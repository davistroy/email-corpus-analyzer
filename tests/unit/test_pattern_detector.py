"""
Unit tests for the pattern detection module.

Tests the PatternDetector class for identifying recurring patterns
in user review decisions.

Task 5B.2: Pattern Detection
"""
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.learning.decision_logger import DecisionAction, DecisionLogger
from src.learning.pattern_detector import (
    DetectedPattern,
    PatternDetector,
    PatternType,
)


class TestPatternType:
    """Test the PatternType enum."""

    def test_pattern_type_values(self):
        """Test that all required pattern type values exist."""
        assert PatternType.RENAME.value == "rename"
        assert PatternType.MERGE.value == "merge"
        assert PatternType.DELETE_LOW_CONFIDENCE.value == "delete_low_confidence"
        assert PatternType.ALWAYS_ACCEPT.value == "always_accept"


class TestDetectedPattern:
    """Test the DetectedPattern dataclass."""

    def test_create_rename_pattern(self):
        """Test creating a rename pattern."""
        pattern = DetectedPattern(
            pattern_type=PatternType.RENAME,
            parameters={"old_name": "Newsletters", "new_name": "Email Updates"},
            occurrences=5,
            confidence=0.83,
        )
        assert pattern.pattern_type == PatternType.RENAME
        assert pattern.parameters["old_name"] == "Newsletters"
        assert pattern.occurrences == 5
        assert pattern.confidence == 0.83

    def test_create_merge_pattern(self):
        """Test creating a merge pattern."""
        pattern = DetectedPattern(
            pattern_type=PatternType.MERGE,
            parameters={"source": "Amazon Orders", "target": "Shopping"},
            occurrences=3,
            confidence=0.75,
        )
        assert pattern.pattern_type == PatternType.MERGE
        assert pattern.parameters["source"] == "Amazon Orders"
        assert pattern.parameters["target"] == "Shopping"

    def test_create_delete_low_confidence_pattern(self):
        """Test creating a delete low confidence pattern."""
        pattern = DetectedPattern(
            pattern_type=PatternType.DELETE_LOW_CONFIDENCE,
            parameters={"threshold": 0.3},
            occurrences=10,
            confidence=0.9,
        )
        assert pattern.pattern_type == PatternType.DELETE_LOW_CONFIDENCE
        assert pattern.parameters["threshold"] == 0.3

    def test_create_always_accept_pattern(self):
        """Test creating an always accept pattern."""
        pattern = DetectedPattern(
            pattern_type=PatternType.ALWAYS_ACCEPT,
            parameters={"category_name": "Important Emails"},
            occurrences=8,
            confidence=0.95,
        )
        assert pattern.pattern_type == PatternType.ALWAYS_ACCEPT
        assert pattern.parameters["category_name"] == "Important Emails"

    def test_pattern_to_dict(self):
        """Test converting pattern to dictionary."""
        pattern = DetectedPattern(
            pattern_type=PatternType.RENAME,
            parameters={"old_name": "Old", "new_name": "New"},
            occurrences=4,
            confidence=0.8,
        )
        result = pattern.to_dict()

        assert result["pattern_type"] == "rename"
        assert result["parameters"] == {"old_name": "Old", "new_name": "New"}
        assert result["occurrences"] == 4
        assert result["confidence"] == 0.8

    def test_pattern_from_dict(self):
        """Test creating pattern from dictionary."""
        data = {
            "pattern_type": "merge",
            "parameters": {"source": "A", "target": "B"},
            "occurrences": 6,
            "confidence": 0.85,
        }
        pattern = DetectedPattern.from_dict(data)

        assert pattern.pattern_type == PatternType.MERGE
        assert pattern.parameters == {"source": "A", "target": "B"}
        assert pattern.occurrences == 6


