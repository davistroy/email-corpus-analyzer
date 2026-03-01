"""
Unit tests for the action logger module.

Tests the ActionLogger class for logging mailbox modifications to an
append-only JSONL audit trail, with rollback support. Also tests the
SQLite backend path (Phase 4, Work Item 4.1).

Phase 5, Item 5.4: Action Logger
Phase 4, Item 4.1: SQLite migration
"""

import json
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.actions.action_logger import (
    ActionLog,
    ActionLogger,
    ActionRecord,
    ActionType,
    RollbackResult,
    get_default_action_log_path,
)
from src.storage.database import Database

# =============================================================================
# ActionType enum tests
# =============================================================================


class TestActionType:
    """Test the ActionType enum."""

    def test_all_action_type_values_exist(self):
        """Test that all required action type values exist."""
        assert ActionType.FOLDER_CREATE.value == "folder_create"
        assert ActionType.FOLDER_DELETE.value == "folder_delete"
        assert ActionType.EMAIL_MOVE.value == "email_move"
        assert ActionType.LABEL_ADD.value == "label_add"
        assert ActionType.LABEL_REMOVE.value == "label_remove"
        assert ActionType.RULE_CREATE.value == "rule_create"
        assert ActionType.RULE_DELETE.value == "rule_delete"
        assert ActionType.ROLLBACK.value == "rollback"

    def test_action_type_from_string(self):
        """Test converting string to action type."""
        assert ActionType("folder_create") == ActionType.FOLDER_CREATE
        assert ActionType("email_move") == ActionType.EMAIL_MOVE
        assert ActionType("rule_create") == ActionType.RULE_CREATE
        assert ActionType("rollback") == ActionType.ROLLBACK

    def test_action_type_invalid_raises(self):
        """Test that invalid action type raises ValueError."""
        with pytest.raises(ValueError):
            ActionType("invalid_action")

    def test_action_type_is_string_enum(self):
        """Test that ActionType behaves as str enum."""
        assert isinstance(ActionType.FOLDER_CREATE, str)
        assert ActionType.FOLDER_CREATE == "folder_create"


# =============================================================================
# ActionRecord model tests
# =============================================================================


class TestActionRecord:
    """Test the ActionRecord dataclass."""

    def test_create_folder_create_record(self):
        """Test creating a folder creation record."""
        now = datetime.now(timezone.utc)
        record = ActionRecord(
            timestamp=now,
            action_type=ActionType.FOLDER_CREATE,
            target_id="folder_abc123",
            details={"folder_name": "Newsletters", "parent_id": "inbox"},
            success=True,
            reversible=True,
        )
        assert record.action_type == ActionType.FOLDER_CREATE
        assert record.target_id == "folder_abc123"
        assert record.details["folder_name"] == "Newsletters"
        assert record.success is True
        assert record.reversible is True
        assert record.timestamp == now

    def test_create_email_move_record(self):
        """Test creating an email move record."""
        record = ActionRecord(
            timestamp=datetime.now(timezone.utc),
            action_type=ActionType.EMAIL_MOVE,
            target_id="msg_xyz789",
            details={
                "source_folder": "inbox",
                "target_folder": "Newsletters",
                "source_folder_id": "folder_inbox",
                "target_folder_id": "folder_news",
            },
            success=True,
            reversible=True,
        )
        assert record.action_type == ActionType.EMAIL_MOVE
        assert record.details["source_folder"] == "inbox"
        assert record.details["target_folder"] == "Newsletters"

    def test_create_rule_deploy_record(self):
        """Test creating a rule deployment record."""
        record = ActionRecord(
            timestamp=datetime.now(timezone.utc),
            action_type=ActionType.RULE_CREATE,
            target_id="rule_001",
            details={
                "rule_name": "Newsletter Filter",
                "conditions": {"from": "newsletter@example.com"},
                "actions": {"move_to": "Newsletters"},
            },
            success=True,
            reversible=True,
        )
        assert record.action_type == ActionType.RULE_CREATE
        assert record.details["rule_name"] == "Newsletter Filter"

    def test_create_failed_record(self):
        """Test creating a record for a failed action."""
        record = ActionRecord(
            timestamp=datetime.now(timezone.utc),
            action_type=ActionType.EMAIL_MOVE,
            target_id="msg_fail",
            details={"error": "Permission denied", "source_folder": "inbox"},
            success=False,
            reversible=False,
        )
        assert record.success is False
        assert record.reversible is False
        assert record.details["error"] == "Permission denied"

    def test_create_non_reversible_record(self):
        """Test creating a non-reversible action record."""
        record = ActionRecord(
            timestamp=datetime.now(timezone.utc),
            action_type=ActionType.FOLDER_DELETE,
            target_id="folder_old",
            details={"folder_name": "Deprecated"},
            success=True,
            reversible=False,
        )
        assert record.reversible is False

    def test_default_details_empty_dict(self):
        """Test that details defaults to empty dict."""
        record = ActionRecord(
            timestamp=datetime.now(timezone.utc),
            action_type=ActionType.FOLDER_CREATE,
            target_id="folder_1",
            success=True,
            reversible=True,
        )
        assert record.details == {}

    def test_to_dict_serialization(self):
        """Test ActionRecord serializes to dict correctly."""
        now = datetime(2026, 2, 28, 12, 0, 0, tzinfo=timezone.utc)
        record = ActionRecord(
            timestamp=now,
            action_type=ActionType.EMAIL_MOVE,
            target_id="msg_001",
            details={"source_folder": "inbox", "target_folder": "Archive"},
            success=True,
            reversible=True,
        )
        d = record.to_dict()
        assert d["timestamp"] == "2026-02-28T12:00:00+00:00"
        assert d["action_type"] == "email_move"
        assert d["target_id"] == "msg_001"
        assert d["details"]["source_folder"] == "inbox"
        assert d["success"] is True
        assert d["reversible"] is True

    def test_from_dict_deserialization(self):
        """Test ActionRecord deserializes from dict correctly."""
        data = {
            "timestamp": "2026-02-28T12:00:00+00:00",
            "action_type": "email_move",
            "target_id": "msg_001",
            "details": {"source_folder": "inbox", "target_folder": "Archive"},
            "success": True,
            "reversible": True,
        }
        record = ActionRecord.from_dict(data)
        assert record.action_type == ActionType.EMAIL_MOVE
        assert record.target_id == "msg_001"
        assert record.timestamp == datetime(2026, 2, 28, 12, 0, 0, tzinfo=timezone.utc)
        assert record.success is True
        assert record.reversible is True

    def test_round_trip_serialization(self):
        """Test that to_dict -> from_dict preserves all fields."""
        original = ActionRecord(
            timestamp=datetime.now(timezone.utc),
            action_type=ActionType.RULE_CREATE,
            target_id="rule_42",
            details={"rule_name": "Test", "priority": 5},
            success=True,
            reversible=True,
        )
        restored = ActionRecord.from_dict(original.to_dict())
        assert restored.action_type == original.action_type
        assert restored.target_id == original.target_id
        assert restored.details == original.details
        assert restored.success == original.success
        assert restored.reversible == original.reversible
        # Timestamps should be equal (within microsecond precision of isoformat)
        assert abs((restored.timestamp - original.timestamp).total_seconds()) < 0.001

    def test_to_dict_json_serializable(self):
        """Test that to_dict output is JSON serializable."""
        record = ActionRecord(
            timestamp=datetime.now(timezone.utc),
            action_type=ActionType.FOLDER_CREATE,
            target_id="folder_1",
            details={"name": "Test", "nested": {"key": "value"}},
            success=True,
            reversible=True,
        )
        # Should not raise
        json_str = json.dumps(record.to_dict())
        assert isinstance(json_str, str)


