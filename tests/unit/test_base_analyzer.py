"""
Unit tests for Track 7A: Abstract BaseAnalyzer class.

Tests the abstract base class for all email analyzers with:
- Abstract method enforcement
- Common validation logic
- Name property requirement
- Incremental analysis support flag
"""
from datetime import datetime

import pytest

from src.models.corpus import Corpus, CorpusMetadata
from src.models.email import Email


def create_test_email(
    email_id: str = "test_001",
    sender_email: str = "sender@example.com",
    sender_domain: str = "example.com",
    subject: str = "Test Subject",
    body_text: str = "Test body content",
    received_date: datetime | None = None,
) -> Email:
    """Factory function to create Email objects for testing."""
    if received_date is None:
        received_date = datetime(2024, 1, 15, 10, 0)
    return Email(
        id=email_id,
        sender_email=sender_email,
        sender_name="Test Sender",
        sender_domain=sender_domain,
        subject=subject,
        body_text=body_text,
        received_date=received_date,
        has_attachments=False,
    )


def create_test_corpus(emails: list[Email] | None = None) -> Corpus:
    """Factory function to create Corpus objects for testing."""
    if emails is None:
        emails = [create_test_email(email_id=f"email_{i}") for i in range(5)]
    return Corpus(
        extraction_metadata=CorpusMetadata(
            extraction_date=datetime.now(),
            total_emails=len(emails),
            source="test",
            user_email="user@example.com",
        ),
        emails=emails,
    )


# ============================================================================
# Test BaseAnalyzer Abstract Class
# ============================================================================


class TestBaseAnalyzerAbstract:
    """Test cases for BaseAnalyzer abstract base class."""

    def test_base_analyzer_exists(self):
        """Test that BaseAnalyzer class exists."""
        from src.analyzers.base import BaseAnalyzer

        assert BaseAnalyzer is not None

    def test_base_analyzer_is_abstract(self):
        """Test that BaseAnalyzer cannot be instantiated directly."""
        from src.analyzers.base import BaseAnalyzer

        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            BaseAnalyzer()

    def test_base_analyzer_is_generic(self):
        """Test that BaseAnalyzer is a generic class with TypeVar."""
        from src.analyzers.base import BaseAnalyzer

        # Check it's a generic class
        assert hasattr(BaseAnalyzer, "__class_getitem__")

    def test_base_analyzer_has_analyze_method(self):
        """Test that BaseAnalyzer requires analyze method."""
        from src.analyzers.base import BaseAnalyzer

        # analyze should be an abstract method
        assert hasattr(BaseAnalyzer, "analyze")

    def test_base_analyzer_has_name_property(self):
        """Test that BaseAnalyzer requires name property."""
        from src.analyzers.base import BaseAnalyzer

        # name should be an abstract property
        assert hasattr(BaseAnalyzer, "name")

    def test_base_analyzer_has_supports_incremental_method(self):
        """Test that BaseAnalyzer has supports_incremental method."""
        from src.analyzers.base import BaseAnalyzer

        assert hasattr(BaseAnalyzer, "supports_incremental")

    def test_base_analyzer_has_validate_input_method(self):
        """Test that BaseAnalyzer has validate_input method."""
        from src.analyzers.base import BaseAnalyzer

        assert hasattr(BaseAnalyzer, "validate_input")


