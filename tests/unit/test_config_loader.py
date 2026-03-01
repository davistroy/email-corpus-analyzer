"""
Unit tests for configuration file loader.

Tests cover:
- src/config/loader.py - YAML loading with resolution order

Following TDD: these tests were written BEFORE implementation.
"""

import os
from pathlib import Path
from unittest.mock import mock_open, patch

import pytest


class TestGetGlobalConfigPath:
    """Test cases for get_global_config_path function."""

    def test_get_global_config_path_returns_path_in_user_config_dir(self):
        """Test global config path is in user's config directory."""
        from src.config.loader import get_global_config_path

        path = get_global_config_path()

        assert isinstance(path, Path)
        assert "email-analyzer" in str(path)
        assert path.name == "config.yaml"

    @patch.dict(os.environ, {"HOME": "/home/testuser"})
    def test_get_global_config_path_uses_home_on_linux(self):
        """Test global config uses ~/.config on Linux."""
        from src.config.loader import get_global_config_path

        with patch("platform.system", return_value="Linux"):
            path = get_global_config_path()

            # Should be under home directory
            assert ".config" in str(path) or "email-analyzer" in str(path)

    @patch.dict(os.environ, {"APPDATA": "C:\\Users\\Test\\AppData\\Roaming"})
    def test_get_global_config_path_uses_appdata_on_windows(self):
        """Test global config uses APPDATA on Windows."""
        from src.config.loader import get_global_config_path

        with patch("platform.system", return_value="Windows"):
            path = get_global_config_path()

            # Should contain email-analyzer
            assert "email-analyzer" in str(path)


class TestGetProjectConfigPath:
    """Test cases for get_project_config_path function."""

    def test_get_project_config_path_returns_path_in_cwd(self):
        """Test project config path is in current working directory."""
        from src.config.loader import get_project_config_path

        path = get_project_config_path()

        assert isinstance(path, Path)
        assert path.name == ".email-analyzer.yaml"

    def test_get_project_config_path_with_custom_directory(self):
        """Test project config path with custom directory."""
        from src.config.loader import get_project_config_path

        path = get_project_config_path(Path("/custom/project"))

        assert path == Path("/custom/project/.email-analyzer.yaml")


class TestLoadYamlFile:
    """Test cases for load_yaml_file function."""

    def test_load_yaml_file_returns_dict(self):
        """Test loading valid YAML returns dictionary."""
        from src.config.loader import load_yaml_file

        yaml_content = """
output_dir: /custom/output
user_email: test@example.com
verbose: true
extract:
  batch_size: 300
"""
        with (
            patch("builtins.open", mock_open(read_data=yaml_content)),
            patch("pathlib.Path.exists", return_value=True),
        ):
            result = load_yaml_file(Path("/config.yaml"))

        assert isinstance(result, dict)
        assert result["output_dir"] == "/custom/output"
        assert result["user_email"] == "test@example.com"
        assert result["verbose"] is True
        assert result["extract"]["batch_size"] == 300

    def test_load_yaml_file_missing_file_returns_empty_dict(self):
        """Test loading missing file returns empty dictionary."""
        from src.config.loader import load_yaml_file

        with patch("pathlib.Path.exists", return_value=False):
            result = load_yaml_file(Path("/nonexistent.yaml"))

        assert result == {}

    def test_load_yaml_file_empty_file_returns_empty_dict(self):
        """Test loading empty file returns empty dictionary."""
        from src.config.loader import load_yaml_file

        with (
            patch("builtins.open", mock_open(read_data="")),
            patch("pathlib.Path.exists", return_value=True),
        ):
            result = load_yaml_file(Path("/empty.yaml"))

        assert result == {}

    def test_load_yaml_file_invalid_yaml_raises_error(self):
        """Test loading invalid YAML raises ConfigLoadError."""
        from src.config.loader import ConfigLoadError, load_yaml_file

        invalid_yaml = """
output_dir: /path
  bad_indent: value
"""
        with (
            patch("builtins.open", mock_open(read_data=invalid_yaml)),
            patch("pathlib.Path.exists", return_value=True),
            pytest.raises(ConfigLoadError) as exc_info,
        ):
            load_yaml_file(Path("/invalid.yaml"))

        assert "invalid.yaml" in str(exc_info.value)

    def test_load_yaml_file_permission_error(self):
        """Test loading file with permission error raises ConfigLoadError."""
        from src.config.loader import ConfigLoadError, load_yaml_file

        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("builtins.open", side_effect=PermissionError("Access denied")),
            pytest.raises(ConfigLoadError) as exc_info,
        ):
            load_yaml_file(Path("/protected.yaml"))

        assert "permission" in str(exc_info.value).lower() or "Access denied" in str(exc_info.value)


