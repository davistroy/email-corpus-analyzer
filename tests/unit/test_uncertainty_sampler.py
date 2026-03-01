"""Tests for UncertaintySampler (Phase 5, Work Item 5.3).

Tests cover:
- get_uncertain(): returns N least confident classifications
- get_disagreements(): identifies rule vs LLM disagreements
- Edge cases: empty input, all same confidence, n > total
- Sorting behavior: ascending confidence for uncertainty, confidence gap for disagreements
"""

from datetime import datetime, timezone

import pytest

from src.learning.uncertainty_sampler import UncertaintySampler
from src.models.categorization import CategoryAssignment, EmailCategorization

# =============================================================================
# Helpers
# =============================================================================


def _make_categorization(
    email_id: str,
    category: str,
    confidence: float,
    source: str | None = None,
) -> EmailCategorization:
    """Create an EmailCategorization for testing."""
    return EmailCategorization(
        email_id=email_id,
        primary_category=CategoryAssignment(
            category_name=category,
            confidence=confidence,
            source=source,
        ),
        categorized_at=datetime(2026, 2, 28, tzinfo=timezone.utc),
    )


def _make_uncategorized(email_id: str) -> EmailCategorization:
    """Create an uncategorized EmailCategorization."""
    return EmailCategorization.uncategorized(email_id=email_id)


# =============================================================================
# UncertaintySampler instantiation
# =============================================================================


class TestUncertaintySamplerInit:
    """Test UncertaintySampler construction."""

    def test_default_construction(self):
        sampler = UncertaintySampler()
        assert sampler is not None

    def test_custom_default_n(self):
        sampler = UncertaintySampler(default_n=5)
        assert sampler.default_n == 5

    def test_default_n_value(self):
        sampler = UncertaintySampler()
        assert sampler.default_n == 10


# =============================================================================
# get_uncertain()
# =============================================================================


class TestGetUncertain:
    """Test get_uncertain returns N least confident classifications."""

    def setup_method(self):
        self.sampler = UncertaintySampler()

    def test_returns_n_least_confident(self):
        """Should return the N categorizations with lowest confidence."""
        cats = [
            _make_categorization("e1", "A", 0.9),
            _make_categorization("e2", "B", 0.3),
            _make_categorization("e3", "C", 0.5),
            _make_categorization("e4", "D", 0.1),
            _make_categorization("e5", "E", 0.7),
        ]
        result = self.sampler.get_uncertain(cats, n=3)
        assert len(result) == 3
        # Ordered ascending by confidence
        assert result[0].email_id == "e4"  # 0.1
        assert result[1].email_id == "e2"  # 0.3
        assert result[2].email_id == "e3"  # 0.5

    def test_ascending_confidence_order(self):
        """Results should be sorted by confidence ascending."""
        cats = [
            _make_categorization("e1", "A", 0.8),
            _make_categorization("e2", "B", 0.2),
            _make_categorization("e3", "C", 0.6),
            _make_categorization("e4", "D", 0.4),
        ]
        result = self.sampler.get_uncertain(cats, n=4)
        confidences = [r.primary_category.confidence for r in result]
        assert confidences == sorted(confidences)

    def test_empty_input(self):
        """Empty input should return empty list."""
        result = self.sampler.get_uncertain([], n=5)
        assert result == []

    def test_n_greater_than_total(self):
        """When n > total, return all sorted by confidence ascending."""
        cats = [
            _make_categorization("e1", "A", 0.5),
            _make_categorization("e2", "B", 0.3),
        ]
        result = self.sampler.get_uncertain(cats, n=10)
        assert len(result) == 2
        assert result[0].email_id == "e2"  # 0.3
        assert result[1].email_id == "e1"  # 0.5

    def test_n_equals_zero(self):
        """n=0 should return empty list."""
        cats = [_make_categorization("e1", "A", 0.5)]
        result = self.sampler.get_uncertain(cats, n=0)
        assert result == []

    def test_all_same_confidence(self):
        """When all have the same confidence, should return any n of them."""
        cats = [_make_categorization(f"e{i}", "A", 0.5) for i in range(5)]
        result = self.sampler.get_uncertain(cats, n=3)
        assert len(result) == 3
        # All should have confidence 0.5
        for r in result:
            assert r.primary_category.confidence == 0.5

    def test_uses_default_n_when_not_specified(self):
        """When n is not specified, should use default_n."""
        sampler = UncertaintySampler(default_n=2)
        cats = [
            _make_categorization("e1", "A", 0.9),
            _make_categorization("e2", "B", 0.3),
            _make_categorization("e3", "C", 0.5),
        ]
        result = sampler.get_uncertain(cats)
        assert len(result) == 2

    def test_excludes_uncategorized(self):
        """Uncategorized emails (confidence=0.0) should be excluded.

        These already need review by definition, so no need to include
        them in the uncertainty sample.
        """
        cats = [
            _make_uncategorized("e1"),
            _make_categorization("e2", "B", 0.3),
            _make_categorization("e3", "C", 0.7),
        ]
        result = self.sampler.get_uncertain(cats, n=3)
        # Only the categorized ones
        assert len(result) == 2
        assert result[0].email_id == "e2"

    def test_single_item(self):
        """Single-item list should return that item."""
        cats = [_make_categorization("e1", "A", 0.5)]
        result = self.sampler.get_uncertain(cats, n=1)
        assert len(result) == 1
        assert result[0].email_id == "e1"

    def test_stable_sort_on_tie(self):
        """Ties in confidence should preserve original order (stable sort)."""
        cats = [
            _make_categorization("e1", "A", 0.5),
            _make_categorization("e2", "B", 0.5),
            _make_categorization("e3", "C", 0.5),
        ]
        result = self.sampler.get_uncertain(cats, n=3)
        assert [r.email_id for r in result] == ["e1", "e2", "e3"]

    def test_negative_n_returns_empty(self):
        """Negative n should be treated as 0 (return empty)."""
        cats = [_make_categorization("e1", "A", 0.5)]
        result = self.sampler.get_uncertain(cats, n=-1)
        assert result == []


