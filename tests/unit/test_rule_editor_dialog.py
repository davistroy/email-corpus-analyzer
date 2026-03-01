"""
Unit tests for RuleEditorDialog (Phase 3, Item 3.5).

Tests the TUI dialog for editing category rule conditions with live match count.
TDD: Tests written first, implementation follows.
"""

from datetime import datetime

from src.models.category import Category, CategorySource
from src.models.email import Email
from src.models.rule import (  # noqa: F401
    CategoryRule,
    ConditionField,
    ConditionLogic,
    ConditionOperator,
    RuleAction,
    RuleActionType,
    RuleCondition,
)

# =============================================================================
# Helpers
# =============================================================================


def _make_category(
    category_id: str = "cat_1",
    name: str = "Newsletter Updates",
    confidence: float = 0.85,
    email_count: int = 42,
) -> Category:
    """Create a test Category."""
    return Category(
        category_id=category_id,
        category_name=name,
        description="Test category",
        confidence=confidence,
        email_count=email_count,
        percentage=25.0,
        source=CategorySource.TEMPLATE,
        source_id="test_source",
        example_email_ids=[],
        distinguishing_features=["newsletter", "weekly"],
    )


def _make_email(
    email_id: str = "email_1",
    sender_email: str = "news@example.com",
    sender_domain: str = "example.com",
    subject: str = "Weekly Newsletter",
    body_text: str = "Here is your weekly newsletter update.",
    has_attachments: bool = False,
) -> Email:
    """Create a test Email."""
    return Email(
        id=email_id,
        sender_email=sender_email,
        sender_name="News Bot",
        sender_domain=sender_domain,
        subject=subject,
        body_text=body_text,
        received_date=datetime(2024, 6, 15, 9, 0, 0),
        has_attachments=has_attachments,
    )


def _make_condition(
    field: ConditionField = ConditionField.SENDER_DOMAIN,
    operator: ConditionOperator = ConditionOperator.EQUALS,
    value: str = "example.com",
) -> RuleCondition:
    """Create a test RuleCondition."""
    return RuleCondition(field=field, operator=operator, value=value)


def _make_rule(
    conditions: list[RuleCondition] | None = None,
    logic: ConditionLogic = ConditionLogic.AND,
    category_id: str = "cat_1",
) -> CategoryRule:
    """Create a test CategoryRule."""
    if conditions is None:
        conditions = [_make_condition()]
    return CategoryRule(
        rule_id=f"rule_{category_id}",
        name="Test Rule",
        conditions=conditions,
        action=RuleAction(
            action_type=RuleActionType.CATEGORIZE,
            target="Newsletter Updates",
            target_category_id=category_id,
        ),
        logic=logic,
        category_id=category_id,
    )


def _make_corpus() -> list[Email]:
    """Create a small test corpus for match count testing."""
    return [
        _make_email(email_id="e1", sender_domain="example.com", subject="Weekly Newsletter"),
        _make_email(email_id="e2", sender_domain="example.com", subject="Monthly Report"),
        _make_email(email_id="e3", sender_domain="other.com", subject="Weekly Newsletter"),
        _make_email(email_id="e4", sender_domain="other.com", subject="Hello"),
        _make_email(email_id="e5", sender_domain="example.com", subject="Alert: system down"),
    ]


# =============================================================================
# Test: Dialog Initialization
# =============================================================================


