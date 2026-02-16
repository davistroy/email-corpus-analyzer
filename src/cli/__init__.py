"""
Email Corpus Extraction and Analysis System - CLI Entry Point.

Commands:
  extract   - Extract emails from M365/Hotmail
  analyze   - Analyze email corpus for patterns
  suggest   - Generate category suggestions
  review    - Interactively review and approve categories
  pipeline  - Run complete end-to-end workflow
  config    - Manage configuration (init, show)
  info      - Show corpus statistics
  export    - Export categories to CSV or HTML format

All commands support --output-dir to specify custom output location.
Default output directory: ~/data/outputs
"""
import argparse
import logging
import sys
from pathlib import Path

from src import __version__
from src.cli.commands.analyze import build_analyze_parser, cmd_analyze
from src.cli.commands.config import (
    build_config_parser,
    cmd_config,
    cmd_config_init,
    cmd_config_show,
    cmd_config_validate,
    validate_config,
)
from src.cli.commands.export import build_export_parser, cmd_export
from src.cli.commands.extract import build_extract_parser, cmd_extract
from src.cli.commands.info import build_info_parser, cmd_info
from src.cli.commands.pipeline import build_pipeline_parser, cmd_pipeline
from src.cli.commands.review import auto_approve_categories, build_review_parser, cmd_review
from src.cli.commands.suggest import build_suggest_parser, cmd_suggest
from src.cli.formatters import output_json
from src.cli.parsers import (
    _CONFIG_MAPPINGS,
    EMAIL_REGEX,
    SUBPARSERS,
    _apply_config_defaults,
    setup_output_directory,
    validate_email_format,
)
from src.config.loader import ConfigLoadError, load_config
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Re-export all public names for backward compatibility.
# Tests and external code use `from src.cli import X` extensively.
__all__ = [
    "create_parser",
    "main",
    "setup_output_directory",
    "validate_email_format",
    "output_json",
    "cmd_extract",
    "cmd_analyze",
    "cmd_suggest",
    "cmd_review",
    "cmd_pipeline",
    "cmd_config",
    "cmd_config_init",
    "cmd_config_show",
    "cmd_config_validate",
    "cmd_info",
    "cmd_export",
    "auto_approve_categories",
    "validate_config",
    "EMAIL_REGEX",
    "SUBPARSERS",
    "_CONFIG_MAPPINGS",
    "_apply_config_defaults",
]


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

  # Get corpus info
  %(prog)s info

For more information, see: specs/001-use-the-document/quickstart.md
        """
    )

    # Version flag
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}"
    )

    # Global options (available to all commands)
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Output directory for all files (default: ~/data/outputs)"
    )

    # Mutually exclusive group for verbose/quiet/json
    output_group = parser.add_mutually_exclusive_group()
    output_group.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose debug logging"
    )
    output_group.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Suppress INFO output, only show warnings and errors"
    )
    output_group.add_argument(
        "--json",
        action="store_true",
        help="Output results as machine-readable JSON"
    )

    parser.add_argument(
        "--config",
        type=Path,
        help="Path to custom configuration file (YAML)"
    )

    # Subcommands
    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
        help="Command to execute"
    )

    # Build each command's subparser and register in SUBPARSERS
    # so _apply_config_defaults() can look up defaults without
    # accessing private argparse internals.
    SUBPARSERS.clear()
    SUBPARSERS["extract"] = build_extract_parser(subparsers)
    SUBPARSERS["analyze"] = build_analyze_parser(subparsers)
    SUBPARSERS["suggest"] = build_suggest_parser(subparsers)
    SUBPARSERS["review"] = build_review_parser(subparsers)
    SUBPARSERS["pipeline"] = build_pipeline_parser(subparsers)
    SUBPARSERS["info"] = build_info_parser(subparsers)
    SUBPARSERS["export"] = build_export_parser(subparsers)
    SUBPARSERS["config"] = build_config_parser(subparsers)

    return parser


def main() -> int:
    """
    Main CLI entry point.

    Returns:
        Exit code (0 = success, non-zero = error)
    """
    parser = create_parser()
    args = parser.parse_args()

    # Setup logging level based on flags
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    elif args.quiet:
        logging.getLogger().setLevel(logging.WARNING)
    elif args.json:
        # In JSON mode, suppress normal logging (only errors)
        logging.getLogger().setLevel(logging.ERROR)

    # Load configuration from files (unless running config command)
    if args.command != "config":
        try:
            config = load_config(config_path=args.config)
            # Apply config defaults to args where CLI didn't specify
            _apply_config_defaults(args, config, parser)
        except ConfigLoadError as e:
            logger.error(f"Failed to load configuration: {e}")
            return 1

    # Configure output directory (skip for info command if no explicit output-dir)
    if args.command != "info" or args.output_dir:
        setup_output_directory(args)

    # Dispatch to command handler
    command_handlers = {
        "extract": cmd_extract,
        "analyze": cmd_analyze,
        "suggest": cmd_suggest,
        "review": cmd_review,
        "pipeline": cmd_pipeline,
        "config": cmd_config,
        "info": cmd_info,
        "export": cmd_export,
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
