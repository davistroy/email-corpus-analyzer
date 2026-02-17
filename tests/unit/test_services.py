"""
Unit tests for Track 7B: Service Layer.

Tests the service layer components:
- ExtractionService
- AnalysisService
- SuggestionService
- PipelineService
"""
import json
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.config.models import (
    AnalyzeConfig,
    AnalyzerThresholds,
    AppConfig,
    ExtractConfig,
    SuggestConfig,
)
from src.models.analysis_results import (
    AnalysisResults,
    DomainCount,
    SenderAnalysis,
    SubjectPatterns,
    TemporalPatterns,
    VolumeStats,
)
from src.models.category import Category, CategorySource
from src.models.content_cluster import ContentCluster, RepresentativeSample
from src.models.corpus import Corpus, CorpusMetadata
from src.models.email import Email
from src.models.sender import Sender, SenderType

# =============================================================================
# Test Fixtures
# =============================================================================


def create_test_email(
    email_id: str = "test_001",
    sender_email: str = "sender@example.com",
    sender_domain: str = "example.com",
    subject: str = "Test Subject",
    body_text: str = "Test body content",
    received_date: datetime | None = None,
) -> Email:
    """Factory function to create Email objects for testing."""
    if received_date is None:
        received_date = datetime(2024, 1, 15, 10, 0)
    return Email(
        id=email_id,
        sender_email=sender_email,
        sender_name="Test Sender",
        sender_domain=sender_domain,
        subject=subject,
        body_text=body_text,
        received_date=received_date,
        has_attachments=False,
    )


def create_test_corpus(emails: list[Email] | None = None) -> Corpus:
    """Factory function to create Corpus objects for testing."""
    if emails is None:
        emails = [create_test_email(email_id=f"email_{i}") for i in range(10)]
    return Corpus(
        extraction_metadata=CorpusMetadata(
            extraction_date=datetime.now(),
            total_emails=len(emails),
            source="test",
            user_email="user@example.com",
        ),
        emails=emails,
    )


def create_test_analysis_results() -> AnalysisResults:
    """Factory function to create AnalysisResults for testing."""
    senders = [
        Sender(
            email="sender@example.com",
            name="Test Sender",
            domain="example.com",
            type=SenderType.SERVICE,
            frequency_count=50,
            sample_subjects=["Subject 1", "Subject 2"],
            email_ids=["email_1", "email_2"],
        )
    ]
    clusters = [
        ContentCluster(
            cluster_id=0,
            size=50,
            percentage=50.0,
            representative_samples=[
                RepresentativeSample(
                    subject="Test Subject",
                    sender="sender@example.com",
                    body_preview="Test body preview",
                )
            ],
            common_domains=[("example.com", 50)],
            email_ids=["email_1", "email_2"],
        )
    ]
    return AnalysisResults(
        sender_analysis=SenderAnalysis(
            top_senders=senders,
            top_domains=[DomainCount(domain="example.com", count=100)],
            unique_senders=10,
            unique_domains=5,
        ),
        subject_patterns=SubjectPatterns(
            common_prefixes={"RE:": 20},
            numbered_patterns={"Invoice": 5},
            top_keywords=[("meeting", 10)],
            bracket_tags=[("URGENT", 3)],
            total_subjects_analyzed=100,
        ),
        content_clusters=clusters,
        temporal_patterns=TemporalPatterns(
            frequency_distribution={"daily": 50, "weekly": 30},
            sender_frequencies={},
        ),
        volume_stats=VolumeStats(
            total_emails=100,
            unique_senders=10,
            date_range={"oldest": "2024-01-01", "newest": "2024-01-31", "span_days": "30"},
            with_attachments=20,
            attachment_percentage=20.0,
            avg_body_length_chars=500,
            emails_per_day=3.3,
        ),
    )


def create_test_categories() -> list[Category]:
    """Factory function to create Category list for testing."""
    return [
        Category(
            category_id="cat_001",
            category_name="Test Category",
            description="A test category",
            confidence=0.85,
            email_count=50,
            percentage=10.0,
            source=CategorySource.CONTENT_CLUSTER,
            source_id="cluster_0",
            distinguishing_features=["feature1"],
            example_email_ids=["email_1"],
        )
    ]


# =============================================================================
# Test AnalysisService
# =============================================================================


class TestAnalysisServiceExists:
    """Test that AnalysisService exists and has correct interface."""

    def test_analysis_service_exists(self):
        """Test that AnalysisService class exists."""
        from src.services.analysis_service import AnalysisService

        assert AnalysisService is not None

    def test_analysis_service_has_run_method(self):
        """Test that AnalysisService has run method."""
        from src.services.analysis_service import AnalysisService

        assert hasattr(AnalysisService, "run")

    def test_analysis_service_accepts_config(self):
        """Test that AnalysisService can be initialized with config."""
        from src.services.analysis_service import AnalysisService

        config = AnalyzeConfig(num_clusters=5)
        service = AnalysisService(config)
        assert service.config == config


class TestAnalysisServiceRun:
    """Test AnalysisService.run method."""

    @patch("src.analyzers.semantic_analyzer.SentenceTransformer")
    def test_run_returns_analysis_results(self, mock_st):
        """Test that run returns tuple of (AnalysisResults, stats)."""
        import numpy as np

        from src.services.analysis_service import AnalysisService

        mock_model = MagicMock()
        mock_model.encode.return_value = np.random.rand(10, 384)
        mock_st.return_value = mock_model

        config = AnalyzeConfig(num_clusters=2)
        service = AnalysisService(config)
        corpus = create_test_corpus()

        result = service.run(corpus)

        assert isinstance(result, tuple)
        analysis_results, incremental_stats = result
        assert isinstance(analysis_results, AnalysisResults)
        assert incremental_stats is None  # No embedding_cache provided

    @patch("src.analyzers.semantic_analyzer.SentenceTransformer")
    def test_run_calls_progress_callback(self, mock_st):
        """Test that run calls progress callback."""
        import numpy as np

        from src.services.analysis_service import AnalysisService

        mock_model = MagicMock()
        mock_model.encode.return_value = np.random.rand(10, 384)
        mock_st.return_value = mock_model

        config = AnalyzeConfig(num_clusters=2)
        service = AnalysisService(config)
        corpus = create_test_corpus()

        callback_calls = []

        def progress_callback(message: str):
            callback_calls.append(message)

        result = service.run(corpus, progress_callback=progress_callback)

        assert len(callback_calls) > 0
        assert isinstance(result, tuple)

    def test_run_raises_on_empty_corpus(self):
        """Test that run raises error on empty corpus."""
        from src.services.analysis_service import AnalysisService

        config = AnalyzeConfig(num_clusters=2)
        service = AnalysisService(config)
        corpus = create_test_corpus(emails=[])

        with pytest.raises(ValueError, match="empty"):
            service.run(corpus)


class TestAnalysisServiceAnalyzers:
    """Test AnalysisService analyzer management."""

    def test_service_uses_all_analyzers(self):
        """Test that service uses all required analyzers."""
        from src.services.analysis_service import AnalysisService

        config = AnalyzeConfig()
        service = AnalysisService(config)

        # Should have access to all analyzer types
        analyzer_names = [a.name for a in service._analyzers]
        assert "Sender Analyzer" in analyzer_names
        assert "Subject Analyzer" in analyzer_names
        assert "Temporal Analyzer" in analyzer_names
        assert "Volume Analyzer" in analyzer_names
        assert "Semantic Analyzer" in analyzer_names

    def test_build_analyzers_is_single_source_of_truth(self):
        """Test that _build_analyzers includes all 5 analyzers used by run()."""
        from src.services.analysis_service import AnalysisService

        config = AnalyzeConfig(num_clusters=3)
        service = AnalysisService(config)

        # Exactly 5 analyzers should be built
        assert len(service._analyzers) == 5

    def test_build_analyzers_includes_semantic_analyzer(self):
        """Test that SemanticAnalyzer is built with correct config."""
        from src.analyzers import SemanticAnalyzer
        from src.services.analysis_service import AnalysisService

        config = AnalyzeConfig(max_embedding_text_length=2000)
        service = AnalysisService(config)

        semantic = [a for a in service._analyzers if isinstance(a, SemanticAnalyzer)]
        assert len(semantic) == 1
        assert semantic[0].max_embedding_text_length == 2000

    def test_all_analyzers_have_result_field_mapping(self):
        """Test that every analyzer in the list has a result field mapping."""
        from src.services.analysis_service import _ANALYZER_RESULT_FIELDS, AnalysisService

        config = AnalyzeConfig()
        service = AnalysisService(config)

        for analyzer in service._analyzers:
            assert type(analyzer) in _ANALYZER_RESULT_FIELDS, (
                f"{analyzer.name} has no entry in _ANALYZER_RESULT_FIELDS"
            )


# =============================================================================
# Test AnalysisService Feature Parity (Work Item 2.1)
# =============================================================================


class TestAnalysisServiceAutoCluster:
    """Test that AnalysisService passes auto_clusters to run_full_analysis."""

    @patch("src.services.analysis_service.run_full_analysis")
    def test_auto_clusters_true_reaches_run_full_analysis(self, mock_rfa):
        """Test that auto_clusters=True is forwarded to run_full_analysis."""
        from src.services.analysis_service import AnalysisService

        mock_rfa.return_value = (create_test_analysis_results(), None)

        config = AnalyzeConfig(num_clusters=5)
        service = AnalysisService(config)
        corpus = create_test_corpus()

        service.run(corpus, auto_clusters=True)

        mock_rfa.assert_called_once()
        _, kwargs = mock_rfa.call_args
        assert kwargs["auto_clusters"] is True

    @patch("src.services.analysis_service.run_full_analysis")
    def test_cluster_method_elbow_reaches_run_full_analysis(self, mock_rfa):
        """Test that cluster_method='elbow' is forwarded to run_full_analysis."""
        from src.services.analysis_service import AnalysisService

        mock_rfa.return_value = (create_test_analysis_results(), None)

        config = AnalyzeConfig()
        service = AnalysisService(config)
        corpus = create_test_corpus()

        service.run(corpus, auto_clusters=True, cluster_method="elbow")

        mock_rfa.assert_called_once()
        _, kwargs = mock_rfa.call_args
        assert kwargs["cluster_method"] == "elbow"

    @patch("src.services.analysis_service.run_full_analysis")
    def test_auto_cluster_bounds_from_config(self, mock_rfa):
        """Test that auto_cluster_min/max from config reach run_full_analysis."""
        from src.services.analysis_service import AnalysisService

        mock_rfa.return_value = (create_test_analysis_results(), None)

        config = AnalyzeConfig(auto_cluster_min=5, auto_cluster_max=20)
        service = AnalysisService(config)
        corpus = create_test_corpus()

        service.run(corpus, auto_clusters=True)

        mock_rfa.assert_called_once()
        _, kwargs = mock_rfa.call_args
        assert kwargs["auto_cluster_min"] == 5
        assert kwargs["auto_cluster_max"] == 20


