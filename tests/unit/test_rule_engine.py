"""
Unit tests for RuleEngine (Phase 3, Item 3.2).

Tests rule evaluation against emails: single conditions, AND/OR logic,
short-circuit evaluation, all operators, all fields, case sensitivity,
and RuleSet evaluation with priority sorting.

TDD: These tests are written first, implementation follows.
"""

from datetime import datetime

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
from src.rules.engine import RuleEngine

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
        "body_text": "Hi team, here is the weekly status report. Please review.",
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
) -> CategoryRule:
    if conditions is None:
        conditions = [_make_condition()]
    return CategoryRule(
        rule_id=rule_id,
        name=name,
        conditions=conditions,
        action=RuleAction(
            action_type=RuleActionType.CATEGORIZE,
            target="Test Category",
        ),
        logic=logic,
        priority=priority,
        enabled=enabled,
    )


# =============================================================================
# RuleEngine instantiation
# =============================================================================


class TestRuleEngineInit:
    """Test RuleEngine construction."""

    def test_creates_engine(self):
        engine = RuleEngine()
        assert engine is not None


# =============================================================================
# evaluate_condition: CONTAINS operator
# =============================================================================


class TestEvaluateConditionContains:
    """Test the CONTAINS operator across different fields."""

    def test_subject_contains_match(self):
        engine = RuleEngine()
        cond = _make_condition(
            field=ConditionField.SUBJECT,
            operator=ConditionOperator.CONTAINS,
            value="Team Update",
        )
        email = _make_email(subject="Weekly Team Update")
        assert engine.evaluate_condition(cond, email) is True

    def test_subject_contains_no_match(self):
        engine = RuleEngine()
        cond = _make_condition(
            field=ConditionField.SUBJECT,
            operator=ConditionOperator.CONTAINS,
            value="Budget Report",
        )
        email = _make_email(subject="Weekly Team Update")
        assert engine.evaluate_condition(cond, email) is False

    def test_body_contains_match(self):
        engine = RuleEngine()
        cond = _make_condition(
            field=ConditionField.BODY,
            operator=ConditionOperator.CONTAINS,
            value="status report",
        )
        email = _make_email(body_text="Here is the weekly status report.")
        assert engine.evaluate_condition(cond, email) is True

    def test_body_contains_no_match(self):
        engine = RuleEngine()
        cond = _make_condition(
            field=ConditionField.BODY,
            operator=ConditionOperator.CONTAINS,
            value="invoice",
        )
        email = _make_email(body_text="Here is the weekly status report.")
        assert engine.evaluate_condition(cond, email) is False

    def test_sender_email_contains(self):
        engine = RuleEngine()
        cond = _make_condition(
            field=ConditionField.SENDER_EMAIL,
            operator=ConditionOperator.CONTAINS,
            value="alice",
        )
        email = _make_email(sender_email="alice@example.com")
        assert engine.evaluate_condition(cond, email) is True

    def test_sender_name_contains(self):
        engine = RuleEngine()
        cond = _make_condition(
            field=ConditionField.SENDER_NAME,
            operator=ConditionOperator.CONTAINS,
            value="Smith",
        )
        email = _make_email(sender_name="Alice Smith")
        assert engine.evaluate_condition(cond, email) is True

    def test_sender_domain_contains(self):
        engine = RuleEngine()
        cond = _make_condition(
            field=ConditionField.SENDER_DOMAIN,
            operator=ConditionOperator.CONTAINS,
            value="example",
        )
        email = _make_email(sender_domain="example.com")
        assert engine.evaluate_condition(cond, email) is True

    def test_recipient_email_contains(self):
        engine = RuleEngine()
        cond = _make_condition(
            field=ConditionField.RECIPIENT_EMAIL,
            operator=ConditionOperator.CONTAINS,
            value="bob",
        )
        email = _make_email(recipient_email="bob@test.org")
        assert engine.evaluate_condition(cond, email) is True

    def test_contains_case_insensitive_by_default(self):
        engine = RuleEngine()
        cond = _make_condition(
            field=ConditionField.SUBJECT,
            operator=ConditionOperator.CONTAINS,
            value="team update",
            case_sensitive=False,
        )
        email = _make_email(subject="Weekly TEAM UPDATE")
        assert engine.evaluate_condition(cond, email) is True

    def test_contains_case_sensitive(self):
        engine = RuleEngine()
        cond = _make_condition(
            field=ConditionField.SUBJECT,
            operator=ConditionOperator.CONTAINS,
            value="team update",
            case_sensitive=True,
        )
        email = _make_email(subject="Weekly TEAM UPDATE")
        assert engine.evaluate_condition(cond, email) is False


# =============================================================================
# evaluate_condition: EQUALS operator
# =============================================================================


