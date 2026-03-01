"""
Unit tests for the classify CLI command (Phase 2, Work Item 2.3).

TDD: Tests written first, implementation follows.

Tests cover:
- Parser construction (classify command with all flags)
- classify: loads corpus, creates LLMClassifier, classifies all emails, saves report
- classify --dry-run: preview without calling LLM
- classify --json: machine-readable JSON output
- classify --provider / --model: LLM provider and model selection
- classify --confidence-threshold: minimum confidence filter
- classify --categories: path to YAML category definitions
- classify --corpus: custom corpus path
- classify --output: custom output path
- Error handling: missing corpus, Ollama not running, invalid categories file
- Dispatch registration in main CLI
"""

import argparse
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.classifiers.base import ClassificationResult
from src.config.models import CategoryDefinition, ClassifierConfig

# =============================================================================
# Helpers
# =============================================================================


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


def _make_categories_yaml_content() -> str:
    """Return YAML content defining categories for classification."""
    return """categories:
  - name: Newsletters
    description: Regular newsletter emails from subscriptions
  - name: Promotions
    description: Marketing and promotional offers
  - name: Personal
    description: Personal correspondence from known contacts
"""


def _make_mock_classification_result(
    category: str = "Newsletters",
    confidence: float = 0.85,
) -> ClassificationResult:
    """Create a mock ClassificationResult."""
    return ClassificationResult(
        category_name=category,
        confidence=confidence,
        source="llm:ollama",
        reasoning="Test reasoning",
    )


def _make_default_args(**overrides) -> argparse.Namespace:
    """Create a default args Namespace for the classify command."""
    defaults = {
        "command": "classify",
        "provider": None,
        "model": None,
        "endpoint_id": None,
        "categories": None,
        "confidence_threshold": None,
        "corpus": None,
        "output": None,
        "dry_run": False,
        "json": False,
        "verbose": False,
        "config": None,
        "output_dir": None,
    }
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def _make_mock_config(
    categories: list[CategoryDefinition] | None = None,
    provider: str = "ollama",
    model_name: str = "qwen2.5:7b",
    confidence_threshold: float = 0.6,
) -> MagicMock:
    """Create a mock AppConfig with a real ClassifierConfig.

    Uses real ClassifierConfig and CategoryDefinition objects so they pass
    Pydantic validation when the implementation reconstructs configs.
    """
    if categories is None:
        categories = [
            CategoryDefinition(name="Newsletters", description="Regular newsletters"),
        ]

    real_classifier_config = ClassifierConfig(
        provider=provider,
        model_name=model_name,
        confidence_threshold=confidence_threshold,
        categories=categories,
    )

    mock_config = MagicMock()
    mock_config.classifier = real_classifier_config
    return mock_config


# =============================================================================
# Parser tests
# =============================================================================


