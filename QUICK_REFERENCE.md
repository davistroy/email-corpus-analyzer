# Email Processor - Quick Reference

## Installation & Setup

```bash
# Clone and setup
cd /home/davistroy/dev/email-processor/initial-learning
source venv/bin/activate
pip install -r requirements.txt
```

## Default Output Location
**`~/data/outputs`** (automatically created with secure permissions)

---

## Common Commands

### Extract Emails
```bash
# Default location (~/data/outputs)
python -m src.cli extract --user-email your.email@hotmail.com

# Custom location
python -m src.cli --output-dir ~/my-emails extract --user-email your.email@hotmail.com
```

### Analyze Corpus
```bash
# Default location
python -m src.cli analyze

# With 15 clusters
python -m src.cli analyze --num-clusters 15

# Custom corpus
python -m src.cli analyze --corpus ~/path/to/email_corpus.json
```

### Generate Suggestions
```bash
# Default location
python -m src.cli suggest

# Lower threshold (more categories)
python -m src.cli suggest --min-cluster-percentage 3.0
```

### Review Categories
```bash
# Interactive review
python -m src.cli review

# Skip cleanup prompt
python -m src.cli review --no-cleanup
```

### Complete Pipeline
```bash
# One command - does everything
python -m src.cli pipeline --user-email your.email@hotmail.com

# Custom location
python -m src.cli --output-dir ~/analysis pipeline --user-email your.email@hotmail.com
```

---

## Output Files

| File | Location (default) |
|------|-------------------|
| Email corpus | `~/data/outputs/email_corpus.json` |
| Analysis results | `~/data/outputs/corpus_analysis_results.json` |
| Category suggestions | `~/data/outputs/category_suggestions.json` |
| Suggestions report | `~/data/outputs/category_suggestions_report.md` |
| Approved categories | `~/data/outputs/approved_categories.json` |
| Error log | `~/data/outputs/extraction_errors.log` |

---

## CLI Flags

### Global (before command)
- `--output-dir DIR` - Set output directory for all files
- `--verbose` / `-v` - Enable debug logging

### Extract Command
- `--user-email EMAIL` - (required) M365/Hotmail address
- `--corpus-file PATH` - Custom corpus file path
- `--batch-size N` - Emails per batch (default: 500)
- `--checkpoint-interval N` - Checkpoint every N emails (default: 100)

### Analyze Command
- `--corpus PATH` - Input corpus file
- `--num-clusters N` - Semantic clusters (default: 10)
- `--analysis-file PATH` - Output analysis file

### Suggest Command
- `--analysis PATH` - Input analysis file
- `--min-cluster-percentage PCT` - Min cluster size (default: 5.0)
- `--min-sender-count N` - Min sender emails (default: 20)
- `--suggestions-file PATH` - Output suggestions file

### Review Command
- `--suggestions PATH` - Input suggestions file
- `--approved-file PATH` - Output approved categories file
- `--no-cleanup` - Skip cleanup prompt

### Pipeline Command
- `--user-email EMAIL` - (required) M365/Hotmail address
- `--num-clusters N` - Semantic clusters (default: 10)
- `--no-cleanup` - Skip cleanup prompt

---

## Help

```bash
# General help
python -m src.cli --help

# Command-specific help
python -m src.cli extract --help
python -m src.cli analyze --help
python -m src.cli suggest --help
python -m src.cli review --help
python -m src.cli pipeline --help
```

---

## Troubleshooting

**"ModuleNotFoundError: No module named 'src'"**
→ Run from project root: `python -m src.cli` (not `python src/cli.py`)

**"Permission denied" creating directory**
→ Use home directory: `--output-dir ~/my-emails`

**"File not found" in analyze/suggest/review**
→ Ensure previous step completed or specify `--output-dir` consistently

**Want to see debug logs**
→ Add `--verbose` flag before command

---

## Examples

```bash
# Example 1: Quick start (default location)
python -m src.cli pipeline --user-email user@hotmail.com

# Example 2: Everything in custom directory
python -m src.cli --output-dir ~/email-analysis pipeline --user-email user@hotmail.com

# Example 3: Step by step with custom locations
python -m src.cli --output-dir ~/project extract --user-email user@hotmail.com
python -m src.cli --output-dir ~/project analyze --num-clusters 15
python -m src.cli --output-dir ~/project suggest
python -m src.cli --output-dir ~/project review

# Example 4: Re-analyze existing corpus
python -m src.cli analyze --corpus ~/old/email_corpus.json --num-clusters 20

# Example 5: Resume interrupted extraction
python -m src.cli extract --user-email user@hotmail.com
# Automatically resumes from last checkpoint
```

---

## Security Notes

- 📁 Directory permissions: `0700` (user only)
- 📄 File permissions: `0600` (user read/write only)
- 🔒 Local storage only (no cloud transmission)
- 🏠 Default location in home directory (always safe)

---

For detailed documentation, see:
- `USAGE.md` - Complete usage guide
- `OUTPUT_CONFIGURATION.md` - Technical implementation details
- `specs/001-use-the-document/quickstart.md` - Feature scenarios
