"""
Cluster Optimizer module.

Provides methods to automatically determine optimal number of clusters (k)
using elbow method and silhouette analysis.

Per Phase 2, Track 2A requirements.
"""
import logging
import math
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

import numpy as np
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_samples, silhouette_score

from src.utils.constants import SIGMOID_STEEPNESS

from .base import BaseAnalyzer

logger = logging.getLogger(__name__)


def compute_max_k(n_emails: int, min_k: int = 3, max_k_cap: int = 25) -> int:
    """
    Compute a corpus-size-aware maximum k for cluster optimization.

    Uses sqrt(n_emails / 5) as the scaling heuristic, clamped to [min_k, max_k_cap].
    This produces sensible upper bounds across corpus sizes:
      - 50 emails   -> max_k = 3  (min)
      - 100 emails  -> max_k = 4
      - 1,000 emails -> max_k = 14
      - 10,000 emails -> max_k = 25 (capped)

    The result is also clamped to n_emails - 1 (can't have more clusters than samples).

    Args:
        n_emails: Total number of emails in the corpus.
        min_k: Minimum allowed max_k (default 3).
        max_k_cap: Maximum allowed max_k (default 25).

    Returns:
        Integer max_k value clamped to [min_k, max_k_cap] and <= n_emails - 1.

    Raises:
        ValueError: If n_emails < 2 or min_k > max_k_cap.
    """
    if n_emails < 2:
        raise ValueError(f"n_emails must be >= 2, got {n_emails}")
    if min_k > max_k_cap:
        raise ValueError(
            f"min_k ({min_k}) must be <= max_k_cap ({max_k_cap})"
        )

    raw = int(math.sqrt(n_emails / 5))
    clamped = max(min_k, min(raw, max_k_cap))
    # Never exceed n_emails - 1 (KMeans requirement)
    return min(clamped, n_emails - 1)


def silhouette_to_confidence(score: float) -> float:
    """
    Convert a silhouette score to a confidence value using sigmoid normalization.

    Unlike linear normalization ((score + 1) / 2), which maps the full [-1, 1]
    range uniformly to [0, 1], a sigmoid provides better discrimination in the
    useful range: negative scores map to clearly low confidence, while positive
    scores above ~0.5 map to high confidence.

    Mapping examples:
      - score =  0.5 -> confidence ≈ 0.92 (good clustering)
      - score =  0.0 -> confidence = 0.50 (neutral / ambiguous)
      - score = -0.3 -> confidence ≈ 0.18 (clearly bad)

    Args:
        score: Silhouette score in [-1, 1].

    Returns:
        Confidence value in (0, 1).
    """
    return 1.0 / (1.0 + math.exp(-SIGMOID_STEEPNESS * score))


def interpret_silhouette(score: float) -> str:
    """
    Return a human-readable interpretation label for a silhouette score.

    The score is first mapped through sigmoid normalization, then classified:
      - confidence > 0.7:  "strong"
      - 0.4 <= confidence <= 0.7: "moderate"
      - confidence < 0.4:  "weak"

    Args:
        score: Raw silhouette score in [-1, 1].

    Returns:
        One of "strong", "moderate", or "weak".
    """
    confidence = silhouette_to_confidence(score)
    if confidence > 0.7:
        return "strong"
    if confidence >= 0.4:
        return "moderate"
    return "weak"


@dataclass
class ClusterOptimizationResult:
    """Result from cluster optimization analysis."""

    optimal_k: int
    confidence_score: float
    method: str
    k_scores: dict[int, float]
    per_cluster_scores: dict[int, float] | None = None
    interpretation: str | None = None


