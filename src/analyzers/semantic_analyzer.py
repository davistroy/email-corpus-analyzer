"""
Semantic Analyzer module.

Performs semantic clustering of email corpus using sentence transformers and KMeans.
Per analyzer_contract.md lines 153-221 and research.md lines 15-68.
"""
import logging
from collections import Counter
from collections.abc import Callable

import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.cluster import KMeans
from sklearn.metrics.pairwise import cosine_distances

from ..models.content_cluster import ContentCluster, RepresentativeSample
from ..models.corpus import Corpus

logger = logging.getLogger(__name__)


class SemanticAnalyzer:
    """
    Semantic analyzer using sentence transformers for email clustering.

    Per FR-015, FR-016, FR-017 requirements.
    """

    def __init__(self, model_name: str = "mixedbread-ai/mxbai-embed-large-v1"):
        """
        Initialize with sentence transformer model.

        Args:
            model_name: Hugging Face model identifier
        """
        self.model_name = model_name
        self.model = None
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

        # Adjust num_clusters if corpus is too small
        effective_clusters = min(num_clusters, len(corpus.emails))
        if effective_clusters < num_clusters:
            logger.warning(
                f"Corpus has only {len(corpus.emails)} emails, "
                f"reducing clusters from {num_clusters} to {effective_clusters}"
            )

        total_emails = len(corpus.emails)
        logger.info(f"Starting semantic analysis of {total_emails} emails into {effective_clusters} clusters")

        # Ensure model is loaded before analysis
        self._ensure_model_loaded()

        # Step 1: Generate embeddings (FR-015)
        # Combine subject + first 500 chars of body using Email.combined_text property
        logger.debug("Extracting combined text for embeddings")
        texts = [email.combined_text for email in corpus.emails]

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

        # Step 2: Perform KMeans clustering (FR-016)
        logger.info(f"Performing KMeans clustering with {effective_clusters} clusters")
        kmeans = KMeans(
            n_clusters=effective_clusters,
            random_state=42,
            n_init=10
        )
        cluster_labels = kmeans.fit_predict(embeddings)
        cluster_centers = kmeans.cluster_centers_

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

            logger.debug(
                f"Cluster {cluster_id}: {cluster_size} emails, "
                f"{percentage:.1f}%, {len(representative_samples)} samples, "
                f"{len(common_domains)} domains"
            )

            # Create ContentCluster
            cluster = ContentCluster(
                cluster_id=cluster_id,
                size=cluster_size,
                percentage=percentage,
                representative_samples=representative_samples,
                common_domains=common_domains,
                email_ids=email_ids
            )
            clusters.append(cluster)

        logger.info(f"Semantic analysis complete. Generated {len(clusters)} clusters")

        return clusters
