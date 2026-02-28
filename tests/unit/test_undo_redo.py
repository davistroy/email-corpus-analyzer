"""
Unit tests for the undo/redo system (Phase 2 Item 2.1).

Tests the command pattern implementation with reversible commands
for accept, delete, skip, rename, and merge operations.
Verifies undo stack limit (50), redo behavior, and notification messages.
"""

from src.models.category import Category, CategorySource
from src.ui.tui.commands_undo import (
    AcceptCommand,
    Command,
    DeleteCommand,
    MergeCommand,
    RenameCommand,
    SkipCommand,
    UndoManager,
)
from src.ui.tui.state import ReviewState


def make_category(
    category_id: str = "cat_1",
    name: str = "Test Category",
    confidence: float = 0.85,
    email_count: int = 10,
    source: CategorySource = CategorySource.CONTENT_CLUSTER,
    example_email_ids: list[str] | None = None,
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
        example_email_ids=example_email_ids or [],
        distinguishing_features=[],
    )


# ---------------------------------------------------------------------------
# Command ABC Tests
# ---------------------------------------------------------------------------


class TestCommandABC:
    """Test the abstract Command base class."""

    def test_command_is_abstract(self):
        """Command cannot be instantiated directly."""
        import abc

        assert hasattr(Command, "execute")
        assert hasattr(Command, "undo")
        assert hasattr(Command, "description")

        # Verify ABC enforcement
        assert abc.ABC in Command.__mro__

    def test_concrete_command_must_implement_execute_and_undo(self):
        """A concrete command must implement execute() and undo()."""

        class IncompleteCommand(Command):
            @property
            def description(self) -> str:
                return "incomplete"

        try:
            IncompleteCommand()  # type: ignore
            raise AssertionError("Should not instantiate without execute/undo")
        except TypeError:
            pass  # expected


# ---------------------------------------------------------------------------
# AcceptCommand Tests
# ---------------------------------------------------------------------------


class TestAcceptCommand:
    """Test the AcceptCommand."""

    def test_accept_execute_moves_to_approved(self):
        """Execute moves the category from pending to approved."""
        cat = make_category("c1", "Cat One")
        state = ReviewState(categories=[cat])

        cmd = AcceptCommand(state, "c1")
        result = cmd.execute()

        assert result is True
        assert len(state.pending) == 0
        assert len(state.approved) == 1
        assert state.approved[0].category_id == "c1"

    def test_accept_undo_returns_to_pending(self):
        """Undo restores the category back to pending."""
        cat = make_category("c1", "Cat One")
        state = ReviewState(categories=[cat])

        cmd = AcceptCommand(state, "c1")
        cmd.execute()
        cmd.undo()

        assert len(state.pending) == 1
        assert len(state.approved) == 0
        assert state.pending[0].category_id == "c1"

    def test_accept_undo_restores_position(self):
        """Undo restores category at its original position in pending."""
        cats = [make_category("c1", "A"), make_category("c2", "B"), make_category("c3", "C")]
        state = ReviewState(categories=cats)

        # Accept the middle one
        cmd = AcceptCommand(state, "c2")
        cmd.execute()
        assert len(state.pending) == 2

        cmd.undo()
        assert len(state.pending) == 3
        assert state._pending[1].category_id == "c2"

    def test_accept_undo_decrements_counter(self):
        """Undo decrements the accepted counter."""
        cat = make_category("c1", "Cat One")
        state = ReviewState(categories=[cat])

        cmd = AcceptCommand(state, "c1")
        cmd.execute()
        assert state.counters["accepted"] == 1

        cmd.undo()
        assert state.counters["accepted"] == 0

    def test_accept_description(self):
        """AcceptCommand has a meaningful description."""
        cat = make_category("c1", "Cat One")
        state = ReviewState(categories=[cat])

        cmd = AcceptCommand(state, "c1")
        cmd.execute()

        assert "accept" in cmd.description.lower()
        assert "Cat One" in cmd.description

    def test_accept_execute_fails_for_missing_category(self):
        """Execute returns False for nonexistent category."""
        state = ReviewState(categories=[make_category("c1")])

        cmd = AcceptCommand(state, "nonexistent")
        result = cmd.execute()

        assert result is False