class TestRuleEditorDialogInit:
    """Test RuleEditorDialog initialization."""

    def test_can_be_instantiated_with_rule(self):
        """Dialog can be created with an existing rule."""
        from src.ui.tui.dialogs.rule_editor_dialog import RuleEditorDialog

        rule = _make_rule()
        category = _make_category()
        dialog = RuleEditorDialog(rule=rule, category=category, corpus=[])

        assert dialog is not None
        assert dialog.rule is not None

    def test_can_be_instantiated_without_rule(self):
        """Dialog can be created without a rule (new rule creation)."""
        from src.ui.tui.dialogs.rule_editor_dialog import RuleEditorDialog

        category = _make_category()
        dialog = RuleEditorDialog(rule=None, category=category, corpus=[])

        assert dialog is not None
        assert dialog.rule is None

    def test_stores_category(self):
        """Dialog stores the category reference."""
        from src.ui.tui.dialogs.rule_editor_dialog import RuleEditorDialog

        category = _make_category(name="Promotions")
        dialog = RuleEditorDialog(rule=None, category=category, corpus=[])

        assert dialog.category.category_name == "Promotions"

    def test_stores_corpus(self):
        """Dialog stores the email corpus for match counting."""
        from src.ui.tui.dialogs.rule_editor_dialog import RuleEditorDialog

        corpus = _make_corpus()
        dialog = RuleEditorDialog(rule=None, category=_make_category(), corpus=corpus)

        assert len(dialog.corpus) == 5

    def test_has_escape_binding(self):
        """Dialog has escape key binding for cancel."""
        from src.ui.tui.dialogs.rule_editor_dialog import RuleEditorDialog

        dialog = RuleEditorDialog(rule=None, category=_make_category(), corpus=[])

        binding_keys = [b.key for b in dialog.BINDINGS]
        assert "escape" in binding_keys

    def test_is_modal_screen(self):
        """Dialog is a ModalScreen."""
        from textual.screen import ModalScreen

        from src.ui.tui.dialogs.rule_editor_dialog import RuleEditorDialog

        dialog = RuleEditorDialog(rule=None, category=_make_category(), corpus=[])

        assert isinstance(dialog, ModalScreen)


# =============================================================================
# Test: Working Conditions Management
# =============================================================================


class TestRuleEditorConditions:
    """Test condition management (add/remove) in the dialog."""

    def test_get_working_conditions_from_existing_rule(self):
        """Working conditions are initialized from an existing rule."""
        from src.ui.tui.dialogs.rule_editor_dialog import RuleEditorDialog

        conditions = [
            _make_condition(ConditionField.SENDER_DOMAIN, ConditionOperator.EQUALS, "example.com"),
            _make_condition(ConditionField.SUBJECT, ConditionOperator.CONTAINS, "newsletter"),
        ]
        rule = _make_rule(conditions=conditions)
        dialog = RuleEditorDialog(rule=rule, category=_make_category(), corpus=[])

        assert len(dialog.working_conditions) == 2

    def test_get_working_conditions_empty_for_new_rule(self):
        """Working conditions are empty when no rule is provided."""
        from src.ui.tui.dialogs.rule_editor_dialog import RuleEditorDialog

        dialog = RuleEditorDialog(rule=None, category=_make_category(), corpus=[])

        assert len(dialog.working_conditions) == 0

    def test_add_condition(self):
        """Can add a new condition to working conditions."""
        from src.ui.tui.dialogs.rule_editor_dialog import RuleEditorDialog

        dialog = RuleEditorDialog(rule=None, category=_make_category(), corpus=[])
        new_cond = _make_condition(ConditionField.SUBJECT, ConditionOperator.CONTAINS, "promo")

        dialog.add_condition(new_cond)

        assert len(dialog.working_conditions) == 1
        assert dialog.working_conditions[0].value == "promo"

    def test_add_multiple_conditions(self):
        """Can add multiple conditions."""
        from src.ui.tui.dialogs.rule_editor_dialog import RuleEditorDialog

        dialog = RuleEditorDialog(rule=None, category=_make_category(), corpus=[])
        dialog.add_condition(
            _make_condition(ConditionField.SUBJECT, ConditionOperator.CONTAINS, "promo")
        )
        dialog.add_condition(
            _make_condition(ConditionField.SENDER_DOMAIN, ConditionOperator.EQUALS, "shop.com")
        )

        assert len(dialog.working_conditions) == 2

    def test_remove_condition_by_index(self):
        """Can remove a condition by its index."""
        from src.ui.tui.dialogs.rule_editor_dialog import RuleEditorDialog

        conditions = [
            _make_condition(ConditionField.SENDER_DOMAIN, ConditionOperator.EQUALS, "a.com"),
            _make_condition(ConditionField.SUBJECT, ConditionOperator.CONTAINS, "test"),
            _make_condition(ConditionField.BODY, ConditionOperator.CONTAINS, "hello"),
        ]
        rule = _make_rule(conditions=conditions)
        dialog = RuleEditorDialog(rule=rule, category=_make_category(), corpus=[])

        dialog.remove_condition(1)

        assert len(dialog.working_conditions) == 2
        assert dialog.working_conditions[0].value == "a.com"
        assert dialog.working_conditions[1].value == "hello"

    def test_remove_condition_out_of_range_no_crash(self):
        """Removing a condition with out-of-range index does nothing."""
        from src.ui.tui.dialogs.rule_editor_dialog import RuleEditorDialog

        dialog = RuleEditorDialog(
            rule=_make_rule(conditions=[_make_condition()]),
            category=_make_category(),
            corpus=[],
        )

        dialog.remove_condition(99)

        assert len(dialog.working_conditions) == 1

    def test_remove_condition_negative_index_no_crash(self):
        """Removing a condition with negative index does nothing."""
        from src.ui.tui.dialogs.rule_editor_dialog import RuleEditorDialog

        dialog = RuleEditorDialog(
            rule=_make_rule(conditions=[_make_condition()]),
            category=_make_category(),
            corpus=[],
        )

        dialog.remove_condition(-1)

        assert len(dialog.working_conditions) == 1


