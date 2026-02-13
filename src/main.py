#!/usr/bin/env python3
"""
Email Corpus Extraction and Analysis System - CLI Entry Point.

Per specs/001-use-the-document/tasks.md T035-T036 and quickstart.md.

Commands:
  extract   - Extract emails from M365/Hotmail
  analyze   - Analyze email corpus for patterns
  suggest   - Generate category suggestions
  review    - Interactively review and approve categories
  pipeline  - Run complete pipeline (extract → analyze → suggest → review → cleanup)
"""
import argparse

# Setup root logger
import logging
import sys
from pathlib import Path

from src.analyzers import run_full_analysis
from src.extractors.m365_extractor import EmailExtractor
from src.generators.category_generator import CategoryGenerator
from src.models.analysis_results import AnalysisResults
from src.models.category import Category
from src.models.corpus import Corpus
from src.ui.category_review import cleanup_intermediate_files, review_categories
from src.utils.file_manager import atomic_write_text, ensure_output_dir, load_json, save_json
from src.utils.logger import setup_logger

logger = setup_logger(
    __name__,
    log_file=Path("outputs/errors.log"),
    level=logging.DEBUG
)

# Default configuration
DEFAULT_OUTPUT_DIR = Path("/mnt/user-data/outputs")
DEFAULT_USER_EMAIL = "user@example.com"  # Should be configured


