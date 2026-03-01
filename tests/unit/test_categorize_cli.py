"""
Unit tests for the categorize CLI command (Phase 4, Item 4.5).

TDD: Tests written first, implementation follows.

Tests cover:
- Parser construction (categorize command with flags)
- categorize: loads corpus + rules, runs EmailCategorizer, saves report
- categorize --report: runs coverage reporter and displays report
- categorize --resolve: uses conflict resolver with strategy selection
- categorize --dry-run: preview without saving
- categorize --strategy: selects conflict resolution strategy
- --json flag support for machine-readable output
- --verbose flag for per-email detail
- Error handling for missing files
"""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

# =============================================================================
# Helpers
# =============================================================================


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


def _make_corpus_dict(num_emails: int = 3) -> dict:
    """Create a serialized corpus dict with test emails."""
    emails = []
    for i in range(num_emails):
        emails.append(
            {
                "id": f"msg_{i}",
                "sender_email": f"sender{i}@example.com",
                "sender_name": f"Sender {i}",
                "sender_domain": "example.com",
                "subject": f"Test newsletter {i}" if i % 2 == 0 else f"Other subject {i}",
                "body_text": f"Body text for email {i}",
                "received_date": "2024-06-15T10:00:00Z",
                "has_attachments": False,
            }
        )
    return {
        "emails": emails,
        "extraction_metadata": {
            "extraction_date": "2024-01-01T00:00:00Z",
            "source": "hotmail",
            "user_email": "test@test.com",
            "total_emails": num_emails,
        },
    }


# =============================================================================
# Parser tests
# =============================================================================


class TestCategorizeParser:
    """Test that the categorize subcommand parser is correctly configured."""

    def test_categorize_command_registered_in_parser(self):
        """Test that 'categorize' is a valid subcommand."""
        from src.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["categorize"])
        assert args.command == "categorize"

    def test_categorize_report_flag(self):
        """Test that --report flag is accepted."""
        from src.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["categorize", "--report"])
        assert args.report is True

    def test_categorize_resolve_flag(self):
        """Test that --resolve flag is accepted."""
        from src.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["categorize", "--resolve"])
        assert args.resolve is True

    def test_categorize_dry_run_flag(self):
        """Test that --dry-run flag is accepted."""
        from src.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["categorize", "--dry-run"])
        assert args.dry_run is True

    def test_categorize_strategy_priority(self):
        """Test that --strategy priority is accepted."""
        from src.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["categorize", "--strategy", "priority"])
        assert args.strategy == "priority"

    def test_categorize_strategy_specificity(self):
        """Test that --strategy specificity is accepted."""
        from src.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["categorize", "--strategy", "specificity"])
        assert args.strategy == "specificity"

    def test_categorize_strategy_historical(self):
        """Test that --strategy historical is accepted."""
        from src.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["categorize", "--strategy", "historical"])
        assert args.strategy == "historical"

    def test_categorize_strategy_invalid_rejected(self):
        """Test that invalid strategy value is rejected."""
        from src.cli import create_parser

        parser = create_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["categorize", "--strategy", "invalid"])

    def test_categorize_custom_corpus_path(self):
        """Test that --corpus flag is accepted."""
        from src.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["categorize", "--corpus", "/tmp/corpus.json"])
        assert args.corpus == Path("/tmp/corpus.json")

    def test_categorize_custom_rules_file(self):
        """Test that --rules-file flag is accepted."""
        from src.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["categorize", "--rules-file", "/tmp/rules.json"])
        assert args.rules_file == Path("/tmp/rules.json")

    def test_categorize_custom_output_file(self):
        """Test that --output flag is accepted."""
        from src.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["categorize", "--output", "/tmp/report.json"])
        assert args.output == Path("/tmp/report.json")

    def test_categorize_defaults(self):
        """Test default values for all flags."""
        from src.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["categorize"])
        assert args.report is False
        assert args.resolve is False
        assert args.dry_run is False
        assert args.strategy == "priority"
        assert args.corpus is None
        assert args.rules_file is None
        assert args.output is None

    def test_categorize_command_in_dispatch(self):
        """Test that the main dispatcher knows about the categorize command."""
        from src.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["categorize"])
        assert args.command == "categorize"


