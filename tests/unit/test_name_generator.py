"""
Unit tests for TF-IDF name generator.

Tests TfidfNameGenerator class for generating descriptive category names
from email clusters using TF-IDF analysis.
"""
import pytest

from src.generators.name_generator import (
    TfidfNameGenerator,
    score_name_quality,
    NameQualityScore,
)


# -----------------------------------------------------------------------------
# Task 2B.1: TF-IDF Name Generator Tests
# -----------------------------------------------------------------------------

class TestTfidfNameGenerator:
    """Test cases for TfidfNameGenerator class."""

    def test_tfidf_finds_distinguishing_terms(self):
        """Should identify terms unique to cluster vs corpus.

        Given a cluster with specific terms that appear less frequently
        in the overall corpus, TF-IDF should highlight those distinguishing terms.
        """
        generator = TfidfNameGenerator()

        # Cluster emails about invoice/payment (specific)
        cluster_texts = [
            "Your invoice #12345 is ready for payment",
            "Invoice attached - payment due by Friday",
            "Payment confirmation for invoice INV-2024-001",
        ]

        # Corpus has more generic emails
        corpus_texts = [
            "Hello, how are you?",
            "Meeting tomorrow at 3pm",
            "Please review the attached document",
            "Weekly team update",
            "Your invoice #12345 is ready for payment",  # One overlap
        ]

        name, confidence = generator.generate_name(cluster_texts, corpus_texts)

        # Name should contain distinguishing terms like invoice, payment
        name_lower = name.lower()
        assert any(term in name_lower for term in ["invoice", "payment"])
        assert confidence > 0

    def test_tfidf_filters_stop_words(self):
        """Should not include 'the', 'and', etc in names."""
        generator = TfidfNameGenerator()

        cluster_texts = [
            "The quick brown fox jumps over the lazy dog",
            "A brown and orange fox is running fast",
        ]
        corpus_texts = [
            "Meeting at the office",
            "The report is ready",
        ]

        name, _ = generator.generate_name(cluster_texts, corpus_texts)
        name_lower = name.lower()

        # Common stop words should not be in the name
        stop_words = ["the", "and", "a", "is", "over", "at"]
        for word in name_lower.split():
            assert word not in stop_words, f"Stop word '{word}' found in name"

    def test_tfidf_handles_empty_cluster(self):
        """Should return 'Miscellaneous' for empty input."""
        generator = TfidfNameGenerator()

        cluster_texts = []
        corpus_texts = ["Some email", "Another email"]

        name, confidence = generator.generate_name(cluster_texts, corpus_texts)

        assert name == "Miscellaneous"
        assert confidence == 0.0

    def test_tfidf_limits_name_length(self):
        """Names should be 2-4 words."""
        generator = TfidfNameGenerator()

        cluster_texts = [
            "Amazon order confirmation shipping delivery tracking number update",
            "Your Amazon package shipped with tracking delivery estimate",
            "Amazon delivery notification shipping confirmation arrived",
        ]
        corpus_texts = [
            "Hello world",
            "Meeting notes",
        ]

        name, _ = generator.generate_name(cluster_texts, corpus_texts)

        word_count = len(name.split())
        assert 2 <= word_count <= 4, f"Name '{name}' has {word_count} words, expected 2-4"

    def test_tfidf_handles_single_text(self):
        """Should work with single cluster text."""
        generator = TfidfNameGenerator()

        cluster_texts = ["Amazon order shipped - tracking available"]
        corpus_texts = ["Other email", "Another email"]

        name, confidence = generator.generate_name(cluster_texts, corpus_texts)

        assert name != "Miscellaneous"
        assert confidence > 0

    def test_tfidf_returns_confidence_score(self):
        """Should return a confidence score between 0 and 1."""
        generator = TfidfNameGenerator()

        cluster_texts = [
            "Invoice payment due",
            "Payment received for invoice",
        ]
        corpus_texts = ["Hello", "Meeting"]

        name, confidence = generator.generate_name(cluster_texts, corpus_texts)

        assert 0.0 <= confidence <= 1.0

    def test_tfidf_handles_identical_cluster_and_corpus(self):
        """Should still generate name when cluster equals corpus."""
        generator = TfidfNameGenerator()

        texts = [
            "Invoice payment due",
            "Payment received",
        ]

        name, confidence = generator.generate_name(texts, texts)

        # Should still return something reasonable
        assert name is not None
        assert isinstance(name, str)

    def test_tfidf_empty_corpus_uses_cluster_terms(self):
        """Should use cluster terms when corpus is empty."""
        generator = TfidfNameGenerator()

        cluster_texts = [
            "Amazon shipping notification",
            "Amazon order delivered",
        ]
        corpus_texts = []

        name, confidence = generator.generate_name(cluster_texts, corpus_texts)

        assert "Amazon" in name or "Shipping" in name or "Order" in name

    def test_tfidf_proper_noun_capitalization(self):
        """Should properly capitalize names."""
        generator = TfidfNameGenerator()

        cluster_texts = [
            "amazon shipping update",
            "amazon order confirmation",
        ]
        corpus_texts = ["meeting notes", "hello"]

        name, _ = generator.generate_name(cluster_texts, corpus_texts)

        # Name should be title case
        assert name[0].isupper() or name == "Miscellaneous"


