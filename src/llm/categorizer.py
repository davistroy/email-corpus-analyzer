"""
LLM-based email categorization.

Uses Claude to generate intelligent category suggestions
based on analysis results.
"""
from pydantic import BaseModel, Field

from src.models.analysis_results import AnalysisResults
from src.models.category import Category
from src.utils.logger import get_logger

from .client import LLMClient

logger = get_logger(__name__)


class CategorySuggestion(BaseModel):
    """A single category suggestion from the LLM."""

    category_name: str = Field(
        ...,
        min_length=2,
        max_length=50,
        description="Concise category name",
    )
    description: str = Field(
        ...,
        max_length=300,
        description="Description of what emails this category contains",
    )
    confidence: float = Field(
        ...,
        ge=0,
        le=1,
        description="Confidence in this category (0-1)",
    )
    reasoning: str = Field(
        ...,
        description="Why this category is suggested",
    )
    matching_patterns: list[str] = Field(
        default_factory=list,
        description="Patterns that match this category (senders, subjects, etc.)",
    )
    suggested_action: str = Field(
        default="keep",
        description="Suggested action: keep, archive, review, delete",
    )
    estimated_count: int = Field(
        default=0,
        description="Estimated number of emails in this category",
    )


class CategorySuggestions(BaseModel):
    """Complete category suggestions from LLM analysis."""

    categories: list[CategorySuggestion] = Field(
        ...,
        description="Suggested categories",
    )
    uncategorized_percentage: float = Field(
        default=0,
        description="Estimated percentage of emails that don't fit categories",
    )
    recommendations: str = Field(
        default="",
        description="Overall recommendations for inbox organization",
    )