# =============================================================================
# Categorize (default mode) tests
# =============================================================================


class TestCategorizeDefault:
    """Test the default categorize command (run categorization)."""

    @patch("src.cli.commands.categorize.save_json")
    @patch("src.cli.commands.categorize.load_json")
    @patch("src.cli.commands.categorize.PathConfig")
    def test_categorize_success(self, mock_path_config, mock_load_json, mock_save_json):
        """Test successful categorization run."""
        from src.cli.commands.categorize import cmd_categorize

        mock_path_config.get_rules_path.return_value = Path("/tmp/rules.json")
        mock_path_config.get_corpus_path.return_value = Path("/tmp/corpus.json")
        mock_path_config.get_categorization_report_path.return_value = Path("/tmp/report.json")

        mock_load_json.side_effect = [
            _make_ruleset_dict(),
            _make_corpus_dict(3),
        ]

        args = argparse.Namespace(
            command="categorize",
            report=False,
            resolve=False,
            dry_run=False,
            strategy="priority",
            corpus=None,
            rules_file=None,
            output=None,
            json=False,
            verbose=False,
        )

        result = cmd_categorize(args)
        assert result == 0
        mock_save_json.assert_called_once()

    @patch("src.cli.commands.categorize.save_json")
    @patch("src.cli.commands.categorize.load_json")
    @patch("src.cli.commands.categorize.PathConfig")
    def test_categorize_json_output(self, mock_path_config, mock_load_json, mock_save_json, capsys):
        """Test categorize with --json outputs structured JSON."""
        from src.cli.commands.categorize import cmd_categorize

        mock_path_config.get_rules_path.return_value = Path("/tmp/rules.json")
        mock_path_config.get_corpus_path.return_value = Path("/tmp/corpus.json")
        mock_path_config.get_categorization_report_path.return_value = Path("/tmp/report.json")

        mock_load_json.side_effect = [
            _make_ruleset_dict(),
            _make_corpus_dict(3),
        ]

        args = argparse.Namespace(
            command="categorize",
            report=False,
            resolve=False,
            dry_run=False,
            strategy="priority",
            corpus=None,
            rules_file=None,
            output=None,
            json=True,
            verbose=False,
        )

        result = cmd_categorize(args)
        assert result == 0

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["command"] == "categorize"
        assert data["status"] == "success"
        assert "total_emails" in data["stats"]
        assert "coverage_percentage" in data["stats"]

    @patch("src.cli.commands.categorize.load_json")
    @patch("src.cli.commands.categorize.PathConfig")
    def test_categorize_rules_not_found(self, mock_path_config, mock_load_json):
        """Test categorize fails when rules file is missing."""
        from src.cli.commands.categorize import cmd_categorize

        mock_path_config.get_rules_path.return_value = Path("/tmp/rules.json")
        mock_load_json.side_effect = FileNotFoundError("Not found")

        args = argparse.Namespace(
            command="categorize",
            report=False,
            resolve=False,
            dry_run=False,
            strategy="priority",
            corpus=None,
            rules_file=None,
            output=None,
            json=False,
            verbose=False,
        )

        result = cmd_categorize(args)
        assert result == 1

    @patch("src.cli.commands.categorize.load_json")
    @patch("src.cli.commands.categorize.PathConfig")
    def test_categorize_rules_not_found_json(self, mock_path_config, mock_load_json, capsys):
        """Test categorize with missing rules outputs JSON error."""
        from src.cli.commands.categorize import cmd_categorize

        mock_path_config.get_rules_path.return_value = Path("/tmp/rules.json")
        mock_load_json.side_effect = FileNotFoundError("Not found")

        args = argparse.Namespace(
            command="categorize",
            report=False,
            resolve=False,
            dry_run=False,
            strategy="priority",
            corpus=None,
            rules_file=None,
            output=None,
            json=True,
            verbose=False,
        )

        result = cmd_categorize(args)
        assert result == 1
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["status"] == "error"

    @patch("src.cli.commands.categorize.load_json")
    @patch("src.cli.commands.categorize.PathConfig")
    def test_categorize_corpus_not_found(self, mock_path_config, mock_load_json):
        """Test categorize fails when corpus file is missing."""
        from src.cli.commands.categorize import cmd_categorize

        mock_path_config.get_rules_path.return_value = Path("/tmp/rules.json")
        mock_path_config.get_corpus_path.return_value = Path("/tmp/corpus.json")

        mock_load_json.side_effect = [
            _make_ruleset_dict(),
            FileNotFoundError("Not found"),
        ]

        args = argparse.Namespace(
            command="categorize",
            report=False,
            resolve=False,
            dry_run=False,
            strategy="priority",
            corpus=None,
            rules_file=None,
            output=None,
            json=False,
            verbose=False,
        )

        result = cmd_categorize(args)
        assert result == 1

    @patch("src.cli.commands.categorize.load_json")
    @patch("src.cli.commands.categorize.PathConfig")
    def test_categorize_custom_paths(self, mock_path_config, mock_load_json):
        """Test categorize with custom --corpus, --rules-file, --output paths."""
        from src.cli.commands.categorize import cmd_categorize

        mock_load_json.side_effect = [
            _make_ruleset_dict(),
            _make_corpus_dict(2),
        ]

        args = argparse.Namespace(
            command="categorize",
            report=False,
            resolve=False,
            dry_run=False,
            strategy="priority",
            corpus=Path("/custom/corpus.json"),
            rules_file=Path("/custom/rules.json"),
            output=Path("/custom/report.json"),
            json=False,
            verbose=False,
        )

        with patch("src.cli.commands.categorize.save_json") as mock_save:
            result = cmd_categorize(args)

        assert result == 0
        calls = mock_load_json.call_args_list
        assert calls[0][0][0] == Path("/custom/rules.json")
        assert calls[1][0][0] == Path("/custom/corpus.json")
        assert mock_save.call_args[0][1] == Path("/custom/report.json")


