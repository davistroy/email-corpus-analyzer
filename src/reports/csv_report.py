"""
CSV Report Generator.

Exports analysis data as CSV files for spreadsheet analysis.
"""
import csv
import zipfile
from pathlib import Path

from src.models.analysis_results import AnalysisResults
from src.models.category import Category
from src.models.corpus import Corpus

from .base import BaseReportGenerator, ReportMetadata


class CSVReportGenerator(BaseReportGenerator):
    """
    Generate CSV reports with multiple files.

    Creates separate CSV files for:
    - Senders analysis
    - Content clusters
    - Category suggestions
    - Subject patterns
    - Temporal patterns

    Can export as individual files in a directory or as a zip archive.
    """

    def __init__(self, export_as_zip: bool = True):
        """
        Initialize CSV report generator.

        Args:
            export_as_zip: Whether to create a zip archive (default: True).
                          If False, creates a directory with separate CSV files.
        """
        super().__init__()
        self.export_as_zip = export_as_zip

    def generate(
        self,
        analysis: AnalysisResults,
        categories: list[Category] | None = None,
        corpus: Corpus | None = None,
        metadata: ReportMetadata | None = None,
    ) -> dict[str, str]:
        """
        Generate CSV content for each report section.

        Returns:
            Dictionary mapping filename to CSV content.
        """
        meta = self._create_metadata(analysis, metadata)

        csv_files = {}

        # Generate each CSV file
        csv_files["summary.csv"] = self._generate_summary_csv(analysis, meta)
        csv_files["senders.csv"] = self._generate_senders_csv(analysis)
        csv_files["domains.csv"] = self._generate_domains_csv(analysis)
        csv_files["clusters.csv"] = self._generate_clusters_csv(analysis)
        csv_files["subject_keywords.csv"] = self._generate_keywords_csv(analysis)
        csv_files["subject_prefixes.csv"] = self._generate_prefixes_csv(analysis)
        csv_files["temporal_patterns.csv"] = self._generate_temporal_csv(analysis)

        if categories:
            csv_files["categories.csv"] = self._generate_categories_csv(categories)

        return csv_files

    def save(
        self,
        output_path: Path,
        analysis: AnalysisResults,
        categories: list[Category] | None = None,
        corpus: Corpus | None = None,
        metadata: ReportMetadata | None = None,
    ) -> Path:
        """
        Save CSV reports to file or directory.

        Args:
            output_path: Path to zip file or directory.

        Returns:
            Path to created file or directory.
        """
        csv_files = self.generate(analysis, categories, corpus, metadata)

        if self.export_as_zip:
            # Create zip archive
            if not str(output_path).endswith('.zip'):
                output_path = output_path.with_suffix('.zip')

            output_path.parent.mkdir(parents=True, exist_ok=True)

            with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for filename, content in csv_files.items():
                    zipf.writestr(filename, content)

            return output_path
        else:
            # Create directory with separate CSV files
            output_path.mkdir(parents=True, exist_ok=True)

            for filename, content in csv_files.items():
                file_path = output_path / filename
                file_path.write_text(content, encoding="utf-8")

            return output_path

    def _generate_summary_csv(self, analysis: AnalysisResults, meta: ReportMetadata) -> str:
        """Generate summary statistics CSV."""
        rows = [
            ["Metric", "Value"],
            ["Generated At", self._format_date(meta.generated_at)],
            ["Generator Version", meta.generator_version],
        ]

        if meta.mailbox_name:
            rows.append(["Mailbox Name", meta.mailbox_name])
        if meta.mailbox_email:
            rows.append(["Mailbox Email", meta.mailbox_email])
        if meta.date_range:
            rows.append(["Date Range", meta.date_range])

        rows.extend([
            ["", ""],  # Blank row
            ["Total Emails", str(analysis.volume_stats.total_emails)],
            ["Unique Senders", str(analysis.volume_stats.unique_senders)],
            ["Unique Domains", str(analysis.sender_analysis.unique_domains)],
            ["Content Clusters", str(len(analysis.content_clusters))],
            ["With Attachments", str(analysis.volume_stats.with_attachments)],
            ["Attachment Percentage", f"{analysis.volume_stats.attachment_percentage:.2f}%"],
            ["Emails Per Day", f"{analysis.volume_stats.emails_per_day:.2f}"],
            ["Average Body Length", str(analysis.volume_stats.avg_body_length_chars)],
        ])

        return self._rows_to_csv(rows)

    def _generate_senders_csv(self, analysis: AnalysisResults) -> str:
        """Generate senders analysis CSV."""
        rows = [
            ["Email", "Name", "Domain", "Type", "Count", "Percentage", "Sample Subjects"],
        ]

        total_emails = analysis.volume_stats.total_emails

        for sender in analysis.sender_analysis.top_senders:
            percentage = (sender.frequency_count / total_emails * 100) if total_emails > 0 else 0
            sample_subjects = "; ".join(sender.sample_subjects[:3])

            rows.append([
                sender.email,
                sender.name or "",
                sender.domain,
                sender.type.value,
                str(sender.frequency_count),
                f"{percentage:.2f}%",
                sample_subjects,
            ])

        return self._rows_to_csv(rows)

    def _generate_domains_csv(self, analysis: AnalysisResults) -> str:
        """Generate domains analysis CSV."""
        rows = [
            ["Domain", "Count", "Percentage"],
        ]

        total_emails = analysis.volume_stats.total_emails

        for domain in analysis.sender_analysis.top_domains:
            percentage = (domain.count / total_emails * 100) if total_emails > 0 else 0

            rows.append([
                domain.domain,
                str(domain.count),
                f"{percentage:.2f}%",
            ])

        return self._rows_to_csv(rows)

    def _generate_clusters_csv(self, analysis: AnalysisResults) -> str:
        """Generate content clusters CSV."""
        rows = [
            ["Cluster ID", "Name", "Size", "Percentage", "Confidence", "Action",
             "Representative Subjects", "Common Domains"],
        ]

        for cluster in analysis.content_clusters:
            subjects = "; ".join([s.subject for s in cluster.representative_samples[:3]])
            domains = "; ".join([f"{d[0]} ({d[1]})" for d in cluster.common_domains[:3]])
            confidence = f"{cluster.name_confidence * 100:.1f}%" if cluster.name_confidence is not None else "N/A"

            rows.append([
                str(cluster.cluster_id),
                cluster.display_name,
                str(cluster.size),
                f"{cluster.percentage:.2f}%",
                confidence,
                cluster.suggested_action or "N/A",
                subjects,
                domains,
            ])

        return self._rows_to_csv(rows)

    def _generate_keywords_csv(self, analysis: AnalysisResults) -> str:
        """Generate subject keywords CSV."""
        rows = [
            ["Keyword", "Count"],
        ]

        for keyword, count in analysis.subject_patterns.top_keywords:
            rows.append([keyword, str(count)])

        return self._rows_to_csv(rows)

    def _generate_prefixes_csv(self, analysis: AnalysisResults) -> str:
        """Generate subject prefixes CSV."""
        rows = [
            ["Prefix", "Count"],
        ]

        for prefix, count in sorted(
            analysis.subject_patterns.common_prefixes.items(),
            key=lambda x: x[1],
            reverse=True
        ):
            rows.append([prefix, str(count)])

        return self._rows_to_csv(rows)

    def _generate_temporal_csv(self, analysis: AnalysisResults) -> str:
        """Generate temporal patterns CSV."""
        rows = [
            ["Frequency Pattern", "Count"],
        ]

        for freq, count in sorted(
            analysis.temporal_patterns.frequency_distribution.items(),
            key=lambda x: x[1],
            reverse=True
        ):
            rows.append([freq, str(count)])

        return self._rows_to_csv(rows)

    def _generate_categories_csv(self, categories: list[Category]) -> str:
        """Generate category suggestions CSV."""
        rows = [
            ["Category Name", "Description", "Confidence", "Email Count", "Percentage",
             "Source", "Features"],
        ]

        for category in categories:
            features = "; ".join(category.distinguishing_features[:3])
            confidence = f"{category.confidence * 100:.1f}%"
            percentage = f"{category.percentage:.2f}%" if category.percentage is not None else "N/A"

            rows.append([
                category.category_name,
                category.description,
                confidence,
                str(category.email_count or "N/A"),
                percentage,
                category.source.value,
                features,
            ])

        return self._rows_to_csv(rows)

    def _rows_to_csv(self, rows: list[list[str]]) -> str:
        """Convert rows to CSV string."""
        import io
        output = io.StringIO()
        writer = csv.writer(output, lineterminator='\n')
        writer.writerows(rows)
        return output.getvalue()


class DirectoryCSVReportGenerator(CSVReportGenerator):
    """Generate CSV reports as separate files in a directory."""

    def __init__(self):
        """Initialize directory CSV generator."""
        super().__init__(export_as_zip=False)
