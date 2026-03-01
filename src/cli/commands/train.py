"""Train command: fine-tune local SetFit model on accumulated corrections.

Phase 6, Work Item 6.3: Creates the training pipeline CLI command.

Loads corrections from the SQLite database via EmailFeedbackStore, looks up
the corresponding email text for each correction, groups by category, filters
categories with insufficient examples, trains a SetFit model, and saves it
with version metadata.

Supports --min-examples (minimum per class, default 8), --model-type (setfit),
and --output (model save path).
"""

import argparse
import time
from collections import Counter
from pathlib import Path

from src.classifiers.setfit_classifier import SetFitClassifier
from src.cli.formatters import output_json
from src.learning.feedback_store import EmailFeedbackStore
from src.storage.database import Database
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Default model save directory
DEFAULT_MODEL_DIR = Path.home() / ".email-analyzer" / "models" / "setfit"


def build_train_parser(subparsers) -> argparse.ArgumentParser:
    """Add train subparser to the CLI and return it."""
    train_parser = subparsers.add_parser(
        "train",
        help="Fine-tune local model on accumulated corrections",
        description=(
            "Train a SetFit classifier on user corrections stored in the database. "
            "Reports: number of corrections per category, training accuracy, model path. "
            "Categories with fewer than --min-examples corrections are skipped."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Train with default settings (min 8 examples per category)
  %(prog)s

  # Train with lower minimum example threshold
  %(prog)s --min-examples 4

  # Save model to custom path
  %(prog)s --output ~/models/my-setfit

  # Preview training data without actually training
  %(prog)s --dry-run

  # Machine-readable JSON output
  %(prog)s --json

  # Use a specific database file
  %(prog)s --db-path /path/to/database.db
        """,
    )

    train_parser.add_argument(
        "--min-examples",
        type=int,
        default=8,
        help="Minimum corrections per category to include in training (default: 8). "
        "Categories with fewer corrections are skipped with a warning.",
    )
    train_parser.add_argument(
        "--model-type",
        choices=["setfit"],
        default="setfit",
        help="Model type to train (default: setfit). Currently only SetFit is supported.",
    )
    train_parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help=f"Directory to save the trained model (default: {DEFAULT_MODEL_DIR})",
    )
    train_parser.add_argument(
        "--db-path",
        type=Path,
        default=None,
        help="Path to SQLite database (default: ~/.email-analyzer/email_analyzer.db)",
    )
    train_parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Preview training data without actually training the model",
    )

    return train_parser  # type: ignore[no-any-return]


# =============================================================================
# Training data preparation
# =============================================================================


def _load_training_data(
    db: Database,
    store: EmailFeedbackStore,
    min_examples: int,
) -> tuple[list[tuple[str, str]], dict[str, int], dict[str, int]]:
    """Load corrections and prepare training data.

    Retrieves all corrections from the store, looks up the corresponding
    email text from the database, groups by new_category, and filters
    categories below the minimum example threshold.

    Args:
        db: Database instance for email text lookups.
        store: EmailFeedbackStore to retrieve corrections from.
        min_examples: Minimum corrections per category.

    Returns:
        Tuple of:
        - training_examples: List of (text, label) tuples for training
        - included_counts: Dict of {category: count} for included categories
        - skipped_counts: Dict of {category: count} for skipped categories
    """
    corrections = store.get_corrections()

    if not corrections:
        return [], {}, {}

    # Group corrections by new_category and count
    category_counts: dict[str, int] = Counter(c.new_category for c in corrections)

    # Separate into included and skipped
    included_categories = {cat for cat, count in category_counts.items() if count >= min_examples}
    skipped_counts = {cat: count for cat, count in category_counts.items() if count < min_examples}
    included_counts = {
        cat: count for cat, count in category_counts.items() if count >= min_examples
    }

    if not included_categories:
        return [], {}, skipped_counts

    # Build training examples: look up email text for each correction
    training_examples: list[tuple[str, str]] = []

    for correction in corrections:
        if correction.new_category not in included_categories:
            continue

        # Look up email text from the database
        email_text = _get_email_text(db, correction.email_id)
        if email_text:
            training_examples.append((email_text, correction.new_category))

    return training_examples, included_counts, skipped_counts


def _get_email_text(db: Database, email_id: str) -> str | None:
    """Look up email subject and body from the database.

    Combines subject and body_text into a single training text string.

    Args:
        db: Database instance.
        email_id: The email ID to look up.

    Returns:
        Combined text string, or None if the email is not found.
    """
    try:
        cursor = db.execute(
            "SELECT subject, body_text FROM emails WHERE id = ?",
            (email_id,),
        )
        row = cursor.fetchone()
        if row is None:
            logger.debug("Email %s not found in database, skipping", email_id)
            return None

        subject, body_text = row[0] or "", row[1] or ""
        parts = []
        if subject:
            parts.append(f"Subject: {subject}")
        if body_text:
            # Truncate very long bodies to avoid model input limits
            parts.append(f"Body: {body_text[:2000]}")

        return "\n".join(parts) if parts else None

    except Exception as e:
        logger.warning("Failed to look up email %s: %s", email_id, e)
        return None


# =============================================================================
# Display helpers
# =============================================================================


def _print_training_results(
    training_stats: dict,
    included_counts: dict[str, int],
    skipped_counts: dict[str, int],
    model_path: Path,
    duration: float,
) -> None:
    """Print a human-readable training summary."""
    print()
    print("=" * 60)
    print("TRAINING RESULTS")
    print("=" * 60)
    print("Model type:         SetFit")
    print(f"Training examples:  {training_stats['num_examples']}")
    print(f"Categories trained: {training_stats['num_categories']}")
    print(f"Model saved to:     {model_path}")
    print(f"Duration:           {duration:.1f}s")
    print()

    if included_counts:
        print("--- Examples per Category ---")
        max_name_len = max(len(name) for name in included_counts)
        for name, count in sorted(included_counts.items(), key=lambda x: x[1], reverse=True):
            print(f"  {name:<{max_name_len}}  {count:>5} corrections")
        print()

    if skipped_counts:
        print("--- Skipped Categories (insufficient examples) ---")
        max_name_len = max(len(name) for name in skipped_counts)
        for name, count in sorted(skipped_counts.items(), key=lambda x: x[1], reverse=True):
            print(f"  {name:<{max_name_len}}  {count:>5} corrections (skipped)")
        print()

    print("=" * 60)
    print()


def _print_dry_run_preview(
    included_counts: dict[str, int],
    skipped_counts: dict[str, int],
    min_examples: int,
    model_type: str,
    model_path: Path,
) -> None:
    """Print a dry-run preview of what would be trained."""
    print()
    print("=" * 60)
    print("DRY RUN PREVIEW - No training will be performed")
    print("=" * 60)
    print(f"Model type:         {model_type}")
    print(f"Min examples:       {min_examples}")
    print(f"Model save path:    {model_path}")
    print()

    total_examples = sum(included_counts.values())
    print(f"Total training examples:  {total_examples}")
    print(f"Categories to train:      {len(included_counts)}")
    print(f"Categories to skip:       {len(skipped_counts)}")
    print()

    if included_counts:
        print("--- Categories to Train ---")
        max_name_len = max(len(name) for name in included_counts)
        for name, count in sorted(included_counts.items(), key=lambda x: x[1], reverse=True):
            print(f"  {name:<{max_name_len}}  {count:>5} corrections")
        print()

    if skipped_counts:
        print("--- Categories to Skip (below threshold) ---")
        max_name_len = max(len(name) for name in skipped_counts)
        for name, count in sorted(skipped_counts.items(), key=lambda x: x[1], reverse=True):
            print(f"  {name:<{max_name_len}}  {count:>5} corrections")
        print()

    print("=" * 60)
    print()


# =============================================================================
# Main command handler
# =============================================================================


def cmd_train(args: argparse.Namespace) -> int:
    """Execute train command.

    Loads corrections from the database, prepares training data, trains a
    SetFit model, and saves it with version metadata.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 = success, non-zero = error)
    """
    start_time = time.time()

    is_dry_run = getattr(args, "dry_run", False)
    is_json = getattr(args, "json", False)
    min_examples = getattr(args, "min_examples", 8)
    model_type = getattr(args, "model_type", "setfit")
    model_path = getattr(args, "output", None) or DEFAULT_MODEL_DIR
    db_path = getattr(args, "db_path", None)

    logger.info("=== MODEL TRAINING PIPELINE ===")

    # ------------------------------------------------------------------
    # 1. Open database
    # ------------------------------------------------------------------
    try:
        db = Database(db_path or Database.default_path())
    except Exception as e:
        msg = f"Failed to open database: {e}"
        logger.error(msg)
        if is_json:
            output_json({"command": "train", "status": "error", "error": msg})
        return 1

    # ------------------------------------------------------------------
    # 2. Load corrections
    # ------------------------------------------------------------------
    try:
        store = EmailFeedbackStore(database=db)
        training_examples, included_counts, skipped_counts = _load_training_data(
            db, store, min_examples
        )
    except Exception as e:
        msg = f"Failed to load corrections: {e}"
        logger.error(msg)
        if is_json:
            output_json({"command": "train", "status": "error", "error": msg})
        return 1

    # ------------------------------------------------------------------
    # 3. Validate training data
    # ------------------------------------------------------------------
    if not training_examples:
        if skipped_counts:
            msg = (
                f"No categories have enough corrections for training "
                f"(minimum: {min_examples}). "
                f"Skipped categories: {', '.join(f'{k} ({v})' for k, v in skipped_counts.items())}. "
                f"Collect more corrections or lower --min-examples."
            )
        else:
            msg = (
                "No corrections found in the database. "
                "Use the feedback system to record corrections before training."
            )
        logger.error(msg)
        if is_json:
            output_json({"command": "train", "status": "error", "error": msg})
        return 1

    # Log skipped categories
    if skipped_counts:
        for cat, count in skipped_counts.items():
            logger.warning(
                "Skipping category '%s': only %d corrections (minimum: %d)",
                cat,
                count,
                min_examples,
            )

    # ------------------------------------------------------------------
    # 4. Dry-run mode: preview and exit
    # ------------------------------------------------------------------
    if is_dry_run:
        if is_json:
            output_json(
                {
                    "command": "train",
                    "status": "success",
                    "dry_run": True,
                    "model_type": model_type,
                    "min_examples": min_examples,
                    "model_path": str(model_path),
                    "total_examples": len(training_examples),
                    "categories_to_train": included_counts,
                    "categories_skipped": skipped_counts,
                }
            )
        else:
            _print_dry_run_preview(
                included_counts,
                skipped_counts,
                min_examples,
                model_type,
                model_path,
            )
        return 0

    # ------------------------------------------------------------------
    # 5. Train the model
    # ------------------------------------------------------------------
    try:
        categories = list(included_counts.keys())
        classifier = SetFitClassifier(
            categories=categories,
            min_examples_per_class=min_examples,
        )

        logger.info(
            "Training %s model on %d examples across %d categories...",
            model_type,
            len(training_examples),
            len(categories),
        )

        training_stats = classifier.train(training_examples)

    except ImportError as e:
        msg = f"SetFit is not installed: {e}. Install with: pip install -e '.[ml]'"
        logger.error(msg)
        if is_json:
            output_json({"command": "train", "status": "error", "error": msg})
        return 1
    except (ValueError, RuntimeError) as e:
        msg = f"Training failed: {e}"
        logger.error(msg)
        if is_json:
            output_json({"command": "train", "status": "error", "error": msg})
        return 1

    # ------------------------------------------------------------------
    # 6. Save the model
    # ------------------------------------------------------------------
    try:
        classifier.save_model(model_path)
        logger.info("Model saved to %s", model_path)
    except Exception as e:
        msg = f"Failed to save model: {e}"
        logger.error(msg)
        if is_json:
            output_json({"command": "train", "status": "error", "error": msg})
        return 1

    # ------------------------------------------------------------------
    # 7. Output results
    # ------------------------------------------------------------------
    duration = time.time() - start_time

    if is_json:
        output_json(
            {
                "command": "train",
                "status": "success",
                "dry_run": False,
                "model_type": model_type,
                "model_path": str(model_path),
                "duration_seconds": round(duration, 2),
                "training_stats": training_stats,
                "categories_trained": included_counts,
                "categories_skipped": skipped_counts,
            }
        )
    else:
        _print_training_results(
            training_stats,
            included_counts,
            skipped_counts,
            model_path,
            duration,
        )

    return 0
