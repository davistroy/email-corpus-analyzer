## Learning Capture — Every Session

After any non-trivial finding (extraction failure, auth flow issue, rate limit, classifier behavior surprise, SQLite/embedding behavior, async concurrency issue, Windows/environment quirk, multi-attempt fix):
1. Update `CLAUDE.md` — add/update bullet in relevant section
2. Update memory file — `C:\Users\Troy Davis\.claude\projects\C--Users-Troy-Davis-dev-personal-email-corpus-analyzer\memory\`
3. Update `MEMORY.md` — concise bullet + link to topic file

| File | Purpose |
|------|---------|
| `CLAUDE.md` | Operational rules, always enforced |
| `memory/MEMORY.md` | Concise index, survives compaction |
| `memory/pipeline-learnings.md` | Pipeline stages, extraction, clustering |
| `memory/classifier-learnings.md` | LLM, SetFit, ensemble classifier behavior |
| `memory/storage-learnings.md` | SQLite, sqlite-vec, migration issues |
| `memory/auth-learnings.md` | M365/Gmail OAuth, MSAL, token caching |

### Verified Operational Rules

*(None yet — add as discovered)*

---

# CLAUDE.md

## Build & Test Commands

```bash
pip install -r requirements.txt
pip install -e ".[dev]"
pip install -e ".[cloud]"       # For Claude support
pip install -e ".[dev,cloud]"

pytest                          # All 4252 tests with coverage
pytest tests/unit/
pytest tests/contract/
pytest tests/integration/
pytest tests/unit/test_html_parser.py
pytest -k "test_name"
pytest --cov=src --cov-report=html

ruff check src/
ruff check src/ --fix

python -m src.cli --help
python -m src.cli pipeline --user-email user@hotmail.com
python -m src.cli pipeline --user-email user@gmail.com --source gmail
```

## Architecture

Extract → Analyze → Suggest → Review → Rules → Categorize → Apply → Classify → Feedback → Learn → Retrain → Scheduler → Monitor → Notify

### Core Modules

| Module | Purpose | Key Abstractions |
|--------|---------|-----------------|
| `src/extractors/` | M365/Hotmail + Gmail extraction | `BaseExtractor`, `GraphApiClient` (MSAL device code), `GmailClient` (OAuth 2.0), `CheckpointManager` |
| `src/analyzers/` | 5 core + 2 optional analyzers | `BaseAnalyzer`, `SemanticAnalyzer`, `ClusterOptimizer`, `ThreadAnalyzer` |
| `src/generators/` | Category suggestions | `TemplateMatcher` (18 templates), `ConfidenceScorer`, `NameGenerator` |
| `src/rules/` | Category rules | `RuleEngine` (AND/OR, 8 operators), `RuleBuilder`, `RuleTester` |
| `src/categorizer/` | Email categorization | `EmailCategorizer`, `ConflictResolver`, `CoverageReporter` |
| `src/classifiers/` | Classification | `BaseClassifier`, `LLMClassifier` (Instructor + Ollama/OpenAI/Claude), `SetFitClassifier`, `EnsembleClassifier`, `EmailSanitizer` |
| `src/storage/` | SQLite persistence | `Database` (WAL), `EmailStore`, `EmbeddingStore` (sqlite-vec), `JsonToSqliteMigrator` |
| `src/actions/` | Email actions | `FolderManager`, `EmailMover` (batch + rollback), `RuleDeployer`, `ActionLogger` |
| `src/automation/` | Scheduled processing | `IncrementalProcessor`, `ChangeDetector`, `Scheduler`, `Retrainer` |
| `src/ui/` | TUI (Textual) + CLI | `ReviewApp`, `ReviewState` (thread-safe), undo/redo (Ctrl+Z/Y) |
| `src/learning/` | Feedback learning | `DecisionLogger`, `PatternDetector` (90-day half-life), `EmailFeedbackStore`, `UncertaintySampler`, `AccuracyTracker` |
| `src/exporters/` | Export formats | CSV, HTML, Outlook rules, Gmail filters |
| `src/models/` | Pydantic v2 models | `Email`, `Corpus`, `AnalysisResults`, `Category`, `RuleSet` |

### CLI Commands

| Command | Description |
|---------|-------------|
| `extract` | Extract emails (supports `--source`, `--since-last`) |
| `analyze` | Analyze corpus (`--auto-clusters`, `--incremental`, `--cluster-viz`) |
| `suggest` | Generate category suggestions |
| `review` | Interactive TUI review (`--no-tui` for CLI) |
| `pipeline` | Run complete workflow |
| `info` | Corpus statistics |
| `config init/show/validate` | Config management |
| `export` | CSV, HTML, Outlook rules, Gmail filters |
| `rules generate/test/show/edit` | Rule management |
| `categorize` | Email-by-email categorization (`--report`, `--resolve`) |
| `classify` | LLM classification (`--batch`, `--dry-run`, `--provider`, `--model`) |
| `migrate` | Import JSON/JSONL → SQLite (idempotent) |
| `train` | Fine-tune SetFit (`--min-examples`, `--output`) |
| `apply folders/move/rules/rollback` | Execute actions |
| `scheduler setup/run/status/disable` | Scheduled processing |
| `notifications show/clear/test` | Notification management |

**Global flags:** `--version`, `--verbose`, `--quiet`, `--json`, `--config`
**`--dry-run`:** Available per-command (not global)

### Output Files

Default: `~/data/outputs/` (configurable via `--output-dir`)

| File | Description |
|------|-------------|
| `email_corpus.json` | Extracted email data (legacy) |
| `corpus_analysis_results.json` | Analysis results |
| `category_suggestions.json` | Generated categories |
| `approved_categories.json` | Final approved categories |
| `embeddings_cache.npz` | Cached embeddings (+ .meta.json sidecar) |
| `rules.json` | Category rules |
| `categorization_report.json` | Categorization results |
| `~/.email-analyzer/email_analyzer.db` | SQLite DB (emails, classifications, corrections, logs) |
| `~/.email-analyzer/notifications.jsonl` | Notification history |
| `~/.email-analyzer/scheduler_state.json` | Scheduler state |
| `~/.config/email-analyzer/config.yaml` | Global config |
| `~/.email-analyzer/models/setfit/` | Saved SetFit model |

## Classification System

| Classifier | Type | Cost | When to Use |
|------------|------|------|-------------|
| `RuleEngine` | Rule-based | Zero | High-precision pattern matching |
| `LLMClassifier` | LLM (Ollama/OpenAI/Claude) | Free-$$ | Zero-shot, no training data |
| `SetFitClassifier` | Fine-tuned local | Zero (after training) | 8+ corrections per category |
| `EnsembleClassifier` | Chained | Varies | Production: rules → SetFit → LLM |

**LLM Providers:** Ollama (default, localhost:11434), OpenAI (`OPENAI_API_KEY`), Claude (`ANTHROPIC_API_KEY` + `[cloud]` extra), RunPod (`RUNPOD_API_KEY` + `--endpoint-id`)

**`EmailSanitizer`:** Strips injection patterns (role prefixes, instruction tags, code fences). Email text wrapped in `<email_content>` XML delimiters.

## Storage

**SQLite** at `~/.email-analyzer/email_analyzer.db` (WAL mode)

| Table | Purpose |
|-------|---------|
| `emails` | Extracted messages |
| `classifications` | Predictions (multiple per email) |
| `corrections` | User corrections for feedback |
| `sync_state` | Provider sync tokens |
| `decision_log` | Review decision history |
| `action_log` | Action audit trail |
| `schema_version` | Migration tracking |

**EmbeddingStore:** sqlite-vec extension, `vec0` virtual table, cosine distance nearest-neighbor.

## Feedback Learning

1. User corrects classification (A → B)
2. `EmailFeedbackStore` records correction with timestamp
3. Temporal decay (~70-day half-life) weights recent corrections higher
4. `UncertaintySampler` surfaces low-confidence and classifier-disagreement emails
5. `AccuracyTracker` monitors per-category correction rates
6. When rate exceeds threshold (default 20% in 7 days), `Retrainer` triggers
7. `Retrainer` assembles training data + trains SetFit model

**Active learning strategies:** uncertainty sampling (N least-confident), disagreement sampling (rule engine vs LLM differ).

## Configuration

```yaml
# ~/.config/email-analyzer/config.yaml
user_email: "user@example.com"
output_dir: "~/data/outputs"
analyze:
  num_clusters: 10
  max_embedding_text_length: 1500
  auto_cluster_min: 3
  auto_cluster_max: 25
  embedding_provider: "remote"   # "local" or "remote"
  embedding_base_url: "https://api.openai.com/v1"
  embedding_model_name: "text-embedding-3-small"
  embedding_api_key_env_var: "OPENAI_API_KEY"
  embedding_batch_size: 500
  clustering_pca_dims: 128
