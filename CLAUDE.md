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
pytest tests/unit/test_html_parser.py   # Single test file
pytest -k "test_name"                   # Run specific test by name
pytest --cov=src --cov-report=html      # Generate HTML coverage report

# Linting
ruff check src/
ruff check src/ --fix           # Auto-fix issues

# Run CLI commands
python -m src.cli --help
python -m src.cli --version
python -m src.cli pipeline --user-email user@hotmail.com
python -m src.cli pipeline --user-email user@gmail.com --source gmail
python -m src.cli pipeline --user-email user@hotmail.com --source both --gmail-email user@gmail.com
python -m src.cli extract --user-email user@hotmail.com
python -m src.cli extract --user-email user@gmail.com --source gmail
python -m src.cli analyze --auto-clusters
python -m src.cli analyze --auto-clusters --cluster-viz
python -m src.cli suggest
python -m src.cli review
python -m src.cli info
python -m src.cli config show
python -m src.cli export --format html
python -m src.cli export --format outlook-rules
python -m src.cli export --format gmail-filters
python -m src.cli config validate
python -m src.cli rules generate
python -m src.cli rules test
python -m src.cli rules show
python -m src.cli categorize
python -m src.cli categorize --report
python -m src.cli categorize --resolve --strategy priority
python -m src.cli apply folders --dry-run --source hotmail
python -m src.cli apply move --dry-run
python -m src.cli apply rules --dry-run --source gmail
python -m src.cli apply rollback --since 2026-01-01
python -m src.cli scheduler setup
python -m src.cli scheduler status
python -m src.cli notifications show
python -m src.cli notifications test
```

## Architecture

This system extracts emails from M365/Hotmail and Gmail, analyzes patterns, generates category suggestions, applies rules for email-by-email categorization, and automates email organization through a multi-stage pipeline:

```
Extract → Analyze → Suggest → Review → Rules → Categorize → Apply
                                                    ↓
                                          Scheduler → Monitor → Notify
