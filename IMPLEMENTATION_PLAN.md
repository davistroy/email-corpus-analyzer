# Implementation Plan: Architectural Refinement

**Generated:** 2026-02-15
**Source Documents:**
- Architectural audit (4 parallel agent sweeps, Feb 15 2026)
- Findings walkthrough with recommended solutions, alternatives, and clarifications
- Previous plan (Feb 13, 19 work items) — fully completed, superseded

**Total Phases:** 4
**Total Work Items:** 16
**Estimated Total Effort:** ~240,000 tokens

---

## Executive Summary

The email-corpus-analyzer is an 18,334-line Python application with 1,663 tests at 86% coverage. A comprehensive architectural audit identified 23 issues — 16 actionable, 3 requiring no change, and 4 long-term considerations. No critical security vulnerabilities or data integrity risks were found. The architecture is sound (grade: B+).

The most impactful problem is `src/cli.py` — a 2,424-line monolith where parser creation alone is 1,100 lines. Beyond that, the plan targets code duplication (BaseExtractor batch loop, stop word lists, confidence scores), hardcoded values (magic numbers, sender keywords, category templates), and missing infrastructure (CI pipeline, contract tests, rate limit typing).

All items from the previous implementation plan (Feb 13, 2026) have been completed. This plan addresses exclusively new findings from the Feb 15 architectural audit.

---

## Plan Overview

The implementation follows a **risk-ascending strategy**: quick, safe consolidation wins first (Phase 1), then targeted refactors with moderate complexity (Phase 2), then the highest-impact structural change — the CLI split (Phase 3), and finally infrastructure and polish (Phase 4). Each phase leaves the codebase in a working, tested state.

**Key decision inputs from user:**
- `src/main.py` is legacy (confirmed by code review — only M365, no service layer, hardcoded Linux path)
- Category templates will evolve → externalize to JSON
- Target corpus: 10K–50K emails → O(n²) algorithms are borderline; document but don't rewrite yet

### Phase Summary Table

| Phase | Focus Area | Key Deliverables | Work Items | Est. Tokens | Dependencies |
|-------|------------|------------------|------------|-------------|--------------|
| 1 | Quick Wins | Consolidate shared code, delete dead code, remove legacy | 5 | ~40K | None |
| 2 | Targeted Refactors | Batch loop dedup, service cleanup, config fix, rate limit types | 5 | ~80K | None |
| 3 | Structural Changes | CLI package split, externalize templates & keywords | 3 | ~80K | Phase 1 (M2 constants) |
| 4 | Infrastructure & Polish | CI pipeline, contract tests, documentation | 3 | ~40K | Phase 1–3 complete |

---

## Phase 1: Quick Wins

**Estimated Effort:** ~40,000 tokens (including testing/fixes)
**Dependencies:** None
**Parallelizable:** All 5 items are fully independent
**Risk:** Very low — no behavioral changes, only consolidation and deletion

### Goals

- Eliminate dead code and legacy files
- Consolidate duplicated constants and word lists into shared modules
- Establish the `src/utils/constants.py` and `src/utils/text.py` foundations that later phases depend on

### Work Items

#### 1.1 Fix AnalysisService Dead Code

**Audit Ref:** H3
**Files Affected:**
- `src/services/analysis_service.py` (modify — lines 45–127)
- `tests/unit/test_services.py` (modify)

**Description:**
`AnalysisService` has a `_build_analyzers()` method (lines 45–54) that builds a list of analyzer instances but is never called. Instead, `run()` (lines 56–127) creates each analyzer inline with explicit constructor calls. This is confusing — someone extending analysis would naturally modify `_build_analyzers()` and wonder why nothing changes.

**Tasks:**
1. [ ] Refactor `run()` to call `self._build_analyzers()` and iterate over the returned list
2. [ ] Handle `SemanticAnalyzer` specially within the loop (it needs incremental support) — use a type check or flag
3. [ ] Remove the inline analyzer construction from `run()`
4. [ ] Verify progress callback messages still report analyzer names correctly
5. [ ] Update tests to verify analyzer list construction

**Acceptance Criteria:**
- [ ] `_build_analyzers()` is the single source of truth for which analyzers run
- [ ] Adding a new analyzer requires only modifying `_build_analyzers()`
- [ ] All existing 1,663 tests pass
- [ ] `SemanticAnalyzer` incremental mode still works

**Notes:**
If the `SemanticAnalyzer` special-casing makes the loop ugly, an acceptable alternative is to delete `_build_analyzers()` entirely and add a comment explaining why inline construction is intentional. The goal is removing confusion, not forcing a pattern.

---

#### 1.2 Create Shared Text Utilities

**Audit Ref:** M1
**Files Affected:**
- `src/utils/text.py` (create)
- `src/generators/name_generator.py` (modify — lines 17–32)
- `src/analyzers/subject_analyzer.py` (modify)
- `src/generators/category_generator.py` (modify — lines 542–553)
- `tests/unit/test_utils.py` (modify)

**Description:**
Stop word lists are duplicated across 3 modules — `name_generator.py` (54-word `STOP_WORDS` frozenset), `subject_analyzer.py` (inline stop word filtering), and `category_generator.py` (`_extract_common_words()` with its own list). The lists are slightly different because each was written independently. Additionally, `GENERIC_WORDS` (36 words) and `ACTION_WORDS` (28 words) in `name_generator.py` and `KNOWN_PROPER_NOUNS` (57 brands) are useful across modules.

**Tasks:**
1. [ ] Create `src/utils/text.py` with shared frozensets:
   - `STOP_WORDS` — union of all three current lists (~60 words)
   - `GENERIC_WORDS` — words like "email", "misc", "category" (from name_generator.py)
   - `ACTION_WORDS` — words like "update", "invoice", "order" (from name_generator.py)
   - `KNOWN_PROPER_NOUNS` — brand names (from name_generator.py)