# ---------------------------------------------------------------------------
# DeleteCommand Tests
# ---------------------------------------------------------------------------


class TestDeleteCommand:
    """Test the DeleteCommand."""

    def test_delete_execute_moves_to_deleted(self):
        """Execute moves the category to deleted."""
        cat = make_category("c1", "Cat One")
        state = ReviewState(categories=[cat])

        cmd = DeleteCommand(state, "c1")
        result = cmd.execute()

        assert result is True
        assert len(state.pending) == 0
        assert len(state.deleted) == 1

    def test_delete_undo_restores_to_pending(self):
        """Undo removes from deleted and restores to pending."""
        cat = make_category("c1", "Cat One")
        state = ReviewState(categories=[cat])

        cmd = DeleteCommand(state, "c1")
        cmd.execute()
        cmd.undo()

        assert len(state.deleted) == 0
        assert len(state.pending) == 1
        assert state.pending[0].category_id == "c1"

    def test_delete_undo_restores_at_original_position(self):
        """Undo restores category at its original position."""
        cats = [make_category("c1"), make_category("c2"), make_category("c3")]
        state = ReviewState(categories=cats)

        cmd = DeleteCommand(state, "c2")
        cmd.execute()
        cmd.undo()

        assert state._pending[1].category_id == "c2"

    def test_delete_undo_decrements_counter(self):
        """Undo decrements the deleted counter."""
        cat = make_category("c1")
        state = ReviewState(categories=[cat])

        cmd = DeleteCommand(state, "c1")
        cmd.execute()
        assert state.counters["deleted"] == 1

        cmd.undo()
        assert state.counters["deleted"] == 0

    def test_delete_description(self):
        """DeleteCommand has a meaningful description."""
        cat = make_category("c1", "Cat One")
        state = ReviewState(categories=[cat])

        cmd = DeleteCommand(state, "c1")
        cmd.execute()

        assert "delete" in cmd.description.lower()
        assert "Cat One" in cmd.description


# ---------------------------------------------------------------------------
# SkipCommand Tests
# ---------------------------------------------------------------------------


class TestSkipCommand:
    """Test the SkipCommand."""

    def test_skip_execute_moves_to_skipped(self):
        """Execute moves the category to skipped."""
        cat = make_category("c1", "Cat One")
        state = ReviewState(categories=[cat])

        cmd = SkipCommand(state, "c1")
        result = cmd.execute()

        assert result is True
        assert len(state.pending) == 0
        assert len(state.skipped) == 1

    def test_skip_undo_restores_to_pending(self):
        """Undo removes from skipped and restores to pending."""
        cat = make_category("c1", "Cat One")
        state = ReviewState(categories=[cat])

        cmd = SkipCommand(state, "c1")
        cmd.execute()
        cmd.undo()

        assert len(state.skipped) == 0
        assert len(state.pending) == 1
        assert state.pending[0].category_id == "c1"

    def test_skip_undo_decrements_counter(self):
        """Undo decrements the skipped counter."""
        cat = make_category("c1")
        state = ReviewState(categories=[cat])

        cmd = SkipCommand(state, "c1")
        cmd.execute()
        assert state.counters["skipped"] == 1

        cmd.undo()
        assert state.counters["skipped"] == 0

    def test_skip_description(self):
        """SkipCommand has a meaningful description."""
        cat = make_category("c1", "Cat One")
        state = ReviewState(categories=[cat])

        cmd = SkipCommand(state, "c1")
        cmd.execute()

        assert "skip" in cmd.description.lower()
        assert "Cat One" in cmd.description


# ---------------------------------------------------------------------------
# RenameCommand Tests
# ---------------------------------------------------------------------------


