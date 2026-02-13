#!/usr/bin/env python3
"""
Email Corpus Extraction and Analysis System - CLI Entry Point.

Commands:
  extract   - Extract emails from M365/Hotmail
  analyze   - Analyze email corpus for patterns
  suggest   - Generate category suggestions
  review    - Interactively review and approve categories
  pipeline  - Run complete end-to-end workflow
  config    - Manage configuration (init, show)
  info      - Show corpus statistics
  export    - Export categories to CSV or HTML format

All commands support --output-dir to specify custom output location.
Default output directory: ~/data/outputs
"""
import argparse
import json
import logging
import re
import sys
import time
from datetime import datetime
from pathlib import Path

from src import __version__
from src.config.loader import (
    ConfigLoadError,
    generate_template,
    get_global_config_path,
    get_project_config_path,
    load_config,
    show_resolved_config,
)
from src.utils.file_manager import load_json, save_json
from src.utils.logger import get_logger
from src.utils.paths import PathConfig

logger = get_logger(__name__)


# Email validation regex pattern (RFC 5322 simplified)
EMAIL_REGEX = re.compile(
    r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
)


def validate_email_format(email: str) -> bool:
    """
    Validate email address format.

    Args:
        email: Email address to validate

    Returns:
        True if valid email format, False otherwise
    """
    if not email or not isinstance(email, str):
        return False
    return bool(EMAIL_REGEX.match(email.strip()))


def output_json(data: dict) -> None:
    """
    Output data as formatted JSON to stdout.

    Args:
        data: Dictionary to output as JSON
    """
    print(json.dumps(data, indent=2, default=str))


def _show_cluster_analysis(corpus, args: argparse.Namespace) -> int:
    """
    Show cluster analysis report with k vs score table and recommendation.

    Args:
        corpus: Loaded email corpus
        args: Parsed command-line arguments

    Returns:
        Exit code (0 = success, non-zero = error)
    """
    from src.analyzers import ElbowOptimizer, SilhouetteOptimizer
    from src.analyzers.semantic_analyzer import SemanticAnalyzer

    logger.info("=== CLUSTER ANALYSIS REPORT ===")

    # Generate embeddings first
    analyzer = SemanticAnalyzer()
    analyzer._ensure_model_loaded()

    texts = [email.combined_text_with_limit() for email in corpus.emails]
    embeddings = analyzer.model.encode(
        texts,
        show_progress_bar=True,
        convert_to_numpy=True
    )

    # Run both optimization methods
    cluster_method = getattr(args, 'cluster_method', 'silhouette')
    max_k = min(15, len(corpus.emails) - 1)

    if max_k < 2:
        logger.error("Corpus too small for cluster analysis (need at least 3 emails)")
        return 1

    elbow_optimizer = ElbowOptimizer(max_k=max_k)
    silhouette_optimizer = SilhouetteOptimizer(max_k=max_k)

    logger.info("Running elbow method analysis...")
    elbow_result = elbow_optimizer.find_optimal_k(embeddings)

    logger.info("Running silhouette method analysis...")
    silhouette_result = silhouette_optimizer.find_optimal_k(embeddings)

    # Use selected method for recommendation
    if cluster_method == "elbow":
        recommended_k = elbow_result.optimal_k
        confidence = elbow_result.confidence_score
    else:
        recommended_k = silhouette_result.optimal_k
        confidence = silhouette_result.confidence_score

    if getattr(args, 'json', False):
        output_json({
            "command": "analyze",
            "cluster_analysis": True,
            "elbow_method": {
                "optimal_k": elbow_result.optimal_k,
                "confidence": elbow_result.confidence_score,
                "k_scores": elbow_result.k_scores
            },
            "silhouette_method": {
                "optimal_k": silhouette_result.optimal_k,
                "confidence": silhouette_result.confidence_score,
                "k_scores": silhouette_result.k_scores
            },
            "recommendation": {
                "method": cluster_method,
                "optimal_k": recommended_k,
                "confidence": confidence
            }
        })
    else:
        # Print k vs score tables
        print("\n" + "=" * 60)
        print("CLUSTER ANALYSIS REPORT")
        print("=" * 60)

        # Elbow method table
        print("\n--- Elbow Method (Inertia) ---")
        print(f"{'k':<6}{'Inertia':<15}{'Normalized':<12}")
        print("-" * 33)
        k_values = sorted(elbow_result.k_scores.keys())
        max_inertia = max(elbow_result.k_scores.values())
        for k in k_values:
            inertia = elbow_result.k_scores[k]
            normalized = inertia / max_inertia
            marker = " <-- ELBOW" if k == elbow_result.optimal_k else ""
            print(f"{k:<6}{inertia:<15.2f}{normalized:<12.3f}{marker}")

        # ASCII chart for elbow method
        print("\nElbow Curve:")
        _print_ascii_chart(elbow_result.k_scores, elbow_result.optimal_k, "Inertia")

        # Silhouette method table
        print("\n--- Silhouette Method ---")
        print(f"{'k':<6}{'Silhouette Score':<18}")
        print("-" * 24)
        k_values = sorted(silhouette_result.k_scores.keys())
        for k in k_values:
            score = silhouette_result.k_scores[k]
            marker = " <-- BEST" if k == silhouette_result.optimal_k else ""
            print(f"{k:<6}{score:<18.4f}{marker}")

        # ASCII chart for silhouette method
        print("\nSilhouette Curve:")
        _print_ascii_chart(silhouette_result.k_scores, silhouette_result.optimal_k, "Silhouette")

        # Recommendation
        print("\n" + "=" * 60)
        print("RECOMMENDATION")
        print("=" * 60)
        print(f"Method used: {cluster_method}")
        print(f"Optimal number of clusters: {recommended_k}")
        print(f"Confidence score: {confidence:.2f}")

        if elbow_result.optimal_k == silhouette_result.optimal_k:
            print("\nBoth methods agree on the optimal k!")
        else:
            print(f"\nNote: Elbow suggests k={elbow_result.optimal_k}, "
                  f"Silhouette suggests k={silhouette_result.optimal_k}")

        print()

    return 0


def _print_ascii_chart(k_scores: dict[int, float], optimal_k: int, label: str) -> None:
    """
    Print an ASCII chart representation of scores.

    Args:
        k_scores: Dictionary mapping k values to scores
        optimal_k: The optimal k value to highlight
        label: Label for the Y axis
    """
    k_values = sorted(k_scores.keys())
    scores = [k_scores[k] for k in k_values]

    min_score = min(scores)
    max_score = max(scores)
    score_range = max_score - min_score if max_score > min_score else 1.0

    chart_width = 40
    chart_height = 10

    # Normalize scores to chart height
    normalized = [(s - min_score) / score_range for s in scores]

    # Build chart rows (from top to bottom)
    for row in range(chart_height, -1, -1):
        row_level = row / chart_height
        line = ""
        for i, (k, norm_score) in enumerate(zip(k_values, normalized)):
            # For elbow (inertia), lower is better but curve goes down
            # For silhouette, higher is better
            if norm_score >= row_level:
                if k == optimal_k:
                    line += "*"
                else:
                    line += "#"
            else:
                line += " "
        print(f"  {line}")

    # Print x-axis
    print("  " + "-" * len(k_values))
    # Print k labels (truncated if needed)
    k_labels = "".join(str(k)[-1] for k in k_values)
    print(f"  {k_labels}")
    print(f"  k values (2-{max(k_values)})")


