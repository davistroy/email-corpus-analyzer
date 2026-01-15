"""
TF-IDF based name generator for email categories.

Generates descriptive category names by analyzing distinguishing terms
in email clusters using TF-IDF (Term Frequency-Inverse Document Frequency).
"""
from dataclasses import dataclass

from sklearn.feature_extraction.text import TfidfVectorizer

from src.utils.logger import get_logger

logger = get_logger(__name__)


# Stop words to filter from generated names
STOP_WORDS = frozenset([
    # Common English stop words
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "as", "is", "was", "are", "were", "been",
    "be", "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "must", "shall", "can", "need", "dare", "ought",
    "used", "this", "that", "these", "those", "i", "you", "he", "she", "it",
    "we", "they", "what", "which", "who", "whom", "whose", "when", "where",
    "why", "how", "all", "each", "every", "both", "few", "more", "most",
    "other", "some", "such", "no", "not", "only", "same", "so", "than",
    "too", "very", "just", "also", "now", "here", "there", "then", "once",
    # Email-specific common words
    "email", "emails", "mail", "message", "messages", "subject", "re", "fwd",
    "fw", "sent", "received", "please", "thanks", "thank", "regards", "hi",
    "hello", "dear", "sincerely", "best", "am", "pm", "your", "our", "my",
])

# Generic words that indicate poor category names
GENERIC_WORDS = frozenset([
    "category", "related", "miscellaneous", "other", "various", "general",
    "stuff", "things", "items", "emails", "messages", "mail", "type", "kind",
])

# Action words that indicate good category names
ACTION_WORDS = frozenset([
    "update", "updates", "notification", "notifications", "alert", "alerts",
    "confirmation", "confirmations", "reminder", "reminders", "request",
    "requests", "shipping", "shipped", "delivery", "delivered", "payment",
    "paid", "invoice", "invoiced", "order", "ordered", "receipt", "report",
    "reports", "summary", "weekly", "daily", "monthly", "newsletter",
])

# Known proper nouns (brands, companies) for bonus scoring
KNOWN_PROPER_NOUNS = frozenset([
    "amazon", "google", "microsoft", "apple", "facebook", "twitter", "linkedin",
    "github", "slack", "zoom", "netflix", "spotify", "uber", "lyft", "paypal",
    "venmo", "chase", "wells", "fargo", "citi", "capital", "american", "express",
    "mastercard", "visa", "discover", "walmart", "target", "costco", "ebay",
    "etsy", "shopify", "stripe", "square", "dropbox", "box", "salesforce",
    "hubspot", "mailchimp", "constant", "contact", "sendgrid", "twilio",
])


@dataclass
class NameQualityScore:
    """Quality score breakdown for a category name."""

    total_score: float
    length_penalty: float
    generic_penalty: float
    caps_penalty: float
    specificity_bonus: float
    proper_noun_bonus: float
    action_bonus: float