class TestEvaluateConditionEquals:
    """Test the EQUALS operator."""

    def test_sender_domain_equals_match(self):
        engine = RuleEngine()
        cond = _make_condition(
            field=ConditionField.SENDER_DOMAIN,
            operator=ConditionOperator.EQUALS,
            value="example.com",
        )
        email = _make_email(sender_domain="example.com")
        assert engine.evaluate_condition(cond, email) is True

    def test_sender_domain_equals_no_match(self):
        engine = RuleEngine()
        cond = _make_condition(
            field=ConditionField.SENDER_DOMAIN,
            operator=ConditionOperator.EQUALS,
            value="other.com",
        )
        email = _make_email(sender_domain="example.com")
        assert engine.evaluate_condition(cond, email) is False

    def test_sender_email_equals(self):
        engine = RuleEngine()
        cond = _make_condition(
            field=ConditionField.SENDER_EMAIL,
            operator=ConditionOperator.EQUALS,
            value="alice@example.com",
        )
        email = _make_email(sender_email="alice@example.com")
        assert engine.evaluate_condition(cond, email) is True

    def test_equals_case_insensitive(self):
        engine = RuleEngine()
        cond = _make_condition(
            field=ConditionField.SENDER_EMAIL,
            operator=ConditionOperator.EQUALS,
            value="ALICE@EXAMPLE.COM",
            case_sensitive=False,
        )
        email = _make_email(sender_email="alice@example.com")
        assert engine.evaluate_condition(cond, email) is True

    def test_equals_case_sensitive(self):
        engine = RuleEngine()
        cond = _make_condition(
            field=ConditionField.SENDER_EMAIL,
            operator=ConditionOperator.EQUALS,
            value="ALICE@EXAMPLE.COM",
            case_sensitive=True,
        )
        email = _make_email(sender_email="alice@example.com")
        assert engine.evaluate_condition(cond, email) is False

    def test_has_attachment_equals_true(self):
        engine = RuleEngine()
        cond = _make_condition(
            field=ConditionField.HAS_ATTACHMENT,
            operator=ConditionOperator.EQUALS,
            value="true",
        )
        email = _make_email(has_attachments=True)
        assert engine.evaluate_condition(cond, email) is True

    def test_has_attachment_equals_false(self):
        engine = RuleEngine()
        cond = _make_condition(
            field=ConditionField.HAS_ATTACHMENT,
            operator=ConditionOperator.EQUALS,
            value="false",
        )
        email = _make_email(has_attachments=False)
        assert engine.evaluate_condition(cond, email) is True

    def test_has_attachment_equals_mismatch(self):
        engine = RuleEngine()
        cond = _make_condition(
            field=ConditionField.HAS_ATTACHMENT,
            operator=ConditionOperator.EQUALS,
            value="true",
        )
        email = _make_email(has_attachments=False)
        assert engine.evaluate_condition(cond, email) is False


# =============================================================================
# evaluate_condition: STARTS_WITH operator
# =============================================================================


class TestEvaluateConditionStartsWith:
    """Test the STARTS_WITH operator."""

    def test_subject_starts_with_match(self):
        engine = RuleEngine()
        cond = _make_condition(
            field=ConditionField.SUBJECT,
            operator=ConditionOperator.STARTS_WITH,
            value="Weekly",
        )
        email = _make_email(subject="Weekly Team Update")
        assert engine.evaluate_condition(cond, email) is True

    def test_subject_starts_with_no_match(self):
        engine = RuleEngine()
        cond = _make_condition(
            field=ConditionField.SUBJECT,
            operator=ConditionOperator.STARTS_WITH,
            value="Monthly",
        )
        email = _make_email(subject="Weekly Team Update")
        assert engine.evaluate_condition(cond, email) is False

    def test_starts_with_case_insensitive(self):
        engine = RuleEngine()
        cond = _make_condition(
            field=ConditionField.SUBJECT,
            operator=ConditionOperator.STARTS_WITH,
            value="weekly",
            case_sensitive=False,
        )
        email = _make_email(subject="WEEKLY Team Update")
        assert engine.evaluate_condition(cond, email) is True

    def test_starts_with_case_sensitive(self):
        engine = RuleEngine()
        cond = _make_condition(
            field=ConditionField.SUBJECT,
            operator=ConditionOperator.STARTS_WITH,
            value="weekly",
            case_sensitive=True,
        )
        email = _make_email(subject="WEEKLY Team Update")
        assert engine.evaluate_condition(cond, email) is False


# =============================================================================
# evaluate_condition: ENDS_WITH operator
# =============================================================================


