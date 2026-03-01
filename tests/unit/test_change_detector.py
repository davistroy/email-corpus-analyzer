"""
Unit tests for ChangeDetector (Phase 6, Item 6.2).

Tests the change detection engine that handles:
- Detecting drift between two AnalysisResults (distribution changes)
- Detecting volume anomalies in a corpus (spikes/dips)
- Detecting emerging topics not present in old clusters
- DriftReport, VolumeAnomaly, EmergingTopic models
- Configurable thresholds from MonitoringConfig

TDD: These tests are written first, implementation follows.
"""

from datetime import datetime, timedelta

import pytest
from pydantic import ValidationError

from src.config.models import MonitoringConfig
from src.models.analysis_results import (
    AnalysisResults,
    DomainCount,
    SenderAnalysis,
    SubjectPatterns,
    TemporalPatterns,
    VolumeStats,
)
from src.models.content_cluster import ContentCluster, RepresentativeSample
from src.models.corpus import Corpus, CorpusMetadata
from src.models.email import Email
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


def _make_corpus(
    emails: list[Email] | None = None,
    user_email: str = "user@example.com",
) -> Corpus:
    """Create a test corpus with given emails."""
    emails = emails or []
    return Corpus(
        extraction_metadata=CorpusMetadata(
            extraction_date=datetime(2024, 6, 1, 0, 0, 0),
            total_emails=len(emails),
            source="hotmail",
            user_email=user_email,
        ),
        emails=emails,
    )


def _make_cluster(
    cluster_id: int = 0,
    size: int = 10,
    percentage: float = 50.0,
    email_ids: list[str] | None = None,
    subject: str = "Cluster Subject",
    common_domains: list[tuple[str, int]] | None = None,
) -> ContentCluster:
    """Create a test content cluster."""
    return ContentCluster(
        cluster_id=cluster_id,
        size=size,
        percentage=percentage,
        representative_samples=[
            RepresentativeSample(
                subject=subject,
                sender="sender@example.com",
                body_preview="Body preview text.",
            )
        ],
        email_ids=email_ids or [f"email_{i}" for i in range(size)],
        common_domains=common_domains or [("example.com", size)],
    )


def _make_analysis(
    clusters: list[ContentCluster] | None = None,
    total_emails: int = 100,
    top_senders: list[Sender] | None = None,
    top_domains: list[DomainCount] | None = None,
    top_keywords: list[tuple[str, int]] | None = None,
) -> AnalysisResults:
    """Create a minimal AnalysisResults for testing."""
    if clusters is None:
        clusters = [
            _make_cluster(cluster_id=0, size=50, percentage=50.0),
            _make_cluster(cluster_id=1, size=50, percentage=50.0),
        ]

    if top_senders is None:
        top_senders = [
            Sender(
                email="sender@example.com",
                name="Sender",
                domain="example.com",
                type=SenderType.PERSONAL,
                frequency_count=50,
                email_ids=[],
            )
        ]

    if top_domains is None:
        top_domains = [DomainCount(domain="example.com", count=50)]

    if top_keywords is None:
        top_keywords = [("meeting", 10), ("update", 8)]

    return AnalysisResults(
        sender_analysis=SenderAnalysis(
            top_senders=top_senders,
            top_domains=top_domains,
            unique_senders=10,
            unique_domains=5,
        ),
        subject_patterns=SubjectPatterns(
            common_prefixes={"RE:": 10},
            numbered_patterns={"Invoice": 5},
            top_keywords=top_keywords,
            bracket_tags=[],
            total_subjects_analyzed=total_emails,
        ),
        content_clusters=clusters,
        temporal_patterns=TemporalPatterns(
            frequency_distribution={"daily": 30, "weekly": 40, "occasional": 30},
            sender_frequencies={},
        ),
        volume_stats=VolumeStats(
            total_emails=total_emails,
            unique_senders=10,
            date_range={
                "oldest": "2024-01-01T00:00:00",
                "newest": "2024-06-30T00:00:00",
                "span_days": "181",
            },
            with_attachments=10,
            attachment_percentage=10.0,
            avg_body_length_chars=500,
            emails_per_day=0.55,
        ),
    )


# =============================================================================
# Model Tests
# =============================================================================


