"""
LLM-based email classifier using Instructor for structured output.

Phase 2, Work Item 2.2: Implements LLMClassifier(BaseClassifier) that uses
Instructor to get structured Pydantic responses from LLMs. Supports Ollama
(via OpenAI-compatible endpoint), OpenAI (native), and Claude (via Anthropic SDK)
through Instructor's unified patching.

The classifier:
1. Sanitizes email content to defend against prompt injection
2. Constructs a prompt with system instructions, category definitions,
   optional few-shot examples, and the sanitized email
3. Calls the LLM via Instructor's structured output to get a Pydantic response
4. Maps the response to a ClassificationResult

Design decisions:
- Lazy client initialization: The Instructor client is created on first use,
  not at __init__, so the classifier can be instantiated without network access.
- Provider abstraction via _build_client(): A single factory method creates the
  appropriate Instructor client for the configured provider.
- Prompt injection defense: All email content is sanitized and XML-delimited
  before inclusion in prompts.
- Graceful degradation: If the LLM returns an unknown category, the result
  is returned with lowered confidence rather than raising an error.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import instructor
import openai
from pydantic import BaseModel, Field

from src.classifiers.base import (
    BaseClassifier,
    ClassificationContext,
    ClassificationResult,
    ClassifierCapability,
)
from src.classifiers.sanitizer import EmailSanitizer
from src.config.models import ClassifierConfig
from src.exceptions import ClassifierConnectionError, ClassifierResponseError
from src.models.email import Email

logger = logging.getLogger(__name__)

# Optional anthropic import — only needed for Claude provider
try:
    import anthropic
except ImportError:
    anthropic = None  # type: ignore[assignment]


# =============================================================================
# LLM Response Model
# =============================================================================


class LLMClassificationResponse(BaseModel):
    """
    Pydantic model for the structured LLM classification response.

    Used with Instructor to constrain the LLM's output to a valid
    classification result with category, confidence, and reasoning.
    """

    category: str = Field(
        ...,
        min_length=1,
        description="The category name this email belongs to. Must be one of the provided categories.",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score for this classification (0.0 = no confidence, 1.0 = certain)",
    )
    reasoning: str = Field(
        ...,
        min_length=1,
        description="Brief explanation of why this category was chosen",
    )


# =============================================================================
# LLMClassifier
# =============================================================================


class LLMClassifier(BaseClassifier):
    """
    Email classifier that uses an LLM via Instructor for structured output.

    Supports four providers:
    - **ollama**: Local LLM via OpenAI-compatible API (default, zero cost)
    - **openai**: OpenAI API (GPT-4o-mini, etc.)
    - **claude**: Anthropic API (Claude Sonnet, etc.)
    - **runpod**: RunPod serverless via OpenAI-compatible API

    The classifier constructs a prompt with:
    1. System instruction defining the classification task
    2. Category definitions with descriptions
    3. Optional few-shot examples from ClassificationContext
    4. Sanitized email content wrapped in XML delimiters

    Usage::

        from src.config.models import ClassifierConfig, CategoryDefinition
        from src.classifiers.llm_classifier import LLMClassifier

        config = ClassifierConfig(
            provider="ollama",
            model_name="qwen2.5:7b",
            categories=[
                CategoryDefinition(name="Newsletters", description="..."),
                CategoryDefinition(name="Promotions", description="..."),
            ],
        )
        classifier = LLMClassifier(config)
        result = classifier.classify(email, ["Newsletters", "Promotions"])
    """

    def __init__(
        self,
        config: ClassifierConfig,
        few_shot_retriever: Any | None = None,
    ) -> None:
        """
        Initialize the LLM classifier.

        The Instructor client is NOT created here — it is lazily initialized
        on the first call to classify() via _get_client().

        Args:
            config: Classifier configuration with provider, model, and categories.
            few_shot_retriever: Optional FewShotRetriever for dynamic few-shot
                example injection. When provided, classify() will call
                retriever.retrieve(email) to get relevant examples from the
                feedback store and inject them into the classification context.
                When None, the classifier operates in zero-shot mode (or uses
                examples from the explicitly passed ClassificationContext).
        """
        self._config = config
        self._sanitizer = EmailSanitizer()
        self._client: Any = None
        self._few_shot_retriever = few_shot_retriever

    # -------------------------------------------------------------------------
    # BaseClassifier contract
    # -------------------------------------------------------------------------

    @property
    def name(self) -> str:
        """Human-readable classifier name for logging."""
        return f"LLM Classifier ({self._config.provider}/{self._config.model_name})"

    @property
    def capabilities(self) -> set[ClassifierCapability]:
        """LLM classifiers support zero-shot and few-shot classification."""
        return {ClassifierCapability.ZERO_SHOT, ClassifierCapability.FEW_SHOT}

    def classify(
        self,
        email: Email,
        categories: list[str],
        context: ClassificationContext | None = None,
    ) -> ClassificationResult:
        """
        Classify a single email into one of the provided categories.

        Constructs a prompt, calls the LLM via Instructor, and maps the
        structured response to a ClassificationResult.

        Args:
            email: The email to classify.
            categories: List of category names to choose from.
            context: Optional classification context with few-shot examples
                     and category descriptions.

        Returns:
            ClassificationResult with category assignment, confidence, and source.

        Raises:
            ValueError: If categories list is empty.
            ClassifierConnectionError: If the LLM service is unreachable.
            ClassifierResponseError: If the LLM response cannot be parsed.
        """
        if not categories:
            raise ValueError("categories list must not be empty")

        # Inject few-shot examples from retriever if available
        context = self._enrich_context_with_retriever(email, context)

        # Lazy client initialization
        client = self._get_client()

        # Build the prompt
        system_prompt, user_prompt = self._build_prompt(email, categories, context=context)

        # Call the LLM via Instructor
        try:
            response: LLMClassificationResponse = client.chat.completions.create(
                model=self._config.model_name,
                response_model=LLMClassificationResponse,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=self._config.temperature,
                max_tokens=self._config.max_tokens,
            )
        except (ConnectionError, TimeoutError, OSError) as e:
            raise ClassifierConnectionError(
                provider=self._config.provider,
                url=self._get_service_url(),
                context={"error": str(e), "email_id": email.id},
            ) from e
        except Exception as e:
            # Check if this is a connection-like error from httpx/requests
            error_str = str(e).lower()
            if any(
                keyword in error_str
                for keyword in ("connection", "timeout", "refused", "unreachable")
            ):
                raise ClassifierConnectionError(
                    provider=self._config.provider,
                    url=self._get_service_url(),
                    context={"error": str(e), "email_id": email.id},
                ) from e
            raise ClassifierResponseError(
                message=f"LLM classification failed: {e}",
                raw_response=str(e),
                context={"email_id": email.id, "provider": self._config.provider},
            ) from e

        # Map response to ClassificationResult
        return self._map_response(response, categories)

    def batch_classify(
        self,
        emails: list[Email],
        categories: list[str],
        context: ClassificationContext | None = None,
    ) -> list[ClassificationResult]:
        """
        Classify a batch of emails with progress logging.

        Overrides the base implementation to add progress tracking via tqdm.

        Args:
            emails: List of emails to classify.
            categories: List of category names to choose from.
            context: Optional classification context.

        Returns:
            List of ClassificationResult, one per email.
        """
        if not emails:
            return []

        results: list[ClassificationResult] = []
        total = len(emails)

        for i, email in enumerate(emails):
            logger.info(
                "%s: classifying email %d/%d (id=%s)",
                self.name,
                i + 1,
                total,
                email.id,
            )
            result = self.classify(email, categories, context=context)
            results.append(result)

        logger.info("%s: batch classification complete (%d emails)", self.name, total)
        return results

    # -------------------------------------------------------------------------
    # Few-Shot Retriever Integration
    # -------------------------------------------------------------------------

    def _enrich_context_with_retriever(
        self,
        email: Email,
        context: ClassificationContext | None,
    ) -> ClassificationContext | None:
        """
        Enrich the classification context with few-shot examples from the retriever.

        If no retriever is configured, returns the context unchanged.
        If the retriever raises an error, logs the error and returns the
        original context (graceful degradation to zero-shot).

        Args:
            email: The email being classified (passed to retriever for similarity search).
            context: Existing classification context (may be None).

        Returns:
            The (possibly enriched) classification context, or None if no
            retriever and no context were provided.
        """
        if self._few_shot_retriever is None:
            return context

        try:
            examples = self._few_shot_retriever.retrieve(email)
        except Exception:
            logger.warning(
                "Few-shot retriever failed for email %s; falling back to zero-shot",
                email.id,
                exc_info=True,
            )
            return context

        if not examples:
            return context

        # Create or augment context with retrieved examples
        if context is None:
            context = ClassificationContext(few_shot_examples=examples)
        else:
            # Merge: retriever examples come first, then any existing examples
            merged = list(examples) + list(context.few_shot_examples)
            context = ClassificationContext(
                few_shot_examples=merged,
                category_descriptions=context.category_descriptions,
                additional_context=context.additional_context,
            )

        return context

    # -------------------------------------------------------------------------
    # Client Factory
    # -------------------------------------------------------------------------

    def _get_client(self) -> Any:
        """
        Get or create the Instructor client (lazy initialization).

        Returns:
            Instructor-patched client ready for structured output calls.
        """
        if self._client is None:
            self._client = self._build_client()
        return self._client

    def _build_client(self) -> Any:
        """
        Build the appropriate Instructor client based on provider config.

        Returns:
            Instructor-patched client.

        Raises:
            ClassifierConnectionError: If API key is missing or SDK not installed.
        """
        provider = self._config.provider

        if provider == "ollama":
            return self._build_ollama_client()
        if provider == "openai":
            return self._build_openai_client()
        if provider == "claude":
            return self._build_claude_client()
        if provider == "runpod":
            return self._build_runpod_client()

        raise ClassifierConnectionError(
            provider=provider,
            url="N/A",
            recovery_hint=f"Unknown provider '{provider}'. Use: ollama, openai, claude, or runpod.",
        )

    def _build_ollama_client(self) -> Any:
        """Build an Instructor client for Ollama (OpenAI-compatible endpoint)."""
        base_url = f"{self._config.ollama_base_url}/v1"
        logger.info("Creating Ollama Instructor client at %s", base_url)

        oai_client = openai.OpenAI(
            base_url=base_url,
            api_key="ollama",  # Ollama doesn't require a real key
        )
        return instructor.from_openai(oai_client)

    def _build_openai_client(self) -> Any:
        """Build an Instructor client for OpenAI."""
        api_key = self._resolve_api_key()
        logger.info("Creating OpenAI Instructor client")

        oai_client = openai.OpenAI(api_key=api_key)
        return instructor.from_openai(oai_client)

    def _build_claude_client(self) -> Any:
        """Build an Instructor client for Anthropic Claude."""
        if anthropic is None:
            raise ClassifierConnectionError(
                provider="claude",
                url="N/A",
                recovery_hint=(
                    "The anthropic SDK is not installed. "
                    "Install it with: pip install 'email-corpus-analyzer[cloud]' "
                    "or pip install anthropic"
                ),
            )

        api_key = self._resolve_api_key()
        logger.info("Creating Claude Instructor client")

        anthro_client = anthropic.Anthropic(api_key=api_key)
        return instructor.from_anthropic(anthro_client)

    def _build_runpod_client(self) -> Any:
        """Build an Instructor client for RunPod serverless (OpenAI-compatible endpoint)."""
        endpoint_id = self._config.runpod_endpoint_id
        if not endpoint_id:
            raise ClassifierConnectionError(
                provider="runpod",
                url="N/A",
                recovery_hint=(
                    "No runpod_endpoint_id configured. Set classifier.runpod_endpoint_id "
                    "in your config or pass --endpoint-id on the CLI."
                ),
            )

        base_url = f"https://api.runpod.ai/v2/{endpoint_id}/openai/v1"
        api_key = self._resolve_api_key()
        logger.info("Creating RunPod Instructor client at %s", base_url)

        oai_client = openai.OpenAI(base_url=base_url, api_key=api_key)
        return instructor.from_openai(oai_client)

    def _resolve_api_key(self) -> str:
        """
        Resolve the API key from the configured environment variable.

        Returns:
            The API key string.

        Raises:
            ClassifierConnectionError: If the env var is not set or empty.
        """
        env_var = self._config.api_key_env_var
        if not env_var:
            raise ClassifierConnectionError(
                provider=self._config.provider,
                url="N/A",
                recovery_hint=(
                    f"No api_key_env_var configured for {self._config.provider}. "
                    "Set classifier.api_key_env_var in your config to the name of the "
                    "environment variable containing your API key."
                ),
            )

        api_key = os.environ.get(env_var)
        if not api_key:
            raise ClassifierConnectionError(
                provider=self._config.provider,
                url="N/A",
                recovery_hint=(
                    f"Environment variable '{env_var}' is not set or is empty. "
                    f"Set it to your {self._config.provider} API key before running."
                ),
                context={"env_var": env_var},
            )

        return api_key

    def _get_service_url(self) -> str:
        """Get the service URL for error reporting."""
        if self._config.provider == "ollama":
            return f"{self._config.ollama_base_url}/v1"
        if self._config.provider == "openai":
            return "https://api.openai.com/v1"
        if self._config.provider == "claude":
            return "https://api.anthropic.com"
        if self._config.provider == "runpod":
            eid = self._config.runpod_endpoint_id or "<no-endpoint-id>"
            return f"https://api.runpod.ai/v2/{eid}/openai/v1"
        return "unknown"

    # -------------------------------------------------------------------------
    # Prompt Construction
    # -------------------------------------------------------------------------

    def _build_prompt(
        self,
        email: Email,
        categories: list[str],
        context: ClassificationContext | None = None,
    ) -> tuple[str, str]:
        """
        Build the system and user prompts for LLM classification.

        Args:
            email: The email to classify.
            categories: List of category names.
            context: Optional classification context.

        Returns:
            Tuple of (system_prompt, user_prompt).
        """
        # --- System prompt ---
        system_parts: list[str] = [
            "You are an expert email classifier. Your job is to classify emails "
            "into exactly one of the provided categories.",
            "",
            "Rules:",
            "- Choose the single best-matching category from the list below.",
            "- Assign a confidence score from 0.0 (no confidence) to 1.0 (certain).",
            "- Provide a brief reasoning for your choice.",
            "- Base your decision on the email's subject, body, and sender information.",
            "",
        ]

        # Add category definitions
        system_parts.append("Categories:")
        descriptions = self._get_category_descriptions(categories, context)
        for cat_name in categories:
            desc = descriptions.get(cat_name, "")
            if desc:
                system_parts.append(f"- {cat_name}: {desc}")
            else:
                system_parts.append(f"- {cat_name}")
        system_parts.append("")

        # Add few-shot examples if available
        if context and context.few_shot_examples:
            system_parts.append("Examples:")
            for example in context.few_shot_examples:
                subj = example.get("email_subject", "N/A")
                cat = example.get("category", "N/A")
                system_parts.append(f'- Email subject: "{subj}" -> Category: {cat}')
            system_parts.append("")

        system_prompt = "\n".join(system_parts)

        # --- User prompt ---
        # Sanitize and wrap email content
        email_content = self._sanitizer.wrap_for_prompt(email.subject, email.body_text)

        user_parts: list[str] = [
            "Classify the following email:",
            "",
            f"From: {email.sender_email} ({email.sender_domain})",
            email_content,
        ]

        user_prompt = "\n".join(user_parts)

        return system_prompt, user_prompt

    def _get_category_descriptions(
        self,
        categories: list[str],
        context: ClassificationContext | None = None,
    ) -> dict[str, str]:
        """
        Get category descriptions from context or config.

        Priority: context.category_descriptions > config.categories descriptions

        Args:
            categories: List of category names to look up.
            context: Optional classification context with descriptions.

        Returns:
            Dict mapping category name to description.
        """
        descriptions: dict[str, str] = {}

        # First, populate from config categories
        config_cat_map = {cat.name: cat.description for cat in self._config.categories}
        for cat_name in categories:
            if cat_name in config_cat_map:
                descriptions[cat_name] = config_cat_map[cat_name]

        # Then, override with context descriptions if provided
        if context and context.category_descriptions:
            for cat_name in categories:
                if cat_name in context.category_descriptions:
                    descriptions[cat_name] = context.category_descriptions[cat_name]

        return descriptions

    # -------------------------------------------------------------------------
    # Response Mapping
    # -------------------------------------------------------------------------

    def _map_response(
        self,
        response: LLMClassificationResponse,
        categories: list[str],
    ) -> ClassificationResult:
        """
        Map an LLMClassificationResponse to a ClassificationResult.

        If the LLM returns a category not in the provided list, the result
        is returned with reduced confidence and a note in the reasoning.

        Args:
            response: The structured LLM response.
            categories: The list of valid categories.

        Returns:
            ClassificationResult.
        """
        source = f"llm:{self._config.provider}"
        category_name = response.category
        confidence = response.confidence
        reasoning = response.reasoning

        # Check if the returned category is valid
        if category_name not in categories:
            logger.warning(
                "%s: LLM returned unknown category '%s' (valid: %s). "
                "Keeping result with reduced confidence.",
                self.name,
                category_name,
                categories,
            )
            # Reduce confidence since the category doesn't match
            confidence = min(confidence, 0.3)
            reasoning = f"[LLM returned non-standard category '{category_name}'] {reasoning}"

        return ClassificationResult(
            category_name=category_name,
            confidence=confidence,
            source=source,
            reasoning=reasoning,
        )


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "LLMClassificationResponse",
    "LLMClassifier",
]
