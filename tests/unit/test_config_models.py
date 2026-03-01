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


class TestSchedulerConfig:
    """Test cases for SchedulerConfig model (Phase 6, Item 6.5)."""

    def test_scheduler_config_default_values(self):
        """Test SchedulerConfig has correct default values."""
        from src.config.models import SchedulerConfig

        config = SchedulerConfig()

        assert config.enabled is False
        assert config.interval_hours == 24
        assert config.run_at == "02:00"
        assert config.tasks == ["extract", "analyze", "categorize", "move"]
        assert config.auto_categorize is False
        assert config.notification_threshold == 10

    def test_scheduler_config_custom_values(self):
        """Test SchedulerConfig accepts custom values."""
        from src.config.models import SchedulerConfig

        config = SchedulerConfig(
            enabled=True,
            interval_hours=12,
            run_at="03:30",
            tasks=["extract", "analyze"],
            auto_categorize=True,
            notification_threshold=5,
        )

        assert config.enabled is True
        assert config.interval_hours == 12
        assert config.run_at == "03:30"
        assert config.tasks == ["extract", "analyze"]
        assert config.auto_categorize is True
        assert config.notification_threshold == 5

    def test_scheduler_config_interval_hours_must_be_positive(self):
        """Test interval_hours must be >= 1."""
        from pydantic import ValidationError

        from src.config.models import SchedulerConfig

        with pytest.raises(ValidationError):
            SchedulerConfig(interval_hours=0)

    def test_scheduler_config_interval_hours_max_limit(self):
        """Test interval_hours must be <= 168 (one week)."""
        from pydantic import ValidationError

        from src.config.models import SchedulerConfig

        # Exactly 168 should work
        config = SchedulerConfig(interval_hours=168)
        assert config.interval_hours == 168

        with pytest.raises(ValidationError):
            SchedulerConfig(interval_hours=169)

    def test_scheduler_config_run_at_valid_times(self):
        """Test run_at accepts valid HH:MM time formats."""
        from src.config.models import SchedulerConfig

        valid_times = ["00:00", "02:00", "12:30", "23:59", "09:05"]
        for time_str in valid_times:
            config = SchedulerConfig(run_at=time_str)
            assert config.run_at == time_str

    def test_scheduler_config_run_at_invalid_format(self):
        """Test run_at rejects invalid time formats."""
        from pydantic import ValidationError

        from src.config.models import SchedulerConfig

        invalid_times = ["25:00", "12:60", "2:00", "abc", "12:0", "24:00", ""]
        for time_str in invalid_times:
            with pytest.raises(ValidationError):
                SchedulerConfig(run_at=time_str)

    def test_scheduler_config_tasks_valid_values(self):
        """Test tasks accepts valid task names."""
        from src.config.models import SchedulerConfig

        config = SchedulerConfig(tasks=["extract"])
        assert config.tasks == ["extract"]

        config = SchedulerConfig(tasks=["extract", "analyze", "categorize", "move"])
        assert len(config.tasks) == 4

    def test_scheduler_config_tasks_invalid_values(self):
        """Test tasks rejects invalid task names."""
        from pydantic import ValidationError

        from src.config.models import SchedulerConfig

        with pytest.raises(ValidationError):
            SchedulerConfig(tasks=["extract", "invalid_task"])

    def test_scheduler_config_tasks_empty_list(self):
        """Test tasks rejects empty list."""
        from pydantic import ValidationError

        from src.config.models import SchedulerConfig

        with pytest.raises(ValidationError):
            SchedulerConfig(tasks=[])

    def test_scheduler_config_notification_threshold_min(self):
        """Test notification_threshold must be >= 1."""
        from pydantic import ValidationError

        from src.config.models import SchedulerConfig

        with pytest.raises(ValidationError):
            SchedulerConfig(notification_threshold=0)

    def test_scheduler_config_notification_threshold_max(self):
        """Test notification_threshold must be <= 10000."""
        from pydantic import ValidationError

        from src.config.models import SchedulerConfig

        with pytest.raises(ValidationError):
            SchedulerConfig(notification_threshold=10001)

    def test_scheduler_config_from_dict(self):
        """Test SchedulerConfig can be created from dict (YAML support)."""
        from src.config.models import SchedulerConfig

        data = {
            "enabled": True,
            "interval_hours": 6,
            "run_at": "04:00",
            "tasks": ["extract", "analyze"],
            "auto_categorize": True,
            "notification_threshold": 20,
        }
        config = SchedulerConfig(**data)

        assert config.enabled is True
        assert config.interval_hours == 6
        assert config.run_at == "04:00"
        assert config.tasks == ["extract", "analyze"]


