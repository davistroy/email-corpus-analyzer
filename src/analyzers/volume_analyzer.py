"""
Volume Analyzer module.

Implements volume statistics analysis per analyzer_contract.md lines 282-316.
Contract compliance: FR-019
"""

import logging
from collections.abc import Callable
from datetime import datetime

from ..models.analysis_results import VolumeStats
from ..models.corpus import Corpus
from .base import BaseAnalyzer

logger = logging.getLogger(__name__)


class VolumeAnalyzer(BaseAnalyzer[VolumeStats]):
    """Analyzes volume statistics in email corpus."""

    @property
    def name(self) -> str:
        """Return human-readable analyzer name."""
        return "Volume Analyzer"

    def analyze(  # type: ignore[override]
        self, corpus: Corpus, progress_callback: Callable[[int, int], None] | None = None
    ) -> VolumeStats:
        """
        Calculate corpus volume statistics.

        Args:
            corpus: Complete email corpus
            progress_callback: Optional callback(current, total)

        Returns:
            VolumeStats with counts, date ranges, averages

        Raises:
            ValueError: If corpus is empty or invalid
        """
        if not corpus.emails:
            raise ValueError("Corpus is empty")

        logger.debug(f"Starting volume analysis on {len(corpus.emails)} emails")

        # Calculate total emails
        total_emails = len(corpus.emails)

        # Calculate unique senders
        unique_senders_set = set()
        attachment_count = 0
        total_body_length = 0
        oldest_date: datetime | None = None
        newest_date: datetime | None = None

        for idx, email in enumerate(corpus.emails):
            # Count unique senders (normalized to lowercase)
            sender_email = str(email.sender_email).lower()
            unique_senders_set.add(sender_email)

            # Count emails with attachments
            if email.has_attachments:
                attachment_count += 1

            # Sum body lengths
            total_body_length += len(email.body_text)

            # Track date range
            if oldest_date is None or email.received_date < oldest_date:
                oldest_date = email.received_date

            if newest_date is None or email.received_date > newest_date:
                newest_date = email.received_date

            # Progress callback
            if progress_callback and (idx + 1) % 10 == 0:
                progress_callback(idx + 1, total_emails)

        # Final progress update
        if progress_callback:
            progress_callback(total_emails, total_emails)

        # Calculate derived metrics
        unique_senders = len(unique_senders_set)
        attachment_percentage = (attachment_count / total_emails * 100) if total_emails > 0 else 0.0
        avg_body_length_chars = int(total_body_length / total_emails) if total_emails > 0 else 0

        # Calculate date range and emails per day
        if oldest_date and newest_date:
            span_days = (newest_date - oldest_date).days
            # Handle same-day corpus (span_days == 0) by treating as 1 day
            if span_days == 0:
                span_days = 1
            emails_per_day = total_emails / span_days

            date_range = {
                "oldest": oldest_date.isoformat(),
                "newest": newest_date.isoformat(),
                "span_days": str(span_days),
            }
        else:
            # Fallback for edge case (should not happen if corpus is not empty)
            emails_per_day = 0.0
            date_range = {"oldest": "", "newest": "", "span_days": "0"}

        logger.debug(
            f"Volume stats: {total_emails} emails, {unique_senders} unique senders, "
            f"{attachment_count} with attachments ({attachment_percentage:.1f}%), "
            f"avg body length: {avg_body_length_chars} chars, "
            f"{emails_per_day:.2f} emails/day"
        )

        return VolumeStats(
            total_emails=total_emails,
            unique_senders=unique_senders,
            date_range=date_range,
            with_attachments=attachment_count,
            attachment_percentage=round(attachment_percentage, 2),
            avg_body_length_chars=avg_body_length_chars,
            emails_per_day=round(emails_per_day, 2),
        )
