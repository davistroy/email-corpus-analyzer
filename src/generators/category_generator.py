"""
Category Generator implementation.

Per contracts/generator_contract.md, generates category suggestions from
analysis results using clusters, senders, and templates.

Updated for modernization plan with optional LLM-powered categorization.
"""
import asyncio
from datetime import datetime

from src.generators.confidence_scorer import calculate_confidence
from src.generators.template_matcher import match_templates
from src.models.analysis_results import AnalysisResults
from src.models.category import Category, CategorySource
from src.models.category_template import PREDEFINED_TEMPLATES
from src.utils.logger import get_logger

logger = get_logger(__name__)


class CategoryGenerator:
    """
    Generate category suggestions from analysis results.

    Supports:
    - Cluster-based categories (from semantic analysis)
    - Sender-based categories (high-volume senders)
    - Template-based categories (predefined patterns)
    - LLM-powered categorization (optional, for better naming and suggestions)
    """

    def __init__(self, use_llm: bool = False, llm_client=None):
        """
        Initialize category generator.

        Args:
            use_llm: Whether to use LLM for intelligent categorization.
            llm_client: LLM client instance. Creates default if None and use_llm=True.
        """
        self.use_llm = use_llm
        self.llm_client = llm_client
        self._categorizer = None

    def _get_categorizer(self):
        """Lazy load the LLM categorizer."""
        if self._categorizer is None and self.use_llm:
            from src.llm.categorizer import LLMCategorizer
            self._categorizer = LLMCategorizer(self.llm_client)
        return self._categorizer

    def generate_suggestions(
        self,
        analysis_results: AnalysisResults,
        min_cluster_percentage: float = 5.0,
        min_sender_count: int = 20,
    ) -> list[Category]:
        """
        Generate category suggestions from analysis.

        Args:
            analysis_results: Complete analysis results.
            min_cluster_percentage: Minimum cluster size % to suggest (default 5%).
            min_sender_count: Minimum emails from sender to suggest category (default 20).

        Returns:
            List of Category objects sorted by confidence (highest first).
        """
        logger.info("Generating category suggestions...")

        if self.use_llm:
            # Use async LLM categorization
            return asyncio.run(self.generate_suggestions_async(
                analysis_results,
                min_cluster_percentage,
                min_sender_count,
            ))

        return self._generate_suggestions_heuristic(
            analysis_results,
            min_cluster_percentage,
            min_sender_count,
        )

    async def generate_suggestions_async(
        self,
        analysis_results: AnalysisResults,
        min_cluster_percentage: float = 5.0,
        min_sender_count: int = 20,
    ) -> list[Category]:
        """
        Async version of generate_suggestions with LLM support.

        Args:
            analysis_results: Complete analysis results.
            min_cluster_percentage: Minimum cluster size % to suggest.
            min_sender_count: Minimum emails from sender to suggest category.

        Returns:
            List of Category objects sorted by confidence.
        """
        # Start with heuristic categories
        heuristic_categories = self._generate_suggestions_heuristic(
            analysis_results,
            min_cluster_percentage,
            min_sender_count,
        )

        if not self.use_llm:
            return heuristic_categories

        # Enhance with LLM suggestions
        categorizer = self._get_categorizer()
        if not categorizer:
            return heuristic_categories

        try:
            logger.info("Generating LLM-enhanced category suggestions...")

            # Get LLM suggestions
            llm_suggestions = await categorizer.suggest_categories(
                analysis_results,
                existing_categories=heuristic_categories,
            )

            # Convert LLM suggestions to Category objects
            llm_categories = []
            for i, suggestion in enumerate(llm_suggestions.categories):
                category = Category(
                    category_id=f"llm_{i}",
                    category_name=suggestion.category_name,
                    description=suggestion.description,
                    confidence=suggestion.confidence,
                    email_count=suggestion.estimated_count,
                    percentage=(suggestion.estimated_count / analysis_results.volume_stats.total_emails * 100)
                    if analysis_results.volume_stats.total_emails > 0 else 0,
                    source=CategorySource.LLM_SUGGESTED,
                    source_id=f"llm_suggestion_{i}",
                    user_modified=False,
                    distinguishing_features=suggestion.matching_patterns[:5],
                    example_email_ids=[],
                )
                llm_categories.append(category)

            # Merge LLM and heuristic categories
            all_categories = self._merge_with_llm(heuristic_categories, llm_categories)

            # Sort by confidence
            all_categories.sort(key=lambda c: c.confidence, reverse=True)

            logger.info(
                f"Generated {len(all_categories)} categories "
                f"({len(heuristic_categories)} heuristic + {len(llm_categories)} LLM)"
            )

            return all_categories

        except Exception as e:
            logger.warning(f"LLM categorization failed, using heuristics only: {e}")
            return heuristic_categories

    def _generate_suggestions_heuristic(
        self,
        analysis_results: AnalysisResults,
        min_cluster_percentage: float,
        min_sender_count: int,
    ) -> list[Category]:
        """Generate suggestions using heuristic methods (original logic)."""
        all_categories: list[Category] = []
        total_emails = analysis_results.volume_stats.total_emails

        # FR-022: Generate from content clusters
        logger.debug(f"Generating categories from {len(analysis_results.content_clusters)} clusters")
        for cluster in analysis_results.content_clusters:
            if cluster.percentage >= min_cluster_percentage:
                category = self._category_from_cluster(cluster, total_emails)
                all_categories.append(category)
                logger.debug(f"Created cluster-based category: {category.category_name} ({cluster.percentage:.1f}%)")

        # FR-023: Generate from high-volume senders
        logger.debug("Generating categories from top senders")
        for sender in analysis_results.sender_analysis.top_senders[:20]:
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
        logger.info(f"Generated {len(all_categories)} unique categories (heuristic)")

        return all_categories

    def _category_from_cluster(self, cluster, total_emails: int) -> Category:
        """Create category from content cluster."""
        # Use LLM-generated name if available
        if cluster.suggested_name:
            name = cluster.suggested_name
            description = cluster.name_reasoning or f"Content-based grouping of {cluster.size} emails"
        else:
            # Fallback to heuristic naming
            sample_subjects = [s.subject for s in cluster.representative_samples[:3]]
            name = self._generate_cluster_name(sample_subjects, cluster.common_domains)
            description = f"Content-based grouping of {cluster.size} emails ({cluster.percentage:.1f}%)"

        return Category(
            category_id=f"cluster_{cluster.cluster_id}",
            category_name=name,
            description=description,
            confidence=cluster.name_confidence or 0.0,
            email_count=cluster.size,
            percentage=cluster.percentage,
            source=CategorySource.CONTENT_CLUSTER,
            source_id=str(cluster.cluster_id),
            user_modified=False,
            distinguishing_features=[s.subject[:50] for s in cluster.representative_samples[:3]],
            example_email_ids=cluster.email_ids[:10],
        )

    def _category_from_sender(self, sender, total_emails: int) -> Category:
        """Create category from high-volume sender."""
        name = sender.domain.replace('.com', '').replace('.', ' ').title()
        if not name:
            name = sender.email.split('@')[0].replace('.', ' ').title()

        percentage = (sender.frequency_count / total_emails) * 100 if total_emails > 0 else 0

        return Category(
            category_id=f"sender_{sender.email.replace('@', '_at_').replace('.', '_')}",
            category_name=f"{name} Emails",
            description=f"Emails from {sender.email} ({sender.type.value})",
            confidence=0.0,
            email_count=sender.frequency_count,
            percentage=percentage,
            source=CategorySource.SENDER,
            source_id=sender.email,
            user_modified=False,
            distinguishing_features=sender.sample_subjects[:5],
            example_email_ids=sender.email_ids[:10],
        )

    def _generate_cluster_name(self, subjects: list[str], domains: list[tuple]) -> str:
        """Generate descriptive name for cluster."""
        if domains:
            domain_name = domains[0][0].replace('.com', '').replace('.', ' ').title()
            return f"{domain_name} Related"

        words = ' '.join(subjects).lower().split()
        common_words = [w for w in words if len(w) > 4][:2]
        if common_words:
            return ' '.join(common_words).title() + " Category"

        return "Miscellaneous"

    def _merge_similar(self, categories: list[Category]) -> list[Category]:
        """Merge categories with similar names and overlapping emails."""
        merged = []
        merged_indices = set()

        for i, cat1 in enumerate(categories):
            if i in merged_indices:
                continue

            similar = [cat1]
            for j, cat2 in enumerate(categories[i + 1:], start=i + 1):
                if j in merged_indices:
                    continue

                if self._names_similar(cat1.category_name, cat2.category_name):
                    overlap = self._calculate_overlap(
                        set(cat1.example_email_ids),
                        set(cat2.example_email_ids)
                    )
                    if overlap > 0.7:
                        similar.append(cat2)
                        merged_indices.add(j)

            if len(similar) > 1:
                merged_cat = self._merge_categories(similar)
                merged.append(merged_cat)
            else:
                merged.append(cat1)

        logger.debug(f"Merged {len(categories)} → {len(merged)} categories")
        return merged

    def _merge_with_llm(
        self,
        heuristic: list[Category],
        llm: list[Category],
    ) -> list[Category]:
        """Merge heuristic and LLM categories, preferring LLM names."""
        # Create a map of LLM categories by approximate match
        result = []

        for h_cat in heuristic:
            # Try to find matching LLM category
            matched_llm = None
            for l_cat in llm:
                if self._names_similar(h_cat.category_name, l_cat.category_name):
                    matched_llm = l_cat
                    break

            if matched_llm:
                # Enhance heuristic with LLM name/description
                h_cat.category_name = matched_llm.category_name
                h_cat.description = matched_llm.description
                # Boost confidence if LLM agrees
                h_cat.confidence = max(h_cat.confidence, matched_llm.confidence)

            result.append(h_cat)

        # Add LLM-only categories that didn't match
        heuristic_names = {c.category_name.lower() for c in heuristic}
        for l_cat in llm:
            if l_cat.category_name.lower() not in heuristic_names:
                # Check if similar to any existing
                is_similar = any(
                    self._names_similar(l_cat.category_name, h.category_name)
                    for h in result
                )
                if not is_similar:
                    result.append(l_cat)

        return result

    def _names_similar(self, name1: str, name2: str) -> bool:
        """Check if two category names are similar."""
        n1, n2 = name1.lower(), name2.lower()
        return n1 in n2 or n2 in n1 or n1 == n2

    def _calculate_overlap(self, set1: set, set2: set) -> float:
        """Calculate overlap percentage between two email ID sets."""
        if not set1 or not set2:
            return 0.0
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        return intersection / union if union > 0 else 0.0

    def _merge_categories(self, categories: list[Category]) -> Category:
        """Merge multiple categories into one."""
        categories.sort(key=lambda c: c.confidence, reverse=True)
        primary = categories[0]

        all_email_ids = set()
        for cat in categories:
            all_email_ids.update(cat.example_email_ids)

        primary.example_email_ids = list(all_email_ids)[:10]
        return primary

    def apply_templates(self, analysis_results: AnalysisResults) -> list[Category]:
        """Apply predefined category templates."""
        return match_templates(analysis_results, PREDEFINED_TEMPLATES)

    def score_confidence(self, category: Category, total_emails: int) -> float:
        """Calculate confidence score for category."""
        return calculate_confidence(category, total_emails)

    def generate_report(self, categories: list[Category]) -> str:
        """
        Generate human-readable markdown report.

        Args:
            categories: List of Category objects.

        Returns:
            Markdown-formatted report string.
        """
        lines = [
            "# Email Category Suggestions Report",
            "",
            f"**Total Categories**: {len(categories)}",
            f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
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
