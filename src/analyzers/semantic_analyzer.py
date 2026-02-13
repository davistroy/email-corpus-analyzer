"""
Semantic Analyzer module.

Performs semantic clustering of email corpus using sentence transformers and KMeans.
Per analyzer_contract.md lines 153-221 and research.md lines 15-68.

Task 4B.4: Enhanced with incremental analysis support using embedding cache.
"""
import logging
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_samples
from sklearn.metrics.pairwise import cosine_distances

from ..models.content_cluster import ContentCluster, RepresentativeSample
from ..models.corpus import Corpus
from .base import BaseAnalyzer
from .cluster_optimizer import ElbowOptimizer, SilhouetteOptimizer

if TYPE_CHECKING:
    from src.cache.embedding_cache import EmbeddingCache

logger = logging.getLogger(__name__)


@dataclass
class IncrementalAnalysisResult:
    """Result of incremental semantic analysis (Task 4B.4)."""

    clusters: list[ContentCluster]
    stats: dict  # {cached_count, generated_count, hit_rate, etc.}


class SemanticAnalyzer(BaseAnalyzer[list[ContentCluster]]):
    """
    Semantic analyzer using sentence transformers for email clustering.

    Per FR-015, FR-016, FR-017 requirements.
    """

    @property
    def name(self) -> str:
        """Return human-readable analyzer name."""
        return "Semantic Analyzer"

    def supports_incremental(self) -> bool:
        """Return True as semantic analyzer supports incremental analysis."""
        return True

    def __init__(
        self,
        model_name: str = "mixedbread-ai/mxbai-embed-large-v1",
        max_embedding_text_length: int = 1500,
    ):
        """
        Initialize with sentence transformer model.

        Args:
            model_name: Hugging Face model identifier
            max_embedding_text_length: Max body chars for embedding text (default 1500)
        """
        self.model_name = model_name
        self.model = None
        self.max_embedding_text_length = max_embedding_text_length
        logger.debug("SemanticAnalyzer initialized (model will load on first use)")

    def _ensure_model_loaded(self):
        """Lazy load the sentence transformer model."""
        if self.model is None:
            logger.info(f"Loading sentence transformer model: {self.model_name}")
            self.model = SentenceTransformer(self.model_name)
            logger.info(f"Model loaded successfully: {self.model_name}")

    def analyze(
        self,
        corpus: Corpus,
        num_clusters: int = 10,
        auto_clusters: bool = False,
        cluster_method: str = "silhouette",
        progress_callback: Callable[[int, int], None] | None = None
    ) -> list[ContentCluster]:
        """
        Perform semantic clustering of email corpus.

        Per FR-015, FR-016, FR-017:
        - Combines subject + first 500 chars of body for embedding
        - Generates embeddings using model.encode() with progress bar
        - Uses scikit-learn KMeans for clustering
        - Identifies 5 representative samples per cluster (closest to centroid)
        - Calculates cluster percentage of corpus
        - Extracts common domains for each cluster

        Args:
            corpus: Email corpus to analyze
            num_clusters: Number of clusters (default 10)
            auto_clusters: If True, automatically determine optimal k
            cluster_method: Method for auto-clustering: "elbow" or "silhouette"
            progress_callback: Optional callback(current, total)

        Returns:
            List of ContentCluster objects

        Raises:
            ValueError: If corpus is empty or invalid
        """
        if not corpus.emails:
            raise ValueError("Cannot analyze empty corpus")

        if num_clusters < 1:
            raise ValueError(f"num_clusters must be >= 1, got {num_clusters}")

        total_emails = len(corpus.emails)

        # Ensure model is loaded before analysis
        self._ensure_model_loaded()

        # Step 1: Generate embeddings (FR-015)
        # Combine subject + body text using configurable length limit
        logger.debug(
            f"Extracting combined text for embeddings "
            f"(max_body_length={self.max_embedding_text_length})"
        )
        texts = [
            email.combined_text_with_limit(self.max_embedding_text_length)
            for email in corpus.emails
        ]

        logger.info("Generating embeddings with sentence transformer")
        if progress_callback:
            progress_callback(0, total_emails)

        # Generate embeddings with progress bar (FR-016)
        embeddings = self.model.encode(
            texts,
            show_progress_bar=True,
            convert_to_numpy=True
        )

        if progress_callback:
            progress_callback(total_emails, total_emails)

        logger.info(f"Generated embeddings with shape: {embeddings.shape}")

        # Determine effective number of clusters
        if auto_clusters and total_emails >= 3:
            # Auto-determine optimal k using specified method
            logger.info(f"Auto-determining optimal clusters using {cluster_method} method...")

            if cluster_method == "elbow":
                optimizer = ElbowOptimizer(max_k=min(15, total_emails - 1))
            else:  # silhouette (default)
                optimizer = SilhouetteOptimizer(max_k=min(15, total_emails - 1))

            optimization_result = optimizer.find_optimal_k(embeddings)
            effective_clusters = optimization_result.optimal_k

            logger.info(
                f"Auto-clustering found optimal k={effective_clusters} "
                f"(confidence: {optimization_result.confidence_score:.2f})"
            )
        else:
            # Use specified num_clusters, adjusting if corpus is too small
            effective_clusters = min(num_clusters, len(corpus.emails))
            if effective_clusters < num_clusters:
                logger.warning(
                    f"Corpus has only {len(corpus.emails)} emails, "
                    f"reducing clusters from {num_clusters} to {effective_clusters}"
                )

        logger.info(f"Starting semantic analysis of {total_emails} emails into {effective_clusters} clusters")

        # Step 2: Perform KMeans clustering (FR-016)
        logger.info(f"Performing KMeans clustering with {effective_clusters} clusters")
        kmeans = KMeans(
            n_clusters=effective_clusters,
            random_state=42,
            n_init=10
        )
        cluster_labels = kmeans.fit_predict(embeddings)
        cluster_centers = kmeans.cluster_centers_

        # Calculate silhouette scores for quality metrics (Task 2A.4)
        per_sample_silhouette = None
        if effective_clusters >= 2 and total_emails >= 3:
            try:
                per_sample_silhouette = silhouette_samples(embeddings, cluster_labels)
            except Exception as e:
                logger.warning(f"Could not calculate silhouette scores: {e}")

        logger.debug(f"Clustering complete. Unique labels: {np.unique(cluster_labels)}")

        # Step 3: Build ContentCluster objects (FR-017)
        clusters = []

        for cluster_id in range(effective_clusters):
            # Get emails in this cluster
            cluster_mask = cluster_labels == cluster_id
            cluster_indices = np.where(cluster_mask)[0]
            cluster_size = len(cluster_indices)

            if cluster_size == 0:
                logger.warning(f"Cluster {cluster_id} is empty, skipping")
                continue

            logger.debug(f"Processing cluster {cluster_id} with {cluster_size} emails")

            # Calculate percentage of corpus
            percentage = (cluster_size / total_emails) * 100

            # Get emails in this cluster
            cluster_emails = [corpus.emails[i] for i in cluster_indices]
            email_ids = [email.id for email in cluster_emails]

            # Find 5 representative samples (closest to centroid) (FR-017)
            cluster_embeddings = embeddings[cluster_mask]
            centroid = cluster_centers[cluster_id]

            # Calculate distances to centroid
            distances = cosine_distances(
                cluster_embeddings,
                centroid.reshape(1, -1)
            ).flatten()

            # Get indices of 5 closest samples (or fewer if cluster is small)
            num_samples = min(5, cluster_size)
            closest_indices = np.argsort(distances)[:num_samples]

            # Map back to original corpus indices
            representative_indices = cluster_indices[closest_indices]

            # Build representative samples
            representative_samples = []
            for idx in representative_indices:
                email = corpus.emails[idx]
                sample = RepresentativeSample(
                    subject=email.subject,
                    sender=email.sender_email,
                    body_preview=email.body_text[:200]  # 200 char preview per model
                )
                representative_samples.append(sample)

            # Extract common domains (FR-017)
            domain_counts = Counter(email.sender_domain for email in cluster_emails)
            # Get top 10 domains
            common_domains = domain_counts.most_common(10)

            # Calculate per-cluster quality metrics (Task 2A.4)
            # Silhouette score for this cluster (average of sample silhouettes)
            cluster_silhouette = None
            if per_sample_silhouette is not None:
                cluster_sample_silhouettes = per_sample_silhouette[cluster_mask]
                cluster_silhouette = float(np.mean(cluster_sample_silhouettes))

            # Cohesion score (average intra-cluster distance to centroid)
            cohesion = float(np.mean(distances))

            silhouette_str = f"{cluster_silhouette:.3f}" if cluster_silhouette is not None else "N/A"
            logger.debug(
                f"Cluster {cluster_id}: {cluster_size} emails, "
                f"{percentage:.1f}%, {len(representative_samples)} samples, "
                f"{len(common_domains)} domains, "
                f"silhouette={silhouette_str}, "
                f"cohesion={cohesion:.3f}"
            )

            # Create ContentCluster
            cluster = ContentCluster(
                cluster_id=cluster_id,
                size=cluster_size,
                percentage=percentage,
                representative_samples=representative_samples,
                common_domains=common_domains,
                email_ids=email_ids,
                silhouette_score=cluster_silhouette,
                cohesion_score=cohesion
            )
            clusters.append(cluster)

        logger.info(f"Semantic analysis complete. Generated {len(clusters)} clusters")

        return clusters

    def analyze_incremental(
        self,
        corpus: Corpus,
        embedding_cache: "EmbeddingCache",
        num_clusters: int = 10,
        auto_clusters: bool = False,
        cluster_method: str = "silhouette",
        progress_callback: Callable[[int, int], None] | None = None
    ) -> IncrementalAnalysisResult:
        """
        Perform incremental semantic clustering using cached embeddings.

        Task 4B.4: Only generates embeddings for new emails, uses cache for existing.

        Args:
            corpus: Email corpus to analyze
            embedding_cache: EmbeddingCache instance to use for caching
            num_clusters: Number of clusters (default 10)
            auto_clusters: If True, automatically determine optimal k
            cluster_method: Method for auto-clustering: "elbow" or "silhouette"
            progress_callback: Optional callback(current, total)

        Returns:
            IncrementalAnalysisResult with clusters and statistics
        """
        if not corpus.emails:
            raise ValueError("Cannot analyze empty corpus")

        if num_clusters < 1:
            raise ValueError(f"num_clusters must be >= 1, got {num_clusters}")

        total_emails = len(corpus.emails)

        # Get email IDs
        email_ids = [email.id for email in corpus.emails]

        # Partition into cached and uncached
        cached_ids, uncached_ids = embedding_cache.partition_ids(email_ids)

        logger.info(
            f"Incremental analysis: {len(cached_ids)} cached, "
            f"{len(uncached_ids)} new embeddings needed"
        )

        # Build full embedding matrix in corpus order
        embeddings_list = []
        id_to_email = {email.id: email for email in corpus.emails}

        # Generate embeddings for uncached emails only
        if uncached_ids:
            self._ensure_model_loaded()

            uncached_texts = [
                id_to_email[email_id].combined_text_with_limit(
                    self.max_embedding_text_length
                )
                for email_id in uncached_ids
            ]

            logger.info(f"Generating {len(uncached_texts)} new embeddings")

            if progress_callback:
                progress_callback(0, len(uncached_texts))

            new_embeddings = self.model.encode(
                uncached_texts,
                show_progress_bar=True,
                convert_to_numpy=True
            )

            if progress_callback:
                progress_callback(len(uncached_texts), len(uncached_texts))

            # Add new embeddings to cache
            embedding_cache.add(uncached_ids, new_embeddings)

            logger.info(f"Added {len(uncached_ids)} embeddings to cache")

        # Build full embedding matrix in corpus order
        for email_id in email_ids:
            embedding = embedding_cache.get(email_id)
            if embedding is not None:
                embeddings_list.append(embedding)
            else:
                # Should not happen after above, but handle gracefully
                logger.warning(f"Missing embedding for {email_id}")
                # Generate on-the-fly
                self._ensure_model_loaded()
                text = id_to_email[email_id].combined_text_with_limit(
                    self.max_embedding_text_length
                )
                embedding = self.model.encode([text], convert_to_numpy=True)[0]
                embeddings_list.append(embedding)

        embeddings = np.array(embeddings_list)

        logger.info(f"Built embedding matrix: {embeddings.shape}")

        # Calculate stats
        stats = {
            "cached_count": len(cached_ids),
            "generated_count": len(uncached_ids),
            "total_emails": total_emails,
            "hit_rate": len(cached_ids) / total_emails if total_emails > 0 else 0.0,
        }

        # Now perform clustering using the combined embeddings
        # (Reuse clustering logic from analyze method)
        effective_clusters = self._determine_clusters(
            embeddings, total_emails, num_clusters, auto_clusters, cluster_method
        )

        clusters = self._perform_clustering(
            corpus, embeddings, effective_clusters
        )

        return IncrementalAnalysisResult(clusters=clusters, stats=stats)

    def _determine_clusters(
        self,
        embeddings: np.ndarray,
        total_emails: int,
        num_clusters: int,
        auto_clusters: bool,
        cluster_method: str
    ) -> int:
        """Determine effective number of clusters."""
        if auto_clusters and total_emails >= 3:
            logger.info(f"Auto-determining optimal clusters using {cluster_method} method...")

            if cluster_method == "elbow":
                optimizer = ElbowOptimizer(max_k=min(15, total_emails - 1))
            else:
                optimizer = SilhouetteOptimizer(max_k=min(15, total_emails - 1))

            optimization_result = optimizer.find_optimal_k(embeddings)
            effective_clusters = optimization_result.optimal_k

            logger.info(
                f"Auto-clustering found optimal k={effective_clusters} "
                f"(confidence: {optimization_result.confidence_score:.2f})"
            )
        else:
            effective_clusters = min(num_clusters, total_emails)
            if effective_clusters < num_clusters:
                logger.warning(
                    f"Corpus has only {total_emails} emails, "
                    f"reducing clusters from {num_clusters} to {effective_clusters}"
                )

        return effective_clusters

    def _perform_clustering(
        self,
        corpus: Corpus,
        embeddings: np.ndarray,
        effective_clusters: int
    ) -> list[ContentCluster]:
        """Perform KMeans clustering and build ContentCluster objects."""
        total_emails = len(corpus.emails)

        logger.info(f"Performing KMeans clustering with {effective_clusters} clusters")
        kmeans = KMeans(
            n_clusters=effective_clusters,
            random_state=42,
            n_init=10
        )
        cluster_labels = kmeans.fit_predict(embeddings)
        cluster_centers = kmeans.cluster_centers_

        # Calculate silhouette scores
        per_sample_silhouette = None
        if effective_clusters >= 2 and total_emails >= 3:
            try:
                per_sample_silhouette = silhouette_samples(embeddings, cluster_labels)
            except Exception as e:
                logger.warning(f"Could not calculate silhouette scores: {e}")

        clusters = []

        for cluster_id in range(effective_clusters):
            cluster_mask = cluster_labels == cluster_id
            cluster_indices = np.where(cluster_mask)[0]
            cluster_size = len(cluster_indices)

            if cluster_size == 0:
                continue

            percentage = (cluster_size / total_emails) * 100
            cluster_emails = [corpus.emails[i] for i in cluster_indices]
            email_ids = [email.id for email in cluster_emails]

            cluster_embeddings = embeddings[cluster_mask]
            centroid = cluster_centers[cluster_id]

            distances = cosine_distances(
                cluster_embeddings, centroid.reshape(1, -1)
            ).flatten()

            num_samples = min(5, cluster_size)
            closest_indices = np.argsort(distances)[:num_samples]
            representative_indices = cluster_indices[closest_indices]

            representative_samples = []
            for idx in representative_indices:
                email = corpus.emails[idx]
                sample = RepresentativeSample(
                    subject=email.subject,
                    sender=email.sender_email,
                    body_preview=email.body_text[:200]
                )
                representative_samples.append(sample)

            domain_counts = Counter(email.sender_domain for email in cluster_emails)
            common_domains = domain_counts.most_common(10)

            cluster_silhouette = None
            if per_sample_silhouette is not None:
                cluster_sample_silhouettes = per_sample_silhouette[cluster_mask]
                cluster_silhouette = float(np.mean(cluster_sample_silhouettes))

            cohesion = float(np.mean(distances))

            cluster = ContentCluster(
                cluster_id=cluster_id,
                size=cluster_size,
                percentage=percentage,
                representative_samples=representative_samples,
                common_domains=common_domains,
                email_ids=email_ids,
                silhouette_score=cluster_silhouette,
                cohesion_score=cohesion
            )
            clusters.append(cluster)

        return clusters
