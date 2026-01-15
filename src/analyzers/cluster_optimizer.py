"""
Cluster Optimizer module.

Provides methods to automatically determine optimal number of clusters (k)
using elbow method and silhouette analysis.

Per Phase 2, Track 2A requirements.
"""
import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field

import numpy as np
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score, silhouette_samples

logger = logging.getLogger(__name__)


@dataclass
class ClusterOptimizationResult:
    """Result from cluster optimization analysis."""

    optimal_k: int
    confidence_score: float
    method: str
    k_scores: dict[int, float]
    per_cluster_scores: dict[int, float] | None = None


class ElbowOptimizer:
    """
    Finds optimal number of clusters using the elbow method.

    The elbow method looks at the inertia (within-cluster sum of squares)
    for different values of k and identifies the "elbow" point where
    adding more clusters provides diminishing returns.
    """

    def __init__(self, max_k: int = 15):
        """
        Initialize ElbowOptimizer.

        Args:
            max_k: Maximum number of clusters to evaluate
        """
        self.max_k = max_k
        logger.debug(f"ElbowOptimizer initialized with max_k={max_k}")

    def find_optimal_k(
        self,
        embeddings: np.ndarray,
        progress_callback: Callable[[int, int], None] | None = None
    ) -> ClusterOptimizationResult:
        """
        Find optimal k using elbow method.

        Args:
            embeddings: Numpy array of shape (n_samples, n_features)
            progress_callback: Optional callback(current, total) for progress updates

        Returns:
            ClusterOptimizationResult with optimal k and confidence score

        Raises:
            ValueError: If embeddings has fewer than 3 samples
        """
        n_samples = embeddings.shape[0]

        if n_samples < 3:
            raise ValueError("Embeddings must have at least 3 samples for clustering")

        # Determine k range
        # max_k cannot exceed n_samples - 1
        actual_max_k = min(self.max_k, n_samples - 1)
        k_values = list(range(2, actual_max_k + 1))

        if not k_values:
            k_values = [2]

        total_iterations = len(k_values)
        logger.info(f"Evaluating k values from 2 to {actual_max_k}")

        # Calculate inertia for each k
        inertias = []
        for i, k in enumerate(k_values):
            kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
            kmeans.fit(embeddings)
            inertias.append(kmeans.inertia_)

            if progress_callback:
                progress_callback(i + 1, total_iterations)

            logger.debug(f"k={k}, inertia={kmeans.inertia_:.2f}")

        # Detect elbow point
        optimal_k = self._detect_elbow(k_values, inertias)

        # Calculate confidence score
        confidence = self._calculate_confidence(k_values, inertias, optimal_k)

        # Build k_scores dictionary
        k_scores = dict(zip(k_values, inertias))

        logger.info(f"Elbow method found optimal k={optimal_k} with confidence={confidence:.2f}")

        return ClusterOptimizationResult(
            optimal_k=optimal_k,
            confidence_score=confidence,
            method="elbow",
            k_scores=k_scores
        )

    def _detect_elbow(self, k_values: list[int], inertias: list[float]) -> int:
        """
        Detect the elbow point in the inertia curve using the kneedle algorithm.

        The elbow is the point of maximum curvature, calculated as the point
        furthest from the line connecting the first and last points.

        Args:
            k_values: List of k values tested
            inertias: Corresponding inertia values

        Returns:
            The k value at the elbow point
        """
        if len(k_values) <= 2:
            return k_values[0]

        # Normalize to [0, 1] range for both axes
        k_norm = np.array(k_values, dtype=float)
        inertia_norm = np.array(inertias, dtype=float)

        k_min, k_max = k_norm.min(), k_norm.max()
        inertia_min, inertia_max = inertia_norm.min(), inertia_norm.max()

        if k_max - k_min > 0:
            k_norm = (k_norm - k_min) / (k_max - k_min)
        else:
            k_norm = np.zeros_like(k_norm)

        if inertia_max - inertia_min > 0:
            inertia_norm = (inertia_norm - inertia_min) / (inertia_max - inertia_min)
        else:
            inertia_norm = np.zeros_like(inertia_norm)

        # Line from first to last point
        line_start = np.array([k_norm[0], inertia_norm[0]])
        line_end = np.array([k_norm[-1], inertia_norm[-1]])
        line_vec = line_end - line_start
        line_len = np.linalg.norm(line_vec)

        if line_len == 0:
            return k_values[0]

        line_unit = line_vec / line_len

        # Calculate perpendicular distance from each point to the line
        distances = []
        for i in range(len(k_values)):
            point = np.array([k_norm[i], inertia_norm[i]])
            vec = point - line_start
            # Distance to line = |cross product| / |line length|
            # In 2D: cross product z-component = vec_x * line_y - vec_y * line_x
            cross = abs(vec[0] * line_vec[1] - vec[1] * line_vec[0])
            distance = cross / line_len
            distances.append(distance)

        # Find the point with maximum distance (the elbow)
        max_idx = np.argmax(distances)

        return k_values[max_idx]

    def _calculate_confidence(
        self,
        k_values: list[int],
        inertias: list[float],
        elbow_k: int
    ) -> float:
        """
        Calculate confidence score for the detected elbow point.

        Confidence is based on:
        1. How pronounced the elbow is (curvature at the elbow point)
        2. How much inertia reduction happens at the elbow

        Args:
            k_values: List of k values tested
            inertias: Corresponding inertia values
            elbow_k: The detected elbow point

        Returns:
            Confidence score between 0 and 1
        """
        if len(k_values) <= 2:
            return 0.5

        # Find elbow index
        try:
            elbow_idx = k_values.index(elbow_k)
        except ValueError:
            return 0.5

        # Calculate the "sharpness" of the elbow
        # This is based on the change in slope before and after the elbow

        if elbow_idx == 0 or elbow_idx >= len(k_values) - 1:
            return 0.3

        # Slope before elbow
        slope_before = (inertias[elbow_idx] - inertias[elbow_idx - 1]) / 1.0

        # Slope after elbow
        slope_after = (inertias[elbow_idx + 1] - inertias[elbow_idx]) / 1.0

        # Both slopes should be negative for decreasing inertia
        # A clear elbow has a much steeper slope before than after
        if slope_before < 0 and slope_after < 0:
            # Calculate ratio of slope change
            slope_ratio = abs(slope_before) / (abs(slope_after) + 1e-10)
            # Normalize to [0, 1]
            confidence = min(1.0, slope_ratio / 10.0)
        else:
            confidence = 0.3

        # Also consider the overall reduction in inertia
        total_reduction = (inertias[0] - inertias[-1]) / (inertias[0] + 1e-10)
        reduction_at_elbow = (inertias[0] - inertias[elbow_idx]) / (inertias[0] + 1e-10)

        # If most reduction happens before elbow, it's a good elbow
        elbow_quality = reduction_at_elbow / (total_reduction + 1e-10) if total_reduction > 0 else 0.5

        # Combine factors
        final_confidence = (confidence + elbow_quality) / 2.0

        return max(0.0, min(1.0, final_confidence))


