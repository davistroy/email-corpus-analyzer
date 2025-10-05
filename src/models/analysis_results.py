"""
AnalysisResults data model.

Per data-model.md lines 217-253.
"""
from typing import List, Dict
from pydantic import BaseModel

from .sender import Sender
from .content_cluster import ContentCluster


class SenderAnalysis(BaseModel):
    """Results from sender pattern analysis."""

    top_senders: List[Sender]
    top_domains: List[Dict[str, int]]  # [{"domain": "example.com", "count": 45}]
    unique_senders: int
    unique_domains: int


class SubjectPatterns(BaseModel):
    """Results from subject line pattern analysis."""

    common_prefixes: Dict[str, int]  # {"RE:": 45, "FWD:": 23}
    numbered_patterns: Dict[str, int]  # {"Invoice": 12, "Order": 34}
    top_keywords: List[tuple[str, int]]  # [("meeting", 45), ("update", 38)]
    bracket_tags: List[tuple[str, int]]  # [("URGENT", 12), ("Team", 8)]
    total_subjects_analyzed: int


class TemporalPatterns(BaseModel):
    """Results from temporal pattern analysis."""

    frequency_distribution: Dict[str, int]  # {"daily": 50, "weekly": 30, ...}
    sender_frequencies: Dict[str, Dict]  # {sender_email: {type, count, first, last}}


class VolumeStats(BaseModel):
    """Results from volume statistics analysis."""

    total_emails: int
    unique_senders: int
    date_range: Dict[str, str]  # {oldest, newest, span_days}
    with_attachments: int
    attachment_percentage: float
    avg_body_length_chars: int
    emails_per_day: float


class AnalysisResults(BaseModel):
    """Complete analysis output container."""

    sender_analysis: SenderAnalysis
    subject_patterns: SubjectPatterns
    content_clusters: List[ContentCluster]
    temporal_patterns: TemporalPatterns
    volume_stats: VolumeStats
