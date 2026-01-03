# Email Corpus Analyzer - Modernization Plan

**Version**: 2.0
**Created**: 2026-01-03
**Status**: Draft

## Executive Summary

This plan modernizes the email corpus analyzer to support:
1. **Multiple email providers**: M365 (corporate), Gmail, IMAP/SMTP
2. **Multi-mailbox analysis**: Each mailbox analyzed individually with cross-mailbox insights
3. **Async-first architecture**: Concurrent extraction for better performance
4. **LLM-powered categorization**: Replace heuristics with Claude for intelligent categorization
5. **Modern Python stack**: Updated dependencies and patterns

---

## Part 1: Current State Analysis

### What Works Well (Keep)
| Component | Rationale |
|-----------|-----------|
| Pydantic 2.0 models | Best-in-class validation, keep and extend |
| Modular analyzer design | Clean separation, easy to extend |
| Checkpoint/resume system | Essential for long extractions |
| Interactive review UI | Maintains human-in-the-loop |
| PathConfig centralization | Good configuration management |
| Progress callbacks | User feedback without threading complexity |

### What Needs Modernization
| Component | Current State | Problem |
|-----------|--------------|---------|
| M365 extractor | Stub implementation, MCP-dependent | Can't work standalone or with other providers |
| Email model | "M365 message ID" hardcoded | Not provider-agnostic |
| Corpus model | Single `user_email` field | No multi-mailbox support |
| Semantic analysis | KMeans with fixed cluster count | Must guess cluster count, poor interpretability |
| Category generation | Keyword/domain heuristics | Misses context, poor category names |
| CLI | M365-only, single mailbox | Doesn't support multiple providers/mailboxes |
| All I/O | Synchronous | Slow extraction for large mailboxes |

---

## Part 2: Target Architecture

### 2.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CLI Layer                                       │
│  email-analyzer add-mailbox | extract | analyze | suggest | review | report  │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Mailbox Manager                                      │
│  - Registry of configured mailboxes                                          │
│  - Per-mailbox corpus storage                                                │
│  - Cross-mailbox aggregation                                                 │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
          ┌───────────────────────────┼───────────────────────────┐
          ▼                           ▼                           ▼
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  M365 Provider   │     │  Gmail Provider  │     │  IMAP Provider   │
│  (msgraph-sdk)   │     │  (google-api)    │     │  (aioimaplib)    │
└──────────────────┘     └──────────────────┘     └──────────────────┘
          │                           │                           │
          └───────────────────────────┼───────────────────────────┘
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      Provider Abstraction Layer                              │
│  - Async EmailProvider protocol                                              │
│  - Unified Email model                                                       │
│  - Provider-specific auth handling                                           │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Analysis Pipeline                                    │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │  Embedding  │→ │  Clustering │→ │  LLM-based  │→ │  Confidence Scoring │ │
│  │  Generation │  │  (HDBSCAN)  │  │  Naming     │  │  (with reasoning)   │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      LLM Categorization Engine                               │
│  - Claude API for intelligent category suggestions                           │
│  - Structured output for consistent results                                  │
│  - Hybrid: embeddings for similarity + LLM for interpretation               │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Directory Structure

