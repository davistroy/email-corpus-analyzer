"""
Unit tests for TUI progress bar and stats panel widgets.

Tests the ProgressBar and StatsPanel widgets for Task 3B.1.
"""
import pytest

from src.models.category import Category, CategorySource


def create_test_category(
    category_id: str = "test_cat_1",
    name: str = "Test Category",
    description: str = "A test category",
    confidence: float = 0.85,
    email_count: int = 10,
    percentage: float = 25.0,
    source: CategorySource = CategorySource.CONTENT_CLUSTER,
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
        example_email_ids=[],
        distinguishing_features=[]
    )


class TestProgressBarInit:
    """Test ProgressBar initialization."""

    def test_progress_bar_can_be_instantiated(self):
        """Test that ProgressBar can be instantiated."""
        from src.ui.tui.widgets.progress_bar import ProgressBar

        bar = ProgressBar(total=10, reviewed=0)

        assert bar is not None

    def test_progress_bar_with_total_and_reviewed(self):
        """Test progress bar with initial values."""
        from src.ui.tui.widgets.progress_bar import ProgressBar

        bar = ProgressBar(total=20, reviewed=5)

        assert bar.total == 20
        assert bar.reviewed == 5

    def test_progress_bar_with_zero_total(self):
        """Test progress bar handles zero total."""
        from src.ui.tui.widgets.progress_bar import ProgressBar

        bar = ProgressBar(total=0, reviewed=0)

        assert bar.total == 0
        assert bar.percentage == 0.0


class TestProgressBarPercentage:
    """Test ProgressBar percentage calculation."""

    def test_progress_bar_percentage_zero(self):
        """Test percentage when no items reviewed."""
        from src.ui.tui.widgets.progress_bar import ProgressBar

        bar = ProgressBar(total=10, reviewed=0)

        assert bar.percentage == 0.0

    def test_progress_bar_percentage_half(self):
        """Test percentage at 50%."""
        from src.ui.tui.widgets.progress_bar import ProgressBar

        bar = ProgressBar(total=10, reviewed=5)

        assert bar.percentage == 50.0

    def test_progress_bar_percentage_full(self):
        """Test percentage at 100%."""
        from src.ui.tui.widgets.progress_bar import ProgressBar

        bar = ProgressBar(total=10, reviewed=10)

        assert bar.percentage == 100.0

    def test_progress_bar_percentage_partial(self):
        """Test percentage with partial values."""
        from src.ui.tui.widgets.progress_bar import ProgressBar

        bar = ProgressBar(total=7, reviewed=3)

        # 3/7 * 100 = 42.857...
        assert 42.0 <= bar.percentage <= 43.0


class TestProgressBarUpdate:
    """Test ProgressBar update methods."""

    def test_progress_bar_increment(self):
        """Test incrementing reviewed count."""
        from src.ui.tui.widgets.progress_bar import ProgressBar

        bar = ProgressBar(total=10, reviewed=3)
        bar.increment()

        assert bar.reviewed == 4

    def test_progress_bar_set_reviewed(self):
        """Test setting reviewed count directly."""
        from src.ui.tui.widgets.progress_bar import ProgressBar

        bar = ProgressBar(total=10, reviewed=3)
        bar.set_reviewed(7)

        assert bar.reviewed == 7

    def test_progress_bar_reset(self):
        """Test resetting progress bar."""
        from src.ui.tui.widgets.progress_bar import ProgressBar

        bar = ProgressBar(total=10, reviewed=5)
        bar.reset()

        assert bar.reviewed == 0

    def test_progress_bar_update_total(self):
        """Test updating total count."""
        from src.ui.tui.widgets.progress_bar import ProgressBar

        bar = ProgressBar(total=10, reviewed=5)
        bar.set_total(20)

        assert bar.total == 20


class TestProgressBarDisplay:
    """Test ProgressBar display content."""

    def test_progress_bar_shows_count(self):
        """Test that progress bar displays count."""
        from src.ui.tui.widgets.progress_bar import ProgressBar

        bar = ProgressBar(total=10, reviewed=5)
        content = bar.get_content_text()

        assert "5" in content
        assert "10" in content

    def test_progress_bar_shows_percentage(self):
        """Test that progress bar displays percentage."""
        from src.ui.tui.widgets.progress_bar import ProgressBar

        bar = ProgressBar(total=10, reviewed=5)
        content = bar.get_content_text()

        assert "50" in content or "%" in content


