"""
Contract tests for analyzer implementations.

Verifies that all analyzer subclasses of BaseAnalyzer conform to the
documented contract: name property, analyze method signature, empty/single
input handling, and return type guarantees.

Phase 4.2: Analyzer Contract Tests
"""

from datetime import datetime, timedelta

import pytest

from src.analyzers.base import AnalysisError, BaseAnalyzer
from src.analyzers.sender_analyzer import SenderAnalyzer
from src.analyzers.subject_analyzer import SubjectAnalyzer
from src.analyzers.temporal_analyzer import TemporalAnalyzer
from src.analyzers.thread_analyzer import ThreadAnalysisResult, ThreadAnalyzer
from src.analyzers.volume_analyzer import VolumeAnalyzer
from src.models.analysis_results import (
    SenderAnalysis,
    SubjectPatterns,
    TemporalPatterns,
    VolumeStats,
)
from src.models.corpus import Corpus, CorpusMetadata
from src.models.email import Email

# -----------------------------------------------------------------------
# Analyzers that can run without model download (no sentence-transformers)
# SemanticAnalyzer and HierarchicalAnalyzer require a model download, so
# they are excluded from parameterized contract tests.
# -----------------------------------------------------------------------
LIGHTWEIGHT_ANALYZERS = [
    SenderAnalyzer,
    SubjectAnalyzer,
    TemporalAnalyzer,
    VolumeAnalyzer,
    ThreadAnalyzer,
]

# Analyzers that raise on empty corpus input
ANALYZERS_RAISING_ON_EMPTY = [
    SenderAnalyzer,
    SubjectAnalyzer,
    VolumeAnalyzer,
    ThreadAnalyzer,
]

# Analyzers that gracefully handle empty corpus (return empty/zero result)
ANALYZERS_GRACEFUL_ON_EMPTY = [
    TemporalAnalyzer,
]


# -----------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------


def _make_email(
    idx: int,
    sender_email: str = "sender{idx}@example.com",
    sender_domain: str = "example.com",
    subject: str = "Test Subject {idx}",
    days_offset: int = 0,
) -> Email:
    """Helper to build a minimal Email object."""
    return Email(
        id=f"contract_email_{idx:04d}",
        sender_email=sender_email.format(idx=idx),
        sender_name=f"Sender {idx}",
        sender_domain=sender_domain,
        recipient_email="user@example.com",
        recipient_name="Test User",
        subject=subject.format(idx=idx),
        body_text=f"Body content for email {idx}. Some extra words for analysis.",
        received_date=datetime(2024, 3, 1, 10, 0, 0) + timedelta(days=days_offset + idx),
        has_attachments=idx % 4 == 0,
    )


def _make_corpus(emails: list[Email]) -> Corpus:
    """Wrap a list of Email objects in a Corpus with metadata."""
    return Corpus(
        extraction_metadata=CorpusMetadata(
            extraction_date=datetime(2024, 3, 15, 12, 0, 0),
            total_emails=len(emails),
            source="contract-test",
            user_email="user@example.com",
        ),
        emails=emails,
    )


@pytest.fixture
def contract_emails():
    """Create 5 emails with varied senders and dates for contract tests."""
    return [
        _make_email(0, sender_email="alice@corp.com", sender_domain="corp.com"),
        _make_email(1, sender_email="bob@shop.com", sender_domain="shop.com"),
        _make_email(
            2,
            sender_email="noreply@alerts.com",
            sender_domain="alerts.com",
            subject="[Alert] System notification #{idx}",
        ),
        _make_email(3, sender_email="alice@corp.com", sender_domain="corp.com"),
        _make_email(4, sender_email="carol@news.com", sender_domain="news.com"),
    ]


@pytest.fixture
def contract_corpus(contract_emails):
    """Corpus wrapping the contract_emails list."""
    return _make_corpus(contract_emails)


@pytest.fixture
def single_email_corpus():
    """Corpus with exactly one email."""
    return _make_corpus([_make_email(0)])


@pytest.fixture
def empty_corpus():
    """Corpus with no emails."""
    return _make_corpus([])


def _instantiate(analyzer_cls):
    """Instantiate an analyzer with default args."""
    return analyzer_cls()


# -----------------------------------------------------------------------
# Parametrized Contract Tests
# -----------------------------------------------------------------------