# =============================================================================
# ActionLog model tests
# =============================================================================


class TestActionLog:
    """Test the ActionLog collection model."""

    def test_empty_action_log(self):
        """Test creating an empty action log."""
        log = ActionLog(records=[])
        assert len(log.records) == 0
        assert log.total_count == 0

    def test_action_log_with_records(self):
        """Test creating action log with records."""
        records = [
            ActionRecord(
                timestamp=datetime.now(timezone.utc),
                action_type=ActionType.FOLDER_CREATE,
                target_id=f"folder_{i}",
                success=True,
                reversible=True,
            )
            for i in range(3)
        ]
        log = ActionLog(records=records)
        assert log.total_count == 3

    def test_action_log_success_count(self):
        """Test counting successful actions."""
        records = [
            ActionRecord(
                timestamp=datetime.now(timezone.utc),
                action_type=ActionType.EMAIL_MOVE,
                target_id=f"msg_{i}",
                success=i < 2,  # first 2 succeed, third fails
                reversible=True,
            )
            for i in range(3)
        ]
        log = ActionLog(records=records)
        assert log.success_count == 2
        assert log.failure_count == 1

    def test_action_log_reversible_count(self):
        """Test counting reversible actions."""
        records = [
            ActionRecord(
                timestamp=datetime.now(timezone.utc),
                action_type=ActionType.EMAIL_MOVE,
                target_id=f"msg_{i}",
                success=True,
                reversible=i != 1,  # second is not reversible
            )
            for i in range(3)
        ]
        log = ActionLog(records=records)
        assert log.reversible_count == 2

    def test_action_log_filter_by_type(self):
        """Test filtering records by action type."""
        records = [
            ActionRecord(
                timestamp=datetime.now(timezone.utc),
                action_type=ActionType.FOLDER_CREATE,
                target_id="folder_1",
                success=True,
                reversible=True,
            ),
            ActionRecord(
                timestamp=datetime.now(timezone.utc),
                action_type=ActionType.EMAIL_MOVE,
                target_id="msg_1",
                success=True,
                reversible=True,
            ),
            ActionRecord(
                timestamp=datetime.now(timezone.utc),
                action_type=ActionType.EMAIL_MOVE,
                target_id="msg_2",
                success=True,
                reversible=True,
            ),
        ]
        log = ActionLog(records=records)
        moves = log.filter_by_type(ActionType.EMAIL_MOVE)
        assert len(moves) == 2
        folders = log.filter_by_type(ActionType.FOLDER_CREATE)
        assert len(folders) == 1


# =============================================================================
# RollbackResult model tests
# =============================================================================


class TestRollbackResult:
    """Test the RollbackResult dataclass."""

    def test_rollback_result_all_success(self):
        """Test rollback result when all actions succeed."""
        result = RollbackResult(
            total_actions=5,
            successful=5,
            failed=0,
            skipped=0,
            errors=[],
        )
        assert result.total_actions == 5
        assert result.successful == 5
        assert result.all_succeeded is True

    def test_rollback_result_with_failures(self):
        """Test rollback result with failures."""
        result = RollbackResult(
            total_actions=5,
            successful=3,
            failed=1,
            skipped=1,
            errors=["Failed to unmove msg_3: permission denied"],
        )
        assert result.all_succeeded is False
        assert len(result.errors) == 1

    def test_rollback_result_empty(self):
        """Test rollback result with no actions."""
        result = RollbackResult(
            total_actions=0,
            successful=0,
            failed=0,
            skipped=0,
            errors=[],
        )
        assert result.all_succeeded is True


# =============================================================================
# get_default_action_log_path tests
# =============================================================================


class TestGetDefaultActionLogPath:
    """Test the default action log path function."""

    def test_returns_path_in_home_directory(self):
        """Test that default path is under home directory."""
        path = get_default_action_log_path()
        assert path.parent.name == ".email-analyzer"
        assert path.name == "action_log.jsonl"
        assert Path.home() in path.parents

    def test_returns_path_object(self):
        """Test that the function returns a Path object."""
        path = get_default_action_log_path()
        assert isinstance(path, Path)


# =============================================================================
# ActionLogger core tests
# =============================================================================


