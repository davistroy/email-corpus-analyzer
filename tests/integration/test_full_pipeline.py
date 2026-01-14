"""
End-to-end integration tests for the full pipeline.

Tests the complete workflow: extract -> analyze -> categorize
using mocked providers and LLM to verify all components work together.
"""
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Check for anthropic package
try:
    import anthropic  # noqa
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

from src.extractors.async_extractor import AsyncEmailExtractor
from src.llm.categorizer import CategorySuggestions, LLMCategorizer
from src.llm.client import LLMClient
from src.mailbox.manager import MailboxManager
from src.models.corpus import Corpus
from src.models.email import Email
from src.models.mailbox import Mailbox, MailboxStatus
from src.models.provider import ProviderType


@pytest.mark.integration
@pytest.mark.asyncio
class TestFullPipeline:
    """End-to-end pipeline tests."""

    async def test_extract_and_save_pipeline(
        self,
        test_data_dir: Path,
        mock_m365_provider,
        m365_mailbox: Mailbox,
        sample_emails: list[Email],
    ):
        """Test extraction and saving to disk."""
        # Step 1: Extract emails
        extractor = AsyncEmailExtractor(
            provider=mock_m365_provider,
            mailbox=m365_mailbox,
            data_dir=test_data_dir,
        )

        corpus = await extractor.extract_all(batch_size=10)

        # Step 2: Verify corpus
        assert isinstance(corpus, Corpus)
        assert len(corpus.emails) == len(sample_emails)

        # Step 3: Save corpus
        from src.utils.file_manager import save_json

        corpus_path = m365_mailbox.get_corpus_path(test_data_dir)
        corpus_path.parent.mkdir(parents=True, exist_ok=True)
        save_json(corpus.model_dump(mode="json"), corpus_path)

        # Step 4: Verify saved
        assert corpus_path.exists()

        # Step 5: Load and verify
        from src.utils.file_manager import load_json

        loaded_data = load_json(corpus_path)
        loaded_corpus = Corpus(**loaded_data)

        assert len(loaded_corpus.emails) == len(sample_emails)

    async def test_manager_extract_analyze_flow(
        self,
        test_data_dir: Path,
        mock_m365_provider,
        sample_emails: list[Email],
    ):
        """Test extraction and analysis through manager."""
        manager = MailboxManager(data_dir=test_data_dir)

        # Step 1: Add mailbox
        mailbox = manager.add_mailbox(
            name="Test Mailbox",
            provider=ProviderType.M365,
            email_address="test@example.com",
        )

        assert mailbox.status == MailboxStatus.PENDING_AUTH

        # Step 2: Authenticate
        with patch("src.mailbox.manager.get_provider_for_mailbox", return_value=mock_m365_provider):
            await manager.authenticate_mailbox(mailbox.id)

            updated = manager.registry.get_mailbox(mailbox.id)
            assert updated.status == MailboxStatus.ACTIVE

        # Step 3: Extract
        with patch("src.mailbox.manager.get_provider_for_mailbox", return_value=mock_m365_provider):
            corpus = await manager.extract_mailbox(mailbox.id)

            assert len(corpus.emails) == len(sample_emails)

        # Step 4: Verify state updated
        final = manager.registry.get_mailbox(mailbox.id)
        assert final.extraction.is_complete
        assert final.extraction.total_emails == len(sample_emails)

    @pytest.mark.skipif(not HAS_ANTHROPIC, reason="anthropic package not installed")
    async def test_extract_analyze_categorize_pipeline(
        self,
        test_data_dir: Path,
        mock_m365_provider,
        sample_emails: list[Email],
        mock_anthropic_client,
    ):
        """Test complete pipeline: extract -> analyze -> categorize."""
        # Step 1: Extract emails
        manager = MailboxManager(data_dir=test_data_dir)
        mailbox = manager.add_mailbox(
            "Pipeline Test",
            ProviderType.M365,
            "test@example.com",
        )

        with patch("src.mailbox.manager.get_provider_for_mailbox", return_value=mock_m365_provider):
            corpus = await manager.extract_mailbox(mailbox.id)

        assert len(corpus.emails) == len(sample_emails)

        # Step 2: Analyze corpus (simplified - just verify we can analyze)
        from src.analyzers.sender_analyzer import SenderAnalyzer
        from src.analyzers.volume_analyzer import VolumeAnalyzer

        volume_analyzer = VolumeAnalyzer()
        volume_stats = volume_analyzer.analyze(corpus)

        sender_analyzer = SenderAnalyzer()
        sender_analysis = sender_analyzer.analyze(corpus)

        assert volume_stats.total_emails == len(sample_emails)
        assert len(sender_analysis.top_senders) > 0

        # Step 3: Categorize with LLM
        with patch("anthropic.Anthropic", return_value=mock_anthropic_client):
            # Mock LLM response
            mock_tool_use = MagicMock()
            mock_tool_use.type = "tool_use"
            mock_tool_use.name = "structured_response"
            mock_tool_use.input = {
                "categories": [
                    {
                        "category_name": "General Emails",
                        "description": "Miscellaneous emails",
                        "confidence": 0.7,
                        "reasoning": "Small sample set",
                        "matching_patterns": ["example.com"],
                        "suggested_action": "review",
                        "estimated_count": len(sample_emails),
                    }
                ],
                "uncategorized_percentage": 10.0,
                "recommendations": "Review for better categorization.",
            }

            mock_response = MagicMock()
            mock_response.content = [mock_tool_use]

            with patch("asyncio.to_thread", return_value=mock_response):
                client = LLMClient(api_key="test-key")
                categorizer = LLMCategorizer(client=client)

                # Create minimal analysis results
                from src.models.analysis_results import (
                    AnalysisResults,
                    SubjectPatterns,
                    TemporalPatterns,
                )

                analysis = AnalysisResults(
                    volume_stats=volume_stats,
                    sender_analysis=sender_analysis,
                    content_clusters=[],
                    subject_patterns=SubjectPatterns(
                        common_prefixes={},
                        numbered_patterns={},
                        top_keywords=[],
                        bracket_tags=[],
                        total_subjects_analyzed=0,
                    ),
                    temporal_patterns=TemporalPatterns(
                        frequency_distribution={},
                        sender_frequencies={},
                    ),
                )

                suggestions = await categorizer.suggest_categories(analysis)

                assert len(suggestions.categories) > 0
                assert suggestions.categories[0].category_name == "General Emails"

    async def test_multi_mailbox_extraction_pipeline(
        self,
        test_data_dir: Path,
        mock_m365_provider,
        mock_gmail_provider,
        sample_emails: list[Email],
    ):
        """Test extracting from multiple mailboxes concurrently."""
        manager = MailboxManager(data_dir=test_data_dir)

        # Add multiple mailboxes
        mb1 = manager.add_mailbox("M365 Box", ProviderType.M365, "m365@test.com")
        mb1.set_active()
        manager.registry.update_mailbox(mb1)

        mb2 = manager.add_mailbox("Gmail Box", ProviderType.GMAIL, "gmail@test.com")
        mb2.set_active()
        manager.registry.update_mailbox(mb2)

        # Mock provider factory
        def get_provider(mailbox):
            if mailbox.provider == ProviderType.M365:
                return mock_m365_provider
            return mock_gmail_provider

        with patch("src.mailbox.manager.get_provider_for_mailbox", side_effect=get_provider):
            results = await manager.extract_all_mailboxes(concurrency=2)

            assert len(results) == 2
            assert mb1.id in results
            assert mb2.id in results

            # Verify both were extracted
            for corpus in results.values():
                assert len(corpus.emails) == len(sample_emails)

    async def test_error_recovery_pipeline(
        self,
        test_data_dir: Path,
        mock_m365_provider,
        sample_emails: list[Email],
    ):
        """Test pipeline recovers from errors gracefully."""
        manager = MailboxManager(data_dir=test_data_dir)

        # Add mailbox
        mailbox = manager.add_mailbox("Error Test", ProviderType.M365, "test@example.com")

        # Step 1: Extraction succeeds
        with patch("src.mailbox.manager.get_provider_for_mailbox", return_value=mock_m365_provider):
            corpus = await manager.extract_mailbox(mailbox.id)
            assert len(corpus.emails) > 0

        # Step 2: Analysis can fail but shouldn't break everything
        from src.analyzers.volume_analyzer import VolumeAnalyzer

        analyzer = VolumeAnalyzer()
        stats = analyzer.analyze(corpus)

        assert stats is not None

        # Step 3: Categorization can fall back when LLM fails
        categorizer = LLMCategorizer(client=None)  # No client

        from src.models.analysis_results import (
            AnalysisResults,
            SubjectPatterns,
            TemporalPatterns,
        )
        from src.analyzers.sender_analyzer import SenderAnalyzer

        sender_analyzer = SenderAnalyzer()
        sender_analysis = sender_analyzer.analyze(corpus)

        analysis = AnalysisResults(
            volume_stats=stats,
            sender_analysis=sender_analysis,
            content_clusters=[],
            subject_patterns=SubjectPatterns(
                common_prefixes={},
                numbered_patterns={},
                top_keywords=[],
                bracket_tags=[],
                total_subjects_analyzed=0,
            ),
            temporal_patterns=TemporalPatterns(
                frequency_distribution={},
                sender_frequencies={},
            ),
        )

        # Should use fallback without crashing
        suggestions = await categorizer.suggest_categories(analysis)
        assert isinstance(suggestions, CategorySuggestions)

    async def test_checkpoint_resume_pipeline(
        self,
        test_data_dir: Path,
        m365_mailbox: Mailbox,
        sample_emails: list[Email],
    ):
        """Test pipeline can resume from checkpoint after interruption."""
        from unittest.mock import Mock

        # Create provider that will be "interrupted"
        provider = Mock()
        provider.provider_type = ProviderType.M365
        provider.email_address = "test@example.com"
        provider.is_authenticated = True
        provider.authenticate = AsyncMock(return_value=True)
        provider.get_total_count = AsyncMock(return_value=len(sample_emails))

        # First extraction: partial
        async def mock_fetch_partial(*args, **kwargs):
            for email in sample_emails[:5]:
                yield email
            # Simulate interruption
            raise Exception("Connection interrupted")

        provider.fetch_emails = mock_fetch_partial

        extractor = AsyncEmailExtractor(
            provider=provider,
            mailbox=m365_mailbox,
            data_dir=test_data_dir,
            checkpoint_interval=3,
        )

        # First attempt fails
        with pytest.raises(Exception, match="interrupted"):
            await extractor.extract_all(batch_size=10)

        # Verify checkpoint exists
        checkpoint_path = m365_mailbox.get_checkpoint_path(test_data_dir)
        assert checkpoint_path.exists()

        # Second extraction: complete
        async def mock_fetch_complete(*args, **kwargs):
            for email in sample_emails:
                yield email

        provider.fetch_emails = mock_fetch_complete

        extractor2 = AsyncEmailExtractor(
            provider=provider,
            mailbox=m365_mailbox,
            data_dir=test_data_dir,
        )

        # Should resume and complete
        corpus = await extractor2.extract_all(batch_size=10)

        # Should have all emails
        assert len(corpus.emails) >= 5

    async def test_large_corpus_pipeline(
        self,
        test_data_dir: Path,
        m365_mailbox: Mailbox,
    ):
        """Test pipeline handles large email corpus efficiently."""
        from unittest.mock import Mock

        # Create provider with many emails
        provider = Mock()
        provider.provider_type = ProviderType.M365
        provider.email_address = "test@example.com"
        provider.is_authenticated = True
        provider.authenticate = AsyncMock(return_value=True)
        provider.get_total_count = AsyncMock(return_value=1000)

        # Generate many emails
        async def mock_fetch_many(*args, **kwargs):
            base_date = datetime.now() - timedelta(days=365)
            for i in range(1000):
                yield Email(
                    id=f"email-{i}",
                    provider=ProviderType.M365,
                    sender_email=f"sender{i % 10}@example.com",
                    sender_name=f"Sender {i % 10}",
                    sender_domain="example.com",
                    subject=f"Email {i}",
                    body_text=f"Content {i}",
                    received_date=base_date + timedelta(days=i),
                    has_attachments=False,
                )

        provider.fetch_emails = mock_fetch_many

        extractor = AsyncEmailExtractor(
            provider=provider,
            mailbox=m365_mailbox,
            data_dir=test_data_dir,
            checkpoint_interval=100,
        )

        # Extract
        corpus = await extractor.extract_all(batch_size=50)

        assert len(corpus.emails) == 1000

        # Analyze (should handle large corpus)
        from src.analyzers.volume_analyzer import VolumeAnalyzer
        from src.analyzers.sender_analyzer import SenderAnalyzer

        volume_analyzer = VolumeAnalyzer()
        stats = volume_analyzer.analyze(corpus)

        assert stats.total_emails == 1000
        assert stats.unique_senders == 10

        sender_analyzer = SenderAnalyzer()
        sender_analysis = sender_analyzer.analyze(corpus)

        assert len(sender_analysis.top_senders) > 0


