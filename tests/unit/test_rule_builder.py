"""
Unit tests for RuleBuilder (Phase 3, Item 3.3).

TDD: Tests written first, implementation follows.
Tests that RuleBuilder generates CategoryRules from approved categories
using sender patterns, subject patterns, and analysis results.
"""

from __future__ import annotations

from src.models.analysis_results import (
    AnalysisResults,
    DomainCount,
    SenderAnalysis,
    SubjectPatterns,
    TemporalPatterns,
    VolumeStats,
)
from src.models.category import Category, CategorySource
from src.models.content_cluster import ContentCluster, RepresentativeSample
from src.models.rule import (
    CategoryRule,
    ConditionField,
    ConditionLogic,
    ConditionOperator,
    RuleActionType,
    RuleSet,
)
from src.models.sender import Sender, SenderType
from src.rules.builder import RuleBuilder

# =============================================================================
# Fixtures
# =============================================================================


def _make_sender(
    email: str = "news@example.com",
    name: str = "Example News",
    domain: str = "example.com",
    sender_type: SenderType = SenderType.SERVICE,
    frequency_count: int = 50,
    sample_subjects: list[str] | None = None,
    email_ids: list[str] | None = None,
) -> Sender:
    """Create a test Sender."""
    return Sender(
        email=email,
        name=name,
        domain=domain,
        type=sender_type,
        frequency_count=frequency_count,
        sample_subjects=sample_subjects or ["Weekly Update", "Monthly Report"],
        email_ids=email_ids or [f"email_{i}" for i in range(min(frequency_count, 10))],
    )


def _make_cluster(
    cluster_id: int = 0,
    size: int = 100,
    percentage: float = 10.0,
    subjects: list[str] | None = None,
    senders: list[str] | None = None,
    domains: list[tuple[str, int]] | None = None,
    email_ids: list[str] | None = None,
) -> ContentCluster:
    """Create a test ContentCluster."""
    if subjects is None:
        subjects = ["Invoice #12345", "Payment Confirmation", "Receipt for Order"]
    if senders is None:
        senders = ["billing@example.com", "noreply@store.com", "payments@shop.com"]

    samples = [
        RepresentativeSample(
            subject=subj,
            sender=sender,
            body_preview=f"Body preview for {subj}",
        )
        for subj, sender in zip(subjects, senders, strict=False)
    ]

    return ContentCluster(
        cluster_id=cluster_id,
        size=size,
        percentage=percentage,
        representative_samples=samples,
        common_domains=domains or [("example.com", 50), ("store.com", 30)],
        email_ids=email_ids or [f"email_{i}" for i in range(min(size, 10))],
        silhouette_score=0.5,
        cohesion_score=0.3,
    )


def _make_analysis_results(
    senders: list[Sender] | None = None,
    clusters: list[ContentCluster] | None = None,
    top_domains: list[DomainCount] | None = None,
    top_keywords: list[tuple[str, int]] | None = None,
    common_prefixes: dict[str, int] | None = None,
) -> AnalysisResults:
    """Create a test AnalysisResults."""
    if senders is None:
        senders = [
            _make_sender(email="news@example.com", domain="example.com", frequency_count=50),
            _make_sender(email="alerts@service.com", domain="service.com", frequency_count=30),
        ]
    if clusters is None:
        clusters = [_make_cluster()]
    if top_domains is None:
        top_domains = [
            DomainCount(domain="example.com", count=80),
            DomainCount(domain="service.com", count=40),
        ]
    if top_keywords is None:
        top_keywords = [("invoice", 45), ("payment", 30), ("order", 25)]
    if common_prefixes is None:
        common_prefixes = {"RE:": 45, "FWD:": 23}

    return AnalysisResults(
        sender_analysis=SenderAnalysis(
            top_senders=senders,
            top_domains=top_domains,
            unique_senders=len(senders),
            unique_domains=len(top_domains),
        ),
        subject_patterns=SubjectPatterns(
            common_prefixes=common_prefixes,
            numbered_patterns={"Invoice": 12, "Order": 34},
            top_keywords=top_keywords,
            bracket_tags=[("URGENT", 5)],
            total_subjects_analyzed=500,
        ),
        content_clusters=clusters,
        temporal_patterns=TemporalPatterns(
            frequency_distribution={"daily": 50, "weekly": 30},
            sender_frequencies={},
        ),
        volume_stats=VolumeStats(
            total_emails=1000,
            unique_senders=200,
            date_range={"oldest": "2025-01-01", "newest": "2025-12-31", "span_days": "365"},
            with_attachments=100,
            attachment_percentage=10.0,
            avg_body_length_chars=500,
            emails_per_day=2.7,
        ),
    )