class TestMonitoringConfig:
    """Test cases for MonitoringConfig model (Phase 6, Item 6.5)."""

    def test_monitoring_config_default_values(self):
        """Test MonitoringConfig has correct default values."""
        from src.config.models import MonitoringConfig

        config = MonitoringConfig()

        assert config.drift_threshold == 0.15
        assert config.volume_anomaly_stddev == 2.0
        assert config.alert_channels == ["log"]
        assert config.check_interval_hours == 6
        assert config.new_cluster_threshold == 10

    def test_monitoring_config_custom_values(self):
        """Test MonitoringConfig accepts custom values."""
        from src.config.models import MonitoringConfig

        config = MonitoringConfig(
            drift_threshold=0.25,
            volume_anomaly_stddev=3.0,
            alert_channels=["desktop", "log", "email"],
            check_interval_hours=12,
            new_cluster_threshold=20,
        )

        assert config.drift_threshold == 0.25
        assert config.volume_anomaly_stddev == 3.0
        assert config.alert_channels == ["desktop", "log", "email"]
        assert config.check_interval_hours == 12
        assert config.new_cluster_threshold == 20

    def test_monitoring_config_drift_threshold_range(self):
        """Test drift_threshold must be between 0.0 and 1.0."""
        from pydantic import ValidationError

        from src.config.models import MonitoringConfig

        # Valid boundary values
        MonitoringConfig(drift_threshold=0.01)
        MonitoringConfig(drift_threshold=1.0)

        with pytest.raises(ValidationError):
            MonitoringConfig(drift_threshold=0.0)

        with pytest.raises(ValidationError):
            MonitoringConfig(drift_threshold=1.1)

    def test_monitoring_config_volume_anomaly_stddev_range(self):
        """Test volume_anomaly_stddev must be > 0 and <= 10."""
        from pydantic import ValidationError

        from src.config.models import MonitoringConfig

        MonitoringConfig(volume_anomaly_stddev=0.5)
        MonitoringConfig(volume_anomaly_stddev=10.0)

        with pytest.raises(ValidationError):
            MonitoringConfig(volume_anomaly_stddev=0.0)

        with pytest.raises(ValidationError):
            MonitoringConfig(volume_anomaly_stddev=10.1)

    def test_monitoring_config_alert_channels_valid(self):
        """Test alert_channels accepts valid channel names."""
        from src.config.models import MonitoringConfig

        config = MonitoringConfig(alert_channels=["desktop"])
        assert config.alert_channels == ["desktop"]

        config = MonitoringConfig(alert_channels=["desktop", "log", "email"])
        assert len(config.alert_channels) == 3

    def test_monitoring_config_alert_channels_invalid(self):
        """Test alert_channels rejects invalid channel names."""
        from pydantic import ValidationError

        from src.config.models import MonitoringConfig

        with pytest.raises(ValidationError):
            MonitoringConfig(alert_channels=["desktop", "sms"])

    def test_monitoring_config_alert_channels_empty(self):
        """Test alert_channels rejects empty list."""
        from pydantic import ValidationError

        from src.config.models import MonitoringConfig

        with pytest.raises(ValidationError):
            MonitoringConfig(alert_channels=[])

    def test_monitoring_config_check_interval_hours_range(self):
        """Test check_interval_hours must be >= 1 and <= 168."""
        from pydantic import ValidationError

        from src.config.models import MonitoringConfig

        MonitoringConfig(check_interval_hours=1)
        MonitoringConfig(check_interval_hours=168)

        with pytest.raises(ValidationError):
            MonitoringConfig(check_interval_hours=0)

        with pytest.raises(ValidationError):
            MonitoringConfig(check_interval_hours=169)

    def test_monitoring_config_new_cluster_threshold_range(self):
        """Test new_cluster_threshold must be >= 1 and <= 10000."""
        from pydantic import ValidationError

        from src.config.models import MonitoringConfig

        MonitoringConfig(new_cluster_threshold=1)
        MonitoringConfig(new_cluster_threshold=10000)

        with pytest.raises(ValidationError):
            MonitoringConfig(new_cluster_threshold=0)

        with pytest.raises(ValidationError):
            MonitoringConfig(new_cluster_threshold=10001)

    def test_monitoring_config_from_dict(self):
        """Test MonitoringConfig can be created from dict (YAML support)."""
        from src.config.models import MonitoringConfig

        data = {
            "drift_threshold": 0.20,
            "volume_anomaly_stddev": 2.5,
            "alert_channels": ["desktop", "email"],
            "check_interval_hours": 8,
            "new_cluster_threshold": 15,
        }
        config = MonitoringConfig(**data)

        assert config.drift_threshold == 0.20
        assert config.volume_anomaly_stddev == 2.5
        assert config.alert_channels == ["desktop", "email"]


