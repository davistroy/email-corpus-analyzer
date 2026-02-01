"""
Search input widget for category filtering.

Per Phase 8 Track 8B.2 specification.
Supports filter syntax:
- Plain text: fuzzy match on category name
- source:cluster - filter by source type
- confidence:>80 - filter by confidence threshold
"""
from textual.widgets import Input


class SearchInput(Input):
    """
    Search input widget for filtering categories.

    Supports filter syntax:
    - Plain text: fuzzy match on category name
    - source:<type>: filter by source (template, content_cluster, sender, custom)
    - confidence:>N: filter by confidence greater than N%
    - confidence:<N: filter by confidence less than N%
    """

    BINDINGS = [
        ("escape", "clear", "Clear"),
    ]

    def __init__(self, **kwargs):
        """Initialize search input with placeholder."""
        super().__init__(
            placeholder="Search (/ to activate, Esc to clear)",
            **kwargs
        )

    @property
    def filter_query(self) -> str:
        """Get the current filter query."""
        return self.value.strip()

    def action_clear(self) -> None:
        """Clear the search input."""
        self.value = ""
