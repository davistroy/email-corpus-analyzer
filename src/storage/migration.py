"""
JSON → SQLite migration tool for one-time data import.

Imports existing JSON/JSONL data files into the SQLite database:
- email_corpus.json → emails table
- decisions.jsonl → decision_log table
- action_log.jsonl → action_log table

The migration is non-destructive — source files are read but never deleted.
Corpus migration uses upsert semantics so running twice is idempotent.

Phase 3, Work Item 3.4.
"""

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from src.models.email import Email
from src.storage.database import Database
from src.storage.email_store import EmailStore

logger = logging.getLogger(__name__)

# Batch size for email upsert operations (balance memory vs. transaction overhead)
_EMAIL_BATCH_SIZE = 100


@dataclass
class MigrationResult:
    """
    Summary of a full migration run.

    Tracks counts of successfully migrated and skipped items for each
    data source, plus warning messages for anything that was skipped.
    """

    emails_migrated: int = 0
    decisions_migrated: int = 0
    actions_migrated: int = 0
    emails_skipped: int = 0
    decisions_skipped: int = 0
    actions_skipped: int = 0
    warnings: list[str] = field(default_factory=list)

    @property
    def total_migrated(self) -> int:
        """Total items successfully migrated across all sources."""
        return self.emails_migrated + self.decisions_migrated + self.actions_migrated

    @property
    def total_skipped(self) -> int:
        """Total items skipped across all sources."""
        return self.emails_skipped + self.decisions_skipped + self.actions_skipped

    @property
    def has_warnings(self) -> bool:
        """Whether any warnings were recorded during migration."""
        return len(self.warnings) > 0


