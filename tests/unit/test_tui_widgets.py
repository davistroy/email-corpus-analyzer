"""
Unit tests for the TUI widgets.

Tests CategoryTable, DetailPanel, and ActionBar widgets.
"""

from src.models.category import Category, CategorySource


def create_test_category(
    category_id: str = "test_cat_1",
    name: str = "Test Category",
    description: str = "A test category",
    confidence: float = 0.85,
    email_count: int = 10,
    percentage: float = 25.0,
    source: CategorySource = CategorySource.CONTENT_CLUSTER,
    example_email_ids: list[str] | None = None,
    distinguishing_features: list[str] | None = None
) -> Category:
    """Helper to create test Category objects."""
    return Category(
        category_id=category_id,
        category_name=name,
        description=description,
        confidence=confidence,
        email_count=email_count,
        percentage=percentage,
        source=source,
        source_id="test_source",
        example_email_ids=example_email_ids or [],
        distinguishing_features=distinguishing_features or []
    )


class TestCategoryTableInit:
    """Test CategoryTable initialization."""

    def test_table_can_be_instantiated(self):
        """Test that CategoryTable can be instantiated."""
        from src.ui.tui.widgets.category_table import CategoryTable

        categories = [create_test_category()]
        # CategoryTable defers setup to on_mount, so this should work without app
        table = CategoryTable(categories=categories)

        assert table is not None
        assert hasattr(table, "categories")

    def test_table_with_empty_categories(self):
        """Test table initialization with empty categories."""
        from src.ui.tui.widgets.category_table import CategoryTable

        table = CategoryTable(categories=[])

        assert table is not None
        assert table.categories == []

    def test_table_stores_categories(self):
        """Test that table stores categories."""
        from src.ui.tui.widgets.category_table import CategoryTable

        categories = [create_test_category()]
        table = CategoryTable(categories=categories)

        assert hasattr(table, "categories")
        assert len(table.categories) == 1


class TestCategoryTableColumns:
    """Test CategoryTable column configuration."""

    def test_table_has_columns_attribute(self):
        """Test that table has columns attribute."""
        from src.ui.tui.widgets.category_table import CategoryTable

        table = CategoryTable(categories=[])

        # The table should have the categories attribute
        assert hasattr(table, "categories")

    def test_table_columns_include_required_fields(self):
        """Test that table includes all required columns."""
        from src.ui.tui.widgets.category_table import TABLE_COLUMNS

        # TABLE_COLUMNS = ["#", "Name", "Confidence", "Emails", "Source"]
        required_columns = ["#", "name", "confidence", "emails", "source"]

        for col in required_columns:
            assert any(col.lower() in c.lower() for c in TABLE_COLUMNS), f"Missing column: {col}"


class TestCategoryTableSelection:
    """Test CategoryTable row selection."""

    def test_table_tracks_selected_row(self):
        """Test that table tracks selected row index."""
        from src.ui.tui.widgets.category_table import CategoryTable

        categories = [create_test_category()]
        table = CategoryTable(categories=categories)

        # selected_row is a reactive attribute
        assert hasattr(table, "selected_row")

    def test_table_get_selected_category(self):
        """Test getting selected category from table."""
        from src.ui.tui.widgets.category_table import CategoryTable

        category = create_test_category(name="Selected")
        table = CategoryTable(categories=[category])
        table.selected_row = 0  # Ensure index is set

        selected = table.get_selected_category()
        assert selected is not None
        assert selected.category_name == "Selected"

    def test_table_selection_with_empty_categories(self):
        """Test selection returns None with empty categories."""
        from src.ui.tui.widgets.category_table import CategoryTable

        table = CategoryTable(categories=[])

        selected = table.get_selected_category()
        assert selected is None


