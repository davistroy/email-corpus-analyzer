"""
Thread Analyzer module.

Analyzes email threads/conversations by parsing In-Reply-To and References headers.
Per Phase 8 Track 8A.1 specification.
Work Item 3.2: Added subject-based fallback grouping for emails without threading headers.
"""
import logging
import re
import uuid
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import timedelta

from src.models.corpus import Corpus
from src.models.email import Email

from .base import AnalysisError, BaseAnalyzer

logger = logging.getLogger(__name__)

# Pattern to match RE:/FWD:/FW: prefixes (case-insensitive, possibly repeated)
_REPLY_PREFIX_RE = re.compile(r'^(re|fwd|fw)\s*:\s*', re.IGNORECASE)


def _normalize_subject(subject: str) -> str:
    """
    Normalize an email subject for comparison.

    Strips RE:/FWD:/FW: prefixes (case-insensitive, repeated),
    normalizes whitespace, and lowercases the result.

    Args:
        subject: Raw email subject string.

    Returns:
        Normalized subject string for comparison.
    """
    result = subject
    # Repeatedly strip leading reply/forward prefixes
    while True:
        new_result = _REPLY_PREFIX_RE.sub('', result, count=1)
        if new_result == result:
            break
        result = new_result
    # Normalize whitespace and lowercase
    result = ' '.join(result.split())
    return result.lower()


