"""
Category table widget for the TUI application.

A scrollable, navigable table displaying categories with their properties.
Supports hierarchical categories with expand/collapse functionality (Task 4A.4).
Phase 8 Track 8B.1: Added multi-select and bulk operations.
Phase 8 Track 8B.2: Added search/filter functionality.
Phase 2 Item 2.3: Added column sorting with F1-F4 keys.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from textual.reactive import reactive
from textual.widgets import DataTable
from textual.widgets.data_table import ColumnKey

from src.models.category import Category, CategorySource
from src.ui.tui.utils import MAX_NAME_DISPLAY, format_confidence_bar

# Table column definitions
TABLE_COLUMNS = ["#", "Name", "Confidence", "Emails", "Source"]

# Fixed column widths (these don't change with terminal size)
FIXED_COL_INDEX_WIDTH = 4
FIXED_COL_CONFIDENCE_WIDTH = 18
FIXED_COL_EMAILS_WIDTH = 8
FIXED_COL_SOURCE_WIDTH = 10

# Sum of fixed columns (excluding Name which is dynamic)
_FIXED_WIDTH_TOTAL = (
    FIXED_COL_INDEX_WIDTH
    + FIXED_COL_CONFIDENCE_WIDTH
    + FIXED_COL_EMAILS_WIDTH
    + FIXED_COL_SOURCE_WIDTH
)

# Minimum name column width to keep text readable
MIN_NAME_COLUMN_WIDTH = 15


def calculate_name_column_width(terminal_width: int) -> int:
    """
    Calculate the name column width based on available terminal width.

    The name column gets whatever space remains after fixed-width columns
    (index, confidence, emails, source) and estimated borders/padding.
    The result is clamped to a minimum of MIN_NAME_COLUMN_WIDTH.

    Args:
        terminal_width: Total terminal width in columns.

    Returns:
        Width in characters for the Name column.
    """
    # The category list pane gets ~60% of terminal width
    # (3fr out of 5fr total), minus borders (~4 chars)
    pane_width = int(terminal_width * 3 / 5) - 4
    available = pane_width - _FIXED_WIDTH_TOTAL
    return max(MIN_NAME_COLUMN_WIDTH, available)


# ---------------------------------------------------------------------------
# Sort key mapping: F-key -> column name (Phase 2 Item 2.3)
# ---------------------------------------------------------------------------

SORT_KEY_MAP: dict[str, str] = {
    "f1": "name",
    "f2": "confidence",
    "f3": "source",
    "f4": "emails",
}

# Default sort directions when switching TO a column for the first time.
# Name/source are alphabetical (ascending), numeric columns are descending (highest first).
_DEFAULT_ASCENDING: dict[str, bool] = {
    "name": True,
    "confidence": False,
    "emails": False,
    "source": True,
}

# Sort indicator characters
_SORT_INDICATOR_ASC = "\u25b2"  # ▲
_SORT_INDICATOR_DESC = "\u25bc"  # ▼


@dataclass
class SortState:
    """
    Tracks the current sort column and direction.

    Default sort is confidence descending (highest confidence first),
    matching the original behavior before sorting was added.
    """

    column: str = "confidence"
    ascending: bool = False

    @property
    def indicator(self) -> str:
        """Return the Unicode arrow indicator for the current direction."""
        return _SORT_INDICATOR_ASC if self.ascending else _SORT_INDICATOR_DESC

    def toggle(self, column: str) -> None:
        """
        Toggle sort for the given column.

        If the column is already active, flip ascending/descending.
        If switching to a new column, use the default direction for that column.

        Args:
            column: The column key to sort by.
        """
        if column == self.column:
            self.ascending = not self.ascending
        else:
            self.column = column
            self.ascending = _DEFAULT_ASCENDING.get(column, True)


def sort_categories(categories: list[Category], state: SortState) -> list[Category]:
    """
    Return a new list of categories sorted according to the given SortState.

    Does NOT mutate the original list.

    Args:
        categories: Categories to sort.
        state: Current sort configuration.

    Returns:
        A new sorted list of Category objects.
    """
    if not categories:
        return []

    def _sort_key(cat: Category):
        if state.column == "name":
            return cat.category_name.lower()
        if state.column == "confidence":
            return cat.confidence
        if state.column == "emails":
            # None email_count sorts last regardless of direction
            if cat.email_count is None:
                return float("-inf") if state.ascending else float("-inf")
            return cat.email_count
        if state.column == "source":
            return cat.source.value.lower()
        # Fallback
        return cat.category_name.lower()

    # For email_count with None values, we need special handling:
    # None always sorts to the end (last position) regardless of direction.
    if state.column == "emails":
        has_count = [c for c in categories if c.email_count is not None]
        no_count = [c for c in categories if c.email_count is None]
        sorted_with = sorted(has_count, key=_sort_key, reverse=not state.ascending)
        return sorted_with + no_count

    return sorted(categories, key=_sort_key, reverse=not state.ascending)


def get_sort_header(display_name: str, column_key: str, state: SortState) -> str:
    """
    Return a column header string with sort indicator if this column is active.

    Args:
        display_name: The human-readable column label (e.g. "Name").
        column_key: The internal sort key (e.g. "name").
        state: Current sort state.

    Returns:
        The display name, optionally followed by an arrow indicator.
    """
    if state.column == column_key:
        return f"{display_name} {state.indicator}"
    return display_name


# Hierarchy indicators
EXPAND_INDICATOR = "+"
COLLAPSE_INDICATOR = "-"
INDENT_CHAR = "  "  # Two spaces per level
CHILD_INDICATOR = "|--"

# Selection indicator
SELECTED_INDICATOR = "*"


def format_source(source: CategorySource) -> str:
    """
    Format category source for display.

    Args:
        source: CategorySource enum value

    Returns:
        Human-readable source string
    """
    source_labels = {
        CategorySource.CONTENT_CLUSTER: "Cluster",
        CategorySource.SENDER: "Sender",
        CategorySource.TEMPLATE: "Template",
        CategorySource.CUSTOM: "Custom",
    }
    return source_labels.get(source, str(source.value))


def format_email_count(count: int | None) -> str:
    """
    Format email count for display.

    Args:
        count: Email count or None

    Returns:
        Formatted count string
    """
    if count is None:
        return "-"
    return str(count)


def format_hierarchy_indicator(
    level: int,
    has_children: bool,
    expanded: bool,
) -> str:
    """
    Format hierarchy indicator for tree view display.

    Args:
        level: Category hierarchy level (0=top, 1=sub, etc.)
        has_children: Whether category has subcategories
        expanded: Whether category is expanded (shows children)

    Returns:
        Hierarchy indicator string
    """
    if level == 0:
        # Top-level category
        if has_children:
            return COLLAPSE_INDICATOR if expanded else EXPAND_INDICATOR
        return " "  # No indicator for leaf at top level
    # Child category - show indentation
    indent = INDENT_CHAR * (level - 1)
    return f"{indent}{CHILD_INDICATOR}"


class CategoryTable(DataTable):
    """
    A table widget for displaying and selecting categories.

    Supports keyboard navigation with j/k and arrow keys,
    row selection with highlighting, color-coded confidence,
    hierarchical category display with expand/collapse,
    multi-select for bulk operations (Phase 8 Track 8B.1),
    and search/filter functionality (Phase 8 Track 8B.2).
    """

    BINDINGS = [
        ("j", "cursor_down", "Down"),
        ("k", "cursor_up", "Up"),
        ("down", "cursor_down", "Down"),
        ("up", "cursor_up", "Up"),
        ("enter", "select", "Select"),
        ("space", "toggle_select", "Toggle Selection"),
    ]

    selected_row: reactive[int] = reactive(0)

    def __init__(self, categories: list[Category], *args, **kwargs):
        """
        Initialize the category table.

        Args:
            categories: List of categories to display (may include hierarchical)
        """
        super().__init__(*args, cursor_type="row", **kwargs)
        self.categories = list(categories)  # Make a copy
        self._table_initialized = False
        # Track expanded state for hierarchical categories
        self._expanded_ids: set[str] = set()
        # Initialize all top-level categories as collapsed by default

        # Multi-select support (Phase 8 Track 8B.1)
        self.selected_ids: set[str] = set()

        # Filter support (Phase 8 Track 8B.2)
        self._filter_query: str = ""
        self._filtered_categories: list[Category] | None = None

        # Sort support (Phase 2 Item 2.3)
        self.sort_state = SortState()

    def on_mount(self) -> None:
        """Set up the table when mounted."""
        if not self._table_initialized:
            self._setup_table()
            self._table_initialized = True

    def _setup_table(self) -> None:
        """Set up table columns and populate with data."""
        # Add columns
        self.add_column("#", key="index", width=4)
        self.add_column("Name", key="name", width=30)
        self.add_column("Confidence", key="confidence", width=18)
        self.add_column("Emails", key="emails", width=8)
        self.add_column("Source", key="source", width=10)

        # Add rows
        self._populate_rows()

    def _populate_rows(self) -> None:
        """Populate table with category data, respecting hierarchy, expansion, and selection."""
        self.clear()
        visible_categories = self.get_visible_categories()

        for idx, category in enumerate(visible_categories, 1):
            # Format name with hierarchy indicator
            indicator = format_hierarchy_indicator(
                level=category.level,
                has_children=category.has_children,
                expanded=self.is_expanded(category.category_id),
            )

            # Add selection indicator (Phase 2 Item 2.2)
            selected_mark = SELECTED_INDICATOR if category.category_id in self.selected_ids else " "

            display_name = f"{indicator} {category.category_name}"

            confidence_bar = format_confidence_bar(category.confidence)
            self.add_row(
                f"{selected_mark}{idx}",
                display_name[:MAX_NAME_DISPLAY],  # Truncate long names
                confidence_bar,
                format_email_count(category.email_count),
                format_source(category.source),
                key=category.category_id,
            )

    def get_visible_categories(self) -> list[Category]:
        """
        Get list of categories currently visible (respecting sort, expanded state, and filter).

        Returns:
            List of Category objects that should be displayed
        """
        # Use filtered list if filter is active
        base_categories = (
            self._filtered_categories if self._filtered_categories is not None else self.categories
        )

        # Apply sort (Phase 2 Item 2.3)
        sorted_categories = sort_categories(base_categories, self.sort_state)

        visible = []
        for category in sorted_categories:
            visible.append(category)
            # Add children if expanded
            if category.has_children and self.is_expanded(category.category_id):
                visible.extend(category.subcategories)
        return visible

    def is_expanded(self, category_id: str) -> bool:
        """
        Check if a category is expanded.

        Args:
            category_id: ID of category to check

        Returns:
            True if expanded, False if collapsed
        """
        return category_id in self._expanded_ids

    def toggle_expand(self, category_id: str) -> None:
        """
        Toggle expand/collapse state for a category.

        Args:
            category_id: ID of category to toggle
        """
        if category_id in self._expanded_ids:
            self._expanded_ids.remove(category_id)
        else:
            self._expanded_ids.add(category_id)
        self._populate_rows()

    def expand_category(self, category_id: str) -> None:
        """
        Expand a category to show its children.

        Args:
            category_id: ID of category to expand
        """
        self._expanded_ids.add(category_id)
        self._populate_rows()

    def collapse_category(self, category_id: str) -> None:
        """
        Collapse a category to hide its children.

        Args:
            category_id: ID of category to collapse
        """
        self._expanded_ids.discard(category_id)
        self._populate_rows()

    def get_selected_category(self) -> Category | None:
        """
        Get the currently selected category.

        Returns:
            Selected Category or None if no selection
        """
        visible = self.get_visible_categories()
        if not visible or self.selected_row < 0:
            return None
        if self.selected_row >= len(visible):
            return None
        return visible[self.selected_row]

    def move_down(self) -> None:
        """Move selection down one row."""
        visible = self.get_visible_categories()
        if not visible:
            return
        self.selected_row = (self.selected_row + 1) % len(visible)
        self.move_cursor(row=self.selected_row)

    def move_up(self) -> None:
        """Move selection up one row."""
        visible = self.get_visible_categories()
        if not visible:
            return
        self.selected_row = (self.selected_row - 1) % len(visible)
        self.move_cursor(row=self.selected_row)

    def remove_category(self, category: Category) -> None:
        """
        Remove a category from the table.

        Preserves sort order. Selection adjusts to stay within bounds.

        Args:
            category: Category to remove
        """
        if category in self.categories:
            # Remember current selection identity before removal
            selected_cat = self.get_selected_category()
            selected_id = selected_cat.category_id if selected_cat else None

            self.categories.remove(category)

            # Adjust selection: try to keep same category, else clamp
            visible = self.get_visible_categories()
            if not visible:
                self.selected_row = 0
            elif selected_id and selected_id != category.category_id:
                # Find the same category in the new visible list
                for i, cat in enumerate(visible):
                    if cat.category_id == selected_id:
                        self.selected_row = i
                        break
                else:
                    self.selected_row = min(self.selected_row, len(visible) - 1)
            else:
                # Selected category was the one removed; clamp
                self.selected_row = min(self.selected_row, len(visible) - 1)

            # Rebuild table
            if self._table_initialized:
                self._populate_rows()

    def update_category(self, old_category: Category, new_category: Category) -> None:
        """
        Update a category in the table.

        Re-applies current sort after update so the new values
        appear in the correct position.

        Args:
            old_category: Category to replace
            new_category: New category data
        """
        if old_category in self.categories:
            idx = self.categories.index(old_category)
            self.categories[idx] = new_category
            # Re-populate; sort is applied automatically via get_visible_categories
            if self._table_initialized:
                self._populate_rows()

    def refresh_display(self) -> None:
        """Refresh the table display."""
        self._populate_rows()

    # -------------------------------------------------------------------------
    # Column Sorting (Phase 2 Item 2.3)
    # -------------------------------------------------------------------------

    def apply_sort(self, column: str) -> None:
        """
        Apply or toggle sort for the given column.

        If the column is already the active sort column, toggles
        ascending/descending. Otherwise, switches to the new column
        with its default sort direction.

        Preserves the currently selected category identity (not row index)
        so the user's selection tracks across sort changes.

        Args:
            column: Column key to sort by (name, confidence, emails, source).
        """
        # Remember current selection
        selected_cat = self.get_selected_category()
        selected_id = selected_cat.category_id if selected_cat else None

        # Toggle sort state
        self.sort_state.toggle(column)

        # Re-populate rows (get_visible_categories will apply the new sort)
        if self._table_initialized:
            self._populate_rows()

        # Restore selection to the same category
        if selected_id is not None:
            visible = self.get_visible_categories()
            for i, cat in enumerate(visible):
                if cat.category_id == selected_id:
                    self.selected_row = i
                    break

    def update_column_widths(self, terminal_width: int) -> None:
        """
        Recalculate column widths based on terminal width (Phase 2 Item 1.5).

        Updates the Name column to use available space while keeping
        fixed-width columns unchanged. Repopulates rows to apply
        new truncation lengths.

        Args:
            terminal_width: Current terminal width in columns.
        """
        new_name_width = calculate_name_column_width(terminal_width)
        # Update the column width in the DataTable if columns exist
        if self._table_initialized and self.columns:
            try:
                name_col = self.columns.get(ColumnKey("name"))
                if name_col is not None:
                    name_col.width = new_name_width
            except (KeyError, AttributeError):
                pass  # Column may not exist yet
        # Re-populate rows so name truncation uses the new width
        if self._table_initialized:
            self._populate_rows()

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """Handle row highlight event."""
        if event.cursor_row is not None:
            self.selected_row = event.cursor_row

    def expand_all(self) -> None:
        """Expand all hierarchical categories."""
        for category in self.categories:
            if category.has_children:
                self._expanded_ids.add(category.category_id)
        self._populate_rows()

    def collapse_all(self) -> None:
        """Collapse all hierarchical categories."""
        self._expanded_ids.clear()
        self._populate_rows()

    # -------------------------------------------------------------------------
    # Multi-Select Operations (Phase 8 Track 8B.1)
    # -------------------------------------------------------------------------

    def toggle_selection(self, category_id: str) -> None:
        """
        Toggle selection state for a category.

        Args:
            category_id: ID of category to toggle
        """
        if category_id in self.selected_ids:
            self.selected_ids.remove(category_id)
        else:
            self.selected_ids.add(category_id)
        if self._table_initialized:
            self._populate_rows()

    def action_toggle_select(self) -> None:
        """Action handler for space key - toggle current selection."""
        category = self.get_selected_category()
        if category:
            self.toggle_selection(category.category_id)

    def select_all(self) -> None:
        """Select all visible categories."""
        visible = self.get_visible_categories()
        for cat in visible:
            self.selected_ids.add(cat.category_id)
        if self._table_initialized:
            self._populate_rows()

    def clear_selection(self) -> None:
        """Clear all selections."""
        self.selected_ids.clear()
        if self._table_initialized:
            self._populate_rows()

    def is_selected(self, category_id: str) -> bool:
        """
        Check if a category is selected.

        Args:
            category_id: ID of category to check

        Returns:
            True if selected, False otherwise
        """
        return category_id in self.selected_ids

    def get_selected_categories(self) -> list[Category]:
        """
        Get all selected Category objects.

        Returns:
            List of selected Category objects
        """
        selected = []
        for cat in self.categories:
            if cat.category_id in self.selected_ids:
                selected.append(cat)
            # Also check subcategories
            for subcat in cat.subcategories:
                if subcat.category_id in self.selected_ids:
                    selected.append(subcat)
        return selected

    def accept_selected(self) -> list[Category]:
        """
        Accept (remove) all selected categories.

        Returns:
            List of accepted Category objects
        """
        accepted = self.get_selected_categories()

        # Remove from categories list
        self.categories = [
            cat for cat in self.categories if cat.category_id not in self.selected_ids
        ]

        # Also remove from subcategories
        for cat in self.categories:
            cat.subcategories = [
                sub for sub in cat.subcategories if sub.category_id not in self.selected_ids
            ]

        # Clear selection
        self.selected_ids.clear()
        if self._table_initialized:
            self._populate_rows()

        return accepted

    def delete_selected(self) -> list[Category]:
        """
        Delete all selected categories.

        Returns:
            List of deleted Category objects
        """
        # Same implementation as accept - just different semantics
        return self.accept_selected()

    # -------------------------------------------------------------------------
    # Search/Filter Operations (Phase 8 Track 8B.2)
    # -------------------------------------------------------------------------

    def apply_filter(self, query: str) -> None:
        """
        Apply a filter to the category list.

        Args:
            query: Filter query string
                - Plain text: fuzzy match on name
                - source:<type>: filter by source
                - confidence:>N or confidence:<N: filter by confidence
        """
        self._filter_query = query.strip()
        self._filtered_categories = None  # Clear cache to recalculate

        if not self._filter_query:
            if self._table_initialized:
                self._populate_rows()
            return

        # Parse filter query
        filtered = []
        for cat in self.categories:
            if self._matches_filter(cat, self._filter_query):
                filtered.append(cat)
            # Also check subcategories
            for subcat in cat.subcategories:
                if self._matches_filter(subcat, self._filter_query):
                    if cat not in filtered:
                        filtered.append(cat)
                    break

        self._filtered_categories = filtered
        self._clamp_selected_row()
        if self._table_initialized:
            self._populate_rows()

    def _clamp_selected_row(self) -> None:
        """Clamp selected_row to valid range for currently visible categories."""
        visible = self.get_visible_categories()
        if not visible:
            self.selected_row = 0
        elif self.selected_row >= len(visible):
            self.selected_row = len(visible) - 1

    def _matches_filter(self, category: Category, query: str) -> bool:
        """
        Check if a category matches the filter query.

        Args:
            category: Category to check
            query: Filter query

        Returns:
            True if matches, False otherwise
        """
        query_lower = query.lower()

        # Check for source filter: source:template, source:content_cluster, etc.
        if query_lower.startswith("source:"):
            source_type = query_lower[7:]
            return source_type in category.source.value.lower()

        # Check for confidence filter: confidence:>80, confidence:<70
        confidence_match = re.match(r"confidence:([<>])(\d+)", query_lower)
        if confidence_match:
            operator = confidence_match.group(1)
            threshold = int(confidence_match.group(2)) / 100.0
            if operator == ">":
                return category.confidence > threshold
            return category.confidence < threshold

        # Default: fuzzy match on name or description (case insensitive)
        return query_lower in category.category_name.lower() or (
            bool(category.description) and query_lower in category.description.lower()
        )

    def clear_filter(self) -> None:
        """Clear the current filter."""
        self._filter_query = ""
        self._filtered_categories = None
        if self._table_initialized:
            self._populate_rows()

    @property
    def has_active_filter(self) -> bool:
        """Check if there's an active filter."""
        return bool(self._filter_query)

    @property
    def filter_count_text(self) -> str:
        """
        Get the filter count indicator text.

        Returns:
            String like "2 of 5 categories"
        """
        visible_count = len(self.get_visible_categories())
        total_count = len(self.categories)
        return f"{visible_count} of {total_count} categories"

    def select_by_pattern(self, pattern: str) -> None:
        """
        Select categories matching a pattern.

        Args:
            pattern: Pattern to match (same syntax as filter)
        """
        for cat in self.categories:
            if self._matches_filter(cat, pattern):
                self.selected_ids.add(cat.category_id)
            for subcat in cat.subcategories:
                if self._matches_filter(subcat, pattern):
                    self.selected_ids.add(subcat.category_id)
        if self._table_initialized:
            self._populate_rows()
