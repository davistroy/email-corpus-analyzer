"""
LLM-based cluster naming.

Uses Claude to generate meaningful, descriptive names for
email clusters based on representative samples.
"""
from pydantic import BaseModel, Field

from src.models.content_cluster import RepresentativeSample
from src.utils.logger import get_logger

from .client import LLMClient

logger = get_logger(__name__)


class ClusterName(BaseModel):
    """Structured output for cluster naming."""

    name: str = Field(
        ...,
        min_length=2,
        max_length=50,
        description="Concise category name (2-5 words)",
    )
    description: str = Field(
        ...,
        max_length=200,
        description="Brief description of what emails this contains",
    )
    confidence: float = Field(
        ...,
        ge=0,
        le=1,
        description="Confidence in this categorization (0-1)",
    )
    reasoning: str = Field(
        ...,
        description="Brief explanation of why this name fits the cluster",
    )
    suggested_action: str = Field(
        default="keep",
        description="Suggested action: keep, archive, review, delete",
    )


class ClusterNamer:
    """
    Use LLM to generate meaningful cluster names.

    Analyzes representative samples and common domains
    to produce descriptive, actionable category names.
    """

    SYSTEM_PROMPT = """You are an expert at analyzing and categorizing emails.
Given representative email samples from a cluster, generate a clear, descriptive category name.

Guidelines:
- Names should be 2-5 words, descriptive but concise
- Focus on the PURPOSE or TYPE of emails, not specific senders
- Consider: topic, sender type, action required, or content category
- Avoid generic names like "Miscellaneous" unless truly appropriate
- Suggest practical actions: keep for reference, archive, review periodically, can delete

Examples of good names:
- "Shopping Order Updates"
- "Bank Account Alerts"
- "Team Meeting Invites"
- "Newsletter Subscriptions"
- "Password Reset Requests"
- "Travel Booking Confirmations"
"""

    def __init__(self, client: LLMClient | None = None):
        """
        Initialize cluster namer.

        Args:
            client: LLM client to use. Creates default if None.
        """
        self.client = client or LLMClient()

    async def name_cluster(
        self,
        representative_samples: list[RepresentativeSample],
        common_domains: list[tuple[str, int]],
        cluster_size: int | None = None,
        cluster_percentage: float | None = None,
    ) -> ClusterName:
        """
        Generate a meaningful name for a cluster.

        Args:
            representative_samples: Sample emails from the cluster.
            common_domains: Most common sender domains with counts.
            cluster_size: Number of emails in cluster.
            cluster_percentage: Percentage of total corpus.

        Returns:
            ClusterName with name, description, and confidence.
        """
        # Build context from samples
        samples_text = self._format_samples(representative_samples[:5])
        domains_text = self._format_domains(common_domains[:5])

        # Build size context
        size_context = ""
        if cluster_size:
            size_context = f"\n\nCluster contains {cluster_size} emails"
            if cluster_percentage:
                size_context += f" ({cluster_percentage:.1f}% of inbox)"

        prompt = f"""Analyze these representative emails from a cluster and suggest a category name.

## Representative Emails:
{samples_text}

## Common Sender Domains:
{domains_text}
{size_context}

Generate a concise, meaningful category name that captures what these emails have in common."""

        try:
            result = await self.client.generate_structured(
                prompt=prompt,
                response_model=ClusterName,
                system=self.SYSTEM_PROMPT,
            )
            return result

        except Exception as e:
            logger.warning(f"LLM naming failed, using fallback: {e}")
            return self._fallback_name(representative_samples, common_domains)

    def _format_samples(self, samples: list[RepresentativeSample]) -> str:
        """Format samples for prompt."""
        lines = []
        for i, sample in enumerate(samples, 1):
            lines.append(f"{i}. Subject: {sample.subject}")
            lines.append(f"   From: {sample.sender}")
            preview = sample.body_preview[:150].replace("\n", " ")
            lines.append(f"   Preview: {preview}...")
            lines.append("")
        return "\n".join(lines)

    def _format_domains(self, domains: list[tuple[str, int]]) -> str:
        """Format domains for prompt."""
        if not domains:
            return "No common domains identified"
        return ", ".join([f"{d[0]} ({d[1]} emails)" for d in domains])

    def _fallback_name(
        self,
        samples: list[RepresentativeSample],
        domains: list[tuple[str, int]],
    ) -> ClusterName:
        """Generate fallback name without LLM."""
        # Try to use common domain
        if domains:
            domain_name = domains[0][0].replace(".com", "").replace(".", " ").title()
            return ClusterName(
                name=f"{domain_name} Emails",
                description=f"Emails from {domains[0][0]} and related senders",
                confidence=0.5,
                reasoning="Named based on most common sender domain",
                suggested_action="review",
            )

        # Fallback to sample subjects
        if samples:
            words = samples[0].subject.split()[:3]
            name = " ".join(words).title() if words else "Mixed Emails"
            return ClusterName(
                name=name,
                description="Mixed content cluster",
                confidence=0.3,
                reasoning="Named based on first sample subject",
                suggested_action="review",
            )

        return ClusterName(
            name="Uncategorized",
            description="Emails that don't fit other categories",
            confidence=0.2,
            reasoning="No clear pattern identified",
            suggested_action="review",
        )

    async def name_clusters_batch(
        self,
        clusters: list[dict],
    ) -> list[ClusterName]:
        """
        Name multiple clusters.

        Args:
            clusters: List of dicts with 'samples' and 'domains' keys.

        Returns:
            List of ClusterName objects.
        """
        import asyncio

        tasks = [
            self.name_cluster(
                representative_samples=c.get("samples", []),
                common_domains=c.get("domains", []),
                cluster_size=c.get("size"),
                cluster_percentage=c.get("percentage"),
            )
            for c in clusters
        ]

        return await asyncio.gather(*tasks)
