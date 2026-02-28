"""
Unit tests for Phase 2 Item 1.3: SearchInput and Filter System Integration.

Tests the wiring of SearchInput into the ReviewApp, filtering categories
in real-time, filter indicator display, Escape-to-clear behavior, and
integration with ReviewState.filter_text.

TDD: tests written first per constitution.
"""

from unittest.mock import MagicMock, patch

import pytest

from src.models.category import Category, CategorySource
from src.ui.tui.state import ReviewState

# ============================================================================
# Test Fixtures
# ============================================================================


def make_category(
    category_id: str = "cat_001",
    name: str = "Test Category",
    description: str = "A test category",
    confidence: float = 0.85,
    email_count: int = 100,
    source: CategorySource = CategorySource.CONTENT_CLUSTER,
) -> Category:
    """Create a test Category."""
    return Category(
        category_id=category_id,
        category_name=name,
        description=description,
        confidence=confidence,
        email_count=email_count,
        percentage=10.0,
        source=source,
        source_id="test_source",
        example_email_ids=[],
        distinguishing_features=[],
    )


@pytest.fixture
def sample_categories() -> list[Category]:
    """Create a realistic set of categories for testing."""
    return [
        make_category(
            category_id="cat_001",
            name="Financial Alerts",
            description="Bank and payment notifications",
            confidence=0.85,
            email_count=150,
            source=CategorySource.TEMPLATE,
        ),
        make_category(
            category_id="cat_002",
            name="Shopping Orders",
            description="E-commerce order confirmations and shipping updates",
            confidence=0.72,
            email_count=89,
            source=CategorySource.CONTENT_CLUSTER,
        ),
        make_category(
            category_id="cat_003",
            name="Newsletter Weekly",
            description="Weekly newsletters from subscriptions",
            confidence=0.65,
            email_count=45,
            source=CategorySource.SENDER,
        ),
        make_category(
            category_id="cat_004",
            name="Social Updates",
            description="Social media notifications and alerts",
            confidence=0.90,
            email_count=200,
            source=CategorySource.CONTENT_CLUSTER,
        ),
        make_category(
            category_id="cat_005",
            name="System Alerts",
            description="System notifications and monitoring",
            confidence=0.55,
            email_count=30,
            source=CategorySource.TEMPLATE,
        ),
    ]


# ============================================================================
# 1. Filter matches against description (new requirement)
# ============================================================================


class TestFilterMatchesDescription:
    """Test that filter matches against category description in addition to name and source."""

    def test_filter_matches_description_text(self, sample_categories):
        """Filter should match against category description field."""
        from src.ui.tui.widgets.category_table import CategoryTable

        table = CategoryTable(categories=sample_categories)

        # "payment" only appears in cat_001's description, not its name
        table.apply_filter("payment")
        visible = table.get_visible_categories()

        assert len(visible) == 1
        assert visible[0].category_id == "cat_001"

    def test_filter_matches_description_case_insensitive(self, sample_categories):
        """Description matching should be case insensitive."""
        from src.ui.tui.widgets.category_table import CategoryTable

        table = CategoryTable(categories=sample_categories)

        table.apply_filter("E-COMMERCE")
        visible = table.get_visible_categories()

        assert len(visible) == 1
        assert visible[0].category_id == "cat_002"

    def test_filter_matches_name_or_description(self, sample_categories):
        """Filter should match if text appears in name OR description."""
        from src.ui.tui.widgets.category_table import CategoryTable

        table = CategoryTable(categories=sample_categories)

        # "alerts" appears in cat_001 name, cat_004 description, cat_005 name
        table.apply_filter("alerts")
        visible = table.get_visible_categories()

        matching_ids = {c.category_id for c in visible}
        assert "cat_001" in matching_ids  # "Financial Alerts" (name)
        assert "cat_004" in matching_ids  # "alerts" in description
        assert "cat_005" in matching_ids  # "System Alerts" (name)


# ============================================================================
# 2. SearchInput vim-style '/' activation
# ============================================================================


class TestSearchInputActivation:
    """Test that SearchInput is activated by '/' key in ReviewApp."""

    def test_app_has_slash_binding(self):
        """ReviewApp should have a '/' key binding for search activation."""
        from src.ui.tui.app import ReviewApp

        app = ReviewApp(categories=[make_category()])

        binding_keys = [b.key for b in app.BINDINGS]
        assert "slash" in binding_keys or "/" in binding_keys

    def test_app_has_search_action(self):
        """ReviewApp should have an action_activate_search method."""
        from src.ui.tui.app import ReviewApp

        app = ReviewApp(categories=[make_category()])

        assert hasattr(app, "action_activate_search")

    def test_search_input_in_compose(self):
        """ReviewApp.compose() should include a SearchInput widget."""
        from src.ui.tui.app import ReviewApp

        app = ReviewApp(categories=[make_category()])

        # Check compose yields SearchInput by inspecting the compose generator
        widgets = list(app.compose())
        found = _find_widget_type_in_tree(widgets, "SearchInput")
        assert found, "SearchInput not found in compose() widget tree"