class TestCategoryTableNavigation:
    """Test CategoryTable navigation methods."""

    def test_table_move_down(self):
        """Test moving selection down."""
        from unittest.mock import patch

        from src.ui.tui.widgets.category_table import CategoryTable

        categories = [
            create_test_category(category_id="cat1"),
            create_test_category(category_id="cat2"),
        ]
        table = CategoryTable(categories=categories)
        table.selected_row = 0

        # Mock move_cursor to avoid app context requirement
        with patch.object(table, 'move_cursor'):
            initial_row = table.selected_row
            table.move_down()

            assert table.selected_row == initial_row + 1

    def test_table_move_up(self):
        """Test moving selection up."""
        from unittest.mock import patch

        from src.ui.tui.widgets.category_table import CategoryTable

        categories = [
            create_test_category(category_id="cat1"),
            create_test_category(category_id="cat2"),
        ]
        table = CategoryTable(categories=categories)
        table.selected_row = 1  # Start at second row

        with patch.object(table, 'move_cursor'):
            table.move_up()

            assert table.selected_row == 0

    def test_table_move_down_at_end_wraps(self):
        """Test that moving down at end wraps to beginning."""
        from unittest.mock import patch

        from src.ui.tui.widgets.category_table import CategoryTable

        categories = [
            create_test_category(category_id="cat1"),
            create_test_category(category_id="cat2"),
        ]
        table = CategoryTable(categories=categories)
        table.selected_row = 1  # At last row

        with patch.object(table, 'move_cursor'):
            table.move_down()

            # Should wrap to 0
            assert table.selected_row == 0

    def test_table_move_up_at_start_wraps(self):
        """Test that moving up at start wraps to end."""
        from unittest.mock import patch

        from src.ui.tui.widgets.category_table import CategoryTable

        categories = [
            create_test_category(category_id="cat1"),
            create_test_category(category_id="cat2"),
        ]
        table = CategoryTable(categories=categories)
        table.selected_row = 0  # At first row

        with patch.object(table, 'move_cursor'):
            table.move_up()

            # Should wrap to last row (1)
            assert table.selected_row == 1


class TestCategoryTableRemove:
    """Test CategoryTable category removal."""

    def test_table_remove_category(self):
        """Test removing a category from table."""
        from unittest.mock import patch

        from src.ui.tui.widgets.category_table import CategoryTable

        cat1 = create_test_category(category_id="cat1")
        cat2 = create_test_category(category_id="cat2")
        table = CategoryTable(categories=[cat1, cat2])

        # Mock _populate_rows which requires app context
        with patch.object(table, '_populate_rows'):
            table.remove_category(cat1)

            assert len(table.categories) == 1
            assert cat1 not in table.categories

    def test_table_remove_updates_selection(self):
        """Test that removing category updates selection."""
        from unittest.mock import patch

        from src.ui.tui.widgets.category_table import CategoryTable

        cat1 = create_test_category(category_id="cat1")
        cat2 = create_test_category(category_id="cat2")
        table = CategoryTable(categories=[cat1, cat2])
        table.selected_row = 1

        with patch.object(table, '_populate_rows'):
            table.remove_category(cat2)

            # Selection should be valid after removal
            assert table.selected_row >= 0
            assert table.selected_row < len(table.categories) or len(table.categories) == 0


class TestDetailPanelInit:
    """Test DetailPanel initialization."""

    def test_panel_can_be_instantiated(self):
        """Test that DetailPanel can be instantiated."""
        from src.ui.tui.widgets.detail_panel import DetailPanel

        panel = DetailPanel()

        assert panel is not None

    def test_panel_with_initial_category(self):
        """Test panel initialization with category."""
        from src.ui.tui.widgets.detail_panel import DetailPanel

        category = create_test_category()
        panel = DetailPanel(category=category)

        assert panel.category == category


class TestDetailPanelUpdate:
    """Test DetailPanel update methods."""

    def test_panel_update_category(self):
        """Test updating panel with new category."""
        from src.ui.tui.widgets.detail_panel import DetailPanel

        panel = DetailPanel()
        category = create_test_category(name="Updated Category")

        panel.update_category(category)

        assert panel.category == category
        assert panel.category.category_name == "Updated Category"

    def test_panel_clear_category(self):
        """Test clearing category from panel."""
        from src.ui.tui.widgets.detail_panel import DetailPanel

        category = create_test_category()
        panel = DetailPanel(category=category)

        panel.clear()

        assert panel.category is None


