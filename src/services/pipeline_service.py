"""
Pipeline Service module.

Orchestrates the complete email analysis pipeline.
Decoupled from CLI for independent use.

Per Phase 7, Track 7B specification.
"""
import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from src.config.models import AppConfig
from src.models.analysis_results import AnalysisResults
from src.models.category import Category
from src.models.corpus import Corpus
from src.services.analysis_service import AnalysisService
from src.services.extraction_service import ExtractionService
from src.services.suggestion_service import SuggestionService

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    """Result from running the complete pipeline."""

    corpus: Corpus
    analysis: AnalysisResults
    categories: list[Category]
    output_dir: Path


class PipelineService:
    """
    Service for orchestrating the complete email analysis pipeline.

    Provides high-level pipeline API independent of CLI.
    Coordinates extraction, analysis, and suggestion services.
    """

    def __init__(self, config: AppConfig):
        """
        Initialize pipeline service.

        Args:
            config: Application configuration
        """
        self.config = config

    def run(
        self,
        output_dir: Path,
        progress_callback: Callable[[str], None] | None = None,
        skip_extraction: bool = False,
        existing_corpus: Corpus | None = None,
    ) -> PipelineResult:
        """
        Run complete email analysis pipeline.

        Args:
            output_dir: Output directory for all files
            progress_callback: Optional callback(message) for status updates
            skip_extraction: If True, skip extraction (requires existing_corpus)
            existing_corpus: Pre-existing corpus to use instead of extracting

        Returns:
            PipelineResult with corpus, analysis, and categories

        Raises:
            ValueError: If skip_extraction is True but no existing_corpus provided
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        # Step 1: Extraction
        if skip_extraction:
            if existing_corpus is None:
                raise ValueError(
                    "existing_corpus required when skip_extraction is True"
                )
            corpus = existing_corpus
            if progress_callback:
                progress_callback("Using existing corpus, skipping extraction...")
        else:
            if progress_callback:
                progress_callback("Starting extraction phase...")

            extraction_service = ExtractionService(
                config=self.config.extract,
                user_email=str(self.config.user_email) if self.config.user_email else "",
                output_dir=output_dir,
            )

            corpus = extraction_service.run(
                progress_callback=progress_callback,
            )

            # Save corpus
            corpus_path = output_dir / "email_corpus.json"
            extraction_service.save_corpus(corpus, corpus_path)

            if progress_callback:
                progress_callback(f"Saved corpus to {corpus_path}")

        # Step 2: Analysis
        if progress_callback:
            progress_callback("Starting analysis phase...")

        analysis_service = AnalysisService(config=self.config.analyze)

        analysis = analysis_service.run(
            corpus=corpus,
            progress_callback=progress_callback,
        )

        # Save analysis
        analysis_path = output_dir / "corpus_analysis_results.json"
        analysis_path.write_text(analysis.model_dump_json(indent=2))

        if progress_callback:
            progress_callback(f"Saved analysis to {analysis_path}")

        # Step 3: Suggestions
        if progress_callback:
            progress_callback("Starting suggestion phase...")

        suggestion_service = SuggestionService(config=self.config.suggest)

        categories = suggestion_service.run(
            analysis=analysis,
            progress_callback=progress_callback,
        )

        # Save suggestions
        suggestions_path = output_dir / "category_suggestions.json"
        suggestions_path.write_text(
            "[" + ",\n".join(c.model_dump_json() for c in categories) + "]"
        )

        if progress_callback:
            progress_callback(f"Saved suggestions to {suggestions_path}")
            progress_callback("Pipeline complete!")

        return PipelineResult(
            corpus=corpus,
            analysis=analysis,
            categories=categories,
            output_dir=output_dir,
        )


__all__ = ["PipelineService", "PipelineResult"]