2. [ ] Update `name_generator.py` to import from `utils.text` instead of defining its own
3. [ ] Update `subject_analyzer.py` to import `STOP_WORDS` from `utils.text`
4. [ ] Update `category_generator.py._extract_common_words()` to import from `utils.text`
5. [ ] Allow module-specific extensions: `module_stops = STOP_WORDS | {"module_specific_word"}`
6. [ ] Write tests verifying the shared sets contain all previously-used words

**Acceptance Criteria:**
- [ ] No module defines its own stop word list
- [ ] All three modules produce identical results to their previous behavior
- [ ] `src/utils/text.py` is the single source of truth for text processing word lists
- [ ] All existing tests pass

---

#### 1.3 Create Constants Module

**Audit Ref:** M2
**Files Affected:**
- `src/utils/constants.py` (create)
- `src/extractors/base_extractor.py` (modify — sentinel at line ~223, backoff at ~485)
- `src/analyzers/cluster_optimizer.py` (modify — sigmoid at line 81)
- `src/generators/category_generator.py` (modify — quality threshold at line 31)
- `src/generators/confidence_scorer.py` (modify — log base at lines 88, 166)
- Tests updated as needed

**Description:**
Numeric literals are used directly in code without named constants. `999999` as a sentinel for unknown email count, `5.0` for sigmoid steepness, `0.4` for name quality threshold, `101` as a log base, `8` for max backoff seconds. These values are well-chosen but undiscoverable — you can't grep for "what controls the sigmoid curve" without reading the code.

**Tasks:**
1. [ ] Create `src/utils/constants.py` with documented constants:
   ```python
   # Extraction
   EMAIL_COUNT_SENTINEL = 999_999  # Used when provider doesn't report total count
   MAX_BACKOFF_SECONDS = 8         # Ceiling for exponential backoff on rate limit
   DEFAULT_BATCH_SIZE = 500
   DEFAULT_CHECKPOINT_INTERVAL = 100

   # Scoring
   SIGMOID_STEEPNESS = 5.0         # Controls sigmoid curve sharpness in cluster scoring
   VOLUME_LOG_BASE = 101           # log10(101) ≈ 2.004; makes 100 emails → score 1.0
   NAME_QUALITY_REVIEW_THRESHOLD = 0.4  # Below this, category name flagged for review

   # Sampling limits
   MAX_REPRESENTATIVE_SAMPLES = 5
   MAX_COMMON_DOMAINS = 10
   MAX_TOP_KEYWORDS = 50
   ```
2. [ ] Replace all hardcoded values with imports from `constants.py`
3. [ ] Update affected tests to use constants where they reference these values
4. [ ] Verify no behavioral changes

**Acceptance Criteria:**
- [ ] All magic numbers listed above are replaced with named constants
- [ ] Each constant has a comment explaining its purpose
- [ ] No behavioral changes — defaults are identical to previous hardcoded values
- [ ] All existing tests pass

---

#### 1.4 Consolidate Source Confidence Scores

**Audit Ref:** M8
**Files Affected:**
- `src/generators/confidence_scorer.py` (modify — lines 92–97 and 170–175)
- `tests/unit/test_confidence_scorer.py` (verify)

**Description:**
`confidence_scorer.py` defines the same source-type-to-reliability mapping in two places: `calculate_confidence()` (line 92) and `calculate_confidence_enhanced()` (line 170). Both are `{"TEMPLATE": 0.9, "CONTENT_CLUSTER": 0.8, "SENDER": 0.7, "CUSTOM": 0.5}`. If someone updates one and not the other, the simple and enhanced scoring paths diverge silently.

**Tasks:**
1. [ ] Define module-level constant:
   ```python
   SOURCE_RELIABILITY_SCORES: dict[str, float] = {
       CategorySource.TEMPLATE.value: 0.9,
       CategorySource.CONTENT_CLUSTER.value: 0.8,
       CategorySource.SENDER.value: 0.7,
       CategorySource.CUSTOM.value: 0.5,
   }
   ```
2. [ ] Update both functions to reference `SOURCE_RELIABILITY_SCORES`
3. [ ] Verify existing tests pass with no changes

**Acceptance Criteria:**
- [ ] Single definition of source reliability scores
- [ ] Both scoring functions use the same constant
- [ ] All existing tests pass

---

#### 1.5 Delete Legacy `src/main.py`

**Audit Ref:** L1
**Files Affected:**
- `src/main.py` (delete — 565 lines)
- Any imports or references to `src.main` (update)
- `CLAUDE.md` (update entry points section if referenced)

**Description:**
`src/main.py` is the original entry point from before `src/cli.py` was built. It only supports M365 extraction (no Gmail), has no service layer, no config system, no TUI, no export, and hardcodes a Linux-style path (`/mnt/user-data/outputs`). Everything it does, `cli.py` does better. User confirmed they're unsure why both exist; code review confirms it's legacy.

**Tasks:**
1. [ ] Search for any imports of `src.main` or `EmailProcessorCLI` across the codebase
2. [ ] Remove any references found
3. [ ] Delete `src/main.py`
4. [ ] Verify `python -m src.cli --help` still works
5. [ ] Update CLAUDE.md entry points section if `main.py` is mentioned

**Acceptance Criteria:**
- [ ] `src/main.py` is removed from the repository
- [ ] No remaining references to `EmailProcessorCLI` or `src.main`
- [ ] `src/cli.py` confirmed as the sole entry point
- [ ] All existing tests pass

---

### Phase 1 Testing Requirements

- [ ] AnalysisService tests verify `_build_analyzers()` is used in `run()`
- [ ] Utils text module tests verify word list completeness
- [ ] Constants module has no behavioral tests needed (just import verification)
- [ ] Confidence scorer tests unchanged (behavior preserved)
- [ ] No test references `src.main` or `EmailProcessorCLI`
- [ ] All 1,663 existing tests pass with no regressions

### Phase 1 Completion Checklist

