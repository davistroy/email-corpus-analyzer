"""
Unit tests for EmailCategorizer (Phase 4, Item 4.2).

Tests email categorization using rules: single email categorization,
batch corpus categorization, priority-based primary/secondary assignment,
confidence normalization, uncategorized handling, and progress callbacks.

TDD: These tests are written first, implementation follows.
"""

from datetime import datetime
from unittest.mock import MagicMock

from src.categorizer.categorizer import EmailCategorizer
from src.models.categorization import (
    CategorizationReport,
    EmailCategorization,
)
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

# =============================================================================
# Helpers
# =============================================================================


def _make_email(**overrides) -> Email:
    """Create a test email with sensible defaults, overridable per-field."""
    defaults = {
        "id": "email_001",
        "sender_email": "alice@example.com",
        "sender_name": "Alice Smith",
        "sender_domain": "example.com",
        "recipient_email": "bob@test.org",
        "recipient_name": "Bob Jones",
        "subject": "Weekly Team Update",
        "body_text": "Hi team, here is the weekly status report.",
        "received_date": datetime(2024, 6, 15, 9, 0, 0),
        "has_attachments": False,
    }
    defaults.update(overrides)
    return Email(**defaults)


def _make_condition(
    field: ConditionField = ConditionField.SENDER_DOMAIN,
    operator: ConditionOperator = ConditionOperator.EQUALS,
    value: str = "example.com",
    case_sensitive: bool = False,
) -> RuleCondition:
    return RuleCondition(field=field, operator=operator, value=value, case_sensitive=case_sensitive)


def _make_rule(
    rule_id: str = "rule_001",
    name: str = "Test Rule",
    conditions: list[RuleCondition] | None = None,
    logic: ConditionLogic = ConditionLogic.AND,
    priority: int = 0,
    enabled: bool = True,
    action_target: str = "Test Category",
    action_type: RuleActionType = RuleActionType.CATEGORIZE,
) -> CategoryRule:
    if conditions is None:
        conditions = [_make_condition()]
    return CategoryRule(
        rule_id=rule_id,
        name=name,
        conditions=conditions,
        action=RuleAction(
            action_type=action_type,
            target=action_target,
        ),
        logic=logic,
        priority=priority,
        enabled=enabled,
    )


def _make_rule_set(*rules: CategoryRule) -> RuleSet:
    """Create a RuleSet from the given rules."""
    return RuleSet(rules=list(rules))


def _make_corpus(emails: list[Email]) -> Corpus:
    """Create a Corpus from the given emails."""
    return Corpus(
        extraction_metadata=CorpusMetadata(
            extraction_date=datetime(2024, 6, 15, 12, 0, 0),
            total_emails=len(emails),
            source="m365",
            user_email="user@example.com",
        ),
        emails=emails,
    )


# =============================================================================
# EmailCategorizer Construction
# =============================================================================


class TestEmailCategorizerConstruction:
    """Test EmailCategorizer instantiation."""

    def test_create_categorizer(self):
        """Test creating a categorizer instance."""
        categorizer = EmailCategorizer()
        assert categorizer is not None

    def test_categorizer_has_rule_engine(self):
        """Test categorizer uses a RuleEngine internally."""
        categorizer = EmailCategorizer()
        assert categorizer._engine is not None


# =============================================================================
# categorize_email — Single Email
# =============================================================================


