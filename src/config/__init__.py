"""
Configuration module for Email Corpus Analyzer.

Provides:
- Configuration data models (Pydantic)
- YAML config file loading
- Config merging with precedence resolution
"""

from src.config.loader import (
    ConfigLoadError,
    generate_template,
    get_global_config_path,
    get_project_config_path,
    load_config,
    load_yaml_file,
    show_resolved_config,
)
from src.config.models import (
    AnalyzeConfig,
    AppConfig,
    ExtractConfig,
    PipelineConfig,
    ReviewConfig,
    SuggestConfig,
    merge_configs,
)

__all__ = [
    # Models
    "AppConfig",
    "AnalyzeConfig",
    "ExtractConfig",
    "PipelineConfig",
    "ReviewConfig",
    "SuggestConfig",
    "merge_configs",
    # Loader
    "ConfigLoadError",
    "generate_template",
    "get_global_config_path",
    "get_project_config_path",
    "load_config",
    "load_yaml_file",
    "show_resolved_config",
]