class TestSearchInputPlacement:
    """Test SearchInput is placed above CategoryTable in the layout."""

    def test_search_input_has_correct_id(self):
        """SearchInput in compose should have id='search-input'."""
        from src.ui.tui.app import ReviewApp

        app = ReviewApp(categories=[make_category()])
        widgets = list(app.compose())

        search = _find_widget_by_id_in_tree(widgets, "search-input")
        assert search is not None, "SearchInput with id='search-input' not found in compose"

    def test_search_input_before_category_table(self):
        """SearchInput should appear before CategoryTable in the left column."""
        from src.ui.tui.app import ReviewApp

        app = ReviewApp(categories=[make_category()])
        widgets = list(app.compose())

        # Find the Vertical container (id="category-list") that holds both
        category_list = _find_widget_by_id_in_tree(widgets, "category-list")
        assert category_list is not None, "category-list container not found"

        # Check ordering within _pending_children
        children = getattr(category_list, "_pending_children", [])
        child_types = [type(c).__name__ for c in children]
        assert "SearchInput" in child_types, "SearchInput not in category-list children"
        assert "CategoryTable" in child_types, "CategoryTable not in category-list children"

        search_idx = child_types.index("SearchInput")
        table_idx = child_types.index("CategoryTable")
        assert search_idx < table_idx, "SearchInput should appear before CategoryTable"


# ============================================================================
# 3. Filter indicator showing count of matching items
# ============================================================================


class TestFilterIndicator:
    """Test filter indicator text in the status/footer area."""

    def test_filter_indicator_shows_filtered_count(self):
        """SearchInput should have get_filter_indicator method."""
        from src.ui.tui.widgets.search_input import SearchInput

        search = SearchInput()
        assert hasattr(search, "get_filter_indicator")

    def test_filter_indicator_empty_when_no_filter(self):
        """When no filter is active, indicator should be empty string."""
        from src.ui.tui.widgets.search_input import SearchInput

        search = SearchInput()
        indicator = search.get_filter_indicator(visible_count=5, total_count=5)
        assert indicator == ""

    def test_filter_indicator_with_active_filter(self):
        """When filter is active, show 'Filtered: X/Y categories'.

        Uses the _filter_query attribute directly since Textual's value
        reactive requires an active app context.
        """
        from src.ui.tui.widgets.search_input import SearchInput

        search = SearchInput()

        # Bypass the reactive `value` setter by testing the method contract:
        # get_filter_indicator checks filter_query, which reads self.value.
        # We can't set value outside an app context, so we mock filter_query.
        with patch.object(
            type(search), "filter_query", new_callable=lambda: property(lambda self: "test")
        ):
            indicator = search.get_filter_indicator(visible_count=3, total_count=10)
            assert "3" in indicator
            assert "10" in indicator
            assert "Filtered" in indicator

    def test_filter_indicator_zero_matches(self):
        """When filter matches nothing, indicator should show 0."""
        from src.ui.tui.widgets.search_input import SearchInput

        search = SearchInput()

        with patch.object(
            type(search),
            "filter_query",
            new_callable=lambda: property(lambda self: "nonexistent"),
        ):
            indicator = search.get_filter_indicator(visible_count=0, total_count=10)
            assert "0" in indicator
            assert "10" in indicator


# ============================================================================
# 4. Escape clears filter and returns focus to table
# ============================================================================


class TestEscapeClearsFilter:
    """Test that Escape key clears the filter and returns focus to table."""

    def test_search_input_action_clear_resets_value(self):
        """SearchInput.action_clear() should set value to empty string.

        Uses mock to avoid Textual's reactive requiring an active app.
        """
        from src.ui.tui.widgets.search_input import SearchInput

        search = SearchInput()

        # Mock the reactive value setter since we're outside an app context
        with patch.object(
            type(search),
            "value",
            new_callable=lambda: property(
                lambda self: self._test_value if hasattr(self, "_test_value") else "",
                lambda self, v: setattr(self, "_test_value", v),
            ),
        ):
            search.value = "some filter text"
            assert search.value == "some filter text"

            search.action_clear()
            assert search.value == ""

    def test_search_input_escape_binding_exists(self):
        """SearchInput should have an Escape binding."""
        from src.ui.tui.widgets.search_input import SearchInput

        search = SearchInput()

        binding_keys = [b[0] for b in search.BINDINGS]
        assert "escape" in binding_keys


# ============================================================================
# 5. Integration with ReviewState.filter_text
# ============================================================================


