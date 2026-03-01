"""
Unit tests for Phase 6, Work Item 6.1: SetFitClassifier.

Tests the SetFitClassifier class with:
- BaseClassifier contract compliance (classify, name, capabilities)
- Training with labeled examples via train()
- Model save/load to/from disk
- Confidence scoring via prediction probabilities
- Graceful handling of missing SetFit library
- Edge cases: empty categories, untrained model, insufficient training data

TDD: Tests written before implementation.
All SetFit model interactions are mocked for CI speed.
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.classifiers.base import (
    BaseClassifier,
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
    sender_email: str = "sender@example.com",
    sender_domain: str = "example.com",
) -> Email:
    """Create a minimal test email."""
    return Email(
        id=email_id,
        sender_email=sender_email,
        sender_name="Test Sender",
        sender_domain=sender_domain,
        recipient_email="recipient@example.com",
        subject=subject,
        body_text=body_text,
        received_date=datetime(2024, 1, 15, 10, 30, 0),
        has_attachments=False,
    )


def _make_training_examples(categories: list[str], per_class: int = 10) -> list[tuple[str, str]]:
    """Generate synthetic training examples.

    Returns a list of (text, label) tuples with `per_class` examples for each category.
    """
    examples = []
    templates = {
        "Newsletters": [
            "Weekly digest: top stories this week",
            "Monthly newsletter from our team",
            "Your daily digest is ready",
            "This week in tech - newsletter edition",
            "Subscriber update: new content available",
            "Newsletter: industry trends and insights",
            "Your weekly roundup is here",
            "Community digest - what happened this week",
            "Newsletter special: year in review",
            "Weekly brief: curated stories for you",
        ],
        "Promotions": [
            "50% off sale starts today",
            "Exclusive deal just for you",
            "Limited time offer - don't miss out",
            "Flash sale: everything must go",
            "Your exclusive coupon inside",
            "Big savings event starts now",
            "Special promotion: buy one get one free",
            "Deal alert: prices slashed",
            "Members-only sale this weekend",
            "Clearance event - up to 70% off",
        ],
        "Personal": [
            "Hey, how are you doing?",
            "Catching up - it's been a while",
            "Let's meet for coffee soon",
            "Happy birthday! Hope you have a great day",
            "Thinking of you - sending warm wishes",
            "Family reunion plans for summer",
            "Photos from last weekend's trip",
            "Quick question about the weekend plans",
            "Thanks for dinner last night",
            "Just wanted to say hi",
        ],
        "Work": [
            "Q3 report attached for review",
            "Meeting scheduled for Monday at 2pm",
            "Action items from today's standup",
            "Please review the attached proposal",
            "Project status update - week 12",
            "Budget approval needed by Friday",
            "New hire onboarding checklist",
            "Performance review schedule",
            "Team offsite planning document",
            "Client deliverable deadline reminder",
        ],
    }
    for cat in categories:
        cat_templates = templates.get(cat, [f"{cat} example {i}" for i in range(per_class)])
        for i in range(per_class):
            text = cat_templates[i % len(cat_templates)]
            examples.append((text, cat))
    return examples


def _build_mock_setfit_model():
    """Build a mock SetFitModel that simulates SetFit behavior."""
    mock_model = MagicMock()
    mock_model.predict.return_value = ["Newsletters"]
    mock_model.predict_proba.return_value = np.array([[0.85, 0.05, 0.05, 0.05]])
    mock_model.model_card_data = MagicMock()
    return mock_model


def _build_mock_setfit_module():
    """Build a mock setfit module with SetFitModel and SetFitTrainer."""
    mock_module = MagicMock()
    mock_model = _build_mock_setfit_model()
    mock_module.SetFitModel.from_pretrained.return_value = mock_model
    mock_trainer = MagicMock()
    mock_module.SetFitTrainer.return_value = mock_trainer
    return mock_module, mock_model, mock_trainer


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
def training_examples():
    """Synthetic training examples (10 per class, 4 classes)."""
    return _make_training_examples(["Newsletters", "Promotions", "Personal", "Work"])


@pytest.fixture
def mock_setfit():
    """Patch the setfit module and _SETFIT_AVAILABLE flag for testing.

    Yields (mock_module, mock_model, mock_trainer) and ensures the
    setfit_classifier module sees setfit as available.
    """
    mock_module, mock_model, mock_trainer = _build_mock_setfit_module()

    with (
        patch("src.classifiers.setfit_classifier._SETFIT_AVAILABLE", True),
        patch("src.classifiers.setfit_classifier._setfit_module", mock_module),
    ):
        yield mock_module, mock_model, mock_trainer


# =============================================================================
# Test: SetFitClassifier construction and BaseClassifier contract
# =============================================================================


class TestSetFitClassifierConstruction:
    """Tests for SetFitClassifier initialization and ABC compliance."""

    def test_setfit_classifier_exists(self):
        """SetFitClassifier class can be imported."""
        from src.classifiers.setfit_classifier import SetFitClassifier

        assert SetFitClassifier is not None

    def test_setfit_classifier_is_base_classifier(self):
        """SetFitClassifier inherits from BaseClassifier."""
        from src.classifiers.setfit_classifier import SetFitClassifier

        assert issubclass(SetFitClassifier, BaseClassifier)

    def test_create_setfit_classifier(self, mock_setfit):
        """SetFitClassifier can be instantiated with categories."""
        from src.classifiers.setfit_classifier import SetFitClassifier

        classifier = SetFitClassifier(
            categories=["Newsletters", "Promotions", "Personal", "Work"],
        )
        assert classifier is not None

    def test_name_property(self, mock_setfit):
        """name property returns a human-readable identifier containing 'SetFit'."""
        from src.classifiers.setfit_classifier import SetFitClassifier

        classifier = SetFitClassifier(categories=["Newsletters"])
        assert "SetFit" in classifier.name

    def test_capabilities_include_few_shot_and_fine_tuned(self, mock_setfit):
        """SetFitClassifier reports FEW_SHOT and FINE_TUNED capabilities."""
        from src.classifiers.setfit_classifier import SetFitClassifier

        classifier = SetFitClassifier(categories=["Newsletters"])
        caps = classifier.capabilities
        assert ClassifierCapability.FEW_SHOT in caps
        assert ClassifierCapability.FINE_TUNED in caps

    def test_custom_model_name(self, mock_setfit):
        """SetFitClassifier accepts a custom base model name."""
        from src.classifiers.setfit_classifier import SetFitClassifier

        classifier = SetFitClassifier(
            categories=["Newsletters"],
            model_name="BAAI/bge-small-en-v1.5",
        )
        assert "BAAI/bge-small-en-v1.5" in classifier.name


# =============================================================================
# Test: Training with labeled examples
# =============================================================================


class TestSetFitTraining:
    """Tests for the train() method."""

    def test_train_with_valid_examples(self, mock_setfit, training_examples):
        """train() accepts (text, label) pairs and trains the model."""
        from src.classifiers.setfit_classifier import SetFitClassifier

        classifier = SetFitClassifier(
            categories=["Newsletters", "Promotions", "Personal", "Work"],
        )
        classifier.train(training_examples)
        assert classifier.is_trained

    def test_train_returns_training_stats(self, mock_setfit, training_examples):
        """train() returns a dict with training statistics."""
        from src.classifiers.setfit_classifier import SetFitClassifier

        classifier = SetFitClassifier(
            categories=["Newsletters", "Promotions", "Personal", "Work"],
        )
        stats = classifier.train(training_examples)

        assert isinstance(stats, dict)
        assert "num_examples" in stats
        assert "num_categories" in stats
        assert stats["num_examples"] == 40  # 10 per class * 4 classes
        assert stats["num_categories"] == 4

    def test_train_with_insufficient_examples_raises(self, mock_setfit):
        """train() raises ValueError when too few examples per class."""
        from src.classifiers.setfit_classifier import SetFitClassifier

        classifier = SetFitClassifier(
            categories=["Newsletters", "Promotions"],
            min_examples_per_class=8,
        )
        # Only 2 examples per class
        examples = [
            ("Newsletter subject 1", "Newsletters"),
            ("Newsletter subject 2", "Newsletters"),
            ("Promo subject 1", "Promotions"),
            ("Promo subject 2", "Promotions"),
        ]
        with pytest.raises(ValueError, match="minimum.*examples"):
            classifier.train(examples)

    def test_train_with_empty_examples_raises(self, mock_setfit):
        """train() raises ValueError with empty example list."""
        from src.classifiers.setfit_classifier import SetFitClassifier

        classifier = SetFitClassifier(categories=["Newsletters"])
        with pytest.raises(ValueError, match="empty"):
            classifier.train([])

    def test_train_filters_unknown_categories(self, mock_setfit):
        """train() ignores examples with categories not in the classifier's category list."""
        from src.classifiers.setfit_classifier import SetFitClassifier

        classifier = SetFitClassifier(
            categories=["Newsletters"],
            min_examples_per_class=2,
        )
        examples = [
            ("Newsletter 1", "Newsletters"),
            ("Newsletter 2", "Newsletters"),
            ("Newsletter 3", "Newsletters"),
            ("Spam 1", "Spam"),  # Unknown category, should be filtered
            ("Spam 2", "Spam"),
        ]
        stats = classifier.train(examples)
        assert stats["num_examples"] == 3  # Only Newsletter examples counted
        assert stats["num_categories"] == 1


