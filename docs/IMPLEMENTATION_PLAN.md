# Email Corpus Analyzer - Implementation Plan

> **Document Purpose**: Detailed, phased implementation plan for improvements documented in `IMPROVEMENT_RECOMMENDATIONS.md`. Each phase is scoped to ~100,000 tokens including implementation, testing, and fixes.
>
> **Methodology**: TDD per constitution. Tests first, then implementation.

---

## Overview

| Phase | Focus | Estimated Tokens | Parallelizable Tracks | Status |
|-------|-------|------------------|----------------------|--------|
| 1 | Foundation & Quick Wins | ~80,000 | 3 tracks | ✅ Complete |
| 2 | Core Quality Improvements | ~95,000 | 2 tracks | ✅ Complete |
| 3 | Rich User Interface | ~90,000 | 2 tracks | ✅ Complete |
| 4 | Advanced Features | ~85,000 | 2 tracks | ✅ Complete |
| 5 | Extensibility & Polish | ~75,000 | 3 tracks | ✅ Complete |
| 6 | Data Resilience | ~7,000 | 1 track | ✅ Complete |

**Total Estimated**: ~432,000 tokens across 6 phases
**Progress**: 6/6 phases complete (1968+ tests, 86% coverage)

---

## Phase 1: Foundation & Quick Wins ✅ COMPLETE

**Goal**: Establish configuration system, improve CLI ergonomics, implement quick wins.

**Duration Estimate**: ~80,000 tokens

**Status**: ✅ Completed on 2025-01-14 (635 tests passing, 93% coverage)

### Track 1A: Configuration System (35,000 tokens) ✅

Sequential tasks - each builds on previous.

#### Task 1A.1: Configuration Data Model ✅
**Effort**: 8,000 tokens | **Dependencies**: None

Create Pydantic models for configuration:

```
Files created:
- src/config/__init__.py
- src/config/models.py
- tests/unit/test_config_models.py (37 tests)
```

**Acceptance Criteria**:
- [x] `AppConfig` model with all CLI options as fields
- [x] Nested models: `ExtractConfig`, `AnalyzeConfig`, `SuggestConfig`, `ReviewConfig`
- [x] Validation rules matching existing CLI constraints
- [x] Default values matching current CLI defaults
- [x] 100% test coverage for validation edge cases

**Test Cases**:
```python
def test_config_default_values():
    """Config should have sensible defaults."""

def test_config_validates_num_clusters_positive():
    """num_clusters must be >= 1."""

def test_config_validates_min_sender_count():
    """min_sender_count must be >= 1."""

def test_config_path_expansion():
    """~ in paths should expand to home directory."""
```

---

#### Task 1A.2: Configuration File Loader ✅
**Effort**: 12,000 tokens | **Dependencies**: 1A.1

Implement YAML loading with resolution order:

```
Files created:
- src/config/loader.py
- tests/unit/test_config_loader.py (33 tests)

Files modified:
- pyproject.toml (added pyyaml>=6.0.0 dependency)
```

**Acceptance Criteria**:
- [x] Load from `~/.config/email-analyzer/config.yaml` (global)
- [x] Load from `./.email-analyzer.yaml` (project)
- [x] Merge configs with correct precedence (project > global > defaults)
- [x] Handle missing files gracefully (use defaults)
- [x] Validate loaded config against models
- [x] Clear error messages for invalid YAML

**Test Cases**:
```python
def test_loader_missing_files_returns_defaults():
    """Missing config files should return default config."""

def test_loader_project_overrides_global():
    """Project config values override global config."""

def test_loader_invalid_yaml_raises_clear_error():
    """Invalid YAML should raise ConfigError with line number."""

def test_loader_unknown_keys_warns():
    """Unknown config keys should log warning but not fail."""
```

---

#### Task 1A.3: CLI Integration ✅
**Effort**: 10,000 tokens | **Dependencies**: 1A.2

Integrate config loading into CLI with argument override:

```
Files modified:
- src/cli.py
- tests/unit/test_cli.py
```

**Acceptance Criteria**:
- [x] Config loaded at startup before command dispatch
- [x] CLI arguments override config file values
- [x] Add `--config` flag for custom config path
- [x] Add `config init` subcommand to generate template
- [x] Add `config show` subcommand to display resolved config
- [x] Backward compatible (all existing args still work)

**Test Cases**:
```python
def test_cli_args_override_config_file():
    """CLI --num-clusters should override config file value."""

def test_cli_config_flag_loads_custom_path():
    """--config path/to/config.yaml should load that file."""

def test_config_init_creates_template():
    """config init should create template config file."""

def test_config_show_displays_resolved():
    """config show should display merged configuration."""
```

---

#### Task 1A.4: Config Documentation & Template ✅
**Effort**: 5,000 tokens | **Dependencies**: 1A.3

```
Files created:
- src/config/template.yaml (embedded default template with inline documentation)
```

**Acceptance Criteria**:
- [x] Template file with all options documented inline
- [x] Template generated via `config init` command
- [x] Example configs available via template

