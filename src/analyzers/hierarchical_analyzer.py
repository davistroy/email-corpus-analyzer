"""
Hierarchical Analyzer module.

Performs hierarchical agglomerative clustering of email corpus to generate
2-level category hierarchy. Uses scipy's hierarchical clustering with ward linkage.

Per Task 4A.2 requirements.
"""
from __future__ import annotations

import logging
from collections import Counter
from collections.abc import Callable
from typing import TYPE_CHECKING

import numpy as np
from pydantic import BaseModel, Field
from scipy.cluster.hierarchy import fcluster, linkage
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_distances

from ..models.content_cluster import RepresentativeSample
from ..models.corpus import Corpus
from .base import BaseAnalyzer

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class HierarchicalCluster(BaseModel):
    """
    Hierarchical cluster data model for 2-level category hierarchy.

    Extends the concept of ContentCluster to support parent-child relationships.
    """

    cluster_id: str = Field(..., min_length=1)
    level: int = Field(..., ge=0, description="0=top-level, 1=subcluster")
    parent_cluster_id: str | None = Field(
        default=None,
        description="ID of parent cluster (None for top-level)"
    )
    size: int = Field(..., ge=1)
    percentage: float = Field(..., ge=0, le=100)
    representative_samples: list[RepresentativeSample] = Field(
        default_factory=list, max_length=5
    )
    common_domains: list[tuple[str, int]] = Field(default_factory=list)
    email_ids: list[str] = Field(default_factory=list)
    subclusters: list[HierarchicalCluster] = Field(default_factory=list)

    @property
    def is_top_level(self) -> bool:
        """Return True if this is a top-level cluster (level 0)."""
        return self.level == 0

    @property
    def has_children(self) -> bool:
        """Return True if this cluster has subclusters."""
        return len(self.subclusters) > 0

    @property
    def children_count(self) -> int:
        """Return the number of direct subclusters."""
        return len(self.subclusters)


