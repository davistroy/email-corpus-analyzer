# Architecture Review

Date: 2026-02-16  
Project: `email-corpus-analyzer`  
Scope: Quick architectural audit and technical debt assessment (read-only analysis synthesized into this document)

## Executive Summary

The codebase is a layered Python monolith with strong domain modeling, clear package boundaries, and substantial test coverage. The core risks are architectural drift and behavior divergence caused by duplicated orchestration paths and incorrect config override semantics.

Top issues to address first:

1. Config precedence bug in merge semantics (`src/config/models.py`).
2. Pipeline command not propagating declared flags to analyze/suggest stages (`src/cli/commands/pipeline.py`).
3. Split orchestration between service-layer and command-layer flows.

## Architecture Reconnaissance

### Tech Stack

- Python 3.10+ (`pyproject.toml`)
- Pydantic 2.x for models/config
- sentence-transformers + scikit-learn for semantic analysis
- Textual for TUI
- Jinja2 for HTML export
- MSAL + requests for Microsoft Graph
- google-api-python-client + google-auth for Gmail
- pytest + pytest-cov + ruff

### Pattern in Use

- Layered monolith:
  - `src/models`: domain schemas
  - `src/extractors`: provider integrations
  - `src/analyzers`: analysis logic
  - `src/generators`: suggestion logic
  - `src/services`: service orchestration
  - `src/cli`, `src/ui`: presentation interfaces

### Entry Points and Boundaries

- CLI entry points: `email-processor`, `python -m src.cli`
- External boundaries:
  - Microsoft Graph API (`src/extractors/graph_api_client.py`)
  - Gmail API (`src/extractors/gmail_client.py`)
  - Filesystem output and checkpoints (`src/utils/paths.py`, `src/utils/file_manager.py`)

### Dependency Graph

- Static import cycle scan across `src` found no cycles.
- Package boundaries are mostly clean.

## Findings

### Critical (Must Fix)

No confirmed critical defects from static audit.

### High (Must Fix)

1. Config precedence semantics are incorrect for explicit default resets.
   - File: `src/config/models.py:452`, `src/config/models.py:486`
   - Problem: merge logic uses "override differs from default" instead of "higher-precedence source explicitly set value."
   - Impact: higher-precedence configs cannot reliably set booleans back to `false` or intentionally set default-valued options.

2. Pipeline options are declared but not propagated.
   - File: `src/cli/commands/pipeline.py:70`, `src/cli/commands/pipeline.py:76`, `src/cli/commands/pipeline.py:193`
   - Problem: `--auto-clusters` / `--cluster-method` are accepted but not forwarded to `cmd_analyze`; suggest thresholds are hardcoded.
   - Impact: user intent is silently ignored; runtime behavior differs from CLI contract.

### Medium (Should Fix)

1. Orchestration duplication increases drift risk.
   - Files: `src/analyzers/__init__.py:41`, `src/services/analysis_service.py:37`, `src/cli/commands/pipeline.py:109`
   - Problem: multiple orchestrators implement overlapping sequencing and options.
   - Impact: feature updates can land in one path and miss others.

2. TUI swallows broad exceptions in state updates.
   - File: `src/ui/tui/app.py:266`, `src/ui/tui/app.py:274`, `src/ui/tui/app.py:283`
   - Problem: `except Exception: pass` suppresses actionable defects.
   - Impact: hidden UI failures and difficult debugging.

3. Gmail extraction is N+1 by design.
   - File: `src/extractors/gmail_client.py:159`, `src/extractors/gmail_client.py:169`
   - Problem: list IDs then fetch each message individually.
   - Impact: slower extraction and higher API quota pressure at scale.

4. Uses private argparse internals.
   - File: `src/cli/parsers.py:97`
   - Problem: accesses private parser internals for defaults.
   - Impact: upgrade fragility if argparse internals change.

### Low (Could Fix)

