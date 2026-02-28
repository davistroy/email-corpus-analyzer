"""
Unit tests for configuration data models.

Tests cover:
- src/config/models.py - Pydantic models for AppConfig and nested configs

Following TDD: these tests were written BEFORE implementation.
"""

from pathlib import Path

import pytest


class TestExtractConfig:
    """Test cases for ExtractConfig model."""

    def test_extract_config_default_values(self):
        """Test ExtractConfig has correct default values."""
        from src.config.models import ExtractConfig

        config = ExtractConfig()

        assert config.batch_size == 500
        assert config.checkpoint_interval == 100
        assert config.corpus_file is None

    def test_extract_config_custom_values(self):
        """Test ExtractConfig accepts custom values."""
        from src.config.models import ExtractConfig

        config = ExtractConfig(
            batch_size=250, checkpoint_interval=50, corpus_file=Path("/custom/corpus.json")
        )

        assert config.batch_size == 250
        assert config.checkpoint_interval == 50
        assert config.corpus_file == Path("/custom/corpus.json")

    def test_extract_config_batch_size_must_be_positive(self):
        """Test batch_size must be greater than 0."""
        from pydantic import ValidationError

        from src.config.models import ExtractConfig

        with pytest.raises(ValidationError) as exc_info:
            ExtractConfig(batch_size=0)

        assert "batch_size" in str(exc_info.value)

    def test_extract_config_batch_size_must_not_be_negative(self):
        """Test batch_size cannot be negative."""
        from pydantic import ValidationError

        from src.config.models import ExtractConfig

        with pytest.raises(ValidationError):
            ExtractConfig(batch_size=-1)

    def test_extract_config_checkpoint_interval_must_be_positive(self):
        """Test checkpoint_interval must be greater than 0."""
        from pydantic import ValidationError

        from src.config.models import ExtractConfig

        with pytest.raises(ValidationError) as exc_info:
            ExtractConfig(checkpoint_interval=0)

        assert "checkpoint_interval" in str(exc_info.value)

    def test_extract_config_batch_size_max_limit(self):
        """Test batch_size has a reasonable upper limit."""
        from pydantic import ValidationError

        from src.config.models import ExtractConfig

        with pytest.raises(ValidationError):
            ExtractConfig(batch_size=100001)

    def test_extract_config_checkpoint_interval_max_limit(self):
        """Test checkpoint_interval has a reasonable upper limit."""
        from pydantic import ValidationError

        from src.config.models import ExtractConfig

        with pytest.raises(ValidationError):
            ExtractConfig(checkpoint_interval=10001)