class TestAppConfigWithSchedulerAndMonitoring:
    """Test AppConfig integration with SchedulerConfig and MonitoringConfig."""

    def test_app_config_has_scheduler_default(self):
        """Test AppConfig includes SchedulerConfig with defaults."""
        from src.config.models import AppConfig, SchedulerConfig

        config = AppConfig()
        assert isinstance(config.scheduler, SchedulerConfig)
        assert config.scheduler.enabled is False
        assert config.scheduler.interval_hours == 24

    def test_app_config_has_monitoring_default(self):
        """Test AppConfig includes MonitoringConfig with defaults."""
        from src.config.models import AppConfig, MonitoringConfig

        config = AppConfig()
        assert isinstance(config.monitoring, MonitoringConfig)
        assert config.monitoring.drift_threshold == 0.15
        assert config.monitoring.check_interval_hours == 6

    def test_app_config_with_custom_scheduler(self):
        """Test AppConfig accepts custom scheduler config."""
        from src.config.models import AppConfig, SchedulerConfig

        scheduler = SchedulerConfig(enabled=True, interval_hours=12, run_at="03:00")
        config = AppConfig(scheduler=scheduler)

        assert config.scheduler.enabled is True
        assert config.scheduler.interval_hours == 12
        assert config.scheduler.run_at == "03:00"

    def test_app_config_with_custom_monitoring(self):
        """Test AppConfig accepts custom monitoring config."""
        from src.config.models import AppConfig, MonitoringConfig

        monitoring = MonitoringConfig(drift_threshold=0.25, check_interval_hours=12)
        config = AppConfig(monitoring=monitoring)

        assert config.monitoring.drift_threshold == 0.25
        assert config.monitoring.check_interval_hours == 12

    def test_app_config_from_dict_with_scheduler_and_monitoring(self):
        """Test AppConfig can be created from dict with new sections."""
        from src.config.models import AppConfig

        data = {
            "scheduler": {
                "enabled": True,
                "interval_hours": 8,
                "run_at": "01:00",
                "tasks": ["extract", "analyze"],
            },
            "monitoring": {
                "drift_threshold": 0.20,
                "alert_channels": ["desktop", "log"],
            },
        }
        config = AppConfig(**data)

        assert config.scheduler.enabled is True
        assert config.scheduler.interval_hours == 8
        assert config.monitoring.drift_threshold == 0.20
        assert config.monitoring.alert_channels == ["desktop", "log"]

    def test_app_config_serialization_with_new_sections(self):
        """Test AppConfig serialization includes scheduler and monitoring."""
        from src.config.models import AppConfig

        config = AppConfig()
        data = config.model_dump()

        assert "scheduler" in data
        assert "monitoring" in data
        assert data["scheduler"]["enabled"] is False
        assert data["monitoring"]["drift_threshold"] == 0.15

    def test_merge_configs_with_scheduler(self):
        """Test merge_configs handles scheduler section."""
        from src.config.models import AppConfig, SchedulerConfig, merge_configs

        base = AppConfig(scheduler=SchedulerConfig(enabled=False, interval_hours=24))
        override = AppConfig(scheduler=SchedulerConfig(enabled=True, interval_hours=12))

        result = merge_configs(base, override)

        assert result.scheduler.enabled is True
        assert result.scheduler.interval_hours == 12

    def test_merge_configs_with_monitoring(self):
        """Test merge_configs handles monitoring section."""
        from src.config.models import AppConfig, MonitoringConfig, merge_configs

        base = AppConfig(monitoring=MonitoringConfig(drift_threshold=0.15))
        override = AppConfig(monitoring=MonitoringConfig(drift_threshold=0.25))

        result = merge_configs(base, override)

        assert result.monitoring.drift_threshold == 0.25

    def test_merge_configs_scheduler_unset_preserves_base(self):
        """Test merge preserves base scheduler when override doesn't set it."""
        from src.config.models import AppConfig, SchedulerConfig, merge_configs

        base = AppConfig(scheduler=SchedulerConfig(enabled=True, interval_hours=12))
        override = AppConfig()  # No scheduler set

        result = merge_configs(base, override)

        assert result.scheduler.enabled is True
        assert result.scheduler.interval_hours == 12


