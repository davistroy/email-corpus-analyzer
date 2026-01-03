"""
Tests for mailbox registry.
"""
import pytest
from pathlib import Path
from uuid import uuid4

from src.mailbox.registry import MailboxRegistry
from src.models.mailbox import Mailbox, MailboxStatus
from src.models.provider import ProviderType


class TestMailboxRegistry:
    """Test mailbox registry operations."""

    @pytest.fixture
    def registry(self, tmp_path):
        """Create a registry with temporary storage."""
        return MailboxRegistry(config_dir=tmp_path)

    @pytest.fixture
    def sample_mailbox(self):
        """Create a sample mailbox."""
        return Mailbox(
            name="Test Mailbox",
            provider=ProviderType.M365,
            email_address="test@example.com",
        )

    def test_add_mailbox(self, registry, sample_mailbox):
        """Test adding a mailbox."""
        registry.add_mailbox(sample_mailbox)

        # Verify it was added
        retrieved = registry.get_mailbox(sample_mailbox.id)
        assert retrieved is not None
        assert retrieved.name == sample_mailbox.name
        assert retrieved.email_address == sample_mailbox.email_address

    def test_add_duplicate_mailbox_fails(self, registry, sample_mailbox):
        """Test that adding duplicate mailbox raises error."""
        registry.add_mailbox(sample_mailbox)

        with pytest.raises(ValueError):
            registry.add_mailbox(sample_mailbox)

    def test_update_mailbox(self, registry, sample_mailbox):
        """Test updating a mailbox."""
        registry.add_mailbox(sample_mailbox)

        # Update status
        sample_mailbox.set_active()
        registry.update_mailbox(sample_mailbox)

        # Verify update
        retrieved = registry.get_mailbox(sample_mailbox.id)
        assert retrieved.status == MailboxStatus.ACTIVE

    def test_update_nonexistent_mailbox_fails(self, registry, sample_mailbox):
        """Test that updating nonexistent mailbox raises error."""
        with pytest.raises(KeyError):
            registry.update_mailbox(sample_mailbox)

    def test_get_by_name(self, registry, sample_mailbox):
        """Test finding mailbox by name."""
        registry.add_mailbox(sample_mailbox)

        # Case-insensitive search
        found = registry.get_by_name("test mailbox")
        assert found is not None
        assert found.id == sample_mailbox.id

        # Non-existent name
        not_found = registry.get_by_name("nonexistent")
        assert not_found is None

    def test_get_by_email(self, registry, sample_mailbox):
        """Test finding mailbox by email."""
        registry.add_mailbox(sample_mailbox)

        found = registry.get_by_email("test@example.com")
        assert found is not None
        assert found.id == sample_mailbox.id

        # Case-insensitive
        found_upper = registry.get_by_email("TEST@EXAMPLE.COM")
        assert found_upper is not None

    def test_list_mailboxes(self, registry):
        """Test listing all mailboxes."""
        # Add multiple mailboxes
        for i in range(3):
            mailbox = Mailbox(
                name=f"Mailbox {i}",
                provider=ProviderType.M365,
                email_address=f"test{i}@example.com",
            )
            registry.add_mailbox(mailbox)

        all_mailboxes = registry.list_mailboxes()
        assert len(all_mailboxes) == 3

    def test_list_mailboxes_with_filter(self, registry):
        """Test listing mailboxes with filters."""
        # Add mailboxes with different providers
        m365 = Mailbox(
            name="M365",
            provider=ProviderType.M365,
            email_address="m365@example.com",
        )
        m365.set_active()
        registry.add_mailbox(m365)

        gmail = Mailbox(
            name="Gmail",
            provider=ProviderType.GMAIL,
            email_address="gmail@example.com",
            provider_config={"credentials_file": "/path/to/creds.json"},
        )
        registry.add_mailbox(gmail)

        # Filter by provider
        m365_only = registry.list_mailboxes(provider=ProviderType.M365)
        assert len(m365_only) == 1
        assert m365_only[0].provider == ProviderType.M365

        # Filter by status
        active_only = registry.list_mailboxes(status=MailboxStatus.ACTIVE)
        assert len(active_only) == 1

    def test_remove_mailbox(self, registry, sample_mailbox):
        """Test removing a mailbox."""
        registry.add_mailbox(sample_mailbox)

        # Remove it
        removed = registry.remove_mailbox(sample_mailbox.id)
        assert removed is True

        # Verify it's gone
        assert registry.get_mailbox(sample_mailbox.id) is None

        # Remove nonexistent
        not_removed = registry.remove_mailbox(uuid4())
        assert not_removed is False

    def test_clear_all(self, registry):
        """Test clearing all mailboxes."""
        # Add some mailboxes
        for i in range(5):
            registry.add_mailbox(Mailbox(
                name=f"Mailbox {i}",
                provider=ProviderType.IMAP,
                email_address=f"test{i}@example.com",
                provider_config={"host": "mail.example.com"},
            ))

        count = registry.clear_all()
        assert count == 5
        assert registry.count == 0

    def test_persistence(self, tmp_path):
        """Test that registry persists across instances."""
        # Create and populate registry
        registry1 = MailboxRegistry(config_dir=tmp_path)
        mailbox = Mailbox(
            name="Persistent",
            provider=ProviderType.M365,
            email_address="persistent@example.com",
        )
        registry1.add_mailbox(mailbox)

        # Create new instance with same path
        registry2 = MailboxRegistry(config_dir=tmp_path)
        retrieved = registry2.get_mailbox(mailbox.id)

        assert retrieved is not None
        assert retrieved.name == "Persistent"
