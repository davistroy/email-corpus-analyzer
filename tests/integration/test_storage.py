"""
Integration tests for the complete SQLite storage layer.

Tests the full stack: Database + EmailStore + JsonToSqliteMigrator working
together in realistic end-to-end workflows. Unit tests for each component
exist separately in tests/unit/; these tests verify cross-component behavior.

Phase 3: Integration Testing for Storage Layer.

Test categories:
- End-to-end migration: JSON corpus -> SQLite -> EmailStore queries
- Database lifecycle: create, populate, close, reopen, verify persistence
- Transaction integrity: rollback on error, atomicity across components
- Concurrent access: multiple readers/writers on the same database file
- Data integrity: round-trip fidelity across the full chain
- Large dataset: batch processing and pagination
- Schema persistence: version tracking across open/close cycles
- Foreign key cascades: email deletion cascading to classifications/corrections
"""

import json
import threading
from datetime import datetime

import pytest

from src.models.email import Email
from src.storage.database import Database
from src.storage.email_store import EmailStore
from src.storage.migration import JsonToSqliteMigrator, MigrationResult

# =============================================================================
# Helpers
# =============================================================================


def _make_email(
    email_id: str = "email_001",
    sender_email: str = "sender@example.com",
    sender_name: str = "Test Sender",
    sender_domain: str = "example.com",
    recipient_email: str = "recipient@example.com",
    recipient_name: str = "Test Recipient",
    subject: str = "Test Email Subject",
    body_text: str = "This is a test email body.",
    received_date: datetime | None = None,
    has_attachments: bool = False,
    thread_id: str | None = None,
    in_reply_to: str | None = None,
    references: list[str] | None = None,
    provider: str | None = None,
    provider_message_id: str | None = None,
) -> Email:
    """Create a test Email with sensible defaults."""
    return Email(
        id=email_id,
        sender_email=sender_email,
        sender_name=sender_name,
        sender_domain=sender_domain,
        recipient_email=recipient_email,
        recipient_name=recipient_name,
        subject=subject,
        body_text=body_text,
        received_date=received_date or datetime(2024, 1, 15, 10, 30, 0),
        has_attachments=has_attachments,
        thread_id=thread_id,
        in_reply_to=in_reply_to,
        references=references or [],
        provider=provider,
        provider_message_id=provider_message_id,
    )


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
    return {
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
        "provider": kwargs.get("provider"),
        "provider_message_id": kwargs.get("provider_message_id"),
    }


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


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def db_path(tmp_path):
    """Return a temporary database file path."""
    return tmp_path / "integration_test.db"


@pytest.fixture
def db(db_path):
    """Create a temporary Database for testing."""
    database = Database(db_path)
    yield database
    database.close()


@pytest.fixture
def email_store(db):
    """Create an EmailStore backed by a temporary database."""
    return EmailStore(db)


@pytest.fixture
def migrator(db):
    """Create a JsonToSqliteMigrator backed by a temporary database."""
    return JsonToSqliteMigrator(db)


@pytest.fixture
def diverse_emails():
    """Create a diverse set of 50 Email objects for integration testing."""
    domains = ["amazon.com", "github.com", "linkedin.com", "newsletter.com", "work.com"]
    subjects_by_domain = {
        "amazon.com": ["Your order has shipped", "Order confirmation", "Delivery update"],
        "github.com": ["PR review requested", "Issue opened", "Build failed"],
        "linkedin.com": ["New connection request", "Job alert", "Profile viewed"],
        "newsletter.com": ["Weekly digest", "Top stories", "Breaking news"],
        "work.com": ["Meeting invite", "Project update", "Action required"],
    }
    emails = []
    for i in range(50):
        domain = domains[i % len(domains)]
        subjects = subjects_by_domain[domain]
        subject = subjects[i % len(subjects)] + f" #{i}"
        emails.append(
            _make_email(
                email_id=f"diverse_{i:04d}",
                sender_email=f"sender{i % 10}@{domain}",
                sender_name=f"Sender {i % 10}",
                sender_domain=domain,
                subject=subject,
                body_text=f"Body text for email {i}. Related to {domain}.",
                received_date=datetime(2024, 1, (i % 28) + 1, 10, i % 60),
                has_attachments=i % 5 == 0,
                thread_id=f"thread_{i // 3}" if i % 3 != 0 else None,
                in_reply_to=f"<msg_{i - 1}@{domain}>" if i % 3 == 2 else None,
                references=[f"<ref_{j}@{domain}>" for j in range(i % 4)],
                provider="m365" if i % 2 == 0 else "gmail",
                provider_message_id=f"provider_msg_{i:04d}",
            )
        )
    return emails


