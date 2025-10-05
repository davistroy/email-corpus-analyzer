
# Implementation Plan: Email Corpus Extraction and Analysis System

**Branch**: `001-use-the-document` | **Date**: 2025-10-05 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/home/davistroy/dev/email-processor/initial-learning/specs/001-use-the-document/spec.md`

## Execution Flow (/plan command scope)
```
1. Load feature spec from Input path
   → If not found: ERROR "No feature spec at {path}"
2. Fill Technical Context (scan for NEEDS CLARIFICATION)
   → Detect Project Type from file system structure or context (web=frontend+backend, mobile=app+api)
   → Set Structure Decision based on project type
3. Fill the Constitution Check section based on the content of the constitution document.
4. Evaluate Constitution Check section below
   → If violations exist: Document in Complexity Tracking
   → If no justification possible: ERROR "Simplify approach first"
   → Update Progress Tracking: Initial Constitution Check
5. Execute Phase 0 → research.md
   → If NEEDS CLARIFICATION remain: ERROR "Resolve unknowns"
6. Execute Phase 1 → contracts, data-model.md, quickstart.md, agent-specific template file (e.g., `CLAUDE.md` for Claude Code, `.github/copilot-instructions.md` for GitHub Copilot, `GEMINI.md` for Gemini CLI, `QWEN.md` for Qwen Code, or `AGENTS.md` for all other agents).
7. Re-evaluate Constitution Check section
   → If new violations: Refactor design, return to Phase 1
   → Update Progress Tracking: Post-Design Constitution Check
