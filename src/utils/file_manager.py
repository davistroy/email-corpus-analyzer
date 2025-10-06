"""
File manager utility for JSON save/load with proper permissions.

Per Constitution Principle IV (Privacy & Data Security),
all output files have 0600 permissions (user read/write only).

Default output directory: ~/data/outputs
Override using PathConfig.set_output_dir() or CLI arguments.
"""
import json
import os
from pathlib import Path
from typing import Any

from src.utils.logger import get_logger
from src.utils.paths import PathConfig

logger = get_logger(__name__)


def ensure_output_dir(output_dir: Path | str | None = None) -> Path:
    """
    Ensure output directory exists with secure permissions.

    Args:
        output_dir: Path to output directory (default: uses PathConfig)

    Returns:
        Path object for output directory

    Raises:
        OSError: If directory creation fails
    """
    if output_dir is None:
        # Use centralized configuration
        return PathConfig.ensure_output_dir_exists()

    # Custom path provided - create it with secure permissions
    path = Path(output_dir)
    path.mkdir(parents=True, exist_ok=True)

    # Set directory permissions to 0700 (user read/write/execute only)
    os.chmod(path, 0o700)
    logger.debug(f"Output directory ensured: {path} (permissions: 0700)")

    return path


def save_json(
    data: Any,
    file_path: Path | str,
    indent: int = 2,
    ensure_parents: bool = True
) -> None:
    """
    Save data to JSON file with UTF-8 encoding and 0600 permissions.

    Args:
        data: Data to serialize to JSON
        file_path: Path to output JSON file
        indent: JSON indentation (default: 2)
        ensure_parents: Create parent directories if needed

    Raises:
        OSError: If file write fails
        TypeError: If data is not JSON-serializable
    """
    path = Path(file_path)

    if ensure_parents:
        path.parent.mkdir(parents=True, exist_ok=True)

    # Write JSON with pretty printing
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=indent, ensure_ascii=False, default=str)

    # Set file permissions to 0600 (user read/write only)
    os.chmod(path, 0o600)
    logger.info(f"Saved JSON to {path} (permissions: 0600)")


def load_json(file_path: Path | str) -> Any:
    """
    Load data from JSON file.

    Args:
        file_path: Path to JSON file

    Returns:
        Deserialized JSON data

    Raises:
        FileNotFoundError: If file doesn't exist
        json.JSONDecodeError: If file contains invalid JSON
    """
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"JSON file not found: {path}")

    with open(path, encoding='utf-8') as f:
        data = json.load(f)

    logger.debug(f"Loaded JSON from {path}")
    return data
