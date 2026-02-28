"""
Unit tests for data models.

Tests the Category model, hierarchical extensions, and Email model.
"""

from datetime import datetime

import pytest

from src.models.category import Category, CategorySource
from src.models.email import Email

# -----------------------------------------------------------------------------
# Test Fixtures - Sample Data Builders
# -----------------------------------------------------------------------------


def create_test_category(
    category_id: str = "test_cat_1",
    name: str = "Test Category",
    description: str = "A test category",
    confidence: float = 0.85,
    email_count: int = 100,
    percentage: float = 10.0,
    source: CategorySource = CategorySource.CONTENT_CLUSTER,
    parent_category_id: str | None = None,
    level: int = 0,
    subcategories: list | None = None,
) -> Category:
    """Create a test Category object."""
    return Category(
        category_id=category_id,
        category_name=name,
        description=description,
        confidence=confidence,
        email_count=email_count,
        percentage=percentage,
        source=source,
        parent_category_id=parent_category_id,
        level=level,
        subcategories=subcategories or [],
    )


# -----------------------------------------------------------------------------
# Category Model Base Tests
# -----------------------------------------------------------------------------


class TestCategoryModel:
    """Test cases for the base Category model."""

    def test_category_required_fields(self):
        """Test that Category requires essential fields."""
        category = Category(
            category_id="cat_1",
            category_name="Test",
            description="Test category",
            confidence=0.8,
            source=CategorySource.CONTENT_CLUSTER,
        )

        assert category.category_id == "cat_1"
        assert category.category_name == "Test"
        assert category.confidence == 0.8

    def test_category_id_validation(self):
        """Test that category_id must be non-empty."""
        with pytest.raises(ValueError):
            Category(
                category_id="",
                category_name="Test",
                description="Test",
                confidence=0.5,
                source=CategorySource.TEMPLATE,
            )

    def test_category_name_validation(self):
        """Test that category_name must be non-empty."""
        with pytest.raises(ValueError):
            Category(
                category_id="cat_1",
                category_name="",
                description="Test",
                confidence=0.5,
                source=CategorySource.TEMPLATE,
            )

    def test_confidence_range_validation(self):
        """Test that confidence must be between 0 and 1."""
        with pytest.raises(ValueError):
            Category(
                category_id="cat_1",
                category_name="Test",
                description="Test",
                confidence=1.5,  # Invalid: > 1
                source=CategorySource.TEMPLATE,
            )

        with pytest.raises(ValueError):
            Category(
                category_id="cat_2",
                category_name="Test",
                description="Test",
                confidence=-0.1,  # Invalid: < 0
                source=CategorySource.TEMPLATE,
            )

    def test_category_optional_fields_defaults(self):
        """Test that optional fields have correct defaults."""
        category = Category(
            category_id="cat_1",
            category_name="Test",
            description="Test",
            confidence=0.5,
            source=CategorySource.CUSTOM,
        )

        assert category.email_count is None
        assert category.percentage is None
        assert category.source_id is None
        assert category.user_modified is False
        assert category.distinguishing_features == []
        assert category.example_email_ids == []


# -----------------------------------------------------------------------------
# Hierarchical Category Model Tests (Task 4A.1)
# -----------------------------------------------------------------------------