```
src/
├── providers/                    # NEW: Provider abstraction
│   ├── __init__.py
│   ├── base.py                   # EmailProvider protocol
│   ├── m365/
│   │   ├── __init__.py
│   │   ├── provider.py           # M365Provider implementation
│   │   ├── auth.py               # OAuth2 with device code flow
│   │   └── mapper.py             # Graph API → Email model
│   ├── gmail/
│   │   ├── __init__.py
│   │   ├── provider.py           # GmailProvider implementation
│   │   ├── auth.py               # OAuth2 with credentials file
│   │   └── mapper.py             # Gmail API → Email model
│   └── imap/
│       ├── __init__.py
│       ├── provider.py           # IMAPProvider implementation
│       ├── auth.py               # Basic/OAuth IMAP auth
│       └── mapper.py             # IMAP → Email model
├── mailbox/                      # NEW: Multi-mailbox management
│   ├── __init__.py
│   ├── registry.py               # Mailbox configuration store
│   ├── manager.py                # Mailbox operations
│   └── aggregator.py             # Cross-mailbox analysis
├── extractors/                   # REFACTOR: Use providers
│   ├── __init__.py
│   ├── async_extractor.py        # Async extraction with providers
│   ├── checkpoint_manager.py     # Keep, enhance for multi-mailbox
│   └── html_parser.py            # Keep as-is
├── analyzers/                    # ENHANCE: Better clustering
│   ├── __init__.py
│   ├── semantic_analyzer.py      # Upgrade to HDBSCAN
│   ├── sender_analyzer.py        # Keep
│   ├── subject_analyzer.py       # Keep
│   ├── temporal_analyzer.py      # Keep
│   └── volume_analyzer.py        # Keep
├── llm/                          # NEW: LLM integration
│   ├── __init__.py
│   ├── client.py                 # Anthropic API client
│   ├── categorizer.py            # LLM-based categorization
│   ├── namer.py                  # Cluster naming with Claude
│   └── schemas.py                # Structured output schemas
├── generators/                   # REFACTOR: Use LLM
│   ├── __init__.py
│   ├── category_generator.py     # Integrate LLM
│   ├── confidence_scorer.py      # Add LLM reasoning
│   └── template_matcher.py       # Optional: Keep as fallback
├── models/                       # EXTEND: Multi-provider support
│   ├── __init__.py
│   ├── email.py                  # Add provider field
│   ├── corpus.py                 # Add mailbox_id
│   ├── mailbox.py                # NEW: Mailbox configuration
│   ├── provider.py               # NEW: Provider enum
│   └── ...                       # Keep others
├── ui/                           # Keep
├── utils/                        # Keep
├── cli.py                        # REWRITE: Multi-provider CLI
└── main.py
```

---

## Part 3: Provider Abstraction Layer

### 3.1 Email Provider Protocol

```python
# src/providers/base.py
from abc import ABC, abstractmethod
from typing import AsyncIterator
from dataclasses import dataclass
from enum import Enum

class ProviderType(Enum):
    M365 = "m365"
    GMAIL = "gmail"
    IMAP = "imap"

@dataclass
class ProviderConfig:
    """Base configuration for all providers."""
    provider_type: ProviderType
    display_name: str  # User-friendly name like "Work Email"
    email_address: str

@dataclass
class M365Config(ProviderConfig):
    """M365-specific configuration."""
    tenant_id: str | None = None  # None = consumer accounts
    client_id: str | None = None  # For custom app registration

@dataclass
class GmailConfig(ProviderConfig):
    """Gmail-specific configuration."""
    credentials_file: str  # Path to OAuth credentials.json

@dataclass
class IMAPConfig(ProviderConfig):
    """IMAP-specific configuration."""
    host: str
    port: int = 993
    use_ssl: bool = True
    username: str | None = None  # If different from email_address
    password: str | None = None  # Or use OAuth

class EmailProvider(ABC):
    """Abstract base for all email providers."""

    @property
    @abstractmethod
    def provider_type(self) -> ProviderType:
        """Return the provider type."""
        ...

    @abstractmethod
    async def authenticate(self) -> bool:
        """Authenticate with the email service."""
        ...

    @abstractmethod
    async def fetch_emails(
        self,
        batch_size: int = 100,
        since: datetime | None = None,
        folder: str = "INBOX"
    ) -> AsyncIterator[Email]:
        """Yield emails in batches."""
        ...

    @abstractmethod
    async def get_total_count(self, folder: str = "INBOX") -> int | None:
        """Get total email count if available."""
        ...

    @abstractmethod
    async def close(self) -> None:
        """Clean up connections."""
        ...
```

### 3.2 M365 Provider Implementation