class TestLoadConfig:
    """Test cases for load_config function - main loading function."""

    def test_load_config_returns_app_config(self):
        """Test load_config returns AppConfig instance."""
        from src.config.loader import load_config
        from src.config.models import AppConfig

        with patch("src.config.loader.load_yaml_file", return_value={}):
            config = load_config()

        assert isinstance(config, AppConfig)

    def test_load_config_with_defaults_only(self):
        """Test load_config with no config files returns defaults."""
        from src.config.loader import load_config

        with patch("src.config.loader.load_yaml_file", return_value={}):
            config = load_config()

        assert config.extract.batch_size == 500
        assert config.extract.checkpoint_interval == 100
        assert config.analyze.num_clusters == 10
        assert config.suggest.min_cluster_percentage == 5.0
        assert config.suggest.min_sender_count == 20

    def test_load_config_with_global_config(self):
        """Test load_config loads from global config."""
        from src.config.loader import load_config

        global_yaml = {"user_email": "global@example.com", "extract": {"batch_size": 300}}

        def mock_load(path):
            if "email-analyzer" in str(path):  # Global path
                return global_yaml
            return {}

        with patch("src.config.loader.load_yaml_file", side_effect=mock_load):
            config = load_config()

        assert config.user_email == "global@example.com"
        assert config.extract.batch_size == 300

    def test_load_config_with_project_config(self):
        """Test load_config loads from project config."""
        from src.config.loader import load_config

        project_yaml = {"extract": {"checkpoint_interval": 50}, "analyze": {"num_clusters": 20}}

        def mock_load(path):
            if ".email-analyzer.yaml" in str(path):  # Project path
                return project_yaml
            return {}

        with patch("src.config.loader.load_yaml_file", side_effect=mock_load):
            config = load_config()

        assert config.extract.checkpoint_interval == 50
        assert config.analyze.num_clusters == 20

    def test_load_config_project_overrides_global(self):
        """Test project config takes precedence over global."""
        from src.config.loader import load_config

        def mock_load(path):
            if "email-analyzer" in str(path) and "config.yaml" in str(path):
                return {"extract": {"batch_size": 300}}
            if ".email-analyzer.yaml" in str(path):
                return {"extract": {"batch_size": 200}}
            return {}

        with patch("src.config.loader.load_yaml_file", side_effect=mock_load):
            config = load_config()

        # Project (200) should override global (300)
        assert config.extract.batch_size == 200

    def test_load_config_with_custom_config_path(self):
        """Test load_config with custom config file path."""
        from src.config.loader import load_config

        custom_yaml = {"output_dir": "/custom/output", "verbose": True}

        custom_path = Path("/my/custom/config.yaml")

        def mock_load(path):
            # Check if this is the custom path by comparing Path objects
            if path == custom_path:
                return custom_yaml
            return {}

        with patch("src.config.loader.load_yaml_file", side_effect=mock_load):
            config = load_config(config_path=custom_path)

        assert config.output_dir == Path("/custom/output")
        assert config.verbose is True

    def test_load_config_custom_overrides_project_and_global(self):
        """Test custom config takes precedence over project and global."""
        from src.config.loader import load_config

        def mock_load(path):
            if "email-analyzer" in str(path) and "config.yaml" in str(path):
                return {"extract": {"batch_size": 300}}
            if ".email-analyzer.yaml" in str(path):
                return {"extract": {"batch_size": 200}}
            if "custom" in str(path):
                return {"extract": {"batch_size": 100}}
            return {}

        with patch("src.config.loader.load_yaml_file", side_effect=mock_load):
            config = load_config(config_path=Path("/custom/config.yaml"))

        # Custom (100) should override all
        assert config.extract.batch_size == 100

    def test_load_config_invalid_values_raises_error(self):
        """Test load_config raises error for invalid config values."""
        from src.config.loader import ConfigLoadError, load_config

        invalid_yaml = {
            "extract": {"batch_size": -1}  # Invalid: must be positive
        }

        with (
            patch("src.config.loader.load_yaml_file", return_value=invalid_yaml),
            pytest.raises(ConfigLoadError) as exc_info,
        ):
            load_config()

        assert (
            "batch_size" in str(exc_info.value).lower()
            or "validation" in str(exc_info.value).lower()
        )

    def test_load_config_invalid_email_raises_error(self):
        """Test load_config raises error for invalid email format."""
        from src.config.loader import ConfigLoadError, load_config

        invalid_yaml = {"user_email": "not-an-email"}

        with (
            patch("src.config.loader.load_yaml_file", return_value=invalid_yaml),
            pytest.raises(ConfigLoadError) as exc_info,
        ):
            load_config()

        assert "email" in str(exc_info.value).lower() or "validation" in str(exc_info.value).lower()

    def test_load_config_preserves_defaults_for_missing_keys(self):
        """Test load_config uses defaults for keys not in config files."""
        from src.config.loader import load_config

        partial_yaml = {
            "extract": {"batch_size": 250}
            # checkpoint_interval not specified
        }

        with patch("src.config.loader.load_yaml_file", return_value=partial_yaml):
            config = load_config()

        assert config.extract.batch_size == 250
        assert config.extract.checkpoint_interval == 100  # Default preserved


