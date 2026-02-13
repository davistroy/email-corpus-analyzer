# Implementation Plan

**Generated:** 2026-02-13
**Source Documents:**
- `specs/001-use-the-document/spec.md` (51 functional requirements)
- `specs/001-use-the-document/data-model.md` (7 entity schemas)
- `specs/001-use-the-document/contracts/` (3 interface contracts)
- `docs/RECOMMENDATIONS.md` (23 improvement recommendations)
- Deep codebase analysis (4 parallel agent sweeps, Feb 2026)

**Total Phases:** 4
**Estimated Total Effort:** ~190,000 tokens

---

## Executive Summary

The email-corpus-analyzer is a well-architected 11K-line Python application with 1,403 tests at 83% coverage. It extracts emails from Hotmail/Gmail, runs ML-powered analysis (semantic clustering, sender frequency, temporal patterns), generates category suggestions, and exports actionable Outlook rules / Gmail filters.

This plan addresses findings from a comprehensive codebase audit. The most critical issue is a broken extraction wiring — `ExtractionService` references an MCP stub that doesn't function standalone, while a fully working `GraphAPIClient`-based extractor sits orphaned. Beyond that, the plan targets analysis quality improvements (more text for embeddings, configurable thresholds, better template matching), robustness hardening (cache versioning, atomic writes, MIME recursion), and intelligence calibration (confidence scoring, temporal decay in learning, cluster visualization).

Many items from the original `docs/RECOMMENDATIONS.md` (Jan 2025) have already been implemented: BaseAnalyzer ABC, service layer, exception hierarchy, thread analyzer, rule exporters, TUI bulk operations, config validation. This plan focuses exclusively on **new work** identified by the Feb 2026 analysis.

---

## Plan Overview

The implementation follows a risk-first strategy: fix the critical extraction break first (Phase 1), then improve the quality of analysis results (Phase 2), harden reliability and edge cases (Phase 3), and finally calibrate the intelligence layer (Phase 4). Each phase leaves the codebase in a working, tested state.

### Phase Summary Table

| Phase | Focus Area | Key Deliverables | Est. Tokens | Dependencies |
|-------|------------|------------------|-------------|--------------|
| 1 | Extraction Fix | Rewire services, unify paths, delete stub | ~40K | None |
| 2 | Analysis Quality | More embedding text, config externalization, better matching | ~60K | Phase 1 |
| 3 | Robustness | Cache versioning, MIME recursion, atomic writes | ~50K | Phase 1 |
| 4 | Intelligence | Confidence calibration, learning decay, visualization | ~40K | Phase 2, 3 |

---

## Phase 1: Critical Extraction Fix

**Estimated Effort:** ~40,000 tokens (including testing/fixes)
**Dependencies:** None
**Parallelizable:** Work items 1.1–1.3 are sequential; 1.4 can run in parallel

### Goals

- Make `PipelineService` → `ExtractionService` work end-to-end standalone
- Unify CLI and service layer extraction paths so both use the same code
- Remove dead/orphaned extraction code

### Work Items

#### 1.1 Rewire ExtractionService to Real Extractors

**Requirement Refs:** FR-001, FR-002, FR-003
**Files Affected:**
- `src/services/extraction_service.py` (modify)
- `src/extractors/m365_mcp_extractor.py` (delete)
- `src/extractors/m365_mcp_client.py` (delete)
- `tests/unit/test_services.py` (modify)
- `tests/unit/test_extractors.py` (modify)

**Description:**
`ExtractionService._get_extractor()` currently imports `M365MCPExtractor` from `m365_mcp_extractor.py` — a stub that relies on Claude Code's MCP context to replace comment blocks with API calls. It literally falls through to `batch_messages = []` when run standalone. Meanwhile, `EmailExtractor` in `m365_extractor.py` uses `GraphAPIClient` with real MSAL device code auth and actually works.

**Tasks:**
1. [ ] Replace `M365MCPExtractor` import with `EmailExtractor` from `m365_extractor.py`
2. [ ] Update `_get_extractor()` to instantiate `EmailExtractor` with correct params (user_email, checkpoint_dir, client_id)
3. [ ] Map `ExtractionService.run()` to call `EmailExtractor.extract_all()` or `extract_incremental()` based on `since_last` flag
4. [ ] Convert `EmailExtractor.ExtractionResult` → `Corpus` return type expected by service
5. [ ] Delete `src/extractors/m365_mcp_extractor.py` and `src/extractors/m365_mcp_client.py`
6. [ ] Update all imports and `__init__.py` exports
7. [ ] Update tests — remove M365MCPExtractor test fixtures, add ExtractionService integration tests

