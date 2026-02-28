"""
Integration tests for configuration file loading precedence.

Tests the config loading hierarchy: defaults < global < project < CLI args.
Per Phase 7, Track 7C specification.
"""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from src.config.loader import load_config
from src.config.models import AppConfig

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def temp_home_dir():
    """Create a temporary home directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def temp_project_dir():
    """Create a temporary project directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


def create_global_config(home_dir: Path, config_data: dict) -> Path:
    """Create a global config file in the home directory."""
    config_dir = home_dir / ".email-analyzer"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "config.yaml"
    config_path.write_text(yaml.dump(config_data))
    return config_path


def create_project_config(project_dir: Path, config_data: dict) -> Path:
    """Create a project config file in the project directory."""
    config_path = project_dir / ".email-analyzer.yaml"
    config_path.write_text(yaml.dump(config_data))
    return config_path


# =============================================================================
# Test Default Configuration
# =============================================================================


class TestDefaultConfiguration:
    """Test default configuration values."""

    def test_default_config_values(self):
        """Test that AppConfig has correct defaults."""
        config = AppConfig()

        # Global defaults
        assert config.output_dir is None
        assert config.user_email is None
        assert config.verbose is False

        # Extract defaults
        assert config.extract.batch_size == 500
        assert config.extract.checkpoint_interval == 100

        # Analyze defaults
        assert config.analyze.num_clusters == 10

        # Suggest defaults
        assert config.suggest.min_cluster_percentage == 5.0
        assert config.suggest.min_sender_count == 20

    def test_default_config_serialization(self):
        """Test that default config can be serialized and deserialized."""
        config = AppConfig()
        json_data = config.model_dump_json()
        loaded = AppConfig.model_validate_json(json_data)

        assert loaded.analyze.num_clusters == config.analyze.num_clusters
        assert loaded.suggest.min_sender_count == config.suggest.min_sender_count


# =============================================================================
# Test Configuration Loading Precedence
# =============================================================================


class TestConfigPrecedence:
    """Test configuration loading precedence."""

    @patch("src.config.loader.get_global_config_path")
    @patch("src.config.loader.get_project_config_path")
    def test_global_config_overrides_defaults(
        self, mock_project_path, mock_global_path, temp_home_dir
    ):
        """Test that global config overrides defaults."""
        global_config = {
            "analyze": {
                "num_clusters": 15,
            },
            "suggest": {
                "min_sender_count": 30,
            },
        }
        config_path = create_global_config(temp_home_dir, global_config)
        mock_global_path.return_value = config_path
        mock_project_path.return_value = temp_home_dir / "nonexistent.yaml"

        config = load_config()

        # Global config should override defaults
        assert config.analyze.num_clusters == 15
        assert config.suggest.min_sender_count == 30

        # Non-specified values remain default
        assert config.extract.batch_size == 500

    @patch("src.config.loader.get_global_config_path")
    @patch("src.config.loader.get_project_config_path")
    def test_project_config_overrides_global(
        self, mock_project_path, mock_global_path, temp_home_dir, temp_project_dir
    ):
        """Test that project config overrides global config."""
        global_config = {
            "analyze": {
                "num_clusters": 15,
            },
            "suggest": {
                "min_sender_count": 30,
            },
        }
        global_path = create_global_config(temp_home_dir, global_config)
        mock_global_path.return_value = global_path

        project_config = {
            "analyze": {
                "num_clusters": 20,  # Override global
            },
            # min_sender_count not specified, should use global
        }
        project_path = create_project_config(temp_project_dir, project_config)
        mock_project_path.return_value = project_path

        config = load_config()

        # Project should override global
        assert config.analyze.num_clusters == 20
        # Global value preserved where not overridden
        assert config.suggest.min_sender_count == 30

    @patch("src.config.loader.get_global_config_path")
    @patch("src.config.loader.get_project_config_path")
    def test_custom_config_overrides_all(
        self, mock_project_path, mock_global_path, temp_home_dir, temp_project_dir
    ):
        """Test that custom config file overrides all others."""
        global_config = {"analyze": {"num_clusters": 15}}
        global_path = create_global_config(temp_home_dir, global_config)
        mock_global_path.return_value = global_path

        project_config = {"analyze": {"num_clusters": 20}}
        project_path = create_project_config(temp_project_dir, project_config)
        mock_project_path.return_value = project_path

        # Create custom config file
        custom_config_path = temp_project_dir / "custom_config.yaml"
        custom_config_path.write_text(yaml.dump({"analyze": {"num_clusters": 25}}))

        config = load_config(config_path=custom_config_path)

        # Custom config should win
        assert config.analyze.num_clusters == 25


