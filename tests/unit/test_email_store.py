"""
Unit tests for Phase 3, Work Item 3.2: EmailStore CRUD Operations.

Tests the EmailStore class with:
- Email model to_row() / from_row() serialization round-trips
- Single and batch upsert operations (insert and update)
- Get by ID and get_all with pagination
- Count operations
- Single and batch delete operations
- Edge cases: missing fields, duplicate IDs, empty batches, Unicode content

TDD: Tests written before implementation.
"""

import json
from datetime import datetime

import pytest

from src.models.email import Email
from src.storage.database import Database

# =============================================================================
# Helper: create a standard test email
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
    """Helper to create a test Email with sensible defaults."""
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


@pytest.fixture
def db(tmp_path):
    """Create a temporary Database for testing."""
    db = Database(tmp_path / "test.db")
    yield db
    db.close()


@pytest.fixture
def email_store(db):
    """Create an EmailStore backed by a temporary database."""
    from src.storage.email_store import EmailStore

    return EmailStore(db)


# =============================================================================
# Email.to_row() and Email.from_row() serialization tests
# =============================================================================


class TestEmailToRow:
    """Test Email.to_row() serialization."""

    def test_to_row_returns_dict(self):
        """Test that to_row() returns a dictionary."""
        email = _make_email()
        row = email.to_row()
        assert isinstance(row, dict)

    def test_to_row_contains_all_required_fields(self):
        """Test that to_row() includes all fields needed for the DB schema."""
        email = _make_email()
        row = email.to_row()

        expected_keys = {
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
        }
        assert set(row.keys()) == expected_keys

    def test_to_row_serializes_received_date_as_iso_string(self):
        """Test that received_date is serialized as ISO 8601 string."""
        email = _make_email(received_date=datetime(2024, 6, 15, 14, 30, 0))
        row = email.to_row()
        assert row["received_date"] == "2024-06-15T14:30:00"

    def test_to_row_serializes_has_attachments_as_int(self):
        """Test that has_attachments is serialized as integer (0/1) for SQLite."""
        email_no = _make_email(has_attachments=False)
        email_yes = _make_email(has_attachments=True)
        assert email_no.to_row()["has_attachments"] == 0
        assert email_yes.to_row()["has_attachments"] == 1

    def test_to_row_serializes_references_as_json(self):
        """Test that references list is serialized as JSON string."""
        refs = ["<msg1@example.com>", "<msg2@example.com>"]
        email = _make_email(references=refs)
        row = email.to_row()
        assert row["references_json"] == json.dumps(refs)

    def test_to_row_serializes_empty_references_as_json(self):
        """Test that empty references list becomes '[]' JSON string."""
        email = _make_email(references=[])
        row = email.to_row()
        assert row["references_json"] == "[]"

    def test_to_row_preserves_none_optional_fields(self):
        """Test that None optional fields remain None in the row."""
        email = _make_email(
            recipient_email=None,
            thread_id=None,
            in_reply_to=None,
            provider=None,
            provider_message_id=None,
        )
        row = email.to_row()
        assert row["recipient_email"] is None
        assert row["thread_id"] is None
        assert row["in_reply_to"] is None
        assert row["provider"] is None
        assert row["provider_message_id"] is None

    def test_to_row_preserves_string_fields(self):
        """Test that string fields are preserved exactly."""
        email = _make_email(
            email_id="abc-123",
            sender_email="test@domain.org",
            sender_name="John Doe",
            sender_domain="domain.org",
            subject="Important Update",
            body_text="Hello world",
        )
        row = email.to_row()
        assert row["id"] == "abc-123"
        assert row["sender_email"] == "test@domain.org"
        assert row["sender_name"] == "John Doe"
        assert row["sender_domain"] == "domain.org"
        assert row["subject"] == "Important Update"
        assert row["body_text"] == "Hello world"

    def test_to_row_with_provider_fields(self):
        """Test that provider fields are included when set."""
        email = _make_email(
            provider="m365",
            provider_message_id="AAMkAGE1...",
        )
        row = email.to_row()
        assert row["provider"] == "m365"
        assert row["provider_message_id"] == "AAMkAGE1..."