```python
# src/providers/m365/provider.py
from msgraph import GraphServiceClient
from azure.identity import DeviceCodeCredential

class M365Provider(EmailProvider):
    """Microsoft 365 email provider using Microsoft Graph SDK."""

    SCOPES = ["Mail.Read", "User.Read"]

    def __init__(self, config: M365Config):
        self.config = config
        self.client: GraphServiceClient | None = None

    @property
    def provider_type(self) -> ProviderType:
        return ProviderType.M365

    async def authenticate(self) -> bool:
        """Authenticate using device code flow (works for personal & corporate)."""
        credential = DeviceCodeCredential(
            client_id=self.config.client_id or "default_app_id",
            tenant_id=self.config.tenant_id or "consumers"
        )
        self.client = GraphServiceClient(credential, self.SCOPES)

        # Verify by fetching user profile
        user = await self.client.me.get()
        return user is not None

    async def fetch_emails(
        self,
        batch_size: int = 100,
        since: datetime | None = None,
        folder: str = "INBOX"
    ) -> AsyncIterator[Email]:
        """Fetch emails using Graph API with pagination."""
        request = self.client.me.mail_folders.by_mail_folder_id(folder).messages

        # Configure request with pagination
        query_params = MessagesRequestBuilder.MessagesRequestBuilderGetQueryParameters(
            top=batch_size,
            orderby=["receivedDateTime desc"],
            select=["id", "subject", "from", "toRecipients",
                    "receivedDateTime", "body", "hasAttachments"]
        )

        if since:
            query_params.filter = f"receivedDateTime ge {since.isoformat()}"

        # Iterate through pages
        response = await request.get(request_configuration=...)
        while response:
            for message in response.value:
                yield self._map_to_email(message)

            # Get next page
            if response.odata_next_link:
                response = await request.with_url(response.odata_next_link).get()
            else:
                break
```

### 3.3 Gmail Provider Implementation

```python
# src/providers/gmail/provider.py
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

class GmailProvider(EmailProvider):
    """Gmail provider using Google API."""

    SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

    def __init__(self, config: GmailConfig):
        self.config = config
        self.service = None

    async def authenticate(self) -> bool:
        """Authenticate using OAuth2 flow."""
        flow = InstalledAppFlow.from_client_secrets_file(
            self.config.credentials_file,
            self.SCOPES
        )
        creds = flow.run_local_server(port=0)
        self.service = build("gmail", "v1", credentials=creds)
        return True

    async def fetch_emails(
        self,
        batch_size: int = 100,
        since: datetime | None = None,
        folder: str = "INBOX"
    ) -> AsyncIterator[Email]:
        """Fetch emails using Gmail API with batching."""
        query = f"in:{folder}"
        if since:
            query += f" after:{int(since.timestamp())}"

        # Use asyncio.to_thread for sync API calls
        page_token = None
        while True:
            results = await asyncio.to_thread(
                self.service.users().messages().list,
                userId="me",
                q=query,
                maxResults=batch_size,
                pageToken=page_token
            )

            # Batch fetch full message details
            for msg_id in (m["id"] for m in results.get("messages", [])):
                message = await asyncio.to_thread(
                    self.service.users().messages().get,
                    userId="me",
                    id=msg_id,
                    format="full"
                )
                yield self._map_to_email(message)

            page_token = results.get("nextPageToken")
            if not page_token:
                break
```

### 3.4 IMAP Provider Implementation

```python
# src/providers/imap/provider.py
import aioimaplib

class IMAPProvider(EmailProvider):
    """IMAP provider for generic mailboxes."""

    def __init__(self, config: IMAPConfig):
        self.config = config
        self.client: aioimaplib.IMAP4_SSL | None = None

    async def authenticate(self) -> bool:
        """Connect and authenticate to IMAP server."""
        self.client = aioimaplib.IMAP4_SSL(
            host=self.config.host,
            port=self.config.port
        )
        await self.client.wait_hello_from_server()

        response = await self.client.login(
            self.config.username or self.config.email_address,
            self.config.password
        )
        return response.result == "OK"

    async def fetch_emails(
        self,
        batch_size: int = 100,
        since: datetime | None = None,
        folder: str = "INBOX"
    ) -> AsyncIterator[Email]:
        """Fetch emails using IMAP."""
        await self.client.select(folder)

        # Build search criteria
        criteria = "ALL"
        if since:
            criteria = f'SINCE {since.strftime("%d-%b-%Y")}'

        _, data = await self.client.search(criteria)
        message_ids = data[0].split()

        # Fetch in batches
        for i in range(0, len(message_ids), batch_size):
            batch = message_ids[i:i + batch_size]
            batch_range = f"{batch[0].decode()}:{batch[-1].decode()}"

            _, messages = await self.client.fetch(
                batch_range,
                "(RFC822.HEADER BODY[TEXT])"
            )

            for msg in messages:
                yield self._parse_imap_message(msg)
```

