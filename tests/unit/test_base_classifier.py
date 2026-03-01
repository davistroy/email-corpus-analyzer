"""
Unit tests for Phase 1, Work Item 1.1: BaseClassifier ABC and ClassificationResult Model.

Tests the abstract base class for all email classifiers with:
- Abstract method enforcement (classify must be implemented)
- ClassificationResult Pydantic model validation
- ClassifierCapability enum values
- ClassificationContext dataclass
- batch_classify default implementation
"""

from datetime import datetime

import pytest
from pydantic import ValidationError

from src.models.email import Email


def create_test_email(
    email_id: str = "test_001",
    sender_email: str = "sender@example.com",
    sender_domain: str = "example.com",
    subject: str = "Test Subject",
    body_text: str = "Test body content",
    received_date: datetime | None = None,
) -> Email:
    """Factory function to create Email objects for testing."""
    if received_date is None:
        received_date = datetime(2024, 1, 15, 10, 0)
    return Email(
        id=email_id,
        sender_email=sender_email,
        sender_name="Test Sender",
        sender_domain=sender_domain,
        subject=subject,
        body_text=body_text,
        received_date=received_date,
        has_attachments=False,
    )


# ============================================================================
# Test ClassificationResult Pydantic Model
# ============================================================================


class TestClassificationResult:
    """Test cases for ClassificationResult Pydantic model."""

    def test_classification_result_exists(self):
        """Test that ClassificationResult class exists."""
        from src.classifiers.base import ClassificationResult

        assert ClassificationResult is not None

    def test_valid_classification_result(self):
        """Test creating a valid ClassificationResult."""
        from src.classifiers.base import ClassificationResult

        result = ClassificationResult(
            category_name="Newsletters",
            confidence=0.85,
            source="llm:ollama",
            reasoning="Email contains typical newsletter patterns",
        )
        assert result.category_name == "Newsletters"
        assert result.confidence == 0.85
        assert result.source == "llm:ollama"
        assert result.reasoning == "Email contains typical newsletter patterns"

    def test_classification_result_minimal(self):
        """Test ClassificationResult with only required fields."""
        from src.classifiers.base import ClassificationResult

        result = ClassificationResult(
            category_name="Promotions",
            confidence=0.5,
            source="rule:rule_001",
        )
        assert result.category_name == "Promotions"
        assert result.confidence == 0.5
        assert result.source == "rule:rule_001"
        assert result.reasoning is None

    def test_confidence_minimum_zero(self):
        """Test that confidence cannot be below 0.0."""
        from src.classifiers.base import ClassificationResult

        with pytest.raises(ValidationError):
            ClassificationResult(
                category_name="Test",
                confidence=-0.1,
                source="test",
            )

    def test_confidence_maximum_one(self):
        """Test that confidence cannot exceed 1.0."""
        from src.classifiers.base import ClassificationResult

        with pytest.raises(ValidationError):
            ClassificationResult(
                category_name="Test",
                confidence=1.5,
                source="test",
            )

    def test_confidence_boundary_zero(self):
        """Test that confidence can be exactly 0.0."""
        from src.classifiers.base import ClassificationResult

        result = ClassificationResult(
            category_name="Unknown",
            confidence=0.0,
            source="test",
        )
        assert result.confidence == 0.0

    def test_confidence_boundary_one(self):
        """Test that confidence can be exactly 1.0."""
        from src.classifiers.base import ClassificationResult

        result = ClassificationResult(
            category_name="Certain",
            confidence=1.0,
            source="test",
        )
        assert result.confidence == 1.0

    def test_category_name_required(self):
        """Test that category_name is required."""
        from src.classifiers.base import ClassificationResult

        with pytest.raises(ValidationError):
            ClassificationResult(
                confidence=0.5,
                source="test",
            )

    def test_category_name_non_empty(self):
        """Test that category_name cannot be empty."""
        from src.classifiers.base import ClassificationResult

        with pytest.raises(ValidationError):
            ClassificationResult(
                category_name="",
                confidence=0.5,
                source="test",
            )

    def test_source_required(self):
        """Test that source is required."""
        from src.classifiers.base import ClassificationResult

        with pytest.raises(ValidationError):
            ClassificationResult(
                category_name="Test",
                confidence=0.5,
            )

    def test_classification_result_serialization(self):
        """Test that ClassificationResult serializes to dict."""
        from src.classifiers.base import ClassificationResult

        result = ClassificationResult(
            category_name="Newsletters",
            confidence=0.85,
            source="llm:ollama",
            reasoning="Newsletter pattern detected",
        )
        data = result.model_dump()
        assert data["category_name"] == "Newsletters"
        assert data["confidence"] == 0.85
        assert data["source"] == "llm:ollama"
        assert data["reasoning"] == "Newsletter pattern detected"


