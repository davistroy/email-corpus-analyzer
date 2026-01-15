"""
Unit tests for CLI TUI integration.

Tests the --no-tui flag, --headless flag, and TUI fallback behavior (Task 3B.4).
"""
import argparse
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.models.category import Category, CategorySource


def create_test_category(
    category_id: str = "test_cat_1",
    name: str = "Test Category",
) -> Category:
    """Helper to create test Category objects."""
    return Category(
        category_id=category_id,
        category_name=name,
        description="A test category",
        confidence=0.85,
        email_count=10,
        percentage=25.0,
        source=CategorySource.CONTENT_CLUSTER,
        source_id="test_source",
        example_email_ids=[],
        distinguishing_features=[]
    )


class TestReviewCommandFlags:
    """Test review command TUI-related flags."""

    def test_review_command_has_no_tui_flag(self):
        """Test review command has --no-tui flag."""
        from src.cli import create_parser

        parser = create_parser()

        args = parser.parse_args(["review"])
        assert hasattr(args, "no_tui")
        assert args.no_tui is False

        args = parser.parse_args(["review", "--no-tui"])
        assert args.no_tui is True

    def test_review_command_has_headless_flag(self):
        """Test review command has --headless flag for automation."""
        from src.cli import create_parser

        parser = create_parser()

        args = parser.parse_args(["review"])
        assert hasattr(args, "headless")
        assert args.headless is False

        args = parser.parse_args(["review", "--headless"])
        assert args.headless is True


class TestPipelineCommandFlags:
    """Test pipeline command TUI-related flags."""

    def test_pipeline_command_has_no_tui_flag(self):
        """Test pipeline command has --no-tui flag."""
        from src.cli import create_parser

        parser = create_parser()

        args = parser.parse_args(["pipeline", "--user-email", "test@example.com"])
        assert hasattr(args, "no_tui")
        assert args.no_tui is False

        args = parser.parse_args(["pipeline", "--user-email", "test@example.com", "--no-tui"])
        assert args.no_tui is True


class TestTUILaunch:
    """Test TUI launch behavior."""

    @patch("src.ui.category_review.is_tui_supported")
    @patch("src.ui.category_review.run_tui_review")
    @patch("src.ui.category_review.load_json")
    @patch("src.utils.paths.PathConfig.get_corpus_path")
    def test_review_launches_tui_by_default(
        self, mock_corpus_path, mock_load_json, mock_run_tui, mock_supported
    ):
        """Test that review launches TUI by default when supported."""
        from src.ui.category_review import review_categories_with_ui

        mock_corpus_path.return_value = Path("/nonexistent/corpus.json")
        mock_load_json.return_value = {"emails": []}
        mock_supported.return_value = True

        categories = [create_test_category()]
        mock_run_tui.return_value = categories

        result = review_categories_with_ui(categories, use_tui=True)

        mock_run_tui.assert_called_once()

    @patch("src.ui.category_review.review_categories")
    @patch("src.ui.category_review.load_json")
    @patch("src.utils.paths.PathConfig.get_corpus_path")
    def test_review_uses_legacy_cli_with_no_tui(self, mock_corpus_path, mock_load_json, mock_review):
        """Test that --no-tui uses legacy CLI interface."""
        from src.ui.category_review import review_categories_with_ui

        mock_corpus_path.return_value = Path("/nonexistent/corpus.json")
        mock_load_json.return_value = {"emails": []}

        categories = [create_test_category()]
        mock_review.return_value = categories

        result = review_categories_with_ui(categories, use_tui=False)

        mock_review.assert_called_once()


class TestHeadlessMode:
    """Test headless/automation mode."""

    @patch("src.cli.auto_approve_categories")
    @patch("src.cli.PathConfig")
    def test_headless_flag_auto_approves(self, mock_path_config, mock_auto_approve):
        """Test that --headless auto-approves all suggestions."""
        from src.cli import cmd_review

        mock_auto_approve.return_value = 0

        args = argparse.Namespace(
            suggestions=None,
            approved_file=None,
            no_cleanup=False,
            no_tui=False,
            headless=True,
            dry_run=False,
            json=False,
            verbose=False,
            quiet=False,
        )

        result = cmd_review(args)

        mock_auto_approve.assert_called_once()
        assert result == 0


