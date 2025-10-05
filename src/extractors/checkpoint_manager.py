"""
Checkpoint manager for resumable email extraction.

Per FR-010, saves checkpoint every N emails to allow resumption
of interrupted extractions.
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.utils.logger import get_logger
from src.utils.file_manager import save_json, load_json

logger = get_logger(__name__)


class CheckpointManager:
    """Manages extraction checkpoints for resumability."""

    def __init__(
        self,
        checkpoint_dir: Path | str = "outputs",
        checkpoint_interval: int = 100
    ):
        """
        Initialize checkpoint manager.

        Args:
            checkpoint_dir: Directory for checkpoint files
            checkpoint_interval: Save checkpoint every N emails
        """
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_interval = checkpoint_interval
        self.checkpoint_file = self.checkpoint_dir / "extraction_checkpoint.json"

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

    def load_checkpoint(self) -> Optional[dict]:
        """
        Load existing checkpoint.

        Returns:
            Checkpoint data dict or None if no checkpoint exists
        """
        if not self.checkpoint_file.exists():
            logger.debug("No checkpoint file found")
            return None

        try:
            checkpoint_data = load_json(self.checkpoint_file)
            logger.info(
                f"Checkpoint loaded: {checkpoint_data['emails_processed']} emails "
                f"from {checkpoint_data['timestamp']}"
            )
            return checkpoint_data
        except Exception as e:
            logger.error(f"Failed to load checkpoint: {e}")
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
