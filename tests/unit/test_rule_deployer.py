"""
Unit tests for RuleDeployer (Phase 5, Item 5.3).

Tests server-side rule deployment to M365 (Graph API messageRules) and
Gmail (Filters API), including dry-run mode, conflict detection, rollback,
and error handling. All external API calls are mocked.

TDD: These tests are written first, implementation follows.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.actions.rule_deployer import (
    DeployedRuleRecord,
    DeploymentResult,
    DeploymentStatus,
    RuleConflict,
    RuleDeployer,
)
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


def _make_condition(
    field: ConditionField = ConditionField.SENDER_DOMAIN,
    operator: ConditionOperator = ConditionOperator.EQUALS,
    value: str = "example.com",
) -> RuleCondition:
    return RuleCondition(field=field, operator=operator, value=value)


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
            action_type=RuleActionType.MOVE_TO_FOLDER,
            target="Test Folder",
        ),
        logic=logic,
        priority=priority,
        enabled=enabled,
    )


def _make_rule_set(rules: list[CategoryRule] | None = None) -> RuleSet:
    if rules is None:
        rules = [_make_rule()]
    return RuleSet(rules=rules)


# =============================================================================
# DeploymentResult model tests
# =============================================================================


class TestDeploymentResultModel:
    """Tests for DeploymentResult data model."""

    def test_empty_result(self):
        result = DeploymentResult()
        assert result.total == 0
        assert result.succeeded == 0
        assert result.failed == 0
        assert result.skipped == 0
        assert result.deployed_rules == []
        assert result.failures == {}
        assert result.conflicts == []
        assert result.dry_run is False

    def test_result_with_deployed_rules(self):
        record = DeployedRuleRecord(
            local_rule_id="rule_001",
            server_rule_id="srv_abc",
            source="m365",
            status=DeploymentStatus.DEPLOYED,
        )
        result = DeploymentResult(deployed_rules=[record])
        assert result.total == 1
        assert result.succeeded == 1
        assert result.failed == 0

    def test_result_counts_mixed(self):
        records = [
            DeployedRuleRecord(
                local_rule_id="rule_001",
                server_rule_id="srv_1",
                source="m365",
                status=DeploymentStatus.DEPLOYED,
            ),
            DeployedRuleRecord(
                local_rule_id="rule_002",
                server_rule_id=None,
                source="m365",
                status=DeploymentStatus.FAILED,
            ),
            DeployedRuleRecord(
                local_rule_id="rule_003",
                server_rule_id=None,
                source="m365",
                status=DeploymentStatus.SKIPPED,
            ),
        ]
        result = DeploymentResult(
            deployed_rules=records,
            failures={"rule_002": "Server error"},
        )
        assert result.total == 3
        assert result.succeeded == 1
        assert result.failed == 1
        assert result.skipped == 1

    def test_dry_run_flag(self):
        result = DeploymentResult(dry_run=True)
        assert result.dry_run is True

    def test_conflicts_list(self):
        conflict = RuleConflict(
            local_rule_id="rule_001",
            server_rule_id="existing_001",
            description="Overlapping sender condition",
        )
        result = DeploymentResult(conflicts=[conflict])
        assert len(result.conflicts) == 1
        assert result.conflicts[0].local_rule_id == "rule_001"


# =============================================================================
# RuleDeployer instantiation
# =============================================================================


class TestRuleDeployerInit:
    """Test RuleDeployer construction."""

    def test_creates_deployer_m365(self):
        deployer = RuleDeployer(source="m365")
        assert deployer.source == "m365"

    def test_creates_deployer_gmail(self):
        deployer = RuleDeployer(source="gmail")
        assert deployer.source == "gmail"

    def test_invalid_source_raises(self):
        with pytest.raises(ValueError, match="source"):
            RuleDeployer(source="yahoo")

    def test_dry_run_default_false(self):
        deployer = RuleDeployer(source="m365")
        assert deployer.dry_run is False

    def test_dry_run_can_be_set(self):
        deployer = RuleDeployer(source="m365", dry_run=True)
        assert deployer.dry_run is True


# =============================================================================
# M365 Graph API rule conversion
# =============================================================================


class TestM365RuleConversion:
    """Test converting CategoryRule to Graph API messageRules payload."""

    def test_basic_sender_domain_rule(self):
        deployer = RuleDeployer(source="m365")
        rule = _make_rule(
            conditions=[
                _make_condition(
                    field=ConditionField.SENDER_DOMAIN,
                    operator=ConditionOperator.EQUALS,
                    value="example.com",
                )
            ],
            name="Example Domain Rule",
        )
        payload = deployer._convert_to_m365_rule(rule)
        assert payload["displayName"] == "Example Domain Rule"
        assert payload["isEnabled"] is True
        assert payload["sequence"] == rule.priority
        assert "conditions" in payload
        assert "actions" in payload

    def test_sender_email_condition(self):
        deployer = RuleDeployer(source="m365")
        rule = _make_rule(
            conditions=[
                _make_condition(
                    field=ConditionField.SENDER_EMAIL,
                    operator=ConditionOperator.EQUALS,
                    value="alice@example.com",
                )
            ]
        )
        payload = deployer._convert_to_m365_rule(rule)
        conditions = payload["conditions"]
        assert "senderContains" in conditions or "fromAddresses" in conditions

    def test_subject_contains_condition(self):
        deployer = RuleDeployer(source="m365")
        rule = _make_rule(
            conditions=[
                _make_condition(
                    field=ConditionField.SUBJECT,
                    operator=ConditionOperator.CONTAINS,
                    value="weekly update",
                )
            ]
        )
        payload = deployer._convert_to_m365_rule(rule)
        conditions = payload["conditions"]
        assert "subjectContains" in conditions

    def test_body_contains_condition(self):
        deployer = RuleDeployer(source="m365")
        rule = _make_rule(
            conditions=[
                _make_condition(
                    field=ConditionField.BODY,
                    operator=ConditionOperator.CONTAINS,
                    value="invoice",
                )
            ]
        )
        payload = deployer._convert_to_m365_rule(rule)
        conditions = payload["conditions"]
        assert "bodyContains" in conditions

    def test_move_to_folder_action(self):
        deployer = RuleDeployer(source="m365")
        rule = _make_rule()
        rule.action = RuleAction(
            action_type=RuleActionType.MOVE_TO_FOLDER,
            target="Newsletters",
        )
        payload = deployer._convert_to_m365_rule(rule)
        actions = payload["actions"]
        assert "moveToFolder" in actions

    def test_disabled_rule_conversion(self):
        deployer = RuleDeployer(source="m365")
        rule = _make_rule(enabled=False)
        payload = deployer._convert_to_m365_rule(rule)
        assert payload["isEnabled"] is False

    def test_multiple_conditions_and_logic(self):
        deployer = RuleDeployer(source="m365")
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
                    value="weekly",
                ),
            ],
            logic=ConditionLogic.AND,
        )
        payload = deployer._convert_to_m365_rule(rule)
        # Both conditions should appear in the payload
        conditions = payload["conditions"]
        assert len(conditions) >= 2

    def test_has_attachment_condition(self):
        deployer = RuleDeployer(source="m365")
        rule = _make_rule(
            conditions=[
                _make_condition(
                    field=ConditionField.HAS_ATTACHMENT,
                    operator=ConditionOperator.EQUALS,
                    value="true",
                )
            ]
        )
        payload = deployer._convert_to_m365_rule(rule)
        conditions = payload["conditions"]
        assert "hasAttachments" in conditions


# =============================================================================
# Gmail filter conversion
# =============================================================================


class TestGmailFilterConversion:
    """Test converting CategoryRule to Gmail filter payload."""

    def test_basic_sender_domain_filter(self):
        deployer = RuleDeployer(source="gmail")
        rule = _make_rule(
            conditions=[
                _make_condition(
                    field=ConditionField.SENDER_DOMAIN,
                    operator=ConditionOperator.EQUALS,
                    value="example.com",
                )
            ]
        )
        payload = deployer._convert_to_gmail_filter(rule)
        assert "criteria" in payload
        assert "action" in payload
        criteria = payload["criteria"]
        assert "from" in criteria

    def test_sender_email_filter(self):
        deployer = RuleDeployer(source="gmail")
        rule = _make_rule(
            conditions=[
                _make_condition(
                    field=ConditionField.SENDER_EMAIL,
                    operator=ConditionOperator.EQUALS,
                    value="alice@example.com",
                )
            ]
        )
        payload = deployer._convert_to_gmail_filter(rule)
        criteria = payload["criteria"]
        assert "from" in criteria
        assert "alice@example.com" in criteria["from"]

    def test_subject_contains_filter(self):
        deployer = RuleDeployer(source="gmail")
        rule = _make_rule(
            conditions=[
                _make_condition(
                    field=ConditionField.SUBJECT,
                    operator=ConditionOperator.CONTAINS,
                    value="newsletter",
                )
            ]
        )
        payload = deployer._convert_to_gmail_filter(rule)
        criteria = payload["criteria"]
        assert "subject" in criteria

    def test_body_contains_filter(self):
        deployer = RuleDeployer(source="gmail")
        rule = _make_rule(
            conditions=[
                _make_condition(
                    field=ConditionField.BODY,
                    operator=ConditionOperator.CONTAINS,
                    value="unsubscribe",
                )
            ]
        )
        payload = deployer._convert_to_gmail_filter(rule)
        criteria = payload["criteria"]
        assert "query" in criteria

    def test_apply_label_action(self):
        deployer = RuleDeployer(source="gmail")
        rule = _make_rule()
        rule.action = RuleAction(
            action_type=RuleActionType.APPLY_LABEL,
            target="Newsletters",
        )
        payload = deployer._convert_to_gmail_filter(rule)
        action = payload["action"]
        assert "addLabelIds" in action

    def test_move_to_folder_uses_label(self):
        deployer = RuleDeployer(source="gmail")
        rule = _make_rule()
        rule.action = RuleAction(
            action_type=RuleActionType.MOVE_TO_FOLDER,
            target="Projects",
        )
        payload = deployer._convert_to_gmail_filter(rule)
        action = payload["action"]
        # Gmail uses labels, so move_to_folder maps to addLabelIds
        assert "addLabelIds" in action

    def test_has_attachment_filter(self):
        deployer = RuleDeployer(source="gmail")
        rule = _make_rule(
            conditions=[
                _make_condition(
                    field=ConditionField.HAS_ATTACHMENT,
                    operator=ConditionOperator.EQUALS,
                    value="true",
                )
            ]
        )
        payload = deployer._convert_to_gmail_filter(rule)
        criteria = payload["criteria"]
        assert criteria.get("hasAttachment") is True

    def test_multiple_conditions_combined_in_query(self):
        deployer = RuleDeployer(source="gmail")
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
                    value="weekly",
                ),
            ],
            logic=ConditionLogic.AND,
        )
        payload = deployer._convert_to_gmail_filter(rule)
        criteria = payload["criteria"]
        # Should have both from and subject criteria
        assert "from" in criteria
        assert "subject" in criteria


# =============================================================================
# Deploy rules — M365
# =============================================================================


class TestDeployM365Rules:
    """Test deploying rules to M365 via Graph API (mocked)."""

    @patch("src.actions.rule_deployer.requests")
    def test_deploy_single_rule_success(self, mock_requests):
        """Deploying a single rule creates a messageRule via POST."""
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "id": "srv_rule_001",
            "displayName": "Test Rule",
        }
        mock_response.raise_for_status = MagicMock()
        mock_requests.post.return_value = mock_response

        deployer = RuleDeployer(source="m365")
        rule_set = _make_rule_set()

        result = deployer.deploy_rules(rule_set, access_token="fake-token")

        assert result.succeeded == 1
        assert result.failed == 0
        assert result.deployed_rules[0].server_rule_id == "srv_rule_001"
        assert result.deployed_rules[0].status == DeploymentStatus.DEPLOYED

    @patch("src.actions.rule_deployer.requests")
    def test_deploy_rule_api_failure(self, mock_requests):
        """API failure records the rule as failed with error message."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"
        mock_response.raise_for_status.side_effect = Exception("400 Bad Request")
        mock_requests.post.return_value = mock_response

        deployer = RuleDeployer(source="m365")
        rule_set = _make_rule_set()

        result = deployer.deploy_rules(rule_set, access_token="fake-token")

        assert result.succeeded == 0
        assert result.failed == 1
        assert "rule_001" in result.failures

    @patch("src.actions.rule_deployer.requests")
    def test_deploy_multiple_rules(self, mock_requests):
        """Deploying multiple rules returns individual results."""
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"id": "srv_rule_x", "displayName": "Rule"}
        mock_response.raise_for_status = MagicMock()
        mock_requests.post.return_value = mock_response

        deployer = RuleDeployer(source="m365")
        rules = [
            _make_rule(rule_id="rule_001", name="Rule 1"),
            _make_rule(rule_id="rule_002", name="Rule 2"),
            _make_rule(rule_id="rule_003", name="Rule 3"),
        ]
        rule_set = _make_rule_set(rules)

        result = deployer.deploy_rules(rule_set, access_token="fake-token")

        assert result.total == 3
        assert result.succeeded == 3

    @patch("src.actions.rule_deployer.requests")
    def test_deploy_skips_disabled_rules(self, mock_requests):
        """Disabled rules are skipped, not deployed."""
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"id": "srv_rule_x"}
        mock_response.raise_for_status = MagicMock()
        mock_requests.post.return_value = mock_response

        deployer = RuleDeployer(source="m365")
        rules = [
            _make_rule(rule_id="rule_001", enabled=True),
            _make_rule(rule_id="rule_002", enabled=False),
        ]
        rule_set = _make_rule_set(rules)

        result = deployer.deploy_rules(rule_set, access_token="fake-token")

        assert result.total == 2
        assert result.succeeded == 1
        assert result.skipped == 1

    @patch("src.actions.rule_deployer.requests")
    def test_deploy_continues_on_individual_failure(self, mock_requests):
        """One rule failing doesn't stop deployment of subsequent rules."""
        responses = []
        # First call fails
        fail_resp = MagicMock()
        fail_resp.status_code = 400
        fail_resp.text = "Bad Request"
        fail_resp.raise_for_status.side_effect = Exception("400")
        responses.append(fail_resp)
        # Second call succeeds
        ok_resp = MagicMock()
        ok_resp.status_code = 201
        ok_resp.json.return_value = {"id": "srv_rule_002"}
        ok_resp.raise_for_status = MagicMock()
        responses.append(ok_resp)

        mock_requests.post.side_effect = responses

        deployer = RuleDeployer(source="m365")
        rules = [
            _make_rule(rule_id="rule_001"),
            _make_rule(rule_id="rule_002"),
        ]
        rule_set = _make_rule_set(rules)

        result = deployer.deploy_rules(rule_set, access_token="fake-token")

        assert result.succeeded == 1
        assert result.failed == 1


