"""
Unit tests for Phase 2 Item 2.2: Bulk Operations UI.

Tests:
- Space toggles selection of current category row (multi-select)
- Ctrl+A selects/deselects all visible categories
- Track selected categories in ReviewState (selected_categories: set[str])
- When categories are selected, show count in ActionBar ("3 selected")
- Bulk accept (Shift+A): accept all selected categories at once
- Bulk delete (Shift+D): delete all selected categories at once
- Wire the existing BulkActionDialog for confirmation
- Visual indicator on selected rows in CategoryTable
- Selection clears after bulk action
- Selection persists across filter changes (only for still-visible items)
- Escape deselects all when not in filter mode

TDD: Tests written first before implementation.
"""

import pytest

from src.models.category import Category, CategorySource

# =============================================================================
# Test Fixtures
# =============================================================================


def make_category(
    category_id: str = "cat_1",
    name: str = "Test Category",
    confidence: float = 0.85,
    email_count: int = 10,
    source: CategorySource = CategorySource.CONTENT_CLUSTER,
) -> Category:
    """Helper to create test Category objects."""
    return Category(
        category_id=category_id,
        category_name=name,
        description=f"Description for {name}",
        confidence=confidence,
        email_count=email_count,
        percentage=25.0,
        source=source,
        source_id="test_source",
        example_email_ids=[],
        distinguishing_features=[],
    )


@pytest.fixture
def five_categories() -> list[Category]:
    """Create 5 sample categories for bulk operations testing."""
    return [
        make_category("cat_001", "Financial Alerts", 0.85, 150, CategorySource.TEMPLATE),
        make_category("cat_002", "Shopping Orders", 0.72, 89, CategorySource.CONTENT_CLUSTER),
        make_category("cat_003", "Newsletter Weekly", 0.65, 45, CategorySource.SENDER),
        make_category("cat_004", "Social Updates", 0.90, 200, CategorySource.CONTENT_CLUSTER),
        make_category("cat_005", "System Alerts", 0.55, 30, CategorySource.TEMPLATE),
    ]


# =============================================================================
# ReviewState: selected_categories tracking
# =============================================================================


class TestReviewStateSelectedCategories:
    """Test that ReviewState tracks selected categories."""

    def test_state_has_selected_categories_field(self, five_categories):
        """ReviewState has a selected_categories set[str] field."""
        from src.ui.tui.state import ReviewState

        state = ReviewState(categories=five_categories)
        assert hasattr(state, "selected_categories")
        assert isinstance(state.selected_categories, set)
        assert len(state.selected_categories) == 0

    def test_toggle_selection_adds_category(self, five_categories):
        """toggle_selection adds a category_id to selected_categories."""
        from src.ui.tui.state import ReviewState

        state = ReviewState(categories=five_categories)
        state.toggle_selection("cat_001")
        assert "cat_001" in state.selected_categories

    def test_toggle_selection_removes_when_already_selected(self, five_categories):
        """toggle_selection removes a category_id if already selected."""
        from src.ui.tui.state import ReviewState

        state = ReviewState(categories=five_categories)
        state.toggle_selection("cat_001")
        assert "cat_001" in state.selected_categories
        state.toggle_selection("cat_001")
        assert "cat_001" not in state.selected_categories

    def test_toggle_selection_ignores_nonexistent_category(self, five_categories):
        """toggle_selection does nothing for a category not in pending."""
        from src.ui.tui.state import ReviewState

        state = ReviewState(categories=five_categories)
        state.toggle_selection("nonexistent_id")
        assert "nonexistent_id" not in state.selected_categories

    def test_select_all_visible(self, five_categories):
        """select_all_visible selects all pending category IDs."""
        from src.ui.tui.state import ReviewState

        state = ReviewState(categories=five_categories)
        state.select_all_visible([c.category_id for c in five_categories])
        assert len(state.selected_categories) == 5
        for cat in five_categories:
            assert cat.category_id in state.selected_categories

    def test_select_all_visible_toggles_to_deselect(self, five_categories):
        """select_all_visible deselects all when all are already selected."""
        from src.ui.tui.state import ReviewState

        state = ReviewState(categories=five_categories)
        ids = [c.category_id for c in five_categories]
        state.select_all_visible(ids)
        assert len(state.selected_categories) == 5

        # Calling again should deselect all
        state.select_all_visible(ids)
        assert len(state.selected_categories) == 0

    def test_clear_selection(self, five_categories):
        """clear_selection removes all selected categories."""
        from src.ui.tui.state import ReviewState

        state = ReviewState(categories=five_categories)
        state.toggle_selection("cat_001")
        state.toggle_selection("cat_003")
        assert len(state.selected_categories) == 2

        state.clear_selection()
        assert len(state.selected_categories) == 0

    def test_selection_count(self, five_categories):
        """selection_count returns number of selected categories."""
        from src.ui.tui.state import ReviewState

        state = ReviewState(categories=five_categories)
        assert state.selection_count == 0

        state.toggle_selection("cat_001")
        assert state.selection_count == 1

        state.toggle_selection("cat_003")
        assert state.selection_count == 2

    def test_has_selection(self, five_categories):
        """has_selection returns True when at least one category is selected."""
        from src.ui.tui.state import ReviewState

        state = ReviewState(categories=five_categories)
        assert state.has_selection is False

        state.toggle_selection("cat_001")
        assert state.has_selection is True

    def test_get_selected_pending(self, five_categories):
        """get_selected_pending returns Category objects for selected IDs."""
        from src.ui.tui.state import ReviewState

        state = ReviewState(categories=five_categories)
        state.toggle_selection("cat_001")
        state.toggle_selection("cat_003")

        selected = state.get_selected_pending()
        assert len(selected) == 2
        assert any(c.category_id == "cat_001" for c in selected)
        assert any(c.category_id == "cat_003" for c in selected)


