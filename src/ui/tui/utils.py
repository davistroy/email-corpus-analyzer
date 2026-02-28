"""
Centralized TUI utility functions.

Phase 2, Item 1.1: Shared utilities extracted from duplicated code across
category_table.py, detail_panel.py, and theme.py.

Phase 2, Item 2.4: Added accessibility features:
- Confidence symbols (get_confidence_symbol) for color-blind users
- Accessible mode state (is_accessible_mode, set_accessible_mode, toggle_accessible_mode)
- High-contrast mode state (is_high_contrast_mode, set_high_contrast_mode, toggle_high_contrast_mode)
- format_confidence_bar accessible parameter to include symbols/text labels

This module is the single source of truth for:
- format_confidence_bar() - visual confidence bar rendering
- get_confidence_level() - confidence level classification
- get_confidence_color() - confidence level color mapping
- get_confidence_symbol() - confidence level symbol mapping
- Truncation constants for display widths
- Confidence threshold constants
- Accessibility mode state
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Confidence thresholds (formerly in theme.py only)
# ---------------------------------------------------------------------------

CONFIDENCE_HIGH_THRESHOLD: float = 0.7
CONFIDENCE_MEDIUM_THRESHOLD: float = 0.4

# ---------------------------------------------------------------------------
# Display truncation constants (formerly hardcoded magic numbers)
# ---------------------------------------------------------------------------

MAX_NAME_DISPLAY: int = 28
"""Maximum characters for category name display in tables."""

MAX_SUBJECT_DISPLAY: int = 50
"""Maximum characters for email subject display."""

MAX_FEATURE_DISPLAY: int = 70
"""Maximum characters for distinguishing feature display."""

# ---------------------------------------------------------------------------
# Confidence colors (hex values for Rich/Textual markup)
# ---------------------------------------------------------------------------

CONFIDENCE_COLORS: dict[str, str] = {
    "high": "#28a745",  # Green - >= CONFIDENCE_HIGH_THRESHOLD
    "medium": "#ffc107",  # Yellow - >= CONFIDENCE_MEDIUM_THRESHOLD
    "low": "#dc3545",  # Red - < CONFIDENCE_MEDIUM_THRESHOLD
}

# ---------------------------------------------------------------------------
# Confidence symbols for accessibility (Phase 2, Item 2.4)
# ---------------------------------------------------------------------------

CONFIDENCE_SYMBOLS: dict[str, str] = {
    "high": "\u25cf",  # ● Filled circle — high confidence
    "medium": "\u25d0",  # ◐ Half circle — medium confidence
    "low": "\u25cb",  # ○ Open circle — low confidence
}
"""Unicode symbols conveying confidence level without relying on color."""

# ---------------------------------------------------------------------------
# Accessibility mode state (Phase 2, Item 2.4)
# ---------------------------------------------------------------------------

_accessible_mode: bool = False
"""Module-level flag for accessible mode (symbols alongside colors)."""

_high_contrast_mode: bool = False
"""Module-level flag for high-contrast mode (bold text, high-contrast colors)."""


def is_accessible_mode() -> bool:
    """Check whether accessible mode is active."""
    return _accessible_mode


def set_accessible_mode(enabled: bool) -> None:
    """Enable or disable accessible mode."""
    global _accessible_mode
    _accessible_mode = enabled


def toggle_accessible_mode() -> bool:
    """Toggle accessible mode and return the new state."""
    global _accessible_mode
    _accessible_mode = not _accessible_mode
    return _accessible_mode


def is_high_contrast_mode() -> bool:
    """Check whether high-contrast mode is active."""
    return _high_contrast_mode


def set_high_contrast_mode(enabled: bool) -> None:
    """Enable or disable high-contrast mode.

    Enabling high-contrast mode also enables accessible mode,
    because HC mode implies the user benefits from non-color cues.
    """
    global _high_contrast_mode, _accessible_mode
    _high_contrast_mode = enabled
    if enabled:
        _accessible_mode = True


def toggle_high_contrast_mode() -> bool:
    """Toggle high-contrast mode and return the new state."""
    global _high_contrast_mode, _accessible_mode
    _high_contrast_mode = not _high_contrast_mode
    if _high_contrast_mode:
        _accessible_mode = True
    return _high_contrast_mode


# ---------------------------------------------------------------------------
# Confidence utility functions
# ---------------------------------------------------------------------------


def get_confidence_level(confidence: float) -> str:
    """
    Classify a confidence value into a named level.

    Args:
        confidence: Confidence value (typically 0.0 to 1.0)

    Returns:
        "high", "medium", or "low"
    """
    if confidence >= CONFIDENCE_HIGH_THRESHOLD:
        return "high"
    if confidence >= CONFIDENCE_MEDIUM_THRESHOLD:
        return "medium"
    return "low"


def get_confidence_color(confidence: float) -> str:
    """
    Get the hex color string for a confidence value.

    Args:
        confidence: Confidence value (typically 0.0 to 1.0)

    Returns:
        Hex color string (e.g. "#28a745")
    """
    level = get_confidence_level(confidence)
    return CONFIDENCE_COLORS[level]


def get_confidence_symbol(confidence: float) -> str:
    """
    Get the Unicode symbol for a confidence value.

    Returns a distinct symbol per level so confidence information
    is conveyed without relying on color alone.

    Args:
        confidence: Confidence value (typically 0.0 to 1.0)

    Returns:
        Unicode symbol string (e.g. "●" for high)
    """
    level = get_confidence_level(confidence)
    return CONFIDENCE_SYMBOLS[level]


def get_active_confidence_colors() -> dict[str, str]:
    """
    Return the confidence color mapping for the current mode.

    In normal mode returns CONFIDENCE_COLORS; in high-contrast mode
    returns HIGH_CONTRAST_CONFIDENCE_COLORS from theme.

    Returns:
        Dict mapping "high"/"medium"/"low" to hex color strings.
    """
    if _high_contrast_mode:
        from src.ui.tui.theme import HIGH_CONTRAST_CONFIDENCE_COLORS

        return HIGH_CONTRAST_CONFIDENCE_COLORS
    return CONFIDENCE_COLORS


def format_confidence_bar(
    confidence: float,
    width: int = 10,
    *,
    colored: bool = False,
    accessible: bool = False,
) -> str:
    """
    Render a confidence score as a visual bar with optional Rich color markup.

    This is the single implementation replacing the two divergent copies that
    previously lived in category_table.py and detail_panel.py.

    Phase 2 Item 2.4: Added ``accessible`` parameter. When True, the bar
    includes a confidence symbol and a text label (e.g. "HIGH") so that
    information is not conveyed by color alone.

    Args:
        confidence: Score value (clamped to 0.0-1.0)
        width: Number of block characters in the bar
        colored: If True, wrap filled portion in Rich color markup
                 (green/yellow/red based on confidence thresholds).
                 If False (default), return plain Unicode with percentage.
        accessible: If True, prepend a confidence symbol and append a
                    text label (e.g. "● HIGH") alongside the bar.

    Returns:
        String like "████████░░ 85%" (plain) or
        "[green]████████[/green]░░ 85%" (colored) or
        "● ████████░░ 85% HIGH" (accessible)
    """
    confidence = max(0.0, min(1.0, confidence))
    filled = int(confidence * width)
    empty = width - filled

    filled_char = "\u2588"  # Full block
    empty_char = "\u2591"  # Light shade

    filled_str = filled_char * filled
    empty_str = empty_char * empty
    percentage = f"{confidence * 100:.0f}%"

    if colored:
        level = get_confidence_level(confidence)
        color = {"high": "green", "medium": "yellow", "low": "red"}[level]
        bar = f"[{color}]{filled_str}[/{color}]{empty_str} {percentage}"
    else:
        bar = f"{filled_str}{empty_str} {percentage}"

    if accessible:
        level = get_confidence_level(confidence)
        symbol = CONFIDENCE_SYMBOLS[level]
        label = level.upper()
        bar = f"{symbol} {bar} {label}"

    return bar