class TestAnalyzeConfig:
    """Test cases for AnalyzeConfig model."""

    def test_analyze_config_default_values(self):
        """Test AnalyzeConfig has correct default values."""
        from src.config.models import AnalyzeConfig

        config = AnalyzeConfig()

        assert config.num_clusters == 10
        assert config.max_embedding_text_length == 1500
        assert config.auto_cluster_min == 3
        assert config.auto_cluster_max == 25
        assert config.corpus_file is None
        assert config.analysis_file is None

    def test_analyze_config_custom_values(self):
        """Test AnalyzeConfig accepts custom values."""
        from src.config.models import AnalyzeConfig

        config = AnalyzeConfig(
            num_clusters=15,
            max_embedding_text_length=2000,
            corpus_file=Path("/input/corpus.json"),
            analysis_file=Path("/output/analysis.json"),
        )

        assert config.num_clusters == 15
        assert config.max_embedding_text_length == 2000
        assert config.corpus_file == Path("/input/corpus.json")
        assert config.analysis_file == Path("/output/analysis.json")

    def test_analyze_config_num_clusters_must_be_positive(self):
        """Test num_clusters must be at least 1."""
        from pydantic import ValidationError

        from src.config.models import AnalyzeConfig

        with pytest.raises(ValidationError) as exc_info:
            AnalyzeConfig(num_clusters=0)

        assert "num_clusters" in str(exc_info.value)

    def test_analyze_config_num_clusters_max_limit(self):
        """Test num_clusters has a reasonable upper limit."""
        from pydantic import ValidationError

        from src.config.models import AnalyzeConfig

        with pytest.raises(ValidationError):
            AnalyzeConfig(num_clusters=1001)

    def test_analyze_config_max_embedding_text_length_default(self):
        """Test max_embedding_text_length defaults to 1500."""
        from src.config.models import AnalyzeConfig

        config = AnalyzeConfig()
        assert config.max_embedding_text_length == 1500

    def test_analyze_config_max_embedding_text_length_custom(self):
        """Test max_embedding_text_length accepts valid custom values."""
        from src.config.models import AnalyzeConfig

        config = AnalyzeConfig(max_embedding_text_length=3000)
        assert config.max_embedding_text_length == 3000

    def test_analyze_config_max_embedding_text_length_min_boundary(self):
        """Test max_embedding_text_length must be at least 200."""
        from pydantic import ValidationError

        from src.config.models import AnalyzeConfig

        # Exactly 200 should work
        config = AnalyzeConfig(max_embedding_text_length=200)
        assert config.max_embedding_text_length == 200

        # Below 200 should fail
        with pytest.raises(ValidationError) as exc_info:
            AnalyzeConfig(max_embedding_text_length=199)
        assert "max_embedding_text_length" in str(exc_info.value)

    def test_analyze_config_max_embedding_text_length_max_boundary(self):
        """Test max_embedding_text_length must not exceed 5000."""
        from pydantic import ValidationError

        from src.config.models import AnalyzeConfig

        # Exactly 5000 should work
        config = AnalyzeConfig(max_embedding_text_length=5000)
        assert config.max_embedding_text_length == 5000

        # Above 5000 should fail
        with pytest.raises(ValidationError) as exc_info:
            AnalyzeConfig(max_embedding_text_length=5001)
        assert "max_embedding_text_length" in str(exc_info.value)

    def test_analyze_config_auto_cluster_min_default(self):
        """Test auto_cluster_min defaults to 3."""
        from src.config.models import AnalyzeConfig

        config = AnalyzeConfig()
        assert config.auto_cluster_min == 3

    def test_analyze_config_auto_cluster_max_default(self):
        """Test auto_cluster_max defaults to 25."""
        from src.config.models import AnalyzeConfig

        config = AnalyzeConfig()
        assert config.auto_cluster_max == 25

    def test_analyze_config_auto_cluster_bounds_configurable(self):
        """Test auto_cluster_min and auto_cluster_max accept custom values."""
        from src.config.models import AnalyzeConfig

        config = AnalyzeConfig(auto_cluster_min=5, auto_cluster_max=50)
        assert config.auto_cluster_min == 5
        assert config.auto_cluster_max == 50

    def test_analyze_config_auto_cluster_min_gt_max_raises(self):
        """Test that auto_cluster_min > auto_cluster_max raises ValidationError."""
        from pydantic import ValidationError

        from src.config.models import AnalyzeConfig

        with pytest.raises(ValidationError) as exc_info:
            AnalyzeConfig(auto_cluster_min=30, auto_cluster_max=10)
        assert "auto_cluster_min" in str(exc_info.value)

    def test_analyze_config_auto_cluster_min_boundary(self):
        """Test auto_cluster_min must be >= 2."""
        from pydantic import ValidationError

        from src.config.models import AnalyzeConfig

        config = AnalyzeConfig(auto_cluster_min=2)
        assert config.auto_cluster_min == 2

        with pytest.raises(ValidationError):
            AnalyzeConfig(auto_cluster_min=1)

    def test_analyze_config_auto_cluster_max_boundary(self):
        """Test auto_cluster_max must be >= 3 and <= 100."""
        from pydantic import ValidationError

        from src.config.models import AnalyzeConfig

        config = AnalyzeConfig(auto_cluster_max=100)
        assert config.auto_cluster_max == 100

        with pytest.raises(ValidationError):
            AnalyzeConfig(auto_cluster_max=101)

        with pytest.raises(ValidationError):
            AnalyzeConfig(auto_cluster_max=2)


