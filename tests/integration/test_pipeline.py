"""
Integration tests for full pipeline workflow.

Tests the complete email analysis pipeline from corpus to suggestions.
Per Phase 7, Track 7C specification.
"""
import json
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.config.models import AnalyzeConfig, AppConfig, SuggestConfig
from src.models.corpus import Corpus, CorpusMetadata
from src.models.email import Email


# =============================================================================
# Test Fixtures
# =============================================================================


def create_diverse_emails(count: int = 50) -> list[Email]:
    """Create a diverse set of test emails for integration testing."""
    emails = []
    domains = ["amazon.com", "github.com", "linkedin.com", "newsletter.com", "work.com"]
    subjects_by_domain = {
        "amazon.com": ["Your order has shipped", "Order confirmation", "Delivery update"],
        "github.com": ["PR review requested", "Issue opened", "Build failed"],
        "linkedin.com": ["New connection request", "Job alert", "Who's viewed your profile"],
        "newsletter.com": ["Weekly digest", "Top stories", "Breaking news"],
        "work.com": ["Meeting invite", "Project update", "Action required"],
    }

    for i in range(count):
        domain = domains[i % len(domains)]
        subjects = subjects_by_domain[domain]
        subject = subjects[i % len(subjects)] + f" #{i}"

        emails.append(
            Email(
                id=f"email_{i:04d}",
                sender_email=f"sender{i % 10}@{domain}",
                sender_name=f"Sender {i % 10}",
                sender_domain=domain,
                subject=subject,
                body_text=f"This is the body text for email {i}. It contains some content related to {domain}.",
                received_date=datetime(2024, 1, (i % 28) + 1, 10, i % 60),
                has_attachments=i % 5 == 0,
            )
        )

    return emails


def create_test_corpus(emails: list[Email] | None = None) -> Corpus:
    """Create a test corpus for integration testing."""
    if emails is None:
        emails = create_diverse_emails(50)

    return Corpus(
        extraction_metadata=CorpusMetadata(
            extraction_date=datetime.now(),
            total_emails=len(emails),
            source="test",
            user_email="test@example.com",
        ),
        emails=emails,
    )


