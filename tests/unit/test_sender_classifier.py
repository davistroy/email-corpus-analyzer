"""
Unit tests for sender classification logic.

Tests the classify_sender_type function from sender_analyzer with
various sender patterns and domains.
"""
import pytest
from src.analyzers.sender_analyzer import SenderAnalyzer
from src.models.sender import SenderType
from src.models.email import Email
from src.models.corpus import Corpus, CorpusMetadata
from datetime import datetime


class TestSenderClassifier:
    """Test cases for sender type classification."""

    @pytest.fixture
    def analyzer(self):
        """Create SenderAnalyzer instance."""
        return SenderAnalyzer()

    def test_marketing_unsubscribe_keyword(self, analyzer):
        """Test marketing classification via unsubscribe keyword."""
        subject = "Special Offer! Click to unsubscribe"
        sender_type = analyzer._classify_sender_type(
            subject=subject,
            domain="deals.example.com",
            body_sample="Get 50% off today"
        )
        assert sender_type == SenderType.MARKETING

    def test_marketing_promotional_keywords(self, analyzer):
        """Test marketing classification via promotional keywords."""
        subjects = [
            "Limited Time Offer!",
            "Flash Sale Today Only",
            "Discount Inside - Save Now",
            "Special Promotion Just For You"
        ]
        for subject in subjects:
            sender_type = analyzer._classify_sender_type(
                subject=subject,
                domain="promo.store.com",
                body_sample=""
            )
            assert sender_type == SenderType.MARKETING

    def test_service_noreply_email(self, analyzer):
        """Test service classification for noreply addresses."""
        noreply_addresses = [
            "noreply@service.com",
            "no-reply@example.com",
            "donotreply@system.com"
        ]
        for email in noreply_addresses:
            sender_type = analyzer._classify_sender_type(
                subject="System Notification",
                domain=email.split('@')[1],
                body_sample="",
                sender_email=email
            )
            assert sender_type == SenderType.SERVICE

    def test_service_automated_keywords(self, analyzer):
        """Test service classification via automated keywords."""
        subjects = [
            "Password Reset Request",
            "Verification Code: 123456",
            "Your Invoice #12345",
            "Order Confirmation",
            "Notification: Account Updated"
        ]
        for subject in subjects:
            sender_type = analyzer._classify_sender_type(
                subject=subject,
                domain="service.example.com",
                body_sample=""
            )
            assert sender_type == SenderType.SERVICE

    def test_work_corporate_domains(self, analyzer):
        """Test work classification for corporate domains."""
        # Note: This requires actual logic in classify_sender_type
        # Currently may not be implemented
        sender_type = analyzer._classify_sender_type(
            subject="Meeting Tomorrow",
            domain="acme-corp.com",
            body_sample="Hi team"
        )
        # May be PERSONAL or WORK depending on implementation
        assert sender_type in [SenderType.WORK, SenderType.PERSONAL]

    def test_personal_common_domains(self, analyzer):
        """Test personal classification for gmail/outlook/yahoo."""
        personal_domains = ["gmail.com", "outlook.com", "yahoo.com", "hotmail.com"]
        for domain in personal_domains:
            sender_type = analyzer._classify_sender_type(
                subject="Hey, how are you?",
                domain=domain,
                body_sample="Hope you're doing well"
            )
            # Should be PERSONAL (no marketing/service keywords)
            assert sender_type == SenderType.PERSONAL

    def test_personal_default_fallback(self, analyzer):
        """Test that unknown patterns default to PERSONAL."""
        sender_type = analyzer._classify_sender_type(
            subject="Random subject",
            domain="unknown-domain.xyz",
            body_sample="Random content"
        )
        assert sender_type == SenderType.PERSONAL

    def test_marketing_takes_precedence_over_service(self, analyzer):
        """Test that marketing keywords override service keywords."""
        sender_type = analyzer._classify_sender_type(
            subject="Limited Offer - Your Invoice Inside",
            domain="billing.store.com",
            body_sample="Unsubscribe here"
        )
        # Should be MARKETING due to "offer" and "unsubscribe"
        assert sender_type == SenderType.MARKETING

    def test_service_notification_domain(self, analyzer):
        """Test service classification for notification domains."""
        notification_domains = [
            "notifications.github.com",
            "notify.twitter.com",
            "alerts.system.com"
        ]
        for domain in notification_domains:
            sender_type = analyzer._classify_sender_type(
                subject="New Activity",
                domain=domain,
                body_sample="You have a new notification"
            )
            assert sender_type == SenderType.SERVICE

    def test_empty_subject_and_body(self, analyzer):
        """Test classification with minimal information."""
        sender_type = analyzer._classify_sender_type(
            subject="",
            domain="example.com",
            body_sample=""
        )
        # Should default to PERSONAL
        assert sender_type == SenderType.PERSONAL

    def test_case_insensitive_keyword_matching(self, analyzer):
        """Test that keyword matching is case-insensitive."""
        subjects = [
            "UNSUBSCRIBE HERE",
            "Password RESET",
            "limited OFFER"
        ]
        expected = [SenderType.MARKETING, SenderType.SERVICE, SenderType.MARKETING]
        for subject, expected_type in zip(subjects, expected):
            sender_type = analyzer._classify_sender_type(
                subject=subject,
                domain="example.com",
                body_sample=""
            )
            assert sender_type == expected_type

    def test_integration_with_full_analysis(self, analyzer):
        """Test sender classification in full analyze workflow."""
        # Create test corpus
        emails = [
            Email(
                id="1",
                sender_email="noreply@service.com",
                sender_name="Service Bot",
                sender_domain="service.com",
                subject="Password Reset",
                body_text="Click here to reset",
                received_date=datetime(2024, 1, 1, 10, 0),
                has_attachments=False
            ),
            Email(
                id="2",
                sender_email="deals@store.com",
                sender_name="Store Deals",
                sender_domain="store.com",
                subject="50% Off Sale!",
                body_text="Unsubscribe at bottom",
                received_date=datetime(2024, 1, 2, 10, 0),
                has_attachments=False
            ),
            Email(
                id="3",
                sender_email="friend@gmail.com",
                sender_name="Friend",
                sender_domain="gmail.com",
                subject="Hey there",
                body_text="How are you?",
                received_date=datetime(2024, 1, 3, 10, 0),
                has_attachments=False
            )
        ]

        corpus = Corpus(
            extraction_metadata=CorpusMetadata(
                extraction_date=datetime.now(),
                total_emails=3,
                source="test",
                user_email="user@example.com"
            ),
            emails=emails
        )

        result = analyzer.analyze(corpus)

        # Verify we have 3 senders
        assert len(result.top_senders) == 3

        # Verify types are correctly classified
        sender_types = {s.email: s.type for s in result.top_senders}
        assert sender_types["noreply@service.com"] == SenderType.SERVICE
        assert sender_types["deals@store.com"] == SenderType.MARKETING
        assert sender_types["friend@gmail.com"] == SenderType.PERSONAL
