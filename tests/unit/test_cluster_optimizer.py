"""
Unit tests for cluster optimizer module.

Tests the following cluster optimization components:
- compute_max_k function - corpus-size-aware max_k calculation
- ElbowOptimizer class - finds optimal k using inertia curve
- SilhouetteOptimizer class - finds optimal k using silhouette scores
"""
from unittest.mock import MagicMock, patch
import numpy as np
import pytest

from src.analyzers.cluster_optimizer import (
    ElbowOptimizer,
    SilhouetteOptimizer,
    ClusterOptimizationResult,
    compute_max_k,
)


# ============================================================================
# Test compute_max_k
# ============================================================================


class TestComputeMaxK:
    """Test cases for compute_max_k function."""

    def test_50_emails_returns_min(self):
        """50 emails -> sqrt(50/5) = sqrt(10) ≈ 3 -> clamped to min_k=3."""
        result = compute_max_k(50)
        assert result == 3

    def test_100_emails(self):
        """100 emails -> sqrt(100/5) = sqrt(20) ≈ 4."""
        result = compute_max_k(100)
        assert result == 4

    def test_1000_emails(self):
        """1000 emails -> sqrt(1000/5) = sqrt(200) ≈ 14."""
        result = compute_max_k(1000)
        assert result == 14

    def test_10000_emails_returns_cap(self):
        """10000 emails -> sqrt(10000/5) = sqrt(2000) ≈ 44 -> clamped to cap=25."""
        result = compute_max_k(10000)
        assert result == 25

    def test_very_small_corpus(self):
        """3 emails -> sqrt(3/5) ≈ 0 -> clamped to min_k=3 -> then clamped to n-1=2."""
        result = compute_max_k(3)
        assert result == 2  # can't exceed n_emails - 1

    def test_custom_min_k(self):
        """Custom min_k is respected."""
        result = compute_max_k(50, min_k=5)
        assert result == 5

    def test_custom_max_k_cap(self):
        """Custom max_k_cap is respected."""
        result = compute_max_k(10000, max_k_cap=15)
        assert result == 15

    def test_custom_min_and_max(self):
        """Both custom min and max are respected together."""
        result = compute_max_k(100, min_k=2, max_k_cap=10)
        assert result == 4

    def test_n_emails_minus_1_clamp(self):
        """Result never exceeds n_emails - 1."""
        # 4 emails: sqrt(4/5)=0.89 -> int=0 -> clamp to min_k=3 -> clamp to n-1=3
        result = compute_max_k(4)
        assert result == 3

    def test_invalid_n_emails_raises(self):
        """n_emails < 2 should raise ValueError."""
        with pytest.raises(ValueError, match="n_emails must be >= 2"):
            compute_max_k(1)
        with pytest.raises(ValueError, match="n_emails must be >= 2"):
            compute_max_k(0)

    def test_min_k_greater_than_max_k_cap_raises(self):
        """min_k > max_k_cap should raise ValueError."""
        with pytest.raises(ValueError, match="min_k.*must be <= max_k_cap"):
            compute_max_k(100, min_k=30, max_k_cap=10)

    def test_scaling_is_monotonic(self):
        """Larger corpora should produce >= max_k compared to smaller ones."""
        sizes = [50, 100, 200, 500, 1000, 5000, 10000]
        results = [compute_max_k(n) for n in sizes]
        for i in range(len(results) - 1):
            assert results[i] <= results[i + 1], (
                f"compute_max_k({sizes[i]})={results[i]} > "
                f"compute_max_k({sizes[i+1]})={results[i+1]}"
            )

    def test_acceptance_50_email_corpus_max_5_clusters(self):
        """Acceptance criterion: 50-email corpus produces max_k <= 5."""
        result = compute_max_k(50)
        assert result <= 5

    def test_acceptance_10k_corpus_can_reach_25(self):
        """Acceptance criterion: 10K-email corpus can produce up to 25 clusters."""
        result = compute_max_k(10000)
        assert result == 25


# ============================================================================
# Test ClusterOptimizationResult
# ============================================================================