classifier:
  provider: "ollama"             # ollama | openai | claude | runpod
  model_name: "qwen2.5:7b"
  ollama_base_url: "http://localhost:11434"
  confidence_threshold: 0.6
  temperature: 0.0
  categories:
    - name: "Newsletters"
      description: "Regular newsletter subscriptions and digests"
learning:
  pattern_half_life_days: 90.0
scheduler:
  enabled: false
  interval_hours: 24
  run_at: "02:00"
  tasks: [extract, analyze, categorize, move]
monitoring:
  drift_threshold: 0.15
  volume_anomaly_stddev: 2.0
  alert_channels: [console, log]
```

`python -m src.cli config init` — generate template

## Environment Setup

- **M365/Hotmail:** MSAL device code flow — first run prints URL+code for browser auth. Token cached locally.
- **Gmail:** Requires `credentials.json` from Google Cloud Console (OAuth 2.0, Desktop app). Browser opens on first run.
- **Ollama:** `ollama pull qwen2.5:7b`. Default: `http://localhost:11434`.
- **API keys:** Stored in Bitwarden Secrets Manager. Config YAML references env var name; key must be in environment at runtime.

## Gotchas

- **First-run model download:** sentence-transformers downloads ~400MB on first `analyze`.
- **Auth is interactive:** M365 and Gmail require browser on first run. No headless without pre-cached tokens.
- **Graph API rate limits:** 429 handled with backoff; large mailboxes may need multiple runs with `--since-last`.
- **Checkpoint resumption:** Re-run with same flags — `CheckpointManager` auto-resumes.
- **Embedding cache invalidation:** Changing model version auto-invalidates (`.meta.json` sidecar tracks model identity).
- **`--cluster-viz` requires matplotlib** — `pip install matplotlib` if needed.
- **Ollama must be running** — `classify` with `provider=ollama` throws `ClassifierConnectionError` if not.
- **SQLite migration is one-way:** Source JSON files preserved but no longer updated after `migrate`.
- **SetFit requires training** — minimum 8 examples per category before use.
- **`EmailSanitizer` strips "SYSTEM:" prefixes** — legitimate emails with role-prefix lines will be stripped; check logs for WARNING-level sanitization messages.

## Tech Stack

Python 3.10+, Pydantic v2, sentence-transformers, scikit-learn, Textual (TUI), SQLite (WAL) + sqlite-vec, Instructor (structured LLM output), OpenAI SDK (transport for Ollama + OpenAI), Anthropic SDK (optional), SetFit (optional), Microsoft Graph API (MSAL), Gmail API (OAuth 2.0), Ruff (linting), Jinja2 (HTML reports)