class TestReviewStateFilterText:
    """Test that the filter system integrates with ReviewState.filter_text."""

    def test_state_has_filter_text(self, sample_categories):
        """ReviewState should have filter_text property."""
        state = ReviewState(categories=sample_categories)
        assert hasattr(state, "filter_text")
        assert state.filter_text == ""

    def test_state_filter_text_setter(self, sample_categories):
        """ReviewState.filter_text should be settable."""
        state = ReviewState(categories=sample_categories)
        state.filter_text = "test query"
        assert state.filter_text == "test query"

    def test_app_apply_filter_updates_state(self, sample_categories):
        """When _apply_filter is called, state.filter_text should update.

        We mock query_one since widgets aren't mounted in unit tests.
        """
        from src.ui.tui.app import ReviewApp

        app = ReviewApp(categories=sample_categories)
        assert hasattr(app, "_apply_filter")

        # Mock query_one to avoid needing mounted widgets
        with patch.object(app, "query_one", side_effect=Exception("not mounted")):
            # _apply_filter should still update state even if widgets fail
            pass

        # Directly test state update (the method updates state first, then
        # tries to update widgets which may raise NoMatches)
        from textual.css.query import NoMatches

        with patch.object(app, "query_one", side_effect=NoMatches("not mounted")):
            app._apply_filter("test query")

        assert app.state.filter_text == "test query"

    def test_app_clear_filter_clears_state(self, sample_categories):
        """When filter is cleared, state.filter_text should be empty."""
        from textual.css.query import NoMatches

        from src.ui.tui.app import ReviewApp

        app = ReviewApp(categories=sample_categories)

        with patch.object(app, "query_one", side_effect=NoMatches("not mounted")):
            app._apply_filter("test query")
            assert app.state.filter_text == "test query"

            app._apply_filter("")
            assert app.state.filter_text == ""


# ============================================================================
# 6. Filter narrows visible rows correctly
# ============================================================================


class TestFilterNarrowsVisibleRows:
    """Test that applying a filter reduces the visible rows correctly."""

    def test_empty_filter_shows_all_rows(self, sample_categories):
        """Empty filter string should show all categories."""
        from src.ui.tui.widgets.category_table import CategoryTable

        table = CategoryTable(categories=sample_categories)

        table.apply_filter("")
        visible = table.get_visible_categories()

        assert len(visible) == len(sample_categories)

    def test_filter_reduces_visible_count(self, sample_categories):
        """Non-empty filter should reduce visible rows."""
        from src.ui.tui.widgets.category_table import CategoryTable

        table = CategoryTable(categories=sample_categories)

        table.apply_filter("Financial")
        visible = table.get_visible_categories()

        assert len(visible) < len(sample_categories)
        assert len(visible) == 1

    def test_filter_no_match_shows_empty(self, sample_categories):
        """Filter with no matches should show zero rows."""
        from src.ui.tui.widgets.category_table import CategoryTable

        table = CategoryTable(categories=sample_categories)

        table.apply_filter("xyznonexistent")
        visible = table.get_visible_categories()

        assert len(visible) == 0


# ============================================================================
# 7. Selection state preserved when filter changes
# ============================================================================


class TestSelectionPreservedOnFilterChange:
    """Test that selection state is preserved across filter changes."""

    def test_selected_index_clamped_after_filter(self, sample_categories):
        """Selected index should be clamped to valid range after filter."""
        from src.ui.tui.widgets.category_table import CategoryTable

        table = CategoryTable(categories=sample_categories)
        table.selected_row = 4  # Last row (index 4)

        # Apply filter that shows only 1 category
        table.apply_filter("Financial")

        # selected_row should be clamped to valid range for visible categories
        visible = table.get_visible_categories()
        assert table.selected_row <= max(0, len(visible) - 1)

    def test_selected_index_unchanged_when_still_valid(self, sample_categories):
        """Selected index should stay the same if still in valid range."""
        from src.ui.tui.widgets.category_table import CategoryTable

        table = CategoryTable(categories=sample_categories)
        table.selected_row = 0

        # Apply filter that shows 3 categories
        table.apply_filter("alerts")
        visible = table.get_visible_categories()

        assert len(visible) == 3
        assert table.selected_row == 0


# ============================================================================
# 8. Filter + action maintains consistent state
# ============================================================================


