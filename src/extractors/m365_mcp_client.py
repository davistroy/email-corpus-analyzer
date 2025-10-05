"""
M365 MCP Client.

Wrapper for M365 MCP server tools to abstract MCP calls.

NOTE: This module is designed to work with Claude Code's MCP integration.
In production, MCP tools are called via Claude Code's MCP server integration,
not as importable Python modules. This file contains a fallback implementation
for environments where MCP is not available.
"""
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

    def fetch_emails(
        self,
        max_results: int = 500,
        skip: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Fetch emails from M365 inbox.

        Args:
            max_results: Maximum emails to fetch
            skip: Number of emails to skip (pagination)

        Returns:
            List of email message dictionaries

        Raises:
            ConnectionError: If MCP tool call fails

        Note:
            This method is a stub when running outside Claude Code.
            When executed via Claude Code with M365 MCP configured,
            Claude will call mcp__m365-email__fetch_emails directly.
        """
        logger.warning(
            "M365MCPClient.fetch_emails() called in stub mode. "
            "This requires Claude Code with M365 MCP server configured. "
            "Returning empty list."
        )

        # Fallback: return empty list when MCP not available
        # In production with Claude Code, this would be replaced with actual MCP calls
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
