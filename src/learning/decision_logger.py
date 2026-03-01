"""
Decision logger for tracking user review decisions.

Task 5B.1: Decision Logging
Phase 4, Item 4.1: SQLite migration — dual backend (JSONL fallback + SQLite)

Logs all review decisions for pattern detection and learning user
preferences over time.

When a Database instance is provided, all reads/writes go to the SQLite
decision_log table. When no database is provided, falls back to the
original JSONL file behavior for backward compatibility.

Storage location (JSONL fallback): ~/.email-analyzer/decisions.jsonl
Storage location (SQLite): ~/.email-analyzer/email_analyzer.db → decision_log table
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

from src.utils.logger import get_logger

if TYPE_CHECKING:
    from src.storage.database import Database

logger = get_logger(__name__)


class DecisionAction(str, Enum):
    """Actions that can be taken on a category during review."""

    ACCEPT = "accept"
    RENAME = "rename"
    MERGE = "merge"
    DELETE = "delete"
    SKIP = "skip"


@dataclass
class ReviewDecision:
    """
    Represents a single review decision made by the user.

    Attributes:
        timestamp: When the decision was made (UTC)
        category_name: Name of the category at decision time
        action: The action taken (accept, rename, merge, delete, skip)
        context: Additional context (old_name, new_name, merge_target, confidence, etc.)
    """

    timestamp: datetime
    category_name: str
    action: DecisionAction
    context: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "category_name": self.category_name,
            "action": self.action.value,
            "context": self.context,
        }

    @classmethod
    def from_dict(cls, data: dict) -> ReviewDecision:
        """Create ReviewDecision from dictionary."""
        return cls(
            timestamp=datetime.fromisoformat(data["timestamp"]),
            category_name=data["category_name"],
            action=DecisionAction(data["action"]),
            context=data.get("context", {}),
        )


def get_default_decisions_path() -> Path:
    """
    Get the default path for the decisions JSONL file.

    Returns:
        Path to ~/.email-analyzer/decisions.jsonl
    """
    return Path.home() / ".email-analyzer" / "decisions.jsonl"


class DecisionLogger:
    """
    Logger for tracking user review decisions.

    Stores decisions in JSONL format (one JSON object per line) for
    easy appending and reading. Supports:
    - Logging decisions with context
    - Retrieving all decisions or filtering by action type
    - Clearing decision history

    Example usage:
        logger = DecisionLogger()
        logger.log_decision("Newsletters", DecisionAction.ACCEPT)
        logger.log_decision("Old Name", DecisionAction.RENAME, old_name="Old Name", new_name="New Name")
        decisions = logger.get_decisions()
    """

    def __init__(
        self,
        decisions_path: Path | None = None,
        database: Database | None = None,
    ):
        """
        Initialize the decision logger.

        Args:
            decisions_path: Custom path for decisions file.
                           Defaults to ~/.email-analyzer/decisions.jsonl
            database: Optional Database instance. When provided, all reads/writes
                     go to the SQLite decision_log table instead of JSONL.
        """
        self.decisions_path = decisions_path or get_default_decisions_path()
        self._database = database

        # Ensure parent directory exists (needed for JSONL fallback)
        self.decisions_path.parent.mkdir(parents=True, exist_ok=True)

        backend = "SQLite" if database else "JSONL"
        logger.debug(
            f"DecisionLogger initialized with {backend} backend, path: {self.decisions_path}"
        )

    def log_decision(self, category_name: str, action: DecisionAction, **context) -> ReviewDecision:
        """
        Log a review decision.

        When a database is configured, writes to SQLite. Otherwise writes to JSONL.

        Args:
            category_name: Name of the category
            action: Action taken (accept, rename, merge, delete, skip)
            **context: Additional context (old_name, new_name, merge_target, confidence, etc.)

        Returns:
            The logged ReviewDecision object
        """
        decision = ReviewDecision(
            timestamp=datetime.now(timezone.utc),
            category_name=category_name,
            action=action,
            context=context,
        )

        if self._database is not None:
            self._write_decision_to_sqlite(decision)
        else:
            # Append to JSONL file
            with open(self.decisions_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(decision.to_dict()) + "\n")

        logger.debug(f"Logged decision: {action.value} for '{category_name}'")
        return decision

    def get_decisions(self, action_filter: DecisionAction | None = None) -> list[ReviewDecision]:
        """
        Get all logged decisions, optionally filtered by action type.

        When a database is configured, reads from SQLite. Otherwise reads from JSONL.

        Args:
            action_filter: If provided, only return decisions with this action

        Returns:
            List of ReviewDecision objects, oldest first
        """
        if self._database is not None:
            return self._get_decisions_from_sqlite(action_filter)

        if not self.decisions_path.exists():
            return []

        decisions = []
        with open(self.decisions_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    decision = ReviewDecision.from_dict(data)
                    if action_filter is None or decision.action == action_filter:
                        decisions.append(decision)
                except (json.JSONDecodeError, KeyError, ValueError) as e:
                    logger.warning(f"Skipping corrupt decision line: {e}")
                    continue

        return decisions

    def get_decision_count(self, action_filter: DecisionAction | None = None) -> int:
        """
        Get the count of logged decisions.

        Args:
            action_filter: If provided, only count decisions with this action

        Returns:
            Number of decisions matching the filter
        """
        return len(self.get_decisions(action_filter=action_filter))

    def clear_decisions(self) -> None:
        """
        Clear all logged decisions.

        When using SQLite, deletes all rows from the decision_log table.
        When using JSONL, removes the decisions file.

        This operation is irreversible.
        """
        if self._database is not None:
            self._database.execute("DELETE FROM decision_log")
            logger.info("Cleared decision history (SQLite)")
        elif self.decisions_path.exists():
            self.decisions_path.unlink()
            logger.info(f"Cleared decision history: {self.decisions_path}")
        else:
            logger.debug("No decision file to clear")

    # -------------------------------------------------------------------------
    # SQLite backend helpers
    # -------------------------------------------------------------------------

    def _write_decision_to_sqlite(self, decision: ReviewDecision) -> None:
        """
        Write a single ReviewDecision to the SQLite decision_log table.

        Each write is a single INSERT in autocommit mode (atomic).

        Args:
            decision: The ReviewDecision to persist.
        """
        assert self._database is not None
        sql = (
            "INSERT INTO decision_log (timestamp, category_name, action, context_json) "
            "VALUES (?, ?, ?, ?)"
        )
        params = (
            decision.timestamp.isoformat(),
            decision.category_name,
            decision.action.value,
            json.dumps(decision.context),
        )
        self._database.execute(sql, params)

    def _get_decisions_from_sqlite(
        self, action_filter: DecisionAction | None = None
    ) -> list[ReviewDecision]:
        """
        Read ReviewDecisions from the SQLite decision_log table.

        Args:
            action_filter: If provided, only return decisions with this action.

        Returns:
            List of ReviewDecision objects, oldest first (ordered by id).
        """
        assert self._database is not None

        if action_filter is not None:
            sql = (
                "SELECT timestamp, category_name, action, context_json "
                "FROM decision_log WHERE action = ? ORDER BY id"
            )
            cursor = self._database.execute(sql, (action_filter.value,))
        else:
            sql = (
                "SELECT timestamp, category_name, action, context_json "
                "FROM decision_log ORDER BY id"
            )
            cursor = self._database.execute(sql)

        decisions: list[ReviewDecision] = []
        for row in cursor.fetchall():
            timestamp_str, category_name, action_val, context_json = row
            decisions.append(
                ReviewDecision(
                    timestamp=datetime.fromisoformat(timestamp_str),
                    category_name=category_name,
                    action=DecisionAction(action_val),
                    context=json.loads(context_json) if context_json else {},
                )
            )
        return decisions
