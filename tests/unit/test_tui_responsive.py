"""
Unit tests for TUI responsive layout (Phase 2 Item 1.5).

Tests:
- CSS uses fr units for flexible column sizing
- Minimum terminal size check on startup
- Terminal resize event handling
- Modal dialogs use percentage-based widths
- Column truncation recalculates based on width
- Layout renders at various terminal sizes (80x24, 120x40, 200x60)
"""

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
    distinguishing_features: list[str] | None = None,
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
        distinguishing_features=distinguishing_features or [],
    )


# ---------------------------------------------------------------------------
# CSS fr unit tests
# ---------------------------------------------------------------------------


class TestCSSFrUnits:
    """Test that APP_CSS uses fr (fractional) units for flexible layout."""

    def test_category_list_uses_fr_units(self):
        """Test that #category-list width uses fr units instead of fixed percentage."""
        from src.ui.tui.theme import APP_CSS

        # Should NOT use fixed percentage for category-list
        # Check that the CSS contains fr-based sizing
        assert "3fr" in APP_CSS or "2fr" in APP_CSS, (
            "category-list should use fr units for flexible sizing"
        )

    def test_detail_container_uses_fr_units(self):
        """Test that #detail-container width uses fr units instead of fixed percentage."""
        from src.ui.tui.theme import APP_CSS

        # The detail container should also use fr units
        assert "2fr" in APP_CSS, "detail-container should use fr units for flexible sizing"

    def test_no_hardcoded_60_40_split(self):
        """Test that the old hardcoded 60%/40% split is replaced."""
        from src.ui.tui.theme import APP_CSS

        # The old pattern was width: 60%; and width: 40%;
        # These should no longer appear in the main column containers
        lines = APP_CSS.split("\n")
        in_category_list = False
        in_detail_panel = False
        for line in lines:
            stripped = line.strip()
            if "#category-list" in stripped:
                in_category_list = True
                in_detail_panel = False
            elif "#detail-container" in stripped or "#detail-panel" in stripped:
                in_detail_panel = True
                in_category_list = False
            elif stripped == "}" and (in_category_list or in_detail_panel):
                in_category_list = False
                in_detail_panel = False

            if in_category_list and "width: 60%" in stripped:
                pytest.fail("category-list still uses hardcoded 60% width")
            if in_detail_panel and "width: 40%" in stripped:
                pytest.fail("detail-panel still uses hardcoded 40% width")

    def test_main_container_uses_horizontal_layout(self):
        """Test that the main container still uses horizontal layout."""
        from src.ui.tui.theme import APP_CSS

        assert "layout: horizontal" in APP_CSS


# ---------------------------------------------------------------------------
# Minimum terminal size check
# ---------------------------------------------------------------------------


class TestMinTerminalSizeCheck:
    """Test minimum terminal size enforcement."""

    def test_min_terminal_size_constants_exist(self):
        """Test that minimum terminal size constants are defined."""
        from src.ui.tui.app import MIN_TERMINAL_COLS, MIN_TERMINAL_ROWS

        assert MIN_TERMINAL_COLS >= 80
        assert MIN_TERMINAL_ROWS >= 24

    def test_min_terminal_size_values(self):
        """Test specific minimum size values."""
        from src.ui.tui.app import MIN_TERMINAL_COLS, MIN_TERMINAL_ROWS

        assert MIN_TERMINAL_COLS == 80
        assert MIN_TERMINAL_ROWS == 24

    def test_check_terminal_size_passes_at_minimum(self):
        """Test that check passes at exactly minimum size."""
        from src.ui.tui.app import check_terminal_size

        ok, msg = check_terminal_size(80, 24)
        assert ok is True
        assert msg is None or msg == ""

    def test_check_terminal_size_passes_above_minimum(self):
        """Test that check passes above minimum size."""
        from src.ui.tui.app import check_terminal_size

        ok, msg = check_terminal_size(120, 40)
        assert ok is True

    def test_check_terminal_size_fails_too_narrow(self):
        """Test that check fails when terminal is too narrow."""
        from src.ui.tui.app import check_terminal_size

        ok, msg = check_terminal_size(79, 24)
        assert ok is False
        assert msg is not None
        assert "80" in msg  # Should mention the minimum width

    def test_check_terminal_size_fails_too_short(self):
        """Test that check fails when terminal is too short."""
        from src.ui.tui.app import check_terminal_size

        ok, msg = check_terminal_size(80, 23)
        assert ok is False
        assert msg is not None
        assert "24" in msg  # Should mention the minimum height

    def test_check_terminal_size_fails_both_too_small(self):
        """Test that check fails when both dimensions are too small."""
        from src.ui.tui.app import check_terminal_size

        ok, msg = check_terminal_size(60, 20)
        assert ok is False
        assert msg is not None

    def test_check_terminal_size_message_is_friendly(self):
        """Test that the failure message is user-friendly."""
        from src.ui.tui.app import check_terminal_size

        ok, msg = check_terminal_size(60, 20)
        assert ok is False
        # Message should mention current and required size
        assert "60" in msg or "20" in msg
        assert "80" in msg or "24" in msg


