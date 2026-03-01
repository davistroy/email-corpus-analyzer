# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Test Commands

```bash
# Install dependencies
pip install -r requirements.txt
pip install -e ".[dev]"      # Install with dev dependencies
pip install -e ".[cloud]"    # Install with Anthropic Claude support
pip install -e ".[dev,cloud]"  # Both

# Run tests (4252 tests)
pytest                                  # All 4252 tests with coverage
pytest tests/unit/                      # Unit tests only
pytest tests/contract/                  # Contract tests only
pytest tests/integration/               # Integration tests only
pytest tests/unit/test_html_parser.py   # Single test file
pytest -k "test_name"                   # Run specific test by name
pytest --cov=src --cov-report=html      # Generate HTML coverage report

# Linting
ruff check src/
ruff check src/ --fix           # Auto-fix issues

# Run CLI (see CLI Commands table below for full command list)
python -m src.cli --help
python -m src.cli pipeline --user-email user@hotmail.com
python -m src.cli pipeline --user-email user@gmail.com --source gmail
```

## Architecture

This system extracts emails from M365/Hotmail and Gmail, analyzes patterns, generates category suggestions, applies rules and LLM-based classifiers for email categorization, stores data in SQLite, learns from user corrections, and automates email organization through a multi-stage pipeline:

```
Extract → Analyze → Suggest → Review → Rules → Categorize → Apply
                                                    ↓
                                    Classify (LLM/SetFit/Ensemble)
                                                    ↓
                                    Feedback → Learn → Retrain
                                                    ↓
                                          Scheduler → Monitor → Notify
```

### Core Modules

| Module | Purpose | Key Abstractions |
|--------|---------|-----------------|
| `src/extractors/` | Email extraction from M365/Hotmail and Gmail | `BaseExtractor` ABC, `GraphApiClient` (MSAL device code), `GmailClient` (OAuth 2.0), `CheckpointManager` (v2 compact format) |
| `src/analyzers/` | 5 core + 2 optional analyzers | `BaseAnalyzer` ABC, `SemanticAnalyzer` (sentence-transformers), `ClusterOptimizer` (elbow/silhouette), `ThreadAnalyzer` |
| `src/generators/` | Category suggestion from analysis | `TemplateMatcher` (18 templates, word-boundary regex), `ConfidenceScorer` (log volume), `NameGenerator` (TF-IDF) |
| `src/rules/` | Category rule system | `RuleEngine` (AND/OR, 8 operators, short-circuit), `RuleBuilder`, `RuleTester` (coverage, confusion matrix) |
| `src/categorizer/` | Email-by-email categorization | `EmailCategorizer`, `ConflictResolver` (priority/specificity/historical), `CoverageReporter` |
| `src/classifiers/` | Classification abstraction layer | `BaseClassifier` ABC, `LLMClassifier` (Instructor + Ollama/OpenAI/Claude), `SetFitClassifier` (few-shot fine-tuning), `EnsembleClassifier` (priority-ordered chaining), `EmailSanitizer` (prompt injection defense) |
| `src/storage/` | SQLite persistence layer | `Database` (WAL mode, schema versioning), `EmailStore` (CRUD + upsert), `EmbeddingStore` (sqlite-vec cosine similarity), `JsonToSqliteMigrator` |
| `src/actions/` | Email action execution | `FolderManager`, `EmailMover` (batch + rollback), `RuleDeployer` (server-side rules), `ActionLogger` (JSONL audit) |
| `src/automation/` | Scheduled processing, monitoring, retraining | `IncrementalProcessor`, `ChangeDetector` (drift/anomaly), `Scheduler` (Win Task Scheduler/crontab), `Retrainer` (automated model retraining) |
| `src/ui/` | TUI (Textual) and CLI review interface | `ReviewApp`, `ReviewState` (thread-safe reactive), undo/redo (Ctrl+Z/Y), widgets and dialogs |
| `src/services/` | CLI-agnostic orchestration layer | `PipelineService`, `ExtractionService`, `AnalysisService`, `SuggestionService` |
| `src/models/` | Pydantic v2 data models | `Email`, `Corpus`, `AnalysisResults`, `Category`, `ContentCluster`, `RuleSet`, `CategorizationReport` |
| `src/learning/` | Feedback learning and active learning | `DecisionLogger` (JSONL), `PatternDetector` (90-day half-life decay), `EmailFeedbackStore` (corrections with temporal decay), `UncertaintySampler` (active learning), `AccuracyTracker` (per-category correction rate monitoring) |
| `src/exporters/` | Export formats | CSV (Excel-compatible), standalone HTML, Outlook rules, Gmail filters |
| `src/cache/` | Performance | `EmbeddingCache` with model metadata versioning (auto-invalidation) |
| `src/config/` | Configuration | Pydantic config models (incl. `ClassifierConfig`, `CategoryDefinition`), YAML loader with precedence |
| `src/preview/` | Dry-run estimators | Preview output for all commands |
| `src/utils/` | Shared utilities | `PathConfig`, `FileManager`, logging, progress (tqdm), validators, text processing |
| `src/exceptions.py` | Custom exception hierarchy | Recovery hints, typed errors (ExportError, ActionError, ClassificationError, ClassifierConnectionError, ClassifierResponseError, StorageError, DatabaseSchemaError) |
| `src/data/` | Data files | `templates.json` -- 18 category templates (editable without code changes) |

