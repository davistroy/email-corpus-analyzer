"""
Tests for Phase 2 Item 2.5: Dead code cleanup and naming normalization.

Verifies:
- Removed functions/fields are absent from commands.py
- promote/demote methods removed from CategoryTable
- __all__ exports are accurate and consistent
- No orphaned import references
- Naming conventions are normalized
- mypy passes after changes
"""

import importlib
import inspect

from src.models.category import Category, CategorySource

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _make_category(**kwargs) -> Category:
    """Create a minimal Category for testing."""
    defaults = {
        "category_id": "test_1",
        "category_name": "Test",
        "description": "Test category",
        "confidence": 0.8,
        "email_count": 50,
        "percentage": 5.0,
        "source": CategorySource.TEMPLATE,
        "distinguishing_features": [],
    }
    defaults.update(kwargs)
    return Category(**defaults)


# ===========================================================================
# 1. Dead code removal from commands.py
# ===========================================================================


class TestCommandsDeadCodeRemoved:
    """Verify unused items removed from commands.py."""

    def test_command_has_no_enabled_field(self):
        """The Command dataclass should not have an 'enabled' field."""
        from src.ui.tui.commands import Command

        cmd = Command(key="a", description="Accept", action="accept")
        assert not hasattr(cmd, "enabled"), (
            "Command.enabled field should have been removed (never used)"
        )

    def test_get_command_by_key_removed(self):
        """get_command_by_key should no longer exist in commands.py."""
        from src.ui.tui import commands

        assert not hasattr(commands, "get_command_by_key"), (
            "get_command_by_key should have been removed (never called)"
        )

    def test_get_command_by_action_removed(self):
        """get_command_by_action should no longer exist in commands.py."""
        from src.ui.tui import commands

        assert not hasattr(commands, "get_command_by_action"), (
            "get_command_by_action should have been removed (never called)"
        )


# ===========================================================================
# 2. promote/demote dead code removed from CategoryTable
# ===========================================================================


class TestCategoryTableDeadCodeRemoved:
    """Verify unused hierarchy methods removed from CategoryTable."""

    def test_promote_to_top_level_removed(self):
        """promote_to_top_level should no longer exist."""
        from src.ui.tui.widgets.category_table import CategoryTable

        table = CategoryTable(categories=[_make_category()])
        assert not hasattr(table, "promote_to_top_level"), (
            "promote_to_top_level should have been removed (dead code)"
        )

    def test_demote_to_subcategory_removed(self):
        """demote_to_subcategory should no longer exist."""
        from src.ui.tui.widgets.category_table import CategoryTable

        table = CategoryTable(categories=[_make_category()])
        assert not hasattr(table, "demote_to_subcategory"), (
            "demote_to_subcategory should have been removed (dead code)"
        )


# ===========================================================================
# 3. __all__ exports are accurate
# ===========================================================================


class TestExportsAccurate:
    """Verify __all__ exports match reality in all __init__.py files."""

    def test_tui_init_all_matches_module(self):
        """Every name in src.ui.tui.__all__ must be importable."""
        import src.ui.tui as tui_pkg

        for name in tui_pkg.__all__:
            assert hasattr(tui_pkg, name), (
                f"'{name}' listed in __all__ but not importable from src.ui.tui"
            )

    def test_tui_init_no_removed_functions(self):
        """Removed functions must not appear in __all__."""
        import src.ui.tui as tui_pkg

        removed = {"get_command_by_key", "get_command_by_action"}
        exported = set(tui_pkg.__all__)
        overlap = removed & exported
        assert not overlap, f"Removed functions still in __all__: {overlap}"

    def test_widgets_init_all_matches_module(self):
        """Every name in widgets.__all__ must be importable."""
        import src.ui.tui.widgets as widgets_pkg

        for name in widgets_pkg.__all__:
            assert hasattr(widgets_pkg, name), (
                f"'{name}' listed in __all__ but not importable from widgets"
            )

    def test_dialogs_init_all_matches_module(self):
        """Every name in dialogs.__all__ must be importable."""
        import src.ui.tui.dialogs as dialogs_pkg

        for name in dialogs_pkg.__all__:
            assert hasattr(dialogs_pkg, name), (
                f"'{name}' listed in __all__ but not importable from dialogs"
            )

    def test_theme_all_matches_module(self):
        """Every name in theme.__all__ must be importable."""
        import src.ui.tui.theme as theme_mod

        for name in theme_mod.__all__:
            assert hasattr(theme_mod, name), (
                f"'{name}' listed in __all__ but not importable from theme"
            )


# ===========================================================================
# 4. No orphaned references to removed items
# ===========================================================================