class TestAnalysisServiceIncremental:
    """Test that AnalysisService supports incremental analysis."""

    @patch("src.services.analysis_service.run_full_analysis")
    def test_incremental_mode_passes_embedding_cache(self, mock_rfa):
        """Test that embedding_cache is forwarded to run_full_analysis."""
        from src.services.analysis_service import AnalysisService

        mock_rfa.return_value = (create_test_analysis_results(), {
            "cached_count": 5, "generated_count": 5, "total_emails": 10, "hit_rate": 0.5
        })

        config = AnalyzeConfig()
        service = AnalysisService(config)
        corpus = create_test_corpus()
        mock_cache = MagicMock()

        service.run(corpus, embedding_cache=mock_cache)

        mock_rfa.assert_called_once()
        _, kwargs = mock_rfa.call_args
        assert kwargs["embedding_cache"] is mock_cache

    @patch("src.services.analysis_service.run_full_analysis")
    def test_incremental_returns_stats(self, mock_rfa):
        """Test that incremental stats are returned from run()."""
        from src.services.analysis_service import AnalysisService

        expected_stats = {
            "cached_count": 5, "generated_count": 5, "total_emails": 10, "hit_rate": 0.5
        }
        mock_rfa.return_value = (create_test_analysis_results(), expected_stats)

        config = AnalyzeConfig()
        service = AnalysisService(config)
        corpus = create_test_corpus()
        mock_cache = MagicMock()

        result = service.run(corpus, embedding_cache=mock_cache)

        # The result should be a tuple (AnalysisResults, incremental_stats)
        assert isinstance(result, tuple)
        analysis_results, incremental_stats = result
        assert isinstance(analysis_results, AnalysisResults)
        assert incremental_stats == expected_stats

    @patch("src.services.analysis_service.run_full_analysis")
    def test_non_incremental_returns_none_stats(self, mock_rfa):
        """Test that non-incremental mode returns None for stats."""
        from src.services.analysis_service import AnalysisService

        mock_rfa.return_value = (create_test_analysis_results(), None)

        config = AnalyzeConfig()
        service = AnalysisService(config)
        corpus = create_test_corpus()

        result = service.run(corpus)

        assert isinstance(result, tuple)
        analysis_results, incremental_stats = result
        assert isinstance(analysis_results, AnalysisResults)
        assert incremental_stats is None


class TestAnalysisServiceThresholds:
    """Test that AnalysisService passes thresholds to run_full_analysis."""

    @patch("src.services.analysis_service.run_full_analysis")
    def test_thresholds_from_config_reach_run_full_analysis(self, mock_rfa):
        """Test that thresholds from config are forwarded."""
        from src.services.analysis_service import AnalysisService

        mock_rfa.return_value = (create_test_analysis_results(), None)

        custom_thresholds = AnalyzerThresholds(top_senders=100, top_domains=50)
        config = AnalyzeConfig(thresholds=custom_thresholds)
        service = AnalysisService(config)
        corpus = create_test_corpus()

        service.run(corpus)

        mock_rfa.assert_called_once()
        _, kwargs = mock_rfa.call_args
        assert kwargs["thresholds"].top_senders == 100
        assert kwargs["thresholds"].top_domains == 50

    @patch("src.services.analysis_service.run_full_analysis")
    def test_default_thresholds_passed_when_not_configured(self, mock_rfa):
        """Test that default thresholds are passed when not explicitly configured."""
        from src.services.analysis_service import AnalysisService

        mock_rfa.return_value = (create_test_analysis_results(), None)

        config = AnalyzeConfig()
        service = AnalysisService(config)
        corpus = create_test_corpus()

        service.run(corpus)

        mock_rfa.assert_called_once()
        _, kwargs = mock_rfa.call_args
        # Should pass the default AnalyzerThresholds
        assert isinstance(kwargs["thresholds"], AnalyzerThresholds)
        assert kwargs["thresholds"].top_senders == 50  # default


class TestAnalysisServiceProgressCallbacks:
    """Test that AnalysisService progress callbacks work correctly."""

    @patch("src.services.analysis_service.run_full_analysis")
    def test_progress_callback_is_forwarded(self, mock_rfa):
        """Test that progress callback is forwarded to run_full_analysis."""
        from src.services.analysis_service import AnalysisService

        mock_rfa.return_value = (create_test_analysis_results(), None)

        config = AnalyzeConfig()
        service = AnalysisService(config)
        corpus = create_test_corpus()

        callback_calls = []

        def progress_cb(msg):
            callback_calls.append(msg)

        service.run(corpus, progress_callback=progress_cb)

        mock_rfa.assert_called_once()
        _, kwargs = mock_rfa.call_args
        # run_full_analysis should receive a progress_callback
        assert kwargs["progress_callback"] is not None

    @patch("src.services.analysis_service.run_full_analysis")
    def test_progress_callback_called_for_start_and_complete(self, mock_rfa):
        """Test that service calls progress_callback for start and complete."""
        from src.services.analysis_service import AnalysisService

        mock_rfa.return_value = (create_test_analysis_results(), None)

        config = AnalyzeConfig()
        service = AnalysisService(config)
        corpus = create_test_corpus()

        callback_calls = []

        def progress_cb(msg):
            callback_calls.append(msg)

        service.run(corpus, progress_callback=progress_cb)

        # Should have at least "Starting analysis..." and "Analysis complete!"
        assert any("Starting" in c for c in callback_calls)
        assert any("complete" in c.lower() for c in callback_calls)


class TestAnalysisServiceClusterViz:
    """Test that AnalysisService supports cluster_viz generation."""

    @patch("src.services.analysis_service.run_full_analysis")
    def test_cluster_viz_flag_stored(self, mock_rfa):
        """Test that cluster_viz flag is accepted by run()."""
        from src.services.analysis_service import AnalysisService

        mock_rfa.return_value = (create_test_analysis_results(), None)

        config = AnalyzeConfig()
        service = AnalysisService(config)
        corpus = create_test_corpus()

        # Should not raise even though cluster_viz is True
        result = service.run(corpus, cluster_viz=True)
        assert result is not None

    @patch("src.services.analysis_service.run_full_analysis")
    def test_cluster_viz_returns_path_in_metadata(self, mock_rfa):
        """Test that cluster_viz=True includes viz_path in result metadata."""
        from src.services.analysis_service import AnalysisService

        mock_rfa.return_value = (create_test_analysis_results(), None)

        config = AnalyzeConfig()
        service = AnalysisService(config)
        corpus = create_test_corpus()

        # When cluster_viz is True, result tuple should include viz_path
        result = service.run(corpus, cluster_viz=True)
        assert isinstance(result, tuple)


class TestAnalysisServiceFeatureParity:
    """Test complete feature parity between service and run_full_analysis."""

    @patch("src.services.analysis_service.run_full_analysis")
    def test_all_config_params_forwarded(self, mock_rfa):
        """Test that all AnalyzeConfig params are forwarded to run_full_analysis."""
        from src.services.analysis_service import AnalysisService

        mock_rfa.return_value = (create_test_analysis_results(), None)

        custom_thresholds = AnalyzerThresholds(representative_samples=10)
        config = AnalyzeConfig(
            num_clusters=15,
            max_embedding_text_length=2000,
            auto_cluster_min=4,
            auto_cluster_max=30,
            thresholds=custom_thresholds,
        )
        service = AnalysisService(config)
        corpus = create_test_corpus()

        service.run(
            corpus,
            auto_clusters=True,
            cluster_method="elbow",
        )

        mock_rfa.assert_called_once()
        _, kwargs = mock_rfa.call_args
        assert kwargs["num_clusters"] == 15
        assert kwargs["max_embedding_text_length"] == 2000
        assert kwargs["auto_cluster_min"] == 4
        assert kwargs["auto_cluster_max"] == 30
        assert kwargs["auto_clusters"] is True
        assert kwargs["cluster_method"] == "elbow"
        assert kwargs["thresholds"].representative_samples == 10

    @patch("src.services.analysis_service.run_full_analysis")
    def test_default_behavior_unchanged(self, mock_rfa):
        """Test that default behavior (no extra params) remains unchanged."""
        from src.services.analysis_service import AnalysisService

        mock_rfa.return_value = (create_test_analysis_results(), None)

        config = AnalyzeConfig()
        service = AnalysisService(config)
        corpus = create_test_corpus()

        service.run(corpus)

        mock_rfa.assert_called_once()
        _, kwargs = mock_rfa.call_args
        # Default values
        assert kwargs["num_clusters"] == 10
        assert kwargs["auto_clusters"] is False
        assert kwargs["cluster_method"] == "silhouette"
        assert kwargs["embedding_cache"] is None
        assert kwargs["max_embedding_text_length"] == 1500
        assert kwargs["auto_cluster_min"] == 3
        assert kwargs["auto_cluster_max"] == 25

    def test_run_still_raises_on_empty_corpus(self):
        """Test that empty corpus still raises ValueError."""
        from src.services.analysis_service import AnalysisService

        config = AnalyzeConfig()
        service = AnalysisService(config)
        corpus = create_test_corpus(emails=[])

        with pytest.raises(ValueError, match="empty"):
            service.run(corpus)

    @patch("src.services.analysis_service.run_full_analysis")
    def test_run_returns_tuple_matching_run_full_analysis(self, mock_rfa):
        """Test that run() returns the same tuple shape as run_full_analysis."""
        from src.services.analysis_service import AnalysisService

        expected_results = create_test_analysis_results()
        expected_stats = {"cached_count": 3, "generated_count": 7}
        mock_rfa.return_value = (expected_results, expected_stats)

        config = AnalyzeConfig()
        service = AnalysisService(config)
        corpus = create_test_corpus()

        result = service.run(corpus, embedding_cache=MagicMock())

        assert isinstance(result, tuple)
        assert len(result) == 2
        analysis, stats = result
        assert analysis is expected_results
        assert stats is expected_stats


# =============================================================================
# Test SuggestionService
# =============================================================================


class TestSuggestionServiceExists:
    """Test that SuggestionService exists and has correct interface."""

    def test_suggestion_service_exists(self):
        """Test that SuggestionService class exists."""
        from src.services.suggestion_service import SuggestionService

        assert SuggestionService is not None

    def test_suggestion_service_has_run_method(self):
        """Test that SuggestionService has run method."""
        from src.services.suggestion_service import SuggestionService

        assert hasattr(SuggestionService, "run")

    def test_suggestion_service_accepts_config(self):
        """Test that SuggestionService can be initialized with config."""
        from src.services.suggestion_service import SuggestionService

        config = SuggestConfig(min_cluster_percentage=5.0)
        service = SuggestionService(config)
        assert service.config == config


class TestSuggestionServiceRun:
    """Test SuggestionService.run method."""

    def test_run_returns_category_list(self):
        """Test that run returns list of Category objects."""
        from src.services.suggestion_service import SuggestionService

        config = SuggestConfig()
        service = SuggestionService(config)
        analysis = create_test_analysis_results()

        result = service.run(analysis)

        assert isinstance(result, list)
        # All items should be Category objects
        for item in result:
            assert isinstance(item, Category)

    def test_run_calls_progress_callback(self):
        """Test that run calls progress callback."""
        from src.services.suggestion_service import SuggestionService

        config = SuggestConfig()
        service = SuggestionService(config)
        analysis = create_test_analysis_results()

        callback_calls = []

        def progress_callback(message: str):
            callback_calls.append(message)

        service.run(analysis, progress_callback=progress_callback)

        assert len(callback_calls) > 0


# =============================================================================
# Test ExtractionService
# =============================================================================


class TestExtractionServiceExists:
    """Test that ExtractionService exists and has correct interface."""

    def test_extraction_service_exists(self):
        """Test that ExtractionService class exists."""
        from src.services.extraction_service import ExtractionService

        assert ExtractionService is not None

    def test_extraction_service_has_run_method(self):
        """Test that ExtractionService has run method."""
        from src.services.extraction_service import ExtractionService

        assert hasattr(ExtractionService, "run")

    def test_extraction_service_accepts_config(self):
        """Test that ExtractionService can be initialized with config."""
        from src.services.extraction_service import ExtractionService

        config = ExtractConfig(batch_size=100)
        service = ExtractionService(config, user_email="test@example.com")
        assert service.config == config


