"""
Unit tests for category generator modules.

Tests CategoryGenerator class and TemplateMatcher functions for
generating category suggestions from analysis results.
"""
import pytest

from src.generators.category_generator import CategoryGenerator
from src.generators.template_matcher import (
    match_templates,
    _match_by_keywords,
    _match_by_domains,
)
from src.models.analysis_results import (
    AnalysisResults,
    SenderAnalysis,
    SubjectPatterns,
    TemporalPatterns,
    VolumeStats,
    DomainCount,
)
from src.models.category import Category, CategorySource
from src.models.category_template import CategoryTemplate
from src.models.content_cluster import ContentCluster, RepresentativeSample
from src.models.sender import Sender, SenderType


# -----------------------------------------------------------------------------
# Test Fixtures - Sample Data Builders
# -----------------------------------------------------------------------------

def create_sample_sender(
    email: str = "test@example.com",
    domain: str = "example.com",
    sender_type: SenderType = SenderType.SERVICE,
    frequency_count: int = 50,
    sample_subjects: list[str] = None,
    email_ids: list[str] = None,
) -> Sender:
    """Create a sample Sender for testing."""
    return Sender(
        email=email,
        name="Test Sender",
        domain=domain,
        type=sender_type,
        frequency_count=frequency_count,
        sample_subjects=sample_subjects or ["Test subject 1", "Test subject 2"],
        email_ids=email_ids or [f"email_{i}" for i in range(frequency_count)],
    )


def create_sample_cluster(
    cluster_id: int = 0,
    size: int = 100,
    percentage: float = 10.0,
    subjects: list[str] = None,
    body_previews: list[str] = None,
    common_domains: list[tuple[str, int]] = None,
    email_ids: list[str] = None,
) -> ContentCluster:
    """Create a sample ContentCluster for testing."""
    subjects = subjects or ["Test Subject", "Another Subject"]
    body_previews = body_previews or ["Test body preview", "Another body preview"]

    samples = [
        RepresentativeSample(
            subject=subj,
            sender="sender@test.com",
            body_preview=body,
        )
        for subj, body in zip(subjects, body_previews)
    ]

    return ContentCluster(
        cluster_id=cluster_id,
        size=size,
        percentage=percentage,
        representative_samples=samples,
        common_domains=common_domains or [("test.com", 50)],
        email_ids=email_ids or [f"cluster_{cluster_id}_email_{i}" for i in range(size)],
    )


def create_sample_analysis_results(
    total_emails: int = 1000,
    senders: list[Sender] = None,
    clusters: list[ContentCluster] = None,
    top_keywords: list[tuple[str, int]] = None,
) -> AnalysisResults:
    """Create sample AnalysisResults for testing."""
    senders = senders or [create_sample_sender()]
    clusters = clusters or [create_sample_cluster()]
    top_keywords = top_keywords or [("test", 50), ("email", 30)]

    return AnalysisResults(
        sender_analysis=SenderAnalysis(
            top_senders=senders,
            top_domains=[DomainCount(domain="example.com", count=100)],
            unique_senders=len(senders),
            unique_domains=1,
        ),
        subject_patterns=SubjectPatterns(
            common_prefixes={"RE:": 45, "FWD:": 23},
            numbered_patterns={"Invoice": 12, "Order": 34},
            top_keywords=top_keywords,
            bracket_tags=[("URGENT", 12), ("Team", 8)],
            total_subjects_analyzed=total_emails,
        ),
        content_clusters=clusters,
        temporal_patterns=TemporalPatterns(
            frequency_distribution={"daily": 50, "weekly": 30},
            sender_frequencies={},
        ),
        volume_stats=VolumeStats(
            total_emails=total_emails,
            unique_senders=len(senders),
            date_range={"oldest": "2024-01-01", "newest": "2024-12-31", "span_days": "365"},
            with_attachments=100,
            attachment_percentage=10.0,
            avg_body_length_chars=500,
            emails_per_day=2.7,
        ),
    )


# -----------------------------------------------------------------------------
# CategoryGenerator Tests
# -----------------------------------------------------------------------------