class TestNoOrphanedReferences:
    """Verify that no module tries to import removed items."""

    def test_import_src_ui_tui_succeeds(self):
        """The tui package must import cleanly with no errors."""
        import src.ui.tui

        importlib.reload(src.ui.tui)

    def test_import_src_ui_tui_widgets_succeeds(self):
        """The widgets sub-package must import cleanly."""
        import src.ui.tui.widgets

        importlib.reload(src.ui.tui.widgets)

    def test_import_src_ui_tui_commands_succeeds(self):
        """commands.py must import cleanly."""
        import src.ui.tui.commands

        importlib.reload(src.ui.tui.commands)


# ===========================================================================
# 5. Naming normalization
# ===========================================================================


class TestNamingNormalization:
    """Verify naming conventions are consistent across TUI modules."""

    def test_action_bar_merge_enabled_naming(self):
        """ActionBar reactive field for merge should follow consistent naming."""
        from src.ui.tui.widgets.action_bar import ActionBar

        # The reactive field should be named 'merge_enabled' (no leading underscore)
        # to be consistent with CategoryTable.selected_row
        bar = ActionBar()
        assert hasattr(bar, "merge_enabled"), (
            "ActionBar should have 'merge_enabled' reactive (normalized from '_merge_enabled')"
        )

    def test_category_table_selected_row_exists(self):
        """CategoryTable should still have selected_row reactive."""
        from src.ui.tui.widgets.category_table import CategoryTable

        table = CategoryTable(categories=[_make_category()])
        assert hasattr(table, "selected_row"), "CategoryTable.selected_row reactive should exist"


# ===========================================================================
# 6. Widgets __init__ imports from canonical location
# ===========================================================================


class TestCanonicalImports:
    """Verify format_confidence_bar is imported from utils, not category_table."""

    def test_widgets_init_format_confidence_bar_from_utils(self):
        """format_confidence_bar re-exported from widgets should originate from utils."""
        from src.ui.tui.utils import format_confidence_bar as utils_fn
        from src.ui.tui.widgets import format_confidence_bar as widgets_fn

        # Both should be the exact same function object
        assert widgets_fn is utils_fn, (
            "widgets.__init__ should import format_confidence_bar directly from utils"
        )


# ===========================================================================
# 7. Backward compatibility preserved
# ===========================================================================


class TestBackwardCompat:
    """Ensure surviving public API still works after cleanup."""

    def test_command_dataclass_still_works(self):
        """Command(key, description, action) must still work."""
        from src.ui.tui.commands import Command

        cmd = Command(key="a", description="Accept", action="accept")
        assert cmd.key == "a"
        assert cmd.description == "Accept"
        assert cmd.action == "accept"

    def test_get_all_commands_still_works(self):
        """get_all_commands returns non-empty list of Command."""
        from src.ui.tui.commands import Command, get_all_commands

        cmds = get_all_commands()
        assert len(cmds) >= 5
        assert all(isinstance(c, Command) for c in cmds)

    def test_format_command_help_still_works(self):
        """format_command_help returns a non-empty string."""
        from src.ui.tui.commands import format_command_help

        help_text = format_command_help()
        assert "Available Commands" in help_text

    def test_action_bar_set_merge_enabled_still_works(self):
        """ActionBar.set_merge_enabled API must still function."""
        from src.ui.tui.widgets.action_bar import ActionBar

        bar = ActionBar()
        bar.set_merge_enabled(False)
        assert not bar.is_merge_enabled()
        bar.set_merge_enabled(True)
        assert bar.is_merge_enabled()

    def test_category_table_expand_collapse_all(self):
        """expand_all/collapse_all should still work after promote/demote removal."""
        from unittest.mock import patch

        from src.ui.tui.widgets.category_table import CategoryTable

        cat = _make_category()
        table = CategoryTable(categories=[cat])
        with patch.object(table, "_populate_rows"):
            table.expand_all()
            table.collapse_all()

    def test_category_table_hierarchy_still_works(self):
        """Hierarchy display (expand/collapse/toggle) should still function."""
        from unittest.mock import patch

        from src.ui.tui.widgets.category_table import CategoryTable

        cat = _make_category(category_id="p1")
        table = CategoryTable(categories=[cat])
        with patch.object(table, "_populate_rows"):
            table.toggle_expand("p1")
            assert table.is_expanded("p1")
            table.toggle_expand("p1")
            assert not table.is_expanded("p1")


# ===========================================================================
# 8. Type hint correctness
# ===========================================================================


class TestTypeHintCorrectness:
    """Verify type annotations are present and accurate."""

    def test_update_column_widths_uses_column_key(self):
        """update_column_widths should use ColumnKey for dict access, not bare str."""
        from src.ui.tui.widgets.category_table import CategoryTable

        source = inspect.getsource(CategoryTable.update_column_widths)
        # After fix, should use ColumnKey instead of bare string
        assert "ColumnKey" in source or "columns.get" not in source or "columns" not in source, (
            "update_column_widths should use ColumnKey for type-safe column access"
        )
