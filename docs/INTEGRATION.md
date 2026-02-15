# Email Extraction Architecture

This document describes the email extraction architecture and how to integrate with it programmatically.

## Overview

The extraction system uses a `BaseExtractor` ABC with two concrete implementations:

- **`EmailExtractor`** (M365/Hotmail) — uses `GraphAPIClient` with MSAL device code flow
- **`GmailExtractor`** (Gmail) — uses `GmailClient` with OAuth 2.0 browser flow

Both extractors share checkpoint handling, batch pagination, error collection, and progress callbacks via the base class.

## Architecture

```
ExtractionService
├── EmailExtractor (M365)          → GraphAPIClient → Microsoft Graph API
│   └── BaseExtractor (shared)         └── MSAL device code auth
└── GmailExtractor (Gmail)         → GmailClient → Gmail API
    └── BaseExtractor (shared)         └── OAuth 2.0 browser flow
```

### Key Classes

| Class | Module | Purpose |
|-------|--------|---------|
| `BaseExtractor` | `src/extractors/base_extractor.py` | ABC with shared batch loop, checkpoint, error handling |
| `EmailExtractor` | `src/extractors/m365_extractor.py` | M365/Hotmail extraction via Graph API |
| `GmailExtractor` | `src/extractors/gmail_extractor.py` | Gmail extraction via Gmail API |
| `GraphAPIClient` | `src/extractors/graph_api_client.py` | Microsoft Graph API client (MSAL device code) |
| `GmailClient` | `src/extractors/gmail_client.py` | Gmail API client (OAuth 2.0) |
| `ExtractionService` | `src/services/extraction_service.py` | Orchestrates extraction across sources |
| `CheckpointManager` | `src/extractors/checkpoint_manager.py` | Compact v2 checkpoint format (<1KB) |

## Programmatic Usage

### Using ExtractionService (Recommended)

```python
from src.services.extraction_service import ExtractionService

# M365/Hotmail extraction
service = ExtractionService(
    user_email="user@hotmail.com",
    source="hotmail",
    output_dir="~/data/outputs"
)
corpus = service.run()

# Gmail extraction
service = ExtractionService(
    user_email="user@gmail.com",
    source="gmail",
    output_dir="~/data/outputs"
)
corpus = service.run()

# Both sources merged
service = ExtractionService(
    user_email="user@hotmail.com",
    source="both",
    gmail_email="user@gmail.com",
    output_dir="~/data/outputs"
)
corpus = service.run()
```

### Using Extractors Directly

```python
from src.extractors.m365_extractor import EmailExtractor
from src.extractors.gmail_extractor import GmailExtractor

# M365/Hotmail
extractor = EmailExtractor(user_email="user@hotmail.com")
result = extractor.extract_all(batch_size=500)
corpus = result.corpus

# Gmail
extractor = GmailExtractor(user_email="user@gmail.com")
result = extractor.extract_all(batch_size=500)
corpus = result.corpus

# Incremental extraction (only new emails)
result = extractor.extract_incremental()
```

## Authentication

### M365/Hotmail (Device Code Flow)

No setup required. On first run, the user sees a device code and URL:

```
MICROSOFT AUTHENTICATION REQUIRED
To sign in, open https://microsoft.com/devicelogin and enter code XXXXXXXX
```

Tokens are cached at `~/.email-analyzer/ms_token_cache.json`.

### Gmail (OAuth 2.0 Browser Flow)

Requires OAuth client credentials from Google Cloud Console:

1. Enable Gmail API in Google Cloud Console
2. Create OAuth 2.0 Desktop App credentials
3. Save the JSON file to `~/.email-analyzer/gmail_credentials.json`

On first run, a browser opens for Google sign-in. Tokens are cached at `~/.email-analyzer/gmail_token.json`.

See [Setup Guide](M365_SETUP.md) for detailed instructions.

## Extending with New Email Sources

To add a new email source:

1. Create a new client class (e.g., `ImapClient`) for API communication
2. Create a new extractor subclass of `BaseExtractor`
3. Implement the abstract methods: `_fetch_batch()`, `_get_api_client()`, `_build_incremental_query()`
4. Register the new source in `ExtractionService._get_extractor()`
5. Add CLI support for the new `--source` value

The `BaseExtractor` handles all common logic (checkpoints, batching, error collection, progress) automatically.