class TestCategorizeEmail:
    """Test categorize_email for single email categorization."""

    def test_single_matching_rule_returns_primary_category(self):
        """Test email matching one rule gets that rule's target as primary."""
        email = _make_email()
        rule = _make_rule(
            rule_id="rule_newsletters",
            priority=10,
            action_target="Newsletters",
            conditions=[
                _make_condition(
                    field=ConditionField.SENDER_DOMAIN,
                    operator=ConditionOperator.EQUALS,
                    value="example.com",
                )
            ],
        )
        rule_set = _make_rule_set(rule)

        categorizer = EmailCategorizer()
        result = categorizer.categorize_email(email, rule_set)

        assert isinstance(result, EmailCategorization)
        assert result.email_id == "email_001"
        assert result.primary_category.category_name == "Newsletters"
        assert result.is_uncategorized is False

    def test_no_matching_rules_returns_uncategorized(self):
        """Test email matching no rules is marked uncategorized."""
        email = _make_email(sender_domain="nomatch.com", sender_email="x@nomatch.com")
        rule = _make_rule(
            conditions=[
                _make_condition(
                    field=ConditionField.SENDER_DOMAIN,
                    operator=ConditionOperator.EQUALS,
                    value="example.com",
                )
            ],
        )
        rule_set = _make_rule_set(rule)

        categorizer = EmailCategorizer()
        result = categorizer.categorize_email(email, rule_set)

        assert result.is_uncategorized is True
        assert result.primary_category.category_name == "Uncategorized"
        assert result.primary_category.confidence == 0.0
        assert result.secondary_categories == []
        assert result.matched_rules == []

    def test_multiple_matching_rules_highest_priority_is_primary(self):
        """Test highest-priority matching rule becomes primary category."""
        email = _make_email()
        low_priority_rule = _make_rule(
            rule_id="rule_low",
            priority=5,
            action_target="General",
            conditions=[
                _make_condition(
                    field=ConditionField.SENDER_DOMAIN,
                    operator=ConditionOperator.EQUALS,
                    value="example.com",
                )
            ],
        )
        high_priority_rule = _make_rule(
            rule_id="rule_high",
            priority=20,
            action_target="Important Updates",
            conditions=[
                _make_condition(
                    field=ConditionField.SUBJECT,
                    operator=ConditionOperator.CONTAINS,
                    value="Update",
                )
            ],
        )
        rule_set = _make_rule_set(low_priority_rule, high_priority_rule)

        categorizer = EmailCategorizer()
        result = categorizer.categorize_email(email, rule_set)

        assert result.primary_category.category_name == "Important Updates"

    def test_multiple_matching_rules_others_become_secondary(self):
        """Test non-primary matching rules become secondary categories."""
        email = _make_email()
        rule_high = _make_rule(
            rule_id="rule_high",
            priority=20,
            action_target="Updates",
            conditions=[
                _make_condition(
                    field=ConditionField.SUBJECT,
                    operator=ConditionOperator.CONTAINS,
                    value="Update",
                )
            ],
        )
        rule_mid = _make_rule(
            rule_id="rule_mid",
            priority=10,
            action_target="Team Comms",
            conditions=[
                _make_condition(
                    field=ConditionField.BODY,
                    operator=ConditionOperator.CONTAINS,
                    value="team",
                )
            ],
        )
        rule_low = _make_rule(
            rule_id="rule_low",
            priority=5,
            action_target="Example Domain",
            conditions=[
                _make_condition(
                    field=ConditionField.SENDER_DOMAIN,
                    operator=ConditionOperator.EQUALS,
                    value="example.com",
                )
            ],
        )
        rule_set = _make_rule_set(rule_high, rule_mid, rule_low)

        categorizer = EmailCategorizer()
        result = categorizer.categorize_email(email, rule_set)

        assert result.primary_category.category_name == "Updates"
        assert len(result.secondary_categories) == 2
        secondary_names = [s.category_name for s in result.secondary_categories]
        assert "Team Comms" in secondary_names
        assert "Example Domain" in secondary_names

    def test_matched_rules_ids_are_recorded(self):
        """Test all matched rule IDs are recorded on the result."""
        email = _make_email()
        rule1 = _make_rule(
            rule_id="rule_aaa",
            priority=10,
            action_target="Cat A",
            conditions=[
                _make_condition(
                    field=ConditionField.SENDER_DOMAIN,
                    operator=ConditionOperator.EQUALS,
                    value="example.com",
                )
            ],
        )
        rule2 = _make_rule(
            rule_id="rule_bbb",
            priority=5,
            action_target="Cat B",
            conditions=[
                _make_condition(
                    field=ConditionField.SUBJECT,
                    operator=ConditionOperator.CONTAINS,
                    value="Update",
                )
            ],
        )
        rule_set = _make_rule_set(rule1, rule2)

        categorizer = EmailCategorizer()
        result = categorizer.categorize_email(email, rule_set)

        assert "rule_aaa" in result.matched_rules
        assert "rule_bbb" in result.matched_rules
        assert len(result.matched_rules) == 2

    def test_disabled_rules_are_skipped(self):
        """Test disabled rules do not produce matches."""
        email = _make_email()
        disabled_rule = _make_rule(
            rule_id="rule_disabled",
            priority=100,
            action_target="Should Not Match",
            enabled=False,
            conditions=[
                _make_condition(
                    field=ConditionField.SENDER_DOMAIN,
                    operator=ConditionOperator.EQUALS,
                    value="example.com",
                )
            ],
        )
        rule_set = _make_rule_set(disabled_rule)

        categorizer = EmailCategorizer()
        result = categorizer.categorize_email(email, rule_set)

        assert result.is_uncategorized is True

    def test_empty_rule_set_returns_uncategorized(self):
        """Test email against empty rule set is uncategorized."""
        email = _make_email()
        rule_set = _make_rule_set()

        categorizer = EmailCategorizer()
        result = categorizer.categorize_email(email, rule_set)

        assert result.is_uncategorized is True


