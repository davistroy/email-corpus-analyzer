"""
Unit tests for StatsPanel wiring into the TUI layout (Phase 2, Item 1.2).

Tests:
- StatsPanel renders with zero counts
- StatsPanel shows pending/approved/skipped/deleted counters
- StatsPanel shows session timer
- Counters increment correctly for each action type
- Panel updates reactively when ReviewState changes
- StatsPanel is present in ReviewApp compose output
- update_from_state() synchronizes panel with ReviewState
"""

from unittest.mock import MagicMock, patch

from src.models.category import Category, CategorySource


def make_category(
    category_id: str = "cat_1",
    name: str = "Test Category",
    confidence: float = 0.85,
    email_count: int = 10,
    source: CategorySource = CategorySource.CONTENT_CLUSTER,
) -> Category:
    """Helper to create test Category objects."""
    return Category(
        category_id=category_id,
        category_name=name,
        description=f"Description for {name}",
        confidence=confidence,
        email_count=email_count,
        percentage=25.0,
        source=source,
        source_id="test_source",
        example_email_ids=[],
        distinguishing_features=[],
    )


# ---------------------------------------------------------------------------
# StatsPanel rendering with zero counts
# ---------------------------------------------------------------------------


class TestStatsPanelZeroCounts:
    """StatsPanel renders correctly with all-zero counts."""

    def test_renders_with_zero_counts(self):
        """Panel displays zero for all counters at initialization."""
        from src.ui.tui.widgets.stats_panel import StatsPanel

        panel = StatsPanel()
        content = panel.get_content_text()

        # All counters should show 0
        assert "0" in content

    def test_zero_counts_shows_pending_label(self):
        """Panel shows a 'Pending' label."""
        from src.ui.tui.widgets.stats_panel import StatsPanel

        panel = StatsPanel()
        content = panel.get_content_text()

        assert "pending" in content.lower() or "Pending" in content

    def test_zero_counts_shows_approved_label(self):
        """Panel shows an 'Approved' label."""
        from src.ui.tui.widgets.stats_panel import StatsPanel

        panel = StatsPanel()
        content = panel.get_content_text()

        assert "approved" in content.lower() or "Accepted" in content

    def test_zero_counts_shows_skipped_label(self):
        """Panel shows a 'Skipped' label."""
        from src.ui.tui.widgets.stats_panel import StatsPanel

        panel = StatsPanel()
        content = panel.get_content_text()

        assert "skipped" in content.lower() or "Skipped" in content

    def test_zero_counts_shows_deleted_label(self):
        """Panel shows a 'Deleted' label."""
        from src.ui.tui.widgets.stats_panel import StatsPanel

        panel = StatsPanel()
        content = panel.get_content_text()

        assert "deleted" in content.lower() or "Deleted" in content


# ---------------------------------------------------------------------------
# StatsPanel session timer
# ---------------------------------------------------------------------------


class TestStatsPanelSessionTimer:
    """StatsPanel shows an elapsed session timer."""

    def test_has_session_start_time(self):
        """Panel records a session start time."""
        from src.ui.tui.widgets.stats_panel import StatsPanel

        panel = StatsPanel()
        assert hasattr(panel, "_session_start")
        assert panel._session_start is not None

    def test_elapsed_seconds_returns_non_negative(self):
        """elapsed_seconds returns a non-negative value."""
        from src.ui.tui.widgets.stats_panel import StatsPanel

        panel = StatsPanel()
        elapsed = panel.elapsed_seconds
        assert elapsed >= 0.0

    def test_format_elapsed_time_zero(self):
        """Format elapsed time for 0 seconds."""
        from src.ui.tui.widgets.stats_panel import StatsPanel

        panel = StatsPanel()
        formatted = panel._format_elapsed(0)
        assert formatted == "0:00"

    def test_format_elapsed_time_seconds(self):
        """Format elapsed time for seconds only."""
        from src.ui.tui.widgets.stats_panel import StatsPanel

        panel = StatsPanel()
        formatted = panel._format_elapsed(45)
        assert formatted == "0:45"

    def test_format_elapsed_time_minutes(self):
        """Format elapsed time for minutes and seconds."""
        from src.ui.tui.widgets.stats_panel import StatsPanel

        panel = StatsPanel()
        formatted = panel._format_elapsed(125)
        assert formatted == "2:05"

    def test_format_elapsed_time_hours(self):
        """Format elapsed time for hours, minutes, and seconds."""
        from src.ui.tui.widgets.stats_panel import StatsPanel

        panel = StatsPanel()
        formatted = panel._format_elapsed(3661)
        assert formatted == "1:01:01"

    def test_content_includes_timer_label(self):
        """Panel content includes a timer/elapsed label."""
        from src.ui.tui.widgets.stats_panel import StatsPanel

        panel = StatsPanel()
        content = panel.get_content_text()

        assert (
            "elapsed" in content.lower() or "timer" in content.lower() or "time" in content.lower()
        )