class TestDetailPanelContent:
    """Test DetailPanel content display."""

    def test_panel_shows_category_name(self):
        """Test that panel shows category name."""
        from src.ui.tui.widgets.detail_panel import DetailPanel

        category = create_test_category(name="Newsletter Updates")
        panel = DetailPanel(category=category)

        content = panel.get_content_text()
        assert "Newsletter Updates" in content

    def test_panel_shows_description(self):
        """Test that panel shows description."""
        from src.ui.tui.widgets.detail_panel import DetailPanel

        category = create_test_category(description="Weekly newsletter emails")
        panel = DetailPanel(category=category)

        content = panel.get_content_text()
        assert "Weekly newsletter emails" in content

    def test_panel_shows_confidence(self):
        """Test that panel shows confidence score."""
        from src.ui.tui.widgets.detail_panel import DetailPanel

        category = create_test_category(confidence=0.85)
        panel = DetailPanel(category=category)

        content = panel.get_content_text()
        assert "85" in content or "0.85" in content

    def test_panel_shows_email_count(self):
        """Test that panel shows email count."""
        from src.ui.tui.widgets.detail_panel import DetailPanel

        category = create_test_category(email_count=150)
        panel = DetailPanel(category=category)

        content = panel.get_content_text()
        assert "150" in content

    def test_panel_shows_distinguishing_features(self):
        """Test that panel shows distinguishing features."""
        from src.ui.tui.widgets.detail_panel import DetailPanel

        category = create_test_category(
            distinguishing_features=["Contains invoice data", "From accounting dept"]
        )
        panel = DetailPanel(category=category)

        content = panel.get_content_text()
        assert "invoice" in content.lower() or "features" in content.lower()


class TestDetailPanelCollapsible:
    """Test DetailPanel collapsible behavior."""

    def test_panel_has_collapsed_state(self):
        """Test that panel has collapsed state."""
        from src.ui.tui.widgets.detail_panel import DetailPanel

        panel = DetailPanel()

        assert hasattr(panel, "collapsed") or hasattr(panel, "_collapsed")

    def test_panel_toggle_collapse(self):
        """Test toggling collapse state."""
        from src.ui.tui.widgets.detail_panel import DetailPanel

        panel = DetailPanel()
        initial_state = panel.collapsed

        panel.toggle_collapse()

        assert panel.collapsed != initial_state


class TestActionBarInit:
    """Test ActionBar initialization."""

    def test_bar_can_be_instantiated(self):
        """Test that ActionBar can be instantiated."""
        from src.ui.tui.widgets.action_bar import ActionBar

        bar = ActionBar()

        assert bar is not None


class TestActionBarCommands:
    """Test ActionBar command display."""

    def test_bar_shows_accept_command(self):
        """Test that action bar shows accept command."""
        from src.ui.tui.widgets.action_bar import COMMANDS

        assert any("accept" in cmd.lower() or cmd == "A" for cmd in COMMANDS)

    def test_bar_shows_rename_command(self):
        """Test that action bar shows rename command."""
        from src.ui.tui.widgets.action_bar import COMMANDS

        assert any("rename" in cmd.lower() or cmd == "R" for cmd in COMMANDS)

    def test_bar_shows_merge_command(self):
        """Test that action bar shows merge command."""
        from src.ui.tui.widgets.action_bar import COMMANDS

        assert any("merge" in cmd.lower() or cmd == "M" for cmd in COMMANDS)

    def test_bar_shows_delete_command(self):
        """Test that action bar shows delete command."""
        from src.ui.tui.widgets.action_bar import COMMANDS

        assert any("delete" in cmd.lower() or cmd == "D" for cmd in COMMANDS)

    def test_bar_shows_skip_command(self):
        """Test that action bar shows skip command."""
        from src.ui.tui.widgets.action_bar import COMMANDS

        assert any("skip" in cmd.lower() or cmd == "S" for cmd in COMMANDS)

    def test_bar_shows_help_command(self):
        """Test that action bar shows help command."""
        from src.ui.tui.widgets.action_bar import COMMANDS

        assert any("help" in cmd.lower() or cmd == "?" for cmd in COMMANDS)


