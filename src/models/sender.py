"""
Sender data model.

Per data-model.md lines 174-205.
"""
from enum import Enum

from pydantic import BaseModel, EmailStr, Field


class SenderType(str, Enum):
    """Sender classification types."""

    PERSONAL = "personal"
    SERVICE = "service"
    MARKETING = "marketing"
    WORK = "work"


class Sender(BaseModel):
    """Aggregated sender information with classification."""

    email: EmailStr
    name: str = ""
    domain: str
    type: SenderType
    frequency_count: int = Field(..., ge=1)
    sample_subjects: list[str] = Field(default_factory=list, max_length=5)
    email_ids: list[str] = Field(default_factory=list)
