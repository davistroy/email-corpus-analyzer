# Tasks: Email Corpus Extraction and Analysis System

**Input**: Design documents from `/home/davistroy/dev/email-processor/initial-learning/specs/001-use-the-document/`
**Prerequisites**: plan.md, research.md, data-model.md, contracts/

## Execution Flow (main)
```
1. Load plan.md from feature directory
   → Tech stack: Python 3.10+, sentence-transformers, scikit-learn, beautifulsoup4
   → Structure: Single project (CLI-based data processing pipeline)
   → Verify: research.md contains Context7 queries for all libraries ✓
2. Load design documents:
   → data-model.md: 7 entities (Email, Corpus, Sender, AnalysisResults, ContentCluster, Category, CategoryTemplate)
   → contracts/: 3 contract files (extractor, analyzer, generator)
   → research.md: Context7 decisions for all libraries ✓
3. Generate tasks by category:
   → Setup: Python project, dependencies, directory structure
   → Tests: 3 contract tests, 5 integration tests
   → Core: 7 Pydantic models, 5 analyzers, 1 extractor, 1 generator, 1 review UI
   → Integration: Logging, progress tracking, file management
   → Polish: Unit tests, quickstart validation, error handling
4. Task rules applied:
   → Different files = [P] for parallel execution
   → Same file = sequential
   → Tests before implementation (TDD principle)
5. Total tasks: 41 numbered sequentially (T001-T041)
```

## Format: `[ID] [P?] Description`
- **[P]**: Can run in parallel (different files, no dependencies)
- Include exact file paths in descriptions

## Path Conventions
- **Single project structure**: `src/`, `tests/` at repository root
- **Output directory**: `/mnt/user-data/outputs/` (gitignored)
- Paths follow structure from plan.md

---

## Phase 3.1: Setup (3 tasks)

- [x] **T001** Create project directory structure per plan.md
  - Create `src/models/`, `src/extractors/`, `src/analyzers/`, `src/generators/`, `src/ui/`, `src/utils/`
  - Create `tests/contract/`, `tests/integration/`, `tests/unit/`, `tests/fixtures/`
  - Create `outputs/` with permissions 0700 (local alternative to /mnt/user-data/outputs/)
  - Add `.gitignore` to exclude `/mnt/user-data/outputs/` and `outputs/`

- [x] **T002** Initialize Python project with dependencies from research.md
  - Create `requirements.txt` with:
    - sentence-transformers>=2.0.0
    - scikit-learn==1.7.1
    - beautifulsoup4>=4.12.0
    - lxml>=4.9.0
    - tqdm>=4.66.0
    - pydantic>=2.0.0
    - numpy>=1.24.0
    - pytest>=7.4.0
    - pytest-cov>=4.1.0
  - Create `pyproject.toml` for Python 3.10+ compatibility
  - Run `pip install -r requirements.txt` in venv

- [x] **T003** [P] Configure linting and logging infrastructure
  - Create `.flake8`, `.pylintrc`, or `pyproject.toml` with ruff config
  - Create `src/utils/logger.py` with debug-level logging (per Clarification Q2)
  - Create `src/utils/progress.py` for progress callbacks (Constitution Principle VII)

---

## Phase 3.2: Tests First (TDD) ⚠️ MUST COMPLETE BEFORE 3.3 (8 tasks)

**CRITICAL: These tests MUST be written and MUST FAIL before ANY implementation**

### Contract Tests (3 parallel)

- [ ] **T004** [P] Contract test for EmailExtractor in `tests/contract/test_extractor_contract.py`
  - Test `extract_all()` method signature and return type
  - Test `resume_from_checkpoint()` method
  - 5 test cases from contracts/extractor_contract.md:
    - test_extract_all_success
    - test_extract_handles_rate_limit
    - test_resume_from_checkpoint
    - test_continue_on_malformed_email
    - test_progress_callback_invoked
  - **MUST FAIL**: No implementation exists yet

