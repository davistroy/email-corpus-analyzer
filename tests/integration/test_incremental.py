"""
Integration tests for incremental extraction and analysis.

Tests the incremental workflow for extracting new emails and updating analysis.
Per Phase 7, Track 7C specification.
"""

import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.models.corpus import Corpus, CorpusMetadata
from src.models.email import Email

# =============================================================================
# Test Fixtures
# =============================================================================


def create_batch_emails(
    start_id: int,
    count: int,
    base_date: datetime,
) -> list[Email]:
    """Create a batch of test emails."""
    emails = []
    for i in range(count):
        emails.append(
            Email(
                id=f"email_{start_id + i:04d}",
                sender_email=f"sender{i % 5}@example.com",
                sender_name=f"Sender {i % 5}",
                sender_domain="example.com",
                subject=f"Test subject {start_id + i}",
                body_text=f"Test body for email {start_id + i}",
                received_date=base_date + timedelta(days=i),
                has_attachments=i % 3 == 0,
            )
        )
    return emails


def create_corpus_with_emails(emails: list[Email]) -> Corpus:
    """Create a corpus with given emails."""
    return Corpus(
        extraction_metadata=CorpusMetadata(
            extraction_date=datetime.now(),
            total_emails=len(emails),
            source="test",
            user_email="test@example.com",
        ),
        emails=emails,
    )


