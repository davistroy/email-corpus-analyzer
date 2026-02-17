"""
Unit tests for the interactive category review CLI module.

Tests the CategoryReview class and related functions with mocked
user input and file I/O operations.
"""
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.models.category import Category, CategorySource
from src.models.email import Email
from src.ui.category_review import CategoryReview, cleanup_intermediate_files, review_categories


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


def create_test_email(
    email_id: str = "email_1",
    sender_email: str = "sender@example.com",
    sender_name: str = "Test Sender",
    subject: str = "Test Subject",
    body_text: str = "Test body content"
) -> Email:
    """Helper to create test Email objects."""
    return Email(
        id=email_id,
        sender_email=sender_email,
        sender_name=sender_name,
        sender_domain=sender_email.split("@")[1],
        subject=subject,
        body_text=body_text,
        received_date=datetime(2024, 1, 15, 10, 30, 0),
        has_attachments=False
    )


class TestCategoryReviewInit:
    """Test CategoryReview initialization."""

    def test_init_with_categories_only(self):
        """Test initialization with categories but no email lookup."""
        categories = [create_test_category()]
        reviewer = CategoryReview(categories)

        assert reviewer.categories == categories
        assert reviewer.email_lookup == {}
        assert reviewer.approved == []
        assert reviewer.modified_count == 0
        assert reviewer.merged_count == 0
        assert reviewer.deleted_count == 0
        assert reviewer.custom_count == 0
        assert reviewer.skipped == []

    def test_init_with_email_lookup(self):
        """Test initialization with both categories and email lookup."""
        categories = [create_test_category()]
        email = create_test_email()
        email_lookup = {email.id: email}

        reviewer = CategoryReview(categories, email_lookup)

        assert reviewer.categories == categories
        assert reviewer.email_lookup == email_lookup
        assert "email_1" in reviewer.email_lookup

    def test_init_with_empty_categories(self):
        """Test initialization with empty category list."""
        reviewer = CategoryReview([])

        assert reviewer.categories == []
        assert len(reviewer.approved) == 0


class TestReviewCategoryAccept:
    """Test accepting categories in interactive review."""

    @patch("builtins.print")
    @patch("builtins.input")
    def test_accept_category(self, mock_input, mock_print):
        """Test accepting a category with 'A' choice."""
        category = create_test_category(name="Newsletters")
        reviewer = CategoryReview([category])

        mock_input.return_value = "A"
        result = reviewer._review_category(category, 1, 1)

        assert result == "accept"
        assert category in reviewer.approved
        assert len(reviewer.approved) == 1

    @patch("builtins.print")
    @patch("builtins.input")
    def test_accept_lowercase(self, mock_input, mock_print):
        """Test accepting with lowercase 'a'."""
        category = create_test_category()
        reviewer = CategoryReview([category])

        mock_input.return_value = "a"
        result = reviewer._review_category(category, 1, 1)

        assert result == "accept"
        assert category in reviewer.approved

    @patch("builtins.print")
    @patch("builtins.input")
    def test_accept_displays_category_info(self, mock_input, mock_print):
        """Test that category info is displayed before accepting."""
        category = create_test_category(
            name="Important Emails",
            description="High priority messages",
            confidence=0.95,
            email_count=50,
            percentage=12.5
        )
        reviewer = CategoryReview([category])
        mock_input.return_value = "A"

        reviewer._review_category(category, 1, 3)

        # Verify key information was printed
        print_calls = [str(c) for c in mock_print.call_args_list]
        all_output = " ".join(print_calls)

        assert "Important Emails" in all_output
        assert "High priority messages" in all_output
        assert "95.0%" in all_output
        assert "50" in all_output