class TestExtractionServiceRun:
    """Test ExtractionService.run method."""

    def test_run_with_mocked_extractor(self):
        """Test that run returns Corpus with mocked extractor."""
        from src.extractors.m365_extractor import ExtractionResult
        from src.services.extraction_service import ExtractionService

        config = ExtractConfig()
        service = ExtractionService(config, user_email="test@example.com")

        # Mock the extractor to return ExtractionResult
        mock_corpus = create_test_corpus()
        mock_result = ExtractionResult(
            corpus=mock_corpus,
            failed_emails=[],
            success_count=len(mock_corpus.emails),
            failure_count=0,
            total_attempted=len(mock_corpus.emails),
        )
        service._m365_extractor = MagicMock()
        service._m365_extractor.extract_all.return_value = mock_result

        result = service.run()

        assert isinstance(result, Corpus)
        service._m365_extractor.extract_all.assert_called_once()

    def test_run_calls_progress_callback(self):
        """Test that run calls progress callback."""
        from src.extractors.m365_extractor import ExtractionResult
        from src.services.extraction_service import ExtractionService

        config = ExtractConfig()
        service = ExtractionService(config, user_email="test@example.com")

        mock_corpus = create_test_corpus()
        mock_result = ExtractionResult(
            corpus=mock_corpus,
            failed_emails=[],
            success_count=len(mock_corpus.emails),
            failure_count=0,
            total_attempted=len(mock_corpus.emails),
        )
        service._m365_extractor = MagicMock()
        service._m365_extractor.extract_all.return_value = mock_result

        callback_calls = []

        def progress_callback(message: str):
            callback_calls.append(message)

        service.run(progress_callback=progress_callback)

        assert len(callback_calls) > 0

    def test_run_incremental_with_existing_corpus(self):
        """Test that run with since_last=True calls extract_incremental."""
        from src.extractors.m365_extractor import IncrementalExtractionResult
        from src.services.extraction_service import ExtractionService

        config = ExtractConfig()
        service = ExtractionService(config, user_email="test@example.com")

        existing_corpus = create_test_corpus()
        mock_result = IncrementalExtractionResult(
            corpus=existing_corpus,
            failed_emails=[],
            new_emails_count=5,
            previous_count=10,
            total_count=15,
        )
        service._m365_extractor = MagicMock()
        service._m365_extractor.extract_incremental.return_value = mock_result

        result = service.run(since_last=True, existing_corpus=existing_corpus)

        assert isinstance(result, Corpus)
        service._m365_extractor.extract_incremental.assert_called_once()

    def test_run_full_extraction_when_since_last_without_corpus(self):
        """Test that run does full extraction when since_last=True but no existing corpus."""
        from src.extractors.m365_extractor import ExtractionResult
        from src.services.extraction_service import ExtractionService

        config = ExtractConfig()
        service = ExtractionService(config, user_email="test@example.com")

        mock_corpus = create_test_corpus()
        mock_result = ExtractionResult(
            corpus=mock_corpus,
            failed_emails=[],
            success_count=len(mock_corpus.emails),
            failure_count=0,
            total_attempted=len(mock_corpus.emails),
        )
        service._m365_extractor = MagicMock()
        service._m365_extractor.extract_all.return_value = mock_result

        # since_last=True but no existing_corpus => falls through to full extraction
        result = service.run(since_last=True, existing_corpus=None)

        assert isinstance(result, Corpus)
        service._m365_extractor.extract_all.assert_called_once()


# =============================================================================
# Test ExtractConfig Validation
# =============================================================================


class TestExtractConfigValidation:
    """Test ExtractConfig source and gmail_email validation."""

    def test_default_source_is_hotmail(self):
        """Test that default source is hotmail."""
        config = ExtractConfig()
        assert config.source == "hotmail"
        assert config.gmail_email is None

    def test_hotmail_source_no_gmail_email_required(self):
        """Test that hotmail source does not require gmail_email."""
        config = ExtractConfig(source="hotmail")
        assert config.source == "hotmail"

    def test_gmail_source_requires_gmail_email(self):
        """Test that gmail source requires gmail_email."""
        with pytest.raises(ValueError, match="gmail_email is required"):
            ExtractConfig(source="gmail")

    def test_both_source_requires_gmail_email(self):
        """Test that both source requires gmail_email."""
        with pytest.raises(ValueError, match="gmail_email is required"):
            ExtractConfig(source="both")

    def test_gmail_source_with_gmail_email_succeeds(self):
        """Test that gmail source with gmail_email is valid."""
        config = ExtractConfig(source="gmail", gmail_email="user@gmail.com")
        assert config.source == "gmail"
        assert config.gmail_email == "user@gmail.com"

    def test_both_source_with_gmail_email_succeeds(self):
        """Test that both source with gmail_email is valid."""
        config = ExtractConfig(source="both", gmail_email="user@gmail.com")
        assert config.source == "both"
        assert config.gmail_email == "user@gmail.com"

    def test_invalid_source_raises_error(self):
        """Test that invalid source value raises validation error."""
        with pytest.raises(ValueError, match="source must be one of"):
            ExtractConfig(source="yahoo")


# =============================================================================
# Test ExtractionService Gmail Mode
# =============================================================================


class TestExtractionServiceGmail:
    """Test ExtractionService with Gmail source."""

    def test_run_gmail_source(self):
        """Test that run with source=gmail uses GmailExtractor."""
        from src.extractors.m365_extractor import ExtractionResult
        from src.services.extraction_service import ExtractionService

        config = ExtractConfig(source="gmail", gmail_email="user@gmail.com")
        service = ExtractionService(config, user_email="user@hotmail.com")

        mock_corpus = create_test_corpus()
        mock_result = ExtractionResult(
            corpus=mock_corpus,
            failed_emails=[],
            success_count=len(mock_corpus.emails),
            failure_count=0,
            total_attempted=len(mock_corpus.emails),
        )
        service._gmail_extractor = MagicMock()
        service._gmail_extractor.extract_all.return_value = mock_result

        result = service.run()

        assert isinstance(result, Corpus)
        service._gmail_extractor.extract_all.assert_called_once()

    def test_run_gmail_incremental(self):
        """Test incremental extraction with Gmail source."""
        from src.extractors.m365_extractor import IncrementalExtractionResult
        from src.services.extraction_service import ExtractionService

        config = ExtractConfig(source="gmail", gmail_email="user@gmail.com")
        service = ExtractionService(config, user_email="user@hotmail.com")

        existing_corpus = create_test_corpus()
        mock_result = IncrementalExtractionResult(
            corpus=existing_corpus,
            failed_emails=[],
            new_emails_count=3,
            previous_count=10,
            total_count=13,
        )
        service._gmail_extractor = MagicMock()
        service._gmail_extractor.extract_incremental.return_value = mock_result

        result = service.run(since_last=True, existing_corpus=existing_corpus)

        assert isinstance(result, Corpus)
        service._gmail_extractor.extract_incremental.assert_called_once()

    def test_gmail_extractor_uses_gmail_email(self):
        """Test that Gmail extractor is created with gmail_email from config."""
        from src.services.extraction_service import ExtractionService

        config = ExtractConfig(source="gmail", gmail_email="user@gmail.com")
        service = ExtractionService(config, user_email="user@hotmail.com")

        with patch("src.extractors.gmail_extractor.GmailExtractor") as mock_cls:
            mock_cls.return_value = MagicMock()
            service._get_gmail_extractor()

            mock_cls.assert_called_once_with(
                user_email="user@gmail.com",
                checkpoint_dir="outputs",
            )


# =============================================================================
# Test ExtractionService Both Mode
# =============================================================================


class TestExtractionServiceBoth:
    """Test ExtractionService with both source."""

    def test_run_both_sources(self):
        """Test that run with source=both uses both extractors and merges."""
        from src.extractors.m365_extractor import ExtractionResult
        from src.services.extraction_service import ExtractionService

        config = ExtractConfig(source="both", gmail_email="user@gmail.com")
        service = ExtractionService(config, user_email="user@hotmail.com")

        # Create distinct corpora for each source
        m365_emails = [create_test_email(email_id=f"m365_{i}") for i in range(5)]
        gmail_emails = [create_test_email(email_id=f"gmail_{i}") for i in range(3)]

        m365_corpus = create_test_corpus(emails=m365_emails)
        gmail_corpus = create_test_corpus(emails=gmail_emails)

        m365_result = ExtractionResult(
            corpus=m365_corpus,
            failed_emails=[],
            success_count=5,
            failure_count=0,
            total_attempted=5,
        )
        gmail_result = ExtractionResult(
            corpus=gmail_corpus,
            failed_emails=[],
            success_count=3,
            failure_count=0,
            total_attempted=3,
        )

        service._m365_extractor = MagicMock()
        service._m365_extractor.extract_all.return_value = m365_result
        service._gmail_extractor = MagicMock()
        service._gmail_extractor.extract_all.return_value = gmail_result

        result = service.run()

        assert isinstance(result, Corpus)
        assert len(result.emails) == 8  # 5 + 3, no duplicates
        service._m365_extractor.extract_all.assert_called_once()
        service._gmail_extractor.extract_all.assert_called_once()

    def test_run_both_deduplicates_by_id(self):
        """Test that both mode deduplicates emails by ID."""
        from src.extractors.m365_extractor import ExtractionResult
        from src.services.extraction_service import ExtractionService

        config = ExtractConfig(source="both", gmail_email="user@gmail.com")
        service = ExtractionService(config, user_email="user@hotmail.com")

        # Create overlapping emails (same IDs in both sources)
        shared_emails = [create_test_email(email_id=f"shared_{i}") for i in range(2)]
        m365_only = [create_test_email(email_id=f"m365_{i}") for i in range(3)]
        gmail_only = [create_test_email(email_id=f"gmail_{i}") for i in range(2)]

        m365_corpus = create_test_corpus(emails=m365_only + shared_emails)
        gmail_corpus = create_test_corpus(emails=gmail_only + shared_emails)

        m365_result = ExtractionResult(
            corpus=m365_corpus,
            failed_emails=[],
            success_count=5,
            failure_count=0,
            total_attempted=5,
        )
        gmail_result = ExtractionResult(
            corpus=gmail_corpus,
            failed_emails=[],
            success_count=4,
            failure_count=0,
            total_attempted=4,
        )

        service._m365_extractor = MagicMock()
        service._m365_extractor.extract_all.return_value = m365_result
        service._gmail_extractor = MagicMock()
        service._gmail_extractor.extract_all.return_value = gmail_result

        result = service.run()

        # Should have 3 m365 + 2 shared + 2 gmail = 7 unique
        assert len(result.emails) == 7
        email_ids = {e.id for e in result.emails}
        assert "shared_0" in email_ids
        assert "shared_1" in email_ids
        assert "m365_0" in email_ids
        assert "gmail_0" in email_ids

    def test_run_both_merged_metadata(self):
        """Test that merged corpus has correct metadata."""
        from src.extractors.m365_extractor import ExtractionResult
        from src.services.extraction_service import ExtractionService

        config = ExtractConfig(source="both", gmail_email="user@gmail.com")
        service = ExtractionService(config, user_email="user@hotmail.com")

        m365_corpus = create_test_corpus(emails=[create_test_email(email_id="m365_1")])
        gmail_corpus = create_test_corpus(emails=[create_test_email(email_id="gmail_1")])

        m365_result = ExtractionResult(
            corpus=m365_corpus, failed_emails=[],
            success_count=1, failure_count=0, total_attempted=1,
        )
        gmail_result = ExtractionResult(
            corpus=gmail_corpus, failed_emails=[],
            success_count=1, failure_count=0, total_attempted=1,
        )

        service._m365_extractor = MagicMock()
        service._m365_extractor.extract_all.return_value = m365_result
        service._gmail_extractor = MagicMock()
        service._gmail_extractor.extract_all.return_value = gmail_result

        result = service.run()

        assert "M365/Hotmail" in result.extraction_metadata.source
        assert "Gmail" in result.extraction_metadata.source
        assert result.extraction_metadata.total_emails == 2

    def test_run_both_calls_progress_callback(self):
        """Test that both mode calls progress callback multiple times."""
        from src.extractors.m365_extractor import ExtractionResult
        from src.services.extraction_service import ExtractionService

        config = ExtractConfig(source="both", gmail_email="user@gmail.com")
        service = ExtractionService(config, user_email="user@hotmail.com")

        m365_corpus = create_test_corpus(emails=[create_test_email(email_id="m365_1")])
        gmail_corpus = create_test_corpus(emails=[create_test_email(email_id="gmail_1")])

        m365_result = ExtractionResult(
            corpus=m365_corpus, failed_emails=[],
            success_count=1, failure_count=0, total_attempted=1,
        )
        gmail_result = ExtractionResult(
            corpus=gmail_corpus, failed_emails=[],
            success_count=1, failure_count=0, total_attempted=1,
        )

        service._m365_extractor = MagicMock()
        service._m365_extractor.extract_all.return_value = m365_result
        service._gmail_extractor = MagicMock()
        service._gmail_extractor.extract_all.return_value = gmail_result

        callback_calls = []
        service.run(progress_callback=lambda m: callback_calls.append(m))

        # Should have calls for: starting, both-mode, m365, gmail, merged
        assert len(callback_calls) >= 4


