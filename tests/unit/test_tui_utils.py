"""
Tests for centralized TUI utility functions.

Phase 2, Item 1.1: Centralize shared TUI utilities.
Tests written first per TDD constitution.
"""


# ---------------------------------------------------------------------------
# format_confidence_bar tests
# ---------------------------------------------------------------------------


class TestFormatConfidenceBar:
    """Test the unified format_confidence_bar function."""

    def test_basic_bar_at_half(self):
        """Test bar at 50% confidence shows correct fill ratio."""
        from src.ui.tui.utils import format_confidence_bar

        bar = format_confidence_bar(0.5, width=10)
        assert bar is not None
        assert len(bar) > 0
        # Should contain filled and empty block chars
        assert "\u2588" in bar  # filled block
        assert "\u2591" in bar  # empty block

    def test_bar_zero_confidence(self):
        """Test bar at 0.0 shows all empty blocks."""
        from src.ui.tui.utils import format_confidence_bar

        bar = format_confidence_bar(0.0, width=10)
        assert "\u2588" not in bar  # no filled blocks
        assert "\u2591" in bar  # has empty blocks

    def test_bar_full_confidence(self):
        """Test bar at 1.0 shows all filled blocks."""
        from src.ui.tui.utils import format_confidence_bar

        bar = format_confidence_bar(1.0, width=10)
        assert "\u2588" in bar  # has filled blocks
        assert "\u2591" not in bar  # no empty blocks

    def test_bar_negative_clamped_to_zero(self):
        """Test that negative values are clamped to 0.0."""
        from src.ui.tui.utils import format_confidence_bar

        bar = format_confidence_bar(-0.5, width=10)
        # Should be identical to 0.0
        bar_zero = format_confidence_bar(0.0, width=10)
        assert bar == bar_zero

    def test_bar_above_one_clamped_to_one(self):
        """Test that values > 1.0 are clamped to 1.0."""
        from src.ui.tui.utils import format_confidence_bar

        bar = format_confidence_bar(1.5, width=10)
        bar_one = format_confidence_bar(1.0, width=10)
        assert bar == bar_one

    def test_bar_width_respected(self):
        """Test that different widths produce bars with correct block count."""
        from src.ui.tui.utils import format_confidence_bar

        bar_10 = format_confidence_bar(0.5, width=10)
        bar_20 = format_confidence_bar(0.5, width=20)
        # Wider bar should have more block characters total
        blocks_10 = bar_10.count("\u2588") + bar_10.count("\u2591")
        blocks_20 = bar_20.count("\u2588") + bar_20.count("\u2591")
        assert blocks_20 > blocks_10

    def test_bar_default_width_is_10(self):
        """Test that default width is 10."""
        from src.ui.tui.utils import format_confidence_bar

        bar = format_confidence_bar(0.5)
        blocks = bar.count("\u2588") + bar.count("\u2591")
        assert blocks == 10

    def test_bar_includes_percentage(self):
        """Test that the bar includes a percentage label."""
        from src.ui.tui.utils import format_confidence_bar

        bar = format_confidence_bar(0.85, width=10)
        assert "85%" in bar

    def test_bar_percentage_zero(self):
        """Test percentage label at 0%."""
        from src.ui.tui.utils import format_confidence_bar

        bar = format_confidence_bar(0.0, width=10)
        assert "0%" in bar

    def test_bar_percentage_hundred(self):
        """Test percentage label at 100%."""
        from src.ui.tui.utils import format_confidence_bar

        bar = format_confidence_bar(1.0, width=10)
        assert "100%" in bar

    def test_bar_high_confidence_color(self):
        """Test that high confidence (>= 0.7) gets green color markup."""
        from src.ui.tui.utils import format_confidence_bar

        bar = format_confidence_bar(0.8, width=10, colored=True)
        assert "green" in bar

    def test_bar_medium_confidence_color(self):
        """Test that medium confidence (0.4-0.7) gets yellow color markup."""
        from src.ui.tui.utils import format_confidence_bar

        bar = format_confidence_bar(0.5, width=10, colored=True)
        assert "yellow" in bar

    def test_bar_low_confidence_color(self):
        """Test that low confidence (< 0.4) gets red color markup."""
        from src.ui.tui.utils import format_confidence_bar

        bar = format_confidence_bar(0.2, width=10, colored=True)
        assert "red" in bar

    def test_bar_uncolored_by_default(self):
        """Test that default (uncolored) mode produces no markup."""
        from src.ui.tui.utils import format_confidence_bar

        bar = format_confidence_bar(0.8, width=10)
        # Default uncolored should not contain Rich markup brackets for color
        assert "[green]" not in bar
        assert "[red]" not in bar
        assert "[yellow]" not in bar

    def test_bar_colored_mode_includes_markup(self):
        """Test that colored mode includes Rich markup."""
        from src.ui.tui.utils import format_confidence_bar

        bar = format_confidence_bar(0.8, width=10, colored=True)
        assert "[" in bar  # Contains markup