class TestActionLoggerInit:
    """Test ActionLogger initialization."""

    def test_init_default_path(self):
        """Test that logger initializes with default path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "action_log.jsonl"
            logger = ActionLogger(log_path=path)
            assert logger.log_path == path

    def test_init_creates_parent_directory(self):
        """Test that logger creates parent directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "subdir" / "nested" / "action_log.jsonl"
            logger = ActionLogger(log_path=path)
            assert logger.log_path.parent.exists()

    def test_init_with_existing_file(self):
        """Test that logger works with existing log file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "action_log.jsonl"
            path.touch()
            logger = ActionLogger(log_path=path)
            assert logger.log_path == path


# =============================================================================
# ActionLogger log_action tests
# =============================================================================


class TestActionLoggerLogAction:
    """Test ActionLogger.log_action method."""

    def test_log_folder_create(self):
        """Test logging a folder creation action."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "action_log.jsonl"
            logger = ActionLogger(log_path=path)

            record = logger.log_action(
                action_type=ActionType.FOLDER_CREATE,
                target_id="folder_abc",
                details={"folder_name": "Newsletters", "parent_id": "inbox"},
                success=True,
                reversible=True,
            )

            assert record.action_type == ActionType.FOLDER_CREATE
            assert record.target_id == "folder_abc"
            assert record.success is True
            assert record.reversible is True
            assert record.timestamp is not None

    def test_log_email_move(self):
        """Test logging an email move action."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "action_log.jsonl"
            logger = ActionLogger(log_path=path)

            record = logger.log_action(
                action_type=ActionType.EMAIL_MOVE,
                target_id="msg_001",
                details={
                    "source_folder": "inbox",
                    "target_folder": "Newsletters",
                },
                success=True,
                reversible=True,
            )

            assert record.action_type == ActionType.EMAIL_MOVE
            assert record.details["source_folder"] == "inbox"

    def test_log_rule_create(self):
        """Test logging a rule deployment action."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "action_log.jsonl"
            logger = ActionLogger(log_path=path)

            record = logger.log_action(
                action_type=ActionType.RULE_CREATE,
                target_id="rule_001",
                details={"rule_name": "Newsletter Filter"},
                success=True,
                reversible=True,
            )

            assert record.action_type == ActionType.RULE_CREATE

    def test_log_failed_action(self):
        """Test logging a failed action."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "action_log.jsonl"
            logger = ActionLogger(log_path=path)

            record = logger.log_action(
                action_type=ActionType.EMAIL_MOVE,
                target_id="msg_fail",
                details={"error": "Permission denied"},
                success=False,
                reversible=False,
            )

            assert record.success is False
            assert record.reversible is False

    def test_log_appends_to_file(self):
        """Test that each log call appends a line to the JSONL file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "action_log.jsonl"
            logger = ActionLogger(log_path=path)

            logger.log_action(
                action_type=ActionType.FOLDER_CREATE,
                target_id="folder_1",
                success=True,
                reversible=True,
            )
            logger.log_action(
                action_type=ActionType.EMAIL_MOVE,
                target_id="msg_1",
                success=True,
                reversible=True,
            )

            lines = path.read_text(encoding="utf-8").strip().split("\n")
            assert len(lines) == 2

    def test_log_writes_valid_json_per_line(self):
        """Test that each line in the log is valid JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "action_log.jsonl"
            logger = ActionLogger(log_path=path)

            logger.log_action(
                action_type=ActionType.FOLDER_CREATE,
                target_id="folder_1",
                details={"name": "Test"},
                success=True,
                reversible=True,
            )

            line = path.read_text(encoding="utf-8").strip()
            data = json.loads(line)
            assert data["action_type"] == "folder_create"
            assert data["target_id"] == "folder_1"
            assert data["success"] is True

    def test_log_returns_action_record(self):
        """Test that log_action returns the ActionRecord."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "action_log.jsonl"
            logger = ActionLogger(log_path=path)

            result = logger.log_action(
                action_type=ActionType.FOLDER_CREATE,
                target_id="folder_1",
                success=True,
                reversible=True,
            )

            assert isinstance(result, ActionRecord)

    def test_log_default_details_empty(self):
        """Test that details defaults to empty dict when not provided."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "action_log.jsonl"
            logger = ActionLogger(log_path=path)

            record = logger.log_action(
                action_type=ActionType.FOLDER_CREATE,
                target_id="folder_1",
                success=True,
                reversible=True,
            )

            assert record.details == {}


# =============================================================================
# ActionLogger get_actions tests
# =============================================================================


class TestActionLoggerGetActions:
    """Test ActionLogger.get_actions method."""

    def test_get_actions_empty_file(self):
        """Test getting actions from non-existent file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "action_log.jsonl"
            logger = ActionLogger(log_path=path)

            actions = logger.get_actions()
            assert actions == []

    def test_get_all_actions(self):
        """Test retrieving all logged actions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "action_log.jsonl"
            logger = ActionLogger(log_path=path)

            logger.log_action(
                action_type=ActionType.FOLDER_CREATE,
                target_id="folder_1",
                success=True,
                reversible=True,
            )
            logger.log_action(
                action_type=ActionType.EMAIL_MOVE,
                target_id="msg_1",
                success=True,
                reversible=True,
            )

            actions = logger.get_actions()
            assert len(actions) == 2
            assert actions[0].action_type == ActionType.FOLDER_CREATE
            assert actions[1].action_type == ActionType.EMAIL_MOVE

    def test_get_actions_filtered_by_type(self):
        """Test filtering actions by type."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "action_log.jsonl"
            logger = ActionLogger(log_path=path)

            logger.log_action(
                action_type=ActionType.FOLDER_CREATE,
                target_id="folder_1",
                success=True,
                reversible=True,
            )
            logger.log_action(
                action_type=ActionType.EMAIL_MOVE,
                target_id="msg_1",
                success=True,
                reversible=True,
            )
            logger.log_action(
                action_type=ActionType.EMAIL_MOVE,
                target_id="msg_2",
                success=True,
                reversible=True,
            )

            moves = logger.get_actions(action_type_filter=ActionType.EMAIL_MOVE)
            assert len(moves) == 2
            assert all(a.action_type == ActionType.EMAIL_MOVE for a in moves)

    def test_get_actions_skips_corrupt_lines(self):
        """Test that corrupt JSONL lines are skipped gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "action_log.jsonl"
            logger = ActionLogger(log_path=path)

            # Write a valid record
            logger.log_action(
                action_type=ActionType.FOLDER_CREATE,
                target_id="folder_1",
                success=True,
                reversible=True,
            )

            # Manually write a corrupt line
            with open(path, "a", encoding="utf-8") as f:
                f.write("this is not valid json\n")

            # Write another valid record
            logger.log_action(
                action_type=ActionType.EMAIL_MOVE,
                target_id="msg_1",
                success=True,
                reversible=True,
            )

            actions = logger.get_actions()
            assert len(actions) == 2  # skipped corrupt line

    def test_get_actions_skips_empty_lines(self):
        """Test that empty lines in JSONL are skipped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "action_log.jsonl"
            logger = ActionLogger(log_path=path)

            logger.log_action(
                action_type=ActionType.FOLDER_CREATE,
                target_id="folder_1",
                success=True,
                reversible=True,
            )

            # Append empty lines
            with open(path, "a", encoding="utf-8") as f:
                f.write("\n\n\n")

            actions = logger.get_actions()
            assert len(actions) == 1

    def test_get_actions_preserves_order(self):
        """Test that actions are returned in chronological order."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "action_log.jsonl"
            logger = ActionLogger(log_path=path)

            for i in range(5):
                logger.log_action(
                    action_type=ActionType.EMAIL_MOVE,
                    target_id=f"msg_{i}",
                    success=True,
                    reversible=True,
                )

            actions = logger.get_actions()
            assert [a.target_id for a in actions] == [f"msg_{i}" for i in range(5)]


# =============================================================================
# ActionLogger get_action_count tests
# =============================================================================


class TestActionLoggerGetActionCount:
    """Test ActionLogger.get_action_count method."""

    def test_count_empty(self):
        """Test count with no actions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "action_log.jsonl"
            logger = ActionLogger(log_path=path)
            assert logger.get_action_count() == 0

    def test_count_all(self):
        """Test counting all actions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "action_log.jsonl"
            logger = ActionLogger(log_path=path)

            for i in range(3):
                logger.log_action(
                    action_type=ActionType.EMAIL_MOVE,
                    target_id=f"msg_{i}",
                    success=True,
                    reversible=True,
                )

            assert logger.get_action_count() == 3

    def test_count_filtered_by_type(self):
        """Test counting actions filtered by type."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "action_log.jsonl"
            logger = ActionLogger(log_path=path)

            logger.log_action(
                action_type=ActionType.FOLDER_CREATE,
                target_id="f_1",
                success=True,
                reversible=True,
            )
            logger.log_action(
                action_type=ActionType.EMAIL_MOVE,
                target_id="m_1",
                success=True,
                reversible=True,
            )
            logger.log_action(
                action_type=ActionType.EMAIL_MOVE,
                target_id="m_2",
                success=True,
                reversible=True,
            )

            assert logger.get_action_count(action_type_filter=ActionType.EMAIL_MOVE) == 2
            assert logger.get_action_count(action_type_filter=ActionType.FOLDER_CREATE) == 1