class TestSuggestConfig:
    """Test cases for SuggestConfig model."""

    def test_suggest_config_default_values(self):
        """Test SuggestConfig has correct default values."""
        from src.config.models import SuggestConfig

        config = SuggestConfig()

        assert config.min_cluster_percentage == 5.0
        assert config.min_sender_count == 20
        assert config.analysis_file is None
        assert config.suggestions_file is None

    def test_suggest_config_custom_values(self):
        """Test SuggestConfig accepts custom values."""
        from src.config.models import SuggestConfig

        config = SuggestConfig(
            min_cluster_percentage=10.0,
            min_sender_count=50,
            analysis_file=Path("/input/analysis.json"),
            suggestions_file=Path("/output/suggestions.json"),
        )

        assert config.min_cluster_percentage == 10.0
        assert config.min_sender_count == 50
        assert config.analysis_file == Path("/input/analysis.json")
        assert config.suggestions_file == Path("/output/suggestions.json")

    def test_suggest_config_min_cluster_percentage_must_be_non_negative(self):
        """Test min_cluster_percentage cannot be negative."""
        from pydantic import ValidationError

        from src.config.models import SuggestConfig

        with pytest.raises(ValidationError) as exc_info:
            SuggestConfig(min_cluster_percentage=-1.0)

        assert "min_cluster_percentage" in str(exc_info.value)

    def test_suggest_config_min_cluster_percentage_max_100(self):
        """Test min_cluster_percentage cannot exceed 100."""
        from pydantic import ValidationError

        from src.config.models import SuggestConfig

        with pytest.raises(ValidationError):
            SuggestConfig(min_cluster_percentage=101.0)

    def test_suggest_config_min_sender_count_must_be_positive(self):
        """Test min_sender_count must be at least 1."""
        from pydantic import ValidationError

        from src.config.models import SuggestConfig

        with pytest.raises(ValidationError) as exc_info:
            SuggestConfig(min_sender_count=0)

        assert "min_sender_count" in str(exc_info.value)


class TestReviewConfig:
    """Test cases for ReviewConfig model."""

    def test_review_config_default_values(self):
        """Test ReviewConfig has correct default values."""
        from src.config.models import ReviewConfig

        config = ReviewConfig()

        assert config.suggestions_file is None
        assert config.approved_file is None
        assert config.no_cleanup is False

    def test_review_config_custom_values(self):
        """Test ReviewConfig accepts custom values."""
        from src.config.models import ReviewConfig

        config = ReviewConfig(
            suggestions_file=Path("/input/suggestions.json"),
            approved_file=Path("/output/approved.json"),
            no_cleanup=True,
        )

        assert config.suggestions_file == Path("/input/suggestions.json")
        assert config.approved_file == Path("/output/approved.json")
        assert config.no_cleanup is True


class TestPipelineConfig:
    """Test cases for PipelineConfig model."""

    def test_pipeline_config_default_values(self):
        """Test PipelineConfig has correct default values."""
        from src.config.models import PipelineConfig

        config = PipelineConfig()

        assert config.num_clusters == 10
        assert config.no_cleanup is False

    def test_pipeline_config_custom_values(self):
        """Test PipelineConfig accepts custom values."""
        from src.config.models import PipelineConfig

        config = PipelineConfig(num_clusters=20, no_cleanup=True)

        assert config.num_clusters == 20
        assert config.no_cleanup is True