class TestReviewCategoryRename:
    """Test renaming categories in interactive review."""

    @patch("builtins.print")
    @patch("builtins.input")
    def test_rename_category(self, mock_input, mock_print):
        """Test renaming a category."""
        category = create_test_category(name="Old Name")
        reviewer = CategoryReview([category])

        mock_input.side_effect = ["R", "New Name"]
        result = reviewer._review_category(category, 1, 1)

        assert result == "rename"
        assert category.category_name == "New Name"
        assert category.user_modified is True
        assert category in reviewer.approved
        assert reviewer.modified_count == 1

    @patch("builtins.print")
    @patch("builtins.input")
    def test_rename_with_empty_name_invalid(self, mock_input, mock_print):
        """Test that empty name is rejected and prompts again."""
        category = create_test_category(name="Original Name")
        reviewer = CategoryReview([category])

        # First try empty name, then valid name
        mock_input.side_effect = ["R", "", "A"]
        result = reviewer._review_category(category, 1, 1)

        # Should accept after invalid rename attempt
        assert result == "accept"
        assert category.category_name == "Original Name"  # Not changed
        assert reviewer.modified_count == 0

    @patch("builtins.print")
    @patch("builtins.input")
    def test_rename_with_whitespace_only_invalid(self, mock_input, mock_print):
        """Test that whitespace-only name is rejected."""
        category = create_test_category(name="Original")
        reviewer = CategoryReview([category])

        mock_input.side_effect = ["R", "   ", "A"]
        result = reviewer._review_category(category, 1, 1)

        assert result == "accept"
        assert category.category_name == "Original"


class TestReviewCategoryMerge:
    """Test merging categories in interactive review."""

    @patch("builtins.print")
    @patch("builtins.input")
    def test_merge_category(self, mock_input, mock_print):
        """Test merging a category into an existing approved one."""
        target_category = create_test_category(
            category_id="target",
            name="Target Category",
            email_count=20,
            example_email_ids=["email_1", "email_2"]
        )
        source_category = create_test_category(
            category_id="source",
            name="Source Category",
            email_count=15,
            example_email_ids=["email_3", "email_4"]
        )

        reviewer = CategoryReview([target_category, source_category])
        reviewer.approved = [target_category]  # Pre-approve target

        mock_input.side_effect = ["M", "1"]
        result = reviewer._review_category(source_category, 2, 2)

        assert result == "merge"
        assert reviewer.merged_count == 1
        # Email count should be combined
        assert target_category.email_count == 35
        assert target_category.user_modified is True

    @patch("builtins.print")
    @patch("builtins.input")
    def test_merge_no_approved_categories(self, mock_input, mock_print):
        """Test merge fails gracefully when no approved categories exist."""
        category = create_test_category()
        reviewer = CategoryReview([category])

        # Try to merge, but no approved categories - should continue prompt
        mock_input.side_effect = ["M", "A"]
        result = reviewer._review_category(category, 1, 1)

        assert result == "accept"
        assert reviewer.merged_count == 0

    @patch("builtins.print")
    @patch("builtins.input")
    def test_merge_cancel_with_zero(self, mock_input, mock_print):
        """Test canceling merge with 0."""
        target = create_test_category(name="Target")
        source = create_test_category(name="Source")
        reviewer = CategoryReview([target, source])
        reviewer.approved = [target]

        mock_input.side_effect = ["M", "0", "A"]  # Cancel merge, then accept
        result = reviewer._review_category(source, 2, 2)

        assert result == "accept"
        assert reviewer.merged_count == 0

    @patch("builtins.print")
    @patch("builtins.input")
    def test_merge_invalid_index(self, mock_input, mock_print):
        """Test merge with invalid category index."""
        target = create_test_category(name="Target")
        source = create_test_category(name="Source")
        reviewer = CategoryReview([target, source])
        reviewer.approved = [target]

        mock_input.side_effect = ["M", "99", "A"]  # Invalid index, then accept
        result = reviewer._review_category(source, 2, 2)

        assert result == "accept"
        assert reviewer.merged_count == 0

    @patch("builtins.print")
    @patch("builtins.input")
    def test_merge_non_numeric_input(self, mock_input, mock_print):
        """Test merge with non-numeric input."""
        target = create_test_category(name="Target")
        source = create_test_category(name="Source")
        reviewer = CategoryReview([target, source])
        reviewer.approved = [target]

        mock_input.side_effect = ["M", "abc", "A"]
        result = reviewer._review_category(source, 2, 2)

        assert result == "accept"
        assert reviewer.merged_count == 0


