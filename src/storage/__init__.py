"""
Storage package for SQLite database access.

Provides the Database connection manager and store classes for
persisting emails, classifications, corrections, and audit logs.

Phase 3: SQLite Core.
Phase 4: sqlite-vec embedding storage.
"""

from src.storage.database import Database
from src.storage.email_store import EmailStore
from src.storage.embedding_store import EmbeddingStore
from src.storage.migration import JsonToSqliteMigrator, MigrationResult

__all__ = [
    "Database",
    "EmailStore",
    "EmbeddingStore",
    "JsonToSqliteMigrator",
    "MigrationResult",
]