class TestAppConfig:
    """Test cases for AppConfig model - the root configuration."""

    def test_app_config_default_values(self):
        """Test AppConfig has all nested configs with defaults."""
        from src.config.models import AppConfig

        config = AppConfig()

        assert config.output_dir is None
        assert config.user_email is None
        assert config.verbose is False

        # Nested configs should be present
        assert config.extract is not None
        assert config.analyze is not None
        assert config.suggest is not None
        assert config.review is not None
        assert config.pipeline is not None

    def test_app_config_with_output_dir(self):
        """Test AppConfig accepts output_dir."""
        from src.config.models import AppConfig

        config = AppConfig(output_dir=Path("/custom/output"))

        assert config.output_dir == Path("/custom/output")

    def test_app_config_with_user_email(self):
        """Test AppConfig accepts user_email."""
        from src.config.models import AppConfig

        config = AppConfig(user_email="test@example.com")

        assert config.user_email == "test@example.com"

    def test_app_config_with_verbose_flag(self):
        """Test AppConfig accepts verbose flag."""
        from src.config.models import AppConfig

        config = AppConfig(verbose=True)

        assert config.verbose is True

    def test_app_config_nested_extract_config(self):
        """Test AppConfig can set nested ExtractConfig values."""
        from src.config.models import AppConfig, ExtractConfig

        config = AppConfig(extract=ExtractConfig(batch_size=200, checkpoint_interval=25))

        assert config.extract.batch_size == 200
        assert config.extract.checkpoint_interval == 25

    def test_app_config_nested_analyze_config(self):
        """Test AppConfig can set nested AnalyzeConfig values."""
        from src.config.models import AnalyzeConfig, AppConfig

        config = AppConfig(analyze=AnalyzeConfig(num_clusters=20))

        assert config.analyze.num_clusters == 20

    def test_app_config_nested_suggest_config(self):
        """Test AppConfig can set nested SuggestConfig values."""
        from src.config.models import AppConfig, SuggestConfig

        config = AppConfig(suggest=SuggestConfig(min_cluster_percentage=8.0, min_sender_count=30))

        assert config.suggest.min_cluster_percentage == 8.0
        assert config.suggest.min_sender_count == 30

    def test_app_config_from_dict(self):
        """Test AppConfig can be created from nested dictionary."""
        from src.config.models import AppConfig

        data = {
            "output_dir": "/custom/output",
            "user_email": "test@example.com",
            "verbose": True,
            "extract": {"batch_size": 300, "checkpoint_interval": 75},
            "analyze": {"num_clusters": 15},
        }

        config = AppConfig(**data)

        assert config.output_dir == Path("/custom/output")
        assert config.user_email == "test@example.com"
        assert config.verbose is True
        assert config.extract.batch_size == 300
        assert config.extract.checkpoint_interval == 75
        assert config.analyze.num_clusters == 15

    def test_app_config_to_dict(self):
        """Test AppConfig can be serialized to dictionary."""
        from src.config.models import AppConfig, ExtractConfig

        config = AppConfig(
            output_dir=Path("/custom/output"),
            user_email="test@example.com",
            extract=ExtractConfig(batch_size=250),
        )

        data = config.model_dump()

        assert data["output_dir"] == Path("/custom/output")
        assert data["user_email"] == "test@example.com"
        assert data["extract"]["batch_size"] == 250

    def test_app_config_user_email_validation(self):
        """Test user_email must be valid email format when provided."""
        from pydantic import ValidationError

        from src.config.models import AppConfig

        with pytest.raises(ValidationError) as exc_info:
            AppConfig(user_email="not-an-email")

        assert "user_email" in str(exc_info.value)

    def test_app_config_invalid_nested_config(self):
        """Test AppConfig rejects invalid nested config values."""
        from pydantic import ValidationError

        from src.config.models import AppConfig

        with pytest.raises(ValidationError):
            AppConfig(extract={"batch_size": -1})


