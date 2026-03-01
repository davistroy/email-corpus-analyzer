"""
Migrate command: import JSON/JSONL data into SQLite database.

Phase 3, Work Item 3.4.

One-time migration tool that imports existing data files:
- email_corpus.json → emails table
- decisions.jsonl → decision_log table
- action_log.jsonl → action_log table

Source files are read but NOT deleted after migration.
"""

import argparse
import json
from pathlib import Path

from src.cli.formatters import output_json
from src.storage.database import Database
from src.storage.migration import JsonToSqliteMigrator
from src.utils.logger import get_logger
from src.utils.paths import PathConfig

logger = get_logger(__name__)


def build_migrate_parser(subparsers) -> argparse.ArgumentParser:
    """Add migrate subparser to the CLI and return it."""
    migrate_parser = subparsers.add_parser(
        "migrate",
        help="Migrate JSON data to SQLite database",
        description=(
            "One-time migration of existing JSON/JSONL data files into the SQLite database. "
            "Imports email corpus, decision history, and action audit log. "
            "Source files are NOT deleted after migration. Safe to run multiple times."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Migrate using default paths
  %(prog)s

  # Migrate specific corpus file
  %(prog)s --corpus /path/to/email_corpus.json

  # Migrate to a specific database
  %(prog)s --db-path /path/to/database.db

  # Preview without writing
  %(prog)s --dry-run

  # JSON output for automation
  %(prog)s --json
        """,
    )

    migrate_parser.add_argument(
        "--corpus",
        type=Path,
        help="Path to email_corpus.json (default: {output-dir}/email_corpus.json)",
    )
    migrate_parser.add_argument(
        "--decisions",
        type=Path,
        help="Path to decisions.jsonl (default: ~/.email-analyzer/decisions.jsonl)",
    )
    migrate_parser.add_argument(
        "--actions",
        type=Path,
        help="Path to action_log.jsonl (default: ~/.email-analyzer/action_log.jsonl)",
    )
    migrate_parser.add_argument(
        "--db-path",
        type=Path,
        help="Path to SQLite database file (default: ~/.email-analyzer/email_analyzer.db)",
    )
    migrate_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would be migrated without writing to the database",
    )

    return migrate_parser  # type: ignore[no-any-return]


def cmd_migrate(args: argparse.Namespace) -> int:
    """
    Execute the migrate command.

    Args:
        args: Parsed command-line arguments.

    Returns:
        Exit code (0 = success, non-zero = error).
    """
    # Resolve paths
    corpus_path = args.corpus or PathConfig.get_corpus_path()
    decisions_path = args.decisions or (Path.home() / ".email-analyzer" / "decisions.jsonl")
    actions_path = args.actions or (Path.home() / ".email-analyzer" / "action_log.jsonl")
    db_path = getattr(args, "db_path", None) or Database.default_path()

    is_json = getattr(args, "json", False)
    is_dry_run = getattr(args, "dry_run", False)

    # --- Dry-run mode ---
    if is_dry_run:
        return _handle_dry_run(corpus_path, decisions_path, actions_path, is_json)

    # --- Real migration ---
    try:
        with Database(db_path) as db:
            migrator = JsonToSqliteMigrator(db)

            if not is_json:
                print(f"\nMigrating data to SQLite: {db_path}")
                print("-" * 50)

            def on_progress(stage: str, current: int, total: int) -> None:
                if not is_json:
                    print(f"  {stage}: {current}/{total}", end="\r", flush=True)

            result = migrator.migrate_all(
                corpus_path=corpus_path,
                decisions_path=decisions_path,
                actions_path=actions_path,
                progress_callback=on_progress,
            )

        if is_json:
            output_json(
                {
                    "command": "migrate",
                    "status": "success",
                    "db_path": str(db_path),
                    "emails_migrated": result.emails_migrated,
                    "decisions_migrated": result.decisions_migrated,
                    "actions_migrated": result.actions_migrated,
                    "emails_skipped": result.emails_skipped,
                    "decisions_skipped": result.decisions_skipped,
                    "actions_skipped": result.actions_skipped,
                    "total_migrated": result.total_migrated,
                    "total_skipped": result.total_skipped,
                    "warnings": result.warnings,
                }
            )
        else:
            print()
            print("\nMigration complete!")
            print(
                f"  Emails:    {result.emails_migrated} migrated"
                + (f", {result.emails_skipped} skipped" if result.emails_skipped else "")
            )
            print(
                f"  Decisions: {result.decisions_migrated} migrated"
                + (f", {result.decisions_skipped} skipped" if result.decisions_skipped else "")
            )
            print(
                f"  Actions:   {result.actions_migrated} migrated"
                + (f", {result.actions_skipped} skipped" if result.actions_skipped else "")
            )
            print(f"  Total:     {result.total_migrated} items migrated")
            if result.has_warnings:
                print(f"\nWarnings ({len(result.warnings)}):")
                for warning in result.warnings:
                    print(f"  - {warning}")
            print(f"\nDatabase: {db_path}")
            print()

        return 0

    except FileNotFoundError as e:
        logger.error(str(e))
        if is_json:
            output_json({"command": "migrate", "status": "error", "error": str(e)})
        return 1
    except Exception as e:
        logger.error("Migration failed: %s", e, exc_info=True)
        if is_json:
            output_json({"command": "migrate", "status": "error", "error": str(e)})
        return 1


def _handle_dry_run(
    corpus_path: Path,
    decisions_path: Path,
    actions_path: Path,
    is_json: bool,
) -> int:
    """Handle --dry-run by reporting what would be migrated without writing."""
    email_count = 0
    decision_count = 0
    action_count = 0

    # Count corpus emails
    if corpus_path.exists():
        try:
            with open(corpus_path, encoding="utf-8") as f:
                corpus_data = json.load(f)
            email_count = len(corpus_data.get("emails", []))
        except Exception as e:
            logger.warning("Could not read corpus file: %s", e)

    # Count decision lines
    if decisions_path.exists():
        try:
            with open(decisions_path, encoding="utf-8") as f:
                decision_count = sum(1 for line in f if line.strip())
        except Exception as e:
            logger.warning("Could not read decisions file: %s", e)

    # Count action lines
    if actions_path.exists():
        try:
            with open(actions_path, encoding="utf-8") as f:
                action_count = sum(1 for line in f if line.strip())
        except Exception as e:
            logger.warning("Could not read actions file: %s", e)

    if is_json:
        output_json(
            {
                "command": "migrate",
                "status": "dry_run",
                "would_migrate": {
                    "emails": email_count,
                    "decisions": decision_count,
                    "actions": action_count,
                    "total": email_count + decision_count + action_count,
                },
                "sources": {
                    "corpus": str(corpus_path),
                    "decisions": str(decisions_path),
                    "actions": str(actions_path),
                },
            }
        )
    else:
        print("\nDry-run: previewing migration (no data will be written)")
        print("-" * 50)
        print(f"  Corpus:    {corpus_path}")
        print(
            f"             {email_count} emails to migrate"
            + (" (file not found)" if not corpus_path.exists() else "")
        )
        print(f"  Decisions: {decisions_path}")
        print(
            f"             {decision_count} decisions to migrate"
            + (" (file not found)" if not decisions_path.exists() else "")
        )
        print(f"  Actions:   {actions_path}")
        print(
            f"             {action_count} actions to migrate"
            + (" (file not found)" if not actions_path.exists() else "")
        )
        print(f"\n  Total: {email_count + decision_count + action_count} items would be migrated")
        print()

    return 0