# =============================================================================
# ActionLogger get_rollback_actions tests
# =============================================================================


class TestActionLoggerGetRollbackActions:
    """Test ActionLogger.get_rollback_actions method."""

    def test_get_rollback_actions_returns_reversible_only(self):
        """Test that only reversible successful actions are returned."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "action_log.jsonl"
            logger = ActionLogger(log_path=path)

            logger.log_action(
                action_type=ActionType.EMAIL_MOVE,
                target_id="msg_1",
                details={"source_folder": "inbox", "target_folder": "News"},
                success=True,
                reversible=True,
            )
            logger.log_action(
                action_type=ActionType.EMAIL_MOVE,
                target_id="msg_2",
                details={"error": "failed"},
                success=False,
                reversible=False,
            )
            logger.log_action(
                action_type=ActionType.FOLDER_CREATE,
                target_id="folder_1",
                details={"folder_name": "News"},
                success=True,
                reversible=False,  # explicitly not reversible
            )

            rollback = logger.get_rollback_actions()
            assert len(rollback) == 1
            assert rollback[0].target_id == "msg_1"

    def test_get_rollback_actions_since_datetime(self):
        """Test filtering rollback actions by datetime."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "action_log.jsonl"
            logger = ActionLogger(log_path=path)

            # Write records with specific timestamps
            old_time = datetime(2026, 1, 1, tzinfo=timezone.utc)
            recent_time = datetime(2026, 2, 28, tzinfo=timezone.utc)

            old_record = ActionRecord(
                timestamp=old_time,
                action_type=ActionType.EMAIL_MOVE,
                target_id="msg_old",
                details={"source_folder": "inbox", "target_folder": "Old"},
                success=True,
                reversible=True,
            )
            recent_record = ActionRecord(
                timestamp=recent_time,
                action_type=ActionType.EMAIL_MOVE,
                target_id="msg_recent",
                details={"source_folder": "inbox", "target_folder": "Recent"},
                success=True,
                reversible=True,
            )

            # Manually write with controlled timestamps
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(old_record.to_dict()) + "\n")
                f.write(json.dumps(recent_record.to_dict()) + "\n")

            since = datetime(2026, 2, 1, tzinfo=timezone.utc)
            rollback = logger.get_rollback_actions(since=since)
            assert len(rollback) == 1
            assert rollback[0].target_id == "msg_recent"

    def test_get_rollback_actions_returned_in_reverse_order(self):
        """Test that rollback actions are returned in reverse chronological order."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "action_log.jsonl"
            logger = ActionLogger(log_path=path)

            for i in range(3):
                logger.log_action(
                    action_type=ActionType.EMAIL_MOVE,
                    target_id=f"msg_{i}",
                    details={"source_folder": "inbox", "target_folder": f"folder_{i}"},
                    success=True,
                    reversible=True,
                )

            rollback = logger.get_rollback_actions()
            # Should be reversed: msg_2, msg_1, msg_0
            assert [r.target_id for r in rollback] == ["msg_2", "msg_1", "msg_0"]

    def test_get_rollback_actions_excludes_already_rolled_back(self):
        """Test that actions already rolled back are excluded."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "action_log.jsonl"
            logger = ActionLogger(log_path=path)

            # Original action
            logger.log_action(
                action_type=ActionType.EMAIL_MOVE,
                target_id="msg_1",
                details={"source_folder": "inbox", "target_folder": "News"},
                success=True,
                reversible=True,
            )
            # Rollback record for that action
            logger.log_action(
                action_type=ActionType.ROLLBACK,
                target_id="msg_1",
                details={"original_action": "email_move", "rolled_back": True},
                success=True,
                reversible=False,
            )
            # Another action that hasn't been rolled back
            logger.log_action(
                action_type=ActionType.EMAIL_MOVE,
                target_id="msg_2",
                details={"source_folder": "inbox", "target_folder": "Archive"},
                success=True,
                reversible=True,
            )

            rollback = logger.get_rollback_actions()
            assert len(rollback) == 1
            assert rollback[0].target_id == "msg_2"

    def test_get_rollback_actions_empty_log(self):
        """Test getting rollback actions from empty log."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "action_log.jsonl"
            logger = ActionLogger(log_path=path)

            rollback = logger.get_rollback_actions()
            assert rollback == []


# =============================================================================
# ActionLogger replay_rollback tests
# =============================================================================


class TestActionLoggerReplayRollback:
    """Test ActionLogger.replay_rollback method."""

    def test_replay_rollback_generates_reverse_records(self):
        """Test that replay_rollback generates reverse action records."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "action_log.jsonl"
            logger = ActionLogger(log_path=path)

            # Create some actions
            logger.log_action(
                action_type=ActionType.EMAIL_MOVE,
                target_id="msg_1",
                details={
                    "source_folder": "inbox",
                    "target_folder": "Newsletters",
                    "source_folder_id": "id_inbox",
                    "target_folder_id": "id_news",
                },
                success=True,
                reversible=True,
            )

            actions_to_rollback = logger.get_rollback_actions()
            result = logger.replay_rollback(actions_to_rollback)

            assert isinstance(result, RollbackResult)
            assert result.total_actions == 1
            # Rollback records should be written to the log
            all_actions = logger.get_actions()
            rollback_records = [a for a in all_actions if a.action_type == ActionType.ROLLBACK]
            assert len(rollback_records) == 1

    def test_replay_rollback_empty_list(self):
        """Test replaying empty rollback list."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "action_log.jsonl"
            logger = ActionLogger(log_path=path)

            result = logger.replay_rollback([])
            assert result.total_actions == 0
            assert result.successful == 0
            assert result.all_succeeded is True

    def test_replay_rollback_skips_non_reversible(self):
        """Test that non-reversible actions are skipped in rollback."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "action_log.jsonl"
            logger = ActionLogger(log_path=path)

            non_reversible = ActionRecord(
                timestamp=datetime.now(timezone.utc),
                action_type=ActionType.FOLDER_DELETE,
                target_id="folder_1",
                details={},
                success=True,
                reversible=False,
            )

            result = logger.replay_rollback([non_reversible])
            assert result.total_actions == 1
            assert result.skipped == 1
            assert result.successful == 0

    def test_replay_rollback_logs_each_reverse_action(self):
        """Test that each reverse action is logged."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "action_log.jsonl"
            logger = ActionLogger(log_path=path)

            # Create multiple actions
            for i in range(3):
                logger.log_action(
                    action_type=ActionType.EMAIL_MOVE,
                    target_id=f"msg_{i}",
                    details={
                        "source_folder": "inbox",
                        "target_folder": f"folder_{i}",
                    },
                    success=True,
                    reversible=True,
                )

            actions_to_rollback = logger.get_rollback_actions()
            result = logger.replay_rollback(actions_to_rollback)

            assert result.total_actions == 3
            # Should have 3 original + 3 rollback records
            all_actions = logger.get_actions()
            assert len(all_actions) == 6

    def test_replay_rollback_email_move_reverses_folders(self):
        """Test that email move rollback swaps source and target folders."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "action_log.jsonl"
            logger = ActionLogger(log_path=path)

            logger.log_action(
                action_type=ActionType.EMAIL_MOVE,
                target_id="msg_1",
                details={
                    "source_folder": "inbox",
                    "target_folder": "Newsletters",
                    "source_folder_id": "id_inbox",
                    "target_folder_id": "id_news",
                },
                success=True,
                reversible=True,
            )

            actions = logger.get_rollback_actions()
            logger.replay_rollback(actions)

            all_actions = logger.get_actions()
            rollback_record = [a for a in all_actions if a.action_type == ActionType.ROLLBACK][0]
            # The rollback details should contain reverse info
            assert rollback_record.details["original_action"] == "email_move"
            assert rollback_record.details["reverse_details"]["source_folder"] == "Newsletters"
            assert rollback_record.details["reverse_details"]["target_folder"] == "inbox"