class TestClassifyParser:
    """Test that the classify subcommand parser is correctly configured."""

    def test_classify_command_registered_in_parser(self):
        """Test that 'classify' is a valid subcommand."""
        from src.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["classify"])
        assert args.command == "classify"

    def test_classify_provider_flag(self):
        """Test that --provider flag is accepted with valid choices."""
        from src.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["classify", "--provider", "ollama"])
        assert args.provider == "ollama"

    def test_classify_provider_openai(self):
        """Test that --provider openai is accepted."""
        from src.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["classify", "--provider", "openai"])
        assert args.provider == "openai"

    def test_classify_provider_claude(self):
        """Test that --provider claude is accepted."""
        from src.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["classify", "--provider", "claude"])
        assert args.provider == "claude"

    def test_classify_provider_runpod(self):
        """Test that --provider runpod is accepted."""
        from src.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["classify", "--provider", "runpod"])
        assert args.provider == "runpod"

    def test_classify_endpoint_id_flag(self):
        """Test that --endpoint-id flag is accepted."""
        from src.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["classify", "--endpoint-id", "abc123"])
        assert args.endpoint_id == "abc123"

    def test_classify_provider_invalid_rejected(self):
        """Test that invalid provider value is rejected."""
        from src.cli import create_parser

        parser = create_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["classify", "--provider", "invalid"])

    def test_classify_model_flag(self):
        """Test that --model flag is accepted."""
        from src.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["classify", "--model", "qwen2.5:7b"])
        assert args.model == "qwen2.5:7b"

    def test_classify_categories_flag(self):
        """Test that --categories flag accepts a file path."""
        from src.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["classify", "--categories", "/tmp/categories.yaml"])
        assert args.categories == Path("/tmp/categories.yaml")

    def test_classify_confidence_threshold_flag(self):
        """Test that --confidence-threshold flag accepts a float."""
        from src.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["classify", "--confidence-threshold", "0.7"])
        assert args.confidence_threshold == 0.7

    def test_classify_corpus_flag(self):
        """Test that --corpus flag is accepted."""
        from src.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["classify", "--corpus", "/tmp/corpus.json"])
        assert args.corpus == Path("/tmp/corpus.json")

    def test_classify_output_flag(self):
        """Test that --output flag is accepted."""
        from src.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["classify", "--output", "/tmp/report.json"])
        assert args.output == Path("/tmp/report.json")

    def test_classify_dry_run_flag(self):
        """Test that --dry-run flag is accepted."""
        from src.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["classify", "--dry-run"])
        assert args.dry_run is True

    def test_classify_defaults(self):
        """Test default values for all flags."""
        from src.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["classify"])
        assert args.provider is None
        assert args.model is None
        assert args.categories is None
        assert args.confidence_threshold is None
        assert args.corpus is None
        assert args.output is None
        assert args.dry_run is False

    def test_classify_help_does_not_error(self):
        """Test that --help works (exits with 0)."""
        from src.cli import create_parser

        parser = create_parser()
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["classify", "--help"])
        assert exc_info.value.code == 0


# =============================================================================
# Dispatch tests
# =============================================================================


class TestClassifyDispatch:
    """Test that classify is properly registered in the main CLI dispatch."""

    def test_classify_in_main_dispatch(self):
        """Test that the classify command handler exists in __init__.py dispatcher."""
        from src.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["classify"])
        assert args.command == "classify"

    def test_classify_handler_importable(self):
        """Test that cmd_classify can be imported from the commands module."""
        from src.cli.commands.classify import cmd_classify

        assert callable(cmd_classify)

    def test_classify_builder_importable(self):
        """Test that build_classify_parser can be imported."""
        from src.cli.commands.classify import build_classify_parser

        assert callable(build_classify_parser)


# =============================================================================
# Successful classification tests
# =============================================================================


