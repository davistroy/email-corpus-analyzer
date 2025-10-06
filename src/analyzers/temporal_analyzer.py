"""
Temporal pattern analyzer for email corpus.

Per analyzer_contract.md lines 225-278.
"""
import logging
from collections import defaultdict
from collections.abc import Callable
from datetime import datetime

from ..models.analysis_results import TemporalPatterns
from ..models.corpus import Corpus

logger = logging.getLogger(__name__)


class TemporalAnalyzer:
    """Analyzes temporal patterns in email corpus."""

    def analyze(
        self,
        corpus: Corpus,
        progress_callback: Callable[[int, int], None] | None = None
    ) -> TemporalPatterns:
        """
        Analyze temporal email patterns.

        Args:
            corpus: Email corpus to analyze
            progress_callback: Optional callback for progress updates (current, total)

        Returns:
            TemporalPatterns with frequency classifications

        FR-018: Classifies senders by frequency:
            - one-time: 1 email
            - daily: avg interval < 2 days (>=10 emails)
            - weekly: avg interval < 8 days (>=10 emails)
            - monthly: avg interval < 35 days (>=10 emails)
            - occasional: default
        """
        logger.debug(f"Starting temporal analysis on {len(corpus.emails)} emails")

        # Group emails by sender
        sender_emails: dict[str, list[datetime]] = defaultdict(list)

        for idx, email in enumerate(corpus.emails):
            sender_emails[email.sender_email].append(email.received_date)

            if progress_callback and (idx + 1) % 100 == 0:
                progress_callback(idx + 1, len(corpus.emails))

        # Sort dates for each sender
        for sender in sender_emails:
            sender_emails[sender].sort()

        logger.debug(f"Grouped emails from {len(sender_emails)} unique senders")

        # Classify each sender's frequency
        frequency_distribution: dict[str, int] = {
            "one-time": 0,
            "daily": 0,
            "weekly": 0,
            "monthly": 0,
            "occasional": 0
        }

        sender_frequencies: dict[str, dict] = {}

        for sender, dates in sender_emails.items():
            frequency_type = self.classify_frequency(dates)
            frequency_distribution[frequency_type] += 1

            sender_frequencies[sender] = {
                "type": frequency_type,
                "count": len(dates),
                "first": dates[0].isoformat(),
                "last": dates[-1].isoformat()
            }

        # Final progress callback
        if progress_callback:
            progress_callback(len(corpus.emails), len(corpus.emails))

        logger.debug(
            f"Temporal analysis complete. Distribution: {frequency_distribution}"
        )

        return TemporalPatterns(
            frequency_distribution=frequency_distribution,
            sender_frequencies=sender_frequencies
        )

    def classify_frequency(self, dates: list[datetime]) -> str:
        """
        Classify sender frequency based on email patterns.

        Args:
            dates: List of email received dates (sorted)

        Returns:
            "one-time" | "daily" | "weekly" | "monthly" | "occasional"

        FR-018 Classification Rules:
            - one-time: 1 email
            - daily: avg interval < 2 days (>=10 emails)
            - weekly: avg interval < 8 days (>=10 emails)
            - monthly: avg interval < 35 days (>=10 emails)
            - occasional: default
        """
        email_count = len(dates)

        # One-time sender: exactly 1 email
        if email_count == 1:
            logger.debug("Classified as one-time: 1 email")
            return "one-time"

        # Need at least 10 emails for frequency classification
        if email_count < 10:
            logger.debug(f"Classified as occasional: {email_count} emails (< 10)")
            return "occasional"

        # Calculate average interval between emails
        total_span = (dates[-1] - dates[0]).total_seconds()
        intervals = email_count - 1

        if intervals == 0:
            # All emails on same date
            logger.debug("Classified as occasional: all emails on same date")
            return "occasional"

        avg_interval_days = total_span / intervals / 86400  # seconds to days

        logger.debug(
            f"Average interval: {avg_interval_days:.2f} days "
            f"({email_count} emails)"
        )

        # Apply classification thresholds
        if avg_interval_days < 2:
            return "daily"
        if avg_interval_days < 8:
            return "weekly"
        if avg_interval_days < 35:
            return "monthly"
        return "occasional"
