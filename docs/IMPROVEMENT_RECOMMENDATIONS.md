# Email Corpus Analyzer - Improvement Recommendations

> **Document Purpose**: This document captures all recommended improvements to the Email Corpus Analyzer, organized by category with full context, rationale, and implementation guidance.
>
> **Related Documents**:
> - Implementation Plan: `docs/IMPLEMENTATION_PLAN.md`
> - Original Spec: `specs/001-use-the-document/spec.md`
> - Constitution: `.specify/memory/constitution.md`

---

## Table of Contents

1. [Usability Improvements](#1-usability-improvements)
2. [Output Quality Improvements](#2-output-quality-improvements)
3. [Architectural Improvements](#3-architectural-improvements)
4. [Quick Wins](#4-quick-wins)
5. [Priority Matrix](#5-priority-matrix)

---

## 1. Usability Improvements

### 1.1 Configuration File Support

**Priority**: High | **Effort**: Medium | **Impact**: High

#### Current State

All configuration must be passed via CLI arguments on every invocation:

```bash
python -m src.cli pipeline --user-email user@hotmail.com --num-clusters 15 --min-sender-count 10 --output-dir ~/analysis
```

**Location**: `src/cli.py:27-202` (argument parsing)

#### Problem

- Users must remember and re-type long command lines
- No persistence of preferences between sessions
- Difficult to share configurations across team members
- No environment-specific configurations (dev/prod)

#### Recommendation

Add support for a hierarchical configuration system:

1. **Global config**: `~/.config/email-analyzer/config.yaml`
2. **Project config**: `./.email-analyzer.yaml` (in working directory)
3. **CLI arguments**: Override any config value

**Proposed Config Structure**:
```yaml
# .email-analyzer.yaml
version: 1

# Default settings
user_email: user@hotmail.com
output_dir: ~/data/outputs

# Per-stage configuration
extract:
  batch_size: 500
  checkpoint_interval: 100

analyze:
  num_clusters: 15
  # auto_clusters: true  # Future: automatic cluster selection

suggest:
  min_cluster_percentage: 3.0
  min_sender_count: 10

review:
  auto_cleanup: false

# Custom templates (extends built-in)
custom_templates:
  - name: "Work Communications"
    keywords: ["meeting", "agenda", "standup", "sprint"]
    domains: ["company.com", "slack.com"]
    description: "Work-related communications"
```

**Resolution Order**: CLI args > project config > global config > defaults

#### Implementation Notes

- Use `pydantic-settings` for validation and loading
- Create `src/config/` module with `ConfigLoader` class
- Add `--config` flag to specify custom config path
- Add `config init` command to generate template config file
- Maintain backward compatibility (all args still work without config)

---

### 1.2 Rich Terminal UI for Category Review

**Priority**: High | **Effort**: High | **Impact**: Very High

#### Current State

The review interface uses basic `input()` prompts:

```python
# src/ui/category_review.py:143-144
choice = input("Your choice: ").strip().upper()
```

Output is plain text with minimal formatting:
```
--- Category 1 of 12 ---
Name: Financial & Banking
Description: Financial transactions, banking, and billing
Confidence: 85.0%
Emails: 234 (4.3% of inbox)

Options:
  [A] Accept this category
  [R] Rename category
  ...
```

#### Problems

1. **No visual hierarchy**: All text looks the same
2. **Single-item view**: Can't see multiple categories at once
3. **No keyboard navigation**: Must type letters for each action
4. **Poor comparison**: Hard to compare categories for merge decisions
5. **No color coding**: Confidence levels aren't visually distinguished
6. **No progress context**: Can't see overall progress easily

#### Recommendation

Replace basic CLI with `rich` + `textual` based TUI:

**Main Features**:
- **Dashboard view**: Show all categories in a scrollable table
- **Detail panel**: Expandable view with sample emails
- **Color coding**: Red/yellow/green for confidence levels
- **Keyboard navigation**: j/k (vim-style), arrow keys, Enter to select
- **Batch operations**: Select multiple categories for bulk actions
- **Side-by-side comparison**: For merge decisions
- **Progress indicator**: Shows current position and session stats

**Proposed Layout**:
```
┌─ Email Category Review ──────────────────────────────────────────────┐
│ Categories: 12 total | Reviewed: 5 | Remaining: 7                    │
├──────────────────────────────────────────────────────────────────────┤
│ # │ Category Name          │ Confidence │ Emails │ Source           │
│───┼────────────────────────┼────────────┼────────┼──────────────────│
│ ▶ │ Financial & Banking    │ ████████░░ │   234  │ template         │
│   │ Amazon Orders          │ ███████░░░ │   156  │ sender           │
│   │ Newsletter Cluster     │ █████░░░░░ │    89  │ cluster          │
│   │ ...                    │            │        │                  │
├──────────────────────────────────────────────────────────────────────┤
│ Sample Emails (3 of 234):                                            │
│   • From: chase.com - "Your statement is ready"                      │
│   • From: paypal.com - "Receipt for your payment"                    │
│   • From: venmo.com - "You paid $25.00"                              │
├──────────────────────────────────────────────────────────────────────┤
│ [A]ccept [R]ename [M]erge [D]elete [S]kip | [?] Help [Q]uit         │
└──────────────────────────────────────────────────────────────────────┘
```

#### Implementation Notes

- Add `rich` and `textual` to dependencies
- Create `src/ui/tui/` package with modular components
- Keep existing CLI as fallback (`--no-tui` flag)
- Support both mouse and keyboard input
- Add `--headless` mode for automation (no prompts, accept all)

---

### 1.3 Preview/Dry-Run Mode

**Priority**: Medium | **Effort**: Low | **Impact**: Medium

#### Current State

Commands execute immediately with no preview of what will happen.

#### Problem

- Users can't verify settings before long operations
- No way to estimate time/resources required
- Risk of overwriting existing files accidentally

#### Recommendation

Add `--dry-run` flag to all commands:

| Command | Dry-Run Output |
|---------|----------------|
| `extract --dry-run` | Shows: email count estimate, date range, output path, estimated size |
| `analyze --dry-run` | Shows: corpus stats, analyzers to run, cluster count, estimated time |
| `suggest --dry-run` | Shows: categories that would be generated (names only, no files saved) |
| `review --dry-run` | Shows: categories to review, estimated session time |
| `pipeline --dry-run` | Shows: full plan for all stages |

**Example Output**:
```
$ python -m src.cli analyze --dry-run

=== ANALYSIS PREVIEW (Dry Run) ===
Input corpus: ~/data/outputs/email_corpus.json
  - 5,432 emails
  - Date range: 2023-01-15 to 2025-01-14 (730 days)
  - Unique senders: 847

Analyzers to run:
  1. SenderAnalyzer     - ~2 seconds
  2. SubjectAnalyzer    - ~1 second
  3. SemanticAnalyzer   - ~3 minutes (loading model + embeddings)
  4. TemporalAnalyzer   - ~1 second
  5. VolumeAnalyzer     - <1 second

Estimated total time: 3-4 minutes
Output: ~/data/outputs/corpus_analysis_results.json

Run without --dry-run to execute.
```

#### Implementation Notes

- Add `--dry-run` / `-n` flag to argument parser
- Each `cmd_*` function checks flag and calls preview variant
- Preview functions reuse validation logic but skip writes
- Return structured data for machine-readable output (`--json --dry-run`)

---

### 1.4 Incremental/Delta Analysis

**Priority**: Medium | **Effort**: High | **Impact**: High

#### Current State

Every run re-extracts and re-analyzes the entire corpus from scratch.

**Location**: `src/extractors/m365_extractor.py` - always fetches all emails

#### Problem

- Inefficient for users with large inboxes who want regular updates
- Re-downloading thousands of emails wastes time and bandwidth
- Re-computing embeddings for unchanged emails wastes compute

#### Recommendation

**Phase 1 - Incremental Extraction**:
- Track last extraction timestamp in corpus metadata
- Add `extract --since-last` to fetch only new emails
- Merge new emails into existing corpus (deduplication by Message-ID)
- Update corpus metadata with new totals

**Phase 2 - Incremental Analysis**:
- Cache embeddings for analyzed emails (by email ID hash)
- On re-analysis, only compute embeddings for new emails
- Merge new embeddings with cached ones
- Re-run clustering on full embedding set (clustering itself is fast)

**Proposed Workflow**:
```bash
# Initial full extraction
python -m src.cli extract --user-email user@hotmail.com

# Later: incremental update
python -m src.cli extract --user-email user@hotmail.com --since-last
# Output: "Fetched 47 new emails (5,432 → 5,479 total)"

# Incremental analysis (uses cached embeddings)
python -m src.cli analyze --incremental
# Output: "Generated 47 new embeddings, using 5,432 cached"
```

#### Implementation Notes

- Add `last_extraction_date` to `CorpusMetadata` model
- Create embedding cache: `embeddings_cache.npz` (numpy compressed)
- Store email ID → embedding index mapping
- Handle deleted emails (mark as removed, don't re-fetch)
- Add `--full` flag to force complete re-extraction/analysis

---

### 1.5 Unified Progress Feedback System

**Priority**: Medium | **Effort**: Medium | **Impact**: Medium

#### Current State

Progress reporting is inconsistent:
- SemanticAnalyzer uses `show_progress_bar=True` via sentence-transformers
- Other analyzers use optional `progress_callback` (often unused)
- CLI stages print basic log messages

**Location**: `src/analyzers/semantic_analyzer.py:105-108`, `src/utils/progress.py`

#### Problem

- Users don't know how long operations will take
- No unified progress display across stages
- No summary statistics at completion

#### Recommendation

Create unified progress system using `rich.progress`:

**Features**:
- Multi-task progress bars (one per stage in pipeline)
- Estimated time remaining (ETA)
- Real-time statistics (emails/sec, errors)
- Final summary dashboard

**Proposed Display**:
```
Email Corpus Analyzer - Pipeline

[1/4] Extracting emails    ████████████████████████░░░░  80% │ 4,320/5,400 │ ETA: 45s
      Errors: 3 │ Rate: 120 emails/sec

[2/4] Analyzing corpus     ░░░░░░░░░░░░░░░░░░░░░░░░░░░░   0% │ Waiting...
[3/4] Generating categories ░░░░░░░░░░░░░░░░░░░░░░░░░░░░   0% │ Waiting...
[4/4] Review               ░░░░░░░░░░░░░░░░░░░░░░░░░░░░   0% │ Waiting...
```

**Completion Summary**:
```
═══════════════════════════════════════════════════════════
Pipeline Complete ✓
───────────────────────────────────────────────────────────
Stage              Duration    Status
───────────────────────────────────────────────────────────
Extraction         2m 15s      5,432 emails (12 errors)
Analysis           3m 42s      10 clusters generated
Suggestions        0.8s        18 categories
Review             5m 30s      15 approved, 2 merged, 1 deleted
───────────────────────────────────────────────────────────
Total duration: 12m 17s
Output: ~/data/outputs/approved_categories.json
═══════════════════════════════════════════════════════════
```

#### Implementation Notes

- Refactor `src/utils/progress.py` to use `rich.progress`
- Create `ProgressManager` class for coordinating multi-stage progress
- Pass progress manager to all analyzers and extractors
- Add `--quiet` flag to suppress progress (for scripting)
- Add `--json-progress` for machine-readable progress events

---

### 1.6 Undo/Rollback Support

**Priority**: Low | **Effort**: Medium | **Impact**: Low

#### Current State

`cleanup_intermediate_files()` permanently deletes files:

```python
# src/ui/category_review.py:406-407
file_path.unlink()
```

#### Problem

- No way to recover if user makes a mistake during review
- Previous analysis runs are lost
- Can't compare current vs previous categorizations

#### Recommendation

- Move deleted files to `~/.email-analyzer/archive/` with timestamp
- Keep last N analysis runs (configurable, default 3)
- Add `restore` command to recover from archive
- Add `history` command to list previous runs

**Archive Structure**:
```
~/.email-analyzer/archive/
├── 2025-01-14_103045/
│   ├── email_corpus.json
│   ├── corpus_analysis_results.json
│   ├── category_suggestions.json
│   └── approved_categories.json
└── 2025-01-10_142312/
    └── ...
```

#### Implementation Notes

- Create `src/utils/archive.py` module
- Add `max_archives` to config (default: 3)
- Implement `archive_current()` before each pipeline run
- Add `--no-archive` flag for one-off runs

---

### 1.7 Export Formats

**Priority**: Low | **Effort**: Medium | **Impact**: Medium

#### Current State

Only JSON output format.

#### Problem

- JSON is not user-friendly for non-technical users
- Can't easily import results into spreadsheets
- No visual reports for sharing

#### Recommendation

Add export command with multiple formats:

| Format | Use Case |
|--------|----------|
| CSV | Spreadsheet analysis, data import |
| HTML | Interactive report with charts |
| PDF | Shareable summary report |
| Outlook Rules | Direct import to Outlook |
| Gmail Filters | Direct import to Gmail |

**Example**:
```bash
python -m src.cli export --format html --output report.html
python -m src.cli export --format outlook-rules --output rules.xml
```

#### Implementation Notes

- Create `src/exporters/` module
- Use `jinja2` for HTML templating
- Use `weasyprint` or `reportlab` for PDF
- Research Outlook/Gmail rule formats for compatibility

---

## 2. Output Quality Improvements

### 2.1 Automatic Cluster Count Selection

**Priority**: High | **Effort**: Medium | **Impact**: Very High

#### Current State

Fixed default of `num_clusters=10`:

```python
# src/analyzers/semantic_analyzer.py:52
num_clusters: int = 10,
```

Users must guess the appropriate number without guidance.

#### Problem

- Optimal cluster count varies dramatically by corpus:
  - Small inbox (500 emails): 5-7 clusters may be ideal
  - Large diverse inbox (50,000 emails): 20-30 clusters may be needed
- Wrong cluster count leads to:
  - Too few: Overly broad, meaningless categories
  - Too many: Fragmented, overlapping categories
- Users have no way to know what's appropriate

#### Recommendation

Implement automatic cluster selection using statistical methods:

**Option 1 - Elbow Method**:
```python
def find_optimal_clusters_elbow(embeddings, max_k=30):
    """Find optimal k using elbow method (inertia curve)."""
    inertias = []
    for k in range(2, max_k + 1):
        kmeans = KMeans(n_clusters=k, random_state=42)
        kmeans.fit(embeddings)
        inertias.append(kmeans.inertia_)

    # Find elbow point (maximum curvature)
    return find_elbow_point(inertias) + 2  # +2 because we started at k=2
```

**Option 2 - Silhouette Analysis** (more robust):
```python
def find_optimal_clusters_silhouette(embeddings, max_k=30):
    """Find optimal k using silhouette score."""
    scores = []
    for k in range(2, max_k + 1):
        kmeans = KMeans(n_clusters=k, random_state=42)
        labels = kmeans.fit_predict(embeddings)
        score = silhouette_score(embeddings, labels)
        scores.append(score)

    return np.argmax(scores) + 2  # +2 because we started at k=2
```

**Proposed Interface**:
```bash
# Use automatic selection (recommended)
python -m src.cli analyze --auto-clusters

# Override with specific value
python -m src.cli analyze --num-clusters 15

# Show analysis of different k values
python -m src.cli analyze --cluster-analysis
# Output: table showing k vs silhouette score vs inertia
```

#### Implementation Notes

- Add `ClusterOptimizer` class in `src/analyzers/cluster_optimizer.py`
- Cache optimization results (expensive computation)
- Show optimization progress (testing k=2..30 takes time)
- Allow setting `max_k` via config
- Default to auto-selection, allow override

---

### 2.2 Hierarchical Categories

**Priority**: High | **Effort**: High | **Impact**: High

#### Current State

All categories are flat with no parent-child relationships:

```python
# src/models/category.py - no hierarchy support
class Category(BaseModel):
    category_id: str
    category_name: str
    # ... no parent_category_id field
```

#### Problem

Real email organization is naturally hierarchical:
```
Shopping
├── Amazon
│   ├── Orders
│   └── Deals & Promotions
├── eBay
└── Other Retail

Work
├── Team Updates
├── Meeting Invites
└── Project Notifications
```

Flat categories force users to either:
- Have too many top-level categories (overwhelming)
- Have overly broad categories (not useful)

#### Recommendation

**Phase 1 - Data Model**:
- Add `parent_category_id: str | None` to Category model
- Add `subcategories: list[Category]` for tree representation
- Add `level: int` (0 = top-level, 1 = subcategory, etc.)

**Phase 2 - Generation**:
- Use hierarchical agglomerative clustering instead of (or in addition to) KMeans
- Generate 2-level hierarchy:
  - Level 0: Broad categories (5-10)
  - Level 1: Specific subcategories (2-5 per parent)
- Match templates at appropriate level

**Phase 3 - Review UI**:
- Tree view in TUI for hierarchical display
- Allow promoting subcategories to top-level
- Allow demoting top-level to subcategory
- Collapse/expand in review interface

**Proposed Output**:
```json
{
  "categories": [
    {
      "category_id": "cat_shopping",
      "category_name": "Shopping & E-commerce",
      "level": 0,
      "parent_category_id": null,
      "subcategories": [
        {
          "category_id": "cat_amazon",
          "category_name": "Amazon Orders",
          "level": 1,
          "parent_category_id": "cat_shopping"
        }
      ]
    }
  ]
}
```

#### Implementation Notes

- Research `scipy.cluster.hierarchy` for agglomerative clustering
- Use dendrogram analysis to determine optimal cut points
- Add `--flat` flag to disable hierarchy (backward compatibility)
- Consider linkage methods: ward, complete, average

---

### 2.3 Improved Category Naming

**Priority**: High | **Effort**: Medium | **Impact**: High

#### Current State

Simplistic naming algorithm:

```python
# src/generators/category_generator.py:122-135
def _generate_cluster_name(self, subjects: list[str], domains: list[tuple]) -> str:
    # Try to use common domain
    if domains:
        domain_name = domains[0][0].replace('.com', '').replace('.', ' ').title()
        return f"{domain_name} Related"

    # Fallback to common words in subjects
    words = ' '.join(subjects).lower().split()
    common_words = [w for w in words if len(w) > 4][:2]
    if common_words:
        return ' '.join(common_words).title() + " Category"

    return "Miscellaneous"
```

#### Problems

1. **Generic names**: "Amazon Related", "Order Category", "Miscellaneous"
2. **No context**: Names don't explain what's in the category
3. **Poor word filtering**: `len(w) > 4` is too simplistic (misses "sale", "bill")
4. **Domain-centric**: Prioritizes domain over actual content

#### Recommendation

**Approach 1 - TF-IDF Keyphrase Extraction**:
```python
from sklearn.feature_extraction.text import TfidfVectorizer

def generate_cluster_name_tfidf(cluster_texts: list[str], corpus_texts: list[str]) -> str:
    """Generate name using TF-IDF to find distinguishing terms."""
    # Fit on full corpus to get IDF weights
    vectorizer = TfidfVectorizer(max_features=1000, stop_words='english')
    vectorizer.fit(corpus_texts)

    # Transform cluster texts
    cluster_tfidf = vectorizer.transform(cluster_texts)

    # Get top terms by mean TF-IDF score
    mean_scores = cluster_tfidf.mean(axis=0).A1
    top_indices = mean_scores.argsort()[-3:][::-1]
    top_terms = [vectorizer.get_feature_names_out()[i] for i in top_indices]

    return ' '.join(top_terms).title()
```

**Approach 2 - KeyBERT** (better quality, more compute):
```python
from keybert import KeyBERT

def generate_cluster_name_keybert(cluster_texts: list[str]) -> str:
    """Generate name using KeyBERT keyphrase extraction."""
    kw_model = KeyBERT()
    combined_text = ' '.join(cluster_texts)
    keywords = kw_model.extract_keywords(
        combined_text,
        keyphrase_ngram_range=(1, 2),
        top_n=3
    )
    return ', '.join([kw[0] for kw in keywords]).title()
```

**Approach 3 - LLM-based** (highest quality, optional):
```python
def generate_cluster_name_llm(representative_samples: list[str]) -> str:
    """Generate name using local LLM (ollama or similar)."""
    prompt = f"""Given these representative email subjects from a category:
    {representative_samples[:5]}

    Generate a short, descriptive category name (2-4 words) that captures
    what these emails have in common. Return only the name."""

    # Call local LLM API
    response = ollama.generate(model='llama2', prompt=prompt)
    return response['response'].strip()
```

**Implementation Strategy**:
1. Default: TF-IDF (fast, no extra dependencies)
2. Optional: KeyBERT (`--better-names` flag, adds dependency)
3. Optional: LLM (`--llm-names` flag, requires ollama setup)

#### Implementation Notes

- Add `src/generators/name_generator.py` module
- Implement all three approaches behind common interface
- Add name quality heuristics (reject names < 2 words, > 6 words)
- Flag low-confidence names for user review
- Allow users to regenerate names during review

---

### 2.4 Expanded Template Coverage

**Priority**: Medium | **Effort**: Low | **Impact**: High

#### Current State

Only 6 predefined templates:

```python
# src/models/category_template.py:20-57
PREDEFINED_TEMPLATES = [
    "Financial & Banking",
    "Shopping & E-commerce",
    "Social Media",
    "Newsletters & Marketing",
    "Travel & Transportation",
    "Account & Security",
]
```

#### Problem

Many common email categories are not covered:
- Work/Business
- Personal (friends, family)
- Healthcare
- Education
- Entertainment subscriptions
- Government/Official
- Utilities
- And more...

#### Recommendation

Expand to 15-20 templates covering common categories:

```python
PREDEFINED_TEMPLATES = [
    # Existing (enhanced)
    CategoryTemplate(
        name="Financial & Banking",
        keywords=["invoice", "payment", "bank", "statement", "bill", "credit",
                  "transaction", "wire", "transfer", "balance", "account"],
        domains=["paypal.com", "chase.com", "bankofamerica.com", "stripe.com",
                 "venmo.com", "wellsfargo.com", "capitalone.com", "discover.com"],
        description="Financial transactions, banking, and billing"
    ),

    # New templates
    CategoryTemplate(
        name="Work & Business",
        keywords=["meeting", "agenda", "standup", "sprint", "deadline", "project",
                  "quarterly", "report", "review", "sync", "update"],
        domains=["slack.com", "zoom.us", "teams.microsoft.com", "asana.com",
                 "monday.com", "jira.atlassian.com"],
        description="Work-related communications and meetings"
    ),

    CategoryTemplate(
        name="Healthcare & Medical",
        keywords=["appointment", "prescription", "lab results", "doctor", "health",
                  "insurance claim", "copay", "pharmacy", "medical"],
        domains=["mychart.com", "healthgrades.com", "cvs.com", "walgreens.com"],
        description="Healthcare appointments, prescriptions, and medical communications"
    ),

    CategoryTemplate(
        name="Education & Learning",
        keywords=["course", "assignment", "grade", "enrollment", "syllabus",
                  "certificate", "lesson", "quiz", "lecture"],
        domains=["coursera.org", "udemy.com", "edx.org", "khanacademy.org",
                 "linkedin.com/learning", "skillshare.com"],
        description="Online courses, educational content, and learning platforms"
    ),

    CategoryTemplate(
        name="Entertainment & Subscriptions",
        keywords=["subscription", "streaming", "watch", "listen", "playlist",
                  "new release", "recommendation"],
        domains=["netflix.com", "spotify.com", "hulu.com", "disneyplus.com",
                 "hbomax.com", "youtube.com", "twitch.tv", "audible.com"],
        description="Entertainment subscriptions and streaming services"
    ),

    CategoryTemplate(
        name="Government & Official",
        keywords=["tax", "irs", "dmv", "license", "permit", "registration",
                  "government", "official", "federal", "state"],
        domains=["irs.gov", "ssa.gov", "usps.com", "dmv.gov"],
        description="Government communications, taxes, and official notices"
    ),

    CategoryTemplate(
        name="Utilities & Bills",
        keywords=["utility", "electric", "gas", "water", "internet", "phone",
                  "cable", "bill due", "usage", "meter"],
        domains=["xfinity.com", "att.com", "verizon.com", "spectrum.com"],
        description="Utility bills and service providers"
    ),

    CategoryTemplate(
        name="Real Estate & Housing",
        keywords=["rent", "lease", "mortgage", "property", "apartment", "house",
                  "landlord", "maintenance", "hoa"],
        domains=["zillow.com", "apartments.com", "realtor.com", "redfin.com"],
        description="Housing, rent, and real estate communications"
    ),

    CategoryTemplate(
        name="Insurance",
        keywords=["policy", "coverage", "claim", "premium", "deductible",
                  "insurance", "renewal", "quote"],
        domains=["geico.com", "progressive.com", "statefarm.com", "allstate.com"],
        description="Insurance policies, claims, and coverage"
    ),

    CategoryTemplate(
        name="Food & Dining",
        keywords=["order", "delivery", "restaurant", "reservation", "menu",
                  "pickup", "groceries"],
        domains=["doordash.com", "ubereats.com", "grubhub.com", "instacart.com",
                 "opentable.com", "yelp.com"],
        description="Food delivery, restaurant reservations, and dining"
    ),

    CategoryTemplate(
        name="Fitness & Wellness",
        keywords=["workout", "gym", "fitness", "exercise", "meditation",
                  "wellness", "health goal", "activity"],
        domains=["peloton.com", "fitbit.com", "myfitnesspal.com", "headspace.com",
                 "strava.com", "classpass.com"],
        description="Fitness tracking, gym memberships, and wellness"
    ),

    CategoryTemplate(
        name="Charity & Donations",
        keywords=["donate", "donation", "charity", "nonprofit", "fundraiser",
                  "contribution", "volunteer", "cause"],
        domains=["gofundme.com", "change.org", "redcross.org"],
        description="Charitable donations and nonprofit communications"
    ),

    CategoryTemplate(
        name="Job Search & Recruitment",
        keywords=["job", "application", "interview", "resume", "position",
                  "recruiter", "hiring", "opportunity", "career"],
        domains=["linkedin.com", "indeed.com", "glassdoor.com", "monster.com",
                 "ziprecruiter.com"],
        description="Job applications, interviews, and recruitment"
    ),
]
```

#### Implementation Notes

- Move templates to external YAML file for easy editing
- Add `--custom-templates path/to/templates.yaml` flag
- Allow users to disable built-in templates (`--no-builtin-templates`)
- Add template validation (require name, keywords, description)

---

### 2.5 Confidence Score Refinement

**Priority**: Medium | **Effort**: Medium | **Impact**: Medium

#### Current State

Simple averaging of three factors:

```python
# Referenced in src/generators/category_generator.py:67
confidence = avg(volume_score, source_score, percentage_score)

# Where:
volume_score = min(email_count / 100, 1.0)
source_score = {TEMPLATE: 0.9, CONTENT_CLUSTER: 0.8, SENDER: 0.7, CUSTOM: 0.5}
percentage_score = percentage / 100.0
```

#### Problems

1. **No cohesion measure**: Doesn't consider how "tight" the cluster is
2. **Equal weighting**: All factors weighted equally, but importance varies
3. **No name confidence**: Poor names should lower overall confidence
4. **No distinctiveness**: Overlapping clusters should have lower confidence

#### Recommendation

Enhanced confidence scoring:

```python
def calculate_confidence_v2(
    category: Category,
    cluster_silhouette: float | None,  # Per-cluster silhouette score
    name_quality: float,                # 0-1 based on naming heuristics
    overlap_penalty: float,             # Penalty for overlapping with other categories
    total_emails: int
) -> float:
    """Calculate refined confidence score."""

    # Base scores (existing)
    volume_score = min(category.email_count / 100, 1.0)
    source_score = SOURCE_WEIGHTS[category.source]
    percentage_score = min(category.percentage / 10, 1.0)  # Cap at 10%

    # New scores
    cohesion_score = cluster_silhouette if cluster_silhouette else 0.7
    name_score = name_quality
    distinctiveness_score = 1.0 - overlap_penalty

    # Weighted combination
    confidence = (
        0.25 * cohesion_score +      # How tight is the cluster?
        0.20 * volume_score +         # How many emails?
        0.20 * source_score +         # How was it generated?
        0.15 * percentage_score +     # What % of inbox?
        0.10 * name_score +           # Is the name good?
        0.10 * distinctiveness_score  # Is it unique?
    )

    return round(confidence, 3)
```

#### Implementation Notes

- Calculate silhouette score per cluster during semantic analysis
- Add name quality heuristics (length, stop words, specificity)
- Calculate pairwise cluster overlap during generation
- Store component scores for transparency (show in review UI)

---

### 2.6 Feedback Loop / Learning from User Decisions

**Priority**: Medium | **Effort**: High | **Impact**: High

#### Current State

User decisions during review are not persisted or used for future runs:

```python
# src/ui/category_review.py - decisions are made but not stored for learning
```

#### Problem

- Users make the same corrections repeatedly
- System doesn't learn from patterns in user behavior
- No personalization over time

#### Recommendation

**Phase 1 - Decision Logging**:
- Store all review decisions with context:
  ```json
  {
    "timestamp": "2025-01-14T10:30:00Z",
    "category_name": "Amazon Related",
    "action": "rename",
    "new_name": "Amazon Orders",
    "confidence_at_decision": 0.72,
    "email_count": 156
  }
  ```

**Phase 2 - Pattern Detection**:
- Identify recurring patterns:
  - "User always renames 'X Related' to 'X'"
  - "User always merges Amazon and Amazon Prime"
  - "User always deletes categories with <10 emails"

**Phase 3 - Apply Learning**:
- Pre-apply learned transformations
- Show user what was auto-applied
- Allow override of learned behavior

**Proposed UX**:
```
Based on your previous reviews:
  • Auto-renamed "Amazon Related" → "Amazon Orders" (5 previous renames)
  • Auto-merged "Spotify" and "Spotify Wrapped" (3 previous merges)

[A]ccept auto-changes  [R]eview individually  [C]lear learning
```

#### Implementation Notes

- Store decisions in `~/.email-analyzer/decisions.jsonl`
- Create `src/learning/` module
- Define minimum pattern threshold (e.g., 3 occurrences)
- Add `--no-learning` flag to disable
- Add `learning clear` command to reset

---

### 2.7 Improved Sender Classification

**Priority**: Low | **Effort**: Medium | **Impact**: Medium

#### Current State

Simple heuristics for sender type:

```python
# src/analyzers/sender_analyzer.py (inferred from exploration)
# Uses keywords like "noreply", "marketing" in email address
```

#### Problem

- Misclassifies senders based on surface patterns
- Doesn't use email structure/headers
- No authentication verification

#### Recommendation

Enhanced classification using multiple signals:

```python
def classify_sender(email: Email) -> SenderType:
    """Classify sender using multiple signals."""
    signals = []

    # 1. Address patterns (existing)
    if 'noreply' in email.sender_email.lower():
        signals.append(('service', 0.8))

    # 2. Headers (new)
    if email.headers.get('List-Unsubscribe'):
        signals.append(('newsletter', 0.9))
    if email.headers.get('Precedence') == 'bulk':
        signals.append(('marketing', 0.85))

    # 3. Content structure (new)
    if has_html_heavy_content(email):
        signals.append(('marketing', 0.6))
    if has_personal_greeting(email):
        signals.append(('personal', 0.7))

    # 4. Reply patterns (new)
    if email_has_replies_from_user(email):
        signals.append(('personal', 0.9))

    return aggregate_signals(signals)
```

#### Implementation Notes

- Requires extracting more email headers during extraction
- Add `headers` field to Email model
- Consider privacy implications of content analysis

---

### 2.8 Duplicate Detection

**Priority**: Low | **Effort**: Low | **Impact**: Low

#### Current State

No duplicate detection - all emails treated as unique.

#### Problem

- Duplicates skew sender counts
- Duplicates inflate cluster sizes
- Near-duplicates (forwards, replies) may fragment clusters

#### Recommendation

Add duplicate detection during extraction:

```python
def detect_duplicates(emails: list[Email]) -> tuple[list[Email], list[DuplicateGroup]]:
    """Detect and group duplicate emails."""
    seen_message_ids = {}
    seen_hashes = {}
    unique = []
    duplicates = []

    for email in emails:
        # Exact duplicate (same Message-ID)
        if email.message_id in seen_message_ids:
            duplicates.append((email, seen_message_ids[email.message_id]))
            continue

        # Content duplicate (same hash)
        content_hash = hash_email_content(email)
        if content_hash in seen_hashes:
            duplicates.append((email, seen_hashes[content_hash]))
            continue

        seen_message_ids[email.message_id] = email
        seen_hashes[content_hash] = email
        unique.append(email)

    return unique, duplicates
```

#### Implementation Notes

- Add `--include-duplicates` flag to keep duplicates
- Report duplicate statistics in extraction summary
- Consider SimHash for near-duplicate detection (more complex)

---

## 3. Architectural Improvements

### 3.1 Plugin System for Analyzers

**Priority**: Medium | **Effort**: High | **Impact**: Medium

#### Current State

Analyzers are hardcoded:

```python
# src/analyzers/__init__.py
def run_full_analysis(corpus, num_clusters):
    results = AnalysisResults(
        sender_analysis=SenderAnalyzer().analyze(corpus),
        subject_analysis=SubjectAnalyzer().analyze(corpus),
        # ... hardcoded list
    )
```

#### Recommendation

Plugin-based architecture:

```python
# src/analyzers/base.py
from abc import ABC, abstractmethod

class BaseAnalyzer(ABC):
    """Base class for all analyzers."""

    name: str
    version: str

    @abstractmethod
    def analyze(self, corpus: Corpus, **kwargs) -> AnalyzerResult:
        pass

# Discovery via entry points
# pyproject.toml:
# [project.entry-points."email_analyzer.analyzers"]
# sender = "src.analyzers.sender_analyzer:SenderAnalyzer"
# custom = "my_plugin:MyCustomAnalyzer"
```

#### Implementation Notes

- Define `AnalyzerProtocol` for type checking
- Use `importlib.metadata.entry_points()` for discovery
- Add `--analyzers` flag to select which to run
- Add `--disable-analyzer` to skip specific ones

---

### 3.2 Multi-Source Email Support

**Priority**: Medium | **Effort**: High | **Impact**: Medium

#### Current State

Only M365/Hotmail extraction via MCP.

#### Recommendation

Abstract email source behind interface:

```python
# src/extractors/base.py
class EmailSource(ABC):
    @abstractmethod
    def extract(self, **kwargs) -> Corpus:
        pass

# src/extractors/sources/
#   m365.py      - Existing M365 MCP
#   gmail.py     - Gmail API
#   imap.py      - Generic IMAP
#   mbox.py      - Local mbox files
#   maildir.py   - Local maildir
```

**CLI**:
```bash
python -m src.cli extract --source m365 --user-email user@hotmail.com
python -m src.cli extract --source gmail --credentials creds.json
python -m src.cli extract --source mbox --file archive.mbox
```

#### Implementation Notes

- Unified Email model regardless of source
- Source-specific authentication handling
- Add `--source` flag with validation

---

### 3.3 Database Backend Option

**Priority**: Low | **Effort**: High | **Impact**: Low

#### Current State

All data stored as JSON files.

#### Problem

Large corpora (100k+ emails) may have memory/performance issues loading entire JSON files.

#### Recommendation

Optional SQLite backend:

```bash
# Use SQLite for large corpora
python -m src.cli extract --backend sqlite --user-email user@hotmail.com
```

#### Implementation Notes

- Create `src/storage/` module with `JsonStorage` and `SqliteStorage`
- Abstract storage behind interface
- Keep JSON as default (simpler, portable)
- Add migration tool: `migrate json-to-sqlite`

---

### 3.4 Python API / Library Mode

**Priority**: Low | **Effort**: Medium | **Impact**: Medium

#### Current State

CLI-only interface.

#### Recommendation

Expose clean Python API:

```python
from email_analyzer import Corpus, Pipeline
from email_analyzer.sources import MboxSource

# Load from local file
corpus = Corpus.from_source(MboxSource("archive.mbox"))

# Or from existing JSON
corpus = Corpus.from_json("email_corpus.json")

# Run analysis
pipeline = Pipeline(corpus)
analysis = pipeline.analyze(num_clusters=15)
categories = pipeline.suggest(analysis)

# Export
categories.to_json("categories.json")
categories.to_csv("categories.csv")
```

#### Implementation Notes

- Refactor CLI to use library API internally
- Add `py.typed` marker for type checking
- Document API with docstrings and examples
- Consider Jupyter notebook examples

---

## 4. Quick Wins

Low-effort improvements with meaningful impact:

| Improvement | Location | Effort | Impact |
|------------|----------|--------|--------|
| Add `--quiet` flag | `src/cli.py` | 1 hour | Medium |
| Add `--json` output flag | `src/cli.py` | 2 hours | Medium |
| Color-code confidence in review | `src/ui/category_review.py` | 2 hours | Medium |
| Show email count before extraction | `src/cli.py:cmd_extract` | 1 hour | High |
| Add `info` command for corpus stats | `src/cli.py` | 3 hours | Medium |
| Validate email format early | `src/cli.py:cmd_extract` | 30 min | Medium |
| Add `--skip-review` for automation | `src/cli.py:cmd_pipeline` | 1 hour | High |
| Add `--version` flag | `src/cli.py` | 30 min | Low |
| Improve error messages | Various | 2 hours | Medium |

---

## 5. Priority Matrix

### Tier 1 - High Impact, Reasonable Effort
1. Configuration File Support (1.1)
2. Rich Terminal UI (1.2)
3. Auto Cluster Selection (2.1)
4. Improved Category Naming (2.3)
5. Expanded Templates (2.4)

### Tier 2 - High Impact, Higher Effort
6. Hierarchical Categories (2.2)
7. Incremental Analysis (1.4)
8. Confidence Score Refinement (2.5)

### Tier 3 - Medium Impact
9. Preview/Dry-Run Mode (1.3)
10. Progress Feedback (1.5)
11. Feedback Loop (2.6)
12. Quick Wins (4.x)

### Tier 4 - Lower Priority
13. Plugin System (3.1)
14. Multi-Source Support (3.2)
15. Export Formats (1.7)
16. Undo/Rollback (1.6)
17. Database Backend (3.3)
18. Library API (3.4)

---

## Appendix: Dependencies to Add

| Feature | New Dependencies |
|---------|-----------------|
| Rich TUI | `rich>=13.0`, `textual>=0.40` |
| Config Files | `pydantic-settings>=2.0` |
| Better Naming | `keybert>=0.8` (optional) |
| PDF Export | `weasyprint>=60` or `reportlab>=4.0` |
| Cluster Optimization | (uses existing sklearn) |

---

*Document Version: 1.0*
*Created: 2025-01-14*
*Author: Claude Code Analysis*
