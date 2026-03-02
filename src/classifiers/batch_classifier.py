"""
Batch LLM classifier using the Anthropic Message Batches API.

Submits all classification requests in a single batch for 50% cost reduction
and massive parallelism. The Batch API processes up to 10,000 requests per
batch asynchronously, typically completing in minutes to hours.

Usage:
    from src.classifiers.batch_classifier import BatchClassifier
    from src.config.models import ClassifierConfig

    config = ClassifierConfig(provider="claude", model_name="claude-sonnet-4-6", ...)
    classifier = BatchClassifier(config)
    results = classifier.classify_batch(emails, category_names, category_descriptions)

Design decisions:
- Uses tool_use (function calling) for structured output, matching the same
  schema that Instructor generates for LLMClassificationResponse.
- Splits large email lists into 10,000-request batches (API limit).
- Polls for completion with exponential backoff.
- Returns results in the same order as input emails.
"""

from __future__ import annotations

import logging
import os
import time

import anthropic

from src.classifiers.sanitizer import EmailSanitizer
from src.config.models import ClassifierConfig
from src.exceptions import ClassifierConnectionError, ClassifierResponseError
from src.models.email import Email

logger = logging.getLogger(__name__)

# Maximum requests per batch (Anthropic API limit)
MAX_BATCH_SIZE = 1_000  # Keep well under 10K API limit to avoid HTTP payload timeouts

# Polling intervals
INITIAL_POLL_INTERVAL = 5  # seconds
MAX_POLL_INTERVAL = 60  # seconds
POLL_BACKOFF_FACTOR = 1.5

# Tool definition matching Instructor's schema for LLMClassificationResponse
CLASSIFICATION_TOOL = {
    "name": "classify_email",
    "description": (
        "Classify an email into a category. Returns the category name, "
        "confidence score, and reasoning."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "category": {
                "type": "string",
                "description": (
                    "The category name this email belongs to. "
                    "Must be one of the provided categories."
                ),
            },
            "confidence": {
                "type": "number",
                "minimum": 0.0,
                "maximum": 1.0,
                "description": (
                    "Confidence score for this classification (0.0 = no confidence, 1.0 = certain)"
                ),
            },
            "reasoning": {
                "type": "string",
                "description": "Brief explanation of why this category was chosen",
            },
        },
        "required": ["category", "confidence", "reasoning"],
    },
}


class BatchClassificationResult:
    """Result from batch classification for a single email."""

    __slots__ = ("email_id", "category_name", "confidence", "reasoning", "source", "error")

    def __init__(
        self,
        email_id: str,
        category_name: str = "",
        confidence: float = 0.0,
        reasoning: str = "",
        source: str = "llm:claude:batch",
        error: str | None = None,
    ):
        self.email_id = email_id
        self.category_name = category_name
        self.confidence = confidence
        self.reasoning = reasoning
        self.source = source
        self.error = error

    @property
    def succeeded(self) -> bool:
        return self.error is None and self.category_name != ""


