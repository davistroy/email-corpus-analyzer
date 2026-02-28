"""
Theme configuration for the TUI application.

Defines colors, styles, and visual theming for the Category Review TUI.

Confidence utility functions (get_confidence_color, get_confidence_level)
and threshold constants are delegated to src.ui.tui.utils — re-exported
here for backward compatibility.
"""

from src.ui.tui.utils import (
    CONFIDENCE_COLORS,
    CONFIDENCE_HIGH_THRESHOLD,
    CONFIDENCE_MEDIUM_THRESHOLD,
    get_confidence_color,
    get_confidence_level,
)

# Main theme colors
THEME_COLORS = {
    "primary": "#007acc",  # Blue - primary actions
    "secondary": "#6c757d",  # Gray - secondary elements
    "success": "#28a745",  # Green - success/accept
    "warning": "#ffc107",  # Yellow - warning/medium
    "danger": "#dc3545",  # Red - danger/delete/low
    "info": "#17a2b8",  # Cyan - info
    "background": "#1e1e1e",  # Dark background
    "surface": "#252526",  # Surface color
    "text": "#d4d4d4",  # Default text
    "text_muted": "#808080",  # Muted text
    "border": "#3c3c3c",  # Border color
    "highlight": "#264f78",  # Selection highlight
}

# Re-export for backward compatibility — these are now defined in utils.py
__all__ = [
    "THEME_COLORS",
    "CONFIDENCE_COLORS",
    "CONFIDENCE_HIGH_THRESHOLD",
    "CONFIDENCE_MEDIUM_THRESHOLD",
    "get_confidence_color",
    "get_confidence_level",
    "APP_CSS",
]

# CSS styles for the TUI application
APP_CSS = """
Screen {
    background: $surface;
}

#main-container {
    layout: horizontal;
}

#category-list {
    width: 3fr;
    min-width: 30;
    border: solid $primary;
    border-title-color: $primary;
    overflow-y: auto;
}

#detail-container {
    width: 2fr;
    min-width: 25;
    overflow-y: auto;
}

#detail-panel {
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
    color: $error;
}

.selected {
    background: $accent;
}

.header {
    text-style: bold;
    color: $text;
}

.muted {
    color: $text-muted;
}

DataTable > .datatable--cursor {
    background: $accent;
}

DataTable > .datatable--header {
    text-style: bold;
    background: $surface;
}

#stats-panel {
    height: auto;
    max-height: 14;
    padding: 0 1;
    border-top: solid $border;
}

#too-small-message {
    align: center middle;
    text-align: center;
    width: 100%;
    height: 100%;
    color: $warning;
    text-style: bold;
}
"""