class TestEvaluateConditionEndsWith:
    """Test the ENDS_WITH operator."""

    def test_subject_ends_with_match(self):
        engine = RuleEngine()
        cond = _make_condition(
            field=ConditionField.SUBJECT,
            operator=ConditionOperator.ENDS_WITH,
            value="Update",
        )
        email = _make_email(subject="Weekly Team Update")
        assert engine.evaluate_condition(cond, email) is True

    def test_subject_ends_with_no_match(self):
        engine = RuleEngine()
        cond = _make_condition(
            field=ConditionField.SUBJECT,
            operator=ConditionOperator.ENDS_WITH,
            value="Report",
        )
        email = _make_email(subject="Weekly Team Update")
        assert engine.evaluate_condition(cond, email) is False

    def test_ends_with_case_insensitive(self):
        engine = RuleEngine()
        cond = _make_condition(
            field=ConditionField.SUBJECT,
            operator=ConditionOperator.ENDS_WITH,
            value="update",
            case_sensitive=False,
        )
        email = _make_email(subject="Weekly Team UPDATE")
        assert engine.evaluate_condition(cond, email) is True

    def test_sender_domain_ends_with(self):
        engine = RuleEngine()
        cond = _make_condition(
            field=ConditionField.SENDER_DOMAIN,
            operator=ConditionOperator.ENDS_WITH,
            value=".com",
        )
        email = _make_email(sender_domain="example.com")
        assert engine.evaluate_condition(cond, email) is True


# =============================================================================
# evaluate_condition: MATCHES_REGEX operator
# =============================================================================


class TestEvaluateConditionMatchesRegex:
    """Test the MATCHES_REGEX operator."""

    def test_subject_regex_match(self):
        engine = RuleEngine()
        cond = _make_condition(
            field=ConditionField.SUBJECT,
            operator=ConditionOperator.MATCHES_REGEX,
            value=r"Invoice\s*#\d+",
        )
        email = _make_email(subject="Invoice #12345 for your order")
        assert engine.evaluate_condition(cond, email) is True

    def test_subject_regex_no_match(self):
        engine = RuleEngine()
        cond = _make_condition(
            field=ConditionField.SUBJECT,
            operator=ConditionOperator.MATCHES_REGEX,
            value=r"Invoice\s*#\d+",
        )
        email = _make_email(subject="Weekly Team Update")
        assert engine.evaluate_condition(cond, email) is False

    def test_regex_case_insensitive(self):
        engine = RuleEngine()
        cond = _make_condition(
            field=ConditionField.SUBJECT,
            operator=ConditionOperator.MATCHES_REGEX,
            value=r"invoice\s*#\d+",
            case_sensitive=False,
        )
        email = _make_email(subject="INVOICE #999")
        assert engine.evaluate_condition(cond, email) is True

    def test_regex_case_sensitive(self):
        engine = RuleEngine()
        cond = _make_condition(
            field=ConditionField.SUBJECT,
            operator=ConditionOperator.MATCHES_REGEX,
            value=r"invoice\s*#\d+",
            case_sensitive=True,
        )
        email = _make_email(subject="INVOICE #999")
        assert engine.evaluate_condition(cond, email) is False

    def test_regex_invalid_pattern_returns_false(self):
        """Invalid regex patterns should not raise, just return False."""
        engine = RuleEngine()
        cond = _make_condition(
            field=ConditionField.SUBJECT,
            operator=ConditionOperator.MATCHES_REGEX,
            value=r"[invalid(regex",
        )
        email = _make_email(subject="anything")
        assert engine.evaluate_condition(cond, email) is False

    def test_body_regex_match(self):
        engine = RuleEngine()
        cond = _make_condition(
            field=ConditionField.BODY,
            operator=ConditionOperator.MATCHES_REGEX,
            value=r"\bstatus\s+report\b",
        )
        email = _make_email(body_text="Please review the status report attached.")
        assert engine.evaluate_condition(cond, email) is True


# =============================================================================
# evaluate_condition: IN_LIST operator
# =============================================================================