class BatchClassifier:
    """
    Email classifier using the Anthropic Message Batches API.

    Submits all classification requests as a single batch for:
    - 50% cost reduction vs. standard API
    - Massive parallelism (Anthropic processes batch in parallel)
    - Higher rate limits (separate from interactive API)

    Requires provider="claude" and ANTHROPIC_API_KEY.
    """

    def __init__(self, config: ClassifierConfig):
        self._config = config
        self._sanitizer = EmailSanitizer()
        self._client = None

    def _get_client(self):
        """Lazy-initialize the Anthropic client."""
        if self._client is None:
            try:
                import anthropic
            except ImportError as e:
                raise ClassifierConnectionError(
                    provider="claude",
                    url="N/A",
                    recovery_hint=(
                        "The anthropic SDK is not installed. "
                        "Install with: pip install 'email-corpus-analyzer[cloud]'"
                    ),
                ) from e

            api_key = self._resolve_api_key()
            self._client = anthropic.Anthropic(api_key=api_key)
        return self._client

    def _resolve_api_key(self) -> str:
        """Resolve API key from configured env var."""
        env_var = self._config.api_key_env_var
        if not env_var:
            raise ClassifierConnectionError(
                provider="claude",
                url="N/A",
                recovery_hint=(
                    "No api_key_env_var configured for claude. "
                    "Set classifier.api_key_env_var in config."
                ),
            )
        api_key = os.environ.get(env_var)
        if not api_key:
            raise ClassifierConnectionError(
                provider="claude",
                url="N/A",
                recovery_hint=(
                    f"Environment variable '{env_var}' is not set. "
                    f"Set it to your Anthropic API key."
                ),
            )
        return api_key

    def classify_batch(
        self,
        emails: list[Email],
        categories: list[str],
        category_descriptions: dict[str, str] | None = None,
    ) -> list[BatchClassificationResult]:
        """
        Classify all emails using the Anthropic Batch API.

        Constructs prompts for every email, submits them as batch requests,
        polls for completion, and returns parsed results.

        Args:
            emails: List of emails to classify.
            categories: List of category names.
            category_descriptions: Optional dict of category_name -> description.

        Returns:
            List of BatchClassificationResult, one per email, in input order.
        """
        if not emails:
            return []

        client = self._get_client()
        system_prompt = self._build_system_prompt(categories, category_descriptions)

        # Build all batch requests, using index-based custom_id (max 64 chars)
        # since M365 email IDs can exceed the Batch API's 64-char limit.
        all_requests = []
        idx_to_email_id: dict[str, str] = {}
        total = len(emails)
        for idx, email in enumerate(emails):
            custom_id = f"email_{idx}"
            idx_to_email_id[custom_id] = email.id
            user_prompt = self._build_user_prompt(email)
            request = {
                "custom_id": custom_id,
                "params": {
                    "model": self._config.model_name,
                    "max_tokens": self._config.max_tokens,
                    "temperature": self._config.temperature,
                    "system": system_prompt,
                    "tools": [CLASSIFICATION_TOOL],
                    "tool_choice": {"type": "tool", "name": "classify_email"},
                    "messages": [{"role": "user", "content": user_prompt}],
                },
            }
            all_requests.append(request)
            if (idx + 1) % 5000 == 0 or idx + 1 == total:
                logger.info(f"Built {idx + 1}/{total} batch requests")

        logger.info(f"All {len(all_requests)} batch requests built for {self._config.model_name}")

        # Split into chunks of MAX_BATCH_SIZE, submit, and wait for each
        # before submitting the next. This avoids pre-authorizing the full
        # corpus cost upfront and handles credit exhaustion gracefully.
        batch_ids = []
        total_chunks = (len(all_requests) + MAX_BATCH_SIZE - 1) // MAX_BATCH_SIZE
        for chunk_start in range(0, len(all_requests), MAX_BATCH_SIZE):
            chunk = all_requests[chunk_start : chunk_start + MAX_BATCH_SIZE]
            chunk_num = chunk_start // MAX_BATCH_SIZE + 1

            logger.info(f"Submitting batch {chunk_num}/{total_chunks} ({len(chunk)} requests)")

            try:
                batch = client.messages.batches.create(requests=chunk)
            except anthropic.BadRequestError as e:
                if "credit balance" in str(e).lower():
                    logger.warning(
                        f"Credit balance exhausted after {len(batch_ids)} batches "
                        f"({chunk_start} requests submitted). "
                        f"Collecting partial results."
                    )
                    break
                raise

            batch_ids.append(batch.id)
            logger.info(
                f"Batch {chunk_num} submitted: id={batch.id} status={batch.processing_status}"
            )

            # Wait for this batch before submitting the next to avoid
            # pre-authorizing multiple batches simultaneously
            self._wait_for_completion(client, [batch.id])

        # Collect and parse results (keyed by index-based custom_id)
        results_map: dict[str, BatchClassificationResult] = {}
        for batch_id in batch_ids:
            self._collect_batch_results(client, batch_id, results_map, categories)

        # Return in input order, mapping index-based IDs back to real email IDs
        ordered_results = []
        for idx, email in enumerate(emails):
            custom_id = f"email_{idx}"
            if custom_id in results_map:
                result = results_map[custom_id]
                result.email_id = email.id  # Replace index ID with real email ID
                ordered_results.append(result)
            else:
                ordered_results.append(
                    BatchClassificationResult(
                        email_id=email.id,
                        error="No result returned from batch API",
                    )
                )

        succeeded = sum(1 for r in ordered_results if r.succeeded)
        failed = len(ordered_results) - succeeded
        logger.info(
            f"Batch classification complete: {succeeded} succeeded, {failed} failed "
            f"out of {len(ordered_results)} total"
        )

        return ordered_results

    def _wait_for_completion(self, client, batch_ids: list[str], timeout: float = 86400) -> None:
        """
        Poll batch statuses until all complete or timeout.

        Uses exponential backoff for polling interval.

        Args:
            client: Anthropic client.
            batch_ids: List of batch IDs to monitor.
            timeout: Maximum wait time in seconds (default 24 hours).

        Raises:
            ClassifierResponseError: If timeout is exceeded.
        """
        start_time = time.time()
        poll_interval = INITIAL_POLL_INTERVAL
        pending = set(batch_ids)

        while pending:
            elapsed = time.time() - start_time
            if elapsed > timeout:
                raise ClassifierResponseError(
                    message=f"Batch processing timed out after {elapsed:.0f}s",
                    raw_response=f"Pending batches: {pending}",
                )

            time.sleep(poll_interval)

            for batch_id in list(pending):
                batch = client.messages.batches.retrieve(batch_id)
                status = batch.processing_status
                counts = batch.request_counts

                logger.info(
                    f"Batch {batch_id}: status={status} "
                    f"succeeded={counts.succeeded} "
                    f"errored={counts.errored} "
                    f"processing={counts.processing}"
                )

                if status == "ended":
                    pending.discard(batch_id)
                elif status in ("canceling", "canceled"):
                    pending.discard(batch_id)
                    logger.warning(f"Batch {batch_id} was canceled")

            if pending:
                poll_interval = min(poll_interval * POLL_BACKOFF_FACTOR, MAX_POLL_INTERVAL)

        total_time = time.time() - start_time
        logger.info(f"All batches complete in {total_time:.1f}s")

    def _collect_batch_results(
        self,
        client,
        batch_id: str,
        results_map: dict[str, BatchClassificationResult],
        categories: list[str],
    ) -> None:
        """
        Download and parse results from a completed batch.

        Args:
            client: Anthropic client.
            batch_id: Batch ID to retrieve results for.
            results_map: Dict to populate with email_id -> result.
            categories: Valid category names for validation.
        """
        logger.info(f"Collecting results for batch {batch_id}")

        for result in client.messages.batches.results(batch_id):
            email_id = result.custom_id

            if result.result.type == "succeeded":
                parsed = self._parse_tool_response(result.result.message, email_id, categories)
                results_map[email_id] = parsed

            elif result.result.type == "errored":
                error_msg = str(getattr(result.result, "error", "Unknown error"))
                results_map[email_id] = BatchClassificationResult(
                    email_id=email_id,
                    error=f"API error: {error_msg}",
                )
                logger.warning(f"Email {email_id}: batch API error: {error_msg}")

            elif result.result.type == "expired":
                results_map[email_id] = BatchClassificationResult(
                    email_id=email_id,
                    error="Request expired before processing",
                )
                logger.warning(f"Email {email_id}: request expired")

            elif result.result.type == "canceled":
                results_map[email_id] = BatchClassificationResult(
                    email_id=email_id,
                    error="Request was canceled",
                )

    def _parse_tool_response(
        self, message, email_id: str, categories: list[str]
    ) -> BatchClassificationResult:
        """
        Parse a Message response looking for tool_use blocks with classification data.

        Args:
            message: Anthropic Message object from batch result.
            email_id: Email ID for this result.
            categories: Valid category names.

        Returns:
            BatchClassificationResult with parsed classification.
        """
        for block in message.content:
            if block.type == "tool_use" and block.name == "classify_email":
                tool_input = block.input
                category = tool_input.get("category", "")
                confidence = float(tool_input.get("confidence", 0.0))
                reasoning = tool_input.get("reasoning", "")

                # Validate category
                if category not in categories:
                    logger.warning(
                        f"Email {email_id}: LLM returned unknown category "
                        f"'{category}'. Keeping with reduced confidence."
                    )
                    confidence = min(confidence, 0.3)
                    reasoning = f"[LLM returned non-standard category '{category}'] {reasoning}"

                return BatchClassificationResult(
                    email_id=email_id,
                    category_name=category,
                    confidence=confidence,
                    reasoning=reasoning,
                )

        # No tool_use block found
        return BatchClassificationResult(
            email_id=email_id,
            error="No tool_use response in message",
        )

    # -------------------------------------------------------------------------
    # Prompt Construction (mirrors LLMClassifier prompts)
    # -------------------------------------------------------------------------

    def _build_system_prompt(
        self,
        categories: list[str],
        category_descriptions: dict[str, str] | None = None,
    ) -> str:
        """Build the system prompt with category definitions."""
        parts = [
            "You are an expert email classifier. Your job is to classify emails "
            "into exactly one of the provided categories.",
            "",
            "Rules:",
            "- Choose the single best-matching category from the list below.",
            "- Assign a confidence score from 0.0 (no confidence) to 1.0 (certain).",
            "- Provide a brief reasoning for your choice.",
            "- Base your decision on the email's subject, body, and sender information.",
            "",
            "Categories:",
        ]

        descriptions = category_descriptions or {}
        for cat_name in categories:
            desc = descriptions.get(cat_name, "")
            if desc:
                parts.append(f"- {cat_name}: {desc}")
            else:
                parts.append(f"- {cat_name}")
        parts.append("")

        return "\n".join(parts)

    def _build_user_prompt(self, email: Email) -> str:
        """Build the user prompt with sanitized email content."""
        email_content = self._sanitizer.wrap_for_prompt(email.subject, email.body_text)

        parts = [
            "Classify the following email:",
            "",
            f"From: {email.sender_email} ({email.sender_domain})",
            email_content,
        ]

        return "\n".join(parts)


__all__ = ["BatchClassifier", "BatchClassificationResult"]