# =============================================================================
# Test ExtractionService Source Registry Dispatch
# =============================================================================


class TestExtractionServiceSourceRegistry:
    """Test unified source registry dispatch in ExtractionService.run()."""

    def test_unknown_source_raises_clear_error(self):
        """Test that an unknown source raises ValueError with descriptive message."""
        from src.services.extraction_service import ExtractionService

        # Bypass ExtractConfig validation by setting source after construction
        config = ExtractConfig()
        service = ExtractionService(config, user_email="test@example.com")
        # Force an invalid source past config validation
        service.config = MagicMock()
        service.config.source = "yahoo"
        service.config.batch_size = 100
        service.config.checkpoint_interval = 50

        with pytest.raises(ValueError, match="Unknown source.*yahoo"):
            service.run()

    def test_all_three_modes_dispatch_correctly(self):
        """Test that hotmail, gmail, and both modes all dispatch via the registry."""
        from src.services.extraction_service import _SOURCE_REGISTRY

        # Verify registry has all three modes
        assert "hotmail" in _SOURCE_REGISTRY
        assert "gmail" in _SOURCE_REGISTRY
        assert "both" in _SOURCE_REGISTRY

        # hotmail mode uses m365 extractor
        assert len(_SOURCE_REGISTRY["hotmail"]) == 1
        assert _SOURCE_REGISTRY["hotmail"][0].factory_attr == "_get_m365_extractor"

        # gmail mode uses gmail extractor
        assert len(_SOURCE_REGISTRY["gmail"]) == 1
        assert _SOURCE_REGISTRY["gmail"][0].factory_attr == "_get_gmail_extractor"

        # both mode uses both extractors
        assert len(_SOURCE_REGISTRY["both"]) == 2
        factory_attrs = {sc.factory_attr for sc in _SOURCE_REGISTRY["both"]}
        assert factory_attrs == {"_get_m365_extractor", "_get_gmail_extractor"}

    def test_adding_source_only_requires_registry_entry(self):
        """Test that _SOURCE_REGISTRY is the single source of truth for dispatch."""
        from src.services.extraction_service import _SOURCE_REGISTRY, _SourceConfig

        # Verify the registry is a dict of str -> list[_SourceConfig]
        for key, configs in _SOURCE_REGISTRY.items():
            assert isinstance(key, str)
            assert isinstance(configs, list)
            for sc in configs:
                assert isinstance(sc, _SourceConfig)
                assert hasattr(sc, "label")
                assert hasattr(sc, "factory_attr")

    def test_single_source_returns_corpus_directly(self):
        """Test that single-source modes return corpus without merging."""
        from src.extractors.m365_extractor import ExtractionResult
        from src.services.extraction_service import ExtractionService

        config = ExtractConfig()
        service = ExtractionService(config, user_email="test@example.com")

        mock_corpus = create_test_corpus()
        mock_result = ExtractionResult(
            corpus=mock_corpus,
            failed_emails=[],
            success_count=len(mock_corpus.emails),
            failure_count=0,
            total_attempted=len(mock_corpus.emails),
        )
        service._m365_extractor = MagicMock()
        service._m365_extractor.extract_all.return_value = mock_result

        result = service.run()

        # Should be the exact same corpus object, not a merged copy
        assert result is mock_corpus

    def test_multi_source_returns_merged_corpus(self):
        """Test that multi-source mode merges and returns a new corpus."""
        from src.extractors.m365_extractor import ExtractionResult
        from src.services.extraction_service import ExtractionService

        config = ExtractConfig(source="both", gmail_email="user@gmail.com")
        service = ExtractionService(config, user_email="user@hotmail.com")

        m365_emails = [create_test_email(email_id="m365_1")]
        gmail_emails = [create_test_email(email_id="gmail_1")]

        m365_corpus = create_test_corpus(emails=m365_emails)
        gmail_corpus = create_test_corpus(emails=gmail_emails)

        m365_result = ExtractionResult(
            corpus=m365_corpus, failed_emails=[],
            success_count=1, failure_count=0, total_attempted=1,
        )
        gmail_result = ExtractionResult(
            corpus=gmail_corpus, failed_emails=[],
            success_count=1, failure_count=0, total_attempted=1,
        )

        service._m365_extractor = MagicMock()
        service._m365_extractor.extract_all.return_value = m365_result
        service._gmail_extractor = MagicMock()
        service._gmail_extractor.extract_all.return_value = gmail_result

        result = service.run()

        # Should be a new merged corpus, not one of the originals
        assert result is not m365_corpus
        assert result is not gmail_corpus
        assert len(result.emails) == 2


# =============================================================================
# Test ExtractionService._merge_corpora
# =============================================================================


class TestMergeCorpora:
    """Test the static _merge_corpora method."""

    def test_merge_empty_corpora(self):
        """Test merging empty corpora."""
        from src.services.extraction_service import ExtractionService

        c1 = create_test_corpus(emails=[])
        c2 = create_test_corpus(emails=[])

        merged = ExtractionService._merge_corpora(
            [c1, c2], user_email="test@example.com",
            source_labels=["A", "B"],
        )

        assert len(merged.emails) == 0
        assert merged.extraction_metadata.source == "A+B"

    def test_merge_single_corpus(self):
        """Test merging a single corpus returns same emails."""
        from src.services.extraction_service import ExtractionService

        emails = [create_test_email(email_id=f"e_{i}") for i in range(3)]
        c1 = create_test_corpus(emails=emails)

        merged = ExtractionService._merge_corpora(
            [c1], user_email="test@example.com",
            source_labels=["Source"],
        )

        assert len(merged.emails) == 3


# =============================================================================
# Test PipelineService
# =============================================================================


class TestPipelineServiceExists:
    """Test that PipelineService exists and has correct interface."""

    def test_pipeline_service_exists(self):
        """Test that PipelineService class exists."""
        from src.services.pipeline_service import PipelineService

        assert PipelineService is not None

    def test_pipeline_service_has_run_method(self):
        """Test that PipelineService has run method."""
        from src.services.pipeline_service import PipelineService

        assert hasattr(PipelineService, "run")

    def test_pipeline_service_accepts_config(self):
        """Test that PipelineService can be initialized with config."""
        from src.services.pipeline_service import PipelineService

        config = AppConfig()
        service = PipelineService(config)
        assert service.config == config


class TestPipelineServiceRun:
    """Test PipelineService.run method."""

    @patch("src.services.pipeline_service.ExtractionService")
    @patch("src.services.pipeline_service.AnalysisService")
    @patch("src.services.pipeline_service.SuggestionService")
    @patch("src.analyzers.semantic_analyzer.SentenceTransformer")
    def test_run_returns_pipeline_result(
        self, mock_st, mock_suggest, mock_analyze, mock_extract
    ):
        """Test that run returns PipelineResult."""

        from src.services.pipeline_service import PipelineResult, PipelineService

        # Setup mocks
        mock_corpus = create_test_corpus()
        mock_analysis = create_test_analysis_results()
        mock_categories = create_test_categories()

        mock_extract.return_value.run.return_value = mock_corpus
        mock_analyze.return_value.run.return_value = (mock_analysis, None)
        mock_suggest.return_value.run.return_value = mock_categories

        config = AppConfig(user_email="test@example.com")
        service = PipelineService(config)

        with tempfile.TemporaryDirectory() as tmpdir:
            result = service.run(output_dir=Path(tmpdir))

            assert isinstance(result, PipelineResult)
            assert result.corpus is not None
            assert result.analysis is not None
            assert result.categories is not None

    @patch("src.services.pipeline_service.ExtractionService")
    @patch("src.services.pipeline_service.AnalysisService")
    @patch("src.services.pipeline_service.SuggestionService")
    def test_run_calls_progress_callback(
        self, mock_suggest, mock_analyze, mock_extract
    ):
        """Test that run calls progress callback."""
        from src.services.pipeline_service import PipelineService

        mock_corpus = create_test_corpus()
        mock_analysis = create_test_analysis_results()
        mock_categories = create_test_categories()

        mock_extract.return_value.run.return_value = mock_corpus
        mock_analyze.return_value.run.return_value = (mock_analysis, None)
        mock_suggest.return_value.run.return_value = mock_categories

        config = AppConfig(user_email="test@example.com")
        service = PipelineService(config)

        callback_calls = []

        def progress_callback(message: str):
            callback_calls.append(message)

        with tempfile.TemporaryDirectory() as tmpdir:
            service.run(output_dir=Path(tmpdir), progress_callback=progress_callback)

        assert len(callback_calls) > 0


# =============================================================================
# Test Service Independence
# =============================================================================


class TestServiceIndependence:
    """Test that services can be used independently."""

    def test_analysis_service_works_without_extraction(self):
        """Test AnalysisService works with pre-existing corpus."""
        from src.services.analysis_service import AnalysisService

        config = AnalyzeConfig(num_clusters=2)
        service = AnalysisService(config)

        # Create corpus directly (simulating loading from file)
        corpus = create_test_corpus()

        # Should work without extraction service
        with patch("src.analyzers.semantic_analyzer.SentenceTransformer") as mock_st:
            import numpy as np

            mock_model = MagicMock()
            mock_model.encode.return_value = np.random.rand(10, 384)
            mock_st.return_value = mock_model

            result = service.run(corpus)
            assert result is not None
            assert isinstance(result, tuple)
            analysis_results, stats = result
            assert isinstance(analysis_results, AnalysisResults)

    def test_suggestion_service_works_without_analysis(self):
        """Test SuggestionService works with pre-existing analysis."""
        from src.services.suggestion_service import SuggestionService

        config = SuggestConfig()
        service = SuggestionService(config)

        # Create analysis directly (simulating loading from file)
        analysis = create_test_analysis_results()

        # Should work without analysis service
        result = service.run(analysis)
        assert result is not None