# =============================================================================
# ActionLogger clear_actions tests
# =============================================================================


class TestActionLoggerClearActions:
    """Test ActionLogger.clear_actions method."""

    def test_clear_removes_file(self):
        """Test that clear_actions removes the log file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "action_log.jsonl"
            logger = ActionLogger(log_path=path)

            logger.log_action(
                action_type=ActionType.FOLDER_CREATE,
                target_id="folder_1",
                success=True,
                reversible=True,
            )
            assert path.exists()

            logger.clear_actions()
            assert not path.exists()

    def test_clear_nonexistent_file_no_error(self):
        """Test that clearing non-existent file doesn't raise."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "action_log.jsonl"
            logger = ActionLogger(log_path=path)
            logger.clear_actions()  # Should not raise

    def test_clear_then_get_returns_empty(self):
        """Test that getting actions after clear returns empty list."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "action_log.jsonl"
            logger = ActionLogger(log_path=path)

            logger.log_action(
                action_type=ActionType.FOLDER_CREATE,
                target_id="folder_1",
                success=True,
                reversible=True,
            )
            logger.clear_actions()

            assert logger.get_actions() == []
            assert logger.get_action_count() == 0


# =============================================================================
# ActionLogger thread safety tests
# =============================================================================


class TestActionLoggerThreadSafety:
    """Test ActionLogger thread-safe append operations."""

    def test_concurrent_writes_no_data_loss(self):
        """Test that concurrent writes don't lose records."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "action_log.jsonl"
            logger = ActionLogger(log_path=path)

            num_threads = 10
            records_per_thread = 20
            errors = []

            def write_records(thread_id: int):
                try:
                    for i in range(records_per_thread):
                        logger.log_action(
                            action_type=ActionType.EMAIL_MOVE,
                            target_id=f"msg_t{thread_id}_{i}",
                            details={"thread": thread_id, "index": i},
                            success=True,
                            reversible=True,
                        )
                except Exception as e:
                    errors.append(str(e))

            threads = [
                threading.Thread(target=write_records, args=(t,)) for t in range(num_threads)
            ]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            assert len(errors) == 0, f"Errors during concurrent write: {errors}"
            actions = logger.get_actions()
            assert len(actions) == num_threads * records_per_thread

    def test_concurrent_writes_valid_json(self):
        """Test that concurrent writes produce valid JSONL (no interleaving)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "action_log.jsonl"
            logger = ActionLogger(log_path=path)

            num_threads = 5
            records_per_thread = 10

            def write_records(thread_id: int):
                for i in range(records_per_thread):
                    logger.log_action(
                        action_type=ActionType.EMAIL_MOVE,
                        target_id=f"msg_t{thread_id}_{i}",
                        success=True,
                        reversible=True,
                    )

            threads = [
                threading.Thread(target=write_records, args=(t,)) for t in range(num_threads)
            ]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            # Every line should be valid JSON
            with open(path, encoding="utf-8") as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        json.loads(line)
                    except json.JSONDecodeError:
                        pytest.fail(f"Invalid JSON on line {line_num}: {line[:100]}")


# =============================================================================
# ActionLogger get_action_log tests
# =============================================================================


class TestActionLoggerGetActionLog:
    """Test ActionLogger.get_action_log method."""

    def test_get_action_log_returns_action_log(self):
        """Test that get_action_log returns an ActionLog model."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "action_log.jsonl"
            logger = ActionLogger(log_path=path)

            logger.log_action(
                action_type=ActionType.FOLDER_CREATE,
                target_id="folder_1",
                success=True,
                reversible=True,
            )
            logger.log_action(
                action_type=ActionType.EMAIL_MOVE,
                target_id="msg_1",
                success=False,
                reversible=False,
            )

            log = logger.get_action_log()
            assert isinstance(log, ActionLog)
            assert log.total_count == 2
            assert log.success_count == 1
            assert log.failure_count == 1


# =============================================================================
# ActionLogger generate_reverse_record tests
# =============================================================================


