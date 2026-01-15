"""
Unit tests for Embedding Cache module (Task 4B.3).

Tests the embedding cache functionality for storing and retrieving
email embeddings efficiently using numpy compressed format.
"""
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.cache.embedding_cache import EmbeddingCache, CacheStatistics
from src.models.corpus import Corpus, CorpusMetadata
from src.models.email import Email


def create_test_email(id: str, subject: str = "Test") -> Email:
    """Factory function to create test Email objects."""
    return Email(
        id=id,
        sender_email=f"sender_{id}@example.com",
        sender_name="Sender",
        sender_domain="example.com",
        subject=subject,
        body_text=f"Body for {id}",
        received_date=datetime(2024, 1, 15),
        has_attachments=False
    )


class TestEmbeddingCacheInit:
    """Test cases for EmbeddingCache initialization."""

    def test_init_creates_cache_file_path(self, tmp_path):
        """Test that cache is initialized with correct file path."""
        cache_path = tmp_path / "embeddings_cache.npz"
        cache = EmbeddingCache(cache_path=cache_path)
        assert cache.cache_path == cache_path

    def test_init_with_default_path(self, tmp_path):
        """Test initialization with default path from PathConfig."""
        with patch("src.utils.paths.PathConfig.get_output_dir") as mock_get_output_dir:
            mock_get_output_dir.return_value = tmp_path
            cache = EmbeddingCache()
            assert cache.cache_path == tmp_path / "embeddings_cache.npz"

    def test_init_creates_empty_cache(self, tmp_path):
        """Test that new cache starts empty."""
        cache_path = tmp_path / "embeddings_cache.npz"
        cache = EmbeddingCache(cache_path=cache_path)
        assert cache.size == 0

    def test_init_loads_existing_cache(self, tmp_path):
        """Test that existing cache file is loaded on init."""
        cache_path = tmp_path / "embeddings_cache.npz"

        # Create a cache file with data
        embeddings = np.array([[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]])
        email_ids = np.array(["email_1", "email_2"])
        np.savez_compressed(cache_path, embeddings=embeddings, email_ids=email_ids)

        # Load cache
        cache = EmbeddingCache(cache_path=cache_path)
        assert cache.size == 2


class TestEmbeddingCacheStorage:
    """Test cases for storing embeddings in cache."""

    @pytest.fixture
    def cache(self, tmp_path):
        """Create EmbeddingCache instance for tests."""
        cache_path = tmp_path / "test_cache.npz"
        return EmbeddingCache(cache_path=cache_path)

    def test_add_embeddings(self, cache):
        """Test adding embeddings to cache."""
        email_ids = ["email_1", "email_2", "email_3"]
        embeddings = np.random.rand(3, 384)

        cache.add(email_ids, embeddings)

        assert cache.size == 3
        assert cache.contains("email_1")
        assert cache.contains("email_2")
        assert cache.contains("email_3")

    def test_add_embeddings_preserves_shape(self, cache):
        """Test that embedding dimensions are preserved."""
        email_ids = ["email_1"]
        embeddings = np.random.rand(1, 1024)  # Different embedding size

        cache.add(email_ids, embeddings)

        retrieved = cache.get("email_1")
        assert retrieved.shape == (1024,)

    def test_add_embeddings_with_mismatch_raises_error(self, cache):
        """Test that mismatched email_ids and embeddings raises error."""
        email_ids = ["email_1", "email_2"]  # 2 IDs
        embeddings = np.random.rand(3, 384)  # 3 embeddings

        with pytest.raises(ValueError, match="Number of email IDs .* must match"):
            cache.add(email_ids, embeddings)

    def test_save_persists_to_file(self, cache, tmp_path):
        """Test that save() persists cache to disk."""
        email_ids = ["email_1"]
        embeddings = np.random.rand(1, 384)

        cache.add(email_ids, embeddings)
        cache.save()

        # Verify file exists and contains data
        assert cache.cache_path.exists()

        # Load and verify
        data = np.load(cache.cache_path, allow_pickle=True)
        assert len(data["email_ids"]) == 1
        assert data["embeddings"].shape[0] == 1