class TestConfigLoadError:
    """Test cases for ConfigLoadError exception."""

    def test_config_load_error_is_exception(self):
        """Test ConfigLoadError is an Exception."""
        from src.config.loader import ConfigLoadError

        error = ConfigLoadError("test error")

        assert isinstance(error, Exception)
        assert str(error) == "test error"

    def test_config_load_error_includes_path(self):
        """Test ConfigLoadError can include file path info."""
        from src.config.loader import ConfigLoadError

        error = ConfigLoadError("Invalid YAML in /path/to/config.yaml: syntax error")

        assert "/path/to/config.yaml" in str(error)


class TestGenerateTemplate:
    """Test cases for generate_template function."""

    def test_generate_template_returns_string(self):
        """Test generate_template returns YAML string."""
        from src.config.loader import generate_template

        template = generate_template()

        assert isinstance(template, str)
        assert len(template) > 0

    def test_generate_template_contains_all_sections(self):
        """Test template contains all configuration sections."""
        from src.config.loader import generate_template

        template = generate_template()

        assert "output_dir" in template
        assert "user_email" in template
        assert "verbose" in template
        assert "extract:" in template
        assert "analyze:" in template
        assert "suggest:" in template
        assert "review:" in template
        assert "pipeline:" in template

    def test_generate_template_contains_default_values(self):
        """Test template contains default values."""
        from src.config.loader import generate_template

        template = generate_template()

        assert "batch_size:" in template
        assert "500" in template
        assert "checkpoint_interval:" in template
        assert "100" in template
        assert "num_clusters:" in template
        assert "10" in template

    def test_generate_template_is_valid_yaml(self):
        """Test generated template is valid YAML."""
        import yaml

        from src.config.loader import generate_template

        template = generate_template()

        # Should parse without error
        parsed = yaml.safe_load(template)

        assert isinstance(parsed, dict)

    def test_generate_template_has_comments(self):
        """Test template has helpful comments."""
        from src.config.loader import generate_template

        template = generate_template()

        # Should have comment markers
        assert "#" in template