---

## Part 4: Multi-Mailbox Support

### 4.1 Mailbox Model

```python
# src/models/mailbox.py
from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime
from uuid import UUID, uuid4

class MailboxStatus(Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    ERROR = "error"
    PENDING_AUTH = "pending_auth"

class Mailbox(BaseModel):
    """Configured mailbox with extraction status."""

    id: UUID = Field(default_factory=uuid4)
    name: str  # User-friendly name: "Work Email", "Personal Gmail"
    provider: ProviderType
    email_address: str
    status: MailboxStatus = MailboxStatus.PENDING_AUTH

    # Provider-specific config stored as JSON
    provider_config: dict = Field(default_factory=dict)

    # Extraction state
    last_extraction: datetime | None = None
    total_emails: int = 0
    corpus_path: str | None = None  # Path to this mailbox's corpus

    # Analysis state
    last_analysis: datetime | None = None
    analysis_path: str | None = None
```

### 4.2 Mailbox Registry

```python
# src/mailbox/registry.py
import json
from pathlib import Path
from uuid import UUID

class MailboxRegistry:
    """Persistent storage for mailbox configurations."""

    def __init__(self, config_dir: Path = Path.home() / ".email-analyzer"):
        self.config_dir = config_dir
        self.config_file = config_dir / "mailboxes.json"
        self._ensure_dir()

    def add_mailbox(self, mailbox: Mailbox) -> None:
        """Register a new mailbox."""
        mailboxes = self._load()
        mailboxes[str(mailbox.id)] = mailbox.model_dump(mode="json")
        self._save(mailboxes)

    def get_mailbox(self, mailbox_id: UUID) -> Mailbox | None:
        """Get mailbox by ID."""
        mailboxes = self._load()
        data = mailboxes.get(str(mailbox_id))
        return Mailbox(**data) if data else None

    def list_mailboxes(self) -> list[Mailbox]:
        """List all configured mailboxes."""
        return [Mailbox(**m) for m in self._load().values()]

    def get_by_email(self, email: str) -> Mailbox | None:
        """Find mailbox by email address."""
        for mailbox in self.list_mailboxes():
            if mailbox.email_address == email:
                return mailbox
        return None
```

### 4.3 Per-Mailbox Storage

```
~/.email-analyzer/
├── mailboxes.json              # Mailbox registry
├── credentials/                # Encrypted auth tokens
│   ├── {mailbox_id}.enc
│   └── ...
└── data/
    ├── {mailbox_id}/           # Per-mailbox data
    │   ├── corpus.json
    │   ├── analysis.json
    │   ├── suggestions.json
    │   ├── approved_categories.json
    │   └── checkpoints/
    │       └── extraction_checkpoint.json
    └── aggregated/             # Cross-mailbox analysis
        └── combined_analysis.json
```

---

## Part 5: Async Extraction Architecture

### 5.1 Async Extractor