# =============================================================================
# Test: Logic Toggle
# =============================================================================


class TestRuleEditorLogicToggle:
    """Test AND/OR logic toggle."""

    def test_default_logic_is_and_with_rule(self):
        """Default logic from an AND-rule is AND."""
        from src.ui.tui.dialogs.rule_editor_dialog import RuleEditorDialog

        rule = _make_rule(logic=ConditionLogic.AND)
        dialog = RuleEditorDialog(rule=rule, category=_make_category(), corpus=[])

        assert dialog.working_logic == ConditionLogic.AND

    def test_default_logic_is_or_from_or_rule(self):
        """Logic from an OR-rule is OR."""
        from src.ui.tui.dialogs.rule_editor_dialog import RuleEditorDialog

        rule = _make_rule(logic=ConditionLogic.OR)
        dialog = RuleEditorDialog(rule=rule, category=_make_category(), corpus=[])

        assert dialog.working_logic == ConditionLogic.OR

    def test_default_logic_without_rule_is_or(self):
        """Default logic for a new rule (no existing rule) is OR."""
        from src.ui.tui.dialogs.rule_editor_dialog import RuleEditorDialog

        dialog = RuleEditorDialog(rule=None, category=_make_category(), corpus=[])

        assert dialog.working_logic == ConditionLogic.OR

    def test_toggle_logic_and_to_or(self):
        """Toggle logic from AND to OR."""
        from src.ui.tui.dialogs.rule_editor_dialog import RuleEditorDialog

        rule = _make_rule(logic=ConditionLogic.AND)
        dialog = RuleEditorDialog(rule=rule, category=_make_category(), corpus=[])

        dialog.toggle_logic()

        assert dialog.working_logic == ConditionLogic.OR

    def test_toggle_logic_or_to_and(self):
        """Toggle logic from OR to AND."""
        from src.ui.tui.dialogs.rule_editor_dialog import RuleEditorDialog

        rule = _make_rule(logic=ConditionLogic.OR)
        dialog = RuleEditorDialog(rule=rule, category=_make_category(), corpus=[])

        dialog.toggle_logic()

        assert dialog.working_logic == ConditionLogic.AND

    def test_toggle_logic_twice_returns_original(self):
        """Toggling twice returns to original value."""
        from src.ui.tui.dialogs.rule_editor_dialog import RuleEditorDialog

        rule = _make_rule(logic=ConditionLogic.AND)
        dialog = RuleEditorDialog(rule=rule, category=_make_category(), corpus=[])

        dialog.toggle_logic()
        dialog.toggle_logic()

        assert dialog.working_logic == ConditionLogic.AND


# =============================================================================
# Test: Live Match Count
# =============================================================================


