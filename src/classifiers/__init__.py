"""
Classifier abstractions for email classification.

Phase 1, Work Item 1.1: Provides the BaseClassifier ABC, ClassificationResult model,
ClassifierCapability enum, and ClassificationContext dataclass that all classifier
implementations must use.

Phase 2, Work Item 2.1: Adds EmailSanitizer and SanitizedText for prompt injection defense.
Phase 2, Work Item 2.2: Adds LLMClassifier with Instructor for structured LLM output.
Phase 6, Work Item 6.1: Adds SetFitClassifier for few-shot fine-tuned classification.
Phase 6, Work Item 6.2: Adds EnsembleClassifier for priority-ordered classifier chaining.
"""

from src.classifiers.base import (
    BaseClassifier,
    ClassificationContext,
    ClassificationResult,
    ClassifierCapability,
)
from src.classifiers.ensemble import EnsembleClassifier
from src.classifiers.llm_classifier import LLMClassificationResponse, LLMClassifier
from src.classifiers.sanitizer import EmailSanitizer, SanitizedText
from src.classifiers.setfit_classifier import SetFitClassifier

__all__ = [
    "BaseClassifier",
    "ClassificationContext",
    "ClassificationResult",
    "ClassifierCapability",
    "EmailSanitizer",
    "EnsembleClassifier",
    "LLMClassificationResponse",
    "LLMClassifier",
    "SanitizedText",
    "SetFitClassifier",
]
