"""
Unit tests for Phase 4, Work Item 4.2: EmbeddingStore with sqlite-vec.

Tests the EmbeddingStore class that provides vector storage and cosine
similarity search using sqlite-vec virtual tables.

TDD: Tests written before implementation.
"""

import numpy as np
import pytest

from src.storage.database import Database

# =============================================================================
# Helper to skip if sqlite-vec is not available
# =============================================================================


def _sqlite_vec_available() -> bool:
    """Check whether sqlite-vec can be loaded."""
    try:
        import sqlite_vec  # noqa: F401

        return True
    except ImportError:
        return False


pytestmark = pytest.mark.skipif(
    not _sqlite_vec_available(),
    reason="sqlite-vec not installed",
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def db(tmp_path):
    """Create a temporary Database instance."""
    db_path = tmp_path / "test_embed.db"
    database = Database(db_path)
    yield database
    database.close()


@pytest.fixture
def store(db):
    """Create an EmbeddingStore bound to a Database."""
    from src.storage.embedding_store import EmbeddingStore

    return EmbeddingStore(db, embedding_dim=4)


@pytest.fixture
def store_1024(db):
    """Create an EmbeddingStore with 1024-dim embeddings."""
    from src.storage.embedding_store import EmbeddingStore

    return EmbeddingStore(db, embedding_dim=1024)


# =============================================================================
# Class existence and construction
# =============================================================================


class TestEmbeddingStoreCreation:
    """Test EmbeddingStore construction and virtual table creation."""

    def test_class_exists(self):
        """EmbeddingStore can be imported."""
        from src.storage.embedding_store import EmbeddingStore

        assert EmbeddingStore is not None

    def test_construction_creates_virtual_table(self, db):
        """Constructing EmbeddingStore should create the vec0 virtual table."""
        from src.storage.embedding_store import EmbeddingStore

        EmbeddingStore(db, embedding_dim=4)
        # Table should exist — querying it should not raise
        cursor = db.execute("SELECT COUNT(*) FROM vec_embeddings")
        assert cursor.fetchone()[0] == 0

    def test_construction_with_default_dim(self, db):
        """EmbeddingStore should default to 1024 dimensions."""
        from src.storage.embedding_store import EmbeddingStore

        store = EmbeddingStore(db)
        assert store.embedding_dim == 1024

    def test_construction_idempotent(self, db):
        """Creating EmbeddingStore twice on the same DB should not fail."""
        from src.storage.embedding_store import EmbeddingStore

        EmbeddingStore(db, embedding_dim=4)
        EmbeddingStore(db, embedding_dim=4)  # Should not raise


# =============================================================================
# Add (single and batch)
# =============================================================================


class TestEmbeddingStoreAdd:
    """Test adding embeddings to the store."""

    def test_add_single_embedding(self, store):
        """Add a single embedding and verify it is stored."""
        emb = np.array([0.1, 0.2, 0.3, 0.4], dtype=np.float32)
        store.add("email_1", emb)

        retrieved = store.get("email_1")
        assert retrieved is not None
        assert np.allclose(retrieved, emb)

    def test_add_preserves_float64_by_conversion(self, store):
        """Float64 input should be converted to float32 for sqlite-vec."""
        emb = np.array([0.1, 0.2, 0.3, 0.4], dtype=np.float64)
        store.add("email_1", emb)

        retrieved = store.get("email_1")
        assert retrieved is not None
        assert retrieved.dtype == np.float32
        assert np.allclose(retrieved, emb, atol=1e-7)

    def test_add_wrong_dimension_raises(self, store):
        """Adding an embedding with wrong dimension should raise ValueError."""
        emb = np.array([0.1, 0.2, 0.3], dtype=np.float32)  # 3-d, store expects 4
        with pytest.raises(ValueError, match="[Dd]imension"):
            store.add("email_1", emb)

    def test_add_batch(self, store):
        """Add a batch of embeddings and verify all are stored."""
        ids = ["email_1", "email_2", "email_3"]
        embs = np.array(
            [[0.1, 0.2, 0.3, 0.4], [0.5, 0.6, 0.7, 0.8], [0.9, 1.0, 1.1, 1.2]],
            dtype=np.float32,
        )
        store.add_batch(ids, embs)

        for i, email_id in enumerate(ids):
            retrieved = store.get(email_id)
            assert retrieved is not None
            assert np.allclose(retrieved, embs[i])

    def test_add_batch_mismatched_lengths_raises(self, store):
        """add_batch should raise if ids and embeddings have different lengths."""
        ids = ["email_1", "email_2"]
        embs = np.random.rand(3, 4).astype(np.float32)
        with pytest.raises(ValueError, match="[Nn]umber"):
            store.add_batch(ids, embs)

    def test_add_batch_empty_is_noop(self, store):
        """add_batch with empty lists should succeed without error."""
        store.add_batch([], np.array([]).reshape(0, 4).astype(np.float32))
        assert store.count() == 0

    def test_add_duplicate_replaces(self, store):
        """Adding the same email_id again should replace the embedding."""
        emb_v1 = np.array([0.1, 0.2, 0.3, 0.4], dtype=np.float32)
        emb_v2 = np.array([0.9, 0.8, 0.7, 0.6], dtype=np.float32)

        store.add("email_1", emb_v1)
        store.add("email_1", emb_v2)

        retrieved = store.get("email_1")
        assert np.allclose(retrieved, emb_v2)
        assert store.count() == 1


# =============================================================================
# Get (single)
# =============================================================================


class TestEmbeddingStoreGet:
    """Test retrieving embeddings."""

    def test_get_existing(self, store):
        """Get returns the correct embedding for an existing ID."""
        emb = np.array([0.1, 0.2, 0.3, 0.4], dtype=np.float32)
        store.add("email_1", emb)

        retrieved = store.get("email_1")
        assert retrieved is not None
        assert np.allclose(retrieved, emb)

    def test_get_nonexistent_returns_none(self, store):
        """Get returns None for a non-existent ID."""
        result = store.get("nonexistent")
        assert result is None

    def test_get_returns_copy(self, store):
        """get() should return a numpy array (not a memoryview or bytes)."""
        emb = np.array([0.1, 0.2, 0.3, 0.4], dtype=np.float32)
        store.add("email_1", emb)

        retrieved = store.get("email_1")
        assert isinstance(retrieved, np.ndarray)
        assert retrieved.dtype == np.float32


# =============================================================================
# Search similar (cosine similarity)
# =============================================================================


class TestEmbeddingStoreSearchSimilar:
    """Test cosine similarity search."""

    @pytest.fixture
    def populated_store(self, store):
        """Store pre-loaded with known embeddings for similarity tests."""
        store.add("email_a", np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32))
        store.add("email_b", np.array([0.9, 0.1, 0.0, 0.0], dtype=np.float32))
        store.add("email_c", np.array([0.0, 0.0, 1.0, 0.0], dtype=np.float32))
        store.add("email_d", np.array([0.0, 0.0, 0.0, 1.0], dtype=np.float32))
        return store

    def test_search_returns_nearest(self, populated_store):
        """search_similar should return the closest embedding first."""
        query = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
        results = populated_store.search_similar(query, k=2)

        assert len(results) == 2
        # First result should be email_a (exact match)
        assert results[0][0] == "email_a"
        # Second should be email_b (most similar after exact match)
        assert results[1][0] == "email_b"

    def test_search_returns_email_id_and_distance(self, populated_store):
        """Each result should be a (email_id, distance) tuple."""
        query = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
        results = populated_store.search_similar(query, k=1)

        assert len(results) == 1
        email_id, distance = results[0]
        assert isinstance(email_id, str)
        assert isinstance(distance, float)

    def test_search_exact_match_distance_is_zero(self, populated_store):
        """Exact match should have distance 0.0 (cosine distance)."""
        query = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
        results = populated_store.search_similar(query, k=1)

        _, distance = results[0]
        assert distance == pytest.approx(0.0, abs=1e-6)

    def test_search_opposite_has_high_distance(self, populated_store):
        """Orthogonal vectors should have cosine distance ~1.0."""
        query = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
        results = populated_store.search_similar(query, k=4)

        # email_c and email_d are orthogonal to query → distance ~1.0
        distances_by_id = dict(results)
        assert distances_by_id["email_c"] == pytest.approx(1.0, abs=0.1)
        assert distances_by_id["email_d"] == pytest.approx(1.0, abs=0.1)

    def test_search_respects_k_limit(self, populated_store):
        """search_similar should return at most k results."""
        query = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
        results = populated_store.search_similar(query, k=2)
        assert len(results) == 2

    def test_search_k_larger_than_store_returns_all(self, populated_store):
        """When k > total embeddings, return all available."""
        query = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
        results = populated_store.search_similar(query, k=100)
        assert len(results) == 4

    def test_search_empty_store_returns_empty(self, store):
        """Searching an empty store should return an empty list."""
        query = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
        results = store.search_similar(query, k=5)
        assert results == []

    def test_search_wrong_dimension_raises(self, populated_store):
        """Query with wrong dimension should raise ValueError."""
        query = np.array([1.0, 0.0, 0.0], dtype=np.float32)  # 3-d, store expects 4
        with pytest.raises(ValueError, match="[Dd]imension"):
            populated_store.search_similar(query, k=5)