**Acceptance Criteria:**
- [ ] `PipelineService.run()` successfully extracts emails when M365 auth is configured
- [ ] `ExtractionService` no longer references any MCP stub code
- [ ] All existing tests pass (with updated mocks)
- [ ] `m365_mcp_extractor.py` and `m365_mcp_client.py` are removed from repo

**Notes:**
The `ExtractionResult` dataclass from `m365_extractor.py` contains `corpus`, `failed_emails`, `success_count`, etc. The service currently expects a bare `Corpus` return. Either adapt the service to use `ExtractionResult` (preferred — preserves error info) or unwrap it.

---

#### 1.2 Add Gmail Support to ExtractionService

**Requirement Refs:** CLI `--source` flag
**Files Affected:**
- `src/services/extraction_service.py` (modify)
- `src/config/models.py` (modify — add `source` field to `ExtractConfig`)
- `tests/unit/test_services.py` (modify)

**Description:**
`ExtractionService` currently only wires to M365. The CLI's `--source hotmail|gmail|both` flag likely bypasses the service layer entirely, creating two extraction code paths. Both should go through the service.

**Tasks:**
1. [ ] Add `source: str = "hotmail"` field to `ExtractConfig` (values: hotmail, gmail, both)
2. [ ] Add `gmail_email: str | None = None` to `ExtractConfig` for separate Gmail address
3. [ ] Update `ExtractionService._get_extractor()` to return appropriate extractor based on `config.source`
4. [ ] For `source="both"`, run both extractors and merge corpora (deduplicate by email ID)
5. [ ] Update CLI to delegate extraction to `ExtractionService` instead of directly instantiating extractors
6. [ ] Write tests for all three source modes

**Acceptance Criteria:**
- [ ] `python -m src.cli pipeline --source gmail --user-email user@gmail.com` works through the service layer
- [ ] `python -m src.cli pipeline --source both --user-email user@hotmail.com --gmail-email user@gmail.com` works
- [ ] CLI and `PipelineService` use identical extraction code paths

---

#### 1.3 Consolidate Extractor Base Class

**Requirement Refs:** DRY principle; RECOMMENDATIONS.md A1
**Files Affected:**
- `src/extractors/base_extractor.py` (create)
- `src/extractors/m365_extractor.py` (modify)
- `src/extractors/gmail_extractor.py` (modify)
- `tests/unit/test_extractors.py` (modify)

**Description:**
`EmailExtractor` (M365) and `GmailExtractor` share ~70% identical code: checkpoint handling, batch loop, error collection, progress callbacks, `_process_email()`. Extract shared logic into a base class.

**Tasks:**
1. [ ] Create `BaseExtractor` ABC in `src/extractors/base_extractor.py`
2. [ ] Move shared methods: `_process_email()`, checkpoint save/load/resume, batch loop logic, error collection
3. [ ] Define abstract methods: `_fetch_batch()`, `_get_api_client()`, `_build_incremental_query()`
4. [ ] Refactor `EmailExtractor` and `GmailExtractor` to inherit from `BaseExtractor`
5. [ ] Move `ExtractionResult` and `IncrementalExtractionResult` dataclasses to base module
6. [ ] Update tests — verify both extractors still pass, add base class contract tests

**Acceptance Criteria:**
- [ ] `EmailExtractor` and `GmailExtractor` each contain only API-specific code
- [ ] All 1,403+ existing tests pass
- [ ] No code duplication between the two extractors

---

#### 1.4 Improve Checkpoint Efficiency

**Requirement Refs:** FR-010
**Files Affected:**
- `src/extractors/checkpoint_manager.py` (modify)
- `tests/unit/test_extractors.py` (modify)

**Description:**
The checkpoint manager currently stores **full email objects** in the checkpoint file. For 1,000+ emails, this creates 10–50MB checkpoint files. Store only resume metadata instead.

**Tasks:**
1. [ ] Change checkpoint format to store only: `emails_processed`, `last_processed_id`, `timestamp`, `checkpoint_interval` (remove `extracted_emails` array)
2. [ ] On resume, re-fetch from API starting at saved offset rather than replaying from checkpoint
3. [ ] Add integrity check: verify `emails_processed` is consistent on load
4. [ ] Add checkpoint format version field for future migration
5. [ ] Update tests for new checkpoint format

**Acceptance Criteria:**
- [ ] Checkpoint files are < 1KB regardless of corpus size
- [ ] Resume-from-checkpoint still works correctly (verified by test)
- [ ] Old-format checkpoints are handled gracefully (warn and restart fresh)

---

### Phase 1 Testing Requirements

