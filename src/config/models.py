"""
Configuration data models for Email Corpus Analyzer.

Provides Pydantic models for all CLI configuration options with:
- Default values matching existing CLI defaults
- Validation rules for all parameters
- Nested configuration structure for each command

Per Task 1A.1 specification.
"""
from pathlib import Path
from typing import Any

from pydantic import BaseModel, EmailStr, Field, field_validator


class ExtractConfig(BaseModel):
    """Configuration for extract command."""

    batch_size: int = Field(
        default=500,
        gt=0,
        le=100000,
        description="Number of emails to fetch per batch"
    )
    checkpoint_interval: int = Field(
        default=100,
        gt=0,
        le=10000,
        description="Save checkpoint every N emails"
    )
    corpus_file: Path | None = Field(
        default=None,
        description="Custom path for corpus JSON file"
    )


class AnalyzeConfig(BaseModel):
    """Configuration for analyze command."""

    num_clusters: int = Field(
        default=10,
        ge=1,
        le=1000,
        description="Number of semantic clusters"
    )
    corpus_file: Path | None = Field(
        default=None,
        description="Path to corpus JSON file"
    )
    analysis_file: Path | None = Field(
        default=None,
        description="Custom path for analysis results"
    )


class SuggestConfig(BaseModel):
    """Configuration for suggest command."""

    min_cluster_percentage: float = Field(
        default=5.0,
        ge=0,
        le=100,
        description="Minimum cluster size percentage for category generation"
    )
    min_sender_count: int = Field(
        default=20,
        ge=1,
        description="Minimum email count for sender-based categories"
    )
    analysis_file: Path | None = Field(
        default=None,
        description="Path to analysis results JSON"
    )
    suggestions_file: Path | None = Field(
        default=None,
        description="Custom path for suggestions JSON"
    )


class ReviewConfig(BaseModel):
    """Configuration for review command."""

    suggestions_file: Path | None = Field(
        default=None,
        description="Path to suggestions JSON"
    )
    approved_file: Path | None = Field(
        default=None,
        description="Custom path for approved categories"
    )
    no_cleanup: bool = Field(
        default=False,
        description="Skip optional cleanup of intermediate files"
    )


class PipelineConfig(BaseModel):
    """Configuration for pipeline command."""

    num_clusters: int = Field(
        default=10,
        ge=1,
        le=1000,
        description="Number of semantic clusters"
    )
    no_cleanup: bool = Field(
        default=False,
        description="Skip optional cleanup of intermediate files"
    )


class AppConfig(BaseModel):
    """Root application configuration containing all options."""

    # Global options
    output_dir: Path | None = Field(
        default=None,
        description="Output directory for all files"
    )
    user_email: EmailStr | None = Field(
        default=None,
        description="M365/Hotmail email address"
    )
    verbose: bool = Field(
        default=False,
        description="Enable verbose debug logging"
    )

    # Command-specific configurations
    extract: ExtractConfig = Field(default_factory=ExtractConfig)
    analyze: AnalyzeConfig = Field(default_factory=AnalyzeConfig)
    suggest: SuggestConfig = Field(default_factory=SuggestConfig)
    review: ReviewConfig = Field(default_factory=ReviewConfig)
    pipeline: PipelineConfig = Field(default_factory=PipelineConfig)

    @field_validator("output_dir", mode="before")
    @classmethod
    def convert_output_dir_to_path(cls, v: Any) -> Path | None:
        """Convert string output_dir to Path."""
        if v is None:
            return None
        if isinstance(v, str):
            return Path(v)
        return v


def _merge_nested_config(
    base: BaseModel,
    override: BaseModel,
    defaults: BaseModel
) -> dict[str, Any]:
    """
    Merge two nested config models, preserving base values for None overrides.

    Args:
        base: Base configuration to start from
        override: Configuration with override values
        defaults: Default configuration to check for non-default values

    Returns:
        Merged dictionary suitable for model construction
    """
    result = {}
    base_dict = base.model_dump()
    override_dict = override.model_dump()
    defaults_dict = defaults.model_dump()

    for key in base_dict:
        base_val = base_dict[key]
        override_val = override_dict[key]
        default_val = defaults_dict[key]

        # If override has a non-default value, use it
        # Otherwise use the base value
        if override_val != default_val:
            result[key] = override_val
        else:
            result[key] = base_val

    return result


def merge_configs(base: AppConfig, override: AppConfig) -> AppConfig:
    """
    Merge two AppConfig instances with override taking precedence.

    Values in override replace values in base, except when override value
    is None or matches the default value.

    Args:
        base: Base configuration
        override: Configuration with override values

    Returns:
        New AppConfig with merged values
    """
    defaults = AppConfig()

    # Merge top-level fields
    merged = {}

    # Handle simple fields
    for field in ["output_dir", "user_email", "verbose"]:
        base_val = getattr(base, field)
        override_val = getattr(override, field)
        default_val = getattr(defaults, field)

        # Use override if it's not None/default, else use base
        if override_val is not None and override_val != default_val:
            merged[field] = override_val
        else:
            merged[field] = base_val

    # Handle nested configs
    for config_name, config_cls in [
        ("extract", ExtractConfig),
        ("analyze", AnalyzeConfig),
        ("suggest", SuggestConfig),
        ("review", ReviewConfig),
        ("pipeline", PipelineConfig),
    ]:
        base_nested = getattr(base, config_name)
        override_nested = getattr(override, config_name)
        defaults_nested = config_cls()

        merged_nested = _merge_nested_config(
            base_nested, override_nested, defaults_nested
        )
        merged[config_name] = config_cls(**merged_nested)

    return AppConfig(**merged)
