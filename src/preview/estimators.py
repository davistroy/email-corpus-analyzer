"""
Estimators for dry-run mode previews.

Provides estimation classes for each CLI command that can calculate
expected behavior without actually executing operations.

Each estimator follows a consistent pattern:
1. Takes CLI args as input
2. Returns an Estimate dataclass with predictions
3. Can be formatted for human-readable output
"""
import argparse
from dataclasses import dataclass
from pathlib import Path

from src.utils.file_manager import load_json
from src.utils.paths import PathConfig

# =============================================================================
# Estimate Data Models
# =============================================================================


@dataclass
class ExtractEstimate:
    """Estimation results for extract command."""

    user_email: str
    output_path: Path
    email_count_estimate: int | None = None
    output_size_estimate: int | None = None  # bytes
    duration_estimate: float | None = None  # seconds


@dataclass
class AnalyzeEstimate:
    """Estimation results for analyze command."""

    corpus_path: Path
    corpus_exists: bool
    output_path: Path
    corpus_size_bytes: int | None = None
    email_count: int | None = None
    embedding_time_estimate_seconds: float | None = None
    clustering_time_estimate_seconds: float | None = None
    output_size_estimate_bytes: int | None = None


@dataclass
class SuggestEstimate:
    """Estimation results for suggest command."""

    analysis_path: Path
    analysis_exists: bool
    output_path: Path
    duration_estimate_seconds: float | None = None
    output_size_estimate_bytes: int | None = None


@dataclass
class ReviewEstimate:
    """Estimation results for review command."""

    suggestions_path: Path
    suggestions_exists: bool
    output_path: Path
    category_count: int | None = None


@dataclass
class PipelineEstimate:
    """Combined estimation for full pipeline."""

    extract: ExtractEstimate
    analyze: AnalyzeEstimate
    suggest: SuggestEstimate
    review: ReviewEstimate


# =============================================================================
# Estimator Classes
# =============================================================================


class ExtractEstimator:
    """Estimator for extract command dry-run."""

    # Time per email for extraction (seconds) - rough estimate
    TIME_PER_EMAIL_SECONDS = 0.05

    # Average email size in corpus (bytes)
    AVG_EMAIL_SIZE_BYTES = 8000

    def estimate(self, args: argparse.Namespace) -> ExtractEstimate:
        """
        Generate extraction estimate.

        Args:
            args: Parsed CLI arguments

        Returns:
            ExtractEstimate with predictions
        """
        # Determine output path
        if args.corpus_file:
            output_path = args.corpus_file
        else:
            output_path = PathConfig.get_corpus_path()

        return ExtractEstimate(
            user_email=args.user_email,
            output_path=output_path,
            # Cannot estimate without M365 connection
            email_count_estimate=None,
            output_size_estimate=None,
            duration_estimate=None,
        )


class AnalyzeEstimator:
    """Estimator for analyze command dry-run."""

    # Time per email for semantic embedding (seconds)
    TIME_PER_EMAIL_EMBEDDING_SECONDS = 0.1

    # Base clustering time (seconds)
    CLUSTERING_BASE_TIME_SECONDS = 5.0

    # Clustering time per 1000 emails (seconds)
    CLUSTERING_TIME_PER_1000_SECONDS = 2.0

    # Output size ratio (analysis results / corpus size)
    OUTPUT_SIZE_RATIO = 0.07

    def estimate(self, args: argparse.Namespace) -> AnalyzeEstimate:
        """
        Generate analysis estimate.

        Args:
            args: Parsed CLI arguments

        Returns:
            AnalyzeEstimate with predictions
        """
        # Determine paths
        if args.corpus:
            corpus_path = args.corpus
        else:
            corpus_path = PathConfig.get_corpus_path()

        if hasattr(args, "analysis_file") and args.analysis_file:
            output_path = args.analysis_file
        else:
            output_path = PathConfig.get_analysis_path()

        # Check if corpus exists
        corpus_exists = corpus_path.exists()

        if not corpus_exists:
            return AnalyzeEstimate(
                corpus_path=corpus_path,
                corpus_exists=False,
                output_path=output_path,
            )

        # Get corpus info
        try:
            corpus_size_bytes = corpus_path.stat().st_size
            corpus_data = load_json(corpus_path)
            email_count = len(corpus_data.get("emails", []))
        except Exception:
            return AnalyzeEstimate(
                corpus_path=corpus_path,
                corpus_exists=True,
                output_path=output_path,
            )

        # Calculate time estimates
        embedding_time = email_count * self.TIME_PER_EMAIL_EMBEDDING_SECONDS
        clustering_time = (
            self.CLUSTERING_BASE_TIME_SECONDS
            + (email_count / 1000) * self.CLUSTERING_TIME_PER_1000_SECONDS
        )

        # Estimate output size
        output_size = int(corpus_size_bytes * self.OUTPUT_SIZE_RATIO)

        return AnalyzeEstimate(
            corpus_path=corpus_path,
            corpus_exists=True,
            corpus_size_bytes=corpus_size_bytes,
            email_count=email_count,
            output_path=output_path,
            embedding_time_estimate_seconds=embedding_time,
            clustering_time_estimate_seconds=clustering_time,
            output_size_estimate_bytes=output_size,
        )


