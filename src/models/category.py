"""
Category data model.

Per data-model.md lines 320-355.
Per Phase 4 Track 4A.1: Added hierarchical category support with parent_category_id,
level, and subcategories fields for tree-based category organization.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class CategorySource(str, Enum):
    """Source type for category generation."""

    CONTENT_CLUSTER = "content_cluster"
    SENDER = "sender"
    TEMPLATE = "template"
    CUSTOM = "custom"


class Category(BaseModel):
    """
    Suggested or approved email classification.

    Supports hierarchical organization with parent-child relationships.
    Level 0 categories are top-level, level 1+ are subcategories.
    """

    category_id: str = Field(..., min_length=1)
    category_name: str = Field(..., min_length=1)
    description: str
    confidence: float = Field(..., ge=0, le=1)
    email_count: int | None = Field(None, ge=0)
    percentage: float | None = Field(None, ge=0, le=100)
    source: CategorySource
    source_id: str | None = None
    user_modified: bool = False
    distinguishing_features: list[str] = Field(default_factory=list)
    example_email_ids: list[str] = Field(default_factory=list, max_length=10)
    name_quality_score: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Quality score for the category name (0-1, higher is better)",
    )
    needs_name_review: bool = Field(
        default=False,
        description="Flag indicating the category name needs human review (quality < 0.4)",
    )
    confidence_breakdown: dict[str, float] | None = Field(
        default=None,
        description="Component scores that make up the confidence score (cohesion, volume, source, percentage, name_quality, distinctiveness)",
    )

    # Hierarchical category fields (Task 4A.1)
    parent_category_id: str | None = Field(
        default=None, description="ID of parent category if this is a subcategory"
    )
    level: int = Field(
        default=0,
        ge=0,
        description="Hierarchy level (0=top-level, 1=subcategory, 2=sub-subcategory, etc.)",
    )
    subcategories: list[Category] = Field(
        default_factory=list, description="Child categories for tree view display"
    )

    @property
    def is_top_level(self) -> bool:
        """Return True if this is a top-level category (level 0)."""
        return self.level == 0

    @property
    def has_children(self) -> bool:
        """Return True if this category has subcategories."""
        return len(self.subcategories) > 0

    @property
    def children_count(self) -> int:
        """Return the number of direct subcategories."""
        return len(self.subcategories)
