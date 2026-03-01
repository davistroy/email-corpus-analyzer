"""
Email categorizer for applying category rules to individual emails (Phase 4, Item 4.2).

Provides:
- EmailCategorizer.categorize_email(): Categorize a single email using a RuleSet
- EmailCategorizer.categorize_corpus(): Batch categorize an entire corpus with progress

Primary category is the highest-priority matching rule's action target.
Secondary categories are all other matching rule action targets (deduplicated).
Confidence is derived from rule priority, normalized to 0-1 range.
Uncategorized emails (no matching rules) use the EmailCategorization.uncategorized() factory.

Phase 1, Item 1.3: Hybrid classification support. When an optional BaseClassifier
is provided, it serves as a fallback for emails that no rules match. Source tracking
distinguishes rule-based ("rule:<rule_id>") from classifier-based ("classifier:<name>")
assignments.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from src.classifiers.base import BaseClassifier
from src.models.categorization import (
    CategorizationReport,
    CategoryAssignment,
    EmailCategorization,
)
from src.models.corpus import Corpus
from src.models.email import Email
from src.models.rule import CategoryRule, RuleSet
from src.rules.engine import RuleEngine

logger = logging.getLogger(__name__)

# Baseline confidence for a zero-priority rule that still matched.
# Ensures even priority=0 produces a positive confidence signal.
_MIN_CONFIDENCE = 0.1

# Maximum priority value for normalization.  Priorities above this
# still produce confidence=1.0 (capped), but values below are linearly
# interpolated between _MIN_CONFIDENCE and 1.0.
_MAX_PRIORITY_FOR_NORMALIZATION = 100


def _priority_to_confidence(priority: int) -> float:
    """Convert an integer rule priority to a 0-1 confidence score.

    The mapping is linear between _MIN_CONFIDENCE (at priority 0) and
    1.0 (at _MAX_PRIORITY_FOR_NORMALIZATION), capped at 1.0 for higher
    priorities.

    Args:
        priority: Non-negative integer rule priority.

    Returns:
        Confidence float in range [_MIN_CONFIDENCE, 1.0].
    """
    if priority <= 0:
        return _MIN_CONFIDENCE
    ratio = min(priority / _MAX_PRIORITY_FOR_NORMALIZATION, 1.0)
    return _MIN_CONFIDENCE + ratio * (1.0 - _MIN_CONFIDENCE)


class EmailCategorizer:
    """Categorize emails by evaluating a RuleSet against each message.

    Uses the Phase 3 RuleEngine for condition evaluation.  Produces
    EmailCategorization results with primary/secondary categories and
    confidence scores derived from rule priority.

    Optionally accepts a BaseClassifier for hybrid classification:
    when rules return no match and a classifier is available, the
    classifier is invoked as a fallback.
    """

    def __init__(
        self,
        classifier: BaseClassifier | None = None,
        classifier_threshold: float = 0.6,
    ) -> None:
        """Initialize the categorizer.

        Args:
            classifier: Optional classifier for fallback when rules return
                no match.  When None, unmatched emails are marked uncategorized.
            classifier_threshold: Minimum confidence to accept a classifier
                result.  Results below this threshold are treated as
                uncategorized.  Default is 0.6.
        """
        self._engine = RuleEngine()
        self._classifier = classifier
        self._classifier_threshold = classifier_threshold

    # ------------------------------------------------------------------
    # Single-email categorization
    # ------------------------------------------------------------------

    def categorize_email(
        self,
        email: Email,
        rule_set: RuleSet,
    ) -> EmailCategorization:
        """Categorize a single email against a rule set.

        Rules are evaluated first.  If rules match, the result is returned
        immediately (classifier is NOT invoked).  If no rules match and a
        classifier is available, the classifier is invoked as fallback.
        If the classifier result is below the confidence threshold, or if
        the classifier raises an error, the email is marked uncategorized.

        Args:
            email: The email to categorize.
            rule_set: The set of rules to evaluate.

        Returns:
            An EmailCategorization with primary category (highest-priority
            match), secondary categories (remaining matches, deduplicated),
            and matched rule IDs.  If no rules match and no classifier is
            available (or classifier fails), returns an uncategorized result.
        """
        matched_rules: list[CategoryRule] = self._engine.evaluate_all(rule_set, email)

        if not matched_rules:
            return self._classify_with_fallback(email, rule_set)

        # Build assignments from matched rules, sorted by priority (highest first).
        # evaluate_all already returns sorted by priority descending.
        assignments: list[tuple[CategoryAssignment, str]] = []
        for rule in matched_rules:
            assignment = CategoryAssignment(
                category_name=rule.action.target,
                confidence=_priority_to_confidence(rule.priority),
                source=f"rule:{rule.rule_id}",
            )
            assignments.append((assignment, rule.rule_id))

        # Primary = first (highest-priority) assignment
        primary = assignments[0][0]
        matched_rule_ids = [rule_id for _, rule_id in assignments]

        # Secondary = remaining assignments, but deduplicate by category name.
        # If a secondary has the same category_name as primary, skip it.
        seen_category_names = {primary.category_name}
        secondaries: list[CategoryAssignment] = []
        for assignment, _ in assignments[1:]:
            if assignment.category_name not in seen_category_names:
                seen_category_names.add(assignment.category_name)
                secondaries.append(assignment)

        return EmailCategorization(
            email_id=email.id,
            primary_category=primary,
            secondary_categories=secondaries,
            matched_rules=matched_rule_ids,
        )

    # ------------------------------------------------------------------
    # Classifier fallback
    # ------------------------------------------------------------------

    def _classify_with_fallback(
        self,
        email: Email,
        rule_set: RuleSet,
    ) -> EmailCategorization:
        """Attempt classifier fallback for an email that matched no rules.

        If no classifier is configured, returns uncategorized immediately.
        If the classifier raises any exception, the error is logged and the
        email is returned as uncategorized (resilient error handling per
        constitutional principle #6).

        Args:
            email: The email that matched no rules.
            rule_set: The rule set (used to extract category names for the
                classifier).

        Returns:
            EmailCategorization from the classifier result, or uncategorized.
        """
        if self._classifier is None:
            return EmailCategorization.uncategorized(email_id=email.id)

        # Extract unique category names from rule targets for the classifier
        categories = list({rule.action.target for rule in rule_set.rules})

        try:
            result = self._classifier.classify(email, categories)
        except Exception:
            logger.warning(
                "Classifier '%s' failed for email %s; falling back to uncategorized",
                self._classifier.name,
                email.id,
                exc_info=True,
            )
            return EmailCategorization.uncategorized(email_id=email.id)

        # Check confidence threshold
        if result.confidence < self._classifier_threshold:
            logger.debug(
                "Classifier confidence %.2f below threshold %.2f for email %s; "
                "marking uncategorized",
                result.confidence,
                self._classifier_threshold,
                email.id,
            )
            return EmailCategorization.uncategorized(email_id=email.id)

        # Convert ClassificationResult to EmailCategorization
        primary = CategoryAssignment(
            category_name=result.category_name,
            confidence=result.confidence,
            source=f"classifier:{self._classifier.name}",
        )
        return EmailCategorization(
            email_id=email.id,
            primary_category=primary,
        )

    # ------------------------------------------------------------------
    # Batch corpus categorization
    # ------------------------------------------------------------------

    def categorize_corpus(
        self,
        corpus: Corpus,
        rule_set: RuleSet,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> CategorizationReport:
        """Categorize every email in a corpus using the given rules.

        Args:
            corpus: The email corpus to categorize.
            rule_set: The rules to apply.
            progress_callback: Optional callback invoked as
                ``progress_callback(current_index, total)`` after each
                email is processed (1-indexed).

        Returns:
            A CategorizationReport with aggregate metrics and individual
            categorization results.
        """
        total = len(corpus.emails)
        categorizations: list[EmailCategorization] = []
        categories_used: dict[str, int] = {}
        categorized_count = 0

        for idx, email in enumerate(corpus.emails, start=1):
            result = self.categorize_email(email, rule_set)
            categorizations.append(result)

            if not result.is_uncategorized:
                categorized_count += 1
                cat_name = result.primary_category.category_name
                categories_used[cat_name] = categories_used.get(cat_name, 0) + 1

            if progress_callback is not None:
                progress_callback(idx, total)

        uncategorized_count = total - categorized_count
        coverage = round((categorized_count / total) * 100, 2) if total > 0 else 0.0

        return CategorizationReport(
            total_emails=total,
            categorized_count=categorized_count,
            uncategorized_count=uncategorized_count,
            coverage_percentage=coverage,
            categories_used=categories_used,
            categorizations=categorizations,
            rule_set_version=rule_set.version,
        )
