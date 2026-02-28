"""
Pattern detector for identifying recurring patterns in user decisions.

Task 5B.2: Pattern Detection
Task 4.2: Temporal Decay — recent decisions carry more weight than old ones.

Analyzes logged review decisions to identify patterns such as:
- Rename patterns (X -> Y repeatedly)
- Merge patterns (X + Y repeatedly)
- Delete low-confidence patterns (deleting when confidence < threshold)
- Always accept patterns (same name always accepted)

Patterns are used to pre-apply learned preferences in future reviews.

Temporal decay: each occurrence is weighted by exp(-days_old / half_life_days).
A decision that is `half_life_days` old contributes 50% of a brand-new decision's
weight.  Decisions older than ~4 half-lives contribute negligible weight.
"""

import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
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
        occurrences: Number of times this pattern was observed (raw, unweighted)
        confidence: Confidence score for the pattern (0-1, based on recency-weighted occurrences)
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
    occurrence threshold.  Each occurrence is weighted by its recency using
    exponential decay: ``weight = exp(-days_old / half_life_days)``.

    Patterns can be used to pre-apply learned preferences in future category
    reviews.

    Example usage:
        logger = DecisionLogger()
        detector = PatternDetector(decision_logger=logger)
        patterns = detector.detect_patterns()
        high_confidence = detector.get_high_confidence_patterns(min_confidence=0.8)
    """

    # Threshold below which deletes are considered "low confidence" deletes
    LOW_CONFIDENCE_THRESHOLD = 0.4

    # Small tolerance for floating-point comparison of weighted counts
    # against integer thresholds.  Prevents near-instant decisions from
    # being fractionally below the threshold due to microsecond age.
    _WEIGHT_TOLERANCE = 1e-6

    def __init__(
        self,
        decision_logger: DecisionLogger,
        min_occurrences: int = 3,
        half_life_days: float = 90.0,
        reference_time: datetime | None = None,
    ):
        """
        Initialize the pattern detector.

        Args:
            decision_logger: DecisionLogger instance to read decisions from
            min_occurrences: Minimum number of occurrences to consider a pattern
                           (default: 3)
            half_life_days: Half-life in days for temporal decay of pattern
                          weights.  A decision this many days old contributes
                          50% of a brand-new decision's weight.  (default: 90)
            reference_time: The "now" timestamp used for age calculation.
                           Defaults to ``datetime.now(timezone.utc)`` when
                           ``detect_patterns`` is called.  Exposed for testing.
        """
        self.decision_logger = decision_logger
        self.min_occurrences = min_occurrences
        self.half_life_days = half_life_days
        self._reference_time = reference_time

        logger.debug(
            f"PatternDetector initialized with min_occurrences={min_occurrences}, "
            f"half_life_days={half_life_days}"
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

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

        now = self._reference_time or datetime.now(timezone.utc)

        patterns: list[DetectedPattern] = []

        # Detect each pattern type
        patterns.extend(self._detect_rename_patterns(decisions, now))
        patterns.extend(self._detect_merge_patterns(decisions, now))
        patterns.extend(self._detect_delete_low_confidence_patterns(decisions, now))
        patterns.extend(self._detect_always_accept_patterns(decisions, now))

        # Sort by confidence (highest first)
        patterns.sort(key=lambda p: p.confidence, reverse=True)

        logger.info(f"Detected {len(patterns)} patterns from {len(decisions)} decisions")
        return patterns

    def get_high_confidence_patterns(self, min_confidence: float = 0.8) -> list[DetectedPattern]:
        """
        Get only patterns with high confidence.

        Args:
            min_confidence: Minimum confidence threshold (default: 0.8)

        Returns:
            List of DetectedPattern objects with confidence >= min_confidence
        """
        all_patterns = self.detect_patterns()
        return [p for p in all_patterns if p.confidence >= min_confidence]

    # ------------------------------------------------------------------
    # Temporal decay helpers
    # ------------------------------------------------------------------

    def _decision_weight(self, decision: ReviewDecision, now: datetime) -> float:
        """
        Compute the temporal-decay weight for a single decision.

        Uses ``exp(-days_old / half_life_days)`` so that a decision exactly
        one half-life old receives weight 0.5.

        Args:
            decision: The review decision
            now: Current reference time

        Returns:
            Weight in the range (0, 1]
        """
        delta = now - decision.timestamp
        days_old = max(delta.total_seconds() / 86400.0, 0.0)
        return math.exp(-days_old * math.log(2) / self.half_life_days)

    def _weighted_count(
        self,
        decisions: list[ReviewDecision],
        now: datetime,
    ) -> float:
        """
        Compute the sum of temporal-decay weights for a list of decisions.

        Args:
            decisions: Decisions belonging to this pattern group
            now: Current reference time

        Returns:
            Weighted occurrence count (a float >= 0)
        """
        return sum(self._decision_weight(d, now) for d in decisions)

    # ------------------------------------------------------------------
    # Confidence calculation
    # ------------------------------------------------------------------

    def _calculate_confidence(self, weighted_count: float) -> float:
        """
        Calculate confidence score based on recency-weighted occurrence count.

        Confidence scales from 0.5 at the minimum-occurrence threshold to
        0.95+ at high weighted counts.  Uses a logarithmic scale so that
        diminishing returns kick in and huge numbers aren't required.

        Args:
            weighted_count: Recency-weighted occurrence count

        Returns:
            Confidence score between 0.0 and 0.99
        """
        if weighted_count < self.min_occurrences - self._WEIGHT_TOLERANCE:
            return 0.0

        # Base confidence at threshold
        base_confidence = 0.5

        # Scale up logarithmically (each doubling adds ~0.2)
        ratio = weighted_count / self.min_occurrences
        log_factor = math.log2(ratio) if ratio > 1 else 0
        confidence = base_confidence + (log_factor * 0.2)

        # Cap at 0.99
        return min(confidence, 0.99)

    # ------------------------------------------------------------------
    # Pattern detection methods
    # ------------------------------------------------------------------

    def _detect_rename_patterns(
        self,
        decisions: list[ReviewDecision],
        now: datetime,
    ) -> list[DetectedPattern]:
        """
        Detect rename patterns (X -> Y repeatedly).

        Args:
            decisions: List of all decisions
            now: Current reference time

        Returns:
            List of DetectedPattern objects for rename patterns
        """
        groups: dict[tuple[str, str], list[ReviewDecision]] = defaultdict(list)

        for decision in decisions:
            if decision.action == DecisionAction.RENAME:
                old_name = decision.context.get("old_name")
                new_name = decision.context.get("new_name")
                if old_name and new_name:
                    groups[(old_name, new_name)].append(decision)

        patterns = []
        for (old_name, new_name), group_decisions in groups.items():
            weighted = self._weighted_count(group_decisions, now)
            if weighted >= self.min_occurrences - self._WEIGHT_TOLERANCE:
                patterns.append(
                    DetectedPattern(
                        pattern_type=PatternType.RENAME,
                        parameters={"old_name": old_name, "new_name": new_name},
                        occurrences=len(group_decisions),
                        confidence=self._calculate_confidence(weighted),
                    )
                )

        return patterns

    def _detect_merge_patterns(
        self,
        decisions: list[ReviewDecision],
        now: datetime,
    ) -> list[DetectedPattern]:
        """
        Detect merge patterns (source + target repeatedly).

        Args:
            decisions: List of all decisions
            now: Current reference time

        Returns:
            List of DetectedPattern objects for merge patterns
        """
        groups: dict[tuple[str, str], list[ReviewDecision]] = defaultdict(list)

        for decision in decisions:
            if decision.action == DecisionAction.MERGE:
                source = decision.category_name
                target = decision.context.get("merge_target")
                if source and target:
                    groups[(source, target)].append(decision)

        patterns = []
        for (source, target), group_decisions in groups.items():
            weighted = self._weighted_count(group_decisions, now)
            if weighted >= self.min_occurrences - self._WEIGHT_TOLERANCE:
                patterns.append(
                    DetectedPattern(
                        pattern_type=PatternType.MERGE,
                        parameters={"source": source, "target": target},
                        occurrences=len(group_decisions),
                        confidence=self._calculate_confidence(weighted),
                    )
                )

        return patterns

    def _detect_delete_low_confidence_patterns(
        self,
        decisions: list[ReviewDecision],
        now: datetime,
    ) -> list[DetectedPattern]:
        """
        Detect patterns of deleting low-confidence categories.

        If user consistently deletes categories below a certain confidence
        threshold, this is detected as a pattern.

        Args:
            decisions: List of all decisions
            now: Current reference time

        Returns:
            List of DetectedPattern objects (at most one for delete low confidence)
        """
        low_conf_decisions: list[ReviewDecision] = []
        low_conf_values: list[float] = []

        for decision in decisions:
            if decision.action == DecisionAction.DELETE:
                confidence = decision.context.get("confidence")
                if confidence is not None and confidence <= self.LOW_CONFIDENCE_THRESHOLD:
                    low_conf_decisions.append(decision)
                    low_conf_values.append(confidence)

        if not low_conf_decisions:
            return []

        weighted = self._weighted_count(low_conf_decisions, now)

        if weighted >= self.min_occurrences - self._WEIGHT_TOLERANCE:
            avg_threshold = sum(low_conf_values) / len(low_conf_values) if low_conf_values else 0.3

            return [
                DetectedPattern(
                    pattern_type=PatternType.DELETE_LOW_CONFIDENCE,
                    parameters={"threshold": round(avg_threshold + 0.05, 2)},
                    occurrences=len(low_conf_decisions),
                    confidence=self._calculate_confidence(weighted),
                )
            ]

        return []

    def _detect_always_accept_patterns(
        self,
        decisions: list[ReviewDecision],
        now: datetime,
    ) -> list[DetectedPattern]:
        """
        Detect patterns of always accepting certain category names.

        Args:
            decisions: List of all decisions
            now: Current reference time

        Returns:
            List of DetectedPattern objects for always-accept patterns
        """
        groups: dict[str, list[ReviewDecision]] = defaultdict(list)

        for decision in decisions:
            if decision.action == DecisionAction.ACCEPT:
                groups[decision.category_name].append(decision)

        patterns = []
        for category_name, group_decisions in groups.items():
            weighted = self._weighted_count(group_decisions, now)
            if weighted >= self.min_occurrences - self._WEIGHT_TOLERANCE:
                patterns.append(
                    DetectedPattern(
                        pattern_type=PatternType.ALWAYS_ACCEPT,
                        parameters={"category_name": category_name},
                        occurrences=len(group_decisions),
                        confidence=self._calculate_confidence(weighted),
                    )
                )

        return patterns
