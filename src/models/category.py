"""
Category data model.

Per data-model.md lines 320-355.
"""
from enum import Enum

from pydantic import BaseModel, Field


class CategorySource(str, Enum):
    """Source type for category generation."""

    CONTENT_CLUSTER = "content_cluster"
    SENDER = "sender"
    TEMPLATE = "template"
    CUSTOM = "custom"


class Category(BaseModel):
    """Suggested or approved email classification."""

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