- [ ] All 5 work items complete
- [ ] All tests passing
- [ ] `src/main.py` deleted
- [ ] `src/utils/text.py` and `src/utils/constants.py` created
- [ ] No regressions introduced

---

## Phase 2: Targeted Refactors

**Estimated Effort:** ~80,000 tokens (including testing/fixes)
**Dependencies:** None (can run in parallel with Phase 1, but benefits from 1.3 constants)
**Parallelizable:** Items 2.1–2.5 are all independent
**Risk:** Medium — changes control flow in extractors and CLI config, requires careful testing

### Goals

- Eliminate the largest DRY violation in the codebase (BaseExtractor batch loop)
- Unify ExtractionService source branching for extensibility
- Fix fragile config application and domain name stripping
- Replace string-based rate limit detection with typed exceptions

### Work Items

#### 2.1 Extract Shared Batch Loop in BaseExtractor

**Audit Ref:** H2
**Files Affected:**
- `src/extractors/base_extractor.py` (modify — lines 187–461)
- `tests/unit/test_extractors.py` (modify)
- `tests/unit/test_base_analyzer.py` (modify if needed)

**Description:**
`extract_all()` (lines 187–330, 143 lines) and `extract_incremental()` (lines 332–461, 129 lines) implement nearly identical batch processing loops — pagination, per-email try/catch, checkpoint saving, rate limit handling, error collection. The only real differences are: (1) incremental has a deduplication check against existing IDs, and (2) incremental uses `_fetch_incremental_batch()` instead of `_fetch_batch()`. A bug fix in checkpoint logic must be applied in both places today.

**Tasks:**
1. [ ] Create private method `_execute_batch_loop()` with signature:
   ```python
   def _execute_batch_loop(
       self,
       fetch_fn: Callable[..., list[dict]],
       existing_ids: set[str] | None,  # None for full, set for incremental
       max_batch_size: int,
       checkpoint_interval: int,
       progress_callback: Callable[[int, int], None] | None,
       fetch_kwargs: dict[str, Any] | None = None,
   ) -> tuple[list[Email], list[ExtractionError]]:
   ```
2. [ ] Move the common batch loop logic into `_execute_batch_loop()`:
   - Checkpoint resume check
   - Batch fetch loop with pagination
   - Per-email `_process_email()` with try/catch
   - Error collection (ExtractionError with type classification)
   - Checkpoint saving at intervals
   - Rate limit detection and backoff
   - Progress callback invocation
3. [ ] Add dedup logic: if `existing_ids` is not None, skip emails whose ID is already in the set
4. [ ] Refactor `extract_all()` to call `_execute_batch_loop(fetch_fn=self._fetch_batch, existing_ids=None, ...)`
5. [ ] Refactor `extract_incremental()` to call `_execute_batch_loop(fetch_fn=self._fetch_incremental_batch, existing_ids=existing_ids, ...)`
6. [ ] Both public methods become thin wrappers: setup params → call shared loop → build result dataclass
7. [ ] Update tests — verify both extraction modes still pass all existing tests
8. [ ] Add a test that modifies checkpoint behavior and verifies it affects both modes

**Acceptance Criteria:**
- [ ] Batch loop logic exists in exactly one place
- [ ] `extract_all()` and `extract_incremental()` are each < 30 lines
- [ ] Checkpoint, error collection, and rate limit handling tested via the shared method
- [ ] All existing extractor tests pass
- [ ] Both M365 and Gmail extractors work correctly through both modes

---

#### 2.2 Unify ExtractionService Source Branching

**Audit Ref:** M4
**Files Affected:**
- `src/services/extraction_service.py` (modify — lines 228–271)
- `tests/unit/test_services.py` (modify)

**Description:**
`ExtractionService.run()` has three branches — hotmail, gmail, both — where the hotmail and gmail branches are structurally identical copies with only the extractor factory method changed. Adding a third email source (Yahoo, IMAP) would require copy-pasting a fourth branch.

**Tasks:**
1. [ ] Define a source configuration mapping:
   ```python
   _SOURCE_CONFIGS: dict[str, tuple[str, Callable]] = {
       "hotmail": ("M365/Hotmail", self._get_m365_extractor),
       "gmail": ("Gmail", self._get_gmail_extractor),
   }
   ```
2. [ ] Replace the if/elif/else chain with a loop:
   ```python
   sources = list(_SOURCE_CONFIGS.keys()) if self.source == "both" else [self.source]
   corpora = []
   for source_key in sources:
       label, factory = _SOURCE_CONFIGS[source_key]
       extractor = factory()
       corpus = self._run_single_extractor(extractor, label, ...)
       corpora.append((corpus, label))
   ```
3. [ ] Single-source returns `corpora[0][0]`; multi-source calls `_merge_corpora()`
4. [ ] Update tests to verify loop-based dispatch works for all three modes
5. [ ] Add a test that validates an unknown source raises a clear error

**Acceptance Criteria:**
- [ ] No duplicated extraction branches in `run()`
- [ ] Adding a new source requires only adding an entry to `_SOURCE_CONFIGS` + a factory method
- [ ] All three source modes (hotmail, gmail, both) work correctly
- [ ] Invalid source values produce clear `ConfigurationError`
- [ ] All existing service tests pass

---

#### 2.3 Data-Driven Config Application in CLI

**Audit Ref:** M5
**Files Affected:**
- `src/cli.py` (modify — lines 2370–2421)
- `tests/unit/test_cli.py` (modify)

**Description:**
`_apply_config_defaults()` manually checks each CLI argument against hardcoded defaults: `if hasattr(args, "batch_size") and args.batch_size == 500`. The "500" default is hardcoded in both the parser definition and this function. Add a new CLI option and you must update this function too, with a matching default comparison value.

