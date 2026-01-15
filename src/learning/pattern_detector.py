"""
Pattern detector for identifying recurring patterns in user decisions.

Task 5B.2: Pattern Detection

Analyzes logged review decisions to identify patterns such as:
- Rename patterns (X -> Y repeatedly)
- Merge patterns (X + Y repeatedly)
- Delete low-confidence patterns (deleting when confidence < threshold)
- Always accept patterns (same name always accepted)

Patterns are used to pre-apply learned preferences in future reviews.
"""
from collections import Counter
from dataclasses import dataclass
from enum import Enum

from src.learning.decision_logger import DecisionAction, DecisionLogger, ReviewDecision
from src.utils.logger import get_logger

logger = get_logger(__name__)


class PatternType(str, Enum):
    """Types of patterns that can be detected."""

    RENAME = "rename"
    MERGE = "merge"
    DELETE_LOW_CONFIDENCE = "delete_low_confidence"
    ALWAYS_ACCEPT = "always_accept"


@dataclass
class DetectedPattern:
    """
    Represents a detected pattern in user decisions.

    Attributes:
        pattern_type: Type of pattern (rename, merge, delete_low_confidence, always_accept)
        parameters: Pattern-specific parameters (e.g., old_name, new_name for rename)
        occurrences: Number of times this pattern was observed
        confidence: Confidence score for the pattern (0-1, based on occurrences)
    """

    pattern_type: PatternType
    parameters: dict
    occurrences: int
    confidence: float

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "pattern_type": self.pattern_type.value,
            "parameters": self.parameters,
            "occurrences": self.occurrences,
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DetectedPattern":
        """Create DetectedPattern from dictionary."""
        return cls(
            pattern_type=PatternType(data["pattern_type"]),
            parameters=data["parameters"],
            occurrences=data["occurrences"],
            confidence=data["confidence"],
        )


