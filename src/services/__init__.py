"""
Service layer for Email Corpus Analyzer.

Provides high-level service classes that orchestrate business logic
independently of CLI. Services can be used programmatically.

Per Phase 7, Track 7B specification.
"""
from src.services.analysis_service import AnalysisService
from src.services.extraction_service import ExtractionService
from src.services.pipeline_service import PipelineResult, PipelineService
from src.services.suggestion_service import SuggestionService

__all__ = [
    "ExtractionService",
    "AnalysisService",
    "SuggestionService",
    "PipelineService",
    "PipelineResult",
]