class TestCategoryDefinition:
    """Test cases for CategoryDefinition model (Work Item 1.2)."""

    def test_category_definition_required_fields(self):
        """Test CategoryDefinition requires name and description."""
        from src.config.models import CategoryDefinition

        cat = CategoryDefinition(name="Newsletters", description="Periodic newsletter emails")

        assert cat.name == "Newsletters"
        assert cat.description == "Periodic newsletter emails"

    def test_category_definition_with_keywords(self):
        """Test CategoryDefinition accepts optional keywords list."""
        from src.config.models import CategoryDefinition

        cat = CategoryDefinition(
            name="Shopping",
            description="Order confirmations and receipts",
            keywords=["order", "receipt", "shipping"],
        )

        assert cat.keywords == ["order", "receipt", "shipping"]

    def test_category_definition_keywords_default_empty(self):
        """Test CategoryDefinition keywords defaults to empty list."""
        from src.config.models import CategoryDefinition

        cat = CategoryDefinition(name="Work", description="Work-related emails")

        assert cat.keywords == []

    def test_category_definition_name_cannot_be_empty(self):
        """Test CategoryDefinition name cannot be empty string."""
        from pydantic import ValidationError

        from src.config.models import CategoryDefinition

        with pytest.raises(ValidationError):
            CategoryDefinition(name="", description="Some description")

    def test_category_definition_description_cannot_be_empty(self):
        """Test CategoryDefinition description cannot be empty string."""
        from pydantic import ValidationError

        from src.config.models import CategoryDefinition

        with pytest.raises(ValidationError):
            CategoryDefinition(name="Test", description="")

    def test_category_definition_name_stripped(self):
        """Test CategoryDefinition name has whitespace stripped."""
        from src.config.models import CategoryDefinition

        cat = CategoryDefinition(name="  Newsletters  ", description="Newsletter emails")

        assert cat.name == "Newsletters"

    def test_category_definition_serialization(self):
        """Test CategoryDefinition serializes to dict correctly."""
        from src.config.models import CategoryDefinition

        cat = CategoryDefinition(
            name="Finance",
            description="Financial statements and alerts",
            keywords=["bank", "statement"],
        )
        data = cat.model_dump()

        assert data["name"] == "Finance"
        assert data["description"] == "Financial statements and alerts"
        assert data["keywords"] == ["bank", "statement"]


