"""
Suggestion Service module.

Orchestrates category suggestion generation.
Decoupled from CLI for independent use.

Per Phase 7, Track 7B specification.
"""
import logging
from collections.abc import Callable

from src.config.models import SuggestConfig
from src.generators.category_generator import CategoryGenerator
from src.models.analysis_results import AnalysisResults
from src.models.category import Category

logger = logging.getLogger(__name__)


class SuggestionService:
    """
    Service for orchestrating category suggestion generation.

    Provides high-level suggestion API independent of CLI.
    """

    def __init__(self, config: SuggestConfig):
        """
        Initialize suggestion service.

        Args:
            config: Suggestion configuration
        """
        self.config = config

    def run(
        self,
        analysis: AnalysisResults,
        progress_callback: Callable[[str], None] | None = None,
    ) -> list[Category]:
        """
        Generate category suggestions from analysis results.

        Args:
            analysis: Analysis results to generate suggestions from
            progress_callback: Optional callback(message) for status updates

        Returns:
            List of suggested categories
        """
        if progress_callback:
            progress_callback("Generating category suggestions...")

        generator = CategoryGenerator()

        if progress_callback:
            progress_callback("Processing content clusters...")

        categories = generator.generate_suggestions(
            analysis,
            min_cluster_percentage=self.config.min_cluster_percentage,
            min_sender_count=self.config.min_sender_count,
        )

        if progress_callback:
            progress_callback(f"Generated {len(categories)} category suggestions")

        return categories


__all__ = ["SuggestionService"]
