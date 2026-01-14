"""
JSON Report Generator.

Exports analysis results and categories as structured JSON with metadata.
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from src.models.analysis_results import AnalysisResults
from src.models.category import Category
from src.models.corpus import Corpus

from .base import BaseReportGenerator, ReportMetadata


class JSONReportGenerator(BaseReportGenerator):
    """Generate structured JSON reports with full analysis data."""

    def __init__(self, pretty: bool = True, include_email_ids: bool = False):
        """
        Initialize JSON report generator.

        Args:
            pretty: Whether to pretty-print JSON (default: True).
            include_email_ids: Whether to include email ID lists (default: False).
        """
        super().__init__()
        self.pretty = pretty
        self.include_email_ids = include_email_ids

    def generate(
        self,
        analysis: AnalysisResults,
        categories: list[Category] | None = None,
        corpus: Corpus | None = None,
        metadata: ReportMetadata | None = None,
    ) -> dict[str, Any]:
        """Generate JSON report as dictionary."""
        meta = self._create_metadata(analysis, metadata)

        report = {
            "metadata": self._serialize_metadata(meta),
            "summary": self._generate_summary(analysis),
            "volume_stats": self._serialize_volume_stats(analysis.volume_stats),
            "sender_analysis": self._serialize_sender_analysis(analysis.sender_analysis),
            "content_clusters": self._serialize_clusters(analysis.content_clusters),
            "temporal_patterns": self._serialize_temporal_patterns(analysis.temporal_patterns),
            "subject_patterns": self._serialize_subject_patterns(analysis.subject_patterns),
        }

        if categories:
            report["categories"] = self._serialize_categories(categories)

        if corpus:
            report["corpus_metadata"] = self._serialize_corpus_metadata(corpus)

        return report

    def save(
        self,
        output_path: Path,
        analysis: AnalysisResults,
        categories: list[Category] | None = None,
        corpus: Corpus | None = None,
        metadata: ReportMetadata | None = None,
    ) -> Path:
        """Save JSON report to file."""
        report = self.generate(analysis, categories, corpus, metadata)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            if self.pretty:
                json.dump(report, f, indent=2, ensure_ascii=False, default=str)
            else:
                json.dump(report, f, ensure_ascii=False, default=str)

        return output_path

    def _serialize_metadata(self, meta: ReportMetadata) -> dict[str, Any]:
        """Serialize report metadata."""
        return {
            "generated_at": meta.generated_at.isoformat(),
            "generator_version": meta.generator_version,
            "mailbox_name": meta.mailbox_name,
            "mailbox_email": meta.mailbox_email,
            "total_emails": meta.total_emails,
            "date_range": meta.date_range,
        }

    def _generate_summary(self, analysis: AnalysisResults) -> dict[str, Any]:
        """Generate summary statistics."""
        return {
            "total_emails": analysis.volume_stats.total_emails,
            "unique_senders": analysis.volume_stats.unique_senders,
            "content_clusters": len(analysis.content_clusters),
            "with_attachments": analysis.volume_stats.with_attachments,
            "attachment_percentage": round(analysis.volume_stats.attachment_percentage, 2),
            "emails_per_day": round(analysis.volume_stats.emails_per_day, 2),
            "avg_body_length": analysis.volume_stats.avg_body_length_chars,
        }

    def _serialize_volume_stats(self, stats) -> dict[str, Any]:
        """Serialize volume statistics."""
        return {
            "total_emails": stats.total_emails,
            "unique_senders": stats.unique_senders,
            "date_range": stats.date_range,
            "with_attachments": stats.with_attachments,
            "attachment_percentage": round(stats.attachment_percentage, 2),
            "avg_body_length_chars": stats.avg_body_length_chars,
            "emails_per_day": round(stats.emails_per_day, 2),
        }

    def _serialize_sender_analysis(self, sender_analysis) -> dict[str, Any]:
        """Serialize sender analysis."""
        return {
            "unique_senders": sender_analysis.unique_senders,
            "unique_domains": sender_analysis.unique_domains,
            "top_senders": [
                {
                    "email": sender.email,
                    "name": sender.name,
                    "domain": sender.domain,
                    "type": sender.type.value,
                    "frequency_count": sender.frequency_count,
                    "sample_subjects": sender.sample_subjects,
                    "email_ids": sender.email_ids if self.include_email_ids else [],
                }
                for sender in sender_analysis.top_senders
            ],
            "top_domains": [
                {
                    "domain": domain.domain,
                    "count": domain.count,
                }
                for domain in sender_analysis.top_domains
            ],
        }

    def _serialize_clusters(self, clusters) -> list[dict[str, Any]]:
        """Serialize content clusters."""
        return [
            {
                "cluster_id": cluster.cluster_id,
                "name": cluster.display_name,
                "size": cluster.size,
                "percentage": round(cluster.percentage, 2),
                "confidence": round(cluster.name_confidence, 3) if cluster.name_confidence is not None else None,
                "reasoning": cluster.name_reasoning,
                "suggested_action": cluster.suggested_action,
                "representative_samples": [
                    {
                        "subject": sample.subject,
                        "sender": sample.sender,
                        "body_preview": sample.body_preview,
                    }
                    for sample in cluster.representative_samples
                ],
                "common_domains": [
                    {"domain": domain[0], "count": domain[1]}
                    for domain in cluster.common_domains
                ],
                "email_ids": cluster.email_ids if self.include_email_ids else [],
            }
            for cluster in clusters
        ]

    def _serialize_temporal_patterns(self, temporal) -> dict[str, Any]:
        """Serialize temporal patterns."""
        return {
            "frequency_distribution": temporal.frequency_distribution,
            "sender_frequencies": temporal.sender_frequencies if hasattr(temporal, 'sender_frequencies') else {},
        }

    def _serialize_subject_patterns(self, subject) -> dict[str, Any]:
        """Serialize subject patterns."""
        return {
            "total_subjects_analyzed": subject.total_subjects_analyzed,
            "common_prefixes": subject.common_prefixes,
            "numbered_patterns": subject.numbered_patterns,
            "top_keywords": [
                {"keyword": kw[0], "count": kw[1]}
                for kw in subject.top_keywords
            ],
            "bracket_tags": [
                {"tag": tag[0], "count": tag[1]}
                for tag in subject.bracket_tags
            ],
        }

    def _serialize_categories(self, categories: list[Category]) -> list[dict[str, Any]]:
        """Serialize category suggestions."""
        return [
            {
                "category_id": cat.category_id,
                "category_name": cat.category_name,
                "description": cat.description,
                "confidence": round(cat.confidence, 3),
                "email_count": cat.email_count,
                "percentage": round(cat.percentage, 2) if cat.percentage is not None else None,
                "source": cat.source.value,
                "source_id": cat.source_id,
                "user_modified": cat.user_modified,
                "distinguishing_features": cat.distinguishing_features,
                "example_email_ids": cat.example_email_ids if self.include_email_ids else [],
            }
            for cat in categories
        ]

    def _serialize_corpus_metadata(self, corpus: Corpus) -> dict[str, Any]:
        """Serialize corpus metadata."""
        return {
            "user_email": corpus.user_email,
            "extracted_at": corpus.extraction_metadata.extracted_at.isoformat() if hasattr(corpus.extraction_metadata, 'extracted_at') else None,
            "total_emails": corpus.extraction_metadata.total_emails if hasattr(corpus.extraction_metadata, 'total_emails') else len(corpus.emails),
            "provider": corpus.extraction_metadata.provider if hasattr(corpus.extraction_metadata, 'provider') else "unknown",
        }


class CompactJSONReportGenerator(JSONReportGenerator):
    """Generate compact (minified) JSON reports."""

    def __init__(self, include_email_ids: bool = False):
        """Initialize compact JSON generator."""
        super().__init__(pretty=False, include_email_ids=include_email_ids)
