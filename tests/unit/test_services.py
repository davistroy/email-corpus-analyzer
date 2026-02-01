"""
Unit tests for Track 7B: Service Layer.

Tests the service layer components:
- ExtractionService
- AnalysisService
- SuggestionService
- PipelineService
"""
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch
import json
import tempfile

import pytest

from src.config.models import (
    AnalyzeConfig,
    AppConfig,
    ExtractConfig,
    PipelineConfig,
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
    id: str = "test_001",
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
        id=id,
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
        emails = [create_test_email(id=f"email_{i}") for i in range(10)]
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
        """Test that run returns AnalysisResults."""
        import numpy as np

        from src.services.analysis_service import AnalysisService

        mock_model = MagicMock()
        mock_model.encode.return_value = np.random.rand(10, 384)
        mock_st.return_value = mock_model

        config = AnalyzeConfig(num_clusters=2)
        service = AnalysisService(config)
        corpus = create_test_corpus()

        result = service.run(corpus)

        assert isinstance(result, AnalysisResults)

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

        service.run(corpus, progress_callback=progress_callback)

        assert len(callback_calls) > 0

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
        from src.services.extraction_service import ExtractionService

        config = ExtractConfig()
        service = ExtractionService(config, user_email="test@example.com")

        # Mock the extractor
        mock_corpus = create_test_corpus()
        service._extractor = MagicMock()
        service._extractor.extract.return_value = mock_corpus

        result = service.run()

        assert isinstance(result, Corpus)

    def test_run_calls_progress_callback(self):
        """Test that run calls progress callback."""
        from src.services.extraction_service import ExtractionService

        config = ExtractConfig()
        service = ExtractionService(config, user_email="test@example.com")

        mock_corpus = create_test_corpus()
        service._extractor = MagicMock()
        service._extractor.extract.return_value = mock_corpus

        callback_calls = []

        def progress_callback(message: str):
            callback_calls.append(message)

        service.run(progress_callback=progress_callback)

        assert len(callback_calls) > 0


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
        import numpy as np

        from src.services.pipeline_service import PipelineResult, PipelineService

        # Setup mocks
        mock_corpus = create_test_corpus()
        mock_analysis = create_test_analysis_results()
        mock_categories = create_test_categories()

        mock_extract.return_value.run.return_value = mock_corpus
        mock_analyze.return_value.run.return_value = mock_analysis
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
        mock_analyze.return_value.run.return_value = mock_analysis
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