def _make_category(
    category_id: str = "cat_newsletters",
    name: str = "Newsletters & Marketing",
    source: CategorySource = CategorySource.TEMPLATE,
    source_id: str | None = "Newsletters & Marketing",
    confidence: float = 0.85,
    email_count: int = 150,
    percentage: float = 15.0,
    features: list[str] | None = None,
    example_ids: list[str] | None = None,
) -> Category:
    """Create a test Category."""
    return Category(
        category_id=category_id,
        category_name=name,
        description=f"Category: {name}",
        confidence=confidence,
        email_count=email_count,
        percentage=percentage,
        source=source,
        source_id=source_id,
        distinguishing_features=features or ["newsletter", "subscribe", "unsubscribe"],
        example_email_ids=example_ids or [f"email_{i}" for i in range(10)],
    )


# =============================================================================
# RuleBuilder Initialization Tests
# =============================================================================


class TestRuleBuilderInit:
    """Test RuleBuilder initialization."""

    def test_create_builder(self):
        """Test that RuleBuilder can be instantiated."""
        builder = RuleBuilder()
        assert builder is not None

    def test_builder_has_build_from_category_method(self):
        """Test that RuleBuilder has the build_from_category method."""
        builder = RuleBuilder()
        assert hasattr(builder, "build_from_category")
        assert callable(builder.build_from_category)

    def test_builder_has_build_from_categories_method(self):
        """Test that RuleBuilder has the build_from_categories method."""
        builder = RuleBuilder()
        assert hasattr(builder, "build_from_categories")
        assert callable(builder.build_from_categories)


# =============================================================================
# build_from_category: Template-sourced categories
# =============================================================================


class TestBuildFromCategoryTemplate:
    """Test building rules from template-sourced categories."""

    def test_template_category_generates_rule(self):
        """Test that a template-sourced category generates a valid CategoryRule."""
        builder = RuleBuilder()
        category = _make_category(
            source=CategorySource.TEMPLATE,
            source_id="Newsletters & Marketing",
            features=["newsletter", "subscribe", "unsubscribe", "promotional"],
        )
        analysis = _make_analysis_results()

        rule = builder.build_from_category(category, analysis)

        assert isinstance(rule, CategoryRule)
        assert rule.category_id == category.category_id
        assert rule.enabled is True

    def test_template_rule_has_subject_conditions(self):
        """Test that template rules include subject keyword conditions from features."""
        builder = RuleBuilder()
        category = _make_category(
            source=CategorySource.TEMPLATE,
            source_id="Newsletters & Marketing",
            features=["newsletter", "subscribe", "promotional"],
        )
        analysis = _make_analysis_results()

        rule = builder.build_from_category(category, analysis)

        # Should have at least one subject-based condition from the template keywords
        subject_conditions = [c for c in rule.conditions if c.field == ConditionField.SUBJECT]
        assert len(subject_conditions) > 0

    def test_template_rule_has_domain_conditions(self):
        """Test that template rules include domain conditions when matching domains found."""
        builder = RuleBuilder()
        # Template that matches domains in analysis
        category = _make_category(
            source=CategorySource.TEMPLATE,
            source_id="Newsletters & Marketing",
            features=["newsletter"],
        )
        analysis = _make_analysis_results(
            top_domains=[
                DomainCount(domain="mailchimp.com", count=50),
                DomainCount(domain="example.com", count=80),
            ],
        )

        rule = builder.build_from_category(category, analysis)

        # Should find conditions (from template keywords and/or domains in data)
        assert len(rule.conditions) >= 1

    def test_template_rule_uses_or_logic(self):
        """Test that template rules with multiple diverse conditions use OR logic."""
        builder = RuleBuilder()
        category = _make_category(
            source=CategorySource.TEMPLATE,
            source_id="Newsletters & Marketing",
            features=["newsletter", "subscribe", "promotional", "digest"],
        )
        analysis = _make_analysis_results()

        rule = builder.build_from_category(category, analysis)

        # Template categories typically match on any keyword OR domain -> OR logic
        assert rule.logic == ConditionLogic.OR

    def test_template_rule_action_is_categorize(self):
        """Test that the rule action is CATEGORIZE targeting the category."""
        builder = RuleBuilder()
        category = _make_category()
        analysis = _make_analysis_results()

        rule = builder.build_from_category(category, analysis)

        assert rule.action.action_type == RuleActionType.CATEGORIZE
        assert rule.action.target == category.category_name
        assert rule.action.target_category_id == category.category_id

    def test_template_rule_id_generated(self):
        """Test that rule_id is automatically generated."""
        builder = RuleBuilder()
        category = _make_category(category_id="cat_newsletters")
        analysis = _make_analysis_results()

        rule = builder.build_from_category(category, analysis)

        assert rule.rule_id
        assert len(rule.rule_id) > 0
        assert "cat_newsletters" in rule.rule_id


