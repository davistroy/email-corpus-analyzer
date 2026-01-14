"""
Integration tests for mailbox management.

Tests the MailboxRegistry and MailboxManager together to ensure
proper persistence, state management, and orchestration of operations.
"""
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.mailbox.manager import MailboxManager
from src.mailbox.registry import MailboxRegistry
from src.models.corpus import Corpus
from src.models.mailbox import Mailbox, MailboxStatus
from src.models.provider import ProviderType
from src.providers.base import AuthenticationError


@pytest.mark.integration
class TestMailboxRegistry:
    """Integration tests for mailbox registry persistence."""

    def test_add_and_retrieve_mailbox(self, test_config_dir: Path):
        """Test adding and retrieving mailbox."""
        registry = MailboxRegistry(test_config_dir)

        mailbox = Mailbox(
            name="Test Mailbox",
            provider=ProviderType.M365,
            email_address="test@example.com",
        )

        registry.add_mailbox(mailbox)

        # Retrieve by ID
        retrieved = registry.get_mailbox(mailbox.id)
        assert retrieved is not None
        assert retrieved.id == mailbox.id
        assert retrieved.name == mailbox.name
        assert retrieved.email_address == mailbox.email_address

    def test_add_duplicate_mailbox_fails(self, test_config_dir: Path):
        """Test adding mailbox with duplicate ID fails."""
        registry = MailboxRegistry(test_config_dir)

        mailbox = Mailbox(
            name="Test Mailbox",
            provider=ProviderType.M365,
            email_address="test@example.com",
        )

        registry.add_mailbox(mailbox)

        with pytest.raises(ValueError, match="already exists"):
            registry.add_mailbox(mailbox)

    def test_update_mailbox(self, test_config_dir: Path):
        """Test updating existing mailbox."""
        registry = MailboxRegistry(test_config_dir)

        mailbox = Mailbox(
            name="Original Name",
            provider=ProviderType.GMAIL,
            email_address="test@gmail.com",
        )

        registry.add_mailbox(mailbox)

        # Update mailbox
        mailbox.name = "Updated Name"
        mailbox.set_active()
        registry.update_mailbox(mailbox)

        # Verify update persisted
        retrieved = registry.get_mailbox(mailbox.id)
        assert retrieved.name == "Updated Name"
        assert retrieved.status == MailboxStatus.ACTIVE

    def test_update_nonexistent_mailbox_fails(self, test_config_dir: Path):
        """Test updating nonexistent mailbox fails."""
        registry = MailboxRegistry(test_config_dir)

        mailbox = Mailbox(
            id=uuid4(),
            name="Nonexistent",
            provider=ProviderType.IMAP,
            email_address="test@imap.com",
        )

        with pytest.raises(KeyError, match="not found"):
            registry.update_mailbox(mailbox)

    def test_get_by_name(self, test_config_dir: Path):
        """Test finding mailbox by name."""
        registry = MailboxRegistry(test_config_dir)

        mailbox = Mailbox(
            name="Work Email",
            provider=ProviderType.M365,
            email_address="work@company.com",
        )

        registry.add_mailbox(mailbox)

        # Find by exact name
        found = registry.get_by_name("Work Email")
        assert found is not None
        assert found.id == mailbox.id

        # Case insensitive
        found = registry.get_by_name("work email")
        assert found is not None

    def test_get_by_email(self, test_config_dir: Path):
        """Test finding mailbox by email address."""
        registry = MailboxRegistry(test_config_dir)

        mailbox = Mailbox(
            name="Personal",
            provider=ProviderType.GMAIL,
            email_address="personal@gmail.com",
        )

        registry.add_mailbox(mailbox)

        found = registry.get_by_email("personal@gmail.com")
        assert found is not None
        assert found.id == mailbox.id

        # Case insensitive
        found = registry.get_by_email("PERSONAL@GMAIL.COM")
        assert found is not None

    def test_list_mailboxes(self, test_config_dir: Path):
        """Test listing all mailboxes."""
        registry = MailboxRegistry(test_config_dir)

        # Add multiple mailboxes
        mailboxes = [
            Mailbox(name="M365", provider=ProviderType.M365, email_address="m365@test.com"),
            Mailbox(name="Gmail", provider=ProviderType.GMAIL, email_address="gmail@test.com"),
            Mailbox(name="IMAP", provider=ProviderType.IMAP, email_address="imap@test.com"),
        ]

        for mb in mailboxes:
            registry.add_mailbox(mb)

        # List all
        all_mailboxes = registry.list_mailboxes()
        assert len(all_mailboxes) == 3

        # Sorted by name
        assert all_mailboxes[0].name == "Gmail"
        assert all_mailboxes[1].name == "IMAP"
        assert all_mailboxes[2].name == "M365"

    def test_list_mailboxes_by_provider(self, test_config_dir: Path):
        """Test filtering mailboxes by provider."""
        registry = MailboxRegistry(test_config_dir)

        registry.add_mailbox(Mailbox(name="M365-1", provider=ProviderType.M365, email_address="m1@test.com"))
        registry.add_mailbox(Mailbox(name="M365-2", provider=ProviderType.M365, email_address="m2@test.com"))
        registry.add_mailbox(Mailbox(name="Gmail", provider=ProviderType.GMAIL, email_address="g@test.com"))

        m365_mailboxes = registry.list_mailboxes(provider=ProviderType.M365)
        assert len(m365_mailboxes) == 2

    def test_list_mailboxes_by_status(self, test_config_dir: Path):
        """Test filtering mailboxes by status."""
        registry = MailboxRegistry(test_config_dir)

        mb1 = Mailbox(name="Active", provider=ProviderType.M365, email_address="a@test.com")
        mb1.set_active()
        registry.add_mailbox(mb1)

        mb2 = Mailbox(name="Pending", provider=ProviderType.GMAIL, email_address="p@test.com")
        registry.add_mailbox(mb2)

        active = registry.list_mailboxes(status=MailboxStatus.ACTIVE)
        assert len(active) == 1
        assert active[0].name == "Active"

    def test_remove_mailbox(self, test_config_dir: Path):
        """Test removing mailbox."""
        registry = MailboxRegistry(test_config_dir)

        mailbox = Mailbox(name="To Remove", provider=ProviderType.IMAP, email_address="r@test.com")
        registry.add_mailbox(mailbox)

        # Remove
        result = registry.remove_mailbox(mailbox.id)
        assert result is True

        # Verify removed
        assert registry.get_mailbox(mailbox.id) is None

    def test_remove_nonexistent_mailbox(self, test_config_dir: Path):
        """Test removing nonexistent mailbox returns False."""
        registry = MailboxRegistry(test_config_dir)

        result = registry.remove_mailbox(uuid4())
        assert result is False

    def test_clear_all(self, test_config_dir: Path):
        """Test clearing all mailboxes."""
        registry = MailboxRegistry(test_config_dir)

        # Add multiple mailboxes
        for i in range(5):
            mailbox = Mailbox(
                name=f"Mailbox {i}",
                provider=ProviderType.M365,
                email_address=f"mb{i}@test.com",
            )
            registry.add_mailbox(mailbox)

        assert registry.count == 5

        # Clear all
        count = registry.clear_all()
        assert count == 5
        assert registry.count == 0

    def test_config_file_persistence(self, test_config_dir: Path):
        """Test that mailboxes persist across registry instances."""
        mailbox = Mailbox(name="Persistent", provider=ProviderType.GMAIL, email_address="p@test.com")

        # Add in first instance
        registry1 = MailboxRegistry(test_config_dir)
        registry1.add_mailbox(mailbox)

        # Retrieve in second instance
        registry2 = MailboxRegistry(test_config_dir)
        retrieved = registry2.get_mailbox(mailbox.id)

        assert retrieved is not None
        assert retrieved.name == mailbox.name

    def test_secure_file_permissions(self, test_config_dir: Path):
        """Test config files have secure permissions."""
        registry = MailboxRegistry(test_config_dir)

        mailbox = Mailbox(name="Secure", provider=ProviderType.M365, email_address="s@test.com")
        registry.add_mailbox(mailbox)

        # Check directory permissions (700)
        assert oct(test_config_dir.stat().st_mode)[-3:] == "700"

        # Check file permissions (600)
        config_file = test_config_dir / "mailboxes.json"
        assert oct(config_file.stat().st_mode)[-3:] == "600"


