"""
Conflict resolver for email categorization (Phase 4, Item 4.3).

When multiple rules match a single email, the ConflictResolver determines
which category assignment wins. Three strategies are supported:

- PRIORITY: Highest rule priority value wins (default).
- SPECIFICITY: Rule with the most conditions wins (more conditions = more specific).
- HISTORICAL: Prefer categories the user has previously approved via the decision log.

Strategies can be chained: if the first strategy results in a tie, the next
strategy in the chain breaks the tie. If all strategies tie, the first
candidate in the sorted list is chosen deterministically.
"""

from __future__ import annotations

import math
from enum import Enum

from pydantic import BaseModel, Field

from src.learning.decision_logger import DecisionAction, DecisionLogger
from src.models.categorization import CategoryAssignment
from src.models.email import Email
from src.models.rule import CategoryRule

# =============================================================================
# Enums
# =============================================================================


class ConflictResolution(str, Enum):
    """Strategy for resolving conflicts when multiple rules match an email."""

    PRIORITY = "priority"
    SPECIFICITY = "specificity"
    HISTORICAL = "historical"


# =============================================================================
# Models
# =============================================================================


class ResolutionResult(BaseModel):
    """
    Result of conflict resolution for an email.

    Contains the chosen category assignment, the reason it was chosen,
    which strategy produced the decision, and the alternative candidates
    that were considered but not selected.
    """

    chosen: CategoryAssignment = Field(..., description="The winning category assignment")
    reason: str = Field(
        ..., min_length=1, description="Human-readable explanation of why this category was chosen"
    )
    strategy_used: ConflictResolution = Field(
        ..., description="Which resolution strategy produced this result"
    )
    alternatives: list[CategoryAssignment] = Field(
        default_factory=list,
        description="Other category assignments that were considered but not chosen",
    )


# =============================================================================
# Confidence calculation
# =============================================================================

# Base confidence for a single-condition rule.  Each additional condition
# adds diminishing returns via a logarithmic curve, capping at 1.0.
_BASE_CONFIDENCE = 0.5
_CONFIDENCE_SCALE = 0.25


def _compute_confidence(condition_count: int) -> float:
    """Compute a confidence score based on rule specificity (condition count).

    Uses a logarithmic curve so that:
    - 1 condition  -> ~0.50
    - 2 conditions -> ~0.67
    - 3 conditions -> ~0.77
    - 4 conditions -> ~0.85
    - 5+ conditions approach but never exceed 1.0

    Returns:
        Float between 0.0 and 1.0.
    """
    if condition_count <= 0:
        return 0.0
    raw = _BASE_CONFIDENCE + _CONFIDENCE_SCALE * math.log(condition_count + 1)
    return min(raw, 1.0)


# =============================================================================
# ConflictResolver
# =============================================================================