@pytest.mark.parametrize("analyzer_cls", LIGHTWEIGHT_ANALYZERS)
class TestAnalyzerContract:
    """Verify every lightweight analyzer meets the BaseAnalyzer contract."""

    def test_inherits_base_analyzer(self, analyzer_cls):
        """All analyzers must be subclasses of BaseAnalyzer."""
        assert issubclass(analyzer_cls, BaseAnalyzer)

    def test_has_non_empty_name(self, analyzer_cls):
        """The name property must return a non-empty string."""
        analyzer = _instantiate(analyzer_cls)
        assert isinstance(analyzer.name, str)
        assert len(analyzer.name) > 0

    def test_name_is_human_readable(self, analyzer_cls):
        """Name should contain at least two words (e.g. 'Sender Analyzer')."""
        analyzer = _instantiate(analyzer_cls)
        assert " " in analyzer.name, (
            f"{analyzer_cls.__name__}.name should be human-readable "
            f"(multiple words), got: {analyzer.name!r}"
        )

    def test_analyze_returns_result(self, analyzer_cls, contract_corpus):
        """analyze(corpus) must return a non-None result."""
        analyzer = _instantiate(analyzer_cls)
        result = analyzer.analyze(contract_corpus)
        assert result is not None

    def test_analyze_result_type(self, analyzer_cls, contract_corpus):
        """analyze() result should be a recognized analysis result type."""
        analyzer = _instantiate(analyzer_cls)
        result = analyzer.analyze(contract_corpus)
        # Every concrete analyzer returns a specific Pydantic model or dataclass
        allowed_types = (
            SenderAnalysis,
            SubjectPatterns,
            TemporalPatterns,
            VolumeStats,
            ThreadAnalysisResult,
            list,  # SemanticAnalyzer/HierarchicalAnalyzer return list
        )
        assert isinstance(result, allowed_types), (
            f"{analyzer_cls.__name__}.analyze() returned unexpected type: {type(result).__name__}"
        )

    def test_empty_corpus_does_not_crash(self, analyzer_cls, empty_corpus):
        """analyze() with empty corpus must either raise or return a result (not crash)."""
        analyzer = _instantiate(analyzer_cls)
        try:
            result = analyzer.analyze(empty_corpus)
            # If it doesn't raise, it must return a non-None result
            assert result is not None
        except (ValueError, AnalysisError):
            pass  # Raising is also acceptable behavior

    def test_single_email_handled(self, analyzer_cls, single_email_corpus):
        """analyze() with a single-email corpus must not crash."""
        analyzer = _instantiate(analyzer_cls)
        result = analyzer.analyze(single_email_corpus)
        assert result is not None

    def test_supports_incremental_returns_bool(self, analyzer_cls):
        """supports_incremental() must return a bool."""
        analyzer = _instantiate(analyzer_cls)
        result = analyzer.supports_incremental()
        assert isinstance(result, bool)

    def test_analyze_accepts_progress_callback(self, analyzer_cls, contract_corpus):
        """analyze() must accept an optional progress_callback kwarg."""
        analyzer = _instantiate(analyzer_cls)
        callbacks_received = []

        def callback(current, total):
            callbacks_received.append((current, total))

        result = analyzer.analyze(contract_corpus, progress_callback=callback)
        assert result is not None
        # Callback invocation is optional, but the parameter must be accepted


# -----------------------------------------------------------------------
# Empty corpus behavior: strict vs. graceful
# -----------------------------------------------------------------------


@pytest.mark.parametrize("analyzer_cls", ANALYZERS_RAISING_ON_EMPTY)
class TestAnalyzerEmptyCorpusStrict:
    """Analyzers that must raise on empty corpus."""

    def test_empty_corpus_raises(self, analyzer_cls, empty_corpus):
        """These analyzers raise ValueError or AnalysisError on empty input."""
        analyzer = _instantiate(analyzer_cls)
        with pytest.raises((ValueError, AnalysisError)):
            analyzer.analyze(empty_corpus)


@pytest.mark.parametrize("analyzer_cls", ANALYZERS_GRACEFUL_ON_EMPTY)
class TestAnalyzerEmptyCorpusGraceful:
    """Analyzers that handle empty corpus without raising."""

    def test_empty_corpus_returns_result(self, analyzer_cls, empty_corpus):
        """These analyzers return a valid (empty/zero) result on empty input."""
        analyzer = _instantiate(analyzer_cls)
        result = analyzer.analyze(empty_corpus)
        assert result is not None


# -----------------------------------------------------------------------
# Analyzer-specific contract tests (non-parametrized)
# -----------------------------------------------------------------------


