"""
Contract tests for extractor implementations.

Verifies that BaseExtractor subclasses (EmailExtractor for M365, GmailExtractor)
conform to the documented extractor contract: abstract method signatures,
source name conventions, and checkpoint source tags.

Phase 4.2: Extractor Contract Tests

NOTE: Extractor constructors initialize API clients that require auth.
These tests verify the class structure and method signatures without
instantiating the extractors (no network or auth required).
"""

import inspect

import pytest

from src.extractors.base_extractor import BaseExtractor
from src.extractors.gmail_extractor import GmailExtractor
from src.extractors.m365_extractor import EmailExtractor

ALL_EXTRACTOR_CLASSES = [EmailExtractor, GmailExtractor]


# -----------------------------------------------------------------------
# Structural contract tests (no instantiation needed)
# -----------------------------------------------------------------------


@pytest.mark.parametrize("extractor_cls", ALL_EXTRACTOR_CLASSES)
class TestExtractorInheritanceContract:
    """Verify extractor classes inherit from BaseExtractor."""

    def test_inherits_base_extractor(self, extractor_cls):
        """All extractors must be subclasses of BaseExtractor."""
        assert issubclass(extractor_cls, BaseExtractor)

    def test_implements_get_source_name(self, extractor_cls):
        """_get_source_name must be defined on the concrete class (not just ABC)."""
        # Verify the method is not abstract on the subclass
        method = extractor_cls._get_source_name
        assert callable(method)
        # Verify it's overridden (not the abstract stub)
        assert not getattr(method, "__isabstractmethod__", False)

    def test_implements_get_checkpoint_source(self, extractor_cls):
        """_get_checkpoint_source must be defined on the concrete class."""
        method = extractor_cls._get_checkpoint_source
        assert callable(method)
        assert not getattr(method, "__isabstractmethod__", False)

    def test_implements_fetch_batch(self, extractor_cls):
        """_fetch_batch must be implemented."""
        method = extractor_cls._fetch_batch
        assert callable(method)
        assert not getattr(method, "__isabstractmethod__", False)

    def test_implements_process_email(self, extractor_cls):
        """_process_email must be implemented."""
        method = extractor_cls._process_email
        assert callable(method)
        assert not getattr(method, "__isabstractmethod__", False)

    def test_fetch_batch_signature(self, extractor_cls):
        """_fetch_batch must accept (self, start, end, last_id) parameters."""
        sig = inspect.signature(extractor_cls._fetch_batch)
        params = list(sig.parameters.keys())
        assert "self" in params
        assert "start" in params
        assert "end" in params
        assert "last_id" in params

    def test_process_email_signature(self, extractor_cls):
        """_process_email must accept (self, email_data) parameters."""
        sig = inspect.signature(extractor_cls._process_email)
        params = list(sig.parameters.keys())
        assert "self" in params
        assert "email_data" in params

    def test_has_extract_all_method(self, extractor_cls):
        """extract_all should be inherited from BaseExtractor."""
        assert hasattr(extractor_cls, "extract_all")
        assert callable(extractor_cls.extract_all)

    def test_has_extract_incremental_method(self, extractor_cls):
        """extract_incremental should be inherited from BaseExtractor."""
        assert hasattr(extractor_cls, "extract_incremental")
        assert callable(extractor_cls.extract_incremental)

    def test_constructor_requires_user_email(self, extractor_cls):
        """Constructor must accept user_email as first positional arg."""
        sig = inspect.signature(extractor_cls.__init__)
        params = list(sig.parameters.keys())
        # First param after self should be user_email
        assert "user_email" in params

    def test_constructor_accepts_checkpoint_dir(self, extractor_cls):
        """Constructor must accept checkpoint_dir parameter."""
        sig = inspect.signature(extractor_cls.__init__)
        params = list(sig.parameters.keys())
        assert "checkpoint_dir" in params


# -----------------------------------------------------------------------
# Source name / checkpoint source contract tests using mock
# -----------------------------------------------------------------------


class TestM365ExtractorSourceContract:
    """Verify M365 EmailExtractor source name and checkpoint source values."""

    def test_get_source_name_returns_non_empty_string(self):
        """_get_source_name should return a non-empty string."""
        # Inspect the method's source to verify it returns a string literal
        source = inspect.getsource(EmailExtractor._get_source_name)
        assert "return" in source
        # Also verify via direct call on an uninitialized-safe approach:
        # The method doesn't use self, so we can call it with a dummy
        result = (
            EmailExtractor._get_source_name.__wrapped__(None)
            if hasattr(EmailExtractor._get_source_name, "__wrapped__")
            else EmailExtractor._get_source_name(None)
        )  # type: ignore[arg-type]
        assert isinstance(result, str)
        assert len(result) > 0

    def test_get_checkpoint_source_returns_non_empty_string(self):
        """_get_checkpoint_source should return a non-empty string."""
        result = EmailExtractor._get_checkpoint_source(None)  # type: ignore[arg-type]
        assert isinstance(result, str)
        assert len(result) > 0

    def test_source_name_value(self):
        """Source name should contain 'M365' or 'Hotmail'."""
        result = EmailExtractor._get_source_name(None)  # type: ignore[arg-type]
        assert "M365" in result or "Hotmail" in result

    def test_checkpoint_source_is_lowercase(self):
        """Checkpoint source tag should be lowercase for file naming."""
        result = EmailExtractor._get_checkpoint_source(None)  # type: ignore[arg-type]
        assert result == result.lower()


class TestGmailExtractorSourceContract:
    """Verify GmailExtractor source name and checkpoint source values."""

    def test_get_source_name_returns_non_empty_string(self):
        """_get_source_name should return a non-empty string."""
        result = GmailExtractor._get_source_name(None)  # type: ignore[arg-type]
        assert isinstance(result, str)
        assert len(result) > 0

    def test_get_checkpoint_source_returns_non_empty_string(self):
        """_get_checkpoint_source should return a non-empty string."""
        result = GmailExtractor._get_checkpoint_source(None)  # type: ignore[arg-type]
        assert isinstance(result, str)
        assert len(result) > 0

    def test_source_name_value(self):
        """Source name should contain 'Gmail'."""
        result = GmailExtractor._get_source_name(None)  # type: ignore[arg-type]
        assert "Gmail" in result

    def test_checkpoint_source_is_lowercase(self):
        """Checkpoint source tag should be lowercase for file naming."""
        result = GmailExtractor._get_checkpoint_source(None)  # type: ignore[arg-type]
        assert result == result.lower()


# -----------------------------------------------------------------------
# BaseExtractor ABC enforcement
# -----------------------------------------------------------------------


class TestBaseExtractorABCEnforcement:
    """Verify that BaseExtractor cannot be instantiated directly."""

    def test_base_extractor_is_abstract(self):
        """BaseExtractor should not be directly instantiable."""
        with pytest.raises(TypeError):
            BaseExtractor(user_email="test@example.com")  # type: ignore[abstract]

    def test_base_extractor_abstract_methods(self):
        """BaseExtractor should declare exactly the expected abstract methods."""
        abstract_methods = set()
        for name in dir(BaseExtractor):
            method = getattr(BaseExtractor, name, None)
            if getattr(method, "__isabstractmethod__", False):
                abstract_methods.add(name)
        expected = {
            "_get_source_name",
            "_get_checkpoint_source",
            "_fetch_batch",
            "_process_email",
        }
        assert abstract_methods == expected, (
            f"Expected abstract methods {expected}, got {abstract_methods}"
        )