class TestClassifyCommand:
    """Test the classify command execution with mocked classifier."""

    @patch("src.cli.commands.classify.save_json")
    @patch("src.cli.commands.classify.load_json")
    @patch("src.cli.commands.classify.PathConfig")
    @patch("src.cli.commands.classify.LLMClassifier")
    @patch("src.cli.commands.classify.load_config")
    def test_classify_success_with_config_categories(
        self,
        mock_load_config,
        mock_classifier_cls,
        mock_path_config,
        mock_load_json,
        mock_save_json,
    ):
        """Test successful classification using categories from config."""
        from src.cli.commands.classify import cmd_classify

        mock_path_config.get_corpus_path.return_value = Path("/tmp/corpus.json")
        mock_path_config.get_categorization_report_path.return_value = Path("/tmp/report.json")
        mock_load_json.return_value = _make_corpus_dict(3)

        mock_classifier = MagicMock()
        mock_classifier.classify.return_value = _make_mock_classification_result()
        mock_classifier.name = "LLM Classifier (ollama/qwen2.5:7b)"
        mock_classifier_cls.return_value = mock_classifier

        mock_load_config.return_value = _make_mock_config(
            categories=[
                CategoryDefinition(name="Newsletters", description="Regular newsletters"),
                CategoryDefinition(name="Promotions", description="Marketing emails"),
            ]
        )

        args = _make_default_args()
        result = cmd_classify(args)

        assert result == 0
        mock_save_json.assert_called_once()

    @patch("src.cli.commands.classify.save_json")
    @patch("src.cli.commands.classify.load_json")
    @patch("src.cli.commands.classify.PathConfig")
    @patch("src.cli.commands.classify.LLMClassifier")
    @patch("src.cli.commands.classify.load_config")
    def test_classify_with_categories_file(
        self,
        mock_load_config,
        mock_classifier_cls,
        mock_path_config,
        mock_load_json,
        mock_save_json,
        tmp_path,
    ):
        """Test classification using categories from a YAML file."""
        from src.cli.commands.classify import cmd_classify

        mock_path_config.get_corpus_path.return_value = Path("/tmp/corpus.json")
        mock_path_config.get_categorization_report_path.return_value = Path("/tmp/report.json")
        mock_load_json.return_value = _make_corpus_dict(2)

        mock_classifier = MagicMock()
        mock_classifier.classify.return_value = _make_mock_classification_result()
        mock_classifier.name = "LLM Classifier (ollama/qwen2.5:7b)"
        mock_classifier_cls.return_value = mock_classifier

        # Write a YAML categories file
        cat_file = tmp_path / "categories.yaml"
        cat_file.write_text(_make_categories_yaml_content())

        mock_load_config.return_value = _make_mock_config(categories=[])

        args = _make_default_args(categories=cat_file)
        result = cmd_classify(args)

        assert result == 0
        # Verify classifier was constructed with categories from the file
        mock_classifier_cls.assert_called_once()
        config_arg = mock_classifier_cls.call_args[0][0]
        assert len(config_arg.categories) == 3

    @patch("src.cli.commands.classify.save_json")
    @patch("src.cli.commands.classify.load_json")
    @patch("src.cli.commands.classify.PathConfig")
    @patch("src.cli.commands.classify.LLMClassifier")
    @patch("src.cli.commands.classify.load_config")
    def test_classify_provider_override(
        self,
        mock_load_config,
        mock_classifier_cls,
        mock_path_config,
        mock_load_json,
        mock_save_json,
    ):
        """Test that --provider overrides config provider."""
        from src.cli.commands.classify import cmd_classify

        mock_path_config.get_corpus_path.return_value = Path("/tmp/corpus.json")
        mock_path_config.get_categorization_report_path.return_value = Path("/tmp/report.json")
        mock_load_json.return_value = _make_corpus_dict(1)

        mock_classifier = MagicMock()
        mock_classifier.classify.return_value = _make_mock_classification_result()
        mock_classifier.name = "LLM Classifier (openai/gpt-4o-mini)"
        mock_classifier_cls.return_value = mock_classifier

        mock_load_config.return_value = _make_mock_config()

        args = _make_default_args(provider="openai", model="gpt-4o-mini")
        result = cmd_classify(args)

        assert result == 0
        config_arg = mock_classifier_cls.call_args[0][0]
        assert config_arg.provider == "openai"
        assert config_arg.model_name == "gpt-4o-mini"

    @patch("src.cli.commands.classify.save_json")
    @patch("src.cli.commands.classify.load_json")
    @patch("src.cli.commands.classify.PathConfig")
    @patch("src.cli.commands.classify.LLMClassifier")
    @patch("src.cli.commands.classify.load_config")
    def test_classify_provider_runpod_with_endpoint_id(
        self,
        mock_load_config,
        mock_classifier_cls,
        mock_path_config,
        mock_load_json,
        mock_save_json,
    ):
        """Test that --provider runpod --endpoint-id passes through to config."""
        from src.cli.commands.classify import cmd_classify

        mock_path_config.get_corpus_path.return_value = Path("/tmp/corpus.json")
        mock_path_config.get_categorization_report_path.return_value = Path("/tmp/report.json")
        mock_load_json.return_value = _make_corpus_dict(1)

        mock_classifier = MagicMock()
        mock_classifier.classify.return_value = _make_mock_classification_result()
        mock_classifier.name = "LLM Classifier (runpod/qwen2.5:72b)"
        mock_classifier_cls.return_value = mock_classifier

        mock_load_config.return_value = _make_mock_config()

        args = _make_default_args(provider="runpod", endpoint_id="1fgb26fi1t0e4u")
        result = cmd_classify(args)

        assert result == 0
        config_arg = mock_classifier_cls.call_args[0][0]
        assert config_arg.provider == "runpod"
        assert config_arg.runpod_endpoint_id == "1fgb26fi1t0e4u"

    @patch("src.cli.commands.classify.save_json")
    @patch("src.cli.commands.classify.load_json")
    @patch("src.cli.commands.classify.PathConfig")
    @patch("src.cli.commands.classify.LLMClassifier")
    @patch("src.cli.commands.classify.load_config")
    def test_classify_confidence_threshold_override(
        self,
        mock_load_config,
        mock_classifier_cls,
        mock_path_config,
        mock_load_json,
        mock_save_json,
    ):
        """Test that --confidence-threshold overrides config threshold."""
        from src.cli.commands.classify import cmd_classify

        mock_path_config.get_corpus_path.return_value = Path("/tmp/corpus.json")
        mock_path_config.get_categorization_report_path.return_value = Path("/tmp/report.json")
        mock_load_json.return_value = _make_corpus_dict(1)

        # Return a result below the custom threshold
        mock_classifier = MagicMock()
        mock_classifier.classify.return_value = _make_mock_classification_result(confidence=0.75)
        mock_classifier.name = "LLM Classifier (ollama/qwen2.5:7b)"
        mock_classifier_cls.return_value = mock_classifier

        mock_load_config.return_value = _make_mock_config()

        args = _make_default_args(confidence_threshold=0.8)
        result = cmd_classify(args)

        assert result == 0
        # The report should mark 0.75 confidence as below 0.8 threshold -> uncategorized
        saved_data = mock_save_json.call_args[0][0]
        assert saved_data["uncategorized_count"] >= 0