8. Plan Phase 2 → Describe task generation approach (DO NOT create tasks.md)
9. STOP - Ready for /tasks command
```

**IMPORTANT**: The /plan command STOPS at step 7. Phases 2-4 are executed by other commands:
- Phase 2: /tasks command creates tasks.md
- Phase 3-4: Implementation execution (manual or via tools)

## Summary
Extract all emails from Hotmail/Outlook inbox via M365 MCP server, analyze patterns across sender/subject/semantic/temporal dimensions, generate AI-assisted category suggestions, and provide interactive review interface. System prioritizes privacy (local-only storage), accuracy over speed, debug-level logging, and modular testable components following TDD principles.

## Technical Context
**Language/Version**: Python 3.10+ (per constitution requirement for type hints, pattern matching)
**Primary Dependencies**: NEEDS CLARIFICATION - Will research via Context7: text embedding libraries (sentence-transformers/OpenAI), clustering (scikit-learn), HTML parsing (BeautifulSoup4), M365 MCP client
**Storage**: Local JSON files with UTF-8 encoding at `/mnt/user-data/outputs/` (per constitution privacy requirement)
**Testing**: pytest (Python standard, supports fixtures and parametrization)
**Target Platform**: Linux/WSL2 (per env context), local execution only (no cloud/remote)
**Project Type**: Single project (CLI-based data processing pipeline)
**Performance Goals**: Best-effort with progress tracking for operations >10 seconds; prioritize accuracy over speed (per clarification Q4)
**Constraints**: No hard time limits; support 10,000+ emails; memory-efficient streaming/generators; local-only data storage; debug-level logging (per clarification Q2)
**Scale/Scope**: Phase 0 only - corpus extraction and analysis; 4 main processing steps (extract, analyze, suggest, review); 51 functional requirements

## Constitution Check
*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Verify compliance with Email Corpus Analysis Constitution v1.0.0:

- [x] **TDD Compliance**: Plan includes test-first approach (contract tests before implementation) - Phase 1 generates failing tests before any implementation
- [x] **Documentation-First**: All design artifacts (spec.md, data-model.md, contracts/) exist before coding - spec.md complete, Phase 1 will generate data-model.md and contracts/
- [x] **Context7 Research**: All external libraries researched via Context7 MCP server - Phase 0 will query Context7 for all dependencies marked NEEDS CLARIFICATION
- [x] **Privacy & Data Security**: Email data stored locally, no unauthorized external transmission - All storage paths use `/mnt/user-data/outputs/`, FR-039/FR-040 enforce local-only
- [x] **Modular Components**: Each analysis module independently testable with clear contracts - Design separates extraction, sender analysis, subject analysis, semantic analysis, category generation modules
- [x] **Error Resilience**: Plan includes error handling, logging, and graceful degradation - FR-043 through FR-047 enforce debug-level logging, partial success reporting, graceful continuation
- [x] **Performance Transparency**: Long operations include progress indicators and checkpointing - FR-009, FR-010, FR-021, FR-050 enforce progress tracking for operations >10 seconds

**Justification for any violations:** No violations - all constitutional principles satisfied

## Project Structure

### Documentation (this feature)
```
specs/[###-feature]/
├── plan.md              # This file (/plan command output)
├── research.md          # Phase 0 output (/plan command)
├── data-model.md        # Phase 1 output (/plan command)
├── quickstart.md        # Phase 1 output (/plan command)
├── contracts/           # Phase 1 output (/plan command)
└── tasks.md             # Phase 2 output (/tasks command - NOT created by /plan)
```

### Source Code (repository root)
```
src/
├── models/              # Data models (Email, Corpus, Sender, Category, etc.)
│   ├── __init__.py
│   ├── email.py
│   ├── corpus.py
│   ├── sender.py
│   ├── analysis_results.py
│   ├── content_cluster.py
│   └── category.py
├── extractors/          # Email extraction logic
│   ├── __init__.py
│   ├── m365_extractor.py
│   ├── html_parser.py
│   └── checkpoint_manager.py
├── analyzers/           # Analysis modules (modular per constitution)
│   ├── __init__.py
│   ├── sender_analyzer.py
│   ├── subject_analyzer.py
│   ├── semantic_analyzer.py
│   ├── temporal_analyzer.py
│   └── volume_analyzer.py
├── generators/          # Category generation
│   ├── __init__.py
│   ├── category_generator.py
│   ├── template_matcher.py
│   └── confidence_scorer.py
├── ui/                  # Interactive review interface
│   ├── __init__.py
│   └── category_review.py
├── utils/               # Shared utilities
│   ├── __init__.py
│   ├── logger.py
│   ├── progress.py
│   ├── file_manager.py
│   └── validators.py
└── main.py              # CLI entry point

tests/
├── contract/            # Contract tests (API/module interfaces)
│   ├── test_extractor_contract.py
│   ├── test_analyzer_contract.py
│   └── test_generator_contract.py
├── integration/         # Integration tests (end-to-end flows)
│   ├── test_extraction_flow.py
│   ├── test_analysis_flow.py
│   ├── test_suggestion_flow.py
│   └── test_review_flow.py
├── unit/                # Unit tests (individual functions)
│   ├── test_html_parser.py
│   ├── test_sender_classifier.py
│   ├── test_confidence_scorer.py
│   └── test_validators.py
└── fixtures/            # Test data and sample emails
    ├── sample_corpus.json
    └── sample_emails/

/mnt/user-data/outputs/  # Runtime output directory (gitignored)
├── email_corpus.json
├── extraction_errors.log
├── corpus_analysis_results.json
├── category_suggestions.json
├── category_suggestions_report.md
└── approved_categories.json
```

**Structure Decision**: Single project structure (Option 1) selected. This is a CLI-based data processing pipeline without web/mobile components. Modular design with separate directories for extraction, analysis, generation, and UI aligns with Constitution Principle V (Modular, Testable Components). Test structure follows TDD principle with contract/integration/unit separation.

## Phase 0: Outline & Research
1. **Extract unknowns from Technical Context** above:
   - For each NEEDS CLARIFICATION → research task
   - For each dependency → best practices task
   - For each integration → patterns task

2. **Generate and dispatch research agents**:
   ```
   For each unknown in Technical Context:
     Task: "Research {unknown} for {feature context}"
   For each technology choice:
     Task: "Find best practices for {tech} in {domain}"
   ```

3. **Consolidate findings** in `research.md` using format:
   - Decision: [what was chosen]
   - Rationale: [why chosen]
   - Alternatives considered: [what else evaluated]

**Output**: research.md with all NEEDS CLARIFICATION resolved

## Phase 1: Design & Contracts
*Prerequisites: research.md complete*

1. **Extract entities from feature spec** → `data-model.md`:
   - Entity name, fields, relationships
   - Validation rules from requirements
   - State transitions if applicable

2. **Generate API contracts** from functional requirements:
   - For each user action → endpoint
   - Use standard REST/GraphQL patterns
   - Output OpenAPI/GraphQL schema to `/contracts/`

3. **Generate contract tests** from contracts:
   - One test file per endpoint
   - Assert request/response schemas
   - Tests must fail (no implementation yet)

4. **Extract test scenarios** from user stories:
   - Each story → integration test scenario
   - Quickstart test = story validation steps

5. **Update agent file incrementally** (O(1) operation):
   - Run `.specify/scripts/bash/update-agent-context.sh claude`
     **IMPORTANT**: Execute it exactly as specified above. Do not add or remove any arguments.
   - If exists: Add only NEW tech from current plan
   - Preserve manual additions between markers
   - Update recent changes (keep last 3)
   - Keep under 150 lines for token efficiency
   - Output to repository root

**Output**: data-model.md, /contracts/*, failing tests, quickstart.md, agent-specific file

## Phase 2: Task Planning Approach
*This section describes what the /tasks command will do - DO NOT execute during /plan*

**Task Generation Strategy**:
- Load `.specify/templates/tasks-template.md` as base
- Generate tasks from Phase 1 design docs (contracts, data model, quickstart)
- Each contract → contract test task [P]
- Each entity → model creation task [P] 
- Each user story → integration test task
- Implementation tasks to make tests pass

**Ordering Strategy**:
- TDD order: Tests before implementation 
- Dependency order: Models before services before UI
- Mark [P] for parallel execution (independent files)

**Estimated Output**: 25-30 numbered, ordered tasks in tasks.md

**IMPORTANT**: This phase is executed by the /tasks command, NOT by /plan

## Phase 3+: Future Implementation
*These phases are beyond the scope of the /plan command*

**Phase 3**: Task execution (/tasks command creates tasks.md)  
**Phase 4**: Implementation (execute tasks.md following constitutional principles)  
**Phase 5**: Validation (run tests, execute quickstart.md, performance validation)

## Complexity Tracking
*Fill ONLY if Constitution Check has violations that must be justified*

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| [e.g., 4th project] | [current need] | [why 3 projects insufficient] |
| [e.g., Repository pattern] | [specific problem] | [why direct DB access insufficient] |


## Phase 2: Task Planning Approach
*This section describes what the /tasks command will do - DO NOT execute during /plan*

**Task Generation Strategy**:
- Load data-model.md entities → create model implementation tasks
- Load contracts/* → create contract test tasks (MUST fail before implementation)
- Load quickstart.md scenarios → create integration test tasks
- Generate implementation tasks to make tests pass
- Add utility tasks (logging, progress tracking, file management)

**Ordering Strategy**:
- TDD order: Contract tests → Integration tests → Models → Analyzers → Generators → CLI
- Parallel tasks marked [P] for independent files
- Sequential for same-file modifications

**Estimated Output**: ~35-40 numbered tasks in tasks.md

**Categories**:
1. **Setup** (3-5 tasks): Project structure, dependencies, configuration
2. **Tests First** (8-10 tasks): Contract tests, integration tests (ALL MUST FAIL initially)
3. **Core Models** (7-8 tasks): Pydantic models for all entities
4. **Extraction** (4-5 tasks): M365 integration, HTML parsing, checkpointing
5. **Analysis** (6-8 tasks): 5 analyzer modules + orchestrator
6. **Generation** (4-5 tasks): Category generation, template matching, confidence scoring
7. **Interactive UI** (2-3 tasks): Category review CLI
8. **Polish** (5-6 tasks): Error handling, logging, cleanup, documentation

**IMPORTANT**: This phase is executed by the /tasks command, NOT by /plan

---

## Progress Tracking
*This checklist is updated during execution flow*

**Phase Status**:
- [x] Phase 0: Research complete (/plan command) - research.md created with Context7 findings
- [x] Phase 1: Design complete (/plan command) - data-model.md, contracts/, quickstart.md, CLAUDE.md created
- [x] Phase 2: Task planning complete (/plan command - describe approach only) - strategy documented above
- [ ] Phase 3: Tasks generated (/tasks command) - Not executed by /plan
- [ ] Phase 4: Implementation complete
- [ ] Phase 5: Validation passed

**Gate Status**:
- [x] Initial Constitution Check: PASS - All 7 principles satisfied
- [x] Post-Design Constitution Check: PASS - Re-evaluated below, no violations
- [x] All NEEDS CLARIFICATION resolved - Context7 research completed for all libraries
- [x] Complexity deviations documented - None (no violations)

**Artifacts Generated**:
- [x] `/specs/001-use-the-document/plan.md` (this file)
- [x] `/specs/001-use-the-document/research.md` (Context7 findings)
- [x] `/specs/001-use-the-document/data-model.md` (7 entities with Pydantic models)
- [x] `/specs/001-use-the-document/contracts/extractor_contract.md`
- [x] `/specs/001-use-the-document/contracts/analyzer_contract.md`
- [x] `/specs/001-use-the-document/contracts/generator_contract.md`
- [x] `/specs/001-use-the-document/quickstart.md` (5 acceptance scenarios)
- [x] `/CLAUDE.md` (agent context file updated)

---

## Post-Design Constitution Re-Check

Verify compliance after Phase 1 design:

- [x] **TDD Compliance**: Contracts define failing tests before implementation - extractor_contract.md, analyzer_contract.md, generator_contract.md all include test cases
- [x] **Documentation-First**: All artifacts generated (data-model, contracts, quickstart) before any code - 8 design documents created
- [x] **Context7 Research**: research.md documents all Context7 queries with library IDs and findings
- [x] **Privacy & Data Security**: data-model.md enforces local-only storage, file permissions 0600, no external transmission
- [x] **Modular Components**: 7 entities + 5 analyzer modules + extractor + generator all independently testable with clear contracts
- [x] **Error Resilience**: Contracts specify error handling (ExtractionError, try/except patterns), debug logging (Clarification Q2)
- [x] **Performance Transparency**: Contracts specify progress_callback parameters for all long operations

**Result**: NO VIOLATIONS - Design fully constitutional

---
*Based on Constitution v1.0.0 - See `.specify/memory/constitution.md`*