# =============================================================================
# Delete and sync
# =============================================================================


class TestEmbeddingStoreDelete:
    """Test deletion and sync operations."""

    def test_delete_existing(self, store):
        """Deleting an existing embedding should remove it."""
        store.add("email_1", np.array([0.1, 0.2, 0.3, 0.4], dtype=np.float32))
        store.delete("email_1")

        assert store.get("email_1") is None
        assert store.count() == 0

    def test_delete_nonexistent_is_noop(self, store):
        """Deleting a non-existent ID should not raise."""
        store.delete("nonexistent")  # Should not raise

    def test_sync_with_ids_removes_stale(self, store):
        """sync_with_ids should remove embeddings not in the valid set."""
        store.add("email_1", np.array([0.1, 0.2, 0.3, 0.4], dtype=np.float32))
        store.add("email_2", np.array([0.5, 0.6, 0.7, 0.8], dtype=np.float32))
        store.add("email_3", np.array([0.9, 1.0, 1.1, 1.2], dtype=np.float32))

        removed = store.sync_with_ids({"email_1", "email_3"})

        assert removed == 1
        assert store.get("email_1") is not None
        assert store.get("email_2") is None
        assert store.get("email_3") is not None

    def test_sync_with_ids_noop_when_all_valid(self, store):
        """sync_with_ids returns 0 when all IDs are in the valid set."""
        store.add("email_1", np.array([0.1, 0.2, 0.3, 0.4], dtype=np.float32))
        removed = store.sync_with_ids({"email_1"})
        assert removed == 0

    def test_sync_with_empty_set_removes_all(self, store):
        """sync_with_ids with empty set should remove everything."""
        store.add("email_1", np.array([0.1, 0.2, 0.3, 0.4], dtype=np.float32))
        store.add("email_2", np.array([0.5, 0.6, 0.7, 0.8], dtype=np.float32))

        removed = store.sync_with_ids(set())
        assert removed == 2
        assert store.count() == 0


