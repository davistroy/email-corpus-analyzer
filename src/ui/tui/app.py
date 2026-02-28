"""
Main TUI application for category review.

Provides an interactive terminal-based interface for reviewing,
approving, and modifying suggested email categories.
"""

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.css.query import NoMatches
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import Footer, Header, Input, Static

from src.models.category import Category
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
        self.categories = categories
        self.email_lookup = email_lookup or {}
        self.approved_categories: list[Category] = []
        self.skipped_categories: list[Category] = []
        self.modified_count = 0
        self.merged_count = 0
        self.deleted_count = 0
        self._selected_index = 0

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

    def get_selected_category(self) -> Category | None:
        """
        Get the currently selected category.

        Returns:
            Selected Category or None if no selection
        """
        if not self.categories:
            return None
        if self._selected_index < 0 or self._selected_index >= len(self.categories):
            return None
        return self.categories[self._selected_index]

    def get_approved_categories(self) -> list[Category]:
        """
        Get all approved categories.

        Returns:
            List of approved categories
        """
        return self.approved_categories.copy()

    def get_stats(self) -> dict:
        """
        Get review statistics.

        Returns:
            Dictionary with modification stats
        """
        return {
            "modified": self.modified_count,
            "merged": self.merged_count,
            "deleted": self.deleted_count,
            "approved": len(self.approved_categories),
            "skipped": len(self.skipped_categories),
            "remaining": len(self.categories),
        }

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

    def _remove_current_category(self) -> Category | None:
        """Remove and return the current category from the list."""
        category = self.get_selected_category()
        if category and category in self.categories:
            self.categories.remove(category)
            # Adjust selection
            if self._selected_index >= len(self.categories):
                self._selected_index = max(0, len(self.categories) - 1)
            self._update_table()
            self._update_detail_panel()
        return category

    # Action methods

    def action_accept(self) -> None:
        """Accept the current category."""
        category = self._remove_current_category()
        if category:
            self.approved_categories.append(category)
            self._update_action_bar()
            self.notify(f"Accepted: {category.category_name}")

    def action_rename(self) -> None:
        """Rename the current category."""
        category = self.get_selected_category()
        if not category:
            return

        def handle_rename(new_name: str | None) -> None:
            if new_name:
                old_name = category.category_name
                category.category_name = new_name
                category.user_modified = True
                self._remove_current_category()
                self.approved_categories.append(category)
                self.modified_count += 1
                self._update_action_bar()
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

        def handle_merge(target: Category | None) -> None:
            if target:
                # Merge email IDs
                all_ids = set(target.example_email_ids) | set(category.example_email_ids)
                target.example_email_ids = list(all_ids)[:10]
                target.email_count = (target.email_count or 0) + (category.email_count or 0)
                target.user_modified = True
                self._remove_current_category()
                self.merged_count += 1
                self.notify(f"Merged into: {target.category_name}")

        self.push_screen(MergeModal(self.approved_categories), handle_merge)

    def action_delete(self) -> None:
        """Delete the current category."""
        category = self._remove_current_category()
        if category:
            self.deleted_count += 1
            self.notify(f"Deleted: {category.category_name}")

    def action_skip(self) -> None:
        """Skip the current category for later review."""
        category = self._remove_current_category()
        if category:
            self.skipped_categories.append(category)
            self.notify(f"Skipped: {category.category_name}")

    def action_move_down(self) -> None:
        """Move selection down."""
        if self.categories:
            self._selected_index = (self._selected_index + 1) % len(self.categories)
            self._update_detail_panel()
            try:
                table = self.query_one("#category-table", CategoryTable)
                table.move_down()
            except NoMatches:
                pass  # Table may not be mounted yet

    def action_move_up(self) -> None:
        """Move selection up."""
        if self.categories:
            self._selected_index = (self._selected_index - 1) % len(self.categories)
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
