"""
SQLite database connection manager with schema creation and migration versioning.

Provides the Database class for managing SQLite connections with WAL mode,
schema creation, version tracking, and transaction management.

Phase 3, Work Item 3.1.
"""

import logging
import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from src.exceptions import DatabaseSchemaError, StorageError

logger = logging.getLogger(__name__)

# Current schema version — increment when schema changes
CURRENT_SCHEMA_VERSION = 1

# SQL statements for schema creation
_SCHEMA_SQL = """
-- Email messages extracted from providers
CREATE TABLE IF NOT EXISTS emails (
    id TEXT PRIMARY KEY,
    sender_email TEXT NOT NULL,
    sender_name TEXT NOT NULL DEFAULT '',
    sender_domain TEXT NOT NULL,
    recipient_email TEXT,
    recipient_name TEXT NOT NULL DEFAULT '',
    subject TEXT NOT NULL DEFAULT '',
    body_text TEXT NOT NULL DEFAULT '',
    received_date TEXT NOT NULL,
    has_attachments INTEGER NOT NULL DEFAULT 0,
    thread_id TEXT,
    in_reply_to TEXT,
    references_json TEXT,
    provider TEXT,
    provider_message_id TEXT
);

-- Classification predictions (multiple per email for history)
CREATE TABLE IF NOT EXISTS classifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email_id TEXT NOT NULL,
    category_name TEXT NOT NULL,
    confidence REAL NOT NULL,
    source TEXT NOT NULL,
    model_version TEXT,
    classified_at TEXT NOT NULL,
    FOREIGN KEY (email_id) REFERENCES emails(id) ON DELETE CASCADE
);

-- User corrections for feedback learning
CREATE TABLE IF NOT EXISTS corrections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email_id TEXT NOT NULL,
    old_category TEXT NOT NULL,
    new_category TEXT NOT NULL,
    corrected_at TEXT NOT NULL,
    weight REAL NOT NULL DEFAULT 1.0,
    FOREIGN KEY (email_id) REFERENCES emails(id) ON DELETE CASCADE
);

-- Provider sync state for incremental extraction
CREATE TABLE IF NOT EXISTS sync_state (
    provider TEXT PRIMARY KEY,
    sync_token TEXT,
    last_sync_at TEXT
);

-- Review decision history (migrated from JSONL)
CREATE TABLE IF NOT EXISTS decision_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    category_name TEXT NOT NULL,
    action TEXT NOT NULL,
    context_json TEXT
);

-- Action audit trail (migrated from JSONL)
CREATE TABLE IF NOT EXISTS action_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    action_type TEXT NOT NULL,
    target_id TEXT,
    details_json TEXT,
    success INTEGER NOT NULL DEFAULT 1,
    reversible INTEGER NOT NULL DEFAULT 1
);

-- Schema version for migration tracking
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER NOT NULL,
    applied_at TEXT NOT NULL
);

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_classifications_email_id
    ON classifications(email_id);

CREATE INDEX IF NOT EXISTS idx_corrections_email_id
    ON corrections(email_id);

CREATE INDEX IF NOT EXISTS idx_corrections_corrected_at
    ON corrections(corrected_at);

CREATE INDEX IF NOT EXISTS idx_emails_sender_domain
    ON emails(sender_domain);

CREATE INDEX IF NOT EXISTS idx_emails_received_date
    ON emails(received_date);

CREATE INDEX IF NOT EXISTS idx_emails_provider_message_id
    ON emails(provider_message_id);
"""