# =============================================================================
# build_from_category: Sender-sourced categories
# =============================================================================


class TestBuildFromCategorySender:
    """Test building rules from sender-sourced categories."""

    def test_sender_category_generates_rule(self):
        """Test that a sender-sourced category generates a valid rule."""
        builder = RuleBuilder()
        category = _make_category(
            category_id="sender_news_at_example_com",
            name="Example News Emails",
            source=CategorySource.SENDER,
            source_id="news@example.com",
            features=["Weekly Update", "Monthly Report"],
        )
        analysis = _make_analysis_results()

        rule = builder.build_from_category(category, analysis)

        assert isinstance(rule, CategoryRule)
        assert rule.category_id == category.category_id

    def test_sender_rule_has_sender_email_condition(self):
        """Test that sender rules include a sender_email condition."""
        builder = RuleBuilder()
        category = _make_category(
            source=CategorySource.SENDER,
            source_id="news@example.com",
        )
        analysis = _make_analysis_results()

        rule = builder.build_from_category(category, analysis)

        email_conditions = [c for c in rule.conditions if c.field == ConditionField.SENDER_EMAIL]
        assert len(email_conditions) >= 1
        assert any(c.value == "news@example.com" for c in email_conditions)

    def test_sender_rule_has_domain_condition(self):
        """Test that sender rules also include a domain fallback condition."""
        builder = RuleBuilder()
        category = _make_category(
            source=CategorySource.SENDER,
            source_id="news@example.com",
        )
        analysis = _make_analysis_results()

        rule = builder.build_from_category(category, analysis)

        domain_conditions = [c for c in rule.conditions if c.field == ConditionField.SENDER_DOMAIN]
        # Should have domain condition as additional match criterion
        assert len(domain_conditions) >= 1

    def test_sender_rule_uses_or_logic(self):
        """Test that sender rules use OR logic (match email OR domain)."""
        builder = RuleBuilder()
        category = _make_category(
            source=CategorySource.SENDER,
            source_id="news@example.com",
        )
        analysis = _make_analysis_results()

        rule = builder.build_from_category(category, analysis)

        # Sender categories match on email address OR domain
        assert rule.logic == ConditionLogic.OR


# =============================================================================
# build_from_category: Cluster-sourced categories
# =============================================================================