- [ ] `ExtractionService` unit tests with mocked `EmailExtractor` and `GmailExtractor`
- [ ] Integration test: `PipelineService.run()` with mock API responses
- [ ] Checkpoint resume test with new compact format
- [ ] All existing 1,403+ tests pass with no regressions

### Phase 1 Completion Checklist

- [ ] All work items complete
- [ ] MCP stub files deleted
- [ ] All tests passing
- [ ] CLAUDE.md updated with any changed commands
- [ ] No regressions introduced

---

## Phase 2: Analysis Quality Improvements

**Estimated Effort:** ~60,000 tokens (including testing/fixes)
**Dependencies:** Phase 1 (extraction must work for end-to-end validation)
**Parallelizable:** Items 2.1–2.4 are independent; 2.5 depends on 2.3

### Goals

- Give the semantic analyzer more text to work with (better clustering)
- Make all hardcoded thresholds configurable via YAML
- Fix brittle template matching that produces false positives
- Scale auto-cluster count intelligently with corpus size

### Work Items

#### 2.1 Increase combined_text Length for Embeddings

**Requirement Refs:** FR-015, FR-016, FR-017
**Files Affected:**
- `src/models/email.py` (modify)
- `src/config/models.py` (modify)
- `tests/unit/test_models.py` (modify)

**Description:**
`Email.combined_text` truncates body at 500 chars. The embedding model (mxbai-embed-large-v1) supports 512 tokens (~2000 chars). Truncating at 500 means clustering is based on subject + first ~3 sentences, missing action items, signatures, and key content deeper in email bodies. This directly degrades clustering quality for threaded/corporate emails.

**Tasks:**
1. [ ] Change `combined_text` property to use 1500 chars: `f"{self.subject} {self.body_text[:1500]}"`
2. [ ] Add `max_embedding_text_length` to `AnalyzeConfig` (default: 1500, range: 200–5000)
3. [ ] Thread the config value through `SemanticAnalyzer` so it's not hardcoded in the model
4. [ ] Update tests — verify combined_text respects new length
5. [ ] Run embedding cache invalidation note in docs (old cache incompatible after change)

**Acceptance Criteria:**
- [ ] `combined_text` returns subject + up to 1500 chars of body by default
- [ ] Length is configurable via YAML config
- [ ] Existing tests updated and passing

**Notes:**
This change invalidates any existing embedding cache. Document this in CLAUDE.md and consider auto-invalidation via cache versioning (Phase 3, item 3.1).

---

#### 2.2 Externalize Magic Numbers to Config

**Requirement Refs:** All analysis FRs
**Files Affected:**
- `src/config/models.py` (modify — add new config fields)
- `src/analyzers/sender_analyzer.py` (modify)
- `src/analyzers/subject_analyzer.py` (modify)
- `src/analyzers/semantic_analyzer.py` (modify)
- `src/analyzers/temporal_analyzer.py` (modify)
- `src/analyzers/cluster_optimizer.py` (modify)
- `src/generators/category_generator.py` (modify)
- `src/generators/template_matcher.py` (modify)
- `src/generators/confidence_scorer.py` (modify)
- `tests/unit/test_config_models.py` (modify)

**Description:**
16 hardcoded thresholds are scattered across analyzers and generators. These should be exposed in the existing YAML config system so users can tune them without modifying code.

**Tasks:**
1. [ ] Add `AnalyzerThresholds` model to `config/models.py`:
   - `top_senders: int = 50` (SenderAnalyzer)
   - `top_domains: int = 30` (SenderAnalyzer)
   - `marketing_min_emails: int = 10` (SenderAnalyzer)
   - `top_keywords: int = 50` (SubjectAnalyzer)
   - `max_auto_clusters: int = 15` (SemanticAnalyzer)
   - `representative_samples: int = 5` (SemanticAnalyzer)
   - `random_state: int = 42` (SemanticAnalyzer)
   - `frequency_daily_threshold_days: float = 2.0` (TemporalAnalyzer)
   - `frequency_weekly_threshold_days: float = 8.0` (TemporalAnalyzer)
   - `frequency_monthly_threshold_days: float = 35.0` (TemporalAnalyzer)
   - `min_emails_for_frequency: int = 10` (TemporalAnalyzer)
2. [ ] Add `GeneratorThresholds` model:
   - `min_cluster_percentage: float = 5.0` (CategoryGenerator — already in SuggestConfig, wire it)
   - `max_senders_for_categories: int = 20` (CategoryGenerator)
   - `merge_name_similarity: float = 0.8` (CategoryGenerator)
   - `merge_email_overlap: float = 0.7` (CategoryGenerator)
   - `confidence_source_weights` dict (ConfidenceScorer)
