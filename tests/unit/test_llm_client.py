"""
Tests for LLM client and structured output.
"""
import pytest
from pydantic import BaseModel, Field

from src.llm.client import LLMClient, get_llm_client
from src.llm.namer import ClusterName, ClusterNamer
from src.llm.categorizer import CategorySuggestion, CategorySuggestions


class TestLLMModels:
    """Test LLM-related Pydantic models."""

    def test_cluster_name_model(self):
        """Test ClusterName model validation."""
        name = ClusterName(
            name="Shopping Receipts",
            description="Online shopping order confirmations",
            confidence=0.85,
            reasoning="Contains order confirmations from multiple retailers",
            suggested_action="archive",
        )
        assert name.name == "Shopping Receipts"
        assert 0 <= name.confidence <= 1

    def test_cluster_name_validation(self):
        """Test ClusterName validation constraints."""
        # Name too short
        with pytest.raises(ValueError):
            ClusterName(
                name="X",  # min 2 chars
                description="Test",
                confidence=0.5,
                reasoning="Test",
            )

        # Confidence out of range
        with pytest.raises(ValueError):
            ClusterName(
                name="Valid Name",
                description="Test",
                confidence=1.5,  # max 1.0
                reasoning="Test",
            )

    def test_category_suggestion_model(self):
        """Test CategorySuggestion model."""
        suggestion = CategorySuggestion(
            category_name="Bank Alerts",
            description="Security and transaction alerts from banks",
            confidence=0.9,
            reasoning="High volume of bank notification emails",
            matching_patterns=["bank", "security", "alert"],
            suggested_action="keep",
            estimated_count=150,
        )
        assert suggestion.category_name == "Bank Alerts"
        assert len(suggestion.matching_patterns) == 3

    def test_category_suggestions_model(self):
        """Test CategorySuggestions collection model."""
        suggestions = CategorySuggestions(
            categories=[
                CategorySuggestion(
                    category_name="Test",
                    description="Test category",
                    confidence=0.8,
                    reasoning="Test",
                ),
            ],
            uncategorized_percentage=5.0,
            recommendations="Review weekly newsletters",
        )
        assert len(suggestions.categories) == 1
        assert suggestions.uncategorized_percentage == 5.0


class TestLLMClient:
    """Test LLM client functionality."""

    def test_client_initialization(self):
        """Test client initializes without API key."""
        client = LLMClient()
        assert client.model == "claude-sonnet-4-20250514"
        assert not client.is_available  # No API key set

    def test_client_with_api_key(self):
        """Test client with API key."""
        client = LLMClient(api_key="test-key")
        assert client.is_available

    def test_get_llm_client_singleton(self):
        """Test global client getter."""
        client1 = get_llm_client()
        client2 = get_llm_client()
        assert client1 is client2


class TestClusterNamer:
    """Test cluster naming functionality."""

    def test_fallback_name_with_domain(self):
        """Test fallback naming uses domain."""
        from src.models.content_cluster import RepresentativeSample

        namer = ClusterNamer(client=None)  # No client = fallback mode

        samples = [
            RepresentativeSample(
                subject="Your order has shipped",
                sender="orders@amazon.com",
                body_preview="Your package is on its way...",
            ),
        ]
        domains = [("amazon.com", 50), ("example.com", 10)]

        result = namer._fallback_name(samples, domains)
        assert "Amazon" in result.name
        assert result.confidence == 0.5  # Fallback confidence

    def test_fallback_name_without_domain(self):
        """Test fallback naming without domains."""
        from src.models.content_cluster import RepresentativeSample

        namer = ClusterNamer(client=None)

        samples = [
            RepresentativeSample(
                subject="Important meeting tomorrow",
                sender="unknown@example.com",
                body_preview="Please attend...",
            ),
        ]

        result = namer._fallback_name(samples, [])
        assert result.name  # Should have some name
        assert result.confidence < 0.5  # Lower confidence for no-domain fallback

    def test_fallback_name_empty(self):
        """Test fallback naming with no data."""
        namer = ClusterNamer(client=None)
        result = namer._fallback_name([], [])
        assert result.name == "Uncategorized"
        assert result.confidence == 0.2
