"""
Unit tests for Phase 3, Work Item 3.1: Database Schema and Connection Management.

Tests the SQLite database module with:
- Database creation and file management
- WAL mode for concurrent access
- Schema creation with all required tables
- Schema version tracking for migrations
- Connection context manager for transaction management
- Concurrent access patterns
- Storage exception handling

TDD: Tests written before implementation.
"""

import threading
from pathlib import Path

import pytest

from src.exceptions import StorageError

# =============================================================================
# Database creation and initialization tests
# =============================================================================


class TestDatabaseCreation:
    """Test Database class instantiation and file management."""

    def test_database_class_exists(self):
        """Test that Database class can be imported."""
        from src.storage.database import Database

        assert Database is not None

    def test_database_creates_file(self, tmp_path):
        """Test that Database creates the SQLite file on initialization."""
        from src.storage.database import Database

        db_path = tmp_path / "test.db"
        assert not db_path.exists()

        db = Database(db_path)
        assert db_path.exists()
        db.close()

    def test_database_creates_parent_directories(self, tmp_path):
        """Test that Database creates parent directories if they don't exist."""
        from src.storage.database import Database

        db_path = tmp_path / "nested" / "dir" / "test.db"
        assert not db_path.parent.exists()

        db = Database(db_path)
        assert db_path.exists()
        db.close()

    def test_database_accepts_string_path(self, tmp_path):
        """Test that Database accepts a string path (not just Path objects)."""
        from src.storage.database import Database

        db_path = str(tmp_path / "test.db")
        db = Database(db_path)
        assert Path(db_path).exists()
        db.close()

    def test_database_reuses_existing_file(self, tmp_path):
        """Test that Database opens an existing database without data loss."""
        from src.storage.database import Database

        db_path = tmp_path / "test.db"

        # Create and close
        db1 = Database(db_path)
        db1.close()

        # Reopen - should not raise
        db2 = Database(db_path)
        db2.close()

    def test_database_default_path(self):
        """Test that default_path() returns the expected default location."""
        from src.storage.database import Database

        default = Database.default_path()
        assert isinstance(default, Path)
        assert default.name == "email_analyzer.db"
        assert ".email-analyzer" in str(default)

    def test_database_close(self, tmp_path):
        """Test that close() properly closes the connection."""
        from src.storage.database import Database

        db_path = tmp_path / "test.db"
        db = Database(db_path)
        db.close()
        # After close, operations should fail
        with pytest.raises(StorageError):
            db.execute("SELECT 1")

    def test_database_context_manager(self, tmp_path):
        """Test Database works as a context manager."""
        from src.storage.database import Database

        db_path = tmp_path / "test.db"
        with Database(db_path) as db:
            # Should be usable inside context
            assert db is not None
        # After context exit, db should be closed


# =============================================================================
# WAL mode tests
# =============================================================================


class TestWALMode:
    """Test WAL (Write-Ahead Logging) mode configuration."""

    def test_wal_mode_enabled(self, tmp_path):
        """Test that WAL mode is enabled on database creation."""
        from src.storage.database import Database

        db_path = tmp_path / "test.db"
        db = Database(db_path)

        # Verify WAL mode through direct query
        result = db.execute("PRAGMA journal_mode").fetchone()
        assert result[0].lower() == "wal"
        db.close()

    def test_wal_mode_persists_on_reopen(self, tmp_path):
        """Test that WAL mode persists when database is reopened."""
        from src.storage.database import Database

        db_path = tmp_path / "test.db"

        db1 = Database(db_path)
        db1.close()

        db2 = Database(db_path)
        result = db2.execute("PRAGMA journal_mode").fetchone()
        assert result[0].lower() == "wal"
        db2.close()


# =============================================================================
# Schema creation tests
# =============================================================================