class PatternDetector:
    """
    Detects recurring patterns in user review decisions.

    Analyzes the decision log to identify patterns that meet the minimum
    occurrence threshold. Patterns can be used to pre-apply learned
    preferences in future category reviews.

    Example usage:
        logger = DecisionLogger()
        detector = PatternDetector(decision_logger=logger)
        patterns = detector.detect_patterns()
        high_confidence = detector.get_high_confidence_patterns(min_confidence=0.8)
    """

    # Threshold below which deletes are considered "low confidence" deletes
    LOW_CONFIDENCE_THRESHOLD = 0.4

    def __init__(
        self,
        decision_logger: DecisionLogger,
        min_occurrences: int = 3,
    ):
        """
        Initialize the pattern detector.

        Args:
            decision_logger: DecisionLogger instance to read decisions from
            min_occurrences: Minimum number of occurrences to consider a pattern
                           (default: 3)
        """
        self.decision_logger = decision_logger
        self.min_occurrences = min_occurrences

        logger.debug(f"PatternDetector initialized with min_occurrences={min_occurrences}")

    def detect_patterns(self) -> list[DetectedPattern]:
        """
        Detect all patterns in the decision history.

        Analyzes the decision log and returns all patterns that meet the
        minimum occurrence threshold, sorted by confidence (highest first).

        Returns:
            List of DetectedPattern objects, sorted by confidence descending
        """
        decisions = self.decision_logger.get_decisions()
        if not decisions:
            return []

        patterns: list[DetectedPattern] = []

        # Detect each pattern type
        patterns.extend(self._detect_rename_patterns(decisions))
        patterns.extend(self._detect_merge_patterns(decisions))
        patterns.extend(self._detect_delete_low_confidence_patterns(decisions))
        patterns.extend(self._detect_always_accept_patterns(decisions))

        # Sort by confidence (highest first)
        patterns.sort(key=lambda p: p.confidence, reverse=True)

        logger.info(f"Detected {len(patterns)} patterns from {len(decisions)} decisions")
        return patterns

    def get_high_confidence_patterns(
        self,
        min_confidence: float = 0.8
    ) -> list[DetectedPattern]:
        """
        Get only patterns with high confidence.

        Args:
            min_confidence: Minimum confidence threshold (default: 0.8)

        Returns:
            List of DetectedPattern objects with confidence >= min_confidence
        """
        all_patterns = self.detect_patterns()
        return [p for p in all_patterns if p.confidence >= min_confidence]

    def _calculate_confidence(self, occurrences: int) -> float:
        """
        Calculate confidence score based on number of occurrences.

        Confidence scales from 0.5 at threshold to 0.95+ at high occurrences.
        Uses a logarithmic scale to avoid requiring huge numbers of occurrences.

        Args:
            occurrences: Number of pattern occurrences

        Returns:
            Confidence score between 0.5 and 0.99
        """
        import math

        if occurrences < self.min_occurrences:
            return 0.0

        # Base confidence at threshold
        base_confidence = 0.5

        # Scale up logarithmically (each doubling adds ~0.2)
        # At 3 occurrences: ~0.5, at 6: ~0.7, at 10: ~0.85, at 15: ~0.9
        ratio = occurrences / self.min_occurrences
        log_factor = math.log2(ratio) if ratio > 1 else 0
        confidence = base_confidence + (log_factor * 0.2)

        # Cap at 0.99
        return min(confidence, 0.99)

    def _detect_rename_patterns(
        self,
        decisions: list[ReviewDecision]
    ) -> list[DetectedPattern]:
        """
        Detect rename patterns (X -> Y repeatedly).

        Args:
            decisions: List of all decisions

        Returns:
            List of DetectedPattern objects for rename patterns
        """
        # Count occurrences of each old_name -> new_name pair
        rename_counts: Counter = Counter()

        for decision in decisions:
            if decision.action == DecisionAction.RENAME:
                old_name = decision.context.get("old_name")
                new_name = decision.context.get("new_name")
                if old_name and new_name:
                    key = (old_name, new_name)
                    rename_counts[key] += 1

        # Create patterns for those meeting threshold
        patterns = []
        for (old_name, new_name), count in rename_counts.items():
            if count >= self.min_occurrences:
                patterns.append(DetectedPattern(
                    pattern_type=PatternType.RENAME,
                    parameters={"old_name": old_name, "new_name": new_name},
                    occurrences=count,
                    confidence=self._calculate_confidence(count),
                ))

        return patterns

    def _detect_merge_patterns(
        self,
        decisions: list[ReviewDecision]
    ) -> list[DetectedPattern]:
        """
        Detect merge patterns (source + target repeatedly).

        Args:
            decisions: List of all decisions

        Returns:
            List of DetectedPattern objects for merge patterns
        """
        merge_counts: Counter = Counter()

        for decision in decisions:
            if decision.action == DecisionAction.MERGE:
                source = decision.category_name
                target = decision.context.get("merge_target")
                if source and target:
                    key = (source, target)
                    merge_counts[key] += 1

        patterns = []
        for (source, target), count in merge_counts.items():
            if count >= self.min_occurrences:
                patterns.append(DetectedPattern(
                    pattern_type=PatternType.MERGE,
                    parameters={"source": source, "target": target},
                    occurrences=count,
                    confidence=self._calculate_confidence(count),
                ))

        return patterns

    def _detect_delete_low_confidence_patterns(
        self,
        decisions: list[ReviewDecision]
    ) -> list[DetectedPattern]:
        """
        Detect patterns of deleting low-confidence categories.

        If user consistently deletes categories below a certain confidence
        threshold, this is detected as a pattern.

        Args:
            decisions: List of all decisions

        Returns:
            List of DetectedPattern objects (at most one for delete low confidence)
        """
        # Collect confidence values from delete decisions
        delete_confidences = []
        for decision in decisions:
            if decision.action == DecisionAction.DELETE:
                confidence = decision.context.get("confidence")
                if confidence is not None:
                    delete_confidences.append(confidence)

        if len(delete_confidences) < self.min_occurrences:
            return []

        # Check if most deletes are for low confidence categories
        low_conf_count = sum(
            1 for c in delete_confidences if c <= self.LOW_CONFIDENCE_THRESHOLD
        )

        if low_conf_count >= self.min_occurrences:
            # Calculate the average threshold used
            low_conf_values = [
                c for c in delete_confidences if c <= self.LOW_CONFIDENCE_THRESHOLD
            ]
            avg_threshold = sum(low_conf_values) / len(low_conf_values) if low_conf_values else 0.3

            return [DetectedPattern(
                pattern_type=PatternType.DELETE_LOW_CONFIDENCE,
                parameters={"threshold": round(avg_threshold + 0.05, 2)},  # Slightly above average
                occurrences=low_conf_count,
                confidence=self._calculate_confidence(low_conf_count),
            )]

        return []

    def _detect_always_accept_patterns(
        self,
        decisions: list[ReviewDecision]
    ) -> list[DetectedPattern]:
        """
        Detect patterns of always accepting certain category names.

        Args:
            decisions: List of all decisions

        Returns:
            List of DetectedPattern objects for always-accept patterns
        """
        accept_counts: Counter = Counter()

        for decision in decisions:
            if decision.action == DecisionAction.ACCEPT:
                accept_counts[decision.category_name] += 1

        patterns = []
        for category_name, count in accept_counts.items():
            if count >= self.min_occurrences:
                patterns.append(DetectedPattern(
                    pattern_type=PatternType.ALWAYS_ACCEPT,
                    parameters={"category_name": category_name},
                    occurrences=count,
                    confidence=self._calculate_confidence(count),
                ))

        return patterns
