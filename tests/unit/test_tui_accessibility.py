"""
Tests for TUI accessibility improvements.

Phase 2, Item 2.4: Accessibility improvements.
Tests written first per TDD constitution.

Covers:
- High-contrast mode toggle and style application
- Confidence symbols (alongside colors) for color-blind users
- format_confidence_bar with accessible mode (symbols in output)
- Focus indicator CSS classes
- Mode indicator updates on state change
- ActionBar contextual updates (e.g., merge disabled when no approved)
"""

# ===========================================================================
# Confidence Symbols
# ===========================================================================


class TestConfidenceSymbols:
    """Test that confidence symbols are defined and map correctly to levels."""

    def test_confidence_symbols_defined(self):
        """Test that CONFIDENCE_SYMBOLS dict exists with high/medium/low keys."""
        from src.ui.tui.utils import CONFIDENCE_SYMBOLS

        assert "high" in CONFIDENCE_SYMBOLS
        assert "medium" in CONFIDENCE_SYMBOLS
        assert "low" in CONFIDENCE_SYMBOLS

    def test_confidence_symbols_are_distinct(self):
        """Test that each level has a distinct symbol."""
        from src.ui.tui.utils import CONFIDENCE_SYMBOLS

        symbols = list(CONFIDENCE_SYMBOLS.values())
        assert len(set(symbols)) == 3, "All three symbols must be distinct"

    def test_get_confidence_symbol_high(self):
        """Test that high confidence returns the high symbol."""
        from src.ui.tui.utils import CONFIDENCE_SYMBOLS, get_confidence_symbol

        assert get_confidence_symbol(0.9) == CONFIDENCE_SYMBOLS["high"]
        assert get_confidence_symbol(0.7) == CONFIDENCE_SYMBOLS["high"]

    def test_get_confidence_symbol_medium(self):
        """Test that medium confidence returns the medium symbol."""
        from src.ui.tui.utils import CONFIDENCE_SYMBOLS, get_confidence_symbol

        assert get_confidence_symbol(0.5) == CONFIDENCE_SYMBOLS["medium"]
        assert get_confidence_symbol(0.4) == CONFIDENCE_SYMBOLS["medium"]

    def test_get_confidence_symbol_low(self):
        """Test that low confidence returns the low symbol."""
        from src.ui.tui.utils import CONFIDENCE_SYMBOLS, get_confidence_symbol

        assert get_confidence_symbol(0.2) == CONFIDENCE_SYMBOLS["low"]
        assert get_confidence_symbol(0.0) == CONFIDENCE_SYMBOLS["low"]

    def test_get_confidence_symbol_boundary_0_7(self):
        """Test exact boundary at 0.7."""
        from src.ui.tui.utils import get_confidence_symbol

        sym_at = get_confidence_symbol(0.7)
        sym_below = get_confidence_symbol(0.6999)
        assert sym_at != sym_below

    def test_get_confidence_symbol_boundary_0_4(self):
        """Test exact boundary at 0.4."""
        from src.ui.tui.utils import get_confidence_symbol

        sym_at = get_confidence_symbol(0.4)
        sym_below = get_confidence_symbol(0.3999)
        assert sym_at != sym_below


# ===========================================================================
# format_confidence_bar with accessible mode
# ===========================================================================