class TestReviewCategoryDelete:
    """Test deleting categories in interactive review."""

    @patch("builtins.print")
    @patch("builtins.input")
    def test_delete_category_confirmed(self, mock_input, mock_print):
        """Test deleting a category with confirmation."""
        category = create_test_category(name="To Delete")
        reviewer = CategoryReview([category])

        mock_input.side_effect = ["D", "y"]
        result = reviewer._review_category(category, 1, 1)

        assert result == "delete"
        assert category not in reviewer.approved
        assert reviewer.deleted_count == 1

    @patch("builtins.print")
    @patch("builtins.input")
    def test_delete_category_cancelled(self, mock_input, mock_print):
        """Test canceling category deletion."""
        category = create_test_category(name="Keep This")
        reviewer = CategoryReview([category])

        mock_input.side_effect = ["D", "n", "A"]  # Cancel delete, then accept
        result = reviewer._review_category(category, 1, 1)

        assert result == "accept"
        assert reviewer.deleted_count == 0
        assert category in reviewer.approved


class TestReviewCategorySkip:
    """Test skipping categories in interactive review."""

    @patch("builtins.print")
    @patch("builtins.input")
    def test_skip_category_first_pass(self, mock_input, mock_print):
        """Test skipping a category on first pass."""
        category = create_test_category(name="Skip Me")
        reviewer = CategoryReview([category])

        mock_input.return_value = "S"
        result = reviewer._review_category(category, 1, 1, is_retry=False)

        assert result == "skip"
        assert category in reviewer.skipped
        assert category not in reviewer.approved

    @patch("builtins.print")
    @patch("builtins.input")
    def test_skip_category_on_retry(self, mock_input, mock_print):
        """Test skipping on retry (will auto-accept)."""
        category = create_test_category(name="Skip Again")
        reviewer = CategoryReview([category])

        mock_input.return_value = "S"
        result = reviewer._review_category(category, 1, 1, is_retry=True)

        assert result == "skip"
        # On retry, should NOT add to skipped again
        assert category not in reviewer.skipped


class TestReviewCategoryInvalidInput:
    """Test handling of invalid user input."""

    @patch("builtins.print")
    @patch("builtins.input")
    def test_invalid_choice_prompts_again(self, mock_input, mock_print):
        """Test that invalid choice prompts for input again."""
        category = create_test_category()
        reviewer = CategoryReview([category])

        mock_input.side_effect = ["X", "Z", "invalid", "A"]
        result = reviewer._review_category(category, 1, 1)

        assert result == "accept"
        # Should have prompted multiple times
        assert mock_input.call_count == 4


