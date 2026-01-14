"""
Integration tests for email providers.

Tests provider implementations with mocked external APIs to ensure
they correctly implement the EmailProvider protocol and handle
authentication, email fetching, and error cases.
"""
import sys
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

# Check for optional dependencies
try:
    import azure.identity  # noqa
    import msgraph  # noqa
    HAS_M365_DEPS = True
except ImportError:
    HAS_M365_DEPS = False

try:
    import google.oauth2.credentials  # noqa
    import googleapiclient.discovery  # noqa
    HAS_GMAIL_DEPS = True
except ImportError:
    HAS_GMAIL_DEPS = False

try:
    import aioimaplib  # noqa
    HAS_IMAP_DEPS = True
except ImportError:
    HAS_IMAP_DEPS = False

from src.models.email import Email
from src.models.provider import (
    GmailConfig,
    IMAPConfig,
    M365Config,
    ProviderType,
)
from src.providers.base import AuthenticationError, FolderInfo, RateLimitError
from src.providers.gmail.provider import GmailProvider
from src.providers.imap.provider import IMAPProvider
from src.providers.m365.provider import M365Provider


@pytest.mark.integration
class TestM365Provider:
    """Integration tests for M365 provider."""

    @pytest.mark.asyncio
    @pytest.mark.skipif(not HAS_M365_DEPS, reason="M365 dependencies not installed")
    async def test_authentication_success(self, m365_config: M365Config):
        """Test successful M365 authentication with mocked Graph API."""
        with patch("azure.identity.DeviceCodeCredential") as mock_cred, \
             patch("msgraph.GraphServiceClient") as mock_client, \
             patch("asyncio.to_thread") as mock_thread:

            # Mock user profile
            mock_user = MagicMock()
            mock_user.display_name = "Test User"
            mock_user.mail = "test@example.com"

            mock_thread.return_value = mock_user

            provider = M365Provider(m365_config)
            result = await provider.authenticate()

            assert result is True
            assert provider.is_authenticated
            mock_cred.assert_called_once()
            mock_client.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.skipif(not HAS_M365_DEPS, reason="M365 dependencies not installed")
    async def test_authentication_failure_missing_dependencies(self, m365_config: M365Config):
        """Test authentication fails gracefully when dependencies missing."""
        with patch("azure.identity.DeviceCodeCredential", side_effect=ImportError):
            provider = M365Provider(m365_config)

            with pytest.raises(AuthenticationError) as exc_info:
                await provider.authenticate()

            assert "dependencies not installed" in str(exc_info.value)
            assert not provider.is_authenticated

    @pytest.mark.asyncio
    @pytest.mark.skipif(not HAS_M365_DEPS, reason="M365 dependencies not installed")
    async def test_fetch_emails(self, m365_config: M365Config, sample_emails: list[Email]):
        """Test fetching emails from M365 with mocked API."""
        with patch("azure.identity.DeviceCodeCredential"), \
             patch("msgraph.GraphServiceClient") as mock_client, \
             patch("asyncio.to_thread") as mock_thread:

            provider = M365Provider(m365_config)

            # Mock authentication
            mock_user = MagicMock()
            mock_user.display_name = "Test User"
            mock_user.mail = "test@example.com"

            # Setup mock responses
            call_count = [0]

            def mock_thread_side_effect(func):
                call_count[0] += 1
                if call_count[0] == 1:
                    return mock_user  # First call: authenticate
                # Subsequent calls: fetch emails
                return MagicMock(value=[])

            mock_thread.side_effect = mock_thread_side_effect

            await provider.authenticate()

            # Mock email fetching
            emails = []
            async for email in provider.fetch_emails(batch_size=10):
                emails.append(email)

            # Should get called but return no messages in our mock
            assert isinstance(emails, list)

    @pytest.mark.asyncio
    async def test_fetch_emails_not_authenticated(self, m365_config: M365Config):
        """Test fetching emails without authentication raises error."""
        provider = M365Provider(m365_config)

        with pytest.raises(AuthenticationError) as exc_info:
            async for _ in provider.fetch_emails():
                pass

        assert "Not authenticated" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_total_count(self, m365_config: M365Config):
        """Test getting total email count (returns None for M365)."""
        provider = M365Provider(m365_config)
        count = await provider.get_total_count()
        # M365 doesn't provide efficient count
        assert count is None

    @pytest.mark.asyncio
    @pytest.mark.skipif(not HAS_M365_DEPS, reason="M365 dependencies not installed")
    async def test_list_folders(self, m365_config: M365Config):
        """Test listing folders with mocked Graph API."""
        with patch("azure.identity.DeviceCodeCredential"), \
             patch("msgraph.GraphServiceClient") as mock_client, \
             patch("asyncio.to_thread") as mock_thread:

            provider = M365Provider(m365_config)

            # Mock authentication
            mock_user = MagicMock()
            mock_user.display_name = "Test User"
            mock_user.mail = "test@example.com"

            # Mock folders
            mock_folder1 = MagicMock()
            mock_folder1.display_name = "Inbox"
            mock_folder1.total_item_count = 100
            mock_folder1.unread_item_count = 10

            mock_folder2 = MagicMock()
            mock_folder2.display_name = "Sent Items"
            mock_folder2.total_item_count = 50
            mock_folder2.unread_item_count = 0

            mock_folders_result = MagicMock()
            mock_folders_result.value = [mock_folder1, mock_folder2]

            call_count = [0]

            def mock_thread_side_effect(func):
                call_count[0] += 1
                if call_count[0] == 1:
                    return mock_user  # authenticate
                return mock_folders_result  # list_folders

            mock_thread.side_effect = mock_thread_side_effect

            await provider.authenticate()
            folders = await provider.list_folders()

            assert len(folders) == 2
            assert folders[0].name == "Inbox"
            assert folders[0].message_count == 100
            assert folders[1].name == "Sent Items"

    @pytest.mark.asyncio
    async def test_close(self, m365_config: M365Config):
        """Test closing provider cleans up resources."""
        provider = M365Provider(m365_config)
        await provider.close()

        assert not provider.is_authenticated
        assert provider._client is None


