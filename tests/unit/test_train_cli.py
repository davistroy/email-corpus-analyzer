"""
Unit tests for the train CLI command (Phase 6, Work Item 6.3).

TDD: Tests written first, implementation follows.

Tests cover:
- Parser construction (train command with all flags)
- train: loads corrections from CorrectionStore, trains SetFit model, saves model
- train --min-examples: minimum corrections per category filter
- train --model-type: setfit (only supported type currently)
- train --output: model save path
- train --dry-run: preview without training
- train --json: machine-readable JSON output
- Filtering categories with insufficient examples (with warning)
- Model saved with version metadata
- Error handling: no corrections, no database, import errors
- Dispatch registration in main CLI
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


def _make_default_args(**overrides) -> argparse.Namespace:
    """Create a default args Namespace for the train command."""
    defaults = {
        "command": "train",
        "min_examples": 8,
        "model_type": "setfit",
        "output": None,
        "dry_run": False,
        "json": False,
        "verbose": False,
        "config": None,
        "output_dir": None,
        "db_path": None,
    }
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def _make_mock_corrections(categories_with_counts: dict[str, int]) -> list:
    """Create mock Correction objects grouped by category.

    Args:
        categories_with_counts: Dict of {new_category: count}

    Returns:
        List of mock Correction objects.
    """
    from src.learning.feedback_store import Correction

    corrections = []
    idx = 1
    for cat, count in categories_with_counts.items():
        for _i in range(count):
            corrections.append(
                Correction(
                    id=idx,
                    email_id=f"email_{idx:04d}",
                    old_category="Uncategorized",
                    new_category=cat,
                    corrected_at=datetime(2026, 2, 20, 12, 0, 0, tzinfo=timezone.utc),
                )
            )
            idx += 1
    return corrections


def _make_mock_database():
    """Create a mock Database instance."""
    return MagicMock()


# =============================================================================
# Parser tests
# =============================================================================


class TestTrainParser:
    """Test that the train subcommand parser is correctly configured."""

    def test_train_command_registered_in_parser(self):
        """Test that 'train' is a valid subcommand."""
        from src.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["train"])
        assert args.command == "train"

    def test_train_min_examples_flag(self):
        """Test that --min-examples flag is accepted."""
        from src.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["train", "--min-examples", "16"])
        assert args.min_examples == 16

    def test_train_min_examples_default(self):
        """Test that --min-examples defaults to 8."""
        from src.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["train"])
        assert args.min_examples == 8

    def test_train_model_type_flag(self):
        """Test that --model-type flag is accepted with valid choices."""
        from src.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["train", "--model-type", "setfit"])
        assert args.model_type == "setfit"

    def test_train_model_type_invalid_rejected(self):
        """Test that invalid model type value is rejected."""
        from src.cli import create_parser

        parser = create_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["train", "--model-type", "invalid"])

    def test_train_output_flag(self):
        """Test that --output flag accepts a directory path."""
        from src.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["train", "--output", "/tmp/models/setfit"])
        assert args.output == Path("/tmp/models/setfit")

    def test_train_dry_run_flag(self):
        """Test that --dry-run flag is accepted."""
        from src.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["train", "--dry-run"])
        assert args.dry_run is True

    def test_train_db_path_flag(self):
        """Test that --db-path flag is accepted."""
        from src.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["train", "--db-path", "/tmp/test.db"])
        assert args.db_path == Path("/tmp/test.db")

    def test_train_defaults(self):
        """Test default values for all flags."""
        from src.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["train"])
        assert args.min_examples == 8
        assert args.model_type == "setfit"
        assert args.output is None
        assert args.dry_run is False
        assert args.db_path is None

    def test_train_help_does_not_error(self):
        """Test that --help works (exits with 0)."""
        from src.cli import create_parser

        parser = create_parser()
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["train", "--help"])
        assert exc_info.value.code == 0


# =============================================================================
# Dispatch tests
# =============================================================================


class TestTrainDispatch:
    """Test that train is properly registered in the main CLI dispatch."""

    def test_train_in_main_dispatch(self):
        """Test that the train command handler exists in __init__.py dispatcher."""
        from src.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["train"])
        assert args.command == "train"

    def test_train_handler_importable(self):
        """Test that cmd_train can be imported from the commands module."""
        from src.cli.commands.train import cmd_train

        assert callable(cmd_train)

    def test_train_builder_importable(self):
        """Test that build_train_parser can be imported."""
        from src.cli.commands.train import build_train_parser

        assert callable(build_train_parser)


# =============================================================================
# Successful training flow tests
# =============================================================================


class TestTrainCommand:
    """Test the train command execution with mocked classifier and database."""

    @patch("src.cli.commands.train.SetFitClassifier")
    @patch("src.cli.commands.train.EmailFeedbackStore")
    @patch("src.cli.commands.train.Database")
    def test_train_success_basic(
        self,
        mock_db_cls,
        mock_store_cls,
        mock_setfit_cls,
    ):
        """Test successful training with sufficient corrections."""
        from src.cli.commands.train import cmd_train

        # Setup database
        mock_db = _make_mock_database()
        mock_db_cls.return_value = mock_db

        # Setup corrections store
        mock_store = MagicMock()
        corrections = _make_mock_corrections(
            {
                "Newsletters": 10,
                "Promotions": 10,
            }
        )
        mock_store.get_corrections.return_value = corrections
        mock_store_cls.return_value = mock_store

        # Setup SetFit classifier
        mock_classifier = MagicMock()
        mock_classifier.train.return_value = {
            "num_examples": 20,
            "num_categories": 2,
            "examples_per_category": {"Newsletters": 10, "Promotions": 10},
        }
        mock_setfit_cls.return_value = mock_classifier

        args = _make_default_args()
        result = cmd_train(args)

        assert result == 0
        mock_classifier.train.assert_called_once()
        mock_classifier.save_model.assert_called_once()

    @patch("src.cli.commands.train.SetFitClassifier")
    @patch("src.cli.commands.train.EmailFeedbackStore")
    @patch("src.cli.commands.train.Database")
    def test_train_filters_insufficient_categories(
        self,
        mock_db_cls,
        mock_store_cls,
        mock_setfit_cls,
        capsys,
    ):
        """Test that categories with fewer than min_examples are skipped with warning."""
        from src.cli.commands.train import cmd_train

        mock_db = _make_mock_database()
        mock_db_cls.return_value = mock_db

        mock_store = MagicMock()
        # "Personal" has only 3 corrections, below the default threshold of 8
        corrections = _make_mock_corrections(
            {
                "Newsletters": 10,
                "Personal": 3,
                "Promotions": 10,
            }
        )
        mock_store.get_corrections.return_value = corrections
        mock_store_cls.return_value = mock_store

        mock_classifier = MagicMock()
        mock_classifier.train.return_value = {
            "num_examples": 20,
            "num_categories": 2,
            "examples_per_category": {"Newsletters": 10, "Promotions": 10},
        }
        mock_setfit_cls.return_value = mock_classifier

        args = _make_default_args()
        result = cmd_train(args)

        assert result == 0
        # Train should be called with only the examples from sufficient categories
        train_call_args = mock_classifier.train.call_args[0][0]
        train_labels = [label for _, label in train_call_args]
        assert "Personal" not in train_labels
        assert "Newsletters" in train_labels
        assert "Promotions" in train_labels

    @patch("src.cli.commands.train.SetFitClassifier")
    @patch("src.cli.commands.train.EmailFeedbackStore")
    @patch("src.cli.commands.train.Database")
    def test_train_custom_min_examples(
        self,
        mock_db_cls,
        mock_store_cls,
        mock_setfit_cls,
    ):
        """Test that --min-examples controls the minimum threshold."""
        from src.cli.commands.train import cmd_train

        mock_db = _make_mock_database()
        mock_db_cls.return_value = mock_db

        mock_store = MagicMock()
        corrections = _make_mock_corrections(
            {
                "Newsletters": 5,
                "Promotions": 5,
            }
        )
        mock_store.get_corrections.return_value = corrections
        mock_store_cls.return_value = mock_store

        mock_classifier = MagicMock()
        mock_classifier.train.return_value = {
            "num_examples": 10,
            "num_categories": 2,
            "examples_per_category": {"Newsletters": 5, "Promotions": 5},
        }
        mock_setfit_cls.return_value = mock_classifier

        # Set min_examples to 4 so both categories pass
        args = _make_default_args(min_examples=4)
        result = cmd_train(args)

        assert result == 0
        mock_classifier.train.assert_called_once()

    @patch("src.cli.commands.train.SetFitClassifier")
    @patch("src.cli.commands.train.EmailFeedbackStore")
    @patch("src.cli.commands.train.Database")
    def test_train_saves_to_custom_output(
        self,
        mock_db_cls,
        mock_store_cls,
        mock_setfit_cls,
    ):
        """Test that --output saves model to custom path."""
        from src.cli.commands.train import cmd_train

        mock_db = _make_mock_database()
        mock_db_cls.return_value = mock_db

        mock_store = MagicMock()
        corrections = _make_mock_corrections({"Newsletters": 10})
        mock_store.get_corrections.return_value = corrections
        mock_store_cls.return_value = mock_store

        mock_classifier = MagicMock()
        mock_classifier.train.return_value = {
            "num_examples": 10,
            "num_categories": 1,
            "examples_per_category": {"Newsletters": 10},
        }
        mock_setfit_cls.return_value = mock_classifier

        custom_output = Path("/custom/models/setfit")
        args = _make_default_args(output=custom_output)
        result = cmd_train(args)

        assert result == 0
        mock_classifier.save_model.assert_called_once_with(custom_output)

    @patch("src.cli.commands.train.SetFitClassifier")
    @patch("src.cli.commands.train.EmailFeedbackStore")
    @patch("src.cli.commands.train.Database")
    def test_train_saves_version_metadata(
        self,
        mock_db_cls,
        mock_store_cls,
        mock_setfit_cls,
    ):
        """Test that model is saved with version metadata (save_model called)."""
        from src.cli.commands.train import cmd_train

        mock_db = _make_mock_database()
        mock_db_cls.return_value = mock_db

        mock_store = MagicMock()
        corrections = _make_mock_corrections({"Newsletters": 10})
        mock_store.get_corrections.return_value = corrections
        mock_store_cls.return_value = mock_store

        mock_classifier = MagicMock()
        mock_classifier.train.return_value = {
            "num_examples": 10,
            "num_categories": 1,
            "examples_per_category": {"Newsletters": 10},
        }
        mock_setfit_cls.return_value = mock_classifier

        args = _make_default_args()
        result = cmd_train(args)

        assert result == 0
        # save_model is called, which internally writes version metadata
        mock_classifier.save_model.assert_called_once()


# =============================================================================
# Dry-run tests
# =============================================================================


class TestTrainDryRun:
    """Test train --dry-run mode."""

    @patch("src.cli.commands.train.EmailFeedbackStore")
    @patch("src.cli.commands.train.Database")
    def test_dry_run_does_not_train(
        self,
        mock_db_cls,
        mock_store_cls,
        capsys,
    ):
        """Test that --dry-run does not create classifier or train model."""
        from src.cli.commands.train import cmd_train

        mock_db = _make_mock_database()
        mock_db_cls.return_value = mock_db

        mock_store = MagicMock()
        corrections = _make_mock_corrections(
            {
                "Newsletters": 10,
                "Promotions": 10,
            }
        )
        mock_store.get_corrections.return_value = corrections
        mock_store_cls.return_value = mock_store

        args = _make_default_args(dry_run=True)

        with patch("src.cli.commands.train.SetFitClassifier") as mock_cls:
            result = cmd_train(args)
            mock_cls.assert_not_called()

        assert result == 0

    @patch("src.cli.commands.train.EmailFeedbackStore")
    @patch("src.cli.commands.train.Database")
    def test_dry_run_shows_preview(
        self,
        mock_db_cls,
        mock_store_cls,
        capsys,
    ):
        """Test that --dry-run shows training preview information."""
        from src.cli.commands.train import cmd_train

        mock_db = _make_mock_database()
        mock_db_cls.return_value = mock_db

        mock_store = MagicMock()
        corrections = _make_mock_corrections(
            {
                "Newsletters": 10,
                "Promotions": 12,
            }
        )
        mock_store.get_corrections.return_value = corrections
        mock_store_cls.return_value = mock_store

        args = _make_default_args(dry_run=True)
        result = cmd_train(args)

        assert result == 0
        captured = capsys.readouterr()
        assert "DRY RUN" in captured.out or "dry" in captured.out.lower()

    @patch("src.cli.commands.train.EmailFeedbackStore")
    @patch("src.cli.commands.train.Database")
    def test_dry_run_json_output(
        self,
        mock_db_cls,
        mock_store_cls,
        capsys,
    ):
        """Test that --dry-run with --json includes dry_run indicator."""
        from src.cli.commands.train import cmd_train

        mock_db = _make_mock_database()
        mock_db_cls.return_value = mock_db

        mock_store = MagicMock()
        corrections = _make_mock_corrections({"Newsletters": 10})
        mock_store.get_corrections.return_value = corrections
        mock_store_cls.return_value = mock_store

        args = _make_default_args(dry_run=True, json=True)
        result = cmd_train(args)

        assert result == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["dry_run"] is True
        assert data["command"] == "train"


# =============================================================================
# JSON output tests
# =============================================================================


class TestTrainJsonOutput:
    """Test train command JSON output mode."""

    @patch("src.cli.commands.train.SetFitClassifier")
    @patch("src.cli.commands.train.EmailFeedbackStore")
    @patch("src.cli.commands.train.Database")
    def test_train_json_output_success(
        self,
        mock_db_cls,
        mock_store_cls,
        mock_setfit_cls,
        capsys,
    ):
        """Test that --json outputs structured JSON on success."""
        from src.cli.commands.train import cmd_train

        mock_db = _make_mock_database()
        mock_db_cls.return_value = mock_db

        mock_store = MagicMock()
        corrections = _make_mock_corrections({"Newsletters": 10, "Promotions": 10})
        mock_store.get_corrections.return_value = corrections
        mock_store_cls.return_value = mock_store

        mock_classifier = MagicMock()
        mock_classifier.train.return_value = {
            "num_examples": 20,
            "num_categories": 2,
            "examples_per_category": {"Newsletters": 10, "Promotions": 10},
        }
        mock_setfit_cls.return_value = mock_classifier

        args = _make_default_args(json=True)
        result = cmd_train(args)

        assert result == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["command"] == "train"
        assert data["status"] == "success"
        assert "training_stats" in data
        assert "model_path" in data

    @patch("src.cli.commands.train.EmailFeedbackStore")
    @patch("src.cli.commands.train.Database")
    def test_train_json_output_error(
        self,
        mock_db_cls,
        mock_store_cls,
        capsys,
    ):
        """Test that errors in --json mode output JSON error."""
        from src.cli.commands.train import cmd_train

        mock_db = _make_mock_database()
        mock_db_cls.return_value = mock_db

        mock_store = MagicMock()
        mock_store.get_corrections.return_value = []  # No corrections
        mock_store_cls.return_value = mock_store

        args = _make_default_args(json=True)
        result = cmd_train(args)

        assert result == 1
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["status"] == "error"


# =============================================================================
# Error handling tests
# =============================================================================


class TestTrainErrors:
    """Test train command error handling."""

    @patch("src.cli.commands.train.EmailFeedbackStore")
    @patch("src.cli.commands.train.Database")
    def test_train_no_corrections(
        self,
        mock_db_cls,
        mock_store_cls,
    ):
        """Test train fails gracefully when no corrections exist."""
        from src.cli.commands.train import cmd_train

        mock_db = _make_mock_database()
        mock_db_cls.return_value = mock_db

        mock_store = MagicMock()
        mock_store.get_corrections.return_value = []
        mock_store_cls.return_value = mock_store

        args = _make_default_args()
        result = cmd_train(args)

        assert result == 1

    @patch("src.cli.commands.train.EmailFeedbackStore")
    @patch("src.cli.commands.train.Database")
    def test_train_all_categories_below_threshold(
        self,
        mock_db_cls,
        mock_store_cls,
    ):
        """Test train fails when ALL categories have insufficient corrections."""
        from src.cli.commands.train import cmd_train

        mock_db = _make_mock_database()
        mock_db_cls.return_value = mock_db

        mock_store = MagicMock()
        # All categories below default threshold of 8
        corrections = _make_mock_corrections(
            {
                "Newsletters": 3,
                "Personal": 2,
            }
        )
        mock_store.get_corrections.return_value = corrections
        mock_store_cls.return_value = mock_store

        args = _make_default_args()
        result = cmd_train(args)

        assert result == 1

    @patch("src.cli.commands.train.Database")
    def test_train_database_error(
        self,
        mock_db_cls,
    ):
        """Test train handles database connection errors."""
        from src.cli.commands.train import cmd_train
        from src.exceptions import StorageError

        mock_db_cls.side_effect = StorageError("Cannot open database")

        args = _make_default_args()
        result = cmd_train(args)

        assert result == 1

    @patch("src.cli.commands.train.SetFitClassifier")
    @patch("src.cli.commands.train.EmailFeedbackStore")
    @patch("src.cli.commands.train.Database")
    def test_train_setfit_import_error(
        self,
        mock_db_cls,
        mock_store_cls,
        mock_setfit_cls,
    ):
        """Test train handles SetFit not installed (ImportError)."""
        from src.cli.commands.train import cmd_train

        mock_db = _make_mock_database()
        mock_db_cls.return_value = mock_db

        mock_store = MagicMock()
        corrections = _make_mock_corrections({"Newsletters": 10})
        mock_store.get_corrections.return_value = corrections
        mock_store_cls.return_value = mock_store

        mock_setfit_cls.side_effect = ImportError("The setfit library is not installed.")

        args = _make_default_args()
        result = cmd_train(args)

        assert result == 1

    @patch("src.cli.commands.train.SetFitClassifier")
    @patch("src.cli.commands.train.EmailFeedbackStore")
    @patch("src.cli.commands.train.Database")
    def test_train_training_failure(
        self,
        mock_db_cls,
        mock_store_cls,
        mock_setfit_cls,
    ):
        """Test train handles training failures gracefully."""
        from src.cli.commands.train import cmd_train

        mock_db = _make_mock_database()
        mock_db_cls.return_value = mock_db

        mock_store = MagicMock()
        corrections = _make_mock_corrections({"Newsletters": 10})
        mock_store.get_corrections.return_value = corrections
        mock_store_cls.return_value = mock_store

        mock_classifier = MagicMock()
        mock_classifier.train.side_effect = ValueError("Training failed")
        mock_setfit_cls.return_value = mock_classifier

        args = _make_default_args()
        result = cmd_train(args)

        assert result == 1


# =============================================================================
# Output format tests
# =============================================================================


class TestTrainOutput:
    """Test train command output formatting."""

    @patch("src.cli.commands.train.SetFitClassifier")
    @patch("src.cli.commands.train.EmailFeedbackStore")
    @patch("src.cli.commands.train.Database")
    def test_train_prints_training_results(
        self,
        mock_db_cls,
        mock_store_cls,
        mock_setfit_cls,
        capsys,
    ):
        """Test that train prints a human-readable training summary."""
        from src.cli.commands.train import cmd_train

        mock_db = _make_mock_database()
        mock_db_cls.return_value = mock_db

        mock_store = MagicMock()
        corrections = _make_mock_corrections(
            {
                "Newsletters": 10,
                "Promotions": 12,
            }
        )
        mock_store.get_corrections.return_value = corrections
        mock_store_cls.return_value = mock_store

        mock_classifier = MagicMock()
        mock_classifier.train.return_value = {
            "num_examples": 22,
            "num_categories": 2,
            "examples_per_category": {"Newsletters": 10, "Promotions": 12},
        }
        mock_setfit_cls.return_value = mock_classifier

        args = _make_default_args()
        result = cmd_train(args)

        assert result == 0
        captured = capsys.readouterr()
        assert "TRAINING RESULTS" in captured.out or "Training" in captured.out
        assert "Newsletters" in captured.out
        assert "Promotions" in captured.out

    @patch("src.cli.commands.train.SetFitClassifier")
    @patch("src.cli.commands.train.EmailFeedbackStore")
    @patch("src.cli.commands.train.Database")
    def test_train_warns_on_skipped_categories(
        self,
        mock_db_cls,
        mock_store_cls,
        mock_setfit_cls,
        capsys,
    ):
        """Test that skipped categories produce a warning message."""
        from src.cli.commands.train import cmd_train

        mock_db = _make_mock_database()
        mock_db_cls.return_value = mock_db

        mock_store = MagicMock()
        corrections = _make_mock_corrections(
            {
                "Newsletters": 10,
                "Personal": 3,  # Below threshold
            }
        )
        mock_store.get_corrections.return_value = corrections
        mock_store_cls.return_value = mock_store

        mock_classifier = MagicMock()
        mock_classifier.train.return_value = {
            "num_examples": 10,
            "num_categories": 1,
            "examples_per_category": {"Newsletters": 10},
        }
        mock_setfit_cls.return_value = mock_classifier

        args = _make_default_args()
        result = cmd_train(args)

        assert result == 0
        captured = capsys.readouterr()
        # Should mention skipped category
        assert "Personal" in captured.out or "skipped" in captured.out.lower()


# =============================================================================
# Training data preparation tests
# =============================================================================


class TestTrainDataPreparation:
    """Test that corrections are correctly prepared for training."""

    @patch("src.cli.commands.train.SetFitClassifier")
    @patch("src.cli.commands.train.EmailFeedbackStore")
    @patch("src.cli.commands.train.Database")
    def test_corrections_grouped_by_category(
        self,
        mock_db_cls,
        mock_store_cls,
        mock_setfit_cls,
    ):
        """Test that corrections are grouped by new_category for training."""
        from src.cli.commands.train import cmd_train

        mock_db = _make_mock_database()
        mock_db_cls.return_value = mock_db

        # We need the store to return corrections, and also need to verify
        # that the training examples use the email subject/body as text
        # and new_category as label
        mock_store = MagicMock()
        corrections = _make_mock_corrections(
            {
                "Newsletters": 10,
                "Promotions": 8,
            }
        )
        mock_store.get_corrections.return_value = corrections
        mock_store_cls.return_value = mock_store

        mock_classifier = MagicMock()
        mock_classifier.train.return_value = {
            "num_examples": 18,
            "num_categories": 2,
            "examples_per_category": {"Newsletters": 10, "Promotions": 8},
        }
        mock_setfit_cls.return_value = mock_classifier

        args = _make_default_args()
        result = cmd_train(args)

        assert result == 0
        # Verify train was called with (text, label) tuples
        train_call_args = mock_classifier.train.call_args[0][0]
        assert isinstance(train_call_args, list)
        assert all(isinstance(item, tuple) and len(item) == 2 for item in train_call_args)
        # All labels should be either Newsletters or Promotions
        labels = {label for _, label in train_call_args}
        assert labels == {"Newsletters", "Promotions"}

    @patch("src.cli.commands.train.SetFitClassifier")
    @patch("src.cli.commands.train.EmailFeedbackStore")
    @patch("src.cli.commands.train.Database")
    def test_classifier_created_with_correct_categories(
        self,
        mock_db_cls,
        mock_store_cls,
        mock_setfit_cls,
    ):
        """Test that SetFitClassifier is created with the filtered category list."""
        from src.cli.commands.train import cmd_train

        mock_db = _make_mock_database()
        mock_db_cls.return_value = mock_db

        mock_store = MagicMock()
        corrections = _make_mock_corrections(
            {
                "Newsletters": 10,
                "Promotions": 10,
                "Junk": 2,  # Below threshold, will be skipped
            }
        )
        mock_store.get_corrections.return_value = corrections
        mock_store_cls.return_value = mock_store

        mock_classifier = MagicMock()
        mock_classifier.train.return_value = {
            "num_examples": 20,
            "num_categories": 2,
            "examples_per_category": {"Newsletters": 10, "Promotions": 10},
        }
        mock_setfit_cls.return_value = mock_classifier

        args = _make_default_args()
        result = cmd_train(args)

        assert result == 0
        # Verify SetFitClassifier was created with only the sufficient categories
        call_kwargs = mock_setfit_cls.call_args
        categories_arg = (
            call_kwargs[1]["categories"]
            if "categories" in (call_kwargs[1] or {})
            else call_kwargs[0][0]
            if call_kwargs[0]
            else call_kwargs[1].get("categories")
        )
        assert "Junk" not in categories_arg
        assert "Newsletters" in categories_arg
        assert "Promotions" in categories_arg