class TestShowResolvedConfig:
    """Test cases for show_resolved_config function."""

    def test_show_resolved_config_returns_string(self):
        """Test show_resolved_config returns formatted string."""
        from src.config.loader import show_resolved_config
        from src.config.models import AppConfig

        config = AppConfig()
        output = show_resolved_config(config)

        assert isinstance(output, str)

    def test_show_resolved_config_includes_all_fields(self):
        """Test output includes all config fields."""
        from src.config.loader import show_resolved_config
        from src.config.models import AppConfig

        config = AppConfig(user_email="test@example.com")
        output = show_resolved_config(config)

        assert "user_email" in output
        assert "test@example.com" in output
        assert "extract" in output
        assert "analyze" in output

    def test_show_resolved_config_yaml_format(self):
        """Test output is valid YAML format."""
        import yaml

        from src.config.loader import show_resolved_config
        from src.config.models import AppConfig

        config = AppConfig()
        output = show_resolved_config(config)

        # Should parse as YAML
        parsed = yaml.safe_load(output)
        assert isinstance(parsed, dict)


class TestIntegration:
    """Integration tests for config loading."""

    def test_full_config_loading_workflow(self, tmp_path):
        """Test complete config loading with actual files."""
        import yaml

        from src.config.loader import load_yaml_file

        # Create a temporary config file
        config_file = tmp_path / "config.yaml"
        config_data = {
            "user_email": "test@example.com",
            "extract": {"batch_size": 250, "checkpoint_interval": 50},
        }
        config_file.write_text(yaml.dump(config_data))

        # Load with the actual file
        loaded = load_yaml_file(config_file)

        assert loaded["user_email"] == "test@example.com"
        assert loaded["extract"]["batch_size"] == 250

    def test_empty_yaml_file_handling(self, tmp_path):
        """Test handling of empty YAML file."""
        from src.config.loader import load_yaml_file

        empty_file = tmp_path / "empty.yaml"
        empty_file.write_text("")

        result = load_yaml_file(empty_file)

        assert result == {}

    def test_yaml_with_only_comments(self, tmp_path):
        """Test handling of YAML with only comments."""
        from src.config.loader import load_yaml_file

        comments_only = tmp_path / "comments.yaml"
        comments_only.write_text("# This is a comment\n# Another comment\n")

        result = load_yaml_file(comments_only)

        assert result == {}


class TestGenerateTemplateSchedulerMonitoring:
    """Test cases for generate_template with scheduler and monitoring sections."""

    def test_generate_template_contains_scheduler_section(self):
        """Test template contains scheduler configuration section."""
        from src.config.loader import generate_template

        template = generate_template()

        assert "scheduler:" in template or "# scheduler:" in template
        assert "enabled" in template
        assert "interval_hours" in template
        assert "run_at" in template
        assert "tasks" in template

    def test_generate_template_contains_monitoring_section(self):
        """Test template contains monitoring configuration section."""
        from src.config.loader import generate_template

        template = generate_template()

        assert "monitoring:" in template or "# monitoring:" in template
        assert "drift_threshold" in template
        assert "volume_anomaly_stddev" in template
        assert "alert_channels" in template
        assert "check_interval_hours" in template

    def test_generate_template_scheduler_defaults(self):
        """Test template contains scheduler default values."""
        from src.config.loader import generate_template

        template = generate_template()

        assert "02:00" in template
        assert "24" in template

    def test_generate_template_monitoring_defaults(self):
        """Test template contains monitoring default values."""
        from src.config.loader import generate_template

        template = generate_template()

        assert "0.15" in template
        assert "2.0" in template

    def test_generate_template_with_new_sections_is_valid_yaml(self):
        """Test generated template with new sections is still valid YAML."""
        import yaml

        from src.config.loader import generate_template

        template = generate_template()
        parsed = yaml.safe_load(template)

        assert isinstance(parsed, dict)


class TestShowResolvedConfigSchedulerMonitoring:
    """Test show_resolved_config includes scheduler and monitoring."""

    def test_show_resolved_config_includes_scheduler(self):
        """Test output includes scheduler section."""
        from src.config.loader import show_resolved_config
        from src.config.models import AppConfig

        config = AppConfig()
        output = show_resolved_config(config)

        assert "scheduler" in output
        assert "enabled" in output

    def test_show_resolved_config_includes_monitoring(self):
        """Test output includes monitoring section."""
        from src.config.loader import show_resolved_config
        from src.config.models import AppConfig

        config = AppConfig()
        output = show_resolved_config(config)

        assert "monitoring" in output
        assert "drift_threshold" in output