3. [ ] Nest under `AnalyzeConfig.thresholds` and `SuggestConfig.thresholds`
4. [ ] Thread config through each analyzer/generator constructor
5. [ ] Replace all hardcoded values with config lookups
6. [ ] Add validation bounds for each field
7. [ ] Update `config init` template to include new fields (commented out as advanced options)
8. [ ] Write tests for custom threshold values

**Acceptance Criteria:**
- [ ] All 16 previously-hardcoded values are now configurable via YAML
- [ ] Default values match current behavior (no behavior change without config)
- [ ] `python -m src.cli config show` displays all threshold values
- [ ] Config validation rejects out-of-range values

---

#### 2.3 Fix Template Matching Brittleness

**Requirement Refs:** FR-024
**Files Affected:**
- `src/generators/template_matcher.py` (modify)
- `tests/unit/test_template_matcher.py` (modify)

**Description:**
`TemplateMatcher` uses substring matching (`keyword in text_lower`), causing false positives: "visa" matches "provisioning", "amazon" matches "amazonas", "mail" in domain matches "email.example.com". Switch to word-boundary regex for keywords and suffix-based matching for domains.

**Tasks:**
1. [ ] Replace `keyword in text_lower` with `re.search(r'\b' + re.escape(keyword) + r'\b', text_lower)` for all keyword matching
2. [ ] Replace `domain in sender_domain_lower` with proper domain suffix matching: `sender_domain_lower.endswith(domain) or sender_domain_lower == domain`
3. [ ] Pre-compile regex patterns at template initialization time (avoid recompiling per email)
4. [ ] Add test cases for false-positive scenarios: "visa" in "provisioning", "amazon" in "amazonas"
5. [ ] Verify existing template matching still works with updated logic

**Acceptance Criteria:**
- [ ] "visa" does NOT match "provisioning" or "advisory"
- [ ] "amazon.com" matches "amazon.com" but NOT "notamazon.com"
- [ ] "mail" in domain list does NOT match "email.example.com"
- [ ] All 18 templates still match their intended emails correctly
- [ ] No performance regression (pre-compiled patterns)

---

#### 2.4 Smart Auto-Cluster Count Scaling

**Requirement Refs:** FR-016
**Files Affected:**
- `src/analyzers/semantic_analyzer.py` (modify)
- `src/analyzers/cluster_optimizer.py` (modify)
- `tests/unit/test_analyzers.py` (modify)
- `tests/unit/test_cluster_optimizer.py` (modify)

**Description:**
Current `max_k = min(15, total_emails - 1)` is too many for small corpora (50 emails → 15 clusters = 30% singletons) and too few for large ones (10K emails → 15 clusters = very broad). Use a corpus-size-aware heuristic.

**Tasks:**
1. [ ] Replace fixed `max_k=15` with: `max_k = min(int(math.sqrt(n_emails / 5)), 25)` clamped to range [3, configurable_max]
   - 100 emails → max_k ≈ 4
   - 1,000 emails → max_k ≈ 14
   - 10,000 emails → max_k ≈ 25 (capped)
2. [ ] Make the formula configurable: `auto_cluster_max` in `AnalyzerThresholds` (default: 25)
3. [ ] Add `auto_cluster_min` (default: 3) for small corpora
4. [ ] Update cluster optimizer to respect new bounds
5. [ ] Write tests covering small (50), medium (1K), and large (10K) corpus sizes

**Acceptance Criteria:**
- [ ] 50-email corpus doesn't produce more than ~4-5 clusters in auto mode
- [ ] 10K-email corpus can produce up to 25 clusters
- [ ] Bounds are configurable via YAML
- [ ] Existing auto-clustering tests updated and passing

---

#### 2.5 DRY Up Dual Analysis Functions

**Requirement Refs:** Code quality
**Files Affected:**
- `src/analyzers/__init__.py` (modify)
- `src/services/analysis_service.py` (modify)
- `tests/unit/test_analyzers.py` (modify)

**Description:**
`run_full_analysis()` and `run_full_analysis_incremental()` are 90% identical — the only difference is `SemanticAnalyzer.analyze()` vs `SemanticAnalyzer.analyze_incremental()` call. Merge into a single function with optional `embedding_cache` parameter.

**Tasks:**
1. [ ] Merge into single `run_full_analysis(corpus, embedding_cache=None, ...)` function
2. [ ] If `embedding_cache` provided, use `analyze_incremental()`; otherwise use `analyze()`
3. [ ] Return `(AnalysisResults, incremental_stats | None)` tuple
4. [ ] Update `AnalysisService.run()` to use unified function
5. [ ] Remove `run_full_analysis_incremental` from exports and update all callers
6. [ ] Update tests

