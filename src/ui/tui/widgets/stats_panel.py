"""
Session statistics panel widget for the TUI application.

Displays real-time statistics about review actions taken during the session.
"""

from __future__ import annotations

from textual.reactive import reactive
from textual.widgets import Static


class StatsPanel(Static):
    """
    A panel widget displaying session statistics.

    Shows counts for:
    - Accepted categories
    - Renamed categories
    - Merged categories
    - Deleted categories

    Supports real-time updates as actions are taken.
    """

    accepted: reactive[int] = reactive(0)
    renamed: reactive[int] = reactive(0)
    merged: reactive[int] = reactive(0)
    deleted: reactive[int] = reactive(0)

    def __init__(
        self,
        accepted: int = 0,
        renamed: int = 0,
        merged: int = 0,
        deleted: int = 0,
        *args,
        **kwargs,
    ):
        """
        Initialize the stats panel.

        Args:
            accepted: Number of accepted categories
            renamed: Number of renamed categories
            merged: Number of merged categories
            deleted: Number of deleted categories
        """
        super().__init__(*args, **kwargs)
        self.accepted = accepted
        self.renamed = renamed
        self.merged = merged
        self.deleted = deleted
        self._update_content()

    @property
    def total_actions(self) -> int:
        """
        Calculate total actions taken.

        Returns:
            Sum of all action counts
        """
        return self.accepted + self.renamed + self.merged + self.deleted

    @classmethod
    def from_stats(cls, stats: dict) -> StatsPanel:
        """
        Create a StatsPanel from a stats dictionary.

        Args:
            stats: Dictionary with keys: approved/accepted, modified/renamed, merged, deleted

        Returns:
            New StatsPanel instance
        """
        return cls(
            accepted=stats.get("approved", stats.get("accepted", 0)),
            renamed=stats.get("modified", stats.get("renamed", 0)),
            merged=stats.get("merged", 0),
            deleted=stats.get("deleted", 0),
        )

    def increment_accepted(self) -> None:
        """Increment the accepted count by 1."""
        self.accepted += 1
        self._update_content()

    def increment_renamed(self) -> None:
        """Increment the renamed count by 1."""
        self.renamed += 1
        self._update_content()

    def increment_merged(self) -> None:
        """Increment the merged count by 1."""
        self.merged += 1
        self._update_content()

    def increment_deleted(self) -> None:
        """Increment the deleted count by 1."""
        self.deleted += 1
        self._update_content()

    def reset(self) -> None:
        """Reset all stats to zero."""
        self.accepted = 0
        self.renamed = 0
        self.merged = 0
        self.deleted = 0
        self._update_content()

    def get_content_text(self) -> str:
        """
        Get the content text for the stats panel.

        Returns:
            Formatted stats string
        """
        lines = [
            "[b]Session Statistics[/b]",
            "",
            f"[green]Accepted:[/green]  {self.accepted}",
            f"[blue]Renamed:[/blue]   {self.renamed}",
            f"[yellow]Merged:[/yellow]    {self.merged}",
            f"[red]Deleted:[/red]    {self.deleted}",
            "",
            f"[dim]Total:[/dim]      {self.total_actions}",
        ]
        return "\n".join(lines)

    def _update_content(self) -> None:
        """Update the displayed content."""
        self.update(self.get_content_text())

    def watch_accepted(self, accepted: int) -> None:
        """React to accepted count changes."""
        self._update_content()

    def watch_renamed(self, renamed: int) -> None:
        """React to renamed count changes."""
        self._update_content()

    def watch_merged(self, merged: int) -> None:
        """React to merged count changes."""
        self._update_content()

    def watch_deleted(self, deleted: int) -> None:
        """React to deleted count changes."""
        self._update_content()
