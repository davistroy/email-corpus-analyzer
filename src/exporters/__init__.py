"""
Exporters module for Email Corpus Analyzer (Track 5C: Export & Polish).

Provides export functionality for category data:
- CSV export with configurable delimiters and UTF-8 BOM for Excel
- HTML report generation with inline CSS and visualizations
"""
from src.exporters.csv_exporter import export_categories_to_csv
from src.exporters.html_exporter import export_categories_to_html

__all__ = [
    "export_categories_to_csv",
    "export_categories_to_html",
]
