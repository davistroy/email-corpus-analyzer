"""
Theme configuration for the TUI application.

Defines colors, styles, and visual theming for the Category Review TUI.

Confidence utility functions (get_confidence_color, get_confidence_level)
and threshold constants are delegated to src.ui.tui.utils -- re-exported
here for backward compatibility.

Phase 2, Item 2.4: Added high-contrast mode colors, high-contrast
confidence colors, high-contrast CSS, and focus indicator CSS.
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

# ---------------------------------------------------------------------------
# High-contrast mode colors (Phase 2, Item 2.4)
# ---------------------------------------------------------------------------

HIGH_CONTRAST_COLORS = {
    "primary": "#ffff00",  # Bright yellow — high visibility
    "secondary": "#ffffff",  # White — clearly visible on black
    "success": "#00ff00",  # Bright green — high visibility
    "warning": "#ffff00",  # Bright yellow
    "danger": "#ff0000",  # Bright red
    "info": "#00ffff",  # Bright cyan
    "background": "#000000",  # Pure black background
    "surface": "#000000",  # Pure black surface
    "text": "#ffffff",  # Pure white text
    "text_muted": "#c0c0c0",  # Light gray (still visible on black)
    "border": "#ffffff",  # White borders for maximum contrast
    "highlight": "#ffff00",  # Bright yellow highlight
}
"""High-contrast color palette: bright colors on pure black for maximum readability."""

HIGH_CONTRAST_CONFIDENCE_COLORS: dict[str, str] = {
    "high": "#00ff00",  # Bright green
    "medium": "#ffff00",  # Bright yellow
    "low": "#ff0000",  # Bright red
}
"""High-contrast confidence colors — brighter and more distinguishable than normal."""

# Re-export for backward compatibility — these are now defined in utils.py
__all__ = [
    "THEME_COLORS",
    "HIGH_CONTRAST_COLORS",
    "HIGH_CONTRAST_CONFIDENCE_COLORS",
    "CONFIDENCE_COLORS",
    "CONFIDENCE_HIGH_THRESHOLD",
    "CONFIDENCE_MEDIUM_THRESHOLD",
    "get_confidence_color",
    "get_confidence_level",
    "APP_CSS",
    "HIGH_CONTRAST_CSS",
]

# CSS styles for the TUI application
# Phase 2 Item 2.4: Added :focus-within and :focus styles for clear focus ring
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

#category-list:focus-within {
    border: double $accent;
    border-title-color: $accent;
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

#detail-panel:focus-within {
    border: double $accent;
    border-title-color: $accent;
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

DataTable:focus {
    border: double $accent;
}

DataTable > .datatable--cursor {
    background: $accent;
}

DataTable > .datatable--header {
    text-style: bold;
    background: $surface;
}

#search-input:focus {
    border: double $accent;
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

/* -----------------------------------------------------------------------
   High-contrast mode (Phase 2, Item 2.4)
   Activated via .high-contrast class on the App widget (Ctrl+H toggle).
   ----------------------------------------------------------------------- */

.high-contrast {
    background: #000000;
}

.high-contrast #category-list {
    border: solid #ffffff;
    border-title-color: #ffff00;
}

.high-contrast #category-list:focus-within {
    border: double #ffff00;
}

.high-contrast #detail-panel {
    border: solid #ffffff;
    border-title-color: #ffffff;
}

.high-contrast #detail-panel:focus-within {
    border: double #ffff00;
}

.high-contrast .confidence-high {
    color: #00ff00;
    text-style: bold;
}

.high-contrast .confidence-medium {
    color: #ffff00;
    text-style: bold;
}

.high-contrast .confidence-low {
    color: #ff0000;
    text-style: bold;
}

.high-contrast DataTable:focus {
    border: double #ffff00;
}

.high-contrast DataTable > .datatable--cursor {
    background: #ffff00;
    color: #000000;
    text-style: bold;
}

.high-contrast DataTable > .datatable--header {
    text-style: bold;
    background: #000000;
    color: #ffffff;
}

.high-contrast #search-input:focus {
    border: double #ffff00;
}

.high-contrast #action-bar {
    background: #000000;
    border-top: solid #ffffff;
    text-style: bold;
}

.high-contrast #stats-panel {
    border-top: solid #ffffff;
    text-style: bold;
}
"""

# ---------------------------------------------------------------------------
# High-contrast CSS overlay (Phase 2, Item 2.4)
# ---------------------------------------------------------------------------

HIGH_CONTRAST_CSS = """
Screen {
    background: #000000;
}

#main-container {
    layout: horizontal;
}

#category-list {
    border: solid #ffffff;
    border-title-color: #ffff00;
}

#category-list:focus-within {
    border: double #ffff00;
    border-title-color: #ffff00;
}

#detail-panel {
    border: solid #ffffff;
    border-title-color: #ffffff;
}

#detail-panel:focus-within {
    border: double #ffff00;
    border-title-color: #ffff00;
}

.header {
    text-style: bold;
    color: #ffffff;
}

.muted {
    color: #c0c0c0;
}

.confidence-high {
    color: #00ff00;
    text-style: bold;
}

.confidence-medium {
    color: #ffff00;
    text-style: bold;
}

.confidence-low {
    color: #ff0000;
    text-style: bold;
}

DataTable:focus {
    border: double #ffff00;
}

DataTable > .datatable--cursor {
    background: #ffff00;
    color: #000000;
    text-style: bold;
}

DataTable > .datatable--header {
    text-style: bold;
    background: #000000;
    color: #ffffff;
}

#search-input:focus {
    border: double #ffff00;
}

#action-bar {
    background: #000000;
    border-top: solid #ffffff;
    text-style: bold;
}

#stats-panel {
    border-top: solid #ffffff;
    text-style: bold;
}
"""
