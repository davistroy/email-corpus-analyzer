"""Info command: show corpus statistics."""
import argparse
from datetime import datetime
from pathlib import Path

from src.cli.formatters import output_json
from src.utils.file_manager import load_json
from src.utils.logger import get_logger
from src.utils.paths import PathConfig

logger = get_logger(__name__)


def build_info_parser(subparsers) -> argparse.ArgumentParser:
    """Add info subparser to the CLI and return it."""
    info_parser = subparsers.add_parser(
        "info",
        help="Show corpus statistics",
        description="Display information about the email corpus without loading all data.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Show info for default corpus
  %(prog)s

  # Show info for custom corpus file
  %(prog)s --corpus /path/to/corpus.json

  # Output as JSON
  %(prog)s --json
        """
    )
    info_parser.add_argument(
        "--corpus",
        type=Path,
        help="Path to corpus JSON file (default: {output-dir}/email_corpus.json)"
    )

    return info_parser


def cmd_info(args: argparse.Namespace) -> int:
    """
    Execute info command to show corpus statistics.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 = success, non-zero = error)
    """
    # Determine corpus path
    corpus_path = args.corpus or PathConfig.get_corpus_path()

    # Load corpus data
    try:
        corpus_data = load_json(corpus_path)
    except FileNotFoundError:
        logger.error(f"Corpus file not found: {corpus_path}")
        if getattr(args, 'json', False):
            output_json({
                "command": "info",
                "status": "error",
                "error": f"Corpus file not found: {corpus_path}"
            })
        return 1
    except Exception as e:
        logger.error(f"Failed to load corpus: {e}")
        if getattr(args, 'json', False):
            output_json({
                "command": "info",
                "status": "error",
                "error": str(e)
            })
        return 1

    # Extract statistics
    emails = corpus_data.get("emails", [])

    email_count = len(emails)

    # Get unique senders and domains
    senders = set()
    domains = set()
    for email in emails:
        sender = email.get("sender_email", "")
        if sender:
            senders.add(sender)
            if "@" in sender:
                domains.add(sender.split("@")[1])

    # Get date range
    dates = []
    for email in emails:
        date_str = email.get("received_date")
        if date_str:
            try:
                # Handle ISO format
                if isinstance(date_str, str):
                    dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                    dates.append(dt)
            except ValueError:
                pass

    date_range_str = "N/A"
    date_span_days = 0
    if dates:
        oldest = min(dates)
        newest = max(dates)
        date_span_days = (newest - oldest).days
        date_range_str = f"{oldest.strftime('%Y-%m-%d')} to {newest.strftime('%Y-%m-%d')} ({date_span_days} days)"

    # Get file size
    try:
        file_size = corpus_path.stat().st_size
        file_size_mb = file_size / (1024 * 1024)
        file_size_str = f"{file_size_mb:.1f} MB"
    except Exception:
        file_size = 0
        file_size_str = "Unknown"

    # Check for analysis and category files
    analysis_path = PathConfig.get_analysis_path()
    suggestions_path = PathConfig.get_suggestions_path()
    approved_path = PathConfig.get_approved_categories_path()

    analysis_available = analysis_path.exists() if analysis_path else False
    suggestions_count = 0
    approved_count = 0

    if suggestions_path and suggestions_path.exists():
        try:
            suggestions_data = load_json(suggestions_path)
            suggestions_count = len(suggestions_data)
        except Exception:
            pass

    if approved_path and approved_path.exists():
        try:
            approved_data = load_json(approved_path)
            approved_count = len(approved_data)
        except Exception:
            pass

    if getattr(args, 'json', False):
        output_json({
            "command": "info",
            "status": "success",
            "corpus_file": str(corpus_path),
            "file_size_bytes": file_size,
            "email_count": email_count,
            "unique_senders": len(senders),
            "unique_domains": len(domains),
            "date_range": {
                "oldest": min(dates).isoformat() if dates else None,
                "newest": max(dates).isoformat() if dates else None,
                "span_days": date_span_days
            },
            "analysis_available": analysis_available,
            "categories_suggested": suggestions_count,
            "categories_approved": approved_count
        })
    else:
        print("\nCorpus Information")
        print("-" * 50)
        print(f"File:           {corpus_path}")
        print(f"Size:           {file_size_str}")
        print(f"Emails:         {email_count:,}")
        print(f"Date Range:     {date_range_str}")
        print(f"Unique Senders: {len(senders):,}")
        print(f"Unique Domains: {len(domains):,}")
        print()
        if analysis_available:
            print("Analysis Status: Available")
        else:
            print("Analysis Status: Not available")
        if suggestions_count > 0 or approved_count > 0:
            print(f"Categories:      {suggestions_count} suggested, {approved_count} approved")
        print()

    return 0