# -----------------------------------------------------------------------------
# Task 2B.2: Name Quality Scoring Tests
# -----------------------------------------------------------------------------

class TestNameQualityScoring:
    """Test cases for score_name_quality function."""

    def test_good_name_high_score(self):
        """Good names should score > 0.7."""
        good_names = [
            "Amazon Order Confirmations",
            "Weekly Team Updates",
            "Bank Statement Alerts",
            "GitHub Pull Requests",
            "LinkedIn Job Notifications",
        ]

        for name in good_names:
            score = score_name_quality(name)
            assert score.total_score > 0.7, f"'{name}' scored {score.total_score}, expected > 0.7"

    def test_poor_name_low_score(self):
        """Poor names should score < 0.4."""
        poor_names = [
            "Email Category",
            "Miscellaneous",
            "Related",
            "Stuff",
            "Items",
        ]

        for name in poor_names:
            score = score_name_quality(name)
            assert score.total_score < 0.4, f"'{name}' scored {score.total_score}, expected < 0.4"

    def test_penalize_too_short(self):
        """Should penalize names that are too short (1 word)."""
        score_short = score_name_quality("Emails")
        score_good = score_name_quality("Amazon Order Emails")

        assert score_short.length_penalty < 0
        assert score_good.total_score > score_short.total_score

    def test_penalize_too_long(self):
        """Should penalize names that are too long (>4 words)."""
        score_long = score_name_quality("Very Long Category Name That Is Too Verbose")
        score_good = score_name_quality("Weekly Team Updates")

        assert score_long.length_penalty < 0
        assert score_good.total_score > score_long.total_score

    def test_penalize_generic_words(self):
        """Should penalize names with generic words."""
        score_generic = score_name_quality("Email Category")
        score_specific = score_name_quality("Amazon Shipping Updates")

        assert score_generic.generic_penalty < 0
        assert score_specific.total_score > score_generic.total_score

    def test_penalize_all_caps(self):
        """Should penalize names that are all caps."""
        score_caps = score_name_quality("AMAZON ORDERS")
        score_normal = score_name_quality("Amazon Orders")

        assert score_caps.caps_penalty < 0
        assert score_normal.total_score > score_caps.total_score

    def test_reward_specific_terms(self):
        """Should reward names with specific/concrete terms."""
        score = score_name_quality("Invoice Payment Reminders")

        assert score.specificity_bonus > 0

    def test_reward_proper_nouns(self):
        """Should reward names with proper nouns."""
        score_proper = score_name_quality("Amazon Order Confirmations")
        score_generic = score_name_quality("order confirmations")

        assert score_proper.proper_noun_bonus > 0
        assert score_proper.total_score > score_generic.total_score

    def test_reward_action_words(self):
        """Should reward names with action words."""
        score = score_name_quality("Shipping Updates")

        # "Updates" and "Shipping" are action-oriented
        assert score.action_bonus >= 0

    def test_returns_component_breakdown(self):
        """Should return score with component breakdown."""
        score = score_name_quality("Amazon Order Confirmations")

        assert isinstance(score, NameQualityScore)
        assert hasattr(score, 'total_score')
        assert hasattr(score, 'length_penalty')
        assert hasattr(score, 'generic_penalty')
        assert hasattr(score, 'caps_penalty')
        assert hasattr(score, 'specificity_bonus')
        assert hasattr(score, 'proper_noun_bonus')
        assert hasattr(score, 'action_bonus')

    def test_score_bounded_zero_to_one(self):
        """Total score should be bounded between 0 and 1."""
        names = [
            "Amazon",
            "EMAIL CATEGORY STUFF GENERIC ITEMS MISCELLANEOUS",
            "Amazon Order Confirmations",
            "",
            "a",
        ]

        for name in names:
            score = score_name_quality(name)
            assert 0.0 <= score.total_score <= 1.0, f"'{name}' score {score.total_score} out of bounds"

    def test_empty_name_zero_score(self):
        """Empty name should score 0."""
        score = score_name_quality("")
        assert score.total_score == 0.0

    def test_whitespace_only_zero_score(self):
        """Whitespace-only name should score 0."""
        score = score_name_quality("   ")
        assert score.total_score == 0.0


