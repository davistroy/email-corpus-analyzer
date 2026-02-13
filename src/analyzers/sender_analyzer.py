"""
Sender Analyzer module.

Implements sender pattern analysis per analyzer_contract.md lines 38-100.
Contract compliance: FR-012, FR-013
"""
import logging
from collections import Counter, defaultdict
from collections.abc import Callable
from typing import TYPE_CHECKING

from ..models.analysis_results import SenderAnalysis
from ..models.corpus import Corpus
from ..models.sender import Sender, SenderType
from .base import BaseAnalyzer

if TYPE_CHECKING:
    from ..config.models import AnalyzerThresholds

logger = logging.getLogger(__name__)


class SenderAnalyzer(BaseAnalyzer[SenderAnalysis]):
    """Analyzes sender patterns in email corpus."""

    def __init__(self, thresholds: "AnalyzerThresholds | None" = None):
        """
        Initialize SenderAnalyzer.

        Args:
            thresholds: Optional analyzer thresholds config. Uses defaults if None.
        """
        if thresholds is None:
            from ..config.models import AnalyzerThresholds
            thresholds = AnalyzerThresholds()
        self.thresholds = thresholds

    @property
    def name(self) -> str:
        """Return human-readable analyzer name."""
        return "Sender Analyzer"

    def analyze(
        self,
        corpus: Corpus,
        progress_callback: Callable[[int, int], None] | None = None
    ) -> SenderAnalysis:
        """
        Analyze sender patterns.

        Args:
            corpus: Complete email corpus
            progress_callback: Optional callback(current, total)

        Returns:
            SenderAnalysis with top_senders, top_domains, unique counts

        Raises:
            ValueError: If corpus is empty or invalid
        """
        if not corpus.emails:
            raise ValueError("Corpus is empty")

        logger.debug(f"Starting sender analysis on {len(corpus.emails)} emails")

        # Count emails per sender
        sender_counts = Counter()
        sender_names = {}
        sender_subjects = defaultdict(list)
        sender_email_ids = defaultdict(list)
        domain_counts = Counter()

        total_emails = len(corpus.emails)
        for idx, email in enumerate(corpus.emails):
            sender_email = str(email.sender_email).lower()
            sender_counts[sender_email] += 1

            # Store sender name (use first non-empty name encountered)
            if email.sender_name and sender_email not in sender_names:
                sender_names[sender_email] = email.sender_name

            # Collect sample subjects (max 5)
            if len(sender_subjects[sender_email]) < 5:
                sender_subjects[sender_email].append(email.subject)

            # Collect email IDs
            sender_email_ids[sender_email].append(email.id)

            # Count domains
            domain_counts[email.sender_domain] += 1

            # Progress callback
            if progress_callback and (idx + 1) % 10 == 0:
                progress_callback(idx + 1, total_emails)

        # Final progress update
        if progress_callback:
            progress_callback(total_emails, total_emails)

        logger.debug(
            f"Counted {len(sender_counts)} unique senders "
            f"from {len(domain_counts)} unique domains"
        )

        # Extract top N senders by frequency
        top_sender_emails = [email for email, _ in sender_counts.most_common(self.thresholds.top_senders)]
        top_senders = []

        for sender_email in top_sender_emails:
            sender = Sender(
                email=sender_email,
                name=sender_names.get(sender_email, ""),
                domain=sender_email.split('@')[1] if '@' in sender_email else "",
                type=SenderType.PERSONAL,  # Will be classified next
                frequency_count=sender_counts[sender_email],
                sample_subjects=sender_subjects[sender_email],
                email_ids=sender_email_ids[sender_email]
            )
            # Classify sender type
            sender.type = self.classify_sender_type(sender)
            top_senders.append(sender)

        # Extract top N domains by frequency
        top_domains = [
            {"domain": domain, "count": count}
            for domain, count in domain_counts.most_common(self.thresholds.top_domains)
        ]

        logger.debug(
            f"Extracted top {len(top_senders)} senders "
            f"and top {len(top_domains)} domains"
        )

        return SenderAnalysis(
            top_senders=top_senders,
            top_domains=top_domains,
            unique_senders=len(sender_counts),
            unique_domains=len(domain_counts)
        )

    def classify_sender_type(self, sender: Sender) -> SenderType:
        """
        Classify sender as personal/service/marketing/work.

        Per FR-012, FR-013:
        - Service: email or domain contain "noreply", "no-reply", "donotreply", "notification", "notify", "alert"
        - Marketing: >10 emails + keywords "unsubscribe", "promotional", "offer", "discount", "sale"
        - Work: keywords "meeting", "project", "team", "re:", "fwd:"
        - Personal: default

        Args:
            sender: Sender object with domain, count, sample_subjects

        Returns:
            SenderType enum value
        """
        # Check for service indicators in email or domain
        service_indicators = ["noreply", "no-reply", "donotreply", "notification", "notify", "alert"]
        email_lower = sender.email.lower()
        domain_lower = sender.domain.lower()
        if any(indicator in email_lower or indicator in domain_lower for indicator in service_indicators):
            logger.debug(f"Classified {sender.email} as SERVICE (email/domain contains service indicator)")
            return SenderType.SERVICE

        # Combine all sample subjects for keyword analysis
        all_subjects_text = " ".join(sender.sample_subjects).lower()

        # Check for marketing indicators (requires sufficient emails)
        marketing_keywords = ["unsubscribe", "promotional", "offer", "discount", "sale", "promotion"]
        if sender.frequency_count > self.thresholds.marketing_min_emails:
            if any(keyword in all_subjects_text for keyword in marketing_keywords):
                logger.debug(
                    f"Classified {sender.email} as MARKETING "
                    f"(count: {sender.frequency_count}, keywords found)"
                )
                return SenderType.MARKETING

        # Check for work indicators
        work_keywords = ["meeting", "project", "team", "re:", "fwd:"]
        if any(keyword in all_subjects_text for keyword in work_keywords):
            logger.debug(f"Classified {sender.email} as WORK (keywords found)")
            return SenderType.WORK

        # Default to personal
        logger.debug(f"Classified {sender.email} as PERSONAL (default)")
        return SenderType.PERSONAL
