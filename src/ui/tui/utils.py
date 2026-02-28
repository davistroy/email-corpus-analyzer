"""
Centralized TUI utility functions.

Phase 2, Item 1.1: Shared utilities extracted from duplicated code across
category_table.py, detail_panel.py, and theme.py.

This module is the single source of truth for:
- format_confidence_bar() - visual confidence bar rendering
- get_confidence_level() - confidence level classification
- get_confidence_color() - confidence level color mapping
- Truncation constants for display widths
- Confidence threshold constants
"""

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


def format_confidence_bar(
    confidence: float,
    width: int = 10,
    *,
    colored: bool = False,
) -> str:
    """
    Render a confidence score as a visual bar with optional Rich color markup.

    This is the single implementation replacing the two divergent copies that
    previously lived in category_table.py and detail_panel.py.

    Args:
        confidence: Score value (clamped to 0.0-1.0)
        width: Number of block characters in the bar
        colored: If True, wrap filled portion in Rich color markup
                 (green/yellow/red based on confidence thresholds).
                 If False (default), return plain Unicode with percentage.

    Returns:
        String like "████████░░ 85%" (plain) or
        "[green]████████[/green]░░ 85%" (colored)
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
        return f"[{color}]{filled_str}[/{color}]{empty_str} {percentage}"

    return f"{filled_str}{empty_str} {percentage}"