def create_parser() -> argparse.ArgumentParser:
    """
    Create CLI argument parser with all commands and options.

    Returns:
        Configured ArgumentParser
    """
    parser = argparse.ArgumentParser(
        prog="email-processor",
        description="Email Corpus Extraction and Analysis System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Extract emails to default location (~/data/outputs)
  %(prog)s extract --user-email user@hotmail.com

  # Extract to custom directory
  %(prog)s extract --user-email user@hotmail.com --output-dir ~/my-emails

  # Analyze existing corpus
  %(prog)s analyze --corpus ~/my-emails/email_corpus.json

  # Run complete pipeline
  %(prog)s pipeline --user-email user@hotmail.com --output-dir ~/analysis

  # Get corpus info
  %(prog)s info

For more information, see: specs/001-use-the-document/quickstart.md
        """
    )

    # Version flag
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}"
    )

    # Global options (available to all commands)
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Output directory for all files (default: ~/data/outputs)"
    )

    # Mutually exclusive group for verbose/quiet/json
    output_group = parser.add_mutually_exclusive_group()
    output_group.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose debug logging"
    )
    output_group.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Suppress INFO output, only show warnings and errors"
    )
    output_group.add_argument(
        "--json",
        action="store_true",
        help="Output results as machine-readable JSON"
    )

    parser.add_argument(
        "--config",
        type=Path,
        help="Path to custom configuration file (YAML)"
    )

    # Subcommands
    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
        help="Command to execute"
    )

    # ===== EXTRACT COMMAND =====
    extract_parser = subparsers.add_parser(
        "extract",
        help="Extract emails from Hotmail/Gmail inbox",
        description="Extract emails from M365/Hotmail or Gmail and save to JSON corpus file.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Extract from Hotmail (default)
  %(prog)s --user-email user@hotmail.com

  # Extract from Gmail
  %(prog)s --user-email user@gmail.com --source gmail

  # Extract from both accounts
  %(prog)s --user-email user@hotmail.com --source both --gmail-email user@gmail.com

  # Extract with larger batches
  %(prog)s --user-email user@hotmail.com --batch-size 1000

  # Incremental extraction (only new emails)
  %(prog)s --user-email user@hotmail.com --since-last

  # Preview without executing
  %(prog)s --user-email user@hotmail.com --dry-run
        """
    )
    extract_parser.add_argument(
        "--user-email",
        required=True,
        help="Primary email address (Hotmail/Outlook or Gmail)"
    )
    extract_parser.add_argument(
        "--source",
        type=str,
        choices=["hotmail", "gmail", "both"],
        default="hotmail",
        help="Email source: hotmail, gmail, or both (default: hotmail)"
    )
    extract_parser.add_argument(
        "--gmail-email",
        type=str,
        help="Gmail address (required when --source both, if different from --user-email)"
    )
    extract_parser.add_argument(
        "--corpus-file",
        type=Path,
        help="Custom path for corpus JSON (default: {output-dir}/email_corpus.json)"
    )
    extract_parser.add_argument(
        "--batch-size",
        type=int,
        default=500,
        help="Number of emails to fetch per batch (default: 500)"
    )
    extract_parser.add_argument(
        "--checkpoint-interval",
        type=int,
        default=100,
        help="Save checkpoint every N emails (default: 100)"
    )
    extract_parser.add_argument(
        "-n", "--dry-run",
        action="store_true",
        help="Show what would be done without actually executing"
    )
    extract_parser.add_argument(
        "--since-last",
        action="store_true",
        default=False,
        help="Incremental extraction: only fetch emails since last extraction (Task 4B.2)"
    )

    # ===== ANALYZE COMMAND =====
    analyze_parser = subparsers.add_parser(
        "analyze",
        help="Analyze email corpus for patterns",
        description="Run all 5 analyzers on email corpus and generate analysis results.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic analysis with default settings
  %(prog)s

  # Analyze with custom number of clusters
  %(prog)s --num-clusters 15

  # Auto-determine optimal clusters using silhouette method
  %(prog)s --auto-clusters

  # Auto-determine using elbow method
  %(prog)s --auto-clusters --cluster-method elbow

  # Show cluster analysis report
  %(prog)s --cluster-analysis

  # Incremental analysis (reuse cached embeddings)
  %(prog)s --incremental

  # Analyze custom corpus file
  %(prog)s --corpus /path/to/corpus.json

Note: --auto-clusters and --num-clusters are mutually exclusive.
      When using --auto-clusters, the --cluster-method flag determines
      which optimization method is used (default: silhouette).
        """
    )
    analyze_parser.add_argument(
        "--corpus",
        type=Path,
        help="Path to corpus JSON file (default: {output-dir}/email_corpus.json)"
    )
    analyze_parser.add_argument(
        "--num-clusters",
        type=int,
        default=10,
        help="Number of semantic clusters (default: 10)"
    )
    analyze_parser.add_argument(
        "--auto-clusters",
        action="store_true",
        default=False,
        help="Automatically determine optimal number of clusters"
    )
    analyze_parser.add_argument(
        "--cluster-method",
        type=str,
        choices=["elbow", "silhouette"],
        default="silhouette",
        help="Method to determine optimal clusters: elbow or silhouette (default: silhouette)"
    )
    analyze_parser.add_argument(
        "--cluster-analysis",
        action="store_true",
        default=False,
        help="Show cluster analysis report with k vs score table"
    )
    analyze_parser.add_argument(
        "--analysis-file",
        type=Path,
        help="Custom path for analysis results (default: {output-dir}/corpus_analysis_results.json)"
    )
    analyze_parser.add_argument(
        "-n", "--dry-run",
        action="store_true",
        help="Show what would be done without actually executing"
    )
    analyze_parser.add_argument(
        "--incremental",
        action="store_true",
        default=False,
        help="Use embedding cache for incremental analysis (Task 4B.4)"
    )

    # ===== SUGGEST COMMAND =====
    suggest_parser = subparsers.add_parser(
        "suggest",
        help="Generate category suggestions",
        description="Generate category suggestions from analysis results.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate suggestions with default settings
  %(prog)s

  # Require larger clusters for suggestions
  %(prog)s --min-cluster-percentage 10.0

  # Require more emails for sender-based categories
  %(prog)s --min-sender-count 50

  # Use custom analysis file
  %(prog)s --analysis /path/to/analysis.json

  # Preview without executing
  %(prog)s --dry-run
        """
    )
    suggest_parser.add_argument(
        "--analysis",
        type=Path,
        help="Path to analysis results JSON (default: {output-dir}/corpus_analysis_results.json)"
    )
    suggest_parser.add_argument(
        "--min-cluster-percentage",
        type=float,
        default=5.0,
        help="Minimum cluster size percentage for category generation (default: 5.0)"
    )
    suggest_parser.add_argument(
        "--min-sender-count",
        type=int,
        default=20,
        help="Minimum email count for sender-based categories (default: 20)"
    )
    suggest_parser.add_argument(
        "--suggestions-file",
        type=Path,
        help="Custom path for suggestions JSON (default: {output-dir}/category_suggestions.json)"
    )
    suggest_parser.add_argument(
        "-n", "--dry-run",
        action="store_true",
        help="Show what would be done without actually executing"
    )

    # ===== REVIEW COMMAND =====
    review_parser = subparsers.add_parser(
        "review",
        help="Interactively review category suggestions",
        description="Interactively review, rename, merge, or delete category suggestions.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive TUI review (default)
  %(prog)s

  # Use legacy CLI interface
  %(prog)s --no-tui

  # Auto-approve all suggestions (for automation)
  %(prog)s --headless

  # Skip cleanup of intermediate files
  %(prog)s --no-cleanup

  # Disable learning from review decisions
  %(prog)s --no-learning

Note: --headless and --no-tui are mutually exclusive in practice.
      --headless bypasses all interactive review.
        """
    )
    review_parser.add_argument(
        "--suggestions",
        type=Path,
        help="Path to suggestions JSON (default: {output-dir}/category_suggestions.json)"
    )
    review_parser.add_argument(
        "--approved-file",
        type=Path,
        help="Custom path for approved categories (default: {output-dir}/approved_categories.json)"
    )
    review_parser.add_argument(
        "--no-cleanup",
        action="store_true",
        help="Skip optional cleanup of intermediate files"
    )
    review_parser.add_argument(
        "-n", "--dry-run",
        action="store_true",
        help="Show what would be done without actually executing"
    )
    review_parser.add_argument(
        "--no-tui",
        action="store_true",
        help="Use legacy CLI interface instead of TUI"
    )
    review_parser.add_argument(
        "--headless",
        action="store_true",
        help="Auto-approve all suggestions without interactive review (for automation)"
    )
    review_parser.add_argument(
        "--no-learning",
        action="store_true",
        help="Disable feedback learning (don't log decisions or apply learned patterns)"
    )

    # ===== PIPELINE COMMAND =====
    pipeline_parser = subparsers.add_parser(
        "pipeline",
        help="Run complete end-to-end workflow",
        description="Run extract -> analyze -> suggest -> review -> optional cleanup.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run complete pipeline with TUI review
  %(prog)s --user-email user@hotmail.com

  # Run pipeline to custom directory
  %(prog)s --user-email user@hotmail.com --output-dir ~/my-analysis

  # Skip interactive review (auto-approve all)
  %(prog)s --user-email user@hotmail.com --skip-review

  # Use auto-clustering
  %(prog)s --user-email user@hotmail.com --auto-clusters

  # Preview all stages without executing
  %(prog)s --user-email user@hotmail.com --dry-run

The pipeline runs these stages in order:
  1. extract  - Fetch emails from M365
  2. analyze  - Run all analyzers
  3. suggest  - Generate categories
  4. review   - Interactive approval
        """
    )
    pipeline_parser.add_argument(
        "--user-email",
        required=True,
        help="Primary email address (Hotmail/Outlook or Gmail)"
    )
    pipeline_parser.add_argument(
        "--source",
        type=str,
        choices=["hotmail", "gmail", "both"],
        default="hotmail",
        help="Email source: hotmail, gmail, or both (default: hotmail)"
    )
    pipeline_parser.add_argument(
        "--gmail-email",
        type=str,
        help="Gmail address (required when --source both, if different from --user-email)"
    )
    pipeline_parser.add_argument(
        "--num-clusters",
        type=int,
        default=10,
        help="Number of semantic clusters (default: 10)"
    )
    pipeline_parser.add_argument(
        "--auto-clusters",
        action="store_true",
        default=False,
        help="Automatically determine optimal number of clusters"
    )
    pipeline_parser.add_argument(
        "--cluster-method",
        type=str,
        choices=["elbow", "silhouette"],
        default="silhouette",
        help="Method to determine optimal clusters: elbow or silhouette (default: silhouette)"
    )
    pipeline_parser.add_argument(
        "--no-cleanup",
        action="store_true",
        help="Skip optional cleanup of intermediate files"
    )
    pipeline_parser.add_argument(
        "--skip-review",
        action="store_true",
        help="Skip interactive review and auto-accept all suggestions"
    )
    pipeline_parser.add_argument(
        "-n", "--dry-run",
        action="store_true",
        help="Show what would be done without actually executing"
    )
    pipeline_parser.add_argument(
        "--no-tui",
        action="store_true",
        help="Use legacy CLI interface instead of TUI for review step"
    )
    pipeline_parser.add_argument(
        "--no-learning",
        action="store_true",
        help="Disable feedback learning (don't log decisions or apply learned patterns)"
    )

    # ===== INFO COMMAND =====
    info_parser = subparsers.add_parser(
        "info",
        help="Show corpus statistics",
        description="Display information about the email corpus without loading all data.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Show info for default corpus
  %(prog)s

  # Show info for custom corpus file
  %(prog)s --corpus /path/to/corpus.json

  # Output as JSON
  %(prog)s --json
        """
    )
    info_parser.add_argument(
        "--corpus",
        type=Path,
        help="Path to corpus JSON file (default: {output-dir}/email_corpus.json)"
    )

    # ===== EXPORT COMMAND (Task 5C.3, Phase 8 Track 8B.3) =====
    export_parser = subparsers.add_parser(
        "export",
        help="Export categories to CSV, HTML, or email rules format",
        description="Export approved categories to CSV, HTML, Outlook rules, or Gmail filters.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Export to CSV (Excel-compatible)
  %(prog)s --format csv

  # Export to HTML report
  %(prog)s --format html

  # Export to Outlook rules XML
  %(prog)s --format outlook-rules

  # Export to Gmail filters XML
  %(prog)s --format gmail-filters

  # Export to custom path
  %(prog)s --format csv --output /path/to/categories.csv

  # Export from custom input file
  %(prog)s --format html --input /path/to/categories.json

Import Instructions:
  Outlook: File -> Manage Rules & Alerts -> Options -> Import Rules
  Gmail: Settings -> See all settings -> Filters -> Import filters
        """
    )
    export_parser.add_argument(
        "--format",
        type=str,
        required=True,
        choices=["csv", "html", "outlook-rules", "gmail-filters"],
        help="Export format: csv, html, outlook-rules, or gmail-filters"
    )
    export_parser.add_argument(
        "--output",
        type=Path,
        help="Custom output path (default: auto-generated in output dir)"
    )
    export_parser.add_argument(
        "--input",
        type=Path,
        help="Input categories file (default: approved_categories.json)"
    )

    # ===== CONFIG COMMAND =====
    config_parser = subparsers.add_parser(
        "config",
        help="Manage configuration files",
        description="Initialize or display configuration settings."
    )
    config_subparsers = config_parser.add_subparsers(
        dest="config_action",
        required=True,
        help="Config action to perform"
    )

    # config init
    config_init_parser = config_subparsers.add_parser(
        "init",
        help="Generate a template configuration file",
        description="Create a new configuration file with default values."
    )
    config_init_parser.add_argument(
        "--output",
        dest="config_output",
        type=Path,
        help="Output path for config file (default: .email-analyzer.yaml)"
    )
    config_init_parser.add_argument(
        "--global",
        dest="config_global",
        action="store_true",
        help="Create global config in ~/.config/email-analyzer/"
    )

    # config show
    config_subparsers.add_parser(
        "show",
        help="Display resolved configuration",
        description="Show the current configuration with all sources merged."
    )

    # config validate
    config_subparsers.add_parser(
        "validate",
        help="Validate configuration settings",
        description="Check all configuration values and runtime conditions."
    )

    return parser