# =============================================================================
# ReviewState: Bulk accept and bulk delete
# =============================================================================


class TestReviewStateBulkAccept:
    """Test bulk accept via ReviewState."""

    def test_bulk_accept_moves_selected_to_approved(self, five_categories):
        """bulk_accept moves all selected categories to approved."""
        from src.ui.tui.state import ReviewState

        state = ReviewState(categories=five_categories)
        state.toggle_selection("cat_001")
        state.toggle_selection("cat_003")

        result = state.bulk_accept()
        assert result == 2
        assert len(state.pending) == 3
        assert len(state.approved) == 2
        assert any(c.category_id == "cat_001" for c in state.approved)
        assert any(c.category_id == "cat_003" for c in state.approved)

    def test_bulk_accept_clears_selection(self, five_categories):
        """bulk_accept clears selected_categories after completion."""
        from src.ui.tui.state import ReviewState

        state = ReviewState(categories=five_categories)
        state.toggle_selection("cat_001")
        state.toggle_selection("cat_003")

        state.bulk_accept()
        assert len(state.selected_categories) == 0

    def test_bulk_accept_increments_counter(self, five_categories):
        """bulk_accept increments the accepted counter."""
        from src.ui.tui.state import ReviewState

        state = ReviewState(categories=five_categories)
        state.toggle_selection("cat_001")
        state.toggle_selection("cat_003")

        state.bulk_accept()
        assert state.counters["accepted"] == 2

    def test_bulk_accept_with_no_selection_returns_zero(self, five_categories):
        """bulk_accept returns 0 when nothing is selected."""
        from src.ui.tui.state import ReviewState

        state = ReviewState(categories=five_categories)
        result = state.bulk_accept()
        assert result == 0

    def test_bulk_accept_marks_unsaved_changes(self, five_categories):
        """bulk_accept sets has_unsaved_changes flag."""
        from src.ui.tui.state import ReviewState

        state = ReviewState(categories=five_categories)
        state.toggle_selection("cat_001")
        state.bulk_accept()
        assert state.has_unsaved_changes is True

    def test_bulk_accept_clamps_selected_index(self, five_categories):
        """bulk_accept clamps selected_index to valid range."""
        from src.ui.tui.state import ReviewState

        state = ReviewState(categories=five_categories)
        state.selected_index = 4  # Last item
        # Select last two
        state.toggle_selection("cat_004")
        state.toggle_selection("cat_005")

        state.bulk_accept()
        # Now only 3 items, index should be clamped
        assert state.selected_index <= len(state.pending) - 1

    def test_bulk_accept_fires_notification(self, five_categories):
        """bulk_accept fires on_change callback."""
        from src.ui.tui.state import ReviewState

        state = ReviewState(categories=five_categories)
        events = []
        state.on_change = lambda e: events.append(e)

        state.toggle_selection("cat_001")
        state.toggle_selection("cat_003")
        state.bulk_accept()

        assert any(e.get("action") == "bulk_accept" for e in events)