class TestSchemaCreation:
    """Test that all required tables and indexes are created."""

    def _get_tables(self, db) -> list[str]:
        """Helper to get all table names from the database."""
        rows = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        return [row[0] for row in rows]

    def _get_indexes(self, db) -> list[str]:
        """Helper to get all index names from the database."""
        rows = db.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
        return [row[0] for row in rows]

    def _get_columns(self, db, table_name: str) -> list[dict]:
        """Helper to get column info for a table."""
        rows = db.execute(f"PRAGMA table_info({table_name})").fetchall()
        return [
            {"name": row[1], "type": row[2], "notnull": bool(row[3]), "pk": bool(row[5])}
            for row in rows
        ]

    def _get_column_names(self, db, table_name: str) -> list[str]:
        """Helper to get column names for a table."""
        return [col["name"] for col in self._get_columns(db, table_name)]

    def test_emails_table_exists(self, tmp_path):
        """Test that emails table is created."""
        from src.storage.database import Database

        db = Database(tmp_path / "test.db")
        tables = self._get_tables(db)
        assert "emails" in tables
        db.close()

    def test_emails_table_columns(self, tmp_path):
        """Test that emails table has all required columns."""
        from src.storage.database import Database

        db = Database(tmp_path / "test.db")
        columns = self._get_column_names(db, "emails")

        expected_columns = [
            "id",
            "sender_email",
            "sender_name",
            "sender_domain",
            "recipient_email",
            "recipient_name",
            "subject",
            "body_text",
            "received_date",
            "has_attachments",
            "thread_id",
            "in_reply_to",
            "references_json",
            "provider",
            "provider_message_id",
        ]
        for col in expected_columns:
            assert col in columns, f"Missing column: {col}"
        db.close()

    def test_emails_table_primary_key(self, tmp_path):
        """Test that emails table has id as primary key."""
        from src.storage.database import Database

        db = Database(tmp_path / "test.db")
        columns = self._get_columns(db, "emails")
        pk_columns = [c for c in columns if c["pk"]]
        assert len(pk_columns) == 1
        assert pk_columns[0]["name"] == "id"
        db.close()

    def test_classifications_table_exists(self, tmp_path):
        """Test that classifications table is created."""
        from src.storage.database import Database

        db = Database(tmp_path / "test.db")
        tables = self._get_tables(db)
        assert "classifications" in tables
        db.close()

    def test_classifications_table_columns(self, tmp_path):
        """Test that classifications table has all required columns."""
        from src.storage.database import Database

        db = Database(tmp_path / "test.db")
        columns = self._get_column_names(db, "classifications")

        expected_columns = [
            "id",
            "email_id",
            "category_name",
            "confidence",
            "source",
            "model_version",
            "classified_at",
        ]
        for col in expected_columns:
            assert col in columns, f"Missing column: {col}"
        db.close()

    def test_corrections_table_exists(self, tmp_path):
        """Test that corrections table is created."""
        from src.storage.database import Database

        db = Database(tmp_path / "test.db")
        tables = self._get_tables(db)
        assert "corrections" in tables
        db.close()

    def test_corrections_table_columns(self, tmp_path):
        """Test that corrections table has all required columns."""
        from src.storage.database import Database

        db = Database(tmp_path / "test.db")
        columns = self._get_column_names(db, "corrections")

        expected_columns = [
            "id",
            "email_id",
            "old_category",
            "new_category",
            "corrected_at",
            "weight",
        ]
        for col in expected_columns:
            assert col in columns, f"Missing column: {col}"
        db.close()

    def test_sync_state_table_exists(self, tmp_path):
        """Test that sync_state table is created."""
        from src.storage.database import Database

        db = Database(tmp_path / "test.db")
        tables = self._get_tables(db)
        assert "sync_state" in tables
        db.close()

    def test_sync_state_table_columns(self, tmp_path):
        """Test that sync_state table has all required columns."""
        from src.storage.database import Database

        db = Database(tmp_path / "test.db")
        columns = self._get_column_names(db, "sync_state")

        expected_columns = ["provider", "sync_token", "last_sync_at"]
        for col in expected_columns:
            assert col in columns, f"Missing column: {col}"
        db.close()

    def test_decision_log_table_exists(self, tmp_path):
        """Test that decision_log table is created."""
        from src.storage.database import Database

        db = Database(tmp_path / "test.db")
        tables = self._get_tables(db)
        assert "decision_log" in tables
        db.close()

    def test_decision_log_table_columns(self, tmp_path):
        """Test that decision_log table has all required columns."""
        from src.storage.database import Database

        db = Database(tmp_path / "test.db")
        columns = self._get_column_names(db, "decision_log")

        expected_columns = [
            "id",
            "timestamp",
            "category_name",
            "action",
            "context_json",
        ]
        for col in expected_columns:
            assert col in columns, f"Missing column: {col}"
        db.close()

    def test_action_log_table_exists(self, tmp_path):
        """Test that action_log table is created."""
        from src.storage.database import Database

        db = Database(tmp_path / "test.db")
        tables = self._get_tables(db)
        assert "action_log" in tables
        db.close()

    def test_action_log_table_columns(self, tmp_path):
        """Test that action_log table has all required columns."""
        from src.storage.database import Database

        db = Database(tmp_path / "test.db")
        columns = self._get_column_names(db, "action_log")

        expected_columns = [
            "id",
            "timestamp",
            "action_type",
            "target_id",
            "details_json",
            "success",
            "reversible",
        ]
        for col in expected_columns:
            assert col in columns, f"Missing column: {col}"
        db.close()

    def test_schema_version_table_exists(self, tmp_path):
        """Test that schema_version table is created."""
        from src.storage.database import Database

        db = Database(tmp_path / "test.db")
        tables = self._get_tables(db)
        assert "schema_version" in tables
        db.close()

    def test_all_required_tables_present(self, tmp_path):
        """Test that all 7 required tables are created."""
        from src.storage.database import Database

        db = Database(tmp_path / "test.db")
        tables = self._get_tables(db)

        required_tables = [
            "emails",
            "classifications",
            "corrections",
            "sync_state",
            "decision_log",
            "action_log",
            "schema_version",
        ]
        for table in required_tables:
            assert table in tables, f"Missing table: {table}"
        db.close()


