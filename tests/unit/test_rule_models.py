"""
Unit tests for rule data models (Phase 3, Item 3.1).

Tests RuleCondition, RuleAction, CategoryRule, and RuleSet Pydantic v2 models.
TDD: These tests are written first, implementation follows.
"""

from datetime import datetime, timezone

import pytest

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
# RuleCondition Tests
# =============================================================================


class TestConditionFieldEnum:
    """Test ConditionField enum values."""

    def test_all_field_types_exist(self):
        """Test all expected field types are defined."""
        assert ConditionField.SENDER_EMAIL.value == "sender_email"
        assert ConditionField.SENDER_DOMAIN.value == "sender_domain"
        assert ConditionField.SUBJECT.value == "subject"
        assert ConditionField.BODY.value == "body"
        assert ConditionField.HAS_ATTACHMENT.value == "has_attachment"
        assert ConditionField.SENDER_NAME.value == "sender_name"
        assert ConditionField.RECIPIENT_EMAIL.value == "recipient_email"


class TestConditionOperatorEnum:
    """Test ConditionOperator enum values."""

    def test_all_operator_types_exist(self):
        """Test all expected operators are defined."""
        assert ConditionOperator.CONTAINS.value == "contains"
        assert ConditionOperator.EQUALS.value == "equals"
        assert ConditionOperator.MATCHES_REGEX.value == "matches_regex"
        assert ConditionOperator.STARTS_WITH.value == "starts_with"
        assert ConditionOperator.ENDS_WITH.value == "ends_with"
        assert ConditionOperator.IN_LIST.value == "in_list"
        assert ConditionOperator.NOT_CONTAINS.value == "not_contains"
        assert ConditionOperator.NOT_EQUALS.value == "not_equals"


class TestRuleCondition:
    """Test RuleCondition model."""

    def test_minimal_condition(self):
        """Test creating a condition with only required fields."""
        cond = RuleCondition(
            field=ConditionField.SENDER_DOMAIN,
            operator=ConditionOperator.EQUALS,
            value="example.com",
        )
        assert cond.field == ConditionField.SENDER_DOMAIN
        assert cond.operator == ConditionOperator.EQUALS
        assert cond.value == "example.com"
        assert cond.case_sensitive is False  # default

    def test_case_sensitive_flag(self):
        """Test case_sensitive defaults to False and can be set True."""
        cond_default = RuleCondition(
            field=ConditionField.SUBJECT,
            operator=ConditionOperator.CONTAINS,
            value="URGENT",
        )
        assert cond_default.case_sensitive is False

        cond_cs = RuleCondition(
            field=ConditionField.SUBJECT,
            operator=ConditionOperator.CONTAINS,
            value="URGENT",
            case_sensitive=True,
        )
        assert cond_cs.case_sensitive is True

    def test_field_from_string(self):
        """Test ConditionField can be created from string value."""
        cond = RuleCondition(
            field="sender_email",
            operator="contains",
            value="@test.com",
        )
        assert cond.field == ConditionField.SENDER_EMAIL
        assert cond.operator == ConditionOperator.CONTAINS

    def test_value_required_non_empty(self):
        """Test that value must be non-empty string."""
        with pytest.raises(ValueError):
            RuleCondition(
                field=ConditionField.SENDER_DOMAIN,
                operator=ConditionOperator.EQUALS,
                value="",
            )

    def test_in_list_with_comma_separated_value(self):
        """Test IN_LIST operator with comma-separated values."""
        cond = RuleCondition(
            field=ConditionField.SENDER_DOMAIN,
            operator=ConditionOperator.IN_LIST,
            value="example.com,test.com,demo.org",
        )
        assert cond.value == "example.com,test.com,demo.org"

    def test_regex_operator_accepted(self):
        """Test matches_regex operator is valid."""
        cond = RuleCondition(
            field=ConditionField.SUBJECT,
            operator=ConditionOperator.MATCHES_REGEX,
            value=r"Invoice\s*#\d+",
        )
        assert cond.operator == ConditionOperator.MATCHES_REGEX

    def test_model_dump_roundtrip(self):
        """Test serialization and deserialization."""
        cond = RuleCondition(
            field=ConditionField.BODY,
            operator=ConditionOperator.CONTAINS,
            value="unsubscribe",
            case_sensitive=False,
        )
        data = cond.model_dump()
        restored = RuleCondition.model_validate(data)
        assert restored == cond

    def test_model_dump_contains_all_fields(self):
        """Test model_dump includes all fields."""
        cond = RuleCondition(
            field=ConditionField.SENDER_EMAIL,
            operator=ConditionOperator.EQUALS,
            value="test@example.com",
            case_sensitive=True,
        )
        data = cond.model_dump()
        assert "field" in data
        assert "operator" in data
        assert "value" in data
        assert "case_sensitive" in data
        assert data["field"] == "sender_email"
        assert data["operator"] == "equals"
        assert data["case_sensitive"] is True

    def test_has_attachment_field(self):
        """Test has_attachment field with equals operator."""
        cond = RuleCondition(
            field=ConditionField.HAS_ATTACHMENT,
            operator=ConditionOperator.EQUALS,
            value="true",
        )
        assert cond.field == ConditionField.HAS_ATTACHMENT