# =============================================================================
# Deploy rules — Gmail
# =============================================================================


class TestDeployGmailRules:
    """Test deploying rules to Gmail via Filters API (mocked)."""

    @patch("src.actions.rule_deployer.RuleDeployer._get_gmail_service")
    def test_deploy_single_filter_success(self, mock_get_service):
        """Deploying a single filter creates a Gmail filter."""
        mock_service = MagicMock()
        mock_create = mock_service.users().settings().filters().create
        mock_create.return_value.execute.return_value = {
            "id": "gmail_filter_001",
        }
        mock_get_service.return_value = mock_service

        deployer = RuleDeployer(source="gmail")
        rule_set = _make_rule_set()

        result = deployer.deploy_rules(rule_set)

        assert result.succeeded == 1
        assert result.deployed_rules[0].server_rule_id == "gmail_filter_001"
        assert result.deployed_rules[0].status == DeploymentStatus.DEPLOYED

    @patch("src.actions.rule_deployer.RuleDeployer._get_gmail_service")
    def test_deploy_filter_api_failure(self, mock_get_service):
        """Gmail API failure records the filter as failed."""
        mock_service = MagicMock()
        mock_create = mock_service.users().settings().filters().create
        mock_create.return_value.execute.side_effect = Exception("API Error")
        mock_get_service.return_value = mock_service

        deployer = RuleDeployer(source="gmail")
        rule_set = _make_rule_set()

        result = deployer.deploy_rules(rule_set)

        assert result.succeeded == 0
        assert result.failed == 1

    @patch("src.actions.rule_deployer.RuleDeployer._get_gmail_service")
    def test_deploy_multiple_gmail_filters(self, mock_get_service):
        """Deploying multiple Gmail filters returns individual results."""
        mock_service = MagicMock()
        counter = {"n": 0}

        def make_filter(*args, **kwargs):
            counter["n"] += 1
            result_mock = MagicMock()
            result_mock.execute.return_value = {"id": f"gmail_filter_{counter['n']:03d}"}
            return result_mock

        mock_service.users().settings().filters().create.side_effect = make_filter
        mock_get_service.return_value = mock_service

        deployer = RuleDeployer(source="gmail")
        rules = [
            _make_rule(rule_id="rule_001"),
            _make_rule(rule_id="rule_002"),
        ]
        rule_set = _make_rule_set(rules)

        result = deployer.deploy_rules(rule_set)

        assert result.total == 2
        assert result.succeeded == 2

    @patch("src.actions.rule_deployer.RuleDeployer._get_gmail_service")
    def test_deploy_gmail_skips_disabled(self, mock_get_service):
        """Disabled rules are skipped in Gmail deployment."""
        mock_service = MagicMock()
        mock_create = mock_service.users().settings().filters().create
        mock_create.return_value.execute.return_value = {"id": "gmail_filter_001"}
        mock_get_service.return_value = mock_service

        deployer = RuleDeployer(source="gmail")
        rules = [
            _make_rule(rule_id="rule_001", enabled=True),
            _make_rule(rule_id="rule_002", enabled=False),
        ]
        rule_set = _make_rule_set(rules)

        result = deployer.deploy_rules(rule_set)

        assert result.succeeded == 1
        assert result.skipped == 1


