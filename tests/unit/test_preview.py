"""
Unit tests for preview/estimators module.

Tests cover:
- ExtractEstimator - Estimates for email extraction
- AnalyzeEstimator - Estimates for corpus analysis
- SuggestEstimator - Estimates for category suggestion
- ReviewEstimator - Estimates for category review
- Estimate data models
- Preview output formatting

Uses mocking to avoid real file I/O, network calls, and external dependencies.
Following TDD - these tests are written before implementation.
"""

import argparse
from pathlib import Path
from unittest.mock import patch

import pytest


class TestEstimateModels:
    """Test cases for Estimate data models."""

    def test_extract_estimate_model_exists(self):
        """Test that ExtractEstimate model can be imported and instantiated."""
        from src.preview.estimators import ExtractEstimate

        estimate = ExtractEstimate(
            user_email="test@example.com",
            output_path=Path("/output/corpus.json"),
            email_count_estimate=None,  # Unknown without M365 connection
            output_size_estimate=None,
            duration_estimate=None,
        )

        assert estimate.user_email == "test@example.com"
        assert estimate.output_path == Path("/output/corpus.json")
        assert estimate.email_count_estimate is None

    def test_analyze_estimate_model_exists(self):
        """Test that AnalyzeEstimate model can be imported and instantiated."""
        from src.preview.estimators import AnalyzeEstimate

        estimate = AnalyzeEstimate(
            corpus_path=Path("/output/corpus.json"),
            corpus_exists=True,
            corpus_size_bytes=47185920,  # ~45 MB
            email_count=5432,
            output_path=Path("/output/analysis.json"),
            embedding_time_estimate_seconds=543.2,  # ~9 minutes
            clustering_time_estimate_seconds=7.5,
            output_size_estimate_bytes=3145728,  # ~3 MB
        )

        assert estimate.corpus_exists is True
        assert estimate.email_count == 5432
        assert estimate.embedding_time_estimate_seconds == pytest.approx(543.2)

    def test_suggest_estimate_model_exists(self):
        """Test that SuggestEstimate model can be imported and instantiated."""
        from src.preview.estimators import SuggestEstimate

        estimate = SuggestEstimate(
            analysis_path=Path("/output/analysis.json"),
            analysis_exists=True,
            output_path=Path("/output/suggestions.json"),
            duration_estimate_seconds=5.0,
            output_size_estimate_bytes=102400,  # ~100 KB
        )

        assert estimate.analysis_exists is True
        assert estimate.duration_estimate_seconds == 5.0

    def test_review_estimate_model_exists(self):
        """Test that ReviewEstimate model can be imported and instantiated."""
        from src.preview.estimators import ReviewEstimate

        estimate = ReviewEstimate(
            suggestions_path=Path("/output/suggestions.json"),
            suggestions_exists=True,
            category_count=15,
            output_path=Path("/output/approved.json"),
        )

        assert estimate.suggestions_exists is True
        assert estimate.category_count == 15

    def test_pipeline_estimate_model_exists(self):
        """Test that PipelineEstimate model can be imported and instantiated."""
        from src.preview.estimators import (
            AnalyzeEstimate,
            ExtractEstimate,
            PipelineEstimate,
            ReviewEstimate,
            SuggestEstimate,
        )

        extract = ExtractEstimate(
            user_email="test@example.com",
            output_path=Path("/output/corpus.json"),
        )
        analyze = AnalyzeEstimate(
            corpus_path=Path("/output/corpus.json"),
            corpus_exists=False,
            output_path=Path("/output/analysis.json"),
        )
        suggest = SuggestEstimate(
            analysis_path=Path("/output/analysis.json"),
            analysis_exists=False,
            output_path=Path("/output/suggestions.json"),
        )
        review = ReviewEstimate(
            suggestions_path=Path("/output/suggestions.json"),
            suggestions_exists=False,
            output_path=Path("/output/approved.json"),
        )

        pipeline = PipelineEstimate(
            extract=extract,
            analyze=analyze,
            suggest=suggest,
            review=review,
        )

        assert pipeline.extract.user_email == "test@example.com"
        assert pipeline.analyze.corpus_exists is False


