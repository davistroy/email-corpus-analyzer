"""
Rule deployer for converting local CategoryRules to server-side inbox rules.

Phase 5, Item 5.3: Deploys rules to M365 (Graph API messageRules) and
Gmail (Filters API). Supports dry-run mode, conflict detection, and rollback.

M365 endpoint: POST /me/mailFolders/inbox/messageRules
Gmail endpoint: users.settings.filters.create()
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

import requests
from pydantic import BaseModel, Field

from src.models.rule import (
    CategoryRule,
    ConditionField,
    ConditionOperator,
    RuleActionType,
    RuleSet,
)
from src.utils.logger import get_logger

logger = get_logger(__name__)

GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"

# Operators that M365 Graph API messageRules do not support
_M365_UNSUPPORTED_OPERATORS = {
    ConditionOperator.MATCHES_REGEX,
    ConditionOperator.IN_LIST,
}

# Operators that Gmail filters do not natively support (mapped where possible)
_GMAIL_UNSUPPORTED_OPERATORS = {
    ConditionOperator.MATCHES_REGEX,
    ConditionOperator.IN_LIST,
    ConditionOperator.STARTS_WITH,
    ConditionOperator.ENDS_WITH,
}

VALID_SOURCES = {"m365", "gmail"}


# =============================================================================
# Models
# =============================================================================


class DeploymentStatus(str, Enum):
    """Status of a deployed rule."""

    DEPLOYED = "deployed"
    FAILED = "failed"
    SKIPPED = "skipped"
    DRY_RUN = "dry_run"
    ROLLED_BACK = "rolled_back"


class DeployedRuleRecord(BaseModel):
    """Record of a single rule deployment attempt."""

    local_rule_id: str = Field(..., description="Local CategoryRule ID")
    server_rule_id: str | None = Field(default=None, description="Server-assigned rule/filter ID")
    source: str = Field(..., description="Target platform (m365 or gmail)")
    status: DeploymentStatus = Field(..., description="Deployment outcome")
    payload: dict[str, Any] | None = Field(
        default=None, description="Converted payload sent to server (or would-be sent in dry-run)"
    )
    deployed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp of the deployment attempt",
    )


class RuleConflict(BaseModel):
    """Represents a conflict between a local rule and an existing server rule."""

    local_rule_id: str = Field(..., description="Local CategoryRule ID")
    server_rule_id: str = Field(..., description="Existing server rule/filter ID")
    server_rule_name: str = Field(default="", description="Display name of existing rule")
    description: str = Field(default="", description="Human-readable description of the conflict")
    overlapping_conditions: list[str] = Field(
        default_factory=list, description="Conditions that overlap"
    )


class DeploymentResult(BaseModel):
    """Result of a rule deployment operation (deploy or rollback)."""

    deployed_rules: list[DeployedRuleRecord] = Field(
        default_factory=list, description="Individual rule deployment records"
    )
    failures: dict[str, str] = Field(
        default_factory=dict, description="Map of rule_id -> error message for failures"
    )
    conflicts: list[RuleConflict] = Field(
        default_factory=list, description="Detected conflicts with existing server rules"
    )
    dry_run: bool = Field(
        default=False, description="Whether this was a dry-run (no actual API calls)"
    )

    @property
    def total(self) -> int:
        """Total number of rules processed."""
        return len(self.deployed_rules)

    @property
    def succeeded(self) -> int:
        """Number of successfully deployed rules."""
        return sum(1 for r in self.deployed_rules if r.status == DeploymentStatus.DEPLOYED)

    @property
    def failed(self) -> int:
        """Number of failed deployments."""
        return sum(1 for r in self.deployed_rules if r.status == DeploymentStatus.FAILED)

    @property
    def skipped(self) -> int:
        """Number of skipped rules (disabled, dry-run non-applicable, etc.)."""
        return sum(1 for r in self.deployed_rules if r.status == DeploymentStatus.SKIPPED)


# =============================================================================
# RuleDeployer
# =============================================================================


class RuleDeployer:
    """
    Deploys local CategoryRules as server-side inbox rules.

    Supports:
    - M365: Graph API messageRules (POST /me/mailFolders/inbox/messageRules)
    - Gmail: Gmail Filters API (users.settings.filters.create)
    - Dry-run mode: show payloads without making API calls
    - Conflict detection: check existing server rules for overlaps
    - Rollback: delete previously deployed server rules
    """

    def __init__(self, source: str, dry_run: bool = False) -> None:
        """
        Initialize the deployer.

        Args:
            source: Target platform ("m365" or "gmail")
            dry_run: If True, no API calls will be made

        Raises:
            ValueError: If source is not "m365" or "gmail"
        """
        if source not in VALID_SOURCES:
            raise ValueError(
                f"Invalid source '{source}'. Must be one of: {', '.join(sorted(VALID_SOURCES))}"
            )
        self.source = source
        self.dry_run = dry_run

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def deploy_rules(
        self,
        rule_set: RuleSet,
        access_token: str | None = None,
    ) -> DeploymentResult:
        """
        Deploy all enabled rules in the RuleSet to the server.

        Args:
            rule_set: The RuleSet containing rules to deploy
            access_token: OAuth token for M365 (required for M365, ignored for Gmail)

        Returns:
            DeploymentResult with per-rule outcomes

        Raises:
            ValueError: If M365 is targeted and no access_token is provided
                        (unless dry_run is True)
        """
        if self.source == "m365" and access_token is None and not self.dry_run:
            raise ValueError(
                "access_token is required for M365 deployment. "
                "Authenticate with GraphAPIClient first."
            )

        result = DeploymentResult(dry_run=self.dry_run)

        for rule in rule_set.rules:
            if not rule.enabled:
                result.deployed_rules.append(
                    DeployedRuleRecord(
                        local_rule_id=rule.rule_id,
                        server_rule_id=None,
                        source=self.source,
                        status=DeploymentStatus.SKIPPED,
                    )
                )
                continue

            if self.source == "m365":
                self._deploy_m365_rule(rule, access_token, result)
            else:
                self._deploy_gmail_rule(rule, result)

        if result.succeeded > 0 or (self.dry_run and result.total > 0):
            logger.info(
                f"Deployment {'(dry-run) ' if self.dry_run else ''}complete: "
                f"{result.succeeded} deployed, {result.failed} failed, "
                f"{result.skipped} skipped"
            )
        return result

    def check_conflicts(
        self,
        rule_set: RuleSet,
        access_token: str | None = None,
    ) -> list[RuleConflict]:
        """
        Check for conflicts between local rules and existing server rules.

        Args:
            rule_set: The RuleSet to check
            access_token: OAuth token for M365 (required for M365)

        Returns:
            List of detected RuleConflict objects. Empty list if no conflicts
            or if the check fails gracefully.
        """
        try:
            if self.source == "m365":
                return self._check_m365_conflicts(rule_set, access_token)
            return self._check_gmail_conflicts(rule_set)
        except Exception as e:
            logger.warning(f"Conflict check failed: {e}. Proceeding without conflict data.")
            return []

    def rollback(
        self,
        deployment_result: DeploymentResult,
        access_token: str | None = None,
    ) -> DeploymentResult:
        """
        Roll back a previous deployment by deleting deployed server rules.

        Args:
            deployment_result: Previous DeploymentResult containing deployed rule records
            access_token: OAuth token for M365

        Returns:
            New DeploymentResult describing the rollback outcome
        """
        rollback_result = DeploymentResult()

        for record in deployment_result.deployed_rules:
            if record.status != DeploymentStatus.DEPLOYED:
                rollback_result.deployed_rules.append(
                    DeployedRuleRecord(
                        local_rule_id=record.local_rule_id,
                        server_rule_id=record.server_rule_id,
                        source=record.source,
                        status=DeploymentStatus.SKIPPED,
                    )
                )
                continue

            if self.source == "m365":
                self._rollback_m365_rule(record, access_token, rollback_result)
            else:
                self._rollback_gmail_rule(record, rollback_result)

        if rollback_result.total > 0:
            logger.info(
                f"Rollback complete: {rollback_result.succeeded} removed, "
                f"{rollback_result.failed} failed, {rollback_result.skipped} skipped"
            )
        return rollback_result

    def validate_rules(self, rule_set: RuleSet) -> list[str]:
        """
        Validate rules for compatibility with the target platform.

        Checks for unsupported operators, missing required fields, and
        platform-specific limitations.

        Args:
            rule_set: The RuleSet to validate

        Returns:
            List of validation error/warning strings. Empty if all valid.
        """
        errors: list[str] = []

        unsupported = (
            _M365_UNSUPPORTED_OPERATORS if self.source == "m365" else _GMAIL_UNSUPPORTED_OPERATORS
        )

        for rule in rule_set.rules:
            for condition in rule.conditions:
                if condition.operator in unsupported:
                    errors.append(
                        f"Rule '{rule.name}' (id={rule.rule_id}): "
                        f"Unsupported operator '{condition.operator.value}' "
                        f"for {self.source}. Field: {condition.field.value}"
                    )

        return errors

    # -------------------------------------------------------------------------
    # M365 rule conversion
    # -------------------------------------------------------------------------

    def _convert_to_m365_rule(self, rule: CategoryRule) -> dict[str, Any]:
        """
        Convert a CategoryRule to a Graph API messageRules payload.

        See: https://learn.microsoft.com/en-us/graph/api/resources/messagerule

        Args:
            rule: The CategoryRule to convert

        Returns:
            Dict payload suitable for POST to /me/mailFolders/inbox/messageRules
        """
        conditions: dict[str, Any] = {}
        for condition in rule.conditions:
            self._add_m365_condition(conditions, condition)

        actions: dict[str, Any] = {}
        self._add_m365_action(actions, rule)

        return {
            "displayName": rule.name,
            "sequence": rule.priority,
            "isEnabled": rule.enabled,
            "conditions": conditions,
            "actions": actions,
        }

    def _add_m365_condition(
        self,
        conditions: dict[str, Any],
        condition: Any,
    ) -> None:
        """Map a single RuleCondition to M365 messageRule condition fields."""
        field = condition.field
        value = condition.value

        if field == ConditionField.SENDER_DOMAIN:
            conditions.setdefault("senderContains", []).append(value)
        elif field == ConditionField.SENDER_EMAIL:
            conditions.setdefault("fromAddresses", []).append({"emailAddress": {"address": value}})
        elif field == ConditionField.SENDER_NAME:
            conditions.setdefault("senderContains", []).append(value)
        elif field == ConditionField.SUBJECT:
            conditions.setdefault("subjectContains", []).append(value)
        elif field == ConditionField.BODY:
            conditions.setdefault("bodyContains", []).append(value)
        elif field == ConditionField.HAS_ATTACHMENT:
            conditions["hasAttachments"] = value.lower() == "true"
        elif field == ConditionField.RECIPIENT_EMAIL:
            conditions.setdefault("recipientContains", []).append(value)

    def _add_m365_action(
        self,
        actions: dict[str, Any],
        rule: CategoryRule,
    ) -> None:
        """Map the rule action to M365 messageRule action fields."""
        action = rule.action

        if action.action_type == RuleActionType.MOVE_TO_FOLDER:
            # moveToFolder requires a folder ID; use target as placeholder
            # (caller should resolve folder name to ID via FolderManager)
            actions["moveToFolder"] = action.target
        elif action.action_type == RuleActionType.APPLY_LABEL:
            # M365 doesn't have labels; map to categories
            actions.setdefault("assignCategories", []).append(action.target)
        elif action.action_type == RuleActionType.FLAG:
            actions["flagMessage"] = {"followUpStatus": "flagged"}
        elif action.action_type in (RuleActionType.CATEGORIZE, RuleActionType.TAG):
            actions.setdefault("assignCategories", []).append(action.target)

    # -------------------------------------------------------------------------
    # Gmail filter conversion
    # -------------------------------------------------------------------------

    def _convert_to_gmail_filter(self, rule: CategoryRule) -> dict[str, Any]:
        """
        Convert a CategoryRule to a Gmail filter payload.

        See: https://developers.google.com/gmail/api/reference/rest/v1/users.settings.filters

        Args:
            rule: The CategoryRule to convert

        Returns:
            Dict payload suitable for users.settings.filters.create()
        """
        criteria: dict[str, Any] = {}
        for condition in rule.conditions:
            self._add_gmail_criteria(criteria, condition)

        action: dict[str, Any] = {}
        self._add_gmail_action(action, rule)

        return {
            "criteria": criteria,
            "action": action,
        }

    def _add_gmail_criteria(
        self,
        criteria: dict[str, Any],
        condition: Any,
    ) -> None:
        """Map a single RuleCondition to Gmail filter criteria fields."""
        field = condition.field
        operator = condition.operator
        value = condition.value

        if field in (
            ConditionField.SENDER_DOMAIN,
            ConditionField.SENDER_EMAIL,
            ConditionField.SENDER_NAME,
        ):
            existing = criteria.get("from", "")
            criteria["from"] = f"{existing} {value}".strip() if existing else value
        elif field == ConditionField.SUBJECT:
            if operator == ConditionOperator.NOT_CONTAINS:
                existing = criteria.get("negatedQuery", "")
                criteria["negatedQuery"] = (
                    f"{existing} subject:{value}".strip() if existing else f"subject:{value}"
                )
            else:
                existing = criteria.get("subject", "")
                criteria["subject"] = f"{existing} {value}".strip() if existing else value
        elif field == ConditionField.BODY:
            existing = criteria.get("query", "")
            criteria["query"] = f"{existing} {value}".strip() if existing else value
        elif field == ConditionField.HAS_ATTACHMENT:
            criteria["hasAttachment"] = value.lower() == "true"
        elif field == ConditionField.RECIPIENT_EMAIL:
            existing = criteria.get("to", "")
            criteria["to"] = f"{existing} {value}".strip() if existing else value

    def _add_gmail_action(
        self,
        action: dict[str, Any],
        rule: CategoryRule,
    ) -> None:
        """Map the rule action to Gmail filter action fields."""
        rule_action = rule.action

        if rule_action.action_type in (
            RuleActionType.MOVE_TO_FOLDER,
            RuleActionType.APPLY_LABEL,
            RuleActionType.CATEGORIZE,
            RuleActionType.TAG,
        ):
            # Gmail uses labels for folders; the target name is the label
            # Caller should resolve label name to ID via Gmail API
            action.setdefault("addLabelIds", []).append(rule_action.target)
        elif rule_action.action_type == RuleActionType.FLAG:
            action["addLabelIds"] = action.get("addLabelIds", []) + ["STARRED"]

    # -------------------------------------------------------------------------
    # M365 deployment
    # -------------------------------------------------------------------------

    def _deploy_m365_rule(
        self,
        rule: CategoryRule,
        access_token: str | None,
        result: DeploymentResult,
    ) -> None:
        """Deploy a single rule to M365 via Graph API."""
        payload = self._convert_to_m365_rule(rule)

        if self.dry_run:
            result.deployed_rules.append(
                DeployedRuleRecord(
                    local_rule_id=rule.rule_id,
                    server_rule_id=None,
                    source="m365",
                    status=DeploymentStatus.DRY_RUN,
                    payload=payload,
                )
            )
            return

        url = f"{GRAPH_BASE_URL}/me/mailFolders/inbox/messageRules"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            data = response.json()
            server_rule_id = data.get("id")

            result.deployed_rules.append(
                DeployedRuleRecord(
                    local_rule_id=rule.rule_id,
                    server_rule_id=server_rule_id,
                    source="m365",
                    status=DeploymentStatus.DEPLOYED,
                    payload=payload,
                )
            )
            logger.info(f"Deployed M365 rule: {rule.name} (server id: {server_rule_id})")

        except Exception as e:
            error_msg = str(e)
            result.deployed_rules.append(
                DeployedRuleRecord(
                    local_rule_id=rule.rule_id,
                    server_rule_id=None,
                    source="m365",
                    status=DeploymentStatus.FAILED,
                    payload=payload,
                )
            )
            result.failures[rule.rule_id] = error_msg
            logger.error(f"Failed to deploy M365 rule '{rule.name}': {error_msg}")

    # -------------------------------------------------------------------------
    # Gmail deployment
    # -------------------------------------------------------------------------

    def _deploy_gmail_rule(
        self,
        rule: CategoryRule,
        result: DeploymentResult,
    ) -> None:
        """Deploy a single rule to Gmail as a filter."""
        payload = self._convert_to_gmail_filter(rule)

        if self.dry_run:
            result.deployed_rules.append(
                DeployedRuleRecord(
                    local_rule_id=rule.rule_id,
                    server_rule_id=None,
                    source="gmail",
                    status=DeploymentStatus.DRY_RUN,
                    payload=payload,
                )
            )
            return

        try:
            service = self._get_gmail_service()
            created = (
                service.users().settings().filters().create(userId="me", body=payload).execute()
            )
            server_filter_id = created.get("id")

            result.deployed_rules.append(
                DeployedRuleRecord(
                    local_rule_id=rule.rule_id,
                    server_rule_id=server_filter_id,
                    source="gmail",
                    status=DeploymentStatus.DEPLOYED,
                    payload=payload,
                )
            )
            logger.info(f"Deployed Gmail filter: {rule.name} (server id: {server_filter_id})")

        except Exception as e:
            error_msg = str(e)
            result.deployed_rules.append(
                DeployedRuleRecord(
                    local_rule_id=rule.rule_id,
                    server_rule_id=None,
                    source="gmail",
                    status=DeploymentStatus.FAILED,
                    payload=payload,
                )
            )
            result.failures[rule.rule_id] = error_msg
            logger.error(f"Failed to deploy Gmail filter '{rule.name}': {error_msg}")

    # -------------------------------------------------------------------------
    # M365 conflict detection
    # -------------------------------------------------------------------------

    def _check_m365_conflicts(
        self,
        rule_set: RuleSet,
        access_token: str | None,
    ) -> list[RuleConflict]:
        """Fetch existing M365 messageRules and check for overlaps."""
        url = f"{GRAPH_BASE_URL}/me/mailFolders/inbox/messageRules"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        existing_rules = response.json().get("value", [])

        conflicts: list[RuleConflict] = []

        for local_rule in rule_set.rules:
            local_payload = self._convert_to_m365_rule(local_rule)
            local_conditions = local_payload.get("conditions", {})

            for server_rule in existing_rules:
                server_conditions = server_rule.get("conditions", {})
                overlaps = self._find_m365_condition_overlaps(local_conditions, server_conditions)
                if overlaps:
                    conflicts.append(
                        RuleConflict(
                            local_rule_id=local_rule.rule_id,
                            server_rule_id=server_rule.get("id", "unknown"),
                            server_rule_name=server_rule.get("displayName", ""),
                            description=(
                                f"Overlapping conditions with existing rule "
                                f"'{server_rule.get('displayName', 'unnamed')}'"
                            ),
                            overlapping_conditions=overlaps,
                        )
                    )

        return conflicts

    def _find_m365_condition_overlaps(
        self,
        local: dict[str, Any],
        server: dict[str, Any],
    ) -> list[str]:
        """Find overlapping condition values between local and server rules."""
        overlaps: list[str] = []

        # Check senderContains overlap
        local_senders = {s.lower() for s in local.get("senderContains", [])}
        server_senders = {s.lower() for s in server.get("senderContains", [])}
        for overlap in local_senders & server_senders:
            overlaps.append(f"senderContains: {overlap}")

        # Check subjectContains overlap
        local_subjects = {s.lower() for s in local.get("subjectContains", [])}
        server_subjects = {s.lower() for s in server.get("subjectContains", [])}
        for overlap in local_subjects & server_subjects:
            overlaps.append(f"subjectContains: {overlap}")

        # Check bodyContains overlap
        local_body = {s.lower() for s in local.get("bodyContains", [])}
        server_body = {s.lower() for s in server.get("bodyContains", [])}
        for overlap in local_body & server_body:
            overlaps.append(f"bodyContains: {overlap}")

        # Check hasAttachments overlap
        if (
            "hasAttachments" in local
            and "hasAttachments" in server
            and local["hasAttachments"] == server["hasAttachments"]
        ):
            overlaps.append("hasAttachments")

        # Check fromAddresses overlap
        local_from = set()
        for addr in local.get("fromAddresses", []):
            email = addr.get("emailAddress", {}).get("address", "").lower()
            if email:
                local_from.add(email)
        server_from = set()
        for addr in server.get("fromAddresses", []):
            email = addr.get("emailAddress", {}).get("address", "").lower()
            if email:
                server_from.add(email)
        for overlap in local_from & server_from:
            overlaps.append(f"fromAddresses: {overlap}")

        return overlaps

    # -------------------------------------------------------------------------
    # Gmail conflict detection
    # -------------------------------------------------------------------------

    def _check_gmail_conflicts(
        self,
        rule_set: RuleSet,
    ) -> list[RuleConflict]:
        """Fetch existing Gmail filters and check for overlaps."""
        service = self._get_gmail_service()
        result = service.users().settings().filters().list(userId="me").execute()
        existing_filters = result.get("filter", [])

        conflicts: list[RuleConflict] = []

        for local_rule in rule_set.rules:
            local_payload = self._convert_to_gmail_filter(local_rule)
            local_criteria = local_payload.get("criteria", {})

            for server_filter in existing_filters:
                server_criteria = server_filter.get("criteria", {})
                overlaps = self._find_gmail_criteria_overlaps(local_criteria, server_criteria)
                if overlaps:
                    conflicts.append(
                        RuleConflict(
                            local_rule_id=local_rule.rule_id,
                            server_rule_id=server_filter.get("id", "unknown"),
                            description="Overlapping criteria with existing Gmail filter",
                            overlapping_conditions=overlaps,
                        )
                    )

        return conflicts

    def _find_gmail_criteria_overlaps(
        self,
        local: dict[str, Any],
        server: dict[str, Any],
    ) -> list[str]:
        """Find overlapping criteria values between local and server filters."""
        overlaps: list[str] = []

        # Check 'from' overlap
        local_from = local.get("from", "").lower()
        server_from = server.get("from", "").lower()
        if local_from and server_from and (local_from in server_from or server_from in local_from):
            overlaps.append(f"from: {local_from}")

        # Check 'subject' overlap
        local_subject = local.get("subject", "").lower()
        server_subject = server.get("subject", "").lower()
        if (
            local_subject
            and server_subject
            and (local_subject in server_subject or server_subject in local_subject)
        ):
            overlaps.append(f"subject: {local_subject}")

        # Check 'query' overlap
        local_query = local.get("query", "").lower()
        server_query = server.get("query", "").lower()
        if (
            local_query
            and server_query
            and (local_query in server_query or server_query in local_query)
        ):
            overlaps.append(f"query: {local_query}")

        # Check 'hasAttachment' overlap
        if (
            "hasAttachment" in local
            and "hasAttachment" in server
            and local["hasAttachment"] == server["hasAttachment"]
        ):
            overlaps.append("hasAttachment")

        return overlaps

    # -------------------------------------------------------------------------
    # M365 rollback
    # -------------------------------------------------------------------------

    def _rollback_m365_rule(
        self,
        record: DeployedRuleRecord,
        access_token: str | None,
        result: DeploymentResult,
    ) -> None:
        """Delete a previously deployed M365 messageRule."""
        url = f"{GRAPH_BASE_URL}/me/mailFolders/inbox/messageRules/{record.server_rule_id}"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        try:
            response = requests.delete(url, headers=headers, timeout=30)
            response.raise_for_status()

            result.deployed_rules.append(
                DeployedRuleRecord(
                    local_rule_id=record.local_rule_id,
                    server_rule_id=record.server_rule_id,
                    source="m365",
                    status=DeploymentStatus.DEPLOYED,
                )
            )
            logger.info(f"Rolled back M365 rule: {record.server_rule_id}")

        except Exception as e:
            error_msg = str(e)
            result.deployed_rules.append(
                DeployedRuleRecord(
                    local_rule_id=record.local_rule_id,
                    server_rule_id=record.server_rule_id,
                    source="m365",
                    status=DeploymentStatus.FAILED,
                )
            )
            result.failures[record.local_rule_id] = error_msg
            logger.error(f"Failed to rollback M365 rule {record.server_rule_id}: {error_msg}")

    # -------------------------------------------------------------------------
    # Gmail rollback
    # -------------------------------------------------------------------------

    def _rollback_gmail_rule(
        self,
        record: DeployedRuleRecord,
        result: DeploymentResult,
    ) -> None:
        """Delete a previously deployed Gmail filter."""
        try:
            service = self._get_gmail_service()
            (
                service.users()
                .settings()
                .filters()
                .delete(userId="me", id=record.server_rule_id)
                .execute()
            )

            result.deployed_rules.append(
                DeployedRuleRecord(
                    local_rule_id=record.local_rule_id,
                    server_rule_id=record.server_rule_id,
                    source="gmail",
                    status=DeploymentStatus.DEPLOYED,
                )
            )
            logger.info(f"Rolled back Gmail filter: {record.server_rule_id}")

        except Exception as e:
            error_msg = str(e)
            result.deployed_rules.append(
                DeployedRuleRecord(
                    local_rule_id=record.local_rule_id,
                    server_rule_id=record.server_rule_id,
                    source="gmail",
                    status=DeploymentStatus.FAILED,
                )
            )
            result.failures[record.local_rule_id] = error_msg
            logger.error(f"Failed to rollback Gmail filter {record.server_rule_id}: {error_msg}")

    # -------------------------------------------------------------------------
    # Gmail service helper
    # -------------------------------------------------------------------------

    def _get_gmail_service(self):
        """
        Get authenticated Gmail API service.

        This is a separate method to facilitate mocking in tests.
        In production, this would use GmailClient's authentication flow.

        Returns:
            Gmail API service object
        """
        from src.extractors.gmail_client import GmailClient

        client = GmailClient(user_email="")
        return client._get_service()
