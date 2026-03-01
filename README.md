# Email Corpus Extraction and Analysis System

A Python-based system for extracting emails from Hotmail/Outlook.com and Gmail, analyzing patterns, generating AI-assisted category suggestions, classifying emails with LLM and fine-tuned models, and automating email organization with rule-based categorization, folder management, and scheduled processing. Learns from user corrections to improve over time.

## Quick Start

### Installation
```bash
# Clone and navigate to the project
git clone https://github.com/davistroy/email-corpus-analyzer.git
cd email-corpus-analyzer

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Optional: Install with Claude (Anthropic) support
pip install -e ".[cloud]"
```

### Basic Commands

**Default output location:** `~/data/outputs` (created automatically with secure permissions)

```bash
# Run complete pipeline from Hotmail (extract -> analyze -> suggest -> review)
python -m src.cli pipeline --user-email your.email@hotmail.com --auto-clusters

# From Gmail
python -m src.cli pipeline --user-email your.email@gmail.com --source gmail --auto-clusters

# From both accounts
python -m src.cli pipeline --user-email your.email@hotmail.com --source both --gmail-email your.email@gmail.com

# Or run individual steps:
python -m src.cli extract --user-email your.email@hotmail.com  # Extract emails
python -m src.cli analyze --auto-clusters                       # Analyze patterns
python -m src.cli analyze --auto-clusters --cluster-viz          # With cluster visualization
python -m src.cli suggest                                       # Generate categories
python -m src.cli review                                        # Review interactively (TUI)
python -m src.cli rules generate                                # Generate rules from categories
python -m src.cli rules test                                    # Test rules against corpus
python -m src.cli categorize                                    # Categorize emails using rules
python -m src.cli classify                                      # Classify with LLM (Ollama default)
python -m src.cli classify --provider openai --model gpt-4o-mini  # Classify with OpenAI
python -m src.cli migrate                                       # Migrate JSON data to SQLite
python -m src.cli train                                         # Train SetFit model on corrections
python -m src.cli apply folders --dry-run --source hotmail      # Create mailbox folders
python -m src.cli apply move --dry-run                          # Move emails to folders
python -m src.cli apply rules --dry-run --source gmail          # Deploy server-side rules
python -m src.cli export --format outlook-rules                 # Export Outlook rules
python -m src.cli export --format gmail-filters                 # Export Gmail filters
python -m src.cli scheduler setup                               # Set up automated processing
python -m src.cli notifications show                            # View notifications

# Get help
python -m src.cli --help
python -m src.cli <command> --help  # For specific command help
```

### Output Files

| File | Description |
|------|-------------|
| `email_corpus.json` | Extracted email data (legacy JSON format) |
| `corpus_analysis_results.json` | Analysis results (5 core analyzers) |
| `category_suggestions.json` | AI-generated category suggestions |
| `category_suggestions_report.md` | Human-readable report |
| `approved_categories.json` | Final approved categories |
| `rules.json` | Generated category rules |
| `categorization_report.json` | Email categorization results |
| `embeddings_cache.npz` | Cached embeddings for incremental analysis |
| `cluster_visualization.png` | Cluster scatter plot (with `--cluster-viz`) |
| `~/.email-analyzer/email_analyzer.db` | SQLite database (emails, classifications, corrections, logs) |
| `~/.email-analyzer/models/setfit/` | Saved SetFit model and metadata |

**For complete usage documentation, see [docs/USAGE.md](docs/USAGE.md) and [docs/QUICK_REFERENCE.md](docs/QUICK_REFERENCE.md)**

---

## Classification System

The system supports a progression of classification strategies:

| Classifier | Type | Cost | Description |
|------------|------|------|-------------|
| Rule Engine | Rule-based | Zero | High-precision pattern matching (sender, domain, keywords) |
| LLM Classifier | Zero/few-shot | Free-$$ | Ollama (local, free), OpenAI, or Claude via Instructor |
| SetFit Classifier | Fine-tuned local | Zero | Few-shot fine-tuning with 8+ examples per category |
| Ensemble Classifier | Chained | Varies | Tries rules -> SetFit -> LLM in priority order |

### LLM Classification