def setup_output_directory(args: argparse.Namespace) -> None:
    """
    Configure output directory based on CLI arguments.

    Args:
        args: Parsed command-line arguments
    """
    if args.output_dir:
        # User specified custom output directory
        PathConfig.set_output_dir(args.output_dir)
        logger.info(f"Using custom output directory: {args.output_dir}")
    else:
        # Use default
        default_dir = PathConfig.get_default_output_dir()
        logger.info(f"Using default output directory: {default_dir}")

    # Ensure directory exists with secure permissions
    PathConfig.ensure_output_dir_exists()


def cmd_extract(args: argparse.Namespace) -> int:
    """
    Execute email extraction command.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 = success, non-zero = error)
    """
    # Validate email format first (even for dry-run)
    if not validate_email_format(args.user_email):
        logger.error(f"Invalid email format: {args.user_email}")
        if getattr(args, 'json', False):
            output_json({
                "command": "extract",
                "status": "error",
                "error": f"Invalid email format: {args.user_email}"
            })
        return 1

    # Handle dry-run mode
    if getattr(args, 'dry_run', False):
        from src.preview.estimators import ExtractEstimator, format_extract_preview

        estimator = ExtractEstimator()
        estimate = estimator.estimate(args)

        if getattr(args, 'json', False):
            output_json({
                "command": "extract",
                "dry_run": True,
                "status": "preview",
                "user_email": estimate.user_email,
                "output_path": str(estimate.output_path),
                "email_count_estimate": estimate.email_count_estimate,
                "output_size_estimate": estimate.output_size_estimate,
                "duration_estimate": estimate.duration_estimate,
            })
        else:
            print(format_extract_preview(estimate))

        return 0

    start_time = time.time()
    source = getattr(args, 'source', 'hotmail')
    gmail_email = getattr(args, 'gmail_email', None)

    logger.info("=== EMAIL EXTRACTION ===")
    logger.info(f"User email: {args.user_email}")
    logger.info(f"Source: {source}")

    # Determine corpus path
    if args.corpus_file:
        corpus_path = args.corpus_file
    else:
        corpus_path = PathConfig.get_corpus_path()

    logger.info(f"Corpus output: {corpus_path}")

    # Build ExtractConfig with source info
    try:
        from src.config.models import ExtractConfig
        from src.services.extraction_service import ExtractionService

        extract_config = ExtractConfig(
            batch_size=args.batch_size,
            checkpoint_interval=args.checkpoint_interval,
            source=source,
            gmail_email=gmail_email or (args.user_email if source in ("gmail", "both") else None),
        )

        output_dir = PathConfig.get_output_dir()
        service = ExtractionService(
            config=extract_config,
            user_email=args.user_email,
            output_dir=output_dir,
        )
    except Exception as e:
        logger.error(f"Failed to initialize extraction service: {e}", exc_info=True)
        if getattr(args, 'json', False):
            output_json({
                "command": "extract",
                "status": "error",
                "error": str(e)
            })
        return 1

    # Handle incremental extraction (Task 4B.2)
    existing_corpus = None
    if getattr(args, 'since_last', False):
        from src.models.corpus import Corpus

        try:
            existing_data = load_json(corpus_path)
            existing_corpus = Corpus(**existing_data)
            logger.info(f"Loaded existing corpus with {len(existing_corpus.emails)} emails")
        except FileNotFoundError:
            logger.error(f"No existing corpus found at {corpus_path}. Run full extraction first.")
            if getattr(args, 'json', False):
                output_json({
                    "command": "extract",
                    "status": "error",
                    "error": f"No existing corpus found at {corpus_path}. Run full extraction first."
                })
            return 1
        except Exception as e:
            logger.error(f"Failed to load existing corpus: {e}")
            if getattr(args, 'json', False):
                output_json({
                    "command": "extract",
                    "status": "error",
                    "error": str(e)
                })
            return 1

    # Run extraction via ExtractionService
    try:
        corpus = service.run(
            since_last=getattr(args, 'since_last', False),
            existing_corpus=existing_corpus,
        )

        # Save corpus
        save_json(corpus.model_dump(), corpus_path)

        duration = time.time() - start_time
        total_emails = len(corpus.emails)

        if getattr(args, 'json', False):
            output_json({
                "command": "extract",
                "status": "success",
                "duration_seconds": round(duration, 2),
                "output_file": str(corpus_path),
                "stats": {
                    "emails_extracted": total_emails,
                }
            })
        else:
            logger.info(f"Extraction complete: {total_emails} emails")

        return 0

    except Exception as e:
        logger.error(f"Extraction failed: {e}", exc_info=True)
        if getattr(args, 'json', False):
            output_json({
                "command": "extract",
                "status": "error",
                "error": str(e)
            })
        return 1


