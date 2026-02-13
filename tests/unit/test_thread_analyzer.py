"""
Unit tests for Track 8A: Thread Analyzer.

Tests the thread detection analyzer that identifies email conversations
by parsing In-Reply-To and References headers.
Work Item 3.2: Added subject-based fallback grouping tests.

Uses TDD approach - tests written first before implementation.
"""
from datetime import datetime, timedelta

import pytest

from src.models.corpus import Corpus, CorpusMetadata
from src.models.email import Email


def create_test_email(
    id: str = "test_001",
    sender_email: str = "sender@example.com",
    sender_domain: str = "example.com",
    subject: str = "Test Subject",
    body_text: str = "Test body content",
    received_date: datetime | None = None,
    thread_id: str | None = None,
    in_reply_to: str | None = None,
    references: list[str] | None = None,
) -> Email:
    """Factory function to create Email objects for testing."""
    if received_date is None:
        received_date = datetime(2024, 1, 15, 10, 0)

    email = Email(
        id=id,
        sender_email=sender_email,
        sender_name="Test Sender",
        sender_domain=sender_domain,
        subject=subject,
        body_text=body_text,
        received_date=received_date,
        has_attachments=False,
        thread_id=thread_id,
        in_reply_to=in_reply_to,
        references=references or [],
    )
    return email


def create_test_corpus(emails: list[Email] | None = None) -> Corpus:
    """Factory function to create Corpus objects for testing."""
    if emails is None:
        emails = [create_test_email(id=f"email_{i}") for i in range(5)]
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
# Test ThreadAnalyzer Class Existence
# ============================================================================


class TestThreadAnalyzerExists:
    """Test that ThreadAnalyzer class exists with required interface."""

    def test_thread_analyzer_exists(self):
        """Test that ThreadAnalyzer class exists."""
        from src.analyzers.thread_analyzer import ThreadAnalyzer

        assert ThreadAnalyzer is not None

    def test_thread_analyzer_inherits_from_base(self):
        """Test ThreadAnalyzer is a BaseAnalyzer."""
        from src.analyzers.base import BaseAnalyzer
        from src.analyzers.thread_analyzer import ThreadAnalyzer

        assert issubclass(ThreadAnalyzer, BaseAnalyzer)

    def test_thread_analyzer_has_name(self):
        """Test ThreadAnalyzer has name property."""
        from src.analyzers.thread_analyzer import ThreadAnalyzer

        analyzer = ThreadAnalyzer()
        assert analyzer.name == "Thread Analyzer"

    def test_thread_analyzer_supports_incremental_false(self):
        """Test ThreadAnalyzer does not support incremental."""
        from src.analyzers.thread_analyzer import ThreadAnalyzer

        analyzer = ThreadAnalyzer()
        assert analyzer.supports_incremental() is False


# ============================================================================
# Test Thread Detection by In-Reply-To Header
# ============================================================================


class TestThreadDetectionInReplyTo:
    """Test thread detection using In-Reply-To header."""

    def test_detect_thread_by_in_reply_to(self):
        """Test that emails with same In-Reply-To are grouped in same thread."""
        from src.analyzers.thread_analyzer import ThreadAnalyzer

        # Create a chain: original -> reply1, reply2
        original = create_test_email(
            id="msg_001",
            subject="Original Message",
        )
        reply1 = create_test_email(
            id="msg_002",
            subject="Re: Original Message",
            in_reply_to="msg_001",
        )
        reply2 = create_test_email(
            id="msg_003",
            subject="Re: Original Message",
            in_reply_to="msg_001",
        )

        corpus = create_test_corpus([original, reply1, reply2])
        analyzer = ThreadAnalyzer()
        result = analyzer.analyze(corpus)

        # All three should be in the same thread
        assert result.threads is not None
        assert len(result.threads) == 1

        thread = list(result.threads.values())[0]
        assert len(thread.email_ids) == 3
        assert "msg_001" in thread.email_ids
        assert "msg_002" in thread.email_ids
        assert "msg_003" in thread.email_ids

    def test_detect_chained_thread(self):
        """Test detection of chained replies (A -> B -> C)."""
        from src.analyzers.thread_analyzer import ThreadAnalyzer

        # Create a chain: msg1 -> msg2 -> msg3
        msg1 = create_test_email(id="msg_001", subject="Hello")
        msg2 = create_test_email(
            id="msg_002",
            subject="Re: Hello",
            in_reply_to="msg_001",
        )
        msg3 = create_test_email(
            id="msg_003",
            subject="Re: Re: Hello",
            in_reply_to="msg_002",
        )

        corpus = create_test_corpus([msg1, msg2, msg3])
        analyzer = ThreadAnalyzer()
        result = analyzer.analyze(corpus)

        # All three should be in the same thread
        assert len(result.threads) == 1
        thread = list(result.threads.values())[0]
        assert len(thread.email_ids) == 3