```bash
# Local (free) with Ollama
python -m src.cli classify

# Cloud providers
python -m src.cli classify --provider openai --model gpt-4o-mini
python -m src.cli classify --provider claude --model claude-sonnet-4-20250514

# Preview without calling LLM
python -m src.cli classify --dry-run
```

### Training Local Models

```bash
# Train SetFit model on accumulated user corrections
python -m src.cli train

# With lower minimum example threshold
python -m src.cli train --min-examples 4

# Save to custom path
python -m src.cli train --output ./models/my-model
```

### Security

Email content is sanitized before LLM classification to defend against prompt injection attacks. The `EmailSanitizer` strips role prefixes, instruction tags, and code fence delimiters, then wraps content in XML delimiters.

---

## Storage

### SQLite Database

Primary storage is SQLite at `~/.email-analyzer/email_analyzer.db` with WAL mode:

- **emails**: Extracted email messages
- **classifications**: Classification predictions (full history)
- **corrections**: User corrections for feedback learning
- **sync_state**: Provider sync tokens for incremental extraction
- **decision_log**: Review decision history
- **action_log**: Action audit trail

### Migration from JSON

```bash
# One-time migration of existing JSON data to SQLite
python -m src.cli migrate

# Preview without writing
python -m src.cli migrate --dry-run
```

Migration is non-destructive (source files preserved) and idempotent (safe to run multiple times).

---

## Feedback Learning

The system learns from user corrections:

1. User corrects a misclassification
2. Correction stored with temporal decay weighting (~70-day half-life)
3. Uncertain and disagreement emails are surfaced for review (active learning)
4. Per-category accuracy is tracked; retraining triggers when correction rate exceeds threshold
5. SetFit model is retrained on accumulated corrections

---

## Configuration

### Configuration File Example

Place a `.email-analyzer.yaml` file in your project directory or `~/.email-analyzer/config.yaml` for global settings. Project-level config overrides global; CLI arguments override both.

```yaml
# Email Analyzer Configuration
# Place at ~/.email-analyzer/config.yaml (global) or ./.email-analyzer.yaml (project)

# Global Settings
user_email: "your@email.com"
output_dir: "~/data/outputs"
verbose: false

# Extraction Settings
extract:
  batch_size: 500           # Emails per API batch (1-100000)
  checkpoint_interval: 100  # Save progress every N emails
  source: "hotmail"         # hotmail | gmail | both

# Analysis Settings
analyze:
  num_clusters: 10                      # Fixed cluster count (ignored if using --auto-clusters)
  max_embedding_text_length: 1500       # Characters of body for embeddings (200-5000)
  auto_cluster_min: 3                   # Min clusters in auto mode
  auto_cluster_max: 25                  # Max clusters in auto mode
  thresholds:
    top_senders: 50                     # Number of top senders to extract
    top_domains: 30                     # Number of top domains to extract
    service_keywords:
      - "noreply"
      - "no-reply"
      - "notification"
    marketing_keywords:
      - "unsubscribe"
      - "promotional"
      - "discount"
    work_keywords:
      - "meeting"
      - "project"
      - "team"
    frequency_daily_threshold_days: 2.0 # Classification threshold for daily senders
    min_emails_for_frequency: 10        # Min emails required for frequency classification

# Suggestion Settings
suggest:
  min_cluster_percentage: 5.0  # Minimum cluster size (% of corpus) to become a category
  min_sender_count: 20         # Minimum emails for sender-based categories
  thresholds:
    max_senders_for_categories: 20  # Max top senders to consider
    merge_name_similarity: 0.8      # Threshold for merging similar category names
    merge_email_overlap: 0.7        # Threshold for merging categories by email overlap

# Classifier Settings
classifier:
  provider: "ollama"                    # ollama | openai | claude
  model_name: "qwen2.5:7b"             # LLM model name
  ollama_base_url: "http://localhost:11434"
  api_key_env_var: ""                   # Env var name for cloud API keys (e.g., OPENAI_API_KEY)
  confidence_threshold: 0.6            # Minimum confidence to accept LLM result
  max_tokens: 200
  temperature: 0.0                      # Deterministic classification
  categories:                           # Category definitions
    - name: "Newsletters"
      description: "Regular newsletter subscriptions and digests"
    - name: "Promotions"
      description: "Marketing emails, sales, and promotional offers"

# Learning Settings
learning:
  pattern_half_life_days: 90.0  # Temporal decay for pattern confidence (in days)

# Scheduler Settings
scheduler:
  enabled: false
  interval_hours: 24
  run_at: "02:00"                  # HH:MM format
  tasks: [extract, analyze, categorize]

# Monitoring Settings
monitoring:
  drift_threshold: 0.15
  volume_anomaly_stddev: 2.0
  alert_channels: [console, log]   # console, log, desktop
  check_interval_hours: 6
```