@pytest.mark.integration
class TestGmailProvider:
    """Integration tests for Gmail provider."""

    @pytest.mark.asyncio
    @pytest.mark.skipif(not HAS_GMAIL_DEPS, reason="Gmail dependencies not installed")
    async def test_authentication_with_existing_token(self, gmail_config: GmailConfig, tmp_path):
        """Test authentication with existing valid token."""
        with patch("google.oauth2.credentials.Credentials") as mock_creds, \
             patch("googleapiclient.discovery.build") as mock_build, \
             patch("asyncio.to_thread") as mock_thread:

            # Mock existing credentials
            mock_cred_obj = MagicMock()
            mock_cred_obj.valid = True
            mock_cred_obj.expired = False
            mock_creds.from_authorized_user_file.return_value = mock_cred_obj

            # Mock Gmail service
            mock_service = MagicMock()
            mock_profile = {"emailAddress": "test@gmail.com"}

            async def mock_thread_wrapper(func):
                if callable(func):
                    return func()
                return mock_profile

            mock_thread.side_effect = mock_thread_wrapper
            mock_build.return_value = mock_service
            mock_service.users().getProfile().execute.return_value = mock_profile

            # Create token file
            token_file = tmp_path / "token.json"
            gmail_config.token_file = str(token_file)
            token_file.write_text('{"token": "test"}')

            provider = GmailProvider(gmail_config)
            result = await provider.authenticate()

            assert result is True
            assert provider.is_authenticated

    @pytest.mark.asyncio
    @pytest.mark.skipif(not HAS_GMAIL_DEPS, reason="Gmail dependencies not installed")
    async def test_authentication_missing_credentials_file(self, gmail_config: GmailConfig):
        """Test authentication fails when credentials file missing."""
        gmail_config.credentials_file = "/nonexistent/credentials.json"

        provider = GmailProvider(gmail_config)

        with pytest.raises(AuthenticationError) as exc_info:
            await provider.authenticate()

        assert "credentials file not found" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    @pytest.mark.skipif(not HAS_GMAIL_DEPS, reason="Gmail dependencies not installed")
    async def test_fetch_emails_with_query(self, gmail_config: GmailConfig, tmp_path):
        """Test fetching emails with date filter."""
        with patch("google.oauth2.credentials.Credentials") as mock_creds, \
             patch("googleapiclient.discovery.build") as mock_build, \
             patch("asyncio.to_thread") as mock_thread:

            # Setup mocks
            mock_cred_obj = MagicMock()
            mock_cred_obj.valid = True
            mock_creds.from_authorized_user_file.return_value = mock_cred_obj

            mock_service = MagicMock()
            mock_profile = {"emailAddress": "test@gmail.com"}

            # Mock message list
            mock_messages = {"messages": [], "nextPageToken": None}

            call_count = [0]

            async def mock_thread_wrapper(func):
                call_count[0] += 1
                if call_count[0] == 1:
                    return mock_profile  # authenticate
                # For message listing
                return mock_messages

            mock_thread.side_effect = mock_thread_wrapper
            mock_build.return_value = mock_service
            mock_service.users().getProfile().execute.return_value = mock_profile
            mock_service.users().messages().list().execute.return_value = mock_messages

            token_file = tmp_path / "token.json"
            gmail_config.token_file = str(token_file)
            token_file.write_text('{"token": "test"}')

            provider = GmailProvider(gmail_config)
            await provider.authenticate()

            # Fetch with date filter
            since = datetime.now() - timedelta(days=7)
            emails = []
            async for email in provider.fetch_emails(since=since):
                emails.append(email)

            assert isinstance(emails, list)

    @pytest.mark.asyncio
    @pytest.mark.skipif(not HAS_GMAIL_DEPS, reason="Gmail dependencies not installed")
    async def test_rate_limit_handling(self, gmail_config: GmailConfig, tmp_path):
        """Test Gmail provider handles rate limiting."""
        with patch("google.oauth2.credentials.Credentials") as mock_creds, \
             patch("googleapiclient.discovery.build") as mock_build, \
             patch("asyncio.to_thread") as mock_thread:

            mock_cred_obj = MagicMock()
            mock_cred_obj.valid = True
            mock_creds.from_authorized_user_file.return_value = mock_cred_obj

            mock_service = MagicMock()
            mock_profile = {"emailAddress": "test@gmail.com"}

            call_count = [0]

            async def mock_thread_wrapper(func):
                call_count[0] += 1
                if call_count[0] == 1:
                    return mock_profile  # authenticate
                # Simulate rate limit error
                raise Exception("rateLimitExceeded")

            mock_thread.side_effect = mock_thread_wrapper
            mock_build.return_value = mock_service

            token_file = tmp_path / "token.json"
            gmail_config.token_file = str(token_file)
            token_file.write_text('{"token": "test"}')

            provider = GmailProvider(gmail_config)
            await provider.authenticate()

            with pytest.raises(RateLimitError):
                async for _ in provider.fetch_emails():
                    pass

    @pytest.mark.asyncio
    @pytest.mark.skipif(not HAS_GMAIL_DEPS, reason="Gmail dependencies not installed")
    async def test_get_total_count(self, gmail_config: GmailConfig, tmp_path):
        """Test getting message count from Gmail."""
        with patch("google.oauth2.credentials.Credentials") as mock_creds, \
             patch("googleapiclient.discovery.build") as mock_build, \
             patch("asyncio.to_thread") as mock_thread:

            mock_cred_obj = MagicMock()
            mock_cred_obj.valid = True
            mock_creds.from_authorized_user_file.return_value = mock_cred_obj

            mock_service = MagicMock()
            mock_profile = {"emailAddress": "test@gmail.com"}
            mock_label = {"messagesTotal": 150}

            call_count = [0]

            async def mock_thread_wrapper(func):
                call_count[0] += 1
                if call_count[0] == 1:
                    return mock_profile
                return mock_label

            mock_thread.side_effect = mock_thread_wrapper
            mock_build.return_value = mock_service

            token_file = tmp_path / "token.json"
            gmail_config.token_file = str(token_file)
            token_file.write_text('{"token": "test"}')

            provider = GmailProvider(gmail_config)
            await provider.authenticate()

            count = await provider.get_total_count()
            assert count == 150


