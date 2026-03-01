"""
Unit tests for the feedback learning decision logger module.

Tests the DecisionLogger class for logging review decisions to JSONL format,
supporting pattern detection and learned preferences. Also tests the
SQLite backend path (Phase 4, Work Item 4.1).

Task 5B.1: Decision Logging
Phase 4, Item 4.1: SQLite migration
"""

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from src.learning.decision_logger import (
    DecisionAction,
    DecisionLogger,
    ReviewDecision,
    get_default_decisions_path,
)
from src.storage.database import Database


class TestDecisionAction:
    """Test the DecisionAction enum."""

    def test_action_values(self):
        """Test that all required action values exist."""
        assert DecisionAction.ACCEPT.value == "accept"
        assert DecisionAction.RENAME.value == "rename"
        assert DecisionAction.MERGE.value == "merge"
        assert DecisionAction.DELETE.value == "delete"
        assert DecisionAction.SKIP.value == "skip"

    def test_action_from_string(self):
        """Test converting string to action."""
        assert DecisionAction("accept") == DecisionAction.ACCEPT
        assert DecisionAction("rename") == DecisionAction.RENAME
        assert DecisionAction("merge") == DecisionAction.MERGE
        assert DecisionAction("delete") == DecisionAction.DELETE
        assert DecisionAction("skip") == DecisionAction.SKIP


class TestReviewDecision:
    """Test the ReviewDecision dataclass."""

    def test_create_accept_decision(self):
        """Test creating an accept decision."""
        decision = ReviewDecision(
            timestamp=datetime.now(timezone.utc),
            category_name="Newsletters",
            action=DecisionAction.ACCEPT,
        )
        assert decision.category_name == "Newsletters"
        assert decision.action == DecisionAction.ACCEPT
        assert decision.context == {}

    def test_create_rename_decision_with_context(self):
        """Test creating a rename decision with old/new names."""
        decision = ReviewDecision(
            timestamp=datetime.now(timezone.utc),
            category_name="New Name",
            action=DecisionAction.RENAME,
            context={
                "old_name": "Old Name",
                "new_name": "New Name",
            },
        )
        assert decision.action == DecisionAction.RENAME
        assert decision.context["old_name"] == "Old Name"
        assert decision.context["new_name"] == "New Name"

    def test_create_merge_decision_with_context(self):
        """Test creating a merge decision with merge target."""
        decision = ReviewDecision(
            timestamp=datetime.now(timezone.utc),
            category_name="Source Category",
            action=DecisionAction.MERGE,
            context={
                "merge_target": "Target Category",
            },
        )
        assert decision.action == DecisionAction.MERGE
        assert decision.context["merge_target"] == "Target Category"

    def test_create_delete_decision_with_context(self):
        """Test creating a delete decision with confidence."""
        decision = ReviewDecision(
            timestamp=datetime.now(timezone.utc),
            category_name="Low Quality",
            action=DecisionAction.DELETE,
            context={
                "confidence": 0.3,
                "reason": "low_confidence",
            },
        )
        assert decision.action == DecisionAction.DELETE
        assert decision.context["confidence"] == 0.3

    def test_to_dict(self):
        """Test converting decision to dictionary."""
        ts = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        decision = ReviewDecision(
            timestamp=ts,
            category_name="Test Category",
            action=DecisionAction.ACCEPT,
            context={"key": "value"},
        )
        result = decision.to_dict()

        assert result["timestamp"] == "2024-01-15T10:30:00+00:00"
        assert result["category_name"] == "Test Category"
        assert result["action"] == "accept"
        assert result["context"] == {"key": "value"}

    def test_from_dict(self):
        """Test creating decision from dictionary."""
        data = {
            "timestamp": "2024-01-15T10:30:00+00:00",
            "category_name": "Test Category",
            "action": "rename",
            "context": {"old_name": "Old", "new_name": "New"},
        }
        decision = ReviewDecision.from_dict(data)

        assert decision.category_name == "Test Category"
        assert decision.action == DecisionAction.RENAME
        assert decision.context["old_name"] == "Old"