class SilhouetteOptimizer:
    """
    Finds optimal number of clusters using silhouette analysis.

    The silhouette score measures how similar an object is to its own cluster
    compared to other clusters. A higher silhouette score indicates better
    defined clusters.
    """

    def __init__(self, max_k: int = 15):
        """
        Initialize SilhouetteOptimizer.

        Args:
            max_k: Maximum number of clusters to evaluate
        """
        self.max_k = max_k
        logger.debug(f"SilhouetteOptimizer initialized with max_k={max_k}")

    def find_optimal_k(
        self,
        embeddings: np.ndarray,
        progress_callback: Callable[[int, int], None] | None = None
    ) -> ClusterOptimizationResult:
        """
        Find optimal k using silhouette analysis with parallel evaluation.

        Args:
            embeddings: Numpy array of shape (n_samples, n_features)
            progress_callback: Optional callback(current, total) for progress updates

        Returns:
            ClusterOptimizationResult with optimal k, confidence score,
            and per-cluster silhouette scores

        Raises:
            ValueError: If embeddings has fewer than 3 samples
        """
        n_samples = embeddings.shape[0]

        if n_samples < 3:
            raise ValueError("Embeddings must have at least 3 samples for clustering")

        # Determine k range
        actual_max_k = min(self.max_k, n_samples - 1)
        k_values = list(range(2, actual_max_k + 1))

        if not k_values:
            k_values = [2]

        total_iterations = len(k_values)
        logger.info(f"Evaluating k values from 2 to {actual_max_k} using silhouette analysis")

        # Evaluate silhouette scores in parallel
        k_scores: dict[int, float] = {}
        k_labels: dict[int, np.ndarray] = {}

        def evaluate_k(k: int) -> tuple[int, float, np.ndarray]:
            """Evaluate silhouette score for a given k."""
            kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
            labels = kmeans.fit_predict(embeddings)
            score = silhouette_score(embeddings, labels)
            return k, score, labels

        completed = 0
        with ThreadPoolExecutor() as executor:
            futures = {executor.submit(evaluate_k, k): k for k in k_values}

            for future in as_completed(futures):
                k, score, labels = future.result()
                k_scores[k] = score
                k_labels[k] = labels

                completed += 1
                if progress_callback:
                    progress_callback(completed, total_iterations)

                logger.debug(f"k={k}, silhouette_score={score:.4f}")

        # Find optimal k (highest silhouette score)
        optimal_k = max(k_scores, key=k_scores.get)
        max_score = k_scores[optimal_k]

        # Calculate per-cluster silhouette scores for the optimal k
        optimal_labels = k_labels[optimal_k]
        sample_scores = silhouette_samples(embeddings, optimal_labels)

        per_cluster_scores: dict[int, float] = {}
        for cluster_id in range(optimal_k):
            cluster_mask = optimal_labels == cluster_id
            if np.any(cluster_mask):
                per_cluster_scores[cluster_id] = float(np.mean(sample_scores[cluster_mask]))

        # Calculate confidence based on the maximum silhouette score
        # Silhouette scores range from -1 to 1
        # We normalize to [0, 1] for confidence
        confidence = (max_score + 1.0) / 2.0

        logger.info(
            f"Silhouette method found optimal k={optimal_k} "
            f"with score={max_score:.4f}, confidence={confidence:.2f}"
        )

        return ClusterOptimizationResult(
            optimal_k=optimal_k,
            confidence_score=confidence,
            method="silhouette",
            k_scores=k_scores,
            per_cluster_scores=per_cluster_scores
        )


# Export classes
__all__ = [
    'ClusterOptimizationResult',
    'ElbowOptimizer',
    'SilhouetteOptimizer',
]
