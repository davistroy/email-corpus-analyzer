"""
Classifier abstractions for email classification.

Phase 1, Work Item 1.1: Provides the BaseClassifier ABC, ClassificationResult model,
ClassifierCapability enum, and ClassificationContext dataclass that all classifier
implementations must use.
"""

from src.classifiers.base import (
    BaseClassifier,
    ClassificationContext,
    ClassificationResult,
    ClassifierCapability,
)

__all__ = [
    "BaseClassifier",
    "ClassificationContext",
    "ClassificationResult",
    "ClassifierCapability",
]