# =============================================================================
# Index tests
# =============================================================================


class TestIndexes:
    """Test that appropriate indexes are created."""

    def _get_indexes(self, db) -> list[str]:
        """Helper to get all non-internal index names."""
        rows = db.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
        return [row[0] for row in rows]

    def test_classifications_email_id_index(self, tmp_path):
        """Test that an index exists on classifications.email_id."""
        from src.storage.database import Database

        db = Database(tmp_path / "test.db")
        indexes = self._get_indexes(db)
        # There should be an index covering email_id on classifications
        assert any("classification" in idx and "email" in idx for idx in indexes), (
            f"No index on classifications.email_id. Found indexes: {indexes}"
        )
        db.close()

    def test_corrections_corrected_at_index(self, tmp_path):
        """Test that an index exists on corrections.corrected_at."""
        from src.storage.database import Database

        db = Database(tmp_path / "test.db")
        indexes = self._get_indexes(db)
        assert any("correction" in idx and "corrected" in idx for idx in indexes), (
            f"No index on corrections.corrected_at. Found indexes: {indexes}"
        )
        db.close()

    def test_emails_sender_domain_index(self, tmp_path):
        """Test that an index exists on emails.sender_domain for common queries."""
        from src.storage.database import Database

        db = Database(tmp_path / "test.db")
        indexes = self._get_indexes(db)
        assert any("email" in idx and "sender_domain" in idx for idx in indexes), (
            f"No index on emails.sender_domain. Found indexes: {indexes}"
        )
        db.close()

    def test_emails_received_date_index(self, tmp_path):
        """Test that an index exists on emails.received_date for temporal queries."""
        from src.storage.database import Database

        db = Database(tmp_path / "test.db")
        indexes = self._get_indexes(db)
        assert any("email" in idx and "received_date" in idx for idx in indexes), (
            f"No index on emails.received_date. Found indexes: {indexes}"
        )
        db.close()

    def test_corrections_email_id_index(self, tmp_path):
        """Test that an index exists on corrections.email_id."""
        from src.storage.database import Database

        db = Database(tmp_path / "test.db")
        indexes = self._get_indexes(db)
        assert any("correction" in idx and "email" in idx for idx in indexes), (
            f"No index on corrections.email_id. Found indexes: {indexes}"
        )
        db.close()