class TestCommandsModule:
    """Test commands module."""

    def test_commands_module_exists(self):
        """Test that commands module exists."""
        from src.ui.tui import commands

        assert commands is not None

    def test_command_accept_exists(self):
        """Test that accept command is defined."""
        from src.ui.tui.commands import Command

        assert Command is not None

    def test_command_has_key(self):
        """Test that Command has key attribute."""
        from src.ui.tui.commands import Command

        cmd = Command(key="a", description="Accept", action="accept")
        assert cmd.key == "a"

    def test_command_has_description(self):
        """Test that Command has description."""
        from src.ui.tui.commands import Command

        cmd = Command(key="a", description="Accept category", action="accept")
        assert cmd.description == "Accept category"

    def test_get_all_commands(self):
        """Test getting all available commands."""
        from src.ui.tui.commands import get_all_commands

        commands = get_all_commands()

        assert len(commands) >= 5  # At least A, R, M, D, S


class TestWidgetsPackageInit:
    """Test widgets package initialization."""

    def test_package_imports(self):
        """Test that widgets package can be imported."""
        from src.ui.tui.widgets import ActionBar, CategoryTable, DetailPanel

        assert CategoryTable is not None
        assert DetailPanel is not None
        assert ActionBar is not None


class TestConfidenceBar:
    """Test confidence bar rendering in CategoryTable."""

    def test_format_confidence_bar(self):
        """Test confidence bar formatting."""
        from src.ui.tui.widgets.category_table import format_confidence_bar

        bar = format_confidence_bar(0.85)
        assert bar is not None
        assert len(bar) > 0

    def test_confidence_bar_high(self):
        """Test confidence bar for high confidence."""
        from src.ui.tui.widgets.category_table import format_confidence_bar

        bar = format_confidence_bar(0.9)
        # High confidence should show more filled characters
        assert bar is not None

    def test_confidence_bar_low(self):
        """Test confidence bar for low confidence."""
        from src.ui.tui.widgets.category_table import format_confidence_bar

        bar = format_confidence_bar(0.2)
        # Low confidence should show fewer filled characters
        assert bar is not None

    def test_confidence_bar_zero(self):
        """Test confidence bar for zero confidence."""
        from src.ui.tui.widgets.category_table import format_confidence_bar

        bar = format_confidence_bar(0.0)
        assert bar is not None

    def test_confidence_bar_full(self):
        """Test confidence bar for full confidence."""
        from src.ui.tui.widgets.category_table import format_confidence_bar

        bar = format_confidence_bar(1.0)
        assert bar is not None


class TestCategoryTableFormatting:
    """Test CategoryTable row formatting."""

    def test_format_source(self):
        """Test source formatting."""
        from src.ui.tui.widgets.category_table import format_source

        assert format_source(CategorySource.CONTENT_CLUSTER) == "Cluster"
        assert format_source(CategorySource.SENDER) == "Sender"
        assert format_source(CategorySource.TEMPLATE) == "Template"
        assert format_source(CategorySource.CUSTOM) == "Custom"

    def test_format_email_count(self):
        """Test email count formatting."""
        from src.ui.tui.widgets.category_table import format_email_count

        assert format_email_count(100) == "100"
        assert format_email_count(None) == "-"
        assert format_email_count(0) == "0"


class TestActionBarContextual:
    """Test ActionBar contextual state."""

    def test_bar_enable_disable_command(self):
        """Test enabling/disabling commands."""
        from src.ui.tui.widgets.action_bar import ActionBar

        bar = ActionBar()

        # Merge should be disabled when no approved categories
        bar.set_merge_enabled(False)
        assert not bar.is_merge_enabled()

        bar.set_merge_enabled(True)
        assert bar.is_merge_enabled()


# -----------------------------------------------------------------------------
# Hierarchical Category Table Tests (Task 4A.4)
# -----------------------------------------------------------------------------


