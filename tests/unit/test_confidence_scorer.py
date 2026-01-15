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


# =============================================================================
# Task 5A.1: Enhanced Confidence Model Tests
# =============================================================================


class TestConfidenceWeights:
    """Test ConfidenceWeights dataclass."""

    def test_confidence_weights_default_values(self):
        """Test that ConfidenceWeights has sensible defaults."""
        from src.generators.confidence_scorer import ConfidenceWeights

        weights = ConfidenceWeights()

        # All weights should be positive
        assert weights.cohesion >= 0
        assert weights.volume >= 0
        assert weights.source >= 0
        assert weights.percentage >= 0
        assert weights.name_quality >= 0
        assert weights.distinctiveness >= 0

        # Weights should sum to 1.0 for normalization
        total = (
            weights.cohesion + weights.volume + weights.source +
            weights.percentage + weights.name_quality + weights.distinctiveness
        )
        assert 0.99 <= total <= 1.01  # Allow small float tolerance

    def test_confidence_weights_custom_values(self):
        """Test creating ConfidenceWeights with custom values."""
        from src.generators.confidence_scorer import ConfidenceWeights

        weights = ConfidenceWeights(
            cohesion=0.3,
            volume=0.2,
            source=0.2,
            percentage=0.15,
            name_quality=0.1,
            distinctiveness=0.05
        )

        assert weights.cohesion == 0.3
        assert weights.volume == 0.2
        assert weights.source == 0.2
        assert weights.percentage == 0.15
        assert weights.name_quality == 0.1
        assert weights.distinctiveness == 0.05


