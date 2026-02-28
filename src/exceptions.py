"""
Custom exception hierarchy for Email Corpus Analyzer.

Provides structured exceptions with:
- Descriptive error messages
- Recovery hints for users
- Context dictionaries for debugging

Per Phase 6 Track 6A specification.
"""

from typing import Any


class EmailAnalyzerError(Exception):
    """
    Base exception for all Email Corpus Analyzer errors.

    All custom exceptions inherit from this class, allowing for
    unified error handling throughout the application.

    Attributes:
        message: Human-readable error description
        recovery_hint: Suggested action for the user to resolve the error
        context: Dictionary with additional error context for debugging
    """

    def __init__(
        self, message: str, recovery_hint: str | None = None, context: dict[str, Any] | None = None
    ):
        """
        Initialize the exception.

        Args:
            message: Human-readable error description
            recovery_hint: Suggested action for the user to resolve the error
            context: Dictionary with additional error context for debugging
        """
        self.message = message
        self.recovery_hint = recovery_hint
        self.context = context or {}
        super().__init__(message)

    def __str__(self) -> str:
        """Return string representation of the error."""
        return self.message


# =============================================================================
# Corpus-related exceptions
# =============================================================================


class CorpusNotFoundError(EmailAnalyzerError):
    """
    Raised when the email corpus file cannot be found.

    Typically occurs when running analyze/suggest commands
    without first running extract.
    """

    def __init__(self, path: str, recovery_hint: str | None = None):
        """
        Initialize corpus not found error.

        Args:
            path: Path to the missing corpus file
            recovery_hint: Custom recovery hint (default provided if None)
        """
        message = f"Corpus file not found: {path}"
        hint = recovery_hint or (
            "Run 'extract' command first to create the corpus file, "
            "or specify a valid path with --corpus"
        )
        super().__init__(message=message, recovery_hint=hint, context={"path": path})


class CorpusParseError(EmailAnalyzerError):
    """
    Raised when the corpus file cannot be parsed.

    Occurs when the corpus JSON is malformed or contains
    invalid data that cannot be deserialized.
    """

    def __init__(self, path: str, parse_error: str, recovery_hint: str | None = None):
        """
        Initialize corpus parse error.

        Args:
            path: Path to the corpus file
            parse_error: Description of the parse error
            recovery_hint: Custom recovery hint (default provided if None)
        """
        message = f"Failed to parse corpus file {path}: {parse_error}"
        hint = recovery_hint or (
            "The corpus file may be corrupted. Try re-running the 'extract' command "
            "to regenerate it, or check the file contents manually."
        )
        super().__init__(
            message=message, recovery_hint=hint, context={"path": path, "parse_error": parse_error}
        )


# =============================================================================
# Configuration-related exceptions
# =============================================================================


class ConfigurationError(EmailAnalyzerError):
    """
    Raised when there is a configuration error.

    Base class for all configuration-related exceptions.
    """

    def __init__(
        self, message: str, recovery_hint: str | None = None, context: dict[str, Any] | None = None
    ):
        """
        Initialize configuration error.

        Args:
            message: Error description
            recovery_hint: Custom recovery hint
            context: Additional context
        """
        hint = recovery_hint or (
            "Check your configuration file or run 'config init' to generate a template"
        )
        super().__init__(message=message, recovery_hint=hint, context=context or {})


class ConfigValidationError(ConfigurationError):
    """
    Raised when configuration validation fails.

    Occurs when a configuration value is invalid or
    doesn't meet requirements (e.g., path doesn't exist).
    """

    def __init__(self, field: str, value: Any, reason: str, recovery_hint: str | None = None):
        """
        Initialize configuration validation error.

        Args:
            field: Name of the invalid configuration field
            value: The invalid value
            reason: Why the value is invalid
            recovery_hint: Custom recovery hint
        """
        message = f"Invalid configuration for '{field}': {reason}"
        hint = recovery_hint or (
            f"Check the value for '{field}' in your configuration file. "
            "Run 'config show' to see current settings."
        )
        super().__init__(
            message=message,
            recovery_hint=hint,
            context={"field": field, "value": value, "reason": reason},
        )