# ---------------------------------------------------------------------------
# Terminal resize handling
# ---------------------------------------------------------------------------


class TestTerminalResizeHandling:
    """Test that the app handles terminal resize events."""

    def test_app_has_on_resize_handler(self):
        """Test that ReviewApp has a resize event handler."""
        from src.ui.tui.app import ReviewApp

        app = ReviewApp(categories=[create_test_category()])
        assert hasattr(app, "on_resize") or hasattr(app, "handle_resize")

    def test_resize_handler_is_callable(self):
        """Test that the resize handler is callable."""
        from src.ui.tui.app import ReviewApp

        app = ReviewApp(categories=[create_test_category()])
        handler = getattr(app, "on_resize", getattr(app, "handle_resize", None))
        assert callable(handler)


# ---------------------------------------------------------------------------
# Dynamic column truncation
# ---------------------------------------------------------------------------


class TestDynamicColumnTruncation:
    """Test that column widths adapt to available width."""

    def test_calculate_name_column_width_default(self):
        """Test default name column width calculation."""
        from src.ui.tui.widgets.category_table import calculate_name_column_width

        # At 80 columns the pane is ~44 chars wide after borders,
        # minus 40 fixed columns leaves 4 — clamped to minimum (15).
        # At 120 columns we get more usable space.
        width_80 = calculate_name_column_width(80)
        assert width_80 >= 15
        assert width_80 <= 50

        width_120 = calculate_name_column_width(120)
        assert width_120 >= 20
        assert width_120 <= 60

    def test_calculate_name_column_width_wide_terminal(self):
        """Test name column width at wide terminal (200 cols)."""
        from src.ui.tui.widgets.category_table import calculate_name_column_width

        width = calculate_name_column_width(200)
        # At 200 cols, name column should be wider than at 80
        narrow_width = calculate_name_column_width(80)
        assert width > narrow_width

    def test_calculate_name_column_width_narrow_terminal(self):
        """Test name column width at narrow terminal."""
        from src.ui.tui.widgets.category_table import calculate_name_column_width

        width = calculate_name_column_width(80)
        assert width >= 15  # Should still be usable

    def test_calculate_name_column_width_minimum(self):
        """Test that name column has a minimum width."""
        from src.ui.tui.widgets.category_table import calculate_name_column_width

        # Even at very small terminal, name column should have minimum
        width = calculate_name_column_width(40)
        assert width >= 15

    def test_get_name_truncation_length_returns_int(self):
        """Test that the truncation function returns an integer."""
        from src.ui.tui.widgets.category_table import calculate_name_column_width

        width = calculate_name_column_width(120)
        assert isinstance(width, int)


# ---------------------------------------------------------------------------
# Modal dialog percentage widths
# ---------------------------------------------------------------------------


