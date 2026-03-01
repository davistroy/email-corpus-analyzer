"""
Unit tests for Phase 3, Work Item 3.4: JSON → SQLite Migration Tool.

Tests the JsonToSqliteMigrator class with:
- Corpus JSON migration (email_corpus.json → emails table)
- Decision JSONL migration (decisions.jsonl → decision_log table)
- Action log JSONL migration (action_log.jsonl → action_log table)
- Full migrate_all orchestration
- Idempotency (running twice doesn't duplicate data)
- Corrupt JSONL line handling (skip with warning)
- Progress callback reporting
- Edge cases: missing files, empty files, malformed JSON

TDD: Tests written before implementation.
"""

import json
from datetime import datetime
from pathlib import Path

import pytest

from src.storage.database import Database
from src.storage.email_store import EmailStore
from src.storage.migration import JsonToSqliteMigrator, MigrationResult

# =============================================================================
# Test helpers
# =============================================================================


def _make_corpus_json(emails: list[dict], metadata: dict | None = None) -> dict:
    """Build a corpus JSON structure matching email_corpus.json format."""
    meta = metadata or {
        "extraction_date": "2024-01-20T12:00:00",
        "total_emails": len(emails),
        "source": "m365",
        "user_email": "user@example.com",
    }
    return {"extraction_metadata": meta, "emails": emails}


def _make_email_dict(
    email_id: str = "email_001",
    sender_email: str = "sender@example.com",
    sender_name: str = "Test Sender",
    sender_domain: str = "example.com",
    subject: str = "Test Subject",
    body_text: str = "Test body text.",
    received_date: str = "2024-01-15T10:30:00",
    has_attachments: bool = False,
    **kwargs,
) -> dict:
    """Build an email dict matching the JSON corpus format."""
    email = {
        "id": email_id,
        "sender_email": sender_email,
        "sender_name": sender_name,
        "sender_domain": sender_domain,
        "recipient_email": kwargs.get("recipient_email", "recipient@example.com"),
        "recipient_name": kwargs.get("recipient_name", "Test Recipient"),
        "subject": subject,
        "body_text": body_text,
        "received_date": received_date,
        "has_attachments": has_attachments,
        "thread_id": kwargs.get("thread_id"),
        "in_reply_to": kwargs.get("in_reply_to"),
        "references": kwargs.get("references", []),
    }
    return email  # noqa: RET504


def _make_decision_line(
    category: str = "Newsletters",
    action: str = "accept",
    timestamp: str = "2024-01-20T14:30:00+00:00",
    context: dict | None = None,
) -> str:
    """Build a single JSONL line matching decisions.jsonl format."""
    record = {
        "timestamp": timestamp,
        "category_name": category,
        "action": action,
        "context": context or {},
    }
    return json.dumps(record)


def _make_action_line(
    action_type: str = "email_move",
    target_id: str = "msg_001",
    timestamp: str = "2024-01-21T09:00:00+00:00",
    success: bool = True,
    reversible: bool = True,
    details: dict | None = None,
) -> str:
    """Build a single JSONL line matching action_log.jsonl format."""
    record = {
        "timestamp": timestamp,
        "action_type": action_type,
        "target_id": target_id,
        "details": details or {},
        "success": success,
        "reversible": reversible,
    }
    return json.dumps(record)


@pytest.fixture
def db(tmp_path):
    """Create a temporary Database for migration testing."""
    db = Database(tmp_path / "migration_test.db")
    yield db
    db.close()


@pytest.fixture
def migrator(db):
    """Create a JsonToSqliteMigrator backed by a temporary database."""
    return JsonToSqliteMigrator(db)


@pytest.fixture
def corpus_file(tmp_path):
    """Create a sample corpus JSON file with several emails."""
    emails = [_make_email_dict(email_id=f"email_{i:03d}") for i in range(5)]
    corpus_data = _make_corpus_json(emails)
    path = tmp_path / "email_corpus.json"
    path.write_text(json.dumps(corpus_data, indent=2), encoding="utf-8")
    return path