# =============================================================================
# get_disagreements()
# =============================================================================


class TestGetDisagreements:
    """Test get_disagreements identifies rule vs LLM classification disagreements."""

    def setup_method(self):
        self.sampler = UncertaintySampler()

    def test_identifies_disagreements(self):
        """Should find emails where rule and LLM assign different categories."""
        rule_results = [
            _make_categorization("e1", "Newsletters", 0.9, source="rule:r1"),
            _make_categorization("e2", "Promotions", 0.8, source="rule:r2"),
            _make_categorization("e3", "Personal", 0.7, source="rule:r3"),
        ]
        llm_results = [
            _make_categorization("e1", "Newsletters", 0.85, source="llm:ollama"),
            _make_categorization("e2", "Newsletters", 0.7, source="llm:ollama"),  # disagrees
            _make_categorization("e3", "Social", 0.6, source="llm:ollama"),  # disagrees
        ]
        disagreements = self.sampler.get_disagreements(rule_results, llm_results)
        assert len(disagreements) == 2

    def test_disagreement_tuple_structure(self):
        """Each disagreement should be (rule_result, llm_result) tuple."""
        rule_results = [
            _make_categorization("e1", "A", 0.9, source="rule:r1"),
        ]
        llm_results = [
            _make_categorization("e1", "B", 0.8, source="llm:ollama"),
        ]
        disagreements = self.sampler.get_disagreements(rule_results, llm_results)
        assert len(disagreements) == 1
        rule_cat, llm_cat = disagreements[0]
        assert rule_cat.primary_category.category_name == "A"
        assert llm_cat.primary_category.category_name == "B"

    def test_no_disagreements(self):
        """Should return empty list when all classifications agree."""
        rule_results = [
            _make_categorization("e1", "A", 0.9),
            _make_categorization("e2", "B", 0.8),
        ]
        llm_results = [
            _make_categorization("e1", "A", 0.7),
            _make_categorization("e2", "B", 0.6),
        ]
        disagreements = self.sampler.get_disagreements(rule_results, llm_results)
        assert len(disagreements) == 0

    def test_empty_input_both(self):
        """Empty inputs should return empty list."""
        disagreements = self.sampler.get_disagreements([], [])
        assert disagreements == []

    def test_empty_rule_results(self):
        """Empty rule results should return empty list."""
        llm_results = [_make_categorization("e1", "A", 0.8)]
        disagreements = self.sampler.get_disagreements([], llm_results)
        assert disagreements == []

    def test_empty_llm_results(self):
        """Empty LLM results should return empty list."""
        rule_results = [_make_categorization("e1", "A", 0.8)]
        disagreements = self.sampler.get_disagreements(rule_results, [])
        assert disagreements == []

    def test_sorted_by_confidence_gap_descending(self):
        """Disagreements should be sorted by confidence gap (descending).

        Confidence gap = abs(rule_confidence - llm_confidence).
        Larger gaps first because they represent more uncertain disagreements.
        """
        rule_results = [
            _make_categorization("e1", "A", 0.9),
            _make_categorization("e2", "C", 0.5),
            _make_categorization("e3", "E", 0.7),
        ]
        llm_results = [
            _make_categorization("e1", "B", 0.8),  # gap = 0.1
            _make_categorization("e2", "D", 0.9),  # gap = 0.4
            _make_categorization("e3", "F", 0.3),  # gap = 0.4
        ]
        disagreements = self.sampler.get_disagreements(rule_results, llm_results)
        assert len(disagreements) == 3
        # e2 and e3 have gap=0.4 (first), e1 has gap=0.1 (last)
        # For same gap, preserve original order (stable sort)
        gaps = [
            abs(rule.primary_category.confidence - llm.primary_category.confidence)
            for rule, llm in disagreements
        ]
        assert gaps == sorted(gaps, reverse=True)

    def test_unmatched_email_ids_ignored(self):
        """Emails present in only one result set should be ignored."""
        rule_results = [
            _make_categorization("e1", "A", 0.9),
            _make_categorization("e2", "B", 0.8),
        ]
        llm_results = [
            _make_categorization("e1", "C", 0.7),
            _make_categorization("e3", "D", 0.6),  # e3 not in rule_results
        ]
        disagreements = self.sampler.get_disagreements(rule_results, llm_results)
        assert len(disagreements) == 1
        rule_cat, llm_cat = disagreements[0]
        assert rule_cat.email_id == "e1"

    def test_case_sensitive_category_comparison(self):
        """Category comparison should be case-sensitive."""
        rule_results = [
            _make_categorization("e1", "Newsletters", 0.9),
        ]
        llm_results = [
            _make_categorization("e1", "newsletters", 0.8),  # different case
        ]
        disagreements = self.sampler.get_disagreements(rule_results, llm_results)
        assert len(disagreements) == 1

    def test_uncategorized_vs_categorized_is_disagreement(self):
        """Uncategorized (rule) vs categorized (LLM) should be a disagreement."""
        rule_results = [_make_uncategorized("e1")]
        llm_results = [_make_categorization("e1", "A", 0.8)]
        disagreements = self.sampler.get_disagreements(rule_results, llm_results)
        assert len(disagreements) == 1

    def test_both_uncategorized_not_a_disagreement(self):
        """Both uncategorized should not be a disagreement."""
        rule_results = [_make_uncategorized("e1")]
        llm_results = [_make_uncategorized("e1")]
        disagreements = self.sampler.get_disagreements(rule_results, llm_results)
        assert len(disagreements) == 0


