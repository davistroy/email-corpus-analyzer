# Email Corpus Analyzer - Usage Guide

This guide covers all features of the Email Corpus Analyzer CLI.

## Table of Contents

- [Installation](#installation)
- [Getting Started](#getting-started)
- [Mailbox Management](#mailbox-management)
- [Extracting Emails](#extracting-emails)
- [Analyzing Emails](#analyzing-emails)
- [Generating Suggestions](#generating-suggestions)
- [Interactive Review](#interactive-review)
- [Generating Reports](#generating-reports)
- [Pipeline Command](#pipeline-command)
- [Cross-Mailbox Analysis](#cross-mailbox-analysis)
- [Output Formats](#output-formats)
- [Troubleshooting](#troubleshooting)

---

## Installation

### System Requirements

- Python 3.11 or higher
- 4GB RAM minimum (8GB recommended for large mailboxes)
- Internet connection for email provider APIs

### Install from Source

```bash
# Clone repository
git clone https://github.com/davistroy/email-corpus-analyzer.git
cd email-corpus-analyzer

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

# Install package
pip install -e .

# Verify installation
email-analyzer --help
```

### Install Development Dependencies

```bash
pip install -e ".[dev]"
```

---

## Getting Started

### First-Time Setup

1. **Add a mailbox**:
   ```bash
   email-analyzer mailbox add --name "Work" --provider m365 --email you@company.com
   ```

2. **Authenticate**:
   ```bash
   email-analyzer mailbox auth Work
   ```

3. **Run the pipeline**:
   ```bash
   email-analyzer pipeline
   ```

4. **View reports**:
   ```bash
   email-analyzer report --format html
   ```

### Check System Status

```bash
email-analyzer status
```

This shows:
- Configured mailboxes and their status
- Authentication state
- Extraction progress
- Suggested next steps

---

## Mailbox Management

### Adding Mailboxes

#### Microsoft 365 (Personal Account)

```bash
email-analyzer mailbox add \
  --name "Outlook" \
  --provider m365 \
  --email you@outlook.com
```

#### Microsoft 365 (Corporate Account)

```bash
email-analyzer mailbox add \
  --name "Work" \
  --provider m365 \
  --email you@company.com \
  --tenant YOUR_TENANT_ID \
  --client-id YOUR_CLIENT_ID
```

#### Gmail

```bash
email-analyzer mailbox add \
  --name "Personal" \
  --provider gmail \
  --email you@gmail.com \
  --credentials ~/path/to/credentials.json
```

See [GMAIL_SETUP.md](GMAIL_SETUP.md) for obtaining credentials.

#### IMAP Server

```bash
email-analyzer mailbox add \
  --name "Legacy" \
  --provider imap \
  --email you@example.com \
  --host imap.example.com \
  --port 993
```

You'll be prompted for your password securely.

### Listing Mailboxes

```bash
# List all mailboxes
email-analyzer mailbox list

# Filter by provider
email-analyzer mailbox list --provider gmail

# Filter by status
email-analyzer mailbox list --status active
```

### Viewing Mailbox Details

```bash
# Text format
email-analyzer mailbox info Work

# JSON format
email-analyzer mailbox info Work --format json
```

### Authenticating Mailboxes

```bash
email-analyzer mailbox auth Work
```

This opens the appropriate OAuth flow for your provider:
- **M365**: Device code flow (displays code, open browser)
- **Gmail**: OAuth consent screen in browser
- **IMAP**: Password verification

### Removing Mailboxes

```bash
# Remove configuration only
email-analyzer mailbox remove Work

# Remove configuration and all data
email-analyzer mailbox remove Work --delete-data
```

---

## Extracting Emails

### Basic Extraction

```bash
# Extract from all mailboxes
email-analyzer extract

# Extract from specific mailbox
email-analyzer extract --mailbox Work
```

### Extraction Options

```bash
email-analyzer extract \
  --mailbox Work \
  --since 2024-01-01 \
  --batch-size 100 \
  --max-emails 5000
```

| Option | Description | Default |
|--------|-------------|---------|
| `--mailbox` | Specific mailbox name | All mailboxes |
| `--since` | Only emails after this date | None (all) |
| `--batch-size` | Emails per API batch | 500 |
| `--max-emails` | Maximum emails to extract | Unlimited |

### Resume Interrupted Extraction

Extraction automatically saves checkpoints. If interrupted, simply run the same command again:

```bash
email-analyzer extract --mailbox Work
# Resumes from last checkpoint
```

---

## Analyzing Emails

### Basic Analysis

```bash
# Analyze all mailboxes
email-analyzer analyze

# Analyze specific mailbox
email-analyzer analyze --mailbox Work
```

### Analysis Methods

```bash
# HDBSCAN clustering (auto-detects cluster count)
email-analyzer analyze --method hdbscan

# KMeans with specific cluster count
email-analyzer analyze --method kmeans --clusters 15
```

### LLM-Enhanced Analysis

Use Claude AI for intelligent cluster naming:

```bash
# Requires ANTHROPIC_API_KEY environment variable
export ANTHROPIC_API_KEY="your-api-key"
email-analyzer analyze --llm
```

### Analysis Options

| Option | Description | Default |
|--------|-------------|---------|
| `--mailbox` | Specific mailbox | All |
| `--method` | Clustering method (hdbscan/kmeans) | hdbscan |
| `--clusters` | Number of clusters (kmeans only) | 10 |
| `--min-size` | Minimum cluster size | 5 |
| `--llm` | Use LLM for naming | False |

---

## Generating Suggestions

Generate category suggestions from analysis results:

```bash
# Basic suggestions
email-analyzer suggest

# With custom thresholds
email-analyzer suggest \
  --min-cluster 10.0 \
  --min-sender 50
```

### Suggestion Options

| Option | Description | Default |
|--------|-------------|---------|
| `--mailbox` | Specific mailbox | All |
| `--min-cluster` | Minimum cluster size % | 5.0 |
| `--min-sender` | Minimum emails from sender | 20 |

---

## Interactive Review

Review and approve category suggestions interactively:

```bash
email-analyzer review
```

### Review Actions

During review, you can:

| Action | Key | Description |
|--------|-----|-------------|
| Accept | `a` | Approve category as-is |
| Rename | `r` | Change name/description |
| Merge | `m` | Combine with another category |
| Delete | `d` | Discard category |
| Skip | `s` | Review later |

### Skip Cleanup

```bash
email-analyzer review --skip-cleanup
```

---

## Generating Reports

### Available Formats

| Format | Description | Output |
|--------|-------------|--------|
| `html` | Interactive HTML with styling | Single file |
| `json` | Complete JSON data | Single file |
| `csv` | Tabular CSV files | Zip archive or directory |
| `markdown` | Human-readable report | Single file |
| `table` | Rich console table | Terminal output |
| `all` | Generate all formats | Multiple files |

### Basic Report Generation

```bash
# HTML report
email-analyzer report --format html

# JSON report
email-analyzer report --format json

# All formats
email-analyzer report --format all
```

### Report Options

```bash
email-analyzer report \
  --format json \
  --pretty \
  --output ~/reports/analysis.json
```

| Option | Description | Default |
|--------|-------------|---------|
| `--format` | Output format | table |
| `--output` | Custom output path | Auto-generated |
| `--pretty` | Pretty-print JSON | False |
| `--compact` | Minify JSON | False |
| `--zip` | Package CSV as zip | True |
| `--no-zip` | CSV as directory | False |

### Cross-Mailbox Reports

Compare patterns across multiple mailboxes:

```bash
email-analyzer report --cross-mailbox --format html
```

---

## Pipeline Command

Run the complete workflow with a single command:

```bash
email-analyzer pipeline
```

### Pipeline Steps

1. Extract emails from all authenticated mailboxes
2. Analyze corpus (sender, subject, semantic, temporal, volume)
3. Generate category suggestions
4. Interactive review (optional)
5. Generate final report

### Pipeline Options

```bash
email-analyzer pipeline \
  --llm \
  --skip-extract \
  --skip-review
```

| Option | Description |
|--------|-------------|
| `--llm` | Enable LLM-powered category naming |
| `--skip-extract` | Skip extraction (use existing data) |
| `--skip-review` | Skip interactive review |
| `--method` | Clustering method (hdbscan/kmeans) |

---

## Cross-Mailbox Analysis

Analyze patterns across multiple email accounts:

### Setup Multiple Mailboxes

```bash
email-analyzer mailbox add --name "Work" --provider m365 --email work@company.com
email-analyzer mailbox add --name "Personal" --provider gmail --email me@gmail.com
email-analyzer mailbox auth Work
email-analyzer mailbox auth Personal
```

### Extract and Analyze

```bash
# Extract from all
email-analyzer extract

# Analyze each mailbox
email-analyzer analyze --mailbox Work
email-analyzer analyze --mailbox Personal
```

### Generate Comparison Report

```bash
email-analyzer report --cross-mailbox --format table
```

---

## Output Formats

### Console Table (default)

```bash
email-analyzer report --format table
```

Interactive table displayed in terminal with Rich formatting.

### HTML Report

```bash
email-analyzer report --format html
```

Features:
- Interactive collapsible sections
- Color-coded badges
- Progress bars
- Print-friendly styling

### JSON Export

```bash
# Pretty-printed
email-analyzer report --format json --pretty

# Compact/minified
email-analyzer report --format json --compact
```

### CSV Export

```bash
# As zip archive
email-analyzer report --format csv

# As directory
email-analyzer report --format csv --no-zip
```

Generated CSV files:
- `summary.csv` - Overall statistics
- `senders.csv` - Top senders
- `domains.csv` - Domain frequencies
- `clusters.csv` - Content clusters
- `categories.csv` - Category suggestions

### Markdown Report

```bash
email-analyzer report --format markdown
```

Human-readable report suitable for documentation.

---

## Troubleshooting

### "ModuleNotFoundError: No module named 'src'"

Run as module from project root:

```bash
# Correct
email-analyzer report

# Or if not installed
python -m src.cli_new report
```

### "ANTHROPIC_API_KEY not set"

Set the environment variable for LLM features:

```bash
export ANTHROPIC_API_KEY="your-api-key"
email-analyzer analyze --llm
```

### "Authentication failed"

Re-authenticate the mailbox:

```bash
email-analyzer mailbox auth <mailbox-name>
```

### "No mailboxes configured"

Add a mailbox first:

```bash
email-analyzer mailbox add --name "Work" --provider m365 --email you@company.com
```

### "Permission denied" creating files

Use a directory you have write access to:

```bash
export EMAIL_ANALYZER_DATA_DIR=~/email-analyzer-data
email-analyzer extract
```

### Viewing Debug Logs

Enable verbose output:

```bash
email-analyzer --verbose extract
```

Or check log files in `~/.email-analyzer/logs/`.

---

## Data Storage

Default location: `~/.email-analyzer/`

```
~/.email-analyzer/
├── mailboxes.json           # Mailbox registry
├── credentials/             # Encrypted credentials
├── data/
│   ├── {mailbox_id}/       # Per-mailbox data
│   │   ├── corpus.json
│   │   ├── analysis.json
│   │   ├── suggestions.json
│   │   └── checkpoints/
│   └── aggregated/         # Cross-mailbox data
└── logs/                   # Application logs
```

### Custom Data Directory

```bash
export EMAIL_ANALYZER_DATA_DIR=/path/to/custom/directory
email-analyzer extract
```

---

## Security Notes

1. **Local Storage Only**: No data transmitted to external services (except email providers and optional LLM)
2. **Secure Permissions**: Files created with `0600`, directories with `0700`
3. **Credential Protection**: OAuth tokens encrypted at rest
4. **No Plaintext Passwords**: IMAP passwords stored securely

---

## Next Steps

After completing analysis:

1. Review generated reports in `~/.email-analyzer/data/`
2. Use approved categories for email organization
3. Re-run analysis periodically for updated insights
4. Try different clustering methods for varied results

For provider-specific setup, see:
- [M365_SETUP.md](M365_SETUP.md)
- [GMAIL_SETUP.md](GMAIL_SETUP.md)
- [IMAP_SETUP.md](IMAP_SETUP.md)
