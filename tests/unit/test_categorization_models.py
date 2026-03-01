"""
Unit tests for categorization data models (Phase 4, Item 4.1).

Tests CategoryAssignment, EmailCategorization, and CategorizationReport
Pydantic v2 models.
TDD: These tests are written first, implementation follows.
"""

import json
from datetime import datetime, timezone

import pytest

from src.models.categorization import (
    CategorizationReport,
    CategoryAssignment,
    EmailCategorization,
)

# =============================================================================
# CategoryAssignment Tests
# =============================================================================


class TestCategoryAssignment:
    """Test CategoryAssignment model."""

    def test_minimal_assignment(self):
        """Test creating an assignment with only required fields."""
        assignment = CategoryAssignment(
            category_name="Newsletters",
            confidence=0.85,
        )
        assert assignment.category_name == "Newsletters"
        assert assignment.confidence == 0.85
        assert assignment.source is None

    def test_assignment_with_rule_source(self):
        """Test assignment with a rule_id source."""
        assignment = CategoryAssignment(
            category_name="Newsletters",
            confidence=0.92,
            source="rule_newsletter_001",
        )
        assert assignment.source == "rule_newsletter_001"

    def test_assignment_with_manual_source(self):
        """Test assignment with manual source."""
        assignment = CategoryAssignment(
            category_name="Personal",
            confidence=1.0,
            source="manual",
        )
        assert assignment.source == "manual"

    def test_confidence_at_zero(self):
        """Test confidence at lower bound."""
        assignment = CategoryAssignment(
            category_name="Spam",
            confidence=0.0,
        )
        assert assignment.confidence == 0.0

    def test_confidence_at_one(self):
        """Test confidence at upper bound."""
        assignment = CategoryAssignment(
            category_name="Important",
            confidence=1.0,
        )
        assert assignment.confidence == 1.0

    def test_confidence_below_zero_rejected(self):
        """Test confidence below 0.0 is rejected."""
        with pytest.raises(ValueError):
            CategoryAssignment(
                category_name="Test",
                confidence=-0.1,
            )

    def test_confidence_above_one_rejected(self):
        """Test confidence above 1.0 is rejected."""
        with pytest.raises(ValueError):
            CategoryAssignment(
                category_name="Test",
                confidence=1.1,
            )

    def test_category_name_required_non_empty(self):
        """Test category_name must be non-empty."""
        with pytest.raises(ValueError):
            CategoryAssignment(
                category_name="",
                confidence=0.5,
            )

    def test_model_dump_roundtrip(self):
        """Test serialization and deserialization."""
        assignment = CategoryAssignment(
            category_name="Marketing",
            confidence=0.75,
            source="rule_mktg_001",
        )
        data = assignment.model_dump()
        restored = CategoryAssignment.model_validate(data)
        assert restored == assignment

    def test_model_dump_contains_all_fields(self):
        """Test model_dump includes all fields."""
        assignment = CategoryAssignment(
            category_name="Newsletters",
            confidence=0.9,
            source="rule_001",
        )
        data = assignment.model_dump()
        assert "category_name" in data
        assert "confidence" in data
        assert "source" in data
        assert data["category_name"] == "Newsletters"
        assert data["confidence"] == 0.9
        assert data["source"] == "rule_001"


# =============================================================================
# EmailCategorization Tests
# =============================================================================


