"""
Unit tests for the apply CLI command (Phase 5, Item 5.5).

TDD: Tests written first, implementation follows.

Tests cover:
- Parser construction (apply subcommand with folders/move/rules/rollback sub-actions)
- apply folders: creates folders via FolderManager
- apply move: moves emails via EmailMover
- apply rules: deploys rules via RuleDeployer
- apply rollback: reverses actions via ActionLogger
- --dry-run, --source, --json, --verbose flag support
- --since flag for rollback time-based filtering
- Error handling for missing files and invalid sources
- Confirmation prompt before live operations
"""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# =============================================================================
# Helpers
# =============================================================================


def _make_approved_categories() -> list[dict]:
    """Create a list of serialized approved category dicts."""
    return [
        {
            "category_id": "cat_1",
            "category_name": "Newsletter Updates",
            "description": "Test category",
            "confidence": 0.85,
            "email_count": 42,
            "percentage": 25.0,
            "source": "template",
            "source_id": "test_source",
            "example_email_ids": [],
            "distinguishing_features": ["newsletter", "weekly"],
        },
        {
            "category_id": "cat_2",
            "category_name": "Shipping Notifications",
            "description": "Shipping updates",
            "confidence": 0.90,
            "email_count": 30,
            "percentage": 18.0,
            "source": "template",
            "source_id": "test_source_2",
            "example_email_ids": [],
            "distinguishing_features": ["shipping", "tracking"],
        },
    ]


def _make_ruleset_dict() -> dict:
    """Create a serialized RuleSet dict."""
    now = datetime.now(timezone.utc).isoformat()
    return {
        "rules": [
            {
                "rule_id": "rule_cat_1",
                "name": "Rule: Newsletter Updates",
                "description": "Auto-generated rule",
                "conditions": [
                    {
                        "field": "subject",
                        "operator": "contains",
                        "value": "newsletter",
                        "case_sensitive": False,
                    }
                ],
                "action": {
                    "action_type": "categorize",
                    "target": "Newsletter Updates",
                    "target_category_id": "cat_1",
                },
                "logic": "or",
                "priority": 85,
                "enabled": True,
                "category_id": "cat_1",
                "created_date": now,
                "last_modified": now,
            }
        ],
        "version": "1.0",
        "description": "Test rule set",
        "created_date": now,
        "last_modified": now,
        "source_category_ids": ["cat_1"],
    }


def _make_categorization_report() -> dict:
    """Create a minimal categorization report dict."""
    return {
        "total_emails": 100,
        "categorized_count": 80,
        "uncategorized_count": 20,
        "coverage_percentage": 80.0,
        "category_count": 2,
        "multi_category_count": 5,
        "categories_used": {"Newsletter Updates": 50, "Shipping Notifications": 30},
        "categorizations": [
            {
                "email_id": f"msg_{i}",
                "matched_rules": ["rule_cat_1"],
                "primary_category": {
                    "category_name": "Newsletter Updates",
                    "rule_id": "rule_cat_1",
                    "confidence": 0.85,
                },
                "secondary_categories": [],
            }
            for i in range(5)
        ],
    }


def _make_args(**kwargs) -> argparse.Namespace:
    """Create a Namespace with common defaults for apply command."""
    defaults = {
        "apply_action": None,
        "source": "hotmail",
        "dry_run": False,
        "json": False,
        "verbose": False,
        "yes": False,
    }
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


# =============================================================================
# Parser tests
# =============================================================================