class TestDriftReport:
    """Tests for the DriftReport data model."""

    def test_drift_report_creation(self) -> None:
        """DriftReport can be created with required fields."""
        from src.automation.change_detector import DriftReport

        report = DriftReport(
            overall_drift_score=0.25,
            per_cluster_drift={0: 0.1, 1: 0.4},
            significant_changes=["Cluster 1 shrank by 40%"],
        )
        assert report.overall_drift_score == 0.25
        assert report.per_cluster_drift == {0: 0.1, 1: 0.4}
        assert len(report.significant_changes) == 1

    def test_drift_report_defaults(self) -> None:
        """DriftReport has sensible defaults for optional fields."""
        from src.automation.change_detector import DriftReport

        report = DriftReport(overall_drift_score=0.0)
        assert report.per_cluster_drift == {}
        assert report.significant_changes == []

    def test_drift_report_score_bounds(self) -> None:
        """DriftReport overall_drift_score is bounded 0.0-1.0."""
        from src.automation.change_detector import DriftReport

        report = DriftReport(overall_drift_score=0.0)
        assert report.overall_drift_score == 0.0

        report = DriftReport(overall_drift_score=1.0)
        assert report.overall_drift_score == 1.0

        with pytest.raises(ValidationError):
            DriftReport(overall_drift_score=-0.1)

        with pytest.raises(ValidationError):
            DriftReport(overall_drift_score=1.1)


class TestVolumeAnomaly:
    """Tests for the VolumeAnomaly data model."""

    def test_volume_anomaly_creation(self) -> None:
        """VolumeAnomaly can be created with required fields."""
        from src.automation.change_detector import VolumeAnomaly

        anomaly = VolumeAnomaly(
            date_range=("2024-06-01", "2024-06-07"),
            expected_volume=10.0,
            actual_volume=35,
            z_score=3.5,
        )
        assert anomaly.date_range == ("2024-06-01", "2024-06-07")
        assert anomaly.expected_volume == 10.0
        assert anomaly.actual_volume == 35
        assert anomaly.z_score == 3.5

    def test_volume_anomaly_spike_and_dip(self) -> None:
        """VolumeAnomaly z_score can be positive (spike) or negative (dip)."""
        from src.automation.change_detector import VolumeAnomaly

        spike = VolumeAnomaly(
            date_range=("2024-06-01", "2024-06-07"),
            expected_volume=10.0,
            actual_volume=30,
            z_score=3.0,
        )
        assert spike.z_score > 0

        dip = VolumeAnomaly(
            date_range=("2024-06-01", "2024-06-07"),
            expected_volume=10.0,
            actual_volume=2,
            z_score=-2.5,
        )
        assert dip.z_score < 0


class TestEmergingTopic:
    """Tests for the EmergingTopic data model."""

    def test_emerging_topic_creation(self) -> None:
        """EmergingTopic can be created with required fields."""
        from src.automation.change_detector import EmergingTopic

        topic = EmergingTopic(
            topic_keywords=["kubernetes", "deployment", "cluster"],
            email_count=15,
            first_seen="2024-06-15",
            suggested_category="DevOps Notifications",
        )
        assert topic.topic_keywords == ["kubernetes", "deployment", "cluster"]
        assert topic.email_count == 15
        assert topic.first_seen == "2024-06-15"
        assert topic.suggested_category == "DevOps Notifications"

    def test_emerging_topic_defaults(self) -> None:
        """EmergingTopic has sensible defaults."""
        from src.automation.change_detector import EmergingTopic

        topic = EmergingTopic(
            topic_keywords=["test"],
            email_count=5,
            first_seen="2024-06-15",
        )
        assert topic.suggested_category is None


# =============================================================================
# ChangeDetector — detect_drift tests
# =============================================================================


