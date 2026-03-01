"""
TUI package for Category Review.

Provides a terminal-based user interface for reviewing email category suggestions.
"""

from src.ui.tui.app import ReviewApp
from src.ui.tui.commands import (
    Command,
    format_command_help,
    get_all_commands,
)
from src.ui.tui.state import ReviewState
from src.ui.tui.theme import (
    CONFIDENCE_COLORS,
    THEME_COLORS,
    get_confidence_color,
    get_confidence_level,
)

__all__ = [
    "ReviewApp",
    "ReviewState",
    "THEME_COLORS",
    "CONFIDENCE_COLORS",
    "get_confidence_color",
    "get_confidence_level",
    "Command",
    "get_all_commands",
    "format_command_help",
]
