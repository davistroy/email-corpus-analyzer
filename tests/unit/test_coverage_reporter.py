"""
Unit tests for CoverageReporter (Phase 4, Item 4.4).

Tests categorization coverage analysis: overall metrics, per-category breakdown,
uncategorized pattern detection, distribution statistics, recommendations,
and formatted text report generation.

TDD: These tests are written first, implementation follows.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.categorizer.coverage_reporter import (
    CategoryCoverage,
    CoverageAnalysis,
    CoverageReporter,
    DistributionStats,
    Recommendation,
    UncategorizedPattern,
)
from src.models.categorization import (
    CategorizationReport,
    CategoryAssignment,
    EmailCategorization,
)
from src.models.corpus import Corpus, CorpusMetadata
from src.models.email import Email

# =============================================================================
# Helpers
# =============================================================================


def _make_email(
    id: str = "email_001",  # noqa: A002
    sender_email: str = "alice@example.com",
    sender_domain: str = "example.com",
    subject: str = "Weekly Update",
    body_text: str = "Here is the weekly status update.",
    received_date: datetime | None = None,
    **overrides,
) -> Email:
    """Create a test email with sensible defaults."""
    defaults = {
        "id": id,
        "sender_email": sender_email,
        "sender_name": "Alice",
        "sender_domain": sender_domain,
        "recipient_email": "user@test.com",
        "subject": subject,
        "body_text": body_text,
        "received_date": received_date or datetime(2024, 6, 15, 9, 0, 0),
        "has_attachments": False,
    }
    defaults.update(overrides)
    return Email(**defaults)


def _make_corpus(emails: list[Email]) -> Corpus:
    """Create a test corpus from a list of emails."""
    return Corpus(
        extraction_metadata=CorpusMetadata(
            extraction_date=datetime(2024, 6, 15, tzinfo=timezone.utc),
            total_emails=len(emails),
            source="test",
            user_email="user@test.com",
        ),
        emails=emails,
    )


def _make_categorization(
    email_id: str,
    category_name: str = "Newsletters",
    confidence: float = 0.85,
    source: str | None = "rule_001",
) -> EmailCategorization:
    """Create a categorized email."""
    return EmailCategorization(
        email_id=email_id,
        primary_category=CategoryAssignment(
            category_name=category_name,
            confidence=confidence,
            source=source,
        ),
    )


def _make_uncategorized(email_id: str) -> EmailCategorization:
    """Create an uncategorized email."""
    return EmailCategorization.uncategorized(email_id)


def _make_report(
    categorizations: list[EmailCategorization],
    total_emails: int | None = None,
) -> CategorizationReport:
    """Build a CategorizationReport from a list of categorizations."""
    if total_emails is None:
        total_emails = len(categorizations)
    categorized = sum(1 for c in categorizations if not c.is_uncategorized)
    uncategorized = total_emails - categorized

    categories_used: dict[str, int] = {}
    for c in categorizations:
        if not c.is_uncategorized:
            name = c.primary_category.category_name
            categories_used[name] = categories_used.get(name, 0) + 1

    pct = (categorized / total_emails * 100.0) if total_emails > 0 else 0.0
    return CategorizationReport(
        total_emails=total_emails,
        categorized_count=categorized,
        uncategorized_count=uncategorized,
        coverage_percentage=pct,
        categories_used=categories_used,
        categorizations=categorizations,
    )


# =============================================================================
# CoverageAnalysis Model Tests
# =============================================================================


class TestCoverageAnalysisModel:
    """Test the CoverageAnalysis Pydantic model."""

    def test_minimal_construction(self):
        """CoverageAnalysis can be created with all required fields."""
        analysis = CoverageAnalysis(
            total_emails=100,
            categorized_count=80,
            uncategorized_count=20,
            coverage_percentage=80.0,
            per_category=[],
            uncategorized_patterns=[],
            distribution=DistributionStats(
                mean=20.0, median=15.0, std=5.0, min_count=5, max_count=40
            ),
            recommendations=[],
        )
        assert analysis.total_emails == 100
        assert analysis.coverage_percentage == 80.0
        assert analysis.distribution.mean == 20.0

    def test_distribution_stats_fields(self):
        """DistributionStats holds mean, median, std, min, max."""
        stats = DistributionStats(mean=25.0, median=20.0, std=10.0, min_count=3, max_count=50)
        assert stats.mean == 25.0
        assert stats.median == 20.0
        assert stats.std == 10.0
        assert stats.min_count == 3
        assert stats.max_count == 50

    def test_category_coverage_fields(self):
        """CategoryCoverage holds name, email count, and percentage."""
        cc = CategoryCoverage(
            category_name="Newsletters",
            email_count=50,
            percentage=25.0,
        )
        assert cc.category_name == "Newsletters"
        assert cc.email_count == 50
        assert cc.percentage == 25.0

    def test_uncategorized_pattern_fields(self):
        """UncategorizedPattern holds pattern type, value, count, and email IDs."""
        pattern = UncategorizedPattern(
            pattern_type="sender_domain",
            value="marketing.com",
            count=15,
            example_email_ids=["e1", "e2"],
        )
        assert pattern.pattern_type == "sender_domain"
        assert pattern.value == "marketing.com"
        assert pattern.count == 15
        assert len(pattern.example_email_ids) == 2

    def test_recommendation_fields(self):
        """Recommendation holds type, description, and supporting data."""
        rec = Recommendation(
            recommendation_type="new_rule",
            description="Create rule for marketing.com domain",
            pattern=UncategorizedPattern(
                pattern_type="sender_domain",
                value="marketing.com",
                count=15,
                example_email_ids=["e1"],
            ),
            priority="high",
        )
        assert rec.recommendation_type == "new_rule"
        assert rec.priority == "high"
        assert rec.pattern.value == "marketing.com"

    def test_json_round_trip(self):
        """CoverageAnalysis serializes to JSON and deserializes cleanly."""
        analysis = CoverageAnalysis(
            total_emails=50,
            categorized_count=40,
            uncategorized_count=10,
            coverage_percentage=80.0,
            per_category=[
                CategoryCoverage(category_name="News", email_count=25, percentage=50.0),
            ],
            uncategorized_patterns=[],
            distribution=DistributionStats(
                mean=25.0, median=25.0, std=0.0, min_count=25, max_count=25
            ),
            recommendations=[],
        )
        json_str = analysis.model_dump_json()
        restored = CoverageAnalysis.model_validate_json(json_str)
        assert restored.total_emails == 50
        assert len(restored.per_category) == 1
        assert restored.per_category[0].category_name == "News"


# =============================================================================
# CoverageReporter.analyze_coverage Tests
# =============================================================================


class TestAnalyzeCoverage:
    """Test CoverageReporter.analyze_coverage()."""

    def setup_method(self):
        self.reporter = CoverageReporter()

    def test_empty_corpus(self):
        """Empty corpus produces zero coverage with no patterns."""
        corpus = _make_corpus([])
        report = _make_report([], total_emails=0)
        analysis = self.reporter.analyze_coverage(report, corpus)

        assert analysis.total_emails == 0
        assert analysis.categorized_count == 0
        assert analysis.uncategorized_count == 0
        assert analysis.coverage_percentage == 0.0
        assert analysis.per_category == []
        assert analysis.uncategorized_patterns == []
        assert analysis.recommendations == []

    def test_full_coverage(self):
        """100% coverage when every email is categorized."""
        emails = [
            _make_email(id=f"e{i}", sender_email=f"s{i}@a.com", sender_domain="a.com")
            for i in range(5)
        ]
        corpus = _make_corpus(emails)
        cats = [_make_categorization(f"e{i}", "News") for i in range(5)]
        report = _make_report(cats)

        analysis = self.reporter.analyze_coverage(report, corpus)

        assert analysis.coverage_percentage == 100.0
        assert analysis.uncategorized_count == 0
        assert analysis.uncategorized_patterns == []

    def test_partial_coverage(self):
        """Partial coverage computes correct percentages."""
        emails = [
            _make_email(id=f"e{i}", sender_email=f"s{i}@a.com", sender_domain="a.com")
            for i in range(10)
        ]
        corpus = _make_corpus(emails)
        cats = [_make_categorization(f"e{i}", "News") for i in range(7)]
        cats += [_make_uncategorized(f"e{i}") for i in range(7, 10)]
        report = _make_report(cats)

        analysis = self.reporter.analyze_coverage(report, corpus)

        assert analysis.coverage_percentage == 70.0
        assert analysis.categorized_count == 7
        assert analysis.uncategorized_count == 3

    def test_per_category_breakdown(self):
        """Per-category breakdown shows correct email counts and percentages."""
        emails = [
            _make_email(id=f"e{i}", sender_email=f"s{i}@a.com", sender_domain="a.com")
            for i in range(10)
        ]
        corpus = _make_corpus(emails)
        cats = (
            [_make_categorization(f"e{i}", "News") for i in range(4)]
            + [_make_categorization(f"e{i}", "Promotions") for i in range(4, 7)]
            + [_make_uncategorized(f"e{i}") for i in range(7, 10)]
        )
        report = _make_report(cats)

        analysis = self.reporter.analyze_coverage(report, corpus)

        cat_map = {c.category_name: c for c in analysis.per_category}
        assert "News" in cat_map
        assert "Promotions" in cat_map
        assert cat_map["News"].email_count == 4
        assert cat_map["News"].percentage == 40.0
        assert cat_map["Promotions"].email_count == 3
        assert cat_map["Promotions"].percentage == 30.0

    def test_distribution_stats(self):
        """Distribution statistics compute correctly for multi-category data."""
        emails = [
            _make_email(id=f"e{i}", sender_email=f"s{i}@a.com", sender_domain="a.com")
            for i in range(10)
        ]
        corpus = _make_corpus(emails)
        # Category A: 6 emails, Category B: 2 emails, Category C: 2 emails
        cats = (
            [_make_categorization(f"e{i}", "A") for i in range(6)]
            + [_make_categorization(f"e{i}", "B") for i in range(6, 8)]
            + [_make_categorization(f"e{i}", "C") for i in range(8, 10)]
        )
        report = _make_report(cats)

        analysis = self.reporter.analyze_coverage(report, corpus)

        # Counts: [6, 2, 2] -> mean ~3.33, median 2, std ~1.89, min 2, max 6
        assert analysis.distribution.min_count == 2
        assert analysis.distribution.max_count == 6
        assert analysis.distribution.median == 2.0
        assert 3.0 < analysis.distribution.mean < 4.0  # ~3.33

    def test_single_category_distribution(self):
        """Distribution with one category has std=0."""
        emails = [_make_email(id="e0", sender_email="s@a.com", sender_domain="a.com")]
        corpus = _make_corpus(emails)
        cats = [_make_categorization("e0", "Only")]
        report = _make_report(cats)

        analysis = self.reporter.analyze_coverage(report, corpus)

        assert analysis.distribution.std == 0.0
        assert analysis.distribution.mean == 1.0
        assert analysis.distribution.median == 1.0

    def test_no_categories_distribution(self):
        """Distribution with zero categories returns zero stats."""
        emails = [_make_email(id="e0", sender_email="s@a.com", sender_domain="a.com")]
        corpus = _make_corpus(emails)
        cats = [_make_uncategorized("e0")]
        report = _make_report(cats)

        analysis = self.reporter.analyze_coverage(report, corpus)

        assert analysis.distribution.mean == 0.0
        assert analysis.distribution.median == 0.0
        assert analysis.distribution.std == 0.0
        assert analysis.distribution.min_count == 0
        assert analysis.distribution.max_count == 0


# =============================================================================
# Uncategorized Pattern Detection Tests
# =============================================================================


class TestUncategorizedPatterns:
    """Test detection of patterns among uncategorized emails."""

    def setup_method(self):
        self.reporter = CoverageReporter()

    def test_detects_common_sender_domain(self):
        """Frequent sender domain among uncategorized emails is detected."""
        emails = [
            _make_email(
                id=f"e{i}",
                sender_email=f"promo{i}@marketing.com",
                sender_domain="marketing.com",
                subject=f"Sale {i}",
            )
            for i in range(5)
        ]
        corpus = _make_corpus(emails)
        cats = [_make_uncategorized(f"e{i}") for i in range(5)]
        report = _make_report(cats)

        analysis = self.reporter.analyze_coverage(report, corpus)

        domain_patterns = [
            p for p in analysis.uncategorized_patterns if p.pattern_type == "sender_domain"
        ]
        assert len(domain_patterns) >= 1
        marketing = [p for p in domain_patterns if p.value == "marketing.com"]
        assert len(marketing) == 1
        assert marketing[0].count == 5

    def test_detects_common_sender_email(self):
        """Frequent individual sender among uncategorized emails is detected."""
        emails = [
            _make_email(
                id=f"e{i}",
                sender_email="noreply@service.com",
                sender_domain="service.com",
                subject=f"Notification {i}",
            )
            for i in range(4)
        ]
        corpus = _make_corpus(emails)
        cats = [_make_uncategorized(f"e{i}") for i in range(4)]
        report = _make_report(cats)

        analysis = self.reporter.analyze_coverage(report, corpus)

        sender_patterns = [
            p for p in analysis.uncategorized_patterns if p.pattern_type == "sender_email"
        ]
        assert any(p.value == "noreply@service.com" and p.count == 4 for p in sender_patterns)

    def test_detects_common_subject_prefix(self):
        """Frequent subject prefix among uncategorized emails is detected."""
        emails = [
            _make_email(
                id=f"e{i}",
                sender_email=f"user{i}@various.com",
                sender_domain="various.com",
                subject=f"[ALERT] System event {i}",
            )
            for i in range(5)
        ]
        corpus = _make_corpus(emails)
        cats = [_make_uncategorized(f"e{i}") for i in range(5)]
        report = _make_report(cats)

        analysis = self.reporter.analyze_coverage(report, corpus)

        subject_patterns = [
            p for p in analysis.uncategorized_patterns if p.pattern_type == "subject_prefix"
        ]
        assert any("[ALERT]" in p.value for p in subject_patterns)

    def test_no_patterns_below_threshold(self):
        """Patterns below the minimum count threshold are not reported."""
        # Single email from a unique sender -- should not appear as a pattern
        emails = [
            _make_email(id="e0", sender_email="rare@unique.com", sender_domain="unique.com"),
        ]
        corpus = _make_corpus(emails)
        cats = [_make_uncategorized("e0")]
        report = _make_report(cats)

        analysis = self.reporter.analyze_coverage(report, corpus)

        # With only 1 email, no patterns should meet the threshold
        assert len(analysis.uncategorized_patterns) == 0

    def test_mixed_categorized_and_uncategorized(self):
        """Patterns are detected only among uncategorized emails, not categorized ones."""
        emails = [
            _make_email(
                id=f"cat{i}",
                sender_email="known@company.com",
                sender_domain="company.com",
                subject=f"Known {i}",
            )
            for i in range(5)
        ] + [
            _make_email(
                id=f"uncat{i}",
                sender_email="unknown@mystery.com",
                sender_domain="mystery.com",
                subject=f"Mystery {i}",
            )
            for i in range(3)
        ]
        corpus = _make_corpus(emails)
        cats = [_make_categorization(f"cat{i}", "Known") for i in range(5)] + [
            _make_uncategorized(f"uncat{i}") for i in range(3)
        ]
        report = _make_report(cats)

        analysis = self.reporter.analyze_coverage(report, corpus)

        # company.com should NOT appear (those emails are categorized)
        domain_vals = [
            p.value for p in analysis.uncategorized_patterns if p.pattern_type == "sender_domain"
        ]
        assert "company.com" not in domain_vals
        # mystery.com should appear
        assert "mystery.com" in domain_vals

    def test_pattern_includes_example_email_ids(self):
        """Patterns include example email IDs for reference."""
        emails = [
            _make_email(
                id=f"e{i}",
                sender_email="bot@alerts.io",
                sender_domain="alerts.io",
                subject=f"Alert {i}",
            )
            for i in range(4)
        ]
        corpus = _make_corpus(emails)
        cats = [_make_uncategorized(f"e{i}") for i in range(4)]
        report = _make_report(cats)

        analysis = self.reporter.analyze_coverage(report, corpus)

        for pattern in analysis.uncategorized_patterns:
            if pattern.value == "bot@alerts.io" or pattern.value == "alerts.io":
                assert len(pattern.example_email_ids) > 0
                assert all(eid.startswith("e") for eid in pattern.example_email_ids)


# =============================================================================
# Recommendation Tests
# =============================================================================


class TestRecommendations:
    """Test recommendation generation for uncategorized patterns."""

    def setup_method(self):
        self.reporter = CoverageReporter()

    def test_recommends_rule_for_frequent_domain(self):
        """Frequent uncategorized domain generates a 'new_rule' recommendation."""
        emails = [
            _make_email(
                id=f"e{i}",
                sender_email=f"news{i}@newsletter.com",
                sender_domain="newsletter.com",
                subject=f"Newsletter {i}",
            )
            for i in range(5)
        ]
        corpus = _make_corpus(emails)
        cats = [_make_uncategorized(f"e{i}") for i in range(5)]
        report = _make_report(cats)

        analysis = self.reporter.analyze_coverage(report, corpus)

        assert len(analysis.recommendations) >= 1
        rule_recs = [r for r in analysis.recommendations if r.recommendation_type == "new_rule"]
        assert len(rule_recs) >= 1
        assert any("newsletter.com" in r.description for r in rule_recs)

    def test_recommends_rule_for_frequent_sender(self):
        """Frequent uncategorized sender generates a recommendation."""
        emails = [
            _make_email(
                id=f"e{i}",
                sender_email="alerts@system.net",
                sender_domain="system.net",
                subject=f"System Alert {i}",
            )
            for i in range(5)
        ]
        corpus = _make_corpus(emails)
        cats = [_make_uncategorized(f"e{i}") for i in range(5)]
        report = _make_report(cats)

        analysis = self.reporter.analyze_coverage(report, corpus)

        descs = " ".join(r.description for r in analysis.recommendations)
        assert "alerts@system.net" in descs or "system.net" in descs

    def test_high_priority_for_large_patterns(self):
        """Patterns covering many uncategorized emails get high priority."""
        emails = [
            _make_email(
                id=f"e{i}",
                sender_email=f"s{i}@bigcorp.com",
                sender_domain="bigcorp.com",
                subject=f"Corporate {i}",
            )
            for i in range(10)
        ]
        corpus = _make_corpus(emails)
        cats = [_make_uncategorized(f"e{i}") for i in range(10)]
        report = _make_report(cats)

        analysis = self.reporter.analyze_coverage(report, corpus)

        high_recs = [r for r in analysis.recommendations if r.priority == "high"]
        assert len(high_recs) >= 1

    def test_no_recommendations_at_full_coverage(self):
        """No recommendations when coverage is 100%."""
        emails = [_make_email(id="e0", sender_email="s@a.com", sender_domain="a.com")]
        corpus = _make_corpus(emails)
        cats = [_make_categorization("e0", "Done")]
        report = _make_report(cats)

        analysis = self.reporter.analyze_coverage(report, corpus)

        assert analysis.recommendations == []

    def test_recommendations_sorted_by_priority(self):
        """Recommendations are returned sorted: high before medium before low."""
        # Build a corpus with two distinct uncategorized patterns of different sizes
        emails = [
            _make_email(
                id=f"big{i}",
                sender_email=f"x{i}@bigdomain.com",
                sender_domain="bigdomain.com",
                subject=f"Big {i}",
            )
            for i in range(8)
        ] + [
            _make_email(
                id=f"small{i}",
                sender_email=f"y{i}@smalldomain.com",
                sender_domain="smalldomain.com",
                subject=f"Small {i}",
            )
            for i in range(3)
        ]
        corpus = _make_corpus(emails)
        cats = [_make_uncategorized(f"big{i}") for i in range(8)] + [
            _make_uncategorized(f"small{i}") for i in range(3)
        ]
        report = _make_report(cats)

        analysis = self.reporter.analyze_coverage(report, corpus)

        if len(analysis.recommendations) >= 2:
            priority_order = {"high": 0, "medium": 1, "low": 2}
            priorities = [priority_order.get(r.priority, 99) for r in analysis.recommendations]
            assert priorities == sorted(priorities), "Recommendations should be sorted by priority"


# =============================================================================
# Formatted Report Tests
# =============================================================================


class TestFormatReport:
    """Test formatted text report generation."""

    def setup_method(self):
        self.reporter = CoverageReporter()

    def test_format_report_returns_string(self):
        """format_report returns a non-empty string."""
        emails = [
            _make_email(id=f"e{i}", sender_email=f"s{i}@a.com", sender_domain="a.com")
            for i in range(5)
        ]
        corpus = _make_corpus(emails)
        cats = [_make_categorization(f"e{i}", "Test") for i in range(3)] + [
            _make_uncategorized(f"e{i}") for i in range(3, 5)
        ]
        report = _make_report(cats)
        analysis = self.reporter.analyze_coverage(report, corpus)

        text = self.reporter.format_report(analysis)

        assert isinstance(text, str)
        assert len(text) > 0

    def test_format_report_includes_coverage_percentage(self):
        """Formatted report includes the coverage percentage."""
        emails = [
            _make_email(id=f"e{i}", sender_email=f"s{i}@a.com", sender_domain="a.com")
            for i in range(10)
        ]
        corpus = _make_corpus(emails)
        cats = [_make_categorization(f"e{i}", "X") for i in range(8)] + [
            _make_uncategorized(f"e{i}") for i in range(8, 10)
        ]
        report = _make_report(cats)
        analysis = self.reporter.analyze_coverage(report, corpus)

        text = self.reporter.format_report(analysis)

        assert "80.0%" in text

    def test_format_report_includes_category_names(self):
        """Formatted report includes the names of categories used."""
        emails = [
            _make_email(id=f"e{i}", sender_email=f"s{i}@a.com", sender_domain="a.com")
            for i in range(6)
        ]
        corpus = _make_corpus(emails)
        cats = [_make_categorization(f"e{i}", "Alpha") for i in range(3)] + [
            _make_categorization(f"e{i}", "Beta") for i in range(3, 6)
        ]
        report = _make_report(cats)
        analysis = self.reporter.analyze_coverage(report, corpus)

        text = self.reporter.format_report(analysis)

        assert "Alpha" in text
        assert "Beta" in text

    def test_format_report_includes_recommendations(self):
        """Formatted report includes recommendations when present."""
        emails = [
            _make_email(
                id=f"e{i}",
                sender_email=f"p{i}@promo.io",
                sender_domain="promo.io",
                subject=f"Promo {i}",
            )
            for i in range(5)
        ]
        corpus = _make_corpus(emails)
        cats = [_make_uncategorized(f"e{i}") for i in range(5)]
        report = _make_report(cats)
        analysis = self.reporter.analyze_coverage(report, corpus)

        text = self.reporter.format_report(analysis)

        assert "Recommendation" in text or "recommendation" in text

    def test_format_report_empty_corpus(self):
        """Formatted report handles empty corpus gracefully."""
        corpus = _make_corpus([])
        report = _make_report([], total_emails=0)
        analysis = self.reporter.analyze_coverage(report, corpus)

        text = self.reporter.format_report(analysis)

        assert isinstance(text, str)
        assert "0" in text

    def test_format_report_includes_distribution_stats(self):
        """Formatted report includes distribution statistics."""
        emails = [
            _make_email(id=f"e{i}", sender_email=f"s{i}@a.com", sender_domain="a.com")
            for i in range(6)
        ]
        corpus = _make_corpus(emails)
        cats = [_make_categorization(f"e{i}", "A") for i in range(4)] + [
            _make_categorization(f"e{i}", "B") for i in range(4, 6)
        ]
        report = _make_report(cats)
        analysis = self.reporter.analyze_coverage(report, corpus)

        text = self.reporter.format_report(analysis)

        # Should include some distribution info (mean, median, etc.)
        assert "mean" in text.lower() or "median" in text.lower() or "distribution" in text.lower()

    def test_format_report_includes_uncategorized_patterns(self):
        """Formatted report shows uncategorized pattern details."""
        emails = [
            _make_email(
                id=f"e{i}",
                sender_email=f"spam{i}@junk.org",
                sender_domain="junk.org",
                subject=f"Buy now {i}",
            )
            for i in range(5)
        ]
        corpus = _make_corpus(emails)
        cats = [_make_uncategorized(f"e{i}") for i in range(5)]
        report = _make_report(cats)
        analysis = self.reporter.analyze_coverage(report, corpus)

        text = self.reporter.format_report(analysis)

        assert "junk.org" in text


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Edge cases and boundary conditions for CoverageReporter."""

    def setup_method(self):
        self.reporter = CoverageReporter()

    def test_all_uncategorized(self):
        """0% coverage when no emails are categorized."""
        emails = [
            _make_email(id=f"e{i}", sender_email=f"s{i}@a.com", sender_domain="a.com")
            for i in range(5)
        ]
        corpus = _make_corpus(emails)
        cats = [_make_uncategorized(f"e{i}") for i in range(5)]
        report = _make_report(cats)

        analysis = self.reporter.analyze_coverage(report, corpus)

        assert analysis.coverage_percentage == 0.0
        assert analysis.categorized_count == 0
        assert analysis.uncategorized_count == 5

    def test_single_email_categorized(self):
        """Single email corpus at 100% coverage."""
        emails = [_make_email(id="e0", sender_email="s@a.com", sender_domain="a.com")]
        corpus = _make_corpus(emails)
        cats = [_make_categorization("e0", "Sole")]
        report = _make_report(cats)

        analysis = self.reporter.analyze_coverage(report, corpus)

        assert analysis.coverage_percentage == 100.0
        assert len(analysis.per_category) == 1
        assert analysis.per_category[0].category_name == "Sole"

    def test_many_categories(self):
        """Large number of categories produces correct per-category breakdowns."""
        n_cats = 20
        emails = [
            _make_email(id=f"e{i}", sender_email=f"s{i}@a.com", sender_domain="a.com")
            for i in range(n_cats)
        ]
        corpus = _make_corpus(emails)
        cats = [_make_categorization(f"e{i}", f"Cat{i}") for i in range(n_cats)]
        report = _make_report(cats)

        analysis = self.reporter.analyze_coverage(report, corpus)

        assert len(analysis.per_category) == n_cats
        for pc in analysis.per_category:
            assert pc.email_count == 1
            assert pc.percentage == pytest.approx(100.0 / n_cats)

    def test_uncategorized_emails_not_in_corpus_ignored(self):
        """Uncategorized email IDs not in corpus are handled gracefully.

        The reporter uses the corpus to look up email metadata for pattern detection.
        If an email ID in the report doesn't exist in the corpus, skip it.
        """
        emails = [_make_email(id="e0", sender_email="s@a.com", sender_domain="a.com")]
        corpus = _make_corpus(emails)
        # Report includes an email ID not in corpus
        cats = [
            _make_uncategorized("e0"),
            _make_uncategorized("ghost_email"),
        ]
        report = _make_report(cats, total_emails=2)

        # Should not raise
        analysis = self.reporter.analyze_coverage(report, corpus)
        assert analysis.uncategorized_count == 2

    def test_high_value_pattern_detection(self):
        """High-value patterns: frequent sender with no rule match should be flagged."""
        # 6 emails from same sender, all uncategorized -- should be flagged
        emails = [
            _make_email(
                id=f"e{i}",
                sender_email="important@vip.com",
                sender_domain="vip.com",
                subject=f"VIP Update {i}",
            )
            for i in range(6)
        ]
        corpus = _make_corpus(emails)
        cats = [_make_uncategorized(f"e{i}") for i in range(6)]
        report = _make_report(cats)

        analysis = self.reporter.analyze_coverage(report, corpus)

        # Should detect sender pattern
        sender_patterns = [
            p for p in analysis.uncategorized_patterns if p.pattern_type == "sender_email"
        ]
        assert any(p.value == "important@vip.com" for p in sender_patterns)
        # Should generate recommendation
        assert len(analysis.recommendations) >= 1

    def test_per_category_sorted_by_count_descending(self):
        """Per-category coverage is sorted by email count descending."""
        emails = [
            _make_email(id=f"e{i}", sender_email=f"s{i}@a.com", sender_domain="a.com")
            for i in range(10)
        ]
        corpus = _make_corpus(emails)
        cats = (
            [_make_categorization(f"e{i}", "Big") for i in range(5)]
            + [_make_categorization(f"e{i}", "Medium") for i in range(5, 8)]
            + [_make_categorization(f"e{i}", "Small") for i in range(8, 10)]
        )
        report = _make_report(cats)

        analysis = self.reporter.analyze_coverage(report, corpus)

        counts = [c.email_count for c in analysis.per_category]
        assert counts == sorted(counts, reverse=True)
