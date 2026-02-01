# Implementation Plan v2

**Generated:** 2025-01-14
**Based On:** RECOMMENDATIONS.md (Post-Phase 5 Assessment)
**Total Phases:** 3 (Phases 6-8)

## ✅ ALL PHASES COMPLETE

| Phase | Status | Completion Date | Tests |
|-------|--------|-----------------|-------|
| Phase 6 | ✅ Complete | 2025-01-14 | 1189 |
| Phase 7 | ✅ Complete | 2025-01-14 | 1289 |
| Phase 8 | ✅ Complete | 2025-01-14 | 1365 |

**Final Test Count:** 1365 tests
**Final Coverage:** 84%

---

## Plan Overview

This plan continues from the completed Phase 1-5 implementation (1144 tests, 84% coverage). The focus shifts from core functionality to **production hardening**: better error handling, extensibility patterns, and end-to-end validation.

### Phase Summary Table

| Phase | Focus Area | Key Deliverables | Est. Tokens | Dependencies |
|-------|------------|------------------|-------------|--------------|
| 6 | Error Handling & Quick Wins | Exception hierarchy, config validation, Levenshtein naming | ~70K | None |
| 7 | Architecture Refinement | Abstract analyzer, service layer, integration tests | ~95K | Phase 6 |
| 8 | Capabilities & Polish | Thread analysis, bulk TUI operations, rule export | ~85K | Phase 7 |

**Total Estimated:** ~250,000 tokens across 3 phases

---

## Phase 6: Error Handling & Quick Wins

**Estimated Effort:** ~70,000 tokens (including testing/fixes)
**Dependencies:** None (builds on Phase 5 complete)
**Parallelizable:** Yes - 3 independent tracks

### Goals
- Improve error messages with actionable recovery steps
- Add config validation command
- Implement quick wins from recommendations
- Standardize logging across modules

### Track 6A: Exception Hierarchy & Error Messages (25,000 tokens)

#### 6A.1 Create Exception Hierarchy
**Recommendation Ref:** A3, U1
**Files Affected:**
- `src/exceptions.py` (new)
- `src/cli.py` (modify error handlers)

**Description:**
Create structured exception classes that capture context and provide recovery guidance.

```python
# src/exceptions.py
class EmailAnalyzerError(Exception):
    """Base exception with recovery hint support."""
    def __init__(self, message: str, recovery_hint: str = None, context: dict = None):
        super().__init__(message)
        self.recovery_hint = recovery_hint
        self.context = context or {}

class CorpusNotFoundError(EmailAnalyzerError):
    """Raised when corpus file doesn't exist."""
    def __init__(self, path: Path):
        super().__init__(
            f"Corpus file not found: {path}",
            recovery_hint="Run extraction first: python -m src.cli extract --user-email YOUR_EMAIL",
            context={"path": str(path)}
        )
```

**Acceptance Criteria:**
- [x] Base `EmailAnalyzerError` with message, recovery_hint, context
- [x] `CorpusNotFoundError`, `CorpusParseError` for corpus issues
- [x] `ConfigurationError`, `ConfigValidationError` for config issues
- [x] `AnalysisError`, `ClusteringError` for analysis issues
- [x] `ExtractionError`, `M365AuthError` for extraction issues
- [x] All exceptions include actionable recovery hints
- [x] 100% test coverage for exception classes

**Test Cases:**
```python
def test_exception_includes_recovery_hint():
    err = CorpusNotFoundError(Path("/missing.json"))
    assert "extraction first" in err.recovery_hint

def test_exception_context_contains_path():
    err = CorpusNotFoundError(Path("/missing.json"))
    assert err.context["path"] == "/missing.json"
```

---

#### 6A.2 Update CLI Error Handlers
**Recommendation Ref:** U1
**Files Affected:**
- `src/cli.py` (all cmd_* methods)

**Description:**
Replace generic `except Exception` with specific exception handling that formats errors based on type.

**Acceptance Criteria:**
- [x] Each command catches specific exceptions
- [x] Error output includes recovery hints
- [x] `--verbose` shows full stack trace
- [x] `--json` output includes structured error with recovery_hint
- [x] Non-zero exit codes for different error types (1=user error, 2=system error)

