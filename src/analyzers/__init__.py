"""
Analysis module orchestrator.

Per contracts/analyzer_contract.md lines 324-364, provides run_full_analysis()
that executes all 5 analyzer modules and combines results.

Task 4B.4: Enhanced with run_full_analysis_incremental for embedding cache support.
Phase 7: Track 7A - Added BaseAnalyzer abstract base class for all analyzers.
Phase 8: Track 8A.1 - Added ThreadAnalyzer for email thread/conversation detection.
"""
from collections.abc import Callable
from typing import TYPE_CHECKING

from src.analyzers.base import AnalysisError, BaseAnalyzer
from src.analyzers.cluster_optimizer import (
    ClusterOptimizationResult,
    ElbowOptimizer,
    SilhouetteOptimizer,
)
from src.analyzers.semantic_analyzer import SemanticAnalyzer
from src.analyzers.sender_analyzer import SenderAnalyzer
from src.analyzers.subject_analyzer import SubjectAnalyzer
from src.analyzers.temporal_analyzer import TemporalAnalyzer
from src.analyzers.thread_analyzer import ThreadAnalyzer
from src.analyzers.volume_analyzer import VolumeAnalyzer
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
    progress_callback: Callable[[str, int, int], None] | None = None
) -> AnalysisResults:
    """
    Run all analyzers and combine results.

    Args:
        corpus: Complete email corpus
        num_clusters: Number of semantic clusters (default: 10)
        auto_clusters: If True, automatically determine optimal k
        cluster_method: Method for auto-clustering: "elbow" or "silhouette"
        max_embedding_text_length: Max body chars for embedding text (default 1500)
        progress_callback: Optional callback(analyzer_name, current, total)

    Returns:
        AnalysisResults with all analysis components

    Raises:
        ValueError: If corpus is empty or invalid
    """
    logger.info(f"Starting full analysis of {len(corpus.emails)} emails")

    # Validate corpus
    if not corpus.emails:
        raise ValueError("Cannot analyze empty corpus")

    # FR-012: Sender analysis
    logger.info("Running sender analysis...")
    sender_analyzer = SenderAnalyzer()
    sender_analysis = sender_analyzer.analyze(
        corpus,
        progress_callback=lambda c, t: progress_callback("sender", c, t) if progress_callback else None
    )
    logger.debug(f"Sender analysis complete: {sender_analysis.unique_senders} unique senders")

    # FR-014: Subject analysis
    logger.info("Running subject analysis...")
    subject_analyzer = SubjectAnalyzer()
    subject_patterns = subject_analyzer.analyze(
        corpus,
        progress_callback=lambda c, t: progress_callback("subject", c, t) if progress_callback else None
    )
    logger.debug(f"Subject analysis complete: {subject_patterns.total_subjects_analyzed} subjects analyzed")

    # FR-015: Semantic analysis
    logger.info("Running semantic analysis...")
    semantic_analyzer = SemanticAnalyzer(
        max_embedding_text_length=max_embedding_text_length,
    )
    content_clusters = semantic_analyzer.analyze(
        corpus,
        num_clusters=num_clusters,
        auto_clusters=auto_clusters,
        cluster_method=cluster_method,
        progress_callback=lambda c, t: progress_callback("semantic", c, t) if progress_callback else None
    )
    logger.debug(f"Semantic analysis complete: {len(content_clusters)} clusters created")

    # FR-018: Temporal analysis
    logger.info("Running temporal analysis...")
    temporal_analyzer = TemporalAnalyzer()
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

    logger.info("Full analysis complete!")
    return results


def run_full_analysis_incremental(
    corpus: Corpus,
    embedding_cache: "EmbeddingCache",
    num_clusters: int = 10,
    auto_clusters: bool = False,
    cluster_method: str = "silhouette",
    max_embedding_text_length: int = 1500,
    progress_callback: Callable[[str, int, int], None] | None = None
) -> tuple[AnalysisResults, dict]:
    """
    Run all analyzers with incremental embedding support (Task 4B.4).

    Uses cached embeddings for semantic analysis to speed up repeated runs.

    Args:
        corpus: Complete email corpus
        embedding_cache: EmbeddingCache instance for caching embeddings
        num_clusters: Number of semantic clusters (default: 10)
        auto_clusters: If True, automatically determine optimal k
        cluster_method: Method for auto-clustering: "elbow" or "silhouette"
        max_embedding_text_length: Max body chars for embedding text (default 1500)
        progress_callback: Optional callback(analyzer_name, current, total)

    Returns:
        Tuple of (AnalysisResults, incremental_stats dict)

    Raises:
        ValueError: If corpus is empty or invalid
    """
    logger.info(f"Starting incremental analysis of {len(corpus.emails)} emails")

    # Validate corpus
    if not corpus.emails:
        raise ValueError("Cannot analyze empty corpus")

    # FR-012: Sender analysis
    logger.info("Running sender analysis...")
    sender_analyzer = SenderAnalyzer()
    sender_analysis = sender_analyzer.analyze(
        corpus,
        progress_callback=lambda c, t: progress_callback("sender", c, t) if progress_callback else None
    )
    logger.debug(f"Sender analysis complete: {sender_analysis.unique_senders} unique senders")

    # FR-014: Subject analysis
    logger.info("Running subject analysis...")
    subject_analyzer = SubjectAnalyzer()
    subject_patterns = subject_analyzer.analyze(
        corpus,
        progress_callback=lambda c, t: progress_callback("subject", c, t) if progress_callback else None
    )
    logger.debug(f"Subject analysis complete: {subject_patterns.total_subjects_analyzed} subjects analyzed")

    # FR-015: Semantic analysis (INCREMENTAL)
    logger.info("Running incremental semantic analysis...")
    semantic_analyzer = SemanticAnalyzer(
        max_embedding_text_length=max_embedding_text_length,
    )
    incremental_result = semantic_analyzer.analyze_incremental(
        corpus,
        embedding_cache=embedding_cache,
        num_clusters=num_clusters,
        auto_clusters=auto_clusters,
        cluster_method=cluster_method,
        progress_callback=lambda c, t: progress_callback("semantic", c, t) if progress_callback else None
    )
    content_clusters = incremental_result.clusters
    incremental_stats = incremental_result.stats
    logger.debug(f"Semantic analysis complete: {len(content_clusters)} clusters created")
    logger.info(
        f"Embedding stats: {incremental_stats['cached_count']} cached, "
        f"{incremental_stats['generated_count']} generated"
    )

    # FR-018: Temporal analysis
    logger.info("Running temporal analysis...")
    temporal_analyzer = TemporalAnalyzer()
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

    logger.info("Incremental analysis complete!")
    return results, incremental_stats


# Export all analyzers for direct access
__all__ = [
    'run_full_analysis',
    'run_full_analysis_incremental',
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
]