class LLMCategorizer:
    """
    Use Claude for intelligent category suggestions.

    Analyzes complete analysis results to generate
    meaningful, actionable category suggestions.
    """

    SYSTEM_PROMPT = """You are an expert email organization consultant.
Analyze email patterns and suggest practical categories for inbox organization.

Goals:
1. Create categories that are actionable (user knows what to do with emails)
2. Minimize overlap between categories
3. Cover the majority of emails (aim for <10% uncategorized)
4. Consider both content and sender-based categories
5. Suggest practical actions for each category

Category naming guidelines:
- Use clear, descriptive names (2-5 words)
- Focus on email purpose: notifications, receipts, newsletters, etc.
- Consider temporal patterns: daily digests, weekly reports, etc.
- Group by action needed: requires response, FYI only, archive immediately

Output 5-15 categories that cover the inbox effectively."""

    def __init__(self, client: LLMClient | None = None):
        """
        Initialize categorizer.

        Args:
            client: LLM client to use. Creates default if None.
        """
        self.client = client or LLMClient()

    async def suggest_categories(
        self,
        analysis_results: AnalysisResults,
        existing_categories: list[Category] | None = None,
        max_categories: int = 15,
    ) -> CategorySuggestions:
        """
        Generate category suggestions from analysis results.

        Args:
            analysis_results: Complete analysis from analyzers.
            existing_categories: Previously defined categories to consider.
            max_categories: Maximum number of categories to suggest.

        Returns:
            CategorySuggestions with recommended categories.
        """
        # Build analysis summary
        summary = self._build_analysis_summary(analysis_results)

        # Add existing categories context
        existing_context = ""
        if existing_categories:
            existing_context = "\n\n## Existing Categories:\n"
            for cat in existing_categories:
                existing_context += f"- {cat.category_name}: {cat.description}\n"

        prompt = f"""Analyze this email inbox and suggest organizational categories.

## Inbox Analysis Summary:
{summary}
{existing_context}

Based on this analysis, suggest {max_categories} or fewer categories that would effectively organize this inbox.
Consider patterns in senders, content, timing, and required actions."""

        try:
            result = await self.client.generate_structured(
                prompt=prompt,
                response_model=CategorySuggestions,
                system=self.SYSTEM_PROMPT,
            )
            return result

        except Exception as e:
            logger.warning(f"LLM categorization failed, using fallback: {e}")
            return self._fallback_suggestions(analysis_results)

    def _build_analysis_summary(self, results: AnalysisResults) -> str:
        """Build a text summary of analysis results."""
        lines = []

        # Volume stats
        vol = results.volume_stats
        lines.append(f"Total emails: {vol.total_emails}")
        lines.append(f"Unique senders: {vol.unique_senders}")
        lines.append(f"Unique domains: {vol.unique_domains}")
        lines.append(f"Emails with attachments: {vol.emails_with_attachments}")
        lines.append("")

        # Top senders
        lines.append("### Top Senders:")
        for sender in results.sender_analysis.top_senders[:10]:
            lines.append(f"- {sender.email} ({sender.frequency_count} emails, {sender.type.value})")
        lines.append("")

        # Top domains
        lines.append("### Top Domains:")
        for domain, count in results.sender_analysis.top_domains[:10]:
            lines.append(f"- {domain}: {count} emails")
        lines.append("")

        # Content clusters
        lines.append("### Content Clusters (by semantic similarity):")
        for cluster in results.content_clusters[:10]:
            sample_subjects = [s.subject[:50] for s in cluster.representative_samples[:3]]
            lines.append(f"- Cluster {cluster.cluster_id}: {cluster.size} emails ({cluster.percentage:.1f}%)")
            lines.append(f"  Sample subjects: {', '.join(sample_subjects)}")
        lines.append("")

        # Subject patterns
        lines.append("### Subject Patterns:")
        patterns = results.subject_patterns
        if patterns.common_prefixes:
            lines.append(f"- Common prefixes: {patterns.common_prefixes[:5]}")
        if patterns.keywords:
            lines.append(f"- Keywords: {patterns.keywords[:10]}")
        lines.append("")

        # Temporal patterns
        lines.append("### Temporal Patterns:")
        temp = results.temporal_patterns
        lines.append(f"- Daily senders: {len(temp.frequency_distribution.get('daily', []))}")
        lines.append(f"- Weekly senders: {len(temp.frequency_distribution.get('weekly', []))}")
        lines.append(f"- One-time senders: {len(temp.frequency_distribution.get('one_time', []))}")

        return "\n".join(lines)

    def _fallback_suggestions(self, results: AnalysisResults) -> CategorySuggestions:
        """Generate fallback suggestions without LLM."""
        categories = []

        # Create categories from top senders
        for sender in results.sender_analysis.top_senders[:5]:
            if sender.frequency_count >= 20:
                domain = sender.domain.replace(".com", "").title()
                categories.append(CategorySuggestion(
                    category_name=f"{domain} Emails",
                    description=f"Emails from {sender.email}",
                    confidence=0.7,
                    reasoning=f"High-volume sender with {sender.frequency_count} emails",
                    matching_patterns=[sender.email, sender.domain],
                    suggested_action="review",
                    estimated_count=sender.frequency_count,
                ))

        # Create categories from clusters
        for cluster in results.content_clusters[:5]:
            if cluster.percentage >= 5:
                domain = cluster.common_domains[0][0] if cluster.common_domains else "Mixed"
                categories.append(CategorySuggestion(
                    category_name=f"{domain.replace('.com', '').title()} Content",
                    description=f"Content cluster with {cluster.size} emails",
                    confidence=0.5,
                    reasoning=f"Semantic cluster covering {cluster.percentage:.1f}% of inbox",
                    matching_patterns=[d[0] for d in cluster.common_domains[:3]],
                    suggested_action="review",
                    estimated_count=cluster.size,
                ))

        return CategorySuggestions(
            categories=categories,
            uncategorized_percentage=30.0,  # Conservative estimate
            recommendations="Consider reviewing clusters for more specific categorization.",
        )

    async def refine_category(
        self,
        category: Category,
        sample_emails: list[dict],
    ) -> CategorySuggestion:
        """
        Refine an existing category with more context.

        Args:
            category: Existing category to refine.
            sample_emails: Sample emails from this category.

        Returns:
            Refined CategorySuggestion.
        """
        samples_text = "\n".join([
            f"- Subject: {e.get('subject', '')}\n  From: {e.get('sender_email', '')}"
            for e in sample_emails[:5]
        ])

        prompt = f"""Refine this email category based on sample emails.

## Current Category:
- Name: {category.category_name}
- Description: {category.description}
- Email count: {category.email_count}

## Sample Emails:
{samples_text}

Suggest a more accurate name and description based on the actual email content."""

        return await self.client.generate_structured(
            prompt=prompt,
            response_model=CategorySuggestion,
            system="You are refining an email category. Be specific and actionable.",
        )
