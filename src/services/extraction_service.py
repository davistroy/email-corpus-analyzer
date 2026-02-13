"""
Extraction Service module.

Orchestrates email extraction from M365/Hotmail via the real
GraphAPIClient-backed EmailExtractor. Decoupled from CLI for
independent use.

Per Phase 7, Track 7B specification.
Rewired in Work Item 1.1 to use real extractors instead of MCP stubs.
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from src.config.models import ExtractConfig
from src.models.corpus import Corpus

if TYPE_CHECKING:
    from src.extractors.m365_extractor import EmailExtractor

logger = logging.getLogger(__name__)


class ExtractionService:
    """
    Service for orchestrating email extraction.

    Provides high-level extraction API independent of CLI.
    Uses EmailExtractor (backed by GraphAPIClient with real MSAL auth)
    for M365/Hotmail extraction.
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
            config: Extraction configuration
            user_email: M365/Hotmail email address
            output_dir: Optional output directory for corpus file
        """
        self.config = config
        self.user_email = user_email
        self.output_dir = output_dir
        self._extractor: EmailExtractor | None = None

    def _get_extractor(self) -> EmailExtractor:
        """Get or create the M365 email extractor."""
        if self._extractor is None:
            from src.extractors.m365_extractor import EmailExtractor

            # Determine checkpoint directory from output_dir or default
            checkpoint_dir = str(self.output_dir) if self.output_dir else "outputs"

            self._extractor = EmailExtractor(
                user_email=self.user_email,
                checkpoint_dir=checkpoint_dir,
            )
        return self._extractor

    def run(
        self,
        progress_callback: Callable[[str], None] | None = None,
        since_last: bool = False,
        existing_corpus: Corpus | None = None,
    ) -> Corpus:
        """
        Run email extraction.

        Args:
            progress_callback: Optional callback(message) for status updates
            since_last: If True, only extract emails since last extraction
            existing_corpus: Existing corpus for incremental extraction

        Returns:
            Extracted email corpus

        Raises:
            ConnectionError: If M365 server is unreachable
            AuthenticationError: If M365 authentication fails
        """
        if progress_callback:
            progress_callback("Starting email extraction...")

        extractor = self._get_extractor()

        if progress_callback:
            progress_callback(f"Extracting emails for {self.user_email}...")

        try:
            if since_last and existing_corpus is not None:
                # Incremental extraction: only fetch new emails
                incremental_result = extractor.extract_incremental(
                    existing_corpus=existing_corpus,
                    max_batch_size=self.config.batch_size,
                    checkpoint_interval=self.config.checkpoint_interval,
                )

                corpus = incremental_result.corpus

                if incremental_result.failed_emails:
                    logger.warning(
                        f"{len(incremental_result.failed_emails)} emails failed "
                        f"during incremental extraction"
                    )

                if progress_callback:
                    progress_callback(
                        f"Incremental extraction complete: "
                        f"{incremental_result.new_emails_count} new emails "
                        f"({incremental_result.previous_count} -> "
                        f"{incremental_result.total_count} total)"
                    )
            else:
                # Full extraction
                result = extractor.extract_all(
                    max_batch_size=self.config.batch_size,
                    checkpoint_interval=self.config.checkpoint_interval,
                )

                corpus = result.corpus

                if result.failed_emails:
                    logger.warning(
                        f"{result.failure_count} of {result.total_attempted} "
                        f"emails failed during extraction "
                        f"(success rate: {result.success_rate:.1%})"
                    )

                if progress_callback:
                    progress_callback(
                        f"Extracted {corpus.extraction_metadata.total_emails} emails"
                    )

            return corpus

        except Exception as e:
            logger.error(f"Extraction failed: {e}")
            raise

    def save_corpus(self, corpus: Corpus, output_path: Path) -> None:
        """
        Save corpus to file.

        Args:
            corpus: Corpus to save
            output_path: Path to save corpus JSON
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(corpus.model_dump_json(indent=2))
        logger.info(f"Saved corpus to {output_path}")


__all__ = ["ExtractionService"]