**Acceptance Criteria:**
- [ ] Single `run_full_analysis()` function handles both modes
- [ ] `__all__` export list updated
- [ ] All tests pass

---

### Phase 2 Testing Requirements

- [ ] Embedding length tests with configurable values
- [ ] Config threshold validation tests (bounds, defaults)
- [ ] Template matcher false-positive regression tests
- [ ] Auto-cluster scaling tests across corpus sizes
- [ ] All 1,403+ existing tests pass

### Phase 2 Completion Checklist

- [ ] All work items complete
- [ ] All tests passing
- [ ] CLAUDE.md updated (new config fields documented)
- [ ] `config init` template includes new threshold options
- [ ] No regressions introduced

---

## Phase 3: Robustness & Reliability

**Estimated Effort:** ~50,000 tokens (including testing/fixes)
**Dependencies:** Phase 1 (extraction fix)
**Parallelizable:** All items 3.1–3.6 are independent

### Goals

- Prevent silent data corruption from model/cache mismatches
- Handle deeply nested email MIME structures
- Make file operations atomic and crash-safe
- Improve thread detection for emails missing headers

### Work Items

#### 3.1 Add Embedding Cache Versioning

**Requirement Refs:** Reliability
**Files Affected:**
- `src/cache/embedding_cache.py` (modify)
- `tests/unit/test_embedding_cache.py` (modify)

**Description:**
If the embedding model changes (upgrade sentence-transformers, switch to different model), the cached `.npz` file becomes silently incompatible — embeddings computed with model A get mixed with model B. Store model metadata in cache and auto-invalidate on mismatch.

**Tasks:**
1. [ ] Add metadata fields to cache: `model_name`, `model_version`, `embedding_dim`, `max_text_length`, `created_at`
2. [ ] On cache load, compare stored metadata against current config
3. [ ] If model name or embedding dimension mismatches, log warning and invalidate entire cache
4. [ ] If `max_text_length` changed (Phase 2, item 2.1), invalidate cache (embeddings computed on different text lengths)
5. [ ] Store metadata in separate `.json` sidecar file alongside `.npz`
6. [ ] Write tests for version mismatch detection and auto-invalidation

**Acceptance Criteria:**
- [ ] Changing embedding model name auto-invalidates cache with warning
- [ ] Changing `max_embedding_text_length` auto-invalidates cache
- [ ] Cache created with current config loads without issue
- [ ] Old caches without metadata are treated as invalid (fresh start)

---

#### 3.2 Thread Analysis Subject-Based Fallback

**Requirement Refs:** Phase 8A.1 (thread analysis)
**Files Affected:**
- `src/analyzers/thread_analyzer.py` (modify)
- `tests/unit/test_thread_analyzer.py` (modify)

**Description:**
`ThreadAnalyzer` relies on `In-Reply-To` and `References` headers, which are often stripped or missing (web-based senders, forwarded emails, some corporate systems). Add a heuristic fallback: emails with matching normalized subjects from the same sender domain within a time window are likely the same thread.

**Tasks:**
1. [ ] Add subject-normalization function: strip RE:/FWD:/FW: prefixes, normalize whitespace, lowercase
2. [ ] After header-based grouping, run second pass: ungrouped emails with matching normalized subjects + same sender domain + within 7-day window → merge into thread
3. [ ] Make time window configurable (default: 7 days)
4. [ ] Add `thread_method` field to each thread: "header" or "subject_heuristic" for transparency
5. [ ] Write tests with emails that have no In-Reply-To but matching subjects

**Acceptance Criteria:**
- [ ] Emails with stripped headers but matching subjects are grouped correctly
- [ ] Heuristic doesn't over-group (different topics with similar subjects stay separate)
- [ ] Thread method is tracked for each group
- [ ] Time window is configurable

---

#### 3.3 Gmail Recursive MIME Extraction

**Requirement Refs:** FR-004
**Files Affected:**
- `src/extractors/gmail_client.py` (modify)
- `tests/unit/test_gmail_extractor.py` (modify)

**Description:**
`GmailClient._extract_body()` handles only 2 levels of MIME nesting (parts → nested_parts). Real emails can have 3+ levels: `multipart/mixed → multipart/alternative → text/html`. Make this recursive.

**Tasks:**
1. [ ] Refactor `_extract_body()` to use recursive helper: `_extract_body_recursive(payload, depth=0, max_depth=10)`
2. [ ] Recurse into any part with `parts` array
3. [ ] Collect all `text/html` and `text/plain` parts, prefer HTML
4. [ ] Add `max_depth` guard to prevent infinite recursion on malformed messages
5. [ ] Write tests with 3-level and 4-level nested MIME structures