**Test Cases:**
```python
def test_corpus_not_found_shows_recovery_hint(capsys):
    cli.cmd_analyze()  # with missing corpus
    captured = capsys.readouterr()
    assert "Run extraction first" in captured.err

def test_verbose_shows_stack_trace(capsys):
    # --verbose flag enabled
    assert "Traceback" in captured.err
```

---

### Track 6B: Config Validation & CLI Help (20,000 tokens)

#### 6B.1 Add Config Validation Command
**Recommendation Ref:** U2
**Files Affected:**
- `src/cli.py` (add cmd_config_validate)
- `src/config/loader.py` (add validation helpers)

**Description:**
Add `config validate` command that checks configuration without running commands.

```bash
python -m src.cli config validate

=== Configuration Validation ===
Source: ~/.email-analyzer/config.yaml

✓ user_email: valid (user@example.com)
✓ output_dir: exists and writable
✓ analyze.num_clusters: valid (15)
✗ suggest.min_cluster_percentage: must be 0-100 (got: 150.0)

1 error found. Fix before running commands.
```

**Acceptance Criteria:**
- [x] `config validate` command added to CLI
- [x] Validates all config fields against Pydantic models
- [x] Checks runtime conditions (path exists, writable)
- [x] Shows clear ✓/✗ status for each field
- [x] Returns exit code 1 on validation failure
- [x] Works with --json flag for machine-readable output

**Test Cases:**
```python
def test_config_validate_valid_config():
    result = runner.invoke(cli, ["config", "validate"])
    assert result.exit_code == 0

def test_config_validate_invalid_value():
    # With invalid min_cluster_percentage
    result = runner.invoke(cli, ["config", "validate"])
    assert result.exit_code == 1
    assert "min_cluster_percentage" in result.output
```

---

#### 6B.2 Enhanced CLI Help with Examples
**Recommendation Ref:** U3
**Files Affected:**
- `src/cli.py` (setup_parser method)

**Description:**
Add epilog sections to subparsers with usage examples and flag explanations.

**Acceptance Criteria:**
- [x] Each subcommand has epilog with examples
- [x] Explains when to use competing flags (--auto-clusters vs --num-clusters)
- [x] Documents flag interactions
- [x] Uses RawDescriptionHelpFormatter to preserve formatting

---

### Track 6C: Quick Wins (25,000 tokens)

#### 6C.1 Levenshtein Distance for Name Similarity
**Recommendation Ref:** Q1
**Files Affected:**
- `src/generators/category_generator.py` (lines 285-295)

**Description:**
Replace substring matching with proper string similarity scoring.

```python
from difflib import SequenceMatcher

def name_similarity(name1: str, name2: str) -> float:
    """Calculate similarity ratio between category names."""
    return SequenceMatcher(None, name1.lower(), name2.lower()).ratio()

# In merge detection:
if name_similarity(cat1.name, cat2.name) > self.config.merge_similarity_threshold:
    # Consider merging
```

**Acceptance Criteria:**
- [x] Use difflib.SequenceMatcher for similarity
- [x] Add `merge_similarity_threshold` to config (default: 0.8)
- [x] Log similarity scores at DEBUG level
- [x] Update merge detection logic
- [x] Test cases for similar but not identical names

**Test Cases:**
```python
def test_similarity_catches_near_matches():
    assert name_similarity("Financial Services", "Finance Services") > 0.8

def test_similarity_rejects_different_names():
    assert name_similarity("Newsletter", "Banking") < 0.5
```

---

#### 6C.2 Unified Logging Configuration
**Recommendation Ref:** A4
**Files Affected:**
- `src/utils/logger.py` (enhance)
- `src/ui/category_review.py` (replace print with logger)
- Multiple modules (audit for print statements)

**Description:**
Ensure all modules use consistent logging patterns.

**Acceptance Criteria:**
- [x] All modules use `logging.getLogger(__name__)`
- [x] Replace print() with logger.info() in category_review.py
- [x] `setup_logging()` configures root logger
- [x] Support --log-file option
- [x] Use rich.logging.RichHandler for console

---

#### 6C.3 Test Fixture Standardization
**Recommendation Ref:** D3
**Files Affected:**
- `tests/conftest.py` (create/enhance)
- Multiple test files (refactor to use shared fixtures)

**Description:**
Create shared pytest fixtures in conftest.py for reuse across test files.

