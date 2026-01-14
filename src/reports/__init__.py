"""
Report generation module.

Provides multiple report formats for email corpus analysis results:
- HTML: Interactive reports with styling and visualizations
- JSON: Structured data export with metadata
- CSV: Tabular data for spreadsheet analysis

Usage:
    from src.reports import HTMLReportGenerator, JSONReportGenerator, CSVReportGenerator

    # Generate HTML report
    html_gen = HTMLReportGenerator()
    html_gen.save(output_path, analysis_results, categories)

    # Generate JSON report
    json_gen = JSONReportGenerator(pretty=True)
    json_gen.save(output_path, analysis_results, categories)

    # Generate CSV reports
    csv_gen = CSVReportGenerator(export_as_zip=True)
    csv_gen.save(output_path, analysis_results, categories)
"""
from .base import BaseReportGenerator, ReportGenerator, ReportMetadata
from .csv_report import CSVReportGenerator, DirectoryCSVReportGenerator
from .html_report import HTMLReportGenerator
from .json_report import CompactJSONReportGenerator, JSONReportGenerator

__all__ = [
    # Base classes
    "ReportGenerator",
    "BaseReportGenerator",
    "ReportMetadata",
    # HTML
    "HTMLReportGenerator",
    # JSON
    "JSONReportGenerator",
    "CompactJSONReportGenerator",
    # CSV
    "CSVReportGenerator",
    "DirectoryCSVReportGenerator",
]
