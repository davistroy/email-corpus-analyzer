"""
Unit tests for cross-entity validation functions.

Tests the validation functions that ensure data consistency
across Email, Corpus, ContentCluster, and Category entities.
"""
import pytest
from datetime import datetime
from src.utils.validators import (
    validate_corpus_total_matches_length,
    validate_unique_email_ids,
    validate_cluster_percentages_sum_100,
    validate_email_id_references
)
from src.models.email import Email
from src.models.corpus import Corpus, CorpusMetadata
from src.models.content_cluster import ContentCluster
from src.models.category import Category, CategorySource


class TestCorpusValidation:
    """Test cases for Corpus validation."""

    def test_corpus_total_matches_length_valid(self):
        """Test validation passes when total_emails matches list length."""
        corpus = Corpus(
            extraction_metadata=CorpusMetadata(
                extraction_date=datetime.now(),
                total_emails=3,
                source="test",
                user_email="user@example.com"
            ),
            emails=[
                Email(
                    id="1",
                    sender_email="a@example.com",
                    sender_domain="example.com",
                    subject="Test 1",
                    body_text="Body 1",
                    received_date=datetime(2024, 1, 1),
                    has_attachments=False
                ),
                Email(
                    id="2",
                    sender_email="b@example.com",
                    sender_domain="example.com",
                    subject="Test 2",
                    body_text="Body 2",
                    received_date=datetime(2024, 1, 2),
                    has_attachments=False
                ),
                Email(
                    id="3",
                    sender_email="c@example.com",
                    sender_domain="example.com",
                    subject="Test 3",
                    body_text="Body 3",
                    received_date=datetime(2024, 1, 3),
                    has_attachments=False
                )
            ]
        )

        assert validate_corpus_total_matches_length(corpus) is True

    def test_corpus_total_matches_length_invalid_mismatch(self):
        """Test validation fails when total_emails doesn't match list length."""
        corpus = Corpus(
            extraction_metadata=CorpusMetadata(
                extraction_date=datetime.now(),
                total_emails=5,  # Says 5 but only has 2
                source="test",
                user_email="user@example.com"
            ),
            emails=[
                Email(
                    id="1",
                    sender_email="a@example.com",
                    sender_domain="example.com",
                    subject="Test",
                    body_text="Body",
                    received_date=datetime.now(),
                    has_attachments=False
                ),
                Email(
                    id="2",
                    sender_email="b@example.com",
                    sender_domain="example.com",
                    subject="Test",
                    body_text="Body",
                    received_date=datetime.now(),
                    has_attachments=False
                )
            ]
        )

        assert validate_corpus_total_matches_length(corpus) is False

    def test_corpus_total_matches_length_empty_corpus(self):
        """Test validation with empty corpus."""
        corpus = Corpus(
            extraction_metadata=CorpusMetadata(
                extraction_date=datetime.now(),
                total_emails=0,
                source="test",
                user_email="user@example.com"
            ),
            emails=[]
        )

        assert validate_corpus_total_matches_length(corpus) is True

    def test_unique_email_ids_valid(self):
        """Test validation passes when all email IDs are unique."""
        corpus = Corpus(
            extraction_metadata=CorpusMetadata(
                extraction_date=datetime.now(),
                total_emails=3,
                source="test",
                user_email="user@example.com"
            ),
            emails=[
                Email(
                    id="unique_1",
                    sender_email="a@example.com",
                    sender_domain="example.com",
                    subject="Test",
                    body_text="Body",
                    received_date=datetime.now(),
                    has_attachments=False
                ),
                Email(
                    id="unique_2",
                    sender_email="b@example.com",
                    sender_domain="example.com",
                    subject="Test",
                    body_text="Body",
                    received_date=datetime.now(),
                    has_attachments=False
                ),
                Email(
                    id="unique_3",
                    sender_email="c@example.com",
                    sender_domain="example.com",
                    subject="Test",
                    body_text="Body",
                    received_date=datetime.now(),
                    has_attachments=False
                )
            ]
        )

        assert validate_unique_email_ids(corpus) is True

    def test_unique_email_ids_invalid_duplicates(self):
        """Test validation fails when email IDs are duplicated."""
        corpus = Corpus(
            extraction_metadata=CorpusMetadata(
                extraction_date=datetime.now(),
                total_emails=3,
                source="test",
                user_email="user@example.com"
            ),
            emails=[
                Email(
                    id="duplicate_id",
                    sender_email="a@example.com",
                    sender_domain="example.com",
                    subject="Test 1",
                    body_text="Body 1",
                    received_date=datetime.now(),
                    has_attachments=False
                ),
                Email(
                    id="unique_id",
                    sender_email="b@example.com",
                    sender_domain="example.com",
                    subject="Test 2",
                    body_text="Body 2",
                    received_date=datetime.now(),
                    has_attachments=False
                ),
                Email(
                    id="duplicate_id",  # Same as first
                    sender_email="c@example.com",
                    sender_domain="example.com",
                    subject="Test 3",
                    body_text="Body 3",
                    received_date=datetime.now(),
                    has_attachments=False
                )
            ]
        )

        assert validate_unique_email_ids(corpus) is False


