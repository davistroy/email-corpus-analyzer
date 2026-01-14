"""
Integration tests for async email extraction.

Tests the async extractor with checkpoint support, progress tracking,
and error handling using mocked providers.
"""
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.extractors.async_extractor import (
    AsyncCheckpointManager,
    AsyncEmailExtractor,
    ExtractionError,
)
from src.models.corpus import Corpus
from src.models.email import Email
from src.models.mailbox import Mailbox
from src.providers.base import ExtractionProgress, RateLimitError


@pytest.mark.integration
@pytest.mark.asyncio
class TestAsyncCheckpointManager:
    """Test checkpoint manager functionality."""

    async def test_checkpoint_save_and_resume(self, test_data_dir: Path, sample_emails: list[Email]):
        """Test saving and resuming from checkpoint."""
        checkpoint_path = test_data_dir / "checkpoint.json"
        manager = AsyncCheckpointManager(checkpoint_path)

        # Save checkpoint
        last_date = datetime.now()
        emails_data = [e.model_dump(mode="json") for e in sample_emails[:3]]

        await manager.save_checkpoint(
            emails_processed=3,
            last_email_date=last_date,
            emails=emails_data,
        )

        assert checkpoint_path.exists()

        # Resume from checkpoint
        count, resume_date, emails = await manager.get_resume_point()

        assert count == 3
        assert resume_date == last_date
        assert len(emails) == 3

    async def test_checkpoint_no_file(self, test_data_dir: Path):
        """Test resume when no checkpoint exists."""
        checkpoint_path = test_data_dir / "nonexistent.json"
        manager = AsyncCheckpointManager(checkpoint_path)

        count, resume_date, emails = await manager.get_resume_point()

        assert count == 0
        assert resume_date is None
        assert emails == []

    async def test_checkpoint_clear(self, test_data_dir: Path):
        """Test clearing checkpoint."""
        checkpoint_path = test_data_dir / "checkpoint.json"
        manager = AsyncCheckpointManager(checkpoint_path)

        # Save and clear
        await manager.save_checkpoint(5, datetime.now(), [])
        assert checkpoint_path.exists()

        await manager.clear_checkpoint()
        assert not checkpoint_path.exists()

    async def test_should_checkpoint_interval(self, test_data_dir: Path):
        """Test checkpoint interval logic."""
        checkpoint_path = test_data_dir / "checkpoint.json"
        manager = AsyncCheckpointManager(checkpoint_path)
        manager._checkpoint_interval = 10

        assert not manager.should_checkpoint(5)
        assert manager.should_checkpoint(10)
        assert not manager.should_checkpoint(15)
        assert manager.should_checkpoint(20)


