"""
Unit tests for Phase 5, Work Item 5.1: EmailFeedbackStore with Temporal Decay.

Tests the EmailFeedbackStore class with:
- Correction recording and retrieval
- Temporal decay weight calculation (exp(-0.01 * days_old))
- Category filtering on corrections
- Correction statistics (total, per-category, correction rate)
- Edge cases: empty store, duplicate corrections, boundary weights

TDD: Tests written before implementation.
"""

import math
from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

from src.storage.database import Database

# =============================================================================
# Helpers
# =============================================================================


def _insert_stub_email(db: Database, email_id: str) -> None:
    """Insert a minimal stub email into the emails table to satisfy FK constraints."""
    now = datetime.now(timezone.utc).isoformat()
    db.execute(
        "INSERT OR IGNORE INTO emails "
        "(id, sender_email, sender_domain, subject, body_text, received_date, has_attachments) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (email_id, "test@test.com", "test.com", "Test", "Body", now, 0),
    )


def _insert_stub_emails(db: Database, email_ids: list[str]) -> None:
    """Insert multiple stub emails."""
    for eid in email_ids:
        _insert_stub_email(db, eid)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def db(tmp_path):
    """Create a temporary Database for testing."""
    db = Database(tmp_path / "test.db")
    yield db
    db.close()


@pytest.fixture
def feedback_store(db):
    """Create an EmailFeedbackStore backed by a temporary database."""
    from src.learning.feedback_store import EmailFeedbackStore

    return EmailFeedbackStore(database=db)


# =============================================================================
# Pydantic model tests
# =============================================================================


class TestCorrectionModel:
    """Test the Correction Pydantic model."""

    def test_correction_model_exists(self):
        """Test that Correction model can be imported."""
        from src.learning.feedback_store import Correction

        assert Correction is not None

    def test_correction_fields(self):
        """Test that Correction model has required fields."""
        from src.learning.feedback_store import Correction

        c = Correction(
            id=1,
            email_id="email_001",
            old_category="Newsletters",
            new_category="Marketing",
            corrected_at=datetime.now(timezone.utc),
        )
        assert c.id == 1
        assert c.email_id == "email_001"
        assert c.old_category == "Newsletters"
        assert c.new_category == "Marketing"
        assert c.corrected_at is not None

    def test_correction_validates_email_id(self):
        """Test that Correction validates email_id is non-empty."""
        from pydantic import ValidationError

        from src.learning.feedback_store import Correction

        with pytest.raises(ValidationError):
            Correction(
                id=1,
                email_id="",
                old_category="A",
                new_category="B",
                corrected_at=datetime.now(timezone.utc),
            )

    def test_correction_validates_categories_different(self):
        """Test that old_category and new_category must be different."""
        from pydantic import ValidationError

        from src.learning.feedback_store import Correction

        with pytest.raises(ValidationError):
            Correction(
                id=1,
                email_id="email_001",
                old_category="Same",
                new_category="Same",
                corrected_at=datetime.now(timezone.utc),
            )


class TestWeightedCorrectionModel:
    """Test the WeightedCorrection Pydantic model."""

    def test_weighted_correction_model_exists(self):
        """Test that WeightedCorrection model can be imported."""
        from src.learning.feedback_store import WeightedCorrection

        assert WeightedCorrection is not None

    def test_weighted_correction_fields(self):
        """Test that WeightedCorrection has all required fields."""
        from src.learning.feedback_store import WeightedCorrection

        wc = WeightedCorrection(
            id=1,
            email_id="email_001",
            old_category="A",
            new_category="B",
            corrected_at=datetime.now(timezone.utc),
            weight=0.95,
        )
        assert wc.weight == 0.95

    def test_weighted_correction_weight_range(self):
        """Test that weight must be between 0.0 and 1.0."""
        from pydantic import ValidationError

        from src.learning.feedback_store import WeightedCorrection

        with pytest.raises(ValidationError):
            WeightedCorrection(
                id=1,
                email_id="email_001",
                old_category="A",
                new_category="B",
                corrected_at=datetime.now(timezone.utc),
                weight=1.5,
            )

        with pytest.raises(ValidationError):
            WeightedCorrection(
                id=1,
                email_id="email_001",
                old_category="A",
                new_category="B",
                corrected_at=datetime.now(timezone.utc),
                weight=-0.1,
            )


