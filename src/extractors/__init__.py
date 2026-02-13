"""Email extraction modules for Hotmail/M365 and Gmail."""

from src.extractors.base_extractor import (
    BaseExtractor,
    ExtractionError,
    ExtractionResult,
    IncrementalExtractionResult,
)
from src.extractors.gmail_extractor import GmailExtractor
from src.extractors.m365_extractor import EmailExtractor

__all__ = [
    "BaseExtractor",
    "EmailExtractor",
    "ExtractionError",
    "ExtractionResult",
    "IncrementalExtractionResult",
    "GmailExtractor",
]