---

### Track 1B: Quick Wins (25,000 tokens) ✅

Independent tasks - can run in parallel.

#### Task 1B.1: Add --quiet Flag ✅
**Effort**: 3,000 tokens | **Dependencies**: None

```
Files modified:
- src/cli.py
- tests/unit/test_cli.py
```

**Acceptance Criteria**:
- [x] `--quiet` / `-q` flag suppresses INFO output
- [x] Only errors and warnings shown in quiet mode
- [x] Works with all commands

---

#### Task 1B.2: Add --json Output Flag ✅
**Effort**: 5,000 tokens | **Dependencies**: None

```
Files modified:
- src/cli.py
- tests/unit/test_cli.py
```

**Acceptance Criteria**:
- [x] `--json` flag outputs machine-readable JSON
- [x] JSON output includes status, timing, file paths
- [x] Works with all commands
- [x] Mutually exclusive with `--verbose`

**Output Format**:
```json
{
  "command": "analyze",
  "status": "success",
  "duration_seconds": 234.5,
  "output_file": "/path/to/analysis.json",
  "stats": {
    "emails_analyzed": 5432,
    "clusters_generated": 10
  }
}
```

---

#### Task 1B.3: Add info Command ✅
**Effort**: 6,000 tokens | **Dependencies**: None

```
Files modified:
- src/cli.py
- tests/unit/test_cli.py
```

**Acceptance Criteria**:
- [x] `info` command shows corpus statistics
- [x] Shows: email count, date range, unique senders, file sizes
- [x] Works without full corpus load (read metadata only)
- [x] Supports `--json` output

**Example Output**:
```
Corpus Information
──────────────────────────────────────
File:           ~/data/outputs/email_corpus.json
Size:           45.2 MB
Emails:         5,432
Date Range:     2023-01-15 to 2025-01-14 (730 days)
Unique Senders: 847
Unique Domains: 312

Analysis Status: Available (2025-01-14)
Categories:      18 suggested, 15 approved
```

---

#### Task 1B.4: Add --skip-review Flag ✅
**Effort**: 4,000 tokens | **Dependencies**: None

```
Files modified:
- src/cli.py
- tests/unit/test_cli.py
```

**Acceptance Criteria**:
- [x] `pipeline --skip-review` skips interactive review
- [x] Auto-accepts all suggestions
- [x] Useful for automation/CI

---

#### Task 1B.5: Email Validation & Early Feedback ✅
**Effort**: 4,000 tokens | **Dependencies**: None

```
Files modified:
- src/cli.py
- tests/unit/test_cli.py
```

**Acceptance Criteria**:
- [x] Validate email format before starting extraction
- [x] Clear error message for invalid email format
- [x] Supports JSON output for errors

---

#### Task 1B.6: Add --version Flag ✅
**Effort**: 2,000 tokens | **Dependencies**: None

```
Files modified:
- src/cli.py
- src/__init__.py (added __version__ = "0.1.0")
- tests/unit/test_cli.py
```

**Acceptance Criteria**:
- [x] `--version` shows version number
- [x] Version sourced from single location (src/__init__.py)

---

### Track 1C: Dry-Run Mode (20,000 tokens) ✅

#### Task 1C.1: Dry-Run Infrastructure ✅
**Effort**: 8,000 tokens | **Dependencies**: None

```
Files created:
- src/preview/__init__.py
- src/preview/estimators.py
- tests/unit/test_preview.py (36 tests)
```

**Acceptance Criteria**:
- [x] `Estimator` classes for each command (ExtractEstimator, AnalyzeEstimator, SuggestEstimator, ReviewEstimator, PipelineEstimator)
- [x] Estimate extraction count (from API metadata if available)
- [x] Estimate analysis time based on corpus size
- [x] Estimate output file sizes

---

#### Task 1C.2: Dry-Run CLI Integration ✅
**Effort**: 12,000 tokens | **Dependencies**: 1C.1

```
Files modified:
- src/cli.py
- tests/unit/test_cli.py
```

**Acceptance Criteria**:
- [x] `--dry-run` / `-n` flag for all commands
- [x] Shows preview without executing
- [x] Reuses validation logic
- [x] Clear output distinguishing preview from execution

---

### Phase 1 Parallel Execution Plan ✅ COMPLETE

```
All tracks completed:
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│ Track 1A ✅     │  │ Track 1B ✅     │  │ Track 1C ✅     │
│ Config System   │  │ Quick Wins      │  │ Dry-Run Mode    │
├─────────────────┤  ├─────────────────┤  ├─────────────────┤
│ 1A.1 Models ✅  │  │ 1B.1 --quiet ✅ │  │ 1C.1 Estimat ✅ │
│       ↓         │  │ 1B.2 --json ✅  │  │       ↓         │
│ 1A.2 Loader ✅  │  │ 1B.3 info ✅    │  │ 1C.2 CLI ✅     │
│       ↓         │  │ 1B.4 --skip ✅  │  └─────────────────┘
│ 1A.3 CLI ✅     │  │ 1B.5 valid ✅   │
│       ↓         │  │ 1B.6 --ver ✅   │
│ 1A.4 Docs ✅    │  └─────────────────┘
└─────────────────┘
```