# =============================================================================
# EmailFeedbackStore instantiation tests
# =============================================================================


class TestFeedbackStoreCreation:
    """Test EmailFeedbackStore instantiation."""

    def test_feedback_store_class_exists(self):
        """Test that EmailFeedbackStore class can be imported."""
        from src.learning.feedback_store import EmailFeedbackStore

        assert EmailFeedbackStore is not None

    def test_feedback_store_creates_with_database(self, db):
        """Test that EmailFeedbackStore can be created with a Database."""
        from src.learning.feedback_store import EmailFeedbackStore

        store = EmailFeedbackStore(database=db)
        assert store is not None

    def test_feedback_store_requires_database(self):
        """Test that EmailFeedbackStore requires a Database instance."""
        from src.learning.feedback_store import EmailFeedbackStore

        with pytest.raises(TypeError):
            EmailFeedbackStore()


# =============================================================================
# record_correction tests
# =============================================================================


class TestRecordCorrection:
    """Test recording corrections."""

    def test_record_correction_basic(self, feedback_store, db):
        """Test recording a basic correction without embedding."""
        _insert_stub_email(db, "email_001")
        feedback_store.record_correction(
            email_id="email_001",
            old_category="Newsletters",
            new_category="Marketing",
        )
        corrections = feedback_store.get_corrections()
        assert len(corrections) == 1
        assert corrections[0].email_id == "email_001"
        assert corrections[0].old_category == "Newsletters"
        assert corrections[0].new_category == "Marketing"

    def test_record_correction_with_embedding(self, feedback_store, db):
        """Test recording a correction with an embedding vector."""
        _insert_stub_email(db, "email_002")
        embedding = np.array([0.1, 0.2, 0.3, 0.4, 0.5], dtype=np.float32)
        feedback_store.record_correction(
            email_id="email_002",
            old_category="Spam",
            new_category="Promotions",
            embedding=embedding,
        )
        corrections = feedback_store.get_corrections()
        assert len(corrections) == 1
        assert corrections[0].email_id == "email_002"

    def test_record_correction_without_embedding(self, feedback_store, db):
        """Test recording a correction with embedding=None (default)."""
        _insert_stub_email(db, "email_003")
        feedback_store.record_correction(
            email_id="email_003",
            old_category="A",
            new_category="B",
            embedding=None,
        )
        corrections = feedback_store.get_corrections()
        assert len(corrections) == 1

    def test_record_multiple_corrections(self, feedback_store, db):
        """Test recording multiple corrections."""
        _insert_stub_emails(db, ["email_001", "email_002", "email_003"])
        feedback_store.record_correction("email_001", "A", "B")
        feedback_store.record_correction("email_002", "C", "D")
        feedback_store.record_correction("email_003", "E", "F")

        corrections = feedback_store.get_corrections()
        assert len(corrections) == 3

    def test_record_correction_sets_timestamp(self, feedback_store, db):
        """Test that recording a correction sets a valid UTC timestamp."""
        _insert_stub_email(db, "email_001")
        before = datetime.now(timezone.utc)
        feedback_store.record_correction("email_001", "A", "B")
        after = datetime.now(timezone.utc)

        corrections = feedback_store.get_corrections()
        assert len(corrections) == 1
        # Timestamp should be between before and after
        assert corrections[0].corrected_at >= before
        assert corrections[0].corrected_at <= after

    def test_record_correction_same_email_multiple_times(self, feedback_store, db):
        """Test that the same email can have multiple corrections (re-corrections)."""
        _insert_stub_email(db, "email_001")
        feedback_store.record_correction("email_001", "A", "B")
        feedback_store.record_correction("email_001", "B", "C")

        corrections = feedback_store.get_corrections()
        assert len(corrections) == 2

    def test_record_correction_persists_in_database(self, db):
        """Test that corrections are persisted in SQLite."""
        from src.learning.feedback_store import EmailFeedbackStore

        _insert_stub_email(db, "email_001")
        store1 = EmailFeedbackStore(database=db)
        store1.record_correction("email_001", "A", "B")

        # Create a new store instance with the same database
        store2 = EmailFeedbackStore(database=db)
        corrections = store2.get_corrections()
        assert len(corrections) == 1
        assert corrections[0].email_id == "email_001"

    def test_record_correction_returns_correction_id(self, feedback_store, db):
        """Test that record_correction returns the new correction's auto-incremented ID."""
        _insert_stub_email(db, "email_001")
        cid = feedback_store.record_correction("email_001", "A", "B")
        assert isinstance(cid, int)
        assert cid > 0

    def test_record_correction_successive_ids_increment(self, feedback_store, db):
        """Test that successive record_correction calls return incrementing IDs."""
        _insert_stub_emails(db, ["email_001", "email_002"])
        id1 = feedback_store.record_correction("email_001", "A", "B")
        id2 = feedback_store.record_correction("email_002", "C", "D")
        assert id2 > id1


