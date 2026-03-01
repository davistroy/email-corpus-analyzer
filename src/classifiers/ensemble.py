"""
Ensemble classifier that chains multiple classifiers in priority order.

Phase 6, Work Item 6.2: Implements EnsembleClassifier(BaseClassifier) that tries
classifiers in order. Default chain: rules -> SetFit -> LLM. Each classifier is
attempted in sequence; if its confidence exceeds the configured threshold, that
result is used immediately. If all classifiers are below threshold, the highest-
confidence result is returned as a fallback.

Design decisions:
- Each classifier in the chain has its own confidence threshold, allowing the
  ensemble to demand higher certainty from cheaper classifiers (rules) and
  accept lower certainty from expensive ones (LLM).
- Failed classifiers are gracefully skipped with a logged warning, not surfaced
  as errors. Only when ALL classifiers fail does the ensemble raise.
- Usage statistics (attempted, selected, below_threshold, errors) are tracked
  per-classifier for accuracy monitoring and cost optimization.
- The result source field encodes both "ensemble" and the winning classifier's
  name so downstream consumers can audit which model produced each result.
"""

from __future__ import annotations

import logging

from src.classifiers.base import (
    BaseClassifier,
    ClassificationContext,
    ClassificationResult,
    ClassifierCapability,
)
from src.exceptions import ClassificationError
from src.models.email import Email

logger = logging.getLogger(__name__)


class _ClassifierStats:
    """Mutable usage statistics for a single classifier in the chain."""

    __slots__ = ("attempted", "selected", "below_threshold", "errors")

    def __init__(self) -> None:
        self.attempted: int = 0
        self.selected: int = 0
        self.below_threshold: int = 0
        self.errors: int = 0

    def to_dict(self) -> dict[str, int]:
        """Return stats as a plain dict."""
        return {
            "attempted": self.attempted,
            "selected": self.selected,
            "below_threshold": self.below_threshold,
            "errors": self.errors,
        }

    def reset(self) -> None:
        """Reset all counters to zero."""
        self.attempted = 0
        self.selected = 0
        self.below_threshold = 0
        self.errors = 0