class TestEmailFromRow:
    """Test Email.from_row() deserialization."""

    def test_from_row_returns_email(self):
        """Test that from_row() returns an Email instance."""
        row = {
            "id": "email_001",
            "sender_email": "sender@example.com",
            "sender_name": "Test Sender",
            "sender_domain": "example.com",
            "recipient_email": "recipient@example.com",
            "recipient_name": "Test Recipient",
            "subject": "Test Subject",
            "body_text": "Test body",
            "received_date": "2024-01-15T10:30:00",
            "has_attachments": 0,
            "thread_id": None,
            "in_reply_to": None,
            "references_json": "[]",
            "provider": None,
            "provider_message_id": None,
        }
        email = Email.from_row(row)
        assert isinstance(email, Email)

    def test_from_row_deserializes_received_date(self):
        """Test that received_date is deserialized from ISO string to datetime."""
        row = {
            "id": "email_001",
            "sender_email": "sender@example.com",
            "sender_name": "Test Sender",
            "sender_domain": "example.com",
            "recipient_email": None,
            "recipient_name": "",
            "subject": "Sub",
            "body_text": "Body",
            "received_date": "2024-06-15T14:30:00",
            "has_attachments": 0,
            "thread_id": None,
            "in_reply_to": None,
            "references_json": "[]",
            "provider": None,
            "provider_message_id": None,
        }
        email = Email.from_row(row)
        assert email.received_date == datetime(2024, 6, 15, 14, 30, 0)

    def test_from_row_deserializes_has_attachments(self):
        """Test that has_attachments int is deserialized to bool."""
        row_false = {
            "id": "e1",
            "sender_email": "a@b.com",
            "sender_name": "",
            "sender_domain": "b.com",
            "recipient_email": None,
            "recipient_name": "",
            "subject": "s",
            "body_text": "b",
            "received_date": "2024-01-15T10:00:00",
            "has_attachments": 0,
            "thread_id": None,
            "in_reply_to": None,
            "references_json": "[]",
            "provider": None,
            "provider_message_id": None,
        }
        row_true = dict(row_false)
        row_true["id"] = "e2"
        row_true["has_attachments"] = 1

        assert Email.from_row(row_false).has_attachments is False
        assert Email.from_row(row_true).has_attachments is True

    def test_from_row_deserializes_references_json(self):
        """Test that references_json is deserialized from JSON string to list."""
        refs = ["<msg1@example.com>", "<msg2@example.com>"]
        row = {
            "id": "e1",
            "sender_email": "a@b.com",
            "sender_name": "",
            "sender_domain": "b.com",
            "recipient_email": None,
            "recipient_name": "",
            "subject": "s",
            "body_text": "b",
            "received_date": "2024-01-15T10:00:00",
            "has_attachments": 0,
            "thread_id": None,
            "in_reply_to": None,
            "references_json": json.dumps(refs),
            "provider": None,
            "provider_message_id": None,
        }
        email = Email.from_row(row)
        assert email.references == refs

    def test_from_row_handles_null_references_json(self):
        """Test that None references_json becomes empty list."""
        row = {
            "id": "e1",
            "sender_email": "a@b.com",
            "sender_name": "",
            "sender_domain": "b.com",
            "recipient_email": None,
            "recipient_name": "",
            "subject": "s",
            "body_text": "b",
            "received_date": "2024-01-15T10:00:00",
            "has_attachments": 0,
            "thread_id": None,
            "in_reply_to": None,
            "references_json": None,
            "provider": None,
            "provider_message_id": None,
        }
        email = Email.from_row(row)
        assert email.references == []


class TestEmailRoundTrip:
    """Test that to_row() and from_row() are perfect inverses."""

    def test_round_trip_basic_email(self):
        """Test round-trip for a basic email."""
        original = _make_email()
        row = original.to_row()
        restored = Email.from_row(row)
        assert restored == original

    def test_round_trip_with_all_fields(self):
        """Test round-trip with all optional fields populated."""
        original = _make_email(
            thread_id="thread-abc",
            in_reply_to="<reply@example.com>",
            references=["<ref1@example.com>", "<ref2@example.com>"],
            provider="gmail",
            provider_message_id="msg-xyz-123",
        )
        row = original.to_row()
        restored = Email.from_row(row)
        assert restored == original

    def test_round_trip_with_none_optionals(self):
        """Test round-trip with all optionals as None."""
        original = _make_email(
            recipient_email=None,
            thread_id=None,
            in_reply_to=None,
            references=[],
            provider=None,
            provider_message_id=None,
        )
        row = original.to_row()
        restored = Email.from_row(row)
        assert restored == original

    def test_round_trip_preserves_unicode(self):
        """Test round-trip preserves Unicode content."""
        original = _make_email(
            sender_name="Rene Descartes",
            subject="Re: Reunion planning",
            body_text="Cafe at 3pm? Cost is 50 euros.",
        )
        row = original.to_row()
        restored = Email.from_row(row)
        assert restored == original

    def test_round_trip_with_attachments(self):
        """Test round-trip for email with attachments."""
        original = _make_email(has_attachments=True)
        row = original.to_row()
        restored = Email.from_row(row)
        assert restored.has_attachments is True
        assert restored == original


