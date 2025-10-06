"""
Interactive category review CLI module.

Per quickstart.md Scenario 4 (lines 172-243), FR-032, and Clarification Q5.
Allows users to review, approve, modify, merge, or delete suggested categories.
"""
import uuid
from datetime import datetime
from pathlib import Path

from src.models.category import Category, CategorySource
from src.models.email import Email
from src.utils.file_manager import load_json, save_json
from src.utils.logger import get_logger

logger = get_logger(__name__)


class CategoryReview:
    """Interactive CLI for reviewing and approving category suggestions."""

    def __init__(self, categories: list[Category], email_lookup: dict[str, Email] = None):
        """
        Initialize category review.

        Args:
            categories: List of suggested categories to review
            email_lookup: Optional dictionary mapping email IDs to Email objects for sample display
        """
        self.categories = categories
        self.email_lookup = email_lookup or {}
        self.approved: list[Category] = []
        self.modified_count = 0
        self.merged_count = 0
        self.deleted_count = 0
        self.custom_count = 0
        self.skipped: list[Category] = []

    def run_interactive_review(self) -> list[Category]:
        """
        Run interactive review session.

        Returns:
            List of approved categories with user modifications

        Based on quickstart.md lines 178-217
        """
        print("=" * 60)
        print("CATEGORY REVIEW - Interactive Mode")
        print("=" * 60)
        print()

        # First pass - review all categories
        for idx, category in enumerate(self.categories, 1):
            self._review_category(category, idx, len(self.categories))

        # Second pass - re-present skipped categories
        if self.skipped:
            print("\n" + "=" * 60)
            print(f"Re-reviewing {len(self.skipped)} skipped categories...")
            print("=" * 60)
            print()

            remaining_skipped = []
            for idx, category in enumerate(self.skipped, 1):
                result = self._review_category(category, idx, len(self.skipped), is_retry=True)
                if result == 'skip':
                    remaining_skipped.append(category)

            # If still skipped, auto-accept them
            if remaining_skipped:
                print(f"\nAuto-accepting {len(remaining_skipped)} remaining skipped categories...")
                self.approved.extend(remaining_skipped)

        # Prompt for custom categories
        print("\n" + "=" * 60)
        add_custom = input("Would you like to add any custom categories? (y/n): ").strip().lower()
        if add_custom == 'y':
            self._add_custom_categories()

        print("\n" + "=" * 60)
        print("Review complete!")
        print(f"Approved {len(self.approved)} categories")
        print("=" * 60)

        return self.approved

    def _review_category(
        self,
        category: Category,
        idx: int,
        total: int,
        is_retry: bool = False
    ) -> str:
        """
        Review a single category interactively.

        Args:
            category: Category to review
            idx: Current category index
            total: Total categories to review
            is_retry: Whether this is a retry of a skipped category

        Returns:
            Action taken: 'accept', 'rename', 'merge', 'delete', or 'skip'
        """
        retry_prefix = "[RETRY] " if is_retry else ""
        print(f"--- {retry_prefix}Category {idx} of {total} ---")
        print(f"Name: {category.category_name}")
        print(f"Description: {category.description}")
        print(f"Confidence: {category.confidence * 100:.1f}%")

        # Format email count display
        email_count_str = f"{category.email_count}" if category.email_count else "Unknown"
        percentage_str = f" ({category.percentage:.1f}% of inbox)" if category.percentage else ""
        print(f"Emails: {email_count_str}{percentage_str}")
        print()

        # Show sample emails if available (per quickstart.md lines 192-196)
        if category.example_email_ids and self.email_lookup:
            print("Sample emails in this category:")
            for email_id in category.example_email_ids[:3]:  # Show max 3 samples
                if email_id in self.email_lookup:
                    email = self.email_lookup[email_id]
                    print(f"  - From: {email.sender_email}")
                    print(f"    Subject: {email.subject}")
            print()
        elif category.distinguishing_features:
            # Fallback to distinguishing features if no emails available
            print("Sample emails in this category:")
            for feature in category.distinguishing_features[:3]:
                print(f"  - {feature[:80]}{'...' if len(feature) > 80 else ''}")
            print()

        print("Options:")
        print("  [A] Accept this category")
        print("  [R] Rename category")
        print("  [M] Merge with another category")
        print("  [D] Delete this category")
        print("  [S] Skip for now")
        print()

        while True:
            choice = input("Your choice: ").strip().upper()

            if choice == 'A':
                self.approved.append(category)
                print(f"✓ Category '{category.category_name}' approved")
                logger.info(f"Category accepted: {category.category_name}")
                print()
                return 'accept'

            if choice == 'R':
                new_name = input("Enter new category name: ").strip()
                if new_name:
                    old_name = category.category_name
                    category.category_name = new_name
                    category.user_modified = True
                    self.approved.append(category)
                    self.modified_count += 1
                    print(f"✓ Category renamed to '{new_name}' and approved")
                    logger.info(f"Category renamed: '{old_name}' -> '{new_name}'")
                    print()
                    return 'rename'
                print("Invalid name. Category not modified.")
                logger.debug("Invalid category name provided for rename")

            elif choice == 'M':
                print("\nAvailable categories to merge with:")
                for i, approved_cat in enumerate(self.approved, 1):
                    print(f"  {i}. {approved_cat.category_name}")

                if not self.approved:
                    print("No approved categories available for merging yet.")
                    continue

                try:
                    merge_idx = int(input("Enter category number to merge with (0 to cancel): "))
                    if merge_idx == 0:
                        continue
                    if 1 <= merge_idx <= len(self.approved):
                        target = self.approved[merge_idx - 1]
                        # Merge email IDs and update counts
                        all_ids = set(target.example_email_ids) | set(category.example_email_ids)
                        target.example_email_ids = list(all_ids)[:10]
                        target.email_count += category.email_count
                        target.user_modified = True
                        self.merged_count += 1
                        print(f"✓ Merged into '{target.category_name}'")
                        logger.info(f"Category merged: '{category.category_name}' into '{target.category_name}'")
                        print()
                        return 'merge'
                except (ValueError, IndexError):
                    print("Invalid selection.")
                    logger.debug("Invalid merge selection")

            elif choice == 'D':
                confirm = input(f"Delete '{category.category_name}'? (y/n): ").strip().lower()
                if confirm == 'y':
                    self.deleted_count += 1
                    print(f"✓ Category '{category.category_name}' deleted")
                    logger.info(f"Category deleted: {category.category_name}")
                    print()
                    return 'delete'
                logger.debug(f"Category deletion cancelled for: {category.category_name}")

            elif choice == 'S':
                if not is_retry:
                    self.skipped.append(category)
                    print(f"⊙ Category '{category.category_name}' skipped")
                    logger.debug(f"Category skipped: {category.category_name}")
                    print()
                    return 'skip'
                # On retry, skip means we'll auto-accept later
                print(f"⊙ Category '{category.category_name}' skipped (will auto-accept)")
                logger.debug(f"Category skipped on retry (will auto-accept): {category.category_name}")
                print()
                return 'skip'

            else:
                print("Invalid choice. Please enter A, R, M, D, or S.")
                logger.debug(f"Invalid choice entered: {choice}")

    def _add_custom_categories(self) -> None:
        """Add custom categories defined by user."""
        print("\nAdding custom categories (press Enter with empty name to finish):")

        while True:
            name = input("\nCategory name: ").strip()
            if not name:
                break

            description = input("Description: ").strip()
            if not description:
                description = f"Custom category: {name}"

            # Create custom category
            custom_category = Category(
                category_id=f"custom_{len(self.approved) + 1}",
                category_name=name,
                description=description,
                confidence=1.0,  # User-defined = 100% confidence
                email_count=0,
                percentage=0.0,
                source=CategorySource.CUSTOM,
                source_id="user_defined",
                user_modified=True,
                distinguishing_features=[],
                example_email_ids=[]
            )

            self.approved.append(custom_category)
            self.custom_count += 1
            print(f"✓ Custom category '{name}' added")
            logger.info(f"Custom category added: {name}")

    def save_approved_categories(self, output_path: Path) -> dict:
        """
        Save approved categories to JSON file (FR-036, FR-037).

        Args:
            output_path: Path to save approved_categories.json

        Returns:
            Dictionary containing approval metadata and categories
        """
        # Calculate stats (FR-037)
        suggested_count = len(self.categories)
        approved_base = len(self.approved) - self.custom_count

        approval_data = {
            "approval_date": datetime.utcnow().isoformat() + "Z",  # ISO 8601 with Z suffix
            "total_categories": len(self.approved),
            "processing_stats": {
                "suggested": suggested_count,
                "approved": approved_base,
                "modified": self.modified_count,
                "merged": self.merged_count,
                "deleted": self.deleted_count,
                "custom": self.custom_count
            },
            "categories": [cat.model_dump() for cat in self.approved]
        }

        save_json(approval_data, output_path)
        logger.info(f"Saved {len(self.approved)} approved categories to {output_path}")

        return approval_data