class TestDefaultDecisionsPath:
    """Test the default decisions path function."""

    def test_default_path_is_in_user_home(self):
        """Test that default path is in user's home directory."""
        path = get_default_decisions_path()
        assert path.parent.name == ".email-analyzer"
        assert path.name == "decisions.jsonl"
        assert str(Path.home()) in str(path)


class TestDecisionLoggerInit:
    """Test DecisionLogger initialization."""

    def test_init_with_default_path(self):
        """Test initializing with default path."""
        with (
            tempfile.TemporaryDirectory() as tmpdir,
            patch("src.learning.decision_logger.get_default_decisions_path") as mock_path,
        ):
            mock_path.return_value = Path(tmpdir) / "decisions.jsonl"
            logger = DecisionLogger()
            assert logger.decisions_path.name == "decisions.jsonl"

    def test_init_with_custom_path(self):
        """Test initializing with custom path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            custom_path = Path(tmpdir) / "custom_decisions.jsonl"
            logger = DecisionLogger(decisions_path=custom_path)
            assert logger.decisions_path == custom_path

    def test_init_creates_parent_directory(self):
        """Test that parent directory is created if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            nested_path = Path(tmpdir) / "nested" / "dir" / "decisions.jsonl"
            DecisionLogger(decisions_path=nested_path)
            assert nested_path.parent.exists()


class TestDecisionLoggerLogDecision:
    """Test logging decisions to file."""

    def test_log_accept_decision(self):
        """Test logging an accept decision."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "decisions.jsonl"
            logger = DecisionLogger(decisions_path=path)

            logger.log_decision(
                category_name="Newsletters",
                action=DecisionAction.ACCEPT,
            )

            # Read the file and verify
            with open(path, encoding="utf-8") as f:
                line = f.readline()
                data = json.loads(line)

            assert data["category_name"] == "Newsletters"
            assert data["action"] == "accept"
            assert "timestamp" in data

    def test_log_rename_decision(self):
        """Test logging a rename decision with context."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "decisions.jsonl"
            logger = DecisionLogger(decisions_path=path)

            logger.log_decision(
                category_name="New Category Name",
                action=DecisionAction.RENAME,
                old_name="Old Category Name",
                new_name="New Category Name",
            )

            with open(path, encoding="utf-8") as f:
                data = json.loads(f.readline())

            assert data["action"] == "rename"
            assert data["context"]["old_name"] == "Old Category Name"
            assert data["context"]["new_name"] == "New Category Name"

    def test_log_merge_decision(self):
        """Test logging a merge decision with target."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "decisions.jsonl"
            logger = DecisionLogger(decisions_path=path)

            logger.log_decision(
                category_name="Source",
                action=DecisionAction.MERGE,
                merge_target="Target",
            )

            with open(path, encoding="utf-8") as f:
                data = json.loads(f.readline())

            assert data["action"] == "merge"
            assert data["context"]["merge_target"] == "Target"

    def test_log_delete_decision(self):
        """Test logging a delete decision with confidence."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "decisions.jsonl"
            logger = DecisionLogger(decisions_path=path)

            logger.log_decision(
                category_name="Low Quality Category",
                action=DecisionAction.DELETE,
                confidence=0.25,
            )

            with open(path, encoding="utf-8") as f:
                data = json.loads(f.readline())

            assert data["action"] == "delete"
            assert data["context"]["confidence"] == 0.25

    def test_log_multiple_decisions(self):
        """Test logging multiple decisions appends to file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "decisions.jsonl"
            logger = DecisionLogger(decisions_path=path)

            logger.log_decision("Cat1", DecisionAction.ACCEPT)
            logger.log_decision("Cat2", DecisionAction.DELETE)
            logger.log_decision("Cat3", DecisionAction.RENAME, old_name="Old", new_name="Cat3")

            with open(path, encoding="utf-8") as f:
                lines = f.readlines()

            assert len(lines) == 3
            assert json.loads(lines[0])["category_name"] == "Cat1"
            assert json.loads(lines[1])["category_name"] == "Cat2"
            assert json.loads(lines[2])["category_name"] == "Cat3"

    def test_log_decision_with_custom_context(self):
        """Test logging decision with arbitrary context."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "decisions.jsonl"
            logger = DecisionLogger(decisions_path=path)

            logger.log_decision(
                category_name="Test",
                action=DecisionAction.SKIP,
                custom_key="custom_value",
                another_key=123,
            )

            with open(path, encoding="utf-8") as f:
                data = json.loads(f.readline())

            assert data["context"]["custom_key"] == "custom_value"
            assert data["context"]["another_key"] == 123