@pytest.fixture
def temp_output_dir():
    """Create a temporary output directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def initial_corpus():
    """Create initial corpus with 20 emails."""
    base_date = datetime(2024, 1, 1)
    emails = create_batch_emails(0, 20, base_date)
    return create_corpus_with_emails(emails)


@pytest.fixture
def incremental_emails():
    """Create new emails to add incrementally."""
    base_date = datetime(2024, 1, 25)  # After initial emails
    return create_batch_emails(20, 10, base_date)


# =============================================================================
# Test Incremental Extraction
# =============================================================================


class TestIncrementalExtraction:
    """Integration tests for incremental email extraction."""

    def test_corpus_merge_preserves_existing_emails(self, initial_corpus, incremental_emails):
        """Test that merging corpus preserves existing emails."""
        # Simulate incremental merge
        merged_emails = list(initial_corpus.emails) + incremental_emails

        merged_corpus = Corpus(
            extraction_metadata=CorpusMetadata(
                extraction_date=datetime.now(),
                total_emails=len(merged_emails),
                source="test",
                user_email="test@example.com",
                last_extraction_date=initial_corpus.extraction_metadata.extraction_date,
            ),
            emails=merged_emails,
        )

        # Verify all emails present
        assert len(merged_corpus.emails) == 30
        assert merged_corpus.extraction_metadata.total_emails == 30

        # Verify original emails preserved
        original_ids = {e.id for e in initial_corpus.emails}
        merged_ids = {e.id for e in merged_corpus.emails}
        assert original_ids.issubset(merged_ids)

    def test_corpus_merge_deduplicates_by_id(self, initial_corpus):
        """Test that merging deduplicates emails by ID."""
        # Create duplicate emails with same IDs
        duplicate_emails = [
            Email(
                id="email_0000",  # Same ID as existing
                sender_email="different@example.com",
                sender_name="Different Sender",
                sender_domain="example.com",
                subject="Duplicate email",
                body_text="This should not be added",
                received_date=datetime(2024, 2, 1),
                has_attachments=False,
            )
        ]

        # Merge with deduplication
        existing_ids = {e.id for e in initial_corpus.emails}
        new_emails = [e for e in duplicate_emails if e.id not in existing_ids]
        merged_emails = list(initial_corpus.emails) + new_emails

        # Verify no duplicates
        assert len(merged_emails) == len(initial_corpus.emails)

    def test_incremental_extraction_updates_metadata(self, initial_corpus, incremental_emails):
        """Test that incremental extraction updates metadata correctly."""
        merged_emails = list(initial_corpus.emails) + incremental_emails

        merged_corpus = Corpus(
            extraction_metadata=CorpusMetadata(
                extraction_date=datetime.now(),
                total_emails=len(merged_emails),
                source="test",
                user_email="test@example.com",
                last_extraction_date=initial_corpus.extraction_metadata.extraction_date,
            ),
            emails=merged_emails,
        )

        # Verify metadata updated
        assert merged_corpus.extraction_metadata.total_emails == 30
        assert merged_corpus.extraction_metadata.last_extraction_date is not None


# =============================================================================
# Test Incremental Analysis
# =============================================================================


class TestIncrementalAnalysis:
    """Integration tests for incremental analysis with embedding cache."""

    @patch("src.analyzers.semantic_analyzer.SentenceTransformer")
    def test_incremental_analysis_uses_cache(self, mock_st, initial_corpus, temp_output_dir):
        """Test that incremental analysis utilizes embedding cache."""
        from src.analyzers.semantic_analyzer import SemanticAnalyzer
        from src.cache.embedding_cache import EmbeddingCache

        # Setup mock
        mock_model = MagicMock()
        mock_st.return_value = mock_model

        # Create cache with initial embeddings
        cache_path = temp_output_dir / "embeddings_cache.npz"
        cache = EmbeddingCache(cache_path=cache_path)

        # Pre-populate cache with some embeddings
        initial_ids = [e.id for e in initial_corpus.emails[:10]]
        initial_embeddings = np.random.rand(10, 1024)
        cache.add(initial_ids, initial_embeddings)

        # Setup mock to return embeddings for remaining emails
        mock_model.encode.return_value = np.random.rand(10, 1024)

        # Run incremental analysis
        analyzer = SemanticAnalyzer()
        analyzer.model = mock_model

        result = analyzer.analyze_incremental(
            corpus=initial_corpus,
            embedding_cache=cache,
            num_clusters=3,
        )

        # Verify cache was used
        assert result.stats["cached_count"] == 10
        assert result.stats["generated_count"] == 10

    @patch("src.analyzers.semantic_analyzer.SentenceTransformer")
    def test_incremental_analysis_updates_cache(self, mock_st, initial_corpus, temp_output_dir):
        """Test that incremental analysis updates the cache with new embeddings."""
        from src.analyzers.semantic_analyzer import SemanticAnalyzer
        from src.cache.embedding_cache import EmbeddingCache

        mock_model = MagicMock()
        mock_model.encode.return_value = np.random.rand(20, 1024)
        mock_st.return_value = mock_model

        # Create empty cache
        cache_path = temp_output_dir / "embeddings_cache.npz"
        cache = EmbeddingCache(cache_path=cache_path)
        initial_size = cache.size

        # Run incremental analysis
        analyzer = SemanticAnalyzer()
        analyzer.model = mock_model

        analyzer.analyze_incremental(
            corpus=initial_corpus,
            embedding_cache=cache,
            num_clusters=3,
        )

        # Verify cache was updated
        assert cache.size > initial_size

    @patch("src.analyzers.semantic_analyzer.SentenceTransformer")
    def test_incremental_analysis_with_all_cached(self, mock_st, initial_corpus, temp_output_dir):
        """Test incremental analysis when all emails are already cached."""
        from src.analyzers.semantic_analyzer import SemanticAnalyzer
        from src.cache.embedding_cache import EmbeddingCache

        mock_model = MagicMock()
        mock_st.return_value = mock_model

        # Create cache with all emails pre-cached
        cache_path = temp_output_dir / "embeddings_cache.npz"
        cache = EmbeddingCache(cache_path=cache_path)

        all_ids = [e.id for e in initial_corpus.emails]
        all_embeddings = np.random.rand(20, 1024)
        cache.add(all_ids, all_embeddings)

        # Run incremental analysis
        analyzer = SemanticAnalyzer()
        analyzer.model = mock_model

        result = analyzer.analyze_incremental(
            corpus=initial_corpus,
            embedding_cache=cache,
            num_clusters=3,
        )

        # Model should not be called since all cached
        mock_model.encode.assert_not_called()
        assert result.stats["cached_count"] == 20
        assert result.stats["generated_count"] == 0


# =============================================================================
# Test Cache Persistence
# =============================================================================


class TestCachePersistence:
    """Integration tests for embedding cache persistence."""

    def test_cache_persists_across_sessions(self, temp_output_dir):
        """Test that embedding cache persists to disk and reloads."""
        from src.cache.embedding_cache import EmbeddingCache

        cache_path = temp_output_dir / "embeddings_cache.npz"

        # Create cache and add embeddings
        cache1 = EmbeddingCache(cache_path=cache_path)
        test_ids = ["email_1", "email_2", "email_3"]
        test_embeddings = np.random.rand(3, 1024)
        cache1.add(test_ids, test_embeddings)
        cache1.save()

        # Create new cache instance (simulating new session)
        cache2 = EmbeddingCache(cache_path=cache_path)

        # Verify embeddings are available
        assert cache2.size == 3
        # Use get_batch instead of get with list
        retrieved, missing = cache2.get_batch(test_ids)
        assert len(missing) == 0
        assert retrieved.shape == (3, 1024)

    def test_cache_handles_partial_hits(self, temp_output_dir):
        """Test that cache correctly handles partial cache hits."""
        from src.cache.embedding_cache import EmbeddingCache

        cache_path = temp_output_dir / "embeddings_cache.npz"

        # Create cache with some embeddings
        cache = EmbeddingCache(cache_path=cache_path)
        cached_ids = ["email_1", "email_2"]
        cached_embeddings = np.random.rand(2, 1024)
        cache.add(cached_ids, cached_embeddings)

        # Request mix of cached and uncached using get_batch
        requested_ids = ["email_1", "email_3", "email_2", "email_4"]

        # Get cached embeddings using get_batch
        cached_hits, missing_ids = cache.get_batch(["email_1", "email_2"])
        assert cached_hits.shape == (2, 1024)
        assert len(missing_ids) == 0

        # Check which are missing
        _, all_missing = cache.get_batch(requested_ids)
        assert set(all_missing) == {"email_3", "email_4"}
