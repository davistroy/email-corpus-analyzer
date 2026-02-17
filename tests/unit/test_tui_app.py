"""
Unit tests for the TUI application foundation.

Tests the ReviewApp class, theme configuration, basic app lifecycle,
exception handling specifics, is_tui_supported, and TUI fallback behavior.
"""
from unittest.mock import patch

import pytest

from src.models.category import Category, CategorySource


def create_test_category(
    category_id: str = "test_cat_1",
    name: str = "Test Category",
    description: str = "A test category",
    confidence: float = 0.85,
    email_count: int = 10,
    percentage: float = 25.0,
    source: CategorySource = CategorySource.CONTENT_CLUSTER,
    example_email_ids: list[str] | None = None,
    distinguishing_features: list[str] | None = None
) -> Category:
    """Helper to create test Category objects."""
    return Category(
        category_id=category_id,
        category_name=name,
        description=description,
        confidence=confidence,
        email_count=email_count,
        percentage=percentage,
        source=source,
        source_id="test_source",
        example_email_ids=example_email_ids or [],
        distinguishing_features=distinguishing_features or []
    )


class TestReviewAppInit:
    """Test ReviewApp initialization."""

    def test_app_can_be_instantiated(self):
        """Test that ReviewApp can be instantiated."""
        from src.ui.tui.app import ReviewApp

        categories = [create_test_category()]
        app = ReviewApp(categories=categories)

        assert app is not None
        assert app.categories == categories

    def test_app_with_empty_categories(self):
        """Test app initialization with empty category list."""
        from src.ui.tui.app import ReviewApp

        app = ReviewApp(categories=[])

        assert app.categories == []

    def test_app_with_multiple_categories(self):
        """Test app initialization with multiple categories."""
        from src.ui.tui.app import ReviewApp

        categories = [
            create_test_category(category_id="cat1", name="Category 1"),
            create_test_category(category_id="cat2", name="Category 2"),
            create_test_category(category_id="cat3", name="Category 3"),
        ]
        app = ReviewApp(categories=categories)

        assert len(app.categories) == 3

    def test_app_tracks_approved_categories(self):
        """Test that app tracks approved categories."""
        from src.ui.tui.app import ReviewApp

        app = ReviewApp(categories=[create_test_category()])

        assert hasattr(app, "approved_categories")
        assert app.approved_categories == []

    def test_app_tracks_stats(self):
        """Test that app tracks modification stats."""
        from src.ui.tui.app import ReviewApp

        app = ReviewApp(categories=[create_test_category()])

        assert hasattr(app, "modified_count")
        assert hasattr(app, "merged_count")
        assert hasattr(app, "deleted_count")
        assert app.modified_count == 0
        assert app.merged_count == 0
        assert app.deleted_count == 0


class TestReviewAppTitle:
    """Test ReviewApp title and subtitle."""

    def test_app_has_title(self):
        """Test that app has a title."""
        from src.ui.tui.app import ReviewApp

        app = ReviewApp(categories=[])

        assert app.TITLE == "Category Review"

    def test_app_has_subtitle(self):
        """Test that app has a subtitle."""
        from src.ui.tui.app import ReviewApp

        app = ReviewApp(categories=[])

        assert "Email Corpus Analyzer" in app.SUB_TITLE


class TestReviewAppKeyBindings:
    """Test ReviewApp keyboard bindings."""

    def test_app_has_quit_binding(self):
        """Test that app has quit key binding."""
        from src.ui.tui.app import ReviewApp

        app = ReviewApp(categories=[])

        # Check that q binding exists in BINDINGS
        binding_keys = [b.key for b in app.BINDINGS]
        assert "q" in binding_keys or "ctrl+c" in binding_keys

    def test_app_has_help_binding(self):
        """Test that app has help key binding."""
        from src.ui.tui.app import ReviewApp

        app = ReviewApp(categories=[])

        binding_keys = [b.key for b in app.BINDINGS]
        assert "?" in binding_keys or "f1" in binding_keys

    def test_app_has_navigation_bindings(self):
        """Test that app has navigation key bindings."""
        from src.ui.tui.app import ReviewApp

        app = ReviewApp(categories=[])

        binding_keys = [b.key for b in app.BINDINGS]
        # Should have either j/k or arrow keys
        has_jk = "j" in binding_keys and "k" in binding_keys
        has_arrows = "down" in binding_keys and "up" in binding_keys

        assert has_jk or has_arrows