class TestLoadConfigSchedulerMonitoring:
    """Test load_config with scheduler and monitoring YAML sections."""

    def test_load_config_with_scheduler_section(self):
        """Test load_config loads scheduler section from YAML."""
        from src.config.loader import load_config

        yaml_data = {
            "scheduler": {
                "enabled": True,
                "interval_hours": 12,
                "run_at": "03:00",
                "tasks": ["extract", "analyze"],
            }
        }

        with patch("src.config.loader.load_yaml_file", return_value=yaml_data):
            config = load_config()

        assert config.scheduler.enabled is True
        assert config.scheduler.interval_hours == 12
        assert config.scheduler.run_at == "03:00"
        assert config.scheduler.tasks == ["extract", "analyze"]

    def test_load_config_with_monitoring_section(self):
        """Test load_config loads monitoring section from YAML."""
        from src.config.loader import load_config

        yaml_data = {
            "monitoring": {
                "drift_threshold": 0.25,
                "volume_anomaly_stddev": 3.0,
                "alert_channels": ["desktop", "email"],
                "check_interval_hours": 12,
            }
        }

        with patch("src.config.loader.load_yaml_file", return_value=yaml_data):
            config = load_config()

        assert config.monitoring.drift_threshold == 0.25
        assert config.monitoring.volume_anomaly_stddev == 3.0
        assert config.monitoring.alert_channels == ["desktop", "email"]
        assert config.monitoring.check_interval_hours == 12

    def test_load_config_invalid_scheduler_raises_error(self):
        """Test load_config raises error for invalid scheduler config."""
        from src.config.loader import ConfigLoadError, load_config

        yaml_data = {
            "scheduler": {
                "interval_hours": -1,
            }
        }

        with (
            patch("src.config.loader.load_yaml_file", return_value=yaml_data),
            pytest.raises(ConfigLoadError),
        ):
            load_config()

    def test_load_config_invalid_monitoring_raises_error(self):
        """Test load_config raises error for invalid monitoring config."""
        from src.config.loader import ConfigLoadError, load_config

        yaml_data = {
            "monitoring": {
                "drift_threshold": 5.0,
            }
        }

        with (
            patch("src.config.loader.load_yaml_file", return_value=yaml_data),
            pytest.raises(ConfigLoadError),
        ):
            load_config()


class TestValidateConfigSchedulerMonitoring:
    """Test validate_config with scheduler and monitoring sections."""

    def test_validate_config_scheduler_ok_when_default(self):
        """Test validate_config reports ok for default scheduler."""
        from src.cli.commands.config import validate_config
        from src.config.models import AppConfig

        config = AppConfig()
        results = validate_config(config)

        scheduler_results = [r for r in results if r["field"].startswith("scheduler")]
        assert len(scheduler_results) >= 1
        assert all(r["status"] == "ok" for r in scheduler_results)

    def test_validate_config_monitoring_ok_when_default(self):
        """Test validate_config reports ok for default monitoring."""
        from src.cli.commands.config import validate_config
        from src.config.models import AppConfig

        config = AppConfig()
        results = validate_config(config)

        monitoring_results = [r for r in results if r["field"].startswith("monitoring")]
        assert len(monitoring_results) >= 1
        assert all(r["status"] == "ok" for r in monitoring_results)

    def test_validate_config_scheduler_enabled_ok(self):
        """Test validate_config reports ok for enabled scheduler with valid config."""
        from src.cli.commands.config import validate_config
        from src.config.models import AppConfig, SchedulerConfig

        config = AppConfig(
            scheduler=SchedulerConfig(
                enabled=True,
                interval_hours=12,
                run_at="03:00",
                tasks=["extract", "analyze"],
            )
        )
        results = validate_config(config)

        scheduler_results = [r for r in results if r["field"].startswith("scheduler")]
        assert all(r["status"] in ("ok", "warning") for r in scheduler_results)

    def test_validate_config_monitoring_custom_ok(self):
        """Test validate_config reports ok for custom monitoring config."""
        from src.cli.commands.config import validate_config
        from src.config.models import AppConfig, MonitoringConfig

        config = AppConfig(
            monitoring=MonitoringConfig(
                drift_threshold=0.25,
                volume_anomaly_stddev=3.0,
                alert_channels=["desktop", "log"],
            )
        )
        results = validate_config(config)

        monitoring_results = [r for r in results if r["field"].startswith("monitoring")]
        assert all(r["status"] in ("ok", "warning") for r in monitoring_results)