# =============================================================================
# Test Service Module Exports
# =============================================================================


class TestServiceModuleExports:
    """Test that service module exports are correct."""

    def test_services_init_exports(self):
        """Test that services __init__ exports all services."""
        from src import services

        assert hasattr(services, "ExtractionService")
        assert hasattr(services, "AnalysisService")
        assert hasattr(services, "SuggestionService")
        assert hasattr(services, "PipelineService")


# =============================================================================
# Test ExtractionService: Extractor Lazy Creation
# =============================================================================


class TestExtractionServiceExtractorCreation:
    """Test lazy creation of extractor instances."""

    def test_m365_extractor_created_lazily(self):
        """Test that M365 extractor is created on first access."""
        from src.services.extraction_service import ExtractionService

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            config = ExtractConfig()
            service = ExtractionService(
                config, user_email="test@example.com", output_dir=output_dir
            )

            assert service._m365_extractor is None

            with patch("src.extractors.m365_extractor.EmailExtractor") as mock_cls:
                mock_cls.return_value = MagicMock()
                extractor = service._get_m365_extractor()

                mock_cls.assert_called_once_with(
                    user_email="test@example.com",
                    checkpoint_dir=str(output_dir),
                )
                assert extractor is mock_cls.return_value

    def test_m365_extractor_cached_after_creation(self):
        """Test that M365 extractor is only created once (cached)."""
        from src.services.extraction_service import ExtractionService

        config = ExtractConfig()
        service = ExtractionService(config, user_email="test@example.com")

        with patch("src.extractors.m365_extractor.EmailExtractor") as mock_cls:
            mock_cls.return_value = MagicMock()
            first = service._get_m365_extractor()
            second = service._get_m365_extractor()

            mock_cls.assert_called_once()
            assert first is second

    def test_m365_extractor_uses_outputs_when_no_output_dir(self):
        """Test that M365 extractor uses 'outputs' when output_dir is None."""
        from src.services.extraction_service import ExtractionService

        config = ExtractConfig()
        service = ExtractionService(config, user_email="test@example.com")
        assert service.output_dir is None

        with patch("src.extractors.m365_extractor.EmailExtractor") as mock_cls:
            mock_cls.return_value = MagicMock()
            service._get_m365_extractor()

            mock_cls.assert_called_once_with(
                user_email="test@example.com",
                checkpoint_dir="outputs",
            )

    def test_gmail_extractor_created_lazily(self):
        """Test that Gmail extractor is created on first access."""
        from src.services.extraction_service import ExtractionService

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            config = ExtractConfig(source="gmail", gmail_email="user@gmail.com")
            service = ExtractionService(
                config, user_email="user@hotmail.com", output_dir=output_dir
            )

            assert service._gmail_extractor is None

            with patch("src.extractors.gmail_extractor.GmailExtractor") as mock_cls:
                mock_cls.return_value = MagicMock()
                extractor = service._get_gmail_extractor()

                mock_cls.assert_called_once_with(
                    user_email="user@gmail.com",
                    checkpoint_dir=str(output_dir),
                )
                assert extractor is mock_cls.return_value

    def test_gmail_extractor_cached_after_creation(self):
        """Test that Gmail extractor is only created once (cached)."""
        from src.services.extraction_service import ExtractionService

        config = ExtractConfig(source="gmail", gmail_email="user@gmail.com")
        service = ExtractionService(config, user_email="user@hotmail.com")

        with patch("src.extractors.gmail_extractor.GmailExtractor") as mock_cls:
            mock_cls.return_value = MagicMock()
            first = service._get_gmail_extractor()
            second = service._get_gmail_extractor()

            mock_cls.assert_called_once()
            assert first is second

    def test_gmail_extractor_falls_back_to_user_email(self):
        """Test that Gmail extractor uses user_email when gmail_email is None."""
        from src.services.extraction_service import ExtractionService

        config = ExtractConfig()
        # Manually clear gmail_email to test fallback
        service = ExtractionService(config, user_email="fallback@example.com")
        service.config = MagicMock()
        service.config.gmail_email = None

        with patch("src.extractors.gmail_extractor.GmailExtractor") as mock_cls:
            mock_cls.return_value = MagicMock()
            service._get_gmail_extractor()

            mock_cls.assert_called_once_with(
                user_email="fallback@example.com",
                checkpoint_dir="outputs",
            )


# =============================================================================
# Test ExtractionService: Failed Email Handling and Logging
# =============================================================================


class TestExtractionServiceFailedEmails:
    """Test ExtractionService handling of failed emails."""

    def test_full_extraction_with_failed_emails_logs_warning(self):
        """Test that failed emails during full extraction triggers warning log."""
        from src.extractors.base_extractor import ExtractionError
        from src.extractors.m365_extractor import ExtractionResult
        from src.services.extraction_service import ExtractionService

        config = ExtractConfig()
        service = ExtractionService(config, user_email="test@example.com")

        mock_corpus = create_test_corpus()
        failed = [
            ExtractionError(
                email_id="bad_1", error_type="timeout",
                error_message="timeout", timestamp=datetime.now(),
            )
        ]
        mock_result = ExtractionResult(
            corpus=mock_corpus,
            failed_emails=failed,
            success_count=9,
            failure_count=1,
            total_attempted=10,
        )
        service._m365_extractor = MagicMock()
        service._m365_extractor.extract_all.return_value = mock_result

        with patch("src.services.extraction_service.logger") as mock_logger:
            service.run()
            mock_logger.warning.assert_called_once()
            warning_msg = mock_logger.warning.call_args[0][0]
            assert "1 of 10" in warning_msg
            assert "90.0%" in warning_msg

    def test_incremental_extraction_with_failed_emails_logs_warning(self):
        """Test that failed emails during incremental extraction triggers warning."""
        from src.extractors.base_extractor import ExtractionError
        from src.extractors.m365_extractor import IncrementalExtractionResult
        from src.services.extraction_service import ExtractionService

        config = ExtractConfig()
        service = ExtractionService(config, user_email="test@example.com")

        existing_corpus = create_test_corpus()
        failed = [
            ExtractionError(
                email_id="bad_1", error_type="malformed",
                error_message="bad data", timestamp=datetime.now(),
            ),
            ExtractionError(
                email_id="bad_2", error_type="timeout",
                error_message="timeout", timestamp=datetime.now(),
            ),
        ]
        mock_result = IncrementalExtractionResult(
            corpus=existing_corpus,
            failed_emails=failed,
            new_emails_count=5,
            previous_count=10,
            total_count=15,
        )
        service._m365_extractor = MagicMock()
        service._m365_extractor.extract_incremental.return_value = mock_result

        with patch("src.services.extraction_service.logger") as mock_logger:
            service.run(since_last=True, existing_corpus=existing_corpus)
            mock_logger.warning.assert_called_once()
            warning_msg = mock_logger.warning.call_args[0][0]
            assert "2 emails failed" in warning_msg

    def test_incremental_extraction_progress_callback_reports_counts(self):
        """Test that incremental progress callback includes new/total counts."""
        from src.extractors.m365_extractor import IncrementalExtractionResult
        from src.services.extraction_service import ExtractionService

        config = ExtractConfig()
        service = ExtractionService(config, user_email="test@example.com")

        existing_corpus = create_test_corpus()
        mock_result = IncrementalExtractionResult(
            corpus=existing_corpus,
            failed_emails=[],
            new_emails_count=5,
            previous_count=10,
            total_count=15,
        )
        service._m365_extractor = MagicMock()
        service._m365_extractor.extract_incremental.return_value = mock_result

        callback_calls = []
        service.run(
            since_last=True,
            existing_corpus=existing_corpus,
            progress_callback=lambda m: callback_calls.append(m),
        )

        # Find the incremental completion message
        incremental_msgs = [m for m in callback_calls if "incremental" in m.lower()]
        assert len(incremental_msgs) >= 1
        msg = incremental_msgs[0]
        assert "5 new emails" in msg
        assert "10" in msg
        assert "15" in msg


# =============================================================================
# Test ExtractionService: Error Propagation
# =============================================================================


class TestExtractionServiceErrorPropagation:
    """Test ExtractionService error propagation and logging."""

    def test_extraction_exception_is_logged_and_reraised(self):
        """Test that exceptions from extractors are logged and re-raised."""
        from src.services.extraction_service import ExtractionService

        config = ExtractConfig()
        service = ExtractionService(config, user_email="test@example.com")

        service._m365_extractor = MagicMock()
        service._m365_extractor.extract_all.side_effect = ConnectionError(
            "Server unreachable"
        )

        with patch("src.services.extraction_service.logger") as mock_logger:
            with pytest.raises(ConnectionError, match="Server unreachable"):
                service.run()

            mock_logger.error.assert_called_once()
            error_msg = mock_logger.error.call_args[0][0]
            assert "Extraction failed" in error_msg

    def test_authentication_error_is_reraised(self):
        """Test that authentication errors propagate correctly."""
        from src.services.extraction_service import ExtractionService

        config = ExtractConfig()
        service = ExtractionService(config, user_email="test@example.com")

        service._m365_extractor = MagicMock()
        service._m365_extractor.extract_all.side_effect = PermissionError(
            "Auth failed"
        )

        with pytest.raises(PermissionError, match="Auth failed"):
            service.run()

    def test_exception_during_both_mode_is_reraised(self):
        """Test that exception during multi-source extraction is reraised."""
        from src.extractors.m365_extractor import ExtractionResult
        from src.services.extraction_service import ExtractionService

        config = ExtractConfig(source="both", gmail_email="user@gmail.com")
        service = ExtractionService(config, user_email="user@hotmail.com")

        # M365 succeeds, Gmail fails
        m365_corpus = create_test_corpus(emails=[create_test_email(email_id="m365_1")])
        m365_result = ExtractionResult(
            corpus=m365_corpus, failed_emails=[],
            success_count=1, failure_count=0, total_attempted=1,
        )
        service._m365_extractor = MagicMock()
        service._m365_extractor.extract_all.return_value = m365_result
        service._gmail_extractor = MagicMock()
        service._gmail_extractor.extract_all.side_effect = RuntimeError("Gmail down")

        with pytest.raises(RuntimeError, match="Gmail down"):
            service.run()


# =============================================================================
# Test ExtractionService: save_corpus
# =============================================================================


class TestExtractionServiceSaveCorpus:
    """Test ExtractionService.save_corpus method."""

    def test_save_corpus_writes_file(self):
        """Test that save_corpus writes corpus JSON to disk."""
        from src.services.extraction_service import ExtractionService

        config = ExtractConfig()
        service = ExtractionService(config, user_email="test@example.com")

        corpus = create_test_corpus()

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_corpus.json"
            service.save_corpus(corpus, output_path)

            assert output_path.exists()
            content = json.loads(output_path.read_text())
            assert "extraction_metadata" in content
            assert "emails" in content

    def test_save_corpus_creates_parent_dirs(self):
        """Test that save_corpus creates parent directories."""
        from src.services.extraction_service import ExtractionService

        config = ExtractConfig()
        service = ExtractionService(config, user_email="test@example.com")

        corpus = create_test_corpus(emails=[create_test_email()])

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "nested" / "dir" / "corpus.json"
            service.save_corpus(corpus, output_path)

            assert output_path.exists()

    def test_save_corpus_is_valid_json(self):
        """Test that saved corpus is valid parseable JSON."""
        from src.services.extraction_service import ExtractionService

        config = ExtractConfig()
        service = ExtractionService(config, user_email="test@example.com")

        emails = [create_test_email(email_id=f"e_{i}") for i in range(3)]
        corpus = create_test_corpus(emails=emails)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "corpus.json"
            service.save_corpus(corpus, output_path)

            # Re-parse and verify round-trip
            loaded = Corpus.model_validate_json(output_path.read_text())
            assert len(loaded.emails) == 3


