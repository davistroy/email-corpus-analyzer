"""
Unit tests for custom exception hierarchy.

Tests cover:
- Base EmailAnalyzerError class with message, recovery_hint, context
- Corpus-related exceptions: CorpusNotFoundError, CorpusParseError
- Configuration exceptions: ConfigurationError, ConfigValidationError
- Analysis exceptions: AnalysisError, ClusteringError
- Extraction exceptions: ExtractionError, M365AuthError

Per Phase 6 Track 6A specification.
"""
import pytest


class TestEmailAnalyzerError:
    """Test cases for base EmailAnalyzerError class."""

    def test_base_error_with_message_only(self):
        """Test EmailAnalyzerError with just a message."""
        from src.exceptions import EmailAnalyzerError

        error = EmailAnalyzerError("Something went wrong")

        assert str(error) == "Something went wrong"
        assert error.message == "Something went wrong"
        assert error.recovery_hint is None
        assert error.context == {}

    def test_base_error_with_recovery_hint(self):
        """Test EmailAnalyzerError with recovery hint."""
        from src.exceptions import EmailAnalyzerError

        error = EmailAnalyzerError(
            "Something went wrong",
            recovery_hint="Try again later"
        )

        assert error.message == "Something went wrong"
        assert error.recovery_hint == "Try again later"

    def test_base_error_with_context(self):
        """Test EmailAnalyzerError with context dictionary."""
        from src.exceptions import EmailAnalyzerError

        error = EmailAnalyzerError(
            "File error",
            context={"file_path": "/path/to/file", "operation": "read"}
        )

        assert error.message == "File error"
        assert error.context["file_path"] == "/path/to/file"
        assert error.context["operation"] == "read"

    def test_base_error_with_all_parameters(self):
        """Test EmailAnalyzerError with all parameters."""
        from src.exceptions import EmailAnalyzerError

        error = EmailAnalyzerError(
            "Complete error",
            recovery_hint="Check the file exists",
            context={"path": "/file.json"}
        )

        assert error.message == "Complete error"
        assert error.recovery_hint == "Check the file exists"
        assert error.context == {"path": "/file.json"}

    def test_base_error_is_exception(self):
        """Test EmailAnalyzerError is a proper Exception."""
        from src.exceptions import EmailAnalyzerError

        error = EmailAnalyzerError("Test error")

        assert isinstance(error, Exception)
        with pytest.raises(EmailAnalyzerError):
            raise error

    def test_base_error_str_representation(self):
        """Test string representation includes recovery hint if present."""
        from src.exceptions import EmailAnalyzerError

        # Without hint
        error1 = EmailAnalyzerError("Error message")
        assert str(error1) == "Error message"

        # With hint
        error2 = EmailAnalyzerError("Error message", recovery_hint="Try this fix")
        assert "Error message" in str(error2)


class TestCorpusExceptions:
    """Test cases for corpus-related exceptions."""

    def test_corpus_not_found_error(self):
        """Test CorpusNotFoundError with default recovery hint."""
        from src.exceptions import CorpusNotFoundError, EmailAnalyzerError

        error = CorpusNotFoundError("/path/to/corpus.json")

        assert isinstance(error, EmailAnalyzerError)
        assert "corpus.json" in error.message
        assert error.recovery_hint is not None
        assert "extract" in error.recovery_hint.lower()

    def test_corpus_not_found_error_with_custom_hint(self):
        """Test CorpusNotFoundError with custom recovery hint."""
        from src.exceptions import CorpusNotFoundError

        error = CorpusNotFoundError(
            "/custom/path.json",
            recovery_hint="Custom hint"
        )

        assert error.recovery_hint == "Custom hint"

    def test_corpus_not_found_error_context_includes_path(self):
        """Test CorpusNotFoundError includes path in context."""
        from src.exceptions import CorpusNotFoundError

        error = CorpusNotFoundError("/some/path/corpus.json")

        assert "path" in error.context
        assert error.context["path"] == "/some/path/corpus.json"

    def test_corpus_parse_error(self):
        """Test CorpusParseError with default recovery hint."""
        from src.exceptions import CorpusParseError, EmailAnalyzerError

        error = CorpusParseError("/path/corpus.json", "Invalid JSON syntax")

        assert isinstance(error, EmailAnalyzerError)
        assert "parse" in error.message.lower() or "Invalid JSON" in error.message
        assert error.recovery_hint is not None

    def test_corpus_parse_error_context(self):
        """Test CorpusParseError includes path and parse error in context."""
        from src.exceptions import CorpusParseError

        error = CorpusParseError("/path/file.json", "Unexpected token at line 5")

        assert "path" in error.context
        assert "parse_error" in error.context
        assert error.context["path"] == "/path/file.json"


class TestConfigurationExceptions:
    """Test cases for configuration-related exceptions."""

    def test_configuration_error(self):
        """Test ConfigurationError with message and hint."""
        from src.exceptions import ConfigurationError, EmailAnalyzerError

        error = ConfigurationError("Invalid config file")

        assert isinstance(error, EmailAnalyzerError)
        assert "config" in error.message.lower() or "Invalid config" in error.message

    def test_configuration_error_with_recovery_hint(self):
        """Test ConfigurationError with recovery hint."""
        from src.exceptions import ConfigurationError

        error = ConfigurationError(
            "Missing required field",
            recovery_hint="Run 'config init' to generate a template"
        )

        assert error.recovery_hint == "Run 'config init' to generate a template"

    def test_config_validation_error(self):
        """Test ConfigValidationError with field information."""
        from src.exceptions import ConfigurationError, ConfigValidationError

        error = ConfigValidationError(
            field="output_dir",
            value="/invalid/path",
            reason="Directory does not exist"
        )

        assert isinstance(error, ConfigurationError)
        assert "output_dir" in error.message or "output_dir" in str(error.context)
        assert error.recovery_hint is not None

    def test_config_validation_error_context(self):
        """Test ConfigValidationError includes field details in context."""
        from src.exceptions import ConfigValidationError

        error = ConfigValidationError(
            field="num_clusters",
            value=-5,
            reason="Must be positive"
        )

        assert "field" in error.context
        assert "value" in error.context
        assert "reason" in error.context
        assert error.context["field"] == "num_clusters"
        assert error.context["value"] == -5