class HierarchicalAnalyzer(BaseAnalyzer[list[HierarchicalCluster]]):
    """
    Hierarchical analyzer using agglomerative clustering for email categorization.

    Generates 2-level hierarchy:
    - Level 0: 5-10 broad categories
    - Level 1: 2-5 subcategories per parent

    Uses scipy's hierarchical clustering with ward linkage for optimal merging.
    """

    @property
    def name(self) -> str:
        """Return human-readable analyzer name."""
        return "Hierarchical Analyzer"

    def __init__(
        self,
        model_name: str = "mixedbread-ai/mxbai-embed-large-v1",
        min_top_clusters: int = 5,
        max_top_clusters: int = 10,
        min_subclusters: int = 2,
        max_subclusters: int = 5,
        max_embedding_text_length: int = 1500,
    ):
        """
        Initialize the hierarchical analyzer.

        Args:
            model_name: Hugging Face model identifier for embeddings
            min_top_clusters: Minimum number of top-level clusters (default 5)
            max_top_clusters: Maximum number of top-level clusters (default 10)
            min_subclusters: Minimum subclusters per parent (default 2)
            max_subclusters: Maximum subclusters per parent (default 5)
            max_embedding_text_length: Max body chars for embedding text (default 1500)
        """
        self.model_name = model_name
        self.model = None
        self.min_top_clusters = min_top_clusters
        self.max_top_clusters = max_top_clusters
        self.min_subclusters = min_subclusters
        self.max_subclusters = max_subclusters
        self.max_embedding_text_length = max_embedding_text_length

        # Internal state for fallback
        self._flat_clusters: list[HierarchicalCluster] = []
        self._embeddings: np.ndarray | None = None
        self._corpus: Corpus | None = None

        logger.debug(
            f"HierarchicalAnalyzer initialized "
            f"(top: {min_top_clusters}-{max_top_clusters}, "
            f"sub: {min_subclusters}-{max_subclusters})"
        )

    def _ensure_model_loaded(self) -> None:
        """Lazy load the sentence transformer model."""
        if self.model is None:
            logger.info(f"Loading sentence transformer model: {self.model_name}")
            self.model = SentenceTransformer(self.model_name)
            logger.info(f"Model loaded successfully: {self.model_name}")

    def analyze(
        self,
        corpus: Corpus,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> list[HierarchicalCluster]:
        """
        Perform hierarchical clustering of email corpus.

        Args:
            corpus: Email corpus to analyze
            progress_callback: Optional callback(current, total)

        Returns:
            List of top-level HierarchicalCluster objects with subclusters

        Raises:
            ValueError: If corpus is empty
        """
        if not corpus.emails:
            raise ValueError("Cannot analyze empty corpus")

        total_emails = len(corpus.emails)
        self._corpus = corpus

        logger.info(f"Starting hierarchical analysis of {total_emails} emails")

        # Ensure model is loaded
        self._ensure_model_loaded()

        # Step 1: Generate embeddings
        if progress_callback:
            progress_callback(0, total_emails)

        logger.debug(
            f"Extracting combined text for embeddings "
            f"(max_body_length={self.max_embedding_text_length})"
        )
        texts = [
            email.combined_text_with_limit(self.max_embedding_text_length)
            for email in corpus.emails
        ]

        logger.info("Generating embeddings with sentence transformer")
        self._embeddings = self.model.encode(
            texts,
            show_progress_bar=True,
            convert_to_numpy=True,
        )

        if progress_callback:
            progress_callback(total_emails // 2, total_emails)

        logger.info(f"Generated embeddings with shape: {self._embeddings.shape}")

        # Handle edge cases
        if total_emails == 1:
            return self._create_single_cluster(corpus, self._embeddings)

        if total_emails < 10:
            # Too few for meaningful hierarchy, use flat clustering
            return self._create_flat_clusters(
                corpus, self._embeddings, min(3, total_emails)
            )

        # Step 2: Build hierarchical clustering
        logger.debug("Building hierarchical clustering with ward linkage")
        linkage_matrix = linkage(self._embeddings, method="ward")

        # Step 3: Determine optimal cut point for top-level clusters
        target_top_clusters = min(
            max(self.min_top_clusters, total_emails // 20),
            self.max_top_clusters,
        )
        target_top_clusters = min(target_top_clusters, total_emails - 1)

        logger.debug(f"Target top-level clusters: {target_top_clusters}")

        top_level_cut = self._select_optimal_cut_point(
            linkage_matrix, target_top_clusters
        )
        top_labels = fcluster(linkage_matrix, top_level_cut, criterion="distance")

        # Step 4: Create top-level clusters
        top_clusters = self._build_clusters_from_labels(
            corpus, self._embeddings, top_labels, level=0
        )

        # Step 5: Generate subclusters for each top-level cluster
        for cluster in top_clusters:
            if cluster.size >= 5:  # Only create subclusters for larger clusters
                cluster.subclusters = self._generate_subclusters(
                    cluster,
                    corpus,
                    self._embeddings,
                )

        # Store flat version for fallback
        self._flat_clusters = self._flatten_hierarchy(top_clusters)

        if progress_callback:
            progress_callback(total_emails, total_emails)

        logger.info(
            f"Hierarchical analysis complete. "
            f"Generated {len(top_clusters)} top-level clusters"
        )

        return top_clusters

    def _select_optimal_cut_point(
        self,
        linkage_matrix: np.ndarray,
        target_clusters: int,
    ) -> float:
        """
        Select optimal cut point in dendrogram for target number of clusters.

        Uses distance-based approach to find cut point that yields approximately
        the target number of clusters.

        Args:
            linkage_matrix: scipy linkage matrix
            target_clusters: Desired number of clusters

        Returns:
            Distance threshold for cutting dendrogram
        """
        # Get distances from linkage matrix (3rd column)
        distances = linkage_matrix[:, 2]

        if len(distances) == 0:
            return 1.0

        # Binary search for distance that gives target clusters
        min_dist = distances.min()
        max_dist = distances.max()

        # Use distance that would give approximately target clusters
        # Work backwards from dendrogram structure
        linkage_matrix.shape[0] + 1

        # Find distance that gives closest to target clusters
        best_distance = max_dist / 2
        best_diff = float("inf")

        for distance in np.linspace(min_dist, max_dist, 50):
            labels = fcluster(linkage_matrix, distance, criterion="distance")
            n_clusters = len(np.unique(labels))
            diff = abs(n_clusters - target_clusters)

            if diff < best_diff:
                best_diff = diff
                best_distance = distance

            if diff == 0:
                break

        return best_distance

    def _build_clusters_from_labels(
        self,
        corpus: Corpus,
        embeddings: np.ndarray,
        labels: np.ndarray,
        level: int,
        parent_id: str | None = None,
    ) -> list[HierarchicalCluster]:
        """
        Build HierarchicalCluster objects from cluster labels.

        Args:
            corpus: Email corpus
            embeddings: Email embeddings
            labels: Cluster labels for each email
            level: Hierarchy level (0=top, 1=sub)
            parent_id: Parent cluster ID for subclusters

        Returns:
            List of HierarchicalCluster objects
        """
        clusters = []
        total_emails = len(corpus.emails)
        unique_labels = np.unique(labels)

        for label_idx, cluster_label in enumerate(unique_labels):
            # Get emails in this cluster
            cluster_mask = labels == cluster_label
            cluster_indices = np.where(cluster_mask)[0]
            cluster_size = len(cluster_indices)

            if cluster_size == 0:
                continue

            # Generate cluster ID
            cluster_id = f"cluster_{label_idx}" if level == 0 else f"{parent_id}_{label_idx}"

            # Calculate percentage
            percentage = (cluster_size / total_emails) * 100

            # Get emails in cluster
            cluster_emails = [corpus.emails[i] for i in cluster_indices]
            email_ids = [email.id for email in cluster_emails]

            # Find representative samples (closest to centroid)
            cluster_embeddings = embeddings[cluster_mask]
            centroid = cluster_embeddings.mean(axis=0)
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
                    body_preview=email.body_text[:200],
                )
                representative_samples.append(sample)

            # Extract common domains
            domain_counts = Counter(email.sender_domain for email in cluster_emails)
            common_domains = domain_counts.most_common(10)

            cluster = HierarchicalCluster(
                cluster_id=cluster_id,
                level=level,
                parent_cluster_id=parent_id,
                size=cluster_size,
                percentage=percentage,
                representative_samples=representative_samples,
                common_domains=common_domains,
                email_ids=email_ids,
                subclusters=[],
            )
            clusters.append(cluster)

        return clusters

    def _generate_subclusters(
        self,
        parent_cluster: HierarchicalCluster,
        corpus: Corpus,
        embeddings: np.ndarray,
    ) -> list[HierarchicalCluster]:
        """
        Generate subclusters for a parent cluster.

        Args:
            parent_cluster: Parent cluster to subdivide
            corpus: Full email corpus
            embeddings: Full embedding matrix

        Returns:
            List of subcluster HierarchicalCluster objects
        """
        # Get indices of emails in parent cluster
        parent_indices = [
            i for i, email in enumerate(corpus.emails)
            if email.id in parent_cluster.email_ids
        ]

        if len(parent_indices) < self.min_subclusters * 2:
            # Not enough emails for meaningful subclusters
            return []

        # Extract embeddings for parent cluster
        parent_embeddings = embeddings[parent_indices]

        # Determine target subclusters
        target_subclusters = min(
            max(self.min_subclusters, len(parent_indices) // 10),
            self.max_subclusters,
        )
        target_subclusters = min(target_subclusters, len(parent_indices) - 1)

        if target_subclusters < 2:
            return []

        # Build sub-hierarchy
        try:
            sub_linkage = linkage(parent_embeddings, method="ward")
            sub_cut = self._select_optimal_cut_point(sub_linkage, target_subclusters)
            sub_labels = fcluster(sub_linkage, sub_cut, criterion="distance")
        except Exception as e:
            logger.warning(f"Could not generate subclusters: {e}")
            return []

        # Map back to original indices for building clusters
        # Create a mini-corpus with just the parent cluster emails
        parent_emails = [corpus.emails[i] for i in parent_indices]
        from ..models.corpus import Corpus, CorpusMetadata
        mini_corpus = Corpus(
            extraction_metadata=CorpusMetadata(
                extraction_date=corpus.extraction_metadata.extraction_date,
                total_emails=len(parent_emails),
                source=corpus.extraction_metadata.source,
                user_email=corpus.extraction_metadata.user_email,
            ),
            emails=parent_emails,
        )

        subclusters = self._build_clusters_from_labels(
            mini_corpus,
            parent_embeddings,
            sub_labels,
            level=1,
            parent_id=parent_cluster.cluster_id,
        )

        # Update percentages to be relative to parent
        for subcluster in subclusters:
            subcluster.percentage = (
                subcluster.size / parent_cluster.size
            ) * parent_cluster.percentage

        return subclusters

    def _create_single_cluster(
        self,
        corpus: Corpus,
        embeddings: np.ndarray,
    ) -> list[HierarchicalCluster]:
        """Create a single cluster for single-email corpus."""
        email = corpus.emails[0]

        sample = RepresentativeSample(
            subject=email.subject,
            sender=email.sender_email,
            body_preview=email.body_text[:200],
        )

        cluster = HierarchicalCluster(
            cluster_id="cluster_0",
            level=0,
            parent_cluster_id=None,
            size=1,
            percentage=100.0,
            representative_samples=[sample],
            common_domains=[(email.sender_domain, 1)],
            email_ids=[email.id],
            subclusters=[],
        )

        self._flat_clusters = [cluster]
        return [cluster]

    def _create_flat_clusters(
        self,
        corpus: Corpus,
        embeddings: np.ndarray,
        num_clusters: int,
    ) -> list[HierarchicalCluster]:
        """Create flat clusters without hierarchy for small corpora."""
        if num_clusters >= len(corpus.emails):
            # One cluster per email
            labels = np.arange(len(corpus.emails))
        else:
            # Use hierarchical clustering to get flat labels
            linkage_matrix = linkage(embeddings, method="ward")
            cut_distance = self._select_optimal_cut_point(linkage_matrix, num_clusters)
            labels = fcluster(linkage_matrix, cut_distance, criterion="distance")

        clusters = self._build_clusters_from_labels(
            corpus, embeddings, labels, level=0
        )

        self._flat_clusters = clusters
        return clusters

    def _flatten_hierarchy(
        self,
        clusters: list[HierarchicalCluster],
    ) -> list[HierarchicalCluster]:
        """Flatten hierarchical clusters to single level."""
        flat = []
        for cluster in clusters:
            # Create a copy without subclusters
            flat_cluster = HierarchicalCluster(
                cluster_id=cluster.cluster_id,
                level=0,
                parent_cluster_id=None,
                size=cluster.size,
                percentage=cluster.percentage,
                representative_samples=cluster.representative_samples,
                common_domains=cluster.common_domains,
                email_ids=cluster.email_ids,
                subclusters=[],
            )
            flat.append(flat_cluster)
        return flat

    def get_flat_clusters(self) -> list[HierarchicalCluster]:
        """
        Get flat version of clusters (without hierarchy).

        Returns:
            List of flat clusters (all level 0, no subclusters)
        """
        return self._flat_clusters
