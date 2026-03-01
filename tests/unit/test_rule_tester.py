"""
Unit tests for RuleTester (Phase 3, Item 3.4).

Tests dry-run evaluation of rules against a corpus: per-rule match counts,
coverage statistics, uncovered emails, conflict reports (emails matching
multiple rules), confusion matrix, and progress callbacks.

TDD: These tests are written first, implementation follows.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.models.corpus import Corpus, CorpusMetadata
from src.models.email import Email
from src.models.rule import (
    CategoryRule,
    ConditionField,
    ConditionLogic,
    ConditionOperator,
    RuleAction,
    RuleActionType,
    RuleCondition,
    RuleSet,
)
from src.rules.tester import (
    ConflictEntry,
    ConfusionCell,
    ConfusionMatrix,
    RuleMatchDetail,
    RuleTester,
    TestReport,
)

# =============================================================================
# Helpers
# =============================================================================


def _make_email(
    id: str = "email_001",  # noqa: A002
    sender_email: str = "alice@example.com",
    sender_domain: str = "example.com",
    subject: str = "Weekly Team Update",
    body_text: str = "Hi team, here is the weekly status report.",
    **overrides,
) -> Email:
    """Create a test email with sensible defaults."""
    defaults = {
        "id": id,
        "sender_email": sender_email,
        "sender_name": "Alice Smith",
        "sender_domain": sender_domain,
        "recipient_email": "bob@test.org",
        "subject": subject,
        "body_text": body_text,
        "received_date": datetime(2024, 6, 15, 9, 0, 0),
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


def _make_rule(
    rule_id: str = "rule_1",
    name: str = "Test Rule",
    field: ConditionField = ConditionField.SENDER_DOMAIN,
    operator: ConditionOperator = ConditionOperator.EQUALS,
    value: str = "example.com",
    category_id: str = "cat_1",
    logic: ConditionLogic = ConditionLogic.AND,
    enabled: bool = True,
    priority: int = 50,
    conditions: list[RuleCondition] | None = None,
) -> CategoryRule:
    """Create a test CategoryRule with a single condition (or custom conditions)."""
    if conditions is None:
        conditions = [RuleCondition(field=field, operator=operator, value=value)]
    return CategoryRule(
        rule_id=rule_id,
        name=name,
        conditions=conditions,
        action=RuleAction(
            action_type=RuleActionType.CATEGORIZE,
            target=name,
            target_category_id=category_id,
        ),
        logic=logic,
        priority=priority,
        enabled=enabled,
        category_id=category_id,
    )


def _make_rule_set(*rules: CategoryRule) -> RuleSet:
    """Create a RuleSet from individual rules."""
    return RuleSet(rules=list(rules))


# =============================================================================
# TestReport model tests
# =============================================================================


class TestTestReportModel:
    """Tests for the TestReport Pydantic model."""

    def test_empty_report(self):
        """An empty TestReport has zero counts and empty collections."""
        report = TestReport(
            total_emails=0,
            total_rules=0,
            rule_matches=[],
            covered_email_ids=set(),
            uncovered_email_ids=set(),
            conflicts=[],
            confusion_matrix=None,
        )
        assert report.total_emails == 0
        assert report.coverage_percentage == 0.0
        assert report.conflict_count == 0
        assert len(report.uncovered_email_ids) == 0

    def test_coverage_percentage_calculation(self):
        """Coverage percentage = covered / total * 100."""
        report = TestReport(
            total_emails=100,
            total_rules=2,
            rule_matches=[],
            covered_email_ids={f"e_{i}" for i in range(75)},
            uncovered_email_ids={f"e_{i}" for i in range(75, 100)},
            conflicts=[],
            confusion_matrix=None,
        )
        assert report.coverage_percentage == 75.0

    def test_coverage_percentage_zero_emails(self):
        """Zero emails yields 0% coverage, not division by zero."""
        report = TestReport(
            total_emails=0,
            total_rules=0,
            rule_matches=[],
            covered_email_ids=set(),
            uncovered_email_ids=set(),
            conflicts=[],
            confusion_matrix=None,
        )
        assert report.coverage_percentage == 0.0

    def test_conflict_count(self):
        """Conflict count matches length of conflicts list."""
        conflicts = [
            ConflictEntry(
                email_id="e_1",
                matching_rule_ids=["rule_1", "rule_2"],
                matching_rule_names=["Rule A", "Rule B"],
            ),
            ConflictEntry(
                email_id="e_2",
                matching_rule_ids=["rule_1", "rule_3"],
                matching_rule_names=["Rule A", "Rule C"],
            ),
        ]
        report = TestReport(
            total_emails=10,
            total_rules=3,
            rule_matches=[],
            covered_email_ids={"e_1", "e_2"},
            uncovered_email_ids=set(),
            conflicts=conflicts,
            confusion_matrix=None,
        )
        assert report.conflict_count == 2


class TestRuleMatchDetail:
    """Tests for RuleMatchDetail data model."""

    def test_basic_fields(self):
        """RuleMatchDetail stores per-rule match data."""
        detail = RuleMatchDetail(
            rule_id="rule_1",
            rule_name="Test Rule",
            match_count=42,
            matched_email_ids=["e_1", "e_2"],
            example_subjects=["Subject A"],
            example_senders=["alice@test.com"],
        )
        assert detail.rule_id == "rule_1"
        assert detail.match_count == 42
        assert len(detail.matched_email_ids) == 2
        assert detail.match_percentage == 0.0  # unset default

    def test_match_percentage_field(self):
        """Match percentage can be set explicitly."""
        detail = RuleMatchDetail(
            rule_id="rule_1",
            rule_name="Test",
            match_count=50,
            matched_email_ids=[],
            example_subjects=[],
            example_senders=[],
            match_percentage=50.0,
        )
        assert detail.match_percentage == 50.0


# =============================================================================
# RuleTester.test_rules — basic dry-run
# =============================================================================


class TestRuleTesterBasicDryRun:
    """Tests for dry-running rules against a corpus."""

    def test_single_rule_matches_all(self):
        """One rule matching all emails produces 100% coverage."""
        emails = [_make_email(id=f"e_{i}", sender_domain="example.com") for i in range(5)]
        corpus = _make_corpus(emails)
        rule = _make_rule(value="example.com")
        rule_set = _make_rule_set(rule)

        tester = RuleTester()
        report = tester.test_rules(rule_set, corpus)

        assert report.total_emails == 5
        assert report.total_rules == 1
        assert report.coverage_percentage == 100.0
        assert len(report.uncovered_email_ids) == 0
        assert len(report.rule_matches) == 1
        assert report.rule_matches[0].match_count == 5

    def test_single_rule_matches_some(self):
        """One rule matching a subset shows correct coverage and uncovered set."""
        emails = [
            _make_email(id="e_1", sender_domain="example.com"),
            _make_email(id="e_2", sender_domain="example.com"),
            _make_email(id="e_3", sender_domain="other.org"),
        ]
        corpus = _make_corpus(emails)
        rule = _make_rule(value="example.com")
        rule_set = _make_rule_set(rule)

        tester = RuleTester()
        report = tester.test_rules(rule_set, corpus)

        assert report.total_emails == 3
        assert report.coverage_percentage == pytest.approx(66.666, abs=0.01)
        assert report.uncovered_email_ids == {"e_3"}
        assert report.rule_matches[0].match_count == 2

    def test_no_rules_zero_coverage(self):
        """An empty rule set yields 0% coverage; all emails uncovered."""
        emails = [_make_email(id="e_1")]
        corpus = _make_corpus(emails)
        rule_set = RuleSet(rules=[])

        tester = RuleTester()
        report = tester.test_rules(rule_set, corpus)

        assert report.total_emails == 1
        assert report.total_rules == 0
        assert report.coverage_percentage == 0.0
        assert report.uncovered_email_ids == {"e_1"}

    def test_empty_corpus(self):
        """An empty corpus yields an empty report with 0% coverage."""
        corpus = _make_corpus([])
        rule = _make_rule()
        rule_set = _make_rule_set(rule)

        tester = RuleTester()
        report = tester.test_rules(rule_set, corpus)

        assert report.total_emails == 0
        assert report.total_rules == 1
        assert report.coverage_percentage == 0.0
        assert len(report.rule_matches) == 1
        assert report.rule_matches[0].match_count == 0

    def test_disabled_rules_not_evaluated(self):
        """Disabled rules appear in rule_matches with zero matches."""
        emails = [_make_email(id="e_1", sender_domain="example.com")]
        corpus = _make_corpus(emails)
        rule = _make_rule(enabled=False, value="example.com")
        rule_set = _make_rule_set(rule)

        tester = RuleTester()
        report = tester.test_rules(rule_set, corpus)

        assert report.coverage_percentage == 0.0
        assert len(report.rule_matches) == 1
        assert report.rule_matches[0].match_count == 0
        assert report.uncovered_email_ids == {"e_1"}

    def test_multiple_rules_disjoint(self):
        """Two rules matching disjoint email sets yield combined coverage."""
        emails = [
            _make_email(id="e_1", sender_domain="alpha.com"),
            _make_email(id="e_2", sender_domain="beta.com"),
            _make_email(id="e_3", sender_domain="gamma.com"),
        ]
        corpus = _make_corpus(emails)
        rule_a = _make_rule(rule_id="r_a", value="alpha.com", category_id="cat_a")
        rule_b = _make_rule(rule_id="r_b", value="beta.com", category_id="cat_b")
        rule_set = _make_rule_set(rule_a, rule_b)

        tester = RuleTester()
        report = tester.test_rules(rule_set, corpus)

        assert report.coverage_percentage == pytest.approx(66.666, abs=0.01)
        assert report.uncovered_email_ids == {"e_3"}
        assert report.conflict_count == 0

        match_a = next(m for m in report.rule_matches if m.rule_id == "r_a")
        match_b = next(m for m in report.rule_matches if m.rule_id == "r_b")
        assert match_a.match_count == 1
        assert match_b.match_count == 1


# =============================================================================
# Conflict detection (emails matching multiple rules)
# =============================================================================


class TestRuleTesterConflicts:
    """Tests for detecting conflicts (email matched by multiple rules)."""

    def test_overlapping_rules_create_conflict(self):
        """An email matched by two rules creates a conflict entry."""
        emails = [
            _make_email(id="e_1", sender_domain="example.com", subject="Invoice #123"),
        ]
        corpus = _make_corpus(emails)
        rule_domain = _make_rule(
            rule_id="r_domain",
            name="Domain Rule",
            value="example.com",
            category_id="cat_domain",
        )
        rule_subject = _make_rule(
            rule_id="r_subject",
            name="Subject Rule",
            field=ConditionField.SUBJECT,
            operator=ConditionOperator.CONTAINS,
            value="Invoice",
            category_id="cat_subject",
        )
        rule_set = _make_rule_set(rule_domain, rule_subject)

        tester = RuleTester()
        report = tester.test_rules(rule_set, corpus)

        assert report.conflict_count == 1
        conflict = report.conflicts[0]
        assert conflict.email_id == "e_1"
        assert set(conflict.matching_rule_ids) == {"r_domain", "r_subject"}
        assert len(conflict.matching_rule_names) == 2

    def test_no_conflict_for_single_rule_match(self):
        """An email matched by exactly one rule is not a conflict."""
        emails = [
            _make_email(id="e_1", sender_domain="example.com"),
            _make_email(id="e_2", sender_domain="other.org"),
        ]
        corpus = _make_corpus(emails)
        rule = _make_rule(rule_id="r_1", value="example.com")
        rule_set = _make_rule_set(rule)

        tester = RuleTester()
        report = tester.test_rules(rule_set, corpus)

        assert report.conflict_count == 0

    def test_three_rule_conflict(self):
        """An email matched by three rules lists all three in conflict entry."""
        email = _make_email(
            id="e_1",
            sender_domain="shop.com",
            subject="Order Confirmation",
            body_text="Your order has been confirmed.",
        )
        corpus = _make_corpus([email])
        rule_a = _make_rule(rule_id="r_a", value="shop.com", category_id="cat_a", name="R_A")
        rule_b = _make_rule(
            rule_id="r_b",
            field=ConditionField.SUBJECT,
            operator=ConditionOperator.CONTAINS,
            value="Order",
            category_id="cat_b",
            name="R_B",
        )
        rule_c = _make_rule(
            rule_id="r_c",
            field=ConditionField.BODY,
            operator=ConditionOperator.CONTAINS,
            value="confirmed",
            category_id="cat_c",
            name="R_C",
        )
        rule_set = _make_rule_set(rule_a, rule_b, rule_c)

        tester = RuleTester()
        report = tester.test_rules(rule_set, corpus)

        assert report.conflict_count == 1
        assert len(report.conflicts[0].matching_rule_ids) == 3

    def test_conflicts_only_for_different_category_rules(self):
        """Two rules for the SAME category matching same email is NOT a conflict."""
        emails = [
            _make_email(id="e_1", sender_domain="example.com", subject="Update"),
        ]
        corpus = _make_corpus(emails)
        rule_a = _make_rule(rule_id="r_a", value="example.com", category_id="cat_same", name="R_A")
        rule_b = _make_rule(
            rule_id="r_b",
            field=ConditionField.SUBJECT,
            operator=ConditionOperator.CONTAINS,
            value="Update",
            category_id="cat_same",
            name="R_B",
        )
        rule_set = _make_rule_set(rule_a, rule_b)

        tester = RuleTester()
        report = tester.test_rules(rule_set, corpus)

        # Same category means no conflict
        assert report.conflict_count == 0


# =============================================================================
# Per-rule match detail
# =============================================================================


class TestPerRuleMatchDetail:
    """Tests for per-rule match counts, examples, and match percentages."""

    def test_match_detail_example_subjects(self):
        """Rule match detail includes example subjects from matched emails."""
        emails = [
            _make_email(id="e_1", sender_domain="example.com", subject="Alpha Report"),
            _make_email(id="e_2", sender_domain="example.com", subject="Beta Report"),
            _make_email(id="e_3", sender_domain="example.com", subject="Gamma Report"),
        ]
        corpus = _make_corpus(emails)
        rule = _make_rule(value="example.com")
        rule_set = _make_rule_set(rule)

        tester = RuleTester()
        report = tester.test_rules(rule_set, corpus)

        detail = report.rule_matches[0]
        assert detail.match_count == 3
        assert len(detail.example_subjects) <= 5  # capped at 5 examples
        assert "Alpha Report" in detail.example_subjects

    def test_match_detail_example_senders(self):
        """Rule match detail includes example senders from matched emails."""
        emails = [
            _make_email(id="e_1", sender_domain="example.com", sender_email="a@example.com"),
            _make_email(id="e_2", sender_domain="example.com", sender_email="b@example.com"),
        ]
        corpus = _make_corpus(emails)
        rule = _make_rule(value="example.com")
        rule_set = _make_rule_set(rule)

        tester = RuleTester()
        report = tester.test_rules(rule_set, corpus)

        detail = report.rule_matches[0]
        assert "a@example.com" in detail.example_senders
        assert "b@example.com" in detail.example_senders

    def test_match_percentage_relative_to_corpus(self):
        """Match percentage is relative to total corpus size."""
        emails = [
            _make_email(id="e_1", sender_domain="example.com"),
            _make_email(id="e_2", sender_domain="example.com"),
            _make_email(id="e_3", sender_domain="other.org"),
            _make_email(id="e_4", sender_domain="other.org"),
        ]
        corpus = _make_corpus(emails)
        rule = _make_rule(value="example.com")
        rule_set = _make_rule_set(rule)

        tester = RuleTester()
        report = tester.test_rules(rule_set, corpus)

        detail = report.rule_matches[0]
        assert detail.match_percentage == 50.0

    def test_example_subjects_capped_at_five(self):
        """Example subjects list is capped at 5 entries."""
        emails = [
            _make_email(id=f"e_{i}", sender_domain="example.com", subject=f"Subject {i}")
            for i in range(20)
        ]
        corpus = _make_corpus(emails)
        rule = _make_rule(value="example.com")
        rule_set = _make_rule_set(rule)

        tester = RuleTester()
        report = tester.test_rules(rule_set, corpus)

        detail = report.rule_matches[0]
        assert detail.match_count == 20
        assert len(detail.example_subjects) == 5
        assert len(detail.example_senders) == 5


# =============================================================================
# Confusion matrix
# =============================================================================


class TestConfusionMatrix:
    """Tests for the rule overlap confusion matrix."""

    def test_confusion_matrix_disjoint_rules(self):
        """Two rules matching disjoint emails have zero overlap in the matrix."""
        emails = [
            _make_email(id="e_1", sender_domain="alpha.com"),
            _make_email(id="e_2", sender_domain="beta.com"),
        ]
        corpus = _make_corpus(emails)
        rule_a = _make_rule(rule_id="r_a", value="alpha.com", category_id="cat_a")
        rule_b = _make_rule(rule_id="r_b", value="beta.com", category_id="cat_b")
        rule_set = _make_rule_set(rule_a, rule_b)

        tester = RuleTester()
        report = tester.test_rules(rule_set, corpus)

        assert report.confusion_matrix is not None
        cm = report.confusion_matrix

        # Diagonal entries: each rule matches its own emails
        cell_aa = cm.get_cell("r_a", "r_a")
        assert cell_aa is not None
        assert cell_aa.count == 1

        cell_bb = cm.get_cell("r_b", "r_b")
        assert cell_bb is not None
        assert cell_bb.count == 1

        # Off-diagonal: zero overlap
        cell_ab = cm.get_cell("r_a", "r_b")
        assert cell_ab is not None
        assert cell_ab.count == 0

    def test_confusion_matrix_overlapping_rules(self):
        """Two rules matching the same email show overlap in off-diagonal cells."""
        email = _make_email(id="e_1", sender_domain="shop.com", subject="Order Confirmation")
        corpus = _make_corpus([email])
        rule_a = _make_rule(rule_id="r_a", value="shop.com", category_id="cat_a")
        rule_b = _make_rule(
            rule_id="r_b",
            field=ConditionField.SUBJECT,
            operator=ConditionOperator.CONTAINS,
            value="Order",
            category_id="cat_b",
        )
        rule_set = _make_rule_set(rule_a, rule_b)

        tester = RuleTester()
        report = tester.test_rules(rule_set, corpus)

        cm = report.confusion_matrix
        assert cm is not None

        # Off-diagonal entries show overlap
        cell_ab = cm.get_cell("r_a", "r_b")
        assert cell_ab is not None
        assert cell_ab.count == 1

        cell_ba = cm.get_cell("r_b", "r_a")
        assert cell_ba is not None
        assert cell_ba.count == 1

    def test_confusion_matrix_none_for_single_rule(self):
        """Confusion matrix is None when there is only one enabled rule."""
        emails = [_make_email(id="e_1")]
        corpus = _make_corpus(emails)
        rule = _make_rule()
        rule_set = _make_rule_set(rule)

        tester = RuleTester()
        report = tester.test_rules(rule_set, corpus)

        # Only 1 rule: no pairwise overlap to compute
        assert report.confusion_matrix is None

    def test_confusion_matrix_none_for_empty_rules(self):
        """Confusion matrix is None when there are zero rules."""
        emails = [_make_email(id="e_1")]
        corpus = _make_corpus(emails)
        rule_set = RuleSet(rules=[])

        tester = RuleTester()
        report = tester.test_rules(rule_set, corpus)

        assert report.confusion_matrix is None

    def test_confusion_matrix_rule_ids(self):
        """Confusion matrix enumerates all enabled rule IDs."""
        emails = [_make_email(id="e_1", sender_domain="example.com")]
        corpus = _make_corpus(emails)
        rule_a = _make_rule(rule_id="r_a", value="example.com", category_id="cat_a")
        rule_b = _make_rule(rule_id="r_b", value="other.com", category_id="cat_b")
        rule_set = _make_rule_set(rule_a, rule_b)

        tester = RuleTester()
        report = tester.test_rules(rule_set, corpus)

        cm = report.confusion_matrix
        assert cm is not None
        assert set(cm.rule_ids) == {"r_a", "r_b"}

    def test_confusion_matrix_symmetric(self):
        """Overlap is symmetric: cell(A,B) == cell(B,A)."""
        emails = [
            _make_email(id="e_1", sender_domain="shop.com", subject="Order"),
            _make_email(id="e_2", sender_domain="shop.com", subject="Delivery"),
            _make_email(id="e_3", sender_domain="other.com", subject="Order"),
        ]
        corpus = _make_corpus(emails)
        rule_a = _make_rule(rule_id="r_a", value="shop.com", category_id="cat_a")
        rule_b = _make_rule(
            rule_id="r_b",
            field=ConditionField.SUBJECT,
            operator=ConditionOperator.CONTAINS,
            value="Order",
            category_id="cat_b",
        )
        rule_set = _make_rule_set(rule_a, rule_b)

        tester = RuleTester()
        report = tester.test_rules(rule_set, corpus)

        cm = report.confusion_matrix
        assert cm is not None
        cell_ab = cm.get_cell("r_a", "r_b")
        cell_ba = cm.get_cell("r_b", "r_a")
        assert cell_ab is not None and cell_ba is not None
        assert cell_ab.count == cell_ba.count


# =============================================================================
# Progress callback support
# =============================================================================


class TestProgressCallback:
    """Tests for progress callback during rule testing."""

    def test_progress_callback_called(self):
        """Progress callback is invoked with (current, total) during testing."""
        emails = [_make_email(id=f"e_{i}") for i in range(10)]
        corpus = _make_corpus(emails)
        rule = _make_rule()
        rule_set = _make_rule_set(rule)

        calls: list[tuple[int, int]] = []

        def progress(current: int, total: int) -> None:
            calls.append((current, total))

        tester = RuleTester()
        tester.test_rules(rule_set, corpus, progress_callback=progress)

        # At least one call was made
        assert len(calls) > 0
        # Last call should be (total, total)
        assert calls[-1] == (10, 10)
        # All totals should match corpus size
        assert all(t == 10 for _, t in calls)

    def test_no_callback_no_error(self):
        """test_rules works fine without a progress callback."""
        emails = [_make_email(id="e_1")]
        corpus = _make_corpus(emails)
        rule = _make_rule()
        rule_set = _make_rule_set(rule)

        tester = RuleTester()
        report = tester.test_rules(rule_set, corpus)

        assert report.total_emails == 1

    def test_progress_callback_empty_corpus(self):
        """Progress callback is NOT called for an empty corpus."""
        corpus = _make_corpus([])
        rule_set = _make_rule_set(_make_rule())

        calls: list[tuple[int, int]] = []

        tester = RuleTester()
        tester.test_rules(rule_set, corpus, progress_callback=lambda c, t: calls.append((c, t)))

        assert len(calls) == 0


# =============================================================================
# Edge cases
# =============================================================================


class TestEdgeCases:
    """Edge case tests for RuleTester."""

    def test_all_disabled_rules(self):
        """All disabled rules: zero coverage, all uncovered."""
        emails = [_make_email(id="e_1", sender_domain="example.com")]
        corpus = _make_corpus(emails)
        rule_a = _make_rule(rule_id="r_a", enabled=False, value="example.com")
        rule_b = _make_rule(rule_id="r_b", enabled=False, value="other.com")
        rule_set = _make_rule_set(rule_a, rule_b)

        tester = RuleTester()
        report = tester.test_rules(rule_set, corpus)

        assert report.coverage_percentage == 0.0
        assert report.uncovered_email_ids == {"e_1"}
        # Confusion matrix None because no enabled rules
        assert report.confusion_matrix is None

    def test_large_corpus_report(self):
        """Stress test: RuleTester handles 500 emails and 10 rules."""
        emails = [
            _make_email(
                id=f"e_{i}",
                sender_domain=f"domain{i % 10}.com",
                subject=f"Subject {i}",
            )
            for i in range(500)
        ]
        corpus = _make_corpus(emails)

        rules = [
            _make_rule(
                rule_id=f"r_{d}",
                value=f"domain{d}.com",
                category_id=f"cat_{d}",
            )
            for d in range(10)
        ]
        rule_set = _make_rule_set(*rules)

        tester = RuleTester()
        report = tester.test_rules(rule_set, corpus)

        # All 500 emails should be covered (10 domains, 50 each)
        assert report.total_emails == 500
        assert report.coverage_percentage == 100.0
        assert len(report.uncovered_email_ids) == 0

        # Each rule should match exactly 50
        for detail in report.rule_matches:
            assert detail.match_count == 50

    def test_same_email_matching_all_rules(self):
        """An email matching every rule appears in all rule details."""
        email = _make_email(
            id="e_1",
            sender_domain="example.com",
            subject="Hello World",
            body_text="Body content",
        )
        corpus = _make_corpus([email])
        rule_a = _make_rule(rule_id="r_a", value="example.com", category_id="cat_a")
        rule_b = _make_rule(
            rule_id="r_b",
            field=ConditionField.SUBJECT,
            operator=ConditionOperator.CONTAINS,
            value="Hello",
            category_id="cat_b",
        )
        rule_c = _make_rule(
            rule_id="r_c",
            field=ConditionField.BODY,
            operator=ConditionOperator.CONTAINS,
            value="Body",
            category_id="cat_c",
        )
        rule_set = _make_rule_set(rule_a, rule_b, rule_c)

        tester = RuleTester()
        report = tester.test_rules(rule_set, corpus)

        assert report.coverage_percentage == 100.0
        assert report.conflict_count == 1
        for detail in report.rule_matches:
            assert detail.match_count == 1
            assert "e_1" in detail.matched_email_ids

    def test_rule_matches_sorted_by_match_count_descending(self):
        """Rule match details are sorted by match count (highest first)."""
        emails = [
            _make_email(id="e_1", sender_domain="alpha.com"),
            _make_email(id="e_2", sender_domain="alpha.com"),
            _make_email(id="e_3", sender_domain="alpha.com"),
            _make_email(id="e_4", sender_domain="beta.com"),
        ]
        corpus = _make_corpus(emails)
        # r_a matches 1 email, r_b matches 3 emails
        rule_a = _make_rule(rule_id="r_a", value="beta.com", category_id="cat_a")
        rule_b = _make_rule(rule_id="r_b", value="alpha.com", category_id="cat_b")
        rule_set = _make_rule_set(rule_a, rule_b)

        tester = RuleTester()
        report = tester.test_rules(rule_set, corpus)

        assert report.rule_matches[0].rule_id == "r_b"
        assert report.rule_matches[0].match_count == 3
        assert report.rule_matches[1].rule_id == "r_a"
        assert report.rule_matches[1].match_count == 1


# =============================================================================
# ConfusionMatrix model tests
# =============================================================================


class TestConfusionMatrixModel:
    """Tests for the ConfusionMatrix model directly."""

    def test_get_cell_nonexistent(self):
        """get_cell returns None for rule IDs not in the matrix."""
        cm = ConfusionMatrix(
            rule_ids=["r_a"],
            rule_names={"r_a": "Rule A"},
            cells=[ConfusionCell(row_rule_id="r_a", col_rule_id="r_a", count=5)],
        )
        assert cm.get_cell("r_a", "r_nonexistent") is None
        assert cm.get_cell("r_nonexistent", "r_a") is None

    def test_get_cell_found(self):
        """get_cell returns the correct cell for valid rule IDs."""
        cells = [
            ConfusionCell(row_rule_id="r_a", col_rule_id="r_a", count=3),
            ConfusionCell(row_rule_id="r_a", col_rule_id="r_b", count=1),
            ConfusionCell(row_rule_id="r_b", col_rule_id="r_a", count=1),
            ConfusionCell(row_rule_id="r_b", col_rule_id="r_b", count=2),
        ]
        cm = ConfusionMatrix(
            rule_ids=["r_a", "r_b"],
            rule_names={"r_a": "Rule A", "r_b": "Rule B"},
            cells=cells,
        )
        cell = cm.get_cell("r_a", "r_b")
        assert cell is not None
        assert cell.count == 1