class SuggestEstimator:
    """Estimator for suggest command dry-run."""

    # Base suggestion generation time (seconds)
    BASE_DURATION_SECONDS = 3.0

    # Time per MB of analysis data (seconds)
    TIME_PER_MB_SECONDS = 1.0

    # Output size estimate (bytes)
    DEFAULT_OUTPUT_SIZE_BYTES = 100000

    def estimate(self, args: argparse.Namespace) -> SuggestEstimate:
        """
        Generate suggestion estimate.

        Args:
            args: Parsed CLI arguments

        Returns:
            SuggestEstimate with predictions
        """
        # Determine paths
        if args.analysis:
            analysis_path = args.analysis
        else:
            analysis_path = PathConfig.get_analysis_path()

        if hasattr(args, "suggestions_file") and args.suggestions_file:
            output_path = args.suggestions_file
        else:
            output_path = PathConfig.get_suggestions_path()

        # Check if analysis exists
        analysis_exists = analysis_path.exists()

        if not analysis_exists:
            return SuggestEstimate(
                analysis_path=analysis_path,
                analysis_exists=False,
                output_path=output_path,
            )

        # Get analysis info and calculate estimates
        try:
            analysis_size_bytes = analysis_path.stat().st_size
            analysis_size_mb = analysis_size_bytes / (1024 * 1024)
            duration = self.BASE_DURATION_SECONDS + analysis_size_mb * self.TIME_PER_MB_SECONDS
        except Exception:
            duration = self.BASE_DURATION_SECONDS

        return SuggestEstimate(
            analysis_path=analysis_path,
            analysis_exists=True,
            output_path=output_path,
            duration_estimate_seconds=duration,
            output_size_estimate_bytes=self.DEFAULT_OUTPUT_SIZE_BYTES,
        )


class ReviewEstimator:
    """Estimator for review command dry-run."""

    def estimate(self, args: argparse.Namespace) -> ReviewEstimate:
        """
        Generate review estimate.

        Args:
            args: Parsed CLI arguments

        Returns:
            ReviewEstimate with predictions
        """
        # Determine paths
        if args.suggestions:
            suggestions_path = args.suggestions
        else:
            suggestions_path = PathConfig.get_suggestions_path()

        if hasattr(args, "approved_file") and args.approved_file:
            output_path = args.approved_file
        else:
            output_path = PathConfig.get_approved_categories_path()

        # Check if suggestions exist
        suggestions_exists = suggestions_path.exists()

        if not suggestions_exists:
            return ReviewEstimate(
                suggestions_path=suggestions_path,
                suggestions_exists=False,
                output_path=output_path,
            )

        # Get category count
        try:
            suggestions_data = load_json(suggestions_path)
            category_count = len(suggestions_data)
        except Exception:
            category_count = None

        return ReviewEstimate(
            suggestions_path=suggestions_path,
            suggestions_exists=True,
            output_path=output_path,
            category_count=category_count,
        )


