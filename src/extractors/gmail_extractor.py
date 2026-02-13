"""
Gmail Email Extractor.

Extracts emails from Gmail via the Gmail API with OAuth 2.0 authentication.
Follows the same interface and patterns as EmailExtractor (m365_extractor.py)
for seamless integration with the CLI and pipeline.

Refactored in Work Item 1.3: Now inherits from BaseExtractor.
"""
from datetime import datetime
from pathlib import Path

from src.extractors.base_extractor import (
    BaseExtractor,
    ExtractionError,
    ExtractionResult,
    IncrementalExtractionResult,
)
from src.extractors.html_parser import extract_plain_text
from src.models.corpus import Corpus
from src.models.email import Email
from src.utils.logger import get_logger

# Re-export for any code importing from this module
__all__ = [
    "GmailExtractor",
    "ExtractionError",
    "ExtractionResult",
    "IncrementalExtractionResult",
]

logger = get_logger(__name__)


class GmailExtractor(BaseExtractor):
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

        super().__init__(
            user_email=user_email,
            checkpoint_dir=checkpoint_dir,
            checkpoint_filename="gmail_extraction_checkpoint.json",
        )
        self.gmail_client = GmailClient(
            user_email,
            credentials_path=credentials_path,
        )

    # ── BaseExtractor abstract method implementations ─────────────────

    def _get_source_name(self) -> str:
        """Return 'Gmail' as the source identifier."""
        return "Gmail"

    def _get_checkpoint_source(self) -> str:
        """Return 'gmail' as the checkpoint source tag."""
        return "gmail"

    def _fetch_batch(self, start: int, end: int, last_id: str = "") -> list[dict]:
        """
        Fetch a batch of emails from Gmail.

        Args:
            start: Starting index/offset
            end: Ending index/offset
            last_id: Last email ID (unused for Gmail)

        Returns:
            List of normalized email dictionaries
        """
        batch_size = end - start
        self.logger.debug(f"Fetching emails starting at {start} (batch_size={batch_size})")

        return self.gmail_client.fetch_emails(
            max_results=batch_size,
            skip=start,
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

        return Email(
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

    # ── Gmail-specific overrides ──────────────────────────────────────

    def _fetch_incremental_batch(
        self,
        start: int,
        batch_size: int,
        **kwargs,
    ) -> list[dict]:
        """
        Fetch a batch for incremental extraction with Gmail query filter.

        Args:
            start: Starting offset
            batch_size: Number of emails to fetch
            **kwargs: May contain 'query' for Gmail search filter

        Returns:
            List of normalized email data dicts
        """
        query = kwargs.get("query", "")
        return self.gmail_client.fetch_emails(
            max_results=batch_size,
            skip=start,
            query=query,
        )

    def _get_incremental_kwargs(self, existing_corpus: Corpus) -> dict:
        """
        Build Gmail-specific query for incremental extraction.

        Uses the last_extraction_date to construct an 'after:' Gmail search query.

        Args:
            existing_corpus: Existing corpus with metadata

        Returns:
            Dict with 'query' key for Gmail search
        """
        since_date = existing_corpus.extraction_metadata.last_extraction_date
        query = ""
        if since_date:
            query = f"after:{since_date.strftime('%Y/%m/%d')}"
            self.logger.info(f"Fetching Gmail messages: {query}")
        return {"query": query}