class TestEvaluateConditionInList:
    """Test the IN_LIST operator (comma-separated values)."""

    def test_sender_domain_in_list_match(self):
        engine = RuleEngine()
        cond = _make_condition(
            field=ConditionField.SENDER_DOMAIN,
            operator=ConditionOperator.IN_LIST,
            value="example.com,test.org,demo.net",
        )
        email = _make_email(sender_domain="test.org")
        assert engine.evaluate_condition(cond, email) is True

    def test_sender_domain_in_list_no_match(self):
        engine = RuleEngine()
        cond = _make_condition(
            field=ConditionField.SENDER_DOMAIN,
            operator=ConditionOperator.IN_LIST,
            value="example.com,test.org,demo.net",
        )
        email = _make_email(sender_domain="other.com")
        assert engine.evaluate_condition(cond, email) is False

    def test_in_list_case_insensitive(self):
        engine = RuleEngine()
        cond = _make_condition(
            field=ConditionField.SENDER_DOMAIN,
            operator=ConditionOperator.IN_LIST,
            value="Example.COM,Test.ORG",
            case_sensitive=False,
        )
        email = _make_email(sender_domain="example.com")
        assert engine.evaluate_condition(cond, email) is True

    def test_in_list_case_sensitive(self):
        engine = RuleEngine()
        cond = _make_condition(
            field=ConditionField.SENDER_DOMAIN,
            operator=ConditionOperator.IN_LIST,
            value="Example.COM,Test.ORG",
            case_sensitive=True,
        )
        email = _make_email(sender_domain="example.com")
        assert engine.evaluate_condition(cond, email) is False

    def test_in_list_whitespace_trimmed(self):
        """Values in list should have whitespace trimmed."""
        engine = RuleEngine()
        cond = _make_condition(
            field=ConditionField.SENDER_DOMAIN,
            operator=ConditionOperator.IN_LIST,
            value="example.com , test.org , demo.net",
        )
        email = _make_email(sender_domain="test.org")
        assert engine.evaluate_condition(cond, email) is True

    def test_in_list_single_value(self):
        engine = RuleEngine()
        cond = _make_condition(
            field=ConditionField.SENDER_EMAIL,
            operator=ConditionOperator.IN_LIST,
            value="alice@example.com",
        )
        email = _make_email(sender_email="alice@example.com")
        assert engine.evaluate_condition(cond, email) is True

    def test_sender_email_in_list(self):
        engine = RuleEngine()
        cond = _make_condition(
            field=ConditionField.SENDER_EMAIL,
            operator=ConditionOperator.IN_LIST,
            value="alice@example.com,bob@test.org,charlie@demo.net",
        )
        email = _make_email(sender_email="bob@test.org")
        assert engine.evaluate_condition(cond, email) is True


# =============================================================================
# evaluate_condition: NOT_CONTAINS operator
# =============================================================================


class TestEvaluateConditionNotContains:
    """Test the NOT_CONTAINS operator."""

    def test_not_contains_match(self):
        engine = RuleEngine()
        cond = _make_condition(
            field=ConditionField.SUBJECT,
            operator=ConditionOperator.NOT_CONTAINS,
            value="unsubscribe",
        )
        email = _make_email(subject="Weekly Team Update")
        assert engine.evaluate_condition(cond, email) is True

    def test_not_contains_no_match(self):
        engine = RuleEngine()
        cond = _make_condition(
            field=ConditionField.SUBJECT,
            operator=ConditionOperator.NOT_CONTAINS,
            value="Update",
        )
        email = _make_email(subject="Weekly Team Update")
        assert engine.evaluate_condition(cond, email) is False

    def test_not_contains_case_insensitive(self):
        engine = RuleEngine()
        cond = _make_condition(
            field=ConditionField.SUBJECT,
            operator=ConditionOperator.NOT_CONTAINS,
            value="update",
            case_sensitive=False,
        )
        email = _make_email(subject="Weekly Team UPDATE")
        assert engine.evaluate_condition(cond, email) is False

    def test_not_contains_body(self):
        engine = RuleEngine()
        cond = _make_condition(
            field=ConditionField.BODY,
            operator=ConditionOperator.NOT_CONTAINS,
            value="confidential",
        )
        email = _make_email(body_text="This is a public announcement.")
        assert engine.evaluate_condition(cond, email) is True


# =============================================================================
# evaluate_condition: NOT_EQUALS operator
# =============================================================================


class TestEvaluateConditionNotEquals:
    """Test the NOT_EQUALS operator."""

    def test_not_equals_match(self):
        engine = RuleEngine()
        cond = _make_condition(
            field=ConditionField.SENDER_DOMAIN,
            operator=ConditionOperator.NOT_EQUALS,
            value="spam.com",
        )
        email = _make_email(sender_domain="example.com")
        assert engine.evaluate_condition(cond, email) is True

    def test_not_equals_no_match(self):
        engine = RuleEngine()
        cond = _make_condition(
            field=ConditionField.SENDER_DOMAIN,
            operator=ConditionOperator.NOT_EQUALS,
            value="example.com",
        )
        email = _make_email(sender_domain="example.com")
        assert engine.evaluate_condition(cond, email) is False

    def test_not_equals_case_insensitive(self):
        engine = RuleEngine()
        cond = _make_condition(
            field=ConditionField.SENDER_DOMAIN,
            operator=ConditionOperator.NOT_EQUALS,
            value="EXAMPLE.COM",
            case_sensitive=False,
        )
        email = _make_email(sender_domain="example.com")
        assert engine.evaluate_condition(cond, email) is False

    def test_not_equals_case_sensitive(self):
        engine = RuleEngine()
        cond = _make_condition(
            field=ConditionField.SENDER_DOMAIN,
            operator=ConditionOperator.NOT_EQUALS,
            value="EXAMPLE.COM",
            case_sensitive=True,
        )
        email = _make_email(sender_domain="example.com")
        assert engine.evaluate_condition(cond, email) is True


# =============================================================================
# evaluate_condition: HAS_ATTACHMENT field
# =============================================================================