# =============================================================================
# Dry-run mode
# =============================================================================


class TestDryRunMode:
    """Test dry-run mode — no API calls made."""

    @patch("src.actions.rule_deployer.requests")
    def test_dry_run_m365_no_api_calls(self, mock_requests):
        """Dry-run should not make any POST requests."""
        deployer = RuleDeployer(source="m365", dry_run=True)
        rule_set = _make_rule_set()

        result = deployer.deploy_rules(rule_set, access_token="fake-token")

        mock_requests.post.assert_not_called()
        assert result.dry_run is True
        assert result.total == 1
        # Dry-run records should show what would be deployed
        assert len(result.deployed_rules) == 1
        assert result.deployed_rules[0].status == DeploymentStatus.DRY_RUN

    @patch("src.actions.rule_deployer.RuleDeployer._get_gmail_service")
    def test_dry_run_gmail_no_api_calls(self, mock_get_service):
        """Dry-run should not call Gmail API."""
        deployer = RuleDeployer(source="gmail", dry_run=True)
        rule_set = _make_rule_set()

        result = deployer.deploy_rules(rule_set)

        mock_get_service.assert_not_called()
        assert result.dry_run is True
        assert result.total == 1
        assert result.deployed_rules[0].status == DeploymentStatus.DRY_RUN

    @patch("src.actions.rule_deployer.requests")
    def test_dry_run_shows_converted_payloads(self, mock_requests):
        """Dry-run should populate the payloads for inspection."""
        deployer = RuleDeployer(source="m365", dry_run=True)
        rule_set = _make_rule_set()

        result = deployer.deploy_rules(rule_set, access_token="fake-token")

        # Each dry-run record should have the converted payload
        record = result.deployed_rules[0]
        assert record.payload is not None
        assert "displayName" in record.payload

    @patch("src.actions.rule_deployer.RuleDeployer._get_gmail_service")
    def test_dry_run_gmail_shows_payloads(self, mock_get_service):
        """Gmail dry-run should populate the filter payload."""
        deployer = RuleDeployer(source="gmail", dry_run=True)
        rule_set = _make_rule_set()

        result = deployer.deploy_rules(rule_set)

        record = result.deployed_rules[0]
        assert record.payload is not None
        assert "criteria" in record.payload

    @patch("src.actions.rule_deployer.requests")
    def test_dry_run_skips_disabled(self, mock_requests):
        """Disabled rules are still skipped in dry-run."""
        deployer = RuleDeployer(source="m365", dry_run=True)
        rules = [
            _make_rule(rule_id="rule_001", enabled=True),
            _make_rule(rule_id="rule_002", enabled=False),
        ]
        rule_set = _make_rule_set(rules)

        result = deployer.deploy_rules(rule_set, access_token="fake-token")

        assert result.total == 2
        assert result.skipped == 1
        dry_run_records = [r for r in result.deployed_rules if r.status == DeploymentStatus.DRY_RUN]
        assert len(dry_run_records) == 1