def review_categories(
    categories: list[Category],
    output_path: Path | None = None
) -> list[Category]:
    """
    Interactive review of suggested categories.

    Presents each category with details and sample emails, allowing users to:
    - Accept, Rename, Merge, Delete, or Skip categories
    - Re-presents skipped categories at end (per Clarification Q5)
    - Add custom categories

    Args:
        categories: List of Category objects to review
        output_path: Optional path to save approved categories (if None, no save)

    Returns:
        List of approved Category objects

    Raises:
        ValueError: If categories data is invalid
    """
    logger.info("Starting interactive category review")

    # Load email corpus for sample display
    from src.utils.paths import PathConfig
    corpus_path = PathConfig.get_corpus_path()
    email_lookup = {}
    if corpus_path.exists():
        corpus_data = load_json(corpus_path)
        email_lookup = {email["id"]: Email(**email) for email in corpus_data.get("emails", [])}

    # Run interactive review
    reviewer = CategoryReview(categories, email_lookup)
    approved = reviewer.run_interactive_review()

    # Assign unique category IDs to all approved categories (FR-035)
    for category in approved:
        if not category.category_id or category.category_id.startswith("temp_") or category.category_id.startswith("custom_"):
            category.category_id = f"cat_{uuid.uuid4().hex[:12]}"

    # Save approved categories if output path provided
    if output_path:
        reviewer.save_approved_categories(output_path)
        print(f"\nSaved to: {output_path}")

    print("\nReview complete!")
    print(f"Approved {len(approved)} categories")
    logger.info(f"Category review complete. Approved {len(approved)} categories")

    return approved


