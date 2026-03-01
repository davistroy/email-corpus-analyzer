"""Categorize command: apply rules to classify individual emails (Phase 4, Item 4.5)."""

import argparse
import time
from pathlib import Path

from src.cli.formatters import output_json
from src.utils.file_manager import load_json, save_json
from src.utils.logger import get_logger
from src.utils.paths import PathConfig

logger = get_logger(__name__)


def build_categorize_parser(subparsers) -> argparse.ArgumentParser:
    """Add categorize subparser to the CLI and return it."""
    categorize_parser = subparsers.add_parser(
        "categorize",
        help="Categorize emails using approved rules",
        description="Apply category rules to classify every email in the corpus. "
        "Produces a categorization report with per-email assignments and coverage metrics.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run categorization against corpus
  %(prog)s

  # Preview categorization without saving
  %(prog)s --dry-run

  # Generate and display coverage report
  %(prog)s --report

  # Use conflict resolution with specificity strategy
  %(prog)s --resolve --strategy specificity

  # Machine-readable JSON output
  %(prog)s --json

  # Verbose per-email detail
  %(prog)s --verbose

  # Custom file paths
  %(prog)s --corpus /path/to/corpus.json --rules-file /path/to/rules.json
        """,
    )

    categorize_parser.add_argument(
        "--report",
        action="store_true",
        default=False,
        help="Generate and display coverage report after categorization",
    )
    categorize_parser.add_argument(
        "--resolve",
        action="store_true",
        default=False,
        help="Use conflict resolution for emails matching multiple rules",
    )
    categorize_parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Preview categorization without saving results to disk",
    )
    categorize_parser.add_argument(
        "--strategy",
        choices=["priority", "specificity", "historical"],
        default="priority",
        help="Conflict resolution strategy (default: priority). "
        "Only applies when --resolve is specified.",
    )
    categorize_parser.add_argument(
        "--corpus",
        type=Path,
        help="Path to email corpus JSON (default: {output-dir}/email_corpus.json)",
    )
    categorize_parser.add_argument(
        "--rules-file",
        type=Path,
        help="Path to rules JSON (default: {output-dir}/rules.json)",
    )
    categorize_parser.add_argument(
        "--output",
        type=Path,
        help="Output path for categorization report JSON "
        "(default: {output-dir}/categorization_report.json)",
    )

    return categorize_parser  # type: ignore[no-any-return]


# =============================================================================
# Load helpers
# =============================================================================


def _load_rules(args: argparse.Namespace):
    """Load the RuleSet from disk. Returns (rule_set, error_code) tuple."""
    from src.models.rule import RuleSet

    rules_path = getattr(args, "rules_file", None) or PathConfig.get_rules_path()

    try:
        rules_data = load_json(rules_path)
        rule_set = RuleSet(**rules_data)
        logger.info(f"Loaded {rule_set.rule_count} rules from {rules_path}")
        return rule_set, None
    except FileNotFoundError:
        msg = (
            f"Rules file not found: {rules_path}. "
            f"Run 'rules generate' first, or specify a valid path with --rules-file."
        )
        logger.error(msg)
        if getattr(args, "json", False):
            output_json({"command": "categorize", "status": "error", "error": msg})
        return None, 1
    except Exception as e:
        logger.error(f"Failed to load rules from {rules_path}: {e}")
        if getattr(args, "json", False):
            output_json({"command": "categorize", "status": "error", "error": str(e)})
        return None, 1


def _load_corpus(args: argparse.Namespace):
    """Load the Corpus from disk. Returns (corpus, error_code) tuple."""
    from src.models.corpus import Corpus

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
        if getattr(args, "json", False):
            output_json({"command": "categorize", "status": "error", "error": msg})
        return None, 1
    except Exception as e:
        logger.error(f"Failed to load corpus from {corpus_path}: {e}")
        if getattr(args, "json", False):
            output_json({"command": "categorize", "status": "error", "error": str(e)})
        return None, 1


# =============================================================================
# Display helpers
# =============================================================================


def _print_categorization_summary(report, verbose: bool = False) -> None:
    """Print a human-readable categorization summary."""
    print()
    print("=" * 60)
    print("CATEGORIZATION RESULTS")
    print("=" * 60)
    print(f"Total emails:       {report.total_emails}")
    print(f"Categorized:        {report.categorized_count}")
    print(f"Uncategorized:      {report.uncategorized_count}")
    print(f"Coverage:           {report.coverage_percentage:.1f}%")
    print(f"Categories used:    {report.category_count}")
    print(f"Multi-category:     {report.multi_category_count}")
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
                secondary_str = ""
                if cat.secondary_categories:
                    sec_names = [s.category_name for s in cat.secondary_categories]
                    secondary_str = f" (also: {', '.join(sec_names)})"
                print(
                    f"  {cat.email_id}: {primary.category_name} "
                    f"(confidence: {primary.confidence:.2f}){secondary_str}"
                )
        print()

    print("=" * 60)
    print()


# =============================================================================
# Main command handler
# =============================================================================


def cmd_categorize(args: argparse.Namespace) -> int:
    """
    Execute categorize command.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 = success, non-zero = error)
    """
    from src.categorizer.categorizer import EmailCategorizer
    from src.categorizer.conflict_resolver import ConflictResolution, ConflictResolver
    from src.categorizer.coverage_reporter import CoverageReporter

    start_time = time.time()

    logger.info("=== EMAIL CATEGORIZATION ===")

    # Load rules
    rule_set, err = _load_rules(args)
    if err is not None:
        return err

    # Load corpus
    corpus, err = _load_corpus(args)
    if err is not None:
        return err

    # Run categorization
    try:
        categorizer = EmailCategorizer()
        is_dry_run = getattr(args, "dry_run", False)
        is_report = getattr(args, "report", False)
        is_resolve = getattr(args, "resolve", False)
        is_json = getattr(args, "json", False)
        is_verbose = getattr(args, "verbose", False)
        strategy_name = getattr(args, "strategy", "priority")
        output_path = getattr(args, "output", None) or PathConfig.get_categorization_report_path()

        # Run categorization
        report = categorizer.categorize_corpus(corpus, rule_set)

        # If --resolve, run conflict resolution on multi-match emails
        if is_resolve:
            strategy = ConflictResolution(strategy_name)
            resolver = ConflictResolver(strategy=strategy)

            resolved_count = 0
            for cat_result in report.categorizations:
                if cat_result.has_multiple_categories and not cat_result.is_uncategorized:
                    # Get matching rules for this email
                    email = next((e for e in corpus.emails if e.id == cat_result.email_id), None)
                    if email is not None:
                        matched_rules = [
                            r
                            for r in rule_set.enabled_rules
                            if r.rule_id in cat_result.matched_rules
                        ]
                        if len(matched_rules) > 1:
                            resolution = resolver.resolve(email, matched_rules)
                            # Update primary category to the resolved choice
                            cat_result.primary_category = resolution.chosen
                            cat_result.secondary_categories = resolution.alternatives
                            resolved_count += 1

            if resolved_count > 0:
                logger.info(
                    f"Resolved {resolved_count} multi-category conflicts using {strategy_name}"
                )

        duration = time.time() - start_time

        # Display output
        if is_report:
            # Generate and display coverage report
            coverage_reporter = CoverageReporter()
            coverage_analysis = coverage_reporter.analyze_coverage(report, corpus)

            if is_json:
                output_json(
                    {
                        "command": "categorize --report",
                        "status": "success",
                        "dry_run": is_dry_run,
                        "duration_seconds": round(duration, 2),
                        "coverage": coverage_analysis.model_dump(mode="json"),
                    }
                )
            else:
                formatted = coverage_reporter.format_report(coverage_analysis)
                print(formatted)
        elif is_json:
            output_json(
                {
                    "command": "categorize",
                    "status": "success",
                    "dry_run": is_dry_run,
                    "duration_seconds": round(duration, 2),
                    "output_file": str(output_path) if not is_dry_run else None,
                    "stats": {
                        "total_emails": report.total_emails,
                        "categorized_count": report.categorized_count,
                        "uncategorized_count": report.uncategorized_count,
                        "coverage_percentage": round(report.coverage_percentage, 1),
                        "categories_used": report.category_count,
                        "multi_category_count": report.multi_category_count,
                    },
                }
            )
        else:
            _print_categorization_summary(report, verbose=is_verbose)

        # Save unless dry-run
        if not is_dry_run:
            save_json(report.model_dump(mode="json"), output_path)
            logger.info(f"Categorization report saved to {output_path}")

        return 0

    except Exception as e:
        logger.error(f"Categorization failed: {e}", exc_info=True)
        if getattr(args, "json", False):
            output_json({"command": "categorize", "status": "error", "error": str(e)})
        return 1
