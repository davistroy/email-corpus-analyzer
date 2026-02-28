"""Pipeline command: run complete end-to-end workflow."""

import argparse
import time

from src.cli.commands.review import auto_approve_categories, cmd_review
from src.cli.formatters import output_json
from src.config.models import (
    AnalyzeConfig,
    AppConfig,
    ExtractConfig,
    SuggestConfig,
)
from src.services.pipeline_service import PipelineService
from src.utils.logger import get_logger

logger = get_logger(__name__)


def build_pipeline_parser(subparsers) -> argparse.ArgumentParser:
    """Add pipeline subparser to the CLI and return it."""
    pipeline_parser = subparsers.add_parser(
        "pipeline",
        help="Run complete end-to-end workflow",
        description="Run extract -> analyze -> suggest -> review -> optional cleanup.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run complete pipeline with TUI review
  %(prog)s --user-email user@hotmail.com

  # Run pipeline to custom directory
  %(prog)s --user-email user@hotmail.com --output-dir ~/my-analysis

  # Skip interactive review (auto-approve all)
  %(prog)s --user-email user@hotmail.com --skip-review

  # Use auto-clustering
  %(prog)s --user-email user@hotmail.com --auto-clusters

  # Preview all stages without executing
  %(prog)s --user-email user@hotmail.com --dry-run

The pipeline runs these stages in order:
  1. extract  - Fetch emails from M365
  2. analyze  - Run all analyzers
  3. suggest  - Generate categories
  4. review   - Interactive approval
        """,
    )
    pipeline_parser.add_argument(
        "--user-email", required=True, help="Primary email address (Hotmail/Outlook or Gmail)"
    )
    pipeline_parser.add_argument(
        "--source",
        type=str,
        choices=["hotmail", "gmail", "both"],
        default="hotmail",
        help="Email source: hotmail, gmail, or both (default: hotmail)",
    )
    pipeline_parser.add_argument(
        "--gmail-email",
        type=str,
        help="Gmail address (required when --source both, if different from --user-email)",
    )
    pipeline_parser.add_argument(
        "--num-clusters", type=int, default=10, help="Number of semantic clusters (default: 10)"
    )
    pipeline_parser.add_argument(
        "--auto-clusters",
        action="store_true",
        default=False,
        help="Automatically determine optimal number of clusters",
    )
    pipeline_parser.add_argument(
        "--cluster-method",
        type=str,
        choices=["elbow", "silhouette"],
        default="silhouette",
        help="Method to determine optimal clusters: elbow or silhouette (default: silhouette)",
    )
    pipeline_parser.add_argument(
        "--cluster-viz",
        action="store_true",
        default=False,
        help="Generate cluster visualization PNG during analysis (requires matplotlib)",
    )
    pipeline_parser.add_argument(
        "--incremental",
        action="store_true",
        default=False,
        help="Use embedding cache for incremental analysis",
    )
    pipeline_parser.add_argument(
        "--min-cluster-percentage",
        type=float,
        default=5.0,
        help="Minimum cluster size percentage for category generation (default: 5.0)",
    )
    pipeline_parser.add_argument(
        "--min-sender-count",
        type=int,
        default=20,
        help="Minimum email count for sender-based categories (default: 20)",
    )
    pipeline_parser.add_argument(
        "--no-cleanup", action="store_true", help="Skip optional cleanup of intermediate files"
    )
    pipeline_parser.add_argument(
        "--skip-review",
        action="store_true",
        help="Skip interactive review and auto-accept all suggestions",
    )
    pipeline_parser.add_argument(
        "-n",
        "--dry-run",
        action="store_true",
        help="Show what would be done without actually executing",
    )
    pipeline_parser.add_argument(
        "--no-tui",
        action="store_true",
        help="Use legacy CLI interface instead of TUI for review step",
    )
    pipeline_parser.add_argument(
        "--no-learning",
        action="store_true",
        help="Disable feedback learning (don't log decisions or apply learned patterns)",
    )

    return pipeline_parser  # type: ignore[no-any-return]


def _build_app_config(args: argparse.Namespace) -> AppConfig:
    """
    Build an AppConfig from parsed pipeline CLI arguments.

    Maps pipeline CLI argument names to the appropriate nested config
    fields (ExtractConfig, AnalyzeConfig, SuggestConfig).

    Args:
        args: Parsed command-line arguments

    Returns:
        AppConfig with values from CLI args
    """
    source = getattr(args, "source", "hotmail")
    gmail_email = getattr(args, "gmail_email", None)

    # Build extract config - only set gmail_email if source requires it
    if source in ("gmail", "both"):
        extract_config = ExtractConfig(source=source, gmail_email=gmail_email or args.user_email)
    else:
        extract_config = ExtractConfig(source=source)

    analyze_config = AnalyzeConfig(
        num_clusters=args.num_clusters,
    )

    suggest_config = SuggestConfig(
        min_cluster_percentage=getattr(args, "min_cluster_percentage", 5.0),
        min_sender_count=getattr(args, "min_sender_count", 20),
    )

    return AppConfig(
        user_email=args.user_email,
        output_dir=args.output_dir,
        extract=extract_config,
        analyze=analyze_config,
        suggest=suggest_config,
    )


def cmd_pipeline(args: argparse.Namespace) -> int:
    """
    Execute complete pipeline command.

    Routes extract -> analyze -> suggest through PipelineService.
    The review step remains in the CLI layer since it is UI-specific.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 = success, non-zero = error)
    """
    from pathlib import Path

    from src.cli.parsers import validate_email_format

    # Validate email format first (even for dry-run)
    if not validate_email_format(args.user_email):
        logger.error(f"Invalid email format: {args.user_email}")
        if getattr(args, "json", False):
            output_json(
                {
                    "command": "pipeline",
                    "status": "error",
                    "error": f"Invalid email format: {args.user_email}",
                }
            )
        return 1

    # Handle dry-run mode
    if getattr(args, "dry_run", False):
        from src.preview.estimators import PipelineEstimator, format_pipeline_preview

        estimator = PipelineEstimator()
        estimate = estimator.estimate(args)

        if getattr(args, "json", False):
            output_json(
                {
                    "command": "pipeline",
                    "dry_run": True,
                    "status": "preview",
                    "stages": {
                        "extract": {
                            "user_email": estimate.extract.user_email,
                            "output_path": str(estimate.extract.output_path),
                        },
                        "analyze": {
                            "corpus_path": str(estimate.analyze.corpus_path),
                            "output_path": str(estimate.analyze.output_path),
                        },
                        "suggest": {
                            "analysis_path": str(estimate.suggest.analysis_path),
                            "output_path": str(estimate.suggest.output_path),
                        },
                        "review": {
                            "suggestions_path": str(estimate.review.suggestions_path),
                            "output_path": str(estimate.review.output_path),
                        },
                    },
                }
            )
        else:
            print(format_pipeline_preview(estimate))

        return 0

    start_time = time.time()

    logger.info("=== COMPLETE PIPELINE ===")

    # Build config and service
    config = _build_app_config(args)
    service = PipelineService(config)

    # Determine output directory
    output_dir = Path(args.output_dir) if args.output_dir else Path.home() / "data" / "outputs"

    # Run extract -> analyze -> suggest through PipelineService
    try:

        def progress_callback(message: str) -> None:
            logger.info(message)

        _pipeline_result = service.run(  # noqa: F841 - result available for future review-step integration
            output_dir=output_dir,
            progress_callback=progress_callback,
            auto_clusters=getattr(args, "auto_clusters", False),
            cluster_method=getattr(args, "cluster_method", "silhouette"),
            cluster_viz=getattr(args, "cluster_viz", False),
        )
    except Exception as e:
        logger.error(
            f"Pipeline failed during extract/analyze/suggest stages: {e}. "
            f"Output directory: {output_dir}. "
            f"You can re-run individual stages to isolate the failure. "
            f"Use --verbose for full traceback.",
            exc_info=True,
        )
        if getattr(args, "json", False):
            output_json({"command": "pipeline", "status": "error", "error": str(e)})
        return 1

    # Step 4: Review (stays in CLI layer - UI-specific)
    if getattr(args, "skip_review", False):
        logger.info("Step 4/4: Auto-approving suggestions (--skip-review)...")
        review_args = argparse.Namespace(
            suggestions=None,
            approved_file=None,
            no_cleanup=args.no_cleanup,
            output_dir=args.output_dir,
            verbose=getattr(args, "verbose", False),
            quiet=getattr(args, "quiet", False),
            json=getattr(args, "json", False),
        )
        if auto_approve_categories(review_args) != 0:
            return 1
    else:
        logger.info("Step 4/4: Interactive review...")
        review_args = argparse.Namespace(
            suggestions=None,
            approved_file=None,
            no_cleanup=args.no_cleanup,
            no_tui=getattr(args, "no_tui", False),
            no_learning=getattr(args, "no_learning", False),
            output_dir=args.output_dir,
            verbose=getattr(args, "verbose", False),
            quiet=getattr(args, "quiet", False),
            json=getattr(args, "json", False),
        )
        if cmd_review(review_args) != 0:
            return 1

    duration = time.time() - start_time

    if getattr(args, "json", False):
        output_json(
            {"command": "pipeline", "status": "success", "duration_seconds": round(duration, 2)}
        )
    else:
        logger.info("Pipeline complete!")

    return 0
