# Email Processor - Usage Guide

## Quick Start

### Prerequisites

- Python 3.10+
- Dependencies installed: `pip install -r requirements.txt`
- For Hotmail: No setup needed — authenticates on first run via device code
- For Gmail: OAuth credentials from Google Cloud Console (see [Setup Guide](M365_SETUP.md))

### Default Output Directory
All output files are saved to: **`~/data/outputs`**

This expands to `C:\Users\YourUsername\data\outputs` on Windows or `/home/yourusername/data/outputs` on Linux/Mac.

### Running the Pipeline

```bash
# Extract from Hotmail and run full pipeline
python -m src.cli pipeline --user-email troy.davis@hotmail.com

# Extract from Gmail instead
python -m src.cli pipeline --user-email your.email@gmail.com --source gmail

# Extract from both accounts
python -m src.cli pipeline --user-email troy.davis@hotmail.com --source both --gmail-email your.email@gmail.com
```

On first run, you'll be prompted to authenticate in your browser. Tokens are cached for future runs.

---

## Custom Output Directories

### Method 1: Global --output-dir Flag

Use `--output-dir` **before** the command name:

```bash
# Extract to custom directory
python -m src.cli --output-dir ~/my-emails extract --user-email user@hotmail.com

# Analyze in custom directory
python -m src.cli --output-dir ~/my-emails analyze

# Run pipeline in custom directory
python -m src.cli --output-dir ~/email-analysis pipeline --user-email user@hotmail.com
```

### Method 2: Per-File Custom Paths

Override individual file paths while using default output directory:

```bash
# Extract to custom corpus file
python -m src.cli extract --user-email user@hotmail.com --corpus-file ~/custom_corpus.json

# Analyze custom corpus, save to custom analysis file
python -m src.cli analyze --corpus ~/custom_corpus.json --analysis-file ~/custom_analysis.json
```

### Method 3: Mix Global + Per-File

```bash
# Use custom output directory, but override specific files
python -m src.cli --output-dir ~/emails \
  extract --user-email user@hotmail.com --corpus-file ~/backup/emails.json
```

---

## Command Reference

### 1. Extract

Extract emails from Hotmail/Outlook.com or Gmail inbox.

**Basic Usage:**
```bash
# From Hotmail (default)
python -m src.cli extract --user-email troy.davis@hotmail.com

# From Gmail
python -m src.cli extract --user-email your.email@gmail.com --source gmail

# From both
python -m src.cli extract --user-email troy.davis@hotmail.com --source both --gmail-email your.email@gmail.com

# Incremental (only new emails since last extraction)
python -m src.cli extract --user-email troy.davis@hotmail.com --since-last
```

**All Options:**
```bash
python -m src.cli [--output-dir DIR] extract \
  --user-email EMAIL \
  [--source {hotmail,gmail,both}] \
  [--gmail-email EMAIL] \
  [--corpus-file PATH] \
  [--batch-size N] \
  [--checkpoint-interval N] \
  [--since-last] \
  [--dry-run]
```

**Options:**
- `--user-email` (required): Primary email address
- `--source`: Email source — `hotmail` (default), `gmail`, or `both`
- `--gmail-email`: Gmail address when using `--source both` (if different from `--user-email`)
- `--corpus-file`: Custom corpus JSON path (default: `{output-dir}/email_corpus.json`)
- `--batch-size`: Emails per API batch (default: 500)
- `--checkpoint-interval`: Save checkpoint every N emails (default: 100)
- `--since-last`: Only fetch emails received since the last extraction
- `--dry-run`: Preview what would happen without executing

**Output Files:**
- `email_corpus.json` - Complete email corpus
- `extraction_checkpoint.json` - Temporary (deleted on success)

**Authentication:**
- **Hotmail**: Device code flow — prints a URL and code, you authenticate in any browser
- **Gmail**: Browser-based OAuth — opens browser for Google sign-in
- Tokens cached at `~/.email-analyzer/` for future runs

---

### 2. Analyze

Analyze email corpus for patterns (7 analyzers: sender, subject, semantic, temporal, volume, hierarchical, thread).

**Basic Usage:**
```bash
python -m src.cli analyze

# Auto-detect optimal cluster count
python -m src.cli analyze --auto-clusters
```

**All Options:**
```bash
python -m src.cli [--output-dir DIR] analyze \
  [--corpus PATH] \
  [--num-clusters N] \
  [--auto-clusters] \
  [--cluster-method {elbow,silhouette}] \
  [--incremental] \
  [--analysis-file PATH]
```

