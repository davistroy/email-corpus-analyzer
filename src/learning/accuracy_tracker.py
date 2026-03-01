"""
Per-category accuracy tracking with correction rate monitoring.

Phase 6, Work Item 6.4: Monitors correction rates over a rolling window
to detect when a category's classification accuracy has degraded enough
to trigger retraining.

AccuracyTracker computes:
- Total classifications and corrections in a time window
- Per-category correction rate (corrections / classifications)
- Whether any category exceeds the retraining threshold

The tracker reads from the same SQLite tables that EmailCategorizer writes
(classifications) and EmailFeedbackStore writes (corrections), so it
observes the real production data with no additional instrumentation.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from src.utils.logger import get_logger

if TYPE_CHECKING:
    from src.learning.feedback_store import EmailFeedbackStore
    from src.storage.database import Database

logger = get_logger(__name__)


# =============================================================================
# Data Models
# =============================================================================


class CategoryAccuracyMetrics(BaseModel):
    """Per-category accuracy metrics for a time window."""

    category_name: str = Field(..., min_length=1)
    total_classifications: int = Field(..., ge=0)
    total_corrections: int = Field(..., ge=0)
    correction_rate: float = Field(..., ge=0.0, le=1.0)

    @property
    def accuracy_rate(self) -> float:
        """Estimated accuracy (1 - correction_rate)."""
        return 1.0 - self.correction_rate


class AccuracyReport(BaseModel):
    """
    Accuracy report for a time window across all categories.

    Contains aggregate metrics and per-category breakdowns.
    """

    total_classifications: int = Field(..., ge=0)
    total_corrections: int = Field(..., ge=0)
    overall_correction_rate: float = Field(..., ge=0.0, le=1.0)
    per_category_metrics: dict[str, CategoryAccuracyMetrics] = Field(default_factory=dict)
    window_days: int = Field(..., ge=0)
    worst_category: str | None = Field(default=None)
    worst_correction_rate: float = Field(default=0.0, ge=0.0, le=1.0)


# =============================================================================
# AccuracyTracker
# =============================================================================


class AccuracyTracker:
    """
    Monitors per-category correction rates to detect accuracy degradation.

    Reads from the classifications and corrections tables in the SQLite
    database. Computes per-category correction rates over a rolling
    time window and determines whether retraining is needed.

    Usage:
        tracker = AccuracyTracker(correction_store=feedback, classification_store=db)
        report = tracker.get_accuracy_report(days=7)
        if tracker.needs_retraining(threshold=0.20):
            # trigger retraining
    """

    def __init__(
        self,
        correction_store: EmailFeedbackStore,
        classification_store: Database,
    ) -> None:
        """
        Initialize the accuracy tracker.

        Args:
            correction_store: EmailFeedbackStore for reading corrections.
            classification_store: Database for reading classifications.
        """
        self._correction_store = correction_store
        self._classification_store = classification_store

    def get_accuracy_report(self, days: int = 7) -> AccuracyReport:
        """
        Compute accuracy metrics for the specified time window.

        Args:
            days: Number of days to look back. Default 7.

        Returns:
            AccuracyReport with aggregate and per-category metrics.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        cutoff_iso = cutoff.isoformat()

        # Get classifications in the window
        cursor = self._classification_store.execute(
            "SELECT category_name, COUNT(*) FROM classifications "
            "WHERE classified_at >= ? GROUP BY category_name",
            (cutoff_iso,),
        )
        classifications_by_category: dict[str, int] = {}
        total_classifications = 0
        for row in cursor.fetchall():
            classifications_by_category[row[0]] = row[1]
            total_classifications += row[1]

        # Get corrections in the window
        corrections = self._correction_store.get_corrections(days=days)
        total_corrections = len(corrections)

        # Count corrections per (old) category — the category that was wrong
        corrections_by_category: dict[str, int] = defaultdict(int)
        for correction in corrections:
            corrections_by_category[correction.old_category] += 1

        # Build per-category metrics
        all_categories = set(classifications_by_category.keys()) | set(
            corrections_by_category.keys()
        )
        per_category: dict[str, CategoryAccuracyMetrics] = {}
        worst_category: str | None = None
        worst_rate = 0.0

        for cat in all_categories:
            cat_classifications = classifications_by_category.get(cat, 0)
            cat_corrections = corrections_by_category.get(cat, 0)

            if cat_classifications > 0:
                correction_rate = cat_corrections / cat_classifications
            elif cat_corrections > 0:
                correction_rate = 1.0  # All corrections, no tracked classifications
            else:
                correction_rate = 0.0

            correction_rate = min(correction_rate, 1.0)

            metrics = CategoryAccuracyMetrics(
                category_name=cat,
                total_classifications=cat_classifications,
                total_corrections=cat_corrections,
                correction_rate=round(correction_rate, 4),
            )
            per_category[cat] = metrics

            if correction_rate > worst_rate:
                worst_rate = correction_rate
                worst_category = cat

        overall_rate = (
            total_corrections / total_classifications if total_classifications > 0 else 0.0
        )

        return AccuracyReport(
            total_classifications=total_classifications,
            total_corrections=total_corrections,
            overall_correction_rate=round(min(overall_rate, 1.0), 4),
            per_category_metrics=per_category,
            window_days=days,
            worst_category=worst_category,
            worst_correction_rate=round(worst_rate, 4),
        )

    def needs_retraining(self, threshold: float = 0.20, days: int = 7) -> bool:
        """
        Check whether any category's correction rate exceeds the threshold.

        Args:
            threshold: Maximum acceptable correction rate (0.0 to 1.0).
                If any category exceeds this rate, retraining is recommended.
                Default is 0.20 (20%).
            days: Number of days to look back. Default 7.

        Returns:
            True if any category exceeds the threshold.
        """
        report = self.get_accuracy_report(days=days)

        if report.total_classifications == 0:
            return False

        for cat, metrics in report.per_category_metrics.items():
            if metrics.correction_rate > threshold:
                logger.info(
                    "Retraining recommended: category '%s' has correction rate %.1f%% "
                    "(threshold: %.1f%%)",
                    cat,
                    metrics.correction_rate * 100,
                    threshold * 100,
                )
                return True

        return False


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "AccuracyReport",
    "AccuracyTracker",
    "CategoryAccuracyMetrics",
]
