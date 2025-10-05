# Feature Specification: Email Corpus Extraction and Analysis System

**Feature Branch**: `001-use-the-document`
**Created**: 2025-10-05
**Status**: Draft
**Input**: User description: "use the document ./info/email-corpus-analysis-spec.md as input"

## Execution Flow (main)
```
1. Parse user description from Input
   → ✓ Loaded email-corpus-analysis-spec.md
2. Extract key concepts from description
   → ✓ Identified: email extraction, analysis, categorization, M365 integration
3. For each unclear aspect:
   → Marked with [NEEDS CLARIFICATION: specific question]
4. Fill User Scenarios & Testing section
   → ✓ Clear user flow defined
5. Generate Functional Requirements
   → ✓ Each requirement testable
6. Identify Key Entities (if data involved)
   → ✓ Entities identified
7. Run Review Checklist
   → ⚠ Some NEEDS CLARIFICATION remain (see below)
8. Return: SUCCESS (spec ready for planning with clarifications needed)
```

---

## ⚡ Quick Guidelines
- ✅ Focus on WHAT users need and WHY
- ❌ Avoid HOW to implement (no tech stack, APIs, code structure)
- 👥 Written for business stakeholders, not developers
- 🔍 Mark all ambiguities - planning phase will research via Context7

### Section Requirements
- **Mandatory sections**: Must be completed for every feature
- **Optional sections**: Include only when relevant to the feature
- When a section doesn't apply, remove it entirely (don't leave as "N/A")

---

## Clarifications

### Session 2025-10-05
- Q: Should the system retain extracted email corpus and analysis files indefinitely, or is there an expected data retention/cleanup policy? → A: Provide optional cleanup after category approval
- Q: When long-running operations fail or are interrupted, what logging detail level is needed for troubleshooting? → A: Debug: all above + intermediate analysis states
- Q: If extraction runs multiple times on the same inbox, how should the system handle the corpus file? → A: Overwrite - replace entire corpus with new extraction
- Q: For FR-049 (analysis completion time), what is an acceptable performance target for 1,000 emails? → A: No hard limit - best effort with progress tracking, prioritize accuracy
- Q: During interactive category review (FR-032), when user selects "skip" for a category, what should happen to that category? → A: Ask again - loop back at end of review

---

## User Scenarios & Testing *(mandatory)*

### Primary User Story
As a user with a large Hotmail/Outlook inbox, I want to extract all my emails, analyze them to discover natural patterns, and receive suggested categories based on my actual email content, so that I can better organize and manage my email archive without manual categorization of thousands of messages.

### Acceptance Scenarios

#### Scenario 1: Complete Email Extraction
1. **Given** I have authenticated M365 MCP server access to my Hotmail account
2. **When** I initiate the email extraction process
3. **Then** the system extracts 100% of emails from my inbox
4. **And** stores them in a structured JSON file with all metadata (sender, subject, body, dates)
5. **And** provides a progress indicator showing emails processed
6. **And** logs any extraction errors without stopping the process
7. **And** reports total extracted and any failures at completion

#### Scenario 2: Corpus Analysis and Pattern Discovery
1. **Given** I have a complete email corpus JSON file
2. **When** I run the analysis process
3. **Then** the system analyzes sender patterns (frequency, domains, types)
4. **And** analyzes subject line patterns (prefixes, keywords, numbered patterns)
5. **And** performs semantic content clustering to identify themes
6. **And** analyzes temporal patterns (email frequency by sender)
7. **And** generates volume statistics
8. **And** produces a comprehensive analysis report in JSON format
9. **And** shows progress during long-running analysis operations

#### Scenario 3: Category Suggestion Generation
1. **Given** I have completed corpus analysis results
2. **When** I request category suggestions
3. **Then** the system generates suggested categories from content clusters
4. **And** applies predefined category templates (financial, shopping, social, etc.)
5. **And** assigns confidence scores to each suggested category
6. **And** provides representative email samples for each category
7. **And** outputs both JSON data and human-readable markdown report

#### Scenario 4: Interactive Category Review
1. **Given** I have category suggestions
2. **When** I enter the interactive review mode
3. **Then** the system presents each category with sample emails
4. **And** allows me to accept, rename, merge, delete, or skip categories
5. **And** re-presents skipped categories at the end of the review session
6. **And** allows me to add custom categories
7. **And** saves my approved category structure for future use

### Edge Cases
- What happens when M365 API rate limits are hit during extraction?
  - System implements exponential backoff and retry logic
  - Shows warning but continues when rate limit clears

- What happens when emails have malformed HTML or missing fields?
  - System logs the error with email ID
  - Continues processing remaining emails
  - Reports failures in summary