---

## Phase 2: Core Quality Improvements ✅ COMPLETE

**Goal**: Improve categorization quality through better clustering and naming.

**Duration Estimate**: ~95,000 tokens

**Status**: ✅ Completed on 2025-01-14 (741 tests passing, 93% coverage)

### Track 2A: Intelligent Clustering (50,000 tokens) ✅

#### Task 2A.1: Cluster Optimizer - Elbow Method ✅
**Effort**: 12,000 tokens | **Dependencies**: None

```
Files created:
- src/analyzers/cluster_optimizer.py
- tests/unit/test_cluster_optimizer.py (28 tests)
```

**Acceptance Criteria**:
- [x] `ElbowOptimizer` class
- [x] Find optimal k using inertia curve
- [x] Implement knee/elbow detection algorithm
- [x] Return optimal k with confidence score
- [x] Configurable max_k parameter

**Test Cases**:
```python
def test_elbow_finds_clear_elbow():
    """Should find elbow in synthetic data with clear structure."""

def test_elbow_handles_no_clear_elbow():
    """Should return reasonable k when elbow is ambiguous."""

def test_elbow_respects_max_k():
    """Should not exceed max_k even if elbow suggests higher."""
```

---

#### Task 2A.2: Cluster Optimizer - Silhouette Method ✅
**Effort**: 12,000 tokens | **Dependencies**: None

```
Files modified:
- src/analyzers/cluster_optimizer.py
- tests/unit/test_cluster_optimizer.py
```

**Acceptance Criteria**:
- [x] `SilhouetteOptimizer` class
- [x] Find optimal k using silhouette score
- [x] Return per-cluster silhouette scores (for confidence)
- [x] Parallel evaluation of different k values
- [x] Progress callback for long optimizations

---

#### Task 2A.3: Auto-Cluster CLI Integration ✅
**Effort**: 10,000 tokens | **Dependencies**: 2A.1, 2A.2

```
Files modified:
- src/cli.py
- src/analyzers/__init__.py
- src/analyzers/semantic_analyzer.py
- tests/unit/test_cli.py
```

**Acceptance Criteria**:
- [x] `--auto-clusters` flag uses optimizer
- [x] `--cluster-method` flag: elbow, silhouette (default: silhouette)
- [x] Show optimization results before clustering
- [x] Cache optimization results for reuse
- [x] `--num-clusters` overrides auto-selection

---

#### Task 2A.4: Per-Cluster Quality Metrics ✅
**Effort**: 8,000 tokens | **Dependencies**: 2A.2

```
Files modified:
- src/models/content_cluster.py
- src/analyzers/semantic_analyzer.py
- tests/unit/test_analyzers.py
```

**Acceptance Criteria**:
- [x] Add `silhouette_score` field to ContentCluster
- [x] Add `cohesion_score` field (intra-cluster distance)
- [x] Calculate during clustering, not separately
- [x] Include in analysis results JSON

---

#### Task 2A.5: Cluster Analysis Report ✅
**Effort**: 8,000 tokens | **Dependencies**: 2A.3, 2A.4

```
Files modified:
- src/cli.py
```

**Acceptance Criteria**:
- [x] `analyze --cluster-analysis` shows k vs score table
- [x] Visual representation (ASCII chart) of elbow curve
- [x] Recommendation with explanation
- [x] Supports `--json` output

---

### Track 2B: Improved Category Naming (45,000 tokens) ✅

#### Task 2B.1: TF-IDF Name Generator ✅
**Effort**: 15,000 tokens | **Dependencies**: None

```
Files created:
- src/generators/name_generator.py
- tests/unit/test_name_generator.py (28 tests)
```

**Acceptance Criteria**:
- [x] `TfidfNameGenerator` class
- [x] Extract distinguishing terms using TF-IDF
- [x] Filter stop words and common terms
- [x] Generate 2-4 word descriptive names
- [x] Return confidence score for generated name

**Test Cases**:
```python
def test_tfidf_finds_distinguishing_terms():
    """Should identify terms unique to cluster vs corpus."""

def test_tfidf_filters_stop_words():
    """Should not include 'the', 'and', etc in names."""

def test_tfidf_handles_empty_cluster():
    """Should return 'Miscellaneous' for empty input."""

def test_tfidf_limits_name_length():
    """Names should be 2-4 words."""
```

---

#### Task 2B.2: Name Quality Scoring ✅
**Effort**: 10,000 tokens | **Dependencies**: 2B.1

```
Files modified:
- src/generators/name_generator.py
- tests/unit/test_name_generator.py
```

**Acceptance Criteria**:
- [x] `score_name_quality()` function
- [x] Penalize: too short, too long, generic words, all caps
- [x] Reward: specific terms, proper nouns, action words
- [x] Return 0-1 score with component breakdown

