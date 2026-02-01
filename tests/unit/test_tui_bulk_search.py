"""
Unit tests for Track 8B: TUI Bulk Operations and Search/Filter.

Tests the TUI enhancements including:
- Multi-select with Space toggle
- Bulk actions (Shift+A accept all, Shift+D delete all)
- Search/filter functionality
- Pattern-based selection

Uses TDD approach - tests written first before implementation.
"""
import pytest

from src.models.category import Category, CategorySource


# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def sample_categories() -> list[Category]:
    """Create sample categories for testing."""
    return [
        Category(
            category_id="cat_001",
            category_name="Financial Alerts",
            description="Bank and payment notifications",
            confidence=0.85,
            email_count=150,
            source=CategorySource.TEMPLATE,
        ),
        Category(
            category_id="cat_002",
            category_name="Shopping Orders",
            description="E-commerce order updates",
            confidence=0.72,
            email_count=89,
            source=CategorySource.CONTENT_CLUSTER,
        ),
        Category(
            category_id="cat_003",
            category_name="Newsletter Weekly",
            description="Weekly newsletters",
            confidence=0.65,
            email_count=45,
            source=CategorySource.SENDER,
        ),
        Category(
            category_id="cat_004",
            category_name="Social Updates",
            description="Social media notifications",
            confidence=0.90,
            email_count=200,
            source=CategorySource.CONTENT_CLUSTER,
        ),
        Category(
            category_id="cat_005",
            category_name="System Alerts",
            description="System notifications",
            confidence=0.55,
            email_count=30,
            source=CategorySource.TEMPLATE,
        ),
    ]


# ============================================================================
# Track 8B.1: Bulk Operations Tests
# ============================================================================


class TestCategoryTableSelection:
    """Test multi-select functionality in CategoryTable."""

    def test_table_has_selected_ids_attribute(self, sample_categories):
        """Test CategoryTable has selected_ids set for tracking selections."""
        from src.ui.tui.widgets.category_table import CategoryTable

        table = CategoryTable(categories=sample_categories)

        assert hasattr(table, "selected_ids")
        assert isinstance(table.selected_ids, set)
        assert len(table.selected_ids) == 0  # Initially empty

    def test_toggle_selection(self, sample_categories):
        """Test Space toggles selection on current category."""
        from src.ui.tui.widgets.category_table import CategoryTable

        table = CategoryTable(categories=sample_categories)

        # Toggle selection for first category
        table.toggle_selection("cat_001")
        assert "cat_001" in table.selected_ids

        # Toggle again to deselect
        table.toggle_selection("cat_001")
        assert "cat_001" not in table.selected_ids

    def test_select_all(self, sample_categories):
        """Test select_all selects all visible categories."""
        from src.ui.tui.widgets.category_table import CategoryTable

        table = CategoryTable(categories=sample_categories)

        table.select_all()

        assert len(table.selected_ids) == len(sample_categories)
        for cat in sample_categories:
            assert cat.category_id in table.selected_ids

    def test_clear_selection(self, sample_categories):
        """Test clear_selection removes all selections."""
        from src.ui.tui.widgets.category_table import CategoryTable

        table = CategoryTable(categories=sample_categories)
        table.select_all()
        assert len(table.selected_ids) > 0

        table.clear_selection()
        assert len(table.selected_ids) == 0

    def test_get_selected_categories(self, sample_categories):
        """Test get_selected_categories returns selected Category objects."""
        from src.ui.tui.widgets.category_table import CategoryTable

        table = CategoryTable(categories=sample_categories)
        table.toggle_selection("cat_001")
        table.toggle_selection("cat_003")

        selected = table.get_selected_categories()

        assert len(selected) == 2
        assert any(c.category_id == "cat_001" for c in selected)
        assert any(c.category_id == "cat_003" for c in selected)

    def test_is_selected(self, sample_categories):
        """Test is_selected checks if category is selected."""
        from src.ui.tui.widgets.category_table import CategoryTable

        table = CategoryTable(categories=sample_categories)
        table.toggle_selection("cat_001")

        assert table.is_selected("cat_001") is True
        assert table.is_selected("cat_002") is False


class TestBulkConfirmationDialog:
    """Test bulk action confirmation dialog."""

    def test_bulk_action_dialog_exists(self):
        """Test BulkActionDialog class exists."""
        from src.ui.tui.dialogs.bulk_action_dialog import BulkActionDialog

        assert BulkActionDialog is not None

    def test_bulk_action_dialog_shows_count(self, sample_categories):
        """Test dialog shows count of affected items."""
        from src.ui.tui.dialogs.bulk_action_dialog import BulkActionDialog

        dialog = BulkActionDialog(
            action="accept",
            count=3,
            categories=sample_categories[:3],
        )

        assert dialog.count == 3
        assert dialog.action == "accept"


class TestBulkActions:
    """Test bulk action methods."""

    def test_accept_selected_categories(self, sample_categories):
        """Test accepting multiple selected categories."""
        from src.ui.tui.widgets.category_table import CategoryTable

        table = CategoryTable(categories=sample_categories)
        table.toggle_selection("cat_001")
        table.toggle_selection("cat_002")

        accepted = table.accept_selected()

        # Should return the accepted categories
        assert len(accepted) == 2
        # Should remove from the table
        assert len(table.categories) == 3
        # Selection should be cleared
        assert len(table.selected_ids) == 0

    def test_delete_selected_categories(self, sample_categories):
        """Test deleting multiple selected categories."""
        from src.ui.tui.widgets.category_table import CategoryTable

        table = CategoryTable(categories=sample_categories)
        table.toggle_selection("cat_001")
        table.toggle_selection("cat_002")

        deleted = table.delete_selected()

        # Should return the deleted categories
        assert len(deleted) == 2
        # Should remove from the table
        assert len(table.categories) == 3
        # Selection should be cleared
        assert len(table.selected_ids) == 0