class TestReviewAppActions:
    """Test ReviewApp action methods."""

    def test_app_has_accept_action(self):
        """Test that app has accept action."""
        from src.ui.tui.app import ReviewApp

        app = ReviewApp(categories=[create_test_category()])

        assert hasattr(app, "action_accept") or hasattr(app, "accept_category")

    def test_app_has_rename_action(self):
        """Test that app has rename action."""
        from src.ui.tui.app import ReviewApp

        app = ReviewApp(categories=[create_test_category()])

        assert hasattr(app, "action_rename") or hasattr(app, "rename_category")

    def test_app_has_merge_action(self):
        """Test that app has merge action."""
        from src.ui.tui.app import ReviewApp

        app = ReviewApp(categories=[create_test_category()])

        assert hasattr(app, "action_merge") or hasattr(app, "merge_category")

    def test_app_has_delete_action(self):
        """Test that app has delete action."""
        from src.ui.tui.app import ReviewApp

        app = ReviewApp(categories=[create_test_category()])

        assert hasattr(app, "action_delete") or hasattr(app, "delete_category")

    def test_app_has_skip_action(self):
        """Test that app has skip action."""
        from src.ui.tui.app import ReviewApp

        app = ReviewApp(categories=[create_test_category()])

        assert hasattr(app, "action_skip") or hasattr(app, "skip_category")


class TestThemeConfiguration:
    """Test theme configuration."""

    def test_theme_module_exists(self):
        """Test that theme module exists."""
        from src.ui.tui import theme

        assert theme is not None

    def test_theme_has_colors(self):
        """Test that theme defines colors."""
        from src.ui.tui.theme import THEME_COLORS

        assert THEME_COLORS is not None
        assert isinstance(THEME_COLORS, dict)

    def test_theme_has_confidence_colors(self):
        """Test that theme has confidence level colors."""
        from src.ui.tui.theme import CONFIDENCE_COLORS

        assert CONFIDENCE_COLORS is not None
        assert "high" in CONFIDENCE_COLORS
        assert "medium" in CONFIDENCE_COLORS
        assert "low" in CONFIDENCE_COLORS

    def test_get_confidence_color_high(self):
        """Test getting color for high confidence."""
        from src.ui.tui.theme import get_confidence_color

        color = get_confidence_color(0.9)
        assert color is not None

    def test_get_confidence_color_medium(self):
        """Test getting color for medium confidence."""
        from src.ui.tui.theme import get_confidence_color

        color = get_confidence_color(0.6)
        assert color is not None

    def test_get_confidence_color_low(self):
        """Test getting color for low confidence."""
        from src.ui.tui.theme import get_confidence_color

        color = get_confidence_color(0.3)
        assert color is not None

    def test_confidence_color_boundaries(self):
        """Test confidence color at boundaries."""
        from src.ui.tui.theme import get_confidence_color

        # Test boundary values
        low_color = get_confidence_color(0.39)
        get_confidence_color(0.4)  # medium - verify no error at boundary
        high_color = get_confidence_color(0.7)

        # Colors should be different at boundaries
        assert low_color != high_color


class TestTUIPackageInit:
    """Test TUI package initialization."""

    def test_package_imports(self):
        """Test that TUI package can be imported."""
        from src.ui.tui import ReviewApp

        assert ReviewApp is not None

    def test_package_exports_app(self):
        """Test that package exports ReviewApp."""
        import src.ui.tui as tui

        assert hasattr(tui, "ReviewApp")

    def test_package_exports_theme(self):
        """Test that package exports theme utilities."""
        import src.ui.tui as tui

        assert hasattr(tui, "get_confidence_color")