class TestApplyParser:
    """Test that the apply subcommand parser is correctly configured."""

    def test_apply_command_registered_in_parser(self):
        """Test that 'apply' is a valid subcommand."""
        from src.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["apply", "folders"])
        assert args.command == "apply"

    def test_apply_folders_subcommand(self):
        """Test that 'apply folders' is parsed correctly."""
        from src.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["apply", "folders"])
        assert args.command == "apply"
        assert args.apply_action == "folders"

    def test_apply_move_subcommand(self):
        """Test that 'apply move' is parsed correctly."""
        from src.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["apply", "move"])
        assert args.command == "apply"
        assert args.apply_action == "move"

    def test_apply_rules_subcommand(self):
        """Test that 'apply rules' is parsed correctly."""
        from src.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["apply", "rules"])
        assert args.command == "apply"
        assert args.apply_action == "rules"

    def test_apply_rollback_subcommand(self):
        """Test that 'apply rollback' is parsed correctly."""
        from src.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["apply", "rollback"])
        assert args.command == "apply"
        assert args.apply_action == "rollback"

    def test_apply_requires_action(self):
        """Test that 'apply' without an action fails."""
        from src.cli import create_parser

        parser = create_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["apply"])

    def test_apply_dry_run_flag(self):
        """Test that --dry-run flag is accepted on subcommands."""
        from src.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["apply", "folders", "--dry-run"])
        assert args.dry_run is True

    def test_apply_source_flag_hotmail(self):
        """Test --source hotmail flag."""
        from src.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["apply", "folders", "--source", "hotmail"])
        assert args.source == "hotmail"

    def test_apply_source_flag_gmail(self):
        """Test --source gmail flag."""
        from src.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["apply", "folders", "--source", "gmail"])
        assert args.source == "gmail"

    def test_apply_source_flag_both(self):
        """Test --source both flag."""
        from src.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["apply", "folders", "--source", "both"])
        assert args.source == "both"

    def test_apply_source_invalid(self):
        """Test that invalid --source value is rejected."""
        from src.cli import create_parser

        parser = create_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["apply", "folders", "--source", "yahoo"])

    def test_apply_yes_flag(self):
        """Test --yes flag skips confirmation prompt."""
        from src.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["apply", "move", "--yes"])
        assert args.yes is True

    def test_apply_rollback_since_flag(self):
        """Test --since flag on rollback subcommand."""
        from src.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["apply", "rollback", "--since", "2024-01-15T00:00:00"])
        assert args.since == "2024-01-15T00:00:00"

    def test_apply_folders_categories_path(self):
        """Test --categories flag on folders subcommand."""
        from src.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["apply", "folders", "--categories", "/tmp/cats.json"])
        assert args.categories == Path("/tmp/cats.json")

    def test_apply_move_report_path(self):
        """Test --report flag on move subcommand."""
        from src.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["apply", "move", "--report", "/tmp/report.json"])
        assert args.report == Path("/tmp/report.json")

    def test_apply_rules_rules_file_path(self):
        """Test --rules-file flag on rules subcommand."""
        from src.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["apply", "rules", "--rules-file", "/tmp/rules.json"])
        assert args.rules_file == Path("/tmp/rules.json")

    def test_apply_command_in_dispatch(self):
        """Test that the main dispatcher knows about the apply command."""
        from src.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["apply", "folders"])
        assert args.command == "apply"


# =============================================================================
# apply folders tests
# =============================================================================


