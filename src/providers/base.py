"""
Base email provider protocol and common types.

All email providers must implement the EmailProvider protocol.
"""
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol, runtime_checkable

from src.models.email import Email
from src.models.provider import ProviderType


@dataclass
class ExtractionProgress:
    """Progress information for email extraction."""
    emails_fetched: int = 0
    total_emails: int | None = None  # None if count unknown
    current_batch: int = 0
    errors: int = 0
    last_email_date: datetime | None = None
    status: str = "in_progress"  # in_progress, completed, error

    @property
    def percentage(self) -> float | None:
        """Progress percentage, or None if total unknown."""
        if self.total_emails and self.total_emails > 0:
            return (self.emails_fetched / self.total_emails) * 100
        return None


@dataclass
class FolderInfo:
    """Information about an email folder/label."""
    name: str
    message_count: int | None = None
    unread_count: int | None = None
    # Gmail labels vs IMAP folders vs M365 folders
    folder_type: str = "folder"  # folder, label, category
    children: list["FolderInfo"] = field(default_factory=list)


@runtime_checkable
class EmailProvider(Protocol):
    """
    Protocol for email providers.

    All providers must implement these async methods for
    authentication, email fetching, and resource cleanup.
    """

    @property
    def provider_type(self) -> ProviderType:
        """Return the provider type."""
        ...

    @property
    def email_address(self) -> str:
        """Return the email address for this provider."""
        ...

    @property
    def is_authenticated(self) -> bool:
        """Check if provider is currently authenticated."""
        ...

    async def authenticate(self) -> bool:
        """
        Authenticate with the email service.

        Returns:
            True if authentication successful, False otherwise.

        Raises:
            AuthenticationError: If authentication fails with details.
        """
        ...

    async def fetch_emails(
        self,
        batch_size: int = 100,
        since: datetime | None = None,
        folder: str = "INBOX",
        include_body: bool = True,
    ) -> AsyncIterator[Email]:
        """
        Fetch emails from the mailbox.

        Args:
            batch_size: Number of emails to fetch per API request.
            since: Only fetch emails received after this date.
            folder: Folder/label to fetch from (default: INBOX).
            include_body: Whether to fetch full body content.

        Yields:
            Email objects as they are fetched.

        Raises:
            ConnectionError: If connection to server fails.
            AuthenticationError: If not authenticated or token expired.
        """
        ...

    async def get_total_count(self, folder: str = "INBOX") -> int | None:
        """
        Get total email count in folder.

        Args:
            folder: Folder to count emails in.

        Returns:
            Total count, or None if count not available.
        """
        ...

    async def list_folders(self) -> list[FolderInfo]:
        """
        List available folders/labels.

        Returns:
            List of folder information.
        """
        ...

    async def close(self) -> None:
        """
        Close connections and clean up resources.

        Should be called when done with the provider.
        """
        ...


class BaseEmailProvider(ABC):
    """
    Abstract base class for email providers.

    Provides common functionality and enforces the EmailProvider protocol.
    """

    def __init__(self, email_address: str):
        self._email_address = email_address
        self._authenticated = False

    @property
    def email_address(self) -> str:
        return self._email_address

    @property
    def is_authenticated(self) -> bool:
        return self._authenticated

    @property
    @abstractmethod
    def provider_type(self) -> ProviderType:
        """Return the provider type."""
        ...

    @abstractmethod
    async def authenticate(self) -> bool:
        """Authenticate with the email service."""
        ...

    @abstractmethod
    async def fetch_emails(
        self,
        batch_size: int = 100,
        since: datetime | None = None,
        folder: str = "INBOX",
        include_body: bool = True,
    ) -> AsyncIterator[Email]:
        """Fetch emails from the mailbox."""
        ...

    async def get_total_count(self, folder: str = "INBOX") -> int | None:
        """Default implementation returns None (count unknown)."""
        return None

    async def list_folders(self) -> list[FolderInfo]:
        """Default implementation returns empty list."""
        return []

    async def close(self) -> None:
        """Default implementation does nothing."""
        self._authenticated = False

    async def __aenter__(self) -> "BaseEmailProvider":
        """Async context manager entry."""
        await self.authenticate()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.close()


class AuthenticationError(Exception):
    """Raised when authentication fails."""

    def __init__(self, message: str, provider: ProviderType, recoverable: bool = False):
        super().__init__(message)
        self.provider = provider
        self.recoverable = recoverable  # True if user can retry with new credentials


class RateLimitError(Exception):
    """Raised when API rate limit is hit."""

    def __init__(self, message: str, retry_after: int | None = None):
        super().__init__(message)
        self.retry_after = retry_after  # Seconds to wait before retry