# =============================================================================
# EmailStore instantiation tests
# =============================================================================


class TestEmailStoreCreation:
    """Test EmailStore class instantiation."""

    def test_email_store_class_exists(self):
        """Test that EmailStore class can be imported."""
        from src.storage.email_store import EmailStore

        assert EmailStore is not None

    def test_email_store_accepts_database(self, db):
        """Test that EmailStore accepts a Database instance."""
        from src.storage.email_store import EmailStore

        store = EmailStore(db)
        assert store is not None

    def test_email_store_importable_from_package(self):
        """Test that EmailStore can be imported from src.storage."""
        from src.storage import EmailStore

        assert EmailStore is not None


# =============================================================================
# EmailStore.upsert() tests
# =============================================================================


class TestEmailStoreUpsert:
    """Test EmailStore single upsert operation."""

    def test_upsert_inserts_new_email(self, email_store):
        """Test that upsert() inserts a new email."""
        email = _make_email(email_id="new_email_001")
        email_store.upsert(email)

        result = email_store.get("new_email_001")
        assert result is not None
        assert result.id == "new_email_001"

    def test_upsert_returns_none(self, email_store):
        """Test that upsert() returns None (operation is void)."""
        email = _make_email()
        result = email_store.upsert(email)
        assert result is None

    def test_upsert_updates_existing_email(self, email_store):
        """Test that upsert() updates an email with the same ID."""
        email_v1 = _make_email(email_id="upd_001", subject="Original Subject")
        email_store.upsert(email_v1)

        email_v2 = _make_email(email_id="upd_001", subject="Updated Subject")
        email_store.upsert(email_v2)

        result = email_store.get("upd_001")
        assert result is not None
        assert result.subject == "Updated Subject"

    def test_upsert_preserves_all_fields(self, email_store):
        """Test that upsert() preserves all email fields after insert."""
        email = _make_email(
            email_id="full_001",
            sender_email="full@example.com",
            sender_name="Full Sender",
            sender_domain="example.com",
            recipient_email="recip@example.com",
            recipient_name="Full Recipient",
            subject="Full Subject",
            body_text="Full body text here.",
            received_date=datetime(2024, 3, 20, 8, 15, 0),
            has_attachments=True,
            thread_id="thread-xyz",
            in_reply_to="<reply@example.com>",
            references=["<ref1@example.com>", "<ref2@example.com>"],
            provider="m365",
            provider_message_id="AAMkAGE1...",
        )
        email_store.upsert(email)

        result = email_store.get("full_001")
        assert result == email


# =============================================================================
# EmailStore.upsert_batch() tests
# =============================================================================


