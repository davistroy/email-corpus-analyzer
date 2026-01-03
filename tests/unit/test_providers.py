"""
Tests for email provider abstraction layer.
"""
import pytest
from uuid import uuid4

from src.models.provider import (
    ProviderType,
    M365Config,
    GmailConfig,
    IMAPConfig,
    create_provider_config,
)
from src.models.mailbox import Mailbox, MailboxStatus, ExtractionState, AnalysisState
from src.providers.base import BaseEmailProvider, FolderInfo


class TestProviderModels:
    """Test provider configuration models."""

    def test_m365_config_basic(self):
        """Test M365 config with minimal fields."""
        config = M365Config(
            display_name="Work Email",
            email_address="user@company.com",
        )
        assert config.provider_type == ProviderType.M365
        assert config.tenant_id is None
        assert config.client_id is None

    def test_m365_config_corporate(self):
        """Test M365 config with corporate tenant."""
        config = M365Config(
            display_name="Corporate",
            email_address="user@corp.com",
            tenant_id="tenant-123",
            client_id="client-456",
        )
        assert config.tenant_id == "tenant-123"
        assert config.client_id == "client-456"

    def test_gmail_config(self):
        """Test Gmail config."""
        config = GmailConfig(
            display_name="Personal Gmail",
            email_address="user@gmail.com",
            credentials_file="/path/to/credentials.json",
        )
        assert config.provider_type == ProviderType.GMAIL
        assert config.credentials_file == "/path/to/credentials.json"

    def test_imap_config(self):
        """Test IMAP config."""
        config = IMAPConfig(
            display_name="Legacy Mail",
            email_address="user@example.com",
            host="mail.example.com",
            port=993,
            use_ssl=True,
        )
        assert config.provider_type == ProviderType.IMAP
        assert config.host == "mail.example.com"
        assert config.port == 993

    def test_create_provider_config_factory(self):
        """Test provider config factory function."""
        config = create_provider_config(
            ProviderType.M365,
            display_name="Test",
            email_address="test@example.com",
        )
        assert isinstance(config, M365Config)
        assert config.display_name == "Test"


class TestMailboxModel:
    """Test mailbox model."""

    def test_mailbox_creation(self):
        """Test basic mailbox creation."""
        mailbox = Mailbox(
            name="Test Mailbox",
            provider=ProviderType.M365,
            email_address="test@example.com",
        )
        assert mailbox.name == "Test Mailbox"
        assert mailbox.status == MailboxStatus.PENDING_AUTH
        assert mailbox.extraction.total_emails == 0

    def test_mailbox_paths(self, tmp_path):
        """Test mailbox path generation."""
        mailbox = Mailbox(
            name="Test",
            provider=ProviderType.GMAIL,
            email_address="test@gmail.com",
        )

        data_dir = mailbox.get_data_dir(tmp_path)
        assert str(mailbox.id) in str(data_dir)

        corpus_path = mailbox.get_corpus_path(tmp_path)
        assert corpus_path.name == "corpus.json"

    def test_mailbox_state_updates(self):
        """Test mailbox state update methods."""
        mailbox = Mailbox(
            name="Test",
            provider=ProviderType.IMAP,
            email_address="test@example.com",
        )

        # Test extraction complete
        mailbox.mark_extraction_complete(100)
        assert mailbox.extraction.total_emails == 100
        assert mailbox.extraction.is_complete

        # Test analysis complete
        mailbox.mark_analysis_complete(5, 10)
        assert mailbox.analysis.cluster_count == 5
        assert mailbox.analysis.category_count == 10

        # Test error state
        mailbox.set_error("Connection failed")
        assert mailbox.status == MailboxStatus.ERROR
        assert mailbox.status_message == "Connection failed"

        # Test active state
        mailbox.set_active()
        assert mailbox.status == MailboxStatus.ACTIVE


class TestFolderInfo:
    """Test folder info model."""

    def test_folder_info_basic(self):
        """Test basic folder info."""
        folder = FolderInfo(name="INBOX")
        assert folder.name == "INBOX"
        assert folder.message_count is None
        assert folder.folder_type == "folder"

    def test_folder_info_with_counts(self):
        """Test folder info with message counts."""
        folder = FolderInfo(
            name="Inbox",
            message_count=150,
            unread_count=10,
            folder_type="label",
        )
        assert folder.message_count == 150
        assert folder.unread_count == 10
        assert folder.folder_type == "label"
