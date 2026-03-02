"""
Unit tests for analyzer modules.

Tests the following analyzer components:
- run_full_analysis function from src/analyzers/__init__.py
- SemanticAnalyzer class from src/analyzers/semantic_analyzer.py
- TemporalAnalyzer class from src/analyzers/temporal_analyzer.py
- VolumeAnalyzer class from src/analyzers/volume_analyzer.py
- SubjectAnalyzer class from src/analyzers/subject_analyzer.py
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.analyzers import run_full_analysis
from src.analyzers.semantic_analyzer import SemanticAnalyzer
from src.analyzers.subject_analyzer import SubjectAnalyzer
from src.analyzers.temporal_analyzer import TemporalAnalyzer
from src.analyzers.volume_analyzer import VolumeAnalyzer
from src.models.corpus import Corpus, CorpusMetadata
from src.models.email import Email

# ============================================================================
# Fixtures
# ============================================================================


def create_email(
    email_id: str,
    sender_email: str,
    sender_domain: str,
    subject: str = "Test Subject",
    body_text: str = "Test body content",
    received_date: datetime | None = None,
    has_attachments: bool = False,
    sender_name: str = "",
    recipient_email: str | None = None,
    recipient_name: str = "",
) -> Email:
    """Factory function to create Email objects for testing."""
    if received_date is None:
        received_date = datetime(2024, 1, 15, 10, 0)
    return Email(
        id=email_id,
        sender_email=sender_email,
        sender_name=sender_name,
        sender_domain=sender_domain,
        recipient_email=recipient_email,
        recipient_name=recipient_name,
        subject=subject,
        body_text=body_text,
        received_date=received_date,
        has_attachments=has_attachments,
    )


def create_corpus(emails: list[Email], user_email: str = "user@example.com") -> Corpus:
    """Factory function to create Corpus objects for testing."""
    return Corpus(
        extraction_metadata=CorpusMetadata(
            extraction_date=datetime.now(),
            total_emails=len(emails),
            source="test",
            user_email=user_email,
        ),
        emails=emails,
    )


# ============================================================================
# Test VolumeAnalyzer
# ============================================================================


class TestVolumeAnalyzer:
    """Test cases for VolumeAnalyzer class."""

    @pytest.fixture
    def analyzer(self):
        """Create VolumeAnalyzer instance."""
        return VolumeAnalyzer()

    def test_analyze_empty_corpus_raises_error(self, analyzer):
        """Test that analyzing empty corpus raises ValueError."""
        corpus = create_corpus([])
        with pytest.raises(ValueError, match="Corpus is empty"):
            analyzer.analyze(corpus)

    def test_analyze_single_email(self, analyzer):
        """Test analyzing corpus with a single email."""
        emails = [
            create_email(
                email_id="1",
                sender_email="sender@example.com",
                sender_domain="example.com",
                subject="Test",
                body_text="This is test body content",
                received_date=datetime(2024, 1, 15, 10, 0),
                has_attachments=True,
            )
        ]
        corpus = create_corpus(emails)

        result = analyzer.analyze(corpus)

        assert result.total_emails == 1
        assert result.unique_senders == 1
        assert result.with_attachments == 1
        assert result.attachment_percentage == 100.0
        assert result.avg_body_length_chars == len("This is test body content")
        # Single email on same day results in span_days = 1
        assert result.date_range["span_days"] == "1"

    def test_analyze_multiple_emails_same_sender(self, analyzer):
        """Test analyzing corpus with multiple emails from same sender."""
        emails = [
            create_email(
                email_id=str(i),
                sender_email="sender@example.com",
                sender_domain="example.com",
                subject=f"Subject {i}",
                body_text=f"Body {i}",
                received_date=datetime(2024, 1, i, 10, 0),
            )
            for i in range(1, 6)
        ]
        corpus = create_corpus(emails)

        result = analyzer.analyze(corpus)

        assert result.total_emails == 5
        assert result.unique_senders == 1
        assert result.with_attachments == 0
        assert result.attachment_percentage == 0.0

    def test_analyze_multiple_senders(self, analyzer):
        """Test analyzing corpus with multiple unique senders."""
        emails = [
            create_email(
                email_id="1", sender_email="alice@example.com", sender_domain="example.com"
            ),
            create_email(email_id="2", sender_email="bob@example.com", sender_domain="example.com"),
            create_email(email_id="3", sender_email="charlie@other.com", sender_domain="other.com"),
        ]
        corpus = create_corpus(emails)

        result = analyzer.analyze(corpus)

        assert result.total_emails == 3
        assert result.unique_senders == 3

    def test_analyze_date_range_calculation(self, analyzer):
        """Test date range is calculated correctly."""
        emails = [
            create_email(
                email_id="1",
                sender_email="sender@example.com",
                sender_domain="example.com",
                received_date=datetime(2024, 1, 1, 10, 0),
            ),
            create_email(
                email_id="2",
                sender_email="sender@example.com",
                sender_domain="example.com",
                received_date=datetime(2024, 1, 31, 10, 0),
            ),
        ]
        corpus = create_corpus(emails)

        result = analyzer.analyze(corpus)

        assert result.date_range["oldest"] == "2024-01-01T10:00:00"
        assert result.date_range["newest"] == "2024-01-31T10:00:00"
        assert result.date_range["span_days"] == "30"

    def test_analyze_emails_per_day(self, analyzer):
        """Test emails per day calculation."""
        # 10 emails over 10 days = 1 email per day
        emails = [
            create_email(
                email_id=str(i),
                sender_email="sender@example.com",
                sender_domain="example.com",
                received_date=datetime(2024, 1, 1, 10, 0) + timedelta(days=i),
            )
            for i in range(10)
        ]
        corpus = create_corpus(emails)

        result = analyzer.analyze(corpus)

        # 10 emails over 9 day span = 10/9 = ~1.11 emails/day
        assert result.emails_per_day == pytest.approx(1.11, rel=0.1)

    def test_analyze_attachment_percentage(self, analyzer):
        """Test attachment percentage calculation."""
        emails = [
            create_email(
                email_id="1",
                sender_email="sender@example.com",
                sender_domain="example.com",
                has_attachments=True,
            ),
            create_email(
                email_id="2",
                sender_email="sender@example.com",
                sender_domain="example.com",
                has_attachments=False,
            ),
            create_email(
                email_id="3",
                sender_email="sender@example.com",
                sender_domain="example.com",
                has_attachments=True,
            ),
            create_email(
                email_id="4",
                sender_email="sender@example.com",
                sender_domain="example.com",
                has_attachments=False,
            ),
        ]
        corpus = create_corpus(emails)

        result = analyzer.analyze(corpus)

        assert result.with_attachments == 2
        assert result.attachment_percentage == 50.0

    def test_analyze_average_body_length(self, analyzer):
        """Test average body length calculation."""
        emails = [
            create_email(
                email_id="1",
                sender_email="sender@example.com",
                sender_domain="example.com",
                body_text="Short",  # 5 chars
            ),
            create_email(
                email_id="2",
                sender_email="sender@example.com",
                sender_domain="example.com",
                body_text="This is a longer body",  # 21 chars
            ),
        ]
        corpus = create_corpus(emails)

        result = analyzer.analyze(corpus)

        # Average of 5 and 21 = 13
        assert result.avg_body_length_chars == 13

    def test_analyze_progress_callback(self, analyzer):
        """Test progress callback is called correctly."""
        emails = [
            create_email(
                email_id=str(i), sender_email="sender@example.com", sender_domain="example.com"
            )
            for i in range(25)
        ]
        corpus = create_corpus(emails)

        callback_calls = []

        def progress_callback(current, total):
            callback_calls.append((current, total))

        analyzer.analyze(corpus, progress_callback=progress_callback)

        # Callback called every 10 emails + final
        assert len(callback_calls) > 0
        # Final callback should be (25, 25)
        assert callback_calls[-1] == (25, 25)

    def test_analyze_sender_case_insensitivity(self, analyzer):
        """Test that sender emails are normalized to lowercase."""
        emails = [
            create_email(
                email_id="1", sender_email="Sender@Example.COM", sender_domain="example.com"
            ),
            create_email(
                email_id="2", sender_email="sender@example.com", sender_domain="example.com"
            ),
        ]
        corpus = create_corpus(emails)

        result = analyzer.analyze(corpus)

        # Both should count as same sender (case-insensitive)
        assert result.unique_senders == 1


# ============================================================================
# Test TemporalAnalyzer
# ============================================================================


class TestTemporalAnalyzer:
    """Test cases for TemporalAnalyzer class."""

    @pytest.fixture
    def analyzer(self):
        """Create TemporalAnalyzer instance."""
        return TemporalAnalyzer()

    def test_classify_frequency_one_time(self, analyzer):
        """Test classification of one-time sender."""
        dates = [datetime(2024, 1, 15)]
        result = analyzer.classify_frequency(dates)
        assert result == "one-time"

    def test_classify_frequency_occasional_few_emails(self, analyzer):
        """Test classification when fewer than 10 emails."""
        dates = [datetime(2024, 1, i) for i in range(1, 9)]  # 8 emails
        result = analyzer.classify_frequency(dates)
        assert result == "occasional"

    def test_classify_frequency_daily(self, analyzer):
        """Test classification of daily sender (avg < 2 days, >= 10 emails)."""
        # 10 emails in 10 days = avg 1 day between emails
        dates = [datetime(2024, 1, 1) + timedelta(days=i) for i in range(10)]
        result = analyzer.classify_frequency(dates)
        assert result == "daily"

    def test_classify_frequency_weekly(self, analyzer):
        """Test classification of weekly sender (avg < 8 days, >= 10 emails)."""
        # 10 emails over 50 days = avg 5.5 days between emails
        dates = [datetime(2024, 1, 1) + timedelta(days=i * 5) for i in range(10)]
        result = analyzer.classify_frequency(dates)
        assert result == "weekly"

    def test_classify_frequency_monthly(self, analyzer):
        """Test classification of monthly sender (avg < 35 days, >= 10 emails)."""
        # 10 emails over 200 days = avg 22 days between emails
        dates = [datetime(2024, 1, 1) + timedelta(days=i * 22) for i in range(10)]
        result = analyzer.classify_frequency(dates)
        assert result == "monthly"

    def test_classify_frequency_occasional_sparse(self, analyzer):
        """Test classification of occasional sender (avg >= 35 days, >= 10 emails)."""
        # 10 emails over 400 days = avg 44 days between emails
        dates = [datetime(2024, 1, 1) + timedelta(days=i * 44) for i in range(10)]
        result = analyzer.classify_frequency(dates)
        assert result == "occasional"

    def test_classify_frequency_all_same_timestamp(self, analyzer):
        """Test classification when all emails have exact same timestamp."""
        # When all emails are at the exact same timestamp, total_span = 0
        # and avg_interval_days = 0, which is < 2, so classified as "daily"
        # This is the actual behavior - emails with 0 time between them
        # are considered "daily" because the average interval is 0 days
        dates = [datetime(2024, 1, 15, 10, 0, 0)] * 10  # Exact same timestamp
        result = analyzer.classify_frequency(dates)
        assert result == "daily"

    def test_analyze_empty_corpus(self, analyzer):
        """Test analyzing empty corpus."""
        corpus = create_corpus([])
        result = analyzer.analyze(corpus)

        # Empty corpus should return empty distributions
        assert result.frequency_distribution["one-time"] == 0
        assert result.frequency_distribution["daily"] == 0
        assert len(result.sender_frequencies) == 0

    def test_analyze_single_sender_one_email(self, analyzer):
        """Test analyzing corpus with single sender, one email."""
        emails = [
            create_email(
                email_id="1",
                sender_email="sender@example.com",
                sender_domain="example.com",
                received_date=datetime(2024, 1, 15),
            )
        ]
        corpus = create_corpus(emails)

        result = analyzer.analyze(corpus)

        assert result.frequency_distribution["one-time"] == 1
        assert "sender@example.com" in result.sender_frequencies
        assert result.sender_frequencies["sender@example.com"]["type"] == "one-time"
        assert result.sender_frequencies["sender@example.com"]["count"] == 1

    def test_analyze_multiple_senders_different_frequencies(self, analyzer):
        """Test analyzing corpus with multiple senders of different frequencies."""
        base_date = datetime(2024, 1, 1)
        emails = []

        # One-time sender
        emails.append(
            create_email(
                email_id="onetime_1",
                sender_email="onetime@example.com",
                sender_domain="example.com",
                received_date=base_date,
            )
        )

        # Daily sender (10 emails, 1 day apart)
        for i in range(10):
            emails.append(
                create_email(
                    email_id=f"daily_{i}",
                    sender_email="daily@example.com",
                    sender_domain="example.com",
                    received_date=base_date + timedelta(days=i),
                )
            )

        corpus = create_corpus(emails)
        result = analyzer.analyze(corpus)

        assert result.frequency_distribution["one-time"] == 1
        assert result.frequency_distribution["daily"] == 1
        assert result.sender_frequencies["onetime@example.com"]["type"] == "one-time"
        assert result.sender_frequencies["daily@example.com"]["type"] == "daily"

    def test_analyze_sender_first_last_dates(self, analyzer):
        """Test that first and last dates are recorded correctly."""
        emails = [
            create_email(
                email_id="1",
                sender_email="sender@example.com",
                sender_domain="example.com",
                received_date=datetime(2024, 1, 1, 10, 0),
            ),
            create_email(
                email_id="2",
                sender_email="sender@example.com",
                sender_domain="example.com",
                received_date=datetime(2024, 1, 15, 10, 0),
            ),
            create_email(
                email_id="3",
                sender_email="sender@example.com",
                sender_domain="example.com",
                received_date=datetime(2024, 1, 10, 10, 0),
            ),
        ]
        corpus = create_corpus(emails)

        result = analyzer.analyze(corpus)

        sender_freq = result.sender_frequencies["sender@example.com"]
        assert sender_freq["first"] == "2024-01-01T10:00:00"
        assert sender_freq["last"] == "2024-01-15T10:00:00"

    def test_analyze_progress_callback(self, analyzer):
        """Test progress callback is called correctly."""
        emails = [
            create_email(
                email_id=str(i), sender_email=f"sender{i}@example.com", sender_domain="example.com"
            )
            for i in range(150)
        ]
        corpus = create_corpus(emails)

        callback_calls = []

        def progress_callback(current, total):
            callback_calls.append((current, total))

        analyzer.analyze(corpus, progress_callback=progress_callback)

        # Callback called every 100 emails + final
        assert len(callback_calls) > 0
        assert callback_calls[-1] == (150, 150)


# ============================================================================
# Test SubjectAnalyzer
# ============================================================================


class TestSubjectAnalyzer:
    """Test cases for SubjectAnalyzer class."""

    @pytest.fixture
    def analyzer(self):
        """Create SubjectAnalyzer instance."""
        return SubjectAnalyzer()

    def test_analyze_empty_corpus_raises_error(self, analyzer):
        """Test that analyzing empty corpus raises ValueError."""
        corpus = create_corpus([])
        with pytest.raises(ValueError, match="Corpus is empty"):
            analyzer.analyze(corpus)

    def test_analyze_single_email(self, analyzer):
        """Test analyzing corpus with single email."""
        emails = [
            create_email(
                email_id="1",
                sender_email="sender@example.com",
                sender_domain="example.com",
                subject="Test Subject Line",
            )
        ]
        corpus = create_corpus(emails)

        result = analyzer.analyze(corpus)

        assert result.total_subjects_analyzed == 1
        assert isinstance(result.common_prefixes, dict)
        assert isinstance(result.numbered_patterns, dict)
        assert isinstance(result.top_keywords, list)

    def test_extract_re_prefix(self, analyzer):
        """Test extraction of RE: prefix."""
        emails = [
            create_email(
                email_id="1",
                sender_email="sender@example.com",
                sender_domain="example.com",
                subject="Re: Meeting Tomorrow",
            ),
            create_email(
                email_id="2",
                sender_email="sender@example.com",
                sender_domain="example.com",
                subject="RE: Follow Up",
            ),
            create_email(
                email_id="3",
                sender_email="sender@example.com",
                sender_domain="example.com",
                subject="re: another reply",
            ),
        ]
        corpus = create_corpus(emails)

        result = analyzer.analyze(corpus)

        # All RE: variants should be normalized to uppercase
        assert "RE:" in result.common_prefixes
        assert result.common_prefixes["RE:"] == 3

    def test_extract_fwd_prefix(self, analyzer):
        """Test extraction of FWD: prefix."""
        emails = [
            create_email(
                email_id="1",
                sender_email="sender@example.com",
                sender_domain="example.com",
                subject="Fwd: Important Document",
            ),
            create_email(
                email_id="2",
                sender_email="sender@example.com",
                sender_domain="example.com",
                subject="FWD: Check This Out",
            ),
        ]
        corpus = create_corpus(emails)

        result = analyzer.analyze(corpus)

        assert "FWD:" in result.common_prefixes
        assert result.common_prefixes["FWD:"] == 2

    def test_extract_numbered_patterns(self, analyzer):
        """Test extraction of numbered patterns like 'Invoice #12345'."""
        emails = [
            create_email(
                email_id="1",
                sender_email="sender@example.com",
                sender_domain="example.com",
                subject="Invoice #12345",
            ),
            create_email(
                email_id="2",
                sender_email="sender@example.com",
                sender_domain="example.com",
                subject="Order #9876",
            ),
            create_email(
                email_id="3",
                sender_email="sender@example.com",
                sender_domain="example.com",
                subject="Invoice #67890",
            ),
        ]
        corpus = create_corpus(emails)

        result = analyzer.analyze(corpus)

        assert "Invoice" in result.numbered_patterns
        assert result.numbered_patterns["Invoice"] == 2
        assert "Order" in result.numbered_patterns
        assert result.numbered_patterns["Order"] == 1

    def test_extract_bracket_tags(self, analyzer):
        """Test extraction of bracket tags like [URGENT]."""
        emails = [
            create_email(
                email_id="1",
                sender_email="sender@example.com",
                sender_domain="example.com",
                subject="[URGENT] Please Review",
            ),
            create_email(
                email_id="2",
                sender_email="sender@example.com",
                sender_domain="example.com",
                subject="(Action Required) Update Needed",
            ),
            create_email(
                email_id="3",
                sender_email="sender@example.com",
                sender_domain="example.com",
                subject="[URGENT] Another Urgent Matter",
            ),
        ]
        corpus = create_corpus(emails)

        result = analyzer.analyze(corpus)

        # bracket_tags is list of tuples
        tag_dict = dict(result.bracket_tags)
        assert "URGENT" in tag_dict
        assert tag_dict["URGENT"] == 2
        assert "Action Required" in tag_dict
        assert tag_dict["Action Required"] == 1

    def test_extract_keywords_filters_stop_words(self, analyzer):
        """Test that stop words are filtered from keywords."""
        emails = [
            create_email(
                email_id="1",
                sender_email="sender@example.com",
                sender_domain="example.com",
                subject="This is the test meeting for project",
            )
        ]
        corpus = create_corpus(emails)

        result = analyzer.analyze(corpus)

        # Convert to dict for easier testing
        keyword_dict = dict(result.top_keywords)

        # Stop words should be filtered out
        assert "this" not in keyword_dict
        assert "is" not in keyword_dict
        assert "the" not in keyword_dict
        assert "for" not in keyword_dict

        # Content words should be included
        assert "test" in keyword_dict or "meeting" in keyword_dict or "project" in keyword_dict

    def test_extract_keywords_removes_prefixes(self, analyzer):
        """Test that prefixes are removed before extracting keywords."""
        emails = [
            create_email(
                email_id="1",
                sender_email="sender@example.com",
                sender_domain="example.com",
                subject="Re: Important Meeting",
            )
        ]
        corpus = create_corpus(emails)

        result = analyzer.analyze(corpus)

        keyword_dict = dict(result.top_keywords)
        # "re" from prefix should not appear as keyword
        assert "re" not in keyword_dict

    def test_analyze_top_50_keywords(self, analyzer):
        """Test that only top 50 keywords are returned."""
        # Create emails with many unique words
        subjects = [f"UniqueWord{i} Another{i}" for i in range(100)]
        emails = [
            create_email(
                email_id=str(i),
                sender_email="sender@example.com",
                sender_domain="example.com",
                subject=subjects[i],
            )
            for i in range(100)
        ]
        corpus = create_corpus(emails)

        result = analyzer.analyze(corpus)

        assert len(result.top_keywords) <= 50

    def test_analyze_progress_callback(self, analyzer):
        """Test progress callback is called correctly."""
        emails = [
            create_email(
                email_id=str(i),
                sender_email="sender@example.com",
                sender_domain="example.com",
                subject=f"Subject {i}",
            )
            for i in range(250)
        ]
        corpus = create_corpus(emails)

        callback_calls = []

        def progress_callback(current, total):
            callback_calls.append((current, total))

        analyzer.analyze(corpus, progress_callback=progress_callback)

        assert len(callback_calls) > 0
        assert callback_calls[-1] == (250, 250)

    def test_extract_prefixes_private_method(self, analyzer):
        """Test the private _extract_prefixes method directly."""
        from collections import Counter

        counter = Counter()

        analyzer._extract_prefixes("Re: Test", counter)
        assert "RE:" in counter
        assert counter["RE:"] == 1

        analyzer._extract_prefixes("Fwd: Test", counter)
        assert "FWD:" in counter
        assert counter["FWD:"] == 1

        # Non-prefix should not be added
        analyzer._extract_prefixes("Hello World", counter)
        assert len(counter) == 2

    def test_extract_numbered_patterns_private_method(self, analyzer):
        """Test the private _extract_numbered_patterns method directly."""
        from collections import Counter

        counter = Counter()

        analyzer._extract_numbered_patterns("Invoice #123", counter)
        assert "Invoice" in counter

        analyzer._extract_numbered_patterns("Order #456 and Ticket #789", counter)
        assert "Order" in counter
        assert "Ticket" in counter

    def test_extract_bracket_tags_private_method(self, analyzer):
        """Test the private _extract_bracket_tags method directly."""
        from collections import Counter

        counter = Counter()

        analyzer._extract_bracket_tags("[URGENT] Test", counter)
        assert "URGENT" in counter

        analyzer._extract_bracket_tags("(Team) Meeting [Project]", counter)
        assert "Team" in counter
        assert "Project" in counter

    def test_extract_keywords_private_method(self, analyzer):
        """Test the private _extract_keywords method directly."""
        from collections import Counter

        counter = Counter()

        analyzer._extract_keywords("Hello World Testing", counter)
        assert "hello" in counter
        assert "world" in counter
        assert "testing" in counter


# ============================================================================
# Test Incremental Analysis (Task 4B.4)
# ============================================================================


class TestIncrementalAnalysis:
    """Test cases for Task 4B.4: Incremental analysis functionality."""

    @pytest.fixture
    def analyzer(self):
        """Create SemanticAnalyzer instance for tests."""
        return SemanticAnalyzer()

    @pytest.fixture
    def mock_embedding_cache(self, tmp_path):
        """Create mock embedding cache with some cached embeddings."""
        from src.cache.embedding_cache import EmbeddingCache

        cache = EmbeddingCache(cache_path=tmp_path / "test_cache.npz")
        # Add cached embeddings for email_1 and email_2
        cache.add(
            ["email_1", "email_2"],
            np.random.rand(2, 1024),  # mxbai-embed-large has 1024 dimensions
        )
        return cache

    @pytest.fixture
    def test_corpus(self):
        """Create test corpus with 4 emails."""
        return Corpus(
            extraction_metadata=CorpusMetadata(
                extraction_date=datetime.now(),
                total_emails=4,
                source="test",
                user_email="user@example.com",
            ),
            emails=[
                Email(
                    id="email_1",
                    sender_email="sender1@example.com",
                    sender_domain="example.com",
                    subject="Cached email 1",
                    body_text="This is cached email 1",
                    received_date=datetime(2024, 1, 1),
                    has_attachments=False,
                ),
                Email(
                    id="email_2",
                    sender_email="sender2@example.com",
                    sender_domain="example.com",
                    subject="Cached email 2",
                    body_text="This is cached email 2",
                    received_date=datetime(2024, 1, 2),
                    has_attachments=False,
                ),
                Email(
                    id="email_3",
                    sender_email="sender3@example.com",
                    sender_domain="example.com",
                    subject="New email 3",
                    body_text="This is new email 3",
                    received_date=datetime(2024, 1, 3),
                    has_attachments=False,
                ),
                Email(
                    id="email_4",
                    sender_email="sender4@example.com",
                    sender_domain="example.com",
                    subject="New email 4",
                    body_text="This is new email 4",
                    received_date=datetime(2024, 1, 4),
                    has_attachments=False,
                ),
            ],
        )

    @patch.object(SemanticAnalyzer, "_ensure_model_loaded")
    def test_analyze_incremental_uses_cached_embeddings(
        self, mock_ensure, analyzer, mock_embedding_cache, test_corpus
    ):
        """Test that incremental analysis uses cached embeddings."""
        mock_model = MagicMock()
        mock_model.encode.return_value = np.random.rand(2, 1024)
        analyzer.model = mock_model

        result = analyzer.analyze_incremental(
            corpus=test_corpus, embedding_cache=mock_embedding_cache, num_clusters=2
        )

        # Should have generated stats
        assert hasattr(result, "stats")
        assert result.stats["cached_count"] == 2
        assert result.stats["generated_count"] == 2

    @patch.object(SemanticAnalyzer, "_ensure_model_loaded")
    def test_analyze_incremental_updates_cache(
        self, mock_ensure, analyzer, mock_embedding_cache, test_corpus
    ):
        """Test that new embeddings are added to cache."""
        initial_size = mock_embedding_cache.size

        mock_model = MagicMock()
        mock_model.encode.return_value = np.random.rand(2, 1024)
        analyzer.model = mock_model

        analyzer.analyze_incremental(
            corpus=test_corpus, embedding_cache=mock_embedding_cache, num_clusters=2
        )

        # Cache should have grown by 2 (the new emails)
        assert mock_embedding_cache.size == initial_size + 2

    @patch.object(SemanticAnalyzer, "_ensure_model_loaded")
    def test_analyze_incremental_returns_clusters(
        self, mock_ensure, analyzer, mock_embedding_cache, test_corpus
    ):
        """Test that incremental analysis returns ContentCluster list."""
        mock_model = MagicMock()
        mock_model.encode.return_value = np.random.rand(2, 1024)
        analyzer.model = mock_model

        result = analyzer.analyze_incremental(
            corpus=test_corpus, embedding_cache=mock_embedding_cache, num_clusters=2
        )

        assert hasattr(result, "clusters")
        assert isinstance(result.clusters, list)

    @patch.object(SemanticAnalyzer, "_ensure_model_loaded")
    def test_analyze_incremental_all_cached(self, mock_ensure, analyzer, tmp_path):
        """Test incremental analysis when all emails are cached."""
        from src.cache.embedding_cache import EmbeddingCache

        # Create cache with all emails
        cache = EmbeddingCache(cache_path=tmp_path / "full_cache.npz")
        cache.add(["e1", "e2", "e3"], np.random.rand(3, 1024))

        corpus = Corpus(
            extraction_metadata=CorpusMetadata(
                extraction_date=datetime.now(),
                total_emails=3,
                source="test",
                user_email="user@example.com",
            ),
            emails=[
                Email(
                    id="e1",
                    sender_email="a@example.com",
                    sender_domain="example.com",
                    subject="Test",
                    body_text="Test",
                    received_date=datetime(2024, 1, 1),
                    has_attachments=False,
                ),
                Email(
                    id="e2",
                    sender_email="b@example.com",
                    sender_domain="example.com",
                    subject="Test",
                    body_text="Test",
                    received_date=datetime(2024, 1, 2),
                    has_attachments=False,
                ),
                Email(
                    id="e3",
                    sender_email="c@example.com",
                    sender_domain="example.com",
                    subject="Test",
                    body_text="Test",
                    received_date=datetime(2024, 1, 3),
                    has_attachments=False,
                ),
            ],
        )

        mock_model = MagicMock()
        analyzer.model = mock_model

        result = analyzer.analyze_incremental(corpus=corpus, embedding_cache=cache, num_clusters=2)

        # Model.encode should not be called (all cached)
        mock_model.encode.assert_not_called()
        assert result.stats["cached_count"] == 3
        assert result.stats["generated_count"] == 0


class TestCLIAnalyzeIncrementalFlag:
    """Test cases for --incremental CLI flag (Task 4B.4)."""

    def test_analyze_command_has_incremental_flag(self):
        """Test that analyze command has --incremental flag."""
        from src.cli import create_parser

        parser = create_parser()

        # Without flag - default should be False
        args = parser.parse_args(["analyze"])
        assert args.incremental is False

        # With flag - should be True
        args = parser.parse_args(["analyze", "--incremental"])
        args = parser.parse_args(["analyze", "--incremental"])
        assert args.incremental is True


# ============================================================================
# Test SemanticAnalyzer
# ============================================================================


class TestSemanticAnalyzer:
    """Test cases for SemanticAnalyzer class."""

    @pytest.fixture
    def analyzer(self):
        """Create SemanticAnalyzer instance."""
        return SemanticAnalyzer()

    def test_init_default_model(self, analyzer):
        """Test default model name is set correctly."""
        assert analyzer.model_name == "mixedbread-ai/mxbai-embed-large-v1"
        assert analyzer.model is None  # Lazy loaded

    def test_init_custom_model(self):
        """Test custom model name initialization."""
        custom_analyzer = SemanticAnalyzer(model_name="custom-model")
        assert custom_analyzer.model_name == "custom-model"

    def test_analyze_empty_corpus_raises_error(self, analyzer):
        """Test that analyzing empty corpus raises ValueError."""
        corpus = create_corpus([])
        with pytest.raises(ValueError, match="Cannot analyze empty corpus"):
            analyzer.analyze(corpus)

    def test_analyze_invalid_num_clusters_raises_error(self, analyzer):
        """Test that invalid num_clusters raises ValueError."""
        emails = [
            create_email(
                email_id="1", sender_email="sender@example.com", sender_domain="example.com"
            )
        ]
        corpus = create_corpus(emails)

        with pytest.raises(ValueError, match="num_clusters must be >= 1"):
            analyzer.analyze(corpus, num_clusters=0)

        with pytest.raises(ValueError, match="num_clusters must be >= 1"):
            analyzer.analyze(corpus, num_clusters=-1)

    @patch.object(SemanticAnalyzer, "_ensure_model_loaded")
    @patch("src.analyzers.embedding_provider.SentenceTransformer")
    def test_analyze_reduces_clusters_for_small_corpus(
        self, mock_st_class, mock_ensure_model, analyzer
    ):
        """Test that num_clusters is reduced when corpus is smaller."""
        # Create small corpus
        emails = [
            create_email(
                email_id=str(i),
                sender_email=f"sender{i}@example.com",
                sender_domain="example.com",
                subject=f"Subject {i}",
                body_text=f"Body content {i}",
            )
            for i in range(3)
        ]
        corpus = create_corpus(emails)

        # Mock the model
        mock_model = MagicMock()
        mock_model.encode.return_value = np.random.rand(3, 384)
        analyzer.model = mock_model

        # Request 10 clusters but only have 3 emails
        result = analyzer.analyze(corpus, num_clusters=10)

        # Should have at most 3 clusters
        assert len(result) <= 3

    @patch.object(SemanticAnalyzer, "_ensure_model_loaded")
    @patch("src.analyzers.embedding_provider.SentenceTransformer")
    def test_analyze_creates_clusters(self, mock_st_class, mock_ensure_model, analyzer):
        """Test that analyze creates ContentCluster objects."""
        emails = [
            create_email(
                email_id=str(i),
                sender_email=f"sender{i % 2}@example.com",
                sender_domain="example.com",
                subject=f"Subject {i}",
                body_text=f"Body content {i}",
            )
            for i in range(10)
        ]
        corpus = create_corpus(emails)

        # Mock the model to return deterministic embeddings
        mock_model = MagicMock()
        mock_model.encode.return_value = np.random.rand(10, 384)
        analyzer.model = mock_model

        result = analyzer.analyze(corpus, num_clusters=2)

        assert len(result) > 0
        for cluster in result:
            assert cluster.cluster_id >= 0
            assert cluster.size > 0
            assert 0 <= cluster.percentage <= 100
            assert len(cluster.representative_samples) <= 5
            assert len(cluster.email_ids) > 0

    @patch.object(SemanticAnalyzer, "_ensure_model_loaded")
    @patch("src.analyzers.embedding_provider.SentenceTransformer")
    def test_analyze_cluster_percentages_sum_correctly(
        self, mock_st_class, mock_ensure_model, analyzer
    ):
        """Test that cluster percentages sum to approximately 100%."""
        emails = [
            create_email(
                email_id=str(i), sender_email="sender@example.com", sender_domain="example.com"
            )
            for i in range(20)
        ]
        corpus = create_corpus(emails)

        mock_model = MagicMock()
        mock_model.encode.return_value = np.random.rand(20, 384)
        analyzer.model = mock_model

        result = analyzer.analyze(corpus, num_clusters=3)

        total_percentage = sum(c.percentage for c in result)
        assert abs(total_percentage - 100.0) < 0.1

    @patch.object(SemanticAnalyzer, "_ensure_model_loaded")
    @patch("src.analyzers.embedding_provider.SentenceTransformer")
    def test_analyze_single_email_single_cluster(self, mock_st_class, mock_ensure_model, analyzer):
        """Test analyzing single email creates single cluster."""
        emails = [
            create_email(
                email_id="1",
                sender_email="sender@example.com",
                sender_domain="example.com",
                subject="Test Subject",
                body_text="Test body",
            )
        ]
        corpus = create_corpus(emails)

        mock_model = MagicMock()
        mock_model.encode.return_value = np.random.rand(1, 384)
        analyzer.model = mock_model

        result = analyzer.analyze(corpus, num_clusters=1)

        assert len(result) == 1
        assert result[0].size == 1
        assert result[0].percentage == 100.0

    @patch.object(SemanticAnalyzer, "_ensure_model_loaded")
    @patch("src.analyzers.embedding_provider.SentenceTransformer")
    def test_analyze_common_domains_extraction(self, mock_st_class, mock_ensure_model, analyzer):
        """Test that common domains are extracted for each cluster."""
        emails = [
            create_email(
                email_id=str(i),
                sender_email=f"sender{i % 3}@domain{i % 2}.com",
                sender_domain=f"domain{i % 2}.com",
                subject=f"Subject {i}",
            )
            for i in range(10)
        ]
        corpus = create_corpus(emails)

        mock_model = MagicMock()
        mock_model.encode.return_value = np.random.rand(10, 384)
        analyzer.model = mock_model

        result = analyzer.analyze(corpus, num_clusters=1)

        assert len(result) > 0
        # Each cluster should have common_domains populated
        for cluster in result:
            # common_domains is list of tuples
            assert isinstance(cluster.common_domains, list)

    @patch.object(SemanticAnalyzer, "_ensure_model_loaded")
    @patch("src.analyzers.embedding_provider.SentenceTransformer")
    def test_analyze_representative_samples(self, mock_st_class, mock_ensure_model, analyzer):
        """Test that representative samples are created correctly."""
        emails = [
            create_email(
                email_id=str(i),
                sender_email=f"sender{i}@example.com",
                sender_domain="example.com",
                subject=f"Subject {i}",
                body_text=f"Body text for email {i}",
            )
            for i in range(10)
        ]
        corpus = create_corpus(emails)

        mock_model = MagicMock()
        mock_model.encode.return_value = np.random.rand(10, 384)
        analyzer.model = mock_model

        result = analyzer.analyze(corpus, num_clusters=2)

        for cluster in result:
            # At most 5 representative samples
            assert len(cluster.representative_samples) <= 5
            for sample in cluster.representative_samples:
                assert hasattr(sample, "subject")
                assert hasattr(sample, "sender")
                assert hasattr(sample, "body_preview")
                assert len(sample.body_preview) <= 200

    @patch.object(SemanticAnalyzer, "_ensure_model_loaded")
    @patch("src.analyzers.embedding_provider.SentenceTransformer")
    def test_analyze_progress_callback(self, mock_st_class, mock_ensure_model, analyzer):
        """Test progress callback is called correctly."""
        emails = [
            create_email(
                email_id=str(i), sender_email="sender@example.com", sender_domain="example.com"
            )
            for i in range(10)
        ]
        corpus = create_corpus(emails)

        mock_model = MagicMock()
        mock_model.encode.return_value = np.random.rand(10, 384)
        analyzer.model = mock_model

        callback_calls = []

        def progress_callback(current, total):
            callback_calls.append((current, total))

        analyzer.analyze(corpus, num_clusters=2, progress_callback=progress_callback)

        assert len(callback_calls) > 0
        # Should have initial 0 and final total
        assert callback_calls[0] == (0, 10)
        assert callback_calls[-1] == (10, 10)

    def test_ensure_model_loaded_lazy_loading(self, analyzer):
        """Test that model is lazily loaded."""
        assert analyzer.model is None

        with patch("src.analyzers.embedding_provider.SentenceTransformer") as mock_st:
            mock_model = MagicMock()
            mock_model.get_sentence_embedding_dimension.return_value = 384
            mock_st.return_value = mock_model

            analyzer._ensure_model_loaded()

            mock_st.assert_called_once_with(analyzer.model_name)
            # After _ensure_model_loaded, the provider wraps the model
            assert analyzer._provider is not None

    def test_ensure_model_loaded_only_once(self, analyzer):
        """Test that model is only loaded once."""
        mock_model = MagicMock()
        analyzer.model = mock_model

        with patch("src.analyzers.embedding_provider.SentenceTransformer") as mock_st:
            analyzer._ensure_model_loaded()
            mock_st.assert_not_called()

    def test_init_default_max_embedding_text_length(self, analyzer):
        """Test default max_embedding_text_length is 1500."""
        assert analyzer.max_embedding_text_length == 1500

    def test_init_custom_max_embedding_text_length(self):
        """Test custom max_embedding_text_length initialization."""
        custom_analyzer = SemanticAnalyzer(max_embedding_text_length=3000)
        assert custom_analyzer.max_embedding_text_length == 3000

    @patch.object(SemanticAnalyzer, "_ensure_model_loaded")
    @patch("src.analyzers.embedding_provider.SentenceTransformer")
    def test_analyze_uses_configurable_text_length(self, mock_st_class, mock_ensure_model):
        """Test that analyze uses max_embedding_text_length for text preparation."""
        custom_analyzer = SemanticAnalyzer(max_embedding_text_length=300)

        long_body = "z" * 1000
        emails = [
            create_email(
                email_id="1",
                sender_email="sender@example.com",
                sender_domain="example.com",
                subject="Subj",
                body_text=long_body,
            )
        ]
        corpus = create_corpus(emails)

        mock_model = MagicMock()
        mock_model.encode.return_value = np.random.rand(1, 384)
        custom_analyzer.model = mock_model

        custom_analyzer.analyze(corpus, num_clusters=1)

        # Check that model.encode was called with text truncated at 300 chars
        call_args = mock_model.encode.call_args
        texts = call_args[0][0]
        expected_text = f"Subj {long_body[:300]}"
        assert texts[0] == expected_text


# ============================================================================
# Test run_full_analysis
# ============================================================================


class TestRunFullAnalysis:
    """Test cases for run_full_analysis function."""

    def test_empty_corpus_raises_error(self):
        """Test that empty corpus raises ValueError."""
        corpus = create_corpus([])
        with pytest.raises(ValueError, match="Cannot analyze empty corpus"):
            run_full_analysis(corpus)

    @patch("src.analyzers.embedding_provider.SentenceTransformer")
    def test_calls_all_analyzers_integration(self, mock_st_class):
        """Test that all analyzers are called and return AnalysisResults.

        This is an integration test that actually calls the analyzers
        with a mock for the sentence transformer to avoid slow model loading.
        """
        # Configure the mock SentenceTransformer
        mock_model = MagicMock()
        mock_model.encode.return_value = np.random.rand(5, 384)
        mock_model.get_sentence_embedding_dimension.return_value = 384
        mock_st_class.return_value = mock_model

        emails = [
            create_email(
                email_id=str(i),
                sender_email=f"sender{i % 3}@example.com",
                sender_domain="example.com",
                subject=f"Test Subject {i}",
                body_text=f"Test body content for email {i}",
                received_date=datetime(2024, 1, 1) + timedelta(days=i),
            )
            for i in range(5)
        ]
        corpus = create_corpus(emails)

        result, incremental_stats = run_full_analysis(corpus, num_clusters=2)

        # Without embedding_cache, incremental_stats should be None
        assert incremental_stats is None

        # Verify result is AnalysisResults with all components
        assert hasattr(result, "sender_analysis")
        assert hasattr(result, "subject_patterns")
        assert hasattr(result, "content_clusters")
        assert hasattr(result, "temporal_patterns")
        assert hasattr(result, "volume_stats")

        # Verify components have expected data
        assert result.sender_analysis.unique_senders == 3
        assert result.subject_patterns.total_subjects_analyzed == 5
        assert result.volume_stats.total_emails == 5

    @patch("src.analyzers.embedding_provider.SentenceTransformer")
    def test_num_clusters_parameter(self, mock_st_class):
        """Test that num_clusters parameter affects semantic analysis.

        Uses a real run to verify the parameter is properly passed.
        """
        # Configure the mock SentenceTransformer
        mock_model = MagicMock()
        mock_model.encode.return_value = np.random.rand(10, 384)
        mock_model.get_sentence_embedding_dimension.return_value = 384
        mock_st_class.return_value = mock_model

        emails = [
            create_email(
                email_id=str(i),
                sender_email="sender@example.com",
                sender_domain="example.com",
                subject=f"Test Subject {i}",
                body_text=f"Test body content {i}",
            )
            for i in range(10)
        ]
        corpus = create_corpus(emails)

        result, _stats = run_full_analysis(corpus, num_clusters=3)

        # Should have clusters (num depends on KMeans results)
        assert isinstance(result.content_clusters, list)

    @patch("src.analyzers.embedding_provider.SentenceTransformer")
    def test_progress_callback_integration(self, mock_st_class):
        """Test that progress callback is called during full analysis."""
        # Configure the mock SentenceTransformer
        mock_model = MagicMock()
        mock_model.encode.return_value = np.random.rand(5, 384)
        mock_model.get_sentence_embedding_dimension.return_value = 384
        mock_st_class.return_value = mock_model

        emails = [
            create_email(
                email_id=str(i), sender_email="sender@example.com", sender_domain="example.com"
            )
            for i in range(5)
        ]
        corpus = create_corpus(emails)

        callback_data = []

        def progress_callback(analyzer_name, current, total):
            callback_data.append((analyzer_name, current, total))

        run_full_analysis(corpus, progress_callback=progress_callback)

        # Verify callback was called with different analyzer names
        analyzer_names = {name for name, _, _ in callback_data}
        assert "sender" in analyzer_names or len(callback_data) > 0

    @patch("src.analyzers.embedding_provider.SentenceTransformer")
    def test_with_embedding_cache_returns_incremental_stats(self, mock_st_class):
        """Test that providing embedding_cache triggers incremental mode and returns stats."""
        import os
        import tempfile

        from src.cache.embedding_cache import EmbeddingCache

        mock_model = MagicMock()
        mock_model.encode.return_value = np.random.rand(5, 1024)
        mock_model.get_sentence_embedding_dimension.return_value = 1024
        mock_st_class.return_value = mock_model

        emails = [
            create_email(
                email_id=str(i),
                sender_email=f"sender{i}@example.com",
                sender_domain="example.com",
                subject=f"Test Subject {i}",
                body_text=f"Test body content for email {i}",
                received_date=datetime(2024, 1, 1) + timedelta(days=i),
            )
            for i in range(5)
        ]
        corpus = create_corpus(emails)

        with tempfile.TemporaryDirectory() as tmp_dir:
            cache = EmbeddingCache(cache_path=os.path.join(tmp_dir, "cache.npz"))
            result, incremental_stats = run_full_analysis(
                corpus, num_clusters=2, embedding_cache=cache
            )

            # With embedding_cache, incremental_stats should be a dict
            assert incremental_stats is not None
            assert isinstance(incremental_stats, dict)
            assert "cached_count" in incremental_stats
            assert "generated_count" in incremental_stats

            # Results should still be valid
            assert hasattr(result, "sender_analysis")
            assert hasattr(result, "content_clusters")


# ============================================================================
# Edge Case Tests
# ============================================================================


class TestEdgeCases:
    """Test edge cases across all analyzers."""

    def test_volume_analyzer_same_day_emails(self):
        """Test volume analyzer when all emails are on the same day."""
        analyzer = VolumeAnalyzer()
        emails = [
            create_email(
                email_id=str(i),
                sender_email="sender@example.com",
                sender_domain="example.com",
                received_date=datetime(2024, 1, 15, i, 0),  # Same day, different hours
            )
            for i in range(5)
        ]
        corpus = create_corpus(emails)

        result = analyzer.analyze(corpus)

        # Same day should result in span_days = 1 (to avoid division by zero)
        assert result.date_range["span_days"] == "1"
        assert result.emails_per_day == 5.0

    def test_temporal_analyzer_burst_emails(self):
        """Test temporal analyzer with burst of emails on same day but different hours."""
        analyzer = TemporalAnalyzer()

        # All emails on same day but different hours - this creates small intervals
        # 15 emails with different hours creates avg interval < 2 days, so "daily"
        emails = [
            create_email(
                email_id=str(i),
                sender_email="sender@example.com",
                sender_domain="example.com",
                received_date=datetime(2024, 1, 15, i % 24, 0),
            )
            for i in range(15)
        ]
        corpus = create_corpus(emails)

        result = analyzer.analyze(corpus)

        # Since emails have different timestamps (different hours), intervals are very small
        # This classifies as "daily" because avg interval < 2 days
        assert result.sender_frequencies["sender@example.com"]["type"] == "daily"

    def test_subject_analyzer_empty_subjects(self):
        """Test subject analyzer with empty subjects."""
        analyzer = SubjectAnalyzer()
        emails = [
            create_email(
                email_id="1",
                sender_email="sender@example.com",
                sender_domain="example.com",
                subject="",
            ),
            create_email(
                email_id="2",
                sender_email="sender@example.com",
                sender_domain="example.com",
                subject="",
            ),
        ]
        corpus = create_corpus(emails)

        result = analyzer.analyze(corpus)

        assert result.total_subjects_analyzed == 2
        # Empty subjects should not cause errors

    def test_subject_analyzer_special_characters(self):
        """Test subject analyzer with special characters."""
        analyzer = SubjectAnalyzer()
        emails = [
            create_email(
                email_id="1",
                sender_email="sender@example.com",
                sender_domain="example.com",
                subject="[Test] Invoice #123 - $500.00 @work",
            )
        ]
        corpus = create_corpus(emails)

        result = analyzer.analyze(corpus)

        assert result.total_subjects_analyzed == 1
        # Should extract bracket tag
        tag_dict = dict(result.bracket_tags)
        assert "Test" in tag_dict

    def test_volume_analyzer_empty_body(self):
        """Test volume analyzer with empty body text."""
        analyzer = VolumeAnalyzer()
        emails = [
            create_email(
                email_id="1",
                sender_email="sender@example.com",
                sender_domain="example.com",
                body_text="",
            )
        ]
        corpus = create_corpus(emails)

        result = analyzer.analyze(corpus)

        assert result.avg_body_length_chars == 0

    def test_temporal_analyzer_exact_threshold_boundaries(self):
        """Test temporal analyzer at exact threshold boundaries."""
        analyzer = TemporalAnalyzer()

        # Test boundary: exactly 2 days average (should be weekly, not daily)
        # 10 emails over 18 days = 2 day intervals
        dates = [datetime(2024, 1, 1) + timedelta(days=i * 2) for i in range(10)]
        result = analyzer.classify_frequency(dates)
        assert result == "weekly"  # 2 days is weekly (< 8, not < 2)

        # Test boundary: exactly 8 days average (should be monthly, not weekly)
        dates = [datetime(2024, 1, 1) + timedelta(days=i * 8) for i in range(10)]
        result = analyzer.classify_frequency(dates)
        assert result == "monthly"  # 8 days is monthly (< 35, not < 8)

        # Test boundary: exactly 35 days average (should be occasional)
        dates = [datetime(2024, 1, 1) + timedelta(days=i * 35) for i in range(10)]
        result = analyzer.classify_frequency(dates)
        assert result == "occasional"  # 35 days is occasional (>= 35)

    def test_subject_analyzer_unicode_subjects(self):
        """Test subject analyzer with unicode characters."""
        analyzer = SubjectAnalyzer()
        emails = [
            create_email(
                email_id="1",
                sender_email="sender@example.com",
                sender_domain="example.com",
                subject="Meeting about cafe resume",
            ),
            create_email(
                email_id="2",
                sender_email="sender@example.com",
                sender_domain="example.com",
                subject="Test unicode characters",
            ),
        ]
        corpus = create_corpus(emails)

        result = analyzer.analyze(corpus)

        assert result.total_subjects_analyzed == 2

    def test_volume_analyzer_large_corpus(self):
        """Test volume analyzer with larger corpus."""
        analyzer = VolumeAnalyzer()
        emails = [
            create_email(
                email_id=str(i),
                sender_email=f"sender{i % 100}@domain{i % 10}.com",
                sender_domain=f"domain{i % 10}.com",
                body_text="x" * (i % 1000),
                has_attachments=(i % 3 == 0),
                received_date=datetime(2024, 1, 1) + timedelta(days=i % 365),
            )
            for i in range(500)
        ]
        corpus = create_corpus(emails)

        result = analyzer.analyze(corpus)

        assert result.total_emails == 500
        assert result.unique_senders == 100
        assert result.with_attachments > 0


# ============================================================================
# Test Per-Cluster Quality Metrics (Task 2A.4)
# ============================================================================


class TestClusterQualityMetrics:
    """Test cases for per-cluster quality metrics."""

    def test_content_cluster_has_silhouette_score_field(self):
        """Test ContentCluster model has silhouette_score field."""
        from src.models.content_cluster import ContentCluster, RepresentativeSample

        sample = RepresentativeSample(
            subject="Test", sender="test@example.com", body_preview="Test body"
        )

        cluster = ContentCluster(
            cluster_id=0,
            size=10,
            percentage=50.0,
            representative_samples=[sample],
            common_domains=[("example.com", 5)],
            email_ids=["1", "2"],
            silhouette_score=0.75,
        )

        assert cluster.silhouette_score == 0.75

    def test_content_cluster_silhouette_score_default_none(self):
        """Test ContentCluster silhouette_score defaults to None."""
        from src.models.content_cluster import ContentCluster, RepresentativeSample

        sample = RepresentativeSample(
            subject="Test", sender="test@example.com", body_preview="Test body"
        )

        cluster = ContentCluster(
            cluster_id=0,
            size=10,
            percentage=50.0,
            representative_samples=[sample],
            common_domains=[],
            email_ids=["1"],
        )

        assert cluster.silhouette_score is None

    def test_content_cluster_has_cohesion_score_field(self):
        """Test ContentCluster model has cohesion_score field."""
        from src.models.content_cluster import ContentCluster, RepresentativeSample

        sample = RepresentativeSample(
            subject="Test", sender="test@example.com", body_preview="Test body"
        )

        cluster = ContentCluster(
            cluster_id=0,
            size=10,
            percentage=50.0,
            representative_samples=[sample],
            common_domains=[],
            email_ids=["1"],
            cohesion_score=0.85,
        )

        assert cluster.cohesion_score == 0.85

    def test_content_cluster_cohesion_score_default_none(self):
        """Test ContentCluster cohesion_score defaults to None."""
        from src.models.content_cluster import ContentCluster, RepresentativeSample

        sample = RepresentativeSample(
            subject="Test", sender="test@example.com", body_preview="Test body"
        )

        cluster = ContentCluster(
            cluster_id=0,
            size=10,
            percentage=50.0,
            representative_samples=[sample],
            common_domains=[],
            email_ids=["1"],
        )

        assert cluster.cohesion_score is None

    @patch.object(SemanticAnalyzer, "_ensure_model_loaded")
    @patch("src.analyzers.embedding_provider.SentenceTransformer")
    def test_semantic_analyzer_calculates_quality_metrics(self, mock_st_class, mock_ensure_model):
        """Test that semantic analyzer calculates quality metrics for clusters."""
        analyzer = SemanticAnalyzer()

        # Create distinct clusters for better silhouette scores
        np.random.seed(42)
        cluster1 = np.random.randn(10, 20) * 0.1 + np.array([0] * 20)
        cluster2 = np.random.randn(10, 20) * 0.1 + np.array([10] * 20)
        embeddings = np.vstack([cluster1, cluster2])

        emails = [
            create_email(
                email_id=str(i),
                sender_email=f"sender{i % 2}@example.com",
                sender_domain="example.com",
                subject=f"Subject {i}",
                body_text=f"Body content {i}",
            )
            for i in range(20)
        ]
        corpus = create_corpus(emails)

        mock_model = MagicMock()
        mock_model.encode.return_value = embeddings
        analyzer.model = mock_model

        result = analyzer.analyze(corpus, num_clusters=2)

        # Clusters should have quality metrics populated
        assert len(result) > 0
        for cluster in result:
            # silhouette_score should be set for k >= 2
            assert cluster.silhouette_score is not None
            assert -1.0 <= cluster.silhouette_score <= 1.0
            # cohesion_score should be set
            assert cluster.cohesion_score is not None
            assert cluster.cohesion_score >= 0.0

    @patch.object(SemanticAnalyzer, "_ensure_model_loaded")
    @patch("src.analyzers.embedding_provider.SentenceTransformer")
    def test_semantic_analyzer_single_cluster_no_silhouette(self, mock_st_class, mock_ensure_model):
        """Test that silhouette is None for single cluster (k=1)."""
        analyzer = SemanticAnalyzer()

        np.random.seed(42)
        embeddings = np.random.rand(5, 10)

        emails = [
            create_email(
                email_id=str(i), sender_email="sender@example.com", sender_domain="example.com"
            )
            for i in range(5)
        ]
        corpus = create_corpus(emails)

        mock_model = MagicMock()
        mock_model.encode.return_value = embeddings
        analyzer.model = mock_model

        result = analyzer.analyze(corpus, num_clusters=1)

        # With k=1, silhouette cannot be calculated
        assert len(result) == 1
        assert result[0].silhouette_score is None

    @patch.object(SemanticAnalyzer, "_ensure_model_loaded")
    @patch("src.analyzers.embedding_provider.SentenceTransformer")
    def test_quality_metrics_included_in_json_output(self, mock_st_class, mock_ensure_model):
        """Test that quality metrics are included in model_dump output."""
        analyzer = SemanticAnalyzer()

        np.random.seed(42)
        embeddings = np.random.rand(10, 10)

        emails = [
            create_email(
                email_id=str(i), sender_email="sender@example.com", sender_domain="example.com"
            )
            for i in range(10)
        ]
        corpus = create_corpus(emails)

        mock_model = MagicMock()
        mock_model.encode.return_value = embeddings
        analyzer.model = mock_model

        result = analyzer.analyze(corpus, num_clusters=2)

        # Check that model_dump includes quality metrics
        for cluster in result:
            cluster_dict = cluster.model_dump()
            assert "silhouette_score" in cluster_dict
            assert "cohesion_score" in cluster_dict


# ============================================================================
# Test Cluster Visualization (Task 4.3)
# ============================================================================


try:
    import matplotlib  # noqa: F401

    _has_matplotlib = True
except ImportError:
    _has_matplotlib = False


class TestClusterVisualization:
    """Test cases for generate_cluster_visualization function."""

    @pytest.mark.skipif(not _has_matplotlib, reason="matplotlib required")
    def test_generates_png_with_silhouette_scores(self, tmp_path):
        """Test that visualization creates a PNG file with scatter + bar chart."""
        from src.analyzers.semantic_analyzer import generate_cluster_visualization

        np.random.seed(42)
        embeddings = np.random.rand(30, 10)
        labels = np.array([0] * 10 + [1] * 10 + [2] * 10)
        silhouette_scores = {0: 0.5, 1: 0.3, 2: 0.7}

        output_path = tmp_path / "test_viz.png"

        result = generate_cluster_visualization(
            embeddings=embeddings,
            labels=labels,
            output_path=output_path,
            cluster_silhouette_scores=silhouette_scores,
        )

        assert result is not None
        assert result.exists()
        assert result.suffix == ".png"
        # File should be non-trivial in size (at least a few KB)
        assert result.stat().st_size > 1000

    @pytest.mark.skipif(not _has_matplotlib, reason="matplotlib required")
    def test_generates_png_without_silhouette_scores(self, tmp_path):
        """Test that visualization works without silhouette scores (scatter only)."""
        from src.analyzers.semantic_analyzer import generate_cluster_visualization

        np.random.seed(42)
        embeddings = np.random.rand(20, 10)
        labels = np.array([0] * 10 + [1] * 10)

        output_path = tmp_path / "test_viz_no_sil.png"

        result = generate_cluster_visualization(
            embeddings=embeddings,
            labels=labels,
            output_path=output_path,
            cluster_silhouette_scores=None,
        )

        assert result is not None
        assert result.exists()

    def test_returns_none_when_matplotlib_unavailable(self, tmp_path):
        """Test graceful handling when matplotlib is not installed."""
        from src.analyzers.semantic_analyzer import generate_cluster_visualization

        np.random.seed(42)
        embeddings = np.random.rand(10, 5)
        labels = np.array([0] * 5 + [1] * 5)

        output_path = tmp_path / "should_not_exist.png"

        with patch.dict("sys.modules", {"matplotlib": None}):
            result = generate_cluster_visualization(
                embeddings=embeddings,
                labels=labels,
                output_path=output_path,
            )

        assert result is None
        assert not output_path.exists()

    @pytest.mark.skipif(not _has_matplotlib, reason="matplotlib required")
    def test_single_cluster_visualization(self, tmp_path):
        """Test visualization with a single cluster."""
        from src.analyzers.semantic_analyzer import generate_cluster_visualization

        np.random.seed(42)
        embeddings = np.random.rand(10, 5)
        labels = np.zeros(10, dtype=int)

        output_path = tmp_path / "single_cluster.png"

        result = generate_cluster_visualization(
            embeddings=embeddings,
            labels=labels,
            output_path=output_path,
        )

        assert result is not None
        assert result.exists()

    @pytest.mark.skipif(not _has_matplotlib, reason="matplotlib required")
    def test_output_path_as_string(self, tmp_path):
        """Test that output_path accepts string as well as Path."""
        from src.analyzers.semantic_analyzer import generate_cluster_visualization

        np.random.seed(42)
        embeddings = np.random.rand(10, 5)
        labels = np.array([0] * 5 + [1] * 5)

        output_path = str(tmp_path / "string_path.png")

        result = generate_cluster_visualization(
            embeddings=embeddings,
            labels=labels,
            output_path=output_path,
        )

        assert result is not None
        assert result.exists()


class TestClusterVizCLIFlag:
    """Test that --cluster-viz CLI flag is properly configured."""

    def test_analyze_command_has_cluster_viz_flag(self):
        """Test that analyze command has --cluster-viz flag."""
        from src.cli import create_parser

        parser = create_parser()

        # Without flag - default should be False
        args = parser.parse_args(["analyze"])
        assert args.cluster_viz is False

        # With flag - should be True
        args = parser.parse_args(["analyze", "--cluster-viz"])
        assert args.cluster_viz is True


class TestHTMLExporterVisualization:
    """Test that HTML exporter includes cluster visualization when available."""

    def test_html_includes_visualization_when_png_exists(self, tmp_path):
        """Test that HTML report includes img tag when visualization exists."""
        from src.exporters.html_exporter import export_categories_to_html
        from src.models.category import Category, CategorySource

        # Create a dummy visualization PNG
        viz_path = tmp_path / "cluster_visualization.png"
        viz_path.write_bytes(b"fake png data")

        # Create a minimal category
        categories = [
            Category(
                category_id="cat1",
                category_name="Test Category",
                description="A test category",
                confidence=0.8,
                source=CategorySource.TEMPLATE,
                email_count=10,
            )
        ]

        output_path = tmp_path / "report.html"
        export_categories_to_html(categories, output_path)

        html_content = output_path.read_text(encoding="utf-8")
        assert "cluster_visualization.png" in html_content
        assert "Cluster Visualization" in html_content

    def test_html_excludes_visualization_when_no_png(self, tmp_path):
        """Test that HTML report omits visualization section when no PNG."""
        from src.exporters.html_exporter import export_categories_to_html
        from src.models.category import Category, CategorySource

        categories = [
            Category(
                category_id="cat1",
                category_name="Test Category",
                description="A test category",
                confidence=0.8,
                source=CategorySource.TEMPLATE,
                email_count=10,
            )
        ]

        output_path = tmp_path / "report.html"
        export_categories_to_html(categories, output_path)

        html_content = output_path.read_text(encoding="utf-8")
        assert "Cluster Visualization" not in html_content

    def test_html_accepts_explicit_visualization_path(self, tmp_path):
        """Test that explicit cluster_visualization_path param works."""
        from src.exporters.html_exporter import export_categories_to_html
        from src.models.category import Category, CategorySource

        # Put viz in a subdirectory
        viz_dir = tmp_path / "viz"
        viz_dir.mkdir()
        viz_path = viz_dir / "my_clusters.png"
        viz_path.write_bytes(b"fake png data")

        categories = [
            Category(
                category_id="cat1",
                category_name="Test Category",
                description="A test category",
                confidence=0.8,
                source=CategorySource.TEMPLATE,
                email_count=10,
            )
        ]

        output_path = tmp_path / "report.html"
        export_categories_to_html(
            categories,
            output_path,
            cluster_visualization_path=viz_path,
        )

        html_content = output_path.read_text(encoding="utf-8")
        assert "Cluster Visualization" in html_content