class TestEvaluateConditionHasAttachment:
    """Test HAS_ATTACHMENT field handling with various operators."""

    def test_has_attachment_contains_true(self):
        """CONTAINS on has_attachment checks string 'true'/'false'."""
        engine = RuleEngine()
        cond = _make_condition(
            field=ConditionField.HAS_ATTACHMENT,
            operator=ConditionOperator.CONTAINS,
            value="true",
        )
        email = _make_email(has_attachments=True)
        assert engine.evaluate_condition(cond, email) is True

    def test_has_attachment_contains_false(self):
        engine = RuleEngine()
        cond = _make_condition(
            field=ConditionField.HAS_ATTACHMENT,
            operator=ConditionOperator.CONTAINS,
            value="true",
        )
        email = _make_email(has_attachments=False)
        assert engine.evaluate_condition(cond, email) is False


# =============================================================================
# evaluate_condition: Recipient email None
# =============================================================================


class TestEvaluateConditionNullableFields:
    """Test fields that can be None (recipient_email)."""

    def test_recipient_email_none_contains(self):
        """If recipient_email is None, contains should return False."""
        engine = RuleEngine()
        cond = _make_condition(
            field=ConditionField.RECIPIENT_EMAIL,
            operator=ConditionOperator.CONTAINS,
            value="bob",
        )
        email = _make_email(recipient_email=None)
        assert engine.evaluate_condition(cond, email) is False

    def test_recipient_email_none_equals(self):
        engine = RuleEngine()
        cond = _make_condition(
            field=ConditionField.RECIPIENT_EMAIL,
            operator=ConditionOperator.EQUALS,
            value="bob@test.org",
        )
        email = _make_email(recipient_email=None)
        assert engine.evaluate_condition(cond, email) is False

    def test_recipient_email_none_not_equals(self):
        """NOT_EQUALS with None field should return True (None != anything)."""
        engine = RuleEngine()
        cond = _make_condition(
            field=ConditionField.RECIPIENT_EMAIL,
            operator=ConditionOperator.NOT_EQUALS,
            value="bob@test.org",
        )
        email = _make_email(recipient_email=None)
        assert engine.evaluate_condition(cond, email) is True

    def test_recipient_email_none_not_contains(self):
        """NOT_CONTAINS with None field should return True."""
        engine = RuleEngine()
        cond = _make_condition(
            field=ConditionField.RECIPIENT_EMAIL,
            operator=ConditionOperator.NOT_CONTAINS,
            value="bob",
        )
        email = _make_email(recipient_email=None)
        assert engine.evaluate_condition(cond, email) is True


# =============================================================================
# evaluate_rule: AND logic
# =============================================================================


class TestEvaluateRuleAndLogic:
    """Test rule evaluation with AND logic (all conditions must match)."""

    def test_all_conditions_match(self):
        engine = RuleEngine()
        rule = _make_rule(
            conditions=[
                _make_condition(
                    field=ConditionField.SENDER_DOMAIN,
                    operator=ConditionOperator.EQUALS,
                    value="example.com",
                ),
                _make_condition(
                    field=ConditionField.SUBJECT,
                    operator=ConditionOperator.CONTAINS,
                    value="Update",
                ),
            ],
            logic=ConditionLogic.AND,
        )
        email = _make_email(sender_domain="example.com", subject="Weekly Team Update")
        assert engine.evaluate_rule(rule, email) is True

    def test_one_condition_fails(self):
        engine = RuleEngine()
        rule = _make_rule(
            conditions=[
                _make_condition(
                    field=ConditionField.SENDER_DOMAIN,
                    operator=ConditionOperator.EQUALS,
                    value="example.com",
                ),
                _make_condition(
                    field=ConditionField.SUBJECT,
                    operator=ConditionOperator.CONTAINS,
                    value="Budget",
                ),
            ],
            logic=ConditionLogic.AND,
        )
        email = _make_email(sender_domain="example.com", subject="Weekly Team Update")
        assert engine.evaluate_rule(rule, email) is False

    def test_no_conditions_all_fail(self):
        engine = RuleEngine()
        rule = _make_rule(
            conditions=[
                _make_condition(
                    field=ConditionField.SENDER_DOMAIN,
                    operator=ConditionOperator.EQUALS,
                    value="other.com",
                ),
                _make_condition(
                    field=ConditionField.SUBJECT,
                    operator=ConditionOperator.CONTAINS,
                    value="Budget",
                ),
            ],
            logic=ConditionLogic.AND,
        )
        email = _make_email(sender_domain="example.com", subject="Weekly Team Update")
        assert engine.evaluate_rule(rule, email) is False

    def test_single_condition_and(self):
        engine = RuleEngine()
        rule = _make_rule(
            conditions=[
                _make_condition(
                    field=ConditionField.SENDER_DOMAIN,
                    operator=ConditionOperator.EQUALS,
                    value="example.com",
                ),
            ],
            logic=ConditionLogic.AND,
        )
        email = _make_email(sender_domain="example.com")
        assert engine.evaluate_rule(rule, email) is True