**Scoring Criteria**:
```python
# Good names (score > 0.7):
#   "Amazon Order Confirmations"
#   "Weekly Team Updates"
#   "Bank Statement Alerts"

# Poor names (score < 0.4):
#   "Email Category"
#   "Miscellaneous"
#   "Related"
```

---

#### Task 2B.3: Generator Integration ✅
**Effort**: 12,000 tokens | **Dependencies**: 2B.1, 2B.2

```
Files modified:
- src/generators/category_generator.py
- src/models/category.py (added name_quality_score, needs_name_review fields)
- tests/unit/test_generators.py
```

**Acceptance Criteria**:
- [x] Replace `_generate_cluster_name` with TF-IDF generator
- [x] Include name quality score in Category model
- [x] Flag low-quality names for review
- [x] Backward compatible (same output format)

---

#### Task 2B.4: Expanded Template Library ✅
**Effort**: 8,000 tokens | **Dependencies**: None

```
Files modified:
- src/models/category_template.py (expanded from 6 to 18 templates)
- tests/unit/test_template_matcher.py (27 new tests)
```

**Acceptance Criteria**:
- [x] Expand from 6 to 18 templates
- [x] Added: Work, Healthcare, Education, Entertainment, Government, Utilities, Real Estate, Insurance, Food, Fitness, Charity, Jobs
- [x] Enhanced keyword lists for existing templates (15-20 keywords each)
- [x] More domains per template (10-20 domains each)

---

### Phase 2 Parallel Execution Plan ✅ COMPLETE

```
All tracks completed:
┌─────────────────────────┐  ┌─────────────────────────┐
│ Track 2A ✅             │  │ Track 2B ✅             │
│ Intelligent Clustering  │  │ Improved Naming         │
├─────────────────────────┤  ├─────────────────────────┤
│ 2A.1 Elbow Method ✅    │  │ 2B.1 TF-IDF Gen ✅      │
│ 2A.2 Silhouette ✅      │  │        ↓                │
│        ↓                │  │ 2B.2 Quality ✅         │
│ 2A.3 CLI Integration ✅ │  │        ↓                │
│        ↓                │  │ 2B.3 Integration ✅     │
│ 2A.4 Quality Metrics ✅ │  │                         │
│        ↓                │  │ 2B.4 Templates ✅       │
│ 2A.5 Analysis Report ✅ │  │                         │
└─────────────────────────┘  └─────────────────────────┘
```

---

## Phase 3: Rich User Interface ✅ COMPLETE

**Goal**: Replace basic CLI review with modern TUI.

**Duration Estimate**: ~90,000 tokens

**Status**: ✅ Completed on 2025-01-14 (889 tests passing, 86% coverage)

### Track 3A: TUI Foundation (50,000 tokens) ✅

#### Task 3A.1: TUI Infrastructure Setup ✅
**Effort**: 10,000 tokens | **Dependencies**: None

```
Files created:
- src/ui/tui/__init__.py
- src/ui/tui/app.py (ReviewApp class)
- src/ui/tui/theme.py
- tests/unit/test_tui_app.py (32 tests)

Files modified:
- pyproject.toml (added textual>=0.50.0)
```

**Acceptance Criteria**:
- [x] `ReviewApp` Textual application class
- [x] Theme configuration (colors, styles)
- [x] Basic app lifecycle (start, stop)
- [x] Keyboard binding infrastructure

---

#### Task 3A.2: Category Table Component ✅
**Effort**: 15,000 tokens | **Dependencies**: 3A.1

```
Files created:
- src/ui/tui/widgets/__init__.py
- src/ui/tui/widgets/category_table.py
- tests/unit/test_tui_widgets.py (46 tests)
```

**Acceptance Criteria**:
- [x] Scrollable table of categories
- [x] Columns: index, name, confidence (bar), email count, source
- [x] Row selection with highlight
- [x] Keyboard navigation (j/k, arrows)
- [x] Color-coded confidence (red/yellow/green)

---

#### Task 3A.3: Category Detail Panel ✅
**Effort**: 12,000 tokens | **Dependencies**: 3A.1

```
Files created:
- src/ui/tui/widgets/detail_panel.py
```

**Acceptance Criteria**:
- [x] Shows selected category details
- [x] Sample emails (sender, subject)
- [x] Distinguishing features
- [x] Confidence breakdown
- [x] Collapsible/expandable

---

#### Task 3A.4: Action Bar & Commands ✅
**Effort**: 13,000 tokens | **Dependencies**: 3A.2, 3A.3

```
Files created:
- src/ui/tui/widgets/action_bar.py
- src/ui/tui/commands.py
```

**Acceptance Criteria**:
- [x] Action bar showing available commands
- [x] Keyboard shortcuts: A(ccept), R(ename), M(erge), D(elete), S(kip)
- [x] Modal dialogs for rename, merge selection
- [x] Help overlay (? key)
- [x] Quit confirmation

---

### Track 3B: TUI Features (40,000 tokens) ✅

#### Task 3B.1: Progress & Statistics ✅
**Effort**: 10,000 tokens | **Dependencies**: 3A.1

