"""
Shared pytest fixtures for Email Corpus Analyzer tests.

Provides standardized test data builders and fixtures used across test modules.
Per Phase 6 Track 6C specification.
"""

import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from src.models.analysis_results import (
    AnalysisResults,
    DomainCount,
    SenderAnalysis,
    SubjectPatterns,
    TemporalPatterns,
    VolumeStats,
)
from src.models.category import Category, CategorySource
from src.models.content_cluster import ContentCluster, RepresentativeSample
from src.models.corpus import Corpus, CorpusMetadata
from src.models.email import Email
from src.models.sender import Sender, SenderType

# =============================================================================
# Email and Corpus Fixtures
# =============================================================================


@pytest.fixture
def sample_email():
    """Create a sample Email for testing."""
    return Email(
        id="email_001",
        sender_email="sender@example.com",
        sender_name="Test Sender",
        sender_domain="example.com",
        recipient_email="recipient@example.com",
        recipient_name="Test Recipient",
        subject="Test Email Subject",
        body_text="This is a test email body with some content.",
        received_date=datetime(2024, 1, 15, 10, 30, 0),
        has_attachments=False,
    )


@pytest.fixture
def sample_emails():
    """Create a list of sample emails for testing."""
    return [
        Email(
            id=f"email_{i:03d}",
            sender_email=f"sender{i}@example.com",
            sender_name=f"Sender {i}",
            sender_domain="example.com",
            recipient_email="recipient@example.com",
            recipient_name="Recipient",
            subject=f"Test Subject {i}",
            body_text=f"Test body content for email {i}.",
            received_date=datetime(2024, 1, i % 28 + 1, 10, 30, 0),
            has_attachments=i % 3 == 0,
        )
        for i in range(10)
    ]


@pytest.fixture
def sample_corpus(sample_emails):
    """Create a sample Corpus for testing."""
    return Corpus(
        extraction_metadata=CorpusMetadata(
            extraction_date=datetime(2024, 1, 20, 12, 0, 0),
            total_emails=len(sample_emails),
            source="m365",
            user_email="user@example.com",
        ),
        emails=sample_emails,
    )


@pytest.fixture
def sample_corpus_metadata():
    """Create sample CorpusMetadata for testing."""
    return CorpusMetadata(
        extraction_date=datetime(2024, 1, 20, 12, 0, 0),
        total_emails=100,
        source="m365",
        user_email="user@example.com",
        last_extraction_date=datetime(2024, 1, 19, 12, 0, 0),
        email_ids_hash="abc123def456",
        extraction_params={"batch_size": 500, "checkpoint_interval": 100},
    )


# =============================================================================
# Category Fixtures
# =============================================================================


@pytest.fixture
def sample_category():
    """Create a sample Category for testing."""
    return Category(
        category_id="cat_001",
        category_name="Test Category",
        description="A test category for unit testing",
        confidence=0.85,
        email_count=100,
        percentage=10.0,
        source=CategorySource.CONTENT_CLUSTER,
        source_id="cluster_0",
        distinguishing_features=["feature1", "feature2"],
        example_email_ids=["email_001", "email_002", "email_003"],
    )


@pytest.fixture
def sample_categories():
    """Create a list of sample categories for testing."""
    return [
        Category(
            category_id=f"cat_{i:03d}",
            category_name=f"Category {i}",
            description=f"Description for category {i}",
            confidence=0.7 + (i * 0.05),
            email_count=50 + (i * 10),
            percentage=5.0 + (i * 1.5),
            source=CategorySource.CONTENT_CLUSTER if i % 2 == 0 else CategorySource.SENDER,
            source_id=f"source_{i}",
            distinguishing_features=[f"feature_{i}_a", f"feature_{i}_b"],
            example_email_ids=[f"email_{i}_{j}" for j in range(3)],
        )
        for i in range(5)
    ]


@pytest.fixture
def sample_hierarchical_categories():
    """Create sample hierarchical categories with parent-child relationships."""
    child1 = Category(
        category_id="child_001",
        category_name="Child Category 1",
        description="A child category",
        confidence=0.80,
        email_count=30,
        percentage=3.0,
        source=CategorySource.CONTENT_CLUSTER,
        parent_category_id="parent_001",
        level=1,
    )
    child2 = Category(
        category_id="child_002",
        category_name="Child Category 2",
        description="Another child category",
        confidence=0.75,
        email_count=25,
        percentage=2.5,
        source=CategorySource.CONTENT_CLUSTER,
        parent_category_id="parent_001",
        level=1,
    )
    parent = Category(
        category_id="parent_001",
        category_name="Parent Category",
        description="A parent category with children",
        confidence=0.85,
        email_count=100,
        percentage=10.0,
        source=CategorySource.CONTENT_CLUSTER,
        level=0,
        subcategories=[child1, child2],
    )
    return [parent, child1, child2]