### Entry Point

`src/cli/` -- CLI package invoked via `python -m src.cli`. One module per command in `commands/`, shared parsers in `parsers.py`, output formatting in `formatters.py`.

### CLI Commands

| Command | Description |
|---------|-------------|
| `extract` | Extract emails from Hotmail/Gmail (supports `--source`, `--since-last`) |
| `analyze` | Analyze corpus (supports `--auto-clusters`, `--incremental`, `--cluster-viz`) |
| `suggest` | Generate category suggestions |
| `review` | Interactive review (TUI by default, `--no-tui` for CLI) |
| `pipeline` | Run complete workflow |
| `info` | Show corpus statistics |
| `config init` | Generate config template |
| `config show` | Display resolved configuration |
| `config validate` | Validate configuration with checks |
| `export` | Export to CSV, HTML, Outlook rules, or Gmail filters |
| `rules generate` | Auto-generate rules from approved categories |
| `rules test` | Dry-run rules against corpus with coverage report |
| `rules show` | Display current rules |
| `rules edit` | Edit rules interactively (TUI with live match preview) |
| `categorize` | Email-by-email categorization using rules |
| `categorize --report` | Generate coverage analysis report |
| `categorize --resolve` | Resolve multi-match conflicts (--strategy priority\|specificity\|historical) |
| `classify` | LLM-based email classification (--provider, --model, --categories YAML) |
| `classify --dry-run` | Preview classification without calling LLM |
| `migrate` | Import JSON/JSONL data into SQLite database (one-time, idempotent) |
| `train` | Fine-tune local SetFit model on accumulated corrections (--min-examples, --output) |
| `apply folders` | Create mailbox folders for categories |
| `apply move` | Move emails to categorized folders |
| `apply rules` | Deploy rules as server-side inbox rules/filters |
| `apply rollback` | Rollback recent actions (--since DATETIME) |
| `scheduler setup` | Register scheduled processing task |
| `scheduler run` | Manually trigger incremental processing |
| `scheduler status` | Show schedule status and last run |
| `scheduler disable` | Disable scheduled processing |
| `notifications show` | View notification history (--severity filter) |
| `notifications clear` | Clear notification history |
| `notifications test` | Send a test notification |

### Global CLI Flags

| Flag | Description |
|------|-------------|
| `--version` | Show version |
| `--verbose` | Enable debug logging |
| `--quiet` | Suppress INFO output |
| `--json` | JSON output for automation |
| `--config` | Custom config file path |

**Per-command flags:** `--dry-run` is available on most commands (extract, analyze, suggest, review, pipeline, categorize, classify, apply, migrate, train) but is not a global flag.