# =============================================================================
# Analysis-related exceptions
# =============================================================================


class AnalysisError(EmailAnalyzerError):
    """
    Raised when analysis fails.

    Base class for all analysis-related exceptions.
    """

    def __init__(
        self, message: str, recovery_hint: str | None = None, context: dict[str, Any] | None = None
    ):
        """
        Initialize analysis error.

        Args:
            message: Error description
            recovery_hint: Custom recovery hint
            context: Additional context
        """
        hint = recovery_hint or (
            "Check the corpus data and try again. Use --verbose for more details."
        )
        super().__init__(message=message, recovery_hint=hint, context=context or {})


class ClusteringError(AnalysisError):
    """
    Raised when semantic clustering fails.

    Occurs when there are issues with the clustering algorithm,
    such as too few samples or invalid parameters.
    """

    def __init__(
        self, message: str, recovery_hint: str | None = None, context: dict[str, Any] | None = None
    ):
        """
        Initialize clustering error.

        Args:
            message: Error description
            recovery_hint: Custom recovery hint
            context: Additional context (e.g., k value, sample count)
        """
        hint = recovery_hint or (
            "Try adjusting --num-clusters or use --auto-clusters to "
            "automatically determine the optimal number of clusters."
        )
        super().__init__(message=message, recovery_hint=hint, context=context or {})


# =============================================================================
# Extraction-related exceptions
# =============================================================================


class ExtractionError(EmailAnalyzerError):
    """
    Raised when email extraction fails.

    Base class for all extraction-related exceptions.
    """

    def __init__(
        self, message: str, recovery_hint: str | None = None, context: dict[str, Any] | None = None
    ):
        """
        Initialize extraction error.

        Args:
            message: Error description
            recovery_hint: Custom recovery hint
            context: Additional context
        """
        hint = recovery_hint or (
            "Check your network connection and try again. Use --verbose for more details."
        )
        super().__init__(message=message, recovery_hint=hint, context=context or {})


class RateLimitError(ExtractionError):
    """
    Raised when a provider rate limit is exceeded (HTTP 429).

    Carries an optional retry_after hint (seconds) extracted from the
    provider's response headers so callers can back off intelligently.
    """

    def __init__(
        self,
        retry_after: int | None = None,
        context: dict[str, Any] | None = None,
    ):
        """
        Initialize rate limit error.

        Args:
            retry_after: Seconds to wait before retrying (from provider header)
            context: Additional context for debugging
        """
        super().__init__(
            message="Rate limit exceeded",
            recovery_hint="Wait and retry. The provider is throttling requests.",
            context=context or {},
        )
        self.retry_after = retry_after


class M365AuthError(ExtractionError):
    """
    Raised when M365 authentication fails.

    Occurs when the authentication token is invalid,
    expired, or the user doesn't have permission.
    """

    def __init__(
        self, message: str, recovery_hint: str | None = None, context: dict[str, Any] | None = None
    ):
        """
        Initialize M365 authentication error.

        Args:
            message: Error description
            recovery_hint: Custom recovery hint
            context: Additional context (e.g., user email, error code)
        """
        hint = recovery_hint or (
            "Re-authenticate with your M365 account. "
            "Ensure you have granted the necessary permissions to access your emails."
        )
        super().__init__(message=message, recovery_hint=hint, context=context or {})


# =============================================================================
# Export-related exceptions
# =============================================================================


class ExportError(EmailAnalyzerError):
    """
    Raised when export operations fail.

    Occurs when template files are missing, output paths
    are invalid, or rendering fails.
    """

    def __init__(
        self, message: str, recovery_hint: str | None = None, context: dict[str, Any] | None = None
    ):
        """
        Initialize export error.

        Args:
            message: Error description
            recovery_hint: Custom recovery hint
            context: Additional context (e.g., template path, output path)
        """
        hint = recovery_hint or (
            "Check the export configuration and try again. Use --verbose for more details."
        )
        super().__init__(message=message, recovery_hint=hint, context=context or {})
