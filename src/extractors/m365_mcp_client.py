"""
M365 MCP Client.

Wrapper for M365 MCP server tools to abstract MCP calls.
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
        """
        try:
            # Import the MCP tool at runtime
            # This allows the code to work even if MCP isn't available
            from mcp__m365_email import fetch_emails

            result = fetch_emails(
                user_email=self.user_email,
                max_results=max_results,
                skip=skip
            )

            # The MCP tool returns a list of email messages
            if isinstance(result, list):
                return result
            elif isinstance(result, dict) and "messages" in result:
                return result["messages"]
            else:
                logger.error(f"Unexpected MCP response format: {type(result)}")
                return []

        except ImportError as e:
            logger.error(f"M365 MCP tools not available: {e}")
            raise ConnectionError("M365 MCP server not configured")
        except Exception as e:
            logger.error(f"Failed to fetch emails from M365: {e}")
            raise ConnectionError(f"M365 API error: {str(e)}")

    def get_message_body(self, message_id: str) -> str:
        """
        Fetch full body content of a message.

        Args:
            message_id: Microsoft Graph message ID

        Returns:
            HTML body content

        Raises:
            ConnectionError: If MCP tool call fails
        """
        try:
            # Import the MCP tool at runtime
            from mcp__m365_email import get_message_body

            result = get_message_body(
                user_email=self.user_email,
                message_id=message_id
            )

            # The MCP tool returns the body content
            if isinstance(result, str):
                return result
            elif isinstance(result, dict) and "body" in result:
                return result["body"]
            else:
                logger.error(f"Unexpected MCP response format: {type(result)}")
                return ""

        except ImportError as e:
            logger.error(f"M365 MCP tools not available: {e}")
            raise ConnectionError("M365 MCP server not configured")
        except Exception as e:
            logger.error(f"Failed to get message body: {e}")
            raise ConnectionError(f"M365 API error: {str(e)}")
