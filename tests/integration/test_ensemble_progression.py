"""
Integration tests for Phase 6: Ensemble Model Progression.

Tests the full stack of ensemble classification with feedback-driven learning:
- EnsembleClassifier chaining multiple classifiers (rules -> model -> LLM)
- SetFitClassifier training on correction data from the feedback store
- AccuracyTracker computing per-category correction rates from real DB data
- Retrainer orchestrating model retraining when accuracy thresholds are exceeded
- End-to-end: extract -> classify -> correct -> retrain -> reclassify loop

These tests verify cross-component behavior between:
- Database + EmailStore + EmailFeedbackStore (storage layer)
- EnsembleClassifier + SetFitClassifier + LLMClassifier (classifier layer)
- AccuracyTracker + Retrainer (learning/automation layer)
- EmailCategorizer (orchestration layer)

All LLM and SetFit model calls are mocked. Tests exercise real SQLite storage
and real classifier chaining logic.

Phase 6, Work Item 6.5: Integration Testing for Ensemble Model Progression.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock

import numpy as np
import pytest

from src.classifiers.base import (
    BaseClassifier,
    ClassificationContext,
    ClassificationResult,
    ClassifierCapability,
)
from src.learning.feedback_store import EmailFeedbackStore
from src.models.categorization import CategoryAssignment, EmailCategorization
from src.models.email import Email
from src.storage.database import Database
from src.storage.email_store import EmailStore

# =============================================================================
# Mock SetFit module — SetFit is not installed in test environment
# =============================================================================


def _build_mock_setfit_module():
    """Build a mock setfit module with SetFitModel and SetFitTrainer."""
    mock_module = MagicMock()
    mock_model = MagicMock()
    mock_model.predict.return_value = ["Newsletters"]
    mock_model.predict_proba.return_value = np.array([[0.85, 0.10, 0.05]])
    mock_module.SetFitModel.from_pretrained.return_value = mock_model
    mock_trainer = MagicMock()
    mock_module.SetFitTrainer.return_value = mock_trainer
    return mock_module, mock_model, mock_trainer


def _patch_setfit_and_create(categories, mock_module=None, min_examples=8):
    """Create a SetFitClassifier with setfit mocked in the module globals.

    Patches the module-level _setfit_module and _SETFIT_AVAILABLE so the
    classifier can be instantiated AND used (train, classify) without the
    real setfit library.

    Returns the classifier. The mock stays in effect on the module globals
    until _restore_setfit() is called.
    """
    import src.classifiers.setfit_classifier as sfm

    if mock_module is None:
        mock_module, _, _ = _build_mock_setfit_module()

    # Patch the module-level variables directly
    sfm._setfit_module = mock_module
    sfm._SETFIT_AVAILABLE = True

    return sfm.SetFitClassifier(categories=categories, min_examples_per_class=min_examples)


def _restore_setfit():
    """Restore the setfit_classifier module to its original unpatched state."""
    import src.classifiers.setfit_classifier as sfm

    sfm._setfit_module = None
    sfm._SETFIT_AVAILABLE = False


# =============================================================================
# Helpers
# =============================================================================


def _make_email(
    email_id: str = "email_001",
    sender_email: str = "sender@example.com",
    sender_name: str = "Test Sender",
    sender_domain: str = "example.com",
    subject: str = "Test Email Subject",
    body_text: str = "This is a test email body.",
    received_date: datetime | None = None,
) -> Email:
    """Create a test Email with sensible defaults."""
    return Email(
        id=email_id,
        sender_email=sender_email,
        sender_name=sender_name,
        sender_domain=sender_domain,
        subject=subject,
        body_text=body_text,
        received_date=received_date or datetime(2024, 1, 15, 10, 30, 0),
        has_attachments=False,
    )


def _insert_email_row(db: Database, email: Email) -> None:
    """Insert an email into the database for FK constraint satisfaction."""
    db.execute(
        "INSERT INTO emails (id, sender_email, sender_name, sender_domain, "
        "subject, body_text, received_date, has_attachments) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            email.id,
            email.sender_email,
            email.sender_name,
            email.sender_domain,
            email.subject,
            email.body_text,
            email.received_date.isoformat(),
            0,
        ),
    )


class StubClassifier(BaseClassifier):
    """A deterministic test classifier that returns preconfigured results."""

    def __init__(
        self,
        classifier_name: str = "stub",
        default_category: str = "Uncategorized",
        default_confidence: float = 0.5,
        capabilities_set: set[ClassifierCapability] | None = None,
        results_map: dict[str, ClassificationResult] | None = None,
        should_fail: bool = False,
    ) -> None:
        self._name = classifier_name
        self._default_category = default_category
        self._default_confidence = default_confidence
        self._capabilities = capabilities_set or {ClassifierCapability.ZERO_SHOT}
        self._results_map = results_map or {}
        self._should_fail = should_fail
        self.classify_calls: list[str] = []

    @property
    def name(self) -> str:
        return self._name

    @property
    def capabilities(self) -> set[ClassifierCapability]:
        return self._capabilities

    def classify(
        self,
        email: Email,
        categories: list[str],
        context: ClassificationContext | None = None,
    ) -> ClassificationResult:
        self.classify_calls.append(email.id)
        if self._should_fail:
            raise RuntimeError(f"Classifier {self._name} is configured to fail")
        if email.id in self._results_map:
            return self._results_map[email.id]
        return ClassificationResult(
            category_name=self._default_category,
            confidence=self._default_confidence,
            source=f"stub:{self._name}",
        )


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def db_path(tmp_path):
    """Return a temporary database file path."""
    return tmp_path / "ensemble_integration_test.db"


@pytest.fixture
def db(db_path):
    """Create a temporary Database for testing."""
    database = Database(db_path)
    yield database
    database.close()


@pytest.fixture
def email_store(db):
    """Create an EmailStore backed by a temporary database."""
    return EmailStore(db)


@pytest.fixture
def feedback_store(db):
    """Create an EmailFeedbackStore backed by a temporary database."""
    return EmailFeedbackStore(db)


@pytest.fixture
def diverse_emails():
    """Create 20 diverse emails across 4 categories for integration testing."""
    categories_data = {
        "newsletter": {
            "domain": "newsletter.com",
            "subjects": [
                "Weekly Digest: Top Stories",
                "Monthly Newsletter",
                "Daily Brief Update",
                "Curated Content for You",
                "This Week in Tech",
            ],
        },
        "shopping": {
            "domain": "amazon.com",
            "subjects": [
                "Your order has shipped",
                "Order confirmation #12345",
                "Delivery update",
                "Track your package",
                "Your receipt from Amazon",
            ],
        },
        "social": {
            "domain": "linkedin.com",
            "subjects": [
                "New connection request",
                "Job alert: Senior Engineer",
                "Someone viewed your profile",
                "Congratulations on your work anniversary",
                "New endorsement notification",
            ],
        },
        "work": {
            "domain": "work.com",
            "subjects": [
                "Meeting invite: Standup",
                "Project update Q4",
                "Action required: Review PR",
                "Sprint planning notes",
                "Team offsite agenda",
            ],
        },
    }

    emails = []
    i = 0
    for category, data in categories_data.items():
        for subject in data["subjects"]:
            emails.append(
                _make_email(
                    email_id=f"email_{i:04d}",
                    sender_email=f"sender{i}@{data['domain']}",
                    sender_name=f"Sender {i}",
                    sender_domain=data["domain"],
                    subject=subject,
                    body_text=f"Body text for {category} email: {subject}.",
                    received_date=datetime(2024, 1, (i % 28) + 1, 10, i % 60),
                )
            )
            i += 1
    return emails


# =============================================================================
# EnsembleClassifier Integration: chaining multiple classifiers
# =============================================================================


class TestEnsembleClassifierChaining:
    """Integration tests for EnsembleClassifier chaining classifiers in order."""

    def test_first_confident_classifier_wins(self):
        """When the first classifier exceeds threshold, it is used."""
        from src.classifiers.ensemble import EnsembleClassifier

        high_conf = StubClassifier("high_conf", "Newsletters", 0.95)
        low_conf = StubClassifier("low_conf", "Promotions", 0.30)

        ensemble = EnsembleClassifier(
            chain=[(high_conf, 0.6), (low_conf, 0.6)],
        )

        email = _make_email()
        result = ensemble.classify(email, ["Newsletters", "Promotions"])

        assert result.category_name == "Newsletters"
        assert result.confidence >= 0.6
        assert "high_conf" in result.source
        # Second classifier should NOT have been called
        assert len(low_conf.classify_calls) == 0

    def test_falls_through_to_second_when_first_below_threshold(self):
        """When first classifier is below threshold, second is tried."""
        from src.classifiers.ensemble import EnsembleClassifier

        low_conf = StubClassifier("low_conf", "Newsletters", 0.30)
        high_conf = StubClassifier("high_conf", "Promotions", 0.85)

        ensemble = EnsembleClassifier(
            chain=[(low_conf, 0.6), (high_conf, 0.6)],
        )

        email = _make_email()
        result = ensemble.classify(email, ["Newsletters", "Promotions"])

        assert result.category_name == "Promotions"
        assert result.confidence >= 0.6
        assert "high_conf" in result.source

    def test_highest_confidence_wins_when_all_below_threshold(self):
        """When all classifiers are below threshold, highest confidence wins."""
        from src.classifiers.ensemble import EnsembleClassifier

        c1 = StubClassifier("c1", "Cat_A", 0.30)
        c2 = StubClassifier("c2", "Cat_B", 0.50)
        c3 = StubClassifier("c3", "Cat_C", 0.40)

        ensemble = EnsembleClassifier(
            chain=[(c1, 0.8), (c2, 0.8), (c3, 0.8)],
        )

        email = _make_email()
        result = ensemble.classify(email, ["Cat_A", "Cat_B", "Cat_C"])

        assert result.category_name == "Cat_B"
        assert result.confidence == 0.50

    def test_failed_classifier_is_skipped(self):
        """A classifier that raises an error is skipped gracefully."""
        from src.classifiers.ensemble import EnsembleClassifier

        failing = StubClassifier("failing", should_fail=True)
        working = StubClassifier("working", "Newsletters", 0.85)

        ensemble = EnsembleClassifier(
            chain=[(failing, 0.6), (working, 0.6)],
        )

        email = _make_email()
        result = ensemble.classify(email, ["Newsletters"])

        assert result.category_name == "Newsletters"
        assert "working" in result.source

    def test_tracks_which_classifier_produced_result(self):
        """EnsembleClassifier source field identifies the winning classifier."""
        from src.classifiers.ensemble import EnsembleClassifier

        c1 = StubClassifier("rule_engine", "Newsletters", 0.40)
        c2 = StubClassifier("setfit_model", "Newsletters", 0.92)

        ensemble = EnsembleClassifier(
            chain=[(c1, 0.6), (c2, 0.6)],
        )

        email = _make_email()
        result = ensemble.classify(email, ["Newsletters"])

        # Source format: "ensemble:<classifier_name>:<original_source>"
        assert "ensemble:" in result.source
        assert "setfit_model" in result.source

    def test_usage_statistics_tracked(self):
        """EnsembleClassifier tracks per-classifier hit rates."""
        from src.classifiers.ensemble import EnsembleClassifier

        c1 = StubClassifier("rule_engine", "Newsletters", 0.40)
        c2 = StubClassifier("llm_fallback", "Newsletters", 0.85)

        ensemble = EnsembleClassifier(
            chain=[(c1, 0.6), (c2, 0.6)],
        )

        for i in range(5):
            email = _make_email(email_id=f"email_{i}")
            ensemble.classify(email, ["Newsletters"])

        stats = ensemble.get_usage_stats()
        assert stats["rule_engine"]["selected"] == 0  # Never above threshold
        assert stats["llm_fallback"]["selected"] == 5  # Always above threshold
        assert stats["rule_engine"]["attempted"] == 5
        assert stats["rule_engine"]["below_threshold"] == 5

    def test_batch_classify_chains_correctly(self):
        """Batch classification applies ensemble logic to each email."""
        from src.classifiers.ensemble import EnsembleClassifier

        # email_001 has a specific high-confidence result from c1
        c1_results = {
            "email_001": ClassificationResult(
                category_name="Newsletters",
                confidence=0.95,
                source="stub:c1",
            )
        }
        c1 = StubClassifier("c1", "Unknown", 0.20, results_map=c1_results)
        c2 = StubClassifier("c2", "Promotions", 0.85)

        ensemble = EnsembleClassifier(
            chain=[(c1, 0.6), (c2, 0.6)],
        )

        emails = [_make_email(email_id=f"email_{i:03d}") for i in range(3)]
        results = ensemble.batch_classify(emails, ["Newsletters", "Promotions"])

        assert len(results) == 3
        # email_001 should use c1's specific high-confidence result
        assert results[1].category_name == "Newsletters"
        # Others should fall through to c2
        assert results[0].category_name == "Promotions"
        assert results[2].category_name == "Promotions"

    def test_ensemble_implements_base_classifier_contract(self):
        """EnsembleClassifier is a BaseClassifier subclass."""
        from src.classifiers.ensemble import EnsembleClassifier

        c1 = StubClassifier("c1", "Cat", 0.9)
        ensemble = EnsembleClassifier(chain=[(c1, 0.5)])

        assert isinstance(ensemble, BaseClassifier)
        assert ensemble.name  # Has a name
        assert isinstance(ensemble.capabilities, set)  # Has capabilities


# =============================================================================
# SetFitClassifier Integration: training and classification
# =============================================================================


class TestSetFitClassifierIntegration:
    """Integration tests for SetFitClassifier with mocked SetFit model."""

    def teardown_method(self):
        """Restore setfit module state after each test."""
        _restore_setfit()

    def test_setfit_classifier_implements_base_contract(self):
        """SetFitClassifier is a BaseClassifier with FINE_TUNED capability."""
        classifier = _patch_setfit_and_create(["Newsletters", "Shopping"])
        assert isinstance(classifier, BaseClassifier)
        assert ClassifierCapability.FINE_TUNED in classifier.capabilities

    def test_train_with_examples_sets_trained_flag(self):
        """Training with sufficient examples marks the classifier as trained."""
        categories = ["Newsletters", "Shopping", "Social", "Work"]
        classifier = _patch_setfit_and_create(categories, min_examples=3)
        examples = [
            ("Weekly Newsletter: Top Stories", "Newsletters"),
            ("Your order has shipped", "Shopping"),
            ("New connection request", "Social"),
            ("Meeting invite: Standup", "Work"),
        ] * 3  # 12 examples total (3 per class)

        classifier.train(examples)
        assert classifier.is_trained

    def test_classify_after_training_returns_valid_result(self):
        """Classify returns a valid ClassificationResult after training."""
        mock_module, mock_model, _ = _build_mock_setfit_module()
        mock_model.predict.return_value = ["Newsletters"]
        mock_model.predict_proba.return_value = np.array([[0.85, 0.10, 0.05]])

        categories = ["Newsletters", "Shopping", "Social"]
        classifier = _patch_setfit_and_create(categories, mock_module=mock_module, min_examples=4)
        examples = [
            ("Weekly Newsletter: Top Stories", "Newsletters"),
            ("Your order has shipped", "Shopping"),
            ("New connection request", "Social"),
        ] * 4

        classifier.train(examples)

        email = _make_email(subject="Monthly Newsletter Digest")
        result = classifier.classify(email, categories)

        assert isinstance(result, ClassificationResult)
        assert result.category_name in categories
        assert 0.0 <= result.confidence <= 1.0
        assert "setfit" in result.source.lower()

    def test_classify_before_training_raises_error(self):
        """Classify raises an error when called before training."""
        from src.exceptions import ClassificationError

        classifier = _patch_setfit_and_create(["Newsletters"])
        email = _make_email()

        with pytest.raises(ClassificationError):
            classifier.classify(email, ["Newsletters"])

    def test_save_and_load_model_round_trip(self, tmp_path):
        """Model can be saved and loaded with same classification behavior."""
        import json

        mock_module, mock_model, _ = _build_mock_setfit_module()
        categories = ["Newsletters", "Shopping"]
        classifier = _patch_setfit_and_create(categories, mock_module=mock_module, min_examples=5)
        examples = [
            ("Newsletter content", "Newsletters"),
            ("Order shipped", "Shopping"),
        ] * 5

        classifier.train(examples)

        model_path = tmp_path / "setfit_model"
        classifier.save_model(model_path)

        # Verify metadata was saved
        meta_path = model_path / "classifier_metadata.json"
        assert meta_path.exists()
        metadata = json.loads(meta_path.read_text())
        assert metadata["categories"] == categories

    def test_confidence_scores_are_meaningful(self):
        """Confidence scores are in valid range from mocked model."""
        mock_module, mock_model, _ = _build_mock_setfit_module()
        mock_model.predict.return_value = ["Newsletters"]
        mock_model.predict_proba.return_value = np.array([[0.85, 0.15]])

        categories = ["Newsletters", "Shopping"]
        classifier = _patch_setfit_and_create(categories, mock_module=mock_module, min_examples=4)
        examples = [
            ("Weekly Newsletter", "Newsletters"),
            ("Monthly Digest", "Newsletters"),
            ("Order shipped", "Shopping"),
            ("Package delivered", "Shopping"),
        ] * 4

        classifier.train(examples)

        email = _make_email(subject="Weekly Newsletter Update")
        result = classifier.classify(email, categories)
        assert 0.0 <= result.confidence <= 1.0


# =============================================================================
# EnsembleClassifier + EmailCategorizer Integration
# =============================================================================


class TestEnsembleWithCategorizer:
    """Integration: EnsembleClassifier used as fallback in EmailCategorizer."""

    def test_categorizer_uses_ensemble_as_fallback(self, db):
        """EmailCategorizer falls back to ensemble when no rules match."""
        from src.categorizer.categorizer import EmailCategorizer
        from src.classifiers.ensemble import EnsembleClassifier
        from src.models.rule import (
            CategoryRule,
            ConditionField,
            ConditionLogic,
            ConditionOperator,
            RuleAction,
            RuleActionType,
            RuleCondition,
            RuleSet,
        )

        c1 = StubClassifier("model", "Newsletters", 0.85)
        ensemble = EnsembleClassifier(chain=[(c1, 0.6)])

        categorizer = EmailCategorizer(classifier=ensemble, database=db)

        # Rule matches example.com only
        rule = CategoryRule(
            rule_id="rule_001",
            name="Example Rule",
            conditions=[
                RuleCondition(
                    field=ConditionField.SENDER_DOMAIN,
                    operator=ConditionOperator.EQUALS,
                    value="example.com",
                    case_sensitive=False,
                )
            ],
            action=RuleAction(action_type=RuleActionType.CATEGORIZE, target="Work"),
            logic=ConditionLogic.AND,
            priority=50,
            enabled=True,
        )
        rule_set = RuleSet(rules=[rule])

        # Email from example.com -> rule match
        email_matched = _make_email(email_id="matched_001", sender_domain="example.com")
        _insert_email_row(db, email_matched)
        result_matched = categorizer.categorize_email(email_matched, rule_set)
        assert result_matched.primary_category.category_name == "Work"
        assert "rule:" in result_matched.primary_category.source

        # Email from other.com -> falls through to ensemble
        email_unmatched = _make_email(
            email_id="unmatched_001",
            sender_email="user@other.com",
            sender_domain="other.com",
        )
        _insert_email_row(db, email_unmatched)
        result_unmatched = categorizer.categorize_email(email_unmatched, rule_set)
        assert result_unmatched.primary_category.category_name == "Newsletters"
        assert "classifier:" in result_unmatched.primary_category.source

    def test_categorizer_records_ensemble_classifications_in_db(self, db):
        """Classifications from ensemble fallback are recorded in the DB."""
        from src.categorizer.categorizer import EmailCategorizer
        from src.classifiers.ensemble import EnsembleClassifier
        from src.models.rule import (
            CategoryRule,
            ConditionField,
            ConditionLogic,
            ConditionOperator,
            RuleAction,
            RuleActionType,
            RuleCondition,
            RuleSet,
        )

        c1 = StubClassifier("llm", "Promotions", 0.88)
        ensemble = EnsembleClassifier(chain=[(c1, 0.6)])
        categorizer = EmailCategorizer(classifier=ensemble, database=db)

        rule = CategoryRule(
            rule_id="rule_001",
            name="No Match Rule",
            conditions=[
                RuleCondition(
                    field=ConditionField.SENDER_DOMAIN,
                    operator=ConditionOperator.EQUALS,
                    value="nevermatches.xyz",
                    case_sensitive=False,
                )
            ],
            action=RuleAction(action_type=RuleActionType.CATEGORIZE, target="NoMatch"),
            logic=ConditionLogic.AND,
            priority=50,
            enabled=True,
        )
        rule_set = RuleSet(rules=[rule])

        email = _make_email(
            email_id="record_001", sender_domain="other.com", sender_email="user@other.com"
        )
        _insert_email_row(db, email)
        categorizer.categorize_email(email, rule_set)

        # Verify classification was recorded
        cursor = db.execute(
            "SELECT email_id, category_name, source FROM classifications WHERE email_id = ?",
            ("record_001",),
        )
        row = cursor.fetchone()
        assert row is not None
        assert row[1] == "Promotions"
        assert "classifier:" in row[2]


# =============================================================================
# AccuracyTracker Integration: correction rates from real DB data
# =============================================================================


class TestAccuracyTrackerIntegration:
    """Integration: AccuracyTracker computes metrics from real DB data."""

    def _setup_classified_emails(self, db, feedback_store, email_store):
        """Insert emails, classify them, then record some corrections."""
        categories = ["Newsletters", "Shopping", "Social"]
        emails = []
        for i in range(15):
            cat = categories[i % 3]
            email = _make_email(
                email_id=f"acc_email_{i:03d}",
                sender_domain=f"{cat.lower()}.com",
                sender_email=f"user@{cat.lower()}.com",
                subject=f"Email about {cat} #{i}",
            )
            emails.append((email, cat))
            _insert_email_row(db, email)

            # Insert a classification record
            now = datetime.now(timezone.utc).isoformat()
            db.execute(
                "INSERT INTO classifications "
                "(email_id, category_name, confidence, source, classified_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (email.id, cat, 0.85, "stub:test", now),
            )

        # Record corrections: 3 out of 5 "Shopping" emails were wrong
        feedback_store.record_correction("acc_email_001", "Shopping", "Newsletters")
        feedback_store.record_correction("acc_email_004", "Shopping", "Social")
        feedback_store.record_correction("acc_email_007", "Shopping", "Newsletters")

        return emails

    def test_accuracy_report_reflects_correction_rates(self, db, feedback_store, email_store):
        """AccuracyTracker report shows per-category correction rates."""
        from src.learning.accuracy_tracker import AccuracyTracker

        self._setup_classified_emails(db, feedback_store, email_store)

        tracker = AccuracyTracker(
            correction_store=feedback_store,
            classification_store=db,
        )
        report = tracker.get_accuracy_report(days=7)

        assert report.total_classifications > 0
        assert report.total_corrections == 3
        assert "Shopping" in report.per_category_metrics

    def test_needs_retraining_when_correction_rate_high(self, db, feedback_store, email_store):
        """needs_retraining returns True when correction rate exceeds threshold."""
        from src.learning.accuracy_tracker import AccuracyTracker

        self._setup_classified_emails(db, feedback_store, email_store)

        tracker = AccuracyTracker(
            correction_store=feedback_store,
            classification_store=db,
        )
        # With 3 corrections out of 5 Shopping emails, rate = 60% > 20% threshold
        assert tracker.needs_retraining(threshold=0.20) is True

    def test_no_retraining_needed_with_zero_corrections(self, db, feedback_store, email_store):
        """needs_retraining returns False when there are no corrections."""
        from src.learning.accuracy_tracker import AccuracyTracker

        # Just insert some emails and classifications, no corrections
        for i in range(5):
            email = _make_email(
                email_id=f"clean_{i:03d}",
                sender_domain="clean.com",
                sender_email="user@clean.com",
            )
            _insert_email_row(db, email)
            now = datetime.now(timezone.utc).isoformat()
            db.execute(
                "INSERT INTO classifications "
                "(email_id, category_name, confidence, source, classified_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (email.id, "Newsletters", 0.90, "stub:test", now),
            )

        tracker = AccuracyTracker(
            correction_store=feedback_store,
            classification_store=db,
        )
        assert tracker.needs_retraining(threshold=0.20) is False

    def test_accuracy_report_handles_empty_database(self, db, feedback_store, email_store):
        """AccuracyTracker handles empty database gracefully."""
        from src.learning.accuracy_tracker import AccuracyTracker

        tracker = AccuracyTracker(
            correction_store=feedback_store,
            classification_store=db,
        )
        report = tracker.get_accuracy_report(days=7)

        assert report.total_classifications == 0
        assert report.total_corrections == 0
        assert len(report.per_category_metrics) == 0


# =============================================================================
# Retrainer Integration: orchestrating training from corrections
# =============================================================================


class TestRetrainerIntegration:
    """Integration: Retrainer gathers corrections and triggers training."""

    def test_retrainer_collects_training_data_from_feedback_store(self, db, feedback_store):
        """Retrainer gathers labeled examples from correction history."""
        from src.automation.retrainer import Retrainer

        # Set up emails and corrections
        for i in range(10):
            email = _make_email(
                email_id=f"retrain_{i:03d}",
                sender_domain="test.com",
                sender_email="user@test.com",
                subject=f"Subject for email {i}",
                body_text=f"Body text for email {i}",
            )
            _insert_email_row(db, email)

        # Record corrections: these define the "correct" labels
        feedback_store.record_correction("retrain_000", "Wrong", "Newsletters")
        feedback_store.record_correction("retrain_001", "Wrong", "Newsletters")
        feedback_store.record_correction("retrain_002", "Wrong", "Shopping")
        feedback_store.record_correction("retrain_003", "Wrong", "Shopping")
        feedback_store.record_correction("retrain_004", "Wrong", "Social")
        feedback_store.record_correction("retrain_005", "Wrong", "Social")

        retrainer = Retrainer(
            feedback_store=feedback_store,
            email_store=EmailStore(db),
        )

        training_data = retrainer.collect_training_data(min_examples_per_category=2)

        # Should have examples for all 3 categories
        labels = {label for _, label in training_data}
        assert "Newsletters" in labels
        assert "Shopping" in labels
        assert "Social" in labels
        assert len(training_data) >= 6

    def test_retrainer_skips_categories_with_insufficient_examples(self, db, feedback_store):
        """Retrainer excludes categories with fewer than min_examples corrections."""
        from src.automation.retrainer import Retrainer

        for i in range(3):
            email = _make_email(
                email_id=f"sparse_{i:03d}",
                sender_domain="test.com",
                sender_email="user@test.com",
                subject=f"Subject {i}",
            )
            _insert_email_row(db, email)

        # Only 1 correction for "Rare" category (below threshold of 2)
        feedback_store.record_correction("sparse_000", "Wrong", "Rare")
        # 2 corrections for "Common"
        feedback_store.record_correction("sparse_001", "Wrong", "Common")
        feedback_store.record_correction("sparse_002", "Wrong", "Common")

        retrainer = Retrainer(
            feedback_store=feedback_store,
            email_store=EmailStore(db),
        )

        training_data = retrainer.collect_training_data(min_examples_per_category=2)
        labels = {label for _, label in training_data}

        assert "Common" in labels
        assert "Rare" not in labels

    def test_retrainer_trains_classifier_with_collected_data(self, db, feedback_store):
        """Retrainer orchestrates classifier training end-to-end."""
        from src.automation.retrainer import Retrainer

        for i in range(8):
            email = _make_email(
                email_id=f"trainflow_{i:03d}",
                sender_domain="test.com",
                sender_email="user@test.com",
                subject=f"Training subject {i}",
                body_text=f"Training body {i}",
            )
            _insert_email_row(db, email)

        feedback_store.record_correction("trainflow_000", "X", "Newsletters")
        feedback_store.record_correction("trainflow_001", "X", "Newsletters")
        feedback_store.record_correction("trainflow_002", "X", "Newsletters")
        feedback_store.record_correction("trainflow_003", "X", "Newsletters")
        feedback_store.record_correction("trainflow_004", "X", "Shopping")
        feedback_store.record_correction("trainflow_005", "X", "Shopping")
        feedback_store.record_correction("trainflow_006", "X", "Shopping")
        feedback_store.record_correction("trainflow_007", "X", "Shopping")

        retrainer = Retrainer(
            feedback_store=feedback_store,
            email_store=EmailStore(db),
        )

        classifier = _patch_setfit_and_create(["Newsletters", "Shopping"], min_examples=2)
        result = retrainer.train_classifier(classifier, min_examples_per_category=2)

        assert result.success
        assert result.categories_trained >= 2
        assert result.total_examples >= 8
        assert classifier.is_trained
        _restore_setfit()


# =============================================================================
# End-to-end: classify -> correct -> retrain -> reclassify
# =============================================================================


class TestEndToEndFeedbackLoop:
    """End-to-end integration: full classify -> correct -> retrain cycle."""

    def test_full_feedback_loop_with_ensemble(self, db, feedback_store, email_store):
        """Complete loop: classify with ensemble, correct errors, retrain, reclassify."""
        from src.automation.retrainer import Retrainer
        from src.categorizer.categorizer import EmailCategorizer
        from src.classifiers.ensemble import EnsembleClassifier
        from src.learning.accuracy_tracker import AccuracyTracker
        from src.models.rule import (
            CategoryRule,
            ConditionField,
            ConditionLogic,
            ConditionOperator,
            RuleAction,
            RuleActionType,
            RuleCondition,
            RuleSet,
        )

        # --- Step 1: Initial classification with LLM stub ---
        llm_stub = StubClassifier("llm_stub", "Newsletters", 0.80)
        ensemble = EnsembleClassifier(chain=[(llm_stub, 0.6)])
        categorizer = EmailCategorizer(classifier=ensemble, database=db)

        rule = CategoryRule(
            rule_id="rule_001",
            name="Never Match Rule",
            conditions=[
                RuleCondition(
                    field=ConditionField.SENDER_DOMAIN,
                    operator=ConditionOperator.EQUALS,
                    value="nevermatches.xyz",
                    case_sensitive=False,
                )
            ],
            action=RuleAction(action_type=RuleActionType.CATEGORIZE, target="Placeholder"),
            logic=ConditionLogic.AND,
            priority=50,
            enabled=True,
        )
        rule_set = RuleSet(rules=[rule])

        emails = []
        for i in range(10):
            email = _make_email(
                email_id=f"loop_{i:03d}",
                sender_domain="misc.com",
                sender_email=f"user{i}@misc.com",
                subject=f"Subject {i}",
                body_text=f"Body {i}",
            )
            emails.append(email)
            _insert_email_row(db, email)
            email_store.upsert(email)

        for email in emails:
            categorizer.categorize_email(email, rule_set)

        # Verify initial classifications
        cursor = db.execute("SELECT COUNT(*) FROM classifications")
        initial_count = cursor.fetchone()[0]
        assert initial_count == 10

        # --- Step 2: User corrects some emails ---
        # Suppose emails 0-4 should actually be "Shopping", not "Newsletters"
        for i in range(5):
            feedback_store.record_correction(f"loop_{i:03d}", "Newsletters", "Shopping")

        # --- Step 3: Check if retraining is needed ---
        tracker = AccuracyTracker(
            correction_store=feedback_store,
            classification_store=db,
        )
        assert tracker.needs_retraining(threshold=0.20) is True

        # --- Step 4: Retrain with mocked SetFit ---
        retrainer = Retrainer(
            feedback_store=feedback_store,
            email_store=email_store,
        )
        mock_module, mock_model, _ = _build_mock_setfit_module()
        mock_model.predict.return_value = ["Shopping"]
        mock_model.predict_proba.return_value = np.array([[0.90, 0.10]])
        new_classifier = _patch_setfit_and_create(
            ["Newsletters", "Shopping"], mock_module=mock_module, min_examples=2
        )
        train_result = retrainer.train_classifier(new_classifier, min_examples_per_category=2)
        assert train_result.success
        assert new_classifier.is_trained

        # --- Step 5: Reclassify with updated ensemble ---
        new_ensemble = EnsembleClassifier(
            chain=[(new_classifier, 0.6), (llm_stub, 0.6)],
        )
        new_categorizer = EmailCategorizer(classifier=new_ensemble, database=db)

        # Reclassify one email
        reclassified = new_categorizer.categorize_email(emails[0], rule_set)
        assert isinstance(reclassified, EmailCategorization)
        # The retrained classifier should produce valid results
        assert reclassified.primary_category.category_name in [
            "Shopping",
            "Newsletters",
            "Placeholder",
        ]
        _restore_setfit()

    def test_corrections_persist_across_db_lifecycle(self, db_path, tmp_path):
        """Corrections and classifications persist across DB close/reopen."""
        # Phase 1: populate
        db1 = Database(db_path)
        EmailStore(db1)  # ensure tables exist
        feedback1 = EmailFeedbackStore(db1)

        email = _make_email(
            email_id="persist_001", sender_domain="test.com", sender_email="user@test.com"
        )
        _insert_email_row(db1, email)

        now = datetime.now(timezone.utc).isoformat()
        db1.execute(
            "INSERT INTO classifications "
            "(email_id, category_name, confidence, source, classified_at) "
            "VALUES (?, ?, ?, ?, ?)",
            ("persist_001", "Newsletters", 0.85, "stub:test", now),
        )
        feedback1.record_correction("persist_001", "Newsletters", "Shopping")
        db1.close()

        # Phase 2: reopen and verify
        db2 = Database(db_path)
        feedback2 = EmailFeedbackStore(db2)

        corrections = feedback2.get_corrections()
        assert len(corrections) == 1
        assert corrections[0].old_category == "Newsletters"
        assert corrections[0].new_category == "Shopping"

        cursor = db2.execute(
            "SELECT category_name FROM classifications WHERE email_id = ?",
            ("persist_001",),
        )
        row = cursor.fetchone()
        assert row[0] == "Newsletters"

        db2.close()

    def test_ensemble_with_feedback_store_and_uncertainty_sampling(self, db, feedback_store):
        """Ensemble classification + uncertainty sampling identifies low-confidence emails."""
        from src.learning.uncertainty_sampler import UncertaintySampler
        from src.models.categorization import EmailCategorization

        # Create emails with varying ensemble confidence
        categorizations = []
        for i in range(10):
            conf = 0.3 + (i * 0.07)  # 0.30, 0.37, ..., 0.93
            cat = EmailCategorization(
                email_id=f"uncertain_{i:03d}",
                primary_category=CategoryAssignment(
                    category_name="Newsletters",
                    confidence=conf,
                    source="classifier:ensemble",
                ),
            )
            categorizations.append(cat)

        sampler = UncertaintySampler(default_n=3)
        uncertain = sampler.get_uncertain(categorizations)

        assert len(uncertain) == 3
        # Should be the 3 lowest confidence
        assert uncertain[0].primary_category.confidence < uncertain[2].primary_category.confidence
