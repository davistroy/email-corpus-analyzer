"""
Feedback learning module for category review decisions.

This module provides functionality for:
- Logging user review decisions to persistent storage (Task 5B.1)
- Detecting patterns in user decisions (Task 5B.2)
- Applying learned preferences to new suggestions (Task 5B.3)
- Uncertainty sampling for active learning (Phase 5, Item 5.3)
- Email-level feedback with temporal decay (Phase 5, Item 5.1)
"""

from src.learning.decision_logger import (
    DecisionAction,
    DecisionLogger,
    ReviewDecision,
    get_default_decisions_path,
)
from src.learning.feedback_store import (
    Correction,
    EmailFeedbackStore,
    WeightedCorrection,
)
from src.learning.pattern_detector import (
    DetectedPattern,
    PatternDetector,
    PatternType,
)
from src.learning.uncertainty_sampler import UncertaintySampler

__all__ = [
    "Correction",
    "DecisionAction",
    "DecisionLogger",
    "DetectedPattern",
    "EmailFeedbackStore",
    "PatternDetector",
    "PatternType",
    "ReviewDecision",
    "UncertaintySampler",
    "WeightedCorrection",
    "get_default_decisions_path",
]
