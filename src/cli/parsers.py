"""Shared CLI parser helpers and configuration mapping."""
import argparse
import re
from collections.abc import Callable
from typing import Any

from src.utils.logger import get_logger
from src.utils.paths import PathConfig

logger = get_logger(__name__)


# Email validation regex pattern (RFC 5322 simplified)
EMAIL_REGEX = re.compile(
    r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
)


def validate_email_format(email: str) -> bool:
    """
    Validate email address format.

    Args:
        email: Email address to validate

    Returns:
        True if valid email format, False otherwise
    """
    if not email or not isinstance(email, str):
        return False
    return bool(EMAIL_REGEX.match(email.strip()))


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


# Mapping from CLI argument name to config accessor lambda.
# Adding a new CLI option that can be overridden by config requires only
# adding one entry here.  _apply_config_defaults() iterates this mapping
# and compares the current arg value against the parser default to decide
# whether the user explicitly supplied the flag on the command line.
_CONFIG_MAPPINGS: dict[str, Callable[..., Any]] = {
    "output_dir": lambda c: c.output_dir,
    "verbose": lambda c: c.verbose,
    "user_email": lambda c: c.user_email,
    "batch_size": lambda c: c.extract.batch_size,
    "checkpoint_interval": lambda c: c.extract.checkpoint_interval,
    "num_clusters": lambda c: c.analyze.num_clusters,
    "min_cluster_percentage": lambda c: c.suggest.min_cluster_percentage,
    "min_sender_count": lambda c: c.suggest.min_sender_count,
    "no_cleanup": lambda c: c.review.no_cleanup,
}


def _apply_config_defaults(
    args: argparse.Namespace,
    config,
    parser: argparse.ArgumentParser,
) -> None:
    """
    Apply configuration file defaults to CLI arguments.

    CLI arguments always take precedence over config file values.
    Only applies config values where CLI didn't provide a value
    (i.e. the arg still holds the parser default).

    Uses _CONFIG_MAPPINGS so that adding a new config-backed CLI option
    requires only one new mapping entry -- no hardcoded default comparisons.

    Args:
        args: Parsed command-line arguments (modified in place)
        config: Loaded AppConfig instance
        parser: The ArgumentParser used to parse args (for default lookup)
    """
    # Build a lookup that checks the main parser first, then the active
    # subparser, so we can resolve defaults for both global and
    # command-specific arguments.
    subparser = None
    if hasattr(args, "command") and args.command:
        subparser_actions = parser._subparsers._group_actions
        if subparser_actions:
            choices = subparser_actions[0].choices
            subparser = choices.get(args.command)

    def _get_parser_default(attr: str):
        """Return the argparse default for *attr*, checking subparser first."""
        if subparser is not None:
            val = subparser.get_default(attr)
            if val is not None:
                return val
        return parser.get_default(attr)

    for attr, config_accessor in _CONFIG_MAPPINGS.items():
        # Skip attributes that don't exist on this command's namespace
        if not hasattr(args, attr):
            continue

        current_value = getattr(args, attr)
        config_value = config_accessor(config)
        parser_default = _get_parser_default(attr)

        # If the config doesn't provide a meaningful override, skip
        if config_value is None:
            continue

        # Only override when the CLI value matches the parser default
        # (meaning the user didn't explicitly set it on the command line)
        if current_value == parser_default:
            setattr(args, attr, config_value)
