"""
Checkpoint manager for resumable email extraction.

Per FR-010, saves checkpoint every N emails to allow resumption
of interrupted extractions.

Checkpoint format v2 stores only lightweight metadata (< 1KB),
not full email objects. On resume, extractors use the skip offset
to re-fetch from the API at the correct position.
"""

from datetime import datetime
from pathlib import Path

from src.utils.file_manager import load_json, save_json
from src.utils.logger import get_logger
from src.utils.paths import PathConfig

logger = get_logger(__name__)

# Current checkpoint format version
CHECKPOINT_VERSION = 2


class CheckpointManager:
    """Manages extraction checkpoints for resumability."""

    def __init__(self, checkpoint_path: Path | str | None = None, checkpoint_interval: int = 100):
        """
        Initialize checkpoint manager.

        Args:
            checkpoint_path: Custom path for checkpoint file (uses PathConfig if None)
            checkpoint_interval: Save checkpoint every N emails
        """
        self.checkpoint_interval = checkpoint_interval

        if checkpoint_path is None:
            self.checkpoint_file = PathConfig.get_checkpoint_path()
        else:
            self.checkpoint_file = Path(checkpoint_path)

    def save_checkpoint(
        self, emails_processed: int, last_processed_id: str, source: str = "hotmail"
    ) -> None:
        """
        Save extraction checkpoint with lightweight metadata only.

        Args:
            emails_processed: Number of emails processed so far
            last_processed_id: ID of last processed email
            source: Extraction source ("hotmail" or "gmail")
        """
        checkpoint_data = {
            "version": CHECKPOINT_VERSION,
            "emails_processed": emails_processed,
            "last_processed_id": last_processed_id,
            "timestamp": datetime.now().isoformat(),
            "checkpoint_interval": self.checkpoint_interval,
            "source": source,
        }

        save_json(checkpoint_data, self.checkpoint_file)
        logger.info(f"Checkpoint saved: {emails_processed} emails processed")

    def load_checkpoint(self) -> dict | None:
        """
        Load existing checkpoint.

        Returns:
            Checkpoint data dict or None if no checkpoint exists.
            Returns None for v1 (legacy) checkpoints that stored full email objects.
        """
        if not self.checkpoint_file.exists():
            logger.debug("No checkpoint file found")
            return None

        # Check if path is a directory instead of a file
        if self.checkpoint_file.is_dir():
            logger.warning(
                f"Checkpoint path is a directory, not a file: {self.checkpoint_file}. "
                f"Starting fresh extraction."
            )
            return None

        try:
            checkpoint_data = load_json(self.checkpoint_file)

            # Version check: reject v1 (legacy) checkpoints
            version = checkpoint_data.get("version")
            if version is None or version < CHECKPOINT_VERSION:
                logger.warning("Old checkpoint format detected, starting fresh extraction")
                return None

            # Integrity check: emails_processed must be a non-negative integer
            emails_processed = checkpoint_data.get("emails_processed")
            if not isinstance(emails_processed, int) or emails_processed < 0:
                logger.warning(
                    f"Invalid emails_processed value ({emails_processed}), "
                    f"starting fresh extraction."
                )
                return None

            logger.info(
                f"Checkpoint loaded: {checkpoint_data['emails_processed']} emails "
                f"from {checkpoint_data['timestamp']}"
            )
            return checkpoint_data
        except Exception as e:
            logger.warning(f"Failed to load checkpoint: {e}. Starting fresh extraction.")
            return None

    def should_checkpoint(self, current_count: int) -> bool:
        """
        Check if checkpoint should be saved.

        Args:
            current_count: Current number of emails processed

        Returns:
            True if checkpoint should be saved
        """
        return current_count % self.checkpoint_interval == 0

    def clear_checkpoint(self) -> None:
        """Delete checkpoint file after successful completion."""
        if self.checkpoint_file.exists():
            # Ensure we're not trying to delete a directory
            if self.checkpoint_file.is_dir():
                logger.error(
                    f"Cannot clear checkpoint: {self.checkpoint_file} is a directory, not a file"
                )
                return

            self.checkpoint_file.unlink()
            logger.info("Checkpoint cleared")

    def get_resume_point(self) -> tuple[int, str]:
        """
        Get resumption point from checkpoint.

        Returns:
            Tuple of (emails_processed, last_id)
            Returns (0, "") if no checkpoint
        """
        checkpoint = self.load_checkpoint()
        if not checkpoint:
            return (0, "")

        return (
            checkpoint["emails_processed"],
            checkpoint["last_processed_id"],
        )
