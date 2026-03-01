"""
Email data model.

Per data-model.md lines 75-91.
Phase 8 Track 8A.1: Added thread_id, in_reply_to, and references fields for thread analysis.
Phase 3 Work Item 3.2: Added provider, provider_message_id, to_row(), from_row() for SQLite.
"""

import json
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


class Email(BaseModel):
    """Individual email message with complete metadata and content."""

    id: str = Field(..., min_length=1, description="Unique M365 message ID")
    sender_email: str = Field(..., min_length=1)
    sender_name: str = ""
    sender_domain: str = Field(..., min_length=1)
    recipient_email: str | None = None

    @field_validator("sender_email", "recipient_email", mode="before")
    @classmethod
    def _lenient_email_check(cls, v: str | None) -> str | None:
        """Accept any string containing @ as an email address.

        Extracted data from APIs (Graph, Gmail) may contain technically-invalid
        addresses (e.g. underscores in domains, leading hyphens). These must be
        preserved so spam/automated senders can be classified.
        """
        if v is None:
            return None
        if not isinstance(v, str):
            raise ValueError("Email must be a string")
        v = v.strip()
        if "@" not in v:
            raise ValueError(f"Email must contain @: {v!r}")
        return v

    recipient_name: str = ""
    subject: str
    body_text: str
    received_date: datetime
    has_attachments: bool

    # Thread analysis fields (Phase 8 Track 8A.1)
    thread_id: str | None = Field(default=None, description="Unique ID for conversation thread")
    in_reply_to: str | None = Field(
        default=None, description="Message ID this email is replying to (from In-Reply-To header)"
    )
    references: list[str] = Field(
        default_factory=list,
        description="List of message IDs in the thread (from References header)",
    )

    # Provider tracking fields (Phase 3 Work Item 3.2)
    provider: str | None = Field(
        default=None, description="Email provider source (e.g., 'm365', 'gmail')"
    )
    provider_message_id: str | None = Field(
        default=None, description="Provider-specific message identifier"
    )

    def to_row(self) -> dict[str, Any]:
        """Serialize this Email to a dict suitable for SQLite insertion.

        Converts Python types to SQLite-compatible types:
        - datetime -> ISO 8601 string
        - bool -> int (0/1)
        - list[str] references -> JSON string

        Returns:
            Dictionary with column names matching the emails table schema.
        """
        return {
            "id": self.id,
            "sender_email": self.sender_email,
            "sender_name": self.sender_name,
            "sender_domain": self.sender_domain,
            "recipient_email": self.recipient_email,
            "recipient_name": self.recipient_name,
            "subject": self.subject,
            "body_text": self.body_text,
            "received_date": self.received_date.isoformat(),
            "has_attachments": int(self.has_attachments),
            "thread_id": self.thread_id,
            "in_reply_to": self.in_reply_to,
            "references_json": json.dumps(self.references),
            "provider": self.provider,
            "provider_message_id": self.provider_message_id,
        }

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "Email":
        """Deserialize a database row dict into an Email instance.

        Reverses the conversions done by to_row():
        - ISO 8601 string -> datetime
        - int (0/1) -> bool
        - JSON string -> list[str] references

        Args:
            row: Dictionary with column names from the emails table.

        Returns:
            Email instance populated from the row data.
        """
        references_json = row.get("references_json")
        references = json.loads(references_json) if references_json else []

        return cls(
            id=row["id"],
            sender_email=row["sender_email"],
            sender_name=row.get("sender_name", ""),
            sender_domain=row["sender_domain"],
            recipient_email=row.get("recipient_email"),
            recipient_name=row.get("recipient_name", ""),
            subject=row.get("subject", ""),
            body_text=row.get("body_text", ""),
            received_date=datetime.fromisoformat(row["received_date"]),
            has_attachments=bool(row.get("has_attachments", 0)),
            thread_id=row.get("thread_id"),
            in_reply_to=row.get("in_reply_to"),
            references=references,
            provider=row.get("provider"),
            provider_message_id=row.get("provider_message_id"),
        )

    def combined_text_with_limit(self, max_body_length: int = 1500) -> str:
        """Combined subject + body for embeddings with configurable body length.

        Args:
            max_body_length: Maximum number of body characters to include.
                Defaults to 1500 (embedding models typically support ~2000 tokens).

        Returns:
            Subject + truncated body text
        """
        return f"{self.subject} {self.body_text[:max_body_length]}"

    @property
    def combined_text(self) -> str:
        """Combined subject + body for embeddings (default 1500 char limit)."""
        return self.combined_text_with_limit(1500)
