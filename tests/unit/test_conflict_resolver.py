"""
Unit tests for ConflictResolver (Phase 4, Item 4.3).

Tests resolution strategies for emails matching multiple category rules:
- Priority-based resolution (highest priority rule wins)
- Specificity-based resolution (most conditions wins)
- Historical resolution (prefer previously approved categories)
- Strategy chaining (fallback on ties)
- ResolutionResult model validation

TDD: These tests are written first, implementation follows.
"""

from datetime import datetime
from pathlib import Path

import pytest

from src.categorizer.conflict_resolver import (
    ConflictResolution,
    ConflictResolver,
    ResolutionResult,
)
from src.learning.decision_logger import DecisionAction, DecisionLogger
from src.models.categorization import CategoryAssignment
from src.models.email import Email
from src.models.rule import (
    CategoryRule,
    ConditionField,
    ConditionLogic,
    ConditionOperator,
    RuleAction,
    RuleActionType,
    RuleCondition,
)

# =============================================================================
# Helpers
# =============================================================================


def _make_email(**overrides) -> Email:
    """Create a test email with sensible defaults."""
    defaults = {
        "id": "email_001",
        "sender_email": "alice@example.com",
        "sender_name": "Alice Smith",
        "sender_domain": "example.com",
        "recipient_email": "bob@test.org",
        "recipient_name": "Bob Jones",
        "subject": "Weekly Team Update",
        "body_text": "Hi team, here is the weekly status report.",
        "received_date": datetime(2024, 6, 15, 9, 0, 0),
        "has_attachments": False,
    }
    defaults.update(overrides)
    return Email(**defaults)


def _make_condition(
    field: ConditionField = ConditionField.SENDER_DOMAIN,
    operator: ConditionOperator = ConditionOperator.EQUALS,
    value: str = "example.com",
) -> RuleCondition:
    return RuleCondition(field=field, operator=operator, value=value)


def _make_rule(
    rule_id: str = "rule_001",
    name: str = "Test Rule",
    target: str = "Test Category",
    conditions: list[RuleCondition] | None = None,
    logic: ConditionLogic = ConditionLogic.AND,
    priority: int = 0,
    enabled: bool = True,
    category_id: str | None = None,
) -> CategoryRule:
    if conditions is None:
        conditions = [_make_condition()]
    return CategoryRule(
        rule_id=rule_id,
        name=name,
        conditions=conditions,
        action=RuleAction(
            action_type=RuleActionType.CATEGORIZE,
            target=target,
        ),
        logic=logic,
        priority=priority,
        enabled=enabled,
        category_id=category_id,
    )


# =============================================================================
# ConflictResolution Enum Tests
# =============================================================================


class TestConflictResolutionEnum:
    """Test ConflictResolution strategy enum."""

    def test_priority_strategy_exists(self):
        """Priority-based strategy is available."""
        assert ConflictResolution.PRIORITY == "priority"

    def test_specificity_strategy_exists(self):
        """Specificity-based strategy is available."""
        assert ConflictResolution.SPECIFICITY == "specificity"

    def test_historical_strategy_exists(self):
        """Historical strategy is available."""
        assert ConflictResolution.HISTORICAL == "historical"

    def test_all_strategies(self):
        """All three strategies exist."""
        strategies = list(ConflictResolution)
        assert len(strategies) == 3


# =============================================================================
# ResolutionResult Model Tests
# =============================================================================