class TestConcreteAnalyzerImplementation:
    """Test concrete implementations of BaseAnalyzer."""

    def test_concrete_analyzer_must_implement_analyze(self):
        """Test that concrete analyzer must implement analyze method."""
        from src.analyzers.base import BaseAnalyzer

        class IncompleteAnalyzer(BaseAnalyzer):
            @property
            def name(self) -> str:
                return "Incomplete"

        # Should raise TypeError because analyze is not implemented
        with pytest.raises(TypeError):
            IncompleteAnalyzer()

    def test_concrete_analyzer_must_implement_name(self):
        """Test that concrete analyzer must implement name property."""
        from src.analyzers.base import BaseAnalyzer

        class IncompleteAnalyzer(BaseAnalyzer):
            def analyze(self, emails, **kwargs):
                return None

        # Should raise TypeError because name is not implemented
        with pytest.raises(TypeError):
            IncompleteAnalyzer()

    def test_complete_concrete_analyzer(self):
        """Test that complete concrete analyzer can be instantiated."""
        from src.analyzers.base import BaseAnalyzer

        class CompleteAnalyzer(BaseAnalyzer[dict]):
            @property
            def name(self) -> str:
                return "Complete Analyzer"

            def analyze(self, emails, **kwargs):
                return {"count": len(emails)}

        analyzer = CompleteAnalyzer()
        assert analyzer is not None
        assert analyzer.name == "Complete Analyzer"

    def test_supports_incremental_default_false(self):
        """Test that supports_incremental defaults to False."""
        from src.analyzers.base import BaseAnalyzer

        class SimpleAnalyzer(BaseAnalyzer[dict]):
            @property
            def name(self) -> str:
                return "Simple"

            def analyze(self, emails, **kwargs):
                return {}

        analyzer = SimpleAnalyzer()
        assert analyzer.supports_incremental() is False

    def test_supports_incremental_can_be_overridden(self):
        """Test that supports_incremental can be overridden."""
        from src.analyzers.base import BaseAnalyzer

        class IncrementalAnalyzer(BaseAnalyzer[dict]):
            @property
            def name(self) -> str:
                return "Incremental"

            def analyze(self, emails, **kwargs):
                return {}

            def supports_incremental(self) -> bool:
                return True

        analyzer = IncrementalAnalyzer()
        assert analyzer.supports_incremental() is True

    def test_validate_input_raises_on_empty_list(self):
        """Test that validate_input raises AnalysisError on empty list."""
        from src.analyzers.base import AnalysisError, BaseAnalyzer

        class TestAnalyzer(BaseAnalyzer[dict]):
            @property
            def name(self) -> str:
                return "Test"

            def analyze(self, emails, **kwargs):
                return {}

        analyzer = TestAnalyzer()

        with pytest.raises(AnalysisError, match="requires non-empty email list"):
            analyzer.validate_input([])

    def test_validate_input_passes_for_non_empty_list(self):
        """Test that validate_input passes for non-empty list."""
        from src.analyzers.base import BaseAnalyzer

        class TestAnalyzer(BaseAnalyzer[dict]):
            @property
            def name(self) -> str:
                return "Test"

            def analyze(self, emails, **kwargs):
                return {}

        analyzer = TestAnalyzer()
        emails = [create_test_email()]

        # Should not raise
        analyzer.validate_input(emails)


class TestAnalysisError:
    """Test cases for AnalysisError exception."""

    def test_analysis_error_exists(self):
        """Test that AnalysisError exception exists."""
        from src.analyzers.base import AnalysisError

        assert AnalysisError is not None

    def test_analysis_error_is_exception(self):
        """Test that AnalysisError is an Exception subclass."""
        from src.analyzers.base import AnalysisError

        assert issubclass(AnalysisError, Exception)

    def test_analysis_error_can_be_raised(self):
        """Test that AnalysisError can be raised with message."""
        from src.analyzers.base import AnalysisError

        with pytest.raises(AnalysisError, match="Test error message"):
            raise AnalysisError("Test error message")


# ============================================================================
# Test Existing Analyzers Inherit from BaseAnalyzer
# ============================================================================


class TestSenderAnalyzerInheritance:
    """Test that SenderAnalyzer inherits from BaseAnalyzer."""

    def test_sender_analyzer_inherits_from_base(self):
        """Test SenderAnalyzer is a BaseAnalyzer."""
        from src.analyzers.base import BaseAnalyzer
        from src.analyzers.sender_analyzer import SenderAnalyzer

        assert issubclass(SenderAnalyzer, BaseAnalyzer)

    def test_sender_analyzer_has_name(self):
        """Test SenderAnalyzer has name property."""
        from src.analyzers.sender_analyzer import SenderAnalyzer

        analyzer = SenderAnalyzer()
        assert analyzer.name == "Sender Analyzer"

    def test_sender_analyzer_supports_incremental_false(self):
        """Test SenderAnalyzer does not support incremental."""
        from src.analyzers.sender_analyzer import SenderAnalyzer

        analyzer = SenderAnalyzer()
        assert analyzer.supports_incremental() is False