**Acceptance Criteria:**
- [ ] 3+ level nested MIME emails have their body extracted correctly
- [ ] Recursion depth is bounded (no stack overflow on malformed email)
- [ ] HTML content is still preferred over plain text
- [ ] Existing 2-level tests still pass

---

#### 3.4 Atomic Writes for Approval Saving

**Requirement Refs:** FR-036, data integrity
**Files Affected:**
- `src/ui/category_review.py` (modify)
- `src/services/pipeline_service.py` (modify)
- `src/utils/file_manager.py` (modify)

**Description:**
If `save_approved_categories()` or any JSON write fails mid-write (crash, disk full, permission error), the output file is corrupted. Use temp-file-then-rename pattern for all critical writes.

**Tasks:**
1. [ ] Create `atomic_write(path, content)` utility in `file_manager.py`
   - Write to `path.tmp` in same directory
   - `os.replace(path.tmp, path)` on success (atomic on all platforms)
   - Clean up `.tmp` on failure
2. [ ] Use `atomic_write()` for: `approved_categories.json`, `email_corpus.json`, `corpus_analysis_results.json`, `category_suggestions.json`
3. [ ] Update `PipelineService` file saves to use atomic writes
4. [ ] Write tests: verify file is either fully written or not modified

**Acceptance Criteria:**
- [ ] Interrupted writes don't corrupt existing files
- [ ] `.tmp` files are cleaned up on failure
- [ ] All critical JSON outputs use atomic writes

---

#### 3.5 HTML Exporter Template Validation

**Requirement Refs:** Export reliability
**Files Affected:**
- `src/exporters/html_exporter.py` (modify)
- `tests/unit/test_exporters.py` (modify)

**Description:**
`env.get_template("report.html.j2")` throws an opaque Jinja2 error if the template file is missing from the distribution. Add a clear error with recovery hint.

**Tasks:**
1. [ ] Wrap template loading in try/except with `ExportError` that includes template path and recovery instructions
2. [ ] Validate template directory exists at module load time
3. [ ] Add test for missing template scenario

**Acceptance Criteria:**
- [ ] Missing template produces clear error: "Template not found at {path}. Reinstall package or check installation."
- [ ] Existing export tests pass

---

#### 3.6 M365 Incremental Extraction with Server-Side Filtering

**Requirement Refs:** FR-002, performance
**Files Affected:**
- `src/extractors/graph_api_client.py` (modify)
- `src/extractors/m365_extractor.py` (modify)
- `tests/unit/test_extractors.py` (modify)

**Description:**
M365 incremental extraction currently fetches ALL emails and deduplicates client-side. Gmail correctly uses `after:YYYY/MM/DD` server-side. The Graph API supports `$filter=receivedDateTime gt {date}` which would make M365 incremental extraction equally efficient.

**Tasks:**
1. [ ] Add `filter_after` parameter to `GraphAPIClient.fetch_emails()`
2. [ ] Construct OData filter: `$filter=receivedDateTime gt {iso_date}`
3. [ ] Update `EmailExtractor.extract_incremental()` to pass `last_extraction_date` as filter
4. [ ] Keep client-side dedup as safety net (filter + dedup)
5. [ ] Write test verifying filter parameter is sent in API request

**Acceptance Criteria:**
- [ ] Incremental extraction sends date filter to Graph API
- [ ] Only new emails are fetched (verified by mock)
- [ ] Client-side dedup still works as safety net
- [ ] Full extraction (no filter) still works

---

### Phase 3 Testing Requirements

- [ ] Cache versioning: mismatch detection, auto-invalidation
- [ ] Thread heuristic: subject matching with and without headers
- [ ] MIME recursion: 3-level, 4-level, malformed structures
- [ ] Atomic writes: interruption simulation
- [ ] All 1,403+ existing tests pass

### Phase 3 Completion Checklist

- [ ] All work items complete
- [ ] All tests passing
- [ ] No regressions introduced

---

## Phase 4: Intelligence & Calibration

**Estimated Effort:** ~40,000 tokens (including testing/fixes)
**Dependencies:** Phase 2 (config externalization), Phase 3 (cache versioning)
**Parallelizable:** All items 4.1–4.4 are independent

### Goals

- Make confidence scores more meaningful and calibratable
- Add temporal awareness to the learning system
- Provide visual feedback on cluster quality
- Improve silhouette score interpretation

### Work Items

#### 4.1 Confidence Scoring Improvements