# =============================================================================
# Test: Classification (classify method)
# =============================================================================


class TestSetFitClassification:
    """Tests for the classify() method per BaseClassifier contract."""

    def test_classify_returns_classification_result(
        self, mock_setfit, training_examples, test_email, categories
    ):
        """classify() returns a ClassificationResult."""
        from src.classifiers.setfit_classifier import SetFitClassifier

        classifier = SetFitClassifier(categories=categories)
        classifier.train(training_examples)

        result = classifier.classify(test_email, categories)
        assert isinstance(result, ClassificationResult)

    def test_classify_result_has_valid_category(
        self, mock_setfit, training_examples, test_email, categories
    ):
        """classify() returns a category from the provided list."""
        _, mock_model, _ = mock_setfit
        mock_model.predict.return_value = ["Newsletters"]
        mock_model.predict_proba.return_value = np.array([[0.85, 0.05, 0.05, 0.05]])

        from src.classifiers.setfit_classifier import SetFitClassifier

        classifier = SetFitClassifier(categories=categories)
        classifier.train(training_examples)

        result = classifier.classify(test_email, categories)
        assert result.category_name in categories

    def test_classify_result_has_valid_confidence(
        self, mock_setfit, training_examples, test_email, categories
    ):
        """classify() returns confidence in [0.0, 1.0]."""
        from src.classifiers.setfit_classifier import SetFitClassifier

        classifier = SetFitClassifier(categories=categories)
        classifier.train(training_examples)

        result = classifier.classify(test_email, categories)
        assert 0.0 <= result.confidence <= 1.0

    def test_classify_result_source_identifies_setfit(
        self, mock_setfit, training_examples, test_email, categories
    ):
        """classify() result source field identifies SetFit classifier."""
        from src.classifiers.setfit_classifier import SetFitClassifier

        classifier = SetFitClassifier(categories=categories)
        classifier.train(training_examples)

        result = classifier.classify(test_email, categories)
        assert "setfit" in result.source

    def test_classify_untrained_model_raises(self, mock_setfit, test_email, categories):
        """classify() raises ClassificationError when model is not trained."""
        from src.classifiers.setfit_classifier import SetFitClassifier
        from src.exceptions import ClassificationError

        classifier = SetFitClassifier(categories=categories)
        # Do NOT train

        with pytest.raises(ClassificationError, match="not.*trained"):
            classifier.classify(test_email, categories)

    def test_classify_with_empty_categories_raises(
        self, mock_setfit, training_examples, test_email
    ):
        """classify() raises ValueError with empty categories list."""
        from src.classifiers.setfit_classifier import SetFitClassifier

        classifier = SetFitClassifier(categories=["Newsletters"])
        classifier.train([("text", "Newsletters")] * 10)

        with pytest.raises(ValueError, match="categories"):
            classifier.classify(test_email, [])

    def test_classify_uses_email_subject_and_body(self, mock_setfit, training_examples, categories):
        """classify() combines subject and body for input text."""
        _, mock_model, _ = mock_setfit

        from src.classifiers.setfit_classifier import SetFitClassifier

        classifier = SetFitClassifier(categories=categories)
        classifier.train(training_examples)

        email = _make_email(subject="Test Subject", body_text="Test body content")
        classifier.classify(email, categories)

        # Check that predict was called with text containing subject and body
        call_args = mock_model.predict.call_args
        input_texts = call_args[0][0]  # first positional arg is the list of texts
        combined_text = " ".join(input_texts) if isinstance(input_texts, list) else str(input_texts)
        assert "Test Subject" in combined_text
        assert "Test body" in combined_text