@pytest.fixture
def decisions_file(tmp_path):
    """Create a sample decisions JSONL file."""
    lines = [
        _make_decision_line("Newsletters", "accept"),
        _make_decision_line(
            "Promotions", "rename", context={"old_name": "Promos", "new_name": "Promotions"}
        ),
        _make_decision_line("Spam", "delete"),
    ]
    path = tmp_path / "decisions.jsonl"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


@pytest.fixture
def actions_file(tmp_path):
    """Create a sample action_log JSONL file."""
    lines = [
        _make_action_line("folder_create", "folder_newsletters"),
        _make_action_line(
            "email_move", "msg_001", details={"source_folder": "inbox", "target_folder": "News"}
        ),
        _make_action_line("rule_create", "rule_001"),
    ]
    path = tmp_path / "action_log.jsonl"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


# =============================================================================
# MigrationResult model tests
# =============================================================================


class TestMigrationResult:
    """Test the MigrationResult dataclass."""

    def test_migration_result_creation(self):
        """Test that MigrationResult can be created."""
        result = MigrationResult(
            emails_migrated=10,
            decisions_migrated=5,
            actions_migrated=3,
            emails_skipped=0,
            decisions_skipped=0,
            actions_skipped=0,
            warnings=[],
        )
        assert result.emails_migrated == 10
        assert result.decisions_migrated == 5
        assert result.actions_migrated == 3

    def test_migration_result_total_property(self):
        """Test that total counts all migrated items."""
        result = MigrationResult(
            emails_migrated=10,
            decisions_migrated=5,
            actions_migrated=3,
            emails_skipped=1,
            decisions_skipped=2,
            actions_skipped=0,
            warnings=["warning1"],
        )
        assert result.total_migrated == 18

    def test_migration_result_total_skipped_property(self):
        """Test that total_skipped counts all skipped items."""
        result = MigrationResult(
            emails_migrated=10,
            decisions_migrated=5,
            actions_migrated=3,
            emails_skipped=1,
            decisions_skipped=2,
            actions_skipped=3,
            warnings=[],
        )
        assert result.total_skipped == 6

    def test_migration_result_has_warnings(self):
        """Test the has_warnings property."""
        result_no_warn = MigrationResult(
            emails_migrated=0,
            decisions_migrated=0,
            actions_migrated=0,
            emails_skipped=0,
            decisions_skipped=0,
            actions_skipped=0,
            warnings=[],
        )
        result_warn = MigrationResult(
            emails_migrated=0,
            decisions_migrated=0,
            actions_migrated=0,
            emails_skipped=0,
            decisions_skipped=0,
            actions_skipped=0,
            warnings=["some warning"],
        )
        assert result_no_warn.has_warnings is False
        assert result_warn.has_warnings is True


# =============================================================================
# JsonToSqliteMigrator creation tests
# =============================================================================


class TestMigratorCreation:
    """Test JsonToSqliteMigrator instantiation."""

    def test_migrator_class_exists(self):
        """Test that JsonToSqliteMigrator can be imported."""
        from src.storage.migration import JsonToSqliteMigrator

        assert JsonToSqliteMigrator is not None

    def test_migrator_accepts_database(self, db):
        """Test that migrator accepts a Database instance."""
        migrator = JsonToSqliteMigrator(db)
        assert migrator is not None

    def test_migrator_importable_from_package(self):
        """Test that migrator can be imported from src.storage."""
        from src.storage import JsonToSqliteMigrator

        assert JsonToSqliteMigrator is not None


# =============================================================================
# migrate_corpus() tests
# =============================================================================