def cmd_analyze(args: argparse.Namespace) -> int:
    """
    Execute corpus analysis command.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 = success, non-zero = error)
    """
    # Handle dry-run mode
    if getattr(args, 'dry_run', False):
        from src.preview.estimators import AnalyzeEstimator, format_analyze_preview

        estimator = AnalyzeEstimator()
        estimate = estimator.estimate(args)

        if getattr(args, 'json', False):
            output_json({
                "command": "analyze",
                "dry_run": True,
                "status": "preview",
                "corpus_path": str(estimate.corpus_path),
                "corpus_exists": estimate.corpus_exists,
                "email_count": estimate.email_count,
                "output_path": str(estimate.output_path),
                "embedding_time_estimate_seconds": estimate.embedding_time_estimate_seconds,
                "clustering_time_estimate_seconds": estimate.clustering_time_estimate_seconds,
            })
        else:
            print(format_analyze_preview(estimate))

        return 0

    from src.analyzers import run_full_analysis
    from src.models.corpus import Corpus

    start_time = time.time()

    logger.info("=== CORPUS ANALYSIS ===")

    # Determine corpus path
    if args.corpus:
        corpus_path = args.corpus
    else:
        corpus_path = PathConfig.get_corpus_path()

    logger.info(f"Corpus input: {corpus_path}")

    # Load corpus
    try:
        corpus_data = load_json(corpus_path)
        corpus = Corpus(**corpus_data)
        logger.info(f"Loaded {len(corpus.emails)} emails")

    except Exception as e:
        logger.error(f"Failed to load corpus: {e}")
        if getattr(args, 'json', False):
            output_json({
                "command": "analyze",
                "status": "error",
                "error": str(e)
            })
        return 1

    # Determine analysis output path
    if args.analysis_file:
        analysis_path = args.analysis_file
    else:
        analysis_path = PathConfig.get_analysis_path()

    logger.info(f"Analysis output: {analysis_path}")

    # Handle --cluster-analysis flag (show k vs score analysis)
    if getattr(args, 'cluster_analysis', False):
        return _show_cluster_analysis(corpus, args)

    # Handle --incremental flag (Task 4B.4)
    if getattr(args, 'incremental', False):
        return _cmd_analyze_incremental(args, corpus, analysis_path, start_time)

    # Run analysis
    try:
        results, _incremental_stats = run_full_analysis(
            corpus=corpus,
            num_clusters=args.num_clusters,
            auto_clusters=getattr(args, 'auto_clusters', False),
            cluster_method=getattr(args, 'cluster_method', 'silhouette')
        )

        # Save results
        save_json(results.model_dump(), analysis_path)

        duration = time.time() - start_time

        if getattr(args, 'json', False):
            output_json({
                "command": "analyze",
                "status": "success",
                "duration_seconds": round(duration, 2),
                "output_file": str(analysis_path),
                "stats": {
                    "emails_analyzed": len(corpus.emails),
                    "clusters_generated": len(results.content_clusters),
                    "unique_senders": results.sender_analysis.unique_senders
                }
            })
        else:
            logger.info("Analysis complete")
            logger.info(f"  - {results.sender_analysis.unique_senders} unique senders")
            logger.info(f"  - {len(results.content_clusters)} semantic clusters")

        return 0

    except Exception as e:
        logger.error(f"Analysis failed: {e}", exc_info=True)
        if getattr(args, 'json', False):
            output_json({
                "command": "analyze",
                "status": "error",
                "error": str(e)
            })
        return 1