class TestDecisionLoggerGetDecisions:
    """Test retrieving logged decisions."""

    def test_get_decisions_empty_file(self):
        """Test getting decisions from empty/nonexistent file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "decisions.jsonl"
            logger = DecisionLogger(decisions_path=path)

            decisions = logger.get_decisions()

            assert decisions == []

    def test_get_decisions_returns_all(self):
        """Test getting all logged decisions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "decisions.jsonl"
            logger = DecisionLogger(decisions_path=path)

            logger.log_decision("Cat1", DecisionAction.ACCEPT)
            logger.log_decision("Cat2", DecisionAction.DELETE)
            logger.log_decision("Cat3", DecisionAction.RENAME, old_name="Old", new_name="Cat3")

            decisions = logger.get_decisions()

            assert len(decisions) == 3
            assert decisions[0].category_name == "Cat1"
            assert decisions[1].category_name == "Cat2"
            assert decisions[2].category_name == "Cat3"

    def test_get_decisions_by_action(self):
        """Test filtering decisions by action type."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "decisions.jsonl"
            logger = DecisionLogger(decisions_path=path)

            logger.log_decision("Cat1", DecisionAction.ACCEPT)
            logger.log_decision("Cat2", DecisionAction.DELETE)
            logger.log_decision("Cat3", DecisionAction.ACCEPT)
            logger.log_decision("Cat4", DecisionAction.DELETE)

            accept_decisions = logger.get_decisions(action_filter=DecisionAction.ACCEPT)
            delete_decisions = logger.get_decisions(action_filter=DecisionAction.DELETE)

            assert len(accept_decisions) == 2
            assert len(delete_decisions) == 2
            assert all(d.action == DecisionAction.ACCEPT for d in accept_decisions)
            assert all(d.action == DecisionAction.DELETE for d in delete_decisions)

    def test_get_decisions_handles_corrupt_lines(self):
        """Test that corrupt lines are skipped gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "decisions.jsonl"

            # Write some valid and invalid lines
            with open(path, "w", encoding="utf-8") as f:
                f.write(
                    '{"timestamp": "2024-01-15T10:00:00+00:00", "category_name": "Valid", "action": "accept", "context": {}}\n'
                )
                f.write("invalid json line\n")
                f.write(
                    '{"timestamp": "2024-01-15T11:00:00+00:00", "category_name": "Also Valid", "action": "delete", "context": {}}\n'
                )

            logger = DecisionLogger(decisions_path=path)
            decisions = logger.get_decisions()

            # Should only return the 2 valid decisions
            assert len(decisions) == 2
            assert decisions[0].category_name == "Valid"
            assert decisions[1].category_name == "Also Valid"


