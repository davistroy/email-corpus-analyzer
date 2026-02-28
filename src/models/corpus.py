"""
Corpus data model.

Per data-model.md lines 132-150.
Enhanced with Task 4B.1 metadata fields for incremental processing.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field

from .email import Email


class CorpusMetadata(BaseModel):
    """Metadata for email corpus extraction.

    Task 4B.1 enhancements:
    - last_extraction_date: Track when the last extraction occurred (for incremental)
    - email_ids_hash: Hash of all email IDs for change detection
    - extraction_params: Store extraction parameters used
    """

    extraction_date: datetime
    total_emails: int = Field(..., ge=0)
    source: str
    user_email: EmailStr

    # Task 4B.1: Enhanced metadata fields for incremental processing
    last_extraction_date: datetime | None = Field(
        default=None, description="Date of last extraction (for incremental extraction)"
    )
    email_ids_hash: str | None = Field(
        default=None, description="Hash of all email IDs for change detection"
    )
    extraction_params: dict[str, Any] | None = Field(
        default=None, description="Parameters used for extraction (batch_size, etc.)"
    )


class Corpus(BaseModel):
    """Complete collection of extracted emails with metadata."""

    extraction_metadata: CorpusMetadata
    emails: list[Email] = Field(default_factory=list)

    @property
    def date_range(self) -> tuple[datetime, datetime]:
        """Get oldest and newest email dates."""
        if not self.emails:
            return (
                self.extraction_metadata.extraction_date,
                self.extraction_metadata.extraction_date,
            )
        dates = [e.received_date for e in self.emails]
        return (min(dates), max(dates))
