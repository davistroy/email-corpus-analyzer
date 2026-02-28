"""
TUI dialogs package.

Provides modal dialog components for the Category Review TUI.
Phase 8 Track 8B.1: Added BulkActionDialog for bulk operations.
Phase 3 Item 3.5: Added RuleEditorDialog for rule condition editing.
"""

from src.ui.tui.dialogs.bulk_action_dialog import BulkActionDialog
from src.ui.tui.dialogs.merge_dialog import MergeDialog
from src.ui.tui.dialogs.rename_dialog import RenameDialog
from src.ui.tui.dialogs.rule_editor_dialog import RuleEditorDialog

__all__ = [
    "RenameDialog",
    "MergeDialog",
    "BulkActionDialog",
    "RuleEditorDialog",
]