class TestClusterValidation:
    """Test cases for ContentCluster validation."""

    def test_cluster_percentages_sum_100_valid(self):
        """Test validation passes when cluster percentages sum to ~100%."""
        clusters = [
            ContentCluster(
                cluster_id=0,
                size=45,
                percentage=45.0,
                representative_samples=[],
                common_keywords=[],
                common_domains=[],
                email_ids=[]
            ),
            ContentCluster(
                cluster_id=1,
                size=30,
                percentage=30.0,
                representative_samples=[],
                common_keywords=[],
                common_domains=[],
                email_ids=[]
            ),
            ContentCluster(
                cluster_id=2,
                size=25,
                percentage=25.0,
                representative_samples=[],
                common_keywords=[],
                common_domains=[],
                email_ids=[]
            )
        ]

        assert validate_cluster_percentages_sum_100(clusters) is True

    def test_cluster_percentages_sum_100_within_tolerance(self):
        """Test validation passes when sum is within tolerance (98-102%)."""
        # Sum = 98.5% (within 2% tolerance)
        clusters = [
            ContentCluster(
                cluster_id=0,
                size=50,
                percentage=50.0,
                representative_samples=[],
                common_keywords=[],
                common_domains=[],
                email_ids=[]
            ),
            ContentCluster(
                cluster_id=1,
                size=48,
                percentage=48.5,
                representative_samples=[],
                common_keywords=[],
                common_domains=[],
                email_ids=[]
            )
        ]

        assert validate_cluster_percentages_sum_100(clusters, tolerance=2.0) is True

    def test_cluster_percentages_sum_100_invalid_too_low(self):
        """Test validation fails when sum is below tolerance."""
        # Sum = 90% (outside 2% tolerance)
        clusters = [
            ContentCluster(
                cluster_id=0,
                size=50,
                percentage=50.0,
                representative_samples=[],
                common_keywords=[],
                common_domains=[],
                email_ids=[]
            ),
            ContentCluster(
                cluster_id=1,
                size=40,
                percentage=40.0,
                representative_samples=[],
                common_keywords=[],
                common_domains=[],
                email_ids=[]
            )
        ]

        assert validate_cluster_percentages_sum_100(clusters, tolerance=2.0) is False

    def test_cluster_percentages_sum_100_invalid_too_high(self):
        """Test validation fails when sum is above tolerance."""
        # Sum = 110% (outside 2% tolerance)
        clusters = [
            ContentCluster(
                cluster_id=0,
                size=60,
                percentage=60.0,
                representative_samples=[],
                common_keywords=[],
                common_domains=[],
                email_ids=[]
            ),
            ContentCluster(
                cluster_id=1,
                size=50,
                percentage=50.0,
                representative_samples=[],
                common_keywords=[],
                common_domains=[],
                email_ids=[]
            )
        ]

        assert validate_cluster_percentages_sum_100(clusters, tolerance=2.0) is False

    def test_cluster_percentages_empty_list(self):
        """Test validation with empty cluster list."""
        clusters = []
        # Empty list should fail (sum = 0, not ~100)
        assert validate_cluster_percentages_sum_100(clusters) is False


