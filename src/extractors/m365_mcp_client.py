"""
M365 MCP Client.

Wrapper for M365 MCP server tools to abstract MCP calls.

NOTE: This module is designed to work with Claude Code's MCP integration.
In production, MCP tools are called via Claude Code's MCP server integration,
not as importable Python modules. This file contains a fallback implementation
for environments where MCP is not available.
"""
from typing import Any

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

    def fetch_emails(
        self,
        max_results: int = 500,
        skip: int = 0
    ) -> list[dict[str, Any]]:
        """
        Fetch emails from M365 inbox using MCP server.

        Args:
            max_results: Maximum emails to fetch
            skip: Number of emails to skip (pagination)

        Returns:
            List of email message dictionaries from Microsoft Graph API

        Raises:
            ConnectionError: If MCP tool call fails

        Note:
            This method uses the M365 MCP server through Claude Code.
            When running standalone (outside Claude Code), returns empty list.

            The actual MCP call is handled by the email processor CLI script,
            which invokes this via Claude Code's MCP integration.
        """
        logger.warning(
            "M365MCPClient.fetch_emails() called in stub mode. "
            "To use M365 email extraction, run via the fetch_emails_cli.py script "
            "which will invoke this through Claude Code's MCP integration. "
            "Returning empty list."
        )

        # This is a stub - the actual implementation happens when Claude Code
        # calls this method and uses mcp__m365-email__fetch_emails MCP tool
        return []

    def get_message_body(self, message_id: str) -> str:
        """
        Fetch full body content of a message.

        Args:
            message_id: Microsoft Graph message ID

        Returns:
            HTML body content

        Raises:
            ConnectionError: If MCP tool call fails

        Note:
            This method is a stub when running outside Claude Code.
            When executed via Claude Code with M365 MCP configured,
            Claude will call mcp__m365-email__get_message_body directly.
        """
        logger.warning(
            f"M365MCPClient.get_message_body({message_id}) called in stub mode. "
            "This requires Claude Code with M365 MCP server configured. "
            "Returning empty string."
        )

        # Fallback: return empty string when MCP not available
        # In production with Claude Code, this would be replaced with actual MCP calls
        return ""
