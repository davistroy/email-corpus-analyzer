# Email Corpus Analyzer - Development Guidelines

## Project Overview

Multi-provider email corpus analysis system with LLM-powered categorization.

**Version**: 2.0.0
**Python**: 3.11+

## Quick Commands

```bash
# Install
pip install -e ".[dev]"

# Run CLI
email-analyzer --help

# Run tests
pytest

# Lint
ruff check src/

# Type check
mypy src/
```

## Project Structure

```
src/
├── models/          # Pydantic data models
├── providers/       # Email providers (M365, Gmail, IMAP)
├── analyzers/       # 5 analysis engines
├── generators/      # Category generation
├── reports/         # Report generators (HTML, JSON, CSV)
├── llm/             # Claude AI integration
├── mailbox/         # Multi-mailbox management
├── extractors/      # Email extraction
├── ui/              # Interactive review
├── utils/           # Utilities
└── cli_new.py       # Main CLI (Typer)
tests/
├── unit/            # Unit tests
└── integration/     # Integration tests
```

## Key Technologies

- **Python 3.11+**: Type hints, pattern matching
- **Pydantic 2.0**: Data validation
- **Typer + Rich**: CLI framework
- **sentence-transformers**: Text embeddings
- **HDBSCAN**: Clustering
- **Anthropic Claude**: LLM integration
- **msgraph-sdk**: M365 API
- **google-api-python-client**: Gmail API
- **aioimaplib**: Async IMAP

## Code Style

- Follow PEP 8 and Ruff rules
- Use type hints everywhere
- Docstrings for public functions
- 100 character line length

## Testing

```bash
# All tests
pytest

# With coverage
pytest --cov=src --cov-report=html

# Unit only
pytest tests/unit/

# Integration only
pytest tests/integration/
```

## CLI Entry Point

Main CLI: `src/cli_new.py`

```bash
# Installed as
email-analyzer <command>

# Or run directly
python -m src.cli_new <command>
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `ANTHROPIC_API_KEY` | For LLM features (`--llm` flag) |
| `EMAIL_ANALYZER_DATA_DIR` | Custom data directory |

## Data Storage

Default: `~/.email-analyzer/`

```
~/.email-analyzer/
├── mailboxes.json      # Mailbox registry
├── credentials/        # OAuth tokens
├── data/{mailbox}/     # Per-mailbox data
└── logs/               # Application logs
```

## Key Commands

| Command | Description |
|---------|-------------|
| `mailbox add` | Add email mailbox |
| `mailbox auth` | Authenticate |
| `extract` | Extract emails |
| `analyze` | Analyze patterns |
| `suggest` | Generate categories |
| `review` | Interactive review |
| `report` | Generate reports |
| `pipeline` | Full workflow |

## Architecture Notes

### Providers
- `src/providers/base.py`: Abstract provider interface
- `src/providers/m365/`: Microsoft Graph API
- `src/providers/gmail/`: Gmail API
- `src/providers/imap/`: Generic IMAP

### Analyzers
- `sender_analyzer.py`: Top senders, domains
- `subject_analyzer.py`: Patterns, keywords
- `semantic_analyzer.py`: HDBSCAN clustering
- `temporal_analyzer.py`: Frequency patterns
- `volume_analyzer.py`: Statistics

### Reports
- `html_report.py`: Interactive HTML
- `json_report.py`: JSON export
- `csv_report.py`: CSV files

## Documentation

- [README.md](README.md) - Overview
- [USAGE.md](USAGE.md) - Full usage guide
- [QUICK_REFERENCE.md](QUICK_REFERENCE.md) - Command reference
- [TESTING.md](TESTING.md) - Testing guide
- [M365_SETUP.md](M365_SETUP.md) - M365 setup
- [GMAIL_SETUP.md](GMAIL_SETUP.md) - Gmail setup
- [IMAP_SETUP.md](IMAP_SETUP.md) - IMAP setup