class TestCategoryValidation:
    """Test cases for Category validation."""

    def test_email_id_references_valid(self):
        """Test validation passes when all category email IDs exist in corpus."""
        corpus = Corpus(
            extraction_metadata=CorpusMetadata(
                extraction_date=datetime.now(),
                total_emails=5,
                source="test",
                user_email="user@example.com"
            ),
            emails=[
                Email(
                    id=f"email_{i}",
                    sender_email=f"user{i}@example.com",
                    sender_domain="example.com",
                    subject=f"Test {i}",
                    body_text=f"Body {i}",
                    received_date=datetime.now(),
                    has_attachments=False
                )
                for i in range(1, 6)
            ]
        )

        categories = [
            Category(
                category_id="cat_1",
                category_name="Category 1",
                description="Test",
                confidence=0.8,
                email_count=3,
                percentage=60.0,
                source=CategorySource.CONTENT_CLUSTER,
                example_email_ids=["email_1", "email_2", "email_3"]
            ),
            Category(
                category_id="cat_2",
                category_name="Category 2",
                description="Test",
                confidence=0.7,
                email_count=2,
                percentage=40.0,
                source=CategorySource.SENDER,
                example_email_ids=["email_4", "email_5"]
            )
        ]

        assert validate_email_id_references(categories, corpus) is True

    def test_email_id_references_invalid_missing_ids(self):
        """Test validation fails when category references non-existent email IDs."""
        corpus = Corpus(
            extraction_metadata=CorpusMetadata(
                extraction_date=datetime.now(),
                total_emails=2,
                source="test",
                user_email="user@example.com"
            ),
            emails=[
                Email(
                    id="email_1",
                    sender_email="a@example.com",
                    sender_domain="example.com",
                    subject="Test",
                    body_text="Body",
                    received_date=datetime.now(),
                    has_attachments=False
                ),
                Email(
                    id="email_2",
                    sender_email="b@example.com",
                    sender_domain="example.com",
                    subject="Test",
                    body_text="Body",
                    received_date=datetime.now(),
                    has_attachments=False
                )
            ]
        )

        categories = [
            Category(
                category_id="cat_1",
                category_name="Category 1",
                description="Test",
                confidence=0.8,
                email_count=3,
                percentage=100.0,
                source=CategorySource.TEMPLATE,
                example_email_ids=["email_1", "email_999", "email_888"]  # 999 and 888 don't exist
            )
        ]

        assert validate_email_id_references(categories, corpus) is False

    def test_email_id_references_empty_examples(self):
        """Test validation with categories that have no example_email_ids."""
        corpus = Corpus(
            extraction_metadata=CorpusMetadata(
                extraction_date=datetime.now(),
                total_emails=1,
                source="test",
                user_email="user@example.com"
            ),
            emails=[
                Email(
                    id="email_1",
                    sender_email="a@example.com",
                    sender_domain="example.com",
                    subject="Test",
                    body_text="Body",
                    received_date=datetime.now(),
                    has_attachments=False
                )
            ]
        )

        categories = [
            Category(
                category_id="cat_1",
                category_name="Empty Category",
                description="No examples",
                confidence=0.5,
                source=CategorySource.CUSTOM,
                example_email_ids=[]  # Empty list
            )
        ]

        # Should pass - empty list is valid
        assert validate_email_id_references(categories, corpus) is True

    def test_email_id_references_empty_corpus(self):
        """Test validation fails when corpus is empty but categories have examples."""
        corpus = Corpus(
            extraction_metadata=CorpusMetadata(
                extraction_date=datetime.now(),
                total_emails=0,
                source="test",
                user_email="user@example.com"
            ),
            emails=[]
        )

        categories = [
            Category(
                category_id="cat_1",
                category_name="Category",
                description="Test",
                confidence=0.8,
                source=CategorySource.TEMPLATE,
                example_email_ids=["email_1"]  # References non-existent email
            )
        ]

        assert validate_email_id_references(categories, corpus) is False