class TestResolutionResult:
    """Test ResolutionResult model."""

    def test_minimal_result(self):
        """Test creating a result with required fields only."""
        chosen = CategoryAssignment(
            category_name="Newsletters",
            confidence=0.9,
            source="rule_001",
        )
        result = ResolutionResult(
            chosen=chosen,
            reason="Highest priority rule",
            strategy_used=ConflictResolution.PRIORITY,
        )
        assert result.chosen.category_name == "Newsletters"
        assert result.reason == "Highest priority rule"
        assert result.strategy_used == ConflictResolution.PRIORITY
        assert result.alternatives == []

    def test_result_with_alternatives(self):
        """Test result includes alternative candidates."""
        chosen = CategoryAssignment(
            category_name="Newsletters",
            confidence=0.9,
            source="rule_001",
        )
        alt = CategoryAssignment(
            category_name="Marketing",
            confidence=0.85,
            source="rule_002",
        )
        result = ResolutionResult(
            chosen=chosen,
            reason="Highest priority rule",
            strategy_used=ConflictResolution.PRIORITY,
            alternatives=[alt],
        )
        assert len(result.alternatives) == 1
        assert result.alternatives[0].category_name == "Marketing"

    def test_result_serialization_roundtrip(self):
        """Test serialization and deserialization."""
        chosen = CategoryAssignment(
            category_name="Work",
            confidence=0.88,
            source="rule_w1",
        )
        result = ResolutionResult(
            chosen=chosen,
            reason="Most specific rule",
            strategy_used=ConflictResolution.SPECIFICITY,
            alternatives=[],
        )
        data = result.model_dump()
        restored = ResolutionResult.model_validate(data)
        assert restored.chosen.category_name == result.chosen.category_name
        assert restored.reason == result.reason
        assert restored.strategy_used == result.strategy_used


# =============================================================================
# ConflictResolver — Single Rule (No Conflict)
# =============================================================================


class TestConflictResolverSingleRule:
    """Test resolve() with a single matching rule (no conflict to resolve)."""

    def test_single_rule_returns_its_category(self):
        """Single matching rule should be returned directly."""
        resolver = ConflictResolver()
        email = _make_email()
        rules = [_make_rule(target="Newsletters", priority=5)]

        result = resolver.resolve(email, rules)

        assert result.chosen.category_name == "Newsletters"
        assert result.alternatives == []
        assert "single" in result.reason.lower() or "only" in result.reason.lower()

    def test_single_rule_confidence_from_rule_specificity(self):
        """Single rule confidence should reflect condition count."""
        resolver = ConflictResolver()
        email = _make_email()
        rules = [
            _make_rule(
                target="Specific",
                conditions=[
                    _make_condition(
                        ConditionField.SENDER_DOMAIN, ConditionOperator.EQUALS, "example.com"
                    ),
                    _make_condition(ConditionField.SUBJECT, ConditionOperator.CONTAINS, "Update"),
                ],
            )
        ]

        result = resolver.resolve(email, rules)
        assert result.chosen.category_name == "Specific"
        assert result.chosen.confidence > 0.0


# =============================================================================
# ConflictResolver — Priority Strategy
# =============================================================================


class TestPriorityResolution:
    """Test priority-based conflict resolution."""

    def test_highest_priority_wins(self):
        """Rule with highest priority value should win."""
        resolver = ConflictResolver(strategy=ConflictResolution.PRIORITY)
        email = _make_email()
        rules = [
            _make_rule(rule_id="low", target="Low Priority", priority=1),
            _make_rule(rule_id="high", target="High Priority", priority=10),
            _make_rule(rule_id="mid", target="Mid Priority", priority=5),
        ]

        result = resolver.resolve(email, rules)

        assert result.chosen.category_name == "High Priority"
        assert result.strategy_used == ConflictResolution.PRIORITY
        assert "priority" in result.reason.lower()

    def test_alternatives_contain_non_winners(self):
        """Non-winning rules should appear as alternatives."""
        resolver = ConflictResolver(strategy=ConflictResolution.PRIORITY)
        email = _make_email()
        rules = [
            _make_rule(rule_id="r1", target="Cat A", priority=10),
            _make_rule(rule_id="r2", target="Cat B", priority=5),
            _make_rule(rule_id="r3", target="Cat C", priority=1),
        ]

        result = resolver.resolve(email, rules)

        assert len(result.alternatives) == 2
        alt_names = [a.category_name for a in result.alternatives]
        assert "Cat B" in alt_names
        assert "Cat C" in alt_names

    def test_priority_tie_falls_through(self):
        """When priorities are tied, result should still be deterministic."""
        resolver = ConflictResolver(strategy=ConflictResolution.PRIORITY)
        email = _make_email()
        rules = [
            _make_rule(rule_id="r1", target="Cat A", priority=5),
            _make_rule(rule_id="r2", target="Cat B", priority=5),
        ]

        result = resolver.resolve(email, rules)

        # Should pick one deterministically (first in list after sort)
        assert result.chosen.category_name in ("Cat A", "Cat B")

    def test_negative_priority_supported(self):
        """Negative priority values should work correctly."""
        resolver = ConflictResolver(strategy=ConflictResolution.PRIORITY)
        email = _make_email()
        rules = [
            _make_rule(rule_id="r1", target="Negative", priority=-5),
            _make_rule(rule_id="r2", target="Zero", priority=0),
        ]

        result = resolver.resolve(email, rules)
        assert result.chosen.category_name == "Zero"


