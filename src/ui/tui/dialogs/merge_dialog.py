"""
Merge selection dialog for the TUI application.

Modal dialog for selecting a category to merge into with preview.
"""
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import DataTable, Static

from src.models.category import Category


class MergeDialog(ModalScreen[Category | None]):
    """
    Modal dialog for selecting a category to merge into.

    Features:
    - Shows list of approved categories
    - Keyboard navigation and selection
    - Preview of merged result
    - Cancel/confirm with keyboard
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("j", "move_down", "Down"),
        Binding("k", "move_up", "Up"),
        Binding("down", "move_down", "Down"),
        Binding("up", "move_up", "Up"),
        Binding("enter", "select_category", "Select"),
    ]

    CSS = """
    #merge-dialog {
        align: center middle;
        width: 80;
        height: auto;
        max-height: 80%;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }

    #merge-dialog .dialog-title {
        text-style: bold;
        text-align: center;
        width: 100%;
        margin-bottom: 1;
    }

    #merge-dialog .dialog-subtitle {
        color: $text-muted;
        margin-bottom: 1;
    }

    #merge-dialog .dialog-hint {
        color: $text-muted;
        text-align: center;
        margin-top: 1;
    }

    #merge-dialog .preview-section {
        border: solid $secondary;
        padding: 1;
        margin-top: 1;
    }

    #merge-dialog .preview-title {
        color: $text-muted;
        text-style: italic;
    }

    #merge-dialog DataTable {
        height: auto;
        max-height: 15;
    }
    """

    selected_index: reactive[int] = reactive(0)

    def __init__(
        self,
        categories: list[Category],
        source_category: Category,
        *args,
        **kwargs
    ):
        """
        Initialize the merge dialog.

        Args:
            categories: List of approved categories to merge into
            source_category: The category being merged (source)
        """
        super().__init__(*args, **kwargs)
        self.merge_categories = list(categories)
        self.source_category = source_category

    def compose(self) -> ComposeResult:
        """Compose the dialog content."""
        yield Container(
            Static("Merge Into Category", classes="dialog-title"),
            Static(
                f"Merging: {self.source_category.category_name}",
                classes="dialog-subtitle"
            ),
            Static("Select a category to merge into:", classes="dialog-subtitle"),
            DataTable(id="merge-table", cursor_type="row"),
            Vertical(
                Static("Preview:", classes="preview-title"),
                Static("Select a category to see preview", id="merge-preview"),
                classes="preview-section",
            ),
            Static(
                "Press Enter to select, j/k or arrows to navigate, Escape to cancel",
                classes="dialog-hint"
            ),
            id="merge-dialog",
        )

    def on_mount(self) -> None:
        """Set up the table when dialog opens."""
        table = self.query_one("#merge-table", DataTable)
        table.add_column("#", key="index", width=4)
        table.add_column("Name", key="name", width=30)
        table.add_column("Emails", key="emails", width=10)
        table.add_column("Confidence", key="confidence", width=12)

        for idx, category in enumerate(self.merge_categories, 1):
            confidence_str = f"{category.confidence * 100:.0f}%"
            email_str = str(category.email_count) if category.email_count else "-"
            table.add_row(
                str(idx),
                category.category_name[:28],
                email_str,
                confidence_str,
                key=category.category_id,
            )

        table.focus()
        self._update_preview()

    def get_merge_preview(self, target: Category) -> str:
        """
        Get preview text for merging into a target category.

        Args:
            target: The target category to merge into

        Returns:
            Preview text showing combined result
        """
        source_count = self.source_category.email_count or 0
        target_count = target.email_count or 0
        combined_count = source_count + target_count

        lines = [
            f"Target: {target.category_name}",
            f"Combined emails: {combined_count}",
            f"  ({target_count} + {source_count})",
        ]
        return "\n".join(lines)

    def get_selected_category(self) -> Category | None:
        """
        Get the currently selected category.

        Returns:
            Selected Category or None if no selection
        """
        if not self.merge_categories:
            return None

        if self.selected_index < 0 or self.selected_index >= len(self.merge_categories):
            return None

        return self.merge_categories[self.selected_index]

    def _update_preview(self) -> None:
        """Update the merge preview display."""
        try:
            preview_widget = self.query_one("#merge-preview", Static)
            selected = self.get_selected_category()

            if selected:
                preview_widget.update(self.get_merge_preview(selected))
            else:
                preview_widget.update("No category selected")
        except Exception:
            pass

    def action_move_down(self) -> None:
        """Move selection down."""
        if self.merge_categories:
            self.selected_index = (self.selected_index + 1) % len(self.merge_categories)
            try:
                table = self.query_one("#merge-table", DataTable)
                table.move_cursor(row=self.selected_index)
            except Exception:
                pass
            self._update_preview()

    def action_move_up(self) -> None:
        """Move selection up."""
        if self.merge_categories:
            self.selected_index = (self.selected_index - 1) % len(self.merge_categories)
            try:
                table = self.query_one("#merge-table", DataTable)
                table.move_cursor(row=self.selected_index)
            except Exception:
                pass
            self._update_preview()

    def action_select_category(self) -> None:
        """Select the current category and dismiss."""
        selected = self.get_selected_category()
        self.dismiss(selected)

    def action_cancel(self) -> None:
        """Cancel the merge operation."""
        self.dismiss(None)

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """Handle row highlight event."""
        if event.cursor_row is not None:
            self.selected_index = event.cursor_row
            self._update_preview()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection event."""
        selected = self.get_selected_category()
        self.dismiss(selected)