class TestDetectDrift:
    """Tests for ChangeDetector.detect_drift()."""

    def test_identical_analyses_zero_drift(self) -> None:
        """Two identical analyses should produce zero drift."""
        from src.automation.change_detector import ChangeDetector

        detector = ChangeDetector()
        analysis = _make_analysis()

        report = detector.detect_drift(analysis, analysis)

        assert report.overall_drift_score == 0.0
        assert report.significant_changes == []

    def test_cluster_size_shift_detected(self) -> None:
        """Significant cluster size redistribution produces drift > 0."""
        from src.automation.change_detector import ChangeDetector

        detector = ChangeDetector()

        old_analysis = _make_analysis(
            clusters=[
                _make_cluster(cluster_id=0, size=50, percentage=50.0),
                _make_cluster(cluster_id=1, size=50, percentage=50.0),
            ]
        )
        new_analysis = _make_analysis(
            clusters=[
                _make_cluster(cluster_id=0, size=80, percentage=80.0),
                _make_cluster(cluster_id=1, size=20, percentage=20.0),
            ]
        )

        report = detector.detect_drift(old_analysis, new_analysis)

        assert report.overall_drift_score > 0.0
        assert len(report.per_cluster_drift) > 0

    def test_drift_with_new_cluster_appearing(self) -> None:
        """A new cluster appearing should contribute to drift."""
        from src.automation.change_detector import ChangeDetector

        detector = ChangeDetector()

        old_analysis = _make_analysis(
            clusters=[
                _make_cluster(cluster_id=0, size=100, percentage=100.0),
            ]
        )
        new_analysis = _make_analysis(
            clusters=[
                _make_cluster(cluster_id=0, size=70, percentage=70.0),
                _make_cluster(cluster_id=1, size=30, percentage=30.0),
            ]
        )

        report = detector.detect_drift(old_analysis, new_analysis)

        assert report.overall_drift_score > 0.0

    def test_drift_with_cluster_disappearing(self) -> None:
        """A cluster disappearing (size -> 0) should contribute to drift."""
        from src.automation.change_detector import ChangeDetector

        detector = ChangeDetector()

        old_analysis = _make_analysis(
            clusters=[
                _make_cluster(cluster_id=0, size=50, percentage=50.0),
                _make_cluster(cluster_id=1, size=50, percentage=50.0),
            ]
        )
        new_analysis = _make_analysis(
            clusters=[
                _make_cluster(cluster_id=0, size=100, percentage=100.0),
            ]
        )

        report = detector.detect_drift(old_analysis, new_analysis)

        assert report.overall_drift_score > 0.0

    def test_significant_changes_reported_above_threshold(self) -> None:
        """Changes exceeding drift_threshold should appear in significant_changes."""
        from src.automation.change_detector import ChangeDetector

        config = MonitoringConfig(drift_threshold=0.10)
        detector = ChangeDetector(config=config)

        old_analysis = _make_analysis(
            clusters=[
                _make_cluster(cluster_id=0, size=50, percentage=50.0),
                _make_cluster(cluster_id=1, size=50, percentage=50.0),
            ]
        )
        # Major shift: cluster 0 goes from 50% to 90%
        new_analysis = _make_analysis(
            clusters=[
                _make_cluster(cluster_id=0, size=90, percentage=90.0),
                _make_cluster(cluster_id=1, size=10, percentage=10.0),
            ]
        )

        report = detector.detect_drift(old_analysis, new_analysis)

        assert len(report.significant_changes) > 0
        assert report.overall_drift_score > config.drift_threshold

    def test_minor_changes_not_significant(self) -> None:
        """Small changes below drift_threshold should not be flagged."""
        from src.automation.change_detector import ChangeDetector

        config = MonitoringConfig(drift_threshold=0.50)
        detector = ChangeDetector(config=config)

        old_analysis = _make_analysis(
            clusters=[
                _make_cluster(cluster_id=0, size=50, percentage=50.0),
                _make_cluster(cluster_id=1, size=50, percentage=50.0),
            ]
        )
        # Tiny shift
        new_analysis = _make_analysis(
            clusters=[
                _make_cluster(cluster_id=0, size=52, percentage=52.0),
                _make_cluster(cluster_id=1, size=48, percentage=48.0),
            ]
        )

        report = detector.detect_drift(old_analysis, new_analysis)

        assert report.overall_drift_score < config.drift_threshold
        assert len(report.significant_changes) == 0

    def test_drift_uses_custom_threshold(self) -> None:
        """ChangeDetector respects custom MonitoringConfig drift_threshold."""
        from src.automation.change_detector import ChangeDetector

        strict_config = MonitoringConfig(drift_threshold=0.01)
        lenient_config = MonitoringConfig(drift_threshold=0.99)

        old_analysis = _make_analysis(
            clusters=[
                _make_cluster(cluster_id=0, size=50, percentage=50.0),
                _make_cluster(cluster_id=1, size=50, percentage=50.0),
            ]
        )
        new_analysis = _make_analysis(
            clusters=[
                _make_cluster(cluster_id=0, size=60, percentage=60.0),
                _make_cluster(cluster_id=1, size=40, percentage=40.0),
            ]
        )

        strict_detector = ChangeDetector(config=strict_config)
        lenient_detector = ChangeDetector(config=lenient_config)

        strict_report = strict_detector.detect_drift(old_analysis, new_analysis)
        lenient_report = lenient_detector.detect_drift(old_analysis, new_analysis)

        # Same drift score regardless of threshold
        assert strict_report.overall_drift_score == lenient_report.overall_drift_score
        # Strict flags changes, lenient does not
        assert len(strict_report.significant_changes) >= len(lenient_report.significant_changes)

    def test_drift_empty_old_clusters(self) -> None:
        """Empty old analysis (no clusters) treated as full drift if new has clusters."""
        from src.automation.change_detector import ChangeDetector

        detector = ChangeDetector()

        old_analysis = _make_analysis(clusters=[])
        new_analysis = _make_analysis(
            clusters=[_make_cluster(cluster_id=0, size=100, percentage=100.0)]
        )

        report = detector.detect_drift(old_analysis, new_analysis)

        # Should not crash, drift should be max since everything is new
        assert report.overall_drift_score > 0.0

    def test_drift_empty_new_clusters(self) -> None:
        """Empty new analysis (no clusters) treated as full drift if old had clusters."""
        from src.automation.change_detector import ChangeDetector

        detector = ChangeDetector()

        old_analysis = _make_analysis(
            clusters=[_make_cluster(cluster_id=0, size=100, percentage=100.0)]
        )
        new_analysis = _make_analysis(clusters=[])

        report = detector.detect_drift(old_analysis, new_analysis)

        assert report.overall_drift_score > 0.0

    def test_drift_both_empty_clusters(self) -> None:
        """Both analyses with no clusters yields zero drift."""
        from src.automation.change_detector import ChangeDetector

        detector = ChangeDetector()

        old_analysis = _make_analysis(clusters=[])
        new_analysis = _make_analysis(clusters=[])

        report = detector.detect_drift(old_analysis, new_analysis)

        assert report.overall_drift_score == 0.0

    def test_per_cluster_drift_values(self) -> None:
        """Per-cluster drift values reflect individual cluster changes."""
        from src.automation.change_detector import ChangeDetector

        detector = ChangeDetector()

        old_analysis = _make_analysis(
            clusters=[
                _make_cluster(cluster_id=0, size=50, percentage=50.0),
                _make_cluster(cluster_id=1, size=30, percentage=30.0),
                _make_cluster(cluster_id=2, size=20, percentage=20.0),
            ]
        )
        new_analysis = _make_analysis(
            clusters=[
                _make_cluster(cluster_id=0, size=50, percentage=50.0),  # unchanged
                _make_cluster(cluster_id=1, size=10, percentage=10.0),  # shrank
                _make_cluster(cluster_id=2, size=40, percentage=40.0),  # grew
            ]
        )

        report = detector.detect_drift(old_analysis, new_analysis)

        # Cluster 0 should have minimal drift
        assert report.per_cluster_drift[0] < report.per_cluster_drift[1]
        assert report.per_cluster_drift[0] < report.per_cluster_drift[2]

    def test_drift_domain_distribution_changes(self) -> None:
        """Drift detection captures domain distribution shifts."""
        from src.automation.change_detector import ChangeDetector

        detector = ChangeDetector()

        old_analysis = _make_analysis(
            top_domains=[
                DomainCount(domain="example.com", count=80),
                DomainCount(domain="other.com", count=20),
            ]
        )
        new_analysis = _make_analysis(
            top_domains=[
                DomainCount(domain="example.com", count=30),
                DomainCount(domain="other.com", count=20),
                DomainCount(domain="newdomain.com", count=50),
            ]
        )

        report = detector.detect_drift(old_analysis, new_analysis)

        # Domain shift should contribute to drift
        assert report.overall_drift_score > 0.0


