"""
Unit tests for ReviewState centralized state management.

Tests state transitions, invalid state guards, change notifications,
and concurrent action protection per Phase 2 Item 1.4.
"""

import threading

from src.models.category import Category, CategorySource


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


class TestReviewStateInit:
    """Test ReviewState initialization."""

    def test_init_with_categories(self):
        """State initializes with a list of pending categories."""
        from src.ui.tui.state import ReviewState

        cats = [make_category("c1", "Cat1"), make_category("c2", "Cat2")]
        state = ReviewState(categories=cats)

        assert len(state.pending) == 2
        assert len(state.approved) == 0
        assert len(state.skipped) == 0
        assert len(state.deleted) == 0

    def test_init_with_empty_categories(self):
        """State initializes correctly with empty list."""
        from src.ui.tui.state import ReviewState

        state = ReviewState(categories=[])

        assert len(state.pending) == 0
        assert state.selected_index == 0

    def test_init_copies_input_list(self):
        """State makes a defensive copy of the input list."""
        from src.ui.tui.state import ReviewState

        cats = [make_category("c1", "Cat1")]
        state = ReviewState(categories=cats)
        cats.append(make_category("c2", "Cat2"))

        assert len(state.pending) == 1

    def test_init_selected_index_zero(self):
        """Initial selected_index is 0."""
        from src.ui.tui.state import ReviewState

        state = ReviewState(categories=[make_category()])
        assert state.selected_index == 0

    def test_init_counters_zero(self):
        """All counters start at zero."""
        from src.ui.tui.state import ReviewState

        state = ReviewState(categories=[make_category()])
        counters = state.counters
        assert counters["accepted"] == 0
        assert counters["renamed"] == 0
        assert counters["merged"] == 0
        assert counters["deleted"] == 0
        assert counters["skipped"] == 0

    def test_init_filter_text_empty(self):
        """filter_text starts empty."""
        from src.ui.tui.state import ReviewState

        state = ReviewState(categories=[make_category()])
        assert state.filter_text == ""


class TestStateTransitions:
    """Test valid state transitions: pending -> approved/deleted/skipped."""

    def test_accept_moves_to_approved(self):
        """Accepting a pending category moves it to approved."""
        from src.ui.tui.state import ReviewState

        cat = make_category("c1", "Cat1")
        state = ReviewState(categories=[cat])

        result = state.accept("c1")

        assert result is True
        assert len(state.pending) == 0
        assert len(state.approved) == 1
        assert state.approved[0].category_id == "c1"
        assert state.counters["accepted"] == 1

    def test_delete_moves_to_deleted(self):
        """Deleting a pending category moves it to deleted."""
        from src.ui.tui.state import ReviewState

        cat = make_category("c1", "Cat1")
        state = ReviewState(categories=[cat])

        result = state.delete("c1")

        assert result is True
        assert len(state.pending) == 0
        assert len(state.deleted) == 1
        assert state.deleted[0].category_id == "c1"
        assert state.counters["deleted"] == 1

    def test_skip_moves_to_skipped(self):
        """Skipping a pending category moves it to skipped."""
        from src.ui.tui.state import ReviewState

        cat = make_category("c1", "Cat1")
        state = ReviewState(categories=[cat])

        result = state.skip("c1")

        assert result is True
        assert len(state.pending) == 0
        assert len(state.skipped) == 1
        assert state.skipped[0].category_id == "c1"
        assert state.counters["skipped"] == 1

    def test_rename_moves_to_approved_with_new_name(self):
        """Renaming accepts the category with a new name."""
        from src.ui.tui.state import ReviewState

        cat = make_category("c1", "Old Name")
        state = ReviewState(categories=[cat])

        result = state.rename("c1", "New Name")

        assert result is True
        assert len(state.pending) == 0
        assert len(state.approved) == 1
        assert state.approved[0].category_name == "New Name"
        assert state.approved[0].user_modified is True
        assert state.counters["renamed"] == 1

    def test_merge_combines_categories(self):
        """Merging combines a pending category into an approved target."""
        from src.ui.tui.state import ReviewState

        target = make_category("t1", "Target", email_count=5)
        source = make_category("s1", "Source", email_count=3)
        state = ReviewState(categories=[source])
        # Pre-approve the target
        state._approved.append(target)

        result = state.merge("s1", "t1")

        assert result is True
        assert len(state.pending) == 0
        assert state.counters["merged"] == 1
        # Target should have combined email count
        merged = state.get_approved_by_id("t1")
        assert merged is not None
        assert merged.email_count == 8

    def test_accept_selected(self):
        """accept_selected uses current selected_index."""
        from src.ui.tui.state import ReviewState

        cats = [make_category("c1"), make_category("c2"), make_category("c3")]
        state = ReviewState(categories=cats)
        state.selected_index = 1

        result = state.accept_selected()

        assert result is True
        assert len(state.approved) == 1
        assert state.approved[0].category_id == "c2"

    def test_delete_selected(self):
        """delete_selected uses current selected_index."""
        from src.ui.tui.state import ReviewState

        cats = [make_category("c1"), make_category("c2")]
        state = ReviewState(categories=cats)
        state.selected_index = 0

        result = state.delete_selected()

        assert result is True
        assert len(state.deleted) == 1
        assert state.deleted[0].category_id == "c1"

    def test_skip_selected(self):
        """skip_selected uses current selected_index."""
        from src.ui.tui.state import ReviewState

        cats = [make_category("c1"), make_category("c2")]
        state = ReviewState(categories=cats)
        state.selected_index = 1

        result = state.skip_selected()

        assert result is True
        assert len(state.skipped) == 1
        assert state.skipped[0].category_id == "c2"