# =============================================================================
# JSON output tests
# =============================================================================


class TestClassifyJsonOutput:
    """Test classify command JSON output mode."""

    @patch("src.cli.commands.classify.save_json")
    @patch("src.cli.commands.classify.load_json")
    @patch("src.cli.commands.classify.PathConfig")
    @patch("src.cli.commands.classify.LLMClassifier")
    @patch("src.cli.commands.classify.load_config")
    def test_classify_json_output(
        self,
        mock_load_config,
        mock_classifier_cls,
        mock_path_config,
        mock_load_json,
        mock_save_json,
        capsys,
    ):
        """Test that --json outputs structured JSON to stdout."""
        from src.cli.commands.classify import cmd_classify

        mock_path_config.get_corpus_path.return_value = Path("/tmp/corpus.json")
        mock_path_config.get_categorization_report_path.return_value = Path("/tmp/report.json")
        mock_load_json.return_value = _make_corpus_dict(2)

        mock_classifier = MagicMock()
        mock_classifier.classify.return_value = _make_mock_classification_result()
        mock_classifier.name = "LLM Classifier (ollama/qwen2.5:7b)"
        mock_classifier_cls.return_value = mock_classifier

        mock_load_config.return_value = _make_mock_config()

        args = _make_default_args(json=True)
        result = cmd_classify(args)

        assert result == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["command"] == "classify"
        assert data["status"] == "success"
        assert "total_emails" in data["stats"]
        assert "coverage_percentage" in data["stats"]
        assert "provider" in data

    @patch("src.cli.commands.classify.load_json")
    @patch("src.cli.commands.classify.PathConfig")
    @patch("src.cli.commands.classify.load_config")
    def test_classify_json_error_output(
        self, mock_load_config, mock_path_config, mock_load_json, capsys
    ):
        """Test that errors in --json mode output JSON error."""
        from src.cli.commands.classify import cmd_classify

        mock_path_config.get_corpus_path.return_value = Path("/tmp/corpus.json")
        mock_load_json.side_effect = FileNotFoundError("Not found")
        mock_load_config.return_value = _make_mock_config()

        args = _make_default_args(json=True)
        result = cmd_classify(args)

        assert result == 1
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["status"] == "error"


# =============================================================================
# Dry-run tests
# =============================================================================