### Output Files

Default output: `~/data/outputs/` (configurable via `--output-dir` or config file)

| File | Description |
|------|-------------|
| `email_corpus.json` | Extracted email data (legacy JSON format) |
| `corpus_analysis_results.json` | Analysis from analyzers |
| `category_suggestions.json` | Generated categories |
| `category_suggestions_report.md` | Human-readable report |
| `approved_categories.json` | Final approved categories |
| `embeddings_cache.npz` | Cached embeddings (with .meta.json sidecar) |
| `cluster_visualization.png` | PCA scatter + silhouette chart (optional) |
| `rules.json` | Generated category rules |
| `categorization_report.json` | Email categorization results |
| `~/.email-analyzer/email_analyzer.db` | SQLite database (emails, classifications, corrections, logs) |
| `~/.email-analyzer/decisions.jsonl` | Review decision history (legacy, migrated to SQLite) |
| `~/.email-analyzer/action_log.jsonl` | Action audit trail (legacy, migrated to SQLite) |
| `~/.email-analyzer/notifications.jsonl` | Notification history |
| `~/.email-analyzer/scheduler_state.json` | Scheduler state (next/last run) |
| `~/.config/email-analyzer/config.yaml` | Global configuration (Linux/Mac; `%APPDATA%/email-analyzer/` on Windows) |
| `~/.email-analyzer/models/setfit/` | Saved SetFit model and metadata |

## Classification System

The system supports multiple classification strategies, from zero-config rules to fine-tuned local models:

### Classifier Hierarchy

| Classifier | Type | Cost | When to Use |
|------------|------|------|-------------|
| `RuleEngine` | Rule-based | Zero | High-precision pattern matching (sender, domain, keywords) |
| `LLMClassifier` | LLM (Ollama/OpenAI/Claude) | Free-$$ | Zero-shot or few-shot when no training data exists |
| `SetFitClassifier` | Fine-tuned local | Zero (after training) | When 8+ corrections per category have accumulated |
| `EnsembleClassifier` | Chained | Varies | Production: tries rules -> SetFit -> LLM in priority order |

### LLM Providers

- **Ollama** (default): Local LLM, zero cost, requires Ollama running at localhost:11434
- **OpenAI**: Cloud API, requires `OPENAI_API_KEY` env var
- **Claude**: Anthropic API, requires `ANTHROPIC_API_KEY` env var and `pip install -e ".[cloud]"`

### Prompt Injection Defense

`EmailSanitizer` strips injection patterns (role prefixes, instruction tags, code fences) from email content before LLM classification. All email text is wrapped in `<email_content>` XML delimiters to create a clear boundary between email content and system instructions.

### Ensemble Classification

`EnsembleClassifier` tries classifiers in priority order with per-classifier confidence thresholds. The first classifier exceeding its threshold wins. If none exceed their threshold, the highest-confidence result is used as fallback. Per-classifier usage statistics are tracked for monitoring and cost optimization.

## Storage

### SQLite Database

Primary storage is SQLite at `~/.email-analyzer/email_analyzer.db` with WAL mode for concurrent access:

| Table | Purpose |
|-------|---------|
| `emails` | Extracted email messages |
| `classifications` | Classification predictions (multiple per email for history) |
| `corrections` | User corrections for feedback learning |
| `sync_state` | Provider sync tokens for incremental extraction |
| `decision_log` | Review decision history (migrated from JSONL) |
| `action_log` | Action audit trail (migrated from JSONL) |
| `schema_version` | Schema migration version tracking |

### Embedding Store (sqlite-vec)

`EmbeddingStore` uses the `sqlite-vec` extension for vector similarity search. Stores email embeddings in a `vec0` virtual table and supports cosine distance-based nearest-neighbor queries for few-shot example retrieval.

### JSON to SQLite Migration

`python -m src.cli migrate` imports existing JSON/JSONL files into SQLite. Non-destructive (source files preserved), idempotent (safe to run multiple times), with upsert semantics for emails.

