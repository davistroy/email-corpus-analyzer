"""
Unit tests for IncrementalProcessor (Phase 6, Item 6.1).

Tests the incremental processing engine that handles:
- Extracting only new emails since last run
- Merging new emails into existing corpus without duplicates
- Reassigning new emails to existing clusters via nearest-centroid
- Categorizing new emails using existing rules
- IncrementalResult model with processing metrics
- Progress callbacks

TDD: These tests are written first, implementation follows.
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.models.analysis_results import (
    AnalysisResults,
    DomainCount,
    SenderAnalysis,
    SubjectPatterns,
    TemporalPatterns,
    VolumeStats,
)
from src.models.categorization import CategoryAssignment, EmailCategorization
from src.models.content_cluster import ContentCluster, RepresentativeSample
from src.models.corpus import Corpus, CorpusMetadata
from src.models.email import Email
from src.models.rule import (
    CategoryRule,
    ConditionField,
    ConditionOperator,
    RuleAction,
    RuleActionType,
    RuleCondition,
    RuleSet,
)
from src.models.sender import Sender, SenderType

# =============================================================================
# Helpers
# =============================================================================


def _make_email(
    email_id: str = "email_001",
    sender_email: str = "sender@example.com",
    sender_domain: str = "example.com",
    subject: str = "Test Subject",
    body_text: str = "Test body content.",
    received_date: datetime | None = None,
) -> Email:
    """Create a test email with sensible defaults."""
    return Email(
        id=email_id,
        sender_email=sender_email,
        sender_name="Test Sender",
        sender_domain=sender_domain,
        recipient_email="recipient@example.com",
        recipient_name="Recipient",
        subject=subject,
        body_text=body_text,
        received_date=received_date or datetime(2024, 6, 15, 9, 0, 0),
        has_attachments=False,
    )


def _make_corpus(emails: list[Email] | None = None, user_email: str = "user@example.com") -> Corpus:
    """Create a test corpus with given emails."""
    emails = emails or []
    return Corpus(
        extraction_metadata=CorpusMetadata(
            extraction_date=datetime(2024, 6, 1, 0, 0, 0),
            total_emails=len(emails),
            source="hotmail",
            user_email=user_email,
            last_extraction_date=datetime(2024, 6, 15, 0, 0, 0),
        ),
        emails=emails,
    )


def _make_analysis_results(
    clusters: list[ContentCluster] | None = None,
) -> AnalysisResults:
    """Create minimal AnalysisResults with given clusters."""
    if clusters is None:
        clusters = [
            ContentCluster(
                cluster_id=0,
                size=5,
                percentage=50.0,
                representative_samples=[
                    RepresentativeSample(
                        subject="Cluster 0 Subject",
                        sender="sender@example.com",
                        body_preview="Cluster 0 body preview",
                    )
                ],
                common_domains=[("example.com", 5)],
                email_ids=["email_001", "email_002", "email_003", "email_004", "email_005"],
            ),
            ContentCluster(
                cluster_id=1,
                size=5,
                percentage=50.0,
                representative_samples=[
                    RepresentativeSample(
                        subject="Cluster 1 Subject",
                        sender="other@test.com",
                        body_preview="Cluster 1 body preview",
                    )
                ],
                common_domains=[("test.com", 5)],
                email_ids=["email_006", "email_007", "email_008", "email_009", "email_010"],
            ),
        ]
    return AnalysisResults(
        sender_analysis=SenderAnalysis(
            top_senders=[
                Sender(
                    email="sender@example.com",
                    name="Sender",
                    domain="example.com",
                    type=SenderType.SERVICE,
                    frequency_count=5,
                    sample_subjects=["Sub"],
                    email_ids=["email_001"],
                )
            ],
            top_domains=[DomainCount(domain="example.com", count=10)],
            unique_senders=2,
            unique_domains=2,
        ),
        subject_patterns=SubjectPatterns(
            common_prefixes={},
            numbered_patterns={},
            top_keywords=[],
            bracket_tags=[],
            total_subjects_analyzed=10,
        ),
        content_clusters=clusters,
        temporal_patterns=TemporalPatterns(
            frequency_distribution={},
            sender_frequencies={},
        ),
        volume_stats=VolumeStats(
            total_emails=10,
            unique_senders=2,
            date_range={"oldest": "2024-06-01", "newest": "2024-06-15", "span_days": "14"},
            with_attachments=0,
            attachment_percentage=0.0,
            avg_body_length_chars=100,
            emails_per_day=0.7,
        ),
    )


def _make_rule_set() -> RuleSet:
    """Create a test rule set with two rules."""
    return RuleSet(
        rules=[
            CategoryRule(
                rule_id="rule_001",
                name="Example Domain Rule",
                conditions=[
                    RuleCondition(
                        field=ConditionField.SENDER_DOMAIN,
                        operator=ConditionOperator.EQUALS,
                        value="example.com",
                    )
                ],
                action=RuleAction(
                    action_type=RuleActionType.CATEGORIZE,
                    target="Example Emails",
                ),
                priority=10,
            ),
            CategoryRule(
                rule_id="rule_002",
                name="Test Domain Rule",
                conditions=[
                    RuleCondition(
                        field=ConditionField.SENDER_DOMAIN,
                        operator=ConditionOperator.EQUALS,
                        value="test.com",
                    )
                ],
                action=RuleAction(
                    action_type=RuleActionType.CATEGORIZE,
                    target="Test Emails",
                ),
                priority=5,
            ),
        ],
        version="1.0",
    )


# =============================================================================
# IncrementalResult Model Tests
# =============================================================================


class TestIncrementalResult:
    """Tests for the IncrementalResult data model."""

    def test_create_with_all_fields(self):
        from src.automation.incremental import IncrementalResult

        result = IncrementalResult(
            new_email_count=15,
            merged_corpus_size=115,
            new_categorizations=[
                EmailCategorization(
                    email_id="email_new_001",
                    primary_category=CategoryAssignment(
                        category_name="Test",
                        confidence=0.9,
                        source="rule_001",
                    ),
                )
            ],
            processing_time=2.5,
        )
        assert result.new_email_count == 15
        assert result.merged_corpus_size == 115
        assert len(result.new_categorizations) == 1
        assert result.processing_time == 2.5

    def test_create_with_zero_new_emails(self):
        from src.automation.incremental import IncrementalResult

        result = IncrementalResult(
            new_email_count=0,
            merged_corpus_size=100,
            new_categorizations=[],
            processing_time=0.1,
        )
        assert result.new_email_count == 0
        assert result.merged_corpus_size == 100
        assert len(result.new_categorizations) == 0

    def test_negative_new_email_count_rejected(self):
        from src.automation.incremental import IncrementalResult

        with pytest.raises(ValueError):
            IncrementalResult(
                new_email_count=-1,
                merged_corpus_size=100,
                new_categorizations=[],
                processing_time=0.1,
            )

    def test_negative_processing_time_rejected(self):
        from src.automation.incremental import IncrementalResult

        with pytest.raises(ValueError):
            IncrementalResult(
                new_email_count=0,
                merged_corpus_size=100,
                new_categorizations=[],
                processing_time=-1.0,
            )

    def test_serialization_roundtrip(self):
        from src.automation.incremental import IncrementalResult

        result = IncrementalResult(
            new_email_count=5,
            merged_corpus_size=105,
            new_categorizations=[],
            processing_time=1.23,
        )
        json_str = result.model_dump_json()
        restored = IncrementalResult.model_validate_json(json_str)
        assert restored.new_email_count == result.new_email_count
        assert restored.merged_corpus_size == result.merged_corpus_size
        assert restored.processing_time == result.processing_time


# =============================================================================
# IncrementalProcessor — extract_new Tests
# =============================================================================


class TestExtractNew:
    """Tests for IncrementalProcessor.extract_new()."""

    def test_extract_new_returns_only_new_emails(self):
        from src.automation.incremental import IncrementalProcessor

        existing_emails = [
            _make_email(email_id=f"email_{i:03d}", received_date=datetime(2024, 6, i + 1, 10, 0, 0))
            for i in range(5)
        ]
        existing_corpus = _make_corpus(existing_emails)

        new_emails = [
            _make_email(
                email_id=f"email_new_{i:03d}", received_date=datetime(2024, 6, 20 + i, 10, 0, 0)
            )
            for i in range(3)
        ]

        mock_service = MagicMock()
        mock_corpus_result = _make_corpus(new_emails)
        mock_service.run.return_value = mock_corpus_result

        processor = IncrementalProcessor(extraction_service=mock_service)
        result = processor.extract_new(existing_corpus=existing_corpus)

        assert len(result) == 3
        mock_service.run.assert_called_once()
        # Verify since_last=True was passed
        call_kwargs = mock_service.run.call_args
        assert call_kwargs.kwargs.get("since_last") is True

    def test_extract_new_with_empty_existing_corpus(self):
        from src.automation.incremental import IncrementalProcessor

        existing_corpus = _make_corpus([])

        new_emails = [
            _make_email(
                email_id=f"email_new_{i:03d}", received_date=datetime(2024, 6, 20 + i, 10, 0, 0)
            )
            for i in range(3)
        ]

        mock_service = MagicMock()
        mock_service.run.return_value = _make_corpus(new_emails)

        processor = IncrementalProcessor(extraction_service=mock_service)
        result = processor.extract_new(existing_corpus=existing_corpus)

        assert len(result) == 3

    def test_extract_new_returns_empty_when_no_new_emails(self):
        from src.automation.incremental import IncrementalProcessor

        existing_corpus = _make_corpus(
            [_make_email(email_id="email_001", received_date=datetime(2024, 6, 15, 10, 0, 0))]
        )

        mock_service = MagicMock()
        mock_service.run.return_value = _make_corpus([])

        processor = IncrementalProcessor(extraction_service=mock_service)
        result = processor.extract_new(existing_corpus=existing_corpus)

        assert len(result) == 0

    def test_extract_new_with_progress_callback(self):
        from src.automation.incremental import IncrementalProcessor

        existing_corpus = _make_corpus([_make_email(email_id="email_001")])
        new_emails = [_make_email(email_id="email_new_001")]

        mock_service = MagicMock()
        mock_service.run.return_value = _make_corpus(new_emails)

        progress_messages: list[str] = []

        def callback(msg: str) -> None:
            progress_messages.append(msg)

        processor = IncrementalProcessor(extraction_service=mock_service)
        processor.extract_new(existing_corpus=existing_corpus, progress_callback=callback)

        assert len(progress_messages) > 0
        assert any("extract" in msg.lower() for msg in progress_messages)

    def test_extract_new_propagates_extraction_errors(self):
        from src.automation.incremental import IncrementalProcessor

        existing_corpus = _make_corpus([_make_email(email_id="email_001")])

        mock_service = MagicMock()
        mock_service.run.side_effect = ConnectionError("Network failure")

        processor = IncrementalProcessor(extraction_service=mock_service)
        with pytest.raises(ConnectionError, match="Network failure"):
            processor.extract_new(existing_corpus=existing_corpus)


# =============================================================================
# IncrementalProcessor — merge_into_corpus Tests
# =============================================================================


class TestMergeIntoCorpus:
    """Tests for IncrementalProcessor.merge_into_corpus()."""

    def test_merge_appends_new_emails(self):
        from src.automation.incremental import IncrementalProcessor

        existing_emails = [_make_email(email_id=f"email_{i:03d}") for i in range(3)]
        existing_corpus = _make_corpus(existing_emails)
        new_emails = [_make_email(email_id=f"email_new_{i:03d}") for i in range(2)]

        processor = IncrementalProcessor(extraction_service=MagicMock())
        merged = processor.merge_into_corpus(new_emails, existing_corpus)

        assert len(merged.emails) == 5
        assert merged.extraction_metadata.total_emails == 5

    def test_merge_deduplicates_by_email_id(self):
        from src.automation.incremental import IncrementalProcessor

        existing_emails = [_make_email(email_id="email_001"), _make_email(email_id="email_002")]
        existing_corpus = _make_corpus(existing_emails)
        # One duplicate, one new
        new_emails = [_make_email(email_id="email_002"), _make_email(email_id="email_003")]

        processor = IncrementalProcessor(extraction_service=MagicMock())
        merged = processor.merge_into_corpus(new_emails, existing_corpus)

        assert len(merged.emails) == 3
        ids = {e.id for e in merged.emails}
        assert ids == {"email_001", "email_002", "email_003"}

    def test_merge_preserves_existing_emails(self):
        from src.automation.incremental import IncrementalProcessor

        existing_emails = [
            _make_email(email_id="email_001", subject="Original Subject"),
        ]
        existing_corpus = _make_corpus(existing_emails)
        new_emails = [_make_email(email_id="email_002", subject="New Subject")]

        processor = IncrementalProcessor(extraction_service=MagicMock())
        merged = processor.merge_into_corpus(new_emails, existing_corpus)

        original = next(e for e in merged.emails if e.id == "email_001")
        assert original.subject == "Original Subject"

    def test_merge_updates_metadata(self):
        from src.automation.incremental import IncrementalProcessor

        existing_corpus = _make_corpus([_make_email(email_id="email_001")])
        new_emails = [_make_email(email_id="email_002")]

        processor = IncrementalProcessor(extraction_service=MagicMock())
        merged = processor.merge_into_corpus(new_emails, existing_corpus)

        assert merged.extraction_metadata.total_emails == 2
        # last_extraction_date should be updated
        assert merged.extraction_metadata.last_extraction_date is not None
        # Source should be preserved
        assert merged.extraction_metadata.source == "hotmail"

    def test_merge_with_empty_new_emails(self):
        from src.automation.incremental import IncrementalProcessor

        existing_emails = [_make_email(email_id="email_001")]
        existing_corpus = _make_corpus(existing_emails)

        processor = IncrementalProcessor(extraction_service=MagicMock())
        merged = processor.merge_into_corpus([], existing_corpus)

        assert len(merged.emails) == 1
        assert merged.extraction_metadata.total_emails == 1

    def test_merge_with_empty_existing_corpus(self):
        from src.automation.incremental import IncrementalProcessor

        existing_corpus = _make_corpus([])
        new_emails = [_make_email(email_id="email_001")]

        processor = IncrementalProcessor(extraction_service=MagicMock())
        merged = processor.merge_into_corpus(new_emails, existing_corpus)

        assert len(merged.emails) == 1

    def test_merge_computes_email_ids_hash(self):
        from src.automation.incremental import IncrementalProcessor

        existing_corpus = _make_corpus([_make_email(email_id="email_001")])
        new_emails = [_make_email(email_id="email_002")]

        processor = IncrementalProcessor(extraction_service=MagicMock())
        merged = processor.merge_into_corpus(new_emails, existing_corpus)

        assert merged.extraction_metadata.email_ids_hash is not None
        assert len(merged.extraction_metadata.email_ids_hash) > 0

    def test_merge_with_all_duplicates(self):
        from src.automation.incremental import IncrementalProcessor

        existing_emails = [_make_email(email_id="email_001"), _make_email(email_id="email_002")]
        existing_corpus = _make_corpus(existing_emails)
        # All duplicates
        new_emails = [_make_email(email_id="email_001"), _make_email(email_id="email_002")]

        processor = IncrementalProcessor(extraction_service=MagicMock())
        merged = processor.merge_into_corpus(new_emails, existing_corpus)

        assert len(merged.emails) == 2


# =============================================================================
# IncrementalProcessor — reassign_to_clusters Tests
# =============================================================================


class TestReassignToClusters:
    """Tests for IncrementalProcessor.reassign_to_clusters()."""

    def test_reassign_assigns_to_nearest_centroid(self):
        """New emails should be assigned to the cluster whose centroid is nearest."""
        from src.automation.incremental import IncrementalProcessor

        new_emails = [_make_email(email_id="email_new_001", sender_domain="example.com")]
        existing_analysis = _make_analysis_results()

        # Mock the embedding model to return deterministic vectors
        mock_service = MagicMock()
        processor = IncrementalProcessor(extraction_service=mock_service)

        # We'll need to mock the embedding generation
        # Centroid 0 at [1, 0], Centroid 1 at [0, 1], new email embedding at [0.9, 0.1]
        # -> should assign to cluster 0
        with (
            patch.object(processor, "_compute_embeddings") as mock_embed,
            patch.object(processor, "_compute_centroids") as mock_centroids,
        ):
            mock_embed.return_value = np.array([[0.9, 0.1]])
            mock_centroids.return_value = np.array([[1.0, 0.0], [0.0, 1.0]])

            updated = processor.reassign_to_clusters(new_emails, existing_analysis)

        # email_new_001 should be added to cluster 0
        cluster_0 = next(c for c in updated.content_clusters if c.cluster_id == 0)
        assert "email_new_001" in cluster_0.email_ids

    def test_reassign_updates_cluster_sizes(self):
        from src.automation.incremental import IncrementalProcessor

        new_emails = [_make_email(email_id="email_new_001")]
        existing_analysis = _make_analysis_results()
        original_cluster_0_size = existing_analysis.content_clusters[0].size

        mock_service = MagicMock()
        processor = IncrementalProcessor(extraction_service=mock_service)

        with (
            patch.object(processor, "_compute_embeddings") as mock_embed,
            patch.object(processor, "_compute_centroids") as mock_centroids,
        ):
            mock_embed.return_value = np.array([[0.9, 0.1]])
            mock_centroids.return_value = np.array([[1.0, 0.0], [0.0, 1.0]])

            updated = processor.reassign_to_clusters(new_emails, existing_analysis)

        cluster_0 = next(c for c in updated.content_clusters if c.cluster_id == 0)
        assert cluster_0.size == original_cluster_0_size + 1

    def test_reassign_updates_percentages(self):
        from src.automation.incremental import IncrementalProcessor

        new_emails = [_make_email(email_id="email_new_001")]
        existing_analysis = _make_analysis_results()

        mock_service = MagicMock()
        processor = IncrementalProcessor(extraction_service=mock_service)

        with (
            patch.object(processor, "_compute_embeddings") as mock_embed,
            patch.object(processor, "_compute_centroids") as mock_centroids,
        ):
            mock_embed.return_value = np.array([[0.9, 0.1]])
            mock_centroids.return_value = np.array([[1.0, 0.0], [0.0, 1.0]])

            updated = processor.reassign_to_clusters(new_emails, existing_analysis)

        # Total is now 11 (10 original + 1 new)
        total = sum(c.size for c in updated.content_clusters)
        assert total == 11
        # Percentages should be recalculated and sum to ~100
        pct_sum = sum(c.percentage for c in updated.content_clusters)
        assert abs(pct_sum - 100.0) < 0.1

    def test_reassign_with_empty_new_emails(self):
        from src.automation.incremental import IncrementalProcessor

        existing_analysis = _make_analysis_results()

        processor = IncrementalProcessor(extraction_service=MagicMock())
        updated = processor.reassign_to_clusters([], existing_analysis)

        # Should return unchanged analysis
        assert updated.content_clusters == existing_analysis.content_clusters

    def test_reassign_multiple_emails_to_different_clusters(self):
        from src.automation.incremental import IncrementalProcessor

        new_emails = [
            _make_email(email_id="email_new_001"),
            _make_email(email_id="email_new_002"),
        ]
        existing_analysis = _make_analysis_results()

        processor = IncrementalProcessor(extraction_service=MagicMock())

        with (
            patch.object(processor, "_compute_embeddings") as mock_embed,
            patch.object(processor, "_compute_centroids") as mock_centroids,
        ):
            # First email close to cluster 0, second close to cluster 1
            mock_embed.return_value = np.array([[0.9, 0.1], [0.1, 0.9]])
            mock_centroids.return_value = np.array([[1.0, 0.0], [0.0, 1.0]])

            updated = processor.reassign_to_clusters(new_emails, existing_analysis)

        cluster_0 = next(c for c in updated.content_clusters if c.cluster_id == 0)
        cluster_1 = next(c for c in updated.content_clusters if c.cluster_id == 1)
        assert "email_new_001" in cluster_0.email_ids
        assert "email_new_002" in cluster_1.email_ids

    def test_reassign_preserves_existing_email_ids(self):
        from src.automation.incremental import IncrementalProcessor

        new_emails = [_make_email(email_id="email_new_001")]
        existing_analysis = _make_analysis_results()
        original_ids_0 = list(existing_analysis.content_clusters[0].email_ids)
        original_ids_1 = list(existing_analysis.content_clusters[1].email_ids)

        processor = IncrementalProcessor(extraction_service=MagicMock())

        with (
            patch.object(processor, "_compute_embeddings") as mock_embed,
            patch.object(processor, "_compute_centroids") as mock_centroids,
        ):
            mock_embed.return_value = np.array([[0.9, 0.1]])
            mock_centroids.return_value = np.array([[1.0, 0.0], [0.0, 1.0]])

            updated = processor.reassign_to_clusters(new_emails, existing_analysis)

        cluster_0 = next(c for c in updated.content_clusters if c.cluster_id == 0)
        cluster_1 = next(c for c in updated.content_clusters if c.cluster_id == 1)
        # Original IDs should be preserved
        for eid in original_ids_0:
            assert eid in cluster_0.email_ids
        for eid in original_ids_1:
            assert eid in cluster_1.email_ids

    def test_reassign_with_progress_callback(self):
        from src.automation.incremental import IncrementalProcessor

        new_emails = [_make_email(email_id="email_new_001")]
        existing_analysis = _make_analysis_results()

        progress_messages: list[str] = []

        def callback(msg: str) -> None:
            progress_messages.append(msg)

        processor = IncrementalProcessor(extraction_service=MagicMock())

        with (
            patch.object(processor, "_compute_embeddings") as mock_embed,
            patch.object(processor, "_compute_centroids") as mock_centroids,
        ):
            mock_embed.return_value = np.array([[0.9, 0.1]])
            mock_centroids.return_value = np.array([[1.0, 0.0], [0.0, 1.0]])

            processor.reassign_to_clusters(
                new_emails, existing_analysis, progress_callback=callback
            )

        assert len(progress_messages) > 0


# =============================================================================
# IncrementalProcessor — categorize_new Tests
# =============================================================================


class TestCategorizeNew:
    """Tests for IncrementalProcessor.categorize_new()."""

    def test_categorize_matches_rule(self):
        from src.automation.incremental import IncrementalProcessor

        new_emails = [_make_email(email_id="email_new_001", sender_domain="example.com")]
        rule_set = _make_rule_set()

        processor = IncrementalProcessor(extraction_service=MagicMock())
        categorizations = processor.categorize_new(new_emails, rule_set)

        assert len(categorizations) == 1
        assert categorizations[0].email_id == "email_new_001"
        assert categorizations[0].primary_category.category_name == "Example Emails"

    def test_categorize_multiple_emails_different_rules(self):
        from src.automation.incremental import IncrementalProcessor

        new_emails = [
            _make_email(email_id="email_new_001", sender_domain="example.com"),
            _make_email(email_id="email_new_002", sender_domain="test.com"),
        ]
        rule_set = _make_rule_set()

        processor = IncrementalProcessor(extraction_service=MagicMock())
        categorizations = processor.categorize_new(new_emails, rule_set)

        assert len(categorizations) == 2
        cats_by_id = {c.email_id: c for c in categorizations}
        assert cats_by_id["email_new_001"].primary_category.category_name == "Example Emails"
        assert cats_by_id["email_new_002"].primary_category.category_name == "Test Emails"

    def test_categorize_uncategorized_email(self):
        from src.automation.incremental import IncrementalProcessor

        new_emails = [_make_email(email_id="email_new_001", sender_domain="unknown.org")]
        rule_set = _make_rule_set()

        processor = IncrementalProcessor(extraction_service=MagicMock())
        categorizations = processor.categorize_new(new_emails, rule_set)

        assert len(categorizations) == 1
        assert categorizations[0].is_uncategorized

    def test_categorize_empty_list(self):
        from src.automation.incremental import IncrementalProcessor

        rule_set = _make_rule_set()
        processor = IncrementalProcessor(extraction_service=MagicMock())
        categorizations = processor.categorize_new([], rule_set)
        assert categorizations == []

    def test_categorize_with_progress_callback(self):
        from src.automation.incremental import IncrementalProcessor

        new_emails = [
            _make_email(email_id=f"email_new_{i:03d}", sender_domain="example.com")
            for i in range(5)
        ]
        rule_set = _make_rule_set()

        progress_calls: list[str] = []

        def callback(msg: str) -> None:
            progress_calls.append(msg)

        processor = IncrementalProcessor(extraction_service=MagicMock())
        processor.categorize_new(new_emails, rule_set, progress_callback=callback)

        assert len(progress_calls) > 0

    def test_categorize_with_empty_rule_set(self):
        from src.automation.incremental import IncrementalProcessor

        new_emails = [_make_email(email_id="email_new_001")]
        empty_rules = RuleSet(rules=[])

        processor = IncrementalProcessor(extraction_service=MagicMock())
        categorizations = processor.categorize_new(new_emails, empty_rules)

        assert len(categorizations) == 1
        assert categorizations[0].is_uncategorized


# =============================================================================
# IncrementalProcessor — run (full pipeline) Tests
# =============================================================================


class TestIncrementalProcessorRun:
    """Tests for the full incremental processing pipeline."""

    def test_run_returns_incremental_result(self):
        from src.automation.incremental import IncrementalProcessor, IncrementalResult

        existing_emails = [_make_email(email_id="email_001")]
        existing_corpus = _make_corpus(existing_emails)
        existing_analysis = _make_analysis_results()
        rule_set = _make_rule_set()

        new_emails = [
            _make_email(email_id="email_new_001", sender_domain="example.com"),
        ]

        mock_service = MagicMock()
        mock_service.run.return_value = _make_corpus(new_emails)

        processor = IncrementalProcessor(extraction_service=mock_service)

        with (
            patch.object(processor, "_compute_embeddings") as mock_embed,
            patch.object(processor, "_compute_centroids") as mock_centroids,
        ):
            mock_embed.return_value = np.array([[0.9, 0.1]])
            mock_centroids.return_value = np.array([[1.0, 0.0], [0.0, 1.0]])

            result = processor.run(
                existing_corpus=existing_corpus,
                existing_analysis=existing_analysis,
                rule_set=rule_set,
            )

        assert isinstance(result, IncrementalResult)
        assert result.new_email_count == 1
        assert result.merged_corpus_size == 2
        assert len(result.new_categorizations) == 1
        assert result.processing_time >= 0

    def test_run_with_no_new_emails(self):
        from src.automation.incremental import IncrementalProcessor

        existing_corpus = _make_corpus([_make_email(email_id="email_001")])
        existing_analysis = _make_analysis_results()
        rule_set = _make_rule_set()

        mock_service = MagicMock()
        mock_service.run.return_value = _make_corpus([])

        processor = IncrementalProcessor(extraction_service=mock_service)
        result = processor.run(
            existing_corpus=existing_corpus,
            existing_analysis=existing_analysis,
            rule_set=rule_set,
        )

        assert result.new_email_count == 0
        assert result.merged_corpus_size == 1
        assert len(result.new_categorizations) == 0

    def test_run_with_progress_callback(self):
        from src.automation.incremental import IncrementalProcessor

        existing_corpus = _make_corpus([_make_email(email_id="email_001")])
        existing_analysis = _make_analysis_results()
        rule_set = _make_rule_set()

        new_emails = [_make_email(email_id="email_new_001", sender_domain="example.com")]

        mock_service = MagicMock()
        mock_service.run.return_value = _make_corpus(new_emails)

        progress_messages: list[str] = []

        def callback(msg: str) -> None:
            progress_messages.append(msg)

        processor = IncrementalProcessor(extraction_service=mock_service)

        with (
            patch.object(processor, "_compute_embeddings") as mock_embed,
            patch.object(processor, "_compute_centroids") as mock_centroids,
        ):
            mock_embed.return_value = np.array([[0.9, 0.1]])
            mock_centroids.return_value = np.array([[1.0, 0.0], [0.0, 1.0]])

            processor.run(
                existing_corpus=existing_corpus,
                existing_analysis=existing_analysis,
                rule_set=rule_set,
                progress_callback=callback,
            )

        assert len(progress_messages) > 0

    def test_run_measures_processing_time(self):
        from src.automation.incremental import IncrementalProcessor

        existing_corpus = _make_corpus([_make_email(email_id="email_001")])
        existing_analysis = _make_analysis_results()
        rule_set = _make_rule_set()

        mock_service = MagicMock()
        mock_service.run.return_value = _make_corpus([])

        processor = IncrementalProcessor(extraction_service=mock_service)
        result = processor.run(
            existing_corpus=existing_corpus,
            existing_analysis=existing_analysis,
            rule_set=rule_set,
        )

        assert result.processing_time >= 0

    def test_run_without_rule_set_skips_categorization(self):
        from src.automation.incremental import IncrementalProcessor

        existing_corpus = _make_corpus([_make_email(email_id="email_001")])
        existing_analysis = _make_analysis_results()

        new_emails = [_make_email(email_id="email_new_001")]

        mock_service = MagicMock()
        mock_service.run.return_value = _make_corpus(new_emails)

        processor = IncrementalProcessor(extraction_service=mock_service)

        with (
            patch.object(processor, "_compute_embeddings") as mock_embed,
            patch.object(processor, "_compute_centroids") as mock_centroids,
        ):
            mock_embed.return_value = np.array([[0.9, 0.1]])
            mock_centroids.return_value = np.array([[1.0, 0.0], [0.0, 1.0]])

            result = processor.run(
                existing_corpus=existing_corpus,
                existing_analysis=existing_analysis,
                rule_set=None,
            )

        assert result.new_email_count == 1
        assert len(result.new_categorizations) == 0

    def test_run_without_existing_analysis_skips_reassignment(self):
        from src.automation.incremental import IncrementalProcessor

        existing_corpus = _make_corpus([_make_email(email_id="email_001")])
        rule_set = _make_rule_set()

        new_emails = [_make_email(email_id="email_new_001", sender_domain="example.com")]

        mock_service = MagicMock()
        mock_service.run.return_value = _make_corpus(new_emails)

        processor = IncrementalProcessor(extraction_service=mock_service)
        result = processor.run(
            existing_corpus=existing_corpus,
            existing_analysis=None,
            rule_set=rule_set,
        )

        assert result.new_email_count == 1
        assert result.merged_corpus_size == 2
        assert len(result.new_categorizations) == 1


# =============================================================================
# IncrementalProcessor — merged_corpus property Tests
# =============================================================================


class TestMergedCorpusProperty:
    """Tests for accessing the merged corpus after a run."""

    def test_merged_corpus_available_after_run(self):
        from src.automation.incremental import IncrementalProcessor

        existing_corpus = _make_corpus([_make_email(email_id="email_001")])
        existing_analysis = _make_analysis_results()
        rule_set = _make_rule_set()

        new_emails = [_make_email(email_id="email_new_001", sender_domain="example.com")]

        mock_service = MagicMock()
        mock_service.run.return_value = _make_corpus(new_emails)

        processor = IncrementalProcessor(extraction_service=mock_service)

        with (
            patch.object(processor, "_compute_embeddings") as mock_embed,
            patch.object(processor, "_compute_centroids") as mock_centroids,
        ):
            mock_embed.return_value = np.array([[0.9, 0.1]])
            mock_centroids.return_value = np.array([[1.0, 0.0], [0.0, 1.0]])

            processor.run(
                existing_corpus=existing_corpus,
                existing_analysis=existing_analysis,
                rule_set=rule_set,
            )

        assert processor.merged_corpus is not None
        assert len(processor.merged_corpus.emails) == 2

    def test_merged_corpus_none_before_run(self):
        from src.automation.incremental import IncrementalProcessor

        processor = IncrementalProcessor(extraction_service=MagicMock())
        assert processor.merged_corpus is None

    def test_updated_analysis_available_after_run(self):
        from src.automation.incremental import IncrementalProcessor

        existing_corpus = _make_corpus([_make_email(email_id="email_001")])
        existing_analysis = _make_analysis_results()

        new_emails = [_make_email(email_id="email_new_001")]

        mock_service = MagicMock()
        mock_service.run.return_value = _make_corpus(new_emails)

        processor = IncrementalProcessor(extraction_service=mock_service)

        with (
            patch.object(processor, "_compute_embeddings") as mock_embed,
            patch.object(processor, "_compute_centroids") as mock_centroids,
        ):
            mock_embed.return_value = np.array([[0.9, 0.1]])
            mock_centroids.return_value = np.array([[1.0, 0.0], [0.0, 1.0]])

            processor.run(
                existing_corpus=existing_corpus,
                existing_analysis=existing_analysis,
                rule_set=None,
            )

        assert processor.updated_analysis is not None
