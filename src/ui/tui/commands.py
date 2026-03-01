"""
Command definitions for the TUI application.

Defines keyboard commands and their associated actions.
"""

from dataclasses import dataclass


@dataclass
class Command:
    """Represents a keyboard command in the TUI."""

    key: str
    description: str
    action: str


# Default commands for category review
DEFAULT_COMMANDS = [
    Command(key="a", description="Accept category", action="accept"),
    Command(key="r", description="Rename category", action="rename"),
    Command(key="m", description="Merge with another", action="merge"),
    Command(key="d", description="Delete category", action="delete"),
    Command(key="s", description="Skip for now", action="skip"),
    Command(key="?", description="Show help", action="help"),
    Command(key="q", description="Quit", action="quit"),
]


def get_all_commands() -> list[Command]:
    """
    Get all available commands.

    Returns:
        List of Command objects
    """
    return DEFAULT_COMMANDS.copy()


def format_command_help() -> str:
    """
    Format all commands as help text.

    Returns:
        Formatted help string
    """
    lines = ["Available Commands:", ""]
    for cmd in DEFAULT_COMMANDS:
        lines.append(f"  [{cmd.key.upper()}] {cmd.description}")
    lines.append("")
    lines.append("Navigation:")
    lines.append("  [j/Down] Move down")
    lines.append("  [k/Up] Move up")
    lines.append("  [Enter] Select")
    return "\n".join(lines)
