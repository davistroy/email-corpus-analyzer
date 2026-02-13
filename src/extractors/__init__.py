"""Email extraction modules for Hotmail/M365 and Gmail."""

from src.extractors.gmail_extractor import GmailExtractor
from src.extractors.m365_extractor import (
    EmailExtractor,
    ExtractionError,
    ExtractionResult,
    IncrementalExtractionResult,
)

__all__ = [
    "EmailExtractor",
    "ExtractionError",
    "ExtractionResult",
    "IncrementalExtractionResult",
    "GmailExtractor",
]
