"""
Unit tests for the feedback learning decision logger module.

Tests the DecisionLogger class for logging review decisions to JSONL format,
supporting pattern detection and learned preferences.

Task 5B.1: Decision Logging
"""
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.learning.decision_logger import (
    DecisionLogger,
    ReviewDecision,
    DecisionAction,
    get_default_decisions_path,
)


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
            }
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
            }
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
            }
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
            context={"key": "value"}
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
            "context": {"old_name": "Old", "new_name": "New"}
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
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("src.learning.decision_logger.get_default_decisions_path") as mock_path:
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
            logger = DecisionLogger(decisions_path=nested_path)
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
            with open(path, "r", encoding="utf-8") as f:
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

            with open(path, "r", encoding="utf-8") as f:
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

            with open(path, "r", encoding="utf-8") as f:
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

            with open(path, "r", encoding="utf-8") as f:
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

            with open(path, "r", encoding="utf-8") as f:
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

            with open(path, "r", encoding="utf-8") as f:
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
                f.write('{"timestamp": "2024-01-15T10:00:00+00:00", "category_name": "Valid", "action": "accept", "context": {}}\n')
                f.write('invalid json line\n')
                f.write('{"timestamp": "2024-01-15T11:00:00+00:00", "category_name": "Also Valid", "action": "delete", "context": {}}\n')

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