class TestStatsPanelInit:
    """Test StatsPanel initialization."""

    def test_stats_panel_can_be_instantiated(self):
        """Test that StatsPanel can be instantiated."""
        from src.ui.tui.widgets.stats_panel import StatsPanel

        panel = StatsPanel()

        assert panel is not None

    def test_stats_panel_with_initial_stats(self):
        """Test StatsPanel with initial stats."""
        from src.ui.tui.widgets.stats_panel import StatsPanel

        panel = StatsPanel(
            accepted=5,
            renamed=2,
            merged=1,
            deleted=3
        )

        assert panel.accepted == 5
        assert panel.renamed == 2
        assert panel.merged == 1
        assert panel.deleted == 3

    def test_stats_panel_default_values(self):
        """Test StatsPanel has default zero values."""
        from src.ui.tui.widgets.stats_panel import StatsPanel

        panel = StatsPanel()

        assert panel.accepted == 0
        assert panel.renamed == 0
        assert panel.merged == 0
        assert panel.deleted == 0


class TestStatsPanelUpdate:
    """Test StatsPanel update methods."""

    def test_stats_panel_increment_accepted(self):
        """Test incrementing accepted count."""
        from src.ui.tui.widgets.stats_panel import StatsPanel

        panel = StatsPanel()
        panel.increment_accepted()

        assert panel.accepted == 1

    def test_stats_panel_increment_renamed(self):
        """Test incrementing renamed count."""
        from src.ui.tui.widgets.stats_panel import StatsPanel

        panel = StatsPanel()
        panel.increment_renamed()

        assert panel.renamed == 1

    def test_stats_panel_increment_merged(self):
        """Test incrementing merged count."""
        from src.ui.tui.widgets.stats_panel import StatsPanel

        panel = StatsPanel()
        panel.increment_merged()

        assert panel.merged == 1

    def test_stats_panel_increment_deleted(self):
        """Test incrementing deleted count."""
        from src.ui.tui.widgets.stats_panel import StatsPanel

        panel = StatsPanel()
        panel.increment_deleted()

        assert panel.deleted == 1

    def test_stats_panel_reset(self):
        """Test resetting all stats."""
        from src.ui.tui.widgets.stats_panel import StatsPanel

        panel = StatsPanel(accepted=5, renamed=2, merged=1, deleted=3)
        panel.reset()

        assert panel.accepted == 0
        assert panel.renamed == 0
        assert panel.merged == 0
        assert panel.deleted == 0


class TestStatsPanelDisplay:
    """Test StatsPanel display content."""

    def test_stats_panel_shows_accepted(self):
        """Test that stats panel shows accepted count."""
        from src.ui.tui.widgets.stats_panel import StatsPanel

        panel = StatsPanel(accepted=5)
        content = panel.get_content_text()

        assert "5" in content
        assert "accept" in content.lower() or "Accepted" in content

    def test_stats_panel_shows_renamed(self):
        """Test that stats panel shows renamed count."""
        from src.ui.tui.widgets.stats_panel import StatsPanel

        panel = StatsPanel(renamed=3)
        content = panel.get_content_text()

        assert "3" in content
        assert "rename" in content.lower() or "Renamed" in content

    def test_stats_panel_shows_merged(self):
        """Test that stats panel shows merged count."""
        from src.ui.tui.widgets.stats_panel import StatsPanel

        panel = StatsPanel(merged=2)
        content = panel.get_content_text()

        assert "2" in content
        assert "merge" in content.lower() or "Merged" in content

    def test_stats_panel_shows_deleted(self):
        """Test that stats panel shows deleted count."""
        from src.ui.tui.widgets.stats_panel import StatsPanel

        panel = StatsPanel(deleted=4)
        content = panel.get_content_text()

        assert "4" in content
        assert "delete" in content.lower() or "Deleted" in content


class TestStatsPanelTotal:
    """Test StatsPanel total calculation."""

    def test_stats_panel_total_actions(self):
        """Test calculating total actions."""
        from src.ui.tui.widgets.stats_panel import StatsPanel

        panel = StatsPanel(accepted=5, renamed=2, merged=1, deleted=3)

        assert panel.total_actions == 11

    def test_stats_panel_total_actions_zero(self):
        """Test total actions when all zero."""
        from src.ui.tui.widgets.stats_panel import StatsPanel

        panel = StatsPanel()

        assert panel.total_actions == 0


class TestStatsPanelFromStats:
    """Test StatsPanel creation from stats dict."""

    def test_stats_panel_from_dict(self):
        """Test creating StatsPanel from stats dict."""
        from src.ui.tui.widgets.stats_panel import StatsPanel

        stats = {
            "approved": 5,
            "modified": 2,
            "merged": 1,
            "deleted": 3,
        }

        panel = StatsPanel.from_stats(stats)

        assert panel.accepted == 5
        assert panel.renamed == 2
        assert panel.merged == 1
        assert panel.deleted == 3


class TestWidgetsPackageExports:
    """Test that widgets package exports the new widgets."""

    def test_package_exports_progress_bar(self):
        """Test that package exports ProgressBar."""
        from src.ui.tui.widgets import ProgressBar

        assert ProgressBar is not None

    def test_package_exports_stats_panel(self):
        """Test that package exports StatsPanel."""
        from src.ui.tui.widgets import StatsPanel

        assert StatsPanel is not None
