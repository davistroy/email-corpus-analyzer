"""
Unit tests for configuration data models.

Tests cover:
- src/config/models.py - Pydantic models for AppConfig and nested configs

Following TDD: these tests were written BEFORE implementation.
"""
import pytest
from pathlib import Path


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
            batch_size=250,
            checkpoint_interval=50,
            corpus_file=Path("/custom/corpus.json")
        )

        assert config.batch_size == 250
        assert config.checkpoint_interval == 50
        assert config.corpus_file == Path("/custom/corpus.json")

    def test_extract_config_batch_size_must_be_positive(self):
        """Test batch_size must be greater than 0."""
        from src.config.models import ExtractConfig
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            ExtractConfig(batch_size=0)

        assert "batch_size" in str(exc_info.value)

    def test_extract_config_batch_size_must_not_be_negative(self):
        """Test batch_size cannot be negative."""
        from src.config.models import ExtractConfig
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ExtractConfig(batch_size=-1)

    def test_extract_config_checkpoint_interval_must_be_positive(self):
        """Test checkpoint_interval must be greater than 0."""
        from src.config.models import ExtractConfig
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            ExtractConfig(checkpoint_interval=0)

        assert "checkpoint_interval" in str(exc_info.value)

    def test_extract_config_batch_size_max_limit(self):
        """Test batch_size has a reasonable upper limit."""
        from src.config.models import ExtractConfig
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ExtractConfig(batch_size=100001)

    def test_extract_config_checkpoint_interval_max_limit(self):
        """Test checkpoint_interval has a reasonable upper limit."""
        from src.config.models import ExtractConfig
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ExtractConfig(checkpoint_interval=10001)


class TestAnalyzeConfig:
    """Test cases for AnalyzeConfig model."""

    def test_analyze_config_default_values(self):
        """Test AnalyzeConfig has correct default values."""
        from src.config.models import AnalyzeConfig

        config = AnalyzeConfig()

        assert config.num_clusters == 10
        assert config.corpus_file is None
        assert config.analysis_file is None

    def test_analyze_config_custom_values(self):
        """Test AnalyzeConfig accepts custom values."""
        from src.config.models import AnalyzeConfig

        config = AnalyzeConfig(
            num_clusters=15,
            corpus_file=Path("/input/corpus.json"),
            analysis_file=Path("/output/analysis.json")
        )

        assert config.num_clusters == 15
        assert config.corpus_file == Path("/input/corpus.json")
        assert config.analysis_file == Path("/output/analysis.json")

    def test_analyze_config_num_clusters_must_be_positive(self):
        """Test num_clusters must be at least 1."""
        from src.config.models import AnalyzeConfig
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            AnalyzeConfig(num_clusters=0)

        assert "num_clusters" in str(exc_info.value)

    def test_analyze_config_num_clusters_max_limit(self):
        """Test num_clusters has a reasonable upper limit."""
        from src.config.models import AnalyzeConfig
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            AnalyzeConfig(num_clusters=1001)


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
            suggestions_file=Path("/output/suggestions.json")
        )

        assert config.min_cluster_percentage == 10.0
        assert config.min_sender_count == 50
        assert config.analysis_file == Path("/input/analysis.json")
        assert config.suggestions_file == Path("/output/suggestions.json")

    def test_suggest_config_min_cluster_percentage_must_be_non_negative(self):
        """Test min_cluster_percentage cannot be negative."""
        from src.config.models import SuggestConfig
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            SuggestConfig(min_cluster_percentage=-1.0)

        assert "min_cluster_percentage" in str(exc_info.value)

    def test_suggest_config_min_cluster_percentage_max_100(self):
        """Test min_cluster_percentage cannot exceed 100."""
        from src.config.models import SuggestConfig
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            SuggestConfig(min_cluster_percentage=101.0)

    def test_suggest_config_min_sender_count_must_be_positive(self):
        """Test min_sender_count must be at least 1."""
        from src.config.models import SuggestConfig
        from pydantic import ValidationError

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
            no_cleanup=True
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

        config = AppConfig(
            extract=ExtractConfig(batch_size=200, checkpoint_interval=25)
        )

        assert config.extract.batch_size == 200
        assert config.extract.checkpoint_interval == 25

    def test_app_config_nested_analyze_config(self):
        """Test AppConfig can set nested AnalyzeConfig values."""
        from src.config.models import AppConfig, AnalyzeConfig

        config = AppConfig(analyze=AnalyzeConfig(num_clusters=20))

        assert config.analyze.num_clusters == 20

    def test_app_config_nested_suggest_config(self):
        """Test AppConfig can set nested SuggestConfig values."""
        from src.config.models import AppConfig, SuggestConfig

        config = AppConfig(
            suggest=SuggestConfig(
                min_cluster_percentage=8.0,
                min_sender_count=30
            )
        )

        assert config.suggest.min_cluster_percentage == 8.0
        assert config.suggest.min_sender_count == 30

    def test_app_config_from_dict(self):
        """Test AppConfig can be created from nested dictionary."""
        from src.config.models import AppConfig

        data = {
            "output_dir": "/custom/output",
            "user_email": "test@example.com",
            "verbose": True,
            "extract": {
                "batch_size": 300,
                "checkpoint_interval": 75
            },
            "analyze": {
                "num_clusters": 15
            }
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
            extract=ExtractConfig(batch_size=250)
        )

        data = config.model_dump()

        assert data["output_dir"] == Path("/custom/output")
        assert data["user_email"] == "test@example.com"
        assert data["extract"]["batch_size"] == 250

    def test_app_config_user_email_validation(self):
        """Test user_email must be valid email format when provided."""
        from src.config.models import AppConfig
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            AppConfig(user_email="not-an-email")

        assert "user_email" in str(exc_info.value)

    def test_app_config_invalid_nested_config(self):
        """Test AppConfig rejects invalid nested config values."""
        from src.config.models import AppConfig
        from pydantic import ValidationError

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

        base = AppConfig(
            extract=ExtractConfig(batch_size=500, checkpoint_interval=100)
        )
        override = AppConfig(
            extract=ExtractConfig(batch_size=250)
        )

        result = merge_configs(base, override)

        # Override value should take precedence
        assert result.extract.batch_size == 250
        # Base value should be preserved for non-overridden fields
        assert result.extract.checkpoint_interval == 100

    def test_merge_configs_partial_nested_override(self):
        """Test partial override of nested config."""
        from src.config.models import AppConfig, AnalyzeConfig, SuggestConfig, merge_configs

        base = AppConfig(
            analyze=AnalyzeConfig(num_clusters=10),
            suggest=SuggestConfig(min_cluster_percentage=5.0, min_sender_count=20)
        )
        override = AppConfig(
            suggest=SuggestConfig(min_sender_count=30)
        )

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

        defaults = AppConfig(
            extract=ExtractConfig(batch_size=500, checkpoint_interval=100)
        )
        global_config = AppConfig(
            user_email="global@example.com",
            extract=ExtractConfig(batch_size=300)
        )
        project_config = AppConfig(
            extract=ExtractConfig(checkpoint_interval=50)
        )

        # Merge: defaults <- global <- project
        result = merge_configs(merge_configs(defaults, global_config), project_config)

        # Project override
        assert result.extract.checkpoint_interval == 50
        # Global override (not overridden by project)
        assert result.extract.batch_size == 300
        assert result.user_email == "global@example.com"
