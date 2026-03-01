"""Uncertainty sampling for email classification feedback loop (Phase 5, Item 5.3).

Identifies the lowest-confidence classifications from a batch for user review,
and flags emails where the rule engine and LLM classifier disagree. These two
signals — low confidence and classifier disagreement — are the most valuable
emails to surface for human review in an active learning loop.

Classes:
    UncertaintySampler: Selects uncertain and disagreement emails for review.
"""

from __future__ import annotations

import logging

from src.models.categorization import EmailCategorization

logger = logging.getLogger(__name__)


class UncertaintySampler:
    """Selects uncertain classifications and classifier disagreements for review.

    Two sampling strategies:
    - **Uncertainty sampling**: Sort classifications by confidence ascending,
      return the N least confident. These are the emails where the classifier
      is least sure and human feedback will be most valuable.
    - **Disagreement sampling**: Find emails where the rule engine and LLM
      classifier assign different categories. Sort by confidence gap descending
      so the most divergent disagreements surface first.

    Args:
        default_n: Default number of uncertain items to return when n is not
            specified in get_uncertain(). Defaults to 10.
    """

    def __init__(self, default_n: int = 10) -> None:
        self.default_n = default_n

    def get_uncertain(
        self,
        categorizations: list[EmailCategorization],
        n: int | None = None,
    ) -> list[EmailCategorization]:
        """Return the N least confident classifications for review.

        Filters out uncategorized emails (confidence=0.0, category=Uncategorized)
        since those already need review by definition. Sorts by confidence ascending
        and returns the first N items.

        Args:
            categorizations: List of email categorizations from a classification run.
            n: Number of uncertain items to return. If None, uses default_n.
                If n <= 0, returns empty list.

        Returns:
            List of EmailCategorization sorted by confidence ascending (least
            confident first), with at most n items.
        """
        if n is None:
            n = self.default_n
        if n <= 0:
            return []

        # Filter out uncategorized (they already need review)
        categorized = [c for c in categorizations if not c.is_uncategorized]

        if not categorized:
            return []

        # Sort by confidence ascending (stable sort preserves input order on ties)
        sorted_cats = sorted(
            categorized,
            key=lambda c: c.primary_category.confidence,
        )

        result = sorted_cats[:n]
        logger.debug(
            "Uncertainty sampling: selected %d of %d categorized emails (n=%d)",
            len(result),
            len(categorized),
            n,
        )
        return result

    def get_disagreements(
        self,
        rule_results: list[EmailCategorization],
        llm_results: list[EmailCategorization],
    ) -> list[tuple[EmailCategorization, EmailCategorization]]:
        """Find emails where rule engine and LLM classifier disagree.

        Matches results by email_id. For matched pairs where the primary
        category differs, returns (rule_result, llm_result) tuples sorted
        by confidence gap descending (largest disagreements first).

        Emails present in only one result set are ignored — disagreement
        detection requires both classifiers to have produced a result.

        Args:
            rule_results: Categorizations from the rule engine.
            llm_results: Categorizations from the LLM classifier.

        Returns:
            List of (rule_categorization, llm_categorization) tuples for
            disagreeing pairs, sorted by absolute confidence gap descending.
        """
        if not rule_results or not llm_results:
            return []

        # Index LLM results by email_id for O(1) lookup
        llm_by_id: dict[str, EmailCategorization] = {cat.email_id: cat for cat in llm_results}

        disagreements: list[tuple[EmailCategorization, EmailCategorization]] = []

        for rule_cat in rule_results:
            llm_cat = llm_by_id.get(rule_cat.email_id)
            if llm_cat is None:
                continue

            rule_category = rule_cat.primary_category.category_name
            llm_category = llm_cat.primary_category.category_name

            if rule_category != llm_category:
                disagreements.append((rule_cat, llm_cat))

        # Sort by confidence gap descending (stable sort)
        disagreements.sort(
            key=lambda pair: abs(
                pair[0].primary_category.confidence - pair[1].primary_category.confidence
            ),
            reverse=True,
        )

        logger.debug(
            "Disagreement sampling: found %d disagreements from %d matched pairs",
            len(disagreements),
            min(len(rule_results), len(llm_results)),
        )
        return disagreements


__all__ = ["UncertaintySampler"]