class TestFormatConfidenceBarAccessible:
    """Test format_confidence_bar with accessible=True adds symbols."""

    def test_accessible_bar_contains_symbol_high(self):
        """Test that accessible mode includes the high confidence symbol."""
        from src.ui.tui.utils import CONFIDENCE_SYMBOLS, format_confidence_bar

        bar = format_confidence_bar(0.85, width=10, accessible=True)
        assert CONFIDENCE_SYMBOLS["high"] in bar

    def test_accessible_bar_contains_symbol_medium(self):
        """Test that accessible mode includes the medium confidence symbol."""
        from src.ui.tui.utils import CONFIDENCE_SYMBOLS, format_confidence_bar

        bar = format_confidence_bar(0.5, width=10, accessible=True)
        assert CONFIDENCE_SYMBOLS["medium"] in bar

    def test_accessible_bar_contains_symbol_low(self):
        """Test that accessible mode includes the low confidence symbol."""
        from src.ui.tui.utils import CONFIDENCE_SYMBOLS, format_confidence_bar

        bar = format_confidence_bar(0.2, width=10, accessible=True)
        assert CONFIDENCE_SYMBOLS["low"] in bar

    def test_accessible_bar_still_has_percentage(self):
        """Test that accessible mode still includes percentage."""
        from src.ui.tui.utils import format_confidence_bar

        bar = format_confidence_bar(0.85, width=10, accessible=True)
        assert "85%" in bar

    def test_accessible_bar_still_has_blocks(self):
        """Test that accessible mode still has block chars."""
        from src.ui.tui.utils import format_confidence_bar

        bar = format_confidence_bar(0.5, width=10, accessible=True)
        assert "\u2588" in bar  # filled block
        assert "\u2591" in bar  # empty block

    def test_non_accessible_bar_has_no_symbol(self):
        """Test that default (non-accessible) mode has no confidence symbol."""
        from src.ui.tui.utils import CONFIDENCE_SYMBOLS, format_confidence_bar

        bar = format_confidence_bar(0.85, width=10)
        for sym in CONFIDENCE_SYMBOLS.values():
            assert sym not in bar

    def test_accessible_and_colored_together(self):
        """Test accessible mode combined with colored mode."""
        from src.ui.tui.utils import CONFIDENCE_SYMBOLS, format_confidence_bar

        bar = format_confidence_bar(0.85, width=10, colored=True, accessible=True)
        assert CONFIDENCE_SYMBOLS["high"] in bar
        assert "green" in bar
        assert "85%" in bar

    def test_accessible_bar_at_zero(self):
        """Test accessible mode at 0.0."""
        from src.ui.tui.utils import CONFIDENCE_SYMBOLS, format_confidence_bar

        bar = format_confidence_bar(0.0, width=10, accessible=True)
        assert CONFIDENCE_SYMBOLS["low"] in bar
        assert "0%" in bar

    def test_accessible_bar_at_one(self):
        """Test accessible mode at 1.0."""
        from src.ui.tui.utils import CONFIDENCE_SYMBOLS, format_confidence_bar

        bar = format_confidence_bar(1.0, width=10, accessible=True)
        assert CONFIDENCE_SYMBOLS["high"] in bar
        assert "100%" in bar

    def test_accessible_bar_contains_level_text(self):
        """Test that accessible mode includes the level text label (high/medium/low)."""
        from src.ui.tui.utils import format_confidence_bar

        bar_high = format_confidence_bar(0.85, width=10, accessible=True)
        assert "HIGH" in bar_high or "high" in bar_high.lower()

        bar_med = format_confidence_bar(0.5, width=10, accessible=True)
        assert "MED" in bar_med or "medium" in bar_med.lower()

        bar_low = format_confidence_bar(0.2, width=10, accessible=True)
        assert "LOW" in bar_low or "low" in bar_low.lower()


# ===========================================================================
# High Contrast Theme Colors
# ===========================================================================


class TestHighContrastTheme:
    """Test that high-contrast mode theme colors are defined and distinct."""

    def test_high_contrast_colors_defined(self):
        """Test that HIGH_CONTRAST_COLORS dict is defined."""
        from src.ui.tui.theme import HIGH_CONTRAST_COLORS

        assert isinstance(HIGH_CONTRAST_COLORS, dict)
        assert len(HIGH_CONTRAST_COLORS) > 0

    def test_high_contrast_has_required_keys(self):
        """Test that high-contrast colors include the same keys as THEME_COLORS."""
        from src.ui.tui.theme import HIGH_CONTRAST_COLORS, THEME_COLORS

        for key in THEME_COLORS:
            assert key in HIGH_CONTRAST_COLORS, f"Missing key: {key}"

    def test_high_contrast_colors_differ_from_normal(self):
        """Test that high-contrast colors are different from normal theme."""
        from src.ui.tui.theme import HIGH_CONTRAST_COLORS, THEME_COLORS

        # At least some colors should differ
        differ_count = sum(1 for k in THEME_COLORS if THEME_COLORS[k] != HIGH_CONTRAST_COLORS[k])
        assert differ_count > 0, "High contrast should differ from normal in at least some colors"

    def test_high_contrast_confidence_colors_defined(self):
        """Test that HIGH_CONTRAST_CONFIDENCE_COLORS dict is defined."""
        from src.ui.tui.theme import HIGH_CONTRAST_CONFIDENCE_COLORS

        assert "high" in HIGH_CONTRAST_CONFIDENCE_COLORS
        assert "medium" in HIGH_CONTRAST_CONFIDENCE_COLORS
        assert "low" in HIGH_CONTRAST_CONFIDENCE_COLORS

    def test_high_contrast_confidence_colors_are_distinct(self):
        """Test that all three HC confidence colors are distinct."""
        from src.ui.tui.theme import HIGH_CONTRAST_CONFIDENCE_COLORS

        colors = list(HIGH_CONTRAST_CONFIDENCE_COLORS.values())
        assert len(set(colors)) == 3


# ===========================================================================
# High Contrast CSS
# ===========================================================================