class TestBuildFromCategoryCluster:
    """Test building rules from content cluster-sourced categories."""

    def test_cluster_category_generates_rule(self):
        """Test that a cluster-sourced category generates a valid rule."""
        builder = RuleBuilder()
        cluster = _make_cluster(
            cluster_id=3,
            subjects=["Invoice #12345", "Payment Confirmation", "Receipt for Order"],
            domains=[("billing.com", 40), ("payments.net", 20)],
        )
        category = _make_category(
            category_id="cluster_3",
            name="Billing & Payments",
            source=CategorySource.CONTENT_CLUSTER,
            source_id="3",
            features=["Invoice #12345", "Payment Confirmation", "Receipt for Order"],
        )
        analysis = _make_analysis_results(clusters=[cluster])

        rule = builder.build_from_category(category, analysis)

        assert isinstance(rule, CategoryRule)
        assert rule.category_id == category.category_id

    def test_cluster_rule_has_domain_conditions(self):
        """Test that cluster rules extract domain conditions from cluster common_domains."""
        builder = RuleBuilder()
        cluster = _make_cluster(
            cluster_id=3,
            domains=[("billing.com", 40), ("payments.net", 20)],
        )
        category = _make_category(
            category_id="cluster_3",
            source=CategorySource.CONTENT_CLUSTER,
            source_id="3",
        )
        analysis = _make_analysis_results(clusters=[cluster])

        rule = builder.build_from_category(category, analysis)

        domain_conditions = [c for c in rule.conditions if c.field == ConditionField.SENDER_DOMAIN]
        assert len(domain_conditions) >= 1

    def test_cluster_rule_has_subject_conditions(self):
        """Test that cluster rules extract keyword conditions from representative subjects."""
        builder = RuleBuilder()
        cluster = _make_cluster(
            cluster_id=3,
            subjects=["Weekly Newsletter", "Monthly Newsletter", "Newsletter Digest"],
        )
        category = _make_category(
            category_id="cluster_3",
            source=CategorySource.CONTENT_CLUSTER,
            source_id="3",
            features=["Weekly Newsletter", "Monthly Newsletter", "Newsletter Digest"],
        )
        analysis = _make_analysis_results(clusters=[cluster])

        rule = builder.build_from_category(category, analysis)

        subject_conditions = [c for c in rule.conditions if c.field == ConditionField.SUBJECT]
        assert len(subject_conditions) >= 1

    def test_cluster_rule_uses_or_logic(self):
        """Test cluster rules use OR logic (match any domain or keyword)."""
        builder = RuleBuilder()
        cluster = _make_cluster(
            cluster_id=3,
            domains=[("billing.com", 40)],
        )
        category = _make_category(
            category_id="cluster_3",
            source=CategorySource.CONTENT_CLUSTER,
            source_id="3",
        )
        analysis = _make_analysis_results(clusters=[cluster])

        rule = builder.build_from_category(category, analysis)

        assert rule.logic == ConditionLogic.OR


# =============================================================================
# build_from_category: Custom-sourced categories
# =============================================================================


class TestBuildFromCategoryCustom:
    """Test building rules from custom (user-created) categories."""

    def test_custom_category_generates_rule(self):
        """Test that a custom category generates a rule from features."""
        builder = RuleBuilder()
        category = _make_category(
            category_id="custom_important",
            name="Important Updates",
            source=CategorySource.CUSTOM,
            source_id=None,
            features=["urgent", "important", "action required"],
        )
        analysis = _make_analysis_results()

        rule = builder.build_from_category(category, analysis)

        assert isinstance(rule, CategoryRule)
        assert rule.category_id == category.category_id

    def test_custom_rule_uses_features_as_subject_keywords(self):
        """Test that custom rules use distinguishing_features as subject keywords."""
        builder = RuleBuilder()
        category = _make_category(
            source=CategorySource.CUSTOM,
            features=["urgent", "important", "action required"],
        )
        analysis = _make_analysis_results()

        rule = builder.build_from_category(category, analysis)

        subject_conditions = [c for c in rule.conditions if c.field == ConditionField.SUBJECT]
        assert len(subject_conditions) >= 1