```

### Core Pipeline Modules

- **`src/extractors/`** - Email extraction from M365/Hotmail and Gmail:
  - `base_extractor.py` - BaseExtractor ABC with shared batch loop, checkpoint, error handling
  - `graph_api_client.py` - Microsoft Graph API client with MSAL device code auth (supports server-side date filtering)
  - `gmail_client.py` - Gmail API client with OAuth 2.0 authentication (recursive MIME extraction)
  - `gmail_extractor.py` - Gmail extractor inheriting BaseExtractor
  - `m365_extractor.py` - M365/Hotmail extractor inheriting BaseExtractor
  - `html_parser.py` - HTML to plain text conversion for email bodies
  - `checkpoint_manager.py` - Compact v2 checkpoint format (metadata-only, <1KB)
  - Supports `--source hotmail|gmail|both` flag for multi-source extraction

- **`src/analyzers/`** - 5 core + 2 optional analyzers inheriting from `BaseAnalyzer` ABC:
  - `base.py` - Abstract base class for all analyzers
  - `sender_analyzer.py` - Sender frequency, domain patterns
  - `subject_analyzer.py` - Subject line patterns, prefixes
  - `semantic_analyzer.py` - Content clustering via sentence-transformers
  - `temporal_analyzer.py` - Time-based patterns
  - `volume_analyzer.py` - Statistical metrics
  - `hierarchical_analyzer.py` - Hierarchical clustering with scipy
  - `cluster_optimizer.py` - Elbow/Silhouette methods with sigmoid scoring and corpus-scaled max_k
  - `thread_analyzer.py` - Email thread/conversation grouping with subject-based fallback

- **`src/generators/`** - Category suggestion from analysis results:
  - `template_matcher.py` - Matches 18 predefined templates (word-boundary regex, no false positives)
  - `confidence_scorer.py` - Logarithmic volume scoring, configurable weights
  - `name_generator.py` - TF-IDF based name generation
  - `category_generator.py` - Main generator with learning integration

- **`src/rules/`** - Category rule system:
  - `engine.py` - RuleEngine evaluates conditions against emails (AND/OR logic, 8 operators, short-circuit)
  - `builder.py` - RuleBuilder auto-generates rules from approved categories and analysis results
  - `tester.py` - RuleTester dry-runs rules against corpus (coverage, conflicts, confusion matrix)

- **`src/categorizer/`** - Email-by-email categorization:
  - `categorizer.py` - EmailCategorizer assigns primary/secondary categories via rules
  - `conflict_resolver.py` - ConflictResolver with priority/specificity/historical strategies
  - `coverage_reporter.py` - CoverageReporter detects uncategorized patterns, generates recommendations

- **`src/actions/`** - Email action execution:
  - `folder_manager.py` - FolderManager creates mailbox folders (M365 Graph API / Gmail Labels)
  - `email_mover.py` - EmailMover batch-moves emails with rate limiting and rollback
  - `rule_deployer.py` - RuleDeployer converts rules to server-side inbox rules/filters
  - `action_logger.py` - ActionLogger append-only JSONL audit trail with rollback replay

- **`src/automation/`** - Automated processing and monitoring:
  - `incremental.py` - IncrementalProcessor extracts new emails, merges, reassigns clusters
  - `change_detector.py` - ChangeDetector for drift scoring, volume anomalies, emerging topics
  - `scheduler.py` - Scheduler with Windows Task Scheduler / crontab integration
  - `notifications.py` - NotificationManager with console/log/desktop alert channels

- **`src/ui/`** - User interface components:
  - `category_review.py` - CLI review with learning support
  - `tui/app.py` - Main ReviewApp (Textual-based TUI)
  - `tui/state.py` - ReviewState centralized state management (thread-safe, reactive)
  - `tui/utils.py` - Shared utilities (format_confidence_bar, truncation constants)
  - `tui/commands.py` - Command definitions and key bindings
  - `tui/commands_undo.py` - Command pattern undo/redo (Ctrl+Z/Y, 50-op stack)
  - `tui/theme.py` - Theme colors, confidence colors, high-contrast mode, APP_CSS
  - `tui/widgets/` - CategoryTable, DetailPanel, ActionBar, SearchInput, StatsPanel, ProgressBar
  - `tui/dialogs/` - BulkActionDialog, MergeDialog, RenameDialog, RuleEditorDialog

- **`src/services/`** - Service layer (CLI-agnostic orchestration):
  - `extraction_service.py` - Multi-source extraction (hotmail/gmail/both) with corpus merge
  - `analysis_service.py` - Runs all analyzers with progress callbacks
  - `suggestion_service.py` - Category generation orchestration
  - `pipeline_service.py` - Full workflow orchestration

- **`src/exceptions.py`** - Custom exception hierarchy with recovery hints (includes ExportError, ActionError, FolderActionError)

- **`src/learning/`** - Feedback learning system:
  - `decision_logger.py` - Logs review decisions to JSONL
  - `pattern_detector.py` - Detects recurring patterns with temporal decay (90-day half-life)

- **`src/exporters/`** - Export formats:
  - `csv_exporter.py` - CSV export with Excel compatibility
  - `html_exporter.py` - Standalone HTML reports
  - `rule_exporter.py` - Outlook and Gmail rule/filter export

- **`src/cache/`** - Performance optimization:
  - `embedding_cache.py` - Caches embeddings with model metadata versioning (auto-invalidation)

- **`src/config/`** - Configuration system:
  - `models.py` - Pydantic config models (includes SchedulerConfig, MonitoringConfig)
  - `loader.py` - YAML config loading with precedence

- **`src/preview/`** - Dry-run estimators for all commands

- **`src/utils/`** - Shared utilities:
  - `logger.py` - Debug-level logging with console + file handlers
  - `file_manager.py` - File I/O with secure permissions
  - `paths.py` - Centralized PathConfig for output directory resolution
  - `constants.py` - Named constants (extraction, scoring parameters)
  - `progress.py` - Progress tracking with tqdm integration
  - `text.py` - Centralized word lists (stop words, generic/action words)
  - `validators.py` - Cross-entity validation (Corpus, Email, Category)

### Data Models

All models in `src/models/` use Pydantic v2. Key models:
- `Email` - Single email with metadata and content
- `Corpus` - Collection of emails with metadata (includes extraction tracking)
- `AnalysisResults` - Combined output from all analyzers
- `Category` - Suggested category with confidence score, hierarchy support
- `CategoryTemplate` - Predefined category patterns (18 templates)
- `ContentCluster` - Cluster with quality metrics (silhouette, cohesion, interpretation labels)
- `RuleCondition`, `CategoryRule`, `RuleAction`, `RuleSet` - Rule system models
- `EmailCategorization`, `CategorizationReport`, `CategoryAssignment` - Categorization models

### Entry Points

- `src/cli/` - CLI package (`python -m src.cli`)
  - `__init__.py` - Main entry, parser creation, command dispatch
  - `parsers.py` - Shared argument groups, data-driven config mapping
  - `formatters.py` - Output helpers, cluster visualization
  - `commands/` - One module per command (extract, analyze, suggest, review, pipeline, config, info, export, rules, categorize, apply, scheduler, notifications)

- **`src/data/`** - Data files:
  - `templates.json` - 18 category templates (editable without code changes)

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