```python
# src/extractors/async_extractor.py
import asyncio
from typing import AsyncIterator

class AsyncEmailExtractor:
    """Async email extraction with provider abstraction."""

    def __init__(
        self,
        provider: EmailProvider,
        checkpoint_manager: CheckpointManager
    ):
        self.provider = provider
        self.checkpoint = checkpoint_manager

    async def extract_all(
        self,
        batch_size: int = 100,
        progress_callback: Callable[[int, int | None], None] | None = None
    ) -> ExtractionResult:
        """Extract all emails with progress tracking."""

        # Get resume point if any
        start_from = self.checkpoint.get_resume_point()

        emails: list[Email] = []
        errors: list[ExtractionError] = []

        try:
            total = await self.provider.get_total_count()

            async for email in self.provider.fetch_emails(
                batch_size=batch_size,
                since=start_from.last_date if start_from else None
            ):
                try:
                    emails.append(email)

                    # Checkpoint periodically
                    if len(emails) % 100 == 0:
                        await self.checkpoint.save_async(emails)
                        if progress_callback:
                            progress_callback(len(emails), total)

                except Exception as e:
                    errors.append(ExtractionError(
                        email_id=email.id if email else "unknown",
                        error_type="processing",
                        error_message=str(e)
                    ))

            # Clear checkpoint on success
            self.checkpoint.clear()

            return ExtractionResult(
                emails=emails,
                errors=errors,
                success_count=len(emails),
                failure_count=len(errors)
            )

        finally:
            await self.provider.close()
```

### 5.2 Concurrent Multi-Mailbox Extraction

```python
# src/mailbox/manager.py
class MailboxManager:
    """Orchestrate operations across multiple mailboxes."""

    async def extract_all_mailboxes(
        self,
        mailbox_ids: list[UUID] | None = None,
        concurrency: int = 3
    ) -> dict[UUID, ExtractionResult]:
        """Extract from multiple mailboxes concurrently."""

        mailboxes = self.registry.list_mailboxes()
        if mailbox_ids:
            mailboxes = [m for m in mailboxes if m.id in mailbox_ids]

        semaphore = asyncio.Semaphore(concurrency)

        async def extract_one(mailbox: Mailbox) -> tuple[UUID, ExtractionResult]:
            async with semaphore:
                provider = self._get_provider(mailbox)
                extractor = AsyncEmailExtractor(provider, ...)
                result = await extractor.extract_all()
                return mailbox.id, result

        tasks = [extract_one(m) for m in mailboxes]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        return {mid: res for mid, res in results if not isinstance(res, Exception)}
```

---

## Part 6: LLM-Powered Categorization

### 6.1 Anthropic Client Wrapper

```python
# src/llm/client.py
import anthropic
from pydantic import BaseModel

class LLMClient:
    """Wrapper for Anthropic API with structured outputs."""

    def __init__(self, api_key: str | None = None):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = "claude-sonnet-4-20250514"

    async def generate_structured(
        self,
        prompt: str,
        response_model: type[BaseModel],
        system: str | None = None
    ) -> BaseModel:
        """Generate structured output using tool use."""

        response = await asyncio.to_thread(
            self.client.messages.create,
            model=self.model,
            max_tokens=4096,
            system=system or "You are an expert email analyst.",
            messages=[{"role": "user", "content": prompt}],
            tools=[{
                "name": "structured_response",
                "description": "Return structured analysis",
                "input_schema": response_model.model_json_schema()
            }],
            tool_choice={"type": "tool", "name": "structured_response"}
        )

        # Extract tool use result
        for block in response.content:
            if block.type == "tool_use":
                return response_model.model_validate(block.input)

        raise ValueError("No structured response generated")
```

### 6.2 LLM-Based Category Naming

```python
# src/llm/namer.py
from pydantic import BaseModel, Field

class ClusterName(BaseModel):
    """Structured output for cluster naming."""
    name: str = Field(description="Concise category name (2-4 words)")
    description: str = Field(description="Brief description of what emails this contains")
    confidence: float = Field(ge=0, le=1, description="Confidence in this categorization")
    reasoning: str = Field(description="Why this name fits the cluster")

class ClusterNamer:
    """Use LLM to generate meaningful cluster names."""

    def __init__(self, client: LLMClient):
        self.client = client

    async def name_cluster(
        self,
        representative_samples: list[RepresentativeSample],
        common_domains: list[tuple[str, int]]
    ) -> ClusterName:
        """Generate a meaningful name for a cluster."""

        # Build context from samples
        samples_text = "\n".join([
            f"- Subject: {s.subject}\n  From: {s.sender}\n  Preview: {s.body_preview[:100]}..."
            for s in representative_samples[:5]
        ])

        domains_text = ", ".join([f"{d[0]} ({d[1]} emails)" for d in common_domains[:5]])

        prompt = f"""Analyze these representative emails from a cluster and suggest a category name.

## Representative Emails:
{samples_text}

## Common Sender Domains:
{domains_text}

Generate a concise, meaningful category name that captures what these emails have in common.
Consider: topic, purpose, sender type, or action required."""

        return await self.client.generate_structured(
            prompt=prompt,
            response_model=ClusterName
        )
```

