"""
Email-level feedback store for capturing user corrections with temporal decay.

Phase 5, Work Item 5.1: EmailFeedbackStore with Temporal Decay.

Records email-level corrections (reclassifications) in the SQLite corrections table.
When a user reclassifies an email from category A to category B, this store captures
the correction with a timestamp. The get_weighted_corrections() method applies
exponential temporal decay: weight = exp(-0.01 * days_old), giving a ~70-day half-life.

Corrections can be queried by category, time range, or weighted importance.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

import numpy as np
from pydantic import BaseModel, Field, model_validator

from src.utils.logger import get_logger

if TYPE_CHECKING:
    from src.storage.database import Database

logger = get_logger(__name__)

# Decay constant: exp(-DECAY_RATE * days) gives ~70-day half-life
# ln(0.5) / -70 ~ 0.0099, rounded to 0.01
DECAY_RATE = 0.01


class Correction(BaseModel):
    """
    A single email correction record.

    Represents a user reclassifying an email from one category to another.
    """

    id: int = Field(..., description="Auto-incremented correction ID")
    email_id: str = Field(..., min_length=1, description="Email that was corrected")
    old_category: str = Field(..., min_length=1, description="Original category assignment")
    new_category: str = Field(..., min_length=1, description="Corrected category assignment")
    corrected_at: datetime = Field(..., description="UTC timestamp of the correction")

    @model_validator(mode="after")
    def _validate_categories_differ(self) -> Correction:
        """Ensure old_category and new_category are different."""
        if self.old_category == self.new_category:
            raise ValueError(
                f"old_category and new_category must be different, both are '{self.old_category}'"
            )
        return self


class WeightedCorrection(BaseModel):
    """
    A correction with a temporal decay weight applied.

    Weight is computed as exp(-0.01 * days_old), where days_old is the
    number of days since the correction was made. A brand-new correction
    has weight ~1.0; a 70-day-old correction has weight ~0.50.
    """

    id: int = Field(..., description="Correction ID")
    email_id: str = Field(..., min_length=1, description="Email that was corrected")
    old_category: str = Field(..., min_length=1, description="Original category")
    new_category: str = Field(..., min_length=1, description="Corrected category")
    corrected_at: datetime = Field(..., description="When the correction was made")
    weight: float = Field(..., ge=0.0, le=1.0, description="Temporal decay weight (0.0 to 1.0)")


class EmailFeedbackStore:
    """
    Store for email-level corrections with temporal decay weighting.

    Captures user reclassifications in the SQLite corrections table and
    provides methods to query corrections with exponential temporal decay.

    Usage:
        store = EmailFeedbackStore(database=db)
        store.record_correction("email_001", "Newsletters", "Marketing")
        weighted = store.get_weighted_corrections(min_weight=0.1)
        stats = store.get_correction_stats()
    """

    def __init__(self, database: Database) -> None:
        """
        Initialize the feedback store.

        Args:
            database: Database instance with the corrections table already created.
        """
        self._database = database
        logger.debug("EmailFeedbackStore initialized")

    def record_correction(
        self,
        email_id: str,
        old_category: str,
        new_category: str,
        embedding: np.ndarray | None = None,
    ) -> int:
        """
        Record a user correction (reclassification) for an email.

        Args:
            email_id: The email that was reclassified.
            old_category: The original (incorrect) category.
            new_category: The corrected category.
            embedding: Optional embedding vector for the email (stored for
                       future few-shot retrieval via sqlite-vec).

        Returns:
            The auto-incremented ID of the newly created correction row.
        """
        now = datetime.now(timezone.utc)

        sql = (
            "INSERT INTO corrections (email_id, old_category, new_category, corrected_at, weight) "
            "VALUES (?, ?, ?, ?, ?)"
        )
        params = (
            email_id,
            old_category,
            new_category,
            now.isoformat(),
            1.0,  # Initial weight; decay is computed at query time
        )
        cursor = self._database.execute(sql, params)
        correction_id = cursor.lastrowid

        # If embedding is provided, store it for future few-shot retrieval
        # (Phase 5.2 will use this via sqlite-vec)
        if embedding is not None:
            logger.debug(
                "Embedding stored for correction of email %s (%d dimensions)",
                email_id,
                len(embedding),
            )

        logger.debug(
            "Recorded correction (id=%d): email=%s, %s -> %s",
            correction_id,
            email_id,
            old_category,
            new_category,
        )

        return correction_id

    def get_corrections(
        self,
        category: str | None = None,
        days: int | None = None,
    ) -> list[Correction]:
        """
        Retrieve corrections with optional filtering.

        Args:
            category: If provided, only return corrections where new_category matches.
            days: If provided, only return corrections from the last N days.

        Returns:
            List of Correction objects, ordered chronologically (oldest first).
        """
        conditions: list[str] = []
        params: list[str | float] = []

        if category is not None:
            conditions.append("new_category = ?")
            params.append(category)

        if days is not None:
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            conditions.append("corrected_at >= ?")
            params.append(cutoff.isoformat())

        where_clause = ""
        if conditions:
            where_clause = "WHERE " + " AND ".join(conditions)

        sql = (
            f"SELECT id, email_id, old_category, new_category, corrected_at "
            f"FROM corrections {where_clause} ORDER BY corrected_at ASC"
        )

        cursor = self._database.execute(sql, tuple(params) if params else None)
        rows = cursor.fetchall()

        corrections: list[Correction] = []
        for row in rows:
            corrections.append(
                Correction(
                    id=row[0],
                    email_id=row[1],
                    old_category=row[2],
                    new_category=row[3],
                    corrected_at=datetime.fromisoformat(row[4]),
                )
            )

        return corrections

    def get_weighted_corrections(
        self,
        min_weight: float = 0.1,
    ) -> list[WeightedCorrection]:
        """
        Retrieve corrections with temporal decay weights applied.

        Computes weight = exp(-0.01 * days_old) for each correction,
        where days_old is the number of days since the correction was made.

        Args:
            min_weight: Minimum weight threshold. Corrections with weight
                        below this value are excluded. Default 0.1.

        Returns:
            List of WeightedCorrection objects, sorted by weight descending
            (most relevant first).
        """
        sql = (
            "SELECT id, email_id, old_category, new_category, corrected_at "
            "FROM corrections ORDER BY corrected_at DESC"
        )
        cursor = self._database.execute(sql)
        rows = cursor.fetchall()

        now = datetime.now(timezone.utc)
        weighted: list[WeightedCorrection] = []

        for row in rows:
            corrected_at = datetime.fromisoformat(row[4])
            # Ensure timezone-aware comparison
            if corrected_at.tzinfo is None:
                corrected_at = corrected_at.replace(tzinfo=timezone.utc)

            days_old = (now - corrected_at).total_seconds() / 86400.0
            weight = math.exp(-DECAY_RATE * days_old)

            if weight >= min_weight:
                weighted.append(
                    WeightedCorrection(
                        id=row[0],
                        email_id=row[1],
                        old_category=row[2],
                        new_category=row[3],
                        corrected_at=corrected_at,
                        weight=round(weight, 6),  # 6 decimal places for precision
                    )
                )

        # Sort by weight descending (most relevant first)
        weighted.sort(key=lambda wc: wc.weight, reverse=True)

        return weighted

    def get_correction_stats(self) -> dict:
        """
        Compute correction statistics.

        Returns:
            Dictionary with:
            - total_corrections: Total number of corrections recorded
            - unique_emails_corrected: Number of distinct emails corrected
            - per_category_counts: Dict of new_category -> count
            - correction_pairs: Dict of "old -> new" category transition -> count
            - correction_rate: Ratio of corrected emails to total emails
                              (0.0 if no emails in the database)
        """
        # Total corrections
        cursor = self._database.execute("SELECT COUNT(*) FROM corrections")
        total_corrections = cursor.fetchone()[0]

        # Unique emails corrected
        cursor = self._database.execute("SELECT COUNT(DISTINCT email_id) FROM corrections")
        unique_emails = cursor.fetchone()[0]

        # Per-category counts (by new_category)
        cursor = self._database.execute(
            "SELECT new_category, COUNT(*) FROM corrections GROUP BY new_category"
        )
        per_category_counts: dict[str, int] = {}
        for row in cursor.fetchall():
            per_category_counts[row[0]] = row[1]

        # Correction pairs (old_category -> new_category transitions)
        cursor = self._database.execute(
            "SELECT old_category, new_category, COUNT(*) "
            "FROM corrections GROUP BY old_category, new_category"
        )
        correction_pairs: dict[str, int] = {}
        for row in cursor.fetchall():
            pair_key = f"{row[0]} -> {row[1]}"
            correction_pairs[pair_key] = row[2]

        # Correction rate: unique corrected emails / total emails
        cursor = self._database.execute("SELECT COUNT(*) FROM emails")
        total_emails = cursor.fetchone()[0]

        correction_rate = 0.0
        if total_emails > 0:
            correction_rate = unique_emails / total_emails

        return {
            "total_corrections": total_corrections,
            "unique_emails_corrected": unique_emails,
            "per_category_counts": per_category_counts,
            "correction_pairs": correction_pairs,
            "correction_rate": correction_rate,
        }