class TestCategoryGenerator:
    """Test cases for CategoryGenerator class."""

    def test_generate_suggestions_returns_sorted_by_confidence(self):
        """Test that suggestions are sorted by confidence (highest first)."""
        senders = [
            create_sample_sender(
                email="high@amazon.com",
                domain="amazon.com",
                frequency_count=200,
                email_ids=[f"amazon_{i}" for i in range(200)],
            ),
            create_sample_sender(
                email="low@test.com",
                domain="test.com",
                frequency_count=30,
                email_ids=[f"test_{i}" for i in range(30)],
            ),
        ]
        clusters = [
            create_sample_cluster(
                cluster_id=1,
                size=150,
                percentage=15.0,
                email_ids=[f"cluster1_{i}" for i in range(150)],
            ),
        ]
        analysis = create_sample_analysis_results(
            total_emails=1000,
            senders=senders,
            clusters=clusters,
        )

        generator = CategoryGenerator()
        categories = generator.generate_suggestions(analysis)

        # Verify sorted by confidence descending
        for i in range(len(categories) - 1):
            assert categories[i].confidence >= categories[i + 1].confidence

    def test_generate_suggestions_filters_by_min_cluster_percentage(self):
        """Test that clusters below min percentage are filtered out."""
        clusters = [
            create_sample_cluster(cluster_id=0, size=100, percentage=10.0),
            create_sample_cluster(cluster_id=1, size=30, percentage=3.0),  # Below default 5%
            create_sample_cluster(cluster_id=2, size=50, percentage=5.0),  # At threshold
        ]
        analysis = create_sample_analysis_results(
            total_emails=1000,
            senders=[],
            clusters=clusters,
        )

        generator = CategoryGenerator()
        categories = generator.generate_suggestions(analysis, min_cluster_percentage=5.0)

        # Only clusters with >= 5% should generate categories
        cluster_categories = [c for c in categories if c.source == CategorySource.CONTENT_CLUSTER]
        assert len(cluster_categories) == 2  # 10% and 5% clusters only

    def test_generate_suggestions_filters_by_min_sender_count(self):
        """Test that senders below min count are filtered out."""
        senders = [
            create_sample_sender(
                email="high@test.com",
                domain="test.com",
                frequency_count=50,
                email_ids=[f"high_{i}" for i in range(50)],
            ),
            create_sample_sender(
                email="low@test.com",
                domain="test2.com",
                frequency_count=10,  # Below default 20
                email_ids=[f"low_{i}" for i in range(10)],
            ),
        ]
        analysis = create_sample_analysis_results(
            total_emails=1000,
            senders=senders,
            clusters=[],
        )

        generator = CategoryGenerator()
        categories = generator.generate_suggestions(analysis, min_sender_count=20)

        sender_categories = [c for c in categories if c.source == CategorySource.SENDER]
        assert len(sender_categories) == 1
        assert "Test" in sender_categories[0].category_name

    def test_generate_suggestions_includes_template_categories(self):
        """Test that template matching generates categories."""
        # Create cluster with financial keywords
        clusters = [
            create_sample_cluster(
                cluster_id=0,
                size=100,
                percentage=10.0,
                subjects=["Your invoice is ready", "Payment confirmation"],
                body_previews=["Invoice #12345", "Payment received"],
            ),
        ]
        analysis = create_sample_analysis_results(
            total_emails=1000,
            senders=[],
            clusters=clusters,
        )

        generator = CategoryGenerator()
        categories = generator.generate_suggestions(analysis)

        template_categories = [c for c in categories if c.source == CategorySource.TEMPLATE]
        assert len(template_categories) > 0

    def test_generate_suggestions_empty_analysis(self):
        """Test handling of empty analysis results."""
        analysis = create_sample_analysis_results(
            total_emails=0,
            senders=[],
            clusters=[],
        )

        generator = CategoryGenerator()
        categories = generator.generate_suggestions(analysis)

        # Should return empty or minimal categories (no senders or clusters)
        assert isinstance(categories, list)

    def test_category_from_cluster_generates_valid_category(self):
        """Test cluster-based category creation."""
        cluster = create_sample_cluster(
            cluster_id=5,
            size=100,
            percentage=10.0,
            subjects=["Newsletter Update", "Weekly Digest"],
            body_previews=["Here is your weekly update", "Weekly news"],
            common_domains=[("newsletter.com", 80)],
        )
        analysis = create_sample_analysis_results(clusters=[cluster], senders=[])

        generator = CategoryGenerator()
        category = generator._category_from_cluster(cluster, 1000)

        assert category.category_id == "cluster_5"
        assert category.source == CategorySource.CONTENT_CLUSTER
        assert category.email_count == 100
        assert category.percentage == 10.0
        assert len(category.distinguishing_features) <= 3

    def test_category_from_sender_generates_valid_category(self):
        """Test sender-based category creation."""
        sender = create_sample_sender(
            email="notifications@amazon.com",
            domain="amazon.com",
            frequency_count=150,
        )

        generator = CategoryGenerator()
        category = generator._category_from_sender(sender, 1000)

        assert "amazon" in category.category_id.lower()
        assert category.source == CategorySource.SENDER
        assert category.email_count == 150
        assert category.percentage == 15.0  # 150/1000 * 100
        assert "Amazon" in category.category_name

    def test_category_from_sender_handles_empty_domain(self):
        """Test sender category when domain is empty string."""
        sender = Sender(
            email="test@example.com",
            name="Test",
            domain="",  # Empty domain string
            type=SenderType.SERVICE,
            frequency_count=50,
            sample_subjects=["Test"],
            email_ids=["e1", "e2"],
        )

        generator = CategoryGenerator()
        category = generator._category_from_sender(sender, 1000)

        # Should fall back to email local part for name
        assert "Test" in category.category_name

    def test_generate_cluster_name_uses_domain(self):
        """Test cluster name generation prefers domain."""
        generator = CategoryGenerator()

        name = generator._generate_cluster_name(
            subjects=["Test subject"],
            domains=[("newsletter.com", 100)],
        )

        assert "Newsletter" in name

    def test_generate_cluster_name_fallback_to_subjects(self):
        """Test cluster name generation falls back to subjects."""
        generator = CategoryGenerator()

        name = generator._generate_cluster_name(
            subjects=["Meeting invitation for project", "Project update required"],
            domains=[],
        )

        assert name != "Miscellaneous"

    def test_generate_cluster_name_miscellaneous_fallback(self):
        """Test cluster name generation fallback to Miscellaneous."""
        generator = CategoryGenerator()

        name = generator._generate_cluster_name(
            subjects=["Hi", "Hey"],  # Short words filtered out
            domains=[],
        )

        assert name == "Miscellaneous"

    def test_merge_similar_combines_overlapping_categories(self):
        """Test that similar categories with overlap are merged."""
        categories = [
            Category(
                category_id="cat1",
                category_name="Amazon Emails",
                description="Amazon",
                confidence=0.8,
                email_count=100,
                percentage=10.0,
                source=CategorySource.SENDER,
                example_email_ids=["e1", "e2", "e3", "e4", "e5"],
            ),
            Category(
                category_id="cat2",
                category_name="Amazon Emails Newsletter",
                description="Amazon newsletter",
                confidence=0.6,
                email_count=80,
                percentage=8.0,
                source=CategorySource.TEMPLATE,
                example_email_ids=["e1", "e2", "e3", "e4", "e6"],  # 4/6 overlap = 66%
            ),
        ]

        generator = CategoryGenerator()
        merged = generator._merge_similar(categories)

        # Should not merge because overlap is 66% (below 70% threshold)
        # Let's create categories that will merge
        categories_high_overlap = [
            Category(
                category_id="cat1",
                category_name="Amazon Emails",
                description="Amazon",
                confidence=0.8,
                email_count=100,
                percentage=10.0,
                source=CategorySource.SENDER,
                example_email_ids=["e1", "e2", "e3", "e4", "e5"],
            ),
            Category(
                category_id="cat2",
                category_name="Amazon Emails Promo",
                description="Amazon promo",
                confidence=0.6,
                email_count=80,
                percentage=8.0,
                source=CategorySource.TEMPLATE,
                example_email_ids=["e1", "e2", "e3", "e4", "e5"],  # 100% overlap
            ),
        ]

        merged_high = generator._merge_similar(categories_high_overlap)
        assert len(merged_high) == 1
        assert merged_high[0].confidence == 0.8  # Keeps highest confidence

    def test_merge_similar_preserves_dissimilar_categories(self):
        """Test that dissimilar categories are not merged."""
        categories = [
            Category(
                category_id="cat1",
                category_name="Amazon Emails",
                description="Amazon",
                confidence=0.8,
                email_count=100,
                percentage=10.0,
                source=CategorySource.SENDER,
                example_email_ids=["e1", "e2", "e3"],
            ),
            Category(
                category_id="cat2",
                category_name="Financial Updates",
                description="Banking",
                confidence=0.7,
                email_count=50,
                percentage=5.0,
                source=CategorySource.TEMPLATE,
                example_email_ids=["e4", "e5", "e6"],  # No overlap
            ),
        ]

        generator = CategoryGenerator()
        merged = generator._merge_similar(categories)

        assert len(merged) == 2

    def test_merge_similar_skips_already_merged_indices(self):
        """Test that already-merged categories are skipped in subsequent checks."""
        # Three categories where first merges with second, and third is similar to second
        # but should not be processed again since second is already merged
        categories = [
            Category(
                category_id="cat1",
                category_name="Amazon Orders",
                description="Amazon",
                confidence=0.9,
                email_count=100,
                percentage=10.0,
                source=CategorySource.SENDER,
                example_email_ids=["e1", "e2", "e3", "e4", "e5"],
            ),
            Category(
                category_id="cat2",
                category_name="Amazon Orders Promo",  # Similar to cat1
                description="Amazon promo",
                confidence=0.7,
                email_count=80,
                percentage=8.0,
                source=CategorySource.TEMPLATE,
                example_email_ids=["e1", "e2", "e3", "e4", "e5"],  # 100% overlap with cat1
            ),
            Category(
                category_id="cat3",
                category_name="Amazon Orders Newsletter",  # Also similar to cat1 and cat2
                description="Amazon newsletter",
                confidence=0.6,
                email_count=70,
                percentage=7.0,
                source=CategorySource.TEMPLATE,
                example_email_ids=["e1", "e2", "e3", "e4", "e5"],  # 100% overlap
            ),
        ]

        generator = CategoryGenerator()
        merged = generator._merge_similar(categories)

        # All three should merge into one (the highest confidence one)
        assert len(merged) == 1
        assert merged[0].confidence == 0.9

    def test_merge_similar_inner_loop_skips_previously_merged(self):
        """Test that inner loop skips categories merged in earlier outer iterations.

        This tests the continue statement on line 150 specifically - where
        the inner loop encounters a category that was already merged during
        a prior outer loop iteration.
        """
        # Set up 4 categories:
        # - cat0 (Amazon) will merge with cat2 (Amazon Newsletter) - skipping cat1 (different name)
        # - cat1 (Netflix) will try to check cat2, but cat2 is already merged with cat0
        categories = [
            Category(
                category_id="cat0",
                category_name="Amazon Orders",
                description="Amazon",
                confidence=0.9,
                email_count=100,
                percentage=10.0,
                source=CategorySource.SENDER,
                example_email_ids=["a1", "a2", "a3", "a4", "a5"],
            ),
            Category(
                category_id="cat1",
                category_name="Netflix",  # Different name from Amazon
                description="Netflix",
                confidence=0.8,
                email_count=90,
                percentage=9.0,
                source=CategorySource.SENDER,
                example_email_ids=["a1", "a2", "a3", "a4", "a5"],  # Same emails (high overlap)
            ),
            Category(
                category_id="cat2",
                category_name="Amazon",  # Similar to cat0
                description="Amazon Newsletter",
                confidence=0.7,
                email_count=80,
                percentage=8.0,
                source=CategorySource.TEMPLATE,
                example_email_ids=["a1", "a2", "a3", "a4", "a5"],  # Same emails (high overlap)
            ),
        ]

        generator = CategoryGenerator()
        merged = generator._merge_similar(categories)

        # Expected behavior:
        # - i=0 (Amazon Orders): checks j=1 (Netflix) - not similar name, skip
        #                        checks j=2 (Amazon) - similar name, high overlap -> merge
        #                        merged_indices now has {2}
        # - i=1 (Netflix): 1 not in merged_indices, processes
        #                  checks j=2 (Amazon) - but 2 is in merged_indices -> continue (line 150)
        #                  no merge found, Netflix stays separate
        # - i=2 (Amazon): 2 is in merged_indices -> skip entire iteration

        # Result: 2 categories (merged Amazon, standalone Netflix)
        assert len(merged) == 2

    def test_names_similar_exact_match(self):
        """Test name similarity for exact matches."""
        generator = CategoryGenerator()

        assert generator._names_similar("Amazon", "Amazon")
        assert generator._names_similar("amazon", "AMAZON")

    def test_names_similar_substring_match(self):
        """Test name similarity for substring matches."""
        generator = CategoryGenerator()

        assert generator._names_similar("Amazon", "Amazon Emails")
        assert generator._names_similar("Amazon Newsletter", "Amazon")

    def test_names_similar_different_names(self):
        """Test name similarity returns False for different names."""
        generator = CategoryGenerator()

        assert not generator._names_similar("Amazon", "Netflix")
        assert not generator._names_similar("Financial", "Social Media")

    def test_calculate_overlap_full_overlap(self):
        """Test overlap calculation with identical sets."""
        generator = CategoryGenerator()

        overlap = generator._calculate_overlap({"a", "b", "c"}, {"a", "b", "c"})
        assert overlap == 1.0

    def test_calculate_overlap_no_overlap(self):
        """Test overlap calculation with disjoint sets."""
        generator = CategoryGenerator()

        overlap = generator._calculate_overlap({"a", "b"}, {"c", "d"})
        assert overlap == 0.0

    def test_calculate_overlap_partial_overlap(self):
        """Test overlap calculation with partial intersection."""
        generator = CategoryGenerator()

        overlap = generator._calculate_overlap({"a", "b", "c"}, {"b", "c", "d"})
        # intersection = 2, union = 4, overlap = 0.5
        assert overlap == 0.5

    def test_calculate_overlap_empty_sets(self):
        """Test overlap calculation with empty sets."""
        generator = CategoryGenerator()

        assert generator._calculate_overlap(set(), {"a"}) == 0.0
        assert generator._calculate_overlap({"a"}, set()) == 0.0
        assert generator._calculate_overlap(set(), set()) == 0.0

    def test_apply_templates_delegates_to_matcher(self):
        """Test that apply_templates calls the template matcher."""
        clusters = [
            create_sample_cluster(
                cluster_id=0,
                size=100,
                percentage=10.0,
                subjects=["Order shipped", "Delivery update"],
                body_previews=["Your order has shipped", "Package delivery"],
            ),
        ]
        analysis = create_sample_analysis_results(clusters=clusters, senders=[])

        generator = CategoryGenerator()
        template_categories = generator.apply_templates(analysis)

        assert isinstance(template_categories, list)

    def test_score_confidence_delegates_to_scorer(self):
        """Test that score_confidence calls the confidence scorer."""
        category = Category(
            category_id="test",
            category_name="Test",
            description="Test",
            confidence=0.0,
            email_count=100,
            percentage=10.0,
            source=CategorySource.TEMPLATE,
        )

        generator = CategoryGenerator()
        score = generator.score_confidence(category, 1000)

        assert 0.0 <= score <= 1.0


