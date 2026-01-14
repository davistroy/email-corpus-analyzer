# Email Corpus Analyzer

A Python-based system for extracting emails from multiple providers (Microsoft 365, Gmail, IMAP), analyzing patterns, and generating AI-assisted category suggestions.

## Features

- **Multi-Provider Support**: Connect to M365/Outlook, Gmail, or any IMAP server
- **Multi-Mailbox Management**: Analyze multiple email accounts simultaneously
- **Intelligent Analysis**: 5 analyzers (sender, subject, semantic, temporal, volume)
- **LLM-Powered Categorization**: Claude AI integration for smart category naming
- **Comprehensive Reports**: HTML, JSON, CSV, and Markdown output formats
- **Privacy-First**: All data stored locally with secure permissions

## Quick Start

### Prerequisites

- Python 3.11 or higher
- pip (Python package manager)

### Installation

```bash
# Clone the repository
git clone https://github.com/davistroy/email-corpus-analyzer.git
cd email-corpus-analyzer

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

# Install the package
pip install -e .

# Or install with development dependencies
pip install -e ".[dev]"
```

### Verify Installation

```bash
# Check the CLI is working
email-analyzer --help

# Check version
email-analyzer version
```

## Basic Usage

### 1. Add a Mailbox

```bash
# Microsoft 365 (personal)
email-analyzer mailbox add --name "Work" --provider m365 --email you@outlook.com

# Gmail
email-analyzer mailbox add --name "Personal" --provider gmail \
  --email you@gmail.com --credentials ~/credentials.json

# IMAP
email-analyzer mailbox add --name "Legacy" --provider imap \
  --email you@example.com --host imap.example.com
```

### 2. Authenticate

```bash
email-analyzer mailbox auth Work
```

### 3. Run Analysis Pipeline

```bash
# Complete workflow: extract -> analyze -> suggest -> review
email-analyzer pipeline

# Or with LLM-powered category naming
email-analyzer pipeline --llm
```

### 4. Generate Reports

```bash
# HTML report (interactive)
email-analyzer report --format html

# All formats at once
email-analyzer report --format all
```

## Command Overview

| Command | Description |
|---------|-------------|
| `mailbox add` | Add a new mailbox configuration |
| `mailbox list` | List all configured mailboxes |
| `mailbox auth` | Authenticate a mailbox |
| `mailbox info` | Show mailbox details |
| `mailbox remove` | Remove a mailbox |
| `extract` | Extract emails from mailboxes |
| `analyze` | Analyze email corpus for patterns |
| `suggest` | Generate category suggestions |
| `review` | Interactively review categories |
| `report` | Generate analysis reports |
| `pipeline` | Run complete workflow |
| `status` | Show system status |
| `version` | Display version info |

## Documentation

- [USAGE.md](USAGE.md) - Comprehensive usage guide
- [QUICK_REFERENCE.md](QUICK_REFERENCE.md) - Command quick reference
- [TESTING.md](TESTING.md) - Testing instructions
- [M365_SETUP.md](M365_SETUP.md) - Microsoft 365 configuration
- [GMAIL_SETUP.md](GMAIL_SETUP.md) - Gmail OAuth setup
- [IMAP_SETUP.md](IMAP_SETUP.md) - IMAP server configuration

## Project Structure

```
email-corpus-analyzer/
├── src/
│   ├── models/          # Pydantic data models
│   ├── providers/       # Email provider implementations
│   │   ├── m365/        # Microsoft 365/Outlook
│   │   ├── gmail/       # Google Gmail
│   │   └── imap/        # Generic IMAP
│   ├── analyzers/       # 5 analysis engines
│   ├── generators/      # Category generation
│   ├── reports/         # Report generators
│   ├── llm/             # Claude AI integration
│   ├── mailbox/         # Mailbox management
│   ├── extractors/      # Email extraction
│   ├── ui/              # Interactive review UI
│   ├── utils/           # Utilities
│   └── cli_new.py       # Typer CLI application
├── tests/
│   ├── unit/            # Unit tests
│   └── integration/     # Integration tests
├── specs/               # Design specifications
└── examples/            # Usage examples
```

## Technology Stack

- **Python 3.11+** - Modern Python with type hints
- **Typer + Rich** - Beautiful CLI interface
- **Pydantic 2.0** - Data validation
- **sentence-transformers** - Text embeddings
- **HDBSCAN** - Density-based clustering
- **Anthropic Claude** - LLM integration
- **msgraph-sdk** - Microsoft 365 API
- **google-api-python-client** - Gmail API

## Development

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/unit/test_html_parser.py

# Run integration tests
pytest tests/integration/
```

### Code Quality

```bash
# Linting
ruff check src/

# Type checking
mypy src/

# Fix linting issues
ruff check --fix src/
```

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `ANTHROPIC_API_KEY` | Claude API key for LLM features | For `--llm` flag |
| `EMAIL_ANALYZER_DATA_DIR` | Custom data directory | No |

## Security

- All data stored locally (no cloud uploads)
- File permissions: `0600` (user read/write only)
- Directory permissions: `0700` (user only)
- Credentials encrypted at rest
- OAuth tokens stored securely

## License

MIT License - See LICENSE file for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Write tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

For detailed contribution guidelines, see CONTRIBUTING.md.