class EmailProcessorCLI:
    """CLI command dispatcher for email processing system."""

    def __init__(self, output_dir: Path, user_email: str):
        """
        Initialize CLI processor.

        Args:
            output_dir: Directory for output files
            user_email: User's M365 email address
        """
        self.output_dir = output_dir
        self.user_email = user_email
        ensure_output_dir(self.output_dir)
        logger.info(f"Initialized CLI with output_dir={output_dir}")

    def extract(self, batch_size: int = 500, checkpoint_interval: int = 100) -> bool:
        """
        Extract emails from M365/Hotmail.

        Per quickstart.md Scenario 1 (lines 17-67).

        Args:
            batch_size: Maximum emails per API request
            checkpoint_interval: Save checkpoint every N emails

        Returns:
            True if successful, False otherwise
        """
        logger.info("Starting email extraction command...")
        print("Starting email extraction...")

        try:
            # Initialize extractor
            extractor = EmailExtractor(
                user_email=self.user_email,
                checkpoint_dir=str(self.output_dir)
            )

            # Create progress tracker
            def progress_callback(current: int, total: int):
                percentage = (current / total * 100) if total > 0 else 0
                batch_num = (current // batch_size) + 1
                total_batches = (total // batch_size) + 1
                print(f"Processing batch {batch_num}/{total_batches}... [{current}/{total}] ({percentage:.1f}%)")

            # Run extraction
            result = extractor.extract_all(
                max_batch_size=batch_size,
                checkpoint_interval=checkpoint_interval,
                progress_callback=progress_callback
            )

            print("\nExtraction complete!")
            print(f"Successfully processed: {result.success_count} emails")
            print(f"Failed: {result.failure_count} emails")

            # Save corpus
            corpus_path = self.output_dir / "email_corpus.json"
            save_json(result.corpus.model_dump(), corpus_path)
            print(f"Output saved to: {corpus_path}")

            # Save error log if there are failures
            if result.failed_emails:
                error_log_path = self.output_dir / "extraction_errors.log"
                with open(error_log_path, 'w', encoding='utf-8') as f:
                    for error in result.failed_emails:
                        f.write(f"[{error.timestamp}] {error.error_type}: {error.email_id} - {error.error_message}\n")
                print(f"(see {error_log_path} for error details)")

            return True

        except Exception as e:
            logger.error(f"Extraction failed: {e}", exc_info=True)
            print(f"ERROR: Extraction failed - {e}")
            return False

    def analyze(self, num_clusters: int = 10) -> bool:
        """
        Analyze email corpus for patterns.

        Per quickstart.md Scenario 2 (lines 70-117).

        Args:
            num_clusters: Number of semantic clusters to generate

        Returns:
            True if successful, False otherwise
        """
        logger.info("Starting corpus analysis command...")
        print("Starting corpus analysis...")

        try:
            # Load corpus
            corpus_path = self.output_dir / "email_corpus.json"
            corpus_data = load_json(corpus_path)
            corpus = Corpus(**corpus_data)
            print(f"Analyzing {len(corpus.emails)} emails...")
            print()

            # Progress callback
            def progress_callback(analyzer_name: str, current: int, total: int):
                percentage = (current / total * 100) if total > 0 else 0
                bar_width = 20
                filled = int(bar_width * current / total) if total > 0 else 0
                bar = "=" * filled + "-" * (bar_width - filled)
                print(f"{analyzer_name.capitalize()} analysis... [{bar}] {current}/{total} ({percentage:.1f}%)")

            # Run analysis with progress tracking
            print("1. Analyzing senders...")
            print("2. Analyzing subject patterns...")
            print("3. Analyzing content semantics...")
            print("4. Analyzing temporal patterns...")
            print("5. Calculating volume statistics...")
            print()

            results, _incremental_stats = run_full_analysis(
                corpus,
                num_clusters=num_clusters,
                progress_callback=progress_callback
            )

            print("\nAnalysis complete!")

            # Save results
            results_path = self.output_dir / "corpus_analysis_results.json"
            save_json(results.model_dump(), results_path)
            print(f"Results saved to: {results_path}")

            return True

        except FileNotFoundError:
            logger.error("Corpus file not found. Run 'extract' command first.")
            print("ERROR: Email corpus not found. Run 'extract' command first.")
            return False
        except Exception as e:
            logger.error(f"Analysis failed: {e}", exc_info=True)
            print(f"ERROR: Analysis failed - {e}")
            return False

    def suggest(
        self,
        min_cluster_percentage: float = 5.0,
        min_sender_count: int = 20
    ) -> bool:
        """
        Generate category suggestions.

        Per quickstart.md Scenario 3 (lines 120-168).

        Args:
            min_cluster_percentage: Minimum cluster size % to suggest
            min_sender_count: Minimum emails from sender to suggest category

        Returns:
            True if successful, False otherwise
        """
        logger.info("Starting category suggestion command...")
        print("Generating category suggestions...")

        try:
            # Load analysis results
            results_path = self.output_dir / "corpus_analysis_results.json"
            results_data = load_json(results_path)
            results = AnalysisResults(**results_data)

            # Generate suggestions
            generator = CategoryGenerator()
            categories = generator.generate_suggestions(
                results,
                min_cluster_percentage=min_cluster_percentage,
                min_sender_count=min_sender_count
            )

            print(f"From content clusters: {sum(1 for c in categories if c.source.value == 'content_cluster')} categories")
            print(f"From high-volume senders: {sum(1 for c in categories if c.source.value == 'sender')} categories")
            print(f"From templates: {sum(1 for c in categories if c.source.value == 'template')} categories")
            print()
            print(f"Generated {len(categories)} unique category suggestions")

            # Save suggestions
            suggestions_path = self.output_dir / "category_suggestions.json"
            suggestions_data = {
                "total_categories": len(categories),
                "generation_date": __import__('datetime').datetime.now().isoformat(),
                "categories": [cat.model_dump() for cat in categories]
            }
            save_json(suggestions_data, suggestions_path)
            print(f"Saved to: {suggestions_path}")

            # Generate report (atomic write to prevent corruption)
            report = generator.generate_report(categories)
            report_path = self.output_dir / "category_suggestions_report.md"
            atomic_write_text(report_path, report)
            print(f"Report saved to: {report_path}")

            return True

        except FileNotFoundError:
            logger.error("Analysis results not found. Run 'analyze' command first.")
            print("ERROR: Analysis results not found. Run 'analyze' command first.")
            return False
        except Exception as e:
            logger.error(f"Suggestion generation failed: {e}", exc_info=True)
            print(f"ERROR: Suggestion generation failed - {e}")
            return False

    def review(self, enable_cleanup: bool = True) -> bool:
        """
        Interactively review and approve categories.

        Per quickstart.md Scenario 4 (lines 171-243).

        Args:
            enable_cleanup: Whether to prompt for cleanup after review

        Returns:
            True if successful, False otherwise
        """
        logger.info("Starting category review command...")

        try:
            # Load suggestions
            suggestions_path = self.output_dir / "category_suggestions.json"
            suggestions_data = load_json(str(suggestions_path))
            categories = [Category(**cat) for cat in suggestions_data]

            # Determine approved output path
            approved_path = self.output_dir / "approved_categories.json"

            # Run interactive review
            approved = review_categories(categories, output_path=approved_path)

            # Optional cleanup
            if enable_cleanup:
                cleanup_intermediate_files(str(self.output_dir))

            return True

        except FileNotFoundError:
            logger.error("Category suggestions not found. Run 'suggest' command first.")
            print("ERROR: Category suggestions not found. Run 'suggest' command first.")
            return False
        except Exception as e:
            logger.error(f"Review failed: {e}", exc_info=True)
            print(f"ERROR: Review failed - {e}")
            return False

    def pipeline(
        self,
        batch_size: int = 500,
        checkpoint_interval: int = 100,
        num_clusters: int = 10,
        min_cluster_percentage: float = 5.0,
        min_sender_count: int = 20
    ) -> bool:
        """
        Run complete pipeline: extract → analyze → suggest → review → cleanup.

        Per quickstart.md End-to-End Validation (lines 290-319).

        Args:
            batch_size: Extraction batch size
            checkpoint_interval: Checkpoint interval
            num_clusters: Number of semantic clusters
            min_cluster_percentage: Min cluster size %
            min_sender_count: Min sender email count

        Returns:
            True if all steps successful, False otherwise
        """
        logger.info("Starting complete pipeline...")
        print("=" * 60)
        print("EMAIL PROCESSING PIPELINE")
        print("=" * 60)
        print()

        steps = [
            ("STEP 1/5: Extracting emails", "extract"),
            ("STEP 2/5: Analyzing corpus", "analyze"),
            ("STEP 3/5: Generating suggestions", "suggest"),
            ("STEP 4/5: Reviewing categories", "review"),
            ("STEP 5/5: Cleanup (optional)", None)  # Cleanup handled by review
        ]

        try:
            # Step 1: Extract
            print(steps[0][0])
            print("-" * 60)
            if not self.extract(batch_size, checkpoint_interval):
                print("\nPipeline failed at extraction step.")
                return False
            print()

            # Step 2: Analyze
            print(steps[1][0])
            print("-" * 60)
            if not self.analyze(num_clusters):
                print("\nPipeline failed at analysis step.")
                return False
            print()

            # Step 3: Suggest
            print(steps[2][0])
            print("-" * 60)
            if not self.suggest(min_cluster_percentage, min_sender_count):
                print("\nPipeline failed at suggestion step.")
                return False
            print()

            # Step 4: Review (includes optional cleanup)
            print(steps[3][0])
            print("-" * 60)
            if not self.review(enable_cleanup=True):
                print("\nPipeline failed at review step.")
                return False
            print()

            # Success
            print("=" * 60)
            print("PIPELINE COMPLETE!")
            print("=" * 60)
            print(f"\nFinal output: {self.output_dir / 'approved_categories.json'}")

            return True

        except KeyboardInterrupt:
            logger.warning("Pipeline interrupted by user")
            print("\n\nPipeline interrupted by user.")
            return False
        except Exception as e:
            logger.error(f"Pipeline failed: {e}", exc_info=True)
            print(f"\nERROR: Pipeline failed - {e}")
            return False


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Email Corpus Extraction and Analysis System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python src/main.py extract
  python src/main.py analyze --clusters 15
  python src/main.py suggest
  python src/main.py review
  python src/main.py pipeline

For more information, see specs/001-use-the-document/quickstart.md
        """
    )

    # Global arguments
    parser.add_argument(
        '--output-dir',
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f'Output directory (default: {DEFAULT_OUTPUT_DIR})'
    )
    parser.add_argument(
        '--user-email',
        type=str,
        default=DEFAULT_USER_EMAIL,
        help=f'M365 user email (default: {DEFAULT_USER_EMAIL})'
    )

    # Subcommands
    subparsers = parser.add_subparsers(dest='command', help='Command to run')

    # Extract command
    extract_parser = subparsers.add_parser(
        'extract',
        help='Extract emails from M365/Hotmail'
    )
    extract_parser.add_argument(
        '--batch-size',
        type=int,
        default=500,
        help='Maximum emails per API request (default: 500)'
    )
    extract_parser.add_argument(
        '--checkpoint-interval',
        type=int,
        default=100,
        help='Save checkpoint every N emails (default: 100)'
    )

    # Analyze command
    analyze_parser = subparsers.add_parser(
        'analyze',
        help='Analyze email corpus for patterns'
    )
    analyze_parser.add_argument(
        '--clusters',
        type=int,
        default=10,
        help='Number of semantic clusters (default: 10)'
    )

    # Suggest command
    suggest_parser = subparsers.add_parser(
        'suggest',
        help='Generate category suggestions'
    )
    suggest_parser.add_argument(
        '--min-cluster-pct',
        type=float,
        default=5.0,
        help='Minimum cluster size percentage (default: 5.0)'
    )
    suggest_parser.add_argument(
        '--min-sender-count',
        type=int,
        default=20,
        help='Minimum emails from sender (default: 20)'
    )

    # Review command
    review_parser = subparsers.add_parser(
        'review',
        help='Interactively review and approve categories'
    )
    review_parser.add_argument(
        '--no-cleanup',
        action='store_true',
        help='Disable cleanup prompt after review'
    )

    # Pipeline command
    pipeline_parser = subparsers.add_parser(
        'pipeline',
        help='Run complete pipeline (extract → analyze → suggest → review)'
    )
    pipeline_parser.add_argument(
        '--batch-size',
        type=int,
        default=500,
        help='Extraction batch size (default: 500)'
    )
    pipeline_parser.add_argument(
        '--checkpoint-interval',
        type=int,
        default=100,
        help='Checkpoint interval (default: 100)'
    )
    pipeline_parser.add_argument(
        '--clusters',
        type=int,
        default=10,
        help='Number of semantic clusters (default: 10)'
    )
    pipeline_parser.add_argument(
        '--min-cluster-pct',
        type=float,
        default=5.0,
        help='Minimum cluster size percentage (default: 5.0)'
    )
    pipeline_parser.add_argument(
        '--min-sender-count',
        type=int,
        default=20,
        help='Minimum emails from sender (default: 20)'
    )

    # Parse arguments
    args = parser.parse_args()

    # Check if command provided
    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Initialize CLI
    cli = EmailProcessorCLI(
        output_dir=args.output_dir,
        user_email=args.user_email
    )

    # Execute command
    success = False
    try:
        if args.command == 'extract':
            success = cli.extract(
                batch_size=args.batch_size,
                checkpoint_interval=args.checkpoint_interval
            )

        elif args.command == 'analyze':
            success = cli.analyze(num_clusters=args.clusters)

        elif args.command == 'suggest':
            success = cli.suggest(
                min_cluster_percentage=args.min_cluster_pct,
                min_sender_count=args.min_sender_count
            )

        elif args.command == 'review':
            success = cli.review(enable_cleanup=not args.no_cleanup)

        elif args.command == 'pipeline':
            success = cli.pipeline(
                batch_size=args.batch_size,
                checkpoint_interval=args.checkpoint_interval,
                num_clusters=args.clusters,
                min_cluster_percentage=args.min_cluster_pct,
                min_sender_count=args.min_sender_count
            )

    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user.")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        print(f"\nFATAL ERROR: {e}")
        sys.exit(1)

    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