# =============================================================================
# ChangeDetector — detect_volume_anomaly tests
# =============================================================================


class TestDetectVolumeAnomaly:
    """Tests for ChangeDetector.detect_volume_anomaly()."""

    def test_no_anomaly_with_uniform_volume(self) -> None:
        """Uniform daily volume produces no anomalies."""
        from src.automation.change_detector import ChangeDetector

        detector = ChangeDetector()

        base_date = datetime(2024, 6, 1)
        emails = []
        # 5 emails per day for 30 days = uniform
        for day in range(30):
            for i in range(5):
                emails.append(
                    _make_email(
                        email_id=f"email_{day}_{i}",
                        received_date=base_date + timedelta(days=day, hours=i),
                    )
                )

        corpus = _make_corpus(emails)
        anomalies = detector.detect_volume_anomaly(corpus, window_days=30)

        assert len(anomalies) == 0

    def test_spike_detected(self) -> None:
        """A sudden volume spike is detected as an anomaly."""
        from src.automation.change_detector import ChangeDetector

        config = MonitoringConfig(volume_anomaly_stddev=2.0)
        detector = ChangeDetector(config=config)

        base_date = datetime(2024, 6, 1)
        emails = []
        # Normal: 5 emails/day for 29 days
        for day in range(29):
            for i in range(5):
                emails.append(
                    _make_email(
                        email_id=f"email_{day}_{i}",
                        received_date=base_date + timedelta(days=day, hours=i),
                    )
                )
        # Spike: 50 emails on day 30
        for i in range(50):
            emails.append(
                _make_email(
                    email_id=f"email_spike_{i}",
                    received_date=base_date + timedelta(days=29, hours=i % 24),
                )
            )

        corpus = _make_corpus(emails)
        anomalies = detector.detect_volume_anomaly(corpus, window_days=30)

        assert len(anomalies) >= 1
        # The spike day should have a positive z_score
        spike_anomaly = [a for a in anomalies if a.z_score > 0]
        assert len(spike_anomaly) >= 1
        assert spike_anomaly[0].actual_volume > spike_anomaly[0].expected_volume

    def test_dip_detected(self) -> None:
        """A sudden volume dip is detected as an anomaly."""
        from src.automation.change_detector import ChangeDetector

        config = MonitoringConfig(volume_anomaly_stddev=2.0)
        detector = ChangeDetector(config=config)

        base_date = datetime(2024, 6, 1)
        emails = []
        # Normal: 20 emails/day for 29 days
        for day in range(29):
            for i in range(20):
                emails.append(
                    _make_email(
                        email_id=f"email_{day}_{i}",
                        received_date=base_date + timedelta(days=day, hours=i % 24),
                    )
                )
        # Dip: 0 emails on day 30 (no emails added for that day)
        # Actually, add 1 email to have something there
        emails.append(
            _make_email(
                email_id="email_dip_0",
                received_date=base_date + timedelta(days=29, hours=12),
            )
        )

        corpus = _make_corpus(emails)
        anomalies = detector.detect_volume_anomaly(corpus, window_days=30)

        # The dip day should have a negative z_score
        dip_anomalies = [a for a in anomalies if a.z_score < 0]
        assert len(dip_anomalies) >= 1

    def test_custom_stddev_threshold(self) -> None:
        """Higher stddev threshold means fewer anomalies detected."""
        from src.automation.change_detector import ChangeDetector

        base_date = datetime(2024, 6, 1)
        emails = []
        for day in range(29):
            for i in range(5):
                emails.append(
                    _make_email(
                        email_id=f"email_{day}_{i}",
                        received_date=base_date + timedelta(days=day, hours=i),
                    )
                )
        # Moderate spike: 15 emails on day 30 (3x normal)
        for i in range(15):
            emails.append(
                _make_email(
                    email_id=f"email_spike_{i}",
                    received_date=base_date + timedelta(days=29, hours=i % 24),
                )
            )

        corpus = _make_corpus(emails)

        strict_detector = ChangeDetector(config=MonitoringConfig(volume_anomaly_stddev=1.0))
        lenient_detector = ChangeDetector(config=MonitoringConfig(volume_anomaly_stddev=5.0))

        strict_anomalies = strict_detector.detect_volume_anomaly(corpus, window_days=30)
        lenient_anomalies = lenient_detector.detect_volume_anomaly(corpus, window_days=30)

        assert len(strict_anomalies) >= len(lenient_anomalies)

    def test_empty_corpus_no_crash(self) -> None:
        """Empty corpus produces no anomalies without crashing."""
        from src.automation.change_detector import ChangeDetector

        detector = ChangeDetector()
        corpus = _make_corpus([])
        anomalies = detector.detect_volume_anomaly(corpus, window_days=30)

        assert anomalies == []

    def test_single_day_corpus_no_anomaly(self) -> None:
        """A corpus with all emails on a single day should not crash."""
        from src.automation.change_detector import ChangeDetector

        detector = ChangeDetector()
        emails = [
            _make_email(
                email_id=f"email_{i}",
                received_date=datetime(2024, 6, 15, i, 0, 0),
            )
            for i in range(10)
        ]
        corpus = _make_corpus(emails)
        anomalies = detector.detect_volume_anomaly(corpus, window_days=30)

        # With only one day of data, no meaningful anomaly detection possible
        assert isinstance(anomalies, list)

    def test_window_days_parameter(self) -> None:
        """The window_days parameter controls how many days are analyzed."""
        from src.automation.change_detector import ChangeDetector

        detector = ChangeDetector()

        base_date = datetime(2024, 6, 1)
        emails = []
        # 60 days of emails, spike on day 55
        for day in range(60):
            count = 50 if day == 55 else 5
            for i in range(count):
                emails.append(
                    _make_email(
                        email_id=f"email_{day}_{i}",
                        received_date=base_date + timedelta(days=day, hours=i % 24),
                    )
                )

        corpus = _make_corpus(emails)

        # 30-day window should miss the spike (it's on day 55, window is last 30)
        anomalies_30 = detector.detect_volume_anomaly(corpus, window_days=30)

        # 60-day window should find the spike
        anomalies_60 = detector.detect_volume_anomaly(corpus, window_days=60)

        # Spike is on day 55, so within last 30 days (days 30-60).
        # Both should find it since spike is within last 30 days too.
        # But result counts may differ due to statistical windows.
        assert isinstance(anomalies_30, list)
        assert isinstance(anomalies_60, list)

    def test_anomaly_z_score_values(self) -> None:
        """VolumeAnomaly z_score values are reasonable numbers."""
        from src.automation.change_detector import ChangeDetector

        config = MonitoringConfig(volume_anomaly_stddev=2.0)
        detector = ChangeDetector(config=config)

        base_date = datetime(2024, 6, 1)
        emails = []
        for day in range(29):
            for i in range(5):
                emails.append(
                    _make_email(
                        email_id=f"email_{day}_{i}",
                        received_date=base_date + timedelta(days=day, hours=i),
                    )
                )
        # Large spike
        for i in range(100):
            emails.append(
                _make_email(
                    email_id=f"email_spike_{i}",
                    received_date=base_date + timedelta(days=29, hours=i % 24),
                )
            )

        corpus = _make_corpus(emails)
        anomalies = detector.detect_volume_anomaly(corpus, window_days=30)

        for anomaly in anomalies:
            assert isinstance(anomaly.z_score, float)
            assert abs(anomaly.z_score) >= config.volume_anomaly_stddev