# ============================================================================
# Test Thread Detection by References Header
# ============================================================================


class TestThreadDetectionReferences:
    """Test thread detection using References header."""

    def test_detect_thread_by_references(self):
        """Test that emails with common references are grouped."""
        from src.analyzers.thread_analyzer import ThreadAnalyzer

        # Create emails with references header
        msg1 = create_test_email(id="msg_001", subject="Original")
        msg2 = create_test_email(
            id="msg_002",
            subject="Re: Original",
            references=["msg_001"],
        )
        msg3 = create_test_email(
            id="msg_003",
            subject="Re: Re: Original",
            references=["msg_001", "msg_002"],
        )

        corpus = create_test_corpus([msg1, msg2, msg3])
        analyzer = ThreadAnalyzer()
        result = analyzer.analyze(corpus)

        # All three should be in the same thread
        assert len(result.threads) == 1
        thread = list(result.threads.values())[0]
        assert len(thread.email_ids) == 3

    def test_combined_in_reply_to_and_references(self):
        """Test that In-Reply-To and References are combined for thread detection."""
        from src.analyzers.thread_analyzer import ThreadAnalyzer

        # Some email clients use both headers
        msg1 = create_test_email(id="msg_001", subject="Original")
        msg2 = create_test_email(
            id="msg_002",
            subject="Re: Original",
            in_reply_to="msg_001",
            references=["msg_001"],
        )

        corpus = create_test_corpus([msg1, msg2])
        analyzer = ThreadAnalyzer()
        result = analyzer.analyze(corpus)

        assert len(result.threads) == 1


# ============================================================================
# Test Single Email Thread Assignment
# ============================================================================


class TestSingleEmailThreads:
    """Test that single emails get their own unique thread ID."""

    def test_single_emails_get_unique_thread(self):
        """Test that unrelated emails each get their own thread."""
        from src.analyzers.thread_analyzer import ThreadAnalyzer

        msg1 = create_test_email(id="msg_001", subject="Topic A")
        msg2 = create_test_email(id="msg_002", subject="Topic B")
        msg3 = create_test_email(id="msg_003", subject="Topic C")

        corpus = create_test_corpus([msg1, msg2, msg3])
        analyzer = ThreadAnalyzer()
        result = analyzer.analyze(corpus)

        # Each should be in its own thread
        assert len(result.threads) == 3
        for thread in result.threads.values():
            assert len(thread.email_ids) == 1

    def test_thread_id_format(self):
        """Test that generated thread IDs have proper format."""
        from src.analyzers.thread_analyzer import ThreadAnalyzer

        msg1 = create_test_email(id="msg_001", subject="Standalone")

        corpus = create_test_corpus([msg1])
        analyzer = ThreadAnalyzer()
        result = analyzer.analyze(corpus)

        thread = list(result.threads.values())[0]
        # Thread ID should be a non-empty string
        assert thread.thread_id is not None
        assert len(thread.thread_id) > 0
        assert isinstance(thread.thread_id, str)


# ============================================================================
# Test ThreadAnalysisResult Model
# ============================================================================