# =============================================================================
# Schema version tests
# =============================================================================


class TestSchemaVersion:
    """Test schema version tracking for future migrations."""

    def test_initial_schema_version(self, tmp_path):
        """Test that initial schema version is 1."""
        from src.storage.database import Database

        db = Database(tmp_path / "test.db")
        version = db.get_schema_version()
        assert version == 1
        db.close()

    def test_schema_version_set_and_get(self, tmp_path):
        """Test setting and getting schema version."""
        from src.storage.database import Database

        db = Database(tmp_path / "test.db")
        assert db.get_schema_version() == 1

        db.set_schema_version(2)
        assert db.get_schema_version() == 2
        db.close()

    def test_schema_version_persists_across_reopen(self, tmp_path):
        """Test that schema version persists when database is reopened."""
        from src.storage.database import Database

        db_path = tmp_path / "test.db"
        db1 = Database(db_path)
        db1.set_schema_version(3)
        db1.close()

        db2 = Database(db_path)
        assert db2.get_schema_version() == 3
        db2.close()

    def test_schema_version_validation(self, tmp_path):
        """Test that schema version must be a positive integer."""
        from src.storage.database import Database

        db = Database(tmp_path / "test.db")
        with pytest.raises(ValueError):
            db.set_schema_version(0)
        with pytest.raises(ValueError):
            db.set_schema_version(-1)
        db.close()


# =============================================================================
# Connection and transaction management tests
# =============================================================================


class TestConnectionManagement:
    """Test connection context manager and transaction management."""

    def test_execute_returns_cursor(self, tmp_path):
        """Test that execute() returns a cursor with results."""
        from src.storage.database import Database

        db = Database(tmp_path / "test.db")
        cursor = db.execute("SELECT 1 as value")
        row = cursor.fetchone()
        assert row[0] == 1
        db.close()

    def test_execute_with_params(self, tmp_path):
        """Test that execute() accepts parameterized queries."""
        from src.storage.database import Database

        db = Database(tmp_path / "test.db")
        db.execute(
            "INSERT INTO emails (id, sender_email, sender_name, sender_domain, "
            "recipient_email, recipient_name, subject, body_text, received_date, "
            "has_attachments) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "test1",
                "sender@test.com",
                "Sender",
                "test.com",
                "recip@test.com",
                "Recipient",
                "Test Subject",
                "Body",
                "2024-01-15T10:00:00",
                0,
            ),
        )
        cursor = db.execute("SELECT id, subject FROM emails WHERE id = ?", ("test1",))
        row = cursor.fetchone()
        assert row[0] == "test1"
        assert row[1] == "Test Subject"
        db.close()

    def test_executemany(self, tmp_path):
        """Test that executemany() works for batch inserts."""
        from src.storage.database import Database

        db = Database(tmp_path / "test.db")
        rows = [
            (
                "id1",
                "a@test.com",
                "A",
                "test.com",
                None,
                "",
                "Sub1",
                "Body1",
                "2024-01-15T10:00:00",
                0,
            ),
            (
                "id2",
                "b@test.com",
                "B",
                "test.com",
                None,
                "",
                "Sub2",
                "Body2",
                "2024-01-16T10:00:00",
                0,
            ),
        ]
        db.executemany(
            "INSERT INTO emails (id, sender_email, sender_name, sender_domain, "
            "recipient_email, recipient_name, subject, body_text, received_date, "
            "has_attachments) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
        cursor = db.execute("SELECT COUNT(*) FROM emails")
        assert cursor.fetchone()[0] == 2
        db.close()

    def test_transaction_context_manager_commit(self, tmp_path):
        """Test that transaction context manager commits on success."""
        from src.storage.database import Database

        db = Database(tmp_path / "test.db")
        with db.transaction():
            db.execute(
                "INSERT INTO emails (id, sender_email, sender_name, sender_domain, "
                "recipient_email, recipient_name, subject, body_text, received_date, "
                "has_attachments) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    "txn1",
                    "a@test.com",
                    "A",
                    "test.com",
                    None,
                    "",
                    "Sub",
                    "Body",
                    "2024-01-15T10:00:00",
                    0,
                ),
            )

        # Data should be committed
        cursor = db.execute("SELECT COUNT(*) FROM emails WHERE id = ?", ("txn1",))
        assert cursor.fetchone()[0] == 1
        db.close()

    def test_transaction_context_manager_rollback(self, tmp_path):
        """Test that transaction context manager rolls back on exception."""
        from src.storage.database import Database

        db = Database(tmp_path / "test.db")
        with pytest.raises(ValueError), db.transaction():
            db.execute(
                "INSERT INTO emails (id, sender_email, sender_name, sender_domain, "
                "recipient_email, recipient_name, subject, body_text, received_date, "
                "has_attachments) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    "txn2",
                    "a@test.com",
                    "A",
                    "test.com",
                    None,
                    "",
                    "Sub",
                    "Body",
                    "2024-01-15T10:00:00",
                    0,
                ),
            )
            raise ValueError("Simulated error")

        # Data should NOT be committed due to rollback
        cursor = db.execute("SELECT COUNT(*) FROM emails WHERE id = ?", ("txn2",))
        assert cursor.fetchone()[0] == 0
        db.close()

    def test_foreign_keys_enabled(self, tmp_path):
        """Test that foreign keys are enabled."""
        from src.storage.database import Database

        db = Database(tmp_path / "test.db")
        result = db.execute("PRAGMA foreign_keys").fetchone()
        assert result[0] == 1
        db.close()


