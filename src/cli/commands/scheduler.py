"""Scheduler command: setup, run, status, and disable scheduled processing."""

import argparse

from src.cli.formatters import output_json
from src.utils.logger import get_logger

logger = get_logger(__name__)


def build_scheduler_parser(subparsers) -> argparse.ArgumentParser:
    """Add scheduler subparser to the CLI and return it."""
    scheduler_parser = subparsers.add_parser(
        "scheduler",
        help="Manage scheduled automated processing (setup, run, status, disable)",
        description="Set up automated extraction, analysis, and categorization "
        "using platform-native scheduling (Windows Task Scheduler / crontab).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Set up scheduled processing (daily at configured time)
  %(prog)s setup

  # Manually trigger a scheduled run
  %(prog)s run

  # Check current schedule status
  %(prog)s status

  # Disable scheduled processing
  %(prog)s disable
        """,
    )

    scheduler_subparsers = scheduler_parser.add_subparsers(
        dest="scheduler_action", required=True, help="Scheduler action to perform"
    )

    # scheduler setup
    scheduler_subparsers.add_parser(
        "setup",
        help="Register the scheduled task with the OS scheduler",
        description="Set up automated scheduled processing. On Windows, registers a "
        "Task Scheduler task. On Linux/macOS, installs a crontab entry.",
    )

    # scheduler run
    scheduler_subparsers.add_parser(
        "run",
        help="Manually trigger a scheduled run",
        description="Run incremental extraction, analysis, and categorization now. "
        "This is the same operation the scheduler executes automatically.",
    )

    # scheduler status
    scheduler_subparsers.add_parser(
        "status",
        help="Show current schedule status (next run, last run, enabled/disabled)",
        description="Display the current state of the scheduler including whether "
        "it is enabled, when it last ran, and when the next run is scheduled.",
    )

    # scheduler disable
    scheduler_subparsers.add_parser(
        "disable",
        help="Disable scheduled processing",
        description="Remove the scheduled task from the OS scheduler and mark "
        "scheduling as disabled.",
    )

    return scheduler_parser  # type: ignore[no-any-return]


# =============================================================================
# Sub-command handlers
# =============================================================================


def _cmd_scheduler_setup(args: argparse.Namespace) -> int:
    """Execute scheduler setup: register the scheduled task."""
    from src.automation.scheduler import Scheduler
    from src.config.loader import load_config

    logger.info("=== SCHEDULER SETUP ===")

    try:
        config = load_config(config_path=getattr(args, "config", None))
        scheduler = Scheduler(config=config.scheduler)
    except Exception:
        scheduler = Scheduler()

    status = scheduler.setup()

    if getattr(args, "json", False):
        output_json(
            {
                "command": "scheduler setup",
                "status": "success" if status.enabled else "error",
                "schedule": status.model_dump(mode="json"),
            }
        )
    else:
        if status.enabled:
            logger.info(
                f"Scheduler enabled: running every {status.interval_hours} hours. "
                f"Next run: {status.next_run}"
            )
        else:
            logger.error("Scheduler setup failed. Check logs for details.")

    return 0 if status.enabled else 1


def _cmd_scheduler_run(args: argparse.Namespace) -> int:
    """Execute scheduler run: manually trigger a scheduled run."""
    from src.automation.scheduler import Scheduler
    from src.config.loader import load_config

    logger.info("=== SCHEDULER RUN ===")

    try:
        config = load_config(config_path=getattr(args, "config", None))
        scheduler = Scheduler(config=config.scheduler)
    except Exception:
        scheduler = Scheduler()

    def _progress(msg: str) -> None:
        if not getattr(args, "json", False):
            logger.info(msg)

    result = scheduler.run(progress_callback=_progress)

    if result is not None:
        if getattr(args, "json", False):
            output_json(
                {
                    "command": "scheduler run",
                    "status": "success",
                    "result": {
                        "new_email_count": result.new_email_count,
                        "merged_corpus_size": result.merged_corpus_size,
                        "new_categorizations": len(result.new_categorizations),
                        "processing_time": result.processing_time,
                    },
                }
            )
        else:
            logger.info(
                f"Scheduled run complete: {result.new_email_count} new emails, "
                f"{result.merged_corpus_size} total, "
                f"{result.processing_time:.1f}s elapsed"
            )
        return 0
    if getattr(args, "json", False):
        output_json(
            {
                "command": "scheduler run",
                "status": "error",
                "error": "Scheduled run failed. Check logs for details.",
            }
        )
    else:
        logger.error("Scheduled run failed. Check logs for details.")
    return 1


def _cmd_scheduler_status(args: argparse.Namespace) -> int:
    """Execute scheduler status: show current schedule state."""
    from src.automation.scheduler import Scheduler
    from src.config.loader import load_config

    try:
        config = load_config(config_path=getattr(args, "config", None))
        scheduler = Scheduler(config=config.scheduler)
    except Exception:
        scheduler = Scheduler()

    status = scheduler.get_status()

    if getattr(args, "json", False):
        output_json(
            {
                "command": "scheduler status",
                "status": "success",
                "schedule": status.model_dump(mode="json"),
            }
        )
    else:
        print()
        print("=" * 50)
        print("SCHEDULER STATUS")
        print("=" * 50)
        print(f"  Enabled:        {'Yes' if status.enabled else 'No'}")
        print(f"  Interval:       Every {status.interval_hours} hours")
        print(f"  Next run:       {status.next_run or 'Not scheduled'}")
        print(f"  Last run:       {status.last_run or 'Never'}")
        print(f"  Last result:    {status.last_result or 'N/A'}")
        print("=" * 50)
        print()

    return 0


def _cmd_scheduler_disable(args: argparse.Namespace) -> int:
    """Execute scheduler disable: remove the scheduled task."""
    from src.automation.scheduler import Scheduler
    from src.config.loader import load_config

    logger.info("=== SCHEDULER DISABLE ===")

    try:
        config = load_config(config_path=getattr(args, "config", None))
        scheduler = Scheduler(config=config.scheduler)
    except Exception:
        scheduler = Scheduler()

    status = scheduler.disable()

    if getattr(args, "json", False):
        output_json(
            {
                "command": "scheduler disable",
                "status": "success",
                "schedule": status.model_dump(mode="json"),
            }
        )
    else:
        logger.info("Scheduler disabled. Scheduled task removed.")

    return 0


# =============================================================================
# Top-level dispatcher
# =============================================================================


def cmd_scheduler(args: argparse.Namespace) -> int:
    """Execute scheduler command dispatcher.

    Args:
        args: Parsed command-line arguments.

    Returns:
        Exit code (0 = success, non-zero = error).
    """
    action = getattr(args, "scheduler_action", None)

    if action == "setup":
        return _cmd_scheduler_setup(args)
    if action == "run":
        return _cmd_scheduler_run(args)
    if action == "status":
        return _cmd_scheduler_status(args)
    if action == "disable":
        return _cmd_scheduler_disable(args)

    logger.error(f"Unknown scheduler action: {action}")
    return 1