class TestEnhancedConfidenceScorer:
    """Test enhanced confidence scoring with weighted factors."""

    def test_calculate_confidence_enhanced_returns_breakdown(self):
        """Test that enhanced confidence calculation returns breakdown dict."""
        from src.generators.confidence_scorer import calculate_confidence_enhanced

        category = Category(
            category_id="test_enhanced_1",
            category_name="Financial",
            description="Banking emails",
            confidence=0.0,
            email_count=100,
            percentage=10.0,
            source=CategorySource.TEMPLATE,
            distinguishing_features=["invoice", "payment"],
            name_quality_score=0.8
        )

        score, breakdown = calculate_confidence_enhanced(category, total_emails=1000)

        # Should return both score and breakdown
        assert isinstance(score, float)
        assert isinstance(breakdown, dict)

        # Breakdown should have all component scores
        assert "cohesion" in breakdown
        assert "volume" in breakdown
        assert "source" in breakdown
        assert "percentage" in breakdown
        assert "name_quality" in breakdown
        assert "distinctiveness" in breakdown

    def test_calculate_confidence_enhanced_score_in_range(self):
        """Test that enhanced confidence score is in valid range."""
        from src.generators.confidence_scorer import calculate_confidence_enhanced

        category = Category(
            category_id="test_enhanced_2",
            category_name="Test",
            description="Test",
            confidence=0.0,
            email_count=50,
            percentage=5.0,
            source=CategorySource.CONTENT_CLUSTER,
            distinguishing_features=[]
        )

        score, _ = calculate_confidence_enhanced(category, total_emails=1000)

        assert 0.0 <= score <= 1.0

    def test_calculate_confidence_enhanced_component_scores_in_range(self):
        """Test that all component scores are in valid range [0, 1]."""
        from src.generators.confidence_scorer import calculate_confidence_enhanced

        category = Category(
            category_id="test_enhanced_3",
            category_name="Test Category",
            description="Test",
            confidence=0.0,
            email_count=100,
            percentage=10.0,
            source=CategorySource.TEMPLATE,
            distinguishing_features=["feature1", "feature2"]
        )

        _, breakdown = calculate_confidence_enhanced(category, total_emails=1000)

        for component, value in breakdown.items():
            assert 0.0 <= value <= 1.0, f"Component {component} out of range: {value}"

    def test_calculate_confidence_enhanced_with_custom_weights(self):
        """Test enhanced confidence with custom weights."""
        from src.generators.confidence_scorer import (
            calculate_confidence_enhanced,
            ConfidenceWeights
        )

        category = Category(
            category_id="test_enhanced_4",
            category_name="Test",
            description="Test",
            confidence=0.0,
            email_count=100,
            percentage=10.0,
            source=CategorySource.TEMPLATE,
            distinguishing_features=[]
        )

        # Use custom weights that emphasize volume
        weights = ConfidenceWeights(
            cohesion=0.1,
            volume=0.5,
            source=0.1,
            percentage=0.1,
            name_quality=0.1,
            distinctiveness=0.1
        )

        score, _ = calculate_confidence_enhanced(
            category, total_emails=1000, weights=weights
        )

        assert 0.0 <= score <= 1.0

    def test_cohesion_score_from_distinguishing_features(self):
        """Test cohesion score based on distinguishing features count."""
        from src.generators.confidence_scorer import calculate_confidence_enhanced

        # Category with many distinguishing features = high cohesion
        high_cohesion = Category(
            category_id="test_cohesion_high",
            category_name="Cohesive",
            description="Test",
            confidence=0.0,
            email_count=50,
            percentage=5.0,
            source=CategorySource.CONTENT_CLUSTER,
            distinguishing_features=["f1", "f2", "f3", "f4", "f5"]
        )

        # Category with no features = low cohesion
        low_cohesion = Category(
            category_id="test_cohesion_low",
            category_name="Not Cohesive",
            description="Test",
            confidence=0.0,
            email_count=50,
            percentage=5.0,
            source=CategorySource.CONTENT_CLUSTER,
            distinguishing_features=[]
        )

        _, high_breakdown = calculate_confidence_enhanced(high_cohesion, total_emails=1000)
        _, low_breakdown = calculate_confidence_enhanced(low_cohesion, total_emails=1000)

        assert high_breakdown["cohesion"] > low_breakdown["cohesion"]

    def test_name_quality_component(self):
        """Test name quality component uses name_quality_score field."""
        from src.generators.confidence_scorer import calculate_confidence_enhanced

        # High quality name
        high_quality = Category(
            category_id="test_name_high",
            category_name="Financial Statements",
            description="Test",
            confidence=0.0,
            email_count=50,
            percentage=5.0,
            source=CategorySource.TEMPLATE,
            distinguishing_features=[],
            name_quality_score=0.9
        )

        # Low quality name
        low_quality = Category(
            category_id="test_name_low",
            category_name="cluster_42",
            description="Test",
            confidence=0.0,
            email_count=50,
            percentage=5.0,
            source=CategorySource.TEMPLATE,
            distinguishing_features=[],
            name_quality_score=0.2
        )

        _, high_breakdown = calculate_confidence_enhanced(high_quality, total_emails=1000)
        _, low_breakdown = calculate_confidence_enhanced(low_quality, total_emails=1000)

        assert high_breakdown["name_quality"] > low_breakdown["name_quality"]

    def test_name_quality_defaults_when_none(self):
        """Test name_quality defaults to neutral value when name_quality_score is None."""
        from src.generators.confidence_scorer import calculate_confidence_enhanced

        category = Category(
            category_id="test_name_none",
            category_name="Test",
            description="Test",
            confidence=0.0,
            email_count=50,
            percentage=5.0,
            source=CategorySource.TEMPLATE,
            distinguishing_features=[],
            name_quality_score=None
        )

        _, breakdown = calculate_confidence_enhanced(category, total_emails=1000)

        # Should use default neutral value (0.5) when None
        assert 0.4 <= breakdown["name_quality"] <= 0.6

    def test_distinctiveness_defaults_to_full_score(self):
        """Test distinctiveness defaults to 1.0 when not provided."""
        from src.generators.confidence_scorer import calculate_confidence_enhanced

        category = Category(
            category_id="test_distinct",
            category_name="Test",
            description="Test",
            confidence=0.0,
            email_count=50,
            percentage=5.0,
            source=CategorySource.TEMPLATE,
            distinguishing_features=[]
        )

        # No overlap scores provided, should default to 1.0
        _, breakdown = calculate_confidence_enhanced(category, total_emails=1000)

        assert breakdown["distinctiveness"] == 1.0

    def test_enhanced_confidence_with_overlap_penalty(self):
        """Test that overlap scores reduce distinctiveness."""
        from src.generators.confidence_scorer import calculate_confidence_enhanced

        category = Category(
            category_id="test_overlap",
            category_name="Test",
            description="Test",
            confidence=0.0,
            email_count=50,
            percentage=5.0,
            source=CategorySource.TEMPLATE,
            distinguishing_features=[]
        )

        # Provide overlap scores - high overlap should reduce distinctiveness
        overlap_scores = {"other_cat": 0.8}  # 80% overlap with another category

        _, breakdown = calculate_confidence_enhanced(
            category, total_emails=1000, overlap_scores=overlap_scores
        )

        # Distinctiveness should be penalized
        assert breakdown["distinctiveness"] < 1.0