**Acceptance Criteria:**
- [x] `sample_corpus` fixture with 100 diverse emails
- [x] `sample_analysis_results` fixture
- [x] `sample_categories` fixture
- [x] `temp_output_dir` fixture for file tests
- [x] Document fixture purposes
- [x] Refactor existing tests to use shared fixtures

---

### Phase 6 Testing Requirements
- All new code has 100% test coverage
- Existing tests continue to pass
- Error handling tested with mock failures
- Config validation tested with invalid inputs

### Phase 6 Completion Checklist
- [x] Exception hierarchy implemented and tested
- [x] CLI error handlers updated
- [x] Config validate command working
- [x] CLI help improved
- [x] Levenshtein similarity implemented
- [x] Logging unified
- [x] Test fixtures standardized
- [x] All 1144+ tests passing (1189 tests)
- [x] Coverage maintained at 84%+

**Phase 6 Completed:** 2025-01-14

---

## Phase 7: Architecture Refinement

**Estimated Effort:** ~95,000 tokens (including testing/fixes)
**Dependencies:** Phase 6 complete
**Parallelizable:** Yes - 2 tracks (after 7A.1)

### Goals
- Create abstract analyzer interface for extensibility
- Extract service layer from CLI
- Build comprehensive integration test suite
- Document extension points

### Track 7A: Abstract Interfaces (35,000 tokens)

#### 7A.1 Abstract Analyzer Base Class
**Recommendation Ref:** A1
**Files Affected:**
- `src/analyzers/base.py` (new)
- `src/analyzers/__init__.py` (update exports)
- All analyzer files (update inheritance)

**Description:**
Create ABC that defines analyzer contract and enables extension.

```python
# src/analyzers/base.py
from abc import ABC, abstractmethod
from typing import TypeVar, Generic

T = TypeVar('T')

class BaseAnalyzer(ABC, Generic[T]):
    """Abstract base for all email analyzers."""

    @abstractmethod
    def analyze(self, emails: list[Email], **kwargs) -> T:
        """Analyze emails and return typed results."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable analyzer name for logging."""
        pass

    def supports_incremental(self) -> bool:
        """Override to enable incremental analysis."""
        return False

    def validate_input(self, emails: list[Email]) -> None:
        """Validate input before analysis. Override for custom validation."""
        if not emails:
            raise AnalysisError(f"{self.name} requires non-empty email list")
```

**Acceptance Criteria:**
- [x] `BaseAnalyzer` ABC with required methods
- [x] Generic type parameter for results
- [x] All 7 analyzers inherit from BaseAnalyzer
- [x] Analyzer registry via `__subclasses__()`
- [x] Type hints preserved for return types
- [x] Documentation for extending

**Test Cases:**
```python
def test_all_analyzers_inherit_from_base():
    from src.analyzers import base
    analyzers = base.BaseAnalyzer.__subclasses__()
    assert len(analyzers) >= 7

def test_analyzer_name_property_required():
    class BadAnalyzer(BaseAnalyzer):
        def analyze(self, emails): pass
    with pytest.raises(TypeError):
        BadAnalyzer()  # Missing name property
```

---

#### 7A.2 Update Existing Analyzers
**Recommendation Ref:** A1
**Files Affected:**
- `src/analyzers/sender_analyzer.py`
- `src/analyzers/subject_analyzer.py`
- `src/analyzers/semantic_analyzer.py`
- `src/analyzers/temporal_analyzer.py`
- `src/analyzers/volume_analyzer.py`
- `src/analyzers/hierarchical_analyzer.py`
- `src/analyzers/cluster_optimizer.py`

**Description:**
Migrate each analyzer to inherit from BaseAnalyzer.

**Acceptance Criteria:**
- [x] Each analyzer inherits from BaseAnalyzer
- [x] Each implements `name` property
- [x] SemanticAnalyzer overrides `supports_incremental()`
- [x] Type hints updated for generic results
- [x] All existing tests pass

---

### Track 7B: Service Layer (40,000 tokens)

#### 7B.1 Create Service Layer Structure
**Recommendation Ref:** A2
**Files Affected:**
- `src/services/__init__.py` (new)
- `src/services/extraction_service.py` (new)
- `src/services/analysis_service.py` (new)
- `src/services/suggestion_service.py` (new)
- `src/services/pipeline_service.py` (new)