# =============================================================================
# Test: Confidence scoring
# =============================================================================


class TestConfidenceScoring:
    """Tests that confidence scores are meaningful, not all 1.0 or all 0.5."""

    def test_high_probability_gives_high_confidence(
        self, mock_setfit, training_examples, test_email, categories
    ):
        """When the model is very certain, confidence is high."""
        _, mock_model, _ = mock_setfit
        mock_model.predict.return_value = ["Newsletters"]
        mock_model.predict_proba.return_value = np.array([[0.95, 0.02, 0.02, 0.01]])

        from src.classifiers.setfit_classifier import SetFitClassifier

        classifier = SetFitClassifier(categories=categories)
        classifier.train(training_examples)

        result = classifier.classify(test_email, categories)
        assert result.confidence >= 0.8

    def test_low_probability_gives_low_confidence(
        self, mock_setfit, training_examples, test_email, categories
    ):
        """When the model is uncertain, confidence is low."""
        _, mock_model, _ = mock_setfit
        mock_model.predict.return_value = ["Newsletters"]
        mock_model.predict_proba.return_value = np.array([[0.30, 0.25, 0.25, 0.20]])

        from src.classifiers.setfit_classifier import SetFitClassifier

        classifier = SetFitClassifier(categories=categories)
        classifier.train(training_examples)

        result = classifier.classify(test_email, categories)
        assert result.confidence <= 0.5

    def test_confidence_varies_across_predictions(self, mock_setfit, training_examples, categories):
        """Different emails produce different confidence scores (not all constant)."""
        _, mock_model, _ = mock_setfit

        # Two calls return different probability distributions
        mock_model.predict.side_effect = [["Newsletters"], ["Promotions"]]
        mock_model.predict_proba.side_effect = [
            np.array([[0.90, 0.04, 0.03, 0.03]]),
            np.array([[0.10, 0.55, 0.20, 0.15]]),
        ]

        from src.classifiers.setfit_classifier import SetFitClassifier

        classifier = SetFitClassifier(categories=categories)
        classifier.train(training_examples)

        email1 = _make_email(email_id="e1", subject="Weekly newsletter")
        email2 = _make_email(email_id="e2", subject="Half off sale")

        r1 = classifier.classify(email1, categories)
        r2 = classifier.classify(email2, categories)

        assert r1.confidence != r2.confidence