class TestGenerateTemplateClassifier:
    """Test cases for generate_template with classifier section (Work Item 1.2)."""

    def test_generate_template_contains_classifier_section(self):
        """Test template contains classifier configuration section."""
        from src.config.loader import generate_template

        template = generate_template()

        assert "classifier" in template.lower()
        assert "provider" in template
        assert "model_name" in template
        assert "confidence_threshold" in template
        assert "categories" in template

    def test_generate_template_classifier_defaults_documented(self):
        """Test template documents classifier defaults."""
        from src.config.loader import generate_template

        template = generate_template()

        assert "ollama" in template
        assert "qwen2.5:7b" in template
        assert "0.6" in template

    def test_generate_template_with_classifier_is_valid_yaml(self):
        """Test generated template with classifier section is still valid YAML."""
        import yaml

        from src.config.loader import generate_template

        template = generate_template()
        parsed = yaml.safe_load(template)

        assert isinstance(parsed, dict)


class TestShowResolvedConfigClassifier:
    """Test show_resolved_config includes classifier section (Work Item 1.2)."""

    def test_show_resolved_config_includes_classifier(self):
        """Test output includes classifier section."""
        from src.config.loader import show_resolved_config
        from src.config.models import AppConfig

        config = AppConfig()
        output = show_resolved_config(config)

        assert "classifier" in output
        assert "provider" in output
        assert "ollama" in output


class TestLoadConfigClassifier:
    """Test load_config with classifier YAML section (Work Item 1.2)."""

    def test_load_config_with_classifier_section(self):
        """Test load_config loads classifier section from YAML."""
        from src.config.loader import load_config

        yaml_data = {
            "classifier": {
                "provider": "claude",
                "model_name": "claude-sonnet-4-20250514",
                "api_key_env_var": "ANTHROPIC_API_KEY",
                "confidence_threshold": 0.8,
                "categories": [
                    {"name": "Work", "description": "Work-related emails"},
                    {
                        "name": "Shopping",
                        "description": "Orders and receipts",
                        "keywords": ["order", "receipt"],
                    },
                ],
            }
        }

        with patch("src.config.loader.load_yaml_file", return_value=yaml_data):
            config = load_config()

        assert config.classifier.provider == "claude"
        assert config.classifier.model_name == "claude-sonnet-4-20250514"
        assert config.classifier.api_key_env_var == "ANTHROPIC_API_KEY"
        assert config.classifier.confidence_threshold == 0.8
        assert len(config.classifier.categories) == 2
        assert config.classifier.categories[0].name == "Work"
        assert config.classifier.categories[1].keywords == ["order", "receipt"]

    def test_load_config_invalid_classifier_provider_raises_error(self):
        """Test load_config raises error for invalid classifier provider."""
        from src.config.loader import ConfigLoadError, load_config

        yaml_data = {
            "classifier": {
                "provider": "invalid_provider",
            }
        }

        with (
            patch("src.config.loader.load_yaml_file", return_value=yaml_data),
            pytest.raises(ConfigLoadError),
        ):
            load_config()

    def test_load_config_invalid_classifier_url_raises_error(self):
        """Test load_config raises error for invalid ollama_base_url."""
        from src.config.loader import ConfigLoadError, load_config

        yaml_data = {
            "classifier": {
                "ollama_base_url": "not-a-url",
            }
        }

        with (
            patch("src.config.loader.load_yaml_file", return_value=yaml_data),
            pytest.raises(ConfigLoadError),
        ):
            load_config()

    def test_load_config_classifier_defaults_when_absent(self):
        """Test load_config uses classifier defaults when section is absent."""
        from src.config.loader import load_config

        with patch("src.config.loader.load_yaml_file", return_value={}):
            config = load_config()

        assert config.classifier.provider == "ollama"
        assert config.classifier.model_name == "qwen2.5:7b"
        assert config.classifier.categories == []
