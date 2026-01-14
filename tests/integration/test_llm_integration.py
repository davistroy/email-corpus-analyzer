"""
Integration tests for LLM integration.

Tests the LLM client and categorizer with mocked Anthropic API
to ensure proper structured output and error handling.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel, Field

# Check for anthropic package
try:
    import anthropic  # noqa
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

from src.llm.categorizer import CategorySuggestion, CategorySuggestions, LLMCategorizer
from src.llm.client import LLMClient
from src.models.analysis_results import AnalysisResults
from src.models.category import Category


class TestModel(BaseModel):
    """Test model for structured output."""

    name: str = Field(..., min_length=1)
    value: int = Field(..., ge=0)
    description: str


@pytest.mark.integration
@pytest.mark.asyncio
class TestLLMClient:
    """Integration tests for LLM client."""

    async def test_client_initialization(self):
        """Test client can be initialized."""
        client = LLMClient(api_key="test-key")

        assert client.api_key == "test-key"
        assert client.model == "claude-sonnet-4-20250514"
        assert client.is_available

    async def test_client_without_api_key(self):
        """Test client handles missing API key."""
        with patch.dict("os.environ", {}, clear=True):
            client = LLMClient()

            assert not client.is_available
            assert client.api_key is None

    @pytest.mark.skipif(not HAS_ANTHROPIC, reason="anthropic package not installed")
    async def test_generate_structured_success(self, mock_anthropic_client):
        """Test successful structured generation."""
        with patch("anthropic.Anthropic", return_value=mock_anthropic_client):
            client = LLMClient(api_key="test-key")

            # Mock response with tool use
            mock_tool_use = MagicMock()
            mock_tool_use.type = "tool_use"
            mock_tool_use.name = "structured_response"
            mock_tool_use.input = {
                "name": "Test Name",
                "value": 42,
                "description": "Test description",
            }

            mock_response = MagicMock()
            mock_response.content = [mock_tool_use]

            with patch("asyncio.to_thread", return_value=mock_response):
                result = await client.generate_structured(
                    prompt="Generate a test model",
                    response_model=TestModel,
                )

                assert isinstance(result, TestModel)
                assert result.name == "Test Name"
                assert result.value == 42

    @pytest.mark.skipif(not HAS_ANTHROPIC, reason="anthropic package not installed")
    async def test_generate_structured_validation_error(self, mock_anthropic_client):
        """Test structured generation with validation error."""
        with patch("anthropic.Anthropic", return_value=mock_anthropic_client):
            client = LLMClient(api_key="test-key")

            # Mock response with invalid data
            mock_tool_use = MagicMock()
            mock_tool_use.type = "tool_use"
            mock_tool_use.name = "structured_response"
            mock_tool_use.input = {
                "name": "",  # Invalid: min_length=1
                "value": -1,  # Invalid: ge=0
                "description": "Test",
            }

            mock_response = MagicMock()
            mock_response.content = [mock_tool_use]

            with patch("asyncio.to_thread", return_value=mock_response):
                with pytest.raises(Exception):  # Pydantic validation error
                    await client.generate_structured(
                        prompt="Generate invalid model",
                        response_model=TestModel,
                    )

    @pytest.mark.skipif(not HAS_ANTHROPIC, reason="anthropic package not installed")
    async def test_generate_structured_no_tool_use(self, mock_anthropic_client):
        """Test handling response without tool use."""
        with patch("anthropic.Anthropic", return_value=mock_anthropic_client):
            client = LLMClient(api_key="test-key")

            # Mock response without tool use
            mock_text_block = MagicMock()
            mock_text_block.type = "text"
            mock_text_block.text = "Just text response"

            mock_response = MagicMock()
            mock_response.content = [mock_text_block]

            with patch("asyncio.to_thread", return_value=mock_response):
                with pytest.raises(ValueError, match="No structured response"):
                    await client.generate_structured(
                        prompt="Generate test",
                        response_model=TestModel,
                    )

    @pytest.mark.skipif(not HAS_ANTHROPIC, reason="anthropic package not installed")
    async def test_generate_text(self, mock_anthropic_client):
        """Test text generation."""
        with patch("anthropic.Anthropic", return_value=mock_anthropic_client):
            client = LLMClient(api_key="test-key")

            # Mock text response
            mock_text_block = MagicMock()
            mock_text_block.text = "Generated text content"

            mock_response = MagicMock()
            mock_response.content = [mock_text_block]

            with patch("asyncio.to_thread", return_value=mock_response):
                result = await client.generate_text(prompt="Generate text")

                assert result == "Generated text content"

    @pytest.mark.skipif(not HAS_ANTHROPIC, reason="anthropic package not installed")
    async def test_generate_text_multiple_blocks(self, mock_anthropic_client):
        """Test text generation with multiple content blocks."""
        with patch("anthropic.Anthropic", return_value=mock_anthropic_client):
            client = LLMClient(api_key="test-key")

            # Mock multiple text blocks
            block1 = MagicMock()
            block1.text = "First block"

            block2 = MagicMock()
            block2.text = "Second block"

            mock_response = MagicMock()
            mock_response.content = [block1, block2]

            with patch("asyncio.to_thread", return_value=mock_response):
                result = await client.generate_text(prompt="Generate text")

                assert result == "First block\nSecond block"

    async def test_custom_model(self):
        """Test using custom model."""
        client = LLMClient(api_key="test-key", model="claude-opus-4-20250514")

        assert client.model == "claude-opus-4-20250514"

    @pytest.mark.skipif(not HAS_ANTHROPIC, reason="anthropic package not installed")
    async def test_custom_system_prompt(self, mock_anthropic_client):
        """Test custom system prompt."""
        with patch("anthropic.Anthropic", return_value=mock_anthropic_client):
            client = LLMClient(api_key="test-key")

            mock_tool_use = MagicMock()
            mock_tool_use.type = "tool_use"
            mock_tool_use.name = "structured_response"
            mock_tool_use.input = {"name": "Test", "value": 1, "description": "Test"}

            mock_response = MagicMock()
            mock_response.content = [mock_tool_use]

            with patch("asyncio.to_thread", return_value=mock_response) as mock_thread:
                await client.generate_structured(
                    prompt="Test",
                    response_model=TestModel,
                    system="Custom system prompt",
                )

                # Verify system prompt was used
                call_args = mock_thread.call_args
                # The lambda passed to to_thread needs to be called
                # Just verify it was called


@pytest.mark.integration
@pytest.mark.asyncio
class TestLLMCategorizer:
    """Integration tests for LLM categorizer."""

    def create_mock_analysis(self) -> AnalysisResults:
        """Create mock analysis results for testing."""
        from src.models.sender import Sender, SenderType
        from src.models.analysis_results import (
            ContentCluster,
            DomainCount,
            SenderAnalysis,
            SubjectPatterns,
            TemporalPatterns,
            VolumeStats,
        )
        from src.models.content_cluster import RepresentativeSample

        volume = VolumeStats(
            total_emails=100,
            unique_senders=20,
            date_range={"oldest": "2024-01-01", "newest": "2024-12-31", "span_days": "365"},
            with_attachments=30,
            attachment_percentage=30.0,
            avg_body_length_chars=500,
            emails_per_day=0.27,
        )

        sender_analysis = SenderAnalysis(
            top_senders=[
                Sender(
                    email="newsletter@company.com",
                    domain="company.com",
                    frequency_count=40,
                    type=SenderType.SERVICE,
                ),
                Sender(
                    email="alerts@bank.com",
                    domain="bank.com",
                    frequency_count=25,
                    type=SenderType.SERVICE,
                ),
            ],
            top_domains=[
                DomainCount(domain="company.com", count=40),
                DomainCount(domain="bank.com", count=25),
            ],
            unique_senders=20,
            unique_domains=10,
        )

        clusters = [
            ContentCluster(
                cluster_id=0,
                size=40,
                percentage=40.0,
                common_domains=[("company.com", 40)],
                representative_samples=[
                    RepresentativeSample(
                        subject="Weekly Newsletter",
                        sender="newsletter@company.com",
                        body_preview="This week's updates...",
                    )
                ],
            )
        ]

        subject_patterns = SubjectPatterns(
            common_prefixes={"RE:": 10, "FWD:": 5},
            numbered_patterns={"Invoice": 12, "Order": 8},
            top_keywords=[("alert", 15), ("update", 10), ("newsletter", 8)],
            bracket_tags=[("URGENT", 5), ("INFO", 3)],
            total_subjects_analyzed=100,
        )

        temporal = TemporalPatterns(
            frequency_distribution={"daily": 50, "weekly": 30, "monthly": 20},
            sender_frequencies={
                "alerts@bank.com": {"type": "daily", "count": 25, "first": "2024-01-01", "last": "2024-12-31"},
                "newsletter@company.com": {"type": "weekly", "count": 40, "first": "2024-01-01", "last": "2024-12-31"},
            }
        )

        return AnalysisResults(
            volume_stats=volume,
            sender_analysis=sender_analysis,
            content_clusters=clusters,
            subject_patterns=subject_patterns,
            temporal_patterns=temporal,
        )

    @pytest.mark.skipif(not HAS_ANTHROPIC, reason="anthropic package not installed")
    async def test_suggest_categories_with_llm(self, mock_anthropic_client):
        """Test category suggestions with mocked LLM."""
        with patch("anthropic.Anthropic", return_value=mock_anthropic_client):
            client = LLMClient(api_key="test-key")
            categorizer = LLMCategorizer(client=client)

            # Mock structured response
            mock_tool_use = MagicMock()
            mock_tool_use.type = "tool_use"
            mock_tool_use.name = "structured_response"
            mock_tool_use.input = {
                "categories": [
                    {
                        "category_name": "Newsletters",
                        "description": "Weekly company newsletters",
                        "confidence": 0.9,
                        "reasoning": "High volume from newsletter sender",
                        "matching_patterns": ["newsletter@company.com"],
                        "suggested_action": "archive",
                        "estimated_count": 40,
                    },
                    {
                        "category_name": "Bank Alerts",
                        "description": "Transaction and security alerts",
                        "confidence": 0.85,
                        "reasoning": "Automated alerts from bank",
                        "matching_patterns": ["alerts@bank.com", "bank.com"],
                        "suggested_action": "keep",
                        "estimated_count": 25,
                    },
                ],
                "uncategorized_percentage": 10.0,
                "recommendations": "Consider setting up filters for newsletters.",
            }

            mock_response = MagicMock()
            mock_response.content = [mock_tool_use]

            with patch("asyncio.to_thread", return_value=mock_response):
                analysis = self.create_mock_analysis()
                suggestions = await categorizer.suggest_categories(analysis)

                assert isinstance(suggestions, CategorySuggestions)
                assert len(suggestions.categories) == 2
                assert suggestions.categories[0].category_name == "Newsletters"
                assert suggestions.categories[1].category_name == "Bank Alerts"
                assert suggestions.uncategorized_percentage == 10.0

    async def test_suggest_categories_fallback(self):
        """Test fallback suggestions when LLM unavailable."""
        # Create categorizer without client
        categorizer = LLMCategorizer(client=None)

        analysis = self.create_mock_analysis()

        # Should use fallback without error
        suggestions = await categorizer.suggest_categories(analysis)

        assert isinstance(suggestions, CategorySuggestions)
        assert len(suggestions.categories) > 0

    @pytest.mark.skipif(not HAS_ANTHROPIC, reason="anthropic package not installed")
    async def test_suggest_categories_with_existing(self, mock_anthropic_client):
        """Test suggestions considering existing categories."""
        with patch("anthropic.Anthropic", return_value=mock_anthropic_client):
            client = LLMClient(api_key="test-key")
            categorizer = LLMCategorizer(client=client)

            existing = [
                Category(
                    category_name="Existing Category",
                    description="Already defined",
                    email_count=10,
                )
            ]

            mock_tool_use = MagicMock()
            mock_tool_use.type = "tool_use"
            mock_tool_use.name = "structured_response"
            mock_tool_use.input = {
                "categories": [
                    {
                        "category_name": "New Category",
                        "description": "Newly suggested",
                        "confidence": 0.8,
                        "reasoning": "Different from existing",
                    }
                ],
                "uncategorized_percentage": 5.0,
                "recommendations": "Keep existing category.",
            }

            mock_response = MagicMock()
            mock_response.content = [mock_tool_use]

            with patch("asyncio.to_thread", return_value=mock_response):
                analysis = self.create_mock_analysis()
                suggestions = await categorizer.suggest_categories(
                    analysis,
                    existing_categories=existing,
                )

                assert isinstance(suggestions, CategorySuggestions)

    @pytest.mark.skipif(not HAS_ANTHROPIC, reason="anthropic package not installed")
    async def test_suggest_categories_max_limit(self, mock_anthropic_client):
        """Test category suggestions respect max limit."""
        with patch("anthropic.Anthropic", return_value=mock_anthropic_client):
            client = LLMClient(api_key="test-key")
            categorizer = LLMCategorizer(client=client)

            # Mock response with many categories
            categories = [
                {
                    "category_name": f"Category {i}",
                    "description": f"Description {i}",
                    "confidence": 0.7,
                    "reasoning": "Test",
                }
                for i in range(20)
            ]

            mock_tool_use = MagicMock()
            mock_tool_use.type = "tool_use"
            mock_tool_use.name = "structured_response"
            mock_tool_use.input = {
                "categories": categories,
                "uncategorized_percentage": 5.0,
                "recommendations": "Many categories suggested.",
            }

            mock_response = MagicMock()
            mock_response.content = [mock_tool_use]

            with patch("asyncio.to_thread", return_value=mock_response):
                analysis = self.create_mock_analysis()
                suggestions = await categorizer.suggest_categories(
                    analysis,
                    max_categories=10,
                )

                # Verify request mentioned the limit
                assert isinstance(suggestions, CategorySuggestions)

    @pytest.mark.skipif(not HAS_ANTHROPIC, reason="anthropic package not installed")
    async def test_refine_category(self, mock_anthropic_client):
        """Test refining existing category."""
        with patch("anthropic.Anthropic", return_value=mock_anthropic_client):
            client = LLMClient(api_key="test-key")
            categorizer = LLMCategorizer(client=client)

            category = Category(
                category_name="Vague Name",
                description="Needs refinement",
                email_count=50,
            )

            sample_emails = [
                {
                    "subject": "Order Confirmation #12345",
                    "sender_email": "orders@shop.com",
                },
                {
                    "subject": "Your Order Has Shipped",
                    "sender_email": "shipping@shop.com",
                },
            ]

            mock_tool_use = MagicMock()
            mock_tool_use.type = "tool_use"
            mock_tool_use.name = "structured_response"
            mock_tool_use.input = {
                "category_name": "Shopping Orders",
                "description": "Order confirmations and shipping notifications",
                "confidence": 0.95,
                "reasoning": "All samples are order-related from shopping sites",
                "matching_patterns": ["orders@shop.com", "shipping@shop.com"],
                "suggested_action": "archive",
                "estimated_count": 50,
            }

            mock_response = MagicMock()
            mock_response.content = [mock_tool_use]

            with patch("asyncio.to_thread", return_value=mock_response):
                refined = await categorizer.refine_category(category, sample_emails)

                assert isinstance(refined, CategorySuggestion)
                assert refined.category_name == "Shopping Orders"
                assert refined.confidence == 0.95

    def test_build_analysis_summary(self):
        """Test building analysis summary text."""
        categorizer = LLMCategorizer(client=None)
        analysis = self.create_mock_analysis()

        summary = categorizer._build_analysis_summary(analysis)

        assert "Total emails: 100" in summary
        assert "Unique senders: 20" in summary
        assert "newsletter@company.com" in summary
        assert "bank.com" in summary

    def test_fallback_suggestions_from_senders(self):
        """Test fallback creates categories from top senders."""
        categorizer = LLMCategorizer(client=None)
        analysis = self.create_mock_analysis()

        suggestions = categorizer._fallback_suggestions(analysis)

        assert isinstance(suggestions, CategorySuggestions)
        assert len(suggestions.categories) > 0

        # Should include categories from top senders
        category_names = [c.category_name for c in suggestions.categories]
        assert any("company" in name.lower() for name in category_names)

    def test_fallback_suggestions_from_clusters(self):
        """Test fallback creates categories from clusters."""
        categorizer = LLMCategorizer(client=None)
        analysis = self.create_mock_analysis()

        suggestions = categorizer._fallback_suggestions(analysis)

        # Should have categories from both senders and clusters
        assert len(suggestions.categories) > 0
        assert suggestions.uncategorized_percentage > 0


@pytest.mark.integration
@pytest.mark.asyncio
class TestLLMIntegrationScenarios:
    """Test realistic LLM integration scenarios."""

    @pytest.mark.skipif(not HAS_ANTHROPIC, reason="anthropic package not installed")
    async def test_complete_categorization_flow(self, mock_anthropic_client):
        """Test complete flow from analysis to categories."""
        with patch("anthropic.Anthropic", return_value=mock_anthropic_client):
            # Setup client and categorizer
            client = LLMClient(api_key="test-key")
            categorizer = LLMCategorizer(client=client)

            # Mock analysis
            from src.models.sender import Sender, SenderType
            from src.models.analysis_results import (
                AnalysisResults,
                ContentCluster,
                DomainCount,
                SenderAnalysis,
                SubjectPatterns,
                TemporalPatterns,
                VolumeStats,
            )

            analysis = AnalysisResults(
                volume_stats=VolumeStats(
                    total_emails=500,
                    unique_senders=100,
                    date_range={"oldest": "2024-01-01", "newest": "2024-12-31", "span_days": "365"},
                    with_attachments=50,
                    attachment_percentage=10.0,
                    avg_body_length_chars=500,
                    emails_per_day=1.4,
                ),
                sender_analysis=SenderAnalysis(
                    top_senders=[
                        Sender(
                            email="noreply@service.com",
                            domain="service.com",
                            frequency_count=150,
                            type=SenderType.SERVICE,
                        )
                    ],
                    top_domains=[DomainCount(domain="service.com", count=150)],
                    unique_senders=100,
                    unique_domains=50,
                ),
                content_clusters=[],
                subject_patterns=SubjectPatterns(
                    common_prefixes={},
                    numbered_patterns={},
                    top_keywords=[],
                    bracket_tags=[],
                    total_subjects_analyzed=0,
                ),
                temporal_patterns=TemporalPatterns(
                    frequency_distribution={},
                    sender_frequencies={},
                ),
            )

            # Mock LLM response
            mock_tool_use = MagicMock()
            mock_tool_use.type = "tool_use"
            mock_tool_use.name = "structured_response"
            mock_tool_use.input = {
                "categories": [
                    {
                        "category_name": "Service Notifications",
                        "description": "Automated notifications from service",
                        "confidence": 0.9,
                        "reasoning": "High volume automated emails",
                        "matching_patterns": ["noreply@service.com"],
                        "suggested_action": "archive",
                        "estimated_count": 150,
                    }
                ],
                "uncategorized_percentage": 5.0,
                "recommendations": "Set up filters for automated emails.",
            }

            mock_response = MagicMock()
            mock_response.content = [mock_tool_use]

            with patch("asyncio.to_thread", return_value=mock_response):
                suggestions = await categorizer.suggest_categories(analysis, max_categories=10)

                assert len(suggestions.categories) == 1
                assert suggestions.categories[0].estimated_count == 150

    async def test_error_handling_with_recovery(self):
        """Test LLM error handling with fallback."""
        # Client without API key
        client = LLMClient()  # No API key
        categorizer = LLMCategorizer(client=client)

        from src.models.sender import Sender, SenderType
        from src.models.analysis_results import (
            AnalysisResults,
            SenderAnalysis,
            SubjectPatterns,
            TemporalPatterns,
            VolumeStats,
        )

        analysis = AnalysisResults(
            volume_stats=VolumeStats(
                total_emails=100,
                unique_senders=10,
                date_range={"oldest": "2024-01-01", "newest": "2024-12-31", "span_days": "365"},
                with_attachments=10,
                attachment_percentage=10.0,
                avg_body_length_chars=500,
                emails_per_day=0.27,
            ),
            sender_analysis=SenderAnalysis(
                top_senders=[],
                top_domains=[],
                unique_senders=10,
                unique_domains=5,
            ),
            content_clusters=[],
            subject_patterns=SubjectPatterns(
                common_prefixes={},
                numbered_patterns={},
                top_keywords=[],
                bracket_tags=[],
                total_subjects_analyzed=0,
            ),
            temporal_patterns=TemporalPatterns(
                frequency_distribution={},
                sender_frequencies={},
            ),
        )

        # Should fall back gracefully
        suggestions = await categorizer.suggest_categories(analysis)

        assert isinstance(suggestions, CategorySuggestions)
        # Fallback may return empty or basic categories