class TestReviewCategorySampleDisplay:
    """Test displaying sample emails for categories."""

    @patch("builtins.print")
    @patch("builtins.input")
    def test_display_sample_emails(self, mock_input, mock_print):
        """Test that sample emails are displayed when available."""
        email1 = create_test_email("email_1", "alice@example.com", "Alice", "Hello")
        email2 = create_test_email("email_2", "bob@example.com", "Bob", "World")

        category = create_test_category(example_email_ids=["email_1", "email_2"])
        email_lookup = {"email_1": email1, "email_2": email2}
        reviewer = CategoryReview([category], email_lookup)

        mock_input.return_value = "A"
        reviewer._review_category(category, 1, 1)

        print_calls = [str(c) for c in mock_print.call_args_list]
        all_output = " ".join(print_calls)

        assert "alice@example.com" in all_output
        assert "bob@example.com" in all_output

    @patch("builtins.print")
    @patch("builtins.input")
    def test_display_distinguishing_features_fallback(self, mock_input, mock_print):
        """Test fallback to distinguishing features when no email lookup."""
        category = create_test_category(
            example_email_ids=["email_1"],
            distinguishing_features=["Contains invoice data", "Monthly billing"]
        )
        reviewer = CategoryReview([category], {})  # Empty email lookup

        mock_input.return_value = "A"
        reviewer._review_category(category, 1, 1)

        print_calls = [str(c) for c in mock_print.call_args_list]
        all_output = " ".join(print_calls)

        assert "Contains invoice data" in all_output
        assert "Monthly billing" in all_output

    @patch("builtins.print")
    @patch("builtins.input")
    def test_truncate_long_features(self, mock_input, mock_print):
        """Test that long distinguishing features are truncated."""
        long_feature = "A" * 100  # 100 characters
        category = create_test_category(
            example_email_ids=[],
            distinguishing_features=[long_feature]
        )
        reviewer = CategoryReview([category])

        mock_input.return_value = "A"
        reviewer._review_category(category, 1, 1)

        print_calls = [str(c) for c in mock_print.call_args_list]
        all_output = " ".join(print_calls)

        # Should be truncated with ellipsis
        assert "..." in all_output


class TestRunInteractiveReview:
    """Test the main interactive review loop."""

    @patch("builtins.print")
    @patch("builtins.input")
    def test_review_all_accept(self, mock_input, mock_print):
        """Test reviewing all categories and accepting all."""
        cat1 = create_test_category(category_id="cat1", name="Category 1")
        cat2 = create_test_category(category_id="cat2", name="Category 2")
        reviewer = CategoryReview([cat1, cat2])

        # Accept both categories, decline custom categories
        mock_input.side_effect = ["A", "A", "n"]
        approved = reviewer.run_interactive_review()

        assert len(approved) == 2
        assert cat1 in approved
        assert cat2 in approved

    @patch("builtins.print")
    @patch("builtins.input")
    def test_review_with_skip_and_retry(self, mock_input, mock_print):
        """Test that skipped categories are re-presented."""
        cat1 = create_test_category(category_id="cat1", name="Category 1")
        cat2 = create_test_category(category_id="cat2", name="Category 2")
        reviewer = CategoryReview([cat1, cat2])

        # Skip first, accept second, then accept first on retry, decline custom
        mock_input.side_effect = ["S", "A", "A", "n"]
        approved = reviewer.run_interactive_review()

        assert len(approved) == 2

    @patch("builtins.print")
    @patch("builtins.input")
    def test_skipped_auto_accept_on_second_skip(self, mock_input, mock_print):
        """Test that categories skipped twice are auto-accepted."""
        category = create_test_category(name="Skipped Category")
        reviewer = CategoryReview([category])

        # Skip on first pass, skip on retry (auto-accept), decline custom
        mock_input.side_effect = ["S", "S", "n"]
        approved = reviewer.run_interactive_review()

        assert len(approved) == 1
        assert category in approved

    @patch("builtins.print")
    @patch("builtins.input")
    def test_review_empty_category_list(self, mock_input, mock_print):
        """Test reviewing empty category list."""
        reviewer = CategoryReview([])

        mock_input.return_value = "n"  # No custom categories
        approved = reviewer.run_interactive_review()

        assert approved == []