1. Large modules with mixed responsibilities.
   - Files: `src/generators/category_generator.py`, `src/ui/category_review.py`
2. Documentation drift on test/coverage claims.
   - File: `README.md:99`
3. Thread analyzer contract mismatch risk.
   - Files: `src/analyzers/__init__.py:28`, `src/models/analysis_results.py:56`

## Security Posture Notes

Positive:

- Token and output file permission hardening exists (`0600`/`0700`) with atomic writes.
- No hardcoded user credentials found in source.

Concerns:

- On Windows, permission hardening can silently degrade (`chmod` fallback paths).
- Dependency vulnerability audit tool was unavailable in this environment (`pip-audit` not installed), so CVE status is unverified.

## Testability and Reliability Notes

Positive:

- Strong automated test footprint and CI matrix.
- Coverage gate configured in CI (`--cov-fail-under=85`).

Gaps:

- Missing explicit tests for config reset-to-default precedence behavior.
- Behavioral parity tests needed once orchestration is unified.

## Accepted Architectural Decisions

The following recommendations were accepted:

1. Canonical orchestration path:
   - `PipelineService` is the runtime authority.
   - CLI becomes a thin adapter over services.

2. Config precedence semantics:
   - Strict source precedence with explicit override semantics.
   - If a higher-precedence source explicitly sets a value, that value wins even when it equals a model default.

3. Thread analysis contract:
   - Keep `ThreadAnalyzer` optional for now.
   - Add a formal optional field in output schema, guarded by flag/versioned output compatibility.

## Remediation Roadmap

### Quick Wins (<1 day each)

1. Fix config merge precedence and add tests.
   - Files: `src/config/models.py`, `tests/unit/test_config_models.py`
   - Effort: S
   - Risk: Medium
   - Dependency: None

2. Fix pipeline argument propagation.
   - Files: `src/cli/commands/pipeline.py`, related CLI tests
   - Effort: S
   - Risk: Low
   - Dependency: None

3. Replace silent broad exception handling in TUI update paths with targeted exceptions and logs.
   - Files: `src/ui/tui/app.py`
   - Effort: S
   - Risk: Low
   - Dependency: None

4. Correct README test/coverage claims.
   - Files: `README.md`
   - Effort: XS
   - Risk: Low
   - Dependency: None

### Short-Term Targets (1-2 weeks)

1. Refactor CLI pipeline to call `PipelineService` end-to-end.
   - Files: `src/cli/commands/pipeline.py`, `src/services/pipeline_service.py`
   - Effort: M
   - Risk: Medium
   - Dependency: quick wins complete

2. Unify analysis orchestration path and remove duplicate sequencing logic.
   - Files: `src/analyzers/__init__.py`, `src/services/analysis_service.py`, `src/cli/commands/analyze.py`
   - Effort: M
   - Risk: Medium
   - Dependency: pipeline-service alignment

3. Add dependency security checks to CI.
   - Files: `.github/workflows/ci.yml`
   - Effort: S
   - Risk: Low
   - Dependency: tooling selection

### Strategic Initiatives

1. Formalize optional thread analysis in schema and versioned outputs.
   - Files: `src/models/analysis_results.py`, analyzers/services/CLI output code, tests
   - Effort: M
   - Risk: Medium
   - Dependency: orchestration unification

2. Break up oversized modules for clearer boundaries.
   - Files: `src/generators/category_generator.py`, `src/ui/category_review.py`
   - Effort: L
   - Risk: Medium
   - Dependency: ADR and stable interfaces

### Long-Term Considerations

1. Locked dependency workflow for reproducibility.
   - Effort: M
2. Gmail extraction optimization strategy for quota and latency.
   - Effort: L

## ADRs to Add

1. Service-first orchestration (`PipelineService` as system-of-record).
2. Config precedence and explicit override semantics.
3. Optional analyzer output versioning policy (thread analysis).
4. Dependency security and lock strategy.
