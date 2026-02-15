"""
Base Extractor ABC for email extraction.

Consolidates shared logic from EmailExtractor (M365) and GmailExtractor:
- Checkpoint handling (save/load/resume/clear)
- Batch loop with pagination
- Error collection and reporting
- Progress callback invocation
- Corpus construction and metadata
- Rate limit handling with exponential backoff
- Email ID hash computation for change detection

Subclasses implement only API-specific behavior via abstract methods.
"""
import hashlib
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from src.extractors.checkpoint_manager import CheckpointManager
from src.models.corpus import Corpus, CorpusMetadata
from src.models.email import Email
from src.utils.constants import (
    DEFAULT_BATCH_SIZE,
    DEFAULT_CHECKPOINT_INTERVAL,
    EMAIL_COUNT_SENTINEL,
    MAX_BACKOFF_SECONDS,
)
from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ExtractionError:
    """Details of a failed email extraction."""
    email_id: str
    error_type: str  # "rate_limit", "timeout", "malformed", "unknown"
    error_message: str
    timestamp: datetime


@dataclass
class ExtractionResult:
    """Result of email extraction operation."""
    corpus: Corpus
    failed_emails: list[ExtractionError]
    success_count: int
    failure_count: int
    total_attempted: int

    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        return self.success_count / self.total_attempted if self.total_attempted > 0 else 0.0


@dataclass
class IncrementalExtractionResult:
    """Result of incremental email extraction operation (Task 4B.2)."""
    corpus: Corpus
    failed_emails: list[ExtractionError]
    new_emails_count: int  # Number of newly added emails
    previous_count: int  # Number of emails before extraction
    total_count: int  # Total emails after extraction

    @property
    def success_rate(self) -> float:
        """Calculate success rate for new emails."""
        total_attempted = self.new_emails_count + len(self.failed_emails)
        return self.new_emails_count / total_attempted if total_attempted > 0 else 1.0


