"""
Template matcher for category generation.

Implements FR-024: Template Application
Per generator_contract.md lines 32-45 and 79-82.
"""
import logging
from typing import List
from collections import defaultdict

from src.models.category_template import CategoryTemplate, PREDEFINED_TEMPLATES
from src.models.category import Category, CategorySource
from src.models.analysis_results import AnalysisResults

logger = logging.getLogger(__name__)


def match_templates(
    analysis_results: AnalysisResults,
    templates: List[CategoryTemplate] = None
) -> List[Category]:
    """
    Apply predefined category templates to analysis results.

    Matches keywords in subject/body AND/OR domains per FR-024.
    Creates Category objects with source=TEMPLATE and source_id=template name.

    Args:
        analysis_results: Complete analysis results containing sender and cluster data
        templates: Optional list of templates to apply (defaults to PREDEFINED_TEMPLATES)

    Returns:
        List of Category objects from template matching
    """
    if templates is None:
        templates = PREDEFINED_TEMPLATES

    logger.debug(f"Starting template matching with {len(templates)} templates")

    categories = []
    total_emails = analysis_results.volume_stats.total_emails

    for template in templates:
        logger.debug(f"Processing template: {template.name}")

        # Collect matching email IDs
        matching_email_ids = set()

        # Match by keywords in subject/body through clusters
        matching_email_ids.update(_match_by_keywords(
            analysis_results,
            template.keywords
        ))

        # Match by domains through senders
        matching_email_ids.update(_match_by_domains(
            analysis_results,
            template.domains
        ))

        # If we have matches, create a category
        if matching_email_ids:
            email_count = len(matching_email_ids)
            percentage = (email_count / total_emails * 100) if total_emails > 0 else 0.0

            # Generate category_id from template name
            category_id = template.name.lower().replace(" ", "_").replace("&", "and")

            # Take up to 10 example email IDs
            example_ids = list(matching_email_ids)[:10]

            # Calculate initial confidence (will be refined by confidence scorer)
            # Base confidence on percentage of corpus matched
            confidence = min(0.9, percentage / 100.0 * 2)  # Cap at 0.9, scale by 2x
            confidence = max(0.1, confidence)  # Floor at 0.1

            category = Category(
                category_id=category_id,
                category_name=template.name,
                description=template.description,
                confidence=confidence,
                email_count=email_count,
                percentage=percentage,
                source=CategorySource.TEMPLATE,
                source_id=template.name,
                user_modified=False,
                distinguishing_features=template.keywords[:5],  # Top 5 keywords as features
                example_email_ids=example_ids
            )

            categories.append(category)
            logger.debug(
                f"Template '{template.name}' matched {email_count} emails "
                f"({percentage:.1f}% of corpus)"
            )
        else:
            logger.debug(f"Template '{template.name}' had no matches")

    logger.info(f"Template matching complete. Generated {len(categories)} categories")
    return categories


def _match_by_keywords(
    analysis_results: AnalysisResults,
    keywords: List[str]
) -> set:
    """
    Match emails by keywords in subject lines and cluster samples.

    Args:
        analysis_results: Analysis results to search
        keywords: List of keywords to match (case-insensitive)

    Returns:
        Set of matching email IDs
    """
    matching_ids = set()
    keywords_lower = [kw.lower() for kw in keywords]

    # Match through content clusters (which contain subject/body preview info)
    for cluster in analysis_results.content_clusters:
        cluster_matches = False

        # Check representative samples for keyword matches
        for sample in cluster.representative_samples:
            subject_lower = sample.subject.lower()
            body_lower = sample.body_preview.lower()

            # Check if any keyword appears in subject or body
            if any(kw in subject_lower or kw in body_lower for kw in keywords_lower):
                cluster_matches = True
                break

        # If cluster matches, add all its email IDs
        if cluster_matches:
            matching_ids.update(cluster.email_ids)

    # Also check subject patterns for keyword matches
    for keyword_tuple in analysis_results.subject_patterns.top_keywords:
        keyword_from_pattern = keyword_tuple[0].lower()

        # If this pattern keyword matches any template keyword
        if any(kw in keyword_from_pattern or keyword_from_pattern in kw
               for kw in keywords_lower):
            # We can't get email IDs directly from top_keywords
            # This is more for logging/validation
            logger.debug(f"Subject pattern keyword '{keyword_tuple[0]}' matches template keywords")

    return matching_ids


def _match_by_domains(
    analysis_results: AnalysisResults,
    domains: List[str]
) -> set:
    """
    Match emails by sender domains.

    Args:
        analysis_results: Analysis results to search
        domains: List of domain patterns to match (partial match supported)

    Returns:
        Set of matching email IDs
    """
    matching_ids = set()
    domains_lower = [d.lower() for d in domains]

    # Match through top senders
    for sender in analysis_results.sender_analysis.top_senders:
        sender_domain_lower = sender.domain.lower()

        # Check if sender domain contains or matches any template domain
        if any(domain in sender_domain_lower or sender_domain_lower in domain
               for domain in domains_lower):
            matching_ids.update(sender.email_ids)
            logger.debug(
                f"Sender domain '{sender.domain}' matches template domains "
                f"({sender.frequency_count} emails)"
            )

    # Also check common domains in clusters
    for cluster in analysis_results.content_clusters:
        for domain_tuple in cluster.common_domains:
            cluster_domain_lower = domain_tuple[0].lower()

            if any(domain in cluster_domain_lower or cluster_domain_lower in domain
                   for domain in domains_lower):
                matching_ids.update(cluster.email_ids)
                logger.debug(
                    f"Cluster domain '{domain_tuple[0]}' matches template domains "
                    f"({cluster.size} emails)"
                )

    return matching_ids
