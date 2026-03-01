"""
Actions package for applying categorization results to live mailboxes.

Provides folder management, email moving, rule deployment, and action logging
for both Microsoft 365 (Graph API) and Gmail (Gmail API) mailboxes.

Phase 5 of the implementation plan.
"""

from src.actions.action_logger import (
    ActionLog,
    ActionLogger,
    ActionRecord,
    ActionType,
    RollbackResult,
    get_default_action_log_path,
)
from src.actions.email_mover import (
    EmailMover,
    GmailMoveBackend,
    M365MoveBackend,
    MoveResult,
)

__all__ = [
    "ActionLog",
    "ActionLogger",
    "ActionRecord",
    "ActionType",
    "EmailMover",
    "GmailMoveBackend",
    "M365MoveBackend",
    "MoveResult",
    "RollbackResult",
    "get_default_action_log_path",
]
