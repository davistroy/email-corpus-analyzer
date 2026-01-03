"""
Async email extractor using provider abstraction.

Provides async email extraction with progress tracking,
checkpoint support, and error handling.
"""
import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from src.models.corpus import Corpus, CorpusMetadata
from src.models.email import Email
from src.models.mailbox import Mailbox
from src.providers.base import EmailProvider, ExtractionProgress, RateLimitError
from src.utils.file_manager import load_json, save_json
from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ExtractionError:
    """Details of a failed email extraction."""
    email_id: str
    error_type: str  # "rate_limit", "timeout", "malformed", "unknown"
    error_message: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ExtractionResult:
    """Result of email extraction operation."""
    corpus: Corpus
    failed_emails: list[ExtractionError]
    success_count: int
    failure_count: int
    total_attempted: int
    duration_seconds: float

    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.total_attempted == 0:
            return 0.0
        return self.success_count / self.total_attempted


class AsyncCheckpointManager:
    """Async checkpoint manager for resumable extraction."""

    def __init__(self, checkpoint_path: Path):
        self.checkpoint_path = checkpoint_path
        self._checkpoint_interval = 100

    async def get_resume_point(self) -> tuple[int, datetime | None, list[dict]]:
        """
        Get resume point from checkpoint.

        Returns:
            Tuple of (emails_processed, last_email_date, extracted_emails)
        """
        if not self.checkpoint_path.exists():
            return 0, None, []

        try:
            data = await asyncio.to_thread(load_json, self.checkpoint_path)
            return (
                data.get("emails_processed", 0),
                datetime.fromisoformat(data["last_email_date"]) if data.get("last_email_date") else None,
                data.get("emails", []),
            )
        except Exception as e:
            logger.warning(f"Failed to load checkpoint: {e}")
            return 0, None, []

    async def save_checkpoint(
        self,
        emails_processed: int,
        last_email_date: datetime | None,
        emails: list[dict],
    ) -> None:
        """Save checkpoint data."""
        self.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "emails_processed": emails_processed,
            "last_email_date": last_email_date.isoformat() if last_email_date else None,
            "emails": emails,
            "saved_at": datetime.now().isoformat(),
        }

        await asyncio.to_thread(save_json, data, self.checkpoint_path)
        logger.debug(f"Checkpoint saved: {emails_processed} emails")

    def should_checkpoint(self, emails_processed: int) -> bool:
        """Check if we should save a checkpoint."""
        return emails_processed > 0 and emails_processed % self._checkpoint_interval == 0

    async def clear_checkpoint(self) -> None:
        """Clear checkpoint file."""
        if self.checkpoint_path.exists():
            await asyncio.to_thread(self.checkpoint_path.unlink)
            logger.debug("Checkpoint cleared")


