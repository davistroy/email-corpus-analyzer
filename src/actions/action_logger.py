"""
Action logger for tracking all mailbox modifications.

Phase 5, Item 5.4: Action Logger

Maintains an append-only JSONL audit trail of all email actions:
folder creation, email moves, rule deployments, rollbacks.
Supports rollback replay by reading the log and generating reverse operations.

Storage location: ~/.email-analyzer/action_log.jsonl
"""

import json
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

from src.utils.logger import get_logger

logger = get_logger(__name__)


class ActionType(str, Enum):
    """Types of mailbox actions that can be logged."""

    FOLDER_CREATE = "folder_create"
    FOLDER_DELETE = "folder_delete"
    EMAIL_MOVE = "email_move"
    LABEL_ADD = "label_add"
    LABEL_REMOVE = "label_remove"
    RULE_CREATE = "rule_create"
    RULE_DELETE = "rule_delete"
    ROLLBACK = "rollback"


# Mapping from action types to their reverse actions
_REVERSE_ACTION_MAP: dict[ActionType, str] = {
    ActionType.FOLDER_CREATE: "folder_delete",
    ActionType.FOLDER_DELETE: "folder_create",
    ActionType.EMAIL_MOVE: "email_move",  # swap source/target
    ActionType.LABEL_ADD: "label_remove",
    ActionType.LABEL_REMOVE: "label_add",
    ActionType.RULE_CREATE: "rule_delete",
    ActionType.RULE_DELETE: "rule_create",
}


@dataclass
class ActionRecord:
    """
    Represents a single mailbox action.

    Attributes:
        timestamp: When the action occurred (UTC)
        action_type: Type of action performed
        target_id: ID of the target object (email, folder, rule)
        details: Additional context (folder names, rule config, etc.)
        success: Whether the action succeeded
        reversible: Whether this action can be rolled back
    """

    timestamp: datetime
    action_type: ActionType
    target_id: str
    success: bool
    reversible: bool
    details: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "action_type": self.action_type.value,
            "target_id": self.target_id,
            "details": self.details,
            "success": self.success,
            "reversible": self.reversible,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ActionRecord":
        """Create ActionRecord from dictionary."""
        return cls(
            timestamp=datetime.fromisoformat(data["timestamp"]),
            action_type=ActionType(data["action_type"]),
            target_id=data["target_id"],
            details=data.get("details", {}),
            success=data["success"],
            reversible=data["reversible"],
        )


@dataclass
class ActionLog:
    """
    Collection of ActionRecords with aggregate metadata.

    Provides convenience properties for counting successes, failures,
    and reversible actions.
    """

    records: list[ActionRecord]

    @property
    def total_count(self) -> int:
        """Total number of records."""
        return len(self.records)

    @property
    def success_count(self) -> int:
        """Number of successful actions."""
        return sum(1 for r in self.records if r.success)

    @property
    def failure_count(self) -> int:
        """Number of failed actions."""
        return sum(1 for r in self.records if not r.success)

    @property
    def reversible_count(self) -> int:
        """Number of reversible actions."""
        return sum(1 for r in self.records if r.reversible)

    def filter_by_type(self, action_type: ActionType) -> list[ActionRecord]:
        """Filter records by action type."""
        return [r for r in self.records if r.action_type == action_type]


@dataclass
class RollbackResult:
    """
    Result of a rollback replay operation.

    Attributes:
        total_actions: Total number of actions attempted
        successful: Number of successfully reversed actions
        failed: Number of failed reversals
        skipped: Number of non-reversible actions skipped
        errors: List of error messages from failed reversals
    """

    total_actions: int
    successful: int
    failed: int
    skipped: int
    errors: list[str] = field(default_factory=list)

    @property
    def all_succeeded(self) -> bool:
        """Whether all attempted actions succeeded (skipped don't count as failure)."""
        return self.failed == 0