class TestConfigMerging:
    """Test cases for config merging utility."""

    def test_merge_configs_empty_override(self):
        """Test merging with empty override returns base config."""
        from src.config.models import AppConfig, merge_configs

        base = AppConfig(user_email="base@example.com")
        override = AppConfig()

        result = merge_configs(base, override)

        assert result.user_email == "base@example.com"

    def test_merge_configs_full_override(self):
        """Test merging with override replaces values."""
        from src.config.models import AppConfig, merge_configs

        base = AppConfig(user_email="base@example.com", verbose=False)
        override = AppConfig(user_email="override@example.com", verbose=True)

        result = merge_configs(base, override)

        assert result.user_email == "override@example.com"
        assert result.verbose is True

    def test_merge_configs_nested_override(self):
        """Test merging nested config values."""
        from src.config.models import AppConfig, ExtractConfig, merge_configs

        base = AppConfig(extract=ExtractConfig(batch_size=500, checkpoint_interval=100))
        override = AppConfig(extract=ExtractConfig(batch_size=250))

        result = merge_configs(base, override)

        # Override value should take precedence
        assert result.extract.batch_size == 250
        # Base value should be preserved for non-overridden fields
        assert result.extract.checkpoint_interval == 100

    def test_merge_configs_partial_nested_override(self):
        """Test partial override of nested config."""
        from src.config.models import AnalyzeConfig, AppConfig, SuggestConfig, merge_configs

        base = AppConfig(
            analyze=AnalyzeConfig(num_clusters=10),
            suggest=SuggestConfig(min_cluster_percentage=5.0, min_sender_count=20),
        )
        override = AppConfig(suggest=SuggestConfig(min_sender_count=30))

        result = merge_configs(base, override)

        # Unmodified nested config should be preserved
        assert result.analyze.num_clusters == 10
        # Partially modified nested config should have override
        assert result.suggest.min_sender_count == 30
        # And preserve non-overridden values
        assert result.suggest.min_cluster_percentage == 5.0

    def test_merge_configs_none_values_dont_override(self):
        """Test that None values in override don't replace base values."""
        from src.config.models import AppConfig, merge_configs

        base = AppConfig(output_dir=Path("/base/output"))
        override = AppConfig(output_dir=None)

        result = merge_configs(base, override)

        assert result.output_dir == Path("/base/output")

    def test_merge_three_configs(self):
        """Test merging multiple configs (defaults < global < project)."""
        from src.config.models import AppConfig, ExtractConfig, merge_configs

        defaults = AppConfig(extract=ExtractConfig(batch_size=500, checkpoint_interval=100))
        global_config = AppConfig(
            user_email="global@example.com", extract=ExtractConfig(batch_size=300)
        )
        project_config = AppConfig(extract=ExtractConfig(checkpoint_interval=50))

        # Merge: defaults <- global <- project
        result = merge_configs(merge_configs(defaults, global_config), project_config)

        # Project override
        assert result.extract.checkpoint_interval == 50
        # Global override (not overridden by project)
        assert result.extract.batch_size == 300
        assert result.user_email == "global@example.com"


