"""
Progress bar widget for the TUI application.

Displays review progress as a visual progress bar showing reviewed/total.
"""

from textual.reactive import reactive
from textual.widgets import Static


class ProgressBar(Static):
    """
    A progress bar widget displaying review progress.

    Shows:
    - Visual progress bar
    - Reviewed/Total count
    - Percentage complete
    """

    total: reactive[int] = reactive(0)
    reviewed: reactive[int] = reactive(0)

    def __init__(self, total: int = 0, reviewed: int = 0, *args, **kwargs):
        """
        Initialize the progress bar.

        Args:
            total: Total number of items to review
            reviewed: Number of items already reviewed
        """
        super().__init__(*args, **kwargs)
        self.total = total
        self.reviewed = reviewed
        self._update_content()

    @property
    def percentage(self) -> float:
        """
        Calculate the current percentage complete.

        Returns:
            Percentage as float (0.0 to 100.0)
        """
        if self.total == 0:
            return 0.0
        return (self.reviewed / self.total) * 100.0

    def increment(self) -> None:
        """Increment the reviewed count by 1."""
        self.reviewed += 1
        self._update_content()

    def set_reviewed(self, count: int) -> None:
        """
        Set the reviewed count directly.

        Args:
            count: New reviewed count
        """
        self.reviewed = count
        self._update_content()

    def set_total(self, count: int) -> None:
        """
        Set the total count.

        Args:
            count: New total count
        """
        self.total = count
        self._update_content()

    def reset(self) -> None:
        """Reset the reviewed count to zero."""
        self.reviewed = 0
        self._update_content()

    def get_content_text(self) -> str:
        """
        Get the content text for the progress bar.

        Returns:
            Formatted progress bar string
        """
        bar_width = 20
        filled = int((self.percentage / 100.0) * bar_width)
        empty = bar_width - filled

        bar = "\u2588" * filled + "\u2591" * empty
        pct_str = f"{self.percentage:.1f}%"

        return f"Progress: [{bar}] {self.reviewed}/{self.total} ({pct_str})"

    def _update_content(self) -> None:
        """Update the displayed content."""
        self.update(self.get_content_text())

    def watch_reviewed(self, reviewed: int) -> None:
        """React to reviewed count changes."""
        self._update_content()

    def watch_total(self, total: int) -> None:
        """React to total count changes."""
        self._update_content()
