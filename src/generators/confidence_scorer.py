"""
Confidence Scorer module.

Implements confidence scoring per generator_contract.md lines 47-62.
Contract compliance: FR-025
"""
import logging

from ..models.category import Category, CategorySource

logger = logging.getLogger(__name__)


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
        total_emails
    )

    # Calculate volume score: scale to 100 emails max
    email_count = category.email_count or 0
    volume_score = min(email_count / 100.0, 1.0)
    logger.debug("  volume_score: %.3f (email_count=%d)", volume_score, email_count)

    # Calculate source score based on CategorySource
    source_scores = {
        CategorySource.TEMPLATE: 0.9,
        CategorySource.CONTENT_CLUSTER: 0.8,
        CategorySource.SENDER: 0.7,
        CategorySource.CUSTOM: 0.5,
    }
    source_score = source_scores.get(category.source, 0.5)
    logger.debug("  source_score: %.3f (source=%s)", source_score, category.source)

    # Calculate percentage score: convert from percentage to 0-1 range
    percentage = category.percentage or 0.0
    percentage_score = percentage / 100.0
    logger.debug("  percentage_score: %.3f (percentage=%.2f%%)", percentage_score, percentage)

    # Calculate average of three scores
    confidence = (volume_score + source_score + percentage_score) / 3.0

    # Ensure result is in range [0.0, 1.0] per FR-025
    confidence = max(0.0, min(1.0, confidence))

    logger.debug(
        "  final confidence: %.3f for category '%s'",
        confidence,
        category.category_name
    )

    return confidence