**Requirement Refs:** FR-025
**Files Affected:**
- `src/generators/confidence_scorer.py` (modify)
- `src/generators/category_generator.py` (modify)
- `tests/unit/test_confidence_scorer.py` (modify)

**Description:**
Current confidence averaging is unjustified (why 1/3 weight each?). The enhanced scorer has configurable weights but distinctiveness uses `max_overlap` instead of `mean_overlap`, and percentage score breaks for small corpora (5% = 0.05 confidence). Improve the scoring to be more meaningful.

**Tasks:**
1. [ ] Change distinctiveness from `1.0 - max_overlap` to `1.0 - mean_overlap` (average across all other categories)
2. [ ] Fix percentage score: use `min(1.0, percentage / 10.0)` instead of `percentage / 100.0` so a 10% category gets 1.0 (not 0.1)
3. [ ] Add logarithmic volume scaling: `min(1.0, log10(email_count + 1) / log10(101))` so 100 emails = 1.0, 10 emails ≈ 0.5
4. [ ] Make all weights configurable via `GeneratorThresholds` from Phase 2
5. [ ] Add confidence breakdown to export outputs (HTML and CSV)
6. [ ] Write tests verifying improved scoring across small/medium/large corpora

**Acceptance Criteria:**
- [ ] 10-email category in 200-email corpus gets reasonable confidence (not 0.05)
- [ ] Distinctiveness reflects average separation, not worst case
- [ ] Weights are configurable via YAML
- [ ] Confidence breakdown visible in exports

---

#### 4.2 Pattern Detector Temporal Decay

**Requirement Refs:** Learning system quality
**Files Affected:**
- `src/learning/pattern_detector.py` (modify)
- `tests/unit/test_pattern_detector.py` (modify)

**Description:**
Pattern confidence is calculated purely from occurrence count. A rename pattern from 6 months ago is weighted identically to one from yesterday. Add time-based decay so recent decisions have more influence.

**Tasks:**
1. [ ] Add decay factor to confidence calculation: `weight = exp(-days_old / half_life_days)`
2. [ ] Default `half_life_days = 90` (configurable) — patterns lose half their weight every 90 days
3. [ ] Weight each occurrence by its recency before computing pattern confidence
4. [ ] Add `learning.pattern_half_life_days` to config
5. [ ] Write tests with old vs recent decisions, verify recency bias

**Acceptance Criteria:**
- [ ] Pattern from 180 days ago contributes ~25% of a recent pattern's weight
- [ ] Half-life is configurable
- [ ] Very old patterns (>365 days) have negligible influence
- [ ] Recent-only patterns reach high confidence faster

---

#### 4.3 Cluster Quality Visualization

**Requirement Refs:** FR-015 (analysis quality transparency)
**Files Affected:**
- `src/analyzers/semantic_analyzer.py` (modify)
- `src/exporters/html_exporter.py` (modify)
- `src/cli.py` (modify — add `--cluster-viz` flag)
- `tests/unit/test_analyzers.py` (modify)

**Description:**
After analysis, there's no visual way to assess whether clustering worked well. Add a PCA scatter plot of embeddings colored by cluster, saved as part of analysis output. Also add per-cluster silhouette bars.

**Tasks:**
1. [ ] Add `generate_cluster_visualization(embeddings, labels, output_path)` to semantic analyzer
2. [ ] Use PCA to reduce to 2D, matplotlib scatter plot colored by cluster
3. [ ] Add silhouette bar chart (per-cluster scores)
4. [ ] Save as `cluster_visualization.png` in output directory
5. [ ] Add `--cluster-viz` flag to `analyze` command (off by default to avoid matplotlib dependency)
6. [ ] Make matplotlib an optional dependency (`pip install email-corpus-analyzer[viz]`)
7. [ ] Include visualization in HTML export report if available

**Acceptance Criteria:**
- [ ] `analyze --cluster-viz` produces a scatter plot PNG
- [ ] Clusters are visually distinguishable by color
- [ ] Silhouette bar chart shows per-cluster quality
- [ ] Works without matplotlib installed (graceful skip with warning)

---

#### 4.4 Improved Silhouette Score Interpretation

**Requirement Refs:** Clustering quality
**Files Affected:**
- `src/analyzers/cluster_optimizer.py` (modify)
- `tests/unit/test_cluster_optimizer.py` (modify)

**Description:**
Silhouette score normalized linearly from [-1, 1] to [0, 1] via `(score + 1) / 2`. This means a score of 0 (ambiguous clustering) becomes 0.5 confidence, and -0.3 (bad clustering) becomes 0.35 — which users might interpret as "fair." Use a sigmoid mapping that punishes negative scores more aggressively.