# ============================================================================
# Test ClassifierCapability Enum
# ============================================================================


class TestClassifierCapability:
    """Test cases for ClassifierCapability enum."""

    def test_classifier_capability_exists(self):
        """Test that ClassifierCapability enum exists."""
        from src.classifiers.base import ClassifierCapability

        assert ClassifierCapability is not None

    def test_zero_shot_capability(self):
        """Test ZERO_SHOT capability value."""
        from src.classifiers.base import ClassifierCapability

        assert ClassifierCapability.ZERO_SHOT == "zero_shot"

    def test_few_shot_capability(self):
        """Test FEW_SHOT capability value."""
        from src.classifiers.base import ClassifierCapability

        assert ClassifierCapability.FEW_SHOT == "few_shot"

    def test_fine_tuned_capability(self):
        """Test FINE_TUNED capability value."""
        from src.classifiers.base import ClassifierCapability

        assert ClassifierCapability.FINE_TUNED == "fine_tuned"

    def test_capability_is_string_enum(self):
        """Test that ClassifierCapability values are strings."""
        from src.classifiers.base import ClassifierCapability

        assert isinstance(ClassifierCapability.ZERO_SHOT, str)
        assert isinstance(ClassifierCapability.FEW_SHOT, str)
        assert isinstance(ClassifierCapability.FINE_TUNED, str)

    def test_all_capabilities(self):
        """Test that all expected capabilities are defined."""
        from src.classifiers.base import ClassifierCapability

        capabilities = list(ClassifierCapability)
        assert len(capabilities) == 3


# ============================================================================
# Test ClassificationContext Dataclass
# ============================================================================


class TestClassificationContext:
    """Test cases for ClassificationContext dataclass."""

    def test_classification_context_exists(self):
        """Test that ClassificationContext exists."""
        from src.classifiers.base import ClassificationContext

        assert ClassificationContext is not None

    def test_classification_context_is_dataclass(self):
        """Test that ClassificationContext is a dataclass."""
        import dataclasses

        from src.classifiers.base import ClassificationContext

        assert dataclasses.is_dataclass(ClassificationContext)

    def test_context_defaults(self):
        """Test ClassificationContext default values."""
        from src.classifiers.base import ClassificationContext

        ctx = ClassificationContext()
        assert ctx.few_shot_examples == []
        assert ctx.category_descriptions == {}
        assert ctx.additional_context == {}

    def test_context_with_few_shot_examples(self):
        """Test ClassificationContext with few-shot examples."""
        from src.classifiers.base import ClassificationContext

        examples = [
            {"email_subject": "50% off sale!", "category": "Promotions"},
            {"email_subject": "Weekly digest", "category": "Newsletters"},
        ]
        ctx = ClassificationContext(few_shot_examples=examples)
        assert len(ctx.few_shot_examples) == 2
        assert ctx.few_shot_examples[0]["category"] == "Promotions"

    def test_context_with_category_descriptions(self):
        """Test ClassificationContext with category descriptions."""
        from src.classifiers.base import ClassificationContext

        descriptions = {
            "Newsletters": "Regular email digests and subscription content",
            "Promotions": "Marketing and sales emails",
        }
        ctx = ClassificationContext(category_descriptions=descriptions)
        assert len(ctx.category_descriptions) == 2
        assert "Newsletters" in ctx.category_descriptions

    def test_context_with_additional_context(self):
        """Test ClassificationContext with additional context."""
        from src.classifiers.base import ClassificationContext

        ctx = ClassificationContext(
            additional_context={"user_email": "user@example.com", "source": "gmail"}
        )
        assert ctx.additional_context["user_email"] == "user@example.com"

    def test_context_fully_populated(self):
        """Test ClassificationContext with all fields populated."""
        from src.classifiers.base import ClassificationContext

        ctx = ClassificationContext(
            few_shot_examples=[{"subject": "test", "category": "Test"}],
            category_descriptions={"Test": "Test category"},
            additional_context={"key": "value"},
        )
        assert len(ctx.few_shot_examples) == 1
        assert len(ctx.category_descriptions) == 1
        assert len(ctx.additional_context) == 1