# =============================================================================
# Concurrent access tests
# =============================================================================


class TestConcurrentAccess:
    """Test concurrent database access patterns."""

    def test_concurrent_reads(self, tmp_path):
        """Test that multiple threads can read simultaneously."""
        from src.storage.database import Database

        db_path = tmp_path / "test.db"
        db = Database(db_path)

        # Insert test data
        db.execute(
            "INSERT INTO emails (id, sender_email, sender_name, sender_domain, "
            "recipient_email, recipient_name, subject, body_text, received_date, "
            "has_attachments) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "conc1",
                "a@test.com",
                "A",
                "test.com",
                None,
                "",
                "Sub",
                "Body",
                "2024-01-15T10:00:00",
                0,
            ),
        )

        results = []
        errors = []

        def read_emails():
            try:
                # Each thread gets its own connection for true concurrency
                thread_db = Database(db_path)
                cursor = thread_db.execute("SELECT id FROM emails WHERE id = ?", ("conc1",))
                row = cursor.fetchone()
                results.append(row[0] if row else None)
                thread_db.close()
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=read_emails) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert not errors, f"Errors during concurrent reads: {errors}"
        assert all(r == "conc1" for r in results)
        db.close()

    def test_concurrent_writes(self, tmp_path):
        """Test that concurrent writes don't corrupt data (WAL mode benefit)."""
        from src.storage.database import Database

        db_path = tmp_path / "test.db"
        db = Database(db_path)

        errors = []

        def write_email(idx):
            try:
                thread_db = Database(db_path)
                thread_db.execute(
                    "INSERT INTO emails (id, sender_email, sender_name, sender_domain, "
                    "recipient_email, recipient_name, subject, body_text, received_date, "
                    "has_attachments) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        f"write_{idx}",
                        "a@test.com",
                        "A",
                        "test.com",
                        None,
                        "",
                        f"Sub {idx}",
                        "Body",
                        "2024-01-15T10:00:00",
                        0,
                    ),
                )
                thread_db.close()
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=write_email, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert not errors, f"Errors during concurrent writes: {errors}"

        cursor = db.execute("SELECT COUNT(*) FROM emails")
        count = cursor.fetchone()[0]
        assert count == 10
        db.close()


# =============================================================================
# Storage exception tests
# =============================================================================


