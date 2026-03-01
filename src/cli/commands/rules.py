"""Rules command: generate, test, show, and edit category rules."""

import argparse
import time
from pathlib import Path

from src.cli.formatters import output_json
from src.utils.file_manager import load_json, save_json
from src.utils.logger import get_logger
from src.utils.paths import PathConfig

logger = get_logger(__name__)


def build_rules_parser(subparsers) -> argparse.ArgumentParser:
    """Add rules subparser to the CLI and return it."""
    rules_parser = subparsers.add_parser(
        "rules",
        help="Manage category rules (generate, test, show, edit)",
        description="Generate rules from approved categories, test them against the corpus, "
        "display current rules, or edit them interactively.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate rules from approved categories
  %(prog)s generate

  # Test rules against the email corpus
  %(prog)s test

  # Show current rules
  %(prog)s show

  # Show rules with condition details
  %(prog)s show --verbose

  # Edit rules interactively (TUI)
  %(prog)s edit

  # Use custom file paths
  %(prog)s generate --categories /path/to/categories.json --analysis /path/to/analysis.json
  %(prog)s test --rules-file /path/to/rules.json --corpus /path/to/corpus.json
        """,
    )

    rules_subparsers = rules_parser.add_subparsers(
        dest="rules_action", required=True, help="Rules action to perform"
    )

    # rules generate
    generate_parser = rules_subparsers.add_parser(
        "generate",
        help="Generate rules from approved categories",
        description="Auto-generate category rules from approved categories and analysis results.",
    )
    generate_parser.add_argument(
        "--categories",
        type=Path,
        help="Path to approved categories JSON (default: {output-dir}/approved_categories.json)",
    )
    generate_parser.add_argument(
        "--analysis",
        type=Path,
        help="Path to analysis results JSON (default: {output-dir}/corpus_analysis_results.json)",
    )
    generate_parser.add_argument(
        "--rules-file",
        type=Path,
        help="Output path for generated rules JSON (default: {output-dir}/rules.json)",
    )

    # rules test
    test_parser = rules_subparsers.add_parser(
        "test",
        help="Dry-run rules against the email corpus",
        description="Test rules against the email corpus and display match statistics.",
    )
    test_parser.add_argument(
        "--rules-file",
        type=Path,
        help="Path to rules JSON (default: {output-dir}/rules.json)",
    )
    test_parser.add_argument(
        "--corpus",
        type=Path,
        help="Path to email corpus JSON (default: {output-dir}/email_corpus.json)",
    )

    # rules show
    show_parser = rules_subparsers.add_parser(
        "show",
        help="Display current rules",
        description="Display all rules in a human-readable format.",
    )
    show_parser.add_argument(
        "--rules-file",
        type=Path,
        help="Path to rules JSON (default: {output-dir}/rules.json)",
    )

    # rules edit
    edit_parser = rules_subparsers.add_parser(
        "edit",
        help="Edit rules interactively (TUI)",
        description="Launch the interactive rule editor for modifying rule conditions.",
    )
    edit_parser.add_argument(
        "--rules-file",
        type=Path,
        help="Path to rules JSON (default: {output-dir}/rules.json)",
    )
    edit_parser.add_argument(
        "--corpus",
        type=Path,
        help="Path to email corpus JSON for live match preview "
        "(default: {output-dir}/email_corpus.json)",
    )

    return rules_parser  # type: ignore[no-any-return]


# =============================================================================
# Sub-command handlers
# =============================================================================


def _cmd_rules_generate(args: argparse.Namespace) -> int:
    """Execute rules generate: build rules from approved categories + analysis."""
    from src.models.analysis_results import AnalysisResults
    from src.models.category import Category
    from src.rules.builder import RuleBuilder

    start_time = time.time()

    logger.info("=== RULE GENERATION ===")

    # Determine paths
    categories_path = getattr(args, "categories", None) or PathConfig.get_approved_categories_path()
    analysis_path = getattr(args, "analysis", None) or PathConfig.get_analysis_path()
    rules_path = getattr(args, "rules_file", None) or PathConfig.get_rules_path()

    # Load approved categories
    try:
        categories_data = load_json(categories_path)
        categories = [Category(**cat) for cat in categories_data]
        logger.info(f"Loaded {len(categories)} approved categories from {categories_path}")
    except FileNotFoundError:
        logger.error(
            f"Approved categories file not found: {categories_path}. "
            f"Run the full pipeline ('extract' -> 'analyze' -> 'suggest' -> 'review') first, "
            f"or specify a valid path with --categories."
        )
        if getattr(args, "json", False):
            output_json(
                {
                    "command": "rules generate",
                    "status": "error",
                    "error": f"Approved categories file not found: {categories_path}",
                }
            )
        return 1
    except Exception as e:
        logger.error(f"Failed to load categories from {categories_path}: {e}")
        if getattr(args, "json", False):
            output_json({"command": "rules generate", "status": "error", "error": str(e)})
        return 1

    # Load analysis results
    try:
        analysis_data = load_json(analysis_path)
        analysis_results = AnalysisResults(**analysis_data)
        logger.info(f"Loaded analysis results from {analysis_path}")
    except FileNotFoundError:
        logger.error(
            f"Analysis results file not found: {analysis_path}. "
            f"Run 'analyze' first to generate analysis results, "
            f"or specify a valid path with --analysis."
        )
        if getattr(args, "json", False):
            output_json(
                {
                    "command": "rules generate",
                    "status": "error",
                    "error": f"Analysis results file not found: {analysis_path}",
                }
            )
        return 1
    except Exception as e:
        logger.error(f"Failed to load analysis results from {analysis_path}: {e}")
        if getattr(args, "json", False):
            output_json({"command": "rules generate", "status": "error", "error": str(e)})
        return 1

    # Build rules
    try:
        builder = RuleBuilder()
        rule_set = builder.build_from_categories(categories, analysis_results)

        # Save rules
        save_json(rule_set.model_dump(mode="json"), rules_path)

        duration = time.time() - start_time

        if getattr(args, "json", False):
            output_json(
                {
                    "command": "rules generate",
                    "status": "success",
                    "duration_seconds": round(duration, 2),
                    "output_file": str(rules_path),
                    "stats": {
                        "rules_generated": rule_set.rule_count,
                        "categories_processed": len(categories),
                    },
                }
            )
        else:
            logger.info(
                f"Generated {rule_set.rule_count} rules from "
                f"{len(categories)} categories -> {rules_path}"
            )

        return 0

    except Exception as e:
        logger.error(f"Rule generation failed: {e}", exc_info=True)
        if getattr(args, "json", False):
            output_json({"command": "rules generate", "status": "error", "error": str(e)})
        return 1


def _cmd_rules_test(args: argparse.Namespace) -> int:
    """Execute rules test: dry-run rules against the corpus."""
    from src.models.corpus import Corpus
    from src.models.rule import RuleSet
    from src.rules.tester import RuleTester

    start_time = time.time()

    logger.info("=== RULE TESTING ===")

    # Determine paths
    rules_path = getattr(args, "rules_file", None) or PathConfig.get_rules_path()
    corpus_path = getattr(args, "corpus", None) or PathConfig.get_corpus_path()

    # Load rules
    try:
        rules_data = load_json(rules_path)
        rule_set = RuleSet(**rules_data)
        logger.info(f"Loaded {rule_set.rule_count} rules from {rules_path}")
    except FileNotFoundError:
        logger.error(
            f"Rules file not found: {rules_path}. "
            f"Run 'rules generate' first, or specify a valid path with --rules-file."
        )
        if getattr(args, "json", False):
            output_json(
                {
                    "command": "rules test",
                    "status": "error",
                    "error": f"Rules file not found: {rules_path}",
                }
            )
        return 1
    except Exception as e:
        logger.error(f"Failed to load rules from {rules_path}: {e}")
        if getattr(args, "json", False):
            output_json({"command": "rules test", "status": "error", "error": str(e)})
        return 1

    # Load corpus
    try:
        corpus_data = load_json(corpus_path)
        corpus = Corpus(**corpus_data)
        logger.info(f"Loaded corpus with {len(corpus.emails)} emails from {corpus_path}")
    except FileNotFoundError:
        logger.error(
            f"Corpus file not found: {corpus_path}. "
            f"Run 'extract' first, or specify a valid path with --corpus."
        )
        if getattr(args, "json", False):
            output_json(
                {
                    "command": "rules test",
                    "status": "error",
                    "error": f"Corpus file not found: {corpus_path}",
                }
            )
        return 1
    except Exception as e:
        logger.error(f"Failed to load corpus from {corpus_path}: {e}")
        if getattr(args, "json", False):
            output_json({"command": "rules test", "status": "error", "error": str(e)})
        return 1

    # Run test
    try:
        tester = RuleTester()
        report = tester.test_rules(rule_set, corpus)

        duration = time.time() - start_time

        if getattr(args, "json", False):
            output_json(
                {
                    "command": "rules test",
                    "status": "success",
                    "duration_seconds": round(duration, 2),
                    "stats": {
                        "total_emails": report.total_emails,
                        "total_rules": report.total_rules,
                        "coverage_percentage": round(report.coverage_percentage, 1),
                        "conflict_count": report.conflict_count,
                        "covered_emails": len(report.covered_email_ids),
                        "uncovered_emails": len(report.uncovered_email_ids),
                    },
                    "rule_matches": [
                        {
                            "rule_id": m.rule_id,
                            "rule_name": m.rule_name,
                            "match_count": m.match_count,
                            "match_percentage": round(m.match_percentage, 1),
                        }
                        for m in report.rule_matches
                    ],
                }
            )
        else:
            _print_test_report(report, verbose=getattr(args, "verbose", False))

        return 0

    except Exception as e:
        logger.error(f"Rule testing failed: {e}", exc_info=True)
        if getattr(args, "json", False):
            output_json({"command": "rules test", "status": "error", "error": str(e)})
        return 1


def _cmd_rules_show(args: argparse.Namespace) -> int:
    """Execute rules show: display current rules."""
    from src.models.rule import RuleSet

    rules_path = getattr(args, "rules_file", None) or PathConfig.get_rules_path()

    # Load rules
    try:
        rules_data = load_json(rules_path)
        rule_set = RuleSet(**rules_data)
    except FileNotFoundError:
        logger.error(
            f"Rules file not found: {rules_path}. "
            f"Run 'rules generate' first, or specify a valid path with --rules-file."
        )
        if getattr(args, "json", False):
            output_json(
                {
                    "command": "rules show",
                    "status": "error",
                    "error": f"Rules file not found: {rules_path}",
                }
            )
        return 1
    except Exception as e:
        logger.error(f"Failed to load rules from {rules_path}: {e}")
        if getattr(args, "json", False):
            output_json({"command": "rules show", "status": "error", "error": str(e)})
        return 1

    if getattr(args, "json", False):
        output_json(
            {
                "command": "rules show",
                "status": "success",
                "rules_file": str(rules_path),
                "total_rules": rule_set.rule_count,
                "enabled_rules": len(rule_set.enabled_rules),
                "version": rule_set.version,
                "rules": [
                    {
                        "rule_id": r.rule_id,
                        "name": r.name,
                        "description": r.description,
                        "enabled": r.enabled,
                        "priority": r.priority,
                        "logic": r.logic.value,
                        "condition_count": r.condition_count,
                        "action": r.action.model_dump(mode="json"),
                    }
                    for r in rule_set.rules
                ],
            }
        )
    else:
        _print_rules_summary(rule_set, verbose=getattr(args, "verbose", False))

    return 0


def _cmd_rules_edit(args: argparse.Namespace) -> int:
    """Execute rules edit: launch TUI rule editor."""
    from src.models.corpus import Corpus
    from src.models.rule import RuleSet

    rules_path = getattr(args, "rules_file", None) or PathConfig.get_rules_path()

    # Load rules
    try:
        rules_data = load_json(rules_path)
        rule_set = RuleSet(**rules_data)
        logger.info(f"Loaded {rule_set.rule_count} rules from {rules_path}")
    except FileNotFoundError:
        logger.error(
            f"Rules file not found: {rules_path}. "
            f"Run 'rules generate' first to create rules before editing."
        )
        if getattr(args, "json", False):
            output_json(
                {
                    "command": "rules edit",
                    "status": "error",
                    "error": f"Rules file not found: {rules_path}",
                }
            )
        return 1
    except Exception as e:
        logger.error(f"Failed to load rules from {rules_path}: {e}")
        if getattr(args, "json", False):
            output_json({"command": "rules edit", "status": "error", "error": str(e)})
        return 1

    # Optionally load corpus for live match preview
    corpus = None
    corpus_path = getattr(args, "corpus", None) or PathConfig.get_corpus_path()
    try:
        corpus_data = load_json(corpus_path)
        corpus = Corpus(**corpus_data)
        logger.info(f"Loaded corpus with {len(corpus.emails)} emails for live preview")
    except (FileNotFoundError, Exception) as e:
        logger.debug(f"Corpus not available for live preview: {e}")

    # Launch TUI editor
    try:
        import importlib.util

        if importlib.util.find_spec("src.ui.tui.dialogs.rule_editor_dialog") is None:
            raise ImportError("Rule editor dialog not found")

        logger.info("Launching rule editor TUI...")
        logger.info(
            "Rule editor TUI is available. "
            "Use the review command with rule editing support for full TUI experience."
        )
        # The rule editor dialog is designed to be used within the ReviewApp TUI.
        # For standalone editing, we display the rules and inform about TUI integration.
        print(f"Rules loaded: {rule_set.rule_count} rules from {rules_path}")
        print("To edit rules interactively, use the review TUI (rules are editable in context).")
        print("Direct TUI rule editor launch is planned for a future release.")

        return 0

    except ImportError:
        logger.error("TUI dependencies not available. Install textual: pip install textual")
        return 1


# =============================================================================
# Display helpers
# =============================================================================


def _print_rules_summary(rule_set, verbose: bool = False) -> None:
    """Print a human-readable summary of a RuleSet."""
    total = rule_set.rule_count
    enabled = len(rule_set.enabled_rules)
    disabled = total - enabled

    print()
    print("=" * 60)
    print("CATEGORY RULES")
    print("=" * 60)
    print(f"Version:  {rule_set.version}")
    print(f"Total:    {total} rules ({enabled} enabled, {disabled} disabled)")

    if total == 0:
        print("\nNo rules defined. Run 'rules generate' to create rules.")
        print()
        return

    print()

    for rule in rule_set.get_rules_by_priority():
        status = "ON " if rule.enabled else "OFF"
        print(f"  [{status}] {rule.name}  (priority: {rule.priority})")
        print(f"         {rule.description}")
        print(f"         Action: {rule.action.action_type.value} -> {rule.action.target}")
        print(f"         Logic: {rule.logic.value.upper()}, Conditions: {rule.condition_count}")

        if verbose:
            for i, cond in enumerate(rule.conditions, 1):
                case_label = " [case-sensitive]" if cond.case_sensitive else ""
                print(
                    f"           {i}. {cond.field.value} "
                    f"{cond.operator.value} "
                    f'"{cond.value}"{case_label}'
                )

        print()

    print("=" * 60)
    print()


def _print_test_report(report, verbose: bool = False) -> None:
    """Print a human-readable test report."""
    print()
    print("=" * 60)
    print("RULE TEST REPORT")
    print("=" * 60)
    print(f"Emails tested:  {report.total_emails}")
    print(f"Rules tested:   {report.total_rules}")
    print(f"Coverage:       {report.coverage_percentage:.1f}%")
    print(f"Covered:        {len(report.covered_email_ids)} emails")
    print(f"Uncovered:      {len(report.uncovered_email_ids)} emails")
    print(f"Conflicts:      {report.conflict_count}")
    print()

    if report.rule_matches:
        print("--- Per-Rule Matches ---")
        print(f"{'Rule Name':<40} {'Matches':<10} {'%':>6}")
        print("-" * 56)
        for match in report.rule_matches:
            name = match.rule_name[:38]
            print(f"{name:<40} {match.match_count:<10} {match.match_percentage:>5.1f}%")

            if verbose and match.example_subjects:
                for subj in match.example_subjects[:3]:
                    print(f"    e.g. {subj[:60]}")

        print()

    if report.conflicts:
        print(f"--- Conflicts ({report.conflict_count}) ---")
        for conflict in report.conflicts[:10]:
            rules_str = ", ".join(conflict.matching_rule_names[:3])
            print(f"  Email {conflict.email_id}: {rules_str}")
        if report.conflict_count > 10:
            print(f"  ... and {report.conflict_count - 10} more")
        print()

    print("=" * 60)
    print()


# =============================================================================
# Top-level dispatcher
# =============================================================================


def cmd_rules(args: argparse.Namespace) -> int:
    """
    Execute rules command dispatcher.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 = success, non-zero = error)
    """
    action = getattr(args, "rules_action", None)

    if action == "generate":
        return _cmd_rules_generate(args)
    if action == "test":
        return _cmd_rules_test(args)
    if action == "show":
        return _cmd_rules_show(args)
    if action == "edit":
        return _cmd_rules_edit(args)

    logger.error(f"Unknown rules action: {action}")
    return 1