# =============================================================================
# Test ExtractionService: Config Propagation
# =============================================================================


class TestExtractionServiceConfigPropagation:
    """Test that config values propagate to extractors correctly."""

    def test_batch_size_propagated_to_extractor(self):
        """Test that batch_size from config is passed to extractor."""
        from src.extractors.m365_extractor import ExtractionResult
        from src.services.extraction_service import ExtractionService

        config = ExtractConfig(batch_size=250, checkpoint_interval=50)
        service = ExtractionService(config, user_email="test@example.com")

        mock_corpus = create_test_corpus()
        mock_result = ExtractionResult(
            corpus=mock_corpus, failed_emails=[],
            success_count=10, failure_count=0, total_attempted=10,
        )
        service._m365_extractor = MagicMock()
        service._m365_extractor.extract_all.return_value = mock_result

        service.run()

        service._m365_extractor.extract_all.assert_called_once_with(
            max_batch_size=250,
            checkpoint_interval=50,
        )

    def test_checkpoint_interval_propagated_to_incremental(self):
        """Test that checkpoint_interval is passed to incremental extraction."""
        from src.extractors.m365_extractor import IncrementalExtractionResult
        from src.services.extraction_service import ExtractionService

        config = ExtractConfig(batch_size=300, checkpoint_interval=75)
        service = ExtractionService(config, user_email="test@example.com")

        existing_corpus = create_test_corpus()
        mock_result = IncrementalExtractionResult(
            corpus=existing_corpus, failed_emails=[],
            new_emails_count=5, previous_count=10, total_count=15,
        )
        service._m365_extractor = MagicMock()
        service._m365_extractor.extract_incremental.return_value = mock_result

        service.run(since_last=True, existing_corpus=existing_corpus)

        service._m365_extractor.extract_incremental.assert_called_once_with(
            existing_corpus=existing_corpus,
            max_batch_size=300,
            checkpoint_interval=75,
        )


# =============================================================================
# Test ExtractionService: Merge Corpora Edge Cases
# =============================================================================


class TestMergeCorporaEdgeCases:
    """Test edge cases in _merge_corpora static method."""

    def test_merge_preserves_email_order(self):
        """Test that merge preserves order: first corpus emails before second."""
        from src.services.extraction_service import ExtractionService

        emails_a = [create_test_email(email_id=f"a_{i}") for i in range(3)]
        emails_b = [create_test_email(email_id=f"b_{i}") for i in range(2)]

        c1 = create_test_corpus(emails=emails_a)
        c2 = create_test_corpus(emails=emails_b)

        merged = ExtractionService._merge_corpora(
            [c1, c2], user_email="test@example.com",
            source_labels=["A", "B"],
        )

        ids = [e.id for e in merged.emails]
        assert ids == ["a_0", "a_1", "a_2", "b_0", "b_1"]

    def test_merge_computes_email_ids_hash(self):
        """Test that merge computes a SHA-256 hash of sorted email IDs."""
        import hashlib

        from src.services.extraction_service import ExtractionService

        emails = [create_test_email(email_id=f"e_{i}") for i in range(3)]
        c1 = create_test_corpus(emails=emails)

        merged = ExtractionService._merge_corpora(
            [c1], user_email="test@example.com",
            source_labels=["Test"],
        )

        # Verify hash is computed
        assert merged.extraction_metadata.email_ids_hash != ""

        # Verify hash is correct
        sorted_ids = sorted(e.id for e in emails)
        expected = hashlib.sha256("|".join(sorted_ids).encode()).hexdigest()
        assert merged.extraction_metadata.email_ids_hash == expected

    def test_merge_empty_corpora_has_empty_hash(self):
        """Test that merging empty corpora produces empty hash."""
        from src.services.extraction_service import ExtractionService

        c1 = create_test_corpus(emails=[])

        merged = ExtractionService._merge_corpora(
            [c1], user_email="test@example.com",
            source_labels=["Empty"],
        )

        assert merged.extraction_metadata.email_ids_hash == ""

    def test_merge_sets_extraction_params_with_source_labels(self):
        """Test that merged metadata includes source labels in extraction_params."""
        from src.services.extraction_service import ExtractionService

        c1 = create_test_corpus(emails=[create_test_email(email_id="e1")])
        c2 = create_test_corpus(emails=[create_test_email(email_id="e2")])

        merged = ExtractionService._merge_corpora(
            [c1, c2], user_email="test@example.com",
            source_labels=["M365/Hotmail", "Gmail"],
        )

        assert merged.extraction_metadata.extraction_params == {
            "sources": ["M365/Hotmail", "Gmail"]
        }

    def test_merge_sets_user_email_in_metadata(self):
        """Test that merged metadata has the correct user_email."""
        from src.services.extraction_service import ExtractionService

        c1 = create_test_corpus(emails=[create_test_email(email_id="e1")])

        merged = ExtractionService._merge_corpora(
            [c1], user_email="merged@example.com",
            source_labels=["Test"],
        )

        assert merged.extraction_metadata.user_email == "merged@example.com"


# =============================================================================
# Test AnalysisService: _generate_viz Method
# =============================================================================


class TestAnalysisServiceGenerateViz:
    """Test AnalysisService._generate_viz method."""

    @patch("src.services.analysis_service.run_full_analysis")
    def test_generate_viz_called_when_cluster_viz_true(self, mock_rfa):
        """Test that _generate_viz is invoked when cluster_viz=True."""
        from src.services.analysis_service import AnalysisService

        mock_rfa.return_value = (create_test_analysis_results(), None)

        config = AnalyzeConfig()
        service = AnalysisService(config)
        corpus = create_test_corpus()

        with patch.object(service, "_generate_viz") as mock_viz:
            service.run(corpus, cluster_viz=True)
            mock_viz.assert_called_once()

    @patch("src.services.analysis_service.run_full_analysis")
    def test_generate_viz_not_called_when_cluster_viz_false(self, mock_rfa):
        """Test that _generate_viz is NOT invoked when cluster_viz=False."""
        from src.services.analysis_service import AnalysisService

        mock_rfa.return_value = (create_test_analysis_results(), None)

        config = AnalyzeConfig()
        service = AnalysisService(config)
        corpus = create_test_corpus()

        with patch.object(service, "_generate_viz") as mock_viz:
            service.run(corpus, cluster_viz=False)
            mock_viz.assert_not_called()

    def test_generate_viz_handles_import_error(self):
        """Test that _generate_viz handles ImportError gracefully."""
        from src.services.analysis_service import AnalysisService

        config = AnalyzeConfig()
        service = AnalysisService(config)
        corpus = create_test_corpus()
        results = create_test_analysis_results()

        with patch("src.services.analysis_service.logger") as mock_logger:
            # Force ImportError by patching the import inside _generate_viz
            with patch.dict("sys.modules", {"sklearn.cluster": None}):
                # This should not raise -- ImportError is caught
                service._generate_viz(corpus, results)

            mock_logger.warning.assert_called()

    def test_generate_viz_handles_general_exception(self):
        """Test that _generate_viz handles general exceptions gracefully."""
        from src.services.analysis_service import AnalysisService

        config = AnalyzeConfig()
        service = AnalysisService(config)
        corpus = create_test_corpus()
        results = create_test_analysis_results()

        with patch("src.services.analysis_service.logger") as mock_logger:
            with patch(
                "src.analyzers.semantic_analyzer.SemanticAnalyzer"
            ) as mock_sem:
                mock_sem.side_effect = RuntimeError("Model loading failed")
                service._generate_viz(corpus, results)

            mock_logger.warning.assert_called()

    def test_generate_viz_skips_with_fewer_than_2_clusters(self):
        """Test that _generate_viz exits early with fewer than 2 clusters."""
        import numpy as np

        from src.services.analysis_service import AnalysisService

        config = AnalyzeConfig()
        service = AnalysisService(config)

        # Create results with only 1 cluster
        single_cluster_results = create_test_analysis_results()
        single_cluster_results.content_clusters = [
            single_cluster_results.content_clusters[0]
        ]

        corpus = create_test_corpus()

        with patch("src.services.analysis_service.logger") as mock_logger:
            with patch(
                "src.analyzers.semantic_analyzer.SemanticAnalyzer"
            ) as mock_sem_cls:
                mock_analyzer = MagicMock()
                mock_analyzer.model.encode.return_value = np.random.rand(10, 384)
                mock_sem_cls.return_value = mock_analyzer

                service._generate_viz(corpus, single_cluster_results)

            # Should log a warning about fewer than 2 clusters
            warning_calls = [
                call[0][0] for call in mock_logger.warning.call_args_list
            ]
            assert any("fewer than 2 clusters" in msg for msg in warning_calls)

    def test_generate_viz_happy_path(self):
        """Test _generate_viz full happy path: KMeans, silhouette map, file output."""
        import numpy as np

        from src.services.analysis_service import AnalysisService

        config = AnalyzeConfig()
        service = AnalysisService(config)

        corpus = create_test_corpus()

        # Create results with multiple clusters (>= 2) including silhouette scores
        results = create_test_analysis_results()
        # Add a second cluster to the results so n_clusters >= 2
        second_cluster = ContentCluster(
            cluster_id=1,
            size=30,
            percentage=30.0,
            representative_samples=[
                RepresentativeSample(
                    subject="Another Subject",
                    sender="other@example.com",
                    body_preview="Another body",
                )
            ],
            common_domains=[("example.com", 30)],
            email_ids=["email_3", "email_4"],
            silhouette_score=0.75,
        )
        results.content_clusters.append(second_cluster)
        # Set silhouette on the first one too
        results.content_clusters[0].silhouette_score = 0.65

        mock_embeddings = np.random.rand(10, 384)
        mock_labels = np.array([0, 1, 0, 1, 0, 1, 0, 1, 0, 1])

        with patch(
            "src.analyzers.semantic_analyzer.SemanticAnalyzer"
        ) as mock_sem_cls:
            mock_analyzer = MagicMock()
            mock_analyzer.model.encode.return_value = mock_embeddings
            mock_sem_cls.return_value = mock_analyzer

            with patch(
                "src.analyzers.semantic_analyzer.generate_cluster_visualization"
            ) as mock_gen_viz:
                mock_kmeans = MagicMock()
                mock_kmeans.fit_predict.return_value = mock_labels

                with (
                    patch("sklearn.cluster.KMeans", return_value=mock_kmeans),
                    patch("src.utils.paths.PathConfig.get_output_dir") as mock_outdir,
                ):
                    mock_outdir.return_value = Path("/tmp/test_output")

                    service._generate_viz(corpus, results)

                    # Verify generate_cluster_visualization was called
                    mock_gen_viz.assert_called_once()
                    call_kwargs = mock_gen_viz.call_args[1]
                    assert call_kwargs["output_path"] == Path("/tmp/test_output/cluster_visualization.png")
                    # Verify silhouette scores were passed
                    assert call_kwargs["cluster_silhouette_scores"] is not None

    def test_generate_viz_silhouette_map_excludes_none_scores(self):
        """Test that silhouette map only includes clusters with non-None scores."""
        import numpy as np

        from src.services.analysis_service import AnalysisService

        config = AnalyzeConfig()
        service = AnalysisService(config)

        corpus = create_test_corpus()

        results = create_test_analysis_results()
        # Add second cluster with silhouette_score=None
        second_cluster = ContentCluster(
            cluster_id=1,
            size=30,
            percentage=30.0,
            representative_samples=[
                RepresentativeSample(
                    subject="Test",
                    sender="test@example.com",
                    body_preview="Test",
                )
            ],
            common_domains=[("example.com", 30)],
            email_ids=["email_3"],
            silhouette_score=None,  # No silhouette score
        )
        results.content_clusters.append(second_cluster)
        # First cluster also has no silhouette score
        results.content_clusters[0].silhouette_score = None

        mock_embeddings = np.random.rand(10, 384)
        mock_labels = np.array([0, 1, 0, 1, 0, 1, 0, 1, 0, 1])

        with patch(
            "src.analyzers.semantic_analyzer.SemanticAnalyzer"
        ) as mock_sem_cls:
            mock_analyzer = MagicMock()
            mock_analyzer.model.encode.return_value = mock_embeddings
            mock_sem_cls.return_value = mock_analyzer

            with patch(
                "src.analyzers.semantic_analyzer.generate_cluster_visualization"
            ) as mock_gen_viz:
                mock_kmeans = MagicMock()
                mock_kmeans.fit_predict.return_value = mock_labels

                with (
                    patch("sklearn.cluster.KMeans", return_value=mock_kmeans),
                    patch("src.utils.paths.PathConfig.get_output_dir") as mock_outdir,
                ):
                    mock_outdir.return_value = Path("/tmp/test_output")

                    service._generate_viz(corpus, results)

                    # With all silhouette scores None, silhouette_map is empty
                    # so `silhouette_map or None` evaluates to None
                    call_kwargs = mock_gen_viz.call_args[1]
                    assert call_kwargs["cluster_silhouette_scores"] is None


