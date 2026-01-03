"""
Corpus data model.

Per data-model.md lines 132-150.
Updated for multi-provider and multi-mailbox support.
"""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from .email import Email
from .provider import ProviderType


class CorpusMetadata(BaseModel):
    """Metadata for email corpus extraction."""

    # Identity
    mailbox_id: UUID | None = Field(
        default=None,
        description="ID of the mailbox this corpus belongs to"
    )
    mailbox_name: str | None = Field(
        default=None,
        description="User-friendly mailbox name"
    )

    # Provider info
    provider: ProviderType = Field(
        default=ProviderType.M365,
        description="Email provider for this corpus"
    )
    source: str = Field(
        default="unknown",
        description="Legacy source field for backward compatibility"
    )

    # User info
    user_email: EmailStr

    # Extraction info
    extraction_date: datetime
    extraction_duration_seconds: float | None = None
    total_emails: int = Field(..., ge=0)

    # Optional filtering applied during extraction
    folder: str = Field(default="INBOX", description="Folder extracted from")
    since_date: datetime | None = Field(
        default=None,
        description="Only emails after this date were extracted"
    )


class Corpus(BaseModel):
    """Complete collection of extracted emails with metadata."""

    extraction_metadata: CorpusMetadata
    emails: list[Email] = Field(default_factory=list)

    # Version for migration support
    schema_version: str = Field(
        default="2.0",
        description="Schema version for backward compatibility"
    )

    @property
    def date_range(self) -> tuple[datetime, datetime]:
        """Get oldest and newest email dates."""
        if not self.emails:
            return (
                self.extraction_metadata.extraction_date,
                self.extraction_metadata.extraction_date
            )
        dates = [e.received_date for e in self.emails]
        return (min(dates), max(dates))

    @property
    def unique_senders(self) -> int:
        """Count of unique sender emails."""
        return len({e.sender_email for e in self.emails})

    @property
    def unique_domains(self) -> int:
        """Count of unique sender domains."""
        return len({e.sender_domain for e in self.emails})

    def filter_by_folder(self, folder: str) -> "Corpus":
        """Return a new corpus with only emails from specified folder."""
        filtered_emails = [e for e in self.emails if e.folder == folder]
        return Corpus(
            extraction_metadata=self.extraction_metadata,
            emails=filtered_emails,
            schema_version=self.schema_version
        )

    def filter_by_date_range(
        self,
        start: datetime | None = None,
        end: datetime | None = None
    ) -> "Corpus":
        """Return a new corpus with emails in date range."""
        filtered = self.emails
        if start:
            filtered = [e for e in filtered if e.received_date >= start]
        if end:
            filtered = [e for e in filtered if e.received_date <= end]
        return Corpus(
            extraction_metadata=self.extraction_metadata,
            emails=filtered,
            schema_version=self.schema_version
        )