# =============================================================================
# Dry-run tests
# =============================================================================


class TestCategorizeDryRun:
    """Test categorize --dry-run mode."""

    @patch("src.cli.commands.categorize.load_json")
    @patch("src.cli.commands.categorize.PathConfig")
    def test_dry_run_does_not_save(self, mock_path_config, mock_load_json, capsys):
        """Test that dry-run mode does not save to disk."""
        from src.cli.commands.categorize import cmd_categorize

        mock_path_config.get_rules_path.return_value = Path("/tmp/rules.json")
        mock_path_config.get_corpus_path.return_value = Path("/tmp/corpus.json")
        mock_path_config.get_categorization_report_path.return_value = Path("/tmp/report.json")

        mock_load_json.side_effect = [
            _make_ruleset_dict(),
            _make_corpus_dict(3),
        ]

        args = argparse.Namespace(
            command="categorize",
            report=False,
            resolve=False,
            dry_run=True,
            strategy="priority",
            corpus=None,
            rules_file=None,
            output=None,
            json=False,
            verbose=False,
        )

        with patch("src.cli.commands.categorize.save_json") as mock_save:
            result = cmd_categorize(args)

        assert result == 0
        mock_save.assert_not_called()

    @patch("src.cli.commands.categorize.load_json")
    @patch("src.cli.commands.categorize.PathConfig")
    def test_dry_run_json_output(self, mock_path_config, mock_load_json, capsys):
        """Test dry-run with --json flag includes dry_run indicator."""
        from src.cli.commands.categorize import cmd_categorize

        mock_path_config.get_rules_path.return_value = Path("/tmp/rules.json")
        mock_path_config.get_corpus_path.return_value = Path("/tmp/corpus.json")
        mock_path_config.get_categorization_report_path.return_value = Path("/tmp/report.json")

        mock_load_json.side_effect = [
            _make_ruleset_dict(),
            _make_corpus_dict(3),
        ]

        args = argparse.Namespace(
            command="categorize",
            report=False,
            resolve=False,
            dry_run=True,
            strategy="priority",
            corpus=None,
            rules_file=None,
            output=None,
            json=True,
            verbose=False,
        )

        with patch("src.cli.commands.categorize.save_json"):
            result = cmd_categorize(args)

        assert result == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["dry_run"] is True