**Tasks:**
1. [ ] Create a config-to-CLI mapping dictionary:
   ```python
   _CONFIG_MAPPINGS: dict[str, Callable[[AppConfig], Any]] = {
       "user_email": lambda c: c.user_email,
       "output_dir": lambda c: c.output_dir,
       "batch_size": lambda c: c.extract.batch_size,
       "checkpoint_interval": lambda c: c.extract.checkpoint_interval,
       "num_clusters": lambda c: c.analyze.num_clusters,
       "min_cluster_pct": lambda c: c.suggest.min_cluster_percentage,
       "min_sender_count": lambda c: c.suggest.min_sender_count,
   }
   ```
2. [ ] Rewrite `_apply_config_defaults()` to iterate the mapping:
   ```python
   def _apply_config_defaults(args, config, parser):
       for attr, getter in _CONFIG_MAPPINGS.items():
           if hasattr(args, attr):
               parser_default = parser.get_default(attr)
               current_value = getattr(args, attr)
               if current_value == parser_default or current_value is None:
                   setattr(args, attr, getter(config))
   ```
3. [ ] Pass the parser object into `_apply_config_defaults()` (it already exists in scope)
4. [ ] Remove all hardcoded default comparisons (500, 100, 10, 5.0, 20)
5. [ ] Write tests: set config values, verify they propagate when CLI args are at defaults
6. [ ] Write tests: set CLI args explicitly, verify they override config values

**Acceptance Criteria:**
- [ ] No hardcoded default values in `_apply_config_defaults()`
- [ ] Adding a new CLI option requires only adding one entry to `_CONFIG_MAPPINGS`
- [ ] Config precedence preserved: CLI args > config file > defaults
- [ ] All existing CLI tests pass

---

#### 2.4 Fix Domain Name Stripping

**Audit Ref:** M6
**Files Affected:**
- `src/generators/category_generator.py` (modify — lines 207, 254, 491, 509)
- `src/utils/text.py` (modify — add helper function)
- `tests/unit/test_generators.py` (modify)

**Description:**
`category_generator.py` has four occurrences of `.replace('.com', '')` for generating category names from domain names. This means `amazon.com` → `amazon` works, but `amazon.co.uk` → `amazon.co.uk` (unchanged), `example.org` → `example.org` (unchanged), `bank.co.za` → `bank.co.za` (unchanged).

**Tasks:**
1. [ ] Add `strip_domain_suffix()` to `src/utils/text.py`:
   ```python
   def strip_domain_suffix(domain: str) -> str:
       """Extract registrable name from a domain for display purposes."""
       parts = domain.lower().split('.')
       # Two-part country TLDs: co.uk, com.au, co.za, com.br, etc.
       if len(parts) >= 3 and parts[-2] in ('co', 'com', 'org', 'net', 'ac', 'gov'):
           return '.'.join(parts[:-2])
       elif len(parts) >= 2:
           return '.'.join(parts[:-1])
       return domain
   ```
2. [ ] Replace all 4 occurrences of `.replace('.com', '')` chains with `strip_domain_suffix()`
3. [ ] Write tests:
   - `amazon.com` → `amazon`
   - `amazon.co.uk` → `amazon`
   - `bank.co.za` → `bank`
   - `example.org` → `example`
   - `mail.google.com` → `mail.google` (subdomain preserved)
   - `localhost` → `localhost` (no suffix)
4. [ ] Verify category names are now correct for non-.com domains

**Acceptance Criteria:**
- [ ] All common TLD patterns handled: .com, .org, .net, .co.uk, .com.au, etc.
- [ ] No `.replace('.com', '')` remains in the codebase
- [ ] Category names for non-.com senders are human-readable
- [ ] All existing generator tests pass

---

#### 2.5 Add RateLimitError Exception Type

**Audit Ref:** M9
**Files Affected:**
- `src/exceptions.py` (modify — add RateLimitError)
- `src/extractors/graph_api_client.py` (modify — line ~188)
- `src/extractors/gmail_client.py` (modify — error handling)
- `src/extractors/base_extractor.py` (modify — line ~285)
- `tests/unit/test_extractors.py` (modify)
- `tests/unit/test_graph_api_client.py` (modify)

**Description:**
`base_extractor.py` line 285 detects rate limiting with `"rate" in str(e).lower()` — string matching on error messages. This is fragile: "Request throttled" wouldn't trigger it, and "cannot operate" would false-positive. Both API clients already know when they're being rate-limited (HTTP 429), but that information is lost by the time it reaches the base extractor.

**Tasks:**
1. [ ] Add `RateLimitError` to `src/exceptions.py`:
   ```python
   class RateLimitError(ExtractionError):
       """Provider rate limit exceeded (HTTP 429)."""
       def __init__(self, retry_after: int | None = None, **kwargs):
           super().__init__(
               message="Rate limit exceeded",
               recovery_hint="Wait and retry. The provider is throttling requests.",
               **kwargs,
           )
           self.retry_after = retry_after
   ```
2. [ ] In `GraphAPIClient._make_request()`: detect HTTP 429, parse `Retry-After` header, raise `RateLimitError(retry_after=seconds)`
3. [ ] In `GmailClient`: detect `HttpError` with status 429, raise `RateLimitError`
4. [ ] In `BaseExtractor._execute_batch_loop()` (or current batch loops): replace string matching with `except RateLimitError as e:` and use `e.retry_after` for smarter backoff
5. [ ] Keep a general `except Exception` fallback for other errors (no change to existing behavior)
6. [ ] Write tests: mock 429 response → verify `RateLimitError` raised with correct `retry_after`
7. [ ] Write tests: verify backoff uses `retry_after` when available

**Acceptance Criteria:**
- [ ] No string matching for rate limit detection remains
- [ ] HTTP 429 from either API raises `RateLimitError` with `retry_after`
- [ ] BaseExtractor catches `RateLimitError` by type
- [ ] `retry_after` header value is used when available (smarter than fixed exponential)
- [ ] Non-429 errors still handled by general exception path
- [ ] All existing tests pass

---

### Phase 2 Testing Requirements