class TestRenameCommand:
    """Test the RenameCommand."""

    def test_rename_execute_renames_and_approves(self):
        """Execute renames the category and moves to approved."""
        cat = make_category("c1", "Old Name")
        state = ReviewState(categories=[cat])

        cmd = RenameCommand(state, "c1", "New Name")
        result = cmd.execute()

        assert result is True
        assert len(state.pending) == 0
        assert len(state.approved) == 1
        assert state.approved[0].category_name == "New Name"

    def test_rename_undo_restores_original_name(self):
        """Undo restores the original name and moves back to pending."""
        cat = make_category("c1", "Old Name")
        state = ReviewState(categories=[cat])

        cmd = RenameCommand(state, "c1", "New Name")
        cmd.execute()
        cmd.undo()

        assert len(state.approved) == 0
        assert len(state.pending) == 1
        assert state.pending[0].category_name == "Old Name"
        assert state.pending[0].user_modified is False

    def test_rename_undo_decrements_counter(self):
        """Undo decrements the renamed counter."""
        cat = make_category("c1", "Old Name")
        state = ReviewState(categories=[cat])

        cmd = RenameCommand(state, "c1", "New Name")
        cmd.execute()
        assert state.counters["renamed"] == 1

        cmd.undo()
        assert state.counters["renamed"] == 0

    def test_rename_undo_restores_position(self):
        """Undo restores the category at its original position."""
        cats = [make_category("c1", "A"), make_category("c2", "B"), make_category("c3", "C")]
        state = ReviewState(categories=cats)

        cmd = RenameCommand(state, "c2", "New B")
        cmd.execute()
        cmd.undo()

        assert state._pending[1].category_id == "c2"
        assert state._pending[1].category_name == "B"

    def test_rename_description(self):
        """RenameCommand has a meaningful description."""
        cat = make_category("c1", "Old Name")
        state = ReviewState(categories=[cat])

        cmd = RenameCommand(state, "c1", "New Name")
        cmd.execute()

        assert "rename" in cmd.description.lower()
        assert "Old Name" in cmd.description


# ---------------------------------------------------------------------------
# MergeCommand Tests
# ---------------------------------------------------------------------------


class TestMergeCommand:
    """Test the MergeCommand."""

    def test_merge_execute_merges_source_into_target(self):
        """Execute merges source into target."""
        target = make_category("t1", "Target", email_count=5, example_email_ids=["e1", "e2"])
        source = make_category("s1", "Source", email_count=3, example_email_ids=["e3", "e4"])
        state = ReviewState(categories=[source])
        state._approved.append(target)

        cmd = MergeCommand(state, "s1", "t1")
        result = cmd.execute()

        assert result is True
        assert len(state.pending) == 0
        assert state.counters["merged"] == 1

    def test_merge_undo_restores_source_to_pending(self):
        """Undo restores the source category to pending."""
        target = make_category("t1", "Target", email_count=5, example_email_ids=["e1", "e2"])
        source = make_category("s1", "Source", email_count=3, example_email_ids=["e3", "e4"])
        state = ReviewState(categories=[source])
        state._approved.append(target)

        cmd = MergeCommand(state, "s1", "t1")
        cmd.execute()
        cmd.undo()

        assert len(state.pending) == 1
        assert state.pending[0].category_id == "s1"
        assert state.pending[0].category_name == "Source"

    def test_merge_undo_restores_target_state(self):
        """Undo restores the target's original email count and IDs."""
        target = make_category("t1", "Target", email_count=5, example_email_ids=["e1", "e2"])
        source = make_category("s1", "Source", email_count=3, example_email_ids=["e3", "e4"])
        state = ReviewState(categories=[source])
        state._approved.append(target)

        cmd = MergeCommand(state, "s1", "t1")
        cmd.execute()

        # After merge, target has combined count
        merged_target = state.get_approved_by_id("t1")
        assert merged_target is not None
        assert merged_target.email_count == 8

        cmd.undo()

        # After undo, target should have original state
        restored_target = state.get_approved_by_id("t1")
        assert restored_target is not None
        assert restored_target.email_count == 5
        assert restored_target.example_email_ids == ["e1", "e2"]

    def test_merge_undo_decrements_counter(self):
        """Undo decrements the merged counter."""
        target = make_category("t1", "Target", email_count=5)
        source = make_category("s1", "Source", email_count=3)
        state = ReviewState(categories=[source])
        state._approved.append(target)

        cmd = MergeCommand(state, "s1", "t1")
        cmd.execute()
        assert state.counters["merged"] == 1

        cmd.undo()
        assert state.counters["merged"] == 0

    def test_merge_undo_restores_target_user_modified(self):
        """Undo restores target's user_modified flag."""
        target = make_category("t1", "Target", email_count=5)
        target.user_modified = False
        source = make_category("s1", "Source", email_count=3)
        state = ReviewState(categories=[source])
        state._approved.append(target)

        cmd = MergeCommand(state, "s1", "t1")
        cmd.execute()
        assert state.get_approved_by_id("t1").user_modified is True

        cmd.undo()
        assert state.get_approved_by_id("t1").user_modified is False

    def test_merge_description(self):
        """MergeCommand has a meaningful description."""
        target = make_category("t1", "Target", email_count=5)
        source = make_category("s1", "Source", email_count=3)
        state = ReviewState(categories=[source])
        state._approved.append(target)

        cmd = MergeCommand(state, "s1", "t1")
        cmd.execute()

        assert "merge" in cmd.description.lower()
        assert "Source" in cmd.description