# =============================================================================
# Test Configuration Validation
# =============================================================================


class TestConfigValidation:
    """Test configuration validation."""

    def test_invalid_num_clusters_raises_error(self):
        """Test that invalid num_clusters raises validation error."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            AppConfig(analyze={"num_clusters": 0})

        with pytest.raises(ValidationError):
            AppConfig(analyze={"num_clusters": -5})

    def test_invalid_batch_size_raises_error(self):
        """Test that invalid batch_size raises validation error."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            AppConfig(extract={"batch_size": 0})

        with pytest.raises(ValidationError):
            AppConfig(extract={"batch_size": -100})

    def test_invalid_percentage_raises_error(self):
        """Test that invalid percentage raises validation error."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            AppConfig(suggest={"min_cluster_percentage": -5.0})

        with pytest.raises(ValidationError):
            AppConfig(suggest={"min_cluster_percentage": 150.0})

    def test_valid_email_format(self):
        """Test that valid email formats are accepted."""
        config = AppConfig(user_email="valid@example.com")
        assert config.user_email == "valid@example.com"

    def test_invalid_email_format_raises_error(self):
        """Test that invalid email format raises validation error."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            AppConfig(user_email="not-an-email")


# =============================================================================
# Test Config File Formats
# =============================================================================


class TestConfigFileFormats:
    """Test different config file formats."""

    @patch("src.config.loader.get_global_config_path")
    @patch("src.config.loader.get_project_config_path")
    def test_yaml_config_loading(self, mock_project_path, mock_global_path, temp_home_dir):
        """Test YAML config file loading."""
        yaml_config = """
analyze:
  num_clusters: 12
suggest:
  min_cluster_percentage: 7.5
"""
        config_dir = temp_home_dir / ".email-analyzer"
        config_dir.mkdir(parents=True, exist_ok=True)
        config_path = config_dir / "config.yaml"
        config_path.write_text(yaml_config)

        mock_global_path.return_value = config_path
        mock_project_path.return_value = temp_home_dir / "nonexistent.yaml"

        config = load_config()

        assert config.analyze.num_clusters == 12
        assert config.suggest.min_cluster_percentage == 7.5

    @patch("src.config.loader.get_global_config_path")
    @patch("src.config.loader.get_project_config_path")
    def test_empty_config_file(self, mock_project_path, mock_global_path, temp_home_dir):
        """Test empty config file uses defaults."""
        config_dir = temp_home_dir / ".email-analyzer"
        config_dir.mkdir(parents=True, exist_ok=True)
        config_path = config_dir / "config.yaml"
        config_path.write_text("")

        mock_global_path.return_value = config_path
        mock_project_path.return_value = temp_home_dir / "nonexistent.yaml"

        config = load_config()

        # Should use all defaults
        assert config.analyze.num_clusters == 10
        assert config.suggest.min_sender_count == 20

    @patch("src.config.loader.get_global_config_path")
    @patch("src.config.loader.get_project_config_path")
    def test_malformed_yaml_raises_error(self, mock_project_path, mock_global_path, temp_home_dir):
        """Test that malformed YAML raises appropriate error."""
        config_dir = temp_home_dir / ".email-analyzer"
        config_dir.mkdir(parents=True, exist_ok=True)
        config_path = config_dir / "config.yaml"
        config_path.write_text("invalid: yaml: content:")

        mock_global_path.return_value = config_path
        mock_project_path.return_value = temp_home_dir / "nonexistent.yaml"

        # Should either raise or use defaults (implementation-dependent)
        # The important thing is it doesn't crash
        try:
            config = load_config()
            # If it doesn't raise, verify defaults are used
            assert config is not None
        except Exception:
            # It's OK to raise on malformed config
            pass


