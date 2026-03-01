"""
Configuration data models for Email Corpus Analyzer.

Provides Pydantic models for all CLI configuration options with:
- Default values matching existing CLI defaults
- Validation rules for all parameters
- Nested configuration structure for each command

Per Task 1A.1 specification.
Task 2.2: Added AnalyzerThresholds and GeneratorThresholds for externalizing magic numbers.
Phase 6, Item 6.5: Added SchedulerConfig and MonitoringConfig for automation.
"""

import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

# Valid task names for scheduler
VALID_SCHEDULER_TASKS = ("extract", "analyze", "categorize", "move")

# Valid alert channel names for monitoring
VALID_ALERT_CHANNELS = ("desktop", "log", "email", "console")

# Regex for HH:MM time format (00:00 - 23:59)
TIME_FORMAT_RE = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")


class ExtractConfig(BaseModel):
    """Configuration for extract command."""

    batch_size: int = Field(
        default=500, gt=0, le=100000, description="Number of emails to fetch per batch"
    )
    checkpoint_interval: int = Field(
        default=100, gt=0, le=10000, description="Save checkpoint every N emails"
    )
    corpus_file: Path | None = Field(default=None, description="Custom path for corpus JSON file")
    source: str = Field(default="hotmail", description="Email source: hotmail, gmail, or both")
    gmail_email: str | None = Field(
        default=None, description="Gmail address (required when source is gmail or both)"
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
            raise ValueError(f"gmail_email is required when source is '{self.source}'")
        return self


class AnalyzerThresholds(BaseModel):
    """
    Configurable thresholds for analyzer modules.

    All defaults match the previously-hardcoded values so behavior
    is unchanged without explicit configuration.
    """

    # SenderAnalyzer thresholds
    top_senders: int = Field(
        default=50, ge=1, le=1000, description="Number of top senders to extract by frequency"
    )
    top_domains: int = Field(
        default=30, ge=1, le=500, description="Number of top domains to extract by frequency"
    )
    marketing_min_emails: int = Field(
        default=10,
        ge=1,
        le=10000,
        description="Minimum email count to classify sender as marketing",
    )

    # SubjectAnalyzer thresholds
    top_keywords: int = Field(
        default=50,
        ge=1,
        le=1000,
        description="Number of top keywords to extract from subject lines",
    )

    # SemanticAnalyzer thresholds
    max_auto_clusters: int = Field(
        default=15,
        ge=2,
        le=100,
        description="Maximum number of clusters for auto-clustering optimization",
    )
    representative_samples: int = Field(
        default=5,
        ge=1,
        le=50,
        description="Number of representative samples per cluster (closest to centroid)",
    )
    random_state: int = Field(
        default=42, ge=0, description="Random state seed for KMeans clustering reproducibility"
    )

    # SenderAnalyzer classification keywords
    service_keywords: list[str] = Field(
        default=[
            "noreply",
            "no-reply",
            "donotreply",
            "notification",
            "notify",
            "alert",
        ],
        description="Keywords in sender email/domain that indicate a service/automated sender",
    )
    marketing_keywords: list[str] = Field(
        default=[
            "unsubscribe",
            "promotional",
            "offer",
            "discount",
            "sale",
            "promotion",
        ],
        description="Keywords in subject lines that indicate marketing emails",
    )
    work_keywords: list[str] = Field(
        default=[
            "meeting",
            "project",
            "team",
            "re:",
            "fwd:",
        ],
        description="Keywords in subject lines that indicate work-related emails",
    )

    # TemporalAnalyzer thresholds
    frequency_daily_threshold_days: float = Field(
        default=2.0,
        gt=0,
        le=365,
        description="Average interval (days) below which sender is classified as daily",
    )
    frequency_weekly_threshold_days: float = Field(
        default=8.0,
        gt=0,
        le=365,
        description="Average interval (days) below which sender is classified as weekly",
    )
    frequency_monthly_threshold_days: float = Field(
        default=35.0,
        gt=0,
        le=365,
        description="Average interval (days) below which sender is classified as monthly",
    )
    min_emails_for_frequency: int = Field(
        default=10,
        ge=2,
        le=10000,
        description="Minimum email count required for frequency classification beyond one-time",
    )


class AnalyzeConfig(BaseModel):
    """Configuration for analyze command."""

    num_clusters: int = Field(default=10, ge=1, le=1000, description="Number of semantic clusters")
    max_embedding_text_length: int = Field(
        default=1500,
        ge=200,
        le=5000,
        description="Maximum body text characters for embedding generation",
    )
    auto_cluster_min: int = Field(
        default=3, ge=2, le=50, description="Minimum max_k bound for auto-clustering"
    )
    auto_cluster_max: int = Field(
        default=25, ge=3, le=100, description="Maximum max_k cap for auto-clustering"
    )
    corpus_file: Path | None = Field(default=None, description="Path to corpus JSON file")
    analysis_file: Path | None = Field(default=None, description="Custom path for analysis results")
    thresholds: AnalyzerThresholds = Field(
        default_factory=AnalyzerThresholds,
        description="Configurable thresholds for analyzer modules",
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
        description="Maximum number of top senders to consider for sender-based categories",
    )
    merge_name_similarity: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Name similarity threshold for merging categories (SequenceMatcher ratio)",
    )
    merge_email_overlap: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Email ID overlap threshold (Jaccard) for merging categories",
    )

    # Confidence weight fields (Work Item 4.1)
    # These weights are used by calculate_confidence_enhanced and should sum to 1.0
    confidence_weight_cohesion: float = Field(
        default=0.15,
        ge=0.0,
        le=1.0,
        description="Confidence weight for cohesion (distinguishing features count)",
    )
    confidence_weight_volume: float = Field(
        default=0.20,
        ge=0.0,
        le=1.0,
        description="Confidence weight for volume (logarithmic email count scaling)",
    )
    confidence_weight_source: float = Field(
        default=0.25, ge=0.0, le=1.0, description="Confidence weight for source type reliability"
    )
    confidence_weight_percentage: float = Field(
        default=0.15,
        ge=0.0,
        le=1.0,
        description="Confidence weight for corpus percentage (10% = 1.0)",
    )
    confidence_weight_name_quality: float = Field(
        default=0.10, ge=0.0, le=1.0, description="Confidence weight for name quality score"
    )
    confidence_weight_distinctiveness: float = Field(
        default=0.15,
        ge=0.0,
        le=1.0,
        description="Confidence weight for distinctiveness (mean overlap penalty)",
    )

    @model_validator(mode="after")
    def validate_confidence_weights_sum(self) -> "GeneratorThresholds":
        """Ensure confidence weights sum to approximately 1.0."""
        total = (
            self.confidence_weight_cohesion
            + self.confidence_weight_volume
            + self.confidence_weight_source
            + self.confidence_weight_percentage
            + self.confidence_weight_name_quality
            + self.confidence_weight_distinctiveness
        )
        if not (0.99 <= total <= 1.01):
            raise ValueError(f"confidence_weight_* fields must sum to 1.0, got {total:.4f}")
        return self


