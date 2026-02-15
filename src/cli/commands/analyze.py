"""Analyze command: run analyzers on email corpus."""
import argparse
import time
from pathlib import Path

from src.cli.formatters import _generate_cluster_viz, _show_cluster_analysis, output_json
from src.utils.file_manager import load_json, save_json
from src.utils.logger import get_logger
from src.utils.paths import PathConfig

logger = get_logger(__name__)


def build_analyze_parser(subparsers) -> None:
    """Add analyze subparser to the CLI."""
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
    analyze_parser.add_argument(
        "--cluster-viz",
        action="store_true",
        default=False,
        help="Generate cluster visualization PNG (requires matplotlib)"
    )


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

        # Generate cluster visualization if requested (Task 4.3)
        viz_path = None
        if getattr(args, 'cluster_viz', False):
            viz_path = _generate_cluster_viz(corpus, results)

        duration = time.time() - start_time

        if getattr(args, 'json', False):
            json_output = {
                "command": "analyze",
                "status": "success",
                "duration_seconds": round(duration, 2),
                "output_file": str(analysis_path),
                "stats": {
                    "emails_analyzed": len(corpus.emails),
                    "clusters_generated": len(results.content_clusters),
                    "unique_senders": results.sender_analysis.unique_senders
                }
            }
            if viz_path:
                json_output["visualization_path"] = str(viz_path)
            output_json(json_output)
        else:
            logger.info("Analysis complete")
            logger.info(f"  - {results.sender_analysis.unique_senders} unique senders")
            logger.info(f"  - {len(results.content_clusters)} semantic clusters")
            if viz_path:
                logger.info(f"  - Cluster visualization: {viz_path}")

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