class TestReviewAppState:
    """Test ReviewApp state management."""

    def test_app_tracks_selected_index(self):
        """Test that app tracks selected category index."""
        from src.ui.tui.app import ReviewApp

        app = ReviewApp(categories=[create_test_category()])

        assert hasattr(app, "selected_index") or hasattr(app, "_selected_index")

    def test_app_initial_selected_index(self):
        """Test that initial selected index is 0."""
        from src.ui.tui.app import ReviewApp

        categories = [create_test_category()]
        app = ReviewApp(categories=categories)

        selected_idx = getattr(app, "selected_index", getattr(app, "_selected_index", 0))
        assert selected_idx == 0

    def test_app_get_selected_category(self):
        """Test getting the currently selected category."""
        from src.ui.tui.app import ReviewApp

        category = create_test_category(name="Selected")
        app = ReviewApp(categories=[category])

        selected = app.get_selected_category()
        assert selected is not None
        assert selected.category_name == "Selected"

    def test_app_get_selected_returns_none_when_empty(self):
        """Test get_selected_category returns None when no categories."""
        from src.ui.tui.app import ReviewApp

        app = ReviewApp(categories=[])

        selected = app.get_selected_category()
        assert selected is None


class TestReviewAppCSS:
    """Test ReviewApp CSS configuration."""

    def test_app_has_css_path(self):
        """Test that app has CSS path or inline CSS."""
        from src.ui.tui.app import ReviewApp

        app = ReviewApp(categories=[])

        # App should have CSS_PATH or DEFAULT_CSS
        has_css = hasattr(app, "CSS_PATH") or hasattr(app, "CSS") or hasattr(app, "DEFAULT_CSS")
        assert has_css


class TestReviewAppGetResults:
    """Test ReviewApp result retrieval."""

    def test_app_get_approved_categories(self):
        """Test getting approved categories from app."""
        from src.ui.tui.app import ReviewApp

        cat1 = create_test_category(category_id="cat1", name="Category 1")
        cat2 = create_test_category(category_id="cat2", name="Category 2")
        app = ReviewApp(categories=[cat1, cat2])
        app.approved_categories = [cat1]

        result = app.get_approved_categories()
        assert len(result) == 1
        assert result[0].category_name == "Category 1"

    def test_app_get_stats(self):
        """Test getting stats from app."""
        from src.ui.tui.app import ReviewApp

        app = ReviewApp(categories=[])
        app.modified_count = 2
        app.merged_count = 1
        app.deleted_count = 3

        stats = app.get_stats()
        assert stats["modified"] == 2
        assert stats["merged"] == 1
        assert stats["deleted"] == 3


# === Exception Handling Tests (Work Item 3.2) ===


