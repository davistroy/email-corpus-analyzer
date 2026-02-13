"""
Gmail API client using OAuth 2.0 with device/OOB flow.

Authenticates with Google and fetches emails via the Gmail API.

Authentication:
    - First run: opens browser for OAuth consent (or uses device code)
    - Subsequent runs: uses cached refresh token
    - Token cache: ~/.email-analyzer/gmail_token.json
    - Credentials: ~/.email-analyzer/gmail_credentials.json

Setup:
    1. Go to https://console.cloud.google.com/
    2. Create project or select existing
    3. Enable Gmail API
    4. Create OAuth 2.0 credentials (Desktop application)
    5. Download client_secret JSON → save as ~/.email-analyzer/gmail_credentials.json
"""
import base64
import json
from pathlib import Path
from typing import Any

from src.utils.logger import get_logger

logger = get_logger(__name__)

CREDENTIALS_DIR = Path.home() / ".email-analyzer"
CREDENTIALS_FILE = CREDENTIALS_DIR / "gmail_credentials.json"
TOKEN_FILE = CREDENTIALS_DIR / "gmail_token.json"

# Gmail API scopes - read-only access
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


class GmailClient:
    """
    Gmail API client with OAuth 2.0 authentication.

    Fetches emails via the Gmail API using messages.list and messages.get.
    """

    def __init__(
        self,
        user_email: str,
        credentials_path: Path | None = None,
        token_path: Path | None = None,
    ):
        self.user_email = user_email
        self.credentials_path = credentials_path or CREDENTIALS_FILE
        self.token_path = token_path or TOKEN_FILE
        self._service = None

    def _get_credentials(self):
        """
        Get or refresh OAuth 2.0 credentials.

        Returns:
            google.oauth2.credentials.Credentials object

        Raises:
            FileNotFoundError: If credentials file doesn't exist
            RuntimeError: If authentication fails
        """
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow

        creds = None

        # Load cached token
        if self.token_path.exists():
            creds = Credentials.from_authorized_user_file(
                str(self.token_path), SCOPES
            )

        # Refresh or get new credentials
        if creds and creds.valid:
            return creds

        if creds and creds.expired and creds.refresh_token:
            logger.info("Refreshing expired Gmail token...")
            try:
                creds.refresh(Request())
                self._save_token(creds)
                return creds
            except Exception as e:
                logger.warning(f"Token refresh failed: {e}, starting new auth flow")

        # New authentication flow
        if not self.credentials_path.exists():
            raise FileNotFoundError(
                f"Gmail credentials not found at {self.credentials_path}. "
                f"Download OAuth client JSON from Google Cloud Console and save it there. "
                f"See: https://console.cloud.google.com/apis/credentials"
            )

        logger.info("Starting Gmail OAuth authentication flow...")
        print("\n" + "=" * 60)
        print("GMAIL AUTHENTICATION REQUIRED")
        print("=" * 60)
        print("A browser window will open for Google sign-in.")
        print("=" * 60 + "\n")

        flow = InstalledAppFlow.from_client_secrets_file(
            str(self.credentials_path), SCOPES
        )
        creds = flow.run_local_server(port=0)

        self._save_token(creds)
        logger.info("Gmail authentication successful, token cached.")
        return creds

    def _save_token(self, creds) -> None:
        """Save credentials to token file with restrictive permissions."""
        import os
        self.token_path.parent.mkdir(parents=True, exist_ok=True)
        self.token_path.write_text(creds.to_json())
        try:
            os.chmod(self.token_path, 0o600)
        except OSError:
            pass  # Windows may not support chmod

    def _get_service(self):
        """Get or create Gmail API service."""
        if self._service is None:
            from googleapiclient.discovery import build

            creds = self._get_credentials()
            self._service = build("gmail", "v1", credentials=creds)
        return self._service

    def fetch_emails(
        self,
        max_results: int = 500,
        skip: int = 0,
        query: str = "",
    ) -> list[dict[str, Any]]:
        """
        Fetch emails from Gmail inbox.

        Args:
            max_results: Maximum emails to return
            skip: Number of emails to skip (implemented via page tokens)
            query: Gmail search query (e.g., "after:2024/01/01")

        Returns:
            List of message dicts normalized to Microsoft Graph format
            for compatibility with the existing Email model.

        Raises:
            ConnectionError: On API errors
        """
        service = self._get_service()

        try:
            # Get message IDs
            message_ids = self._list_message_ids(
                service, max_results=max_results, skip=skip, query=query
            )

            if not message_ids:
                logger.info("No messages found")
                return []

            # Fetch full message details
            messages = []
            for msg_id in message_ids:
                try:
                    msg = self._get_message(service, msg_id)
                    if msg:
                        messages.append(msg)
                except Exception as e:
                    logger.warning(f"Failed to fetch message {msg_id}: {e}")

            logger.info(f"Fetched {len(messages)} emails from Gmail")
            return messages

        except Exception as e:
            raise ConnectionError(f"Gmail API error: {e}") from e

    def _list_message_ids(
        self,
        service,
        max_results: int,
        skip: int = 0,
        query: str = "",
    ) -> list[str]:
        """
        List message IDs from Gmail, handling pagination and skip.

        Args:
            service: Gmail API service
            max_results: Max messages to return
            skip: Messages to skip
            query: Gmail search query

        Returns:
            List of message ID strings
        """
        all_ids: list[str] = []
        page_token = None
        total_needed = skip + max_results

        while len(all_ids) < total_needed:
            batch_size = min(500, total_needed - len(all_ids))

            request_params: dict[str, Any] = {
                "userId": "me",
                "maxResults": batch_size,
                "labelIds": ["INBOX"],
            }
            if query:
                request_params["q"] = query
            if page_token:
                request_params["pageToken"] = page_token

            result = service.users().messages().list(**request_params).execute()
            messages = result.get("messages", [])

            if not messages:
                break

            all_ids.extend(m["id"] for m in messages)
            page_token = result.get("nextPageToken")

            if not page_token:
                break

        # Apply skip and limit
        return all_ids[skip : skip + max_results]

    def _get_message(self, service, message_id: str) -> dict[str, Any] | None:
        """
        Fetch a single message and normalize to Graph API format.

        The normalized format matches Microsoft Graph API structure so the
        existing Email model and _process_email() work without changes.
        """
        msg = (
            service.users()
            .messages()
            .get(userId="me", id=message_id, format="full")
            .execute()
        )

        headers = {h["name"].lower(): h["value"] for h in msg.get("payload", {}).get("headers", [])}

        # Extract sender
        from_header = headers.get("from", "")
        sender_email, sender_name = self._parse_email_header(from_header)

        # Extract recipients
        to_header = headers.get("to", "")
        recipient_email, recipient_name = self._parse_email_header(to_header)

        # Extract body
        body_html = self._extract_body(msg.get("payload", {}))

        # Extract date
        date_str = headers.get("date", "")
        received_dt = self._parse_date(date_str, msg.get("internalDate"))

        # Thread info
        thread_id = msg.get("threadId", "")
        in_reply_to = headers.get("in-reply-to", "")
        references = headers.get("references", "").split() if headers.get("references") else []

        # Normalize to Graph API format for compatibility with EmailExtractor._process_email()
        return {
            "id": message_id,
            "subject": headers.get("subject", "(No subject)"),
            "from": {
                "emailAddress": {
                    "address": sender_email,
                    "name": sender_name,
                }
            },
            "toRecipients": [
                {
                    "emailAddress": {
                        "address": recipient_email,
                        "name": recipient_name,
                    }
                }
            ]
            if recipient_email
            else [],
            "receivedDateTime": received_dt,
            "body": {"contentType": "html", "content": body_html},
            "bodyPreview": msg.get("snippet", ""),
            "hasAttachments": bool(
                msg.get("payload", {}).get("parts", [])
                and any(
                    p.get("filename")
                    for p in msg.get("payload", {}).get("parts", [])
                )
            ),
            "conversationId": thread_id,
            # Extra fields for thread analysis
            "_gmail_thread_id": thread_id,
            "_in_reply_to": in_reply_to,
            "_references": references,
        }

    def _extract_body(self, payload: dict) -> str:
        """Extract HTML or plain text body from Gmail message payload.

        Delegates to a recursive helper that walks arbitrarily nested
        MIME structures (multipart/mixed -> multipart/alternative -> text/html, etc.).
        """
        html_parts: list[str] = []
        text_parts: list[str] = []
        self._extract_body_recursive(payload, html_parts, text_parts, depth=0, max_depth=10)

        # Prefer HTML; fall back to plain text
        if html_parts:
            return html_parts[0]
        if text_parts:
            return text_parts[0]

        # Last resort: top-level body data regardless of MIME type
        body_data = payload.get("body", {}).get("data")
        if body_data:
            return base64.urlsafe_b64decode(body_data).decode("utf-8", errors="replace")

        return ""

    def _extract_body_recursive(
        self,
        payload: dict,
        html_parts: list[str],
        text_parts: list[str],
        depth: int = 0,
        max_depth: int = 10,
    ) -> None:
        """Recursively walk a MIME payload tree collecting text bodies.

        Args:
            payload: A Gmail API payload or part dict.
            html_parts: Accumulator for decoded text/html bodies.
            text_parts: Accumulator for decoded text/plain bodies.
            depth: Current recursion depth.
            max_depth: Maximum recursion depth to prevent stack overflow
                       on malformed messages.
        """
        if depth > max_depth:
            return

        mime_type = payload.get("mimeType", "")
        body_data = payload.get("body", {}).get("data")

        # Leaf node with data
        if body_data:
            decoded = base64.urlsafe_b64decode(body_data).decode("utf-8", errors="replace")
            if "html" in mime_type:
                html_parts.append(decoded)
            elif "plain" in mime_type:
                text_parts.append(decoded)

        # Recurse into child parts
        for part in payload.get("parts", []):
            self._extract_body_recursive(part, html_parts, text_parts, depth + 1, max_depth)

    @staticmethod
    def _parse_email_header(header: str) -> tuple[str, str]:
        """
        Parse an email From/To header into (email, name).

        Handles formats like:
            "John Doe <john@example.com>"
            "john@example.com"
            "<john@example.com>"
        """
        import re

        if not header:
            return ("unknown@unknown.com", "")

        # Try "Name <email>" format
        match = re.match(r'^"?([^"<]*)"?\s*<([^>]+)>', header.strip())
        if match:
            name = match.group(1).strip().strip('"')
            email = match.group(2).strip()
            return (email, name)

        # Try bare email
        match = re.match(r'^<?([^@\s]+@[^>\s]+)>?$', header.strip())
        if match:
            email = match.group(1)
            return (email, "")

        # Fallback
        return (header.strip(), "")

    @staticmethod
    def _parse_date(date_str: str, internal_date_ms: str | None = None) -> str:
        """
        Parse email date header to ISO format compatible with Graph API.

        Args:
            date_str: RFC 2822 date string from email header
            internal_date_ms: Gmail internalDate in milliseconds

        Returns:
            ISO 8601 datetime string with Z suffix
        """
        from datetime import datetime, timezone
        from email.utils import parsedate_to_datetime

        # Try parsing the header date
        if date_str:
            try:
                dt = parsedate_to_datetime(date_str)
                return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            except Exception:
                pass

        # Fallback to internalDate
        if internal_date_ms:
            try:
                dt = datetime.fromtimestamp(
                    int(internal_date_ms) / 1000, tz=timezone.utc
                )
                return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
            except Exception:
                pass

        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def get_message_body(self, message_id: str) -> str:
        """
        Fetch full body of a specific message.

        Args:
            message_id: Gmail message ID

        Returns:
            HTML body content
        """
        service = self._get_service()
        try:
            msg = (
                service.users()
                .messages()
                .get(userId="me", id=message_id, format="full")
                .execute()
            )
            return self._extract_body(msg.get("payload", {}))
        except Exception as e:
            logger.error(f"Failed to get message body: {e}")
            raise ConnectionError(f"Failed to get message body: {e}") from e
