"""Export command: export categories to various formats."""

import argparse
import time
from pathlib import Path

from src.cli.formatters import output_json
from src.utils.file_manager import load_json
from src.utils.logger import get_logger
from src.utils.paths import PathConfig

logger = get_logger(__name__)


def build_export_parser(subparsers) -> argparse.ArgumentParser:
    """Add export subparser to the CLI and return it."""
    export_parser = subparsers.add_parser(
        "export",
        help="Export categories to CSV, HTML, or email rules format",
        description="Export approved categories to CSV, HTML, Outlook rules, or Gmail filters.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Export to CSV (Excel-compatible)
  %(prog)s --format csv

  # Export to HTML report
  %(prog)s --format html

  # Export to Outlook rules XML
  %(prog)s --format outlook-rules

  # Export to Gmail filters XML
  %(prog)s --format gmail-filters

  # Export to custom path
  %(prog)s --format csv --output /path/to/categories.csv

  # Export from custom input file
  %(prog)s --format html --input /path/to/categories.json

Import Instructions:
  Outlook: File -> Manage Rules & Alerts -> Options -> Import Rules
  Gmail: Settings -> See all settings -> Filters -> Import filters
        """,
    )
    export_parser.add_argument(
        "--format",
        type=str,
        required=True,
        choices=["csv", "html", "outlook-rules", "gmail-filters"],
        help="Export format: csv, html, outlook-rules, or gmail-filters",
    )
    export_parser.add_argument(
        "--output", type=Path, help="Custom output path (default: auto-generated in output dir)"
    )
    export_parser.add_argument(
        "--input", type=Path, help="Input categories file (default: approved_categories.json)"
    )

    return export_parser


def cmd_export(args: argparse.Namespace) -> int:
    """
    Execute export command.

    Exports approved categories to CSV, HTML, Outlook rules, or Gmail filters format.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 = success, non-zero = error)
    """
    from datetime import datetime

    from src.exporters.csv_exporter import export_categories_to_csv
    from src.exporters.html_exporter import export_categories_to_html
    from src.exporters.rule_exporter import GmailFilterExporter, OutlookRuleExporter
    from src.models.category import Category

    start_time = time.time()

    logger.info(f"=== CATEGORY EXPORT ({args.format.upper()}) ===")

    # Determine input path
    input_path = args.input or PathConfig.get_approved_categories_path()

    logger.info(f"Input file: {input_path}")

    # Load categories
    try:
        categories_data = load_json(input_path)
        categories = [Category(**cat) for cat in categories_data]
        logger.info(f"Loaded {len(categories)} categories")

    except FileNotFoundError:
        logger.error(
            f"Categories file not found: {input_path}. "
            f"Run the full pipeline ('extract' -> 'analyze' -> 'suggest' -> 'review') first, "
            f"or specify a valid input file with --input."
        )
        if getattr(args, "json", False):
            output_json(
                {
                    "command": "export",
                    "status": "error",
                    "error": f"Categories file not found: {input_path}",
                }
            )
        return 1
    except Exception as e:
        logger.error(
            f"Failed to load categories from {input_path}: {e}. "
            f"The file may be corrupted or contain invalid data. "
            f"Try re-running 'review' to regenerate approved categories."
        )
        if getattr(args, "json", False):
            output_json({"command": "export", "status": "error", "error": str(e)})
        return 1

    # Determine output path
    if args.output:
        output_path = args.output
    else:
        # Auto-generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if args.format == "csv":
            output_path = PathConfig.get_output_dir() / f"categories_{timestamp}.csv"
        elif args.format == "html":
            output_path = PathConfig.get_output_dir() / f"category_report_{timestamp}.html"
        elif args.format == "outlook-rules":
            output_path = PathConfig.get_output_dir() / f"outlook_rules_{timestamp}.xml"
        else:  # gmail-filters
            output_path = PathConfig.get_output_dir() / f"gmail_filters_{timestamp}.xml"

    logger.info(f"Output file: {output_path}")

    # Export based on format
    try:
        if args.format == "csv":
            result_path = export_categories_to_csv(categories, output_path)
        elif args.format == "html":
            result_path = export_categories_to_html(categories, output_path)
        elif args.format == "outlook-rules":
            exporter = OutlookRuleExporter()
            result_path = exporter.export_to_file(categories, output_path)
        else:  # gmail-filters
            exporter = GmailFilterExporter()
            result_path = exporter.export_to_file(categories, output_path)

        duration = time.time() - start_time

        if getattr(args, "json", False):
            output_json(
                {
                    "command": "export",
                    "status": "success",
                    "format": args.format,
                    "duration_seconds": round(duration, 2),
                    "output_file": str(result_path),
                    "categories_exported": len(categories),
                }
            )
        else:
            logger.info(f"Export complete: {result_path}")
            logger.info(f"Exported {len(categories)} categories to {args.format.upper()}")

            # Show import instructions for rule exports
            if args.format == "outlook-rules":
                logger.info("To import: File -> Manage Rules & Alerts -> Options -> Import Rules")
            elif args.format == "gmail-filters":
                logger.info("To import: Settings -> See all settings -> Filters -> Import filters")

        return 0

    except Exception as e:
        logger.error(
            f"Export to {args.format.upper()} failed. "
            f"Input: {input_path}, Output: {output_path}. "
            f"Error: {e}. "
            f"Check that the output directory exists and is writable.",
            exc_info=True,
        )
        if getattr(args, "json", False):
            output_json({"command": "export", "status": "error", "error": str(e)})
        return 1