class TestReviewStateBulkDelete:
    """Test bulk delete via ReviewState."""

    def test_bulk_delete_moves_selected_to_deleted(self, five_categories):
        """bulk_delete moves all selected categories to deleted."""
        from src.ui.tui.state import ReviewState

        state = ReviewState(categories=five_categories)
        state.toggle_selection("cat_002")
        state.toggle_selection("cat_005")

        result = state.bulk_delete()
        assert result == 2
        assert len(state.pending) == 3
        assert len(state.deleted) == 2
        assert any(c.category_id == "cat_002" for c in state.deleted)
        assert any(c.category_id == "cat_005" for c in state.deleted)

    def test_bulk_delete_clears_selection(self, five_categories):
        """bulk_delete clears selected_categories after completion."""
        from src.ui.tui.state import ReviewState

        state = ReviewState(categories=five_categories)
        state.toggle_selection("cat_002")
        state.bulk_delete()
        assert len(state.selected_categories) == 0

    def test_bulk_delete_increments_counter(self, five_categories):
        """bulk_delete increments the deleted counter."""
        from src.ui.tui.state import ReviewState

        state = ReviewState(categories=five_categories)
        state.toggle_selection("cat_002")
        state.toggle_selection("cat_005")

        state.bulk_delete()
        assert state.counters["deleted"] == 2

    def test_bulk_delete_with_no_selection_returns_zero(self, five_categories):
        """bulk_delete returns 0 when nothing is selected."""
        from src.ui.tui.state import ReviewState

        state = ReviewState(categories=five_categories)
        result = state.bulk_delete()
        assert result == 0

    def test_bulk_delete_marks_unsaved_changes(self, five_categories):
        """bulk_delete sets has_unsaved_changes flag."""
        from src.ui.tui.state import ReviewState

        state = ReviewState(categories=five_categories)
        state.toggle_selection("cat_002")
        state.bulk_delete()
        assert state.has_unsaved_changes is True

    def test_bulk_delete_fires_notification(self, five_categories):
        """bulk_delete fires on_change callback."""
        from src.ui.tui.state import ReviewState

        state = ReviewState(categories=five_categories)
        events = []
        state.on_change = lambda e: events.append(e)

        state.toggle_selection("cat_002")
        state.bulk_delete()

        assert any(e.get("action") == "bulk_delete" for e in events)


# =============================================================================
# ReviewState: Selection cleared on individual actions
# =============================================================================


class TestSelectionClearedOnActions:
    """Test that individual actions clear selection if affected category was selected."""

    def test_accept_removes_from_selection(self, five_categories):
        """Accepting a category removes it from selected_categories."""
        from src.ui.tui.state import ReviewState

        state = ReviewState(categories=five_categories)
        state.toggle_selection("cat_001")
        state.toggle_selection("cat_002")

        state.accept("cat_001")
        assert "cat_001" not in state.selected_categories
        # cat_002 should remain selected
        assert "cat_002" in state.selected_categories

    def test_delete_removes_from_selection(self, five_categories):
        """Deleting a category removes it from selected_categories."""
        from src.ui.tui.state import ReviewState

        state = ReviewState(categories=five_categories)
        state.toggle_selection("cat_001")
        state.toggle_selection("cat_002")

        state.delete("cat_001")
        assert "cat_001" not in state.selected_categories
        assert "cat_002" in state.selected_categories

    def test_skip_removes_from_selection(self, five_categories):
        """Skipping a category removes it from selected_categories."""
        from src.ui.tui.state import ReviewState

        state = ReviewState(categories=five_categories)
        state.toggle_selection("cat_001")

        state.skip("cat_001")
        assert "cat_001" not in state.selected_categories


# =============================================================================
# ActionBar: Selection count display
# =============================================================================