**Description:**
Extract orchestration logic from CLI into reusable service classes.

```python
# src/services/analysis_service.py
class AnalysisService:
    """Orchestrates email corpus analysis."""

    def __init__(self, config: AnalyzeConfig):
        self.config = config
        self._analyzers = self._build_analyzers()

    def run(
        self,
        corpus: Corpus,
        incremental: bool = False,
        progress_callback: Callable = None
    ) -> AnalysisResults:
        """Run all analyzers on corpus."""
        results = {}
        for analyzer in self._analyzers:
            if progress_callback:
                progress_callback(f"Running {analyzer.name}...")
            results[analyzer.name] = analyzer.analyze(corpus.emails)
        return AnalysisResults(**results)
```

**Acceptance Criteria:**
- [x] ExtractionService handles M365 extraction
- [x] AnalysisService runs all analyzers
- [x] SuggestionService generates categories
- [x] PipelineService orchestrates full workflow
- [x] Services receive config, return results (no CLI awareness)
- [x] Progress via callbacks
- [x] Services independently testable

---

#### 7B.2 Refactor CLI to Use Services
**Recommendation Ref:** A2
**Files Affected:**
- `src/cli.py` (major refactor)

**Description:**
CLI becomes thin layer that parses arguments and calls services.

**Acceptance Criteria:**
- [x] Each cmd_* method uses appropriate service
- [x] CLI handles only argument parsing and output formatting
- [x] Service exceptions caught and formatted by CLI
- [x] All existing CLI tests pass
- [x] CLI code reduced by ~40%

---

### Track 7C: Integration Tests (20,000 tokens)

#### 7C.1 Integration Test Suite
**Recommendation Ref:** D1
**Files Affected:**
- `tests/integration/__init__.py` (enhance)
- `tests/integration/test_pipeline.py` (new)
- `tests/integration/test_incremental.py` (new)
- `tests/integration/test_config.py` (new)

**Description:**
Create end-to-end tests that verify full workflows.

**Acceptance Criteria:**
- [x] Test full pipeline with fixture corpus
- [x] Test incremental extraction merges correctly
- [x] Test config file loading precedence
- [x] Test CLI command execution via subprocess
- [x] Mock M365 MCP server responses
- [x] Use temp directories for outputs
- [x] Tests run in CI pipeline

**Test Cases:**
```python
def test_full_pipeline_produces_approved_categories(temp_dir, sample_corpus):
    """Run extract → analyze → suggest → review and verify output."""

def test_incremental_extraction_deduplicates(temp_dir):
    """Extract twice with overlap, verify no duplicates."""

def test_project_config_overrides_global(temp_dir):
    """Create both config files, verify precedence."""
```

---

### Phase 7 Testing Requirements
- All services have 100% test coverage
- Integration tests cover main workflows
- ABC enforcement verified
- Existing unit tests continue to pass

### Phase 7 Completion Checklist
- [x] BaseAnalyzer ABC implemented
- [x] All analyzers migrated
- [x] Service layer created
- [x] CLI refactored to use services
- [x] Integration test suite complete
- [x] Extension documentation written
- [x] All tests passing (1289 tests)
- [x] Coverage maintained at 84%+

**Phase 7 Completed:** 2025-01-14

---

## Phase 8: Capabilities & Polish

**Estimated Effort:** ~85,000 tokens (including testing/fixes)
**Dependencies:** Phase 7 complete
**Parallelizable:** Yes - 2 tracks

### Goals
- Add email thread grouping
- Implement bulk TUI operations
- Create email rule export
- Final documentation polish

### Track 8A: Email Thread Analysis (40,000 tokens)

#### 8A.1 Thread Detection
**Recommendation Ref:** N1
**Files Affected:**
- `src/models/email.py` (add thread_id field)
- `src/analyzers/thread_analyzer.py` (new)
- `src/analyzers/__init__.py` (register)

**Description:**
Parse email headers to identify conversation threads.

**Acceptance Criteria:**
- [x] Parse `In-Reply-To` and `References` headers
- [x] Generate unique thread_id for each conversation
- [x] Single emails get their own thread_id
- [x] ThreadAnalyzer groups emails by thread
- [x] Analysis can operate at email or thread level

