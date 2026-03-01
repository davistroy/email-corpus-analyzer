"""Classify command: LLM-based email classification (Phase 2, Item 2.3).

Runs LLM classification directly on a corpus without requiring rules.
Supports --provider, --model, --categories (YAML), --confidence-threshold,
and --output flags. Uses the existing CategorizationReport model for output.
Works with or without prior analysis -- only requires an extracted corpus.
"""

import argparse
import time
from pathlib import Path

import yaml

from src.classifiers.llm_classifier import LLMClassifier
from src.cli.formatters import output_json
from src.config.loader import load_config
from src.config.models import CategoryDefinition, ClassifierConfig
from src.exceptions import ClassificationError, ClassifierConnectionError
from src.models.categorization import (
    CategorizationReport,
    CategoryAssignment,
    EmailCategorization,
)
from src.models.corpus import Corpus
from src.utils.file_manager import load_json, save_json
from src.utils.logger import get_logger
from src.utils.paths import PathConfig

logger = get_logger(__name__)


def build_classify_parser(subparsers) -> argparse.ArgumentParser:
    """Add classify subparser to the CLI and return it."""
    classify_parser = subparsers.add_parser(
        "classify",
        help="Classify emails using LLM (Ollama, OpenAI, Claude, or RunPod)",
        description="Run LLM-based classification on an email corpus. "
        "Assigns each email to a category using a language model. "
        "Does NOT require rules -- only requires an extracted corpus and category definitions.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Classify using Ollama (default, local, zero cost)
  %(prog)s

  # Classify with a specific provider and model
  %(prog)s --provider openai --model gpt-4o-mini

  # Classify with categories from a YAML file
  %(prog)s --categories ~/my-categories.yaml

  # Preview what would be classified without calling the LLM
  %(prog)s --dry-run

  # Set custom confidence threshold
  %(prog)s --confidence-threshold 0.7

  # Machine-readable JSON output
  %(prog)s --json

  # Custom corpus and output paths
  %(prog)s --corpus /path/to/corpus.json --output /path/to/report.json
        """,
    )

    classify_parser.add_argument(
        "--provider",
        choices=["ollama", "openai", "claude", "runpod"],
        default=None,
        help="LLM provider (default: from config, or 'ollama'). Ollama runs locally at no cost.",
    )
    classify_parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Model name (default: from config, or 'qwen2.5:7b' for Ollama). "
        "Examples: qwen2.5:7b, gpt-4o-mini, claude-sonnet-4-20250514",
    )
    classify_parser.add_argument(
        "--endpoint-id",
        type=str,
        default=None,
        help="RunPod serverless endpoint ID (required when --provider is 'runpod'). "
        "The endpoint URL is constructed as https://api.runpod.ai/v2/{endpoint-id}/openai/v1",
    )
    classify_parser.add_argument(
        "--categories",
        type=Path,
        default=None,
        help="Path to YAML file defining categories for classification. "
        "If not provided, uses categories from config.",
    )
    classify_parser.add_argument(
        "--confidence-threshold",
        type=float,
        default=None,
        help="Minimum confidence to accept a classification (0.0-1.0). "
        "Results below this threshold are marked uncategorized. "
        "Default: from config, or 0.6.",
    )
    classify_parser.add_argument(
        "--corpus",
        type=Path,
        default=None,
        help="Path to email corpus JSON (default: {output-dir}/email_corpus.json)",
    )
    classify_parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output path for classification report JSON "
        "(default: {output-dir}/categorization_report.json)",
    )
    classify_parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Preview what would be classified without calling the LLM",
    )

    return classify_parser  # type: ignore[no-any-return]


# =============================================================================
# Category loading
# =============================================================================


def _load_categories_from_yaml(yaml_path: Path) -> list[CategoryDefinition]:
    """Load category definitions from a YAML file.

    Expected YAML format:
        categories:
          - name: Newsletters
            description: Regular newsletter emails
            keywords: [newsletter, digest]  # optional
          - name: Promotions
            description: Marketing and promotional offers

    Args:
        yaml_path: Path to the YAML file.

    Returns:
        List of CategoryDefinition objects.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the YAML is invalid or missing required fields.
    """
    if not yaml_path.exists():
        raise FileNotFoundError(f"Categories file not found: {yaml_path}")

    with open(yaml_path) as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict) or "categories" not in data:
        raise ValueError(
            f"Categories YAML must have a top-level 'categories' key. "
            f"Got keys: {list(data.keys()) if isinstance(data, dict) else type(data).__name__}"
        )

    categories = []
    for entry in data["categories"]:
        if not isinstance(entry, dict) or "name" not in entry or "description" not in entry:
            raise ValueError(
                f"Each category must have 'name' and 'description' fields. Got: {entry}"
            )
        categories.append(
            CategoryDefinition(
                name=entry["name"],
                description=entry["description"],
                keywords=entry.get("keywords", []),
            )
        )

    return categories


# =============================================================================
# Corpus loading
# =============================================================================


def _load_corpus(args: argparse.Namespace, is_json: bool = False):
    """Load the Corpus from disk. Returns (corpus, error_code) tuple."""
    corpus_path = getattr(args, "corpus", None) or PathConfig.get_corpus_path()

    try:
        corpus_data = load_json(corpus_path)
        corpus = Corpus(**corpus_data)
        logger.info(f"Loaded corpus with {len(corpus.emails)} emails from {corpus_path}")
        return corpus, None
    except FileNotFoundError:
        msg = (
            f"Corpus file not found: {corpus_path}. "
            f"Run 'extract' first, or specify a valid path with --corpus."
        )
        logger.error(msg)
        if is_json:
            output_json({"command": "classify", "status": "error", "error": msg})
        return None, 1
    except Exception as e:
        logger.error(f"Failed to load corpus from {corpus_path}: {e}")
        if is_json:
            output_json({"command": "classify", "status": "error", "error": str(e)})
        return None, 1


# =============================================================================
# Display helpers
# =============================================================================


def _print_classification_summary(report: CategorizationReport, verbose: bool = False) -> None:
    """Print a human-readable classification summary."""
    print()
    print("=" * 60)
    print("CLASSIFICATION RESULTS")
    print("=" * 60)
    print(f"Total emails:       {report.total_emails}")
    print(f"Classified:         {report.categorized_count}")
    print(f"Uncategorized:      {report.uncategorized_count}")
    print(f"Coverage:           {report.coverage_percentage:.1f}%")
    print(f"Categories used:    {report.category_count}")
    print()

    if report.categories_used:
        print("--- Category Breakdown ---")
        max_name_len = max(len(name) for name in report.categories_used)
        for name, count in sorted(report.categories_used.items(), key=lambda x: x[1], reverse=True):
            print(f"  {name:<{max_name_len}}  {count:>5} emails")
        print()

    if verbose:
        print("--- Per-Email Detail ---")
        for cat in report.categorizations:
            if cat.is_uncategorized:
                print(f"  {cat.email_id}: [Uncategorized]")
            else:
                primary = cat.primary_category
                reasoning = ""
                if primary.source:
                    reasoning = f" [{primary.source}]"
                print(
                    f"  {cat.email_id}: {primary.category_name} "
                    f"(confidence: {primary.confidence:.2f}){reasoning}"
                )
        print()

    print("=" * 60)
    print()


def _print_dry_run_preview(
    corpus: Corpus,
    categories: list[CategoryDefinition],
    provider: str,
    model: str,
    threshold: float,
) -> None:
    """Print a dry-run preview of what would be classified."""
    print()
    print("=" * 60)
    print("DRY RUN PREVIEW - No LLM calls will be made")
    print("=" * 60)
    print(f"Corpus:             {len(corpus.emails)} emails")
    print(f"Provider:           {provider}")
    print(f"Model:              {model}")
    print(f"Confidence threshold: {threshold}")
    print(f"Categories:         {len(categories)}")
    print()
    for cat in categories:
        print(f"  - {cat.name}: {cat.description}")
    print()
    print("=" * 60)
    print()


# =============================================================================
# Main command handler
# =============================================================================


def cmd_classify(args: argparse.Namespace) -> int:
    """
    Execute classify command.

    Loads the corpus, creates an LLMClassifier from config (with CLI overrides),
    classifies every email, and saves a CategorizationReport.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 = success, non-zero = error)
    """
    start_time = time.time()

    is_dry_run = getattr(args, "dry_run", False)
    is_json = getattr(args, "json", False)
    is_verbose = getattr(args, "verbose", False)

    logger.info("=== LLM EMAIL CLASSIFICATION ===")

    # ------------------------------------------------------------------
    # 1. Load configuration
    # ------------------------------------------------------------------
    try:
        config = load_config(config_path=getattr(args, "config", None))
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        if is_json:
            output_json({"command": "classify", "status": "error", "error": str(e)})
        return 1

    classifier_config = config.classifier

    # ------------------------------------------------------------------
    # 2. Resolve categories (CLI --categories file overrides config)
    # ------------------------------------------------------------------
    categories_path = getattr(args, "categories", None)
    yaml_categories: list[CategoryDefinition] | None = None
    if categories_path:
        try:
            yaml_categories = _load_categories_from_yaml(categories_path)
            logger.info(f"Loaded {len(yaml_categories)} categories from {categories_path}")
        except FileNotFoundError as e:
            msg = str(e)
            logger.error(msg)
            if is_json:
                output_json({"command": "classify", "status": "error", "error": msg})
            return 1
        except (ValueError, yaml.YAMLError) as e:
            msg = f"Failed to parse categories file {categories_path}: {e}"
            logger.error(msg)
            if is_json:
                output_json({"command": "classify", "status": "error", "error": msg})
            return 1

    # Determine final categories list:
    # - If YAML file provided, use those
    # - Otherwise, use config categories
    categories = (
        yaml_categories if yaml_categories is not None else list(classifier_config.categories)
    )

    if not categories:
        msg = (
            "No categories defined. Provide categories via --categories YAML file "
            "or configure classifier.categories in your config file. "
            "Run 'config init' to generate a template."
        )
        logger.error(msg)
        if is_json:
            output_json({"command": "classify", "status": "error", "error": msg})
        return 1

    # Extract category names for the classifier
    category_names = [cat.name for cat in categories]

    # ------------------------------------------------------------------
    # 3. Apply CLI overrides to classifier config
    # ------------------------------------------------------------------
    cli_provider = getattr(args, "provider", None)
    cli_model = getattr(args, "model", None)
    cli_threshold = getattr(args, "confidence_threshold", None)
    cli_endpoint_id = getattr(args, "endpoint_id", None)

    provider = cli_provider or classifier_config.provider
    model_name = cli_model or classifier_config.model_name
    confidence_threshold = (
        cli_threshold if cli_threshold is not None else classifier_config.confidence_threshold
    )
    runpod_endpoint_id = cli_endpoint_id or classifier_config.runpod_endpoint_id

    # Build effective classifier config:
    # When YAML categories or CLI overrides are present, construct a new config.
    # Otherwise, use the config's classifier config as-is.
    has_overrides = (
        yaml_categories is not None
        or cli_provider
        or cli_model
        or cli_threshold is not None
        or cli_endpoint_id
    )
    if has_overrides:
        effective_config = ClassifierConfig(
            provider=provider,
            model_name=model_name,
            ollama_base_url=classifier_config.ollama_base_url,
            runpod_endpoint_id=runpod_endpoint_id,
            api_key_env_var=classifier_config.api_key_env_var,
            confidence_threshold=confidence_threshold,
            max_tokens=classifier_config.max_tokens,
            temperature=classifier_config.temperature,
            categories=yaml_categories if yaml_categories is not None else [],
        )
    else:
        effective_config = classifier_config

    # ------------------------------------------------------------------
    # 4. Load corpus
    # ------------------------------------------------------------------
    corpus, err = _load_corpus(args, is_json=is_json)
    if err is not None:
        return err

    # ------------------------------------------------------------------
    # 5. Dry-run mode: preview and exit
    # ------------------------------------------------------------------
    if is_dry_run:
        if is_json:
            output_json(
                {
                    "command": "classify",
                    "status": "success",
                    "dry_run": True,
                    "provider": provider,
                    "model": model_name,
                    "confidence_threshold": confidence_threshold,
                    "total_emails": len(corpus.emails),
                    "categories": [cat.name for cat in categories],
                }
            )
        else:
            _print_dry_run_preview(corpus, categories, provider, model_name, confidence_threshold)
        return 0

    # ------------------------------------------------------------------
    # 6. Handle empty corpus
    # ------------------------------------------------------------------
    if not corpus.emails:
        report = CategorizationReport(
            total_emails=0,
            categorized_count=0,
            uncategorized_count=0,
            coverage_percentage=0.0,
            categories_used={},
            categorizations=[],
        )
        output_path = getattr(args, "output", None) or PathConfig.get_categorization_report_path()
        save_json(report.model_dump(mode="json"), output_path)

        if is_json:
            output_json(
                {
                    "command": "classify",
                    "status": "success",
                    "dry_run": False,
                    "provider": provider,
                    "model": model_name,
                    "total_emails": 0,
                    "output_file": str(output_path),
                    "stats": {
                        "total_emails": 0,
                        "categorized_count": 0,
                        "uncategorized_count": 0,
                        "coverage_percentage": 0.0,
                        "categories_used": 0,
                    },
                }
            )
        else:
            logger.info("Corpus is empty. No emails to classify.")

        return 0

    # ------------------------------------------------------------------
    # 7. Create classifier and classify emails
    # ------------------------------------------------------------------
    try:
        classifier = LLMClassifier(effective_config)

        categorizations: list[EmailCategorization] = []
        categories_used: dict[str, int] = {}
        categorized_count = 0
        total = len(corpus.emails)

        for idx, email in enumerate(corpus.emails, start=1):
            logger.info(f"Classifying email {idx}/{total}: {email.id}")

            result = classifier.classify(email, category_names)

            # Check confidence threshold
            if result.confidence < confidence_threshold:
                cat_result = EmailCategorization.uncategorized(email_id=email.id)
            else:
                cat_result = EmailCategorization(
                    email_id=email.id,
                    primary_category=CategoryAssignment(
                        category_name=result.category_name,
                        confidence=result.confidence,
                        source=result.source,
                    ),
                )
                categorized_count += 1
                categories_used[result.category_name] = (
                    categories_used.get(result.category_name, 0) + 1
                )

            categorizations.append(cat_result)

        uncategorized_count = total - categorized_count
        coverage = round((categorized_count / total) * 100, 2) if total > 0 else 0.0

        report = CategorizationReport(
            total_emails=total,
            categorized_count=categorized_count,
            uncategorized_count=uncategorized_count,
            coverage_percentage=coverage,
            categories_used=categories_used,
            categorizations=categorizations,
        )

    except ClassifierConnectionError as e:
        msg = f"Cannot connect to LLM service: {e}"
        if e.recovery_hint:
            msg += f"\n  Hint: {e.recovery_hint}"
        logger.error(msg)
        if is_json:
            output_json({"command": "classify", "status": "error", "error": str(e)})
        return 1
    except ClassificationError as e:
        msg = f"Classification failed: {e}"
        if e.recovery_hint:
            msg += f"\n  Hint: {e.recovery_hint}"
        logger.error(msg)
        if is_json:
            output_json({"command": "classify", "status": "error", "error": str(e)})
        return 1
    except Exception as e:
        logger.error(f"Classification failed: {e}", exc_info=True)
        if is_json:
            output_json({"command": "classify", "status": "error", "error": str(e)})
        return 1

    # ------------------------------------------------------------------
    # 8. Output results
    # ------------------------------------------------------------------
    duration = time.time() - start_time
    output_path = getattr(args, "output", None) or PathConfig.get_categorization_report_path()

    if is_json:
        output_json(
            {
                "command": "classify",
                "status": "success",
                "dry_run": False,
                "provider": provider,
                "model": model_name,
                "duration_seconds": round(duration, 2),
                "output_file": str(output_path),
                "stats": {
                    "total_emails": report.total_emails,
                    "categorized_count": report.categorized_count,
                    "uncategorized_count": report.uncategorized_count,
                    "coverage_percentage": round(report.coverage_percentage, 1),
                    "categories_used": report.category_count,
                },
            }
        )
    else:
        _print_classification_summary(report, verbose=is_verbose)

    # Save report
    save_json(report.model_dump(mode="json"), output_path)
    logger.info(f"Classification report saved to {output_path}")

    return 0