**Options:**
- `--corpus`: Path to corpus JSON (default: `{output-dir}/email_corpus.json`)
- `--num-clusters`: Semantic cluster count (default: 10)
- `--auto-clusters`: Automatically determine optimal cluster count
- `--cluster-method`: Method for auto-clustering — `silhouette` (default) or `elbow`
- `--incremental`: Only process new emails using cached embeddings
- `--analysis-file`: Custom analysis results path

**Output Files:**
- `corpus_analysis_results.json` - Combined results from all analyzers
- `embeddings_cache.npz` - Cached embeddings for incremental analysis

---

### 3. Suggest

Generate category suggestions from analysis results.

**Basic Usage:**
```bash
python -m src.cli suggest
```

**All Options:**
```bash
python -m src.cli [--output-dir DIR] suggest \
  [--analysis PATH] \
  [--min-cluster-percentage PCT] \
  [--min-sender-count N] \
  [--suggestions-file PATH] \
  [--dry-run]
```

**Options:**
- `--analysis`: Path to analysis results (default: `{output-dir}/corpus_analysis_results.json`)
- `--min-cluster-percentage`: Min cluster size % for category (default: 5.0)
- `--min-sender-count`: Min emails from sender for category (default: 20)
- `--suggestions-file`: Custom suggestions path
- `--dry-run`: Preview suggestions without writing output files

**Output Files:**
- `category_suggestions.json` - Category suggestions (JSON)
- `category_suggestions_report.md` - Human-readable report

---

### 4. Review

Interactively review and approve category suggestions.

**Basic Usage:**
```bash
# TUI interface (default)
python -m src.cli review

# CLI-based review
python -m src.cli review --no-tui
```

**All Options:**
```bash
python -m src.cli [--output-dir DIR] review \
  [--suggestions PATH] \
  [--approved-file PATH] \
  [--no-cleanup] \
  [--no-tui] \
  [--headless] \
  [--no-learning]
```

**Options:**
- `--suggestions`: Path to suggestions JSON
- `--approved-file`: Custom approved categories path
- `--no-cleanup`: Skip optional cleanup of intermediate files
- `--no-tui`: Use legacy CLI interface instead of TUI
- `--headless`: Auto-approve all suggestions without interactive review (for automation)
- `--no-learning`: Disable feedback learning

**TUI Actions:**
- Navigate with arrow keys
- `A` — Accept category
- `R` — Rename category
- `M` — Merge with another category
- `D` — Delete category
- `S` — Skip (review later)
- `/` — Search/filter categories

**Output Files:**
- `approved_categories.json` - Final approved categories
- `~/.email-analyzer/decisions.jsonl` - Decision history for learning

---

### 5. Export

Export approved categories to various formats.

```bash
# CSV export
python -m src.cli export --format csv

# HTML report
python -m src.cli export --format html

# Outlook rules
python -m src.cli export --format outlook-rules

# Gmail filters (XML)
python -m src.cli export --format gmail-filters
```

---

### 6. Pipeline

Run complete end-to-end workflow: extract → analyze → suggest → review.

**Basic Usage:**
```bash
# Hotmail pipeline
python -m src.cli pipeline --user-email troy.davis@hotmail.com

# Gmail pipeline
python -m src.cli pipeline --user-email your.email@gmail.com --source gmail

# Both accounts
python -m src.cli pipeline --user-email troy.davis@hotmail.com --source both --gmail-email your.email@gmail.com

# Skip interactive review
python -m src.cli pipeline --user-email troy.davis@hotmail.com --skip-review
```

**All Options:**
```bash
python -m src.cli [--output-dir DIR] pipeline \
  --user-email EMAIL \
  [--source {hotmail,gmail,both}] \
  [--gmail-email EMAIL] \
  [--num-clusters N] \
  [--auto-clusters] \
  [--cluster-method {elbow,silhouette}] \
  [--skip-review] \
  [--no-cleanup] \
  [--no-tui] \
  [--no-learning] \
  [--dry-run]
```

---

### 7. Other Commands

```bash
# Show corpus statistics
python -m src.cli info

# Configuration management
python -m src.cli config show       # Show resolved configuration
python -m src.cli config init       # Generate config template
python -m src.cli config validate   # Validate configuration
```

---

## File Locations Summary

### Default (~/data/outputs/)