**Tasks:**
1. [ ] Replace linear normalization with sigmoid: `1 / (1 + exp(-5 * score))` so:
   - score = 0.5 → confidence ≈ 0.92 (good)
   - score = 0.0 → confidence = 0.50 (neutral)
   - score = -0.3 → confidence ≈ 0.18 (clearly bad)
2. [ ] Add interpretation labels: >0.7 "strong", 0.4-0.7 "moderate", <0.4 "weak"
3. [ ] Include interpretation in analysis output JSON
4. [ ] Update tests

**Acceptance Criteria:**
- [ ] Negative silhouette scores map to clearly low confidence (<0.3)
- [ ] Positive scores above 0.5 map to high confidence (>0.9)
- [ ] Interpretation labels included in output
- [ ] All optimizer tests updated and passing

---

### Phase 4 Testing Requirements

- [ ] Confidence scoring tests across corpus sizes (small/medium/large)
- [ ] Temporal decay tests with synthetic decision histories
- [ ] Visualization generation (if matplotlib available)
- [ ] Silhouette interpretation boundary tests
- [ ] All 1,403+ existing tests pass

### Phase 4 Completion Checklist

- [ ] All work items complete
- [ ] All tests passing
- [ ] CLAUDE.md updated with new flags and config options
- [ ] No regressions introduced

---

## Parallel Work Opportunities

| Work Item | Can Run With | Notes |
|-----------|--------------|-------|
| 1.4 (Checkpoint efficiency) | 1.1–1.3 | Independent of extraction rewiring |
| 2.1 (Embedding text length) | 2.2, 2.3, 2.4 | Only changes model property |
| 2.3 (Template matching) | 2.1, 2.2, 2.4 | Generator layer, no analyzer deps |
| 3.1–3.6 (All Phase 3 items) | Each other | All independently scoped |
| 4.1–4.4 (All Phase 4 items) | Each other | All independently scoped |

---

## Risk Mitigation

| Risk | Likelihood | Impact | Mitigation Strategy |
|------|------------|--------|---------------------|
| Extraction rewiring breaks auth flow | Medium | High | Test with real M365 account before merging; keep GraphAPIClient unchanged |
| Embedding cache invalidation loses user's work | Low | Medium | Warn user before invalidating; keep old cache as backup (.npz.bak) |
| Template matching regex too strict | Low | Medium | Run against existing test corpus; compare match counts before/after |
| Config model changes break existing YAML files | Medium | Medium | Ensure all new fields have defaults matching current behavior |
| matplotlib dependency bloats install | Low | Low | Make optional (`[viz]` extra); degrade gracefully |

---

## Success Metrics

- [ ] All 4 phases completed
- [ ] All acceptance criteria met across 19 work items
- [ ] `PipelineService.run()` works end-to-end standalone (no Claude Code MCP dependency)
- [ ] Test count maintained or increased (currently 1,403)
- [ ] Coverage maintained or increased (currently 83%)
- [ ] No hardcoded analysis thresholds remain in source code
- [ ] False-positive template matches eliminated (visa/provisioning, etc.)
- [ ] Embedding cache self-validates against model changes

---

## Appendix: Requirement Traceability

| Requirement | Source | Phase | Work Item |
|-------------|--------|-------|-----------|
| FR-001 (M365 connection) | spec.md | 1 | 1.1 |
| FR-002 (Pagination) | spec.md | 1, 3 | 1.1, 3.6 |
| FR-003 (Email details) | spec.md | 1 | 1.1 |
| FR-004 (HTML to text) | spec.md | 3 | 3.3 |
| FR-010 (Checkpoint) | spec.md | 1 | 1.4 |
| FR-015 (Semantic analysis) | spec.md | 2, 4 | 2.1, 4.3 |
| FR-016 (Cluster config) | spec.md | 2 | 2.4 |
| FR-017 (Representative samples) | spec.md | 2 | 2.1 |
| FR-024 (Templates) | spec.md | 2 | 2.3 |
| FR-025 (Confidence scores) | spec.md | 4 | 4.1 |
| FR-036 (Save approved) | spec.md | 3 | 3.4 |
| DRY (code quality) | Analysis | 1, 2 | 1.3, 2.5 |
| Magic numbers | Analysis | 2 | 2.2 |
| Cache versioning | Analysis | 3 | 3.1 |
| Thread robustness | Analysis | 3 | 3.2 |
| Learning quality | Analysis | 4 | 4.2 |
| Clustering transparency | Analysis | 4 | 4.3, 4.4 |

---

*Implementation plan generated by Claude on 2026-02-13*
*Source: Deep codebase analysis (4 parallel agent sweeps) + spec.md + RECOMMENDATIONS.md*