# ============================================================================
# Test BaseClassifier Abstract Class
# ============================================================================


class TestBaseClassifierAbstract:
    """Test cases for BaseClassifier abstract base class."""

    def test_base_classifier_exists(self):
        """Test that BaseClassifier class exists."""
        from src.classifiers.base import BaseClassifier

        assert BaseClassifier is not None

    def test_base_classifier_is_abstract(self):
        """Test that BaseClassifier cannot be instantiated directly."""
        from src.classifiers.base import BaseClassifier

        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            BaseClassifier()

    def test_base_classifier_has_classify_method(self):
        """Test that BaseClassifier requires classify method."""
        from src.classifiers.base import BaseClassifier

        assert hasattr(BaseClassifier, "classify")

    def test_base_classifier_has_name_property(self):
        """Test that BaseClassifier requires name property."""
        from src.classifiers.base import BaseClassifier

        assert hasattr(BaseClassifier, "name")

    def test_base_classifier_has_capabilities_property(self):
        """Test that BaseClassifier requires capabilities property."""
        from src.classifiers.base import BaseClassifier

        assert hasattr(BaseClassifier, "capabilities")

    def test_base_classifier_has_batch_classify_method(self):
        """Test that BaseClassifier has batch_classify default method."""
        from src.classifiers.base import BaseClassifier

        assert hasattr(BaseClassifier, "batch_classify")