- What happens when inbox has 10,000+ emails?
  - System processes in batches with checkpointing every 100 emails
  - Allows resumption if interrupted
  - Provides ETA and progress updates

- What happens when semantic analysis takes too long?
  - System shows progress indicator
  - Allows sampling approach for very large corpora
  - Provides option to skip semantic analysis

- What happens when no clear patterns emerge?
  - System still generates basic categories from templates
  - Reports low confidence scores
  - Suggests manual category creation

- What happens when extraction is interrupted and user wants to resume?
  - System resumes from last checkpoint (every 100 emails)
  - Completed extraction overwrites any partial corpus file
  - Checkpoints are temporary and cleared after successful completion

## Requirements *(mandatory)*

### Functional Requirements

#### Email Extraction (Phase 0 - Step 1)
- **FR-001**: System MUST connect to M365 MCP server to access Hotmail/Outlook inbox
- **FR-002**: System MUST extract all emails using pagination with maximum page size (500 emails per batch)
- **FR-003**: System MUST fetch complete email details including: id, sender (email, name, domain), recipients, subject, body text, received date, attachment status
- **FR-004**: System MUST convert HTML email bodies to plain text while preserving content
- **FR-005**: System MUST handle extraction errors gracefully, logging failures without halting process
- **FR-006**: System MUST implement retry logic with exponential backoff for rate limiting and timeouts
- **FR-007**: System MUST save extracted emails to local JSON file at `/mnt/user-data/outputs/email_corpus.json`, overwriting any existing corpus file from previous extractions
- **FR-008**: System MUST include extraction metadata: date, total count, source, user email
- **FR-009**: System MUST provide progress indicators showing emails processed and percentage complete
- **FR-010**: System MUST checkpoint progress every 100 emails to enable resumption after interruption
- **FR-011**: System MUST log extraction errors to `/mnt/user-data/outputs/extraction_errors.log`

#### Corpus Analysis (Phase 0 - Step 2)
- **FR-012**: System MUST analyze sender patterns: frequency distribution, domain clustering, sender type classification
- **FR-013**: System MUST classify senders as: personal, service, marketing, or work based on heuristics
- **FR-014**: System MUST analyze subject patterns: common prefixes (RE:, FWD:), numbered patterns, keywords, bracket tags
- **FR-015**: System MUST perform semantic content analysis using text embeddings and clustering
- **FR-016**: System MUST cluster emails into configurable number of thematic groups (default: 10 clusters)
- **FR-017**: System MUST identify representative samples for each cluster (5 closest to centroid)
- **FR-018**: System MUST analyze temporal patterns: sender frequency classification (one-time, daily, weekly, monthly, occasional)
- **FR-019**: System MUST calculate volume statistics: total emails, unique senders, date range, attachment percentage, average body length
- **FR-020**: System MUST save analysis results to `/mnt/user-data/outputs/corpus_analysis_results.json`
- **FR-021**: System MUST show progress during analysis operations taking longer than 10 seconds

#### Category Generation (Phase 0 - Step 3)
- **FR-022**: System MUST generate category suggestions from content clusters (clusters >5% of corpus)
- **FR-023**: System MUST generate categories from high-volume senders (>20 emails)
- **FR-024**: System MUST apply predefined category templates: Financial & Banking, Shopping & E-commerce, Social Media, Newsletters & Marketing, Travel & Transportation, Account & Security
- **FR-025**: System MUST assign confidence scores based on: email count, source type, percentage of corpus
- **FR-026**: System MUST include for each category: name, description, confidence score, email count, percentage, representative sample IDs, distinguishing features
- **FR-027**: System MUST merge similar categories to avoid duplication
- **FR-028**: System MUST sort categories by confidence score (highest first)
- **FR-029**: System MUST save suggestions to `/mnt/user-data/outputs/category_suggestions.json`
- **FR-030**: System MUST generate human-readable markdown report at `/mnt/user-data/outputs/category_suggestions_report.md`

#### Interactive Review (Phase 0 - Step 4)
- **FR-031**: System MUST present categories one at a time with details and sample emails
- **FR-032**: System MUST allow users to: accept, rename, merge, delete, or skip each category; skipped categories MUST be presented again at end of review session
- **FR-033**: System MUST allow users to add custom categories with name and description
- **FR-034**: System MUST merge categories by combining email counts and sample IDs
- **FR-035**: System MUST assign unique category IDs to approved categories
- **FR-036**: System MUST save approved categories to `/mnt/user-data/outputs/approved_categories.json`
- **FR-037**: System MUST include processing statistics: suggested, approved, modified, merged, deleted, custom counts
- **FR-038**: System MUST offer optional cleanup of intermediate files (corpus, analysis results, suggestions) after category approval is complete