def _cmd_analyze_incremental(
    args: argparse.Namespace,
    corpus,
    analysis_path: Path,
    start_time: float
) -> int:
    """
    Execute incremental corpus analysis (Task 4B.4).

    Args:
        args: Parsed command-line arguments
        corpus: Loaded corpus
        analysis_path: Path for analysis output
        start_time: Start time for duration calculation

    Returns:
        Exit code (0 = success, non-zero = error)
    """
    from src.analyzers import run_full_analysis
    from src.cache.embedding_cache import EmbeddingCache

    logger.info("=== INCREMENTAL ANALYSIS (--incremental) ===")

    # Initialize embedding cache
    cache_path = PathConfig.get_output_dir() / "embeddings_cache.npz"
    embedding_cache = EmbeddingCache(cache_path=cache_path)

    logger.info(f"Embedding cache: {cache_path} ({embedding_cache.size} entries)")

    try:
        results, incremental_stats = run_full_analysis(
            corpus=corpus,
            embedding_cache=embedding_cache,
            num_clusters=args.num_clusters,
            auto_clusters=getattr(args, 'auto_clusters', False),
            cluster_method=getattr(args, 'cluster_method', 'silhouette')
        )

        # Save embedding cache
        embedding_cache.save()

        # Save results
        save_json(results.model_dump(), analysis_path)

        duration = time.time() - start_time

        if getattr(args, 'json', False):
            output_json({
                "command": "analyze",
                "incremental": True,
                "status": "success",
                "duration_seconds": round(duration, 2),
                "output_file": str(analysis_path),
                "stats": {
                    "emails_analyzed": len(corpus.emails),
                    "clusters_generated": len(results.content_clusters),
                    "unique_senders": results.sender_analysis.unique_senders,
                    "cached_embeddings": incremental_stats.get("cached_count", 0),
                    "generated_embeddings": incremental_stats.get("generated_count", 0),
                }
            })
        else:
            logger.info(
                f"Incremental analysis complete: "
                f"Generated {incremental_stats.get('generated_count', 0)} new embeddings, "
                f"used {incremental_stats.get('cached_count', 0)} cached"
            )
            logger.info(f"  - {results.sender_analysis.unique_senders} unique senders")
            logger.info(f"  - {len(results.content_clusters)} semantic clusters")

        return 0

    except Exception as e:
        logger.error(f"Incremental analysis failed: {e}", exc_info=True)
        if getattr(args, 'json', False):
            output_json({
                "command": "analyze",
                "incremental": True,
                "status": "error",
                "error": str(e)
            })
        return 1


def cmd_suggest(args: argparse.Namespace) -> int:
    """
    Execute category suggestion command.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 = success, non-zero = error)
    """
    # Handle dry-run mode
    if getattr(args, 'dry_run', False):
        from src.preview.estimators import SuggestEstimator, format_suggest_preview

        estimator = SuggestEstimator()
        estimate = estimator.estimate(args)

        if getattr(args, 'json', False):
            output_json({
                "command": "suggest",
                "dry_run": True,
                "status": "preview",
                "analysis_path": str(estimate.analysis_path),
                "analysis_exists": estimate.analysis_exists,
                "output_path": str(estimate.output_path),
                "duration_estimate_seconds": estimate.duration_estimate_seconds,
            })
        else:
            print(format_suggest_preview(estimate))

        return 0

    from src.generators.category_generator import CategoryGenerator
    from src.models.analysis_results import AnalysisResults

    start_time = time.time()

    logger.info("=== CATEGORY SUGGESTION ===")

    # Determine analysis path
    if args.analysis:
        analysis_path = args.analysis
    else:
        analysis_path = PathConfig.get_analysis_path()

    logger.info(f"Analysis input: {analysis_path}")

    # Load analysis results
    try:
        analysis_data = load_json(analysis_path)
        results = AnalysisResults(**analysis_data)

    except Exception as e:
        logger.error(f"Failed to load analysis: {e}")
        if getattr(args, 'json', False):
            output_json({
                "command": "suggest",
                "status": "error",
                "error": str(e)
            })
        return 1

    # Determine suggestions output path
    if args.suggestions_file:
        suggestions_path = args.suggestions_file
    else:
        suggestions_path = PathConfig.get_suggestions_path()

    logger.info(f"Suggestions output: {suggestions_path}")

    # Generate suggestions
    try:
        generator = CategoryGenerator()
        categories = generator.generate_suggestions(
            analysis_results=results,
            min_cluster_percentage=args.min_cluster_percentage,
            min_sender_count=args.min_sender_count
        )

        # Save suggestions
        save_json(
            [cat.model_dump() for cat in categories],
            suggestions_path
        )

        # Generate markdown report
        report_path = PathConfig.get_suggestions_report_path()
        report = generator.generate_report(categories)
        report_path.write_text(report, encoding='utf-8')

        duration = time.time() - start_time

        if getattr(args, 'json', False):
            output_json({
                "command": "suggest",
                "status": "success",
                "duration_seconds": round(duration, 2),
                "output_file": str(suggestions_path),
                "stats": {
                    "categories_suggested": len(categories)
                }
            })
        else:
            logger.info(f"Generated {len(categories)} category suggestions")

        return 0

    except Exception as e:
        logger.error(f"Suggestion generation failed: {e}", exc_info=True)
        if getattr(args, 'json', False):
            output_json({
                "command": "suggest",
                "status": "error",
                "error": str(e)
            })
        return 1


def cmd_review(args: argparse.Namespace) -> int:
    """
    Execute interactive category review command.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 = success, non-zero = error)
    """
    # Handle dry-run mode
    if getattr(args, 'dry_run', False):
        from src.preview.estimators import ReviewEstimator, format_review_preview

        estimator = ReviewEstimator()
        estimate = estimator.estimate(args)

        if getattr(args, 'json', False):
            output_json({
                "command": "review",
                "dry_run": True,
                "status": "preview",
                "suggestions_path": str(estimate.suggestions_path),
                "suggestions_exists": estimate.suggestions_exists,
                "category_count": estimate.category_count,
                "output_path": str(estimate.output_path),
            })
        else:
            print(format_review_preview(estimate))

        return 0

    from src.models.category import Category
    from src.ui.category_review import (
        cleanup_intermediate_files,
        review_categories_with_ui,
    )

    start_time = time.time()

    # Handle headless mode (auto-approve all)
    if getattr(args, 'headless', False):
        return auto_approve_categories(args)

    logger.info("=== CATEGORY REVIEW ===")

    # Determine suggestions path
    if args.suggestions:
        suggestions_path = args.suggestions
    else:
        suggestions_path = PathConfig.get_suggestions_path()

    logger.info(f"Suggestions input: {suggestions_path}")

    # Load suggestions
    try:
        suggestions_data = load_json(suggestions_path)
        categories = [Category(**cat) for cat in suggestions_data]

    except Exception as e:
        logger.error(f"Failed to load suggestions: {e}")
        if getattr(args, 'json', False):
            output_json({
                "command": "review",
                "status": "error",
                "error": str(e)
            })
        return 1

    # Determine approved output path
    if args.approved_file:
        approved_path = args.approved_file
    else:
        approved_path = PathConfig.get_approved_categories_path()

    logger.info(f"Approved categories output: {approved_path}")

    # Determine whether to use TUI
    use_tui = not getattr(args, 'no_tui', False)

    # Determine whether to use learning (Task 5B.3)
    enable_learning = not getattr(args, 'no_learning', False)

    # Run interactive review
    try:
        approved = review_categories_with_ui(
            categories,
            output_path=approved_path,
            use_tui=use_tui,
            enable_learning=enable_learning,
        )

        duration = time.time() - start_time

        if getattr(args, 'json', False):
            output_json({
                "command": "review",
                "status": "success",
                "duration_seconds": round(duration, 2),
                "output_file": str(approved_path),
                "stats": {
                    "categories_reviewed": len(categories),
                    "categories_approved": len(approved)
                }
            })
        else:
            logger.info(f"Approved {len(approved)} categories")

        # Optional cleanup
        if not args.no_cleanup:
            cleanup_intermediate_files(str(PathConfig.get_output_dir()))

        return 0

    except Exception as e:
        logger.error(f"Review failed: {e}", exc_info=True)
        if getattr(args, 'json', False):
            output_json({
                "command": "review",
                "status": "error",
                "error": str(e)
            })
        return 1


