"""
Integration tests: ReviewApp uses ReviewState as single source of truth.

Verifies that app.py delegates all state management to ReviewState
and that the existing app API surface remains compatible.
"""

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


class TestAppUsesReviewState:
    """Verify ReviewApp delegates to ReviewState."""

    def test_app_has_state_attribute(self):
        """ReviewApp has a .state attribute of type ReviewState."""
        from src.ui.tui.app import ReviewApp
        from src.ui.tui.state import ReviewState

        app = ReviewApp(categories=[make_category()])
        assert hasattr(app, "state")
        assert isinstance(app.state, ReviewState)

    def test_app_state_initialized_with_categories(self):
        """ReviewState is initialized with the same categories passed to the app."""
        from src.ui.tui.app import ReviewApp

        cats = [make_category("c1"), make_category("c2")]
        app = ReviewApp(categories=cats)

        assert len(app.state.pending) == 2

    def test_app_categories_property_delegates_to_state(self):
        """app.categories returns state.pending."""
        from src.ui.tui.app import ReviewApp

        cats = [make_category("c1"), make_category("c2")]
        app = ReviewApp(categories=cats)

        assert app.categories == app.state.pending

    def test_app_approved_categories_delegates_to_state(self):
        """app.approved_categories returns state.approved."""
        from src.ui.tui.app import ReviewApp

        app = ReviewApp(categories=[make_category("c1")])
        app.state.accept("c1")

        assert len(app.approved_categories) == 1
        assert app.approved_categories == app.state.approved

    def test_app_skipped_categories_delegates_to_state(self):
        """app.skipped_categories returns state.skipped."""
        from src.ui.tui.app import ReviewApp

        app = ReviewApp(categories=[make_category("c1")])
        app.state.skip("c1")

        assert len(app.skipped_categories) == 1

    def test_app_get_selected_category_delegates_to_state(self):
        """get_selected_category returns state.selected_category."""
        from src.ui.tui.app import ReviewApp

        cats = [make_category("c1"), make_category("c2")]
        app = ReviewApp(categories=cats)
        app.state.selected_index = 1

        selected = app.get_selected_category()
        assert selected is not None
        assert selected.category_id == "c2"

    def test_app_get_approved_categories_returns_copy(self):
        """get_approved_categories returns a copy, not a reference."""
        from src.ui.tui.app import ReviewApp

        app = ReviewApp(categories=[make_category("c1")])
        app.state.accept("c1")

        result = app.get_approved_categories()
        result.append(make_category("extra"))
        assert len(app.state.approved) == 1

    def test_app_get_stats_delegates_to_state(self):
        """get_stats returns data from state."""
        from src.ui.tui.app import ReviewApp

        cats = [make_category("c1"), make_category("c2")]
        app = ReviewApp(categories=cats)
        app.state.accept("c1")

        stats = app.get_stats()
        # Must have the keys the existing tests expect
        assert "approved" in stats
        assert "remaining" in stats

    def test_backward_compat_modified_count(self):
        """modified_count (renamed counter) is accessible."""
        from src.ui.tui.app import ReviewApp

        app = ReviewApp(categories=[make_category("c1")])
        app.state.rename("c1", "New Name")

        assert app.modified_count == 1

    def test_backward_compat_merged_count(self):
        """merged_count is accessible."""
        from src.ui.tui.app import ReviewApp

        target = make_category("t1", email_count=5)
        source = make_category("s1", email_count=3)
        app = ReviewApp(categories=[source])
        app.state._approved.append(target)
        app.state.merge("s1", "t1")

        assert app.merged_count == 1

    def test_backward_compat_deleted_count(self):
        """deleted_count is accessible."""
        from src.ui.tui.app import ReviewApp

        app = ReviewApp(categories=[make_category("c1")])
        app.state.delete("c1")

        assert app.deleted_count == 1

    def test_backward_compat_selected_index(self):
        """_selected_index is accessible via state."""
        from src.ui.tui.app import ReviewApp

        cats = [make_category("c1"), make_category("c2")]
        app = ReviewApp(categories=cats)

        assert app._selected_index == 0

    def test_app_get_selected_returns_none_when_empty(self):
        """get_selected_category returns None for empty categories."""
        from src.ui.tui.app import ReviewApp

        app = ReviewApp(categories=[])
        assert app.get_selected_category() is None

    def test_app_get_selected_returns_none_out_of_bounds(self):
        """get_selected_category returns None for out-of-bounds index."""
        from src.ui.tui.app import ReviewApp

        app = ReviewApp(categories=[make_category()])
        app.state._selected_index = 999

        assert app.get_selected_category() is None


class TestAppGetStatsBackwardCompat:
    """Ensure get_stats returns the keys existing tests expect."""

    def test_get_stats_has_expected_keys(self):
        """get_stats must have: modified, merged, deleted, approved, skipped, remaining."""
        from src.ui.tui.app import ReviewApp

        app = ReviewApp(categories=[make_category()])
        stats = app.get_stats()

        expected_keys = {"modified", "merged", "deleted", "approved", "skipped", "remaining"}
        assert expected_keys.issubset(set(stats.keys()))

    def test_get_stats_values_correct(self):
        """get_stats values match state after actions."""
        from src.ui.tui.app import ReviewApp

        cats = [make_category(f"c{i}") for i in range(4)]
        app = ReviewApp(categories=cats)

        app.state.accept("c0")
        app.state.rename("c1", "Renamed")
        app.state.delete("c2")
        app.state.skip("c3")

        stats = app.get_stats()
        assert stats["modified"] == 1  # renamed
        assert stats["merged"] == 0
        assert stats["deleted"] == 1
        assert stats["approved"] == 2  # accepted + renamed
        assert stats["skipped"] == 1
        assert stats["remaining"] == 0