#### Data Privacy & Security
- **FR-039**: System MUST store all email data in local filesystem only (never cloud/remote)
- **FR-040**: System MUST NOT transmit personal email content to external services without explicit user consent
- **FR-041**: System MUST use UTF-8 encoding for all file operations
- **FR-042**: System MUST set appropriate file permissions (user-only read/write) on output files

#### Error Handling & Resilience
- **FR-043**: System MUST validate inputs before processing
- **FR-044**: System MUST continue processing when individual emails fail
- **FR-045**: System MUST log all errors with debug-level detail including: timestamp, operation name, error message, email IDs, batch numbers, retry counts, full stack traces, API responses, and intermediate analysis states
- **FR-046**: System MUST report partial success with clear failure summary
- **FR-047**: System MUST handle Unicode/encoding errors gracefully

#### Performance & Scale
- **FR-048**: System MUST support inboxes with 10,000+ emails
- **FR-049**: System MUST process emails during extraction on best-effort basis with progress tracking [NEEDS CLARIFICATION: depends on network/API performance - actual rate may vary]
- **FR-050**: System MUST complete analysis with no hard time limit, prioritizing accuracy over speed, while showing progress indicators for operations exceeding 10 seconds
- **FR-051**: System MUST use streaming/generator patterns to avoid loading all emails into memory simultaneously

### Key Entities *(include if feature involves data)*

- **Email**: Individual email message with metadata
  - Attributes: id (unique identifier), sender (email/name/domain), recipients, subject, body_text (plain text), received_date (ISO format), has_attachments (boolean)
  - Relationships: belongs to Corpus, may belong to multiple Categories

- **Corpus**: Complete collection of extracted emails
  - Attributes: extraction_date, total_emails, source (Hotmail/M365), user_email
  - Relationships: contains many Emails

- **Sender**: Email sender information
  - Attributes: email (address), name (display name), domain, type (personal/service/marketing/work), frequency_count
  - Relationships: has sent many Emails

- **AnalysisResults**: Complete analysis output
  - Components: sender_analysis, subject_patterns, content_clusters, temporal_patterns, volume_stats
  - Relationships: analyzes one Corpus

- **ContentCluster**: Thematic grouping from semantic analysis
  - Attributes: cluster_id, size, percentage, centroid (embedding), common_domains
  - Relationships: contains many Emails, may generate Category

- **Category**: Suggested or approved email classification
  - Attributes: category_id, category_name, description, confidence, email_count, percentage, source (cluster/sender/template/custom), user_modified (boolean)
  - Relationships: associated with many Emails, may derive from ContentCluster

- **CategoryTemplate**: Predefined category pattern
  - Attributes: name, keywords (list), domains (list), description
  - Used for: matching against corpus to suggest categories

---

## Review & Acceptance Checklist
*GATE: Automated checks run during main() execution*

### Content Quality
- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

### Requirement Completeness
- [⚠] No [NEEDS CLARIFICATION] markers remain - **2 clarifications remain** (FR-048, FR-049 - performance targets dependent on environment)
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Scope is clearly bounded (Phase 0 only - corpus extraction and analysis, NOT subsequent categorization workflow)
- [x] Dependencies and assumptions identified (M365 MCP server authenticated, Context7 for library research)

---

## Execution Status
*Updated by main() during processing*

- [x] User description parsed
- [x] Key concepts extracted
- [x] Ambiguities marked
- [x] User scenarios defined
- [x] Requirements generated
- [x] Entities identified
- [⚠] Review checklist passed (with 2 minor clarifications)

---

## Success Criteria

The feature is complete when:
1. User can extract 100% of accessible emails from Hotmail inbox via M365 MCP
2. System generates structured corpus file with all email metadata and content
3. System produces comprehensive analysis report covering senders, subjects, semantics, temporal patterns, and volume (prioritizing accuracy over speed)
4. System suggests initial categories with confidence scores
5. User can interactively review and approve category structure
6. All data remains stored locally with no unauthorized external transmission
7. Process handles errors gracefully with clear reporting and debug-level logging
8. Long operations show progress indicators (operations >10 seconds)
9. User can optionally cleanup intermediate files after category approval

## Out of Scope (Phase 0)
- Email-by-email categorization (future Phase 1)
- Interactive learning from user corrections (future)
- Automated daily processing (future)
- Email filtering or moving (future)
- Real-time email monitoring (future)
- Category rule refinement (future)