# =============================================================================
# Confidence Scoring
# =============================================================================


class TestConfidenceScoring:
    """Test confidence calculation based on rule priority."""

    def test_single_rule_confidence_normalized(self):
        """Test confidence is normalized from rule priority (0-1 range)."""
        email = _make_email()
        rule = _make_rule(
            rule_id="rule_one",
            priority=50,
            action_target="Cat A",
            conditions=[
                _make_condition(
                    field=ConditionField.SENDER_DOMAIN,
                    operator=ConditionOperator.EQUALS,
                    value="example.com",
                )
            ],
        )
        rule_set = _make_rule_set(rule)

        categorizer = EmailCategorizer()
        result = categorizer.categorize_email(email, rule_set)

        assert 0.0 <= result.primary_category.confidence <= 1.0

    def test_higher_priority_yields_higher_confidence(self):
        """Test higher-priority rules produce higher confidence scores."""
        email = _make_email()
        rule_high = _make_rule(
            rule_id="rule_high",
            priority=100,
            action_target="High Priority Cat",
            conditions=[
                _make_condition(
                    field=ConditionField.SENDER_DOMAIN,
                    operator=ConditionOperator.EQUALS,
                    value="example.com",
                )
            ],
        )
        rule_low = _make_rule(
            rule_id="rule_low",
            priority=10,
            action_target="Low Priority Cat",
            conditions=[
                _make_condition(
                    field=ConditionField.SUBJECT,
                    operator=ConditionOperator.CONTAINS,
                    value="Update",
                )
            ],
        )
        rule_set = _make_rule_set(rule_high, rule_low)

        categorizer = EmailCategorizer()
        result = categorizer.categorize_email(email, rule_set)

        # Primary (highest priority) should have higher confidence than secondary
        assert result.primary_category.confidence > result.secondary_categories[0].confidence

    def test_zero_priority_produces_positive_confidence(self):
        """Test zero-priority rule still produces a small positive confidence."""
        email = _make_email()
        rule = _make_rule(
            rule_id="rule_zero",
            priority=0,
            action_target="Zero Priority",
            conditions=[
                _make_condition(
                    field=ConditionField.SENDER_DOMAIN,
                    operator=ConditionOperator.EQUALS,
                    value="example.com",
                )
            ],
        )
        rule_set = _make_rule_set(rule)

        categorizer = EmailCategorizer()
        result = categorizer.categorize_email(email, rule_set)

        # Even zero-priority rules should get a baseline confidence > 0
        assert result.primary_category.confidence > 0.0

    def test_confidence_never_exceeds_one(self):
        """Test confidence is capped at 1.0 regardless of priority magnitude."""
        email = _make_email()
        rule = _make_rule(
            rule_id="rule_extreme",
            priority=99999,
            action_target="Extreme Priority",
            conditions=[
                _make_condition(
                    field=ConditionField.SENDER_DOMAIN,
                    operator=ConditionOperator.EQUALS,
                    value="example.com",
                )
            ],
        )
        rule_set = _make_rule_set(rule)

        categorizer = EmailCategorizer()
        result = categorizer.categorize_email(email, rule_set)

        assert result.primary_category.confidence <= 1.0

    def test_confidence_source_is_rule_id(self):
        """Test the source on a category assignment is the rule ID."""
        email = _make_email()
        rule = _make_rule(
            rule_id="rule_src_check",
            priority=10,
            action_target="Source Check",
            conditions=[
                _make_condition(
                    field=ConditionField.SENDER_DOMAIN,
                    operator=ConditionOperator.EQUALS,
                    value="example.com",
                )
            ],
        )
        rule_set = _make_rule_set(rule)

        categorizer = EmailCategorizer()
        result = categorizer.categorize_email(email, rule_set)

        assert result.primary_category.source == "rule_src_check"