# =============================================================================
# RuleAction Tests
# =============================================================================


class TestRuleActionTypeEnum:
    """Test RuleActionType enum values."""

    def test_all_action_types_exist(self):
        """Test all expected action types are defined."""
        assert RuleActionType.MOVE_TO_FOLDER.value == "move_to_folder"
        assert RuleActionType.APPLY_LABEL.value == "apply_label"
        assert RuleActionType.CATEGORIZE.value == "categorize"
        assert RuleActionType.TAG.value == "tag"
        assert RuleActionType.FLAG.value == "flag"


class TestRuleAction:
    """Test RuleAction model."""

    def test_minimal_action(self):
        """Test creating an action with required fields."""
        action = RuleAction(
            action_type=RuleActionType.CATEGORIZE,
            target="Newsletters",
        )
        assert action.action_type == RuleActionType.CATEGORIZE
        assert action.target == "Newsletters"

    def test_move_to_folder_action(self):
        """Test move_to_folder action type."""
        action = RuleAction(
            action_type=RuleActionType.MOVE_TO_FOLDER,
            target="Inbox/Newsletters",
        )
        assert action.action_type == RuleActionType.MOVE_TO_FOLDER
        assert action.target == "Inbox/Newsletters"

    def test_apply_label_action(self):
        """Test apply_label action type."""
        action = RuleAction(
            action_type=RuleActionType.APPLY_LABEL,
            target="important",
        )
        assert action.action_type == RuleActionType.APPLY_LABEL

    def test_target_required_non_empty(self):
        """Test that target must be non-empty."""
        with pytest.raises(ValueError):
            RuleAction(
                action_type=RuleActionType.CATEGORIZE,
                target="",
            )

    def test_action_type_from_string(self):
        """Test RuleActionType can be set from string value."""
        action = RuleAction(
            action_type="move_to_folder",
            target="Archive",
        )
        assert action.action_type == RuleActionType.MOVE_TO_FOLDER

    def test_target_category_id_optional(self):
        """Test target_category_id is optional."""
        action = RuleAction(
            action_type=RuleActionType.CATEGORIZE,
            target="Newsletters",
        )
        assert action.target_category_id is None

        action_with_id = RuleAction(
            action_type=RuleActionType.CATEGORIZE,
            target="Newsletters",
            target_category_id="cat_newsletters_01",
        )
        assert action_with_id.target_category_id == "cat_newsletters_01"

    def test_model_dump_roundtrip(self):
        """Test serialization and deserialization."""
        action = RuleAction(
            action_type=RuleActionType.MOVE_TO_FOLDER,
            target="Archive/Old",
            target_category_id="cat_archive",
        )
        data = action.model_dump()
        restored = RuleAction.model_validate(data)
        assert restored == action


# =============================================================================
# ConditionLogic Enum Tests
# =============================================================================


class TestConditionLogicEnum:
    """Test ConditionLogic enum values."""

    def test_logic_values(self):
        """Test AND/OR logic enum values."""
        assert ConditionLogic.AND.value == "and"
        assert ConditionLogic.OR.value == "or"


# =============================================================================
# CategoryRule Tests
# =============================================================================