def auto_approve_categories(args: argparse.Namespace) -> int:
    """
    Auto-approve all category suggestions without interactive review.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 = success, non-zero = error)
    """
    start_time = time.time()

    logger.info("=== AUTO-APPROVE CATEGORIES ===")

    # Determine suggestions path
    if hasattr(args, 'suggestions') and args.suggestions:
        suggestions_path = args.suggestions
    else:
        suggestions_path = PathConfig.get_suggestions_path()

    # Determine approved output path
    if hasattr(args, 'approved_file') and args.approved_file:
        approved_path = args.approved_file
    else:
        approved_path = PathConfig.get_approved_categories_path()

    logger.info(f"Auto-approving suggestions from: {suggestions_path}")
    logger.info(f"Saving to: {approved_path}")

    try:
        # Load suggestions
        suggestions_data = load_json(suggestions_path)

        # Save directly as approved (no changes)
        save_json(suggestions_data, approved_path)

        duration = time.time() - start_time

        if getattr(args, 'json', False):
            output_json({
                "command": "auto_approve",
                "status": "success",
                "duration_seconds": round(duration, 2),
                "output_file": str(approved_path),
                "stats": {
                    "categories_approved": len(suggestions_data)
                }
            })
        else:
            logger.info(f"Auto-approved {len(suggestions_data)} categories")

        return 0

    except FileNotFoundError as e:
        logger.error(f"Suggestions file not found: {e}")
        if getattr(args, 'json', False):
            output_json({
                "command": "auto_approve",
                "status": "error",
                "error": str(e)
            })
        return 1
    except Exception as e:
        logger.error(f"Auto-approve failed: {e}", exc_info=True)
        if getattr(args, 'json', False):
            output_json({
                "command": "auto_approve",
                "status": "error",
                "error": str(e)
            })
        return 1


def cmd_pipeline(args: argparse.Namespace) -> int:
    """
    Execute complete pipeline command.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 = success, non-zero = error)
    """
    # Validate email format first (even for dry-run)
    if not validate_email_format(args.user_email):
        logger.error(f"Invalid email format: {args.user_email}")
        if getattr(args, 'json', False):
            output_json({
                "command": "pipeline",
                "status": "error",
                "error": f"Invalid email format: {args.user_email}"
            })
        return 1

    # Handle dry-run mode
    if getattr(args, 'dry_run', False):
        from src.preview.estimators import PipelineEstimator, format_pipeline_preview

        estimator = PipelineEstimator()
        estimate = estimator.estimate(args)

        if getattr(args, 'json', False):
            output_json({
                "command": "pipeline",
                "dry_run": True,
                "status": "preview",
                "stages": {
                    "extract": {
                        "user_email": estimate.extract.user_email,
                        "output_path": str(estimate.extract.output_path),
                    },
                    "analyze": {
                        "corpus_path": str(estimate.analyze.corpus_path),
                        "output_path": str(estimate.analyze.output_path),
                    },
                    "suggest": {
                        "analysis_path": str(estimate.suggest.analysis_path),
                        "output_path": str(estimate.suggest.output_path),
                    },
                    "review": {
                        "suggestions_path": str(estimate.review.suggestions_path),
                        "output_path": str(estimate.review.output_path),
                    },
                },
            })
        else:
            print(format_pipeline_preview(estimate))

        return 0

    start_time = time.time()

    logger.info("=== COMPLETE PIPELINE ===")

    # Step 1: Extract
    logger.info("Step 1/4: Extracting emails...")
    extract_args = argparse.Namespace(
        user_email=args.user_email,
        source=getattr(args, 'source', 'hotmail'),
        gmail_email=getattr(args, 'gmail_email', None),
        corpus_file=None,
        batch_size=500,
        checkpoint_interval=100,
        since_last=False,
        dry_run=False,
        output_dir=args.output_dir,
        verbose=getattr(args, 'verbose', False),
        quiet=getattr(args, 'quiet', False),
        json=getattr(args, 'json', False)
    )
    if cmd_extract(extract_args) != 0:
        return 1

    # Step 2: Analyze
    logger.info("Step 2/4: Analyzing corpus...")
    analyze_args = argparse.Namespace(
        corpus=None,
        num_clusters=args.num_clusters,
        analysis_file=None,
        output_dir=args.output_dir,
        verbose=getattr(args, 'verbose', False),
        quiet=getattr(args, 'quiet', False),
        json=getattr(args, 'json', False)
    )
    if cmd_analyze(analyze_args) != 0:
        return 1

    # Step 3: Suggest
    logger.info("Step 3/4: Generating suggestions...")
    suggest_args = argparse.Namespace(
        analysis=None,
        min_cluster_percentage=5.0,
        min_sender_count=20,
        suggestions_file=None,
        output_dir=args.output_dir,
        verbose=getattr(args, 'verbose', False),
        quiet=getattr(args, 'quiet', False),
        json=getattr(args, 'json', False)
    )
    if cmd_suggest(suggest_args) != 0:
        return 1

    # Step 4: Review or Auto-approve
    if getattr(args, 'skip_review', False):
        logger.info("Step 4/4: Auto-approving suggestions (--skip-review)...")
        review_args = argparse.Namespace(
            suggestions=None,
            approved_file=None,
            no_cleanup=args.no_cleanup,
            output_dir=args.output_dir,
            verbose=getattr(args, 'verbose', False),
            quiet=getattr(args, 'quiet', False),
            json=getattr(args, 'json', False)
        )
        if auto_approve_categories(review_args) != 0:
            return 1
    else:
        logger.info("Step 4/4: Interactive review...")
        review_args = argparse.Namespace(
            suggestions=None,
            approved_file=None,
            no_cleanup=args.no_cleanup,
            no_tui=getattr(args, 'no_tui', False),
            no_learning=getattr(args, 'no_learning', False),
            output_dir=args.output_dir,
            verbose=getattr(args, 'verbose', False),
            quiet=getattr(args, 'quiet', False),
            json=getattr(args, 'json', False)
        )
        if cmd_review(review_args) != 0:
            return 1

    duration = time.time() - start_time

    if getattr(args, 'json', False):
        output_json({
            "command": "pipeline",
            "status": "success",
            "duration_seconds": round(duration, 2)
        })
    else:
        logger.info("Pipeline complete!")

    return 0


def cmd_info(args: argparse.Namespace) -> int:
    """
    Execute info command to show corpus statistics.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 = success, non-zero = error)
    """
    # Determine corpus path
    if args.corpus:
        corpus_path = args.corpus
    else:
        corpus_path = PathConfig.get_corpus_path()

    # Load corpus data
    try:
        corpus_data = load_json(corpus_path)
    except FileNotFoundError:
        logger.error(f"Corpus file not found: {corpus_path}")
        if getattr(args, 'json', False):
            output_json({
                "command": "info",
                "status": "error",
                "error": f"Corpus file not found: {corpus_path}"
            })
        return 1
    except Exception as e:
        logger.error(f"Failed to load corpus: {e}")
        if getattr(args, 'json', False):
            output_json({
                "command": "info",
                "status": "error",
                "error": str(e)
            })
        return 1

    # Extract statistics
    emails = corpus_data.get("emails", [])

    email_count = len(emails)

    # Get unique senders and domains
    senders = set()
    domains = set()
    for email in emails:
        sender = email.get("sender_email", "")
        if sender:
            senders.add(sender)
            if "@" in sender:
                domains.add(sender.split("@")[1])

    # Get date range
    dates = []
    for email in emails:
        date_str = email.get("received_date")
        if date_str:
            try:
                # Handle ISO format
                if isinstance(date_str, str):
                    dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                    dates.append(dt)
            except ValueError:
                pass

    date_range_str = "N/A"
    date_span_days = 0
    if dates:
        oldest = min(dates)
        newest = max(dates)
        date_span_days = (newest - oldest).days
        date_range_str = f"{oldest.strftime('%Y-%m-%d')} to {newest.strftime('%Y-%m-%d')} ({date_span_days} days)"

    # Get file size
    try:
        file_size = corpus_path.stat().st_size
        file_size_mb = file_size / (1024 * 1024)
        file_size_str = f"{file_size_mb:.1f} MB"
    except Exception:
        file_size = 0
        file_size_str = "Unknown"

    # Check for analysis and category files
    analysis_path = PathConfig.get_analysis_path()
    suggestions_path = PathConfig.get_suggestions_path()
    approved_path = PathConfig.get_approved_categories_path()

    analysis_available = analysis_path.exists() if analysis_path else False
    suggestions_count = 0
    approved_count = 0

    if suggestions_path and suggestions_path.exists():
        try:
            suggestions_data = load_json(suggestions_path)
            suggestions_count = len(suggestions_data)
        except Exception:
            pass

    if approved_path and approved_path.exists():
        try:
            approved_data = load_json(approved_path)
            approved_count = len(approved_data)
        except Exception:
            pass

    if getattr(args, 'json', False):
        output_json({
            "command": "info",
            "status": "success",
            "corpus_file": str(corpus_path),
            "file_size_bytes": file_size,
            "email_count": email_count,
            "unique_senders": len(senders),
            "unique_domains": len(domains),
            "date_range": {
                "oldest": min(dates).isoformat() if dates else None,
                "newest": max(dates).isoformat() if dates else None,
                "span_days": date_span_days
            },
            "analysis_available": analysis_available,
            "categories_suggested": suggestions_count,
            "categories_approved": approved_count
        })
    else:
        print("\nCorpus Information")
        print("-" * 50)
        print(f"File:           {corpus_path}")
        print(f"Size:           {file_size_str}")
        print(f"Emails:         {email_count:,}")
        print(f"Date Range:     {date_range_str}")
        print(f"Unique Senders: {len(senders):,}")
        print(f"Unique Domains: {len(domains):,}")
        print()
        if analysis_available:
            print("Analysis Status: Available")
        else:
            print("Analysis Status: Not available")
        if suggestions_count > 0 or approved_count > 0:
            print(f"Categories:      {suggestions_count} suggested, {approved_count} approved")
        print()

    return 0


