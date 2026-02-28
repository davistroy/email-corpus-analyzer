"""
Abstract base class for all email analyzers.

Per Phase 7, Track 7A specification.
Provides a consistent interface for all analyzer implementations.
"""

from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

T = TypeVar("T")


class AnalysisError(Exception):
    """Exception raised when analysis fails."""


class BaseAnalyzer(ABC, Generic[T]):
    """
    Abstract base class for all email analyzers.

    Provides:
    - Common interface for analyze method
    - Name property for logging/identification
    - Incremental analysis support flag
    - Input validation helper

    Type parameter T represents the return type of analyze().
    """

    @abstractmethod
    def analyze(self, data: Any, **kwargs: Any) -> T:
        """
        Analyze emails and return typed results.

        Args:
            data: Input data (Corpus, list of emails, or embeddings depending on analyzer)
            **kwargs: Additional analyzer-specific parameters

        Returns:
            Analysis results of type T (defined by concrete class)

        Raises:
            AnalysisError: If analysis fails
            ValueError: If input is invalid
        """

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Human-readable analyzer name for logging.

        Returns:
            Name string (e.g., "Sender Analyzer", "Semantic Analyzer")
        """

    def supports_incremental(self) -> bool:
        """
        Check if analyzer supports incremental analysis.

        Override in subclass to enable incremental analysis.
        Default is False.

        Returns:
            True if analyzer supports incremental analysis, False otherwise
        """
        return False

    def validate_input(self, emails: Any) -> None:
        """
        Validate input before analysis.

        Override for custom validation in subclasses.

        Args:
            emails: List of Email objects to validate

        Raises:
            AnalysisError: If validation fails
        """
        if not emails:
            raise AnalysisError(f"{self.name} requires non-empty email list")


# Export for convenience
__all__ = [
    "BaseAnalyzer",
    "AnalysisError",
    "T",
]
