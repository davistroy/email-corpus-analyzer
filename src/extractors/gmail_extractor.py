"""
Gmail Email Extractor.

Extracts emails from Gmail via the Gmail API with OAuth 2.0 authentication.
Follows the same interface and patterns as EmailExtractor (m365_extractor.py)
for seamless integration with the CLI and pipeline.
"""
import hashlib
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from src.extractors.checkpoint_manager import CheckpointManager
from src.extractors.html_parser import extract_plain_text
from src.extractors.m365_extractor import ExtractionError, ExtractionResult, IncrementalExtractionResult
from src.models.corpus import Corpus, CorpusMetadata
from src.models.email import Email
from src.utils.logger import get_logger

logger = get_logger(__name__)


class GmailExtractor:
    """Extract emails from Gmail via the Gmail API."""

    def __init__(
        self,
        user_email: str,
        checkpoint_dir: str = "outputs",
        credentials_path: Path | None = None,
    ):
        """
        Initialize Gmail extractor.

        Args:
            user_email: Gmail address
            checkpoint_dir: Directory for checkpoints
            credentials_path: Path to Gmail OAuth credentials JSON
        """
        from src.extractors.gmail_client import GmailClient

        self.user_email = user_email
        checkpoint_path = Path(checkpoint_dir) / "gmail_extraction_checkpoint.json"
        self.checkpoint_manager = CheckpointManager(checkpoint_path=checkpoint_path)
        self.gmail_client = GmailClient(
            user_email,
            credentials_path=credentials_path,
        )
        self.logger = get_logger(__name__)

    def extract_all(
        self,
        max_batch_size: int = 500,
        checkpoint_interval: int = 100,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> ExtractionResult:
        """
        Extract all emails from Gmail inbox.

        Args:
            max_batch_size: Maximum emails per API request
            checkpoint_interval: Save checkpoint every N emails
            progress_callback: Optional callback(current, total) for progress

        Returns:
            ExtractionResult with corpus and error summary
        """
        self.logger.info("Starting Gmail email extraction...")

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

        # Process in batches
        current_batch = emails_processed // max_batch_size

        while True:
            batch_start = current_batch * max_batch_size
            self.logger.debug(f"Processing batch {current_batch + 1}: starting at {batch_start}")

            try:
                batch_emails = self.gmail_client.fetch_emails(
                    max_results=max_batch_size,
                    skip=batch_start,
                )

                if not batch_emails:
                    self.logger.info("No more emails to fetch, stopping pagination")
                    break

                for email_data in batch_emails:
                    try:
                        email = self._process_email(email_data)
                        all_emails.append(email)
                        emails_processed += 1
                        last_id = email.id

                        if self.checkpoint_manager.should_checkpoint(emails_processed):
                            self.checkpoint_manager.save_checkpoint(
                                emails_processed,
                                email.id,
                                [e.model_dump() for e in all_emails],
                            )

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
                if len(batch_emails) < max_batch_size:
                    self.logger.info(f"Received {len(batch_emails)} (< {max_batch_size}), reached end")
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
                    break

            current_batch += 1

        # Build corpus
        email_ids_hash = self._compute_email_ids_hash(all_emails)
        metadata = CorpusMetadata(
            extraction_date=datetime.now(),
            total_emails=len(all_emails),
            source="Gmail",
            user_email=self.user_email,
            last_extraction_date=datetime.now(),
            email_ids_hash=email_ids_hash,
            extraction_params={
                "batch_size": max_batch_size,
                "checkpoint_interval": checkpoint_interval,
            },
        )
        corpus = Corpus(extraction_metadata=metadata, emails=all_emails)

        self.checkpoint_manager.clear_checkpoint()
        self.logger.info(f"Gmail extraction complete: {len(all_emails)} emails, {len(failed_emails)} failed")

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
        max_batch_size: int = 500,
        checkpoint_interval: int = 100,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> IncrementalExtractionResult:
        """
        Incremental extraction — only fetch new emails since last extraction.

        Args:
            existing_corpus: Existing corpus to merge into
            max_batch_size: Maximum emails per batch
            checkpoint_interval: Checkpoint interval
            progress_callback: Progress callback

        Returns:
            IncrementalExtractionResult with merged corpus
        """
        self.logger.info("Starting incremental Gmail extraction...")

        existing_ids = {email.id for email in existing_corpus.emails}
        previous_count = len(existing_corpus.emails)

        # Build Gmail search query for emails after last extraction
        since_date = existing_corpus.extraction_metadata.last_extraction_date
        query = ""
        if since_date:
            query = f"after:{since_date.strftime('%Y/%m/%d')}"
            self.logger.info(f"Fetching Gmail messages: {query}")

        failed_emails: list[ExtractionError] = []
        new_emails: list[Email] = []
        current_batch = 0
        emails_processed = 0

        while True:
            batch_start = current_batch * max_batch_size

            try:
                batch_emails = self.gmail_client.fetch_emails(
                    max_results=max_batch_size,
                    skip=batch_start,
                    query=query,
                )

                if not batch_emails:
                    break

                for email_data in batch_emails:
                    try:
                        email_id = email_data.get("id", "")
                        if email_id in existing_ids:
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

                if len(batch_emails) < max_batch_size:
                    break

            except Exception as e:
                self.logger.error(f"Batch fetch failed: {e}")
                if "rate" in str(e).lower():
                    self._handle_rate_limit(current_batch)
                else:
                    break

            current_batch += 1

        # Merge
        all_emails = list(existing_corpus.emails) + new_emails
        email_ids_hash = self._compute_email_ids_hash(all_emails)

        metadata = CorpusMetadata(
            extraction_date=existing_corpus.extraction_metadata.extraction_date,
            total_emails=len(all_emails),
            source="Gmail",
            user_email=self.user_email,
            last_extraction_date=datetime.now(),
            email_ids_hash=email_ids_hash,
            extraction_params={
                "batch_size": max_batch_size,
                "checkpoint_interval": checkpoint_interval,
                "incremental": True,
            },
        )

        merged_corpus = Corpus(extraction_metadata=metadata, emails=all_emails)

        self.logger.info(f"Added {len(new_emails)} new Gmail emails ({previous_count} -> {len(all_emails)} total)")

        return IncrementalExtractionResult(
            corpus=merged_corpus,
            failed_emails=failed_emails,
            new_emails_count=len(new_emails),
            previous_count=previous_count,
            total_count=len(all_emails),
        )

    def _process_email(self, email_data: dict) -> Email:
        """
        Process Gmail message (already normalized to Graph format by GmailClient).

        Args:
            email_data: Normalized message dict

        Returns:
            Validated Email object
        """
        sender_email = email_data.get("from", {}).get("emailAddress", {}).get("address", "")
        sender_domain = sender_email.split("@")[1] if "@" in sender_email else "unknown"

        html_body = email_data.get("body", {}).get("content", "")
        try:
            body_text = extract_plain_text(html_body) if html_body else ""
        except Exception as e:
            self.logger.warning(f"HTML parsing failed for email {email_data.get('id')}: {e}")
            body_text = html_body

        # Extract thread fields from Gmail-specific data
        thread_id = email_data.get("_gmail_thread_id")
        in_reply_to = email_data.get("_in_reply_to") or None
        references = email_data.get("_references", [])

        received_dt_str = email_data.get("receivedDateTime", "")

        email = Email(
            id=email_data.get("id", ""),
            sender_email=sender_email,
            sender_name=email_data.get("from", {}).get("emailAddress", {}).get("name", ""),
            sender_domain=sender_domain,
            recipient_email=email_data.get("toRecipients", [{}])[0].get("emailAddress", {}).get("address")
            if email_data.get("toRecipients")
            else None,
            recipient_name=email_data.get("toRecipients", [{}])[0].get("emailAddress", {}).get("name", "")
            if email_data.get("toRecipients")
            else "",
            subject=email_data.get("subject", ""),
            body_text=body_text,
            received_date=datetime.fromisoformat(received_dt_str.replace("Z", "+00:00")),
            has_attachments=email_data.get("hasAttachments", False),
            thread_id=thread_id,
            in_reply_to=in_reply_to,
            references=references,
        )

        return email

    def _handle_rate_limit(self, attempt: int) -> None:
        """Exponential backoff for rate limiting."""
        backoff = min(2**attempt, 8)
        self.logger.warning(f"Rate limited, backing off {backoff}s")
        time.sleep(backoff)

    @staticmethod
    def _compute_email_ids_hash(emails: list[Email]) -> str:
        """SHA256 hash of sorted email IDs for change detection."""
        if not emails:
            return ""
        sorted_ids = sorted(email.id for email in emails)
        combined = "|".join(sorted_ids)
        return hashlib.sha256(combined.encode()).hexdigest()