class TestAddCustomCategories:
    """Test adding custom categories during review."""

    @patch("builtins.print")
    @patch("builtins.input")
    def test_add_single_custom_category(self, mock_input, mock_print):
        """Test adding a single custom category."""
        reviewer = CategoryReview([])

        # Yes to custom, name, description, then empty to finish, decline more
        mock_input.side_effect = ["y", "My Custom", "Custom description", "", ""]
        approved = reviewer.run_interactive_review()

        assert len(approved) == 1
        custom = approved[0]
        assert custom.category_name == "My Custom"
        assert custom.description == "Custom description"
        assert custom.source == CategorySource.CUSTOM
        assert custom.confidence == 1.0
        assert custom.user_modified is True
        assert reviewer.custom_count == 1

    @patch("builtins.print")
    @patch("builtins.input")
    def test_add_custom_with_empty_description(self, mock_input, mock_print):
        """Test adding custom category with default description."""
        reviewer = CategoryReview([])

        mock_input.side_effect = ["y", "NoDesc Category", "", ""]
        approved = reviewer.run_interactive_review()

        assert len(approved) == 1
        assert approved[0].description == "Custom category: NoDesc Category"

    @patch("builtins.print")
    @patch("builtins.input")
    def test_add_multiple_custom_categories(self, mock_input, mock_print):
        """Test adding multiple custom categories."""
        reviewer = CategoryReview([])

        mock_input.side_effect = [
            "y",  # Yes to custom
            "First Custom", "First desc",
            "Second Custom", "Second desc",
            ""  # Empty to finish
        ]
        approved = reviewer.run_interactive_review()

        assert len(approved) == 2
        assert reviewer.custom_count == 2

    @patch("builtins.print")
    @patch("builtins.input")
    def test_decline_custom_categories(self, mock_input, mock_print):
        """Test declining to add custom categories."""
        reviewer = CategoryReview([])

        mock_input.return_value = "n"
        approved = reviewer.run_interactive_review()

        assert len(approved) == 0
        assert reviewer.custom_count == 0


class TestSaveApprovedCategories:
    """Test saving approved categories to file."""

    @patch("src.ui.category_review.save_json")
    def test_save_approved_categories(self, mock_save_json):
        """Test saving approved categories generates correct data."""
        cat1 = create_test_category(category_id="cat1", name="Category 1")
        cat2 = create_test_category(category_id="cat2", name="Category 2")
        reviewer = CategoryReview([cat1, cat2])
        reviewer.approved = [cat1, cat2]
        reviewer.modified_count = 1
        reviewer.merged_count = 0
        reviewer.deleted_count = 1
        reviewer.custom_count = 0

        output_path = Path("/tmp/approved_categories.json")
        result = reviewer.save_approved_categories(output_path)

        mock_save_json.assert_called_once()

        # Verify structure
        assert "approval_date" in result
        assert result["total_categories"] == 2
        assert result["processing_stats"]["suggested"] == 2
        assert result["processing_stats"]["modified"] == 1
        assert result["processing_stats"]["deleted"] == 1
        assert len(result["categories"]) == 2

    @patch("src.ui.category_review.save_json")
    def test_save_with_custom_categories(self, mock_save_json):
        """Test that custom categories are counted correctly in stats."""
        original_cat = create_test_category(category_id="cat1")
        custom_cat = create_test_category(
            category_id="custom_1",
            source=CategorySource.CUSTOM
        )

        reviewer = CategoryReview([original_cat])
        reviewer.approved = [original_cat, custom_cat]
        reviewer.custom_count = 1

        result = reviewer.save_approved_categories(Path("/tmp/test.json"))

        # approved_base should exclude custom categories
        assert result["processing_stats"]["approved"] == 1
        assert result["processing_stats"]["custom"] == 1