### 6.3 LLM-Based Category Suggestion

```python
# src/llm/categorizer.py
class CategorySuggestion(BaseModel):
    """Structured category suggestion."""
    category_name: str
    description: str
    confidence: float = Field(ge=0, le=1)
    reasoning: str
    matched_patterns: list[str]
    suggested_action: str = Field(description="archive, delete, label, keep")

class CategorySuggestions(BaseModel):
    """Multiple category suggestions."""
    categories: list[CategorySuggestion]
    uncategorized_percentage: float
    recommendations: str

class LLMCategorizer:
    """Use Claude for intelligent category suggestions."""

    async def suggest_categories(
        self,
        analysis_results: AnalysisResults,
        existing_categories: list[Category] | None = None
    ) -> CategorySuggestions:
        """Generate category suggestions using LLM."""

        # Prepare analysis summary
        summary = self._build_analysis_summary(analysis_results)

        prompt = f"""You are analyzing an email inbox to suggest organizational categories.

## Inbox Analysis Summary:
{summary}

## Existing Categories (if any):
{existing_categories or "None"}

Based on this analysis, suggest categories that would help organize this inbox effectively.
Consider:
1. High-volume senders that deserve their own category
2. Content patterns (newsletters, receipts, notifications)
3. Temporal patterns (one-time vs recurring)
4. Action-based categories (requires response, FYI only, archive immediately)

Aim for 5-15 categories that cover most emails with minimal overlap."""

        return await self.client.generate_structured(
            prompt=prompt,
            response_model=CategorySuggestions
        )
```

### 6.4 Hybrid Approach: Embeddings + LLM

```python
# src/analyzers/semantic_analyzer.py (updated)
from hdbscan import HDBSCAN

class ModernSemanticAnalyzer:
    """Updated semantic analyzer with HDBSCAN and LLM naming."""

    def __init__(
        self,
        embedding_model: str = "mixedbread-ai/mxbai-embed-large-v1",
        llm_client: LLMClient | None = None
    ):
        self.embedding_model = embedding_model
        self.model = None
        self.llm_client = llm_client
        self.namer = ClusterNamer(llm_client) if llm_client else None

    async def analyze(
        self,
        corpus: Corpus,
        min_cluster_size: int = 10,
        progress_callback: Callable | None = None
    ) -> list[ContentCluster]:
        """Analyze with HDBSCAN (auto cluster count) and LLM naming."""

        # Generate embeddings (same as before)
        self._ensure_model_loaded()
        texts = [email.combined_text for email in corpus.emails]
        embeddings = self.model.encode(texts, show_progress_bar=True)

        # Use HDBSCAN - no need to specify cluster count!
        clusterer = HDBSCAN(
            min_cluster_size=min_cluster_size,
            min_samples=5,
            metric='euclidean',
            cluster_selection_method='eom'
        )
        cluster_labels = clusterer.fit_predict(embeddings)

        # Build clusters
        clusters = []
        unique_labels = set(cluster_labels) - {-1}  # -1 is noise

        for cluster_id in unique_labels:
            cluster = self._build_cluster(
                cluster_id, cluster_labels, corpus, embeddings
            )

            # Use LLM for naming if available
            if self.namer:
                name_result = await self.namer.name_cluster(
                    cluster.representative_samples,
                    cluster.common_domains
                )
                cluster.suggested_name = name_result.name
                cluster.name_confidence = name_result.confidence
                cluster.name_reasoning = name_result.reasoning

            clusters.append(cluster)

        return clusters
```

