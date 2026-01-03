"""
Mailbox data model for multi-mailbox support.

Each mailbox represents a configured email account that can be
extracted and analyzed independently.
"""
from datetime import datetime
from enum import Enum
from pathlib import Path
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from .provider import ProviderConfig, ProviderType


class MailboxStatus(Enum):
    """Status of a configured mailbox."""
    ACTIVE = "active"           # Ready for extraction/analysis
    PAUSED = "paused"           # Temporarily disabled
    ERROR = "error"             # Authentication or connection error
    PENDING_AUTH = "pending_auth"  # Needs authentication


class ExtractionState(BaseModel):
    """Tracks extraction progress for a mailbox."""
    last_extraction: datetime | None = None
    total_emails: int = 0
    last_email_date: datetime | None = None
    checkpoint_path: str | None = None
    is_complete: bool = False


class AnalysisState(BaseModel):
    """Tracks analysis state for a mailbox."""
    last_analysis: datetime | None = None
    cluster_count: int = 0
    category_count: int = 0
    analysis_path: str | None = None


class Mailbox(BaseModel):
    """Configured mailbox with extraction and analysis state."""

    # Identity
    id: UUID = Field(default_factory=uuid4)
    name: str = Field(..., min_length=1, description="User-friendly name")

    # Provider configuration
    provider: ProviderType
    email_address: str
    provider_config: dict = Field(
        default_factory=dict,
        description="Provider-specific configuration as JSON"
    )

    # Status
    status: MailboxStatus = MailboxStatus.PENDING_AUTH
    status_message: str | None = None

    # State tracking
    extraction: ExtractionState = Field(default_factory=ExtractionState)
    analysis: AnalysisState = Field(default_factory=AnalysisState)

    # Paths (relative to data directory)
    corpus_path: str | None = None

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    model_config = {"extra": "forbid"}

    def get_data_dir(self, base_dir: Path) -> Path:
        """Get the data directory for this mailbox."""
        return base_dir / "data" / str(self.id)

    def get_corpus_path(self, base_dir: Path) -> Path:
        """Get the corpus file path for this mailbox."""
        return self.get_data_dir(base_dir) / "corpus.json"

    def get_analysis_path(self, base_dir: Path) -> Path:
        """Get the analysis file path for this mailbox."""
        return self.get_data_dir(base_dir) / "analysis.json"

    def get_suggestions_path(self, base_dir: Path) -> Path:
        """Get the suggestions file path for this mailbox."""
        return self.get_data_dir(base_dir) / "suggestions.json"

    def get_checkpoint_path(self, base_dir: Path) -> Path:
        """Get the checkpoint file path for this mailbox."""
        return self.get_data_dir(base_dir) / "checkpoints" / "extraction_checkpoint.json"

    def mark_extraction_complete(self, total_emails: int) -> None:
        """Mark extraction as complete."""
        self.extraction.last_extraction = datetime.now()
        self.extraction.total_emails = total_emails
        self.extraction.is_complete = True
        self.updated_at = datetime.now()

    def mark_analysis_complete(self, cluster_count: int, category_count: int) -> None:
        """Mark analysis as complete."""
        self.analysis.last_analysis = datetime.now()
        self.analysis.cluster_count = cluster_count
        self.analysis.category_count = category_count
        self.updated_at = datetime.now()

    def set_error(self, message: str) -> None:
        """Set mailbox to error state."""
        self.status = MailboxStatus.ERROR
        self.status_message = message
        self.updated_at = datetime.now()

    def set_active(self) -> None:
        """Set mailbox to active state."""
        self.status = MailboxStatus.ACTIVE
        self.status_message = None
        self.updated_at = datetime.now()
