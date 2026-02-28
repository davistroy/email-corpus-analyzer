# Implementation Plan v2: Phase 2

**Generated:** 2026-02-28
**Based On:** Intent Review findings, TUI Frontend Design Review, spec.md Out of Scope items
**Total Phases:** 6
**Methodology:** TDD per constitution (tests first, then implementation)
**Predecessor:** IMPLEMENTATION_PLAN.md (Phase 1 extraction pipeline fixes — complete)

---

## Plan Overview

Phase 2 brings the 5 originally out-of-scope features into the system and overhauls the TUI for production quality. The phases are ordered by dependency and value: TUI improvements first (they benefit all subsequent features), then the 5 new capabilities in increasing complexity order.

### Phase Summary Table

| Phase | Focus Area | Key Deliverables | Est. Effort | Dependencies |
|-------|------------|------------------|-------------|--------------|
| 1 | TUI Polish & Integration | Wire unused widgets, fix state management, responsive layout | Medium | None |
| 2 | TUI Advanced Features | Search/filter UI, undo/redo, bulk operations, accessibility | Medium | Phase 1 |
| 3 | Category Rule Refinement | Rule editor, condition builder, rule testing, iterative improvement | Medium | None |
| 4 | Email-by-Email Categorization | Apply approved categories to individual emails, confidence scoring | Large | Phase 3 |
| 5 | Email Filtering & Moving | Apply rules to live mailbox via Graph API / Gmail API | Large | Phase 4 |
| 6 | Automated Processing & Monitoring | Scheduled re-extraction, incremental analysis, change detection | Large | Phase 5 |

---

## Phase 1: TUI Polish & Integration

**Goal:** Wire the existing but unused widgets into the layout, fix state management, eliminate code duplication, and make the TUI responsive.

**Rationale:** The TUI already has StatsPanel, ProgressBar, and SearchInput widgets built but never integrated. Confidence formatting is duplicated across 3 files. State is scattered with no centralized management. Fixing these before adding features prevents compounding technical debt.

### Work Items

#### 1.1 Centralize Shared Utilities — COMPLETE (2026-02-28)

**Files Affected:**
- `src/ui/tui/utils.py` (NEW)
- `src/ui/tui/widgets/category_table.py`
- `src/ui/tui/widgets/detail_panel.py`
- `src/ui/tui/theme.py`

**What:**
- Extract `format_confidence_bar()` into a shared `utils.py` module (currently duplicated with different Unicode chars in category_table.py:30 and detail_panel.py:39)
- Extract `get_confidence_level()` into shared location (duplicated in theme.py and detail_panel.py)
- Move all hardcoded truncation lengths into named constants: `MAX_NAME_DISPLAY = 28`, `MAX_SUBJECT_DISPLAY = 50`, `MAX_FEATURE_DISPLAY = 70`
- Move confidence thresholds (0.7, 0.4) from theme.py:31-32 into config-driven values

**Tests:**
- Unit tests for format_confidence_bar with edge cases (0.0, 1.0, negative, >1.0)
- Unit tests for get_confidence_level at boundaries
- Verify no import of old duplicated functions remains

---

#### 1.2 Wire StatsPanel into Layout

**Files Affected:**
- `src/ui/tui/app.py`
- `src/ui/tui/widgets/stats_panel.py`
- `src/ui/tui/theme.py` (CSS updates)

**What:**
- Add StatsPanel below the CategoryTable in the left column
- Wire counters: reviewed/total, approved, modified, merged, deleted
- Update counters on every action (accept, rename, merge, delete, skip)
- Show session timer (elapsed time since review started)

**Tests:**
- StatsPanel renders with zero counts
- Counters increment correctly for each action type
- Panel updates reactively when app state changes

---

#### 1.3 Wire SearchInput and Filter System

**Files Affected:**
- `src/ui/tui/app.py`
- `src/ui/tui/widgets/search_input.py`
- `src/ui/tui/widgets/category_table.py`

**What:**
- Add SearchInput above CategoryTable (activated with `/` key, like vim)
- Wire SearchInput.on_input_changed to CategoryTable.apply_filter()
- Show filter active indicator in status bar ("Filtered: 12/45 categories")
- Escape clears filter and returns focus to table
- Filter matches against: category name, source, description

**Tests:**
- Filter narrows visible rows correctly
- Empty filter shows all rows
- Escape clears filter
- Selection state preserved when filter changes
- Filter + action (delete filtered item) maintains consistent state

---

