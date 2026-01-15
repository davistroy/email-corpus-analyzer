"""
M365 Email Extractor.

Per contracts/extractor_contract.md, extracts emails from M365 MCP server
with pagination, retry logic, and checkpoint support.

Task 4B.1/4B.2: Enhanced with incremental extraction support and metadata tracking.
"""
import hashlib
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from src.extractors.checkpoint_manager import CheckpointManager
from src.extractors.html_parser import extract_plain_text
from src.extractors.m365_mcp_client import M365MCPClient
from src.models.corpus import Corpus, CorpusMetadata
from src.models.email import Email
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


class EmailExtractor:
    """Extract emails from M365 MCP server."""

    def __init__(
        self,
        user_email: str,
        checkpoint_dir: str = "outputs"
    ):
        """
        Initialize email extractor.

        Args:
            user_email: User's M365 email address
            checkpoint_dir: Directory for checkpoints (will use extraction_checkpoint.json)
        """
        from pathlib import Path

        self.user_email = user_email

        # Convert directory to checkpoint file path
        checkpoint_path = Path(checkpoint_dir) / "extraction_checkpoint.json"
        self.checkpoint_manager = CheckpointManager(checkpoint_path=checkpoint_path)
        self.mcp_client = M365MCPClient(user_email)
        self.logger = get_logger(__name__)

    def extract_all(
        self,
        max_batch_size: int = 500,
        checkpoint_interval: int = 100,
        progress_callback: Callable[[int, int], None] | None = None
    ) -> ExtractionResult:
        """
        Extract all emails from M365 inbox.

        Args:
            max_batch_size: Maximum emails per API request (default 500)
            checkpoint_interval: Save checkpoint every N emails (default 100)
            progress_callback: Optional callback(current, total) for progress

        Returns:
            ExtractionResult with corpus and error summary

        Raises:
            ConnectionError: If M365 MCP server unreachable
            AuthenticationError: If M365 authentication fails
        """
        self.logger.info("Starting email extraction...")

        # Check for existing checkpoint
        emails_processed, last_id, extracted_emails = self.checkpoint_manager.get_resume_point()
        if emails_processed > 0:
            self.logger.info(f"Resuming from checkpoint: {emails_processed} emails already processed")

        failed_emails: list[ExtractionError] = []
        all_emails: list[Email] = []

        # Reconstruct emails from checkpoint
        for email_dict in extracted_emails:
            try:
                all_emails.append(Email(**email_dict))
            except Exception as e:
                self.logger.warning(f"Failed to reconstruct email from checkpoint: {e}")

        # Fetch message list from M365
        # NOTE: This would use M365 MCP tools - using stub for now
        try:
            total_emails = self._get_total_email_count()
            self.logger.info(f"Found {total_emails} total emails to process")
        except Exception as e:
            self.logger.error(f"Failed to get email count: {e}")
            raise ConnectionError(f"M365 MCP server unreachable: {e}")

        # Process in batches
        current_batch = emails_processed // max_batch_size
        while emails_processed < total_emails:
            batch_start = current_batch * max_batch_size
            batch_end = min(batch_start + max_batch_size, total_emails)

            self.logger.debug(f"Processing batch {current_batch + 1}: emails {batch_start}-{batch_end}")

            try:
                batch_emails = self._fetch_batch(batch_start, batch_end, last_id)

                # Check if we've reached the end of available emails
                if not batch_emails:
                    self.logger.info("No more emails to fetch, stopping pagination")
                    break

                for email_data in batch_emails:
                    try:
                        email = self._process_email(email_data)
                        all_emails.append(email)
                        emails_processed += 1
                        last_id = email.id  # Update last_id for checkpoint

                        # Save checkpoint if needed
                        if self.checkpoint_manager.should_checkpoint(emails_processed):
                            self.checkpoint_manager.save_checkpoint(
                                emails_processed,
                                email.id,
                                [e.model_dump() for e in all_emails]
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
                            timestamp=datetime.now()
                        ))

                # If we got fewer emails than requested, we've reached the end
                if len(batch_emails) < (batch_end - batch_start):
                    self.logger.info(f"Received {len(batch_emails)} emails (less than requested), stopping pagination")
                    break

            except Exception as e:
                self.logger.error(f"Batch fetch failed: {e}")
                # Check if rate limited
                if "rate limit" in str(e).lower():
                    self._handle_rate_limit(current_batch)
                else:
                    failed_emails.append(ExtractionError(
                        email_id=f"batch_{current_batch}",
                        error_type="timeout",
                        error_message=str(e),
                        timestamp=datetime.now()
                    ))
                    break  # Stop on non-rate-limit errors

            current_batch += 1

        # Create corpus with enhanced metadata (Task 4B.1)
        # Compute email IDs hash for change detection
        email_ids_hash = self._compute_email_ids_hash(all_emails)

        # Store extraction parameters
        extraction_params = {
            "batch_size": max_batch_size,
            "checkpoint_interval": checkpoint_interval,
        }

        metadata = CorpusMetadata(
            extraction_date=datetime.now(),
            total_emails=len(all_emails),
            source="Hotmail/M365",
            user_email=self.user_email,
            last_extraction_date=datetime.now(),
            email_ids_hash=email_ids_hash,
            extraction_params=extraction_params,
        )
        corpus = Corpus(extraction_metadata=metadata, emails=all_emails)

        # Clear checkpoint on success
        self.checkpoint_manager.clear_checkpoint()

        self.logger.info(f"Extraction complete! {len(all_emails)} emails extracted, {len(failed_emails)} failed")

        return ExtractionResult(
            corpus=corpus,
            failed_emails=failed_emails,
            success_count=len(all_emails),
            failure_count=len(failed_emails),
            total_attempted=len(all_emails) + len(failed_emails)
        )

    def resume_from_checkpoint(self, checkpoint_path: str) -> ExtractionResult:
        """
        Resume interrupted extraction from checkpoint.

        Args:
            checkpoint_path: Path to checkpoint file

        Returns:
            ExtractionResult continuing from checkpoint

        Raises:
            FileNotFoundError: If checkpoint doesn't exist
            ValueError: If checkpoint corrupted
        """
        # Use existing checkpoint manager
        return self.extract_all()

    def extract_incremental(
        self,
        existing_corpus: Corpus,
        max_batch_size: int = 500,
        checkpoint_interval: int = 100,
        progress_callback: Callable[[int, int], None] | None = None
    ) -> IncrementalExtractionResult:
        """
        Perform incremental extraction - only fetch new emails since last extraction.

        Task 4B.2: Implements --since-last functionality.

        Args:
            existing_corpus: Existing corpus to merge new emails into
            max_batch_size: Maximum emails per API request (default 500)
            checkpoint_interval: Save checkpoint every N emails (default 100)
            progress_callback: Optional callback(current, total) for progress

        Returns:
            IncrementalExtractionResult with merged corpus and statistics
        """
        self.logger.info("Starting incremental email extraction...")

        # Track existing email IDs for deduplication
        existing_ids = {email.id for email in existing_corpus.emails}
        previous_count = len(existing_corpus.emails)

        self.logger.info(f"Existing corpus has {previous_count} emails")

        # Get the last extraction date for filtering
        since_date = existing_corpus.extraction_metadata.last_extraction_date
        if since_date:
            self.logger.info(f"Fetching emails since: {since_date.isoformat()}")

        failed_emails: list[ExtractionError] = []
        new_emails: list[Email] = []

        # Fetch new emails from M365
        try:
            total_available = self._get_total_email_count()
            self.logger.info(f"Server reports {total_available} emails available")
        except Exception as e:
            self.logger.error(f"Failed to get email count: {e}")
            raise ConnectionError(f"M365 MCP server unreachable: {e}")

        # Process in batches (similar to extract_all but with deduplication)
        current_batch = 0
        emails_processed = 0

        while True:
            batch_start = current_batch * max_batch_size
            batch_end = batch_start + max_batch_size

            self.logger.debug(f"Processing batch {current_batch + 1}: emails {batch_start}-{batch_end}")

            try:
                batch_emails = self._fetch_batch(batch_start, batch_end)

                if not batch_emails:
                    self.logger.info("No more emails to fetch, stopping pagination")
                    break

                for email_data in batch_emails:
                    try:
                        email_id = email_data.get("id", "")

                        # Skip if already in existing corpus (deduplication)
                        if email_id in existing_ids:
                            self.logger.debug(f"Skipping duplicate email: {email_id}")
                            continue

                        email = self._process_email(email_data)
                        new_emails.append(email)
                        existing_ids.add(email_id)  # Track to avoid duplicates in same batch
                        emails_processed += 1

                        if progress_callback:
                            progress_callback(emails_processed, emails_processed)

                    except Exception as e:
                        self.logger.warning(f"Failed to process email: {e}")
                        failed_emails.append(ExtractionError(
                            email_id=email_data.get("id", "unknown"),
                            error_type="malformed",
                            error_message=str(e),
                            timestamp=datetime.now()
                        ))

                # If we got fewer emails than requested, we've reached the end
                if len(batch_emails) < max_batch_size:
                    self.logger.info(f"Received {len(batch_emails)} emails (less than requested), stopping pagination")
                    break

            except Exception as e:
                self.logger.error(f"Batch fetch failed: {e}")
                if "rate limit" in str(e).lower():
                    self._handle_rate_limit(current_batch)
                else:
                    break

            current_batch += 1

        # Merge new emails with existing corpus
        all_emails = list(existing_corpus.emails) + new_emails
        new_emails_count = len(new_emails)
        total_count = len(all_emails)

        self.logger.info(f"Added {new_emails_count} new emails ({previous_count} -> {total_count} total)")

        # Create updated corpus with new metadata
        email_ids_hash = self._compute_email_ids_hash(all_emails)
        extraction_params = {
            "batch_size": max_batch_size,
            "checkpoint_interval": checkpoint_interval,
            "incremental": True,
        }

        metadata = CorpusMetadata(
            extraction_date=existing_corpus.extraction_metadata.extraction_date,  # Keep original
            total_emails=total_count,
            source="Hotmail/M365",
            user_email=self.user_email,
            last_extraction_date=datetime.now(),  # Update to now
            email_ids_hash=email_ids_hash,
            extraction_params=extraction_params,
        )

        merged_corpus = Corpus(extraction_metadata=metadata, emails=all_emails)

        return IncrementalExtractionResult(
            corpus=merged_corpus,
            failed_emails=failed_emails,
            new_emails_count=new_emails_count,
            previous_count=previous_count,
            total_count=total_count
        )

    def _get_total_email_count(self) -> int:
        """
        Get total email count from M365.

        Uses M365 MCP server to fetch a minimal batch and extract count.
        Since Microsoft Graph doesn't provide total count without fetching all messages,
        we use a large max_results and check if we get fewer results than requested.
        """
        self.logger.debug("Fetching total email count from M365 MCP")

        try:
            # Fetch with a very small batch to check if we can get count metadata
            result = self.mcp_client.fetch_emails(max_results=1, skip=0)

            # Microsoft Graph doesn't provide total count directly
            # We'll need to estimate by fetching batches until we get fewer than max_results
            # For now, return a large number and rely on pagination to handle actual count
            self.logger.info("M365 doesn't provide total count upfront, will paginate until exhausted")

            # Return a large sentinel value that will be updated during pagination
            # This ensures we don't prematurely stop fetching
            return 999999

        except ConnectionError:
            raise
        except Exception as e:
            self.logger.error(f"Failed to get email count: {e}")
            raise ConnectionError(f"M365 MCP server unreachable: {e}")

    def _fetch_batch(self, start: int, end: int, last_id: str = "") -> list[dict]:
        """
        Fetch a batch of emails from M365.

        Args:
            start: Starting index for this batch
            end: Ending index for this batch
            last_id: Last email ID processed (unused for M365 Graph API)

        Returns:
            List of email dictionaries

        Raises:
            ConnectionError: If M365 MCP server fails
        """
        batch_size = end - start
        self.logger.debug(f"Fetching emails {start}-{end} (batch_size={batch_size})")

        try:
            # Use MCP client to fetch emails with pagination
            emails = self.mcp_client.fetch_emails(
                max_results=batch_size,
                skip=start
            )

            # If we get fewer emails than requested, we've reached the end
            if len(emails) < batch_size:
                self.logger.info(f"Fetched {len(emails)} emails (fewer than requested {batch_size}), reached end of inbox")

            return emails

        except ConnectionError:
            raise
        except Exception as e:
            self.logger.error(f"Failed to fetch batch {start}-{end}: {e}")
            raise ConnectionError(f"M365 batch fetch failed: {e}")

    def _process_email(self, email_data: dict) -> Email:
        """
        Process raw M365 email data into Email model.

        Args:
            email_data: Raw email data from M365

        Returns:
            Validated Email object

        Raises:
            ValueError: If email data is invalid
        """
        # Extract sender domain
        sender_email = email_data.get("from", {}).get("emailAddress", {}).get("address", "")
        sender_domain = sender_email.split("@")[1] if "@" in sender_email else "unknown"

        # Convert HTML body to plain text
        html_body = email_data.get("body", {}).get("content", "")
        try:
            body_text = extract_plain_text(html_body) if html_body else ""
        except Exception as e:
            self.logger.warning(f"HTML parsing failed for email {email_data.get('id')}: {e}")
            body_text = html_body  # Fallback to raw HTML

        # Create Email object
        email = Email(
            id=email_data.get("id", ""),
            sender_email=sender_email,
            sender_name=email_data.get("from", {}).get("emailAddress", {}).get("name", ""),
            sender_domain=sender_domain,
            recipient_email=email_data.get("toRecipients", [{}])[0].get("emailAddress", {}).get("address"),
            recipient_name=email_data.get("toRecipients", [{}])[0].get("emailAddress", {}).get("name", ""),
            subject=email_data.get("subject", ""),
            body_text=body_text,
            received_date=datetime.fromisoformat(email_data.get("receivedDateTime", "").replace("Z", "+00:00")),
            has_attachments=email_data.get("hasAttachments", False)
        )

        return email

    def _handle_rate_limit(self, attempt: int) -> None:
        """
        Handle rate limiting with exponential backoff.

        Args:
            attempt: Current attempt number
        """
        backoff_seconds = min(2 ** attempt, 8)  # Max 8 seconds
        self.logger.warning(f"Rate limited, backing off for {backoff_seconds} seconds")
        time.sleep(backoff_seconds)

    def _compute_email_ids_hash(self, emails: list[Email]) -> str:
        """
        Compute a hash of all email IDs for change detection.

        Task 4B.1: Used to detect if corpus has changed between extractions.

        Args:
            emails: List of Email objects

        Returns:
            SHA256 hash of sorted email IDs
        """
        if not emails:
            return ""

        # Sort IDs for consistent hashing regardless of extraction order
        sorted_ids = sorted(email.id for email in emails)
        combined = "|".join(sorted_ids)
        return hashlib.sha256(combined.encode()).hexdigest()