def cmd_export(args: argparse.Namespace) -> int:
    """
    Execute export command (Task 5C.3, Phase 8 Track 8B.3).

    Exports approved categories to CSV, HTML, Outlook rules, or Gmail filters format.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 = success, non-zero = error)
    """
    from datetime import datetime

    from src.exporters.csv_exporter import export_categories_to_csv
    from src.exporters.html_exporter import export_categories_to_html
    from src.exporters.rule_exporter import GmailFilterExporter, OutlookRuleExporter
    from src.models.category import Category

    start_time = time.time()

    logger.info(f"=== CATEGORY EXPORT ({args.format.upper()}) ===")

    # Determine input path
    if args.input:
        input_path = args.input
    else:
        input_path = PathConfig.get_approved_categories_path()

    logger.info(f"Input file: {input_path}")

    # Load categories
    try:
        categories_data = load_json(input_path)
        categories = [Category(**cat) for cat in categories_data]
        logger.info(f"Loaded {len(categories)} categories")

    except FileNotFoundError:
        logger.error(f"Categories file not found: {input_path}")
        if getattr(args, 'json', False):
            output_json({
                "command": "export",
                "status": "error",
                "error": f"Categories file not found: {input_path}"
            })
        return 1
    except Exception as e:
        logger.error(f"Failed to load categories: {e}")
        if getattr(args, 'json', False):
            output_json({
                "command": "export",
                "status": "error",
                "error": str(e)
            })
        return 1

    # Determine output path
    if args.output:
        output_path = args.output
    else:
        # Auto-generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if args.format == "csv":
            output_path = PathConfig.get_output_dir() / f"categories_{timestamp}.csv"
        elif args.format == "html":
            output_path = PathConfig.get_output_dir() / f"category_report_{timestamp}.html"
        elif args.format == "outlook-rules":
            output_path = PathConfig.get_output_dir() / f"outlook_rules_{timestamp}.xml"
        else:  # gmail-filters
            output_path = PathConfig.get_output_dir() / f"gmail_filters_{timestamp}.xml"

    logger.info(f"Output file: {output_path}")

    # Export based on format
    try:
        if args.format == "csv":
            result_path = export_categories_to_csv(categories, output_path)
        elif args.format == "html":
            result_path = export_categories_to_html(categories, output_path)
        elif args.format == "outlook-rules":
            exporter = OutlookRuleExporter()
            result_path = exporter.export_to_file(categories, output_path)
        else:  # gmail-filters
            exporter = GmailFilterExporter()
            result_path = exporter.export_to_file(categories, output_path)

        duration = time.time() - start_time

        if getattr(args, 'json', False):
            output_json({
                "command": "export",
                "status": "success",
                "format": args.format,
                "duration_seconds": round(duration, 2),
                "output_file": str(result_path),
                "categories_exported": len(categories)
            })
        else:
            logger.info(f"Export complete: {result_path}")
            logger.info(f"Exported {len(categories)} categories to {args.format.upper()}")

            # Show import instructions for rule exports
            if args.format == "outlook-rules":
                logger.info("To import: File -> Manage Rules & Alerts -> Options -> Import Rules")
            elif args.format == "gmail-filters":
                logger.info("To import: Settings -> See all settings -> Filters -> Import filters")

        return 0

    except Exception as e:
        logger.error(f"Export failed: {e}", exc_info=True)
        if getattr(args, 'json', False):
            output_json({
                "command": "export",
                "status": "error",
                "error": str(e)
            })
        return 1


def cmd_config_init(args: argparse.Namespace) -> int:
    """
    Execute config init command - generate template configuration file.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 = success, non-zero = error)
    """
    # Determine output path
    if args.config_output:
        output_path = args.config_output
    elif args.config_global:
        output_path = get_global_config_path()
        # Ensure parent directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
    else:
        output_path = get_project_config_path()

    # Generate and write template
    try:
        template = generate_template()
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(template)
        logger.info(f"Created configuration file: {output_path}")
        return 0
    except OSError as e:
        logger.error(f"Failed to write configuration file: {e}")
        return 1


def cmd_config_show(args: argparse.Namespace) -> int:
    """
    Execute config show command - display resolved configuration.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 = success, non-zero = error)
    """
    try:
        config = load_config(config_path=args.config)
        output = show_resolved_config(config)
        print(output)
        return 0
    except ConfigLoadError as e:
        logger.error(f"Failed to load configuration: {e}")
        return 1