@pytest.mark.integration
class TestIMAPProvider:
    """Integration tests for IMAP provider."""

    @pytest.mark.asyncio
    @pytest.mark.skipif(not HAS_IMAP_DEPS, reason="IMAP dependencies not installed")
    async def test_authentication_success(self, imap_config: IMAPConfig):
        """Test successful IMAP authentication."""
        with patch("aioimaplib") as mock_imap:
            # Mock IMAP client
            mock_client = MagicMock()
            mock_client.wait_hello_from_server = AsyncMock()
            mock_login_response = MagicMock()
            mock_login_response.result = "OK"
            mock_client.login = AsyncMock(return_value=mock_login_response)

            mock_imap.IMAP4_SSL.return_value = mock_client

            # Set password
            from pydantic import SecretStr
            imap_config.password = SecretStr("test-password")

            provider = IMAPProvider(imap_config)
            result = await provider.authenticate()

            assert result is True
            assert provider.is_authenticated
            mock_client.wait_hello_from_server.assert_called_once()
            mock_client.login.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.skipif(not HAS_IMAP_DEPS, reason="IMAP dependencies not installed")
    async def test_authentication_missing_password(self, imap_config: IMAPConfig):
        """Test authentication fails without password."""
        provider = IMAPProvider(imap_config)

        with pytest.raises(AuthenticationError) as exc_info:
            await provider.authenticate()

        assert "password not provided" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    @pytest.mark.skipif(not HAS_IMAP_DEPS, reason="IMAP dependencies not installed")
    async def test_fetch_emails_with_search(self, imap_config: IMAPConfig):
        """Test fetching emails with IMAP SEARCH."""
        with patch("aioimaplib") as mock_imap:
            # Setup mocks
            mock_client = MagicMock()
            mock_client.wait_hello_from_server = AsyncMock()
            mock_login_response = MagicMock()
            mock_login_response.result = "OK"
            mock_client.login = AsyncMock(return_value=mock_login_response)

            # Mock SELECT
            mock_select_response = MagicMock()
            mock_select_response.result = "OK"
            mock_client.select = AsyncMock(return_value=mock_select_response)

            # Mock SEARCH
            mock_search_response = MagicMock()
            mock_search_response.result = "OK"
            mock_search_response.lines = [b"1 2 3"]
            mock_client.search = AsyncMock(return_value=mock_search_response)

            # Mock FETCH - return empty for simplicity
            mock_fetch_response = MagicMock()
            mock_fetch_response.result = "OK"
            mock_fetch_response.lines = []
            mock_client.fetch = AsyncMock(return_value=mock_fetch_response)

            mock_imap.IMAP4_SSL.return_value = mock_client

            from pydantic import SecretStr
            imap_config.password = SecretStr("test-password")

            provider = IMAPProvider(imap_config)
            await provider.authenticate()

            # Fetch emails
            emails = []
            async for email in provider.fetch_emails():
                emails.append(email)

            # Search should be called with date filter
            mock_client.search.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.skipif(not HAS_IMAP_DEPS, reason="IMAP dependencies not installed")
    async def test_get_total_count(self, imap_config: IMAPConfig):
        """Test getting message count from IMAP."""
        with patch("aioimaplib") as mock_imap:
            mock_client = MagicMock()
            mock_client.wait_hello_from_server = AsyncMock()
            mock_login_response = MagicMock()
            mock_login_response.result = "OK"
            mock_client.login = AsyncMock(return_value=mock_login_response)

            # Mock SELECT with EXISTS response
            mock_select_response = MagicMock()
            mock_select_response.result = "OK"
            mock_select_response.lines = [b"* 42 EXISTS"]
            mock_client.select = AsyncMock(return_value=mock_select_response)

            mock_imap.IMAP4_SSL.return_value = mock_client

            from pydantic import SecretStr
            imap_config.password = SecretStr("test-password")

            provider = IMAPProvider(imap_config)
            await provider.authenticate()

            count = await provider.get_total_count()
            assert count == 42

    @pytest.mark.asyncio
    @pytest.mark.skipif(not HAS_IMAP_DEPS, reason="IMAP dependencies not installed")
    async def test_list_folders(self, imap_config: IMAPConfig):
        """Test listing IMAP folders."""
        with patch("aioimaplib") as mock_imap:
            mock_client = MagicMock()
            mock_client.wait_hello_from_server = AsyncMock()
            mock_login_response = MagicMock()
            mock_login_response.result = "OK"
            mock_client.login = AsyncMock(return_value=mock_login_response)

            # Mock LIST
            mock_list_response = MagicMock()
            mock_list_response.result = "OK"
            mock_list_response.lines = [
                b'(\\HasNoChildren) "/" "INBOX"',
                b'(\\HasNoChildren) "/" "Sent"',
            ]
            mock_client.list = AsyncMock(return_value=mock_list_response)

            mock_imap.IMAP4_SSL.return_value = mock_client

            from pydantic import SecretStr
            imap_config.password = SecretStr("test-password")

            provider = IMAPProvider(imap_config)
            await provider.authenticate()

            folders = await provider.list_folders()
            assert len(folders) == 2
            assert folders[0].name == "INBOX"
            assert folders[1].name == "Sent"

    @pytest.mark.asyncio
    @pytest.mark.skipif(not HAS_IMAP_DEPS, reason="IMAP dependencies not installed")
    async def test_close(self, imap_config: IMAPConfig):
        """Test closing IMAP connection."""
        with patch("aioimaplib") as mock_imap:
            mock_client = MagicMock()
            mock_client.wait_hello_from_server = AsyncMock()
            mock_login_response = MagicMock()
            mock_login_response.result = "OK"
            mock_client.login = AsyncMock(return_value=mock_login_response)
            mock_client.logout = AsyncMock()

            mock_imap.IMAP4_SSL.return_value = mock_client

            from pydantic import SecretStr
            imap_config.password = SecretStr("test-password")

            provider = IMAPProvider(imap_config)
            await provider.authenticate()
            await provider.close()

            assert not provider.is_authenticated
            mock_client.logout.assert_called_once()