class AsyncEmailExtractor:
    """
    Async email extractor using provider abstraction.

    Supports:
    - Any EmailProvider implementation
    - Async iteration over emails
    - Checkpoint/resume for long extractions
    - Progress callbacks
    - Error collection and reporting
    """

    def __init__(
        self,
        provider: EmailProvider,
        mailbox: Mailbox,
        data_dir: Path,
        checkpoint_interval: int = 100,
    ):
        """
        Initialize async extractor.

        Args:
            provider: Email provider to use.
            mailbox: Mailbox configuration.
            data_dir: Base data directory.
            checkpoint_interval: Save checkpoint every N emails.
        """
        self.provider = provider
        self.mailbox = mailbox
        self.data_dir = data_dir

        checkpoint_path = mailbox.get_checkpoint_path(data_dir)
        self.checkpoint = AsyncCheckpointManager(checkpoint_path)
        self.checkpoint._checkpoint_interval = checkpoint_interval

    async def extract_all(
        self,
        batch_size: int = 100,
        since: datetime | None = None,
        folder: str = "INBOX",
        progress_callback: Callable[[ExtractionProgress], None] | None = None,
    ) -> Corpus:
        """
        Extract all emails from mailbox.

        Args:
            batch_size: Emails per API request.
            since: Only extract emails after this date.
            folder: Folder to extract from.
            progress_callback: Optional progress callback.

        Returns:
            Extracted Corpus.
        """
        start_time = time.time()
        logger.info(f"Starting extraction from {self.mailbox.name} ({self.mailbox.provider.value})")

        # Authenticate if needed
        if not self.provider.is_authenticated:
            await self.provider.authenticate()

        # Get resume point
        emails_processed, last_date, checkpoint_emails = await self.checkpoint.get_resume_point()
        if emails_processed > 0:
            logger.info(f"Resuming from checkpoint: {emails_processed} emails already processed")
            # Use last_date to avoid re-fetching
            if last_date and (not since or last_date > since):
                since = last_date

        # Initialize state
        all_emails: list[Email] = []
        failed_emails: list[ExtractionError] = []

        # Reconstruct emails from checkpoint
        for email_dict in checkpoint_emails:
            try:
                all_emails.append(Email(**email_dict))
            except Exception as e:
                logger.warning(f"Failed to reconstruct email from checkpoint: {e}")

        # Get total count if available
        total_count = await self.provider.get_total_count(folder)

        # Create progress tracker
        progress = ExtractionProgress(
            emails_fetched=len(all_emails),
            total_emails=total_count,
            status="in_progress",
        )

        if progress_callback:
            progress_callback(progress)

        # Fetch emails
        try:
            async for email in self.provider.fetch_emails(
                batch_size=batch_size,
                since=since,
                folder=folder,
            ):
                try:
                    # Add mailbox ID to email
                    email.mailbox_id = self.mailbox.id
                    all_emails.append(email)

                    # Update progress
                    progress.emails_fetched = len(all_emails)
                    progress.last_email_date = email.received_date

                    if progress_callback:
                        progress_callback(progress)

                    # Checkpoint periodically
                    if self.checkpoint.should_checkpoint(len(all_emails)):
                        await self.checkpoint.save_checkpoint(
                            len(all_emails),
                            email.received_date,
                            [e.model_dump(mode="json") for e in all_emails],
                        )

                except Exception as e:
                    logger.warning(f"Failed to process email: {e}")
                    failed_emails.append(ExtractionError(
                        email_id=email.id if email else "unknown",
                        error_type="processing",
                        error_message=str(e),
                    ))

        except RateLimitError as e:
            logger.warning(f"Rate limited: {e}. Saving checkpoint and stopping.")
            await self.checkpoint.save_checkpoint(
                len(all_emails),
                progress.last_email_date,
                [e.model_dump(mode="json") for e in all_emails],
            )
            progress.status = "rate_limited"
            raise

        except Exception as e:
            logger.error(f"Extraction failed: {e}")
            # Save checkpoint before failing
            await self.checkpoint.save_checkpoint(
                len(all_emails),
                progress.last_email_date,
                [e.model_dump(mode="json") for e in all_emails],
            )
            progress.status = "error"
            raise

        # Clear checkpoint on success
        await self.checkpoint.clear_checkpoint()

        # Calculate duration
        duration = time.time() - start_time

        # Create corpus
        metadata = CorpusMetadata(
            mailbox_id=self.mailbox.id,
            mailbox_name=self.mailbox.name,
            provider=self.mailbox.provider,
            source=self.mailbox.provider.value,
            user_email=self.mailbox.email_address,
            extraction_date=datetime.now(),
            extraction_duration_seconds=duration,
            total_emails=len(all_emails),
            folder=folder,
            since_date=since,
        )

        corpus = Corpus(
            extraction_metadata=metadata,
            emails=all_emails,
            schema_version="2.0",
        )

        # Update progress
        progress.status = "completed"
        if progress_callback:
            progress_callback(progress)

        logger.info(
            f"Extraction complete: {len(all_emails)} emails in {duration:.1f}s "
            f"({len(failed_emails)} errors)"
        )

        return corpus


async def extract_from_provider(
    provider: EmailProvider,
    user_email: str,
    output_path: Path,
    batch_size: int = 100,
    since: datetime | None = None,
    folder: str = "INBOX",
    progress_callback: Callable[[ExtractionProgress], None] | None = None,
) -> Corpus:
    """
    Convenience function to extract emails using a provider.

    Args:
        provider: Email provider to use.
        user_email: User's email address.
        output_path: Path to save corpus JSON.
        batch_size: Emails per request.
        since: Only fetch emails after this date.
        folder: Folder to extract from.
        progress_callback: Optional progress callback.

    Returns:
        Extracted Corpus.
    """
    # Create a temporary mailbox for the extraction
    from uuid import uuid4
    from src.models.mailbox import Mailbox

    mailbox = Mailbox(
        id=uuid4(),
        name="Direct Extraction",
        provider=provider.provider_type,
        email_address=user_email,
    )

    data_dir = output_path.parent

    extractor = AsyncEmailExtractor(
        provider=provider,
        mailbox=mailbox,
        data_dir=data_dir,
    )

    corpus = await extractor.extract_all(
        batch_size=batch_size,
        since=since,
        folder=folder,
        progress_callback=progress_callback,
    )

    # Save corpus
    save_json(corpus.model_dump(mode="json"), output_path)

    return corpus
