"""
Email provider abstraction layer.

Supports multiple email providers with a unified async interface:
- M365 (Microsoft 365 / Outlook)
- Gmail (Google Workspace / personal Gmail)
- IMAP (Generic IMAP servers)
"""
from .base import EmailProvider, ExtractionProgress
from .factory import create_provider, get_provider_for_mailbox

__all__ = [
    "EmailProvider",
    "ExtractionProgress",
    "create_provider",
    "get_provider_for_mailbox",
]