class TestThreadAnalysisResult:
    """Test ThreadAnalysisResult data model."""

    def test_result_has_threads_dict(self):
        """Test that result contains threads dictionary."""
        from src.analyzers.thread_analyzer import ThreadAnalyzer

        msg1 = create_test_email(id="msg_001", subject="Test")
        corpus = create_test_corpus([msg1])

        analyzer = ThreadAnalyzer()
        result = analyzer.analyze(corpus)

        assert hasattr(result, "threads")
        assert isinstance(result.threads, dict)

    def test_result_has_total_threads_count(self):
        """Test result includes total thread count."""
        from src.analyzers.thread_analyzer import ThreadAnalyzer

        msg1 = create_test_email(id="msg_001", subject="Test")
        corpus = create_test_corpus([msg1])

        analyzer = ThreadAnalyzer()
        result = analyzer.analyze(corpus)

        assert hasattr(result, "total_threads")
        assert result.total_threads == 1

    def test_result_has_conversation_threads_count(self):
        """Test result includes count of multi-email threads (conversations)."""
        from src.analyzers.thread_analyzer import ThreadAnalyzer

        # One conversation (2 emails) and one single email
        msg1 = create_test_email(id="msg_001", subject="Original")
        msg2 = create_test_email(
            id="msg_002",
            subject="Re: Original",
            in_reply_to="msg_001",
        )
        msg3 = create_test_email(id="msg_003", subject="Standalone")

        corpus = create_test_corpus([msg1, msg2, msg3])
        analyzer = ThreadAnalyzer()
        result = analyzer.analyze(corpus)

        assert hasattr(result, "conversation_count")
        assert result.conversation_count == 1  # Only the 2-email thread

    def test_result_has_single_email_threads_count(self):
        """Test result includes count of single-email threads."""
        from src.analyzers.thread_analyzer import ThreadAnalyzer

        msg1 = create_test_email(id="msg_001", subject="Original")
        msg2 = create_test_email(
            id="msg_002",
            subject="Re: Original",
            in_reply_to="msg_001",
        )
        msg3 = create_test_email(id="msg_003", subject="Standalone")

        corpus = create_test_corpus([msg1, msg2, msg3])
        analyzer = ThreadAnalyzer()
        result = analyzer.analyze(corpus)

        assert hasattr(result, "single_email_count")
        assert result.single_email_count == 1


# ============================================================================
# Test Thread Model
# ============================================================================


class TestThreadModel:
    """Test Thread data model attributes."""

    def test_thread_has_required_attributes(self):
        """Test Thread model has all required attributes."""
        from src.analyzers.thread_analyzer import ThreadAnalyzer

        msg1 = create_test_email(id="msg_001", subject="Test")
        corpus = create_test_corpus([msg1])

        analyzer = ThreadAnalyzer()
        result = analyzer.analyze(corpus)

        thread = list(result.threads.values())[0]

        assert hasattr(thread, "thread_id")
        assert hasattr(thread, "email_ids")
        assert hasattr(thread, "subject")
        assert hasattr(thread, "participant_count")
        assert hasattr(thread, "message_count")

    def test_thread_subject_is_first_email_subject(self):
        """Test thread subject is the original email's subject."""
        from src.analyzers.thread_analyzer import ThreadAnalyzer

        msg1 = create_test_email(
            id="msg_001",
            subject="Original Subject",
            received_date=datetime(2024, 1, 1, 10, 0),
        )
        msg2 = create_test_email(
            id="msg_002",
            subject="Re: Original Subject",
            in_reply_to="msg_001",
            received_date=datetime(2024, 1, 2, 10, 0),
        )

        corpus = create_test_corpus([msg2, msg1])  # Out of order
        analyzer = ThreadAnalyzer()
        result = analyzer.analyze(corpus)

        thread = list(result.threads.values())[0]
        # Should use the earliest email's subject (Original Subject)
        assert thread.subject == "Original Subject"

    def test_thread_participant_count(self):
        """Test thread tracks unique participants."""
        from src.analyzers.thread_analyzer import ThreadAnalyzer

        msg1 = create_test_email(
            id="msg_001",
            sender_email="alice@example.com",
            subject="Hello",
        )
        msg2 = create_test_email(
            id="msg_002",
            sender_email="bob@example.com",
            subject="Re: Hello",
            in_reply_to="msg_001",
        )
        msg3 = create_test_email(
            id="msg_003",
            sender_email="alice@example.com",  # Alice replies again
            subject="Re: Re: Hello",
            in_reply_to="msg_002",
        )

        corpus = create_test_corpus([msg1, msg2, msg3])
        analyzer = ThreadAnalyzer()
        result = analyzer.analyze(corpus)

        thread = list(result.threads.values())[0]
        assert thread.participant_count == 2  # alice and bob


