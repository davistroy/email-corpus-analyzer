"""
Analysis Service module.

Orchestrates email corpus analysis.
Decoupled from CLI for independent use.

Per Phase 7, Track 7B specification.
Work Item 2.1: Expanded to be the single source of truth for all analysis,
delegating to run_full_analysis() with full feature parity.
"""

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING

from src.analyzers import (
    SemanticAnalyzer,
    SenderAnalyzer,
    SubjectAnalyzer,
    TemporalAnalyzer,
    VolumeAnalyzer,
    run_full_analysis,
)
from src.analyzers.base import BaseAnalyzer
from src.config.models import AnalyzeConfig
from src.models.analysis_results import AnalysisResults
from src.models.corpus import Corpus

if TYPE_CHECKING:
    from src.cache.embedding_cache import EmbeddingCache

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
    Delegates to run_full_analysis() as the single authoritative path
    for all analysis features including auto-clustering, incremental
    analysis, and cluster visualization.
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
        progress_callback: Callable[[str], None] | None = None,
        auto_clusters: bool = False,
        cluster_method: str = "silhouette",
        embedding_cache: "EmbeddingCache | None" = None,
        cluster_viz: bool = False,
    ) -> tuple[AnalysisResults, dict | None]:
        """
        Run all analyzers on corpus.

        Delegates to run_full_analysis() with all config and runtime
        parameters. This is the single authoritative entry point for
        corpus analysis.

        Args:
            corpus: Email corpus to analyze
            progress_callback: Optional callback(message) for status updates.
                Accepts a single string message. Internally adapted to
                the 3-arg format expected by run_full_analysis.
            auto_clusters: If True, automatically determine optimal k
            cluster_method: Method for auto-clustering: "elbow" or "silhouette"
            embedding_cache: Optional EmbeddingCache for incremental analysis
            cluster_viz: If True, generate cluster visualization PNG

        Returns:
            Tuple of (AnalysisResults, incremental_stats dict or None).
            incremental_stats is None when embedding_cache is not provided.

        Raises:
            ValueError: If corpus is empty
        """
        if not corpus.emails:
            raise ValueError("Cannot analyze empty corpus")

        if progress_callback:
            progress_callback("Starting analysis...")

        # Adapt single-arg progress callback to 3-arg format for run_full_analysis
        rfa_progress: Callable[[str, int, int], None] | None = None
        if progress_callback:

            def rfa_progress(analyzer_name: str, current: int, total: int) -> None:
                progress_callback(f"Running {analyzer_name}... ({current}/{total})")

        results, incremental_stats = run_full_analysis(
            corpus=corpus,
            num_clusters=self.config.num_clusters,
            auto_clusters=auto_clusters,
            cluster_method=cluster_method,
            max_embedding_text_length=self.config.max_embedding_text_length,
            auto_cluster_min=self.config.auto_cluster_min,
            auto_cluster_max=self.config.auto_cluster_max,
            progress_callback=rfa_progress,
            embedding_cache=embedding_cache,
            thresholds=self.config.thresholds,
        )

        # Generate cluster visualization if requested
        if cluster_viz:
            self._generate_viz(corpus, results)

        if progress_callback:
            progress_callback("Analysis complete!")

        return results, incremental_stats

    def _generate_viz(self, corpus: Corpus, results: AnalysisResults) -> None:
        """
        Generate cluster visualization PNG.

        Calls the standalone generate_cluster_visualization function
        from the semantic analyzer module. Requires re-generating
        embeddings and cluster labels since run_full_analysis does not
        expose them.

        Args:
            corpus: Email corpus (needed for embedding text)
            results: AnalysisResults with content_clusters
        """
        try:
            from sklearn.cluster import KMeans

            from src.analyzers.semantic_analyzer import SemanticAnalyzer as _SemanticAnalyzer
            from src.analyzers.semantic_analyzer import generate_cluster_visualization
            from src.utils.paths import PathConfig

            analyzer = _SemanticAnalyzer(
                max_embedding_text_length=self.config.max_embedding_text_length,
                thresholds=self.config.thresholds,
            )
            analyzer._ensure_model_loaded()

            texts = [
                email.combined_text_with_limit(self.config.max_embedding_text_length)
                for email in corpus.emails
            ]
            assert analyzer.model is not None
            embeddings = analyzer.model.encode(
                texts, show_progress_bar=False, convert_to_numpy=True
            )

            n_clusters = len(results.content_clusters)
            if n_clusters < 2:
                logger.warning("Cannot generate visualization with fewer than 2 clusters")
                return

            kmeans = KMeans(
                n_clusters=n_clusters,
                random_state=self.config.thresholds.random_state,
                n_init=10,
            )
            labels = kmeans.fit_predict(embeddings)

            silhouette_map = {}
            for cluster in results.content_clusters:
                if cluster.silhouette_score is not None:
                    silhouette_map[cluster.cluster_id] = cluster.silhouette_score

            output_path = PathConfig.get_output_dir() / "cluster_visualization.png"
            generate_cluster_visualization(
                embeddings=embeddings,
                labels=labels,
                output_path=output_path,
                cluster_silhouette_scores=silhouette_map or None,
            )
        except ImportError as e:
            logger.warning(f"Could not generate visualization: {e}")
        except Exception as e:
            logger.warning(f"Visualization generation failed: {e}")


__all__ = ["AnalysisService"]