class TestNameQualityEdgeCases:
    """Edge case tests for name quality scoring."""

    def test_unicode_characters(self):
        """Should handle unicode characters gracefully."""
        score = score_name_quality("Cafe Updates")
        assert 0.0 <= score.total_score <= 1.0

    def test_numbers_in_name(self):
        """Should handle numbers in names."""
        score = score_name_quality("Q4 2024 Reports")
        assert 0.0 <= score.total_score <= 1.0

    def test_mixed_case(self):
        """Should handle mixed case appropriately."""
        score = score_name_quality("iPhone Order Updates")
        assert 0.0 <= score.total_score <= 1.0
        assert score.caps_penalty == 0  # Should not penalize proper mixed case

    def test_hyphenated_words(self):
        """Should handle hyphenated words."""
        score = score_name_quality("E-commerce Order Updates")
        assert 0.0 <= score.total_score <= 1.0


# -----------------------------------------------------------------------------
# Integration Tests
# -----------------------------------------------------------------------------

class TestNameGeneratorIntegration:
    """Integration tests for name generator with quality scoring."""

    def test_generated_names_have_quality_scores(self):
        """Names from generator should be scoreable."""
        generator = TfidfNameGenerator()

        cluster_texts = [
            "Your Amazon order has shipped",
            "Amazon delivery confirmation",
            "Amazon order tracking update",
        ]
        corpus_texts = ["Meeting notes", "Hello world"]

        name, confidence = generator.generate_name(cluster_texts, corpus_texts)
        quality_score = score_name_quality(name)

        # Generated name should be valid and scoreable
        assert quality_score.total_score > 0.0
        assert name != "Miscellaneous" or confidence == 0.0

    def test_generator_produces_quality_names(self):
        """Generator should produce names with reasonable quality."""
        generator = TfidfNameGenerator()

        # Test with clear, distinct cluster
        cluster_texts = [
            "Invoice #12345 - Payment Due",
            "Payment reminder for invoice",
            "Your invoice is ready for payment",
        ]
        corpus_texts = [
            "Hello, how are you?",
            "Meeting at 3pm",
            "Project update needed",
        ]

        name, confidence = generator.generate_name(cluster_texts, corpus_texts)
        quality_score = score_name_quality(name)

        # Should produce a decent quality name for clear clusters
        if confidence > 0.5:
            assert quality_score.total_score > 0.4, f"Name '{name}' has low quality {quality_score.total_score}"