class TestEmailCategorization:
    """Test EmailCategorization model."""

    def _make_primary(self) -> CategoryAssignment:
        """Create a standard primary category assignment."""
        return CategoryAssignment(
            category_name="Newsletters",
            confidence=0.92,
            source="rule_newsletter_001",
        )

    def _make_secondary(self) -> list[CategoryAssignment]:
        """Create standard secondary category assignments."""
        return [
            CategoryAssignment(
                category_name="Marketing",
                confidence=0.45,
                source="rule_mktg_001",
            ),
            CategoryAssignment(
                category_name="Promotions",
                confidence=0.30,
                source="rule_promo_001",
            ),
        ]

    def test_minimal_categorization(self):
        """Test creating a categorization with only required fields."""
        cat = EmailCategorization(
            email_id="msg_abc123",
            primary_category=self._make_primary(),
        )
        assert cat.email_id == "msg_abc123"
        assert cat.primary_category.category_name == "Newsletters"
        assert cat.primary_category.confidence == 0.92
        assert cat.secondary_categories == []
        assert cat.matched_rules == []
        assert cat.categorized_at is not None

    def test_email_id_required_non_empty(self):
        """Test email_id must be non-empty."""
        with pytest.raises(ValueError):
            EmailCategorization(
                email_id="",
                primary_category=self._make_primary(),
            )

    def test_with_secondary_categories(self):
        """Test categorization with secondary categories."""
        cat = EmailCategorization(
            email_id="msg_abc123",
            primary_category=self._make_primary(),
            secondary_categories=self._make_secondary(),
        )
        assert len(cat.secondary_categories) == 2
        assert cat.secondary_categories[0].category_name == "Marketing"
        assert cat.secondary_categories[1].category_name == "Promotions"

    def test_with_matched_rules(self):
        """Test categorization with matched rule IDs."""
        cat = EmailCategorization(
            email_id="msg_abc123",
            primary_category=self._make_primary(),
            matched_rules=["rule_newsletter_001", "rule_mktg_001"],
        )
        assert len(cat.matched_rules) == 2
        assert "rule_newsletter_001" in cat.matched_rules
        assert "rule_mktg_001" in cat.matched_rules

    def test_categorized_at_auto_set(self):
        """Test categorized_at is auto-populated with UTC timestamp."""
        cat = EmailCategorization(
            email_id="msg_abc123",
            primary_category=self._make_primary(),
        )
        assert cat.categorized_at is not None
        assert isinstance(cat.categorized_at, datetime)

    def test_categorized_at_can_be_explicit(self):
        """Test categorized_at can be explicitly set."""
        fixed_date = datetime(2026, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        cat = EmailCategorization(
            email_id="msg_abc123",
            primary_category=self._make_primary(),
            categorized_at=fixed_date,
        )
        assert cat.categorized_at == fixed_date

    def test_model_dump_roundtrip(self):
        """Test full serialization and deserialization."""
        cat = EmailCategorization(
            email_id="msg_abc123",
            primary_category=self._make_primary(),
            secondary_categories=self._make_secondary(),
            matched_rules=["rule_newsletter_001", "rule_mktg_001"],
        )
        data = cat.model_dump()
        restored = EmailCategorization.model_validate(data)
        assert restored.email_id == cat.email_id
        assert restored.primary_category.category_name == cat.primary_category.category_name
        assert restored.primary_category.confidence == cat.primary_category.confidence
        assert len(restored.secondary_categories) == len(cat.secondary_categories)
        assert len(restored.matched_rules) == len(cat.matched_rules)

    def test_model_dump_json_serializable(self):
        """Test model_dump produces JSON-serializable output."""
        cat = EmailCategorization(
            email_id="msg_abc123",
            primary_category=self._make_primary(),
            secondary_categories=self._make_secondary(),
            matched_rules=["rule_001"],
        )
        data = cat.model_dump(mode="json")
        json_str = json.dumps(data)
        assert isinstance(json_str, str)

    def test_is_uncategorized_false_when_has_primary(self):
        """Test is_uncategorized returns False when primary category exists."""
        cat = EmailCategorization(
            email_id="msg_abc123",
            primary_category=self._make_primary(),
        )
        assert cat.is_uncategorized is False

    def test_has_multiple_categories_without_secondary(self):
        """Test has_multiple_categories is False with no secondaries."""
        cat = EmailCategorization(
            email_id="msg_abc123",
            primary_category=self._make_primary(),
        )
        assert cat.has_multiple_categories is False

    def test_has_multiple_categories_with_secondary(self):
        """Test has_multiple_categories is True with secondaries."""
        cat = EmailCategorization(
            email_id="msg_abc123",
            primary_category=self._make_primary(),
            secondary_categories=self._make_secondary(),
        )
        assert cat.has_multiple_categories is True

    def test_all_categories_returns_primary_and_secondary(self):
        """Test all_categories returns primary followed by secondaries."""
        primary = self._make_primary()
        secondaries = self._make_secondary()
        cat = EmailCategorization(
            email_id="msg_abc123",
            primary_category=primary,
            secondary_categories=secondaries,
        )
        all_cats = cat.all_categories
        assert len(all_cats) == 3
        assert all_cats[0].category_name == "Newsletters"
        assert all_cats[1].category_name == "Marketing"
        assert all_cats[2].category_name == "Promotions"

    def test_all_categories_primary_only(self):
        """Test all_categories with only primary category."""
        cat = EmailCategorization(
            email_id="msg_abc123",
            primary_category=self._make_primary(),
        )
        all_cats = cat.all_categories
        assert len(all_cats) == 1
        assert all_cats[0].category_name == "Newsletters"


# =============================================================================
# EmailCategorization for Uncategorized Emails
# =============================================================================


class TestUncategorizedEmail:
    """Test EmailCategorization for uncategorized emails."""

    def test_uncategorized_email_factory(self):
        """Test creating an uncategorized email via class method."""
        cat = EmailCategorization.uncategorized(email_id="msg_no_match")
        assert cat.email_id == "msg_no_match"
        assert cat.is_uncategorized is True
        assert cat.primary_category.category_name == "Uncategorized"
        assert cat.primary_category.confidence == 0.0
        assert cat.primary_category.source is None
        assert cat.secondary_categories == []
        assert cat.matched_rules == []

    def test_uncategorized_has_no_multiple_categories(self):
        """Test uncategorized email has no multiple categories."""
        cat = EmailCategorization.uncategorized(email_id="msg_no_match")
        assert cat.has_multiple_categories is False


# =============================================================================
# CategorizationReport Tests
# =============================================================================


class TestCategorizationReport:
    """Test CategorizationReport model."""

    def _make_categorization(
        self,
        email_id: str,
        category_name: str = "Newsletters",
        confidence: float = 0.9,
    ) -> EmailCategorization:
        """Create a test EmailCategorization."""
        return EmailCategorization(
            email_id=email_id,
            primary_category=CategoryAssignment(
                category_name=category_name,
                confidence=confidence,
                source="rule_001",
            ),
        )

    def _make_uncategorized(self, email_id: str) -> EmailCategorization:
        """Create an uncategorized EmailCategorization."""
        return EmailCategorization.uncategorized(email_id=email_id)

    def test_minimal_report(self):
        """Test creating a report with only required fields."""
        report = CategorizationReport(
            total_emails=100,
            categorized_count=85,
            uncategorized_count=15,
            coverage_percentage=85.0,
            categories_used={"Newsletters": 50, "Marketing": 35},
            categorizations=[],
        )
        assert report.total_emails == 100
        assert report.categorized_count == 85
        assert report.uncategorized_count == 15
        assert report.coverage_percentage == 85.0
        assert report.categories_used == {"Newsletters": 50, "Marketing": 35}
        assert report.categorizations == []
        assert report.created_at is not None
        assert report.rule_set_version is None

    def test_with_rule_set_version(self):
        """Test report with rule_set_version."""
        report = CategorizationReport(
            total_emails=100,
            categorized_count=100,
            uncategorized_count=0,
            coverage_percentage=100.0,
            categories_used={"All": 100},
            categorizations=[],
            rule_set_version="1.0",
        )
        assert report.rule_set_version == "1.0"

    def test_with_categorizations(self):
        """Test report with actual categorizations."""
        cats = [
            self._make_categorization("msg_1", "Newsletters"),
            self._make_categorization("msg_2", "Marketing"),
            self._make_uncategorized("msg_3"),
        ]
        report = CategorizationReport(
            total_emails=3,
            categorized_count=2,
            uncategorized_count=1,
            coverage_percentage=66.67,
            categories_used={"Newsletters": 1, "Marketing": 1},
            categorizations=cats,
        )
        assert len(report.categorizations) == 3

    def test_created_at_auto_set(self):
        """Test created_at is auto-populated."""
        report = CategorizationReport(
            total_emails=0,
            categorized_count=0,
            uncategorized_count=0,
            coverage_percentage=0.0,
            categories_used={},
            categorizations=[],
        )
        assert report.created_at is not None
        assert isinstance(report.created_at, datetime)

    def test_created_at_can_be_explicit(self):
        """Test created_at can be explicitly set."""
        fixed_date = datetime(2026, 2, 1, 8, 0, 0, tzinfo=timezone.utc)
        report = CategorizationReport(
            total_emails=0,
            categorized_count=0,
            uncategorized_count=0,
            coverage_percentage=0.0,
            categories_used={},
            categorizations=[],
            created_at=fixed_date,
        )
        assert report.created_at == fixed_date

    def test_total_emails_non_negative(self):
        """Test total_emails must be >= 0."""
        with pytest.raises(ValueError):
            CategorizationReport(
                total_emails=-1,
                categorized_count=0,
                uncategorized_count=0,
                coverage_percentage=0.0,
                categories_used={},
                categorizations=[],
            )

    def test_categorized_count_non_negative(self):
        """Test categorized_count must be >= 0."""
        with pytest.raises(ValueError):
            CategorizationReport(
                total_emails=10,
                categorized_count=-1,
                uncategorized_count=11,
                coverage_percentage=0.0,
                categories_used={},
                categorizations=[],
            )

    def test_uncategorized_count_non_negative(self):
        """Test uncategorized_count must be >= 0."""
        with pytest.raises(ValueError):
            CategorizationReport(
                total_emails=10,
                categorized_count=11,
                uncategorized_count=-1,
                coverage_percentage=0.0,
                categories_used={},
                categorizations=[],
            )

    def test_coverage_percentage_bounds(self):
        """Test coverage_percentage must be 0-100."""
        # Valid at boundaries
        report_zero = CategorizationReport(
            total_emails=10,
            categorized_count=0,
            uncategorized_count=10,
            coverage_percentage=0.0,
            categories_used={},
            categorizations=[],
        )
        assert report_zero.coverage_percentage == 0.0

        report_full = CategorizationReport(
            total_emails=10,
            categorized_count=10,
            uncategorized_count=0,
            coverage_percentage=100.0,
            categories_used={"All": 10},
            categorizations=[],
        )
        assert report_full.coverage_percentage == 100.0

    def test_coverage_percentage_below_zero_rejected(self):
        """Test coverage_percentage below 0 is rejected."""
        with pytest.raises(ValueError):
            CategorizationReport(
                total_emails=10,
                categorized_count=0,
                uncategorized_count=10,
                coverage_percentage=-1.0,
                categories_used={},
                categorizations=[],
            )

    def test_coverage_percentage_above_100_rejected(self):
        """Test coverage_percentage above 100 is rejected."""
        with pytest.raises(ValueError):
            CategorizationReport(
                total_emails=10,
                categorized_count=10,
                uncategorized_count=0,
                coverage_percentage=100.1,
                categories_used={"All": 10},
                categorizations=[],
            )

    def test_model_dump_roundtrip(self):
        """Test full serialization and deserialization."""
        cats = [
            self._make_categorization("msg_1", "Newsletters"),
            self._make_categorization("msg_2", "Marketing"),
        ]
        report = CategorizationReport(
            total_emails=100,
            categorized_count=85,
            uncategorized_count=15,
            coverage_percentage=85.0,
            categories_used={"Newsletters": 50, "Marketing": 35},
            categorizations=cats,
            rule_set_version="1.2",
        )
        data = report.model_dump()
        restored = CategorizationReport.model_validate(data)
        assert restored.total_emails == report.total_emails
        assert restored.categorized_count == report.categorized_count
        assert restored.uncategorized_count == report.uncategorized_count
        assert restored.coverage_percentage == report.coverage_percentage
        assert restored.categories_used == report.categories_used
        assert len(restored.categorizations) == len(report.categorizations)
        assert restored.rule_set_version == report.rule_set_version

    def test_model_dump_json_serializable(self):
        """Test model_dump produces JSON-serializable output."""
        cats = [self._make_categorization("msg_1")]
        report = CategorizationReport(
            total_emails=10,
            categorized_count=8,
            uncategorized_count=2,
            coverage_percentage=80.0,
            categories_used={"Newsletters": 8},
            categorizations=cats,
            rule_set_version="1.0",
        )
        data = report.model_dump(mode="json")
        json_str = json.dumps(data)
        assert isinstance(json_str, str)

    def test_category_count_property(self):
        """Test category_count returns number of unique categories used."""
        report = CategorizationReport(
            total_emails=100,
            categorized_count=80,
            uncategorized_count=20,
            coverage_percentage=80.0,
            categories_used={"Newsletters": 40, "Marketing": 25, "Social": 15},
            categorizations=[],
        )
        assert report.category_count == 3

    def test_category_count_empty(self):
        """Test category_count with no categories."""
        report = CategorizationReport(
            total_emails=10,
            categorized_count=0,
            uncategorized_count=10,
            coverage_percentage=0.0,
            categories_used={},
            categorizations=[],
        )
        assert report.category_count == 0

    def test_multi_category_count_property(self):
        """Test multi_category_count returns count of emails with multiple categories."""
        primary = CategoryAssignment(category_name="Newsletters", confidence=0.9, source="rule_001")
        secondary = CategoryAssignment(category_name="Marketing", confidence=0.5, source="rule_002")
        cats = [
            EmailCategorization(
                email_id="msg_1",
                primary_category=primary,
                secondary_categories=[secondary],
            ),
            EmailCategorization(
                email_id="msg_2",
                primary_category=primary,
            ),
            EmailCategorization(
                email_id="msg_3",
                primary_category=primary,
                secondary_categories=[secondary],
            ),
        ]
        report = CategorizationReport(
            total_emails=3,
            categorized_count=3,
            uncategorized_count=0,
            coverage_percentage=100.0,
            categories_used={"Newsletters": 3, "Marketing": 2},
            categorizations=cats,
        )
        assert report.multi_category_count == 2


# =============================================================================
# CategorizationReport Validation Tests
# =============================================================================


class TestCategorizationReportValidation:
    """Test CategorizationReport cross-field validation."""

    def test_counts_must_sum_to_total(self):
        """Test categorized + uncategorized must equal total_emails."""
        with pytest.raises(ValueError, match="must equal total_emails"):
            CategorizationReport(
                total_emails=100,
                categorized_count=80,
                uncategorized_count=10,  # 80 + 10 != 100
                coverage_percentage=80.0,
                categories_used={"Test": 80},
                categorizations=[],
            )

    def test_counts_sum_correctly(self):
        """Test report passes validation when counts sum correctly."""
        report = CategorizationReport(
            total_emails=100,
            categorized_count=80,
            uncategorized_count=20,
            coverage_percentage=80.0,
            categories_used={"Test": 80},
            categorizations=[],
        )
        assert report.categorized_count + report.uncategorized_count == report.total_emails

    def test_zero_total_valid(self):
        """Test zero total emails is valid."""
        report = CategorizationReport(
            total_emails=0,
            categorized_count=0,
            uncategorized_count=0,
            coverage_percentage=0.0,
            categories_used={},
            categorizations=[],
        )
        assert report.total_emails == 0


# =============================================================================
# Cross-model Integration Tests
# =============================================================================


class TestCategorizationModelIntegration:
    """Integration tests across categorization models."""

    def test_full_categorization_workflow(self):
        """Test creating a full categorization from assignments through report."""
        # Create categorizations for several emails
        categorizations = []
        for i in range(5):
            cat = EmailCategorization(
                email_id=f"msg_{i:03d}",
                primary_category=CategoryAssignment(
                    category_name="Newsletters",
                    confidence=0.85 + i * 0.02,
                    source="rule_nl_001",
                ),
                matched_rules=["rule_nl_001"],
            )
            categorizations.append(cat)

        # Add some uncategorized
        for i in range(5, 7):
            categorizations.append(EmailCategorization.uncategorized(email_id=f"msg_{i:03d}"))

        # Build report
        report = CategorizationReport(
            total_emails=7,
            categorized_count=5,
            uncategorized_count=2,
            coverage_percentage=71.43,
            categories_used={"Newsletters": 5},
            categorizations=categorizations,
            rule_set_version="1.0",
        )

        assert report.total_emails == 7
        assert report.category_count == 1
        assert len(report.categorizations) == 7
        assert report.rule_set_version == "1.0"

    def test_multi_category_email_in_report(self):
        """Test email with multiple category assignments in a report."""
        primary = CategoryAssignment(
            category_name="Work Updates",
            confidence=0.88,
            source="rule_work_001",
        )
        secondaries = [
            CategoryAssignment(
                category_name="Project Alpha",
                confidence=0.65,
                source="rule_alpha_001",
            ),
            CategoryAssignment(
                category_name="Weekly Reports",
                confidence=0.42,
                source="rule_weekly_001",
            ),
        ]
        cat = EmailCategorization(
            email_id="msg_multi",
            primary_category=primary,
            secondary_categories=secondaries,
            matched_rules=["rule_work_001", "rule_alpha_001", "rule_weekly_001"],
        )

        assert cat.has_multiple_categories is True
        assert len(cat.all_categories) == 3
        assert cat.primary_category.confidence > cat.secondary_categories[0].confidence
        assert cat.secondary_categories[0].confidence > cat.secondary_categories[1].confidence

    def test_report_json_full_roundtrip(self):
        """Test full JSON serialization roundtrip of a complete report."""
        cats = [
            EmailCategorization(
                email_id="msg_001",
                primary_category=CategoryAssignment(
                    category_name="Newsletters",
                    confidence=0.95,
                    source="rule_001",
                ),
                secondary_categories=[
                    CategoryAssignment(
                        category_name="Marketing",
                        confidence=0.40,
                        source="rule_002",
                    ),
                ],
                matched_rules=["rule_001", "rule_002"],
            ),
            EmailCategorization.uncategorized(email_id="msg_002"),
        ]
        report = CategorizationReport(
            total_emails=2,
            categorized_count=1,
            uncategorized_count=1,
            coverage_percentage=50.0,
            categories_used={"Newsletters": 1},
            categorizations=cats,
            rule_set_version="1.0",
        )

        # Serialize to JSON string
        json_data = report.model_dump(mode="json")
        json_str = json.dumps(json_data, indent=2)

        # Deserialize from JSON string
        parsed = json.loads(json_str)
        restored = CategorizationReport.model_validate(parsed)

        assert restored.total_emails == 2
        assert restored.categorized_count == 1
        assert len(restored.categorizations) == 2
        assert restored.categorizations[0].primary_category.category_name == "Newsletters"
        assert restored.categorizations[1].is_uncategorized is True
        assert restored.rule_set_version == "1.0"