class TestDecisionLoggerClearDecisions:
    """Test clearing logged decisions."""

    def test_clear_decisions_removes_file(self):
        """Test that clear_decisions removes the decisions file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "decisions.jsonl"
            logger = DecisionLogger(decisions_path=path)

            # Log some decisions
            logger.log_decision("Cat1", DecisionAction.ACCEPT)
            logger.log_decision("Cat2", DecisionAction.DELETE)

            assert path.exists()

            # Clear decisions
            logger.clear_decisions()

            assert not path.exists()

    def test_clear_decisions_on_nonexistent_file(self):
        """Test that clear_decisions handles nonexistent file gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "decisions.jsonl"
            logger = DecisionLogger(decisions_path=path)

            # Should not raise an error
            logger.clear_decisions()

            assert not path.exists()

    def test_get_decisions_after_clear(self):
        """Test that get_decisions returns empty after clear."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "decisions.jsonl"
            logger = DecisionLogger(decisions_path=path)

            logger.log_decision("Cat1", DecisionAction.ACCEPT)
            logger.clear_decisions()
            decisions = logger.get_decisions()

            assert decisions == []


class TestDecisionLoggerPersistence:
    """Test that decisions persist across logger instances."""

    def test_decisions_persist_across_instances(self):
        """Test that decisions logged by one instance are visible to another."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "decisions.jsonl"

            # First instance logs decisions
            logger1 = DecisionLogger(decisions_path=path)
            logger1.log_decision("Cat1", DecisionAction.ACCEPT)
            logger1.log_decision("Cat2", DecisionAction.DELETE)

            # Second instance reads decisions
            logger2 = DecisionLogger(decisions_path=path)
            decisions = logger2.get_decisions()

            assert len(decisions) == 2
            assert decisions[0].category_name == "Cat1"
            assert decisions[1].category_name == "Cat2"

    def test_decisions_append_across_instances(self):
        """Test that new decisions append to existing ones."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "decisions.jsonl"

            # First instance logs
            logger1 = DecisionLogger(decisions_path=path)
            logger1.log_decision("Cat1", DecisionAction.ACCEPT)

            # Second instance appends
            logger2 = DecisionLogger(decisions_path=path)
            logger2.log_decision("Cat2", DecisionAction.DELETE)

            # Third instance reads all
            logger3 = DecisionLogger(decisions_path=path)
            decisions = logger3.get_decisions()

            assert len(decisions) == 2


class TestDecisionLoggerDecisionCount:
    """Test decision counting functionality."""

    def test_get_decision_count_empty(self):
        """Test count is 0 for empty file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "decisions.jsonl"
            logger = DecisionLogger(decisions_path=path)

            assert logger.get_decision_count() == 0

    def test_get_decision_count(self):
        """Test count reflects logged decisions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "decisions.jsonl"
            logger = DecisionLogger(decisions_path=path)

            logger.log_decision("Cat1", DecisionAction.ACCEPT)
            logger.log_decision("Cat2", DecisionAction.DELETE)
            logger.log_decision("Cat3", DecisionAction.RENAME, old_name="Old", new_name="Cat3")

            assert logger.get_decision_count() == 3

    def test_get_decision_count_by_action(self):
        """Test counting decisions by action type."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "decisions.jsonl"
            logger = DecisionLogger(decisions_path=path)

            logger.log_decision("Cat1", DecisionAction.ACCEPT)
            logger.log_decision("Cat2", DecisionAction.ACCEPT)
            logger.log_decision("Cat3", DecisionAction.DELETE)
            logger.log_decision("Cat4", DecisionAction.RENAME, old_name="Old", new_name="Cat4")

            assert logger.get_decision_count(action_filter=DecisionAction.ACCEPT) == 2
            assert logger.get_decision_count(action_filter=DecisionAction.DELETE) == 1
            assert logger.get_decision_count(action_filter=DecisionAction.RENAME) == 1


# =============================================================================
# DecisionLogger SQLite backend tests (Phase 4, Work Item 4.1)
# =============================================================================