class TestEmbeddingCacheRetrieval:
    """Test cases for retrieving embeddings from cache."""

    @pytest.fixture
    def populated_cache(self, tmp_path):
        """Create EmbeddingCache with some data."""
        cache_path = tmp_path / "test_cache.npz"
        cache = EmbeddingCache(cache_path=cache_path)

        # Add some test embeddings
        email_ids = ["email_1", "email_2", "email_3"]
        embeddings = np.array([
            [0.1, 0.2, 0.3],
            [0.4, 0.5, 0.6],
            [0.7, 0.8, 0.9]
        ])
        cache.add(email_ids, embeddings)
        return cache

    def test_get_single_embedding(self, populated_cache):
        """Test retrieving a single embedding by ID."""
        embedding = populated_cache.get("email_1")
        assert embedding is not None
        assert embedding.shape == (3,)
        assert np.allclose(embedding, [0.1, 0.2, 0.3])

    def test_get_nonexistent_returns_none(self, populated_cache):
        """Test that getting non-existent ID returns None."""
        embedding = populated_cache.get("nonexistent_email")
        assert embedding is None

    def test_get_batch(self, populated_cache):
        """Test retrieving batch of embeddings."""
        email_ids = ["email_1", "email_3"]
        embeddings, missing = populated_cache.get_batch(email_ids)

        assert embeddings.shape == (2, 3)
        assert len(missing) == 0
        assert np.allclose(embeddings[0], [0.1, 0.2, 0.3])
        assert np.allclose(embeddings[1], [0.7, 0.8, 0.9])

    def test_get_batch_with_missing(self, populated_cache):
        """Test batch retrieval with some missing IDs."""
        email_ids = ["email_1", "missing_email", "email_3"]
        embeddings, missing = populated_cache.get_batch(email_ids)

        # Should only return 2 embeddings
        assert embeddings.shape == (2, 3)
        assert len(missing) == 1
        assert "missing_email" in missing

    def test_contains(self, populated_cache):
        """Test contains() method."""
        assert populated_cache.contains("email_1") is True
        assert populated_cache.contains("email_2") is True
        assert populated_cache.contains("nonexistent") is False


class TestEmbeddingCacheInvalidation:
    """Test cases for cache invalidation."""

    @pytest.fixture
    def populated_cache(self, tmp_path):
        """Create EmbeddingCache with some data."""
        cache_path = tmp_path / "test_cache.npz"
        cache = EmbeddingCache(cache_path=cache_path)

        email_ids = ["email_1", "email_2", "email_3"]
        embeddings = np.random.rand(3, 384)
        cache.add(email_ids, embeddings)
        return cache

    def test_invalidate_single_email(self, populated_cache):
        """Test invalidating (removing) a single email from cache."""
        populated_cache.invalidate("email_2")

        assert populated_cache.size == 2
        assert populated_cache.contains("email_1") is True
        assert populated_cache.contains("email_2") is False
        assert populated_cache.contains("email_3") is True

    def test_invalidate_nonexistent_is_noop(self, populated_cache):
        """Test that invalidating non-existent ID doesn't raise error."""
        original_size = populated_cache.size
        populated_cache.invalidate("nonexistent")
        assert populated_cache.size == original_size

    def test_invalidate_batch(self, populated_cache):
        """Test invalidating multiple emails at once."""
        populated_cache.invalidate_batch(["email_1", "email_3"])

        assert populated_cache.size == 1
        assert populated_cache.contains("email_2") is True

    def test_clear(self, populated_cache):
        """Test clearing entire cache."""
        populated_cache.clear()
        assert populated_cache.size == 0