class TestMigrateCorpus:
    """Test corpus JSON migration to emails table."""

    def test_migrate_corpus_inserts_emails(self, migrator, corpus_file, db):
        """Test that migrate_corpus imports emails from JSON to SQLite."""
        count = migrator.migrate_corpus(corpus_file)
        assert count == 5

        # Verify emails are in the database
        store = EmailStore(db)
        assert store.count() == 5

    def test_migrate_corpus_preserves_email_fields(self, migrator, db, tmp_path):
        """Test that all email fields are preserved during migration."""
        emails = [
            _make_email_dict(
                email_id="field_test_001",
                sender_email="detailed@test.org",
                sender_name="Detailed Sender",
                sender_domain="test.org",
                subject="Detailed Subject",
                body_text="Detailed body text for testing.",
                received_date="2024-06-15T14:30:00",
                has_attachments=True,
                recipient_email="recip@test.org",
                recipient_name="Detailed Recipient",
                thread_id="thread-abc",
                in_reply_to="<reply@test.org>",
                references=["<ref1@test.org>", "<ref2@test.org>"],
            )
        ]
        corpus = _make_corpus_json(emails)
        path = tmp_path / "detailed_corpus.json"
        path.write_text(json.dumps(corpus), encoding="utf-8")

        migrator.migrate_corpus(path)

        store = EmailStore(db)
        email = store.get("field_test_001")
        assert email is not None
        assert email.sender_email == "detailed@test.org"
        assert email.sender_name == "Detailed Sender"
        assert email.sender_domain == "test.org"
        assert email.subject == "Detailed Subject"
        assert email.body_text == "Detailed body text for testing."
        assert email.received_date == datetime(2024, 6, 15, 14, 30, 0)
        assert email.has_attachments is True
        assert email.recipient_email == "recip@test.org"
        assert email.recipient_name == "Detailed Recipient"
        assert email.thread_id == "thread-abc"
        assert email.in_reply_to == "<reply@test.org>"
        assert email.references == ["<ref1@test.org>", "<ref2@test.org>"]

    def test_migrate_corpus_is_idempotent(self, migrator, corpus_file, db):
        """Test that running migration twice doesn't duplicate data."""
        migrator.migrate_corpus(corpus_file)
        migrator.migrate_corpus(corpus_file)

        store = EmailStore(db)
        assert store.count() == 5  # Still 5, not 10

    def test_migrate_corpus_handles_missing_file(self, migrator, tmp_path):
        """Test that missing corpus file raises FileNotFoundError."""
        missing_path = tmp_path / "nonexistent_corpus.json"
        with pytest.raises(FileNotFoundError):
            migrator.migrate_corpus(missing_path)

    def test_migrate_corpus_handles_malformed_json(self, migrator, tmp_path):
        """Test that malformed JSON raises an error."""
        bad_file = tmp_path / "bad_corpus.json"
        bad_file.write_text("not valid json {{{", encoding="utf-8")
        with pytest.raises((json.JSONDecodeError, ValueError)):
            migrator.migrate_corpus(bad_file)

    def test_migrate_corpus_handles_empty_emails(self, migrator, db, tmp_path):
        """Test migration of a corpus with no emails."""
        corpus = _make_corpus_json([])
        path = tmp_path / "empty_corpus.json"
        path.write_text(json.dumps(corpus), encoding="utf-8")

        count = migrator.migrate_corpus(path)
        assert count == 0

        store = EmailStore(db)
        assert store.count() == 0

    def test_migrate_corpus_handles_missing_optional_fields(self, migrator, db, tmp_path):
        """Test migration handles emails missing optional fields gracefully."""
        # Minimal email dict (missing thread_id, in_reply_to, references, etc.)
        emails = [
            {
                "id": "minimal_001",
                "sender_email": "sender@example.com",
                "sender_name": "Sender",
                "sender_domain": "example.com",
                "subject": "Minimal",
                "body_text": "Body",
                "received_date": "2024-01-15T10:00:00",
                "has_attachments": False,
            }
        ]
        corpus = _make_corpus_json(emails)
        path = tmp_path / "minimal_corpus.json"
        path.write_text(json.dumps(corpus), encoding="utf-8")

        count = migrator.migrate_corpus(path)
        assert count == 1

        store = EmailStore(db)
        email = store.get("minimal_001")
        assert email is not None
        assert email.thread_id is None
        assert email.references == []

    def test_migrate_corpus_skips_invalid_emails_with_warning(self, migrator, db, tmp_path):
        """Test that invalid emails are skipped, not crashing the migration."""
        emails = [
            _make_email_dict(email_id="valid_001"),
            # Missing required field sender_email
            {
                "id": "invalid_001",
                "subject": "Missing sender",
                "sender_domain": "x.com",
                "body_text": "b",
                "received_date": "2024-01-15T10:00:00",
                "has_attachments": False,
            },
            _make_email_dict(email_id="valid_002"),
        ]
        corpus = _make_corpus_json(emails)
        path = tmp_path / "partial_corpus.json"
        path.write_text(json.dumps(corpus), encoding="utf-8")

        count = migrator.migrate_corpus(path)
        # Should have migrated the 2 valid ones, skipped the invalid one
        assert count == 2

        store = EmailStore(db)
        assert store.count() == 2
        assert store.get("valid_001") is not None
        assert store.get("valid_002") is not None

    def test_migrate_corpus_large_batch(self, migrator, db, tmp_path):
        """Test migration of a large number of emails."""
        emails = [_make_email_dict(email_id=f"large_{i:04d}") for i in range(500)]
        corpus = _make_corpus_json(emails)
        path = tmp_path / "large_corpus.json"
        path.write_text(json.dumps(corpus), encoding="utf-8")

        count = migrator.migrate_corpus(path)
        assert count == 500

        store = EmailStore(db)
        assert store.count() == 500

    def test_migrate_corpus_with_progress_callback(self, migrator, corpus_file):
        """Test that progress callback is called during migration."""
        progress_calls = []

        def on_progress(migrated: int, total: int):
            progress_calls.append((migrated, total))

        migrator.migrate_corpus(corpus_file, progress_callback=on_progress)
        # Should have been called at least once
        assert len(progress_calls) > 0
        # Last call should report all emails migrated
        last_migrated, last_total = progress_calls[-1]
        assert last_migrated == 5
        assert last_total == 5


