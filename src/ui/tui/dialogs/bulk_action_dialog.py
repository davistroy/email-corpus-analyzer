"""
Bulk action confirmation dialog for TUI.

Per Phase 8 Track 8B.1 specification.
Shows confirmation for bulk operations on multiple categories.
"""
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.screen import ModalScreen
from textual.widgets import Static

from src.models.category import Category


class BulkActionDialog(ModalScreen[bool]):
    """
    Modal dialog for confirming bulk actions on categories.

    Shows count of items affected and requires explicit confirmation.
    """

    BINDINGS = [
        Binding("y", "confirm", "Yes"),
        Binding("n", "cancel", "No"),
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(
        self,
        action: str,
        count: int,
        categories: list[Category],
        *args,
        **kwargs
    ):
        """
        Initialize bulk action dialog.

        Args:
            action: Action to perform ("accept", "delete")
            count: Number of categories affected
            categories: List of categories to be affected
        """
        super().__init__(*args, **kwargs)
        self.action = action
        self.count = count
        self.categories = categories

    def compose(self) -> ComposeResult:
        """Compose the modal content."""
        action_text = self.action.capitalize()
        yield Container(
            Static(f"Bulk {action_text}", classes="modal-title"),
            Static(
                f"Are you sure you want to {self.action} {self.count} categories?",
                classes="modal-subtitle",
            ),
            Static(
                self._get_category_preview(),
                classes="modal-preview",
            ),
            Static("[Y]es / [N]o", classes="modal-hint"),
            id="bulk-action-modal",
        )

    def _get_category_preview(self) -> str:
        """Get preview text of affected categories."""
        if not self.categories:
            return ""

        lines = []
        for cat in self.categories[:5]:  # Show first 5
            lines.append(f"  - {cat.category_name}")

        if len(self.categories) > 5:
            lines.append(f"  ... and {len(self.categories) - 5} more")

        return "\n".join(lines)

    def action_confirm(self) -> None:
        """Confirm the bulk action."""
        self.dismiss(True)

    def action_cancel(self) -> None:
        """Cancel the bulk action."""
        self.dismiss(False)
