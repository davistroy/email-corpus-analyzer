# Implementation Plan

**Generated:** 2026-02-17T16:30:00Z
**Based On:** RECOMMENDATIONS.md
**Total Phases:** 1
**Methodology:** TDD per constitution (tests first, then implementation)

---

## Plan Overview

All four recommendations are scoped to a single phase. The fixes are independent at the code level but share the extraction pipeline context, so grouping them reduces context-switching overhead. Work items are ordered by priority: data correctness first, then UX improvements.

### Phase Summary Table

| Phase | Focus Area | Key Deliverables | Est. Tokens | Dependencies |
|-------|------------|------------------|-------------|--------------|
| 1 | Extraction Pipeline Fixes | Safe recipient parsing, progress bar, clean errors, no sentinel display | ~60K | None |

---

## Phase 1: Extraction Pipeline Fixes

**Estimated Effort:** ~60,000 tokens (including testing/fixes)
**Dependencies:** None
**Parallelizable:** Yes — work items 1.1 and 1.3/1.4 are independent; 1.2 depends loosely on understanding 1.1's error flow

### Goals
- Recover the 5-10% of emails currently lost to the toRecipients IndexError
- Show a live tqdm progress bar during extraction with email count, rate, and elapsed time
- Suppress the misleading "999999 emails" sentinel message
- Replace verbose Pydantic error dumps with clean single-line warnings and an end-of-extraction summary

### Work Items

#### 1.1 Fix toRecipients IndexError in Both Extractors
**Recommendation Ref:** D1
**Files Affected:**
- `src/extractors/m365_extractor.py` (lines 140-141)
- `src/extractors/gmail_extractor.py` (lines 126-131)
- `tests/unit/test_extractors.py` (new test cases)
- `tests/unit/test_gmail_extractor.py` (new test cases)

**Description:**
Replace unsafe `toRecipients[0]` indexing with safe extraction. When `toRecipients` is empty, missing, or None, set `recipient_email=None` and `recipient_name=""`.

M365 extractor fix (lines 140-141):
```python
# Before:
recipient_email=email_data.get("toRecipients", [{}])[0].get("emailAddress", {}).get("address"),
recipient_name=email_data.get("toRecipients", [{}])[0].get("emailAddress", {}).get("name", ""),

# After:
recipient_email=(email_data.get("toRecipients") or [{}])[0].get("emailAddress", {}).get("address")
    if email_data.get("toRecipients")
    else None,
recipient_name=(email_data.get("toRecipients") or [{}])[0].get("emailAddress", {}).get("name", "")
    if email_data.get("toRecipients")
    else "",
```

Gmail extractor already has the conditional but the default branch `[{}]` still triggers when `toRecipients` exists but is empty `[]`. Fix the guard to check `len()` not just truthiness.

**Acceptance Criteria:**
- [ ] Emails with `"toRecipients": []` are processed successfully with `recipient_email=None`
- [ ] Emails with `"toRecipients": None` are processed successfully
- [ ] Emails with missing `toRecipients` key are processed successfully
- [ ] Emails with valid `toRecipients` still extract correctly
- [ ] Tests cover all four scenarios for both M365 and Gmail extractors
- [ ] No IndexError warnings in extraction output for recipient-related failures

---

#### 1.2 Wire tqdm Progress Bar into Extraction
**Recommendation Ref:** U2
**Files Affected:**
- `src/cli/commands/extract.py` (add progress bar setup)
- `src/services/extraction_service.py` (pass progress callback to extractor)
- `src/extractors/base_extractor.py` (adjust logging when progress bar active)
- `tests/unit/test_extractors.py` (test progress callback invocation)
- `tests/unit/test_services.py` (test callback passthrough)

**Description:**
Create a tqdm progress bar in the extract CLI command and wire it through the service layer to the extractor's batch loop. Since M365 doesn't provide a total count, use tqdm's indeterminate mode (`total=None`) which displays count, rate, and elapsed time without a percentage bar.