class ConflictResolver:
    """Resolve conflicts when multiple rules match a single email.

    Parameters
    ----------
    strategy : ConflictResolution, optional
        Single resolution strategy to use (default: PRIORITY).
    strategy_chain : list[ConflictResolution], optional
        Ordered list of strategies. If provided, overrides ``strategy``.
        Each strategy is tried in order; if a strategy produces a clear
        winner (unique best), that winner is returned.  If a strategy
        ties, the next strategy in the chain breaks the tie.
    decision_logger : DecisionLogger, optional
        Required when HISTORICAL is in the strategy or chain.

    Raises
    ------
    ValueError
        If HISTORICAL strategy is requested without a ``decision_logger``.
    """

    def __init__(
        self,
        strategy: ConflictResolution = ConflictResolution.PRIORITY,
        strategy_chain: list[ConflictResolution] | None = None,
        decision_logger: DecisionLogger | None = None,
    ) -> None:
        self._strategy = strategy
        self._chain = strategy_chain or [strategy]
        self._decision_logger = decision_logger

        # Validate that HISTORICAL has a logger
        if ConflictResolution.HISTORICAL in self._chain and decision_logger is None:
            raise ValueError(
                "A DecisionLogger is required when using the HISTORICAL resolution strategy."
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def strategy(self) -> ConflictResolution:
        """Return the primary (first) resolution strategy."""
        return self._chain[0] if self._chain else self._strategy

    def resolve(
        self,
        email: Email,
        matching_rules: list[CategoryRule],
    ) -> ResolutionResult:
        """Determine the best category assignment for an email.

        Parameters
        ----------
        email : Email
            The email being categorized.
        matching_rules : list[CategoryRule]
            Rules that matched this email (from RuleEngine.evaluate_all).
            Must contain at least one rule.

        Returns
        -------
        ResolutionResult
            The chosen category, reason, strategy used, and alternatives.

        Raises
        ------
        ValueError
            If ``matching_rules`` is empty.
        """
        if not matching_rules:
            raise ValueError("At least one matching rule is required for conflict resolution.")

        # Fast path: single rule, no conflict
        if len(matching_rules) == 1:
            rule = matching_rules[0]
            return ResolutionResult(
                chosen=self._assignment_from_rule(rule),
                reason="Only one rule matched — no conflict to resolve.",
                strategy_used=self._chain[0],
                alternatives=[],
            )

        # Run strategy chain
        candidates = list(matching_rules)
        strategy_used = self._chain[0]

        for strat in self._chain:
            ranked = self._apply_strategy(strat, candidates, email)
            strategy_used = strat

            # If strategy produced a clear winner (top differs from second), stop
            if len(ranked) == 1 or self._has_clear_winner(strat, ranked):
                break

            # Tie: narrow candidates to the tied top group, try next strategy
            candidates = self._tied_group(strat, ranked)

        winner = ranked[0]
        losers = ranked[1:]

        # Build alternatives — deduplicate by category name (exclude winner's name)
        winner_name = winner.action.target
        alternatives = []
        seen_names: set[str] = set()
        for rule in losers:
            name = rule.action.target
            if name != winner_name and name not in seen_names:
                seen_names.add(name)
                alternatives.append(self._assignment_from_rule(rule))

        return ResolutionResult(
            chosen=self._assignment_from_rule(winner),
            reason=self._build_reason(strategy_used, winner),
            strategy_used=strategy_used,
            alternatives=alternatives,
        )

    # ------------------------------------------------------------------
    # Strategy implementations
    # ------------------------------------------------------------------

    def _apply_strategy(
        self,
        strategy: ConflictResolution,
        rules: list[CategoryRule],
        email: Email,
    ) -> list[CategoryRule]:
        """Sort rules according to the given strategy (best first)."""
        if strategy == ConflictResolution.PRIORITY:
            return sorted(rules, key=lambda r: r.priority, reverse=True)

        if strategy == ConflictResolution.SPECIFICITY:
            return sorted(rules, key=lambda r: r.condition_count, reverse=True)

        if strategy == ConflictResolution.HISTORICAL:
            scores = self._historical_scores(rules)
            return sorted(rules, key=lambda r: scores.get(r.rule_id, 0.0), reverse=True)

        return list(rules)  # pragma: no cover

    def _has_clear_winner(
        self,
        strategy: ConflictResolution,
        ranked: list[CategoryRule],
    ) -> bool:
        """Return True if the top-ranked rule is strictly better than the second."""
        if len(ranked) < 2:
            return True
        first, second = ranked[0], ranked[1]

        if strategy == ConflictResolution.PRIORITY:
            return first.priority > second.priority

        if strategy == ConflictResolution.SPECIFICITY:
            return first.condition_count > second.condition_count

        if strategy == ConflictResolution.HISTORICAL:
            scores = self._historical_scores(ranked)
            return scores.get(first.rule_id, 0.0) > scores.get(second.rule_id, 0.0)

        return False  # pragma: no cover

    def _tied_group(
        self,
        strategy: ConflictResolution,
        ranked: list[CategoryRule],
    ) -> list[CategoryRule]:
        """Return the subset of ranked rules tied with the top entry."""
        if not ranked:
            return []

        first = ranked[0]

        if strategy == ConflictResolution.PRIORITY:
            return [r for r in ranked if r.priority == first.priority]

        if strategy == ConflictResolution.SPECIFICITY:
            return [r for r in ranked if r.condition_count == first.condition_count]

        if strategy == ConflictResolution.HISTORICAL:
            scores = self._historical_scores(ranked)
            top_score = scores.get(first.rule_id, 0.0)
            return [r for r in ranked if scores.get(r.rule_id, 0.0) == top_score]

        return list(ranked)  # pragma: no cover

    # ------------------------------------------------------------------
    # Historical scoring
    # ------------------------------------------------------------------

    def _historical_scores(self, rules: list[CategoryRule]) -> dict[str, float]:
        """Compute a historical preference score for each rule.

        Scores are based on user decisions from the decision log:
        - ACCEPT / RENAME: +1 per occurrence
        - DELETE: -1 per occurrence
        - SKIP / MERGE: 0 (neutral)

        Higher score means the user historically favoured this category.
        """
        if self._decision_logger is None:
            return {}

        decisions = self._decision_logger.get_decisions()

        # Build score per category name
        name_scores: dict[str, float] = {}
        for d in decisions:
            name = d.category_name
            if d.action == DecisionAction.ACCEPT:
                name_scores[name] = name_scores.get(name, 0.0) + 1.0
            elif d.action == DecisionAction.RENAME:
                # Credit the *new* name (the user chose to keep this category
                # under a better name)
                new_name = d.context.get("new_name", name)
                name_scores[new_name] = name_scores.get(new_name, 0.0) + 1.0
            elif d.action == DecisionAction.DELETE:
                name_scores[name] = name_scores.get(name, 0.0) - 1.0
            # SKIP and MERGE are neutral

        # Map category names back to rule IDs
        rule_scores: dict[str, float] = {}
        for rule in rules:
            target = rule.action.target
            rule_scores[rule.rule_id] = name_scores.get(target, 0.0)

        return rule_scores

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _assignment_from_rule(self, rule: CategoryRule) -> CategoryAssignment:
        """Create a CategoryAssignment from a matched rule."""
        return CategoryAssignment(
            category_name=rule.action.target,
            confidence=_compute_confidence(rule.condition_count),
            source=rule.rule_id,
        )

    @staticmethod
    def _build_reason(strategy: ConflictResolution, winner: CategoryRule) -> str:
        """Build a human-readable reason string."""
        if strategy == ConflictResolution.PRIORITY:
            return (
                f"Priority-based resolution: rule '{winner.name}' "
                f"(priority {winner.priority}) wins."
            )
        if strategy == ConflictResolution.SPECIFICITY:
            return (
                f"Specificity-based resolution: rule '{winner.name}' "
                f"with {winner.condition_count} conditions is the most specific."
            )
        if strategy == ConflictResolution.HISTORICAL:
            return (
                f"Historical resolution: category '{winner.action.target}' "
                f"was previously preferred by the user."
            )
        return f"Resolved via {strategy.value}."  # pragma: no cover