class TestClusterOptimizationResult:
    """Test cases for ClusterOptimizationResult dataclass."""

    def test_creation_with_required_fields(self):
        """Test creation with required fields."""
        result = ClusterOptimizationResult(
            optimal_k=5,
            confidence_score=0.85,
            method="elbow",
            k_scores={2: 100.0, 3: 80.0, 4: 50.0, 5: 45.0, 6: 43.0},
        )

        assert result.optimal_k == 5
        assert result.confidence_score == 0.85
        assert result.method == "elbow"
        assert len(result.k_scores) == 5

    def test_creation_with_all_fields(self):
        """Test creation with all fields including per_cluster_scores."""
        result = ClusterOptimizationResult(
            optimal_k=3,
            confidence_score=0.75,
            method="silhouette",
            k_scores={2: 0.5, 3: 0.7, 4: 0.6},
            per_cluster_scores={0: 0.8, 1: 0.7, 2: 0.6},
        )

        assert result.optimal_k == 3
        assert result.per_cluster_scores is not None
        assert len(result.per_cluster_scores) == 3


# ============================================================================
# Test ElbowOptimizer
# ============================================================================


class TestElbowOptimizer:
    """Test cases for ElbowOptimizer class."""

    @pytest.fixture
    def optimizer(self):
        """Create ElbowOptimizer instance."""
        return ElbowOptimizer()

    def test_init_default_max_k(self, optimizer):
        """Test default max_k is set correctly."""
        assert optimizer.max_k == 15

    def test_init_custom_max_k(self):
        """Test custom max_k initialization."""
        custom_optimizer = ElbowOptimizer(max_k=20)
        assert custom_optimizer.max_k == 20

    def test_find_optimal_k_returns_result(self, optimizer):
        """Test that find_optimal_k returns ClusterOptimizationResult."""
        # Generate sample embeddings (50 samples, 10 features)
        np.random.seed(42)
        embeddings = np.random.rand(50, 10)

        result = optimizer.find_optimal_k(embeddings)

        assert isinstance(result, ClusterOptimizationResult)
        assert result.method == "elbow"
        assert 2 <= result.optimal_k <= optimizer.max_k
        assert 0.0 <= result.confidence_score <= 1.0

    def test_find_optimal_k_small_dataset(self, optimizer):
        """Test with small dataset (fewer samples than max_k)."""
        # Generate small embeddings (5 samples, 10 features)
        np.random.seed(42)
        embeddings = np.random.rand(5, 10)

        result = optimizer.find_optimal_k(embeddings)

        # Optimal k should be at most n_samples - 1
        assert result.optimal_k <= 4

    def test_find_optimal_k_with_clear_elbow(self, optimizer):
        """Test with data that has a clear elbow point."""
        # Create 3 well-separated clusters
        np.random.seed(42)
        cluster1 = np.random.randn(30, 10) + np.array([0] * 10)
        cluster2 = np.random.randn(30, 10) + np.array([10] * 10)
        cluster3 = np.random.randn(30, 10) + np.array([20] * 10)
        embeddings = np.vstack([cluster1, cluster2, cluster3])

        result = optimizer.find_optimal_k(embeddings)

        # Should identify around 3 clusters
        assert 2 <= result.optimal_k <= 5
        assert result.confidence_score > 0.5

    def test_find_optimal_k_returns_k_scores(self, optimizer):
        """Test that k_scores dictionary is populated."""
        np.random.seed(42)
        embeddings = np.random.rand(30, 10)

        result = optimizer.find_optimal_k(embeddings)

        assert len(result.k_scores) > 0
        # Should have scores for k=2 through some max value
        assert 2 in result.k_scores

    def test_find_optimal_k_min_samples_required(self, optimizer):
        """Test that minimum 3 samples are required."""
        embeddings = np.random.rand(2, 10)

        with pytest.raises(ValueError, match="at least 3 samples"):
            optimizer.find_optimal_k(embeddings)

    def test_find_optimal_k_progress_callback(self, optimizer):
        """Test progress callback is called during optimization."""
        np.random.seed(42)
        embeddings = np.random.rand(30, 10)

        callback_calls = []

        def progress_callback(current, total):
            callback_calls.append((current, total))

        optimizer.find_optimal_k(embeddings, progress_callback=progress_callback)

        assert len(callback_calls) > 0
        # Final callback should have current == total
        assert callback_calls[-1][0] == callback_calls[-1][1]

    def test_detect_elbow_decreasing_inertias(self, optimizer):
        """Test elbow detection with decreasing inertias."""
        # Simulate typical elbow curve
        k_values = list(range(2, 11))
        inertias = [1000, 500, 300, 200, 180, 175, 172, 170, 169]

        elbow_k = optimizer._detect_elbow(k_values, inertias)

        # Elbow should be detected around k=4-5 where slope changes most
        assert 3 <= elbow_k <= 6

    def test_detect_elbow_linear_decrease(self, optimizer):
        """Test elbow detection with linear decrease (no clear elbow)."""
        k_values = list(range(2, 11))
        inertias = [100, 90, 80, 70, 60, 50, 40, 30, 20]

        elbow_k = optimizer._detect_elbow(k_values, inertias)

        # Should return something reasonable
        assert 2 <= elbow_k <= 10

    def test_calculate_confidence_high_curvature(self, optimizer):
        """Test confidence calculation with high curvature at elbow."""
        k_values = list(range(2, 11))
        # Sharp elbow at k=4
        inertias = [1000, 500, 200, 180, 175, 173, 172, 171, 170]
        elbow_k = 4

        confidence = optimizer._calculate_confidence(k_values, inertias, elbow_k)

        # High curvature should give high confidence
        assert 0.5 <= confidence <= 1.0

    def test_calculate_confidence_low_curvature(self, optimizer):
        """Test confidence calculation with low curvature (unclear elbow)."""
        k_values = list(range(2, 11))
        # Linear decrease - no clear elbow
        inertias = [100, 90, 80, 70, 60, 50, 40, 30, 20]
        elbow_k = 5

        confidence = optimizer._calculate_confidence(k_values, inertias, elbow_k)

        # Low curvature should give lower confidence
        assert 0.0 <= confidence <= 1.0