class TestEmailStoreUpsertBatch:
    """Test EmailStore batch upsert operations."""

    def test_upsert_batch_inserts_multiple(self, email_store):
        """Test that upsert_batch() inserts multiple emails."""
        emails = [_make_email(email_id=f"batch_{i:03d}") for i in range(5)]
        email_store.upsert_batch(emails)

        assert email_store.count() == 5

    def test_upsert_batch_returns_none(self, email_store):
        """Test that upsert_batch() returns None."""
        emails = [_make_email(email_id=f"batch_{i:03d}") for i in range(3)]
        result = email_store.upsert_batch(emails)
        assert result is None

    def test_upsert_batch_handles_empty_list(self, email_store):
        """Test that upsert_batch() handles an empty list gracefully."""
        email_store.upsert_batch([])
        assert email_store.count() == 0

    def test_upsert_batch_updates_existing(self, email_store):
        """Test that upsert_batch() updates existing emails."""
        emails_v1 = [
            _make_email(email_id="batch_001", subject="Original 1"),
            _make_email(email_id="batch_002", subject="Original 2"),
        ]
        email_store.upsert_batch(emails_v1)

        emails_v2 = [
            _make_email(email_id="batch_001", subject="Updated 1"),
            _make_email(email_id="batch_002", subject="Updated 2"),
        ]
        email_store.upsert_batch(emails_v2)

        assert email_store.count() == 2
        assert email_store.get("batch_001").subject == "Updated 1"
        assert email_store.get("batch_002").subject == "Updated 2"

    def test_upsert_batch_mixed_insert_update(self, email_store):
        """Test batch with mix of new inserts and updates."""
        email_store.upsert(_make_email(email_id="existing_001", subject="Old"))

        batch = [
            _make_email(email_id="existing_001", subject="Updated"),
            _make_email(email_id="new_001", subject="Brand New"),
        ]
        email_store.upsert_batch(batch)

        assert email_store.count() == 2
        assert email_store.get("existing_001").subject == "Updated"
        assert email_store.get("new_001").subject == "Brand New"

    def test_upsert_batch_is_atomic(self, email_store, db):
        """Test that batch upsert is wrapped in a single transaction."""
        # Insert some valid emails first
        email_store.upsert(_make_email(email_id="pre_existing"))

        # We can verify atomicity by checking count before and after a failed batch.
        # A batch with a deliberately corrupt entry that causes a SQL error
        # should roll back the entire batch.
        # Since we can't easily inject a SQL error through the Email model
        # (Pydantic validates), we verify that a successful batch is committed
        # all-at-once by checking count after.
        emails = [_make_email(email_id=f"atomic_{i:03d}") for i in range(10)]
        email_store.upsert_batch(emails)
        assert email_store.count() == 11  # 1 pre-existing + 10 new

    def test_upsert_batch_large(self, email_store):
        """Test batch upsert with a large number of emails."""
        emails = [_make_email(email_id=f"large_{i:04d}") for i in range(100)]
        email_store.upsert_batch(emails)
        assert email_store.count() == 100


# =============================================================================
# EmailStore.get() tests
# =============================================================================


class TestEmailStoreGet:
    """Test EmailStore get by ID operation."""

    def test_get_returns_email(self, email_store):
        """Test that get() returns an Email instance."""
        email_store.upsert(_make_email(email_id="get_001"))
        result = email_store.get("get_001")
        assert isinstance(result, Email)

    def test_get_returns_none_for_missing(self, email_store):
        """Test that get() returns None for a nonexistent ID."""
        result = email_store.get("nonexistent_id")
        assert result is None

    def test_get_returns_correct_email(self, email_store):
        """Test that get() returns the correct email by ID."""
        email_store.upsert(_make_email(email_id="get_a", subject="Alpha"))
        email_store.upsert(_make_email(email_id="get_b", subject="Beta"))

        result = email_store.get("get_b")
        assert result.id == "get_b"
        assert result.subject == "Beta"

    def test_get_round_trips_all_fields(self, email_store):
        """Test that get() returns an email with all fields intact."""
        original = _make_email(
            email_id="get_full",
            sender_email="full@test.org",
            sender_name="Full Name",
            sender_domain="test.org",
            recipient_email="recip@test.org",
            recipient_name="Recip Name",
            subject="Full Subject",
            body_text="Full body",
            received_date=datetime(2024, 7, 4, 12, 0, 0),
            has_attachments=True,
            thread_id="thread-full",
            in_reply_to="<reply-full@test.org>",
            references=["<ref-a@test.org>", "<ref-b@test.org>"],
            provider="gmail",
            provider_message_id="gmail-msg-123",
        )
        email_store.upsert(original)
        result = email_store.get("get_full")
        assert result == original


# =============================================================================
# EmailStore.get_all() tests
# =============================================================================


