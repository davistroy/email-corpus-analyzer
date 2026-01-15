"""
TUI widgets package.

Provides reusable widgets for the Category Review TUI.
"""
from src.ui.tui.widgets.action_bar import COMMANDS, ActionBar, HelpOverlay
from src.ui.tui.widgets.category_table import (
    TABLE_COLUMNS,
    CategoryTable,
    format_confidence_bar,
    format_email_count,
    format_source,
)
from src.ui.tui.widgets.detail_panel import DetailPanel
from src.ui.tui.widgets.progress_bar import ProgressBar
from src.ui.tui.widgets.stats_panel import StatsPanel

__all__ = [
    "CategoryTable",
    "TABLE_COLUMNS",
    "format_confidence_bar",
    "format_source",
    "format_email_count",
    "DetailPanel",
    "ActionBar",
    "HelpOverlay",
    "COMMANDS",
    "ProgressBar",
    "StatsPanel",
]