class TestExtractEstimator:
    """Test cases for ExtractEstimator class."""

    def test_extract_estimator_can_be_instantiated(self):
        """Test ExtractEstimator can be created."""
        from src.preview.estimators import ExtractEstimator

        estimator = ExtractEstimator()
        assert estimator is not None

    @patch("src.preview.estimators.PathConfig")
    def test_extract_estimator_estimate_returns_extract_estimate(self, mock_path_config):
        """Test that estimate() returns ExtractEstimate."""
        from src.preview.estimators import ExtractEstimate, ExtractEstimator

        mock_path_config.get_corpus_path.return_value = Path("/output/corpus.json")

        estimator = ExtractEstimator()
        args = argparse.Namespace(
            user_email="test@example.com",
            corpus_file=None,
            batch_size=500,
            checkpoint_interval=100,
        )

        estimate = estimator.estimate(args)

        assert isinstance(estimate, ExtractEstimate)
        assert estimate.user_email == "test@example.com"
        assert estimate.output_path == Path("/output/corpus.json")

    @patch("src.preview.estimators.PathConfig")
    def test_extract_estimator_uses_custom_corpus_path(self, mock_path_config):
        """Test ExtractEstimator uses custom corpus path when provided."""
        from src.preview.estimators import ExtractEstimator

        estimator = ExtractEstimator()
        args = argparse.Namespace(
            user_email="test@example.com",
            corpus_file=Path("/custom/corpus.json"),
            batch_size=500,
            checkpoint_interval=100,
        )

        estimate = estimator.estimate(args)

        assert estimate.output_path == Path("/custom/corpus.json")
        mock_path_config.get_corpus_path.assert_not_called()

    def test_extract_estimator_email_count_is_none_without_connection(self):
        """Test email count estimate is None without M365 connection."""
        from src.preview.estimators import ExtractEstimator

        estimator = ExtractEstimator()
        args = argparse.Namespace(
            user_email="test@example.com",
            corpus_file=Path("/output/corpus.json"),
            batch_size=500,
            checkpoint_interval=100,
        )

        estimate = estimator.estimate(args)

        # Without M365 connection, we can't know how many emails
        assert estimate.email_count_estimate is None
        assert estimate.output_size_estimate is None
        assert estimate.duration_estimate is None


class TestAnalyzeEstimator:
    """Test cases for AnalyzeEstimator class."""

    def test_analyze_estimator_can_be_instantiated(self):
        """Test AnalyzeEstimator can be created."""
        from src.preview.estimators import AnalyzeEstimator

        estimator = AnalyzeEstimator()
        assert estimator is not None

    @patch("src.preview.estimators.PathConfig")
    def test_analyze_estimator_estimate_returns_analyze_estimate(self, mock_path_config):
        """Test that estimate() returns AnalyzeEstimate."""
        from src.preview.estimators import AnalyzeEstimate, AnalyzeEstimator

        mock_path_config.get_corpus_path.return_value = Path("/output/corpus.json")
        mock_path_config.get_analysis_path.return_value = Path("/output/analysis.json")

        estimator = AnalyzeEstimator()
        args = argparse.Namespace(
            corpus=None,
            num_clusters=10,
            analysis_file=None,
        )

        # Corpus doesn't exist
        with patch.object(Path, "exists", return_value=False):
            estimate = estimator.estimate(args)

        assert isinstance(estimate, AnalyzeEstimate)
        assert estimate.corpus_exists is False

    @patch("src.preview.estimators.PathConfig")
    @patch("src.preview.estimators.load_json")
    def test_analyze_estimator_with_existing_corpus(self, mock_load_json, mock_path_config):
        """Test AnalyzeEstimator with existing corpus file."""
        from src.preview.estimators import AnalyzeEstimator

        corpus_path = Path("/output/corpus.json")
        mock_path_config.get_corpus_path.return_value = corpus_path
        mock_path_config.get_analysis_path.return_value = Path("/output/analysis.json")

        # Mock corpus data
        mock_load_json.return_value = {
            "emails": [{"id": f"email_{i}"} for i in range(5432)],
            "extraction_metadata": {
                "extraction_date": "2024-01-01T00:00:00",
                "total_emails": 5432,
                "source": "m365",
                "user_email": "test@example.com",
            },
        }

        estimator = AnalyzeEstimator()
        args = argparse.Namespace(
            corpus=None,
            num_clusters=10,
            analysis_file=None,
        )

        # Mock file existence and size
        with (
            patch.object(Path, "exists", return_value=True),
            patch.object(Path, "stat") as mock_stat,
        ):
            mock_stat.return_value.st_size = 47185920  # ~45 MB
            estimate = estimator.estimate(args)

        assert estimate.corpus_exists is True
        assert estimate.email_count == 5432
        assert estimate.corpus_size_bytes == 47185920

    @patch("src.preview.estimators.PathConfig")
    @patch("src.preview.estimators.load_json")
    def test_analyze_estimator_calculates_time_estimates(self, mock_load_json, mock_path_config):
        """Test AnalyzeEstimator calculates time estimates based on email count."""
        from src.preview.estimators import AnalyzeEstimator

        corpus_path = Path("/output/corpus.json")
        mock_path_config.get_corpus_path.return_value = corpus_path
        mock_path_config.get_analysis_path.return_value = Path("/output/analysis.json")

        # 5432 emails at ~0.1s each = ~543 seconds for embeddings
        mock_load_json.return_value = {
            "emails": [{"id": f"email_{i}"} for i in range(5432)],
            "extraction_metadata": {
                "extraction_date": "2024-01-01T00:00:00",
                "total_emails": 5432,
                "source": "m365",
                "user_email": "test@example.com",
            },
        }

        estimator = AnalyzeEstimator()
        args = argparse.Namespace(
            corpus=None,
            num_clusters=10,
            analysis_file=None,
        )

        with (
            patch.object(Path, "exists", return_value=True),
            patch.object(Path, "stat") as mock_stat,
        ):
            mock_stat.return_value.st_size = 47185920
            estimate = estimator.estimate(args)

        # Embedding time ~0.1s per email
        assert estimate.embedding_time_estimate_seconds is not None
        assert estimate.embedding_time_estimate_seconds > 500  # > 500 seconds for 5432 emails
        # Clustering time scales with email count (5s base + ~2s per 1000 emails)
        assert estimate.clustering_time_estimate_seconds is not None
        assert 5 <= estimate.clustering_time_estimate_seconds <= 20

    @patch("src.preview.estimators.PathConfig")
    def test_analyze_estimator_uses_custom_paths(self, mock_path_config):
        """Test AnalyzeEstimator uses custom paths when provided."""
        from src.preview.estimators import AnalyzeEstimator

        estimator = AnalyzeEstimator()
        args = argparse.Namespace(
            corpus=Path("/custom/corpus.json"),
            num_clusters=10,
            analysis_file=Path("/custom/analysis.json"),
        )

        with patch.object(Path, "exists", return_value=False):
            estimate = estimator.estimate(args)

        assert estimate.corpus_path == Path("/custom/corpus.json")
        assert estimate.output_path == Path("/custom/analysis.json")
        mock_path_config.get_corpus_path.assert_not_called()
        mock_path_config.get_analysis_path.assert_not_called()


