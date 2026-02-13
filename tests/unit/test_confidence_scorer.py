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

        # Template source = 0.9, volume log10(151)/log10(101) capped at 1.0,
        # percentage min(1.0, 15/10) = 1.0
        # Expected: avg(1.0, 0.9, 1.0) = 0.9667
        assert 0.96 <= score <= 0.97

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

        # Cluster source = 0.8, volume log10(51)/log10(101) ≈ 0.852,
        # percentage min(1.0, 5/10) = 0.5
        # Expected: avg(0.852, 0.8, 0.5) ≈ 0.717
        assert 0.71 <= score <= 0.73

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

        # Sender source = 0.7, volume log10(11)/log10(101) ≈ 0.520,
        # percentage min(1.0, 1/10) = 0.1
        # Expected: avg(0.520, 0.7, 0.1) ≈ 0.440
        assert 0.43 <= score <= 0.45

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

        # Custom source = 0.5, volume log10(3)/log10(101) ≈ 0.238,
        # percentage min(1.0, 0.2/10) = 0.02
        # Expected: avg(0.238, 0.5, 0.02) ≈ 0.253
        assert 0.25 <= score <= 0.26

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

    def test_volume_score_capped_at_high_count(self):
        """Test that volume score caps at 1.0 even with very high email count."""
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

        # Volume log10(501)/log10(101) capped at 1.0, percentage capped at 1.0
        # Expected: avg(1.0, 0.9, 1.0) ≈ 0.967
        assert 0.96 <= score <= 0.97

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

        # Volume log10(51)/log10(101) ≈ 0.852, source = 0.8,
        # percentage min(1.0, 50/10) capped at 1.0
        # Expected: avg(0.852, 0.8, 1.0) ≈ 0.884
        assert 0.88 <= score <= 0.89

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


# =============================================================================
# Work Item 4.1: Improved Confidence Scoring Tests
# =============================================================================


class TestLogarithmicVolumeScaling:
    """Test logarithmic volume scaling: min(1.0, log10(count+1)/log10(101))."""

    def test_volume_100_emails_equals_one(self):
        """100 emails should produce volume score of 1.0."""
        import math
        from src.generators.confidence_scorer import calculate_confidence_enhanced

        category = Category(
            category_id="vol_100",
            category_name="Test",
            description="Test",
            confidence=0.0,
            email_count=100,
            percentage=10.0,
            source=CategorySource.TEMPLATE,
            distinguishing_features=[]
        )
        _, breakdown = calculate_confidence_enhanced(category, total_emails=1000)

        # log10(101)/log10(101) = 1.0
        assert abs(breakdown["volume"] - 1.0) < 0.001

    def test_volume_10_emails_about_half(self):
        """10 emails should produce volume score of approximately 0.52."""
        from src.generators.confidence_scorer import calculate_confidence_enhanced

        category = Category(
            category_id="vol_10",
            category_name="Test",
            description="Test",
            confidence=0.0,
            email_count=10,
            percentage=5.0,
            source=CategorySource.TEMPLATE,
            distinguishing_features=[]
        )
        _, breakdown = calculate_confidence_enhanced(category, total_emails=200)

        # log10(11)/log10(101) ≈ 0.5195
        assert 0.50 <= breakdown["volume"] <= 0.54

    def test_volume_1_email_low_but_nonzero(self):
        """1 email should produce a low but nonzero volume score."""
        from src.generators.confidence_scorer import calculate_confidence_enhanced

        category = Category(
            category_id="vol_1",
            category_name="Test",
            description="Test",
            confidence=0.0,
            email_count=1,
            percentage=0.5,
            source=CategorySource.TEMPLATE,
            distinguishing_features=[]
        )
        _, breakdown = calculate_confidence_enhanced(category, total_emails=200)

        # log10(2)/log10(101) ≈ 0.150
        assert 0.14 <= breakdown["volume"] <= 0.16

    def test_volume_0_emails_is_zero(self):
        """0 emails should produce volume score of 0.0."""
        from src.generators.confidence_scorer import calculate_confidence_enhanced

        category = Category(
            category_id="vol_0",
            category_name="Test",
            description="Test",
            confidence=0.0,
            email_count=0,
            percentage=0.0,
            source=CategorySource.TEMPLATE,
            distinguishing_features=[]
        )
        _, breakdown = calculate_confidence_enhanced(category, total_emails=200)

        # log10(1)/log10(101) = 0.0
        assert breakdown["volume"] == 0.0

    def test_volume_above_100_still_capped(self):
        """Email counts above 100 should still cap at 1.0."""
        from src.generators.confidence_scorer import calculate_confidence_enhanced

        category = Category(
            category_id="vol_1000",
            category_name="Test",
            description="Test",
            confidence=0.0,
            email_count=1000,
            percentage=50.0,
            source=CategorySource.TEMPLATE,
            distinguishing_features=[]
        )
        _, breakdown = calculate_confidence_enhanced(category, total_emails=2000)

        assert breakdown["volume"] == 1.0


