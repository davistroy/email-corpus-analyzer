# Email Corpus Extraction and Analysis System

A Python-based system for extracting emails from Hotmail/Outlook via M365 MCP, analyzing patterns, and generating AI-assisted category suggestions.

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
```

### Basic Commands

**Default output location:** `~/data/outputs` (created automatically with secure permissions)

```bash
# Run complete pipeline (extract → analyze → suggest → review)
python -m src.cli pipeline --user-email your.email@hotmail.com

# Or run individual steps:
python -m src.cli extract --user-email your.email@hotmail.com  # Extract emails
python -m src.cli analyze                                       # Analyze patterns
python -m src.cli suggest                                       # Generate categories
python -m src.cli review                                        # Review interactively

# Use custom output directory
python -m src.cli --output-dir ~/my-emails pipeline --user-email your.email@hotmail.com

# Get help
python -m src.cli --help
python -m src.cli <command> --help  # For specific command help
```

### Output Files

| File | Description |
|------|-------------|
| `email_corpus.json` | Extracted email data |
| `corpus_analysis_results.json` | Analysis results (5 analyzers) |
| `category_suggestions.json` | AI-generated category suggestions |
| `category_suggestions_report.md` | Human-readable report |
| `approved_categories.json` | Final approved categories |

**For complete usage documentation, see [docs/USAGE.md](docs/USAGE.md) and [docs/QUICK_REFERENCE.md](docs/QUICK_REFERENCE.md)**

---

## Architecture

### Technology Stack
- **Python**: 3.10+ (type hints, pattern matching)
- **Text Embeddings**: sentence-transformers >= 2.0.0
- **Clustering**: scikit-learn == 1.7.1
- **HTML Parsing**: BeautifulSoup4 >= 4.12.0 + lxml
- **Data Validation**: Pydantic >= 2.0.0
- **Progress Tracking**: tqdm >= 4.66.0
- **Testing**: pytest >= 7.4.0

### Project Structure

```
email-corpus-analyzer/
├── src/
│   ├── models/              # 7 Pydantic data models
│   ├── extractors/          # Email extraction (M365, HTML parsing)
│   ├── analyzers/           # 5 analysis modules
│   ├── generators/          # Category suggestion generation
│   ├── ui/                  # Interactive category review
│   └── utils/               # Logging, file management, paths
├── tests/
│   ├── contract/            # Contract tests
│   ├── integration/         # Integration tests
│   └── unit/                # Unit tests
├── docs/                    # Documentation
├── scripts/                 # Standalone scripts
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
4. **Privacy & Data Security** - Local-only storage, secure permissions
5. **Modular Components** - Independent, testable modules
6. **Error Resilience** - Debug logging, graceful degradation
7. **Performance Transparency** - Progress indicators for long operations

## Development

### Prerequisites
- Python 3.10 or higher
- M365 MCP server configured and authenticated (for email extraction)

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
- [M365 Setup](docs/M365_SETUP.md)
- [Output Configuration](docs/OUTPUT_CONFIGURATION.md)
- [Integration Guide](docs/INTEGRATION.md)

## License

Internal project - Email Corpus Analysis System