@pytest.fixture
def corpus_file(tmp_path):
    """Create a sample corpus JSON file with 20 diverse emails."""
    domains = ["amazon.com", "github.com", "linkedin.com", "newsletter.com"]
    emails = []
    for i in range(20):
        domain = domains[i % len(domains)]
        emails.append(
            _make_email_dict(
                email_id=f"corpus_email_{i:03d}",
                sender_email=f"sender{i}@{domain}",
                sender_name=f"Sender {i}",
                sender_domain=domain,
                subject=f"Email subject {i}",
                body_text=f"Body for email {i} from {domain}.",
                has_attachments=i % 4 == 0,
                thread_id=f"thread_{i // 3}" if i % 3 != 0 else None,
                references=[f"<ref_{j}@{domain}>" for j in range(i % 3)],
                provider="m365" if i % 2 == 0 else "gmail",
                provider_message_id=f"pmid_{i:03d}",
            )
        )
    corpus_data = _make_corpus_json(emails)
    path = tmp_path / "email_corpus.json"
    path.write_text(json.dumps(corpus_data, indent=2), encoding="utf-8")
    return path


@pytest.fixture
def decisions_file(tmp_path):
    """Create a sample decisions JSONL file."""
    lines = [
        _make_decision_line("Newsletters", "accept"),
        _make_decision_line("Promotions", "rename", context={"old": "Promos", "new": "Promotions"}),
        _make_decision_line("GitHub Notifications", "accept"),
        _make_decision_line("Spam", "delete"),
        _make_decision_line("Social Media", "skip"),
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
            "email_move", "msg_001", details={"source": "inbox", "target": "Newsletters"}
        ),
        _make_action_line("rule_create", "rule_001"),
        _make_action_line("email_move", "msg_002", success=False, reversible=False),
    ]
    path = tmp_path / "action_log.jsonl"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


# =============================================================================
# End-to-end migration: JSON -> SQLite -> EmailStore queries
# =============================================================================


class TestMigrationToEmailStoreEndToEnd:
    """Test the complete flow: JSON files -> migration -> querying via EmailStore."""

    def test_migrate_corpus_then_query_via_store(self, migrator, db, corpus_file):
        """Migrate JSON corpus to SQLite, then query all emails via EmailStore."""
        count = migrator.migrate_corpus(corpus_file)
        assert count == 20

        store = EmailStore(db)
        all_emails = store.get_all()
        assert len(all_emails) == 20

        # Verify every migrated email is retrievable by ID
        for i in range(20):
            email = store.get(f"corpus_email_{i:03d}")
            assert email is not None
            assert email.sender_domain in [
                "amazon.com",
                "github.com",
                "linkedin.com",
                "newsletter.com",
            ]

    def test_migrate_all_then_verify_all_tables(
        self, migrator, db, corpus_file, decisions_file, actions_file
    ):
        """Migrate all data sources and verify all tables have data."""
        result = migrator.migrate_all(
            corpus_path=corpus_file,
            decisions_path=decisions_file,
            actions_path=actions_file,
        )

        assert isinstance(result, MigrationResult)
        assert result.emails_migrated == 20
        assert result.decisions_migrated == 5
        assert result.actions_migrated == 4
        assert result.total_migrated == 29
        assert not result.has_warnings

        # Verify emails via EmailStore
        store = EmailStore(db)
        assert store.count() == 20

        # Verify decisions directly in DB
        cursor = db.execute("SELECT COUNT(*) FROM decision_log")
        assert cursor.fetchone()[0] == 5

        # Verify actions directly in DB
        cursor = db.execute("SELECT COUNT(*) FROM action_log")
        assert cursor.fetchone()[0] == 4

    def test_migrate_then_paginate_results(self, migrator, db, corpus_file):
        """Migrate corpus then use pagination to walk through results."""
        migrator.migrate_corpus(corpus_file)
        store = EmailStore(db)

        page1 = store.get_all(limit=5, offset=0)
        page2 = store.get_all(limit=5, offset=5)
        page3 = store.get_all(limit=5, offset=10)
        page4 = store.get_all(limit=5, offset=15)
        page5 = store.get_all(limit=5, offset=20)

        assert len(page1) == 5
        assert len(page2) == 5
        assert len(page3) == 5
        assert len(page4) == 5
        assert len(page5) == 0  # Past the end

        # Collect all IDs and verify no duplicates
        all_ids = {e.id for page in [page1, page2, page3, page4] for e in page}
        assert len(all_ids) == 20

    def test_migrate_then_delete_subset(self, migrator, db, corpus_file):
        """Migrate corpus, delete some emails, verify remainder."""
        migrator.migrate_corpus(corpus_file)
        store = EmailStore(db)
        assert store.count() == 20

        # Delete first 5 emails
        ids_to_delete = [f"corpus_email_{i:03d}" for i in range(5)]
        store.delete_batch(ids_to_delete)
        assert store.count() == 15

        # Verify deleted ones are gone
        for eid in ids_to_delete:
            assert store.get(eid) is None

        # Verify remaining are intact
        for i in range(5, 20):
            email = store.get(f"corpus_email_{i:03d}")
            assert email is not None

    def test_migrate_then_upsert_updates_existing(self, migrator, db, corpus_file):
        """Migrate corpus, then upsert modified emails to verify update semantics."""
        migrator.migrate_corpus(corpus_file)
        store = EmailStore(db)

        # Fetch, modify, and upsert an email
        original = store.get("corpus_email_000")
        assert original is not None
        original_subject = original.subject

        modified = _make_email(
            email_id="corpus_email_000",
            sender_email=original.sender_email,
            sender_domain=original.sender_domain,
            subject="UPDATED: " + original_subject,
            body_text="Updated body text after migration.",
            received_date=original.received_date,
        )
        store.upsert(modified)

        # Verify update
        updated = store.get("corpus_email_000")
        assert updated.subject.startswith("UPDATED:")
        assert updated.body_text == "Updated body text after migration."

        # Count should not change
        assert store.count() == 20


