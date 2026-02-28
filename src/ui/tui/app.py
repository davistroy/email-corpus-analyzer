"""
Main TUI application for category review.

Provides an interactive terminal-based interface for reviewing,
approving, and modifying suggested email categories.

State is centralized in ReviewState (state.py) per Phase 2 Item 1.4.
"""

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.css.query import NoMatches
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import Footer, Header, Input, Static

from src.models.category import Category
from src.ui.tui.state import ReviewState
from src.ui.tui.theme import APP_CSS
from src.ui.tui.widgets.action_bar import ActionBar, HelpOverlay
from src.ui.tui.widgets.category_table import CategoryTable
from src.ui.tui.widgets.detail_panel import DetailPanel


class RenameModal(ModalScreen[str | None]):
    """Modal dialog for renaming a category."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(self, current_name: str, *args, **kwargs):
        """Initialize with current category name."""
        super().__init__(*args, **kwargs)
        self.current_name = current_name

    def compose(self) -> ComposeResult:
        """Compose the modal content."""
        yield Container(
            Static("Rename Category", classes="modal-title"),
            Static(f"Current name: {self.current_name}", classes="modal-subtitle"),
            Input(placeholder="Enter new name", id="rename-input"),
            Static("Press Enter to confirm, Escape to cancel", classes="modal-hint"),
            id="rename-modal",
        )

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission."""
        if event.value.strip():
            self.dismiss(event.value.strip())
        else:
            self.dismiss(None)

    def action_cancel(self) -> None:
        """Cancel the rename."""
        self.dismiss(None)


