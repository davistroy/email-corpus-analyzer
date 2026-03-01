"""
Configuration file loader for Email Corpus Analyzer.

Provides YAML configuration loading with resolution order:
1. Built-in defaults (from models)
2. Global config (~/.config/email-analyzer/config.yaml)
3. Project config (./.email-analyzer.yaml)
4. Custom config (--config flag)

Per Task 1A.2 specification.
"""

import os
import platform
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from src.config.models import AppConfig, merge_configs


class ConfigLoadError(Exception):
    """Raised when configuration loading fails."""


def get_global_config_path() -> Path:
    """
    Get path to global configuration file.

    Returns:
        Path to global config file:
        - Windows: %APPDATA%/email-analyzer/config.yaml
        - Linux/Mac: ~/.config/email-analyzer/config.yaml
    """
    system = platform.system()

    if system == "Windows":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))

    return base / "email-analyzer" / "config.yaml"


def get_project_config_path(directory: Path | None = None) -> Path:
    """
    Get path to project-level configuration file.

    Args:
        directory: Directory to check. Defaults to current working directory.

    Returns:
        Path to project config file (.email-analyzer.yaml)
    """
    if directory is None:
        directory = Path.cwd()
    return directory / ".email-analyzer.yaml"


def load_yaml_file(path: Path) -> dict[str, Any]:
    """
    Load YAML file and return contents as dictionary.

    Args:
        path: Path to YAML file

    Returns:
        Dictionary with file contents, or empty dict if file doesn't exist

    Raises:
        ConfigLoadError: If file exists but cannot be parsed
    """
    if not path.exists():
        return {}

    try:
        with open(path, encoding="utf-8") as f:
            content = yaml.safe_load(f)
            # Handle empty files or files with only comments
            if content is None:
                return {}
            result: dict[str, Any] = content
            return result
    except yaml.YAMLError as e:
        raise ConfigLoadError(f"Invalid YAML in {path}: {e}") from e
    except PermissionError as e:
        raise ConfigLoadError(f"Permission denied reading {path}: {e}") from e
    except OSError as e:
        raise ConfigLoadError(f"Error reading {path}: {e}") from e


def _dict_to_config(data: dict[str, Any]) -> AppConfig:
    """
    Convert dictionary to AppConfig, with validation.

    Args:
        data: Dictionary of config values

    Returns:
        AppConfig instance

    Raises:
        ConfigLoadError: If validation fails
    """
    try:
        return AppConfig(**data)
    except ValidationError as e:
        raise ConfigLoadError(f"Configuration validation error: {e}") from e


def load_config(config_path: Path | None = None, project_dir: Path | None = None) -> AppConfig:
    """
    Load configuration from all sources with proper precedence.

    Resolution order (later overrides earlier):
    1. Built-in defaults
    2. Global config (~/.config/email-analyzer/config.yaml)
    3. Project config (./.email-analyzer.yaml)
    4. Custom config (config_path argument)

    Args:
        config_path: Optional path to custom config file
        project_dir: Optional project directory to look for .email-analyzer.yaml

    Returns:
        Merged AppConfig with all settings resolved

    Raises:
        ConfigLoadError: If any config file is invalid
    """
    # Start with defaults
    result = AppConfig()

    # Load and merge global config
    global_path = get_global_config_path()
    global_data = load_yaml_file(global_path)
    if global_data:
        global_config = _dict_to_config(global_data)
        result = merge_configs(result, global_config)

    # Load and merge project config
    project_path = get_project_config_path(project_dir)
    project_data = load_yaml_file(project_path)
    if project_data:
        project_config = _dict_to_config(project_data)
        result = merge_configs(result, project_config)

    # Load and merge custom config if provided
    if config_path is not None:
        custom_data = load_yaml_file(config_path)
        if custom_data:
            custom_config = _dict_to_config(custom_data)
            result = merge_configs(result, custom_config)

    return result


