"""
Unit tests for EmailMover (Phase 5, Item 5.2).

Tests email moving for both M365 (Graph API) and Gmail (Labels API) backends.
All API calls are mocked. Tests cover:
- Single email moves (M365 and Gmail)
- Batch moves with progress callbacks
- Dry-run mode
- Idempotent moves (skip already-in-target)
- Rate limiting with configurable delay
- Rollback via ActionLogger integration
- Error handling and resilience
- MoveResult model

TDD: These tests are written first, implementation follows.
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock

from src.actions.action_logger import ActionLogger, ActionType
from src.actions.email_mover import (
    EmailMover,
    GmailMoveBackend,
    M365MoveBackend,
    MoveBackend,
    MoveResult,
)

# =============================================================================
# Helpers
# =============================================================================


def _mock_graph_client() -> MagicMock:
    """Create a mock GraphAPIClient."""
    client = MagicMock()
    client._access_token = "test-token"
    client._ensure_authenticated.return_value = "test-token"
    return client


def _mock_gmail_service() -> MagicMock:
    """Create a mock Gmail API service."""
    return MagicMock()


# =============================================================================
# MoveResult model tests
# =============================================================================


class TestMoveResult:
    """Tests for the MoveResult data model."""

    def test_create_empty_result(self):
        result = MoveResult()
        assert result.successful_count == 0
        assert result.failed_count == 0
        assert result.skipped_count == 0
        assert result.failed_ids == []
        assert result.duration == 0.0

    def test_create_result_with_values(self):
        result = MoveResult(
            successful_count=10,
            failed_count=2,
            skipped_count=3,
            failed_ids=["msg_1", "msg_2"],
            duration=5.5,
        )
        assert result.successful_count == 10
        assert result.failed_count == 2
        assert result.skipped_count == 3
        assert result.failed_ids == ["msg_1", "msg_2"]
        assert result.duration == 5.5

    def test_total_count(self):
        result = MoveResult(successful_count=5, failed_count=2, skipped_count=3)
        assert result.total_count == 10

    def test_all_succeeded_true(self):
        result = MoveResult(successful_count=5, failed_count=0)
        assert result.all_succeeded is True

    def test_all_succeeded_false(self):
        result = MoveResult(successful_count=5, failed_count=1)
        assert result.all_succeeded is False

    def test_result_repr(self):
        result = MoveResult(successful_count=5, failed_count=1, skipped_count=2)
        r = repr(result)
        assert "MoveResult" in r
        assert "5" in r
        assert "1" in r


# =============================================================================
# M365MoveBackend tests
# =============================================================================


class TestM365MoveBackend:
    """Tests for the Microsoft 365 / Graph API move backend."""

    def test_move_email_calls_graph_api(self):
        """POST /me/messages/{id}/move with destinationId."""
        client = _mock_graph_client()
        client._make_request.return_value = {
            "id": "msg_1",
            "parentFolderId": "folder_1",
        }
        backend = M365MoveBackend(client)

        success = backend.move_email("msg_1", "folder_1")

        assert success is True
        client._make_request.assert_called_once()
        call_args = client._make_request.call_args
        url = call_args[0][0]
        assert "/me/messages/msg_1/move" in url
        assert call_args[1]["method"] == "POST"
        assert call_args[1]["json_data"]["destinationId"] == "folder_1"

    def test_move_email_api_error_returns_false(self):
        """API failures should return False, not raise."""
        client = _mock_graph_client()
        client._make_request.side_effect = ConnectionError("Graph API error")
        backend = M365MoveBackend(client)

        success = backend.move_email("msg_1", "folder_1")

        assert success is False

    def test_get_email_folder_calls_api(self):
        """Fetch current folder ID for an email."""
        client = _mock_graph_client()
        client._make_request.return_value = {"parentFolderId": "inbox_id"}
        backend = M365MoveBackend(client)

        folder_id = backend.get_email_folder("msg_1")

        assert folder_id == "inbox_id"
        call_args = client._make_request.call_args
        url = call_args[0][0]
        assert "/me/messages/msg_1" in url

    def test_get_email_folder_api_error_returns_none(self):
        client = _mock_graph_client()
        client._make_request.side_effect = ConnectionError("Network error")
        backend = M365MoveBackend(client)

        folder_id = backend.get_email_folder("msg_1")
        assert folder_id is None


# =============================================================================
# GmailMoveBackend tests
# =============================================================================


class TestGmailMoveBackend:
    """Tests for the Gmail / Labels API move backend."""

    def test_move_email_modifies_labels(self):
        """Gmail moves = add destination label, optionally remove INBOX."""
        service = _mock_gmail_service()
        service.users().messages().modify.return_value.execute.return_value = {
            "id": "msg_1",
            "labelIds": ["Label_1"],
        }
        backend = GmailMoveBackend(service, remove_from_inbox=True)

        success = backend.move_email("msg_1", "Label_1")

        assert success is True
        service.users().messages().modify.assert_called_once()
        call_kwargs = service.users().messages().modify.call_args[1]
        assert call_kwargs["userId"] == "me"
        assert call_kwargs["id"] == "msg_1"
        body = call_kwargs["body"]
        assert "Label_1" in body["addLabelIds"]
        assert "INBOX" in body["removeLabelIds"]

    def test_move_email_without_inbox_removal(self):
        """When remove_from_inbox is False, only add the label."""
        service = _mock_gmail_service()
        service.users().messages().modify.return_value.execute.return_value = {
            "id": "msg_1",
            "labelIds": ["Label_1"],
        }
        backend = GmailMoveBackend(service, remove_from_inbox=False)

        success = backend.move_email("msg_1", "Label_1")

        assert success is True
        call_kwargs = service.users().messages().modify.call_args[1]
        body = call_kwargs["body"]
        assert "Label_1" in body["addLabelIds"]
        assert body.get("removeLabelIds", []) == []

    def test_move_email_api_error_returns_false(self):
        service = _mock_gmail_service()
        service.users().messages().modify.return_value.execute.side_effect = Exception(
            "Gmail API error"
        )
        backend = GmailMoveBackend(service)

        success = backend.move_email("msg_1", "Label_1")
        assert success is False

    def test_get_email_labels_calls_api(self):
        """Fetch current labels for an email."""
        service = _mock_gmail_service()
        service.users().messages().get.return_value.execute.return_value = {
            "id": "msg_1",
            "labelIds": ["INBOX", "Label_1"],
        }
        backend = GmailMoveBackend(service)

        labels = backend.get_email_folder("msg_1")
        # Gmail returns labelIds as a comma-separated string or first label
        assert labels is not None

    def test_get_email_labels_api_error_returns_none(self):
        service = _mock_gmail_service()
        service.users().messages().get.return_value.execute.side_effect = Exception("API error")
        backend = GmailMoveBackend(service)

        result = backend.get_email_folder("msg_1")
        assert result is None


# =============================================================================
# EmailMover — single email move
# =============================================================================


class TestEmailMoverSingleMove:
    """Tests for EmailMover.move_email()."""

    def test_move_single_email_success(self):
        backend = MagicMock(spec=MoveBackend)
        backend.move_email.return_value = True
        backend.get_email_folder.return_value = "inbox_id"  # different from target
        mover = EmailMover(backend)

        success = mover.move_email("msg_1", "folder_1")

        assert success is True
        backend.move_email.assert_called_once_with("msg_1", "folder_1")

    def test_move_single_email_failure(self):
        backend = MagicMock(spec=MoveBackend)
        backend.move_email.return_value = False
        backend.get_email_folder.return_value = "inbox_id"
        mover = EmailMover(backend)

        success = mover.move_email("msg_1", "folder_1")

        assert success is False

    def test_move_email_already_in_target_skips(self):
        """Idempotent: skip if email is already in the target folder."""
        backend = MagicMock(spec=MoveBackend)
        backend.get_email_folder.return_value = "folder_1"  # already there
        mover = EmailMover(backend)

        success = mover.move_email("msg_1", "folder_1")

        assert success is True
        backend.move_email.assert_not_called()  # skipped, no API call

    def test_move_email_dry_run(self):
        """Dry-run mode should not make API calls."""
        backend = MagicMock(spec=MoveBackend)
        backend.get_email_folder.return_value = "inbox_id"
        mover = EmailMover(backend, dry_run=True)

        success = mover.move_email("msg_1", "folder_1")

        assert success is True
        backend.move_email.assert_not_called()

    def test_move_email_logs_to_action_logger(self, tmp_path):
        """Successful moves are logged to ActionLogger."""
        backend = MagicMock(spec=MoveBackend)
        backend.move_email.return_value = True
        backend.get_email_folder.return_value = "inbox_id"
        action_logger = ActionLogger(log_path=tmp_path / "actions.jsonl")
        mover = EmailMover(backend, action_logger=action_logger)

        mover.move_email("msg_1", "folder_1")

        actions = action_logger.get_actions()
        assert len(actions) == 1
        assert actions[0].action_type == ActionType.EMAIL_MOVE
        assert actions[0].target_id == "msg_1"
        assert actions[0].success is True
        assert actions[0].details["source_folder_id"] == "inbox_id"
        assert actions[0].details["target_folder_id"] == "folder_1"

    def test_move_email_failure_logged(self, tmp_path):
        """Failed moves are also logged for audit trail."""
        backend = MagicMock(spec=MoveBackend)
        backend.move_email.return_value = False
        backend.get_email_folder.return_value = "inbox_id"
        action_logger = ActionLogger(log_path=tmp_path / "actions.jsonl")
        mover = EmailMover(backend, action_logger=action_logger)

        mover.move_email("msg_1", "folder_1")

        actions = action_logger.get_actions()
        assert len(actions) == 1
        assert actions[0].success is False

    def test_move_email_dry_run_not_logged(self, tmp_path):
        """Dry-run moves should not be logged to ActionLogger."""
        backend = MagicMock(spec=MoveBackend)
        backend.get_email_folder.return_value = "inbox_id"
        action_logger = ActionLogger(log_path=tmp_path / "actions.jsonl")
        mover = EmailMover(backend, dry_run=True, action_logger=action_logger)

        mover.move_email("msg_1", "folder_1")

        actions = action_logger.get_actions()
        assert len(actions) == 0


# =============================================================================
# EmailMover — batch move
# =============================================================================


class TestEmailMoverBatchMove:
    """Tests for EmailMover.move_batch()."""

    def test_batch_move_all_succeed(self):
        backend = MagicMock(spec=MoveBackend)
        backend.move_email.return_value = True
        backend.get_email_folder.return_value = "inbox_id"
        mover = EmailMover(backend)

        moves = [
            ("msg_1", "folder_1"),
            ("msg_2", "folder_2"),
            ("msg_3", "folder_1"),
        ]
        result = mover.move_batch(moves)

        assert result.successful_count == 3
        assert result.failed_count == 0
        assert result.failed_ids == []
        assert result.duration > 0.0

    def test_batch_move_partial_failures(self):
        backend = MagicMock(spec=MoveBackend)
        backend.get_email_folder.return_value = "inbox_id"

        def move_side_effect(email_id, folder_id):
            return email_id != "msg_2"  # msg_2 fails

        backend.move_email.side_effect = move_side_effect
        mover = EmailMover(backend)

        moves = [
            ("msg_1", "folder_1"),
            ("msg_2", "folder_1"),
            ("msg_3", "folder_1"),
        ]
        result = mover.move_batch(moves)

        assert result.successful_count == 2
        assert result.failed_count == 1
        assert "msg_2" in result.failed_ids

    def test_batch_move_all_fail(self):
        backend = MagicMock(spec=MoveBackend)
        backend.move_email.return_value = False
        backend.get_email_folder.return_value = "inbox_id"
        mover = EmailMover(backend)

        moves = [("msg_1", "folder_1"), ("msg_2", "folder_1")]
        result = mover.move_batch(moves)

        assert result.successful_count == 0
        assert result.failed_count == 2
        assert result.failed_ids == ["msg_1", "msg_2"]

    def test_batch_move_empty_list(self):
        backend = MagicMock(spec=MoveBackend)
        mover = EmailMover(backend)

        result = mover.move_batch([])

        assert result.successful_count == 0
        assert result.failed_count == 0
        assert result.skipped_count == 0
        assert result.duration >= 0.0

    def test_batch_move_with_progress_callback(self):
        backend = MagicMock(spec=MoveBackend)
        backend.move_email.return_value = True
        backend.get_email_folder.return_value = "inbox_id"
        mover = EmailMover(backend)

        progress_calls = []

        def progress_cb(completed: int, total: int):
            progress_calls.append((completed, total))

        moves = [
            ("msg_1", "folder_1"),
            ("msg_2", "folder_1"),
            ("msg_3", "folder_1"),
        ]
        mover.move_batch(moves, progress_callback=progress_cb)

        # Should call progress for each email
        assert len(progress_calls) == 3
        assert progress_calls[0] == (1, 3)
        assert progress_calls[1] == (2, 3)
        assert progress_calls[2] == (3, 3)

    def test_batch_move_skips_already_in_target(self):
        """Idempotent batch: emails already in target folder are skipped."""
        backend = MagicMock(spec=MoveBackend)

        def folder_side_effect(email_id):
            if email_id == "msg_2":
                return "folder_1"  # already in target
            return "inbox_id"

        backend.get_email_folder.side_effect = folder_side_effect
        backend.move_email.return_value = True
        mover = EmailMover(backend)

        moves = [
            ("msg_1", "folder_1"),
            ("msg_2", "folder_1"),  # already there
            ("msg_3", "folder_1"),
        ]
        result = mover.move_batch(moves)

        assert result.successful_count == 2
        assert result.skipped_count == 1
        assert result.failed_count == 0
        # move_email should only be called for msg_1 and msg_3
        assert backend.move_email.call_count == 2

    def test_batch_move_logs_all_moves(self, tmp_path):
        """All moves in a batch are logged to ActionLogger."""
        backend = MagicMock(spec=MoveBackend)
        backend.move_email.return_value = True
        backend.get_email_folder.return_value = "inbox_id"
        action_logger = ActionLogger(log_path=tmp_path / "actions.jsonl")
        mover = EmailMover(backend, action_logger=action_logger)

        moves = [
            ("msg_1", "folder_1"),
            ("msg_2", "folder_2"),
        ]
        mover.move_batch(moves)

        actions = action_logger.get_actions()
        assert len(actions) == 2
        assert all(a.action_type == ActionType.EMAIL_MOVE for a in actions)
        assert all(a.success is True for a in actions)

    def test_batch_move_dry_run(self):
        """Dry-run batch: no API calls, all counted as successful."""
        backend = MagicMock(spec=MoveBackend)
        backend.get_email_folder.return_value = "inbox_id"
        mover = EmailMover(backend, dry_run=True)

        moves = [
            ("msg_1", "folder_1"),
            ("msg_2", "folder_2"),
        ]
        result = mover.move_batch(moves)

        assert result.successful_count == 2
        assert result.failed_count == 0
        backend.move_email.assert_not_called()

    def test_batch_move_dry_run_skips_already_in_target(self):
        """Dry-run should still detect and skip already-in-target emails."""
        backend = MagicMock(spec=MoveBackend)

        def folder_side_effect(email_id):
            if email_id == "msg_2":
                return "folder_1"
            return "inbox_id"

        backend.get_email_folder.side_effect = folder_side_effect
        mover = EmailMover(backend, dry_run=True)

        moves = [
            ("msg_1", "folder_1"),
            ("msg_2", "folder_1"),  # already there
        ]
        result = mover.move_batch(moves)

        assert result.successful_count == 1
        assert result.skipped_count == 1


# =============================================================================
# Rate limiting tests
# =============================================================================


class TestEmailMoverRateLimiting:
    """Tests for rate limiting / delay between requests."""

    def test_rate_limit_delay_between_moves(self):
        """Configurable delay between API calls."""
        backend = MagicMock(spec=MoveBackend)
        backend.move_email.return_value = True
        backend.get_email_folder.return_value = "inbox_id"
        # 0.05s delay to keep tests fast but measurable
        mover = EmailMover(backend, rate_limit_delay=0.05)

        moves = [("msg_1", "folder_1"), ("msg_2", "folder_1")]

        start = time.monotonic()
        mover.move_batch(moves)
        elapsed = time.monotonic() - start

        # Should take at least 1 delay (between the 2 moves)
        assert elapsed >= 0.04  # allow small timing tolerance

    def test_zero_delay_is_allowed(self):
        """Setting delay to 0 means no rate limiting."""
        backend = MagicMock(spec=MoveBackend)
        backend.move_email.return_value = True
        backend.get_email_folder.return_value = "inbox_id"
        mover = EmailMover(backend, rate_limit_delay=0.0)

        moves = [("msg_1", "folder_1"), ("msg_2", "folder_1")]
        result = mover.move_batch(moves)

        assert result.successful_count == 2

    def test_default_delay_is_reasonable(self):
        """Default delay should be set (not None or negative)."""
        backend = MagicMock(spec=MoveBackend)
        mover = EmailMover(backend)
        assert mover._rate_limit_delay >= 0.0


# =============================================================================
# Rollback support
# =============================================================================


class TestEmailMoverRollback:
    """Tests for rollback integration via ActionLogger."""

    def test_moves_are_reversible_in_action_log(self, tmp_path):
        """Move actions should be logged as reversible."""
        backend = MagicMock(spec=MoveBackend)
        backend.move_email.return_value = True
        backend.get_email_folder.return_value = "inbox_id"
        action_logger = ActionLogger(log_path=tmp_path / "actions.jsonl")
        mover = EmailMover(backend, action_logger=action_logger)

        mover.move_email("msg_1", "folder_1")

        actions = action_logger.get_actions()
        assert len(actions) == 1
        assert actions[0].reversible is True

    def test_move_logs_source_and_target_for_rollback(self, tmp_path):
        """Action details must include source and target folder for reversal."""
        backend = MagicMock(spec=MoveBackend)
        backend.move_email.return_value = True
        backend.get_email_folder.return_value = "original_folder_id"
        action_logger = ActionLogger(log_path=tmp_path / "actions.jsonl")
        mover = EmailMover(backend, action_logger=action_logger)

        mover.move_email("msg_1", "target_folder_id")

        actions = action_logger.get_actions()
        details = actions[0].details
        assert details["source_folder_id"] == "original_folder_id"
        assert details["target_folder_id"] == "target_folder_id"

    def test_failed_moves_logged_as_not_reversible(self, tmp_path):
        """Failed moves are not reversible since nothing happened."""
        backend = MagicMock(spec=MoveBackend)
        backend.move_email.return_value = False
        backend.get_email_folder.return_value = "inbox_id"
        action_logger = ActionLogger(log_path=tmp_path / "actions.jsonl")
        mover = EmailMover(backend, action_logger=action_logger)

        mover.move_email("msg_1", "folder_1")

        actions = action_logger.get_actions()
        assert len(actions) == 1
        assert actions[0].reversible is False


# =============================================================================
# Edge cases
# =============================================================================


class TestEmailMoverEdgeCases:
    """Edge cases and error handling."""

    def test_move_email_empty_id_returns_false(self):
        backend = MagicMock(spec=MoveBackend)
        mover = EmailMover(backend)

        success = mover.move_email("", "folder_1")
        assert success is False

    def test_move_email_empty_folder_id_returns_false(self):
        backend = MagicMock(spec=MoveBackend)
        mover = EmailMover(backend)

        success = mover.move_email("msg_1", "")
        assert success is False

    def test_batch_move_exception_in_backend_doesnt_crash(self):
        """If the backend raises an unexpected exception, treat as failure."""
        backend = MagicMock(spec=MoveBackend)
        backend.get_email_folder.return_value = "inbox_id"

        call_count = [0]

        def move_side_effect(email_id, folder_id):
            call_count[0] += 1
            if email_id == "msg_2":
                raise RuntimeError("Unexpected error")
            return True

        backend.move_email.side_effect = move_side_effect
        mover = EmailMover(backend)

        moves = [
            ("msg_1", "folder_1"),
            ("msg_2", "folder_1"),
            ("msg_3", "folder_1"),
        ]
        result = mover.move_batch(moves)

        assert result.successful_count == 2
        assert result.failed_count == 1
        assert "msg_2" in result.failed_ids

    def test_get_email_folder_failure_skips_idempotency_check(self):
        """If we can't determine current folder, proceed with move anyway."""
        backend = MagicMock(spec=MoveBackend)
        backend.get_email_folder.return_value = None  # can't determine
        backend.move_email.return_value = True
        mover = EmailMover(backend)

        success = mover.move_email("msg_1", "folder_1")

        assert success is True
        backend.move_email.assert_called_once()

    def test_mover_repr(self):
        backend = MagicMock(spec=MoveBackend)
        mover = EmailMover(backend)
        r = repr(mover)
        assert "EmailMover" in r

    def test_mover_dry_run_repr(self):
        backend = MagicMock(spec=MoveBackend)
        mover = EmailMover(backend, dry_run=True)
        r = repr(mover)
        assert "dry_run=True" in r
