"""
Coverage reporter for categorization analysis (Phase 4, Item 4.4).

Provides:
- CoverageReporter: Analyze categorization coverage across a corpus
- CoverageAnalysis: Detailed coverage metrics, patterns, and recommendations
- UncategorizedPattern: Detected pattern among uncategorized emails
- Recommendation: Suggested action to improve coverage
"""

from __future__ import annotations

import logging
import statistics
from collections import Counter, defaultdict

from pydantic import BaseModel, Field

from src.models.categorization import CategorizationReport
from src.models.corpus import Corpus
from src.models.email import Email

logger = logging.getLogger(__name__)

# Minimum number of uncategorized emails sharing a pattern to report it
_MIN_PATTERN_COUNT = 2

# Maximum example email IDs per pattern
_MAX_EXAMPLE_IDS = 5

# Priority thresholds (fraction of uncategorized emails)
_HIGH_PRIORITY_FRACTION = 0.3
_MEDIUM_PRIORITY_FRACTION = 0.1


# =============================================================================
# Data Models
# =============================================================================


class DistributionStats(BaseModel):
    """Statistical distribution of emails across categories."""

    mean: float = Field(..., description="Mean emails per category")
    median: float = Field(..., description="Median emails per category")
    std: float = Field(..., ge=0.0, description="Standard deviation of emails per category")
    min_count: int = Field(..., ge=0, description="Minimum emails in any category")
    max_count: int = Field(..., ge=0, description="Maximum emails in any category")


class CategoryCoverage(BaseModel):
    """Coverage metrics for a single category."""

    category_name: str = Field(..., min_length=1, description="Name of the category")
    email_count: int = Field(..., ge=0, description="Number of emails in this category")
    percentage: float = Field(
        ..., ge=0.0, le=100.0, description="Percentage of total emails in this category"
    )


class UncategorizedPattern(BaseModel):
    """A detected pattern among uncategorized emails."""

    pattern_type: str = Field(
        ...,
        description="Type of pattern: 'sender_domain', 'sender_email', or 'subject_prefix'",
    )
    value: str = Field(..., description="The pattern value (domain, email, or prefix)")
    count: int = Field(
        ..., ge=1, description="Number of uncategorized emails matching this pattern"
    )
    example_email_ids: list[str] = Field(
        default_factory=list,
        description="Example email IDs exhibiting this pattern",
    )


class Recommendation(BaseModel):
    """A recommendation for improving categorization coverage."""

    recommendation_type: str = Field(
        ..., description="Type of recommendation: 'new_rule', 'extend_rule'"
    )
    description: str = Field(..., description="Human-readable recommendation description")
    pattern: UncategorizedPattern = Field(
        ..., description="The uncategorized pattern this recommendation addresses"
    )
    priority: str = Field(..., description="Priority level: 'high', 'medium', or 'low'")


class CoverageAnalysis(BaseModel):
    """Complete coverage analysis of a categorization run."""

    total_emails: int = Field(..., ge=0, description="Total emails in the corpus")
    categorized_count: int = Field(..., ge=0, description="Number of categorized emails")
    uncategorized_count: int = Field(..., ge=0, description="Number of uncategorized emails")
    coverage_percentage: float = Field(
        ..., ge=0.0, le=100.0, description="Percentage of emails categorized"
    )
    per_category: list[CategoryCoverage] = Field(
        default_factory=list,
        description="Per-category breakdown sorted by email count descending",
    )
    uncategorized_patterns: list[UncategorizedPattern] = Field(
        default_factory=list,
        description="Detected patterns among uncategorized emails",
    )
    distribution: DistributionStats = Field(..., description="Category distribution statistics")
    recommendations: list[Recommendation] = Field(
        default_factory=list,
        description="Recommendations for improving coverage, sorted by priority",
    )


# =============================================================================
# CoverageReporter
# =============================================================================