@dataclass
class Thread:
    """Represents an email conversation thread."""

    thread_id: str
    email_ids: list[str] = field(default_factory=list)
    subject: str = ""
    participant_count: int = 0
    message_count: int = 0
    participants: set[str] = field(default_factory=set)
    thread_method: str = "header"

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
    3. Subject-based heuristic fallback for emails without threading headers
    4. Assigning unique thread IDs to conversation groups
    5. Single emails without replies get their own thread ID

    Args:
        subject_match_window_days: Maximum number of days between emails
            for subject-based heuristic grouping. Default is 7. Set to 0
            to disable subject-based fallback entirely.
    """

    def __init__(self, subject_match_window_days: int = 7):
        """
        Initialize ThreadAnalyzer.

        Args:
            subject_match_window_days: Time window in days for subject-based
                heuristic grouping. Emails with matching normalized subjects,
                same sender domain, and within this window will be grouped.
                Default: 7 days. Set to 0 to disable.
        """
        self._subject_match_window_days = subject_match_window_days

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

        First groups emails by In-Reply-To/References headers, then applies
        a subject-based heuristic fallback for ungrouped emails.

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

        # Track which emails were grouped by headers (multi-email groups)
        header_grouped_ids: set[str] = set()
        for _root_id, email_ids in root_to_emails.items():
            if len(email_ids) > 1:
                header_grouped_ids.update(email_ids)

        # Create Thread objects for header-grouped threads
        threads: dict[str, Thread] = {}

        for _root_id, email_ids in root_to_emails.items():
            if len(email_ids) > 1:
                # Multi-email thread from headers
                thread = self._create_thread(
                    email_ids, email_by_id, thread_method="header"
                )
                threads[thread.thread_id] = thread
                for eid in email_ids:
                    email_to_thread[eid] = thread.thread_id

        # ----------------------------------------------------------------
        # Second pass: subject-based heuristic for ungrouped emails
        # ----------------------------------------------------------------
        ungrouped_ids = [
            eid for eid in email_ids_set if eid not in header_grouped_ids
        ]

        if self._subject_match_window_days > 0 and ungrouped_ids:
            subject_threads = self._group_by_subject_heuristic(
                ungrouped_ids, email_by_id
            )
            for email_ids_group in subject_threads:
                if len(email_ids_group) > 1:
                    thread = self._create_thread(
                        email_ids_group, email_by_id,
                        thread_method="subject_heuristic"
                    )
                    threads[thread.thread_id] = thread
                    for eid in email_ids_group:
                        email_to_thread[eid] = thread.thread_id
                else:
                    # Single email - create its own thread
                    thread = self._create_thread(
                        email_ids_group, email_by_id, thread_method="header"
                    )
                    threads[thread.thread_id] = thread
                    email_to_thread[email_ids_group[0]] = thread.thread_id
        else:
            # No subject heuristic; create individual threads for ungrouped
            for eid in ungrouped_ids:
                thread = self._create_thread(
                    [eid], email_by_id, thread_method="header"
                )
                threads[thread.thread_id] = thread
                email_to_thread[eid] = thread.thread_id

        if progress_callback:
            progress_callback(total_emails, total_emails)

        logger.info(f"Thread analysis complete: {len(threads)} threads identified")

        # Count statistics
        conversation_count = sum(1 for t in threads.values() if t.message_count > 1)
        single_count = sum(1 for t in threads.values() if t.message_count == 1)

        # Count method breakdown
        header_count = sum(
            1 for t in threads.values()
            if t.thread_method == "header" and t.message_count > 1
        )
        heuristic_count = sum(
            1 for t in threads.values()
            if t.thread_method == "subject_heuristic"
        )

        logger.info(
            f"Threads: {len(threads)} total, "
            f"{conversation_count} conversations, "
            f"{single_count} single emails "
            f"(header: {header_count}, subject_heuristic: {heuristic_count})"
        )

        return ThreadAnalysisResult(
            threads=threads,
            total_threads=len(threads),
            conversation_count=conversation_count,
            single_email_count=single_count,
        )

    def _create_thread(
        self,
        email_ids: list[str],
        email_by_id: dict[str, Email],
        thread_method: str = "header",
    ) -> Thread:
        """
        Create a Thread object from a list of email IDs.

        Args:
            email_ids: List of email IDs in the thread.
            email_by_id: Lookup dict from email ID to Email.
            thread_method: How the thread was identified ("header" or "subject_heuristic").

        Returns:
            Thread object with populated fields.
        """
        thread_id = f"thread_{uuid.uuid4().hex[:12]}"
        thread_emails = [email_by_id[eid] for eid in email_ids]

        # Sort by received_date to find the original
        thread_emails_sorted = sorted(
            thread_emails, key=lambda e: e.received_date
        )

        # Get subject from the earliest email
        subject = thread_emails_sorted[0].subject

        # Count unique participants
        participants = {email.sender_email for email in thread_emails}

        return Thread(
            thread_id=thread_id,
            email_ids=email_ids,
            subject=subject,
            participant_count=len(participants),
            message_count=len(email_ids),
            participants=participants,
            thread_method=thread_method,
        )

    def _group_by_subject_heuristic(
        self,
        ungrouped_ids: list[str],
        email_by_id: dict[str, Email],
    ) -> list[list[str]]:
        """
        Group ungrouped emails by normalized subject + sender domain + time window.

        For each pair of ungrouped emails, if they share the same normalized
        subject and sender domain and are within the configured time window,
        they are merged into the same group.

        Args:
            ungrouped_ids: Email IDs not yet assigned to a multi-email thread.
            email_by_id: Lookup dict from email ID to Email.

        Returns:
            List of email ID groups. Each group is a list of email IDs.
        """
        window = timedelta(days=self._subject_match_window_days)

        # Build a key -> list of email IDs mapping
        # Key: (normalized_subject, sender_domain)
        subject_domain_groups: dict[tuple[str, str], list[str]] = defaultdict(list)

        for eid in ungrouped_ids:
            email = email_by_id[eid]
            norm_subj = _normalize_subject(email.subject)
            key = (norm_subj, email.sender_domain)
            subject_domain_groups[key].append(eid)

        result_groups: list[list[str]] = []

        for (_norm_subj, _domain), candidate_ids in subject_domain_groups.items():
            if len(candidate_ids) <= 1:
                # Single email with this subject+domain, no merge possible
                result_groups.append(candidate_ids)
                continue

            # Sort candidates by received_date
            candidates_sorted = sorted(
                candidate_ids,
                key=lambda eid: email_by_id[eid].received_date,
            )

            # Greedily merge: walk sorted list, start new group when time gap exceeds window
            current_group: list[str] = [candidates_sorted[0]]
            current_earliest = email_by_id[candidates_sorted[0]].received_date

            for eid in candidates_sorted[1:]:
                email_date = email_by_id[eid].received_date
                # Check if this email is within the window of the earliest in the group
                if (email_date - current_earliest) <= window:
                    current_group.append(eid)
                else:
                    # Start a new group
                    result_groups.append(current_group)
                    current_group = [eid]
                    current_earliest = email_date

            result_groups.append(current_group)

        return result_groups
