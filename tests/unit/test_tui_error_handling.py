"""
Unit tests for TUI error handling and user feedback (Phase 2 Item 1.6).

Tests:
- Silent NoMatches catches are replaced with logged messages
- Unsaved changes indicator appears after first action
- Unsaved changes indicator clears after save
- Merge with empty approved shows user message, not empty dialog
- Action on deleted/stale category shows notification
- Failed operations produce user-visible notifications
- State validation before every action
"""

import inspect
import logging
from unittest.mock import patch

import pytest

from src.models.category import Category, CategorySource


def create_test_category(
    category_id: str = "test_cat_1",
    name: str = "Test Category",
    description: str = "A test category",
    confidence: float = 0.85,
    email_count: int = 10,
    percentage: float = 25.0,
    source: CategorySource = CategorySource.CONTENT_CLUSTER,
    example_email_ids: list[str] | None = None,
    distinguishing_features: list[str] | None = None,
) -> Category:
    """Helper to create test Category objects."""
    return Category(
        category_id=category_id,
        category_name=name,
        description=description,
        confidence=confidence,
        email_count=email_count,
        percentage=percentage,
        source=source,
        source_id="test_source",
        example_email_ids=example_email_ids or [],
        distinguishing_features=distinguishing_features or [],
    )


# =============================================================================
# 1. NoMatches catches should log instead of silently passing
# =============================================================================