class TestGenerateReverseRecord:
    """Test the reverse record generation logic."""

    def test_reverse_email_move(self):
        """Test generating reverse record for email move."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "action_log.jsonl"
            logger = ActionLogger(log_path=path)

            original = ActionRecord(
                timestamp=datetime.now(timezone.utc),
                action_type=ActionType.EMAIL_MOVE,
                target_id="msg_1",
                details={
                    "source_folder": "inbox",
                    "target_folder": "News",
                    "source_folder_id": "id_inbox",
                    "target_folder_id": "id_news",
                },
                success=True,
                reversible=True,
            )

            reverse = logger._generate_reverse_record(original)
            assert reverse.action_type == ActionType.ROLLBACK
            assert reverse.target_id == "msg_1"
            assert reverse.details["original_action"] == "email_move"
            assert reverse.details["reverse_details"]["source_folder"] == "News"
            assert reverse.details["reverse_details"]["target_folder"] == "inbox"

    def test_reverse_folder_create(self):
        """Test generating reverse record for folder creation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "action_log.jsonl"
            logger = ActionLogger(log_path=path)

            original = ActionRecord(
                timestamp=datetime.now(timezone.utc),
                action_type=ActionType.FOLDER_CREATE,
                target_id="folder_1",
                details={"folder_name": "Newsletters"},
                success=True,
                reversible=True,
            )

            reverse = logger._generate_reverse_record(original)
            assert reverse.action_type == ActionType.ROLLBACK
            assert reverse.details["original_action"] == "folder_create"
            assert reverse.details["reverse_action"] == "folder_delete"

    def test_reverse_rule_create(self):
        """Test generating reverse record for rule creation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "action_log.jsonl"
            logger = ActionLogger(log_path=path)

            original = ActionRecord(
                timestamp=datetime.now(timezone.utc),
                action_type=ActionType.RULE_CREATE,
                target_id="rule_1",
                details={"rule_name": "Newsletter Filter"},
                success=True,
                reversible=True,
            )

            reverse = logger._generate_reverse_record(original)
            assert reverse.action_type == ActionType.ROLLBACK
            assert reverse.details["original_action"] == "rule_create"
            assert reverse.details["reverse_action"] == "rule_delete"

    def test_reverse_label_add(self):
        """Test generating reverse record for label add."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "action_log.jsonl"
            logger = ActionLogger(log_path=path)

            original = ActionRecord(
                timestamp=datetime.now(timezone.utc),
                action_type=ActionType.LABEL_ADD,
                target_id="msg_1",
                details={"label": "Important"},
                success=True,
                reversible=True,
            )

            reverse = logger._generate_reverse_record(original)
            assert reverse.action_type == ActionType.ROLLBACK
            assert reverse.details["original_action"] == "label_add"
            assert reverse.details["reverse_action"] == "label_remove"

    def test_reverse_label_remove(self):
        """Test generating reverse record for label remove."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "action_log.jsonl"
            logger = ActionLogger(log_path=path)

            original = ActionRecord(
                timestamp=datetime.now(timezone.utc),
                action_type=ActionType.LABEL_REMOVE,
                target_id="msg_1",
                details={"label": "Spam"},
                success=True,
                reversible=True,
            )

            reverse = logger._generate_reverse_record(original)
            assert reverse.action_type == ActionType.ROLLBACK
            assert reverse.details["original_action"] == "label_remove"
            assert reverse.details["reverse_action"] == "label_add"

    def test_reverse_non_reversible_returns_none(self):
        """Test that generating reverse for non-reversible returns None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "action_log.jsonl"
            logger = ActionLogger(log_path=path)

            original = ActionRecord(
                timestamp=datetime.now(timezone.utc),
                action_type=ActionType.FOLDER_DELETE,
                target_id="folder_1",
                details={},
                success=True,
                reversible=False,
            )

            reverse = logger._generate_reverse_record(original)
            assert reverse is None


# =============================================================================
# ActionLogger SQLite backend tests (Phase 4, Work Item 4.1)
# =============================================================================


