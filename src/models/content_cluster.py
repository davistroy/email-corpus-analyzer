"""
ContentCluster data model.

Per data-model.md lines 280-292.
"""

from pydantic import BaseModel, Field


class RepresentativeSample(BaseModel):
    """Representative email sample from a cluster."""

    subject: str
    sender: str
    body_preview: str = Field(..., max_length=200)


class ContentCluster(BaseModel):
    """Thematic grouping from semantic analysis."""

    cluster_id: int = Field(..., ge=0)
    size: int = Field(..., ge=1)
    percentage: float = Field(..., ge=0, le=100)
    representative_samples: list[RepresentativeSample] = Field(..., max_length=5)
    common_domains: list[tuple[str, int]] = Field(default_factory=list)
    email_ids: list[str] = Field(default_factory=list)