# ---------------------------------------------------------------------------
# StatsPanel update_from_state
# ---------------------------------------------------------------------------


class TestStatsPanelUpdateFromState:
    """StatsPanel synchronizes with ReviewState via update_from_state()."""

    def test_update_from_state_sets_pending_count(self):
        """update_from_state sets the pending counter from state."""
        from src.ui.tui.state import ReviewState
        from src.ui.tui.widgets.stats_panel import StatsPanel

        state = ReviewState(
            categories=[make_category("c1"), make_category("c2"), make_category("c3")]
        )
        panel = StatsPanel()

        panel.update_from_state(state)
        assert panel.pending == 3

    def test_update_from_state_sets_approved_count(self):
        """update_from_state sets the accepted counter after an accept."""
        from src.ui.tui.state import ReviewState
        from src.ui.tui.widgets.stats_panel import StatsPanel

        state = ReviewState(categories=[make_category("c1"), make_category("c2")])
        state.accept("c1")

        panel = StatsPanel()
        panel.update_from_state(state)

        assert panel.accepted == 1
        assert panel.pending == 1

    def test_update_from_state_sets_skipped_count(self):
        """update_from_state sets the skipped counter after a skip."""
        from src.ui.tui.state import ReviewState
        from src.ui.tui.widgets.stats_panel import StatsPanel

        state = ReviewState(categories=[make_category("c1"), make_category("c2")])
        state.skip("c1")

        panel = StatsPanel()
        panel.update_from_state(state)

        assert panel.skipped == 1

    def test_update_from_state_sets_deleted_count(self):
        """update_from_state sets the deleted counter after a delete."""
        from src.ui.tui.state import ReviewState
        from src.ui.tui.widgets.stats_panel import StatsPanel

        state = ReviewState(categories=[make_category("c1"), make_category("c2")])
        state.delete("c1")

        panel = StatsPanel()
        panel.update_from_state(state)

        assert panel.deleted == 1

    def test_update_from_state_sets_renamed_count(self):
        """update_from_state sets the renamed counter after a rename."""
        from src.ui.tui.state import ReviewState
        from src.ui.tui.widgets.stats_panel import StatsPanel

        state = ReviewState(categories=[make_category("c1"), make_category("c2")])
        state.rename("c1", "New Name")

        panel = StatsPanel()
        panel.update_from_state(state)

        assert panel.renamed == 1

    def test_update_from_state_sets_merged_count(self):
        """update_from_state sets the merged counter after a merge."""
        from src.ui.tui.state import ReviewState
        from src.ui.tui.widgets.stats_panel import StatsPanel

        state = ReviewState(categories=[make_category("c1"), make_category("c2")])
        state.accept("c2")  # Must have approved target first
        state.merge("c1", "c2")

        panel = StatsPanel()
        panel.update_from_state(state)

        assert panel.merged == 1

    def test_update_from_state_sets_total(self):
        """update_from_state sets total_categories from state."""
        from src.ui.tui.state import ReviewState
        from src.ui.tui.widgets.stats_panel import StatsPanel

        state = ReviewState(
            categories=[make_category("c1"), make_category("c2"), make_category("c3")]
        )
        panel = StatsPanel()
        panel.update_from_state(state)

        assert panel.total == 3


# ---------------------------------------------------------------------------
# Counter increments for each action type
# ---------------------------------------------------------------------------


