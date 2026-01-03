"""
Microsoft 365 email provider implementation.

Uses Microsoft Graph SDK for email access with OAuth2 authentication.
Supports both personal Microsoft accounts and corporate M365 accounts.
"""
import asyncio
from collections.abc import AsyncIterator
from datetime import datetime

from src.models.email import Email
from src.models.provider import M365Config, ProviderType
from src.providers.base import (
    AuthenticationError,
    BaseEmailProvider,
    FolderInfo,
    RateLimitError,
)
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Default Azure AD app registration for device code flow
# Users can provide their own client_id for custom apps
DEFAULT_CLIENT_ID = "14d82eec-204b-4c2f-b7e8-296a70dab67e"  # Microsoft Graph CLI


class M365Provider(BaseEmailProvider):
    """
    Microsoft 365 email provider using Microsoft Graph API.

    Supports:
    - Personal Microsoft accounts (Outlook.com, Hotmail, Live)
    - Corporate M365 accounts
    - Device code authentication flow
    """

    SCOPES = [
        "https://graph.microsoft.com/Mail.Read",
        "https://graph.microsoft.com/User.Read",
    ]

    def __init__(self, config: M365Config):
        super().__init__(config.email_address)
        self.config = config
        self._client = None
        self._credential = None

    @property
    def provider_type(self) -> ProviderType:
        return ProviderType.M365

    async def authenticate(self) -> bool:
        """
        Authenticate using device code flow.

        This flow works for both personal and corporate accounts
        and doesn't require a redirect URI.

        Returns:
            True if authentication successful.

        Raises:
            AuthenticationError: If authentication fails.
        """
        try:
            # Lazy imports to avoid dependency issues if not installed
            from azure.identity import DeviceCodeCredential
            from msgraph import GraphServiceClient

            client_id = self.config.client_id or DEFAULT_CLIENT_ID
            tenant_id = self.config.tenant_id or "consumers"  # "consumers" for personal accounts

            logger.info(f"Starting M365 authentication for {self.email_address}")
            logger.info(f"Tenant: {tenant_id}, Client ID: {client_id[:8]}...")

            # Create credential with device code flow
            self._credential = DeviceCodeCredential(
                client_id=client_id,
                tenant_id=tenant_id,
                # Callback to display device code to user
                prompt_callback=self._device_code_callback,
            )

            # Create Graph client
            self._client = GraphServiceClient(
                credentials=self._credential,
                scopes=self.SCOPES,
            )

            # Verify authentication by fetching user profile
            user = await asyncio.to_thread(
                lambda: self._client.me.get()
            )

            if user:
                self._authenticated = True
                logger.info(f"Authenticated as: {user.display_name} ({user.mail or user.user_principal_name})")
                return True

            return False

        except ImportError as e:
            raise AuthenticationError(
                f"M365 dependencies not installed. Run: pip install msgraph-sdk azure-identity. Error: {e}",
                provider=ProviderType.M365,
                recoverable=False,
            )
        except Exception as e:
            logger.error(f"M365 authentication failed: {e}")
            raise AuthenticationError(
                f"M365 authentication failed: {e}",
                provider=ProviderType.M365,
                recoverable=True,
            )

    def _device_code_callback(self, verification_uri: str, user_code: str, expires_on: datetime) -> None:
        """Display device code authentication instructions to user."""
        print("\n" + "=" * 60)
        print("M365 Authentication Required")
        print("=" * 60)
        print(f"\n1. Open a browser and go to: {verification_uri}")
        print(f"2. Enter the code: {user_code}")
        print(f"3. Sign in with your Microsoft account")
        print(f"\nCode expires at: {expires_on}")
        print("=" * 60 + "\n")

    async def fetch_emails(
        self,
        batch_size: int = 100,
        since: datetime | None = None,
        folder: str = "INBOX",
        include_body: bool = True,
    ) -> AsyncIterator[Email]:
        """
        Fetch emails from M365 mailbox using Graph API.

        Args:
            batch_size: Emails per request (max 1000).
            since: Only fetch emails after this date.
            folder: Folder name (INBOX, Drafts, SentItems, etc.)
            include_body: Include full body content.

        Yields:
            Email objects.
        """
        if not self._client:
            raise AuthenticationError(
                "Not authenticated. Call authenticate() first.",
                provider=ProviderType.M365,
            )

        # Map common folder names to M365 well-known folder IDs
        folder_map = {
            "INBOX": "inbox",
            "SENT": "sentitems",
            "DRAFTS": "drafts",
            "TRASH": "deleteditems",
            "JUNK": "junkemail",
            "ARCHIVE": "archive",
        }
        folder_id = folder_map.get(folder.upper(), folder)

        # Build select fields
        select_fields = [
            "id",
            "subject",
            "from",
            "toRecipients",
            "receivedDateTime",
            "hasAttachments",
            "importance",
            "isRead",
            "conversationId",
            "categories",
        ]
        if include_body:
            select_fields.append("body")

        # Build filter for date
        filter_query = None
        if since:
            filter_query = f"receivedDateTime ge {since.isoformat()}"

        try:
            # Use pagination to fetch all emails
            skip = 0
            while True:
                # Fetch batch
                messages = await self._fetch_message_batch(
                    folder_id=folder_id,
                    select=select_fields,
                    filter_query=filter_query,
                    top=batch_size,
                    skip=skip,
                )

                if not messages:
                    break

                for msg in messages:
                    try:
                        email = self._map_to_email(msg, folder)
                        yield email
                    except Exception as e:
                        logger.warning(f"Failed to map message {msg.get('id', 'unknown')}: {e}")
                        continue

                # Check if we got fewer than requested (end of results)
                if len(messages) < batch_size:
                    break

                skip += batch_size

        except Exception as e:
            if "throttl" in str(e).lower() or "rate" in str(e).lower():
                raise RateLimitError(f"Rate limited by M365: {e}", retry_after=60)
            raise

    async def _fetch_message_batch(
        self,
        folder_id: str,
        select: list[str],
        filter_query: str | None,
        top: int,
        skip: int,
    ) -> list[dict]:
        """Fetch a batch of messages using Graph API."""
        try:
            # Build the request using Graph SDK
            request = self._client.me.mail_folders.by_mail_folder_id(folder_id).messages

            # Execute with parameters
            # Note: The actual API call structure depends on msgraph-sdk version
            result = await asyncio.to_thread(
                lambda: request.get(
                    request_configuration=lambda config: self._configure_request(
                        config, select, filter_query, top, skip
                    )
                )
            )

            if result and result.value:
                return [self._message_to_dict(m) for m in result.value]
            return []

        except Exception as e:
            logger.error(f"Failed to fetch messages: {e}")
            raise

    def _configure_request(self, config, select, filter_query, top, skip):
        """Configure request parameters."""
        config.query_parameters.select = select
        config.query_parameters.top = top
        config.query_parameters.skip = skip
        config.query_parameters.orderby = ["receivedDateTime desc"]
        if filter_query:
            config.query_parameters.filter = filter_query

    def _message_to_dict(self, message) -> dict:
        """Convert Graph SDK message object to dict."""
        return {
            "id": message.id,
            "subject": message.subject or "",
            "from": {
                "emailAddress": {
                    "address": message.from_.email_address.address if message.from_ else "",
                    "name": message.from_.email_address.name if message.from_ else "",
                }
            } if message.from_ else {},
            "toRecipients": [
                {
                    "emailAddress": {
                        "address": r.email_address.address if r.email_address else "",
                        "name": r.email_address.name if r.email_address else "",
                    }
                }
                for r in (message.to_recipients or [])
            ],
            "receivedDateTime": message.received_date_time,
            "hasAttachments": message.has_attachments or False,
            "importance": message.importance.value if message.importance else "normal",
            "isRead": message.is_read or False,
            "conversationId": message.conversation_id,
            "categories": message.categories or [],
            "body": {
                "content": message.body.content if message.body else "",
                "contentType": message.body.content_type.value if message.body and message.body.content_type else "text",
            } if message.body else {},
        }

    def _map_to_email(self, msg: dict, folder: str) -> Email:
        """Map Graph API message to Email model."""
        from src.extractors.html_parser import extract_plain_text

        # Extract sender info
        from_data = msg.get("from", {}).get("emailAddress", {})
        sender_email = from_data.get("address", "unknown@unknown.com")
        sender_name = from_data.get("name", "")
        sender_domain = sender_email.split("@")[1] if "@" in sender_email else "unknown"

        # Extract recipient info
        to_recipients = msg.get("toRecipients", [])
        recipient_email = None
        recipient_name = ""
        if to_recipients:
            to_data = to_recipients[0].get("emailAddress", {})
            recipient_email = to_data.get("address")
            recipient_name = to_data.get("name", "")

        # Extract body
        body_data = msg.get("body", {})
        body_content = body_data.get("content", "")
        body_type = body_data.get("contentType", "text")

        if body_type.lower() == "html":
            body_text = extract_plain_text(body_content)
            body_html = body_content
        else:
            body_text = body_content
            body_html = None

        # Parse received date
        received_str = msg.get("receivedDateTime", "")
        if isinstance(received_str, str):
            received_date = datetime.fromisoformat(received_str.replace("Z", "+00:00"))
        else:
            received_date = received_str

        return Email(
            id=msg.get("id", ""),
            provider=ProviderType.M365,
            sender_email=sender_email,
            sender_name=sender_name,
            sender_domain=sender_domain,
            recipient_email=recipient_email,
            recipient_name=recipient_name,
            subject=msg.get("subject", ""),
            body_text=body_text,
            body_html=body_html,
            received_date=received_date,
            has_attachments=msg.get("hasAttachments", False),
            folder=folder,
            labels=msg.get("categories", []),
            is_read=msg.get("isRead", True),
            importance=msg.get("importance", "normal"),
            thread_id=msg.get("conversationId"),
        )

    async def get_total_count(self, folder: str = "INBOX") -> int | None:
        """
        Get total message count in folder.

        Note: Graph API doesn't provide efficient count, so we
        return None to indicate count is unknown.
        """
        # M365 Graph API doesn't provide efficient message count
        # We'd need to fetch all message IDs which is expensive
        return None

    async def list_folders(self) -> list[FolderInfo]:
        """List mail folders."""
        if not self._client:
            return []

        try:
            result = await asyncio.to_thread(
                lambda: self._client.me.mail_folders.get()
            )

            folders = []
            if result and result.value:
                for f in result.value:
                    folders.append(FolderInfo(
                        name=f.display_name,
                        message_count=f.total_item_count,
                        unread_count=f.unread_item_count,
                        folder_type="folder",
                    ))

            return folders

        except Exception as e:
            logger.warning(f"Failed to list folders: {e}")
            return []

    async def close(self) -> None:
        """Clean up resources."""
        self._client = None
        self._credential = None
        self._authenticated = False
        logger.debug("M365 provider closed")