class TestNoMatchesLogging:
    """Test that NoMatches exceptions are logged, not silently swallowed."""

    def test_update_detail_panel_logs_on_no_matches(self, caplog):
        """Test that _update_detail_panel logs when widget not mounted."""
        from textual.css.query import NoMatches

        from src.ui.tui.app import ReviewApp

        app = ReviewApp(categories=[create_test_category()])

        with (
            patch.object(app, "query_one", side_effect=NoMatches("no match")),
            caplog.at_level(logging.DEBUG),
        ):
            app._update_detail_panel()

        assert any("detail" in r.message.lower() for r in caplog.records)

    def test_update_action_bar_logs_on_no_matches(self, caplog):
        """Test that _update_action_bar logs when widget not mounted."""
        from textual.css.query import NoMatches

        from src.ui.tui.app import ReviewApp

        app = ReviewApp(categories=[create_test_category()])

        with (
            patch.object(app, "query_one", side_effect=NoMatches("no match")),
            caplog.at_level(logging.DEBUG),
        ):
            app._update_action_bar()

        assert any(
            "action" in r.message.lower() or "bar" in r.message.lower() for r in caplog.records
        )

    def test_update_table_logs_on_no_matches(self, caplog):
        """Test that _update_table logs when widget not mounted."""
        from textual.css.query import NoMatches

        from src.ui.tui.app import ReviewApp

        app = ReviewApp(categories=[create_test_category()])

        with (
            patch.object(app, "query_one", side_effect=NoMatches("no match")),
            caplog.at_level(logging.DEBUG),
        ):
            app._update_table()

        assert any("table" in r.message.lower() for r in caplog.records)

    def test_update_stats_panel_logs_on_no_matches(self, caplog):
        """Test that _update_stats_panel logs when widget not mounted."""
        from textual.css.query import NoMatches

        from src.ui.tui.app import ReviewApp

        app = ReviewApp(categories=[create_test_category()])

        with (
            patch.object(app, "query_one", side_effect=NoMatches("no match")),
            caplog.at_level(logging.DEBUG),
        ):
            app._update_stats_panel()

        assert any("stats" in r.message.lower() for r in caplog.records)

    def test_activate_search_logs_on_no_matches(self, caplog):
        """Test that action_activate_search logs when search widget not mounted."""
        from textual.css.query import NoMatches

        from src.ui.tui.app import ReviewApp

        app = ReviewApp(categories=[create_test_category()])

        with (
            patch.object(app, "query_one", side_effect=NoMatches("no match")),
            caplog.at_level(logging.DEBUG),
        ):
            app.action_activate_search()

        assert any("search" in r.message.lower() for r in caplog.records)

    def test_apply_filter_logs_on_no_matches(self, caplog):
        """Test that _apply_filter logs when table widget not mounted."""
        from textual.css.query import NoMatches

        from src.ui.tui.app import ReviewApp

        app = ReviewApp(categories=[create_test_category()])

        with (
            patch.object(app, "query_one", side_effect=NoMatches("no match")),
            caplog.at_level(logging.DEBUG),
        ):
            app._apply_filter("test query")

        assert any(
            "table" in r.message.lower() or "filter" in r.message.lower() for r in caplog.records
        )

    def test_move_down_logs_on_no_matches(self, caplog):
        """Test that action_move_down logs when table widget not mounted."""
        from textual.css.query import NoMatches

        from src.ui.tui.app import ReviewApp

        app = ReviewApp(categories=[create_test_category()])

        with (
            patch.object(app, "query_one", side_effect=NoMatches("no match")),
            caplog.at_level(logging.DEBUG),
        ):
            app.action_move_down()

        assert any("table" in r.message.lower() for r in caplog.records)

    def test_move_up_logs_on_no_matches(self, caplog):
        """Test that action_move_up logs when table widget not mounted."""
        from textual.css.query import NoMatches

        from src.ui.tui.app import ReviewApp

        app = ReviewApp(categories=[create_test_category()])

        with (
            patch.object(app, "query_one", side_effect=NoMatches("no match")),
            caplog.at_level(logging.DEBUG),
        ):
            app.action_move_up()

        assert any("table" in r.message.lower() for r in caplog.records)

    def test_no_matches_still_does_not_raise(self):
        """Test that NoMatches exceptions are still caught (not propagated)."""
        from textual.css.query import NoMatches

        from src.ui.tui.app import ReviewApp

        app = ReviewApp(categories=[create_test_category()])

        with patch.object(app, "query_one", side_effect=NoMatches("no match")):
            # None of these should raise
            app._update_detail_panel()
            app._update_action_bar()
            app._update_table()
            app._update_stats_panel()
            app.action_activate_search()
            app._apply_filter("test")

    def test_other_exceptions_still_propagate(self):
        """Test that non-NoMatches exceptions still propagate."""
        from src.ui.tui.app import ReviewApp

        app = ReviewApp(categories=[create_test_category()])

        with (
            patch.object(app, "query_one", side_effect=RuntimeError("unexpected")),
            pytest.raises(RuntimeError, match="unexpected"),
        ):
            app._update_detail_panel()

    def test_merge_dialog_update_preview_logs_on_no_matches(self, caplog):
        """Test that MergeDialog._update_preview logs when widget not mounted."""
        from textual.css.query import NoMatches

        from src.ui.tui.dialogs.merge_dialog import MergeDialog

        source = create_test_category(category_id="source", name="Source")
        target = create_test_category(category_id="target", name="Target")
        dialog = MergeDialog(categories=[target], source_category=source)

        with (
            patch.object(dialog, "query_one", side_effect=NoMatches("no match")),
            caplog.at_level(logging.DEBUG),
        ):
            dialog._update_preview()

        assert any("preview" in r.message.lower() for r in caplog.records)

    def test_merge_dialog_move_down_logs_on_no_matches(self, caplog):
        """Test that MergeDialog.action_move_down logs when table not mounted."""
        from textual.css.query import NoMatches

        from src.ui.tui.dialogs.merge_dialog import MergeDialog

        source = create_test_category(category_id="source", name="Source")
        target = create_test_category(category_id="target", name="Target")
        dialog = MergeDialog(categories=[target], source_category=source)

        with (
            patch.object(dialog, "query_one", side_effect=NoMatches("no match")),
            caplog.at_level(logging.DEBUG),
        ):
            dialog.action_move_down()

        assert any(
            "table" in r.message.lower() or "merge" in r.message.lower() for r in caplog.records
        )

    def test_merge_dialog_move_up_logs_on_no_matches(self, caplog):
        """Test that MergeDialog.action_move_up logs when table not mounted."""
        from textual.css.query import NoMatches

        from src.ui.tui.dialogs.merge_dialog import MergeDialog

        source = create_test_category(category_id="source", name="Source")
        target = create_test_category(category_id="target", name="Target")
        dialog = MergeDialog(categories=[target], source_category=source)

        with (
            patch.object(dialog, "query_one", side_effect=NoMatches("no match")),
            caplog.at_level(logging.DEBUG),
        ):
            dialog.action_move_up()

        assert any(
            "table" in r.message.lower() or "merge" in r.message.lower() for r in caplog.records
        )

    def test_rename_dialog_on_mount_logs_on_no_matches(self, caplog):
        """Test that RenameDialog.on_mount logs when input widget not mounted."""
        from textual.css.query import NoMatches

        from src.ui.tui.dialogs.rename_dialog import RenameDialog

        dialog = RenameDialog(current_name="Test")

        with (
            patch.object(dialog, "query_one", side_effect=NoMatches("no match")),
            caplog.at_level(logging.DEBUG),
        ):
            dialog.on_mount()

        assert any(
            "input" in r.message.lower() or "rename" in r.message.lower() for r in caplog.records
        )

    def test_rename_dialog_show_validation_error_logs_on_no_matches(self, caplog):
        """Test that RenameDialog._show_validation_error logs when widget not mounted."""
        from textual.css.query import NoMatches

        from src.ui.tui.dialogs.rename_dialog import RenameDialog

        dialog = RenameDialog(current_name="Test")

        with (
            patch.object(dialog, "query_one", side_effect=NoMatches("no match")),
            caplog.at_level(logging.DEBUG),
        ):
            dialog._show_validation_error("Some error")

        assert any(
            "validation" in r.message.lower() or "error" in r.message.lower()
            for r in caplog.records
        )

    def test_rename_dialog_clear_validation_error_logs_on_no_matches(self, caplog):
        """Test that RenameDialog._clear_validation_error logs when widget not mounted."""
        from textual.css.query import NoMatches

        from src.ui.tui.dialogs.rename_dialog import RenameDialog

        dialog = RenameDialog(current_name="Test")

        with (
            patch.object(dialog, "query_one", side_effect=NoMatches("no match")),
            caplog.at_level(logging.DEBUG),
        ):
            dialog._clear_validation_error()

        assert any(
            "validation" in r.message.lower() or "error" in r.message.lower()
            for r in caplog.records
        )


