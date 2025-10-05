"""
Subject Analyzer module.

Implements FR-014: Subject line pattern analysis.
Per analyzer_contract.md lines 104-149.
"""
import logging
import re
from collections import Counter
from typing import Callable

from ..models.corpus import Corpus
from ..models.analysis_results import SubjectPatterns

logger = logging.getLogger(__name__)


class SubjectAnalyzer:
    """Analyzer for email subject line patterns."""

    # Standard English stop words
    STOP_WORDS = {
        'a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'for', 'from',
        'has', 'he', 'in', 'is', 'it', 'its', 'of', 'on', 'that', 'the',
        'to', 'was', 'will', 'with', 'you', 'your', 'have', 'this', 'but',
        'or', 'not', 'can', 'we', 'all', 'been', 'were', 'when', 'what',
        'which', 'who', 'if', 'out', 'so', 'up', 'there', 'their', 'they',
        'me', 'my', 'our', 'us', 'am', 'i', 'them'
    }

    # Common prefixes to extract (case-insensitive)
    PREFIX_PATTERNS = [
        r'^re:\s*',
        r'^fwd:\s*',
    ]

    # Numbered pattern regex: (\w+)\s*[#№]\s*\d+
    NUMBERED_PATTERN = re.compile(r'(\w+)\s*[#№]\s*\d+', re.IGNORECASE)

    # Bracket tags regex: [\[\(]([^\]\)]+)[\]\)]
    BRACKET_TAG_PATTERN = re.compile(r'[\[\(]([^\]\)]+)[\]\)]')

    def analyze(
        self,
        corpus: Corpus,
        progress_callback: Callable[[int, int], None] | None = None
    ) -> SubjectPatterns:
        """
        Analyze subject line patterns.

        Args:
            corpus: Complete email corpus
            progress_callback: Optional callback(current, total)

        Returns:
            SubjectPatterns with prefixes, numbered patterns, keywords, tags

        Raises:
            ValueError: If corpus is empty or invalid
        """
        if not corpus.emails:
            raise ValueError("Corpus is empty")

        logger.debug(f"Starting subject analysis on {len(corpus.emails)} emails")

        total = len(corpus.emails)
        common_prefixes: Counter = Counter()
        numbered_patterns: Counter = Counter()
        all_words: Counter = Counter()
        bracket_tags: Counter = Counter()

        for idx, email in enumerate(corpus.emails):
            # Progress callback
            if progress_callback and idx % 100 == 0:
                progress_callback(idx, total)

            subject = email.subject

            # Extract prefixes
            self._extract_prefixes(subject, common_prefixes)

            # Extract numbered patterns
            self._extract_numbered_patterns(subject, numbered_patterns)

            # Extract keywords (after removing prefixes and tags)
            self._extract_keywords(subject, all_words)

            # Extract bracket tags
            self._extract_bracket_tags(subject, bracket_tags)

        # Final progress update
        if progress_callback:
            progress_callback(total, total)

        # Filter stop words and get top 50 keywords
        filtered_words = {
            word: count for word, count in all_words.items()
            if word.lower() not in self.STOP_WORDS and len(word) > 1
        }
        top_keywords = sorted(filtered_words.items(), key=lambda x: x[1], reverse=True)[:50]

        # Get top bracket tags (sorted by frequency)
        top_tags = sorted(bracket_tags.items(), key=lambda x: x[1], reverse=True)

        logger.debug(
            f"Analysis complete: {len(common_prefixes)} prefixes, "
            f"{len(numbered_patterns)} numbered patterns, "
            f"{len(top_keywords)} keywords, {len(top_tags)} tags"
        )

        return SubjectPatterns(
            common_prefixes=dict(common_prefixes),
            numbered_patterns=dict(numbered_patterns),
            top_keywords=top_keywords,
            bracket_tags=top_tags,
            total_subjects_analyzed=total
        )

    def _extract_prefixes(self, subject: str, counter: Counter) -> None:
        """Extract common prefixes like RE:, FWD: (case-insensitive)."""
        for pattern in self.PREFIX_PATTERNS:
            match = re.match(pattern, subject, re.IGNORECASE)
            if match:
                # Normalize to uppercase for counting
                prefix = match.group().strip().upper()
                if not prefix.endswith(':'):
                    prefix += ':'
                counter[prefix] += 1

    def _extract_numbered_patterns(self, subject: str, counter: Counter) -> None:
        """Extract numbered patterns like 'Invoice #12345'."""
        matches = self.NUMBERED_PATTERN.findall(subject)
        for pattern_word in matches:
            # Capitalize first letter for consistency
            normalized = pattern_word.capitalize()
            counter[normalized] += 1

    def _extract_keywords(self, subject: str, counter: Counter) -> None:
        """Extract keywords from subject, excluding prefixes and tags."""
        # Remove prefixes
        cleaned = subject
        for pattern in self.PREFIX_PATTERNS:
            cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)

        # Remove bracket tags
        cleaned = self.BRACKET_TAG_PATTERN.sub('', cleaned)

        # Remove numbered patterns (the entire match)
        cleaned = self.NUMBERED_PATTERN.sub('', cleaned)

        # Extract words (alphanumeric sequences)
        words = re.findall(r'\b[a-zA-Z]+\b', cleaned.lower())
        counter.update(words)

    def _extract_bracket_tags(self, subject: str, counter: Counter) -> None:
        """Extract tags within brackets or parentheses."""
        matches = self.BRACKET_TAG_PATTERN.findall(subject)
        for tag in matches:
            # Strip whitespace and keep original case
            normalized = tag.strip()
            if normalized:
                counter[normalized] += 1
