"""
Email data model.

Per data-model.md lines 75-91.
Phase 8 Track 8A.1: Added thread_id, in_reply_to, and references fields for thread analysis.
"""
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class Email(BaseModel):
    """Individual email message with complete metadata and content."""

    id: str = Field(..., min_length=1, description="Unique M365 message ID")
    sender_email: EmailStr
    sender_name: str = ""
    sender_domain: str = Field(..., min_length=1)
    recipient_email: EmailStr | None = None
    recipient_name: str = ""
    subject: str
    body_text: str
    received_date: datetime
    has_attachments: bool

    # Thread analysis fields (Phase 8 Track 8A.1)
    thread_id: str | None = Field(
        default=None,
        description="Unique ID for conversation thread"
    )
    in_reply_to: str | None = Field(
        default=None,
        description="Message ID this email is replying to (from In-Reply-To header)"
    )
    references: list[str] = Field(
        default_factory=list,
        description="List of message IDs in the thread (from References header)"
    )

    @property
    def combined_text(self) -> str:
        """Combined subject + body for embeddings."""
        return f"{self.subject} {self.body_text[:500]}"
