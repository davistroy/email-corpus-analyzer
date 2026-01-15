"""
Theme configuration for the TUI application.

Defines colors, styles, and visual theming for the Category Review TUI.
"""

# Main theme colors
THEME_COLORS = {
    "primary": "#007acc",        # Blue - primary actions
    "secondary": "#6c757d",      # Gray - secondary elements
    "success": "#28a745",        # Green - success/accept
    "warning": "#ffc107",        # Yellow - warning/medium
    "danger": "#dc3545",         # Red - danger/delete/low
    "info": "#17a2b8",           # Cyan - info
    "background": "#1e1e1e",     # Dark background
    "surface": "#252526",        # Surface color
    "text": "#d4d4d4",           # Default text
    "text_muted": "#808080",     # Muted text
    "border": "#3c3c3c",         # Border color
    "highlight": "#264f78",      # Selection highlight
}

# Confidence level colors (red/yellow/green)
CONFIDENCE_COLORS = {
    "high": "#28a745",      # Green - >= 0.7
    "medium": "#ffc107",    # Yellow - 0.4 to 0.7
    "low": "#dc3545",       # Red - < 0.4
}

# Confidence thresholds
CONFIDENCE_HIGH_THRESHOLD = 0.7
CONFIDENCE_MEDIUM_THRESHOLD = 0.4


def get_confidence_color(confidence: float) -> str:
    """
    Get the appropriate color for a confidence value.

    Args:
        confidence: Confidence value between 0 and 1

    Returns:
        Color hex string for the confidence level
    """
    if confidence >= CONFIDENCE_HIGH_THRESHOLD:
        return CONFIDENCE_COLORS["high"]
    if confidence >= CONFIDENCE_MEDIUM_THRESHOLD:
        return CONFIDENCE_COLORS["medium"]
    return CONFIDENCE_COLORS["low"]


def get_confidence_level(confidence: float) -> str:
    """
    Get the confidence level name.

    Args:
        confidence: Confidence value between 0 and 1

    Returns:
        String: "high", "medium", or "low"
    """
    if confidence >= CONFIDENCE_HIGH_THRESHOLD:
        return "high"
    if confidence >= CONFIDENCE_MEDIUM_THRESHOLD:
        return "medium"
    return "low"


# CSS styles for the TUI application
APP_CSS = """
Screen {
    background: $surface;
}

#main-container {
    layout: horizontal;
}

#category-list {
    width: 60%;
    border: solid $primary;
    border-title-color: $primary;
}

#detail-panel {
    width: 40%;
    border: solid $secondary;
    border-title-color: $secondary;
}

#action-bar {
    dock: bottom;
    height: 3;
    background: $surface;
    border-top: solid $border;
}

.confidence-high {
    color: $success;
}

.confidence-medium {
    color: $warning;
}

.confidence-low {
    color: $danger;
}

.selected {
    background: $highlight;
}

.header {
    text-style: bold;
    color: $text;
}

.muted {
    color: $text-muted;
}

DataTable > .datatable--cursor {
    background: $highlight;
}

DataTable > .datatable--header {
    text-style: bold;
    background: $surface;
}
"""