class TestAnalyzerThresholds:
    """Test cases for AnalyzerThresholds model (Task 2.2)."""

    def test_analyzer_thresholds_default_values_match_original_hardcoded(self):
        """Test all defaults match the previously-hardcoded values exactly."""
        from src.config.models import AnalyzerThresholds

        t = AnalyzerThresholds()

        # SenderAnalyzer defaults
        assert t.top_senders == 50
        assert t.top_domains == 30
        assert t.marketing_min_emails == 10

        # SubjectAnalyzer defaults
        assert t.top_keywords == 50

        # SemanticAnalyzer defaults
        assert t.max_auto_clusters == 15
        assert t.representative_samples == 5
        assert t.random_state == 42

        # TemporalAnalyzer defaults
        assert t.frequency_daily_threshold_days == 2.0
        assert t.frequency_weekly_threshold_days == 8.0
        assert t.frequency_monthly_threshold_days == 35.0
        assert t.min_emails_for_frequency == 10

    def test_analyzer_thresholds_custom_values(self):
        """Test AnalyzerThresholds accepts custom values."""
        from src.config.models import AnalyzerThresholds

        t = AnalyzerThresholds(
            top_senders=100,
            top_domains=50,
            marketing_min_emails=5,
            top_keywords=75,
            max_auto_clusters=20,
            representative_samples=10,
            random_state=123,
            frequency_daily_threshold_days=1.5,
            frequency_weekly_threshold_days=7.0,
            frequency_monthly_threshold_days=30.0,
            min_emails_for_frequency=5,
        )

        assert t.top_senders == 100
        assert t.top_domains == 50
        assert t.marketing_min_emails == 5
        assert t.top_keywords == 75
        assert t.max_auto_clusters == 20
        assert t.representative_samples == 10
        assert t.random_state == 123
        assert t.frequency_daily_threshold_days == 1.5
        assert t.frequency_weekly_threshold_days == 7.0
        assert t.frequency_monthly_threshold_days == 30.0
        assert t.min_emails_for_frequency == 5

    def test_analyzer_thresholds_validation_top_senders_min(self):
        """Test top_senders must be >= 1."""
        from pydantic import ValidationError

        from src.config.models import AnalyzerThresholds

        with pytest.raises(ValidationError):
            AnalyzerThresholds(top_senders=0)

    def test_analyzer_thresholds_validation_top_senders_max(self):
        """Test top_senders must be <= 1000."""
        from pydantic import ValidationError

        from src.config.models import AnalyzerThresholds

        with pytest.raises(ValidationError):
            AnalyzerThresholds(top_senders=1001)

    def test_analyzer_thresholds_validation_top_domains_min(self):
        """Test top_domains must be >= 1."""
        from pydantic import ValidationError

        from src.config.models import AnalyzerThresholds

        with pytest.raises(ValidationError):
            AnalyzerThresholds(top_domains=0)

    def test_analyzer_thresholds_validation_max_auto_clusters_min(self):
        """Test max_auto_clusters must be >= 2."""
        from pydantic import ValidationError

        from src.config.models import AnalyzerThresholds

        with pytest.raises(ValidationError):
            AnalyzerThresholds(max_auto_clusters=1)

    def test_analyzer_thresholds_validation_representative_samples_min(self):
        """Test representative_samples must be >= 1."""
        from pydantic import ValidationError

        from src.config.models import AnalyzerThresholds

        with pytest.raises(ValidationError):
            AnalyzerThresholds(representative_samples=0)

    def test_analyzer_thresholds_validation_random_state_min(self):
        """Test random_state must be >= 0."""
        from pydantic import ValidationError

        from src.config.models import AnalyzerThresholds

        with pytest.raises(ValidationError):
            AnalyzerThresholds(random_state=-1)

    def test_analyzer_thresholds_validation_daily_threshold_positive(self):
        """Test frequency_daily_threshold_days must be > 0."""
        from pydantic import ValidationError

        from src.config.models import AnalyzerThresholds

        with pytest.raises(ValidationError):
            AnalyzerThresholds(frequency_daily_threshold_days=0)

    def test_analyzer_thresholds_validation_weekly_threshold_max(self):
        """Test frequency_weekly_threshold_days must be <= 365."""
        from pydantic import ValidationError

        from src.config.models import AnalyzerThresholds

        with pytest.raises(ValidationError):
            AnalyzerThresholds(frequency_weekly_threshold_days=366)

    def test_analyzer_thresholds_validation_min_emails_for_frequency_min(self):
        """Test min_emails_for_frequency must be >= 2."""
        from pydantic import ValidationError

        from src.config.models import AnalyzerThresholds

        with pytest.raises(ValidationError):
            AnalyzerThresholds(min_emails_for_frequency=1)

    def test_analyze_config_has_thresholds_default(self):
        """Test AnalyzeConfig includes AnalyzerThresholds with defaults."""
        from src.config.models import AnalyzeConfig, AnalyzerThresholds

        config = AnalyzeConfig()
        assert isinstance(config.thresholds, AnalyzerThresholds)
        assert config.thresholds.top_senders == 50

    def test_analyze_config_custom_thresholds(self):
        """Test AnalyzeConfig accepts custom thresholds."""
        from src.config.models import AnalyzeConfig, AnalyzerThresholds

        thresholds = AnalyzerThresholds(top_senders=100, random_state=0)
        config = AnalyzeConfig(thresholds=thresholds)

        assert config.thresholds.top_senders == 100
        assert config.thresholds.random_state == 0
        # Other thresholds should still be defaults
        assert config.thresholds.top_domains == 30

    def test_analyze_config_thresholds_from_dict(self):
        """Test AnalyzeConfig can load thresholds from nested dict (YAML support)."""
        from src.config.models import AnalyzeConfig

        data = {
            "num_clusters": 15,
            "thresholds": {
                "top_senders": 75,
                "frequency_daily_threshold_days": 1.0,
            },
        }
        config = AnalyzeConfig(**data)

        assert config.num_clusters == 15
        assert config.thresholds.top_senders == 75
        assert config.thresholds.frequency_daily_threshold_days == 1.0
        # Non-specified thresholds should be defaults
        assert config.thresholds.top_domains == 30