class TestConcreteClassifierImplementation:
    """Test concrete implementations of BaseClassifier."""

    def test_concrete_classifier_must_implement_classify(self):
        """Test that concrete classifier must implement classify method."""
        from src.classifiers.base import BaseClassifier, ClassifierCapability

        class IncompleteClassifier(BaseClassifier):
            @property
            def name(self) -> str:
                return "Incomplete"

            @property
            def capabilities(self) -> set:
                return {ClassifierCapability.ZERO_SHOT}

        with pytest.raises(TypeError):
            IncompleteClassifier()

    def test_concrete_classifier_must_implement_name(self):
        """Test that concrete classifier must implement name property."""
        from src.classifiers.base import (
            BaseClassifier,
            ClassificationResult,
            ClassifierCapability,
        )

        class IncompleteClassifier(BaseClassifier):
            def classify(self, email, categories, context=None):
                return ClassificationResult(category_name="Test", confidence=0.5, source="test")

            @property
            def capabilities(self) -> set:
                return {ClassifierCapability.ZERO_SHOT}

        with pytest.raises(TypeError):
            IncompleteClassifier()

    def test_concrete_classifier_must_implement_capabilities(self):
        """Test that concrete classifier must implement capabilities property."""
        from src.classifiers.base import BaseClassifier, ClassificationResult

        class IncompleteClassifier(BaseClassifier):
            @property
            def name(self) -> str:
                return "Incomplete"

            def classify(self, email, categories, context=None):
                return ClassificationResult(category_name="Test", confidence=0.5, source="test")

        with pytest.raises(TypeError):
            IncompleteClassifier()

    def test_complete_concrete_classifier(self):
        """Test that complete concrete classifier can be instantiated."""
        from src.classifiers.base import (
            BaseClassifier,
            ClassificationResult,
            ClassifierCapability,
        )

        class TestClassifier(BaseClassifier):
            @property
            def name(self) -> str:
                return "Test Classifier"

            @property
            def capabilities(self) -> set[ClassifierCapability]:
                return {ClassifierCapability.ZERO_SHOT}

            def classify(self, email, categories, context=None):
                return ClassificationResult(
                    category_name=categories[0],
                    confidence=0.9,
                    source="test:v1",
                )

        classifier = TestClassifier()
        assert classifier is not None
        assert classifier.name == "Test Classifier"

    def test_classify_returns_classification_result(self):
        """Test that classify returns a ClassificationResult."""
        from src.classifiers.base import (
            BaseClassifier,
            ClassificationResult,
            ClassifierCapability,
        )

        class TestClassifier(BaseClassifier):
            @property
            def name(self) -> str:
                return "Test Classifier"

            @property
            def capabilities(self) -> set[ClassifierCapability]:
                return {ClassifierCapability.ZERO_SHOT}

            def classify(self, email, categories, context=None):
                return ClassificationResult(
                    category_name=categories[0],
                    confidence=0.9,
                    source="test:v1",
                    reasoning="First category chosen for test",
                )

        classifier = TestClassifier()
        email = create_test_email()
        result = classifier.classify(email, ["Newsletters", "Promotions"])

        assert isinstance(result, ClassificationResult)
        assert result.category_name == "Newsletters"
        assert result.confidence == 0.9
        assert result.source == "test:v1"
        assert result.reasoning == "First category chosen for test"

    def test_classify_with_context(self):
        """Test that classify accepts optional ClassificationContext."""
        from src.classifiers.base import (
            BaseClassifier,
            ClassificationContext,
            ClassificationResult,
            ClassifierCapability,
        )

        class ContextAwareClassifier(BaseClassifier):
            @property
            def name(self) -> str:
                return "Context Classifier"

            @property
            def capabilities(self) -> set[ClassifierCapability]:
                return {ClassifierCapability.FEW_SHOT}

            def classify(self, email, categories, context=None):
                # Use context if provided
                if context and context.category_descriptions:
                    reasoning = f"Used {len(context.category_descriptions)} descriptions"
                else:
                    reasoning = "No context"
                return ClassificationResult(
                    category_name=categories[0],
                    confidence=0.8,
                    source="context_test",
                    reasoning=reasoning,
                )

        classifier = ContextAwareClassifier()
        email = create_test_email()
        ctx = ClassificationContext(category_descriptions={"Newsletters": "Regular digests"})
        result = classifier.classify(email, ["Newsletters"], context=ctx)
        assert result.reasoning == "Used 1 descriptions"

    def test_capabilities_returns_set(self):
        """Test that capabilities returns a set of ClassifierCapability."""
        from src.classifiers.base import (
            BaseClassifier,
            ClassificationResult,
            ClassifierCapability,
        )

        class MultiCapClassifier(BaseClassifier):
            @property
            def name(self) -> str:
                return "Multi"

            @property
            def capabilities(self) -> set[ClassifierCapability]:
                return {ClassifierCapability.ZERO_SHOT, ClassifierCapability.FEW_SHOT}

            def classify(self, email, categories, context=None):
                return ClassificationResult(category_name="Test", confidence=0.5, source="test")

        classifier = MultiCapClassifier()
        caps = classifier.capabilities
        assert isinstance(caps, set)
        assert ClassifierCapability.ZERO_SHOT in caps
        assert ClassifierCapability.FEW_SHOT in caps
        assert len(caps) == 2


# ============================================================================
# Test batch_classify Default Implementation
# ============================================================================