class TestActionLoggerSQLiteInit:
    """Test ActionLogger initialization with SQLite database."""

    def test_init_with_database_parameter(self, tmp_path):
        """Test that ActionLogger accepts a database parameter."""
        db_path = tmp_path / "test.db"
        db = Database(db_path)
        try:
            log_path = tmp_path / "action_log.jsonl"
            logger = ActionLogger(log_path=log_path, database=db)
            assert logger._database is db
        finally:
            db.close()

    def test_init_without_database_defaults_to_none(self):
        """Test that database defaults to None when not provided."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "action_log.jsonl"
            logger = ActionLogger(log_path=path)
            assert logger._database is None


class TestActionLoggerSQLiteLogAction:
    """Test logging actions to SQLite backend."""

    def test_log_action_writes_to_sqlite(self, tmp_path):
        """Test that log_action writes to SQLite when database is provided."""
        db_path = tmp_path / "test.db"
        db = Database(db_path)
        try:
            log_path = tmp_path / "action_log.jsonl"
            logger = ActionLogger(log_path=log_path, database=db)

            record = logger.log_action(
                action_type=ActionType.FOLDER_CREATE,
                target_id="folder_abc",
                details={"folder_name": "Newsletters"},
                success=True,
                reversible=True,
            )

            # Verify it's in SQLite
            cursor = db.execute("SELECT * FROM action_log WHERE target_id = ?", ("folder_abc",))
            row = cursor.fetchone()
            assert row is not None
            assert record.target_id == "folder_abc"
        finally:
            db.close()

    def test_log_action_does_not_write_jsonl_when_database_provided(self, tmp_path):
        """Test that JSONL file is NOT written when database is provided."""
        db_path = tmp_path / "test.db"
        db = Database(db_path)
        try:
            log_path = tmp_path / "action_log.jsonl"
            logger = ActionLogger(log_path=log_path, database=db)

            logger.log_action(
                action_type=ActionType.FOLDER_CREATE,
                target_id="folder_1",
                success=True,
                reversible=True,
            )

            # JSONL file should not exist or be empty
            assert not log_path.exists()
        finally:
            db.close()

    def test_log_action_sqlite_stores_all_fields(self, tmp_path):
        """Test that all ActionRecord fields are stored in SQLite."""
        db_path = tmp_path / "test.db"
        db = Database(db_path)
        try:
            log_path = tmp_path / "action_log.jsonl"
            logger = ActionLogger(log_path=log_path, database=db)

            logger.log_action(
                action_type=ActionType.EMAIL_MOVE,
                target_id="msg_xyz",
                details={"source_folder": "inbox", "target_folder": "News"},
                success=True,
                reversible=True,
            )

            cursor = db.execute(
                "SELECT timestamp, action_type, target_id, details_json, success, reversible "
                "FROM action_log WHERE target_id = ?",
                ("msg_xyz",),
            )
            row = cursor.fetchone()
            assert row is not None
            timestamp, action_type, target_id, details_json, success, reversible = row
            assert action_type == "email_move"
            assert target_id == "msg_xyz"
            assert json.loads(details_json) == {"source_folder": "inbox", "target_folder": "News"}
            assert success == 1
            assert reversible == 1
        finally:
            db.close()

    def test_log_multiple_actions_to_sqlite(self, tmp_path):
        """Test logging multiple actions to SQLite."""
        db_path = tmp_path / "test.db"
        db = Database(db_path)
        try:
            log_path = tmp_path / "action_log.jsonl"
            logger = ActionLogger(log_path=log_path, database=db)

            for i in range(5):
                logger.log_action(
                    action_type=ActionType.EMAIL_MOVE,
                    target_id=f"msg_{i}",
                    details={"index": i},
                    success=True,
                    reversible=True,
                )

            cursor = db.execute("SELECT COUNT(*) FROM action_log")
            count = cursor.fetchone()[0]
            assert count == 5
        finally:
            db.close()

    def test_log_failed_action_to_sqlite(self, tmp_path):
        """Test logging a failed action to SQLite."""
        db_path = tmp_path / "test.db"
        db = Database(db_path)
        try:
            log_path = tmp_path / "action_log.jsonl"
            logger = ActionLogger(log_path=log_path, database=db)

            logger.log_action(
                action_type=ActionType.EMAIL_MOVE,
                target_id="msg_fail",
                details={"error": "Permission denied"},
                success=False,
                reversible=False,
            )

            cursor = db.execute(
                "SELECT success, reversible FROM action_log WHERE target_id = ?",
                ("msg_fail",),
            )
            row = cursor.fetchone()
            assert row[0] == 0  # success = False
            assert row[1] == 0  # reversible = False
        finally:
            db.close()


class TestActionLoggerSQLiteGetActions:
    """Test retrieving actions from SQLite backend."""

    def test_get_actions_from_sqlite(self, tmp_path):
        """Test that get_actions reads from SQLite when database is provided."""
        db_path = tmp_path / "test.db"
        db = Database(db_path)
        try:
            log_path = tmp_path / "action_log.jsonl"
            logger = ActionLogger(log_path=log_path, database=db)

            logger.log_action(
                action_type=ActionType.FOLDER_CREATE,
                target_id="folder_1",
                details={"folder_name": "News"},
                success=True,
                reversible=True,
            )
            logger.log_action(
                action_type=ActionType.EMAIL_MOVE,
                target_id="msg_1",
                details={"source_folder": "inbox", "target_folder": "News"},
                success=True,
                reversible=True,
            )

            actions = logger.get_actions()
            assert len(actions) == 2
            assert actions[0].action_type == ActionType.FOLDER_CREATE
            assert actions[1].action_type == ActionType.EMAIL_MOVE
        finally:
            db.close()

    def test_get_actions_with_type_filter_from_sqlite(self, tmp_path):
        """Test filtering actions by type from SQLite."""
        db_path = tmp_path / "test.db"
        db = Database(db_path)
        try:
            log_path = tmp_path / "action_log.jsonl"
            logger = ActionLogger(log_path=log_path, database=db)

            logger.log_action(
                action_type=ActionType.FOLDER_CREATE,
                target_id="f_1",
                success=True,
                reversible=True,
            )
            logger.log_action(
                action_type=ActionType.EMAIL_MOVE,
                target_id="m_1",
                success=True,
                reversible=True,
            )
            logger.log_action(
                action_type=ActionType.EMAIL_MOVE,
                target_id="m_2",
                success=True,
                reversible=True,
            )

            move_actions = logger.get_actions(action_type_filter=ActionType.EMAIL_MOVE)
            assert len(move_actions) == 2

            folder_actions = logger.get_actions(action_type_filter=ActionType.FOLDER_CREATE)
            assert len(folder_actions) == 1
        finally:
            db.close()

    def test_get_actions_empty_sqlite(self, tmp_path):
        """Test getting actions from empty SQLite database."""
        db_path = tmp_path / "test.db"
        db = Database(db_path)
        try:
            log_path = tmp_path / "action_log.jsonl"
            logger = ActionLogger(log_path=log_path, database=db)

            actions = logger.get_actions()
            assert actions == []
        finally:
            db.close()

    def test_get_action_count_from_sqlite(self, tmp_path):
        """Test action count from SQLite backend."""
        db_path = tmp_path / "test.db"
        db = Database(db_path)
        try:
            log_path = tmp_path / "action_log.jsonl"
            logger = ActionLogger(log_path=log_path, database=db)

            for i in range(3):
                logger.log_action(
                    action_type=ActionType.EMAIL_MOVE,
                    target_id=f"msg_{i}",
                    success=True,
                    reversible=True,
                )

            assert logger.get_action_count() == 3
            assert logger.get_action_count(action_type_filter=ActionType.EMAIL_MOVE) == 3
            assert logger.get_action_count(action_type_filter=ActionType.FOLDER_CREATE) == 0
        finally:
            db.close()


class TestActionLoggerSQLiteGetActionLog:
    """Test get_action_log with SQLite backend."""

    def test_get_action_log_from_sqlite(self, tmp_path):
        """Test that get_action_log works with SQLite backend."""
        db_path = tmp_path / "test.db"
        db = Database(db_path)
        try:
            log_path = tmp_path / "action_log.jsonl"
            logger = ActionLogger(log_path=log_path, database=db)

            logger.log_action(
                action_type=ActionType.FOLDER_CREATE,
                target_id="folder_1",
                success=True,
                reversible=True,
            )
            logger.log_action(
                action_type=ActionType.EMAIL_MOVE,
                target_id="msg_1",
                success=False,
                reversible=False,
            )

            log = logger.get_action_log()
            assert isinstance(log, ActionLog)
            assert log.total_count == 2
            assert log.success_count == 1
            assert log.failure_count == 1
        finally:
            db.close()


class TestActionLoggerSQLiteRollback:
    """Test rollback operations with SQLite backend."""

    def test_get_rollback_actions_from_sqlite(self, tmp_path):
        """Test get_rollback_actions reads from SQLite."""
        db_path = tmp_path / "test.db"
        db = Database(db_path)
        try:
            log_path = tmp_path / "action_log.jsonl"
            logger = ActionLogger(log_path=log_path, database=db)

            logger.log_action(
                action_type=ActionType.EMAIL_MOVE,
                target_id="msg_1",
                details={"source_folder": "inbox", "target_folder": "News"},
                success=True,
                reversible=True,
            )
            logger.log_action(
                action_type=ActionType.EMAIL_MOVE,
                target_id="msg_2",
                success=False,
                reversible=False,
            )

            rollback = logger.get_rollback_actions()
            assert len(rollback) == 1
            assert rollback[0].target_id == "msg_1"
        finally:
            db.close()

    def test_replay_rollback_writes_to_sqlite(self, tmp_path):
        """Test that replay_rollback writes reverse records to SQLite."""
        db_path = tmp_path / "test.db"
        db = Database(db_path)
        try:
            log_path = tmp_path / "action_log.jsonl"
            logger = ActionLogger(log_path=log_path, database=db)

            logger.log_action(
                action_type=ActionType.EMAIL_MOVE,
                target_id="msg_1",
                details={
                    "source_folder": "inbox",
                    "target_folder": "News",
                    "source_folder_id": "id_inbox",
                    "target_folder_id": "id_news",
                },
                success=True,
                reversible=True,
            )

            actions_to_rollback = logger.get_rollback_actions()
            result = logger.replay_rollback(actions_to_rollback)

            assert result.total_actions == 1
            assert result.successful == 1

            # Verify rollback record is in SQLite
            all_actions = logger.get_actions()
            rollback_records = [a for a in all_actions if a.action_type == ActionType.ROLLBACK]
            assert len(rollback_records) == 1
        finally:
            db.close()

    def test_rollback_excludes_already_rolled_back_sqlite(self, tmp_path):
        """Test that already-rolled-back actions are excluded from SQLite queries."""
        db_path = tmp_path / "test.db"
        db = Database(db_path)
        try:
            log_path = tmp_path / "action_log.jsonl"
            logger = ActionLogger(log_path=log_path, database=db)

            logger.log_action(
                action_type=ActionType.EMAIL_MOVE,
                target_id="msg_1",
                details={"source_folder": "inbox", "target_folder": "News"},
                success=True,
                reversible=True,
            )
            # Record a rollback for msg_1
            logger.log_action(
                action_type=ActionType.ROLLBACK,
                target_id="msg_1",
                details={"original_action": "email_move"},
                success=True,
                reversible=False,
            )
            logger.log_action(
                action_type=ActionType.EMAIL_MOVE,
                target_id="msg_2",
                details={"source_folder": "inbox", "target_folder": "Archive"},
                success=True,
                reversible=True,
            )

            rollback = logger.get_rollback_actions()
            assert len(rollback) == 1
            assert rollback[0].target_id == "msg_2"
        finally:
            db.close()

    def test_get_rollback_actions_since_datetime_sqlite(self, tmp_path):
        """Test filtering rollback actions by datetime from SQLite."""
        db_path = tmp_path / "test.db"
        db = Database(db_path)
        try:
            log_path = tmp_path / "action_log.jsonl"
            logger = ActionLogger(log_path=log_path, database=db)

            # Insert with controlled timestamps directly into SQLite
            old_ts = "2026-01-01T00:00:00+00:00"
            recent_ts = "2026-02-28T00:00:00+00:00"

            db.execute(
                "INSERT INTO action_log "
                "(timestamp, action_type, target_id, details_json, success, reversible) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (old_ts, "email_move", "msg_old", "{}", 1, 1),
            )
            db.execute(
                "INSERT INTO action_log "
                "(timestamp, action_type, target_id, details_json, success, reversible) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (recent_ts, "email_move", "msg_recent", "{}", 1, 1),
            )

            since = datetime(2026, 2, 1, tzinfo=timezone.utc)
            rollback = logger.get_rollback_actions(since=since)
            assert len(rollback) == 1
            assert rollback[0].target_id == "msg_recent"
        finally:
            db.close()


class TestActionLoggerSQLiteClearActions:
    """Test clearing actions with SQLite backend."""

    def test_clear_actions_clears_sqlite(self, tmp_path):
        """Test that clear_actions removes records from SQLite."""
        db_path = tmp_path / "test.db"
        db = Database(db_path)
        try:
            log_path = tmp_path / "action_log.jsonl"
            logger = ActionLogger(log_path=log_path, database=db)

            logger.log_action(
                action_type=ActionType.FOLDER_CREATE,
                target_id="folder_1",
                success=True,
                reversible=True,
            )

            assert logger.get_action_count() == 1

            logger.clear_actions()

            assert logger.get_action_count() == 0
            # Verify table is empty
            cursor = db.execute("SELECT COUNT(*) FROM action_log")
            assert cursor.fetchone()[0] == 0
        finally:
            db.close()

    def test_clear_empty_sqlite_no_error(self, tmp_path):
        """Test that clearing empty SQLite table doesn't raise."""
        db_path = tmp_path / "test.db"
        db = Database(db_path)
        try:
            log_path = tmp_path / "action_log.jsonl"
            logger = ActionLogger(log_path=log_path, database=db)
            logger.clear_actions()  # Should not raise
        finally:
            db.close()


