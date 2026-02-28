"""
Unit tests for TUI dialog widgets.

Tests the RenameDialog and MergeDialog widgets for Tasks 3B.2 and 3B.3.
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
        distinguishing_features=[],
    )


# === Task 3B.2: Rename Dialog Tests ===


class TestRenameDialogInit:
    """Test RenameDialog initialization."""

    def test_rename_dialog_can_be_instantiated(self):
        """Test that RenameDialog can be instantiated."""
        from src.ui.tui.dialogs import RenameDialog

        dialog = RenameDialog(current_name="Old Name")

        assert dialog is not None

    def test_rename_dialog_stores_current_name(self):
        """Test that dialog stores the current name."""
        from src.ui.tui.dialogs import RenameDialog

        dialog = RenameDialog(current_name="Newsletter Updates")

        assert dialog.current_name == "Newsletter Updates"

    def test_rename_dialog_has_escape_binding(self):
        """Test that dialog has escape key binding for cancel."""
        from src.ui.tui.dialogs import RenameDialog

        dialog = RenameDialog(current_name="Test")

        binding_keys = [b.key for b in dialog.BINDINGS]
        assert "escape" in binding_keys


class TestRenameDialogValidation:
    """Test RenameDialog name validation."""

    def test_rename_dialog_validate_empty_name(self):
        """Test that empty name is rejected."""
        from src.ui.tui.dialogs import RenameDialog

        dialog = RenameDialog(current_name="Test")

        assert not dialog.validate_name("")
        assert not dialog.validate_name("   ")

    def test_rename_dialog_validate_valid_name(self):
        """Test that valid name passes validation."""
        from src.ui.tui.dialogs import RenameDialog

        dialog = RenameDialog(current_name="Test")

        assert dialog.validate_name("New Category Name")

    def test_rename_dialog_validate_max_length(self):
        """Test that very long names are rejected."""
        from src.ui.tui.dialogs import RenameDialog

        dialog = RenameDialog(current_name="Test")

        long_name = "A" * 200
        assert not dialog.validate_name(long_name)

    def test_rename_dialog_validate_reasonable_length(self):
        """Test that reasonable length names pass."""
        from src.ui.tui.dialogs import RenameDialog

        dialog = RenameDialog(current_name="Test")

        reasonable_name = "This is a reasonable category name"
        assert dialog.validate_name(reasonable_name)


class TestRenameDialogContent:
    """Test RenameDialog content display."""

    def test_rename_dialog_shows_current_name(self):
        """Test that dialog shows the current name."""
        from src.ui.tui.dialogs import RenameDialog

        dialog = RenameDialog(current_name="Newsletter Updates")

        # The compose method should include the current name
        assert dialog.current_name == "Newsletter Updates"

    def test_rename_dialog_has_input_field(self):
        """Test that dialog has an input field."""
        from src.ui.tui.dialogs import RenameDialog

        dialog = RenameDialog(current_name="Test")

        # Dialog should be a ModalScreen
        from textual.screen import ModalScreen

        assert isinstance(dialog, ModalScreen)


class TestRenameDialogActions:
    """Test RenameDialog actions."""

    def test_rename_dialog_has_cancel_action(self):
        """Test that dialog has cancel action."""
        from src.ui.tui.dialogs import RenameDialog

        dialog = RenameDialog(current_name="Test")

        assert hasattr(dialog, "action_cancel")

    def test_rename_dialog_get_validation_error(self):
        """Test getting validation error message."""
        from src.ui.tui.dialogs import RenameDialog

        dialog = RenameDialog(current_name="Test")

        error = dialog.get_validation_error("")
        assert error is not None
        assert len(error) > 0

    def test_rename_dialog_no_error_for_valid_name(self):
        """Test no error for valid name."""
        from src.ui.tui.dialogs import RenameDialog

        dialog = RenameDialog(current_name="Test")

        error = dialog.get_validation_error("Valid Name")
        assert error is None


# === Task 3B.3: Merge Dialog Tests ===


class TestMergeDialogInit:
    """Test MergeDialog initialization."""

    def test_merge_dialog_can_be_instantiated(self):
        """Test that MergeDialog can be instantiated."""
        from src.ui.tui.dialogs import MergeDialog

        categories = [create_test_category()]
        dialog = MergeDialog(categories=categories, source_category=create_test_category())

        assert dialog is not None

    def test_merge_dialog_stores_categories(self):
        """Test that dialog stores available categories."""
        from src.ui.tui.dialogs import MergeDialog

        categories = [
            create_test_category(category_id="cat1", name="Category 1"),
            create_test_category(category_id="cat2", name="Category 2"),
        ]
        source = create_test_category(category_id="source", name="Source")
        dialog = MergeDialog(categories=categories, source_category=source)

        assert len(dialog.merge_categories) == 2

    def test_merge_dialog_stores_source_category(self):
        """Test that dialog stores the source category."""
        from src.ui.tui.dialogs import MergeDialog

        categories = [create_test_category()]
        source = create_test_category(category_id="source", name="Source Category")
        dialog = MergeDialog(categories=categories, source_category=source)

        assert dialog.source_category.category_name == "Source Category"

    def test_merge_dialog_has_escape_binding(self):
        """Test that dialog has escape key binding for cancel."""
        from src.ui.tui.dialogs import MergeDialog

        categories = [create_test_category()]
        dialog = MergeDialog(categories=categories, source_category=create_test_category())

        binding_keys = [b.key for b in dialog.BINDINGS]
        assert "escape" in binding_keys


class TestMergeDialogPreview:
    """Test MergeDialog merge preview."""

    def test_merge_dialog_get_merge_preview(self):
        """Test getting merge preview text."""
        from src.ui.tui.dialogs import MergeDialog

        target = create_test_category(name="Target", email_count=50)
        source = create_test_category(name="Source", email_count=30)
        dialog = MergeDialog(categories=[target], source_category=source)

        preview = dialog.get_merge_preview(target)

        assert preview is not None
        assert "80" in preview  # Combined email count

    def test_merge_dialog_preview_shows_combined_count(self):
        """Test that preview shows combined email count."""
        from src.ui.tui.dialogs import MergeDialog

        target = create_test_category(name="Target", email_count=100)
        source = create_test_category(name="Source", email_count=25)
        dialog = MergeDialog(categories=[target], source_category=source)

        preview = dialog.get_merge_preview(target)

        # Should show 125 total
        assert "125" in preview


class TestMergeDialogSelection:
    """Test MergeDialog category selection."""

    def test_merge_dialog_get_selected_category(self):
        """Test getting selected category for merge."""
        from src.ui.tui.dialogs import MergeDialog

        categories = [
            create_test_category(category_id="cat1", name="Category 1"),
            create_test_category(category_id="cat2", name="Category 2"),
        ]
        source = create_test_category()
        dialog = MergeDialog(categories=categories, source_category=source)
        dialog.selected_index = 1

        selected = dialog.get_selected_category()

        assert selected is not None
        assert selected.category_name == "Category 2"

    def test_merge_dialog_empty_selection(self):
        """Test handling empty selection."""
        from src.ui.tui.dialogs import MergeDialog

        source = create_test_category()
        dialog = MergeDialog(categories=[], source_category=source)

        selected = dialog.get_selected_category()

        assert selected is None


class TestMergeDialogActions:
    """Test MergeDialog actions."""

    def test_merge_dialog_has_cancel_action(self):
        """Test that dialog has cancel action."""
        from src.ui.tui.dialogs import MergeDialog

        categories = [create_test_category()]
        dialog = MergeDialog(categories=categories, source_category=create_test_category())

        assert hasattr(dialog, "action_cancel")


# === Dialog Package Tests ===


class TestDialogsPackageInit:
    """Test dialogs package initialization."""

    def test_package_can_be_imported(self):
        """Test that dialogs package can be imported."""
        from src.ui.tui.dialogs import MergeDialog, RenameDialog

        assert RenameDialog is not None
        assert MergeDialog is not None

    def test_package_exports_rename_dialog(self):
        """Test that package exports RenameDialog."""
        from src.ui.tui import dialogs

        assert hasattr(dialogs, "RenameDialog")

    def test_package_exports_merge_dialog(self):
        """Test that package exports MergeDialog."""
        from src.ui.tui import dialogs

        assert hasattr(dialogs, "MergeDialog")
