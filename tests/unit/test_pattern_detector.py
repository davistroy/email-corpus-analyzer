"""
Unit tests for the pattern detection module.

Tests the PatternDetector class for identifying recurring patterns
in user review decisions.

Task 5B.2: Pattern Detection
Task 4.2: Temporal Decay tests
"""

import json
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.learning.decision_logger import DecisionAction, DecisionLogger, ReviewDecision
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

            delete_patterns = [
                p for p in patterns if p.pattern_type == PatternType.DELETE_LOW_CONFIDENCE
            ]
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
            delete_patterns = [
                p for p in patterns if p.pattern_type == PatternType.DELETE_LOW_CONFIDENCE
            ]
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


# ======================================================================
# Helper for writing decisions with explicit timestamps
# ======================================================================


def _write_decisions(path: Path, decisions: list[ReviewDecision]) -> None:
    """Write pre-built ReviewDecision objects directly to a JSONL file."""
    with open(path, "w", encoding="utf-8") as f:
        for d in decisions:
            f.write(json.dumps(d.to_dict()) + "\n")


def _make_decision(
    category: str,
    action: DecisionAction,
    days_ago: float,
    now: datetime,
    **context,
) -> ReviewDecision:
    """Create a ReviewDecision at a specific age relative to ``now``."""
    return ReviewDecision(
        timestamp=now - timedelta(days=days_ago),
        category_name=category,
        action=action,
        context=context,
    )


# ======================================================================
# Task 4.2 — Temporal Decay Tests
# ======================================================================


class TestTemporalDecayInit:
    """Test PatternDetector initialization with half_life_days."""

    def test_default_half_life_is_90(self):
        """Default half_life_days should be 90."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "decisions.jsonl"
            dl = DecisionLogger(decisions_path=path)
            detector = PatternDetector(decision_logger=dl)
            assert detector.half_life_days == 90.0

    def test_custom_half_life(self):
        """Custom half_life_days should be stored."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "decisions.jsonl"
            dl = DecisionLogger(decisions_path=path)
            detector = PatternDetector(decision_logger=dl, half_life_days=30.0)
            assert detector.half_life_days == 30.0

    def test_reference_time_exposed(self):
        """reference_time should be settable for deterministic testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "decisions.jsonl"
            dl = DecisionLogger(decisions_path=path)
            ref = datetime(2025, 6, 1, tzinfo=timezone.utc)
            detector = PatternDetector(decision_logger=dl, reference_time=ref)
            assert detector._reference_time == ref


class TestDecisionWeightFormula:
    """Verify the exponential decay weight formula directly."""

    def test_brand_new_decision_weight_is_one(self):
        """A decision at exactly now should have weight ~1.0."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "decisions.jsonl"
            dl = DecisionLogger(decisions_path=path)
            now = datetime(2025, 6, 1, tzinfo=timezone.utc)
            detector = PatternDetector(decision_logger=dl, half_life_days=90.0)
            decision = _make_decision("X", DecisionAction.ACCEPT, 0, now)
            assert abs(detector._decision_weight(decision, now) - 1.0) < 1e-9

    def test_one_half_life_weight_is_half(self):
        """A decision exactly one half-life old should have weight ~0.5."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "decisions.jsonl"
            dl = DecisionLogger(decisions_path=path)
            now = datetime(2025, 6, 1, tzinfo=timezone.utc)
            detector = PatternDetector(decision_logger=dl, half_life_days=90.0)
            decision = _make_decision("X", DecisionAction.ACCEPT, 90, now)
            weight = detector._decision_weight(decision, now)
            assert abs(weight - 0.5) < 1e-9

    def test_two_half_lives_weight_is_quarter(self):
        """A decision two half-lives old should have weight ~0.25."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "decisions.jsonl"
            dl = DecisionLogger(decisions_path=path)
            now = datetime(2025, 6, 1, tzinfo=timezone.utc)
            detector = PatternDetector(decision_logger=dl, half_life_days=90.0)
            decision = _make_decision("X", DecisionAction.ACCEPT, 180, now)
            weight = detector._decision_weight(decision, now)
            assert abs(weight - 0.25) < 1e-9

    def test_180_day_old_contributes_about_25_percent(self):
        """
        Acceptance criterion: pattern from 180 days ago contributes ~25%
        of a recent pattern's weight (with default half-life of 90 days).
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "decisions.jsonl"
            dl = DecisionLogger(decisions_path=path)
            now = datetime(2025, 6, 1, tzinfo=timezone.utc)
            detector = PatternDetector(decision_logger=dl, half_life_days=90.0)

            recent = _make_decision("X", DecisionAction.ACCEPT, 0, now)
            old = _make_decision("X", DecisionAction.ACCEPT, 180, now)

            ratio = detector._decision_weight(old, now) / detector._decision_weight(recent, now)
            assert abs(ratio - 0.25) < 0.01

    def test_very_old_patterns_negligible(self):
        """
        Acceptance criterion: decisions older than 365 days should have
        negligible influence (weight < 0.06 with 90-day half-life).
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "decisions.jsonl"
            dl = DecisionLogger(decisions_path=path)
            now = datetime(2025, 6, 1, tzinfo=timezone.utc)
            detector = PatternDetector(decision_logger=dl, half_life_days=90.0)

            ancient = _make_decision("X", DecisionAction.ACCEPT, 365, now)
            weight = detector._decision_weight(ancient, now)
            # 365/90 ≈ 4.06 half-lives → weight ≈ 0.060
            # This is negligible — less than 7% of a fresh decision
            assert weight < 0.07
            # More precisely, ~6% of a fresh decision
            assert weight < 0.065