class TestRuleEditorMatchCount:
    """Test live match count calculation."""

    def test_match_count_no_conditions_returns_zero(self):
        """Match count is 0 when there are no conditions."""
        from src.ui.tui.dialogs.rule_editor_dialog import RuleEditorDialog

        corpus = _make_corpus()
        dialog = RuleEditorDialog(rule=None, category=_make_category(), corpus=corpus)

        assert dialog.compute_match_count() == 0

    def test_match_count_domain_equals(self):
        """Match count for domain equals condition."""
        from src.ui.tui.dialogs.rule_editor_dialog import RuleEditorDialog

        corpus = _make_corpus()
        conditions = [
            _make_condition(ConditionField.SENDER_DOMAIN, ConditionOperator.EQUALS, "example.com")
        ]
        rule = _make_rule(conditions=conditions, logic=ConditionLogic.OR)
        dialog = RuleEditorDialog(rule=rule, category=_make_category(), corpus=corpus)

        # e1, e2, e5 are from example.com
        assert dialog.compute_match_count() == 3

    def test_match_count_subject_contains(self):
        """Match count for subject contains condition."""
        from src.ui.tui.dialogs.rule_editor_dialog import RuleEditorDialog

        corpus = _make_corpus()
        conditions = [
            _make_condition(ConditionField.SUBJECT, ConditionOperator.CONTAINS, "Newsletter")
        ]
        rule = _make_rule(conditions=conditions, logic=ConditionLogic.OR)
        dialog = RuleEditorDialog(rule=rule, category=_make_category(), corpus=corpus)

        # e1 and e3 have "Newsletter" in subject
        assert dialog.compute_match_count() == 2

    def test_match_count_and_logic(self):
        """Match count with AND logic requires all conditions to match."""
        from src.ui.tui.dialogs.rule_editor_dialog import RuleEditorDialog

        corpus = _make_corpus()
        conditions = [
            _make_condition(ConditionField.SENDER_DOMAIN, ConditionOperator.EQUALS, "example.com"),
            _make_condition(ConditionField.SUBJECT, ConditionOperator.CONTAINS, "Newsletter"),
        ]
        rule = _make_rule(conditions=conditions, logic=ConditionLogic.AND)
        dialog = RuleEditorDialog(rule=rule, category=_make_category(), corpus=corpus)

        # Only e1 matches both (example.com AND Newsletter)
        assert dialog.compute_match_count() == 1

    def test_match_count_or_logic(self):
        """Match count with OR logic requires any condition to match."""
        from src.ui.tui.dialogs.rule_editor_dialog import RuleEditorDialog

        corpus = _make_corpus()
        conditions = [
            _make_condition(ConditionField.SENDER_DOMAIN, ConditionOperator.EQUALS, "example.com"),
            _make_condition(ConditionField.SUBJECT, ConditionOperator.CONTAINS, "Newsletter"),
        ]
        rule = _make_rule(conditions=conditions, logic=ConditionLogic.OR)
        dialog = RuleEditorDialog(rule=rule, category=_make_category(), corpus=corpus)

        # e1 (both), e2 (domain), e3 (subject), e5 (domain) = 4
        assert dialog.compute_match_count() == 4

    def test_match_count_empty_corpus(self):
        """Match count is 0 with empty corpus."""
        from src.ui.tui.dialogs.rule_editor_dialog import RuleEditorDialog

        rule = _make_rule()
        dialog = RuleEditorDialog(rule=rule, category=_make_category(), corpus=[])

        assert dialog.compute_match_count() == 0

    def test_match_count_updates_after_add_condition(self):
        """Match count updates after adding a condition."""
        from src.ui.tui.dialogs.rule_editor_dialog import RuleEditorDialog

        corpus = _make_corpus()
        dialog = RuleEditorDialog(rule=None, category=_make_category(), corpus=corpus)

        assert dialog.compute_match_count() == 0

        dialog.add_condition(
            _make_condition(ConditionField.SENDER_DOMAIN, ConditionOperator.EQUALS, "example.com")
        )
        assert dialog.compute_match_count() == 3

    def test_match_count_updates_after_remove_condition(self):
        """Match count updates after removing a condition."""
        from src.ui.tui.dialogs.rule_editor_dialog import RuleEditorDialog

        corpus = _make_corpus()
        conditions = [
            _make_condition(ConditionField.SENDER_DOMAIN, ConditionOperator.EQUALS, "example.com"),
            _make_condition(ConditionField.SUBJECT, ConditionOperator.CONTAINS, "Newsletter"),
        ]
        rule = _make_rule(conditions=conditions, logic=ConditionLogic.AND)
        dialog = RuleEditorDialog(rule=rule, category=_make_category(), corpus=corpus)

        assert dialog.compute_match_count() == 1  # AND: only e1

        dialog.remove_condition(1)  # Remove subject condition
        assert dialog.compute_match_count() == 3  # Now just domain: e1, e2, e5

    def test_match_count_updates_after_toggle_logic(self):
        """Match count updates after toggling AND/OR logic."""
        from src.ui.tui.dialogs.rule_editor_dialog import RuleEditorDialog

        corpus = _make_corpus()
        conditions = [
            _make_condition(ConditionField.SENDER_DOMAIN, ConditionOperator.EQUALS, "example.com"),
            _make_condition(ConditionField.SUBJECT, ConditionOperator.CONTAINS, "Newsletter"),
        ]
        rule = _make_rule(conditions=conditions, logic=ConditionLogic.AND)
        dialog = RuleEditorDialog(rule=rule, category=_make_category(), corpus=corpus)

        and_count = dialog.compute_match_count()  # AND: 1
        dialog.toggle_logic()
        or_count = dialog.compute_match_count()  # OR: 4

        assert and_count == 1
        assert or_count == 4