Implementation approach:
1. In `cmd_extract()`: create a tqdm bar with `total=None, desc="Extracting emails", unit=" emails"`
2. Create a per-email callback that calls `bar.update(1)` on each successful email
3. Pass this callback through `ExtractionService.run()` to `extractor.extract_all(progress_callback=...)`
4. The service needs a new parameter for the per-email callback (separate from its existing status message callback)
5. When progress bar is active, suppress the per-checkpoint INFO log messages (they collide with tqdm's output)

The `ExtractionService._run_single_extractor()` currently calls `extractor.extract_all()` without passing `progress_callback`. Add passthrough.

**Acceptance Criteria:**
- [ ] Running `python -m src.cli extract` shows a live tqdm progress bar
- [ ] Bar displays: description, email count, processing rate (emails/sec), elapsed time
- [ ] Bar updates on each successfully processed email
- [ ] Checkpoint messages don't collide with progress bar output
- [ ] `--quiet` mode suppresses the progress bar
- [ ] `--json` mode suppresses the progress bar (output must be clean JSON)
- [ ] Progress bar closes cleanly on completion or error
- [ ] Tests verify callback is invoked per email

---

#### 1.3 Suppress Sentinel Value from User-Facing Output
**Recommendation Ref:** U1
**Files Affected:**
- `src/extractors/base_extractor.py` (lines 237-241)
- `tests/unit/test_extractors.py` (verify log messages)

**Description:**
In `_execute_batch_loop()`, replace the unconditional "Found N total emails" log with a conditional:
- If count is real (not sentinel): log "Found N emails to process"
- If count is sentinel: log "Fetching emails (total count unknown, will paginate until complete)"

```python
# Before (line 237-241):
total_emails = EMAIL_COUNT_SENTINEL
if existing_ids is None:
    try:
        total_emails = self._get_total_email_count()
        self.logger.info(f"Found {total_emails} total emails to process")

# After:
total_emails = EMAIL_COUNT_SENTINEL
if existing_ids is None:
    try:
        total_emails = self._get_total_email_count()
        if total_emails == EMAIL_COUNT_SENTINEL:
            self.logger.info("Fetching emails (total count unknown, will paginate until complete)")
        else:
            self.logger.info(f"Found {total_emails:,} emails to process")
```

**Acceptance Criteria:**
- [ ] Running M365 extraction shows "Fetching emails (total count unknown...)" not "Found 999999"
- [ ] If a provider returns a real count, it displays formatted with commas
- [ ] Tests verify correct log message for sentinel vs real count

---

#### 1.4 Clean Up Error Messages During Extraction
**Recommendation Ref:** U3
**Files Affected:**
- `src/extractors/base_extractor.py` (lines 301-308, plus new summary after loop)
- `tests/unit/test_extractors.py` (verify error formatting)

**Description:**
Improve the error logging in the per-email exception handler:

1. **Format Pydantic errors concisely:**
```python
from pydantic import ValidationError

except ValidationError as e:
    first = e.errors()[0]
    field = first.get("loc", ["unknown"])[-1]
    msg = first.get("msg", str(e))
    self.logger.warning(f"Skipped email {email_data.get('id', '?')[:12]}: {field} - {msg}")
```

2. **Format other errors with context:**
```python
except Exception as e:
    self.logger.warning(f"Skipped email {email_data.get('id', '?')[:12]}: {type(e).__name__}: {e}")
```

3. **Add error summary after batch loop:**
Track error counts by type during the loop, then log a one-line summary:
```python
error_counts: dict[str, int] = {}
# ... in except block: error_counts[error_type] = error_counts.get(error_type, 0) + 1
# ... after loop:
if error_counts:
    summary = ", ".join(f"{count} {etype}" for etype, count in error_counts.items())
    self.logger.info(f"Skipped {sum(error_counts.values())} emails ({summary})")
```

**Acceptance Criteria:**
- [ ] Pydantic validation errors display as single-line warnings with field name
- [ ] IndexError and other exceptions show type and message concisely
- [ ] Email ID is truncated for readability (first 12 chars)
- [ ] End-of-extraction summary shows error counts by category
- [ ] Full error details still stored in `ExtractionError.error_message` for debugging
- [ ] Tests verify formatted output for ValidationError and generic Exception cases

---

### Phase 1 Testing Requirements
- New tests for toRecipients edge cases: empty array, None, missing key (both extractors)
- Tests for progress callback invocation through service layer
- Tests for log message content (sentinel vs real count)
- Tests for error formatting (ValidationError, IndexError, generic Exception)
- All existing 1977 tests must continue to pass

### Phase 1 Completion Checklist
- [ ] All 4 work items complete
- [ ] All tests passing (existing + new)
- [ ] No regressions in extraction flow
- [ ] Manual smoke test: run extract against real inbox, verify progress bar and clean output
- [ ] CLAUDE.md updated with new test count

---

## Parallel Work Opportunities

| Work Item A | Can Run With | Notes |
|-------------|--------------|-------|
| 1.1 (toRecipients fix) | 1.3 (sentinel suppression) | Different files, no overlap |
| 1.1 (toRecipients fix) | 1.4 (error formatting) | Error formatting changes the handler that catches 1.1's old bug — do 1.1 first |
| 1.3 (sentinel suppression) | 1.4 (error formatting) | Different code paths in base_extractor |
| 1.2 (progress bar) | 1.1, 1.3 | Progress bar is additive, doesn't conflict with other fixes |

**Recommended execution order:** 1.1 → 1.3 → 1.4 → 1.2 (progress bar last, since it touches the most files)

---

## Risk Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Progress bar conflicts with existing logging | Medium | Low | Test with `--verbose` and `--quiet` modes; use tqdm.write() for any log messages during progress |
| Recipient fix changes Email model semantics | Low | Medium | `recipient_email` is already `Optional[str]` — no model change needed |
| Error formatting hides useful debug info | Low | Medium | Keep full error in ExtractionError.error_message; only format the console WARNING |

---

## Success Metrics

| Metric | Before | Target |
|--------|--------|--------|
| Emails lost to IndexError | 5-10% | 0% |
| User sees "999999" | Yes | No |
| Progress feedback during extraction | Checkpoint every 100 emails | Live tqdm bar with rate/count |
| Error message readability | Multi-line Pydantic dumps | Single-line summaries |

---

*Implementation plan generated by Claude on 2026-02-17*