# =============================================================================
# Test: Model save and load
# =============================================================================


class TestModelSaveLoad:
    """Tests for save_model() and load_model() persistence."""

    def test_save_model_creates_directory(self, mock_setfit, training_examples, tmp_path):
        """save_model() saves the trained model to the specified path."""
        _, mock_model, _ = mock_setfit

        from src.classifiers.setfit_classifier import SetFitClassifier

        classifier = SetFitClassifier(
            categories=["Newsletters", "Promotions", "Personal", "Work"],
        )
        classifier.train(training_examples)

        model_path = tmp_path / "setfit_model"
        classifier.save_model(model_path)

        # The mock model's save_pretrained should have been called
        mock_model.save_pretrained.assert_called_once()

    def test_save_model_stores_metadata(self, mock_setfit, training_examples, tmp_path):
        """save_model() stores metadata (categories, model_name) alongside the model."""
        from src.classifiers.setfit_classifier import SetFitClassifier

        cats = ["Newsletters", "Promotions", "Personal", "Work"]
        classifier = SetFitClassifier(categories=cats)
        classifier.train(training_examples)

        model_path = tmp_path / "setfit_model"
        model_path.mkdir(parents=True, exist_ok=True)
        classifier.save_model(model_path)

        # Metadata file should exist
        meta_path = model_path / "classifier_metadata.json"
        assert meta_path.exists()

        import json

        meta = json.loads(meta_path.read_text())
        assert meta["categories"] == cats
        assert "model_name" in meta

    def test_save_untrained_model_raises(self, mock_setfit, tmp_path):
        """save_model() raises ClassificationError for an untrained model."""
        from src.classifiers.setfit_classifier import SetFitClassifier
        from src.exceptions import ClassificationError

        classifier = SetFitClassifier(categories=["Newsletters"])
        with pytest.raises(ClassificationError, match="not.*trained"):
            classifier.save_model(tmp_path / "model")

    def test_load_model_restores_classifier(self, mock_setfit, tmp_path):
        """load_model() loads a previously saved model and restores classify capability."""
        mock_module, mock_model, _ = mock_setfit

        from src.classifiers.setfit_classifier import SetFitClassifier

        cats = ["Newsletters", "Promotions", "Personal", "Work"]

        # Save metadata manually so load can find it
        model_path = tmp_path / "setfit_model"
        model_path.mkdir(parents=True, exist_ok=True)

        import json

        meta = {
            "categories": cats,
            "model_name": "sentence-transformers/paraphrase-MiniLM-L3-v2",
        }
        (model_path / "classifier_metadata.json").write_text(json.dumps(meta))

        # Load
        classifier = SetFitClassifier.load_model(model_path)
        assert classifier.is_trained
        assert classifier._categories == cats

    def test_load_model_missing_path_raises(self, mock_setfit, tmp_path):
        """load_model() raises ClassificationError when path does not exist."""
        from src.classifiers.setfit_classifier import SetFitClassifier
        from src.exceptions import ClassificationError

        with pytest.raises(ClassificationError, match="not.*exist"):
            SetFitClassifier.load_model(tmp_path / "nonexistent_model")