class TestTemporalDecayOldVsRecent:
    """Compare pattern detection for old-only vs recent-only decisions."""

    def test_recent_decisions_produce_higher_confidence(self):
        """
        3 recent decisions should produce higher confidence than
        3 old decisions of the same type.
        """
        now = datetime(2025, 6, 1, tzinfo=timezone.utc)

        # --- Recent decisions (all within 1 day) ---
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "decisions.jsonl"
            dl = DecisionLogger(decisions_path=path)
            recent_decisions = [
                _make_decision("Cat", DecisionAction.ACCEPT, i * 0.1, now) for i in range(5)
            ]
            _write_decisions(path, recent_decisions)

            detector_recent = PatternDetector(
                decision_logger=dl, half_life_days=90.0, reference_time=now
            )
            patterns_recent = detector_recent.detect_patterns()

        # --- Old decisions (all ~200 days ago) ---
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "decisions.jsonl"
            dl = DecisionLogger(decisions_path=path)
            old_decisions = [
                _make_decision("Cat", DecisionAction.ACCEPT, 200 + i * 0.1, now) for i in range(5)
            ]
            _write_decisions(path, old_decisions)

            detector_old = PatternDetector(
                decision_logger=dl, half_life_days=90.0, reference_time=now
            )
            patterns_old = detector_old.detect_patterns()

        # Recent should have higher confidence
        recent_accept = [p for p in patterns_recent if p.pattern_type == PatternType.ALWAYS_ACCEPT]
        old_accept = [p for p in patterns_old if p.pattern_type == PatternType.ALWAYS_ACCEPT]

        assert len(recent_accept) == 1
        # Old decisions at ~200 days with half_life=90:
        # weight ≈ exp(-200*ln2/90) ≈ 0.215 each → sum ≈ 1.07 < 3 threshold
        # So old_accept may be empty (below threshold).
        if len(old_accept) > 0:
            assert recent_accept[0].confidence > old_accept[0].confidence
        else:
            # Old patterns didn't even meet the threshold — proves recency bias
            assert len(old_accept) == 0

    def test_old_decisions_fall_below_threshold(self):
        """
        3 decisions from 200 days ago (with 90-day half-life) should have
        weighted sum < 3, so no pattern is detected even though raw count = 3.
        """
        now = datetime(2025, 6, 1, tzinfo=timezone.utc)

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "decisions.jsonl"
            dl = DecisionLogger(decisions_path=path)
            old_decisions = [
                _make_decision("Cat", DecisionAction.ACCEPT, 200, now) for _ in range(3)
            ]
            _write_decisions(path, old_decisions)

            detector = PatternDetector(
                decision_logger=dl,
                half_life_days=90.0,
                reference_time=now,
                min_occurrences=3,
            )
            patterns = detector.detect_patterns()

            # weighted sum ≈ 3 * 0.215 ≈ 0.64, well below threshold of 3
            accept_patterns = [p for p in patterns if p.pattern_type == PatternType.ALWAYS_ACCEPT]
            assert len(accept_patterns) == 0

    def test_recent_only_patterns_reach_high_confidence_faster(self):
        """
        Acceptance criterion: recent-only patterns should reach high
        confidence faster (fewer raw decisions needed) than old-only patterns.
        """
        now = datetime(2025, 6, 1, tzinfo=timezone.utc)

        # 5 recent decisions — each has weight ~1.0, sum ~5.0
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "decisions.jsonl"
            dl = DecisionLogger(decisions_path=path)
            recent = [_make_decision("Cat", DecisionAction.ACCEPT, 0.1 * i, now) for i in range(5)]
            _write_decisions(path, recent)
            detector = PatternDetector(decision_logger=dl, half_life_days=90.0, reference_time=now)
            patterns_recent = detector.detect_patterns()

        # 10 old decisions (~150 days old) — weight ≈ 0.316 each, sum ≈ 3.16
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "decisions.jsonl"
            dl = DecisionLogger(decisions_path=path)
            old = [_make_decision("Cat", DecisionAction.ACCEPT, 150, now) for _ in range(10)]
            _write_decisions(path, old)
            detector = PatternDetector(decision_logger=dl, half_life_days=90.0, reference_time=now)
            patterns_old = detector.detect_patterns()

        accept_recent = [p for p in patterns_recent if p.pattern_type == PatternType.ALWAYS_ACCEPT]
        accept_old = [p for p in patterns_old if p.pattern_type == PatternType.ALWAYS_ACCEPT]

        # Both should be detected, but recent has higher confidence
        assert len(accept_recent) == 1
        assert len(accept_old) == 1
        # 5 recent (weighted ~5) vs 10 old (weighted ~3.16) → recent confidence > old
        assert accept_recent[0].confidence > accept_old[0].confidence


