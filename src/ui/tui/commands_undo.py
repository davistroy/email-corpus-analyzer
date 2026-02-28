"""
Undo/redo command pattern for the TUI category review.

Implements the Command pattern with reversible operations for
accept, delete, skip, rename, and merge actions. Each command
captures the state needed to reverse its action.

Per Phase 2 Item 2.1 specification.
"""

from __future__ import annotations

import abc
from collections import deque

from src.models.category import Category
from src.ui.tui.state import ReviewState


class Command(abc.ABC):
    """
    Abstract base class for reversible review commands.

    Each concrete command must implement:
    - execute() -> bool: Perform the action, return True on success
    - undo(): Reverse the action, restoring prior state
    - description (property): Human-readable description of the action
    """

    @abc.abstractmethod
    def execute(self) -> bool:
        """
        Execute the command.

        Returns:
            True if the command succeeded, False otherwise.
        """

    @abc.abstractmethod
    def undo(self) -> None:
        """Reverse the command, restoring prior state."""

    @property
    @abc.abstractmethod
    def description(self) -> str:
        """Human-readable description of the action (e.g., "accept 'Newsletter')."""


class AcceptCommand(Command):
    """Command to accept a pending category (move to approved)."""

    def __init__(self, state: ReviewState, category_id: str) -> None:
        self._state = state
        self._category_id = category_id
        self._category: Category | None = None
        self._original_index: int = -1

    def execute(self) -> bool:
        # Capture position before the state removes it
        self._original_index = self._find_pending_index()
        if self._original_index == -1:
            return False

        # Snapshot the category object before state.accept modifies lists
        self._category = self._state.get_pending_by_id(self._category_id)

        return self._state.accept(self._category_id)

    def undo(self) -> None:
        if self._category is None:
            return

        with self._state._lock:
            # Remove from approved
            self._state._approved = [
                c for c in self._state._approved if c.category_id != self._category_id
            ]
            # Re-insert into pending at original position
            idx = min(self._original_index, len(self._state._pending))
            self._state._pending.insert(idx, self._category)
            # Decrement counter
            self._state._counters["accepted"] = max(0, self._state._counters["accepted"] - 1)
            self._state._clamp_selected_index()

        self._state._notify(
            {
                "action": "undo_accept",
                "category_id": self._category_id,
                "category_name": self._category.category_name,
            }
        )

    @property
    def description(self) -> str:
        name = self._category.category_name if self._category else self._category_id
        return f"accept '{name}'"

    def _find_pending_index(self) -> int:
        """Find the index of the category in the pending list."""
        for i, cat in enumerate(self._state._pending):
            if cat.category_id == self._category_id:
                return i
        return -1


class DeleteCommand(Command):
    """Command to delete a pending category."""

    def __init__(self, state: ReviewState, category_id: str) -> None:
        self._state = state
        self._category_id = category_id
        self._category: Category | None = None
        self._original_index: int = -1

    def execute(self) -> bool:
        self._original_index = self._find_pending_index()
        if self._original_index == -1:
            return False

        self._category = self._state.get_pending_by_id(self._category_id)

        return self._state.delete(self._category_id)

    def undo(self) -> None:
        if self._category is None:
            return

        with self._state._lock:
            # Remove from deleted
            self._state._deleted = [
                c for c in self._state._deleted if c.category_id != self._category_id
            ]
            # Re-insert into pending at original position
            idx = min(self._original_index, len(self._state._pending))
            self._state._pending.insert(idx, self._category)
            # Decrement counter
            self._state._counters["deleted"] = max(0, self._state._counters["deleted"] - 1)
            self._state._clamp_selected_index()

        self._state._notify(
            {
                "action": "undo_delete",
                "category_id": self._category_id,
                "category_name": self._category.category_name,
            }
        )

    @property
    def description(self) -> str:
        name = self._category.category_name if self._category else self._category_id
        return f"delete '{name}'"

    def _find_pending_index(self) -> int:
        for i, cat in enumerate(self._state._pending):
            if cat.category_id == self._category_id:
                return i
        return -1


class SkipCommand(Command):
    """Command to skip a pending category."""

    def __init__(self, state: ReviewState, category_id: str) -> None:
        self._state = state
        self._category_id = category_id
        self._category: Category | None = None
        self._original_index: int = -1

    def execute(self) -> bool:
        self._original_index = self._find_pending_index()
        if self._original_index == -1:
            return False

        self._category = self._state.get_pending_by_id(self._category_id)

        return self._state.skip(self._category_id)

    def undo(self) -> None:
        if self._category is None:
            return

        with self._state._lock:
            # Remove from skipped
            self._state._skipped = [
                c for c in self._state._skipped if c.category_id != self._category_id
            ]
            # Re-insert into pending at original position
            idx = min(self._original_index, len(self._state._pending))
            self._state._pending.insert(idx, self._category)
            # Decrement counter
            self._state._counters["skipped"] = max(0, self._state._counters["skipped"] - 1)
            self._state._clamp_selected_index()

        self._state._notify(
            {
                "action": "undo_skip",
                "category_id": self._category_id,
                "category_name": self._category.category_name,
            }
        )

    @property
    def description(self) -> str:
        name = self._category.category_name if self._category else self._category_id
        return f"skip '{name}'"

    def _find_pending_index(self) -> int:
        for i, cat in enumerate(self._state._pending):
            if cat.category_id == self._category_id:
                return i
        return -1


