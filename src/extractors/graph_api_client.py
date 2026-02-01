"""
Microsoft Graph API client using MSAL device code flow.

Replaces the M365MCPClient stub with a real implementation that works
standalone with personal Hotmail/Outlook.com accounts via /me/messages.

Authentication:
    - First run: displays a device code + URL for browser auth
    - Subsequent runs: uses cached token (no re-auth needed)
    - Token cache: ~/.email-analyzer/ms_token_cache.json
"""
import json
from pathlib import Path
from typing import Any

import msal
import requests

from src.utils.logger import get_logger

logger = get_logger(__name__)

# Default public client ID (Microsoft Graph Explorer - well-known public client)
DEFAULT_CLIENT_ID = "14d82eec-204b-4c2f-b7e8-296a70dab67e"

# Personal accounts use "common" tenant
DEFAULT_TENANT_ID = "common"

# Scopes for reading email
SCOPES = ["Mail.Read", "User.Read"]

# Token cache location
TOKEN_CACHE_DIR = Path.home() / ".email-analyzer"
TOKEN_CACHE_FILE = TOKEN_CACHE_DIR / "ms_token_cache.json"

GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"


class GraphAPIClient:
    """
    Microsoft Graph API client with device code authentication.

    Uses /me/messages endpoint which works with both personal (Hotmail/Outlook.com)
    and work/school accounts.
    """

    def __init__(
        self,
        user_email: str,
        client_id: str | None = None,
        tenant_id: str | None = None,
        token_cache_path: Path | None = None,
    ):
        self.user_email = user_email
        self.client_id = client_id or DEFAULT_CLIENT_ID
        self.tenant_id = tenant_id or DEFAULT_TENANT_ID
        self.token_cache_path = token_cache_path or TOKEN_CACHE_FILE
        self._access_token: str | None = None
        self._app: msal.PublicClientApplication | None = None

    def _get_token_cache(self) -> msal.SerializableTokenCache:
        """Load or create MSAL token cache."""
        cache = msal.SerializableTokenCache()
        self.token_cache_path.parent.mkdir(parents=True, exist_ok=True)
        if self.token_cache_path.exists():
            cache.deserialize(self.token_cache_path.read_text())
        return cache

    def _save_token_cache(self, cache: msal.SerializableTokenCache) -> None:
        """Persist token cache to disk."""
        if cache.has_state_changed:
            self.token_cache_path.parent.mkdir(parents=True, exist_ok=True)
            self.token_cache_path.write_text(cache.serialize())

    def _get_app(self) -> msal.PublicClientApplication:
        """Get or create the MSAL application."""
        if self._app is None:
            cache = self._get_token_cache()
            self._app = msal.PublicClientApplication(
                self.client_id,
                authority=f"https://login.microsoftonline.com/{self.tenant_id}",
                token_cache=cache,
            )
        return self._app

    def authenticate(self, force_new: bool = False) -> str:
        """
        Authenticate and return access token.

        Tries cached token first, falls back to device code flow.

        Args:
            force_new: Force re-authentication even if token is cached

        Returns:
            OAuth access token string

        Raises:
            RuntimeError: If authentication fails
        """
        app = self._get_app()

        # Try silent auth from cache
        if not force_new:
            accounts = app.get_accounts()
            if accounts:
                logger.info(f"Using cached credentials for {accounts[0]['username']}")
                result = app.acquire_token_silent(SCOPES, account=accounts[0])
                if result and "access_token" in result:
                    self._access_token = result["access_token"]
                    self._save_token_cache(app.token_cache)
                    return self._access_token

        # Device code flow
        logger.info("Starting device code authentication flow...")
        print("\n" + "=" * 60)
        print("MICROSOFT AUTHENTICATION REQUIRED")
        print("=" * 60)

        flow = app.initiate_device_flow(scopes=SCOPES)
        if "user_code" not in flow:
            raise RuntimeError(
                f"Failed to create device flow: {flow.get('error_description')}"
            )

        print(flow["message"])
        print("=" * 60 + "\n")

        result = app.acquire_token_by_device_flow(flow)

        if "access_token" in result:
            self._save_token_cache(app.token_cache)
            self._access_token = result["access_token"]
            logger.info("Authentication successful, token cached.")
            return self._access_token

        raise RuntimeError(
            f"Authentication failed: {result.get('error_description', 'Unknown error')}"
        )

    def _ensure_authenticated(self) -> str:
        """Ensure we have a valid access token."""
        if self._access_token is None:
            return self.authenticate()
        return self._access_token

    def _make_request(
        self,
        url: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Make authenticated GET request to Graph API.

        Handles token refresh on 401 responses.

        Args:
            url: Full Graph API URL
            params: Query parameters

        Returns:
            JSON response dict

        Raises:
            ConnectionError: On network or API errors
        """
        token = self._ensure_authenticated()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        response = requests.get(url, headers=headers, params=params, timeout=30)

        # Handle token expiry — re-auth and retry once
        if response.status_code == 401:
            logger.info("Token expired, re-authenticating...")
            token = self.authenticate(force_new=True)
            headers["Authorization"] = f"Bearer {token}"
            response = requests.get(url, headers=headers, params=params, timeout=30)

        if response.status_code == 429:
            raise ConnectionError("Rate limited by Microsoft Graph API")

        response.raise_for_status()
        return response.json()

    def fetch_emails(
        self,
        max_results: int = 500,
        skip: int = 0,
    ) -> list[dict[str, Any]]:
        """
        Fetch emails from inbox via Microsoft Graph /me/messages.

        Compatible with the M365MCPClient interface for drop-in replacement.

        Args:
            max_results: Maximum emails to return
            skip: Number of emails to skip (pagination)

        Returns:
            List of message dicts in Microsoft Graph format

        Raises:
            ConnectionError: On API errors
        """
        url = f"{GRAPH_BASE_URL}/me/messages"

        # Graph API caps $top at 999 per request
        page_size = min(max_results, 999)

        params = {
            "$top": page_size,
            "$skip": skip,
            "$select": (
                "id,subject,from,toRecipients,receivedDateTime,"
                "body,bodyPreview,hasAttachments,conversationId,"
                "internetMessageHeaders"
            ),
            "$orderby": "receivedDateTime DESC",
        }

        logger.debug(f"Fetching emails: skip={skip}, top={page_size}")

        try:
            data = self._make_request(url, params)
            messages = data.get("value", [])
            logger.info(f"Fetched {len(messages)} emails (skip={skip})")
            return messages
        except requests.exceptions.HTTPError as e:
            raise ConnectionError(f"Graph API error: {e}") from e
        except requests.exceptions.ConnectionError as e:
            raise ConnectionError(f"Network error reaching Graph API: {e}") from e

    def get_message_body(self, message_id: str) -> str:
        """
        Fetch full body of a specific message.

        Args:
            message_id: Microsoft Graph message ID

        Returns:
            HTML body content

        Raises:
            ConnectionError: On API errors
        """
        url = f"{GRAPH_BASE_URL}/me/messages/{message_id}"
        params = {"$select": "body"}

        try:
            data = self._make_request(url, params)
            return data.get("body", {}).get("content", "")
        except Exception as e:
            logger.error(f"Failed to get message body: {e}")
            raise ConnectionError(f"Failed to get message body: {e}") from e

    def get_user_email(self) -> str:
        """
        Get the authenticated user's email address from Graph API.

        Returns:
            Email address string
        """
        url = f"{GRAPH_BASE_URL}/me"
        params = {"$select": "mail,userPrincipalName"}

        try:
            data = self._make_request(url, params)
            return data.get("mail") or data.get("userPrincipalName", self.user_email)
        except Exception:
            return self.user_email
