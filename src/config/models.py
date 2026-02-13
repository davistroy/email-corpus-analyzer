"""
Configuration data models for Email Corpus Analyzer.

Provides Pydantic models for all CLI configuration options with:
- Default values matching existing CLI defaults
- Validation rules for all parameters
- Nested configuration structure for each command

Per Task 1A.1 specification.
Task 2.2: Added AnalyzerThresholds and GeneratorThresholds for externalizing magic numbers.
"""
from pathlib import Path
from typing import Any

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator


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
    source: str = Field(
        default="hotmail",
        description="Email source: hotmail, gmail, or both"
    )
    gmail_email: str | None = Field(
        default=None,
        description="Gmail address (required when source is gmail or both)"
    )

    @field_validator("source")
    @classmethod
    def validate_source(cls, v: str) -> str:
        """Validate source is one of the allowed values."""
        allowed = ("hotmail", "gmail", "both")
        if v not in allowed:
            raise ValueError(f"source must be one of {allowed}, got '{v}'")
        return v

    @model_validator(mode="after")
    def validate_gmail_email_required(self) -> "ExtractConfig":
        """Ensure gmail_email is provided when source requires it."""
        if self.source in ("gmail", "both") and not self.gmail_email:
            raise ValueError(
                "gmail_email is required when source is "
                f"'{self.source}'"
            )
        return self


class AnalyzerThresholds(BaseModel):
    """
    Configurable thresholds for analyzer modules.

    All defaults match the previously-hardcoded values so behavior
    is unchanged without explicit configuration.
    """

    # SenderAnalyzer thresholds
    top_senders: int = Field(
        default=50,
        ge=1,
        le=1000,
        description="Number of top senders to extract by frequency"
    )
    top_domains: int = Field(
        default=30,
        ge=1,
        le=500,
        description="Number of top domains to extract by frequency"
    )
    marketing_min_emails: int = Field(
        default=10,
        ge=1,
        le=10000,
        description="Minimum email count to classify sender as marketing"
    )

    # SubjectAnalyzer thresholds
    top_keywords: int = Field(
        default=50,
        ge=1,
        le=1000,
        description="Number of top keywords to extract from subject lines"
    )

    # SemanticAnalyzer thresholds
    max_auto_clusters: int = Field(
        default=15,
        ge=2,
        le=100,
        description="Maximum number of clusters for auto-clustering optimization"
    )
    representative_samples: int = Field(
        default=5,
        ge=1,
        le=50,
        description="Number of representative samples per cluster (closest to centroid)"
    )
    random_state: int = Field(
        default=42,
        ge=0,
        description="Random state seed for KMeans clustering reproducibility"
    )

    # TemporalAnalyzer thresholds
    frequency_daily_threshold_days: float = Field(
        default=2.0,
        gt=0,
        le=365,
        description="Average interval (days) below which sender is classified as daily"
    )
    frequency_weekly_threshold_days: float = Field(
        default=8.0,
        gt=0,
        le=365,
        description="Average interval (days) below which sender is classified as weekly"
    )
    frequency_monthly_threshold_days: float = Field(
        default=35.0,
        gt=0,
        le=365,
        description="Average interval (days) below which sender is classified as monthly"
    )
    min_emails_for_frequency: int = Field(
        default=10,
        ge=2,
        le=10000,
        description="Minimum email count required for frequency classification beyond one-time"
    )


class AnalyzeConfig(BaseModel):
    """Configuration for analyze command."""

    num_clusters: int = Field(
        default=10,
        ge=1,
        le=1000,
        description="Number of semantic clusters"
    )
    max_embedding_text_length: int = Field(
        default=1500,
        ge=200,
        le=5000,
        description="Maximum body text characters for embedding generation"
    )
    auto_cluster_min: int = Field(
        default=3,
        ge=2,
        le=50,
        description="Minimum max_k bound for auto-clustering"
    )
    auto_cluster_max: int = Field(
        default=25,
        ge=3,
        le=100,
        description="Maximum max_k cap for auto-clustering"
    )
    corpus_file: Path | None = Field(
        default=None,
        description="Path to corpus JSON file"
    )
    analysis_file: Path | None = Field(
        default=None,
        description="Custom path for analysis results"
    )
    thresholds: AnalyzerThresholds = Field(
        default_factory=AnalyzerThresholds,
        description="Configurable thresholds for analyzer modules"
    )

    @model_validator(mode="after")
    def validate_auto_cluster_bounds(self) -> "AnalyzeConfig":
        """Ensure auto_cluster_min <= auto_cluster_max."""
        if self.auto_cluster_min > self.auto_cluster_max:
            raise ValueError(
                f"auto_cluster_min ({self.auto_cluster_min}) must be <= "
                f"auto_cluster_max ({self.auto_cluster_max})"
            )
        return self


class GeneratorThresholds(BaseModel):
    """
    Configurable thresholds for generator modules.

    All defaults match the previously-hardcoded values so behavior
    is unchanged without explicit configuration.
    """

    # CategoryGenerator thresholds
    max_senders_for_categories: int = Field(
        default=20,
        ge=1,
        le=1000,
        description="Maximum number of top senders to consider for sender-based categories"
    )
    merge_name_similarity: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Name similarity threshold for merging categories (SequenceMatcher ratio)"
    )
    merge_email_overlap: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Email ID overlap threshold (Jaccard) for merging categories"
    )

    # Confidence weight fields (Work Item 4.1)
    # These weights are used by calculate_confidence_enhanced and should sum to 1.0
    confidence_weight_cohesion: float = Field(
        default=0.15,
        ge=0.0,
        le=1.0,
        description="Confidence weight for cohesion (distinguishing features count)"
    )
    confidence_weight_volume: float = Field(
        default=0.20,
        ge=0.0,
        le=1.0,
        description="Confidence weight for volume (logarithmic email count scaling)"
    )
    confidence_weight_source: float = Field(
        default=0.25,
        ge=0.0,
        le=1.0,
        description="Confidence weight for source type reliability"
    )
    confidence_weight_percentage: float = Field(
        default=0.15,
        ge=0.0,
        le=1.0,
        description="Confidence weight for corpus percentage (10% = 1.0)"
    )
    confidence_weight_name_quality: float = Field(
        default=0.10,
        ge=0.0,
        le=1.0,
        description="Confidence weight for name quality score"
    )
    confidence_weight_distinctiveness: float = Field(
        default=0.15,
        ge=0.0,
        le=1.0,
        description="Confidence weight for distinctiveness (mean overlap penalty)"
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
    thresholds: GeneratorThresholds = Field(
        default_factory=GeneratorThresholds,
        description="Configurable thresholds for generator modules"
    )


class LearningConfig(BaseModel):
    """
    Configuration for the feedback learning system.

    Controls temporal decay of pattern detection and other
    learning-related parameters.
    """

    pattern_half_life_days: float = Field(
        default=90.0,
        gt=0,
        le=3650,
        description=(
            "Half-life in days for temporal decay of pattern confidence. "
            "A decision this many days old contributes 50% of a brand-new "
            "decision's weight. Default 90 days."
        ),
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
    learning: LearningConfig = Field(default_factory=LearningConfig)

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
        ("learning", LearningConfig),
    ]:
        base_nested = getattr(base, config_name)
        override_nested = getattr(override, config_name)
        defaults_nested = config_cls()

        merged_nested = _merge_nested_config(
            base_nested, override_nested, defaults_nested
        )
        merged[config_name] = config_cls(**merged_nested)

    return AppConfig(**merged)