# =============================================================================
# evaluate_rule: OR logic
# =============================================================================


class TestEvaluateRuleOrLogic:
    """Test rule evaluation with OR logic (any condition must match)."""

    def test_first_condition_matches(self):
        engine = RuleEngine()
        rule = _make_rule(
            conditions=[
                _make_condition(
                    field=ConditionField.SENDER_DOMAIN,
                    operator=ConditionOperator.EQUALS,
                    value="example.com",
                ),
                _make_condition(
                    field=ConditionField.SUBJECT,
                    operator=ConditionOperator.CONTAINS,
                    value="Budget",
                ),
            ],
            logic=ConditionLogic.OR,
        )
        email = _make_email(sender_domain="example.com", subject="Weekly Team Update")
        assert engine.evaluate_rule(rule, email) is True

    def test_second_condition_matches(self):
        engine = RuleEngine()
        rule = _make_rule(
            conditions=[
                _make_condition(
                    field=ConditionField.SENDER_DOMAIN,
                    operator=ConditionOperator.EQUALS,
                    value="other.com",
                ),
                _make_condition(
                    field=ConditionField.SUBJECT,
                    operator=ConditionOperator.CONTAINS,
                    value="Update",
                ),
            ],
            logic=ConditionLogic.OR,
        )
        email = _make_email(sender_domain="example.com", subject="Weekly Team Update")
        assert engine.evaluate_rule(rule, email) is True

    def test_no_conditions_match(self):
        engine = RuleEngine()
        rule = _make_rule(
            conditions=[
                _make_condition(
                    field=ConditionField.SENDER_DOMAIN,
                    operator=ConditionOperator.EQUALS,
                    value="other.com",
                ),
                _make_condition(
                    field=ConditionField.SUBJECT,
                    operator=ConditionOperator.CONTAINS,
                    value="Budget",
                ),
            ],
            logic=ConditionLogic.OR,
        )
        email = _make_email(sender_domain="example.com", subject="Weekly Team Update")
        assert engine.evaluate_rule(rule, email) is False

    def test_all_conditions_match_or(self):
        engine = RuleEngine()
        rule = _make_rule(
            conditions=[
                _make_condition(
                    field=ConditionField.SENDER_DOMAIN,
                    operator=ConditionOperator.EQUALS,
                    value="example.com",
                ),
                _make_condition(
                    field=ConditionField.SUBJECT,
                    operator=ConditionOperator.CONTAINS,
                    value="Update",
                ),
            ],
            logic=ConditionLogic.OR,
        )
        email = _make_email(sender_domain="example.com", subject="Weekly Team Update")
        assert engine.evaluate_rule(rule, email) is True


# =============================================================================
# evaluate_rule: Disabled rules
# =============================================================================


class TestEvaluateRuleDisabled:
    """Disabled rules should never match."""

    def test_disabled_rule_returns_false(self):
        engine = RuleEngine()
        rule = _make_rule(
            conditions=[
                _make_condition(
                    field=ConditionField.SENDER_DOMAIN,
                    operator=ConditionOperator.EQUALS,
                    value="example.com",
                ),
            ],
            enabled=False,
        )
        email = _make_email(sender_domain="example.com")
        assert engine.evaluate_rule(rule, email) is False


# =============================================================================
# evaluate_rule: Short-circuit evaluation
# =============================================================================


class TestShortCircuitEvaluation:
    """Test that short-circuit evaluation works correctly.

    For AND: stop on first False.
    For OR: stop on first True.
    We verify this by counting how many conditions are actually evaluated.
    """

    def test_and_short_circuits_on_first_false(self):
        """AND logic should not evaluate remaining conditions after a False."""
        engine = RuleEngine()
        eval_count = {"count": 0}
        original_evaluate = engine.evaluate_condition

        def counting_evaluate(cond, email):
            eval_count["count"] += 1
            return original_evaluate(cond, email)

        engine.evaluate_condition = counting_evaluate

        rule = _make_rule(
            conditions=[
                _make_condition(
                    field=ConditionField.SENDER_DOMAIN,
                    operator=ConditionOperator.EQUALS,
                    value="NOMATCH.com",
                ),
                _make_condition(
                    field=ConditionField.SUBJECT,
                    operator=ConditionOperator.CONTAINS,
                    value="Update",
                ),
                _make_condition(
                    field=ConditionField.BODY,
                    operator=ConditionOperator.CONTAINS,
                    value="report",
                ),
            ],
            logic=ConditionLogic.AND,
        )
        email = _make_email()
        result = engine.evaluate_rule(rule, email)
        assert result is False
        assert eval_count["count"] == 1  # Only first condition evaluated

    def test_or_short_circuits_on_first_true(self):
        """OR logic should not evaluate remaining conditions after a True."""
        engine = RuleEngine()
        eval_count = {"count": 0}
        original_evaluate = engine.evaluate_condition

        def counting_evaluate(cond, email):
            eval_count["count"] += 1
            return original_evaluate(cond, email)

        engine.evaluate_condition = counting_evaluate

        rule = _make_rule(
            conditions=[
                _make_condition(
                    field=ConditionField.SENDER_DOMAIN,
                    operator=ConditionOperator.EQUALS,
                    value="example.com",
                ),
                _make_condition(
                    field=ConditionField.SUBJECT,
                    operator=ConditionOperator.CONTAINS,
                    value="NOMATCH",
                ),
                _make_condition(
                    field=ConditionField.BODY,
                    operator=ConditionOperator.CONTAINS,
                    value="NOMATCH",
                ),
            ],
            logic=ConditionLogic.OR,
        )
        email = _make_email()
        result = engine.evaluate_rule(rule, email)
        assert result is True
        assert eval_count["count"] == 1  # Only first condition evaluated