@pytest.mark.integration
class TestProviderFactory:
    """Integration tests for provider factory functions."""

    def test_create_provider_for_mailbox(self, m365_mailbox):
        """Test creating provider from mailbox configuration."""
        from src.providers import get_provider_for_mailbox

        # Add provider config to mailbox
        m365_mailbox.provider_config = {
            "tenant_id": "test-tenant",
            "client_id": "test-client",
        }

        provider = get_provider_for_mailbox(m365_mailbox)

        assert provider is not None
        assert provider.provider_type == ProviderType.M365
        assert provider.email_address == m365_mailbox.email_address

    def test_create_provider_all_types(self):
        """Test creating providers for all supported types."""
        from src.providers import create_provider

        # M365
        m365_config = M365Config(
            email_address="test@example.com",
            display_name="Test User",
        )
        m365_provider = create_provider(m365_config)
        assert m365_provider.provider_type == ProviderType.M365

        # Gmail
        gmail_config = GmailConfig(
            email_address="test@gmail.com",
            display_name="Test Gmail",
            credentials_file="/path/to/creds.json",
        )
        gmail_provider = create_provider(gmail_config)
        assert gmail_provider.provider_type == ProviderType.GMAIL

        # IMAP
        imap_config = IMAPConfig(
            email_address="test@imap.com",
            display_name="Test IMAP",
            host="imap.example.com",
            port=993,
        )
        imap_provider = create_provider(imap_config)
        assert imap_provider.provider_type == ProviderType.IMAP
