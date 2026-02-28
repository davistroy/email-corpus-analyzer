"""Config command: manage configuration files."""

import argparse
from pathlib import Path

from src.cli.formatters import output_json
from src.cli.parsers import validate_email_format
from src.config.loader import (
    ConfigLoadError,
    generate_template,
    get_global_config_path,
    get_project_config_path,
    load_config,
    show_resolved_config,
)
from src.utils.logger import get_logger

logger = get_logger(__name__)


def build_config_parser(subparsers) -> argparse.ArgumentParser:
    """Add config subparser to the CLI and return it."""
    config_parser = subparsers.add_parser(
        "config",
        help="Manage configuration files",
        description="Initialize or display configuration settings.",
    )
    config_subparsers = config_parser.add_subparsers(
        dest="config_action", required=True, help="Config action to perform"
    )

    # config init
    config_init_parser = config_subparsers.add_parser(
        "init",
        help="Generate a template configuration file",
        description="Create a new configuration file with default values.",
    )
    config_init_parser.add_argument(
        "--output",
        dest="config_output",
        type=Path,
        help="Output path for config file (default: .email-analyzer.yaml)",
    )
    config_init_parser.add_argument(
        "--global",
        dest="config_global",
        action="store_true",
        help="Create global config in ~/.config/email-analyzer/",
    )

    # config show
    config_subparsers.add_parser(
        "show",
        help="Display resolved configuration",
        description="Show the current configuration with all sources merged.",
    )

    # config validate
    config_subparsers.add_parser(
        "validate",
        help="Validate configuration settings",
        description="Check all configuration values and runtime conditions.",
    )

    return config_parser


def validate_config(config) -> list[dict]:
    """
    Validate configuration settings and check runtime conditions.

    Args:
        config: AppConfig instance to validate

    Returns:
        List of validation results, each containing:
        - field: Name of the config field
        - status: 'ok', 'warning', or 'error'
        - message: Description of the validation result
    """
    results = []

    # Validate output_dir
    if config.output_dir:
        output_path = Path(config.output_dir).expanduser()
        if output_path.exists():
            if output_path.is_dir():
                # Check if writable
                try:
                    test_file = output_path / ".write_test"
                    test_file.touch()
                    test_file.unlink()
                    results.append(
                        {
                            "field": "output_dir",
                            "status": "ok",
                            "message": f"Directory exists and is writable: {output_path}",
                        }
                    )
                except (PermissionError, OSError):
                    results.append(
                        {
                            "field": "output_dir",
                            "status": "error",
                            "message": f"Directory is not writable: {output_path}",
                        }
                    )
            else:
                results.append(
                    {
                        "field": "output_dir",
                        "status": "error",
                        "message": f"Path exists but is not a directory: {output_path}",
                    }
                )
        else:
            # Check if parent exists and is writable
            parent = output_path.parent
            if parent.exists():
                results.append(
                    {
                        "field": "output_dir",
                        "status": "warning",
                        "message": f"Directory does not exist but parent is accessible: {output_path}",
                    }
                )
            else:
                results.append(
                    {
                        "field": "output_dir",
                        "status": "error",
                        "message": f"Directory does not exist and cannot be created: {output_path}",
                    }
                )
    else:
        results.append(
            {"field": "output_dir", "status": "ok", "message": "Using default output directory"}
        )

    # Validate user_email
    if config.user_email:
        if validate_email_format(config.user_email):
            results.append(
                {
                    "field": "user_email",
                    "status": "ok",
                    "message": f"Valid email format: {config.user_email}",
                }
            )
        else:
            results.append(
                {
                    "field": "user_email",
                    "status": "error",
                    "message": f"Invalid email format: {config.user_email}",
                }
            )
    else:
        results.append(
            {
                "field": "user_email",
                "status": "warning",
                "message": "No user email configured (required for extract command)",
            }
        )

    # Validate extract settings
    if config.extract.batch_size <= 0:
        results.append(
            {
                "field": "extract.batch_size",
                "status": "error",
                "message": "Batch size must be positive",
            }
        )
    else:
        results.append(
            {
                "field": "extract.batch_size",
                "status": "ok",
                "message": f"Batch size: {config.extract.batch_size}",
            }
        )

    if config.extract.checkpoint_interval <= 0:
        results.append(
            {
                "field": "extract.checkpoint_interval",
                "status": "error",
                "message": "Checkpoint interval must be positive",
            }
        )
    else:
        results.append(
            {
                "field": "extract.checkpoint_interval",
                "status": "ok",
                "message": f"Checkpoint interval: {config.extract.checkpoint_interval}",
            }
        )

    # Validate analyze settings
    if config.analyze.num_clusters < 1:
        results.append(
            {
                "field": "analyze.num_clusters",
                "status": "error",
                "message": "Number of clusters must be at least 1",
            }
        )
    else:
        results.append(
            {
                "field": "analyze.num_clusters",
                "status": "ok",
                "message": f"Number of clusters: {config.analyze.num_clusters}",
            }
        )

    # Validate suggest settings
    if config.suggest.min_cluster_percentage < 0 or config.suggest.min_cluster_percentage > 100:
        results.append(
            {
                "field": "suggest.min_cluster_percentage",
                "status": "error",
                "message": "Min cluster percentage must be between 0 and 100",
            }
        )
    else:
        results.append(
            {
                "field": "suggest.min_cluster_percentage",
                "status": "ok",
                "message": f"Min cluster percentage: {config.suggest.min_cluster_percentage}%",
            }
        )

    if config.suggest.min_sender_count < 1:
        results.append(
            {
                "field": "suggest.min_sender_count",
                "status": "error",
                "message": "Min sender count must be at least 1",
            }
        )
    else:
        results.append(
            {
                "field": "suggest.min_sender_count",
                "status": "ok",
                "message": f"Min sender count: {config.suggest.min_sender_count}",
            }
        )

    return results