class TestValidationIntegration:
    """Integration tests for multiple validators together."""

    def test_fully_valid_dataset(self):
        """Test all validators pass on fully valid dataset."""
        corpus = Corpus(
            extraction_metadata=CorpusMetadata(
                extraction_date=datetime.now(),
                total_emails=4,
                source="test",
                user_email="user@example.com"
            ),
            emails=[
                Email(
                    id=f"email_{i}",
                    sender_email=f"user{i}@example.com",
                    sender_domain="example.com",
                    subject=f"Test {i}",
                    body_text=f"Body {i}",
                    received_date=datetime.now(),
                    has_attachments=False
                )
                for i in range(1, 5)
            ]
        )

        clusters = [
            ContentCluster(
                cluster_id=0,
                size=2,
                percentage=50.0,
                representative_samples=[],
                common_keywords=[],
                common_domains=[],
                email_ids=["email_1", "email_2"]
            ),
            ContentCluster(
                cluster_id=1,
                size=2,
                percentage=50.0,
                representative_samples=[],
                common_keywords=[],
                common_domains=[],
                email_ids=["email_3", "email_4"]
            )
        ]

        categories = [
            Category(
                category_id="cat_1",
                category_name="Category 1",
                description="Test",
                confidence=0.8,
                email_count=2,
                percentage=50.0,
                source=CategorySource.CONTENT_CLUSTER,
                example_email_ids=["email_1", "email_2"]
            )
        ]

        # All validations should pass
        assert validate_corpus_total_matches_length(corpus) is True
        assert validate_unique_email_ids(corpus) is True
        assert validate_cluster_percentages_sum_100(clusters) is True
        assert validate_email_id_references(categories, corpus) is True

    def test_multiple_validation_failures(self):
        """Test multiple validators fail on invalid dataset."""
        # Corpus with wrong total and duplicate IDs
        corpus = Corpus(
            extraction_metadata=CorpusMetadata(
                extraction_date=datetime.now(),
                total_emails=10,  # Wrong - should be 3
                source="test",
                user_email="user@example.com"
            ),
            emails=[
                Email(
                    id="dup_id",  # Duplicate
                    sender_email="a@example.com",
                    sender_domain="example.com",
                    subject="Test",
                    body_text="Body",
                    received_date=datetime.now(),
                    has_attachments=False
                ),
                Email(
                    id="dup_id",  # Duplicate
                    sender_email="b@example.com",
                    sender_domain="example.com",
                    subject="Test",
                    body_text="Body",
                    received_date=datetime.now(),
                    has_attachments=False
                ),
                Email(
                    id="unique_id",
                    sender_email="c@example.com",
                    sender_domain="example.com",
                    subject="Test",
                    body_text="Body",
                    received_date=datetime.now(),
                    has_attachments=False
                )
            ]
        )

        # Clusters that don't sum to 100%
        clusters = [
            ContentCluster(
                cluster_id=0,
                size=1,
                percentage=10.0,  # Too low
                representative_samples=[],
                common_keywords=[],
                common_domains=[],
                email_ids=[]
            )
        ]

        # Category referencing non-existent email
        categories = [
            Category(
                category_id="cat_1",
                category_name="Bad Category",
                description="Test",
                confidence=0.8,
                source=CategorySource.TEMPLATE,
                example_email_ids=["non_existent_id"]
            )
        ]

        # Multiple validations should fail
        assert validate_corpus_total_matches_length(corpus) is False
        assert validate_unique_email_ids(corpus) is False
        assert validate_cluster_percentages_sum_100(clusters) is False
        assert validate_email_id_references(categories, corpus) is False