# =============================================================================
# Test: Match Text Formatting
# =============================================================================


class TestRuleEditorMatchText:
    """Test the formatted match count text."""

    def test_match_text_zero(self):
        """Match text for 0 matches."""
        from src.ui.tui.dialogs.rule_editor_dialog import RuleEditorDialog

        dialog = RuleEditorDialog(rule=None, category=_make_category(), corpus=[])

        text = dialog.get_match_text()
        assert "0" in text
        assert "email" in text.lower()

    def test_match_text_singular(self):
        """Match text for 1 match uses singular form."""
        from src.ui.tui.dialogs.rule_editor_dialog import RuleEditorDialog

        corpus = [_make_email(email_id="e1", sender_domain="example.com")]
        conditions = [
            _make_condition(ConditionField.SENDER_DOMAIN, ConditionOperator.EQUALS, "example.com")
        ]
        rule = _make_rule(conditions=conditions)
        dialog = RuleEditorDialog(rule=rule, category=_make_category(), corpus=corpus)

        text = dialog.get_match_text()
        assert "1" in text
        assert "email" in text.lower()

    def test_match_text_plural(self):
        """Match text for multiple matches uses plural form."""
        from src.ui.tui.dialogs.rule_editor_dialog import RuleEditorDialog

        corpus = _make_corpus()
        conditions = [
            _make_condition(ConditionField.SENDER_DOMAIN, ConditionOperator.EQUALS, "example.com")
        ]
        rule = _make_rule(conditions=conditions)
        dialog = RuleEditorDialog(rule=rule, category=_make_category(), corpus=corpus)

        text = dialog.get_match_text()
        assert "3" in text
        assert "emails" in text.lower()

    def test_match_text_includes_corpus_total(self):
        """Match text includes the total corpus size for context."""
        from src.ui.tui.dialogs.rule_editor_dialog import RuleEditorDialog

        corpus = _make_corpus()
        conditions = [
            _make_condition(ConditionField.SENDER_DOMAIN, ConditionOperator.EQUALS, "example.com")
        ]
        rule = _make_rule(conditions=conditions)
        dialog = RuleEditorDialog(rule=rule, category=_make_category(), corpus=corpus)

        text = dialog.get_match_text()
        assert "5" in text  # total corpus size


# =============================================================================
# Test: Condition Display Formatting
# =============================================================================


class TestRuleEditorConditionDisplay:
    """Test formatting of conditions for display."""

    def test_format_condition_display(self):
        """Condition is formatted as a human-readable string."""
        from src.ui.tui.dialogs.rule_editor_dialog import RuleEditorDialog

        condition = _make_condition(
            ConditionField.SENDER_DOMAIN, ConditionOperator.EQUALS, "example.com"
        )
        dialog = RuleEditorDialog(rule=None, category=_make_category(), corpus=[])

        text = dialog.format_condition(condition)

        assert "sender_domain" in text
        assert "equals" in text
        assert "example.com" in text

    def test_format_condition_subject_contains(self):
        """Subject contains condition is formatted correctly."""
        from src.ui.tui.dialogs.rule_editor_dialog import RuleEditorDialog

        condition = _make_condition(
            ConditionField.SUBJECT, ConditionOperator.CONTAINS, "newsletter"
        )
        dialog = RuleEditorDialog(rule=None, category=_make_category(), corpus=[])

        text = dialog.format_condition(condition)

        assert "subject" in text
        assert "contains" in text
        assert "newsletter" in text


# =============================================================================
# Test: Build Result
# =============================================================================