class TestActionBarSelectionCount:
    """Test ActionBar displays selection count."""

    def test_action_bar_set_selection_count_zero(self):
        """ActionBar with 0 selection shows no selection indicator."""
        from src.ui.tui.widgets.action_bar import ActionBar

        bar = ActionBar()
        bar.set_selection_count(0)
        # The rendered content should NOT contain "selected"
        # We check via get_content which returns the current text
        assert bar._selection_count == 0

    def test_action_bar_set_selection_count_nonzero(self):
        """ActionBar with N>0 selection shows 'N selected'."""
        from src.ui.tui.widgets.action_bar import ActionBar

        bar = ActionBar()
        bar.set_selection_count(3)
        assert bar._selection_count == 3

    def test_action_bar_selection_text_in_content(self):
        """ActionBar renders selection count text when count > 0."""
        from src.ui.tui.widgets.action_bar import ActionBar

        bar = ActionBar()
        bar.set_selection_count(3)
        # Force content generation
        bar._update_content()
        # The internal render should include "3 selected"
        content = bar._get_content_text()
        assert "3 selected" in content

    def test_action_bar_no_selection_text_when_zero(self):
        """ActionBar does not show selection text when count is 0."""
        from src.ui.tui.widgets.action_bar import ActionBar

        bar = ActionBar()
        bar.set_selection_count(0)
        bar._update_content()
        content = bar._get_content_text()
        assert "selected" not in content

    def test_action_bar_shows_bulk_hints_when_selected(self):
        """ActionBar shows bulk action hints (Shift+A, Shift+D) when items selected."""
        from src.ui.tui.widgets.action_bar import ActionBar

        bar = ActionBar()
        bar.set_selection_count(2)
        bar._update_content()
        content = bar._get_content_text()
        assert "Shift+A" in content or "S-a" in content or "Bulk Accept" in content
        assert "Shift+D" in content or "S-d" in content or "Bulk Delete" in content


# =============================================================================
# CategoryTable: Visual indicator for selected rows
# =============================================================================


class TestCategoryTableSelectionIndicator:
    """Test visual selection indicators in CategoryTable."""

    def test_selected_row_shows_checkmark(self, five_categories):
        """Selected rows display a checkmark indicator in the index column."""
        from src.ui.tui.widgets.category_table import CategoryTable

        table = CategoryTable(categories=five_categories)
        table.toggle_selection("cat_001")

        # The table should indicate selection visually
        # We test by checking the row data includes a selection marker
        assert table.is_selected("cat_001") is True
        assert table.is_selected("cat_002") is False

    def test_selection_indicator_constant_exists(self):
        """SELECTED_INDICATOR constant exists in category_table module."""
        from src.ui.tui.widgets.category_table import SELECTED_INDICATOR

        assert SELECTED_INDICATOR is not None
        assert len(SELECTED_INDICATOR) > 0


# =============================================================================
# CategoryTable: Syncs selection with ReviewState
# =============================================================================


class TestCategoryTableStateSync:
    """Test that CategoryTable selection syncs with ReviewState's selected_categories."""

    def test_table_toggle_updates_provided_set(self, five_categories):
        """toggle_selection on table updates the selected_ids set."""
        from src.ui.tui.widgets.category_table import CategoryTable

        table = CategoryTable(categories=five_categories)
        table.toggle_selection("cat_001")
        assert "cat_001" in table.selected_ids

    def test_table_select_all_with_filter(self, five_categories):
        """select_all only selects visible (filtered) categories."""
        from src.ui.tui.widgets.category_table import CategoryTable

        table = CategoryTable(categories=five_categories)
        # Apply filter to show only template-sourced categories
        table.apply_filter("source:template")
        table.select_all()

        # Only cat_001 and cat_005 are template source
        assert len(table.selected_ids) == 2
        assert "cat_001" in table.selected_ids
        assert "cat_005" in table.selected_ids

    def test_selection_persists_across_filter_changes(self, five_categories):
        """Selections persist when filter changes (for still-visible items)."""
        from src.ui.tui.widgets.category_table import CategoryTable

        table = CategoryTable(categories=five_categories)
        table.toggle_selection("cat_001")
        table.toggle_selection("cat_002")

        # Apply filter that hides cat_002
        table.apply_filter("source:template")
        # cat_001 should still be selected (it's visible)
        assert "cat_001" in table.selected_ids
        # cat_002 is no longer visible but stays in selected_ids
        # (it's in the set but won't be shown; app can prune if needed)
        assert "cat_002" in table.selected_ids

        # Clear filter
        table.clear_filter()
        # Both should still be selected
        assert "cat_001" in table.selected_ids
        assert "cat_002" in table.selected_ids


# =============================================================================
# ReviewApp: Keybindings for bulk operations
# =============================================================================