class MergeModal(ModalScreen[Category | None]):
    """Modal dialog for selecting a category to merge into."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(self, categories: list[Category], *args, **kwargs):
        """Initialize with available categories to merge into."""
        super().__init__(*args, **kwargs)
        self.merge_categories = categories

    def compose(self) -> ComposeResult:
        """Compose the modal content."""
        yield Container(
            Static("Merge Into Category", classes="modal-title"),
            Static("Select a category to merge into:", classes="modal-subtitle"),
            CategoryTable(categories=self.merge_categories, id="merge-table"),
            Static("Press Enter to select, Escape to cancel", classes="modal-hint"),
            id="merge-modal",
        )

    def on_data_table_row_selected(self, event) -> None:
        """Handle category selection."""
        table = self.query_one("#merge-table", CategoryTable)
        selected = table.get_selected_category()
        self.dismiss(selected)

    def action_cancel(self) -> None:
        """Cancel the merge."""
        self.dismiss(None)


class ConfirmQuitModal(ModalScreen[bool]):
    """Modal dialog for confirming quit."""

    BINDINGS = [
        Binding("y", "confirm", "Yes"),
        Binding("n", "cancel", "No"),
        Binding("escape", "cancel", "No"),
    ]

    def compose(self) -> ComposeResult:
        """Compose the modal content."""
        yield Container(
            Static("Quit Category Review?", classes="modal-title"),
            Static("Unsaved changes will be lost.", classes="modal-subtitle"),
            Static("[Y]es / [N]o", classes="modal-hint"),
            id="quit-modal",
        )

    def action_confirm(self) -> None:
        """Confirm quit."""
        self.dismiss(True)

    def action_cancel(self) -> None:
        """Cancel quit."""
        self.dismiss(False)


class HelpScreen(ModalScreen[None]):
    """Screen showing help information."""

    BINDINGS = [
        Binding("escape", "dismiss", "Close"),
        Binding("?", "dismiss", "Close"),
        Binding("f1", "dismiss", "Close"),
    ]

    def compose(self) -> ComposeResult:
        """Compose the help screen."""
        yield Container(
            HelpOverlay(),
            id="help-container",
        )

    def on_key(self, event) -> None:
        """Close on any key press."""
        self.dismiss(None)


class ReviewApp(App):
    """
    Main TUI application for reviewing email categories.

    All mutable state is centralized in self.state (ReviewState).
    Provides an interactive interface for:
    - Viewing suggested categories in a scrollable table
    - Seeing detailed information about each category
    - Accepting, renaming, merging, deleting, or skipping categories
    """

    TITLE = "Category Review"
    SUB_TITLE = "Email Corpus Analyzer"

    CSS = APP_CSS

    BINDINGS = [
        Binding("q", "quit_confirm", "Quit"),
        Binding("ctrl+c", "quit_confirm", "Quit"),
        Binding("?", "help", "Help"),
        Binding("f1", "help", "Help"),
        Binding("a", "accept", "Accept"),
        Binding("r", "rename", "Rename"),
        Binding("m", "merge", "Merge"),
        Binding("d", "delete", "Delete"),
        Binding("s", "skip", "Skip"),
        Binding("j", "move_down", "Down"),
        Binding("k", "move_up", "Up"),
        Binding("down", "move_down", "Down"),
        Binding("up", "move_up", "Up"),
    ]

    selected_index: reactive[int] = reactive(0)

    def __init__(
        self, categories: list[Category], email_lookup: dict | None = None, *args, **kwargs
    ):
        """
        Initialize the review application.

        Args:
            categories: List of categories to review
            email_lookup: Optional dictionary mapping email IDs to Email objects
        """
        super().__init__(*args, **kwargs)
        self.state = ReviewState(categories=categories)
        self.email_lookup = email_lookup or {}

    # -------------------------------------------------------------------------
    # Backward-compatible property accessors (delegate to state)
    # -------------------------------------------------------------------------

    @property
    def categories(self) -> list[Category]:
        """Pending categories (delegates to state.pending)."""
        return self.state._pending

    @categories.setter
    def categories(self, value: list[Category]) -> None:
        """Set pending categories (used only during init/legacy paths)."""
        # Only used if something directly assigns app.categories
        self.state._pending = list(value)

    @property
    def approved_categories(self) -> list[Category]:
        """Approved categories (delegates to state)."""
        return self.state._approved

    @approved_categories.setter
    def approved_categories(self, value: list[Category]) -> None:
        """Set approved categories (backward compat for tests)."""
        self.state._approved = list(value)

    @property
    def skipped_categories(self) -> list[Category]:
        """Skipped categories (delegates to state)."""
        return self.state._skipped

    @skipped_categories.setter
    def skipped_categories(self, value: list[Category]) -> None:
        """Set skipped categories (backward compat)."""
        self.state._skipped = list(value)

    @property
    def modified_count(self) -> int:
        """Renamed count (backward compat name)."""
        return self.state._counters["renamed"]

    @modified_count.setter
    def modified_count(self, value: int) -> None:
        """Set renamed count (backward compat)."""
        self.state._counters["renamed"] = value

    @property
    def merged_count(self) -> int:
        """Merged count."""
        return self.state._counters["merged"]

    @merged_count.setter
    def merged_count(self, value: int) -> None:
        """Set merged count (backward compat)."""
        self.state._counters["merged"] = value

    @property
    def deleted_count(self) -> int:
        """Deleted count."""
        return self.state._counters["deleted"]

    @deleted_count.setter
    def deleted_count(self, value: int) -> None:
        """Set deleted count (backward compat)."""
        self.state._counters["deleted"] = value

    @property
    def _selected_index(self) -> int:
        """Selected index (delegates to state)."""
        return self.state._selected_index

    @_selected_index.setter
    def _selected_index(self, value: int) -> None:
        """Set selected index (delegates to state)."""
        self.state.selected_index = value

    # -------------------------------------------------------------------------
    # Compose & Mount
    # -------------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        """Compose the application UI."""
        yield Header()
        yield Horizontal(
            Vertical(
                CategoryTable(
                    categories=self.categories,
                    id="category-table",
                ),
                id="category-list",
            ),
            Vertical(
                DetailPanel(
                    category=self.categories[0] if self.categories else None,
                    email_lookup=self.email_lookup,
                    id="detail-panel",
                ),
                id="detail-container",
            ),
            id="main-container",
        )
        yield ActionBar(id="action-bar")
        yield Footer()

    def on_mount(self) -> None:
        """Handle app mount event."""
        self._update_detail_panel()
        self._update_action_bar()

    # -------------------------------------------------------------------------
    # Public query methods
    # -------------------------------------------------------------------------

    def get_selected_category(self) -> Category | None:
        """
        Get the currently selected category.

        Returns:
            Selected Category or None if no selection
        """
        return self.state.selected_category

    def get_approved_categories(self) -> list[Category]:
        """
        Get all approved categories.

        Returns:
            List of approved categories (copy)
        """
        return self.state.approved

    def get_stats(self) -> dict:
        """
        Get review statistics.

        Returns:
            Dictionary with modification stats.
            Includes backward-compatible keys (modified, merged, deleted,
            approved, skipped, remaining).
        """
        state_stats = self.state.get_stats()
        return {
            "modified": state_stats["renamed"],
            "merged": state_stats["merged"],
            "deleted": state_stats["deleted"],
            "approved": state_stats["approved"],
            "skipped": state_stats["skipped"],
            "remaining": state_stats["remaining"],
        }

    # -------------------------------------------------------------------------
    # Widget update helpers
    # -------------------------------------------------------------------------

    def _update_detail_panel(self) -> None:
        """Update the detail panel with selected category."""
        try:
            panel = self.query_one("#detail-panel", DetailPanel)
            category = self.get_selected_category()
            panel.update_category(category)
        except NoMatches:
            pass  # Panel may not be mounted yet

    def _update_action_bar(self) -> None:
        """Update action bar based on current state."""
        try:
            bar = self.query_one("#action-bar", ActionBar)
            bar.set_merge_enabled(len(self.approved_categories) > 0)
        except NoMatches:
            pass  # Bar may not be mounted yet

    def _update_table(self) -> None:
        """Update the category table."""
        try:
            table = self.query_one("#category-table", CategoryTable)
            table.categories = self.categories
            table.refresh_display()
        except NoMatches:
            pass  # Table may not be mounted yet

    def _refresh_all_widgets(self) -> None:
        """Refresh all widgets after a state change."""
        self._update_table()
        self._update_detail_panel()
        self._update_action_bar()

    def _remove_current_category(self) -> Category | None:
        """Remove and return the current category from the list.

        NOTE: This is kept for backward compatibility with action methods
        that still need the removed category reference. The actual removal
        is handled through ReviewState methods in the action_* methods.
        """
        category = self.get_selected_category()
        if category and category in self.categories:
            self.categories.remove(category)
            # Adjust selection
            if self._selected_index >= len(self.categories):
                self._selected_index = max(0, len(self.categories) - 1)
            self._update_table()
            self._update_detail_panel()
        return category

    # -------------------------------------------------------------------------
    # Action methods (delegate to state, update widgets)
    # -------------------------------------------------------------------------

    def action_accept(self) -> None:
        """Accept the current category."""
        category = self.get_selected_category()
        if category and self.state.accept(category.category_id):
            self._refresh_all_widgets()
            self.notify(f"Accepted: {category.category_name}")

    def action_rename(self) -> None:
        """Rename the current category."""
        category = self.get_selected_category()
        if not category:
            return

        cat_id = category.category_id

        def handle_rename(new_name: str | None) -> None:
            if new_name:
                old_name = category.category_name
                if self.state.rename(cat_id, new_name):
                    self._refresh_all_widgets()
                    self.notify(f"Renamed: {old_name} -> {new_name}")

        self.push_screen(RenameModal(category.category_name), handle_rename)

    def action_merge(self) -> None:
        """Merge the current category with another."""
        if not self.approved_categories:
            self.notify("No approved categories to merge with", severity="warning")
            return

        category = self.get_selected_category()
        if not category:
            return

        source_id = category.category_id

        def handle_merge(target: Category | None) -> None:
            if target and self.state.merge(source_id, target.category_id):
                self._refresh_all_widgets()
                self.notify(f"Merged into: {target.category_name}")

        self.push_screen(MergeModal(self.approved_categories), handle_merge)

    def action_delete(self) -> None:
        """Delete the current category."""
        category = self.get_selected_category()
        if category and self.state.delete(category.category_id):
            self._refresh_all_widgets()
            self.notify(f"Deleted: {category.category_name}")

    def action_skip(self) -> None:
        """Skip the current category for later review."""
        category = self.get_selected_category()
        if category and self.state.skip(category.category_id):
            self._refresh_all_widgets()
            self.notify(f"Skipped: {category.category_name}")

    def action_move_down(self) -> None:
        """Move selection down."""
        if self.categories:
            self.state.move_selection_down()
            self._update_detail_panel()
            try:
                table = self.query_one("#category-table", CategoryTable)
                table.move_down()
            except NoMatches:
                pass  # Table may not be mounted yet

    def action_move_up(self) -> None:
        """Move selection up."""
        if self.categories:
            self.state.move_selection_up()
            self._update_detail_panel()
            try:
                table = self.query_one("#category-table", CategoryTable)
                table.move_up()
            except NoMatches:
                pass  # Table may not be mounted yet

    def action_help(self) -> None:
        """Show help screen."""
        self.push_screen(HelpScreen())

    def action_quit_confirm(self) -> None:
        """Quit with confirmation."""

        def handle_quit(confirmed: bool | None) -> None:
            if confirmed:
                self.exit()

        self.push_screen(ConfirmQuitModal(), handle_quit)

    def on_data_table_row_highlighted(self, event) -> None:
        """Handle row highlight in the category table."""
        if event.cursor_row is not None:
            self._selected_index = event.cursor_row
            self._update_detail_panel()

    # -------------------------------------------------------------------------
    # Backward-compatible aliases
    # -------------------------------------------------------------------------

    def accept_category(self) -> None:
        """Alias for action_accept."""
        self.action_accept()

    def rename_category(self) -> None:
        """Alias for action_rename."""
        self.action_rename()

    def merge_category(self) -> None:
        """Alias for action_merge."""
        self.action_merge()

    def delete_category(self) -> None:
        """Alias for action_delete."""
        self.action_delete()

    def skip_category(self) -> None:
        """Alias for action_skip."""
        self.action_skip()