class TestModalDialogResponsiveWidths:
    """Test that modal dialogs use percentage-based widths."""

    def test_merge_dialog_uses_percentage_width(self):
        """Test that merge dialog CSS uses percentage width, not fixed chars."""
        from src.ui.tui.dialogs.merge_dialog import MergeDialog

        css = MergeDialog.CSS
        # Should use percentage width (max 80%, min 60 chars)
        assert "%" in css, "Merge dialog should use percentage-based width"

    def test_rename_dialog_uses_percentage_width(self):
        """Test that rename dialog CSS uses percentage width, not fixed chars."""
        from src.ui.tui.dialogs.rename_dialog import RenameDialog

        css = RenameDialog.CSS
        # Should use percentage width
        assert "%" in css, "Rename dialog should use percentage-based width"

    def test_merge_dialog_has_min_width(self):
        """Test that merge dialog has a minimum width constraint."""
        from src.ui.tui.dialogs.merge_dialog import MergeDialog

        css = MergeDialog.CSS
        assert "min-width" in css, "Merge dialog should have min-width"

    def test_rename_dialog_has_min_width(self):
        """Test that rename dialog has a minimum width constraint."""
        from src.ui.tui.dialogs.rename_dialog import RenameDialog

        css = RenameDialog.CSS
        assert "min-width" in css, "Rename dialog should have min-width"

    def test_merge_dialog_has_max_width(self):
        """Test that merge dialog has a maximum width constraint."""
        from src.ui.tui.dialogs.merge_dialog import MergeDialog

        css = MergeDialog.CSS
        assert "max-width" in css, "Merge dialog should have max-width"

    def test_rename_dialog_has_max_width(self):
        """Test that rename dialog has a maximum width constraint."""
        from src.ui.tui.dialogs.rename_dialog import RenameDialog

        css = RenameDialog.CSS
        assert "max-width" in css, "Rename dialog should have max-width"


# ---------------------------------------------------------------------------
# Layout rendering at various sizes
# ---------------------------------------------------------------------------


class TestLayoutRenderingSizes:
    """Test that layout works at different terminal sizes."""

    def test_app_css_has_min_width_on_columns(self):
        """Test that column containers have min-width to prevent collapse."""
        from src.ui.tui.theme import APP_CSS

        assert "min-width" in APP_CSS, "Column containers should have min-width"

    def test_app_instantiation_at_any_size(self):
        """Test that app can be instantiated regardless of terminal size."""
        from src.ui.tui.app import ReviewApp

        categories = [
            create_test_category(category_id=f"cat_{i}", name=f"Category {i}") for i in range(10)
        ]
        app = ReviewApp(categories=categories)
        assert app is not None

    def test_css_has_overflow_handling(self):
        """Test that CSS includes overflow handling for small terminals."""
        from src.ui.tui.theme import APP_CSS

        # Should have overflow handling somewhere
        assert "overflow" in APP_CSS.lower() or "auto" in APP_CSS.lower(), (
            "CSS should handle overflow for small terminals"
        )


# ---------------------------------------------------------------------------
# Integration: CSS well-formedness
# ---------------------------------------------------------------------------


class TestCSSWellFormedness:
    """Test that the updated CSS is well-formed."""

    def test_css_has_balanced_braces(self):
        """Test that CSS has balanced curly braces."""
        from src.ui.tui.theme import APP_CSS

        open_count = APP_CSS.count("{")
        close_count = APP_CSS.count("}")
        assert open_count == close_count, (
            f"Unbalanced braces: {open_count} open, {close_count} close"
        )

    def test_css_has_screen_rule(self):
        """Test that CSS still has the Screen rule."""
        from src.ui.tui.theme import APP_CSS

        assert "Screen" in APP_CSS

    def test_css_has_main_container_rule(self):
        """Test that CSS still has the main-container rule."""
        from src.ui.tui.theme import APP_CSS

        assert "#main-container" in APP_CSS

    def test_css_has_action_bar_rule(self):
        """Test that CSS still has the action-bar rule."""
        from src.ui.tui.theme import APP_CSS

        assert "#action-bar" in APP_CSS

    def test_css_has_datatable_rules(self):
        """Test that CSS still has DataTable styling rules."""
        from src.ui.tui.theme import APP_CSS

        assert "DataTable" in APP_CSS