# =============================================================================
# get_corrections tests
# =============================================================================


class TestGetCorrections:
    """Test retrieving corrections with filtering."""

    def test_get_corrections_empty_store(self, feedback_store):
        """Test that empty store returns empty list, not an error."""
        corrections = feedback_store.get_corrections()
        assert corrections == []

    def test_get_corrections_all(self, feedback_store, db):
        """Test getting all corrections without filters."""
        _insert_stub_emails(db, ["e1", "e2"])
        feedback_store.record_correction("e1", "A", "B")
        feedback_store.record_correction("e2", "C", "D")

        corrections = feedback_store.get_corrections()
        assert len(corrections) == 2

    def test_get_corrections_filter_by_category(self, feedback_store, db):
        """Test filtering corrections by new_category."""
        _insert_stub_emails(db, ["e1", "e2", "e3"])
        feedback_store.record_correction("e1", "A", "Marketing")
        feedback_store.record_correction("e2", "B", "Newsletters")
        feedback_store.record_correction("e3", "C", "Marketing")

        corrections = feedback_store.get_corrections(category="Marketing")
        assert len(corrections) == 2
        assert all(c.new_category == "Marketing" for c in corrections)

    def test_get_corrections_filter_by_category_no_match(self, feedback_store, db):
        """Test filtering by a category that has no corrections."""
        _insert_stub_email(db, "e1")
        feedback_store.record_correction("e1", "A", "Marketing")

        corrections = feedback_store.get_corrections(category="NonExistent")
        assert corrections == []

    def test_get_corrections_filter_by_days(self, feedback_store, db):
        """Test filtering corrections by days (time range)."""
        now = datetime.now(timezone.utc)

        # Insert stub emails
        _insert_stub_emails(db, ["e_old", "e_new"])

        # Insert a correction dated 5 days ago directly into db
        five_days_ago = now - timedelta(days=5)
        db.execute(
            "INSERT INTO corrections (email_id, old_category, new_category, corrected_at, weight) "
            "VALUES (?, ?, ?, ?, ?)",
            ("e_old", "A", "B", five_days_ago.isoformat(), 1.0),
        )

        # Insert a correction dated now
        feedback_store.record_correction("e_new", "C", "D")

        # Filter to last 3 days — should only get the recent one
        corrections = feedback_store.get_corrections(days=3)
        assert len(corrections) == 1
        assert corrections[0].email_id == "e_new"

        # Filter to last 10 days — should get both
        corrections = feedback_store.get_corrections(days=10)
        assert len(corrections) == 2

    def test_get_corrections_filter_combined(self, feedback_store, db):
        """Test combining category and days filters."""
        now = datetime.now(timezone.utc)
        five_days_ago = now - timedelta(days=5)

        _insert_stub_emails(db, ["e_old", "e_new", "e_other"])

        # Old correction to Marketing
        db.execute(
            "INSERT INTO corrections (email_id, old_category, new_category, corrected_at, weight) "
            "VALUES (?, ?, ?, ?, ?)",
            ("e_old", "A", "Marketing", five_days_ago.isoformat(), 1.0),
        )

        # Recent correction to Marketing
        feedback_store.record_correction("e_new", "B", "Marketing")

        # Recent correction to Other
        feedback_store.record_correction("e_other", "C", "Other")

        # Category=Marketing, days=3 — should only get recent Marketing
        corrections = feedback_store.get_corrections(category="Marketing", days=3)
        assert len(corrections) == 1
        assert corrections[0].email_id == "e_new"

    def test_get_corrections_ordered_by_time(self, feedback_store, db):
        """Test that corrections are returned in chronological order (oldest first)."""
        now = datetime.now(timezone.utc)
        email_ids = [f"e_{i}" for i in range(5)]
        _insert_stub_emails(db, email_ids)

        for i in range(5):
            ts = now - timedelta(days=5 - i)
            db.execute(
                "INSERT INTO corrections "
                "(email_id, old_category, new_category, corrected_at, weight) "
                "VALUES (?, ?, ?, ?, ?)",
                (f"e_{i}", "A", "B", ts.isoformat(), 1.0),
            )

        corrections = feedback_store.get_corrections()
        assert len(corrections) == 5
        # Check chronological order
        for i in range(len(corrections) - 1):
            assert corrections[i].corrected_at <= corrections[i + 1].corrected_at