class TestNoMatchesExceptionHandling:
    """Test that TUI code uses NoMatches instead of bare Exception catches."""

    def test_app_imports_no_matches(self):
        """Test that app module imports NoMatches from textual.css.query."""
        import src.ui.tui.app as app_module

        # The module should have NoMatches available
        assert hasattr(app_module, "NoMatches")

    def test_rename_dialog_imports_no_matches(self):
        """Test that rename_dialog module imports NoMatches."""
        import src.ui.tui.dialogs.rename_dialog as rename_module

        assert hasattr(rename_module, "NoMatches")

    def test_merge_dialog_imports_no_matches(self):
        """Test that merge_dialog module imports NoMatches."""
        import src.ui.tui.dialogs.merge_dialog as merge_module

        assert hasattr(merge_module, "NoMatches")

    def test_no_bare_except_exception_in_app(self):
        """Test that app.py has no 'except Exception: pass' patterns."""
        import inspect

        import src.ui.tui.app as app_module

        source = inspect.getsource(app_module)
        # Look for the bad pattern: except Exception followed by pass on next line
        lines = source.split("\n")
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped == "except Exception:":
                # Check the next non-blank line
                next_line = lines[i + 1].strip() if i + 1 < len(lines) else ""
                assert next_line != "pass", (
                    f"Found 'except Exception: pass' at line {i + 1} in app.py"
                )

    def test_no_bare_except_exception_in_rename_dialog(self):
        """Test that rename_dialog.py has no 'except Exception: pass' patterns."""
        import inspect

        import src.ui.tui.dialogs.rename_dialog as rename_module

        source = inspect.getsource(rename_module)
        lines = source.split("\n")
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped == "except Exception:":
                next_line = lines[i + 1].strip() if i + 1 < len(lines) else ""
                assert next_line != "pass", (
                    f"Found 'except Exception: pass' at line {i + 1} in rename_dialog.py"
                )

    def test_no_bare_except_exception_in_merge_dialog(self):
        """Test that merge_dialog.py has no 'except Exception: pass' patterns."""
        import inspect

        import src.ui.tui.dialogs.merge_dialog as merge_module

        source = inspect.getsource(merge_module)
        lines = source.split("\n")
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped == "except Exception:":
                next_line = lines[i + 1].strip() if i + 1 < len(lines) else ""
                assert next_line != "pass", (
                    f"Found 'except Exception: pass' at line {i + 1} in merge_dialog.py"
                )

    def test_update_detail_panel_catches_no_matches(self):
        """Test that _update_detail_panel catches NoMatches when widget not mounted."""
        from textual.css.query import NoMatches

        from src.ui.tui.app import ReviewApp

        app = ReviewApp(categories=[create_test_category()])

        # Mock query_one to raise NoMatches (simulating widget not yet mounted)
        with patch.object(app, "query_one", side_effect=NoMatches("no match")):
            # Should NOT raise -- NoMatches is caught
            app._update_detail_panel()

    def test_update_detail_panel_propagates_other_exceptions(self):
        """Test that _update_detail_panel does NOT catch non-NoMatches exceptions."""
        from src.ui.tui.app import ReviewApp

        app = ReviewApp(categories=[create_test_category()])

        # Mock query_one to raise a RuntimeError (not NoMatches)
        with (
            patch.object(app, "query_one", side_effect=RuntimeError("unexpected")),
            pytest.raises(RuntimeError, match="unexpected"),
        ):
            app._update_detail_panel()

    def test_update_action_bar_catches_no_matches(self):
        """Test that _update_action_bar catches NoMatches when widget not mounted."""
        from textual.css.query import NoMatches

        from src.ui.tui.app import ReviewApp

        app = ReviewApp(categories=[create_test_category()])

        with patch.object(app, "query_one", side_effect=NoMatches("no match")):
            # Should NOT raise -- NoMatches is caught
            app._update_action_bar()

    def test_update_action_bar_propagates_other_exceptions(self):
        """Test that _update_action_bar does NOT catch non-NoMatches exceptions."""
        from src.ui.tui.app import ReviewApp

        app = ReviewApp(categories=[create_test_category()])

        with (
            patch.object(app, "query_one", side_effect=RuntimeError("unexpected")),
            pytest.raises(RuntimeError, match="unexpected"),
        ):
            app._update_action_bar()

    def test_update_table_catches_no_matches(self):
        """Test that _update_table catches NoMatches when widget not mounted."""
        from textual.css.query import NoMatches

        from src.ui.tui.app import ReviewApp

        app = ReviewApp(categories=[create_test_category()])

        with patch.object(app, "query_one", side_effect=NoMatches("no match")):
            # Should NOT raise -- NoMatches is caught
            app._update_table()

    def test_update_table_propagates_other_exceptions(self):
        """Test that _update_table does NOT catch non-NoMatches exceptions."""
        from src.ui.tui.app import ReviewApp

        app = ReviewApp(categories=[create_test_category()])

        with (
            patch.object(app, "query_one", side_effect=RuntimeError("unexpected")),
            pytest.raises(RuntimeError, match="unexpected"),
        ):
            app._update_table()