# ============================================================================
# Test Empty and Edge Cases
# ============================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_corpus_raises_error(self):
        """Test that empty corpus raises appropriate error."""
        from src.analyzers.base import AnalysisError
        from src.analyzers.thread_analyzer import ThreadAnalyzer

        corpus = create_test_corpus([])
        analyzer = ThreadAnalyzer()

        with pytest.raises((AnalysisError, ValueError)):
            analyzer.analyze(corpus)

    def test_handles_missing_headers(self):
        """Test graceful handling of emails without reply headers."""
        from src.analyzers.thread_analyzer import ThreadAnalyzer

        # Email with no In-Reply-To or References
        msg1 = create_test_email(id="msg_001", subject="No headers")

        corpus = create_test_corpus([msg1])
        analyzer = ThreadAnalyzer()
        result = analyzer.analyze(corpus)

        # Should create its own thread
        assert len(result.threads) == 1

    def test_handles_external_references(self):
        """Test handling of references to external (not in corpus) messages."""
        from src.analyzers.thread_analyzer import ThreadAnalyzer

        # References a message not in our corpus
        msg1 = create_test_email(
            id="msg_001",
            subject="Re: External Thread",
            in_reply_to="external_msg_001",  # Not in corpus
            references=["external_msg_001"],
        )

        corpus = create_test_corpus([msg1])
        analyzer = ThreadAnalyzer()
        result = analyzer.analyze(corpus)

        # Should create its own thread (can't find parent)
        assert len(result.threads) == 1


# ============================================================================
# Test Module Registration
# ============================================================================


class TestModuleRegistration:
    """Test ThreadAnalyzer is properly registered in analyzers module."""

    def test_thread_analyzer_importable_from_analyzers(self):
        """Test ThreadAnalyzer is importable from src.analyzers."""
        from src.analyzers import ThreadAnalyzer

        assert ThreadAnalyzer is not None

    def test_thread_analyzer_in_all_exports(self):
        """Test ThreadAnalyzer is in __all__ exports."""
        import src.analyzers as analyzers_module

        assert "ThreadAnalyzer" in analyzers_module.__all__


# ============================================================================
# Test Email Model Thread ID Field
# ============================================================================


class TestEmailThreadIdField:
    """Test that Email model has thread_id field."""

    def test_email_has_thread_id_field(self):
        """Test Email model has optional thread_id field."""
        email = Email(
            id="test_001",
            sender_email="sender@example.com",
            sender_name="Sender",
            sender_domain="example.com",
            subject="Test",
            body_text="Body",
            received_date=datetime.now(),
            has_attachments=False,
        )

        # Should have thread_id attribute (default None)
        assert hasattr(email, "thread_id")
        assert email.thread_id is None

    def test_email_thread_id_can_be_set(self):
        """Test Email thread_id can be set."""
        email = Email(
            id="test_001",
            sender_email="sender@example.com",
            sender_name="Sender",
            sender_domain="example.com",
            subject="Test",
            body_text="Body",
            received_date=datetime.now(),
            has_attachments=False,
            thread_id="thread_abc123",
        )

        assert email.thread_id == "thread_abc123"


# ============================================================================
# Test Email Model In-Reply-To and References Fields
# ============================================================================