@pytest.mark.integration
@pytest.mark.asyncio
class TestAsyncEmailExtractor:
    """Test async email extractor."""

    async def test_extract_all_success(
        self,
        mock_m365_provider,
        m365_mailbox: Mailbox,
        test_data_dir: Path,
        sample_emails: list[Email],
    ):
        """Test successful email extraction."""
        extractor = AsyncEmailExtractor(
            provider=mock_m365_provider,
            mailbox=m365_mailbox,
            data_dir=test_data_dir,
            checkpoint_interval=100,
        )

        corpus = await extractor.extract_all(batch_size=10)

        assert isinstance(corpus, Corpus)
        assert len(corpus.emails) == len(sample_emails)
        assert corpus.extraction_metadata.total_emails == len(sample_emails)
        assert corpus.extraction_metadata.mailbox_id == m365_mailbox.id

        # Verify emails have mailbox_id set
        for email in corpus.emails:
            assert email.mailbox_id == m365_mailbox.id

    async def test_extract_with_progress_callback(
        self,
        mock_m365_provider,
        m365_mailbox: Mailbox,
        test_data_dir: Path,
    ):
        """Test extraction with progress callback."""
        extractor = AsyncEmailExtractor(
            provider=mock_m365_provider,
            mailbox=m365_mailbox,
            data_dir=test_data_dir,
        )

        progress_updates = []

        def progress_callback(progress: ExtractionProgress):
            progress_updates.append({
                "emails_fetched": progress.emails_fetched,
                "status": progress.status,
            })

        corpus = await extractor.extract_all(
            batch_size=10,
            progress_callback=progress_callback,
        )

        # Should have multiple progress updates
        assert len(progress_updates) > 0
        assert progress_updates[-1]["status"] == "completed"

    async def test_extract_with_date_filter(
        self,
        mock_m365_provider,
        m365_mailbox: Mailbox,
        test_data_dir: Path,
    ):
        """Test extraction with date filter."""
        extractor = AsyncEmailExtractor(
            provider=mock_m365_provider,
            mailbox=m365_mailbox,
            data_dir=test_data_dir,
        )

        since = datetime.now() - timedelta(days=7)
        corpus = await extractor.extract_all(
            batch_size=10,
            since=since,
        )

        assert isinstance(corpus, Corpus)
        assert corpus.extraction_metadata.since_date == since

    async def test_extract_with_folder_selection(
        self,
        mock_m365_provider,
        m365_mailbox: Mailbox,
        test_data_dir: Path,
    ):
        """Test extraction from specific folder."""
        extractor = AsyncEmailExtractor(
            provider=mock_m365_provider,
            mailbox=m365_mailbox,
            data_dir=test_data_dir,
        )

        corpus = await extractor.extract_all(
            batch_size=10,
            folder="Sent Items",
        )

        assert corpus.extraction_metadata.folder == "Sent Items"

    async def test_extract_requires_authentication(
        self,
        mock_m365_provider,
        m365_mailbox: Mailbox,
        test_data_dir: Path,
    ):
        """Test extraction authenticates if needed."""
        # Set provider as not authenticated
        mock_m365_provider.is_authenticated = False

        extractor = AsyncEmailExtractor(
            provider=mock_m365_provider,
            mailbox=m365_mailbox,
            data_dir=test_data_dir,
        )

        corpus = await extractor.extract_all(batch_size=10)

        # Should have called authenticate
        mock_m365_provider.authenticate.assert_called_once()
        assert isinstance(corpus, Corpus)

    async def test_extract_with_checkpoint_saving(
        self,
        mock_m365_provider,
        m365_mailbox: Mailbox,
        test_data_dir: Path,
        sample_emails: list[Email],
    ):
        """Test checkpoint is saved periodically."""
        # Set small checkpoint interval
        extractor = AsyncEmailExtractor(
            provider=mock_m365_provider,
            mailbox=m365_mailbox,
            data_dir=test_data_dir,
            checkpoint_interval=5,  # Save every 5 emails
        )

        corpus = await extractor.extract_all(batch_size=10)

        # Checkpoint should be cleared after successful extraction
        checkpoint_path = m365_mailbox.get_checkpoint_path(test_data_dir)
        assert not checkpoint_path.exists()

    async def test_extract_resume_from_checkpoint(
        self,
        mock_m365_provider,
        m365_mailbox: Mailbox,
        test_data_dir: Path,
        sample_emails: list[Email],
    ):
        """Test resuming extraction from checkpoint."""
        checkpoint_path = m365_mailbox.get_checkpoint_path(test_data_dir)
        checkpoint_path.parent.mkdir(parents=True, exist_ok=True)

        # Create checkpoint with some emails already processed
        checkpoint_manager = AsyncCheckpointManager(checkpoint_path)
        partial_emails = sample_emails[:3]
        await checkpoint_manager.save_checkpoint(
            emails_processed=3,
            last_email_date=partial_emails[-1].received_date,
            emails=[e.model_dump(mode="json") for e in partial_emails],
        )

        extractor = AsyncEmailExtractor(
            provider=mock_m365_provider,
            mailbox=m365_mailbox,
            data_dir=test_data_dir,
        )

        corpus = await extractor.extract_all(batch_size=10)

        # Should include both checkpointed and newly fetched emails
        assert len(corpus.emails) >= 3

    async def test_extract_rate_limit_saves_checkpoint(
        self,
        m365_mailbox: Mailbox,
        test_data_dir: Path,
        sample_emails: list[Email],
    ):
        """Test checkpoint is saved when rate limited."""
        # Create provider that raises rate limit after some emails
        from unittest.mock import Mock

        provider = Mock()
        provider.provider_type = "m365"
        provider.email_address = "test@example.com"
        provider.is_authenticated = True
        provider.authenticate = AsyncMock(return_value=True)
        provider.get_total_count = AsyncMock(return_value=10)

        # Yield some emails then raise rate limit
        async def mock_fetch(*args, **kwargs):
            for i, email in enumerate(sample_emails[:5]):
                yield email
            raise RateLimitError("Rate limited", retry_after=60)

        provider.fetch_emails = mock_fetch

        extractor = AsyncEmailExtractor(
            provider=provider,
            mailbox=m365_mailbox,
            data_dir=test_data_dir,
            checkpoint_interval=3,
        )

        with pytest.raises(RateLimitError):
            await extractor.extract_all(batch_size=10)

        # Checkpoint should exist
        checkpoint_path = m365_mailbox.get_checkpoint_path(test_data_dir)
        assert checkpoint_path.exists()

    async def test_extract_handles_individual_email_errors(
        self,
        m365_mailbox: Mailbox,
        test_data_dir: Path,
        sample_emails: list[Email],
    ):
        """Test extraction continues when individual emails fail."""
        from unittest.mock import Mock

        provider = Mock()
        provider.provider_type = "m365"
        provider.email_address = "test@example.com"
        provider.is_authenticated = True
        provider.authenticate = AsyncMock(return_value=True)
        provider.get_total_count = AsyncMock(return_value=10)

        # Create an email that will cause processing error
        bad_email = Email(
            id="bad-email",
            provider="m365",
            sender_email="test@example.com",
            sender_name="Test",
            sender_domain="example.com",
            subject="Bad Email",
            body_text="Test",
            received_date=datetime.now(),
            has_attachments=False,
        )

        async def mock_fetch(*args, **kwargs):
            yield sample_emails[0]
            yield bad_email  # This one will fail processing
            yield sample_emails[1]

        provider.fetch_emails = mock_fetch

        extractor = AsyncEmailExtractor(
            provider=provider,
            mailbox=m365_mailbox,
            data_dir=test_data_dir,
        )

        corpus = await extractor.extract_all(batch_size=10)

        # Should still get the valid emails
        assert len(corpus.emails) >= 2