class TestCategoryConfidenceBreakdown:
    """Test that Category model stores confidence breakdown."""

    def test_category_has_confidence_breakdown_field(self):
        """Test that Category model has confidence_breakdown field."""
        category = Category(
            category_id="test_breakdown",
            category_name="Test",
            description="Test",
            confidence=0.5,
            email_count=50,
            percentage=5.0,
            source=CategorySource.TEMPLATE,
            distinguishing_features=[],
            confidence_breakdown={
                "cohesion": 0.5,
                "volume": 0.6,
                "source": 0.9,
                "percentage": 0.05,
                "name_quality": 0.7,
                "distinctiveness": 0.8
            }
        )

        assert category.confidence_breakdown is not None
        assert category.confidence_breakdown["cohesion"] == 0.5
        assert category.confidence_breakdown["source"] == 0.9

    def test_category_confidence_breakdown_optional(self):
        """Test that confidence_breakdown is optional (defaults to None)."""
        category = Category(
            category_id="test_no_breakdown",
            category_name="Test",
            description="Test",
            confidence=0.5,
            email_count=50,
            percentage=5.0,
            source=CategorySource.TEMPLATE,
            distinguishing_features=[]
        )

        assert category.confidence_breakdown is None


# =============================================================================
# Task 5A.2: Distinctiveness Scoring Tests
# =============================================================================