class TestEmailHeaderFields:
    """Test that Email model has In-Reply-To and References fields."""

    def test_email_has_in_reply_to_field(self):
        """Test Email model has optional in_reply_to field."""
        email = Email(
            id="test_001",
            sender_email="sender@example.com",
            sender_name="Sender",
            sender_domain="example.com",
            subject="Test",
            body_text="Body",
            received_date=datetime.now(),
            has_attachments=False,
        )

        assert hasattr(email, "in_reply_to")
        assert email.in_reply_to is None

    def test_email_in_reply_to_can_be_set(self):
        """Test Email in_reply_to can be set."""
        email = Email(
            id="test_001",
            sender_email="sender@example.com",
            sender_name="Sender",
            sender_domain="example.com",
            subject="Re: Test",
            body_text="Body",
            received_date=datetime.now(),
            has_attachments=False,
            in_reply_to="msg_parent_001",
        )

        assert email.in_reply_to == "msg_parent_001"

    def test_email_has_references_field(self):
        """Test Email model has references list field."""
        email = Email(
            id="test_001",
            sender_email="sender@example.com",
            sender_name="Sender",
            sender_domain="example.com",
            subject="Test",
            body_text="Body",
            received_date=datetime.now(),
            has_attachments=False,
        )

        assert hasattr(email, "references")
        assert email.references == []

    def test_email_references_can_be_set(self):
        """Test Email references list can be set."""
        refs = ["msg_001", "msg_002", "msg_003"]
        email = Email(
            id="test_001",
            sender_email="sender@example.com",
            sender_name="Sender",
            sender_domain="example.com",
            subject="Re: Test",
            body_text="Body",
            received_date=datetime.now(),
            has_attachments=False,
            references=refs,
        )

        assert email.references == refs


# ============================================================================
# Test _normalize_subject Function
# ============================================================================


class TestNormalizeSubject:
    """Test the _normalize_subject helper function."""

    def test_strips_re_prefix(self):
        """Test that RE: prefix is stripped."""
        from src.analyzers.thread_analyzer import _normalize_subject

        assert _normalize_subject("Re: Hello World") == "hello world"

    def test_strips_re_prefix_case_insensitive(self):
        """Test that RE: prefix stripping is case-insensitive."""
        from src.analyzers.thread_analyzer import _normalize_subject

        assert _normalize_subject("RE: Hello World") == "hello world"
        assert _normalize_subject("re: Hello World") == "hello world"
        assert _normalize_subject("Re: Hello World") == "hello world"

    def test_strips_fwd_prefix(self):
        """Test that FWD: prefix is stripped."""
        from src.analyzers.thread_analyzer import _normalize_subject

        assert _normalize_subject("Fwd: Hello World") == "hello world"
        assert _normalize_subject("FWD: Hello World") == "hello world"

    def test_strips_fw_prefix(self):
        """Test that FW: prefix is stripped."""
        from src.analyzers.thread_analyzer import _normalize_subject

        assert _normalize_subject("Fw: Hello World") == "hello world"
        assert _normalize_subject("FW: Hello World") == "hello world"

    def test_strips_repeated_prefixes(self):
        """Test that repeated RE:/FWD: prefixes are all stripped."""
        from src.analyzers.thread_analyzer import _normalize_subject

        assert _normalize_subject("Re: Re: Re: Hello World") == "hello world"
        assert _normalize_subject("Re: Fwd: Hello World") == "hello world"
        assert _normalize_subject("FW: RE: FWD: Hello World") == "hello world"

    def test_normalizes_whitespace(self):
        """Test that multiple spaces are collapsed to single space."""
        from src.analyzers.thread_analyzer import _normalize_subject

        assert _normalize_subject("Hello   World") == "hello world"
        assert _normalize_subject("  Hello  World  ") == "hello world"

    def test_lowercases_result(self):
        """Test that the result is lowercased."""
        from src.analyzers.thread_analyzer import _normalize_subject

        assert _normalize_subject("Hello WORLD") == "hello world"

    def test_empty_string(self):
        """Test handling of empty string."""
        from src.analyzers.thread_analyzer import _normalize_subject

        assert _normalize_subject("") == ""

    def test_only_prefix(self):
        """Test handling of subject that is only a prefix."""
        from src.analyzers.thread_analyzer import _normalize_subject

        assert _normalize_subject("Re:") == ""
        assert _normalize_subject("Re: ") == ""


