"""
Confidence Scorer module.

Implements confidence scoring per generator_contract.md lines 47-62.
Contract compliance: FR-025

Enhanced with Task 5A.1: Weighted confidence factors and breakdown.
Work Item 4.1: Improved scoring with logarithmic volume, percentage/10 scaling,
mean-overlap distinctiveness, and configurable weights via GeneratorThresholds.
"""

import logging
import math
from dataclasses import dataclass

from src.utils.constants import VOLUME_LOG_BASE

from ..models.category import Category, CategorySource

logger = logging.getLogger(__name__)

# Single definition of source-type-to-reliability mapping.
# Used by both calculate_confidence() and calculate_confidence_enhanced().
SOURCE_RELIABILITY_SCORES: dict[CategorySource, float] = {
    CategorySource.TEMPLATE: 0.9,
    CategorySource.CONTENT_CLUSTER: 0.8,
    CategorySource.SENDER: 0.7,
    CategorySource.CUSTOM: 0.5,
}


@dataclass
class ConfidenceWeights:
    """
    Configurable weights for confidence score calculation.

    Weights should sum to 1.0 for proper normalization.
    Default weights prioritize source reliability and volume.

    Can be constructed from GeneratorThresholds via from_thresholds().
    """

    cohesion: float = 0.15  # Based on distinguishing features
    volume: float = 0.20  # Based on email count
    source: float = 0.25  # Based on source type reliability
    percentage: float = 0.15  # Based on corpus percentage
    name_quality: float = 0.10  # Based on name quality score
    distinctiveness: float = 0.15  # Based on overlap with other categories

    @classmethod
    def from_thresholds(cls, thresholds) -> "ConfidenceWeights":
        """
        Create ConfidenceWeights from a GeneratorThresholds config model.

        Args:
            thresholds: GeneratorThresholds instance with confidence_weight_* fields

        Returns:
            ConfidenceWeights populated from config
        """
        return cls(
            cohesion=thresholds.confidence_weight_cohesion,
            volume=thresholds.confidence_weight_volume,
            source=thresholds.confidence_weight_source,
            percentage=thresholds.confidence_weight_percentage,
            name_quality=thresholds.confidence_weight_name_quality,
            distinctiveness=thresholds.confidence_weight_distinctiveness,
        )


def calculate_confidence(category: Category, total_emails: int) -> float:
    """
    Calculate confidence score for category.

    Per FR-025, confidence is based on:
    - email_count (volume_score)
    - source_type (source_score)
    - percentage_of_corpus (percentage_score)

    Formula: confidence = avg(volume_score, source_score, percentage_score)

    Args:
        category: Category to score
        total_emails: Total emails in corpus

    Returns:
        Confidence score 0.0-1.0
    """
    logger.debug(
        "Calculating confidence for category '%s' (source=%s, email_count=%s, percentage=%s, total_emails=%d)",
        category.category_name,
        category.source,
        category.email_count,
        category.percentage,
        total_emails,
    )

    # Calculate volume score: logarithmic scaling so 100 emails = 1.0, 10 ≈ 0.5
    email_count = category.email_count or 0
    volume_score = min(1.0, math.log10(email_count + 1) / math.log10(VOLUME_LOG_BASE))
    logger.debug("  volume_score: %.3f (email_count=%d)", volume_score, email_count)

    # Calculate source score based on CategorySource
    source_score = SOURCE_RELIABILITY_SCORES.get(category.source, 0.5)
    logger.debug("  source_score: %.3f (source=%s)", source_score, category.source)

    # Calculate percentage score: 10% of corpus = 1.0
    percentage = category.percentage or 0.0
    percentage_score = min(1.0, percentage / 10.0)
    logger.debug("  percentage_score: %.3f (percentage=%.2f%%)", percentage_score, percentage)

    # Calculate average of three scores
    confidence = (volume_score + source_score + percentage_score) / 3.0

    # Ensure result is in range [0.0, 1.0] per FR-025
    confidence = max(0.0, min(1.0, confidence))

    logger.debug("  final confidence: %.3f for category '%s'", confidence, category.category_name)

    return confidence


