# Integrating M365 MCP Server with Email Processor

This guide shows how to update the email extractor to use the MCP server.

## Current State

File: `initial-learning/src/extractors/m365_extractor.py`

**Lines 61-75** currently contain stub logic:

```python
# STUB: Replace with actual M365 MCP tool calls
# Expected MCP tool: fetch_emails(user_email, batch_size, skip)
stub_emails = [
    {
        "id": f"stub_email_{i}",
        "subject": f"Test Email {i}",
        "from": {"emailAddress": {"address": "test@example.com", "name": "Test"}},
        # ... stub data
    }
    for i in range(batch_size_to_use)
]
batch_emails = stub_emails
```

## Updated Implementation

Replace lines 61-75 with actual MCP tool calls:

```python
# Call M365 MCP server to fetch emails
# Assuming MCP tools are available as:
# - mcp__m365_email__fetch_emails
# - mcp__m365_email__get_message_body

import json

# Fetch emails using MCP tool
try:
    # In Claude Code environment, MCP tools would be called like:
    # result = await call_mcp_tool("m365-email", "fetch_emails", {
    #     "user_email": user_email,
    #     "max_results": batch_size_to_use,
    #     "skip": skip_count
    # })

    # For now, this shows the structure - actual implementation
    # would use Claude Code's MCP integration

    # Placeholder for MCP call result
    mcp_result = {
        "messages": [],
        "count": 0,
        "has_more": False
    }

    # Parse MCP response
    if isinstance(mcp_result, str):
        mcp_result = json.loads(mcp_result)

    batch_emails = mcp_result.get("messages", [])
    has_more = mcp_result.get("has_more", False)

    logger.info(f"Fetched {len(batch_emails)} emails from M365 (skip={skip_count})")

except Exception as e:
    logger.error(f"Failed to fetch emails from M365: {e}")
    raise ExtractionError(
        message=f"M365 API error: {str(e)}",
        error_type="api_error",
        email_id=None
    )
```

## Better Approach: Abstract MCP Calls

Create a helper module for MCP integration:

### File: `initial-learning/src/extractors/m365_mcp_client.py`

```python
"""
M365 MCP Client

Wrapper for M365 MCP server tools to abstract MCP calls.
"""
import json
from typing import Any, Dict, List
from src.utils.logger import get_logger

logger = get_logger(__name__)


class M365MCPClient:
    """Client for M365 MCP server."""

    def __init__(self, user_email: str):
        """
        Initialize MCP client.

        Args:
            user_email: M365 user email address
        """
        self.user_email = user_email

    async def fetch_emails(
        self,
        max_results: int = 500,
        skip: int = 0
    ) -> Dict[str, Any]:
        """
        Fetch emails from M365 inbox.

        Args:
            max_results: Maximum emails to fetch
            skip: Number of emails to skip (pagination)

        Returns:
            Dict with 'messages', 'count', 'has_more'
        """
        # TODO: Replace with actual MCP tool call
        # In Claude Code, this would use the MCP integration
        # For example:
        # result = await self._call_mcp_tool(
        #     "fetch_emails",
        #     {
        #         "user_email": self.user_email,
        #         "max_results": max_results,
        #         "skip": skip
        #     }
        # )

        # Stub for now
        logger.warning("M365MCPClient is using stub data - MCP not connected")
        return {
            "messages": [],
            "count": 0,
            "has_more": False
        }

    async def get_message_body(self, message_id: str) -> str:
        """
        Fetch full body content of a message.

        Args:
            message_id: Microsoft Graph message ID

        Returns:
            HTML body content
        """
        # TODO: Replace with actual MCP tool call
        # result = await self._call_mcp_tool(
        #     "get_message_body",
        #     {
        #         "user_email": self.user_email,
        #         "message_id": message_id
        #     }
        # )

        # Stub for now
        logger.warning("M365MCPClient is using stub data - MCP not connected")
        return "<p>Stub email body</p>"
```

### Updated `m365_extractor.py`

Then in `m365_extractor.py`, use the client:

```python
# At top of file
from src.extractors.m365_mcp_client import M365MCPClient

# In __init__ method
def __init__(self, user_email: str):
    self.user_email = user_email
    self.mcp_client = M365MCPClient(user_email)
    self.logger = get_logger(__name__)

# In extract_all method, replace stub section:
async def extract_batch(skip_count: int, batch_size: int):
    """Fetch one batch of emails."""
    # Use MCP client
    result = await self.mcp_client.fetch_emails(
        max_results=batch_size,
        skip=skip_count
    )

    batch_emails = result.get("messages", [])
    # ... rest of processing
```

## When MCP Server is Ready

Once the M365 MCP server is configured in Claude Code:

1. **Verify tools are available**:
   - Check Claude Code recognizes `mcp__m365_email__fetch_emails`
   - Check Claude Code recognizes `mcp__m365_email__get_message_body`

2. **Update `m365_mcp_client.py`**:
   - Replace stub implementations with actual MCP tool calls
   - Use Claude Code's MCP integration mechanism

3. **Test extraction**:
   ```bash
   cd /home/davistroy/dev/email-processor/initial-learning
   ./venv/bin/python -m src.main extract --batch-size 50
   ```

4. **Monitor logs**:
   ```bash
   tail -f outputs/extraction_errors.log
   ```

## Alternative: Direct API Calls (No MCP)

If you prefer not to use MCP, you can make direct Microsoft Graph API calls:

### File: `initial-learning/src/extractors/graph_api_client.py`

```python
"""Direct Microsoft Graph API client (no MCP)."""
import httpx
import msal
from typing import Dict, Any, List


class GraphAPIClient:
    """Direct Microsoft Graph API client."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        tenant_id: str,
        user_email: str
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.tenant_id = tenant_id
        self.user_email = user_email
        self._token = None

    def _get_token(self) -> str:
        """Get access token using MSAL."""
        if self._token:
            return self._token

        app = msal.ConfidentialClientApplication(
            self.client_id,
            authority=f"https://login.microsoftonline.com/{self.tenant_id}",
            client_credential=self.client_secret,
        )

        result = app.acquire_token_for_client(
            scopes=["https://graph.microsoft.com/.default"]
        )

        if "access_token" in result:
            self._token = result["access_token"]
            return self._token
        else:
            raise Exception(f"Auth failed: {result.get('error_description')}")

    async def fetch_emails(
        self,
        max_results: int = 500,
        skip: int = 0
    ) -> Dict[str, Any]:
        """Fetch emails from Microsoft Graph API."""
        token = self._get_token()

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        url = f"https://graph.microsoft.com/v1.0/users/{self.user_email}/messages"
        params = {
            "$top": min(max_results, 999),
            "$skip": skip,
            "$select": "id,subject,from,receivedDateTime,body,hasAttachments,toRecipients"
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()

            return {
                "messages": data.get("value", []),
                "count": len(data.get("value", [])),
                "has_more": len(data.get("value", [])) == max_results
            }
```

Then use this in `m365_extractor.py` instead of MCP client.

## Recommendation

**Use the MCP approach** - it's cleaner, more maintainable, and follows the app's architecture. The direct API approach is only for environments where MCP isn't available.