```
Files created:
- src/ui/tui/widgets/progress_bar.py
- src/ui/tui/widgets/stats_panel.py
- tests/unit/test_tui_progress_stats.py (30 tests)
```

**Acceptance Criteria**:
- [x] Progress bar: reviewed/total
- [x] Session statistics: accepted, renamed, merged, deleted
- [x] Real-time updates

---

#### Task 3B.2: Rename Dialog ✅
**Effort**: 8,000 tokens | **Dependencies**: 3A.4

```
Files created:
- src/ui/tui/dialogs/__init__.py
- src/ui/tui/dialogs/rename_dialog.py
- tests/unit/test_tui_dialogs.py (24 tests)
```

**Acceptance Criteria**:
- [x] Modal text input dialog
- [x] Show current name
- [x] Validation (non-empty, reasonable length)
- [x] Cancel/confirm with keyboard

---

#### Task 3B.3: Merge Selection Dialog ✅
**Effort**: 10,000 tokens | **Dependencies**: 3A.4

```
Files created:
- src/ui/tui/dialogs/merge_dialog.py
```

**Acceptance Criteria**:
- [x] Show list of approved categories
- [x] Selection with keyboard
- [x] Preview merged result
- [x] Cancel/confirm

---

#### Task 3B.4: CLI Integration & Fallback ✅
**Effort**: 12,000 tokens | **Dependencies**: 3A.*, 3B.*

```
Files modified:
- src/cli.py (added --no-tui, --headless flags)
- src/ui/category_review.py (added TUI integration)
- tests/unit/test_cli_tui_integration.py (16 tests)
```

**Acceptance Criteria**:
- [x] TUI is default for `review` command
- [x] `--no-tui` flag for legacy CLI interface
- [x] `--headless` flag for automation (accept all)
- [x] Graceful fallback if terminal doesn't support TUI

---

### Phase 3 Parallel Execution Plan ✅ COMPLETE

```
All tracks completed:
┌─────────────────────────┐  ┌─────────────────────────┐
│ Track 3A ✅             │  │ Track 3B ✅             │
│ TUI Foundation          │  │ TUI Features            │
├─────────────────────────┤  ├─────────────────────────┤
│ 3A.1 Infrastructure ✅  │  │                         │
│        ↓                │  │        ↓                │
│ 3A.2 Category Table ✅  │  │ 3B.1 Progress/Stats ✅  │
│ 3A.3 Detail Panel ✅    │  │ 3B.2 Rename Dialog ✅   │
│        ↓                │  │ 3B.3 Merge Dialog ✅    │
│ 3A.4 Action Bar ✅      │  │        ↓                │
│                         │  │ 3B.4 CLI Integration ✅ │
└─────────────────────────┘  └─────────────────────────┘
```

---

## Phase 4: Advanced Features ✅ COMPLETE

**Goal**: Add hierarchical categories and incremental processing.

**Duration Estimate**: ~85,000 tokens

**Status**: ✅ Completed on 2025-01-14 (999 tests passing, 84% coverage)

### Track 4A: Hierarchical Categories (45,000 tokens) ✅

#### Task 4A.1: Hierarchical Data Model ✅
**Effort**: 10,000 tokens | **Dependencies**: None

```
Files modified:
- src/models/category.py (added hierarchical fields)
- tests/unit/test_models.py (21 tests)
```

**Acceptance Criteria**:
- [x] Add `parent_category_id: str | None` field
- [x] Add `level: int` field (0=top, 1=sub, etc)
- [x] Add `subcategories: list[Category]` for tree view
- [x] Helper properties: is_top_level, has_children, children_count
- [x] Backward compatible (existing categories work)

---

#### Task 4A.2: Hierarchical Clustering ✅
**Effort**: 18,000 tokens | **Dependencies**: 4A.1

```
Files created:
- src/analyzers/hierarchical_analyzer.py (HierarchicalAnalyzer class)
- tests/unit/test_hierarchical_analyzer.py (23 tests)
```

**Acceptance Criteria**:
- [x] Use scipy agglomerative clustering (ward linkage)
- [x] Generate 2-level hierarchy
- [x] Level 0: 5-10 broad categories (configurable)
- [x] Level 1: 2-5 subcategories per parent (configurable)
- [x] Optimal cut point selection
- [x] Preserve flat clustering as fallback

---

#### Task 4A.3: Hierarchy-Aware Category Generator ✅
**Effort**: 12,000 tokens | **Dependencies**: 4A.1, 4A.2

```
Files modified:
- src/generators/category_generator.py (added generate_hierarchical_suggestions)
- tests/unit/test_generators.py (68 tests total)
```

**Acceptance Criteria**:
- [x] Generate hierarchical suggestions
- [x] Parent names are broad (e.g., "Shopping")
- [x] Child names are specific (e.g., "Amazon Orders")
- [x] Templates match at appropriate level

---

#### Task 4A.4: Hierarchical Review UI ✅
**Effort**: 8,000 tokens | **Dependencies**: 4A.1, Phase 3