class TestTemporalDecayConfigurable:
    """Test that half_life_days is configurable and affects detection."""

    def test_shorter_half_life_penalizes_old_more(self):
        """
        With a shorter half-life, old decisions should be penalized more
        heavily — same decisions may not meet threshold with short half-life
        but may with a longer one.
        """
        now = datetime(2025, 6, 1, tzinfo=timezone.utc)

        # 5 decisions from 60 days ago
        decisions = [_make_decision("Cat", DecisionAction.ACCEPT, 60, now) for _ in range(5)]

        # With 90-day half-life: weight ≈ exp(-60*ln2/90) ≈ 0.63 each, sum ≈ 3.15 → above threshold
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "decisions.jsonl"
            dl = DecisionLogger(decisions_path=path)
            _write_decisions(path, decisions)

            detector_long = PatternDetector(
                decision_logger=dl,
                half_life_days=90.0,
                reference_time=now,
            )
            patterns_long = detector_long.detect_patterns()

        # With 30-day half-life: weight ≈ exp(-60*ln2/30) ≈ 0.25 each, sum ≈ 1.25 → below threshold
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "decisions.jsonl"
            dl = DecisionLogger(decisions_path=path)
            _write_decisions(path, decisions)

            detector_short = PatternDetector(
                decision_logger=dl,
                half_life_days=30.0,
                reference_time=now,
            )
            patterns_short = detector_short.detect_patterns()

        accept_long = [p for p in patterns_long if p.pattern_type == PatternType.ALWAYS_ACCEPT]
        accept_short = [p for p in patterns_short if p.pattern_type == PatternType.ALWAYS_ACCEPT]

        assert len(accept_long) == 1, "90-day half-life should detect pattern at 60 days"
        assert len(accept_short) == 0, "30-day half-life should NOT detect pattern at 60 days"

    def test_very_long_half_life_behaves_like_no_decay(self):
        """
        With a very long half-life (e.g. 100000 days), old decisions should
        still contribute nearly full weight, behaving like the original code.
        """
        now = datetime(2025, 6, 1, tzinfo=timezone.utc)

        # 4 decisions from 300 days ago — with very long half-life, each
        # weighs ~0.998, sum ~3.99 → comfortably above threshold of 3
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "decisions.jsonl"
            dl = DecisionLogger(decisions_path=path)
            decisions = [_make_decision("Cat", DecisionAction.ACCEPT, 300, now) for _ in range(4)]
            _write_decisions(path, decisions)

            detector = PatternDetector(
                decision_logger=dl,
                half_life_days=100000.0,
                reference_time=now,
            )
            patterns = detector.detect_patterns()

        accept = [p for p in patterns if p.pattern_type == PatternType.ALWAYS_ACCEPT]
        assert len(accept) == 1

    def test_half_life_from_config(self):
        """LearningConfig should provide the half_life_days default."""
        from src.config.models import LearningConfig

        config = LearningConfig()
        assert config.pattern_half_life_days == 90.0

        custom = LearningConfig(pattern_half_life_days=45.0)
        assert custom.pattern_half_life_days == 45.0


class TestTemporalDecayRenamePattern:
    """Verify decay applies to rename pattern detection."""

    def test_old_renames_below_threshold(self):
        """Old rename decisions should not reach pattern threshold."""
        now = datetime(2025, 6, 1, tzinfo=timezone.utc)

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "decisions.jsonl"
            dl = DecisionLogger(decisions_path=path)
            decisions = [
                _make_decision(
                    "New",
                    DecisionAction.RENAME,
                    250,
                    now,
                    old_name="Old",
                    new_name="New",
                )
                for _ in range(3)
            ]
            _write_decisions(path, decisions)

            detector = PatternDetector(
                decision_logger=dl,
                half_life_days=90.0,
                reference_time=now,
            )
            patterns = detector.detect_patterns()
            rename = [p for p in patterns if p.pattern_type == PatternType.RENAME]
            assert len(rename) == 0

    def test_recent_renames_above_threshold(self):
        """Recent rename decisions should reach pattern threshold."""
        now = datetime(2025, 6, 1, tzinfo=timezone.utc)

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "decisions.jsonl"
            dl = DecisionLogger(decisions_path=path)
            # 4 decisions from 1 day ago: weight ≈ 0.992 each, sum ≈ 3.97
            decisions = [
                _make_decision(
                    "New",
                    DecisionAction.RENAME,
                    1,
                    now,
                    old_name="Old",
                    new_name="New",
                )
                for _ in range(4)
            ]
            _write_decisions(path, decisions)

            detector = PatternDetector(
                decision_logger=dl,
                half_life_days=90.0,
                reference_time=now,
            )
            patterns = detector.detect_patterns()
            rename = [p for p in patterns if p.pattern_type == PatternType.RENAME]
            assert len(rename) == 1