class TestSenderAnalyzerContract:
    """SenderAnalyzer-specific contract checks."""

    def test_returns_sender_analysis(self, contract_corpus):
        analyzer = SenderAnalyzer()
        result = analyzer.analyze(contract_corpus)
        assert isinstance(result, SenderAnalysis)

    def test_top_senders_populated(self, contract_corpus):
        analyzer = SenderAnalyzer()
        result = analyzer.analyze(contract_corpus)
        assert len(result.top_senders) > 0

    def test_unique_counts_positive(self, contract_corpus):
        analyzer = SenderAnalyzer()
        result = analyzer.analyze(contract_corpus)
        assert result.unique_senders > 0
        assert result.unique_domains > 0


class TestSubjectAnalyzerContract:
    """SubjectAnalyzer-specific contract checks."""

    def test_returns_subject_patterns(self, contract_corpus):
        analyzer = SubjectAnalyzer()
        result = analyzer.analyze(contract_corpus)
        assert isinstance(result, SubjectPatterns)

    def test_total_subjects_matches_corpus(self, contract_corpus):
        analyzer = SubjectAnalyzer()
        result = analyzer.analyze(contract_corpus)
        assert result.total_subjects_analyzed == len(contract_corpus.emails)


class TestTemporalAnalyzerContract:
    """TemporalAnalyzer-specific contract checks."""

    def test_returns_temporal_patterns(self, contract_corpus):
        analyzer = TemporalAnalyzer()
        result = analyzer.analyze(contract_corpus)
        assert isinstance(result, TemporalPatterns)

    def test_frequency_distribution_has_expected_keys(self, contract_corpus):
        analyzer = TemporalAnalyzer()
        result = analyzer.analyze(contract_corpus)
        expected_keys = {"one-time", "daily", "weekly", "monthly", "occasional"}
        assert set(result.frequency_distribution.keys()) == expected_keys


class TestVolumeAnalyzerContract:
    """VolumeAnalyzer-specific contract checks."""

    def test_returns_volume_stats(self, contract_corpus):
        analyzer = VolumeAnalyzer()
        result = analyzer.analyze(contract_corpus)
        assert isinstance(result, VolumeStats)

    def test_total_emails_matches_corpus(self, contract_corpus):
        analyzer = VolumeAnalyzer()
        result = analyzer.analyze(contract_corpus)
        assert result.total_emails == len(contract_corpus.emails)

    def test_emails_per_day_positive(self, contract_corpus):
        analyzer = VolumeAnalyzer()
        result = analyzer.analyze(contract_corpus)
        assert result.emails_per_day > 0


class TestThreadAnalyzerContract:
    """ThreadAnalyzer-specific contract checks."""

    def test_returns_thread_analysis_result(self, contract_corpus):
        analyzer = ThreadAnalyzer()
        result = analyzer.analyze(contract_corpus)
        assert isinstance(result, ThreadAnalysisResult)

    def test_total_threads_at_least_one(self, contract_corpus):
        analyzer = ThreadAnalyzer()
        result = analyzer.analyze(contract_corpus)
        assert result.total_threads >= 1

    def test_all_emails_assigned_to_threads(self, contract_corpus):
        """Every email in the corpus must appear in exactly one thread."""
        analyzer = ThreadAnalyzer()
        result = analyzer.analyze(contract_corpus)
        all_thread_email_ids = []
        for thread in result.threads.values():
            all_thread_email_ids.extend(thread.email_ids)
        corpus_ids = {email.id for email in contract_corpus.emails}
        thread_ids = set(all_thread_email_ids)
        assert corpus_ids == thread_ids, (
            f"Corpus emails not fully covered by threads. "
            f"Missing: {corpus_ids - thread_ids}, "
            f"Extra: {thread_ids - corpus_ids}"
        )

    def test_supports_incremental_false(self):
        """ThreadAnalyzer does not support incremental analysis."""
        analyzer = ThreadAnalyzer()
        assert analyzer.supports_incremental() is False


# -----------------------------------------------------------------------
# Cross-cutting contract: validate_input base method
# -----------------------------------------------------------------------


class TestBaseAnalyzerValidateInput:
    """Verify the base validate_input helper."""

    @pytest.mark.parametrize("analyzer_cls", LIGHTWEIGHT_ANALYZERS)
    def test_validate_input_raises_on_empty(self, analyzer_cls):
        """validate_input() should raise AnalysisError for empty list."""
        analyzer = _instantiate(analyzer_cls)
        with pytest.raises(AnalysisError):
            analyzer.validate_input([])

    @pytest.mark.parametrize("analyzer_cls", LIGHTWEIGHT_ANALYZERS)
    def test_validate_input_passes_for_non_empty(self, analyzer_cls, contract_emails):
        """validate_input() should not raise for a non-empty list."""
        analyzer = _instantiate(analyzer_cls)
        # Should not raise
        analyzer.validate_input(contract_emails)
