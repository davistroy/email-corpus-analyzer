# Quickstart: Email Corpus Extraction and Analysis System

**Purpose**: Manual validation of core user scenarios from spec.md
**Execution**: Run these steps after implementation to verify acceptance criteria

---

## Prerequisites

1. M365 MCP server authenticated and connected
2. Python 3.10+ environment activated
3. All dependencies installed (`pip install -r requirements.txt`)
4. Output directory exists: `/mnt/user-data/outputs/`

---

## Scenario 1: Complete Email Extraction

**Acceptance Criteria**: spec.md lines 60-67

### Steps

```bash
# 1. Run extraction
python src/main.py extract

# Expected output:
# Starting email extraction...
# Fetching message list...
# Found 1,523 total emails to process
# Processing batch 1/4... [##########---] 500/1523 (32.8%)
# ...
# Extraction complete!
# Successfully processed: 1,521 emails
# Failed: 2 emails (see extraction_errors.log)
# Output saved to: /mnt/user-data/outputs/email_corpus.json
```

### Validation

```bash
# 2. Verify corpus file exists
ls -lh /mnt/user-data/outputs/email_corpus.json

# 3. Verify JSON structure
python -c "
import json
with open('/mnt/user-data/outputs/email_corpus.json') as f:
    corpus = json.load(f)
    print(f\"Total emails: {corpus['extraction_metadata']['total_emails']}\")
    print(f\"First email subject: {corpus['emails'][0]['subject']}\")
"

# 4. Check error log (should have minimal entries)
cat /mnt/user-data/outputs/extraction_errors.log

# Expected: 0-5 errors for typical inbox
```

### Success Criteria

- [ ] `email_corpus.json` file exists and is valid JSON
- [ ] Total emails matches inbox count (±2%)
- [ ] Each email has: id, sender, subject, body_text, received_date
- [ ] Progress indicators shown during extraction
- [ ] Error log contains details for any failed emails

---

## Scenario 2: Corpus Analysis and Pattern Discovery

**Acceptance Criteria**: spec.md lines 69-78

### Steps

```bash
# 1. Run analysis
python src/main.py analyze

# Expected output:
# Starting corpus analysis...
# Analyzing 1,521 emails...
#
# 1. Analyzing senders... [====================] 1521/1521 (100%)
# 2. Analyzing subject patterns... [====================] 1521/1521 (100%)
# 3. Analyzing content semantics... [========----------] 50% (generating embeddings)
# 4. Analyzing temporal patterns... [====================] 1521/1521 (100%)
# 5. Calculating volume statistics... Done
#
# Analysis complete!
# Results saved to: /mnt/user-data/outputs/corpus_analysis_results.json
```

### Validation

```bash
# 2. Verify analysis file
python -c "
import json
with open('/mnt/user-data/outputs/corpus_analysis_results.json') as f:
    results = json.load(f)
    print(f\"Unique senders: {results['sender_analysis']['unique_senders']}\")
    print(f\"Top domain: {results['sender_analysis']['top_domains'][0]}\")
    print(f\"Number of clusters: {len(results['content_clusters'])}\")
    print(f\"Total subjects analyzed: {results['subject_patterns']['total_subjects_analyzed']}\")
"
```

### Success Criteria

- [ ] `corpus_analysis_results.json` exists and is valid JSON
- [ ] Contains all 5 analysis components (sender, subject, content, temporal, volume)
- [ ] Progress indicators shown for operations >10 seconds
- [ ] Semantic clustering completed with 10 clusters (default)
- [ ] Top senders list has frequency counts
- [ ] Subject patterns include prefixes, keywords, numbered patterns

---

## Scenario 3: Category Suggestion Generation

**Acceptance Criteria**: spec.md lines 80-87

### Steps

```bash
# 1. Generate category suggestions
python src/main.py suggest

# Expected output:
# Generating category suggestions...
# From content clusters: 6 categories
# From high-volume senders: 3 categories
# From templates: 4 matching templates
# Merging similar categories...
# Calculating confidence scores...
#
# Generated 10 unique category suggestions
# Saved to: /mnt/user-data/outputs/category_suggestions.json
# Report saved to: /mnt/user-data/outputs/category_suggestions_report.md
```

### Validation

```bash
# 2. Check JSON output
python -c "
import json
with open('/mnt/user-data/outputs/category_suggestions.json') as f:
    data = json.load(f)
    print(f\"Total categories: {data['total_categories']}\")
    for cat in data['categories'][:3]:
        print(f\"  - {cat['category_name']}: {cat['confidence']*100:.1f}% confidence, {cat['email_count']} emails\")
"

# 3. View human-readable report
cat /mnt/user-data/outputs/category_suggestions_report.md
```

### Success Criteria

- [ ] `category_suggestions.json` exists with categories array
- [ ] `category_suggestions_report.md` exists and is readable
- [ ] Each category has: name, description, confidence, email_count, percentage
- [ ] Categories sorted by confidence (highest first)
- [ ] At least one template-based category included
- [ ] Confidence scores in range [0, 1]