class TestPatternDetectorInit:
    """Test PatternDetector initialization."""

    def test_init_with_decision_logger(self):
        """Test initializing with a decision logger."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "decisions.jsonl"
            logger = DecisionLogger(decisions_path=path)
            detector = PatternDetector(decision_logger=logger)

            assert detector.decision_logger == logger

    def test_init_with_custom_threshold(self):
        """Test initializing with custom occurrence threshold."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "decisions.jsonl"
            logger = DecisionLogger(decisions_path=path)
            detector = PatternDetector(decision_logger=logger, min_occurrences=5)

            assert detector.min_occurrences == 5

    def test_default_threshold_is_three(self):
        """Test that default threshold is 3 occurrences."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "decisions.jsonl"
            logger = DecisionLogger(decisions_path=path)
            detector = PatternDetector(decision_logger=logger)

            assert detector.min_occurrences == 3


class TestPatternDetectorRenamePatterns:
    """Test detection of rename patterns."""

    def test_detect_rename_pattern_at_threshold(self):
        """Test detecting rename pattern at exactly 3 occurrences."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "decisions.jsonl"
            logger = DecisionLogger(decisions_path=path)

            # Log 3 identical renames (meets threshold)
            for _ in range(3):
                logger.log_decision(
                    "New Name",
                    DecisionAction.RENAME,
                    old_name="Old Name",
                    new_name="New Name",
                )

            detector = PatternDetector(decision_logger=logger)
            patterns = detector.detect_patterns()

            rename_patterns = [p for p in patterns if p.pattern_type == PatternType.RENAME]
            assert len(rename_patterns) == 1
            assert rename_patterns[0].parameters["old_name"] == "Old Name"
            assert rename_patterns[0].parameters["new_name"] == "New Name"
            assert rename_patterns[0].occurrences == 3

    def test_no_rename_pattern_below_threshold(self):
        """Test no pattern detected below threshold."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "decisions.jsonl"
            logger = DecisionLogger(decisions_path=path)

            # Log only 2 identical renames (below threshold)
            for _ in range(2):
                logger.log_decision(
                    "New Name",
                    DecisionAction.RENAME,
                    old_name="Old Name",
                    new_name="New Name",
                )

            detector = PatternDetector(decision_logger=logger)
            patterns = detector.detect_patterns()

            rename_patterns = [p for p in patterns if p.pattern_type == PatternType.RENAME]
            assert len(rename_patterns) == 0

    def test_multiple_rename_patterns(self):
        """Test detecting multiple different rename patterns."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "decisions.jsonl"
            logger = DecisionLogger(decisions_path=path)

            # Pattern 1: Old1 -> New1 (3 times)
            for _ in range(3):
                logger.log_decision("New1", DecisionAction.RENAME, old_name="Old1", new_name="New1")

            # Pattern 2: Old2 -> New2 (4 times)
            for _ in range(4):
                logger.log_decision("New2", DecisionAction.RENAME, old_name="Old2", new_name="New2")

            detector = PatternDetector(decision_logger=logger)
            patterns = detector.detect_patterns()

            rename_patterns = [p for p in patterns if p.pattern_type == PatternType.RENAME]
            assert len(rename_patterns) == 2

    def test_rename_pattern_confidence_based_on_occurrences(self):
        """Test that confidence increases with more occurrences."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "decisions.jsonl"
            logger = DecisionLogger(decisions_path=path)

            # Log 10 identical renames
            for _ in range(10):
                logger.log_decision("New", DecisionAction.RENAME, old_name="Old", new_name="New")

            detector = PatternDetector(decision_logger=logger)
            patterns = detector.detect_patterns()

            rename_patterns = [p for p in patterns if p.pattern_type == PatternType.RENAME]
            assert len(rename_patterns) == 1
            # Higher occurrences should give higher confidence
            assert rename_patterns[0].confidence > 0.8


class TestPatternDetectorMergePatterns:
    """Test detection of merge patterns."""

    def test_detect_merge_pattern(self):
        """Test detecting merge pattern at threshold."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "decisions.jsonl"
            logger = DecisionLogger(decisions_path=path)

            # Log 3 identical merges
            for _ in range(3):
                logger.log_decision(
                    "Source Category",
                    DecisionAction.MERGE,
                    merge_target="Target Category",
                )

            detector = PatternDetector(decision_logger=logger)
            patterns = detector.detect_patterns()

            merge_patterns = [p for p in patterns if p.pattern_type == PatternType.MERGE]
            assert len(merge_patterns) == 1
            assert merge_patterns[0].parameters["source"] == "Source Category"
            assert merge_patterns[0].parameters["target"] == "Target Category"

    def test_no_merge_pattern_below_threshold(self):
        """Test no merge pattern below threshold."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "decisions.jsonl"
            logger = DecisionLogger(decisions_path=path)

            # Log only 2 merges
            for _ in range(2):
                logger.log_decision("Source", DecisionAction.MERGE, merge_target="Target")

            detector = PatternDetector(decision_logger=logger)
            patterns = detector.detect_patterns()

            merge_patterns = [p for p in patterns if p.pattern_type == PatternType.MERGE]
            assert len(merge_patterns) == 0


class TestPatternDetectorDeletePatterns:
    """Test detection of delete low confidence patterns."""

    def test_detect_delete_low_confidence_pattern(self):
        """Test detecting pattern of deleting low confidence categories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "decisions.jsonl"
            logger = DecisionLogger(decisions_path=path)

            # Log 3 deletes of low-confidence categories
            for i in range(3):
                logger.log_decision(
                    f"Low Quality {i}",
                    DecisionAction.DELETE,
                    confidence=0.25,
                )

            detector = PatternDetector(decision_logger=logger)
            patterns = detector.detect_patterns()

            delete_patterns = [p for p in patterns if p.pattern_type == PatternType.DELETE_LOW_CONFIDENCE]
            assert len(delete_patterns) == 1
            # Should detect the threshold around 0.25-0.3
            assert delete_patterns[0].parameters["threshold"] <= 0.4

    def test_no_delete_pattern_for_high_confidence(self):
        """Test no delete pattern when deleting high confidence categories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "decisions.jsonl"
            logger = DecisionLogger(decisions_path=path)

            # Log deletes of high-confidence categories
            for i in range(3):
                logger.log_decision(
                    f"Category {i}",
                    DecisionAction.DELETE,
                    confidence=0.85,
                )

            detector = PatternDetector(decision_logger=logger)
            patterns = detector.detect_patterns()

            # Should not detect a "delete low confidence" pattern
            delete_patterns = [p for p in patterns if p.pattern_type == PatternType.DELETE_LOW_CONFIDENCE]
            assert len(delete_patterns) == 0


class TestPatternDetectorAlwaysAcceptPatterns:
    """Test detection of always accept patterns."""

    def test_detect_always_accept_pattern(self):
        """Test detecting pattern of always accepting certain names."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "decisions.jsonl"
            logger = DecisionLogger(decisions_path=path)

            # Log 3 accepts for same category name
            for _ in range(3):
                logger.log_decision("Newsletters", DecisionAction.ACCEPT)

            detector = PatternDetector(decision_logger=logger)
            patterns = detector.detect_patterns()

            accept_patterns = [p for p in patterns if p.pattern_type == PatternType.ALWAYS_ACCEPT]
            assert len(accept_patterns) == 1
            assert accept_patterns[0].parameters["category_name"] == "Newsletters"

    def test_multiple_always_accept_patterns(self):
        """Test detecting multiple always accept patterns."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "decisions.jsonl"
            logger = DecisionLogger(decisions_path=path)

            # Log accepts for two different names
            for _ in range(3):
                logger.log_decision("Newsletters", DecisionAction.ACCEPT)
            for _ in range(4):
                logger.log_decision("Important", DecisionAction.ACCEPT)

            detector = PatternDetector(decision_logger=logger)
            patterns = detector.detect_patterns()

            accept_patterns = [p for p in patterns if p.pattern_type == PatternType.ALWAYS_ACCEPT]
            assert len(accept_patterns) == 2


class TestPatternDetectorMixedPatterns:
    """Test detection of mixed patterns."""

    def test_detect_all_pattern_types(self):
        """Test detecting all pattern types simultaneously."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "decisions.jsonl"
            logger = DecisionLogger(decisions_path=path)

            # Rename pattern
            for _ in range(3):
                logger.log_decision("New", DecisionAction.RENAME, old_name="Old", new_name="New")

            # Merge pattern
            for _ in range(3):
                logger.log_decision("Source", DecisionAction.MERGE, merge_target="Target")

            # Delete low confidence pattern
            for _ in range(3):
                logger.log_decision("Low", DecisionAction.DELETE, confidence=0.2)

            # Always accept pattern
            for _ in range(3):
                logger.log_decision("Accepted", DecisionAction.ACCEPT)

            detector = PatternDetector(decision_logger=logger)
            patterns = detector.detect_patterns()

            # Should have at least one of each type
            pattern_types = {p.pattern_type for p in patterns}
            assert PatternType.RENAME in pattern_types
            assert PatternType.MERGE in pattern_types
            assert PatternType.DELETE_LOW_CONFIDENCE in pattern_types
            assert PatternType.ALWAYS_ACCEPT in pattern_types

    def test_patterns_sorted_by_confidence(self):
        """Test that patterns are sorted by confidence (highest first)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "decisions.jsonl"
            logger = DecisionLogger(decisions_path=path)

            # Create patterns with different occurrence counts
            for _ in range(10):  # High confidence
                logger.log_decision("Frequent", DecisionAction.ACCEPT)
            for _ in range(3):  # Lower confidence
                logger.log_decision("Less Frequent", DecisionAction.ACCEPT)

            detector = PatternDetector(decision_logger=logger)
            patterns = detector.detect_patterns()

            # Should be sorted by confidence descending
            for i in range(len(patterns) - 1):
                assert patterns[i].confidence >= patterns[i + 1].confidence


class TestPatternDetectorEmptyDecisions:
    """Test pattern detection with no decisions."""

    def test_no_patterns_with_no_decisions(self):
        """Test that no patterns are detected with no decisions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "decisions.jsonl"
            logger = DecisionLogger(decisions_path=path)

            detector = PatternDetector(decision_logger=logger)
            patterns = detector.detect_patterns()

            assert patterns == []

    def test_no_patterns_with_too_few_decisions(self):
        """Test that no patterns are detected with too few decisions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "decisions.jsonl"
            logger = DecisionLogger(decisions_path=path)

            # Log 2 of each action (below threshold)
            logger.log_decision("A", DecisionAction.ACCEPT)
            logger.log_decision("A", DecisionAction.ACCEPT)
            logger.log_decision("B", DecisionAction.RENAME, old_name="X", new_name="B")
            logger.log_decision("B", DecisionAction.RENAME, old_name="X", new_name="B")

            detector = PatternDetector(decision_logger=logger)
            patterns = detector.detect_patterns()

            assert patterns == []


class TestPatternDetectorHighConfidencePatterns:
    """Test getting only high confidence patterns."""

    def test_get_high_confidence_patterns(self):
        """Test filtering patterns by minimum confidence."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "decisions.jsonl"
            logger = DecisionLogger(decisions_path=path)

            # Pattern with many occurrences (high confidence)
            for _ in range(15):
                logger.log_decision("Frequent", DecisionAction.ACCEPT)

            # Pattern with few occurrences (lower confidence)
            for _ in range(3):
                logger.log_decision("Infrequent", DecisionAction.ACCEPT)

            detector = PatternDetector(decision_logger=logger)
            high_confidence = detector.get_high_confidence_patterns(min_confidence=0.8)

            # Should only get the high confidence pattern
            assert len(high_confidence) >= 1
            assert all(p.confidence >= 0.8 for p in high_confidence)

    def test_get_high_confidence_patterns_empty(self):
        """Test getting high confidence patterns when none exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "decisions.jsonl"
            logger = DecisionLogger(decisions_path=path)

            # Only patterns with low confidence
            for _ in range(3):
                logger.log_decision("Low", DecisionAction.ACCEPT)

            detector = PatternDetector(decision_logger=logger)
            high_confidence = detector.get_high_confidence_patterns(min_confidence=0.95)

            # Should be empty or very few
            assert all(p.confidence >= 0.95 for p in high_confidence)


class TestPatternDetectorCustomThreshold:
    """Test pattern detection with custom occurrence threshold."""

    def test_custom_threshold_higher(self):
        """Test with higher custom threshold."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "decisions.jsonl"
            logger = DecisionLogger(decisions_path=path)

            # Log 4 occurrences
            for _ in range(4):
                logger.log_decision("Category", DecisionAction.ACCEPT)

            # Default threshold (3) should detect
            detector_default = PatternDetector(decision_logger=logger, min_occurrences=3)
            patterns_default = detector_default.detect_patterns()

            # Higher threshold (5) should not detect
            detector_high = PatternDetector(decision_logger=logger, min_occurrences=5)
            patterns_high = detector_high.detect_patterns()

            assert len(patterns_default) > len(patterns_high)

    def test_custom_threshold_lower(self):
        """Test with lower custom threshold."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "decisions.jsonl"
            logger = DecisionLogger(decisions_path=path)

            # Log 2 occurrences
            for _ in range(2):
                logger.log_decision("Category", DecisionAction.ACCEPT)

            # Default threshold (3) should NOT detect
            detector_default = PatternDetector(decision_logger=logger, min_occurrences=3)
            patterns_default = detector_default.detect_patterns()

            # Lower threshold (2) SHOULD detect
            detector_low = PatternDetector(decision_logger=logger, min_occurrences=2)
            patterns_low = detector_low.detect_patterns()

            assert len(patterns_low) > len(patterns_default)