class SuggestConfig(BaseModel):
    """Configuration for suggest command."""

    min_cluster_percentage: float = Field(
        default=5.0,
        ge=0,
        le=100,
        description="Minimum cluster size percentage for category generation",
    )
    min_sender_count: int = Field(
        default=20, ge=1, description="Minimum email count for sender-based categories"
    )
    analysis_file: Path | None = Field(default=None, description="Path to analysis results JSON")
    suggestions_file: Path | None = Field(
        default=None, description="Custom path for suggestions JSON"
    )
    templates_path: Path | None = Field(
        default=None, description="Path to custom category templates JSON file"
    )
    thresholds: GeneratorThresholds = Field(
        default_factory=GeneratorThresholds,
        description="Configurable thresholds for generator modules",
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

    suggestions_file: Path | None = Field(default=None, description="Path to suggestions JSON")
    approved_file: Path | None = Field(
        default=None, description="Custom path for approved categories"
    )
    no_cleanup: bool = Field(
        default=False, description="Skip optional cleanup of intermediate files"
    )


class PipelineConfig(BaseModel):
    """Configuration for pipeline command."""

    num_clusters: int = Field(default=10, ge=1, le=1000, description="Number of semantic clusters")
    no_cleanup: bool = Field(
        default=False, description="Skip optional cleanup of intermediate files"
    )


class SchedulerConfig(BaseModel):
    """
    Configuration for automated scheduled processing.

    Controls when and how the system runs automated extraction,
    analysis, categorization, and email-moving tasks.
    """

    enabled: bool = Field(default=False, description="Enable scheduled automated processing")
    interval_hours: int = Field(
        default=24,
        ge=1,
        le=168,
        description="Hours between scheduled runs (1-168, i.e. up to one week)",
    )
    run_at: str = Field(
        default="02:00",
        description="Time of day to run scheduled tasks (HH:MM, 24-hour format)",
    )
    tasks: list[str] = Field(
        default=["extract", "analyze", "categorize", "move"],
        min_length=1,
        description="Ordered list of tasks to run: extract, analyze, categorize, move",
    )
    auto_categorize: bool = Field(
        default=False,
        description="Automatically apply rules to new emails without review",
    )
    notification_threshold: int = Field(
        default=10,
        ge=1,
        le=10000,
        description="Minimum new uncategorized emails before sending notification",
    )

    @field_validator("run_at")
    @classmethod
    def validate_run_at_format(cls, v: str) -> str:
        """Validate run_at is in HH:MM 24-hour format."""
        if not TIME_FORMAT_RE.match(v):
            raise ValueError(f"run_at must be in HH:MM 24-hour format (00:00-23:59), got '{v}'")
        return v

    @field_validator("tasks")
    @classmethod
    def validate_task_names(cls, v: list[str]) -> list[str]:
        """Validate all task names are recognized."""
        for task in v:
            if task not in VALID_SCHEDULER_TASKS:
                raise ValueError(f"Invalid task '{task}'. Must be one of {VALID_SCHEDULER_TASKS}")
        return v


class MonitoringConfig(BaseModel):
    """
    Configuration for change detection and alerting.

    Controls thresholds for detecting category drift, volume anomalies,
    and new cluster emergence, plus alert delivery channels.
    """

    drift_threshold: float = Field(
        default=0.15,
        gt=0.0,
        le=1.0,
        description="Category match rate drop threshold to trigger drift alert (0.0-1.0)",
    )
    volume_anomaly_stddev: float = Field(
        default=2.0,
        gt=0.0,
        le=10.0,
        description="Standard deviations above mean volume to flag as anomaly",
    )
    alert_channels: list[str] = Field(
        default=["log"],
        min_length=1,
        description="Alert delivery channels: desktop, log, email, console",
    )
    check_interval_hours: int = Field(
        default=6,
        ge=1,
        le=168,
        description="Hours between monitoring checks (1-168)",
    )
    new_cluster_threshold: int = Field(
        default=10,
        ge=1,
        le=10000,
        description="Minimum emails in a new cluster before suggesting a new category",
    )

    @field_validator("alert_channels")
    @classmethod
    def validate_alert_channel_names(cls, v: list[str]) -> list[str]:
        """Validate all alert channel names are recognized."""
        for channel in v:
            if channel not in VALID_ALERT_CHANNELS:
                raise ValueError(
                    f"Invalid alert channel '{channel}'. Must be one of {VALID_ALERT_CHANNELS}"
                )
        return v


class AppConfig(BaseModel):
    """Root application configuration containing all options."""

    # Global options
    output_dir: Path | None = Field(default=None, description="Output directory for all files")
    user_email: EmailStr | None = Field(default=None, description="M365/Hotmail email address")
    verbose: bool = Field(default=False, description="Enable verbose debug logging")

    # Command-specific configurations
    extract: ExtractConfig = Field(default_factory=ExtractConfig)
    analyze: AnalyzeConfig = Field(default_factory=AnalyzeConfig)
    suggest: SuggestConfig = Field(default_factory=SuggestConfig)
    review: ReviewConfig = Field(default_factory=ReviewConfig)
    pipeline: PipelineConfig = Field(default_factory=PipelineConfig)
    learning: LearningConfig = Field(default_factory=LearningConfig)

    # Automation configurations (Phase 6)
    scheduler: SchedulerConfig = Field(default_factory=SchedulerConfig)
    monitoring: MonitoringConfig = Field(default_factory=MonitoringConfig)

    @field_validator("output_dir", mode="before")
    @classmethod
    def convert_output_dir_to_path(cls, v: Any) -> Path | None:
        """Convert string output_dir to Path."""
        if v is None:
            return None
        if isinstance(v, str):
            return Path(v)
        result: Path | None = v
        return result


def _merge_nested_config(
    base: BaseModel,
    override: BaseModel,
) -> dict[str, Any]:
    """
    Merge two nested config models, using model_fields_set to determine
    which override values were explicitly provided.

    Uses Pydantic v2's model_fields_set tracking instead of comparing
    against defaults, so that explicitly setting a value to the default
    in the override correctly takes precedence over the base.

    Args:
        base: Base configuration to start from
        override: Configuration with override values

    Returns:
        Merged dictionary suitable for model construction
    """
    result = {}
    base_dict = base.model_dump()
    override_dict = override.model_dump()

    for key in base_dict:
        # If the key was explicitly set in the override, use override value
        if key in override.model_fields_set:
            result[key] = override_dict[key]
        else:
            result[key] = base_dict[key]

    return result


def merge_configs(base: AppConfig, override: AppConfig) -> AppConfig:
    """
    Merge two AppConfig instances with override taking precedence.

    Uses Pydantic v2's model_fields_set to determine which values in
    the override were explicitly provided. This means an override that
    explicitly sets a value to the default (e.g., verbose=False) will
    correctly take precedence over a base value (e.g., verbose=True).

    Fields not present in override.model_fields_set are preserved from base.

    Args:
        base: Base configuration
        override: Configuration with override values

    Returns:
        New AppConfig with merged values
    """
    # Merge top-level fields
    merged = {}

    # Handle simple fields
    for field in ["output_dir", "user_email", "verbose"]:
        if field in override.model_fields_set:
            override_val = getattr(override, field)
            # For optional fields, None means "not set" even if explicit
            if override_val is not None:
                merged[field] = override_val
            else:
                merged[field] = getattr(base, field)
        else:
            merged[field] = getattr(base, field)

    # Handle nested configs
    for config_name, config_cls in [
        ("extract", ExtractConfig),
        ("analyze", AnalyzeConfig),
        ("suggest", SuggestConfig),
        ("review", ReviewConfig),
        ("pipeline", PipelineConfig),
        ("learning", LearningConfig),
        ("scheduler", SchedulerConfig),
        ("monitoring", MonitoringConfig),
    ]:
        base_nested = getattr(base, config_name)
        override_nested = getattr(override, config_name)

        # Only merge if the nested config was explicitly provided in override
        if config_name in override.model_fields_set:
            merged_nested = _merge_nested_config(
                base_nested,
                override_nested,
            )
            merged[config_name] = config_cls(**merged_nested)
        else:
            merged[config_name] = base_nested

    return AppConfig(**merged)