def generate_template() -> str:
    """
    Generate a template YAML configuration file with all options.

    Returns:
        YAML string with all options commented and documented
    """
    template = """# Email Corpus Analyzer Configuration
# =====================================
# This file configures the email extraction and analysis pipeline.
# Uncomment and modify values as needed.

# Global Settings
# ---------------
# Output directory for all generated files
# output_dir: ~/data/outputs

# Your M365/Hotmail email address (required for extraction)
# user_email: your@email.com

# Enable verbose debug logging
# verbose: false

# Extract Command Settings
# ------------------------
extract:
  # Number of emails to fetch per batch
  batch_size: 500

  # Save checkpoint every N emails
  checkpoint_interval: 100

  # Custom path for corpus JSON (optional)
  # corpus_file: /path/to/corpus.json

# Analyze Command Settings
# ------------------------
analyze:
  # Number of semantic clusters for content analysis
  num_clusters: 10

  # Path to corpus JSON file (optional, uses default if not set)
  # corpus_file: /path/to/corpus.json

  # Custom path for analysis results (optional)
  # analysis_file: /path/to/analysis.json

# Suggest Command Settings
# ------------------------
suggest:
  # Minimum cluster size percentage for category generation
  min_cluster_percentage: 5.0

  # Minimum email count for sender-based categories
  min_sender_count: 20

  # Path to analysis results JSON (optional)
  # analysis_file: /path/to/analysis.json

  # Custom path for suggestions JSON (optional)
  # suggestions_file: /path/to/suggestions.json

# Review Command Settings
# -----------------------
review:
  # Path to suggestions JSON (optional)
  # suggestions_file: /path/to/suggestions.json

  # Custom path for approved categories (optional)
  # approved_file: /path/to/approved.json

  # Skip cleanup of intermediate files
  no_cleanup: false

# Pipeline Command Settings
# -------------------------
pipeline:
  # Number of semantic clusters
  num_clusters: 10

  # Skip cleanup of intermediate files
  no_cleanup: false

# Scheduler Settings (Phase 6 - Automated Processing)
# ---------------------------------------------------
scheduler:
  # Enable scheduled automated processing
  enabled: false

  # Hours between scheduled runs (1-168)
  interval_hours: 24

  # Time of day to run (HH:MM, 24-hour format)
  run_at: "02:00"

  # Ordered list of tasks to run: extract, analyze, categorize, move
  tasks:
    - extract
    - analyze
    - categorize
    - move

  # Automatically apply rules to new emails without review
  auto_categorize: false

  # Minimum new uncategorized emails before sending notification
  notification_threshold: 10

# Monitoring Settings (Phase 6 - Change Detection)
# -------------------------------------------------
monitoring:
  # Category match rate drop threshold to trigger drift alert (0.01-1.0)
  drift_threshold: 0.15

  # Standard deviations above mean volume to flag as anomaly (>0, max 10)
  volume_anomaly_stddev: 2.0

  # Alert delivery channels: desktop, log, email
  alert_channels:
    - log

  # Hours between monitoring checks (1-168)
  check_interval_hours: 6

  # Minimum emails in a new cluster before suggesting a new category
  new_cluster_threshold: 10
"""
    return template  # noqa: RET504


def show_resolved_config(config: AppConfig) -> str:
    """
    Format resolved configuration as YAML string for display.

    Args:
        config: AppConfig instance to display

    Returns:
        Formatted YAML string representation
    """
    # Convert to dict, handling Path objects
    data = config.model_dump()

    # Convert Path objects to strings for YAML serialization
    def convert_paths(obj: Any) -> Any:
        if isinstance(obj, Path):
            return str(obj)
        if isinstance(obj, dict):
            return {k: convert_paths(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [convert_paths(item) for item in obj]
        return obj

    data = convert_paths(data)

    return yaml.dump(data, default_flow_style=False, sort_keys=False)
