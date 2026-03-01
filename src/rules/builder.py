"""
Rule builder for auto-generating rules from approved categories (Phase 3, Item 3.3).

Generates CategoryRules from approved categories and analysis results by extracting
sender patterns (top senders/domains), subject patterns (keywords/prefixes), and
cluster metadata into rule conditions.

Confidence-based priority: higher confidence categories get higher priority rules.
Logic selection: OR logic for categories with diverse matching criteria (most cases),
AND logic only when conditions are tightly coupled (rare).
"""

from __future__ import annotations

import logging
import re
from collections import Counter
from datetime import datetime, timezone

from src.models.analysis_results import AnalysisResults
from src.models.category import Category, CategorySource
from src.models.category_template import PREDEFINED_TEMPLATES, CategoryTemplate
from src.models.content_cluster import ContentCluster
from src.models.rule import (
    CategoryRule,
    ConditionField,
    ConditionLogic,
    ConditionOperator,
    RuleAction,
    RuleActionType,
    RuleCondition,
    RuleSet,
)

logger = logging.getLogger(__name__)

# Stop words to exclude from keyword extraction
_STOP_WORDS = frozenset(
    {
        "the",
        "a",
        "an",
        "and",
        "or",
        "but",
        "in",
        "on",
        "at",
        "to",
        "for",
        "of",
        "with",
        "by",
        "from",
        "is",
        "it",
        "this",
        "that",
        "was",
        "are",
        "be",
        "has",
        "had",
        "have",
        "do",
        "does",
        "did",
        "will",
        "would",
        "could",
        "should",
        "may",
        "might",
        "can",
        "not",
        "no",
        "so",
        "if",
        "than",
        "then",
        "just",
        "about",
        "up",
        "out",
        "your",
        "you",
        "we",
        "our",
        "my",
        "me",
        "us",
        "them",
        "their",
        "its",
        "all",
        "any",
        "some",
        "each",
        "every",
        "both",
        "few",
        "more",
        "most",
        "other",
        "into",
        "over",
        "after",
        "before",
        "between",
        "under",
        "again",
        "here",
        "there",
        "when",
        "where",
        "how",
        "what",
        "which",
        "who",
        "whom",
        "why",
        "been",
        "being",
        "also",
        "very",
        "too",
        "only",
        "own",
        "same",
        "new",
        "old",
        "one",
        "two",
        "three",
        "first",
        "last",
        "long",
        "great",
        "little",
        "right",
        "still",
        "back",
        "even",
        "much",
        "well",
        "way",
        "day",
        "part",
        "people",
        "know",
        "take",
        "come",
        "get",
        "make",
        "like",
        "see",
        "look",
        "find",
        "give",
        "tell",
        "think",
        "say",
        "help",
        "show",
        "try",
        "ask",
        "need",
        "want",
        "use",
        "call",
        "keep",
        "let",
        "put",
        "set",
        "seem",
        "run",
        "body",
        "preview",
        "email",
        "subject",
        "dear",
        "hello",
        "hi",
        "thanks",
        "thank",
        "regards",
        "sincerely",
        "best",
        "please",
    }
)

# Maximum number of keyword conditions to add per rule
_MAX_KEYWORD_CONDITIONS = 5

# Maximum number of domain conditions to add per rule
_MAX_DOMAIN_CONDITIONS = 3

# Minimum keyword length to include
_MIN_KEYWORD_LENGTH = 3


