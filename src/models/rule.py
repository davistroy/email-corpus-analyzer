"""
Rule data models for category rule refinement (Phase 3, Item 3.1).

Defines the core rule primitives:
- RuleCondition: A single match condition (field + operator + value)
- RuleAction: What to do when a rule matches (categorize, move, label, etc.)
- CategoryRule: A named rule combining conditions, logic, action, and metadata
- RuleSet: A versioned collection of CategoryRules with persistence support
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field, model_validator

# =============================================================================
# Enums
# =============================================================================


class ConditionField(str, Enum):
    """Email fields that can be matched by a rule condition."""

    SENDER_EMAIL = "sender_email"
    SENDER_DOMAIN = "sender_domain"
    SENDER_NAME = "sender_name"
    SUBJECT = "subject"
    BODY = "body"
    HAS_ATTACHMENT = "has_attachment"
    RECIPIENT_EMAIL = "recipient_email"


class ConditionOperator(str, Enum):
    """Operators for comparing a field value against the condition value."""

    CONTAINS = "contains"
    EQUALS = "equals"
    MATCHES_REGEX = "matches_regex"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"
    IN_LIST = "in_list"
    NOT_CONTAINS = "not_contains"
    NOT_EQUALS = "not_equals"


class ConditionLogic(str, Enum):
    """Logic for combining multiple conditions in a rule."""

    AND = "and"
    OR = "or"


class RuleActionType(str, Enum):
    """Types of actions a rule can perform when matched."""

    MOVE_TO_FOLDER = "move_to_folder"
    APPLY_LABEL = "apply_label"
    CATEGORIZE = "categorize"
    TAG = "tag"
    FLAG = "flag"


# =============================================================================
# Models
# =============================================================================


class RuleCondition(BaseModel):
    """
    A single match condition within a rule.

    Specifies which email field to inspect, what operator to apply,
    and the value to compare against.
    """

    field: ConditionField = Field(..., description="Email field to match against")
    operator: ConditionOperator = Field(..., description="Comparison operator")
    value: str = Field(..., min_length=1, description="Value to compare against")
    case_sensitive: bool = Field(
        default=False,
        description="Whether the comparison is case-sensitive (default: case-insensitive)",
    )


class RuleAction(BaseModel):
    """
    Action to perform when a rule's conditions are satisfied.

    Specifies the action type and target (folder name, label, category name, etc.).
    """

    action_type: RuleActionType = Field(..., description="Type of action to perform")
    target: str = Field(
        ...,
        min_length=1,
        description="Target for the action (folder path, label name, category name)",
    )
    target_category_id: str | None = Field(
        default=None,
        description="Category ID reference when action_type is 'categorize'",
    )


class CategoryRule(BaseModel):
    """
    A named rule that combines conditions, logic, an action, and metadata.

    Rules are evaluated against individual emails. When all (AND) or any (OR)
    conditions match, the associated action is triggered.
    """

    rule_id: str = Field(..., min_length=1, description="Unique rule identifier")
    name: str = Field(..., min_length=1, description="Human-readable rule name")
    description: str = Field(
        default="",
        description="Optional description of what this rule matches",
    )
    conditions: list[RuleCondition] = Field(
        ..., min_length=1, description="List of conditions (at least one required)"
    )
    action: RuleAction = Field(..., description="Action to perform when conditions match")
    logic: ConditionLogic = Field(
        default=ConditionLogic.AND,
        description="How to combine multiple conditions (AND = all must match, OR = any must match)",
    )
    priority: int = Field(
        default=0,
        description="Rule priority (higher values evaluated first)",
    )
    enabled: bool = Field(
        default=True,
        description="Whether this rule is active",
    )
    category_id: str | None = Field(
        default=None,
        description="Category ID this rule is associated with (cross-reference)",
    )
    created_date: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the rule was created",
    )
    last_modified: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the rule was last modified",
    )

    @property
    def condition_count(self) -> int:
        """Return the number of conditions in this rule."""
        return len(self.conditions)


class RuleSet(BaseModel):
    """
    A versioned collection of CategoryRules with metadata.

    Supports serialization to/from JSON for persistence.
    """

    rules: list[CategoryRule] = Field(
        default_factory=list,
        description="List of category rules",
    )
    version: str = Field(
        default="1.0",
        description="Schema version for forward compatibility",
    )
    description: str = Field(
        default="",
        description="Description of this rule set",
    )
    created_date: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When this rule set was created",
    )
    last_modified: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When this rule set was last modified",
    )
    source_category_ids: list[str] = Field(
        default_factory=list,
        description="Category IDs that were used to generate these rules",
    )

    @model_validator(mode="after")
    def _validate_unique_rule_ids(self) -> RuleSet:
        """Ensure all rule IDs within the set are unique."""
        ids = [r.rule_id for r in self.rules]
        if len(ids) != len(set(ids)):
            duplicates = [rid for rid in ids if ids.count(rid) > 1]
            raise ValueError(f"Duplicate rule IDs found: {set(duplicates)}")
        return self

    @property
    def rule_count(self) -> int:
        """Return the total number of rules."""
        return len(self.rules)

    @property
    def enabled_rules(self) -> list[CategoryRule]:
        """Return only enabled rules."""
        return [r for r in self.rules if r.enabled]

    def get_rules_by_priority(self) -> list[CategoryRule]:
        """Return rules sorted by priority (highest first)."""
        return sorted(self.rules, key=lambda r: r.priority, reverse=True)

    def get_rule_by_id(self, rule_id: str) -> CategoryRule | None:
        """Find a rule by its ID, or return None if not found."""
        for rule in self.rules:
            if rule.rule_id == rule_id:
                return rule
        return None