class TestHighContrastCSS:
    """Test that high-contrast CSS is defined and contains expected styles."""

    def test_high_contrast_css_defined(self):
        """Test that HIGH_CONTRAST_CSS string is defined."""
        from src.ui.tui.theme import HIGH_CONTRAST_CSS

        assert isinstance(HIGH_CONTRAST_CSS, str)
        assert len(HIGH_CONTRAST_CSS) > 0

    def test_high_contrast_css_has_bold(self):
        """Test that high-contrast CSS uses bold text."""
        from src.ui.tui.theme import HIGH_CONTRAST_CSS

        assert "bold" in HIGH_CONTRAST_CSS

    def test_high_contrast_css_has_focus_styles(self):
        """Test that high-contrast CSS includes focus indicator styles."""
        from src.ui.tui.theme import HIGH_CONTRAST_CSS

        # Focus styles should be present for clear visual focus ring
        assert ":focus" in HIGH_CONTRAST_CSS or "focus" in HIGH_CONTRAST_CSS.lower()


# ===========================================================================
# Focus Indicator CSS
# ===========================================================================


class TestFocusIndicatorCSS:
    """Test that focus indicator CSS is present in the standard APP_CSS."""

    def test_app_css_has_focus_styles(self):
        """Test that APP_CSS includes focus-within or :focus styles."""
        from src.ui.tui.theme import APP_CSS

        assert ":focus" in APP_CSS or "focus" in APP_CSS.lower()

    def test_focus_styles_have_border(self):
        """Test that focus styles change the border for visibility."""
        from src.ui.tui.theme import APP_CSS

        # Focus style should change border or outline
        assert "border" in APP_CSS.lower()


# ===========================================================================
# Accessibility State
# ===========================================================================


class TestAccessibilityState:
    """Test the accessibility state tracking in utils."""

    def test_default_accessible_mode_off(self):
        """Test that accessible mode is off by default."""
        from src.ui.tui.utils import is_accessible_mode

        # Default should be False
        assert is_accessible_mode() is False

    def test_set_accessible_mode_on(self):
        """Test enabling accessible mode."""
        from src.ui.tui.utils import is_accessible_mode, set_accessible_mode

        try:
            set_accessible_mode(True)
            assert is_accessible_mode() is True
        finally:
            set_accessible_mode(False)  # Reset

    def test_set_accessible_mode_off(self):
        """Test disabling accessible mode."""
        from src.ui.tui.utils import is_accessible_mode, set_accessible_mode

        set_accessible_mode(True)
        set_accessible_mode(False)
        assert is_accessible_mode() is False

    def test_toggle_accessible_mode(self):
        """Test toggling accessible mode."""
        from src.ui.tui.utils import is_accessible_mode, toggle_accessible_mode

        try:
            initial = is_accessible_mode()
            toggle_accessible_mode()
            assert is_accessible_mode() is not initial
            toggle_accessible_mode()
            assert is_accessible_mode() is initial
        finally:
            set_accessible_mode_cleanup()


# We need a helper to reset state after tests
def set_accessible_mode_cleanup():
    """Reset accessible mode to default."""
    from src.ui.tui.utils import set_accessible_mode

    set_accessible_mode(False)


# ===========================================================================
# High Contrast Mode Toggle
# ===========================================================================


class TestHighContrastModeToggle:
    """Test the high-contrast mode state tracking."""

    def test_default_high_contrast_off(self):
        """Test that high-contrast mode is off by default."""
        from src.ui.tui.utils import is_high_contrast_mode

        assert is_high_contrast_mode() is False

    def test_set_high_contrast_on(self):
        """Test enabling high-contrast mode."""
        from src.ui.tui.utils import is_high_contrast_mode, set_high_contrast_mode

        try:
            set_high_contrast_mode(True)
            assert is_high_contrast_mode() is True
        finally:
            set_high_contrast_mode(False)

    def test_toggle_high_contrast(self):
        """Test toggling high-contrast mode."""
        from src.ui.tui.utils import is_high_contrast_mode, toggle_high_contrast_mode

        try:
            initial = is_high_contrast_mode()
            toggle_high_contrast_mode()
            assert is_high_contrast_mode() is not initial
            toggle_high_contrast_mode()
            assert is_high_contrast_mode() is initial
        finally:
            from src.ui.tui.utils import set_high_contrast_mode

            set_high_contrast_mode(False)

    def test_high_contrast_enables_accessible_mode(self):
        """Test that enabling high-contrast mode also enables accessible mode."""
        from src.ui.tui.utils import (
            is_accessible_mode,
            set_accessible_mode,
            set_high_contrast_mode,
        )

        try:
            set_high_contrast_mode(True)
            assert is_accessible_mode() is True
        finally:
            set_high_contrast_mode(False)
            set_accessible_mode(False)