# =============================================================================
# Duplicate Category Handling
# =============================================================================


class TestDuplicateCategoryHandling:
    """Test behavior when multiple rules map to the same category target."""

    def test_duplicate_category_targets_deduplicated(self):
        """Test multiple rules targeting the same category are deduplicated."""
        email = _make_email()
        rule1 = _make_rule(
            rule_id="rule_domain",
            priority=20,
            action_target="Newsletters",
            conditions=[
                _make_condition(
                    field=ConditionField.SENDER_DOMAIN,
                    operator=ConditionOperator.EQUALS,
                    value="example.com",
                )
            ],
        )
        rule2 = _make_rule(
            rule_id="rule_subject",
            priority=10,
            action_target="Newsletters",
            conditions=[
                _make_condition(
                    field=ConditionField.SUBJECT,
                    operator=ConditionOperator.CONTAINS,
                    value="Update",
                )
            ],
        )
        rule_set = _make_rule_set(rule1, rule2)

        categorizer = EmailCategorizer()
        result = categorizer.categorize_email(email, rule_set)

        # Both rules match but same category target, so primary only, no secondaries
        assert result.primary_category.category_name == "Newsletters"
        # The secondary list should NOT contain duplicates of the primary
        secondary_names = [s.category_name for s in result.secondary_categories]
        assert "Newsletters" not in secondary_names
        # Both rule IDs should still be recorded
        assert "rule_domain" in result.matched_rules
        assert "rule_subject" in result.matched_rules


# =============================================================================
# categorize_corpus — Batch Categorization
# =============================================================================


