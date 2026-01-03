"""
Anthropic API client wrapper with structured output support.

Provides a simple interface for using Claude with Pydantic models
for structured responses.
"""
import asyncio
import os
from typing import TypeVar

from pydantic import BaseModel

from src.utils.logger import get_logger

logger = get_logger(__name__)

T = TypeVar("T", bound=BaseModel)


class LLMClient:
    """
    Wrapper for Anthropic API with structured output support.

    Uses tool use to get structured JSON responses that
    can be parsed into Pydantic models.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "claude-sonnet-4-20250514",
    ):
        """
        Initialize LLM client.

        Args:
            api_key: Anthropic API key. Uses ANTHROPIC_API_KEY env var if not provided.
            model: Model to use for completions.
        """
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.model = model
        self._client = None

    def _get_client(self):
        """Lazy-load the Anthropic client."""
        if self._client is None:
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=self.api_key)
            except ImportError:
                raise ImportError(
                    "anthropic package not installed. Run: pip install anthropic"
                )
        return self._client

    async def generate_structured(
        self,
        prompt: str,
        response_model: type[T],
        system: str | None = None,
        max_tokens: int = 4096,
    ) -> T:
        """
        Generate a structured response using tool use.

        Args:
            prompt: User prompt.
            response_model: Pydantic model class for the response.
            system: Optional system prompt.
            max_tokens: Maximum tokens in response.

        Returns:
            Parsed response as the specified Pydantic model.

        Raises:
            ValueError: If no structured response generated.
        """
        client = self._get_client()

        # Create tool definition from Pydantic schema
        tool_schema = response_model.model_json_schema()

        # Remove unsupported fields from schema
        if "title" in tool_schema:
            del tool_schema["title"]

        tool = {
            "name": "structured_response",
            "description": f"Return a structured {response_model.__name__} response",
            "input_schema": tool_schema,
        }

        try:
            # Make API call
            response = await asyncio.to_thread(
                lambda: client.messages.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    system=system or "You are an expert email analyst. Provide accurate, structured analysis.",
                    messages=[{"role": "user", "content": prompt}],
                    tools=[tool],
                    tool_choice={"type": "tool", "name": "structured_response"},
                )
            )

            # Extract tool use result
            for block in response.content:
                if block.type == "tool_use" and block.name == "structured_response":
                    return response_model.model_validate(block.input)

            raise ValueError("No structured response generated")

        except Exception as e:
            logger.error(f"LLM structured generation failed: {e}")
            raise

    async def generate_text(
        self,
        prompt: str,
        system: str | None = None,
        max_tokens: int = 4096,
    ) -> str:
        """
        Generate a text response.

        Args:
            prompt: User prompt.
            system: Optional system prompt.
            max_tokens: Maximum tokens in response.

        Returns:
            Generated text.
        """
        client = self._get_client()

        try:
            response = await asyncio.to_thread(
                lambda: client.messages.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    system=system or "You are a helpful assistant.",
                    messages=[{"role": "user", "content": prompt}],
                )
            )

            # Extract text content
            text_parts = []
            for block in response.content:
                if hasattr(block, "text"):
                    text_parts.append(block.text)

            return "\n".join(text_parts)

        except Exception as e:
            logger.error(f"LLM text generation failed: {e}")
            raise

    @property
    def is_available(self) -> bool:
        """Check if LLM is available (API key configured)."""
        return bool(self.api_key)


# Global client instance for convenience
_default_client: LLMClient | None = None


def get_llm_client() -> LLMClient:
    """Get or create the default LLM client."""
    global _default_client
    if _default_client is None:
        _default_client = LLMClient()
    return _default_client