# =============================================================================
# get_weighted_corrections tests
# =============================================================================


class TestGetWeightedCorrections:
    """Test weighted corrections with temporal decay."""

    def test_weighted_corrections_empty_store(self, feedback_store):
        """Test that empty store returns empty list for weighted corrections."""
        weighted = feedback_store.get_weighted_corrections()
        assert weighted == []

    def test_weighted_correction_brand_new(self, feedback_store, db):
        """Test that a brand-new correction has weight ~1.0."""
        _insert_stub_email(db, "e1")
        feedback_store.record_correction("e1", "A", "B")

        weighted = feedback_store.get_weighted_corrections()
        assert len(weighted) == 1
        # A correction made just now should have weight very close to 1.0
        assert weighted[0].weight > 0.99

    def test_weighted_correction_70_day_old(self, feedback_store, db):
        """Test that a 70-day-old correction has ~50% weight (half-life)."""
        now = datetime.now(timezone.utc)
        seventy_days_ago = now - timedelta(days=70)

        _insert_stub_email(db, "e_old")
        db.execute(
            "INSERT INTO corrections (email_id, old_category, new_category, corrected_at, weight) "
            "VALUES (?, ?, ?, ?, ?)",
            ("e_old", "A", "B", seventy_days_ago.isoformat(), 1.0),
        )

        weighted = feedback_store.get_weighted_corrections()
        assert len(weighted) == 1

        # exp(-0.01 * 70) = exp(-0.7) ~ 0.4966
        expected_weight = math.exp(-0.01 * 70)
        assert abs(weighted[0].weight - expected_weight) < 0.02

    def test_weighted_correction_decay_formula(self, feedback_store, db):
        """Test the exact decay formula: weight = exp(-0.01 * days_old)."""
        now = datetime.now(timezone.utc)
        test_days = [0, 10, 30, 50, 100, 200]

        for days in test_days:
            email_id = f"e_{days}"
            _insert_stub_email(db, email_id)
            ts = now - timedelta(days=days)
            db.execute(
                "INSERT INTO corrections "
                "(email_id, old_category, new_category, corrected_at, weight) "
                "VALUES (?, ?, ?, ?, ?)",
                (email_id, "A", "B", ts.isoformat(), 1.0),
            )

        weighted = feedback_store.get_weighted_corrections(min_weight=0.0)
        assert len(weighted) == len(test_days)

        for wc in weighted:
            days_str = wc.email_id.replace("e_", "")
            days_old = int(days_str)
            expected = math.exp(-0.01 * days_old)
            # Allow 0.02 tolerance for time elapsed during test execution
            assert abs(wc.weight - expected) < 0.02, (
                f"For {days_old} days: expected ~{expected:.4f}, got {wc.weight:.4f}"
            )

    def test_weighted_corrections_min_weight_filter(self, feedback_store, db):
        """Test that min_weight filters out low-weight corrections."""
        now = datetime.now(timezone.utc)

        # Brand new correction (weight ~1.0)
        _insert_stub_email(db, "e_new")
        feedback_store.record_correction("e_new", "A", "B")

        # 300-day-old correction (weight = exp(-3.0) ~ 0.05)
        _insert_stub_email(db, "e_old")
        old_time = now - timedelta(days=300)
        db.execute(
            "INSERT INTO corrections (email_id, old_category, new_category, corrected_at, weight) "
            "VALUES (?, ?, ?, ?, ?)",
            ("e_old", "C", "D", old_time.isoformat(), 1.0),
        )

        # Default min_weight=0.1 should filter out the 300-day-old correction
        weighted = feedback_store.get_weighted_corrections(min_weight=0.1)
        assert len(weighted) == 1
        assert weighted[0].email_id == "e_new"

        # min_weight=0.0 should return both
        weighted_all = feedback_store.get_weighted_corrections(min_weight=0.0)
        assert len(weighted_all) == 2

    def test_weighted_corrections_sorted_by_weight_desc(self, feedback_store, db):
        """Test that weighted corrections are sorted by weight descending (newest first)."""
        now = datetime.now(timezone.utc)

        for i in [10, 50, 100, 1, 30]:
            email_id = f"e_{i}"
            _insert_stub_email(db, email_id)
            ts = now - timedelta(days=i)
            db.execute(
                "INSERT INTO corrections "
                "(email_id, old_category, new_category, corrected_at, weight) "
                "VALUES (?, ?, ?, ?, ?)",
                (email_id, "A", "B", ts.isoformat(), 1.0),
            )

        weighted = feedback_store.get_weighted_corrections(min_weight=0.0)
        # Should be sorted by weight descending
        for i in range(len(weighted) - 1):
            assert weighted[i].weight >= weighted[i + 1].weight