# ============================================================================
# Test Subject-Based Fallback Grouping
# ============================================================================


class TestSubjectBasedFallback:
    """Test subject-based heuristic grouping for emails without headers."""

    def test_groups_matching_subjects_same_domain_within_window(self):
        """Emails with matching subjects, same sender domain, within time window are grouped."""
        from src.analyzers.thread_analyzer import ThreadAnalyzer

        base_date = datetime(2024, 1, 15, 10, 0)
        msg1 = create_test_email(
            id="msg_001",
            sender_email="alice@example.com",
            sender_domain="example.com",
            subject="Meeting Notes",
            received_date=base_date,
        )
        msg2 = create_test_email(
            id="msg_002",
            sender_email="bob@example.com",
            sender_domain="example.com",
            subject="Re: Meeting Notes",
            received_date=base_date + timedelta(days=1),
        )
        msg3 = create_test_email(
            id="msg_003",
            sender_email="alice@example.com",
            sender_domain="example.com",
            subject="RE: Meeting Notes",
            received_date=base_date + timedelta(days=2),
        )

        corpus = create_test_corpus([msg1, msg2, msg3])
        analyzer = ThreadAnalyzer()
        result = analyzer.analyze(corpus)

        # All three should be grouped into one thread via subject heuristic
        assert result.conversation_count >= 1
        # Find the thread with 3 emails
        multi_threads = [t for t in result.threads.values() if t.message_count == 3]
        assert len(multi_threads) == 1
        thread = multi_threads[0]
        assert set(thread.email_ids) == {"msg_001", "msg_002", "msg_003"}

    def test_different_subjects_stay_separate(self):
        """Emails with different normalized subjects are NOT grouped together."""
        from src.analyzers.thread_analyzer import ThreadAnalyzer

        base_date = datetime(2024, 1, 15, 10, 0)
        msg1 = create_test_email(
            id="msg_001",
            sender_email="alice@example.com",
            sender_domain="example.com",
            subject="Meeting Notes",
            received_date=base_date,
        )
        msg2 = create_test_email(
            id="msg_002",
            sender_email="bob@example.com",
            sender_domain="example.com",
            subject="Lunch Plans",
            received_date=base_date + timedelta(days=1),
        )

        corpus = create_test_corpus([msg1, msg2])
        analyzer = ThreadAnalyzer()
        result = analyzer.analyze(corpus)

        # Should remain as 2 separate threads
        assert len(result.threads) == 2

    def test_same_subject_different_domains_stay_separate(self):
        """Emails with same subject but different sender domains are NOT grouped."""
        from src.analyzers.thread_analyzer import ThreadAnalyzer

        base_date = datetime(2024, 1, 15, 10, 0)
        msg1 = create_test_email(
            id="msg_001",
            sender_email="alice@company-a.com",
            sender_domain="company-a.com",
            subject="Weekly Report",
            received_date=base_date,
        )
        msg2 = create_test_email(
            id="msg_002",
            sender_email="bob@company-b.com",
            sender_domain="company-b.com",
            subject="Weekly Report",
            received_date=base_date + timedelta(days=1),
        )

        corpus = create_test_corpus([msg1, msg2])
        analyzer = ThreadAnalyzer()
        result = analyzer.analyze(corpus)

        # Should remain as 2 separate threads (different domains)
        assert len(result.threads) == 2

    def test_same_subject_outside_time_window_stay_separate(self):
        """Emails with matching subjects but outside the time window are NOT grouped."""
        from src.analyzers.thread_analyzer import ThreadAnalyzer

        base_date = datetime(2024, 1, 1, 10, 0)
        msg1 = create_test_email(
            id="msg_001",
            sender_email="alice@example.com",
            sender_domain="example.com",
            subject="Weekly Report",
            received_date=base_date,
        )
        msg2 = create_test_email(
            id="msg_002",
            sender_email="bob@example.com",
            sender_domain="example.com",
            subject="Re: Weekly Report",
            received_date=base_date + timedelta(days=10),  # 10 days > 7 day window
        )

        corpus = create_test_corpus([msg1, msg2])
        analyzer = ThreadAnalyzer()
        result = analyzer.analyze(corpus)

        # Should remain as 2 separate threads (outside 7-day window)
        assert len(result.threads) == 2

    def test_configurable_time_window(self):
        """Test that subject_match_window_days parameter controls the time window."""
        from src.analyzers.thread_analyzer import ThreadAnalyzer

        base_date = datetime(2024, 1, 1, 10, 0)
        msg1 = create_test_email(
            id="msg_001",
            sender_email="alice@example.com",
            sender_domain="example.com",
            subject="Project Update",
            received_date=base_date,
        )
        msg2 = create_test_email(
            id="msg_002",
            sender_email="bob@example.com",
            sender_domain="example.com",
            subject="Re: Project Update",
            received_date=base_date + timedelta(days=10),
        )

        # With default 7-day window, these should NOT be grouped
        analyzer_default = ThreadAnalyzer()
        result_default = analyzer_default.analyze(create_test_corpus([msg1, msg2]))
        assert len(result_default.threads) == 2

        # With 14-day window, these SHOULD be grouped
        analyzer_wide = ThreadAnalyzer(subject_match_window_days=14)
        result_wide = analyzer_wide.analyze(create_test_corpus([msg1, msg2]))
        assert result_wide.conversation_count == 1

    def test_configurable_window_zero_disables_heuristic(self):
        """Test that setting window to 0 effectively disables subject-based grouping."""
        from src.analyzers.thread_analyzer import ThreadAnalyzer

        base_date = datetime(2024, 1, 15, 10, 0)
        msg1 = create_test_email(
            id="msg_001",
            sender_email="alice@example.com",
            sender_domain="example.com",
            subject="Meeting Notes",
            received_date=base_date,
        )
        msg2 = create_test_email(
            id="msg_002",
            sender_email="bob@example.com",
            sender_domain="example.com",
            subject="Re: Meeting Notes",
            received_date=base_date + timedelta(hours=1),
        )

        analyzer = ThreadAnalyzer(subject_match_window_days=0)
        result = analyzer.analyze(create_test_corpus([msg1, msg2]))
        # With 0-day window, even same-day emails should NOT be grouped by subject
        assert len(result.threads) == 2


