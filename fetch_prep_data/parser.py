# GitHub data parsing utilities with bank-grade security validation
from datetime import date, datetime
from typing import Any, Dict, List

import frontmatter

from config import FileProcessingConfig, GitHubConfig

from .reader import RawRepositoryFile

MAX_DEPTH = 10
MAX_FILES = GitHubConfig.MAX_FILES.value


def parse_data(data_raw: List[RawRepositoryFile]) -> List[Dict[str, Any]]:
    """
    Parse raw GitHub repository files into structured data with security validation.
    Handles files with invalid frontmatter by skipping frontmatter and using content only.
    Converts datetime and date objects to ISO format strings for JSON compatibility.

    Args:
        data_raw: List of RawRepositoryFile objects from GitHub

    Returns:
        List of parsed document dictionaries with frontmatter metadata

    Raises:
        ValueError: If input validation fails
    """
    if not isinstance(data_raw, list):
        raise ValueError("Input must be a list")

    if len(data_raw) > MAX_FILES:
        raise ValueError(f"Too many files: {len(data_raw)} (max: {MAX_FILES})")

    data_parsed = []
    for f in data_raw:
        if len(f.content) > FileProcessingConfig.MAX_CONTENT_SIZE.value:
            print(f"⚠️  Skipping oversized file {f.filename}: {len(f.content)} bytes")
            continue

        try:
            post = frontmatter.loads(f.content)
            data = post.to_dict()
            data["filename"] = f.filename

            # Convert datetime and date objects to ISO format strings for JSON compatibility
            data = _convert_datetime_to_string(data, depth=0)
            data_parsed.append(data)

        except (frontmatter.FrontMatterError, UnicodeDecodeError) as e:
            print(f"⚠️  Skipping frontmatter for {f.filename}: {str(e)[:50]}...")

            # Create document with just content and filename
            data = {
                "content": f.content,
                "filename": f.filename,
                "title": "",
                "description": "",
            }
            data_parsed.append(data)

    return data_parsed


def _convert_datetime_to_string(data: Dict[str, Any], depth: int = 0) -> Dict[str, Any]:
    """
    Recursively convert datetime and date objects to ISO format strings with depth limit.

    Args:
        data: Dictionary that may contain datetime or date objects
        depth: Current recursion depth (for security)

    Returns:
        Dictionary with datetime and date objects converted to ISO strings

    Raises:
        ValueError: If recursion depth exceeds limit
    """
    if depth > MAX_DEPTH:
        raise ValueError(f"Data structure too deep: {depth} levels (max: {MAX_DEPTH})")

    converted = {}
    for key, value in data.items():
        if isinstance(value, (datetime, date)):
            converted[key] = value.isoformat()
        elif isinstance(value, dict):
            converted[key] = _convert_datetime_to_string(value, depth + 1)
        elif isinstance(value, list):
            converted[key] = [
                item.isoformat() if isinstance(item, (datetime, date)) else item
                for item in value
            ]
        else:
            converted[key] = value
    return converted