class TestCategoryHierarchicalFields:
    """Test cases for hierarchical Category fields (Task 4A.1)."""

    def test_parent_category_id_default_none(self):
        """Test that parent_category_id defaults to None."""
        category = create_test_category()

        assert category.parent_category_id is None

    def test_parent_category_id_can_be_set(self):
        """Test that parent_category_id can be set to a valid ID."""
        category = create_test_category(parent_category_id="parent_cat_1")

        assert category.parent_category_id == "parent_cat_1"

    def test_level_default_zero(self):
        """Test that level defaults to 0 (top-level category)."""
        category = create_test_category()

        assert category.level == 0

    def test_level_can_be_set(self):
        """Test that level can be set to different values."""
        category_level_0 = create_test_category(level=0)
        category_level_1 = create_test_category(level=1)
        category_level_2 = create_test_category(level=2)

        assert category_level_0.level == 0
        assert category_level_1.level == 1
        assert category_level_2.level == 2

    def test_level_validation_non_negative(self):
        """Test that level must be non-negative."""
        with pytest.raises(ValueError):
            create_test_category(level=-1)

    def test_subcategories_default_empty_list(self):
        """Test that subcategories defaults to empty list."""
        category = create_test_category()

        assert category.subcategories == []
        assert isinstance(category.subcategories, list)

    def test_subcategories_can_contain_categories(self):
        """Test that subcategories can contain Category objects."""
        child1 = create_test_category(category_id="child_1", name="Child 1", level=1)
        child2 = create_test_category(category_id="child_2", name="Child 2", level=1)

        parent = create_test_category(
            category_id="parent_1",
            name="Parent",
            level=0,
            subcategories=[child1, child2],
        )

        assert len(parent.subcategories) == 2
        assert parent.subcategories[0].category_name == "Child 1"
        assert parent.subcategories[1].category_name == "Child 2"

    def test_nested_hierarchy_three_levels(self):
        """Test that categories can have nested subcategories."""
        grandchild = create_test_category(
            category_id="grandchild_1",
            name="Grandchild",
            level=2,
            parent_category_id="child_1",
        )
        child = create_test_category(
            category_id="child_1",
            name="Child",
            level=1,
            parent_category_id="parent_1",
            subcategories=[grandchild],
        )
        parent = create_test_category(
            category_id="parent_1",
            name="Parent",
            level=0,
            subcategories=[child],
        )

        assert parent.level == 0
        assert parent.subcategories[0].level == 1
        assert parent.subcategories[0].subcategories[0].level == 2

    def test_backward_compatibility_existing_categories_work(self):
        """Test that existing category creation still works (backward compatible)."""
        # Create category without any new hierarchical fields
        category = Category(
            category_id="cat_1",
            category_name="Legacy Category",
            description="Created without new fields",
            confidence=0.75,
            email_count=50,
            percentage=5.0,
            source=CategorySource.SENDER,
            source_id="sender@example.com",
            user_modified=False,
            distinguishing_features=["feature1", "feature2"],
            example_email_ids=["email_1", "email_2"],
        )

        # Should work and have defaults for new fields
        assert category.parent_category_id is None
        assert category.level == 0
        assert category.subcategories == []

    def test_hierarchical_fields_in_model_dump(self):
        """Test that hierarchical fields are included in model_dump output."""
        child = create_test_category(
            category_id="child_1",
            name="Child",
            level=1,
            parent_category_id="parent_1",
        )
        parent = create_test_category(
            category_id="parent_1",
            name="Parent",
            level=0,
            subcategories=[child],
        )

        parent_dict = parent.model_dump()

        assert "parent_category_id" in parent_dict
        assert "level" in parent_dict
        assert "subcategories" in parent_dict
        assert parent_dict["level"] == 0
        assert len(parent_dict["subcategories"]) == 1
        assert parent_dict["subcategories"][0]["level"] == 1

    def test_hierarchical_category_from_dict(self):
        """Test that Category can be recreated from dict with hierarchy."""
        parent_dict = {
            "category_id": "parent_1",
            "category_name": "Parent",
            "description": "Parent category",
            "confidence": 0.9,
            "source": "content_cluster",
            "level": 0,
            "parent_category_id": None,
            "subcategories": [
                {
                    "category_id": "child_1",
                    "category_name": "Child",
                    "description": "Child category",
                    "confidence": 0.85,
                    "source": "content_cluster",
                    "level": 1,
                    "parent_category_id": "parent_1",
                    "subcategories": [],
                }
            ],
        }

        category = Category(**parent_dict)

        assert category.category_id == "parent_1"
        assert len(category.subcategories) == 1
        assert category.subcategories[0].category_id == "child_1"
        assert category.subcategories[0].parent_category_id == "parent_1"