class TestPercentageScoring:
    """Test percentage scoring: min(1.0, percentage / 10.0)."""

    def test_10_percent_category_scores_one(self):
        """A category at 10% of corpus should get percentage score of 1.0."""
        from src.generators.confidence_scorer import calculate_confidence_enhanced

        category = Category(
            category_id="pct_10",
            category_name="Test",
            description="Test",
            confidence=0.0,
            email_count=100,
            percentage=10.0,
            source=CategorySource.TEMPLATE,
            distinguishing_features=[]
        )
        _, breakdown = calculate_confidence_enhanced(category, total_emails=1000)

        assert abs(breakdown["percentage"] - 1.0) < 0.001

    def test_5_percent_category_scores_half(self):
        """A category at 5% of corpus should get percentage score of 0.5."""
        from src.generators.confidence_scorer import calculate_confidence_enhanced

        category = Category(
            category_id="pct_5",
            category_name="Test",
            description="Test",
            confidence=0.0,
            email_count=50,
            percentage=5.0,
            source=CategorySource.TEMPLATE,
            distinguishing_features=[]
        )
        _, breakdown = calculate_confidence_enhanced(category, total_emails=1000)

        assert abs(breakdown["percentage"] - 0.5) < 0.001

    def test_1_percent_category_scores_tenth(self):
        """A category at 1% of corpus should get percentage score of 0.1."""
        from src.generators.confidence_scorer import calculate_confidence_enhanced

        category = Category(
            category_id="pct_1",
            category_name="Test",
            description="Test",
            confidence=0.0,
            email_count=10,
            percentage=1.0,
            source=CategorySource.TEMPLATE,
            distinguishing_features=[]
        )
        _, breakdown = calculate_confidence_enhanced(category, total_emails=1000)

        assert abs(breakdown["percentage"] - 0.1) < 0.001

    def test_above_10_percent_capped_at_one(self):
        """Percentages above 10% should cap at 1.0."""
        from src.generators.confidence_scorer import calculate_confidence_enhanced

        category = Category(
            category_id="pct_50",
            category_name="Test",
            description="Test",
            confidence=0.0,
            email_count=500,
            percentage=50.0,
            source=CategorySource.TEMPLATE,
            distinguishing_features=[]
        )
        _, breakdown = calculate_confidence_enhanced(category, total_emails=1000)

        assert breakdown["percentage"] == 1.0


class TestMeanOverlapDistinctiveness:
    """Test that distinctiveness uses mean overlap instead of max overlap."""

    def test_mean_overlap_with_mixed_overlaps(self):
        """Distinctiveness should use mean, not max, when multiple overlaps exist."""
        from src.generators.confidence_scorer import calculate_confidence_enhanced

        category = Category(
            category_id="test_mean",
            category_name="Test",
            description="Test",
            confidence=0.0,
            email_count=50,
            percentage=5.0,
            source=CategorySource.TEMPLATE,
            distinguishing_features=[]
        )

        # One high overlap, one low overlap
        # max would give 1.0 - 0.9 = 0.1
        # mean gives 1.0 - (0.9 + 0.1) / 2 = 1.0 - 0.5 = 0.5
        overlap_scores = {"cat_high": 0.9, "cat_low": 0.1}

        _, breakdown = calculate_confidence_enhanced(
            category, total_emails=1000, overlap_scores=overlap_scores
        )

        assert abs(breakdown["distinctiveness"] - 0.5) < 0.001

    def test_mean_overlap_single_category_same_as_max(self):
        """With only one other category, mean and max are the same."""
        from src.generators.confidence_scorer import calculate_confidence_enhanced

        category = Category(
            category_id="test_single",
            category_name="Test",
            description="Test",
            confidence=0.0,
            email_count=50,
            percentage=5.0,
            source=CategorySource.TEMPLATE,
            distinguishing_features=[]
        )

        overlap_scores = {"other": 0.6}

        _, breakdown = calculate_confidence_enhanced(
            category, total_emails=1000, overlap_scores=overlap_scores
        )

        # 1.0 - 0.6 = 0.4
        assert abs(breakdown["distinctiveness"] - 0.4) < 0.001

    def test_distinctiveness_uses_mean_in_calculate_distinctiveness_scores(self):
        """calculate_distinctiveness_scores should use mean overlap, not max."""
        from src.generators.confidence_scorer import calculate_distinctiveness_scores

        # 3 categories: cat1 overlaps highly with cat2 but not cat3
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
            example_email_ids=["a", "b", "c", "d", "e"]  # 100% overlap with cat1
        )
        cat3 = Category(
            category_id="cat3",
            category_name="Cat3",
            description="Test",
            confidence=0.5,
            email_count=10,
            percentage=1.0,
            source=CategorySource.CONTENT_CLUSTER,
            distinguishing_features=[],
            example_email_ids=["f", "g", "h", "i", "j"]  # 0% overlap with cat1
        )

        result = calculate_distinctiveness_scores([cat1, cat2, cat3])

        # cat1: overlaps with cat2=1.0, cat3=0.0 -> mean=0.5 -> distinctiveness=0.5
        # With max it would be 1.0-1.0=0.0
        assert abs(result["cat1"] - 0.5) < 0.001

        # cat3: overlaps with cat1=0.0, cat2=0.0 -> mean=0.0 -> distinctiveness=1.0
        assert abs(result["cat3"] - 1.0) < 0.001