# ---------------------------------------------------------------------------
# UndoManager Tests
# ---------------------------------------------------------------------------


class TestUndoManager:
    """Test the UndoManager that holds undo/redo stacks."""

    def test_initial_state(self):
        """UndoManager starts with empty stacks."""
        mgr = UndoManager()

        assert mgr.can_undo is False
        assert mgr.can_redo is False

    def test_execute_and_undo(self):
        """Execute then undo restores state."""
        cat = make_category("c1", "Cat One")
        state = ReviewState(categories=[cat])
        mgr = UndoManager()

        cmd = AcceptCommand(state, "c1")
        mgr.execute(cmd)

        assert mgr.can_undo is True
        assert len(state.pending) == 0

        mgr.undo()

        assert len(state.pending) == 1
        assert state.pending[0].category_id == "c1"

    def test_undo_then_redo(self):
        """Redo reapplies the undone action."""
        cat = make_category("c1", "Cat One")
        state = ReviewState(categories=[cat])
        mgr = UndoManager()

        cmd = AcceptCommand(state, "c1")
        mgr.execute(cmd)
        mgr.undo()

        assert mgr.can_redo is True

        mgr.redo()

        assert len(state.pending) == 0
        assert len(state.approved) == 1

    def test_new_action_clears_redo_stack(self):
        """Executing a new command after undo clears the redo stack."""
        cats = [make_category("c1"), make_category("c2")]
        state = ReviewState(categories=cats)
        mgr = UndoManager()

        cmd1 = AcceptCommand(state, "c1")
        mgr.execute(cmd1)
        mgr.undo()

        assert mgr.can_redo is True

        cmd2 = DeleteCommand(state, "c2")
        mgr.execute(cmd2)

        assert mgr.can_redo is False

    def test_undo_stack_limit_50(self):
        """Undo stack holds at most 50 operations."""
        cats = [make_category(f"c{i}", f"Cat{i}") for i in range(55)]
        state = ReviewState(categories=cats)
        mgr = UndoManager(max_undo=50)

        for i in range(55):
            cmd = AcceptCommand(state, f"c{i}")
            mgr.execute(cmd)

        # Only 50 undos possible, not 55
        undo_count = 0
        while mgr.can_undo:
            mgr.undo()
            undo_count += 1

        assert undo_count == 50

    def test_undo_stack_drops_oldest(self):
        """When stack exceeds limit, oldest operations are dropped."""
        cats = [make_category(f"c{i}", f"Cat{i}") for i in range(52)]
        state = ReviewState(categories=cats)
        mgr = UndoManager(max_undo=50)

        for i in range(52):
            cmd = AcceptCommand(state, f"c{i}")
            mgr.execute(cmd)

        # Should have exactly 50 items in undo stack
        assert mgr.undo_stack_size == 50

    def test_undo_returns_description(self):
        """Undo returns the description of the undone command."""
        cat = make_category("c1", "Cat One")
        state = ReviewState(categories=[cat])
        mgr = UndoManager()

        cmd = AcceptCommand(state, "c1")
        mgr.execute(cmd)

        desc = mgr.undo()

        assert desc is not None
        assert "accept" in desc.lower()
        assert "Cat One" in desc

    def test_redo_returns_description(self):
        """Redo returns the description of the redone command."""
        cat = make_category("c1", "Cat One")
        state = ReviewState(categories=[cat])
        mgr = UndoManager()

        cmd = AcceptCommand(state, "c1")
        mgr.execute(cmd)
        mgr.undo()

        desc = mgr.redo()

        assert desc is not None
        assert "accept" in desc.lower()

    def test_undo_on_empty_returns_none(self):
        """Undo when stack is empty returns None."""
        mgr = UndoManager()

        result = mgr.undo()

        assert result is None

    def test_redo_on_empty_returns_none(self):
        """Redo when stack is empty returns None."""
        mgr = UndoManager()

        result = mgr.redo()

        assert result is None

    def test_multiple_undo_redo_cycles(self):
        """Multiple undo/redo cycles maintain consistency."""
        cats = [make_category("c1"), make_category("c2"), make_category("c3")]
        state = ReviewState(categories=cats)
        mgr = UndoManager()

        # Accept c1, delete c2, skip c3
        mgr.execute(AcceptCommand(state, "c1"))
        mgr.execute(DeleteCommand(state, "c2"))
        mgr.execute(SkipCommand(state, "c3"))

        assert len(state.pending) == 0

        # Undo all 3
        mgr.undo()  # undo skip c3
        assert len(state.pending) == 1
        assert state.pending[0].category_id == "c3"

        mgr.undo()  # undo delete c2
        assert len(state.pending) == 2

        mgr.undo()  # undo accept c1
        assert len(state.pending) == 3

        # Redo all 3
        mgr.redo()
        mgr.redo()
        mgr.redo()

        assert len(state.pending) == 0

    def test_execute_returns_true_on_success(self):
        """Execute returns True when the command succeeds."""
        cat = make_category("c1")
        state = ReviewState(categories=[cat])
        mgr = UndoManager()

        result = mgr.execute(AcceptCommand(state, "c1"))

        assert result is True

    def test_execute_returns_false_on_failure(self):
        """Execute returns False when the command fails (and does not add to stack)."""
        state = ReviewState(categories=[])
        mgr = UndoManager()

        result = mgr.execute(AcceptCommand(state, "nonexistent"))

        assert result is False
        assert mgr.can_undo is False


