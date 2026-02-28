"""
Action bar widget for the TUI application.

Displays available keyboard commands at the bottom of the screen.
Phase 2 Item 2.2: Added selection count display and bulk action hints.
Phase 2 Item 2.4: Added mode text indicator (Normal/Filtering/Selecting X).
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

    merge_enabled: reactive[bool] = reactive(True)

    def __init__(self, *args, **kwargs):
        """Initialize the action bar."""
        super().__init__(*args, **kwargs)
        self._selection_count: int = 0
        self._mode_text: str = "Normal"
        self._update_content()

    def _update_content(self) -> None:
        """Update the displayed content."""
        parts = []

        # Mode indicator (Phase 2 Item 2.4)
        parts.append(f"[b]{self._mode_text}[/b]")
        parts.append("|")

        if self._selection_count > 0:
            # Selection mode: show selection count and bulk action hints
            parts.append(f"[b]{self._selection_count} selected[/b]")
            parts.append("[b][Shift+A][/b]Bulk Accept")
            parts.append("[b][Shift+D][/b]Bulk Delete")
            parts.append("[b][Esc][/b]Deselect")
            parts.append("[b][Ctrl+A][/b]Select All")
        else:
            # Normal mode: show standard commands
            for key, label in COMMANDS.items():
                if key == "M" and not self.merge_enabled:
                    # Show disabled merge command
                    parts.append(f"[dim][{key}]{label}[/dim]")
                else:
                    parts.append(f"[b][{key}][/b]{label}")

        content = "  ".join(parts)
        self.update(content)

    def _get_content_text(self) -> str:
        """
        Get the raw content text for testing purposes.

        Returns:
            The content string that would be rendered (with markup).
        """
        parts = []

        # Mode indicator (Phase 2 Item 2.4)
        parts.append(self._mode_text)
        parts.append("|")

        if self._selection_count > 0:
            parts.append(f"{self._selection_count} selected")
            parts.append("Shift+A Bulk Accept")
            parts.append("Shift+D Bulk Delete")
            parts.append("Esc Deselect")
            parts.append("Ctrl+A Select All")
        else:
            for key, label in COMMANDS.items():
                parts.append(f"[{key}]{label}")

        return "  ".join(parts)

    def set_mode_text(self, mode_text: str) -> None:
        """
        Set the mode indicator text.

        Displayed at the start of the action bar to show current mode:
        "Normal", "Filtering", "Selecting X", etc.

        Args:
            mode_text: Mode description string.
        """
        self._mode_text = mode_text
        self._update_content()

    def set_selection_count(self, count: int) -> None:
        """
        Set the number of selected categories to display.

        When count > 0, the action bar switches to bulk operations mode
        showing selection count and bulk action hints (Shift+A, Shift+D).
        When count is 0, returns to normal command display.

        Args:
            count: Number of selected categories.
        """
        self._selection_count = count
        self._update_content()

    def set_merge_enabled(self, enabled: bool) -> None:
        """
        Enable or disable the merge command.

        Args:
            enabled: Whether merge should be enabled
        """
        self.merge_enabled = enabled
        self._update_content()

    def is_merge_enabled(self) -> bool:
        """
        Check if merge command is enabled.

        Returns:
            True if merge is enabled
        """
        return self.merge_enabled

    def watch_merge_enabled(self, enabled: bool) -> None:
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
            "[u]Sorting[/u]",
            "  [b]F1[/b] - Sort by Name",
            "  [b]F2[/b] - Sort by Confidence",
            "  [b]F3[/b] - Sort by Source",
            "  [b]F4[/b] - Sort by Email Count",
            "  (Press same key again to toggle direction)",
            "",
            "[u]Other[/u]",
            "  [b]?[/b] - Show this help",
            "  [b]Q/Ctrl+C[/b] - Quit (with confirmation)",
            "",
            "Press any key to close this help.",
        ]
        self.update("\n".join(lines))