class TestCategoryGeneratorReport:
    """Test cases for CategoryGenerator.generate_report method."""

    def test_generate_report_returns_markdown(self):
        """Test that report is markdown formatted."""
        categories = [
            Category(
                category_id="cat1",
                category_name="Test Category",
                description="A test category",
                confidence=0.85,
                email_count=100,
                percentage=10.0,
                source=CategorySource.TEMPLATE,
                distinguishing_features=["feature1", "feature2"],
            ),
        ]

        generator = CategoryGenerator()
        report = generator.generate_report(categories)

        assert "# Email Category Suggestions Report" in report
        assert "## 1. Test Category" in report
        assert "**Confidence**: 85.0%" in report
        assert "**Email Count**: 100" in report

    def test_generate_report_empty_categories(self):
        """Test report generation with no categories."""
        generator = CategoryGenerator()
        report = generator.generate_report([])

        assert "**Total Categories**: 0" in report

    def test_generate_report_includes_features(self):
        """Test that distinguishing features are included."""
        categories = [
            Category(
                category_id="cat1",
                category_name="Financial",
                description="Banking emails",
                confidence=0.75,
                email_count=50,
                percentage=5.0,
                source=CategorySource.TEMPLATE,
                distinguishing_features=["invoice", "payment", "statement"],
            ),
        ]

        generator = CategoryGenerator()
        report = generator.generate_report(categories)

        assert "**Key Features**:" in report
        assert "- invoice" in report
        assert "- payment" in report

    def test_generate_report_limits_features(self):
        """Test that only top 5 features are shown."""
        categories = [
            Category(
                category_id="cat1",
                category_name="Test",
                description="Test",
                confidence=0.5,
                email_count=10,
                percentage=1.0,
                source=CategorySource.CUSTOM,
                distinguishing_features=["f1", "f2", "f3", "f4", "f5", "f6", "f7"],
            ),
        ]

        generator = CategoryGenerator()
        report = generator.generate_report(categories)

        # Should only show first 5 features
        assert "- f5" in report
        assert "- f6" not in report

    def test_generate_report_multiple_categories(self):
        """Test report with multiple categories."""
        categories = [
            Category(
                category_id="cat1",
                category_name="First Category",
                description="First",
                confidence=0.9,
                email_count=200,
                percentage=20.0,
                source=CategorySource.TEMPLATE,
            ),
            Category(
                category_id="cat2",
                category_name="Second Category",
                description="Second",
                confidence=0.7,
                email_count=100,
                percentage=10.0,
                source=CategorySource.SENDER,
            ),
        ]

        generator = CategoryGenerator()
        report = generator.generate_report(categories)

        assert "## 1. First Category" in report
        assert "## 2. Second Category" in report
        assert "**Total Categories**: 2" in report