class TestInvalidTransitions:
    """Test invalid state transitions raise or no-op gracefully."""

    def test_accept_nonexistent_category_returns_false(self):
        """Accepting a category not in pending returns False."""
        from src.ui.tui.state import ReviewState

        state = ReviewState(categories=[make_category("c1")])

        result = state.accept("nonexistent")

        assert result is False
        assert len(state.approved) == 0

    def test_delete_nonexistent_category_returns_false(self):
        """Deleting a category not in pending returns False."""
        from src.ui.tui.state import ReviewState

        state = ReviewState(categories=[make_category("c1")])

        result = state.delete("nonexistent")

        assert result is False

    def test_skip_nonexistent_category_returns_false(self):
        """Skipping a category not in pending returns False."""
        from src.ui.tui.state import ReviewState

        state = ReviewState(categories=[make_category("c1")])

        result = state.skip("nonexistent")

        assert result is False

    def test_accept_already_approved_returns_false(self):
        """Cannot accept a category that's already approved."""
        from src.ui.tui.state import ReviewState

        cat = make_category("c1")
        state = ReviewState(categories=[cat])
        state.accept("c1")

        # Try accepting again
        result = state.accept("c1")

        assert result is False
        assert len(state.approved) == 1

    def test_delete_already_deleted_returns_false(self):
        """Cannot delete a category that's already deleted."""
        from src.ui.tui.state import ReviewState

        cat = make_category("c1")
        state = ReviewState(categories=[cat])
        state.delete("c1")

        result = state.delete("c1")

        assert result is False
        assert len(state.deleted) == 1

    def test_merge_with_empty_approved_returns_false(self):
        """Cannot merge when approved list is empty."""
        from src.ui.tui.state import ReviewState

        state = ReviewState(categories=[make_category("c1")])

        result = state.merge("c1", "nonexistent_target")

        assert result is False

    def test_merge_with_nonexistent_target_returns_false(self):
        """Cannot merge into a target that doesn't exist in approved."""
        from src.ui.tui.state import ReviewState

        target = make_category("t1")
        source = make_category("s1")
        state = ReviewState(categories=[source])
        state._approved.append(target)

        result = state.merge("s1", "nonexistent")

        assert result is False

    def test_merge_with_nonexistent_source_returns_false(self):
        """Cannot merge a source that doesn't exist in pending."""
        from src.ui.tui.state import ReviewState

        target = make_category("t1")
        state = ReviewState(categories=[])
        state._approved.append(target)

        result = state.merge("nonexistent", "t1")

        assert result is False

    def test_rename_nonexistent_returns_false(self):
        """Cannot rename a category not in pending."""
        from src.ui.tui.state import ReviewState

        state = ReviewState(categories=[make_category("c1")])

        result = state.rename("nonexistent", "New Name")

        assert result is False

    def test_rename_with_empty_name_returns_false(self):
        """Cannot rename with an empty name."""
        from src.ui.tui.state import ReviewState

        state = ReviewState(categories=[make_category("c1")])

        result = state.rename("c1", "")

        assert result is False

    def test_rename_with_whitespace_name_returns_false(self):
        """Cannot rename with a whitespace-only name."""
        from src.ui.tui.state import ReviewState

        state = ReviewState(categories=[make_category("c1")])

        result = state.rename("c1", "   ")

        assert result is False

    def test_accept_selected_with_empty_pending_returns_false(self):
        """accept_selected returns False when pending is empty."""
        from src.ui.tui.state import ReviewState

        state = ReviewState(categories=[])

        result = state.accept_selected()

        assert result is False

    def test_delete_selected_with_empty_pending_returns_false(self):
        """delete_selected returns False when pending is empty."""
        from src.ui.tui.state import ReviewState

        state = ReviewState(categories=[])

        result = state.delete_selected()

        assert result is False


