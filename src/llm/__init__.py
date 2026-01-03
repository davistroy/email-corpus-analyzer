"""
LLM integration for intelligent email analysis.

Provides Claude-based categorization, cluster naming, and analysis.
"""
from .client import LLMClient
from .categorizer import LLMCategorizer, CategorySuggestion, CategorySuggestions
from .namer import ClusterNamer, ClusterName

__all__ = [
    "LLMClient",
    "LLMCategorizer",
    "CategorySuggestion",
    "CategorySuggestions",
    "ClusterNamer",
    "ClusterName",
]
