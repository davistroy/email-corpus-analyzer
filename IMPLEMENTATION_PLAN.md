# Implementation Plan

**Generated:** 2026-02-28 15:30:00
**Based On:** RECOMMENDATIONS.md
**Total Phases:** 6
**Estimated Total Effort:** ~2,800 LOC across ~35 files

---

## Executive Summary

This plan transforms the email-corpus-analyzer from a static rule-based classifier into a learning system that evolves through phases. The implementation follows a strict dependency order: classification abstraction first (Phase 1), then LLM integration (Phase 2), SQLite migration in two stages (Phases 3-4), email-level feedback loop (Phase 5), and finally ensemble model progression (Phase 6).

Phases 1-2 deliver immediate value — LLM classification with zero training data — using the existing JSON storage. Phases 3-4 migrate to SQLite + sqlite-vec to enable the relational queries and vector similarity search required by the feedback system. Phase 5 closes the loop: every user correction makes the classifier smarter. Phase 6 is future work (month 2-3) that adds fine-tuned local models for near-zero cost operation.

All phases preserve the existing 3,463 tests at 88% coverage. Each phase leaves the codebase in a working state — the existing rule-based pipeline continues to function throughout the migration.

---

## Plan Overview

The implementation strategy is to add capabilities alongside existing code, not replace it. The rule engine remains the first-pass classifier throughout. LLM classification is a fallback for uncategorized emails. SQLite runs in parallel with JSON during migration, with a one-time import tool. The learning system is purely additive.

### Phase Summary Table

| Phase | Focus Area | Key Deliverables | Est. Complexity | Dependencies |
|-------|------------|------------------|-----------------|--------------|
| 1 | Classification Foundation | BaseClassifier ABC, ClassifierConfig, hybrid EmailCategorizer | M (~6 files, ~300 LOC) | None |
| 2 | LLM Classifier + Security | LLMClassifier with Instructor, prompt injection sanitizer | M (~7 files, ~450 LOC) | Phase 1 |
| 3 | SQLite Core | Database schema, EmailStore, JSON migration tool | L (~8 files, ~600 LOC) | None (parallel with 1-2) |
| 4 | SQLite Completion | Log migration, sqlite-vec embeddings, service layer updates | M (~7 files, ~450 LOC) | Phase 3 |
| 5 | Email-level Feedback Loop | FeedbackStore, FewShotRetriever, uncertainty sampling | M (~6 files, ~500 LOC) | Phases 2, 4 |
| 6 | Ensemble Model Progression | SetFit classifier, EnsembleClassifier, training pipeline | L (~7 files, ~500 LOC) | Phase 5 |

<!-- BEGIN PHASES -->

---

## Phase 1: Classification Foundation

**Estimated Complexity:** M (~6 files, ~300 LOC)
**Dependencies:** None
**Parallelizable:** Yes — can run concurrently with Phase 3

### Goals
- Establish the classifier abstraction layer (BaseClassifier ABC)
- Add configuration infrastructure for classifiers
- Refactor EmailCategorizer to support fallback classification
- Add classification-related exceptions

### Work Items

#### 1.1 Create BaseClassifier ABC and ClassificationResult Model ✅ Completed 2026-02-28
**Status: COMPLETE [2026-02-28]**
**Recommendation Ref:** A1
**Files Affected:**
- `src/classifiers/__init__.py` (create)
- `src/classifiers/base.py` (create)

**Description:**
Define the classifier contract that all classifiers must implement. `BaseClassifier` is an ABC with a `classify(email, categories) -> ClassificationResult` method. `ClassificationResult` is a Pydantic model containing `category_name`, `confidence`, `source` (classifier identifier), and `reasoning` (optional explanation). Also define `ClassifierCapability` enum (ZERO_SHOT, FEW_SHOT, FINE_TUNED) for capability discovery.

**Tasks:**
1. [x] Create `src/classifiers/__init__.py` with public exports
2. [x] Create `src/classifiers/base.py` with `BaseClassifier` ABC, `ClassificationResult` Pydantic model, and `ClassifierCapability` enum
3. [x] `classify()` signature: `def classify(self, email: Email, categories: list[str], context: ClassificationContext | None = None) -> ClassificationResult`
4. [x] `ClassificationContext` dataclass: holds few-shot examples, category descriptions, and any additional context for the classifier
5. [x] Add `batch_classify()` default implementation that iterates over `classify()` with progress tracking
6. [x] Write tests for the ABC contract (test that subclasses must implement classify, test ClassificationResult validation)

**Acceptance Criteria:**
- [x] `BaseClassifier` cannot be instantiated directly
- [x] `ClassificationResult` validates confidence is 0.0-1.0
- [x] `ClassificationContext` supports optional few-shot examples
- [x] All new code has tests

---

#### 1.2 Add ClassifierConfig and Category Taxonomy to Config Models ✅ Completed 2026-02-28
**Status: COMPLETE [2026-02-28]**
**Recommendation Ref:** A1
**Files Affected:**
- `src/config/models.py` (modify)
- `src/config/template.yaml` (modify)

**Description:**
Add `ClassifierConfig` to the config model hierarchy. This includes: `provider` (ollama | claude | openai), `model_name` (e.g., "qwen2.5:7b"), `ollama_base_url` (default localhost:11434), `api_key_env_var` (environment variable name for cloud API keys), `confidence_threshold` (minimum confidence to accept LLM result, default 0.6), `max_tokens` (default 200), `temperature` (default 0.0 for deterministic classification), and `categories` (list of category definitions with name + description). Add `classifier` field to `AppConfig`.

**Tasks:**
1. [x] Define `CategoryDefinition` model: `name: str`, `description: str`, `keywords: list[str]` (optional hints)
2. [x] Define `ClassifierConfig` model with all fields and validation (validate provider is one of allowed values, validate URL format for ollama_base_url)
3. [x] Add `classifier: ClassifierConfig = Field(default_factory=ClassifierConfig)` to `AppConfig`
4. [x] Add classifier section to `merge_configs()` nested config handling
5. [x] Update `template.yaml` with classifier section and commented examples
6. [x] Write tests for ClassifierConfig validation (bad provider, bad URL, missing required fields)