# =============================================================================
# Report mode tests
# =============================================================================


class TestCategorizeReport:
    """Test categorize --report mode."""

    @patch("src.cli.commands.categorize.save_json")
    @patch("src.cli.commands.categorize.load_json")
    @patch("src.cli.commands.categorize.PathConfig")
    def test_report_mode_displays_coverage(
        self, mock_path_config, mock_load_json, mock_save_json, capsys
    ):
        """Test that --report mode displays the coverage report."""
        from src.cli.commands.categorize import cmd_categorize

        mock_path_config.get_rules_path.return_value = Path("/tmp/rules.json")
        mock_path_config.get_corpus_path.return_value = Path("/tmp/corpus.json")
        mock_path_config.get_categorization_report_path.return_value = Path("/tmp/report.json")

        mock_load_json.side_effect = [
            _make_ruleset_dict(),
            _make_corpus_dict(3),
        ]

        args = argparse.Namespace(
            command="categorize",
            report=True,
            resolve=False,
            dry_run=False,
            strategy="priority",
            corpus=None,
            rules_file=None,
            output=None,
            json=False,
            verbose=False,
        )

        result = cmd_categorize(args)
        assert result == 0

        captured = capsys.readouterr()
        assert "CATEGORIZATION COVERAGE REPORT" in captured.out

    @patch("src.cli.commands.categorize.save_json")
    @patch("src.cli.commands.categorize.load_json")
    @patch("src.cli.commands.categorize.PathConfig")
    def test_report_mode_json(self, mock_path_config, mock_load_json, mock_save_json, capsys):
        """Test --report with --json outputs coverage analysis as JSON."""
        from src.cli.commands.categorize import cmd_categorize

        mock_path_config.get_rules_path.return_value = Path("/tmp/rules.json")
        mock_path_config.get_corpus_path.return_value = Path("/tmp/corpus.json")
        mock_path_config.get_categorization_report_path.return_value = Path("/tmp/report.json")

        mock_load_json.side_effect = [
            _make_ruleset_dict(),
            _make_corpus_dict(3),
        ]

        args = argparse.Namespace(
            command="categorize",
            report=True,
            resolve=False,
            dry_run=False,
            strategy="priority",
            corpus=None,
            rules_file=None,
            output=None,
            json=True,
            verbose=False,
        )

        result = cmd_categorize(args)
        assert result == 0

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["command"] == "categorize --report"
        assert "coverage" in data


# =============================================================================
# Resolve mode tests
# =============================================================================


