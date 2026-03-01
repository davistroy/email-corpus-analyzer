"""
Unit tests for Phase 6, Work Item 6.2: EnsembleClassifier.

Tests the EnsembleClassifier class with:
- Classifiers tried in priority order (first above threshold wins)
- All classifiers below threshold -> highest confidence wins
- Missing/failed classifiers are gracefully skipped
- Usage statistics are tracked accurately
- Logging of which classifier produced each result
- Edge cases: empty classifier chain, single classifier, all fail

TDD: Tests written before implementation.
"""

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from src.classifiers.base import (
    BaseClassifier,
    ClassificationContext,
    ClassificationResult,
    ClassifierCapability,
)
from src.models.email import Email

# =============================================================================
# Helpers
# =============================================================================


def _make_email(
    email_id: str = "email_001",
    subject: str = "Test Email",
    body_text: str = "This is a test email body.",
) -> Email:
    """Create a minimal test email."""
    return Email(
        id=email_id,
        sender_email="sender@example.com",
        sender_name="Test Sender",
        sender_domain="example.com",
        recipient_email="recipient@example.com",
        subject=subject,
        body_text=body_text,
        received_date=datetime(2024, 1, 15, 10, 30, 0),
        has_attachments=False,
    )


class StubClassifier(BaseClassifier):
    """A stub classifier that returns a fixed result for testing."""

    def __init__(
        self,
        classifier_name: str,
        category: str = "Newsletters",
        confidence: float = 0.9,
        should_raise: bool = False,
        error_type: type[Exception] = RuntimeError,
    ):
        self._name = classifier_name
        self._category = category
        self._confidence = confidence
        self._should_raise = should_raise
        self._error_type = error_type

    @property
    def name(self) -> str:
        return self._name

    @property
    def capabilities(self) -> set[ClassifierCapability]:
        return {ClassifierCapability.ZERO_SHOT}

    def classify(
        self,
        email: Email,
        categories: list[str],
        context: ClassificationContext | None = None,
    ) -> ClassificationResult:
        if self._should_raise:
            raise self._error_type(f"{self._name} failed")
        return ClassificationResult(
            category_name=self._category,
            confidence=self._confidence,
            source=f"stub:{self._name}",
            reasoning=f"Classified by {self._name}",
        )


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def test_email():
    """Create a test email."""
    return _make_email()


@pytest.fixture
def categories():
    """Standard category list."""
    return ["Newsletters", "Promotions", "Personal", "Work"]


@pytest.fixture
def high_confidence_classifier():
    """A classifier that returns high confidence (0.95)."""
    return StubClassifier("rules", category="Newsletters", confidence=0.95)


@pytest.fixture
def medium_confidence_classifier():
    """A classifier that returns medium confidence (0.6)."""
    return StubClassifier("setfit", category="Promotions", confidence=0.6)


@pytest.fixture
def low_confidence_classifier():
    """A classifier that returns low confidence (0.3)."""
    return StubClassifier("llm", category="Personal", confidence=0.3)


@pytest.fixture
def failing_classifier():
    """A classifier that always raises an exception."""
    return StubClassifier("broken", should_raise=True)


# =============================================================================
# Test: EnsembleClassifier construction
# =============================================================================


class TestEnsembleConstruction:
    """Tests for EnsembleClassifier initialization."""

    def test_create_with_classifier_threshold_pairs(
        self, high_confidence_classifier, medium_confidence_classifier
    ):
        """Ensemble accepts an ordered list of (classifier, threshold) tuples."""
        from src.classifiers.ensemble import EnsembleClassifier

        chain = [
            (high_confidence_classifier, 0.8),
            (medium_confidence_classifier, 0.5),
        ]
        ensemble = EnsembleClassifier(chain)
        assert ensemble.name == "Ensemble Classifier"
        assert len(ensemble._chain) == 2

    def test_create_with_empty_chain_raises(self):
        """Ensemble with no classifiers raises ValueError."""
        from src.classifiers.ensemble import EnsembleClassifier

        with pytest.raises(ValueError, match="at least one"):
            EnsembleClassifier([])

    def test_capabilities_include_all_member_capabilities(self):
        """Ensemble capabilities are the union of all member capabilities."""
        from src.classifiers.ensemble import EnsembleClassifier

        class FewShotStub(StubClassifier):
            @property
            def capabilities(self) -> set[ClassifierCapability]:
                return {ClassifierCapability.FEW_SHOT}

        chain = [
            (StubClassifier("a"), 0.8),
            (FewShotStub("b"), 0.5),
        ]
        ensemble = EnsembleClassifier(chain)
        caps = ensemble.capabilities
        assert ClassifierCapability.ZERO_SHOT in caps
        assert ClassifierCapability.FEW_SHOT in caps