class TestBatchClassify:
    """Test cases for batch_classify default implementation."""

    def _make_classifier(self):
        """Create a test classifier for batch tests."""
        from src.classifiers.base import (
            BaseClassifier,
            ClassificationResult,
            ClassifierCapability,
        )

        class CountingClassifier(BaseClassifier):
            def __init__(self):
                self.call_count = 0

            @property
            def name(self) -> str:
                return "Counting Classifier"

            @property
            def capabilities(self) -> set[ClassifierCapability]:
                return {ClassifierCapability.ZERO_SHOT}

            def classify(self, email, categories, context=None):
                self.call_count += 1
                return ClassificationResult(
                    category_name=categories[0],
                    confidence=0.7,
                    source="counting:v1",
                )

        return CountingClassifier()

    def test_batch_classify_returns_list(self):
        """Test that batch_classify returns a list of ClassificationResult."""
        from src.classifiers.base import ClassificationResult

        classifier = self._make_classifier()
        emails = [create_test_email(email_id=f"email_{i}") for i in range(3)]
        categories = ["Newsletters", "Promotions"]

        results = classifier.batch_classify(emails, categories)
        assert isinstance(results, list)
        assert len(results) == 3
        assert all(isinstance(r, ClassificationResult) for r in results)

    def test_batch_classify_calls_classify_for_each_email(self):
        """Test that batch_classify calls classify once per email."""
        classifier = self._make_classifier()
        emails = [create_test_email(email_id=f"email_{i}") for i in range(5)]
        categories = ["Newsletters"]

        classifier.batch_classify(emails, categories)
        assert classifier.call_count == 5

    def test_batch_classify_empty_list(self):
        """Test batch_classify with an empty email list."""
        classifier = self._make_classifier()
        results = classifier.batch_classify([], ["Newsletters"])
        assert results == []
        assert classifier.call_count == 0

    def test_batch_classify_passes_context(self):
        """Test that batch_classify passes context to each classify call."""
        from src.classifiers.base import (
            BaseClassifier,
            ClassificationContext,
            ClassificationResult,
            ClassifierCapability,
        )

        class ContextTracker(BaseClassifier):
            def __init__(self):
                self.contexts_received = []

            @property
            def name(self) -> str:
                return "Context Tracker"

            @property
            def capabilities(self) -> set[ClassifierCapability]:
                return {ClassifierCapability.FEW_SHOT}

            def classify(self, email, categories, context=None):
                self.contexts_received.append(context)
                return ClassificationResult(category_name="Test", confidence=0.5, source="test")

        classifier = ContextTracker()
        emails = [create_test_email(email_id=f"email_{i}") for i in range(2)]
        ctx = ClassificationContext(category_descriptions={"Test": "Test category"})

        classifier.batch_classify(emails, ["Test"], context=ctx)
        assert len(classifier.contexts_received) == 2
        assert all(c is ctx for c in classifier.contexts_received)

    def test_batch_classify_single_email(self):
        """Test batch_classify with a single email."""
        classifier = self._make_classifier()
        emails = [create_test_email()]
        results = classifier.batch_classify(emails, ["Newsletters"])
        assert len(results) == 1
        assert classifier.call_count == 1


# ============================================================================
# Test Module Exports
# ============================================================================


class TestModuleExports:
    """Test that the classifiers package exports expected symbols."""

    def test_base_module_exports(self):
        """Test that base module exports all expected classes."""
        from src.classifiers.base import (
            BaseClassifier,
            ClassificationContext,
            ClassificationResult,
            ClassifierCapability,
        )

        assert BaseClassifier is not None
        assert ClassificationResult is not None
        assert ClassifierCapability is not None
        assert ClassificationContext is not None

    def test_package_init_exports(self):
        """Test that classifiers package __init__ exports public API."""
        from src.classifiers import (
            BaseClassifier,
            ClassificationContext,
            ClassificationResult,
            ClassifierCapability,
        )

        assert BaseClassifier is not None
        assert ClassificationResult is not None
        assert ClassifierCapability is not None
        assert ClassificationContext is not None
