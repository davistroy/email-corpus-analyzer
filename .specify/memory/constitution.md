<!--
SYNC IMPACT REPORT
==================
Version Change: Initial Constitution (v1.0.0)
Modified Principles: N/A (new constitution)
Added Sections:
  - Core Principles (I-VII)
  - Technology Standards
  - Development Workflow
  - Governance
Removed Sections: N/A
Templates Status:
  ✅ plan-template.md - Reviewed, aligned with TDD and documentation principles
  ✅ spec-template.md - Reviewed, aligned with requirements clarity principles
  ✅ tasks-template.md - Reviewed, aligned with TDD and task management principles
Follow-up TODOs: None
-->

# Email Corpus Analysis & Categorization Constitution

## Core Principles

### I. Test-Driven Development (NON-NEGOTIABLE)
**TDD is mandatory for all implementation work.** Tests MUST be written before any implementation code. The development cycle strictly follows Red-Green-Refactor:
1. Write failing tests that define expected behavior
2. Implement minimum code to make tests pass
3. Refactor while keeping tests green

**Rationale:** This ensures code correctness, prevents regression, and produces maintainable, well-designed code from the start. For data analysis and ML work, this prevents silent failures and data corruption.

### II. Documentation-First
**All features begin with clear specification documents.** Before any code is written:
- Feature specs (spec.md) define WHAT and WHY without implementation details
- Implementation plans (plan.md) define HOW with technical decisions
- Data models (data-model.md) define entities and relationships
- Contracts define interfaces and expected behaviors

**Rationale:** Documentation prevents ambiguity, enables review before investment, and serves as living documentation. In data processing, clear specs prevent costly rework from misunderstood requirements.

### III. Context7-Mandatory Research
**All external library usage MUST use the Context7 MCP server for documentation lookup.** Before using any library, framework, or API:
- Query Context7 for latest documentation and best practices
- Verify version compatibility and recommended patterns
- Document the research findings in research.md

**Rationale:** Ensures we use current best practices, avoid deprecated patterns, and reduce bugs from outdated documentation. Critical for data processing libraries where APIs change frequently.

### IV. Privacy & Data Security
**All email data MUST remain local and private.** Email corpus data:
- MUST be stored in local filesystem only (never cloud/remote)
- MUST use appropriate file permissions (user-only read/write)
- MUST NOT transmit personal email content to external services without explicit consent
- MAY use local AI models for analysis (no data leaves machine)

**Rationale:** Email contains sensitive personal information. Privacy violations would destroy user trust and violate data protection principles.

### V. Modular, Testable Components
**Every analysis function MUST be independently testable.** Code organization:
- Each analysis type (sender, subject, semantic) is a separate module
- Each module has clear input/output contracts
- Modules can be tested with sample data without full corpus
- No hidden dependencies or global state

**Rationale:** Enables incremental development, easier debugging, and confidence in correctness. Data processing pipelines fail when components can't be tested in isolation.

### VI. Error Resilience
**Data processing MUST handle failures gracefully.** All extraction and analysis code:
- MUST validate inputs before processing
- MUST log errors with sufficient context for debugging
- MUST continue processing when individual items fail
- MUST report partial success with clear failure summary

**Rationale:** Email corpora are messy with malformed data. Stopping on first error wastes time and prevents completion. Users need visibility into what succeeded and what failed.

### VII. Performance Transparency
**Long-running operations MUST show progress.** For any operation >10 seconds:
- Display progress indicators (percentage, items processed)
- Provide time estimates when possible
- Show intermediate results when applicable
- Allow checkpointing for very long operations

**Rationale:** User feedback prevents uncertainty and frustration. Checkpointing prevents data loss from interruptions. Critical for processing thousands of emails.

## Technology Standards

### Required Tools & Libraries
- **Language**: Python 3.10+ (for type hints, pattern matching, better error messages)
- **Documentation Lookup**: Context7 MCP server (mandatory for all library research)
- **Email Access**: M365 MCP server for Outlook/Hotmail integration
- **Data Storage**: JSON files with UTF-8 encoding (for portability and readability)
- **ML/Analysis**: Latest versions researched via Context7 before selection
  - Text embeddings: Research via Context7 (e.g., sentence-transformers, OpenAI)
  - Clustering: Research via Context7 (e.g., scikit-learn)
  - HTML parsing: Research via Context7 (e.g., BeautifulSoup4)

### Technology Selection Process
1. Identify technology need from feature spec
2. Query Context7 MCP for latest best practices and recommendations
3. Document findings in research.md with:
   - Selected library and version
   - Rationale for selection
   - Alternatives considered
   - Context7 query used
4. Only after Context7 research: add to requirements.txt

### Versioning
All dependencies MUST specify exact versions in requirements.txt:
- Format: `package==X.Y.Z`
- Update only when Context7 research shows clear benefit
- Document version changes in research.md

## Development Workflow

### Feature Development Lifecycle
1. **Specification** (`/specify`): Create spec.md defining user needs and acceptance criteria
2. **Planning** (`/plan`): Research via Context7, design components, create plan.md
3. **Task Generation** (`/tasks`): Generate ordered, testable tasks in tasks.md
4. **Implementation** (`/implement`): Execute tasks following TDD principles
5. **Validation**: Run all tests, verify acceptance criteria

### Code Review Requirements
All code changes MUST:
- Include passing tests (written first per TDD)
- Document any Context7 research performed
- Update relevant documentation (data-model.md, plan.md)
- Pass linting and type checking
- Include error handling for expected failure modes

### Testing Requirements
Every component MUST have:
- **Contract tests**: Verify interface contracts are honored
- **Integration tests**: Verify components work together correctly
- **Unit tests**: Verify individual functions handle edge cases
- **Sample data tests**: Use realistic but anonymized email samples

## Governance

### Constitution Authority
This constitution supersedes all other practices and preferences. When conflicts arise:
1. Constitution principles take precedence
2. If constitution is silent, defer to research via Context7
3. If still unclear, document decision in plan.md with rationale

### Amendment Process
Constitution changes require:
1. Documented justification (what problem does change solve?)
2. Impact analysis on existing features
3. Version update following semantic versioning:
   - MAJOR: Breaking changes to core principles
   - MINOR: New principles or significant expansions
   - PATCH: Clarifications or corrections

### Compliance Verification
Every feature MUST:
- Pass Constitutional Check gates in plan.md
- Document any principle deviations in Complexity Tracking
- Justify deviations with specific rationale
- Prefer simplifying approach over violating principles

### Context7 Enforcement
Before using ANY external library or API:
- MUST query Context7 MCP server for current documentation
- MUST document Context7 findings in research.md
- MUST NOT rely on potentially outdated knowledge or tutorials
- MAY supplement Context7 with additional research, but Context7 is baseline

**Version**: 1.0.0 | **Ratified**: 2025-10-05 | **Last Amended**: 2025-10-05