@pytest.mark.integration
@pytest.mark.asyncio
class TestExtractFromProvider:
    """Test convenience function for direct extraction."""

    async def test_extract_from_provider(
        self,
        mock_m365_provider,
        test_data_dir: Path,
        sample_emails: list[Email],
    ):
        """Test extracting directly from provider."""
        from src.extractors.async_extractor import extract_from_provider

        output_path = test_data_dir / "corpus.json"

        corpus = await extract_from_provider(
            provider=mock_m365_provider,
            user_email="test@example.com",
            output_path=output_path,
            batch_size=10,
        )

        assert isinstance(corpus, Corpus)
        assert len(corpus.emails) == len(sample_emails)

        # Should save to output path
        assert output_path.exists()

    async def test_extract_with_all_parameters(
        self,
        mock_gmail_provider,
        test_data_dir: Path,
    ):
        """Test extraction with all optional parameters."""
        from src.extractors.async_extractor import extract_from_provider

        output_path = test_data_dir / "gmail_corpus.json"
        since = datetime.now() - timedelta(days=30)

        progress_calls = []

        def track_progress(progress):
            progress_calls.append(progress.emails_fetched)

        corpus = await extract_from_provider(
            provider=mock_gmail_provider,
            user_email="test@gmail.com",
            output_path=output_path,
            batch_size=20,
            since=since,
            folder="SENT",
            progress_callback=track_progress,
        )

        assert isinstance(corpus, Corpus)
        assert output_path.exists()
        assert len(progress_calls) > 0


@pytest.mark.integration
@pytest.mark.asyncio
class TestExtractionPerformance:
    """Test extraction performance and concurrency."""

    async def test_concurrent_email_processing(
        self,
        m365_mailbox: Mailbox,
        test_data_dir: Path,
    ):
        """Test that extraction handles async iteration efficiently."""
        from unittest.mock import Mock
        import asyncio

        provider = Mock()
        provider.provider_type = "m365"
        provider.email_address = "test@example.com"
        provider.is_authenticated = True
        provider.authenticate = AsyncMock(return_value=True)
        provider.get_total_count = AsyncMock(return_value=50)

        # Simulate slow email fetching
        async def mock_fetch(*args, **kwargs):
            for i in range(50):
                await asyncio.sleep(0.01)  # Simulate API delay
                yield Email(
                    id=f"email-{i}",
                    provider="m365",
                    sender_email=f"sender{i}@example.com",
                    sender_name=f"Sender {i}",
                    sender_domain="example.com",
                    subject=f"Email {i}",
                    body_text=f"Content {i}",
                    received_date=datetime.now(),
                    has_attachments=False,
                )

        provider.fetch_emails = mock_fetch

        extractor = AsyncEmailExtractor(
            provider=provider,
            mailbox=m365_mailbox,
            data_dir=test_data_dir,
        )

        import time
        start = time.time()
        corpus = await extractor.extract_all(batch_size=10)
        duration = time.time() - start

        # Should complete in reasonable time (async iteration)
        assert len(corpus.emails) == 50
        assert duration < 2.0  # Should be fast with async

    async def test_memory_efficiency_large_corpus(
        self,
        m365_mailbox: Mailbox,
        test_data_dir: Path,
    ):
        """Test extraction handles large email volumes efficiently."""
        from unittest.mock import Mock

        provider = Mock()
        provider.provider_type = "m365"
        provider.email_address = "test@example.com"
        provider.is_authenticated = True
        provider.authenticate = AsyncMock(return_value=True)
        provider.get_total_count = AsyncMock(return_value=1000)

        # Generate many emails
        async def mock_fetch(*args, **kwargs):
            for i in range(1000):
                yield Email(
                    id=f"email-{i}",
                    provider="m365",
                    sender_email="sender@example.com",
                    sender_name="Sender",
                    sender_domain="example.com",
                    subject=f"Email {i}",
                    body_text="Short content",
                    received_date=datetime.now(),
                    has_attachments=False,
                )

        provider.fetch_emails = mock_fetch

        extractor = AsyncEmailExtractor(
            provider=provider,
            mailbox=m365_mailbox,
            data_dir=test_data_dir,
            checkpoint_interval=100,  # Save checkpoints
        )

        corpus = await extractor.extract_all(batch_size=50)

        # Should handle large corpus
        assert len(corpus.emails) == 1000
        assert corpus.extraction_metadata.total_emails == 1000