class TestSuggestEstimator:
    """Test cases for SuggestEstimator class."""

    def test_suggest_estimator_can_be_instantiated(self):
        """Test SuggestEstimator can be created."""
        from src.preview.estimators import SuggestEstimator

        estimator = SuggestEstimator()
        assert estimator is not None

    @patch("src.preview.estimators.PathConfig")
    def test_suggest_estimator_estimate_returns_suggest_estimate(self, mock_path_config):
        """Test that estimate() returns SuggestEstimate."""
        from src.preview.estimators import SuggestEstimate, SuggestEstimator

        mock_path_config.get_analysis_path.return_value = Path("/output/analysis.json")
        mock_path_config.get_suggestions_path.return_value = Path("/output/suggestions.json")

        estimator = SuggestEstimator()
        args = argparse.Namespace(
            analysis=None,
            min_cluster_percentage=5.0,
            min_sender_count=20,
            suggestions_file=None,
        )

        with patch.object(Path, "exists", return_value=False):
            estimate = estimator.estimate(args)

        assert isinstance(estimate, SuggestEstimate)
        assert estimate.analysis_exists is False

    @patch("src.preview.estimators.PathConfig")
    def test_suggest_estimator_with_existing_analysis(self, mock_path_config):
        """Test SuggestEstimator with existing analysis file."""
        from src.preview.estimators import SuggestEstimator

        mock_path_config.get_analysis_path.return_value = Path("/output/analysis.json")
        mock_path_config.get_suggestions_path.return_value = Path("/output/suggestions.json")

        estimator = SuggestEstimator()
        args = argparse.Namespace(
            analysis=None,
            min_cluster_percentage=5.0,
            min_sender_count=20,
            suggestions_file=None,
        )

        with (
            patch.object(Path, "exists", return_value=True),
            patch.object(Path, "stat") as mock_stat,
        ):
            mock_stat.return_value.st_size = 2097152  # 2 MB
            estimate = estimator.estimate(args)

        assert estimate.analysis_exists is True
        # Suggest is fast - typically < 10 seconds
        assert estimate.duration_estimate_seconds is not None
        assert estimate.duration_estimate_seconds < 30


