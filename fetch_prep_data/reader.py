# GitHub repository data reader
import io
import traceback
import zipfile
from dataclasses import dataclass
from typing import Callable, List, Optional

import requests
from pydantic import BaseModel, Field, HttpUrl, ValidationError

from config import FileProcessingConfig, GitHubConfig, RepositoryConfig


@dataclass
class RawRepositoryFile:
    filename: str
    content: str


class RepositoryRequest(BaseModel):
    repo_owner: str = Field(
        ..., min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9_-]+$"
    )
    repo_name: str = Field(
        ..., min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9_.-]+$"
    )
    allowed_extensions: Optional[set] = Field(default=None, max_items=20)


class GitHubRequestConfig(BaseModel):
    base_url: HttpUrl = Field(default=GitHubConfig.BASE_URL.value)
    timeout: int = Field(default=GitHubConfig.TIMEOUT.value, ge=1, le=300)
    max_file_size: int = Field(default=GitHubConfig.MAX_FILE_SIZE.value)
    max_files: int = Field(default=GitHubConfig.MAX_FILES.value)
    max_total_size: int = Field(default=GitHubConfig.MAX_TOTAL_SIZE.value)


def read_github_data(
    repo_owner: str,
    repo_name: str,
    allowed_extensions: set | None = None,
    filename_filter: Callable | None = None,
) -> List[RawRepositoryFile]:
    try:
        request = RepositoryRequest(
            repo_owner=repo_owner,
            repo_name=repo_name,
            allowed_extensions=allowed_extensions,
        )
    except ValidationError as e:
        raise ValidationError(f"Invalid repository parameters: {e}")

    repo_owner = request.repo_owner
    repo_name = request.repo_name
    allowed_extensions = (
        request.allowed_extensions or RepositoryConfig.DEFAULT_EXTENSIONS.value
    )

    # Create GitHub config with security limits
    github_config = GitHubRequestConfig()

    url = f"{RepositoryConfig.GITHUB_CODELOAD_URL.value}/{repo_owner}/{repo_name}/zip/refs/heads/main"

    if filename_filter is None:

        def filename_filter(filepath):
            return True

    try:
        resp = requests.get(url, timeout=github_config.timeout)

        if resp.status_code == 404:
            raise Exception(
                f"Repository not found: {repo_owner}/{repo_name}. Please check the repository name and owner."
            )
        elif resp.status_code == 403:
            raise Exception(
                f"Access forbidden to repository: {repo_owner}/{repo_name}. Repository may be private or access is blocked."
            )
        elif resp.status_code == 429:
            raise Exception(
                "Rate limited by GitHub. Please wait before making another request."
            )
        elif resp.status_code != 200:
            raise Exception(f"Failed to download repository: HTTP {resp.status_code}")

    except requests.exceptions.Timeout:
        raise Exception(f"Request timeout after {github_config.timeout} seconds")
    except requests.exceptions.RequestException as e:
        raise Exception(f"Network error: {e}")

    file_config = FileProcessingConfig

    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    repository_data = _extract_files(
        zf, allowed_extensions, filename_filter, github_config, file_config
    )
    zf.close()

    return repository_data


def _extract_files(
    zf: zipfile.ZipFile,
    allowed_extensions: set,
    filename_filter: Callable,
    github_config: GitHubRequestConfig,
    file_config: type,
) -> List[RawRepositoryFile]:
    """Extract and process files from the zip archive with security checks."""
    data = []
    skipped_stats = {"oversized": 0, "unsafe_type": 0, "filtered": 0, "processed": 0}

    for file_info in zf.infolist():
        if file_info.file_size > file_config.MAX_FILE_SIZE.value:
            skipped_stats["oversized"] += 1
            continue

        filepath = _normalize_filepath(file_info.filename)
        # Security: Check file extension
        if not _is_safe_file(filepath, file_config):
            skipped_stats["unsafe_type"] += 1
            continue

        if _should_skip_file(filepath, allowed_extensions, filename_filter):
            skipped_stats["filtered"] += 1
            continue

        try:
            with zf.open(file_info) as f_in:
                content = f_in.read().decode("utf-8", errors="ignore")
                if content is not None:
                    content = content.strip()

                # Security: Check content size
                if len(content) > file_config.MAX_CONTENT_SIZE.value:
                    skipped_stats["oversized"] += 1
                    continue

                file = RawRepositoryFile(filename=filepath, content=content)
                data.append(file)
                skipped_stats["processed"] += 1

        except Exception as e:
            print(f"Error processing {file_info.filename}: {e}")
            traceback.print_exc()
            continue

    # Print summary instead of individual messages
    total_skipped = sum(skipped_stats.values()) - skipped_stats["processed"]
    if total_skipped > 0:
        print("📊 File processing summary:")
        print(f"   ✅ Processed: {skipped_stats['processed']} files")
        if skipped_stats["oversized"] > 0:
            print(f"   ⚠️  Skipped oversized: {skipped_stats['oversized']} files")
        if skipped_stats["unsafe_type"] > 0:
            print(f"   🔒 Skipped unsafe types: {skipped_stats['unsafe_type']} files")
        if skipped_stats["filtered"] > 0:
            print(f"   🔍 Filtered out: {skipped_stats['filtered']} files")

    return data


def _is_safe_file(filepath: str, file_config: type) -> bool:
    """Check if file is safe to process based on extension."""
    ext = _get_extension(filepath).lower()

    if ext in file_config.BLOCKED_EXTENSIONS.value:
        return False

    if ext in file_config.ALLOWED_EXTENSIONS.value:
        return True

    # Block files without extensions (potential executables)
    if not ext:
        return False

    # Default: block unknown file types
    return False


def _should_skip_file(
    filepath: str, allowed_extensions: set, filename_filter: Callable
) -> bool:
    """Determine whether a file should be skipped during processing."""
    filepath = filepath.lower()

    # directory
    if filepath.endswith("/"):
        return True

    # hidden file
    filename = filepath.split("/")[-1]
    if filename.startswith("."):
        return True

    if allowed_extensions:
        ext = _get_extension(filepath)
        if ext not in allowed_extensions:
            return True

    if not filename_filter(filepath):
        return True

    return False


def _get_extension(filepath: str) -> str:
    filename = filepath.lower().split("/")[-1]
    if "." in filename:
        return filename.rsplit(".", maxsplit=1)[-1]
    else:
        return ""


def _normalize_filepath(filepath: str) -> str:
    """
    Removes the top-level directory from the file path inside the zip archive.
    'repo-main/path/to/file.py' -> 'path/to/file.py'

    Also provides path traversal protection.
    """
    parts = filepath.split("/", maxsplit=1)
    if len(parts) > 1:
        normalized_path = parts[1]
    else:
        normalized_path = parts[0]

    # Security: Prevent path traversal attacks
    if ".." in normalized_path or normalized_path.startswith("/"):
        raise ValueError(f"Invalid file path detected: {filepath}")

    return normalized_path