- [ ] **T005** [P] Contract test for Analyzers in `tests/contract/test_analyzer_contract.py`
  - Test base Analyzer protocol
  - Test each analyzer: SenderAnalyzer, SubjectAnalyzer, SemanticAnalyzer, TemporalAnalyzer, VolumeAnalyzer
  - Test run_full_analysis() orchestrator
  - 10+ test cases from contracts/analyzer_contract.md
  - **MUST FAIL**: No implementation exists yet

- [ ] **T006** [P] Contract test for CategoryGenerator in `tests/contract/test_generator_contract.py`
  - Test `generate_suggestions()` method
  - Test `apply_templates()` method
  - Test `score_confidence()` method
  - 6 test cases from contracts/generator_contract.md:
    - test_generate_from_large_cluster
    - test_skip_small_cluster
    - test_apply_financial_template
    - test_confidence_scoring
    - test_merge_similar_categories
    - test_sort_by_confidence
  - **MUST FAIL**: No implementation exists yet

### Integration Tests (5 parallel)

- [ ] **T007** [P] Integration test for extraction flow in `tests/integration/test_extraction_flow.py`
  - Test full extraction from M365 → corpus.json
  - Mock M365 MCP server responses
  - Validate corpus file structure and permissions (0600)
  - Based on quickstart.md Scenario 1

- [ ] **T008** [P] Integration test for analysis flow in `tests/integration/test_analysis_flow.py`
  - Test corpus.json → analysis_results.json
  - Validate all 5 analysis components present
  - Test progress indicators invoked
  - Based on quickstart.md Scenario 2

- [ ] **T009** [P] Integration test for suggestion flow in `tests/integration/test_suggestion_flow.py`
  - Test analysis_results.json → category_suggestions.json
  - Validate category suggestions sorted by confidence
  - Validate template-based categories included
  - Based on quickstart.md Scenario 3

- [ ] **T010** [P] Integration test for review flow in `tests/integration/test_review_flow.py`
  - Test interactive category review CLI
  - Mock user inputs (accept, rename, merge, delete, skip)
  - Validate approved_categories.json output
  - Based on quickstart.md Scenario 4

- [ ] **T011** [P] Integration test for end-to-end pipeline in `tests/integration/test_pipeline.py`
  - Test extract → analyze → suggest → review → cleanup
  - Based on quickstart.md End-to-End Validation
  - Measure execution time for performance validation

---

## Phase 3.3: Core Implementation - Pydantic Models (7 parallel tasks)

**NOTE**: Models implemented first to support test development (TDD adaptation for type safety)

- [x] **T012** [P] Email model in `src/models/email.py`
  - Implement Pydantic model from data-model.md lines 75-91
  - Attributes: id, sender_email, sender_name, sender_domain, recipient_email, recipient_name, subject, body_text, received_date, has_attachments
  - Property: `combined_text` for embeddings
  - Validation: EmailStr for emails, min_length for id/domain

- [x] **T013** [P] Corpus model in `src/models/corpus.py`
  - Implement CorpusMetadata and Corpus from data-model.md lines 132-150
  - Attributes: extraction_metadata, emails list
  - Property: `date_range` tuple
  - Validation: total_emails >= 0

- [x] **T014** [P] Sender model in `src/models/sender.py`
  - Implement SenderType enum and Sender model from data-model.md lines 174-205
  - Enum: PERSONAL, SERVICE, MARKETING, WORK
  - Attributes: email, name, domain, type, frequency_count, sample_subjects, email_ids
  - Validation: frequency_count >= 1, max 5 sample_subjects

- [x] **T015** [P] AnalysisResults models in `src/models/analysis_results.py`
  - Implement all 5 sub-models from data-model.md lines 217-253:
    - SenderAnalysis
    - SubjectPatterns
    - TemporalPatterns
    - VolumeStats
    - AnalysisResults (container)
  - Include all nested structures (top_senders, common_prefixes, etc.)