def cmd_config_init(args: argparse.Namespace) -> int:
    """
    Execute config init command - generate template configuration file.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 = success, non-zero = error)
    """
    # Determine output path
    if args.config_output:
        output_path = args.config_output
    elif args.config_global:
        output_path = get_global_config_path()
        # Ensure parent directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
    else:
        output_path = get_project_config_path()

    # Generate and write template
    try:
        template = generate_template()
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(template)
        logger.info(f"Created configuration file: {output_path}")
        return 0
    except OSError as e:
        logger.error(
            f"Failed to write configuration file to {output_path}: {e}. "
            f"Check that the directory exists and is writable."
        )
        return 1


def cmd_config_show(args: argparse.Namespace) -> int:
    """
    Execute config show command - display resolved configuration.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 = success, non-zero = error)
    """
    try:
        config = load_config(config_path=args.config)
        output = show_resolved_config(config)
        print(output)
        return 0
    except ConfigLoadError as e:
        config_path_display = (
            args.config or f"{get_global_config_path()} / {get_project_config_path()}"
        )
        logger.error(
            f"Failed to load configuration from {config_path_display}: {e}. "
            f"Run 'config validate' to check your config file, "
            f"or 'config init' to generate a new template."
        )
        return 1


def cmd_config_validate(args: argparse.Namespace) -> int:
    """
    Execute config validate command - validate all configuration settings.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 = success, 1 = has errors)
    """
    try:
        config = load_config(config_path=args.config)
    except ConfigLoadError as e:
        config_path_display = (
            args.config or f"{get_global_config_path()} / {get_project_config_path()}"
        )
        logger.error(
            f"Failed to load configuration from {config_path_display}: {e}. "
            f"Run 'config init' to generate a valid config template."
        )
        if getattr(args, "json", False):
            output_json({"command": "config validate", "status": "error", "error": str(e)})
        return 1

    validations = validate_config(config)

    # Count errors
    errors = [v for v in validations if v["status"] == "error"]
    warnings = [v for v in validations if v["status"] == "warning"]

    if getattr(args, "json", False):
        output_json(
            {
                "command": "config validate",
                "status": "error" if errors else "ok",
                "validations": validations,
                "summary": {
                    "total": len(validations),
                    "ok": len([v for v in validations if v["status"] == "ok"]),
                    "warnings": len(warnings),
                    "errors": len(errors),
                },
            }
        )
    else:
        print("\nConfiguration Validation")
        print("=" * 50)
        print()

        for validation in validations:
            status = validation["status"]
            field = validation["field"]
            message = validation["message"]

            if status == "ok":
                symbol = "[OK]"
            elif status == "warning":
                symbol = "[WARN]"
            else:
                symbol = "[ERROR]"

            print(f"{symbol:8} {field}")
            print(f"         {message}")
            print()

        print("=" * 50)
        print(f"Summary: {len(errors)} errors, {len(warnings)} warnings")

        if errors:
            print("\nConfiguration has errors that must be fixed.")
        elif warnings:
            print("\nConfiguration has warnings but is usable.")
        else:
            print("\nConfiguration is valid.")

    return 1 if errors else 0


def cmd_config(args: argparse.Namespace) -> int:
    """
    Execute config command dispatcher.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 = success, non-zero = error)
    """
    if args.config_action == "init":
        return cmd_config_init(args)
    if args.config_action == "show":
        return cmd_config_show(args)
    if args.config_action == "validate":
        return cmd_config_validate(args)
    logger.error(f"Unknown config action: {args.config_action}")
    return 1