class TestSelectedIndexManagement:
    """Test selected_index adjusts correctly after mutations."""

    def test_selected_index_clamps_after_removal(self):
        """selected_index adjusts to stay in bounds after removing last item."""
        from src.ui.tui.state import ReviewState

        cats = [make_category("c1"), make_category("c2")]
        state = ReviewState(categories=cats)
        state.selected_index = 1  # pointing at c2

        state.accept("c2")

        assert state.selected_index == 0

    def test_selected_index_stays_when_removing_before(self):
        """When removing an item before selected_index, index adjusts down."""
        from src.ui.tui.state import ReviewState

        cats = [make_category("c1"), make_category("c2"), make_category("c3")]
        state = ReviewState(categories=cats)
        state.selected_index = 2  # pointing at c3

        state.accept("c1")

        # c3 is now at index 1
        assert state.selected_index == 1

    def test_selected_index_zero_when_all_removed(self):
        """selected_index becomes 0 when all items removed."""
        from src.ui.tui.state import ReviewState

        state = ReviewState(categories=[make_category("c1")])
        state.selected_index = 0

        state.accept("c1")

        assert state.selected_index == 0

    def test_move_selection_down(self):
        """move_selection_down wraps around."""
        from src.ui.tui.state import ReviewState

        cats = [make_category("c1"), make_category("c2"), make_category("c3")]
        state = ReviewState(categories=cats)

        state.move_selection_down()
        assert state.selected_index == 1

        state.move_selection_down()
        assert state.selected_index == 2

        state.move_selection_down()
        assert state.selected_index == 0  # wraps

    def test_move_selection_up(self):
        """move_selection_up wraps around."""
        from src.ui.tui.state import ReviewState

        cats = [make_category("c1"), make_category("c2"), make_category("c3")]
        state = ReviewState(categories=cats)

        state.move_selection_up()
        assert state.selected_index == 2  # wraps from 0

        state.move_selection_up()
        assert state.selected_index == 1

    def test_move_selection_noop_when_empty(self):
        """move_selection_down/up are no-ops when pending is empty."""
        from src.ui.tui.state import ReviewState

        state = ReviewState(categories=[])

        state.move_selection_down()
        assert state.selected_index == 0

        state.move_selection_up()
        assert state.selected_index == 0

    def test_set_selected_index_clamps(self):
        """Setting selected_index beyond bounds clamps to valid range."""
        from src.ui.tui.state import ReviewState

        cats = [make_category("c1"), make_category("c2")]
        state = ReviewState(categories=cats)

        state.selected_index = 10
        assert state.selected_index <= 1

        state.selected_index = -5
        assert state.selected_index >= 0


