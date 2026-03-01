"""
Storage package for SQLite database access.

Provides the Database connection manager and store classes for
persisting emails, classifications, corrections, and audit logs.

Phase 3: SQLite Core.
"""

from src.storage.database import Database
from src.storage.email_store import EmailStore

__all__ = ["Database", "EmailStore"]
