"""
Unit tests for cluster optimizer module.

Tests the following cluster optimization components:
- compute_max_k function - corpus-size-aware max_k calculation
- silhouette_to_confidence - sigmoid normalization of silhouette scores
- interpret_silhouette - human-readable interpretation labels
- ElbowOptimizer class - finds optimal k using inertia curve
- SilhouetteOptimizer class - finds optimal k using silhouette scores
"""
import math
from unittest.mock import MagicMock, patch
import numpy as np
import pytest

from src.analyzers.cluster_optimizer import (
    ElbowOptimizer,
    SilhouetteOptimizer,
    ClusterOptimizationResult,
    compute_max_k,
    interpret_silhouette,
    silhouette_to_confidence,
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
# Test silhouette_to_confidence (sigmoid normalization)
# ============================================================================


class TestSilhouetteToConfidence:
    """Test cases for sigmoid-based silhouette-to-confidence mapping."""

    def test_positive_score_0_5_maps_high(self):
        """score = 0.5 -> confidence ≈ 0.924 (good clustering)."""
        conf = silhouette_to_confidence(0.5)
        assert abs(conf - 1.0 / (1.0 + math.exp(-2.5))) < 1e-6
        assert conf > 0.9

    def test_zero_score_maps_neutral(self):
        """score = 0.0 -> confidence = 0.50 exactly (neutral)."""
        conf = silhouette_to_confidence(0.0)
        assert conf == pytest.approx(0.5, abs=1e-9)

    def test_negative_score_maps_low(self):
        """score = -0.3 -> confidence ≈ 0.18 (clearly bad)."""
        conf = silhouette_to_confidence(-0.3)
        assert conf < 0.3

    def test_strong_positive_near_1(self):
        """score = 1.0 -> confidence very close to 1.0."""
        conf = silhouette_to_confidence(1.0)
        assert conf > 0.99

    def test_strong_negative_near_0(self):
        """score = -1.0 -> confidence very close to 0.0."""
        conf = silhouette_to_confidence(-1.0)
        assert conf < 0.01

    def test_monotonically_increasing(self):
        """Higher silhouette scores must always produce higher confidence."""
        scores = [-1.0, -0.5, -0.3, 0.0, 0.2, 0.5, 0.8, 1.0]
        confidences = [silhouette_to_confidence(s) for s in scores]
        for i in range(len(confidences) - 1):
            assert confidences[i] < confidences[i + 1], (
                f"Not monotonic: conf({scores[i]})={confidences[i]} "
                f">= conf({scores[i+1]})={confidences[i+1]}"
            )

    def test_output_always_in_0_1(self):
        """Confidence is always strictly between 0 and 1."""
        for score in [-1.0, -0.5, 0.0, 0.5, 1.0]:
            conf = silhouette_to_confidence(score)
            assert 0.0 < conf < 1.0

    def test_acceptance_negative_scores_below_0_3(self):
        """Acceptance: negative silhouette scores map to confidence < 0.3."""
        for score in [-0.3, -0.5, -0.8, -1.0]:
            conf = silhouette_to_confidence(score)
            assert conf < 0.3, (
                f"Negative score {score} mapped to confidence {conf}, "
                f"expected < 0.3"
            )

    def test_acceptance_positive_above_0_5_maps_high(self):
        """Acceptance: positive scores above 0.5 map to confidence > 0.9."""
        for score in [0.5, 0.6, 0.7, 0.8, 0.9, 1.0]:
            conf = silhouette_to_confidence(score)
            assert conf > 0.9, (
                f"Score {score} mapped to confidence {conf}, expected > 0.9"
            )


# ============================================================================
# Test interpret_silhouette
# ============================================================================


class TestInterpretSilhouette:
    """Test cases for silhouette interpretation labels."""

    def test_strong_for_good_score(self):
        """score = 0.5 -> 'strong' (confidence > 0.7)."""
        assert interpret_silhouette(0.5) == "strong"

    def test_strong_for_high_score(self):
        """score = 0.8 -> 'strong'."""
        assert interpret_silhouette(0.8) == "strong"

    def test_moderate_for_zero_score(self):
        """score = 0.0 -> 'moderate' (confidence = 0.5, in [0.4, 0.7])."""
        assert interpret_silhouette(0.0) == "moderate"

    def test_weak_for_negative_score(self):
        """score = -0.3 -> 'weak' (confidence ≈ 0.18 < 0.4)."""
        assert interpret_silhouette(-0.3) == "weak"

    def test_weak_for_very_negative_score(self):
        """score = -1.0 -> 'weak'."""
        assert interpret_silhouette(-1.0) == "weak"

    def test_strong_for_perfect_score(self):
        """score = 1.0 -> 'strong'."""
        assert interpret_silhouette(1.0) == "strong"

    def test_boundary_moderate_to_strong(self):
        """Verify the moderate/strong boundary around confidence = 0.7.

        confidence = 0.7 corresponds to sigmoid(x) = 0.7
        => -5x = ln(1/0.7 - 1) = ln(3/7) ≈ -0.847
        => x ≈ 0.169
        So score = 0.17 should be right near the boundary.
        """
        # Slightly above boundary -> strong
        assert interpret_silhouette(0.2) == "strong"
        # Slightly below boundary -> moderate
        assert interpret_silhouette(0.1) == "moderate"

    def test_boundary_weak_to_moderate(self):
        """Verify the weak/moderate boundary around confidence = 0.4.

        confidence = 0.4 corresponds to sigmoid(x) = 0.4
        => -5x = ln(1/0.4 - 1) = ln(1.5) ≈ 0.405
        => x ≈ -0.081
        So score = -0.08 should be right near the boundary.
        """
        # Slightly above boundary -> moderate
        assert interpret_silhouette(0.0) == "moderate"
        # Clearly below boundary -> weak
        assert interpret_silhouette(-0.2) == "weak"


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
        assert result.interpretation is None  # optional field defaults to None

    def test_creation_with_all_fields(self):
        """Test creation with all fields including per_cluster_scores and interpretation."""
        result = ClusterOptimizationResult(
            optimal_k=3,
            confidence_score=0.75,
            method="silhouette",
            k_scores={2: 0.5, 3: 0.7, 4: 0.6},
            per_cluster_scores={0: 0.8, 1: 0.7, 2: 0.6},
            interpretation="strong",
        )

        assert result.optimal_k == 3
        assert result.per_cluster_scores is not None
        assert len(result.per_cluster_scores) == 3
        assert result.interpretation == "strong"

    def test_interpretation_defaults_to_none(self):
        """Test that interpretation defaults to None when not provided."""
        result = ClusterOptimizationResult(
            optimal_k=5,
            confidence_score=0.5,
            method="elbow",
            k_scores={2: 100.0},
        )
        assert result.interpretation is None


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
        # With sigmoid normalization, well-separated clusters should give high confidence
        assert result.confidence_score > 0.5

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
        """Test that confidence matches sigmoid of maximum silhouette score."""
        np.random.seed(42)
        embeddings = np.random.rand(30, 10)

        result = optimizer.find_optimal_k(embeddings)

        # Confidence should equal sigmoid of the max silhouette score
        max_score = max(result.k_scores.values())
        expected_confidence = silhouette_to_confidence(max_score)
        assert result.confidence_score == pytest.approx(expected_confidence, abs=1e-6)

    def test_interpretation_included_in_result(self, optimizer):
        """Test that interpretation label is present in the result."""
        np.random.seed(42)
        embeddings = np.random.rand(30, 10)

        result = optimizer.find_optimal_k(embeddings)

        assert result.interpretation is not None
        assert result.interpretation in ("strong", "moderate", "weak")

    def test_interpretation_matches_confidence(self, optimizer):
        """Test that interpretation label is consistent with confidence value."""
        np.random.seed(42)
        embeddings = np.random.rand(30, 10)

        result = optimizer.find_optimal_k(embeddings)

        if result.confidence_score > 0.7:
            assert result.interpretation == "strong"
        elif result.confidence_score >= 0.4:
            assert result.interpretation == "moderate"
        else:
            assert result.interpretation == "weak"

    def test_well_separated_clusters_give_strong_interpretation(self, optimizer):
        """Test that well-separated clusters produce 'strong' interpretation."""
        np.random.seed(42)
        cluster1 = np.random.randn(20, 5) * 0.1 + np.array([0, 0, 0, 0, 0])
        cluster2 = np.random.randn(20, 5) * 0.1 + np.array([10, 10, 10, 10, 10])
        embeddings = np.vstack([cluster1, cluster2])

        result = optimizer.find_optimal_k(embeddings)

        # Well-separated clusters -> high silhouette -> strong
        assert result.interpretation == "strong"
        assert result.confidence_score > 0.9


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
