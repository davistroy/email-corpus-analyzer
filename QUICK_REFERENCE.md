# Email Corpus Analyzer - Quick Reference

## Installation

```bash
git clone https://github.com/davistroy/email-corpus-analyzer.git
cd email-corpus-analyzer
python3 -m venv venv && source venv/bin/activate
pip install -e .
```

## Common Commands

### Add Mailbox

```bash
# M365 (personal)
email-analyzer mailbox add -n "Work" -p m365 -e you@outlook.com

# Gmail
email-analyzer mailbox add -n "Personal" -p gmail -e you@gmail.com --credentials ~/creds.json

# IMAP
email-analyzer mailbox add -n "Legacy" -p imap -e you@example.com --host imap.example.com
```

### Manage Mailboxes

```bash
email-analyzer mailbox list                    # List all
email-analyzer mailbox list --provider gmail   # Filter by provider
email-analyzer mailbox auth Work               # Authenticate
email-analyzer mailbox info Work               # Show details
email-analyzer mailbox remove Work             # Remove
```

### Extract & Analyze

```bash
email-analyzer extract                         # Extract all
email-analyzer extract --mailbox Work          # Specific mailbox
email-analyzer analyze                         # Analyze
email-analyzer analyze --llm                   # With LLM naming
email-analyzer suggest                         # Generate suggestions
email-analyzer review                          # Interactive review
```

### Reports

```bash
email-analyzer report --format table           # Console table
email-analyzer report --format html            # HTML report
email-analyzer report --format json --pretty   # JSON (formatted)
email-analyzer report --format csv             # CSV zip
email-analyzer report --format all             # All formats
email-analyzer report --cross-mailbox          # Compare mailboxes
```

### Pipeline

```bash
email-analyzer pipeline                        # Full workflow
email-analyzer pipeline --llm                  # With LLM
email-analyzer pipeline --skip-extract         # Skip extraction
email-analyzer pipeline --skip-review          # Skip review
```

### Utilities

```bash
email-analyzer status                          # System status
email-analyzer version                         # Version info
email-analyzer --help                          # Help
email-analyzer <command> --help                # Command help
```

---

## Command Reference

### Mailbox Commands

| Command | Options | Description |
|---------|---------|-------------|
| `mailbox add` | `-n, -p, -e, --tenant, --client-id, --credentials, --host, --port` | Add mailbox |
| `mailbox list` | `--provider, --status` | List mailboxes |
| `mailbox auth` | `<name>` | Authenticate |
| `mailbox info` | `<name>, --format` | Show details |
| `mailbox remove` | `<name>, --delete-data` | Remove mailbox |

### Analysis Commands

| Command | Options | Description |
|---------|---------|-------------|
| `extract` | `--mailbox, --since, --batch-size, --max-emails` | Extract emails |
| `analyze` | `--mailbox, --method, --clusters, --min-size, --llm` | Analyze corpus |
| `suggest` | `--mailbox, --min-cluster, --min-sender` | Generate suggestions |
| `review` | `--skip-cleanup` | Interactive review |
| `report` | `--format, --output, --pretty, --cross-mailbox` | Generate reports |

### Pipeline Command

| Option | Description |
|--------|-------------|
| `--llm` | Enable LLM naming |
| `--skip-extract` | Skip extraction step |
| `--skip-review` | Skip review step |
| `--method` | Clustering method (hdbscan/kmeans) |

---

## Output Formats

| Format | Command | Output |
|--------|---------|--------|
| Table | `--format table` | Console |
| HTML | `--format html` | `.html` file |
| JSON | `--format json` | `.json` file |
| CSV | `--format csv` | `.zip` or directory |
| Markdown | `--format markdown` | `.md` file |
| All | `--format all` | All formats |

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `ANTHROPIC_API_KEY` | Claude API key (for `--llm`) |
| `EMAIL_ANALYZER_DATA_DIR` | Custom data directory |

---

## Data Location

Default: `~/.email-analyzer/`

```
~/.email-analyzer/
├── mailboxes.json      # Registry
├── credentials/        # OAuth tokens
├── data/{mailbox}/     # Per-mailbox data
└── logs/               # Logs
```

---

## Providers

| Provider | Auth | Command |
|----------|------|---------|
| M365 | Device code | `--provider m365` |
| Gmail | OAuth browser | `--provider gmail --credentials FILE` |
| IMAP | Password | `--provider imap --host HOST` |

---

## Examples

### Quick Start

```bash
email-analyzer mailbox add -n "Work" -p m365 -e you@company.com
email-analyzer mailbox auth Work
email-analyzer pipeline --llm
email-analyzer report --format html
```

### Multi-Mailbox

```bash
email-analyzer mailbox add -n "Work" -p m365 -e work@corp.com
email-analyzer mailbox add -n "Personal" -p gmail -e me@gmail.com --credentials ~/creds.json
email-analyzer mailbox auth Work
email-analyzer mailbox auth Personal
email-analyzer extract
email-analyzer report --cross-mailbox --format html
```

### Custom Analysis

```bash
email-analyzer analyze --method hdbscan --min-size 10 --llm
email-analyzer suggest --min-cluster 3.0 --min-sender 15
email-analyzer report --format all --output ~/reports/
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Module not found | Run `email-analyzer` not `python src/cli.py` |
| Auth failed | Run `email-analyzer mailbox auth <name>` |
| No mailboxes | Run `email-analyzer mailbox add ...` |
| Permission denied | Set `EMAIL_ANALYZER_DATA_DIR=~/data` |
| LLM error | Set `ANTHROPIC_API_KEY` env var |

---

## Documentation

- [USAGE.md](USAGE.md) - Full guide
- [M365_SETUP.md](M365_SETUP.md) - Microsoft 365
- [GMAIL_SETUP.md](GMAIL_SETUP.md) - Gmail
- [IMAP_SETUP.md](IMAP_SETUP.md) - IMAP
- [TESTING.md](TESTING.md) - Testing