# ---------------------------------------------------------------------------
# Integration: Undo/Redo with ReviewState
# ---------------------------------------------------------------------------


class TestUndoRedoIntegration:
    """Integration tests verifying undo/redo with full ReviewState."""

    def test_accept_then_undo_restores_counters(self):
        """Accept then undo restores all counters."""
        cats = [make_category("c1"), make_category("c2")]
        state = ReviewState(categories=cats)
        mgr = UndoManager()

        mgr.execute(AcceptCommand(state, "c1"))
        assert state.counters["accepted"] == 1

        mgr.undo()
        assert state.counters["accepted"] == 0

    def test_delete_then_undo_category_reappears_at_original_position(self):
        """Delete then undo: category reappears at original position."""
        cats = [make_category("c1", "A"), make_category("c2", "B"), make_category("c3", "C")]
        state = ReviewState(categories=cats)
        mgr = UndoManager()

        mgr.execute(DeleteCommand(state, "c2"))
        assert len(state.pending) == 2
        assert state._pending[0].category_id == "c1"
        assert state._pending[1].category_id == "c3"

        mgr.undo()
        assert len(state.pending) == 3
        assert state._pending[0].category_id == "c1"
        assert state._pending[1].category_id == "c2"
        assert state._pending[2].category_id == "c3"

    def test_rename_then_undo_restores_name(self):
        """Rename then undo: original name restored."""
        cat = make_category("c1", "Original Name")
        state = ReviewState(categories=[cat])
        mgr = UndoManager()

        mgr.execute(RenameCommand(state, "c1", "New Name"))
        assert state.approved[0].category_name == "New Name"

        mgr.undo()
        assert state.pending[0].category_name == "Original Name"

    def test_merge_then_undo_splits_back(self):
        """Merge then undo: source category restored, emails split back."""
        target = make_category("t1", "Target", email_count=5, example_email_ids=["e1"])
        source = make_category("s1", "Source", email_count=3, example_email_ids=["e2"])
        state = ReviewState(categories=[source])
        state._approved.append(target)
        mgr = UndoManager()

        mgr.execute(MergeCommand(state, "s1", "t1"))
        assert len(state.pending) == 0
        merged_target = state.get_approved_by_id("t1")
        assert merged_target.email_count == 8

        mgr.undo()
        assert len(state.pending) == 1
        assert state.pending[0].category_id == "s1"
        restored_target = state.get_approved_by_id("t1")
        assert restored_target.email_count == 5

    def test_redo_after_undo_reapplies(self):
        """Redo after undo: action reapplied correctly."""
        cat = make_category("c1", "Cat One")
        state = ReviewState(categories=[cat])
        mgr = UndoManager()

        mgr.execute(AcceptCommand(state, "c1"))
        mgr.undo()
        assert len(state.pending) == 1

        mgr.redo()
        assert len(state.pending) == 0
        assert len(state.approved) == 1

    def test_undo_maintains_unsaved_changes_flag(self):
        """Undo still leaves has_unsaved_changes True (undo is itself a change)."""
        cat = make_category("c1")
        state = ReviewState(categories=[cat])
        mgr = UndoManager()

        mgr.execute(AcceptCommand(state, "c1"))
        assert state.has_unsaved_changes is True

        mgr.undo()
        # Undo is still a state-changing operation, flag stays True
        assert state.has_unsaved_changes is True

    def test_complex_sequence(self):
        """Complex sequence of operations with interleaved undo/redo."""
        cats = [
            make_category("c1", "Alpha"),
            make_category("c2", "Beta"),
            make_category("c3", "Gamma"),
            make_category("c4", "Delta"),
        ]
        state = ReviewState(categories=cats)
        mgr = UndoManager()

        # Accept Alpha
        mgr.execute(AcceptCommand(state, "c1"))
        assert len(state.approved) == 1

        # Delete Beta
        mgr.execute(DeleteCommand(state, "c2"))
        assert len(state.deleted) == 1

        # Undo delete of Beta
        mgr.undo()
        assert len(state.deleted) == 0
        assert len(state.pending) == 3  # c2, c3, c4

        # Rename Gamma
        mgr.execute(RenameCommand(state, "c3", "Gamma Prime"))
        assert len(state.approved) == 2

        # Undo rename of Gamma
        mgr.undo()
        assert len(state.pending) == 3
        found = state.get_pending_by_id("c3")
        assert found is not None
        assert found.category_name == "Gamma"

        # Redo rename of Gamma
        mgr.redo()
        assert len(state.approved) == 2
        gamma = state.get_approved_by_id("c3")
        assert gamma.category_name == "Gamma Prime"