# -----------------------------------------------------------------------------
# TemplateMatcher Tests
# -----------------------------------------------------------------------------

class TestTemplateMatcher:
    """Test cases for template matching functions."""

    def test_match_templates_with_keyword_match(self):
        """Test template matching via keywords in cluster samples."""
        clusters = [
            create_sample_cluster(
                cluster_id=0,
                size=100,
                percentage=10.0,
                subjects=["Invoice #12345", "Payment received"],
                body_previews=["Your invoice is attached", "Payment confirmed"],
            ),
        ]
        analysis = create_sample_analysis_results(
            clusters=clusters,
            senders=[],
        )
        templates = [
            CategoryTemplate(
                name="Financial",
                keywords=["invoice", "payment", "bank"],
                domains=[],
                description="Financial emails",
            ),
        ]

        categories = match_templates(analysis, templates)

        assert len(categories) == 1
        assert categories[0].category_name == "Financial"
        assert categories[0].source == CategorySource.TEMPLATE
        assert categories[0].email_count == 100

    def test_match_templates_with_domain_match(self):
        """Test template matching via sender domains."""
        senders = [
            create_sample_sender(
                email="orders@amazon.com",
                domain="amazon.com",
                frequency_count=50,
                email_ids=[f"amazon_{i}" for i in range(50)],
            ),
        ]
        analysis = create_sample_analysis_results(
            senders=senders,
            clusters=[],
        )
        templates = [
            CategoryTemplate(
                name="Shopping",
                keywords=["nonmatchingkeyword"],  # Keywords required but won't match
                domains=["amazon.com", "ebay.com"],
                description="Shopping emails",
            ),
        ]

        categories = match_templates(analysis, templates)

        assert len(categories) == 1
        assert categories[0].category_name == "Shopping"
        assert categories[0].email_count == 50

    def test_match_templates_combined_keyword_and_domain(self):
        """Test matching combines keyword and domain matches."""
        senders = [
            create_sample_sender(
                email="orders@amazon.com",
                domain="amazon.com",
                frequency_count=30,
                email_ids=[f"amazon_{i}" for i in range(30)],
            ),
        ]
        clusters = [
            create_sample_cluster(
                cluster_id=0,
                size=50,
                percentage=5.0,
                subjects=["Order shipped", "Your order is ready"],
                body_previews=["Order #123 shipped", "Ready for pickup"],
                email_ids=[f"order_{i}" for i in range(50)],
            ),
        ]
        analysis = create_sample_analysis_results(
            senders=senders,
            clusters=clusters,
        )
        templates = [
            CategoryTemplate(
                name="Shopping",
                keywords=["order", "shipped"],
                domains=["amazon.com"],
                description="Shopping emails",
            ),
        ]

        categories = match_templates(analysis, templates)

        assert len(categories) == 1
        # Should combine both domain and keyword matches
        assert categories[0].email_count >= 50

    def test_match_templates_no_matches(self):
        """Test that no categories generated when no matches."""
        clusters = [
            create_sample_cluster(
                cluster_id=0,
                size=100,
                percentage=10.0,
                subjects=["Hello world", "Test message"],
                body_previews=["Just testing", "Another test"],
            ),
        ]
        analysis = create_sample_analysis_results(
            clusters=clusters,
            senders=[],
        )
        templates = [
            CategoryTemplate(
                name="Financial",
                keywords=["invoice", "payment", "bank"],
                domains=["bank.com"],
                description="Financial emails",
            ),
        ]

        categories = match_templates(analysis, templates)

        assert len(categories) == 0

    def test_match_templates_default_templates(self):
        """Test matching with default PREDEFINED_TEMPLATES."""
        clusters = [
            create_sample_cluster(
                cluster_id=0,
                size=100,
                percentage=10.0,
                subjects=["Your flight confirmation", "Hotel booking confirmed"],
                body_previews=["Flight itinerary", "Reservation details"],
            ),
        ]
        analysis = create_sample_analysis_results(
            clusters=clusters,
            senders=[],
        )

        # Use None to trigger default templates
        categories = match_templates(analysis, None)

        # Should match Travel template
        travel_cats = [c for c in categories if "Travel" in c.category_name]
        assert len(travel_cats) >= 1

    def test_match_templates_confidence_scaling(self):
        """Test that confidence is scaled based on percentage."""
        clusters = [
            create_sample_cluster(
                cluster_id=0,
                size=500,
                percentage=50.0,  # High percentage
                subjects=["Invoice attached"],
                body_previews=["Payment due"],
            ),
        ]
        analysis = create_sample_analysis_results(
            total_emails=1000,
            clusters=clusters,
            senders=[],
        )
        templates = [
            CategoryTemplate(
                name="Financial",
                keywords=["invoice", "payment"],
                domains=[],
                description="Financial",
            ),
        ]

        categories = match_templates(analysis, templates)

        assert len(categories) == 1
        # Confidence should be capped at 0.9 for high percentage
        assert categories[0].confidence == 0.9

    def test_match_templates_minimum_confidence(self):
        """Test that confidence has minimum floor."""
        clusters = [
            create_sample_cluster(
                cluster_id=0,
                size=1,
                percentage=0.1,  # Very low percentage
                subjects=["Invoice"],
                body_previews=["Payment"],
            ),
        ]
        analysis = create_sample_analysis_results(
            total_emails=1000,
            clusters=clusters,
            senders=[],
        )
        templates = [
            CategoryTemplate(
                name="Financial",
                keywords=["invoice"],
                domains=[],
                description="Financial",
            ),
        ]

        categories = match_templates(analysis, templates)

        assert len(categories) == 1
        # Confidence should have floor at 0.1
        assert categories[0].confidence >= 0.1

    def test_match_templates_category_id_generation(self):
        """Test that category IDs are properly generated from names."""
        clusters = [
            create_sample_cluster(
                cluster_id=0,
                size=100,
                percentage=10.0,
                subjects=["Password reset"],
                body_previews=["Security alert"],
            ),
        ]
        analysis = create_sample_analysis_results(
            clusters=clusters,
            senders=[],
        )
        templates = [
            CategoryTemplate(
                name="Account & Security",
                keywords=["password", "security"],
                domains=[],
                description="Security emails",
            ),
        ]

        categories = match_templates(analysis, templates)

        assert len(categories) == 1
        assert categories[0].category_id == "account_and_security"

    def test_match_templates_example_email_ids_limited(self):
        """Test that example email IDs are limited to 10."""
        clusters = [
            create_sample_cluster(
                cluster_id=0,
                size=100,
                percentage=10.0,
                subjects=["Invoice"],
                body_previews=["Payment"],
                email_ids=[f"email_{i}" for i in range(100)],
            ),
        ]
        analysis = create_sample_analysis_results(
            clusters=clusters,
            senders=[],
        )
        templates = [
            CategoryTemplate(
                name="Financial",
                keywords=["invoice"],
                domains=[],
                description="Financial",
            ),
        ]

        categories = match_templates(analysis, templates)

        assert len(categories) == 1
        assert len(categories[0].example_email_ids) <= 10