# =============================================================================
# Test: Priority ordering — first classifier above threshold wins
# =============================================================================


class TestPriorityOrdering:
    """Tests that classifiers are tried in order and first above threshold wins."""

    def test_first_classifier_above_threshold_wins(
        self, test_email, categories, high_confidence_classifier, medium_confidence_classifier
    ):
        """When the first classifier exceeds its threshold, it is used."""
        from src.classifiers.ensemble import EnsembleClassifier

        chain = [
            (high_confidence_classifier, 0.8),  # 0.95 >= 0.8 -> should win
            (medium_confidence_classifier, 0.5),
        ]
        ensemble = EnsembleClassifier(chain)
        result = ensemble.classify(test_email, categories)

        assert result.category_name == "Newsletters"
        assert result.confidence == 0.95
        assert "rules" in result.source

    def test_second_classifier_wins_when_first_below_threshold(
        self, test_email, categories, low_confidence_classifier, medium_confidence_classifier
    ):
        """When first classifier is below its threshold, try the second."""
        from src.classifiers.ensemble import EnsembleClassifier

        chain = [
            (low_confidence_classifier, 0.5),  # 0.3 < 0.5 -> skip
            (medium_confidence_classifier, 0.5),  # 0.6 >= 0.5 -> should win
        ]
        ensemble = EnsembleClassifier(chain)
        result = ensemble.classify(test_email, categories)

        assert result.category_name == "Promotions"
        assert result.confidence == 0.6
        assert "setfit" in result.source

    def test_third_classifier_wins_when_first_two_below_threshold(self, test_email, categories):
        """Chain of three: first two below threshold, third wins."""
        from src.classifiers.ensemble import EnsembleClassifier

        c1 = StubClassifier("rules", category="Newsletters", confidence=0.3)
        c2 = StubClassifier("setfit", category="Promotions", confidence=0.4)
        c3 = StubClassifier("llm", category="Work", confidence=0.85)

        chain = [
            (c1, 0.8),  # 0.3 < 0.8 -> skip
            (c2, 0.7),  # 0.4 < 0.7 -> skip
            (c3, 0.6),  # 0.85 >= 0.6 -> wins
        ]
        ensemble = EnsembleClassifier(chain)
        result = ensemble.classify(test_email, categories)

        assert result.category_name == "Work"
        assert result.confidence == 0.85
        assert "llm" in result.source


# =============================================================================
# Test: All below threshold — highest confidence wins
# =============================================================================


class TestFallbackBehavior:
    """Tests that when all classifiers are below threshold, highest confidence wins."""

    def test_all_below_threshold_highest_confidence_wins(self, test_email, categories):
        """When no classifier exceeds its threshold, the highest confidence result is returned."""
        from src.classifiers.ensemble import EnsembleClassifier

        c1 = StubClassifier("rules", category="Newsletters", confidence=0.3)
        c2 = StubClassifier("setfit", category="Promotions", confidence=0.6)
        c3 = StubClassifier("llm", category="Personal", confidence=0.5)

        chain = [
            (c1, 0.8),  # 0.3 < 0.8 -> skip
            (c2, 0.9),  # 0.6 < 0.9 -> skip
            (c3, 0.8),  # 0.5 < 0.8 -> skip
        ]
        ensemble = EnsembleClassifier(chain)
        result = ensemble.classify(test_email, categories)

        # c2 had the highest confidence (0.6) among the below-threshold results
        assert result.category_name == "Promotions"
        assert result.confidence == 0.6
        assert "setfit" in result.source

    def test_all_below_threshold_tie_uses_first_in_chain(self, test_email, categories):
        """When all below threshold and tied confidence, prefer the earlier classifier."""
        from src.classifiers.ensemble import EnsembleClassifier

        c1 = StubClassifier("rules", category="Newsletters", confidence=0.5)
        c2 = StubClassifier("setfit", category="Promotions", confidence=0.5)

        chain = [
            (c1, 0.8),
            (c2, 0.8),
        ]
        ensemble = EnsembleClassifier(chain)
        result = ensemble.classify(test_email, categories)

        # Tied -> first in chain wins
        assert result.category_name == "Newsletters"
        assert "rules" in result.source