# ===========================================================================
# get_active_confidence_colors
# ===========================================================================


class TestGetActiveConfidenceColors:
    """Test that the active confidence colors change based on mode."""

    def test_normal_mode_returns_standard_colors(self):
        """Test that normal mode returns standard CONFIDENCE_COLORS."""
        from src.ui.tui.utils import (
            CONFIDENCE_COLORS,
            get_active_confidence_colors,
            set_high_contrast_mode,
        )

        try:
            set_high_contrast_mode(False)
            colors = get_active_confidence_colors()
            assert colors == CONFIDENCE_COLORS
        finally:
            set_high_contrast_mode(False)

    def test_high_contrast_returns_hc_colors(self):
        """Test that high-contrast mode returns HC confidence colors."""
        from src.ui.tui.theme import HIGH_CONTRAST_CONFIDENCE_COLORS
        from src.ui.tui.utils import get_active_confidence_colors, set_high_contrast_mode

        try:
            set_high_contrast_mode(True)
            colors = get_active_confidence_colors()
            assert colors == HIGH_CONTRAST_CONFIDENCE_COLORS
        finally:
            set_high_contrast_mode(False)


# ===========================================================================
# ActionBar mode indicator
# ===========================================================================


class TestActionBarModeIndicator:
    """Test that ActionBar shows current mode in its content."""

    def test_action_bar_shows_normal_mode(self):
        """Test that ActionBar content indicates Normal mode by default."""
        from src.ui.tui.widgets.action_bar import ActionBar

        bar = ActionBar()
        content = bar._get_content_text()
        # In normal mode with no selection, standard commands are shown
        assert "Accept" in content

    def test_action_bar_shows_selection_mode(self):
        """Test that ActionBar shows selection count when items selected."""
        from src.ui.tui.widgets.action_bar import ActionBar

        bar = ActionBar()
        bar.set_selection_count(3)
        content = bar._get_content_text()
        assert "3 selected" in content

    def test_action_bar_merge_disabled_indicator(self):
        """Test that ActionBar shows merge as disabled when no approved categories."""
        from src.ui.tui.widgets.action_bar import ActionBar

        bar = ActionBar()
        bar.set_merge_enabled(False)
        content = bar._get_content_text()
        # Merge key should still appear but action bar should render it differently
        assert "Merge" in content

    def test_action_bar_shows_mode_text(self):
        """Test that ActionBar shows mode text (Normal/Selecting/Filtering)."""
        from src.ui.tui.widgets.action_bar import ActionBar

        bar = ActionBar()
        bar.set_mode_text("Normal")
        content = bar._get_content_text()
        assert "Normal" in content

    def test_action_bar_mode_text_updates(self):
        """Test that mode text updates when set to different values."""
        from src.ui.tui.widgets.action_bar import ActionBar

        bar = ActionBar()
        bar.set_mode_text("Filtering")
        content = bar._get_content_text()
        assert "Filtering" in content

    def test_action_bar_mode_text_selecting(self):
        """Test mode text shows 'Selecting X' with count."""
        from src.ui.tui.widgets.action_bar import ActionBar

        bar = ActionBar()
        bar.set_mode_text("Selecting 5")
        content = bar._get_content_text()
        assert "Selecting 5" in content


# ===========================================================================
# Backward compatibility: existing format_confidence_bar behavior unaffected
# ===========================================================================


class TestBackwardCompatibility:
    """Ensure that existing format_confidence_bar behavior is unaffected."""

    def test_default_call_no_accessible_param_works(self):
        """Test that calling without accessible param still works."""
        from src.ui.tui.utils import format_confidence_bar

        bar = format_confidence_bar(0.5, width=10)
        assert "50%" in bar
        assert "\u2588" in bar

    def test_colored_call_still_works(self):
        """Test that colored=True still works without accessible."""
        from src.ui.tui.utils import format_confidence_bar

        bar = format_confidence_bar(0.8, width=10, colored=True)
        assert "green" in bar
        assert "80%" in bar

    def test_theme_re_exports_unchanged(self):
        """Test that theme.py re-exports are unchanged."""
        from src.ui.tui.theme import (
            CONFIDENCE_COLORS,
            CONFIDENCE_HIGH_THRESHOLD,
            CONFIDENCE_MEDIUM_THRESHOLD,
            get_confidence_color,
            get_confidence_level,
        )

        assert CONFIDENCE_HIGH_THRESHOLD == 0.7
        assert CONFIDENCE_MEDIUM_THRESHOLD == 0.4
        assert get_confidence_level(0.9) == "high"
        assert isinstance(get_confidence_color(0.5), str)
        assert isinstance(CONFIDENCE_COLORS, dict)