def get_default_action_log_path() -> Path:
    """
    Get the default path for the action log JSONL file.

    Returns:
        Path to ~/.email-analyzer/action_log.jsonl
    """
    return Path.home() / ".email-analyzer" / "action_log.jsonl"


class ActionLogger:
    """
    Logger for tracking all mailbox modifications with rollback support.

    Maintains an append-only JSONL audit trail. All writes are thread-safe
    via a threading lock. Supports:
    - Logging actions with full context
    - Retrieving actions with optional type filtering
    - Identifying rollback-eligible actions
    - Replaying rollback operations (generating reverse records)
    - Clearing action history

    Example usage:
        logger = ActionLogger()
        logger.log_action(
            action_type=ActionType.EMAIL_MOVE,
            target_id="msg_001",
            details={"source_folder": "inbox", "target_folder": "News"},
            success=True,
            reversible=True,
        )
        rollback_actions = logger.get_rollback_actions(since=cutoff)
        result = logger.replay_rollback(rollback_actions)
    """

    def __init__(self, log_path: Path | None = None):
        """
        Initialize the action logger.

        Args:
            log_path: Custom path for action log file.
                     Defaults to ~/.email-analyzer/action_log.jsonl
        """
        self.log_path = log_path or get_default_action_log_path()
        self._lock = threading.Lock()

        # Ensure parent directory exists
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

        logger.debug(f"ActionLogger initialized with path: {self.log_path}")

    def log_action(
        self,
        action_type: ActionType,
        target_id: str,
        details: dict | None = None,
        success: bool = True,
        reversible: bool = True,
    ) -> ActionRecord:
        """
        Log a mailbox action to the audit trail.

        Thread-safe: uses a lock to prevent interleaved writes.

        Args:
            action_type: Type of action performed
            target_id: ID of the target object
            details: Additional context for the action
            success: Whether the action succeeded
            reversible: Whether this action can be rolled back

        Returns:
            The logged ActionRecord
        """
        record = ActionRecord(
            timestamp=datetime.now(timezone.utc),
            action_type=action_type,
            target_id=target_id,
            details=details or {},
            success=success,
            reversible=reversible,
        )

        with self._lock, open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record.to_dict()) + "\n")

        logger.debug(f"Logged action: {action_type.value} for '{target_id}' (success={success})")
        return record

    def get_actions(self, action_type_filter: ActionType | None = None) -> list[ActionRecord]:
        """
        Get all logged actions, optionally filtered by action type.

        Args:
            action_type_filter: If provided, only return actions of this type

        Returns:
            List of ActionRecord objects, oldest first
        """
        if not self.log_path.exists():
            return []

        records: list[ActionRecord] = []
        with open(self.log_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    record = ActionRecord.from_dict(data)
                    if action_type_filter is None or record.action_type == action_type_filter:
                        records.append(record)
                except (json.JSONDecodeError, KeyError, ValueError) as e:
                    logger.warning(f"Skipping corrupt action log line: {e}")
                    continue

        return records

    def get_action_count(self, action_type_filter: ActionType | None = None) -> int:
        """
        Get the count of logged actions.

        Args:
            action_type_filter: If provided, only count actions of this type

        Returns:
            Number of actions matching the filter
        """
        return len(self.get_actions(action_type_filter=action_type_filter))

    def get_action_log(self) -> ActionLog:
        """
        Get all actions as an ActionLog collection with metadata.

        Returns:
            ActionLog with all records and aggregate statistics
        """
        return ActionLog(records=self.get_actions())

    def get_rollback_actions(self, since: datetime | None = None) -> list[ActionRecord]:
        """
        Get actions that can be reversed, in reverse chronological order.

        Filters to only successful, reversible actions that haven't already
        been rolled back. Returns in reverse order so the most recent action
        is undone first.

        Args:
            since: If provided, only return actions after this datetime

        Returns:
            List of reversible ActionRecords in reverse chronological order
        """
        all_actions = self.get_actions()

        # Find target_ids that have already been rolled back
        rolled_back_ids: set[str] = set()
        for record in all_actions:
            if record.action_type == ActionType.ROLLBACK and record.success:
                rolled_back_ids.add(record.target_id)

        # Filter to reversible, successful, non-rolled-back actions
        eligible: list[ActionRecord] = []
        for record in all_actions:
            if record.action_type == ActionType.ROLLBACK:
                continue
            if not record.success or not record.reversible:
                continue
            if record.target_id in rolled_back_ids:
                continue
            if since is not None and record.timestamp < since:
                continue
            eligible.append(record)

        # Return in reverse chronological order
        eligible.reverse()
        return eligible

    def replay_rollback(self, actions: list[ActionRecord]) -> RollbackResult:
        """
        Execute reverse operations for the given actions.

        For each reversible action, generates a reverse record and logs it.
        Non-reversible actions are skipped. The reverse records are logged
        as ROLLBACK action types to prevent re-rollback.

        Args:
            actions: List of ActionRecords to reverse

        Returns:
            RollbackResult summarizing the operation
        """
        if not actions:
            return RollbackResult(
                total_actions=0,
                successful=0,
                failed=0,
                skipped=0,
                errors=[],
            )

        successful = 0
        failed = 0
        skipped = 0
        errors: list[str] = []

        for action in actions:
            reverse = self._generate_reverse_record(action)
            if reverse is None:
                skipped += 1
                continue

            try:
                # Log the rollback record to the audit trail
                with self._lock, open(self.log_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(reverse.to_dict()) + "\n")
                successful += 1
                logger.debug(f"Rolled back: {action.action_type.value} for '{action.target_id}'")
            except Exception as e:
                failed += 1
                error_msg = (
                    f"Failed to rollback {action.action_type.value} for '{action.target_id}': {e}"
                )
                errors.append(error_msg)
                logger.error(error_msg)

        return RollbackResult(
            total_actions=len(actions),
            successful=successful,
            failed=failed,
            skipped=skipped,
            errors=errors,
        )

    def _generate_reverse_record(self, record: ActionRecord) -> ActionRecord | None:
        """
        Generate a reverse ActionRecord for rollback.

        Maps each action type to its reverse operation and constructs
        the appropriate details for the reverse action.

        Args:
            record: The original ActionRecord to reverse

        Returns:
            A new ActionRecord representing the reverse operation,
            or None if the action is not reversible
        """
        if not record.reversible:
            return None

        reverse_action = _REVERSE_ACTION_MAP.get(record.action_type)
        if reverse_action is None:
            return None

        # Build reverse details based on action type
        reverse_details: dict = {
            "original_action": record.action_type.value,
            "reverse_action": reverse_action,
            "original_details": record.details,
        }

        if record.action_type == ActionType.EMAIL_MOVE:
            # Swap source and target folders
            reverse_details["reverse_details"] = {
                "source_folder": record.details.get("target_folder", ""),
                "target_folder": record.details.get("source_folder", ""),
                "source_folder_id": record.details.get("target_folder_id", ""),
                "target_folder_id": record.details.get("source_folder_id", ""),
            }
        elif record.action_type in (ActionType.LABEL_ADD, ActionType.LABEL_REMOVE):
            reverse_details["reverse_details"] = {
                "label": record.details.get("label", ""),
            }

        return ActionRecord(
            timestamp=datetime.now(timezone.utc),
            action_type=ActionType.ROLLBACK,
            target_id=record.target_id,
            details=reverse_details,
            success=True,
            reversible=False,  # Rollback records are not themselves reversible
        )

    def clear_actions(self) -> None:
        """
        Clear all logged actions by removing the action log file.

        This operation is irreversible.
        """
        if self.log_path.exists():
            self.log_path.unlink()
            logger.info(f"Cleared action log: {self.log_path}")
        else:
            logger.debug("No action log file to clear")