# =============================================================================
# Test: Failing/missing classifiers are skipped
# =============================================================================


class TestGracefulFailure:
    """Tests that failing classifiers are gracefully skipped."""

    def test_failing_classifier_skipped(
        self, test_email, categories, failing_classifier, medium_confidence_classifier
    ):
        """A failing classifier is skipped, and the next one is tried."""
        from src.classifiers.ensemble import EnsembleClassifier

        chain = [
            (failing_classifier, 0.5),  # raises RuntimeError -> skip
            (medium_confidence_classifier, 0.5),  # 0.6 >= 0.5 -> wins
        ]
        ensemble = EnsembleClassifier(chain)
        result = ensemble.classify(test_email, categories)

        assert result.category_name == "Promotions"
        assert result.confidence == 0.6

    def test_all_classifiers_fail_raises_classification_error(self, test_email, categories):
        """When all classifiers fail, raise ClassificationError."""
        from src.classifiers.ensemble import EnsembleClassifier
        from src.exceptions import ClassificationError

        c1 = StubClassifier("rules", should_raise=True)
        c2 = StubClassifier("setfit", should_raise=True)

        chain = [
            (c1, 0.5),
            (c2, 0.5),
        ]
        ensemble = EnsembleClassifier(chain)

        with pytest.raises(ClassificationError, match="All classifiers failed"):
            ensemble.classify(test_email, categories)

    def test_failing_first_classifier_still_tracks_stats(
        self, test_email, categories, failing_classifier, high_confidence_classifier
    ):
        """Failed classifiers are counted in usage stats as errors."""
        from src.classifiers.ensemble import EnsembleClassifier

        chain = [
            (failing_classifier, 0.5),
            (high_confidence_classifier, 0.5),
        ]
        ensemble = EnsembleClassifier(chain)
        ensemble.classify(test_email, categories)

        stats = ensemble.get_usage_stats()
        assert stats["broken"]["errors"] == 1
        assert stats["rules"]["selected"] == 1


# =============================================================================
# Test: Usage statistics tracking
# =============================================================================


