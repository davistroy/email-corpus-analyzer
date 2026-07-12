FIX=true
---

## Error Check: 2026-04-16

### Summary

- Open bug issues: 0
- Failed CI checks (default branch): 3
- Dependabot/security alerts: 0
- Security-labeled issues: 0
- Total errors found: 3

### Failed CI/CD on Default Branch

#### Workflow: CI (main branch)

- 🔴 **Run 22574466641** — 2026-03-02
  - URL: https://github.com/davistroy/email-corpus-analyzer/actions/runs/22574466641
  - Job: typecheck (mypy) — **Failed**
    - Found 20 errors in 13 files
    - Error types: no-any-return, return-value incompatibility, missing type annotations, invalid-index types
  - Job: test (3.10) — **Failed**
    - pytest with coverage failed — coverage threshold of 85% not met

- 🔴 **Run 22557669318** — 2026-03-02
  - URL: https://github.com/davistroy/email-corpus-analyzer/actions/runs/22557669318

- 🔴 **Run 22557666981** — 2026-03-02
  - URL: https://github.com/davistroy/email-corpus-analyzer/actions/runs/22557666981

### Analysis

Complex fix required. The codebase has 20 mypy type errors spread across 13 files, including no-any-return violations, return value type mismatches, missing type annotations, and invalid index types. The test coverage failure on Python 3.10 may be a separate issue requiring additional tests.

### Suggested Action

This requires manual attention across multiple files:

1. Run `mypy .` locally to get the full list of 20 errors across 13 files
2. Fix type annotations file by file
3. Run `pytest --cov --cov-fail-under=85` to verify coverage threshold
4. Add missing tests if coverage is below 85%
5. Push fixes to a branch and verify CI passes

### Status Legend

- 🔴 OPEN — Error is unresolved
- 🟢 FIXED — Error was auto-fixed this run
- ⚪ NO ERRORS — Repository is clean