# =============================================================================
# get_correction_stats tests
# =============================================================================


class TestGetCorrectionStats:
    """Test correction statistics."""

    def test_stats_empty_store(self, feedback_store):
        """Test stats on empty store returns zero counts, no errors."""
        stats = feedback_store.get_correction_stats()
        assert stats["total_corrections"] == 0
        assert stats["per_category_counts"] == {}
        assert stats["correction_rate"] == 0.0

    def test_stats_total_corrections(self, feedback_store, db):
        """Test total correction count in stats."""
        _insert_stub_emails(db, ["e1", "e2", "e3"])
        feedback_store.record_correction("e1", "A", "B")
        feedback_store.record_correction("e2", "C", "D")
        feedback_store.record_correction("e3", "E", "F")

        stats = feedback_store.get_correction_stats()
        assert stats["total_corrections"] == 3

    def test_stats_per_category_counts(self, feedback_store, db):
        """Test per-category breakdown in stats."""
        _insert_stub_emails(db, ["e1", "e2", "e3", "e4"])
        feedback_store.record_correction("e1", "A", "Marketing")
        feedback_store.record_correction("e2", "B", "Marketing")
        feedback_store.record_correction("e3", "C", "Newsletters")
        feedback_store.record_correction("e4", "D", "Spam")

        stats = feedback_store.get_correction_stats()
        assert stats["per_category_counts"]["Marketing"] == 2
        assert stats["per_category_counts"]["Newsletters"] == 1
        assert stats["per_category_counts"]["Spam"] == 1

    def test_stats_correction_rate(self, feedback_store, db):
        """Test correction rate = corrections / total emails in database."""
        # Insert 10 emails
        for i in range(10):
            _insert_stub_email(db, f"e_{i}")

        # Add 3 corrections
        feedback_store.record_correction("e_0", "A", "B")
        feedback_store.record_correction("e_1", "C", "D")
        feedback_store.record_correction("e_2", "E", "F")

        stats = feedback_store.get_correction_stats()
        # correction_rate = 3 unique corrected / 10 total emails = 0.3
        assert abs(stats["correction_rate"] - 0.3) < 0.001

    def test_stats_correction_rate_no_emails(self, feedback_store, db):
        """Test correction rate is 0.0 when no emails exist in the emails table."""
        # No emails inserted, no corrections either
        stats = feedback_store.get_correction_stats()
        assert stats["correction_rate"] == 0.0

    def test_stats_includes_unique_email_count(self, feedback_store, db):
        """Test that stats counts unique emails with corrections."""
        _insert_stub_emails(db, ["e1", "e2"])
        feedback_store.record_correction("e1", "A", "B")
        feedback_store.record_correction("e1", "B", "C")  # same email re-corrected
        feedback_store.record_correction("e2", "D", "E")

        stats = feedback_store.get_correction_stats()
        assert stats["total_corrections"] == 3
        assert stats["unique_emails_corrected"] == 2

    def test_stats_correction_pairs(self, feedback_store, db):
        """Test correction pairs tracking (old -> new category transitions)."""
        _insert_stub_emails(db, ["e1", "e2", "e3"])
        feedback_store.record_correction("e1", "Newsletters", "Marketing")
        feedback_store.record_correction("e2", "Newsletters", "Marketing")
        feedback_store.record_correction("e3", "Social", "Notifications")

        stats = feedback_store.get_correction_stats()
        pairs = stats["correction_pairs"]
        assert pairs["Newsletters -> Marketing"] == 2
        assert pairs["Social -> Notifications"] == 1


