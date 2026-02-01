# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Test Commands

```bash
# Install dependencies
pip install -r requirements.txt
pip install -e ".[dev]"  # Install with dev dependencies

# Run tests (1403 tests, 83% coverage)
pytest                                  # All tests with coverage
pytest tests/unit/                      # Unit tests only
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
python -m src.cli suggest
python -m src.cli review
python -m src.cli info
python -m src.cli config show
python -m src.cli export --format html
python -m src.cli export --format outlook-rules
python -m src.cli export --format gmail-filters
python -m src.cli config validate
```

## Architecture

This system extracts emails from M365/Hotmail, analyzes patterns, and generates category suggestions through a four-stage pipeline:

```
Extract → Analyze → Suggest → Review → Export
```

### Core Pipeline Modules

- **`src/extractors/`** - Email extraction from M365/Hotmail and Gmail:
  - `graph_api_client.py` - Microsoft Graph API client with MSAL device code auth (works with personal Hotmail/Outlook.com accounts)
  - `gmail_client.py` - Gmail API client with OAuth 2.0 authentication
  - `gmail_extractor.py` - Gmail extractor with full/incremental extraction and checkpointing
  - `m365_extractor.py` - M365/Hotmail extractor with batched extraction and checkpointing
  - `html_parser.py` - HTML to plain text conversion for email bodies
  - `checkpoint_manager.py` - Checkpoint/resume for interrupted extractions
  - Supports `--source hotmail|gmail|both` flag for multi-source extraction

- **`src/analyzers/`** - 5 core + 2 optional analyzers inheriting from `BaseAnalyzer` ABC:
  - `base.py` - Abstract base class for all analyzers
  - `sender_analyzer.py` - Sender frequency, domain patterns
  - `subject_analyzer.py` - Subject line patterns, prefixes
  - `semantic_analyzer.py` - Content clustering via sentence-transformers
  - `temporal_analyzer.py` - Time-based patterns
  - `volume_analyzer.py` - Statistical metrics
  - `hierarchical_analyzer.py` - Hierarchical clustering with scipy
  - `cluster_optimizer.py` - Elbow/Silhouette methods for optimal k
  - `thread_analyzer.py` - Email thread/conversation grouping

- **`src/generators/`** - Category suggestion from analysis results:
  - `template_matcher.py` - Matches 18 predefined templates
  - `confidence_scorer.py` - Enhanced multi-factor confidence scoring
  - `name_generator.py` - TF-IDF based name generation
  - `category_generator.py` - Main generator with learning integration

- **`src/ui/`** - User interface components:
  - `category_review.py` - CLI review with learning support
  - `tui/` - Textual-based TUI for interactive review with bulk operations and search/filter

- **`src/services/`** - Service layer (CLI-agnostic orchestration):
  - `extraction_service.py` - M365 email extraction orchestration
  - `analysis_service.py` - Runs all analyzers with progress callbacks
  - `suggestion_service.py` - Category generation orchestration
  - `pipeline_service.py` - Full workflow orchestration

- **`src/exceptions.py`** - Custom exception hierarchy with recovery hints

- **`src/learning/`** - Feedback learning system:
  - `decision_logger.py` - Logs review decisions to JSONL
  - `pattern_detector.py` - Detects recurring patterns

- **`src/exporters/`** - Export formats:
  - `csv_exporter.py` - CSV export with Excel compatibility
  - `html_exporter.py` - Standalone HTML reports
  - `rule_exporter.py` - Outlook and Gmail rule/filter export

- **`src/cache/`** - Performance optimization:
  - `embedding_cache.py` - Caches embeddings for incremental analysis

- **`src/config/`** - Configuration system:
  - `models.py` - Pydantic config models
  - `loader.py` - YAML config loading with precedence

- **`src/preview/`** - Dry-run estimators for all commands

### Data Models

All models in `src/models/` use Pydantic v2. Key models:
- `Email` - Single email with metadata and content
- `Corpus` - Collection of emails with metadata (includes extraction tracking)
- `AnalysisResults` - Combined output from all analyzers
- `Category` - Suggested category with confidence score, hierarchy support
- `CategoryTemplate` - Predefined category patterns (18 templates)
- `ContentCluster` - Cluster with quality metrics (silhouette, cohesion)

### Entry Points

- `src/cli.py` - Primary CLI entry point (`python -m src.cli`)
- `src/main.py` - Alternative entry point with `EmailProcessorCLI` class

### CLI Commands

| Command | Description |
|---------|-------------|
| `extract` | Extract emails from Hotmail/Gmail (supports `--source`, `--since-last`) |
| `analyze` | Analyze corpus (supports `--auto-clusters`, `--incremental`) |
| `suggest` | Generate category suggestions |
| `review` | Interactive review (TUI by default, `--no-tui` for CLI) |
| `pipeline` | Run complete workflow |
| `info` | Show corpus statistics |
| `config init` | Generate config template |
| `config show` | Display resolved configuration |
| `config validate` | Validate configuration with checks |
| `export` | Export to CSV, HTML, Outlook rules, or Gmail filters |

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
| `embeddings_cache.npz` | Cached embeddings |
| `~/.email-analyzer/decisions.jsonl` | Review decision history |
| `~/.email-analyzer/config.yaml` | Global configuration |

## Configuration

Configuration via YAML files with precedence: defaults < global < project < CLI args

```yaml
# ~/.email-analyzer/config.yaml or ./.email-analyzer.yaml
user_email: "user@example.com"
output_dir: "~/data/outputs"
analyze:
  num_clusters: 10
suggest:
  min_cluster_percentage: 5.0
  min_sender_count: 20
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
