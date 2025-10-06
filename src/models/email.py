"""
Email data model.

Per data-model.md lines 75-91.
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

    @property
    def combined_text(self) -> str:
        """Combined subject + body for embeddings."""
        return f"{self.subject} {self.body_text[:500]}"
