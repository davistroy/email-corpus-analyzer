"""
Unit tests for Embedding Cache module (Task 4B.3).

Tests the embedding cache functionality for storing and retrieving
email embeddings efficiently using numpy compressed format.

Work Item 3.1: Added tests for cache versioning / metadata sidecar.
"""
import json
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

from src.cache.embedding_cache import (
    DEFAULT_EMBEDDING_DIM,
    DEFAULT_MAX_TEXT_LENGTH,
    DEFAULT_MODEL_NAME,
    CacheStatistics,
    EmbeddingCache,
)
from src.models.corpus import Corpus, CorpusMetadata
from src.models.email import Email


def create_test_email(email_id: str, subject: str = "Test") -> Email:
    """Factory function to create test Email objects."""
    return Email(
        id=email_id,
        sender_email=f"sender_{email_id}@example.com",
        sender_name="Sender",
        sender_domain="example.com",
        subject=subject,
        body_text=f"Body for {email_id}",
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
        """Test that existing cache file with valid metadata is loaded on init."""
        cache_path = tmp_path / "embeddings_cache.npz"
        meta_path = cache_path.with_suffix(".meta.json")

        # Create a cache file with embeddings only (no pickle-requiring arrays)
        embeddings = np.array([[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]])
        np.savez_compressed(cache_path, embeddings=embeddings)

        # Create matching metadata sidecar (includes email_ids)
        metadata = {
            "model_name": DEFAULT_MODEL_NAME,
            "embedding_dim": DEFAULT_EMBEDDING_DIM,
            "max_text_length": DEFAULT_MAX_TEXT_LENGTH,
            "created_at": "2024-01-15T00:00:00+00:00",
            "email_ids": ["email_1", "email_2"],
        }
        meta_path.write_text(json.dumps(metadata), encoding="utf-8")

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

        # Load and verify embeddings from .npz (no pickle needed)
        data = np.load(cache.cache_path, allow_pickle=False)
        assert data["embeddings"].shape[0] == 1

        # Email IDs are now in the metadata sidecar
        meta_path = cache.cache_path.with_suffix(".meta.json")
        assert meta_path.exists()
        metadata = json.loads(meta_path.read_text(encoding="utf-8"))
        assert len(metadata["email_ids"]) == 1


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
        meta_path = cache_path.with_suffix(".meta.json")

        # Write corrupted npz data
        cache_path.write_bytes(b"not valid npz data")

        # Write valid metadata so we reach the npz load attempt
        metadata = {
            "model_name": DEFAULT_MODEL_NAME,
            "embedding_dim": DEFAULT_EMBEDDING_DIM,
            "max_text_length": DEFAULT_MAX_TEXT_LENGTH,
            "created_at": "2024-01-15T00:00:00+00:00",
        }
        meta_path.write_text(json.dumps(metadata), encoding="utf-8")

        # Should not raise, just start empty and clean up corrupt files
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


def _write_npz_with_metadata(
    cache_path: Path,
    embeddings: np.ndarray,
    email_ids: list[str],
    model_name: str = DEFAULT_MODEL_NAME,
    embedding_dim: int = DEFAULT_EMBEDDING_DIM,
    max_text_length: int = DEFAULT_MAX_TEXT_LENGTH,
) -> None:
    """Helper to write a cache .npz + .meta.json pair on disk."""
    np.savez_compressed(
        cache_path,
        embeddings=embeddings,
    )
    meta_path = cache_path.with_suffix(".meta.json")
    metadata = {
        "model_name": model_name,
        "embedding_dim": embedding_dim,
        "max_text_length": max_text_length,
        "created_at": "2024-01-15T00:00:00+00:00",
        "email_ids": list(email_ids),
    }
    meta_path.write_text(json.dumps(metadata), encoding="utf-8")


class TestCacheVersioning:
    """Test cases for cache versioning via metadata sidecar (Work Item 3.1)."""

    # ---- Normal loading with matching metadata ----

    def test_matching_metadata_loads_cache(self, tmp_path):
        """Cache with matching metadata should load normally."""
        cache_path = tmp_path / "test_cache.npz"
        embeddings = np.array([[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]])

        _write_npz_with_metadata(cache_path, embeddings, ["e1", "e2"])

        cache = EmbeddingCache(cache_path=cache_path)
        assert cache.size == 2
        assert np.allclose(cache.get("e1"), [0.1, 0.2, 0.3])

    def test_save_creates_metadata_sidecar(self, tmp_path):
        """save() should write a .meta.json sidecar alongside .npz."""
        cache_path = tmp_path / "test_cache.npz"
        meta_path = cache_path.with_suffix(".meta.json")

        cache = EmbeddingCache(cache_path=cache_path, model_name="my-model",
                               embedding_dim=768, max_text_length=2000)
        cache.add(["e1"], np.random.rand(1, 768))
        cache.save()

        assert meta_path.exists()
        metadata = json.loads(meta_path.read_text(encoding="utf-8"))
        assert metadata["model_name"] == "my-model"
        assert metadata["embedding_dim"] == 768
        assert metadata["max_text_length"] == 2000
        assert "created_at" in metadata

    def test_metadata_path_property(self, tmp_path):
        """metadata_path should return .meta.json derived from .npz path."""
        cache_path = tmp_path / "embeddings_cache.npz"
        cache = EmbeddingCache(cache_path=cache_path)
        assert cache.metadata_path == tmp_path / "embeddings_cache.meta.json"

    def test_roundtrip_with_metadata(self, tmp_path):
        """Full save/load roundtrip should preserve data when metadata matches."""
        cache_path = tmp_path / "rt_cache.npz"
        model = "test-model/v1"
        dim = 256

        cache1 = EmbeddingCache(cache_path=cache_path, model_name=model,
                                embedding_dim=dim, max_text_length=1000)
        cache1.add(["a", "b"], np.array([[1.0, 2.0], [3.0, 4.0]]))
        cache1.save()

        cache2 = EmbeddingCache(cache_path=cache_path, model_name=model,
                                embedding_dim=dim, max_text_length=1000)
        assert cache2.size == 2
        assert np.allclose(cache2.get("a"), [1.0, 2.0])
        assert np.allclose(cache2.get("b"), [3.0, 4.0])

    # ---- Model name mismatch invalidation ----

    def test_model_name_mismatch_invalidates_cache(self, tmp_path):
        """Changing model_name should invalidate the cache."""
        cache_path = tmp_path / "test_cache.npz"
        meta_path = cache_path.with_suffix(".meta.json")
        embeddings = np.random.rand(3, 384)

        _write_npz_with_metadata(
            cache_path, embeddings, ["e1", "e2", "e3"],
            model_name="old-model/v1"
        )

        # Load with different model name
        cache = EmbeddingCache(
            cache_path=cache_path,
            model_name="new-model/v2"
        )

        assert cache.size == 0
        assert not cache_path.exists()
        assert not meta_path.exists()

    # ---- Embedding dimension mismatch invalidation ----

    def test_embedding_dim_mismatch_invalidates_cache(self, tmp_path):
        """Changing embedding_dim should invalidate the cache."""
        cache_path = tmp_path / "test_cache.npz"
        meta_path = cache_path.with_suffix(".meta.json")
        embeddings = np.random.rand(2, 384)

        _write_npz_with_metadata(
            cache_path, embeddings, ["e1", "e2"],
            embedding_dim=384
        )

        # Load with different dimension
        cache = EmbeddingCache(
            cache_path=cache_path,
            embedding_dim=1024
        )

        assert cache.size == 0
        assert not cache_path.exists()
        assert not meta_path.exists()

    # ---- Max text length mismatch invalidation ----

    def test_max_text_length_mismatch_invalidates_cache(self, tmp_path):
        """Changing max_text_length should invalidate the cache."""
        cache_path = tmp_path / "test_cache.npz"
        meta_path = cache_path.with_suffix(".meta.json")
        embeddings = np.random.rand(2, 384)

        _write_npz_with_metadata(
            cache_path, embeddings, ["e1", "e2"],
            max_text_length=1500
        )

        # Load with different text length
        cache = EmbeddingCache(
            cache_path=cache_path,
            max_text_length=3000
        )

        assert cache.size == 0
        assert not cache_path.exists()
        assert not meta_path.exists()

    # ---- Old cache without metadata sidecar ----

    def test_old_cache_without_metadata_starts_fresh(self, tmp_path):
        """Old cache .npz without .meta.json should be treated as invalid."""
        cache_path = tmp_path / "old_cache.npz"

        # Write only the .npz -- no sidecar
        embeddings = np.array([[0.1, 0.2], [0.3, 0.4]])
        np.savez_compressed(
            cache_path,
            embeddings=embeddings,
            email_ids=np.array(["e1", "e2"], dtype=object),
        )

        cache = EmbeddingCache(cache_path=cache_path)

        assert cache.size == 0
        # The old .npz should be deleted
        assert not cache_path.exists()

    def _caplog_for_cache(self, caplog):
        """Add caplog handler to the cache logger (propagate=False prevents root capture)."""
        import logging
        cache_logger = logging.getLogger("src.cache.embedding_cache")
        cache_logger.addHandler(caplog.handler)
        caplog.handler.setLevel(logging.WARNING)
        return cache_logger

    def test_old_cache_without_metadata_logs_warning(self, tmp_path, caplog):
        """Old cache without metadata should emit a warning."""
        cache_path = tmp_path / "old_cache.npz"
        np.savez_compressed(
            cache_path,
            embeddings=np.random.rand(1, 3),
            email_ids=np.array(["e1"], dtype=object),
        )

        cache_logger = self._caplog_for_cache(caplog)
        try:
            EmbeddingCache(cache_path=cache_path)
        finally:
            cache_logger.removeHandler(caplog.handler)

        assert any("metadata sidecar" in msg for msg in caplog.messages)

    # ---- Mismatch logs warning ----

    def test_model_mismatch_logs_warning(self, tmp_path, caplog):
        """Model name mismatch should log a warning about the change."""
        cache_path = tmp_path / "test_cache.npz"
        _write_npz_with_metadata(
            cache_path, np.random.rand(1, 3), ["e1"],
            model_name="old-model"
        )

        cache_logger = self._caplog_for_cache(caplog)
        try:
            EmbeddingCache(cache_path=cache_path, model_name="new-model")
        finally:
            cache_logger.removeHandler(caplog.handler)

        assert any("Embedding model changed" in msg for msg in caplog.messages)

    def test_text_length_mismatch_logs_warning(self, tmp_path, caplog):
        """Max text length mismatch should log a warning."""
        cache_path = tmp_path / "test_cache.npz"
        _write_npz_with_metadata(
            cache_path, np.random.rand(1, 3), ["e1"],
            max_text_length=1500
        )

        cache_logger = self._caplog_for_cache(caplog)
        try:
            EmbeddingCache(cache_path=cache_path, max_text_length=2000)
        finally:
            cache_logger.removeHandler(caplog.handler)

        assert any("Max text length changed" in msg for msg in caplog.messages)

    def test_dim_mismatch_logs_warning(self, tmp_path, caplog):
        """Embedding dimension mismatch should log a warning."""
        cache_path = tmp_path / "test_cache.npz"
        _write_npz_with_metadata(
            cache_path, np.random.rand(1, 3), ["e1"],
            embedding_dim=384
        )

        cache_logger = self._caplog_for_cache(caplog)
        try:
            EmbeddingCache(cache_path=cache_path, embedding_dim=768)
        finally:
            cache_logger.removeHandler(caplog.handler)

        assert any("Embedding dimension changed" in msg for msg in caplog.messages)

    # ---- Corrupted metadata sidecar ----

    def test_corrupted_metadata_sidecar_starts_fresh(self, tmp_path):
        """Corrupted .meta.json should be treated as missing metadata."""
        cache_path = tmp_path / "test_cache.npz"
        meta_path = cache_path.with_suffix(".meta.json")

        embeddings = np.random.rand(2, 3)
        np.savez_compressed(
            cache_path,
            embeddings=embeddings,
            email_ids=np.array(["e1", "e2"], dtype=object),
        )
        meta_path.write_text("{{not valid json}", encoding="utf-8")

        cache = EmbeddingCache(cache_path=cache_path)
        assert cache.size == 0

    # ---- Cache files cleaned up after invalidation ----

    def test_invalidation_removes_both_files(self, tmp_path):
        """After invalidation, both .npz and .meta.json should be deleted."""
        cache_path = tmp_path / "test_cache.npz"
        meta_path = cache_path.with_suffix(".meta.json")

        _write_npz_with_metadata(
            cache_path, np.random.rand(2, 3), ["e1", "e2"],
            model_name="old-model"
        )
        assert cache_path.exists()
        assert meta_path.exists()

        # Trigger invalidation via model mismatch
        EmbeddingCache(cache_path=cache_path, model_name="new-model")

        assert not cache_path.exists()
        assert not meta_path.exists()

    # ---- Save after invalidation creates fresh metadata ----

    def test_save_after_invalidation_creates_new_metadata(self, tmp_path):
        """After cache invalidation, saving creates correct new metadata."""
        cache_path = tmp_path / "test_cache.npz"
        meta_path = cache_path.with_suffix(".meta.json")

        _write_npz_with_metadata(
            cache_path, np.random.rand(2, 3), ["e1", "e2"],
            model_name="old-model"
        )

        # Invalidate via model change
        cache = EmbeddingCache(
            cache_path=cache_path,
            model_name="new-model",
            embedding_dim=512,
            max_text_length=2000,
        )
        assert cache.size == 0

        # Add new data and save
        cache.add(["x1"], np.random.rand(1, 512))
        cache.save()

        assert meta_path.exists()
        metadata = json.loads(meta_path.read_text(encoding="utf-8"))
        assert metadata["model_name"] == "new-model"
        assert metadata["embedding_dim"] == 512
        assert metadata["max_text_length"] == 2000
