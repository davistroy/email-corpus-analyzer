"""
Cross-entity validation utilities.

Per data-model.md lines 416-425, implements validators for cross-entity constraints:
1. Corpus.total_emails == len(Corpus.emails)
2. All Email.id values must be unique within Corpus
3. Category.example_email_ids must reference valid Email.id values
4. Sum of all ContentCluster.percentage values should ≈ 100% (within rounding)
"""

from src.models.category import Category
from src.models.content_cluster import ContentCluster
from src.models.corpus import Corpus
from src.utils.logger import get_logger

logger = get_logger(__name__)


def validate_corpus_total_matches_length(corpus: Corpus) -> bool:
    """
    Validate that Corpus.total_emails matches the actual number of emails.

    Args:
        corpus: Corpus instance to validate

    Returns:
        True if valid

    Raises:
        ValueError: If total_emails doesn't match len(emails)
    """
    total_emails = corpus.extraction_metadata.total_emails
    actual_count = len(corpus.emails)

    logger.debug(f"Validating corpus total: declared={total_emails}, actual={actual_count}")

    if total_emails != actual_count:
        error_msg = (
            f"Corpus total_emails mismatch: declared {total_emails} but found {actual_count} emails"
        )
        logger.error(error_msg)
        raise ValueError(error_msg)

    logger.debug("Corpus total validation passed")
    return True


def validate_unique_email_ids(corpus: Corpus) -> bool:
    """
    Validate that all Email.id values are unique within the corpus.

    Args:
        corpus: Corpus instance to validate

    Returns:
        True if valid

    Raises:
        ValueError: If duplicate email IDs are found
    """
    email_ids = [email.id for email in corpus.emails]
    unique_ids = set(email_ids)

    logger.debug(
        f"Validating email ID uniqueness: total={len(email_ids)}, unique={len(unique_ids)}"
    )

    if len(email_ids) != len(unique_ids):
        # Find duplicates for error message
        seen = set()
        duplicates = set()
        for email_id in email_ids:
            if email_id in seen:
                duplicates.add(email_id)
            seen.add(email_id)

        error_msg = (
            f"Duplicate email IDs found: {len(email_ids) - len(unique_ids)} "
            f"duplicates across {len(duplicates)} unique ID(s). "
            f"Examples: {list(duplicates)[:5]}"
        )
        logger.error(error_msg)
        raise ValueError(error_msg)

    logger.debug("Email ID uniqueness validation passed")
    return True


def validate_cluster_percentages_sum_100(
    clusters: list[ContentCluster], tolerance: float = 2.0
) -> bool:
    """
    Validate that ContentCluster percentages sum to approximately 100%.

    Per data-model.md line 424, allows tolerance for rounding errors.

    Args:
        clusters: List of ContentCluster instances to validate
        tolerance: Acceptable deviation from 100% (default: 2.0 means 98-102%)

    Returns:
        True if valid

    Raises:
        ValueError: If percentage sum is outside acceptable range
    """
    if not clusters:
        logger.debug("No clusters to validate, skipping percentage sum check")
        return True

    total_percentage = sum(cluster.percentage for cluster in clusters)
    lower_bound = 100.0 - tolerance
    upper_bound = 100.0 + tolerance

    logger.debug(
        f"Validating cluster percentages: total={total_percentage:.2f}%, "
        f"acceptable range=[{lower_bound:.2f}%, {upper_bound:.2f}%], "
        f"cluster_count={len(clusters)}"
    )

    if not (lower_bound <= total_percentage <= upper_bound):
        error_msg = (
            f"ContentCluster percentages sum to {total_percentage:.2f}%, "
            f"expected ~100% (acceptable range: {lower_bound:.2f}%-{upper_bound:.2f}%). "
            f"Cluster count: {len(clusters)}"
        )
        logger.error(error_msg)
        raise ValueError(error_msg)

    logger.debug("Cluster percentages validation passed")
    return True


def validate_email_id_references(categories: list[Category], corpus: Corpus) -> bool:
    """
    Validate that Category.example_email_ids reference valid Email.id values.

    Args:
        categories: List of Category instances to validate
        corpus: Corpus containing valid email IDs

    Returns:
        True if valid

    Raises:
        ValueError: If any example_email_ids reference invalid Email.id values
    """
    valid_email_ids = {email.id for email in corpus.emails}

    logger.debug(
        f"Validating email ID references: "
        f"valid_ids={len(valid_email_ids)}, categories={len(categories)}"
    )

    invalid_references = []

    for category in categories:
        for email_id in category.example_email_ids:
            if email_id not in valid_email_ids:
                invalid_references.append(
                    {
                        "category_id": category.category_id,
                        "category_name": category.category_name,
                        "invalid_email_id": email_id,
                    }
                )

    if invalid_references:
        # Log first few examples
        examples = invalid_references[:3]
        error_msg = (
            f"Found {len(invalid_references)} invalid email ID reference(s) "
            f"in category example_email_ids. Examples: {examples}"
        )
        logger.error(error_msg)
        raise ValueError(error_msg)

    logger.debug(
        f"Email ID references validation passed: "
        f"checked {sum(len(c.example_email_ids) for c in categories)} references"
    )
    return True
