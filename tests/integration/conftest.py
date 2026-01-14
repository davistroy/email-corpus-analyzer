"""
Shared fixtures for integration tests.

Provides common fixtures for mocking external APIs and setting up test data.
"""
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import AsyncIterator
from unittest.mock import AsyncMock, MagicMock, Mock
from uuid import uuid4

import pytest

from src.models.email import Email
from src.models.mailbox import Mailbox, MailboxStatus
from src.models.provider import (
    GmailConfig,
    IMAPConfig,
    M365Config,
    ProviderType,
)
from src.providers.base import FolderInfo


# ===== Test Data =====


@pytest.fixture
def sample_emails() -> list[Email]:
    """Generate sample emails for testing."""
    base_date = datetime.now() - timedelta(days=30)

    emails = []
    for i in range(10):
        email = Email(
            id=f"test-email-{i}",
            provider=ProviderType.M365,
            sender_email=f"sender{i % 3}@example.com",
            sender_name=f"Sender {i % 3}",
            sender_domain="example.com",
            recipient_email="user@test.com",
            recipient_name="Test User",
            subject=f"Test Email {i}",
            body_text=f"This is test email number {i} with some content.",
            body_html=f"<p>This is test email number {i} with some content.</p>",
            received_date=base_date + timedelta(days=i),
            has_attachments=(i % 3 == 0),
            folder="INBOX",
            is_read=(i % 2 == 0),
        )
        emails.append(email)

    return emails


@pytest.fixture
def m365_mailbox() -> Mailbox:
    """Create a test M365 mailbox."""
    return Mailbox(
        id=uuid4(),
        name="Test M365 Mailbox",
        provider=ProviderType.M365,
        email_address="test@example.com",
        status=MailboxStatus.ACTIVE,
    )


@pytest.fixture
def gmail_mailbox() -> Mailbox:
    """Create a test Gmail mailbox."""
    return Mailbox(
        id=uuid4(),
        name="Test Gmail Mailbox",
        provider=ProviderType.GMAIL,
        email_address="test@gmail.com",
        status=MailboxStatus.ACTIVE,
    )


@pytest.fixture
def imap_mailbox() -> Mailbox:
    """Create a test IMAP mailbox."""
    return Mailbox(
        id=uuid4(),
        name="Test IMAP Mailbox",
        provider=ProviderType.IMAP,
        email_address="test@imap.example.com",
        status=MailboxStatus.ACTIVE,
    )


# ===== Provider Configs =====


@pytest.fixture
def m365_config() -> M365Config:
    """Create test M365 configuration."""
    return M365Config(
        display_name="Test M365",
        email_address="test@example.com",
        tenant_id="test-tenant",
        client_id="test-client",
    )


@pytest.fixture
def gmail_config(tmp_path: Path) -> GmailConfig:
    """Create test Gmail configuration."""
    credentials_file = tmp_path / "credentials.json"
    credentials_file.write_text('{"installed": {"client_id": "test"}}')

    return GmailConfig(
        display_name="Test Gmail",
        email_address="test@gmail.com",
        credentials_file=str(credentials_file),
    )


@pytest.fixture
def imap_config() -> IMAPConfig:
    """Create test IMAP configuration."""
    return IMAPConfig(
        display_name="Test IMAP",
        email_address="test@imap.example.com",
        host="imap.example.com",
        port=993,
        use_ssl=True,
    )


# ===== Mocked Providers =====


@pytest.fixture
def mock_m365_provider(sample_emails: list[Email]):
    """Create a mocked M365 provider."""
    from src.providers.m365.provider import M365Provider

    provider = Mock(spec=M365Provider)
    provider.provider_type = ProviderType.M365
    provider.email_address = "test@example.com"
    provider.is_authenticated = False

    # Mock authenticate
    async def mock_authenticate():
        provider.is_authenticated = True
        return True

    provider.authenticate = AsyncMock(side_effect=mock_authenticate)

    # Mock fetch_emails
    async def mock_fetch_emails(*args, **kwargs):
        for email in sample_emails:
            yield email

    provider.fetch_emails = mock_fetch_emails

    # Mock other methods
    provider.get_total_count = AsyncMock(return_value=len(sample_emails))
    provider.list_folders = AsyncMock(return_value=[
        FolderInfo(name="INBOX", message_count=10),
        FolderInfo(name="Sent Items", message_count=5),
    ])
    provider.close = AsyncMock()

    return provider


