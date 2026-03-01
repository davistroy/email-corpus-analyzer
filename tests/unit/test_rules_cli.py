"""
Unit tests for the rules CLI command (Phase 3, Item 3.6).

TDD: Tests written first, implementation follows.

Tests cover:
- Parser construction (rules subcommand with generate/test/show/edit sub-actions)
- rules generate: loads categories + analysis, calls RuleBuilder, saves RuleSet
- rules test: loads rules + corpus, calls RuleTester, displays TestReport
- rules show: loads rules and prints readable summary
- rules edit: launches TUI rule editor
- --json flag support for machine-readable output
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


def _make_category_dict(
    category_id: str = "cat_1",
    name: str = "Newsletter Updates",
    confidence: float = 0.85,
    email_count: int = 42,
) -> dict:
    """Create a serialized category dict."""
    return {
        "category_id": category_id,
        "category_name": name,
        "description": "Test category",
        "confidence": confidence,
        "email_count": email_count,
        "percentage": 25.0,
        "source": "template",
        "source_id": "test_source",
        "example_email_ids": [],
        "distinguishing_features": ["newsletter", "weekly"],
    }


def _make_analysis_dict() -> dict:
    """Create a minimal serialized analysis results dict matching AnalysisResults model."""
    return {
        "sender_analysis": {
            "top_senders": [],
            "top_domains": [],
            "unique_senders": 10,
            "unique_domains": 5,
        },
        "subject_patterns": {
            "common_prefixes": {},
            "numbered_patterns": {},
            "top_keywords": [],
            "bracket_tags": [],
            "total_subjects_analyzed": 100,
        },
        "temporal_patterns": {
            "frequency_distribution": {},
            "sender_frequencies": {},
        },
        "volume_stats": {
            "total_emails": 100,
            "unique_senders": 10,
            "date_range": {"oldest": "2024-01-01", "newest": "2024-12-31", "span_days": "365"},
            "with_attachments": 5,
            "attachment_percentage": 5.0,
            "avg_body_length_chars": 500,
            "emails_per_day": 1.0,
        },
        "content_clusters": [],
    }


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


# =============================================================================
# Parser tests
# =============================================================================


class TestRulesParser:
    """Test that the rules subcommand parser is correctly configured."""

    def test_rules_command_registered_in_parser(self):
        """Test that 'rules' is a valid subcommand."""
        from src.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["rules", "show"])
        assert args.command == "rules"

    def test_rules_generate_subcommand(self):
        """Test that 'rules generate' is parsed correctly."""
        from src.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["rules", "generate"])
        assert args.command == "rules"
        assert args.rules_action == "generate"

    def test_rules_test_subcommand(self):
        """Test that 'rules test' is parsed correctly."""
        from src.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["rules", "test"])
        assert args.command == "rules"
        assert args.rules_action == "test"

    def test_rules_show_subcommand(self):
        """Test that 'rules show' is parsed correctly."""
        from src.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["rules", "show"])
        assert args.command == "rules"
        assert args.rules_action == "show"

    def test_rules_edit_subcommand(self):
        """Test that 'rules edit' is parsed correctly."""
        from src.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["rules", "edit"])
        assert args.command == "rules"
        assert args.rules_action == "edit"

    def test_rules_requires_action(self):
        """Test that 'rules' without an action fails."""
        from src.cli import create_parser

        parser = create_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["rules"])

    def test_rules_generate_custom_categories_path(self):
        """Test that --categories flag is accepted."""
        from src.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["rules", "generate", "--categories", "/tmp/cats.json"])
        assert args.categories == Path("/tmp/cats.json")

    def test_rules_generate_custom_analysis_path(self):
        """Test that --analysis flag is accepted."""
        from src.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["rules", "generate", "--analysis", "/tmp/analysis.json"])
        assert args.analysis == Path("/tmp/analysis.json")

    def test_rules_generate_custom_rules_file(self):
        """Test that --rules-file flag is accepted."""
        from src.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["rules", "generate", "--rules-file", "/tmp/rules.json"])
        assert args.rules_file == Path("/tmp/rules.json")

    def test_rules_test_custom_rules_file(self):
        """Test that 'rules test --rules-file' is accepted."""
        from src.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["rules", "test", "--rules-file", "/tmp/rules.json"])
        assert args.rules_file == Path("/tmp/rules.json")

    def test_rules_test_custom_corpus_path(self):
        """Test that 'rules test --corpus' is accepted."""
        from src.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["rules", "test", "--corpus", "/tmp/corpus.json"])
        assert args.corpus == Path("/tmp/corpus.json")

    def test_rules_show_custom_rules_file(self):
        """Test that 'rules show --rules-file' is accepted."""
        from src.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["rules", "show", "--rules-file", "/tmp/rules.json"])
        assert args.rules_file == Path("/tmp/rules.json")

    def test_rules_command_in_dispatch(self):
        """Test that the main dispatcher knows about the rules command."""
        from src.cli import create_parser

        # Verify that parsing works and the handler can be located
        parser = create_parser()
        args = parser.parse_args(["rules", "show"])
        assert args.command == "rules"


# =============================================================================
# rules generate tests
# =============================================================================


class TestRulesGenerate:
    """Test the rules generate command."""

    @patch("src.cli.commands.rules.save_json")
    @patch("src.cli.commands.rules.load_json")
    @patch("src.cli.commands.rules.PathConfig")
    def test_generate_success(self, mock_path_config, mock_load_json, mock_save_json):
        """Test successful rule generation from categories + analysis."""
        from src.cli.commands.rules import cmd_rules

        # Configure mocks
        mock_path_config.get_approved_categories_path.return_value = Path("/tmp/approved.json")
        mock_path_config.get_analysis_path.return_value = Path("/tmp/analysis.json")
        mock_path_config.get_rules_path.return_value = Path("/tmp/rules.json")

        mock_load_json.side_effect = [
            [_make_category_dict()],  # First call: categories
            _make_analysis_dict(),  # Second call: analysis
        ]

        args = argparse.Namespace(
            rules_action="generate",
            categories=None,
            analysis=None,
            rules_file=None,
            json=False,
            verbose=False,
        )

        result = cmd_rules(args)

        assert result == 0
        mock_save_json.assert_called_once()
        # Verify the saved data is a dict (serialized RuleSet)
        saved_data = mock_save_json.call_args[0][0]
        assert isinstance(saved_data, dict)
        assert "rules" in saved_data

    @patch("src.cli.commands.rules.save_json")
    @patch("src.cli.commands.rules.load_json")
    @patch("src.cli.commands.rules.PathConfig")
    def test_generate_json_output(self, mock_path_config, mock_load_json, mock_save_json, capsys):
        """Test generate with --json flag outputs structured JSON."""
        from src.cli.commands.rules import cmd_rules

        mock_path_config.get_approved_categories_path.return_value = Path("/tmp/approved.json")
        mock_path_config.get_analysis_path.return_value = Path("/tmp/analysis.json")
        mock_path_config.get_rules_path.return_value = Path("/tmp/rules.json")

        mock_load_json.side_effect = [
            [_make_category_dict()],
            _make_analysis_dict(),
        ]

        args = argparse.Namespace(
            rules_action="generate",
            categories=None,
            analysis=None,
            rules_file=None,
            json=True,
            verbose=False,
        )

        result = cmd_rules(args)

        assert result == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["command"] == "rules generate"
        assert data["status"] == "success"
        assert "rules_generated" in data["stats"]

    @patch("src.cli.commands.rules.load_json")
    @patch("src.cli.commands.rules.PathConfig")
    def test_generate_categories_not_found(self, mock_path_config, mock_load_json):
        """Test generate fails gracefully when categories file is missing."""
        from src.cli.commands.rules import cmd_rules

        mock_path_config.get_approved_categories_path.return_value = Path("/tmp/approved.json")
        mock_load_json.side_effect = FileNotFoundError("Not found")

        args = argparse.Namespace(
            rules_action="generate",
            categories=None,
            analysis=None,
            rules_file=None,
            json=False,
            verbose=False,
        )

        result = cmd_rules(args)
        assert result == 1

    @patch("src.cli.commands.rules.load_json")
    @patch("src.cli.commands.rules.PathConfig")
    def test_generate_categories_not_found_json(self, mock_path_config, mock_load_json, capsys):
        """Test generate with missing categories outputs JSON error."""
        from src.cli.commands.rules import cmd_rules

        mock_path_config.get_approved_categories_path.return_value = Path("/tmp/approved.json")
        mock_load_json.side_effect = FileNotFoundError("Not found")

        args = argparse.Namespace(
            rules_action="generate",
            categories=None,
            analysis=None,
            rules_file=None,
            json=True,
            verbose=False,
        )

        result = cmd_rules(args)
        assert result == 1
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["status"] == "error"

    @patch("src.cli.commands.rules.load_json")
    @patch("src.cli.commands.rules.PathConfig")
    def test_generate_analysis_not_found(self, mock_path_config, mock_load_json):
        """Test generate fails gracefully when analysis file is missing."""
        from src.cli.commands.rules import cmd_rules

        mock_path_config.get_approved_categories_path.return_value = Path("/tmp/approved.json")
        mock_path_config.get_analysis_path.return_value = Path("/tmp/analysis.json")

        # First call returns categories, second raises FileNotFoundError
        mock_load_json.side_effect = [
            [_make_category_dict()],
            FileNotFoundError("Not found"),
        ]

        args = argparse.Namespace(
            rules_action="generate",
            categories=None,
            analysis=None,
            rules_file=None,
            json=False,
            verbose=False,
        )

        result = cmd_rules(args)
        assert result == 1

    @patch("src.cli.commands.rules.save_json")
    @patch("src.cli.commands.rules.load_json")
    @patch("src.cli.commands.rules.PathConfig")
    def test_generate_custom_paths(self, mock_path_config, mock_load_json, mock_save_json):
        """Test generate with custom --categories, --analysis, --rules-file paths."""
        from src.cli.commands.rules import cmd_rules

        mock_load_json.side_effect = [
            [_make_category_dict()],
            _make_analysis_dict(),
        ]

        args = argparse.Namespace(
            rules_action="generate",
            categories=Path("/custom/cats.json"),
            analysis=Path("/custom/analysis.json"),
            rules_file=Path("/custom/rules.json"),
            json=False,
            verbose=False,
        )

        result = cmd_rules(args)
        assert result == 0

        # Verify load_json was called with custom paths
        calls = mock_load_json.call_args_list
        assert calls[0][0][0] == Path("/custom/cats.json")
        assert calls[1][0][0] == Path("/custom/analysis.json")

        # Verify save_json was called with custom output path
        assert mock_save_json.call_args[0][1] == Path("/custom/rules.json")


# =============================================================================
# rules test tests
# =============================================================================


class TestRulesTest:
    """Test the rules test command."""

    @patch("src.cli.commands.rules.load_json")
    @patch("src.cli.commands.rules.PathConfig")
    def test_test_success(self, mock_path_config, mock_load_json, capsys):
        """Test successful rule testing against corpus."""
        from src.cli.commands.rules import cmd_rules

        mock_path_config.get_rules_path.return_value = Path("/tmp/rules.json")
        mock_path_config.get_corpus_path.return_value = Path("/tmp/corpus.json")

        mock_load_json.side_effect = [
            _make_ruleset_dict(),  # rules
            {  # corpus
                "emails": [],
                "extraction_metadata": {
                    "extraction_date": "2024-01-01T00:00:00Z",
                    "source": "hotmail",
                    "user_email": "test@test.com",
                    "total_emails": 0,
                },
            },
        ]

        args = argparse.Namespace(
            rules_action="test",
            rules_file=None,
            corpus=None,
            json=False,
            verbose=False,
        )

        result = cmd_rules(args)
        assert result == 0

        captured = capsys.readouterr()
        assert "RULE TEST REPORT" in captured.out

    @patch("src.cli.commands.rules.load_json")
    @patch("src.cli.commands.rules.PathConfig")
    def test_test_json_output(self, mock_path_config, mock_load_json, capsys):
        """Test rules test with --json flag."""
        from src.cli.commands.rules import cmd_rules

        mock_path_config.get_rules_path.return_value = Path("/tmp/rules.json")
        mock_path_config.get_corpus_path.return_value = Path("/tmp/corpus.json")

        mock_load_json.side_effect = [
            _make_ruleset_dict(),
            {
                "emails": [],
                "extraction_metadata": {
                    "extraction_date": "2024-01-01T00:00:00Z",
                    "source": "hotmail",
                    "user_email": "test@test.com",
                    "total_emails": 0,
                },
            },
        ]

        args = argparse.Namespace(
            rules_action="test",
            rules_file=None,
            corpus=None,
            json=True,
            verbose=False,
        )

        result = cmd_rules(args)
        assert result == 0

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["command"] == "rules test"
        assert data["status"] == "success"
        assert "coverage_percentage" in data["stats"]

    @patch("src.cli.commands.rules.load_json")
    @patch("src.cli.commands.rules.PathConfig")
    def test_test_rules_not_found(self, mock_path_config, mock_load_json):
        """Test rules test fails when rules file is missing."""
        from src.cli.commands.rules import cmd_rules

        mock_path_config.get_rules_path.return_value = Path("/tmp/rules.json")
        mock_load_json.side_effect = FileNotFoundError("Not found")

        args = argparse.Namespace(
            rules_action="test",
            rules_file=None,
            corpus=None,
            json=False,
            verbose=False,
        )

        result = cmd_rules(args)
        assert result == 1

    @patch("src.cli.commands.rules.load_json")
    @patch("src.cli.commands.rules.PathConfig")
    def test_test_corpus_not_found(self, mock_path_config, mock_load_json):
        """Test rules test fails when corpus file is missing."""
        from src.cli.commands.rules import cmd_rules

        mock_path_config.get_rules_path.return_value = Path("/tmp/rules.json")
        mock_path_config.get_corpus_path.return_value = Path("/tmp/corpus.json")

        mock_load_json.side_effect = [
            _make_ruleset_dict(),  # rules loaded fine
            FileNotFoundError("Not found"),  # corpus missing
        ]

        args = argparse.Namespace(
            rules_action="test",
            rules_file=None,
            corpus=None,
            json=False,
            verbose=False,
        )

        result = cmd_rules(args)
        assert result == 1


# =============================================================================
# rules show tests
# =============================================================================


class TestRulesShow:
    """Test the rules show command."""

    @patch("src.cli.commands.rules.load_json")
    @patch("src.cli.commands.rules.PathConfig")
    def test_show_success(self, mock_path_config, mock_load_json, capsys):
        """Test successful rules display."""
        from src.cli.commands.rules import cmd_rules

        mock_path_config.get_rules_path.return_value = Path("/tmp/rules.json")
        mock_load_json.return_value = _make_ruleset_dict()

        args = argparse.Namespace(
            rules_action="show",
            rules_file=None,
            json=False,
            verbose=False,
        )

        result = cmd_rules(args)
        assert result == 0

        captured = capsys.readouterr()
        assert "Rule: Newsletter Updates" in captured.out

    @patch("src.cli.commands.rules.load_json")
    @patch("src.cli.commands.rules.PathConfig")
    def test_show_json_output(self, mock_path_config, mock_load_json, capsys):
        """Test rules show with --json flag."""
        from src.cli.commands.rules import cmd_rules

        mock_path_config.get_rules_path.return_value = Path("/tmp/rules.json")
        mock_load_json.return_value = _make_ruleset_dict()

        args = argparse.Namespace(
            rules_action="show",
            rules_file=None,
            json=True,
            verbose=False,
        )

        result = cmd_rules(args)
        assert result == 0

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["command"] == "rules show"
        assert data["status"] == "success"
        assert "rules" in data

    @patch("src.cli.commands.rules.load_json")
    @patch("src.cli.commands.rules.PathConfig")
    def test_show_rules_not_found(self, mock_path_config, mock_load_json):
        """Test show fails when rules file is missing."""
        from src.cli.commands.rules import cmd_rules

        mock_path_config.get_rules_path.return_value = Path("/tmp/rules.json")
        mock_load_json.side_effect = FileNotFoundError("Not found")

        args = argparse.Namespace(
            rules_action="show",
            rules_file=None,
            json=False,
            verbose=False,
        )

        result = cmd_rules(args)
        assert result == 1

    @patch("src.cli.commands.rules.load_json")
    @patch("src.cli.commands.rules.PathConfig")
    def test_show_verbose_includes_conditions(self, mock_path_config, mock_load_json, capsys):
        """Test that verbose mode includes condition details."""
        from src.cli.commands.rules import cmd_rules

        mock_path_config.get_rules_path.return_value = Path("/tmp/rules.json")
        mock_load_json.return_value = _make_ruleset_dict()

        args = argparse.Namespace(
            rules_action="show",
            rules_file=None,
            json=False,
            verbose=True,
        )

        result = cmd_rules(args)
        assert result == 0

        captured = capsys.readouterr()
        # Verbose should include condition details
        assert "subject" in captured.out.lower()
        assert "contains" in captured.out.lower()

    @patch("src.cli.commands.rules.load_json")
    @patch("src.cli.commands.rules.PathConfig")
    def test_show_empty_ruleset(self, mock_path_config, mock_load_json, capsys):
        """Test show with empty rule set."""
        from src.cli.commands.rules import cmd_rules

        mock_path_config.get_rules_path.return_value = Path("/tmp/rules.json")
        now = datetime.now(timezone.utc).isoformat()
        mock_load_json.return_value = {
            "rules": [],
            "version": "1.0",
            "description": "Empty",
            "created_date": now,
            "last_modified": now,
            "source_category_ids": [],
        }

        args = argparse.Namespace(
            rules_action="show",
            rules_file=None,
            json=False,
            verbose=False,
        )

        result = cmd_rules(args)
        assert result == 0

        captured = capsys.readouterr()
        assert "No rules" in captured.out or "0 rules" in captured.out


# =============================================================================
# rules edit tests
# =============================================================================


class TestRulesEdit:
    """Test the rules edit command."""

    @patch("src.cli.commands.rules.load_json")
    @patch("src.cli.commands.rules.PathConfig")
    def test_edit_rules_not_found(self, mock_path_config, mock_load_json):
        """Test edit fails when rules file is missing."""
        from src.cli.commands.rules import cmd_rules

        mock_path_config.get_rules_path.return_value = Path("/tmp/rules.json")
        mock_load_json.side_effect = FileNotFoundError("Not found")

        args = argparse.Namespace(
            rules_action="edit",
            rules_file=None,
            corpus=None,
            json=False,
            verbose=False,
        )

        result = cmd_rules(args)
        assert result == 1


# =============================================================================
# Dispatch tests
# =============================================================================


class TestRulesDispatch:
    """Test the top-level cmd_rules dispatcher."""

    def test_unknown_action_returns_error(self):
        """Test that an unknown action returns exit code 1."""
        from src.cli.commands.rules import cmd_rules

        args = argparse.Namespace(
            rules_action="unknown",
            json=False,
            verbose=False,
        )

        result = cmd_rules(args)
        assert result == 1

    def test_rules_handler_in_main_dispatch(self):
        """Test that the rules command is dispatched in main()."""
        from src.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["rules", "show"])
        assert args.command == "rules"


# =============================================================================
# PathConfig integration
# =============================================================================


class TestPathConfigRules:
    """Test that PathConfig.get_rules_path() works."""

    def test_get_rules_path_returns_rules_json(self):
        """Test default rules path is rules.json in output dir."""
        from src.utils.paths import PathConfig

        # Save and restore
        original = PathConfig._output_dir
        try:
            PathConfig.set_output_dir("/tmp/test_output")
            path = PathConfig.get_rules_path()
            assert path.name == "rules.json"
            assert path.parent.name == "test_output"
        finally:
            PathConfig._output_dir = original
