"""
Corpus data model.

Per data-model.md lines 132-150.
"""
from datetime import datetime
from typing import List
from pydantic import BaseModel, EmailStr, Field

from .email import Email


class CorpusMetadata(BaseModel):
    """Metadata for email corpus extraction."""

    extraction_date: datetime
    total_emails: int = Field(..., ge=0)
    source: str
    user_email: EmailStr


class Corpus(BaseModel):
    """Complete collection of extracted emails with metadata."""

    extraction_metadata: CorpusMetadata
    emails: List[Email] = Field(default_factory=list)

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
