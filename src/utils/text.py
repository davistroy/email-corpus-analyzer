"""
Shared text processing utilities and word lists.

This module is the single source of truth for stop words, generic words,
action words, and known proper nouns used across the email-corpus-analyzer
pipeline. Previously these lists were duplicated (with slight variations)
in name_generator.py, subject_analyzer.py, and category_generator.py.

Modules may extend these sets for local needs:
    module_stops = STOP_WORDS | {"module_specific_word"}
"""

# ──────────────────────────────────────────────────────────────────────
# STOP_WORDS — union of the three previously independent lists from
# name_generator.py, subject_analyzer.py, and category_generator.py.
# ──────────────────────────────────────────────────────────────────────
STOP_WORDS: frozenset[str] = frozenset([
    # Common English stop words
    "a", "all", "am", "an", "and", "are", "as", "at", "be", "been",
    "being", "both", "but", "by", "can", "could", "dare", "did", "do",
    "does", "each", "every", "few", "for", "from", "had", "has", "have",
    "he", "here", "how", "i", "if", "in", "is", "it", "its", "just",
    "may", "me", "might", "more", "most", "must", "my", "need", "no",
    "nor", "not", "now", "of", "on", "only", "or", "other", "ought",
    "our", "out", "own", "same", "shall", "she", "should", "so", "some",
    "such", "than", "that", "the", "their", "them", "then", "there",
    "these", "they", "this", "those", "to", "too", "up", "us", "used",
    "very", "was", "we", "were", "what", "when", "where", "which", "who",
    "whom", "whose", "why", "will", "with", "would", "you", "your",
    # Email-specific common words
    "am", "best", "dear", "email", "emails", "fw", "fwd", "hello", "hi",
    "mail", "message", "messages", "once", "our", "please", "pm", "re",
    "received", "regards", "sent", "sincerely", "subject", "thank",
    "thanks", "also",
])

# ──────────────────────────────────────────────────────────────────────
# GENERIC_WORDS — words that indicate poor / non-descriptive category
# names (from name_generator.py).
# ──────────────────────────────────────────────────────────────────────
GENERIC_WORDS: frozenset[str] = frozenset([
    "category", "emails", "general", "items", "kind", "mail", "messages",
    "miscellaneous", "other", "related", "stuff", "things", "type",
    "various",
])

# ──────────────────────────────────────────────────────────────────────
# ACTION_WORDS — words that indicate good / descriptive category names
# (from name_generator.py).
# ──────────────────────────────────────────────────────────────────────
ACTION_WORDS: frozenset[str] = frozenset([
    "alert", "alerts", "confirmation", "confirmations", "daily",
    "delivered", "delivery", "invoice", "invoiced", "monthly",
    "newsletter", "notification", "notifications", "order", "ordered",
    "paid", "payment", "receipt", "reminder", "reminders", "report",
    "reports", "request", "requests", "shipped", "shipping", "summary",
    "update", "updates", "weekly",
])

# ──────────────────────────────────────────────────────────────────────
# KNOWN_PROPER_NOUNS — brand / company names used for bonus scoring
# (from name_generator.py).
# ──────────────────────────────────────────────────────────────────────
KNOWN_PROPER_NOUNS: frozenset[str] = frozenset([
    "amazon", "american", "apple", "box", "capital", "chase", "citi",
    "constant", "contact", "costco", "discover", "dropbox", "ebay",
    "etsy", "express", "facebook", "fargo", "github", "google",
    "hubspot", "linkedin", "lyft", "mailchimp", "mastercard",
    "microsoft", "netflix", "paypal", "salesforce", "sendgrid",
    "shopify", "slack", "spotify", "square", "stripe", "target",
    "twilio", "twitter", "uber", "venmo", "visa", "walmart", "wells",
    "zoom",
])