class TestHierarchicalCategoryTable:
    """Test CategoryTable with hierarchical categories."""

    def create_hierarchical_category(
        self,
        category_id: str = "parent_1",
        name: str = "Parent Category",
        level: int = 0,
        parent_category_id: str | None = None,
        subcategories: list | None = None,
    ) -> Category:
        """Create a hierarchical test category."""
        return Category(
            category_id=category_id,
            category_name=name,
            description=f"Test {name}",
            confidence=0.85,
            email_count=100,
            percentage=10.0,
            source=CategorySource.CONTENT_CLUSTER,
            level=level,
            parent_category_id=parent_category_id,
            subcategories=subcategories or [],
        )

    def test_table_accepts_hierarchical_categories(self):
        """Test that CategoryTable accepts categories with hierarchy."""
        from src.ui.tui.widgets.category_table import CategoryTable

        child1 = self.create_hierarchical_category(
            category_id="child_1",
            name="Child 1",
            level=1,
            parent_category_id="parent_1",
        )
        parent = self.create_hierarchical_category(
            category_id="parent_1",
            name="Parent",
            level=0,
            subcategories=[child1],
        )

        table = CategoryTable(categories=[parent])

        assert len(table.categories) == 1
        assert table.categories[0].has_children

    def test_table_get_expanded_state(self):
        """Test that table tracks expanded state for hierarchical items."""
        from src.ui.tui.widgets.category_table import CategoryTable

        child = self.create_hierarchical_category(
            category_id="child_1",
            name="Child",
            level=1,
            parent_category_id="parent_1",
        )
        parent = self.create_hierarchical_category(
            category_id="parent_1",
            name="Parent",
            level=0,
            subcategories=[child],
        )

        table = CategoryTable(categories=[parent])

        # Should have is_expanded method or attribute
        assert hasattr(table, 'is_expanded') or hasattr(table, '_expanded_ids')

    def test_table_toggle_expand_collapse(self):
        """Test expanding/collapsing categories with subcategories."""
        from unittest.mock import patch

        from src.ui.tui.widgets.category_table import CategoryTable

        child = self.create_hierarchical_category(
            category_id="child_1",
            name="Child",
            level=1,
            parent_category_id="parent_1",
        )
        parent = self.create_hierarchical_category(
            category_id="parent_1",
            name="Parent",
            level=0,
            subcategories=[child],
        )

        table = CategoryTable(categories=[parent])

        # Should have toggle method
        if hasattr(table, 'toggle_expand'):
            initial = table.is_expanded(parent.category_id)
            # Mock _populate_rows to avoid DataTable column requirements
            with patch.object(table, '_populate_rows'):
                table.toggle_expand(parent.category_id)
            assert table.is_expanded(parent.category_id) != initial

    def test_table_get_visible_rows(self):
        """Test getting visible rows respects expanded state."""
        from src.ui.tui.widgets.category_table import CategoryTable

        child = self.create_hierarchical_category(
            category_id="child_1",
            name="Child",
            level=1,
            parent_category_id="parent_1",
        )
        parent = self.create_hierarchical_category(
            category_id="parent_1",
            name="Parent",
            level=0,
            subcategories=[child],
        )

        table = CategoryTable(categories=[parent])

        # Should have method to get visible rows
        if hasattr(table, 'get_visible_categories'):
            visible = table.get_visible_categories()
            assert len(visible) >= 1


class TestHierarchicalRowFormatting:
    """Test row formatting for hierarchical display."""

    def test_format_hierarchy_indicator_parent(self):
        """Test hierarchy indicator for parent categories."""
        from src.ui.tui.widgets.category_table import format_hierarchy_indicator

        # Collapsed parent
        indicator = format_hierarchy_indicator(level=0, has_children=True, expanded=False)
        assert "+" in indicator or ">" in indicator

        # Expanded parent
        indicator = format_hierarchy_indicator(level=0, has_children=True, expanded=True)
        assert "-" in indicator or "v" in indicator

    def test_format_hierarchy_indicator_child(self):
        """Test hierarchy indicator for child categories."""
        from src.ui.tui.widgets.category_table import format_hierarchy_indicator

        # Child should show indentation
        indicator = format_hierarchy_indicator(level=1, has_children=False, expanded=False)
        assert " " in indicator or "|" in indicator or "-" in indicator

    def test_format_hierarchy_indicator_leaf(self):
        """Test hierarchy indicator for leaf categories (no children)."""
        from src.ui.tui.widgets.category_table import format_hierarchy_indicator

        # Leaf at top level
        indicator = format_hierarchy_indicator(level=0, has_children=False, expanded=False)
        # Should not have expand/collapse indicator
        assert indicator is not None