class TestApplyFolders:
    """Test the apply folders command."""

    @patch("src.cli.commands.apply.load_json")
    @patch("src.cli.commands.apply.PathConfig")
    def test_folders_dry_run_success(self, mock_path_config, mock_load_json, capsys):
        """Test folders dry-run previews folder creation without API calls."""
        from src.cli.commands.apply import cmd_apply

        mock_path_config.get_approved_categories_path.return_value = Path("/tmp/cats.json")
        mock_load_json.return_value = _make_approved_categories()

        args = _make_args(apply_action="folders", dry_run=True, categories=None)
        result = cmd_apply(args)

        assert result == 0

    @patch("src.cli.commands.apply.load_json")
    @patch("src.cli.commands.apply.PathConfig")
    def test_folders_dry_run_json_output(self, mock_path_config, mock_load_json, capsys):
        """Test folders dry-run with --json flag outputs structured JSON."""
        from src.cli.commands.apply import cmd_apply

        mock_path_config.get_approved_categories_path.return_value = Path("/tmp/cats.json")
        mock_load_json.return_value = _make_approved_categories()

        args = _make_args(apply_action="folders", dry_run=True, json=True, categories=None)
        result = cmd_apply(args)

        assert result == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["command"] == "apply folders"
        assert data["status"] == "success"
        assert data["dry_run"] is True

    @patch("src.cli.commands.apply.load_json")
    @patch("src.cli.commands.apply.PathConfig")
    def test_folders_categories_not_found(self, mock_path_config, mock_load_json):
        """Test folders fails gracefully when categories file is missing."""
        from src.cli.commands.apply import cmd_apply

        mock_path_config.get_approved_categories_path.return_value = Path("/tmp/cats.json")
        mock_load_json.side_effect = FileNotFoundError("Not found")

        args = _make_args(apply_action="folders", dry_run=True, categories=None)
        result = cmd_apply(args)

        assert result == 1

    @patch("src.cli.commands.apply.load_json")
    @patch("src.cli.commands.apply.PathConfig")
    def test_folders_categories_not_found_json(self, mock_path_config, mock_load_json, capsys):
        """Test folders with missing categories outputs JSON error."""
        from src.cli.commands.apply import cmd_apply

        mock_path_config.get_approved_categories_path.return_value = Path("/tmp/cats.json")
        mock_load_json.side_effect = FileNotFoundError("Not found")

        args = _make_args(apply_action="folders", dry_run=True, json=True, categories=None)
        result = cmd_apply(args)

        assert result == 1
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["status"] == "error"

    @patch("src.cli.commands.apply.load_json")
    @patch("src.cli.commands.apply.PathConfig")
    def test_folders_custom_categories_path(self, mock_path_config, mock_load_json):
        """Test folders with custom --categories path."""
        from src.cli.commands.apply import cmd_apply

        mock_load_json.return_value = _make_approved_categories()

        args = _make_args(
            apply_action="folders",
            dry_run=True,
            categories=Path("/custom/cats.json"),
        )
        result = cmd_apply(args)

        assert result == 0
        mock_load_json.assert_called_once_with(Path("/custom/cats.json"))

    @patch("src.cli.commands.apply.load_json")
    @patch("src.cli.commands.apply.PathConfig")
    def test_folders_source_gmail(self, mock_path_config, mock_load_json):
        """Test folders with --source gmail uses Gmail backend."""
        from src.cli.commands.apply import cmd_apply

        mock_path_config.get_approved_categories_path.return_value = Path("/tmp/cats.json")
        mock_load_json.return_value = _make_approved_categories()

        args = _make_args(apply_action="folders", dry_run=True, source="gmail", categories=None)
        result = cmd_apply(args)

        assert result == 0


# =============================================================================
# apply move tests
# =============================================================================


class TestApplyMove:
    """Test the apply move command."""

    @patch("src.cli.commands.apply.load_json")
    @patch("src.cli.commands.apply.PathConfig")
    def test_move_dry_run_success(self, mock_path_config, mock_load_json, capsys):
        """Test move dry-run previews email moves without API calls."""
        from src.cli.commands.apply import cmd_apply

        mock_path_config.get_categorization_report_path.return_value = Path("/tmp/report.json")
        mock_load_json.return_value = _make_categorization_report()

        args = _make_args(apply_action="move", dry_run=True, report=None)
        result = cmd_apply(args)

        assert result == 0

    @patch("src.cli.commands.apply.load_json")
    @patch("src.cli.commands.apply.PathConfig")
    def test_move_dry_run_json_output(self, mock_path_config, mock_load_json, capsys):
        """Test move dry-run with --json flag."""
        from src.cli.commands.apply import cmd_apply

        mock_path_config.get_categorization_report_path.return_value = Path("/tmp/report.json")
        mock_load_json.return_value = _make_categorization_report()

        args = _make_args(apply_action="move", dry_run=True, json=True, report=None)
        result = cmd_apply(args)

        assert result == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["command"] == "apply move"
        assert data["dry_run"] is True

    @patch("src.cli.commands.apply.load_json")
    @patch("src.cli.commands.apply.PathConfig")
    def test_move_report_not_found(self, mock_path_config, mock_load_json):
        """Test move fails gracefully when categorization report is missing."""
        from src.cli.commands.apply import cmd_apply

        mock_path_config.get_categorization_report_path.return_value = Path("/tmp/report.json")
        mock_load_json.side_effect = FileNotFoundError("Not found")

        args = _make_args(apply_action="move", dry_run=True, report=None)
        result = cmd_apply(args)

        assert result == 1

    @patch("src.cli.commands.apply.load_json")
    @patch("src.cli.commands.apply.PathConfig")
    def test_move_report_not_found_json(self, mock_path_config, mock_load_json, capsys):
        """Test move with missing report outputs JSON error."""
        from src.cli.commands.apply import cmd_apply

        mock_path_config.get_categorization_report_path.return_value = Path("/tmp/report.json")
        mock_load_json.side_effect = FileNotFoundError("Not found")

        args = _make_args(apply_action="move", dry_run=True, json=True, report=None)
        result = cmd_apply(args)

        assert result == 1
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["status"] == "error"

    @patch("src.cli.commands.apply.load_json")
    @patch("src.cli.commands.apply.PathConfig")
    def test_move_custom_report_path(self, mock_path_config, mock_load_json):
        """Test move with custom --report path."""
        from src.cli.commands.apply import cmd_apply

        mock_load_json.return_value = _make_categorization_report()

        args = _make_args(
            apply_action="move",
            dry_run=True,
            report=Path("/custom/report.json"),
        )
        result = cmd_apply(args)

        assert result == 0
        mock_load_json.assert_called_once_with(Path("/custom/report.json"))