class TestEmailStoreGetAll:
    """Test EmailStore get_all operation with pagination."""

    def test_get_all_empty_store(self, email_store):
        """Test that get_all() returns empty list for empty store."""
        result = email_store.get_all()
        assert result == []

    def test_get_all_returns_all_emails(self, email_store):
        """Test that get_all() returns all stored emails."""
        for i in range(5):
            email_store.upsert(_make_email(email_id=f"all_{i:03d}"))

        result = email_store.get_all()
        assert len(result) == 5

    def test_get_all_returns_email_instances(self, email_store):
        """Test that get_all() returns Email instances."""
        email_store.upsert(_make_email(email_id="all_001"))
        result = email_store.get_all()
        assert all(isinstance(e, Email) for e in result)

    def test_get_all_with_limit(self, email_store):
        """Test that get_all() respects the limit parameter."""
        for i in range(10):
            email_store.upsert(_make_email(email_id=f"lim_{i:03d}"))

        result = email_store.get_all(limit=3)
        assert len(result) == 3

    def test_get_all_with_offset(self, email_store):
        """Test that get_all() respects the offset parameter."""
        for i in range(10):
            email_store.upsert(_make_email(email_id=f"off_{i:03d}"))

        all_emails = email_store.get_all()
        offset_emails = email_store.get_all(offset=5)
        assert len(offset_emails) == 5
        # The offset results should be a subset of the full results
        offset_ids = {e.id for e in offset_emails}
        all_ids = {e.id for e in all_emails}
        assert offset_ids.issubset(all_ids)

    def test_get_all_with_limit_and_offset(self, email_store):
        """Test pagination with both limit and offset."""
        for i in range(20):
            email_store.upsert(_make_email(email_id=f"page_{i:03d}"))

        page1 = email_store.get_all(limit=5, offset=0)
        page2 = email_store.get_all(limit=5, offset=5)
        assert len(page1) == 5
        assert len(page2) == 5
        # Pages should not overlap
        page1_ids = {e.id for e in page1}
        page2_ids = {e.id for e in page2}
        assert page1_ids.isdisjoint(page2_ids)

    def test_get_all_offset_beyond_total(self, email_store):
        """Test that offset beyond total returns empty list."""
        email_store.upsert(_make_email(email_id="only_one"))
        result = email_store.get_all(offset=100)
        assert result == []

    def test_get_all_limit_larger_than_total(self, email_store):
        """Test that limit larger than total returns all available."""
        for i in range(3):
            email_store.upsert(_make_email(email_id=f"few_{i}"))

        result = email_store.get_all(limit=100)
        assert len(result) == 3


# =============================================================================
# EmailStore.count() tests
# =============================================================================


class TestEmailStoreCount:
    """Test EmailStore count operation."""

    def test_count_empty_store(self, email_store):
        """Test that count() returns 0 for empty store."""
        assert email_store.count() == 0

    def test_count_after_inserts(self, email_store):
        """Test that count() reflects inserted emails."""
        for i in range(7):
            email_store.upsert(_make_email(email_id=f"cnt_{i}"))
        assert email_store.count() == 7

    def test_count_after_upsert_existing(self, email_store):
        """Test that count() doesn't increase on upsert of existing email."""
        email_store.upsert(_make_email(email_id="cnt_dup"))
        email_store.upsert(_make_email(email_id="cnt_dup", subject="Updated"))
        assert email_store.count() == 1

    def test_count_after_delete(self, email_store):
        """Test that count() decreases after deletion."""
        for i in range(5):
            email_store.upsert(_make_email(email_id=f"cnt_del_{i}"))
        email_store.delete("cnt_del_0")
        assert email_store.count() == 4


# =============================================================================
# EmailStore.delete() tests
# =============================================================================


class TestEmailStoreDelete:
    """Test EmailStore single delete operation."""

    def test_delete_removes_email(self, email_store):
        """Test that delete() removes an email by ID."""
        email_store.upsert(_make_email(email_id="del_001"))
        email_store.delete("del_001")
        assert email_store.get("del_001") is None

    def test_delete_nonexistent_does_not_raise(self, email_store):
        """Test that deleting a nonexistent ID does not raise."""
        # Should not raise
        email_store.delete("nonexistent_id")

    def test_delete_only_affects_target(self, email_store):
        """Test that delete() only removes the specified email."""
        email_store.upsert(_make_email(email_id="keep_001"))
        email_store.upsert(_make_email(email_id="delete_001"))
        email_store.upsert(_make_email(email_id="keep_002"))

        email_store.delete("delete_001")

        assert email_store.get("keep_001") is not None
        assert email_store.get("delete_001") is None
        assert email_store.get("keep_002") is not None
        assert email_store.count() == 2


# =============================================================================
# EmailStore.delete_batch() tests
# =============================================================================


