"""
Classifier abstractions for email classification.

Phase 1, Work Item 1.1: Provides the BaseClassifier ABC, ClassificationResult model,
ClassifierCapability enum, and ClassificationContext dataclass that all classifier
implementations must use.

Phase 2, Work Item 2.1: Adds EmailSanitizer and SanitizedText for prompt injection defense.
Phase 2, Work Item 2.2: Adds LLMClassifier with Instructor for structured LLM output.
"""

from src.classifiers.base import (
    BaseClassifier,
    ClassificationContext,
    ClassificationResult,
    ClassifierCapability,
)
from src.classifiers.llm_classifier import LLMClassificationResponse, LLMClassifier
from src.classifiers.sanitizer import EmailSanitizer, SanitizedText

__all__ = [
    "BaseClassifier",
    "ClassificationContext",
    "ClassificationResult",
    "ClassifierCapability",
    "EmailSanitizer",
    "LLMClassificationResponse",
    "LLMClassifier",
    "SanitizedText",
]