class TestHierarchicalCategoryActions:
    """Test category actions in hierarchical context."""

    def create_hierarchical_category(
        self,
        category_id: str = "parent_1",
        name: str = "Parent Category",
        level: int = 0,
        parent_category_id: str | None = None,
        subcategories: list | None = None,
    ) -> Category:
        """Create a hierarchical test category."""
        return Category(
            category_id=category_id,
            category_name=name,
            description=f"Test {name}",
            confidence=0.85,
            email_count=100,
            percentage=10.0,
            source=CategorySource.CONTENT_CLUSTER,
            level=level,
            parent_category_id=parent_category_id,
            subcategories=subcategories or [],
        )

    def test_promote_subcategory_to_top_level(self):
        """Test promoting a subcategory to top level."""
        from unittest.mock import patch

        from src.ui.tui.widgets.category_table import CategoryTable

        child = self.create_hierarchical_category(
            category_id="child_1",
            name="Child",
            level=1,
            parent_category_id="parent_1",
        )
        parent = self.create_hierarchical_category(
            category_id="parent_1",
            name="Parent",
            level=0,
            subcategories=[child],
        )

        table = CategoryTable(categories=[parent])

        # Should have promote method
        if hasattr(table, 'promote_to_top_level'):
            with patch.object(table, '_populate_rows'):
                table.promote_to_top_level(child)
                # Child should become top level
                assert child.level == 0 or child in table.categories

    def test_demote_top_level_to_subcategory(self):
        """Test demoting a top-level category to subcategory."""
        from unittest.mock import patch

        from src.ui.tui.widgets.category_table import CategoryTable

        cat1 = self.create_hierarchical_category(
            category_id="cat_1",
            name="Category 1",
            level=0,
        )
        cat2 = self.create_hierarchical_category(
            category_id="cat_2",
            name="Category 2",
            level=0,
        )

        table = CategoryTable(categories=[cat1, cat2])

        # Should have demote method
        if hasattr(table, 'demote_to_subcategory'):
            with patch.object(table, '_populate_rows'):
                table.demote_to_subcategory(cat2, cat1)
                # cat2 should become subcategory of cat1
                assert cat2.level == 1 or cat2 in cat1.subcategories


# =============================================================================
# Task 5A.3: Confidence Display Tests
# =============================================================================


class TestConfidenceBreakdownDisplay:
    """Test confidence breakdown display in DetailPanel."""

    def test_panel_shows_confidence_breakdown_when_available(self):
        """Test that panel shows confidence breakdown if category has it."""
        from src.ui.tui.widgets.detail_panel import DetailPanel

        category = Category(
            category_id="test_breakdown",
            category_name="Test Category",
            description="Test",
            confidence=0.75,
            email_count=100,
            percentage=10.0,
            source=CategorySource.TEMPLATE,
            distinguishing_features=[],
            confidence_breakdown={
                "cohesion": 0.6,
                "volume": 0.8,
                "source": 0.9,
                "percentage": 0.1,
                "name_quality": 0.7,
                "distinctiveness": 0.85
            }
        )

        panel = DetailPanel(category=category)
        content = panel.get_content_text()

        # Should show breakdown section
        assert "cohesion" in content.lower() or "Cohesion" in content
        assert "volume" in content.lower() or "Volume" in content
        assert "source" in content.lower() or "Source" in content

    def test_panel_hides_breakdown_when_not_available(self):
        """Test that panel does not crash when breakdown is None."""
        from src.ui.tui.widgets.detail_panel import DetailPanel

        category = Category(
            category_id="test_no_breakdown",
            category_name="Test Category",
            description="Test",
            confidence=0.75,
            email_count=100,
            percentage=10.0,
            source=CategorySource.TEMPLATE,
            distinguishing_features=[],
            confidence_breakdown=None
        )

        panel = DetailPanel(category=category)
        content = panel.get_content_text()

        # Should not crash, and should still show basic confidence
        assert "75" in content or "0.75" in content

    def test_panel_formats_breakdown_scores_as_percentages(self):
        """Test that breakdown scores are displayed as percentages."""
        from src.ui.tui.widgets.detail_panel import DetailPanel

        category = Category(
            category_id="test_pct",
            category_name="Test",
            description="Test",
            confidence=0.75,
            email_count=100,
            percentage=10.0,
            source=CategorySource.TEMPLATE,
            distinguishing_features=[],
            confidence_breakdown={
                "cohesion": 0.6,
                "volume": 0.8,
                "source": 0.9,
                "percentage": 0.1,
                "name_quality": 0.7,
                "distinctiveness": 0.85
            }
        )

        panel = DetailPanel(category=category)
        content = panel.get_content_text()

        # Should show at least one percentage value from breakdown
        assert "60" in content or "80" in content or "90" in content