---

## Scenario 4: Interactive Category Review

**Acceptance Criteria**: spec.md lines 89-96

### Steps

```bash
# 1. Run interactive review
python src/main.py review

# Expected output:
# ============================================================
# CATEGORY REVIEW - Interactive Mode
# ============================================================
#
# --- Category 1 of 10 ---
# Name: Shopping & E-commerce
# Description: Online shopping confirmations and shipping updates
# Confidence: 92.5%
# Emails: 234 (15.4% of inbox)
#
# Sample emails in this category:
#   - From: amazon.com
#     Subject: Your Amazon order #123-456
#   - From: etsy.com
#     Subject: Order shipped!
#
# Options:
#   [A] Accept this category
#   [R] Rename category
#   [M] Merge with another category
#   [D] Delete this category
#   [S] Skip for now
#
# Your choice: A
# ✓ Category 'Shopping & E-commerce' approved
#
# [... continues for remaining categories ...]
#
# ============================================================
# Would you like to add any custom categories?
# Add custom category? (y/n): n
#
# Review complete!
# Approved 8 categories
# Saved to: /mnt/user-data/outputs/approved_categories.json
```

### Validation

```bash
# 2. Verify approved categories
python -c "
import json
with open('/mnt/user-data/outputs/approved_categories.json') as f:
    data = json.load(f)
    print(f\"Approval date: {data['approval_date']}\")
    print(f\"Total categories: {data['total_categories']}\")
    print(f\"Processing stats: {data['processing_stats']}\")
    for cat in data['categories']:
        print(f\"  {cat['category_id']}: {cat['category_name']} (modified: {cat.get('user_modified', False)})\")
"
```

### Success Criteria

- [ ] Interactive prompt displays each category with details
- [ ] User can accept, rename, merge, delete, or skip categories
- [ ] Skipped categories re-presented at end (per Clarification Q5)
- [ ] Option to add custom categories provided
- [ ] `approved_categories.json` saved with final approved list
- [ ] Processing statistics included (approved, modified, merged, deleted, custom counts)

---

## Scenario 5: Optional Cleanup

**Acceptance Criteria**: Clarification Q1 - Optional cleanup after approval

### Steps

```bash
# After approval, system should offer cleanup
# Expected prompt:
# Category approval complete!
# Would you like to clean up intermediate files? (y/n): y
#
# The following files will be deleted:
#   - /mnt/user-data/outputs/email_corpus.json
#   - /mnt/user-data/outputs/corpus_analysis_results.json
#   - /mnt/user-data/outputs/category_suggestions.json
#   - /mnt/user-data/outputs/category_suggestions_report.md
#
# Keep approved_categories.json and extraction_errors.log? (y/n): y
#
# Cleanup complete!
# Kept: approved_categories.json, extraction_errors.log
```

### Validation

```bash
# Verify only approved categories remain
ls /mnt/user-data/outputs/

# Expected: approved_categories.json, extraction_errors.log
```

### Success Criteria

- [ ] Cleanup prompt appears after category approval
- [ ] User can choose what to delete
- [ ] Approved categories and error log preserved
- [ ] User can decline cleanup (keep all files)

---

## End-to-End Validation

### Full Pipeline

```bash
# Run complete pipeline
python src/main.py pipeline

# This runs: extract → analyze → suggest → review → cleanup
```

### Performance Check

```bash
# Measure execution time
time python src/main.py pipeline

# Expected for 1000 emails:
# - Extraction: 10-20 minutes (network-dependent)
# - Analysis: best-effort, typically 2-10 minutes
# - Suggestion: <2 minutes
# - Review: user-dependent
```

### Success Criteria

- [ ] Complete pipeline runs without crashes
- [ ] All intermediate files created successfully
- [ ] Progress indicators shown for long operations (>10 seconds)
- [ ] Debug-level logging captured in errors.log
- [ ] Final approved_categories.json is valid and complete

---

## Troubleshooting

### Issue: M365 Connection Fails

```bash
# Check MCP server status
# (Command depends on MCP setup - adjust as needed)

# Verify authentication
# (Command depends on MCP setup)
```

### Issue: Out of Memory

```bash
# Enable binary quantization for embeddings
python src/main.py analyze --binary-quantization

# Use smaller batch sizes
python src/main.py extract --batch-size 100
```

### Issue: HTML Parsing Errors

```bash
# Check extraction errors log
grep "HTML" /mnt/user-data/outputs/extraction_errors.log

# These should be logged but not block extraction
```

---

## Cleanup After Testing

```bash
# Remove all test outputs
rm -rf /mnt/user-data/outputs/*

# Or selectively keep approved categories
rm /mnt/user-data/outputs/email_corpus.json
rm /mnt/user-data/outputs/corpus_analysis_results.json
rm /mnt/user-data/outputs/category_suggestions.json
```