class TestMatchByKeywords:
    """Test cases for _match_by_keywords helper function."""

    def test_match_by_keywords_subject_match(self):
        """Test keyword matching in subject lines."""
        clusters = [
            create_sample_cluster(
                cluster_id=0,
                size=50,
                percentage=5.0,
                subjects=["Your invoice is ready", "Another subject"],
                body_previews=["Preview 1", "Preview 2"],
                email_ids=["e1", "e2", "e3"],
            ),
        ]
        analysis = create_sample_analysis_results(clusters=clusters, senders=[])

        matches = _match_by_keywords(analysis, ["invoice"])

        assert "e1" in matches
        assert len(matches) == 3  # All cluster emails matched

    def test_match_by_keywords_body_match(self):
        """Test keyword matching in body previews."""
        clusters = [
            create_sample_cluster(
                cluster_id=0,
                size=30,
                percentage=3.0,
                subjects=["Hello", "Hi there"],
                body_previews=["Payment received for order", "Thanks"],
                email_ids=["b1", "b2"],
            ),
        ]
        analysis = create_sample_analysis_results(clusters=clusters, senders=[])

        matches = _match_by_keywords(analysis, ["payment"])

        assert len(matches) == 2

    def test_match_by_keywords_case_insensitive(self):
        """Test that keyword matching is case-insensitive."""
        clusters = [
            create_sample_cluster(
                cluster_id=0,
                size=20,
                percentage=2.0,
                subjects=["INVOICE ATTACHED", "Invoice Ready"],
                body_previews=["Preview", "Preview"],
                email_ids=["c1", "c2"],
            ),
        ]
        analysis = create_sample_analysis_results(clusters=clusters, senders=[])

        matches = _match_by_keywords(analysis, ["invoice"])

        assert len(matches) == 2

    def test_match_by_keywords_no_matches(self):
        """Test when no keywords match."""
        clusters = [
            create_sample_cluster(
                cluster_id=0,
                size=20,
                percentage=2.0,
                subjects=["Hello world", "Test email"],
                body_previews=["Testing", "More testing"],
            ),
        ]
        analysis = create_sample_analysis_results(clusters=clusters, senders=[])

        matches = _match_by_keywords(analysis, ["invoice", "payment"])

        assert len(matches) == 0

    def test_match_by_keywords_multiple_clusters(self):
        """Test matching across multiple clusters."""
        clusters = [
            create_sample_cluster(
                cluster_id=0,
                size=30,
                percentage=3.0,
                subjects=["Invoice #1"],
                body_previews=["Payment due"],
                email_ids=[f"cluster0_{i}" for i in range(30)],
            ),
            create_sample_cluster(
                cluster_id=1,
                size=20,
                percentage=2.0,
                subjects=["Hello"],
                body_previews=["Testing"],
                email_ids=[f"cluster1_{i}" for i in range(20)],
            ),
            create_sample_cluster(
                cluster_id=2,
                size=25,
                percentage=2.5,
                subjects=["Your payment confirmation"],
                body_previews=["Thanks"],
                email_ids=[f"cluster2_{i}" for i in range(25)],
            ),
        ]
        analysis = create_sample_analysis_results(clusters=clusters, senders=[])

        matches = _match_by_keywords(analysis, ["invoice", "payment"])

        # Should match cluster 0 and cluster 2
        assert len(matches) == 55  # 30 + 25