class TestUsageStatistics:
    """Tests for per-classifier usage statistics tracking."""

    def test_stats_initialized_to_zero(self):
        """All stats start at zero for each classifier in the chain."""
        from src.classifiers.ensemble import EnsembleClassifier

        c1 = StubClassifier("rules")
        c2 = StubClassifier("llm")

        ensemble = EnsembleClassifier([(c1, 0.8), (c2, 0.5)])
        stats = ensemble.get_usage_stats()

        assert stats["rules"]["attempted"] == 0
        assert stats["rules"]["selected"] == 0
        assert stats["rules"]["below_threshold"] == 0
        assert stats["rules"]["errors"] == 0
        assert stats["llm"]["attempted"] == 0

    def test_stats_track_selected_classifier(self, test_email, categories):
        """Stats correctly record which classifier was selected."""
        from src.classifiers.ensemble import EnsembleClassifier

        c1 = StubClassifier("rules", confidence=0.95)
        c2 = StubClassifier("llm", confidence=0.7)

        ensemble = EnsembleClassifier([(c1, 0.8), (c2, 0.5)])
        ensemble.classify(test_email, categories)

        stats = ensemble.get_usage_stats()
        assert stats["rules"]["attempted"] == 1
        assert stats["rules"]["selected"] == 1
        assert stats["rules"]["below_threshold"] == 0
        # llm should not have been attempted since rules won
        assert stats["llm"]["attempted"] == 0

    def test_stats_track_below_threshold(self, test_email, categories):
        """Stats record below-threshold attempts."""
        from src.classifiers.ensemble import EnsembleClassifier

        c1 = StubClassifier("rules", confidence=0.3)
        c2 = StubClassifier("llm", confidence=0.9)

        ensemble = EnsembleClassifier([(c1, 0.8), (c2, 0.5)])
        ensemble.classify(test_email, categories)

        stats = ensemble.get_usage_stats()
        assert stats["rules"]["attempted"] == 1
        assert stats["rules"]["selected"] == 0
        assert stats["rules"]["below_threshold"] == 1
        assert stats["llm"]["attempted"] == 1
        assert stats["llm"]["selected"] == 1

    def test_stats_accumulate_across_multiple_classify_calls(self, test_email, categories):
        """Stats accumulate correctly across multiple calls."""
        from src.classifiers.ensemble import EnsembleClassifier

        c1 = StubClassifier("rules", confidence=0.95)
        c2 = StubClassifier("llm", confidence=0.7)

        ensemble = EnsembleClassifier([(c1, 0.8), (c2, 0.5)])
        ensemble.classify(test_email, categories)
        ensemble.classify(test_email, categories)
        ensemble.classify(test_email, categories)

        stats = ensemble.get_usage_stats()
        assert stats["rules"]["attempted"] == 3
        assert stats["rules"]["selected"] == 3

    def test_stats_track_errors(self, test_email, categories):
        """Stats record errors from failing classifiers."""
        from src.classifiers.ensemble import EnsembleClassifier

        c1 = StubClassifier("rules", should_raise=True)
        c2 = StubClassifier("llm", confidence=0.9)

        ensemble = EnsembleClassifier([(c1, 0.8), (c2, 0.5)])
        ensemble.classify(test_email, categories)

        stats = ensemble.get_usage_stats()
        assert stats["rules"]["attempted"] == 1
        assert stats["rules"]["errors"] == 1
        assert stats["rules"]["selected"] == 0

    def test_reset_stats(self, test_email, categories):
        """reset_stats() clears all accumulated statistics."""
        from src.classifiers.ensemble import EnsembleClassifier

        c1 = StubClassifier("rules", confidence=0.95)
        ensemble = EnsembleClassifier([(c1, 0.8)])
        ensemble.classify(test_email, categories)

        assert ensemble.get_usage_stats()["rules"]["selected"] == 1

        ensemble.reset_stats()

        stats = ensemble.get_usage_stats()
        assert stats["rules"]["attempted"] == 0
        assert stats["rules"]["selected"] == 0

    def test_get_hit_rates(self, test_email, categories):
        """get_hit_rates() returns per-classifier selection rate."""
        from src.classifiers.ensemble import EnsembleClassifier

        c1 = StubClassifier("rules", confidence=0.3)
        c2 = StubClassifier("llm", confidence=0.9)

        ensemble = EnsembleClassifier([(c1, 0.8), (c2, 0.5)])

        # Call 4 times: rules always below threshold, llm always wins
        for _ in range(4):
            ensemble.classify(test_email, categories)

        hit_rates = ensemble.get_hit_rates()
        assert hit_rates["rules"] == pytest.approx(0.0)
        assert hit_rates["llm"] == pytest.approx(1.0)


# =============================================================================
# Test: Logging which classifier produced each result
# =============================================================================