# =============================================================================
# evaluate_all: Full RuleSet evaluation
# =============================================================================


class TestEvaluateAll:
    """Test evaluate_all: evaluate a RuleSet against a single email."""

    def test_returns_matching_rules(self):
        engine = RuleEngine()
        rule_set = RuleSet(
            rules=[
                _make_rule(
                    rule_id="r1",
                    name="Domain Match",
                    conditions=[
                        _make_condition(
                            field=ConditionField.SENDER_DOMAIN,
                            operator=ConditionOperator.EQUALS,
                            value="example.com",
                        )
                    ],
                ),
                _make_rule(
                    rule_id="r2",
                    name="Subject Match",
                    conditions=[
                        _make_condition(
                            field=ConditionField.SUBJECT,
                            operator=ConditionOperator.CONTAINS,
                            value="Update",
                        )
                    ],
                ),
                _make_rule(
                    rule_id="r3",
                    name="No Match",
                    conditions=[
                        _make_condition(
                            field=ConditionField.SENDER_DOMAIN,
                            operator=ConditionOperator.EQUALS,
                            value="other.com",
                        )
                    ],
                ),
            ]
        )
        email = _make_email(sender_domain="example.com", subject="Weekly Team Update")
        matches = engine.evaluate_all(rule_set, email)
        assert len(matches) == 2
        matched_ids = [r.rule_id for r in matches]
        assert "r1" in matched_ids
        assert "r2" in matched_ids
        assert "r3" not in matched_ids

    def test_returns_empty_for_no_matches(self):
        engine = RuleEngine()
        rule_set = RuleSet(
            rules=[
                _make_rule(
                    rule_id="r1",
                    conditions=[
                        _make_condition(
                            field=ConditionField.SENDER_DOMAIN,
                            operator=ConditionOperator.EQUALS,
                            value="other.com",
                        )
                    ],
                ),
            ]
        )
        email = _make_email(sender_domain="example.com")
        matches = engine.evaluate_all(rule_set, email)
        assert len(matches) == 0

    def test_sorted_by_priority_descending(self):
        engine = RuleEngine()
        rule_set = RuleSet(
            rules=[
                _make_rule(
                    rule_id="r_low",
                    name="Low Priority",
                    priority=1,
                    conditions=[
                        _make_condition(
                            field=ConditionField.SENDER_DOMAIN,
                            operator=ConditionOperator.EQUALS,
                            value="example.com",
                        )
                    ],
                ),
                _make_rule(
                    rule_id="r_high",
                    name="High Priority",
                    priority=10,
                    conditions=[
                        _make_condition(
                            field=ConditionField.SENDER_DOMAIN,
                            operator=ConditionOperator.EQUALS,
                            value="example.com",
                        )
                    ],
                ),
                _make_rule(
                    rule_id="r_mid",
                    name="Mid Priority",
                    priority=5,
                    conditions=[
                        _make_condition(
                            field=ConditionField.SENDER_DOMAIN,
                            operator=ConditionOperator.EQUALS,
                            value="example.com",
                        )
                    ],
                ),
            ]
        )
        email = _make_email(sender_domain="example.com")
        matches = engine.evaluate_all(rule_set, email)
        assert len(matches) == 3
        assert matches[0].rule_id == "r_high"
        assert matches[1].rule_id == "r_mid"
        assert matches[2].rule_id == "r_low"

    def test_disabled_rules_excluded(self):
        engine = RuleEngine()
        rule_set = RuleSet(
            rules=[
                _make_rule(
                    rule_id="r1",
                    enabled=True,
                    conditions=[
                        _make_condition(
                            field=ConditionField.SENDER_DOMAIN,
                            operator=ConditionOperator.EQUALS,
                            value="example.com",
                        )
                    ],
                ),
                _make_rule(
                    rule_id="r2",
                    enabled=False,
                    conditions=[
                        _make_condition(
                            field=ConditionField.SENDER_DOMAIN,
                            operator=ConditionOperator.EQUALS,
                            value="example.com",
                        )
                    ],
                ),
            ]
        )
        email = _make_email(sender_domain="example.com")
        matches = engine.evaluate_all(rule_set, email)
        assert len(matches) == 1
        assert matches[0].rule_id == "r1"

    def test_empty_ruleset_returns_empty(self):
        engine = RuleEngine()
        rule_set = RuleSet(rules=[])
        email = _make_email()
        matches = engine.evaluate_all(rule_set, email)
        assert matches == []