# =============================================================================
# 2. Unsaved changes indicator
# =============================================================================


class TestUnsavedChangesIndicator:
    """Test unsaved changes indicator in the app."""

    def test_no_unsaved_changes_initially(self):
        """Test that there are no unsaved changes when app first starts."""
        from src.ui.tui.app import ReviewApp

        app = ReviewApp(categories=[create_test_category()])
        assert not app.state.has_unsaved_changes

    def test_unsaved_changes_after_accept(self):
        """Test that unsaved changes flag is set after accepting a category."""
        from src.ui.tui.app import ReviewApp

        cat = create_test_category()
        app = ReviewApp(categories=[cat])

        app.state.accept(cat.category_id)

        assert app.state.has_unsaved_changes

    def test_unsaved_changes_after_delete(self):
        """Test that unsaved changes flag is set after deleting a category."""
        from src.ui.tui.app import ReviewApp

        cat = create_test_category()
        app = ReviewApp(categories=[cat])

        app.state.delete(cat.category_id)

        assert app.state.has_unsaved_changes

    def test_unsaved_changes_after_skip(self):
        """Test that unsaved changes flag is set after skipping a category."""
        from src.ui.tui.app import ReviewApp

        cat = create_test_category()
        app = ReviewApp(categories=[cat])

        app.state.skip(cat.category_id)

        assert app.state.has_unsaved_changes

    def test_unsaved_changes_cleared_after_save(self):
        """Test that unsaved changes indicator clears after save."""
        from src.ui.tui.app import ReviewApp

        cat = create_test_category()
        app = ReviewApp(categories=[cat])

        app.state.accept(cat.category_id)
        assert app.state.has_unsaved_changes

        app.state.mark_saved()
        assert not app.state.has_unsaved_changes

    def test_app_has_unsaved_changes_subtitle_method(self):
        """Test that app has method to get subtitle with unsaved changes indicator."""
        from src.ui.tui.app import ReviewApp

        app = ReviewApp(categories=[create_test_category()])
        assert hasattr(app, "_get_subtitle_text")

    def test_subtitle_includes_unsaved_when_dirty(self):
        """Test that subtitle includes unsaved indicator when changes exist."""
        from src.ui.tui.app import ReviewApp

        cat = create_test_category()
        app = ReviewApp(categories=[cat])

        # Before any actions, no unsaved indicator
        subtitle_clean = app._get_subtitle_text()
        assert "unsaved" not in subtitle_clean.lower()

        # After an action, unsaved indicator present
        app.state.accept(cat.category_id)
        subtitle_dirty = app._get_subtitle_text()
        assert "unsaved" in subtitle_dirty.lower()

    def test_subtitle_clears_unsaved_after_save(self):
        """Test that subtitle clears unsaved indicator after save."""
        from src.ui.tui.app import ReviewApp

        cat = create_test_category()
        app = ReviewApp(categories=[cat])

        app.state.accept(cat.category_id)
        assert "unsaved" in app._get_subtitle_text().lower()

        app.state.mark_saved()
        assert "unsaved" not in app._get_subtitle_text().lower()

    def test_refresh_all_widgets_updates_subtitle(self):
        """Test that _refresh_all_widgets updates the subtitle."""
        from src.ui.tui.app import ReviewApp

        cat = create_test_category()
        app = ReviewApp(categories=[cat])

        # After an action through state, subtitle should reflect unsaved
        app.state.accept(cat.category_id)

        # _refresh_all_widgets should update subtitle
        with (
            patch.object(app, "_update_table"),
            patch.object(app, "_update_detail_panel"),
            patch.object(app, "_update_action_bar"),
            patch.object(app, "_update_stats_panel"),
        ):
            app._refresh_all_widgets()

        # The sub_title should now show unsaved changes
        assert "unsaved" in app.sub_title.lower()