class TestRuleEditorBuildResult:
    """Test building the result rule from dialog state."""

    def test_build_rule_from_working_state(self):
        """Can build a CategoryRule from the working conditions and logic."""
        from src.ui.tui.dialogs.rule_editor_dialog import RuleEditorDialog

        category = _make_category(category_id="cat_42")
        conditions = [
            _make_condition(ConditionField.SENDER_DOMAIN, ConditionOperator.EQUALS, "test.com"),
            _make_condition(ConditionField.SUBJECT, ConditionOperator.CONTAINS, "alert"),
        ]
        rule = _make_rule(conditions=conditions, logic=ConditionLogic.OR, category_id="cat_42")
        dialog = RuleEditorDialog(rule=rule, category=category, corpus=[])

        result = dialog.build_rule()

        assert result is not None
        assert len(result.conditions) == 2
        assert result.logic == ConditionLogic.OR
        assert result.category_id == "cat_42"

    def test_build_rule_returns_none_with_no_conditions(self):
        """Building a rule with no conditions returns None."""
        from src.ui.tui.dialogs.rule_editor_dialog import RuleEditorDialog

        dialog = RuleEditorDialog(rule=None, category=_make_category(), corpus=[])

        result = dialog.build_rule()

        assert result is None

    def test_build_rule_reflects_toggled_logic(self):
        """Built rule reflects toggled logic."""
        from src.ui.tui.dialogs.rule_editor_dialog import RuleEditorDialog

        conditions = [
            _make_condition(ConditionField.SENDER_DOMAIN, ConditionOperator.EQUALS, "test.com"),
        ]
        rule = _make_rule(conditions=conditions, logic=ConditionLogic.AND)
        dialog = RuleEditorDialog(rule=rule, category=_make_category(), corpus=[])

        dialog.toggle_logic()
        result = dialog.build_rule()

        assert result is not None
        assert result.logic == ConditionLogic.OR

    def test_build_rule_reflects_added_conditions(self):
        """Built rule includes conditions added via add_condition."""
        from src.ui.tui.dialogs.rule_editor_dialog import RuleEditorDialog

        dialog = RuleEditorDialog(rule=None, category=_make_category(), corpus=[])
        dialog.add_condition(
            _make_condition(ConditionField.SENDER_DOMAIN, ConditionOperator.EQUALS, "new.com")
        )

        result = dialog.build_rule()

        assert result is not None
        assert len(result.conditions) == 1
        assert result.conditions[0].value == "new.com"

    def test_build_rule_preserves_existing_rule_metadata(self):
        """Built rule preserves rule_id, name, action from the original rule."""
        from src.ui.tui.dialogs.rule_editor_dialog import RuleEditorDialog

        rule = _make_rule(category_id="cat_1")
        dialog = RuleEditorDialog(rule=rule, category=_make_category(), corpus=[])

        result = dialog.build_rule()

        assert result is not None
        assert result.rule_id == rule.rule_id
        assert result.name == rule.name
        assert result.action.action_type == RuleActionType.CATEGORIZE

    def test_build_rule_new_creates_fresh_metadata(self):
        """Built rule from new dialog gets fresh metadata."""
        from src.ui.tui.dialogs.rule_editor_dialog import RuleEditorDialog

        category = _make_category(category_id="cat_new", name="Fresh Category")
        dialog = RuleEditorDialog(rule=None, category=category, corpus=[])
        dialog.add_condition(
            _make_condition(ConditionField.SUBJECT, ConditionOperator.CONTAINS, "test")
        )

        result = dialog.build_rule()

        assert result is not None
        assert result.category_id == "cat_new"
        assert "Fresh Category" in result.name


# =============================================================================
# Test: Action Methods
# =============================================================================


class TestRuleEditorActions:
    """Test dialog action methods."""

    def test_has_cancel_action(self):
        """Dialog has a cancel action method."""
        from src.ui.tui.dialogs.rule_editor_dialog import RuleEditorDialog

        dialog = RuleEditorDialog(rule=None, category=_make_category(), corpus=[])

        assert hasattr(dialog, "action_cancel")

    def test_has_accept_action(self):
        """Dialog has an accept action method."""
        from src.ui.tui.dialogs.rule_editor_dialog import RuleEditorDialog

        dialog = RuleEditorDialog(rule=None, category=_make_category(), corpus=[])

        assert hasattr(dialog, "action_accept")

    def test_has_add_condition_action(self):
        """Dialog has an add condition action method."""
        from src.ui.tui.dialogs.rule_editor_dialog import RuleEditorDialog

        dialog = RuleEditorDialog(rule=None, category=_make_category(), corpus=[])

        assert hasattr(dialog, "action_add_condition")

    def test_has_remove_condition_action(self):
        """Dialog has a remove condition action method."""
        from src.ui.tui.dialogs.rule_editor_dialog import RuleEditorDialog

        dialog = RuleEditorDialog(rule=None, category=_make_category(), corpus=[])

        assert hasattr(dialog, "action_remove_condition")

    def test_has_toggle_logic_action(self):
        """Dialog has a toggle logic action method."""
        from src.ui.tui.dialogs.rule_editor_dialog import RuleEditorDialog

        dialog = RuleEditorDialog(rule=None, category=_make_category(), corpus=[])

        assert hasattr(dialog, "action_toggle_logic")