class TestReviewCategoriesFunction:
    """Test the review_categories() module-level function."""

    @patch("src.ui.category_review.CategoryReview")
    @patch("src.ui.category_review.load_json")
    @patch("src.utils.paths.PathConfig.get_corpus_path")
    @patch("builtins.print")
    def test_review_categories_basic(
        self, mock_print, mock_get_corpus_path, mock_load_json, mock_reviewer_class
    ):
        """Test basic review_categories call."""
        # Setup mocks
        mock_corpus_path = MagicMock()
        mock_corpus_path.exists.return_value = False
        mock_get_corpus_path.return_value = mock_corpus_path

        mock_reviewer = MagicMock()
        mock_reviewer.run_interactive_review.return_value = []
        mock_reviewer_class.return_value = mock_reviewer

        categories = [create_test_category()]
        review_categories(categories)

        mock_reviewer_class.assert_called_once()
        mock_reviewer.run_interactive_review.assert_called_once()

    @patch("src.ui.category_review.CategoryReview")
    @patch("src.ui.category_review.load_json")
    @patch("src.utils.paths.PathConfig.get_corpus_path")
    @patch("builtins.print")
    def test_review_categories_loads_corpus(
        self, mock_print, mock_get_corpus_path, mock_load_json, mock_reviewer_class
    ):
        """Test that review_categories loads email corpus for lookup."""
        mock_corpus_path = MagicMock()
        mock_corpus_path.exists.return_value = True
        mock_get_corpus_path.return_value = mock_corpus_path

        mock_load_json.return_value = {
            "emails": [
                {
                    "id": "email_1",
                    "sender_email": "test@example.com",
                    "sender_name": "Test",
                    "sender_domain": "example.com",
                    "subject": "Test",
                    "body_text": "Body",
                    "received_date": "2024-01-15T10:30:00",
                    "has_attachments": False
                }
            ]
        }

        mock_reviewer = MagicMock()
        mock_reviewer.run_interactive_review.return_value = []
        mock_reviewer_class.return_value = mock_reviewer

        categories = [create_test_category()]
        review_categories(categories)

        mock_load_json.assert_called_once_with(mock_corpus_path)

    @patch("src.ui.category_review.CategoryReview")
    @patch("src.ui.category_review.load_json")
    @patch("src.utils.paths.PathConfig.get_corpus_path")
    @patch("builtins.print")
    def test_review_categories_assigns_uuids(
        self, mock_print, mock_get_corpus_path, mock_load_json, mock_reviewer_class
    ):
        """Test that unique category IDs are assigned."""
        mock_corpus_path = MagicMock()
        mock_corpus_path.exists.return_value = False
        mock_get_corpus_path.return_value = mock_corpus_path

        # Category with temp ID
        cat_temp = create_test_category(category_id="temp_1")
        cat_custom = create_test_category(category_id="custom_1")

        mock_reviewer = MagicMock()
        mock_reviewer.run_interactive_review.return_value = [cat_temp, cat_custom]
        mock_reviewer_class.return_value = mock_reviewer

        review_categories([])

        # IDs should have been replaced
        assert cat_temp.category_id.startswith("cat_")
        assert cat_custom.category_id.startswith("cat_")

    @patch("src.ui.category_review.CategoryReview")
    @patch("src.ui.category_review.load_json")
    @patch("src.utils.paths.PathConfig.get_corpus_path")
    @patch("builtins.print")
    def test_review_categories_with_output_path(
        self, mock_print, mock_get_corpus_path, mock_load_json, mock_reviewer_class
    ):
        """Test saving to output path when provided."""
        mock_corpus_path = MagicMock()
        mock_corpus_path.exists.return_value = False
        mock_get_corpus_path.return_value = mock_corpus_path

        mock_reviewer = MagicMock()
        mock_reviewer.run_interactive_review.return_value = []
        mock_reviewer_class.return_value = mock_reviewer

        output_path = Path("/tmp/output.json")
        review_categories([], output_path=output_path)

        mock_reviewer.save_approved_categories.assert_called_once_with(output_path)