class TfidfNameGenerator:
    """Generate category names using TF-IDF analysis."""

    def __init__(self, min_df: int = 1, max_features: int = 100):
        """
        Initialize the TF-IDF name generator.

        Args:
            min_df: Minimum document frequency for terms
            max_features: Maximum number of features to extract
        """
        self.min_df = min_df
        self.max_features = max_features

    def generate_name(
        self,
        cluster_texts: list[str],
        corpus_texts: list[str],
    ) -> tuple[str, float]:
        """
        Generate a descriptive name for a cluster of emails.

        Uses TF-IDF to identify terms that are distinctive to this cluster
        compared to the overall corpus.

        Args:
            cluster_texts: List of text content from the cluster
            corpus_texts: List of text content from the full corpus

        Returns:
            Tuple of (generated name, confidence score)
        """
        if not cluster_texts:
            logger.debug("Empty cluster, returning Miscellaneous")
            return "Miscellaneous", 0.0

        # Combine texts for TF-IDF analysis
        # Cluster is first document, corpus is second
        cluster_combined = " ".join(cluster_texts)
        corpus_combined = " ".join(corpus_texts) if corpus_texts else ""

        if not cluster_combined.strip():
            return "Miscellaneous", 0.0

        try:
            # Get distinguishing terms using TF-IDF
            distinguishing_terms = self._extract_distinguishing_terms(
                cluster_combined, corpus_combined
            )

            if not distinguishing_terms:
                # Fallback: extract from cluster alone
                distinguishing_terms = self._extract_cluster_terms(cluster_combined)

            if not distinguishing_terms:
                return "Miscellaneous", 0.0

            # Generate name from top terms (2-4 words)
            name = self._format_name(distinguishing_terms)
            confidence = self._calculate_confidence(distinguishing_terms)

            logger.debug(f"Generated name '{name}' with confidence {confidence:.2f}")
            return name, confidence

        except Exception as e:
            logger.warning(f"Error generating name: {e}")
            return "Miscellaneous", 0.0

    def _extract_distinguishing_terms(
        self,
        cluster_text: str,
        corpus_text: str,
    ) -> list[tuple[str, float]]:
        """
        Extract terms that distinguish the cluster from the corpus.

        Args:
            cluster_text: Combined text from cluster
            corpus_text: Combined text from corpus

        Returns:
            List of (term, tfidf_score) tuples sorted by score descending
        """
        if not corpus_text.strip():
            return self._extract_cluster_terms(cluster_text)

        documents = [cluster_text, corpus_text]

        try:
            vectorizer = TfidfVectorizer(
                min_df=1,
                max_features=self.max_features,
                stop_words="english",
                token_pattern=r"(?u)\b[a-zA-Z][a-zA-Z0-9]*\b",  # Alphanumeric, starts with letter
                lowercase=True,
            )

            tfidf_matrix = vectorizer.fit_transform(documents)
            feature_names = vectorizer.get_feature_names_out()

            # Get TF-IDF scores for cluster (first document)
            cluster_scores = tfidf_matrix[0].toarray().flatten()

            # Create term-score pairs
            term_scores = []
            for term, score in zip(feature_names, cluster_scores):
                if score > 0 and term.lower() not in STOP_WORDS and len(term) > 2:
                    term_scores.append((term, score))

            # Sort by score descending
            term_scores.sort(key=lambda x: x[1], reverse=True)

            return term_scores[:10]  # Return top 10

        except ValueError as e:
            logger.debug(f"TF-IDF extraction failed: {e}")
            return []

    def _extract_cluster_terms(self, cluster_text: str) -> list[tuple[str, float]]:
        """
        Extract important terms from cluster text alone.

        Used as fallback when corpus is empty or TF-IDF fails.

        Args:
            cluster_text: Combined text from cluster

        Returns:
            List of (term, frequency) tuples
        """
        try:
            vectorizer = TfidfVectorizer(
                min_df=1,
                max_features=self.max_features,
                stop_words="english",
                token_pattern=r"(?u)\b[a-zA-Z][a-zA-Z0-9]*\b",
                lowercase=True,
            )

            tfidf_matrix = vectorizer.fit_transform([cluster_text])
            feature_names = vectorizer.get_feature_names_out()
            scores = tfidf_matrix[0].toarray().flatten()

            term_scores = []
            for term, score in zip(feature_names, scores):
                if score > 0 and term.lower() not in STOP_WORDS and len(term) > 2:
                    term_scores.append((term, score))

            term_scores.sort(key=lambda x: x[1], reverse=True)
            return term_scores[:10]

        except ValueError:
            return []

    def _format_name(self, terms: list[tuple[str, float]]) -> str:
        """
        Format extracted terms into a category name.

        Args:
            terms: List of (term, score) tuples

        Returns:
            Formatted category name (2-4 words, title case)
        """
        if not terms:
            return "Miscellaneous"

        # Filter out very short terms and format
        filtered_terms = []
        for term, score in terms:
            if len(term) > 2:
                filtered_terms.append(term.title())

        if not filtered_terms:
            return "Miscellaneous"

        # Take 2-4 top terms
        name_terms = filtered_terms[:4]

        # Ensure minimum 2 words if possible
        if len(name_terms) == 1 and len(filtered_terms) > 1:
            name_terms = filtered_terms[:2]

        return " ".join(name_terms)

    def _calculate_confidence(self, terms: list[tuple[str, float]]) -> float:
        """
        Calculate confidence score for the generated name.

        Args:
            terms: List of (term, score) tuples used for the name

        Returns:
            Confidence score between 0 and 1
        """
        if not terms:
            return 0.0

        # Base confidence on average TF-IDF scores of top terms
        top_scores = [score for _, score in terms[:4]]
        avg_score = sum(top_scores) / len(top_scores)

        # Scale to 0-1 range (TF-IDF scores are typically 0-1 already)
        confidence = min(1.0, avg_score * 2)

        # Bonus for having multiple distinguishing terms
        if len(terms) >= 3:
            confidence = min(1.0, confidence * 1.1)

        return confidence