# =============================================================================
# ConflictResolver — Specificity Strategy
# =============================================================================


class TestSpecificityResolution:
    """Test specificity-based conflict resolution."""

    def test_most_conditions_wins(self):
        """Rule with the most conditions should win."""
        resolver = ConflictResolver(strategy=ConflictResolution.SPECIFICITY)
        email = _make_email()

        few_conditions = _make_rule(
            rule_id="r_few",
            target="General",
            conditions=[_make_condition()],
        )
        many_conditions = _make_rule(
            rule_id="r_many",
            target="Specific",
            conditions=[
                _make_condition(
                    ConditionField.SENDER_DOMAIN, ConditionOperator.EQUALS, "example.com"
                ),
                _make_condition(ConditionField.SUBJECT, ConditionOperator.CONTAINS, "Update"),
                _make_condition(ConditionField.SENDER_NAME, ConditionOperator.CONTAINS, "Alice"),
            ],
        )
        rules = [few_conditions, many_conditions]

        result = resolver.resolve(email, rules)

        assert result.chosen.category_name == "Specific"
        assert result.strategy_used == ConflictResolution.SPECIFICITY
        assert "specific" in result.reason.lower()

    def test_specificity_alternatives(self):
        """Less specific rules appear as alternatives."""
        resolver = ConflictResolver(strategy=ConflictResolution.SPECIFICITY)
        email = _make_email()
        rules = [
            _make_rule(
                rule_id="r1",
                target="One Condition",
                conditions=[_make_condition()],
            ),
            _make_rule(
                rule_id="r2",
                target="Two Conditions",
                conditions=[
                    _make_condition(
                        ConditionField.SENDER_DOMAIN, ConditionOperator.EQUALS, "example.com"
                    ),
                    _make_condition(ConditionField.SUBJECT, ConditionOperator.CONTAINS, "Update"),
                ],
            ),
        ]

        result = resolver.resolve(email, rules)

        assert result.chosen.category_name == "Two Conditions"
        assert len(result.alternatives) == 1
        assert result.alternatives[0].category_name == "One Condition"

    def test_specificity_tie_falls_through(self):
        """Same condition count should still pick deterministically."""
        resolver = ConflictResolver(strategy=ConflictResolution.SPECIFICITY)
        email = _make_email()
        rules = [
            _make_rule(
                rule_id="r1",
                target="Cat A",
                conditions=[_make_condition()],
            ),
            _make_rule(
                rule_id="r2",
                target="Cat B",
                conditions=[
                    _make_condition(ConditionField.SUBJECT, ConditionOperator.CONTAINS, "Update"),
                ],
            ),
        ]

        result = resolver.resolve(email, rules)
        assert result.chosen.category_name in ("Cat A", "Cat B")


# =============================================================================
# ConflictResolver — Historical Strategy
# =============================================================================


