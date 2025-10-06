# Email Processor - Usage Guide

## Quick Start

### Default Output Directory
By default, all output files are saved to: **`~/data/outputs`**

This expands to `/home/yourusername/data/outputs` on Linux/Mac or `C:\Users\YourUsername\data\outputs` on Windows.

### Running Commands

```bash
# Activate virtual environment
source venv/bin/activate  # or: venv\Scripts\activate on Windows

# Extract emails (saves to ~/data/outputs/)
python -m src.cli extract --user-email your.email@hotmail.com

# View help
python -m src.cli --help
```

---

## Custom Output Directories

### Method 1: Global --output-dir Flag

Use `--output-dir` **before** the command name:

```bash
# Extract to custom directory
python -m src.cli --output-dir ~/my-emails extract --user-email user@hotmail.com

# Analyze in custom directory
python -m src.cli --output-dir ~/my-emails analyze

# Run pipeline in custom directory
python -m src.cli --output-dir /mnt/backup/email-analysis pipeline --user-email user@hotmail.com
```

### Method 2: Per-File Custom Paths

Override individual file paths while using default output directory:

```bash
# Extract to custom corpus file
python -m src.cli extract --user-email user@hotmail.com --corpus-file ~/custom_corpus.json

# Analyze custom corpus, save to custom analysis file
python -m src.cli analyze --corpus ~/custom_corpus.json --analysis-file ~/custom_analysis.json
```

### Method 3: Mix Global + Per-File

```bash
# Use custom output directory, but override specific files
python -m src.cli --output-dir ~/emails \
  extract --user-email user@hotmail.com --corpus-file ~/backup/emails.json
```

---

## Command Reference

### 1. Extract

Extract emails from M365/Hotmail inbox.

**Basic Usage:**
```bash
python -m src.cli extract --user-email your.email@hotmail.com
```

**All Options:**
```bash
python -m src.cli [--output-dir DIR] extract \
  --user-email EMAIL \
  [--corpus-file PATH] \
  [--batch-size N] \
  [--checkpoint-interval N]
```

**Options:**
- `--user-email` (required): M365/Hotmail email address
- `--corpus-file`: Custom corpus JSON path (default: `{output-dir}/email_corpus.json`)
- `--batch-size`: Emails per API batch (default: 500)
- `--checkpoint-interval`: Save checkpoint every N emails (default: 100)

**Output Files:**
- `email_corpus.json` - Complete email corpus
- `extraction_errors.log` - Error log (if any failures)
- `extraction_checkpoint.json` - Temporary (deleted on success)

**Example:**
```bash
# Extract with custom batch size
python -m src.cli extract --user-email user@hotmail.com --batch-size 1000

# Extract to specific location
python -m src.cli --output-dir ~/email-backup extract --user-email user@hotmail.com
```

---

### 2. Analyze

Analyze email corpus for patterns (5 analyzers: sender, subject, semantic, temporal, volume).

**Basic Usage:**
```bash
python -m src.cli analyze
```

**All Options:**
```bash
python -m src.cli [--output-dir DIR] analyze \
  [--corpus PATH] \
  [--num-clusters N] \
  [--analysis-file PATH]
```

**Options:**
- `--corpus`: Path to corpus JSON (default: `{output-dir}/email_corpus.json`)
- `--num-clusters`: Semantic cluster count (default: 10)
- `--analysis-file`: Custom analysis results path (default: `{output-dir}/corpus_analysis_results.json`)

**Output Files:**
- `corpus_analysis_results.json` - Complete analysis results

**Example:**
```bash
# Analyze with 15 semantic clusters
python -m src.cli analyze --num-clusters 15

# Analyze corpus from custom location
python -m src.cli analyze --corpus ~/backup/email_corpus.json
```

---

### 3. Suggest

Generate category suggestions from analysis results.

**Basic Usage:**
```bash
python -m src.cli suggest
```

**All Options:**
```bash
python -m src.cli [--output-dir DIR] suggest \
  [--analysis PATH] \
  [--min-cluster-percentage PCT] \
  [--min-sender-count N] \
  [--suggestions-file PATH]
```

**Options:**
- `--analysis`: Path to analysis results (default: `{output-dir}/corpus_analysis_results.json`)
- `--min-cluster-percentage`: Min cluster size % for category (default: 5.0)
- `--min-sender-count`: Min emails from sender for category (default: 20)
- `--suggestions-file`: Custom suggestions path (default: `{output-dir}/category_suggestions.json`)

**Output Files:**
- `category_suggestions.json` - Category suggestions (JSON)
- `category_suggestions_report.md` - Human-readable report

**Example:**
```bash
# More aggressive category generation (smaller threshold)
python -m src.cli suggest --min-cluster-percentage 3.0 --min-sender-count 10
```

---

### 4. Review

Interactively review and approve category suggestions.

**Basic Usage:**
```bash
python -m src.cli review
```

**All Options:**
```bash
python -m src.cli [--output-dir DIR] review \
  [--suggestions PATH] \
  [--approved-file PATH] \
  [--no-cleanup]
```

**Options:**
- `--suggestions`: Path to suggestions JSON (default: `{output-dir}/category_suggestions.json`)
- `--approved-file`: Custom approved categories path (default: `{output-dir}/approved_categories.json`)
- `--no-cleanup`: Skip optional cleanup of intermediate files

**Output Files:**
- `approved_categories.json` - Final approved categories

**Interactive Actions:**
- `[A]ccept` - Approve category as-is
- `[R]ename` - Change category name/description
- `[M]erge` - Combine with another category
- `[D]elete` - Discard category
- `[S]kip` - Review later (will re-present at end)