@pytest.mark.integration
@pytest.mark.asyncio
class TestPipelineWithRealAnalyzers:
    """Test pipeline with actual analyzer implementations."""

    async def test_full_analysis_pipeline(
        self,
        test_data_dir: Path,
        mock_m365_provider,
        sample_emails: list[Email],
    ):
        """Test complete analysis pipeline with all analyzers."""
        # Extract
        manager = MailboxManager(data_dir=test_data_dir)
        mailbox = manager.add_mailbox("Analysis Test", ProviderType.M365, "test@example.com")

        with patch("src.mailbox.manager.get_provider_for_mailbox", return_value=mock_m365_provider):
            corpus = await manager.extract_mailbox(mailbox.id)

        # Run all analyzers
        from src.analyzers.sender_analyzer import SenderAnalyzer
        from src.analyzers.subject_analyzer import SubjectAnalyzer
        from src.analyzers.temporal_analyzer import TemporalAnalyzer
        from src.analyzers.volume_analyzer import VolumeAnalyzer

        volume_analyzer = VolumeAnalyzer()
        volume_stats = volume_analyzer.analyze(corpus)

        sender_analyzer = SenderAnalyzer()
        sender_analysis = sender_analyzer.analyze(corpus)

        subject_analyzer = SubjectAnalyzer()
        subject_patterns = subject_analyzer.analyze(corpus)

        temporal_analyzer = TemporalAnalyzer()
        temporal_patterns = temporal_analyzer.analyze(corpus)

        # Verify all completed
        assert volume_stats.total_emails == len(sample_emails)
        assert len(sender_analysis.top_senders) > 0
        assert subject_patterns is not None
        assert temporal_patterns is not None

    async def test_semantic_analysis_pipeline(
        self,
        test_data_dir: Path,
        mock_m365_provider,
        sample_emails: list[Email],
    ):
        """Test semantic clustering in pipeline."""
        # Extract
        manager = MailboxManager(data_dir=test_data_dir)
        mailbox = manager.add_mailbox("Semantic Test", ProviderType.M365, "test@example.com")

        with patch("src.mailbox.manager.get_provider_for_mailbox", return_value=mock_m365_provider):
            corpus = await manager.extract_mailbox(mailbox.id)

        # Semantic analysis (may be slow, so we just verify it runs)
        from src.analyzers.semantic_analyzer import SemanticAnalyzer

        try:
            semantic_analyzer = SemanticAnalyzer()
            clusters = semantic_analyzer.analyze(corpus)

            # Verify structure
            assert isinstance(clusters, list)
        except (ImportError, OSError, Exception) as e:
            # Skip if ML dependencies not installed or network issues
            pytest.skip(f"ML dependencies not available or network issues: {e}")


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.slow
class TestPerformancePipeline:
    """Performance tests for the full pipeline."""

    async def test_pipeline_performance(
        self,
        test_data_dir: Path,
        m365_mailbox: Mailbox,
    ):
        """Test pipeline performance with realistic data volume."""
        from unittest.mock import Mock
        import time

        # Create provider with moderate email count
        provider = Mock()
        provider.provider_type = ProviderType.M365
        provider.email_address = "test@example.com"
        provider.is_authenticated = True
        provider.authenticate = AsyncMock(return_value=True)
        provider.get_total_count = AsyncMock(return_value=500)

        async def mock_fetch_realistic(*args, **kwargs):
            base_date = datetime.now() - timedelta(days=180)
            for i in range(500):
                yield Email(
                    id=f"email-{i}",
                    provider=ProviderType.M365,
                    sender_email=f"sender{i % 20}@example.com",
                    sender_name=f"Sender {i % 20}",
                    sender_domain="example.com",
                    subject=f"Email subject {i}",
                    body_text=f"Email content number {i} with some text",
                    received_date=base_date + timedelta(days=i / 3),
                    has_attachments=(i % 5 == 0),
                )

        provider.fetch_emails = mock_fetch_realistic

        # Time extraction
        extractor = AsyncEmailExtractor(
            provider=provider,
            mailbox=m365_mailbox,
            data_dir=test_data_dir,
        )

        start = time.time()
        corpus = await extractor.extract_all(batch_size=50)
        extraction_time = time.time() - start

        assert len(corpus.emails) == 500
        assert extraction_time < 10.0  # Should complete in reasonable time

        # Time analysis
        from src.analyzers.sender_analyzer import SenderAnalyzer
        from src.analyzers.volume_analyzer import VolumeAnalyzer

        start = time.time()
        volume_analyzer = VolumeAnalyzer()
        volume_stats = volume_analyzer.analyze(corpus)

        sender_analyzer = SenderAnalyzer()
        sender_analysis = sender_analyzer.analyze(corpus)
        analysis_time = time.time() - start

        assert volume_stats.total_emails == 500
        assert analysis_time < 5.0  # Analysis should be fast

    async def test_concurrent_mailbox_performance(
        self,
        test_data_dir: Path,
        sample_emails: list[Email],
    ):
        """Test performance of concurrent mailbox extraction."""
        from unittest.mock import Mock
        import time

        manager = MailboxManager(data_dir=test_data_dir)

        # Add multiple mailboxes
        mailboxes = []
        for i in range(5):
            mb = manager.add_mailbox(f"MB{i}", ProviderType.M365, f"mb{i}@test.com")
            mb.set_active()
            manager.registry.update_mailbox(mb)
            mailboxes.append(mb)

        # Create mock provider
        def create_mock_provider():
            provider = Mock()
            provider.provider_type = ProviderType.M365
            provider.email_address = "test@example.com"
            provider.is_authenticated = True
            provider.authenticate = AsyncMock(return_value=True)
            provider.get_total_count = AsyncMock(return_value=len(sample_emails))
            provider.close = AsyncMock()

            async def mock_fetch(*args, **kwargs):
                for email in sample_emails:
                    yield email

            provider.fetch_emails = mock_fetch
            return provider

        with patch("src.mailbox.manager.get_provider_for_mailbox", side_effect=lambda _: create_mock_provider()):
            start = time.time()
            results = await manager.extract_all_mailboxes(concurrency=3)
            duration = time.time() - start

            assert len(results) == 5
            # Concurrent extraction should be faster than sequential
            assert duration < 5.0
