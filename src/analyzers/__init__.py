"""
Analysis module orchestrator.

Per contracts/analyzer_contract.md lines 324-364, provides run_full_analysis()
that executes all 5 analyzer modules and combines results.
"""
from collections.abc import Callable
from typing import Optional

from src.analyzers.semantic_analyzer import SemanticAnalyzer
from src.analyzers.sender_analyzer import SenderAnalyzer
from src.analyzers.subject_analyzer import SubjectAnalyzer
from src.analyzers.temporal_analyzer import TemporalAnalyzer
from src.analyzers.volume_analyzer import VolumeAnalyzer
from src.models.analysis_results import AnalysisResults
from src.models.corpus import Corpus
from src.utils.logger import get_logger

logger = get_logger(__name__)


def run_full_analysis(
    corpus: Corpus,
    num_clusters: int = 10,
    progress_callback: Callable[[str, int, int], None] | None = None
) -> AnalysisResults:
    """
    Run all analyzers and combine results.

    Args:
        corpus: Complete email corpus
        num_clusters: Number of semantic clusters (default: 10)
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
    semantic_analyzer = SemanticAnalyzer()
    content_clusters = semantic_analyzer.analyze(
        corpus,
        num_clusters=num_clusters,
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


# Export all analyzers for direct access
__all__ = [
    'run_full_analysis',
    'SenderAnalyzer',
    'SubjectAnalyzer',
    'SemanticAnalyzer',
    'TemporalAnalyzer',
    'VolumeAnalyzer'
]