# =============================================================================
# Priority Assignment
# =============================================================================


class TestPriorityAssignment:
    """Test confidence-based priority assignment."""

    def test_high_confidence_gets_high_priority(self):
        """Test that high confidence categories get high priority."""
        builder = RuleBuilder()
        category = _make_category(confidence=0.95)
        analysis = _make_analysis_results()

        rule = builder.build_from_category(category, analysis)

        assert rule.priority >= 90

    def test_medium_confidence_gets_medium_priority(self):
        """Test that medium confidence categories get medium priority."""
        builder = RuleBuilder()
        category = _make_category(confidence=0.50)
        analysis = _make_analysis_results()

        rule = builder.build_from_category(category, analysis)

        assert 40 <= rule.priority <= 60

    def test_low_confidence_gets_low_priority(self):
        """Test that low confidence categories get low priority."""
        builder = RuleBuilder()
        category = _make_category(confidence=0.10)
        analysis = _make_analysis_results()

        rule = builder.build_from_category(category, analysis)

        assert rule.priority <= 15

    def test_priority_is_integer(self):
        """Test that priority is always an integer."""
        builder = RuleBuilder()
        category = _make_category(confidence=0.73)
        analysis = _make_analysis_results()

        rule = builder.build_from_category(category, analysis)

        assert isinstance(rule.priority, int)

    def test_higher_confidence_higher_priority(self):
        """Test that higher confidence always produces higher or equal priority."""
        builder = RuleBuilder()
        analysis = _make_analysis_results()

        rule_low = builder.build_from_category(
            _make_category(category_id="cat_low", confidence=0.3), analysis
        )
        rule_high = builder.build_from_category(
            _make_category(category_id="cat_high", confidence=0.9), analysis
        )

        assert rule_high.priority > rule_low.priority


# =============================================================================
# build_from_categories (batch)
# =============================================================================


class TestBuildFromCategories:
    """Test batch rule generation from multiple categories."""

    def test_builds_ruleset_from_multiple_categories(self):
        """Test that build_from_categories returns a RuleSet."""
        builder = RuleBuilder()
        categories = [
            _make_category(category_id="cat_1", name="Category One"),
            _make_category(category_id="cat_2", name="Category Two"),
        ]
        analysis = _make_analysis_results()

        ruleset = builder.build_from_categories(categories, analysis)

        assert isinstance(ruleset, RuleSet)
        assert ruleset.rule_count == 2

    def test_ruleset_has_unique_rule_ids(self):
        """Test that all rules in the set have unique IDs."""
        builder = RuleBuilder()
        categories = [
            _make_category(category_id="cat_1"),
            _make_category(category_id="cat_2"),
            _make_category(category_id="cat_3"),
        ]
        analysis = _make_analysis_results()

        ruleset = builder.build_from_categories(categories, analysis)

        rule_ids = [r.rule_id for r in ruleset.rules]
        assert len(rule_ids) == len(set(rule_ids))

    def test_ruleset_tracks_source_category_ids(self):
        """Test that the RuleSet records which category IDs were used."""
        builder = RuleBuilder()
        categories = [
            _make_category(category_id="cat_a"),
            _make_category(category_id="cat_b"),
        ]
        analysis = _make_analysis_results()

        ruleset = builder.build_from_categories(categories, analysis)

        assert "cat_a" in ruleset.source_category_ids
        assert "cat_b" in ruleset.source_category_ids

    def test_empty_categories_list(self):
        """Test that empty categories list returns empty RuleSet."""
        builder = RuleBuilder()
        analysis = _make_analysis_results()

        ruleset = builder.build_from_categories([], analysis)

        assert isinstance(ruleset, RuleSet)
        assert ruleset.rule_count == 0

    def test_ruleset_description_auto_generated(self):
        """Test that the RuleSet gets an auto-generated description."""
        builder = RuleBuilder()
        categories = [_make_category(category_id="cat_1")]
        analysis = _make_analysis_results()

        ruleset = builder.build_from_categories(categories, analysis)

        assert ruleset.description
        assert len(ruleset.description) > 0

    def test_rules_sorted_by_priority(self):
        """Test that rules in the set are sorted by priority (highest first)."""
        builder = RuleBuilder()
        categories = [
            _make_category(category_id="cat_low", confidence=0.2),
            _make_category(category_id="cat_high", confidence=0.95),
            _make_category(category_id="cat_mid", confidence=0.5),
        ]
        analysis = _make_analysis_results()

        ruleset = builder.build_from_categories(categories, analysis)

        priorities = [r.priority for r in ruleset.rules]
        assert priorities == sorted(priorities, reverse=True)

    def test_mixed_source_categories(self):
        """Test building rules from categories with different sources."""
        builder = RuleBuilder()
        categories = [
            _make_category(
                category_id="cat_tmpl",
                source=CategorySource.TEMPLATE,
                source_id="Newsletters & Marketing",
                features=["newsletter", "subscribe"],
            ),
            _make_category(
                category_id="cat_sender",
                source=CategorySource.SENDER,
                source_id="news@example.com",
                features=["Weekly Update"],
            ),
            _make_category(
                category_id="cat_cluster",
                source=CategorySource.CONTENT_CLUSTER,
                source_id="3",
                features=["Invoice", "Payment"],
            ),
        ]
        analysis = _make_analysis_results(clusters=[_make_cluster(cluster_id=3)])

        ruleset = builder.build_from_categories(categories, analysis)

        assert ruleset.rule_count == 3
        # Each rule should reference its category
        category_ids = {r.category_id for r in ruleset.rules}
        assert category_ids == {"cat_tmpl", "cat_sender", "cat_cluster"}