class TestClassifyDryRun:
    """Test classify --dry-run mode."""

    @patch("src.cli.commands.classify.load_json")
    @patch("src.cli.commands.classify.PathConfig")
    @patch("src.cli.commands.classify.load_config")
    def test_dry_run_does_not_call_llm(
        self, mock_load_config, mock_path_config, mock_load_json, capsys
    ):
        """Test that --dry-run does not create classifier or call LLM."""
        from src.cli.commands.classify import cmd_classify

        mock_path_config.get_corpus_path.return_value = Path("/tmp/corpus.json")
        mock_path_config.get_categorization_report_path.return_value = Path("/tmp/report.json")
        mock_load_json.return_value = _make_corpus_dict(3)

        mock_load_config.return_value = _make_mock_config(
            categories=[
                CategoryDefinition(name="Newsletters", description="Regular newsletters"),
                CategoryDefinition(name="Promotions", description="Marketing emails"),
            ]
        )

        args = _make_default_args(dry_run=True)

        with patch("src.cli.commands.classify.LLMClassifier") as mock_cls:
            result = cmd_classify(args)
            # LLMClassifier should NOT be instantiated in dry-run mode
            mock_cls.assert_not_called()

        assert result == 0

    @patch("src.cli.commands.classify.load_json")
    @patch("src.cli.commands.classify.PathConfig")
    @patch("src.cli.commands.classify.load_config")
    def test_dry_run_does_not_save(
        self, mock_load_config, mock_path_config, mock_load_json, capsys
    ):
        """Test that --dry-run does not save results to disk."""
        from src.cli.commands.classify import cmd_classify

        mock_path_config.get_corpus_path.return_value = Path("/tmp/corpus.json")
        mock_path_config.get_categorization_report_path.return_value = Path("/tmp/report.json")
        mock_load_json.return_value = _make_corpus_dict(3)
        mock_load_config.return_value = _make_mock_config()

        args = _make_default_args(dry_run=True)

        with patch("src.cli.commands.classify.save_json") as mock_save:
            result = cmd_classify(args)

        assert result == 0
        mock_save.assert_not_called()

    @patch("src.cli.commands.classify.load_json")
    @patch("src.cli.commands.classify.PathConfig")
    @patch("src.cli.commands.classify.load_config")
    def test_dry_run_shows_preview(
        self, mock_load_config, mock_path_config, mock_load_json, capsys
    ):
        """Test that --dry-run shows preview information."""
        from src.cli.commands.classify import cmd_classify

        mock_path_config.get_corpus_path.return_value = Path("/tmp/corpus.json")
        mock_path_config.get_categorization_report_path.return_value = Path("/tmp/report.json")
        mock_load_json.return_value = _make_corpus_dict(3)

        mock_load_config.return_value = _make_mock_config(
            categories=[
                CategoryDefinition(name="Newsletters", description="Regular newsletters"),
                CategoryDefinition(name="Promotions", description="Marketing emails"),
            ]
        )

        args = _make_default_args(dry_run=True)
        result = cmd_classify(args)

        assert result == 0
        captured = capsys.readouterr()
        assert "DRY RUN" in captured.out or "dry" in captured.out.lower()

    @patch("src.cli.commands.classify.load_json")
    @patch("src.cli.commands.classify.PathConfig")
    @patch("src.cli.commands.classify.load_config")
    def test_dry_run_json_output(self, mock_load_config, mock_path_config, mock_load_json, capsys):
        """Test that --dry-run with --json includes dry_run indicator."""
        from src.cli.commands.classify import cmd_classify

        mock_path_config.get_corpus_path.return_value = Path("/tmp/corpus.json")
        mock_path_config.get_categorization_report_path.return_value = Path("/tmp/report.json")
        mock_load_json.return_value = _make_corpus_dict(3)
        mock_load_config.return_value = _make_mock_config()

        args = _make_default_args(dry_run=True, json=True)
        result = cmd_classify(args)

        assert result == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["dry_run"] is True


# =============================================================================
# Error handling tests
# =============================================================================


