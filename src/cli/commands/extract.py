"""Extract command: fetch emails from M365/Hotmail or Gmail."""
import argparse
import time
from pathlib import Path

from tqdm import tqdm

from src.cli.formatters import output_json
from src.cli.parsers import validate_email_format
from src.utils.file_manager import load_json, save_json
from src.utils.logger import get_logger
from src.utils.paths import PathConfig

logger = get_logger(__name__)


def build_extract_parser(subparsers) -> argparse.ArgumentParser:
    """Add extract subparser to the CLI and return it."""
    extract_parser = subparsers.add_parser(
        "extract",
        help="Extract emails from Hotmail/Gmail inbox",
        description="Extract emails from M365/Hotmail or Gmail and save to JSON corpus file.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Extract from Hotmail (default)
  %(prog)s --user-email user@hotmail.com

  # Extract from Gmail
  %(prog)s --user-email user@gmail.com --source gmail

  # Extract from both accounts
  %(prog)s --user-email user@hotmail.com --source both --gmail-email user@gmail.com

  # Extract with larger batches
  %(prog)s --user-email user@hotmail.com --batch-size 1000

  # Incremental extraction (only new emails)
  %(prog)s --user-email user@hotmail.com --since-last

  # Preview without executing
  %(prog)s --user-email user@hotmail.com --dry-run
        """
    )
    extract_parser.add_argument(
        "--user-email",
        required=True,
        help="Primary email address (Hotmail/Outlook or Gmail)"
    )
    extract_parser.add_argument(
        "--source",
        type=str,
        choices=["hotmail", "gmail", "both"],
        default="hotmail",
        help="Email source: hotmail, gmail, or both (default: hotmail)"
    )
    extract_parser.add_argument(
        "--gmail-email",
        type=str,
        help="Gmail address (required when --source both, if different from --user-email)"
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
    extract_parser.add_argument(
        "-n", "--dry-run",
        action="store_true",
        help="Show what would be done without actually executing"
    )
    extract_parser.add_argument(
        "--since-last",
        action="store_true",
        default=False,
        help="Incremental extraction: only fetch emails since last extraction (Task 4B.2)"
    )

    return extract_parser


def cmd_extract(args: argparse.Namespace) -> int:
    """
    Execute email extraction command.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 = success, non-zero = error)
    """
    # Validate email format first (even for dry-run)
    if not validate_email_format(args.user_email):
        logger.error(f"Invalid email format: {args.user_email}")
        if getattr(args, 'json', False):
            output_json({
                "command": "extract",
                "status": "error",
                "error": f"Invalid email format: {args.user_email}"
            })
        return 1

    # Handle dry-run mode
    if getattr(args, 'dry_run', False):
        from src.preview.estimators import ExtractEstimator, format_extract_preview

        estimator = ExtractEstimator()
        estimate = estimator.estimate(args)

        if getattr(args, 'json', False):
            output_json({
                "command": "extract",
                "dry_run": True,
                "status": "preview",
                "user_email": estimate.user_email,
                "output_path": str(estimate.output_path),
                "email_count_estimate": estimate.email_count_estimate,
                "output_size_estimate": estimate.output_size_estimate,
                "duration_estimate": estimate.duration_estimate,
            })
        else:
            print(format_extract_preview(estimate))

        return 0

    start_time = time.time()
    source = getattr(args, 'source', 'hotmail')
    gmail_email = getattr(args, 'gmail_email', None)

    logger.info("=== EMAIL EXTRACTION ===")
    logger.info(f"User email: {args.user_email}")
    logger.info(f"Source: {source}")

    # Determine corpus path
    corpus_path = args.corpus_file or PathConfig.get_corpus_path()

    logger.info(f"Corpus output: {corpus_path}")

    # Build ExtractConfig with source info
    try:
        from src.config.models import ExtractConfig
        from src.services.extraction_service import ExtractionService

        extract_config = ExtractConfig(
            batch_size=args.batch_size,
            checkpoint_interval=args.checkpoint_interval,
            source=source,
            gmail_email=gmail_email or (args.user_email if source in ("gmail", "both") else None),
        )

        output_dir = PathConfig.get_output_dir()
        service = ExtractionService(
            config=extract_config,
            user_email=args.user_email,
            output_dir=output_dir,
        )
    except Exception as e:
        logger.error(
            f"Failed to initialize extraction service for {source} source: {e}. "
            f"Check your authentication credentials and network connection.",
            exc_info=True,
        )
        if getattr(args, 'json', False):
            output_json({
                "command": "extract",
                "status": "error",
                "error": str(e)
            })
        return 1

    # Handle incremental extraction (Task 4B.2)
    existing_corpus = None
    if getattr(args, 'since_last', False):
        from src.models.corpus import Corpus

        try:
            existing_data = load_json(corpus_path)
            existing_corpus = Corpus(**existing_data)
            logger.info(f"Loaded existing corpus with {len(existing_corpus.emails)} emails")
        except FileNotFoundError:
            logger.error(f"No existing corpus found at {corpus_path}. Run full extraction first.")
            if getattr(args, 'json', False):
                output_json({
                    "command": "extract",
                    "status": "error",
                    "error": f"No existing corpus found at {corpus_path}. Run full extraction first."
                })
            return 1
        except Exception as e:
            logger.error(
                f"Failed to load existing corpus from {corpus_path}: {e}. "
                f"The file may be corrupted. Try running a full extraction without --since-last."
            )
            if getattr(args, 'json', False):
                output_json({
                    "command": "extract",
                    "status": "error",
                    "error": str(e)
                })
            return 1

    # Set up tqdm progress bar (suppressed for --json and --quiet)
    use_progress = not getattr(args, 'json', False) and not getattr(args, 'quiet', False)
    bar = None
    if use_progress:
        bar = tqdm(total=None, desc="Extracting emails", unit=" emails", dynamic_ncols=True)

    def _email_progress(current: int, total: int) -> None:
        if bar is not None:
            bar.update(current - bar.n)

    # Run extraction via ExtractionService
    try:
        corpus = service.run(
            since_last=getattr(args, 'since_last', False),
            existing_corpus=existing_corpus,
            email_progress_callback=_email_progress if use_progress else None,
        )

        # Save corpus
        save_json(corpus.model_dump(), corpus_path)

        duration = time.time() - start_time
        total_emails = len(corpus.emails)

        if getattr(args, 'json', False):
            output_json({
                "command": "extract",
                "status": "success",
                "duration_seconds": round(duration, 2),
                "output_file": str(corpus_path),
                "stats": {
                    "emails_extracted": total_emails,
                }
            })
        else:
            logger.info(f"Extraction complete: {total_emails} emails")

        return 0

    except Exception as e:
        logger.error(
            f"Extraction failed for {source} source (user: {args.user_email}): {e}. "
            f"Output was targeted at {corpus_path}. "
            f"Check your network connection and authentication, then retry. "
            f"Use --verbose for full traceback.",
            exc_info=True,
        )
        if getattr(args, 'json', False):
            output_json({
                "command": "extract",
                "status": "error",
                "error": str(e)
            })
        return 1

    finally:
        if bar is not None:
            bar.close()