class TestHistoricalResolution:
    """Test historical strategy using decision log."""

    def test_previously_accepted_category_wins(self, tmp_path: Path):
        """Category previously accepted by user should be preferred."""
        decisions_file = tmp_path / "decisions.jsonl"
        decision_logger = DecisionLogger(decisions_path=decisions_file)

        # Log that user previously accepted "Newsletters"
        decision_logger.log_decision("Newsletters", DecisionAction.ACCEPT)
        decision_logger.log_decision("Newsletters", DecisionAction.ACCEPT)
        decision_logger.log_decision("Marketing", DecisionAction.SKIP)

        resolver = ConflictResolver(
            strategy=ConflictResolution.HISTORICAL,
            decision_logger=decision_logger,
        )
        email = _make_email()
        rules = [
            _make_rule(rule_id="r1", target="Marketing", priority=10),
            _make_rule(rule_id="r2", target="Newsletters", priority=5),
        ]

        result = resolver.resolve(email, rules)

        assert result.chosen.category_name == "Newsletters"
        assert result.strategy_used == ConflictResolution.HISTORICAL
        assert "historical" in result.reason.lower() or "previous" in result.reason.lower()

    def test_deleted_category_deprioritized(self, tmp_path: Path):
        """Category previously deleted by user should lose to alternatives."""
        decisions_file = tmp_path / "decisions.jsonl"
        decision_logger = DecisionLogger(decisions_path=decisions_file)

        decision_logger.log_decision("Spam", DecisionAction.DELETE)
        decision_logger.log_decision("Spam", DecisionAction.DELETE)
        decision_logger.log_decision("Important", DecisionAction.ACCEPT)

        resolver = ConflictResolver(
            strategy=ConflictResolution.HISTORICAL,
            decision_logger=decision_logger,
        )
        email = _make_email()
        rules = [
            _make_rule(rule_id="r1", target="Spam", priority=10),
            _make_rule(rule_id="r2", target="Important", priority=5),
        ]

        result = resolver.resolve(email, rules)
        assert result.chosen.category_name == "Important"

    def test_no_history_falls_back_to_first(self, tmp_path: Path):
        """With no decision history, should pick first rule deterministically."""
        decisions_file = tmp_path / "decisions.jsonl"
        decision_logger = DecisionLogger(decisions_path=decisions_file)

        resolver = ConflictResolver(
            strategy=ConflictResolution.HISTORICAL,
            decision_logger=decision_logger,
        )
        email = _make_email()
        rules = [
            _make_rule(rule_id="r1", target="Cat A", priority=5),
            _make_rule(rule_id="r2", target="Cat B", priority=10),
        ]

        result = resolver.resolve(email, rules)
        # With no history, should still return a valid result
        assert result.chosen.category_name in ("Cat A", "Cat B")

    def test_historical_without_logger_raises(self):
        """Using HISTORICAL strategy without a DecisionLogger should raise."""
        with pytest.raises(ValueError, match="[Dd]ecision"):
            ConflictResolver(
                strategy=ConflictResolution.HISTORICAL,
                decision_logger=None,
            )

    def test_renamed_category_tracked(self, tmp_path: Path):
        """Renamed categories should be tracked (new name counts as accepted)."""
        decisions_file = tmp_path / "decisions.jsonl"
        decision_logger = DecisionLogger(decisions_path=decisions_file)

        # Rename is a form of acceptance — the new name should count positively
        decision_logger.log_decision(
            "Old Name",
            DecisionAction.RENAME,
            old_name="Old Name",
            new_name="Better Name",
        )

        resolver = ConflictResolver(
            strategy=ConflictResolution.HISTORICAL,
            decision_logger=decision_logger,
        )
        email = _make_email()
        rules = [
            _make_rule(rule_id="r1", target="Better Name", priority=5),
            _make_rule(rule_id="r2", target="Other", priority=5),
        ]

        result = resolver.resolve(email, rules)
        assert result.chosen.category_name == "Better Name"


# =============================================================================
# ConflictResolver — Strategy Chaining
# =============================================================================


