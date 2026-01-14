# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Test Commands

```bash
# Install dependencies
pip install -r requirements.txt
pip install -e ".[dev]"  # Install with dev dependencies

# Run tests
pytest                           # All tests with coverage
pytest tests/unit/              # Unit tests only
pytest tests/unit/test_html_parser.py  # Single test file
pytest -k "test_name"           # Run specific test by name

# Linting
ruff check src/
ruff check src/ --fix           # Auto-fix issues

# Run CLI commands
python -m src.cli --help
python -m src.cli pipeline --user-email user@hotmail.com
python -m src.cli extract --user-email user@hotmail.com
python -m src.cli analyze
python -m src.cli suggest
python -m src.cli review
```

## Architecture

This system extracts emails from M365/Hotmail, analyzes patterns, and generates category suggestions through a four-stage pipeline:

```
Extract → Analyze → Suggest → Review
```

### Core Pipeline Modules

- **`src/extractors/`** - Email extraction from M365 via MCP server. `m365_extractor.py` handles batched extraction with checkpointing. HTML content parsed via `html_parser.py`.

- **`src/analyzers/`** - Five independent analyzers run on the corpus:
  - `sender_analyzer.py` - Sender frequency, domain patterns
  - `subject_analyzer.py` - Subject line patterns, prefixes
  - `semantic_analyzer.py` - Content clustering via sentence-transformers
  - `temporal_analyzer.py` - Time-based patterns
  - `volume_analyzer.py` - Statistical metrics

- **`src/generators/`** - Category suggestion from analysis results. `template_matcher.py` matches predefined templates (financial, shopping, social). `confidence_scorer.py` assigns scores.

- **`src/ui/category_review.py`** - Interactive CLI for reviewing/approving suggested categories.

### Data Models

All models in `src/models/` use Pydantic v2. Key models:
- `Email` - Single email with metadata and content
- `Corpus` - Collection of emails with metadata
- `AnalysisResults` - Combined output from all analyzers
- `Category` - Suggested category with confidence score
- `CategoryTemplate` - Predefined category patterns (6 templates)

### Entry Points

- `src/cli.py` - Primary CLI entry point (`python -m src.cli`)
- `src/main.py` - Alternative entry point with `EmailProcessorCLI` class

### Output Files

Default output: `~/data/outputs/` (configurable via `--output-dir`)

| File | Description |
|------|-------------|
| `email_corpus.json` | Extracted email data |
| `corpus_analysis_results.json` | Analysis from 5 analyzers |
| `category_suggestions.json` | Generated categories |
| `category_suggestions_report.md` | Human-readable report |
| `approved_categories.json` | Final approved categories |

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
- scikit-learn for clustering
- Local JSON storage (no database)
- M365 MCP server for email access (requires separate authentication)
