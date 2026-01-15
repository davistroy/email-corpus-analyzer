"""
Cache module for Email Corpus Analyzer (Task 4B.3).

Provides efficient caching for embeddings and other computed data
to support incremental analysis workflows.
"""
from .embedding_cache import CacheStatistics, EmbeddingCache

__all__ = ["EmbeddingCache", "CacheStatistics"]
