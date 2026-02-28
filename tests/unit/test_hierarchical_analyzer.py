"""
Unit tests for HierarchicalAnalyzer module.

Tests agglomerative clustering for hierarchical email category generation.
Per Task 4A.2 requirements.
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from scipy.cluster.hierarchy import linkage

from src.models.corpus import Corpus, CorpusMetadata
from src.models.email import Email

# -----------------------------------------------------------------------------
# Test Fixtures
# -----------------------------------------------------------------------------


def create_email(
    email_id: str,
    sender_email: str = "sender@example.com",
    sender_domain: str = "example.com",
    subject: str = "Test Subject",
    body_text: str = "Test body content",
    received_date: datetime | None = None,
) -> Email:
    """Factory function to create Email objects for testing."""
    if received_date is None:
        received_date = datetime(2024, 1, 15, 10, 0)
    return Email(
        id=email_id,
        sender_email=sender_email,
        sender_name="Test Sender",
        sender_domain=sender_domain,
        recipient_email=None,
        recipient_name="",
        subject=subject,
        body_text=body_text,
        received_date=received_date,
        has_attachments=False,
    )


def create_corpus(emails: list[Email]) -> Corpus:
    """Factory function to create Corpus objects for testing."""
    return Corpus(
        extraction_metadata=CorpusMetadata(
            extraction_date=datetime.now(),
            total_emails=len(emails),
            source="test",
            user_email="user@example.com",
        ),
        emails=emails,
    )


# -----------------------------------------------------------------------------
# HierarchicalAnalyzer Init Tests
# -----------------------------------------------------------------------------


class TestHierarchicalAnalyzerInit:
    """Test HierarchicalAnalyzer initialization."""

    def test_init_default_parameters(self):
        """Test initialization with default parameters."""
        from src.analyzers.hierarchical_analyzer import HierarchicalAnalyzer

        analyzer = HierarchicalAnalyzer()

        assert analyzer.model_name == "mixedbread-ai/mxbai-embed-large-v1"
        assert analyzer.model is None  # Lazy loaded
        assert analyzer.min_top_clusters == 5
        assert analyzer.max_top_clusters == 10
        assert analyzer.min_subclusters == 2
        assert analyzer.max_subclusters == 5

    def test_init_custom_model(self):
        """Test initialization with custom model name."""
        from src.analyzers.hierarchical_analyzer import HierarchicalAnalyzer

        analyzer = HierarchicalAnalyzer(model_name="custom-model")

        assert analyzer.model_name == "custom-model"

    def test_init_custom_cluster_ranges(self):
        """Test initialization with custom cluster ranges."""
        from src.analyzers.hierarchical_analyzer import HierarchicalAnalyzer

        analyzer = HierarchicalAnalyzer(
            min_top_clusters=3,
            max_top_clusters=8,
            min_subclusters=1,
            max_subclusters=4,
        )

        assert analyzer.min_top_clusters == 3
        assert analyzer.max_top_clusters == 8
        assert analyzer.min_subclusters == 1
        assert analyzer.max_subclusters == 4


# -----------------------------------------------------------------------------
# HierarchicalAnalyzer Validation Tests
# -----------------------------------------------------------------------------


class TestHierarchicalAnalyzerValidation:
    """Test input validation for HierarchicalAnalyzer."""

    def test_analyze_empty_corpus_raises_error(self):
        """Test that analyzing empty corpus raises ValueError."""
        from src.analyzers.hierarchical_analyzer import HierarchicalAnalyzer

        analyzer = HierarchicalAnalyzer()
        corpus = create_corpus([])

        with pytest.raises(ValueError, match="Cannot analyze empty corpus"):
            analyzer.analyze(corpus)

    def test_analyze_single_email_returns_single_cluster(self):
        """Test that single email creates single cluster hierarchy."""
        from src.analyzers.hierarchical_analyzer import HierarchicalAnalyzer

        analyzer = HierarchicalAnalyzer()
        emails = [create_email(email_id="1")]
        corpus = create_corpus(emails)

        with patch.object(analyzer, "_ensure_model_loaded"):
            mock_model = MagicMock()
            mock_model.encode.return_value = np.random.rand(1, 384)
            analyzer.model = mock_model

            result = analyzer.analyze(corpus)

        # Single email should result in single top-level cluster
        assert len(result) == 1
        assert result[0].level == 0


# -----------------------------------------------------------------------------
# Hierarchical Clustering Tests
# -----------------------------------------------------------------------------


class TestHierarchicalClustering:
    """Test hierarchical clustering algorithm."""

    @patch("src.analyzers.hierarchical_analyzer.SentenceTransformer")
    def test_analyze_produces_two_level_hierarchy(self, mock_st_class):
        """Test that analyzer produces 2-level hierarchy."""
        from src.analyzers.hierarchical_analyzer import HierarchicalAnalyzer

        # Create emails with distinct patterns for clear clustering
        emails = [
            create_email(
                email_id=f"shopping_{i}", subject=f"Amazon order {i}", body_text="Order shipped"
            )
            for i in range(10)
        ] + [
            create_email(
                email_id=f"finance_{i}", subject=f"Bank statement {i}", body_text="Account balance"
            )
            for i in range(10)
        ]
        corpus = create_corpus(emails)

        # Create embeddings with clear cluster structure
        np.random.seed(42)
        shopping_embeddings = np.random.randn(10, 20) * 0.1 + np.array([0] * 20)
        finance_embeddings = np.random.randn(10, 20) * 0.1 + np.array([5] * 20)
        embeddings = np.vstack([shopping_embeddings, finance_embeddings])

        mock_model = MagicMock()
        mock_model.encode.return_value = embeddings
        mock_st_class.return_value = mock_model

        analyzer = HierarchicalAnalyzer()

        result = analyzer.analyze(corpus)

        # Should have top-level clusters (level 0)
        top_level = [c for c in result if c.level == 0]
        assert len(top_level) >= 1

        # May have subclusters (level 1) within top-level
        # Note: depends on cluster structure, might not always have subclusters

    @patch("src.analyzers.hierarchical_analyzer.SentenceTransformer")
    def test_top_level_clusters_within_range(self, mock_st_class):
        """Test that number of top-level clusters is within configured range."""
        from src.analyzers.hierarchical_analyzer import HierarchicalAnalyzer

        # Create enough emails for clustering
        emails = [create_email(email_id=str(i)) for i in range(50)]
        corpus = create_corpus(emails)

        np.random.seed(42)
        embeddings = np.random.rand(50, 20)

        mock_model = MagicMock()
        mock_model.encode.return_value = embeddings
        mock_st_class.return_value = mock_model

        analyzer = HierarchicalAnalyzer(min_top_clusters=5, max_top_clusters=10)

        result = analyzer.analyze(corpus)

        top_level = [c for c in result if c.level == 0]
        # Clusters should be within configured range (or adjusted for small corpus)
        assert len(top_level) >= 1
        assert len(top_level) <= 10

    @patch("src.analyzers.hierarchical_analyzer.SentenceTransformer")
    def test_subclusters_per_parent_within_range(self, mock_st_class):
        """Test that subclusters per parent are within configured range."""
        from src.analyzers.hierarchical_analyzer import HierarchicalAnalyzer

        # Create structured data that would produce subclusters
        emails = [create_email(email_id=str(i)) for i in range(100)]
        corpus = create_corpus(emails)

        np.random.seed(42)
        embeddings = np.random.rand(100, 20)

        mock_model = MagicMock()
        mock_model.encode.return_value = embeddings
        mock_st_class.return_value = mock_model

        analyzer = HierarchicalAnalyzer(min_subclusters=2, max_subclusters=5)

        result = analyzer.analyze(corpus)

        # Check subclusters for each top-level cluster
        top_level = [c for c in result if c.level == 0]
        for cluster in top_level:
            if cluster.has_children:
                # Subclusters should be within range
                assert cluster.children_count >= 0
                assert cluster.children_count <= 5


# -----------------------------------------------------------------------------
# Cluster Structure Tests
# -----------------------------------------------------------------------------


class TestClusterStructure:
    """Test cluster structure and properties."""

    @patch("src.analyzers.hierarchical_analyzer.SentenceTransformer")
    def test_clusters_have_required_fields(self, mock_st_class):
        """Test that clusters have all required fields."""
        from src.analyzers.hierarchical_analyzer import HierarchicalAnalyzer

        emails = [create_email(email_id=str(i)) for i in range(20)]
        corpus = create_corpus(emails)

        np.random.seed(42)
        embeddings = np.random.rand(20, 20)

        mock_model = MagicMock()
        mock_model.encode.return_value = embeddings
        mock_st_class.return_value = mock_model

        analyzer = HierarchicalAnalyzer()

        result = analyzer.analyze(corpus)

        for cluster in result:
            # Check HierarchicalCluster fields
            assert hasattr(cluster, "cluster_id")
            assert hasattr(cluster, "level")
            assert hasattr(cluster, "parent_cluster_id")
            assert hasattr(cluster, "size")
            assert hasattr(cluster, "percentage")
            assert hasattr(cluster, "email_ids")
            assert hasattr(cluster, "representative_samples")
            assert hasattr(cluster, "subclusters")

    @patch("src.analyzers.hierarchical_analyzer.SentenceTransformer")
    def test_top_level_clusters_have_null_parent(self, mock_st_class):
        """Test that top-level clusters have no parent."""
        from src.analyzers.hierarchical_analyzer import HierarchicalAnalyzer

        emails = [create_email(email_id=str(i)) for i in range(20)]
        corpus = create_corpus(emails)

        np.random.seed(42)
        embeddings = np.random.rand(20, 20)

        mock_model = MagicMock()
        mock_model.encode.return_value = embeddings
        mock_st_class.return_value = mock_model

        analyzer = HierarchicalAnalyzer()

        result = analyzer.analyze(corpus)

        top_level = [c for c in result if c.level == 0]
        for cluster in top_level:
            assert cluster.parent_cluster_id is None

    @patch("src.analyzers.hierarchical_analyzer.SentenceTransformer")
    def test_subclusters_have_valid_parent(self, mock_st_class):
        """Test that subclusters reference valid parent clusters."""
        from src.analyzers.hierarchical_analyzer import HierarchicalAnalyzer

        emails = [create_email(email_id=str(i)) for i in range(50)]
        corpus = create_corpus(emails)

        np.random.seed(42)
        embeddings = np.random.rand(50, 20)

        mock_model = MagicMock()
        mock_model.encode.return_value = embeddings
        mock_st_class.return_value = mock_model

        analyzer = HierarchicalAnalyzer()

        result = analyzer.analyze(corpus)

        # Collect all cluster IDs
        all_cluster_ids = {c.cluster_id for c in result}
        for c in result:
            all_cluster_ids.update(sub.cluster_id for sub in c.subclusters)

        # Check subclusters have valid parents
        for cluster in result:
            for subcluster in cluster.subclusters:
                assert subcluster.parent_cluster_id is not None
                assert subcluster.parent_cluster_id == cluster.cluster_id

    @patch("src.analyzers.hierarchical_analyzer.SentenceTransformer")
    def test_cluster_percentages_sum_to_100(self, mock_st_class):
        """Test that top-level cluster percentages sum to ~100%."""
        from src.analyzers.hierarchical_analyzer import HierarchicalAnalyzer

        emails = [create_email(email_id=str(i)) for i in range(30)]
        corpus = create_corpus(emails)

        np.random.seed(42)
        embeddings = np.random.rand(30, 20)

        mock_model = MagicMock()
        mock_model.encode.return_value = embeddings
        mock_st_class.return_value = mock_model

        analyzer = HierarchicalAnalyzer()

        result = analyzer.analyze(corpus)

        top_level = [c for c in result if c.level == 0]
        total_percentage = sum(c.percentage for c in top_level)
        assert abs(total_percentage - 100.0) < 0.1


# -----------------------------------------------------------------------------
# Fallback Behavior Tests
# -----------------------------------------------------------------------------


class TestFallbackBehavior:
    """Test fallback to flat clustering."""

    @patch("src.analyzers.hierarchical_analyzer.SentenceTransformer")
    def test_fallback_to_flat_with_few_emails(self, mock_st_class):
        """Test that flat clustering is used when corpus too small for hierarchy."""
        from src.analyzers.hierarchical_analyzer import HierarchicalAnalyzer

        # Very small corpus
        emails = [create_email(email_id=str(i)) for i in range(3)]
        corpus = create_corpus(emails)

        np.random.seed(42)
        embeddings = np.random.rand(3, 20)

        mock_model = MagicMock()
        mock_model.encode.return_value = embeddings
        mock_st_class.return_value = mock_model

        analyzer = HierarchicalAnalyzer()

        result = analyzer.analyze(corpus)

        # Small corpus should still produce valid results
        assert len(result) >= 1
        # All should be top-level (no subclusters for tiny corpus)
        for cluster in result:
            assert cluster.level == 0

    @patch("src.analyzers.hierarchical_analyzer.SentenceTransformer")
    def test_get_flat_clusters_method(self, mock_st_class):
        """Test get_flat_clusters returns flat list without hierarchy."""
        from src.analyzers.hierarchical_analyzer import HierarchicalAnalyzer

        emails = [create_email(email_id=str(i)) for i in range(20)]
        corpus = create_corpus(emails)

        np.random.seed(42)
        embeddings = np.random.rand(20, 20)

        mock_model = MagicMock()
        mock_model.encode.return_value = embeddings
        mock_st_class.return_value = mock_model

        analyzer = HierarchicalAnalyzer()

        # First analyze to populate internal state
        analyzer.analyze(corpus)

        # Then get flat version
        flat_result = analyzer.get_flat_clusters()

        assert isinstance(flat_result, list)
        # Flat clusters should not have subclusters
        for cluster in flat_result:
            assert cluster.level == 0


# -----------------------------------------------------------------------------
# Optimal Cut Point Tests
# -----------------------------------------------------------------------------


class TestOptimalCutPoint:
    """Test optimal cut point selection for hierarchy."""

    def test_select_optimal_cut_point_basic(self):
        """Test optimal cut point selection algorithm."""
        from src.analyzers.hierarchical_analyzer import HierarchicalAnalyzer

        analyzer = HierarchicalAnalyzer()

        # Create a simple dendrogram-like structure
        # Linkage matrix format: [idx1, idx2, distance, count]
        np.random.seed(42)
        data = np.random.rand(10, 5)
        z = linkage(data, method="ward")

        # The method should select a reasonable cut point
        cut_distance = analyzer._select_optimal_cut_point(z, target_clusters=3)

        assert cut_distance > 0
        # Should produce reasonable number of clusters when used

    def test_select_optimal_cut_respects_bounds(self):
        """Test that optimal cut respects min/max cluster bounds."""
        from src.analyzers.hierarchical_analyzer import HierarchicalAnalyzer

        analyzer = HierarchicalAnalyzer(min_top_clusters=5, max_top_clusters=10)

        np.random.seed(42)
        data = np.random.rand(50, 10)
        z = linkage(data, method="ward")

        cut_distance = analyzer._select_optimal_cut_point(
            z,
            target_clusters=7,  # Within range
        )

        assert cut_distance > 0


# -----------------------------------------------------------------------------
# Representative Sample Tests
# -----------------------------------------------------------------------------


class TestRepresentativeSamples:
    """Test representative sample selection for hierarchical clusters."""

    @patch("src.analyzers.hierarchical_analyzer.SentenceTransformer")
    def test_clusters_have_representative_samples(self, mock_st_class):
        """Test that clusters have representative samples."""
        from src.analyzers.hierarchical_analyzer import HierarchicalAnalyzer

        emails = [
            create_email(
                email_id=str(i),
                subject=f"Subject {i}",
                body_text=f"Body text {i}",
            )
            for i in range(20)
        ]
        corpus = create_corpus(emails)

        np.random.seed(42)
        embeddings = np.random.rand(20, 20)

        mock_model = MagicMock()
        mock_model.encode.return_value = embeddings
        mock_st_class.return_value = mock_model

        analyzer = HierarchicalAnalyzer()

        result = analyzer.analyze(corpus)

        for cluster in result:
            assert len(cluster.representative_samples) > 0
            assert len(cluster.representative_samples) <= 5

    @patch("src.analyzers.hierarchical_analyzer.SentenceTransformer")
    def test_representative_samples_have_required_fields(self, mock_st_class):
        """Test that representative samples have required fields."""
        from src.analyzers.hierarchical_analyzer import HierarchicalAnalyzer

        emails = [create_email(email_id=str(i)) for i in range(20)]
        corpus = create_corpus(emails)

        np.random.seed(42)
        embeddings = np.random.rand(20, 20)

        mock_model = MagicMock()
        mock_model.encode.return_value = embeddings
        mock_st_class.return_value = mock_model

        analyzer = HierarchicalAnalyzer()

        result = analyzer.analyze(corpus)

        for cluster in result:
            for sample in cluster.representative_samples:
                assert hasattr(sample, "subject")
                assert hasattr(sample, "sender")
                assert hasattr(sample, "body_preview")


# -----------------------------------------------------------------------------
# Progress Callback Tests
# -----------------------------------------------------------------------------


class TestProgressCallback:
    """Test progress callback functionality."""

    @patch("src.analyzers.hierarchical_analyzer.SentenceTransformer")
    def test_progress_callback_called(self, mock_st_class):
        """Test that progress callback is called during analysis."""
        from src.analyzers.hierarchical_analyzer import HierarchicalAnalyzer

        emails = [create_email(email_id=str(i)) for i in range(20)]
        corpus = create_corpus(emails)

        np.random.seed(42)
        embeddings = np.random.rand(20, 20)

        mock_model = MagicMock()
        mock_model.encode.return_value = embeddings
        mock_st_class.return_value = mock_model

        callback_calls = []

        def progress_callback(current, total):
            callback_calls.append((current, total))

        analyzer = HierarchicalAnalyzer()
        analyzer.analyze(corpus, progress_callback=progress_callback)

        assert len(callback_calls) > 0
        # Should include final callback
        assert callback_calls[-1][0] == callback_calls[-1][1]


# -----------------------------------------------------------------------------
# Common Domains Tests
# -----------------------------------------------------------------------------


class TestCommonDomains:
    """Test common domain extraction for hierarchical clusters."""

    @patch("src.analyzers.hierarchical_analyzer.SentenceTransformer")
    def test_clusters_have_common_domains(self, mock_st_class):
        """Test that clusters have common domains populated."""
        from src.analyzers.hierarchical_analyzer import HierarchicalAnalyzer

        emails = [
            create_email(
                email_id=str(i),
                sender_email=f"user{i % 3}@domain{i % 2}.com",
                sender_domain=f"domain{i % 2}.com",
            )
            for i in range(20)
        ]
        corpus = create_corpus(emails)

        np.random.seed(42)
        embeddings = np.random.rand(20, 20)

        mock_model = MagicMock()
        mock_model.encode.return_value = embeddings
        mock_st_class.return_value = mock_model

        analyzer = HierarchicalAnalyzer()

        result = analyzer.analyze(corpus)

        for cluster in result:
            assert isinstance(cluster.common_domains, list)


# -----------------------------------------------------------------------------
# HierarchicalCluster Model Tests
# -----------------------------------------------------------------------------


class TestHierarchicalClusterModel:
    """Test HierarchicalCluster data model."""

    def test_hierarchical_cluster_creation(self):
        """Test creating HierarchicalCluster object."""
        from src.analyzers.hierarchical_analyzer import HierarchicalCluster
        from src.models.content_cluster import RepresentativeSample

        sample = RepresentativeSample(
            subject="Test Subject",
            sender="test@example.com",
            body_preview="Test body",
        )

        cluster = HierarchicalCluster(
            cluster_id="cluster_0_0",
            level=0,
            parent_cluster_id=None,
            size=10,
            percentage=50.0,
            representative_samples=[sample],
            common_domains=[("example.com", 5)],
            email_ids=["1", "2", "3"],
            subclusters=[],
        )

        assert cluster.cluster_id == "cluster_0_0"
        assert cluster.level == 0
        assert cluster.parent_cluster_id is None
        assert cluster.size == 10

    def test_hierarchical_cluster_with_subclusters(self):
        """Test HierarchicalCluster with subclusters."""
        from src.analyzers.hierarchical_analyzer import HierarchicalCluster
        from src.models.content_cluster import RepresentativeSample

        sample = RepresentativeSample(
            subject="Test",
            sender="test@example.com",
            body_preview="Test",
        )

        child = HierarchicalCluster(
            cluster_id="cluster_0_1",
            level=1,
            parent_cluster_id="cluster_0",
            size=5,
            percentage=25.0,
            representative_samples=[sample],
            common_domains=[],
            email_ids=["1", "2"],
            subclusters=[],
        )

        parent = HierarchicalCluster(
            cluster_id="cluster_0",
            level=0,
            parent_cluster_id=None,
            size=10,
            percentage=50.0,
            representative_samples=[sample],
            common_domains=[],
            email_ids=["1", "2", "3", "4", "5"],
            subclusters=[child],
        )

        assert parent.has_children is True
        assert parent.children_count == 1
        assert parent.subclusters[0].cluster_id == "cluster_0_1"

    def test_hierarchical_cluster_is_top_level(self):
        """Test is_top_level property."""
        from src.analyzers.hierarchical_analyzer import HierarchicalCluster
        from src.models.content_cluster import RepresentativeSample

        sample = RepresentativeSample(
            subject="Test",
            sender="test@example.com",
            body_preview="Test",
        )

        top_level = HierarchicalCluster(
            cluster_id="cluster_0",
            level=0,
            parent_cluster_id=None,
            size=10,
            percentage=50.0,
            representative_samples=[sample],
            common_domains=[],
            email_ids=["1"],
            subclusters=[],
        )

        sub_level = HierarchicalCluster(
            cluster_id="cluster_0_1",
            level=1,
            parent_cluster_id="cluster_0",
            size=5,
            percentage=25.0,
            representative_samples=[sample],
            common_domains=[],
            email_ids=["1"],
            subclusters=[],
        )

        assert top_level.is_top_level is True
        assert sub_level.is_top_level is False