@pytest.fixture
def temp_output_dir():
    """Create a temporary output directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_corpus():
    """Create a sample corpus with 50 diverse emails."""
    return create_test_corpus()


# =============================================================================
# Test Full Pipeline Integration
# =============================================================================


class TestFullPipeline:
    """Integration tests for full pipeline workflow."""

    @patch("src.analyzers.semantic_analyzer.SentenceTransformer")
    def test_pipeline_produces_all_outputs(self, mock_st, temp_output_dir, sample_corpus):
        """Test that pipeline produces corpus, analysis, and suggestions files."""
        from src.services.analysis_service import AnalysisService
        from src.services.suggestion_service import SuggestionService

        # Mock semantic analyzer
        mock_model = MagicMock()
        mock_model.encode.return_value = np.random.rand(50, 384)
        mock_st.return_value = mock_model

        # Run analysis
        analysis_config = AnalyzeConfig(num_clusters=5)
        analysis_service = AnalysisService(analysis_config)
        analysis, _stats = analysis_service.run(sample_corpus)

        # Run suggestion
        suggest_config = SuggestConfig(min_cluster_percentage=5.0, min_sender_count=5)
        suggest_service = SuggestionService(suggest_config)
        categories = suggest_service.run(analysis)

        # Save outputs
        corpus_path = temp_output_dir / "email_corpus.json"
        corpus_path.write_text(sample_corpus.model_dump_json(indent=2))

        analysis_path = temp_output_dir / "corpus_analysis_results.json"
        analysis_path.write_text(analysis.model_dump_json(indent=2))

        suggestions_path = temp_output_dir / "category_suggestions.json"
        suggestions_path.write_text(
            "[" + ",\n".join(c.model_dump_json() for c in categories) + "]"
        )

        # Verify all files exist
        assert corpus_path.exists()
        assert analysis_path.exists()
        assert suggestions_path.exists()

        # Verify file contents are valid JSON
        json.loads(corpus_path.read_text())
        json.loads(analysis_path.read_text())
        json.loads(suggestions_path.read_text())

    @patch("src.analyzers.semantic_analyzer.SentenceTransformer")
    def test_pipeline_analysis_contains_all_components(
        self, mock_st, sample_corpus
    ):
        """Test that analysis contains all required components."""
        from src.services.analysis_service import AnalysisService

        mock_model = MagicMock()
        mock_model.encode.return_value = np.random.rand(50, 384)
        mock_st.return_value = mock_model

        analysis_config = AnalyzeConfig(num_clusters=5)
        analysis_service = AnalysisService(analysis_config)
        analysis, _stats = analysis_service.run(sample_corpus)

        # Verify all analysis components
        assert analysis.sender_analysis is not None
        assert analysis.subject_patterns is not None
        assert analysis.content_clusters is not None
        assert analysis.temporal_patterns is not None
        assert analysis.volume_stats is not None

        # Verify reasonable values
        assert analysis.volume_stats.total_emails == 50
        assert analysis.sender_analysis.unique_senders > 0
        assert len(analysis.content_clusters) > 0

    @patch("src.analyzers.semantic_analyzer.SentenceTransformer")
    def test_pipeline_suggestions_have_valid_structure(
        self, mock_st, sample_corpus
    ):
        """Test that suggestions have valid category structure."""
        from src.services.analysis_service import AnalysisService
        from src.services.suggestion_service import SuggestionService

        mock_model = MagicMock()
        mock_model.encode.return_value = np.random.rand(50, 384)
        mock_st.return_value = mock_model

        analysis_config = AnalyzeConfig(num_clusters=5)
        analysis_service = AnalysisService(analysis_config)
        analysis, _stats = analysis_service.run(sample_corpus)

        suggest_config = SuggestConfig(min_cluster_percentage=5.0, min_sender_count=5)
        suggest_service = SuggestionService(suggest_config)
        categories = suggest_service.run(analysis)

        # Verify category structure
        for category in categories:
            assert category.category_id is not None
            assert category.category_name is not None
            assert category.confidence >= 0.0 and category.confidence <= 1.0
            assert category.source is not None

    @patch("src.analyzers.semantic_analyzer.SentenceTransformer")
    def test_pipeline_with_progress_callback(
        self, mock_st, sample_corpus
    ):
        """Test that progress callbacks are called throughout pipeline."""
        from src.services.analysis_service import AnalysisService
        from src.services.suggestion_service import SuggestionService

        mock_model = MagicMock()
        mock_model.encode.return_value = np.random.rand(50, 384)
        mock_st.return_value = mock_model

        callback_messages = []

        def progress_callback(msg: str):
            callback_messages.append(msg)

        # Run analysis with callback
        analysis_config = AnalyzeConfig(num_clusters=5)
        analysis_service = AnalysisService(analysis_config)
        analysis, _stats = analysis_service.run(sample_corpus, progress_callback=progress_callback)

        # Run suggestion with callback
        suggest_config = SuggestConfig()
        suggest_service = SuggestionService(suggest_config)
        suggest_service.run(analysis, progress_callback=progress_callback)

        # Verify callbacks were called
        assert len(callback_messages) > 0
        assert any("analysis" in msg.lower() or "analyzer" in msg.lower() for msg in callback_messages)


class TestPipelineEdgeCases:
    """Test pipeline behavior with edge cases."""

    @patch("src.analyzers.semantic_analyzer.SentenceTransformer")
    def test_pipeline_with_single_email(self, mock_st):
        """Test pipeline handles single email corpus."""
        from src.services.analysis_service import AnalysisService

        mock_model = MagicMock()
        mock_model.encode.return_value = np.random.rand(1, 384)
        mock_st.return_value = mock_model

        emails = [
            Email(
                id="email_001",
                sender_email="sender@example.com",
                sender_name="Sender",
                sender_domain="example.com",
                subject="Single email",
                body_text="This is the only email in the corpus.",
                received_date=datetime(2024, 1, 15, 10, 30),
                has_attachments=False,
            )
        ]
        corpus = create_test_corpus(emails)

        analysis_config = AnalyzeConfig(num_clusters=1)
        analysis_service = AnalysisService(analysis_config)
        analysis, _stats = analysis_service.run(corpus)

        assert analysis.volume_stats.total_emails == 1
        assert analysis.sender_analysis.unique_senders == 1

    def test_pipeline_with_empty_corpus_raises_error(self):
        """Test pipeline raises error on empty corpus."""
        from src.services.analysis_service import AnalysisService

        corpus = create_test_corpus(emails=[])

        analysis_config = AnalyzeConfig(num_clusters=5)
        analysis_service = AnalysisService(analysis_config)

        with pytest.raises(ValueError, match="empty"):
            analysis_service.run(corpus)

    @patch("src.analyzers.semantic_analyzer.SentenceTransformer")
    def test_pipeline_with_uniform_sender_domain(self, mock_st):
        """Test pipeline handles corpus with all emails from same domain."""
        from src.services.analysis_service import AnalysisService

        mock_model = MagicMock()
        mock_model.encode.return_value = np.random.rand(20, 384)
        mock_st.return_value = mock_model

        emails = [
            Email(
                id=f"email_{i:03d}",
                sender_email=f"sender{i}@singledomain.com",
                sender_name=f"Sender {i}",
                sender_domain="singledomain.com",
                subject=f"Email subject {i}",
                body_text=f"Body text for email {i}",
                received_date=datetime(2024, 1, i % 28 + 1, 10, 30),
                has_attachments=False,
            )
            for i in range(20)
        ]
        corpus = create_test_corpus(emails)

        analysis_config = AnalyzeConfig(num_clusters=3)
        analysis_service = AnalysisService(analysis_config)
        analysis, _stats = analysis_service.run(corpus)

        # All emails from same domain
        assert analysis.sender_analysis.unique_domains == 1


class TestDataPersistence:
    """Test data persistence and reload capabilities."""

    @patch("src.analyzers.semantic_analyzer.SentenceTransformer")
    def test_corpus_roundtrip(self, mock_st, temp_output_dir, sample_corpus):
        """Test corpus can be saved and reloaded correctly."""
        # Save corpus
        corpus_path = temp_output_dir / "email_corpus.json"
        corpus_path.write_text(sample_corpus.model_dump_json(indent=2))

        # Reload corpus
        loaded_data = json.loads(corpus_path.read_text())
        loaded_corpus = Corpus.model_validate(loaded_data)

        # Verify data integrity
        assert loaded_corpus.extraction_metadata.total_emails == sample_corpus.extraction_metadata.total_emails
        assert len(loaded_corpus.emails) == len(sample_corpus.emails)

        for orig, loaded in zip(sample_corpus.emails, loaded_corpus.emails):
            assert orig.id == loaded.id
            assert orig.sender_email == loaded.sender_email
            assert orig.subject == loaded.subject

    @patch("src.analyzers.semantic_analyzer.SentenceTransformer")
    def test_analysis_roundtrip(self, mock_st, temp_output_dir, sample_corpus):
        """Test analysis can be saved and reloaded correctly."""
        from src.models.analysis_results import AnalysisResults
        from src.services.analysis_service import AnalysisService

        mock_model = MagicMock()
        mock_model.encode.return_value = np.random.rand(50, 384)
        mock_st.return_value = mock_model

        # Run analysis
        analysis_config = AnalyzeConfig(num_clusters=5)
        analysis_service = AnalysisService(analysis_config)
        analysis, _stats = analysis_service.run(sample_corpus)

        # Save analysis
        analysis_path = temp_output_dir / "corpus_analysis_results.json"
        analysis_path.write_text(analysis.model_dump_json(indent=2))

        # Reload analysis
        loaded_data = json.loads(analysis_path.read_text())
        loaded_analysis = AnalysisResults.model_validate(loaded_data)

        # Verify data integrity
        assert loaded_analysis.volume_stats.total_emails == analysis.volume_stats.total_emails
        assert len(loaded_analysis.content_clusters) == len(analysis.content_clusters)
        assert loaded_analysis.sender_analysis.unique_senders == analysis.sender_analysis.unique_senders