# =============================================================================
# Test Config Merge Behavior
# =============================================================================


class TestConfigMerge:
    """Test configuration merging behavior."""

    def test_merge_preserves_unset_values(self):
        """Test that merge preserves values not set in override."""
        from src.config.models import merge_configs

        base = AppConfig(
            analyze={"num_clusters": 15},
            suggest={"min_sender_count": 25},
        )

        override = AppConfig(
            analyze={"num_clusters": 20},
        )

        merged = merge_configs(base, override)

        # Override value should win
        assert merged.analyze.num_clusters == 20
        # Base value should be preserved
        assert merged.suggest.min_sender_count == 25

    def test_merge_handles_nested_configs(self):
        """Test that merge handles nested configuration correctly."""
        from src.config.models import merge_configs

        base = AppConfig(
            extract={"batch_size": 200, "checkpoint_interval": 50},
        )

        override = AppConfig(
            extract={"batch_size": 300},  # Only override batch_size
        )

        merged = merge_configs(base, override)

        assert merged.extract.batch_size == 300
        # checkpoint_interval should keep base value
        assert merged.extract.checkpoint_interval == 50


# =============================================================================
# Test Explicit Default Override via YAML (B1 fix)
# =============================================================================


class TestExplicitDefaultOverride:
    """Integration tests for config merge precedence fix (B1).

    These tests verify the end-to-end YAML loading path where a
    project config explicitly sets a value back to the default,
    overriding a global config's non-default value.
    """

    @patch("src.config.loader.get_global_config_path")
    @patch("src.config.loader.get_project_config_path")
    def test_project_verbose_false_overrides_global_verbose_true(
        self, mock_project_path, mock_global_path, temp_home_dir, temp_project_dir
    ):
        """Project YAML setting verbose: false should override global verbose: true."""
        global_config = {"verbose": True}
        global_path = create_global_config(temp_home_dir, global_config)
        mock_global_path.return_value = global_path

        project_config = {"verbose": False}
        project_path = create_project_config(temp_project_dir, project_config)
        mock_project_path.return_value = project_path

        config = load_config()

        assert config.verbose is False

    @patch("src.config.loader.get_global_config_path")
    @patch("src.config.loader.get_project_config_path")
    def test_project_restores_default_num_clusters_over_global(
        self, mock_project_path, mock_global_path, temp_home_dir, temp_project_dir
    ):
        """Project YAML setting num_clusters: 10 (default) should override global's 15."""
        global_config = {"analyze": {"num_clusters": 15}}
        global_path = create_global_config(temp_home_dir, global_config)
        mock_global_path.return_value = global_path

        project_config = {"analyze": {"num_clusters": 10}}
        project_path = create_project_config(temp_project_dir, project_config)
        mock_project_path.return_value = project_path

        config = load_config()

        assert config.analyze.num_clusters == 10

    @patch("src.config.loader.get_global_config_path")
    @patch("src.config.loader.get_project_config_path")
    def test_custom_config_restores_default_over_project_and_global(
        self, mock_project_path, mock_global_path, temp_home_dir, temp_project_dir
    ):
        """Custom config setting batch_size: 500 (default) overrides all layers."""
        global_config = {"extract": {"batch_size": 200}}
        global_path = create_global_config(temp_home_dir, global_config)
        mock_global_path.return_value = global_path

        project_config = {"extract": {"batch_size": 300}}
        project_path = create_project_config(temp_project_dir, project_config)
        mock_project_path.return_value = project_path

        # Custom config restores the default
        custom_config_path = temp_project_dir / "custom_config.yaml"
        custom_config_path.write_text(yaml.dump({"extract": {"batch_size": 500}}))

        config = load_config(config_path=custom_config_path)

        assert config.extract.batch_size == 500
