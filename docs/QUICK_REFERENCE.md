# Email Corpus Analyzer - Quick Reference

## Setup

```bash
cd email-corpus-analyzer
pip install -r requirements.txt
```

**For Hotmail**: No setup needed — authenticates on first run.
**For Gmail**: Save OAuth credentials to `~/.email-analyzer/gmail_credentials.json` (see [Setup Guide](M365_SETUP.md#gmail-setup)).

---

## Extract Emails

```bash
# Hotmail (default)
python -m src.cli extract --user-email user@hotmail.com

# Gmail
python -m src.cli extract --user-email your.email@gmail.com --source gmail

# Both accounts merged
python -m src.cli extract --user-email user@hotmail.com --source both --gmail-email your.email@gmail.com

# Incremental (new emails only)
python -m src.cli extract --user-email user@hotmail.com --since-last
```

## Analyze / Suggest / Review / Export

```bash
python -m src.cli analyze --auto-clusters       # Analyze patterns
python -m src.cli suggest                        # Generate categories
python -m src.cli review                         # Interactive TUI review
python -m src.cli export --format html           # HTML report
python -m src.cli export --format outlook-rules  # Outlook rules
python -m src.cli export --format gmail-filters  # Gmail filters
python -m src.cli export --format csv            # CSV export
```

## Full Pipeline (One Command)

```bash
# Hotmail
python -m src.cli pipeline --user-email user@hotmail.com --auto-clusters

# Gmail
python -m src.cli pipeline --user-email your.email@gmail.com --source gmail --auto-clusters

# Both
python -m src.cli pipeline --user-email user@hotmail.com --source both --gmail-email your.email@gmail.com --auto-clusters
```

## Other Commands

```bash
python -m src.cli info              # Corpus statistics
python -m src.cli config show       # Show configuration
python -m src.cli config init       # Generate config template
python -m src.cli config validate   # Validate config
```

---

## Output Files

| File | Location |
|------|----------|
| Email corpus | `~/data/outputs/email_corpus.json` |
| Analysis results | `~/data/outputs/corpus_analysis_results.json` |
| Category suggestions | `~/data/outputs/category_suggestions.json` |
| Suggestions report | `~/data/outputs/category_suggestions_report.md` |
| Approved categories | `~/data/outputs/approved_categories.json` |
| Embeddings cache | `~/data/outputs/embeddings_cache.npz` |
| Config | `~/.email-analyzer/config.yaml` |
| Decision history | `~/.email-analyzer/decisions.jsonl` |
| MS token cache | `~/.email-analyzer/ms_token_cache.json` |
| Gmail token cache | `~/.email-analyzer/gmail_token.json` |

---

## CLI Flags

### Global (before command)
- `--output-dir DIR` — Output directory for all files
- `--verbose` — Debug logging
- `--quiet` — Suppress INFO output
- `--json` — JSON output for automation
- `--config PATH` — Custom config file
- `--dry-run` — Preview without executing
- `--version` — Show version

### Extract
- `--user-email EMAIL` — (required) Email address
- `--source {hotmail,gmail,both}` — Email source (default: hotmail)
- `--gmail-email EMAIL` — Gmail address for --source both
- `--corpus-file PATH` — Custom corpus file
- `--batch-size N` — Emails per batch (default: 500)
- `--checkpoint-interval N` — Checkpoint every N (default: 100)
- `--since-last` — Incremental extraction

### Analyze
- `--corpus PATH` — Input corpus file
- `--num-clusters N` — Clusters (default: 10)
- `--auto-clusters` — Auto-detect optimal k
- `--cluster-method {elbow,silhouette}` — Optimization method
- `--incremental` — Only process new emails
- `--cluster-viz` — Generate cluster visualization PNG

### Pipeline
- `--user-email EMAIL` — (required) Email address
- `--source {hotmail,gmail,both}` — Email source (default: hotmail)
- `--gmail-email EMAIL` — Gmail address for --source both
- `--auto-clusters` — Auto-detect optimal k
- `--skip-review` — Auto-approve all suggestions
- `--no-tui` — CLI review instead of TUI
- `--no-learning` — Disable feedback learning

---

## Authentication

| Source | Method | First Run | Token Location |
|--------|--------|-----------|----------------|
| Hotmail | Device code flow | Visit URL + enter code | `~/.email-analyzer/ms_token_cache.json` |
| Gmail | Browser OAuth | Browser opens for sign-in | `~/.email-analyzer/gmail_token.json` |

Reset auth: delete the token file and re-run.

---

## Troubleshooting

**"ModuleNotFoundError: No module named 'src'"** → Run from project root: `python -m src.cli`

**"Permission denied"** → Use `--output-dir ~/my-emails`

**"Gmail credentials not found"** → Download OAuth JSON from Google Cloud Console → save to `~/.email-analyzer/gmail_credentials.json`

**Auth expired** → Delete token cache: `rm ~/.email-analyzer/ms_token_cache.json`

**Debug logs** → Add `--verbose` before command

---

For full docs: [USAGE.md](USAGE.md) | [Setup Guide](M365_SETUP.md)
