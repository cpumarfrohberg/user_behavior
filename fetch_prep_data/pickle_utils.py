# Secure pickle handler with minimal security validation
import builtins
import hashlib
import pickle
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

# Security limits
MAX_PICKLE_SIZE = 100_000_000  # 100MB


class SafeUnpickler(pickle.Unpickler):
    """Safe unpickler that only allows basic types."""

    def find_class(self, module: str, name: str) -> Any:
        if module == "builtins" and name in {"dict", "list", "str", "int", "float"}:
            return getattr(builtins, name)
        elif module == "datetime" and name == "datetime":
            return datetime
        raise pickle.UnpicklingError(f"Unsafe class: {module}.{name}")


def validate_path(filepath: str) -> Path:
    """Basic path validation."""
    path = Path(filepath).resolve()
    if ".." in str(path):
        raise ValueError("Invalid path")
    return path


def save_parsed_data(
    data: List[Dict[str, Any]], filepath: str = "parsed_data.pkl"
) -> None:
    """Save parsed data with basic security."""
    filepath = validate_path(filepath)

    if not isinstance(data, list):
        raise ValueError("Data must be a list")

    # Ensure directory exists
    filepath.parent.mkdir(parents=True, exist_ok=True)

    # Add metadata
    save_data = {
        "data": data,
        "metadata": {
            "total_files": len(data),
            "saved_at": datetime.now().isoformat(),
            "version": "2.0",
        },
    }

    # Save with pickle
    with open(filepath, "wb") as f:
        pickle.dump(save_data, f)

    # Create integrity hash
    _create_hash(filepath)
    print(f"✅ Saved {len(data)} documents to {filepath}")


def load_parsed_data(filepath: str = "parsed_data.pkl") -> List[Dict[str, Any]]:
    """Load parsed data with basic security."""
    filepath = validate_path(filepath)

    if not filepath.exists():
        raise FileNotFoundError(f"File not found: {filepath}")

    # Check file size
    if filepath.stat().st_size > MAX_PICKLE_SIZE:
        raise ValueError("File too large")

    # Verify integrity
    _verify_hash(filepath)

    # Load with safe unpickler
    with open(filepath, "rb") as f:
        loaded = SafeUnpickler(f).load()

    if not isinstance(loaded, dict) or "data" not in loaded:
        raise ValueError("Invalid pickle file")

    data = loaded["data"]
    if not isinstance(data, list):
        raise ValueError("Data must be a list")

    print(f"📚 Loaded {len(data)} documents from {filepath}")
    return data


def _create_hash(filepath: Path) -> None:
    """Create integrity hash file."""
    hash_file = filepath.with_suffix(filepath.suffix + ".hash")
    with open(filepath, "rb") as f:
        file_hash = hashlib.sha256(f.read()).hexdigest()
    with open(hash_file, "w") as f:
        f.write(file_hash)


def _verify_hash(filepath: Path) -> None:
    """Verify file integrity."""
    hash_file = filepath.with_suffix(filepath.suffix + ".hash")

    if not hash_file.exists():
        raise ValueError("No integrity hash - refusing to load")

    with open(filepath, "rb") as f:
        current_hash = hashlib.sha256(f.read()).hexdigest()

    with open(hash_file, "r") as f:
        stored_hash = f.read().strip()

    if current_hash != stored_hash:
        raise ValueError("File integrity check failed")


def validate_data_structure(data: List[Dict[str, Any]]) -> None:
    """Validate data structure."""
    if not isinstance(data, list):
        raise ValueError("Data must be a list")

    for i, item in enumerate(data):
        if not isinstance(item, dict):
            raise ValueError(f"Item {i} must be a dictionary")

        if "filename" not in item or "content" not in item:
            raise ValueError(f"Item {i} missing required fields")

        if not isinstance(item["filename"], str) or not isinstance(
            item["content"], str
        ):
            raise ValueError(f"Item {i} has invalid types")