# =============================================================================
# Conflict detection — M365
# =============================================================================


class TestM365ConflictDetection:
    """Test detecting conflicts with existing M365 server-side rules."""

    @patch("src.actions.rule_deployer.requests")
    def test_no_existing_rules_no_conflicts(self, mock_requests):
        """No existing server rules means no conflicts."""
        # GET returns empty list
        mock_get_resp = MagicMock()
        mock_get_resp.status_code = 200
        mock_get_resp.json.return_value = {"value": []}
        mock_get_resp.raise_for_status = MagicMock()
        mock_requests.get.return_value = mock_get_resp

        deployer = RuleDeployer(source="m365")
        rule_set = _make_rule_set()

        conflicts = deployer.check_conflicts(rule_set, access_token="fake-token")

        assert conflicts == []

    @patch("src.actions.rule_deployer.requests")
    def test_detects_sender_domain_overlap(self, mock_requests):
        """Detect conflict when an existing rule matches the same sender domain."""
        mock_get_resp = MagicMock()
        mock_get_resp.status_code = 200
        mock_get_resp.json.return_value = {
            "value": [
                {
                    "id": "existing_001",
                    "displayName": "Existing Example Rule",
                    "isEnabled": True,
                    "conditions": {
                        "senderContains": ["example.com"],
                    },
                    "actions": {
                        "moveToFolder": "OtherFolder",
                    },
                }
            ]
        }
        mock_get_resp.raise_for_status = MagicMock()
        mock_requests.get.return_value = mock_get_resp

        deployer = RuleDeployer(source="m365")
        rule = _make_rule(
            conditions=[
                _make_condition(
                    field=ConditionField.SENDER_DOMAIN,
                    operator=ConditionOperator.EQUALS,
                    value="example.com",
                )
            ]
        )
        rule_set = _make_rule_set([rule])

        conflicts = deployer.check_conflicts(rule_set, access_token="fake-token")

        assert len(conflicts) >= 1
        assert conflicts[0].local_rule_id == "rule_001"
        assert conflicts[0].server_rule_id == "existing_001"

    @patch("src.actions.rule_deployer.requests")
    def test_detects_subject_overlap(self, mock_requests):
        """Detect conflict when an existing rule matches the same subject keyword."""
        mock_get_resp = MagicMock()
        mock_get_resp.status_code = 200
        mock_get_resp.json.return_value = {
            "value": [
                {
                    "id": "existing_002",
                    "displayName": "Existing Subject Rule",
                    "isEnabled": True,
                    "conditions": {
                        "subjectContains": ["weekly"],
                    },
                    "actions": {},
                }
            ]
        }
        mock_get_resp.raise_for_status = MagicMock()
        mock_requests.get.return_value = mock_get_resp

        deployer = RuleDeployer(source="m365")
        rule = _make_rule(
            conditions=[
                _make_condition(
                    field=ConditionField.SUBJECT,
                    operator=ConditionOperator.CONTAINS,
                    value="weekly",
                )
            ]
        )
        rule_set = _make_rule_set([rule])

        conflicts = deployer.check_conflicts(rule_set, access_token="fake-token")

        assert len(conflicts) >= 1

    @patch("src.actions.rule_deployer.requests")
    def test_no_conflict_when_different_conditions(self, mock_requests):
        """No conflict when existing and new rules have different conditions."""
        mock_get_resp = MagicMock()
        mock_get_resp.status_code = 200
        mock_get_resp.json.return_value = {
            "value": [
                {
                    "id": "existing_003",
                    "displayName": "Other Rule",
                    "isEnabled": True,
                    "conditions": {
                        "senderContains": ["other-domain.com"],
                    },
                    "actions": {},
                }
            ]
        }
        mock_get_resp.raise_for_status = MagicMock()
        mock_requests.get.return_value = mock_get_resp

        deployer = RuleDeployer(source="m365")
        rule = _make_rule(
            conditions=[
                _make_condition(
                    field=ConditionField.SENDER_DOMAIN,
                    operator=ConditionOperator.EQUALS,
                    value="example.com",
                )
            ]
        )
        rule_set = _make_rule_set([rule])

        conflicts = deployer.check_conflicts(rule_set, access_token="fake-token")

        assert len(conflicts) == 0


