"""
Gmail email provider implementation.

Uses Google API Client for email access with OAuth2 authentication.
Supports both personal Gmail and Google Workspace accounts.
"""
import asyncio
import base64
from collections.abc import AsyncIterator
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path

from src.models.email import Email
from src.models.provider import GmailConfig, ProviderType
from src.providers.base import (
    AuthenticationError,
    BaseEmailProvider,
    FolderInfo,
    RateLimitError,
)
from src.utils.logger import get_logger

logger = get_logger(__name__)


class GmailProvider(BaseEmailProvider):
    """
    Gmail email provider using Google API.

    Supports:
    - Personal Gmail accounts
    - Google Workspace accounts
    - OAuth2 authentication with credentials.json
    """

    SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

    def __init__(self, config: GmailConfig):
        super().__init__(config.email_address)
        self.config = config
        self._service = None
        self._credentials = None

    @property
    def provider_type(self) -> ProviderType:
        return ProviderType.GMAIL

    async def authenticate(self) -> bool:
        """
        Authenticate using OAuth2 flow.

        Requires a credentials.json file from Google Cloud Console.

        Returns:
            True if authentication successful.

        Raises:
            AuthenticationError: If authentication fails.
        """
        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from googleapiclient.discovery import build

            creds = None
            token_path = Path(self.config.token_file) if self.config.token_file else None

            # Load existing token if available
            if token_path and token_path.exists():
                creds = Credentials.from_authorized_user_file(str(token_path), self.SCOPES)

            # Refresh or get new credentials
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    logger.info("Refreshing expired Gmail credentials")
                    await asyncio.to_thread(lambda: creds.refresh(Request()))
                else:
                    # Check credentials file exists
                    creds_path = Path(self.config.credentials_file)
                    if not creds_path.exists():
                        raise AuthenticationError(
                            f"Gmail credentials file not found: {self.config.credentials_file}. "
                            "Download from Google Cloud Console > APIs & Services > Credentials.",
                            provider=ProviderType.GMAIL,
                            recoverable=False,
                        )

                    logger.info("Starting Gmail OAuth flow")
                    print("\n" + "=" * 60)
                    print("Gmail Authentication Required")
                    print("=" * 60)
                    print("\nA browser window will open for Google sign-in.")
                    print("=" * 60 + "\n")

                    flow = InstalledAppFlow.from_client_secrets_file(
                        str(creds_path),
                        self.SCOPES,
                    )
                    creds = await asyncio.to_thread(
                        lambda: flow.run_local_server(port=0)
                    )

                # Save token for future use
                if token_path:
                    token_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(token_path, "w") as f:
                        f.write(creds.to_json())
                    token_path.chmod(0o600)

            # Build Gmail service
            self._credentials = creds
            self._service = await asyncio.to_thread(
                lambda: build("gmail", "v1", credentials=creds)
            )

            # Verify by getting profile
            profile = await asyncio.to_thread(
                lambda: self._service.users().getProfile(userId="me").execute()
            )

            self._authenticated = True
            logger.info(f"Authenticated as: {profile.get('emailAddress')}")
            return True

        except ImportError as e:
            raise AuthenticationError(
                f"Gmail dependencies not installed. Run: pip install google-api-python-client google-auth-oauthlib. Error: {e}",
                provider=ProviderType.GMAIL,
                recoverable=False,
            ) from e
        except Exception as e:
            logger.error(f"Gmail authentication failed: {e}")
            raise AuthenticationError(
                f"Gmail authentication failed: {e}",
                provider=ProviderType.GMAIL,
                recoverable=True,
            ) from e

    async def fetch_emails(
        self,
        batch_size: int = 100,
        since: datetime | None = None,
        folder: str = "INBOX",
        include_body: bool = True,
    ) -> AsyncIterator[Email]:
        """
        Fetch emails from Gmail using API.

        Args:
            batch_size: Emails per request (max 500).
            since: Only fetch emails after this date.
            folder: Label name (INBOX, SENT, etc.)
            include_body: Include full body content.

        Yields:
            Email objects.
        """
        if not self._service:
            raise AuthenticationError(
                "Not authenticated. Call authenticate() first.",
                provider=ProviderType.GMAIL,
            )

        # Build query
        query_parts = []

        # Map common folder names to Gmail label queries
        label_map = {
            "INBOX": "in:inbox",
            "SENT": "in:sent",
            "DRAFTS": "in:drafts",
            "TRASH": "in:trash",
            "SPAM": "in:spam",
            "ALL": "",
        }
        label_query = label_map.get(folder.upper(), f"label:{folder}")
        if label_query:
            query_parts.append(label_query)

        # Add date filter
        if since:
            date_str = since.strftime("%Y/%m/%d")
            query_parts.append(f"after:{date_str}")

        query = " ".join(query_parts) if query_parts else None

        try:
            page_token = None
            while True:
                # List message IDs
                result = await asyncio.to_thread(
                    lambda token=page_token: self._service.users().messages().list(
                        userId="me",
                        q=query,
                        maxResults=min(batch_size, 500),
                        pageToken=token,
                    ).execute()
                )

                messages = result.get("messages", [])
                if not messages:
                    break

                # Fetch full message details in batches
                for msg_info in messages:
                    try:
                        full_msg = await self._fetch_message(msg_info["id"], include_body)
                        email_obj = self._map_to_email(full_msg, folder)
                        yield email_obj
                    except Exception as e:
                        logger.warning(f"Failed to fetch message {msg_info['id']}: {e}")
                        continue

                # Check for more pages
                page_token = result.get("nextPageToken")
                if not page_token:
                    break

        except Exception as e:
            if "rateLimitExceeded" in str(e) or "quotaExceeded" in str(e):
                raise RateLimitError(f"Rate limited by Gmail: {e}", retry_after=60) from e
            raise

    async def _fetch_message(self, message_id: str, include_body: bool) -> dict:
        """Fetch full message details."""
        format_type = "full" if include_body else "metadata"

        return await asyncio.to_thread(
            lambda: self._service.users().messages().get(
                userId="me",
                id=message_id,
                format=format_type,
            ).execute()
        )

    def _map_to_email(self, msg: dict, folder: str) -> Email:
        """Map Gmail API message to Email model."""
        from src.extractors.html_parser import extract_plain_text

        # Extract headers
        headers = {h["name"].lower(): h["value"] for h in msg.get("payload", {}).get("headers", [])}

        # Parse sender
        from_header = headers.get("from", "")
        sender_email, sender_name = self._parse_email_address(from_header)
        sender_domain = sender_email.split("@")[1] if "@" in sender_email else "unknown"

        # Parse recipient
        to_header = headers.get("to", "")
        recipient_email, recipient_name = self._parse_email_address(to_header)

        # Parse date
        date_header = headers.get("date", "")
        try:
            received_date = parsedate_to_datetime(date_header)
        except Exception:
            # Fallback to internal date
            internal_date = msg.get("internalDate", "0")
            received_date = datetime.fromtimestamp(int(internal_date) / 1000)

        # Extract body
        body_text, body_html = self._extract_body(msg.get("payload", {}))
        if body_html and not body_text:
            body_text = extract_plain_text(body_html)

        # Get labels
        labels = msg.get("labelIds", [])

        return Email(
            id=msg["id"],
            provider=ProviderType.GMAIL,
            sender_email=sender_email,
            sender_name=sender_name,
            sender_domain=sender_domain,
            recipient_email=recipient_email if recipient_email else None,
            recipient_name=recipient_name,
            subject=headers.get("subject", ""),
            body_text=body_text or "",
            body_html=body_html,
            received_date=received_date,
            has_attachments=len(msg.get("payload", {}).get("parts", [])) > 0,
            folder=folder,
            labels=labels,
            is_read="UNREAD" not in labels,
            importance="high" if "IMPORTANT" in labels else "normal",
            thread_id=msg.get("threadId"),
            in_reply_to=headers.get("in-reply-to"),
        )

    def _parse_email_address(self, header: str) -> tuple[str, str]:
        """Parse email address from header like 'Name <email@example.com>'."""
        if not header:
            return "unknown@unknown.com", ""

        # Handle format: "Name <email>"
        if "<" in header and ">" in header:
            name = header.split("<")[0].strip().strip('"')
            email_addr = header.split("<")[1].split(">")[0].strip()
            return email_addr, name

        # Just email address
        return header.strip(), ""

    def _extract_body(self, payload: dict) -> tuple[str | None, str | None]:
        """Extract text and HTML body from payload."""
        text_body = None
        html_body = None

        mime_type = payload.get("mimeType", "")

        # Simple message
        if mime_type.startswith("text/"):
            data = payload.get("body", {}).get("data", "")
            if data:
                decoded = base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
                if mime_type == "text/plain":
                    text_body = decoded
                elif mime_type == "text/html":
                    html_body = decoded

        # Multipart message
        elif mime_type.startswith("multipart/"):
            for part in payload.get("parts", []):
                part_text, part_html = self._extract_body(part)
                if part_text and not text_body:
                    text_body = part_text
                if part_html and not html_body:
                    html_body = part_html

        return text_body, html_body

    async def get_total_count(self, folder: str = "INBOX") -> int | None:
        """Get total message count."""
        if not self._service:
            return None

        try:
            # Map folder to label ID
            label_map = {
                "INBOX": "INBOX",
                "SENT": "SENT",
                "DRAFTS": "DRAFT",
                "TRASH": "TRASH",
                "SPAM": "SPAM",
            }
            label_id = label_map.get(folder.upper(), folder)

            result = await asyncio.to_thread(
                lambda: self._service.users().labels().get(
                    userId="me",
                    id=label_id,
                ).execute()
            )

            return result.get("messagesTotal", 0)

        except Exception as e:
            logger.warning(f"Failed to get message count: {e}")
            return None

    async def list_folders(self) -> list[FolderInfo]:
        """List Gmail labels."""
        if not self._service:
            return []

        try:
            result = await asyncio.to_thread(
                lambda: self._service.users().labels().list(userId="me").execute()
            )

            folders = []
            for label in result.get("labels", []):
                # Get label details for counts
                try:
                    detail = await asyncio.to_thread(
                        lambda lid=label["id"]: self._service.users().labels().get(
                            userId="me",
                            id=lid,
                        ).execute()
                    )
                    folders.append(FolderInfo(
                        name=label["name"],
                        message_count=detail.get("messagesTotal"),
                        unread_count=detail.get("messagesUnread"),
                        folder_type="label",
                    ))
                except Exception:
                    folders.append(FolderInfo(
                        name=label["name"],
                        folder_type="label",
                    ))

            return folders

        except Exception as e:
            logger.warning(f"Failed to list labels: {e}")
            return []

    async def close(self) -> None:
        """Clean up resources."""
        self._service = None
        self._credentials = None
        self._authenticated = False
        logger.debug("Gmail provider closed")