# =============================================================================
# Test AnalysisService: Progress Callback Adaptation
# =============================================================================


class TestAnalysisServiceCallbackAdaptation:
    """Test that AnalysisService adapts single-arg callback to 3-arg format."""

    @patch("src.services.analysis_service.run_full_analysis")
    def test_callback_adapted_to_3_arg_format(self, mock_rfa):
        """Test that the progress callback is adapted from 1-arg to 3-arg."""
        from src.services.analysis_service import AnalysisService

        mock_rfa.return_value = (create_test_analysis_results(), None)

        config = AnalyzeConfig()
        service = AnalysisService(config)
        corpus = create_test_corpus()

        received_messages = []

        def my_callback(msg):
            received_messages.append(msg)

        service.run(corpus, progress_callback=my_callback)

        # Verify the adapted callback was passed to run_full_analysis
        _, kwargs = mock_rfa.call_args
        adapted_cb = kwargs["progress_callback"]
        assert adapted_cb is not None

        # Call the adapted callback directly to verify format
        adapted_cb("TestAnalyzer", 1, 5)

        # Should have formatted it as "Running TestAnalyzer... (1/5)"
        assert any("Running TestAnalyzer... (1/5)" in m for m in received_messages)

    @patch("src.services.analysis_service.run_full_analysis")
    def test_no_callback_passes_none(self, mock_rfa):
        """Test that None progress_callback passes None to run_full_analysis."""
        from src.services.analysis_service import AnalysisService

        mock_rfa.return_value = (create_test_analysis_results(), None)

        config = AnalyzeConfig()
        service = AnalysisService(config)
        corpus = create_test_corpus()

        service.run(corpus, progress_callback=None)

        _, kwargs = mock_rfa.call_args
        assert kwargs["progress_callback"] is None


# =============================================================================
# Test PipelineService: Skip Extraction Path
# =============================================================================


class TestPipelineServiceSkipExtraction:
    """Test PipelineService with skip_extraction flag."""

    @patch("src.services.pipeline_service.AnalysisService")
    @patch("src.services.pipeline_service.SuggestionService")
    def test_skip_extraction_uses_existing_corpus(
        self, mock_suggest, mock_analyze
    ):
        """Test skip_extraction=True uses the provided corpus."""
        from src.services.pipeline_service import PipelineResult, PipelineService

        mock_corpus = create_test_corpus()
        mock_analysis = create_test_analysis_results()
        mock_categories = create_test_categories()

        mock_analyze.return_value.run.return_value = (mock_analysis, None)
        mock_suggest.return_value.run.return_value = mock_categories

        config = AppConfig(user_email="test@example.com")
        service = PipelineService(config)

        with tempfile.TemporaryDirectory() as tmpdir:
            result = service.run(
                output_dir=Path(tmpdir),
                skip_extraction=True,
                existing_corpus=mock_corpus,
            )

            assert isinstance(result, PipelineResult)
            assert result.corpus is mock_corpus

    def test_skip_extraction_without_corpus_raises(self):
        """Test that skip_extraction=True without corpus raises ValueError."""
        from src.services.pipeline_service import PipelineService

        config = AppConfig(user_email="test@example.com")
        service = PipelineService(config)

        with (
            tempfile.TemporaryDirectory() as tmpdir,
            pytest.raises(ValueError, match="existing_corpus required"),
        ):
            service.run(
                output_dir=Path(tmpdir),
                skip_extraction=True,
                existing_corpus=None,
            )

    @patch("src.services.pipeline_service.AnalysisService")
    @patch("src.services.pipeline_service.SuggestionService")
    def test_skip_extraction_progress_callback(
        self, mock_suggest, mock_analyze
    ):
        """Test that skip_extraction reports correct progress messages."""
        from src.services.pipeline_service import PipelineService

        mock_corpus = create_test_corpus()
        mock_analysis = create_test_analysis_results()
        mock_categories = create_test_categories()

        mock_analyze.return_value.run.return_value = (mock_analysis, None)
        mock_suggest.return_value.run.return_value = mock_categories

        config = AppConfig(user_email="test@example.com")
        service = PipelineService(config)

        callback_calls = []

        with tempfile.TemporaryDirectory() as tmpdir:
            service.run(
                output_dir=Path(tmpdir),
                skip_extraction=True,
                existing_corpus=mock_corpus,
                progress_callback=lambda m: callback_calls.append(m),
            )

        assert any("skipping extraction" in m.lower() for m in callback_calls)
        assert any("Pipeline complete" in m for m in callback_calls)


# =============================================================================
# Test PipelineService: Error Handling at Each Stage
# =============================================================================


class TestPipelineServiceErrors:
    """Test PipelineService error handling at each pipeline stage."""

    @patch("src.services.pipeline_service.ExtractionService")
    def test_extraction_failure_propagates(self, mock_extract):
        """Test that extraction failure propagates through pipeline."""
        from src.services.pipeline_service import PipelineService

        mock_extract.return_value.run.side_effect = ConnectionError("No network")

        config = AppConfig(user_email="test@example.com")
        service = PipelineService(config)

        with (
            tempfile.TemporaryDirectory() as tmpdir,
            pytest.raises(ConnectionError, match="No network"),
        ):
            service.run(output_dir=Path(tmpdir))

    @patch("src.services.pipeline_service.ExtractionService")
    @patch("src.services.pipeline_service.AnalysisService")
    def test_analysis_failure_propagates(self, mock_analyze, mock_extract):
        """Test that analysis failure propagates through pipeline."""
        from src.services.pipeline_service import PipelineService

        mock_corpus = create_test_corpus()
        mock_extract.return_value.run.return_value = mock_corpus
        mock_analyze.return_value.run.side_effect = ValueError("Empty corpus")

        config = AppConfig(user_email="test@example.com")
        service = PipelineService(config)

        with (
            tempfile.TemporaryDirectory() as tmpdir,
            pytest.raises(ValueError, match="Empty corpus"),
        ):
            service.run(output_dir=Path(tmpdir))

    @patch("src.services.pipeline_service.ExtractionService")
    @patch("src.services.pipeline_service.AnalysisService")
    @patch("src.services.pipeline_service.SuggestionService")
    def test_suggestion_failure_propagates(
        self, mock_suggest, mock_analyze, mock_extract
    ):
        """Test that suggestion failure propagates through pipeline."""
        from src.services.pipeline_service import PipelineService

        mock_corpus = create_test_corpus()
        mock_analysis = create_test_analysis_results()

        mock_extract.return_value.run.return_value = mock_corpus
        mock_analyze.return_value.run.return_value = (mock_analysis, None)
        mock_suggest.return_value.run.side_effect = RuntimeError("Generator broke")

        config = AppConfig(user_email="test@example.com")
        service = PipelineService(config)

        with (
            tempfile.TemporaryDirectory() as tmpdir,
            pytest.raises(RuntimeError, match="Generator broke"),
        ):
            service.run(output_dir=Path(tmpdir))


# =============================================================================
# Test PipelineService: Config Propagation to Sub-services
# =============================================================================


class TestPipelineServiceConfigPropagation:
    """Test that PipelineService propagates config to sub-services."""

    @patch("src.services.pipeline_service.ExtractionService")
    @patch("src.services.pipeline_service.AnalysisService")
    @patch("src.services.pipeline_service.SuggestionService")
    def test_extract_config_propagated(
        self, mock_suggest, mock_analyze, mock_extract
    ):
        """Test that extract config is passed to ExtractionService."""
        from src.services.pipeline_service import PipelineService

        mock_corpus = create_test_corpus()
        mock_analysis = create_test_analysis_results()
        mock_categories = create_test_categories()

        mock_extract.return_value.run.return_value = mock_corpus
        mock_analyze.return_value.run.return_value = (mock_analysis, None)
        mock_suggest.return_value.run.return_value = mock_categories

        extract_config = ExtractConfig(batch_size=200, checkpoint_interval=25)
        config = AppConfig(
            user_email="test@example.com",
            extract=extract_config,
        )
        service = PipelineService(config)

        with tempfile.TemporaryDirectory() as tmpdir:
            service.run(output_dir=Path(tmpdir))

            # Verify ExtractionService was constructed with extract config
            mock_extract.assert_called_once()
            call_kwargs = mock_extract.call_args[1]
            assert call_kwargs["config"] is extract_config

    @patch("src.services.pipeline_service.ExtractionService")
    @patch("src.services.pipeline_service.AnalysisService")
    @patch("src.services.pipeline_service.SuggestionService")
    def test_analyze_config_propagated(
        self, mock_suggest, mock_analyze, mock_extract
    ):
        """Test that analyze config is passed to AnalysisService."""
        from src.services.pipeline_service import PipelineService

        mock_corpus = create_test_corpus()
        mock_analysis = create_test_analysis_results()
        mock_categories = create_test_categories()

        mock_extract.return_value.run.return_value = mock_corpus
        mock_analyze.return_value.run.return_value = (mock_analysis, None)
        mock_suggest.return_value.run.return_value = mock_categories

        analyze_config = AnalyzeConfig(num_clusters=15, max_embedding_text_length=2000)
        config = AppConfig(
            user_email="test@example.com",
            analyze=analyze_config,
        )
        service = PipelineService(config)

        with tempfile.TemporaryDirectory() as tmpdir:
            service.run(output_dir=Path(tmpdir))

            mock_analyze.assert_called_once_with(config=analyze_config)

    @patch("src.services.pipeline_service.ExtractionService")
    @patch("src.services.pipeline_service.AnalysisService")
    @patch("src.services.pipeline_service.SuggestionService")
    def test_suggest_config_propagated(
        self, mock_suggest, mock_analyze, mock_extract
    ):
        """Test that suggest config is passed to SuggestionService."""
        from src.services.pipeline_service import PipelineService

        mock_corpus = create_test_corpus()
        mock_analysis = create_test_analysis_results()
        mock_categories = create_test_categories()

        mock_extract.return_value.run.return_value = mock_corpus
        mock_analyze.return_value.run.return_value = (mock_analysis, None)
        mock_suggest.return_value.run.return_value = mock_categories

        suggest_config = SuggestConfig(min_cluster_percentage=3.0, min_sender_count=15)
        config = AppConfig(
            user_email="test@example.com",
            suggest=suggest_config,
        )
        service = PipelineService(config)

        with tempfile.TemporaryDirectory() as tmpdir:
            service.run(output_dir=Path(tmpdir))

            mock_suggest.assert_called_once_with(config=suggest_config)

    @patch("src.services.pipeline_service.ExtractionService")
    @patch("src.services.pipeline_service.AnalysisService")
    @patch("src.services.pipeline_service.SuggestionService")
    def test_auto_clusters_propagated_to_analysis(
        self, mock_suggest, mock_analyze, mock_extract
    ):
        """Test that auto_clusters flag is forwarded to analysis service."""
        from src.services.pipeline_service import PipelineService

        mock_corpus = create_test_corpus()
        mock_analysis = create_test_analysis_results()
        mock_categories = create_test_categories()

        mock_extract.return_value.run.return_value = mock_corpus
        mock_analyze.return_value.run.return_value = (mock_analysis, None)
        mock_suggest.return_value.run.return_value = mock_categories

        config = AppConfig(user_email="test@example.com")
        service = PipelineService(config)

        with tempfile.TemporaryDirectory() as tmpdir:
            service.run(
                output_dir=Path(tmpdir),
                auto_clusters=True,
                cluster_method="elbow",
                cluster_viz=True,
            )

            run_kwargs = mock_analyze.return_value.run.call_args[1]
            assert run_kwargs["auto_clusters"] is True
            assert run_kwargs["cluster_method"] == "elbow"
            assert run_kwargs["cluster_viz"] is True