# =============================================================================
# Count and contains
# =============================================================================


class TestEmbeddingStoreCountContains:
    """Test count and contains helper methods."""

    def test_count_empty(self, store):
        """Empty store should have count 0."""
        assert store.count() == 0

    def test_count_after_adds(self, store):
        """Count should reflect number of stored embeddings."""
        store.add("email_1", np.array([0.1, 0.2, 0.3, 0.4], dtype=np.float32))
        store.add("email_2", np.array([0.5, 0.6, 0.7, 0.8], dtype=np.float32))
        assert store.count() == 2

    def test_contains_true(self, store):
        """contains should return True for stored ID."""
        store.add("email_1", np.array([0.1, 0.2, 0.3, 0.4], dtype=np.float32))
        assert store.contains("email_1") is True

    def test_contains_false(self, store):
        """contains should return False for non-existent ID."""
        assert store.contains("nonexistent") is False


# =============================================================================
# Get batch
# =============================================================================


class TestEmbeddingStoreGetBatch:
    """Test batch retrieval of embeddings."""

    def test_get_batch_all_found(self, store):
        """get_batch returns embeddings and empty missing list when all found."""
        ids = ["email_1", "email_2"]
        embs = np.array([[0.1, 0.2, 0.3, 0.4], [0.5, 0.6, 0.7, 0.8]], dtype=np.float32)
        store.add_batch(ids, embs)

        result_embs, missing = store.get_batch(ids)
        assert result_embs.shape == (2, 4)
        assert len(missing) == 0
        assert np.allclose(result_embs[0], embs[0])
        assert np.allclose(result_embs[1], embs[1])

    def test_get_batch_with_missing(self, store):
        """get_batch reports missing IDs correctly."""
        store.add("email_1", np.array([0.1, 0.2, 0.3, 0.4], dtype=np.float32))

        result_embs, missing = store.get_batch(["email_1", "email_2"])
        assert result_embs.shape == (1, 4)
        assert missing == ["email_2"]

    def test_get_batch_all_missing(self, store):
        """get_batch with all missing IDs returns empty array."""
        result_embs, missing = store.get_batch(["email_1", "email_2"])
        assert result_embs.shape == (0, 0)
        assert set(missing) == {"email_1", "email_2"}

    def test_get_batch_empty_input(self, store):
        """get_batch with empty list returns empty results."""
        result_embs, missing = store.get_batch([])
        assert result_embs.shape == (0, 0)
        assert missing == []