class ElbowOptimizer(BaseAnalyzer[ClusterOptimizationResult]):
    """
    Finds optimal number of clusters using the elbow method.

    The elbow method looks at the inertia (within-cluster sum of squares)
    for different values of k and identifies the "elbow" point where
    adding more clusters provides diminishing returns.
    """

    @property
    def name(self) -> str:
        """Return human-readable analyzer name."""
        return "Elbow Optimizer"

    def __init__(self, max_k: int = 15):
        """
        Initialize ElbowOptimizer.

        Args:
            max_k: Maximum number of clusters to evaluate
        """
        self.max_k = max_k
        logger.debug(f"ElbowOptimizer initialized with max_k={max_k}")

    def analyze(self, emails, **kwargs) -> ClusterOptimizationResult:
        """
        Analyze embeddings to find optimal cluster count.

        This method wraps find_optimal_k for BaseAnalyzer compatibility.
        The 'emails' parameter should be embeddings (numpy array) in this case.

        Args:
            emails: Embeddings array (not email list for this optimizer)
            **kwargs: Additional arguments including progress_callback

        Returns:
            ClusterOptimizationResult with optimal k and confidence
        """
        embeddings = emails  # For optimizers, we accept embeddings directly
        progress_callback = kwargs.get('progress_callback')
        return self.find_optimal_k(embeddings, progress_callback)

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
        k_scores = dict(zip(k_values, inertias, strict=False))

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

        k_norm = (k_norm - k_min) / (k_max - k_min) if k_max - k_min > 0 else np.zeros_like(k_norm)

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

        line_vec / line_len

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

        This method combines two signals to assess how "clear" the elbow is:

        1. **Slope Ratio** (curvature sharpness):
           Measures how sharply the inertia curve bends at the elbow.
           Calculated as: |slope_before| / |slope_after|
           - High ratio (e.g., 10:1) → steep drop before elbow, gentle decline after → clear elbow
           - Low ratio (e.g., 2:1) → similar slopes before/after → weak elbow
           Normalized to [0, 1] by dividing by 10 and clamping.

        2. **Inertia Reduction** (elbow positioning):
           Measures what percentage of total inertia reduction occurs before the elbow.
           Calculated as: (inertia[0] - inertia[elbow]) / (inertia[0] - inertia[end])
           - High ratio (e.g., 0.8) → 80% of improvement happens by the elbow → good stopping point
           - Low ratio (e.g., 0.3) → most improvement is after elbow → poor stopping point

        The final confidence is the average of these two signals, clamped to [0, 1].

        **Numerical Examples:**

        Example 1 - Clear elbow (k=5):
          k_values:  [2, 3, 4, 5, 6, 7, 8]
          inertias:  [1000, 600, 400, 300, 270, 260, 255]
          slope_before = (300 - 400) / 1.0 = -100
          slope_after  = (270 - 300) / 1.0 = -30
          slope_ratio  = 100 / 30 = 3.33
          confidence1  = min(1.0, 3.33 / 10) = 0.33

          total_reduction = (1000 - 255) / 1000 = 0.745
          reduction_at_elbow = (1000 - 300) / 1000 = 0.700
          elbow_quality = 0.700 / 0.745 = 0.94

          final = (0.33 + 0.94) / 2 = 0.635

        Example 2 - Weak elbow (k=5):
          k_values:  [2, 3, 4, 5, 6, 7, 8]
          inertias:  [1000, 850, 720, 610, 510, 420, 340]
          slope_before = (610 - 720) / 1.0 = -110
          slope_after  = (510 - 610) / 1.0 = -100
          slope_ratio  = 110 / 100 = 1.10
          confidence1  = min(1.0, 1.10 / 10) = 0.11

          total_reduction = (1000 - 340) / 1000 = 0.660
          reduction_at_elbow = (1000 - 610) / 1000 = 0.390
          elbow_quality = 0.390 / 0.660 = 0.59

          final = (0.11 + 0.59) / 2 = 0.35

        Args:
            k_values: List of k values tested (e.g., [2, 3, 4, 5, 6, 7, 8])
            inertias: Corresponding inertia values (decreasing)
            elbow_k: The detected elbow point (from _detect_elbow)

        Returns:
            Confidence score between 0 and 1, where:
            - > 0.7: Clear elbow, high confidence in the recommendation
            - 0.4-0.7: Moderate elbow, reasonable recommendation
            - < 0.4: Weak elbow, low confidence
        """
        # Edge case: not enough data points to calculate slopes
        if len(k_values) <= 2:
            return 0.5

        # Find the index of the elbow point in our k_values list
        try:
            elbow_idx = k_values.index(elbow_k)
        except ValueError:
            return 0.5

        # Edge case: elbow is at the boundary (can't calculate before/after slopes)
        # Return low confidence since we can't assess curvature
        if elbow_idx == 0 or elbow_idx >= len(k_values) - 1:
            return 0.3

        # --- SIGNAL 1: Slope Ratio (measures curvature sharpness) ---

        # Calculate slope of inertia curve before the elbow
        # Negative value indicates decreasing inertia (expected)
        slope_before = (inertias[elbow_idx] - inertias[elbow_idx - 1]) / 1.0

        # Calculate slope of inertia curve after the elbow
        # Should also be negative, but less steep if it's a true elbow
        slope_after = (inertias[elbow_idx + 1] - inertias[elbow_idx]) / 1.0

        # Both slopes should be negative (inertia decreases with more clusters)
        # A clear elbow has a much steeper slope before than after
        if slope_before < 0 and slope_after < 0:
            # Ratio of absolute slopes: higher ratio = sharper bend
            # e.g., |slope_before| = 100, |slope_after| = 10 → ratio = 10 (sharp elbow)
            #       |slope_before| = 100, |slope_after| = 80 → ratio = 1.25 (gentle bend)
            slope_ratio = abs(slope_before) / (abs(slope_after) + 1e-10)

            # Normalize to [0, 1] by dividing by 10 (assumes ratio of 10 is "perfect")
            # Ratios > 10 are clamped to 1.0
            confidence = min(1.0, slope_ratio / 10.0)
        else:
            # Slopes have wrong sign (shouldn't happen with valid inertia curve)
            # Return low confidence
            confidence = 0.3

        # --- SIGNAL 2: Inertia Reduction (measures elbow positioning) ---

        # Calculate total inertia reduction from k=2 to k=max
        # This is the total improvement available
        total_reduction = (inertias[0] - inertias[-1]) / (inertias[0] + 1e-10)

        # Calculate inertia reduction from k=2 to the elbow point
        # This is how much improvement we've captured by the elbow
        reduction_at_elbow = (inertias[0] - inertias[elbow_idx]) / (inertias[0] + 1e-10)

        # If most reduction happens before the elbow, it's a good stopping point
        # e.g., reduction_at_elbow=0.7, total_reduction=0.8 → quality=0.875 (good!)
        #       reduction_at_elbow=0.3, total_reduction=0.8 → quality=0.375 (poor)
        elbow_quality = reduction_at_elbow / (total_reduction + 1e-10) if total_reduction > 0 else 0.5

        # --- COMBINE SIGNALS ---

        # Average the two signals: curvature sharpness + positioning quality
        final_confidence = (confidence + elbow_quality) / 2.0

        # Clamp to [0, 1] range (should already be in range, but defensive)
        return max(0.0, min(1.0, final_confidence))


class SilhouetteOptimizer(BaseAnalyzer[ClusterOptimizationResult]):
    """
    Finds optimal number of clusters using silhouette analysis.

    The silhouette score measures how similar an object is to its own cluster
    compared to other clusters. A higher silhouette score indicates better
    defined clusters.
    """

    @property
    def name(self) -> str:
        """Return human-readable analyzer name."""
        return "Silhouette Optimizer"

    def __init__(self, max_k: int = 15):
        """
        Initialize SilhouetteOptimizer.

        Args:
            max_k: Maximum number of clusters to evaluate
        """
        self.max_k = max_k
        logger.debug(f"SilhouetteOptimizer initialized with max_k={max_k}")

    def analyze(self, emails, **kwargs) -> ClusterOptimizationResult:
        """
        Analyze embeddings to find optimal cluster count.

        This method wraps find_optimal_k for BaseAnalyzer compatibility.
        The 'emails' parameter should be embeddings (numpy array) in this case.

        Args:
            emails: Embeddings array (not email list for this optimizer)
            **kwargs: Additional arguments including progress_callback

        Returns:
            ClusterOptimizationResult with optimal k and confidence
        """
        embeddings = emails  # For optimizers, we accept embeddings directly
        progress_callback = kwargs.get('progress_callback')
        return self.find_optimal_k(embeddings, progress_callback)

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
        with ThreadPoolExecutor(max_workers=min(4, len(k_values))) as executor:
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

        # Calculate confidence using sigmoid normalization of the silhouette score.
        # Sigmoid provides better discrimination than linear: negative scores map
        # to clearly low confidence, scores above ~0.5 map to high confidence.
        confidence = silhouette_to_confidence(max_score)
        interpretation = interpret_silhouette(max_score)

        logger.info(
            f"Silhouette method found optimal k={optimal_k} "
            f"with score={max_score:.4f}, confidence={confidence:.2f} "
            f"({interpretation})"
        )

        return ClusterOptimizationResult(
            optimal_k=optimal_k,
            confidence_score=confidence,
            method="silhouette",
            k_scores=k_scores,
            per_cluster_scores=per_cluster_scores,
            interpretation=interpretation,
        )


# Export classes and functions
__all__ = [
    'ClusterOptimizationResult',
    'ElbowOptimizer',
    'SilhouetteOptimizer',
    'compute_max_k',
    'interpret_silhouette',
    'silhouette_to_confidence',
]
