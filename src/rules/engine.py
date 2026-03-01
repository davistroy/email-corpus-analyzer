"""
Rule engine for evaluating category rules against emails (Phase 3, Item 3.2).

Provides:
- evaluate_condition(): Evaluate a single RuleCondition against an Email
- evaluate_rule(): Evaluate a CategoryRule (all conditions with AND/OR logic, short-circuit)
- evaluate_all(): Evaluate a RuleSet against an Email, return matching rules sorted by priority
"""

from __future__ import annotations

import re

from src.models.email import Email
from src.models.rule import (
    CategoryRule,
    ConditionField,
    ConditionLogic,
    ConditionOperator,
    RuleCondition,
    RuleSet,
)

# Map ConditionField enum values to Email attribute names.
_FIELD_TO_ATTR: dict[ConditionField, str] = {
    ConditionField.SENDER_EMAIL: "sender_email",
    ConditionField.SENDER_DOMAIN: "sender_domain",
    ConditionField.SENDER_NAME: "sender_name",
    ConditionField.SUBJECT: "subject",
    ConditionField.BODY: "body_text",
    ConditionField.RECIPIENT_EMAIL: "recipient_email",
}


class RuleEngine:
    """Evaluate category rules against emails.

    Supports all condition operators (contains, equals, matches_regex,
    starts_with, ends_with, not_contains, not_equals, in_list) and all
    condition fields (sender_email, sender_domain, sender_name, subject,
    body, has_attachment, recipient_email).

    Condition logic is AND (all must match) or OR (any must match) with
    short-circuit evaluation for performance.
    """

    def _get_field_value(self, field: ConditionField, email: Email) -> str | None:
        """Extract the string value for a condition field from an email.

        For boolean fields (HAS_ATTACHMENT), returns 'true' or 'false'.
        For nullable fields (recipient_email), may return None.
        """
        if field == ConditionField.HAS_ATTACHMENT:
            return "true" if email.has_attachments else "false"
        attr = _FIELD_TO_ATTR.get(field)
        if attr is None:
            return None  # pragma: no cover
        return getattr(email, attr, None)

    def evaluate_condition(self, condition: RuleCondition, email: Email) -> bool:
        """Evaluate a single condition against an email.

        Args:
            condition: The rule condition to evaluate.
            email: The email to test against.

        Returns:
            True if the condition matches, False otherwise.
            Invalid regex patterns return False (not raise).
            None field values return False for positive operators,
            True for negative operators (NOT_CONTAINS, NOT_EQUALS).
        """
        field_value = self._get_field_value(condition.field, email)

        # Handle None field values
        if field_value is None:
            return condition.operator in (
                ConditionOperator.NOT_CONTAINS,
                ConditionOperator.NOT_EQUALS,
            )

        cond_value = condition.value

        # Apply case normalization unless case_sensitive
        if not condition.case_sensitive:
            field_value = field_value.lower()
            cond_value = cond_value.lower()

        op = condition.operator

        if op == ConditionOperator.CONTAINS:
            return cond_value in field_value

        if op == ConditionOperator.EQUALS:
            return field_value == cond_value

        if op == ConditionOperator.STARTS_WITH:
            return field_value.startswith(cond_value)

        if op == ConditionOperator.ENDS_WITH:
            return field_value.endswith(cond_value)

        if op == ConditionOperator.MATCHES_REGEX:
            try:
                flags = 0 if condition.case_sensitive else re.IGNORECASE
                # Use the original values for regex to let re.IGNORECASE handle case
                original_field = self._get_field_value(condition.field, email) or ""
                return bool(re.search(condition.value, original_field, flags))
            except re.error:
                return False

        if op == ConditionOperator.IN_LIST:
            items = [item.strip() for item in condition.value.split(",")]
            if not condition.case_sensitive:
                items = [item.lower() for item in items]
            return field_value in items

        if op == ConditionOperator.NOT_CONTAINS:
            return cond_value not in field_value

        if op == ConditionOperator.NOT_EQUALS:
            return field_value != cond_value

        return False  # pragma: no cover — unreachable with exhaustive enum

    def evaluate_rule(self, rule: CategoryRule, email: Email) -> bool:
        """Evaluate a rule's conditions against an email using AND/OR logic.

        Disabled rules always return False. Short-circuit evaluation is used:
        - AND logic stops on first False condition.
        - OR logic stops on first True condition.

        Args:
            rule: The category rule to evaluate.
            email: The email to test against.

        Returns:
            True if the rule matches the email, False otherwise.
        """
        if not rule.enabled:
            return False

        if rule.logic == ConditionLogic.AND:
            return all(self.evaluate_condition(condition, email) for condition in rule.conditions)
        # OR
        return any(self.evaluate_condition(condition, email) for condition in rule.conditions)

    def evaluate_all(self, rule_set: RuleSet, email: Email) -> list[CategoryRule]:
        """Evaluate all enabled rules in a RuleSet against an email.

        Returns matching rules sorted by priority (highest first).

        Args:
            rule_set: The set of rules to evaluate.
            email: The email to test against.

        Returns:
            List of matching CategoryRule objects, sorted by priority descending.
        """
        matches = [rule for rule in rule_set.rules if self.evaluate_rule(rule, email)]
        matches.sort(key=lambda r: r.priority, reverse=True)
        return matches