# ============================================================================
# Test Thread Method Tracking
# ============================================================================


class TestThreadMethodTracking:
    """Test that thread_method field correctly identifies grouping method."""

    def test_header_grouped_threads_have_header_method(self):
        """Threads grouped by In-Reply-To/References have thread_method='header'."""
        from src.analyzers.thread_analyzer import ThreadAnalyzer

        msg1 = create_test_email(
            id="msg_001",
            subject="Original Message",
        )
        msg2 = create_test_email(
            id="msg_002",
            subject="Re: Original Message",
            in_reply_to="msg_001",
        )

        corpus = create_test_corpus([msg1, msg2])
        analyzer = ThreadAnalyzer()
        result = analyzer.analyze(corpus)

        # The multi-email thread should have method "header"
        conversation_threads = [t for t in result.threads.values() if t.message_count > 1]
        assert len(conversation_threads) == 1
        assert conversation_threads[0].thread_method == "header"

    def test_subject_grouped_threads_have_subject_heuristic_method(self):
        """Threads grouped by subject matching have thread_method='subject_heuristic'."""
        from src.analyzers.thread_analyzer import ThreadAnalyzer

        base_date = datetime(2024, 1, 15, 10, 0)
        msg1 = create_test_email(
            id="msg_001",
            sender_email="alice@example.com",
            sender_domain="example.com",
            subject="Budget Discussion",
            received_date=base_date,
        )
        msg2 = create_test_email(
            id="msg_002",
            sender_email="bob@example.com",
            sender_domain="example.com",
            subject="Re: Budget Discussion",
            received_date=base_date + timedelta(days=1),
        )

        corpus = create_test_corpus([msg1, msg2])
        analyzer = ThreadAnalyzer()
        result = analyzer.analyze(corpus)

        # The multi-email thread should have method "subject_heuristic"
        conversation_threads = [t for t in result.threads.values() if t.message_count > 1]
        assert len(conversation_threads) == 1
        assert conversation_threads[0].thread_method == "subject_heuristic"

    def test_single_email_threads_have_header_method(self):
        """Single-email threads (ungrouped) default to thread_method='header'."""
        from src.analyzers.thread_analyzer import ThreadAnalyzer

        msg1 = create_test_email(id="msg_001", subject="Standalone Email")
        corpus = create_test_corpus([msg1])
        analyzer = ThreadAnalyzer()
        result = analyzer.analyze(corpus)

        thread = list(result.threads.values())[0]
        assert thread.thread_method == "header"

    def test_mixed_methods_in_single_result(self):
        """Result can contain threads with different methods."""
        from src.analyzers.thread_analyzer import ThreadAnalyzer

        base_date = datetime(2024, 1, 15, 10, 0)

        # Header-grouped thread
        msg1 = create_test_email(
            id="msg_001",
            subject="Header Thread",
            received_date=base_date,
        )
        msg2 = create_test_email(
            id="msg_002",
            subject="Re: Header Thread",
            in_reply_to="msg_001",
            received_date=base_date + timedelta(hours=1),
        )

        # Subject-grouped thread (no headers)
        msg3 = create_test_email(
            id="msg_003",
            sender_email="alice@corp.com",
            sender_domain="corp.com",
            subject="Subject Thread",
            received_date=base_date,
        )
        msg4 = create_test_email(
            id="msg_004",
            sender_email="bob@corp.com",
            sender_domain="corp.com",
            subject="Re: Subject Thread",
            received_date=base_date + timedelta(days=1),
        )

        corpus = create_test_corpus([msg1, msg2, msg3, msg4])
        analyzer = ThreadAnalyzer()
        result = analyzer.analyze(corpus)

        methods = {t.thread_method for t in result.threads.values() if t.message_count > 1}
        assert "header" in methods
        assert "subject_heuristic" in methods