class TestCleanupIntermediateFiles:
    """Test cleanup_intermediate_files() function."""

    @patch("builtins.print")
    @patch("builtins.input")
    def test_cleanup_declined(self, mock_input, mock_print):
        """Test declining cleanup keeps all files."""
        mock_input.return_value = "n"

        cleanup_intermediate_files("/tmp/outputs")

        # Should have asked about cleanup
        mock_input.assert_called_once()

    @patch("builtins.print")
    @patch("builtins.input")
    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.unlink")
    def test_cleanup_confirmed(self, mock_unlink, mock_exists, mock_input, mock_print):
        """Test confirming cleanup deletes intermediate files."""
        mock_input.side_effect = ["y", "y"]  # Yes to cleanup, yes to keep important files
        mock_exists.return_value = True

        cleanup_intermediate_files("/tmp/outputs")

        # Should have deleted files
        assert mock_unlink.called

    @patch("builtins.print")
    @patch("builtins.input")
    @patch("pathlib.Path.exists")
    def test_cleanup_no_files_found(self, mock_exists, mock_input, mock_print):
        """Test cleanup when no intermediate files exist."""
        mock_input.return_value = "y"
        mock_exists.return_value = False

        cleanup_intermediate_files("/tmp/outputs")

        print_calls = [str(c) for c in mock_print.call_args_list]
        all_output = " ".join(print_calls)
        assert "No intermediate files found" in all_output

    @patch("builtins.print")
    @patch("builtins.input")
    @patch("pathlib.Path.exists")
    def test_cleanup_cancelled_on_keep_prompt(self, mock_exists, mock_input, mock_print):
        """Test canceling cleanup at keep files prompt."""
        mock_input.side_effect = ["y", "n"]  # Yes to cleanup, no to keep important files
        mock_exists.return_value = True

        cleanup_intermediate_files("/tmp/outputs")

        print_calls = [str(c) for c in mock_print.call_args_list]
        all_output = " ".join(print_calls)
        assert "Cleanup cancelled" in all_output

    @patch("builtins.print")
    @patch("builtins.input")
    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.unlink")
    def test_cleanup_handles_delete_error(
        self, mock_unlink, mock_exists, mock_input, mock_print
    ):
        """Test cleanup handles file deletion errors gracefully."""
        mock_input.side_effect = ["y", "y"]
        mock_exists.return_value = True
        mock_unlink.side_effect = PermissionError("Access denied")

        cleanup_intermediate_files("/tmp/outputs")

        # Should print error but not crash
        print_calls = [str(c) for c in mock_print.call_args_list]
        all_output = " ".join(print_calls)
        assert "Error deleting" in all_output

    @patch("builtins.print")
    @patch("builtins.input")
    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.unlink")
    def test_cleanup_deletes_correct_files(
        self, mock_unlink, mock_exists, mock_input, mock_print
    ):
        """Test that only intermediate files are deleted."""
        mock_input.side_effect = ["y", "y"]
        mock_exists.return_value = True
        mock_unlink.return_value = None

        cleanup_intermediate_files("outputs")

        # Check that the correct files are targeted
        print_calls = [str(c) for c in mock_print.call_args_list]
        all_output = " ".join(print_calls)

        # These should be mentioned as files to delete
        assert "email_corpus.json" in all_output
        assert "corpus_analysis_results.json" in all_output
        assert "category_suggestions.json" in all_output