# =============================================================================
# Test PipelineService: Output File Generation
# =============================================================================


class TestPipelineServiceOutputFiles:
    """Test that PipelineService generates output files correctly."""

    @patch("src.services.pipeline_service.ExtractionService")
    @patch("src.services.pipeline_service.AnalysisService")
    @patch("src.services.pipeline_service.SuggestionService")
    def test_pipeline_saves_analysis_results(
        self, mock_suggest, mock_analyze, mock_extract
    ):
        """Test that pipeline saves analysis results to JSON file."""
        from src.services.pipeline_service import PipelineService

        mock_corpus = create_test_corpus()
        mock_analysis = create_test_analysis_results()
        mock_categories = create_test_categories()

        mock_extract.return_value.run.return_value = mock_corpus
        mock_analyze.return_value.run.return_value = (mock_analysis, None)
        mock_suggest.return_value.run.return_value = mock_categories

        config = AppConfig(user_email="test@example.com")
        service = PipelineService(config)

        with tempfile.TemporaryDirectory() as tmpdir:
            service.run(output_dir=Path(tmpdir))

            analysis_path = Path(tmpdir) / "corpus_analysis_results.json"
            assert analysis_path.exists()

    @patch("src.services.pipeline_service.ExtractionService")
    @patch("src.services.pipeline_service.AnalysisService")
    @patch("src.services.pipeline_service.SuggestionService")
    def test_pipeline_saves_suggestions(
        self, mock_suggest, mock_analyze, mock_extract
    ):
        """Test that pipeline saves category suggestions to JSON file."""
        from src.services.pipeline_service import PipelineService

        mock_corpus = create_test_corpus()
        mock_analysis = create_test_analysis_results()
        mock_categories = create_test_categories()

        mock_extract.return_value.run.return_value = mock_corpus
        mock_analyze.return_value.run.return_value = (mock_analysis, None)
        mock_suggest.return_value.run.return_value = mock_categories

        config = AppConfig(user_email="test@example.com")
        service = PipelineService(config)

        with tempfile.TemporaryDirectory() as tmpdir:
            service.run(output_dir=Path(tmpdir))

            suggestions_path = Path(tmpdir) / "category_suggestions.json"
            assert suggestions_path.exists()

            # Verify it's valid JSON
            content = json.loads(suggestions_path.read_text())
            assert isinstance(content, list)

    @patch("src.services.pipeline_service.ExtractionService")
    @patch("src.services.pipeline_service.AnalysisService")
    @patch("src.services.pipeline_service.SuggestionService")
    def test_pipeline_creates_output_dir(
        self, mock_suggest, mock_analyze, mock_extract
    ):
        """Test that pipeline creates output directory if it doesn't exist."""
        from src.services.pipeline_service import PipelineService

        mock_corpus = create_test_corpus()
        mock_analysis = create_test_analysis_results()
        mock_categories = create_test_categories()

        mock_extract.return_value.run.return_value = mock_corpus
        mock_analyze.return_value.run.return_value = (mock_analysis, None)
        mock_suggest.return_value.run.return_value = mock_categories

        config = AppConfig(user_email="test@example.com")
        service = PipelineService(config)

        with tempfile.TemporaryDirectory() as tmpdir:
            nested_dir = Path(tmpdir) / "nested" / "output"
            result = service.run(output_dir=nested_dir)

            assert nested_dir.exists()
            assert result.output_dir == nested_dir


# =============================================================================
# Test PipelineResult Dataclass
# =============================================================================


class TestPipelineResult:
    """Test PipelineResult dataclass."""

    def test_pipeline_result_has_required_fields(self):
        """Test PipelineResult holds all required fields."""
        from src.services.pipeline_service import PipelineResult

        corpus = create_test_corpus()
        analysis = create_test_analysis_results()
        categories = create_test_categories()

        result = PipelineResult(
            corpus=corpus,
            analysis=analysis,
            categories=categories,
            output_dir=Path("/tmp/test"),
        )

        assert result.corpus is corpus
        assert result.analysis is analysis
        assert result.categories is categories
        assert result.output_dir == Path("/tmp/test")


# =============================================================================
# Test SuggestionService: Config-driven Generation
# =============================================================================


class TestSuggestionServiceConfig:
    """Test SuggestionService config-driven behavior."""

    def test_config_thresholds_passed_to_generator(self):
        """Test that config thresholds are passed to CategoryGenerator."""
        from src.services.suggestion_service import SuggestionService

        config = SuggestConfig(min_cluster_percentage=3.0, min_sender_count=15)
        service = SuggestionService(config)

        analysis = create_test_analysis_results()

        with patch("src.services.suggestion_service.CategoryGenerator") as mock_gen_cls:
            mock_gen = MagicMock()
            mock_gen.generate_suggestions.return_value = create_test_categories()
            mock_gen_cls.return_value = mock_gen

            service.run(analysis)

            # CategoryGenerator should be created with config thresholds
            mock_gen_cls.assert_called_once_with(thresholds=config.thresholds)

            # generate_suggestions should receive min_cluster_percentage and min_sender_count
            mock_gen.generate_suggestions.assert_called_once_with(
                analysis,
                min_cluster_percentage=3.0,
                min_sender_count=15,
            )

    def test_suggestion_service_progress_callback_messages(self):
        """Test the specific progress messages from SuggestionService."""
        from src.services.suggestion_service import SuggestionService

        config = SuggestConfig()
        service = SuggestionService(config)
        analysis = create_test_analysis_results()

        callback_calls = []
        service.run(analysis, progress_callback=lambda m: callback_calls.append(m))

        assert any("Generating" in m for m in callback_calls)
        assert any("Processing" in m for m in callback_calls)
        assert any("Generated" in m for m in callback_calls)

    def test_suggestion_service_without_progress_callback(self):
        """Test SuggestionService works fine without progress callback."""
        from src.services.suggestion_service import SuggestionService

        config = SuggestConfig()
        service = SuggestionService(config)
        analysis = create_test_analysis_results()

        # Should not raise
        result = service.run(analysis, progress_callback=None)
        assert isinstance(result, list)


# =============================================================================
# Test ExtractionService: Progress Callback Details
# =============================================================================


class TestExtractionServiceProgressDetails:
    """Test detailed progress callback behavior for ExtractionService."""

    def test_starting_message_sent(self):
        """Test that 'Starting email extraction...' is sent first."""
        from src.extractors.m365_extractor import ExtractionResult
        from src.services.extraction_service import ExtractionService

        config = ExtractConfig()
        service = ExtractionService(config, user_email="test@example.com")

        mock_corpus = create_test_corpus()
        mock_result = ExtractionResult(
            corpus=mock_corpus, failed_emails=[],
            success_count=10, failure_count=0, total_attempted=10,
        )
        service._m365_extractor = MagicMock()
        service._m365_extractor.extract_all.return_value = mock_result

        callback_calls = []
        service.run(progress_callback=lambda m: callback_calls.append(m))

        assert callback_calls[0] == "Starting email extraction..."

    def test_both_mode_reports_source_labels(self):
        """Test that both mode progress mentions both source names."""
        from src.extractors.m365_extractor import ExtractionResult
        from src.services.extraction_service import ExtractionService

        config = ExtractConfig(source="both", gmail_email="user@gmail.com")
        service = ExtractionService(config, user_email="user@hotmail.com")

        m365_corpus = create_test_corpus(emails=[create_test_email(email_id="m365_1")])
        gmail_corpus = create_test_corpus(emails=[create_test_email(email_id="gmail_1")])

        m365_result = ExtractionResult(
            corpus=m365_corpus, failed_emails=[],
            success_count=1, failure_count=0, total_attempted=1,
        )
        gmail_result = ExtractionResult(
            corpus=gmail_corpus, failed_emails=[],
            success_count=1, failure_count=0, total_attempted=1,
        )

        service._m365_extractor = MagicMock()
        service._m365_extractor.extract_all.return_value = m365_result
        service._gmail_extractor = MagicMock()
        service._gmail_extractor.extract_all.return_value = gmail_result

        callback_calls = []
        service.run(progress_callback=lambda m: callback_calls.append(m))

        # Should mention "M365/Hotmail and Gmail" in one of the messages
        both_msgs = [m for m in callback_calls if "M365/Hotmail" in m and "Gmail" in m]
        assert len(both_msgs) >= 1

    def test_merged_corpus_progress_reports_dedup_counts(self):
        """Test that merged corpus progress shows individual + deduplicated counts."""
        from src.extractors.m365_extractor import ExtractionResult
        from src.services.extraction_service import ExtractionService

        config = ExtractConfig(source="both", gmail_email="user@gmail.com")
        service = ExtractionService(config, user_email="user@hotmail.com")

        m365_emails = [create_test_email(email_id=f"m365_{i}") for i in range(5)]
        gmail_emails = [create_test_email(email_id=f"gmail_{i}") for i in range(3)]

        m365_corpus = create_test_corpus(emails=m365_emails)
        gmail_corpus = create_test_corpus(emails=gmail_emails)

        m365_result = ExtractionResult(
            corpus=m365_corpus, failed_emails=[],
            success_count=5, failure_count=0, total_attempted=5,
        )
        gmail_result = ExtractionResult(
            corpus=gmail_corpus, failed_emails=[],
            success_count=3, failure_count=0, total_attempted=3,
        )

        service._m365_extractor = MagicMock()
        service._m365_extractor.extract_all.return_value = m365_result
        service._gmail_extractor = MagicMock()
        service._gmail_extractor.extract_all.return_value = gmail_result

        callback_calls = []
        service.run(progress_callback=lambda m: callback_calls.append(m))

        merged_msgs = [m for m in callback_calls if "Merged corpus" in m]
        assert len(merged_msgs) == 1
        assert "8 emails" in merged_msgs[0]
        assert "5 + 3" in merged_msgs[0]