# =============================================================================
# evaluate_all: Complex multi-condition scenarios
# =============================================================================


class TestEvaluateAllComplex:
    """Test more complex rule evaluation scenarios."""

    def test_mixed_and_or_rules(self):
        """Test a RuleSet containing both AND and OR rules."""
        engine = RuleEngine()
        rule_set = RuleSet(
            rules=[
                _make_rule(
                    rule_id="and_rule",
                    name="AND Rule",
                    conditions=[
                        _make_condition(
                            field=ConditionField.SENDER_DOMAIN,
                            operator=ConditionOperator.EQUALS,
                            value="example.com",
                        ),
                        _make_condition(
                            field=ConditionField.SUBJECT,
                            operator=ConditionOperator.CONTAINS,
                            value="Update",
                        ),
                    ],
                    logic=ConditionLogic.AND,
                ),
                _make_rule(
                    rule_id="or_rule",
                    name="OR Rule",
                    conditions=[
                        _make_condition(
                            field=ConditionField.SENDER_DOMAIN,
                            operator=ConditionOperator.EQUALS,
                            value="other.com",
                        ),
                        _make_condition(
                            field=ConditionField.HAS_ATTACHMENT,
                            operator=ConditionOperator.EQUALS,
                            value="true",
                        ),
                    ],
                    logic=ConditionLogic.OR,
                ),
            ]
        )
        # Email matches AND rule (domain + subject) but not OR rule (wrong domain, no attachment)
        email = _make_email(
            sender_domain="example.com",
            subject="Weekly Team Update",
            has_attachments=False,
        )
        matches = engine.evaluate_all(rule_set, email)
        assert len(matches) == 1
        assert matches[0].rule_id == "and_rule"

    def test_rule_with_negation_conditions(self):
        """Test rules mixing positive and negative conditions."""
        engine = RuleEngine()
        rule = _make_rule(
            conditions=[
                _make_condition(
                    field=ConditionField.SENDER_DOMAIN,
                    operator=ConditionOperator.EQUALS,
                    value="example.com",
                ),
                _make_condition(
                    field=ConditionField.SUBJECT,
                    operator=ConditionOperator.NOT_CONTAINS,
                    value="spam",
                ),
            ],
            logic=ConditionLogic.AND,
        )
        email = _make_email(sender_domain="example.com", subject="Weekly Team Update")
        assert engine.evaluate_rule(rule, email) is True

    def test_all_operators_on_single_field(self):
        """Verify all string operators work on subject field."""
        engine = RuleEngine()
        email = _make_email(subject="RE: Invoice #1234 - Final")

        assert engine.evaluate_condition(
            _make_condition(
                field=ConditionField.SUBJECT,
                operator=ConditionOperator.CONTAINS,
                value="Invoice",
            ),
            email,
        )
        assert engine.evaluate_condition(
            _make_condition(
                field=ConditionField.SUBJECT,
                operator=ConditionOperator.STARTS_WITH,
                value="RE:",
            ),
            email,
        )
        assert engine.evaluate_condition(
            _make_condition(
                field=ConditionField.SUBJECT,
                operator=ConditionOperator.ENDS_WITH,
                value="Final",
            ),
            email,
        )
        assert engine.evaluate_condition(
            _make_condition(
                field=ConditionField.SUBJECT,
                operator=ConditionOperator.MATCHES_REGEX,
                value=r"#\d{4}",
            ),
            email,
        )
        assert engine.evaluate_condition(
            _make_condition(
                field=ConditionField.SUBJECT,
                operator=ConditionOperator.NOT_CONTAINS,
                value="spam",
            ),
            email,
        )
        assert not engine.evaluate_condition(
            _make_condition(
                field=ConditionField.SUBJECT,
                operator=ConditionOperator.EQUALS,
                value="wrong subject",
            ),
            email,
        )
        assert engine.evaluate_condition(
            _make_condition(
                field=ConditionField.SUBJECT,
                operator=ConditionOperator.NOT_EQUALS,
                value="wrong subject",
            ),
            email,
        )
        assert engine.evaluate_condition(
            _make_condition(
                field=ConditionField.SUBJECT,
                operator=ConditionOperator.IN_LIST,
                value="RE: Invoice #1234 - Final,other subject",
            ),
            email,
        )