- [ ] BaseExtractor: shared batch loop tested for both full and incremental modes
- [ ] ExtractionService: all three source modes tested via loop dispatch
- [ ] CLI config: verify precedence (CLI > config > default) with data-driven mapping
- [ ] Domain stripping: comprehensive TLD coverage tests
- [ ] Rate limit: 429 detection and retry_after propagation tests
- [ ] All 1,663 existing tests pass with no regressions

### Phase 2 Completion Checklist

- [ ] All 5 work items complete
- [ ] All tests passing
- [ ] BaseExtractor batch loop exists in exactly one place
- [ ] No string-based rate limit detection
- [ ] No hardcoded `.replace('.com', '')`
- [ ] No regressions introduced

---

## Phase 3: Structural Changes

**Estimated Effort:** ~80,000 tokens (including testing/fixes)
**Dependencies:** Phase 1 (constants module provides shared defaults for CLI split)
**Parallelizable:** Items 3.2 and 3.3 are independent; 3.1 is the largest single item
**Risk:** Higher — CLI split touches the main entry point; template externalization changes loading behavior

### Goals

- Break the CLI god module into a maintainable package structure
- Externalize category templates to enable runtime evolution without code changes
- Make sender classification keywords configurable

### Work Items

#### 3.1 Split CLI into Package

**Audit Ref:** H1
**Files Affected:**
- `src/cli.py` (delete — 2,425 lines)
- `src/cli/__init__.py` (create — thin dispatcher)
- `src/cli/parsers.py` (create — shared argument groups)
- `src/cli/formatters.py` (create — output helpers, cluster viz, progress)
- `src/cli/commands/extract.py` (create)
- `src/cli/commands/analyze.py` (create)
- `src/cli/commands/suggest.py` (create)
- `src/cli/commands/review.py` (create)
- `src/cli/commands/pipeline.py` (create)
- `src/cli/commands/config.py` (create)
- `src/cli/commands/export.py` (create)
- `src/cli/commands/info.py` (create)
- `tests/unit/test_cli.py` (modify — update imports)
- `tests/unit/test_cli_tui_integration.py` (modify — update imports)
- `pyproject.toml` (verify entry point)

**Description:**
`src/cli.py` is 2,425 lines — the largest file in the codebase by 3x. `create_parser()` alone is 1,100 lines of argparse definitions (lines 315–877). Each command handler mixes setup, execution, and presentation. Every new feature touches this file. This is the single highest-impact refactor in the plan.

**Tasks:**
1. [ ] Create `src/cli/` package directory structure:
   ```
   src/cli/
     __init__.py         # main(), create_parser() (thin dispatcher, ~100 lines)
     parsers.py          # Shared argument groups, _apply_config_defaults() (~150 lines)
     formatters.py       # output_json(), _show_cluster_analysis(), _print_ascii_chart(), progress helpers (~200 lines)
     commands/
       __init__.py
       extract.py        # build_extract_parser(), cmd_extract() (~200 lines)
       analyze.py        # build_analyze_parser(), cmd_analyze() (~250 lines)
       suggest.py        # build_suggest_parser(), cmd_suggest() (~150 lines)
       review.py         # build_review_parser(), cmd_review() (~200 lines)
       pipeline.py       # build_pipeline_parser(), cmd_pipeline() (~200 lines)
       config.py         # build_config_parser(), cmd_config_*() (~150 lines)
       export.py         # build_export_parser(), cmd_export() (~150 lines)
       info.py           # build_info_parser(), cmd_info() (~150 lines)
   ```
2. [ ] Extract shared argument groups to `parsers.py`:
   - `add_output_args(parser)` — `--output-dir`, `--dry-run`
   - `add_verbosity_args(parser)` — `--verbose`, `--quiet`, `--json` (mutually exclusive)
   - `add_config_args(parser)` — `--config`
   - `_apply_config_defaults()` (data-driven, from Phase 2 item 2.3)
3. [ ] Extract output formatting to `formatters.py`:
   - `output_json(data, file=None)` — JSON output helper
   - `show_cluster_analysis(results)` — cluster summary display
   - `print_ascii_chart(data, label)` — text histogram
   - `generate_cluster_viz(results, output_path)` — matplotlib wrapper
   - Progress display helpers
4. [ ] For each command, create a module in `commands/` containing:
   - `build_<command>_parser(subparsers)` — adds the subparser with all arguments
   - `cmd_<command>(args, config)` — the command handler
5. [ ] Rewrite `src/cli/__init__.py`:
   ```python
   from .commands import extract, analyze, suggest, review, pipeline, config, export, info
   from .parsers import add_output_args, add_verbosity_args, add_config_args

   COMMANDS = {
       "extract": (extract.build_parser, extract.cmd_extract),
       "analyze": (analyze.build_parser, analyze.cmd_analyze),
       ...
   }

   def create_parser():
       parser = argparse.ArgumentParser(...)
       subparsers = parser.add_subparsers(...)
       for name, (builder, _) in COMMANDS.items():
           builder(subparsers)
       return parser

   def main():
       parser = create_parser()
       args = parser.parse_args()
       ...
       handler = COMMANDS[args.command][1]
       return handler(args, config)
   ```
6. [ ] Update `pyproject.toml` entry point if it references `src.cli:main`
7. [ ] Update all test imports from `src.cli` to `src.cli.commands.*` or `src.cli`
8. [ ] Verify `python -m src.cli --help` still works
9. [ ] Verify all subcommands work end-to-end
10. [ ] Delete `src/cli.py` (the monolith)

**Acceptance Criteria:**
- [ ] `src/cli.py` no longer exists — replaced by `src/cli/` package
- [ ] No single file exceeds ~300 lines
- [ ] All CLI commands work identically to before
- [ ] Shared argument groups defined once and reused
- [ ] Adding a new command requires: one new file in `commands/`, one entry in `COMMANDS` dict
- [ ] All 3,935 lines of CLI tests pass (test_cli.py is the largest test file)
- [ ] `python -m src.cli --help` displays all commands correctly