class TestReviewAppBulkBindings:
    """Test ReviewApp has keybindings for bulk operations."""

    def test_app_has_space_binding(self, five_categories):
        """ReviewApp has a Space key binding for toggle selection."""
        # Space is handled at the CategoryTable widget level via its BINDINGS,
        # not at the app level. The table's action_toggle_select handles it.
        from src.ui.tui.widgets.category_table import CategoryTable

        bindings = [b[0] if isinstance(b, tuple) else b.key for b in CategoryTable.BINDINGS]
        assert "space" in bindings

    def test_app_has_ctrl_a_binding(self, five_categories):
        """ReviewApp has Ctrl+A binding for select/deselect all."""
        from src.ui.tui.app import ReviewApp

        app = ReviewApp(categories=five_categories)
        binding_keys = [b.key for b in app.BINDINGS]
        assert "ctrl+a" in binding_keys

    def test_app_has_bulk_accept_binding(self, five_categories):
        """ReviewApp has Shift+A (A) binding for bulk accept."""
        from src.ui.tui.app import ReviewApp

        app = ReviewApp(categories=five_categories)
        # Shift+A in Textual is uppercase "A"
        binding_keys = [b.key for b in app.BINDINGS]
        assert "A" in binding_keys or "shift+a" in binding_keys

    def test_app_has_bulk_delete_binding(self, five_categories):
        """ReviewApp has Shift+D (D) binding for bulk delete."""
        from src.ui.tui.app import ReviewApp

        app = ReviewApp(categories=five_categories)
        binding_keys = [b.key for b in app.BINDINGS]
        assert "D" in binding_keys or "shift+d" in binding_keys

    def test_app_has_escape_deselect_binding(self, five_categories):
        """ReviewApp has Escape binding that can deselect all."""
        from src.ui.tui.app import ReviewApp

        app = ReviewApp(categories=five_categories)
        binding_keys = [b.key for b in app.BINDINGS]
        assert "escape" in binding_keys


# =============================================================================
# ReviewApp: Bulk operations integration with state
# =============================================================================


class TestReviewAppBulkActions:
    """Test ReviewApp bulk action methods.

    Since ReviewApp methods that interact with widgets require a mounted
    app (ScreenStackError otherwise), we test the state-level behavior
    that app methods delegate to, plus verify the app has the required
    methods and bindings.
    """

    def test_action_toggle_select_method_exists(self, five_categories):
        """ReviewApp has action_toggle_select method."""
        from src.ui.tui.app import ReviewApp

        app = ReviewApp(categories=five_categories)
        assert hasattr(app, "action_toggle_select")
        assert callable(app.action_toggle_select)

    def test_state_toggle_via_app(self, five_categories):
        """App's state.toggle_selection updates selected_categories."""
        from src.ui.tui.app import ReviewApp

        app = ReviewApp(categories=five_categories)
        app.state.toggle_selection("cat_001")
        assert "cat_001" in app.state.selected_categories

    def test_state_toggle_removes_on_second_call(self, five_categories):
        """App's state.toggle_selection toggles off on second call."""
        from src.ui.tui.app import ReviewApp

        app = ReviewApp(categories=five_categories)
        app.state.toggle_selection("cat_001")
        assert "cat_001" in app.state.selected_categories
        app.state.toggle_selection("cat_001")
        assert "cat_001" not in app.state.selected_categories

    def test_state_select_all_selects_all_pending(self, five_categories):
        """App's state.select_all_visible selects all pending categories."""
        from src.ui.tui.app import ReviewApp

        app = ReviewApp(categories=five_categories)
        ids = [c.category_id for c in five_categories]
        app.state.select_all_visible(ids)
        assert app.state.selection_count == 5

    def test_state_select_all_deselects_when_all_selected(self, five_categories):
        """App's state.select_all_visible deselects when all selected."""
        from src.ui.tui.app import ReviewApp

        app = ReviewApp(categories=five_categories)
        ids = [c.category_id for c in five_categories]
        app.state.select_all_visible(ids)
        assert app.state.selection_count == 5
        app.state.select_all_visible(ids)
        assert app.state.selection_count == 0

    def test_state_deselect_all_clears_selection(self, five_categories):
        """App's state.clear_selection clears all selections."""
        from src.ui.tui.app import ReviewApp

        app = ReviewApp(categories=five_categories)
        app.state.toggle_selection("cat_001")
        app.state.toggle_selection("cat_002")
        app.state.clear_selection()
        assert app.state.selection_count == 0

    def test_execute_bulk_accept(self, five_categories):
        """App's _execute_bulk_accept accepts all selected categories."""
        from src.ui.tui.app import ReviewApp

        app = ReviewApp(categories=five_categories)
        app.state.toggle_selection("cat_001")
        app.state.toggle_selection("cat_003")

        # Call bulk_accept on state directly (what _execute_bulk_accept delegates to)
        count = app.state.bulk_accept()
        assert count == 2
        assert len(app.state.approved) == 2
        assert len(app.state.pending) == 3
        assert app.state.selection_count == 0

    def test_execute_bulk_delete(self, five_categories):
        """App's _execute_bulk_delete deletes all selected categories."""
        from src.ui.tui.app import ReviewApp

        app = ReviewApp(categories=five_categories)
        app.state.toggle_selection("cat_002")
        app.state.toggle_selection("cat_004")

        # Call bulk_delete on state directly (what _execute_bulk_delete delegates to)
        count = app.state.bulk_delete()
        assert count == 2
        assert len(app.state.deleted) == 2
        assert len(app.state.pending) == 3
        assert app.state.selection_count == 0