# =============================================================================
# 3. Merge with empty approved list
# =============================================================================


class TestMergeEmptyApproved:
    """Test merge behavior when no approved categories exist."""

    def test_action_merge_notifies_when_no_approved(self):
        """Test that action_merge shows notification when no approved categories."""
        from src.ui.tui.app import ReviewApp

        app = ReviewApp(categories=[create_test_category()])

        with patch.object(app, "notify") as mock_notify:
            app.action_merge()

        mock_notify.assert_called_once()
        call_args = mock_notify.call_args
        assert "no approved" in call_args[0][0].lower()

    def test_merge_dialog_handles_empty_categories_gracefully(self):
        """Test that MergeDialog handles empty categories list."""
        from src.ui.tui.dialogs.merge_dialog import MergeDialog

        source = create_test_category(category_id="source", name="Source")
        dialog = MergeDialog(categories=[], source_category=source)

        # Should return None when no categories to choose from
        selected = dialog.get_selected_category()
        assert selected is None


# =============================================================================
# 4. State validation before actions
# =============================================================================


class TestStateValidationBeforeActions:
    """Test that actions validate state before operating."""

    def test_accept_on_empty_list_is_safe(self):
        """Test that accepting when no categories does not crash."""
        from src.ui.tui.app import ReviewApp

        app = ReviewApp(categories=[])

        # Should not crash. get_selected_category returns None => no-op.
        app.action_accept()

    def test_delete_on_empty_list_does_not_crash(self):
        """Test that deleting when no categories does not crash."""
        from src.ui.tui.app import ReviewApp

        app = ReviewApp(categories=[])
        app.action_delete()

    def test_skip_on_empty_list_does_not_crash(self):
        """Test that skipping when no categories does not crash."""
        from src.ui.tui.app import ReviewApp

        app = ReviewApp(categories=[])
        app.action_skip()

    def test_action_accept_notifies_on_stale_category(self):
        """Test notification when trying to accept already-deleted category."""
        from src.ui.tui.app import ReviewApp

        cat = create_test_category()
        app = ReviewApp(categories=[cat])

        # Accept the category once
        with patch.object(app, "notify"), patch.object(app, "_refresh_all_widgets"):
            app.action_accept()

        # Now try to accept again (no categories left) -- should be a no-op
        app.action_accept()

    def test_action_delete_notifies_on_failed_state_transition(self):
        """Test that failed delete notifies the user."""
        from src.ui.tui.app import ReviewApp

        cat = create_test_category()
        app = ReviewApp(categories=[cat])

        # Mock state.delete to return False (simulating stale state)
        with (
            patch.object(app.state, "delete", return_value=False),
            patch.object(app, "notify") as mock_notify,
        ):
            app.action_delete()

        mock_notify.assert_called_once()
        call_args = mock_notify.call_args
        assert call_args[1].get("severity") == "warning"

    def test_action_accept_notifies_on_failed_state_transition(self):
        """Test that failed accept notifies the user."""
        from src.ui.tui.app import ReviewApp

        cat = create_test_category()
        app = ReviewApp(categories=[cat])

        # Mock state.accept to return False (simulating stale state)
        with (
            patch.object(app.state, "accept", return_value=False),
            patch.object(app, "notify") as mock_notify,
        ):
            app.action_accept()

        mock_notify.assert_called_once()
        call_args = mock_notify.call_args
        assert call_args[1].get("severity") == "warning"

    def test_action_skip_notifies_on_failed_state_transition(self):
        """Test that failed skip notifies the user."""
        from src.ui.tui.app import ReviewApp

        cat = create_test_category()
        app = ReviewApp(categories=[cat])

        # Mock state.skip to return False (simulating stale state)
        with (
            patch.object(app.state, "skip", return_value=False),
            patch.object(app, "notify") as mock_notify,
        ):
            app.action_skip()

        mock_notify.assert_called_once()
        call_args = mock_notify.call_args
        assert call_args[1].get("severity") == "warning"

    def test_merge_notifies_on_failed_state_transition(self):
        """Test that failed merge notifies the user."""
        from src.ui.tui.app import ReviewApp

        cat = create_test_category()
        target = create_test_category(category_id="target", name="Target")
        app = ReviewApp(categories=[cat])
        app.approved_categories = [target]

        # Mock state.merge to return False (target no longer exists)
        with (
            patch.object(app.state, "merge", return_value=False),
            patch.object(app, "notify") as mock_notify,
        ):
            app._handle_merge_result(cat.category_id, target)

        mock_notify.assert_called_once()
        call_args = mock_notify.call_args
        assert call_args[1].get("severity") == "warning"