class TestReviewEstimator:
    """Test cases for ReviewEstimator class."""

    def test_review_estimator_can_be_instantiated(self):
        """Test ReviewEstimator can be created."""
        from src.preview.estimators import ReviewEstimator

        estimator = ReviewEstimator()
        assert estimator is not None

    @patch("src.preview.estimators.PathConfig")
    def test_review_estimator_estimate_returns_review_estimate(self, mock_path_config):
        """Test that estimate() returns ReviewEstimate."""
        from src.preview.estimators import ReviewEstimate, ReviewEstimator

        mock_path_config.get_suggestions_path.return_value = Path("/output/suggestions.json")
        mock_path_config.get_approved_categories_path.return_value = Path("/output/approved.json")

        estimator = ReviewEstimator()
        args = argparse.Namespace(
            suggestions=None,
            approved_file=None,
            no_cleanup=False,
        )

        with patch.object(Path, "exists", return_value=False):
            estimate = estimator.estimate(args)

        assert isinstance(estimate, ReviewEstimate)
        assert estimate.suggestions_exists is False

    @patch("src.preview.estimators.PathConfig")
    @patch("src.preview.estimators.load_json")
    def test_review_estimator_with_existing_suggestions(self, mock_load_json, mock_path_config):
        """Test ReviewEstimator with existing suggestions file."""
        from src.preview.estimators import ReviewEstimator

        mock_path_config.get_suggestions_path.return_value = Path("/output/suggestions.json")
        mock_path_config.get_approved_categories_path.return_value = Path("/output/approved.json")

        # 15 category suggestions
        mock_load_json.return_value = [{"category_id": f"cat_{i}"} for i in range(15)]

        estimator = ReviewEstimator()
        args = argparse.Namespace(
            suggestions=None,
            approved_file=None,
            no_cleanup=False,
        )

        with patch.object(Path, "exists", return_value=True):
            estimate = estimator.estimate(args)

        assert estimate.suggestions_exists is True
        assert estimate.category_count == 15


class TestPipelineEstimator:
    """Test cases for PipelineEstimator class."""

    def test_pipeline_estimator_can_be_instantiated(self):
        """Test PipelineEstimator can be created."""
        from src.preview.estimators import PipelineEstimator

        estimator = PipelineEstimator()
        assert estimator is not None

    @patch("src.preview.estimators.PathConfig")
    def test_pipeline_estimator_estimate_returns_pipeline_estimate(self, mock_path_config):
        """Test that estimate() returns PipelineEstimate."""
        from src.preview.estimators import PipelineEstimate, PipelineEstimator

        mock_path_config.get_corpus_path.return_value = Path("/output/corpus.json")
        mock_path_config.get_analysis_path.return_value = Path("/output/analysis.json")
        mock_path_config.get_suggestions_path.return_value = Path("/output/suggestions.json")
        mock_path_config.get_approved_categories_path.return_value = Path("/output/approved.json")

        estimator = PipelineEstimator()
        args = argparse.Namespace(
            user_email="test@example.com",
            num_clusters=10,
            no_cleanup=False,
            skip_review=False,
            output_dir=None,
        )

        with patch.object(Path, "exists", return_value=False):
            estimate = estimator.estimate(args)

        assert isinstance(estimate, PipelineEstimate)
        assert estimate.extract.user_email == "test@example.com"


