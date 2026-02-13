"""
M365 Email Extractor.

Per contracts/extractor_contract.md, extracts emails from M365 MCP server
with pagination, retry logic, and checkpoint support.

Task 4B.1/4B.2: Enhanced with incremental extraction support and metadata tracking.
Refactored in Work Item 1.3: Now inherits from BaseExtractor.
"""
from datetime import datetime

from src.extractors.base_extractor import (
    BaseExtractor,
    ExtractionError,
    ExtractionResult,
    IncrementalExtractionResult,
)
from src.extractors.html_parser import extract_plain_text
from src.models.email import Email
from src.utils.logger import get_logger

# Re-export dataclasses for backward compatibility
__all__ = [
    "EmailExtractor",
    "ExtractionError",
    "ExtractionResult",
    "IncrementalExtractionResult",
]

logger = get_logger(__name__)


class EmailExtractor(BaseExtractor):
    """Extract emails from M365 MCP server."""

    def __init__(
        self,
        user_email: str,
        checkpoint_dir: str = "outputs",
        client_id: str | None = None,
    ):
        """
        Initialize email extractor.

        Args:
            user_email: User's M365 email address
            checkpoint_dir: Directory for checkpoints (will use extraction_checkpoint.json)
            client_id: Azure app client ID (uses default public client if None)
        """
        from src.extractors.graph_api_client import GraphAPIClient

        super().__init__(
            user_email=user_email,
            checkpoint_dir=checkpoint_dir,
            checkpoint_filename="extraction_checkpoint.json",
        )
        self.mcp_client = GraphAPIClient(user_email, client_id=client_id)

    # ── BaseExtractor abstract method implementations ─────────────────

    def _get_source_name(self) -> str:
        """Return 'Hotmail/M365' as the source identifier."""
        return "Hotmail/M365"

    def _get_checkpoint_source(self) -> str:
        """Return 'hotmail' as the checkpoint source tag."""
        return "hotmail"

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
            raise ConnectionError(f"M365 batch fetch failed: {e}") from e

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
        return Email(
            id=email_data.get("id", ""),
            sender_email=sender_email,
            sender_name=email_data.get("from", {}).get("emailAddress", {}).get("name", ""),
            sender_domain=sender_domain,
            recipient_email=email_data.get("toRecipients", [{}])[0].get("emailAddress", {}).get("address"),
            recipient_name=email_data.get("toRecipients", [{}])[0].get("emailAddress", {}).get("name", ""),
            subject=email_data.get("subject", ""),
            body_text=body_text,
            received_date=datetime.fromisoformat(email_data.get("receivedDateTime", "").replace("Z", "+00:00")),
            has_attachments=email_data.get("hasAttachments", False),
        )

    # ── M365-specific overrides ───────────────────────────────────────

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
            self.mcp_client.fetch_emails(max_results=1, skip=0)

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
            raise ConnectionError(f"M365 MCP server unreachable: {e}") from e

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
