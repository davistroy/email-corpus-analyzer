#!/usr/bin/env python3
"""
Email Corpus Extraction and Analysis System - CLI Entry Point.

Commands:
  extract   - Extract emails from M365/Hotmail
  analyze   - Analyze email corpus for patterns
  suggest   - Generate category suggestions
  review    - Interactively review and approve categories
  pipeline  - Run complete end-to-end workflow

All commands support --output-dir to specify custom output location.
Default output directory: ~/data/outputs
"""
import argparse
import logging
import sys
from pathlib import Path

from src.utils.file_manager import load_json, save_json
from src.utils.logger import get_logger
from src.utils.paths import PathConfig

logger = get_logger(__name__)


def create_parser() -> argparse.ArgumentParser:
    """
    Create CLI argument parser with all commands and options.

    Returns:
        Configured ArgumentParser
    """
    parser = argparse.ArgumentParser(
        prog="email-processor",
        description="Email Corpus Extraction and Analysis System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Extract emails to default location (~/data/outputs)
  %(prog)s extract --user-email user@hotmail.com

  # Extract to custom directory
  %(prog)s extract --user-email user@hotmail.com --output-dir ~/my-emails

  # Analyze existing corpus
  %(prog)s analyze --corpus ~/my-emails/email_corpus.json

  # Run complete pipeline
  %(prog)s pipeline --user-email user@hotmail.com --output-dir ~/analysis

For more information, see: specs/001-use-the-document/quickstart.md
        """
    )

    # Global options (available to all commands)
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Output directory for all files (default: ~/data/outputs)"
    )

    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose debug logging"
    )

    # Subcommands
    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
        help="Command to execute"
    )

    # ===== EXTRACT COMMAND =====
    extract_parser = subparsers.add_parser(
        "extract",
        help="Extract emails from M365/Hotmail inbox",
        description="Extract all emails from M365 account and save to JSON corpus file."
    )
    extract_parser.add_argument(
        "--user-email",
        required=True,
        help="M365/Hotmail email address to extract from"
    )
    extract_parser.add_argument(
        "--corpus-file",
        type=Path,
        help="Custom path for corpus JSON (default: {output-dir}/email_corpus.json)"
    )
    extract_parser.add_argument(
        "--batch-size",
        type=int,
        default=500,
        help="Number of emails to fetch per batch (default: 500)"
    )
    extract_parser.add_argument(
        "--checkpoint-interval",
        type=int,
        default=100,
        help="Save checkpoint every N emails (default: 100)"
    )

    # ===== ANALYZE COMMAND =====
    analyze_parser = subparsers.add_parser(
        "analyze",
        help="Analyze email corpus for patterns",
        description="Run all 5 analyzers on email corpus and generate analysis results."
    )
    analyze_parser.add_argument(
        "--corpus",
        type=Path,
        help="Path to corpus JSON file (default: {output-dir}/email_corpus.json)"
    )
    analyze_parser.add_argument(
        "--num-clusters",
        type=int,
        default=10,
        help="Number of semantic clusters (default: 10)"
    )
    analyze_parser.add_argument(
        "--analysis-file",
        type=Path,
        help="Custom path for analysis results (default: {output-dir}/corpus_analysis_results.json)"
    )

    # ===== SUGGEST COMMAND =====
    suggest_parser = subparsers.add_parser(
        "suggest",
        help="Generate category suggestions",
        description="Generate category suggestions from analysis results."
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

    # ===== REVIEW COMMAND =====
    review_parser = subparsers.add_parser(
        "review",
        help="Interactively review category suggestions",
        description="Interactively review, rename, merge, or delete category suggestions."
    )
    review_parser.add_argument(
        "--suggestions",
        type=Path,
        help="Path to suggestions JSON (default: {output-dir}/category_suggestions.json)"
    )
    review_parser.add_argument(
        "--approved-file",
        type=Path,
        help="Custom path for approved categories (default: {output-dir}/approved_categories.json)"
    )
    review_parser.add_argument(
        "--no-cleanup",
        action="store_true",
        help="Skip optional cleanup of intermediate files"
    )

    # ===== PIPELINE COMMAND =====
    pipeline_parser = subparsers.add_parser(
        "pipeline",
        help="Run complete end-to-end workflow",
        description="Run extract → analyze → suggest → review → optional cleanup."
    )
    pipeline_parser.add_argument(
        "--user-email",
        required=True,
        help="M365/Hotmail email address to extract from"
    )
    pipeline_parser.add_argument(
        "--num-clusters",
        type=int,
        default=10,
        help="Number of semantic clusters (default: 10)"
    )
    pipeline_parser.add_argument(
        "--no-cleanup",
        action="store_true",
        help="Skip optional cleanup of intermediate files"
    )

    return parser


def setup_output_directory(args: argparse.Namespace) -> None:
    """
    Configure output directory based on CLI arguments.

    Args:
        args: Parsed command-line arguments
    """
    if args.output_dir:
        # User specified custom output directory
        PathConfig.set_output_dir(args.output_dir)
        logger.info(f"Using custom output directory: {args.output_dir}")
    else:
        # Use default
        default_dir = PathConfig.get_default_output_dir()
        logger.info(f"Using default output directory: {default_dir}")

    # Ensure directory exists with secure permissions
    PathConfig.ensure_output_dir_exists()


def cmd_extract(args: argparse.Namespace) -> int:
    """
    Execute email extraction command.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 = success, non-zero = error)
    """
    from src.extractors.m365_extractor import EmailExtractor

    logger.info("=== EMAIL EXTRACTION ===")
    logger.info(f"User email: {args.user_email}")

    # Determine corpus path
    if args.corpus_file:
        corpus_path = args.corpus_file
    else:
        corpus_path = PathConfig.get_corpus_path()

    logger.info(f"Corpus output: {corpus_path}")

    # Create extractor with user email
    try:
        # EmailExtractor needs user_email in constructor
        # Note: checkpoint_dir is being deprecated in favor of PathConfig
        extractor = EmailExtractor(
            user_email=args.user_email,
            checkpoint_dir=str(PathConfig.get_output_dir())
        )
    except Exception as e:
        logger.error(f"✗ Failed to initialize extractor: {e}", exc_info=True)
        return 1

    # Run extraction
    try:
        result = extractor.extract_all(
            max_batch_size=args.batch_size,
            checkpoint_interval=args.checkpoint_interval
        )

        # Save corpus to file
        save_json(result.corpus.model_dump(), corpus_path)

        logger.info(f"✓ Extraction complete: {result.success_count} emails")
        if result.failed_emails:
            logger.warning(f"⚠ {len(result.failed_emails)} errors occurred (see error log)")

        return 0

    except Exception as e:
        logger.error(f"✗ Extraction failed: {e}", exc_info=True)
        return 1


def cmd_analyze(args: argparse.Namespace) -> int:
    """
    Execute corpus analysis command.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 = success, non-zero = error)
    """
    from src.analyzers import run_full_analysis
    from src.models.corpus import Corpus

    logger.info("=== CORPUS ANALYSIS ===")

    # Determine corpus path
    if args.corpus:
        corpus_path = args.corpus
    else:
        corpus_path = PathConfig.get_corpus_path()

    logger.info(f"Corpus input: {corpus_path}")

    # Load corpus
    try:
        corpus_data = load_json(corpus_path)
        corpus = Corpus(**corpus_data)
        logger.info(f"Loaded {len(corpus.emails)} emails")

    except Exception as e:
        logger.error(f"✗ Failed to load corpus: {e}")
        return 1

    # Determine analysis output path
    if args.analysis_file:
        analysis_path = args.analysis_file
    else:
        analysis_path = PathConfig.get_analysis_path()

    logger.info(f"Analysis output: {analysis_path}")

    # Run analysis
    try:
        results = run_full_analysis(
            corpus=corpus,
            num_clusters=args.num_clusters
        )

        # Save results
        save_json(results.model_dump(), analysis_path)

        logger.info("✓ Analysis complete")
        logger.info(f"  - {results.sender_analysis.unique_senders} unique senders")
        logger.info(f"  - {len(results.content_clusters)} semantic clusters")

        return 0

    except Exception as e:
        logger.error(f"✗ Analysis failed: {e}", exc_info=True)
        return 1


def cmd_suggest(args: argparse.Namespace) -> int:
    """
    Execute category suggestion command.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 = success, non-zero = error)
    """
    from src.generators.category_generator import CategoryGenerator
    from src.models.analysis_results import AnalysisResults

    logger.info("=== CATEGORY SUGGESTION ===")

    # Determine analysis path
    if args.analysis:
        analysis_path = args.analysis
    else:
        analysis_path = PathConfig.get_analysis_path()

    logger.info(f"Analysis input: {analysis_path}")

    # Load analysis results
    try:
        analysis_data = load_json(analysis_path)
        results = AnalysisResults(**analysis_data)

    except Exception as e:
        logger.error(f"✗ Failed to load analysis: {e}")
        return 1

    # Determine suggestions output path
    if args.suggestions_file:
        suggestions_path = args.suggestions_file
    else:
        suggestions_path = PathConfig.get_suggestions_path()

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

        # Generate markdown report
        report_path = PathConfig.get_suggestions_report_path()
        report = generator.generate_report(categories)
        report_path.write_text(report, encoding='utf-8')

        logger.info(f"✓ Generated {len(categories)} category suggestions")

        return 0

    except Exception as e:
        logger.error(f"✗ Suggestion generation failed: {e}", exc_info=True)
        return 1


def cmd_review(args: argparse.Namespace) -> int:
    """
    Execute interactive category review command.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 = success, non-zero = error)
    """
    from src.models.category import Category
    from src.ui.category_review import cleanup_intermediate_files, review_categories

    logger.info("=== CATEGORY REVIEW ===")

    # Determine suggestions path
    if args.suggestions:
        suggestions_path = args.suggestions
    else:
        suggestions_path = PathConfig.get_suggestions_path()

    logger.info(f"Suggestions input: {suggestions_path}")

    # Load suggestions
    try:
        suggestions_data = load_json(suggestions_path)
        categories = [Category(**cat) for cat in suggestions_data]

    except Exception as e:
        logger.error(f"✗ Failed to load suggestions: {e}")
        return 1

    # Determine approved output path
    if args.approved_file:
        approved_path = args.approved_file
    else:
        approved_path = PathConfig.get_approved_categories_path()

    logger.info(f"Approved categories output: {approved_path}")

    # Run interactive review
    try:
        approved = review_categories(categories, output_path=approved_path)

        logger.info(f"✓ Approved {len(approved)} categories")

        # Optional cleanup
        if not args.no_cleanup:
            cleanup_intermediate_files(str(PathConfig.get_output_dir()))

        return 0

    except Exception as e:
        logger.error(f"✗ Review failed: {e}", exc_info=True)
        return 1


def cmd_pipeline(args: argparse.Namespace) -> int:
    """
    Execute complete pipeline command.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 = success, non-zero = error)
    """
    logger.info("=== COMPLETE PIPELINE ===")

    # Step 1: Extract
    logger.info("Step 1/4: Extracting emails...")
    extract_args = argparse.Namespace(
        user_email=args.user_email,
        corpus_file=None,
        batch_size=500,
        checkpoint_interval=100,
        output_dir=args.output_dir,
        verbose=args.verbose
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
        verbose=args.verbose
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
        verbose=args.verbose
    )
    if cmd_suggest(suggest_args) != 0:
        return 1

    # Step 4: Review
    logger.info("Step 4/4: Interactive review...")
    review_args = argparse.Namespace(
        suggestions=None,
        approved_file=None,
        no_cleanup=args.no_cleanup,
        output_dir=args.output_dir,
        verbose=args.verbose
    )
    if cmd_review(review_args) != 0:
        return 1

    logger.info("✓ Pipeline complete!")
    return 0


def main() -> int:
    """
    Main CLI entry point.

    Returns:
        Exit code (0 = success, non-zero = error)
    """
    parser = create_parser()
    args = parser.parse_args()

    # Setup logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Configure output directory
    setup_output_directory(args)

    # Dispatch to command handler
    command_handlers = {
        "extract": cmd_extract,
        "analyze": cmd_analyze,
        "suggest": cmd_suggest,
        "review": cmd_review,
        "pipeline": cmd_pipeline
    }

    handler = command_handlers.get(args.command)
    if not handler:
        logger.error(f"Unknown command: {args.command}")
        return 1

    try:
        return handler(args)
    except KeyboardInterrupt:
        logger.warning("\nOperation cancelled by user")
        return 130
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