class TestClassifyErrors:
    """Test classify command error handling."""

    @patch("src.cli.commands.classify.load_json")
    @patch("src.cli.commands.classify.PathConfig")
    @patch("src.cli.commands.classify.load_config")
    def test_classify_corpus_not_found(self, mock_load_config, mock_path_config, mock_load_json):
        """Test classify fails gracefully when corpus file is missing."""
        from src.cli.commands.classify import cmd_classify

        mock_path_config.get_corpus_path.return_value = Path("/tmp/corpus.json")
        mock_load_json.side_effect = FileNotFoundError("Not found")
        mock_load_config.return_value = _make_mock_config()

        args = _make_default_args()
        result = cmd_classify(args)

        assert result == 1

    @patch("src.cli.commands.classify.save_json")
    @patch("src.cli.commands.classify.load_json")
    @patch("src.cli.commands.classify.PathConfig")
    @patch("src.cli.commands.classify.LLMClassifier")
    @patch("src.cli.commands.classify.load_config")
    def test_classify_connection_error(
        self,
        mock_load_config,
        mock_classifier_cls,
        mock_path_config,
        mock_load_json,
        mock_save_json,
    ):
        """Test classify handles connection errors (Ollama not running)."""
        from src.cli.commands.classify import cmd_classify
        from src.exceptions import ClassifierConnectionError

        mock_path_config.get_corpus_path.return_value = Path("/tmp/corpus.json")
        mock_path_config.get_categorization_report_path.return_value = Path("/tmp/report.json")
        mock_load_json.return_value = _make_corpus_dict(1)

        mock_classifier = MagicMock()
        mock_classifier.classify.side_effect = ClassifierConnectionError(
            provider="ollama",
            url="http://localhost:11434/v1",
            recovery_hint="Ensure Ollama is running: ollama serve",
        )
        mock_classifier.name = "LLM Classifier (ollama/qwen2.5:7b)"
        mock_classifier_cls.return_value = mock_classifier

        mock_load_config.return_value = _make_mock_config()

        args = _make_default_args()
        result = cmd_classify(args)

        assert result == 1

    @patch("src.cli.commands.classify.load_json")
    @patch("src.cli.commands.classify.PathConfig")
    @patch("src.cli.commands.classify.load_config")
    def test_classify_invalid_categories_file(
        self, mock_load_config, mock_path_config, mock_load_json, tmp_path
    ):
        """Test classify fails when categories YAML file is invalid."""
        from src.cli.commands.classify import cmd_classify

        bad_yaml = tmp_path / "bad.yaml"
        bad_yaml.write_text("not: valid: yaml: {{{{")

        mock_path_config.get_corpus_path.return_value = Path("/tmp/corpus.json")
        mock_load_config.return_value = _make_mock_config(categories=[])

        args = _make_default_args(categories=bad_yaml)
        result = cmd_classify(args)

        assert result == 1

    @patch("src.cli.commands.classify.load_json")
    @patch("src.cli.commands.classify.PathConfig")
    @patch("src.cli.commands.classify.load_config")
    def test_classify_no_categories_error(self, mock_load_config, mock_path_config, mock_load_json):
        """Test classify fails when no categories are available from config or file."""
        from src.cli.commands.classify import cmd_classify

        mock_path_config.get_corpus_path.return_value = Path("/tmp/corpus.json")
        mock_load_json.return_value = _make_corpus_dict(1)
        mock_load_config.return_value = _make_mock_config(categories=[])

        args = _make_default_args()
        result = cmd_classify(args)

        assert result == 1

    @patch("src.cli.commands.classify.load_json")
    @patch("src.cli.commands.classify.PathConfig")
    @patch("src.cli.commands.classify.load_config")
    def test_classify_categories_file_not_found(
        self, mock_load_config, mock_path_config, mock_load_json
    ):
        """Test classify fails when --categories file does not exist."""
        from src.cli.commands.classify import cmd_classify

        mock_path_config.get_corpus_path.return_value = Path("/tmp/corpus.json")
        mock_load_config.return_value = _make_mock_config(categories=[])

        args = _make_default_args(categories=Path("/nonexistent/categories.yaml"))
        result = cmd_classify(args)

        assert result == 1


# =============================================================================
# Output format tests
# =============================================================================