# =============================================================================
# Rule Name Generation
# =============================================================================


class TestRuleNameGeneration:
    """Test that rules get meaningful names."""

    def test_rule_name_includes_category_name(self):
        """Test that rule name references the category."""
        builder = RuleBuilder()
        category = _make_category(name="Billing & Payments")
        analysis = _make_analysis_results()

        rule = builder.build_from_category(category, analysis)

        assert "Billing & Payments" in rule.name

    def test_rule_description_non_empty(self):
        """Test that rule description is generated."""
        builder = RuleBuilder()
        category = _make_category()
        analysis = _make_analysis_results()

        rule = builder.build_from_category(category, analysis)

        assert rule.description
        assert len(rule.description) > 0


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_category_with_no_features(self):
        """Test category with empty distinguishing_features still generates a rule."""
        builder = RuleBuilder()
        category = _make_category(features=[])
        analysis = _make_analysis_results()

        rule = builder.build_from_category(category, analysis)

        assert isinstance(rule, CategoryRule)
        assert len(rule.conditions) >= 1

    def test_category_with_zero_email_count(self):
        """Test category with zero emails still generates a rule."""
        builder = RuleBuilder()
        category = _make_category(email_count=0, percentage=0.0)
        analysis = _make_analysis_results()

        rule = builder.build_from_category(category, analysis)

        assert isinstance(rule, CategoryRule)

    def test_category_with_zero_confidence(self):
        """Test that zero confidence gets priority 0."""
        builder = RuleBuilder()
        category = _make_category(confidence=0.0)
        analysis = _make_analysis_results()

        rule = builder.build_from_category(category, analysis)

        assert rule.priority == 0

    def test_category_with_max_confidence(self):
        """Test that max confidence (1.0) gets priority 100."""
        builder = RuleBuilder()
        category = _make_category(confidence=1.0)
        analysis = _make_analysis_results()

        rule = builder.build_from_category(category, analysis)

        assert rule.priority == 100

    def test_sender_category_with_no_matching_sender_in_analysis(self):
        """Test sender category when the sender is not in analysis results."""
        builder = RuleBuilder()
        category = _make_category(
            source=CategorySource.SENDER,
            source_id="unknown@nowhere.com",
        )
        # Analysis has different senders
        analysis = _make_analysis_results(
            senders=[_make_sender(email="other@example.com", domain="example.com")]
        )

        rule = builder.build_from_category(category, analysis)

        # Should still generate a rule using the source_id email
        assert isinstance(rule, CategoryRule)
        email_conditions = [c for c in rule.conditions if c.field == ConditionField.SENDER_EMAIL]
        assert len(email_conditions) >= 1

    def test_cluster_category_with_no_matching_cluster_in_analysis(self):
        """Test cluster category when cluster is not in analysis results."""
        builder = RuleBuilder()
        category = _make_category(
            category_id="cluster_99",
            source=CategorySource.CONTENT_CLUSTER,
            source_id="99",
            features=["Update", "News", "Report"],
        )
        # Analysis has cluster_0 not cluster_99
        analysis = _make_analysis_results()

        rule = builder.build_from_category(category, analysis)

        # Should fall back to using features as conditions
        assert isinstance(rule, CategoryRule)
        assert len(rule.conditions) >= 1

    def test_conditions_are_case_insensitive(self):
        """Test that generated conditions default to case-insensitive."""
        builder = RuleBuilder()
        category = _make_category(features=["Newsletter"])
        analysis = _make_analysis_results()

        rule = builder.build_from_category(category, analysis)

        for condition in rule.conditions:
            assert condition.case_sensitive is False

    def test_rule_serialization_roundtrip(self):
        """Test that generated rules can be serialized and deserialized."""
        builder = RuleBuilder()
        category = _make_category()
        analysis = _make_analysis_results()

        rule = builder.build_from_category(category, analysis)

        data = rule.model_dump(mode="json")
        restored = CategoryRule.model_validate(data)
        assert restored.rule_id == rule.rule_id
        assert restored.category_id == rule.category_id
        assert len(restored.conditions) == len(rule.conditions)

    def test_ruleset_serialization_roundtrip(self):
        """Test that generated RuleSet can be serialized and deserialized."""
        builder = RuleBuilder()
        categories = [
            _make_category(category_id="cat_1"),
            _make_category(category_id="cat_2"),
        ]
        analysis = _make_analysis_results()

        ruleset = builder.build_from_categories(categories, analysis)

        data = ruleset.model_dump(mode="json")
        restored = RuleSet.model_validate(data)
        assert restored.rule_count == ruleset.rule_count