class TestStrategyChaining:
    """Test chaining multiple resolution strategies."""

    def test_chain_falls_through_on_tie(self):
        """When first strategy ties, should fall to second strategy."""
        resolver = ConflictResolver(
            strategy_chain=[ConflictResolution.PRIORITY, ConflictResolution.SPECIFICITY],
        )
        email = _make_email()

        # Same priority, but different specificity
        rules = [
            _make_rule(
                rule_id="r1",
                target="General",
                priority=5,
                conditions=[_make_condition()],
            ),
            _make_rule(
                rule_id="r2",
                target="Specific",
                priority=5,
                conditions=[
                    _make_condition(
                        ConditionField.SENDER_DOMAIN, ConditionOperator.EQUALS, "example.com"
                    ),
                    _make_condition(ConditionField.SUBJECT, ConditionOperator.CONTAINS, "Update"),
                    _make_condition(
                        ConditionField.SENDER_NAME, ConditionOperator.CONTAINS, "Alice"
                    ),
                ],
            ),
        ]

        result = resolver.resolve(email, rules)

        assert result.chosen.category_name == "Specific"

    def test_chain_first_strategy_resolves(self):
        """When first strategy resolves cleanly, don't use second."""
        resolver = ConflictResolver(
            strategy_chain=[ConflictResolution.PRIORITY, ConflictResolution.SPECIFICITY],
        )
        email = _make_email()

        rules = [
            _make_rule(
                rule_id="r1",
                target="Low",
                priority=1,
                conditions=[
                    _make_condition(
                        ConditionField.SENDER_DOMAIN, ConditionOperator.EQUALS, "example.com"
                    ),
                    _make_condition(ConditionField.SUBJECT, ConditionOperator.CONTAINS, "Update"),
                ],
            ),
            _make_rule(rule_id="r2", target="High", priority=10, conditions=[_make_condition()]),
        ]

        result = resolver.resolve(email, rules)

        # Priority resolves it — High wins despite fewer conditions
        assert result.chosen.category_name == "High"
        assert result.strategy_used == ConflictResolution.PRIORITY

    def test_three_strategy_chain(self, tmp_path: Path):
        """Three strategies: priority -> specificity -> historical."""
        decisions_file = tmp_path / "decisions.jsonl"
        decision_logger = DecisionLogger(decisions_path=decisions_file)
        decision_logger.log_decision("Historical Winner", DecisionAction.ACCEPT)
        decision_logger.log_decision("Historical Winner", DecisionAction.ACCEPT)

        resolver = ConflictResolver(
            strategy_chain=[
                ConflictResolution.PRIORITY,
                ConflictResolution.SPECIFICITY,
                ConflictResolution.HISTORICAL,
            ],
            decision_logger=decision_logger,
        )
        email = _make_email()

        # Same priority, same condition count, but different history
        rules = [
            _make_rule(
                rule_id="r1",
                target="No History",
                priority=5,
                conditions=[_make_condition()],
            ),
            _make_rule(
                rule_id="r2",
                target="Historical Winner",
                priority=5,
                conditions=[
                    _make_condition(
                        ConditionField.SENDER_DOMAIN, ConditionOperator.EQUALS, "example.com"
                    ),
                ],
            ),
        ]

        result = resolver.resolve(email, rules)
        assert result.chosen.category_name == "Historical Winner"
        assert result.strategy_used == ConflictResolution.HISTORICAL

    def test_chain_requires_historical_logger(self):
        """Chain including HISTORICAL without logger should raise."""
        with pytest.raises(ValueError, match="[Dd]ecision"):
            ConflictResolver(
                strategy_chain=[ConflictResolution.PRIORITY, ConflictResolution.HISTORICAL],
                decision_logger=None,
            )


# =============================================================================
# ConflictResolver — Edge Cases
# =============================================================================


class TestConflictResolverEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_rules_raises(self):
        """Resolve with empty rules list should raise ValueError."""
        resolver = ConflictResolver()
        email = _make_email()

        with pytest.raises(ValueError, match="[Rr]ule"):
            resolver.resolve(email, [])

    def test_default_strategy_is_priority(self):
        """Default strategy should be priority-based."""
        resolver = ConflictResolver()
        assert resolver.strategy == ConflictResolution.PRIORITY

    def test_strategy_param_overrides_default(self):
        """Explicit strategy should override the default."""
        resolver = ConflictResolver(strategy=ConflictResolution.SPECIFICITY)
        assert resolver.strategy == ConflictResolution.SPECIFICITY

    def test_chain_overrides_single_strategy(self):
        """When strategy_chain is provided, it takes precedence over strategy."""
        resolver = ConflictResolver(
            strategy=ConflictResolution.PRIORITY,
            strategy_chain=[ConflictResolution.SPECIFICITY, ConflictResolution.PRIORITY],
        )
        # The chain should be used, not the single strategy
        email = _make_email()
        rules = [
            _make_rule(
                rule_id="r1",
                target="Few Conditions High Priority",
                priority=10,
                conditions=[_make_condition()],
            ),
            _make_rule(
                rule_id="r2",
                target="Many Conditions Low Priority",
                priority=1,
                conditions=[
                    _make_condition(
                        ConditionField.SENDER_DOMAIN, ConditionOperator.EQUALS, "example.com"
                    ),
                    _make_condition(ConditionField.SUBJECT, ConditionOperator.CONTAINS, "Update"),
                    _make_condition(
                        ConditionField.SENDER_NAME, ConditionOperator.CONTAINS, "Alice"
                    ),
                ],
            ),
        ]

        result = resolver.resolve(email, rules)
        # Specificity is first in chain, should win
        assert result.chosen.category_name == "Many Conditions Low Priority"

    def test_rule_source_in_assignment(self):
        """The chosen CategoryAssignment should reference the winning rule_id."""
        resolver = ConflictResolver()
        email = _make_email()
        rules = [_make_rule(rule_id="rule_winner", target="Winner Category", priority=10)]

        result = resolver.resolve(email, rules)
        assert result.chosen.source == "rule_winner"

    def test_confidence_scales_with_specificity(self):
        """Confidence should increase with more conditions matching."""
        resolver = ConflictResolver()
        email = _make_email()

        rules_one = [
            _make_rule(
                rule_id="r1",
                target="One",
                conditions=[_make_condition()],
            )
        ]
        result_one = resolver.resolve(email, rules_one)

        rules_three = [
            _make_rule(
                rule_id="r3",
                target="Three",
                conditions=[
                    _make_condition(
                        ConditionField.SENDER_DOMAIN, ConditionOperator.EQUALS, "example.com"
                    ),
                    _make_condition(ConditionField.SUBJECT, ConditionOperator.CONTAINS, "Update"),
                    _make_condition(
                        ConditionField.SENDER_NAME, ConditionOperator.CONTAINS, "Alice"
                    ),
                ],
            )
        ]
        result_three = resolver.resolve(email, rules_three)

        assert result_three.chosen.confidence > result_one.chosen.confidence

    def test_all_same_target_deduplicates(self):
        """Multiple rules targeting the same category should not produce duplicates."""
        resolver = ConflictResolver()
        email = _make_email()
        rules = [
            _make_rule(rule_id="r1", target="Same Cat", priority=5),
            _make_rule(rule_id="r2", target="Same Cat", priority=10),
        ]

        result = resolver.resolve(email, rules)
        assert result.chosen.category_name == "Same Cat"
        # Alternatives with same name should be filtered or handled
        alt_names = [a.category_name for a in result.alternatives]
        # When multiple rules point to same category, there are no distinct alternatives
        assert "Same Cat" not in alt_names or len(result.alternatives) == 0

    def test_resolve_returns_resolution_result_type(self):
        """Resolve should always return a ResolutionResult instance."""
        resolver = ConflictResolver()
        email = _make_email()
        rules = [_make_rule()]

        result = resolver.resolve(email, rules)
        assert isinstance(result, ResolutionResult)


# =============================================================================
# ConflictResolver — Confidence Calculation
# =============================================================================


class TestConfidenceCalculation:
    """Test that confidence values are calculated sensibly."""

    def test_confidence_between_zero_and_one(self):
        """Confidence should always be in [0, 1]."""
        resolver = ConflictResolver()
        email = _make_email()
        rules = [
            _make_rule(
                rule_id="r1",
                target="Cat",
                conditions=[
                    _make_condition(
                        ConditionField.SENDER_DOMAIN, ConditionOperator.EQUALS, "example.com"
                    ),
                    _make_condition(ConditionField.SUBJECT, ConditionOperator.CONTAINS, "Update"),
                    _make_condition(
                        ConditionField.SENDER_NAME, ConditionOperator.CONTAINS, "Alice"
                    ),
                    _make_condition(ConditionField.BODY, ConditionOperator.CONTAINS, "report"),
                ],
            ),
        ]

        result = resolver.resolve(email, rules)
        assert 0.0 <= result.chosen.confidence <= 1.0

    def test_single_condition_has_base_confidence(self):
        """Single condition should have a reasonable base confidence."""
        resolver = ConflictResolver()
        email = _make_email()
        rules = [_make_rule(conditions=[_make_condition()])]

        result = resolver.resolve(email, rules)
        assert result.chosen.confidence >= 0.3  # At least base level

    def test_alternatives_have_valid_confidence(self):
        """Alternative candidates should also have valid confidence values."""
        resolver = ConflictResolver(strategy=ConflictResolution.PRIORITY)
        email = _make_email()
        rules = [
            _make_rule(rule_id="r1", target="Winner", priority=10),
            _make_rule(rule_id="r2", target="Runner Up", priority=5),
        ]

        result = resolver.resolve(email, rules)
        for alt in result.alternatives:
            assert 0.0 <= alt.confidence <= 1.0