class RenameCommand(Command):
    """Command to rename a pending category and move to approved."""

    def __init__(self, state: ReviewState, category_id: str, new_name: str) -> None:
        self._state = state
        self._category_id = category_id
        self._new_name = new_name
        self._old_name: str = ""
        self._old_user_modified: bool = False
        self._category: Category | None = None
        self._original_index: int = -1

    def execute(self) -> bool:
        self._original_index = self._find_pending_index()
        if self._original_index == -1:
            return False

        cat = self._state.get_pending_by_id(self._category_id)
        if cat is None:
            return False

        self._old_name = cat.category_name
        self._old_user_modified = cat.user_modified
        self._category = cat

        return self._state.rename(self._category_id, self._new_name)

    def undo(self) -> None:
        if self._category is None:
            return

        with self._state._lock:
            # Remove from approved
            self._state._approved = [
                c for c in self._state._approved if c.category_id != self._category_id
            ]
            # Restore original name and user_modified flag
            self._category.category_name = self._old_name
            self._category.user_modified = self._old_user_modified
            # Re-insert into pending at original position
            idx = min(self._original_index, len(self._state._pending))
            self._state._pending.insert(idx, self._category)
            # Decrement counter
            self._state._counters["renamed"] = max(0, self._state._counters["renamed"] - 1)
            self._state._clamp_selected_index()

        self._state._notify(
            {
                "action": "undo_rename",
                "category_id": self._category_id,
                "old_name": self._new_name,
                "new_name": self._old_name,
            }
        )

    @property
    def description(self) -> str:
        return f"rename '{self._old_name}' -> '{self._new_name}'"

    def _find_pending_index(self) -> int:
        for i, cat in enumerate(self._state._pending):
            if cat.category_id == self._category_id:
                return i
        return -1


class MergeCommand(Command):
    """Command to merge a pending source category into an approved target."""

    def __init__(self, state: ReviewState, source_id: str, target_id: str) -> None:
        self._state = state
        self._source_id = source_id
        self._target_id = target_id
        self._source_category: Category | None = None
        self._original_index: int = -1
        # Snapshot of target state before merge
        self._target_old_email_count: int | None = None
        self._target_old_email_ids: list[str] = []
        self._target_old_user_modified: bool = False

    def execute(self) -> bool:
        # Capture source position
        self._original_index = self._find_pending_index(self._source_id)
        if self._original_index == -1:
            return False

        # Snapshot source
        self._source_category = self._state.get_pending_by_id(self._source_id)

        # Snapshot target state before merge modifies it
        target = self._state.get_approved_by_id(self._target_id)
        if target is None:
            return False

        self._target_old_email_count = target.email_count
        self._target_old_email_ids = list(target.example_email_ids)
        self._target_old_user_modified = target.user_modified

        return self._state.merge(self._source_id, self._target_id)

    def undo(self) -> None:
        if self._source_category is None:
            return

        with self._state._lock:
            # Restore target to pre-merge state
            target = None
            for cat in self._state._approved:
                if cat.category_id == self._target_id:
                    target = cat
                    break

            if target is not None:
                target.email_count = self._target_old_email_count
                target.example_email_ids = list(self._target_old_email_ids)
                target.user_modified = self._target_old_user_modified

            # Re-insert source into pending at original position
            idx = min(self._original_index, len(self._state._pending))
            self._state._pending.insert(idx, self._source_category)

            # Decrement counter
            self._state._counters["merged"] = max(0, self._state._counters["merged"] - 1)
            self._state._clamp_selected_index()

        self._state._notify(
            {
                "action": "undo_merge",
                "category_id": self._source_id,
                "target_id": self._target_id,
                "category_name": self._source_category.category_name,
            }
        )

    @property
    def description(self) -> str:
        name = self._source_category.category_name if self._source_category else self._source_id
        return f"merge '{name}' into target"

    def _find_pending_index(self, category_id: str) -> int:
        for i, cat in enumerate(self._state._pending):
            if cat.category_id == category_id:
                return i
        return -1


class UndoManager:
    """
    Manages undo and redo stacks for reversible commands.

    Implements a bounded undo stack (default 50 operations) and a redo
    stack that is cleared whenever a new command is executed.
    """

    def __init__(self, max_undo: int = 50) -> None:
        self._max_undo = max_undo
        self._undo_stack: deque[Command] = deque(maxlen=max_undo)
        self._redo_stack: list[Command] = []

    @property
    def can_undo(self) -> bool:
        """Whether there are commands available to undo."""
        return len(self._undo_stack) > 0

    @property
    def can_redo(self) -> bool:
        """Whether there are commands available to redo."""
        return len(self._redo_stack) > 0

    @property
    def undo_stack_size(self) -> int:
        """Current size of the undo stack."""
        return len(self._undo_stack)

    def execute(self, command: Command) -> bool:
        """
        Execute a command and push it onto the undo stack.

        If the command fails (returns False), it is not added to
        the undo stack. Executing a new command clears the redo stack.

        Args:
            command: The command to execute.

        Returns:
            True if the command succeeded, False otherwise.
        """
        result = command.execute()
        if result:
            self._undo_stack.append(command)
            self._redo_stack.clear()
        return result

    def undo(self) -> str | None:
        """
        Undo the last executed command.

        Returns:
            The description of the undone command, or None if nothing to undo.
        """
        if not self._undo_stack:
            return None

        command = self._undo_stack.pop()
        command.undo()
        self._redo_stack.append(command)
        return command.description

    def redo(self) -> str | None:
        """
        Redo the last undone command.

        Returns:
            The description of the redone command, or None if nothing to redo.
        """
        if not self._redo_stack:
            return None

        command = self._redo_stack.pop()
        command.execute()
        self._undo_stack.append(command)
        return command.description