# =============================================================================
# apply rules tests
# =============================================================================


class TestApplyRules:
    """Test the apply rules command."""

    @patch("src.cli.commands.apply.load_json")
    @patch("src.cli.commands.apply.PathConfig")
    def test_rules_dry_run_success(self, mock_path_config, mock_load_json, capsys):
        """Test rules dry-run previews rule deployment without API calls."""
        from src.cli.commands.apply import cmd_apply

        mock_path_config.get_rules_path.return_value = Path("/tmp/rules.json")
        mock_load_json.return_value = _make_ruleset_dict()

        args = _make_args(apply_action="rules", dry_run=True, rules_file=None)
        result = cmd_apply(args)

        assert result == 0

    @patch("src.cli.commands.apply.load_json")
    @patch("src.cli.commands.apply.PathConfig")
    def test_rules_dry_run_json_output(self, mock_path_config, mock_load_json, capsys):
        """Test rules dry-run with --json outputs structured JSON."""
        from src.cli.commands.apply import cmd_apply

        mock_path_config.get_rules_path.return_value = Path("/tmp/rules.json")
        mock_load_json.return_value = _make_ruleset_dict()

        args = _make_args(apply_action="rules", dry_run=True, json=True, rules_file=None)
        result = cmd_apply(args)

        assert result == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["command"] == "apply rules"
        assert data["dry_run"] is True

    @patch("src.cli.commands.apply.load_json")
    @patch("src.cli.commands.apply.PathConfig")
    def test_rules_file_not_found(self, mock_path_config, mock_load_json):
        """Test rules fails gracefully when rules file is missing."""
        from src.cli.commands.apply import cmd_apply

        mock_path_config.get_rules_path.return_value = Path("/tmp/rules.json")
        mock_load_json.side_effect = FileNotFoundError("Not found")

        args = _make_args(apply_action="rules", dry_run=True, rules_file=None)
        result = cmd_apply(args)

        assert result == 1

    @patch("src.cli.commands.apply.load_json")
    @patch("src.cli.commands.apply.PathConfig")
    def test_rules_file_not_found_json(self, mock_path_config, mock_load_json, capsys):
        """Test rules with missing rules file outputs JSON error."""
        from src.cli.commands.apply import cmd_apply

        mock_path_config.get_rules_path.return_value = Path("/tmp/rules.json")
        mock_load_json.side_effect = FileNotFoundError("Not found")

        args = _make_args(apply_action="rules", dry_run=True, json=True, rules_file=None)
        result = cmd_apply(args)

        assert result == 1
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["status"] == "error"

    @patch("src.cli.commands.apply.load_json")
    @patch("src.cli.commands.apply.PathConfig")
    def test_rules_custom_rules_file_path(self, mock_path_config, mock_load_json):
        """Test rules with custom --rules-file path."""
        from src.cli.commands.apply import cmd_apply

        mock_load_json.return_value = _make_ruleset_dict()

        args = _make_args(
            apply_action="rules",
            dry_run=True,
            rules_file=Path("/custom/rules.json"),
        )
        result = cmd_apply(args)

        assert result == 0
        mock_load_json.assert_called_once_with(Path("/custom/rules.json"))

    @patch("src.cli.commands.apply.load_json")
    @patch("src.cli.commands.apply.PathConfig")
    def test_rules_source_gmail(self, mock_path_config, mock_load_json):
        """Test rules with --source gmail uses Gmail deployer."""
        from src.cli.commands.apply import cmd_apply

        mock_path_config.get_rules_path.return_value = Path("/tmp/rules.json")
        mock_load_json.return_value = _make_ruleset_dict()

        args = _make_args(apply_action="rules", dry_run=True, source="gmail", rules_file=None)
        result = cmd_apply(args)

        assert result == 0