# =============================================================================
# Integration-style tests
# =============================================================================


class TestUncertaintySamplerIntegration:
    """Integration tests combining get_uncertain and get_disagreements."""

    def test_uncertain_and_disagreements_complement(self):
        """Uncertain items and disagreement items can overlap but serve different purposes."""
        sampler = UncertaintySampler()

        # Build a realistic set of categorizations
        rule_results = [
            _make_categorization("e1", "Newsletters", 0.95, source="rule:r1"),
            _make_categorization("e2", "Promotions", 0.4, source="rule:r2"),  # low conf
            _make_categorization("e3", "Personal", 0.85, source="rule:r3"),
            _make_categorization("e4", "Social", 0.3, source="rule:r4"),  # low conf
            _make_categorization("e5", "Work", 0.6, source="rule:r5"),
        ]
        llm_results = [
            _make_categorization("e1", "Newsletters", 0.9, source="llm:ollama"),
            _make_categorization("e2", "Newsletters", 0.7, source="llm:ollama"),  # disagree
            _make_categorization("e3", "Personal", 0.8, source="llm:ollama"),
            _make_categorization("e4", "Personal", 0.5, source="llm:ollama"),  # disagree
            _make_categorization("e5", "Work", 0.55, source="llm:ollama"),
        ]

        uncertain = sampler.get_uncertain(rule_results, n=2)
        assert len(uncertain) == 2
        # e4 (0.3) and e2 (0.4) are least confident
        assert uncertain[0].email_id == "e4"
        assert uncertain[1].email_id == "e2"

        disagreements = sampler.get_disagreements(rule_results, llm_results)
        assert len(disagreements) == 2
        # e2 and e4 disagree

    def test_large_batch_performance(self):
        """Should handle large batches efficiently."""
        sampler = UncertaintySampler()
        cats = [_make_categorization(f"e{i}", "A", i / 1000.0) for i in range(1, 1001)]
        result = sampler.get_uncertain(cats, n=10)
        assert len(result) == 10
        # Lowest confidences should be 0.001 through 0.010
        assert result[0].primary_category.confidence == pytest.approx(0.001)
        assert result[9].primary_category.confidence == pytest.approx(0.010)
