"""
ContentCluster data model.

Per data-model.md lines 280-292.
Per Phase 2 Track 2A.4: Added silhouette_score and cohesion_score fields.
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
    silhouette_score: float | None = Field(
        default=None,
        ge=-1.0,
        le=1.0,
        description="Average silhouette score for this cluster (-1 to 1)",
    )
    cohesion_score: float | None = Field(
        default=None, ge=0.0, description="Intra-cluster distance (lower is better cohesion)"
    )
