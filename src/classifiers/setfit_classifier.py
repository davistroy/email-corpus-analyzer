"""
SetFit-based email classifier for few-shot fine-tuning.

Phase 6, Work Item 6.1: Implements SetFitClassifier(BaseClassifier) that uses
the SetFit library for few-shot fine-tuning. SetFit achieves competitive
accuracy with 8-16 examples per class. The classifier loads a pre-trained
sentence-transformer model, accepts a training set of (text, label) pairs,
and classifies new emails. Model is saved locally and loaded on startup.

When the SetFit library is not installed (core install), the classifier
raises an ImportError at instantiation time with a clear installation hint.
Tests mock the setfit module for CI speed.

Design decisions:
- Optional dependency: SetFit is an optional import. If not installed,
  a clear ImportError is raised at __init__.
- Confidence from probabilities: predict_proba() provides per-class
  probability distributions. The max probability gives meaningful
  confidence differentiation.
- Metadata sidecar: save_model() writes classifier_metadata.json alongside
  the SetFit model directory, storing categories and model name for
  load_model() to restore state.
- Training validation: train() enforces a minimum examples-per-class
  threshold (default 8) and filters out examples with unknown categories.
- Source tracking: source field is "setfit:<model_name>".
"""

from __future__ import annotations

import json
import logging
from collections import Counter
from pathlib import Path

from src.classifiers.base import (
    BaseClassifier,
    ClassificationContext,
    ClassificationResult,
    ClassifierCapability,
)
from src.exceptions import ClassificationError
from src.models.email import Email

logger = logging.getLogger(__name__)

# Optional SetFit import — only required when actually using this classifier
try:
    import setfit as _setfit_module  # type: ignore[import-untyped]

    _SETFIT_AVAILABLE = True
except ImportError:
    _setfit_module = None  # type: ignore[assignment]
    _SETFIT_AVAILABLE = False

# Default base model for sentence-transformer backbone
DEFAULT_MODEL_NAME = "sentence-transformers/paraphrase-MiniLM-L3-v2"

# Metadata filename stored alongside the model
METADATA_FILENAME = "classifier_metadata.json"


