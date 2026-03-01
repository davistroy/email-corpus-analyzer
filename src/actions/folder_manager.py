"""
Folder manager for creating and managing mailbox folders/labels (Phase 5, Item 5.1).

Provides a backend-agnostic FolderManager that delegates to either:
- M365FolderBackend: Microsoft Graph API (POST /me/mailFolders)
- GmailFolderBackend: Gmail API (labels.create)

Supports:
- Creating folders/labels with deduplication (won't recreate existing)
- Nested/hierarchical folders (subfolders under a parent)
- Dry-run mode (preview what would be created without making API calls)
- Bulk folder creation (ensure_folders for a list of category names)
- Case-insensitive name matching for deduplication

Architecture:
    FolderBackend (Protocol)
        ├── M365FolderBackend  — wraps GraphAPIClient
        └── GmailFolderBackend — wraps Gmail API service

    FolderManager — orchestration layer over any backend
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Protocol

from src.exceptions import FolderActionError
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Graph API base URL (same as graph_api_client.py)
GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"


# =============================================================================
# Data classes
# =============================================================================


@dataclass
class FolderInfo:
    """
    Represents a mailbox folder or Gmail label.

    Provider-agnostic representation returned by list_folders()
    and used for deduplication logic.
    """

    folder_id: str
    name: str
    provider: str  # "m365" or "gmail"
    parent_id: str | None = None

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, FolderInfo):
            return NotImplemented
        return (
            self.folder_id == other.folder_id
            and self.name == other.name
            and self.provider == other.provider
            and self.parent_id == other.parent_id
        )

    def __repr__(self) -> str:
        parent = f", parent_id={self.parent_id!r}" if self.parent_id else ""
        return f"FolderInfo(id={self.folder_id!r}, name={self.name!r}, provider={self.provider!r}{parent})"


# =============================================================================
# Backend Protocol
# =============================================================================


class FolderBackend(Protocol):
    """Protocol for folder/label backends (M365 or Gmail)."""

    def list_folders(self) -> list[FolderInfo]:
        """List all existing folders/labels in the mailbox."""
        ...

    def create_folder(self, name: str, *, parent_id: str | None = None) -> str:
        """
        Create a new folder/label and return its ID.

        Args:
            name: Display name for the folder
            parent_id: ID of parent folder (for nested folders)

        Returns:
            Server-assigned folder/label ID
        """
        ...


# =============================================================================
# M365 Backend (Graph API)
# =============================================================================


class M365FolderBackend:
    """
    Microsoft 365 folder backend using Graph API.

    Creates mail folders via POST /me/mailFolders (top-level)
    or POST /me/mailFolders/{parent_id}/childFolders (nested).

    Requires GraphAPIClient with Mail.ReadWrite scope.
    Note: The existing GraphAPIClient only has Mail.Read — scope upgrade
    will be needed before live deployment.
    """

    def __init__(self, graph_client: Any) -> None:
        """
        Initialize with a GraphAPIClient instance.

        Args:
            graph_client: Authenticated GraphAPIClient
        """
        self._client = graph_client

    def list_folders(self) -> list[FolderInfo]:
        """
        List all mail folders via GET /me/mailFolders.

        Returns:
            List of FolderInfo for all folders in the mailbox.

        Raises:
            FolderActionError: On API errors.
        """
        url = f"{GRAPH_BASE_URL}/me/mailFolders"
        params = {"$top": 200, "$select": "id,displayName,parentFolderId"}

        try:
            data = self._client._make_request(url, params)
            folders: list[FolderInfo] = []
            for item in data.get("value", []):
                folders.append(
                    FolderInfo(
                        folder_id=item["id"],
                        name=item["displayName"],
                        provider="m365",
                        parent_id=item.get("parentFolderId"),
                    )
                )
            logger.debug(f"Listed {len(folders)} M365 mail folders")
            return folders
        except Exception as e:
            raise FolderActionError(
                f"Failed to list folders: {e}",
                context={"provider": "m365"},
            ) from e

    def create_folder(self, name: str, *, parent_id: str | None = None) -> str:
        """
        Create a mail folder via Graph API.

        Top-level: POST /me/mailFolders
        Nested:    POST /me/mailFolders/{parent_id}/childFolders

        Args:
            name: Display name for the folder.
            parent_id: Parent folder ID for nested creation.

        Returns:
            Server-assigned folder ID.

        Raises:
            FolderActionError: On API errors.
        """
        if parent_id:
            url = f"{GRAPH_BASE_URL}/me/mailFolders/{parent_id}/childFolders"
        else:
            url = f"{GRAPH_BASE_URL}/me/mailFolders"

        json_data = {"displayName": name}

        try:
            data = self._client._make_request(url, method="POST", json_data=json_data)
            folder_id: str = data["id"]
            logger.info(f"Created M365 folder '{name}' with ID {folder_id}")
            return folder_id
        except Exception as e:
            raise FolderActionError(
                f"Failed to create folder '{name}': {e}",
                context={"provider": "m365", "name": name, "parent_id": parent_id},
            ) from e


# =============================================================================
# Gmail Backend (Labels API)
# =============================================================================


class GmailFolderBackend:
    """
    Gmail folder backend using the Labels API.

    Creates labels via users.labels.create(). Nested labels use
    the Gmail convention of '/' separators in the label name
    (e.g., "Projects/Alpha").

    Requires Gmail API service with gmail.labels scope.
    Note: The existing GmailClient only has gmail.readonly — scope upgrade
    will be needed before live deployment.
    """

    def __init__(self, gmail_service: Any) -> None:
        """
        Initialize with a Gmail API service object.

        Args:
            gmail_service: Authenticated Gmail API service (from googleapiclient.discovery.build)
        """
        self._service = gmail_service

    def list_folders(self) -> list[FolderInfo]:
        """
        List all user-created labels (excludes system labels like INBOX, SENT).

        Returns:
            List of FolderInfo for user labels.

        Raises:
            FolderActionError: On API errors.
        """
        try:
            result = self._service.users().labels().list(userId="me").execute()
            folders: list[FolderInfo] = []
            for label in result.get("labels", []):
                # Skip system labels (INBOX, SENT, DRAFT, etc.)
                if label.get("type") == "system":
                    continue
                folders.append(
                    FolderInfo(
                        folder_id=label["id"],
                        name=label["name"],
                        provider="gmail",
                        parent_id=None,  # Gmail doesn't expose parent_id directly
                    )
                )
            logger.debug(f"Listed {len(folders)} Gmail user labels")
            return folders
        except Exception as e:
            raise FolderActionError(
                f"Failed to list folders: {e}",
                context={"provider": "gmail"},
            ) from e

    def create_folder(
        self, name: str, *, parent_id: str | None = None, parent_name: str | None = None
    ) -> str:
        """
        Create a Gmail label.

        For nested labels, Gmail uses '/' separator in the label name.
        Pass parent_name to create a nested label (e.g., parent_name="Projects"
        + name="Alpha" creates "Projects/Alpha").

        Args:
            name: Label name.
            parent_id: Not used by Gmail (present for protocol conformance).
            parent_name: Parent label name for nested labels.

        Returns:
            Server-assigned label ID.

        Raises:
            FolderActionError: On API errors.
        """
        full_name = f"{parent_name}/{name}" if parent_name else name

        label_body = {
            "name": full_name,
            "labelListVisibility": "labelShow",
            "messageListVisibility": "show",
        }

        try:
            result = self._service.users().labels().create(userId="me", body=label_body).execute()
            label_id: str = result["id"]
            logger.info(f"Created Gmail label '{full_name}' with ID {label_id}")
            return label_id
        except Exception as e:
            raise FolderActionError(
                f"Failed to create folder '{full_name}': {e}",
                context={"provider": "gmail", "name": full_name, "parent_name": parent_name},
            ) from e


# =============================================================================
# FolderManager — orchestration layer
# =============================================================================


class FolderManager:
    """
    Backend-agnostic folder manager with deduplication, caching, and dry-run support.

    Wraps any FolderBackend (M365 or Gmail) and adds:
    - Case-insensitive folder name deduplication
    - Folder list caching (invalidated on create)
    - Dry-run mode (preview without creating)
    - Bulk folder creation with error resilience
    - Hierarchical folder support (parent + children)
    """

    def __init__(self, backend: FolderBackend, dry_run: bool = False) -> None:
        """
        Initialize folder manager.

        Args:
            backend: M365FolderBackend or GmailFolderBackend instance
            dry_run: If True, no folders are created — only planned actions logged
        """
        self._backend = backend
        self._dry_run = dry_run
        self._cache: list[FolderInfo] | None = None
        self._planned_actions: list[dict[str, Any]] = []

    def __repr__(self) -> str:
        dry = ", dry_run=True" if self._dry_run else ""
        return f"FolderManager(backend={type(self._backend).__name__}{dry})"

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def list_folders(self) -> list[FolderInfo]:
        """
        List all folders/labels, using cache if available.

        Returns:
            List of FolderInfo from the backend.
        """
        if self._cache is None:
            self._cache = self._backend.list_folders()
        return list(self._cache)

    def create_folder(self, name: str, *, parent_id: str | None = None) -> str:
        """
        Create a folder/label, deduplicating against existing folders.

        If a folder with the same name (case-insensitive) already exists
        under the same parent, returns the existing folder's ID without
        creating a duplicate.

        Args:
            name: Display name for the folder.
            parent_id: Parent folder ID for nested folders.

        Returns:
            Folder ID (existing or newly created).

        Raises:
            ValueError: If name is empty or whitespace-only.
            FolderActionError: On API errors (non-dry-run mode).
        """
        name = name.strip()
        if not name:
            raise ValueError("Folder name cannot be empty")

        # Check for existing folder with same name (case-insensitive)
        existing = self._find_existing(name, parent_id)
        if existing:
            logger.debug(f"Folder '{name}' already exists with ID {existing.folder_id}")
            return existing.folder_id

        # Dry-run: log the action but don't create
        if self._dry_run:
            placeholder_id = f"dry-run-{uuid.uuid4().hex[:8]}"
            self._planned_actions.append(
                {
                    "action": "create_folder",
                    "name": name,
                    "parent_id": parent_id,
                    "placeholder_id": placeholder_id,
                }
            )
            logger.info(f"[DRY RUN] Would create folder '{name}' (parent={parent_id})")
            return placeholder_id

        # Create via backend
        folder_id = self._backend.create_folder(name, parent_id=parent_id)

        # Invalidate cache so next list_folders() re-fetches
        self._cache = None

        return folder_id

    def ensure_folders(
        self,
        category_names: list[str],
        *,
        parent_id: str | None = None,
    ) -> dict[str, str]:
        """
        Create all needed folders, returning a name -> folder_id mapping.

        Deduplicates against existing folders and within the input list.
        Silently skips folders that already exist.

        Args:
            category_names: List of folder names to ensure exist.
            parent_id: Optional parent folder ID for all created folders.

        Returns:
            Dict mapping each input name to its folder ID.
        """
        result: dict[str, str] = {}
        seen: set[str] = set()

        for name in category_names:
            name = name.strip()
            if not name:
                continue
            lower = name.lower()
            if lower in seen:
                continue
            seen.add(lower)

            folder_id = self.create_folder(name, parent_id=parent_id)
            result[name] = folder_id

        return result

    def ensure_folders_with_errors(
        self,
        category_names: list[str],
        *,
        parent_id: str | None = None,
    ) -> tuple[dict[str, str], list[str]]:
        """
        Create folders with error resilience — continues on individual failures.

        Args:
            category_names: List of folder names to ensure exist.
            parent_id: Optional parent folder ID.

        Returns:
            Tuple of (successful name->id map, list of error messages).
        """
        result: dict[str, str] = {}
        errors: list[str] = []
        seen: set[str] = set()

        for name in category_names:
            name = name.strip()
            if not name:
                continue
            lower = name.lower()
            if lower in seen:
                continue
            seen.add(lower)

            try:
                folder_id = self.create_folder(name, parent_id=parent_id)
                result[name] = folder_id
            except FolderActionError as e:
                error_msg = f"Failed to create folder '{name}': {e}"
                errors.append(error_msg)
                logger.warning(error_msg)

        return result, errors

    def ensure_folder_hierarchy(
        self,
        parent_name: str,
        child_names: list[str],
    ) -> dict[str, str]:
        """
        Create a parent folder and child folders underneath it.

        Args:
            parent_name: Name of the parent folder.
            child_names: Names of child folders to create under parent.

        Returns:
            Dict mapping all names (parent + children) to folder IDs.
        """
        result: dict[str, str] = {}

        # Create or find parent
        parent_id = self.create_folder(parent_name)
        result[parent_name] = parent_id

        # Create children under parent
        for child_name in child_names:
            child_name = child_name.strip()
            if not child_name:
                continue
            child_id = self.create_folder(child_name, parent_id=parent_id)
            result[child_name] = child_id

        return result

    def get_planned_actions(self) -> list[dict[str, Any]]:
        """
        Return the list of planned actions (dry-run mode only).

        Returns:
            List of action dicts with keys: action, name, parent_id, placeholder_id
        """
        return list(self._planned_actions)

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    def _find_existing(self, name: str, parent_id: str | None = None) -> FolderInfo | None:
        """
        Find an existing folder by name (case-insensitive) and parent.

        Args:
            name: Folder name to search for.
            parent_id: Required parent ID (None = top-level).

        Returns:
            FolderInfo if found, None otherwise.
        """
        folders = self.list_folders()
        lower_name = name.lower()

        for folder in folders:
            if folder.name.lower() == lower_name:
                # If parent_id is specified, must match
                if parent_id is not None:
                    if folder.parent_id == parent_id:
                        return folder
                else:
                    return folder

        return None
