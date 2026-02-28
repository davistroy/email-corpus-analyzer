"""Output formatting helpers for CLI commands."""

import json
from pathlib import Path

from src.utils.logger import get_logger
from src.utils.paths import PathConfig

logger = get_logger(__name__)


def output_json(data: dict) -> None:
    """
    Output data as formatted JSON to stdout.

    Args:
        data: Dictionary to output as JSON
    """
    print(json.dumps(data, indent=2, default=str))


def _show_cluster_analysis(corpus, args) -> int:
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
    embeddings = analyzer.model.encode(texts, show_progress_bar=True, convert_to_numpy=True)

    # Run both optimization methods
    cluster_method = getattr(args, "cluster_method", "silhouette")
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

    if getattr(args, "json", False):
        output_json(
            {
                "command": "analyze",
                "cluster_analysis": True,
                "elbow_method": {
                    "optimal_k": elbow_result.optimal_k,
                    "confidence": elbow_result.confidence_score,
                    "k_scores": elbow_result.k_scores,
                },
                "silhouette_method": {
                    "optimal_k": silhouette_result.optimal_k,
                    "confidence": silhouette_result.confidence_score,
                    "interpretation": silhouette_result.interpretation,
                    "k_scores": silhouette_result.k_scores,
                },
                "recommendation": {
                    "method": cluster_method,
                    "optimal_k": recommended_k,
                    "confidence": confidence,
                },
            }
        )
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
            print(
                f"\nNote: Elbow suggests k={elbow_result.optimal_k}, "
                f"Silhouette suggests k={silhouette_result.optimal_k}"
            )

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

    chart_height = 10

    # Normalize scores to chart height
    normalized = [(s - min_score) / score_range for s in scores]

    # Build chart rows (from top to bottom)
    for row in range(chart_height, -1, -1):
        row_level = row / chart_height
        line = ""
        for _i, (k, norm_score) in enumerate(zip(k_values, normalized, strict=True)):
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


def _generate_cluster_viz(corpus, results) -> Path | None:
    """
    Generate cluster visualization PNG from analysis results.

    Re-generates embeddings and runs KMeans to obtain the data needed for
    scatter plot and silhouette bar chart. Returns the output path on success,
    or None if matplotlib is not available.

    Args:
        corpus: Loaded email corpus
        results: AnalysisResults from run_full_analysis

    Returns:
        Path to generated PNG, or None if visualization could not be created
    """
    from src.analyzers.semantic_analyzer import SemanticAnalyzer, generate_cluster_visualization

    # Check matplotlib availability early
    try:
        import matplotlib  # noqa: F401
    except ImportError:
        logger.warning(
            "matplotlib required for visualization. Install with: pip install matplotlib"
        )
        return None

    from sklearn.cluster import KMeans

    logger.info("Generating cluster visualization...")

    # Re-generate embeddings (fast if model is already cached in memory)
    analyzer = SemanticAnalyzer()
    analyzer._ensure_model_loaded()

    texts = [email.combined_text_with_limit() for email in corpus.emails]
    embeddings = analyzer.model.encode(texts, show_progress_bar=False, convert_to_numpy=True)

    # Run KMeans with the same cluster count used in analysis
    n_clusters = len(results.content_clusters)
    if n_clusters < 1:
        logger.warning("No clusters in analysis results, skipping visualization")
        return None

    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    labels = kmeans.fit_predict(embeddings)

    # Build per-cluster silhouette scores from analysis results
    cluster_silhouette_scores = {}
    for cluster in results.content_clusters:
        if cluster.silhouette_score is not None:
            cluster_silhouette_scores[cluster.cluster_id] = cluster.silhouette_score

    output_path = PathConfig.get_output_dir() / "cluster_visualization.png"

    return generate_cluster_visualization(
        embeddings=embeddings,
        labels=labels,
        output_path=output_path,
        cluster_silhouette_scores=cluster_silhouette_scores if cluster_silhouette_scores else None,
    )