class EnsembleClassifier(BaseClassifier):
    """
    Email classifier that chains multiple classifiers in priority order.

    Tries each classifier in sequence. The first classifier whose confidence
    exceeds its configured threshold is selected. If no classifier exceeds
    its threshold, the result with the highest confidence is returned as a
    fallback. Tracks per-classifier usage statistics for monitoring.

    Usage::

        from src.classifiers.ensemble import EnsembleClassifier

        chain = [
            (rule_classifier, 0.8),    # High threshold: rules must be confident
            (setfit_classifier, 0.6),   # Medium threshold for fine-tuned model
            (llm_classifier, 0.4),      # Low threshold: LLM is the fallback
        ]
        ensemble = EnsembleClassifier(chain)
        result = ensemble.classify(email, categories)

        # Check which classifiers are being used
        stats = ensemble.get_usage_stats()
        hit_rates = ensemble.get_hit_rates()
    """

    def __init__(
        self,
        chain: list[tuple[BaseClassifier, float]],
    ) -> None:
        """
        Initialize the ensemble classifier.

        Args:
            chain: Ordered list of (classifier, confidence_threshold) tuples.
                   Classifiers are tried in the order provided. The first
                   classifier whose result meets or exceeds its threshold wins.

        Raises:
            ValueError: If chain is empty.
        """
        if not chain:
            raise ValueError("EnsembleClassifier requires at least one classifier in the chain")

        self._chain: list[tuple[BaseClassifier, float]] = chain
        self._stats: dict[str, _ClassifierStats] = {}
        self._total_classifications: int = 0

        # Initialize stats for each classifier
        for classifier, _ in chain:
            self._stats[classifier.name] = _ClassifierStats()

    # -------------------------------------------------------------------------
    # BaseClassifier contract
    # -------------------------------------------------------------------------

    @property
    def name(self) -> str:
        """Human-readable classifier name for logging."""
        return "Ensemble Classifier"

    @property
    def capabilities(self) -> set[ClassifierCapability]:
        """Union of all member classifier capabilities."""
        caps: set[ClassifierCapability] = set()
        for classifier, _ in self._chain:
            caps.update(classifier.capabilities)
        return caps

    def classify(
        self,
        email: Email,
        categories: list[str],
        context: ClassificationContext | None = None,
    ) -> ClassificationResult:
        """
        Classify an email by trying classifiers in priority order.

        Each classifier is tried in sequence:
        1. If the classifier succeeds and confidence >= threshold, use it.
        2. If the classifier succeeds but confidence < threshold, record it
           as a fallback candidate.
        3. If the classifier raises an exception, log and skip it.

        If no classifier exceeds its threshold, the highest-confidence
        fallback result is returned. If all classifiers fail (raise), a
        ClassificationError is raised.

        Args:
            email: The email to classify.
            categories: List of category names to choose from.
            context: Optional classification context passed to each classifier.

        Returns:
            ClassificationResult from the winning classifier.

        Raises:
            ClassificationError: If all classifiers in the chain fail with errors.
        """
        self._total_classifications += 1

        # Collect fallback results from classifiers that returned but were
        # below their threshold. Track position for tie-breaking.
        fallback_results: list[tuple[int, ClassificationResult, str]] = []
        errors: list[tuple[str, str]] = []

        for idx, (classifier, threshold) in enumerate(self._chain):
            stats = self._stats[classifier.name]
            stats.attempted += 1

            try:
                result = classifier.classify(email, categories, context=context)
            except Exception as e:
                stats.errors += 1
                errors.append((classifier.name, str(e)))
                logger.warning(
                    "Ensemble: classifier '%s' failed for email %s: %s",
                    classifier.name,
                    email.id,
                    e,
                )
                continue

            if result.confidence >= threshold:
                # Winner — meets the threshold
                stats.selected += 1
                logger.debug(
                    "Ensemble: classifier '%s' selected for email %s "
                    "(confidence=%.3f >= threshold=%.3f)",
                    classifier.name,
                    email.id,
                    result.confidence,
                    threshold,
                )
                return self._wrap_result(result, classifier.name)

            # Below threshold — record as fallback candidate
            stats.below_threshold += 1
            fallback_results.append((idx, result, classifier.name))
            logger.debug(
                "Ensemble: classifier '%s' below threshold for email %s "
                "(confidence=%.3f < threshold=%.3f)",
                classifier.name,
                email.id,
                result.confidence,
                threshold,
            )

        # No classifier exceeded its threshold. Use the highest-confidence fallback.
        if fallback_results:
            # Sort by confidence descending, then by chain position ascending (for tie-breaking)
            fallback_results.sort(key=lambda x: (-x[1].confidence, x[0]))
            _, best_result, best_name = fallback_results[0]

            # Record the fallback winner as selected
            self._stats[best_name].selected += 1

            logger.info(
                "Ensemble: no classifier met threshold for email %s. "
                "Using fallback '%s' (confidence=%.3f)",
                email.id,
                best_name,
                best_result.confidence,
            )
            return self._wrap_result(best_result, best_name, is_fallback=True)

        # All classifiers failed with errors — nothing to fall back to
        error_summary = "; ".join(f"{name}: {err}" for name, err in errors)
        raise ClassificationError(
            f"All classifiers failed for email {email.id}: {error_summary}",
            recovery_hint=(
                "Check that at least one classifier in the ensemble chain is operational. "
                "Use --verbose for detailed error information."
            ),
            context={
                "email_id": email.id,
                "errors": dict(errors),
                "chain_size": len(self._chain),
            },
        )

    # -------------------------------------------------------------------------
    # Statistics
    # -------------------------------------------------------------------------

    def get_usage_stats(self) -> dict[str, dict[str, int]]:
        """
        Get per-classifier usage statistics.

        Returns:
            Dict mapping classifier name to stats dict with keys:
            - attempted: Number of times this classifier was called
            - selected: Number of times this classifier produced the final result
            - below_threshold: Number of times it returned below its threshold
            - errors: Number of times it raised an exception
        """
        return {name: stats.to_dict() for name, stats in self._stats.items()}

    def get_hit_rates(self) -> dict[str, float]:
        """
        Get per-classifier selection rate (hit rate).

        The hit rate is the fraction of total ensemble classifications where
        this classifier was selected as the winner.

        Returns:
            Dict mapping classifier name to hit rate (0.0 to 1.0).
            Returns 0.0 for all classifiers if no classifications have been made.
        """
        if self._total_classifications == 0:
            return dict.fromkeys(self._stats, 0.0)

        return {
            name: stats.selected / self._total_classifications
            for name, stats in self._stats.items()
        }

    def reset_stats(self) -> None:
        """Reset all usage statistics to zero."""
        self._total_classifications = 0
        for stats in self._stats.values():
            stats.reset()

    # -------------------------------------------------------------------------
    # Internal
    # -------------------------------------------------------------------------

    def _wrap_result(
        self,
        result: ClassificationResult,
        classifier_name: str,
        is_fallback: bool = False,
    ) -> ClassificationResult:
        """
        Wrap a classifier result with ensemble metadata.

        Updates the source field to include "ensemble:" prefix and the
        winning classifier name, and augments reasoning with ensemble info.

        Args:
            result: The raw result from the winning classifier.
            classifier_name: Name of the classifier that produced this result.
            is_fallback: Whether this result was a fallback (below threshold).

        Returns:
            A new ClassificationResult with ensemble metadata.
        """
        source = f"ensemble:{classifier_name}:{result.source}"
        mode = "fallback" if is_fallback else "threshold"
        reasoning_prefix = f"[Ensemble: {classifier_name} ({mode})]"

        reasoning = result.reasoning
        reasoning = f"{reasoning_prefix} {reasoning}" if reasoning else reasoning_prefix

        return ClassificationResult(
            category_name=result.category_name,
            confidence=result.confidence,
            source=source,
            reasoning=reasoning,
        )


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "EnsembleClassifier",
]