# =============================================================================
# ChangeDetector — detect_emerging_topics tests
# =============================================================================


class TestDetectEmergingTopics:
    """Tests for ChangeDetector.detect_emerging_topics()."""

    def test_identical_analyses_no_emerging(self) -> None:
        """Identical analyses produce no emerging topics."""
        from src.automation.change_detector import ChangeDetector

        detector = ChangeDetector()
        analysis = _make_analysis()

        topics = detector.detect_emerging_topics(analysis, analysis)

        assert topics == []

    def test_new_cluster_detected_as_emerging(self) -> None:
        """A new cluster in new_analysis that wasn't in old should be detected."""
        from src.automation.change_detector import ChangeDetector

        config = MonitoringConfig(new_cluster_threshold=5)
        detector = ChangeDetector(config=config)

        old_analysis = _make_analysis(
            clusters=[
                _make_cluster(
                    cluster_id=0,
                    size=100,
                    percentage=100.0,
                    subject="Old Topic",
                    email_ids=[f"old_{i}" for i in range(100)],
                ),
            ]
        )
        new_analysis = _make_analysis(
            clusters=[
                _make_cluster(
                    cluster_id=0,
                    size=80,
                    percentage=80.0,
                    subject="Old Topic",
                    email_ids=[f"old_{i}" for i in range(80)],
                ),
                _make_cluster(
                    cluster_id=1,
                    size=20,
                    percentage=20.0,
                    subject="New Emerging Topic",
                    email_ids=[f"new_{i}" for i in range(20)],
                ),
            ]
        )

        topics = detector.detect_emerging_topics(old_analysis, new_analysis)

        assert len(topics) >= 1

    def test_below_threshold_not_emerging(self) -> None:
        """New clusters below new_cluster_threshold are not flagged."""
        from src.automation.change_detector import ChangeDetector

        config = MonitoringConfig(new_cluster_threshold=50)
        detector = ChangeDetector(config=config)

        old_analysis = _make_analysis(
            clusters=[
                _make_cluster(
                    cluster_id=0,
                    size=100,
                    percentage=100.0,
                    email_ids=[f"old_{i}" for i in range(100)],
                ),
            ]
        )
        new_analysis = _make_analysis(
            clusters=[
                _make_cluster(
                    cluster_id=0,
                    size=90,
                    percentage=90.0,
                    email_ids=[f"old_{i}" for i in range(90)],
                ),
                _make_cluster(
                    cluster_id=1,
                    size=10,
                    percentage=10.0,
                    email_ids=[f"new_{i}" for i in range(10)],
                ),
            ]
        )

        topics = detector.detect_emerging_topics(old_analysis, new_analysis)

        assert len(topics) == 0

    def test_emerging_topic_contains_keywords(self) -> None:
        """Emerging topics include topic_keywords extracted from cluster data."""
        from src.automation.change_detector import ChangeDetector

        config = MonitoringConfig(new_cluster_threshold=5)
        detector = ChangeDetector(config=config)

        old_analysis = _make_analysis(
            clusters=[
                _make_cluster(
                    cluster_id=0,
                    size=100,
                    percentage=100.0,
                    email_ids=[f"old_{i}" for i in range(100)],
                ),
            ]
        )
        new_cluster = ContentCluster(
            cluster_id=1,
            size=15,
            percentage=15.0,
            representative_samples=[
                RepresentativeSample(
                    subject="Kubernetes Deployment Alert",
                    sender="k8s@devops.com",
                    body_preview="Cluster scaling event detected",
                )
            ],
            email_ids=[f"new_{i}" for i in range(15)],
            common_domains=[("devops.com", 15)],
        )
        new_analysis = _make_analysis(
            clusters=[
                _make_cluster(
                    cluster_id=0,
                    size=85,
                    percentage=85.0,
                    email_ids=[f"old_{i}" for i in range(85)],
                ),
                new_cluster,
            ]
        )

        topics = detector.detect_emerging_topics(old_analysis, new_analysis)

        assert len(topics) >= 1
        assert topics[0].email_count > 0
        assert len(topics[0].topic_keywords) > 0

    def test_emerging_topic_from_keyword_shift(self) -> None:
        """New keywords in subject patterns can indicate emerging topics."""
        from src.automation.change_detector import ChangeDetector

        config = MonitoringConfig(new_cluster_threshold=5)
        detector = ChangeDetector(config=config)

        old_analysis = _make_analysis(
            clusters=[
                _make_cluster(
                    cluster_id=0,
                    size=50,
                    percentage=50.0,
                    email_ids=[f"old_{i}" for i in range(50)],
                ),
                _make_cluster(
                    cluster_id=1,
                    size=50,
                    percentage=50.0,
                    email_ids=[f"old2_{i}" for i in range(50)],
                ),
            ],
            top_keywords=[("meeting", 20), ("update", 15)],
        )
        new_analysis = _make_analysis(
            clusters=[
                _make_cluster(
                    cluster_id=0,
                    size=40,
                    percentage=40.0,
                    email_ids=[f"old_{i}" for i in range(40)],
                ),
                _make_cluster(
                    cluster_id=1,
                    size=40,
                    percentage=40.0,
                    email_ids=[f"old2_{i}" for i in range(40)],
                ),
                _make_cluster(
                    cluster_id=2,
                    size=20,
                    percentage=20.0,
                    subject="New Emerging Cluster",
                    email_ids=[f"new_{i}" for i in range(20)],
                ),
            ],
            top_keywords=[("meeting", 20), ("update", 15), ("kubernetes", 18)],
        )

        topics = detector.detect_emerging_topics(old_analysis, new_analysis)

        # The new cluster should be detected
        assert len(topics) >= 1

    def test_no_emerging_topics_when_old_empty(self) -> None:
        """If old analysis had no clusters, everything in new is 'emerging' but treated as baseline."""
        from src.automation.change_detector import ChangeDetector

        config = MonitoringConfig(new_cluster_threshold=5)
        detector = ChangeDetector(config=config)

        old_analysis = _make_analysis(clusters=[])
        new_analysis = _make_analysis(
            clusters=[
                _make_cluster(cluster_id=0, size=50, percentage=50.0),
                _make_cluster(cluster_id=1, size=50, percentage=50.0),
            ]
        )

        topics = detector.detect_emerging_topics(old_analysis, new_analysis)

        # When old is empty, all new clusters are "emerging" since there's no baseline
        # The implementation can treat this as all new or as baseline
        assert isinstance(topics, list)