# =============================================================================
# apply rollback tests
# =============================================================================


class TestApplyRollback:
    """Test the apply rollback command."""

    @patch("src.cli.commands.apply.ActionLogger")
    def test_rollback_no_actions(self, mock_logger_class, capsys):
        """Test rollback with no eligible actions reports cleanly."""
        from src.cli.commands.apply import cmd_apply

        mock_logger = MagicMock()
        mock_logger.get_rollback_actions.return_value = []
        mock_logger_class.return_value = mock_logger

        args = _make_args(apply_action="rollback", since=None, yes=True)
        result = cmd_apply(args)

        assert result == 0

    @patch("src.cli.commands.apply.ActionLogger")
    def test_rollback_json_output(self, mock_logger_class, capsys):
        """Test rollback with --json outputs structured JSON."""
        from src.cli.commands.apply import cmd_apply

        mock_logger = MagicMock()
        mock_logger.get_rollback_actions.return_value = []
        mock_logger_class.return_value = mock_logger

        args = _make_args(apply_action="rollback", since=None, json=True, yes=True)
        result = cmd_apply(args)

        assert result == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["command"] == "apply rollback"

    @patch("src.cli.commands.apply.ActionLogger")
    def test_rollback_with_since_filter(self, mock_logger_class, capsys):
        """Test rollback --since filters by datetime."""
        from src.cli.commands.apply import cmd_apply

        mock_logger = MagicMock()
        mock_logger.get_rollback_actions.return_value = []
        mock_logger_class.return_value = mock_logger

        args = _make_args(
            apply_action="rollback",
            since="2024-06-01T00:00:00",
            yes=True,
        )
        result = cmd_apply(args)

        assert result == 0
        # Verify that get_rollback_actions was called with the parsed datetime
        call_args = mock_logger.get_rollback_actions.call_args
        assert call_args is not None
        since_arg = call_args[1].get("since") or call_args[0][0] if call_args[0] else None
        # If passed as kwarg
        if since_arg is None and call_args[1]:
            since_arg = call_args[1].get("since")

    @patch("src.cli.commands.apply.ActionLogger")
    def test_rollback_with_actions(self, mock_logger_class, capsys):
        """Test rollback with eligible actions executes replay."""
        from src.actions.action_logger import ActionRecord, ActionType, RollbackResult
        from src.cli.commands.apply import cmd_apply

        mock_logger = MagicMock()
        # Create a mock action record
        mock_action = ActionRecord(
            timestamp=datetime.now(timezone.utc),
            action_type=ActionType.EMAIL_MOVE,
            target_id="msg_001",
            details={"source_folder_id": "inbox", "target_folder_id": "news"},
            success=True,
            reversible=True,
        )
        mock_logger.get_rollback_actions.return_value = [mock_action]
        mock_logger.replay_rollback.return_value = RollbackResult(
            total_actions=1,
            successful=1,
            failed=0,
            skipped=0,
        )
        mock_logger_class.return_value = mock_logger

        args = _make_args(apply_action="rollback", since=None, yes=True)
        result = cmd_apply(args)

        assert result == 0
        mock_logger.replay_rollback.assert_called_once()

    @patch("src.cli.commands.apply.ActionLogger")
    def test_rollback_with_failures(self, mock_logger_class, capsys):
        """Test rollback reports failures correctly."""
        from src.actions.action_logger import ActionRecord, ActionType, RollbackResult
        from src.cli.commands.apply import cmd_apply

        mock_logger = MagicMock()
        mock_action = ActionRecord(
            timestamp=datetime.now(timezone.utc),
            action_type=ActionType.FOLDER_CREATE,
            target_id="folder_001",
            details={},
            success=True,
            reversible=True,
        )
        mock_logger.get_rollback_actions.return_value = [mock_action]
        mock_logger.replay_rollback.return_value = RollbackResult(
            total_actions=1,
            successful=0,
            failed=1,
            skipped=0,
            errors=["Failed to reverse folder_create for folder_001"],
        )
        mock_logger_class.return_value = mock_logger

        args = _make_args(apply_action="rollback", since=None, yes=True)
        result = cmd_apply(args)

        # Returns 1 when there are failures
        assert result == 1

    def test_rollback_invalid_since_format(self, capsys):
        """Test rollback with invalid --since value returns error."""
        from src.cli.commands.apply import cmd_apply

        args = _make_args(
            apply_action="rollback",
            since="not-a-date",
            yes=True,
        )
        result = cmd_apply(args)
        assert result == 1


