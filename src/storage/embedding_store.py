"""
EmbeddingStore: vector storage and cosine similarity search using sqlite-vec.

Provides CRUD operations for email embeddings stored in a sqlite-vec
virtual table, with cosine distance-based similarity search.

Phase 4, Work Item 4.2.
"""

import logging

import numpy as np

from src.exceptions import StorageError
from src.storage.database import Database

logger = logging.getLogger(__name__)

# Default embedding dimension matching the project's default model
DEFAULT_EMBEDDING_DIM = 1024


def _load_sqlite_vec(db: Database) -> None:
    """
    Load the sqlite-vec extension into the database connection.

    This must be called once per connection before using vec0 virtual tables.

    Args:
        db: Database instance whose underlying connection will load the extension.

    Raises:
        StorageError: If sqlite-vec cannot be loaded.
    """
    try:
        import sqlite_vec
    except ImportError as e:
        raise StorageError(
            "sqlite-vec is not installed. Install with: pip install sqlite-vec",
            recovery_hint="Run 'pip install sqlite-vec' to install the required extension.",
            context={"error": str(e)},
        ) from e

    try:
        # Access the raw connection for enable_load_extension
        conn = db._conn  # noqa: SLF001 — intentional access to internal connection
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
    except Exception as e:
        raise StorageError(
            f"Failed to load sqlite-vec extension: {e}",
            context={"error": str(e)},
        ) from e