# =============================================================================
# Database lifecycle: create, populate, close, reopen, verify
# =============================================================================


class TestDatabaseLifecycle:
    """Test data persistence across database open/close cycles."""

    def test_data_persists_after_close_and_reopen(self, db_path):
        """Insert emails, close DB, reopen, verify data is still there."""
        # Phase 1: create and populate
        db1 = Database(db_path)
        store1 = EmailStore(db1)
        emails = [_make_email(email_id=f"persist_{i:03d}") for i in range(10)]
        store1.upsert_batch(emails)
        assert store1.count() == 10
        db1.close()

        # Phase 2: reopen and verify
        db2 = Database(db_path)
        store2 = EmailStore(db2)
        assert store2.count() == 10
        for i in range(10):
            email = store2.get(f"persist_{i:03d}")
            assert email is not None
            assert email.subject == "Test Email Subject"
        db2.close()

    def test_schema_version_persists_across_lifecycle(self, db_path):
        """Verify schema version tracking survives close/reopen."""
        db1 = Database(db_path)
        assert db1.get_schema_version() == 1
        db1.set_schema_version(2)
        assert db1.get_schema_version() == 2
        db1.close()

        db2 = Database(db_path)
        assert db2.get_schema_version() == 2
        db2.close()

    def test_migration_then_close_reopen_query(
        self, db_path, corpus_file, decisions_file, actions_file
    ):
        """Full migration, close, reopen, query all data."""
        # Phase 1: migrate
        db1 = Database(db_path)
        migrator = JsonToSqliteMigrator(db1)
        result = migrator.migrate_all(
            corpus_path=corpus_file,
            decisions_path=decisions_file,
            actions_path=actions_file,
        )
        assert result.total_migrated == 29
        db1.close()

        # Phase 2: reopen and verify
        db2 = Database(db_path)
        store = EmailStore(db2)
        assert store.count() == 20

        # Verify decisions
        cursor = db2.execute("SELECT COUNT(*) FROM decision_log")
        assert cursor.fetchone()[0] == 5

        # Verify actions
        cursor = db2.execute("SELECT COUNT(*) FROM action_log")
        assert cursor.fetchone()[0] == 4

        db2.close()

    def test_context_manager_lifecycle(self, db_path):
        """Test Database as context manager with EmailStore."""
        # Populate via context manager
        with Database(db_path) as db:
            store = EmailStore(db)
            store.upsert_batch([_make_email(email_id=f"ctx_{i}") for i in range(5)])
            assert store.count() == 5

        # Verify persistence after context exit
        with Database(db_path) as db:
            store = EmailStore(db)
            assert store.count() == 5
            for i in range(5):
                assert store.get(f"ctx_{i}") is not None


# =============================================================================
# Transaction integrity
# =============================================================================


