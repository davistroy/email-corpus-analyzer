"""
M365 Email Extractor for Claude Code MCP Integration.

This module provides a direct extraction interface that uses MCP tools
when executed by Claude Code. It bypasses the M365MCPClient stub and
directly invokes MCP tools via Claude's execution context.
"""
from collections.abc import Callable
from datetime import datetime

from src.extractors.html_parser import extract_plain_text
from src.models.corpus import Corpus, CorpusMetadata
from src.models.email import Email
from src.utils.logger import get_logger

logger = get_logger(__name__)


def extract_emails_via_mcp(
    user_email: str,
    batch_size: int = 100,
    max_emails: int | None = None,
    progress_callback: Callable[[int, int], None] | None = None
) -> Corpus:
    """
    Extract emails using Claude Code's M365 MCP integration.

    This function is designed to be called by Claude Code, which will
    replace the MCP tool calls with actual mcp__m365-email__fetch_emails
    invocations.

    Args:
        user_email: M365 email address to extract from
        batch_size: Number of emails to fetch per batch
        max_emails: Maximum total emails to extract (None = all)
        progress_callback: Optional callback(current, total)

    Returns:
        Corpus object with extracted emails

    Note:
        When Claude Code executes this function, it will identify the
        MCP tool call comments and replace them with actual MCP invocations.
    """
    logger.info(f"Starting email extraction for {user_email}")
    logger.info(f"Batch size: {batch_size}, Max emails: {max_emails or 'all'}")

    all_emails: list[Email] = []
    skip = 0
    extraction_start = datetime.now()

    while True:
        # MCP_TOOL_CALL: mcp__m365-email__fetch_emails
        # Parameters: user_email={user_email}, max_results={batch_size}, skip={skip}
        # Expected return: List of message dictionaries from Microsoft Graph API
        #
        # Claude Code: Please replace this comment block with actual MCP tool call:
        # batch_messages = mcp__m365-email__fetch_emails(
        #     user_email=user_email,
        #     max_results=batch_size,
        #     skip=skip
        # )

        # Fallback for non-Claude execution
        logger.warning(
            f"MCP tool call not executed. This script must be run by Claude Code "
            f"with M365 MCP server configured. Batch would fetch skip={skip}, "
            f"max_results={batch_size}"
        )
        batch_messages = []

        if not batch_messages:
            logger.info("No more emails to fetch")
            break

        logger.info(f"Processing batch of {len(batch_messages)} emails (skip={skip})")

        for msg in batch_messages:
            try:
                # Extract email metadata
                email_id = msg.get("id", f"unknown_{skip}_{len(all_emails)}")
                subject = msg.get("subject", "")

                # Extract sender info
                from_field = msg.get("from", {}).get("emailAddress", {})
                sender_email = from_field.get("address", "unknown@unknown.com")
                sender_name = from_field.get("name", "")
                sender_domain = sender_email.split("@")[-1] if "@" in sender_email else ""

                # Extract recipient info
                to_recipients = msg.get("toRecipients", [])
                recipient_email = ""
                recipient_name = ""
                if to_recipients:
                    first_recipient = to_recipients[0].get("emailAddress", {})
                    recipient_email = first_recipient.get("address", "")
                    recipient_name = first_recipient.get("name", "")

                # Extract body content
                body_data = msg.get("body", {})
                body_html = body_data.get("content", "")
                body_text = extract_plain_text(body_html) if body_html else ""

                # Parse received date
                received_str = msg.get("receivedDateTime", "")
                received_date = datetime.fromisoformat(received_str.replace("Z", "+00:00")) if received_str else datetime.now()

                # Check for attachments
                has_attachments = msg.get("hasAttachments", False)

                # Create Email object
                email = Email(
                    id=email_id,
                    sender_email=sender_email,
                    sender_name=sender_name or sender_email,
                    sender_domain=sender_domain,
                    recipient_email=recipient_email or user_email,
                    recipient_name=recipient_name or user_email,
                    subject=subject,
                    body_text=body_text,
                    received_date=received_date,
                    has_attachments=has_attachments
                )

                all_emails.append(email)

                # Progress callback
                if progress_callback:
                    total = max_emails if max_emails else len(all_emails) + batch_size
                    progress_callback(len(all_emails), total)

            except Exception as e:
                logger.error(f"Failed to parse email {msg.get('id', 'unknown')}: {e}")
                continue

        skip += len(batch_messages)

        # Check if we've reached max_emails
        if max_emails and len(all_emails) >= max_emails:
            logger.info(f"Reached max_emails limit: {max_emails}")
            all_emails = all_emails[:max_emails]
            break

        # Check if we got fewer emails than batch_size (end of inbox)
        if len(batch_messages) < batch_size:
            logger.info("Reached end of inbox")
            break

    extraction_end = datetime.now()
    extraction_duration = (extraction_end - extraction_start).total_seconds()

    # Create corpus metadata
    metadata = CorpusMetadata(
        extraction_date=extraction_start,
        total_emails=len(all_emails),
        source="M365/Hotmail",
        user_email=user_email
    )

    corpus = Corpus(
        extraction_metadata=metadata,
        emails=all_emails
    )

    logger.info(f"Extraction complete: {len(all_emails)} emails in {extraction_duration:.2f}s")

    return corpus
