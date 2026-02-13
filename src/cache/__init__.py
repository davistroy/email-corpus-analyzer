"""
Cache module for Email Corpus Analyzer (Task 4B.3).

Provides efficient caching for embeddings and other computed data
to support incremental analysis workflows.
"""
from .embedding_cache import (
    DEFAULT_EMBEDDING_DIM,
    DEFAULT_MAX_TEXT_LENGTH,
    DEFAULT_MODEL_NAME,
    CacheStatistics,
    EmbeddingCache,
)

__all__ = [
    "CacheStatistics",
    "DEFAULT_EMBEDDING_DIM",
    "DEFAULT_MAX_TEXT_LENGTH",
    "DEFAULT_MODEL_NAME",
    "EmbeddingCache",
]
