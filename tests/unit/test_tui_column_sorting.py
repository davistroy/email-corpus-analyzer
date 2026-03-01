"""
Unit tests for Phase 2 Item 2.3: Column Sorting.

Tests F1-F4 sort keys with toggle ascending/descending,
sort indicator in column headers, selection preservation after sort,
and sort persistence across actions.

TDD approach: tests written first before implementation.
"""

import pytest

from src.models.category import Category, CategorySource

# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def sample_categories() -> list[Category]:
    """Create sample categories with varied properties for sorting tests."""
    return [
        Category(
            category_id="cat_001",
            category_name="Financial Alerts",
            description="Bank notifications",
            confidence=0.85,
            email_count=150,
            source=CategorySource.TEMPLATE,
        ),
        Category(
            category_id="cat_002",
            category_name="Shopping Orders",
            description="E-commerce orders",
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
            description="Social media",
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


@pytest.fixture
def categories_with_none_counts() -> list[Category]:
    """Categories with None email_count to test sort edge cases."""
    return [
        Category(
            category_id="cat_a",
            category_name="Alpha",
            description="First",
            confidence=0.5,
            email_count=None,
            source=CategorySource.TEMPLATE,
        ),
        Category(
            category_id="cat_b",
            category_name="Beta",
            description="Second",
            confidence=0.7,
            email_count=100,
            source=CategorySource.SENDER,
        ),
    ]


# ============================================================================
# SortState Tests
# ============================================================================


class TestSortState:
    """Test SortState dataclass for tracking sort configuration."""

    def test_sort_state_default_values(self):
        """SortState defaults to confidence descending."""
        from src.ui.tui.widgets.category_table import SortState

        state = SortState()
        assert state.column == "confidence"
        assert state.ascending is False

    def test_sort_state_custom_values(self):
        """SortState can be initialized with custom values."""
        from src.ui.tui.widgets.category_table import SortState

        state = SortState(column="name", ascending=True)
        assert state.column == "name"
        assert state.ascending is True

    def test_sort_state_toggle_same_column(self):
        """Toggling the same column flips ascending/descending."""
        from src.ui.tui.widgets.category_table import SortState

        state = SortState(column="name", ascending=True)
        state.toggle("name")
        assert state.column == "name"
        assert state.ascending is False

    def test_sort_state_toggle_different_column(self):
        """Toggling a different column switches to it with default direction."""
        from src.ui.tui.widgets.category_table import SortState

        state = SortState(column="name", ascending=True)
        state.toggle("confidence")
        assert state.column == "confidence"
        # Confidence defaults to descending (high to low)
        assert state.ascending is False

    def test_sort_state_toggle_name_defaults_ascending(self):
        """Switching to name column defaults to ascending (A-Z)."""
        from src.ui.tui.widgets.category_table import SortState

        state = SortState(column="confidence", ascending=False)
        state.toggle("name")
        assert state.column == "name"
        assert state.ascending is True

    def test_sort_state_toggle_source_defaults_ascending(self):
        """Switching to source column defaults to ascending (A-Z)."""
        from src.ui.tui.widgets.category_table import SortState

        state = SortState(column="confidence", ascending=False)
        state.toggle("source")
        assert state.column == "source"
        assert state.ascending is True

    def test_sort_state_toggle_emails_defaults_descending(self):
        """Switching to emails column defaults to descending (most first)."""
        from src.ui.tui.widgets.category_table import SortState

        state = SortState(column="name", ascending=True)
        state.toggle("emails")
        assert state.column == "emails"
        assert state.ascending is False

    def test_sort_state_indicator_ascending(self):
        """Sort indicator shows up arrow for ascending."""
        from src.ui.tui.widgets.category_table import SortState

        state = SortState(column="name", ascending=True)
        assert state.indicator == "\u25b2"  # ▲

    def test_sort_state_indicator_descending(self):
        """Sort indicator shows down arrow for descending."""
        from src.ui.tui.widgets.category_table import SortState

        state = SortState(column="name", ascending=False)
        assert state.indicator == "\u25bc"  # ▼


# ============================================================================
# sort_categories Function Tests
# ============================================================================


class TestSortCategories:
    """Test the sort_categories function that applies sort to a category list."""

    def test_sort_by_name_ascending(self, sample_categories):
        """Sort by name ascending produces alphabetical order."""
        from src.ui.tui.widgets.category_table import SortState, sort_categories

        state = SortState(column="name", ascending=True)
        result = sort_categories(sample_categories, state)
        names = [c.category_name for c in result]
        assert names == sorted(names)

    def test_sort_by_name_descending(self, sample_categories):
        """Sort by name descending produces reverse alphabetical order."""
        from src.ui.tui.widgets.category_table import SortState, sort_categories

        state = SortState(column="name", ascending=False)
        result = sort_categories(sample_categories, state)
        names = [c.category_name for c in result]
        assert names == sorted(names, reverse=True)

    def test_sort_by_confidence_descending(self, sample_categories):
        """Sort by confidence descending puts highest first."""
        from src.ui.tui.widgets.category_table import SortState, sort_categories

        state = SortState(column="confidence", ascending=False)
        result = sort_categories(sample_categories, state)
        scores = [c.confidence for c in result]
        assert scores == sorted(scores, reverse=True)

    def test_sort_by_confidence_ascending(self, sample_categories):
        """Sort by confidence ascending puts lowest first."""
        from src.ui.tui.widgets.category_table import SortState, sort_categories

        state = SortState(column="confidence", ascending=True)
        result = sort_categories(sample_categories, state)
        scores = [c.confidence for c in result]
        assert scores == sorted(scores)

    def test_sort_by_emails_descending(self, sample_categories):
        """Sort by email count descending puts highest first."""
        from src.ui.tui.widgets.category_table import SortState, sort_categories

        state = SortState(column="emails", ascending=False)
        result = sort_categories(sample_categories, state)
        counts = [c.email_count for c in result]
        assert counts == sorted(counts, reverse=True)

    def test_sort_by_emails_ascending(self, sample_categories):
        """Sort by email count ascending puts lowest first."""
        from src.ui.tui.widgets.category_table import SortState, sort_categories

        state = SortState(column="emails", ascending=True)
        result = sort_categories(sample_categories, state)
        counts = [c.email_count for c in result]
        assert counts == sorted(counts)

    def test_sort_by_source_ascending(self, sample_categories):
        """Sort by source ascending produces alphabetical source order."""
        from src.ui.tui.widgets.category_table import SortState, sort_categories

        state = SortState(column="source", ascending=True)
        result = sort_categories(sample_categories, state)
        sources = [c.source.value for c in result]
        assert sources == sorted(sources)

    def test_sort_by_source_descending(self, sample_categories):
        """Sort by source descending produces reverse alphabetical source order."""
        from src.ui.tui.widgets.category_table import SortState, sort_categories

        state = SortState(column="source", ascending=False)
        result = sort_categories(sample_categories, state)
        sources = [c.source.value for c in result]
        assert sources == sorted(sources, reverse=True)

    def test_sort_does_not_mutate_original(self, sample_categories):
        """Sorting returns a new list; original is unchanged."""
        from src.ui.tui.widgets.category_table import SortState, sort_categories

        original_ids = [c.category_id for c in sample_categories]
        state = SortState(column="name", ascending=True)
        sort_categories(sample_categories, state)
        assert [c.category_id for c in sample_categories] == original_ids

    def test_sort_empty_list(self):
        """Sorting an empty list returns an empty list."""
        from src.ui.tui.widgets.category_table import SortState, sort_categories

        state = SortState(column="name", ascending=True)
        result = sort_categories([], state)
        assert result == []

    def test_sort_single_item(self, sample_categories):
        """Sorting a single-item list returns that item."""
        from src.ui.tui.widgets.category_table import SortState, sort_categories

        state = SortState(column="name", ascending=True)
        result = sort_categories([sample_categories[0]], state)
        assert len(result) == 1
        assert result[0].category_id == sample_categories[0].category_id

    def test_sort_with_none_email_count(self, categories_with_none_counts):
        """Sort by emails handles None counts (sorts them last)."""
        from src.ui.tui.widgets.category_table import SortState, sort_categories

        state = SortState(column="emails", ascending=True)
        result = sort_categories(categories_with_none_counts, state)
        # None should sort after numeric values in ascending
        assert result[0].category_id == "cat_b"  # 100 comes first
        assert result[1].category_id == "cat_a"  # None comes last

    def test_sort_with_none_email_count_descending(self, categories_with_none_counts):
        """Sort by emails descending handles None counts (sorts them last)."""
        from src.ui.tui.widgets.category_table import SortState, sort_categories

        state = SortState(column="emails", ascending=False)
        result = sort_categories(categories_with_none_counts, state)
        # In descending, None still goes last
        assert result[0].category_id == "cat_b"  # 100 comes first
        assert result[1].category_id == "cat_a"  # None comes last


# ============================================================================
# Column Header Indicator Tests
# ============================================================================


class TestColumnHeaderIndicators:
    """Test that sort indicators appear in column headers."""

    def test_get_column_header_with_sort_active(self):
        """Active sort column shows indicator arrow."""
        from src.ui.tui.widgets.category_table import SortState, get_sort_header

        state = SortState(column="name", ascending=True)
        header = get_sort_header("Name", "name", state)
        assert "\u25b2" in header  # ▲
        assert "Name" in header

    def test_get_column_header_with_sort_descending(self):
        """Descending sort column shows down arrow."""
        from src.ui.tui.widgets.category_table import SortState, get_sort_header

        state = SortState(column="confidence", ascending=False)
        header = get_sort_header("Confidence", "confidence", state)
        assert "\u25bc" in header  # ▼
        assert "Confidence" in header

    def test_get_column_header_inactive_no_indicator(self):
        """Inactive sort column shows no indicator."""
        from src.ui.tui.widgets.category_table import SortState, get_sort_header

        state = SortState(column="confidence", ascending=False)
        header = get_sort_header("Name", "name", state)
        assert "\u25b2" not in header
        assert "\u25bc" not in header
        assert header == "Name"

    def test_all_column_headers(self):
        """All four sortable column headers work correctly."""
        from src.ui.tui.widgets.category_table import SortState, get_sort_header

        columns = [
            ("Name", "name"),
            ("Confidence", "confidence"),
            ("Emails", "emails"),
            ("Source", "source"),
        ]

        for display_name, sort_key in columns:
            state = SortState(column=sort_key, ascending=True)
            header = get_sort_header(display_name, sort_key, state)
            assert "\u25b2" in header, f"Missing indicator for {sort_key}"
            assert display_name in header


# ============================================================================
# CategoryTable Sort Integration Tests
# ============================================================================


class TestCategoryTableSort:
    """Test sort integration in CategoryTable."""

    def test_table_has_sort_state(self, sample_categories):
        """CategoryTable has a sort_state attribute."""
        from src.ui.tui.widgets.category_table import CategoryTable

        table = CategoryTable(categories=sample_categories)
        assert hasattr(table, "sort_state")

    def test_table_default_sort_is_confidence_descending(self, sample_categories):
        """Default sort is confidence descending (current behavior)."""
        from src.ui.tui.widgets.category_table import CategoryTable

        table = CategoryTable(categories=sample_categories)
        assert table.sort_state.column == "confidence"
        assert table.sort_state.ascending is False

    def test_table_apply_sort_by_name(self, sample_categories):
        """apply_sort with name column sorts alphabetically."""
        from src.ui.tui.widgets.category_table import CategoryTable

        table = CategoryTable(categories=sample_categories)
        table.apply_sort("name")
        visible = table.get_visible_categories()
        names = [c.category_name for c in visible]
        assert names == sorted(names)

    def test_table_apply_sort_toggle(self, sample_categories):
        """Applying same sort twice toggles direction."""
        from src.ui.tui.widgets.category_table import CategoryTable

        table = CategoryTable(categories=sample_categories)
        table.apply_sort("name")  # First: ascending
        assert table.sort_state.ascending is True
        table.apply_sort("name")  # Second: descending
        assert table.sort_state.ascending is False

    def test_table_apply_sort_by_confidence(self, sample_categories):
        """apply_sort with confidence column sorts by score."""
        from src.ui.tui.widgets.category_table import CategoryTable

        table = CategoryTable(categories=sample_categories)
        table.apply_sort("confidence")
        # First toggle: confidence is already descending default,
        # so toggling makes it ascending
        visible = table.get_visible_categories()
        scores = [c.confidence for c in visible]
        assert scores == sorted(scores)

    def test_table_apply_sort_by_emails(self, sample_categories):
        """apply_sort with emails column sorts by count."""
        from src.ui.tui.widgets.category_table import CategoryTable

        table = CategoryTable(categories=sample_categories)
        table.apply_sort("emails")
        visible = table.get_visible_categories()
        counts = [c.email_count for c in visible]
        assert counts == sorted(counts, reverse=True)

    def test_table_apply_sort_by_source(self, sample_categories):
        """apply_sort with source column sorts by source type."""
        from src.ui.tui.widgets.category_table import CategoryTable

        table = CategoryTable(categories=sample_categories)
        table.apply_sort("source")
        visible = table.get_visible_categories()
        sources = [c.source.value for c in visible]
        assert sources == sorted(sources)

    def test_sort_preserves_all_categories(self, sample_categories):
        """Sort does not lose any categories."""
        from src.ui.tui.widgets.category_table import CategoryTable

        table = CategoryTable(categories=sample_categories)
        original_ids = {c.category_id for c in sample_categories}
        table.apply_sort("name")
        sorted_ids = {c.category_id for c in table.get_visible_categories()}
        assert sorted_ids == original_ids

    def test_sort_persists_after_removal(self, sample_categories):
        """Sort order is maintained after removing a category."""
        from src.ui.tui.widgets.category_table import CategoryTable

        table = CategoryTable(categories=sample_categories)
        table.apply_sort("name")

        # Remove one category
        table.remove_category(sample_categories[0])

        # Remaining should still be sorted by name
        visible = table.get_visible_categories()
        names = [c.category_name for c in visible]
        assert names == sorted(names)

    def test_sort_persists_after_update(self, sample_categories):
        """Sort order is re-applied after updating a category."""
        from src.ui.tui.widgets.category_table import CategoryTable

        table = CategoryTable(categories=sample_categories)
        table.apply_sort("name")

        # Update a category's name to something that changes sort position
        old_cat = sample_categories[1]
        new_cat = old_cat.model_copy(update={"category_name": "AAAA First"})
        table.update_category(old_cat, new_cat)

        visible = table.get_visible_categories()
        names = [c.category_name for c in visible]
        assert names == sorted(names)

    def test_sort_works_with_filter(self, sample_categories):
        """Sort applies correctly when a filter is active."""
        from src.ui.tui.widgets.category_table import CategoryTable

        table = CategoryTable(categories=sample_categories)
        table.apply_sort("name")
        table.apply_filter("alert")  # Should match "Financial Alerts" and "System Alerts"

        visible = table.get_visible_categories()
        names = [c.category_name for c in visible]
        assert len(names) >= 2
        assert names == sorted(names)


# ============================================================================
# Sort Key Mapping Tests
# ============================================================================


class TestSortKeyMapping:
    """Test the F-key to column mapping for sort operations."""

    def test_sort_key_map_has_four_entries(self):
        """SORT_KEY_MAP has exactly F1-F4 entries."""
        from src.ui.tui.widgets.category_table import SORT_KEY_MAP

        assert len(SORT_KEY_MAP) == 4

    def test_f1_maps_to_name(self):
        """F1 maps to name column."""
        from src.ui.tui.widgets.category_table import SORT_KEY_MAP

        assert SORT_KEY_MAP["f1"] == "name"

    def test_f2_maps_to_confidence(self):
        """F2 maps to confidence column."""
        from src.ui.tui.widgets.category_table import SORT_KEY_MAP

        assert SORT_KEY_MAP["f2"] == "confidence"

    def test_f3_maps_to_source(self):
        """F3 maps to source column."""
        from src.ui.tui.widgets.category_table import SORT_KEY_MAP

        assert SORT_KEY_MAP["f3"] == "source"

    def test_f4_maps_to_emails(self):
        """F4 maps to emails column."""
        from src.ui.tui.widgets.category_table import SORT_KEY_MAP

        assert SORT_KEY_MAP["f4"] == "emails"


# ============================================================================
# Selection Preservation Tests
# ============================================================================


class TestSortSelectionPreservation:
    """Test that the current selection is maintained after sorting."""

    def test_get_selected_category_preserved_after_sort(self, sample_categories):
        """After sorting, get_selected_category returns the same category."""
        from src.ui.tui.widgets.category_table import CategoryTable

        table = CategoryTable(categories=sample_categories)
        # Select the second category
        table.selected_row = 1
        selected_before = table.get_selected_category()
        assert selected_before is not None

        # Sort by name
        table.apply_sort("name")

        # The selected row should now point to the same category
        selected_after = table.get_selected_category()
        assert selected_after is not None
        assert selected_after.category_id == selected_before.category_id

    def test_selection_preserved_when_sort_changes_order(self, sample_categories):
        """Selection tracks category identity, not row position."""
        from src.ui.tui.widgets.category_table import CategoryTable

        table = CategoryTable(categories=sample_categories)
        # Initially select a specific category by moving to it
        target_id = "cat_003"  # Newsletter Weekly
        # Find its initial position
        for i, cat in enumerate(table.get_visible_categories()):
            if cat.category_id == target_id:
                table.selected_row = i
                break

        # Sort by confidence (changes order)
        table.apply_sort("confidence")

        # Find the new position
        selected = table.get_selected_category()
        assert selected is not None
        assert selected.category_id == target_id
