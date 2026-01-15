"""
Preview module for dry-run mode estimation.

This module provides estimators for each CLI command that can preview
what would happen without actually executing the commands.
"""

from .estimators import (
    AnalyzeEstimate,
    AnalyzeEstimator,
    ExtractEstimate,
    ExtractEstimator,
    PipelineEstimate,
    PipelineEstimator,
    ReviewEstimate,
    ReviewEstimator,
    SuggestEstimate,
    SuggestEstimator,
    format_analyze_preview,
    format_bytes,
    format_count,
    format_duration,
    format_extract_preview,
    format_pipeline_preview,
    format_review_preview,
    format_suggest_preview,
)

__all__ = [
    # Estimate models
    "ExtractEstimate",
    "AnalyzeEstimate",
    "SuggestEstimate",
    "ReviewEstimate",
    "PipelineEstimate",
    # Estimator classes
    "ExtractEstimator",
    "AnalyzeEstimator",
    "SuggestEstimator",
    "ReviewEstimator",
    "PipelineEstimator",
    # Formatters
    "format_extract_preview",
    "format_analyze_preview",
    "format_suggest_preview",
    "format_review_preview",
    "format_pipeline_preview",
    # Helpers
    "format_bytes",
    "format_duration",
    "format_count",
]