**Notes:**
This is the largest single work item. Approach it as a mechanical refactor — move code, don't rewrite it. The goal is decomposition, not redesign. Keep function signatures identical; only change where they live.

---

#### 3.2 Externalize Category Templates to JSON

**Audit Ref:** M7
**Files Affected:**
- `src/data/templates.json` (create)
- `src/models/category_template.py` (modify — lines 21–293)
- `src/generators/template_matcher.py` (modify)
- `src/config/models.py` (modify — add `templates_path` option)
- `tests/unit/test_template_matcher.py` (modify)
- `tests/unit/test_models.py` (modify)

**Description:**
`category_template.py` defines 18 category templates as Python objects in source code — 273 lines of keyword lists and domain patterns. Since the templates will evolve based on usage, every change requires a code commit. Externalizing to JSON enables runtime modification and user overrides.

**Tasks:**
1. [ ] Create `src/data/` directory
2. [ ] Create `src/data/templates.json` containing the 18 templates:
   ```json
   [
     {
       "name": "Financial & Banking",
       "keywords": ["bank", "statement", "payment", ...],
       "domains": ["chase.com", "bankofamerica.com", ...],
       "description": "Banking, financial accounts, payments"
     },
     ...
   ]
   ```
3. [ ] Add `load_templates(path: Path | None = None) -> list[CategoryTemplate]` function to `category_template.py`:
   - Default path: `Path(__file__).parent.parent / "data" / "templates.json"`
   - Validates each entry against `CategoryTemplate` Pydantic model
   - Returns list of validated templates
4. [ ] Keep `PREDEFINED_TEMPLATES = load_templates()` for backward compatibility
5. [ ] Add `templates_path: Path | None = None` to `SuggestConfig`
6. [ ] If `templates_path` is set, load user templates and merge with (or replace) predefined set
7. [ ] Update `template_matcher.py` to accept templates as parameter (not just import global)
8. [ ] Include `src/data/templates.json` in package distribution (`pyproject.toml` package-data)
9. [ ] Write tests:
   - Default loading produces 18 templates
   - Custom path loading works
   - Invalid template JSON raises clear error
   - Merge behavior (user templates + predefined)

**Acceptance Criteria:**
- [ ] Templates live in `src/data/templates.json`, not Python source
- [ ] `PREDEFINED_TEMPLATES` still works for backward compatibility
- [ ] Users can specify custom templates via `suggest.templates_path` in config
- [ ] Adding a new template requires only editing the JSON file
- [ ] All existing template matcher tests pass
- [ ] Template JSON is included in package distribution

---

#### 3.3 Externalize Sender Classification Keywords to Config

**Audit Ref:** M3
**Files Affected:**
- `src/config/models.py` (modify — add fields to `AnalyzerThresholds`)
- `src/analyzers/sender_analyzer.py` (modify — lines 158, 169, 179)
- `src/config/template.yaml` (modify — add commented examples)
- `tests/unit/test_analyzers.py` (modify)
- `tests/unit/test_config_models.py` (modify)

**Description:**
`SenderAnalyzer._classify_sender_type()` uses hardcoded string lists to classify senders: service keywords (`noreply`, `notify`, `support`...), marketing keywords (`sale`, `deal`, `offer`...), and work keywords (`meeting`, `project`, `sprint`...). These are English-centric and can't be adjusted without modifying source code.

**Tasks:**
1. [ ] Add three new fields to `AnalyzerThresholds`:
   ```python
   service_keywords: list[str] = [
       "noreply", "no-reply", "notify", "notification", "alert",
       "support", "help", "info", "admin", "system", "mailer",
       "daemon", "bounce", "postmaster", "donotreply",
   ]
   marketing_keywords: list[str] = [
       "sale", "deal", "offer", "discount", "promo", "promotion",
       "coupon", "save", "free", "limited", "exclusive", "unsubscribe",
       "newsletter", "weekly", "digest",
   ]
   work_keywords: list[str] = [
       "meeting", "project", "sprint", "standup", "review",
       "deadline", "action", "agenda", "minutes", "re:", "fwd:",
       "assigned", "task", "jira", "confluence",
   ]
   ```
2. [ ] Update `SenderAnalyzer.__init__()` to read keywords from `self.thresholds`
3. [ ] Replace hardcoded lists in `_classify_sender_type()` with `self.thresholds.service_keywords`, etc.
4. [ ] Add commented examples to `config/template.yaml` showing keyword customization
5. [ ] Write tests: custom keywords override defaults, classification changes accordingly

**Acceptance Criteria:**
- [ ] No hardcoded classification keywords in `sender_analyzer.py`
- [ ] Default keywords match current behavior exactly
- [ ] Users can add/remove keywords via YAML config
- [ ] `config init` template shows keyword customization examples
- [ ] All existing sender analyzer tests pass

---

### Phase 3 Testing Requirements

- [ ] CLI package: all 3,935 lines of test_cli.py pass with updated imports
- [ ] CLI package: all subcommands verified end-to-end (`--help`, basic execution)
- [ ] Templates: JSON loading, validation, user override, merge behavior
- [ ] Sender keywords: custom classification with user-provided keywords
- [ ] All 1,663 existing tests pass with no regressions

### Phase 3 Completion Checklist

- [ ] All 3 work items complete
- [ ] `src/cli.py` deleted, replaced by `src/cli/` package
- [ ] `src/data/templates.json` created with 18 templates
- [ ] Sender keywords configurable via YAML
- [ ] All tests passing
- [ ] CLAUDE.md updated with new package structure
- [ ] No regressions introduced

---

## Phase 4: Infrastructure & Polish

**Estimated Effort:** ~40,000 tokens (including testing/fixes)
**Dependencies:** Phases 1–3 complete (CI should validate the final codebase state)
**Parallelizable:** All 3 items are independent
**Risk:** Low — no behavioral changes to application code

