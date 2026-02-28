"""
Rename dialog for the TUI application.

Modal text input dialog for renaming a category with validation.
"""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.css.query import NoMatches
from textual.screen import ModalScreen
from textual.widgets import Input, Static

# Maximum reasonable length for category names
MAX_NAME_LENGTH = 100


class RenameDialog(ModalScreen[str | None]):
    """
    Modal dialog for renaming a category.

    Features:
    - Shows current name
    - Text input for new name
    - Validation (non-empty, reasonable length)
    - Cancel/confirm with keyboard
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    CSS = """
    #rename-dialog {
        align: center middle;
        width: 60;
        height: auto;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }

    #rename-dialog .dialog-title {
        text-style: bold;
        text-align: center;
        width: 100%;
        margin-bottom: 1;
    }

    #rename-dialog .dialog-subtitle {
        color: $text-muted;
        margin-bottom: 1;
    }

    #rename-dialog .dialog-hint {
        color: $text-muted;
        text-align: center;
        margin-top: 1;
    }

    #rename-dialog .validation-error {
        color: $error;
        margin-top: 1;
    }

    #rename-dialog Input {
        width: 100%;
    }
    """

    def __init__(self, current_name: str, *args, **kwargs):
        """
        Initialize the rename dialog.

        Args:
            current_name: The current category name to show
        """
        super().__init__(*args, **kwargs)
        self.current_name = current_name

    def compose(self) -> ComposeResult:
        """Compose the dialog content."""
        yield Container(
            Static("Rename Category", classes="dialog-title"),
            Static(f"Current name: {self.current_name}", classes="dialog-subtitle"),
            Input(placeholder="Enter new name", id="rename-input"),
            Static("Press Enter to confirm, Escape to cancel", classes="dialog-hint"),
            Static("", id="validation-error", classes="validation-error"),
            id="rename-dialog",
        )

    def on_mount(self) -> None:
        """Focus the input when dialog opens."""
        try:
            input_widget = self.query_one("#rename-input", Input)
            input_widget.focus()
        except NoMatches:
            pass  # Input widget may not be mounted yet

    def validate_name(self, name: str) -> bool:
        """
        Validate the new category name.

        Args:
            name: The name to validate

        Returns:
            True if valid, False otherwise
        """
        stripped = name.strip()

        if not stripped:
            return False

        return not len(stripped) > MAX_NAME_LENGTH

    def get_validation_error(self, name: str) -> str | None:
        """
        Get validation error message for a name.

        Args:
            name: The name to validate

        Returns:
            Error message or None if valid
        """
        stripped = name.strip()

        if not stripped:
            return "Name cannot be empty"

        if len(stripped) > MAX_NAME_LENGTH:
            return f"Name too long (max {MAX_NAME_LENGTH} characters)"

        return None

    def _show_validation_error(self, error: str) -> None:
        """Show a validation error message."""
        try:
            error_widget = self.query_one("#validation-error", Static)
            error_widget.update(error)
        except NoMatches:
            pass  # Validation error widget may not be mounted yet

    def _clear_validation_error(self) -> None:
        """Clear the validation error message."""
        try:
            error_widget = self.query_one("#validation-error", Static)
            error_widget.update("")
        except NoMatches:
            pass  # Validation error widget may not be mounted yet

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission."""
        name = event.value.strip()
        error = self.get_validation_error(name)

        if error:
            self._show_validation_error(error)
            return

        self.dismiss(name)

    def on_input_changed(self, event: Input.Changed) -> None:
        """Clear error on input change."""
        self._clear_validation_error()

    def action_cancel(self) -> None:
        """Cancel the rename operation."""
        self.dismiss(None)
