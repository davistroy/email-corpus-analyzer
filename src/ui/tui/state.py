"""
Centralized state management for the TUI category review.

Provides a single ReviewState class that holds all mutable state:
categories (pending, approved, skipped, deleted), counters,
selected_index, filter_text, and selected_categories (multi-select).
Supports change notifications and thread-safe mutations.

Per Phase 2 Item 1.4 specification.
Phase 2 Item 2.2: Added selected_categories tracking and bulk operations.
"""

from __future__ import annotations

import threading
from collections.abc import Callable

from src.models.category import Category


class ReviewState:
    """
    Centralized state container for the TUI review session.

    Holds all mutable state in one place, replacing scattered state
    across app.py and widgets. Provides:
    - State transition methods (accept, delete, skip, rename, merge)
    - Invalid state guards (returns False on bad transitions)
    - Change notification via on_change callback
    - Thread-safe mutations via internal lock
    - Selected index management with auto-clamping
    - Multi-select tracking for bulk operations (Phase 2 Item 2.2)
    - Bulk accept/delete operations
    """

    def __init__(self, categories: list[Category]) -> None:
        """
        Initialize ReviewState with a list of pending categories.

        Args:
            categories: List of categories to review. A defensive copy is made.
        """
        self._lock = threading.Lock()
        self._pending: list[Category] = list(categories)
        self._approved: list[Category] = []
        self._skipped: list[Category] = []
        self._deleted: list[Category] = []
        self._selected_index: int = 0
        self._filter_text: str = ""
        self._total_categories: int = len(categories)
        self._has_unsaved_changes: bool = False

        # Multi-select tracking for bulk operations (Phase 2 Item 2.2)
        self._selected_categories: set[str] = set()

        # Counters track individual action types
        self._counters: dict[str, int] = {
            "accepted": 0,
            "renamed": 0,
            "merged": 0,
            "deleted": 0,
            "skipped": 0,
        }

        # Notification callback: called with a dict describing the change
        self.on_change: Callable[[dict], None] | None = None

    # -------------------------------------------------------------------------
    # Properties (read-only views)
    # -------------------------------------------------------------------------

    @property
    def pending(self) -> list[Category]:
        """List of categories still awaiting review."""
        return list(self._pending)

    @property
    def approved(self) -> list[Category]:
        """List of approved categories (accepted + renamed)."""
        return list(self._approved)

    @property
    def skipped(self) -> list[Category]:
        """List of skipped categories."""
        return list(self._skipped)

    @property
    def deleted(self) -> list[Category]:
        """List of deleted categories."""
        return list(self._deleted)

    @property
    def counters(self) -> dict[str, int]:
        """Copy of the action counters."""
        return dict(self._counters)

    @property
    def selected_index(self) -> int:
        """Current selected index into the pending list."""
        return self._selected_index

    @selected_index.setter
    def selected_index(self, value: int) -> None:
        """Set selected index, clamping to valid range."""
        with self._lock:
            if not self._pending:
                self._selected_index = 0
            else:
                self._selected_index = max(0, min(value, len(self._pending) - 1))

    @property
    def filter_text(self) -> str:
        """Current filter/search text."""
        return self._filter_text

    @filter_text.setter
    def filter_text(self, value: str) -> None:
        """Set the filter text."""
        self._filter_text = value

    @property
    def selected_category(self) -> Category | None:
        """The currently selected category, or None if pending is empty."""
        if not self._pending:
            return None
        if self._selected_index < 0 or self._selected_index >= len(self._pending):
            return None
        return self._pending[self._selected_index]

    @property
    def has_unsaved_changes(self) -> bool:
        """Whether any actions have been taken since last save."""
        return self._has_unsaved_changes

    @property
    def total_reviewed(self) -> int:
        """Total number of categories that have been reviewed (not pending)."""
        return len(self._approved) + len(self._deleted) + len(self._skipped)

    @property
    def total_categories(self) -> int:
        """Original total number of categories."""
        return self._total_categories

    # -------------------------------------------------------------------------
    # Multi-select (Phase 2 Item 2.2)
    # -------------------------------------------------------------------------

    @property
    def selected_categories(self) -> set[str]:
        """Set of category IDs currently selected for bulk operations."""
        return set(self._selected_categories)

    @property
    def selection_count(self) -> int:
        """Number of currently selected categories."""
        return len(self._selected_categories)

    @property
    def has_selection(self) -> bool:
        """Whether at least one category is selected."""
        return len(self._selected_categories) > 0

    def toggle_selection(self, category_id: str) -> None:
        """
        Toggle selection state for a category.

        Only toggles if the category exists in the pending list.

        Args:
            category_id: ID of category to toggle.
        """
        with self._lock:
            # Only allow selecting pending categories
            if not any(c.category_id == category_id for c in self._pending):
                return

            if category_id in self._selected_categories:
                self._selected_categories.discard(category_id)
            else:
                self._selected_categories.add(category_id)

        self._notify(
            {
                "action": "selection_changed",
                "category_id": category_id,
                "selected_count": len(self._selected_categories),
            }
        )

    def select_all_visible(self, visible_ids: list[str]) -> None:
        """
        Select or deselect all visible categories.

        If all visible IDs are already selected, deselects all.
        Otherwise, selects all visible IDs.

        Args:
            visible_ids: List of category IDs currently visible.
        """
        with self._lock:
            visible_set = set(visible_ids)
            if visible_set and visible_set.issubset(self._selected_categories):
                # All visible are selected -> deselect all
                self._selected_categories.clear()
            else:
                # Select all visible
                self._selected_categories = set(visible_ids)

        self._notify(
            {
                "action": "selection_changed",
                "selected_count": len(self._selected_categories),
            }
        )

    def clear_selection(self) -> None:
        """Clear all selections."""
        with self._lock:
            self._selected_categories.clear()

        self._notify(
            {
                "action": "selection_changed",
                "selected_count": 0,
            }
        )

    def get_selected_pending(self) -> list[Category]:
        """
        Get Category objects for all selected IDs that are still pending.

        Returns:
            List of selected Category objects in pending order.
        """
        return [cat for cat in self._pending if cat.category_id in self._selected_categories]

    # -------------------------------------------------------------------------
    # Bulk operations (Phase 2 Item 2.2)
    # -------------------------------------------------------------------------

    def bulk_accept(self) -> int:
        """
        Accept all selected categories, moving them to approved.

        Returns:
            Number of categories accepted.
        """
        with self._lock:
            selected = [
                cat for cat in self._pending if cat.category_id in self._selected_categories
            ]
            if not selected:
                return 0

            for cat in selected:
                self._pending.remove(cat)
                self._approved.append(cat)
                self._counters["accepted"] += 1

            count = len(selected)
            self._selected_categories.clear()
            self._has_unsaved_changes = True
            self._clamp_selected_index()

        self._notify(
            {
                "action": "bulk_accept",
                "count": count,
                "category_ids": [c.category_id for c in selected],
            }
        )
        return count

    def bulk_delete(self) -> int:
        """
        Delete all selected categories, moving them to deleted.

        Returns:
            Number of categories deleted.
        """
        with self._lock:
            selected = [
                cat for cat in self._pending if cat.category_id in self._selected_categories
            ]
            if not selected:
                return 0

            for cat in selected:
                self._pending.remove(cat)
                self._deleted.append(cat)
                self._counters["deleted"] += 1

            count = len(selected)
            self._selected_categories.clear()
            self._has_unsaved_changes = True
            self._clamp_selected_index()

        self._notify(
            {
                "action": "bulk_delete",
                "count": count,
                "category_ids": [c.category_id for c in selected],
            }
        )
        return count

    # -------------------------------------------------------------------------
    # Lookup helpers
    # -------------------------------------------------------------------------

    def get_pending_by_id(self, category_id: str) -> Category | None:
        """
        Find a category in the pending list by ID.

        Args:
            category_id: The category ID to look up.

        Returns:
            The Category if found, None otherwise.
        """
        for cat in self._pending:
            if cat.category_id == category_id:
                return cat
        return None

    def get_approved_by_id(self, category_id: str) -> Category | None:
        """
        Find a category in the approved list by ID.

        Args:
            category_id: The category ID to look up.

        Returns:
            The Category if found, None otherwise.
        """
        for cat in self._approved:
            if cat.category_id == category_id:
                return cat
        return None

    # -------------------------------------------------------------------------
    # State transition methods
    # -------------------------------------------------------------------------

    def accept(self, category_id: str) -> bool:
        """
        Accept a pending category, moving it to approved.

        Args:
            category_id: ID of category to accept.

        Returns:
            True if the action succeeded, False otherwise.
        """
        with self._lock:
            cat = self._find_and_remove_pending(category_id)
            if cat is None:
                return False

            self._approved.append(cat)
            self._counters["accepted"] += 1
            self._has_unsaved_changes = True
            self._selected_categories.discard(category_id)
            self._clamp_selected_index()

        self._notify(
            {
                "action": "accept",
                "category_id": category_id,
                "category_name": cat.category_name,
            }
        )
        return True

    def delete(self, category_id: str) -> bool:
        """
        Delete a pending category.

        Args:
            category_id: ID of category to delete.

        Returns:
            True if the action succeeded, False otherwise.
        """
        with self._lock:
            cat = self._find_and_remove_pending(category_id)
            if cat is None:
                return False

            self._deleted.append(cat)
            self._counters["deleted"] += 1
            self._has_unsaved_changes = True
            self._selected_categories.discard(category_id)
            self._clamp_selected_index()

        self._notify(
            {
                "action": "delete",
                "category_id": category_id,
                "category_name": cat.category_name,
            }
        )
        return True

    def skip(self, category_id: str) -> bool:
        """
        Skip a pending category for later review.

        Args:
            category_id: ID of category to skip.

        Returns:
            True if the action succeeded, False otherwise.
        """
        with self._lock:
            cat = self._find_and_remove_pending(category_id)
            if cat is None:
                return False

            self._skipped.append(cat)
            self._counters["skipped"] += 1
            self._has_unsaved_changes = True
            self._selected_categories.discard(category_id)
            self._clamp_selected_index()

        self._notify(
            {
                "action": "skip",
                "category_id": category_id,
                "category_name": cat.category_name,
            }
        )
        return True

    def rename(self, category_id: str, new_name: str) -> bool:
        """
        Rename a pending category and move it to approved.

        Args:
            category_id: ID of category to rename.
            new_name: New name for the category.

        Returns:
            True if the action succeeded, False otherwise.
        """
        if not new_name or not new_name.strip():
            return False

        with self._lock:
            cat = self._find_and_remove_pending(category_id)
            if cat is None:
                return False

            old_name = cat.category_name
            cat.category_name = new_name.strip()
            cat.user_modified = True
            self._approved.append(cat)
            self._counters["renamed"] += 1
            self._has_unsaved_changes = True
            self._selected_categories.discard(category_id)
            self._clamp_selected_index()

        self._notify(
            {
                "action": "rename",
                "category_id": category_id,
                "old_name": old_name,
                "new_name": new_name.strip(),
            }
        )
        return True

    def merge(self, source_id: str, target_id: str) -> bool:
        """
        Merge a pending category into an approved target.

        The source is removed from pending and its email IDs and count
        are merged into the target in the approved list.

        Args:
            source_id: ID of the pending category to merge from.
            target_id: ID of the approved category to merge into.

        Returns:
            True if the action succeeded, False otherwise.
        """
        with self._lock:
            # Validate target exists in approved
            target = None
            for cat in self._approved:
                if cat.category_id == target_id:
                    target = cat
                    break
            if target is None:
                return False

            # Validate and remove source from pending
            source = self._find_and_remove_pending(source_id)
            if source is None:
                return False

            # Merge data
            all_ids = set(target.example_email_ids) | set(source.example_email_ids)
            target.example_email_ids = list(all_ids)[:10]
            target.email_count = (target.email_count or 0) + (source.email_count or 0)
            target.user_modified = True

            self._counters["merged"] += 1
            self._has_unsaved_changes = True
            self._selected_categories.discard(source_id)
            self._clamp_selected_index()

        self._notify(
            {
                "action": "merge",
                "category_id": source_id,
                "target_id": target_id,
                "target_name": target.category_name,
            }
        )
        return True

    # -------------------------------------------------------------------------
    # Convenience methods using selected_index
    # -------------------------------------------------------------------------

    def accept_selected(self) -> bool:
        """Accept the currently selected category."""
        cat = self.selected_category
        if cat is None:
            return False
        return self.accept(cat.category_id)

    def delete_selected(self) -> bool:
        """Delete the currently selected category."""
        cat = self.selected_category
        if cat is None:
            return False
        return self.delete(cat.category_id)

    def skip_selected(self) -> bool:
        """Skip the currently selected category."""
        cat = self.selected_category
        if cat is None:
            return False
        return self.skip(cat.category_id)

    # -------------------------------------------------------------------------
    # Navigation
    # -------------------------------------------------------------------------

    def move_selection_down(self) -> None:
        """Move selection down one position, wrapping around."""
        with self._lock:
            if not self._pending:
                return
            old = self._selected_index
            self._selected_index = (self._selected_index + 1) % len(self._pending)

        if old != self._selected_index:
            self._notify(
                {
                    "action": "selection_changed",
                    "selected_index": self._selected_index,
                }
            )

    def move_selection_up(self) -> None:
        """Move selection up one position, wrapping around."""
        with self._lock:
            if not self._pending:
                return
            old = self._selected_index
            self._selected_index = (self._selected_index - 1) % len(self._pending)

        if old != self._selected_index:
            self._notify(
                {
                    "action": "selection_changed",
                    "selected_index": self._selected_index,
                }
            )

    # -------------------------------------------------------------------------
    # Stats and save tracking
    # -------------------------------------------------------------------------

    def get_stats(self) -> dict:
        """
        Get a summary dict of all review statistics.

        Returns:
            Dict with keys: accepted, renamed, merged, deleted, skipped,
            remaining, total, approved (count of approved list).
        """
        return {
            "accepted": self._counters["accepted"],
            "renamed": self._counters["renamed"],
            "merged": self._counters["merged"],
            "deleted": self._counters["deleted"],
            "skipped": self._counters["skipped"],
            "remaining": len(self._pending),
            "total": self._total_categories,
            "approved": len(self._approved),
        }

    def mark_saved(self) -> None:
        """Mark the current state as saved (clears unsaved changes flag)."""
        self._has_unsaved_changes = False

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    def _find_and_remove_pending(self, category_id: str) -> Category | None:
        """
        Find and remove a category from the pending list.

        Must be called while holding self._lock.

        Args:
            category_id: ID of category to find and remove.

        Returns:
            The removed Category, or None if not found.
        """
        for i, cat in enumerate(self._pending):
            if cat.category_id == category_id:
                return self._pending.pop(i)
        return None

    def _clamp_selected_index(self) -> None:
        """
        Clamp selected_index to valid range after a mutation.

        Must be called while holding self._lock.
        """
        if not self._pending:
            self._selected_index = 0
        elif self._selected_index >= len(self._pending):
            self._selected_index = len(self._pending) - 1

    def _notify(self, event: dict) -> None:
        """
        Fire the on_change callback if set.

        Args:
            event: Dict describing the state change.
        """
        callback = self.on_change
        if callback is not None:
            callback(event)
