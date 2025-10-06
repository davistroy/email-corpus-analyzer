"""
Unit tests for confidence score calculation.

Tests the calculate_confidence function with various category
properties and edge cases.
"""
from src.generators.confidence_scorer import calculate_confidence
from src.models.category import Category, CategorySource


class TestConfidenceScorer:
    """Test cases for confidence score calculation."""

    def test_high_confidence_template_category(self):
        """Test high confidence for template-based category with good volume."""
        category = Category(
            category_id="test_1",
            category_name="Financial",
            description="Banking emails",
            confidence=0.0,
            email_count=150,
            percentage=15.0,
            source=CategorySource.TEMPLATE,
            distinguishing_features=["invoice", "payment"]
        )
        total_emails = 1000

        score = calculate_confidence(category, total_emails)

        # Template source = 0.9, volume (150/100 capped at 1.0) = 1.0, percentage = 0.15
        # Expected: avg(1.0, 0.9, 0.15) = 0.6833...
        assert 0.68 <= score <= 0.69

    def test_medium_confidence_cluster_category(self):
        """Test medium confidence for cluster-based category."""
        category = Category(
            category_id="test_2",
            category_name="Newsletter Cluster",
            description="Content cluster",
            confidence=0.0,
            email_count=50,
            percentage=5.0,
            source=CategorySource.CONTENT_CLUSTER,
            distinguishing_features=["newsletter"]
        )
        total_emails = 1000

        score = calculate_confidence(category, total_emails)

        # Cluster source = 0.8, volume = 0.5, percentage = 0.05
        # Expected: avg(0.5, 0.8, 0.05) = 0.45
        assert 0.44 <= score <= 0.46

    def test_low_confidence_sender_category(self):
        """Test lower confidence for sender-based category."""
        category = Category(
            category_id="test_3",
            category_name="Low Volume Sender",
            description="Sender category",
            confidence=0.0,
            email_count=10,
            percentage=1.0,
            source=CategorySource.SENDER,
            distinguishing_features=[]
        )
        total_emails = 1000

        score = calculate_confidence(category, total_emails)

        # Sender source = 0.7, volume = 0.1, percentage = 0.01
        # Expected: avg(0.1, 0.7, 0.01) = 0.27
        assert 0.26 <= score <= 0.28

    def test_very_low_confidence_custom_category(self):
        """Test very low confidence for custom category with low volume."""
        category = Category(
            category_id="test_4",
            category_name="Custom Low Volume",
            description="User custom",
            confidence=0.0,
            email_count=2,
            percentage=0.2,
            source=CategorySource.CUSTOM,
            distinguishing_features=[]
        )
        total_emails = 1000

        score = calculate_confidence(category, total_emails)

        # Custom source = 0.5, volume = 0.02, percentage = 0.002
        # Expected: avg(0.02, 0.5, 0.002) = 0.174
        assert 0.17 <= score <= 0.18

    def test_maximum_confidence_template_100_percent(self):
        """Test maximum possible confidence score."""
        category = Category(
            category_id="test_5",
            category_name="Everything",
            description="All emails",
            confidence=0.0,
            email_count=1000,
            percentage=100.0,
            source=CategorySource.TEMPLATE,
            distinguishing_features=[]
        )
        total_emails = 1000

        score = calculate_confidence(category, total_emails)

        # Template = 0.9, volume = 1.0 (capped), percentage = 1.0
        # Expected: avg(1.0, 0.9, 1.0) = 0.9666...
        assert 0.96 <= score <= 0.97

    def test_volume_score_capped_at_100(self):
        """Test that volume score caps at 1.0 even with >100 emails."""
        category = Category(
            category_id="test_6",
            category_name="High Volume",
            description="Many emails",
            confidence=0.0,
            email_count=500,
            percentage=50.0,
            source=CategorySource.TEMPLATE,
            distinguishing_features=[]
        )
        total_emails = 1000

        score = calculate_confidence(category, total_emails)

        # Volume should be capped at 1.0 (not 5.0)
        # Expected: avg(1.0, 0.9, 0.5) = 0.8
        assert 0.79 <= score <= 0.81

    def test_zero_emails_zero_percentage(self):
        """Test handling of category with zero emails."""
        category = Category(
            category_id="test_7",
            category_name="Empty Category",
            description="No emails",
            confidence=0.0,
            email_count=0,
            percentage=0.0,
            source=CategorySource.CUSTOM,
            distinguishing_features=[]
        )
        total_emails = 1000

        score = calculate_confidence(category, total_emails)

        # Volume = 0.0, source = 0.5, percentage = 0.0
        # Expected: avg(0.0, 0.5, 0.0) = 0.1666...
        assert 0.16 <= score <= 0.17

    def test_small_corpus_100_emails(self):
        """Test confidence calculation with small corpus."""
        category = Category(
            category_id="test_8",
            category_name="Half of Small Corpus",
            description="Test",
            confidence=0.0,
            email_count=50,
            percentage=50.0,
            source=CategorySource.CONTENT_CLUSTER,
            distinguishing_features=[]
        )
        total_emails = 100

        score = calculate_confidence(category, total_emails)

        # Volume = 0.5, source = 0.8, percentage = 0.5
        # Expected: avg(0.5, 0.8, 0.5) = 0.6
        assert 0.59 <= score <= 0.61

    def test_all_category_sources(self):
        """Test that all CategorySource types produce different scores."""
        base_category_data = {
            "category_id": "test",
            "category_name": "Test",
            "description": "Test",
            "confidence": 0.0,
            "email_count": 50,
            "percentage": 5.0,
            "distinguishing_features": []
        }
        total_emails = 1000

        sources_and_scores = {}
        for source in CategorySource:
            category = Category(**base_category_data, source=source)
            score = calculate_confidence(category, total_emails)
            sources_and_scores[source] = score

        # Verify ordering: TEMPLATE > CONTENT_CLUSTER > SENDER > CUSTOM
        assert sources_and_scores[CategorySource.TEMPLATE] > sources_and_scores[CategorySource.CONTENT_CLUSTER]
        assert sources_and_scores[CategorySource.CONTENT_CLUSTER] > sources_and_scores[CategorySource.SENDER]
        assert sources_and_scores[CategorySource.SENDER] > sources_and_scores[CategorySource.CUSTOM]

    def test_score_always_between_0_and_1(self):
        """Test that confidence score is always in valid range."""
        # Test extreme cases
        test_cases = [
            {"email_count": 0, "percentage": 0.0, "source": CategorySource.CUSTOM},
            {"email_count": 10000, "percentage": 100.0, "source": CategorySource.TEMPLATE},
            {"email_count": 1, "percentage": 0.01, "source": CategorySource.SENDER},
        ]

        for case_data in test_cases:
            category = Category(
                category_id="test",
                category_name="Test",
                description="Test",
                confidence=0.0,
                distinguishing_features=[],
                **case_data
            )
            score = calculate_confidence(category, 1000)

            assert 0.0 <= score <= 1.0, f"Score {score} out of range for {case_data}"

    def test_none_email_count_and_percentage(self):
        """Test handling when email_count or percentage is None."""
        category = Category(
            category_id="test_9",
            category_name="Template Only",
            description="Template match",
            confidence=0.0,
            email_count=None,
            percentage=None,
            source=CategorySource.TEMPLATE,
            distinguishing_features=[]
        )
        total_emails = 1000

        score = calculate_confidence(category, total_emails)

        # Should handle None gracefully (treat as 0)
        # Expected: avg(0.0, 0.9, 0.0) = 0.3
        assert 0.29 <= score <= 0.31

    def test_percentage_precision(self):
        """Test that small percentage differences are preserved."""
        category1 = Category(
            category_id="test_10a",
            category_name="1%",
            description="Test",
            confidence=0.0,
            email_count=10,
            percentage=1.0,
            source=CategorySource.TEMPLATE,
            distinguishing_features=[]
        )
        category2 = Category(
            category_id="test_10b",
            category_name="2%",
            description="Test",
            confidence=0.0,
            email_count=20,
            percentage=2.0,
            source=CategorySource.TEMPLATE,
            distinguishing_features=[]
        )
        total_emails = 1000

        score1 = calculate_confidence(category1, total_emails)
        score2 = calculate_confidence(category2, total_emails)

        # Score2 should be higher due to higher percentage and volume
        assert score2 > score1