class TestActionLoggerSQLiteThreadSafety:
    """Test thread safety of SQLite backend."""

    def test_concurrent_sqlite_writes(self, tmp_path):
        """Test concurrent writes to SQLite don't lose records."""
        db_path = tmp_path / "test.db"
        db = Database(db_path)
        try:
            log_path = tmp_path / "action_log.jsonl"
            logger = ActionLogger(log_path=log_path, database=db)

            num_threads = 5
            records_per_thread = 10
            errors = []

            def write_records(thread_id: int):
                try:
                    for i in range(records_per_thread):
                        logger.log_action(
                            action_type=ActionType.EMAIL_MOVE,
                            target_id=f"msg_t{thread_id}_{i}",
                            details={"thread": thread_id},
                            success=True,
                            reversible=True,
                        )
                except Exception as e:
                    errors.append(str(e))

            threads = [
                threading.Thread(target=write_records, args=(t,)) for t in range(num_threads)
            ]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            assert len(errors) == 0, f"Errors during concurrent write: {errors}"
            assert logger.get_action_count() == num_threads * records_per_thread
        finally:
            db.close()


class TestActionLoggerJSONLFallbackUnchanged:
    """Test that JSONL behavior is completely unchanged when no database is provided."""

    def test_jsonl_fallback_log_and_retrieve(self):
        """Test original JSONL path still works without database."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "action_log.jsonl"
            logger = ActionLogger(log_path=path)

            logger.log_action(
                action_type=ActionType.FOLDER_CREATE,
                target_id="folder_1",
                details={"folder_name": "News"},
                success=True,
                reversible=True,
            )

            # Verify JSONL file was written
            assert path.exists()
            with open(path, encoding="utf-8") as f:
                data = json.loads(f.readline())
            assert data["target_id"] == "folder_1"

            # Verify get_actions works via JSONL
            actions = logger.get_actions()
            assert len(actions) == 1
            assert actions[0].target_id == "folder_1"