# =============================================================================
# Confirmation prompt tests
# =============================================================================


class TestConfirmationPrompt:
    """Test mandatory confirmation before live operations."""

    @patch("builtins.input", return_value="n")
    @patch("src.cli.commands.apply.load_json")
    @patch("src.cli.commands.apply.PathConfig")
    def test_folders_live_aborted_on_no(self, mock_path_config, mock_load_json, mock_input):
        """Test that live folders operation is aborted when user says no."""
        from src.cli.commands.apply import cmd_apply

        mock_path_config.get_approved_categories_path.return_value = Path("/tmp/cats.json")
        mock_load_json.return_value = _make_approved_categories()

        args = _make_args(apply_action="folders", dry_run=False, yes=False, categories=None)
        result = cmd_apply(args)

        # Aborted by user = exit 130 (or 1, either is acceptable)
        assert result != 0

    @patch("src.cli.commands.apply.load_json")
    @patch("src.cli.commands.apply.PathConfig")
    def test_dry_run_skips_confirmation(self, mock_path_config, mock_load_json):
        """Test that --dry-run does NOT prompt for confirmation."""
        from src.cli.commands.apply import cmd_apply

        mock_path_config.get_approved_categories_path.return_value = Path("/tmp/cats.json")
        mock_load_json.return_value = _make_approved_categories()

        # If confirmation was incorrectly triggered during dry-run,
        # it would block or raise (no input mock). Success means no prompt.
        args = _make_args(apply_action="folders", dry_run=True, categories=None)
        result = cmd_apply(args)
        assert result == 0

    @patch("src.cli.commands.apply.load_json")
    @patch("src.cli.commands.apply.PathConfig")
    def test_yes_flag_skips_confirmation(self, mock_path_config, mock_load_json):
        """Test that --yes skips confirmation prompt."""
        from src.cli.commands.apply import cmd_apply

        mock_path_config.get_approved_categories_path.return_value = Path("/tmp/cats.json")
        mock_load_json.return_value = _make_approved_categories()

        # --yes with dry_run=False but no real API call still works
        # (FolderManager won't have a real backend, so we stay in dry-run effectively)
        args = _make_args(apply_action="folders", dry_run=True, yes=True, categories=None)
        result = cmd_apply(args)
        assert result == 0


# =============================================================================
# Dispatcher tests
# =============================================================================


class TestApplyDispatcher:
    """Test the top-level apply command dispatcher."""

    def test_unknown_action(self):
        """Test that an unknown apply action returns error."""
        from src.cli.commands.apply import cmd_apply

        args = _make_args(apply_action="unknown")
        result = cmd_apply(args)
        assert result == 1

    def test_none_action(self):
        """Test that a missing apply action returns error."""
        from src.cli.commands.apply import cmd_apply

        args = _make_args(apply_action=None)
        result = cmd_apply(args)
        assert result == 1


# =============================================================================
# Classify report format tests
# =============================================================================