class TestDecisionLoggerSQLiteInit:
    """Test DecisionLogger initialization with SQLite database."""

    def test_init_with_database_parameter(self, tmp_path):
        """Test that DecisionLogger accepts a database parameter."""
        db_path = tmp_path / "test.db"
        db = Database(db_path)
        try:
            decisions_path = tmp_path / "decisions.jsonl"
            logger = DecisionLogger(decisions_path=decisions_path, database=db)
            assert logger._database is db
        finally:
            db.close()

    def test_init_without_database_defaults_to_none(self):
        """Test that database defaults to None when not provided."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "decisions.jsonl"
            logger = DecisionLogger(decisions_path=path)
            assert logger._database is None


class TestDecisionLoggerSQLiteLogDecision:
    """Test logging decisions to SQLite backend."""

    def test_log_decision_writes_to_sqlite(self, tmp_path):
        """Test that log_decision writes to SQLite when database is provided."""
        db_path = tmp_path / "test.db"
        db = Database(db_path)
        try:
            decisions_path = tmp_path / "decisions.jsonl"
            logger = DecisionLogger(decisions_path=decisions_path, database=db)

            decision = logger.log_decision(
                category_name="Newsletters",
                action=DecisionAction.ACCEPT,
            )

            # Verify it's in SQLite
            cursor = db.execute(
                "SELECT * FROM decision_log WHERE category_name = ?",
                ("Newsletters",),
            )
            row = cursor.fetchone()
            assert row is not None
            assert decision.category_name == "Newsletters"
        finally:
            db.close()

    def test_log_decision_does_not_write_jsonl_when_database_provided(self, tmp_path):
        """Test that JSONL file is NOT written when database is provided."""
        db_path = tmp_path / "test.db"
        db = Database(db_path)
        try:
            decisions_path = tmp_path / "decisions.jsonl"
            logger = DecisionLogger(decisions_path=decisions_path, database=db)

            logger.log_decision("Test", DecisionAction.ACCEPT)

            # JSONL file should not exist
            assert not decisions_path.exists()
        finally:
            db.close()

    def test_log_decision_sqlite_stores_all_fields(self, tmp_path):
        """Test that all ReviewDecision fields are stored in SQLite."""
        db_path = tmp_path / "test.db"
        db = Database(db_path)
        try:
            decisions_path = tmp_path / "decisions.jsonl"
            logger = DecisionLogger(decisions_path=decisions_path, database=db)

            logger.log_decision(
                category_name="Old Name",
                action=DecisionAction.RENAME,
                old_name="Old Name",
                new_name="New Name",
            )

            cursor = db.execute(
                "SELECT timestamp, category_name, action, context_json "
                "FROM decision_log WHERE category_name = ?",
                ("Old Name",),
            )
            row = cursor.fetchone()
            assert row is not None
            timestamp, category_name, action, context_json = row
            assert category_name == "Old Name"
            assert action == "rename"
            context = json.loads(context_json)
            assert context["old_name"] == "Old Name"
            assert context["new_name"] == "New Name"
        finally:
            db.close()

    def test_log_multiple_decisions_to_sqlite(self, tmp_path):
        """Test logging multiple decisions to SQLite."""
        db_path = tmp_path / "test.db"
        db = Database(db_path)
        try:
            decisions_path = tmp_path / "decisions.jsonl"
            logger = DecisionLogger(decisions_path=decisions_path, database=db)

            logger.log_decision("Cat1", DecisionAction.ACCEPT)
            logger.log_decision("Cat2", DecisionAction.DELETE)
            logger.log_decision("Cat3", DecisionAction.RENAME, old_name="Old", new_name="Cat3")

            cursor = db.execute("SELECT COUNT(*) FROM decision_log")
            count = cursor.fetchone()[0]
            assert count == 3
        finally:
            db.close()


class TestDecisionLoggerSQLiteGetDecisions:
    """Test retrieving decisions from SQLite backend."""

    def test_get_decisions_from_sqlite(self, tmp_path):
        """Test that get_decisions reads from SQLite when database is provided."""
        db_path = tmp_path / "test.db"
        db = Database(db_path)
        try:
            decisions_path = tmp_path / "decisions.jsonl"
            logger = DecisionLogger(decisions_path=decisions_path, database=db)

            logger.log_decision("Cat1", DecisionAction.ACCEPT)
            logger.log_decision("Cat2", DecisionAction.DELETE)

            decisions = logger.get_decisions()
            assert len(decisions) == 2
            assert decisions[0].category_name == "Cat1"
            assert decisions[0].action == DecisionAction.ACCEPT
            assert decisions[1].category_name == "Cat2"
            assert decisions[1].action == DecisionAction.DELETE
        finally:
            db.close()

    def test_get_decisions_with_action_filter_from_sqlite(self, tmp_path):
        """Test filtering decisions by action type from SQLite."""
        db_path = tmp_path / "test.db"
        db = Database(db_path)
        try:
            decisions_path = tmp_path / "decisions.jsonl"
            logger = DecisionLogger(decisions_path=decisions_path, database=db)

            logger.log_decision("Cat1", DecisionAction.ACCEPT)
            logger.log_decision("Cat2", DecisionAction.DELETE)
            logger.log_decision("Cat3", DecisionAction.ACCEPT)

            accept_decisions = logger.get_decisions(action_filter=DecisionAction.ACCEPT)
            delete_decisions = logger.get_decisions(action_filter=DecisionAction.DELETE)

            assert len(accept_decisions) == 2
            assert len(delete_decisions) == 1
        finally:
            db.close()

    def test_get_decisions_empty_sqlite(self, tmp_path):
        """Test getting decisions from empty SQLite database."""
        db_path = tmp_path / "test.db"
        db = Database(db_path)
        try:
            decisions_path = tmp_path / "decisions.jsonl"
            logger = DecisionLogger(decisions_path=decisions_path, database=db)

            decisions = logger.get_decisions()
            assert decisions == []
        finally:
            db.close()

    def test_get_decision_count_from_sqlite(self, tmp_path):
        """Test decision count from SQLite backend."""
        db_path = tmp_path / "test.db"
        db = Database(db_path)
        try:
            decisions_path = tmp_path / "decisions.jsonl"
            logger = DecisionLogger(decisions_path=decisions_path, database=db)

            logger.log_decision("Cat1", DecisionAction.ACCEPT)
            logger.log_decision("Cat2", DecisionAction.ACCEPT)
            logger.log_decision("Cat3", DecisionAction.DELETE)

            assert logger.get_decision_count() == 3
            assert logger.get_decision_count(action_filter=DecisionAction.ACCEPT) == 2
            assert logger.get_decision_count(action_filter=DecisionAction.DELETE) == 1
        finally:
            db.close()


class TestDecisionLoggerSQLiteClearDecisions:
    """Test clearing decisions with SQLite backend."""

    def test_clear_decisions_clears_sqlite(self, tmp_path):
        """Test that clear_decisions removes records from SQLite."""
        db_path = tmp_path / "test.db"
        db = Database(db_path)
        try:
            decisions_path = tmp_path / "decisions.jsonl"
            logger = DecisionLogger(decisions_path=decisions_path, database=db)

            logger.log_decision("Cat1", DecisionAction.ACCEPT)
            assert logger.get_decision_count() == 1

            logger.clear_decisions()

            assert logger.get_decision_count() == 0
            cursor = db.execute("SELECT COUNT(*) FROM decision_log")
            assert cursor.fetchone()[0] == 0
        finally:
            db.close()

    def test_clear_empty_sqlite_no_error(self, tmp_path):
        """Test that clearing empty SQLite table doesn't raise."""
        db_path = tmp_path / "test.db"
        db = Database(db_path)
        try:
            decisions_path = tmp_path / "decisions.jsonl"
            logger = DecisionLogger(decisions_path=decisions_path, database=db)
            logger.clear_decisions()  # Should not raise
        finally:
            db.close()