# =============================================================================
# Test: Available Fields and Operators
# =============================================================================


class TestRuleEditorFieldsOperators:
    """Test that the dialog exposes available fields and operators."""

    def test_available_fields(self):
        """Dialog exposes the list of available condition fields."""
        from src.ui.tui.dialogs.rule_editor_dialog import RuleEditorDialog

        dialog = RuleEditorDialog(rule=None, category=_make_category(), corpus=[])

        fields = dialog.get_available_fields()
        assert len(fields) > 0
        assert ConditionField.SENDER_EMAIL in fields
        assert ConditionField.SENDER_DOMAIN in fields
        assert ConditionField.SUBJECT in fields
        assert ConditionField.BODY in fields

    def test_available_operators(self):
        """Dialog exposes the list of available operators."""
        from src.ui.tui.dialogs.rule_editor_dialog import RuleEditorDialog

        dialog = RuleEditorDialog(rule=None, category=_make_category(), corpus=[])

        operators = dialog.get_available_operators()
        assert len(operators) > 0
        assert ConditionOperator.CONTAINS in operators
        assert ConditionOperator.EQUALS in operators


# =============================================================================
# Test: Dialog Package Export
# =============================================================================


class TestRuleEditorDialogPackageExport:
    """Test that the dialog is properly exported from the package."""

    def test_can_import_from_dialogs_package(self):
        """RuleEditorDialog can be imported from the dialogs package."""
        from src.ui.tui.dialogs import RuleEditorDialog

        assert RuleEditorDialog is not None

    def test_listed_in_package_all(self):
        """RuleEditorDialog is listed in __all__."""
        from src.ui.tui import dialogs

        assert "RuleEditorDialog" in dialogs.__all__


# =============================================================================
# Test: ReviewApp Integration
# =============================================================================


class TestReviewAppRuleEditorIntegration:
    """Test that ReviewApp has the edit_rule action wired correctly."""

    def test_review_app_has_edit_rule_action(self):
        """ReviewApp has an action_edit_rule method."""
        from src.ui.tui.app import ReviewApp

        app = ReviewApp(categories=[_make_category()])

        assert hasattr(app, "action_edit_rule")

    def test_review_app_has_e_key_binding(self):
        """ReviewApp has 'e' key bound to edit_rule."""
        from src.ui.tui.app import ReviewApp

        app = ReviewApp(categories=[_make_category()])

        binding_keys = [b.key for b in app.BINDINGS]
        assert "e" in binding_keys

    def test_review_app_stores_corpus(self):
        """ReviewApp stores the corpus for rule editor usage."""
        from src.ui.tui.app import ReviewApp

        corpus = _make_corpus()
        app = ReviewApp(categories=[_make_category()], corpus=corpus)

        assert len(app.corpus) == 5

    def test_review_app_stores_category_rules(self):
        """ReviewApp stores the category_rules mapping."""
        from src.ui.tui.app import ReviewApp

        rule = _make_rule(category_id="cat_1")
        rules = {"cat_1": rule}
        app = ReviewApp(categories=[_make_category()], category_rules=rules)

        assert "cat_1" in app.category_rules
        assert app.category_rules["cat_1"].rule_id == rule.rule_id

    def test_review_app_defaults_corpus_to_empty(self):
        """ReviewApp defaults corpus to empty list when not provided."""
        from src.ui.tui.app import ReviewApp

        app = ReviewApp(categories=[_make_category()])

        assert app.corpus == []

    def test_review_app_defaults_category_rules_to_empty(self):
        """ReviewApp defaults category_rules to empty dict when not provided."""
        from src.ui.tui.app import ReviewApp

        app = ReviewApp(categories=[_make_category()])

        assert app.category_rules == {}
