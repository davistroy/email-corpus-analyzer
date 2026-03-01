"""
Email mover for batch-moving emails to categorized folders (Phase 5, Item 5.2).

Provides a backend-agnostic EmailMover that delegates to either:
- M365MoveBackend: Microsoft Graph API (POST /me/messages/{id}/move)
- GmailMoveBackend: Gmail API (messages.modify to add/remove labels)

Supports:
- Single and batch email moves
- Dry-run mode (preview without making API calls)
- Idempotent moves (skip emails already in the target folder)
- Rate limiting (configurable delay between API requests)
- Rollback via ActionLogger integration (tracks source/target for reversal)
- Progress callbacks for large batch operations
- Error resilience (continues on individual failures)

Architecture:
    MoveBackend (Protocol)
        |-- M365MoveBackend  -- wraps GraphAPIClient
        |-- GmailMoveBackend -- wraps Gmail API service

    EmailMover -- orchestration layer over any backend
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

from src.actions.action_logger import ActionLogger, ActionType
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Graph API base URL
GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"

# Default delay between API requests (seconds) to respect rate limits
DEFAULT_RATE_LIMIT_DELAY = 0.1


# =============================================================================
# Data classes
# =============================================================================


@dataclass
class MoveResult:
    """
    Result of a batch email move operation.

    Attributes:
        successful_count: Number of emails successfully moved
        failed_count: Number of emails that failed to move
        skipped_count: Number of emails skipped (already in target folder)
        failed_ids: List of email IDs that failed to move
        duration: Total time taken for the operation in seconds
    """

    successful_count: int = 0
    failed_count: int = 0
    skipped_count: int = 0
    failed_ids: list[str] = field(default_factory=list)
    duration: float = 0.0

    @property
    def total_count(self) -> int:
        """Total number of emails processed (successful + failed + skipped)."""
        return self.successful_count + self.failed_count + self.skipped_count

    @property
    def all_succeeded(self) -> bool:
        """Whether all moves succeeded (no failures)."""
        return self.failed_count == 0

    def __repr__(self) -> str:
        return (
            f"MoveResult(successful={self.successful_count}, "
            f"failed={self.failed_count}, skipped={self.skipped_count}, "
            f"duration={self.duration:.2f}s)"
        )


# =============================================================================
# Backend Protocol
# =============================================================================


class MoveBackend(Protocol):
    """Protocol for email move backends (M365 or Gmail)."""

    def move_email(self, email_id: str, folder_id: str) -> bool:
        """
        Move a single email to the specified folder.

        Args:
            email_id: Provider message ID
            folder_id: Target folder/label ID

        Returns:
            True if the move succeeded, False otherwise
        """
        ...

    def get_email_folder(self, email_id: str) -> str | None:
        """
        Get the current folder/label ID for an email.

        Args:
            email_id: Provider message ID

        Returns:
            Current folder ID, or None if it cannot be determined
        """
        ...


# =============================================================================
# M365 Backend (Graph API)
# =============================================================================


class M365MoveBackend:
    """
    Microsoft 365 move backend using Graph API.

    Moves emails via POST /me/messages/{id}/move with destinationId.
    Requires GraphAPIClient with Mail.ReadWrite scope.
    """

    def __init__(self, graph_client: Any) -> None:
        """
        Initialize with a GraphAPIClient instance.

        Args:
            graph_client: Authenticated GraphAPIClient
        """
        self._client = graph_client

    def move_email(self, email_id: str, folder_id: str) -> bool:
        """
        Move an email via POST /me/messages/{id}/move.

        Args:
            email_id: Graph API message ID
            folder_id: Target mail folder ID

        Returns:
            True if the move succeeded, False on any error
        """
        url = f"{GRAPH_BASE_URL}/me/messages/{email_id}/move"
        json_data = {"destinationId": folder_id}

        try:
            self._client._make_request(url, method="POST", json_data=json_data)
            logger.debug(f"Moved email {email_id} to folder {folder_id}")
            return True
        except Exception as e:
            logger.warning(f"Failed to move email {email_id}: {e}")
            return False

    def get_email_folder(self, email_id: str) -> str | None:
        """
        Get the current parent folder ID for an email.

        Args:
            email_id: Graph API message ID

        Returns:
            parentFolderId, or None on error
        """
        url = f"{GRAPH_BASE_URL}/me/messages/{email_id}"
        params = {"$select": "parentFolderId"}

        try:
            data = self._client._make_request(url, params)
            folder_id: str | None = data.get("parentFolderId")
            return folder_id
        except Exception as e:
            logger.warning(f"Failed to get folder for email {email_id}: {e}")
            return None


# =============================================================================
# Gmail Backend (Labels API)
# =============================================================================


class GmailMoveBackend:
    """
    Gmail move backend using the messages.modify API.

    "Moving" in Gmail means adding the destination label and optionally
    removing the INBOX label. Gmail messages can have multiple labels.

    Requires Gmail API service with gmail.modify scope.
    """

    def __init__(self, gmail_service: Any, remove_from_inbox: bool = True) -> None:
        """
        Initialize with a Gmail API service object.

        Args:
            gmail_service: Authenticated Gmail API service
            remove_from_inbox: If True, remove the INBOX label when adding
                              the destination label (default True)
        """
        self._service = gmail_service
        self._remove_from_inbox = remove_from_inbox

    def move_email(self, email_id: str, folder_id: str) -> bool:
        """
        Move an email by modifying its labels.

        Args:
            email_id: Gmail message ID
            folder_id: Target label ID to add

        Returns:
            True if the modification succeeded, False on any error
        """
        body: dict[str, Any] = {"addLabelIds": [folder_id]}

        if self._remove_from_inbox:
            body["removeLabelIds"] = ["INBOX"]
        else:
            body["removeLabelIds"] = []

        try:
            self._service.users().messages().modify(userId="me", id=email_id, body=body).execute()
            logger.debug(f"Modified labels for email {email_id}: added {folder_id}")
            return True
        except Exception as e:
            logger.warning(f"Failed to modify labels for email {email_id}: {e}")
            return False

    def get_email_folder(self, email_id: str) -> str | None:
        """
        Get the current label IDs for an email.

        Returns the label IDs as a comma-separated string.

        Args:
            email_id: Gmail message ID

        Returns:
            Comma-separated label IDs, or None on error
        """
        try:
            msg = (
                self._service.users()
                .messages()
                .get(userId="me", id=email_id, format="minimal")
                .execute()
            )
            label_ids = msg.get("labelIds", [])
            return ",".join(label_ids) if label_ids else None
        except Exception as e:
            logger.warning(f"Failed to get labels for email {email_id}: {e}")
            return None


# =============================================================================
# EmailMover — orchestration layer
# =============================================================================


class EmailMover:
    """
    Backend-agnostic email mover with dry-run, idempotency, rate limiting,
    and action logging support.

    Wraps any MoveBackend (M365 or Gmail) and adds:
    - Idempotent moves (skip emails already in target folder)
    - Dry-run mode (preview without making API calls)
    - Rate limiting (configurable delay between requests)
    - ActionLogger integration for rollback support
    - Progress callbacks for batch operations
    - Error resilience (continues on individual failures)
    """

    def __init__(
        self,
        backend: MoveBackend,
        *,
        dry_run: bool = False,
        action_logger: ActionLogger | None = None,
        rate_limit_delay: float = DEFAULT_RATE_LIMIT_DELAY,
    ) -> None:
        """
        Initialize the email mover.

        Args:
            backend: M365MoveBackend or GmailMoveBackend instance
            dry_run: If True, no moves are executed — only logged/counted
            action_logger: Optional ActionLogger for audit trail and rollback
            rate_limit_delay: Seconds to wait between API requests (default 0.1)
        """
        self._backend = backend
        self._dry_run = dry_run
        self._action_logger = action_logger
        self._rate_limit_delay = max(0.0, rate_limit_delay)

    def __repr__(self) -> str:
        dry = ", dry_run=True" if self._dry_run else ""
        return f"EmailMover(backend={type(self._backend).__name__}{dry})"

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def move_email(self, email_id: str, folder_id: str) -> bool:
        """
        Move a single email to the specified folder.

        Idempotent: if the email is already in the target folder, it is
        skipped without making an API call.

        Args:
            email_id: Provider message ID
            folder_id: Target folder/label ID

        Returns:
            True if the move succeeded or was skipped (already in target),
            False if the move failed
        """
        # Validate inputs
        if not email_id or not folder_id:
            logger.warning("Cannot move email: empty email_id or folder_id")
            return False

        # Idempotency check: skip if already in target
        current_folder = self._backend.get_email_folder(email_id)
        if current_folder is not None and current_folder == folder_id:
            logger.debug(f"Email {email_id} already in folder {folder_id}, skipping")
            return True

        # Dry-run: count as success but don't execute
        if self._dry_run:
            logger.info(f"[DRY RUN] Would move email {email_id} to folder {folder_id}")
            return True

        # Execute the move
        success = self._backend.move_email(email_id, folder_id)

        # Log to action logger if available
        if self._action_logger is not None:
            self._action_logger.log_action(
                action_type=ActionType.EMAIL_MOVE,
                target_id=email_id,
                details={
                    "source_folder_id": current_folder or "unknown",
                    "target_folder_id": folder_id,
                },
                success=success,
                reversible=success,  # only reversible if the move actually happened
            )

        if success:
            logger.debug(f"Moved email {email_id} to folder {folder_id}")
        else:
            logger.warning(f"Failed to move email {email_id} to folder {folder_id}")

        return success

    def move_batch(
        self,
        moves: list[tuple[str, str]],
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> MoveResult:
        """
        Move a batch of emails to their target folders.

        Continues processing on individual failures. Reports aggregate results.

        Args:
            moves: List of (email_id, folder_id) tuples
            progress_callback: Optional callback(completed, total) for progress reporting

        Returns:
            MoveResult with counts of successful, failed, and skipped moves
        """
        if not moves:
            return MoveResult()

        start_time = time.monotonic()
        total = len(moves)
        successful = 0
        failed = 0
        skipped = 0
        failed_ids: list[str] = []

        for i, (email_id, folder_id) in enumerate(moves):
            # Rate limiting: wait between requests (except before the first one)
            if i > 0 and self._rate_limit_delay > 0:
                time.sleep(self._rate_limit_delay)

            try:
                # Check idempotency
                current_folder = self._backend.get_email_folder(email_id)
                if current_folder is not None and current_folder == folder_id:
                    logger.debug(f"Email {email_id} already in folder {folder_id}, skipping")
                    skipped += 1
                    if progress_callback:
                        progress_callback(i + 1, total)
                    continue

                if self._dry_run:
                    logger.info(f"[DRY RUN] Would move email {email_id} to folder {folder_id}")
                    successful += 1
                    if progress_callback:
                        progress_callback(i + 1, total)
                    continue

                # Execute the move
                success = self._backend.move_email(email_id, folder_id)

                # Log to action logger
                if self._action_logger is not None:
                    self._action_logger.log_action(
                        action_type=ActionType.EMAIL_MOVE,
                        target_id=email_id,
                        details={
                            "source_folder_id": current_folder or "unknown",
                            "target_folder_id": folder_id,
                        },
                        success=success,
                        reversible=success,
                    )

                if success:
                    successful += 1
                else:
                    failed += 1
                    failed_ids.append(email_id)

            except Exception as e:
                logger.error(f"Unexpected error moving email {email_id}: {e}")
                failed += 1
                failed_ids.append(email_id)

                # Log failure to action logger
                if self._action_logger is not None:
                    self._action_logger.log_action(
                        action_type=ActionType.EMAIL_MOVE,
                        target_id=email_id,
                        details={
                            "source_folder_id": "unknown",
                            "target_folder_id": folder_id,
                            "error": str(e),
                        },
                        success=False,
                        reversible=False,
                    )

            if progress_callback:
                progress_callback(i + 1, total)

        duration = time.monotonic() - start_time

        result = MoveResult(
            successful_count=successful,
            failed_count=failed,
            skipped_count=skipped,
            failed_ids=failed_ids,
            duration=duration,
        )

        logger.info(
            f"Batch move {'(dry-run) ' if self._dry_run else ''}complete: "
            f"{result.successful_count} succeeded, {result.failed_count} failed, "
            f"{result.skipped_count} skipped in {result.duration:.2f}s"
        )

        return result
