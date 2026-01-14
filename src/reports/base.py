"""
Base protocol and interfaces for report generators.

Provides a common interface for different report formats (HTML, JSON, CSV, etc.).
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol

from src.models.analysis_results import AnalysisResults
from src.models.category import Category
from src.models.corpus import Corpus


@dataclass
class ReportMetadata:
    """Metadata included in all reports."""

    generated_at: datetime
    generator_version: str = "2.0.0"
    mailbox_name: str | None = None
    mailbox_email: str | None = None
    total_emails: int = 0
    date_range: str | None = None


class ReportGenerator(Protocol):
    """Protocol for report generators."""

    def generate(
        self,
        analysis: AnalysisResults,
        categories: list[Category] | None = None,
        corpus: Corpus | None = None,
        metadata: ReportMetadata | None = None,
    ) -> str | bytes | dict:
        """
        Generate a report from analysis results.

        Args:
            analysis: Analysis results to include in report.
            categories: Optional category suggestions to include.
            corpus: Optional corpus for additional context.
            metadata: Optional metadata to include in report.

        Returns:
            Report content (format depends on generator type).
        """
        ...

    def save(
        self,
        output_path: Path,
        analysis: AnalysisResults,
        categories: list[Category] | None = None,
        corpus: Corpus | None = None,
        metadata: ReportMetadata | None = None,
    ) -> Path:
        """
        Generate and save report to file.

        Args:
            output_path: Path where report should be saved.
            analysis: Analysis results to include in report.
            categories: Optional category suggestions to include.
            corpus: Optional corpus for additional context.
            metadata: Optional metadata to include in report.

        Returns:
            Path to saved report file.
        """
        ...


class BaseReportGenerator(ABC):
    """
    Abstract base class for report generators.

    Provides common utilities for all report types.
    """

    def __init__(self):
        """Initialize report generator."""
        self.version = "2.0.0"

    def _create_metadata(
        self,
        analysis: AnalysisResults,
        custom_metadata: ReportMetadata | None = None,
    ) -> ReportMetadata:
        """Create report metadata."""
        if custom_metadata:
            return custom_metadata

        date_range = None
        if analysis.volume_stats.date_range:
            oldest = analysis.volume_stats.date_range.get("oldest", "")
            newest = analysis.volume_stats.date_range.get("newest", "")
            if oldest and newest:
                date_range = f"{oldest} to {newest}"

        return ReportMetadata(
            generated_at=datetime.now(),
            generator_version=self.version,
            total_emails=analysis.volume_stats.total_emails,
            date_range=date_range,
        )

    @abstractmethod
    def generate(
        self,
        analysis: AnalysisResults,
        categories: list[Category] | None = None,
        corpus: Corpus | None = None,
        metadata: ReportMetadata | None = None,
    ) -> str | bytes | dict:
        """Generate report content."""
        ...

    @abstractmethod
    def save(
        self,
        output_path: Path,
        analysis: AnalysisResults,
        categories: list[Category] | None = None,
        corpus: Corpus | None = None,
        metadata: ReportMetadata | None = None,
    ) -> Path:
        """Save report to file."""
        ...

    def _format_number(self, num: int | float) -> str:
        """Format number with thousands separators."""
        return f"{num:,}"

    def _format_percentage(self, value: float) -> str:
        """Format percentage value."""
        return f"{value:.1f}%"

    def _format_date(self, dt: datetime | str) -> str:
        """Format datetime for display."""
        if isinstance(dt, str):
            return dt
        return dt.strftime("%Y-%m-%d %H:%M:%S")