class TestPairwiseCategoryOverlap:
    """Test pairwise category overlap calculation."""

    def test_calculate_pairwise_overlap_returns_dict(self):
        """Test that pairwise overlap returns a dict of overlap scores."""
        from src.generators.confidence_scorer import calculate_pairwise_overlap

        cat1 = Category(
            category_id="cat1",
            category_name="Newsletter",
            description="Newsletters",
            confidence=0.5,
            email_count=50,
            percentage=5.0,
            source=CategorySource.CONTENT_CLUSTER,
            distinguishing_features=[],
            example_email_ids=["email1", "email2", "email3", "email4", "email5"]
        )
        cat2 = Category(
            category_id="cat2",
            category_name="Promotions",
            description="Promotions",
            confidence=0.5,
            email_count=50,
            percentage=5.0,
            source=CategorySource.CONTENT_CLUSTER,
            distinguishing_features=[],
            example_email_ids=["email3", "email4", "email6", "email7"]
        )

        result = calculate_pairwise_overlap([cat1, cat2])

        # Result should be nested dict: {cat_id: {other_cat_id: overlap_score}}
        assert isinstance(result, dict)
        assert "cat1" in result
        assert "cat2" in result

    def test_calculate_pairwise_overlap_symmetric(self):
        """Test that overlap between A and B equals overlap between B and A."""
        from src.generators.confidence_scorer import calculate_pairwise_overlap

        cat1 = Category(
            category_id="cat1",
            category_name="Cat1",
            description="Test",
            confidence=0.5,
            email_count=10,
            percentage=1.0,
            source=CategorySource.CONTENT_CLUSTER,
            distinguishing_features=[],
            example_email_ids=["a", "b", "c", "d"]
        )
        cat2 = Category(
            category_id="cat2",
            category_name="Cat2",
            description="Test",
            confidence=0.5,
            email_count=10,
            percentage=1.0,
            source=CategorySource.CONTENT_CLUSTER,
            distinguishing_features=[],
            example_email_ids=["c", "d", "e", "f"]
        )

        result = calculate_pairwise_overlap([cat1, cat2])

        # Overlap should be symmetric
        assert result["cat1"]["cat2"] == result["cat2"]["cat1"]

    def test_calculate_pairwise_overlap_no_overlap(self):
        """Test pairwise overlap with no shared emails."""
        from src.generators.confidence_scorer import calculate_pairwise_overlap

        cat1 = Category(
            category_id="cat1",
            category_name="Cat1",
            description="Test",
            confidence=0.5,
            email_count=10,
            percentage=1.0,
            source=CategorySource.CONTENT_CLUSTER,
            distinguishing_features=[],
            example_email_ids=["a", "b", "c"]
        )
        cat2 = Category(
            category_id="cat2",
            category_name="Cat2",
            description="Test",
            confidence=0.5,
            email_count=10,
            percentage=1.0,
            source=CategorySource.CONTENT_CLUSTER,
            distinguishing_features=[],
            example_email_ids=["d", "e", "f"]
        )

        result = calculate_pairwise_overlap([cat1, cat2])

        assert result["cat1"]["cat2"] == 0.0
        assert result["cat2"]["cat1"] == 0.0

    def test_calculate_pairwise_overlap_full_overlap(self):
        """Test pairwise overlap with complete overlap."""
        from src.generators.confidence_scorer import calculate_pairwise_overlap

        cat1 = Category(
            category_id="cat1",
            category_name="Cat1",
            description="Test",
            confidence=0.5,
            email_count=10,
            percentage=1.0,
            source=CategorySource.CONTENT_CLUSTER,
            distinguishing_features=[],
            example_email_ids=["a", "b", "c"]
        )
        cat2 = Category(
            category_id="cat2",
            category_name="Cat2",
            description="Test",
            confidence=0.5,
            email_count=10,
            percentage=1.0,
            source=CategorySource.CONTENT_CLUSTER,
            distinguishing_features=[],
            example_email_ids=["a", "b", "c"]
        )

        result = calculate_pairwise_overlap([cat1, cat2])

        # Complete overlap should be 1.0
        assert result["cat1"]["cat2"] == 1.0
        assert result["cat2"]["cat1"] == 1.0

    def test_calculate_pairwise_overlap_partial(self):
        """Test pairwise overlap with partial overlap."""
        from src.generators.confidence_scorer import calculate_pairwise_overlap

        cat1 = Category(
            category_id="cat1",
            category_name="Cat1",
            description="Test",
            confidence=0.5,
            email_count=10,
            percentage=1.0,
            source=CategorySource.CONTENT_CLUSTER,
            distinguishing_features=[],
            example_email_ids=["a", "b", "c", "d"]  # 4 emails
        )
        cat2 = Category(
            category_id="cat2",
            category_name="Cat2",
            description="Test",
            confidence=0.5,
            email_count=10,
            percentage=1.0,
            source=CategorySource.CONTENT_CLUSTER,
            distinguishing_features=[],
            example_email_ids=["c", "d", "e", "f"]  # 4 emails, 2 shared
        )

        result = calculate_pairwise_overlap([cat1, cat2])

        # Jaccard similarity: 2 / (4 + 4 - 2) = 2/6 = 0.333...
        assert 0.32 <= result["cat1"]["cat2"] <= 0.34

    def test_calculate_pairwise_overlap_empty_categories(self):
        """Test pairwise overlap with empty email lists."""
        from src.generators.confidence_scorer import calculate_pairwise_overlap

        cat1 = Category(
            category_id="cat1",
            category_name="Cat1",
            description="Test",
            confidence=0.5,
            email_count=0,
            percentage=0.0,
            source=CategorySource.CONTENT_CLUSTER,
            distinguishing_features=[],
            example_email_ids=[]
        )
        cat2 = Category(
            category_id="cat2",
            category_name="Cat2",
            description="Test",
            confidence=0.5,
            email_count=10,
            percentage=1.0,
            source=CategorySource.CONTENT_CLUSTER,
            distinguishing_features=[],
            example_email_ids=["a", "b"]
        )

        result = calculate_pairwise_overlap([cat1, cat2])

        # Empty set with non-empty set = 0 overlap
        assert result["cat1"]["cat2"] == 0.0

    def test_calculate_pairwise_overlap_single_category(self):
        """Test pairwise overlap with single category returns empty nested dict."""
        from src.generators.confidence_scorer import calculate_pairwise_overlap

        cat1 = Category(
            category_id="cat1",
            category_name="Cat1",
            description="Test",
            confidence=0.5,
            email_count=10,
            percentage=1.0,
            source=CategorySource.CONTENT_CLUSTER,
            distinguishing_features=[],
            example_email_ids=["a", "b"]
        )

        result = calculate_pairwise_overlap([cat1])

        # Single category should have empty overlaps
        assert result == {"cat1": {}}