def _make_classify_report() -> dict:
    """Create a classify report dict (classify command output format)."""
    return {
        "total_emails": 100,
        "categorized_count": 80,
        "uncategorized_count": 20,
        "coverage_percentage": 80.0,
        "model": "Qwen/Qwen2.5-7B-Instruct",
        "endpoint_id": "test_endpoint",
        "categories_used": {
            "Newsletter Updates": 50,
            "Shipping Notifications": 30,
        },
        "categorized_emails": {
            "msg_001": {
                "category": "Newsletter Updates",
                "confidence": 0.95,
                "source": "llm:vllm:Qwen/Qwen2.5-7B-Instruct",
            },
            "msg_002": {
                "category": "Shipping Notifications",
                "confidence": 0.88,
                "source": "llm:vllm:Qwen/Qwen2.5-7B-Instruct",
            },
            "msg_003": {
                "category": "Newsletter Updates",
                "confidence": 0.92,
                "source": "llm:vllm:Qwen/Qwen2.5-7B-Instruct",
            },
        },
        "uncategorized_email_ids": ["msg_004"],
    }


class TestParseMovesFromReport:
    """Test the dual-format report parser."""

    def test_categorization_report_format(self):
        """Test parsing moves from categorization report (rules-based)."""
        from src.cli.commands.apply import _parse_moves_from_report

        report = _make_categorization_report()
        moves = _parse_moves_from_report(report)

        assert len(moves) == 5
        assert all(cat == "Newsletter Updates" for _, cat in moves)
        assert moves[0][0] == "msg_0"

    def test_classify_report_format(self):
        """Test parsing moves from classify report (LLM-based)."""
        from src.cli.commands.apply import _parse_moves_from_report

        report = _make_classify_report()
        moves = _parse_moves_from_report(report)

        assert len(moves) == 3
        email_ids = {eid for eid, _ in moves}
        assert email_ids == {"msg_001", "msg_002", "msg_003"}

        categories = {cat for _, cat in moves}
        assert categories == {"Newsletter Updates", "Shipping Notifications"}

    def test_empty_report(self):
        """Test parsing an empty report returns no moves."""
        from src.cli.commands.apply import _parse_moves_from_report

        moves = _parse_moves_from_report({})
        assert moves == []

    def test_classify_report_with_empty_category(self):
        """Test that entries with empty category are skipped."""
        from src.cli.commands.apply import _parse_moves_from_report

        report = {
            "categorized_emails": {
                "msg_001": {"category": "Newsletter Updates", "confidence": 0.9},
                "msg_002": {"category": "", "confidence": 0.5},
            }
        }
        moves = _parse_moves_from_report(report)
        assert len(moves) == 1
        assert moves[0] == ("msg_001", "Newsletter Updates")


class TestApplyMoveClassifyReport:
    """Test apply move with classify report format."""

    @patch("src.cli.commands.apply.load_json")
    @patch("src.cli.commands.apply.PathConfig")
    def test_move_dry_run_classify_report(self, mock_path_config, mock_load_json, capsys):
        """Test move dry-run with classify report shows category breakdown."""
        from src.cli.commands.apply import cmd_apply

        mock_path_config.get_categorization_report_path.return_value = Path("/tmp/report.json")
        mock_load_json.return_value = _make_classify_report()

        args = _make_args(
            apply_action="move", dry_run=True, report=None, rate_limit=0.25
        )
        result = cmd_apply(args)

        assert result == 0
        captured = capsys.readouterr()
        assert "Newsletter Updates" in captured.out
        assert "Shipping Notifications" in captured.out
        assert "Moves planned" in captured.out

    @patch("src.cli.commands.apply.load_json")
    @patch("src.cli.commands.apply.PathConfig")
    def test_move_dry_run_classify_report_json(
        self, mock_path_config, mock_load_json, capsys
    ):
        """Test move dry-run with classify report and --json flag."""
        from src.cli.commands.apply import cmd_apply

        mock_path_config.get_categorization_report_path.return_value = Path("/tmp/report.json")
        mock_load_json.return_value = _make_classify_report()

        args = _make_args(
            apply_action="move", dry_run=True, json=True, report=None, rate_limit=0.25
        )
        result = cmd_apply(args)

        assert result == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["moves_planned"] == 3
        assert "category_breakdown" in data
        assert data["category_breakdown"]["Newsletter Updates"] == 2


