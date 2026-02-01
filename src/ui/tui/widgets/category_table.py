"""
Category table widget for the TUI application.

A scrollable, navigable table displaying categories with their properties.
Supports hierarchical categories with expand/collapse functionality (Task 4A.4).
Phase 8 Track 8B.1: Added multi-select and bulk operations.
Phase 8 Track 8B.2: Added search/filter functionality.
"""
import re

from textual.reactive import reactive
from textual.widgets import DataTable

from src.models.category import Category, CategorySource

# Table column definitions
TABLE_COLUMNS = ["#", "Name", "Confidence", "Emails", "Source"]

# Hierarchy indicators
EXPAND_INDICATOR = "+"
COLLAPSE_INDICATOR = "-"
INDENT_CHAR = "  "  # Two spaces per level
CHILD_INDICATOR = "|--"

# Selection indicator
SELECTED_INDICATOR = "*"


def format_confidence_bar(confidence: float, width: int = 10) -> str:
    """
    Format confidence as a visual bar.

    Args:
        confidence: Confidence value between 0 and 1
        width: Width of the bar in characters

    Returns:
        String representing the confidence bar
    """
    filled = int(confidence * width)
    empty = width - filled
    bar = "\u2588" * filled + "\u2591" * empty
    percentage = f"{confidence * 100:.0f}%"
    return f"{bar} {percentage}"


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

    def __init__(
        self,
        categories: list[Category],
        *args,
        **kwargs
    ):
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
        """Populate table with category data, respecting hierarchy and expansion."""
        self.clear()
        visible_categories = self.get_visible_categories()

        for idx, category in enumerate(visible_categories, 1):
            # Format name with hierarchy indicator
            indicator = format_hierarchy_indicator(
                level=category.level,
                has_children=category.has_children,
                expanded=self.is_expanded(category.category_id),
            )
            display_name = f"{indicator} {category.category_name}"

            confidence_bar = format_confidence_bar(category.confidence)
            self.add_row(
                str(idx),
                display_name[:28],  # Truncate long names
                confidence_bar,
                format_email_count(category.email_count),
                format_source(category.source),
                key=category.category_id,
            )

    def get_visible_categories(self) -> list[Category]:
        """
        Get list of categories currently visible (respecting expanded state and filter).

        Returns:
            List of Category objects that should be displayed
        """
        # Use filtered list if filter is active
        base_categories = (
            self._filtered_categories
            if self._filtered_categories is not None
            else self.categories
        )

        visible = []
        for category in base_categories:
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

        Args:
            category: Category to remove
        """
        if category in self.categories:
            idx = self.categories.index(category)
            self.categories.remove(category)

            # Adjust selection if needed
            visible = self.get_visible_categories()
            if visible:
                if self.selected_row >= len(visible):
                    self.selected_row = len(visible) - 1
                elif self.selected_row > idx:
                    self.selected_row -= 1
            else:
                self.selected_row = 0

            # Rebuild table
            self._populate_rows()

    def update_category(self, old_category: Category, new_category: Category) -> None:
        """
        Update a category in the table.

        Args:
            old_category: Category to replace
            new_category: New category data
        """
        if old_category in self.categories:
            idx = self.categories.index(old_category)
            self.categories[idx] = new_category
            self._populate_rows()

    def refresh_display(self) -> None:
        """Refresh the table display."""
        self._populate_rows()

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """Handle row highlight event."""
        if event.cursor_row is not None:
            self.selected_row = event.cursor_row

    # -------------------------------------------------------------------------
    # Hierarchical Actions (Task 4A.4)
    # -------------------------------------------------------------------------

    def promote_to_top_level(self, category: Category) -> None:
        """
        Promote a subcategory to top level.

        Args:
            category: Subcategory to promote
        """
        if category.level == 0:
            return  # Already top level

        # Find parent and remove from its subcategories
        for parent in self.categories:
            if category in parent.subcategories:
                parent.subcategories.remove(category)
                break

        # Update category properties
        category.level = 0
        category.parent_category_id = None

        # Add to main categories list
        self.categories.append(category)
        self._populate_rows()

    def demote_to_subcategory(
        self,
        category: Category,
        new_parent: Category
    ) -> None:
        """
        Demote a top-level category to subcategory of another.

        Args:
            category: Category to demote
            new_parent: Category that will become the parent
        """
        if category.level != 0:
            return  # Already a subcategory
        if category == new_parent:
            return  # Cannot demote to self
        if new_parent not in self.categories:
            return  # Parent must be top-level

        # Remove from top-level
        if category in self.categories:
            self.categories.remove(category)

        # Update category properties
        category.level = 1
        category.parent_category_id = new_parent.category_id

        # Add to new parent's subcategories
        new_parent.subcategories.append(category)
        self._populate_rows()

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
            cat for cat in self.categories
            if cat.category_id not in self.selected_ids
        ]

        # Also remove from subcategories
        for cat in self.categories:
            cat.subcategories = [
                sub for sub in cat.subcategories
                if sub.category_id not in self.selected_ids
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
        if self._table_initialized:
            self._populate_rows()

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

        # Default: fuzzy match on name (case insensitive)
        return query_lower in category.category_name.lower()

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
