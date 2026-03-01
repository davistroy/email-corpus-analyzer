"""
EmailStore: CRUD operations for emails in SQLite.

Provides insert/update (upsert), get, get_all (paginated), count, and delete
operations for Email models. All batch operations are wrapped in a single
transaction for atomicity and performance.

Phase 3, Work Item 3.2.
"""

import logging

from src.models.email import Email
from src.storage.database import Database

logger = logging.getLogger(__name__)

# SQL column list matching Email.to_row() key order
_EMAIL_COLUMNS = (
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
)

_COLUMNS_CSV = ", ".join(_EMAIL_COLUMNS)
_PLACEHOLDERS = ", ".join("?" for _ in _EMAIL_COLUMNS)

_UPSERT_SQL = f"INSERT OR REPLACE INTO emails ({_COLUMNS_CSV}) VALUES ({_PLACEHOLDERS})"

_SELECT_ALL_COLUMNS = _COLUMNS_CSV


class EmailStore:
    """
    CRUD operations for emails stored in SQLite.

    Wraps a Database instance and provides typed operations using
    the Email Pydantic model with to_row()/from_row() for serialization.

    Upsert semantics: INSERT OR REPLACE keyed on emails.id (the primary key).
    This means inserting an email with an existing ID replaces the entire row,
    which is the desired behavior for idempotent extraction.

    Usage:
        store = EmailStore(database)
        store.upsert(email)
        store.upsert_batch(emails)
        email = store.get("email_id")
        all_emails = store.get_all(limit=100, offset=0)
        count = store.count()
        store.delete("email_id")
        store.delete_batch(["id1", "id2"])
    """

    def __init__(self, database: Database) -> None:
        """
        Initialize the EmailStore.

        Args:
            database: An open Database instance to use for all operations.
        """
        self._db = database

    def upsert(self, email: Email) -> None:
        """
        Insert or replace a single email.

        If an email with the same ID already exists, it is fully replaced.

        Args:
            email: The Email to insert or replace.
        """
        row = email.to_row()
        params = tuple(row[col] for col in _EMAIL_COLUMNS)
        self._db.execute(_UPSERT_SQL, params)

    def upsert_batch(self, emails: list[Email]) -> None:
        """
        Insert or replace multiple emails in a single transaction.

        All emails are inserted/replaced atomically. If any single row
        fails, the entire batch is rolled back.

        Args:
            emails: List of Email instances to insert or replace.
        """
        if not emails:
            return

        params_seq = [tuple(email.to_row()[col] for col in _EMAIL_COLUMNS) for email in emails]
        with self._db.transaction():
            self._db.executemany(_UPSERT_SQL, params_seq)

        logger.debug("Upserted batch of %d emails", len(emails))

    def get(self, email_id: str) -> Email | None:
        """
        Get a single email by its ID.

        Args:
            email_id: The email ID to look up.

        Returns:
            The Email if found, or None if no email has that ID.
        """
        cursor = self._db.execute(
            f"SELECT {_SELECT_ALL_COLUMNS} FROM emails WHERE id = ?",
            (email_id,),
        )
        row = cursor.fetchone()
        if row is None:
            return None

        row_dict = dict(zip(_EMAIL_COLUMNS, row, strict=False))
        return Email.from_row(row_dict)

    def get_all(
        self,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[Email]:
        """
        Get all emails with optional pagination.

        Results are ordered by rowid (insertion order) for deterministic
        pagination.

        Args:
            limit: Maximum number of emails to return. None means no limit.
            offset: Number of emails to skip. None means start from the beginning.

        Returns:
            List of Email instances.
        """
        sql = f"SELECT {_SELECT_ALL_COLUMNS} FROM emails ORDER BY rowid"
        params: list = []

        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)

        if offset is not None:
            if limit is None:
                # SQLite requires LIMIT before OFFSET; use -1 for "no limit"
                sql += " LIMIT -1"
            sql += " OFFSET ?"
            params.append(offset)

        cursor = self._db.execute(sql, tuple(params) if params else None)
        rows = cursor.fetchall()

        return [Email.from_row(dict(zip(_EMAIL_COLUMNS, row, strict=False))) for row in rows]

    def count(self) -> int:
        """
        Count the total number of emails in the store.

        Returns:
            Total email count.
        """
        cursor = self._db.execute("SELECT COUNT(*) FROM emails")
        return cursor.fetchone()[0]

    def delete(self, email_id: str) -> None:
        """
        Delete a single email by its ID.

        Does nothing if the email does not exist.

        Args:
            email_id: The ID of the email to delete.
        """
        self._db.execute("DELETE FROM emails WHERE id = ?", (email_id,))

    def delete_batch(self, email_ids: list[str]) -> None:
        """
        Delete multiple emails by their IDs in a single transaction.

        IDs that do not exist are silently ignored.

        Args:
            email_ids: List of email IDs to delete.
        """
        if not email_ids:
            return

        with self._db.transaction():
            self._db.executemany(
                "DELETE FROM emails WHERE id = ?",
                [(eid,) for eid in email_ids],
            )

        logger.debug("Deleted batch of %d email IDs", len(email_ids))