class TestSmallCorpusReasonableConfidence:
    """Test that small categories in small corpora get reasonable confidence scores.

    Acceptance criterion: 10-email category in 200-email corpus should NOT
    get a tiny score like 0.05. The new formulas should produce meaningful
    confidence values even for small categories.
    """

    def test_10_emails_in_200_corpus_reasonable_confidence(self):
        """10-email category in 200-email corpus gets reasonable confidence (not 0.05)."""
        category = Category(
            category_id="small_cat",
            category_name="Small Category",
            description="Small but valid category",
            confidence=0.0,
            email_count=10,
            percentage=5.0,  # 10/200 = 5%
            source=CategorySource.CONTENT_CLUSTER,
            distinguishing_features=["feature1", "feature2"]
        )

        score = calculate_confidence(category, total_emails=200)

        # With new formulas:
        # volume = log10(11)/log10(101) ≈ 0.520
        # source = 0.8 (content cluster)
        # percentage = min(1.0, 5/10) = 0.5
        # avg ≈ 0.607
        assert score > 0.30, f"Score {score} is unreasonably low for a 10-email / 200-corpus category"
        assert score < 1.0

    def test_small_corpus_20_emails_total(self):
        """Categories in very small corpus (20 emails) get reasonable scores."""
        category = Category(
            category_id="tiny_corpus",
            category_name="Test",
            description="Test",
            confidence=0.0,
            email_count=5,
            percentage=25.0,  # 5/20 = 25%
            source=CategorySource.SENDER,
            distinguishing_features=["f1"]
        )

        score = calculate_confidence(category, total_emails=20)

        # volume = log10(6)/log10(101) ≈ 0.388
        # source = 0.7
        # percentage = min(1.0, 25/10) = 1.0
        # avg ≈ 0.696
        assert score > 0.40, f"Score {score} too low for 25% of corpus"

    def test_medium_corpus_500_emails(self):
        """Medium corpus scenario: 30 emails in 500 email corpus."""
        category = Category(
            category_id="med_corpus",
            category_name="Test",
            description="Test",
            confidence=0.0,
            email_count=30,
            percentage=6.0,
            source=CategorySource.CONTENT_CLUSTER,
            distinguishing_features=["f1", "f2", "f3"]
        )

        score = calculate_confidence(category, total_emails=500)

        # volume = log10(31)/log10(101) ≈ 0.743
        # source = 0.8
        # percentage = min(1.0, 6/10) = 0.6
        # avg ≈ 0.714
        assert score > 0.50, f"Score {score} too low for 6% of medium corpus"

    def test_large_corpus_5000_emails(self):
        """Large corpus scenario: 100 emails in 5000 email corpus."""
        category = Category(
            category_id="large_corpus",
            category_name="Test",
            description="Test",
            confidence=0.0,
            email_count=100,
            percentage=2.0,
            source=CategorySource.TEMPLATE,
            distinguishing_features=["f1", "f2"]
        )

        score = calculate_confidence(category, total_emails=5000)

        # volume = log10(101)/log10(101) = 1.0
        # source = 0.9
        # percentage = min(1.0, 2/10) = 0.2
        # avg ≈ 0.700
        assert score > 0.50, f"Score {score} too low for 100-email template category"

    def test_enhanced_10_emails_in_200_corpus(self):
        """Enhanced scorer: 10 emails in 200 corpus with features gets decent score."""
        from src.generators.confidence_scorer import calculate_confidence_enhanced

        category = Category(
            category_id="small_enhanced",
            category_name="Test Category",
            description="Test",
            confidence=0.0,
            email_count=10,
            percentage=5.0,
            source=CategorySource.CONTENT_CLUSTER,
            distinguishing_features=["f1", "f2", "f3"],
            name_quality_score=0.7
        )

        score, breakdown = calculate_confidence_enhanced(category, total_emails=200)

        # With 3 features, good name quality, and no overlap penalty:
        # cohesion = 3/5 = 0.6
        # volume ≈ 0.520
        # source = 0.8
        # percentage = 0.5
        # name_quality = 0.7
        # distinctiveness = 1.0
        assert score > 0.30, f"Enhanced score {score} too low for small but valid category"