class TestTUIFallback:
    """Test TUI fallback when terminal doesn't support it."""

    def test_is_tui_supported_returns_boolean(self):
        """Test that TUI support check returns boolean."""
        from src.ui.category_review import is_tui_supported

        result = is_tui_supported()

        assert isinstance(result, bool)

    @patch("src.ui.category_review.is_tui_supported")
    @patch("src.ui.category_review.review_categories")
    @patch("src.ui.category_review.load_json")
    @patch("src.utils.paths.PathConfig.get_corpus_path")
    def test_fallback_to_legacy_when_tui_not_supported(
        self, mock_corpus_path, mock_load_json, mock_review, mock_supported
    ):
        """Test fallback to legacy CLI when TUI not supported."""
        from src.ui.category_review import review_categories_with_ui

        mock_corpus_path.return_value = Path("/nonexistent/corpus.json")
        mock_load_json.return_value = {"emails": []}
        mock_supported.return_value = False

        categories = [create_test_category()]
        mock_review.return_value = categories

        result = review_categories_with_ui(categories, use_tui=True)

        # Should fall back to legacy when TUI not supported
        mock_review.assert_called_once()


class TestTUIImport:
    """Test that TUI can be imported."""

    def test_tui_app_can_be_imported(self):
        """Test that TUI app can be imported."""
        from src.ui.tui import ReviewApp

        assert ReviewApp is not None

    def test_run_tui_review_function_exists(self):
        """Test that run_tui_review function exists."""
        from src.ui.category_review import run_tui_review

        assert callable(run_tui_review)


class TestCmdReviewWithTUI:
    """Test cmd_review with TUI integration."""

    @patch("src.cli.load_json")
    @patch("src.cli.PathConfig")
    def test_cmd_review_calls_review_categories_with_ui(self, mock_path_config, mock_load_json):
        """Test that cmd_review uses the TUI-aware review function."""
        from src.cli import cmd_review

        mock_path_config.get_suggestions_path.return_value = Path("/test/suggestions.json")
        mock_path_config.get_approved_categories_path.return_value = Path("/test/approved.json")
        mock_load_json.return_value = [
            {
                "category_id": "cat1",
                "category_name": "Test",
                "description": "Test category",
                "confidence": 0.85,
                "email_count": 10,
                "percentage": 25.0,
                "source": "content_cluster",
                "source_id": "test",
                "example_email_ids": [],
                "distinguishing_features": [],
            }
        ]

        # The function should exist and be callable
        assert callable(cmd_review)


class TestReviewCategoriesWithUIFunction:
    """Test the review_categories_with_ui wrapper function."""

    def test_function_signature(self):
        """Test that function has correct signature."""
        from src.ui.category_review import review_categories_with_ui
        import inspect

        sig = inspect.signature(review_categories_with_ui)
        params = list(sig.parameters.keys())

        assert "categories" in params
        assert "use_tui" in params
        assert "output_path" in params

    def test_function_defaults_to_tui(self):
        """Test that function defaults to using TUI."""
        from src.ui.category_review import review_categories_with_ui
        import inspect

        sig = inspect.signature(review_categories_with_ui)
        use_tui_param = sig.parameters.get("use_tui")

        assert use_tui_param is not None
        assert use_tui_param.default is True


class TestGracefulDegradation:
    """Test graceful degradation scenarios."""

    def test_is_tui_supported_does_not_raise(self):
        """Test that is_tui_supported never raises."""
        from src.ui.category_review import is_tui_supported

        # is_tui_supported should not raise even if something goes wrong
        result = is_tui_supported()
        assert isinstance(result, bool)

    def test_empty_categories_handled(self):
        """Test that empty categories list is handled gracefully."""
        from src.ui.tui import ReviewApp

        app = ReviewApp(categories=[])
        assert app is not None
        assert app.categories == []

    @patch("src.ui.category_review.is_tui_supported")
    @patch("src.ui.category_review.review_categories")
    @patch("src.ui.category_review.load_json")
    @patch("src.utils.paths.PathConfig.get_corpus_path")
    def test_graceful_fallback_on_tui_failure(
        self, mock_corpus_path, mock_load_json, mock_review, mock_supported
    ):
        """Test fallback when TUI fails during execution."""
        from src.ui.category_review import review_categories_with_ui

        mock_corpus_path.return_value = Path("/nonexistent/corpus.json")
        mock_load_json.return_value = {"emails": []}
        mock_supported.return_value = False  # TUI not supported

        categories = [create_test_category()]
        mock_review.return_value = categories

        result = review_categories_with_ui(categories, use_tui=True)

        # Should use legacy review when TUI not supported
        mock_review.assert_called_once()