@pytest.mark.integration
@pytest.mark.asyncio
class TestMailboxManager:
    """Integration tests for mailbox manager."""

    async def test_add_mailbox(self, test_data_dir: Path):
        """Test adding mailbox through manager."""
        manager = MailboxManager(data_dir=test_data_dir)

        mailbox = manager.add_mailbox(
            name="Test Mailbox",
            provider=ProviderType.M365,
            email_address="test@example.com",
            tenant_id="test-tenant",
        )

        assert mailbox.id is not None
        assert mailbox.status == MailboxStatus.PENDING_AUTH

        # Verify data directory created
        mailbox_dir = mailbox.get_data_dir(test_data_dir)
        assert mailbox_dir.exists()
        assert (mailbox_dir / "checkpoints").exists()

    async def test_authenticate_mailbox(self, test_data_dir: Path, mock_m365_provider):
        """Test authenticating a mailbox."""
        manager = MailboxManager(data_dir=test_data_dir)

        mailbox = manager.add_mailbox(
            name="Auth Test",
            provider=ProviderType.M365,
            email_address="test@example.com",
        )

        with patch("src.mailbox.manager.get_provider_for_mailbox", return_value=mock_m365_provider):
            result = await manager.authenticate_mailbox(mailbox.id)

            assert result is True

            # Verify mailbox status updated
            updated = manager.registry.get_mailbox(mailbox.id)
            assert updated.status == MailboxStatus.ACTIVE

    async def test_authenticate_mailbox_failure(self, test_data_dir: Path):
        """Test authentication failure updates mailbox status."""
        manager = MailboxManager(data_dir=test_data_dir)

        mailbox = manager.add_mailbox(
            name="Auth Fail",
            provider=ProviderType.M365,
            email_address="test@example.com",
        )

        # Mock failed authentication
        mock_provider = MagicMock()
        mock_provider.authenticate = AsyncMock(side_effect=AuthenticationError(
            "Auth failed",
            provider=ProviderType.M365,
        ))
        mock_provider.close = AsyncMock()

        with patch("src.mailbox.manager.get_provider_for_mailbox", return_value=mock_provider):
            with pytest.raises(AuthenticationError):
                await manager.authenticate_mailbox(mailbox.id)

            # Verify error status
            updated = manager.registry.get_mailbox(mailbox.id)
            assert updated.status == MailboxStatus.ERROR

    async def test_extract_mailbox(self, test_data_dir: Path, mock_m365_provider, sample_emails):
        """Test extracting emails from mailbox."""
        manager = MailboxManager(data_dir=test_data_dir)

        mailbox = manager.add_mailbox(
            name="Extract Test",
            provider=ProviderType.M365,
            email_address="test@example.com",
        )

        with patch("src.mailbox.manager.get_provider_for_mailbox", return_value=mock_m365_provider):
            corpus = await manager.extract_mailbox(mailbox.id, batch_size=10)

            assert isinstance(corpus, Corpus)
            assert len(corpus.emails) == len(sample_emails)

            # Verify mailbox status updated
            updated = manager.registry.get_mailbox(mailbox.id)
            assert updated.extraction.is_complete
            assert updated.extraction.total_emails == len(sample_emails)

            # Verify corpus saved
            corpus_path = mailbox.get_corpus_path(test_data_dir)
            assert corpus_path.exists()

    async def test_extract_with_progress_callback(self, test_data_dir: Path, mock_m365_provider):
        """Test extraction with progress tracking."""
        manager = MailboxManager(data_dir=test_data_dir)

        mailbox = manager.add_mailbox(
            name="Progress Test",
            provider=ProviderType.M365,
            email_address="test@example.com",
        )

        progress_updates = []

        def track_progress(progress):
            progress_updates.append(progress.emails_fetched)

        with patch("src.mailbox.manager.get_provider_for_mailbox", return_value=mock_m365_provider):
            await manager.extract_mailbox(
                mailbox.id,
                batch_size=5,
                progress_callback=track_progress,
            )

            assert len(progress_updates) > 0

    async def test_extract_all_mailboxes(self, test_data_dir: Path, mock_m365_provider, mock_gmail_provider):
        """Test extracting from multiple mailboxes concurrently."""
        manager = MailboxManager(data_dir=test_data_dir)

        # Add multiple mailboxes
        mb1 = manager.add_mailbox("M365", ProviderType.M365, "m365@test.com")
        mb1.set_active()
        manager.registry.update_mailbox(mb1)

        mb2 = manager.add_mailbox("Gmail", ProviderType.GMAIL, "gmail@test.com")
        mb2.set_active()
        manager.registry.update_mailbox(mb2)

        # Mock provider creation
        def mock_get_provider(mailbox):
            if mailbox.provider == ProviderType.M365:
                return mock_m365_provider
            return mock_gmail_provider

        with patch("src.mailbox.manager.get_provider_for_mailbox", side_effect=mock_get_provider):
            results = await manager.extract_all_mailboxes(concurrency=2)

            assert len(results) == 2
            assert mb1.id in results
            assert mb2.id in results
            assert all(isinstance(c, Corpus) for c in results.values())

    async def test_extract_all_specific_mailboxes(self, test_data_dir: Path, mock_m365_provider):
        """Test extracting from specific subset of mailboxes."""
        manager = MailboxManager(data_dir=test_data_dir)

        # Add mailboxes
        mb1 = manager.add_mailbox("MB1", ProviderType.M365, "mb1@test.com")
        mb1.set_active()
        manager.registry.update_mailbox(mb1)

        mb2 = manager.add_mailbox("MB2", ProviderType.M365, "mb2@test.com")
        mb2.set_active()
        manager.registry.update_mailbox(mb2)

        mb3 = manager.add_mailbox("MB3", ProviderType.M365, "mb3@test.com")
        mb3.set_active()
        manager.registry.update_mailbox(mb3)

        # Extract only specific mailboxes
        with patch("src.mailbox.manager.get_provider_for_mailbox", return_value=mock_m365_provider):
            results = await manager.extract_all_mailboxes(
                mailbox_ids=[mb1.id, mb3.id],
                concurrency=2,
            )

            assert len(results) == 2
            assert mb1.id in results
            assert mb3.id in results
            assert mb2.id not in results

    def test_get_corpus(self, test_data_dir: Path, sample_emails):
        """Test loading corpus for mailbox."""
        manager = MailboxManager(data_dir=test_data_dir)

        mailbox = manager.add_mailbox("Test", ProviderType.M365, "test@example.com")

        # Create and save corpus
        from src.models.corpus import Corpus, CorpusMetadata

        metadata = CorpusMetadata(
            user_email="test@example.com",
            extraction_date=datetime.now(),
            total_emails=len(sample_emails),
            mailbox_id=mailbox.id,
        )

        corpus = Corpus(
            extraction_metadata=metadata,
            emails=sample_emails,
        )

        from src.utils.file_manager import save_json

        corpus_path = mailbox.get_corpus_path(test_data_dir)
        corpus_path.parent.mkdir(parents=True, exist_ok=True)
        save_json(corpus.model_dump(mode="json"), corpus_path)

        # Load corpus
        loaded = manager.get_corpus(mailbox.id)

        assert loaded is not None
        assert len(loaded.emails) == len(sample_emails)

    def test_get_all_corpora(self, test_data_dir: Path, sample_emails):
        """Test loading all available corpora."""
        manager = MailboxManager(data_dir=test_data_dir)

        # Create multiple mailboxes with corpora
        from src.models.corpus import Corpus, CorpusMetadata
        from src.utils.file_manager import save_json

        for i in range(3):
            mailbox = manager.add_mailbox(f"MB{i}", ProviderType.M365, f"mb{i}@test.com")

            metadata = CorpusMetadata(
                user_email=mailbox.email_address,
                extraction_date=datetime.now(),
                total_emails=len(sample_emails),
                mailbox_id=mailbox.id,
            )

            corpus = Corpus(extraction_metadata=metadata, emails=sample_emails)

            corpus_path = mailbox.get_corpus_path(test_data_dir)
            corpus_path.parent.mkdir(parents=True, exist_ok=True)
            save_json(corpus.model_dump(mode="json"), corpus_path)

        # Load all
        all_corpora = manager.get_all_corpora()

        assert len(all_corpora) == 3

    def test_get_combined_corpus(self, test_data_dir: Path, sample_emails):
        """Test combining multiple corpora."""
        manager = MailboxManager(data_dir=test_data_dir)

        from src.models.corpus import Corpus, CorpusMetadata
        from src.utils.file_manager import save_json

        # Create mailboxes with different email counts
        emails_per_mailbox = [sample_emails[:3], sample_emails[3:7], sample_emails[7:]]

        for i, emails in enumerate(emails_per_mailbox):
            mailbox = manager.add_mailbox(f"MB{i}", ProviderType.M365, f"mb{i}@test.com")

            metadata = CorpusMetadata(
                user_email=mailbox.email_address,
                extraction_date=datetime.now(),
                total_emails=len(emails),
                mailbox_id=mailbox.id,
            )

            corpus = Corpus(extraction_metadata=metadata, emails=emails)

            corpus_path = mailbox.get_corpus_path(test_data_dir)
            corpus_path.parent.mkdir(parents=True, exist_ok=True)
            save_json(corpus.model_dump(mode="json"), corpus_path)

        # Get combined
        combined = manager.get_combined_corpus()

        assert combined is not None
        assert len(combined.emails) == len(sample_emails)

    def test_remove_mailbox_keep_data(self, test_data_dir: Path):
        """Test removing mailbox without deleting data."""
        manager = MailboxManager(data_dir=test_data_dir)

        mailbox = manager.add_mailbox("To Remove", ProviderType.M365, "remove@test.com")
        mailbox_dir = mailbox.get_data_dir(test_data_dir)

        # Remove without deleting data
        result = manager.remove_mailbox(mailbox.id, delete_data=False)

        assert result is True
        assert mailbox_dir.exists()  # Data still exists

    def test_remove_mailbox_delete_data(self, test_data_dir: Path):
        """Test removing mailbox and deleting data."""
        manager = MailboxManager(data_dir=test_data_dir)

        mailbox = manager.add_mailbox("To Remove", ProviderType.M365, "remove@test.com")
        mailbox_dir = mailbox.get_data_dir(test_data_dir)

        # Remove and delete data
        result = manager.remove_mailbox(mailbox.id, delete_data=True)

        assert result is True
        assert not mailbox_dir.exists()  # Data deleted
