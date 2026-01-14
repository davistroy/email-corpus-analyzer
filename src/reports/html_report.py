"""
HTML Report Generator.

Generates styled HTML reports with interactive elements and visualizations.
"""
from datetime import datetime
from pathlib import Path

from src.models.analysis_results import AnalysisResults
from src.models.category import Category
from src.models.corpus import Corpus

from .base import BaseReportGenerator, ReportMetadata


class HTMLReportGenerator(BaseReportGenerator):
    """Generate interactive HTML reports with CSS styling and charts."""

    def generate(
        self,
        analysis: AnalysisResults,
        categories: list[Category] | None = None,
        corpus: Corpus | None = None,
        metadata: ReportMetadata | None = None,
    ) -> str:
        """Generate HTML report."""
        meta = self._create_metadata(analysis, metadata)

        html_parts = [
            self._generate_header(meta),
            self._generate_css(),
            "</head><body>",
            self._generate_title(meta),
            self._generate_summary(analysis, meta),
            self._generate_sender_analysis(analysis),
            self._generate_content_clusters(analysis),
            self._generate_temporal_patterns(analysis),
            self._generate_subject_patterns(analysis),
            self._generate_categories(categories) if categories else "",
            self._generate_footer(meta),
            "</body></html>",
        ]

        return "\n".join(html_parts)

    def save(
        self,
        output_path: Path,
        analysis: AnalysisResults,
        categories: list[Category] | None = None,
        corpus: Corpus | None = None,
        metadata: ReportMetadata | None = None,
    ) -> Path:
        """Save HTML report to file."""
        html_content = self.generate(analysis, categories, corpus, metadata)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html_content, encoding="utf-8")
        return output_path

    def _generate_header(self, meta: ReportMetadata) -> str:
        """Generate HTML header."""
        title = f"Email Analysis Report - {meta.mailbox_name or 'Combined'}"
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>"""

    def _generate_css(self) -> str:
        """Generate CSS styling."""
        return """
    <style>
        :root {
            --primary-color: #2563eb;
            --secondary-color: #7c3aed;
            --success-color: #10b981;
            --warning-color: #f59e0b;
            --danger-color: #ef4444;
            --bg-color: #f8fafc;
            --card-bg: #ffffff;
            --text-color: #1e293b;
            --text-muted: #64748b;
            --border-color: #e2e8f0;
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: var(--text-color);
            background: var(--bg-color);
            padding: 2rem;
        }

        .container {
            max-width: 1200px;
            margin: 0 auto;
        }

        h1 {
            font-size: 2.5rem;
            font-weight: 700;
            margin-bottom: 0.5rem;
            color: var(--primary-color);
        }

        h2 {
            font-size: 1.75rem;
            font-weight: 600;
            margin: 2rem 0 1rem;
            color: var(--text-color);
            border-bottom: 2px solid var(--primary-color);
            padding-bottom: 0.5rem;
        }

        h3 {
            font-size: 1.25rem;
            font-weight: 600;
            margin: 1.5rem 0 1rem;
            color: var(--text-color);
        }

        .metadata {
            color: var(--text-muted);
            margin-bottom: 2rem;
            font-size: 0.95rem;
        }

        .card {
            background: var(--card-bg);
            border-radius: 0.5rem;
            padding: 1.5rem;
            margin-bottom: 1.5rem;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
        }

        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
            margin-bottom: 2rem;
        }

        .stat-card {
            background: linear-gradient(135deg, var(--primary-color), var(--secondary-color));
            color: white;
            padding: 1.5rem;
            border-radius: 0.5rem;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }

        .stat-value {
            font-size: 2rem;
            font-weight: 700;
            display: block;
        }

        .stat-label {
            font-size: 0.875rem;
            opacity: 0.9;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }

        table {
            width: 100%;
            border-collapse: collapse;
            margin: 1rem 0;
        }

        th {
            background: var(--primary-color);
            color: white;
            padding: 0.75rem;
            text-align: left;
            font-weight: 600;
        }

        td {
            padding: 0.75rem;
            border-bottom: 1px solid var(--border-color);
        }

        tr:hover {
            background: var(--bg-color);
        }

        .progress-bar {
            background: var(--border-color);
            height: 1.5rem;
            border-radius: 0.25rem;
            overflow: hidden;
            margin: 0.5rem 0;
        }

        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, var(--primary-color), var(--secondary-color));
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-size: 0.75rem;
            font-weight: 600;
            transition: width 0.3s ease;
        }

        .badge {
            display: inline-block;
            padding: 0.25rem 0.75rem;
            border-radius: 9999px;
            font-size: 0.875rem;
            font-weight: 500;
        }

        .badge-primary { background: var(--primary-color); color: white; }
        .badge-success { background: var(--success-color); color: white; }
        .badge-warning { background: var(--warning-color); color: white; }
        .badge-danger { background: var(--danger-color); color: white; }

        .collapsible {
            cursor: pointer;
            user-select: none;
        }

        .collapsible:hover {
            opacity: 0.8;
        }

        .collapsible::before {
            content: '▼ ';
            display: inline-block;
            transition: transform 0.2s;
        }

        .collapsible.collapsed::before {
            transform: rotate(-90deg);
        }

        .collapsible-content {
            max-height: 1000px;
            overflow: hidden;
            transition: max-height 0.3s ease;
        }

        .collapsible-content.hidden {
            max-height: 0;
        }

        .footer {
            margin-top: 3rem;
            padding-top: 2rem;
            border-top: 1px solid var(--border-color);
            text-align: center;
            color: var(--text-muted);
            font-size: 0.875rem;
        }

        @media print {
            body {
                background: white;
                padding: 0;
            }
            .card {
                box-shadow: none;
                border: 1px solid var(--border-color);
            }
            .collapsible-content {
                max-height: none !important;
            }
        }
    </style>
    <script>
        function toggleCollapsible(id) {
            const header = document.getElementById('header-' + id);
            const content = document.getElementById('content-' + id);

            if (header && content) {
                header.classList.toggle('collapsed');
                content.classList.toggle('hidden');
            }
        }

        document.addEventListener('DOMContentLoaded', function() {
            // Add click handlers to all collapsibles
            document.querySelectorAll('.collapsible').forEach(el => {
                el.addEventListener('click', function() {
                    const id = this.id.replace('header-', '');
                    toggleCollapsible(id);
                });
            });
        });
    </script>"""

    def _generate_title(self, meta: ReportMetadata) -> str:
        """Generate report title section."""
        title = "Email Analysis Report"
        if meta.mailbox_name:
            title += f" - {meta.mailbox_name}"

        metadata_lines = [
            f"<div class='metadata'>",
            f"Generated: {self._format_date(meta.generated_at)}",
        ]

        if meta.mailbox_email:
            metadata_lines.append(f" | Mailbox: {meta.mailbox_email}")

        if meta.date_range:
            metadata_lines.append(f" | Date Range: {meta.date_range}")

        metadata_lines.append("</div>")

        return f"""<div class="container">
    <h1>{title}</h1>
    {"".join(metadata_lines)}"""

    def _generate_summary(self, analysis: AnalysisResults, meta: ReportMetadata) -> str:
        """Generate summary statistics."""
        stats = analysis.volume_stats

        return f"""
    <h2>Summary Statistics</h2>
    <div class="stats-grid">
        <div class="stat-card">
            <span class="stat-value">{self._format_number(stats.total_emails)}</span>
            <span class="stat-label">Total Emails</span>
        </div>
        <div class="stat-card">
            <span class="stat-value">{self._format_number(stats.unique_senders)}</span>
            <span class="stat-label">Unique Senders</span>
        </div>
        <div class="stat-card">
            <span class="stat-value">{self._format_number(len(analysis.content_clusters))}</span>
            <span class="stat-label">Content Clusters</span>
        </div>
        <div class="stat-card">
            <span class="stat-value">{self._format_percentage(stats.attachment_percentage)}</span>
            <span class="stat-label">With Attachments</span>
        </div>
        <div class="stat-card">
            <span class="stat-value">{self._format_number(int(stats.emails_per_day))}</span>
            <span class="stat-label">Emails/Day</span>
        </div>
        <div class="stat-card">
            <span class="stat-value">{self._format_number(stats.avg_body_length_chars)}</span>
            <span class="stat-label">Avg Body Length</span>
        </div>
    </div>"""

    def _generate_sender_analysis(self, analysis: AnalysisResults) -> str:
        """Generate sender analysis section."""
        sender_analysis = analysis.sender_analysis

        html = [
            "<h2 id='header-senders' class='collapsible'>Sender Analysis</h2>",
            "<div id='content-senders' class='collapsible-content'>",
            "<div class='card'>",
            f"<p><strong>Unique Senders:</strong> {self._format_number(sender_analysis.unique_senders)}</p>",
            f"<p><strong>Unique Domains:</strong> {self._format_number(sender_analysis.unique_domains)}</p>",
        ]

        # Top senders table
        if sender_analysis.top_senders:
            html.append("<h3>Top Senders</h3>")
            html.append("<table>")
            html.append("<thead><tr><th>Sender</th><th>Domain</th><th>Type</th><th>Count</th><th>Percentage</th></tr></thead>")
            html.append("<tbody>")

            total_emails = analysis.volume_stats.total_emails
            for sender in sender_analysis.top_senders[:20]:
                percentage = (sender.frequency_count / total_emails * 100) if total_emails > 0 else 0
                type_badge = f"<span class='badge badge-primary'>{sender.type.value}</span>"

                html.append(f"""
                <tr>
                    <td>{sender.name or sender.email}</td>
                    <td>{sender.domain}</td>
                    <td>{type_badge}</td>
                    <td>{self._format_number(sender.frequency_count)}</td>
                    <td>
                        <div class='progress-bar'>
                            <div class='progress-fill' style='width: {percentage}%'>
                                {self._format_percentage(percentage)}
                            </div>
                        </div>
                    </td>
                </tr>""")

            html.append("</tbody></table>")

        # Top domains table
        if sender_analysis.top_domains:
            html.append("<h3>Top Domains</h3>")
            html.append("<table>")
            html.append("<thead><tr><th>Domain</th><th>Count</th><th>Percentage</th></tr></thead>")
            html.append("<tbody>")

            total_emails = analysis.volume_stats.total_emails
            for domain in sender_analysis.top_domains[:15]:
                percentage = (domain.count / total_emails * 100) if total_emails > 0 else 0

                html.append(f"""
                <tr>
                    <td>{domain.domain}</td>
                    <td>{self._format_number(domain.count)}</td>
                    <td>
                        <div class='progress-bar'>
                            <div class='progress-fill' style='width: {percentage}%'>
                                {self._format_percentage(percentage)}
                            </div>
                        </div>
                    </td>
                </tr>""")

            html.append("</tbody></table>")

        html.append("</div></div>")
        return "\n".join(html)

    def _generate_content_clusters(self, analysis: AnalysisResults) -> str:
        """Generate content clusters section."""
        html = [
            "<h2 id='header-clusters' class='collapsible'>Content Clusters</h2>",
            "<div id='content-clusters' class='collapsible-content'>",
        ]

        for cluster in analysis.content_clusters:
            confidence_class = "success" if (cluster.name_confidence or 0) > 0.7 else "warning"

            html.append("<div class='card'>")
            html.append(f"<h3>{cluster.display_name}</h3>")
            html.append(f"<p><strong>Size:</strong> {self._format_number(cluster.size)} emails ({self._format_percentage(cluster.percentage)})</p>")

            if cluster.name_confidence is not None:
                html.append(f"<p><strong>Confidence:</strong> <span class='badge badge-{confidence_class}'>{self._format_percentage(cluster.name_confidence * 100)}</span></p>")

            if cluster.name_reasoning:
                html.append(f"<p><strong>Reasoning:</strong> {cluster.name_reasoning}</p>")

            if cluster.suggested_action:
                html.append(f"<p><strong>Suggested Action:</strong> <span class='badge badge-primary'>{cluster.suggested_action}</span></p>")

            # Representative samples
            if cluster.representative_samples:
                html.append("<h4>Representative Samples</h4>")
                html.append("<ul>")
                for sample in cluster.representative_samples[:3]:
                    html.append(f"<li><strong>{sample.subject}</strong> - {sample.sender}<br><em>{sample.body_preview}</em></li>")
                html.append("</ul>")

            # Common domains
            if cluster.common_domains:
                html.append("<p><strong>Common Domains:</strong> ")
                domain_badges = [f"<span class='badge badge-primary'>{d[0]} ({d[1]})</span>" for d in cluster.common_domains[:5]]
                html.append(" ".join(domain_badges))
                html.append("</p>")

            html.append("</div>")

        html.append("</div>")
        return "\n".join(html)

    def _generate_temporal_patterns(self, analysis: AnalysisResults) -> str:
        """Generate temporal patterns section."""
        temporal = analysis.temporal_patterns

        html = [
            "<h2 id='header-temporal' class='collapsible'>Temporal Patterns</h2>",
            "<div id='content-temporal' class='collapsible-content'>",
            "<div class='card'>",
            "<h3>Frequency Distribution</h3>",
            "<table>",
            "<thead><tr><th>Frequency</th><th>Count</th></tr></thead>",
            "<tbody>",
        ]

        for freq, count in sorted(temporal.frequency_distribution.items(), key=lambda x: x[1], reverse=True):
            html.append(f"<tr><td>{freq.title()}</td><td>{self._format_number(count)}</td></tr>")

        html.append("</tbody></table>")
        html.append("</div></div>")

        return "\n".join(html)

    def _generate_subject_patterns(self, analysis: AnalysisResults) -> str:
        """Generate subject patterns section."""
        subject = analysis.subject_patterns

        html = [
            "<h2 id='header-subjects' class='collapsible'>Subject Patterns</h2>",
            "<div id='content-subjects' class='collapsible-content'>",
            "<div class='card'>",
        ]

        # Common prefixes
        if subject.common_prefixes:
            html.append("<h3>Common Prefixes</h3>")
            html.append("<table>")
            html.append("<thead><tr><th>Prefix</th><th>Count</th></tr></thead>")
            html.append("<tbody>")
            for prefix, count in sorted(subject.common_prefixes.items(), key=lambda x: x[1], reverse=True)[:10]:
                html.append(f"<tr><td>{prefix}</td><td>{self._format_number(count)}</td></tr>")
            html.append("</tbody></table>")

        # Top keywords
        if subject.top_keywords:
            html.append("<h3>Top Keywords</h3>")
            keyword_badges = [f"<span class='badge badge-primary'>{kw[0]} ({kw[1]})</span>" for kw in subject.top_keywords[:20]]
            html.append("<p>" + " ".join(keyword_badges) + "</p>")

        # Bracket tags
        if subject.bracket_tags:
            html.append("<h3>Bracket Tags</h3>")
            tag_badges = [f"<span class='badge badge-warning'>[{tag[0]}] ({tag[1]})</span>" for tag in subject.bracket_tags[:15]]
            html.append("<p>" + " ".join(tag_badges) + "</p>")

        html.append("</div></div>")
        return "\n".join(html)

    def _generate_categories(self, categories: list[Category]) -> str:
        """Generate categories section."""
        html = [
            "<h2 id='header-categories' class='collapsible'>Category Suggestions</h2>",
            "<div id='content-categories' class='collapsible-content'>",
        ]

        for i, category in enumerate(categories, 1):
            confidence_class = "success" if category.confidence > 0.7 else "warning" if category.confidence > 0.4 else "danger"
            source_class = "primary" if category.source.value == "llm_suggested" else "success"

            html.append("<div class='card'>")
            html.append(f"<h3>{i}. {category.category_name}</h3>")
            html.append(f"<p>{category.description}</p>")
            html.append(f"<p><strong>Confidence:</strong> <span class='badge badge-{confidence_class}'>{self._format_percentage(category.confidence * 100)}</span></p>")
            html.append(f"<p><strong>Source:</strong> <span class='badge badge-{source_class}'>{category.source.value}</span></p>")

            if category.email_count is not None:
                html.append(f"<p><strong>Emails:</strong> {self._format_number(category.email_count)} ({self._format_percentage(category.percentage or 0)})</p>")

            if category.distinguishing_features:
                html.append("<p><strong>Key Features:</strong></p><ul>")
                for feature in category.distinguishing_features[:5]:
                    html.append(f"<li>{feature}</li>")
                html.append("</ul>")

            html.append("</div>")

        html.append("</div>")
        return "\n".join(html)

    def _generate_footer(self, meta: ReportMetadata) -> str:
        """Generate footer."""
        return f"""
    <div class='footer'>
        <p>Generated by Email Corpus Analyzer v{meta.generator_version}</p>
        <p>{self._format_date(meta.generated_at)}</p>
    </div>
</div>"""