class TestClassifierConfig:
    """Test cases for ClassifierConfig model (Work Item 1.2)."""

    def test_classifier_config_default_values(self):
        """Test ClassifierConfig has sensible defaults."""
        from src.config.models import ClassifierConfig

        config = ClassifierConfig()

        assert config.provider == "ollama"
        assert config.model_name == "qwen2.5:7b"
        assert config.ollama_base_url == "http://localhost:11434"
        assert config.api_key_env_var is None
        assert config.confidence_threshold == 0.6
        assert config.max_tokens == 200
        assert config.temperature == 0.0
        assert config.categories == []

    def test_classifier_config_custom_values(self):
        """Test ClassifierConfig accepts custom values."""
        from src.config.models import CategoryDefinition, ClassifierConfig

        categories = [
            CategoryDefinition(name="Work", description="Work emails"),
            CategoryDefinition(name="Personal", description="Personal emails"),
        ]
        config = ClassifierConfig(
            provider="claude",
            model_name="claude-sonnet-4-20250514",
            api_key_env_var="ANTHROPIC_API_KEY",
            confidence_threshold=0.8,
            max_tokens=500,
            temperature=0.1,
            categories=categories,
        )

        assert config.provider == "claude"
        assert config.model_name == "claude-sonnet-4-20250514"
        assert config.api_key_env_var == "ANTHROPIC_API_KEY"
        assert config.confidence_threshold == 0.8
        assert config.max_tokens == 500
        assert config.temperature == 0.1
        assert len(config.categories) == 2

    def test_classifier_config_provider_ollama(self):
        """Test ClassifierConfig accepts ollama provider."""
        from src.config.models import ClassifierConfig

        config = ClassifierConfig(provider="ollama")
        assert config.provider == "ollama"

    def test_classifier_config_provider_claude(self):
        """Test ClassifierConfig accepts claude provider."""
        from src.config.models import ClassifierConfig

        config = ClassifierConfig(provider="claude")
        assert config.provider == "claude"

    def test_classifier_config_provider_openai(self):
        """Test ClassifierConfig accepts openai provider."""
        from src.config.models import ClassifierConfig

        config = ClassifierConfig(provider="openai")
        assert config.provider == "openai"

    def test_classifier_config_provider_runpod(self):
        """Test ClassifierConfig accepts runpod provider."""
        from src.config.models import ClassifierConfig

        config = ClassifierConfig(provider="runpod", runpod_endpoint_id="abc123")
        assert config.provider == "runpod"
        assert config.runpod_endpoint_id == "abc123"

    def test_classifier_config_runpod_endpoint_id_default_none(self):
        """Test runpod_endpoint_id defaults to None."""
        from src.config.models import ClassifierConfig

        config = ClassifierConfig()
        assert config.runpod_endpoint_id is None

    def test_classifier_config_invalid_provider(self):
        """Test ClassifierConfig rejects invalid provider."""
        from pydantic import ValidationError

        from src.config.models import ClassifierConfig

        with pytest.raises(ValidationError) as exc_info:
            ClassifierConfig(provider="invalid_provider")

        assert "provider" in str(exc_info.value)

    def test_classifier_config_invalid_ollama_url(self):
        """Test ClassifierConfig rejects invalid ollama_base_url."""
        from pydantic import ValidationError

        from src.config.models import ClassifierConfig

        with pytest.raises(ValidationError) as exc_info:
            ClassifierConfig(ollama_base_url="not-a-valid-url")

        assert "ollama_base_url" in str(exc_info.value)

    def test_classifier_config_ollama_url_accepts_valid_urls(self):
        """Test ClassifierConfig accepts valid HTTP/HTTPS URLs."""
        from src.config.models import ClassifierConfig

        config = ClassifierConfig(ollama_base_url="http://192.168.1.100:11434")
        assert config.ollama_base_url == "http://192.168.1.100:11434"

        config2 = ClassifierConfig(ollama_base_url="https://ollama.example.com")
        assert config2.ollama_base_url == "https://ollama.example.com"

    def test_classifier_config_ollama_url_trailing_slash_stripped(self):
        """Test ClassifierConfig strips trailing slash from ollama_base_url."""
        from src.config.models import ClassifierConfig

        config = ClassifierConfig(ollama_base_url="http://localhost:11434/")
        assert config.ollama_base_url == "http://localhost:11434"

    def test_classifier_config_confidence_threshold_min(self):
        """Test confidence_threshold must be >= 0.0."""
        from pydantic import ValidationError

        from src.config.models import ClassifierConfig

        with pytest.raises(ValidationError):
            ClassifierConfig(confidence_threshold=-0.1)

    def test_classifier_config_confidence_threshold_max(self):
        """Test confidence_threshold must be <= 1.0."""
        from pydantic import ValidationError

        from src.config.models import ClassifierConfig

        with pytest.raises(ValidationError):
            ClassifierConfig(confidence_threshold=1.1)

    def test_classifier_config_confidence_threshold_boundaries(self):
        """Test confidence_threshold accepts boundary values."""
        from src.config.models import ClassifierConfig

        config_zero = ClassifierConfig(confidence_threshold=0.0)
        assert config_zero.confidence_threshold == 0.0

        config_one = ClassifierConfig(confidence_threshold=1.0)
        assert config_one.confidence_threshold == 1.0

    def test_classifier_config_max_tokens_must_be_positive(self):
        """Test max_tokens must be > 0."""
        from pydantic import ValidationError

        from src.config.models import ClassifierConfig

        with pytest.raises(ValidationError):
            ClassifierConfig(max_tokens=0)

    def test_classifier_config_max_tokens_upper_limit(self):
        """Test max_tokens has a reasonable upper limit."""
        from pydantic import ValidationError

        from src.config.models import ClassifierConfig

        with pytest.raises(ValidationError):
            ClassifierConfig(max_tokens=100001)

    def test_classifier_config_temperature_min(self):
        """Test temperature must be >= 0.0."""
        from pydantic import ValidationError

        from src.config.models import ClassifierConfig

        with pytest.raises(ValidationError):
            ClassifierConfig(temperature=-0.1)

    def test_classifier_config_temperature_max(self):
        """Test temperature must be <= 2.0."""
        from pydantic import ValidationError

        from src.config.models import ClassifierConfig

        with pytest.raises(ValidationError):
            ClassifierConfig(temperature=2.1)

    def test_classifier_config_from_dict(self):
        """Test ClassifierConfig can be created from dictionary (YAML parsing)."""
        from src.config.models import ClassifierConfig

        data = {
            "provider": "openai",
            "model_name": "gpt-4o-mini",
            "api_key_env_var": "OPENAI_API_KEY",
            "confidence_threshold": 0.7,
            "categories": [
                {"name": "Newsletters", "description": "Periodic newsletters"},
                {
                    "name": "Shopping",
                    "description": "Orders and receipts",
                    "keywords": ["order", "receipt"],
                },
            ],
        }
        config = ClassifierConfig(**data)

        assert config.provider == "openai"
        assert config.model_name == "gpt-4o-mini"
        assert len(config.categories) == 2
        assert config.categories[0].name == "Newsletters"
        assert config.categories[1].keywords == ["order", "receipt"]

    def test_classifier_config_serialization(self):
        """Test ClassifierConfig serializes to dict correctly."""
        from src.config.models import CategoryDefinition, ClassifierConfig

        config = ClassifierConfig(
            provider="claude",
            categories=[
                CategoryDefinition(name="Work", description="Work emails", keywords=["meeting"]),
            ],
        )
        data = config.model_dump()

        assert data["provider"] == "claude"
        assert len(data["categories"]) == 1
        assert data["categories"][0]["name"] == "Work"
        assert data["categories"][0]["keywords"] == ["meeting"]