## Feedback Learning System

### Correction Flow

1. User corrects a classification (reclassifies email from category A to B)
2. `EmailFeedbackStore` records the correction with timestamp in SQLite
3. Temporal decay (exponential, ~70-day half-life) weights recent corrections higher
4. `UncertaintySampler` surfaces low-confidence and classifier-disagreement emails for review
5. `AccuracyTracker` monitors per-category correction rates over a rolling window
6. When correction rate exceeds threshold (default 20% in 7 days), `Retrainer` triggers retraining
7. `Retrainer` assembles training data from corrections and trains SetFit model

### Active Learning

`UncertaintySampler` implements two strategies:
- **Uncertainty sampling**: Returns the N least-confident classifications for human review
- **Disagreement sampling**: Finds emails where rule engine and LLM assign different categories

## Configuration

Configuration via YAML files with precedence: defaults < global < project < CLI args

```yaml
# ~/.config/email-analyzer/config.yaml or ./.email-analyzer.yaml
user_email: "user@example.com"
output_dir: "~/data/outputs"
analyze:
  num_clusters: 10
  max_embedding_text_length: 1500  # chars of body for embeddings (200-5000)
  auto_cluster_min: 3              # min clusters in auto mode
  auto_cluster_max: 25             # max clusters in auto mode
  thresholds:
    top_senders: 50
    top_domains: 30
    frequency_daily_threshold_days: 2.0
    representative_samples: 5
suggest:
  min_cluster_percentage: 5.0
  min_sender_count: 20
  thresholds:
    max_senders_for_categories: 20
    merge_name_similarity: 0.8
    merge_email_overlap: 0.7
classifier:
  provider: "ollama"                # ollama | openai | claude
  model_name: "qwen2.5:7b"         # LLM model name
  ollama_base_url: "http://localhost:11434"
  api_key_env_var: ""               # env var name for cloud API keys
  confidence_threshold: 0.6         # minimum confidence to accept result
  max_tokens: 200
  temperature: 0.0                  # deterministic classification
  categories:                       # category definitions for classification
    - name: "Newsletters"
      description: "Regular newsletter subscriptions and digests"
    - name: "Promotions"
      description: "Marketing emails, sales, and promotional offers"
learning:
  pattern_half_life_days: 90.0     # temporal decay for pattern detection
scheduler:
  enabled: false
  interval_hours: 24
  run_at: "02:00"                  # HH:MM format
  tasks: [extract, analyze, categorize, move]
monitoring:
  drift_threshold: 0.15
  volume_anomaly_stddev: 2.0
  alert_channels: [console, log]   # console, log, desktop
  check_interval_hours: 6
```

Generate template: `python -m src.cli config init`

## Constitutional Principles

This project follows strict principles defined in `.specify/memory/constitution.md`:

1. **TDD Mandatory** - Tests must be written before implementation (Red-Green-Refactor)
2. **Documentation-First** - Specs before code. Design docs in `specs/001-use-the-document/`
3. **Context7 Research** - All library usage must be researched via Context7 MCP before use
4. **Privacy** - Email data stays local only, never transmitted externally (exception: LLM API calls for classification when using cloud providers)
5. **Modular Components** - Each analyzer/classifier independently testable
6. **Error Resilience** - Continue processing on individual failures, log with context
7. **Progress Transparency** - Show progress for operations >10 seconds

## Key Design Decisions

- Python 3.10+ required (type hints, pattern matching)
- Pydantic v2 for all data validation
- sentence-transformers for semantic embeddings
- scikit-learn for clustering (KMeans, agglomerative)
- scipy for hierarchical clustering
- Textual for TUI interface
- SQLite with WAL mode for primary storage (migrated from JSON)
- sqlite-vec for vector similarity search (embedding store)
- Instructor for structured LLM output (Pydantic response models)
- OpenAI SDK as LLM transport layer (also used for Ollama via compatible endpoint)
- Anthropic SDK (optional) for Claude provider support
- SetFit for few-shot fine-tuned classification (optional `[ml]` extra -- not yet in pyproject.toml)
- Microsoft Graph API for Hotmail/Outlook.com (MSAL device code flow, no MCP required)
- Gmail API for Gmail extraction (OAuth 2.0)
- YAML configuration with PyYAML
- Jinja2 for HTML report templating

