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

__all__ = [
    "ActionLog",
    "ActionLogger",
    "ActionRecord",
    "ActionType",
    "RollbackResult",
    "get_default_action_log_path",
]