# =============================================================================
# Condition Operator Selection
# =============================================================================


class TestConditionOperators:
    """Test that appropriate operators are selected for different condition types."""

    def test_domain_conditions_use_equals(self):
        """Test that domain conditions use EQUALS operator."""
        builder = RuleBuilder()
        category = _make_category(
            source=CategorySource.SENDER,
            source_id="news@example.com",
        )
        analysis = _make_analysis_results()

        rule = builder.build_from_category(category, analysis)

        domain_conditions = [c for c in rule.conditions if c.field == ConditionField.SENDER_DOMAIN]
        for cond in domain_conditions:
            assert cond.operator == ConditionOperator.EQUALS

    def test_email_conditions_use_equals(self):
        """Test that sender_email conditions use EQUALS operator."""
        builder = RuleBuilder()
        category = _make_category(
            source=CategorySource.SENDER,
            source_id="news@example.com",
        )
        analysis = _make_analysis_results()

        rule = builder.build_from_category(category, analysis)

        email_conditions = [c for c in rule.conditions if c.field == ConditionField.SENDER_EMAIL]
        for cond in email_conditions:
            assert cond.operator == ConditionOperator.EQUALS

    def test_subject_keyword_conditions_use_contains(self):
        """Test that subject keyword conditions use CONTAINS operator."""
        builder = RuleBuilder()
        category = _make_category(
            source=CategorySource.TEMPLATE,
            features=["newsletter", "subscribe"],
        )
        analysis = _make_analysis_results()

        rule = builder.build_from_category(category, analysis)

        subject_conditions = [c for c in rule.conditions if c.field == ConditionField.SUBJECT]
        for cond in subject_conditions:
            assert cond.operator == ConditionOperator.CONTAINS