### Goals

- Automate quality gates with CI
- Begin formal contract testing
- Document the ad-hoc heuristic in cluster optimizer for future maintainers

### Work Items

#### 4.1 Add GitHub Actions CI Pipeline

**Audit Ref:** L3
**Files Affected:**
- `.github/workflows/ci.yml` (create)
- `pyproject.toml` (verify test/lint configuration)

**Description:**
Quality gates are entirely manual — you have to remember to run `ruff check` and `pytest` before committing. There's no CI to catch regressions on push or PR.

**Tasks:**
1. [ ] Create `.github/workflows/ci.yml`:
   ```yaml
   name: CI
   on:
     push:
       branches: [main, '001-use-the-document']
     pull_request:
       branches: [main, '001-use-the-document']

   jobs:
     lint:
       runs-on: ubuntu-latest
       steps:
         - uses: actions/checkout@v4
         - uses: actions/setup-python@v5
           with:
             python-version: '3.10'
         - run: pip install ruff
         - run: ruff check src/

     test:
       runs-on: ubuntu-latest
       steps:
         - uses: actions/checkout@v4
         - uses: actions/setup-python@v5
           with:
             python-version: '3.10'
             cache: 'pip'
         - run: pip install -e ".[dev]"
         - run: pytest --cov=src --cov-report=term-missing --cov-fail-under=85
   ```
2. [ ] Split lint and test into separate jobs for faster feedback
3. [ ] Add Python version matrix if supporting 3.10+ (optional: 3.10, 3.11, 3.12)
4. [ ] Add `cov-fail-under=85` to prevent coverage regression (current: 86%)
5. [ ] Verify the workflow runs successfully on a test push

**Acceptance Criteria:**
- [ ] Push to main or `001-use-the-document` triggers CI
- [ ] PRs show lint and test status checks
- [ ] Ruff violations fail the lint job
- [ ] Test failures fail the test job
- [ ] Coverage below 85% fails the test job

**Notes:**
The sentence-transformers model download during tests may be slow on CI. Consider caching the model directory or using a lighter model for test fixtures. If CI time exceeds 10 minutes, split heavy tests (semantic analyzer) into a separate job.

---

#### 4.2 Add Analyzer Contract Tests

**Audit Ref:** L2
**Files Affected:**
- `tests/contract/test_analyzer_contracts.py` (create)
- `tests/contract/test_extractor_contracts.py` (create)

**Description:**
`tests/contract/` exists with only an `__init__.py`. The specs directory has formal contracts for extractors, analyzers, and generators, but these aren't enforced in code. Contract tests verify that all implementations of an interface meet the documented contract.

**Tasks:**
1. [ ] Create `tests/contract/test_analyzer_contracts.py`:
   ```python
   import pytest
   from src.analyzers import (
       SenderAnalyzer, SubjectAnalyzer, SemanticAnalyzer,
       TemporalAnalyzer, VolumeAnalyzer,
   )
   from src.analyzers.base import BaseAnalyzer

   ALL_ANALYZERS = [
       SenderAnalyzer, SubjectAnalyzer, TemporalAnalyzer, VolumeAnalyzer,
   ]
   # SemanticAnalyzer tested separately (requires model)

   @pytest.mark.parametrize("analyzer_cls", ALL_ANALYZERS)
   class TestAnalyzerContract:
       def test_inherits_base(self, analyzer_cls):
           assert issubclass(analyzer_cls, BaseAnalyzer)

       def test_has_name(self, analyzer_cls):
           analyzer = analyzer_cls()
           assert isinstance(analyzer.name, str)
           assert len(analyzer.name) > 0

       def test_analyze_returns_result(self, analyzer_cls, sample_emails):
           analyzer = analyzer_cls()
           result = analyzer.analyze(sample_emails)
           assert result is not None

       def test_empty_input_handled(self, analyzer_cls):
           analyzer = analyzer_cls()
           result = analyzer.analyze([])
           assert result is not None  # Should not raise

       def test_single_email_handled(self, analyzer_cls, single_email):
           analyzer = analyzer_cls()
           result = analyzer.analyze([single_email])
           assert result is not None
   ```
2. [ ] Create `tests/contract/test_extractor_contracts.py` for BaseExtractor:
   - Verify `_get_source_name()` returns non-empty string
   - Verify `_get_checkpoint_source()` returns non-empty string
   - Verify abstract methods raise `NotImplementedError` if not implemented
3. [ ] Add `sample_emails` and `single_email` fixtures to `tests/conftest.py` if not present
4. [ ] Run contract tests as part of the normal test suite

**Acceptance Criteria:**
- [ ] All 5 analyzer classes pass the contract test suite
- [ ] Empty input and single-email edge cases verified for all analyzers
- [ ] Contract tests run as part of `pytest` (no special flags needed)
- [ ] Future analyzers that don't meet the contract will fail these tests

---

#### 4.3 Document Elbow Optimizer Heuristic

**Audit Ref:** L7
**Files Affected:**
- `src/analyzers/cluster_optimizer.py` (modify — lines 287–349)

**Description:**
The elbow confidence calculation combines slope ratios and inertia reduction percentages with averaging — it works but is hard to reason about or tune. Rather than rewriting a working heuristic, document it thoroughly so future maintainers understand the intent.