class TestCategoryRule:
    """Test CategoryRule model."""

    def _make_conditions(self) -> list[RuleCondition]:
        """Create a standard set of test conditions."""
        return [
            RuleCondition(
                field=ConditionField.SENDER_DOMAIN,
                operator=ConditionOperator.EQUALS,
                value="newsletter.com",
            ),
            RuleCondition(
                field=ConditionField.SUBJECT,
                operator=ConditionOperator.CONTAINS,
                value="weekly digest",
            ),
        ]

    def _make_action(self) -> RuleAction:
        """Create a standard test action."""
        return RuleAction(
            action_type=RuleActionType.CATEGORIZE,
            target="Newsletters",
            target_category_id="cat_newsletters",
        )

    def test_minimal_category_rule(self):
        """Test creating a rule with only required fields."""
        rule = CategoryRule(
            rule_id="rule_001",
            name="Newsletter Rule",
            conditions=self._make_conditions(),
            action=self._make_action(),
        )
        assert rule.rule_id == "rule_001"
        assert rule.name == "Newsletter Rule"
        assert len(rule.conditions) == 2
        assert rule.logic == ConditionLogic.AND  # default
        assert rule.priority == 0  # default
        assert rule.enabled is True  # default

    def test_rule_id_required_non_empty(self):
        """Test that rule_id must be non-empty."""
        with pytest.raises(ValueError):
            CategoryRule(
                rule_id="",
                name="Test",
                conditions=self._make_conditions(),
                action=self._make_action(),
            )

    def test_name_required_non_empty(self):
        """Test that name must be non-empty."""
        with pytest.raises(ValueError):
            CategoryRule(
                rule_id="rule_001",
                name="",
                conditions=self._make_conditions(),
                action=self._make_action(),
            )

    def test_conditions_required_non_empty(self):
        """Test that conditions list must not be empty."""
        with pytest.raises(ValueError):
            CategoryRule(
                rule_id="rule_001",
                name="Empty Rule",
                conditions=[],
                action=self._make_action(),
            )

    def test_logic_default_and(self):
        """Test that condition logic defaults to AND."""
        rule = CategoryRule(
            rule_id="rule_001",
            name="Test",
            conditions=self._make_conditions(),
            action=self._make_action(),
        )
        assert rule.logic == ConditionLogic.AND

    def test_logic_can_be_or(self):
        """Test that condition logic can be set to OR."""
        rule = CategoryRule(
            rule_id="rule_001",
            name="Test",
            conditions=self._make_conditions(),
            action=self._make_action(),
            logic=ConditionLogic.OR,
        )
        assert rule.logic == ConditionLogic.OR

    def test_logic_from_string(self):
        """Test that logic can be set from string value."""
        rule = CategoryRule(
            rule_id="rule_001",
            name="Test",
            conditions=self._make_conditions(),
            action=self._make_action(),
            logic="or",
        )
        assert rule.logic == ConditionLogic.OR

    def test_priority_default_zero(self):
        """Test that priority defaults to 0."""
        rule = CategoryRule(
            rule_id="rule_001",
            name="Test",
            conditions=self._make_conditions(),
            action=self._make_action(),
        )
        assert rule.priority == 0

    def test_priority_can_be_set(self):
        """Test that priority can be set to any integer."""
        rule = CategoryRule(
            rule_id="rule_001",
            name="Test",
            conditions=self._make_conditions(),
            action=self._make_action(),
            priority=10,
        )
        assert rule.priority == 10

    def test_priority_negative_allowed(self):
        """Test that negative priority is allowed (lower = less important)."""
        rule = CategoryRule(
            rule_id="rule_001",
            name="Test",
            conditions=self._make_conditions(),
            action=self._make_action(),
            priority=-5,
        )
        assert rule.priority == -5

    def test_enabled_default_true(self):
        """Test that enabled defaults to True."""
        rule = CategoryRule(
            rule_id="rule_001",
            name="Test",
            conditions=self._make_conditions(),
            action=self._make_action(),
        )
        assert rule.enabled is True

    def test_enabled_can_be_disabled(self):
        """Test that a rule can be disabled."""
        rule = CategoryRule(
            rule_id="rule_001",
            name="Test",
            conditions=self._make_conditions(),
            action=self._make_action(),
            enabled=False,
        )
        assert rule.enabled is False

    def test_category_id_optional(self):
        """Test that category_id is optional for cross-referencing."""
        rule = CategoryRule(
            rule_id="rule_001",
            name="Test",
            conditions=self._make_conditions(),
            action=self._make_action(),
        )
        assert rule.category_id is None

        rule_with_cat = CategoryRule(
            rule_id="rule_001",
            name="Test",
            conditions=self._make_conditions(),
            action=self._make_action(),
            category_id="cat_newsletters",
        )
        assert rule_with_cat.category_id == "cat_newsletters"

    def test_description_optional(self):
        """Test that description is optional with empty default."""
        rule = CategoryRule(
            rule_id="rule_001",
            name="Test",
            conditions=self._make_conditions(),
            action=self._make_action(),
        )
        assert rule.description == ""

        rule_with_desc = CategoryRule(
            rule_id="rule_001",
            name="Test",
            conditions=self._make_conditions(),
            action=self._make_action(),
            description="Matches newsletter emails from example.com",
        )
        assert rule_with_desc.description == "Matches newsletter emails from example.com"

    def test_created_date_auto_set(self):
        """Test that created_date is auto-populated."""
        rule = CategoryRule(
            rule_id="rule_001",
            name="Test",
            conditions=self._make_conditions(),
            action=self._make_action(),
        )
        assert rule.created_date is not None
        assert isinstance(rule.created_date, datetime)

    def test_last_modified_auto_set(self):
        """Test that last_modified is auto-populated."""
        rule = CategoryRule(
            rule_id="rule_001",
            name="Test",
            conditions=self._make_conditions(),
            action=self._make_action(),
        )
        assert rule.last_modified is not None
        assert isinstance(rule.last_modified, datetime)

    def test_created_date_can_be_explicit(self):
        """Test that created_date can be explicitly set."""
        fixed_date = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        rule = CategoryRule(
            rule_id="rule_001",
            name="Test",
            conditions=self._make_conditions(),
            action=self._make_action(),
            created_date=fixed_date,
        )
        assert rule.created_date == fixed_date

    def test_model_dump_roundtrip(self):
        """Test full serialization and deserialization."""
        rule = CategoryRule(
            rule_id="rule_001",
            name="Newsletter Rule",
            conditions=self._make_conditions(),
            action=self._make_action(),
            logic=ConditionLogic.OR,
            priority=5,
            enabled=True,
            category_id="cat_newsletters",
            description="Matches newsletters",
        )
        data = rule.model_dump()
        restored = CategoryRule.model_validate(data)
        assert restored.rule_id == rule.rule_id
        assert restored.name == rule.name
        assert len(restored.conditions) == len(rule.conditions)
        assert restored.logic == rule.logic
        assert restored.priority == rule.priority
        assert restored.enabled == rule.enabled
        assert restored.category_id == rule.category_id
        assert restored.action.action_type == rule.action.action_type

    def test_model_dump_json_serializable(self):
        """Test that model_dump produces JSON-serializable output."""
        import json

        rule = CategoryRule(
            rule_id="rule_001",
            name="Test",
            conditions=self._make_conditions(),
            action=self._make_action(),
        )
        data = rule.model_dump(mode="json")
        # Should not raise
        json_str = json.dumps(data)
        assert isinstance(json_str, str)

    def test_condition_count_property(self):
        """Test condition_count property returns number of conditions."""
        rule = CategoryRule(
            rule_id="rule_001",
            name="Test",
            conditions=self._make_conditions(),
            action=self._make_action(),
        )
        assert rule.condition_count == 2

    def test_single_condition_rule(self):
        """Test rule with a single condition."""
        rule = CategoryRule(
            rule_id="rule_001",
            name="Single Condition Rule",
            conditions=[
                RuleCondition(
                    field=ConditionField.SENDER_DOMAIN,
                    operator=ConditionOperator.EQUALS,
                    value="example.com",
                ),
            ],
            action=self._make_action(),
        )
        assert rule.condition_count == 1