- [x] **T016** [P] ContentCluster model in `src/models/content_cluster.py`
  - Implement RepresentativeSample and ContentCluster from data-model.md lines 280-292
  - Attributes: cluster_id, size, percentage, representative_samples, common_domains, email_ids
  - Validation: cluster_id >= 0, size >= 1, percentage 0-100

- [x] **T017** [P] Category model in `src/models/category.py`
  - Implement CategorySource enum and Category model from data-model.md lines 320-355
  - Enum: CONTENT_CLUSTER, SENDER, TEMPLATE, CUSTOM
  - Attributes: category_id, category_name, description, confidence, email_count, percentage, source, source_id, user_modified, distinguishing_features, example_email_ids
  - Validation: confidence 0-1, max 10 example_email_ids

- [x] **T018** [P] CategoryTemplate model in `src/models/category_template.py`
  - Implement CategoryTemplate from data-model.md lines 389-411
  - Attributes: name, keywords, domains, description
  - Define PREDEFINED_TEMPLATES constant with 6 templates:
    1. Financial & Banking
    2. Shopping & E-commerce
    3. Social Media
    4. Newsletters & Marketing
    5. Travel & Transportation
    6. Account & Security

---

## Phase 3.4: Core Implementation - Extraction (4 tasks)

- [x] **T019** [P] HTML parser utility in `src/extractors/html_parser.py`
  - Implement `extract_plain_text(html_content)` from research.md lines 166-185
  - Use BeautifulSoup with lxml parser, fallback to html.parser
  - Remove `<script>` and `<style>` tags
  - Return clean plain text with whitespace stripped

- [x] **T020** [P] Checkpoint manager in `src/extractors/checkpoint_manager.py`
  - Implement checkpoint save/load/resume logic
  - Save every 100 emails (configurable)
  - JSON format: {emails_processed, last_processed_id, timestamp}
  - File path: `/mnt/user-data/outputs/extraction_checkpoint.json`

- [x] **T021** EmailExtractor implementation in `src/extractors/m365_extractor.py`
  - Implement `extract_all()` per contracts/extractor_contract.md
  - Connect to M365 MCP server tools
  - Pagination with max_batch_size=500
  - Exponential backoff retry (1s, 2s, 4s)
  - Call progress_callback after each batch
  - Use html_parser.py for body text conversion
  - Use checkpoint_manager.py for resumption
  - Return ExtractionResult with corpus + errors
  - **Make T004 tests PASS**

- [x] **T022** File manager utility in `src/utils/file_manager.py`
  - Implement JSON save/load with UTF-8 encoding
  - Set file permissions to 0600 (Constitution Principle IV)
  - Path: `/mnt/user-data/outputs/`
  - Functions: save_json(), load_json(), ensure_output_dir()

---

## Phase 3.5: Core Implementation - Analysis (6 tasks)

- [x] **T023** [P] SenderAnalyzer in `src/analyzers/sender_analyzer.py`
  - Implement `analyze()` method per contracts/analyzer_contract.md lines 45-66
  - Count emails per sender
  - Extract top 50 senders by frequency
  - Extract top 30 domains by frequency
  - Classify sender types (service, marketing, work, personal) per FR-012, FR-013
  - Return SenderAnalysis object

- [x] **T024** [P] SubjectAnalyzer in `src/analyzers/subject_analyzer.py`
  - Implement `analyze()` method per contracts/analyzer_contract.md lines 112-120
  - Extract common prefixes: RE:, FWD: (case-insensitive)
  - Extract numbered patterns: regex `(\w+)\s*[#№]\s*\d+`
  - Extract top 50 keywords (exclude stop words)
  - Extract bracket tags: regex `[\[\(]([^\]\)]+)[\]\)]`
  - Return SubjectPatterns object