**Acceptance Criteria:**
- [x] `ClassifierConfig` has sensible defaults (provider=ollama, model=qwen2.5:7b)
- [x] Category taxonomy is configurable via YAML
- [x] Config merge correctly handles classifier overrides
- [x] Template YAML includes documented classifier section

---

#### 1.3 Refactor EmailCategorizer for Hybrid Classification ✅ Completed 2026-02-28
**Status: COMPLETE [2026-02-28]**
**Recommendation Ref:** A1
**Files Affected:**
- `src/categorizer/categorizer.py` (modify)
- `tests/unit/test_email_categorizer.py` (modify)

**Description:**
Modify `EmailCategorizer` to accept an optional `BaseClassifier` instance. When rules return no match (the `if not matched_rules` branch at line 91), invoke the classifier as fallback. When rules match but with low confidence (below a configurable threshold), optionally invoke the classifier for comparison. Track whether the final classification came from rules or the classifier in `CategoryAssignment.source`.

**Tasks:**
1. [x] Add `classifier: BaseClassifier | None = None` parameter to `EmailCategorizer.__init__()`
2. [x] Add `classifier_threshold: float = 0.6` parameter for minimum classifier confidence
3. [x] In `categorize_email()`, after the `if not matched_rules` check: if classifier is available, call `classifier.classify()` and convert result to `EmailCategorization`
4. [x] Add source tracking: `source="rule:<rule_id>"` for rule matches, `source="classifier:<name>"` for classifier matches
5. [x] Update `categorize_corpus()` to pass classifier context through
6. [x] Update existing tests; add tests for: no rules + classifier fallback, rules match + classifier skipped, no rules + no classifier = uncategorized

**Acceptance Criteria:**
- [x] Existing behavior unchanged when no classifier is provided (all 3,584 tests pass)
- [x] Classifier is only invoked when rules return no match
- [x] Source field correctly identifies rule vs classifier origin
- [x] New tests cover all three code paths

---

#### 1.4 Add Classification Exceptions ✅ Completed 2026-02-28
**Status: COMPLETE [2026-02-28]**
**Recommendation Ref:** A1
**Files Affected:**
- `src/exceptions.py` (modify)

**Description:**
Add `ClassificationError` (base), `ClassifierConnectionError` (Ollama/API unreachable), and `ClassifierResponseError` (invalid/unparseable response) to the exception hierarchy. Follow the existing pattern with `recovery_hint` and `context` fields.

**Tasks:**
1. [x] Add `ClassificationError(EmailAnalyzerError)` base class with default recovery hint
2. [x] Add `ClassifierConnectionError(ClassificationError)` with provider/URL context
3. [x] Add `ClassifierResponseError(ClassificationError)` with raw response context
4. [x] Write tests for exception instantiation and string representation

**Acceptance Criteria:**
- [x] All three exceptions follow the existing pattern (message, recovery_hint, context)
- [x] Recovery hints are actionable (e.g., "Check that Ollama is running at localhost:11434")
- [x] Tests verify inheritance chain

**Notes:**
This is a small addition (~40 LOC) but is listed separately because exceptions should be defined before they're used in Phase 2.

---

### Phase 1 Testing Requirements

- [ ] All existing 3,463 tests pass without modification (except test_email_categorizer which gets new tests)
- [ ] New tests for BaseClassifier ABC contract
- [ ] New tests for ClassifierConfig validation
- [ ] New tests for hybrid EmailCategorizer (3 code paths)
- [ ] New tests for classification exceptions
- [ ] All new code has >80% test coverage

### Phase 1 Completion Checklist

- [ ] All work items complete
- [ ] All tests passing (existing + new)
- [ ] `ruff check src/` passes
- [ ] No regressions in existing pipeline
- [ ] Config template updated

---

## Phase 2: LLM Classifier + Prompt Injection Security

**Estimated Complexity:** M (~7 files, ~450 LOC)
**Dependencies:** Phase 1
**Parallelizable:** No — requires Phase 1 abstractions

### Goals
- Implement LLM classification using Instructor library
- Add prompt injection mitigation for email content
- Support Ollama (local) and cloud API providers
- Add `classify` CLI command

### Work Items

#### 2.1 Implement EmailSanitizer for Prompt Injection Defense ✅ Completed 2026-02-28
**Status: COMPLETE [2026-02-28]**
**Recommendation Ref:** S1
**Files Affected:**
- `src/classifiers/sanitizer.py` (create)
- `tests/unit/test_sanitizer.py` (create)

**Description:**
Create `EmailSanitizer` that strips common injection patterns from email text before LLM input. Patterns to strip: `SYSTEM:`, `ASSISTANT:`, `USER:`, `[INST]`, `<<SYS>>`, `</s>`, and markdown code fence delimiters that could confuse the model. Wrap sanitized content in XML delimiters (`<email_content>...</email_content>`) to clearly separate email text from system instructions. Log when sanitization patterns fire.

**Tasks:**
1. [x] Create `src/classifiers/sanitizer.py` with `EmailSanitizer` class
2. [x] Define `INJECTION_PATTERNS` as compiled regex list (case-insensitive)
3. [x] Implement `sanitize(text: str) -> SanitizedText` where `SanitizedText` tracks original length, sanitized length, and patterns matched
4. [x] Implement `wrap_for_prompt(subject: str, body: str) -> str` that sanitizes and wraps in XML delimiters
5. [x] Write comprehensive tests: known injection patterns, edge cases (legitimate use of "system:" in email), empty input, very long input

**Acceptance Criteria:**
- [x] All known injection patterns are stripped
- [x] Legitimate email content is preserved (e.g., "Our system: is down" keeps the content)
- [x] Sanitization is logged for monitoring
- [x] XML delimiters clearly separate content from instructions

---

#### 2.2 Implement LLMClassifier with Instructor ✅ Completed 2026-02-28
**Status: COMPLETE [2026-02-28]**
**Recommendation Ref:** N1
**Files Affected:**
- `src/classifiers/llm_classifier.py` (create)
- `tests/unit/test_llm_classifier.py` (create)

**Description:**
Implement `LLMClassifier(BaseClassifier)` that uses Instructor for structured LLM output. The classifier constructs a prompt with: system instruction (you are an email classifier), category definitions from config, optional few-shot examples from `ClassificationContext`, and the sanitized email content. Output is a Pydantic model with `category: Literal[...categories]`, `confidence: float`, and `reasoning: str`. Supports Ollama (via OpenAI-compatible endpoint), Claude (via Anthropic SDK), and OpenAI (via OpenAI SDK) through Instructor's unified patching.