# ============================================================================
# Test Subject Heuristic Does Not Interfere with Header Grouping
# ============================================================================


class TestSubjectHeuristicNoInterference:
    """Test that subject heuristic only applies to ungrouped (single) emails."""

    def test_already_header_grouped_not_regrouped_by_subject(self):
        """Emails already grouped by headers are not re-processed by subject heuristic."""
        from src.analyzers.thread_analyzer import ThreadAnalyzer

        base_date = datetime(2024, 1, 15, 10, 0)
        # Two emails connected by In-Reply-To
        msg1 = create_test_email(
            id="msg_001",
            sender_email="alice@example.com",
            sender_domain="example.com",
            subject="Project Alpha",
            received_date=base_date,
        )
        msg2 = create_test_email(
            id="msg_002",
            sender_email="bob@example.com",
            sender_domain="example.com",
            subject="Re: Project Alpha",
            in_reply_to="msg_001",
            received_date=base_date + timedelta(hours=2),
        )
        # Third email, same subject but no headers, different domain
        msg3 = create_test_email(
            id="msg_003",
            sender_email="charlie@other.com",
            sender_domain="other.com",
            subject="Re: Project Alpha",
            received_date=base_date + timedelta(hours=3),
        )

        corpus = create_test_corpus([msg1, msg2, msg3])
        analyzer = ThreadAnalyzer()
        result = analyzer.analyze(corpus)

        # msg1 and msg2 are header-grouped; msg3 has different domain so stays separate
        header_thread = [t for t in result.threads.values() if t.message_count == 2]
        assert len(header_thread) == 1
        assert set(header_thread[0].email_ids) == {"msg_001", "msg_002"}
        assert header_thread[0].thread_method == "header"