- [x] **T025** [P] SemanticAnalyzer in `src/analyzers/semantic_analyzer.py`
  - Implement `analyze()` method per contracts/analyzer_contract.md lines 159-188
  - Use sentence-transformers model "mixedbread-ai/mxbai-embed-large-v1" from research.md
  - Combine subject + first 500 chars of body for embedding
  - Use scikit-learn KMeans (default 10 clusters) from research.md
  - Binary quantization for memory efficiency
  - Identify 5 representative samples per cluster (closest to centroid)
  - Show progress bar for operations >10 seconds
  - Return List[ContentCluster]

- [x] **T026** [P] TemporalAnalyzer in `src/analyzers/temporal_analyzer.py`
  - Implement `analyze()` method per contracts/analyzer_contract.md lines 232-253
  - Classify sender frequency:
    - one-time: 1 email
    - daily: avg interval < 2 days (>=10 emails)
    - weekly: avg interval < 8 days (>=10 emails)
    - monthly: avg interval < 35 days (>=10 emails)
    - occasional: default
  - Return TemporalPatterns object

- [x] **T027** [P] VolumeAnalyzer in `src/analyzers/volume_analyzer.py`
  - Implement `analyze()` method per contracts/analyzer_contract.md lines 289-298
  - Calculate: total_emails, unique_senders, date_range
  - Calculate: with_attachments count and percentage
  - Calculate: avg_body_length_chars
  - Calculate: emails_per_day (total / span_days)
  - Return VolumeStats object

- [x] **T028** Master analyzer orchestrator in `src/analyzers/__init__.py`
  - Implement `run_full_analysis()` per contracts/analyzer_contract.md lines 324-364
  - Run all 5 analyzers sequentially: sender → subject → semantic → temporal → volume
  - Pass progress_callback to each analyzer
  - Combine results into AnalysisResults object
  - **Make T005 tests PASS**

---

## Phase 3.6: Core Implementation - Category Generation (4 tasks)

- [x] **T029** [P] Template matcher in `src/generators/template_matcher.py`
  - Implement `match_templates(analysis_results, templates)` function
  - Match keywords in subject/body AND/OR domains
  - Return List[Category] with source=TEMPLATE
  - Use PREDEFINED_TEMPLATES from category_template.py

- [x] **T030** [P] Confidence scorer in `src/generators/confidence_scorer.py`
  - Implement `calculate_confidence(category, total_emails)` per contracts/generator_contract.md
  - Formula: confidence = avg(volume_score, source_score, percentage_score)
  - Return float 0.0-1.0

- [x] **T031** CategoryGenerator implementation in `src/generators/category_generator.py`
  - Implement `generate_suggestions()` per contracts/generator_contract.md lines 13-30
  - Generate from ContentClusters where percentage > min_cluster_percentage (default 5%)
  - Generate from Senders where frequency_count > min_sender_count (default 20)
  - Apply templates using template_matcher.py
  - Merge similar categories (Levenshtein distance < 3, >70% overlap)
  - Calculate confidence using confidence_scorer.py
  - Sort by confidence descending
  - Return List[Category]
  - **Make T006 tests PASS**

- [x] **T032** Generate human-readable report in `src/generators/category_generator.py`
  - Add method `generate_report(categories)` → markdown string
  - Format per quickstart.md lines 157-158 (category_suggestions_report.md)
  - Include: category name, description, confidence %, email count, percentage

---

## Phase 3.7: Core Implementation - Interactive UI (2 tasks)

- [x] **T033** Category review CLI in `src/ui/category_review.py`
  - Implement interactive review per contracts/ and quickstart.md Scenario 4
  - Display each category with: name, description, confidence, email_count, sample emails
  - Options: [A]ccept, [R]ename, [M]erge, [D]elete, [S]kip
  - Handle skip: re-present at end (Clarification Q5)
  - Collect approved categories
  - Return approved categories list