def validate_config(config) -> list[dict]:
    """
    Validate configuration settings and check runtime conditions.

    Args:
        config: AppConfig instance to validate

    Returns:
        List of validation results, each containing:
        - field: Name of the config field
        - status: 'ok', 'warning', or 'error'
        - message: Description of the validation result
    """
    results = []

    # Validate output_dir
    if config.output_dir:
        output_path = Path(config.output_dir).expanduser()
        if output_path.exists():
            if output_path.is_dir():
                # Check if writable
                try:
                    test_file = output_path / ".write_test"
                    test_file.touch()
                    test_file.unlink()
                    results.append({
                        "field": "output_dir",
                        "status": "ok",
                        "message": f"Directory exists and is writable: {output_path}"
                    })
                except (PermissionError, OSError):
                    results.append({
                        "field": "output_dir",
                        "status": "error",
                        "message": f"Directory is not writable: {output_path}"
                    })
            else:
                results.append({
                    "field": "output_dir",
                    "status": "error",
                    "message": f"Path exists but is not a directory: {output_path}"
                })
        else:
            # Check if parent exists and is writable
            parent = output_path.parent
            if parent.exists():
                results.append({
                    "field": "output_dir",
                    "status": "warning",
                    "message": f"Directory does not exist but parent is accessible: {output_path}"
                })
            else:
                results.append({
                    "field": "output_dir",
                    "status": "error",
                    "message": f"Directory does not exist and cannot be created: {output_path}"
                })
    else:
        results.append({
            "field": "output_dir",
            "status": "ok",
            "message": "Using default output directory"
        })

    # Validate user_email
    if config.user_email:
        if validate_email_format(config.user_email):
            results.append({
                "field": "user_email",
                "status": "ok",
                "message": f"Valid email format: {config.user_email}"
            })
        else:
            results.append({
                "field": "user_email",
                "status": "error",
                "message": f"Invalid email format: {config.user_email}"
            })
    else:
        results.append({
            "field": "user_email",
            "status": "warning",
            "message": "No user email configured (required for extract command)"
        })

    # Validate extract settings
    if config.extract.batch_size <= 0:
        results.append({
            "field": "extract.batch_size",
            "status": "error",
            "message": "Batch size must be positive"
        })
    else:
        results.append({
            "field": "extract.batch_size",
            "status": "ok",
            "message": f"Batch size: {config.extract.batch_size}"
        })

    if config.extract.checkpoint_interval <= 0:
        results.append({
            "field": "extract.checkpoint_interval",
            "status": "error",
            "message": "Checkpoint interval must be positive"
        })
    else:
        results.append({
            "field": "extract.checkpoint_interval",
            "status": "ok",
            "message": f"Checkpoint interval: {config.extract.checkpoint_interval}"
        })

    # Validate analyze settings
    if config.analyze.num_clusters < 1:
        results.append({
            "field": "analyze.num_clusters",
            "status": "error",
            "message": "Number of clusters must be at least 1"
        })
    else:
        results.append({
            "field": "analyze.num_clusters",
            "status": "ok",
            "message": f"Number of clusters: {config.analyze.num_clusters}"
        })

    # Validate suggest settings
    if config.suggest.min_cluster_percentage < 0 or config.suggest.min_cluster_percentage > 100:
        results.append({
            "field": "suggest.min_cluster_percentage",
            "status": "error",
            "message": "Min cluster percentage must be between 0 and 100"
        })
    else:
        results.append({
            "field": "suggest.min_cluster_percentage",
            "status": "ok",
            "message": f"Min cluster percentage: {config.suggest.min_cluster_percentage}%"
        })

    if config.suggest.min_sender_count < 1:
        results.append({
            "field": "suggest.min_sender_count",
            "status": "error",
            "message": "Min sender count must be at least 1"
        })
    else:
        results.append({
            "field": "suggest.min_sender_count",
            "status": "ok",
            "message": f"Min sender count: {config.suggest.min_sender_count}"
        })

    return results


def cmd_config_validate(args: argparse.Namespace) -> int:
    """
    Execute config validate command - validate all configuration settings.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 = success, 1 = has errors)
    """
    try:
        config = load_config(config_path=args.config)
    except ConfigLoadError as e:
        logger.error(f"Failed to load configuration: {e}")
        if getattr(args, 'json', False):
            output_json({
                "command": "config validate",
                "status": "error",
                "error": str(e)
            })
        return 1

    validations = validate_config(config)

    # Count errors
    errors = [v for v in validations if v["status"] == "error"]
    warnings = [v for v in validations if v["status"] == "warning"]

    if getattr(args, 'json', False):
        output_json({
            "command": "config validate",
            "status": "error" if errors else "ok",
            "validations": validations,
            "summary": {
                "total": len(validations),
                "ok": len([v for v in validations if v["status"] == "ok"]),
                "warnings": len(warnings),
                "errors": len(errors)
            }
        })
    else:
        print("\nConfiguration Validation")
        print("=" * 50)
        print()

        for validation in validations:
            status = validation["status"]
            field = validation["field"]
            message = validation["message"]

            if status == "ok":
                symbol = "[OK]"
            elif status == "warning":
                symbol = "[WARN]"
            else:
                symbol = "[ERROR]"

            print(f"{symbol:8} {field}")
            print(f"         {message}")
            print()

        print("=" * 50)
        print(f"Summary: {len(errors)} errors, {len(warnings)} warnings")

        if errors:
            print("\nConfiguration has errors that must be fixed.")
        elif warnings:
            print("\nConfiguration has warnings but is usable.")
        else:
            print("\nConfiguration is valid.")

    return 1 if errors else 0


def cmd_config(args: argparse.Namespace) -> int:
    """
    Execute config command dispatcher.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 = success, non-zero = error)
    """
    if args.config_action == "init":
        return cmd_config_init(args)
    if args.config_action == "show":
        return cmd_config_show(args)
    if args.config_action == "validate":
        return cmd_config_validate(args)
    logger.error(f"Unknown config action: {args.config_action}")
    return 1


def main() -> int:
    """
    Main CLI entry point.

    Returns:
        Exit code (0 = success, non-zero = error)
    """
    parser = create_parser()
    args = parser.parse_args()

    # Setup logging level based on flags
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    elif args.quiet:
        logging.getLogger().setLevel(logging.WARNING)
    elif args.json:
        # In JSON mode, suppress normal logging (only errors)
        logging.getLogger().setLevel(logging.ERROR)

    # Load configuration from files (unless running config command)
    if args.command != "config":
        try:
            config = load_config(config_path=args.config)
            # Apply config defaults to args where CLI didn't specify
            _apply_config_defaults(args, config)
        except ConfigLoadError as e:
            logger.error(f"Failed to load configuration: {e}")
            return 1

    # Configure output directory (skip for info command if no explicit output-dir)
    if args.command != "info" or args.output_dir:
        setup_output_directory(args)

    # Dispatch to command handler
    command_handlers = {
        "extract": cmd_extract,
        "analyze": cmd_analyze,
        "suggest": cmd_suggest,
        "review": cmd_review,
        "pipeline": cmd_pipeline,
        "config": cmd_config,
        "info": cmd_info,
        "export": cmd_export,
    }

    handler = command_handlers.get(args.command)
    if not handler:
        logger.error(f"Unknown command: {args.command}")
        return 1

    try:
        return handler(args)
    except KeyboardInterrupt:
        logger.warning("\nOperation cancelled by user")
        return 130
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return 1


def _apply_config_defaults(args: argparse.Namespace, config) -> None:
    """
    Apply configuration file defaults to CLI arguments.

    CLI arguments always take precedence over config file values.
    Only applies config values where CLI didn't provide a value.

    Args:
        args: Parsed command-line arguments (modified in place)
        config: Loaded AppConfig instance
    """
    # Global settings
    if args.output_dir is None and config.output_dir is not None:
        args.output_dir = config.output_dir

    if not args.verbose and config.verbose:
        args.verbose = config.verbose

    # User email (if not provided on CLI, try config)
    if hasattr(args, "user_email") and args.user_email is None and config.user_email:
        args.user_email = config.user_email

    # Extract command options
    if hasattr(args, "batch_size"):
        # CLI default is 500, config default is 500
        # Only override if config has non-default value
        if args.batch_size == 500 and config.extract.batch_size != 500:
            args.batch_size = config.extract.batch_size

    if hasattr(args, "checkpoint_interval"):
        if args.checkpoint_interval == 100 and config.extract.checkpoint_interval != 100:
            args.checkpoint_interval = config.extract.checkpoint_interval

    # Analyze command options
    if hasattr(args, "num_clusters"):
        if args.num_clusters == 10 and config.analyze.num_clusters != 10:
            args.num_clusters = config.analyze.num_clusters

    # Suggest command options
    if hasattr(args, "min_cluster_percentage"):
        if args.min_cluster_percentage == 5.0 and config.suggest.min_cluster_percentage != 5.0:
            args.min_cluster_percentage = config.suggest.min_cluster_percentage

    if hasattr(args, "min_sender_count"):
        if args.min_sender_count == 20 and config.suggest.min_sender_count != 20:
            args.min_sender_count = config.suggest.min_sender_count

    # Review command options
    if hasattr(args, "no_cleanup"):
        if not args.no_cleanup and config.review.no_cleanup:
            args.no_cleanup = config.review.no_cleanup


if __name__ == "__main__":
    sys.exit(main())
