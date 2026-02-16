"""
Category Generator implementation.

Per contracts/generator_contract.md, generates category suggestions from
analysis results using clusters, senders, and templates.

Task 5B.3: Integrates with feedback learning to apply learned patterns
to generated categories.
Task 2.2: Externalized magic numbers to GeneratorThresholds config.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from src.generators.confidence_scorer import calculate_confidence
from src.generators.name_generator import TfidfNameGenerator, score_name_quality
from src.generators.template_matcher import match_templates
from src.learning.decision_logger import DecisionLogger
from src.learning.pattern_detector import PatternDetector, PatternType
from src.models.analysis_results import AnalysisResults
from src.models.category import Category, CategorySource
from src.models.category_template import PREDEFINED_TEMPLATES
from src.utils.constants import NAME_QUALITY_REVIEW_THRESHOLD
from src.utils.logger import get_logger
from src.utils.text import STOP_WORDS, strip_domain_suffix

if TYPE_CHECKING:
    from src.config.models import GeneratorThresholds

logger = get_logger(__name__)

# Threshold below which names are flagged for review
NAME_QUALITY_THRESHOLD = NAME_QUALITY_REVIEW_THRESHOLD


class CategoryGenerator:
    """Generate category suggestions from analysis results."""

    def __init__(
        self,
        decision_logger: DecisionLogger | None = None,
        thresholds: GeneratorThresholds | None = None,
    ):
        """
        Initialize the category generator with TF-IDF name generator.

        Args:
            decision_logger: Optional DecisionLogger for feedback learning (Task 5B.3)
            thresholds: Optional generator thresholds config. Uses defaults if None.
        """
        if thresholds is None:
            from src.config.models import GeneratorThresholds
            thresholds = GeneratorThresholds()
        self.thresholds = thresholds
        self._name_generator = TfidfNameGenerator()
        self._corpus_texts: list[str] = []
        self._decision_logger = decision_logger

    def generate_suggestions(
        self,
        analysis_results: AnalysisResults,
        min_cluster_percentage: float = 5.0,
        min_sender_count: int = 20
    ) -> list[Category]:
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
        all_categories: list[Category] = []
        total_emails = analysis_results.volume_stats.total_emails

        # Build corpus texts for TF-IDF analysis
        self._corpus_texts = self._build_corpus_texts(analysis_results)

        # FR-022: Generate from content clusters
        logger.debug(f"Generating categories from {len(analysis_results.content_clusters)} clusters")
        for cluster in analysis_results.content_clusters:
            if cluster.percentage >= min_cluster_percentage:
                category = self._category_from_cluster(cluster, total_emails)
                all_categories.append(category)
                logger.debug(f"Created cluster-based category: {category.category_name} ({cluster.percentage:.1f}%)")

        # FR-023: Generate from high-volume senders
        max_senders = self.thresholds.max_senders_for_categories
        logger.debug(f"Generating categories from top {max_senders} senders")
        for sender in analysis_results.sender_analysis.top_senders[:max_senders]:
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

        # Task 5B.3: Apply learned rename patterns to improve category names
        all_categories = self._apply_learned_patterns(all_categories)

        return all_categories

    def _apply_learned_patterns(
        self,
        categories: list[Category]
    ) -> list[Category]:
        """
        Apply learned patterns to improve category names.

        Task 5B.3: Pre-apply high-confidence rename patterns to category
        names during generation. This improves suggestions based on
        previous user feedback.

        Args:
            categories: List of generated categories

        Returns:
            Categories with learned patterns applied
        """
        if not self._decision_logger:
            return categories

        detector = PatternDetector(decision_logger=self._decision_logger)
        patterns = detector.get_high_confidence_patterns(min_confidence=0.8)

        if not patterns:
            return categories

        # Apply rename patterns to improve category names
        rename_patterns = [
            p for p in patterns if p.pattern_type == PatternType.RENAME
        ]

        for category in categories:
            for pattern in rename_patterns:
                old_name = pattern.parameters.get("old_name")
                new_name = pattern.parameters.get("new_name")
                if category.category_name == old_name:
                    logger.debug(
                        f"Applying learned rename: '{old_name}' -> '{new_name}'"
                    )
                    category.category_name = new_name
                    category.user_modified = True
                    break

        return categories

    def _category_from_cluster(self, cluster, total_emails: int) -> Category:
        """Create category from content cluster."""
        # Build cluster texts for TF-IDF analysis
        cluster_texts = []
        for sample in cluster.representative_samples:
            cluster_texts.append(f"{sample.subject} {sample.body_preview}")

        # Generate name using TF-IDF
        name, name_confidence = self._name_generator.generate_name(
            cluster_texts, self._corpus_texts
        )

        # Fall back to legacy method if TF-IDF fails
        if name == "Miscellaneous":
            sample_subjects = [s.subject for s in cluster.representative_samples[:3]]
            name = self._generate_cluster_name(sample_subjects, cluster.common_domains)

        # Score the generated name quality
        quality_score = score_name_quality(name)
        needs_review = quality_score.total_score < NAME_QUALITY_THRESHOLD

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
            example_email_ids=cluster.email_ids[:10],
            name_quality_score=quality_score.total_score,
            needs_name_review=needs_review,
        )

    def _category_from_sender(self, sender, total_emails: int) -> Category:
        """Create category from high-volume sender."""
        # Use sender domain or name for category
        name = strip_domain_suffix(sender.domain).replace('.', ' ').title()
        if not name:
            name = sender.email.split('@')[0].replace('.', ' ').title()

        percentage = (sender.frequency_count / total_emails) * 100 if total_emails > 0 else 0

        # Score the generated name quality
        full_name = f"{name} Emails"
        quality_score = score_name_quality(full_name)
        needs_review = quality_score.total_score < NAME_QUALITY_THRESHOLD

        return Category(
            category_id=f"sender_{sender.email.replace('@', '_at_').replace('.', '_')}",
            category_name=full_name,
            description=f"Emails from {sender.email} ({sender.type.value})",
            confidence=0.0,  # Will be calculated
            email_count=sender.frequency_count,
            percentage=percentage,
            source=CategorySource.SENDER,
            source_id=sender.email,
            user_modified=False,
            distinguishing_features=sender.sample_subjects[:5],
            example_email_ids=sender.email_ids[:10],
            name_quality_score=quality_score.total_score,
            needs_name_review=needs_review,
        )

    def _build_corpus_texts(self, analysis_results: AnalysisResults) -> list[str]:
        """
        Build list of text samples from all clusters for TF-IDF corpus.

        Args:
            analysis_results: Analysis results containing clusters

        Returns:
            List of text strings from all cluster samples
        """
        corpus_texts = []
        for cluster in analysis_results.content_clusters:
            for sample in cluster.representative_samples:
                corpus_texts.append(f"{sample.subject} {sample.body_preview}")
        return corpus_texts

    def _generate_cluster_name(self, subjects: list[str], domains: list[tuple]) -> str:
        """Generate descriptive name for cluster."""
        # Try to use common domain
        if domains:
            domain_name = strip_domain_suffix(domains[0][0]).replace('.', ' ').title()
            return f"{domain_name} Related"

        # Fallback to common words in subjects
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

            # Collect similar categories
            similar = [cat1]
            for j, cat2 in enumerate(categories[i + 1:], start=i + 1):
                if j in merged_indices:
                    continue

                # Check name similarity using configurable threshold
                if self._names_similar(
                    cat1.category_name,
                    cat2.category_name,
                    threshold=self.thresholds.merge_name_similarity,
                ):
                    # Check email overlap against configurable threshold
                    overlap = self._calculate_overlap(
                        set(cat1.example_email_ids),
                        set(cat2.example_email_ids)
                    )
                    if overlap > self.thresholds.merge_email_overlap:
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

    def _names_similar(
        self,
        name1: str,
        name2: str,
        threshold: float = 0.8
    ) -> bool:
        """
        Check if two category names are similar using SequenceMatcher.

        Uses difflib.SequenceMatcher for Levenshtein-like distance calculation.
        This is more accurate than simple substring matching and handles:
        - Typos and minor variations
        - Similar but not identical names
        - Partial matches with proper scoring

        Args:
            name1: First category name
            name2: Second category name
            threshold: Similarity threshold (0.0-1.0), default 0.8

        Returns:
            True if names are similar (ratio >= threshold), False otherwise
        """
        from difflib import SequenceMatcher

        n1, n2 = name1.lower(), name2.lower()

        # Exact match is always similar
        if n1 == n2:
            return True

        # Use SequenceMatcher for similarity ratio
        ratio = SequenceMatcher(None, n1, n2).ratio()

        return ratio >= threshold

    def _calculate_overlap(self, set1: set, set2: set) -> float:
        """Calculate overlap percentage between two email ID sets."""
        if not set1 or not set2:
            return 0.0
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        return intersection / union if union > 0 else 0.0

    def _merge_categories(self, categories: list[Category]) -> Category:
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

    def generate_hierarchical_suggestions(
        self,
        hierarchical_clusters: list,
        total_emails: int,
    ) -> list[Category]:
        """
        Generate hierarchical category suggestions from hierarchical clusters.

        Creates 2-level category hierarchy:
        - Level 0: Broad parent categories (e.g., "Shopping")
        - Level 1: Specific child categories (e.g., "Amazon Orders")

        Args:
            hierarchical_clusters: List of HierarchicalCluster objects from
                HierarchicalAnalyzer
            total_emails: Total emails in corpus for percentage calculation

        Returns:
            List of Category objects with hierarchical structure
        """
        if not hierarchical_clusters:
            return []

        logger.info(f"Generating hierarchical suggestions from {len(hierarchical_clusters)} clusters")
        categories: list[Category] = []

        for cluster in hierarchical_clusters:
            # Generate parent category
            parent_category = self._hierarchical_cluster_to_category(
                cluster,
                total_emails,
                level=0,
                parent_id=None,
            )

            # Generate child categories from subclusters
            if hasattr(cluster, 'subclusters') and cluster.subclusters:
                for subcluster in cluster.subclusters:
                    child_category = self._hierarchical_cluster_to_category(
                        subcluster,
                        total_emails,
                        level=1,
                        parent_id=parent_category.category_id,
                    )
                    parent_category.subcategories.append(child_category)

            categories.append(parent_category)

        # Calculate confidence for all categories
        for category in categories:
            category.confidence = calculate_confidence(category, total_emails)
            for subcategory in category.subcategories:
                subcategory.confidence = calculate_confidence(subcategory, total_emails)

        # Sort by confidence
        categories.sort(key=lambda c: c.confidence, reverse=True)

        logger.info(f"Generated {len(categories)} hierarchical categories")
        return categories

    def _hierarchical_cluster_to_category(
        self,
        cluster,
        total_emails: int,
        level: int,
        parent_id: str | None,
    ) -> Category:
        """
        Convert a HierarchicalCluster to a Category.

        Args:
            cluster: HierarchicalCluster object
            total_emails: Total emails for percentage calculation
            level: Hierarchy level (0=parent, 1=child)
            parent_id: Parent category ID (None for top-level)

        Returns:
            Category object with hierarchical fields set
        """
        # Build cluster texts for naming
        cluster_texts = []
        for sample in cluster.representative_samples:
            cluster_texts.append(f"{sample.subject} {sample.body_preview}")

        # Generate name - use broader name for parents, specific for children
        if level == 0:
            # Parent: prefer domain-based broad name
            name = self._generate_broad_category_name(cluster)
        else:
            # Child: more specific name
            name = self._generate_specific_category_name(cluster)

        # Score name quality
        quality_score = score_name_quality(name)
        needs_review = quality_score.total_score < NAME_QUALITY_THRESHOLD

        # Build description
        if level == 0:
            description = f"Broad category with {cluster.size} emails ({cluster.percentage:.1f}%)"
        else:
            description = f"Subcategory with {cluster.size} emails"

        return Category(
            category_id=f"hier_{cluster.cluster_id}",
            category_name=name,
            description=description,
            confidence=0.0,  # Will be calculated
            email_count=cluster.size,
            percentage=cluster.percentage,
            source=CategorySource.CONTENT_CLUSTER,
            source_id=cluster.cluster_id,
            user_modified=False,
            distinguishing_features=[s.subject[:50] for s in cluster.representative_samples[:3]],
            example_email_ids=cluster.email_ids[:10],
            name_quality_score=quality_score.total_score,
            needs_name_review=needs_review,
            parent_category_id=parent_id,
            level=level,
            subcategories=[],
        )

    def _generate_broad_category_name(self, cluster) -> str:
        """Generate a broad category name for parent level."""
        # Try to use common domain
        if cluster.common_domains:
            domain = cluster.common_domains[0][0]
            # Extract company name from domain
            name = strip_domain_suffix(domain)
            name = name.split('.')[-1]  # Get last part
            return name.title() + " Related"

        # Fall back to extracting common theme from samples
        if cluster.representative_samples:
            subjects = [s.subject for s in cluster.representative_samples[:3]]
            common_words = self._extract_common_words(subjects)
            if common_words:
                return common_words[0].title() + " Emails"

        return "General"

    def _generate_specific_category_name(self, cluster) -> str:
        """Generate a specific category name for child level."""
        # Try to use domain with more specificity
        if cluster.common_domains:
            domain = cluster.common_domains[0][0]
            domain_name = strip_domain_suffix(domain)
            domain_name = domain_name.split('.')[-1].title()

            # Try to add more context from samples
            if cluster.representative_samples:
                subject = cluster.representative_samples[0].subject.lower()
                if 'order' in subject:
                    return f"{domain_name} Orders"
                if 'ship' in subject or 'deliver' in subject:
                    return f"{domain_name} Shipping"
                if 'invoice' in subject or 'payment' in subject:
                    return f"{domain_name} Billing"
                if 'newsletter' in subject or 'news' in subject:
                    return f"{domain_name} Newsletter"
                return f"{domain_name} Updates"

            return f"{domain_name} Emails"

        # Fall back to subject-based naming
        if cluster.representative_samples:
            subjects = [s.subject for s in cluster.representative_samples[:3]]
            name, _ = self._name_generator.generate_name(subjects, subjects)
            if name != "Miscellaneous":
                return name

        return "Subcategory"

    def _extract_common_words(self, texts: list[str]) -> list[str]:
        """Extract common meaningful words from text list."""
        import re
        from collections import Counter

        word_counts: Counter[str] = Counter()
        for text in texts:
            words = re.findall(r'\b[a-z]+\b', text.lower())
            for word in words:
                if len(word) > 3 and word not in STOP_WORDS:
                    word_counts[word] += 1

        # Return most common words
        return [word for word, _ in word_counts.most_common(5)]

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