- [x] **T034** Cleanup utility in `src/ui/category_review.py`
  - Add optional cleanup after approval (Clarification Q1)
  - Prompt: "Clean up intermediate files? (y/n)"
  - List files to delete: corpus.json, analysis_results.json, category_suggestions.json, report.md
  - Keep: approved_categories.json, extraction_errors.log
  - User can decline (keep all)

---

## Phase 3.8: Core Implementation - CLI Entry Point (2 tasks)

- [x] **T035** CLI command dispatcher in `src/main.py`
  - Commands: `extract`, `analyze`, `suggest`, `review`, `pipeline`
  - Use argparse or click for CLI parsing
  - Wire commands to: m365_extractor, run_full_analysis, category_generator, category_review
  - Add `--help` for each command

- [x] **T036** Pipeline orchestrator in `src/main.py`
  - Implement `pipeline` command
  - Run: extract → analyze → suggest → review → optional cleanup
  - Show progress for each step
  - Handle errors gracefully (Constitution Principle VI)
  - Per quickstart.md lines 293-297

---

## Phase 3.9: Integration - Utilities (3 tasks)

- [x] **T037** [P] Validators utility in `src/utils/validators.py`
  - Implement cross-entity validators from data-model.md lines 416-425:
    - validate_corpus_total_matches_length
    - validate_unique_email_ids
    - validate_cluster_percentages_sum_100
    - validate_email_id_references

- [x] **T038** [P] Error logging in `src/utils/logger.py`
  - Expand logger.py to write extraction_errors.log
  - Debug level detail (Clarification Q2)
  - Format: timestamp, email_id, error_type, error_message
  - Save to `/mnt/user-data/outputs/extraction_errors.log`

- [x] **T039** Progress tracking in `src/utils/progress.py`
  - Implement progress_callback wrapper
  - Use tqdm for CLI progress bars
  - Format: `[##########---] 500/1523 (32.8%)`
  - Invoke for operations >10 seconds (Constitution Principle VII)

---

## Phase 3.10: Polish (2 tasks)

- [ ] **T040** [P] Unit tests in `tests/unit/`
  - Create `test_html_parser.py` for BeautifulSoup edge cases
  - Create `test_sender_classifier.py` for sender type classification
  - Create `test_confidence_scorer.py` for confidence calculation
  - Create `test_validators.py` for cross-entity validation
  - Aim for >80% code coverage

- [ ] **T041** Manual quickstart validation
  - Run all 5 scenarios from `specs/001-use-the-document/quickstart.md`
  - Verify success criteria for each scenario
  - Test with real M365 MCP connection (if available) or mocked
  - Measure performance for 1000 emails
  - Document any deviations in quickstart.md

---

## Dependencies

### Critical Path
1. **Setup (T001-T003)** blocks all other tasks
2. **Tests (T004-T011)** MUST complete before implementation (T012-T036)
3. **Models (T012-T018)** block analyzers, extractors, generators
4. **Extractors (T019-T022)** block integration tests (T007)
5. **Analyzers (T023-T028)** block generators (T029-T032)
6. **Generators (T029-T032)** block review UI (T033-T034)
7. **CLI (T035-T036)** requires all core components

### Specific Dependencies
- T021 (EmailExtractor) requires: T012 (Email), T013 (Corpus), T019 (HTML parser), T020 (Checkpoint)
- T028 (run_full_analysis) requires: T023-T027 (all analyzers)
- T031 (CategoryGenerator) requires: T016 (ContentCluster), T017 (Category), T029 (Template matcher), T030 (Confidence scorer)
- T035-T036 (CLI) requires: T021, T028, T031, T033

---

## Parallel Execution Examples

