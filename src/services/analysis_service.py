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

# Maps each analyzer type to its corresponding AnalysisResults field name.
# This is the single source of truth for analyzer-to-result-field mapping.
_ANALYZER_RESULT_FIELDS: dict[type[BaseAnalyzer], str] = {
    SenderAnalyzer: "sender_analysis",
    SubjectAnalyzer: "subject_patterns",
    TemporalAnalyzer: "temporal_patterns",
    VolumeAnalyzer: "volume_stats",
    SemanticAnalyzer: "content_clusters",
}


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
        """
        Build list of analyzer instances.

        This is the single source of truth for which analyzers run.
        To add a new analyzer, add it here and add its result field
        mapping to _ANALYZER_RESULT_FIELDS.
        """
        thresholds = self.config.thresholds
        return [
            SenderAnalyzer(thresholds=thresholds),
            SubjectAnalyzer(thresholds=thresholds),
            TemporalAnalyzer(thresholds=thresholds),
            VolumeAnalyzer(),
            SemanticAnalyzer(
                max_embedding_text_length=self.config.max_embedding_text_length,
                thresholds=thresholds,
            ),
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

        if progress_callback:
            progress_callback("Starting analysis...")

        results = {}

        for analyzer in self._analyzers:
            if progress_callback:
                progress_callback(f"Running {analyzer.name}...")

            # SemanticAnalyzer requires additional kwargs (num_clusters)
            kwargs: dict = {}
            if isinstance(analyzer, SemanticAnalyzer):
                kwargs["num_clusters"] = self.config.num_clusters

            result = analyzer.analyze(corpus, **kwargs)

            field_name = _ANALYZER_RESULT_FIELDS[type(analyzer)]
            results[field_name] = result

        if progress_callback:
            progress_callback("Analysis complete!")

        return AnalysisResults(**results)


__all__ = ["AnalysisService"]