@pytest.fixture
def mock_gmail_provider(sample_emails: list[Email]):
    """Create a mocked Gmail provider."""
    from src.providers.gmail.provider import GmailProvider

    provider = Mock(spec=GmailProvider)
    provider.provider_type = ProviderType.GMAIL
    provider.email_address = "test@gmail.com"
    provider.is_authenticated = False

    # Mock authenticate
    async def mock_authenticate():
        provider.is_authenticated = True
        return True

    provider.authenticate = AsyncMock(side_effect=mock_authenticate)

    # Mock fetch_emails
    async def mock_fetch_emails(*args, **kwargs):
        for email in sample_emails:
            email.provider = ProviderType.GMAIL
            yield email

    provider.fetch_emails = mock_fetch_emails

    # Mock other methods
    provider.get_total_count = AsyncMock(return_value=len(sample_emails))
    provider.list_folders = AsyncMock(return_value=[
        FolderInfo(name="INBOX", message_count=10, folder_type="label"),
        FolderInfo(name="SENT", message_count=5, folder_type="label"),
    ])
    provider.close = AsyncMock()

    return provider


@pytest.fixture
def mock_imap_provider(sample_emails: list[Email]):
    """Create a mocked IMAP provider."""
    from src.providers.imap.provider import IMAPProvider

    provider = Mock(spec=IMAPProvider)
    provider.provider_type = ProviderType.IMAP
    provider.email_address = "test@imap.example.com"
    provider.is_authenticated = False

    # Mock authenticate
    async def mock_authenticate():
        provider.is_authenticated = True
        return True

    provider.authenticate = AsyncMock(side_effect=mock_authenticate)

    # Mock fetch_emails
    async def mock_fetch_emails(*args, **kwargs):
        for email in sample_emails:
            email.provider = ProviderType.IMAP
            yield email

    provider.fetch_emails = mock_fetch_emails

    # Mock other methods
    provider.get_total_count = AsyncMock(return_value=len(sample_emails))
    provider.list_folders = AsyncMock(return_value=[
        FolderInfo(name="INBOX", message_count=10),
        FolderInfo(name="Sent", message_count=5),
    ])
    provider.close = AsyncMock()

    return provider


# ===== Mocked API Clients =====


@pytest.fixture
def mock_anthropic_client():
    """Create a mocked Anthropic client for LLM tests."""
    client = MagicMock()

    # Mock message response
    mock_response = MagicMock()
    mock_tool_use = MagicMock()
    mock_tool_use.type = "tool_use"
    mock_tool_use.name = "structured_response"
    mock_tool_use.input = {
        "name": "Test Category",
        "description": "A test category for emails",
        "confidence": 0.85,
        "reasoning": "This is a test",
    }
    mock_response.content = [mock_tool_use]

    client.messages.create.return_value = mock_response

    return client


@pytest.fixture
def mock_graph_client():
    """Create a mocked Microsoft Graph client."""
    client = MagicMock()

    # Mock user profile
    mock_user = MagicMock()
    mock_user.display_name = "Test User"
    mock_user.mail = "test@example.com"
    mock_user.user_principal_name = "test@example.com"

    client.me.get.return_value = mock_user

    # Mock messages
    mock_messages_result = MagicMock()
    mock_messages_result.value = []

    client.me.mail_folders.by_mail_folder_id.return_value.messages.get.return_value = (
        mock_messages_result
    )

    return client


@pytest.fixture
def mock_gmail_service():
    """Create a mocked Gmail API service."""
    service = MagicMock()

    # Mock profile
    profile_result = {"emailAddress": "test@gmail.com"}
    service.users().getProfile().execute.return_value = profile_result

    # Mock messages list
    messages_result = {"messages": [], "nextPageToken": None}
    service.users().messages().list().execute.return_value = messages_result

    return service


# ===== Temporary Directories =====


@pytest.fixture
def test_data_dir(tmp_path: Path) -> Path:
    """Create a temporary data directory for tests."""
    data_dir = tmp_path / "test_data"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "data").mkdir(exist_ok=True)
    (data_dir / "credentials").mkdir(exist_ok=True)
    return data_dir


@pytest.fixture
def test_config_dir(tmp_path: Path) -> Path:
    """Create a temporary config directory for tests."""
    config_dir = tmp_path / "test_config"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


# ===== Async Helpers =====


@pytest.fixture
def event_loop():
    """Create an event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ===== Markers =====


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
    config.addinivalue_line(
        "markers", "requires_api: mark test as requiring external API access"
    )