class TestCategoryHierarchyHelpers:
    """Test cases for Category hierarchy helper properties."""

    def test_is_top_level_property(self):
        """Test is_top_level returns True for level 0 categories."""
        top_level = create_test_category(level=0)
        sub_level = create_test_category(level=1)

        assert top_level.is_top_level is True
        assert sub_level.is_top_level is False

    def test_has_children_property(self):
        """Test has_children returns True when subcategories exist."""
        child = create_test_category(category_id="child")
        parent = create_test_category(subcategories=[child])
        leaf = create_test_category()

        assert parent.has_children is True
        assert leaf.has_children is False

    def test_children_count_property(self):
        """Test children_count returns correct count."""
        child1 = create_test_category(category_id="child_1")
        child2 = create_test_category(category_id="child_2")
        parent = create_test_category(subcategories=[child1, child2])
        leaf = create_test_category()

        assert parent.children_count == 2
        assert leaf.children_count == 0


class TestCategorySourceEnum:
    """Test cases for CategorySource enum."""

    def test_category_source_values(self):
        """Test all CategorySource enum values exist."""
        assert CategorySource.CONTENT_CLUSTER.value == "content_cluster"
        assert CategorySource.SENDER.value == "sender"
        assert CategorySource.TEMPLATE.value == "template"
        assert CategorySource.CUSTOM.value == "custom"

    def test_category_source_string_conversion(self):
        """Test CategorySource can be created from string."""
        category = Category(
            category_id="cat_1",
            category_name="Test",
            description="Test",
            confidence=0.5,
            source="content_cluster",  # String value
        )

        assert category.source == CategorySource.CONTENT_CLUSTER


# -----------------------------------------------------------------------------
# Email Model Tests - combined_text
# -----------------------------------------------------------------------------


def _make_email(subject: str = "Test Subject", body_text: str = "Test body") -> Email:
    """Helper to create an Email for combined_text tests."""
    return Email(
        id="test_1",
        sender_email="sender@example.com",
        sender_name="Sender",
        sender_domain="example.com",
        subject=subject,
        body_text=body_text,
        received_date=datetime(2024, 1, 15, 10, 0),
        has_attachments=False,
    )


class TestEmailLenientValidation:
    """Test cases for lenient email address validation (Phase 6, Task 6.1)."""

    def test_accepts_standard_email(self):
        """Test that standard email addresses still work."""
        email = _make_email()
        assert email.sender_email == "sender@example.com"

    def test_accepts_underscore_in_domain(self):
        """Test that underscores in domain parts are accepted."""
        email = Email(
            id="t1",
            sender_email="noreply@39._ecoenergi.online",
            sender_name="",
            sender_domain="39._ecoenergi.online",
            subject="Test",
            body_text="",
            received_date=datetime(2024, 1, 1),
            has_attachments=False,
        )
        assert email.sender_email == "noreply@39._ecoenergi.online"

    def test_accepts_hyphens_and_dots_in_domain(self):
        """Test that leading hyphens and consecutive dots in domain are accepted."""
        email = Email(
            id="t2",
            sender_email="CloudNotify@---SyncServi...-MtO0.autoworkscoll.com",
            sender_name="",
            sender_domain="---SyncServi...-MtO0.autoworkscoll.com",
            subject="Test",
            body_text="",
            received_date=datetime(2024, 1, 1),
            has_attachments=False,
        )
        assert email.sender_email == "CloudNotify@---SyncServi...-MtO0.autoworkscoll.com"

    def test_rejects_empty_sender_email(self):
        """Test that empty sender_email is rejected."""
        with pytest.raises(ValueError):
            Email(
                id="t3",
                sender_email="",
                sender_name="",
                sender_domain="example.com",
                subject="Test",
                body_text="",
                received_date=datetime(2024, 1, 1),
                has_attachments=False,
            )

    def test_rejects_no_at_sign(self):
        """Test that email without @ is rejected."""
        with pytest.raises(ValueError):
            Email(
                id="t4",
                sender_email="invalid-email-format",
                sender_name="",
                sender_domain="example.com",
                subject="Test",
                body_text="",
                received_date=datetime(2024, 1, 1),
                has_attachments=False,
            )

    def test_recipient_email_none_accepted(self):
        """Test that None recipient_email is accepted."""
        email = _make_email()
        assert email.recipient_email is None

    def test_recipient_email_with_at_accepted(self):
        """Test that recipient_email with @ is accepted."""
        email = Email(
            id="t5",
            sender_email="sender@example.com",
            sender_name="",
            sender_domain="example.com",
            recipient_email="recipient@weird._domain.com",
            subject="Test",
            body_text="",
            received_date=datetime(2024, 1, 1),
            has_attachments=False,
        )
        assert email.recipient_email == "recipient@weird._domain.com"

    def test_strips_whitespace(self):
        """Test that whitespace is stripped from email addresses."""
        email = Email(
            id="t6",
            sender_email="  sender@example.com  ",
            sender_name="",
            sender_domain="example.com",
            subject="Test",
            body_text="",
            received_date=datetime(2024, 1, 1),
            has_attachments=False,
        )
        assert email.sender_email == "sender@example.com"