def score_name_quality(name: str) -> NameQualityScore:
    """
    Score the quality of a category name.

    Evaluates names based on:
    - Length (penalize too short or too long)
    - Generic words (penalize 'Email Category', 'Miscellaneous', etc.)
    - Capitalization (penalize ALL CAPS)
    - Specificity (reward concrete terms)
    - Proper nouns (reward brand names)
    - Action words (reward descriptive action words)

    Args:
        name: The category name to score

    Returns:
        NameQualityScore with total and component scores

    Example:
        >>> score = score_name_quality("Amazon Order Confirmations")
        >>> score.total_score > 0.7
        True
        >>> score = score_name_quality("Miscellaneous")
        >>> score.total_score < 0.4
        True
    """
    if not name or not name.strip():
        return NameQualityScore(
            total_score=0.0,
            length_penalty=0.0,
            generic_penalty=0.0,
            caps_penalty=0.0,
            specificity_bonus=0.0,
            proper_noun_bonus=0.0,
            action_bonus=0.0,
        )

    name = name.strip()
    words = name.split()
    words_lower = [w.lower() for w in words]
    word_count = len(words)

    # Base score starts at 0.5
    base_score = 0.5

    # Length penalty: optimal is 2-4 words
    length_penalty = 0.0
    if word_count < 2:
        length_penalty = -0.2
    elif word_count > 4:
        length_penalty = -0.1 * (word_count - 4)
        length_penalty = max(-0.3, length_penalty)

    # Generic word penalty
    generic_penalty = 0.0
    generic_count = sum(1 for w in words_lower if w in GENERIC_WORDS)
    if generic_count > 0:
        generic_penalty = -0.2 * generic_count

    # All caps penalty
    caps_penalty = 0.0
    if name.isupper() and len(name) > 1:
        caps_penalty = -0.2

    # Specificity bonus: reward concrete, specific terms
    specificity_bonus = 0.0
    specific_count = sum(1 for w in words_lower if len(w) > 5 and w not in GENERIC_WORDS and w not in STOP_WORDS)
    specificity_bonus = min(0.15, specific_count * 0.05)

    # Proper noun bonus: check for known brands/companies or capitalized words
    proper_noun_bonus = 0.0
    known_proper_count = sum(1 for w in words_lower if w in KNOWN_PROPER_NOUNS)
    if known_proper_count > 0:
        proper_noun_bonus = min(0.2, known_proper_count * 0.1)
    else:
        # Check for capitalized words that aren't at start (indicates proper noun)
        capitalized_count = sum(1 for w in words[1:] if w and w[0].isupper())
        proper_noun_bonus = min(0.1, capitalized_count * 0.05)

    # Action word bonus
    action_bonus = 0.0
    action_count = sum(1 for w in words_lower if w in ACTION_WORDS)
    action_bonus = min(0.15, action_count * 0.05)

    # Calculate total score
    total_score = (
        base_score
        + length_penalty
        + generic_penalty
        + caps_penalty
        + specificity_bonus
        + proper_noun_bonus
        + action_bonus
    )

    # Clamp to 0-1
    total_score = max(0.0, min(1.0, total_score))

    return NameQualityScore(
        total_score=total_score,
        length_penalty=length_penalty,
        generic_penalty=generic_penalty,
        caps_penalty=caps_penalty,
        specificity_bonus=specificity_bonus,
        proper_noun_bonus=proper_noun_bonus,
        action_bonus=action_bonus,
    )
