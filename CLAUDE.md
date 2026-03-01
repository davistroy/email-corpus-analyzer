# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Test Commands

```bash
# Install dependencies
pip install -r requirements.txt
pip install -e ".[dev]"  # Install with dev dependencies

# Run tests (3463 tests, 88% coverage)
pytest                                  # All 3463 tests with coverage
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

This system extracts emails from M365/Hotmail and Gmail, analyzes patterns, generates category suggestions, applies rules for email-by-email categorization, and automates email organization through a multi-stage pipeline:

```
Extract → Analyze → Suggest → Review → Rules → Categorize → Apply
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
| `src/actions/` | Email action execution | `FolderManager`, `EmailMover` (batch + rollback), `RuleDeployer` (server-side rules), `ActionLogger` (JSONL audit) |
| `src/automation/` | Scheduled processing and monitoring | `IncrementalProcessor`, `ChangeDetector` (drift/anomaly), `Scheduler` (Win Task Scheduler/crontab) |
| `src/ui/` | TUI (Textual) and CLI review interface | `ReviewApp`, `ReviewState` (thread-safe reactive), undo/redo (Ctrl+Z/Y), widgets and dialogs |
| `src/services/` | CLI-agnostic orchestration layer | `PipelineService`, `ExtractionService`, `AnalysisService`, `SuggestionService` |
| `src/models/` | Pydantic v2 data models | `Email`, `Corpus`, `AnalysisResults`, `Category`, `ContentCluster`, `RuleSet`, `CategorizationReport` |
| `src/learning/` | Feedback learning | `DecisionLogger` (JSONL), `PatternDetector` (90-day half-life decay) |
| `src/exporters/` | Export formats | CSV (Excel-compatible), standalone HTML, Outlook rules, Gmail filters |
| `src/cache/` | Performance | `EmbeddingCache` with model metadata versioning (auto-invalidation) |
| `src/config/` | Configuration | Pydantic config models, YAML loader with precedence |
| `src/preview/` | Dry-run estimators | Preview output for all commands |
| `src/utils/` | Shared utilities | `PathConfig`, `FileManager`, logging, progress (tqdm), validators, text processing |
| `src/exceptions.py` | Custom exception hierarchy | Recovery hints, typed errors (ExportError, ActionError, FolderActionError) |
| `src/data/` | Data files | `templates.json` — 18 category templates (editable without code changes) |

### Entry Point

`src/cli/` — CLI package invoked via `python -m src.cli`. One module per command in `commands/`, shared parsers in `parsers.py`, output formatting in `formatters.py`.

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
| `categorize` | Email-by-email categorization using rules |
| `categorize --report` | Generate coverage analysis report |
| `categorize --resolve` | Resolve multi-match conflicts (--strategy priority\|specificity\|historical) |
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
| `--dry-run` | Preview without executing |

### Output Files

Default output: `~/data/outputs/` (configurable via `--output-dir` or config file)

| File | Description |
|------|-------------|
| `email_corpus.json` | Extracted email data |
| `corpus_analysis_results.json` | Analysis from analyzers |
| `category_suggestions.json` | Generated categories |
| `category_suggestions_report.md` | Human-readable report |
| `approved_categories.json` | Final approved categories |
| `embeddings_cache.npz` | Cached embeddings (with .meta.json sidecar) |
| `cluster_visualization.png` | PCA scatter + silhouette chart (optional) |
| `rules.json` | Generated category rules |
| `categorization_report.json` | Email categorization results |
| `~/.email-analyzer/decisions.jsonl` | Review decision history |
| `~/.email-analyzer/action_log.jsonl` | Action audit trail (moves, deploys, rollbacks) |
| `~/.email-analyzer/notifications.jsonl` | Notification history |
| `~/.email-analyzer/scheduler_state.json` | Scheduler state (next/last run) |
| `~/.email-analyzer/config.yaml` | Global configuration |

## Configuration

Configuration via YAML files with precedence: defaults < global < project < CLI args

```yaml
# ~/.email-analyzer/config.yaml or ./.email-analyzer.yaml
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
learning:
  pattern_half_life_days: 90.0     # temporal decay for pattern detection
scheduler:
  enabled: false
  interval_hours: 24
  run_at: "02:00"                  # HH:MM format
  tasks: [extract, analyze, categorize]
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
4. **Privacy** - Email data stays local only, never transmitted externally
5. **Modular Components** - Each analyzer independently testable
6. **Error Resilience** - Continue processing on individual failures, log with context
7. **Progress Transparency** - Show progress for operations >10 seconds

## Key Design Decisions

- Python 3.10+ required (type hints, pattern matching)
- Pydantic v2 for all data validation
- sentence-transformers for semantic embeddings
- scikit-learn for clustering (KMeans, agglomerative)
- scipy for hierarchical clustering
- Textual for TUI interface
- Local JSON storage (no database)
- Microsoft Graph API for Hotmail/Outlook.com (MSAL device code flow, no MCP required)
- Gmail API for Gmail extraction (OAuth 2.0)
- YAML configuration with PyYAML
- Jinja2 for HTML report templating

## Code Style

- **Ruff** enforces linting with rules: E, F, W, I (isort), N (naming), UP (pyupgrade), B (bugbear), A, C4, PIE, RET, SIM
- Line length: 100 chars (E501 ignored — formatter handles wrapping)
- Target: Python 3.10 (`target-version = "py310"`)
- All data models use Pydantic v2 — never use raw dicts for structured data
- ABCs for extensible components (`BaseExtractor`, `BaseAnalyzer`)
- Custom exception hierarchy in `src/exceptions.py` — raise typed exceptions, not bare `Exception`

## Environment Setup

### M365/Hotmail (Microsoft Graph API)
- Uses MSAL device code flow — no app registration needed for personal accounts
- On first run, `extract` will print a URL and code; open the URL in a browser and enter the code
- Token is cached locally by MSAL after first auth

### Gmail
- Requires a `credentials.json` from Google Cloud Console (OAuth 2.0 Client ID, Desktop app type)
- Place `credentials.json` in the working directory or configure path in config
- On first run, browser opens for OAuth consent; token is cached locally after auth

### Optional Dependencies
- `matplotlib` — required only for `--cluster-viz` flag (not in core requirements)
- `scipy` — included in requirements, needed for hierarchical clustering

## Gotchas

- **First-run model download**: `sentence-transformers` downloads the embedding model (~400MB) on first use of `analyze`. Expect a delay.
- **Auth is interactive**: Both M365 and Gmail auth flows require a browser on first run. Won't work in headless environments without pre-cached tokens.
- **Graph API rate limits**: Microsoft Graph has throttling; the extractor handles 429 responses with backoff, but very large mailboxes may take multiple runs with `--since-last`.
- **Checkpoint resumption**: If extraction is interrupted, re-run with the same flags — `CheckpointManager` resumes from the last batch automatically.
- **Embedding cache invalidation**: Changing the sentence-transformers model version auto-invalidates the cache (`.meta.json` sidecar tracks model identity).
- **matplotlib import**: `--cluster-viz` will fail silently if matplotlib isn't installed. Install with `pip install matplotlib` if you need cluster visualization.