**Tasks:**
1. [ ] Add comprehensive docstring to `_calculate_elbow_confidence()`:
   ```python
   def _calculate_elbow_confidence(self, ...):
       """
       Confidence in the detected elbow point.

       Combines two signals:
       1. Slope ratio: how sharply the curve bends at the elbow.
          A sharp bend (ratio > 3) indicates a clear elbow → high confidence.
          A gentle bend (ratio < 1.5) indicates ambiguity → low confidence.

       2. Inertia reduction: what percentage of total inertia reduction
          occurs before the elbow point.
          If 85% of reduction happens before the elbow, most structure is
          captured → high confidence.
          If only 55% happens before, the elbow is splitting meaningful
          variance → low confidence.

       The two signals are averaged for the final confidence score.

       Examples:
           10 candidates tested, elbow at k=4:
           - Inertia drops 85% from k=2→4, only 15% after → ~0.82
           - Inertia drops 55% before, 45% after → ~0.55

           5 candidates tested, elbow at k=3:
           - Sharp bend (ratio=4.2), 90% reduction before → ~0.90
           - Gentle bend (ratio=1.3), 60% reduction before → ~0.45
       """
   ```
2. [ ] Add inline comments at key calculation steps explaining the math
3. [ ] No behavioral changes — documentation only

**Acceptance Criteria:**
- [ ] Docstring explains both signals and how they combine
- [ ] Numerical examples show the mapping from inputs to outputs
- [ ] Future maintainer can understand the heuristic without reading the original audit

---

### Phase 4 Testing Requirements

- [ ] CI pipeline: verify workflow runs on test push
- [ ] Contract tests: all analyzer classes pass
- [ ] No behavioral changes in Phase 4 — existing tests sufficient
- [ ] All 1,663+ existing tests pass with no regressions

### Phase 4 Completion Checklist

- [ ] All 3 work items complete
- [ ] CI pipeline running on GitHub
- [ ] Contract tests in `tests/contract/` populated and passing
- [ ] Elbow optimizer documented
- [ ] All tests passing
- [ ] CLAUDE.md updated if needed

---

## Parallel Work Opportunities

| Work Item | Can Run With | Notes |
|-----------|--------------|-------|
| Phase 1 items (1.1–1.5) | Each other | All fully independent |
| Phase 2 items (2.1–2.5) | Each other | All fully independent |
| Phase 2 items | Phase 1 items | Phase 2 benefits from 1.3 constants but doesn't strictly require it |
| 3.2 (Templates JSON) | 3.3 (Keywords config) | Independent externalization targets |
| 3.1 (CLI split) | Nothing | Touches too many files; serialize with everything else |
| Phase 4 items (4.1–4.3) | Each other | All fully independent |

**Critical path:** Phase 1 → Phase 3.1 (CLI split needs constants from 1.3) → Phase 4.1 (CI validates final state)

---

## Risk Mitigation

| Risk | Likelihood | Impact | Mitigation Strategy |
|------|------------|--------|---------------------|
| CLI split breaks command behavior | Medium | High | Mechanical refactor only — move code, don't rewrite; run full test suite after each command module |
| Template JSON loading fails in packaged distribution | Low | Medium | Include in `pyproject.toml` package-data; test with `pip install -e .` |
| Batch loop extraction introduces subtle behavior change | Low | High | Run extractors against mock API before and after; diff extraction results |
| CI sentence-transformers download makes tests slow | Medium | Low | Cache model in CI; or mock model in unit tests, use real model only in integration |
| Config mapping misses an argument | Low | Medium | Add a test that verifies every CLI arg with a config counterpart is in the mapping |

---

## Success Metrics

- [ ] All 4 phases completed (16 work items)
- [ ] All acceptance criteria met
- [ ] `src/cli.py` monolith eliminated — replaced by ~10 files averaging 150–250 lines
- [ ] `src/main.py` legacy code removed (565 lines deleted)
- [ ] Zero duplicated stop word lists, magic numbers, or confidence score mappings
- [ ] Category templates editable without code changes
- [ ] Sender classification keywords configurable via YAML
- [ ] Rate limiting detected by exception type, not string matching
- [ ] CI pipeline enforcing lint + test + coverage on every push
- [ ] Test count maintained or increased (currently 1,663)
- [ ] Coverage maintained or increased (currently 86%)

---

## Appendix: Requirement Traceability

| Audit Finding | Severity | Phase | Work Item |
|---------------|----------|-------|-----------|
| H1: CLI god module (2,424 lines) | High | 3 | 3.1 |
| H2: Batch loop duplication in BaseExtractor | High | 2 | 2.1 |
| H3: Dead code in AnalysisService | High | 1 | 1.1 |
| M1: Stop word lists duplicated across 3 modules | Medium | 1 | 1.2 |
| M2: Magic numbers scattered throughout | Medium | 1 | 1.3 |
| M3: Hardcoded sender classification keywords | Medium | 3 | 3.3 |
| M4: ExtractionService M365/Gmail branches identical | Medium | 2 | 2.2 |
| M5: Config application uses manual hasattr checks | Medium | 2 | 2.3 |
| M6: Domain stripping hardcodes .com only | Medium | 2 | 2.4 |
| M7: CategoryTemplate is 294-line source constant | Medium | 3 | 3.2 |
| M8: Source confidence scores duplicated | Medium | 1 | 1.4 |
| M9: Rate limit detection via string matching | Medium | 2 | 2.5 |
| L1: src/main.py is legacy, overlaps with cli.py | Low | 1 | 1.5 |
| L2: Empty contract test directory | Low | 4 | 4.2 |
| L3: No pre-commit hooks or CI pipeline | Low | 4 | 4.1 |
| L7: Elbow optimizer confidence calculation ad-hoc | Low | 4 | 4.3 |

**Items requiring no change (documented in audit, excluded from plan):**
- L4: Union-Find lacks union-by-rank — path compression sufficient for 10K–50K corpus
- L5: SuggestionService pass-through — kept for architectural consistency
- L6: Template matcher regex cache not thread-safe — single-threaded usage

**Long-term considerations (not in this plan):**
- LT2: Register own Azure App — when headless/scheduled operation needed
- LT3: Evaluate SQLite for corpus — when corpus exceeds 20K+ emails
- LT4: Property-based contract tests with Hypothesis — when adding new implementations

---

*Implementation plan generated by Claude on 2026-02-15*
*Source: Architectural audit (4 parallel agent sweeps) + findings walkthrough + user clarifications*