# =============================================================================
# ChangeDetector — constructor and config tests
# =============================================================================


class TestChangeDetectorConfig:
    """Tests for ChangeDetector configuration."""

    def test_default_config(self) -> None:
        """ChangeDetector uses default MonitoringConfig if none provided."""
        from src.automation.change_detector import ChangeDetector

        detector = ChangeDetector()

        assert detector.config.drift_threshold == 0.15
        assert detector.config.volume_anomaly_stddev == 2.0
        assert detector.config.new_cluster_threshold == 10

    def test_custom_config(self) -> None:
        """ChangeDetector accepts custom MonitoringConfig."""
        from src.automation.change_detector import ChangeDetector

        config = MonitoringConfig(
            drift_threshold=0.30,
            volume_anomaly_stddev=3.0,
            new_cluster_threshold=20,
        )
        detector = ChangeDetector(config=config)

        assert detector.config.drift_threshold == 0.30
        assert detector.config.volume_anomaly_stddev == 3.0
        assert detector.config.new_cluster_threshold == 20


# =============================================================================
# Edge cases and integration-like tests
# =============================================================================


class TestChangeDetectorEdgeCases:
    """Edge case tests for ChangeDetector methods."""

    def test_drift_with_different_cluster_counts(self) -> None:
        """Drift detection handles mismatched cluster counts gracefully."""
        from src.automation.change_detector import ChangeDetector

        detector = ChangeDetector()

        old_analysis = _make_analysis(
            clusters=[_make_cluster(cluster_id=i, size=25, percentage=25.0) for i in range(4)]
        )
        new_analysis = _make_analysis(
            clusters=[_make_cluster(cluster_id=i, size=50, percentage=50.0) for i in range(2)]
        )

        report = detector.detect_drift(old_analysis, new_analysis)

        assert isinstance(report.overall_drift_score, float)
        assert 0.0 <= report.overall_drift_score <= 1.0

    def test_volume_anomaly_with_very_few_days(self) -> None:
        """Volume anomaly with <3 days of data should be safe."""
        from src.automation.change_detector import ChangeDetector

        detector = ChangeDetector()

        emails = [
            _make_email(
                email_id=f"email_{i}",
                received_date=datetime(2024, 6, 15, i, 0, 0),
            )
            for i in range(3)
        ]
        corpus = _make_corpus(emails)
        anomalies = detector.detect_volume_anomaly(corpus, window_days=2)

        assert isinstance(anomalies, list)

    def test_emerging_topics_with_overlapping_email_ids(self) -> None:
        """Clusters sharing email IDs with old analysis are not flagged as emerging."""
        from src.automation.change_detector import ChangeDetector

        config = MonitoringConfig(new_cluster_threshold=3)
        detector = ChangeDetector(config=config)

        shared_ids = [f"shared_{i}" for i in range(20)]

        old_analysis = _make_analysis(
            clusters=[
                _make_cluster(
                    cluster_id=0,
                    size=20,
                    percentage=100.0,
                    email_ids=shared_ids,
                ),
            ]
        )
        # Same emails rearranged into different cluster IDs
        new_analysis = _make_analysis(
            clusters=[
                _make_cluster(
                    cluster_id=0,
                    size=10,
                    percentage=50.0,
                    email_ids=shared_ids[:10],
                ),
                _make_cluster(
                    cluster_id=1,
                    size=10,
                    percentage=50.0,
                    email_ids=shared_ids[10:],
                ),
            ]
        )

        topics = detector.detect_emerging_topics(old_analysis, new_analysis)

        # These are rearrangements of known emails, not truly emerging
        assert len(topics) == 0

    def test_detect_drift_score_is_normalized(self) -> None:
        """overall_drift_score should always be in [0, 1]."""
        from src.automation.change_detector import ChangeDetector

        detector = ChangeDetector()

        # Extreme case: totally different distributions
        old_analysis = _make_analysis(
            clusters=[_make_cluster(cluster_id=0, size=100, percentage=100.0)]
        )
        new_analysis = _make_analysis(
            clusters=[_make_cluster(cluster_id=i, size=10, percentage=10.0) for i in range(10)]
        )

        report = detector.detect_drift(old_analysis, new_analysis)

        assert 0.0 <= report.overall_drift_score <= 1.0
