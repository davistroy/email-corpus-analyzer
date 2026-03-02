"""
Embedding Provider abstraction layer.

Provides a pluggable interface for generating text embeddings, supporting both
local sentence-transformers models and remote OpenAI-compatible /v1/embeddings
endpoints (e.g., llama.cpp, vLLM, Ollama embeddings).

Usage:
    # Local (default, current behavior):
    provider = LocalEmbeddingProvider("mixedbread-ai/mxbai-embed-large-v1")

    # Remote (OpenAI-compatible endpoint):
    provider = RemoteEmbeddingProvider(
        base_url="http://jetson.local:8080/v1",
        model_name="Qwen3-Embedding-0.6B",
    )

    embeddings = provider.encode(texts, show_progress_bar=True)
"""

import logging
from abc import ABC, abstractmethod

import numpy as np
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


class EmbeddingProvider(ABC):
    """Abstract base class for embedding providers."""

    @abstractmethod
    def encode(
        self,
        texts: list[str],
        show_progress_bar: bool = False,
        convert_to_numpy: bool = True,
    ) -> np.ndarray:
        """
        Encode a list of texts into embeddings.

        Args:
            texts: List of text strings to embed.
            show_progress_bar: Whether to display a progress bar.
            convert_to_numpy: Whether to return as numpy array (always True
                for this interface, kept for API compatibility with
                SentenceTransformer.encode).

        Returns:
            numpy array of shape (len(texts), embedding_dim).
        """

    @property
    @abstractmethod
    def embedding_dim(self) -> int:
        """Return the dimensionality of the embedding vectors."""


class LocalEmbeddingProvider(EmbeddingProvider):
    """
    Embedding provider using a local sentence-transformers model.

    Wraps SentenceTransformer to match the EmbeddingProvider interface.
    This preserves the existing behavior of SemanticAnalyzer.
    """

    def __init__(self, model_name: str = "mixedbread-ai/mxbai-embed-large-v1"):
        """
        Initialize with a sentence-transformers model.

        The model is loaded immediately on construction.

        Args:
            model_name: Hugging Face model identifier.
        """
        logger.info(f"Loading sentence transformer model: {model_name}")
        self._model = SentenceTransformer(model_name)
        self._model_name = model_name
        logger.info(f"Model loaded successfully: {model_name}")

    def encode(
        self,
        texts: list[str],
        show_progress_bar: bool = False,
        convert_to_numpy: bool = True,
    ) -> np.ndarray:
        """Encode texts using the local sentence-transformers model."""
        result = self._model.encode(
            texts, show_progress_bar=show_progress_bar, convert_to_numpy=True
        )
        return np.asarray(result)

    @property
    def embedding_dim(self) -> int:
        """Return embedding dimension from the loaded model."""
        return self._model.get_sentence_embedding_dimension()

    @property
    def model(self):
        """Expose the underlying SentenceTransformer model for backward compatibility."""
        return self._model


class RemoteEmbeddingProvider(EmbeddingProvider):
    """
    Embedding provider using a remote OpenAI-compatible /v1/embeddings endpoint.

    Designed for endpoints like llama.cpp, vLLM, Ollama, or any server
    exposing the OpenAI embeddings API format. Uses the openai Python SDK
    as the transport layer with batched requests to avoid overwhelming
    resource-constrained endpoints (e.g., Jetson devices).
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8080/v1",
        model_name: str = "Qwen3-Embedding-0.6B",
        api_key: str = "not-needed",
        batch_size: int = 64,
    ):
        """
        Initialize remote embedding provider.

        Args:
            base_url: Base URL for the OpenAI-compatible API (must include /v1).
            model_name: Model name to pass in the API request.
            api_key: API key (use "not-needed" for local endpoints without auth).
            batch_size: Number of texts per API request. Smaller values reduce
                memory pressure on the endpoint; larger values improve throughput.
        """
        from openai import OpenAI

        self._client = OpenAI(
            base_url=base_url,
            api_key=api_key or "not-needed",
        )
        self._model_name = model_name
        self._batch_size = batch_size
        self._embedding_dim: int | None = None
        self._base_url = base_url

        logger.info(
            f"RemoteEmbeddingProvider initialized: {base_url} "
            f"model={model_name} batch_size={batch_size}"
        )

    def encode(
        self,
        texts: list[str],
        show_progress_bar: bool = False,
        convert_to_numpy: bool = True,
    ) -> np.ndarray:
        """
        Encode texts by calling the remote /v1/embeddings endpoint in batches.

        Args:
            texts: List of text strings to embed.
            show_progress_bar: If True, display a tqdm progress bar.
            convert_to_numpy: Ignored (always returns numpy). Kept for API compat.

        Returns:
            numpy array of shape (len(texts), embedding_dim).

        Raises:
            RuntimeError: If the remote endpoint returns an error.
        """
        if not texts:
            # Return empty array with correct shape if we know the dim
            dim = self._embedding_dim or 0
            return np.empty((0, dim), dtype=np.float32)

        all_embeddings: list[list[float]] = []
        n_texts = len(texts)
        n_batches = (n_texts + self._batch_size - 1) // self._batch_size

        logger.info(
            f"Encoding {n_texts} texts in {n_batches} batches (batch_size={self._batch_size})"
        )

        # Set up optional progress bar
        batch_iter = range(0, n_texts, self._batch_size)
        if show_progress_bar:
            try:
                from tqdm import tqdm

                batch_iter = tqdm(
                    batch_iter,
                    total=n_batches,
                    desc="Embedding",
                    unit="batch",
                )
            except ImportError:
                logger.warning("tqdm not available, progress bar disabled")

        for batch_idx, start in enumerate(batch_iter, 1):
            end = min(start + self._batch_size, n_texts)
            batch_texts = texts[start:end]

            response = self._client.embeddings.create(
                input=batch_texts,
                model=self._model_name,
            )

            # Response data is a list of Embedding objects, each with .embedding
            # Sort by index to ensure correct ordering
            batch_data = sorted(response.data, key=lambda x: x.index)
            batch_embeddings = [item.embedding for item in batch_data]
            all_embeddings.extend(batch_embeddings)

            if not show_progress_bar and batch_idx % 10 == 0:
                logger.info(f"Embedded {batch_idx}/{n_batches} batches")

        result = np.array(all_embeddings, dtype=np.float32)

        # Cache the embedding dimension from the first successful call
        if self._embedding_dim is None and result.shape[0] > 0:
            self._embedding_dim = result.shape[1]
            logger.info(f"Detected embedding dimension: {self._embedding_dim}")

        logger.info(f"Embedding complete: {result.shape}")
        return result

    @property
    def embedding_dim(self) -> int:
        """
        Return the embedding dimension.

        If not yet known (no encode() call made), probe the endpoint with
        a single empty-string request to discover the dimension.
        """
        if self._embedding_dim is None:
            logger.debug("Probing endpoint for embedding dimension...")
            response = self._client.embeddings.create(
                input=["dimension probe"],
                model=self._model_name,
            )
            self._embedding_dim = len(response.data[0].embedding)
            logger.info(f"Probed embedding dimension: {self._embedding_dim}")
        return self._embedding_dim
