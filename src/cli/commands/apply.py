"""Apply command: apply categorization results to live mailboxes (Phase 5, Item 5.5).

Subcommands:
  folders  - Create folder/label structure from approved categories
  move     - Move emails to their categorized folders
  rules    - Deploy server-side inbox rules
  rollback - Undo recent apply operations
"""

import argparse
import time
from datetime import datetime, timezone
from pathlib import Path

from src.actions.action_logger import ActionLogger, RollbackResult
from src.cli.formatters import output_json
from src.utils.file_manager import load_json, save_json
from src.utils.logger import get_logger
from src.utils.paths import PathConfig

logger = get_logger(__name__)


# =============================================================================
# Source mapping helpers
# =============================================================================

# Map CLI --source values to the provider identifiers used by backends
_SOURCE_TO_PROVIDER = {
    "hotmail": "m365",
    "gmail": "gmail",
}


def _get_provider(source: str) -> str:
    """Map CLI source flag to provider identifier.

    Args:
        source: CLI source value (hotmail, gmail, both)

    Returns:
        Provider identifier (m365 or gmail). Defaults to m365.
    """
    return _SOURCE_TO_PROVIDER.get(source, "m365")


# =============================================================================
# Parser
# =============================================================================


def build_apply_parser(subparsers) -> argparse.ArgumentParser:
    """Add apply subparser to the CLI and return it."""
    apply_parser = subparsers.add_parser(
        "apply",
        help="Apply categorization results to live mailboxes",
        description="Apply categorization results to your mailbox: create folders, "
        "move emails, deploy server-side rules, or rollback recent changes.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Preview all folder creation (dry-run)
  %(prog)s folders --dry-run

  # Create folders for approved categories
  %(prog)s folders --yes

  # Preview email moves
  %(prog)s move --dry-run

  # Move emails to categorized folders
  %(prog)s move --yes

  # Preview rule deployment
  %(prog)s rules --dry-run

  # Deploy rules to server
  %(prog)s rules --yes

  # Rollback last apply operation
  %(prog)s rollback --yes

  # Rollback changes since a specific date
  %(prog)s rollback --since 2024-06-01T00:00:00 --yes

  # Use Gmail instead of Hotmail
  %(prog)s folders --source gmail --dry-run
        """,
    )

    apply_subparsers = apply_parser.add_subparsers(
        dest="apply_action", required=True, help="Apply action to perform"
    )

    # Shared arguments for all subcommands
    def _add_common_args(parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Preview changes without making any API calls",
        )
        parser.add_argument(
            "--source",
            choices=["hotmail", "gmail", "both"],
            default="hotmail",
            help="Email source/provider (default: hotmail)",
        )
        parser.add_argument(
            "--yes",
            "-y",
            action="store_true",
            default=False,
            help="Skip confirmation prompt (use with caution)",
        )
        parser.add_argument(
            "--user-email",
            type=str,
            default=None,
            help="User email for API authentication (default: from config)",
        )

    # apply folders
    folders_parser = apply_subparsers.add_parser(
        "folders",
        help="Create folder/label structure from approved categories",
        description="Create mailbox folders or Gmail labels for each approved category.",
    )
    _add_common_args(folders_parser)
    folders_parser.add_argument(
        "--categories",
        type=Path,
        help="Path to approved categories JSON (default: {output-dir}/approved_categories.json)",
    )

    # apply move
    move_parser = apply_subparsers.add_parser(
        "move",
        help="Move emails to their categorized folders",
        description="Move emails to the folders matching their assigned categories.",
    )
    _add_common_args(move_parser)
    move_parser.add_argument(
        "--report",
        type=Path,
        help="Path to categorization report JSON or classify report JSON "
        "(default: {output-dir}/categorization_report.json)",
    )
    move_parser.add_argument(
        "--rate-limit",
        type=float,
        default=0.25,
        help="Seconds between API requests (default: 0.25)",
    )

    # apply rules
    rules_parser = apply_subparsers.add_parser(
        "rules",
        help="Deploy server-side inbox rules",
        description="Deploy category rules as server-side inbox rules (M365 messageRules or "
        "Gmail filters).",
    )
    _add_common_args(rules_parser)
    rules_parser.add_argument(
        "--rules-file",
        type=Path,
        help="Path to rules JSON (default: {output-dir}/rules.json)",
    )

    # apply rollback
    rollback_parser = apply_subparsers.add_parser(
        "rollback",
        help="Rollback recent apply operations",
        description="Undo recent mailbox changes by replaying the action log in reverse.",
    )
    _add_common_args(rollback_parser)
    rollback_parser.add_argument(
        "--since",
        type=str,
        default=None,
        help="Only rollback actions after this datetime (ISO 8601 format, "
        "e.g. 2024-06-01T00:00:00)",
    )

    return apply_parser  # type: ignore[no-any-return]


# =============================================================================
# Confirmation prompt
# =============================================================================


def _confirm_action(action_description: str) -> bool:
    """Prompt the user for confirmation before a live mailbox operation.

    Args:
        action_description: Human-readable description of the action.

    Returns:
        True if user confirms, False otherwise.
    """
    print("\nWARNING: This will modify your live mailbox.")
    print(f"Action: {action_description}")
    try:
        answer = input("Proceed? [y/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return False
    return answer in ("y", "yes")


# =============================================================================
# Sub-command handlers
# =============================================================================


def _cmd_apply_folders(args: argparse.Namespace) -> int:
    """Execute apply folders: create mailbox folders from approved categories."""
    start_time = time.time()
    is_dry_run = getattr(args, "dry_run", False)
    is_json = getattr(args, "json", False)
    source = getattr(args, "source", "hotmail")

    logger.info("=== APPLY FOLDERS ===")

    # Load approved categories
    categories_path = getattr(args, "categories", None) or PathConfig.get_approved_categories_path()

    try:
        categories_data = load_json(categories_path)
        logger.info(f"Loaded {len(categories_data)} approved categories from {categories_path}")
    except FileNotFoundError:
        msg = (
            f"Approved categories file not found: {categories_path}. "
            f"Run the full pipeline ('extract' -> 'analyze' -> 'suggest' -> 'review') first, "
            f"or specify a valid path with --categories."
        )
        logger.error(msg)
        if is_json:
            output_json({"command": "apply folders", "status": "error", "error": msg})
        return 1
    except Exception as e:
        logger.error(f"Failed to load categories from {categories_path}: {e}")
        if is_json:
            output_json({"command": "apply folders", "status": "error", "error": str(e)})
        return 1

    # Extract category names
    category_names = [
        cat.get("category_name", "") for cat in categories_data if cat.get("category_name")
    ]

    if not category_names:
        msg = "No valid category names found in approved categories."
        logger.warning(msg)
        if is_json:
            output_json(
                {
                    "command": "apply folders",
                    "status": "success",
                    "folders_created": 0,
                    "dry_run": is_dry_run,
                }
            )
        else:
            print("No category names found. Nothing to create.")
        return 0

    # Confirmation for live operations
    if not is_dry_run and not getattr(args, "yes", False):
        confirmed = _confirm_action(
            f"Create {len(category_names)} folders/labels in your {source} mailbox"
        )
        if not confirmed:
            logger.info("Operation cancelled by user.")
            return 130

    # In dry-run mode, we don't need a real backend -- use FolderManager with dry_run=True
    # For live mode, we would instantiate a real backend (M365 or Gmail)
    from src.actions.folder_manager import FolderManager

    if is_dry_run:
        # Create a stub backend for dry-run
        class _DryRunBackend:
            def list_folders(self):
                return []

            def create_folder(self, name, *, parent_id=None):
                return f"dry-run-{name}"

        manager = FolderManager(_DryRunBackend(), dry_run=True)
    else:
        # Live mode: instantiate real backend
        if source == "hotmail":
            user_email = getattr(args, "user_email", None)
            if not user_email:
                app_config = getattr(args, "_app_config", None)
                if app_config:
                    user_email = getattr(app_config, "user_email", None)
            if not user_email:
                msg = (
                    "User email required for API authentication. "
                    "Pass --user-email or set user_email in config."
                )
                logger.error(msg)
                if is_json:
                    output_json(
                        {"command": "apply folders", "status": "error", "error": msg}
                    )
                return 1

            from src.actions.folder_manager import M365FolderBackend
            from src.extractors.graph_api_client import GraphAPIClient

            graph_client = GraphAPIClient(user_email=user_email)
            graph_client.authenticate()
            backend = M365FolderBackend(graph_client)
            manager = FolderManager(backend, dry_run=False)
        else:
            msg = f"Live folder creation for source '{source}' is not yet supported."
            logger.error(msg)
            if is_json:
                output_json({"command": "apply folders", "status": "error", "error": msg})
            return 1

    # Create folders
    folder_map, errors = manager.ensure_folders_with_errors(category_names)

    # Save folder_map.json for apply move to consume
    if folder_map and not is_dry_run:
        folder_map_path = PathConfig.get_folder_map_path()
        save_json(dict(folder_map.items()), folder_map_path)
        logger.info(f"Saved folder map to {folder_map_path}")

    duration = time.time() - start_time

    if is_json:
        output_json(
            {
                "command": "apply folders",
                "status": "success",
                "dry_run": is_dry_run,
                "source": source,
                "duration_seconds": round(duration, 2),
                "folders_created": len(folder_map),
                "errors": errors,
                "folders": dict(folder_map.items()),
            }
        )
    else:
        if is_dry_run:
            print(f"\n[DRY RUN] Would create {len(folder_map)} folders in {source}:")
        else:
            print(f"\nCreated {len(folder_map)} folders in {source}:")
        for name in sorted(folder_map):
            print(f"  - {name}")
        if errors:
            print(f"\nErrors ({len(errors)}):")
            for err in errors:
                print(f"  ! {err}")
        print(f"\nDuration: {duration:.2f}s")

    return 0


def _parse_moves_from_report(report_data: dict) -> list[tuple[str, str]]:
    """Parse move operations from either categorization report or classify report format.

    Categorization report format:
        { "categorizations": [ { "email_id": "...", "primary_category": { "category_name": "..." } } ] }

    Classify report format:
        { "categorized_emails": { "email_id": { "category": "...", "confidence": 0.9 } } }

    Args:
        report_data: Loaded JSON report dict

    Returns:
        List of (email_id, category_name) tuples
    """
    moves: list[tuple[str, str]] = []

    if "categorized_emails" in report_data and isinstance(
        report_data["categorized_emails"], dict
    ):
        # Classify report format: dict mapping email_id -> {category, confidence, source}
        for email_id, classification in report_data["categorized_emails"].items():
            category = classification.get("category", "")
            if category and email_id:
                moves.append((email_id, category))
    elif "categorizations" in report_data:
        # Categorization report format: list of {email_id, primary_category: {category_name}}
        for cat in report_data["categorizations"]:
            email_id = cat.get("email_id", "")
            primary = cat.get("primary_category")
            if primary and email_id:
                category_name = primary.get("category_name", "")
                if category_name:
                    moves.append((email_id, category_name))

    return moves


def _cmd_apply_move(args: argparse.Namespace) -> int:
    """Execute apply move: move emails to categorized folders."""
    start_time = time.time()
    is_dry_run = getattr(args, "dry_run", False)
    is_json = getattr(args, "json", False)
    source = getattr(args, "source", "hotmail")
    rate_limit = getattr(args, "rate_limit", 0.25)

    logger.info("=== APPLY MOVE ===")

    # Load categorization report
    report_path = getattr(args, "report", None) or PathConfig.get_categorization_report_path()

    try:
        report_data = load_json(report_path)
        logger.info(f"Loaded report from {report_path}")
    except FileNotFoundError:
        msg = (
            f"Report not found: {report_path}. "
            f"Run 'categorize' or 'classify' first, or specify a valid path with --report."
        )
        logger.error(msg)
        if is_json:
            output_json({"command": "apply move", "status": "error", "error": msg})
        return 1
    except Exception as e:
        logger.error(f"Failed to load report from {report_path}: {e}")
        if is_json:
            output_json({"command": "apply move", "status": "error", "error": str(e)})
        return 1

    # Detect format and extract moves
    moves = _parse_moves_from_report(report_data)
    total_emails = report_data.get("total_emails", len(moves))
    categorized_count = report_data.get("categorized_count", len(moves))

    if not moves:
        msg = "No categorized emails found in report."
        logger.warning(msg)
        if is_json:
            output_json(
                {
                    "command": "apply move",
                    "status": "success",
                    "moves_planned": 0,
                    "dry_run": is_dry_run,
                }
            )
        else:
            print(f"\n{msg}")
        return 0

    # Category breakdown
    from collections import Counter

    category_counts = Counter(cat for _, cat in moves)

    # Confirmation for live operations
    if not is_dry_run and not getattr(args, "yes", False):
        confirmed = _confirm_action(
            f"Move {len(moves)} emails to categorized folders in your {source} mailbox"
        )
        if not confirmed:
            logger.info("Operation cancelled by user.")
            return 130

    # Dry-run: show summary and category breakdown
    if is_dry_run:
        duration = time.time() - start_time
        if is_json:
            output_json(
                {
                    "command": "apply move",
                    "status": "success",
                    "dry_run": True,
                    "source": source,
                    "duration_seconds": round(duration, 2),
                    "total_emails": total_emails,
                    "categorized_count": categorized_count,
                    "moves_planned": len(moves),
                    "category_breakdown": dict(category_counts.most_common()),
                }
            )
        else:
            print(f"\n[DRY RUN] Email move summary ({source}):")
            print(f"  Total emails:      {total_emails}")
            print(f"  Categorized:       {categorized_count}")
            print(f"  Moves planned:     {len(moves)}")
            print("\n  Category breakdown:")
            for cat_name, count in category_counts.most_common():
                print(f"    {cat_name}: {count}")
            print("\nNo emails were moved. Use without --dry-run to execute.")
            print(f"\nDuration: {duration:.2f}s")
        return 0

    # Live mode: need authenticated backend
    if source != "hotmail":
        msg = f"Live email move for source '{source}' is not yet supported."
        logger.error(msg)
        if is_json:
            output_json({"command": "apply move", "status": "error", "error": msg})
        return 1

    user_email = getattr(args, "user_email", None)
    if not user_email:
        app_config = getattr(args, "_app_config", None)
        if app_config:
            user_email = getattr(app_config, "user_email", None)
    if not user_email:
        msg = (
            "User email required for API authentication. "
            "Pass --user-email or set user_email in config."
        )
        logger.error(msg)
        if is_json:
            output_json({"command": "apply move", "status": "error", "error": msg})
        return 1

    from src.actions.email_mover import EmailMover, M365MoveBackend
    from src.actions.folder_manager import FolderManager, M365FolderBackend
    from src.extractors.graph_api_client import GraphAPIClient

    graph_client = GraphAPIClient(user_email=user_email)
    graph_client.authenticate()

    # Load or create folder map (category_name -> folder_id)
    folder_map_path = PathConfig.get_folder_map_path()
    try:
        folder_map = load_json(folder_map_path)
        logger.info(f"Loaded folder map from {folder_map_path} ({len(folder_map)} folders)")
    except FileNotFoundError:
        logger.info("No folder map found, creating folders on-the-fly...")
        backend = M365FolderBackend(graph_client)
        fm = FolderManager(backend, dry_run=False)
        unique_categories = list(category_counts.keys())
        folder_map, folder_errors = fm.ensure_folders_with_errors(unique_categories)
        if folder_errors:
            for err in folder_errors:
                logger.warning(err)
        save_json(dict(folder_map.items()), folder_map_path)
        logger.info(f"Saved folder map to {folder_map_path}")

    # Map (email_id, category_name) -> (email_id, folder_id)
    move_ops: list[tuple[str, str]] = []
    skipped_no_folder = 0
    for email_id, category_name in moves:
        folder_id = folder_map.get(category_name)
        if folder_id:
            move_ops.append((email_id, folder_id))
        else:
            skipped_no_folder += 1
            logger.debug(f"No folder mapping for category '{category_name}', skipping {email_id}")

    if skipped_no_folder:
        logger.warning(
            f"Skipped {skipped_no_folder} emails with unmapped categories. "
            f"Run 'apply folders' first to create all folders."
        )

    # Execute moves
    move_backend = M365MoveBackend(graph_client)
    action_logger = ActionLogger()
    mover = EmailMover(
        move_backend,
        action_logger=action_logger,
        rate_limit_delay=rate_limit,
    )

    def _progress(completed: int, total: int) -> None:
        if completed % 100 == 0 or completed == total:
            print(f"  Progress: {completed}/{total} emails processed")

    print(f"\nMoving {len(move_ops)} emails (rate limit: {rate_limit}s/request)...")
    result = mover.move_batch(move_ops, progress_callback=_progress)

    duration = time.time() - start_time

    if is_json:
        output_json(
            {
                "command": "apply move",
                "status": "success" if result.all_succeeded else "partial",
                "dry_run": False,
                "source": source,
                "duration_seconds": round(duration, 2),
                "total_emails": total_emails,
                "moves_attempted": len(move_ops),
                "successful": result.successful_count,
                "failed": result.failed_count,
                "skipped": result.skipped_count,
                "skipped_no_folder": skipped_no_folder,
            }
        )
    else:
        print(f"\nMove results ({source}):")
        print(f"  Attempted:    {len(move_ops)}")
        print(f"  Successful:   {result.successful_count}")
        print(f"  Failed:       {result.failed_count}")
        print(f"  Skipped:      {result.skipped_count} (already in target)")
        if skipped_no_folder:
            print(f"  No folder:    {skipped_no_folder} (unmapped categories)")
        if result.failed_ids:
            print(f"\n  Failed email IDs ({len(result.failed_ids)}):")
            for fid in result.failed_ids[:10]:
                print(f"    - {fid[:60]}...")
            if len(result.failed_ids) > 10:
                print(f"    ... and {len(result.failed_ids) - 10} more")
        print(f"\nDuration: {duration:.2f}s")

    return 0 if result.all_succeeded else 1


def _cmd_apply_rules(args: argparse.Namespace) -> int:
    """Execute apply rules: deploy rules to server as inbox rules/filters."""
    start_time = time.time()
    is_dry_run = getattr(args, "dry_run", False)
    is_json = getattr(args, "json", False)
    source = getattr(args, "source", "hotmail")

    logger.info("=== APPLY RULES ===")

    # Load rules
    rules_path = getattr(args, "rules_file", None) or PathConfig.get_rules_path()

    try:
        rules_data = load_json(rules_path)
        logger.info(f"Loaded rules from {rules_path}")
    except FileNotFoundError:
        msg = (
            f"Rules file not found: {rules_path}. "
            f"Run 'rules generate' first, or specify a valid path with --rules-file."
        )
        logger.error(msg)
        if is_json:
            output_json({"command": "apply rules", "status": "error", "error": msg})
        return 1
    except Exception as e:
        logger.error(f"Failed to load rules from {rules_path}: {e}")
        if is_json:
            output_json({"command": "apply rules", "status": "error", "error": str(e)})
        return 1

    # Parse RuleSet
    from src.models.rule import RuleSet

    try:
        rule_set = RuleSet(**rules_data)
    except Exception as e:
        msg = f"Invalid rules file format: {e}"
        logger.error(msg)
        if is_json:
            output_json({"command": "apply rules", "status": "error", "error": msg})
        return 1

    # Determine provider from source
    provider = _get_provider(source)

    # Confirmation for live operations
    if not is_dry_run and not getattr(args, "yes", False):
        confirmed = _confirm_action(
            f"Deploy {rule_set.rule_count} rules to your {source} mailbox as server-side rules"
        )
        if not confirmed:
            logger.info("Operation cancelled by user.")
            return 130

    # Deploy via RuleDeployer (always dry_run for now unless --yes)
    from src.actions.rule_deployer import RuleDeployer

    deployer = RuleDeployer(source=provider, dry_run=is_dry_run)

    # Validate rules for target platform
    validation_errors = deployer.validate_rules(rule_set)
    if validation_errors:
        logger.warning(f"Rule validation found {len(validation_errors)} issues:")
        for err in validation_errors:
            logger.warning(f"  - {err}")

    # Deploy (dry_run or live)
    deployment_result = deployer.deploy_rules(rule_set, access_token=None)

    duration = time.time() - start_time

    if is_json:
        output_json(
            {
                "command": "apply rules",
                "status": "success",
                "dry_run": is_dry_run,
                "source": source,
                "provider": provider,
                "duration_seconds": round(duration, 2),
                "total_rules": deployment_result.total,
                "deployed": deployment_result.succeeded,
                "failed": deployment_result.failed,
                "skipped": deployment_result.skipped,
                "validation_warnings": validation_errors,
            }
        )
    else:
        mode = "[DRY RUN] " if is_dry_run else ""
        print(f"\n{mode}Rule deployment summary ({source} / {provider}):")
        print(f"  Total rules:   {deployment_result.total}")
        print(f"  Deployed:      {deployment_result.succeeded}")
        print(f"  Failed:        {deployment_result.failed}")
        print(f"  Skipped:       {deployment_result.skipped}")
        if validation_errors:
            print(f"\n  Validation warnings ({len(validation_errors)}):")
            for err in validation_errors:
                print(f"    - {err}")
        if deployment_result.failures:
            print("\n  Failures:")
            for rule_id, error in deployment_result.failures.items():
                print(f"    - {rule_id}: {error}")
        print(f"\nDuration: {duration:.2f}s")

    return 0


def _cmd_apply_rollback(args: argparse.Namespace) -> int:
    """Execute apply rollback: undo recent apply operations."""
    is_json = getattr(args, "json", False)
    since_str = getattr(args, "since", None)

    logger.info("=== APPLY ROLLBACK ===")

    # Parse --since datetime if provided
    since_dt: datetime | None = None
    if since_str:
        try:
            since_dt = datetime.fromisoformat(since_str)
            # Ensure timezone-aware
            if since_dt.tzinfo is None:
                since_dt = since_dt.replace(tzinfo=timezone.utc)
        except ValueError:
            msg = (
                f"Invalid --since format: '{since_str}'. "
                f"Use ISO 8601 format (e.g. 2024-06-01T00:00:00)."
            )
            logger.error(msg)
            if is_json:
                output_json({"command": "apply rollback", "status": "error", "error": msg})
            return 1

    # Get rollback-eligible actions from action log
    action_logger = ActionLogger()
    eligible_actions = action_logger.get_rollback_actions(since=since_dt)

    if not eligible_actions:
        msg = "No eligible actions to rollback."
        if since_str:
            msg += f" (since {since_str})"
        logger.info(msg)
        if is_json:
            output_json(
                {
                    "command": "apply rollback",
                    "status": "success",
                    "eligible_actions": 0,
                    "message": msg,
                }
            )
        else:
            print(f"\n{msg}")
        return 0

    # Show what would be rolled back
    logger.info(f"Found {len(eligible_actions)} eligible actions for rollback")

    # Confirmation for rollback
    if not getattr(args, "yes", False) and not getattr(args, "dry_run", False):
        print(f"\nActions to rollback ({len(eligible_actions)}):")
        for action in eligible_actions[:10]:
            print(
                f"  - {action.action_type.value}: {action.target_id} ({action.timestamp.isoformat()})"
            )
        if len(eligible_actions) > 10:
            print(f"  ... and {len(eligible_actions) - 10} more")

        confirmed = _confirm_action(f"Rollback {len(eligible_actions)} actions")
        if not confirmed:
            logger.info("Rollback cancelled by user.")
            return 130

    # Execute rollback
    result: RollbackResult = action_logger.replay_rollback(eligible_actions)

    if is_json:
        output_json(
            {
                "command": "apply rollback",
                "status": "success" if result.all_succeeded else "partial",
                "total_actions": result.total_actions,
                "successful": result.successful,
                "failed": result.failed,
                "skipped": result.skipped,
                "errors": result.errors,
            }
        )
    else:
        print("\nRollback results:")
        print(f"  Total actions:  {result.total_actions}")
        print(f"  Successful:     {result.successful}")
        print(f"  Failed:         {result.failed}")
        print(f"  Skipped:        {result.skipped}")
        if result.errors:
            print("\n  Errors:")
            for err in result.errors:
                print(f"    - {err}")

    return 0 if result.all_succeeded else 1


# =============================================================================
# Top-level dispatcher
# =============================================================================


def cmd_apply(args: argparse.Namespace) -> int:
    """
    Execute apply command dispatcher.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 = success, non-zero = error)
    """
    action = getattr(args, "apply_action", None)

    if action == "folders":
        return _cmd_apply_folders(args)
    if action == "move":
        return _cmd_apply_move(args)
    if action == "rules":
        return _cmd_apply_rules(args)
    if action == "rollback":
        return _cmd_apply_rollback(args)

    logger.error(f"Unknown apply action: {action}")
    return 1
