"""Review command: interactive category review and approval."""

import argparse
import time

from src.cli.formatters import output_json
from src.utils.file_manager import load_json, save_json
from src.utils.logger import get_logger
from src.utils.paths import PathConfig

logger = get_logger(__name__)


def build_review_parser(subparsers) -> argparse.ArgumentParser:
    """Add review subparser to the CLI and return it."""
    from pathlib import Path

    review_parser = subparsers.add_parser(
        "review",
        help="Interactively review category suggestions",
        description="Interactively review, rename, merge, or delete category suggestions.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive TUI review (default)
  %(prog)s

  # Use legacy CLI interface
  %(prog)s --no-tui

  # Auto-approve all suggestions (for automation)
  %(prog)s --headless

  # Skip cleanup of intermediate files
  %(prog)s --no-cleanup

  # Disable learning from review decisions
  %(prog)s --no-learning

Note: --headless and --no-tui are mutually exclusive in practice.
      --headless bypasses all interactive review.
        """,
    )
    review_parser.add_argument(
        "--suggestions",
        type=Path,
        help="Path to suggestions JSON (default: {output-dir}/category_suggestions.json)",
    )
    review_parser.add_argument(
        "--approved-file",
        type=Path,
        help="Custom path for approved categories (default: {output-dir}/approved_categories.json)",
    )
    review_parser.add_argument(
        "--no-cleanup", action="store_true", help="Skip optional cleanup of intermediate files"
    )
    review_parser.add_argument(
        "-n",
        "--dry-run",
        action="store_true",
        help="Show what would be done without actually executing",
    )
    review_parser.add_argument(
        "--no-tui", action="store_true", help="Use legacy CLI interface instead of TUI"
    )
    review_parser.add_argument(
        "--headless",
        action="store_true",
        help="Auto-approve all suggestions without interactive review (for automation)",
    )
    review_parser.add_argument(
        "--no-learning",
        action="store_true",
        help="Disable feedback learning (don't log decisions or apply learned patterns)",
    )

    return review_parser


def cmd_review(args: argparse.Namespace) -> int:
    """
    Execute interactive category review command.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 = success, non-zero = error)
    """
    # Handle dry-run mode
    if getattr(args, "dry_run", False):
        from src.preview.estimators import ReviewEstimator, format_review_preview

        estimator = ReviewEstimator()
        estimate = estimator.estimate(args)

        if getattr(args, "json", False):
            output_json(
                {
                    "command": "review",
                    "dry_run": True,
                    "status": "preview",
                    "suggestions_path": str(estimate.suggestions_path),
                    "suggestions_exists": estimate.suggestions_exists,
                    "category_count": estimate.category_count,
                    "output_path": str(estimate.output_path),
                }
            )
        else:
            print(format_review_preview(estimate))

        return 0

    from src.models.category import Category
    from src.ui.category_review import (
        cleanup_intermediate_files,
        review_categories_with_ui,
    )

    start_time = time.time()

    # Handle headless mode (auto-approve all)
    if getattr(args, "headless", False):
        return auto_approve_categories(args)

    logger.info("=== CATEGORY REVIEW ===")

    # Determine suggestions path
    suggestions_path = args.suggestions or PathConfig.get_suggestions_path()

    logger.info(f"Suggestions input: {suggestions_path}")

    # Load suggestions
    try:
        suggestions_data = load_json(suggestions_path)
        categories = [Category(**cat) for cat in suggestions_data]

    except FileNotFoundError:
        logger.error(
            f"Suggestions file not found: {suggestions_path}. "
            f"Run 'suggest' first to generate category suggestions, "
            f"or specify a valid path with --suggestions."
        )
        if getattr(args, "json", False):
            output_json(
                {
                    "command": "review",
                    "status": "error",
                    "error": f"Suggestions file not found: {suggestions_path}",
                }
            )
        return 1
    except Exception as e:
        logger.error(
            f"Failed to load suggestions from {suggestions_path}: {e}. "
            f"The file may be corrupted. Try re-running 'suggest' to regenerate it."
        )
        if getattr(args, "json", False):
            output_json({"command": "review", "status": "error", "error": str(e)})
        return 1

    # Determine approved output path
    approved_path = args.approved_file or PathConfig.get_approved_categories_path()

    logger.info(f"Approved categories output: {approved_path}")

    # Determine whether to use TUI
    use_tui = not getattr(args, "no_tui", False)

    # Determine whether to use learning (Task 5B.3)
    enable_learning = not getattr(args, "no_learning", False)

    # Run interactive review
    try:
        approved = review_categories_with_ui(
            categories,
            output_path=approved_path,
            use_tui=use_tui,
            enable_learning=enable_learning,
        )

        duration = time.time() - start_time

        if getattr(args, "json", False):
            output_json(
                {
                    "command": "review",
                    "status": "success",
                    "duration_seconds": round(duration, 2),
                    "output_file": str(approved_path),
                    "stats": {
                        "categories_reviewed": len(categories),
                        "categories_approved": len(approved),
                    },
                }
            )
        else:
            logger.info(f"Approved {len(approved)} categories")

        # Optional cleanup
        if not args.no_cleanup:
            cleanup_intermediate_files(str(PathConfig.get_output_dir()))

        return 0

    except Exception as e:
        logger.error(
            f"Review failed for suggestions from {suggestions_path}: {e}. "
            f"Approved output was targeted at {approved_path}. "
            f"Use --verbose for full traceback.",
            exc_info=True,
        )
        if getattr(args, "json", False):
            output_json({"command": "review", "status": "error", "error": str(e)})
        return 1


def auto_approve_categories(args: argparse.Namespace) -> int:
    """
    Auto-approve all category suggestions without interactive review.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 = success, non-zero = error)
    """
    start_time = time.time()

    logger.info("=== AUTO-APPROVE CATEGORIES ===")

    # Determine suggestions path
    if hasattr(args, "suggestions") and args.suggestions:
        suggestions_path = args.suggestions
    else:
        suggestions_path = PathConfig.get_suggestions_path()

    # Determine approved output path
    if hasattr(args, "approved_file") and args.approved_file:
        approved_path = args.approved_file
    else:
        approved_path = PathConfig.get_approved_categories_path()

    logger.info(f"Auto-approving suggestions from: {suggestions_path}")
    logger.info(f"Saving to: {approved_path}")

    try:
        # Load suggestions
        suggestions_data = load_json(suggestions_path)

        # Save directly as approved (no changes)
        save_json(suggestions_data, approved_path)

        duration = time.time() - start_time

        if getattr(args, "json", False):
            output_json(
                {
                    "command": "auto_approve",
                    "status": "success",
                    "duration_seconds": round(duration, 2),
                    "output_file": str(approved_path),
                    "stats": {"categories_approved": len(suggestions_data)},
                }
            )
        else:
            logger.info(f"Auto-approved {len(suggestions_data)} categories")

        return 0

    except FileNotFoundError:
        logger.error(
            f"Suggestions file not found: {suggestions_path}. "
            f"Run 'suggest' first to generate category suggestions."
        )
        if getattr(args, "json", False):
            output_json(
                {
                    "command": "auto_approve",
                    "status": "error",
                    "error": f"Suggestions file not found: {suggestions_path}",
                }
            )
        return 1
    except Exception as e:
        logger.error(
            f"Auto-approve failed. Input: {suggestions_path}, Output: {approved_path}. "
            f"Error: {e}. Use --verbose for full traceback.",
            exc_info=True,
        )
        if getattr(args, "json", False):
            output_json({"command": "auto_approve", "status": "error", "error": str(e)})
        return 1