class TestStateChangeNotifications:
    """Test that state changes fire notification callbacks."""

    def test_on_change_fires_on_accept(self):
        """on_change callback fires when a category is accepted."""
        from src.ui.tui.state import ReviewState

        state = ReviewState(categories=[make_category("c1")])
        changes = []
        state.on_change = lambda event: changes.append(event)

        state.accept("c1")

        assert len(changes) == 1
        assert changes[0]["action"] == "accept"
        assert changes[0]["category_id"] == "c1"

    def test_on_change_fires_on_delete(self):
        """on_change callback fires when a category is deleted."""
        from src.ui.tui.state import ReviewState

        state = ReviewState(categories=[make_category("c1")])
        changes = []
        state.on_change = lambda event: changes.append(event)

        state.delete("c1")

        assert len(changes) == 1
        assert changes[0]["action"] == "delete"

    def test_on_change_fires_on_skip(self):
        """on_change callback fires when a category is skipped."""
        from src.ui.tui.state import ReviewState

        state = ReviewState(categories=[make_category("c1")])
        changes = []
        state.on_change = lambda event: changes.append(event)

        state.skip("c1")

        assert len(changes) == 1
        assert changes[0]["action"] == "skip"

    def test_on_change_fires_on_rename(self):
        """on_change callback fires when a category is renamed."""
        from src.ui.tui.state import ReviewState

        state = ReviewState(categories=[make_category("c1")])
        changes = []
        state.on_change = lambda event: changes.append(event)

        state.rename("c1", "New Name")

        assert len(changes) == 1
        assert changes[0]["action"] == "rename"
        assert changes[0]["new_name"] == "New Name"

    def test_on_change_fires_on_merge(self):
        """on_change callback fires when categories are merged."""
        from src.ui.tui.state import ReviewState

        target = make_category("t1", "Target", email_count=5)
        source = make_category("s1", "Source", email_count=3)
        state = ReviewState(categories=[source])
        state._approved.append(target)
        changes = []
        state.on_change = lambda event: changes.append(event)

        state.merge("s1", "t1")

        assert len(changes) == 1
        assert changes[0]["action"] == "merge"
        assert changes[0]["target_id"] == "t1"

    def test_on_change_not_fired_on_failed_action(self):
        """on_change callback does NOT fire when action fails."""
        from src.ui.tui.state import ReviewState

        state = ReviewState(categories=[])
        changes = []
        state.on_change = lambda event: changes.append(event)

        state.accept("nonexistent")

        assert len(changes) == 0

    def test_on_change_fires_on_selection_change(self):
        """on_change fires when selected_index changes via move."""
        from src.ui.tui.state import ReviewState

        cats = [make_category("c1"), make_category("c2")]
        state = ReviewState(categories=cats)
        changes = []
        state.on_change = lambda event: changes.append(event)

        state.move_selection_down()

        assert any(c["action"] == "selection_changed" for c in changes)

    def test_no_callback_when_not_set(self):
        """No error when on_change is None."""
        from src.ui.tui.state import ReviewState

        state = ReviewState(categories=[make_category("c1")])
        state.on_change = None

        # Should not raise
        state.accept("c1")


class TestConcurrentActionProtection:
    """Test that rapid actions don't corrupt state via locking."""

    def test_lock_prevents_concurrent_mutations(self):
        """State uses a lock to prevent concurrent mutations."""
        from src.ui.tui.state import ReviewState

        state = ReviewState(categories=[make_category("c1")])

        # The state should have a lock
        assert hasattr(state, "_lock")

    def test_rapid_sequential_actions_consistent(self):
        """Rapid sequential actions produce consistent state."""
        from src.ui.tui.state import ReviewState

        cats = [make_category(f"c{i}", f"Cat{i}") for i in range(10)]
        state = ReviewState(categories=cats)

        # Rapidly accept all
        for i in range(10):
            state.accept(f"c{i}")

        assert len(state.pending) == 0
        assert len(state.approved) == 10
        assert state.counters["accepted"] == 10

    def test_interleaved_actions_consistent(self):
        """Interleaved accept/delete/skip produce correct counts."""
        from src.ui.tui.state import ReviewState

        cats = [make_category(f"c{i}", f"Cat{i}") for i in range(6)]
        state = ReviewState(categories=cats)

        state.accept("c0")
        state.delete("c1")
        state.skip("c2")
        state.accept("c3")
        state.delete("c4")
        state.skip("c5")

        assert len(state.pending) == 0
        assert len(state.approved) == 2
        assert len(state.deleted) == 2
        assert len(state.skipped) == 2
        assert state.counters["accepted"] == 2
        assert state.counters["deleted"] == 2
        assert state.counters["skipped"] == 2

    def test_threaded_concurrent_access_safe(self):
        """Multiple threads operating on state don't corrupt it."""
        from src.ui.tui.state import ReviewState

        cats = [make_category(f"c{i}", f"Cat{i}") for i in range(100)]
        state = ReviewState(categories=cats)
        errors = []

        def worker(start, end, action):
            try:
                for i in range(start, end):
                    getattr(state, action)(f"c{i}")
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=worker, args=(0, 34, "accept")),
            threading.Thread(target=worker, args=(34, 67, "delete")),
            threading.Thread(target=worker, args=(67, 100, "skip")),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5.0)

        assert len(errors) == 0
        total = len(state.approved) + len(state.deleted) + len(state.skipped)
        assert total == 100
        assert len(state.pending) == 0


