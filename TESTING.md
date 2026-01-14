# Testing Guide

This guide covers how to run tests and validate the Email Corpus Analyzer.

## Quick Start

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html
```

## Test Structure

```
tests/
├── unit/                          # Unit tests
│   ├── test_html_parser.py        # HTML parsing tests
│   ├── test_validators.py         # Input validation tests
│   ├── test_mailbox_registry.py   # Mailbox management tests
│   ├── test_providers.py          # Provider abstraction tests
│   ├── test_llm_client.py         # LLM client tests
│   ├── test_confidence_scorer.py  # Scoring algorithm tests
│   └── test_sender_classifier.py  # Sender classification tests
├── integration/                   # Integration tests
│   ├── test_full_pipeline.py      # End-to-end tests
│   ├── test_async_extraction.py   # Async extraction tests
│   ├── test_llm_integration.py    # LLM integration tests
│   ├── test_mailbox_management.py # Mailbox workflow tests
│   └── test_providers.py          # Provider integration tests
└── contract/                      # Contract tests (API contracts)
```

## Running Tests

### All Tests

```bash
pytest
```

### Unit Tests Only

```bash
pytest tests/unit/
```

### Integration Tests Only

```bash
pytest tests/integration/
```

### Specific Test File

```bash
pytest tests/unit/test_html_parser.py
```

### Specific Test Function

```bash
pytest tests/unit/test_html_parser.py::test_parse_simple_html
```

### With Verbose Output

```bash
pytest -v
```

### With Print Statements

```bash
pytest -s
```

### Stop on First Failure

```bash
pytest -x
```

---

## Test Coverage

### Generate Coverage Report

```bash
pytest --cov=src --cov-report=html
```

This creates an HTML report in `htmlcov/index.html`.

### View Coverage Summary

```bash
pytest --cov=src --cov-report=term-missing
```

Shows which lines are not covered.

### Coverage Thresholds

```bash
pytest --cov=src --cov-fail-under=80
```

Fails if coverage is below 80%.

---

## Test Categories

### Unit Tests

Test individual components in isolation:

```bash
# Test HTML parser
pytest tests/unit/test_html_parser.py

# Test validators
pytest tests/unit/test_validators.py

# Test mailbox registry
pytest tests/unit/test_mailbox_registry.py
```

### Integration Tests

Test components working together:

```bash
# Test full pipeline
pytest tests/integration/test_full_pipeline.py

# Test async extraction
pytest tests/integration/test_async_extraction.py
```

### Async Tests

Tests that use async/await are handled automatically:

```python
# pytest.ini configured with asyncio_mode = "auto"
async def test_async_extraction():
    result = await extractor.extract()
    assert result is not None
```

---

## Writing Tests

### Test File Naming

- Test files: `test_*.py`
- Test classes: `Test*`
- Test functions: `test_*`

### Example Unit Test

```python
# tests/unit/test_example.py
import pytest
from src.models.email import Email

def test_email_creation():
    """Test Email model creation."""
    email = Email(
        id="test-123",
        sender_email="sender@example.com",
        sender_name="Sender",
        subject="Test Subject",
        body_text="Test body",
    )
    assert email.id == "test-123"
    assert email.sender_email == "sender@example.com"

def test_email_validation():
    """Test Email validation fails for invalid data."""
    with pytest.raises(ValueError):
        Email(
            id="",  # Invalid: empty ID
            sender_email="not-an-email",  # Invalid format
            subject="Test",
        )
```

### Example Async Test

```python
# tests/integration/test_async_example.py
import pytest
from src.extractors.async_extractor import AsyncExtractor

@pytest.mark.asyncio
async def test_async_extraction():
    """Test async email extraction."""
    extractor = AsyncExtractor()
    result = await extractor.extract_batch(limit=10)
    assert len(result) <= 10
```

### Example Fixture

```python
# tests/conftest.py
import pytest
from src.models.corpus import Corpus
from src.models.email import Email

@pytest.fixture
def sample_corpus():
    """Create a sample corpus for testing."""
    emails = [
        Email(id=f"email-{i}", sender_email=f"sender{i}@example.com", subject=f"Subject {i}")
        for i in range(10)
    ]
    return Corpus(emails=emails)

@pytest.fixture
def mock_provider(mocker):
    """Create a mock email provider."""
    return mocker.MagicMock()
```

---

## Testing Without Live APIs

### Mock Providers

For testing without real email providers:

```python
# tests/conftest.py
@pytest.fixture
def mock_m365_provider(mocker):
    """Mock M365 provider for offline testing."""
    mock = mocker.patch('src.providers.m365.M365Provider')
    mock.return_value.fetch_emails.return_value = [
        {"id": "1", "subject": "Test", "from": {"email": "test@example.com"}}
    ]
    return mock