class TestPreviewFormatters:
    """Test cases for preview output formatters."""

    def test_format_extract_preview_basic(self):
        """Test basic extract preview formatting."""
        from src.preview.estimators import ExtractEstimate, format_extract_preview

        estimate = ExtractEstimate(
            user_email="user@example.com",
            output_path=Path("/home/user/data/outputs/email_corpus.json"),
        )

        output = format_extract_preview(estimate)

        assert "[DRY RUN] extract" in output
        assert "user@example.com" in output
        assert "email_corpus.json" in output
        assert "No changes will be made" in output

    def test_format_analyze_preview_no_corpus(self):
        """Test analyze preview when corpus doesn't exist."""
        from src.preview.estimators import AnalyzeEstimate, format_analyze_preview

        estimate = AnalyzeEstimate(
            corpus_path=Path("/output/corpus.json"),
            corpus_exists=False,
            output_path=Path("/output/analysis.json"),
        )

        output = format_analyze_preview(estimate)

        assert "[DRY RUN] analyze" in output
        assert "corpus.json" in output
        assert "not found" in output.lower() or "does not exist" in output.lower()

    def test_format_analyze_preview_with_corpus(self):
        """Test analyze preview with existing corpus."""
        from src.preview.estimators import AnalyzeEstimate, format_analyze_preview

        estimate = AnalyzeEstimate(
            corpus_path=Path("/output/corpus.json"),
            corpus_exists=True,
            corpus_size_bytes=47395430,  # ~45.2 MB
            email_count=5432,
            output_path=Path("/output/analysis.json"),
            embedding_time_estimate_seconds=543.2,
            clustering_time_estimate_seconds=7.5,
            output_size_estimate_bytes=3145728,
        )

        output = format_analyze_preview(estimate)

        assert "[DRY RUN] analyze" in output
        assert "5432" in output or "5,432" in output
        assert "45" in output  # ~45 MB
        assert "9 min" in output.lower() or "543" in output  # ~9 minutes

    def test_format_suggest_preview(self):
        """Test suggest preview formatting."""
        from src.preview.estimators import SuggestEstimate, format_suggest_preview

        estimate = SuggestEstimate(
            analysis_path=Path("/output/analysis.json"),
            analysis_exists=True,
            output_path=Path("/output/suggestions.json"),
            duration_estimate_seconds=5.0,
            output_size_estimate_bytes=102400,
        )

        output = format_suggest_preview(estimate)

        assert "[DRY RUN] suggest" in output
        assert "analysis.json" in output
        assert "suggestions.json" in output

    def test_format_review_preview(self):
        """Test review preview formatting."""
        from src.preview.estimators import ReviewEstimate, format_review_preview

        estimate = ReviewEstimate(
            suggestions_path=Path("/output/suggestions.json"),
            suggestions_exists=True,
            category_count=15,
            output_path=Path("/output/approved.json"),
        )

        output = format_review_preview(estimate)

        assert "[DRY RUN] review" in output
        assert "15" in output
        assert "approved" in output.lower()

    def test_format_pipeline_preview(self):
        """Test pipeline preview formatting."""
        from src.preview.estimators import (
            AnalyzeEstimate,
            ExtractEstimate,
            PipelineEstimate,
            ReviewEstimate,
            SuggestEstimate,
            format_pipeline_preview,
        )

        pipeline = PipelineEstimate(
            extract=ExtractEstimate(
                user_email="test@example.com",
                output_path=Path("/output/corpus.json"),
            ),
            analyze=AnalyzeEstimate(
                corpus_path=Path("/output/corpus.json"),
                corpus_exists=False,
                output_path=Path("/output/analysis.json"),
            ),
            suggest=SuggestEstimate(
                analysis_path=Path("/output/analysis.json"),
                analysis_exists=False,
                output_path=Path("/output/suggestions.json"),
            ),
            review=ReviewEstimate(
                suggestions_path=Path("/output/suggestions.json"),
                suggestions_exists=False,
                output_path=Path("/output/approved.json"),
            ),
        )

        output = format_pipeline_preview(pipeline)

        assert "[DRY RUN] pipeline" in output
        assert "extract" in output.lower()
        assert "analyze" in output.lower()
        assert "suggest" in output.lower()
        assert "review" in output.lower()


class TestFormatHelpers:
    """Test cases for format helper functions."""

    def test_format_bytes_small(self):
        """Test formatting small byte values."""
        from src.preview.estimators import format_bytes

        assert format_bytes(500) == "500 B"
        assert format_bytes(1023) == "1023 B"

    def test_format_bytes_kilobytes(self):
        """Test formatting kilobyte values."""
        from src.preview.estimators import format_bytes

        assert "KB" in format_bytes(1024)
        assert "KB" in format_bytes(102400)

    def test_format_bytes_megabytes(self):
        """Test formatting megabyte values."""
        from src.preview.estimators import format_bytes

        assert "MB" in format_bytes(1048576)
        assert "MB" in format_bytes(47395430)

    def test_format_bytes_none(self):
        """Test formatting None value."""
        from src.preview.estimators import format_bytes

        result = format_bytes(None)
        assert "unknown" in result.lower() or result == "N/A"

    def test_format_duration_seconds(self):
        """Test formatting duration in seconds."""
        from src.preview.estimators import format_duration

        assert "sec" in format_duration(30).lower() or "30" in format_duration(30)

    def test_format_duration_minutes(self):
        """Test formatting duration in minutes."""
        from src.preview.estimators import format_duration

        result = format_duration(543)
        assert "min" in result.lower() or "9" in result

    def test_format_duration_none(self):
        """Test formatting None duration."""
        from src.preview.estimators import format_duration

        result = format_duration(None)
        assert "unknown" in result.lower() or "depend" in result.lower() or result == "N/A"

    def test_format_count(self):
        """Test formatting count values."""
        from src.preview.estimators import format_count

        assert format_count(5432) in ["5432", "5,432"]
        assert format_count(None) in ["unknown", "N/A", "Unknown"]
