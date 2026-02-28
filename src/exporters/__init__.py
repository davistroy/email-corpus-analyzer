"""
Exporters module for Email Corpus Analyzer (Track 5C: Export & Polish).

Provides export functionality for category data:
- CSV export with configurable delimiters and UTF-8 BOM for Excel
- HTML report generation with inline CSS and visualizations
- Phase 8 Track 8B.3: Outlook rules and Gmail filter export
"""

from src.exporters.csv_exporter import export_categories_to_csv
from src.exporters.html_exporter import export_categories_to_html
from src.exporters.rule_exporter import GmailFilterExporter, OutlookRuleExporter

__all__ = [
    "export_categories_to_csv",
    "export_categories_to_html",
    "OutlookRuleExporter",
    "GmailFilterExporter",
]