class TestCacheStatistics:
    """Test cases for cache statistics tracking."""

    @pytest.fixture
    def cache(self, tmp_path):
        """Create EmbeddingCache instance."""
        cache_path = tmp_path / "test_cache.npz"
        return EmbeddingCache(cache_path=cache_path)

    def test_get_statistics_empty_cache(self, cache):
        """Test statistics for empty cache."""
        stats = cache.get_statistics()

        assert isinstance(stats, CacheStatistics)
        assert stats.total_entries == 0
        assert stats.hits == 0
        assert stats.misses == 0
        assert stats.hit_rate == 0.0

    def test_get_statistics_tracks_hits(self, cache):
        """Test that cache hits are tracked."""
        # Add embeddings
        cache.add(["email_1"], np.random.rand(1, 384))

        # Hit: retrieve existing
        cache.get("email_1")

        stats = cache.get_statistics()
        assert stats.hits == 1

    def test_get_statistics_tracks_misses(self, cache):
        """Test that cache misses are tracked."""
        # Miss: try to retrieve non-existent
        cache.get("nonexistent")

        stats = cache.get_statistics()
        assert stats.misses == 1

    def test_get_statistics_hit_rate(self, cache):
        """Test hit rate calculation."""
        cache.add(["email_1", "email_2"], np.random.rand(2, 384))

        # 2 hits
        cache.get("email_1")
        cache.get("email_2")
        # 2 misses
        cache.get("missing_1")
        cache.get("missing_2")

        stats = cache.get_statistics()
        assert stats.hits == 2
        assert stats.misses == 2
        assert stats.hit_rate == 0.5

    def test_statistics_includes_cache_size_bytes(self, cache):
        """Test that statistics includes approximate cache size."""
        cache.add(["email_1"], np.random.rand(1, 384))
        cache.save()

        stats = cache.get_statistics()
        assert stats.cache_size_bytes > 0


class TestCacheLoadSave:
    """Test cases for cache persistence."""

    def test_save_and_load_roundtrip(self, tmp_path):
        """Test that save/load preserves all data."""
        cache_path = tmp_path / "test_cache.npz"

        # Create cache and add data
        cache1 = EmbeddingCache(cache_path=cache_path)
        email_ids = ["email_1", "email_2"]
        embeddings = np.array([[0.1, 0.2], [0.3, 0.4]])
        cache1.add(email_ids, embeddings)
        cache1.save()

        # Load into new cache instance
        cache2 = EmbeddingCache(cache_path=cache_path)

        assert cache2.size == 2
        assert np.allclose(cache2.get("email_1"), [0.1, 0.2])
        assert np.allclose(cache2.get("email_2"), [0.3, 0.4])

    def test_load_handles_corrupted_file(self, tmp_path):
        """Test that loading corrupted file starts with empty cache."""
        cache_path = tmp_path / "corrupted.npz"

        # Write corrupted data
        cache_path.write_bytes(b"not valid npz data")

        # Should not raise, just start empty
        cache = EmbeddingCache(cache_path=cache_path)
        assert cache.size == 0

    def test_load_handles_missing_file(self, tmp_path):
        """Test loading when file doesn't exist."""
        cache_path = tmp_path / "nonexistent.npz"

        cache = EmbeddingCache(cache_path=cache_path)
        assert cache.size == 0


class TestCacheWithCorpus:
    """Test cases for cache integration with Corpus."""

    @pytest.fixture
    def cache(self, tmp_path):
        """Create EmbeddingCache instance."""
        return EmbeddingCache(cache_path=tmp_path / "test_cache.npz")

    @pytest.fixture
    def test_corpus(self):
        """Create a test corpus."""
        return Corpus(
            extraction_metadata=CorpusMetadata(
                extraction_date=datetime.now(),
                total_emails=3,
                source="test",
                user_email="user@example.com"
            ),
            emails=[
                create_test_email("email_1", "Subject 1"),
                create_test_email("email_2", "Subject 2"),
                create_test_email("email_3", "Subject 3"),
            ]
        )

    def test_get_cached_and_uncached_ids(self, cache, test_corpus):
        """Test separating cached and uncached email IDs."""
        # Add one email to cache
        cache.add(["email_1"], np.random.rand(1, 384))

        corpus_ids = [e.id for e in test_corpus.emails]
        cached, uncached = cache.partition_ids(corpus_ids)

        assert cached == ["email_1"]
        assert set(uncached) == {"email_2", "email_3"}

    def test_sync_with_corpus_removes_deleted_emails(self, cache, test_corpus):
        """Test that sync removes cached embeddings for deleted emails."""
        # Add more emails to cache than exist in corpus
        cache.add(
            ["email_1", "email_2", "email_3", "deleted_email"],
            np.random.rand(4, 384)
        )

        # Sync with corpus (which doesn't have "deleted_email")
        removed_count = cache.sync_with_corpus(test_corpus)

        assert removed_count == 1
        assert cache.size == 3
        assert cache.contains("deleted_email") is False