---

## Part 7: Updated Dependencies

### 7.1 New pyproject.toml

```toml
[project]
name = "email-corpus-analyzer"
version = "2.0.0"
description = "Multi-provider email corpus analysis with LLM-powered categorization"
requires-python = ">=3.11"  # For better async and typing

dependencies = [
    # Core
    "pydantic>=2.0.0",

    # Async
    "asyncio>=3.4.3",
    "aiofiles>=23.0.0",

    # Email Providers
    "msgraph-sdk>=1.0.0",              # M365
    "azure-identity>=1.15.0",           # M365 auth
    "google-api-python-client>=2.0.0",  # Gmail
    "google-auth-oauthlib>=1.0.0",      # Gmail auth
    "aioimaplib>=1.0.0",                # IMAP async

    # ML/Embeddings
    "sentence-transformers>=2.0.0",
    "hdbscan>=0.8.33",                  # Better than KMeans
    "scikit-learn>=1.3.0",
    "numpy>=1.24.0",

    # LLM
    "anthropic>=0.18.0",

    # HTML/Text
    "beautifulsoup4>=4.12.0",
    "lxml>=4.9.0",

    # CLI
    "typer>=0.9.0",                     # Modern CLI framework
    "rich>=13.0.0",                     # Beautiful output
    "tqdm>=4.66.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-cov>=4.1.0",
    "pytest-asyncio>=0.21.0",
    "ruff>=0.1.0",
    "mypy>=1.0.0",
]
```

---

## Part 8: Updated CLI Design

### 8.1 Modern CLI with Typer

```python
# src/cli.py
import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(help="Email Corpus Analyzer - Multi-provider email analysis")
console = Console()

# Mailbox management commands
mailbox_app = typer.Typer(help="Manage email mailboxes")
app.add_typer(mailbox_app, name="mailbox")

@mailbox_app.command("add")
def add_mailbox(
    name: str = typer.Option(..., help="Friendly name for mailbox"),
    provider: str = typer.Option(..., help="Provider: m365, gmail, imap"),
    email: str = typer.Option(..., help="Email address"),
):
    """Add a new mailbox for analysis."""
    console.print(f"[green]Adding mailbox:[/green] {name} ({provider})")
    # ... implementation

@mailbox_app.command("list")
def list_mailboxes():
    """List all configured mailboxes."""
    table = Table(title="Configured Mailboxes")
    table.add_column("Name")
    table.add_column("Provider")
    table.add_column("Email")
    table.add_column("Status")
    table.add_column("Last Sync")
    # ... add rows
    console.print(table)

@mailbox_app.command("remove")
def remove_mailbox(mailbox_id: str):
    """Remove a mailbox configuration."""
    # ... implementation

# Extraction commands
@app.command("extract")
def extract(
    mailbox: str = typer.Option(None, help="Mailbox name or ID (default: all)"),
    since: str = typer.Option(None, help="Extract emails since date (YYYY-MM-DD)"),
):
    """Extract emails from configured mailboxes."""
    # ... async extraction

# Analysis commands
@app.command("analyze")
def analyze(
    mailbox: str = typer.Option(None, help="Mailbox to analyze (default: all)"),
    use_llm: bool = typer.Option(True, help="Use LLM for category naming"),
):
    """Analyze email corpus for patterns."""
    # ... run analysis

@app.command("suggest")
def suggest(
    mailbox: str = typer.Option(None, help="Mailbox for suggestions"),
    use_llm: bool = typer.Option(True, help="Use LLM for intelligent suggestions"),
):
    """Generate category suggestions."""
    # ... generate suggestions

@app.command("review")
def review(mailbox: str = typer.Option(None)):
    """Interactively review category suggestions."""
    # ... interactive review

@app.command("report")
def report(
    mailbox: str = typer.Option(None, help="Mailbox for report"),
    format: str = typer.Option("markdown", help="Output format: markdown, json, html"),
    cross_mailbox: bool = typer.Option(False, help="Generate cross-mailbox analysis"),
):
    """Generate analysis report."""
    # ... generate report

if __name__ == "__main__":
    app()
```

