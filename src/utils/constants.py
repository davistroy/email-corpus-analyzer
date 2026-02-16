"""
Named constants for the email-corpus-analyzer.

Centralizes magic numbers that were previously scattered across modules.
Each constant includes a comment explaining its purpose and how its value
was chosen.
"""

# ── Extraction ─────────────────────────────────────────────────────────
# Used when the email provider (e.g. Microsoft Graph) does not report a
# total message count.  The batch loop relies on empty-batch detection to
# stop, so this sentinel just needs to be "large enough" to never be the
# reason extraction stops prematurely.
EMAIL_COUNT_SENTINEL = 999_999

# Ceiling for exponential backoff on rate-limit retries (seconds).
# backoff = min(2 ** attempt, MAX_BACKOFF_SECONDS)
MAX_BACKOFF_SECONDS = 8

# Default number of emails fetched per API request.
DEFAULT_BATCH_SIZE = 500

# Default interval (in emails processed) between checkpoint saves.
DEFAULT_CHECKPOINT_INTERVAL = 100

# ── Scoring ────────────────────────────────────────────────────────────
# Controls the steepness of the sigmoid curve used to convert silhouette
# scores to confidence values in cluster_optimizer.  A value of 5.0 gives
# good discrimination: scores near 0 map to ~0.5, scores of +0.5 map to
# ~0.92, and negative scores drop sharply toward 0.
SIGMOID_STEEPNESS = 5.0

# Base for logarithmic volume scoring in confidence_scorer.
# log10(101) ≈ 2.004, which means 100 emails produce a volume score of
# exactly 1.0 (log10(101)/log10(101)).  Smaller counts scale sub-linearly.
VOLUME_LOG_BASE = 101

# Category names with a quality score below this threshold are flagged for
# human review during the suggestion stage.
NAME_QUALITY_REVIEW_THRESHOLD = 0.4

# ── Sampling limits ────────────────────────────────────────────────────
# Maximum number of representative email samples stored per cluster.
MAX_REPRESENTATIVE_SAMPLES = 5

# Maximum number of top domains to track per cluster/analysis.
MAX_COMMON_DOMAINS = 10

# Maximum number of top keywords to extract during analysis.
MAX_TOP_KEYWORDS = 50