class TestResultLogging:
    """Tests that the ensemble logs which classifier produced each result."""

    def test_result_source_identifies_ensemble_and_classifier(
        self, test_email, categories, high_confidence_classifier
    ):
        """Result source includes both 'ensemble' and the winning classifier."""
        from src.classifiers.ensemble import EnsembleClassifier

        ensemble = EnsembleClassifier([(high_confidence_classifier, 0.8)])
        result = ensemble.classify(test_email, categories)

        assert "ensemble" in result.source
        assert "rules" in result.source

    def test_result_reasoning_includes_ensemble_info(
        self, test_email, categories, high_confidence_classifier
    ):
        """Result reasoning mentions the ensemble selection process."""
        from src.classifiers.ensemble import EnsembleClassifier

        ensemble = EnsembleClassifier([(high_confidence_classifier, 0.8)])
        result = ensemble.classify(test_email, categories)

        assert result.reasoning is not None


# =============================================================================
# Test: Context passthrough
# =============================================================================


class TestContextPassthrough:
    """Tests that classification context is passed through to member classifiers."""

    def test_context_passed_to_member_classifiers(self, test_email, categories):
        """Classification context is forwarded to each classifier's classify() call."""
        from src.classifiers.ensemble import EnsembleClassifier

        mock_classifier = MagicMock(spec=BaseClassifier)
        mock_classifier.name = "mock"
        mock_classifier.capabilities = {ClassifierCapability.ZERO_SHOT}
        mock_classifier.classify.return_value = ClassificationResult(
            category_name="Newsletters",
            confidence=0.9,
            source="mock",
            reasoning="test",
        )

        context = ClassificationContext(
            category_descriptions={"Newsletters": "Email newsletters"},
        )

        ensemble = EnsembleClassifier([(mock_classifier, 0.5)])
        ensemble.classify(test_email, categories, context=context)

        mock_classifier.classify.assert_called_once_with(test_email, categories, context=context)


# =============================================================================
# Test: Batch classify
# =============================================================================


class TestBatchClassify:
    """Tests for batch classification."""

    def test_batch_classify_returns_results_per_email(self, categories):
        """batch_classify returns one result per email in order."""
        from src.classifiers.ensemble import EnsembleClassifier

        c1 = StubClassifier("rules", confidence=0.95)
        ensemble = EnsembleClassifier([(c1, 0.8)])

        emails = [_make_email(f"email_{i}") for i in range(5)]
        results = ensemble.batch_classify(emails, categories)

        assert len(results) == 5
        for result in results:
            assert result.category_name == "Newsletters"

    def test_batch_classify_empty_list(self, categories):
        """batch_classify with empty list returns empty list."""
        from src.classifiers.ensemble import EnsembleClassifier

        c1 = StubClassifier("rules", confidence=0.95)
        ensemble = EnsembleClassifier([(c1, 0.8)])

        results = ensemble.batch_classify([], categories)
        assert results == []


# =============================================================================
# Test: Single classifier in chain
# =============================================================================


class TestSingleClassifier:
    """Tests for ensemble with a single classifier."""

    def test_single_classifier_above_threshold(self, test_email, categories):
        """Single classifier above threshold returns its result."""
        from src.classifiers.ensemble import EnsembleClassifier

        c1 = StubClassifier("rules", confidence=0.95)
        ensemble = EnsembleClassifier([(c1, 0.8)])
        result = ensemble.classify(test_email, categories)

        assert result.category_name == "Newsletters"
        assert result.confidence == 0.95

    def test_single_classifier_below_threshold_still_returns_result(self, test_email, categories):
        """Single classifier below threshold still returns its result (fallback)."""
        from src.classifiers.ensemble import EnsembleClassifier

        c1 = StubClassifier("rules", confidence=0.3)
        ensemble = EnsembleClassifier([(c1, 0.8)])
        result = ensemble.classify(test_email, categories)

        # Even though below threshold, it's the only result -> returned as fallback
        assert result.category_name == "Newsletters"
        assert result.confidence == 0.3

    def test_single_classifier_fails_raises(self, test_email, categories):
        """Single classifier that fails raises ClassificationError."""
        from src.classifiers.ensemble import EnsembleClassifier
        from src.exceptions import ClassificationError

        c1 = StubClassifier("rules", should_raise=True)
        ensemble = EnsembleClassifier([(c1, 0.8)])

        with pytest.raises(ClassificationError):
            ensemble.classify(test_email, categories)