**Tasks:**
1. [x] Create `src/classifiers/llm_classifier.py` with `LLMClassifier` class
2. [x] Implement `_build_client()` factory that creates the appropriate Instructor client based on `ClassifierConfig.provider`
3. [x] Implement `_build_prompt()` that constructs the classification prompt with system instructions, category definitions, and optional few-shot examples
4. [x] Implement `classify()` using `client.chat.completions.create()` with the Pydantic response model
5. [x] Handle connection errors (Ollama not running, API key invalid) with `ClassifierConnectionError`
6. [x] Handle response parsing errors with `ClassifierResponseError` and retry logic (Instructor has built-in retries)
7. [x] Implement `batch_classify()` with tqdm progress bar
8. [x] Write tests with mocked Instructor client (test prompt construction, test response parsing, test error handling, test retry behavior)

**Acceptance Criteria:**
- [x] Classification works with Ollama backend (mocked in tests)
- [x] Classification works with cloud API backend (mocked in tests)
- [x] Invalid API keys produce actionable error messages
- [x] Ollama connection failures produce actionable error messages
- [x] Confidence scores are returned in 0.0-1.0 range
- [x] Category output is constrained to configured categories

---

#### 2.3 Add classify CLI Command ✅ Completed 2026-02-28
**Status: COMPLETE [2026-02-28]**
**Recommendation Ref:** U1
**Files Affected:**
- `src/cli/commands/classify.py` (create)
- `src/cli/__init__.py` (modify)
- `tests/unit/test_classify_cli.py` (create)

**Description:**
Add a `classify` subcommand to the CLI that runs LLM classification directly on a corpus. Supports `--provider`, `--model`, `--categories` (path to YAML), `--confidence-threshold`, and `--output` flags. Uses the existing `CategorizationReport` model for output. Works with or without prior analysis — only requires an extracted corpus.

**Tasks:**
1. [x] Create `src/cli/commands/classify.py` with argument parser and command handler
2. [x] Add `classify` subparser to `src/cli/__init__.py`
3. [x] Register command in `src/cli/__init__.py`
4. [x] Implement command: load corpus → create LLMClassifier from config → classify corpus → save report
5. [x] Support `--json` output flag (reuse existing formatters)
6. [x] Support `--dry-run` for preview without actual classification
7. [x] Write tests for CLI argument parsing and command execution (with mocked classifier)

**Acceptance Criteria:**
- [x] `python -m src.cli classify --help` shows all options
- [x] Command loads corpus and classifies all emails
- [x] Output format matches existing `categorize` command
- [x] `--dry-run` shows what would be classified without calling LLM
- [x] Error messages are actionable when Ollama isn't running

---

#### 2.4 Add Dependencies to pyproject.toml ✅ Completed 2026-02-28
**Status: COMPLETE [2026-02-28]**
**Recommendation Ref:** N1
**Files Affected:**
- `pyproject.toml` (modify)
- `requirements.txt` (modify)