# =============================================================================
# Test: Missing SetFit library
# =============================================================================


class TestSetFitNotInstalled:
    """Tests for graceful handling when setfit is not installed."""

    def test_instantiation_without_setfit_raises_helpful_error(self):
        """Instantiating SetFitClassifier without setfit raises ImportError with hint."""
        from src.classifiers.setfit_classifier import SetFitClassifier

        with (
            patch("src.classifiers.setfit_classifier._SETFIT_AVAILABLE", False),
            pytest.raises(ImportError, match="setfit"),
        ):
            SetFitClassifier(categories=["Newsletters"])


# =============================================================================
# Test: Batch classification
# =============================================================================


class TestSetFitBatchClassify:
    """Tests for batch classification performance."""

    def test_batch_classify_returns_results_per_email(
        self, mock_setfit, training_examples, categories
    ):
        """batch_classify returns one result per email."""
        from src.classifiers.setfit_classifier import SetFitClassifier

        classifier = SetFitClassifier(categories=categories)
        classifier.train(training_examples)

        emails = [_make_email(f"email_{i}") for i in range(5)]
        results = classifier.batch_classify(emails, categories)

        assert len(results) == 5
        assert all(isinstance(r, ClassificationResult) for r in results)

    def test_batch_classify_empty_list(self, mock_setfit, training_examples, categories):
        """batch_classify with empty list returns empty list."""
        from src.classifiers.setfit_classifier import SetFitClassifier

        classifier = SetFitClassifier(categories=categories)
        classifier.train(training_examples)

        results = classifier.batch_classify([], categories)
        assert results == []


# =============================================================================
# Test: Module exports
# =============================================================================


class TestSetFitExports:
    """Tests that setfit_classifier module exports expected symbols."""

    def test_module_exports_setfit_classifier(self):
        """SetFitClassifier is importable from the module."""
        from src.classifiers.setfit_classifier import SetFitClassifier

        assert SetFitClassifier is not None

    def test_package_init_exports_setfit_classifier(self):
        """SetFitClassifier is exported from src.classifiers package."""
        from src.classifiers import SetFitClassifier

        assert SetFitClassifier is not None