class TestMatchByDomains:
    """Test cases for _match_by_domains helper function."""

    def test_match_by_domains_exact_match(self):
        """Test exact domain matching."""
        senders = [
            create_sample_sender(
                email="orders@amazon.com",
                domain="amazon.com",
                frequency_count=50,
                email_ids=[f"amazon_{i}" for i in range(50)],
            ),
        ]
        analysis = create_sample_analysis_results(senders=senders, clusters=[])

        matches = _match_by_domains(analysis, ["amazon.com"])

        assert len(matches) == 50

    def test_match_by_domains_partial_match(self):
        """Test partial domain matching."""
        senders = [
            create_sample_sender(
                email="mail@mail.amazon.com",
                domain="mail.amazon.com",
                frequency_count=30,
                email_ids=[f"amazon_mail_{i}" for i in range(30)],
            ),
        ]
        analysis = create_sample_analysis_results(senders=senders, clusters=[])

        matches = _match_by_domains(analysis, ["amazon.com"])

        # mail.amazon.com contains amazon.com
        assert len(matches) == 30

    def test_match_by_domains_case_insensitive(self):
        """Test that domain matching is case-insensitive."""
        senders = [
            create_sample_sender(
                email="test@AMAZON.COM",
                domain="AMAZON.COM",
                frequency_count=20,
                email_ids=["d1", "d2"],
            ),
        ]
        analysis = create_sample_analysis_results(senders=senders, clusters=[])

        matches = _match_by_domains(analysis, ["amazon.com"])

        assert len(matches) == 2

    def test_match_by_domains_cluster_common_domains(self):
        """Test matching through cluster common domains."""
        clusters = [
            create_sample_cluster(
                cluster_id=0,
                size=40,
                percentage=4.0,
                common_domains=[("amazon.com", 35)],
                email_ids=[f"cluster_{i}" for i in range(40)],
            ),
        ]
        analysis = create_sample_analysis_results(clusters=clusters, senders=[])

        matches = _match_by_domains(analysis, ["amazon.com"])

        assert len(matches) == 40

    def test_match_by_domains_no_matches(self):
        """Test when no domains match."""
        senders = [
            create_sample_sender(
                email="test@example.com",
                domain="example.com",
                frequency_count=50,
            ),
        ]
        analysis = create_sample_analysis_results(senders=senders, clusters=[])

        matches = _match_by_domains(analysis, ["amazon.com", "ebay.com"])

        assert len(matches) == 0

    def test_match_by_domains_multiple_senders(self):
        """Test matching across multiple senders."""
        senders = [
            create_sample_sender(
                email="orders@amazon.com",
                domain="amazon.com",
                frequency_count=30,
                email_ids=[f"amazon_{i}" for i in range(30)],
            ),
            create_sample_sender(
                email="support@ebay.com",
                domain="ebay.com",
                frequency_count=20,
                email_ids=[f"ebay_{i}" for i in range(20)],
            ),
            create_sample_sender(
                email="test@gmail.com",
                domain="gmail.com",
                frequency_count=50,
                email_ids=[f"gmail_{i}" for i in range(50)],
            ),
        ]
        analysis = create_sample_analysis_results(senders=senders, clusters=[])

        matches = _match_by_domains(analysis, ["amazon.com", "ebay.com"])

        assert len(matches) == 50  # 30 + 20


