"""
Session statistics panel widget for the TUI application.

Displays real-time statistics about review actions taken during the session,
including pending/approved/skipped/deleted counters, a session timer,
and total category count.

Enhanced in Phase 2 Item 1.2 to wire into ReviewApp layout with
reactive updates driven by ReviewState.
"""

from __future__ import annotations

import time

from textual.reactive import reactive
from textual.widgets import Static

from src.ui.tui.state import ReviewState


class StatsPanel(Static):
    """
    A panel widget displaying session statistics.

    Shows counts for:
    - Pending categories (remaining to review)
    - Accepted categories
    - Renamed categories
    - Merged categories
    - Skipped categories
    - Deleted categories
    - Total categories
    - Session elapsed time

    Supports real-time updates via update_from_state(ReviewState).
    """

    accepted: reactive[int] = reactive(0)
    renamed: reactive[int] = reactive(0)
    merged: reactive[int] = reactive(0)
    deleted: reactive[int] = reactive(0)
    pending: reactive[int] = reactive(0)
    skipped: reactive[int] = reactive(0)
    total: reactive[int] = reactive(0)

    def __init__(
        self,
        accepted: int = 0,
        renamed: int = 0,
        merged: int = 0,
        deleted: int = 0,
        pending: int = 0,
        skipped: int = 0,
        total: int = 0,
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
            pending: Number of pending categories
            skipped: Number of skipped categories
            total: Total number of categories
        """
        super().__init__(*args, **kwargs)
        self._session_start: float = time.monotonic()
        self.accepted = accepted
        self.renamed = renamed
        self.merged = merged
        self.deleted = deleted
        self.pending = pending
        self.skipped = skipped
        self.total = total
        self._update_content()

    # -------------------------------------------------------------------------
    # Session timer
    # -------------------------------------------------------------------------

    @property
    def elapsed_seconds(self) -> float:
        """
        Get the elapsed seconds since session start.

        Returns:
            Elapsed time in seconds (non-negative).
        """
        return max(0.0, time.monotonic() - self._session_start)

    def _format_elapsed(self, seconds: int | float) -> str:
        """
        Format an elapsed time value as a human-readable string.

        Args:
            seconds: Elapsed seconds.

        Returns:
            Formatted string: "M:SS" or "H:MM:SS" for >= 1 hour.
        """
        total_secs = int(seconds)
        hours = total_secs // 3600
        minutes = (total_secs % 3600) // 60
        secs = total_secs % 60

        if hours > 0:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        return f"{minutes}:{secs:02d}"

    # -------------------------------------------------------------------------
    # Sync with ReviewState
    # -------------------------------------------------------------------------

    def update_from_state(self, state: ReviewState) -> None:
        """
        Synchronize panel counters from a ReviewState instance.

        Args:
            state: The current ReviewState to read counters from.
        """
        stats = state.get_stats()
        self.accepted = stats["accepted"]
        self.renamed = stats["renamed"]
        self.merged = stats["merged"]
        self.deleted = stats["deleted"]
        self.skipped = stats["skipped"]
        self.pending = stats["remaining"]
        self.total = stats["total"]
        self._update_content()

    # -------------------------------------------------------------------------
    # Backward-compatible API
    # -------------------------------------------------------------------------

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
            stats: Dictionary with keys: approved/accepted, modified/renamed,
                   merged, deleted

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
        self.pending = 0
        self.skipped = 0
        self.total = 0
        self._session_start = time.monotonic()
        self._update_content()

    # -------------------------------------------------------------------------
    # Display
    # -------------------------------------------------------------------------

    def get_content_text(self) -> str:
        """
        Get the content text for the stats panel.

        Returns:
            Formatted stats string with counters and session timer.
        """
        elapsed = self._format_elapsed(self.elapsed_seconds)

        lines = [
            "[b]Session Statistics[/b]",
            "",
            f"[dim]Pending:[/dim]    {self.pending} / {self.total}",
            f"[green]Accepted:[/green]  {self.accepted}",
            f"[blue]Renamed:[/blue]   {self.renamed}",
            f"[yellow]Merged:[/yellow]    {self.merged}",
            f"[cyan]Skipped:[/cyan]   {self.skipped}",
            f"[red]Deleted:[/red]    {self.deleted}",
            "",
            f"[dim]Total:[/dim]      {self.total_actions}",
            f"[dim]Elapsed:[/dim]    {elapsed}",
        ]
        return "\n".join(lines)

    def _update_content(self) -> None:
        """Update the displayed content."""
        self.update(self.get_content_text())

    # -------------------------------------------------------------------------
    # Reactive watchers
    # -------------------------------------------------------------------------

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

    def watch_pending(self, pending: int) -> None:
        """React to pending count changes."""
        self._update_content()

    def watch_skipped(self, skipped: int) -> None:
        """React to skipped count changes."""
        self._update_content()

    def watch_total(self, total: int) -> None:
        """React to total count changes."""
        self._update_content()