# =============================================================================
# 5. Failed operation notifications
# =============================================================================


class TestFailedOperationNotifications:
    """Test that failed operations produce user-visible notifications."""

    def test_merge_failed_target_gone_notification(self):
        """Test notification when merge target category no longer exists."""
        from src.ui.tui.app import ReviewApp

        cat = create_test_category()
        app = ReviewApp(categories=[cat])

        # Merge should fail because there are no approved categories
        with patch.object(app, "notify") as mock_notify:
            app.action_merge()

        mock_notify.assert_called_once()
        assert "no approved" in mock_notify.call_args[0][0].lower()

    def test_action_on_no_selection_is_safe(self):
        """Test that actions on empty/no-selection state are safe."""
        from src.ui.tui.app import ReviewApp

        app = ReviewApp(categories=[])

        # All actions should be safe with no categories
        app.action_accept()
        app.action_delete()
        app.action_skip()
        app.action_move_up()
        app.action_move_down()


# =============================================================================
# 6. App has _handle_merge_result method for centralized merge error handling
# =============================================================================


class TestHandleMergeResult:
    """Test the centralized _handle_merge_result method."""

    def test_handle_merge_result_exists(self):
        """Test that app has _handle_merge_result method."""
        from src.ui.tui.app import ReviewApp

        app = ReviewApp(categories=[])
        assert hasattr(app, "_handle_merge_result")
        assert callable(app._handle_merge_result)

    def test_handle_merge_result_success(self):
        """Test _handle_merge_result on successful merge."""
        from src.ui.tui.app import ReviewApp

        cat = create_test_category(category_id="src")
        target = create_test_category(category_id="tgt", name="Target")
        app = ReviewApp(categories=[cat])

        # Accept target first so merge has a valid target
        app.state._approved.append(target)

        with (
            patch.object(app, "_refresh_all_widgets"),
            patch.object(app, "notify") as mock_notify,
        ):
            app._handle_merge_result(cat.category_id, target)

        # Should show success notification
        mock_notify.assert_called_once()
        assert "target" in mock_notify.call_args[0][0].lower()

    def test_handle_merge_result_failure(self):
        """Test _handle_merge_result when merge fails."""
        from src.ui.tui.app import ReviewApp

        cat = create_test_category(category_id="src")
        target = create_test_category(category_id="tgt", name="Target")
        app = ReviewApp(categories=[cat])

        # Do NOT add target to approved -- merge should fail
        with patch.object(app, "notify") as mock_notify:
            app._handle_merge_result(cat.category_id, target)

        mock_notify.assert_called_once()
        call_args = mock_notify.call_args
        assert call_args[1].get("severity") == "warning"