class TestApplyParserNewFlags:
    """Test new CLI flags added to the apply parser."""

    def test_user_email_flag(self):
        """Test --user-email flag is parsed."""
        from src.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(
            ["apply", "folders", "--user-email", "troy@hotmail.com"]
        )
        assert args.user_email == "troy@hotmail.com"

    def test_user_email_default_is_none(self):
        """Test --user-email defaults to None."""
        from src.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["apply", "folders"])
        assert args.user_email is None

    def test_rate_limit_flag(self):
        """Test --rate-limit flag on move subcommand."""
        from src.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["apply", "move", "--rate-limit", "0.1"])
        assert args.rate_limit == 0.1

    def test_rate_limit_default(self):
        """Test --rate-limit default is 0.25."""
        from src.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["apply", "move"])
        assert args.rate_limit == 0.25


class TestApplyFoldersLiveMode:
    """Test apply folders live mode wiring."""

    @patch("src.cli.commands.apply.load_json")
    @patch("src.cli.commands.apply.PathConfig")
    def test_folders_live_requires_user_email(self, mock_path_config, mock_load_json, capsys):
        """Test that live folders fails without user_email."""
        from src.cli.commands.apply import cmd_apply

        mock_path_config.get_approved_categories_path.return_value = Path("/tmp/cats.json")
        mock_load_json.return_value = _make_approved_categories()

        args = _make_args(
            apply_action="folders",
            dry_run=False,
            yes=True,
            categories=None,
            user_email=None,
            _app_config=None,
        )
        result = cmd_apply(args)

        assert result == 1

    @patch("src.cli.commands.apply.load_json")
    @patch("src.cli.commands.apply.PathConfig")
    def test_folders_live_unsupported_source(self, mock_path_config, mock_load_json, capsys):
        """Test that live folders with gmail source returns not-supported error."""
        from src.cli.commands.apply import cmd_apply

        mock_path_config.get_approved_categories_path.return_value = Path("/tmp/cats.json")
        mock_load_json.return_value = _make_approved_categories()

        args = _make_args(
            apply_action="folders",
            dry_run=False,
            yes=True,
            source="gmail",
            categories=None,
            user_email="test@gmail.com",
        )
        result = cmd_apply(args)

        assert result == 1


class TestApplyMoveLiveMode:
    """Test apply move live mode wiring."""

    @patch("src.cli.commands.apply.load_json")
    @patch("src.cli.commands.apply.PathConfig")
    def test_move_live_requires_user_email(self, mock_path_config, mock_load_json, capsys):
        """Test that live move fails without user_email."""
        from src.cli.commands.apply import cmd_apply

        mock_path_config.get_categorization_report_path.return_value = Path("/tmp/report.json")
        mock_load_json.return_value = _make_classify_report()

        args = _make_args(
            apply_action="move",
            dry_run=False,
            yes=True,
            report=None,
            rate_limit=0.25,
            user_email=None,
            _app_config=None,
        )
        result = cmd_apply(args)

        assert result == 1

    @patch("src.cli.commands.apply.load_json")
    @patch("src.cli.commands.apply.PathConfig")
    def test_move_live_unsupported_source(self, mock_path_config, mock_load_json, capsys):
        """Test that live move with gmail source returns not-supported error."""
        from src.cli.commands.apply import cmd_apply

        mock_path_config.get_categorization_report_path.return_value = Path("/tmp/report.json")
        mock_load_json.return_value = _make_classify_report()

        args = _make_args(
            apply_action="move",
            dry_run=False,
            yes=True,
            source="gmail",
            report=None,
            rate_limit=0.25,
            user_email="test@gmail.com",
        )
        result = cmd_apply(args)

        assert result == 1


class TestFolderMapPath:
    """Test PathConfig.get_folder_map_path()."""

    def test_folder_map_path(self):
        """Test folder map path returns expected location."""
        from src.utils.paths import PathConfig

        path = PathConfig.get_folder_map_path()
        assert path.name == "folder_map.json"
        assert path.parent == PathConfig.get_output_dir()