Validate your configuration with:
```bash
python -m src.cli config validate
python -m src.cli config show  # Display resolved configuration
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| **Extract fails with authentication error** | Re-run the extract command and follow the device code flow prompt. Browser will open automatically for login. |
| **Analysis takes too long** | Reduce `max_embedding_text_length` to 1000-1200 or use `--auto-clusters` instead of fixed `num_clusters`. |
| **No categories suggested** | Lower `min_cluster_percentage` in config (try 2-3%), or ensure corpus has sufficient emails (100+). |
| **TUI doesn't work or crashes** | Use `--no-tui` flag to fall back to CLI review mode: `python -m src.cli review --no-tui` |
| **Config not being applied** | Run `python -m src.cli config validate` to check for errors. Ensure file is at `~/.email-analyzer/config.yaml` or `./.email-analyzer.yaml` (project root). |
| **Gmail authentication fails** | Ensure OAuth credentials from Google Cloud Console are set up correctly. See [Setup Guide](docs/M365_SETUP.md). |
| **Classify fails with ConnectionError** | Ensure Ollama is running (`ollama serve`) or use a cloud provider (`--provider openai`). |
| **Train says insufficient examples** | Accumulate at least 8 corrections per category before training. Lower threshold with `--min-examples 4`. |
| **Migrate reports warnings** | Non-fatal -- some records may be skipped if malformed. Check the migration summary for details. |

---

## Performance

### Baseline Metrics

- **Extraction**: 100-500 emails/min depending on API rate limits. Larger batches (higher `batch_size`) improve throughput but increase memory usage.
- **Analysis**: ~30 seconds for 1000 emails with semantic embeddings. Scales linearly with corpus size. Can be optimized by reducing `max_embedding_text_length`.
- **Auto-clustering**: Adds ~10-30 seconds for optimal K search via elbow/silhouette methods.
- **Suggestion Generation**: <1 second for 1000+ categories (template matching + confidence scoring).
- **LLM Classification**: ~1-5 seconds per email (Ollama local), ~0.5-2 seconds per email (cloud).
- **SetFit Classification**: ~10-50ms per email (after training).
- **Review (TUI)**: Interactive, real-time; supports bulk operations and filtering.

### Optimization Tips

1. Reduce `max_embedding_text_length` from 1500 to 1000 for faster analysis (minimal accuracy loss)
2. Use `--auto-clusters` instead of fixed `num_clusters` for smarter bucketing
3. Increase `checkpoint_interval` if network is stable (reduces I/O, speeds extraction)
4. Run analysis on a machine with 8+ GB RAM for large corpora (5000+ emails)
5. Use the ensemble classifier to minimize LLM API calls -- rules and SetFit handle most emails at zero cost

---

## Testing & Quality

The project maintains high code quality with comprehensive test coverage:

```bash
# Run all tests (4252 tests)
pytest

# Run specific test suite
pytest tests/unit/                    # Unit tests only
pytest tests/contract/                # Contract tests only
pytest -k "test_name"                 # Run specific test by name

# Generate HTML coverage report
pytest --cov=src --cov-report=html