### Launch all contract tests together (T004-T006):
```bash
# Run in parallel using Task agent
Task: "Contract test for EmailExtractor in tests/contract/test_extractor_contract.py per contracts/extractor_contract.md"
Task: "Contract test for Analyzers in tests/contract/test_analyzer_contract.py per contracts/analyzer_contract.md"
Task: "Contract test for CategoryGenerator in tests/contract/test_generator_contract.py per contracts/generator_contract.md"
```

### Launch all integration tests together (T007-T011):
```bash
Task: "Integration test extraction flow in tests/integration/test_extraction_flow.py from quickstart Scenario 1"
Task: "Integration test analysis flow in tests/integration/test_analysis_flow.py from quickstart Scenario 2"
Task: "Integration test suggestion flow in tests/integration/test_suggestion_flow.py from quickstart Scenario 3"
Task: "Integration test review flow in tests/integration/test_review_flow.py from quickstart Scenario 4"
Task: "Integration test pipeline in tests/integration/test_pipeline.py from quickstart End-to-End"
```

### Launch all Pydantic models together (T012-T018):
```bash
Task: "Implement Email model in src/models/email.py from data-model.md lines 75-91"
Task: "Implement Corpus model in src/models/corpus.py from data-model.md lines 132-150"
Task: "Implement Sender model in src/models/sender.py from data-model.md lines 174-205"
Task: "Implement AnalysisResults in src/models/analysis_results.py from data-model.md lines 217-253"
Task: "Implement ContentCluster in src/models/content_cluster.py from data-model.md lines 280-292"
Task: "Implement Category in src/models/category.py from data-model.md lines 320-355"
Task: "Implement CategoryTemplate in src/models/category_template.py from data-model.md lines 389-411"
```

### Launch all analyzers together (T023-T027):
```bash
Task: "Implement SenderAnalyzer in src/analyzers/sender_analyzer.py per contracts/analyzer_contract.md lines 45-66"
Task: "Implement SubjectAnalyzer in src/analyzers/subject_analyzer.py per contracts/analyzer_contract.md lines 112-120"
Task: "Implement SemanticAnalyzer in src/analyzers/semantic_analyzer.py per contracts/analyzer_contract.md lines 159-188"
Task: "Implement TemporalAnalyzer in src/analyzers/temporal_analyzer.py per contracts/analyzer_contract.md lines 232-253"
Task: "Implement VolumeAnalyzer in src/analyzers/volume_analyzer.py per contracts/analyzer_contract.md lines 289-298"
```

---

## Validation Checklist

**GATE: Verify before marking tasks.md complete**

- [x] All contracts have corresponding tests (T004-T006 cover extractor, analyzers, generator)
- [x] All entities have model tasks (T012-T018 cover all 7 entities)
- [x] All tests come before implementation (Phase 3.2 before 3.3)
- [x] Parallel tasks truly independent (verified: different files, no shared state)
- [x] Each task specifies exact file path (all tasks include `in path/to/file.py`)
- [x] No task modifies same file as another [P] task (verified: all [P] tasks target different files)
- [x] Context7 research verified in research.md (sentence-transformers, scikit-learn, beautifulsoup4)
- [x] Constitutional compliance checked (TDD, modular, privacy, error resilience, progress transparency)

---

## Notes

- **[P] tasks**: Different files, no dependencies, can run concurrently
- **TDD discipline**: Verify tests FAIL before implementing (Phase 3.2 before 3.3)
- **Commit frequency**: Commit after each task for incremental progress
- **Constitution alignment**: All tasks respect 7 core principles (TDD, Documentation-First, Context7, Privacy, Modular, Error Resilient, Performance Transparent)
- **Avoid**: Vague tasks, same-file conflicts, skipping tests, external data transmission

---

**Total Tasks**: 41
**Estimated Parallel Groups**: 8 groups (T004-T006, T007-T011, T012-T018, T019-T020+T022, T023-T027, T029-T030, T037-T039, T040)
**Critical Path Length**: ~12 sequential steps (Setup → Tests → Models → Extraction → Analysis → Generation → Review → CLI → Polish)
