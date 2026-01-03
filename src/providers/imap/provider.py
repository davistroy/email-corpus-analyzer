"""
IMAP email provider implementation.

Uses aioimaplib for async IMAP access. Supports generic IMAP servers
including corporate mail servers, self-hosted solutions, and providers
that offer IMAP access.
"""
import asyncio
import email as email_lib
from collections.abc import AsyncIterator
from datetime import datetime
from email.header import decode_header
from email.utils import parsedate_to_datetime

from src.models.email import Email
from src.models.provider import IMAPConfig, ProviderType
from src.providers.base import (
    AuthenticationError,
    BaseEmailProvider,
    FolderInfo,
)
from src.utils.logger import get_logger

logger = get_logger(__name__)


class IMAPProvider(BaseEmailProvider):
    """
    Generic IMAP email provider.

    Supports:
    - Standard IMAP4 servers with SSL/TLS
    - Basic authentication (username/password)
    - OAuth2 authentication (for providers that support it)
    """

    def __init__(self, config: IMAPConfig):
        super().__init__(config.email_address)
        self.config = config
        self._client = None

    @property
    def provider_type(self) -> ProviderType:
        return ProviderType.IMAP

    async def authenticate(self) -> bool:
        """
        Connect and authenticate to IMAP server.

        Returns:
            True if authentication successful.

        Raises:
            AuthenticationError: If connection or login fails.
        """
        try:
            import aioimaplib

            logger.info(f"Connecting to IMAP server: {self.config.host}:{self.config.port}")

            # Create client
            if self.config.use_ssl:
                self._client = aioimaplib.IMAP4_SSL(
                    host=self.config.host,
                    port=self.config.port,
                )
            else:
                self._client = aioimaplib.IMAP4(
                    host=self.config.host,
                    port=self.config.port,
                )

            # Wait for connection
            await self._client.wait_hello_from_server()

            # Login
            username = self.config.username or self.config.email_address
            password = self.config.password.get_secret_value() if self.config.password else ""

            if not password:
                raise AuthenticationError(
                    "IMAP password not provided",
                    provider=ProviderType.IMAP,
                    recoverable=True,
                )

            response = await self._client.login(username, password)

            if response.result != "OK":
                raise AuthenticationError(
                    f"IMAP login failed: {response.result}",
                    provider=ProviderType.IMAP,
                    recoverable=True,
                )

            self._authenticated = True
            logger.info(f"Connected to IMAP server: {self.config.host}")
            return True

        except ImportError as e:
            raise AuthenticationError(
                f"IMAP dependencies not installed. Run: pip install aioimaplib. Error: {e}",
                provider=ProviderType.IMAP,
                recoverable=False,
            )
        except AuthenticationError:
            raise
        except Exception as e:
            logger.error(f"IMAP connection failed: {e}")
            raise AuthenticationError(
                f"IMAP connection failed: {e}",
                provider=ProviderType.IMAP,
                recoverable=True,
            )

    async def fetch_emails(
        self,
        batch_size: int = 100,
        since: datetime | None = None,
        folder: str = "INBOX",
        include_body: bool = True,
    ) -> AsyncIterator[Email]:
        """
        Fetch emails from IMAP mailbox.

        Args:
            batch_size: Emails to process at a time.
            since: Only fetch emails after this date.
            folder: Mailbox folder name.
            include_body: Include full body content.

        Yields:
            Email objects.
        """
        if not self._client:
            raise AuthenticationError(
                "Not connected. Call authenticate() first.",
                provider=ProviderType.IMAP,
            )

        # Select folder
        response = await self._client.select(folder)
        if response.result != "OK":
            logger.error(f"Failed to select folder {folder}: {response}")
            return

        # Build search criteria
        if since:
            date_str = since.strftime("%d-%b-%Y")
            search_criteria = f'SINCE {date_str}'
        else:
            search_criteria = "ALL"

        # Search for messages
        response = await self._client.search(search_criteria)
        if response.result != "OK":
            logger.error(f"Search failed: {response}")
            return

        # Parse message IDs
        message_ids = response.lines[0].split() if response.lines else []
        if not message_ids:
            logger.info(f"No messages found in {folder}")
            return

        logger.info(f"Found {len(message_ids)} messages in {folder}")

        # Fetch in batches
        for i in range(0, len(message_ids), batch_size):
            batch = message_ids[i:i + batch_size]

            for msg_id in batch:
                try:
                    email_obj = await self._fetch_single_email(
                        msg_id.decode() if isinstance(msg_id, bytes) else str(msg_id),
                        folder,
                        include_body,
                    )
                    if email_obj:
                        yield email_obj
                except Exception as e:
                    logger.warning(f"Failed to fetch message {msg_id}: {e}")
                    continue

    async def _fetch_single_email(
        self,
        msg_id: str,
        folder: str,
        include_body: bool,
    ) -> Email | None:
        """Fetch a single email by ID."""
        # Fetch message
        if include_body:
            fetch_cmd = "(RFC822)"
        else:
            fetch_cmd = "(RFC822.HEADER)"

        response = await self._client.fetch(msg_id, fetch_cmd)
        if response.result != "OK":
            logger.warning(f"Failed to fetch message {msg_id}")
            return None

        # Parse the response - aioimaplib returns data in lines
        raw_data = None
        for line in response.lines:
            if isinstance(line, bytes) and (b"RFC822" in line or len(line) > 100):
                raw_data = line
                break

        if not raw_data:
            # Try to find the message data in a different format
            for i, line in enumerate(response.lines):
                if isinstance(line, bytes) and len(line) > 500:
                    raw_data = line
                    break

        if not raw_data:
            logger.warning(f"No message data found for {msg_id}")
            return None

        # Parse email
        try:
            msg = email_lib.message_from_bytes(raw_data)
            return self._map_to_email(msg, msg_id, folder)
        except Exception as e:
            logger.warning(f"Failed to parse message {msg_id}: {e}")
            return None

    def _map_to_email(
        self,
        msg: email_lib.message.Message,
        msg_id: str,
        folder: str,
    ) -> Email:
        """Map IMAP message to Email model."""
        from src.extractors.html_parser import extract_plain_text

        # Parse From header
        from_header = msg.get("From", "")
        sender_email, sender_name = self._parse_email_header(from_header)
        sender_domain = sender_email.split("@")[1] if "@" in sender_email else "unknown"

        # Parse To header
        to_header = msg.get("To", "")
        recipient_email, recipient_name = self._parse_email_header(to_header)

        # Parse Date
        date_header = msg.get("Date", "")
        try:
            received_date = parsedate_to_datetime(date_header)
        except Exception:
            received_date = datetime.now()

        # Parse Subject
        subject = self._decode_header(msg.get("Subject", ""))

        # Extract body
        body_text, body_html = self._extract_body(msg)
        if body_html and not body_text:
            body_text = extract_plain_text(body_html)

        # Check for attachments
        has_attachments = False
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_disposition() == "attachment":
                    has_attachments = True
                    break

        return Email(
            id=msg_id,
            provider=ProviderType.IMAP,
            sender_email=sender_email,
            sender_name=sender_name,
            sender_domain=sender_domain,
            recipient_email=recipient_email if recipient_email else None,
            recipient_name=recipient_name,
            subject=subject,
            body_text=body_text or "",
            body_html=body_html,
            received_date=received_date,
            has_attachments=has_attachments,
            folder=folder,
            thread_id=msg.get("Message-ID"),
            in_reply_to=msg.get("In-Reply-To"),
        )

    def _parse_email_header(self, header: str) -> tuple[str, str]:
        """Parse email address from header."""
        if not header:
            return "unknown@unknown.com", ""

        # Decode if needed
        header = self._decode_header(header)

        # Handle format: "Name <email>"
        if "<" in header and ">" in header:
            name = header.split("<")[0].strip().strip('"')
            email_addr = header.split("<")[1].split(">")[0].strip()
            return email_addr, name

        return header.strip(), ""

    def _decode_header(self, header: str) -> str:
        """Decode MIME encoded header."""
        if not header:
            return ""

        try:
            decoded_parts = decode_header(header)
            result = []
            for data, charset in decoded_parts:
                if isinstance(data, bytes):
                    charset = charset or "utf-8"
                    try:
                        result.append(data.decode(charset, errors="replace"))
                    except (LookupError, UnicodeDecodeError):
                        result.append(data.decode("utf-8", errors="replace"))
                else:
                    result.append(data)
            return " ".join(result)
        except Exception:
            return str(header)

    def _extract_body(
        self,
        msg: email_lib.message.Message,
    ) -> tuple[str | None, str | None]:
        """Extract text and HTML body from message."""
        text_body = None
        html_body = None

        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = part.get_content_disposition()

                # Skip attachments
                if content_disposition == "attachment":
                    continue

                try:
                    payload = part.get_payload(decode=True)
                    if payload:
                        charset = part.get_content_charset() or "utf-8"
                        try:
                            decoded = payload.decode(charset, errors="replace")
                        except (LookupError, UnicodeDecodeError):
                            decoded = payload.decode("utf-8", errors="replace")

                        if content_type == "text/plain" and not text_body:
                            text_body = decoded
                        elif content_type == "text/html" and not html_body:
                            html_body = decoded
                except Exception:
                    continue
        else:
            # Simple message
            content_type = msg.get_content_type()
            try:
                payload = msg.get_payload(decode=True)
                if payload:
                    charset = msg.get_content_charset() or "utf-8"
                    try:
                        decoded = payload.decode(charset, errors="replace")
                    except (LookupError, UnicodeDecodeError):
                        decoded = payload.decode("utf-8", errors="replace")

                    if content_type == "text/plain":
                        text_body = decoded
                    elif content_type == "text/html":
                        html_body = decoded
            except Exception:
                pass

        return text_body, html_body

    async def get_total_count(self, folder: str = "INBOX") -> int | None:
        """Get total message count in folder."""
        if not self._client:
            return None

        try:
            response = await self._client.select(folder)
            if response.result == "OK":
                # Parse EXISTS response
                for line in response.lines:
                    if isinstance(line, bytes):
                        line = line.decode()
                    if "EXISTS" in str(line):
                        parts = str(line).split()
                        for i, part in enumerate(parts):
                            if part == "EXISTS" and i > 0:
                                return int(parts[i - 1])
            return None
        except Exception as e:
            logger.warning(f"Failed to get message count: {e}")
            return None

    async def list_folders(self) -> list[FolderInfo]:
        """List IMAP folders."""
        if not self._client:
            return []

        try:
            response = await self._client.list('""', "*")
            if response.result != "OK":
                return []

            folders = []
            for line in response.lines:
                if isinstance(line, bytes):
                    line = line.decode()
                # Parse folder name from LIST response
                # Format: (\Flags) "delimiter" "folder_name"
                if '"' in line:
                    parts = line.split('"')
                    if len(parts) >= 4:
                        folder_name = parts[-2]
                        folders.append(FolderInfo(
                            name=folder_name,
                            folder_type="folder",
                        ))

            return folders

        except Exception as e:
            logger.warning(f"Failed to list folders: {e}")
            return []

    async def close(self) -> None:
        """Close IMAP connection."""
        if self._client:
            try:
                await self._client.logout()
            except Exception:
                pass
            self._client = None
        self._authenticated = False
        logger.debug("IMAP provider closed")