class CoverageReporter:
    """Analyze categorization coverage and generate recommendations.

    Examines a CategorizationReport against the original Corpus to:
    - Compute overall and per-category coverage
    - Detect patterns among uncategorized emails (common senders, domains, subject prefixes)
    - Calculate category distribution statistics
    - Generate recommendations for new rules to improve coverage
    """

    def analyze_coverage(
        self,
        report: CategorizationReport,
        corpus: Corpus,
    ) -> CoverageAnalysis:
        """Analyze categorization coverage against the corpus.

        Args:
            report: The categorization report containing per-email classifications.
            corpus: The original email corpus with full email metadata.

        Returns:
            CoverageAnalysis with metrics, patterns, and recommendations.
        """
        total = report.total_emails
        categorized = report.categorized_count
        uncategorized = report.uncategorized_count
        coverage_pct = report.coverage_percentage

        # Build email lookup by ID
        email_lookup: dict[str, Email] = {e.id: e for e in corpus.emails}

        # Per-category breakdown
        per_category = self._build_per_category(report.categories_used, total)

        # Distribution stats
        distribution = self._compute_distribution(report.categories_used)

        # Identify uncategorized email IDs
        uncategorized_ids = [c.email_id for c in report.categorizations if c.is_uncategorized]

        # Detect patterns among uncategorized emails
        uncategorized_emails = [
            email_lookup[eid] for eid in uncategorized_ids if eid in email_lookup
        ]
        patterns = self._detect_patterns(uncategorized_emails)

        # Generate recommendations
        recommendations = self._generate_recommendations(patterns, uncategorized)

        return CoverageAnalysis(
            total_emails=total,
            categorized_count=categorized,
            uncategorized_count=uncategorized,
            coverage_percentage=coverage_pct,
            per_category=per_category,
            uncategorized_patterns=patterns,
            distribution=distribution,
            recommendations=recommendations,
        )

    def format_report(self, analysis: CoverageAnalysis) -> str:
        """Generate a formatted text report from a CoverageAnalysis.

        Args:
            analysis: The coverage analysis to format.

        Returns:
            Multi-line formatted string suitable for console output or file export.
        """
        lines: list[str] = []

        # Header
        lines.append("=" * 60)
        lines.append("CATEGORIZATION COVERAGE REPORT")
        lines.append("=" * 60)
        lines.append("")

        # Overall coverage
        lines.append("Overall Coverage")
        lines.append("-" * 40)
        lines.append(f"  Total emails:       {analysis.total_emails}")
        lines.append(f"  Categorized:        {analysis.categorized_count}")
        lines.append(f"  Uncategorized:      {analysis.uncategorized_count}")
        lines.append(f"  Coverage:           {analysis.coverage_percentage:.1f}%")
        lines.append("")

        # Per-category breakdown
        if analysis.per_category:
            lines.append("Category Breakdown")
            lines.append("-" * 40)
            max_name_len = max(len(c.category_name) for c in analysis.per_category)
            for cat in analysis.per_category:
                lines.append(
                    f"  {cat.category_name:<{max_name_len}}  "
                    f"{cat.email_count:>5} emails  ({cat.percentage:.1f}%)"
                )
            lines.append("")

        # Distribution statistics
        lines.append("Distribution Statistics")
        lines.append("-" * 40)
        lines.append(f"  Mean emails/category:   {analysis.distribution.mean:.1f}")
        lines.append(f"  Median emails/category: {analysis.distribution.median:.1f}")
        lines.append(f"  Std deviation:          {analysis.distribution.std:.1f}")
        lines.append(f"  Min category size:      {analysis.distribution.min_count}")
        lines.append(f"  Max category size:      {analysis.distribution.max_count}")
        lines.append("")

        # Uncategorized patterns
        if analysis.uncategorized_patterns:
            lines.append("Uncategorized Patterns")
            lines.append("-" * 40)
            for pattern in analysis.uncategorized_patterns:
                lines.append(f"  [{pattern.pattern_type}] {pattern.value}: {pattern.count} emails")
            lines.append("")

        # Recommendations
        if analysis.recommendations:
            lines.append("Recommendations")
            lines.append("-" * 40)
            for i, rec in enumerate(analysis.recommendations, 1):
                lines.append(f"  {i}. [{rec.priority.upper()}] {rec.description}")
            lines.append("")

        lines.append("=" * 60)
        return "\n".join(lines)

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    def _build_per_category(
        self, categories_used: dict[str, int], total_emails: int
    ) -> list[CategoryCoverage]:
        """Build per-category coverage list sorted by count descending."""
        result = []
        for name, count in categories_used.items():
            pct = (count / total_emails * 100.0) if total_emails > 0 else 0.0
            result.append(
                CategoryCoverage(
                    category_name=name,
                    email_count=count,
                    percentage=pct,
                )
            )
        result.sort(key=lambda c: c.email_count, reverse=True)
        return result

    def _compute_distribution(self, categories_used: dict[str, int]) -> DistributionStats:
        """Compute distribution statistics from category counts."""
        if not categories_used:
            return DistributionStats(mean=0.0, median=0.0, std=0.0, min_count=0, max_count=0)

        counts = list(categories_used.values())
        mean = statistics.mean(counts)
        median = statistics.median(counts)
        std = statistics.pstdev(counts)  # population std (not sample)

        return DistributionStats(
            mean=mean,
            median=median,
            std=std,
            min_count=min(counts),
            max_count=max(counts),
        )

    def _detect_patterns(self, uncategorized_emails: list[Email]) -> list[UncategorizedPattern]:
        """Detect common patterns among uncategorized emails.

        Looks for:
        - Common sender domains
        - Common sender emails (individual senders)
        - Common subject prefixes (bracket-delimited like [ALERT])
        """
        if not uncategorized_emails:
            return []

        patterns: list[UncategorizedPattern] = []

        # --- Sender domain patterns ---
        domain_counter: Counter[str] = Counter()
        domain_emails: dict[str, list[str]] = defaultdict(list)
        for email in uncategorized_emails:
            domain_counter[email.sender_domain] += 1
            domain_emails[email.sender_domain].append(email.id)

        for domain, count in domain_counter.most_common():
            if count >= _MIN_PATTERN_COUNT:
                patterns.append(
                    UncategorizedPattern(
                        pattern_type="sender_domain",
                        value=domain,
                        count=count,
                        example_email_ids=domain_emails[domain][:_MAX_EXAMPLE_IDS],
                    )
                )

        # --- Sender email patterns ---
        sender_counter: Counter[str] = Counter()
        sender_emails: dict[str, list[str]] = defaultdict(list)
        for email in uncategorized_emails:
            sender_counter[email.sender_email] += 1
            sender_emails[email.sender_email].append(email.id)

        for sender, count in sender_counter.most_common():
            if count >= _MIN_PATTERN_COUNT:
                patterns.append(
                    UncategorizedPattern(
                        pattern_type="sender_email",
                        value=sender,
                        count=count,
                        example_email_ids=sender_emails[sender][:_MAX_EXAMPLE_IDS],
                    )
                )

        # --- Subject prefix patterns ---
        prefix_counter: Counter[str] = Counter()
        prefix_emails: dict[str, list[str]] = defaultdict(list)
        for email in uncategorized_emails:
            prefix = self._extract_subject_prefix(email.subject)
            if prefix:
                prefix_counter[prefix] += 1
                prefix_emails[prefix].append(email.id)

        for prefix, count in prefix_counter.most_common():
            if count >= _MIN_PATTERN_COUNT:
                patterns.append(
                    UncategorizedPattern(
                        pattern_type="subject_prefix",
                        value=prefix,
                        count=count,
                        example_email_ids=prefix_emails[prefix][:_MAX_EXAMPLE_IDS],
                    )
                )

        # Sort patterns by count descending
        patterns.sort(key=lambda p: p.count, reverse=True)
        return patterns

    def _extract_subject_prefix(self, subject: str) -> str | None:
        """Extract a bracket-delimited prefix from a subject line.

        Examples:
            "[ALERT] System down" -> "[ALERT]"
            "RE: Hello" -> "RE:"
            "FWD: Check this" -> "FWD:"
            "Normal subject" -> None
        """
        subject = subject.strip()

        # Check for bracket prefix
        if subject.startswith("["):
            end = subject.find("]")
            if end > 0:
                return subject[: end + 1]

        # Check for common prefixes like RE:, FWD:, FW:
        for prefix in ("RE:", "Re:", "FWD:", "Fwd:", "FW:", "Fw:"):
            if subject.startswith(prefix):
                return prefix

        return None

    def _generate_recommendations(
        self,
        patterns: list[UncategorizedPattern],
        uncategorized_count: int,
    ) -> list[Recommendation]:
        """Generate recommendations from detected uncategorized patterns.

        Priority is based on the fraction of uncategorized emails covered:
        - high: >= 30% of uncategorized emails
        - medium: >= 10% of uncategorized emails
        - low: below 10%
        """
        if not patterns or uncategorized_count == 0:
            return []

        recommendations: list[Recommendation] = []

        # Deduplicate: if a sender_email pattern exists and its domain also exists,
        # prefer the more specific one (sender_email) only if it covers most of the
        # domain. We generate recommendations for all patterns and let priority sort.
        for pattern in patterns:
            fraction = pattern.count / uncategorized_count if uncategorized_count > 0 else 0.0

            if fraction >= _HIGH_PRIORITY_FRACTION:
                priority = "high"
            elif fraction >= _MEDIUM_PRIORITY_FRACTION:
                priority = "medium"
            else:
                priority = "low"

            description = self._describe_recommendation(pattern)

            recommendations.append(
                Recommendation(
                    recommendation_type="new_rule",
                    description=description,
                    pattern=pattern,
                    priority=priority,
                )
            )

        # Sort by priority: high > medium > low
        priority_order = {"high": 0, "medium": 1, "low": 2}
        recommendations.sort(key=lambda r: (priority_order.get(r.priority, 99), -r.pattern.count))

        return recommendations

    def _describe_recommendation(self, pattern: UncategorizedPattern) -> str:
        """Generate a human-readable description for a recommendation."""
        if pattern.pattern_type == "sender_domain":
            return (
                f"Create rule for domain '{pattern.value}' ({pattern.count} uncategorized emails)"
            )
        if pattern.pattern_type == "sender_email":
            return (
                f"Create rule for sender '{pattern.value}' ({pattern.count} uncategorized emails)"
            )
        if pattern.pattern_type == "subject_prefix":
            return (
                f"Create rule for subject prefix '{pattern.value}' "
                f"({pattern.count} uncategorized emails)"
            )
        return (
            f"Create rule for {pattern.pattern_type} '{pattern.value}' "
            f"({pattern.count} uncategorized emails)"
        )