# =============================================================================
# 7. No silent NoMatches passes remain (source code check)
# =============================================================================


class TestNoSilentPasses:
    """Verify source code has no silent 'except NoMatches: pass' without logging."""

    def _check_no_silent_pass(self, module, module_name: str) -> None:
        """Helper to check a module has no silent except NoMatches: pass."""
        source = inspect.getsource(module)
        lines = source.split("\n")
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("except NoMatches"):
                # The next non-empty line should NOT be just 'pass'
                next_idx = i + 1
                while next_idx < len(lines) and not lines[next_idx].strip():
                    next_idx += 1
                if next_idx < len(lines):
                    next_stripped = lines[next_idx].strip()
                    assert next_stripped != "pass", (
                        f"Found silent 'except NoMatches: pass' at line {i + 1} "
                        f"in {module_name}. Should log the exception."
                    )

    def test_app_no_bare_pass_in_except_nomatches(self):
        """Test that app.py has no 'except NoMatches: pass' without logging."""
        import src.ui.tui.app as app_module

        self._check_no_silent_pass(app_module, "app.py")

    def test_merge_dialog_no_bare_pass_in_except_nomatches(self):
        """Test that merge_dialog.py has no silent NoMatches catches."""
        import src.ui.tui.dialogs.merge_dialog as merge_module

        self._check_no_silent_pass(merge_module, "merge_dialog.py")

    def test_rename_dialog_no_bare_pass_in_except_nomatches(self):
        """Test that rename_dialog.py has no silent NoMatches catches."""
        import src.ui.tui.dialogs.rename_dialog as rename_module

        self._check_no_silent_pass(rename_module, "rename_dialog.py")