---

#### 8A.2 Thread-Aware Clustering
**Recommendation Ref:** N1
**Files Affected:**
- `src/analyzers/semantic_analyzer.py`
- `src/config/models.py` (add thread_mode option)

**Description:**
Option to cluster at thread level instead of individual emails.

**Acceptance Criteria:**
- [x] `analyze.thread_mode` config option (default: email)
- [x] When thread_mode=thread, use thread representative for clustering
- [x] Thread representative = first email or concatenated subjects
- [x] Statistics show "X emails in Y threads"

---

### Track 8B: TUI Enhancements & Export (45,000 tokens)

#### 8B.1 Bulk Operations in TUI
**Recommendation Ref:** U4
**Files Affected:**
- `src/ui/tui/widgets/category_table.py`
- `src/ui/tui/dialogs/bulk_action_dialog.py` (new)
- `src/ui/tui/app.py`

**Description:**
Add multi-select and bulk action support to TUI.

**Acceptance Criteria:**
- [x] Space toggles selection on current category
- [x] Ctrl+A selects all visible
- [x] Shift+A accepts all selected
- [x] Shift+D deletes all selected
- [x] Confirmation dialog for bulk actions
- [x] Pattern-based selection ("Accept all confidence > 80%")

---

#### 8B.2 Category Search/Filter
**Recommendation Ref:** U5
**Files Affected:**
- `src/ui/tui/widgets/search_input.py` (new)
- `src/ui/tui/widgets/category_table.py`
- `src/ui/tui/app.py`

**Description:**
Add search bar for filtering categories.

**Acceptance Criteria:**
- [x] `/` activates search
- [x] Filter by name (fuzzy match)
- [x] Filter by source: `source:cluster`
- [x] Filter by confidence: `confidence:>80`
- [x] Esc clears filter
- [x] "X of Y categories" indicator

---

#### 8B.3 Email Rule Export
**Recommendation Ref:** N3
**Files Affected:**
- `src/exporters/rule_exporter.py` (new)
- `src/cli.py` (add export format)

**Description:**
Export approved categories as email rules.

**Acceptance Criteria:**
- [x] `export --format outlook-rules` generates XML
- [x] `export --format gmail-filters` generates XML
- [x] Map category criteria to rule conditions
- [x] Include import instructions
- [x] Handle categories without clear rules (warn user)

---

### Phase 8 Testing Requirements
- Thread detection tested with real email headers
- Bulk TUI operations tested with mock interactions
- Rule export validated against schema
- All existing tests pass

### Phase 8 Completion Checklist
- [x] Thread analyzer implemented
- [x] Thread-aware clustering working
- [x] Bulk TUI operations functional
- [x] Search/filter in TUI working
- [x] Rule export for Outlook/Gmail
- [x] All documentation updated
- [x] All tests passing (1365 tests)
- [x] Final coverage 84%

**Phase 8 Completed:** 2025-01-14

---

## Parallel Work Opportunities

| Work Item A | Can Run With | Notes |
|-------------|--------------|-------|
| 6A (Exceptions) | 6B (Config validate) | Independent tracks |
| 6A (Exceptions) | 6C (Quick wins) | Independent tracks |
| 6B (Config validate) | 6C (Quick wins) | Independent tracks |
| 7A.2 (Migrate analyzers) | 7C (Integration tests) | After 7A.1 complete |
| 7B (Service layer) | 7C (Integration tests) | After 7A.1 complete |
| 8A (Thread analysis) | 8B (TUI enhancements) | Independent tracks |

---

## Risk Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Service layer refactor breaks CLI | Medium | High | Comprehensive integration tests first |
| ABC migration breaks analyzers | Low | Medium | Incremental migration, test each analyzer |
| Thread detection complexity | Medium | Medium | Start with simple header parsing, iterate |
| Rule export format changes | Low | Low | Document as "best effort", warn about limitations |

---

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Test count | 1300+ | pytest --collect-only |
| Coverage | 85%+ | pytest --cov |
| Error messages | 100% with recovery hints | Manual review |
| CLI help | Examples for all commands | Manual review |
| Extension docs | Complete guide | docs/EXTENDING.md exists |

---

*Implementation plan generated by Claude on 2025-01-14*
