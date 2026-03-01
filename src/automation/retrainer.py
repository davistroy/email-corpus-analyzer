"""
Retrainer orchestrator for automated model retraining from accumulated corrections.

Phase 6, Work Item 6.4: Collects training data from the feedback store (corrections),
groups by corrected category, filters categories with insufficient examples, and
triggers classifier training. Designed to be invoked by the scheduler for nightly
retraining when enough new corrections have accumulated.

The Retrainer:
1. Queries the EmailFeedbackStore for all corrections
2. Fetches the corresponding email text from EmailStore
3. Pairs email text with the corrected (new) category label
4. Filters out categories with fewer than min_examples corrections
5. Trains the provided classifier on the assembled training set
"""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from src.utils.logger import get_logger

if TYPE_CHECKING:
    from src.classifiers.setfit_classifier import SetFitClassifier
    from src.learning.feedback_store import EmailFeedbackStore
    from src.storage.email_store import EmailStore

logger = get_logger(__name__)


# =============================================================================
# Data Models
# =============================================================================


class TrainResult(BaseModel):
    """Result of a retraining run."""

    success: bool = Field(..., description="Whether training completed successfully")
    total_examples: int = Field(..., ge=0, description="Number of training examples used")
    categories_trained: int = Field(
        ..., ge=0, description="Number of categories with sufficient examples"
    )
    categories_skipped: list[str] = Field(
        default_factory=list,
        description="Categories skipped due to insufficient examples",
    )
    error_message: str | None = Field(default=None, description="Error message if training failed")


# =============================================================================
# Retrainer
# =============================================================================


class Retrainer:
    """
    Orchestrates model retraining from accumulated user corrections.

    Collects labeled examples from the feedback store (corrections table),
    pairs them with email text from the email store, and trains a classifier
    on the assembled dataset.

    Usage:
        retrainer = Retrainer(feedback_store=feedback, email_store=store)
        training_data = retrainer.collect_training_data(min_examples_per_category=8)
        result = retrainer.train_classifier(classifier, min_examples_per_category=8)
    """

    def __init__(
        self,
        feedback_store: EmailFeedbackStore,
        email_store: EmailStore,
    ) -> None:
        """
        Initialize the retrainer.

        Args:
            feedback_store: EmailFeedbackStore for reading corrections.
            email_store: EmailStore for fetching email text.
        """
        self._feedback_store = feedback_store
        self._email_store = email_store

    def collect_training_data(
        self,
        min_examples_per_category: int = 8,
    ) -> list[tuple[str, str]]:
        """
        Collect training data from corrections, paired with email text.

        Each correction provides a (email_text, corrected_category) pair.
        Categories with fewer than min_examples_per_category corrections
        are excluded from the training set.

        Args:
            min_examples_per_category: Minimum number of corrections needed
                for a category to be included. Default 8.

        Returns:
            List of (text, label) tuples suitable for classifier training.
        """
        corrections = self._feedback_store.get_corrections()

        if not corrections:
            logger.info("No corrections available for training")
            return []

        # Group corrections by new_category (the correct label)
        corrections_by_category: dict[str, list[str]] = defaultdict(list)
        for correction in corrections:
            corrections_by_category[correction.new_category].append(correction.email_id)

        # Filter categories with insufficient examples
        training_data: list[tuple[str, str]] = []
        skipped_categories: list[str] = []

        for category, email_ids in corrections_by_category.items():
            if len(email_ids) < min_examples_per_category:
                skipped_categories.append(category)
                logger.debug(
                    "Skipping category '%s': only %d corrections (need %d)",
                    category,
                    len(email_ids),
                    min_examples_per_category,
                )
                continue

            # Fetch email text for each correction
            for email_id in email_ids:
                email = self._email_store.get(email_id)
                if email is None:
                    logger.warning(
                        "Email %s referenced in correction but not found in store; skipping",
                        email_id,
                    )
                    continue

                text = f"{email.subject} {email.body_text}"
                training_data.append((text, category))

        if skipped_categories:
            logger.info(
                "Skipped %d categories with insufficient corrections: %s",
                len(skipped_categories),
                ", ".join(skipped_categories),
            )

        logger.info(
            "Collected %d training examples across %d categories",
            len(training_data),
            len({label for _, label in training_data}),
        )

        return training_data

    def train_classifier(
        self,
        classifier: SetFitClassifier,
        min_examples_per_category: int = 8,
    ) -> TrainResult:
        """
        Collect training data and train the provided classifier.

        Args:
            classifier: SetFitClassifier to train.
            min_examples_per_category: Minimum corrections per category.

        Returns:
            TrainResult with training outcome details.
        """
        training_data = self.collect_training_data(
            min_examples_per_category=min_examples_per_category
        )

        if not training_data:
            return TrainResult(
                success=False,
                total_examples=0,
                categories_trained=0,
                error_message="No training data available (insufficient corrections)",
            )

        categories = {label for _, label in training_data}

        try:
            classifier.train(training_data)
        except Exception as e:
            logger.error("Training failed: %s", e, exc_info=True)
            return TrainResult(
                success=False,
                total_examples=len(training_data),
                categories_trained=0,
                error_message=str(e),
            )

        # Determine skipped categories
        all_corrections = self._feedback_store.get_corrections()
        all_categories = {c.new_category for c in all_corrections}
        skipped = sorted(all_categories - categories)

        return TrainResult(
            success=True,
            total_examples=len(training_data),
            categories_trained=len(categories),
            categories_skipped=skipped,
        )


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "Retrainer",
    "TrainResult",
]
