"""
Abstract base class for all email classifiers.

Phase 1, Work Item 1.1: Defines the classifier contract.

BaseClassifier is an ABC with a classify(email, categories) -> ClassificationResult method.
ClassificationResult is a Pydantic model containing category_name, confidence, source, and
optional reasoning. ClassifierCapability enum supports capability discovery (ZERO_SHOT,
FEW_SHOT, FINE_TUNED). ClassificationContext is a dataclass holding few-shot examples,
category descriptions, and additional context for the classifier.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from src.models.email import Email

logger = logging.getLogger(__name__)


# =============================================================================
# Enums
# =============================================================================


class ClassifierCapability(str, Enum):
    """Capability types for classifier discovery.

    Used to determine what kind of classification a classifier supports:
    - ZERO_SHOT: Classify without any training examples (e.g., LLM with descriptions)
    - FEW_SHOT: Classify with a small number of labeled examples
    - FINE_TUNED: Classify using a model fine-tuned on domain data
    """

    ZERO_SHOT = "zero_shot"
    FEW_SHOT = "few_shot"
    FINE_TUNED = "fine_tuned"


# =============================================================================
# Data Models
# =============================================================================


class ClassificationResult(BaseModel):
    """
    Result of classifying a single email.

    Contains the assigned category, confidence score, source identifier
    (which classifier produced this result), and optional reasoning.
    """

    category_name: str = Field(..., min_length=1, description="Name of the assigned category")
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence score for this classification (0-1)"
    )
    source: str = Field(
        ..., min_length=1, description="Classifier identifier (e.g., 'llm:ollama', 'rule:rule_001')"
    )
    reasoning: str | None = Field(
        default=None,
        description="Optional explanation for why this category was chosen",
    )


@dataclass
class ClassificationContext:
    """
    Context provided to a classifier for enhanced classification.

    Holds few-shot examples, category descriptions, and any additional
    context that helps the classifier make better decisions.
    """

    few_shot_examples: list[dict[str, Any]] = field(default_factory=list)
    """List of example classifications, each a dict with at least 'email_subject' and 'category'."""

    category_descriptions: dict[str, str] = field(default_factory=dict)
    """Map of category name to human-readable description."""

    additional_context: dict[str, Any] = field(default_factory=dict)
    """Any extra context (e.g., user_email, source provider)."""


# =============================================================================
# Abstract Base Class
# =============================================================================


class BaseClassifier(ABC):
    """
    Abstract base class for all email classifiers.

    Provides:
    - classify() contract for single-email classification
    - name property for logging/identification
    - capabilities property for capability discovery
    - batch_classify() default implementation that iterates over classify()

    All classifier implementations (LLM, SetFit, ensemble) must inherit
    from this class and implement the abstract methods.
    """

    @abstractmethod
    def classify(
        self,
        email: Email,
        categories: list[str],
        context: ClassificationContext | None = None,
    ) -> ClassificationResult:
        """
        Classify a single email into one of the provided categories.

        Args:
            email: The email to classify
            categories: List of category names to choose from
            context: Optional classification context (few-shot examples,
                     category descriptions, additional context)

        Returns:
            ClassificationResult with category assignment, confidence, and source
        """

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Human-readable classifier name for logging.

        Returns:
            Name string (e.g., "LLM Classifier", "SetFit Classifier")
        """

    @property
    @abstractmethod
    def capabilities(self) -> set[ClassifierCapability]:
        """
        Set of capabilities this classifier supports.

        Returns:
            Set of ClassifierCapability enum values
        """

    def batch_classify(
        self,
        emails: list[Email],
        categories: list[str],
        context: ClassificationContext | None = None,
    ) -> list[ClassificationResult]:
        """
        Classify a batch of emails.

        Default implementation iterates over classify() for each email.
        Subclasses may override for more efficient batch processing.

        Args:
            emails: List of emails to classify
            categories: List of category names to choose from
            context: Optional classification context passed to each classify() call

        Returns:
            List of ClassificationResult, one per email (same order as input)
        """
        results: list[ClassificationResult] = []
        for i, email in enumerate(emails):
            logger.debug(
                "%s: classifying email %d/%d (id=%s)",
                self.name,
                i + 1,
                len(emails),
                email.id,
            )
            result = self.classify(email, categories, context=context)
            results.append(result)
        return results


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "BaseClassifier",
    "ClassificationContext",
    "ClassificationResult",
    "ClassifierCapability",
]