class BaseExtractor(ABC):
    """
    Abstract base class for email extractors.

    Provides the shared extraction workflow (batch loop, checkpointing,
    error collection, corpus construction). Subclasses supply only the
    API-specific pieces via abstract methods.
    """

    def __init__(
        self,
        user_email: str,
        checkpoint_dir: str = "outputs",
        checkpoint_filename: str = "extraction_checkpoint.json",
    ):
        """
        Initialize base extractor.

        Args:
            user_email: User's email address
            checkpoint_dir: Directory for checkpoint files
            checkpoint_filename: Name of the checkpoint file
        """
        self.user_email = user_email
        checkpoint_path = Path(checkpoint_dir) / checkpoint_filename
        self.checkpoint_manager = CheckpointManager(checkpoint_path=checkpoint_path)
        self.logger = get_logger(self.__class__.__module__)

    # ── Abstract methods (subclasses must implement) ───────────────────

    @abstractmethod
    def _get_source_name(self) -> str:
        """
        Return the source identifier for this extractor.

        Returns:
            Source name, e.g. "Hotmail/M365" or "Gmail"
        """

    @abstractmethod
    def _get_checkpoint_source(self) -> str:
        """
        Return the checkpoint source tag.

        Returns:
            Short source tag for checkpoint files, e.g. "hotmail" or "gmail"
        """

    @abstractmethod
    def _fetch_batch(self, start: int, end: int, last_id: str = "") -> list[dict]:
        """
        Fetch a batch of raw email data from the API.

        Args:
            start: Starting index/offset for this batch
            end: Ending index/offset for this batch
            last_id: Last processed email ID (for APIs that use cursor pagination)

        Returns:
            List of raw email data dictionaries
        """

    @abstractmethod
    def _process_email(self, email_data: dict) -> Email:
        """
        Convert a raw email data dict into an Email model.

        Each provider has different field mappings (M365 Graph format,
        Gmail normalized format, etc.).

        Args:
            email_data: Raw email data from the provider API

        Returns:
            Validated Email object
        """

    # ── Optional hooks for subclass customization ─────────────────────

    def _get_total_email_count(self) -> int:
        """
        Get the total email count from the provider.

        Default returns a large sentinel value (999999) to rely on
        pagination stopping when an empty batch is returned.
        Subclasses may override to provide an actual count.

        Returns:
            Total email count or sentinel value
        """
        return EMAIL_COUNT_SENTINEL

    def _fetch_incremental_batch(
        self,
        start: int,
        batch_size: int,
        **kwargs,
    ) -> list[dict]:
        """
        Fetch a batch for incremental extraction.

        Default delegates to _fetch_batch. Subclasses can override to
        add query parameters (e.g. Gmail date filters).

        Args:
            start: Starting offset
            batch_size: Number of emails to fetch
            **kwargs: Additional provider-specific parameters

        Returns:
            List of raw email data dicts
        """
        return self._fetch_batch(start, start + batch_size)

    # ── Shared implementation ─────────────────────────────────────────

    def extract_all(
        self,
        max_batch_size: int = DEFAULT_BATCH_SIZE,
        checkpoint_interval: int = DEFAULT_CHECKPOINT_INTERVAL,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> ExtractionResult:
        """
        Extract all emails from the provider inbox.

        Args:
            max_batch_size: Maximum emails per API request (default 500)
            checkpoint_interval: Save checkpoint every N emails (default 100)
            progress_callback: Optional callback(current, total) for progress

        Returns:
            ExtractionResult with corpus and error summary

        Raises:
            ConnectionError: If the email server is unreachable
            AuthenticationError: If authentication fails
        """
        source_name = self._get_source_name()
        self.logger.info(f"Starting {source_name} email extraction...")

        # Check for existing checkpoint
        emails_processed, last_id = self.checkpoint_manager.get_resume_point()
        if emails_processed > 0:
            self.logger.info(
                f"Resuming from checkpoint: {emails_processed} emails already processed"
            )

        failed_emails: list[ExtractionError] = []
        all_emails: list[Email] = []

        # Get total count (may be a sentinel for APIs without counts)
        try:
            total_emails = self._get_total_email_count()
            self.logger.info(f"Found {total_emails} total emails to process")
        except Exception as e:
            self.logger.error(f"Failed to get email count: {e}")
            raise ConnectionError(f"{source_name} server unreachable: {e}") from e

        # Process in batches
        current_batch = emails_processed // max_batch_size
        while emails_processed < total_emails:
            batch_start = current_batch * max_batch_size
            batch_end = min(batch_start + max_batch_size, total_emails)

            self.logger.debug(
                f"Processing batch {current_batch + 1}: emails {batch_start}-{batch_end}"
            )

            try:
                batch_emails = self._fetch_batch(batch_start, batch_end, last_id)

                # Empty batch = end of available emails
                if not batch_emails:
                    self.logger.info("No more emails to fetch, stopping pagination")
                    break

                for email_data in batch_emails:
                    try:
                        email = self._process_email(email_data)
                        all_emails.append(email)
                        emails_processed += 1
                        last_id = email.id

                        # Save checkpoint at intervals
                        if self.checkpoint_manager.should_checkpoint(emails_processed):
                            self.checkpoint_manager.save_checkpoint(
                                emails_processed,
                                email.id,
                                source=self._get_checkpoint_source(),
                            )

                        # Update progress
                        if progress_callback:
                            progress_callback(emails_processed, len(all_emails))

                    except Exception as e:
                        self.logger.warning(f"Failed to process email: {e}")
                        failed_emails.append(ExtractionError(
                            email_id=email_data.get("id", "unknown"),
                            error_type="malformed",
                            error_message=str(e),
                            timestamp=datetime.now(),
                        ))

                # Fewer than requested = end of inbox
                if len(batch_emails) < (batch_end - batch_start):
                    self.logger.info(
                        f"Received {len(batch_emails)} emails "
                        f"(less than requested), stopping pagination"
                    )
                    break

            except Exception as e:
                self.logger.error(f"Batch fetch failed: {e}")
                if "rate" in str(e).lower():
                    self._handle_rate_limit(current_batch)
                else:
                    failed_emails.append(ExtractionError(
                        email_id=f"batch_{current_batch}",
                        error_type="timeout",
                        error_message=str(e),
                        timestamp=datetime.now(),
                    ))
                    break  # Stop on non-rate-limit errors

            current_batch += 1

        # Build corpus with metadata
        email_ids_hash = self._compute_email_ids_hash(all_emails)
        extraction_params = {
            "batch_size": max_batch_size,
            "checkpoint_interval": checkpoint_interval,
        }

        metadata = CorpusMetadata(
            extraction_date=datetime.now(),
            total_emails=len(all_emails),
            source=source_name,
            user_email=self.user_email,
            last_extraction_date=datetime.now(),
            email_ids_hash=email_ids_hash,
            extraction_params=extraction_params,
        )
        corpus = Corpus(extraction_metadata=metadata, emails=all_emails)

        # Clear checkpoint on success
        self.checkpoint_manager.clear_checkpoint()

        self.logger.info(
            f"{source_name} extraction complete: "
            f"{len(all_emails)} emails extracted, {len(failed_emails)} failed"
        )

        return ExtractionResult(
            corpus=corpus,
            failed_emails=failed_emails,
            success_count=len(all_emails),
            failure_count=len(failed_emails),
            total_attempted=len(all_emails) + len(failed_emails),
        )

    def extract_incremental(
        self,
        existing_corpus: Corpus,
        max_batch_size: int = DEFAULT_BATCH_SIZE,
        checkpoint_interval: int = DEFAULT_CHECKPOINT_INTERVAL,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> IncrementalExtractionResult:
        """
        Incremental extraction -- only fetch new emails since last extraction.

        Args:
            existing_corpus: Existing corpus to merge new emails into
            max_batch_size: Maximum emails per API request (default 500)
            checkpoint_interval: Save checkpoint every N emails (default 100)
            progress_callback: Optional callback(current, total) for progress

        Returns:
            IncrementalExtractionResult with merged corpus and statistics
        """
        source_name = self._get_source_name()
        self.logger.info(f"Starting incremental {source_name} extraction...")

        existing_ids = {email.id for email in existing_corpus.emails}
        previous_count = len(existing_corpus.emails)
        self.logger.info(f"Existing corpus has {previous_count} emails")

        # Let subclass build any provider-specific query params
        incremental_kwargs = self._get_incremental_kwargs(existing_corpus)

        failed_emails: list[ExtractionError] = []
        new_emails: list[Email] = []
        current_batch = 0
        emails_processed = 0

        while True:
            batch_start = current_batch * max_batch_size

            self.logger.debug(
                f"Processing batch {current_batch + 1}: starting at {batch_start}"
            )

            try:
                batch_emails = self._fetch_incremental_batch(
                    batch_start, max_batch_size, **incremental_kwargs
                )

                if not batch_emails:
                    self.logger.info("No more emails to fetch, stopping pagination")
                    break

                for email_data in batch_emails:
                    try:
                        email_id = email_data.get("id", "")

                        # Deduplicate against existing corpus
                        if email_id in existing_ids:
                            self.logger.debug(f"Skipping duplicate email: {email_id}")
                            continue

                        email = self._process_email(email_data)
                        new_emails.append(email)
                        existing_ids.add(email_id)
                        emails_processed += 1

                        if progress_callback:
                            progress_callback(emails_processed, emails_processed)

                    except Exception as e:
                        self.logger.warning(f"Failed to process email: {e}")
                        failed_emails.append(ExtractionError(
                            email_id=email_data.get("id", "unknown"),
                            error_type="malformed",
                            error_message=str(e),
                            timestamp=datetime.now(),
                        ))

                # Fewer than requested = end of inbox
                if len(batch_emails) < max_batch_size:
                    self.logger.info(
                        f"Received {len(batch_emails)} emails "
                        f"(less than requested), stopping pagination"
                    )
                    break

            except Exception as e:
                self.logger.error(f"Batch fetch failed: {e}")
                if "rate" in str(e).lower():
                    self._handle_rate_limit(current_batch)
                else:
                    break

            current_batch += 1

        # Merge new emails with existing corpus
        all_emails = list(existing_corpus.emails) + new_emails
        new_emails_count = len(new_emails)
        total_count = len(all_emails)

        self.logger.info(
            f"Added {new_emails_count} new {source_name} emails "
            f"({previous_count} -> {total_count} total)"
        )

        # Build updated corpus metadata
        email_ids_hash = self._compute_email_ids_hash(all_emails)
        extraction_params = {
            "batch_size": max_batch_size,
            "checkpoint_interval": checkpoint_interval,
            "incremental": True,
        }

        metadata = CorpusMetadata(
            extraction_date=existing_corpus.extraction_metadata.extraction_date,
            total_emails=total_count,
            source=source_name,
            user_email=self.user_email,
            last_extraction_date=datetime.now(),
            email_ids_hash=email_ids_hash,
            extraction_params=extraction_params,
        )

        merged_corpus = Corpus(extraction_metadata=metadata, emails=all_emails)

        return IncrementalExtractionResult(
            corpus=merged_corpus,
            failed_emails=failed_emails,
            new_emails_count=new_emails_count,
            previous_count=previous_count,
            total_count=total_count,
        )

    def _get_incremental_kwargs(self, existing_corpus: Corpus) -> dict:
        """
        Build provider-specific keyword arguments for incremental batch fetching.

        Default returns empty dict. Subclasses can override to add
        query filters (e.g. Gmail date-based query).

        Args:
            existing_corpus: The existing corpus (contains last_extraction_date, etc.)

        Returns:
            Dict of extra kwargs to pass to _fetch_incremental_batch
        """
        return {}

    def _handle_rate_limit(self, attempt: int) -> None:
        """
        Handle rate limiting with exponential backoff.

        Args:
            attempt: Current attempt number (used for backoff calculation)
        """
        backoff_seconds = min(2 ** attempt, MAX_BACKOFF_SECONDS)
        self.logger.warning(f"Rate limited, backing off for {backoff_seconds} seconds")
        time.sleep(backoff_seconds)

    @staticmethod
    def _compute_email_ids_hash(emails: list[Email]) -> str:
        """
        Compute a SHA256 hash of all email IDs for change detection.

        Args:
            emails: List of Email objects

        Returns:
            SHA256 hex digest of sorted email IDs, or empty string if no emails
        """
        if not emails:
            return ""
        sorted_ids = sorted(email.id for email in emails)
        combined = "|".join(sorted_ids)
        return hashlib.sha256(combined.encode()).hexdigest()
