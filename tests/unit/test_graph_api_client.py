"""Tests for GraphAPIClient - Microsoft Graph API integration."""
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.extractors.graph_api_client import GraphAPIClient, DEFAULT_CLIENT_ID


@pytest.fixture
def client(tmp_path):
    """Create a GraphAPIClient with temp token cache."""
    return GraphAPIClient(
        user_email="test@hotmail.com",
        token_cache_path=tmp_path / "token_cache.json",
    )


@pytest.fixture
def sample_graph_messages():
    """Sample Microsoft Graph API message responses."""
    return [
        {
            "id": "msg_001",
            "subject": "Test Email 1",
            "from": {
                "emailAddress": {
                    "address": "sender@example.com",
                    "name": "Sender One",
                }
            },
            "toRecipients": [
                {
                    "emailAddress": {
                        "address": "test@hotmail.com",
                        "name": "Test User",
                    }
                }
            ],
            "receivedDateTime": "2025-01-15T10:30:00Z",
            "body": {"contentType": "html", "content": "<p>Hello World</p>"},
            "bodyPreview": "Hello World",
            "hasAttachments": False,
            "conversationId": "conv_001",
        },
        {
            "id": "msg_002",
            "subject": "Newsletter Weekly",
            "from": {
                "emailAddress": {
                    "address": "news@company.com",
                    "name": "Company News",
                }
            },
            "toRecipients": [
                {
                    "emailAddress": {
                        "address": "test@hotmail.com",
                        "name": "Test User",
                    }
                }
            ],
            "receivedDateTime": "2025-01-14T08:00:00Z",
            "body": {"contentType": "html", "content": "<h1>Weekly Update</h1>"},
            "bodyPreview": "Weekly Update",
            "hasAttachments": True,
            "conversationId": "conv_002",
        },
    ]


class TestGraphAPIClientInit:
    def test_default_client_id(self, client):
        assert client.client_id == DEFAULT_CLIENT_ID

    def test_custom_client_id(self, tmp_path):
        c = GraphAPIClient(
            user_email="test@hotmail.com",
            client_id="custom-id",
            token_cache_path=tmp_path / "cache.json",
        )
        assert c.client_id == "custom-id"

    def test_default_tenant(self, client):
        assert client.tenant_id == "common"

    def test_stores_user_email(self, client):
        assert client.user_email == "test@hotmail.com"


class TestGraphAPIClientAuth:
    @patch("src.extractors.graph_api_client.msal.PublicClientApplication")
    def test_silent_auth_from_cache(self, mock_app_cls, client):
        mock_app = MagicMock()
        mock_app_cls.return_value = mock_app
        mock_app.get_accounts.return_value = [{"username": "test@hotmail.com"}]
        mock_app.acquire_token_silent.return_value = {"access_token": "cached_token"}
        mock_app.token_cache = MagicMock()
        mock_app.token_cache.has_state_changed = False

        token = client.authenticate()
        assert token == "cached_token"
        mock_app.acquire_token_silent.assert_called_once()

    @patch("src.extractors.graph_api_client.msal.PublicClientApplication")
    def test_force_new_skips_cache(self, mock_app_cls, client):
        mock_app = MagicMock()
        mock_app_cls.return_value = mock_app
        mock_app.initiate_device_flow.return_value = {
            "user_code": "ABC123",
            "message": "Go to https://...",
        }
        mock_app.acquire_token_by_device_flow.return_value = {
            "access_token": "new_token"
        }
        mock_app.token_cache = MagicMock()
        mock_app.token_cache.has_state_changed = False

        token = client.authenticate(force_new=True)
        assert token == "new_token"
        mock_app.get_accounts.assert_not_called()

    @patch("src.extractors.graph_api_client.msal.PublicClientApplication")
    def test_auth_failure_raises(self, mock_app_cls, client):
        mock_app = MagicMock()
        mock_app_cls.return_value = mock_app
        mock_app.get_accounts.return_value = []
        mock_app.initiate_device_flow.return_value = {
            "user_code": "ABC",
            "message": "Go to...",
        }
        mock_app.acquire_token_by_device_flow.return_value = {
            "error_description": "Timeout"
        }
        mock_app.token_cache = MagicMock()
        mock_app.token_cache.has_state_changed = False

        with pytest.raises(RuntimeError, match="Timeout"):
            client.authenticate()


class TestGraphAPIClientFetchEmails:
    @patch("src.extractors.graph_api_client.requests.get")
    def test_fetch_emails_success(self, mock_get, client, sample_graph_messages):
        client._access_token = "test_token"
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"value": sample_graph_messages}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = client.fetch_emails(max_results=10, skip=0)

        assert len(result) == 2
        assert result[0]["id"] == "msg_001"
        assert result[1]["subject"] == "Newsletter Weekly"

    @patch("src.extractors.graph_api_client.requests.get")
    def test_fetch_emails_empty(self, mock_get, client):
        client._access_token = "test_token"
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"value": []}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = client.fetch_emails()
        assert result == []

    @patch("src.extractors.graph_api_client.requests.get")
    def test_fetch_emails_pagination_params(self, mock_get, client):
        client._access_token = "test_token"
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"value": []}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        client.fetch_emails(max_results=50, skip=100)

        call_kwargs = mock_get.call_args
        params = call_kwargs.kwargs.get("params") or call_kwargs[1].get("params")
        assert params["$top"] == 50
        assert params["$skip"] == 100

    @patch("src.extractors.graph_api_client.requests.get")
    def test_fetch_emails_caps_at_999(self, mock_get, client):
        client._access_token = "test_token"
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"value": []}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        client.fetch_emails(max_results=5000)

        call_kwargs = mock_get.call_args
        params = call_kwargs.kwargs.get("params") or call_kwargs[1].get("params")
        assert params["$top"] == 999

    @patch("src.extractors.graph_api_client.requests.get")
    def test_rate_limit_raises_connection_error(self, mock_get, client):
        client._access_token = "test_token"
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_get.return_value = mock_response

        with pytest.raises(ConnectionError, match="Rate limited"):
            client.fetch_emails()

    @patch("src.extractors.graph_api_client.requests.get")
    def test_token_refresh_on_401(self, mock_get, client):
        client._access_token = "old_token"

        # First call returns 401, second returns success
        expired_response = MagicMock()
        expired_response.status_code = 401

        success_response = MagicMock()
        success_response.status_code = 200
        success_response.json.return_value = {"value": []}
        success_response.raise_for_status = MagicMock()

        mock_get.side_effect = [expired_response, success_response]

        with patch.object(client, "authenticate", return_value="new_token"):
            result = client.fetch_emails()
            assert result == []


class TestGraphAPIClientGetMessageBody:
    @patch("src.extractors.graph_api_client.requests.get")
    def test_get_message_body(self, mock_get, client):
        client._access_token = "test_token"
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "body": {"content": "<p>Full email body</p>"}
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        body = client.get_message_body("msg_001")
        assert body == "<p>Full email body</p>"


class TestGraphAPIClientGetUserEmail:
    @patch("src.extractors.graph_api_client.requests.get")
    def test_get_user_email(self, mock_get, client):
        client._access_token = "test_token"
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "mail": "test@hotmail.com",
            "userPrincipalName": "test@hotmail.com",
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        email = client.get_user_email()
        assert email == "test@hotmail.com"

    @patch("src.extractors.graph_api_client.requests.get")
    def test_get_user_email_fallback(self, mock_get, client):
        client._access_token = "test_token"
        mock_get.side_effect = Exception("API Error")

        email = client.get_user_email()
        assert email == "test@hotmail.com"  # Falls back to constructor email
