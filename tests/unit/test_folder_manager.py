"""
Unit tests for FolderManager (Phase 5, Item 5.1).

Tests folder creation, listing, deduplication, nesting, dry-run mode,
and error handling for both M365 (Graph API) and Gmail (Labels API) backends.

TDD: These tests are written first, implementation follows.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.actions.folder_manager import (
    FolderInfo,
    FolderManager,
    GmailFolderBackend,
    M365FolderBackend,
)
from src.exceptions import FolderActionError

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
    """Create a mock Gmail API service (googleapiclient Resource)."""
    return MagicMock()


# =============================================================================
# FolderInfo model tests
# =============================================================================


class TestFolderInfo:
    """Tests for the FolderInfo data class."""

    def test_create_folder_info(self):
        info = FolderInfo(folder_id="abc123", name="Newsletters", provider="m365")
        assert info.folder_id == "abc123"
        assert info.name == "Newsletters"
        assert info.provider == "m365"
        assert info.parent_id is None

    def test_create_folder_info_with_parent(self):
        info = FolderInfo(folder_id="child1", name="Tech", provider="m365", parent_id="parent1")
        assert info.parent_id == "parent1"

    def test_folder_info_equality(self):
        a = FolderInfo(folder_id="x", name="A", provider="m365")
        b = FolderInfo(folder_id="x", name="A", provider="m365")
        assert a == b

    def test_folder_info_repr(self):
        info = FolderInfo(folder_id="x", name="Test", provider="gmail")
        r = repr(info)
        assert "Test" in r
        assert "gmail" in r


# =============================================================================
# M365FolderBackend tests
# =============================================================================


class TestM365FolderBackend:
    """Tests for the Microsoft 365 / Graph API folder backend."""

    def test_list_folders_calls_graph_api(self):
        client = _mock_graph_client()
        client._make_request = MagicMock(
            return_value={
                "value": [
                    {"id": "f1", "displayName": "Inbox", "parentFolderId": None},
                    {"id": "f2", "displayName": "Newsletters", "parentFolderId": None},
                ]
            }
        )
        backend = M365FolderBackend(client)
        folders = backend.list_folders()

        assert len(folders) == 2
        assert folders[0].folder_id == "f1"
        assert folders[0].name == "Inbox"
        assert folders[1].folder_id == "f2"
        assert folders[1].name == "Newsletters"
        assert all(f.provider == "m365" for f in folders)

    def test_list_folders_includes_child_folders(self):
        """list_folders returns child folder info with parent_id set."""
        client = _mock_graph_client()
        client._make_request = MagicMock(
            return_value={
                "value": [
                    {
                        "id": "parent1",
                        "displayName": "Projects",
                        "parentFolderId": "root",
                    },
                    {
                        "id": "child1",
                        "displayName": "Alpha",
                        "parentFolderId": "parent1",
                    },
                ]
            }
        )
        backend = M365FolderBackend(client)
        folders = backend.list_folders()

        assert len(folders) == 2
        child = [f for f in folders if f.name == "Alpha"][0]
        assert child.parent_id == "parent1"

    def test_create_folder_posts_to_graph(self):
        client = _mock_graph_client()
        client._make_request = MagicMock(
            return_value={"id": "new_folder_id", "displayName": "Newsletters"}
        )
        backend = M365FolderBackend(client)
        folder_id = backend.create_folder("Newsletters")

        assert folder_id == "new_folder_id"
        # Verify POST was called with correct URL and data
        client._make_request.assert_called_once()
        call_args = client._make_request.call_args
        assert "/me/mailFolders" in call_args[0][0]
        assert call_args[1]["method"] == "POST"
        assert call_args[1]["json_data"]["displayName"] == "Newsletters"

    def test_create_subfolder_posts_under_parent(self):
        client = _mock_graph_client()
        client._make_request = MagicMock(return_value={"id": "sub_id", "displayName": "Tech"})
        backend = M365FolderBackend(client)
        folder_id = backend.create_folder("Tech", parent_id="parent_id")

        assert folder_id == "sub_id"
        call_args = client._make_request.call_args
        assert "/me/mailFolders/parent_id/childFolders" in call_args[0][0]
        assert call_args[1]["method"] == "POST"

    def test_create_folder_api_error_raises(self):
        client = _mock_graph_client()
        client._make_request = MagicMock(
            side_effect=ConnectionError("Graph API error: 403 Forbidden")
        )
        backend = M365FolderBackend(client)

        with pytest.raises(FolderActionError, match="Failed to create folder"):
            backend.create_folder("BadFolder")

    def test_list_folders_api_error_raises(self):
        client = _mock_graph_client()
        client._make_request = MagicMock(side_effect=ConnectionError("Network error"))
        backend = M365FolderBackend(client)

        with pytest.raises(FolderActionError, match="Failed to list folders"):
            backend.list_folders()


# =============================================================================
# GmailFolderBackend tests
# =============================================================================


class TestGmailFolderBackend:
    """Tests for the Gmail / Labels API folder backend."""

    def test_list_folders_calls_labels_api(self):
        service = _mock_gmail_service()
        service.users().labels().list.return_value.execute.return_value = {
            "labels": [
                {"id": "Label_1", "name": "Newsletters", "type": "user"},
                {"id": "Label_2", "name": "Receipts", "type": "user"},
                {"id": "INBOX", "name": "INBOX", "type": "system"},
            ]
        }
        backend = GmailFolderBackend(service)
        folders = backend.list_folders()

        # Should only return user labels, not system labels
        assert len(folders) == 2
        assert folders[0].folder_id == "Label_1"
        assert folders[0].name == "Newsletters"
        assert all(f.provider == "gmail" for f in folders)

    def test_list_folders_includes_nested_labels(self):
        """Gmail uses '/' separators for nested labels."""
        service = _mock_gmail_service()
        service.users().labels().list.return_value.execute.return_value = {
            "labels": [
                {"id": "L1", "name": "Projects", "type": "user"},
                {"id": "L2", "name": "Projects/Alpha", "type": "user"},
            ]
        }
        backend = GmailFolderBackend(service)
        folders = backend.list_folders()

        assert len(folders) == 2
        nested = [f for f in folders if f.name == "Projects/Alpha"][0]
        # Gmail nested labels still have parent info derivable from name
        assert nested.folder_id == "L2"

    def test_create_label_calls_api(self):
        service = _mock_gmail_service()
        service.users().labels().create.return_value.execute.return_value = {
            "id": "Label_new",
            "name": "Newsletters",
        }
        backend = GmailFolderBackend(service)
        label_id = backend.create_folder("Newsletters")

        assert label_id == "Label_new"
        service.users().labels().create.assert_called_once()
        call_kwargs = service.users().labels().create.call_args[1]
        assert call_kwargs["userId"] == "me"
        body = call_kwargs["body"]
        assert body["name"] == "Newsletters"
        assert body["labelListVisibility"] == "labelShow"
        assert body["messageListVisibility"] == "show"

    def test_create_nested_label_uses_slash_separator(self):
        """Gmail nests labels via name with '/' separator."""
        service = _mock_gmail_service()
        service.users().labels().create.return_value.execute.return_value = {
            "id": "Label_nested",
            "name": "Projects/Alpha",
        }
        backend = GmailFolderBackend(service)
        label_id = backend.create_folder("Alpha", parent_name="Projects")

        assert label_id == "Label_nested"
        call_kwargs = service.users().labels().create.call_args[1]
        assert call_kwargs["body"]["name"] == "Projects/Alpha"

    def test_create_label_api_error_raises(self):
        service = _mock_gmail_service()
        service.users().labels().create.return_value.execute.side_effect = Exception(
            "Gmail API error"
        )
        backend = GmailFolderBackend(service)

        with pytest.raises(FolderActionError, match="Failed to create folder"):
            backend.create_folder("BadLabel")

    def test_list_folders_api_error_raises(self):
        service = _mock_gmail_service()
        service.users().labels().list.return_value.execute.side_effect = Exception(
            "Gmail API error"
        )
        backend = GmailFolderBackend(service)

        with pytest.raises(FolderActionError, match="Failed to list folders"):
            backend.list_folders()


# =============================================================================
# FolderManager tests — core logic (backend-agnostic)
# =============================================================================


class TestFolderManagerCreateFolder:
    """Tests for FolderManager.create_folder()."""

    def test_create_folder_returns_id(self):
        backend = MagicMock()
        backend.create_folder.return_value = "new_id"
        backend.list_folders.return_value = []
        mgr = FolderManager(backend)
        result = mgr.create_folder("Newsletters")

        assert result == "new_id"
        backend.create_folder.assert_called_once_with("Newsletters", parent_id=None)

    def test_create_folder_with_parent(self):
        backend = MagicMock()
        backend.create_folder.return_value = "child_id"
        backend.list_folders.return_value = []
        mgr = FolderManager(backend)
        result = mgr.create_folder("Tech", parent_id="parent_id")

        assert result == "child_id"
        backend.create_folder.assert_called_once_with("Tech", parent_id="parent_id")

    def test_create_folder_deduplicates_existing(self):
        """If folder already exists with same name, return existing ID."""
        backend = MagicMock()
        backend.list_folders.return_value = [
            FolderInfo(folder_id="existing_id", name="Newsletters", provider="m365"),
        ]
        mgr = FolderManager(backend)
        result = mgr.create_folder("Newsletters")

        assert result == "existing_id"
        backend.create_folder.assert_not_called()

    def test_create_subfolder_deduplicates_under_parent(self):
        """Deduplication should match name AND parent."""
        backend = MagicMock()
        backend.list_folders.return_value = [
            FolderInfo(
                folder_id="existing_child",
                name="Tech",
                provider="m365",
                parent_id="parent1",
            ),
        ]
        backend.create_folder.return_value = "new_child"
        mgr = FolderManager(backend)

        # Same name, same parent => deduplicate
        result = mgr.create_folder("Tech", parent_id="parent1")
        assert result == "existing_child"
        backend.create_folder.assert_not_called()

        # Same name, different parent => create new
        result = mgr.create_folder("Tech", parent_id="parent2")
        assert result == "new_child"
        backend.create_folder.assert_called_once()


class TestFolderManagerEnsureFolders:
    """Tests for FolderManager.ensure_folders()."""

    def test_ensure_folders_creates_missing(self):
        backend = MagicMock()
        backend.list_folders.return_value = []
        backend.create_folder.side_effect = lambda name, **kw: f"id_{name}"
        mgr = FolderManager(backend)

        result = mgr.ensure_folders(["Newsletters", "Receipts", "Social"])

        assert result == {
            "Newsletters": "id_Newsletters",
            "Receipts": "id_Receipts",
            "Social": "id_Social",
        }
        assert backend.create_folder.call_count == 3

    def test_ensure_folders_skips_existing(self):
        backend = MagicMock()
        backend.list_folders.return_value = [
            FolderInfo(folder_id="existing_nl", name="Newsletters", provider="m365"),
        ]
        backend.create_folder.side_effect = lambda name, **kw: f"id_{name}"
        mgr = FolderManager(backend)

        result = mgr.ensure_folders(["Newsletters", "Receipts"])

        assert result == {
            "Newsletters": "existing_nl",
            "Receipts": "id_Receipts",
        }
        # Only Receipts should be created
        backend.create_folder.assert_called_once_with("Receipts", parent_id=None)

    def test_ensure_folders_empty_list(self):
        backend = MagicMock()
        backend.list_folders.return_value = []
        mgr = FolderManager(backend)

        result = mgr.ensure_folders([])
        assert result == {}

    def test_ensure_folders_all_exist(self):
        backend = MagicMock()
        backend.list_folders.return_value = [
            FolderInfo(folder_id="id1", name="A", provider="m365"),
            FolderInfo(folder_id="id2", name="B", provider="m365"),
        ]
        mgr = FolderManager(backend)

        result = mgr.ensure_folders(["A", "B"])
        assert result == {"A": "id1", "B": "id2"}
        backend.create_folder.assert_not_called()

    def test_ensure_folders_case_insensitive_matching(self):
        """Folder name matching should be case-insensitive."""
        backend = MagicMock()
        backend.list_folders.return_value = [
            FolderInfo(folder_id="id1", name="newsletters", provider="m365"),
        ]
        mgr = FolderManager(backend)

        result = mgr.ensure_folders(["Newsletters"])
        assert result == {"Newsletters": "id1"}
        backend.create_folder.assert_not_called()

    def test_ensure_folders_with_parent(self):
        backend = MagicMock()
        backend.list_folders.return_value = [
            FolderInfo(folder_id="parent_id", name="Email Categories", provider="m365"),
        ]
        backend.create_folder.side_effect = lambda name, **kw: f"id_{name}"
        mgr = FolderManager(backend)

        result = mgr.ensure_folders(["Newsletters", "Social"], parent_id="parent_id")

        assert result == {
            "Newsletters": "id_Newsletters",
            "Social": "id_Social",
        }
        # Both should be created under the parent
        for call in backend.create_folder.call_args_list:
            assert call[1].get("parent_id") == "parent_id" or call[0][1:] == ()

    def test_ensure_folders_continues_on_individual_failure(self):
        """If one folder fails to create, continue with others and report errors."""
        backend = MagicMock()
        backend.list_folders.return_value = []

        call_count = [0]

        def create_side_effect(name, **kw):
            call_count[0] += 1
            if name == "BadFolder":
                raise FolderActionError(f"Failed to create folder '{name}'")
            return f"id_{name}"

        backend.create_folder.side_effect = create_side_effect
        mgr = FolderManager(backend)

        result, errors = mgr.ensure_folders_with_errors(["Good1", "BadFolder", "Good2"])

        assert result == {"Good1": "id_Good1", "Good2": "id_Good2"}
        assert len(errors) == 1
        assert "BadFolder" in errors[0]


class TestFolderManagerListFolders:
    """Tests for FolderManager.list_folders()."""

    def test_list_folders_delegates_to_backend(self):
        backend = MagicMock()
        expected = [
            FolderInfo(folder_id="f1", name="Inbox", provider="m365"),
        ]
        backend.list_folders.return_value = expected
        mgr = FolderManager(backend)

        result = mgr.list_folders()
        assert result == expected
        backend.list_folders.assert_called_once()

    def test_list_folders_caches_results(self):
        """Repeated calls to list_folders should use cached data."""
        backend = MagicMock()
        backend.list_folders.return_value = [
            FolderInfo(folder_id="f1", name="Inbox", provider="m365"),
        ]
        mgr = FolderManager(backend)

        mgr.list_folders()
        mgr.list_folders()

        # Backend called only once due to caching
        backend.list_folders.assert_called_once()

    def test_list_folders_cache_invalidated_after_create(self):
        """Creating a folder should invalidate the cache."""
        backend = MagicMock()
        backend.list_folders.return_value = []
        backend.create_folder.return_value = "new_id"
        mgr = FolderManager(backend)

        mgr.list_folders()
        mgr.create_folder("New")
        mgr.list_folders()

        # list_folders should be called twice (once before create, once after)
        assert backend.list_folders.call_count == 2


# =============================================================================
# Dry-run mode tests
# =============================================================================


class TestFolderManagerDryRun:
    """Tests for dry-run mode."""

    def test_dry_run_create_folder_does_not_call_backend(self):
        backend = MagicMock()
        backend.list_folders.return_value = []
        mgr = FolderManager(backend, dry_run=True)

        result = mgr.create_folder("Newsletters")

        assert result is not None  # Returns a placeholder ID
        assert result.startswith("dry-run-")
        backend.create_folder.assert_not_called()

    def test_dry_run_ensure_folders_returns_placeholders(self):
        backend = MagicMock()
        backend.list_folders.return_value = [
            FolderInfo(folder_id="existing_id", name="Existing", provider="m365"),
        ]
        mgr = FolderManager(backend, dry_run=True)

        result = mgr.ensure_folders(["Existing", "NewFolder"])

        # Existing folder should return real ID
        assert result["Existing"] == "existing_id"
        # New folder should return dry-run placeholder
        assert result["NewFolder"].startswith("dry-run-")
        backend.create_folder.assert_not_called()

    def test_dry_run_tracks_planned_actions(self):
        backend = MagicMock()
        backend.list_folders.return_value = []
        mgr = FolderManager(backend, dry_run=True)

        mgr.ensure_folders(["A", "B", "C"])

        planned = mgr.get_planned_actions()
        assert len(planned) == 3
        assert all(a["action"] == "create_folder" for a in planned)
        names = [a["name"] for a in planned]
        assert "A" in names
        assert "B" in names
        assert "C" in names

    def test_dry_run_with_existing_shows_skip(self):
        backend = MagicMock()
        backend.list_folders.return_value = [
            FolderInfo(folder_id="id1", name="Existing", provider="m365"),
        ]
        mgr = FolderManager(backend, dry_run=True)

        mgr.ensure_folders(["Existing", "New"])

        planned = mgr.get_planned_actions()
        # Only 1 create action (skip the existing one)
        create_actions = [a for a in planned if a["action"] == "create_folder"]
        assert len(create_actions) == 1
        assert create_actions[0]["name"] == "New"


# =============================================================================
# Nested folder tests
# =============================================================================


class TestFolderManagerNesting:
    """Tests for nested/hierarchical folder support."""

    def test_ensure_folder_hierarchy_creates_parent_and_children(self):
        backend = MagicMock()
        backend.list_folders.return_value = []

        id_counter = [0]

        def create_with_ids(name, **kw):
            id_counter[0] += 1
            return f"id_{id_counter[0]}"

        backend.create_folder.side_effect = create_with_ids
        mgr = FolderManager(backend)

        result = mgr.ensure_folder_hierarchy(
            "Email Categories", ["Newsletters", "Social", "Receipts"]
        )

        assert "Email Categories" in result
        assert "Newsletters" in result
        assert "Social" in result
        assert "Receipts" in result
        # Parent created first, then children under it
        assert backend.create_folder.call_count == 4  # 1 parent + 3 children

    def test_ensure_folder_hierarchy_reuses_existing_parent(self):
        backend = MagicMock()
        backend.list_folders.return_value = [
            FolderInfo(folder_id="existing_parent", name="Email Categories", provider="m365"),
        ]
        backend.create_folder.side_effect = lambda name, **kw: f"id_{name}"
        mgr = FolderManager(backend)

        result = mgr.ensure_folder_hierarchy("Email Categories", ["Newsletters"])

        assert result["Email Categories"] == "existing_parent"
        # Only child should be created
        backend.create_folder.assert_called_once()

    def test_ensure_folder_hierarchy_empty_children(self):
        """Hierarchy with no children just creates the parent."""
        backend = MagicMock()
        backend.list_folders.return_value = []
        backend.create_folder.return_value = "parent_id"
        mgr = FolderManager(backend)

        result = mgr.ensure_folder_hierarchy("Parent", [])
        assert result == {"Parent": "parent_id"}


# =============================================================================
# Edge cases
# =============================================================================


class TestFolderManagerEdgeCases:
    """Edge case and error handling tests."""

    def test_create_folder_empty_name_raises(self):
        backend = MagicMock()
        backend.list_folders.return_value = []
        mgr = FolderManager(backend)

        with pytest.raises(ValueError, match="Folder name cannot be empty"):
            mgr.create_folder("")

    def test_create_folder_whitespace_only_name_raises(self):
        backend = MagicMock()
        backend.list_folders.return_value = []
        mgr = FolderManager(backend)

        with pytest.raises(ValueError, match="Folder name cannot be empty"):
            mgr.create_folder("   ")

    def test_create_folder_strips_whitespace(self):
        backend = MagicMock()
        backend.list_folders.return_value = []
        backend.create_folder.return_value = "new_id"
        mgr = FolderManager(backend)

        result = mgr.create_folder("  Newsletters  ")
        assert result == "new_id"
        backend.create_folder.assert_called_once_with("Newsletters", parent_id=None)

    def test_ensure_folders_deduplicates_input_names(self):
        """If the same name appears twice in input, only create once."""
        backend = MagicMock()
        backend.list_folders.return_value = []
        backend.create_folder.side_effect = lambda name, **kw: f"id_{name}"
        mgr = FolderManager(backend)

        result = mgr.ensure_folders(["A", "A", "B"])

        assert result == {"A": "id_A", "B": "id_B"}
        assert backend.create_folder.call_count == 2

    def test_folder_manager_repr(self):
        backend = MagicMock()
        mgr = FolderManager(backend)
        r = repr(mgr)
        assert "FolderManager" in r

    def test_folder_manager_dry_run_repr(self):
        backend = MagicMock()
        mgr = FolderManager(backend, dry_run=True)
        r = repr(mgr)
        assert "dry_run=True" in r