class TestHighOverlapCategories:
    """Test identification of high overlap (merge candidate) categories."""

    def test_find_merge_candidates_returns_list(self):
        """Test that find_merge_candidates returns a list of tuples."""
        from src.generators.confidence_scorer import find_merge_candidates

        cat1 = Category(
            category_id="cat1",
            category_name="Newsletters Weekly",
            description="Weekly newsletters",
            confidence=0.5,
            email_count=30,
            percentage=3.0,
            source=CategorySource.CONTENT_CLUSTER,
            distinguishing_features=[],
            example_email_ids=["a", "b", "c", "d", "e"]
        )
        cat2 = Category(
            category_id="cat2",
            category_name="Weekly Updates",
            description="Weekly update emails",
            confidence=0.5,
            email_count=30,
            percentage=3.0,
            source=CategorySource.CONTENT_CLUSTER,
            distinguishing_features=[],
            example_email_ids=["a", "b", "c", "d", "f"]  # High overlap
        )

        result = find_merge_candidates([cat1, cat2])

        assert isinstance(result, list)

    def test_find_merge_candidates_high_overlap(self):
        """Test that high overlap categories are flagged as merge candidates."""
        from src.generators.confidence_scorer import find_merge_candidates

        cat1 = Category(
            category_id="cat1",
            category_name="Cat1",
            description="Test",
            confidence=0.5,
            email_count=10,
            percentage=1.0,
            source=CategorySource.CONTENT_CLUSTER,
            distinguishing_features=[],
            example_email_ids=["a", "b", "c", "d", "e", "f", "g", "h"]
        )
        cat2 = Category(
            category_id="cat2",
            category_name="Cat2",
            description="Test",
            confidence=0.5,
            email_count=10,
            percentage=1.0,
            source=CategorySource.CONTENT_CLUSTER,
            distinguishing_features=[],
            example_email_ids=["a", "b", "c", "d", "e", "f", "g", "i"]  # 7/9 = 0.778 overlap
        )

        result = find_merge_candidates([cat1, cat2], threshold=0.5)

        # High overlap should flag as merge candidates
        assert len(result) >= 1
        # Result tuples should contain category IDs
        cat_ids = set()
        for item in result:
            cat_ids.add(item[0])
            cat_ids.add(item[1])
        assert "cat1" in cat_ids or "cat2" in cat_ids

    def test_find_merge_candidates_no_high_overlap(self):
        """Test that low overlap categories are not flagged."""
        from src.generators.confidence_scorer import find_merge_candidates

        cat1 = Category(
            category_id="cat1",
            category_name="Cat1",
            description="Test",
            confidence=0.5,
            email_count=10,
            percentage=1.0,
            source=CategorySource.CONTENT_CLUSTER,
            distinguishing_features=[],
            example_email_ids=["a", "b", "c", "d"]
        )
        cat2 = Category(
            category_id="cat2",
            category_name="Cat2",
            description="Test",
            confidence=0.5,
            email_count=10,
            percentage=1.0,
            source=CategorySource.CONTENT_CLUSTER,
            distinguishing_features=[],
            example_email_ids=["e", "f", "g", "h"]  # No overlap
        )

        result = find_merge_candidates([cat1, cat2], threshold=0.5)

        assert len(result) == 0

    def test_find_merge_candidates_custom_threshold(self):
        """Test that custom threshold controls merge candidate detection."""
        from src.generators.confidence_scorer import find_merge_candidates

        cat1 = Category(
            category_id="cat1",
            category_name="Cat1",
            description="Test",
            confidence=0.5,
            email_count=10,
            percentage=1.0,
            source=CategorySource.CONTENT_CLUSTER,
            distinguishing_features=[],
            example_email_ids=["a", "b", "c", "d"]
        )
        cat2 = Category(
            category_id="cat2",
            category_name="Cat2",
            description="Test",
            confidence=0.5,
            email_count=10,
            percentage=1.0,
            source=CategorySource.CONTENT_CLUSTER,
            distinguishing_features=[],
            example_email_ids=["c", "d", "e", "f"]  # 50% overlap (2/6 = 0.33 Jaccard)
        )

        # With high threshold, should not flag
        result_high = find_merge_candidates([cat1, cat2], threshold=0.8)
        assert len(result_high) == 0

        # With low threshold, should flag
        result_low = find_merge_candidates([cat1, cat2], threshold=0.2)
        assert len(result_low) >= 1

    def test_find_merge_candidates_returns_overlap_score(self):
        """Test that merge candidates include overlap score."""
        from src.generators.confidence_scorer import find_merge_candidates

        cat1 = Category(
            category_id="cat1",
            category_name="Cat1",
            description="Test",
            confidence=0.5,
            email_count=10,
            percentage=1.0,
            source=CategorySource.CONTENT_CLUSTER,
            distinguishing_features=[],
            example_email_ids=["a", "b", "c", "d", "e"]
        )
        cat2 = Category(
            category_id="cat2",
            category_name="Cat2",
            description="Test",
            confidence=0.5,
            email_count=10,
            percentage=1.0,
            source=CategorySource.CONTENT_CLUSTER,
            distinguishing_features=[],
            example_email_ids=["a", "b", "c", "d", "e"]  # 100% overlap
        )

        result = find_merge_candidates([cat1, cat2], threshold=0.5)

        # Each tuple should have (cat1_id, cat2_id, overlap_score)
        assert len(result) >= 1
        assert len(result[0]) == 3
        assert result[0][2] == 1.0  # Full overlap


