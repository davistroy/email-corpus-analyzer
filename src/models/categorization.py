"""
Categorization data models for email-by-email classification (Phase 4, Item 4.1).

Defines the models that track how individual emails map to categories:
- CategoryAssignment: A single category assignment with confidence and source
- EmailCategorization: An email's full categorization (primary + secondaries)
- CategorizationReport: Summary report of a categorization run with metrics
"""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field, model_validator

# =============================================================================
# Models
# =============================================================================


class CategoryAssignment(BaseModel):
    """
    A single category assignment for an email.

    Represents the assignment of one category with a confidence score
    and the source that produced the assignment (rule ID or 'manual').
    """

    category_name: str = Field(..., min_length=1, description="Name of the assigned category")
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence score for this assignment (0-1)"
    )
    source: str | None = Field(
        default=None,
        description="Source of this assignment: rule_id string or 'manual'",
    )


class EmailCategorization(BaseModel):
    """
    Full categorization result for a single email.

    Tracks the primary category (highest confidence match), any secondary
    categories, which rules matched, and when the categorization occurred.
    """

    email_id: str = Field(..., min_length=1, description="Unique email message ID")
    primary_category: CategoryAssignment = Field(
        ..., description="Primary category assignment (highest confidence)"
    )
    secondary_categories: list[CategoryAssignment] = Field(
        default_factory=list,
        description="Additional category assignments below primary confidence",
    )
    matched_rules: list[str] = Field(
        default_factory=list,
        description="List of rule IDs that matched this email",
    )
    categorized_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when this email was categorized",
    )

    @property
    def is_uncategorized(self) -> bool:
        """Return True if this email was not matched by any rule."""
        return (
            self.primary_category.category_name == "Uncategorized"
            and self.primary_category.confidence == 0.0
        )

    @property
    def has_multiple_categories(self) -> bool:
        """Return True if this email has secondary category assignments."""
        return len(self.secondary_categories) > 0

    @property
    def all_categories(self) -> list[CategoryAssignment]:
        """Return primary category followed by all secondary categories."""
        return [self.primary_category] + list(self.secondary_categories)

    @classmethod
    def uncategorized(cls, email_id: str) -> EmailCategorization:
        """Create an EmailCategorization for an email that matched no rules."""
        return cls(
            email_id=email_id,
            primary_category=CategoryAssignment(
                category_name="Uncategorized",
                confidence=0.0,
                source=None,
            ),
        )


class CategorizationReport(BaseModel):
    """
    Summary report for a categorization run across a corpus.

    Contains aggregate metrics, per-category breakdowns, and the full
    list of individual email categorizations. Supports JSON serialization
    for persistence.
    """

    total_emails: int = Field(..., ge=0, description="Total number of emails in the corpus")
    categorized_count: int = Field(
        ..., ge=0, description="Number of emails assigned to at least one category"
    )
    uncategorized_count: int = Field(
        ..., ge=0, description="Number of emails with no category match"
    )
    coverage_percentage: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Percentage of emails categorized (0-100)",
    )
    categories_used: dict[str, int] = Field(..., description="Map of category name to email count")
    categorizations: list[EmailCategorization] = Field(
        ..., description="Individual email categorization results"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when this report was generated",
    )
    rule_set_version: str | None = Field(
        default=None,
        description="Version of the RuleSet used for this categorization run",
    )

    @model_validator(mode="after")
    def _validate_counts_sum(self) -> CategorizationReport:
        """Ensure categorized + uncategorized counts equal total."""
        if self.categorized_count + self.uncategorized_count != self.total_emails:
            raise ValueError(
                f"categorized_count ({self.categorized_count}) + "
                f"uncategorized_count ({self.uncategorized_count}) "
                f"must equal total_emails ({self.total_emails})"
            )
        return self

    @property
    def category_count(self) -> int:
        """Return the number of unique categories used."""
        return len(self.categories_used)

    @property
    def multi_category_count(self) -> int:
        """Return count of emails with multiple category assignments."""
        return sum(1 for c in self.categorizations if c.has_multiple_categories)
