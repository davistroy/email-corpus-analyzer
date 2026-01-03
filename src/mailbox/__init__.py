"""
Mailbox management module.

Provides registry and manager for multi-mailbox support.
"""
from .manager import MailboxManager
from .registry import MailboxRegistry

__all__ = [
    "MailboxRegistry",
    "MailboxManager",
]