class TestSubjectAnalyzerInheritance:
    """Test that SubjectAnalyzer inherits from BaseAnalyzer."""

    def test_subject_analyzer_inherits_from_base(self):
        """Test SubjectAnalyzer is a BaseAnalyzer."""
        from src.analyzers.base import BaseAnalyzer
        from src.analyzers.subject_analyzer import SubjectAnalyzer

        assert issubclass(SubjectAnalyzer, BaseAnalyzer)

    def test_subject_analyzer_has_name(self):
        """Test SubjectAnalyzer has name property."""
        from src.analyzers.subject_analyzer import SubjectAnalyzer

        analyzer = SubjectAnalyzer()
        assert analyzer.name == "Subject Analyzer"

    def test_subject_analyzer_supports_incremental_false(self):
        """Test SubjectAnalyzer does not support incremental."""
        from src.analyzers.subject_analyzer import SubjectAnalyzer

        analyzer = SubjectAnalyzer()
        assert analyzer.supports_incremental() is False


class TestSemanticAnalyzerInheritance:
    """Test that SemanticAnalyzer inherits from BaseAnalyzer."""

    def test_semantic_analyzer_inherits_from_base(self):
        """Test SemanticAnalyzer is a BaseAnalyzer."""
        from src.analyzers.base import BaseAnalyzer
        from src.analyzers.semantic_analyzer import SemanticAnalyzer

        assert issubclass(SemanticAnalyzer, BaseAnalyzer)

    def test_semantic_analyzer_has_name(self):
        """Test SemanticAnalyzer has name property."""
        from src.analyzers.semantic_analyzer import SemanticAnalyzer

        analyzer = SemanticAnalyzer()
        assert analyzer.name == "Semantic Analyzer"

    def test_semantic_analyzer_supports_incremental_true(self):
        """Test SemanticAnalyzer supports incremental (special case)."""
        from src.analyzers.semantic_analyzer import SemanticAnalyzer

        analyzer = SemanticAnalyzer()
        assert analyzer.supports_incremental() is True


class TestTemporalAnalyzerInheritance:
    """Test that TemporalAnalyzer inherits from BaseAnalyzer."""

    def test_temporal_analyzer_inherits_from_base(self):
        """Test TemporalAnalyzer is a BaseAnalyzer."""
        from src.analyzers.base import BaseAnalyzer
        from src.analyzers.temporal_analyzer import TemporalAnalyzer

        assert issubclass(TemporalAnalyzer, BaseAnalyzer)

    def test_temporal_analyzer_has_name(self):
        """Test TemporalAnalyzer has name property."""
        from src.analyzers.temporal_analyzer import TemporalAnalyzer

        analyzer = TemporalAnalyzer()
        assert analyzer.name == "Temporal Analyzer"

    def test_temporal_analyzer_supports_incremental_false(self):
        """Test TemporalAnalyzer does not support incremental."""
        from src.analyzers.temporal_analyzer import TemporalAnalyzer

        analyzer = TemporalAnalyzer()
        assert analyzer.supports_incremental() is False


class TestVolumeAnalyzerInheritance:
    """Test that VolumeAnalyzer inherits from BaseAnalyzer."""

    def test_volume_analyzer_inherits_from_base(self):
        """Test VolumeAnalyzer is a BaseAnalyzer."""
        from src.analyzers.base import BaseAnalyzer
        from src.analyzers.volume_analyzer import VolumeAnalyzer

        assert issubclass(VolumeAnalyzer, BaseAnalyzer)

    def test_volume_analyzer_has_name(self):
        """Test VolumeAnalyzer has name property."""
        from src.analyzers.volume_analyzer import VolumeAnalyzer

        analyzer = VolumeAnalyzer()
        assert analyzer.name == "Volume Analyzer"

    def test_volume_analyzer_supports_incremental_false(self):
        """Test VolumeAnalyzer does not support incremental."""
        from src.analyzers.volume_analyzer import VolumeAnalyzer

        analyzer = VolumeAnalyzer()
        assert analyzer.supports_incremental() is False