class TestAppConfigWithClassifier:
    """Test AppConfig integration with ClassifierConfig (Work Item 1.2)."""

    def test_app_config_has_classifier_default(self):
        """Test AppConfig includes ClassifierConfig with defaults."""
        from src.config.models import AppConfig, ClassifierConfig

        config = AppConfig()
        assert isinstance(config.classifier, ClassifierConfig)
        assert config.classifier.provider == "ollama"
        assert config.classifier.model_name == "qwen2.5:7b"

    def test_app_config_with_custom_classifier(self):
        """Test AppConfig accepts custom classifier config."""
        from src.config.models import AppConfig, ClassifierConfig

        classifier = ClassifierConfig(provider="claude", model_name="claude-sonnet-4-20250514")
        config = AppConfig(classifier=classifier)

        assert config.classifier.provider == "claude"
        assert config.classifier.model_name == "claude-sonnet-4-20250514"

    def test_app_config_from_dict_with_classifier(self):
        """Test AppConfig can be created from dict with classifier section."""
        from src.config.models import AppConfig

        data = {
            "classifier": {
                "provider": "openai",
                "model_name": "gpt-4o-mini",
                "confidence_threshold": 0.7,
                "categories": [
                    {"name": "Work", "description": "Work emails"},
                    {"name": "Personal", "description": "Personal emails"},
                ],
            }
        }
        config = AppConfig(**data)

        assert config.classifier.provider == "openai"
        assert config.classifier.model_name == "gpt-4o-mini"
        assert len(config.classifier.categories) == 2

    def test_app_config_serialization_with_classifier(self):
        """Test AppConfig serialization includes classifier section."""
        from src.config.models import AppConfig

        config = AppConfig()
        data = config.model_dump()

        assert "classifier" in data
        assert data["classifier"]["provider"] == "ollama"
        assert data["classifier"]["model_name"] == "qwen2.5:7b"

    def test_merge_configs_with_classifier(self):
        """Test merge_configs handles classifier section."""
        from src.config.models import AppConfig, ClassifierConfig, merge_configs

        base = AppConfig(classifier=ClassifierConfig(provider="ollama", model_name="llama3:8b"))
        override = AppConfig(
            classifier=ClassifierConfig(provider="claude", model_name="claude-sonnet-4-20250514")
        )

        result = merge_configs(base, override)

        assert result.classifier.provider == "claude"
        assert result.classifier.model_name == "claude-sonnet-4-20250514"

    def test_merge_configs_classifier_unset_preserves_base(self):
        """Test merge preserves base classifier when override doesn't set it."""
        from src.config.models import AppConfig, ClassifierConfig, merge_configs

        base = AppConfig(
            classifier=ClassifierConfig(provider="claude", model_name="claude-sonnet-4-20250514")
        )
        override = AppConfig()  # No classifier set

        result = merge_configs(base, override)

        assert result.classifier.provider == "claude"
        assert result.classifier.model_name == "claude-sonnet-4-20250514"

    def test_merge_configs_classifier_partial_override(self):
        """Test merge handles partial classifier override."""
        from src.config.models import AppConfig, ClassifierConfig, merge_configs

        base = AppConfig(
            classifier=ClassifierConfig(
                provider="ollama",
                model_name="qwen2.5:7b",
                confidence_threshold=0.6,
            )
        )
        override = AppConfig(classifier=ClassifierConfig(confidence_threshold=0.8))

        result = merge_configs(base, override)

        # Overridden value
        assert result.classifier.confidence_threshold == 0.8
        # Base values preserved for non-overridden fields
        assert result.classifier.provider == "ollama"
        assert result.classifier.model_name == "qwen2.5:7b"