# =============================================================================
# migrate_decisions() tests
# =============================================================================


class TestMigrateDecisions:
    """Test decisions JSONL migration to decision_log table."""

    def test_migrate_decisions_inserts_records(self, migrator, decisions_file, db):
        """Test that decisions are imported into the decision_log table."""
        count = migrator.migrate_decisions(decisions_file)
        assert count == 3

        # Verify records in the database
        cursor = db.execute("SELECT COUNT(*) FROM decision_log")
        assert cursor.fetchone()[0] == 3

    def test_migrate_decisions_preserves_fields(self, migrator, db, tmp_path):
        """Test that all decision fields are preserved."""
        lines = [
            _make_decision_line(
                category="Test Category",
                action="rename",
                timestamp="2024-06-15T14:30:00+00:00",
                context={"old_name": "Old", "new_name": "New"},
            )
        ]
        path = tmp_path / "decisions.jsonl"
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        migrator.migrate_decisions(path)

        cursor = db.execute(
            "SELECT timestamp, category_name, action, context_json FROM decision_log"
        )
        row = cursor.fetchone()
        assert row is not None
        assert row[0] == "2024-06-15T14:30:00+00:00"
        assert row[1] == "Test Category"
        assert row[2] == "rename"
        context = json.loads(row[3])
        assert context["old_name"] == "Old"
        assert context["new_name"] == "New"

    def test_migrate_decisions_skips_corrupt_lines(self, migrator, db, tmp_path):
        """Test that corrupt JSONL lines are skipped with warnings."""
        lines = [
            _make_decision_line("Good", "accept"),
            "not valid json at all {{{{",
            _make_decision_line("Also Good", "delete"),
        ]
        path = tmp_path / "decisions.jsonl"
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        count = migrator.migrate_decisions(path)
        assert count == 2  # 2 valid, 1 corrupt

        cursor = db.execute("SELECT COUNT(*) FROM decision_log")
        assert cursor.fetchone()[0] == 2

    def test_migrate_decisions_handles_empty_lines(self, migrator, db, tmp_path):
        """Test that blank lines in JSONL are silently skipped."""
        lines = [
            _make_decision_line("A", "accept"),
            "",
            "  ",
            _make_decision_line("B", "skip"),
        ]
        path = tmp_path / "decisions.jsonl"
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        count = migrator.migrate_decisions(path)
        assert count == 2

    def test_migrate_decisions_handles_missing_file(self, migrator, tmp_path):
        """Test that missing decisions file returns 0 (not an error)."""
        missing = tmp_path / "nonexistent.jsonl"
        count = migrator.migrate_decisions(missing)
        assert count == 0

    def test_migrate_decisions_handles_empty_file(self, migrator, db, tmp_path):
        """Test migration of an empty decisions file."""
        path = tmp_path / "empty_decisions.jsonl"
        path.write_text("", encoding="utf-8")

        count = migrator.migrate_decisions(path)
        assert count == 0

    def test_migrate_decisions_with_progress_callback(self, migrator, decisions_file):
        """Test that progress callback is called during decision migration."""
        progress_calls = []

        def on_progress(migrated: int, total: int):
            progress_calls.append((migrated, total))

        migrator.migrate_decisions(decisions_file, progress_callback=on_progress)
        assert len(progress_calls) > 0