# =============================================================================
# RuleSet Tests
# =============================================================================


class TestRuleSet:
    """Test RuleSet collection model."""

    def _make_rule(
        self,
        rule_id: str = "rule_001",
        name: str = "Test Rule",
        priority: int = 0,
    ) -> CategoryRule:
        """Create a test rule."""
        return CategoryRule(
            rule_id=rule_id,
            name=name,
            conditions=[
                RuleCondition(
                    field=ConditionField.SENDER_DOMAIN,
                    operator=ConditionOperator.EQUALS,
                    value="example.com",
                ),
            ],
            action=RuleAction(
                action_type=RuleActionType.CATEGORIZE,
                target="Test Category",
            ),
            priority=priority,
        )

    def test_empty_ruleset(self):
        """Test creating an empty RuleSet."""
        rs = RuleSet(rules=[])
        assert len(rs.rules) == 0
        assert rs.version == "1.0"  # default

    def test_ruleset_with_rules(self):
        """Test creating a RuleSet with multiple rules."""
        rs = RuleSet(
            rules=[
                self._make_rule(rule_id="r1", name="Rule 1"),
                self._make_rule(rule_id="r2", name="Rule 2"),
            ]
        )
        assert len(rs.rules) == 2

    def test_version_default(self):
        """Test that version defaults to '1.0'."""
        rs = RuleSet(rules=[])
        assert rs.version == "1.0"

    def test_version_can_be_set(self):
        """Test that version can be explicitly set."""
        rs = RuleSet(rules=[], version="2.1")
        assert rs.version == "2.1"

    def test_created_date_auto_set(self):
        """Test that created_date is auto-populated."""
        rs = RuleSet(rules=[])
        assert rs.created_date is not None
        assert isinstance(rs.created_date, datetime)

    def test_last_modified_auto_set(self):
        """Test that last_modified is auto-populated."""
        rs = RuleSet(rules=[])
        assert rs.last_modified is not None
        assert isinstance(rs.last_modified, datetime)

    def test_description_optional(self):
        """Test description defaults to empty string."""
        rs = RuleSet(rules=[])
        assert rs.description == ""

    def test_description_can_be_set(self):
        """Test description can be set."""
        rs = RuleSet(rules=[], description="Auto-generated rules from approved categories")
        assert rs.description == "Auto-generated rules from approved categories"

    def test_source_category_ids_optional(self):
        """Test that source_category_ids is optional."""
        rs = RuleSet(rules=[])
        assert rs.source_category_ids == []

    def test_source_category_ids_can_be_set(self):
        """Test that source_category_ids can track origin categories."""
        rs = RuleSet(
            rules=[self._make_rule()],
            source_category_ids=["cat_01", "cat_02"],
        )
        assert rs.source_category_ids == ["cat_01", "cat_02"]

    def test_model_dump_roundtrip(self):
        """Test full RuleSet serialization and deserialization."""
        rs = RuleSet(
            rules=[
                self._make_rule(rule_id="r1", name="Rule A", priority=10),
                self._make_rule(rule_id="r2", name="Rule B", priority=5),
            ],
            version="1.2",
            description="Test ruleset",
            source_category_ids=["cat_01"],
        )
        data = rs.model_dump()
        restored = RuleSet.model_validate(data)
        assert len(restored.rules) == 2
        assert restored.version == "1.2"
        assert restored.description == "Test ruleset"
        assert restored.source_category_ids == ["cat_01"]

    def test_model_dump_json_serializable(self):
        """Test full RuleSet produces JSON-serializable output."""
        import json

        rs = RuleSet(
            rules=[self._make_rule()],
            version="1.0",
            description="Test",
        )
        data = rs.model_dump(mode="json")
        json_str = json.dumps(data)
        assert isinstance(json_str, str)

    def test_rule_count_property(self):
        """Test rule_count property."""
        rs = RuleSet(
            rules=[
                self._make_rule(rule_id="r1"),
                self._make_rule(rule_id="r2"),
                self._make_rule(rule_id="r3"),
            ]
        )
        assert rs.rule_count == 3

    def test_enabled_rules_property(self):
        """Test enabled_rules property filters correctly."""
        r1 = self._make_rule(rule_id="r1")
        r2 = self._make_rule(rule_id="r2")
        r2.enabled = False
        r3 = self._make_rule(rule_id="r3")

        rs = RuleSet(rules=[r1, r2, r3])
        enabled = rs.enabled_rules
        assert len(enabled) == 2
        assert all(r.enabled for r in enabled)

    def test_get_rules_by_priority(self):
        """Test get_rules_by_priority returns rules sorted by priority descending."""
        r_low = self._make_rule(rule_id="r_low", priority=1)
        r_high = self._make_rule(rule_id="r_high", priority=10)
        r_mid = self._make_rule(rule_id="r_mid", priority=5)

        rs = RuleSet(rules=[r_low, r_high, r_mid])
        sorted_rules = rs.get_rules_by_priority()
        assert sorted_rules[0].rule_id == "r_high"
        assert sorted_rules[1].rule_id == "r_mid"
        assert sorted_rules[2].rule_id == "r_low"

    def test_get_rule_by_id_found(self):
        """Test get_rule_by_id returns the correct rule."""
        r1 = self._make_rule(rule_id="r1")
        r2 = self._make_rule(rule_id="r2")
        rs = RuleSet(rules=[r1, r2])

        found = rs.get_rule_by_id("r2")
        assert found is not None
        assert found.rule_id == "r2"

    def test_get_rule_by_id_not_found(self):
        """Test get_rule_by_id returns None for missing ID."""
        rs = RuleSet(rules=[self._make_rule(rule_id="r1")])
        assert rs.get_rule_by_id("nonexistent") is None

    def test_duplicate_rule_ids_rejected(self):
        """Test that duplicate rule_ids are rejected."""
        with pytest.raises(ValueError):
            RuleSet(
                rules=[
                    self._make_rule(rule_id="r1"),
                    self._make_rule(rule_id="r1"),
                ]
            )