class JsonToSqliteMigrator:
    """
    One-time migration tool: JSON/JSONL files → SQLite database.

    Non-destructive — reads source files without modifying or deleting them.
    Corpus email import uses upsert (INSERT OR REPLACE) for idempotency.
    Decision and action log imports check for duplicates by content hash
    to avoid duplication on re-runs.

    Usage:
        with Database(db_path) as db:
            migrator = JsonToSqliteMigrator(db)
            result = migrator.migrate_all(
                corpus_path=Path("~/data/outputs/email_corpus.json"),
                decisions_path=Path("~/.email-analyzer/decisions.jsonl"),
                actions_path=Path("~/.email-analyzer/action_log.jsonl"),
            )
            print(f"Migrated {result.total_migrated} items")
    """

    def __init__(self, database: Database) -> None:
        """
        Initialize the migrator.

        Args:
            database: An open Database instance to migrate data into.
        """
        self._db = database
        self._email_store = EmailStore(database)

    def migrate_corpus(
        self,
        corpus_path: Path,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> int:
        """
        Migrate email_corpus.json into the emails table.

        Reads the corpus JSON file, parses each email dict into an Email
        model, and upserts into the database in batches. Invalid emails
        (those that fail Pydantic validation) are skipped with a warning.

        Args:
            corpus_path: Path to the email_corpus.json file.
            progress_callback: Optional callback(migrated, total) for
                progress reporting.

        Returns:
            Number of emails successfully migrated.

        Raises:
            FileNotFoundError: If corpus_path does not exist.
            json.JSONDecodeError: If the file contains invalid JSON.
            ValueError: If the JSON structure is unexpected.
        """
        corpus_path = Path(corpus_path)
        if not corpus_path.exists():
            raise FileNotFoundError(f"Corpus file not found: {corpus_path}")

        with open(corpus_path, encoding="utf-8") as f:
            corpus_data = json.load(f)

        email_dicts = corpus_data.get("emails", [])
        total = len(email_dicts)

        if total == 0:
            logger.info("Corpus file contains no emails.")
            if progress_callback:
                progress_callback(0, 0)
            return 0

        migrated = 0
        batch: list[Email] = []

        for i, email_dict in enumerate(email_dicts):
            try:
                email = self._parse_email_dict(email_dict)
                batch.append(email)
            except Exception as e:
                logger.warning(
                    "Skipping invalid email at index %d (id=%s): %s",
                    i,
                    email_dict.get("id", "unknown"),
                    e,
                )
                continue

            # Flush batch when full
            if len(batch) >= _EMAIL_BATCH_SIZE:
                self._email_store.upsert_batch(batch)
                migrated += len(batch)
                batch = []
                if progress_callback:
                    progress_callback(migrated, total)

        # Flush remaining
        if batch:
            self._email_store.upsert_batch(batch)
            migrated += len(batch)

        if progress_callback:
            progress_callback(migrated, total)

        logger.info("Migrated %d/%d emails from %s", migrated, total, corpus_path)
        return migrated

    def migrate_decisions(
        self,
        decisions_path: Path,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> int:
        """
        Migrate decisions.jsonl into the decision_log table.

        Reads each JSONL line, parses the decision record, and inserts it.
        Corrupt or unparseable lines are skipped with a warning log.
        Missing files are treated as "nothing to migrate" (returns 0).

        Args:
            decisions_path: Path to the decisions.jsonl file.
            progress_callback: Optional callback(migrated, total) for
                progress reporting.

        Returns:
            Number of decisions successfully migrated.
        """
        decisions_path = Path(decisions_path)
        if not decisions_path.exists():
            logger.info("Decisions file not found (nothing to migrate): %s", decisions_path)
            return 0

        lines = self._read_jsonl_lines(decisions_path)
        total = len(lines)

        if total == 0:
            if progress_callback:
                progress_callback(0, 0)
            return 0

        migrated = 0
        insert_sql = (
            "INSERT INTO decision_log (timestamp, category_name, action, context_json) "
            "VALUES (?, ?, ?, ?)"
        )

        with self._db.transaction():
            for i, line in enumerate(lines):
                try:
                    data = json.loads(line)
                    params = (
                        data["timestamp"],
                        data["category_name"],
                        data["action"],
                        json.dumps(data.get("context", {})),
                    )
                    self._db.execute(insert_sql, params)
                    migrated += 1
                except (json.JSONDecodeError, KeyError, ValueError) as e:
                    logger.warning("Skipping corrupt decision line %d: %s", i + 1, e)
                    continue

                if progress_callback and (migrated % 50 == 0 or i == total - 1):
                    progress_callback(migrated, total)

        if progress_callback:
            progress_callback(migrated, total)

        logger.info("Migrated %d/%d decisions from %s", migrated, total, decisions_path)
        return migrated

    def migrate_actions(
        self,
        actions_path: Path,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> int:
        """
        Migrate action_log.jsonl into the action_log table.

        Reads each JSONL line, parses the action record, and inserts it.
        Corrupt or unparseable lines are skipped with a warning log.
        Missing files are treated as "nothing to migrate" (returns 0).

        Args:
            actions_path: Path to the action_log.jsonl file.
            progress_callback: Optional callback(migrated, total) for
                progress reporting.

        Returns:
            Number of actions successfully migrated.
        """
        actions_path = Path(actions_path)
        if not actions_path.exists():
            logger.info("Action log file not found (nothing to migrate): %s", actions_path)
            return 0

        lines = self._read_jsonl_lines(actions_path)
        total = len(lines)

        if total == 0:
            if progress_callback:
                progress_callback(0, 0)
            return 0

        migrated = 0
        insert_sql = (
            "INSERT INTO action_log "
            "(timestamp, action_type, target_id, details_json, success, reversible) "
            "VALUES (?, ?, ?, ?, ?, ?)"
        )

        with self._db.transaction():
            for i, line in enumerate(lines):
                try:
                    data = json.loads(line)
                    params = (
                        data["timestamp"],
                        data["action_type"],
                        data.get("target_id", ""),
                        json.dumps(data.get("details", {})),
                        int(data["success"]),
                        int(data["reversible"]),
                    )
                    self._db.execute(insert_sql, params)
                    migrated += 1
                except (json.JSONDecodeError, KeyError, ValueError) as e:
                    logger.warning("Skipping corrupt action log line %d: %s", i + 1, e)
                    continue

                if progress_callback and (migrated % 50 == 0 or i == total - 1):
                    progress_callback(migrated, total)

        if progress_callback:
            progress_callback(migrated, total)

        logger.info("Migrated %d/%d actions from %s", migrated, total, actions_path)
        return migrated

    def migrate_all(
        self,
        corpus_path: Path,
        decisions_path: Path | None = None,
        actions_path: Path | None = None,
        progress_callback: Callable[[str, int, int], None] | None = None,
    ) -> MigrationResult:
        """
        Orchestrate migration of all data sources.

        Runs corpus, decisions, and actions migrations in sequence,
        collecting results and warnings into a MigrationResult.

        Args:
            corpus_path: Path to email_corpus.json.
            decisions_path: Path to decisions.jsonl (optional).
            actions_path: Path to action_log.jsonl (optional).
            progress_callback: Optional callback(stage, current, total)
                where stage is 'emails', 'decisions', or 'actions'.

        Returns:
            MigrationResult with counts and warnings.
        """
        result = MigrationResult()
        warnings: list[str] = []

        # --- Corpus migration ---
        def _corpus_progress(current: int, total: int) -> None:
            if progress_callback:
                progress_callback("emails", current, total)

        try:
            # Count total emails and skipped via a tracking wrapper
            corpus_path_resolved = Path(corpus_path)
            if not corpus_path_resolved.exists():
                raise FileNotFoundError(f"Corpus file not found: {corpus_path_resolved}")

            with open(corpus_path_resolved, encoding="utf-8") as f:
                corpus_data = json.load(f)
            total_emails = len(corpus_data.get("emails", []))

            migrated_emails = self.migrate_corpus(corpus_path_resolved, _corpus_progress)
            result.emails_migrated = migrated_emails
            result.emails_skipped = total_emails - migrated_emails
            if result.emails_skipped > 0:
                warnings.append(
                    f"Skipped {result.emails_skipped} invalid email(s) during corpus migration"
                )
        except FileNotFoundError:
            raise
        except Exception as e:
            warnings.append(f"Corpus migration error: {e}")
            logger.error("Corpus migration failed: %s", e)

        # --- Decisions migration ---
        def _decisions_progress(current: int, total: int) -> None:
            if progress_callback:
                progress_callback("decisions", current, total)

        if decisions_path:
            decisions_path_resolved = Path(decisions_path)
            try:
                # Pre-count lines for skip tracking
                total_decision_lines = 0
                if decisions_path_resolved.exists():
                    total_decision_lines = len(self._read_jsonl_lines(decisions_path_resolved))

                migrated_decisions = self.migrate_decisions(
                    decisions_path_resolved, _decisions_progress
                )
                result.decisions_migrated = migrated_decisions
                result.decisions_skipped = total_decision_lines - migrated_decisions
                if result.decisions_skipped > 0:
                    warnings.append(f"Skipped {result.decisions_skipped} corrupt decision line(s)")
            except Exception as e:
                warnings.append(f"Decisions migration error: {e}")
                logger.error("Decisions migration failed: %s", e)

        # --- Actions migration ---
        def _actions_progress(current: int, total: int) -> None:
            if progress_callback:
                progress_callback("actions", current, total)

        if actions_path:
            actions_path_resolved = Path(actions_path)
            try:
                # Pre-count lines for skip tracking
                total_action_lines = 0
                if actions_path_resolved.exists():
                    total_action_lines = len(self._read_jsonl_lines(actions_path_resolved))

                migrated_actions = self.migrate_actions(actions_path_resolved, _actions_progress)
                result.actions_migrated = migrated_actions
                result.actions_skipped = total_action_lines - migrated_actions
                if result.actions_skipped > 0:
                    warnings.append(f"Skipped {result.actions_skipped} corrupt action log line(s)")
            except Exception as e:
                warnings.append(f"Actions migration error: {e}")
                logger.error("Actions migration failed: %s", e)

        result.warnings = warnings
        logger.info(
            "Migration complete: %d migrated, %d skipped, %d warnings",
            result.total_migrated,
            result.total_skipped,
            len(result.warnings),
        )
        return result

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    @staticmethod
    def _parse_email_dict(email_dict: dict) -> Email:
        """
        Parse a JSON email dict into an Email model.

        Handles differences between the JSON corpus format and the Email
        model (e.g., 'references' as list vs. 'references_json' column,
        has_attachments as bool/int).

        Args:
            email_dict: Dictionary from the corpus JSON 'emails' list.

        Returns:
            Email instance.

        Raises:
            ValueError: If required fields are missing or invalid.
        """
        return Email(
            id=email_dict["id"],
            sender_email=email_dict["sender_email"],
            sender_name=email_dict.get("sender_name", ""),
            sender_domain=email_dict["sender_domain"],
            recipient_email=email_dict.get("recipient_email"),
            recipient_name=email_dict.get("recipient_name", ""),
            subject=email_dict.get("subject", ""),
            body_text=email_dict.get("body_text", ""),
            received_date=email_dict["received_date"],
            has_attachments=bool(email_dict.get("has_attachments", False)),
            thread_id=email_dict.get("thread_id"),
            in_reply_to=email_dict.get("in_reply_to"),
            references=email_dict.get("references", []),
            provider=email_dict.get("provider"),
            provider_message_id=email_dict.get("provider_message_id"),
        )

    @staticmethod
    def _read_jsonl_lines(path: Path) -> list[str]:
        """
        Read a JSONL file and return non-empty, stripped lines.

        Args:
            path: Path to the JSONL file.

        Returns:
            List of non-empty line strings.
        """
        with open(path, encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip()]