def cleanup_intermediate_files(output_dir: str = "outputs") -> None:
    """
    Optional cleanup of intermediate files after category approval.

    Per Clarification Q1 and quickstart.md Scenario 5 (lines 245-268).
    Prompts user to delete intermediate files while preserving:
    - approved_categories.json
    - extraction_errors.log

    Args:
        output_dir: Output directory containing intermediate files (default: "outputs")
    """
    logger.info("Starting optional cleanup of intermediate files")

    output_path = Path(output_dir)

    # Files to potentially delete
    intermediate_files = [
        "email_corpus.json",
        "corpus_analysis_results.json",
        "category_suggestions.json",
        "category_suggestions_report.md"
    ]

    # Files to keep
    keep_files = [
        "approved_categories.json",
        "extraction_errors.log"
    ]

    print("\nCategory approval complete!")
    cleanup = input("Would you like to clean up intermediate files? (y/n): ").strip().lower()

    if cleanup != 'y':
        print("Cleanup cancelled. All files kept.")
        logger.info("User declined cleanup")
        return

    # List files to delete
    print("\nThe following files will be deleted:")
    files_to_delete = []
    for filename in intermediate_files:
        file_path = output_path / filename
        if file_path.exists():
            print(f"  - {file_path}")
            files_to_delete.append(file_path)

    if not files_to_delete:
        print("No intermediate files found to delete.")
        logger.info("No intermediate files found for cleanup")
        return

    # Confirm keeping important files (per quickstart.md line 260)
    keep_confirm = input(f"\nKeep {', '.join(keep_files)}? (y/n): ").strip().lower()

    if keep_confirm != 'y':
        print("Cleanup cancelled.")
        logger.info("User cancelled cleanup during confirmation")
        return

    # Delete intermediate files
    deleted_count = 0
    for file_path in files_to_delete:
        try:
            file_path.unlink()
            deleted_count += 1
            logger.debug(f"Deleted intermediate file: {file_path}")
        except Exception as e:
            print(f"Error deleting {file_path}: {e}")
            logger.error(f"Failed to delete {file_path}: {e}")

    print("\nCleanup complete!")
    print(f"Kept: {', '.join(keep_files)}")
    logger.info(f"Cleanup complete. Deleted {deleted_count} intermediate files")