# Linting
ruff check src/
ruff check src/ --fix           # Auto-fix style issues
```

---

## Architecture

### Technology Stack
- **Python**: 3.10+ (type hints, pattern matching)
- **Text Embeddings**: sentence-transformers >= 2.0.0
- **Clustering**: scikit-learn >= 1.7.1
- **HTML Parsing**: BeautifulSoup4 >= 4.12.0 + lxml
- **Data Validation**: Pydantic >= 2.0.0
- **TUI Framework**: Textual >= 0.50.0
- **Progress Tracking**: tqdm >= 4.66.0
- **LLM Integration**: Instructor >= 1.0.0 + OpenAI SDK >= 1.0.0
- **Storage**: SQLite (stdlib) + sqlite-vec >= 0.1.0
- **Fine-tuning**: SetFit (optional)
- **Cloud LLM**: Anthropic SDK (optional, `[cloud]` extra)
- **Testing**: pytest >= 7.4.0

### Project Structure

```
email-corpus-analyzer/
├── src/
│   ├── models/              # Pydantic data models
│   ├── extractors/          # Email extraction (Hotmail via Graph API, Gmail via Gmail API)
│   ├── analyzers/           # 5 core + 2 optional analysis modules
│   ├── generators/          # Category suggestion generation
│   ├── rules/               # Rule engine, builder, tester
│   ├── categorizer/         # Email-by-email categorization, conflict resolution
│   ├── classifiers/         # BaseClassifier ABC, LLM, SetFit, Ensemble, Sanitizer
│   ├── storage/             # SQLite database, EmailStore, EmbeddingStore, migration
│   ├── actions/             # Folder management, email moving, rule deployment
│   ├── automation/          # Scheduler, change detection, notifications, retrainer
│   ├── services/            # Service layer (extraction, analysis, suggestion orchestration)
│   ├── cli/                 # CLI package (commands, parsers, formatters)
│   ├── ui/                  # Interactive review (CLI + TUI with undo/redo)
│   ├── cache/               # Embedding cache for incremental analysis
│   ├── config/              # YAML configuration system (incl. ClassifierConfig)
│   ├── data/                # External data files (templates.json)
│   ├── exporters/           # CSV, HTML, Outlook rules, Gmail filters export
│   ├── learning/            # Feedback learning, accuracy tracking, uncertainty sampling
│   ├── preview/             # Dry-run estimators
│   └── utils/               # Logging, file management, paths, constants, validators
├── tests/
│   ├── contract/            # Contract tests
│   ├── integration/         # Integration tests
│   └── unit/                # Unit tests (4252 tests)
├── docs/                    # Documentation
├── .specify/                # Constitution and templates
├── specs/                   # Design specifications
│   └── 001-use-the-document/
├── requirements.txt
└── pyproject.toml
```

## Design Artifacts

All design documents located in `specs/001-use-the-document/`:

1. **spec.md** - 51 functional requirements, 4 acceptance scenarios
2. **plan.md** - Implementation plan with constitutional compliance
3. **research.md** - Context7 research for all libraries
4. **data-model.md** - 7 entities with Pydantic schemas
5. **contracts/** - 3 contract files defining interfaces
6. **quickstart.md** - 5 manual validation scenarios
7. **tasks.md** - 41 tasks with dependencies

## Constitutional Principles

This project follows the **Email Corpus Analysis Constitution v1.0.0** (`.specify/memory/constitution.md`):

1. **Test-Driven Development** - Tests before implementation
2. **Documentation-First** - All design docs created before coding
3. **Context7-Mandatory** - All libraries researched via Context7 MCP
4. **Privacy & Data Security** - Local-only storage, secure permissions (LLM API calls to cloud providers are the exception when configured)
5. **Modular Components** - Independent, testable modules
6. **Error Resilience** - Debug logging, graceful degradation
7. **Performance Transparency** - Progress indicators for long operations

## Development

### Prerequisites
- Python 3.10 or higher
- For Hotmail: No setup needed (authenticates via device code on first run)
- For Gmail: OAuth credentials from Google Cloud Console (see [Setup Guide](docs/M365_SETUP.md))
- For LLM classification: Ollama installed locally, or OpenAI/Anthropic API key

### Testing & Quality

```bash
# Run tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Linting
ruff check src/
```

## Documentation

- [Usage Guide](docs/USAGE.md)
- [Quick Reference](docs/QUICK_REFERENCE.md)
- [Email Source Setup](docs/M365_SETUP.md)
- [Output Configuration](docs/OUTPUT_CONFIGURATION.md)
- [Extraction Architecture](docs/INTEGRATION.md)

## License

Internal project - Email Corpus Analysis System
