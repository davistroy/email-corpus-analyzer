#!/usr/bin/env python3
"""
Example: Generate reports from analysis results.

This demonstrates how to use the report generation functionality.
"""
import sys
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.analysis_results import (
    AnalysisResults,
    DomainCount,
    SenderAnalysis,
    SubjectPatterns,
    TemporalPatterns,
    VolumeStats,
)
from src.models.category import Category, CategorySource
from src.models.content_cluster import ContentCluster, RepresentativeSample
from src.models.sender import Sender, SenderType
from src.reports import (
    CSVReportGenerator,
    HTMLReportGenerator,
    JSONReportGenerator,
    ReportMetadata,
)


def create_sample_analysis() -> AnalysisResults:
    """Create sample analysis results for demonstration."""

    # Sample senders
    senders = [
        Sender(
            email="newsletter@example.com",
            name="Example Newsletter",
            domain="example.com",
            type=SenderType.MARKETING,
            frequency_count=150,
            sample_subjects=["Weekly Update #1", "Weekly Update #2", "Special Offer"],
            email_ids=["1", "2", "3"],
        ),
        Sender(
            email="support@service.com",
            name="Customer Support",
            domain="service.com",
            type=SenderType.SERVICE,
            frequency_count=75,
            sample_subjects=["Your ticket #123", "Issue resolved", "Follow-up"],
            email_ids=["4", "5", "6"],
        ),
    ]

    # Sample clusters
    clusters = [
        ContentCluster(
            cluster_id=0,
            size=150,
            percentage=30.0,
            representative_samples=[
                RepresentativeSample(
                    subject="Weekly Newsletter - Week 1",
                    sender="newsletter@example.com",
                    body_preview="Check out this week's highlights and updates...",
                ),
                RepresentativeSample(
                    subject="Weekly Newsletter - Week 2",
                    sender="newsletter@example.com",
                    body_preview="Here are the latest news and articles...",
                ),
            ],
            common_domains=[("example.com", 150)],
            email_ids=["1", "2", "3"],
            suggested_name="Marketing Newsletters",
            name_confidence=0.85,
            name_reasoning="Consistent weekly newsletter pattern from marketing domain",
            suggested_action="archive",
        ),
        ContentCluster(
            cluster_id=1,
            size=75,
            percentage=15.0,
            representative_samples=[
                RepresentativeSample(
                    subject="Support Ticket #12345",
                    sender="support@service.com",
                    body_preview="Your support request has been received...",
                ),
            ],
            common_domains=[("service.com", 75)],
            email_ids=["4", "5", "6"],
            suggested_name="Customer Support",
            name_confidence=0.92,
            name_reasoning="Support ticket pattern with consistent domain",
            suggested_action="keep",
        ),
    ]

    # Sample categories
    categories = [
        Category(
            category_id="cat_1",
            category_name="Marketing Newsletters",
            description="Automated marketing emails and newsletters",
            confidence=0.85,
            email_count=150,
            percentage=30.0,
            source=CategorySource.CONTENT_CLUSTER,
            source_id="0",
            user_modified=False,
            distinguishing_features=["Weekly pattern", "Marketing content", "Unsubscribe link"],
            example_email_ids=["1", "2", "3"],
        ),
        Category(
            category_id="cat_2",
            category_name="Customer Support",
            description="Support tickets and service communications",
            confidence=0.92,
            email_count=75,
            percentage=15.0,
            source=CategorySource.CONTENT_CLUSTER,
            source_id="1",
            user_modified=False,
            distinguishing_features=["Ticket numbers", "Support responses", "Issue tracking"],
            example_email_ids=["4", "5", "6"],
        ),
    ]

    # Build analysis results
    return AnalysisResults(
        sender_analysis=SenderAnalysis(
            top_senders=senders,
            top_domains=[
                DomainCount(domain="example.com", count=150),
                DomainCount(domain="service.com", count=75),
            ],
            unique_senders=2,
            unique_domains=2,
        ),
        subject_patterns=SubjectPatterns(
            common_prefixes={"Weekly": 50, "RE:": 25},
            numbered_patterns={"#": 75},
            top_keywords=[("update", 45), ("ticket", 30), ("support", 25)],
            bracket_tags=[("URGENT", 5), ("INFO", 10)],
            total_subjects_analyzed=225,
        ),
        content_clusters=clusters,
        temporal_patterns=TemporalPatterns(
            frequency_distribution={"weekly": 150, "irregular": 75},
            sender_frequencies={},
        ),
        volume_stats=VolumeStats(
            total_emails=500,
            unique_senders=2,
            date_range={"oldest": "2024-01-01", "newest": "2024-12-31", "span_days": "365"},
            with_attachments=50,
            attachment_percentage=10.0,
            avg_body_length_chars=1500,
            emails_per_day=1.37,
        ),
    ), categories


def main():
    """Generate sample reports."""
    print("Generating sample reports...")

    # Create sample data
    analysis, categories = create_sample_analysis()

    # Create metadata
    metadata = ReportMetadata(
        generated_at=datetime.now(),
        generator_version="2.0.0",
        mailbox_name="Example Mailbox",
        mailbox_email="user@example.com",
        total_emails=500,
        date_range="2024-01-01 to 2024-12-31",
    )

    # Output directory
    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True)

    # Generate HTML report
    print("  - Generating HTML report...")
    html_gen = HTMLReportGenerator()
    html_path = html_gen.save(
        output_dir / "sample_report.html",
        analysis,
        categories,
        metadata=metadata,
    )
    print(f"    Saved: {html_path}")

    # Generate JSON report
    print("  - Generating JSON report...")
    json_gen = JSONReportGenerator(pretty=True)
    json_path = json_gen.save(
        output_dir / "sample_report.json",
        analysis,
        categories,
        metadata=metadata,
    )
    print(f"    Saved: {json_path}")

    # Generate CSV reports (zip)
    print("  - Generating CSV reports (zip)...")
    csv_gen = CSVReportGenerator(export_as_zip=True)
    csv_path = csv_gen.save(
        output_dir / "sample_report_csv.zip",
        analysis,
        categories,
        metadata=metadata,
    )
    print(f"    Saved: {csv_path}")

    print(f"\nAll reports saved to: {output_dir}")
    print("\nOpen the HTML report in a browser to see the interactive version!")


if __name__ == "__main__":
    main()