# =============================================================================
# migrate_actions() tests
# =============================================================================


class TestMigrateActions:
    """Test action log JSONL migration to action_log table."""

    def test_migrate_actions_inserts_records(self, migrator, actions_file, db):
        """Test that actions are imported into the action_log table."""
        count = migrator.migrate_actions(actions_file)
        assert count == 3

        cursor = db.execute("SELECT COUNT(*) FROM action_log")
        assert cursor.fetchone()[0] == 3

    def test_migrate_actions_preserves_fields(self, migrator, db, tmp_path):
        """Test that all action fields are preserved."""
        lines = [
            _make_action_line(
                action_type="email_move",
                target_id="msg_test",
                timestamp="2024-06-15T14:30:00+00:00",
                success=True,
                reversible=False,
                details={"source_folder": "inbox", "target_folder": "Archive"},
            )
        ]
        path = tmp_path / "actions.jsonl"
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        migrator.migrate_actions(path)

        cursor = db.execute(
            "SELECT timestamp, action_type, target_id, details_json, success, reversible "
            "FROM action_log"
        )
        row = cursor.fetchone()
        assert row is not None
        assert row[0] == "2024-06-15T14:30:00+00:00"
        assert row[1] == "email_move"
        assert row[2] == "msg_test"
        details = json.loads(row[3])
        assert details["source_folder"] == "inbox"
        assert details["target_folder"] == "Archive"
        assert row[4] == 1  # success as int
        assert row[5] == 0  # reversible as int

    def test_migrate_actions_skips_corrupt_lines(self, migrator, db, tmp_path):
        """Test that corrupt JSONL lines are skipped."""
        lines = [
            _make_action_line("folder_create", "folder_001"),
            "{{corrupt line}}",
            _make_action_line("email_move", "msg_002"),
        ]
        path = tmp_path / "actions.jsonl"
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        count = migrator.migrate_actions(path)
        assert count == 2

    def test_migrate_actions_handles_missing_file(self, migrator, tmp_path):
        """Test that missing action log file returns 0."""
        missing = tmp_path / "nonexistent.jsonl"
        count = migrator.migrate_actions(missing)
        assert count == 0

    def test_migrate_actions_handles_empty_file(self, migrator, db, tmp_path):
        """Test migration of an empty action log file."""
        path = tmp_path / "empty_actions.jsonl"
        path.write_text("", encoding="utf-8")

        count = migrator.migrate_actions(path)
        assert count == 0

    def test_migrate_actions_with_progress_callback(self, migrator, actions_file):
        """Test that progress callback is called during action migration."""
        progress_calls = []

        def on_progress(migrated: int, total: int):
            progress_calls.append((migrated, total))

        migrator.migrate_actions(actions_file, progress_callback=on_progress)
        assert len(progress_calls) > 0