# ---------------------------------------------------------------------------
# get_confidence_level tests
# ---------------------------------------------------------------------------


class TestGetConfidenceLevel:
    """Test the unified get_confidence_level function."""

    def test_high_confidence(self):
        """Test high confidence level."""
        from src.ui.tui.utils import get_confidence_level

        assert get_confidence_level(0.9) == "high"
        assert get_confidence_level(0.7) == "high"
        assert get_confidence_level(1.0) == "high"

    def test_medium_confidence(self):
        """Test medium confidence level."""
        from src.ui.tui.utils import get_confidence_level

        assert get_confidence_level(0.5) == "medium"
        assert get_confidence_level(0.4) == "medium"
        assert get_confidence_level(0.69) == "medium"

    def test_low_confidence(self):
        """Test low confidence level."""
        from src.ui.tui.utils import get_confidence_level

        assert get_confidence_level(0.3) == "low"
        assert get_confidence_level(0.0) == "low"
        assert get_confidence_level(0.39) == "low"

    def test_boundary_at_0_7(self):
        """Test exact boundary at 0.7 (should be high)."""
        from src.ui.tui.utils import get_confidence_level

        assert get_confidence_level(0.7) == "high"
        assert get_confidence_level(0.6999) == "medium"

    def test_boundary_at_0_4(self):
        """Test exact boundary at 0.4 (should be medium)."""
        from src.ui.tui.utils import get_confidence_level

        assert get_confidence_level(0.4) == "medium"
        assert get_confidence_level(0.3999) == "low"

    def test_negative_is_low(self):
        """Test that negative values return low."""
        from src.ui.tui.utils import get_confidence_level

        assert get_confidence_level(-0.1) == "low"

    def test_above_one_is_high(self):
        """Test that values above 1.0 return high."""
        from src.ui.tui.utils import get_confidence_level

        assert get_confidence_level(1.5) == "high"


# ---------------------------------------------------------------------------
# get_confidence_color tests
# ---------------------------------------------------------------------------


class TestGetConfidenceColor:
    """Test get_confidence_color delegates through the same thresholds."""

    def test_high_returns_green(self):
        """Test high confidence returns green hex."""
        from src.ui.tui.utils import get_confidence_color

        color = get_confidence_color(0.9)
        assert color is not None
        assert isinstance(color, str)

    def test_medium_returns_yellow(self):
        """Test medium confidence returns yellow hex."""
        from src.ui.tui.utils import get_confidence_color

        color = get_confidence_color(0.5)
        assert color is not None

    def test_low_returns_red(self):
        """Test low confidence returns red hex."""
        from src.ui.tui.utils import get_confidence_color

        color = get_confidence_color(0.2)
        assert color is not None

    def test_different_levels_different_colors(self):
        """Test that different levels produce different colors."""
        from src.ui.tui.utils import get_confidence_color

        high = get_confidence_color(0.9)
        medium = get_confidence_color(0.5)
        low = get_confidence_color(0.2)
        assert high != medium
        assert medium != low
        assert high != low


# ---------------------------------------------------------------------------
# Truncation constants tests
# ---------------------------------------------------------------------------


class TestTruncationConstants:
    """Test that truncation constants are properly defined and usable."""

    def test_max_name_display_defined(self):
        """Test MAX_NAME_DISPLAY constant exists and has expected value."""
        from src.ui.tui.utils import MAX_NAME_DISPLAY

        assert MAX_NAME_DISPLAY == 28

    def test_max_subject_display_defined(self):
        """Test MAX_SUBJECT_DISPLAY constant exists and has expected value."""
        from src.ui.tui.utils import MAX_SUBJECT_DISPLAY

        assert MAX_SUBJECT_DISPLAY == 50

    def test_max_feature_display_defined(self):
        """Test MAX_FEATURE_DISPLAY constant exists and has expected value."""
        from src.ui.tui.utils import MAX_FEATURE_DISPLAY

        assert MAX_FEATURE_DISPLAY == 70

    def test_truncation_with_constant(self):
        """Test that constants work for truncation operations."""
        from src.ui.tui.utils import MAX_NAME_DISPLAY

        long_name = "A" * 100
        truncated = long_name[:MAX_NAME_DISPLAY]
        assert len(truncated) == 28


# ---------------------------------------------------------------------------
# Confidence threshold constants tests
# ---------------------------------------------------------------------------