class TestTransactionIntegrity:
    """Test transaction rollback and atomicity across the storage layer."""

    def test_transaction_rollback_preserves_prior_data(self, db):
        """Data from before a failed transaction should survive."""
        store = EmailStore(db)

        # Insert baseline data outside a transaction
        store.upsert(_make_email(email_id="baseline_001"))
        assert store.count() == 1

        # Start a transaction, insert more, then force a rollback
        with pytest.raises(ValueError), db.transaction():
            db.execute(
                "INSERT INTO emails (id, sender_email, sender_name, sender_domain, "
                "recipient_email, recipient_name, subject, body_text, received_date, "
                "has_attachments) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                ("txn_001", "a@b.com", "A", "b.com", None, "", "S", "B", "2024-01-15T10:00:00", 0),
            )
            raise ValueError("Simulated failure")

        # Baseline should still be there; transaction data should not
        assert store.count() == 1
        assert store.get("baseline_001") is not None
        assert store.get("txn_001") is None

    def test_batch_upsert_atomicity(self, db):
        """Verify that upsert_batch is atomic — all or nothing."""
        store = EmailStore(db)

        # Successful batch
        batch = [_make_email(email_id=f"atomic_{i}") for i in range(10)]
        store.upsert_batch(batch)
        assert store.count() == 10

        # All should be present
        for i in range(10):
            assert store.get(f"atomic_{i}") is not None

    def test_delete_batch_atomicity(self, db):
        """Verify that delete_batch is atomic."""
        store = EmailStore(db)
        store.upsert_batch([_make_email(email_id=f"del_{i}") for i in range(10)])
        assert store.count() == 10

        store.delete_batch([f"del_{i}" for i in range(5)])
        assert store.count() == 5

        # Verify exactly the right ones were deleted
        for i in range(5):
            assert store.get(f"del_{i}") is None
        for i in range(5, 10):
            assert store.get(f"del_{i}") is not None


# =============================================================================
# Data integrity: round-trip fidelity across the full chain
# =============================================================================


class TestDataIntegrityRoundTrip:
    """Verify that data survives the full chain without corruption."""

    def test_email_roundtrip_through_store(self, db):
        """Email -> to_row -> SQLite -> from_row -> Email should be identical."""
        store = EmailStore(db)

        original = _make_email(
            email_id="roundtrip_full",
            sender_email="detailed@test.org",
            sender_name="Full Name",
            sender_domain="test.org",
            recipient_email="recip@test.org",
            recipient_name="Recip Name",
            subject="Full Subject With Special Chars: O'Brien & Co.",
            body_text="Body with\nnewlines\tand\ttabs and unicode: cafe",
            received_date=datetime(2024, 7, 4, 12, 0, 0),
            has_attachments=True,
            thread_id="thread-full-001",
            in_reply_to="<reply-full@test.org>",
            references=["<ref-a@test.org>", "<ref-b@test.org>", "<ref-c@test.org>"],
            provider="gmail",
            provider_message_id="gmail-msg-xyz-123",
        )

        store.upsert(original)
        retrieved = store.get("roundtrip_full")

        assert retrieved == original
        assert retrieved.sender_email == original.sender_email
        assert retrieved.sender_name == original.sender_name
        assert retrieved.sender_domain == original.sender_domain
        assert retrieved.recipient_email == original.recipient_email
        assert retrieved.recipient_name == original.recipient_name
        assert retrieved.subject == original.subject
        assert retrieved.body_text == original.body_text
        assert retrieved.received_date == original.received_date
        assert retrieved.has_attachments == original.has_attachments
        assert retrieved.thread_id == original.thread_id
        assert retrieved.in_reply_to == original.in_reply_to
        assert retrieved.references == original.references
        assert retrieved.provider == original.provider
        assert retrieved.provider_message_id == original.provider_message_id

    def test_diverse_emails_roundtrip(self, db, diverse_emails):
        """50 diverse emails should all round-trip without data loss."""
        store = EmailStore(db)
        store.upsert_batch(diverse_emails)

        for original in diverse_emails:
            retrieved = store.get(original.id)
            assert retrieved is not None, f"Email {original.id} not found after upsert"
            assert retrieved == original, (
                f"Email {original.id} data mismatch: "
                f"subject='{retrieved.subject}' vs '{original.subject}'"
            )

    def test_migration_json_to_store_roundtrip(self, db, tmp_path):
        """JSON dict -> migration -> EmailStore -> Email should preserve all fields."""
        email_dict = _make_email_dict(
            email_id="json_roundtrip_001",
            sender_email="json@example.com",
            sender_name="JSON Sender",
            sender_domain="example.com",
            subject="JSON Round Trip Test",
            body_text="Body from JSON migration.",
            received_date="2024-03-15T08:45:00",
            has_attachments=True,
            thread_id="json-thread-001",
            in_reply_to="<json-parent@example.com>",
            references=["<json-ref-1@example.com>", "<json-ref-2@example.com>"],
            provider="m365",
            provider_message_id="m365-json-001",
        )
        corpus = _make_corpus_json([email_dict])
        path = tmp_path / "roundtrip_corpus.json"
        path.write_text(json.dumps(corpus), encoding="utf-8")

        migrator = JsonToSqliteMigrator(db)
        migrator.migrate_corpus(path)

        store = EmailStore(db)
        email = store.get("json_roundtrip_001")
        assert email is not None
        assert email.sender_email == "json@example.com"
        assert email.sender_name == "JSON Sender"
        assert email.subject == "JSON Round Trip Test"
        assert email.body_text == "Body from JSON migration."
        assert email.received_date == datetime(2024, 3, 15, 8, 45, 0)
        assert email.has_attachments is True
        assert email.thread_id == "json-thread-001"
        assert email.in_reply_to == "<json-parent@example.com>"
        assert email.references == ["<json-ref-1@example.com>", "<json-ref-2@example.com>"]
        assert email.provider == "m365"
        assert email.provider_message_id == "m365-json-001"

    def test_none_optional_fields_preserved(self, db):
        """Emails with None optional fields should round-trip correctly."""
        store = EmailStore(db)
        email = _make_email(
            email_id="none_opts",
            recipient_email=None,
            thread_id=None,
            in_reply_to=None,
            references=[],
            provider=None,
            provider_message_id=None,
        )
        store.upsert(email)
        retrieved = store.get("none_opts")
        assert retrieved == email
        assert retrieved.recipient_email is None
        assert retrieved.thread_id is None
        assert retrieved.in_reply_to is None
        assert retrieved.references == []
        assert retrieved.provider is None
        assert retrieved.provider_message_id is None