class TestHierarchicalAnalyzerInheritance:
    """Test that HierarchicalAnalyzer inherits from BaseAnalyzer."""

    def test_hierarchical_analyzer_inherits_from_base(self):
        """Test HierarchicalAnalyzer is a BaseAnalyzer."""
        from src.analyzers.base import BaseAnalyzer
        from src.analyzers.hierarchical_analyzer import HierarchicalAnalyzer

        assert issubclass(HierarchicalAnalyzer, BaseAnalyzer)

    def test_hierarchical_analyzer_has_name(self):
        """Test HierarchicalAnalyzer has name property."""
        from src.analyzers.hierarchical_analyzer import HierarchicalAnalyzer

        analyzer = HierarchicalAnalyzer()
        assert analyzer.name == "Hierarchical Analyzer"

    def test_hierarchical_analyzer_supports_incremental_false(self):
        """Test HierarchicalAnalyzer does not support incremental."""
        from src.analyzers.hierarchical_analyzer import HierarchicalAnalyzer

        analyzer = HierarchicalAnalyzer()
        assert analyzer.supports_incremental() is False


class TestClusterOptimizerInheritance:
    """Test that cluster optimizers inherit from BaseAnalyzer."""

    def test_elbow_optimizer_inherits_from_base(self):
        """Test ElbowOptimizer is a BaseAnalyzer."""
        from src.analyzers.base import BaseAnalyzer
        from src.analyzers.cluster_optimizer import ElbowOptimizer

        assert issubclass(ElbowOptimizer, BaseAnalyzer)

    def test_elbow_optimizer_has_name(self):
        """Test ElbowOptimizer has name property."""
        from src.analyzers.cluster_optimizer import ElbowOptimizer

        optimizer = ElbowOptimizer()
        assert optimizer.name == "Elbow Optimizer"

    def test_silhouette_optimizer_inherits_from_base(self):
        """Test SilhouetteOptimizer is a BaseAnalyzer."""
        from src.analyzers.base import BaseAnalyzer
        from src.analyzers.cluster_optimizer import SilhouetteOptimizer

        assert issubclass(SilhouetteOptimizer, BaseAnalyzer)

    def test_silhouette_optimizer_has_name(self):
        """Test SilhouetteOptimizer has name property."""
        from src.analyzers.cluster_optimizer import SilhouetteOptimizer

        optimizer = SilhouetteOptimizer()
        assert optimizer.name == "Silhouette Optimizer"


# ============================================================================
# Test Analyze Method Signature Compatibility
# ============================================================================


class TestAnalyzeMethodCompatibility:
    """Test that analyzers maintain compatible analyze method signatures."""

    def test_sender_analyzer_analyze_accepts_corpus(self):
        """Test SenderAnalyzer.analyze accepts Corpus object."""
        from src.analyzers.sender_analyzer import SenderAnalyzer

        analyzer = SenderAnalyzer()
        corpus = create_test_corpus()

        # Should work with corpus
        result = analyzer.analyze(corpus)
        assert result is not None

    def test_subject_analyzer_analyze_accepts_corpus(self):
        """Test SubjectAnalyzer.analyze accepts Corpus object."""
        from src.analyzers.subject_analyzer import SubjectAnalyzer

        analyzer = SubjectAnalyzer()
        corpus = create_test_corpus()

        result = analyzer.analyze(corpus)
        assert result is not None

    def test_temporal_analyzer_analyze_accepts_corpus(self):
        """Test TemporalAnalyzer.analyze accepts Corpus object."""
        from src.analyzers.temporal_analyzer import TemporalAnalyzer

        analyzer = TemporalAnalyzer()
        corpus = create_test_corpus()

        result = analyzer.analyze(corpus)
        assert result is not None

    def test_volume_analyzer_analyze_accepts_corpus(self):
        """Test VolumeAnalyzer.analyze accepts Corpus object."""
        from src.analyzers.volume_analyzer import VolumeAnalyzer

        analyzer = VolumeAnalyzer()
        corpus = create_test_corpus()

        result = analyzer.analyze(corpus)
        assert result is not None