| File | Description | Created By |
|------|-------------|------------|
| `email_corpus.json` | Email corpus | extract |
| `corpus_analysis_results.json` | Analysis results | analyze |
| `category_suggestions.json` | Category suggestions | suggest |
| `category_suggestions_report.md` | Human-readable report | suggest |
| `approved_categories.json` | Final categories | review |
| `embeddings_cache.npz` | Cached embeddings | analyze |
| `extraction_checkpoint.json` | Temp checkpoint | extract (auto-deleted) |

### Configuration (~/.email-analyzer/)

| File | Description |
|------|-------------|
| `config.yaml` | App configuration |
| `decisions.jsonl` | Review decision history |
| `ms_token_cache.json` | Microsoft Graph OAuth tokens |
| `gmail_credentials.json` | Google OAuth client secrets (you provide) |
| `gmail_token.json` | Google OAuth tokens |

---

## Common Workflows

### Workflow 1: First-Time Hotmail Analysis

```bash
# One command — authenticates, extracts, analyzes, generates categories, reviews
python -m src.cli pipeline --user-email troy.davis@hotmail.com --auto-clusters
```

### Workflow 2: First-Time Gmail Analysis

```bash
# Ensure gmail_credentials.json is in ~/.email-analyzer/ first
python -m src.cli pipeline --user-email your.email@gmail.com --source gmail --auto-clusters
```

### Workflow 3: Combined Hotmail + Gmail

```bash
python -m src.cli pipeline \
  --user-email troy.davis@hotmail.com \
  --source both \
  --gmail-email your.email@gmail.com \
  --auto-clusters
```

### Workflow 4: Step-by-Step

```bash
# Step 1: Extract
python -m src.cli extract --user-email troy.davis@hotmail.com

# Step 2: Analyze with auto-clustering
python -m src.cli analyze --auto-clusters

# Step 3: Generate suggestions
python -m src.cli suggest

# Step 4: Interactive review
python -m src.cli review

# Step 5: Export results
python -m src.cli export --format html
python -m src.cli export --format outlook-rules
```

### Workflow 5: Incremental Update

```bash
# Fetch only new emails since last extraction
python -m src.cli extract --user-email troy.davis@hotmail.com --since-last

# Re-analyze with new data (uses cached embeddings for old emails)
python -m src.cli analyze --incremental --auto-clusters

# Re-generate and review
python -m src.cli suggest
python -m src.cli review
```

### Workflow 6: Resume Interrupted Extraction

```bash
# If extraction was interrupted, just run again — it resumes from checkpoint
python -m src.cli extract --user-email troy.davis@hotmail.com
```

### Workflow 7: Dry Run (Preview)

```bash
# See what each command would do without executing
python -m src.cli extract --user-email troy.davis@hotmail.com --dry-run
python -m src.cli pipeline --user-email troy.davis@hotmail.com --dry-run
```

---

## Troubleshooting

### "ModuleNotFoundError: No module named 'src'"
Run as a module from project root:
```bash
# Correct
python -m src.cli --help

# Wrong
cd src && python cli.py --help
```

### "Permission denied" when creating output directory
Use a home directory subdirectory:
```bash
python -m src.cli --output-dir ~/my-emails extract --user-email user@hotmail.com
```

### "File not found" when running analyze/suggest/review
Ensure the previous step completed and files exist. Use `--output-dir` consistently across commands.

### "Gmail credentials not found"
Download OAuth client JSON from Google Cloud Console and save to `~/.email-analyzer/gmail_credentials.json`. See [Setup Guide](M365_SETUP.md#gmail-setup).

### Authentication expired
Delete the token cache and re-authenticate:
```bash
rm ~/.email-analyzer/ms_token_cache.json   # For Hotmail
rm ~/.email-analyzer/gmail_token.json       # For Gmail
```

### Want to see debug logs
```bash
python -m src.cli --verbose extract --user-email user@hotmail.com
```

---

## Security Notes

1. **File Permissions**: Output files created with mode `0600` (user read/write only)
2. **Directory Permissions**: Output directories created with mode `0700` (user only)
3. **Local Storage Only**: Email data stays on your machine — never transmitted externally
4. **Token Storage**: Auth tokens cached in `~/.email-analyzer/` (your home directory)
5. **No Passwords Stored**: Authentication uses OAuth device/browser flows — no passwords saved

---

## Next Steps

After approving categories:
1. Export to Outlook rules: `python -m src.cli export --format outlook-rules`
2. Export to Gmail filters: `python -m src.cli export --format gmail-filters`
3. Export HTML report: `python -m src.cli export --format html`
4. Re-run with different parameters or incremental updates

For authentication setup details, see [Setup Guide](M365_SETUP.md).