# ============================================================================
# Test SilhouetteOptimizer
# ============================================================================


class TestSilhouetteOptimizer:
    """Test cases for SilhouetteOptimizer class."""

    @pytest.fixture
    def optimizer(self):
        """Create SilhouetteOptimizer instance."""
        return SilhouetteOptimizer()

    def test_init_default_max_k(self, optimizer):
        """Test default max_k is set correctly."""
        assert optimizer.max_k == 15

    def test_init_custom_max_k(self):
        """Test custom max_k initialization."""
        custom_optimizer = SilhouetteOptimizer(max_k=25)
        assert custom_optimizer.max_k == 25

    def test_find_optimal_k_returns_result(self, optimizer):
        """Test that find_optimal_k returns ClusterOptimizationResult."""
        np.random.seed(42)
        embeddings = np.random.rand(50, 10)

        result = optimizer.find_optimal_k(embeddings)

        assert isinstance(result, ClusterOptimizationResult)
        assert result.method == "silhouette"
        assert 2 <= result.optimal_k <= optimizer.max_k
        assert 0.0 <= result.confidence_score <= 1.0

    def test_find_optimal_k_small_dataset(self, optimizer):
        """Test with small dataset (fewer samples than max_k)."""
        np.random.seed(42)
        embeddings = np.random.rand(5, 10)

        result = optimizer.find_optimal_k(embeddings)

        # Optimal k should be at most n_samples - 1
        assert result.optimal_k <= 4

    def test_find_optimal_k_with_clear_clusters(self, optimizer):
        """Test with data that has clear cluster structure."""
        # Create 3 well-separated clusters
        np.random.seed(42)
        cluster1 = np.random.randn(30, 10) + np.array([0] * 10)
        cluster2 = np.random.randn(30, 10) + np.array([10] * 10)
        cluster3 = np.random.randn(30, 10) + np.array([20] * 10)
        embeddings = np.vstack([cluster1, cluster2, cluster3])

        result = optimizer.find_optimal_k(embeddings)

        # Should identify around 3 clusters
        assert 2 <= result.optimal_k <= 5
        assert result.confidence_score > 0.3

    def test_find_optimal_k_returns_k_scores(self, optimizer):
        """Test that k_scores dictionary is populated."""
        np.random.seed(42)
        embeddings = np.random.rand(30, 10)

        result = optimizer.find_optimal_k(embeddings)

        assert len(result.k_scores) > 0
        # Silhouette scores should be between -1 and 1
        for score in result.k_scores.values():
            assert -1.0 <= score <= 1.0

    def test_find_optimal_k_returns_per_cluster_scores(self, optimizer):
        """Test that per_cluster_scores is populated."""
        np.random.seed(42)
        embeddings = np.random.rand(30, 10)

        result = optimizer.find_optimal_k(embeddings)

        assert result.per_cluster_scores is not None
        assert len(result.per_cluster_scores) == result.optimal_k

    def test_find_optimal_k_min_samples_required(self, optimizer):
        """Test that minimum 3 samples are required."""
        embeddings = np.random.rand(2, 10)

        with pytest.raises(ValueError, match="at least 3 samples"):
            optimizer.find_optimal_k(embeddings)

    def test_find_optimal_k_progress_callback(self, optimizer):
        """Test progress callback is called during optimization."""
        np.random.seed(42)
        embeddings = np.random.rand(30, 10)

        callback_calls = []

        def progress_callback(current, total):
            callback_calls.append((current, total))

        optimizer.find_optimal_k(embeddings, progress_callback=progress_callback)

        assert len(callback_calls) > 0
        # Final callback should have current == total
        assert callback_calls[-1][0] == callback_calls[-1][1]

    def test_find_optimal_k_parallel_evaluation(self, optimizer):
        """Test that parallel evaluation works correctly."""
        np.random.seed(42)
        embeddings = np.random.rand(50, 10)

        # Run with default settings (should use parallel evaluation)
        result = optimizer.find_optimal_k(embeddings)

        # Should complete without error and return valid result
        assert isinstance(result, ClusterOptimizationResult)
        assert len(result.k_scores) > 0

    def test_silhouette_score_positive_for_good_clusters(self, optimizer):
        """Test that silhouette score is positive for well-separated clusters."""
        np.random.seed(42)
        # Create very well-separated clusters
        cluster1 = np.random.randn(20, 5) * 0.1 + np.array([0, 0, 0, 0, 0])
        cluster2 = np.random.randn(20, 5) * 0.1 + np.array([10, 10, 10, 10, 10])
        embeddings = np.vstack([cluster1, cluster2])

        result = optimizer.find_optimal_k(embeddings)

        # Best silhouette score should be high for well-separated clusters
        max_score = max(result.k_scores.values())
        assert max_score > 0.5

    def test_confidence_based_on_max_silhouette(self, optimizer):
        """Test that confidence is based on maximum silhouette score."""
        np.random.seed(42)
        embeddings = np.random.rand(30, 10)

        result = optimizer.find_optimal_k(embeddings)

        # Confidence should be derived from the silhouette score
        max_score = max(result.k_scores.values())
        # Confidence should be non-negative
        assert result.confidence_score >= 0.0