class TestTemplateMatcherEdgeCases:
    """Test edge cases and boundary conditions for template matching."""

    def test_empty_templates_list(self):
        """Test with empty templates list."""
        analysis = create_sample_analysis_results()

        categories = match_templates(analysis, [])

        assert len(categories) == 0

    def test_empty_keywords_and_domains(self):
        """Test template with empty keywords and domains."""
        analysis = create_sample_analysis_results()
        templates = [
            CategoryTemplate(
                name="Empty Template",
                keywords=["nonexistent_keyword_xyz"],  # Won't match
                domains=[],
                description="Empty",
            ),
        ]

        categories = match_templates(analysis, templates)

        assert len(categories) == 0

    def test_zero_total_emails(self):
        """Test with zero total emails in analysis."""
        analysis = create_sample_analysis_results(total_emails=0)
        templates = [
            CategoryTemplate(
                name="Test",
                keywords=["test"],
                domains=[],
                description="Test",
            ),
        ]

        categories = match_templates(analysis, templates)

        # Should handle gracefully
        assert isinstance(categories, list)

    def test_multiple_templates_same_matches(self):
        """Test when multiple templates match same emails."""
        clusters = [
            create_sample_cluster(
                cluster_id=0,
                size=50,
                percentage=5.0,
                subjects=["Invoice for your order shipped"],
                body_previews=["Your order has been shipped. Payment received."],
                email_ids=[f"email_{i}" for i in range(50)],
            ),
        ]
        analysis = create_sample_analysis_results(clusters=clusters, senders=[])
        templates = [
            CategoryTemplate(
                name="Financial",
                keywords=["invoice", "payment"],
                domains=[],
                description="Financial",
            ),
            CategoryTemplate(
                name="Shopping",
                keywords=["order", "shipped"],
                domains=[],
                description="Shopping",
            ),
        ]

        categories = match_templates(analysis, templates)

        # Both templates should match
        assert len(categories) == 2
        category_names = [c.category_name for c in categories]
        assert "Financial" in category_names
        assert "Shopping" in category_names

    def test_special_characters_in_template_name(self):
        """Test category ID generation with special characters."""
        clusters = [
            create_sample_cluster(
                cluster_id=0,
                size=20,
                percentage=2.0,
                subjects=["Password reset request"],
                body_previews=["Reset your password"],
            ),
        ]
        analysis = create_sample_analysis_results(clusters=clusters, senders=[])
        templates = [
            CategoryTemplate(
                name="Account & Security!",
                keywords=["password"],
                domains=[],
                description="Security",
            ),
        ]

        categories = match_templates(analysis, templates)

        assert len(categories) == 1
        # & should be replaced with 'and'
        assert "and" in categories[0].category_id
        assert "&" not in categories[0].category_id

    def test_distinguishing_features_limited_to_five(self):
        """Test that distinguishing features are limited to 5 keywords."""
        clusters = [
            create_sample_cluster(
                cluster_id=0,
                size=50,
                percentage=5.0,
                subjects=["Invoice ready payment bank statement bill credit"],
                body_previews=["Transaction complete"],
            ),
        ]
        analysis = create_sample_analysis_results(clusters=clusters, senders=[])
        templates = [
            CategoryTemplate(
                name="Financial",
                # Use keywords that will match, more than 5
                keywords=["invoice", "payment", "bank", "statement", "bill", "credit", "transaction", "money"],
                domains=[],
                description="Financial",
            ),
        ]

        categories = match_templates(analysis, templates)

        assert len(categories) == 1
        assert len(categories[0].distinguishing_features) <= 5