```
Files modified:
- src/ui/tui/widgets/category_table.py (tree view support)
- tests/unit/test_tui_widgets.py
```

**Acceptance Criteria**:
- [x] Tree view in TUI with indentation
- [x] Expand/collapse with +/- indicators
- [x] Actions apply to selected level
- [x] Promote subcategory to top-level
- [x] Demote top-level to subcategory

---

### Track 4B: Incremental Processing (40,000 tokens) ✅

#### Task 4B.1: Extraction Metadata Enhancement ✅
**Effort**: 8,000 tokens | **Dependencies**: None

```
Files modified:
- src/models/corpus.py (added metadata fields)
- src/extractors/m365_extractor.py (populate metadata)
- tests/unit/test_extractors.py
```

**Acceptance Criteria**:
- [x] Add `last_extraction_date` to CorpusMetadata
- [x] Add `email_ids_hash` for change detection
- [x] Update metadata on each extraction
- [x] Store extraction parameters used

---

#### Task 4B.2: Incremental Extraction ✅
**Effort**: 15,000 tokens | **Dependencies**: 4B.1

```
Files modified:
- src/extractors/m365_extractor.py (extract_incremental method)
- src/cli.py (--since-last flag)
- tests/unit/test_extractors.py
```

**Acceptance Criteria**:
- [x] `--since-last` flag for incremental extraction
- [x] Fetch only emails after last_extraction_date
- [x] Merge new emails into existing corpus
- [x] Deduplication by Message-ID
- [x] Update metadata with new totals
- [x] Report: "Added X new emails (Y → Z total)"

---

#### Task 4B.3: Embedding Cache ✅
**Effort**: 12,000 tokens | **Dependencies**: None

```
Files created:
- src/cache/__init__.py
- src/cache/embedding_cache.py (EmbeddingCache class)
- tests/unit/test_embedding_cache.py (27 tests)
```

**Acceptance Criteria**:
- [x] Store embeddings: `embeddings_cache.npz`
- [x] Map email ID → embedding index
- [x] Load/save efficiently (numpy compressed)
- [x] Invalidation when email deleted
- [x] Cache statistics (hit rate)

---

#### Task 4B.4: Incremental Analysis ✅
**Effort**: 10,000 tokens | **Dependencies**: 4B.2, 4B.3

```
Files modified:
- src/analyzers/semantic_analyzer.py (analyze_incremental method)
- src/analyzers/__init__.py (run_full_analysis_incremental)
- src/cli.py (--incremental flag)
- tests/unit/test_analyzers.py
```

**Acceptance Criteria**:
- [x] `--incremental` flag for analyze command
- [x] Load cached embeddings for existing emails
- [x] Generate embeddings only for new emails
- [x] Merge and re-cluster
- [x] Update cache with new embeddings
- [x] Report: "Generated X new embeddings, used Y cached"

---

### Phase 4 Parallel Execution Plan ✅ COMPLETE

```
All tracks completed:
┌─────────────────────────┐  ┌─────────────────────────┐
│ Track 4A ✅             │  │ Track 4B ✅             │
│ Hierarchical Categories │  │ Incremental Processing  │
├─────────────────────────┤  ├─────────────────────────┤
│ 4A.1 Data Model ✅      │  │ 4B.1 Metadata ✅        │
│        ↓                │  │        ↓                │
│ 4A.2 Clustering ✅      │  │ 4B.2 Incr Extract ✅    │
│        ↓                │  │                         │
│ 4A.3 Generator ✅       │  │ 4B.3 Embed Cache ✅     │
│        ↓                │  │        ↓                │
│ 4A.4 Review UI ✅       │  │ 4B.4 Incr Analyze ✅    │
└─────────────────────────┘  └─────────────────────────┘
```

---

## Phase 5: Extensibility & Polish ✅ COMPLETE

**Goal**: Refined confidence scoring, feedback learning, export formats.

**Duration Estimate**: ~75,000 tokens

**Status**: ✅ Completed on 2025-01-14 (1144 tests passing, 84% coverage)

### Track 5A: Confidence Refinement (25,000 tokens) ✅

#### Task 5A.1: Enhanced Confidence Model ✅
**Effort**: 12,000 tokens | **Dependencies**: Phase 2 (quality metrics)

```
Files modified:
- src/generators/confidence_scorer.py (ConfidenceWeights, calculate_confidence_enhanced)
- src/models/category.py (added confidence_breakdown field)
- tests/unit/test_confidence_scorer.py (39 tests)
```

**Acceptance Criteria**:
- [x] New confidence formula with weighted factors
- [x] Include: cohesion, volume, source, percentage, name quality, distinctiveness
- [x] Store component scores in Category
- [x] Configurable weights via ConfidenceWeights dataclass

---

#### Task 5A.2: Distinctiveness Scoring ✅
**Effort**: 8,000 tokens | **Dependencies**: 5A.1

```
Files modified:
- src/generators/confidence_scorer.py
- tests/unit/test_confidence_scorer.py
```