# =============================================================================
# migrate_all() tests
# =============================================================================


class TestMigrateAll:
    """Test full migration orchestration."""

    def test_migrate_all_imports_everything(
        self, migrator, corpus_file, decisions_file, actions_file, db, tmp_path
    ):
        """Test that migrate_all imports corpus, decisions, and actions."""
        result = migrator.migrate_all(
            corpus_path=corpus_file,
            decisions_path=decisions_file,
            actions_path=actions_file,
        )

        assert isinstance(result, MigrationResult)
        assert result.emails_migrated == 5
        assert result.decisions_migrated == 3
        assert result.actions_migrated == 3
        assert result.total_migrated == 11

    def test_migrate_all_skips_missing_optional_files(self, migrator, corpus_file, tmp_path, db):
        """Test that migrate_all handles missing decisions/actions gracefully."""
        result = migrator.migrate_all(
            corpus_path=corpus_file,
            decisions_path=tmp_path / "nonexistent_decisions.jsonl",
            actions_path=tmp_path / "nonexistent_actions.jsonl",
        )

        assert result.emails_migrated == 5
        assert result.decisions_migrated == 0
        assert result.actions_migrated == 0

    def test_migrate_all_reports_warnings(self, migrator, db, tmp_path):
        """Test that migrate_all collects warnings from sub-migrations."""
        # Corpus with an invalid email
        emails = [
            _make_email_dict(email_id="valid"),
            {
                "id": "bad",
                "subject": "missing fields",
                "sender_domain": "x.com",
                "body_text": "b",
                "received_date": "2024-01-15T10:00:00",
                "has_attachments": False,
            },
        ]
        corpus = _make_corpus_json(emails)
        corpus_path = tmp_path / "corpus.json"
        corpus_path.write_text(json.dumps(corpus), encoding="utf-8")

        # Decisions with a corrupt line
        decisions_path = tmp_path / "decisions.jsonl"
        decisions_path.write_text(
            _make_decision_line("Good", "accept") + "\n" + "corrupt line\n",
            encoding="utf-8",
        )

        result = migrator.migrate_all(
            corpus_path=corpus_path,
            decisions_path=decisions_path,
            actions_path=tmp_path / "nonexistent.jsonl",
        )

        assert result.emails_migrated == 1
        assert result.emails_skipped == 1
        assert result.decisions_migrated == 1
        assert result.decisions_skipped == 1
        assert result.has_warnings is True
        assert len(result.warnings) >= 2

    def test_migrate_all_is_idempotent(
        self, migrator, corpus_file, decisions_file, actions_file, db
    ):
        """Test that running migrate_all twice produces same final state."""
        migrator.migrate_all(
            corpus_path=corpus_file,
            decisions_path=decisions_file,
            actions_path=actions_file,
        )
        migrator.migrate_all(
            corpus_path=corpus_file,
            decisions_path=decisions_file,
            actions_path=actions_file,
        )

        # Emails use upsert so count stays the same
        store = EmailStore(db)
        assert store.count() == 5

    def test_migrate_all_with_progress_callback(
        self, migrator, corpus_file, decisions_file, actions_file
    ):
        """Test that progress callback is invoked during migrate_all."""
        progress_calls = []

        def on_progress(stage: str, current: int, total: int):
            progress_calls.append((stage, current, total))

        migrator.migrate_all(
            corpus_path=corpus_file,
            decisions_path=decisions_file,
            actions_path=actions_file,
            progress_callback=on_progress,
        )

        assert len(progress_calls) > 0
        stages = {call[0] for call in progress_calls}
        # Should report progress for at least emails and decisions
        assert "emails" in stages or "corpus" in stages


