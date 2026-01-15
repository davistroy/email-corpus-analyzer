"""
Action bar widget for the TUI application.

Displays available keyboard commands at the bottom of the screen.
"""
from textual.reactive import reactive
from textual.widgets import Static

# Command display mapping
COMMANDS = {
    "A": "Accept",
    "R": "Rename",
    "M": "Merge",
    "D": "Delete",
    "S": "Skip",
    "?": "Help",
    "Q": "Quit",
}


class ActionBar(Static):
    """
    A bar widget displaying available keyboard commands.

    Shows commands with their keyboard shortcuts.
    Supports enabling/disabling commands contextually.
    """

    _merge_enabled: reactive[bool] = reactive(True)

    def __init__(self, *args, **kwargs):
        """Initialize the action bar."""
        super().__init__(*args, **kwargs)
        self._update_content()

    def _update_content(self) -> None:
        """Update the displayed content."""
        parts = []

        for key, label in COMMANDS.items():
            if key == "M" and not self._merge_enabled:
                # Show disabled merge command
                parts.append(f"[dim][{key}]{label}[/dim]")
            else:
                parts.append(f"[b][{key}][/b]{label}")

        content = "  ".join(parts)
        self.update(content)

    def set_merge_enabled(self, enabled: bool) -> None:
        """
        Enable or disable the merge command.

        Args:
            enabled: Whether merge should be enabled
        """
        self._merge_enabled = enabled
        self._update_content()

    def is_merge_enabled(self) -> bool:
        """
        Check if merge command is enabled.

        Returns:
            True if merge is enabled
        """
        return self._merge_enabled

    def watch__merge_enabled(self, enabled: bool) -> None:
        """React to merge enabled state changes."""
        self._update_content()

    def get_command_label(self, key: str) -> str | None:
        """
        Get the label for a command key.

        Args:
            key: Command key (e.g., "A")

        Returns:
            Command label or None
        """
        return COMMANDS.get(key.upper())


class HelpOverlay(Static):
    """
    A help overlay showing all available commands.

    Displays when user presses ? key.
    """

    def __init__(self, *args, **kwargs):
        """Initialize the help overlay."""
        super().__init__(*args, **kwargs)
        self._build_content()

    def _build_content(self) -> None:
        """Build the help content."""
        lines = [
            "[b]Category Review Help[/b]",
            "",
            "[u]Actions[/u]",
            "  [b]A[/b] - Accept: Approve this category as-is",
            "  [b]R[/b] - Rename: Change the category name",
            "  [b]M[/b] - Merge: Combine with another approved category",
            "  [b]D[/b] - Delete: Remove this category",
            "  [b]S[/b] - Skip: Review later",
            "",
            "[u]Navigation[/u]",
            "  [b]j/Down[/b] - Move down",
            "  [b]k/Up[/b] - Move up",
            "  [b]Enter[/b] - Confirm selection",
            "",
            "[u]Other[/u]",
            "  [b]?/F1[/b] - Show this help",
            "  [b]Q/Ctrl+C[/b] - Quit (with confirmation)",
            "",
            "Press any key to close this help.",
        ]
        self.update("\n".join(lines))
