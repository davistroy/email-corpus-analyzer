"""
Centralized path configuration for email corpus analysis system.

This module provides a single source of truth for all file paths,
eliminating hardcoded paths and reducing technical debt.

Default output directory: ~/data/outputs
Can be overridden via PathConfig.set_output_dir() or CLI arguments.
"""
import os
from pathlib import Path

from src.utils.logger import get_logger

logger = get_logger(__name__)


class PathConfig:
    """
    Centralized path configuration with runtime override support.

    Thread-safe singleton pattern for managing output directory paths.
    """

    _output_dir: Path | None = None

    @classmethod
    def get_default_output_dir(cls) -> Path:
        """
        Get the default output directory.

        Returns:
            Path to ~/data/outputs (expands ~ to user home directory)
        """
        return Path.home() / "data" / "outputs"

    @classmethod
    def get_output_dir(cls) -> Path:
        """
        Get the configured output directory.

        Returns:
            Currently configured output directory (or default if not set)
        """
        if cls._output_dir is None:
            return cls.get_default_output_dir()
        return cls._output_dir

    @classmethod
    def set_output_dir(cls, path: Path | str) -> Path:
        """
        Override the output directory for this session.

        Args:
            path: New output directory path

        Returns:
            Resolved absolute path
        """
        cls._output_dir = Path(path).resolve()
        logger.info(f"Output directory set to: {cls._output_dir}")
        return cls._output_dir

    @classmethod
    def reset_to_default(cls) -> None:
        """Reset output directory to default."""
        cls._output_dir = None
        logger.debug("Output directory reset to default")

    @classmethod
    def get_corpus_path(cls) -> Path:
        """Get path for email corpus JSON file."""
        return cls.get_output_dir() / "email_corpus.json"

    @classmethod
    def get_analysis_path(cls) -> Path:
        """Get path for analysis results JSON file."""
        return cls.get_output_dir() / "corpus_analysis_results.json"

    @classmethod
    def get_suggestions_path(cls) -> Path:
        """Get path for category suggestions JSON file."""
        return cls.get_output_dir() / "category_suggestions.json"

    @classmethod
    def get_suggestions_report_path(cls) -> Path:
        """Get path for category suggestions markdown report."""
        return cls.get_output_dir() / "category_suggestions_report.md"

    @classmethod
    def get_approved_categories_path(cls) -> Path:
        """Get path for approved categories JSON file."""
        return cls.get_output_dir() / "approved_categories.json"

    @classmethod
    def get_error_log_path(cls) -> Path:
        """Get path for extraction errors log file."""
        return cls.get_output_dir() / "extraction_errors.log"

    @classmethod
    def get_checkpoint_path(cls) -> Path:
        """Get path for extraction checkpoint JSON file."""
        return cls.get_output_dir() / "extraction_checkpoint.json"

    @classmethod
    def ensure_output_dir_exists(cls) -> Path:
        """
        Ensure output directory exists with secure permissions.

        Returns:
            Path to output directory

        Raises:
            OSError: If directory creation fails
        """
        output_dir = cls.get_output_dir()
        output_dir.mkdir(parents=True, exist_ok=True, mode=0o700)

        # Ensure permissions are set correctly (in case dir already existed)
        os.chmod(output_dir, 0o700)

        logger.debug(f"Output directory ensured: {output_dir} (permissions: 0700)")
        return output_dir


# Convenience functions for backward compatibility
def get_output_dir() -> Path:
    """Get the configured output directory."""
    return PathConfig.get_output_dir()


def set_output_dir(path: Path | str) -> Path:
    """Set the output directory for this session."""
    return PathConfig.set_output_dir(path)


def ensure_output_dir() -> Path:
    """Ensure output directory exists."""
    return PathConfig.ensure_output_dir_exists()