class TestStatsPanelCounterIncrements:
    """Counters increment correctly for each action type through update_from_state."""

    def test_accept_increments_accepted(self):
        """Accepting a category increments the accepted counter."""
        from src.ui.tui.state import ReviewState
        from src.ui.tui.widgets.stats_panel import StatsPanel

        state = ReviewState(categories=[make_category("c1"), make_category("c2")])
        panel = StatsPanel()

        state.accept("c1")
        panel.update_from_state(state)
        assert panel.accepted == 1

        state.accept("c2")
        panel.update_from_state(state)
        assert panel.accepted == 2

    def test_skip_increments_skipped(self):
        """Skipping a category increments the skipped counter."""
        from src.ui.tui.state import ReviewState
        from src.ui.tui.widgets.stats_panel import StatsPanel

        state = ReviewState(categories=[make_category("c1"), make_category("c2")])
        panel = StatsPanel()

        state.skip("c1")
        panel.update_from_state(state)
        assert panel.skipped == 1

    def test_delete_increments_deleted(self):
        """Deleting a category increments the deleted counter."""
        from src.ui.tui.state import ReviewState
        from src.ui.tui.widgets.stats_panel import StatsPanel

        state = ReviewState(categories=[make_category("c1"), make_category("c2")])
        panel = StatsPanel()

        state.delete("c1")
        panel.update_from_state(state)
        assert panel.deleted == 1

    def test_rename_increments_renamed(self):
        """Renaming a category increments the renamed counter."""
        from src.ui.tui.state import ReviewState
        from src.ui.tui.widgets.stats_panel import StatsPanel

        state = ReviewState(categories=[make_category("c1"), make_category("c2")])
        panel = StatsPanel()

        state.rename("c1", "Renamed")
        panel.update_from_state(state)
        assert panel.renamed == 1

    def test_merge_increments_merged(self):
        """Merging categories increments the merged counter."""
        from src.ui.tui.state import ReviewState
        from src.ui.tui.widgets.stats_panel import StatsPanel

        state = ReviewState(
            categories=[make_category("c1"), make_category("c2"), make_category("c3")]
        )
        panel = StatsPanel()

        state.accept("c2")
        state.merge("c1", "c2")
        panel.update_from_state(state)
        assert panel.merged == 1


# ---------------------------------------------------------------------------
# Reactive updates (on_change callback triggers panel update)
# ---------------------------------------------------------------------------


class TestStatsPanelReactiveUpdates:
    """Panel updates reactively when ReviewState fires on_change."""

    def test_state_on_change_callback_called(self):
        """State fires on_change when an action occurs."""
        from src.ui.tui.state import ReviewState

        state = ReviewState(categories=[make_category("c1")])
        callback = MagicMock()
        state.on_change = callback

        state.accept("c1")
        callback.assert_called_once()

    def test_wiring_on_change_to_update_from_state(self):
        """Wiring on_change to panel.update_from_state keeps panel in sync."""
        from src.ui.tui.state import ReviewState
        from src.ui.tui.widgets.stats_panel import StatsPanel

        state = ReviewState(categories=[make_category("c1"), make_category("c2")])
        panel = StatsPanel()
        panel.update_from_state(state)  # initial sync

        # Wire the callback
        state.on_change = lambda _event: panel.update_from_state(state)

        state.accept("c1")
        assert panel.accepted == 1
        assert panel.pending == 1

        state.delete("c2")
        assert panel.deleted == 1
        assert panel.pending == 0


# ---------------------------------------------------------------------------
# StatsPanel content display with real data
# ---------------------------------------------------------------------------