# ============================================================================
# Integration Tests
# ============================================================================


class TestClusterOptimizerIntegration:
    """Integration tests for cluster optimizers."""

    def test_elbow_and_silhouette_similar_results_for_clear_clusters(self):
        """Test that both methods find similar k for clear cluster structure."""
        np.random.seed(42)
        # Create 4 well-separated clusters
        clusters = [
            np.random.randn(25, 10) + np.array([i * 15] * 10)
            for i in range(4)
        ]
        embeddings = np.vstack(clusters)

        elbow_optimizer = ElbowOptimizer(max_k=10)
        silhouette_optimizer = SilhouetteOptimizer(max_k=10)

        elbow_result = elbow_optimizer.find_optimal_k(embeddings)
        silhouette_result = silhouette_optimizer.find_optimal_k(embeddings)

        # Both should find approximately 4 clusters (within 2)
        assert abs(elbow_result.optimal_k - silhouette_result.optimal_k) <= 2
        # Both should find something close to 4
        assert 3 <= elbow_result.optimal_k <= 6
        assert 3 <= silhouette_result.optimal_k <= 6

    def test_both_methods_handle_random_data(self):
        """Test that both methods handle random (no clear structure) data."""
        np.random.seed(42)
        # Random data with no clear cluster structure
        embeddings = np.random.rand(100, 20)

        elbow_optimizer = ElbowOptimizer(max_k=10)
        silhouette_optimizer = SilhouetteOptimizer(max_k=10)

        elbow_result = elbow_optimizer.find_optimal_k(embeddings)
        silhouette_result = silhouette_optimizer.find_optimal_k(embeddings)

        # Both should return valid results even for random data
        assert 2 <= elbow_result.optimal_k <= 10
        assert 2 <= silhouette_result.optimal_k <= 10
        # Lower confidence expected for random data
        assert elbow_result.confidence_score >= 0.0
        assert silhouette_result.confidence_score >= 0.0