# =============================================================================
# Analysis Results Fixtures
# =============================================================================


@pytest.fixture
def sample_sender():
    """Create a sample Sender for testing."""
    return Sender(
        email="sender@example.com",
        name="Test Sender",
        domain="example.com",
        type=SenderType.SERVICE,
        frequency_count=50,
        sample_subjects=["Subject 1", "Subject 2", "Subject 3"],
        email_ids=[f"email_{i}" for i in range(50)],
    )


@pytest.fixture
def sample_senders():
    """Create a list of sample senders for testing."""
    return [
        Sender(
            email=f"sender{i}@domain{i % 3}.com",
            name=f"Sender {i}",
            domain=f"domain{i % 3}.com",
            type=SenderType.SERVICE if i % 2 == 0 else SenderType.PERSONAL,
            frequency_count=30 + (i * 5),
            sample_subjects=[f"Subject {i}_{j}" for j in range(3)],
            email_ids=[f"email_{i}_{j}" for j in range(30 + i * 5)],
        )
        for i in range(5)
    ]


@pytest.fixture
def sample_content_cluster():
    """Create a sample ContentCluster for testing."""
    return ContentCluster(
        cluster_id=0,
        size=100,
        percentage=10.0,
        representative_samples=[
            RepresentativeSample(
                subject="Sample Subject 1",
                sender="sender1@example.com",
                body_preview="Preview of email body 1",
            ),
            RepresentativeSample(
                subject="Sample Subject 2",
                sender="sender2@example.com",
                body_preview="Preview of email body 2",
            ),
        ],
        common_domains=[("example.com", 60), ("test.com", 40)],
        email_ids=[f"email_{i}" for i in range(100)],
    )


@pytest.fixture
def sample_content_clusters():
    """Create a list of sample content clusters for testing."""
    return [
        ContentCluster(
            cluster_id=i,
            size=50 + (i * 20),
            percentage=5.0 + (i * 2.0),
            representative_samples=[
                RepresentativeSample(
                    subject=f"Cluster {i} Subject",
                    sender=f"sender{i}@example.com",
                    body_preview=f"Body preview for cluster {i}",
                )
            ],
            common_domains=[(f"domain{i}.com", 50)],
            email_ids=[f"cluster_{i}_email_{j}" for j in range(50 + i * 20)],
        )
        for i in range(3)
    ]


@pytest.fixture
def sample_analysis_results(sample_senders, sample_content_clusters):
    """Create sample AnalysisResults for testing."""
    return AnalysisResults(
        sender_analysis=SenderAnalysis(
            top_senders=sample_senders,
            top_domains=[
                DomainCount(domain="domain0.com", count=100),
                DomainCount(domain="domain1.com", count=80),
                DomainCount(domain="domain2.com", count=60),
            ],
            unique_senders=len(sample_senders),
            unique_domains=3,
        ),
        subject_patterns=SubjectPatterns(
            common_prefixes={"RE:": 50, "FWD:": 20, "[URGENT]": 10},
            numbered_patterns={"Invoice": 15, "Order": 25},
            top_keywords=[("meeting", 45), ("update", 38), ("report", 30)],
            bracket_tags=[("URGENT", 12), ("Team", 8)],
            total_subjects_analyzed=500,
        ),
        content_clusters=sample_content_clusters,
        temporal_patterns=TemporalPatterns(
            frequency_distribution={"daily": 50, "weekly": 30, "monthly": 20},
            sender_frequencies={
                "sender0@domain0.com": {"type": "daily", "count": 50},
                "sender1@domain1.com": {"type": "weekly", "count": 30},
            },
        ),
        volume_stats=VolumeStats(
            total_emails=1000,
            unique_senders=len(sample_senders),
            date_range={"oldest": "2024-01-01", "newest": "2024-01-31", "span_days": "30"},
            with_attachments=150,
            attachment_percentage=15.0,
            avg_body_length_chars=500,
            emails_per_day=33.3,
        ),
    )


# =============================================================================
# Temporary Directory Fixtures
# =============================================================================


@pytest.fixture
def temp_output_dir():
    """Create a temporary output directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def temp_config_dir():
    """Create a temporary config directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def temp_data_dir():
    """Create a temporary data directory with sample files for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir)

        # Create sample corpus file
        corpus_file = data_dir / "email_corpus.json"
        corpus_file.write_text('{"extraction_metadata": {}, "emails": []}')

        # Create sample analysis file
        analysis_file = data_dir / "corpus_analysis_results.json"
        analysis_file.write_text("{}")

        # Create sample suggestions file
        suggestions_file = data_dir / "category_suggestions.json"
        suggestions_file.write_text("[]")

        yield data_dir