class TestDistinctivenessScoring:
    """Test distinctiveness score calculation."""

    def test_calculate_distinctiveness_scores_returns_dict(self):
        """Test that distinctiveness scores returns a dict."""
        from src.generators.confidence_scorer import calculate_distinctiveness_scores

        cat1 = Category(
            category_id="cat1",
            category_name="Cat1",
            description="Test",
            confidence=0.5,
            email_count=10,
            percentage=1.0,
            source=CategorySource.CONTENT_CLUSTER,
            distinguishing_features=[],
            example_email_ids=["a", "b", "c"]
        )
        cat2 = Category(
            category_id="cat2",
            category_name="Cat2",
            description="Test",
            confidence=0.5,
            email_count=10,
            percentage=1.0,
            source=CategorySource.CONTENT_CLUSTER,
            distinguishing_features=[],
            example_email_ids=["d", "e", "f"]
        )

        result = calculate_distinctiveness_scores([cat1, cat2])

        assert isinstance(result, dict)
        assert "cat1" in result
        assert "cat2" in result

    def test_calculate_distinctiveness_scores_range(self):
        """Test that distinctiveness scores are in valid range [0, 1]."""
        from src.generators.confidence_scorer import calculate_distinctiveness_scores

        cat1 = Category(
            category_id="cat1",
            category_name="Cat1",
            description="Test",
            confidence=0.5,
            email_count=10,
            percentage=1.0,
            source=CategorySource.CONTENT_CLUSTER,
            distinguishing_features=[],
            example_email_ids=["a", "b", "c", "d"]
        )
        cat2 = Category(
            category_id="cat2",
            category_name="Cat2",
            description="Test",
            confidence=0.5,
            email_count=10,
            percentage=1.0,
            source=CategorySource.CONTENT_CLUSTER,
            distinguishing_features=[],
            example_email_ids=["c", "d", "e", "f"]
        )

        result = calculate_distinctiveness_scores([cat1, cat2])

        for cat_id, score in result.items():
            assert 0.0 <= score <= 1.0, f"Score for {cat_id} out of range: {score}"

    def test_calculate_distinctiveness_no_overlap_full_score(self):
        """Test that categories with no overlap get full distinctiveness score."""
        from src.generators.confidence_scorer import calculate_distinctiveness_scores

        cat1 = Category(
            category_id="cat1",
            category_name="Cat1",
            description="Test",
            confidence=0.5,
            email_count=10,
            percentage=1.0,
            source=CategorySource.CONTENT_CLUSTER,
            distinguishing_features=[],
            example_email_ids=["a", "b", "c"]
        )
        cat2 = Category(
            category_id="cat2",
            category_name="Cat2",
            description="Test",
            confidence=0.5,
            email_count=10,
            percentage=1.0,
            source=CategorySource.CONTENT_CLUSTER,
            distinguishing_features=[],
            example_email_ids=["d", "e", "f"]
        )

        result = calculate_distinctiveness_scores([cat1, cat2])

        assert result["cat1"] == 1.0
        assert result["cat2"] == 1.0

    def test_calculate_distinctiveness_high_overlap_penalized(self):
        """Test that categories with high overlap get lower distinctiveness."""
        from src.generators.confidence_scorer import calculate_distinctiveness_scores

        cat1 = Category(
            category_id="cat1",
            category_name="Cat1",
            description="Test",
            confidence=0.5,
            email_count=10,
            percentage=1.0,
            source=CategorySource.CONTENT_CLUSTER,
            distinguishing_features=[],
            example_email_ids=["a", "b", "c", "d", "e"]
        )
        cat2 = Category(
            category_id="cat2",
            category_name="Cat2",
            description="Test",
            confidence=0.5,
            email_count=10,
            percentage=1.0,
            source=CategorySource.CONTENT_CLUSTER,
            distinguishing_features=[],
            example_email_ids=["a", "b", "c", "d", "e"]  # 100% overlap
        )

        result = calculate_distinctiveness_scores([cat1, cat2])

        # High overlap should result in low distinctiveness
        assert result["cat1"] < 0.5
        assert result["cat2"] < 0.5
