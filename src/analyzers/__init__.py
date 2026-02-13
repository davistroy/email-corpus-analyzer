"""
Analysis module orchestrator.

Per contracts/analyzer_contract.md lines 324-364, provides run_full_analysis()
that executes all 5 analyzer modules and combines results.

Supports optional embedding_cache parameter for incremental analysis mode.
Phase 7: Track 7A - Added BaseAnalyzer abstract base class for all analyzers.
Phase 8: Track 8A.1 - Added ThreadAnalyzer for email thread/conversation detection.
Task 2.2: Externalized magic numbers to AnalyzerThresholds config.
"""
from collections.abc import Callable
from typing import TYPE_CHECKING

from src.analyzers.base import AnalysisError, BaseAnalyzer
from src.analyzers.cluster_optimizer import (
    ClusterOptimizationResult,
    ElbowOptimizer,
    SilhouetteOptimizer,
    compute_max_k,
)
from src.analyzers.semantic_analyzer import SemanticAnalyzer
from src.analyzers.sender_analyzer import SenderAnalyzer
from src.analyzers.subject_analyzer import SubjectAnalyzer
from src.analyzers.temporal_analyzer import TemporalAnalyzer
from src.analyzers.thread_analyzer import ThreadAnalyzer
from src.analyzers.volume_analyzer import VolumeAnalyzer
from src.config.models import AnalyzerThresholds
from src.models.analysis_results import AnalysisResults
from src.models.corpus import Corpus
from src.utils.logger import get_logger

if TYPE_CHECKING:
    from src.cache.embedding_cache import EmbeddingCache

logger = get_logger(__name__)


def run_full_analysis(
    corpus: Corpus,
    num_clusters: int = 10,
    auto_clusters: bool = False,
    cluster_method: str = "silhouette",
    max_embedding_text_length: int = 1500,
    auto_cluster_min: int = 3,
    auto_cluster_max: int = 25,
    progress_callback: Callable[[str, int, int], None] | None = None,
    embedding_cache: "EmbeddingCache | None" = None,
    thresholds: AnalyzerThresholds | None = None,
) -> tuple[AnalysisResults, dict | None]:
    """
    Run all analyzers and combine results.

    When embedding_cache is provided, uses incremental semantic analysis with
    cached embeddings for faster repeated runs. Otherwise uses standard analysis.

    Args:
        corpus: Complete email corpus
        num_clusters: Number of semantic clusters (default: 10)
        auto_clusters: If True, automatically determine optimal k
        cluster_method: Method for auto-clustering: "elbow" or "silhouette"
        max_embedding_text_length: Max body chars for embedding text (default 1500)
        auto_cluster_min: Minimum max_k bound for auto-clustering (default 3)
        auto_cluster_max: Maximum max_k cap for auto-clustering (default 25)
        progress_callback: Optional callback(analyzer_name, current, total)
        embedding_cache: Optional EmbeddingCache for incremental analysis
        thresholds: Optional analyzer thresholds config. Uses defaults if None.

    Returns:
        Tuple of (AnalysisResults, incremental_stats dict or None).
        incremental_stats is None when embedding_cache is not provided.

    Raises:
        ValueError: If corpus is empty or invalid
    """
    if thresholds is None:
        thresholds = AnalyzerThresholds()

    incremental = embedding_cache is not None
    mode_label = "incremental" if incremental else "full"
    logger.info(f"Starting {mode_label} analysis of {len(corpus.emails)} emails")

    # Validate corpus
    if not corpus.emails:
        raise ValueError("Cannot analyze empty corpus")

    # FR-012: Sender analysis
    logger.info("Running sender analysis...")
    sender_analyzer = SenderAnalyzer(thresholds=thresholds)
    sender_analysis = sender_analyzer.analyze(
        corpus,
        progress_callback=lambda c, t: progress_callback("sender", c, t) if progress_callback else None
    )
    logger.debug(f"Sender analysis complete: {sender_analysis.unique_senders} unique senders")

    # FR-014: Subject analysis
    logger.info("Running subject analysis...")
    subject_analyzer = SubjectAnalyzer(thresholds=thresholds)
    subject_patterns = subject_analyzer.analyze(
        corpus,
        progress_callback=lambda c, t: progress_callback("subject", c, t) if progress_callback else None
    )
    logger.debug(f"Subject analysis complete: {subject_patterns.total_subjects_analyzed} subjects analyzed")

    # FR-015: Semantic analysis
    semantic_analyzer = SemanticAnalyzer(
        max_embedding_text_length=max_embedding_text_length,
        thresholds=thresholds,
    )
    incremental_stats = None

    if incremental:
        logger.info("Running incremental semantic analysis...")
        incremental_result = semantic_analyzer.analyze_incremental(
            corpus,
            embedding_cache=embedding_cache,
            num_clusters=num_clusters,
            auto_clusters=auto_clusters,
            cluster_method=cluster_method,
            auto_cluster_min=auto_cluster_min,
            auto_cluster_max=auto_cluster_max,
            progress_callback=lambda c, t: progress_callback("semantic", c, t) if progress_callback else None
        )
        content_clusters = incremental_result.clusters
        incremental_stats = incremental_result.stats
        logger.debug(f"Semantic analysis complete: {len(content_clusters)} clusters created")
        logger.info(
            f"Embedding stats: {incremental_stats['cached_count']} cached, "
            f"{incremental_stats['generated_count']} generated"
        )
    else:
        logger.info("Running semantic analysis...")
        content_clusters = semantic_analyzer.analyze(
            corpus,
            num_clusters=num_clusters,
            auto_clusters=auto_clusters,
            cluster_method=cluster_method,
            auto_cluster_min=auto_cluster_min,
            auto_cluster_max=auto_cluster_max,
            progress_callback=lambda c, t: progress_callback("semantic", c, t) if progress_callback else None
        )
        logger.debug(f"Semantic analysis complete: {len(content_clusters)} clusters created")

    # FR-018: Temporal analysis
    logger.info("Running temporal analysis...")
    temporal_analyzer = TemporalAnalyzer(thresholds=thresholds)
    temporal_patterns = temporal_analyzer.analyze(
        corpus,
        progress_callback=lambda c, t: progress_callback("temporal", c, t) if progress_callback else None
    )
    logger.debug(f"Temporal analysis complete: {len(temporal_patterns.frequency_distribution)} frequency types")

    # FR-019: Volume statistics
    logger.info("Running volume analysis...")
    volume_analyzer = VolumeAnalyzer()
    volume_stats = volume_analyzer.analyze(
        corpus,
        progress_callback=lambda c, t: progress_callback("volume", c, t) if progress_callback else None
    )
    logger.debug(f"Volume analysis complete: {volume_stats.total_emails} total emails")

    # Create results with all analysis components
    results = AnalysisResults(
        sender_analysis=sender_analysis,
        subject_patterns=subject_patterns,
        content_clusters=content_clusters,
        temporal_patterns=temporal_patterns,
        volume_stats=volume_stats
    )

    logger.info(f"{mode_label.capitalize()} analysis complete!")
    return results, incremental_stats


# Export all analyzers for direct access
__all__ = [
    'run_full_analysis',
    'BaseAnalyzer',
    'AnalysisError',
    'SenderAnalyzer',
    'SubjectAnalyzer',
    'SemanticAnalyzer',
    'TemporalAnalyzer',
    'VolumeAnalyzer',
    'ThreadAnalyzer',
    'ElbowOptimizer',
    'SilhouetteOptimizer',
    'ClusterOptimizationResult',
    'compute_max_k',
]
