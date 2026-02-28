"""
File manager utility for JSON save/load with proper permissions.

Per Constitution Principle IV (Privacy & Data Security),
all output files have 0600 permissions (user read/write only).

Default output directory: ~/data/outputs
Override using PathConfig.set_output_dir() or CLI arguments.

Work Item 3.4: All critical file writes use atomic_write / atomic_write_text
to prevent corruption from interrupted writes. The pattern is:
  1. Write to path.tmp in the same directory
  2. os.replace(path.tmp, path) on success (atomic on all platforms)
  3. Clean up .tmp file on failure via try/finally
"""

import json
import os
from pathlib import Path
from typing import Any

from src.utils.logger import get_logger
from src.utils.paths import PathConfig

logger = get_logger(__name__)


def atomic_write(file_path: Path | str, content: bytes | str, encoding: str = "utf-8") -> None:
    """
    Write content to a file atomically.

    Writes to a temporary file in the same directory, then uses os.replace()
    to atomically swap it into place. This ensures the target file is either
    fully written or not modified at all -- an interrupted write cannot
    corrupt an existing file.

    Args:
        file_path: Destination file path
        content: Content to write (str or bytes)
        encoding: Encoding for str content (default: utf-8). Ignored for bytes.

    Raises:
        OSError: If the write or replace fails
    """
    path = Path(file_path)
    tmp_path = path.with_suffix(path.suffix + ".tmp")

    try:
        if isinstance(content, bytes):
            with open(tmp_path, "wb") as f:
                f.write(content)
        else:
            with open(tmp_path, "w", encoding=encoding) as f:
                f.write(content)

        # Atomic replace: on all platforms, os.replace is atomic if src and dst
        # are on the same filesystem (which they are -- same directory).
        os.replace(tmp_path, path)
        logger.debug(f"Atomic write completed: {path}")

    except BaseException:
        # Clean up temp file on any failure (including KeyboardInterrupt)
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except OSError:
            pass  # Best-effort cleanup
        raise


def atomic_write_text(file_path: Path | str, text: str, encoding: str = "utf-8") -> None:
    """
    Atomically write text content to a file.

    Convenience wrapper around atomic_write() for text content.
    After writing, sets file permissions to 0600 (user read/write only).

    Args:
        file_path: Destination file path
        text: Text content to write
        encoding: Text encoding (default: utf-8)

    Raises:
        OSError: If the write or replace fails
    """
    path = Path(file_path)
    atomic_write(path, text, encoding=encoding)

    # Set file permissions to 0600 (user read/write only)
    os.chmod(path, 0o600)
    logger.debug(f"Permissions set to 0600: {path}")


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
    data: Any, file_path: Path | str, indent: int = 2, ensure_parents: bool = True
) -> None:
    """
    Save data to JSON file atomically with UTF-8 encoding and 0600 permissions.

    Uses atomic_write to ensure the file is either fully written or not
    modified at all. An interrupted write cannot corrupt an existing file.

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

    # Serialize to string first, then write atomically
    json_content = json.dumps(data, indent=indent, ensure_ascii=False, default=str)
    atomic_write_text(path, json_content)

    logger.info(f"Saved JSON to {path} (atomic, permissions: 0600)")


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

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    logger.debug(f"Loaded JSON from {path}")
    return data