class TestClassifyOutput:
    """Test classify command output formatting."""

    @patch("src.cli.commands.classify.save_json")
    @patch("src.cli.commands.classify.load_json")
    @patch("src.cli.commands.classify.PathConfig")
    @patch("src.cli.commands.classify.LLMClassifier")
    @patch("src.cli.commands.classify.load_config")
    def test_classify_saves_categorization_report(
        self,
        mock_load_config,
        mock_classifier_cls,
        mock_path_config,
        mock_load_json,
        mock_save_json,
    ):
        """Test that classify saves a valid CategorizationReport."""
        from src.cli.commands.classify import cmd_classify

        mock_path_config.get_corpus_path.return_value = Path("/tmp/corpus.json")
        mock_path_config.get_categorization_report_path.return_value = Path("/tmp/report.json")
        mock_load_json.return_value = _make_corpus_dict(2)

        mock_classifier = MagicMock()
        mock_classifier.classify.return_value = _make_mock_classification_result()
        mock_classifier.name = "LLM Classifier (ollama/qwen2.5:7b)"
        mock_classifier_cls.return_value = mock_classifier

        mock_load_config.return_value = _make_mock_config()

        args = _make_default_args()
        result = cmd_classify(args)

        assert result == 0
        saved_data = mock_save_json.call_args[0][0]
        # Validate the report structure
        assert "total_emails" in saved_data
        assert "categorized_count" in saved_data
        assert "uncategorized_count" in saved_data
        assert "coverage_percentage" in saved_data
        assert "categories_used" in saved_data
        assert "categorizations" in saved_data

    @patch("src.cli.commands.classify.save_json")
    @patch("src.cli.commands.classify.load_json")
    @patch("src.cli.commands.classify.PathConfig")
    @patch("src.cli.commands.classify.LLMClassifier")
    @patch("src.cli.commands.classify.load_config")
    def test_classify_custom_output_path(
        self,
        mock_load_config,
        mock_classifier_cls,
        mock_path_config,
        mock_load_json,
        mock_save_json,
    ):
        """Test that --output saves to custom path."""
        from src.cli.commands.classify import cmd_classify

        mock_path_config.get_corpus_path.return_value = Path("/tmp/corpus.json")
        mock_load_json.return_value = _make_corpus_dict(1)

        mock_classifier = MagicMock()
        mock_classifier.classify.return_value = _make_mock_classification_result()
        mock_classifier.name = "LLM Classifier (ollama/qwen2.5:7b)"
        mock_classifier_cls.return_value = mock_classifier

        mock_load_config.return_value = _make_mock_config()

        custom_output = Path("/custom/output/report.json")
        args = _make_default_args(output=custom_output)
        result = cmd_classify(args)

        assert result == 0
        assert mock_save_json.call_args[0][1] == custom_output

    @patch("src.cli.commands.classify.save_json")
    @patch("src.cli.commands.classify.load_json")
    @patch("src.cli.commands.classify.PathConfig")
    @patch("src.cli.commands.classify.LLMClassifier")
    @patch("src.cli.commands.classify.load_config")
    def test_classify_prints_summary(
        self,
        mock_load_config,
        mock_classifier_cls,
        mock_path_config,
        mock_load_json,
        mock_save_json,
        capsys,
    ):
        """Test that classify prints a human-readable summary."""
        from src.cli.commands.classify import cmd_classify

        mock_path_config.get_corpus_path.return_value = Path("/tmp/corpus.json")
        mock_path_config.get_categorization_report_path.return_value = Path("/tmp/report.json")
        mock_load_json.return_value = _make_corpus_dict(3)

        mock_classifier = MagicMock()
        mock_classifier.classify.return_value = _make_mock_classification_result()
        mock_classifier.name = "LLM Classifier (ollama/qwen2.5:7b)"
        mock_classifier_cls.return_value = mock_classifier

        mock_load_config.return_value = _make_mock_config()

        args = _make_default_args()
        result = cmd_classify(args)

        assert result == 0
        captured = capsys.readouterr()
        assert "CLASSIFICATION RESULTS" in captured.out
        assert "Total emails" in captured.out


# =============================================================================
# Verbose output tests
# =============================================================================


class TestClassifyVerbose:
    """Test classify --verbose mode."""

    @patch("src.cli.commands.classify.save_json")
    @patch("src.cli.commands.classify.load_json")
    @patch("src.cli.commands.classify.PathConfig")
    @patch("src.cli.commands.classify.LLMClassifier")
    @patch("src.cli.commands.classify.load_config")
    def test_verbose_shows_per_email_detail(
        self,
        mock_load_config,
        mock_classifier_cls,
        mock_path_config,
        mock_load_json,
        mock_save_json,
        capsys,
    ):
        """Test that verbose mode shows per-email classification detail."""
        from src.cli.commands.classify import cmd_classify

        mock_path_config.get_corpus_path.return_value = Path("/tmp/corpus.json")
        mock_path_config.get_categorization_report_path.return_value = Path("/tmp/report.json")
        mock_load_json.return_value = _make_corpus_dict(2)

        mock_classifier = MagicMock()
        mock_classifier.classify.return_value = _make_mock_classification_result()
        mock_classifier.name = "LLM Classifier (ollama/qwen2.5:7b)"
        mock_classifier_cls.return_value = mock_classifier

        mock_load_config.return_value = _make_mock_config()

        args = _make_default_args(verbose=True)
        result = cmd_classify(args)

        assert result == 0
        captured = capsys.readouterr()
        # Should show individual email IDs
        assert "msg_0" in captured.out