class TestIsTuiSupported:
    """Test the is_tui_supported function."""

    def test_is_tui_supported_exists(self):
        """Test that is_tui_supported function exists."""
        from src.ui.category_review import is_tui_supported

        assert callable(is_tui_supported)

    def test_is_tui_supported_returns_bool(self):
        """Test that is_tui_supported returns a boolean."""
        from src.ui.category_review import is_tui_supported

        result = is_tui_supported()
        assert isinstance(result, bool)

    def test_is_tui_supported_false_when_not_tty(self):
        """Test that is_tui_supported returns False when not in a TTY."""
        from src.ui.category_review import is_tui_supported

        with patch("sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = False
            with patch("sys.stdout") as mock_stdout:
                mock_stdout.isatty.return_value = True
                result = is_tui_supported()
                assert result is False

    def test_is_tui_supported_false_when_stdout_not_tty(self):
        """Test that is_tui_supported returns False when stdout is not a TTY."""
        from src.ui.category_review import is_tui_supported

        with patch("sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = True
            with patch("sys.stdout") as mock_stdout:
                mock_stdout.isatty.return_value = False
                result = is_tui_supported()
                assert result is False

    def test_is_tui_supported_false_when_textual_import_fails(self):
        """Test that is_tui_supported returns False when textual can't be imported."""
        from src.ui.category_review import is_tui_supported

        with patch("sys.stdin") as mock_stdin, \
             patch("sys.stdout") as mock_stdout:
            mock_stdin.isatty.return_value = True
            mock_stdout.isatty.return_value = True

            # Patch builtins.__import__ to raise ImportError for textual
            original_import = __builtins__.__import__ if hasattr(__builtins__, '__import__') else __import__

            def mock_import(name, *args, **kwargs):
                if name == "textual.app":
                    raise ImportError("No module named 'textual'")
                return original_import(name, *args, **kwargs)

            with patch("builtins.__import__", side_effect=mock_import):
                result = is_tui_supported()
                assert result is False


class TestTuiFallbackBehavior:
    """Test that TUI gracefully falls back to CLI when unavailable."""

    def test_review_falls_back_when_tui_not_supported(self):
        """Test that review falls back to legacy CLI when TUI is not supported."""
        from src.ui.category_review import is_tui_supported

        # In test environment (non-TTY), TUI should not be supported
        # This verifies the fallback path exists
        with patch("sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = False
            assert is_tui_supported() is False

    def test_review_app_email_lookup_defaults_to_empty(self):
        """Test that ReviewApp defaults email_lookup to empty dict."""
        from src.ui.tui.app import ReviewApp

        app = ReviewApp(categories=[create_test_category()])

        assert app.email_lookup == {}

    def test_review_app_accepts_email_lookup(self):
        """Test that ReviewApp stores provided email_lookup."""
        from src.ui.tui.app import ReviewApp

        lookup = {"email1": "data1", "email2": "data2"}
        app = ReviewApp(categories=[create_test_category()], email_lookup=lookup)

        assert app.email_lookup == lookup

    def test_get_approved_returns_copy(self):
        """Test that get_approved_categories returns a copy, not the original list."""
        from src.ui.tui.app import ReviewApp

        cat = create_test_category()
        app = ReviewApp(categories=[])
        app.approved_categories = [cat]

        result = app.get_approved_categories()
        assert result == [cat]
        # Mutating the returned list should not affect the app's internal list
        result.append(create_test_category(category_id="extra"))
        assert len(app.approved_categories) == 1

    def test_get_stats_includes_all_keys(self):
        """Test that get_stats returns all expected stat keys."""
        from src.ui.tui.app import ReviewApp

        app = ReviewApp(categories=[create_test_category()])
        stats = app.get_stats()

        expected_keys = {"modified", "merged", "deleted", "approved", "skipped", "remaining"}
        assert set(stats.keys()) == expected_keys

    def test_get_selected_category_out_of_bounds(self):
        """Test get_selected_category returns None when index is out of bounds."""
        from src.ui.tui.app import ReviewApp

        app = ReviewApp(categories=[create_test_category()])
        app._selected_index = 999

        assert app.get_selected_category() is None

    def test_get_selected_category_negative_index(self):
        """Test get_selected_category returns None for negative index."""
        from src.ui.tui.app import ReviewApp

        app = ReviewApp(categories=[create_test_category()])
        app._selected_index = -1

        assert app.get_selected_category() is None