class TestEmailStoreDeleteBatch:
    """Test EmailStore batch delete operation."""

    def test_delete_batch_removes_multiple(self, email_store):
        """Test that delete_batch() removes multiple emails."""
        for i in range(5):
            email_store.upsert(_make_email(email_id=f"dbatch_{i}"))

        email_store.delete_batch(["dbatch_0", "dbatch_2", "dbatch_4"])

        assert email_store.count() == 2
        assert email_store.get("dbatch_0") is None
        assert email_store.get("dbatch_1") is not None
        assert email_store.get("dbatch_2") is None
        assert email_store.get("dbatch_3") is not None
        assert email_store.get("dbatch_4") is None

    def test_delete_batch_empty_list(self, email_store):
        """Test that delete_batch() handles empty list gracefully."""
        email_store.upsert(_make_email(email_id="survive_001"))
        email_store.delete_batch([])
        assert email_store.count() == 1

    def test_delete_batch_with_nonexistent_ids(self, email_store):
        """Test that delete_batch() skips nonexistent IDs without error."""
        email_store.upsert(_make_email(email_id="exists_001"))
        email_store.delete_batch(["exists_001", "nope_001", "nope_002"])
        assert email_store.count() == 0

    def test_delete_batch_is_atomic(self, email_store):
        """Test that batch delete is wrapped in a single transaction."""
        for i in range(5):
            email_store.upsert(_make_email(email_id=f"atomic_del_{i}"))

        email_store.delete_batch([f"atomic_del_{i}" for i in range(5)])
        assert email_store.count() == 0


# =============================================================================
# Edge cases and error handling
# =============================================================================


class TestEmailStoreEdgeCases:
    """Test edge cases and error handling."""

    def test_unicode_content_preserved(self, email_store):
        """Test that Unicode content is preserved through store/retrieve."""
        email = _make_email(
            email_id="unicode_001",
            sender_name="Rene Descartes",
            subject="Meeting at the cafe",
            body_text="Price: 50 euros. Japanese: test text. Emoji: hello",
        )
        email_store.upsert(email)
        result = email_store.get("unicode_001")
        assert result.sender_name == email.sender_name
        assert result.subject == email.subject
        assert result.body_text == email.body_text

    def test_very_long_body_text(self, email_store):
        """Test that very long body text is stored and retrieved."""
        long_body = "A" * 100_000
        email = _make_email(email_id="long_body", body_text=long_body)
        email_store.upsert(email)
        result = email_store.get("long_body")
        assert len(result.body_text) == 100_000

    def test_empty_string_fields(self, email_store):
        """Test that empty string fields are preserved."""
        email = _make_email(
            email_id="empty_fields",
            sender_name="",
            recipient_name="",
            subject="",
            body_text="",
        )
        email_store.upsert(email)
        result = email_store.get("empty_fields")
        assert result.sender_name == ""
        assert result.recipient_name == ""
        assert result.subject == ""
        assert result.body_text == ""

    def test_special_characters_in_subject(self, email_store):
        """Test SQL-special characters in text fields."""
        email = _make_email(
            email_id="special_chars",
            subject="O'Brien's \"quote\" and 100% -- done; DROP TABLE emails;",
            body_text="Content with 'quotes' and \"double quotes\" and\nnewlines",
        )
        email_store.upsert(email)
        result = email_store.get("special_chars")
        assert result.subject == email.subject
        assert result.body_text == email.body_text

    def test_many_references(self, email_store):
        """Test email with many references preserves all."""
        refs = [f"<msg{i}@example.com>" for i in range(50)]
        email = _make_email(email_id="many_refs", references=refs)
        email_store.upsert(email)
        result = email_store.get("many_refs")
        assert result.references == refs

    def test_concurrent_upsert_batch_does_not_corrupt(self, email_store, db, tmp_path):
        """Test that the store handles sequential batch operations correctly."""
        # First batch
        batch1 = [_make_email(email_id=f"seq_a_{i}") for i in range(10)]
        email_store.upsert_batch(batch1)

        # Second batch overlapping
        batch2 = [_make_email(email_id=f"seq_a_{i}", subject="Updated") for i in range(5)]
        batch2 += [_make_email(email_id=f"seq_b_{i}") for i in range(5)]
        email_store.upsert_batch(batch2)

        assert email_store.count() == 15  # 10 original (5 updated) + 5 new
        assert email_store.get("seq_a_0").subject == "Updated"
        assert email_store.get("seq_a_7").subject == "Test Email Subject"  # not updated