class TestCategoryReviewEdgeCases:
    """Test edge cases and boundary conditions."""

    @patch("builtins.print")
    @patch("builtins.input")
    def test_category_without_email_count(self, mock_input, mock_print):
        """Test displaying category with no email count."""
        category = create_test_category(email_count=None, percentage=None)
        reviewer = CategoryReview([category])

        mock_input.return_value = "A"
        reviewer._review_category(category, 1, 1)

        print_calls = [str(c) for c in mock_print.call_args_list]
        all_output = " ".join(print_calls)
        assert "Unknown" in all_output

    @patch("builtins.print")
    @patch("builtins.input")
    def test_retry_prefix_shown(self, mock_input, mock_print):
        """Test that RETRY prefix is shown on retry."""
        category = create_test_category()
        reviewer = CategoryReview([category])

        mock_input.return_value = "A"
        reviewer._review_category(category, 1, 1, is_retry=True)

        print_calls = [str(c) for c in mock_print.call_args_list]
        all_output = " ".join(print_calls)
        assert "[RETRY]" in all_output

    @patch("builtins.print")
    @patch("builtins.input")
    def test_merge_combines_example_email_ids(self, mock_input, mock_print):
        """Test that merge combines example_email_ids correctly."""
        target = create_test_category(
            category_id="target",
            example_email_ids=["email_1", "email_2", "email_3"]
        )
        source = create_test_category(
            category_id="source",
            example_email_ids=["email_2", "email_4", "email_5"]  # email_2 is duplicate
        )

        reviewer = CategoryReview([target, source])
        reviewer.approved = [target]

        mock_input.side_effect = ["M", "1"]
        reviewer._review_category(source, 2, 2)

        # Should have merged without duplicates
        assert "email_1" in target.example_email_ids
        assert "email_2" in target.example_email_ids
        assert "email_4" in target.example_email_ids

    @patch("builtins.print")
    @patch("builtins.input")
    def test_max_sample_emails_displayed(self, mock_input, mock_print):
        """Test that only 3 sample emails are displayed."""
        emails = {f"email_{i}": create_test_email(f"email_{i}") for i in range(1, 6)}
        category = create_test_category(
            example_email_ids=["email_1", "email_2", "email_3", "email_4", "email_5"]
        )
        reviewer = CategoryReview([category], emails)

        mock_input.return_value = "A"
        reviewer._review_category(category, 1, 1)

        # Should only show 3 samples
        print_calls = [str(c) for c in mock_print.call_args_list]
        all_output = " ".join(print_calls)

        # Count how many "From:" lines appear (one per email shown)
        from_count = all_output.count("From:")
        assert from_count == 3

    @patch("builtins.print")
    @patch("builtins.input")
    def test_custom_category_id_incrementing(self, mock_input, mock_print):
        """Test that custom category IDs increment correctly."""
        reviewer = CategoryReview([])
        reviewer.approved = [
            create_test_category(category_id="existing_1"),
            create_test_category(category_id="existing_2")
        ]

        # Add one custom category
        mock_input.side_effect = ["Custom Name", "Custom desc", ""]
        reviewer._add_custom_categories()

        # Custom ID should be based on approved count
        custom = reviewer.approved[-1]
        assert custom.category_id == "custom_3"


class TestCategoryReviewStateCounting:
    """Test that state counters are tracked correctly."""

    @patch("builtins.print")
    @patch("builtins.input")
    def test_all_counters_track_correctly(self, mock_input, mock_print):
        """Test that all counters are tracked correctly through various operations."""
        cat1 = create_test_category(category_id="cat1", name="Accept")
        cat2 = create_test_category(category_id="cat2", name="Rename")
        cat3 = create_test_category(category_id="cat3", name="Delete")
        cat4 = create_test_category(category_id="cat4", name="Merge")
        cat5 = create_test_category(category_id="cat5", name="Merge Target")

        reviewer = CategoryReview([cat1, cat2, cat3, cat4, cat5])

        # Sequence: Accept cat1, Rename cat2, Delete cat3, Accept cat5 (for merge), Merge cat4
        mock_input.side_effect = [
            "A",              # Accept cat1
            "R", "New Name",  # Rename cat2
            "D", "y",         # Delete cat3
            "A",              # Accept cat5 (for merge target)
            "M", "2",         # Merge cat4 into cat5 (index 2 in approved list)
            "n"               # No custom categories
        ]

        approved = reviewer.run_interactive_review()

        assert reviewer.modified_count == 1  # cat2 renamed
        assert reviewer.deleted_count == 1   # cat3 deleted
        assert reviewer.merged_count == 1    # cat4 merged
        # Approved: cat1, cat2, cat5 (cat4 was merged into cat5)
        assert len(approved) == 3