# =============================================================================
# Edge cases
# =============================================================================


class TestFeedbackStoreEdgeCases:
    """Test edge cases and error handling."""

    def test_unicode_categories(self, feedback_store, db):
        """Test handling of Unicode category names."""
        _insert_stub_email(db, "email_001")
        feedback_store.record_correction("email_001", "Catégorie", "Réponses")

        corrections = feedback_store.get_corrections()
        assert len(corrections) == 1
        assert corrections[0].old_category == "Catégorie"
        assert corrections[0].new_category == "Réponses"

    def test_long_category_names(self, feedback_store, db):
        """Test handling of very long category names."""
        _insert_stub_email(db, "email_001")
        long_name = "A" * 1000
        feedback_store.record_correction("email_001", long_name, "Short")

        corrections = feedback_store.get_corrections()
        assert len(corrections) == 1
        assert corrections[0].old_category == long_name

    def test_special_characters_in_email_id(self, feedback_store, db):
        """Test handling of special characters in email IDs."""
        eid = "msg:123/456@example.com"
        _insert_stub_email(db, eid)
        feedback_store.record_correction(eid, "A", "B")

        corrections = feedback_store.get_corrections()
        assert len(corrections) == 1
        assert corrections[0].email_id == eid

    def test_persistence_across_store_instances(self, db):
        """Test that corrections persist across EmailFeedbackStore instances."""
        from src.learning.feedback_store import EmailFeedbackStore

        _insert_stub_email(db, "email_001")
        store1 = EmailFeedbackStore(database=db)
        store1.record_correction("email_001", "A", "B")

        store2 = EmailFeedbackStore(database=db)
        corrections = store2.get_corrections()
        assert len(corrections) == 1
        assert corrections[0].email_id == "email_001"

    def test_get_corrections_days_zero_returns_empty(self, feedback_store, db):
        """Test that days=0 returns no corrections."""
        _insert_stub_email(db, "e1")
        feedback_store.record_correction("e1", "A", "B")

        corrections = feedback_store.get_corrections(days=0)
        assert len(corrections) == 0