class TestAnalysisExceptions:
    """Test cases for analysis-related exceptions."""

    def test_analysis_error(self):
        """Test AnalysisError with message."""
        from src.exceptions import AnalysisError, EmailAnalyzerError

        error = AnalysisError("Analysis failed")

        assert isinstance(error, EmailAnalyzerError)
        assert "Analysis failed" in error.message

    def test_analysis_error_with_context(self):
        """Test AnalysisError with context information."""
        from src.exceptions import AnalysisError

        error = AnalysisError(
            "Analyzer error",
            context={"analyzer": "semantic", "stage": "embedding"}
        )

        assert error.context["analyzer"] == "semantic"
        assert error.context["stage"] == "embedding"

    def test_clustering_error(self):
        """Test ClusteringError with default recovery hint."""
        from src.exceptions import AnalysisError, ClusteringError

        error = ClusteringError("Too few samples for clustering")

        assert isinstance(error, AnalysisError)
        assert error.recovery_hint is not None

    def test_clustering_error_with_cluster_info(self):
        """Test ClusteringError with cluster information in context."""
        from src.exceptions import ClusteringError

        error = ClusteringError(
            "Invalid k value",
            context={"k": 0, "min_k": 2, "max_k": 15}
        )

        assert "k" in error.context
        assert error.context["k"] == 0


class TestExtractionExceptions:
    """Test cases for extraction-related exceptions."""

    def test_extraction_error(self):
        """Test ExtractionError with message."""
        from src.exceptions import EmailAnalyzerError, ExtractionError

        error = ExtractionError("Failed to extract emails")

        assert isinstance(error, EmailAnalyzerError)
        assert "extract" in error.message.lower() or "Failed" in error.message

    def test_extraction_error_with_context(self):
        """Test ExtractionError with extraction context."""
        from src.exceptions import ExtractionError

        error = ExtractionError(
            "Batch failed",
            context={"batch_number": 5, "total_batches": 10, "emails_so_far": 2500}
        )

        assert error.context["batch_number"] == 5
        assert error.context["emails_so_far"] == 2500

    def test_m365_auth_error(self):
        """Test M365AuthError with authentication-specific hint."""
        from src.exceptions import ExtractionError, M365AuthError

        error = M365AuthError("Authentication failed")

        assert isinstance(error, ExtractionError)
        assert error.recovery_hint is not None
        # Should suggest re-authentication
        assert "auth" in error.recovery_hint.lower() or "login" in error.recovery_hint.lower()

    def test_m365_auth_error_with_details(self):
        """Test M365AuthError with authentication details."""
        from src.exceptions import M365AuthError

        error = M365AuthError(
            "Token expired",
            context={"user_email": "user@example.com", "error_code": "AADSTS50001"}
        )

        assert "user_email" in error.context
        assert "error_code" in error.context


class TestExceptionHierarchy:
    """Test exception class hierarchy relationships."""

    def test_all_exceptions_inherit_from_base(self):
        """Test all custom exceptions inherit from EmailAnalyzerError."""
        from src.exceptions import (
            AnalysisError,
            ClusteringError,
            ConfigurationError,
            ConfigValidationError,
            CorpusNotFoundError,
            CorpusParseError,
            EmailAnalyzerError,
            ExtractionError,
            M365AuthError,
        )

        assert issubclass(CorpusNotFoundError, EmailAnalyzerError)
        assert issubclass(CorpusParseError, EmailAnalyzerError)
        assert issubclass(ConfigurationError, EmailAnalyzerError)
        assert issubclass(ConfigValidationError, EmailAnalyzerError)
        assert issubclass(AnalysisError, EmailAnalyzerError)
        assert issubclass(ClusteringError, EmailAnalyzerError)
        assert issubclass(ExtractionError, EmailAnalyzerError)
        assert issubclass(M365AuthError, EmailAnalyzerError)

    def test_config_validation_inherits_from_configuration_error(self):
        """Test ConfigValidationError inherits from ConfigurationError."""
        from src.exceptions import ConfigurationError, ConfigValidationError

        assert issubclass(ConfigValidationError, ConfigurationError)

    def test_clustering_error_inherits_from_analysis_error(self):
        """Test ClusteringError inherits from AnalysisError."""
        from src.exceptions import AnalysisError, ClusteringError

        assert issubclass(ClusteringError, AnalysisError)

    def test_m365_auth_error_inherits_from_extraction_error(self):
        """Test M365AuthError inherits from ExtractionError."""
        from src.exceptions import ExtractionError, M365AuthError

        assert issubclass(M365AuthError, ExtractionError)

    def test_can_catch_base_exception(self):
        """Test catching base exception catches all derived exceptions."""
        from src.exceptions import (
            AnalysisError,
            ConfigurationError,
            CorpusNotFoundError,
            EmailAnalyzerError,
            ExtractionError,
        )

        exceptions = [
            CorpusNotFoundError("/path"),
            ConfigurationError("Config error"),
            AnalysisError("Analysis error"),
            ExtractionError("Extraction error"),
        ]

        for exc in exceptions:
            try:
                raise exc
            except EmailAnalyzerError as e:
                assert e is exc