# =============================================================================
# Conflict detection — Gmail
# =============================================================================


class TestGmailConflictDetection:
    """Test detecting conflicts with existing Gmail filters."""

    @patch("src.actions.rule_deployer.RuleDeployer._get_gmail_service")
    def test_no_existing_filters_no_conflicts(self, mock_get_service):
        """No existing Gmail filters means no conflicts."""
        mock_service = MagicMock()
        mock_list = mock_service.users().settings().filters().list
        mock_list.return_value.execute.return_value = {"filter": []}
        mock_get_service.return_value = mock_service

        deployer = RuleDeployer(source="gmail")
        rule_set = _make_rule_set()

        conflicts = deployer.check_conflicts(rule_set)

        assert conflicts == []

    @patch("src.actions.rule_deployer.RuleDeployer._get_gmail_service")
    def test_detects_from_address_overlap(self, mock_get_service):
        """Detect conflict when existing filter matches the same sender."""
        mock_service = MagicMock()
        mock_list = mock_service.users().settings().filters().list
        mock_list.return_value.execute.return_value = {
            "filter": [
                {
                    "id": "existing_gmail_001",
                    "criteria": {
                        "from": "example.com",
                    },
                    "action": {
                        "addLabelIds": ["Label_1"],
                    },
                }
            ]
        }
        mock_get_service.return_value = mock_service

        deployer = RuleDeployer(source="gmail")
        rule = _make_rule(
            conditions=[
                _make_condition(
                    field=ConditionField.SENDER_DOMAIN,
                    operator=ConditionOperator.EQUALS,
                    value="example.com",
                )
            ]
        )
        rule_set = _make_rule_set([rule])

        conflicts = deployer.check_conflicts(rule_set)

        assert len(conflicts) >= 1
        assert conflicts[0].server_rule_id == "existing_gmail_001"