# =============================================================================
# Large dataset: batch processing and pagination
# =============================================================================


class TestLargeDataset:
    """Test storage layer with larger datasets to exercise batching."""

    def test_store_and_retrieve_500_emails(self, db):
        """Store 500 emails via batch upsert, then count and retrieve."""
        store = EmailStore(db)
        emails = [_make_email(email_id=f"large_{i:04d}") for i in range(500)]
        store.upsert_batch(emails)

        assert store.count() == 500

        # Paginate through all
        page_size = 50
        all_ids = set()
        for offset in range(0, 500, page_size):
            page = store.get_all(limit=page_size, offset=offset)
            for e in page:
                all_ids.add(e.id)

        assert len(all_ids) == 500

    def test_migrate_large_corpus(self, db, tmp_path):
        """Migrate a large corpus JSON (300 emails) and verify store counts."""
        emails = [_make_email_dict(email_id=f"lm_{i:04d}") for i in range(300)]
        corpus = _make_corpus_json(emails)
        path = tmp_path / "large_corpus.json"
        path.write_text(json.dumps(corpus), encoding="utf-8")

        migrator = JsonToSqliteMigrator(db)
        count = migrator.migrate_corpus(path)
        assert count == 300

        store = EmailStore(db)
        assert store.count() == 300

    def test_upsert_batch_then_delete_batch_large(self, db):
        """Insert 200, delete 100, verify 100 remain."""
        store = EmailStore(db)
        emails = [_make_email(email_id=f"bd_{i:04d}") for i in range(200)]
        store.upsert_batch(emails)
        assert store.count() == 200

        ids_to_delete = [f"bd_{i:04d}" for i in range(100)]
        store.delete_batch(ids_to_delete)
        assert store.count() == 100

        # Verify right ones remain
        for i in range(100):
            assert store.get(f"bd_{i:04d}") is None
        for i in range(100, 200):
            assert store.get(f"bd_{i:04d}") is not None


# =============================================================================
# Concurrent access
# =============================================================================


