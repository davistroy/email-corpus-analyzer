"""
Search input widget for category filtering.

Per Phase 8 Track 8B.2 specification and Phase 2 Item 1.3.
Supports filter syntax:
- Plain text: fuzzy match on category name and description
- source:cluster - filter by source type
- confidence:>80 - filter by confidence threshold

Activated with '/' key (vim-style), Escape clears and returns focus to table.
"""

from textual.widgets import Input


class SearchInput(Input):
    """
    Search input widget for filtering categories.

    Supports filter syntax:
    - Plain text: fuzzy match on category name and description
    - source:<type>: filter by source (template, content_cluster, sender, custom)
    - confidence:>N: filter by confidence greater than N%
    - confidence:<N: filter by confidence less than N%

    Activated with '/' key (vim-style). Escape clears the filter
    and returns focus to the CategoryTable.
    """

    BINDINGS = [
        ("escape", "clear", "Clear"),
    ]

    def __init__(self, **kwargs):
        """Initialize search input with placeholder."""
        super().__init__(placeholder="Search (/ to activate, Esc to clear)", **kwargs)

    @property
    def filter_query(self) -> str:
        """Get the current filter query."""
        return self.value.strip()

    def action_clear(self) -> None:
        """Clear the search input and return focus to category table."""
        self.value = ""

    def get_filter_indicator(self, visible_count: int, total_count: int) -> str:
        """
        Get the filter indicator text for display in the status area.

        Args:
            visible_count: Number of currently visible (matching) categories.
            total_count: Total number of categories.

        Returns:
            Indicator string like 'Filtered: 3/10 categories', or empty
            string if no filter is active.
        """
        if not self.filter_query:
            return ""
        return f"Filtered: {visible_count}/{total_count} categories"
