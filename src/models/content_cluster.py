"""
ContentCluster data model.

Per data-model.md lines 280-292.
Updated for LLM-based naming support.
"""

from pydantic import BaseModel, Field


class RepresentativeSample(BaseModel):
    """Representative email sample from a cluster."""

    subject: str
    sender: str
    body_preview: str = Field(..., max_length=200)


class ContentCluster(BaseModel):
    """Thematic grouping from semantic analysis."""

    # Core cluster data
    cluster_id: int = Field(..., ge=0)
    size: int = Field(..., ge=1)
    percentage: float = Field(..., ge=0, le=100)
    representative_samples: list[RepresentativeSample] = Field(..., max_length=5)
    common_domains: list[tuple[str, int]] = Field(default_factory=list)
    email_ids: list[str] = Field(default_factory=list)

    # LLM-generated naming (optional, populated by SemanticAnalyzer with use_llm_naming=True)
    suggested_name: str | None = Field(
        default=None,
        description="LLM-suggested category name for this cluster"
    )
    name_confidence: float | None = Field(
        default=None,
        ge=0,
        le=1,
        description="Confidence in the suggested name (0-1)"
    )
    name_reasoning: str | None = Field(
        default=None,
        description="LLM reasoning for the suggested name"
    )
    suggested_action: str | None = Field(
        default=None,
        description="Suggested action: keep, archive, review, delete"
    )

    model_config = {"extra": "allow"}  # Allow extra fields for future extensibility

    @property
    def display_name(self) -> str:
        """Get display name for the cluster."""
        if self.suggested_name:
            return self.suggested_name
        # Fallback to domain-based name
        if self.common_domains:
            domain = self.common_domains[0][0].replace(".com", "").title()
            return f"{domain} Emails"
        return f"Cluster {self.cluster_id}"