class TestGeneratorThresholds:
    """Test cases for GeneratorThresholds model (Task 2.2)."""

    def test_generator_thresholds_default_values_match_original_hardcoded(self):
        """Test all defaults match the previously-hardcoded values exactly."""
        from src.config.models import GeneratorThresholds

        t = GeneratorThresholds()

        assert t.max_senders_for_categories == 20
        assert t.merge_name_similarity == 0.8
        assert t.merge_email_overlap == 0.7

    def test_generator_thresholds_custom_values(self):
        """Test GeneratorThresholds accepts custom values."""
        from src.config.models import GeneratorThresholds

        t = GeneratorThresholds(
            max_senders_for_categories=50,
            merge_name_similarity=0.9,
            merge_email_overlap=0.5,
        )

        assert t.max_senders_for_categories == 50
        assert t.merge_name_similarity == 0.9
        assert t.merge_email_overlap == 0.5

    def test_generator_thresholds_validation_max_senders_min(self):
        """Test max_senders_for_categories must be >= 1."""
        from pydantic import ValidationError

        from src.config.models import GeneratorThresholds

        with pytest.raises(ValidationError):
            GeneratorThresholds(max_senders_for_categories=0)

    def test_generator_thresholds_validation_merge_name_similarity_range(self):
        """Test merge_name_similarity must be between 0.0 and 1.0."""
        from pydantic import ValidationError

        from src.config.models import GeneratorThresholds

        # Valid boundary values
        GeneratorThresholds(merge_name_similarity=0.0)
        GeneratorThresholds(merge_name_similarity=1.0)

        # Invalid
        with pytest.raises(ValidationError):
            GeneratorThresholds(merge_name_similarity=-0.1)

        with pytest.raises(ValidationError):
            GeneratorThresholds(merge_name_similarity=1.1)

    def test_generator_thresholds_validation_merge_email_overlap_range(self):
        """Test merge_email_overlap must be between 0.0 and 1.0."""
        from pydantic import ValidationError

        from src.config.models import GeneratorThresholds

        # Valid boundary values
        GeneratorThresholds(merge_email_overlap=0.0)
        GeneratorThresholds(merge_email_overlap=1.0)

        # Invalid
        with pytest.raises(ValidationError):
            GeneratorThresholds(merge_email_overlap=-0.1)

        with pytest.raises(ValidationError):
            GeneratorThresholds(merge_email_overlap=1.1)

    def test_suggest_config_has_thresholds_default(self):
        """Test SuggestConfig includes GeneratorThresholds with defaults."""
        from src.config.models import GeneratorThresholds, SuggestConfig

        config = SuggestConfig()
        assert isinstance(config.thresholds, GeneratorThresholds)
        assert config.thresholds.max_senders_for_categories == 20

    def test_suggest_config_custom_thresholds(self):
        """Test SuggestConfig accepts custom thresholds."""
        from src.config.models import GeneratorThresholds, SuggestConfig

        thresholds = GeneratorThresholds(max_senders_for_categories=30)
        config = SuggestConfig(thresholds=thresholds)

        assert config.thresholds.max_senders_for_categories == 30
        # Other thresholds should still be defaults
        assert config.thresholds.merge_name_similarity == 0.8

    def test_suggest_config_thresholds_from_dict(self):
        """Test SuggestConfig can load thresholds from nested dict (YAML support)."""
        from src.config.models import SuggestConfig

        data = {
            "min_sender_count": 30,
            "thresholds": {
                "max_senders_for_categories": 50,
                "merge_email_overlap": 0.6,
            },
        }
        config = SuggestConfig(**data)

        assert config.min_sender_count == 30
        assert config.thresholds.max_senders_for_categories == 50
        assert config.thresholds.merge_email_overlap == 0.6
        # Non-specified thresholds should be defaults
        assert config.thresholds.merge_name_similarity == 0.8

    def test_app_config_includes_thresholds(self):
        """Test AppConfig includes both threshold configs through nesting."""
        from src.config.models import AppConfig

        config = AppConfig()

        # Analyzer thresholds via analyze config
        assert config.analyze.thresholds.top_senders == 50
        assert config.analyze.thresholds.random_state == 42

        # Generator thresholds via suggest config
        assert config.suggest.thresholds.max_senders_for_categories == 20
        assert config.suggest.thresholds.merge_name_similarity == 0.8