class TestStatsPanelContentDisplay:
    """StatsPanel get_content_text includes all relevant information."""

    def test_content_shows_pending_count(self):
        """Content text includes the pending count."""
        from src.ui.tui.state import ReviewState
        from src.ui.tui.widgets.stats_panel import StatsPanel

        state = ReviewState(categories=[make_category("c1"), make_category("c2")])
        panel = StatsPanel()
        panel.update_from_state(state)
        content = panel.get_content_text()

        assert "2" in content  # 2 pending

    def test_content_shows_total_categories(self):
        """Content text includes the total category count."""
        from src.ui.tui.state import ReviewState
        from src.ui.tui.widgets.stats_panel import StatsPanel

        state = ReviewState(
            categories=[make_category("c1"), make_category("c2"), make_category("c3")]
        )
        panel = StatsPanel()
        panel.update_from_state(state)
        content = panel.get_content_text()

        assert "3" in content  # 3 total

    def test_content_after_actions_shows_updated_counts(self):
        """Content reflects updated counts after actions."""
        from src.ui.tui.state import ReviewState
        from src.ui.tui.widgets.stats_panel import StatsPanel

        state = ReviewState(
            categories=[
                make_category("c1"),
                make_category("c2"),
                make_category("c3"),
                make_category("c4"),
            ]
        )
        panel = StatsPanel()

        state.accept("c1")
        state.skip("c2")
        state.delete("c3")
        panel.update_from_state(state)

        content = panel.get_content_text()
        # accepted=1, skipped=1, deleted=1, pending=1
        assert "1" in content  # at least one counter is 1


# ---------------------------------------------------------------------------
# StatsPanel wired into ReviewApp layout
# ---------------------------------------------------------------------------


class TestStatsPanelInLayout:
    """StatsPanel is included in ReviewApp's compose output."""

    def test_app_compose_includes_stats_panel_import(self):
        """ReviewApp imports StatsPanel."""
        import src.ui.tui.app as app_module

        assert hasattr(app_module, "StatsPanel") or "StatsPanel" in dir(app_module)

    def test_app_has_update_stats_panel_method(self):
        """ReviewApp has a method to update the stats panel."""
        from src.ui.tui.app import ReviewApp

        app = ReviewApp(categories=[make_category()])
        assert hasattr(app, "_update_stats_panel")

    def test_refresh_all_widgets_includes_stats_update(self):
        """_refresh_all_widgets also updates the stats panel."""
        from src.ui.tui.app import ReviewApp

        app = ReviewApp(categories=[make_category()])

        # Patch _update_stats_panel to verify it's called
        with (
            patch.object(app, "_update_stats_panel") as mock_update,
            patch.object(app, "_update_table"),
            patch.object(app, "_update_detail_panel"),
            patch.object(app, "_update_action_bar"),
        ):
            app._refresh_all_widgets()

        mock_update.assert_called_once()


# ---------------------------------------------------------------------------
# StatsPanel backward compatibility
# ---------------------------------------------------------------------------


class TestStatsPanelBackwardCompat:
    """Existing StatsPanel API still works (no regressions)."""

    def test_increment_accepted_still_works(self):
        """Existing increment_accepted method still works."""
        from src.ui.tui.widgets.stats_panel import StatsPanel

        panel = StatsPanel()
        panel.increment_accepted()
        assert panel.accepted == 1

    def test_increment_renamed_still_works(self):
        """Existing increment_renamed method still works."""
        from src.ui.tui.widgets.stats_panel import StatsPanel

        panel = StatsPanel()
        panel.increment_renamed()
        assert panel.renamed == 1

    def test_increment_merged_still_works(self):
        """Existing increment_merged method still works."""
        from src.ui.tui.widgets.stats_panel import StatsPanel

        panel = StatsPanel()
        panel.increment_merged()
        assert panel.merged == 1

    def test_increment_deleted_still_works(self):
        """Existing increment_deleted method still works."""
        from src.ui.tui.widgets.stats_panel import StatsPanel

        panel = StatsPanel()
        panel.increment_deleted()
        assert panel.deleted == 1

    def test_reset_still_works(self):
        """Existing reset method still works."""
        from src.ui.tui.widgets.stats_panel import StatsPanel

        panel = StatsPanel(accepted=5, renamed=2, merged=1, deleted=3)
        panel.reset()
        assert panel.total_actions == 0

    def test_from_stats_still_works(self):
        """Existing from_stats class method still works."""
        from src.ui.tui.widgets.stats_panel import StatsPanel

        stats = {"approved": 5, "modified": 2, "merged": 1, "deleted": 3}
        panel = StatsPanel.from_stats(stats)
        assert panel.accepted == 5
        assert panel.renamed == 2

    def test_total_actions_still_works(self):
        """Existing total_actions property still works."""
        from src.ui.tui.widgets.stats_panel import StatsPanel

        panel = StatsPanel(accepted=5, renamed=2, merged=1, deleted=3)
        assert panel.total_actions == 11
