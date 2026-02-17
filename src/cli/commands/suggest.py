"""Suggest command: generate category suggestions from analysis."""
import argparse
import time

from src.cli.formatters import output_json
from src.utils.file_manager import atomic_write_text, load_json, save_json
from src.utils.logger import get_logger
from src.utils.paths import PathConfig

logger = get_logger(__name__)


def build_suggest_parser(subparsers) -> argparse.ArgumentParser:
    """Add suggest subparser to the CLI and return it."""
    from pathlib import Path

    suggest_parser = subparsers.add_parser(
        "suggest",
        help="Generate category suggestions",
        description="Generate category suggestions from analysis results.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate suggestions with default settings
  %(prog)s

  # Require larger clusters for suggestions
  %(prog)s --min-cluster-percentage 10.0

  # Require more emails for sender-based categories
  %(prog)s --min-sender-count 50

  # Use custom analysis file
  %(prog)s --analysis /path/to/analysis.json

  # Preview without executing
  %(prog)s --dry-run
        """
    )
    suggest_parser.add_argument(
        "--analysis",
        type=Path,
        help="Path to analysis results JSON (default: {output-dir}/corpus_analysis_results.json)"
    )
    suggest_parser.add_argument(
        "--min-cluster-percentage",
        type=float,
        default=5.0,
        help="Minimum cluster size percentage for category generation (default: 5.0)"
    )
    suggest_parser.add_argument(
        "--min-sender-count",
        type=int,
        default=20,
        help="Minimum email count for sender-based categories (default: 20)"
    )
    suggest_parser.add_argument(
        "--suggestions-file",
        type=Path,
        help="Custom path for suggestions JSON (default: {output-dir}/category_suggestions.json)"
    )
    suggest_parser.add_argument(
        "-n", "--dry-run",
        action="store_true",
        help="Show what would be done without actually executing"
    )

    return suggest_parser


def cmd_suggest(args: argparse.Namespace) -> int:
    """
    Execute category suggestion command.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 = success, non-zero = error)
    """
    # Handle dry-run mode
    if getattr(args, 'dry_run', False):
        from src.preview.estimators import SuggestEstimator, format_suggest_preview

        estimator = SuggestEstimator()
        estimate = estimator.estimate(args)

        if getattr(args, 'json', False):
            output_json({
                "command": "suggest",
                "dry_run": True,
                "status": "preview",
                "analysis_path": str(estimate.analysis_path),
                "analysis_exists": estimate.analysis_exists,
                "output_path": str(estimate.output_path),
                "duration_estimate_seconds": estimate.duration_estimate_seconds,
            })
        else:
            print(format_suggest_preview(estimate))

        return 0

    from src.generators.category_generator import CategoryGenerator
    from src.models.analysis_results import AnalysisResults

    start_time = time.time()

    logger.info("=== CATEGORY SUGGESTION ===")

    # Determine analysis path
    analysis_path = args.analysis or PathConfig.get_analysis_path()

    logger.info(f"Analysis input: {analysis_path}")

    # Load analysis results
    try:
        analysis_data = load_json(analysis_path)
        results = AnalysisResults(**analysis_data)

    except FileNotFoundError:
        logger.error(
            f"Analysis results file not found: {analysis_path}. "
            f"Run 'analyze' first to generate analysis results, "
            f"or specify a valid path with --analysis."
        )
        if getattr(args, 'json', False):
            output_json({
                "command": "suggest",
                "status": "error",
                "error": f"Analysis results file not found: {analysis_path}"
            })
        return 1
    except Exception as e:
        logger.error(
            f"Failed to load analysis results from {analysis_path}: {e}. "
            f"The file may be corrupted. Try re-running 'analyze' to regenerate it."
        )
        if getattr(args, 'json', False):
            output_json({
                "command": "suggest",
                "status": "error",
                "error": str(e)
            })
        return 1

    # Determine suggestions output path
    suggestions_path = args.suggestions_file or PathConfig.get_suggestions_path()

    logger.info(f"Suggestions output: {suggestions_path}")

    # Generate suggestions
    try:
        generator = CategoryGenerator()
        categories = generator.generate_suggestions(
            analysis_results=results,
            min_cluster_percentage=args.min_cluster_percentage,
            min_sender_count=args.min_sender_count
        )

        # Save suggestions
        save_json(
            [cat.model_dump() for cat in categories],
            suggestions_path
        )

        # Generate markdown report (atomic write to prevent corruption)
        report_path = PathConfig.get_suggestions_report_path()
        report = generator.generate_report(categories)
        atomic_write_text(report_path, report)

        duration = time.time() - start_time

        if getattr(args, 'json', False):
            output_json({
                "command": "suggest",
                "status": "success",
                "duration_seconds": round(duration, 2),
                "output_file": str(suggestions_path),
                "stats": {
                    "categories_suggested": len(categories)
                }
            })
        else:
            logger.info(f"Generated {len(categories)} category suggestions")

        return 0

    except Exception as e:
        logger.error(
            f"Suggestion generation failed using analysis from {analysis_path}: {e}. "
            f"Output was targeted at {suggestions_path}. "
            f"Use --verbose for full traceback.",
            exc_info=True,
        )
        if getattr(args, 'json', False):
            output_json({
                "command": "suggest",
                "status": "error",
                "error": str(e)
            })
        return 1
