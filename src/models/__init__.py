"""
Data models for email corpus analyzer.

Exports all Pydantic models for email extraction and analysis.
"""
from .analysis_results import AnalysisResults
from .category import Category, CategorySource
from .category_template import CategoryTemplate, PREDEFINED_TEMPLATES
from .content_cluster import ContentCluster, RepresentativeSample
from .corpus import Corpus, CorpusMetadata
from .email import Email
from .mailbox import (
    AnalysisState,
    ExtractionState,
    Mailbox,
    MailboxStatus,
)
from .provider import (
    BaseProviderConfig,
    GmailConfig,
    IMAPConfig,
    M365Config,
    ProviderConfig,
    ProviderType,
    create_provider_config,
)
from .sender import Sender, SenderType

__all__ = [
    # Email and Corpus
    "Email",
    "Corpus",
    "CorpusMetadata",
    # Provider
    "ProviderType",
    "ProviderConfig",
    "BaseProviderConfig",
    "M365Config",
    "GmailConfig",
    "IMAPConfig",
    "create_provider_config",
    # Mailbox
    "Mailbox",
    "MailboxStatus",
    "ExtractionState",
    "AnalysisState",
    # Analysis
    "AnalysisResults",
    "ContentCluster",
    "RepresentativeSample",
    "Sender",
    "SenderType",
    # Categories
    "Category",
    "CategorySource",
    "CategoryTemplate",
    "PREDEFINED_TEMPLATES",
]