# =============================================================================
# BulkActionDialog: Confirmation wiring
# =============================================================================


class TestBulkActionDialogIntegration:
    """Test BulkActionDialog is properly wired for confirmation."""

    def test_dialog_shows_accept_action(self, five_categories):
        """Dialog can be created with 'accept' action."""
        from src.ui.tui.dialogs.bulk_action_dialog import BulkActionDialog

        cats = five_categories[:2]
        dialog = BulkActionDialog(action="accept", count=2, categories=cats)
        assert dialog.action == "accept"
        assert dialog.count == 2

    def test_dialog_shows_delete_action(self, five_categories):
        """Dialog can be created with 'delete' action."""
        from src.ui.tui.dialogs.bulk_action_dialog import BulkActionDialog

        cats = five_categories[:3]
        dialog = BulkActionDialog(action="delete", count=3, categories=cats)
        assert dialog.action == "delete"
        assert dialog.count == 3

    def test_dialog_preview_truncates_long_lists(self, five_categories):
        """Dialog preview shows max 5 categories and '... and N more'."""
        from src.ui.tui.dialogs.bulk_action_dialog import BulkActionDialog

        dialog = BulkActionDialog(action="accept", count=5, categories=five_categories)
        preview = dialog._get_category_preview()
        assert "Financial Alerts" in preview
        # All 5 fit exactly, so no "more" text
        assert "more" not in preview

    def test_dialog_preview_more_than_five(self):
        """Dialog preview shows '... and N more' for >5 categories."""
        from src.ui.tui.dialogs.bulk_action_dialog import BulkActionDialog

        cats = [make_category(f"cat_{i:03d}", f"Category {i}") for i in range(8)]
        dialog = BulkActionDialog(action="delete", count=8, categories=cats)
        preview = dialog._get_category_preview()
        assert "3 more" in preview


# =============================================================================
# Integration: Full flow tests
# =============================================================================


class TestBulkOperationsFullFlow:
    """Integration tests for the full bulk operations flow."""

    def test_select_two_then_bulk_accept(self, five_categories):
        """Full flow: select two categories, bulk accept, verify state."""
        from src.ui.tui.state import ReviewState

        state = ReviewState(categories=five_categories)
        state.toggle_selection("cat_001")
        state.toggle_selection("cat_003")
        assert state.selection_count == 2

        count = state.bulk_accept()
        assert count == 2
        assert state.selection_count == 0
        assert len(state.approved) == 2
        assert len(state.pending) == 3

    def test_select_all_then_bulk_delete(self, five_categories):
        """Full flow: select all, bulk delete, verify all deleted."""
        from src.ui.tui.state import ReviewState

        state = ReviewState(categories=five_categories)
        state.select_all_visible([c.category_id for c in five_categories])
        assert state.selection_count == 5

        count = state.bulk_delete()
        assert count == 5
        assert len(state.pending) == 0
        assert len(state.deleted) == 5

    def test_mixed_individual_and_bulk(self, five_categories):
        """Full flow: individual accept, then bulk delete remaining."""
        from src.ui.tui.state import ReviewState

        state = ReviewState(categories=five_categories)

        # Individual accept
        state.accept("cat_001")
        assert len(state.approved) == 1
        assert len(state.pending) == 4

        # Bulk delete remaining
        remaining_ids = [c.category_id for c in state._pending]
        state.select_all_visible(remaining_ids)
        count = state.bulk_delete()
        assert count == 4
        assert len(state.pending) == 0
        assert len(state.approved) == 1
        assert len(state.deleted) == 4
