"""
Feedback learning module for category review decisions.

This module provides functionality for:
- Logging user review decisions to persistent storage (Task 5B.1)
- Detecting patterns in user decisions (Task 5B.2)
- Applying learned preferences to new suggestions (Task 5B.3)
"""
from src.learning.decision_logger import (
    DecisionAction,
    DecisionLogger,
    ReviewDecision,
    get_default_decisions_path,
)
from src.learning.pattern_detector import (
    DetectedPattern,
    PatternDetector,
    PatternType,
)

__all__ = [
    "DecisionAction",
    "DecisionLogger",
    "DetectedPattern",
    "PatternDetector",
    "PatternType",
    "ReviewDecision",
    "get_default_decisions_path",
]