# =============================================================================
# CLI command tests
# =============================================================================


class TestMigrateCLI:
    """Test the migrate CLI command."""

    def test_migrate_command_module_exists(self):
        """Test that the migrate command module can be imported."""
        from src.cli.commands.migrate import build_migrate_parser, cmd_migrate

        assert build_migrate_parser is not None
        assert cmd_migrate is not None

    def test_migrate_command_registered_in_cli(self):
        """Test that migrate command is registered in the CLI parser."""
        from src.cli import create_parser

        parser = create_parser()
        # Parse a valid migrate command (no --help which triggers SystemExit)
        args = parser.parse_args(["migrate"])
        assert args.command == "migrate"

    def test_migrate_command_parses_corpus_flag(self):
        """Test that --corpus flag is parsed correctly."""
        from src.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["migrate", "--corpus", "/path/to/corpus.json"])
        assert args.corpus == Path("/path/to/corpus.json")

    def test_migrate_command_parses_db_path_flag(self):
        """Test that --db-path flag is parsed correctly."""
        from src.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["migrate", "--db-path", "/path/to/db.sqlite"])
        assert args.db_path == Path("/path/to/db.sqlite")

    def test_migrate_command_runs_successfully(
        self, corpus_file, decisions_file, actions_file, tmp_path
    ):
        """Test that the migrate command completes successfully."""
        import argparse

        from src.cli.commands.migrate import cmd_migrate

        db_path = tmp_path / "cli_test.db"
        args = argparse.Namespace(
            corpus=corpus_file,
            decisions=decisions_file,
            actions=actions_file,
            db_path=db_path,
            output_dir=tmp_path,
            json=False,
            verbose=False,
            quiet=False,
            dry_run=False,
        )
        exit_code = cmd_migrate(args)
        assert exit_code == 0

        # Verify data was actually migrated
        with Database(db_path) as db:
            store = EmailStore(db)
            assert store.count() == 5

    def test_migrate_command_dry_run(self, corpus_file, tmp_path):
        """Test that --dry-run reports what would be migrated without writing."""
        import argparse

        from src.cli.commands.migrate import cmd_migrate

        db_path = tmp_path / "dryrun_test.db"
        args = argparse.Namespace(
            corpus=corpus_file,
            decisions=None,
            actions=None,
            db_path=db_path,
            output_dir=tmp_path,
            json=False,
            verbose=False,
            quiet=False,
            dry_run=True,
        )
        exit_code = cmd_migrate(args)
        assert exit_code == 0

        # Database should NOT have been created in dry-run mode
        assert not db_path.exists()

    def test_migrate_command_json_output(self, corpus_file, tmp_path, capsys):
        """Test that --json flag produces JSON output."""
        import argparse

        from src.cli.commands.migrate import cmd_migrate

        db_path = tmp_path / "json_test.db"
        args = argparse.Namespace(
            corpus=corpus_file,
            decisions=None,
            actions=None,
            db_path=db_path,
            output_dir=tmp_path,
            json=True,
            verbose=False,
            quiet=False,
            dry_run=False,
        )
        exit_code = cmd_migrate(args)
        assert exit_code == 0

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["status"] == "success"
        assert "emails_migrated" in output


# =============================================================================
# Edge cases
# =============================================================================


