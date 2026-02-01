"""
Thread Analyzer module.

Analyzes email threads/conversations by parsing In-Reply-To and References headers.
Per Phase 8 Track 8A.1 specification.
"""
import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field

from src.models.corpus import Corpus
from src.models.email import Email

from .base import AnalysisError, BaseAnalyzer

logger = logging.getLogger(__name__)


@dataclass
class Thread:
    """Represents an email conversation thread."""

    thread_id: str
    email_ids: list[str] = field(default_factory=list)
    subject: str = ""
    participant_count: int = 0
    message_count: int = 0
    participants: set[str] = field(default_factory=set)

    def __post_init__(self):
        """Update counts after initialization."""
        self.message_count = len(self.email_ids)


@dataclass
class ThreadAnalysisResult:
    """Result of thread analysis."""

    threads: dict[str, Thread]
    total_threads: int = 0
    conversation_count: int = 0  # Threads with 2+ emails
    single_email_count: int = 0  # Threads with only 1 email

    def __post_init__(self):
        """Calculate counts from threads."""
        self.total_threads = len(self.threads)
        self.conversation_count = sum(
            1 for t in self.threads.values() if len(t.email_ids) > 1
        )
        self.single_email_count = sum(
            1 for t in self.threads.values() if len(t.email_ids) == 1
        )


class ThreadAnalyzer(BaseAnalyzer[ThreadAnalysisResult]):
    """
    Analyzes email threads/conversations.

    Identifies conversation threads by:
    1. Parsing In-Reply-To headers to find parent emails
    2. Parsing References headers to find thread chains
    3. Assigning unique thread IDs to conversation groups
    4. Single emails without replies get their own thread ID
    """

    @property
    def name(self) -> str:
        """Return human-readable analyzer name."""
        return "Thread Analyzer"

    def supports_incremental(self) -> bool:
        """Thread analyzer does not support incremental analysis."""
        return False

    def analyze(
        self,
        corpus: Corpus,
        progress_callback: Callable[[int, int], None] | None = None
    ) -> ThreadAnalysisResult:
        """
        Parse email headers to identify conversation threads.

        Args:
            corpus: Email corpus to analyze
            progress_callback: Optional callback(current, total)

        Returns:
            ThreadAnalysisResult with thread mappings and statistics

        Raises:
            AnalysisError: If corpus is empty or invalid
        """
        if not corpus.emails:
            raise AnalysisError("Thread Analyzer requires non-empty email list")

        logger.info(f"Starting thread analysis of {len(corpus.emails)} emails")

        total_emails = len(corpus.emails)
        if progress_callback:
            progress_callback(0, total_emails)

        # Build index of emails by ID for quick lookup
        email_by_id: dict[str, Email] = {email.id: email for email in corpus.emails}
        email_ids_set = set(email_by_id.keys())

        # Track which thread each email belongs to
        email_to_thread: dict[str, str] = {}

        # Build parent-child relationships
        # child_id -> parent_id (from In-Reply-To)
        parent_of: dict[str, str] = {}

        for email in corpus.emails:
            # Check In-Reply-To header
            if email.in_reply_to and email.in_reply_to in email_ids_set:
                parent_of[email.id] = email.in_reply_to

            # Check References header (last reference is usually the parent)
            elif email.references:
                for ref_id in reversed(email.references):
                    if ref_id in email_ids_set:
                        parent_of[email.id] = ref_id
                        break

        # Use Union-Find to group emails into threads
        # Find root of each email and unify those with parent relationships
        parent_union: dict[str, str] = {}

        def find_root(email_id: str) -> str:
            """Find root of the Union-Find set."""
            if email_id not in parent_union:
                parent_union[email_id] = email_id
            if parent_union[email_id] != email_id:
                parent_union[email_id] = find_root(parent_union[email_id])
            return parent_union[email_id]

        def union(id1: str, id2: str) -> None:
            """Unite two sets in Union-Find."""
            root1 = find_root(id1)
            root2 = find_root(id2)
            if root1 != root2:
                parent_union[root1] = root2

        # Unite emails based on parent relationships
        for child_id, parent_id in parent_of.items():
            union(child_id, parent_id)

        # Group emails by their root
        root_to_emails: dict[str, list[str]] = {}
        for email_id in email_ids_set:
            root = find_root(email_id)
            if root not in root_to_emails:
                root_to_emails[root] = []
            root_to_emails[root].append(email_id)

        # Create Thread objects
        threads: dict[str, Thread] = {}

        for _root_id, email_ids in root_to_emails.items():
            # Generate a unique thread ID
            thread_id = f"thread_{uuid.uuid4().hex[:12]}"

            # Get all emails in this thread
            thread_emails = [email_by_id[eid] for eid in email_ids]

            # Sort by received_date to find the original
            thread_emails_sorted = sorted(
                thread_emails,
                key=lambda e: e.received_date
            )

            # Get subject from the earliest email
            original_email = thread_emails_sorted[0]
            subject = original_email.subject

            # Count unique participants
            participants = {email.sender_email for email in thread_emails}

            thread = Thread(
                thread_id=thread_id,
                email_ids=email_ids,
                subject=subject,
                participant_count=len(participants),
                message_count=len(email_ids),
                participants=participants,
            )

            threads[thread_id] = thread

            # Update email_to_thread mapping
            for eid in email_ids:
                email_to_thread[eid] = thread_id

        if progress_callback:
            progress_callback(total_emails, total_emails)

        logger.info(f"Thread analysis complete: {len(threads)} threads identified")

        # Count statistics
        conversation_count = sum(1 for t in threads.values() if t.message_count > 1)
        single_count = sum(1 for t in threads.values() if t.message_count == 1)

        logger.info(
            f"Threads: {len(threads)} total, "
            f"{conversation_count} conversations, "
            f"{single_count} single emails"
        )

        return ThreadAnalysisResult(
            threads=threads,
            total_threads=len(threads),
            conversation_count=conversation_count,
            single_email_count=single_count,
        )