**Acceptance Criteria**:
- [x] Calculate pairwise category overlap (Jaccard similarity)
- [x] Penalize high overlap categories
- [x] Flag potential merge candidates via find_merge_candidates()

---

#### Task 5A.3: Confidence Display in UI ✅
**Effort**: 5,000 tokens | **Dependencies**: 5A.1, Phase 3

```
Files modified:
- src/ui/tui/widgets/detail_panel.py
- src/ui/category_review.py
```

**Acceptance Criteria**:
- [x] Show confidence breakdown in detail panel
- [x] Explain each component score
- [x] Visual comparison (bars)

---

### Track 5B: Feedback Learning (30,000 tokens) ✅

#### Task 5B.1: Decision Logging ✅
**Effort**: 10,000 tokens | **Dependencies**: Phase 3

```
Files created:
- src/learning/__init__.py
- src/learning/decision_logger.py
- tests/unit/test_learning.py (31 tests)
```

**Acceptance Criteria**:
- [x] Log all review decisions to JSONL
- [x] Include: timestamp, category, action, context
- [x] Persistent storage: `~/.email-analyzer/decisions.jsonl`

---

#### Task 5B.2: Pattern Detection ✅
**Effort**: 12,000 tokens | **Dependencies**: 5B.1

```
Files created:
- src/learning/pattern_detector.py
- tests/unit/test_pattern_detector.py (27 tests)
```

**Acceptance Criteria**:
- [x] Identify recurring patterns (3+ occurrences)
- [x] Patterns: rename X→Y, merge X+Y, delete low-confidence, always accept
- [x] Return confidence score for each pattern

---

#### Task 5B.3: Apply Learned Preferences ✅
**Effort**: 8,000 tokens | **Dependencies**: 5B.2

```
Files modified:
- src/generators/category_generator.py
- src/ui/category_review.py
- src/cli.py (added --no-learning flag)
- tests/unit/test_generators.py
```

**Acceptance Criteria**:
- [x] Pre-apply high-confidence patterns
- [x] Show user what was auto-applied
- [x] Allow override/rejection
- [x] `--no-learning` flag to disable

---

### Track 5C: Export & Polish (20,000 tokens) ✅

#### Task 5C.1: CSV Export ✅
**Effort**: 6,000 tokens | **Dependencies**: None

```
Files created:
- src/exporters/__init__.py
- src/exporters/csv_exporter.py
- tests/unit/test_exporters.py (27 tests)
```

**Acceptance Criteria**:
- [x] Export categories to CSV
- [x] Columns: name, description, confidence, email_count, source, level, parent_name
- [x] Configurable delimiter
- [x] UTF-8 with BOM for Excel compatibility

---

#### Task 5C.2: HTML Report ✅
**Effort**: 10,000 tokens | **Dependencies**: None

```
Files created:
- src/exporters/html_exporter.py
- src/exporters/templates/report.html.j2
```

**Acceptance Criteria**:
- [x] Generate standalone HTML report
- [x] Category list with details
- [x] Charts: confidence distribution, source breakdown
- [x] Inline CSS (no external dependencies)

---

#### Task 5C.3: Export CLI Command ✅
**Effort**: 4,000 tokens | **Dependencies**: 5C.1, 5C.2

```
Files modified:
- src/cli.py (added export command)
- tests/unit/test_cli.py (16 tests)
```

**Acceptance Criteria**:
- [x] `export` command with `--format` flag
- [x] Supported formats: csv, html
- [x] `--output` flag for custom path

---

### Phase 5 Parallel Execution Plan ✅ COMPLETE

```
All tracks completed:
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│ Track 5A ✅     │  │ Track 5B ✅     │  │ Track 5C ✅     │
│ Confidence      │  │ Learning        │  │ Export          │
├─────────────────┤  ├─────────────────┤  ├─────────────────┤
│ 5A.1 Model ✅   │  │ 5B.1 Logging ✅ │  │ 5C.1 CSV ✅     │
│      ↓          │  │      ↓          │  │ 5C.2 HTML ✅    │
│ 5A.2 Distinct ✅│  │ 5B.2 Patterns ✅│  │      ↓          │
│      ↓          │  │      ↓          │  │ 5C.3 CLI ✅     │
│ 5A.3 UI ✅      │  │ 5B.3 Apply ✅   │  │                 │
└─────────────────┘  └─────────────────┘  └─────────────────┘
```

---

## Dependency Graph (Cross-Phase)

```
Phase 1                    Phase 2                Phase 3              Phase 4              Phase 5
────────────────────────────────────────────────────────────────────────────────────────────────────
1A Config ──────────────────────────────────────────────────────────────────────────────────────►
1B Quick Wins ──────────────────────────────────────────────────────────────────────────────────►
1C Dry-Run ─────────────────────────────────────────────────────────────────────────────────────►

                          2A Clustering ─────────────────────────────► 4A Hierarchical
                          2B Naming ─────────────────────────────────► 5A Confidence

                                               3A TUI Foundation ──► 4A.4 Hierarchy UI
                                               3B TUI Features ────► 5A.3 Confidence UI
                                                                   ► 5B.3 Learning UI

                                                                     4B Incremental ────────────►
                                                                                        5B Learning
                                                                                        5C Export
```