class TestEmailCombinedText:
    """Test cases for Email.combined_text and combined_text_with_limit."""

    def test_combined_text_default_returns_subject_plus_body(self):
        """Test combined_text property returns subject + body."""
        email = _make_email(subject="Hello", body_text="World")
        assert email.combined_text == "Hello World"

    def test_combined_text_default_truncates_body_at_1500(self):
        """Test combined_text property truncates body at 1500 chars."""
        long_body = "x" * 2000
        email = _make_email(subject="Subj", body_text=long_body)
        result = email.combined_text
        # "Subj " + 1500 x's = 1505 chars total
        assert len(result) == 5 + 1500

    def test_combined_text_short_body_not_truncated(self):
        """Test combined_text does not truncate short body."""
        email = _make_email(subject="Subj", body_text="Short body")
        assert email.combined_text == "Subj Short body"

    def test_combined_text_with_limit_custom_length(self):
        """Test combined_text_with_limit respects custom max_body_length."""
        long_body = "a" * 3000
        email = _make_email(subject="S", body_text=long_body)

        result_500 = email.combined_text_with_limit(500)
        assert len(result_500) == 2 + 500  # "S " + 500 a's

        result_2000 = email.combined_text_with_limit(2000)
        assert len(result_2000) == 2 + 2000  # "S " + 2000 a's

    def test_combined_text_with_limit_default_matches_property(self):
        """Test combined_text_with_limit(1500) matches combined_text property."""
        long_body = "b" * 2000
        email = _make_email(subject="Test", body_text=long_body)
        assert email.combined_text == email.combined_text_with_limit(1500)

    def test_combined_text_with_limit_200(self):
        """Test minimum config boundary of 200 chars."""
        long_body = "c" * 500
        email = _make_email(subject="X", body_text=long_body)
        result = email.combined_text_with_limit(200)
        assert len(result) == 2 + 200  # "X " + 200 c's

    def test_combined_text_with_limit_5000(self):
        """Test maximum config boundary of 5000 chars."""
        long_body = "d" * 6000
        email = _make_email(subject="Y", body_text=long_body)
        result = email.combined_text_with_limit(5000)
        assert len(result) == 2 + 5000  # "Y " + 5000 d's

    def test_combined_text_empty_body(self):
        """Test combined_text with empty body."""
        email = _make_email(subject="Only Subject", body_text="")
        assert email.combined_text == "Only Subject "

    def test_combined_text_empty_subject(self):
        """Test combined_text with empty subject."""
        email = _make_email(subject="", body_text="Only body")
        assert email.combined_text == " Only body"
