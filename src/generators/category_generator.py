"""
Category Generator implementation.

Per contracts/generator_contract.md, generates category suggestions from
analysis results using clusters, senders, and templates.
"""
from typing import List
from collections import defaultdict

from src.models.analysis_results import AnalysisResults
from src.models.category import Category, CategorySource
from src.models.category_template import PREDEFINED_TEMPLATES, CategoryTemplate
from src.generators.template_matcher import match_templates
from src.generators.confidence_scorer import calculate_confidence
from src.utils.logger import get_logger

logger = get_logger(__name__)


class CategoryGenerator:
    """Generate category suggestions from analysis results."""

    def generate_suggestions(
        self,
        analysis_results: AnalysisResults,
        min_cluster_percentage: float = 5.0,
        min_sender_count: int = 20
    ) -> List[Category]:
        """
        Generate category suggestions from analysis.

        Args:
            analysis_results: Complete analysis results
            min_cluster_percentage: Minimum cluster size % to suggest (default 5%)
            min_sender_count: Minimum emails from sender to suggest category (default 20)

        Returns:
            List of Category objects sorted by confidence (highest first)
        """
        logger.info("Generating category suggestions...")
        all_categories: List[Category] = []
        total_emails = analysis_results.volume_stats.total_emails

        # FR-022: Generate from content clusters
        logger.debug(f"Generating categories from {len(analysis_results.content_clusters)} clusters")
        for cluster in analysis_results.content_clusters:
            if cluster.percentage >= min_cluster_percentage:
                category = self._category_from_cluster(cluster, total_emails)
                all_categories.append(category)
                logger.debug(f"Created cluster-based category: {category.category_name} ({cluster.percentage:.1f}%)")

        # FR-023: Generate from high-volume senders
        logger.debug(f"Generating categories from top senders")
        for sender in analysis_results.sender_analysis.top_senders[:20]:  # Top 20 only
            if sender.frequency_count >= min_sender_count:
                category = self._category_from_sender(sender, total_emails)
                all_categories.append(category)
                logger.debug(f"Created sender-based category: {category.category_name} ({sender.frequency_count} emails)")

        # FR-024: Apply templates
        logger.debug("Applying predefined templates")
        template_categories = match_templates(analysis_results, PREDEFINED_TEMPLATES)
        all_categories.extend(template_categories)
        logger.debug(f"Created {len(template_categories)} template-based categories")

        # FR-025: Calculate confidence scores
        logger.debug("Calculating confidence scores")
        for category in all_categories:
            category.confidence = calculate_confidence(category, total_emails)

        # FR-027: Merge similar categories
        logger.debug("Merging similar categories")
        all_categories = self._merge_similar(all_categories)

        # FR-028: Sort by confidence
        all_categories.sort(key=lambda c: c.confidence, reverse=True)
        logger.info(f"Generated {len(all_categories)} unique categories")

        return all_categories

    def _category_from_cluster(self, cluster, total_emails: int) -> Category:
        """Create category from content cluster."""
        # Generate name from representative samples
        sample_subjects = [s.subject for s in cluster.representative_samples[:3]]
        name = self._generate_cluster_name(sample_subjects, cluster.common_domains)

        return Category(
            category_id=f"cluster_{cluster.cluster_id}",
            category_name=name,
            description=f"Content-based grouping of {cluster.size} emails ({cluster.percentage:.1f}%)",
            confidence=0.0,  # Will be calculated by confidence_scorer
            email_count=cluster.size,
            percentage=cluster.percentage,
            source=CategorySource.CONTENT_CLUSTER,
            source_id=str(cluster.cluster_id),
            user_modified=False,
            distinguishing_features=[s.subject[:50] for s in cluster.representative_samples[:3]],
            example_email_ids=cluster.email_ids[:10]
        )

    def _category_from_sender(self, sender, total_emails: int) -> Category:
        """Create category from high-volume sender."""
        # Use sender domain or name for category
        name = sender.domain.replace('.com', '').replace('.', ' ').title()
        if not name:
            name = sender.email.split('@')[0].replace('.', ' ').title()

        percentage = (sender.frequency_count / total_emails) * 100 if total_emails > 0 else 0

        return Category(
            category_id=f"sender_{sender.email.replace('@', '_at_').replace('.', '_')}",
            category_name=f"{name} Emails",
            description=f"Emails from {sender.email} ({sender.type.value})",
            confidence=0.0,  # Will be calculated
            email_count=sender.frequency_count,
            percentage=percentage,
            source=CategorySource.SENDER,
            source_id=sender.email,
            user_modified=False,
            distinguishing_features=sender.sample_subjects[:5],
            example_email_ids=sender.email_ids[:10]
        )

    def _generate_cluster_name(self, subjects: List[str], domains: List[tuple]) -> str:
        """Generate descriptive name for cluster."""
        # Try to use common domain
        if domains:
            domain_name = domains[0][0].replace('.com', '').replace('.', ' ').title()
            return f"{domain_name} Related"

        # Fallback to common words in subjects
        words = ' '.join(subjects).lower().split()
        common_words = [w for w in words if len(w) > 4][:2]
        if common_words:
            return ' '.join(common_words).title() + " Category"

        return "Miscellaneous"

    def _merge_similar(self, categories: List[Category]) -> List[Category]:
        """Merge categories with similar names and overlapping emails."""
        merged = []
        merged_indices = set()

        for i, cat1 in enumerate(categories):
            if i in merged_indices:
                continue

            # Collect similar categories
            similar = [cat1]
            for j, cat2 in enumerate(categories[i + 1:], start=i + 1):
                if j in merged_indices:
                    continue

                # Check name similarity (Levenshtein distance < 3) - simplified to exact match for now
                if self._names_similar(cat1.category_name, cat2.category_name):
                    # Check email overlap
                    overlap = self._calculate_overlap(
                        set(cat1.example_email_ids),
                        set(cat2.example_email_ids)
                    )
                    if overlap > 0.7:  # >70% overlap
                        similar.append(cat2)
                        merged_indices.add(j)

            # Merge if similar categories found
            if len(similar) > 1:
                merged_cat = self._merge_categories(similar)
                merged.append(merged_cat)
            else:
                merged.append(cat1)

        logger.debug(f"Merged {len(categories)} → {len(merged)} categories")
        return merged

    def _names_similar(self, name1: str, name2: str) -> bool:
        """Check if two category names are similar."""
        # Simplified: check if one contains the other (case-insensitive)
        n1, n2 = name1.lower(), name2.lower()
        return n1 in n2 or n2 in n1 or n1 == n2

    def _calculate_overlap(self, set1: set, set2: set) -> float:
        """Calculate overlap percentage between two email ID sets."""
        if not set1 or not set2:
            return 0.0
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        return intersection / union if union > 0 else 0.0

    def _merge_categories(self, categories: List[Category]) -> Category:
        """Merge multiple categories into one."""
        # Keep the one with highest confidence
        categories.sort(key=lambda c: c.confidence, reverse=True)
        primary = categories[0]

        # Combine email IDs
        all_email_ids = set()
        for cat in categories:
            all_email_ids.update(cat.example_email_ids)

        # Update counts
        primary.example_email_ids = list(all_email_ids)[:10]
        return primary

    def apply_templates(self, analysis_results: AnalysisResults) -> List[Category]:
        """Apply predefined category templates."""
        return match_templates(analysis_results, PREDEFINED_TEMPLATES)

    def score_confidence(self, category: Category, total_emails: int) -> float:
        """Calculate confidence score for category."""
        return calculate_confidence(category, total_emails)

    def generate_report(self, categories: List[Category]) -> str:
        """
        Generate human-readable markdown report.

        Args:
            categories: List of Category objects

        Returns:
            Markdown-formatted report string
        """
        lines = [
            "# Email Category Suggestions Report",
            "",
            f"**Total Categories**: {len(categories)}",
            f"**Generated**: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "---",
            ""
        ]

        for i, category in enumerate(categories, 1):
            lines.append(f"## {i}. {category.category_name}")
            lines.append("")
            lines.append(f"**Description**: {category.description}")
            lines.append(f"**Confidence**: {category.confidence * 100:.1f}%")
            lines.append(f"**Email Count**: {category.email_count} ({category.percentage:.1f}% of inbox)")
            lines.append(f"**Source**: {category.source.value}")
            lines.append("")

            if category.distinguishing_features:
                lines.append("**Key Features**:")
                for feature in category.distinguishing_features[:5]:
                    lines.append(f"- {feature}")
                lines.append("")

            lines.append("---")
            lines.append("")

        return '\n'.join(lines)