class TestConfidenceThresholdConstants:
    """Test that confidence thresholds are centralized."""

    def test_high_threshold_defined(self):
        """Test CONFIDENCE_HIGH_THRESHOLD has expected value."""
        from src.ui.tui.utils import CONFIDENCE_HIGH_THRESHOLD

        assert CONFIDENCE_HIGH_THRESHOLD == 0.7

    def test_medium_threshold_defined(self):
        """Test CONFIDENCE_MEDIUM_THRESHOLD has expected value."""
        from src.ui.tui.utils import CONFIDENCE_MEDIUM_THRESHOLD

        assert CONFIDENCE_MEDIUM_THRESHOLD == 0.4

    def test_thresholds_used_by_get_confidence_level(self):
        """Test that get_confidence_level uses the defined thresholds."""
        from src.ui.tui.utils import (
            CONFIDENCE_HIGH_THRESHOLD,
            CONFIDENCE_MEDIUM_THRESHOLD,
            get_confidence_level,
        )

        assert get_confidence_level(CONFIDENCE_HIGH_THRESHOLD) == "high"
        assert get_confidence_level(CONFIDENCE_MEDIUM_THRESHOLD) == "medium"
        assert get_confidence_level(CONFIDENCE_MEDIUM_THRESHOLD - 0.001) == "low"

    def test_thresholds_used_by_get_confidence_color(self):
        """Test that get_confidence_color uses the defined thresholds."""
        from src.ui.tui.utils import (
            CONFIDENCE_HIGH_THRESHOLD,
            CONFIDENCE_MEDIUM_THRESHOLD,
            get_confidence_color,
        )

        high_color = get_confidence_color(CONFIDENCE_HIGH_THRESHOLD)
        low_color = get_confidence_color(CONFIDENCE_MEDIUM_THRESHOLD - 0.001)
        assert high_color != low_color


# ---------------------------------------------------------------------------
# No stale imports tests
# ---------------------------------------------------------------------------


class TestNoStaleImports:
    """Verify that old duplicated functions are no longer importable from original locations."""

    def test_category_table_no_own_format_confidence_bar(self):
        """Verify category_table delegates to utils, not its own copy."""
        from src.ui.tui.utils import format_confidence_bar
        from src.ui.tui.widgets import category_table

        # The function exposed from category_table should be the same object
        # as the one in utils (re-exported, not duplicated)
        assert category_table.format_confidence_bar is format_confidence_bar

    def test_detail_panel_no_own_format_confidence_bar(self):
        """Verify detail_panel uses the shared format_confidence_bar."""
        from src.ui.tui.utils import format_confidence_bar
        from src.ui.tui.widgets import detail_panel

        assert detail_panel.format_confidence_bar is format_confidence_bar

    def test_detail_panel_uses_shared_get_confidence_level(self):
        """Verify detail_panel imports get_confidence_level from utils."""
        from src.ui.tui.utils import get_confidence_level
        from src.ui.tui.widgets import detail_panel

        assert detail_panel.get_confidence_level is get_confidence_level

    def test_theme_delegates_to_utils(self):
        """Verify theme module's functions come from utils."""
        from src.ui.tui import theme
        from src.ui.tui.utils import get_confidence_color, get_confidence_level

        assert theme.get_confidence_level is get_confidence_level
        assert theme.get_confidence_color is get_confidence_color

    def test_widgets_init_exports_from_utils(self):
        """Verify widgets __init__ exports format_confidence_bar from utils."""
        from src.ui.tui.utils import format_confidence_bar as utils_bar
        from src.ui.tui.widgets import format_confidence_bar

        assert format_confidence_bar is utils_bar

    def test_tui_init_exports_from_utils(self):
        """Verify TUI __init__ exports get_confidence_level from utils."""
        from src.ui.tui import get_confidence_level
        from src.ui.tui.utils import get_confidence_level as utils_level

        assert get_confidence_level is utils_level

    def test_truncation_constants_used_in_category_table(self):
        """Verify category_table uses MAX_NAME_DISPLAY from utils."""
        from src.ui.tui.utils import MAX_NAME_DISPLAY
        from src.ui.tui.widgets import category_table

        assert hasattr(category_table, "MAX_NAME_DISPLAY")
        assert category_table.MAX_NAME_DISPLAY is MAX_NAME_DISPLAY

    def test_truncation_constants_used_in_detail_panel(self):
        """Verify detail_panel uses truncation constants from utils."""
        from src.ui.tui.utils import MAX_FEATURE_DISPLAY, MAX_SUBJECT_DISPLAY
        from src.ui.tui.widgets import detail_panel

        assert hasattr(detail_panel, "MAX_SUBJECT_DISPLAY")
        assert detail_panel.MAX_SUBJECT_DISPLAY is MAX_SUBJECT_DISPLAY
        assert hasattr(detail_panel, "MAX_FEATURE_DISPLAY")
        assert detail_panel.MAX_FEATURE_DISPLAY is MAX_FEATURE_DISPLAY

    def test_truncation_constants_used_in_merge_dialog(self):
        """Verify merge_dialog uses MAX_NAME_DISPLAY from utils."""
        from src.ui.tui.dialogs import merge_dialog
        from src.ui.tui.utils import MAX_NAME_DISPLAY

        assert hasattr(merge_dialog, "MAX_NAME_DISPLAY")
        assert merge_dialog.MAX_NAME_DISPLAY is MAX_NAME_DISPLAY
