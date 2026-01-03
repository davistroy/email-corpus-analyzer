"""
Email data model.

Per data-model.md lines 75-91.
Updated for multi-provider support.
"""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from .provider import ProviderType


class Email(BaseModel):
    """Individual email message with complete metadata and content."""

    # Identity - provider-agnostic
    id: str = Field(..., min_length=1, description="Unique message ID from provider")
    provider: ProviderType = Field(
        default=ProviderType.M365,
        description="Email provider this message came from"
    )
    mailbox_id: UUID | None = Field(
        default=None,
        description="ID of the mailbox this email belongs to"
    )

    # Sender information
    sender_email: EmailStr
    sender_name: str = ""
    sender_domain: str = Field(..., min_length=1)

    # Recipient information
    recipient_email: EmailStr | None = None
    recipient_name: str = ""

    # Content
    subject: str
    body_text: str
    body_html: str | None = Field(
        default=None,
        description="Original HTML body if available"
    )

    # Metadata
    received_date: datetime
    has_attachments: bool
    folder: str = Field(
        default="INBOX",
        description="Folder/label the email is in"
    )
    labels: list[str] = Field(
        default_factory=list,
        description="Labels/tags (Gmail) or categories (M365)"
    )
    is_read: bool = Field(default=True, description="Read status")
    importance: str = Field(default="normal", description="Message importance/priority")

    # Threading
    thread_id: str | None = Field(
        default=None,
        description="Conversation/thread ID for grouping"
    )
    in_reply_to: str | None = Field(
        default=None,
        description="Message ID this is a reply to"
    )

    @property
    def combined_text(self) -> str:
        """Combined subject + body for embeddings."""
        return f"{self.subject} {self.body_text[:500]}"

    @property
    def display_sender(self) -> str:
        """Human-readable sender string."""
        if self.sender_name:
            return f"{self.sender_name} <{self.sender_email}>"
        return self.sender_email
