"""
Mailbox registry for persistent storage of mailbox configurations.

Stores mailbox configurations in a JSON file for persistence across sessions.
"""
import json
from pathlib import Path
from uuid import UUID

from src.models.mailbox import Mailbox, MailboxStatus
from src.models.provider import ProviderType
from src.utils.logger import get_logger

logger = get_logger(__name__)


class MailboxRegistry:
    """
    Persistent storage for mailbox configurations.

    Stores configurations in ~/.email-analyzer/mailboxes.json
    with secure file permissions.
    """

    def __init__(self, config_dir: Path | None = None):
        """
        Initialize the mailbox registry.

        Args:
            config_dir: Configuration directory. Defaults to ~/.email-analyzer
        """
        self.config_dir = config_dir or Path.home() / ".email-analyzer"
        self.config_file = self.config_dir / "mailboxes.json"
        self._ensure_dir()

    def _ensure_dir(self) -> None:
        """Ensure configuration directory exists with secure permissions."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        # Set directory permissions to user-only
        self.config_dir.chmod(0o700)

    def _load(self) -> dict[str, dict]:
        """Load mailboxes from config file."""
        if not self.config_file.exists():
            return {}

        try:
            with open(self.config_file, encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse mailboxes.json: {e}")
            return {}
        except Exception as e:
            logger.error(f"Failed to load mailboxes: {e}")
            return {}

    def _save(self, mailboxes: dict[str, dict]) -> None:
        """Save mailboxes to config file with secure permissions."""
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(mailboxes, f, indent=2, default=str)
            # Set file permissions to user-only read/write
            self.config_file.chmod(0o600)
        except Exception as e:
            logger.error(f"Failed to save mailboxes: {e}")
            raise

    def add_mailbox(self, mailbox: Mailbox) -> None:
        """
        Register a new mailbox.

        Args:
            mailbox: Mailbox configuration to add.

        Raises:
            ValueError: If mailbox with same ID already exists.
        """
        mailboxes = self._load()
        mailbox_id = str(mailbox.id)

        if mailbox_id in mailboxes:
            raise ValueError(f"Mailbox with ID {mailbox_id} already exists")

        mailboxes[mailbox_id] = mailbox.model_dump(mode="json")
        self._save(mailboxes)
        logger.info(f"Added mailbox: {mailbox.name} ({mailbox.email_address})")

    def update_mailbox(self, mailbox: Mailbox) -> None:
        """
        Update an existing mailbox.

        Args:
            mailbox: Updated mailbox configuration.

        Raises:
            KeyError: If mailbox doesn't exist.
        """
        mailboxes = self._load()
        mailbox_id = str(mailbox.id)

        if mailbox_id not in mailboxes:
            raise KeyError(f"Mailbox with ID {mailbox_id} not found")

        mailboxes[mailbox_id] = mailbox.model_dump(mode="json")
        self._save(mailboxes)
        logger.debug(f"Updated mailbox: {mailbox.name}")

    def get_mailbox(self, mailbox_id: UUID | str) -> Mailbox | None:
        """
        Get mailbox by ID.

        Args:
            mailbox_id: Mailbox UUID or string ID.

        Returns:
            Mailbox if found, None otherwise.
        """
        mailboxes = self._load()
        data = mailboxes.get(str(mailbox_id))
        if data:
            return Mailbox(**data)
        return None

    def get_by_name(self, name: str) -> Mailbox | None:
        """
        Find mailbox by name (case-insensitive).

        Args:
            name: Mailbox display name.

        Returns:
            First matching mailbox, or None.
        """
        for mailbox in self.list_mailboxes():
            if mailbox.name.lower() == name.lower():
                return mailbox
        return None

    def get_by_email(self, email: str) -> Mailbox | None:
        """
        Find mailbox by email address.

        Args:
            email: Email address.

        Returns:
            First matching mailbox, or None.
        """
        email_lower = email.lower()
        for mailbox in self.list_mailboxes():
            if mailbox.email_address.lower() == email_lower:
                return mailbox
        return None

    def list_mailboxes(
        self,
        provider: ProviderType | None = None,
        status: MailboxStatus | None = None,
    ) -> list[Mailbox]:
        """
        List all configured mailboxes.

        Args:
            provider: Filter by provider type.
            status: Filter by status.

        Returns:
            List of mailboxes matching filters.
        """
        mailboxes = [Mailbox(**m) for m in self._load().values()]

        if provider:
            mailboxes = [m for m in mailboxes if m.provider == provider]
        if status:
            mailboxes = [m for m in mailboxes if m.status == status]

        # Sort by name
        return sorted(mailboxes, key=lambda m: m.name.lower())

    def remove_mailbox(self, mailbox_id: UUID | str) -> bool:
        """
        Remove a mailbox configuration.

        Args:
            mailbox_id: Mailbox UUID or string ID.

        Returns:
            True if removed, False if not found.
        """
        mailboxes = self._load()
        mailbox_id_str = str(mailbox_id)

        if mailbox_id_str in mailboxes:
            removed = mailboxes.pop(mailbox_id_str)
            self._save(mailboxes)
            logger.info(f"Removed mailbox: {removed.get('name', mailbox_id_str)}")
            return True

        return False

    def clear_all(self) -> int:
        """
        Remove all mailbox configurations.

        Returns:
            Number of mailboxes removed.
        """
        mailboxes = self._load()
        count = len(mailboxes)
        self._save({})
        logger.info(f"Cleared {count} mailboxes")
        return count

    @property
    def count(self) -> int:
        """Return number of configured mailboxes."""
        return len(self._load())