# =============================================================================
# Integration: EmbeddingCache delegation to EmbeddingStore
# =============================================================================


class TestEmbeddingCacheDelegation:
    """Test that EmbeddingCache delegates to EmbeddingStore when database is provided."""

    @pytest.fixture
    def db_cache(self, tmp_path):
        """Create EmbeddingCache with database-backed storage."""
        from src.cache.embedding_cache import EmbeddingCache

        db_path = tmp_path / "test_delegate.db"
        database = Database(db_path)
        cache_path = tmp_path / "test_cache.npz"
        cache = EmbeddingCache(
            cache_path=cache_path,
            database=database,
            embedding_dim=4,
        )
        yield cache
        database.close()

    @pytest.fixture
    def npz_cache(self, tmp_path):
        """Create EmbeddingCache without database (NPZ-only)."""
        from src.cache.embedding_cache import EmbeddingCache

        cache_path = tmp_path / "test_cache.npz"
        return EmbeddingCache(cache_path=cache_path, embedding_dim=4)

    def test_db_backed_add_and_get(self, db_cache):
        """DB-backed cache should store and retrieve embeddings."""
        ids = ["email_1", "email_2"]
        embs = np.array([[0.1, 0.2, 0.3, 0.4], [0.5, 0.6, 0.7, 0.8]], dtype=np.float32)

        db_cache.add(ids, embs)

        retrieved = db_cache.get("email_1")
        assert retrieved is not None
        assert np.allclose(retrieved, embs[0], atol=1e-7)

    def test_db_backed_contains(self, db_cache):
        """DB-backed cache should support contains()."""
        db_cache.add(["email_1"], np.array([[0.1, 0.2, 0.3, 0.4]], dtype=np.float32))

        assert db_cache.contains("email_1") is True
        assert db_cache.contains("nonexistent") is False

    def test_db_backed_get_batch(self, db_cache):
        """DB-backed cache should support get_batch()."""
        ids = ["email_1", "email_2"]
        embs = np.array([[0.1, 0.2, 0.3, 0.4], [0.5, 0.6, 0.7, 0.8]], dtype=np.float32)
        db_cache.add(ids, embs)

        result_embs, missing = db_cache.get_batch(["email_1", "email_3"])
        assert result_embs.shape == (1, 4)
        assert missing == ["email_3"]

    def test_db_backed_invalidate(self, db_cache):
        """DB-backed cache should support invalidate()."""
        db_cache.add(["email_1", "email_2"], np.random.rand(2, 4).astype(np.float32))

        db_cache.invalidate("email_1")
        assert db_cache.contains("email_1") is False
        assert db_cache.contains("email_2") is True

    def test_db_backed_invalidate_batch(self, db_cache):
        """DB-backed cache should support invalidate_batch()."""
        db_cache.add(
            ["email_1", "email_2", "email_3"],
            np.random.rand(3, 4).astype(np.float32),
        )
        db_cache.invalidate_batch(["email_1", "email_3"])

        assert db_cache.size == 1
        assert db_cache.contains("email_2") is True

    def test_db_backed_clear(self, db_cache):
        """DB-backed cache should support clear()."""
        db_cache.add(["email_1"], np.random.rand(1, 4).astype(np.float32))
        db_cache.clear()

        assert db_cache.size == 0

    def test_db_backed_partition_ids(self, db_cache):
        """DB-backed cache should support partition_ids()."""
        db_cache.add(["email_1"], np.random.rand(1, 4).astype(np.float32))

        cached, uncached = db_cache.partition_ids(["email_1", "email_2"])
        assert cached == ["email_1"]
        assert uncached == ["email_2"]

    def test_db_backed_size(self, db_cache):
        """DB-backed cache should report correct size."""
        assert db_cache.size == 0
        db_cache.add(["email_1", "email_2"], np.random.rand(2, 4).astype(np.float32))
        assert db_cache.size == 2

    def test_db_backed_save_is_noop(self, db_cache):
        """DB-backed cache save() should not raise (data is already persisted)."""
        db_cache.add(["email_1"], np.random.rand(1, 4).astype(np.float32))
        db_cache.save()  # Should not raise — DB stores are auto-committed

    def test_db_backed_statistics_tracked(self, db_cache):
        """DB-backed cache should track hit/miss statistics."""
        db_cache.add(["email_1"], np.random.rand(1, 4).astype(np.float32))
        db_cache.get("email_1")  # hit
        db_cache.get("nonexistent")  # miss

        stats = db_cache.get_statistics()
        assert stats.hits == 1
        assert stats.misses == 1

    def test_npz_still_works_without_database(self, npz_cache):
        """Existing NPZ path should still work when no database is provided."""
        ids = ["email_1", "email_2"]
        embs = np.array([[0.1, 0.2, 0.3, 0.4], [0.5, 0.6, 0.7, 0.8]])

        npz_cache.add(ids, embs)
        assert npz_cache.size == 2
        assert npz_cache.contains("email_1") is True

        retrieved = npz_cache.get("email_1")
        assert retrieved is not None
        assert np.allclose(retrieved, embs[0])