class Database:
    """
    SQLite database connection manager with WAL mode and schema management.

    Manages a single SQLite connection with:
    - WAL mode for concurrent read/write access
    - Automatic schema creation on first use
    - Schema version tracking for future migrations
    - Transaction context manager for atomic operations
    - Foreign key enforcement

    Usage:
        db = Database(Path("~/.email-analyzer/email_analyzer.db"))
        with db.transaction():
            db.execute("INSERT INTO emails ...", params)
        db.close()

    Or as a context manager:
        with Database(db_path) as db:
            db.execute("SELECT * FROM emails")
    """

    def __init__(self, db_path: str | Path) -> None:
        """
        Initialize the database, creating the file and schema if needed.

        Args:
            db_path: Path to the SQLite database file. Parent directories
                     are created automatically if they don't exist.

        Raises:
            StorageError: If the database cannot be created or opened.
        """
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            self._conn = sqlite3.connect(
                str(self._db_path),
                check_same_thread=False,
                timeout=30.0,
                isolation_level=None,  # autocommit mode — transactions managed explicitly
            )
            self._configure_connection()
            self._create_schema()
        except sqlite3.Error as e:
            raise StorageError(
                f"Failed to open database at {self._db_path}: {e}",
                context={"db_path": str(self._db_path)},
            ) from e

        logger.debug("Database opened at %s", self._db_path)

    def _configure_connection(self) -> None:
        """Configure connection pragmas for performance and correctness."""
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.execute("PRAGMA busy_timeout=5000")

    def _create_schema(self) -> None:
        """Create all tables and indexes if they don't exist."""
        try:
            # executescript issues its own implicit COMMIT, which works fine
            # even in autocommit mode (isolation_level=None)
            self._conn.executescript(_SCHEMA_SQL)
        except sqlite3.Error as e:
            raise DatabaseSchemaError(
                f"Failed to create database schema: {e}",
                context={"db_path": str(self._db_path)},
            ) from e

        # Set initial schema version if this is a new database
        cursor = self._conn.execute("SELECT COUNT(*) FROM schema_version")
        if cursor.fetchone()[0] == 0:
            from datetime import datetime, timezone

            now = datetime.now(timezone.utc).isoformat()
            self._conn.execute(
                "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
                (CURRENT_SCHEMA_VERSION, now),
            )

    @staticmethod
    def default_path() -> Path:
        """Return the default database path: ~/.email-analyzer/email_analyzer.db."""
        return Path.home() / ".email-analyzer" / "email_analyzer.db"

    def execute(self, sql: str, params: tuple[Any, ...] | None = None) -> sqlite3.Cursor:
        """
        Execute a SQL statement and return the cursor.

        Args:
            sql: SQL statement to execute.
            params: Optional tuple of parameters for parameterized queries.

        Returns:
            sqlite3.Cursor with query results.

        Raises:
            StorageError: If the connection is closed or the query fails.
        """
        if self._conn is None:
            raise StorageError(
                "Cannot execute SQL on a closed database connection",
                context={"sql": sql[:200], "db_path": str(self._db_path)},
            )
        try:
            if params is not None:
                return self._conn.execute(sql, params)
            return self._conn.execute(sql)
        except sqlite3.Error as e:
            raise StorageError(
                f"SQL execution failed: {e}",
                context={"sql": sql[:200], "db_path": str(self._db_path)},
            ) from e

    def executemany(self, sql: str, params_seq: list[tuple[Any, ...]]) -> sqlite3.Cursor:
        """
        Execute a SQL statement with multiple parameter sets.

        Args:
            sql: SQL statement to execute.
            params_seq: Sequence of parameter tuples.

        Returns:
            sqlite3.Cursor with results.

        Raises:
            StorageError: If the query fails.
        """
        try:
            return self._conn.executemany(sql, params_seq)
        except sqlite3.Error as e:
            raise StorageError(
                f"SQL executemany failed: {e}",
                context={"sql": sql[:200], "db_path": str(self._db_path)},
            ) from e

    @contextmanager
    def transaction(self) -> Generator[None, None, None]:
        """
        Context manager for explicit transaction control.

        Begins a transaction, commits on successful exit, rolls back on exception.
        In autocommit mode (isolation_level=None), we must issue explicit
        BEGIN/COMMIT/ROLLBACK.

        Usage:
            with db.transaction():
                db.execute("INSERT ...")
                db.execute("UPDATE ...")
        """
        self._conn.execute("BEGIN")
        try:
            yield
            self._conn.execute("COMMIT")
        except Exception:
            self._conn.execute("ROLLBACK")
            raise

    def get_schema_version(self) -> int:
        """
        Get the current schema version.

        Returns:
            Current schema version number.
        """
        cursor = self._conn.execute(
            "SELECT version FROM schema_version ORDER BY version DESC LIMIT 1"
        )
        row = cursor.fetchone()
        if row is None:
            return 0
        return row[0]

    def set_schema_version(self, version: int) -> None:
        """
        Set the schema version (used during migrations).

        Args:
            version: New schema version number (must be positive).

        Raises:
            ValueError: If version is not a positive integer.
        """
        if version < 1:
            raise ValueError(f"Schema version must be a positive integer, got {version}")

        from datetime import datetime, timezone

        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
            (version, now),
        )

    def close(self) -> None:
        """Close the database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None  # type: ignore[assignment]
            logger.debug("Database closed at %s", self._db_path)

    def __enter__(self) -> "Database":
        """Enter context manager."""
        return self

    def __exit__(self, exc_type: type | None, exc_val: Exception | None, exc_tb: Any) -> None:
        """Exit context manager, closing the connection."""
        self.close()

    def __del__(self) -> None:
        """Ensure connection is closed on garbage collection."""
        if hasattr(self, "_conn") and self._conn is not None:
            import contextlib

            with contextlib.suppress(Exception):
                self._conn.close()
