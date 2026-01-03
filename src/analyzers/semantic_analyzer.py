"""
Semantic Analyzer module.

Performs semantic clustering of email corpus using sentence transformers.
Supports both HDBSCAN (automatic cluster detection) and KMeans clustering.
Optionally uses LLM for intelligent cluster naming.

Per analyzer_contract.md lines 153-221 and research.md lines 15-68.
Updated for modernization plan with HDBSCAN and LLM integration.
"""
import asyncio
import logging
from collections import Counter
from collections.abc import Callable
from enum import Enum

import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_distances

from ..models.content_cluster import ContentCluster, RepresentativeSample
from ..models.corpus import Corpus

logger = logging.getLogger(__name__)


class ClusteringMethod(Enum):
    """Supported clustering methods."""
    KMEANS = "kmeans"
    HDBSCAN = "hdbscan"


class SemanticAnalyzer:
    """
    Semantic analyzer using sentence transformers for email clustering.

    Supports:
    - HDBSCAN: Automatic cluster count detection (recommended)
    - KMeans: Fixed cluster count (legacy support)
    - LLM-based cluster naming (optional)

    Per FR-015, FR-016, FR-017 requirements.
    """

    def __init__(
        self,
        model_name: str = "mixedbread-ai/mxbai-embed-large-v1",
        use_llm_naming: bool = False,
        llm_client=None,
    ):
        """
        Initialize with sentence transformer model.

        Args:
            model_name: Hugging Face model identifier for embeddings.
            use_llm_naming: Whether to use LLM for cluster naming.
            llm_client: LLM client for naming. Creates default if None and use_llm_naming=True.
        """
        self.model_name = model_name
        self.model = None
        self.use_llm_naming = use_llm_naming
        self.llm_client = llm_client
        self._namer = None

        logger.debug("SemanticAnalyzer initialized (model will load on first use)")

    def _ensure_model_loaded(self):
        """Lazy load the sentence transformer model."""
        if self.model is None:
            logger.info(f"Loading sentence transformer model: {self.model_name}")
            self.model = SentenceTransformer(self.model_name)
            logger.info(f"Model loaded successfully: {self.model_name}")

    def _get_namer(self):
        """Lazy load the LLM namer."""
        if self._namer is None and self.use_llm_naming:
            from src.llm.namer import ClusterNamer
            self._namer = ClusterNamer(self.llm_client)
        return self._namer

    def analyze(
        self,
        corpus: Corpus,
        num_clusters: int = 10,
        progress_callback: Callable[[int, int], None] | None = None,
        method: ClusteringMethod = ClusteringMethod.HDBSCAN,
        min_cluster_size: int = 10,
    ) -> list[ContentCluster]:
        """
        Perform semantic clustering of email corpus.

        Per FR-015, FR-016, FR-017:
        - Combines subject + first 500 chars of body for embedding
        - Generates embeddings using model.encode() with progress bar
        - Uses HDBSCAN (default) or KMeans for clustering
        - Identifies 5 representative samples per cluster (closest to centroid)
        - Calculates cluster percentage of corpus
        - Extracts common domains for each cluster

        Args:
            corpus: Email corpus to analyze.
            num_clusters: Number of clusters for KMeans (ignored for HDBSCAN).
            progress_callback: Optional callback(current, total).
            method: Clustering method (HDBSCAN or KMEANS).
            min_cluster_size: Minimum cluster size for HDBSCAN.

        Returns:
            List of ContentCluster objects.

        Raises:
            ValueError: If corpus is empty or invalid.
        """
        if not corpus.emails:
            raise ValueError("Cannot analyze empty corpus")

        total_emails = len(corpus.emails)
        logger.info(f"Starting semantic analysis of {total_emails} emails using {method.value}")

        # Ensure model is loaded before analysis
        self._ensure_model_loaded()

        # Step 1: Generate embeddings (FR-015)
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

        # Step 2: Perform clustering
        if method == ClusteringMethod.HDBSCAN:
            cluster_labels, cluster_centers = self._cluster_hdbscan(
                embeddings,
                min_cluster_size=min_cluster_size,
            )
        else:
            cluster_labels, cluster_centers = self._cluster_kmeans(
                embeddings,
                num_clusters=num_clusters,
                corpus_size=total_emails,
            )

        # Step 3: Build ContentCluster objects (FR-017)
        clusters = self._build_clusters(
            corpus=corpus,
            embeddings=embeddings,
            cluster_labels=cluster_labels,
            cluster_centers=cluster_centers,
            total_emails=total_emails,
        )

        # Step 4: Add LLM-based names if enabled
        if self.use_llm_naming and clusters:
            clusters = asyncio.run(self._add_llm_names(clusters))

        logger.info(f"Semantic analysis complete. Generated {len(clusters)} clusters")
        return clusters

    async def analyze_async(
        self,
        corpus: Corpus,
        num_clusters: int = 10,
        progress_callback: Callable[[int, int], None] | None = None,
        method: ClusteringMethod = ClusteringMethod.HDBSCAN,
        min_cluster_size: int = 10,
    ) -> list[ContentCluster]:
        """
        Async version of analyze with proper async LLM naming.

        Use this version when running in an async context.
        """
        if not corpus.emails:
            raise ValueError("Cannot analyze empty corpus")

        total_emails = len(corpus.emails)
        logger.info(f"Starting async semantic analysis of {total_emails} emails")

        # Model loading and embedding generation run in thread pool
        self._ensure_model_loaded()

        texts = [email.combined_text for email in corpus.emails]

        if progress_callback:
            progress_callback(0, total_emails)

        embeddings = await asyncio.to_thread(
            lambda: self.model.encode(texts, show_progress_bar=True, convert_to_numpy=True)
        )

        if progress_callback:
            progress_callback(total_emails, total_emails)

        # Clustering
        if method == ClusteringMethod.HDBSCAN:
            cluster_labels, cluster_centers = await asyncio.to_thread(
                lambda: self._cluster_hdbscan(embeddings, min_cluster_size)
            )
        else:
            cluster_labels, cluster_centers = await asyncio.to_thread(
                lambda: self._cluster_kmeans(embeddings, num_clusters, total_emails)
            )

        # Build clusters
        clusters = self._build_clusters(
            corpus, embeddings, cluster_labels, cluster_centers, total_emails
        )

        # Add LLM names
        if self.use_llm_naming and clusters:
            clusters = await self._add_llm_names(clusters)

        logger.info(f"Async semantic analysis complete. Generated {len(clusters)} clusters")
        return clusters

    def _cluster_hdbscan(
        self,
        embeddings: np.ndarray,
        min_cluster_size: int = 10,
    ) -> tuple[np.ndarray, np.ndarray | None]:
        """
        Perform HDBSCAN clustering.

        HDBSCAN automatically determines the number of clusters
        based on data density. No need to specify cluster count.

        Args:
            embeddings: Email embeddings.
            min_cluster_size: Minimum points to form a cluster.

        Returns:
            Tuple of (cluster_labels, cluster_centers).
            cluster_centers may be None if HDBSCAN is used.
        """
        try:
            import hdbscan
        except ImportError:
            logger.warning("hdbscan not installed, falling back to KMeans")
            return self._cluster_kmeans(embeddings, num_clusters=10, corpus_size=len(embeddings))

        logger.info(f"Performing HDBSCAN clustering (min_cluster_size={min_cluster_size})")

        clusterer = hdbscan.HDBSCAN(
            min_cluster_size=min_cluster_size,
            min_samples=5,
            metric='euclidean',
            cluster_selection_method='eom',
            prediction_data=True,
        )
        cluster_labels = clusterer.fit_predict(embeddings)

        # Get unique clusters (excluding noise labeled as -1)
        unique_labels = set(cluster_labels) - {-1}
        logger.info(f"HDBSCAN found {len(unique_labels)} clusters (plus noise)")

        # Calculate centroids for each cluster
        cluster_centers = []
        for label in sorted(unique_labels):
            mask = cluster_labels == label
            centroid = embeddings[mask].mean(axis=0)
            cluster_centers.append(centroid)

        # Convert noise points to their own "cluster" or assign to nearest
        # For now, we'll leave noise as -1 and handle in _build_clusters

        return cluster_labels, np.array(cluster_centers) if cluster_centers else None

    def _cluster_kmeans(
        self,
        embeddings: np.ndarray,
        num_clusters: int,
        corpus_size: int,
    ) -> tuple[np.ndarray, np.ndarray]:
        """
        Perform KMeans clustering.

        Args:
            embeddings: Email embeddings.
            num_clusters: Target number of clusters.
            corpus_size: Total number of emails.

        Returns:
            Tuple of (cluster_labels, cluster_centers).
        """
        from sklearn.cluster import KMeans

        # Adjust num_clusters if corpus is too small
        effective_clusters = min(num_clusters, corpus_size)
        if effective_clusters < num_clusters:
            logger.warning(
                f"Corpus has only {corpus_size} emails, "
                f"reducing clusters from {num_clusters} to {effective_clusters}"
            )

        logger.info(f"Performing KMeans clustering with {effective_clusters} clusters")
        kmeans = KMeans(
            n_clusters=effective_clusters,
            random_state=42,
            n_init=10,
        )
        cluster_labels = kmeans.fit_predict(embeddings)
        cluster_centers = kmeans.cluster_centers_

        logger.debug(f"KMeans complete. Unique labels: {np.unique(cluster_labels)}")
        return cluster_labels, cluster_centers

    def _build_clusters(
        self,
        corpus: Corpus,
        embeddings: np.ndarray,
        cluster_labels: np.ndarray,
        cluster_centers: np.ndarray | None,
        total_emails: int,
    ) -> list[ContentCluster]:
        """Build ContentCluster objects from clustering results."""
        clusters = []

        # Get unique labels (excluding noise -1 for HDBSCAN)
        unique_labels = sorted(set(cluster_labels) - {-1})

        for cluster_id in unique_labels:
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

            # Find 5 representative samples (closest to centroid)
            cluster_embeddings = embeddings[cluster_mask]

            # Calculate centroid if not provided
            if cluster_centers is not None and cluster_id < len(cluster_centers):
                centroid = cluster_centers[cluster_id]
            else:
                centroid = cluster_embeddings.mean(axis=0)

            # Calculate distances to centroid
            distances = cosine_distances(
                cluster_embeddings,
                centroid.reshape(1, -1)
            ).flatten()

            # Get indices of 5 closest samples
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
                    body_preview=email.body_text[:200]
                )
                representative_samples.append(sample)

            # Extract common domains
            domain_counts = Counter(email.sender_domain for email in cluster_emails)
            common_domains = domain_counts.most_common(10)

            logger.debug(
                f"Cluster {cluster_id}: {cluster_size} emails, "
                f"{percentage:.1f}%, {len(representative_samples)} samples"
            )

            # Create ContentCluster
            cluster = ContentCluster(
                cluster_id=cluster_id,
                size=cluster_size,
                percentage=percentage,
                representative_samples=representative_samples,
                common_domains=common_domains,
                email_ids=email_ids,
            )
            clusters.append(cluster)

        # Handle noise points from HDBSCAN (label -1)
        noise_mask = cluster_labels == -1
        noise_count = noise_mask.sum()
        if noise_count > 0:
            logger.info(f"HDBSCAN identified {noise_count} noise points ({noise_count/total_emails*100:.1f}%)")
            # Optionally create an "Uncategorized" cluster for noise
            # For now, we just log it

        return clusters

    async def _add_llm_names(self, clusters: list[ContentCluster]) -> list[ContentCluster]:
        """Add LLM-generated names to clusters."""
        namer = self._get_namer()
        if not namer:
            return clusters

        logger.info("Generating LLM-based cluster names...")

        for cluster in clusters:
            try:
                name_result = await namer.name_cluster(
                    representative_samples=cluster.representative_samples,
                    common_domains=cluster.common_domains,
                    cluster_size=cluster.size,
                    cluster_percentage=cluster.percentage,
                )

                # Store LLM-generated name in cluster
                # Note: ContentCluster model may need to be extended to store these
                cluster.suggested_name = name_result.name
                cluster.name_confidence = name_result.confidence
                cluster.name_reasoning = name_result.reasoning

                logger.debug(f"Cluster {cluster.cluster_id}: '{name_result.name}' ({name_result.confidence:.2f})")

            except Exception as e:
                logger.warning(f"Failed to generate name for cluster {cluster.cluster_id}: {e}")

        return clusters


# Legacy compatibility function
def analyze_corpus_semantically(
    corpus: Corpus,
    num_clusters: int = 10,
    progress_callback: Callable[[int, int], None] | None = None,
) -> list[ContentCluster]:
    """
    Legacy function for backward compatibility.

    Uses KMeans clustering like the original implementation.
    """
    analyzer = SemanticAnalyzer()
    return analyzer.analyze(
        corpus=corpus,
        num_clusters=num_clusters,
        progress_callback=progress_callback,
        method=ClusteringMethod.KMEANS,
    )
