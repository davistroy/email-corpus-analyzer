"""
Email categorizer for applying category rules to individual emails (Phase 4, Item 4.2).

Provides:
- EmailCategorizer.categorize_email(): Categorize a single email using a RuleSet
- EmailCategorizer.categorize_corpus(): Batch categorize an entire corpus with progress

Primary category is the highest-priority matching rule's action target.
Secondary categories are all other matching rule action targets (deduplicated).
Confidence is derived from rule priority, normalized to 0-1 range.
Uncategorized emails (no matching rules) use the EmailCategorization.uncategorized() factory.
"""

from __future__ import annotations

from collections.abc import Callable

from src.models.categorization import (
    CategorizationReport,
    CategoryAssignment,
    EmailCategorization,
)
from src.models.corpus import Corpus
from src.models.email import Email
from src.models.rule import CategoryRule, RuleSet
from src.rules.engine import RuleEngine

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
    """

    def __init__(self) -> None:
        self._engine = RuleEngine()

    # ------------------------------------------------------------------
    # Single-email categorization
    # ------------------------------------------------------------------

    def categorize_email(
        self,
        email: Email,
        rule_set: RuleSet,
    ) -> EmailCategorization:
        """Categorize a single email against a rule set.

        Args:
            email: The email to categorize.
            rule_set: The set of rules to evaluate.

        Returns:
            An EmailCategorization with primary category (highest-priority
            match), secondary categories (remaining matches, deduplicated),
            and matched rule IDs.  If no rules match, returns an
            uncategorized result.
        """
        matched_rules: list[CategoryRule] = self._engine.evaluate_all(rule_set, email)

        if not matched_rules:
            return EmailCategorization.uncategorized(email_id=email.id)

        # Build assignments from matched rules, sorted by priority (highest first).
        # evaluate_all already returns sorted by priority descending.
        assignments: list[tuple[CategoryAssignment, str]] = []
        for rule in matched_rules:
            assignment = CategoryAssignment(
                category_name=rule.action.target,
                confidence=_priority_to_confidence(rule.priority),
                source=rule.rule_id,
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