# =============================================================================
# Rollback — M365
# =============================================================================


class TestM365Rollback:
    """Test rolling back (deleting) deployed M365 rules."""

    @patch("src.actions.rule_deployer.requests")
    def test_rollback_deletes_deployed_rules(self, mock_requests):
        """Rollback sends DELETE for each deployed server rule."""
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_response.raise_for_status = MagicMock()
        mock_requests.delete.return_value = mock_response

        deployer = RuleDeployer(source="m365")
        deployment_result = DeploymentResult(
            deployed_rules=[
                DeployedRuleRecord(
                    local_rule_id="rule_001",
                    server_rule_id="srv_001",
                    source="m365",
                    status=DeploymentStatus.DEPLOYED,
                ),
                DeployedRuleRecord(
                    local_rule_id="rule_002",
                    server_rule_id="srv_002",
                    source="m365",
                    status=DeploymentStatus.DEPLOYED,
                ),
            ]
        )

        rollback_result = deployer.rollback(deployment_result, access_token="fake-token")

        assert mock_requests.delete.call_count == 2
        assert rollback_result.succeeded == 2

    @patch("src.actions.rule_deployer.requests")
    def test_rollback_skips_failed_rules(self, mock_requests):
        """Rules that were never deployed (failed) are skipped in rollback."""
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_response.raise_for_status = MagicMock()
        mock_requests.delete.return_value = mock_response

        deployer = RuleDeployer(source="m365")
        deployment_result = DeploymentResult(
            deployed_rules=[
                DeployedRuleRecord(
                    local_rule_id="rule_001",
                    server_rule_id="srv_001",
                    source="m365",
                    status=DeploymentStatus.DEPLOYED,
                ),
                DeployedRuleRecord(
                    local_rule_id="rule_002",
                    server_rule_id=None,
                    source="m365",
                    status=DeploymentStatus.FAILED,
                ),
            ]
        )

        rollback_result = deployer.rollback(deployment_result, access_token="fake-token")

        assert mock_requests.delete.call_count == 1
        assert rollback_result.succeeded == 1
        assert rollback_result.skipped == 1

    @patch("src.actions.rule_deployer.requests")
    def test_rollback_handles_delete_failure(self, mock_requests):
        """Rollback continues if individual delete calls fail."""
        responses = []
        # First delete succeeds
        ok_resp = MagicMock()
        ok_resp.status_code = 204
        ok_resp.raise_for_status = MagicMock()
        responses.append(ok_resp)
        # Second delete fails
        fail_resp = MagicMock()
        fail_resp.status_code = 404
        fail_resp.text = "Not Found"
        fail_resp.raise_for_status.side_effect = Exception("404")
        responses.append(fail_resp)

        mock_requests.delete.side_effect = responses

        deployer = RuleDeployer(source="m365")
        deployment_result = DeploymentResult(
            deployed_rules=[
                DeployedRuleRecord(
                    local_rule_id="rule_001",
                    server_rule_id="srv_001",
                    source="m365",
                    status=DeploymentStatus.DEPLOYED,
                ),
                DeployedRuleRecord(
                    local_rule_id="rule_002",
                    server_rule_id="srv_002",
                    source="m365",
                    status=DeploymentStatus.DEPLOYED,
                ),
            ]
        )

        rollback_result = deployer.rollback(deployment_result, access_token="fake-token")

        assert rollback_result.succeeded == 1
        assert rollback_result.failed == 1

    @patch("src.actions.rule_deployer.requests")
    def test_rollback_skips_dry_run_records(self, mock_requests):
        """Dry-run records should not be rolled back."""
        deployer = RuleDeployer(source="m365")
        deployment_result = DeploymentResult(
            dry_run=True,
            deployed_rules=[
                DeployedRuleRecord(
                    local_rule_id="rule_001",
                    server_rule_id=None,
                    source="m365",
                    status=DeploymentStatus.DRY_RUN,
                ),
            ],
        )

        rollback_result = deployer.rollback(deployment_result, access_token="fake-token")

        mock_requests.delete.assert_not_called()
        assert rollback_result.skipped == 1