class TestStorageExceptions:
    """Test storage-related exceptions."""

    def test_storage_error_exists(self):
        """Test that StorageError exception class exists."""
        from src.exceptions import StorageError

        assert StorageError is not None

    def test_storage_error_inherits_from_base(self):
        """Test that StorageError inherits from EmailAnalyzerError."""
        from src.exceptions import EmailAnalyzerError, StorageError

        assert issubclass(StorageError, EmailAnalyzerError)

    def test_storage_error_with_message(self):
        """Test StorageError with message and recovery hint."""
        from src.exceptions import StorageError

        error = StorageError("Database file locked")
        assert error.message == "Database file locked"
        assert error.recovery_hint is not None

    def test_storage_error_with_custom_hint(self):
        """Test StorageError with custom recovery hint."""
        from src.exceptions import StorageError

        error = StorageError("Write failed", recovery_hint="Check disk space")
        assert error.recovery_hint == "Check disk space"

    def test_storage_error_with_context(self):
        """Test StorageError with context dictionary."""
        from src.exceptions import StorageError

        error = StorageError(
            "Schema migration failed",
            context={"current_version": 1, "target_version": 2},
        )
        assert error.context["current_version"] == 1
        assert error.context["target_version"] == 2

    def test_database_schema_error_exists(self):
        """Test that DatabaseSchemaError exception class exists."""
        from src.exceptions import DatabaseSchemaError

        assert DatabaseSchemaError is not None

    def test_database_schema_error_inherits_from_storage_error(self):
        """Test that DatabaseSchemaError inherits from StorageError."""
        from src.exceptions import DatabaseSchemaError, StorageError

        assert issubclass(DatabaseSchemaError, StorageError)

    def test_database_schema_error_with_message(self):
        """Test DatabaseSchemaError with message."""
        from src.exceptions import DatabaseSchemaError

        error = DatabaseSchemaError("Schema version mismatch")
        assert "Schema version mismatch" in error.message
        assert error.recovery_hint is not None

    def test_storage_error_is_raisable(self):
        """Test StorageError can be raised and caught."""
        from src.exceptions import StorageError

        with pytest.raises(StorageError):
            raise StorageError("Test error")

    def test_database_schema_error_is_raisable(self):
        """Test DatabaseSchemaError can be raised and caught as StorageError."""
        from src.exceptions import DatabaseSchemaError, StorageError

        with pytest.raises(StorageError):
            raise DatabaseSchemaError("Schema error")


# =============================================================================
# Module exports tests
# =============================================================================


class TestModuleExports:
    """Test that the storage package exports are correct."""

    def test_database_importable_from_package(self):
        """Test that Database can be imported from src.storage."""
        from src.storage import Database

        assert Database is not None

    def test_exceptions_importable_from_package(self):
        """Test that storage exceptions can be imported from src.exceptions."""
        from src.exceptions import DatabaseSchemaError, StorageError

        assert StorageError is not None
        assert DatabaseSchemaError is not None