```

### Test Data

Create test fixtures in `tests/fixtures/`:

```
tests/fixtures/
├── sample_emails.json
├── sample_corpus.json
└── sample_analysis.json
```

Load in tests:

```python
import json
from pathlib import Path

@pytest.fixture
def sample_emails():
    fixture_path = Path(__file__).parent / "fixtures" / "sample_emails.json"
    with open(fixture_path) as f:
        return json.load(f)
```

---

## Environment Setup for Tests

### Install Test Dependencies

```bash
pip install -e ".[dev]"
```

This installs:
- `pytest>=7.4.0`
- `pytest-cov>=4.1.0`
- `pytest-asyncio>=0.21.0`
- `ruff>=0.1.0`
- `mypy>=1.0.0`

### Environment Variables for Integration Tests

Some integration tests need environment variables:

```bash
# For LLM integration tests
export ANTHROPIC_API_KEY="your-test-key"

# Run integration tests
pytest tests/integration/test_llm_integration.py
```

### Skip Tests Requiring Credentials

Tests that need real credentials are marked:

```python
@pytest.mark.requires_credentials
def test_real_m365_connection():
    ...
```

Skip them with:

```bash
pytest -m "not requires_credentials"
```

---

## Continuous Integration

### pytest.ini Configuration

The project is configured in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = "test_*.py"
python_classes = "Test*"
python_functions = "test_*"
addopts = "-v --cov=src --cov-report=term-missing"
asyncio_mode = "auto"
```

### Running in CI

```bash
# Install dependencies
pip install -e ".[dev]"

# Run tests with coverage
pytest --cov=src --cov-report=xml

# Run linting
ruff check src/

# Run type checking
mypy src/
```

---

## Manual Testing Checklist

For manual validation before release:

### Mailbox Management

- [ ] Add M365 mailbox (personal)
- [ ] Add Gmail mailbox
- [ ] Add IMAP mailbox
- [ ] List mailboxes with filters
- [ ] Show mailbox info
- [ ] Authenticate each provider
- [ ] Remove mailbox

### Extraction

- [ ] Extract from single mailbox
- [ ] Extract from all mailboxes
- [ ] Resume interrupted extraction
- [ ] Verify checkpoint saves

### Analysis

- [ ] Analyze with HDBSCAN
- [ ] Analyze with KMeans
- [ ] Analyze with LLM naming
- [ ] Verify cluster quality

### Suggestions

- [ ] Generate suggestions
- [ ] Adjust thresholds
- [ ] Verify category quality

### Review

- [ ] Accept categories
- [ ] Rename categories
- [ ] Merge categories
- [ ] Delete categories
- [ ] Skip and re-review

### Reports

- [ ] Generate HTML report
- [ ] Generate JSON report
- [ ] Generate CSV report
- [ ] Generate Markdown report
- [ ] Cross-mailbox report

### Pipeline

- [ ] Run full pipeline
- [ ] Pipeline with --llm
- [ ] Pipeline with --skip-extract
- [ ] Pipeline with --skip-review

### Error Handling

- [ ] Invalid mailbox name
- [ ] Missing credentials
- [ ] Network errors
- [ ] Rate limiting

---

## Debugging Tests

### Run with Debug Output

```bash
pytest -v -s --tb=long
```

### Use pdb Debugger

```bash
pytest --pdb
```

Or in test code:

```python
def test_something():
    import pdb; pdb.set_trace()
    result = some_function()
```

### Logging in Tests

```python
import logging

def test_with_logging(caplog):
    with caplog.at_level(logging.DEBUG):
        result = some_function()
    assert "expected message" in caplog.text
```

---

## Performance Testing

### Measure Test Duration

```bash
pytest --durations=10
```

Shows 10 slowest tests.

### Profile Tests

```bash
pytest --profile
```

---

## Code Quality Checks

### Linting with Ruff

```bash
# Check for issues
ruff check src/

# Auto-fix issues
ruff check --fix src/
```

### Type Checking with mypy

```bash
mypy src/
```

### Format Check

```bash
ruff format --check src/
```

---

## Troubleshooting Test Issues

### "ModuleNotFoundError"

Install the package in development mode:

```bash
pip install -e .
```

### "No tests collected"

Check test file naming follows `test_*.py` pattern.

### "Fixture not found"

Ensure fixtures are in `conftest.py` or imported correctly.

### Async Test Failures

Ensure `pytest-asyncio` is installed and configured:

```bash
pip install pytest-asyncio
```

### Slow Tests

Use markers to skip slow tests:

```python
@pytest.mark.slow
def test_slow_operation():
    ...
```

```bash
pytest -m "not slow"
```
