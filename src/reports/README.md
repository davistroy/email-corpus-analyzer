# Report Generation Module

Comprehensive report generation for email corpus analysis results.

## Overview

This module provides multiple report formats for presenting email analysis results:

- **HTML**: Interactive reports with CSS styling, collapsible sections, and visualizations
- **JSON**: Structured data export with full metadata
- **CSV**: Tabular data files for spreadsheet analysis (single zip or multiple files)
- **Markdown**: Simple text reports (generated via CategoryGenerator)

## Features

### HTML Reports
- Responsive design with modern CSS styling
- Interactive collapsible sections
- Progress bars and visualizations
- Summary statistics cards
- Sender analysis with top senders and domains
- Content clusters with LLM-generated names
- Temporal and subject pattern analysis
- Category suggestions with confidence scores
- Print-friendly styles

### JSON Reports
- Complete analysis data export
- Pretty-printed or compact format
- Metadata with generation timestamp
- Optional inclusion of email IDs
- Structured nested data
- Easy parsing for further analysis

### CSV Reports
- Multiple CSV files for different data types:
  - `summary.csv` - Overall statistics
  - `senders.csv` - Sender analysis
  - `domains.csv` - Domain analysis
  - `clusters.csv` - Content clusters
  - `categories.csv` - Category suggestions
  - `subject_keywords.csv` - Subject line keywords
  - `subject_prefixes.csv` - Common prefixes
  - `temporal_patterns.csv` - Frequency patterns
- Export as zip archive or directory
- Compatible with Excel, Google Sheets, etc.

## Usage

### From CLI

```bash
# Generate HTML report
email-analyzer report --format html

# Generate JSON report (pretty-printed)
email-analyzer report --format json --pretty

# Generate CSV reports as zip
email-analyzer report --format csv --zip

# Generate CSV reports as directory
email-analyzer report --format csv --no-zip

# Generate all formats at once
email-analyzer report --format all

# Specify output path
email-analyzer report --format html --output ~/reports/my_analysis.html

# Generate for specific mailbox
email-analyzer report --mailbox "Work" --format html
```

### From Python

```python
from src.reports import HTMLReportGenerator, JSONReportGenerator, CSVReportGenerator, ReportMetadata
from src.models.analysis_results import AnalysisResults
from src.models.category import Category
from datetime import datetime
from pathlib import Path

# Load your analysis results
analysis = AnalysisResults(...)  # Your analysis data
categories = [...]  # Optional category suggestions

# Create metadata
metadata = ReportMetadata(
    generated_at=datetime.now(),
    generator_version="2.0.0",
    mailbox_name="Work Email",
    mailbox_email="user@company.com",
    total_emails=5000,
    date_range="2024-01-01 to 2024-12-31",
)

# Generate HTML report
html_gen = HTMLReportGenerator()
html_gen.save(
    Path("reports/analysis.html"),
    analysis,
    categories,
    metadata=metadata,
)

# Generate JSON report
json_gen = JSONReportGenerator(pretty=True, include_email_ids=False)
json_gen.save(
    Path("reports/analysis.json"),
    analysis,
    categories,
    metadata=metadata,
)

# Generate CSV reports
csv_gen = CSVReportGenerator(export_as_zip=True)
csv_gen.save(
    Path("reports/analysis_data.zip"),
    analysis,
    categories,
    metadata=metadata,
)
```

## API Reference

### Base Classes

#### `ReportMetadata`
Data class containing report metadata:
- `generated_at`: datetime - When the report was generated
- `generator_version`: str - Version of the report generator
- `mailbox_name`: str | None - Friendly name of the mailbox
- `mailbox_email`: str | None - Email address of the mailbox
- `total_emails`: int - Total number of emails analyzed
- `date_range`: str | None - Date range of emails

#### `BaseReportGenerator`
Abstract base class for all report generators. Provides common utilities:
- `_create_metadata()` - Create metadata from analysis
- `_format_number()` - Format numbers with thousands separators
- `_format_percentage()` - Format percentage values
- `_format_date()` - Format datetime for display

### HTML Generator

#### `HTMLReportGenerator`
Generates interactive HTML reports.

```python
generator = HTMLReportGenerator()
```

**Methods:**
- `generate(analysis, categories=None, corpus=None, metadata=None) -> str`
  - Returns HTML string
- `save(output_path, analysis, categories=None, corpus=None, metadata=None) -> Path`
  - Saves HTML to file and returns path