#### 1.4 Centralize State Management — COMPLETE (2026-02-28)

**Files Affected:**
- `src/ui/tui/state.py` (NEW)
- `src/ui/tui/app.py`
- All widgets that read app state

**What:**
- Create `ReviewState` dataclass holding all mutable state: categories, approved, skipped, counters, selected_index, filter_text
- Replace scattered state across app and widgets with single `ReviewState` instance
- Add state change notifications (Textual reactive pattern) so widgets auto-update
- Prevent invalid state transitions (can't merge with empty approved list, can't act on deleted category)

**Tests:**
- State transitions: pending -> approved, pending -> deleted, pending -> skipped
- Invalid transitions raise or no-op gracefully
- Widget updates fire when state changes
- Concurrent action protection (rapid keypresses don't corrupt state)

---

#### 1.5 Responsive Layout

**Files Affected:**
- `src/ui/tui/theme.py` (APP_CSS)
- `src/ui/tui/app.py`
- `src/ui/tui/widgets/category_table.py`

**What:**
- Replace hardcoded 60/40 split with CSS fr units that adapt to terminal width
- Column widths in CategoryTable scale with available width (Name column gets remaining space)
- Add minimum terminal size check (80x24) with graceful message if too small
- Modal dialogs use percentage width (max 80%, min 60 chars) instead of fixed chars
- Handle terminal resize events to reflow layout

**Tests:**
- Layout renders at 80x24, 120x40, 200x60
- Column truncation recalculates on resize
- Modals don't overflow small terminals

---

#### 1.6 Error Handling & User Feedback

**Files Affected:**
- `src/ui/tui/app.py`
- `src/ui/tui/dialogs/merge_dialog.py`

**What:**
- Replace silent `NoMatches` exception catches with user-visible notifications
- Merge dialog: disable selection when approved list is empty, show "No approved categories to merge into" message
- Add "unsaved changes" indicator in footer when actions taken but not saved
- Validate state before every action (guard against acting on stale selection)
- Add notification for failed operations ("Merge failed: target category no longer exists")

**Tests:**
- Merge with empty approved shows message, not empty dialog
- Action on deleted category shows notification
- Unsaved changes indicator appears after first action
- Indicator clears after save

---

## Phase 2: TUI Advanced Features

**Goal:** Add undo/redo, bulk operations UI, sorting, and accessibility improvements.

**Depends on:** Phase 1 (centralized state management is prerequisite for undo/redo)

### Work Items

#### 2.1 Undo/Redo System

**Files Affected:**
- `src/ui/tui/state.py` (extend ReviewState)
- `src/ui/tui/app.py`

**What:**
- Implement command pattern: each action (accept, rename, merge, delete) creates a reversible command object
- `Ctrl+Z` undoes last action, `Ctrl+Y` redoes
- Undo stack limited to 50 operations (memory bound)
- Undo restores category to previous state (re-adds deleted, un-merges, reverts rename)
- Merge undo: split merged category back, restore source category to list

**Tests:**
- Accept then undo: category returns to pending
- Delete then undo: category reappears at original position
- Rename then undo: original name restored
- Merge then undo: source category restored, emails split back
- Undo stack limit: 51st action drops oldest
- Redo after undo: action reapplied

---

#### 2.2 Bulk Operations UI

**Files Affected:**
- `src/ui/tui/app.py`
- `src/ui/tui/widgets/category_table.py`
- `src/ui/tui/widgets/action_bar.py`
- `src/ui/tui/dialogs/bulk_action_dialog.py`

**What:**
- `Space` toggles selection on current row (already coded, wire to visible indicator)
- `Ctrl+A` selects all visible (respects current filter)
- Selected rows show checkmark column indicator
- ActionBar shows "X selected" count when selection active
- Bulk accept/delete available via `Shift+A` / `Shift+D`
- Bulk action confirmation dialog shows affected categories (paginated for large sets)
- Deselect all with `Escape` (when not in filter mode)

**Tests:**
- Space toggles single selection
- Ctrl+A selects all visible rows
- Bulk delete removes all selected
- Bulk accept approves all selected
- Selection clears after bulk action
- Selection persists across filter changes (only for still-visible items)

---

#### 2.3 Column Sorting

**Files Affected:**
- `src/ui/tui/widgets/category_table.py`
- `src/ui/tui/app.py`

**What:**
- `F1-F4` sorts by column: F1=Name, F2=Confidence, F3=Emails, F4=Source
- Toggle ascending/descending on repeated press
- Show sort indicator arrow in column header
- Default sort: confidence descending (current behavior)
- Sort persists across actions (re-sorts after accept/delete)

**Tests:**
- Sort by confidence ascending/descending
- Sort by name alphabetically
- Sort by email count
- Sort indicator shows in correct column
- Sort preserved after deletion

---

#### 2.4 Accessibility Improvements

**Files Affected:**
- `src/ui/tui/theme.py`
- `src/ui/tui/app.py`
- `src/ui/tui/widgets/category_table.py`

**What:**
- Add high-contrast mode toggled with `Ctrl+H` (yellow on black, bold text)
- Confidence indicators: add text symbols alongside colors (checkmark/warning/x) for color-blind users
- Focus indicators: visible border change on focused widget (not just cursor)
- Key binding hints in ActionBar update contextually (show what's available now)
- Status bar shows current mode: "Normal", "Filtering", "Selecting X"

**Tests:**
- High contrast mode applies correct styles
- Confidence symbols render correctly alongside color bars
- Mode indicator updates on state change
- ActionBar updates when context changes (e.g., merge disabled when no approved)

---

#### 2.5 Clean Up Dead Code and Inconsistencies

**Files Affected:**
- `src/ui/tui/commands.py`
- `src/ui/tui/widgets/category_table.py`
- `src/ui/tui/app.py`

**What:**
- Remove unused `Command` class `enabled` field and `get_command_by_key()` / `get_command_by_action()` functions from commands.py (never called)
- Wire or remove hierarchical promote/demote methods in CategoryTable (currently dead code)
- Normalize naming: all event handlers use `action_` prefix, all internal methods use `_` prefix
- Fix naming inconsistency: `_merge_enabled` vs `selected_row` reactive fields
- Add missing type hints (Dict/List parameter specifications)

**Tests:**
- Verify no regressions after dead code removal
- Import checks pass (no orphaned references)
- mypy passes with stricter type hints

---

## Phase 3: Category Rule Refinement

**Original out-of-scope item:** "Category rule refinement (future)"

**Goal:** Allow users to iteratively improve category rules after the initial suggestion/review cycle. Enable fine-tuning of what matches each category — adjusting sender lists, keyword patterns, domain matches, and confidence thresholds.

### Architecture

```
Category (existing) → CategoryRule (NEW) → RuleCondition (NEW)
                                         → RuleAction (NEW)

src/rules/
  rule_engine.py      - Evaluate rules against emails
  rule_builder.py     - Create/modify rules from category metadata
  rule_tester.py      - Dry-run rules against corpus, show matches
src/models/
  rule.py             - CategoryRule, RuleCondition, RuleAction models
src/ui/tui/
  dialogs/rule_editor_dialog.py - TUI dialog for editing rules
```

### Work Items

#### 3.1 Rule Data Model

**Files Affected:**
- `src/models/rule.py` (NEW)

**What:**
- `RuleCondition`: field (sender_email, sender_domain, subject_contains, body_contains, has_attachment), operator (equals, contains, matches_regex, in_list), value
- `CategoryRule`: category_id, conditions (list, AND/OR logic), priority, enabled flag, created_date, last_modified
- `RuleAction`: action_type (categorize, tag, flag), target_category_id
- Auto-generate initial rules from existing category metadata (sender lists, template keywords, cluster features)

---

#### 3.2 Rule Engine

**Files Affected:**
- `src/rules/rule_engine.py` (NEW)

**What:**
- `evaluate(email, rules) -> List[RuleMatch]` — test all rules against a single email
- `categorize_corpus(corpus, rules) -> Dict[email_id, List[category_id]]` — bulk categorization
- Support AND/OR condition groups
- Short-circuit evaluation for performance
- Return match confidence based on condition specificity

---

#### 3.3 Rule Builder

**Files Affected:**
- `src/rules/rule_builder.py` (NEW)

**What:**
- `build_rules_from_categories(categories, analysis_results) -> List[CategoryRule]` — auto-generate rules from existing approved categories
- Template-sourced categories: convert template keywords/domains to rule conditions
- Cluster-sourced categories: extract top TF-IDF terms and common domains as conditions
- Sender-sourced categories: use sender email/domain as conditions
- Allow manual rule creation and editing

---

#### 3.4 Rule Tester

**Files Affected:**
- `src/rules/rule_tester.py` (NEW)

**What:**
- `test_rules(corpus, rules) -> TestReport` — dry-run rules against the full corpus
- Report: matched/unmatched emails, per-rule match counts, overlap (email matched by multiple rules), coverage gaps
- Confusion matrix: compare rule-based categorization vs original cluster assignments
- Suggest rule improvements: "Rule X matches 95% of Category Y — add condition Z to catch remaining 5%"

---

#### 3.5 Rule Editor TUI Dialog

**Files Affected:**
- `src/ui/tui/dialogs/rule_editor_dialog.py` (NEW)
- `src/ui/tui/app.py` (add keybinding)

**What:**
- Accessible from review screen via `E` key on selected category
- Shows current rules for category
- Add/remove/edit conditions
- Test rule against corpus with live match count
- Save modified rules

---

#### 3.6 CLI Integration

**Files Affected:**
- `src/cli/commands/rules.py` (NEW)
- `src/cli/__init__.py`

**What:**
- `python -m src.cli rules generate` — auto-generate rules from approved categories
- `python -m src.cli rules test` — dry-run rules against corpus
- `python -m src.cli rules show` — display current rules
- `python -m src.cli rules edit` — interactive rule editing (TUI)

---

## Phase 4: Email-by-Email Categorization

**Original out-of-scope item:** "Email-by-email categorization (future Phase 1)"

**Goal:** Apply approved categories and refined rules to classify every individual email in the corpus. Produce a complete categorization mapping (email_id -> category assignments with confidence).

**Depends on:** Phase 3 (rule engine provides the categorization mechanism)

### Architecture

```
src/categorizer/
  email_categorizer.py   - Main categorization engine
  conflict_resolver.py   - Handle multi-category assignments
  coverage_reporter.py   - Report uncategorized emails
src/models/
  categorization.py      - EmailCategorization, CategorizationReport models
```

### Work Items

#### 4.1 Categorization Data Model

**Files Affected:**
- `src/models/categorization.py` (NEW)

**What:**
- `EmailCategorization`: email_id, primary_category_id, secondary_categories (list), confidence, rule_ids_matched, categorized_date
- `CategorizationReport`: total_emails, categorized_count, uncategorized_count, multi_category_count, per_category_breakdown, coverage_percentage

---

#### 4.2 Email Categorizer

**Files Affected:**
- `src/categorizer/email_categorizer.py` (NEW)

**What:**
- `categorize_all(corpus, rules) -> List[EmailCategorization]` — apply rules to every email
- Batch processing with progress callback (for large corpora)
- Assign primary category (highest confidence match)
- Track secondary categories (other matches above minimum confidence)
- Flag emails matching zero rules as "uncategorized"

---

#### 4.3 Conflict Resolver

**Files Affected:**
- `src/categorizer/conflict_resolver.py` (NEW)

**What:**
- When an email matches multiple categories with similar confidence, resolve using:
  1. Rule priority (user-assigned)
  2. Condition specificity (more conditions = more specific = higher priority)
  3. Historical user decisions (from learning system)
- Present ambiguous cases to user for manual resolution via TUI
- Learn from manual resolutions (feed back to pattern_detector)

---

#### 4.4 Coverage Reporter

**Files Affected:**
- `src/categorizer/coverage_reporter.py` (NEW)

**What:**
- Report categorization coverage: what percentage of emails are categorized
- Identify common patterns in uncategorized emails (suggest new categories or rule additions)
- Compare rule-based categorization against original cluster assignments
- Export categorization summary (per-category email lists, uncategorized list)

---

#### 4.5 CLI Integration

**Files Affected:**
- `src/cli/commands/categorize.py` (NEW)
- `src/cli/__init__.py`

**What:**
- `python -m src.cli categorize` — run categorization against corpus
- `python -m src.cli categorize --report` — coverage report only
- `python -m src.cli categorize --resolve` — interactive conflict resolution
- `python -m src.cli categorize --dry-run` — preview without saving
- Output: `categorized_emails.json` (email_id -> category mapping)

---

## Phase 5: Email Filtering & Moving

**Original out-of-scope item:** "Email filtering or moving (future)"

**Goal:** Apply categorization results to the live mailbox — create server-side rules, move emails into folders, and apply labels/tags via Graph API and Gmail API.

**Depends on:** Phase 4 (categorization provides the email -> category mapping)

### Architecture

```
src/actions/
  folder_manager.py    - Create/manage mailbox folders
  email_mover.py       - Move emails to categorized folders
  rule_deployer.py     - Deploy server-side rules to M365/Gmail
  action_logger.py     - Audit trail of all mailbox modifications
```

### Work Items

#### 5.1 Folder Manager

**Files Affected:**
- `src/actions/folder_manager.py` (NEW)

**What:**
- `create_folder_structure(categories) -> Dict[category_id, folder_id]` — create mailbox folders matching category hierarchy
- M365: Graph API `/me/mailFolders` POST for folder creation
- Gmail: Labels API for label creation
- Handle existing folders (match by name, don't duplicate)
- Dry-run mode: show what folders would be created without creating them
- Support nested folders for hierarchical categories

---

#### 5.2 Email Mover

**Files Affected:**
- `src/actions/email_mover.py` (NEW)

**What:**
- `move_emails(categorization, folder_map) -> MoveReport` — move emails to category folders
- Batch operations (Graph API supports batch requests, max 20 per batch)
- Gmail: batch modify with label add/remove
- Progress callback for large moves
- Rollback support: track original folder for every moved email
- Skip already-categorized emails (idempotent)
- Error handling: continue on individual failures, report summary

---

#### 5.3 Rule Deployer

**Files Affected:**
- `src/actions/rule_deployer.py` (NEW)

**What:**
- Convert CategoryRules to server-side inbox rules
- M365: Graph API `/me/mailFolders/inbox/messageRules` POST
- Gmail: Filters API (already have export format — extend to live deployment)
- Validate rules before deployment (server-side rule limits, condition support)
- Dry-run mode: show rules that would be created
- Conflict detection: warn if new rules overlap with existing server-side rules

---

#### 5.4 Action Logger

**Files Affected:**
- `src/actions/action_logger.py` (NEW)

**What:**
- Append-only JSONL log of all mailbox modifications
- Fields: timestamp, action_type (move/label/rule_create), email_id, source_folder, target_folder, rule_id, success/failure
- Support rollback by replaying log in reverse
- Stored at `~/.email-analyzer/actions.jsonl`

---

#### 5.5 CLI Integration

**Files Affected:**
- `src/cli/commands/apply.py` (NEW)
- `src/cli/__init__.py`

**What:**
- `python -m src.cli apply --dry-run` — preview all mailbox changes
- `python -m src.cli apply folders` — create folder structure only
- `python -m src.cli apply move` — move emails into folders
- `python -m src.cli apply rules` — deploy server-side rules
- `python -m src.cli apply --rollback` — undo last apply operation
- Mandatory confirmation prompt before any mailbox modification
- `--source hotmail|gmail|both` flag support

---

## Phase 6: Automated Processing & Real-Time Monitoring

**Original out-of-scope items:** "Automated daily processing (future)" and "Real-time email monitoring (future)"

**Goal:** Enable scheduled re-extraction and incremental analysis so categories stay current as new email arrives. Detect when new patterns emerge that don't fit existing categories.

**Depends on:** Phase 5 (automated processing needs the full categorize -> apply pipeline)

### Architecture

```
src/scheduler/
  scheduler.py         - Cron-like scheduling for re-extraction
  incremental.py       - Incremental extraction and analysis
  change_detector.py   - Detect new patterns and category drift
  notification.py      - Alert user when action needed
```

### Work Items

#### 6.1 Incremental Processing Engine

**Files Affected:**
- `src/scheduler/incremental.py` (NEW)

**What:**
- `incremental_extract(last_run_date) -> List[Email]` — extract only emails since last run
- `incremental_analyze(new_emails, existing_analysis) -> AnalysisDelta` — analyze new emails against existing clusters
- Assign new emails to existing clusters (nearest centroid assignment without re-clustering)
- Detect when new emails form a distinct new cluster (distance from all centroids exceeds threshold)
- Update corpus file incrementally (append, don't re-extract)
- Update embeddings cache incrementally

---

#### 6.2 Change Detector

**Files Affected:**
- `src/scheduler/change_detector.py` (NEW)

**What:**
- `detect_changes(old_analysis, new_analysis) -> List[Change]` — identify significant shifts
- Track: new sender patterns, emerging topics, volume spikes, category drift
- Alert thresholds: new cluster forming (>10 emails not matching existing categories), sender frequency change (daily -> weekly), volume anomaly (2x normal)
- Store change history for trend analysis

---

#### 6.3 Scheduler

**Files Affected:**
- `src/scheduler/scheduler.py` (NEW)

**What:**
- Schedule periodic extraction + analysis (configurable interval, default daily)
- Platform-aware: Windows Task Scheduler integration, Unix cron generation
- `python -m src.cli schedule setup --interval daily` — create scheduled task
- `python -m src.cli schedule run` — manual trigger of scheduled pipeline
- `python -m src.cli schedule status` — show last run, next run, run history
- `python -m src.cli schedule disable` — remove scheduled task
- Auth token refresh handling (MSAL tokens expire, need re-auth flow)

---

#### 6.4 Notification System

**Files Affected:**
- `src/scheduler/notification.py` (NEW)

**What:**
- Alert user when automated processing detects actionable changes:
  - New category candidate detected (cluster of uncategorized emails)
  - Existing category drifting (match rate dropping)
  - New high-volume sender detected
  - Rule coverage dropping below threshold
- Notification channels: console output on next CLI run, optional desktop notification (Windows toast / macOS notification center)
- Notification stored in `~/.email-analyzer/notifications.jsonl`
- `python -m src.cli notifications` — show pending notifications
- `python -m src.cli notifications clear` — mark all as read

---

#### 6.5 Configuration Extensions

**Files Affected:**
- `src/config/models.py`
- `src/config/loader.py`

**What:**
- Add scheduler config section:
  ```yaml
  scheduler:
    enabled: true
    interval: daily          # daily, weekly, custom cron
    time: "02:00"            # run at 2 AM
    auto_categorize: false   # auto-apply rules to new emails
    notification_threshold: 10  # min new uncategorized emails to alert
  ```
- Add monitoring config section:
  ```yaml
  monitoring:
    drift_threshold: 0.15   # category match rate drop to trigger alert
    new_cluster_threshold: 10  # min emails to suggest new category
    volume_anomaly_factor: 2.0  # multiplier over average to flag
  ```

---

## Cross-Phase Dependencies

```
Phase 1 (TUI Polish) ──────────────┐
                                    ├── Phase 2 (TUI Advanced)
Phase 3 (Rule Refinement) ─────────┤
                                    ├── Phase 4 (Email Categorization)
                                    │
                                    └── Phase 5 (Filtering & Moving)
                                                │
                                                └── Phase 6 (Automation & Monitoring)
```

Phases 1 and 3 can run in parallel (no dependencies between them).
Phases 2 and 4 can overlap once their respective prerequisites complete.

---

## Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| Graph API rate limits during bulk email moves (Phase 5) | Batch requests (max 20), exponential backoff, configurable throttle |
| OAuth token expiry during scheduled runs (Phase 6) | MSAL token cache with refresh, re-auth notification if refresh fails |
| Undo complexity for merge operations (Phase 2) | Store full pre-merge state snapshot, not just delta |
| Rule conflicts with existing server-side rules (Phase 5) | Pre-deployment conflict check, dry-run mode mandatory for first deploy |
| Large corpus performance for real-time categorization (Phase 4) | Incremental processing, avoid full re-clustering, use cached embeddings |
| Cross-platform scheduler compatibility (Phase 6) | Abstract scheduler interface, Windows/Unix implementations |

---

## Testing Strategy

Each phase follows the project's TDD constitution:

1. **Contract tests** written first for new modules (rule_engine, categorizer, folder_manager, scheduler)
2. **Unit tests** for all business logic with mocked dependencies
3. **Integration tests** for API interactions with recorded responses (VCR pattern)
4. **TUI tests** using Textual's built-in test framework (`async with app.run_test()`)
5. **Coverage floor**: maintain 85%+ across all new code

---

## CLI Command Summary (All Phases)

| Command | Phase | Description |
|---------|-------|-------------|
| `rules generate` | 3 | Auto-generate rules from approved categories |
| `rules test` | 3 | Dry-run rules against corpus |
| `rules show` | 3 | Display current rules |
| `rules edit` | 3 | Interactive rule editing (TUI) |
| `categorize` | 4 | Run categorization against corpus |
| `categorize --report` | 4 | Coverage report |
| `categorize --resolve` | 4 | Interactive conflict resolution |
| `apply --dry-run` | 5 | Preview mailbox changes |
| `apply folders` | 5 | Create folder structure |
| `apply move` | 5 | Move emails into folders |
| `apply rules` | 5 | Deploy server-side rules |
| `apply --rollback` | 5 | Undo last apply operation |
| `schedule setup` | 6 | Create scheduled task |
| `schedule run` | 6 | Manual trigger |
| `schedule status` | 6 | Show schedule info |
| `notifications` | 6 | Show pending alerts |

---

*Plan generated 2026-02-28*