class TestMigrationEdgeCases:
    """Test edge cases and robustness."""

    def test_unicode_content_preserved(self, migrator, db, tmp_path):
        """Test that Unicode email content survives migration."""
        emails = [
            _make_email_dict(
                email_id="unicode_001",
                sender_name="Rene Descartes",
                subject="Re: Reunion planning",
                body_text="Cafe at 3pm? Cost is 50 euros.",
            )
        ]
        corpus = _make_corpus_json(emails)
        path = tmp_path / "unicode_corpus.json"
        path.write_text(json.dumps(corpus, ensure_ascii=False), encoding="utf-8")

        migrator.migrate_corpus(path)

        store = EmailStore(db)
        email = store.get("unicode_001")
        assert "Rene" in email.sender_name
        assert "Cafe" in email.body_text

    def test_large_body_text_preserved(self, migrator, db, tmp_path):
        """Test that large body text survives migration."""
        long_body = "A" * 100_000
        emails = [_make_email_dict(email_id="large_body", body_text=long_body)]
        corpus = _make_corpus_json(emails)
        path = tmp_path / "large_body_corpus.json"
        path.write_text(json.dumps(corpus), encoding="utf-8")

        migrator.migrate_corpus(path)

        store = EmailStore(db)
        email = store.get("large_body")
        assert len(email.body_text) == 100_000

    def test_sql_special_characters_in_fields(self, migrator, db, tmp_path):
        """Test that SQL-special characters are handled safely."""
        emails = [
            _make_email_dict(
                email_id="special_001",
                subject="O'Brien's \"quote\" and 100%; DROP TABLE emails;",
                body_text="Content with 'quotes' and\nnewlines\ttabs",
            )
        ]
        corpus = _make_corpus_json(emails)
        path = tmp_path / "special_corpus.json"
        path.write_text(json.dumps(corpus), encoding="utf-8")

        migrator.migrate_corpus(path)

        store = EmailStore(db)
        email = store.get("special_001")
        assert "O'Brien" in email.subject
        assert "DROP TABLE" in email.subject  # Preserved as text, not executed

    def test_decisions_with_missing_context(self, migrator, db, tmp_path):
        """Test that decisions without context field still migrate."""
        line = json.dumps(
            {
                "timestamp": "2024-01-20T14:30:00+00:00",
                "category_name": "Newsletters",
                "action": "accept",
                # No "context" key
            }
        )
        path = tmp_path / "no_context_decisions.jsonl"
        path.write_text(line + "\n", encoding="utf-8")

        count = migrator.migrate_decisions(path)
        assert count == 1

    def test_actions_with_missing_details(self, migrator, db, tmp_path):
        """Test that actions without details field still migrate."""
        line = json.dumps(
            {
                "timestamp": "2024-01-21T09:00:00+00:00",
                "action_type": "folder_create",
                "target_id": "folder_001",
                "success": True,
                "reversible": True,
                # No "details" key
            }
        )
        path = tmp_path / "no_details_actions.jsonl"
        path.write_text(line + "\n", encoding="utf-8")

        count = migrator.migrate_actions(path)
        assert count == 1

    def test_json_files_not_deleted_after_migration(
        self, migrator, corpus_file, decisions_file, actions_file
    ):
        """Test that JSON files are preserved (not deleted) after migration."""
        migrator.migrate_all(
            corpus_path=corpus_file,
            decisions_path=decisions_file,
            actions_path=actions_file,
        )

        # All original files must still exist
        assert corpus_file.exists()
        assert decisions_file.exists()
        assert actions_file.exists()

    def test_corpus_with_has_attachments_bool_and_int(self, migrator, db, tmp_path):
        """Test migration handles both bool and int has_attachments values."""
        emails = [
            {**_make_email_dict(email_id="bool_true"), "has_attachments": True},
            {**_make_email_dict(email_id="bool_false"), "has_attachments": False},
            {**_make_email_dict(email_id="int_one"), "has_attachments": 1},
            {**_make_email_dict(email_id="int_zero"), "has_attachments": 0},
        ]
        corpus = _make_corpus_json(emails)
        path = tmp_path / "attachment_types.json"
        path.write_text(json.dumps(corpus), encoding="utf-8")

        migrator.migrate_corpus(path)

        store = EmailStore(db)
        assert store.get("bool_true").has_attachments is True
        assert store.get("bool_false").has_attachments is False
        assert store.get("int_one").has_attachments is True
        assert store.get("int_zero").has_attachments is False