class TestConfigMergePrecedence:
    """Test cases for config merge precedence using model_fields_set.

    These tests verify that explicitly setting a value to the default
    in a higher-precedence config correctly overrides a non-default
    value from a lower-precedence config. This is the fix for B1.
    """

    def test_merge_verbose_false_overrides_verbose_true(self):
        """Project config setting verbose=false should override global verbose=true.

        This is the primary bug: a boolean default value (False) in the override
        config should still take precedence over a non-default base value.
        """
        from src.config.models import AppConfig, merge_configs

        global_config = AppConfig(verbose=True)
        project_config = AppConfig(verbose=False)  # Explicit default value

        result = merge_configs(global_config, project_config)

        # verbose=False was EXPLICITLY set in project_config,
        # so it should override global's verbose=True
        assert result.verbose is False

    def test_merge_num_clusters_default_overrides_non_default(self):
        """Project config setting num_clusters=10 (default) should override
        global's num_clusters=15.

        When a user explicitly sets a value that happens to match the default,
        the merge should still honor it over the base config.
        """
        from src.config.models import AnalyzeConfig, AppConfig, merge_configs

        global_config = AppConfig(analyze=AnalyzeConfig(num_clusters=15))
        project_config = AppConfig(analyze=AnalyzeConfig(num_clusters=10))

        result = merge_configs(global_config, project_config)

        # num_clusters=10 was EXPLICITLY set, should override 15
        assert result.analyze.num_clusters == 10

    def test_merge_unset_fields_dont_override(self):
        """Unset fields in override should NOT replace base values.

        This ensures we don't accidentally break the other direction:
        fields NOT present in override should leave base values intact.
        """
        from src.config.models import AnalyzeConfig, AppConfig, merge_configs

        global_config = AppConfig(
            verbose=True, analyze=AnalyzeConfig(num_clusters=15, max_embedding_text_length=2000)
        )
        # Override only sets num_clusters, NOT verbose or max_embedding_text_length
        project_config = AppConfig(analyze=AnalyzeConfig(num_clusters=20))

        result = merge_configs(global_config, project_config)

        # Overridden field should take new value
        assert result.analyze.num_clusters == 20
        # Unset fields should preserve base values
        assert result.verbose is True
        assert result.analyze.max_embedding_text_length == 2000

    def test_merge_no_cleanup_false_overrides_true(self):
        """Explicit no_cleanup=false in override should override base's true.

        Another boolean default-value override scenario, this time on
        a nested config field.
        """
        from src.config.models import AppConfig, ReviewConfig, merge_configs

        base = AppConfig(review=ReviewConfig(no_cleanup=True))
        override = AppConfig(review=ReviewConfig(no_cleanup=False))

        result = merge_configs(base, override)

        assert result.review.no_cleanup is False

    def test_merge_batch_size_default_overrides_custom(self):
        """Explicit batch_size=500 (default) should override base's 200."""
        from src.config.models import AppConfig, ExtractConfig, merge_configs

        base = AppConfig(extract=ExtractConfig(batch_size=200))
        override = AppConfig(extract=ExtractConfig(batch_size=500))

        result = merge_configs(base, override)

        # 500 is the default but was explicitly set
        assert result.extract.batch_size == 500

    def test_merge_three_level_explicit_default_override(self):
        """Three-level merge where project restores a default overridden by global.

        defaults (num_clusters=10) -> global (num_clusters=15) -> project (num_clusters=10)
        The final result should be 10, because project explicitly set it.
        """
        from src.config.models import AnalyzeConfig, AppConfig, merge_configs

        defaults = AppConfig()
        global_config = AppConfig(analyze=AnalyzeConfig(num_clusters=15))
        project_config = AppConfig(analyze=AnalyzeConfig(num_clusters=10))

        # Chain: defaults <- global <- project
        intermediate = merge_configs(defaults, global_config)
        result = merge_configs(intermediate, project_config)

        assert result.analyze.num_clusters == 10

    def test_merge_none_values_in_override_dont_override_base(self):
        """None values in override config should not replace base values.

        This ensures that optional fields left as None in the override
        don't wipe out base config values.
        """
        from pathlib import Path

        from src.config.models import AppConfig, merge_configs

        base = AppConfig(output_dir=Path("/base/output"), user_email="base@example.com")
        # Override with only user_email, output_dir left as None (default)
        override = AppConfig(user_email="override@example.com")

        result = merge_configs(base, override)

        assert result.user_email == "override@example.com"
        assert result.output_dir == Path("/base/output")