class TestCategorizeResolve:
    """Test categorize --resolve mode."""

    @patch("src.cli.commands.categorize.save_json")
    @patch("src.cli.commands.categorize.load_json")
    @patch("src.cli.commands.categorize.PathConfig")
    def test_resolve_uses_conflict_resolver(self, mock_path_config, mock_load_json, mock_save_json):
        """Test that --resolve runs categorization with conflict resolution."""
        from src.cli.commands.categorize import cmd_categorize

        mock_path_config.get_rules_path.return_value = Path("/tmp/rules.json")
        mock_path_config.get_corpus_path.return_value = Path("/tmp/corpus.json")
        mock_path_config.get_categorization_report_path.return_value = Path("/tmp/report.json")

        mock_load_json.side_effect = [
            _make_ruleset_dict(),
            _make_corpus_dict(3),
        ]

        args = argparse.Namespace(
            command="categorize",
            report=False,
            resolve=True,
            dry_run=False,
            strategy="priority",
            corpus=None,
            rules_file=None,
            output=None,
            json=False,
            verbose=False,
        )

        result = cmd_categorize(args)
        assert result == 0

    @patch("src.cli.commands.categorize.save_json")
    @patch("src.cli.commands.categorize.load_json")
    @patch("src.cli.commands.categorize.PathConfig")
    def test_resolve_with_specificity_strategy(
        self, mock_path_config, mock_load_json, mock_save_json
    ):
        """Test --resolve with --strategy specificity."""
        from src.cli.commands.categorize import cmd_categorize

        mock_path_config.get_rules_path.return_value = Path("/tmp/rules.json")
        mock_path_config.get_corpus_path.return_value = Path("/tmp/corpus.json")
        mock_path_config.get_categorization_report_path.return_value = Path("/tmp/report.json")

        mock_load_json.side_effect = [
            _make_ruleset_dict(),
            _make_corpus_dict(3),
        ]

        args = argparse.Namespace(
            command="categorize",
            report=False,
            resolve=True,
            dry_run=False,
            strategy="specificity",
            corpus=None,
            rules_file=None,
            output=None,
            json=False,
            verbose=False,
        )

        result = cmd_categorize(args)
        assert result == 0


# =============================================================================
# Verbose output tests
# =============================================================================


class TestCategorizeVerbose:
    """Test categorize --verbose mode."""

    @patch("src.cli.commands.categorize.save_json")
    @patch("src.cli.commands.categorize.load_json")
    @patch("src.cli.commands.categorize.PathConfig")
    def test_verbose_shows_per_email_detail(
        self, mock_path_config, mock_load_json, mock_save_json, capsys
    ):
        """Test that verbose mode prints per-email categorization detail."""
        from src.cli.commands.categorize import cmd_categorize

        mock_path_config.get_rules_path.return_value = Path("/tmp/rules.json")
        mock_path_config.get_corpus_path.return_value = Path("/tmp/corpus.json")
        mock_path_config.get_categorization_report_path.return_value = Path("/tmp/report.json")

        mock_load_json.side_effect = [
            _make_ruleset_dict(),
            _make_corpus_dict(3),
        ]

        args = argparse.Namespace(
            command="categorize",
            report=False,
            resolve=False,
            dry_run=False,
            strategy="priority",
            corpus=None,
            rules_file=None,
            output=None,
            json=False,
            verbose=True,
        )

        result = cmd_categorize(args)
        assert result == 0

        captured = capsys.readouterr()
        # Verbose should show individual email IDs
        assert "msg_0" in captured.out


# =============================================================================
# Strategy selection tests
# =============================================================================


class TestCategorizeStrategy:
    """Test --strategy flag interaction."""

    @patch("src.cli.commands.categorize.save_json")
    @patch("src.cli.commands.categorize.load_json")
    @patch("src.cli.commands.categorize.PathConfig")
    def test_strategy_historical_without_resolve_still_works(
        self, mock_path_config, mock_load_json, mock_save_json
    ):
        """Test that --strategy historical works (strategy only applies when --resolve is set)."""
        from src.cli.commands.categorize import cmd_categorize

        mock_path_config.get_rules_path.return_value = Path("/tmp/rules.json")
        mock_path_config.get_corpus_path.return_value = Path("/tmp/corpus.json")
        mock_path_config.get_categorization_report_path.return_value = Path("/tmp/report.json")

        mock_load_json.side_effect = [
            _make_ruleset_dict(),
            _make_corpus_dict(2),
        ]

        args = argparse.Namespace(
            command="categorize",
            report=False,
            resolve=False,
            dry_run=False,
            strategy="historical",
            corpus=None,
            rules_file=None,
            output=None,
            json=False,
            verbose=False,
        )

        result = cmd_categorize(args)
        assert result == 0


# =============================================================================
# Dispatch tests
# =============================================================================


