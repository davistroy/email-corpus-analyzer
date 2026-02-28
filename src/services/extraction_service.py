"""
Extraction Service module.

Orchestrates email extraction from M365/Hotmail and/or Gmail.
Decoupled from CLI for independent use.

Per Phase 7, Track 7B specification.
Rewired in Work Item 1.1 to use real extractors instead of MCP stubs.
Updated in Work Item 1.2 to support Gmail and multi-source extraction.
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from src.config.models import ExtractConfig
from src.models.corpus import Corpus, CorpusMetadata

if TYPE_CHECKING:
    from src.extractors.gmail_extractor import GmailExtractor
    from src.extractors.m365_extractor import EmailExtractor

logger = logging.getLogger(__name__)


class _SourceConfig:
    """Configuration for a single extraction source."""

    __slots__ = ("label", "factory_attr")

    def __init__(self, label: str, factory_attr: str):
        self.label = label
        self.factory_attr = factory_attr


# Registry mapping source names to their configs.
# Adding a new source requires only a new entry here + a _get_<source>_extractor method.
_SOURCE_REGISTRY: dict[str, list[_SourceConfig]] = {
    "hotmail": [_SourceConfig(label="M365/Hotmail", factory_attr="_get_m365_extractor")],
    "gmail": [_SourceConfig(label="Gmail", factory_attr="_get_gmail_extractor")],
    "both": [
        _SourceConfig(label="M365/Hotmail", factory_attr="_get_m365_extractor"),
        _SourceConfig(label="Gmail", factory_attr="_get_gmail_extractor"),
    ],
}


class ExtractionService:
    """
    Service for orchestrating email extraction.

    Provides high-level extraction API independent of CLI.
    Supports M365/Hotmail, Gmail, or both sources based on config.source.
    """

    def __init__(
        self,
        config: ExtractConfig,
        user_email: str,
        output_dir: Path | None = None,
    ):
        """
        Initialize extraction service.

        Args:
            config: Extraction configuration (includes source and gmail_email)
            user_email: Primary email address (M365/Hotmail)
            output_dir: Optional output directory for corpus file
        """
        self.config = config
        self.user_email = user_email
        self.output_dir = output_dir
        self._m365_extractor: EmailExtractor | None = None
        self._gmail_extractor: GmailExtractor | None = None

    def _get_m365_extractor(self) -> EmailExtractor:
        """Get or create the M365 email extractor."""
        if self._m365_extractor is None:
            from src.extractors.m365_extractor import EmailExtractor

            checkpoint_dir = str(self.output_dir) if self.output_dir else "outputs"
            self._m365_extractor = EmailExtractor(
                user_email=self.user_email,
                checkpoint_dir=checkpoint_dir,
            )
        return self._m365_extractor

    def _get_gmail_extractor(self) -> GmailExtractor:
        """Get or create the Gmail extractor."""
        if self._gmail_extractor is None:
            from src.extractors.gmail_extractor import GmailExtractor

            checkpoint_dir = str(self.output_dir) if self.output_dir else "outputs"
            gmail_email = self.config.gmail_email or self.user_email
            self._gmail_extractor = GmailExtractor(
                user_email=gmail_email,
                checkpoint_dir=checkpoint_dir,
            )
        return self._gmail_extractor

    def _run_single_extractor(
        self,
        extractor,
        source_label: str,
        progress_callback: Callable[[str], None] | None = None,
        since_last: bool = False,
        existing_corpus: Corpus | None = None,
        email_progress_callback: Callable[[int, int], None] | None = None,
    ) -> Corpus:
        """
        Run extraction with a single extractor.

        Args:
            extractor: EmailExtractor or GmailExtractor instance
            source_label: Label for logging (e.g. "M365/Hotmail", "Gmail")
            progress_callback: Optional callback for status updates
            since_last: If True, do incremental extraction
            existing_corpus: Existing corpus for incremental mode
            email_progress_callback: Optional per-email callback(current, total)

        Returns:
            Extracted corpus
        """
        if progress_callback:
            progress_callback(f"Extracting emails from {source_label}...")

        if since_last and existing_corpus is not None:
            incremental_result = extractor.extract_incremental(
                existing_corpus=existing_corpus,
                max_batch_size=self.config.batch_size,
                checkpoint_interval=self.config.checkpoint_interval,
                progress_callback=email_progress_callback,
            )

            corpus = incremental_result.corpus

            if incremental_result.failed_emails:
                logger.warning(
                    f"{len(incremental_result.failed_emails)} emails failed "
                    f"during incremental {source_label} extraction"
                )

            if progress_callback:
                progress_callback(
                    f"{source_label} incremental extraction complete: "
                    f"{incremental_result.new_emails_count} new emails "
                    f"({incremental_result.previous_count} -> "
                    f"{incremental_result.total_count} total)"
                )
        else:
            result = extractor.extract_all(
                max_batch_size=self.config.batch_size,
                checkpoint_interval=self.config.checkpoint_interval,
                progress_callback=email_progress_callback,
            )

            corpus = result.corpus

            if result.failed_emails:
                logger.warning(
                    f"{result.failure_count} of {result.total_attempted} "
                    f"emails failed during {source_label} extraction "
                    f"(success rate: {result.success_rate:.1%})"
                )

            if progress_callback:
                progress_callback(
                    f"{source_label}: extracted {corpus.extraction_metadata.total_emails} emails"
                )

        return corpus

    @staticmethod
    def _merge_corpora(
        corpora: list[Corpus],
        user_email: str,
        source_labels: list[str],
    ) -> Corpus:
        """
        Merge multiple corpora, deduplicating by email ID.

        Args:
            corpora: List of Corpus objects to merge
            user_email: Primary user email for metadata
            source_labels: Labels for each corpus source

        Returns:
            Merged corpus with deduplicated emails
        """
        seen_ids: set[str] = set()
        merged_emails = []

        for corpus in corpora:
            for email in corpus.emails:
                if email.id not in seen_ids:
                    seen_ids.add(email.id)
                    merged_emails.append(email)

        # Compute email IDs hash for change detection
        email_ids_hash = ""
        if merged_emails:
            sorted_ids = sorted(e.id for e in merged_emails)
            combined = "|".join(sorted_ids)
            email_ids_hash = hashlib.sha256(combined.encode()).hexdigest()

        metadata = CorpusMetadata(
            extraction_date=datetime.now(),
            total_emails=len(merged_emails),
            source="+".join(source_labels),
            user_email=user_email,
            last_extraction_date=datetime.now(),
            email_ids_hash=email_ids_hash,
            extraction_params={"sources": source_labels},
        )

        return Corpus(extraction_metadata=metadata, emails=merged_emails)

    def run(
        self,
        progress_callback: Callable[[str], None] | None = None,
        since_last: bool = False,
        existing_corpus: Corpus | None = None,
        email_progress_callback: Callable[[int, int], None] | None = None,
    ) -> Corpus:
        """
        Run email extraction based on configured source.

        Uses _SOURCE_REGISTRY to dispatch extraction. Single-source entries
        return the corpus directly; multi-source entries merge with deduplication.

        Args:
            progress_callback: Optional callback(message) for status updates
            since_last: If True, only extract emails since last extraction
            existing_corpus: Existing corpus for incremental extraction
            email_progress_callback: Optional per-email callback(current, total) for progress bars

        Returns:
            Extracted email corpus

        Raises:
            ValueError: If source is not in _SOURCE_REGISTRY
            ConnectionError: If email server is unreachable
            AuthenticationError: If authentication fails
        """
        if progress_callback:
            progress_callback("Starting email extraction...")

        source = self.config.source

        if source not in _SOURCE_REGISTRY:
            raise ValueError(f"Unknown source: {source!r}")

        source_configs = _SOURCE_REGISTRY[source]

        try:
            if len(source_configs) > 1 and progress_callback:
                labels = " and ".join(sc.label for sc in source_configs)
                progress_callback(f"Extracting from {labels}...")

            corpora: list[Corpus] = []
            for sc in source_configs:
                extractor = getattr(self, sc.factory_attr)()
                corpus = self._run_single_extractor(
                    extractor,
                    sc.label,
                    progress_callback,
                    since_last,
                    existing_corpus,
                    email_progress_callback,
                )
                corpora.append(corpus)

            # Single source: return directly
            if len(corpora) == 1:
                return corpora[0]

            # Multi-source: merge with deduplication
            source_labels = [sc.label for sc in source_configs]
            merged = self._merge_corpora(
                corpora,
                user_email=self.user_email,
                source_labels=source_labels,
            )

            if progress_callback:
                individual = " + ".join(str(len(c.emails)) for c in corpora)
                progress_callback(
                    f"Merged corpus: {len(merged.emails)} emails (deduplicated from {individual})"
                )

            return merged

        except Exception as e:
            logger.error(f"Extraction failed: {e}")
            raise

    def save_corpus(self, corpus: Corpus, output_path: Path) -> None:
        """
        Save corpus to file atomically.

        Uses atomic_write_text to ensure the file is either fully written or
        not modified at all. An interrupted write cannot corrupt an existing file.

        Args:
            corpus: Corpus to save
            output_path: Path to save corpus JSON
        """
        from src.utils.file_manager import atomic_write_text

        output_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(output_path, corpus.model_dump_json(indent=2))
        logger.info(f"Saved corpus to {output_path} (atomic)")


__all__ = ["ExtractionService"]