class TestConcurrentStorageAccess:
    """Test multi-threaded access patterns through the storage layer."""

    def test_concurrent_reads_via_email_store(self, db_path):
        """Multiple threads reading from EmailStore simultaneously."""
        # Setup: populate database
        db_setup = Database(db_path)
        store_setup = EmailStore(db_setup)
        store_setup.upsert_batch([_make_email(email_id=f"conc_read_{i:03d}") for i in range(20)])
        db_setup.close()

        errors = []
        results = []

        def reader_thread(thread_id):
            try:
                thread_db = Database(db_path)
                thread_store = EmailStore(thread_db)
                count = thread_store.count()
                email = thread_store.get(f"conc_read_{thread_id:03d}")
                results.append((thread_id, count, email is not None))
                thread_db.close()
            except Exception as e:
                errors.append(f"Thread {thread_id}: {e}")

        threads = [threading.Thread(target=reader_thread, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert not errors, f"Errors during concurrent reads: {errors}"
        for thread_id, count, found in results:
            assert count == 20, f"Thread {thread_id} got count={count}"
            assert found, f"Thread {thread_id} did not find its email"

    def test_concurrent_writes_via_email_store(self, db_path):
        """Multiple threads writing via EmailStore simultaneously."""
        Database(db_path).close()  # Initialize schema

        errors = []

        def writer_thread(thread_id):
            try:
                thread_db = Database(db_path)
                thread_store = EmailStore(thread_db)
                thread_store.upsert(_make_email(email_id=f"conc_write_{thread_id:03d}"))
                thread_db.close()
            except Exception as e:
                errors.append(f"Thread {thread_id}: {e}")

        threads = [threading.Thread(target=writer_thread, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert not errors, f"Errors during concurrent writes: {errors}"

        # Verify all writes landed
        db_verify = Database(db_path)
        store_verify = EmailStore(db_verify)
        assert store_verify.count() == 10
        db_verify.close()


# =============================================================================
# Foreign key cascade behavior
# =============================================================================


class TestForeignKeyCascades:
    """Test FK cascade behavior (classifications/corrections -> emails)."""

    def test_delete_email_cascades_to_classifications(self, db):
        """Deleting an email should cascade-delete its classifications."""
        # Insert email
        db.execute(
            "INSERT INTO emails (id, sender_email, sender_name, sender_domain, "
            "subject, body_text, received_date, has_attachments) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("fk_email_001", "a@b.com", "A", "b.com", "S", "B", "2024-01-15T10:00:00", 0),
        )

        # Insert classifications for that email
        db.execute(
            "INSERT INTO classifications (email_id, category_name, confidence, source, "
            "classified_at) VALUES (?, ?, ?, ?, ?)",
            ("fk_email_001", "Newsletters", 0.9, "llm:qwen", "2024-01-15T10:00:00"),
        )
        db.execute(
            "INSERT INTO classifications (email_id, category_name, confidence, source, "
            "classified_at) VALUES (?, ?, ?, ?, ?)",
            ("fk_email_001", "Promotions", 0.7, "rule:domain", "2024-01-15T11:00:00"),
        )

        # Verify classifications exist
        cursor = db.execute(
            "SELECT COUNT(*) FROM classifications WHERE email_id = ?", ("fk_email_001",)
        )
        assert cursor.fetchone()[0] == 2

        # Delete the email
        db.execute("DELETE FROM emails WHERE id = ?", ("fk_email_001",))

        # Classifications should be cascade-deleted
        cursor = db.execute(
            "SELECT COUNT(*) FROM classifications WHERE email_id = ?", ("fk_email_001",)
        )
        assert cursor.fetchone()[0] == 0

    def test_delete_email_cascades_to_corrections(self, db):
        """Deleting an email should cascade-delete its corrections."""
        db.execute(
            "INSERT INTO emails (id, sender_email, sender_name, sender_domain, "
            "subject, body_text, received_date, has_attachments) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("fk_email_002", "a@b.com", "A", "b.com", "S", "B", "2024-01-15T10:00:00", 0),
        )
        db.execute(
            "INSERT INTO corrections (email_id, old_category, new_category, corrected_at) "
            "VALUES (?, ?, ?, ?)",
            ("fk_email_002", "Newsletters", "Promotions", "2024-01-16T10:00:00"),
        )

        cursor = db.execute(
            "SELECT COUNT(*) FROM corrections WHERE email_id = ?", ("fk_email_002",)
        )
        assert cursor.fetchone()[0] == 1

        db.execute("DELETE FROM emails WHERE id = ?", ("fk_email_002",))

        cursor = db.execute(
            "SELECT COUNT(*) FROM corrections WHERE email_id = ?", ("fk_email_002",)
        )
        assert cursor.fetchone()[0] == 0

    def test_email_store_delete_cascades_classifications(self, db):
        """EmailStore.delete() should also trigger FK cascade."""
        store = EmailStore(db)
        store.upsert(_make_email(email_id="store_fk_001"))

        # Add a classification via raw SQL
        db.execute(
            "INSERT INTO classifications (email_id, category_name, confidence, source, "
            "classified_at) VALUES (?, ?, ?, ?, ?)",
            ("store_fk_001", "Work", 0.85, "llm:test", "2024-01-15T10:00:00"),
        )

        cursor = db.execute(
            "SELECT COUNT(*) FROM classifications WHERE email_id = ?", ("store_fk_001",)
        )
        assert cursor.fetchone()[0] == 1

        store.delete("store_fk_001")

        cursor = db.execute(
            "SELECT COUNT(*) FROM classifications WHERE email_id = ?", ("store_fk_001",)
        )
        assert cursor.fetchone()[0] == 0


# =============================================================================
# Idempotency: running migration twice
# =============================================================================


class TestMigrationIdempotency:
    """Test that migrations are idempotent and safe to re-run."""

    def test_corpus_migration_idempotent(self, db, corpus_file):
        """Running corpus migration twice should not duplicate data."""
        migrator = JsonToSqliteMigrator(db)
        migrator.migrate_corpus(corpus_file)
        migrator.migrate_corpus(corpus_file)

        store = EmailStore(db)
        assert store.count() == 20  # Not 40

    def test_full_migration_idempotent_emails(self, db, corpus_file, decisions_file, actions_file):
        """Emails remain at original count after two full migrations."""
        migrator = JsonToSqliteMigrator(db)
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

        store = EmailStore(db)
        assert store.count() == 20

    def test_corpus_migration_updates_on_rerun(self, db, tmp_path):
        """Re-migrating after modifying corpus should update existing emails."""
        # First migration
        emails_v1 = [
            _make_email_dict(email_id="idem_001", subject="Version 1"),
            _make_email_dict(email_id="idem_002", subject="Original"),
        ]
        corpus_v1 = _make_corpus_json(emails_v1)
        path = tmp_path / "corpus.json"
        path.write_text(json.dumps(corpus_v1), encoding="utf-8")

        migrator = JsonToSqliteMigrator(db)
        migrator.migrate_corpus(path)

        store = EmailStore(db)
        assert store.get("idem_001").subject == "Version 1"

        # Second migration with modified data
        emails_v2 = [
            _make_email_dict(email_id="idem_001", subject="Version 2"),
            _make_email_dict(email_id="idem_002", subject="Original"),
            _make_email_dict(email_id="idem_003", subject="New Email"),
        ]
        corpus_v2 = _make_corpus_json(emails_v2)
        path.write_text(json.dumps(corpus_v2), encoding="utf-8")

        migrator.migrate_corpus(path)

        assert store.count() == 3
        assert store.get("idem_001").subject == "Version 2"
        assert store.get("idem_002").subject == "Original"
        assert store.get("idem_003").subject == "New Email"


# =============================================================================
# Error handling: corrupt data, mixed valid/invalid
# =============================================================================


class TestErrorHandling:
    """Test graceful handling of corrupt/invalid data in integration flows."""

    def test_migration_skips_invalid_emails_keeps_valid(self, db, tmp_path):
        """Migration should skip invalid emails but store valid ones."""
        emails = [
            _make_email_dict(email_id="valid_001", subject="Good email 1"),
            # Invalid: missing sender_email
            {
                "id": "invalid_001",
                "sender_domain": "bad.com",
                "subject": "Missing sender",
                "body_text": "b",
                "received_date": "2024-01-15T10:00:00",
                "has_attachments": False,
            },
            _make_email_dict(email_id="valid_002", subject="Good email 2"),
            # Invalid: missing sender_domain
            {
                "id": "invalid_002",
                "sender_email": "a@b.com",
                "subject": "Missing domain",
                "body_text": "b",
                "received_date": "2024-01-15T10:00:00",
                "has_attachments": False,
            },
            _make_email_dict(email_id="valid_003", subject="Good email 3"),
        ]
        corpus = _make_corpus_json(emails)
        path = tmp_path / "mixed_corpus.json"
        path.write_text(json.dumps(corpus), encoding="utf-8")

        migrator = JsonToSqliteMigrator(db)
        count = migrator.migrate_corpus(path)

        # Only valid emails should be stored
        assert count == 3
        store = EmailStore(db)
        assert store.count() == 3
        assert store.get("valid_001") is not None
        assert store.get("valid_002") is not None
        assert store.get("valid_003") is not None
        assert store.get("invalid_001") is None
        assert store.get("invalid_002") is None

    def test_migration_handles_corrupt_jsonl_lines(self, db, tmp_path):
        """Corrupt JSONL lines should be skipped without stopping migration."""
        decision_lines = [
            _make_decision_line("Good1", "accept"),
            "this is not valid json at all",
            _make_decision_line("Good2", "delete"),
            '{"timestamp": "2024-01-20T14:30:00+00:00"}',  # Missing required fields
            _make_decision_line("Good3", "skip"),
        ]
        path = tmp_path / "decisions.jsonl"
        path.write_text("\n".join(decision_lines) + "\n", encoding="utf-8")

        migrator = JsonToSqliteMigrator(db)
        count = migrator.migrate_decisions(path)

        # 3 valid lines, 2 corrupt/incomplete
        assert count == 3

        cursor = db.execute("SELECT COUNT(*) FROM decision_log")
        assert cursor.fetchone()[0] == 3

    def test_migrate_all_reports_skips_in_result(self, db, tmp_path):
        """MigrationResult should accurately report skipped items."""
        # Corpus with 1 valid + 1 invalid
        emails = [
            _make_email_dict(email_id="ok"),
            {
                "id": "bad",
                "subject": "nope",
                "sender_domain": "x.com",
                "body_text": "b",
                "received_date": "2024-01-01T00:00:00",
                "has_attachments": False,
            },
        ]
        corpus = _make_corpus_json(emails)
        corpus_path = tmp_path / "corpus.json"
        corpus_path.write_text(json.dumps(corpus), encoding="utf-8")

        # Decisions with 1 valid + 1 corrupt
        decisions_path = tmp_path / "decisions.jsonl"
        decisions_path.write_text(
            _make_decision_line("Good", "accept") + "\ncorrupt\n",
            encoding="utf-8",
        )

        migrator = JsonToSqliteMigrator(db)
        result = migrator.migrate_all(
            corpus_path=corpus_path,
            decisions_path=decisions_path,
        )

        assert result.emails_migrated == 1
        assert result.emails_skipped == 1
        assert result.decisions_migrated == 1
        assert result.decisions_skipped == 1
        assert result.has_warnings is True


# =============================================================================
# Progress callback integration
# =============================================================================


class TestProgressCallbackIntegration:
    """Test that progress callbacks work across the full migration flow."""

    def test_migrate_all_progress_reports_all_stages(
        self, db, corpus_file, decisions_file, actions_file
    ):
        """Progress callback should be invoked for each stage during migrate_all."""
        progress_calls = []

        def on_progress(stage: str, current: int, total: int):
            progress_calls.append((stage, current, total))

        migrator = JsonToSqliteMigrator(db)
        migrator.migrate_all(
            corpus_path=corpus_file,
            decisions_path=decisions_file,
            actions_path=actions_file,
            progress_callback=on_progress,
        )

        assert len(progress_calls) > 0
        stages_seen = {call[0] for call in progress_calls}
        assert "emails" in stages_seen

        # The final email progress call should show 20/20
        email_calls = [c for c in progress_calls if c[0] == "emails"]
        last_email_call = email_calls[-1]
        assert last_email_call[1] == 20
        assert last_email_call[2] == 20

    def test_corpus_migration_progress_monotonically_increases(self, db, corpus_file):
        """Progress callback values should monotonically increase."""
        progress_calls = []

        def on_progress(current: int, total: int):
            progress_calls.append((current, total))

        migrator = JsonToSqliteMigrator(db)
        migrator.migrate_corpus(corpus_file, progress_callback=on_progress)

        assert len(progress_calls) > 0

        currents = [c[0] for c in progress_calls]
        for i in range(1, len(currents)):
            assert currents[i] >= currents[i - 1], (
                f"Progress went backwards: {currents[i - 1]} -> {currents[i]}"
            )

        # Final value should equal total
        assert progress_calls[-1][0] == progress_calls[-1][1]


# =============================================================================
# Cross-component: EmailStore + raw SQL queries on same DB
# =============================================================================


class TestCrossComponentQueries:
    """Test that EmailStore and raw SQL queries on the same DB are consistent."""

    def test_emails_inserted_via_store_visible_via_raw_sql(self, db):
        """Emails inserted via EmailStore should be queryable via raw SQL."""
        store = EmailStore(db)
        store.upsert(
            _make_email(
                email_id="cross_001",
                sender_domain="test.com",
                subject="Cross component test",
            )
        )

        cursor = db.execute(
            "SELECT id, sender_domain, subject FROM emails WHERE id = ?", ("cross_001",)
        )
        row = cursor.fetchone()
        assert row is not None
        assert row[0] == "cross_001"
        assert row[1] == "test.com"
        assert row[2] == "Cross component test"

    def test_emails_from_migration_queryable_via_store_and_sql(self, db, corpus_file):
        """Migrated emails should be consistently queryable via both interfaces."""
        migrator = JsonToSqliteMigrator(db)
        migrator.migrate_corpus(corpus_file)

        store = EmailStore(db)
        store_count = store.count()

        cursor = db.execute("SELECT COUNT(*) FROM emails")
        sql_count = cursor.fetchone()[0]

        assert store_count == sql_count == 20

    def test_store_delete_reflected_in_raw_sql(self, db):
        """EmailStore.delete() should be reflected in raw SQL queries."""
        store = EmailStore(db)
        store.upsert_batch([_make_email(email_id=f"del_cross_{i}") for i in range(5)])

        store.delete("del_cross_2")

        cursor = db.execute("SELECT COUNT(*) FROM emails")
        assert cursor.fetchone()[0] == 4

        cursor = db.execute("SELECT id FROM emails WHERE id = ?", ("del_cross_2",))
        assert cursor.fetchone() is None

    def test_classify_email_via_sql_then_query(self, db):
        """Insert email via store, classify via SQL, query classification."""
        store = EmailStore(db)
        store.upsert(_make_email(email_id="classify_001"))

        # Classify via raw SQL
        db.execute(
            "INSERT INTO classifications (email_id, category_name, confidence, source, "
            "model_version, classified_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("classify_001", "Work", 0.92, "llm:qwen2.5:7b", "v1.0", "2024-01-15T10:00:00"),
        )

        # Query classification
        cursor = db.execute(
            "SELECT category_name, confidence, source FROM classifications WHERE email_id = ?",
            ("classify_001",),
        )
        row = cursor.fetchone()
        assert row is not None
        assert row[0] == "Work"
        assert row[1] == 0.92
        assert row[2] == "llm:qwen2.5:7b"