# =============================================================================
# High-dimensional embeddings (realistic 1024-d)
# =============================================================================


class TestEmbeddingStoreHighDim:
    """Test with realistic 1024-dimensional embeddings."""

    def test_add_and_get_1024d(self, store_1024):
        """Store and retrieve a 1024-dim embedding."""
        emb = np.random.rand(1024).astype(np.float32)
        store_1024.add("email_1", emb)

        retrieved = store_1024.get("email_1")
        assert retrieved is not None
        assert retrieved.shape == (1024,)
        assert np.allclose(retrieved, emb)

    def test_similarity_search_1024d(self, store_1024):
        """Similarity search should work with 1024-dim vectors."""
        base = np.random.rand(1024).astype(np.float32)
        similar = base + np.random.rand(1024).astype(np.float32) * 0.01  # small perturbation
        dissimilar = np.random.rand(1024).astype(np.float32)

        store_1024.add("base", base)
        store_1024.add("similar", similar)
        store_1024.add("dissimilar", dissimilar)

        results = store_1024.search_similar(base, k=3)
        # First result should be exact match
        assert results[0][0] == "base"
        # Second should be the small perturbation
        assert results[1][0] == "similar"

    def test_batch_add_1024d(self, store_1024):
        """Batch add should work with 1024-dim vectors."""
        n = 50
        ids = [f"email_{i}" for i in range(n)]
        embs = np.random.rand(n, 1024).astype(np.float32)

        store_1024.add_batch(ids, embs)
        assert store_1024.count() == n

        # Verify a few random ones
        for i in [0, 25, 49]:
            retrieved = store_1024.get(ids[i])
            assert np.allclose(retrieved, embs[i])