class PipelineEstimator:
    """Estimator for pipeline command dry-run."""

    def __init__(self):
        self.extract_estimator = ExtractEstimator()
        self.analyze_estimator = AnalyzeEstimator()
        self.suggest_estimator = SuggestEstimator()
        self.review_estimator = ReviewEstimator()

    def estimate(self, args: argparse.Namespace) -> PipelineEstimate:
        """
        Generate pipeline estimate.

        Args:
            args: Parsed CLI arguments

        Returns:
            PipelineEstimate with all stage predictions
        """
        # Create args for each stage
        extract_args = argparse.Namespace(
            user_email=args.user_email,
            corpus_file=None,
            batch_size=getattr(args, "batch_size", 500),
            checkpoint_interval=getattr(args, "checkpoint_interval", 100),
        )

        analyze_args = argparse.Namespace(
            corpus=None,
            num_clusters=args.num_clusters,
            analysis_file=None,
        )

        suggest_args = argparse.Namespace(
            analysis=None,
            min_cluster_percentage=getattr(args, "min_cluster_percentage", 5.0),
            min_sender_count=getattr(args, "min_sender_count", 20),
            suggestions_file=None,
        )

        review_args = argparse.Namespace(
            suggestions=None,
            approved_file=None,
            no_cleanup=args.no_cleanup,
        )

        return PipelineEstimate(
            extract=self.extract_estimator.estimate(extract_args),
            analyze=self.analyze_estimator.estimate(analyze_args),
            suggest=self.suggest_estimator.estimate(suggest_args),
            review=self.review_estimator.estimate(review_args),
        )


# =============================================================================
# Format Helper Functions
# =============================================================================


def format_bytes(size_bytes: int | None) -> str:
    """
    Format byte size to human-readable string.

    Args:
        size_bytes: Size in bytes, or None

    Returns:
        Human-readable size string
    """
    if size_bytes is None:
        return "N/A"

    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    if size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"


def format_duration(seconds: float | None) -> str:
    """
    Format duration to human-readable string.

    Args:
        seconds: Duration in seconds, or None

    Returns:
        Human-readable duration string
    """
    if seconds is None:
        return "depends on email count and network speed"

    if seconds < 60:
        return f"~{int(seconds)} seconds"
    if seconds < 3600:
        minutes = seconds / 60
        return f"~{int(minutes)} minutes"
    hours = seconds / 3600
    return f"~{hours:.1f} hours"


def format_count(count: int | None) -> str:
    """
    Format count to human-readable string.

    Args:
        count: Count value, or None

    Returns:
        Formatted count string
    """
    if count is None:
        return "unknown"
    return f"{count:,}"


# =============================================================================
# Preview Formatters
# =============================================================================


def format_extract_preview(estimate: ExtractEstimate) -> str:
    """
    Format extract estimate as preview output.

    Args:
        estimate: ExtractEstimate to format

    Returns:
        Formatted preview string
    """
    lines = [
        "[DRY RUN] extract",
        "-" * 40,
        f"Input:  {estimate.user_email}",
        f"Output: {estimate.output_path}",
        "",
        "Estimated:",
        f"  - Emails to fetch: {format_count(estimate.email_count_estimate)}",
        f"  - Output file size: {format_bytes(estimate.output_size_estimate)}",
        f"  - Duration: {format_duration(estimate.duration_estimate)}",
        "",
        "No changes will be made.",
    ]
    return "\n".join(lines)