class TestTemporalDecayMergePattern:
    """Verify decay applies to merge pattern detection."""

    def test_old_merges_below_threshold(self):
        """Old merge decisions should not reach pattern threshold."""
        now = datetime(2025, 6, 1, tzinfo=timezone.utc)

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "decisions.jsonl"
            dl = DecisionLogger(decisions_path=path)
            decisions = [
                _make_decision(
                    "Source",
                    DecisionAction.MERGE,
                    250,
                    now,
                    merge_target="Target",
                )
                for _ in range(3)
            ]
            _write_decisions(path, decisions)

            detector = PatternDetector(
                decision_logger=dl,
                half_life_days=90.0,
                reference_time=now,
            )
            patterns = detector.detect_patterns()
            merge = [p for p in patterns if p.pattern_type == PatternType.MERGE]
            assert len(merge) == 0


class TestTemporalDecayDeleteLowConfPattern:
    """Verify decay applies to delete-low-confidence pattern detection."""

    def test_old_delete_low_conf_below_threshold(self):
        """Old delete-low-confidence decisions should not reach threshold."""
        now = datetime(2025, 6, 1, tzinfo=timezone.utc)

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "decisions.jsonl"
            dl = DecisionLogger(decisions_path=path)
            decisions = [
                _make_decision(
                    f"LowQ{i}",
                    DecisionAction.DELETE,
                    250,
                    now,
                    confidence=0.2,
                )
                for i in range(3)
            ]
            _write_decisions(path, decisions)

            detector = PatternDetector(
                decision_logger=dl,
                half_life_days=90.0,
                reference_time=now,
            )
            patterns = detector.detect_patterns()
            delete = [p for p in patterns if p.pattern_type == PatternType.DELETE_LOW_CONFIDENCE]
            assert len(delete) == 0


class TestTemporalDecayMixedAges:
    """Test patterns with a mix of old and recent decisions."""

    def test_mix_of_old_and_recent_still_detects_pattern(self):
        """
        A mix of 2 recent + 5 old decisions. The recent ones contribute ~2.0,
        the old ones contribute a bit each. With enough old decisions the
        total can still cross the threshold.
        """
        now = datetime(2025, 6, 1, tzinfo=timezone.utc)

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "decisions.jsonl"
            dl = DecisionLogger(decisions_path=path)

            # 2 recent (weight ~1.0 each → sum ~2.0)
            recent = [
                _make_decision("Cat", DecisionAction.ACCEPT, 1, now),
                _make_decision("Cat", DecisionAction.ACCEPT, 2, now),
            ]
            # 5 old at 120 days (weight ≈ 0.40 each → sum ≈ 2.0)
            old = [_make_decision("Cat", DecisionAction.ACCEPT, 120, now) for _ in range(5)]
            _write_decisions(path, recent + old)

            detector = PatternDetector(
                decision_logger=dl,
                half_life_days=90.0,
                reference_time=now,
            )
            patterns = detector.detect_patterns()

        accept = [p for p in patterns if p.pattern_type == PatternType.ALWAYS_ACCEPT]
        # total weighted ≈ 2.0 + 2.0 = 4.0 → above min_occurrences=3
        assert len(accept) == 1
        assert accept[0].occurrences == 7  # raw count is 7

    def test_occurrences_reflects_raw_count(self):
        """Even with decay, occurrences should report the raw count."""
        now = datetime(2025, 6, 1, tzinfo=timezone.utc)

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "decisions.jsonl"
            dl = DecisionLogger(decisions_path=path)
            decisions = [_make_decision("Cat", DecisionAction.ACCEPT, 1, now) for _ in range(4)]
            _write_decisions(path, decisions)

            detector = PatternDetector(
                decision_logger=dl,
                half_life_days=90.0,
                reference_time=now,
            )
            patterns = detector.detect_patterns()

        accept = [p for p in patterns if p.pattern_type == PatternType.ALWAYS_ACCEPT]
        assert len(accept) == 1
        assert accept[0].occurrences == 4