# =============================================================================
# Rollback — Gmail
# =============================================================================


class TestGmailRollback:
    """Test rolling back (deleting) deployed Gmail filters."""

    @patch("src.actions.rule_deployer.RuleDeployer._get_gmail_service")
    def test_rollback_deletes_gmail_filters(self, mock_get_service):
        """Rollback calls filters().delete() for each deployed filter."""
        mock_service = MagicMock()
        mock_delete = mock_service.users().settings().filters().delete
        mock_delete.return_value.execute.return_value = {}
        mock_get_service.return_value = mock_service

        deployer = RuleDeployer(source="gmail")
        deployment_result = DeploymentResult(
            deployed_rules=[
                DeployedRuleRecord(
                    local_rule_id="rule_001",
                    server_rule_id="gmail_filter_001",
                    source="gmail",
                    status=DeploymentStatus.DEPLOYED,
                ),
            ]
        )

        rollback_result = deployer.rollback(deployment_result)

        assert rollback_result.succeeded == 1

    @patch("src.actions.rule_deployer.RuleDeployer._get_gmail_service")
    def test_rollback_gmail_handles_failure(self, mock_get_service):
        """Gmail rollback continues on individual delete failure."""
        mock_service = MagicMock()
        mock_delete = mock_service.users().settings().filters().delete
        mock_delete.return_value.execute.side_effect = Exception("Delete failed")
        mock_get_service.return_value = mock_service

        deployer = RuleDeployer(source="gmail")
        deployment_result = DeploymentResult(
            deployed_rules=[
                DeployedRuleRecord(
                    local_rule_id="rule_001",
                    server_rule_id="gmail_filter_001",
                    source="gmail",
                    status=DeploymentStatus.DEPLOYED,
                ),
            ]
        )

        rollback_result = deployer.rollback(deployment_result)

        assert rollback_result.failed == 1