# ============================================================================
# Track 8B.2: Search/Filter Tests
# ============================================================================


class TestSearchInput:
    """Test search input widget."""

    def test_search_input_exists(self):
        """Test SearchInput widget exists."""
        from src.ui.tui.widgets.search_input import SearchInput

        assert SearchInput is not None

    def test_search_input_default_value(self):
        """Test SearchInput starts with empty value."""
        from src.ui.tui.widgets.search_input import SearchInput

        search = SearchInput()

        assert search.value == ""


class TestCategoryFiltering:
    """Test category filtering functionality."""

    def test_filter_by_name(self, sample_categories):
        """Test filtering categories by name (fuzzy match)."""
        from src.ui.tui.widgets.category_table import CategoryTable

        table = CategoryTable(categories=sample_categories)

        table.apply_filter("Financial")
        visible = table.get_visible_categories()

        assert len(visible) == 1
        assert visible[0].category_name == "Financial Alerts"

    def test_filter_by_name_case_insensitive(self, sample_categories):
        """Test filtering is case insensitive."""
        from src.ui.tui.widgets.category_table import CategoryTable

        table = CategoryTable(categories=sample_categories)

        table.apply_filter("shopping")
        visible = table.get_visible_categories()

        assert len(visible) == 1
        assert visible[0].category_name == "Shopping Orders"

    def test_filter_by_source(self, sample_categories):
        """Test filtering by source with syntax: source:cluster."""
        from src.ui.tui.widgets.category_table import CategoryTable

        table = CategoryTable(categories=sample_categories)

        table.apply_filter("source:content_cluster")
        visible = table.get_visible_categories()

        assert len(visible) == 2
        for cat in visible:
            assert cat.source == CategorySource.CONTENT_CLUSTER

    def test_filter_by_confidence_greater(self, sample_categories):
        """Test filtering by confidence: confidence:>80."""
        from src.ui.tui.widgets.category_table import CategoryTable

        table = CategoryTable(categories=sample_categories)

        table.apply_filter("confidence:>80")
        visible = table.get_visible_categories()

        # Categories with confidence > 0.80: cat_001 (0.85), cat_004 (0.90)
        assert len(visible) == 2
        for cat in visible:
            assert cat.confidence > 0.80

    def test_filter_by_confidence_less(self, sample_categories):
        """Test filtering by confidence: confidence:<70."""
        from src.ui.tui.widgets.category_table import CategoryTable

        table = CategoryTable(categories=sample_categories)

        table.apply_filter("confidence:<70")
        visible = table.get_visible_categories()

        # Categories with confidence < 0.70: cat_003 (0.65), cat_005 (0.55)
        assert len(visible) == 2
        for cat in visible:
            assert cat.confidence < 0.70

    def test_clear_filter(self, sample_categories):
        """Test clearing filter shows all categories."""
        from src.ui.tui.widgets.category_table import CategoryTable

        table = CategoryTable(categories=sample_categories)

        table.apply_filter("Financial")
        assert len(table.get_visible_categories()) == 1

        table.clear_filter()
        assert len(table.get_visible_categories()) == len(sample_categories)

    def test_filter_indicator_count(self, sample_categories):
        """Test filtered count indicator 'X of Y categories'."""
        from src.ui.tui.widgets.category_table import CategoryTable

        table = CategoryTable(categories=sample_categories)

        table.apply_filter("source:template")
        visible = table.get_visible_categories()

        assert table.filter_count_text == "2 of 5 categories"

    def test_has_active_filter(self, sample_categories):
        """Test has_active_filter property."""
        from src.ui.tui.widgets.category_table import CategoryTable

        table = CategoryTable(categories=sample_categories)

        assert table.has_active_filter is False

        table.apply_filter("test")
        assert table.has_active_filter is True

        table.clear_filter()
        assert table.has_active_filter is False


class TestPatternBasedSelection:
    """Test pattern-based selection functionality."""

    def test_select_by_confidence_threshold(self, sample_categories):
        """Test selecting all categories above confidence threshold."""
        from src.ui.tui.widgets.category_table import CategoryTable

        table = CategoryTable(categories=sample_categories)

        table.select_by_pattern("confidence:>80")

        # Should select cat_001 (0.85) and cat_004 (0.90)
        assert len(table.selected_ids) == 2
        assert "cat_001" in table.selected_ids
        assert "cat_004" in table.selected_ids

    def test_select_by_source(self, sample_categories):
        """Test selecting all categories by source."""
        from src.ui.tui.widgets.category_table import CategoryTable

        table = CategoryTable(categories=sample_categories)

        table.select_by_pattern("source:template")

        # Should select cat_001 and cat_005
        assert len(table.selected_ids) == 2
        assert "cat_001" in table.selected_ids
        assert "cat_005" in table.selected_ids


class TestSearchInputModule:
    """Test SearchInput module registration."""

    def test_search_input_importable(self):
        """Test SearchInput is importable from widgets."""
        from src.ui.tui.widgets import SearchInput

        assert SearchInput is not None


class TestBulkActionDialogModule:
    """Test BulkActionDialog module registration."""

    def test_bulk_action_dialog_importable(self):
        """Test BulkActionDialog is importable from dialogs."""
        from src.ui.tui.dialogs import BulkActionDialog

        assert BulkActionDialog is not None