class TestCategorizeCorpus:
    """Test categorize_corpus for batch email categorization."""

    def test_categorize_empty_corpus(self):
        """Test categorizing an empty corpus."""
        corpus = _make_corpus([])
        rule_set = _make_rule_set(
            _make_rule(action_target="Cat A"),
        )

        categorizer = EmailCategorizer()
        report = categorizer.categorize_corpus(corpus, rule_set)

        assert isinstance(report, CategorizationReport)
        assert report.total_emails == 0
        assert report.categorized_count == 0
        assert report.uncategorized_count == 0
        assert report.coverage_percentage == 0.0
        assert report.categorizations == []
        assert report.categories_used == {}

    def test_categorize_all_emails_matched(self):
        """Test corpus where all emails match a rule."""
        emails = [_make_email(id=f"email_{i:03d}") for i in range(5)]
        corpus = _make_corpus(emails)
        rule = _make_rule(
            rule_id="rule_all",
            action_target="Example Domain Emails",
            conditions=[
                _make_condition(
                    field=ConditionField.SENDER_DOMAIN,
                    operator=ConditionOperator.EQUALS,
                    value="example.com",
                )
            ],
        )
        rule_set = _make_rule_set(rule)

        categorizer = EmailCategorizer()
        report = categorizer.categorize_corpus(corpus, rule_set)

        assert report.total_emails == 5
        assert report.categorized_count == 5
        assert report.uncategorized_count == 0
        assert report.coverage_percentage == 100.0
        assert len(report.categorizations) == 5
        assert "Example Domain Emails" in report.categories_used
        assert report.categories_used["Example Domain Emails"] == 5

    def test_categorize_mixed_matched_and_unmatched(self):
        """Test corpus with both matched and unmatched emails."""
        emails = [
            _make_email(
                id="email_match_1",
                sender_domain="example.com",
                sender_email="a@example.com",
            ),
            _make_email(
                id="email_match_2",
                sender_domain="example.com",
                sender_email="b@example.com",
            ),
            _make_email(
                id="email_nomatch",
                sender_domain="other.com",
                sender_email="c@other.com",
            ),
        ]
        corpus = _make_corpus(emails)
        rule = _make_rule(
            action_target="Example Emails",
            conditions=[
                _make_condition(
                    field=ConditionField.SENDER_DOMAIN,
                    operator=ConditionOperator.EQUALS,
                    value="example.com",
                )
            ],
        )
        rule_set = _make_rule_set(rule)

        categorizer = EmailCategorizer()
        report = categorizer.categorize_corpus(corpus, rule_set)

        assert report.total_emails == 3
        assert report.categorized_count == 2
        assert report.uncategorized_count == 1
        assert abs(report.coverage_percentage - 66.67) < 0.01

    def test_categories_used_counts_correctly(self):
        """Test categories_used dictionary has correct per-category counts."""
        emails = [
            _make_email(
                id="email_1",
                sender_domain="news.com",
                sender_email="a@news.com",
                subject="Daily Digest",
            ),
            _make_email(
                id="email_2",
                sender_domain="news.com",
                sender_email="b@news.com",
                subject="Breaking News",
            ),
            _make_email(
                id="email_3",
                sender_domain="shop.com",
                sender_email="c@shop.com",
                subject="Your Order",
            ),
        ]
        corpus = _make_corpus(emails)
        rule_news = _make_rule(
            rule_id="rule_news",
            priority=10,
            action_target="News",
            conditions=[
                _make_condition(
                    field=ConditionField.SENDER_DOMAIN,
                    operator=ConditionOperator.EQUALS,
                    value="news.com",
                )
            ],
        )
        rule_shopping = _make_rule(
            rule_id="rule_shopping",
            priority=10,
            action_target="Shopping",
            conditions=[
                _make_condition(
                    field=ConditionField.SENDER_DOMAIN,
                    operator=ConditionOperator.EQUALS,
                    value="shop.com",
                )
            ],
        )
        rule_set = _make_rule_set(rule_news, rule_shopping)

        categorizer = EmailCategorizer()
        report = categorizer.categorize_corpus(corpus, rule_set)

        assert report.categories_used["News"] == 2
        assert report.categories_used["Shopping"] == 1

    def test_rule_set_version_recorded_in_report(self):
        """Test the rule set version is captured in the report."""
        emails = [_make_email(id="email_001")]
        corpus = _make_corpus(emails)
        rule_set = RuleSet(
            rules=[_make_rule()],
            version="2.5",
        )

        categorizer = EmailCategorizer()
        report = categorizer.categorize_corpus(corpus, rule_set)

        assert report.rule_set_version == "2.5"

    def test_each_email_in_corpus_gets_categorization(self):
        """Test every email in the corpus has a corresponding categorization."""
        emails = [_make_email(id=f"email_{i:03d}") for i in range(10)]
        corpus = _make_corpus(emails)
        rule_set = _make_rule_set(_make_rule())

        categorizer = EmailCategorizer()
        report = categorizer.categorize_corpus(corpus, rule_set)

        result_ids = {c.email_id for c in report.categorizations}
        expected_ids = {f"email_{i:03d}" for i in range(10)}
        assert result_ids == expected_ids


# =============================================================================
# Progress Callback
# =============================================================================