---

## Testing Strategy

### Unit Tests (Per Task)
- Write tests BEFORE implementation (TDD)
- Target 95%+ coverage for new code
- Mock external dependencies (M365, file system)
- Use fixtures from existing test suite

### Integration Tests (Per Phase)
- End-to-end workflow tests
- CLI command integration
- File I/O verification
- Performance benchmarks

### Manual Testing Checklist (Per Phase)
- [ ] All new CLI flags work
- [ ] Help text is accurate
- [ ] Error messages are clear
- [ ] Backward compatibility verified
- [ ] TUI renders correctly (Phase 3+)

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| TUI complexity (Phase 3) | Start with minimal viable TUI, iterate |
| Hierarchical clustering quality | Keep flat clustering as fallback |
| Embedding cache corruption | Validate cache integrity on load |
| Learning false positives | Require 3+ occurrences, user override |
| Performance with large corpora | Benchmark at 10k, 50k, 100k emails |

---

## Phase 6: Data Resilience ✅ COMPLETE

**Goal**: Accept technically-invalid email addresses from extracted data so spam/automated senders are preserved for classification and rule export.

**Duration Estimate**: ~7,000 tokens

**Status**: ✅ Completed on 2026-02-17

### Track 6A: Lenient Email Validation (Sequential)

#### Task 6.1: Lenient Email Validator in Email Model ✅
**Effort**: ~3,000 tokens | **Dependencies**: None

**Files modified**: `src/models/email.py`

Changes:
- Removed `EmailStr` import, added `field_validator` import
- Changed `sender_email: EmailStr` → `sender_email: str = Field(..., min_length=1)`
- Changed `recipient_email: EmailStr | None` → `recipient_email: str | None = None`
- Added `@field_validator("sender_email", "recipient_email", mode="before")` that:
  - Returns `None` for `None` input
  - Requires non-empty string containing `@`
  - Strips whitespace
  - Raises `ValueError` for strings without `@`

**Acceptance Criteria**:
- [x] `noreply@39._ecoenergi.online` accepted
- [x] `CloudNotify@---SyncServi...-MtO0.autoworkscoll.com` accepted
- [x] `""` (empty string) rejected
- [x] `"invalid-email-format"` (no @) rejected
- [x] `None` accepted for recipient_email, rejected for sender_email

#### Task 6.2: Lenient Email Validation in Sender Model ✅
**Effort**: ~1,000 tokens | **Dependencies**: 6.1

**Files modified**: `src/models/sender.py`

Changes:
- Removed `EmailStr` import
- Changed `email: EmailStr` → `email: str = Field(..., min_length=1)`

No validator needed — Sender objects are constructed from already-validated Email data.

**Acceptance Criteria**:
- [x] Sender model accepts any non-empty string
- [x] All existing Sender construction in analyzers continues to work

#### Task 6.3: Update Tests ✅
**Effort**: ~3,000 tokens | **Dependencies**: 6.1, 6.2

**Files modified**: `tests/unit/test_extractors.py`, `tests/unit/test_models.py`

Test updates:
1. Updated comment on `test_process_email_handles_missing_sender` to reflect lenient validator
2. `test_process_email_no_at_in_sender` — still passes (lenient validator raises `ValueError` for no-`@`)
3. Added `test_process_email_accepts_technically_invalid_addresses` — verifies real-world spam addresses produce valid Email objects
4. Added `TestEmailLenientValidation` class in test_models.py with 8 tests covering acceptance, rejection, None, and whitespace stripping

#### Task 6.4: Verification (No Changes Required) ✅
**Files verified but NOT modified**:
- `src/config/models.py` — `AppConfig.user_email: EmailStr | None` stays strict
- `src/models/corpus.py` — `CorpusMetadata.user_email: EmailStr` stays strict
- `tests/unit/test_cli.py` — CLI email validation tests unaffected
- `tests/integration/test_config.py` — Config email validation unaffected

---

## Success Metrics ✅

All phases complete - metrics achieved:
- [x] Configuration via file works seamlessly (YAML config with precedence: defaults < global < project < custom)
- [x] Auto-clustering produces better categories than fixed k=10 (Elbow & Silhouette methods with --auto-clusters)
- [x] Category names are descriptive without manual editing (TF-IDF name generator with quality scoring)
- [x] TUI review is faster and more pleasant (Textual-based TUI with keyboard shortcuts)
- [x] Incremental updates work for ongoing inbox management (--since-last extraction, --incremental analysis, embedding cache)
- [x] 84% test coverage maintained (1144 tests passing)

---

*Document Version: 3.0 - Phase 6 Added*
*Created: 2025-01-14*
*Phase 1-5 Completed: 2025-01-14*
*Phase 6 Completed: 2026-02-17*
*Related: IMPROVEMENT_RECOMMENDATIONS.md*