# =============================================================================
# Cross-model Integration Tests
# =============================================================================


class TestRuleModelIntegration:
    """Integration tests across rule models."""

    def test_full_rule_with_all_fields(self):
        """Test creating a fully populated rule with all optional fields."""
        conditions = [
            RuleCondition(
                field=ConditionField.SENDER_DOMAIN,
                operator=ConditionOperator.EQUALS,
                value="marketing.example.com",
                case_sensitive=False,
            ),
            RuleCondition(
                field=ConditionField.SUBJECT,
                operator=ConditionOperator.CONTAINS,
                value="promotion",
                case_sensitive=False,
            ),
            RuleCondition(
                field=ConditionField.HAS_ATTACHMENT,
                operator=ConditionOperator.EQUALS,
                value="false",
            ),
        ]
        action = RuleAction(
            action_type=RuleActionType.MOVE_TO_FOLDER,
            target="Marketing/Promotions",
            target_category_id="cat_marketing_promo",
        )
        rule = CategoryRule(
            rule_id="rule_marketing_001",
            name="Marketing Promotions",
            description="Matches promotional emails from marketing domain",
            conditions=conditions,
            action=action,
            logic=ConditionLogic.AND,
            priority=5,
            enabled=True,
            category_id="cat_marketing_promo",
        )

        assert rule.condition_count == 3
        assert rule.action.target == "Marketing/Promotions"
        assert rule.logic == ConditionLogic.AND

    def test_ruleset_from_dict_deep_nesting(self):
        """Test RuleSet can be reconstructed from deeply nested dict."""
        raw = {
            "version": "1.0",
            "description": "Test set",
            "source_category_ids": ["cat_01"],
            "rules": [
                {
                    "rule_id": "r1",
                    "name": "Rule One",
                    "description": "",
                    "conditions": [
                        {
                            "field": "sender_domain",
                            "operator": "equals",
                            "value": "test.com",
                            "case_sensitive": False,
                        }
                    ],
                    "action": {
                        "action_type": "categorize",
                        "target": "Test",
                        "target_category_id": None,
                    },
                    "logic": "and",
                    "priority": 0,
                    "enabled": True,
                    "category_id": None,
                }
            ],
        }
        # created_date/last_modified will use defaults since not in raw
        rs = RuleSet.model_validate(raw)
        assert rs.version == "1.0"
        assert len(rs.rules) == 1
        assert rs.rules[0].conditions[0].field == ConditionField.SENDER_DOMAIN

    def test_multiple_actions_across_rules(self):
        """Test a RuleSet with different action types across rules."""
        rules = [
            CategoryRule(
                rule_id="r1",
                name="Move Rule",
                conditions=[
                    RuleCondition(
                        field=ConditionField.SENDER_DOMAIN,
                        operator=ConditionOperator.EQUALS,
                        value="spam.com",
                    )
                ],
                action=RuleAction(
                    action_type=RuleActionType.MOVE_TO_FOLDER,
                    target="Junk",
                ),
            ),
            CategoryRule(
                rule_id="r2",
                name="Label Rule",
                conditions=[
                    RuleCondition(
                        field=ConditionField.SUBJECT,
                        operator=ConditionOperator.STARTS_WITH,
                        value="[URGENT]",
                    )
                ],
                action=RuleAction(
                    action_type=RuleActionType.APPLY_LABEL,
                    target="urgent",
                ),
            ),
            CategoryRule(
                rule_id="r3",
                name="Flag Rule",
                conditions=[
                    RuleCondition(
                        field=ConditionField.SENDER_NAME,
                        operator=ConditionOperator.CONTAINS,
                        value="CEO",
                    )
                ],
                action=RuleAction(
                    action_type=RuleActionType.FLAG,
                    target="important",
                ),
            ),
        ]
        rs = RuleSet(rules=rules)
        assert rs.rule_count == 3
        action_types = {r.action.action_type for r in rs.rules}
        assert action_types == {
            RuleActionType.MOVE_TO_FOLDER,
            RuleActionType.APPLY_LABEL,
            RuleActionType.FLAG,
        }