**Features:**
- Modern responsive design
- Interactive collapsible sections
- CSS animations and transitions
- Progress bars for percentages
- Color-coded badges
- Print-friendly styles

### JSON Generator

#### `JSONReportGenerator`
Generates structured JSON reports.

```python
generator = JSONReportGenerator(
    pretty=True,              # Pretty-print JSON
    include_email_ids=False   # Include email ID lists
)
```

**Methods:**
- `generate(analysis, categories=None, corpus=None, metadata=None) -> dict`
  - Returns dictionary
- `save(output_path, analysis, categories=None, corpus=None, metadata=None) -> Path`
  - Saves JSON to file and returns path

**Options:**
- `pretty`: If True, formats JSON with indentation
- `include_email_ids`: If True, includes email ID lists (can be large)

#### `CompactJSONReportGenerator`
Convenience class for minified JSON output.

```python
generator = CompactJSONReportGenerator(include_email_ids=False)
```

### CSV Generator

#### `CSVReportGenerator`
Generates multiple CSV files.

```python
generator = CSVReportGenerator(
    export_as_zip=True  # Export as zip archive
)
```

**Methods:**
- `generate(analysis, categories=None, corpus=None, metadata=None) -> dict[str, str]`
  - Returns dictionary mapping filename to CSV content
- `save(output_path, analysis, categories=None, corpus=None, metadata=None) -> Path`
  - Saves CSV files and returns path to zip or directory

**Options:**
- `export_as_zip`: If True, creates zip archive; if False, creates directory

#### `DirectoryCSVReportGenerator`
Convenience class for directory output.

```python
generator = DirectoryCSVReportGenerator()
```

## Report Contents

### HTML Report Sections

1. **Summary Statistics** - High-level metrics in colored cards
2. **Sender Analysis** - Top senders and domains with progress bars
3. **Content Clusters** - LLM-named clusters with samples
4. **Temporal Patterns** - Frequency distribution
5. **Subject Patterns** - Common prefixes, keywords, tags
6. **Category Suggestions** - Suggested categories with confidence

### JSON Report Structure

```json
{
  "metadata": {
    "generated_at": "2024-01-15T10:30:00",
    "generator_version": "2.0.0",
    "mailbox_name": "Work Email",
    "total_emails": 5000
  },
  "summary": {
    "total_emails": 5000,
    "unique_senders": 250,
    "content_clusters": 15
  },
  "volume_stats": {...},
  "sender_analysis": {...},
  "content_clusters": [...],
  "temporal_patterns": {...},
  "subject_patterns": {...},
  "categories": [...]
}
```

### CSV Files

Each CSV file contains specific data:

- **summary.csv**: Key-value pairs of overall statistics
- **senders.csv**: Email, Name, Domain, Type, Count, Percentage, Samples
- **domains.csv**: Domain, Count, Percentage
- **clusters.csv**: ID, Name, Size, Percentage, Confidence, Action, Samples, Domains
- **categories.csv**: Name, Description, Confidence, Count, Percentage, Source, Features
- **subject_keywords.csv**: Keyword, Count
- **subject_prefixes.csv**: Prefix, Count
- **temporal_patterns.csv**: Frequency, Count

## Examples

See `/examples/generate_reports.py` for a complete example of generating all report types.

## Integration with CLI

The report generators are integrated into the CLI `report` command:

```bash
# View all options
email-analyzer report --help

# Generate specific format
email-analyzer report --format html
email-analyzer report --format json --pretty
email-analyzer report --format csv --zip

# Generate all formats
email-analyzer report --format all

# Custom output path
email-analyzer report --format html --output ~/my_report.html
```

## Customization

To create a custom report generator:

```python
from src.reports.base import BaseReportGenerator
from pathlib import Path

class CustomReportGenerator(BaseReportGenerator):
    def generate(self, analysis, categories=None, corpus=None, metadata=None):
        # Your custom generation logic
        return "custom content"

    def save(self, output_path, analysis, categories=None, corpus=None, metadata=None):
        content = self.generate(analysis, categories, corpus, metadata)
        output_path.write_text(content)
        return output_path
```

## Future Enhancements

Potential future additions:
- PDF report generation
- Excel workbook export with multiple sheets
- Interactive dashboard (Plotly/Dash)
- Email client integration (Outlook, Thunderbird)
- Comparison reports (before/after)
- Custom templates
- Localization support
