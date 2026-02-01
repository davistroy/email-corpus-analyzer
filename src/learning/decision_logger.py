"""
Decision logger for tracking user review decisions.

Task 5B.1: Decision Logging

Logs all review decisions to a JSONL file for pattern detection
and learning user preferences over time.

Storage location: ~/.email-analyzer/decisions.jsonl
"""
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

from src.utils.logger import get_logger

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
    def from_dict(cls, data: dict) -> "ReviewDecision":
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

    def __init__(self, decisions_path: Path | None = None):
        """
        Initialize the decision logger.

        Args:
            decisions_path: Custom path for decisions file.
                           Defaults to ~/.email-analyzer/decisions.jsonl
        """
        self.decisions_path = decisions_path or get_default_decisions_path()

        # Ensure parent directory exists
        self.decisions_path.parent.mkdir(parents=True, exist_ok=True)

        logger.debug(f"DecisionLogger initialized with path: {self.decisions_path}")

    def log_decision(
        self,
        category_name: str,
        action: DecisionAction,
        **context
    ) -> ReviewDecision:
        """
        Log a review decision to the decisions file.

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

        # Append to JSONL file
        with open(self.decisions_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(decision.to_dict()) + "\n")

        logger.debug(f"Logged decision: {action.value} for '{category_name}'")
        return decision

    def get_decisions(
        self,
        action_filter: DecisionAction | None = None
    ) -> list[ReviewDecision]:
        """
        Get all logged decisions, optionally filtered by action type.

        Args:
            action_filter: If provided, only return decisions with this action

        Returns:
            List of ReviewDecision objects, oldest first
        """
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

    def get_decision_count(
        self,
        action_filter: DecisionAction | None = None
    ) -> int:
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
        Clear all logged decisions by removing the decisions file.

        This operation is irreversible.
        """
        if self.decisions_path.exists():
            self.decisions_path.unlink()
            logger.info(f"Cleared decision history: {self.decisions_path}")
        else:
            logger.debug("No decision file to clear")
