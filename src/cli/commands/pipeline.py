"""Pipeline command: run complete end-to-end workflow."""
import argparse
import time

from src.cli.commands.analyze import cmd_analyze
from src.cli.commands.extract import cmd_extract
from src.cli.commands.review import auto_approve_categories, cmd_review
from src.cli.commands.suggest import cmd_suggest
from src.cli.formatters import output_json
from src.utils.logger import get_logger

logger = get_logger(__name__)


def build_pipeline_parser(subparsers) -> None:
    """Add pipeline subparser to the CLI."""
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
        """
    )
    pipeline_parser.add_argument(
        "--user-email",
        required=True,
        help="Primary email address (Hotmail/Outlook or Gmail)"
    )
    pipeline_parser.add_argument(
        "--source",
        type=str,
        choices=["hotmail", "gmail", "both"],
        default="hotmail",
        help="Email source: hotmail, gmail, or both (default: hotmail)"
    )
    pipeline_parser.add_argument(
        "--gmail-email",
        type=str,
        help="Gmail address (required when --source both, if different from --user-email)"
    )
    pipeline_parser.add_argument(
        "--num-clusters",
        type=int,
        default=10,
        help="Number of semantic clusters (default: 10)"
    )
    pipeline_parser.add_argument(
        "--auto-clusters",
        action="store_true",
        default=False,
        help="Automatically determine optimal number of clusters"
    )
    pipeline_parser.add_argument(
        "--cluster-method",
        type=str,
        choices=["elbow", "silhouette"],
        default="silhouette",
        help="Method to determine optimal clusters: elbow or silhouette (default: silhouette)"
    )
    pipeline_parser.add_argument(
        "--no-cleanup",
        action="store_true",
        help="Skip optional cleanup of intermediate files"
    )
    pipeline_parser.add_argument(
        "--skip-review",
        action="store_true",
        help="Skip interactive review and auto-accept all suggestions"
    )
    pipeline_parser.add_argument(
        "-n", "--dry-run",
        action="store_true",
        help="Show what would be done without actually executing"
    )
    pipeline_parser.add_argument(
        "--no-tui",
        action="store_true",
        help="Use legacy CLI interface instead of TUI for review step"
    )
    pipeline_parser.add_argument(
        "--no-learning",
        action="store_true",
        help="Disable feedback learning (don't log decisions or apply learned patterns)"
    )


def cmd_pipeline(args: argparse.Namespace) -> int:
    """
    Execute complete pipeline command.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 = success, non-zero = error)
    """
    from src.cli.parsers import validate_email_format

    # Validate email format first (even for dry-run)
    if not validate_email_format(args.user_email):
        logger.error(f"Invalid email format: {args.user_email}")
        if getattr(args, 'json', False):
            output_json({
                "command": "pipeline",
                "status": "error",
                "error": f"Invalid email format: {args.user_email}"
            })
        return 1

    # Handle dry-run mode
    if getattr(args, 'dry_run', False):
        from src.preview.estimators import PipelineEstimator, format_pipeline_preview

        estimator = PipelineEstimator()
        estimate = estimator.estimate(args)

        if getattr(args, 'json', False):
            output_json({
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
            })
        else:
            print(format_pipeline_preview(estimate))

        return 0

    start_time = time.time()

    logger.info("=== COMPLETE PIPELINE ===")

    # Step 1: Extract
    logger.info("Step 1/4: Extracting emails...")
    extract_args = argparse.Namespace(
        user_email=args.user_email,
        source=getattr(args, 'source', 'hotmail'),
        gmail_email=getattr(args, 'gmail_email', None),
        corpus_file=None,
        batch_size=500,
        checkpoint_interval=100,
        since_last=False,
        dry_run=False,
        output_dir=args.output_dir,
        verbose=getattr(args, 'verbose', False),
        quiet=getattr(args, 'quiet', False),
        json=getattr(args, 'json', False)
    )
    if cmd_extract(extract_args) != 0:
        return 1

    # Step 2: Analyze
    logger.info("Step 2/4: Analyzing corpus...")
    analyze_args = argparse.Namespace(
        corpus=None,
        num_clusters=args.num_clusters,
        analysis_file=None,
        output_dir=args.output_dir,
        verbose=getattr(args, 'verbose', False),
        quiet=getattr(args, 'quiet', False),
        json=getattr(args, 'json', False)
    )
    if cmd_analyze(analyze_args) != 0:
        return 1

    # Step 3: Suggest
    logger.info("Step 3/4: Generating suggestions...")
    suggest_args = argparse.Namespace(
        analysis=None,
        min_cluster_percentage=5.0,
        min_sender_count=20,
        suggestions_file=None,
        output_dir=args.output_dir,
        verbose=getattr(args, 'verbose', False),
        quiet=getattr(args, 'quiet', False),
        json=getattr(args, 'json', False)
    )
    if cmd_suggest(suggest_args) != 0:
        return 1

    # Step 4: Review or Auto-approve
    if getattr(args, 'skip_review', False):
        logger.info("Step 4/4: Auto-approving suggestions (--skip-review)...")
        review_args = argparse.Namespace(
            suggestions=None,
            approved_file=None,
            no_cleanup=args.no_cleanup,
            output_dir=args.output_dir,
            verbose=getattr(args, 'verbose', False),
            quiet=getattr(args, 'quiet', False),
            json=getattr(args, 'json', False)
        )
        if auto_approve_categories(review_args) != 0:
            return 1
    else:
        logger.info("Step 4/4: Interactive review...")
        review_args = argparse.Namespace(
            suggestions=None,
            approved_file=None,
            no_cleanup=args.no_cleanup,
            no_tui=getattr(args, 'no_tui', False),
            no_learning=getattr(args, 'no_learning', False),
            output_dir=args.output_dir,
            verbose=getattr(args, 'verbose', False),
            quiet=getattr(args, 'quiet', False),
            json=getattr(args, 'json', False)
        )
        if cmd_review(review_args) != 0:
            return 1

    duration = time.time() - start_time

    if getattr(args, 'json', False):
        output_json({
            "command": "pipeline",
            "status": "success",
            "duration_seconds": round(duration, 2)
        })
    else:
        logger.info("Pipeline complete!")

    return 0