class TestProgressCallback:
    """Test progress_callback support in categorize_corpus."""

    def test_progress_callback_is_called(self):
        """Test progress callback is invoked during categorization."""
        emails = [_make_email(id=f"email_{i:03d}") for i in range(5)]
        corpus = _make_corpus(emails)
        rule_set = _make_rule_set(_make_rule())

        callback = MagicMock()
        categorizer = EmailCategorizer()
        categorizer.categorize_corpus(corpus, rule_set, progress_callback=callback)

        assert callback.call_count > 0

    def test_progress_callback_called_per_email(self):
        """Test progress callback is called once per email."""
        emails = [_make_email(id=f"email_{i:03d}") for i in range(7)]
        corpus = _make_corpus(emails)
        rule_set = _make_rule_set(_make_rule())

        callback = MagicMock()
        categorizer = EmailCategorizer()
        categorizer.categorize_corpus(corpus, rule_set, progress_callback=callback)

        assert callback.call_count == 7

    def test_progress_callback_receives_index_and_total(self):
        """Test progress callback receives (current_index, total) arguments."""
        emails = [_make_email(id=f"email_{i:03d}") for i in range(3)]
        corpus = _make_corpus(emails)
        rule_set = _make_rule_set(_make_rule())

        callback = MagicMock()
        categorizer = EmailCategorizer()
        categorizer.categorize_corpus(corpus, rule_set, progress_callback=callback)

        # Check first call: (1, 3) and last call: (3, 3)
        first_call_args = callback.call_args_list[0][0]
        last_call_args = callback.call_args_list[-1][0]
        assert first_call_args == (1, 3)
        assert last_call_args == (3, 3)

    def test_no_progress_callback_is_fine(self):
        """Test categorization works fine without a progress callback."""
        emails = [_make_email(id="email_001")]
        corpus = _make_corpus(emails)
        rule_set = _make_rule_set(_make_rule())

        categorizer = EmailCategorizer()
        report = categorizer.categorize_corpus(corpus, rule_set)

        assert report.total_emails == 1


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_single_email_corpus(self):
        """Test categorizing a corpus with exactly one email."""
        corpus = _make_corpus([_make_email(id="solo")])
        rule_set = _make_rule_set(_make_rule(action_target="Solo Category"))

        categorizer = EmailCategorizer()
        report = categorizer.categorize_corpus(corpus, rule_set)

        assert report.total_emails == 1
        assert report.categorized_count == 1
        assert report.coverage_percentage == 100.0

    def test_large_number_of_rules(self):
        """Test with many rules to ensure no performance regression."""
        email = _make_email()
        rules = [
            _make_rule(
                rule_id=f"rule_{i:03d}",
                priority=i,
                action_target=f"Category {i}",
                conditions=[
                    _make_condition(
                        field=ConditionField.SENDER_DOMAIN,
                        operator=ConditionOperator.EQUALS,
                        value=f"domain{i}.com",
                    )
                ],
            )
            for i in range(100)
        ]
        # Add one that actually matches
        matching_rule = _make_rule(
            rule_id="rule_match",
            priority=999,
            action_target="Matched",
            conditions=[
                _make_condition(
                    field=ConditionField.SENDER_DOMAIN,
                    operator=ConditionOperator.EQUALS,
                    value="example.com",
                )
            ],
        )
        rules.append(matching_rule)
        rule_set = _make_rule_set(*rules)

        categorizer = EmailCategorizer()
        result = categorizer.categorize_email(email, rule_set)

        assert result.primary_category.category_name == "Matched"

    def test_all_emails_uncategorized(self):
        """Test corpus where no emails match any rules."""
        emails = [
            _make_email(
                id=f"email_{i:03d}",
                sender_domain="unknown.com",
                sender_email=f"u{i}@unknown.com",
            )
            for i in range(3)
        ]
        corpus = _make_corpus(emails)
        rule = _make_rule(
            conditions=[
                _make_condition(
                    field=ConditionField.SENDER_DOMAIN,
                    operator=ConditionOperator.EQUALS,
                    value="example.com",
                )
            ],
        )
        rule_set = _make_rule_set(rule)

        categorizer = EmailCategorizer()
        report = categorizer.categorize_corpus(corpus, rule_set)

        assert report.categorized_count == 0
        assert report.uncategorized_count == 3
        assert report.coverage_percentage == 0.0
        assert all(c.is_uncategorized for c in report.categorizations)

    def test_non_categorize_action_types_ignored_for_category_assignment(self):
        """Test rules with non-CATEGORIZE actions still contribute to categorization."""
        email = _make_email()
        rule = _make_rule(
            rule_id="rule_tag",
            priority=10,
            action_target="Important",
            action_type=RuleActionType.TAG,
            conditions=[
                _make_condition(
                    field=ConditionField.SENDER_DOMAIN,
                    operator=ConditionOperator.EQUALS,
                    value="example.com",
                )
            ],
        )
        rule_set = _make_rule_set(rule)

        categorizer = EmailCategorizer()
        result = categorizer.categorize_email(email, rule_set)

        # Non-CATEGORIZE rules should still assign the target as category
        assert result.primary_category.category_name == "Important"
        assert result.is_uncategorized is False