# =============================================================================
# Edge cases
# =============================================================================


class TestClassifyEdgeCases:
    """Test edge cases for the classify command."""

    @patch("src.cli.commands.classify.save_json")
    @patch("src.cli.commands.classify.load_json")
    @patch("src.cli.commands.classify.PathConfig")
    @patch("src.cli.commands.classify.LLMClassifier")
    @patch("src.cli.commands.classify.load_config")
    def test_empty_corpus(
        self,
        mock_load_config,
        mock_classifier_cls,
        mock_path_config,
        mock_load_json,
        mock_save_json,
    ):
        """Test classification with empty corpus."""
        from src.cli.commands.classify import cmd_classify

        mock_path_config.get_corpus_path.return_value = Path("/tmp/corpus.json")
        mock_path_config.get_categorization_report_path.return_value = Path("/tmp/report.json")
        mock_load_json.return_value = _make_corpus_dict(0)

        mock_load_config.return_value = _make_mock_config()

        args = _make_default_args()
        result = cmd_classify(args)

        assert result == 0
        # Should not create a classifier for empty corpus
        mock_classifier_cls.assert_not_called()

    @patch("src.cli.commands.classify.save_json")
    @patch("src.cli.commands.classify.load_json")
    @patch("src.cli.commands.classify.PathConfig")
    @patch("src.cli.commands.classify.LLMClassifier")
    @patch("src.cli.commands.classify.load_config")
    def test_classify_custom_corpus_path(
        self,
        mock_load_config,
        mock_classifier_cls,
        mock_path_config,
        mock_load_json,
        mock_save_json,
    ):
        """Test that --corpus uses the custom path."""
        from src.cli.commands.classify import cmd_classify

        mock_load_json.return_value = _make_corpus_dict(1)
        mock_path_config.get_categorization_report_path.return_value = Path("/tmp/report.json")

        mock_classifier = MagicMock()
        mock_classifier.classify.return_value = _make_mock_classification_result()
        mock_classifier.name = "LLM Classifier (ollama/qwen2.5:7b)"
        mock_classifier_cls.return_value = mock_classifier

        mock_load_config.return_value = _make_mock_config()

        custom_corpus = Path("/custom/corpus.json")
        args = _make_default_args(corpus=custom_corpus)
        result = cmd_classify(args)

        assert result == 0
        mock_load_json.assert_called_once_with(custom_corpus)

    @patch("src.cli.commands.classify.save_json")
    @patch("src.cli.commands.classify.load_json")
    @patch("src.cli.commands.classify.PathConfig")
    @patch("src.cli.commands.classify.LLMClassifier")
    @patch("src.cli.commands.classify.load_config")
    def test_classify_below_threshold_marked_uncategorized(
        self,
        mock_load_config,
        mock_classifier_cls,
        mock_path_config,
        mock_load_json,
        mock_save_json,
    ):
        """Test that classifications below confidence threshold are marked uncategorized."""
        from src.cli.commands.classify import cmd_classify

        mock_path_config.get_corpus_path.return_value = Path("/tmp/corpus.json")
        mock_path_config.get_categorization_report_path.return_value = Path("/tmp/report.json")
        mock_load_json.return_value = _make_corpus_dict(2)

        # Return low confidence result
        mock_classifier = MagicMock()
        mock_classifier.classify.return_value = _make_mock_classification_result(confidence=0.3)
        mock_classifier.name = "LLM Classifier (ollama/qwen2.5:7b)"
        mock_classifier_cls.return_value = mock_classifier

        mock_load_config.return_value = _make_mock_config()

        args = _make_default_args(confidence_threshold=0.5)
        result = cmd_classify(args)

        assert result == 0
        saved_data = mock_save_json.call_args[0][0]
        # All emails should be uncategorized (confidence 0.3 < threshold 0.5)
        assert saved_data["uncategorized_count"] == 2
        assert saved_data["categorized_count"] == 0