**Example:**
```bash
# Review without cleanup prompt
python -m src.cli review --no-cleanup
```

---

### 5. Pipeline

Run complete end-to-end workflow: extract → analyze → suggest → review → optional cleanup.

**Basic Usage:**
```bash
python -m src.cli pipeline --user-email your.email@hotmail.com
```

**All Options:**
```bash
python -m src.cli [--output-dir DIR] pipeline \
  --user-email EMAIL \
  [--num-clusters N] \
  [--no-cleanup]
```

**Options:**
- `--user-email` (required): M365/Hotmail email address
- `--num-clusters`: Semantic cluster count (default: 10)
- `--no-cleanup`: Skip optional cleanup of intermediate files

**Output Files:**
- `approved_categories.json` - Final approved categories
- `extraction_errors.log` - Error log (if any failures)
- (Intermediate files optionally deleted during cleanup)

**Example:**
```bash
# Complete pipeline in custom directory
python -m src.cli --output-dir ~/my-email-analysis \
  pipeline --user-email user@hotmail.com --num-clusters 12
```

---

## File Locations Summary

### Default (~/data/outputs/)

| File | Description | Created By |
|------|-------------|------------|
| `email_corpus.json` | Email corpus | extract |
| `corpus_analysis_results.json` | Analysis results | analyze |
| `category_suggestions.json` | Category suggestions | suggest |
| `category_suggestions_report.md` | Human-readable report | suggest |
| `approved_categories.json` | Final categories | review |
| `extraction_errors.log` | Error log | extract |
| `extraction_checkpoint.json` | Temp checkpoint | extract (auto-deleted) |

### Custom Directory Example

```bash
# Set custom directory
python -m src.cli --output-dir /mnt/backup/emails pipeline --user-email user@hotmail.com

# All files created in /mnt/backup/emails/
ls /mnt/backup/emails/
# email_corpus.json
# corpus_analysis_results.json
# category_suggestions.json
# ...
```

---

## Common Workflows

### Workflow 1: Standard Full Pipeline

```bash
# One command, default location (~/data/outputs)
python -m src.cli pipeline --user-email your.email@hotmail.com
```

### Workflow 2: Custom Output Directory

```bash
# Everything in ~/my-emails/
python -m src.cli --output-dir ~/my-emails \
  pipeline --user-email your.email@hotmail.com
```

### Workflow 3: Step-by-Step with Custom Locations

```bash
# Step 1: Extract to custom location
python -m src.cli --output-dir ~/email-project extract --user-email user@hotmail.com

# Step 2: Analyze (uses ~/email-project/email_corpus.json automatically)
python -m src.cli --output-dir ~/email-project analyze --num-clusters 15

# Step 3: Generate suggestions
python -m src.cli --output-dir ~/email-project suggest

# Step 4: Review
python -m src.cli --output-dir ~/email-project review
```

### Workflow 4: Re-analyze Existing Corpus

```bash
# You already extracted emails, now analyze differently
python -m src.cli analyze --corpus ~/data/outputs/email_corpus.json --num-clusters 20

# Or in different location
python -m src.cli --output-dir ~/new-analysis \
  analyze --corpus ~/old-analysis/email_corpus.json --num-clusters 20
```

### Workflow 5: Resume Interrupted Extraction

```bash
# Extraction was interrupted at email 3,456 / 5,000
# Just run extract again - it automatically resumes from checkpoint
python -m src.cli extract --user-email user@hotmail.com
# Resumes from last checkpoint (e.g., email 3,400)
```

---

## Troubleshooting

### Issue: "ModuleNotFoundError: No module named 'src'"

**Solution:** Run as a module from project root:
```bash
# Wrong
cd src && python cli.py --help

# Correct
python -m src.cli --help
```

### Issue: "Permission denied" when creating output directory

**Solution:** Check directory permissions or use a custom directory:
```bash
# Use home directory subdirectory (always writable)
python -m src.cli --output-dir ~/my-emails extract --user-email user@hotmail.com
```

### Issue: "File not found" when running analyze/suggest/review

**Solution:** Ensure previous step completed and files exist:
```bash
# Check if corpus exists
ls ~/data/outputs/email_corpus.json

# If using custom directory, specify it consistently
python -m src.cli --output-dir ~/my-dir analyze
```

### Issue: Want to see debug logs

**Solution:** Use `--verbose` flag:
```bash
python -m src.cli --verbose extract --user-email user@hotmail.com
```

---

## Environment Variables

Currently, the system uses CLI arguments for configuration. Environment variables are not supported, but you can create shell aliases:

```bash
# In ~/.bashrc or ~/.zshrc
alias email-processor='python -m src.cli --output-dir ~/my-emails'

# Then use:
email-processor extract --user-email user@hotmail.com
email-processor analyze
```

---

## Security Notes

1. **File Permissions**: All output files are created with mode `0600` (user read/write only)
2. **Directory Permissions**: Output directories are created with mode `0700` (user read/write/execute only)
3. **Local Storage Only**: No data is transmitted to external services without explicit consent
4. **Secure Defaults**: Default directory (`~/data/outputs`) is in your home directory (protected)

---

## Next Steps

After approving categories, you can:
1. Use `approved_categories.json` for Phase 1 (email-by-email categorization - future feature)
2. Export to your email client (future feature)
3. Re-run analysis with different parameters
4. Archive the analysis results for record-keeping

For more information, see:
- `specs/001-use-the-document/quickstart.md` - Detailed scenarios
- `specs/001-use-the-document/spec.md` - Complete feature specification
- `README.md` - Project overview