**Description:**
Add `instructor>=1.0.0` and `openai>=1.0.0` (Instructor's transport layer) to core dependencies. These are required for LLM classification. The `anthropic` SDK is optional (only needed for Claude provider).

**Tasks:**
1. [x] Add `instructor>=1.0.0` to `[project.dependencies]`
2. [x] Add `openai>=1.0.0` to `[project.dependencies]`
3. [x] Add `anthropic>=0.30.0` to `[project.optional-dependencies]` as `cloud` extra
4. [x] Update `requirements.txt` to match
5. [x] Verify `pip install -e .` succeeds with new dependencies

**Acceptance Criteria:**
- [x] `pip install -e .` installs instructor and openai
- [x] `pip install -e ".[cloud]"` additionally installs anthropic
- [x] No dependency conflicts with existing packages

---

### Phase 2 Testing Requirements

- [ ] All existing tests pass
- [ ] Sanitizer tests cover all injection patterns
- [ ] LLM classifier tests mock all three providers
- [ ] CLI command tests verify argument parsing and execution
- [ ] Integration test: rules + LLM fallback end-to-end (mocked LLM)

### Phase 2 Completion Checklist

- [ ] All work items complete
- [ ] All tests passing
- [ ] `ruff check src/` passes
- [ ] `python -m src.cli classify --help` works
- [ ] LLM classification works with Ollama (manual verification)

---

## Phase 3: SQLite Core Schema and Email Storage

**Estimated Complexity:** L (~8 files, ~600 LOC)
**Dependencies:** None (can run in parallel with Phases 1-2)
**Parallelizable:** Yes — independent of classifier work

### Goals
- Create SQLite database module with connection management
- Define schema for emails, classifications, corrections, sync_state
- Implement EmailStore with full CRUD operations
- Build JSON → SQLite migration tool

### Work Items

#### 3.1 Create Database Module with Schema and Connection Management ✅ Completed 2026-02-28
**Status: COMPLETE [2026-02-28]**
**Recommendation Ref:** A2, N2
**Files Affected:**
- `src/storage/__init__.py` (create)
- `src/storage/database.py` (create)
- `tests/unit/test_database.py` (create)

**Description:**
Create the SQLite database module with connection pooling (WAL mode for concurrent access), schema creation, and migration versioning. Define all tables: `emails` (id, sender_email, sender_name, sender_domain, recipient_email, recipient_name, subject, body_text, received_date, has_attachments, thread_id, in_reply_to, references_json, provider, provider_message_id), `classifications` (email_id, category_name, confidence, source, model_version, classified_at), `corrections` (email_id, old_category, new_category, corrected_at, weight), `sync_state` (provider, sync_token, last_sync_at), `decision_log` (timestamp, category_name, action, context_json), `action_log` (timestamp, action_type, target_id, details_json, success, reversible). Use a `schema_version` table for future migrations.

**Tasks:**
1. [x] Create `src/storage/__init__.py` with public exports
2. [x] Create `src/storage/database.py` with `Database` class
3. [x] Implement `Database.__init__(db_path)` with connection creation and WAL mode
4. [x] Implement `_create_schema()` with all CREATE TABLE statements and indexes
5. [x] Implement `_get_schema_version()` and `_set_schema_version()` for migration tracking
6. [x] Add `get_connection()` context manager for transaction management
7. [x] Write tests: schema creation, WAL mode verification, connection reuse, concurrent access

**Acceptance Criteria:**
- [x] Database file is created at `~/.email-analyzer/email_analyzer.db`
- [x] WAL mode is enabled for concurrent read/write
- [x] All tables are created with correct column types and constraints
- [x] Appropriate indexes exist (email_id on classifications, corrected_at on corrections)
- [x] Schema version is tracked for future migrations

---

#### 3.2 Implement EmailStore with CRUD Operations ✅ Completed 2026-02-28
**Status: COMPLETE [2026-02-28]**
**Recommendation Ref:** A2, N2
**Files Affected:**
- `src/storage/email_store.py` (create)
- `src/models/email.py` (modify)
- `tests/unit/test_email_store.py` (create)

**Description:**
Implement `EmailStore` that provides CRUD operations for emails using Pydantic models. Add `to_row()` and `from_row()` methods to the `Email` model for SQLite serialization. Implement upsert semantics (insert or update based on provider_message_id) for idempotent extraction. Support batch operations for efficient corpus import.

**Tasks:**
1. [x] Add `to_row() -> dict` method to `Email` model (serializes references list to JSON string)
2. [x] Add `from_row(row: dict) -> Email` classmethod to `Email` model (deserializes JSON references)
3. [x] Create `src/storage/email_store.py` with `EmailStore(database: Database)` class
4. [x] Implement `upsert(email: Email)` and `upsert_batch(emails: list[Email])` with INSERT OR REPLACE
5. [x] Implement `get(email_id: str) -> Email | None`
6. [x] Implement `get_all() -> list[Email]` with pagination support
7. [x] Implement `count() -> int`
8. [x] Implement `delete(email_id: str)` and `delete_batch(email_ids: list[str])`
9. [x] Write tests for all CRUD operations including edge cases (duplicate IDs, missing fields, batch operations)

**Acceptance Criteria:**
- [x] `Email.to_row()` produces a dict that round-trips through `Email.from_row()`
- [x] Upsert correctly handles both insert and update cases
- [x] Batch operations are wrapped in a single transaction for performance
- [x] All existing Email tests still pass after adding to_row/from_row

---

#### 3.3 Implement ClassificationStore and CorrectionStore
**Status: PENDING**
**Recommendation Ref:** N2, N3
**Files Affected:**
- `src/storage/classification_store.py` (create)
- `tests/unit/test_classification_store.py` (create)

**Description:**
Implement stores for classification results and user corrections. `ClassificationStore` tracks what the system predicted for each email (with model version for reproducibility). `CorrectionStore` tracks user reclassifications with timestamps for temporal decay weighting. Both support efficient querying: "all corrections in the last N days", "correction rate by category", "all classifications by model version".

**Tasks:**
1. [ ] Create `src/storage/classification_store.py` with `ClassificationStore` and `CorrectionStore` classes
2. [ ] `ClassificationStore.save(email_id, category, confidence, source, model_version)`
3. [ ] `ClassificationStore.get_latest(email_id) -> dict | None`
4. [ ] `ClassificationStore.get_by_model_version(version) -> list[dict]`
5. [ ] `CorrectionStore.add(email_id, old_category, new_category)`
6. [ ] `CorrectionStore.get_recent(days: int) -> list[dict]`
7. [ ] `CorrectionStore.get_correction_rate(category: str, days: int) -> float`
8. [ ] Write tests for all operations including temporal queries

**Acceptance Criteria:**
- [ ] Classification history is preserved (multiple predictions for same email)
- [ ] Corrections include timestamps for temporal decay
- [ ] Correction rate calculation is accurate
- [ ] Queries by time range work correctly across timezone boundaries

---

#### 3.4 Build JSON → SQLite Migration Tool ✅ Completed 2026-02-28
**Status: COMPLETE [2026-02-28]**
**Recommendation Ref:** N2
**Files Affected:**
- `src/storage/migration.py` (create)
- `src/cli/commands/migrate.py` (create)
- `src/cli/__init__.py` (modify)
- `src/storage/__init__.py` (modify)
- `tests/unit/test_migration.py` (create)

**Description:**
Build a one-time migration tool that imports existing JSON data into SQLite. Imports: email_corpus.json → emails table, decisions.jsonl → decision_log table, action_log.jsonl → action_log table. The migration is non-destructive — JSON files are read but not deleted. Add `python -m src.cli migrate` CLI command with progress reporting.

**Tasks:**
1. [x] Create `src/storage/migration.py` with `JsonToSqliteMigrator` class
2. [x] Implement `migrate_corpus(corpus_path: Path)` — parse JSON, upsert into emails table
3. [x] Implement `migrate_decisions(decisions_path: Path)` — parse JSONL, insert into decision_log
4. [x] Implement `migrate_actions(actions_path: Path)` — parse JSONL, insert into action_log
5. [x] Implement `migrate_all(output_dir: Path)` — orchestrate all migrations with progress
6. [x] Create `src/cli/commands/migrate.py` CLI command
7. [x] Write tests with sample JSON/JSONL fixtures

**Acceptance Criteria:**
- [x] `python -m src.cli migrate` imports all existing data
- [x] Migration is idempotent (running twice doesn't duplicate data)
- [x] JSON files are NOT deleted after migration
- [x] Progress is reported during migration
- [x] Corrupt JSONL lines are skipped with warnings (matching existing behavior)

---

### Phase 3 Testing Requirements
**Status: COMPLETE [2026-02-28]**

- [x] All existing tests pass (3,934 total)
- [x] Database tests use temporary file paths (no side effects)
- [x] EmailStore round-trip tests verify data integrity
- [x] Migration tests use fixtures with known data
- [x] All new code has >80% test coverage (database 83%, email_store 95%, migration 83%)
- [x] Integration tests for complete storage layer — 36 tests in `tests/integration/test_storage.py`

### Phase 3 Completion Checklist

- [ ] All work items complete
- [ ] All tests passing
- [ ] `ruff check src/` passes
- [ ] `python -m src.cli migrate --help` works
- [ ] Manual test: migrate real corpus JSON to SQLite and verify counts

---

## Phase 4: SQLite Completion — Logs, Embeddings, Service Layer

**Estimated Complexity:** M (~7 files, ~450 LOC)
**Dependencies:** Phase 3
**Parallelizable:** Work items 4.1 and 4.2 can run concurrently

### Goals
- Migrate ActionLogger and DecisionLogger to SQLite backend
- Replace .npz embedding cache with sqlite-vec
- Update service layer to use new storage

### Work Items

#### 4.1 Migrate ActionLogger and DecisionLogger to SQLite
**Status: COMPLETE [2026-02-28]**
**Recommendation Ref:** N2
**Files Affected:**
- `src/actions/action_logger.py` (modify)
- `src/learning/decision_logger.py` (modify)
- `tests/unit/test_action_logger.py` (modify)
- `tests/unit/test_learning.py` (modify)

**Description:**
Refactor `ActionLogger` and `DecisionLogger` to write to SQLite tables instead of JSONL files. Both classes keep their existing public API — the change is internal storage only. The `ActionLogger` uses the `action_log` table; `DecisionLogger` uses the `decision_log` table. Both accept an optional `Database` instance; if not provided, they fall back to JSONL (backward compatibility during transition).

**Tasks:**
1. [x] Add `database: Database | None = None` parameter to `ActionLogger.__init__()`
2. [x] When database is provided, write to `action_log` table instead of JSONL
3. [x] Update `get_actions()` to query SQLite when database is available
4. [x] Apply same pattern to `DecisionLogger`: database parameter, SQLite writes, query from table
5. [x] Keep JSONL fallback when database is None (backward compat)
6. [x] Update tests to verify both SQLite and JSONL code paths

**Acceptance Criteria:**
- [x] Existing JSONL behavior unchanged when no database provided
- [x] SQLite writes are atomic (single transaction per log entry)
- [x] All existing logger tests pass without modification
- [x] New tests verify SQLite storage and retrieval

---

#### 4.2 Replace Embedding Cache with sqlite-vec ✅ Completed 2026-02-28
**Status: COMPLETE [2026-02-28]**
**Recommendation Ref:** N2
**Files Affected:**
- `src/storage/embedding_store.py` (create)
- `src/cache/embedding_cache.py` (modify)
- `tests/unit/test_embedding_store.py` (create)
- `tests/unit/test_embedding_cache.py` (modify)

**Description:**
Create `EmbeddingStore` that uses sqlite-vec for vector storage and cosine similarity search. The store provides: `add(email_id, embedding)`, `get(email_id)`, `search_similar(embedding, k=5)`, and `delete(email_id)`. Modify `EmbeddingCache` to delegate to `EmbeddingStore` when a database is provided, falling back to .npz for backward compatibility.

**Tasks:**
1. [x] Create `src/storage/embedding_store.py` with `EmbeddingStore(database: Database)` class
2. [x] Create sqlite-vec virtual table: `CREATE VIRTUAL TABLE embeddings USING vec0(email_id TEXT PRIMARY KEY, embedding FLOAT[1024])`
3. [x] Implement `add(email_id: str, embedding: np.ndarray)` and `add_batch()`
4. [x] Implement `get(email_id: str) -> np.ndarray | None`
5. [x] Implement `search_similar(query_embedding: np.ndarray, k: int = 5) -> list[tuple[str, float]]` returning (email_id, cosine_similarity) pairs
6. [x] Implement `delete(email_id: str)` and `sync_with_ids(valid_ids: set[str])`
7. [x] Modify `EmbeddingCache.__init__()` to accept optional `database` parameter
8. [x] When database is provided, delegate all operations to `EmbeddingStore`
9. [x] Write tests for vector storage, similarity search accuracy, and cache delegation

**Acceptance Criteria:**
- [x] Embeddings stored in sqlite-vec virtual table
- [x] `search_similar()` returns correct nearest neighbors by cosine similarity
- [x] `EmbeddingCache` works unchanged when no database provided (all existing tests pass)
- [x] Batch operations are efficient (single transaction)

**Notes:**
Add `sqlite-vec>=0.1.0` to `pyproject.toml` dependencies. sqlite-vec has zero C dependencies and installs via pip on all platforms.

---

#### 4.3 Update Service Layer for SQLite Storage
**Status: PENDING**
**Recommendation Ref:** N2
**Files Affected:**
- `src/services/pipeline_service.py` (modify)
- `src/services/extraction_service.py` (modify)
- `tests/unit/test_services.py` (modify)

**Description:**
Update the service layer to use SQLite storage when a database is available. `ExtractionService` saves extracted emails to both JSON (backward compat) and SQLite. `PipelineService` passes the database instance through to sub-services. `AnalysisService` uses the sqlite-vec-backed `EmbeddingCache` when available.

**Tasks:**
1. [ ] Add `database: Database | None = None` parameter to `PipelineService.__init__()`
2. [ ] Pass database to `ExtractionService` and `AnalysisService`
3. [ ] In `ExtractionService`: after saving corpus JSON, upsert emails into SQLite via `EmailStore`
4. [ ] In `AnalysisService.run()`: pass database to `EmbeddingCache` when available
5. [ ] Update tests to verify SQLite integration path (with mocked Database)

**Acceptance Criteria:**
- [ ] Pipeline works unchanged without database (all existing tests pass)
- [ ] When database is provided, emails are stored in SQLite
- [ ] Embeddings use sqlite-vec when database is available
- [ ] No duplicate code paths — JSON remains for backward compat, SQLite is additive

---

#### 4.4 Add sqlite-vec Dependency
**Status: COMPLETE [2026-02-28]**
**Recommendation Ref:** N2
**Files Affected:**
- `pyproject.toml` (modify)
- `requirements.txt` (modify)

**Tasks:**
1. [ ] Add `sqlite-vec>=0.1.0` to `[project.dependencies]`
2. [ ] Update `requirements.txt`
3. [ ] Verify installation on Windows (the primary dev platform)

**Acceptance Criteria:**
- [ ] `pip install -e .` includes sqlite-vec
- [ ] `import sqlite_vec` succeeds after installation
- [ ] No conflicts with existing dependencies

---

### Phase 4 Testing Requirements

- [ ] All existing tests pass (loggers and cache use JSONL/.npz fallback by default)
- [ ] New SQLite code paths tested with temporary databases
- [ ] Embedding similarity search tests verify nearest-neighbor accuracy
- [ ] Service layer tests verify both with and without database

### Phase 4 Completion Checklist

- [ ] All work items complete
- [ ] All tests passing
- [ ] `ruff check src/` passes
- [ ] Manual test: full pipeline with SQLite storage enabled
- [ ] Embedding search returns correct similar emails

---

## Phase 5: Email-level Feedback Loop

**Estimated Complexity:** M (~6 files, ~500 LOC)
**Dependencies:** Phases 2 and 4
**Parallelizable:** Work items 5.1 and 5.2 can run concurrently

### Goals
- Capture email-level corrections (reclassifications)
- Build dynamic few-shot retriever using sqlite-vec
- Implement uncertainty sampling for active labeling
- Wire feedback into LLM classifier

### Work Items

#### 5.1 Implement EmailFeedbackStore with Temporal Decay
**Status: PENDING**
**Recommendation Ref:** N3
**Files Affected:**
- `src/learning/feedback_store.py` (create)
- `tests/unit/test_feedback_store.py` (create)

**Description:**
Create `EmailFeedbackStore` that captures email-level corrections in the `corrections` table and computes temporal decay weights. When a user reclassifies an email from category A to category B, the store records the correction with a timestamp. The `get_weighted_corrections()` method applies exponential temporal decay: `weight = exp(-0.01 * days_old)` (~70-day half-life). Corrections can be queried by category, time range, or weighted importance.

**Tasks:**
1. [ ] Create `src/learning/feedback_store.py` with `EmailFeedbackStore(database: Database)` class
2. [ ] Implement `record_correction(email_id, old_category, new_category, embedding: np.ndarray | None)`
3. [ ] Implement `get_corrections(category: str | None, days: int | None) -> list[Correction]`
4. [ ] Implement `get_weighted_corrections(min_weight: float = 0.1) -> list[WeightedCorrection]` with temporal decay
5. [ ] Implement `get_correction_stats() -> dict` (total corrections, per-category counts, correction rate)
6. [ ] `Correction` and `WeightedCorrection` as Pydantic models
7. [ ] Write tests: record and retrieve, temporal decay calculation, category filtering, stats

**Acceptance Criteria:**
- [ ] Corrections are persisted in SQLite
- [ ] Temporal decay weight is correctly computed (`exp(-0.01 * days_old)`)
- [ ] 70-day-old correction has ~50% weight of a new correction
- [ ] Per-category correction rate is accurate
- [ ] Empty store returns empty results (not errors)

---

#### 5.2 Build FewShotRetriever with Maximal Marginal Relevance
**Status: PENDING**
**Recommendation Ref:** N3
**Files Affected:**
- `src/learning/few_shot_retriever.py` (create)
- `tests/unit/test_few_shot_retriever.py` (create)

**Description:**
Create `FewShotRetriever` that retrieves semantically similar labeled emails as few-shot examples for the LLM classifier. For each incoming email: embed it, query sqlite-vec for the k*2 nearest corrections, then apply Maximal Marginal Relevance (MMR) to select k=5-6 examples that balance semantic relevance with category diversity. MMR formula: `score = λ * sim(candidate, query) - (1-λ) * max(sim(candidate, already_selected))` with λ=0.7.

**Tasks:**
1. [ ] Create `src/learning/few_shot_retriever.py` with `FewShotRetriever(embedding_store, feedback_store)` class
2. [ ] Implement `retrieve(query_embedding: np.ndarray, k: int = 6) -> list[FewShotExample]`
3. [ ] Implement MMR selection: fetch 2*k nearest, iteratively select based on MMR score
4. [ ] `FewShotExample` dataclass: email_id, subject, body_snippet, category, similarity_score
5. [ ] Implement `format_for_prompt(examples: list[FewShotExample]) -> str` that formats examples for LLM context
6. [ ] Write tests: MMR produces diverse category spread, retrieval with no corrections returns empty, correct k returned

**Acceptance Criteria:**
- [ ] Retrieved examples span multiple categories (MMR diversity)
- [ ] Examples are formatted for clean injection into LLM prompt
- [ ] Works correctly with fewer corrections than k (returns what's available)
- [ ] Empty feedback store produces empty retrieval (classifier falls back to zero-shot)

---

#### 5.3 Implement Uncertainty Sampling
**Status: PENDING**
**Recommendation Ref:** N3
**Files Affected:**
- `src/learning/uncertainty_sampler.py` (create)
- `tests/unit/test_uncertainty_sampler.py` (create)

**Description:**
Create `UncertaintySampler` that identifies the lowest-confidence classifications from a batch for user review. Simple implementation: sort classifications by confidence ascending, return top N. Also flag emails where rule engine and LLM classifier disagree (disagreement sampling).

**Tasks:**
1. [ ] Create `src/learning/uncertainty_sampler.py` with `UncertaintySampler` class
2. [ ] Implement `get_uncertain(categorizations: list[EmailCategorization], n: int = 10) -> list[EmailCategorization]`
3. [ ] Implement `get_disagreements(rule_results, llm_results) -> list[tuple[EmailCategorization, EmailCategorization]]`
4. [ ] Sort by confidence ascending for uncertainty, by confidence gap for disagreements
5. [ ] Write tests: correct sorting, empty input, n > total

**Acceptance Criteria:**
- [ ] Returns the N least confident classifications
- [ ] Disagreements correctly identified between rule and LLM results
- [ ] Handles edge cases (all same confidence, empty input)

---

#### 5.4 Wire Feedback into LLM Classifier and Pipeline
**Status: PENDING**
**Recommendation Ref:** N3
**Files Affected:**
- `src/classifiers/llm_classifier.py` (modify)
- `src/services/pipeline_service.py` (modify)
- `src/categorizer/categorizer.py` (modify)

**Description:**
Connect the feedback loop: when `LLMClassifier.classify()` is called and a `FewShotRetriever` is available, automatically retrieve relevant examples and inject them into the `ClassificationContext`. Update the pipeline to surface uncertain classifications for review. Update `EmailCategorizer` to record classifications in the `ClassificationStore`.

**Tasks:**
1. [ ] Add `few_shot_retriever: FewShotRetriever | None = None` to `LLMClassifier.__init__()`
2. [ ] In `classify()`: if retriever is available, embed the email, retrieve examples, populate `ClassificationContext.few_shot_examples`
3. [ ] Update `_build_prompt()` to include few-shot examples when present
4. [ ] In `EmailCategorizer.categorize_email()`: save classification to `ClassificationStore` when database is available
5. [ ] In pipeline: after classification, run uncertainty sampler and log results

**Acceptance Criteria:**
- [ ] Few-shot examples are included in LLM prompt when available
- [ ] Classifier works without retriever (zero-shot mode, backward compat)
- [ ] Classifications are recorded for model tracking
- [ ] Uncertain classifications are surfaced in pipeline output

---

### Phase 5 Testing Requirements

- [ ] All existing tests pass
- [ ] Temporal decay calculations verified against known values
- [ ] MMR diversity tested with synthetic embeddings
- [ ] End-to-end test: correction → retrieval → improved classification (mocked)

### Phase 5 Completion Checklist

- [ ] All work items complete
- [ ] All tests passing
- [ ] `ruff check src/` passes
- [ ] Feedback store correctly captures corrections
- [ ] Few-shot retrieval produces diverse examples
- [ ] Pipeline surfaces uncertain classifications

---

## Phase 6: Ensemble Model Progression

**Estimated Complexity:** L (~7 files, ~500 LOC)
**Dependencies:** Phase 5 (requires 50+ corrections per category for SetFit training)
**Parallelizable:** Work items 6.1 and 6.2 can run concurrently

### Goals
- Add SetFit classifier for few-shot fine-tuning
- Build ensemble classifier that chains rules → SetFit → LLM
- Create training pipeline CLI command
- Add per-category accuracy tracking

### Work Items

#### 6.1 Implement SetFitClassifier
**Status: PENDING**
**Recommendation Ref:** N4
**Files Affected:**
- `src/classifiers/setfit_classifier.py` (create)
- `tests/unit/test_setfit_classifier.py` (create)

**Description:**
Implement `SetFitClassifier(BaseClassifier)` that uses the SetFit library for few-shot fine-tuning. SetFit achieves competitive accuracy with 8-16 examples per class. The classifier loads a pre-trained model, accepts a training set of (text, label) pairs, and classifies new emails. Model is saved locally and loaded on startup.

**Tasks:**
1. [ ] Create `src/classifiers/setfit_classifier.py` with `SetFitClassifier` class
2. [ ] Implement `train(examples: list[tuple[str, str]])` — fine-tune SetFit model on labeled examples
3. [ ] Implement `classify()` per BaseClassifier contract
4. [ ] Implement `save_model(path: Path)` and `load_model(path: Path)`
5. [ ] Add confidence scoring via prediction probability
6. [ ] Write tests with small synthetic training sets (mocked SetFit for CI speed)

**Acceptance Criteria:**
- [ ] Training completes successfully with 8+ examples per class
- [ ] Model can be saved and loaded from disk
- [ ] Classification output matches BaseClassifier contract
- [ ] Confidence scores are meaningful (not all 1.0 or all 0.5)

---

#### 6.2 Implement EnsembleClassifier
**Status: PENDING**
**Recommendation Ref:** N4
**Files Affected:**
- `src/classifiers/ensemble.py` (create)
- `tests/unit/test_ensemble.py` (create)

**Description:**
Implement `EnsembleClassifier(BaseClassifier)` that chains multiple classifiers in priority order. Default chain: rules → SetFit → LLM. Each classifier is tried in order; if confidence exceeds the configured threshold, that result is used. If all classifiers are below threshold, the highest-confidence result is returned. Track which classifier produced the final result for accuracy monitoring.

**Tasks:**
1. [ ] Create `src/classifiers/ensemble.py` with `EnsembleClassifier` class
2. [ ] Accept ordered list of `(classifier, confidence_threshold)` tuples
3. [ ] Implement `classify()`: try each classifier in order, accept first result above threshold
4. [ ] Track classifier usage statistics (per-classifier hit rate)
5. [ ] Log which classifier produced each result
6. [ ] Write tests: first classifier confident → used, all below threshold → highest wins, missing classifier → skip

**Acceptance Criteria:**
- [ ] Classifiers are tried in order (rules first)
- [ ] First classifier above threshold wins
- [ ] If all below threshold, highest confidence wins
- [ ] Usage statistics are tracked accurately
- [ ] Missing/failed classifiers are gracefully skipped

---

#### 6.3 Create Training Pipeline CLI Command
**Status: PENDING**
**Recommendation Ref:** N4
**Files Affected:**
- `src/cli/commands/train.py` (create)
- `src/cli/parsers.py` (modify)
- `src/cli/__main__.py` (modify)
- `tests/unit/test_train_cli.py` (create)

**Description:**
Add `python -m src.cli train` command that fine-tunes the local model on accumulated corrections. Reports: number of corrections per category, training accuracy, model version. Supports `--min-examples` (minimum per class, default 8), `--model-type` (setfit or modernbert), and `--output` (model save path).

**Tasks:**
1. [ ] Create `src/cli/commands/train.py` with argument parser and command handler
2. [ ] Load corrections from `CorrectionStore`, group by category
3. [ ] Filter categories with fewer than `--min-examples` corrections
4. [ ] Train SetFit model on filtered corrections
5. [ ] Save model to configured path with version metadata
6. [ ] Report training results: examples per category, accuracy, model path
7. [ ] Write tests for CLI argument parsing and training flow (mocked model)

**Acceptance Criteria:**
- [ ] `python -m src.cli train --help` shows all options
- [ ] Training skips categories with insufficient examples (with warning)
- [ ] Model is saved with version metadata
- [ ] Training results are clearly reported

---

#### 6.4 Add Accuracy Tracking and Retrain Triggers
**Status: PENDING**
**Recommendation Ref:** N4
**Files Affected:**
- `src/learning/accuracy_tracker.py` (create)
- `src/automation/retrainer.py` (create)
- `tests/unit/test_accuracy_tracker.py` (create)

**Description:**
Create `AccuracyTracker` that monitors per-category correction rates over a rolling window. If the correction rate for any category exceeds 20% in the last 7 days, flag for retraining. Create `Retrainer` that the scheduler can invoke for nightly retraining when enough new corrections have accumulated.

**Tasks:**
1. [ ] Create `src/learning/accuracy_tracker.py` with `AccuracyTracker(correction_store, classification_store)` class
2. [ ] Implement `get_accuracy_report(days: int = 7) -> AccuracyReport` with per-category metrics
3. [ ] Implement `needs_retraining(threshold: float = 0.20) -> bool`
4. [ ] Create `src/automation/retrainer.py` with `Retrainer` that orchestrates training when triggered
5. [ ] Write tests for accuracy calculation and threshold detection

**Acceptance Criteria:**
- [ ] Correction rate is accurately computed per category
- [ ] Retraining trigger fires when threshold exceeded
- [ ] Accuracy report shows clear per-category breakdown
- [ ] Tracker handles edge cases (no corrections, new categories)

---

#### 6.5 Add SetFit and Training Dependencies
**Status: PENDING**
**Recommendation Ref:** N4
**Files Affected:**
- `pyproject.toml` (modify)
- `requirements.txt` (modify)

**Tasks:**
1. [ ] Add `setfit>=1.0.0` to `[project.optional-dependencies]` as `ml` extra
2. [ ] Add `torch>=2.0.0` to `ml` extra (SetFit dependency)
3. [ ] Update `requirements.txt` with comment about optional ML dependencies
4. [ ] Test that `pip install -e ".[ml]"` installs SetFit and its dependencies

**Acceptance Criteria:**
- [ ] Core install (`pip install -e .`) does NOT require SetFit/PyTorch
- [ ] ML install (`pip install -e ".[ml]"`) includes SetFit
- [ ] No dependency conflicts

---

### Phase 6 Testing Requirements

- [ ] All existing tests pass
- [ ] SetFit tests mock the model for CI speed
- [ ] Ensemble tests verify correct classifier ordering
- [ ] Accuracy tracker tests use synthetic correction data

### Phase 6 Completion Checklist

- [ ] All work items complete
- [ ] All tests passing
- [ ] `ruff check src/` passes
- [ ] `python -m src.cli train --help` works
- [ ] Ensemble classifier chains correctly
- [ ] Accuracy tracking produces meaningful reports

<!-- END PHASES -->

---

<!-- BEGIN TABLES -->

## Parallel Work Opportunities

| Work Item | Can Run With | Notes |
|-----------|--------------|-------|
| Phase 1 (Classification Foundation) | Phase 3 (SQLite Core) | Independent concerns — classifier abstraction vs storage abstraction |
| Phase 1.1 (BaseClassifier ABC) | Phase 1.4 (Exceptions) | No dependencies between these items |
| Phase 3.1 (Database module) | Phase 3.2 (EmailStore) | 3.2 depends on 3.1 schema, but can start interface design |
| Phase 4.1 (Logger migration) | Phase 4.2 (Embedding sqlite-vec) | Both depend on Phase 3 database, but are independent of each other |
| Phase 5.1 (FeedbackStore) | Phase 5.2 (FewShotRetriever) | Both depend on Phase 4, but are independent of each other |
| Phase 6.1 (SetFitClassifier) | Phase 6.2 (EnsembleClassifier) | Ensemble uses SetFit but can be tested with mocks |

---

## Risk Mitigation

| Risk | Likelihood | Impact | Mitigation Strategy |
|------|------------|--------|---------------------|
| Instructor library API changes | Low | Medium | Pin version, wrap in adapter layer |
| sqlite-vec Windows compatibility | Low | High | Test early in Phase 3; fallback to .npz cache if broken |
| Ollama not installed on user machine | Medium | Medium | Graceful degradation: classify command shows clear install instructions |
| SetFit training too slow on CPU (CI) | Medium | Low | Mock model in tests; GPU training is optional optimization |
| Large corpus migration performance | Low | Medium | Batch inserts with transactions; progress reporting |
| Breaking existing 3,463 tests | Low | High | Every phase maintains backward compat via None-defaulted parameters |
| Prompt injection not fully mitigated | Medium | Medium | Pydantic Literal constraint is the primary defense; sanitizer is defense-in-depth |
| Context window exceeded with few-shot examples | Low | Low | Limit to 5-6 examples; truncate body text in examples |

---

## Success Metrics

- [ ] All 6 phases completed
- [ ] All acceptance criteria met
- [ ] Existing test suite (3,463 tests) passes throughout all phases
- [ ] Test coverage remains >= 85%
- [ ] LLM classification provides >= 80% accuracy on real emails (manual verification)
- [ ] SQLite migration preserves all existing data (email count matches JSON corpus)
- [ ] Few-shot retrieval produces relevant examples from corrections
- [ ] Ensemble classifier correctly chains rules → model → LLM fallback
- [ ] Classification improves measurably after 50+ corrections (tracked via accuracy metrics)

---

## Appendix: Recommendation Traceability

| Recommendation | Source | Phase | Work Item |
|----------------|--------|-------|-----------|
| A1 — Classification Abstraction Layer | RECOMMENDATIONS.md | 1 | 1.1, 1.2, 1.3, 1.4 |
| A2 — Storage Abstraction Layer | RECOMMENDATIONS.md | 3 | 3.1, 3.2 |
| S1 — Prompt Injection Mitigation | RECOMMENDATIONS.md | 2 | 2.1 |
| N1 — LLM Classification | RECOMMENDATIONS.md | 2 | 2.2, 2.3, 2.4 |
| N2 — SQLite + sqlite-vec | RECOMMENDATIONS.md | 3, 4 | 3.1, 3.2, 3.3, 3.4, 4.1, 4.2, 4.3, 4.4 |
| N3 — Email Feedback Loop | RECOMMENDATIONS.md | 5 | 5.1, 5.2, 5.3, 5.4 |
| N4 — Ensemble Model Progression | RECOMMENDATIONS.md | 6 | 6.1, 6.2, 6.3, 6.4, 6.5 |
| U1 — Classify CLI Command | RECOMMENDATIONS.md | 2 | 2.3 |

<!-- END TABLES -->

---

*Implementation plan generated by Claude on 2026-02-28 15:30:00*
*Source: /plan-improvements command*