def calculate_confidence_enhanced(
    category: Category,
    total_emails: int,
    weights: ConfidenceWeights | None = None,
    overlap_scores: dict[str, float] | None = None,
) -> tuple[float, dict[str, float]]:
    """
    Calculate enhanced confidence score with weighted factors and breakdown.

    Task 5A.1: Enhanced confidence model with:
    - Cohesion: based on distinguishing features count
    - Volume: based on email count (scaled to 100)
    - Source: based on CategorySource reliability
    - Percentage: based on corpus percentage
    - Name quality: based on name_quality_score field
    - Distinctiveness: based on overlap with other categories

    Args:
        category: Category to score
        total_emails: Total emails in corpus
        weights: Optional custom weights (defaults to ConfidenceWeights())
        overlap_scores: Optional dict of category_id -> overlap percentage
                       for distinctiveness calculation

    Returns:
        Tuple of (confidence_score, breakdown_dict)
        - confidence_score: Final weighted confidence 0.0-1.0
        - breakdown_dict: Component scores for each factor
    """
    if weights is None:
        weights = ConfidenceWeights()

    logger.debug("Calculating enhanced confidence for category '%s'", category.category_name)

    # Calculate cohesion score (based on distinguishing features)
    # More features = higher cohesion (max at 5 features)
    features_count = len(category.distinguishing_features)
    cohesion_score = min(features_count / 5.0, 1.0)
    logger.debug("  cohesion_score: %.3f (features=%d)", cohesion_score, features_count)

    # Calculate volume score: logarithmic scaling so 100 emails = 1.0, 10 ≈ 0.5
    email_count = category.email_count or 0
    volume_score = min(1.0, math.log10(email_count + 1) / math.log10(VOLUME_LOG_BASE))
    logger.debug("  volume_score: %.3f (email_count=%d)", volume_score, email_count)

    # Calculate source score based on CategorySource
    source_score = SOURCE_RELIABILITY_SCORES.get(category.source, 0.5)
    logger.debug("  source_score: %.3f (source=%s)", source_score, category.source)

    # Calculate percentage score: 10% of corpus = 1.0
    percentage = category.percentage or 0.0
    percentage_score = min(1.0, percentage / 10.0)
    logger.debug("  percentage_score: %.3f (percentage=%.2f%%)", percentage_score, percentage)

    # Calculate name quality score (use field value or default to 0.5)
    name_quality_score = (
        category.name_quality_score if category.name_quality_score is not None else 0.5
    )
    logger.debug("  name_quality_score: %.3f", name_quality_score)

    # Calculate distinctiveness score (penalize based on mean overlap with other categories)
    if overlap_scores:
        # Use mean overlap across all other categories for average separation
        mean_overlap = sum(overlap_scores.values()) / len(overlap_scores) if overlap_scores else 0.0
        distinctiveness_score = 1.0 - mean_overlap
    else:
        # Default to full score if no overlap data
        distinctiveness_score = 1.0
    logger.debug("  distinctiveness_score: %.3f", distinctiveness_score)

    # Build breakdown dictionary
    breakdown = {
        "cohesion": cohesion_score,
        "volume": volume_score,
        "source": source_score,
        "percentage": percentage_score,
        "name_quality": name_quality_score,
        "distinctiveness": distinctiveness_score,
    }

    # Calculate weighted confidence
    confidence = (
        weights.cohesion * cohesion_score
        + weights.volume * volume_score
        + weights.source * source_score
        + weights.percentage * percentage_score
        + weights.name_quality * name_quality_score
        + weights.distinctiveness * distinctiveness_score
    )

    # Ensure result is in range [0.0, 1.0]
    confidence = max(0.0, min(1.0, confidence))

    logger.debug(
        "  final enhanced confidence: %.3f for category '%s'", confidence, category.category_name
    )

    return confidence, breakdown


def calculate_pairwise_overlap(categories: list[Category]) -> dict[str, dict[str, float]]:
    """
    Calculate pairwise overlap between all categories.

    Task 5A.2: Computes Jaccard similarity between category email sets.

    Args:
        categories: List of categories to compare

    Returns:
        Nested dict: {cat_id: {other_cat_id: overlap_score}}
        Overlap is calculated as Jaccard similarity (intersection / union)
    """
    result: dict[str, dict[str, float]] = {}

    for cat in categories:
        result[cat.category_id] = {}

    # Calculate pairwise overlaps
    for i, cat1 in enumerate(categories):
        set1 = set(cat1.example_email_ids)

        for cat2 in categories[i + 1 :]:
            set2 = set(cat2.example_email_ids)

            # Calculate Jaccard similarity
            if not set1 or not set2:
                overlap = 0.0
            else:
                intersection = len(set1 & set2)
                union = len(set1 | set2)
                overlap = intersection / union if union > 0 else 0.0

            # Store symmetrically
            result[cat1.category_id][cat2.category_id] = overlap
            result[cat2.category_id][cat1.category_id] = overlap

            logger.debug(
                "Overlap between '%s' and '%s': %.3f",
                cat1.category_name,
                cat2.category_name,
                overlap,
            )

    return result


def find_merge_candidates(
    categories: list[Category], threshold: float = 0.5
) -> list[tuple[str, str, float]]:
    """
    Find category pairs that are candidates for merging due to high overlap.

    Task 5A.2: Identifies categories with significant email overlap.

    Args:
        categories: List of categories to analyze
        threshold: Minimum overlap score to flag as merge candidate (default: 0.5)

    Returns:
        List of tuples (cat1_id, cat2_id, overlap_score) for pairs above threshold
    """
    overlaps = calculate_pairwise_overlap(categories)
    candidates = []

    # Track pairs we've already added (avoid duplicates)
    seen_pairs: set[tuple[str, ...]] = set()

    for cat_id, others in overlaps.items():
        for other_id, overlap in others.items():
            # Create normalized pair key
            pair_key = tuple(sorted([cat_id, other_id]))

            if pair_key not in seen_pairs and overlap >= threshold:
                candidates.append((cat_id, other_id, overlap))
                seen_pairs.add(pair_key)
                logger.info(
                    "Merge candidate: '%s' and '%s' (overlap=%.2f)", cat_id, other_id, overlap
                )

    return candidates


def calculate_distinctiveness_scores(categories: list[Category]) -> dict[str, float]:
    """
    Calculate distinctiveness score for each category.

    Work Item 4.1: Distinctiveness is inversely related to mean overlap
    across all other categories, reflecting average separation rather
    than worst-case overlap.

    Args:
        categories: List of categories to score

    Returns:
        Dict mapping category_id to distinctiveness score (0.0-1.0)
    """
    overlaps = calculate_pairwise_overlap(categories)
    scores: dict[str, float] = {}

    for cat_id, others in overlaps.items():
        if not others:
            # No other categories to overlap with
            scores[cat_id] = 1.0
        else:
            # Distinctiveness = 1 - mean(overlaps) for average separation
            mean_overlap = sum(others.values()) / len(others)
            scores[cat_id] = 1.0 - mean_overlap

        logger.debug("Distinctiveness score for '%s': %.3f", cat_id, scores[cat_id])

    return scores