class EmbeddingStore:
    """
    Vector storage and cosine similarity search for email embeddings.

    Uses sqlite-vec's vec0 virtual table with cosine distance metric.
    Embeddings are stored as packed float32 arrays keyed by email_id (TEXT).

    Provides:
    - add() / add_batch() for storing embeddings
    - get() / get_batch() for retrieval
    - search_similar() for cosine similarity nearest-neighbor search
    - delete() / sync_with_ids() for cleanup
    - count() / contains() for inspection

    Usage:
        store = EmbeddingStore(database, embedding_dim=1024)
        store.add("email_123", embedding_array)
        results = store.search_similar(query_embedding, k=5)
    """

    def __init__(self, database: Database, embedding_dim: int = DEFAULT_EMBEDDING_DIM) -> None:
        """
        Initialize the EmbeddingStore and create the virtual table.

        Args:
            database: An open Database instance.
            embedding_dim: Dimensionality of embeddings (must match model output).
        """
        self._db = database
        self._embedding_dim = embedding_dim

        _load_sqlite_vec(database)
        self._create_table()

        logger.debug(
            "EmbeddingStore initialized (dim=%d) on %s",
            embedding_dim,
            getattr(database, "_db_path", "unknown"),
        )

    @property
    def embedding_dim(self) -> int:
        """Return the configured embedding dimension."""
        return self._embedding_dim

    def _create_table(self) -> None:
        """Create the vec0 virtual table if it doesn't exist."""
        sql = (
            f"CREATE VIRTUAL TABLE IF NOT EXISTS vec_embeddings "
            f"USING vec0(email_id TEXT PRIMARY KEY, "
            f"embedding float[{self._embedding_dim}] distance_metric=cosine)"
        )
        try:
            self._db._conn.execute(sql)  # noqa: SLF001
        except Exception as e:
            raise StorageError(
                f"Failed to create vec_embeddings virtual table: {e}",
                context={"embedding_dim": self._embedding_dim},
            ) from e

    def _to_bytes(self, embedding: np.ndarray) -> bytes:
        """Convert a numpy embedding to packed float32 bytes for sqlite-vec."""
        return embedding.astype(np.float32).tobytes()

    def _from_bytes(self, data: bytes) -> np.ndarray:
        """Convert packed float32 bytes back to a numpy array."""
        return np.frombuffer(data, dtype=np.float32).copy()

    def _validate_dim(self, embedding: np.ndarray, context: str = "embedding") -> None:
        """Validate that the embedding has the expected dimension."""
        if embedding.shape[-1] != self._embedding_dim:
            raise ValueError(
                f"Dimension mismatch: {context} has {embedding.shape[-1]} dimensions, "
                f"expected {self._embedding_dim}"
            )

    def add(self, email_id: str, embedding: np.ndarray) -> None:
        """
        Add or replace a single embedding.

        Args:
            email_id: Unique email identifier.
            embedding: 1-D numpy array of shape (embedding_dim,).

        Raises:
            ValueError: If embedding dimension doesn't match.
        """
        self._validate_dim(embedding, "embedding")
        blob = self._to_bytes(embedding)

        # vec0 does not support INSERT OR REPLACE, so delete-then-insert for upsert
        try:
            conn = self._db._conn  # noqa: SLF001
            conn.execute("DELETE FROM vec_embeddings WHERE email_id = ?", (email_id,))
            conn.execute(
                "INSERT INTO vec_embeddings(email_id, embedding) VALUES (?, ?)",
                (email_id, blob),
            )
        except Exception as e:
            raise StorageError(
                f"Failed to add embedding for {email_id}: {e}",
                context={"email_id": email_id},
            ) from e

    def add_batch(self, email_ids: list[str], embeddings: np.ndarray) -> None:
        """
        Add or replace multiple embeddings in a single transaction.

        Args:
            email_ids: List of email IDs.
            embeddings: 2-D numpy array of shape (n, embedding_dim).

        Raises:
            ValueError: If lengths don't match or dimension is wrong.
        """
        if len(email_ids) == 0:
            return

        if len(email_ids) != embeddings.shape[0]:
            raise ValueError(
                f"Number of email IDs ({len(email_ids)}) must match "
                f"number of embeddings ({embeddings.shape[0]})"
            )

        if embeddings.ndim == 2:
            self._validate_dim(embeddings[0], "embeddings")

        insert_params = [(eid, self._to_bytes(embeddings[i])) for i, eid in enumerate(email_ids)]
        delete_params = [(eid,) for eid in email_ids]

        try:
            conn = self._db._conn  # noqa: SLF001
            conn.execute("BEGIN")
            try:
                # vec0 doesn't support INSERT OR REPLACE — delete then insert
                conn.executemany(
                    "DELETE FROM vec_embeddings WHERE email_id = ?",
                    delete_params,
                )
                conn.executemany(
                    "INSERT INTO vec_embeddings(email_id, embedding) VALUES (?, ?)",
                    insert_params,
                )
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise
        except StorageError:
            raise
        except Exception as e:
            raise StorageError(
                f"Failed to add batch of {len(email_ids)} embeddings: {e}",
                context={"count": len(email_ids)},
            ) from e

        logger.debug("Added batch of %d embeddings", len(email_ids))

    def get(self, email_id: str) -> np.ndarray | None:
        """
        Retrieve the embedding for a single email ID.

        Args:
            email_id: Email ID to look up.

        Returns:
            1-D numpy array, or None if not found.
        """
        try:
            cursor = self._db._conn.execute(  # noqa: SLF001
                "SELECT embedding FROM vec_embeddings WHERE email_id = ?",
                (email_id,),
            )
            row = cursor.fetchone()
        except Exception as e:
            raise StorageError(
                f"Failed to get embedding for {email_id}: {e}",
                context={"email_id": email_id},
            ) from e

        if row is None:
            return None

        return self._from_bytes(row[0])

    def get_batch(self, email_ids: list[str]) -> tuple[np.ndarray, list[str]]:
        """
        Retrieve embeddings for multiple email IDs.

        Args:
            email_ids: List of email IDs to look up.

        Returns:
            Tuple of (found_embeddings, missing_ids). found_embeddings has
            shape (n_found, embedding_dim) or (0, 0) if none found.
        """
        if not email_ids:
            return np.array([]).reshape(0, 0), []

        found = []
        missing = []

        for email_id in email_ids:
            embedding = self.get(email_id)
            if embedding is not None:
                found.append(embedding)
            else:
                missing.append(email_id)

        if found:
            return np.array(found), missing
        return np.array([]).reshape(0, 0), missing

    def search_similar(self, query_embedding: np.ndarray, k: int = 5) -> list[tuple[str, float]]:
        """
        Find the k nearest embeddings by cosine distance.

        Args:
            query_embedding: 1-D numpy query vector.
            k: Maximum number of results to return.

        Returns:
            List of (email_id, cosine_distance) tuples, sorted by distance
            ascending (most similar first). Cosine distance is 0.0 for
            identical vectors, 2.0 for opposite vectors.

        Raises:
            ValueError: If query dimension doesn't match.
        """
        self._validate_dim(query_embedding, "query_embedding")

        blob = self._to_bytes(query_embedding)

        try:
            cursor = self._db._conn.execute(  # noqa: SLF001
                """
                SELECT email_id, distance
                FROM vec_embeddings
                WHERE embedding MATCH ?
                ORDER BY distance
                LIMIT ?
                """,
                (blob, k),
            )
            rows = cursor.fetchall()
        except Exception as e:
            # If table is empty, sqlite-vec may return empty result or raise
            if "no rows" in str(e).lower():
                return []
            raise StorageError(
                f"Similarity search failed: {e}",
                context={"k": k},
            ) from e

        return [(row[0], float(row[1])) for row in rows]

    def delete(self, email_id: str) -> None:
        """
        Delete a single embedding by email ID.

        Does nothing if the ID doesn't exist.

        Args:
            email_id: Email ID to remove.
        """
        try:
            self._db._conn.execute(  # noqa: SLF001
                "DELETE FROM vec_embeddings WHERE email_id = ?",
                (email_id,),
            )
        except Exception as e:
            raise StorageError(
                f"Failed to delete embedding for {email_id}: {e}",
                context={"email_id": email_id},
            ) from e

    def sync_with_ids(self, valid_ids: set[str]) -> int:
        """
        Remove embeddings whose email_id is not in the valid set.

        Args:
            valid_ids: Set of email IDs that should be kept.

        Returns:
            Number of embeddings removed.
        """
        # Get all stored IDs
        try:
            cursor = self._db._conn.execute(  # noqa: SLF001
                "SELECT email_id FROM vec_embeddings"
            )
            all_ids = {row[0] for row in cursor.fetchall()}
        except Exception as e:
            raise StorageError(
                f"Failed to list embedding IDs: {e}",
            ) from e

        stale_ids = all_ids - valid_ids
        if not stale_ids:
            return 0

        try:
            conn = self._db._conn  # noqa: SLF001
            conn.execute("BEGIN")
            try:
                conn.executemany(
                    "DELETE FROM vec_embeddings WHERE email_id = ?",
                    [(eid,) for eid in stale_ids],
                )
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise
        except StorageError:
            raise
        except Exception as e:
            raise StorageError(
                f"Failed to sync embeddings: {e}",
                context={"stale_count": len(stale_ids)},
            ) from e

        logger.info("Removed %d stale embeddings", len(stale_ids))
        return len(stale_ids)

    def count(self) -> int:
        """
        Count the total number of stored embeddings.

        Returns:
            Number of embeddings in the store.
        """
        try:
            cursor = self._db._conn.execute(  # noqa: SLF001
                "SELECT COUNT(*) FROM vec_embeddings"
            )
            return cursor.fetchone()[0]
        except Exception as e:
            raise StorageError(
                f"Failed to count embeddings: {e}",
            ) from e

    def contains(self, email_id: str) -> bool:
        """
        Check whether an embedding exists for the given email ID.

        Args:
            email_id: Email ID to check.

        Returns:
            True if an embedding is stored, False otherwise.
        """
        try:
            cursor = self._db._conn.execute(  # noqa: SLF001
                "SELECT 1 FROM vec_embeddings WHERE email_id = ? LIMIT 1",
                (email_id,),
            )
            return cursor.fetchone() is not None
        except Exception as e:
            raise StorageError(
                f"Failed to check embedding for {email_id}: {e}",
                context={"email_id": email_id},
            ) from e

    def clear(self) -> None:
        """Delete all embeddings from the store."""
        try:
            self._db._conn.execute(  # noqa: SLF001
                "DELETE FROM vec_embeddings"
            )
        except Exception as e:
            raise StorageError(
                f"Failed to clear embeddings: {e}",
            ) from e

        logger.debug("Cleared all embeddings from store")