class RuleBuilder:
    """
    Builds CategoryRules from approved categories and analysis results.

    Extracts sender patterns, subject patterns, and cluster metadata to generate
    rule conditions that match the emails defining each category.
    """

    def build_from_category(
        self,
        category: Category,
        analysis_results: AnalysisResults,
    ) -> CategoryRule:
        """
        Generate a CategoryRule from a single approved category.

        Dispatches to source-specific builders (template, sender, cluster, custom)
        to extract the most relevant conditions from the category's metadata
        and the analysis results.

        Args:
            category: An approved category to generate a rule for.
            analysis_results: Complete analysis results for context.

        Returns:
            A CategoryRule matching the patterns that defined the category.
        """
        # Build conditions based on category source
        if category.source == CategorySource.TEMPLATE:
            conditions = self._conditions_from_template(category, analysis_results)
        elif category.source == CategorySource.SENDER:
            conditions = self._conditions_from_sender(category, analysis_results)
        elif category.source == CategorySource.CONTENT_CLUSTER:
            conditions = self._conditions_from_cluster(category, analysis_results)
        else:
            # CUSTOM or unknown source - use features as keywords
            conditions = self._conditions_from_custom(category, analysis_results)

        # Fallback: if no conditions could be extracted, use category name as keyword
        if not conditions:
            conditions = [
                RuleCondition(
                    field=ConditionField.SUBJECT,
                    operator=ConditionOperator.CONTAINS,
                    value=category.category_name,
                    case_sensitive=False,
                )
            ]

        # Build action
        action = RuleAction(
            action_type=RuleActionType.CATEGORIZE,
            target=category.category_name,
            target_category_id=category.category_id,
        )

        # Calculate priority from confidence (0.0-1.0 -> 0-100)
        priority = self._confidence_to_priority(category.confidence)

        # Determine logic: OR for most cases (match any condition)
        logic = ConditionLogic.OR

        # Build rule
        rule = CategoryRule(
            rule_id=f"rule_{category.category_id}",
            name=f"Rule: {category.category_name}",
            description=self._generate_description(category, conditions),
            conditions=conditions,
            action=action,
            logic=logic,
            priority=priority,
            enabled=True,
            category_id=category.category_id,
        )

        logger.debug(
            f"Built rule '{rule.name}' with {rule.condition_count} conditions, "
            f"priority={rule.priority}, logic={rule.logic.value}"
        )

        return rule

    def build_from_categories(
        self,
        categories: list[Category],
        analysis_results: AnalysisResults,
    ) -> RuleSet:
        """
        Generate a RuleSet from multiple approved categories.

        Args:
            categories: List of approved categories.
            analysis_results: Complete analysis results for context.

        Returns:
            A RuleSet containing one rule per category, sorted by priority.
        """
        rules: list[CategoryRule] = []

        for category in categories:
            rule = self.build_from_category(category, analysis_results)
            rules.append(rule)

        # Sort by priority descending (highest first)
        rules.sort(key=lambda r: r.priority, reverse=True)

        now = datetime.now(timezone.utc)

        ruleset = RuleSet(
            rules=rules,
            version="1.0",
            description=f"Auto-generated rules from {len(categories)} approved categories",
            created_date=now,
            last_modified=now,
            source_category_ids=[c.category_id for c in categories],
        )

        logger.info(
            f"Built RuleSet with {ruleset.rule_count} rules from {len(categories)} categories"
        )

        return ruleset

    # =========================================================================
    # Source-specific condition builders
    # =========================================================================

    def _conditions_from_template(
        self,
        category: Category,
        analysis_results: AnalysisResults,
    ) -> list[RuleCondition]:
        """
        Extract conditions from a template-sourced category.

        Uses template keywords as subject conditions and template domains
        (cross-referenced with analysis results) as domain conditions.
        """
        conditions: list[RuleCondition] = []

        # Find matching template by source_id
        template = self._find_template(category.source_id)

        if template:
            # Add keyword conditions from template
            keywords_to_use = template.keywords[:_MAX_KEYWORD_CONDITIONS]
            for keyword in keywords_to_use:
                conditions.append(
                    RuleCondition(
                        field=ConditionField.SUBJECT,
                        operator=ConditionOperator.CONTAINS,
                        value=keyword,
                        case_sensitive=False,
                    )
                )

            # Add domain conditions from template (limited)
            # Cross-reference with actual analysis to only include domains present in data
            analysis_domains = {
                d.domain.lower() for d in analysis_results.sender_analysis.top_domains
            }
            # Also include cluster common_domains
            for cluster in analysis_results.content_clusters:
                for domain_tuple in cluster.common_domains:
                    analysis_domains.add(domain_tuple[0].lower())

            matched_template_domains = [
                d for d in template.domains if d.lower() in analysis_domains
            ]
            for domain in matched_template_domains[:_MAX_DOMAIN_CONDITIONS]:
                conditions.append(
                    RuleCondition(
                        field=ConditionField.SENDER_DOMAIN,
                        operator=ConditionOperator.EQUALS,
                        value=domain.lower(),
                        case_sensitive=False,
                    )
                )
        else:
            # No template found - use distinguishing features as keywords
            conditions.extend(self._conditions_from_features(category.distinguishing_features))

        return conditions

    def _conditions_from_sender(
        self,
        category: Category,
        analysis_results: AnalysisResults,
    ) -> list[RuleCondition]:
        """
        Extract conditions from a sender-sourced category.

        Primary condition: sender email address (exact match).
        Secondary condition: sender domain (for catching related addresses).
        """
        conditions: list[RuleCondition] = []

        sender_email = category.source_id or ""

        if sender_email:
            # Primary: exact email match
            conditions.append(
                RuleCondition(
                    field=ConditionField.SENDER_EMAIL,
                    operator=ConditionOperator.EQUALS,
                    value=sender_email,
                    case_sensitive=False,
                )
            )

            # Secondary: domain match for related senders
            domain = sender_email.split("@")[-1] if "@" in sender_email else ""
            if domain:
                conditions.append(
                    RuleCondition(
                        field=ConditionField.SENDER_DOMAIN,
                        operator=ConditionOperator.EQUALS,
                        value=domain,
                        case_sensitive=False,
                    )
                )

        # If no sender email, fall back to features
        if not conditions:
            conditions.extend(self._conditions_from_features(category.distinguishing_features))

        return conditions

    def _conditions_from_cluster(
        self,
        category: Category,
        analysis_results: AnalysisResults,
    ) -> list[RuleCondition]:
        """
        Extract conditions from a cluster-sourced category.

        Uses cluster common_domains as domain conditions and extracts
        keywords from representative sample subjects as subject conditions.
        """
        conditions: list[RuleCondition] = []

        # Find matching cluster
        cluster = self._find_cluster(category.source_id, analysis_results)

        if cluster:
            # Add domain conditions from cluster
            for domain_tuple in cluster.common_domains[:_MAX_DOMAIN_CONDITIONS]:
                domain = domain_tuple[0]
                conditions.append(
                    RuleCondition(
                        field=ConditionField.SENDER_DOMAIN,
                        operator=ConditionOperator.EQUALS,
                        value=domain.lower(),
                        case_sensitive=False,
                    )
                )

            # Extract keywords from representative subjects
            keywords = self._extract_keywords_from_samples(cluster)
            for keyword in keywords[:_MAX_KEYWORD_CONDITIONS]:
                conditions.append(
                    RuleCondition(
                        field=ConditionField.SUBJECT,
                        operator=ConditionOperator.CONTAINS,
                        value=keyword,
                        case_sensitive=False,
                    )
                )
        else:
            # Cluster not found in analysis - use features as fallback
            conditions.extend(self._conditions_from_features(category.distinguishing_features))

        return conditions

    def _conditions_from_custom(
        self,
        category: Category,
        analysis_results: AnalysisResults,
    ) -> list[RuleCondition]:
        """
        Extract conditions from a custom (user-created) category.

        Uses distinguishing_features as keyword conditions since custom
        categories have no template or cluster backing.
        """
        return self._conditions_from_features(category.distinguishing_features)

    # =========================================================================
    # Helpers
    # =========================================================================

    def _conditions_from_features(
        self,
        features: list[str],
    ) -> list[RuleCondition]:
        """
        Convert distinguishing features into subject CONTAINS conditions.

        Args:
            features: List of distinguishing feature strings.

        Returns:
            List of RuleConditions for subject matching.
        """
        conditions: list[RuleCondition] = []

        for feature in features[:_MAX_KEYWORD_CONDITIONS]:
            # Clean feature text: strip leading/trailing whitespace
            cleaned = feature.strip()
            if cleaned and len(cleaned) >= _MIN_KEYWORD_LENGTH:
                conditions.append(
                    RuleCondition(
                        field=ConditionField.SUBJECT,
                        operator=ConditionOperator.CONTAINS,
                        value=cleaned,
                        case_sensitive=False,
                    )
                )

        return conditions

    def _find_template(self, source_id: str | None) -> CategoryTemplate | None:
        """Find predefined template by name (source_id)."""
        if not source_id:
            return None
        for template in PREDEFINED_TEMPLATES:
            if template.name == source_id:
                return template
        return None

    def _find_cluster(
        self,
        source_id: str | None,
        analysis_results: AnalysisResults,
    ) -> ContentCluster | None:
        """Find content cluster by ID (source_id)."""
        if source_id is None:
            return None
        try:
            cluster_id = int(source_id)
        except (ValueError, TypeError):
            return None
        for cluster in analysis_results.content_clusters:
            if cluster.cluster_id == cluster_id:
                return cluster
        return None

    def _extract_keywords_from_samples(
        self,
        cluster: ContentCluster,
    ) -> list[str]:
        """
        Extract meaningful keywords from cluster representative samples.

        Uses word frequency across subjects and body previews to find
        the most distinctive terms for the cluster.
        """
        word_counts: Counter[str] = Counter()

        for sample in cluster.representative_samples:
            text = f"{sample.subject} {sample.body_preview}".lower()
            words = re.findall(r"\b[a-z]+\b", text)
            for word in words:
                if len(word) >= _MIN_KEYWORD_LENGTH and word not in _STOP_WORDS:
                    word_counts[word] += 1

        # Return most common keywords
        return [word for word, _ in word_counts.most_common(_MAX_KEYWORD_CONDITIONS)]

    @staticmethod
    def _confidence_to_priority(confidence: float) -> int:
        """
        Convert confidence score (0.0-1.0) to priority (0-100).

        Linear mapping: priority = round(confidence * 100).
        """
        return round(confidence * 100)

    @staticmethod
    def _generate_description(
        category: Category,
        conditions: list[RuleCondition],
    ) -> str:
        """Generate a human-readable description of the rule."""
        source_label = category.source.value.replace("_", " ").title()
        condition_types = set()
        for c in conditions:
            if c.field == ConditionField.SENDER_EMAIL:
                condition_types.add("sender email")
            elif c.field == ConditionField.SENDER_DOMAIN:
                condition_types.add("sender domain")
            elif c.field == ConditionField.SUBJECT:
                condition_types.add("subject keyword")
            elif c.field == ConditionField.BODY:
                condition_types.add("body keyword")

        types_str = ", ".join(sorted(condition_types)) if condition_types else "general"
        return (
            f"Auto-generated from {source_label} category '{category.category_name}'. "
            f"Matches by: {types_str}."
        )