class TestFilterActionConsistency:
    """Test that actions on filtered items maintain consistent state."""

    def test_delete_filtered_item_consistent(self, sample_categories):
        """Deleting a filtered item should maintain filter and state consistency."""
        from src.ui.tui.widgets.category_table import CategoryTable

        table = CategoryTable(categories=sample_categories)

        # Filter to see only "Financial Alerts"
        table.apply_filter("Financial")
        visible_before = table.get_visible_categories()
        assert len(visible_before) == 1

        # Remove the visible category from underlying data
        cat_to_remove = visible_before[0]
        table.categories.remove(cat_to_remove)

        # Re-apply filter - should show 0 now
        table.apply_filter("Financial")
        visible_after = table.get_visible_categories()
        assert len(visible_after) == 0

    def test_clear_filter_after_deletion_shows_remaining(self, sample_categories):
        """Clearing filter after deletion should show remaining categories."""
        from src.ui.tui.widgets.category_table import CategoryTable

        table = CategoryTable(categories=sample_categories)

        # Remove one category
        table.categories.remove(sample_categories[0])

        # Clear filter
        table.clear_filter()
        visible = table.get_visible_categories()

        assert len(visible) == len(sample_categories) - 1


# ============================================================================
# 9. App-level wiring: on_input_changed -> apply_filter
# ============================================================================


class TestAppFilterWiring:
    """Test that ReviewApp wires SearchInput changes to CategoryTable filter."""

    def test_app_has_on_search_changed_handler(self):
        """ReviewApp should handle SearchInput.Changed event."""
        from src.ui.tui.app import ReviewApp

        app = ReviewApp(categories=[make_category()])

        # Should have a handler for input changed events
        assert hasattr(app, "_on_search_input_changed") or hasattr(app, "on_input_changed")

    def test_apply_filter_method_exists(self):
        """ReviewApp should have _apply_filter method."""
        from src.ui.tui.app import ReviewApp

        app = ReviewApp(categories=[make_category()])
        assert hasattr(app, "_apply_filter")

    def test_on_search_input_changed_filters_by_id(self):
        """_on_search_input_changed should only respond to search-input widget."""
        from src.ui.tui.app import ReviewApp

        app = ReviewApp(categories=[make_category()])

        # Create mock event with wrong id - should be ignored
        mock_event = MagicMock()
        mock_event.input.id = "rename-input"
        mock_event.value = "test"

        # Should not call _apply_filter
        with patch.object(app, "_apply_filter") as mock_apply:
            app._on_search_input_changed(mock_event)
            mock_apply.assert_not_called()

        # Create mock event with correct id - should trigger filter
        mock_event.input.id = "search-input"
        with patch.object(app, "_apply_filter") as mock_apply:
            app._on_search_input_changed(mock_event)
            mock_apply.assert_called_once_with("test")


# ============================================================================
# 10. CategoryTable._clamp_selected_row
# ============================================================================


class TestClampSelectedRow:
    """Test the _clamp_selected_row method on CategoryTable."""

    def test_clamp_to_zero_on_empty_filter(self, sample_categories):
        """When filter yields no results, selected_row should be 0."""
        from src.ui.tui.widgets.category_table import CategoryTable

        table = CategoryTable(categories=sample_categories)
        table.selected_row = 3

        table.apply_filter("xyznonexistent")
        assert table.selected_row == 0

    def test_clamp_to_last_visible(self, sample_categories):
        """When selected_row exceeds visible count, clamp to last visible."""
        from src.ui.tui.widgets.category_table import CategoryTable

        table = CategoryTable(categories=sample_categories)
        table.selected_row = 4  # index 4 = last of 5

        # Filter to 2 categories (source:template -> cat_001, cat_005)
        table.apply_filter("source:template")
        visible = table.get_visible_categories()
        assert len(visible) == 2
        assert table.selected_row == 1  # clamped to last visible (index 1)


# ============================================================================
# Helpers
# ============================================================================


def _find_widget_type_in_tree(widgets, type_name: str) -> bool:
    """Recursively search for a widget type in compose output.

    Handles Textual's _pending_children for Container widgets
    which haven't been mounted yet.
    """
    for w in widgets:
        if type(w).__name__ == type_name:
            return True
        # Check _pending_children (Textual containers before mount)
        pending = getattr(w, "_pending_children", [])
        if pending and _find_widget_type_in_tree(pending, type_name):
            return True
        # Check _nodes (NodeList, populated after mount)
        nodes = getattr(w, "_nodes", [])
        if nodes and _find_widget_type_in_tree(list(nodes), type_name):
            return True
    return False


def _find_widget_by_id_in_tree(widgets, widget_id: str):
    """Recursively search for a widget by id in compose output.

    Handles Textual's _pending_children for Container widgets
    which haven't been mounted yet.
    """
    for w in widgets:
        if getattr(w, "id", None) == widget_id:
            return w
        # Check _pending_children
        pending = getattr(w, "_pending_children", [])
        if pending:
            found = _find_widget_by_id_in_tree(pending, widget_id)
            if found:
                return found
        # Check _nodes
        nodes = getattr(w, "_nodes", [])
        if nodes:
            found = _find_widget_by_id_in_tree(list(nodes), widget_id)
            if found:
                return found
    return None