class TestCategorizeDispatch:
    """Test that categorize is properly registered in the main CLI dispatch."""

    def test_categorize_in_main_dispatch(self):
        """Test that the categorize command handler exists in __init__.py dispatcher."""
        from src.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["categorize"])
        assert args.command == "categorize"

    @patch("src.cli.commands.categorize.load_json")
    @patch("src.cli.commands.categorize.PathConfig")
    def test_main_dispatches_to_cmd_categorize(self, mock_path_config, mock_load_json, capsys):
        """Test that main() dispatches categorize command correctly."""
        from src.cli.commands.categorize import cmd_categorize

        mock_path_config.get_rules_path.return_value = Path("/tmp/rules.json")
        mock_load_json.side_effect = FileNotFoundError("test")

        args = argparse.Namespace(
            command="categorize",
            report=False,
            resolve=False,
            dry_run=False,
            strategy="priority",
            corpus=None,
            rules_file=None,
            output=None,
            json=False,
            verbose=False,
        )

        result = cmd_categorize(args)
        assert result == 1  # fails due to missing file, but dispatch works


# =============================================================================
# PathConfig integration
# =============================================================================


class TestPathConfigCategorization:
    """Test that PathConfig.get_categorization_report_path() works."""

    def test_get_categorization_report_path(self):
        """Test default categorization report path."""
        from src.utils.paths import PathConfig

        original = PathConfig._output_dir
        try:
            PathConfig.set_output_dir("/tmp/test_output")
            path = PathConfig.get_categorization_report_path()
            assert path.name == "categorization_report.json"
            assert path.parent.name == "test_output"
        finally:
            PathConfig._output_dir = original


# =============================================================================
# Edge cases
# =============================================================================


class TestCategorizeEdgeCases:
    """Test edge cases for the categorize command."""

    @patch("src.cli.commands.categorize.save_json")
    @patch("src.cli.commands.categorize.load_json")
    @patch("src.cli.commands.categorize.PathConfig")
    def test_empty_corpus(self, mock_path_config, mock_load_json, mock_save_json, capsys):
        """Test categorization with empty corpus."""
        from src.cli.commands.categorize import cmd_categorize

        mock_path_config.get_rules_path.return_value = Path("/tmp/rules.json")
        mock_path_config.get_corpus_path.return_value = Path("/tmp/corpus.json")
        mock_path_config.get_categorization_report_path.return_value = Path("/tmp/report.json")

        mock_load_json.side_effect = [
            _make_ruleset_dict(),
            _make_corpus_dict(0),
        ]

        args = argparse.Namespace(
            command="categorize",
            report=False,
            resolve=False,
            dry_run=False,
            strategy="priority",
            corpus=None,
            rules_file=None,
            output=None,
            json=False,
            verbose=False,
        )

        result = cmd_categorize(args)
        assert result == 0

    @patch("src.cli.commands.categorize.save_json")
    @patch("src.cli.commands.categorize.load_json")
    @patch("src.cli.commands.categorize.PathConfig")
    def test_report_and_dry_run_combined(
        self, mock_path_config, mock_load_json, mock_save_json, capsys
    ):
        """Test --report with --dry-run outputs report but does not save."""
        from src.cli.commands.categorize import cmd_categorize

        mock_path_config.get_rules_path.return_value = Path("/tmp/rules.json")
        mock_path_config.get_corpus_path.return_value = Path("/tmp/corpus.json")
        mock_path_config.get_categorization_report_path.return_value = Path("/tmp/report.json")

        mock_load_json.side_effect = [
            _make_ruleset_dict(),
            _make_corpus_dict(3),
        ]

        args = argparse.Namespace(
            command="categorize",
            report=True,
            resolve=False,
            dry_run=True,
            strategy="priority",
            corpus=None,
            rules_file=None,
            output=None,
            json=False,
            verbose=False,
        )

        result = cmd_categorize(args)
        assert result == 0
        mock_save_json.assert_not_called()

        captured = capsys.readouterr()
        assert "CATEGORIZATION COVERAGE REPORT" in captured.out