class TestConfigurableWeights:
    """Test that confidence weights are configurable via GeneratorThresholds."""

    def test_from_thresholds_creates_weights(self):
        """ConfidenceWeights.from_thresholds creates weights from config."""
        from src.generators.confidence_scorer import ConfidenceWeights
        from src.config.models import GeneratorThresholds

        thresholds = GeneratorThresholds()
        weights = ConfidenceWeights.from_thresholds(thresholds)

        assert weights.cohesion == thresholds.confidence_weight_cohesion
        assert weights.volume == thresholds.confidence_weight_volume
        assert weights.source == thresholds.confidence_weight_source
        assert weights.percentage == thresholds.confidence_weight_percentage
        assert weights.name_quality == thresholds.confidence_weight_name_quality
        assert weights.distinctiveness == thresholds.confidence_weight_distinctiveness

    def test_custom_thresholds_produce_different_scores(self):
        """Custom weights from config should produce different scores."""
        from src.generators.confidence_scorer import (
            ConfidenceWeights,
            calculate_confidence_enhanced
        )
        from src.config.models import GeneratorThresholds

        category = Category(
            category_id="config_test",
            category_name="Test",
            description="Test",
            confidence=0.0,
            email_count=50,
            percentage=5.0,
            source=CategorySource.CONTENT_CLUSTER,
            distinguishing_features=["f1", "f2"],
            name_quality_score=0.7
        )

        # Default weights
        default_weights = ConfidenceWeights()
        default_score, _ = calculate_confidence_enhanced(
            category, total_emails=1000, weights=default_weights
        )

        # Volume-heavy weights from config
        heavy_volume_thresholds = GeneratorThresholds(
            confidence_weight_cohesion=0.05,
            confidence_weight_volume=0.60,
            confidence_weight_source=0.10,
            confidence_weight_percentage=0.10,
            confidence_weight_name_quality=0.05,
            confidence_weight_distinctiveness=0.10,
        )
        custom_weights = ConfidenceWeights.from_thresholds(heavy_volume_thresholds)
        custom_score, _ = calculate_confidence_enhanced(
            category, total_emails=1000, weights=custom_weights
        )

        # Scores should differ because volume is emphasized differently
        assert default_score != custom_score

    def test_default_thresholds_match_default_weights(self):
        """Default GeneratorThresholds should produce same weights as ConfidenceWeights()."""
        from src.generators.confidence_scorer import ConfidenceWeights
        from src.config.models import GeneratorThresholds

        default_weights = ConfidenceWeights()
        from_config = ConfidenceWeights.from_thresholds(GeneratorThresholds())

        assert default_weights.cohesion == from_config.cohesion
        assert default_weights.volume == from_config.volume
        assert default_weights.source == from_config.source
        assert default_weights.percentage == from_config.percentage
        assert default_weights.name_quality == from_config.name_quality
        assert default_weights.distinctiveness == from_config.distinctiveness

    def test_generator_thresholds_weight_fields_exist(self):
        """GeneratorThresholds has all confidence_weight_* fields."""
        from src.config.models import GeneratorThresholds

        thresholds = GeneratorThresholds()

        assert hasattr(thresholds, "confidence_weight_cohesion")
        assert hasattr(thresholds, "confidence_weight_volume")
        assert hasattr(thresholds, "confidence_weight_source")
        assert hasattr(thresholds, "confidence_weight_percentage")
        assert hasattr(thresholds, "confidence_weight_name_quality")
        assert hasattr(thresholds, "confidence_weight_distinctiveness")

    def test_generator_thresholds_weights_sum_to_one(self):
        """Default confidence weights from GeneratorThresholds should sum to 1.0."""
        from src.config.models import GeneratorThresholds

        thresholds = GeneratorThresholds()
        total = (
            thresholds.confidence_weight_cohesion +
            thresholds.confidence_weight_volume +
            thresholds.confidence_weight_source +
            thresholds.confidence_weight_percentage +
            thresholds.confidence_weight_name_quality +
            thresholds.confidence_weight_distinctiveness
        )
        assert 0.99 <= total <= 1.01