def format_analyze_preview(estimate: AnalyzeEstimate) -> str:
    """
    Format analyze estimate as preview output.

    Args:
        estimate: AnalyzeEstimate to format

    Returns:
        Formatted preview string
    """
    lines = [
        "[DRY RUN] analyze",
        "-" * 40,
    ]

    if not estimate.corpus_exists:
        lines.extend([
            f"Input:  {estimate.corpus_path}",
            "        (file does not exist)",
            f"Output: {estimate.output_path}",
            "",
            "WARNING: Corpus file not found. Run 'extract' first.",
        ])
    else:
        corpus_info = f"{estimate.corpus_path}"
        if estimate.corpus_size_bytes and estimate.email_count:
            corpus_info += f" ({format_bytes(estimate.corpus_size_bytes)}, {format_count(estimate.email_count)} emails)"

        lines.extend([
            f"Input:  {corpus_info}",
            f"Output: {estimate.output_path}",
            "",
            "Estimated:",
        ])

        if estimate.email_count and estimate.embedding_time_estimate_seconds:
            lines.append(
                f"  - Semantic embeddings: ~{format_count(estimate.email_count)} emails "
                f"x ~0.1s = {format_duration(estimate.embedding_time_estimate_seconds)}"
            )

        if estimate.clustering_time_estimate_seconds:
            lines.append(
                f"  - Clustering: {format_duration(estimate.clustering_time_estimate_seconds)}"
            )

        if estimate.output_size_estimate_bytes:
            lines.append(
                f"  - Output file size: ~{format_bytes(estimate.output_size_estimate_bytes)}"
            )

    lines.extend(["", "No changes will be made."])
    return "\n".join(lines)


def format_suggest_preview(estimate: SuggestEstimate) -> str:
    """
    Format suggest estimate as preview output.

    Args:
        estimate: SuggestEstimate to format

    Returns:
        Formatted preview string
    """
    lines = [
        "[DRY RUN] suggest",
        "-" * 40,
        f"Input:  {estimate.analysis_path}",
    ]

    if not estimate.analysis_exists:
        lines.extend([
            "        (file does not exist)",
            f"Output: {estimate.output_path}",
            "",
            "WARNING: Analysis file not found. Run 'analyze' first.",
        ])
    else:
        lines.extend([
            f"Output: {estimate.output_path}",
            "",
            "Estimated:",
            f"  - Duration: {format_duration(estimate.duration_estimate_seconds)}",
            f"  - Output file size: ~{format_bytes(estimate.output_size_estimate_bytes)}",
        ])

    lines.extend(["", "No changes will be made."])
    return "\n".join(lines)


def format_review_preview(estimate: ReviewEstimate) -> str:
    """
    Format review estimate as preview output.

    Args:
        estimate: ReviewEstimate to format

    Returns:
        Formatted preview string
    """
    lines = [
        "[DRY RUN] review",
        "-" * 40,
        f"Input:  {estimate.suggestions_path}",
    ]

    if not estimate.suggestions_exists:
        lines.extend([
            "        (file does not exist)",
            f"Output: {estimate.output_path}",
            "",
            "WARNING: Suggestions file not found. Run 'suggest' first.",
        ])
    else:
        lines.extend([
            f"Output: {estimate.output_path} (approved categories)",
            "",
            "Info:",
            f"  - Categories to review: {format_count(estimate.category_count)}",
            "",
            "Interactive review will be required.",
        ])

    lines.extend(["", "No changes will be made."])
    return "\n".join(lines)


def format_pipeline_preview(estimate: PipelineEstimate) -> str:
    """
    Format pipeline estimate as preview output.

    Args:
        estimate: PipelineEstimate to format

    Returns:
        Formatted preview string
    """
    lines = [
        "[DRY RUN] pipeline",
        "=" * 50,
        "",
        "Step 1: Extract",
        f"  User: {estimate.extract.user_email}",
        f"  Output: {estimate.extract.output_path}",
        "",
        "Step 2: Analyze",
        f"  Input: {estimate.analyze.corpus_path}",
    ]

    if estimate.analyze.corpus_exists:
        lines.append(f"  Corpus: {format_count(estimate.analyze.email_count)} emails")
    else:
        lines.append("  (corpus will be created in Step 1)")

    lines.extend([
        f"  Output: {estimate.analyze.output_path}",
        "",
        "Step 3: Suggest",
        f"  Input: {estimate.suggest.analysis_path}",
        f"  Output: {estimate.suggest.output_path}",
        "",
        "Step 4: Review",
        f"  Input: {estimate.review.suggestions_path}",
        f"  Output: {estimate.review.output_path}",
        "",
        "=" * 50,
        "No changes will be made.",
    ])

    return "\n".join(lines)
