"""
AnalysisResults data model.

Per data-model.md lines 217-253.
"""
from pydantic import BaseModel

from .content_cluster import ContentCluster
from .sender import Sender


class DomainCount(BaseModel):
    """Domain frequency count."""
    domain: str
    count: int


class SenderAnalysis(BaseModel):
    """Results from sender pattern analysis."""

    top_senders: list[Sender]
    top_domains: list[DomainCount]  # [{"domain": "example.com", "count": 45}]
    unique_senders: int
    unique_domains: int


class SubjectPatterns(BaseModel):
    """Results from subject line pattern analysis."""

    common_prefixes: dict[str, int]  # {"RE:": 45, "FWD:": 23}
    numbered_patterns: dict[str, int]  # {"Invoice": 12, "Order": 34}
    top_keywords: list[tuple[str, int]]  # [("meeting", 45), ("update", 38)]
    bracket_tags: list[tuple[str, int]]  # [("URGENT", 12), ("Team", 8)]
    total_subjects_analyzed: int


class TemporalPatterns(BaseModel):
    """Results from temporal pattern analysis."""

    frequency_distribution: dict[str, int]  # {"daily": 50, "weekly": 30, ...}
    sender_frequencies: dict[str, dict]  # {sender_email: {type, count, first, last}}


class VolumeStats(BaseModel):
    """Results from volume statistics analysis."""

    total_emails: int
    unique_senders: int
    date_range: dict[str, str]  # {oldest, newest, span_days}
    with_attachments: int
    attachment_percentage: float
    avg_body_length_chars: int
    emails_per_day: float


class AnalysisResults(BaseModel):
    """Complete analysis output container."""

    sender_analysis: SenderAnalysis
    subject_patterns: SubjectPatterns
    content_clusters: list[ContentCluster]
    temporal_patterns: TemporalPatterns
    volume_stats: VolumeStats