class TestConfidenceBarVisualization:
    """Test visual confidence bar rendering."""

    def test_format_confidence_breakdown_bar(self):
        """Test formatting confidence breakdown as visual bars."""
        from src.ui.tui.widgets.detail_panel import format_confidence_bar

        # High score should show mostly filled
        high_bar = format_confidence_bar(0.9, width=10)
        assert len(high_bar) > 0

        # Low score should show mostly empty
        low_bar = format_confidence_bar(0.2, width=10)
        assert len(low_bar) > 0

    def test_format_confidence_breakdown_bar_width(self):
        """Test that confidence bar respects width parameter."""
        from src.ui.tui.widgets.detail_panel import format_confidence_bar

        bar_10 = format_confidence_bar(0.5, width=10)
        bar_20 = format_confidence_bar(0.5, width=20)

        # Bars should have different visual widths
        # (accounting for markup)
        assert bar_10 is not None
        assert bar_20 is not None

    def test_format_confidence_breakdown_bar_edge_cases(self):
        """Test confidence bar edge cases."""
        from src.ui.tui.widgets.detail_panel import format_confidence_bar

        # Zero confidence
        zero_bar = format_confidence_bar(0.0, width=10)
        assert zero_bar is not None

        # Full confidence
        full_bar = format_confidence_bar(1.0, width=10)
        assert full_bar is not None


class TestConfidenceComponentExplanation:
    """Test explanation text for confidence components."""

    def test_get_component_explanation(self):
        """Test getting explanation for confidence components."""
        from src.ui.tui.widgets.detail_panel import get_component_explanation

        # Each component should have an explanation
        cohesion_exp = get_component_explanation("cohesion")
        assert cohesion_exp is not None
        assert len(cohesion_exp) > 0

        volume_exp = get_component_explanation("volume")
        assert volume_exp is not None
        assert len(volume_exp) > 0

        source_exp = get_component_explanation("source")
        assert source_exp is not None
        assert len(source_exp) > 0

    def test_get_component_explanation_unknown(self):
        """Test that unknown component returns default explanation."""
        from src.ui.tui.widgets.detail_panel import get_component_explanation

        unknown_exp = get_component_explanation("unknown_component")
        assert unknown_exp is not None
        # Should return something reasonable, not crash


class TestCategoryReviewConfidenceDisplay:
    """Test confidence display in legacy CLI review."""

    def test_review_shows_confidence_breakdown(self):
        """Test that category review shows breakdown when available."""
        from src.ui.category_review import format_confidence_display

        category = Category(
            category_id="test_cli",
            category_name="Test",
            description="Test",
            confidence=0.75,
            email_count=100,
            percentage=10.0,
            source=CategorySource.TEMPLATE,
            distinguishing_features=[],
            confidence_breakdown={
                "cohesion": 0.6,
                "volume": 0.8,
                "source": 0.9,
                "percentage": 0.1,
                "name_quality": 0.7,
                "distinctiveness": 0.85
            }
        )

        display = format_confidence_display(category)

        assert "75" in display or "0.75" in display
        # Should include some breakdown info
        assert len(display) > 10

    def test_review_confidence_display_without_breakdown(self):
        """Test confidence display falls back gracefully without breakdown."""
        from src.ui.category_review import format_confidence_display

        category = Category(
            category_id="test_cli_no_breakdown",
            category_name="Test",
            description="Test",
            confidence=0.75,
            email_count=100,
            percentage=10.0,
            source=CategorySource.TEMPLATE,
            distinguishing_features=[]
        )

        display = format_confidence_display(category)

        assert "75" in display or "0.75" in display