# =============================================================================
# Validation
# =============================================================================


class TestRuleValidation:
    """Test pre-deployment rule validation."""

    def test_validate_empty_rule_set(self):
        deployer = RuleDeployer(source="m365")
        rule_set = RuleSet(rules=[])
        errors = deployer.validate_rules(rule_set)
        assert len(errors) == 0  # Empty is valid, just nothing to deploy

    def test_validate_unsupported_operator_for_m365(self):
        """M365 doesn't support regex in messageRules; should warn."""
        deployer = RuleDeployer(source="m365")
        rule = _make_rule(
            conditions=[
                _make_condition(
                    field=ConditionField.SUBJECT,
                    operator=ConditionOperator.MATCHES_REGEX,
                    value="^weekly.*report$",
                )
            ]
        )
        rule_set = _make_rule_set([rule])
        errors = deployer.validate_rules(rule_set)
        assert len(errors) > 0
        assert any("regex" in e.lower() or "unsupported" in e.lower() for e in errors)

    def test_validate_valid_rules_pass(self):
        deployer = RuleDeployer(source="m365")
        rule = _make_rule(
            conditions=[
                _make_condition(
                    field=ConditionField.SENDER_DOMAIN,
                    operator=ConditionOperator.EQUALS,
                    value="example.com",
                )
            ]
        )
        rule_set = _make_rule_set([rule])
        errors = deployer.validate_rules(rule_set)
        assert len(errors) == 0

    def test_validate_gmail_unsupported_operator(self):
        """Gmail filters don't support NOT operators natively."""
        deployer = RuleDeployer(source="gmail")
        rule = _make_rule(
            conditions=[
                _make_condition(
                    field=ConditionField.SUBJECT,
                    operator=ConditionOperator.NOT_CONTAINS,
                    value="spam",
                )
            ]
        )
        rule_set = _make_rule_set([rule])
        errors = deployer.validate_rules(rule_set)
        # Gmail can handle negation via "-" prefix, so this may or may not error
        # At minimum, it should not crash
        assert isinstance(errors, list)


# =============================================================================
# Edge cases
# =============================================================================


class TestEdgeCases:
    """Edge case handling."""

    @patch("src.actions.rule_deployer.requests")
    def test_deploy_with_no_access_token_m365_raises(self, mock_requests):
        """M365 deployment without access token raises ValueError."""
        deployer = RuleDeployer(source="m365")
        rule_set = _make_rule_set()

        with pytest.raises(ValueError, match="access_token"):
            deployer.deploy_rules(rule_set)

    def test_deploy_empty_rule_set(self):
        """Deploying an empty rule set returns empty result."""
        deployer = RuleDeployer(source="m365", dry_run=True)
        rule_set = RuleSet(rules=[])

        result = deployer.deploy_rules(rule_set, access_token="fake-token")

        assert result.total == 0
        assert result.succeeded == 0

    @patch("src.actions.rule_deployer.requests")
    def test_check_conflicts_with_api_failure(self, mock_requests):
        """API failure during conflict check returns empty list (graceful)."""
        mock_requests.get.side_effect = Exception("Network error")

        deployer = RuleDeployer(source="m365")
        rule_set = _make_rule_set()

        conflicts = deployer.check_conflicts(rule_set, access_token="fake-token")

        assert conflicts == []

    def test_rollback_empty_deployment(self):
        """Rollback on empty deployment result is a no-op."""
        deployer = RuleDeployer(source="m365")
        deployment_result = DeploymentResult()

        rollback_result = deployer.rollback(deployment_result, access_token="fake-token")

        assert rollback_result.total == 0
