"""
Analysis Service module.

Orchestrates email corpus analysis.
Decoupled from CLI for independent use.

Per Phase 7, Track 7B specification.
"""
import logging
from collections.abc import Callable

from src.analyzers import (
    SemanticAnalyzer,
    SenderAnalyzer,
    SubjectAnalyzer,
    TemporalAnalyzer,
    VolumeAnalyzer,
)
from src.analyzers.base import BaseAnalyzer
from src.config.models import AnalyzeConfig
from src.models.analysis_results import AnalysisResults
from src.models.corpus import Corpus

logger = logging.getLogger(__name__)


class AnalysisService:
    """
    Service for orchestrating email analysis.

    Provides high-level analysis API independent of CLI.
    Runs all configured analyzers on a corpus.
    """

    def __init__(self, config: AnalyzeConfig):
        """
        Initialize analysis service.

        Args:
            config: Analysis configuration
        """
        self.config = config
        self._analyzers = self._build_analyzers()

    def _build_analyzers(self) -> list[BaseAnalyzer]:
        """Build list of analyzer instances."""
        thresholds = self.config.thresholds
        return [
            SenderAnalyzer(thresholds=thresholds),
            SubjectAnalyzer(thresholds=thresholds),
            TemporalAnalyzer(thresholds=thresholds),
            VolumeAnalyzer(),
            # SemanticAnalyzer is handled separately due to special config
        ]

    def run(
        self,
        corpus: Corpus,
        incremental: bool = False,
        progress_callback: Callable[[str], None] | None = None,
    ) -> AnalysisResults:
        """
        Run all analyzers on corpus.

        Args:
            corpus: Email corpus to analyze
            incremental: If True, use incremental analysis where supported
            progress_callback: Optional callback(message) for status updates

        Returns:
            Combined analysis results

        Raises:
            ValueError: If corpus is empty
        """
        if not corpus.emails:
            raise ValueError("Cannot analyze empty corpus")

        thresholds = self.config.thresholds

        if progress_callback:
            progress_callback("Starting analysis...")

        # Run standard analyzers
        if progress_callback:
            progress_callback(f"Running {self._analyzers[0].name}...")

        sender_analysis = SenderAnalyzer(thresholds=thresholds).analyze(corpus)

        if progress_callback:
            progress_callback("Running Subject Analyzer...")

        subject_patterns = SubjectAnalyzer(thresholds=thresholds).analyze(corpus)

        if progress_callback:
            progress_callback("Running Temporal Analyzer...")

        temporal_patterns = TemporalAnalyzer(thresholds=thresholds).analyze(corpus)

        if progress_callback:
            progress_callback("Running Volume Analyzer...")

        volume_stats = VolumeAnalyzer().analyze(corpus)

        # Run semantic analyzer
        if progress_callback:
            progress_callback("Running Semantic Analyzer...")

        semantic_analyzer = SemanticAnalyzer(
            max_embedding_text_length=self.config.max_embedding_text_length,
            thresholds=thresholds,
        )
        content_clusters = semantic_analyzer.analyze(
            corpus,
            num_clusters=self.config.num_clusters,
        )

        if progress_callback:
            progress_callback("Analysis complete!")

        return AnalysisResults(
            sender_analysis=sender_analysis,
            subject_patterns=subject_patterns,
            content_clusters=content_clusters,
            temporal_patterns=temporal_patterns,
            volume_stats=volume_stats,
        )


__all__ = ["AnalysisService"]