class SetFitClassifier(BaseClassifier):
    """
    Email classifier using SetFit for few-shot fine-tuning.

    SetFit (Sentence Transformer Fine-Tuning) trains a classifier with very
    few labeled examples by fine-tuning a sentence-transformer backbone on
    contrastive pairs, then training a classification head. It achieves
    competitive accuracy with as few as 8 examples per class.

    Usage::

        from src.classifiers.setfit_classifier import SetFitClassifier

        classifier = SetFitClassifier(
            categories=["Newsletters", "Promotions", "Personal", "Work"],
        )
        training_data = [
            ("Weekly digest: top stories", "Newsletters"),
            ("50% off sale", "Promotions"),
            ...  # at least 8 per category
        ]
        stats = classifier.train(training_data)
        result = classifier.classify(email, ["Newsletters", "Promotions", "Personal", "Work"])

        # Save and load
        classifier.save_model(Path("./models/setfit"))
        loaded = SetFitClassifier.load_model(Path("./models/setfit"))
    """

    def __init__(
        self,
        categories: list[str],
        model_name: str = DEFAULT_MODEL_NAME,
        min_examples_per_class: int = 8,
    ) -> None:
        """
        Initialize the SetFit classifier.

        The SetFit model is NOT loaded at init time -- it is created lazily
        during train() or loaded explicitly via load_model().

        Args:
            categories: List of category names this classifier can assign.
            model_name: Base sentence-transformer model name (or HuggingFace path).
            min_examples_per_class: Minimum training examples required per category
                for train() to proceed.

        Raises:
            ImportError: If the setfit library is not installed.
        """
        if not _SETFIT_AVAILABLE:
            raise ImportError(
                "The setfit library is not installed. Install it with: pip install setfit"
            )

        self._categories = list(categories)
        self._model_name = model_name
        self._min_examples_per_class = min_examples_per_class
        self._model = None  # Set by train() or load_model()
        self._is_trained = False

    # -------------------------------------------------------------------------
    # BaseClassifier contract
    # -------------------------------------------------------------------------

    @property
    def name(self) -> str:
        """Human-readable classifier name for logging."""
        return f"SetFit Classifier ({self._model_name})"

    @property
    def capabilities(self) -> set[ClassifierCapability]:
        """SetFit supports few-shot and fine-tuned classification."""
        return {ClassifierCapability.FEW_SHOT, ClassifierCapability.FINE_TUNED}

    @property
    def is_trained(self) -> bool:
        """Whether the model has been trained or loaded."""
        return self._is_trained

    def classify(
        self,
        email: Email,
        categories: list[str],
        context: ClassificationContext | None = None,
    ) -> ClassificationResult:
        """
        Classify a single email into one of the provided categories.

        Combines the email subject and body into a single text input,
        runs it through the trained SetFit model, and returns the
        prediction with a confidence score derived from predict_proba.

        Args:
            email: The email to classify.
            categories: List of category names to choose from.
            context: Optional classification context (not used by SetFit,
                     but accepted for BaseClassifier contract compliance).

        Returns:
            ClassificationResult with category, confidence, and source.

        Raises:
            ValueError: If categories list is empty.
            ClassificationError: If the model has not been trained.
        """
        if not categories:
            raise ValueError("categories list must not be empty")

        if not self._is_trained or self._model is None:
            raise ClassificationError(
                "SetFit model is not trained. Call train() or load_model() first.",
                recovery_hint=(
                    "Train the model with labeled examples using "
                    "SetFitClassifier.train(examples), or load a saved model "
                    "with SetFitClassifier.load_model(path)."
                ),
            )

        # Combine subject and body for classification input
        input_text = self._prepare_text(email)

        # Get prediction and probability distribution
        try:
            predictions = self._model.predict([input_text])
            probabilities = self._model.predict_proba([input_text])
        except Exception as e:
            raise ClassificationError(
                f"SetFit prediction failed: {e}",
                recovery_hint="Check that the model was trained correctly.",
                context={"email_id": email.id, "error": str(e)},
            ) from e

        # Extract category and confidence
        predicted_category = str(predictions[0])
        confidence = float(probabilities[0].max())

        # Validate predicted category is in the allowed list
        if predicted_category not in categories:
            logger.warning(
                "%s: predicted category '%s' not in allowed categories %s. "
                "Returning with reduced confidence.",
                self.name,
                predicted_category,
                categories,
            )
            confidence = min(confidence, 0.3)

        return ClassificationResult(
            category_name=predicted_category,
            confidence=confidence,
            source=f"setfit:{self._model_name}",
            reasoning=f"SetFit prediction (confidence: {confidence:.3f})",
        )

    # -------------------------------------------------------------------------
    # Training
    # -------------------------------------------------------------------------

    def train(self, examples: list[tuple[str, str]]) -> dict:
        """
        Fine-tune the SetFit model on labeled training examples.

        Filters out examples whose labels are not in self._categories,
        validates that each remaining category meets the minimum example
        count, then trains the model.

        Args:
            examples: List of (text, label) tuples for training.

        Returns:
            Dict with training statistics:
            - num_examples: Total training examples used
            - num_categories: Number of distinct categories in training set
            - examples_per_category: Dict of category -> example count

        Raises:
            ValueError: If examples is empty or if any category has fewer
                than min_examples_per_class examples.
        """
        if not examples:
            raise ValueError("Training examples list is empty. Provide at least one example.")

        # Filter to known categories
        filtered = [(text, label) for text, label in examples if label in self._categories]
        if not filtered:
            raise ValueError(
                f"No training examples match the configured categories: {self._categories}"
            )

        # Count examples per category
        label_counts = Counter(label for _, label in filtered)

        # Check minimum examples per class
        insufficient = {
            cat: count
            for cat, count in label_counts.items()
            if count < self._min_examples_per_class
        }
        if insufficient:
            detail = ", ".join(f"'{cat}': {count}" for cat, count in insufficient.items())
            raise ValueError(
                f"Categories below minimum examples ({self._min_examples_per_class}): "
                f"{detail}. Provide at least {self._min_examples_per_class} examples per "
                f"category, or lower min_examples_per_class."
            )

        # Prepare training data
        texts = [text for text, _ in filtered]
        labels = [label for _, label in filtered]

        logger.info(
            "%s: training on %d examples across %d categories",
            self.name,
            len(filtered),
            len(label_counts),
        )

        # Create and train the SetFit model
        model = _setfit_module.SetFitModel.from_pretrained(self._model_name)

        trainer = _setfit_module.SetFitTrainer(
            model=model,
            train_dataset=self._create_dataset(texts, labels),
        )
        trainer.train()

        self._model = model
        self._is_trained = True

        stats = {
            "num_examples": len(filtered),
            "num_categories": len(label_counts),
            "examples_per_category": dict(label_counts),
        }

        logger.info(
            "%s: training complete. %d examples, %d categories",
            self.name,
            stats["num_examples"],
            stats["num_categories"],
        )

        return stats

    # -------------------------------------------------------------------------
    # Model Persistence
    # -------------------------------------------------------------------------

    def save_model(self, path: Path) -> None:
        """
        Save the trained model and metadata to disk.

        Creates the directory if it does not exist. Saves both the SetFit
        model (via save_pretrained) and a classifier_metadata.json sidecar
        with categories and model name.

        Args:
            path: Directory to save the model into.

        Raises:
            ClassificationError: If the model has not been trained.
        """
        if not self._is_trained or self._model is None:
            raise ClassificationError(
                "Cannot save: SetFit model is not trained.",
                recovery_hint="Train the model first with train().",
            )

        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)

        # Save the SetFit model
        self._model.save_pretrained(str(path))

        # Save metadata sidecar
        metadata = {
            "categories": self._categories,
            "model_name": self._model_name,
        }
        meta_path = path / METADATA_FILENAME
        meta_path.write_text(json.dumps(metadata, indent=2))

        logger.info("%s: model saved to %s", self.name, path)

    @classmethod
    def load_model(cls, path: Path) -> SetFitClassifier:
        """
        Load a previously saved SetFit model from disk.

        Reads the classifier_metadata.json sidecar to restore categories
        and model name, then loads the SetFit model from the directory.

        Args:
            path: Directory containing the saved model.

        Returns:
            A new SetFitClassifier instance with the loaded model.

        Raises:
            ClassificationError: If the path does not exist or metadata is missing.
            ImportError: If the setfit library is not installed.
        """
        if not _SETFIT_AVAILABLE:
            raise ImportError(
                "The setfit library is not installed. Install it with: pip install setfit"
            )

        path = Path(path)
        if not path.exists():
            raise ClassificationError(
                f"Model path does not exist: {path}",
                recovery_hint="Check the model path and ensure the model was saved previously.",
            )

        # Load metadata
        meta_path = path / METADATA_FILENAME
        if not meta_path.exists():
            raise ClassificationError(
                f"Metadata file not found at {meta_path}",
                recovery_hint=(
                    "The model directory is missing classifier_metadata.json. "
                    "Ensure this model was saved with SetFitClassifier.save_model()."
                ),
            )

        metadata = json.loads(meta_path.read_text())
        categories = metadata["categories"]
        model_name = metadata.get("model_name", DEFAULT_MODEL_NAME)

        # Create classifier instance
        classifier = cls(categories=categories, model_name=model_name)

        # Load the SetFit model
        classifier._model = _setfit_module.SetFitModel.from_pretrained(str(path))
        classifier._is_trained = True

        logger.info("SetFit model loaded from %s (%d categories)", path, len(categories))

        return classifier

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    @staticmethod
    def _prepare_text(email: Email) -> str:
        """
        Combine email subject and body into a single text for classification.

        Args:
            email: The email to prepare.

        Returns:
            Combined text string.
        """
        parts = []
        if email.subject:
            parts.append(f"Subject: {email.subject}")
        if email.body_text:
            # Truncate very long bodies to avoid model input limits
            body = email.body_text[:2000]
            parts.append(f"Body: {body}")
        return "\n".join(parts)

    @staticmethod
    def _create_dataset(texts: list[str], labels: list[str]):
        """
        Create a training dataset compatible with SetFitTrainer.

        Uses a simple dict-based structure that SetFitTrainer accepts.

        Args:
            texts: List of training text strings.
            labels: List of corresponding category labels.

        Returns:
            A dataset-like object for SetFitTrainer.
        """
        return {"text": texts, "label": labels}


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "SetFitClassifier",
]
