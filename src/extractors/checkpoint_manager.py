"""
Checkpoint manager for resumable email extraction.

Per FR-010, saves checkpoint every N emails to allow resumption
of interrupted extractions.
"""
from datetime import datetime
from pathlib import Path

from src.utils.file_manager import load_json, save_json
from src.utils.logger import get_logger
from src.utils.paths import PathConfig

logger = get_logger(__name__)


class CheckpointManager:
    """Manages extraction checkpoints for resumability."""

    def __init__(
        self,
        checkpoint_path: Path | str | None = None,
        checkpoint_interval: int = 100
    ):
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
        self,
        emails_processed: int,
        last_processed_id: str,
        extracted_emails: list
    ) -> None:
        """
        Save extraction checkpoint.

        Args:
            emails_processed: Number of emails processed so far
            last_processed_id: ID of last processed email
            extracted_emails: List of extracted email dicts
        """
        checkpoint_data = {
            "emails_processed": emails_processed,
            "last_processed_id": last_processed_id,
            "timestamp": datetime.now().isoformat(),
            "checkpoint_interval": self.checkpoint_interval,
            "extracted_emails": extracted_emails
        }

        save_json(checkpoint_data, self.checkpoint_file)
        logger.info(f"Checkpoint saved: {emails_processed} emails processed")

    def load_checkpoint(self) -> dict | None:
        """
        Load existing checkpoint.

        Returns:
            Checkpoint data dict or None if no checkpoint exists
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
                logger.error(f"Cannot clear checkpoint: {self.checkpoint_file} is a directory, not a file")
                return

            self.checkpoint_file.unlink()
            logger.info("Checkpoint cleared")

    def get_resume_point(self) -> tuple[int, str, list]:
        """
        Get resumption point from checkpoint.

        Returns:
            Tuple of (emails_processed, last_id, extracted_emails)
            Returns (0, "", []) if no checkpoint
        """
        checkpoint = self.load_checkpoint()
        if not checkpoint:
            return (0, "", [])

        return (
            checkpoint["emails_processed"],
            checkpoint["last_processed_id"],
            checkpoint.get("extracted_emails", [])
        )
