"""
Extraction Service module.

Orchestrates email extraction from M365/Hotmail.
Decoupled from CLI for independent use.

Per Phase 7, Track 7B specification.
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from src.config.models import ExtractConfig
from src.models.corpus import Corpus

if TYPE_CHECKING:
    from src.extractors.m365_mcp_extractor import M365MCPExtractor

logger = logging.getLogger(__name__)


class ExtractionService:
    """
    Service for orchestrating email extraction.

    Provides high-level extraction API independent of CLI.
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
        self._extractor: M365MCPExtractor | None = None

    def _get_extractor(self) -> M365MCPExtractor:
        """Get or create the M365 MCP extractor."""
        if self._extractor is None:
            from src.extractors.m365_mcp_extractor import M365MCPExtractor

            self._extractor = M365MCPExtractor(
                user_email=self.user_email,
                batch_size=self.config.batch_size,
                checkpoint_interval=self.config.checkpoint_interval,
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
            ExtractionError: If extraction fails
        """
        if progress_callback:
            progress_callback("Starting email extraction...")

        extractor = self._get_extractor()

        if progress_callback:
            progress_callback(f"Extracting emails for {self.user_email}...")

        try:
            corpus = extractor.extract(
                since_last=since_last,
                existing_corpus=existing_corpus,
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