# =============================================================================
# Edge cases and robustness tests
# =============================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_schema_not_recreated_on_reopen(self, tmp_path):
        """Test that schema is not recreated if it already exists."""
        from src.storage.database import Database

        db_path = tmp_path / "test.db"

        # Create and insert data
        db1 = Database(db_path)
        db1.execute(
            "INSERT INTO emails (id, sender_email, sender_name, sender_domain, "
            "recipient_email, recipient_name, subject, body_text, received_date, "
            "has_attachments) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "persist1",
                "a@test.com",
                "A",
                "test.com",
                None,
                "",
                "Sub",
                "Body",
                "2024-01-15T10:00:00",
                0,
            ),
        )
        db1.close()

        # Reopen - data should still be there
        db2 = Database(db_path)
        cursor = db2.execute("SELECT id FROM emails WHERE id = ?", ("persist1",))
        row = cursor.fetchone()
        assert row is not None
        assert row[0] == "persist1"
        db2.close()

    def test_unique_constraint_on_emails_id(self, tmp_path):
        """Test that emails.id has a unique constraint (it's the PK)."""
        from src.exceptions import StorageError
        from src.storage.database import Database

        db = Database(tmp_path / "test.db")
        db.execute(
            "INSERT INTO emails (id, sender_email, sender_name, sender_domain, "
            "recipient_email, recipient_name, subject, body_text, received_date, "
            "has_attachments) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "dup1",
                "a@test.com",
                "A",
                "test.com",
                None,
                "",
                "Sub",
                "Body",
                "2024-01-15T10:00:00",
                0,
            ),
        )

        with pytest.raises(StorageError, match="UNIQUE constraint"):
            db.execute(
                "INSERT INTO emails (id, sender_email, sender_name, sender_domain, "
                "recipient_email, recipient_name, subject, body_text, received_date, "
                "has_attachments) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    "dup1",
                    "b@test.com",
                    "B",
                    "test.com",
                    None,
                    "",
                    "Sub2",
                    "Body2",
                    "2024-01-16T10:00:00",
                    0,
                ),
            )
        db.close()

    def test_sync_state_provider_is_primary_key(self, tmp_path):
        """Test that sync_state.provider is the primary key."""
        from src.storage.database import Database

        db = Database(tmp_path / "test.db")
        columns = db.execute("PRAGMA table_info(sync_state)").fetchall()
        pk_columns = [col[1] for col in columns if col[5]]  # col[5] is pk flag
        assert "provider" in pk_columns
        db.close()

    def test_classifications_auto_increment_id(self, tmp_path):
        """Test that classifications.id auto-increments."""
        from src.storage.database import Database

        db = Database(tmp_path / "test.db")
        # Insert an email first for the FK
        db.execute(
            "INSERT INTO emails (id, sender_email, sender_name, sender_domain, "
            "recipient_email, recipient_name, subject, body_text, received_date, "
            "has_attachments) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "email1",
                "a@test.com",
                "A",
                "test.com",
                None,
                "",
                "Sub",
                "Body",
                "2024-01-15T10:00:00",
                0,
            ),
        )

        db.execute(
            "INSERT INTO classifications (email_id, category_name, confidence, source, "
            "model_version, classified_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("email1", "newsletters", 0.9, "llm:qwen2.5", "v1", "2024-01-15T10:00:00"),
        )
        db.execute(
            "INSERT INTO classifications (email_id, category_name, confidence, source, "
            "model_version, classified_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("email1", "promotions", 0.7, "rule:sender_domain", "v1", "2024-01-15T11:00:00"),
        )

        cursor = db.execute("SELECT id FROM classifications ORDER BY id")
        rows = cursor.fetchall()
        assert len(rows) == 2
        assert rows[0][0] < rows[1][0]  # Auto-increment gives ascending IDs
        db.close()

    def test_corrections_default_weight(self, tmp_path):
        """Test that corrections.weight defaults to 1.0."""
        from src.storage.database import Database

        db = Database(tmp_path / "test.db")
        # Insert an email first
        db.execute(
            "INSERT INTO emails (id, sender_email, sender_name, sender_domain, "
            "recipient_email, recipient_name, subject, body_text, received_date, "
            "has_attachments) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "email1",
                "a@test.com",
                "A",
                "test.com",
                None,
                "",
                "Sub",
                "Body",
                "2024-01-15T10:00:00",
                0,
            ),
        )

        db.execute(
            "INSERT INTO corrections (email_id, old_category, new_category, corrected_at) "
            "VALUES (?, ?, ?, ?)",
            ("email1", "newsletters", "promotions", "2024-01-15T10:00:00"),
        )

        cursor = db.execute("SELECT weight FROM corrections WHERE email_id = ?", ("email1",))
        row = cursor.fetchone()
        assert row[0] == 1.0
        db.close()

    def test_action_log_defaults(self, tmp_path):
        """Test that action_log has correct defaults for success and reversible."""
        from src.storage.database import Database

        db = Database(tmp_path / "test.db")
        db.execute(
            "INSERT INTO action_log (timestamp, action_type, target_id, details_json) "
            "VALUES (?, ?, ?, ?)",
            ("2024-01-15T10:00:00", "email_move", "email1", '{"folder": "newsletters"}'),
        )

        cursor = db.execute("SELECT success, reversible FROM action_log")
        row = cursor.fetchone()
        # success defaults to 1 (True), reversible defaults to 1 (True)
        assert row[0] == 1
        assert row[1] == 1
        db.close()