### 8.2 Example Usage

```bash
# Add mailboxes
email-analyzer mailbox add --name "Work" --provider m365 --email user@company.com
email-analyzer mailbox add --name "Personal" --provider gmail --email user@gmail.com
email-analyzer mailbox add --name "Legacy" --provider imap --email user@oldmail.com

# List configured mailboxes
email-analyzer mailbox list

# Extract from all mailboxes
email-analyzer extract

# Extract from specific mailbox
email-analyzer extract --mailbox "Work"

# Analyze with LLM categorization
email-analyzer analyze --use-llm

# Generate cross-mailbox report
email-analyzer report --cross-mailbox --format html
```

---

## Part 9: Implementation Phases

### Phase 1: Foundation (Week 1-2)
- [ ] Update data models for multi-provider support
- [ ] Implement provider abstraction layer (base protocol)
- [ ] Create mailbox registry and manager
- [ ] Update storage layout for per-mailbox data

### Phase 2: Provider Implementations (Week 3-4)
- [ ] Implement M365Provider with msgraph-sdk
- [ ] Implement GmailProvider with google-api-python-client
- [ ] Implement IMAPProvider with aioimaplib
- [ ] Create async extractor using providers

### Phase 3: Analysis Modernization (Week 5)
- [ ] Replace KMeans with HDBSCAN
- [ ] Add LLM client wrapper
- [ ] Implement LLM-based cluster naming
- [ ] Update category generator with LLM suggestions

### Phase 4: CLI & Integration (Week 6)
- [ ] Rewrite CLI with Typer
- [ ] Add multi-mailbox commands
- [ ] Implement cross-mailbox analysis
- [ ] Add report generation

### Phase 5: Testing & Polish (Week 7)
- [ ] Add async tests with pytest-asyncio
- [ ] Integration tests for each provider
- [ ] Documentation updates
- [ ] Performance optimization

---

## Part 10: Migration Path

### For Existing Users

1. **Data Migration**: Existing corpus files remain compatible
2. **Config Migration**: Script to import existing M365 config to new registry
3. **Fallback Mode**: Keep KMeans available if LLM not configured
4. **Gradual Adoption**: Can use new CLI while keeping old corpus files

### Backward Compatibility

```python
# Legacy compatibility wrapper
def legacy_extract(user_email: str) -> Corpus:
    """Compatibility function for old API."""
    mailbox = Mailbox(
        name="Legacy Import",
        provider=ProviderType.M365,
        email_address=user_email
    )
    # ... use new system internally
```

---

## Appendix A: Provider Comparison

| Feature | M365 | Gmail | IMAP |
|---------|------|-------|------|
| Auth Method | OAuth2 Device Code | OAuth2 Web Flow | Password/OAuth |
| Batch Size | 500/request | 100/request | Unlimited |
| Total Count | No | Yes | Yes |
| Rate Limits | Moderate | Strict | None |
| HTML Bodies | Native | Base64 encoded | RFC822 |
| Attachments | Separate call | Inline | Inline |
| Folders | Native | Labels | Folders |

## Appendix B: LLM Cost Estimation

| Operation | Tokens (est.) | Cost @ $3/1M |
|-----------|---------------|--------------|
| Cluster naming (per cluster) | ~500 | $0.0015 |
| Category suggestions (full) | ~2000 | $0.006 |
| Confidence reasoning | ~300 | $0.0009 |
| **Typical analysis (10 clusters)** | ~8000 | **$0.024** |

## Appendix C: Security Considerations

1. **Credentials**: All OAuth tokens encrypted at rest
2. **Email Content**: Never leaves local machine except for LLM calls
3. **LLM Privacy**: Only representative samples sent (5 per cluster)
4. **Permissions**: Read-only access for all providers
5. **Audit Log**: All API calls logged locally
