"""
Embedding Cache module (Task 4B.3).

Provides efficient storage and retrieval of email embeddings using
numpy compressed format (.npz) for fast incremental analysis.
"""
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from src.utils.logger import get_logger

if TYPE_CHECKING:
    from src.models.corpus import Corpus

logger = get_logger(__name__)


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

    def __init__(self, cache_path: Path | None = None):
        """
        Initialize embedding cache.

        Args:
            cache_path: Path to cache file. If None, uses default from PathConfig.
        """
        if cache_path is None:
            from src.utils.paths import PathConfig
            cache_path = PathConfig.get_output_dir() / "embeddings_cache.npz"

        self.cache_path = Path(cache_path)

        # Internal storage
        self._embeddings: np.ndarray | None = None
        self._email_ids: list[str] = []
        self._id_to_index: dict[str, int] = {}

        # Statistics tracking
        self._hits = 0
        self._misses = 0

        # Load existing cache if available
        self._load()

    @property
    def size(self) -> int:
        """Number of cached embeddings."""
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
        if email_id in self._id_to_index:
            self._hits += 1
            idx = self._id_to_index[email_id]
            return self._embeddings[idx].copy()
        else:
            self._misses += 1
            return None

    def get_batch(
        self, email_ids: list[str]
    ) -> tuple[np.ndarray, list[str]]:
        """
        Get embeddings for multiple email IDs.

        Args:
            email_ids: List of email IDs to look up

        Returns:
            Tuple of (embeddings array, list of missing IDs)
        """
        found_embeddings = []
        missing_ids = []

        for email_id in email_ids:
            if email_id in self._id_to_index:
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
        return email_id in self._id_to_index

    def invalidate(self, email_id: str) -> None:
        """
        Remove a single email from cache.

        Args:
            email_id: Email ID to remove
        """
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
        self._embeddings = None
        self._email_ids = []
        self._id_to_index = {}
        self._hits = 0
        self._misses = 0

        logger.debug("Cleared embedding cache")

    def partition_ids(
        self, email_ids: list[str]
    ) -> tuple[list[str], list[str]]:
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
            if email_id in self._id_to_index:
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
        ids_to_remove = [
            email_id for email_id in self._email_ids
            if email_id not in corpus_ids
        ]

        if ids_to_remove:
            self.invalidate_batch(ids_to_remove)
            logger.info(f"Removed {len(ids_to_remove)} stale embeddings from cache")

        return len(ids_to_remove)

    def save(self) -> None:
        """Save cache to disk."""
        if self._embeddings is None or len(self._email_ids) == 0:
            logger.debug("Nothing to save - cache is empty")
            return

        # Ensure parent directory exists
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)

        # Save using numpy compressed format
        np.savez_compressed(
            self.cache_path,
            embeddings=self._embeddings,
            email_ids=np.array(self._email_ids, dtype=object)
        )

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
            cache_size_bytes=cache_size
        )

    def _load(self) -> None:
        """Load cache from disk if it exists."""
        if not self.cache_path.exists():
            logger.debug(f"No cache file at {self.cache_path}")
            return

        try:
            data = np.load(self.cache_path, allow_pickle=True)
            self._embeddings = data["embeddings"]
            self._email_ids = list(data["email_ids"])
            self._rebuild_index()

            logger.info(f"Loaded {self.size} embeddings from cache")

        except Exception as e:
            logger.warning(f"Failed to load cache from {self.cache_path}: {e}")
            # Start fresh
            self._embeddings = None
            self._email_ids = []
            self._id_to_index = {}

    def _rebuild_index(self) -> None:
        """Rebuild the email ID to index mapping."""
        self._id_to_index = {
            email_id: idx for idx, email_id in enumerate(self._email_ids)
        }