class TestDecisionLoggerSQLiteContextPreserved:
    """Test that context data round-trips correctly through SQLite."""

    def test_context_round_trip(self, tmp_path):
        """Test that context dict survives SQLite serialization."""
        db_path = tmp_path / "test.db"
        db = Database(db_path)
        try:
            decisions_path = tmp_path / "decisions.jsonl"
            logger = DecisionLogger(decisions_path=decisions_path, database=db)

            logger.log_decision(
                "Test",
                DecisionAction.MERGE,
                merge_target="Target",
                confidence=0.95,
                custom_list=[1, 2, 3],
            )

            decisions = logger.get_decisions()
            assert len(decisions) == 1
            assert decisions[0].context["merge_target"] == "Target"
            assert decisions[0].context["confidence"] == 0.95
            assert decisions[0].context["custom_list"] == [1, 2, 3]
        finally:
            db.close()


class TestDecisionLoggerJSONLFallbackUnchanged:
    """Test that JSONL behavior is completely unchanged when no database is provided."""

    def test_jsonl_fallback_log_and_retrieve(self):
        """Test original JSONL path still works without database."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "decisions.jsonl"
            logger = DecisionLogger(decisions_path=path)

            logger.log_decision("Cat1", DecisionAction.ACCEPT)

            # Verify JSONL file was written
            assert path.exists()
            with open(path, encoding="utf-8") as f:
                data = json.loads(f.readline())
            assert data["category_name"] == "Cat1"

            # Verify get_decisions works via JSONL
            decisions = logger.get_decisions()
            assert len(decisions) == 1
            assert decisions[0].category_name == "Cat1"
