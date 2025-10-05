"""
Analysis module orchestrator.

Per contracts/analyzer_contract.md lines 324-364, provides run_full_analysis()
that executes all 5 analyzer modules and combines results.
"""
from typing import Callable, Optional

from src.models.corpus import Corpus
from src.models.analysis_results import AnalysisResults
from src.analyzers.sender_analyzer import SenderAnalyzer
from src.analyzers.subject_analyzer import SubjectAnalyzer
from src.analyzers.semantic_analyzer import SemanticAnalyzer
from src.analyzers.temporal_analyzer import TemporalAnalyzer
from src.analyzers.volume_analyzer import VolumeAnalyzer
from src.utils.logger import get_logger

logger = get_logger(__name__)


def run_full_analysis(
    corpus: Corpus,
    num_clusters: int = 10,
    progress_callback: Optional[Callable[[str, int, int], None]] = None
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

    results = AnalysisResults(
        sender_analysis=None,  # Will be populated
        subject_patterns=None,
        content_clusters=[],
        temporal_patterns=None,
        volume_stats=None
    )

    # FR-012: Sender analysis
    logger.info("Running sender analysis...")
    sender_analyzer = SenderAnalyzer()
    results.sender_analysis = sender_analyzer.analyze(
        corpus,
        progress_callback=lambda c, t: progress_callback("sender", c, t) if progress_callback else None
    )
    logger.debug(f"Sender analysis complete: {results.sender_analysis.unique_senders} unique senders")

    # FR-014: Subject analysis
    logger.info("Running subject analysis...")
    subject_analyzer = SubjectAnalyzer()
    results.subject_patterns = subject_analyzer.analyze(
        corpus,
        progress_callback=lambda c, t: progress_callback("subject", c, t) if progress_callback else None
    )
    logger.debug(f"Subject analysis complete: {results.subject_patterns.total_subjects_analyzed} subjects analyzed")

    # FR-015: Semantic analysis
    logger.info("Running semantic analysis...")
    semantic_analyzer = SemanticAnalyzer()
    results.content_clusters = semantic_analyzer.analyze(
        corpus,
        num_clusters=num_clusters,
        progress_callback=lambda c, t: progress_callback("semantic", c, t) if progress_callback else None
    )
    logger.debug(f"Semantic analysis complete: {len(results.content_clusters)} clusters created")

    # FR-018: Temporal analysis
    logger.info("Running temporal analysis...")
    temporal_analyzer = TemporalAnalyzer()
    results.temporal_patterns = temporal_analyzer.analyze(
        corpus,
        progress_callback=lambda c, t: progress_callback("temporal", c, t) if progress_callback else None
    )
    logger.debug(f"Temporal analysis complete: {len(results.temporal_patterns.frequency_distribution)} frequency types")

    # FR-019: Volume statistics
    logger.info("Running volume analysis...")
    volume_analyzer = VolumeAnalyzer()
    results.volume_stats = volume_analyzer.analyze(
        corpus,
        progress_callback=lambda c, t: progress_callback("volume", c, t) if progress_callback else None
    )
    logger.debug(f"Volume analysis complete: {results.volume_stats.total_emails} total emails")

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