## Code Style

- **Ruff** enforces linting with rules: E, F, W, I (isort), N (naming), UP (pyupgrade), B (bugbear), A, C4, PIE, RET, SIM
- Line length: 100 chars (E501 ignored -- formatter handles wrapping)
- Target: Python 3.10 (`target-version = "py310"`)
- All data models use Pydantic v2 -- never use raw dicts for structured data
- ABCs for extensible components (`BaseExtractor`, `BaseAnalyzer`, `BaseClassifier`)
- Custom exception hierarchy in `src/exceptions.py` -- raise typed exceptions, not bare `Exception`

## Environment Setup

### M365/Hotmail (Microsoft Graph API)
- Uses MSAL device code flow -- no app registration needed for personal accounts
- On first run, `extract` will print a URL and code; open the URL in a browser and enter the code
- Token is cached locally by MSAL after first auth

### Gmail
- Requires a `credentials.json` from Google Cloud Console (OAuth 2.0 Client ID, Desktop app type)
- Place `credentials.json` in the working directory or configure path in config
- On first run, browser opens for OAuth consent; token is cached locally after auth

### LLM Classification (Ollama)
- Install Ollama from https://ollama.ai and pull a model: `ollama pull qwen2.5:7b`
- Default endpoint: `http://localhost:11434` (configurable via `classifier.ollama_base_url`)
- No API key needed for local Ollama

### LLM Classification (Cloud)
- **OpenAI**: Set `OPENAI_API_KEY` env var, configure `classifier.provider: openai`
- **Claude**: Install `pip install -e ".[cloud]"`, set `ANTHROPIC_API_KEY` env var, configure `classifier.provider: claude`

### Optional Dependencies
- `matplotlib` -- required only for `--cluster-viz` flag (not in core requirements)
- `scipy` -- included in requirements, needed for hierarchical clustering
- `anthropic` -- required only for Claude provider (`pip install -e ".[cloud]"`)
- `setfit` -- required only for `train` command and SetFit classifier (not yet in pyproject.toml optional extras)

## Gotchas

- **First-run model download**: `sentence-transformers` downloads the embedding model (~400MB) on first use of `analyze`. Expect a delay.
- **Auth is interactive**: Both M365 and Gmail auth flows require a browser on first run. Won't work in headless environments without pre-cached tokens.
- **Graph API rate limits**: Microsoft Graph has throttling; the extractor handles 429 responses with backoff, but very large mailboxes may take multiple runs with `--since-last`.
- **Checkpoint resumption**: If extraction is interrupted, re-run with the same flags -- `CheckpointManager` resumes from the last batch automatically.
- **Embedding cache invalidation**: Changing the sentence-transformers model version auto-invalidates the cache (`.meta.json` sidecar tracks model identity).
- **matplotlib import**: `--cluster-viz` will fail silently if matplotlib isn't installed. Install with `pip install matplotlib` if you need cluster visualization.
- **Ollama must be running**: The `classify` command with `provider=ollama` (default) requires Ollama to be running locally. If not running, you'll get a `ClassifierConnectionError` with a clear recovery hint.
- **LLM classification is not free**: Using `openai` or `claude` providers incurs API costs. Use `--dry-run` to preview before running.
- **SQLite migration is one-way**: After running `migrate`, new data goes to SQLite. The JSON files are preserved but no longer updated by the system.
- **SetFit requires training**: The `SetFitClassifier` must be trained with `train` command before it can classify. Minimum 8 examples per category by default.
- **Prompt injection sanitization**: The `EmailSanitizer` strips known injection patterns from email content. If legitimate emails contain role prefixes like "SYSTEM:" at the start of a line, they will be stripped. Check logs for `WARNING`-level sanitization messages.
