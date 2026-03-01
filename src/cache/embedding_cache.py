"""
Embedding Cache module (Task 4B.3).

Provides efficient storage and retrieval of email embeddings using
numpy compressed format (.npz) for fast incremental analysis.

Work Item 3.1: Added cache versioning with metadata sidecar (.meta.json)
to detect model/config changes and auto-invalidate stale caches.

Work Item 4.2: Added optional sqlite-vec delegation via EmbeddingStore.
When a Database instance is provided, all operations delegate to
EmbeddingStore for persistent vector storage with cosine similarity search.
"""

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np

from src.utils.logger import get_logger

if TYPE_CHECKING:
    from src.models.corpus import Corpus
    from src.storage.database import Database

logger = get_logger(__name__)

# Default values matching SemanticAnalyzer defaults
DEFAULT_MODEL_NAME = "mixedbread-ai/mxbai-embed-large-v1"
DEFAULT_EMBEDDING_DIM = 1024
DEFAULT_MAX_TEXT_LENGTH = 1500


@dataclass
class CacheStatistics:
    """Statistics about embedding cache usage."""

    total_entries: int
    hits: int
    misses: int
    cache_size_bytes: int

    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate (0.0 to 1.0)."""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0


class EmbeddingCache:
    """
    Cache for email embeddings using numpy compressed format.

    Task 4B.3: Supports incremental analysis by caching embeddings
    that can be reused between analysis runs.

    Features:
    - Store embeddings in embeddings_cache.npz file
    - Map email ID -> embedding index
    - Load/save efficiently (numpy compressed)
    - Invalidation when email deleted
    - Cache statistics (hit rate)
    """

    def __init__(
        self,
        cache_path: Path | None = None,
        model_name: str = DEFAULT_MODEL_NAME,
        embedding_dim: int = DEFAULT_EMBEDDING_DIM,
        max_text_length: int = DEFAULT_MAX_TEXT_LENGTH,
        database: "Database | None" = None,
    ):
        """
        Initialize embedding cache.

        Args:
            cache_path: Path to cache file. If None, uses default from PathConfig.
            model_name: Name of the embedding model (used for cache versioning).
            embedding_dim: Dimensionality of embeddings (used for cache versioning).
            max_text_length: Max text length used for embedding generation (used for cache versioning).
            database: Optional Database instance. When provided, embeddings are stored
                in sqlite-vec via EmbeddingStore instead of .npz files.
        """
        if cache_path is None:
            from src.utils.paths import PathConfig

            cache_path = PathConfig.get_output_dir() / "embeddings_cache.npz"

        self.cache_path = Path(cache_path)

        # Cache versioning metadata
        self._model_name = model_name
        self._embedding_dim = embedding_dim
        self._max_text_length = max_text_length

        # Statistics tracking
        self._hits = 0
        self._misses = 0

        # sqlite-vec delegation (Work Item 4.2)
        self._store = None
        if database is not None:
            from src.storage.embedding_store import EmbeddingStore

            self._store = EmbeddingStore(database, embedding_dim=embedding_dim)
            logger.info("EmbeddingCache using sqlite-vec backend")
            # NPZ internal state not needed when delegating
            self._embeddings: np.ndarray | None = None
            self._email_ids: list[str] = []
            self._id_to_index: dict[str, int] = {}
        else:
            # Internal NPZ storage
            self._embeddings = None
            self._email_ids = []
            self._id_to_index = {}
            # Load existing cache if available (with metadata validation)
            self._load()

    @property
    def size(self) -> int:
        """Number of cached embeddings."""
        if self._store is not None:
            return self._store.count()
        return len(self._email_ids)

    def add(self, email_ids: list[str], embeddings: np.ndarray) -> None:
        """
        Add embeddings to cache.

        Args:
            email_ids: List of email IDs corresponding to embeddings
            embeddings: 2D numpy array of shape (n_emails, embedding_dim)

        Raises:
            ValueError: If number of IDs doesn't match number of embeddings
        """
        if len(email_ids) != embeddings.shape[0]:
            raise ValueError(
                f"Number of email IDs ({len(email_ids)}) must match "
                f"number of embeddings ({embeddings.shape[0]})"
            )

        if self._store is not None:
            self._store.add_batch(email_ids, embeddings)
            logger.debug(f"Added {len(email_ids)} embeddings to store (total: {self.size})")
            return

        if self._embeddings is None:
            # First addition - initialize storage
            self._embeddings = embeddings.copy()
            self._email_ids = list(email_ids)
        else:
            # Append to existing
            self._embeddings = np.vstack([self._embeddings, embeddings])
            self._email_ids.extend(email_ids)

        # Rebuild index
        self._rebuild_index()

        logger.debug(f"Added {len(email_ids)} embeddings to cache (total: {self.size})")

    def get(self, email_id: str) -> np.ndarray | None:
        """
        Get embedding for a single email ID.

        Args:
            email_id: Email ID to look up

        Returns:
            Embedding vector or None if not found
        """
        if self._store is not None:
            result = self._store.get(email_id)
            if result is not None:
                self._hits += 1
            else:
                self._misses += 1
            return result

        if email_id in self._id_to_index and self._embeddings is not None:
            self._hits += 1
            idx = self._id_to_index[email_id]
            return self._embeddings[idx].copy()  # type: ignore[no-any-return]
        self._misses += 1
        return None

    def get_batch(self, email_ids: list[str]) -> tuple[np.ndarray, list[str]]:
        """
        Get embeddings for multiple email IDs.

        Args:
            email_ids: List of email IDs to look up

        Returns:
            Tuple of (embeddings array, list of missing IDs)
        """
        if self._store is not None:
            result_embs, missing = self._store.get_batch(email_ids)
            self._hits += len(email_ids) - len(missing)
            self._misses += len(missing)
            return result_embs, missing

        found_embeddings = []
        missing_ids = []

        for email_id in email_ids:
            if email_id in self._id_to_index and self._embeddings is not None:
                self._hits += 1
                idx = self._id_to_index[email_id]
                found_embeddings.append(self._embeddings[idx])
            else:
                self._misses += 1
                missing_ids.append(email_id)

        if found_embeddings:
            embeddings_array = np.array(found_embeddings)
        else:
            embeddings_array = np.array([]).reshape(0, 0)

        return embeddings_array, missing_ids

    def contains(self, email_id: str) -> bool:
        """Check if email ID is in cache."""
        if self._store is not None:
            return self._store.contains(email_id)
        return email_id in self._id_to_index

    def invalidate(self, email_id: str) -> None:
        """
        Remove a single email from cache.

        Args:
            email_id: Email ID to remove
        """
        if self._store is not None:
            self._store.delete(email_id)
            logger.debug(f"Invalidated embedding for {email_id}")
            return

        if email_id not in self._id_to_index:
            return

        idx = self._id_to_index[email_id]

        # Remove from arrays
        if self._embeddings is not None:
            self._embeddings = np.delete(self._embeddings, idx, axis=0)
        self._email_ids.pop(idx)

        # Rebuild index
        self._rebuild_index()

        logger.debug(f"Invalidated embedding for {email_id}")

    def invalidate_batch(self, email_ids: list[str]) -> None:
        """
        Remove multiple emails from cache.

        Args:
            email_ids: List of email IDs to remove
        """
        if self._store is not None:
            for email_id in email_ids:
                self._store.delete(email_id)
            logger.debug(f"Invalidated {len(email_ids)} embeddings")
            return

        # Get indices to remove (must be sorted in reverse to remove from end first)
        indices_to_remove = []
        for email_id in email_ids:
            if email_id in self._id_to_index:
                indices_to_remove.append(self._id_to_index[email_id])

        if not indices_to_remove:
            return

        # Remove from arrays (from highest index to lowest)
        for idx in sorted(indices_to_remove, reverse=True):
            if self._embeddings is not None:
                self._embeddings = np.delete(self._embeddings, idx, axis=0)
            self._email_ids.pop(idx)

        # Rebuild index
        self._rebuild_index()

        logger.debug(f"Invalidated {len(indices_to_remove)} embeddings")

    def clear(self) -> None:
        """Clear all cached embeddings."""
        if self._store is not None:
            self._store.clear()
            self._hits = 0
            self._misses = 0
            logger.debug("Cleared embedding cache (sqlite-vec)")
            return

        self._embeddings = None
        self._email_ids = []
        self._id_to_index = {}
        self._hits = 0
        self._misses = 0

        logger.debug("Cleared embedding cache")

    def partition_ids(self, email_ids: list[str]) -> tuple[list[str], list[str]]:
        """
        Partition email IDs into cached and uncached.

        Args:
            email_ids: List of email IDs to check

        Returns:
            Tuple of (cached_ids, uncached_ids)
        """
        cached = []
        uncached = []

        for email_id in email_ids:
            if self.contains(email_id):
                cached.append(email_id)
            else:
                uncached.append(email_id)

        return cached, uncached

    def sync_with_corpus(self, corpus: "Corpus") -> int:
        """
        Remove cached embeddings for emails no longer in corpus.

        Args:
            corpus: Current corpus to sync with

        Returns:
            Number of embeddings removed
        """
        corpus_ids = {email.id for email in corpus.emails}

        if self._store is not None:
            removed = self._store.sync_with_ids(corpus_ids)
            if removed > 0:
                logger.info(f"Removed {removed} stale embeddings from cache")
            return removed

        ids_to_remove = [email_id for email_id in self._email_ids if email_id not in corpus_ids]

        if ids_to_remove:
            self.invalidate_batch(ids_to_remove)
            logger.info(f"Removed {len(ids_to_remove)} stale embeddings from cache")

        return len(ids_to_remove)

    @property
    def metadata_path(self) -> Path:
        """Path to the metadata sidecar JSON file."""
        return self.cache_path.with_suffix(".meta.json")

    def _build_metadata(self) -> dict[str, Any]:
        """Build metadata dict for the current configuration."""
        return {
            "model_name": self._model_name,
            "embedding_dim": self._embedding_dim,
            "max_text_length": self._max_text_length,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "email_ids": list(self._email_ids),
        }

    def _save_metadata(self) -> None:
        """Write metadata sidecar JSON alongside the .npz file."""
        self.metadata_path.parent.mkdir(parents=True, exist_ok=True)
        metadata = self._build_metadata()
        self.metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        logger.debug(f"Saved cache metadata to {self.metadata_path}")

    def _load_metadata(self) -> dict[str, Any] | None:
        """
        Load metadata sidecar if it exists.

        Returns:
            Metadata dict, or None if sidecar is missing or unreadable.
        """
        if not self.metadata_path.exists():
            return None
        try:
            result: dict[str, Any] = json.loads(self.metadata_path.read_text(encoding="utf-8"))
            return result
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to read cache metadata: {e}")
            return None

    def _validate_metadata(self, metadata: dict[str, Any]) -> bool:
        """
        Validate stored metadata against current configuration.

        Returns:
            True if metadata matches current config, False if cache should
            be invalidated.
        """
        stored_model = metadata.get("model_name")
        stored_dim = metadata.get("embedding_dim")
        stored_text_len = metadata.get("max_text_length")

        if stored_model != self._model_name:
            logger.warning(
                f"Embedding model changed: cached='{stored_model}' "
                f"current='{self._model_name}'. Invalidating cache."
            )
            return False

        if stored_dim != self._embedding_dim:
            logger.warning(
                f"Embedding dimension changed: cached={stored_dim} "
                f"current={self._embedding_dim}. Invalidating cache."
            )
            return False

        if stored_text_len != self._max_text_length:
            logger.warning(
                f"Max text length changed: cached={stored_text_len} "
                f"current={self._max_text_length}. Invalidating cache."
            )
            return False

        return True

    def _delete_cache_files(self) -> None:
        """Delete both .npz and .meta.json files from disk."""
        if self.cache_path.exists():
            self.cache_path.unlink()
            logger.debug(f"Deleted cache file: {self.cache_path}")
        if self.metadata_path.exists():
            self.metadata_path.unlink()
            logger.debug(f"Deleted metadata file: {self.metadata_path}")

    def save(self) -> None:
        """Save cache and metadata sidecar to disk.

        When using sqlite-vec backend, this is a no-op since data is
        persisted on every write. For NPZ backend, saves to disk.
        """
        if self._store is not None:
            # sqlite-vec backend auto-persists; nothing to do
            logger.debug("sqlite-vec backend: save is a no-op (data already persisted)")
            return

        if self._embeddings is None or len(self._email_ids) == 0:
            logger.debug("Nothing to save - cache is empty")
            return

        # Ensure parent directory exists
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)

        # Save embeddings only (no pickle-requiring object arrays)
        np.savez_compressed(
            self.cache_path,
            embeddings=self._embeddings,
        )

        # Save metadata sidecar (includes email IDs as JSON-safe list)
        self._save_metadata()

        logger.debug(f"Saved {self.size} embeddings to {self.cache_path}")

    def get_statistics(self) -> CacheStatistics:
        """
        Get cache statistics.

        Returns:
            CacheStatistics with hit/miss counts and size info
        """
        cache_size = 0
        if self.cache_path.exists():
            cache_size = self.cache_path.stat().st_size

        return CacheStatistics(
            total_entries=self.size,
            hits=self._hits,
            misses=self._misses,
            cache_size_bytes=cache_size,
        )

    def _load(self) -> None:
        """Load cache from disk if it exists, validating metadata first."""
        if not self.cache_path.exists():
            logger.debug(f"No cache file at {self.cache_path}")
            return

        # Check metadata sidecar before loading embeddings
        metadata = self._load_metadata()
        if metadata is None:
            # Old cache without metadata sidecar - treat as invalid
            logger.warning(
                "Cache file exists without metadata sidecar. Starting fresh (old cache format)."
            )
            self._delete_cache_files()
            return

        if not self._validate_metadata(metadata):
            # Metadata mismatch - invalidate
            self._delete_cache_files()
            return

        try:
            data = np.load(self.cache_path, allow_pickle=False)
            self._embeddings = data["embeddings"]
            # Email IDs now stored in metadata sidecar (no pickle needed)
            self._email_ids = list(metadata.get("email_ids", []))
            self._rebuild_index()

            logger.info(f"Loaded {self.size} embeddings from cache")

        except Exception as e:
            logger.warning(f"Failed to load cache from {self.cache_path}: {e}")
            # Start fresh
            self._delete_cache_files()
            self._embeddings = None
            self._email_ids = []
            self._id_to_index = {}

    def _rebuild_index(self) -> None:
        """Rebuild the email ID to index mapping."""
        self._id_to_index = {email_id: idx for idx, email_id in enumerate(self._email_ids)}