class TestFilterText:
    """Test filter_text property."""

    def test_set_filter_text(self):
        """Setting filter_text stores the value."""
        from src.ui.tui.state import ReviewState

        state = ReviewState(categories=[make_category("c1")])
        state.filter_text = "search term"

        assert state.filter_text == "search term"

    def test_clear_filter(self):
        """Setting filter_text to empty clears it."""
        from src.ui.tui.state import ReviewState

        state = ReviewState(categories=[make_category("c1")])
        state.filter_text = "search"
        state.filter_text = ""

        assert state.filter_text == ""


class TestStateAccessors:
    """Test convenience accessor methods."""

    def test_selected_category_returns_correct(self):
        """selected_category returns the category at selected_index."""
        from src.ui.tui.state import ReviewState

        cats = [make_category("c1", "Cat1"), make_category("c2", "Cat2")]
        state = ReviewState(categories=cats)
        state.selected_index = 1

        assert state.selected_category is not None
        assert state.selected_category.category_id == "c2"

    def test_selected_category_returns_none_when_empty(self):
        """selected_category returns None when pending is empty."""
        from src.ui.tui.state import ReviewState

        state = ReviewState(categories=[])

        assert state.selected_category is None

    def test_get_pending_by_id(self):
        """get_pending_by_id returns the correct category."""
        from src.ui.tui.state import ReviewState

        cat = make_category("c1", "Cat1")
        state = ReviewState(categories=[cat])

        result = state.get_pending_by_id("c1")
        assert result is not None
        assert result.category_id == "c1"

    def test_get_pending_by_id_returns_none(self):
        """get_pending_by_id returns None for missing id."""
        from src.ui.tui.state import ReviewState

        state = ReviewState(categories=[make_category("c1")])

        assert state.get_pending_by_id("nonexistent") is None

    def test_get_approved_by_id(self):
        """get_approved_by_id returns the correct category."""
        from src.ui.tui.state import ReviewState

        cat = make_category("c1", "Cat1")
        state = ReviewState(categories=[cat])
        state.accept("c1")

        result = state.get_approved_by_id("c1")
        assert result is not None
        assert result.category_id == "c1"

    def test_get_approved_by_id_returns_none(self):
        """get_approved_by_id returns None for missing id."""
        from src.ui.tui.state import ReviewState

        state = ReviewState(categories=[make_category("c1")])

        assert state.get_approved_by_id("c1") is None

    def test_has_unsaved_changes_initially_false(self):
        """has_unsaved_changes is False initially."""
        from src.ui.tui.state import ReviewState

        state = ReviewState(categories=[make_category("c1")])

        assert state.has_unsaved_changes is False

    def test_has_unsaved_changes_true_after_action(self):
        """has_unsaved_changes becomes True after any action."""
        from src.ui.tui.state import ReviewState

        state = ReviewState(categories=[make_category("c1")])
        state.accept("c1")

        assert state.has_unsaved_changes is True

    def test_total_reviewed(self):
        """total_reviewed returns sum of all non-pending categories."""
        from src.ui.tui.state import ReviewState

        cats = [make_category(f"c{i}") for i in range(5)]
        state = ReviewState(categories=cats)
        state.accept("c0")
        state.delete("c1")
        state.skip("c2")

        assert state.total_reviewed == 3

    def test_total_categories(self):
        """total_categories returns original total count."""
        from src.ui.tui.state import ReviewState

        cats = [make_category(f"c{i}") for i in range(5)]
        state = ReviewState(categories=cats)
        state.accept("c0")

        assert state.total_categories == 5

    def test_get_stats_dict(self):
        """get_stats returns a dict with all expected keys."""
        from src.ui.tui.state import ReviewState

        cats = [make_category(f"c{i}") for i in range(4)]
        state = ReviewState(categories=cats)
        state.accept("c0")
        state.rename("c1", "Renamed")
        state.delete("c2")
        state.skip("c3")

        stats = state.get_stats()

        assert stats["accepted"] == 1
        assert stats["renamed"] == 1
        assert stats["merged"] == 0
        assert stats["deleted"] == 1
        assert stats["skipped"] == 1
        assert stats["remaining"] == 0
        assert stats["total"] == 4
        assert stats["approved"] == 2  # accepted + renamed

    def test_mark_saved(self):
        """mark_saved clears the unsaved changes flag."""
        from src.ui.tui.state import ReviewState

        state = ReviewState(categories=[make_category("c1")])
        state.accept("c1")
        assert state.has_unsaved_changes is True

        state.mark_saved()
        assert state.has_unsaved_changes is False
