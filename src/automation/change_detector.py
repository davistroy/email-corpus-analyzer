"""
Change detector for Phase 6, Item 6.2.

Detects drift, volume anomalies, and emerging topics by comparing
two AnalysisResults snapshots or examining a Corpus for statistical
outliers.

- detect_drift(old, new) -> DriftReport: distribution-shift detection
  using Jensen-Shannon-style percentage divergence across clusters and
  domain distributions.
- detect_volume_anomaly(corpus, window_days) -> list[VolumeAnomaly]:
  z-score based daily volume outlier detection.
- detect_emerging_topics(old, new) -> list[EmergingTopic]: identify
  new clusters whose email IDs were not present in the old analysis.

All thresholds are configurable via MonitoringConfig.
"""

from __future__ import annotations

import logging
import math
from collections import Counter
from datetime import datetime, timedelta

from pydantic import BaseModel, Field

from src.config.models import MonitoringConfig
from src.models.analysis_results import AnalysisResults
from src.models.content_cluster import ContentCluster
from src.models.corpus import Corpus

logger = logging.getLogger(__name__)

# =============================================================================
# Data Models
# =============================================================================


class DriftReport(BaseModel):
    """Report produced by detect_drift().

    Attributes:
        overall_drift_score: Normalized 0-1 score summarizing the total
            distribution shift between old and new analyses. 0 = identical,
            1 = maximally divergent.
        per_cluster_drift: Mapping of cluster_id -> per-cluster drift score
            (absolute percentage-point change divided by 100).
        significant_changes: Human-readable descriptions of changes that
            exceed the configured drift_threshold.
    """

    overall_drift_score: float = Field(
        ..., ge=0.0, le=1.0, description="Overall drift score (0=identical, 1=max divergence)"
    )
    per_cluster_drift: dict[int, float] = Field(
        default_factory=dict,
        description="Per-cluster drift scores keyed by cluster_id",
    )
    significant_changes: list[str] = Field(
        default_factory=list,
        description="Human-readable descriptions of significant changes",
    )


class VolumeAnomaly(BaseModel):
    """A single volume anomaly detected in a corpus.

    Attributes:
        date_range: (start_date, end_date) ISO strings for the anomalous period.
        expected_volume: Mean daily volume used as baseline.
        actual_volume: Observed volume for the anomalous day.
        z_score: Signed z-score — positive = spike, negative = dip.
    """

    date_range: tuple[str, str] = Field(
        ..., description="(start_date, end_date) ISO strings for the anomalous day"
    )
    expected_volume: float = Field(..., description="Mean daily volume (baseline)")
    actual_volume: int = Field(..., description="Observed daily volume")
    z_score: float = Field(..., description="Signed z-score (positive=spike, negative=dip)")


class EmergingTopic(BaseModel):
    """A newly emerging topic detected by comparing analyses.

    Attributes:
        topic_keywords: Keywords extracted from the cluster's representative
            samples (subjects and body previews).
        email_count: Number of emails in the emerging cluster.
        first_seen: ISO date string for when the earliest email in the cluster
            was observed (derived from cluster data).
        suggested_category: Optional suggested category name for the topic.
    """

    topic_keywords: list[str] = Field(..., description="Keywords characterizing the emerging topic")
    email_count: int = Field(..., ge=0, description="Number of emails in the emerging cluster")
    first_seen: str = Field(..., description="ISO date string for first observation")
    suggested_category: str | None = Field(
        default=None, description="Suggested category name for the emerging topic"
    )


# =============================================================================
# ChangeDetector
# =============================================================================


class ChangeDetector:
    """Detects drift, volume anomalies, and emerging topics.

    Uses configurable thresholds from MonitoringConfig to determine what
    constitutes a significant change, anomaly, or emerging pattern.

    Args:
        config: MonitoringConfig with thresholds. Uses defaults if None.
    """

    def __init__(self, config: MonitoringConfig | None = None) -> None:
        self.config = config or MonitoringConfig()

    # ------------------------------------------------------------------
    # detect_drift
    # ------------------------------------------------------------------

    def detect_drift(
        self,
        old_analysis: AnalysisResults,
        new_analysis: AnalysisResults,
    ) -> DriftReport:
        """Compare two analysis results and quantify distribution drift.

        Drift is measured as the mean absolute percentage-point change
        across a unified set of cluster IDs (old + new), normalized to
        [0, 1].  Domain distribution changes contribute additively.

        Args:
            old_analysis: Previous AnalysisResults snapshot.
            new_analysis: Current AnalysisResults snapshot.

        Returns:
            DriftReport with overall score, per-cluster scores, and
            human-readable significant change descriptions.
        """
        old_clusters = old_analysis.content_clusters
        new_clusters = new_analysis.content_clusters

        # Edge case: both empty
        if not old_clusters and not new_clusters:
            return DriftReport(overall_drift_score=0.0)

        # Build percentage maps keyed by cluster_id
        old_pct = {c.cluster_id: c.percentage for c in old_clusters}
        new_pct = {c.cluster_id: c.percentage for c in new_clusters}

        all_ids = sorted(set(old_pct.keys()) | set(new_pct.keys()))

        per_cluster_drift: dict[int, float] = {}
        significant_changes: list[str] = []

        total_abs_diff = 0.0

        for cid in all_ids:
            old_p = old_pct.get(cid, 0.0)
            new_p = new_pct.get(cid, 0.0)
            abs_diff = abs(new_p - old_p)
            # Normalize to [0, 1] range (percentage points / 100)
            drift_val = abs_diff / 100.0
            per_cluster_drift[cid] = round(drift_val, 6)
            total_abs_diff += abs_diff

            # Check if this individual cluster change is significant
            if drift_val >= self.config.drift_threshold:
                direction = "grew" if new_p > old_p else "shrank"
                if old_p == 0.0:
                    significant_changes.append(
                        f"Cluster {cid} appeared with {new_p:.1f}% of corpus"
                    )
                elif new_p == 0.0:
                    significant_changes.append(
                        f"Cluster {cid} disappeared (was {old_p:.1f}% of corpus)"
                    )
                else:
                    significant_changes.append(
                        f"Cluster {cid} {direction} from {old_p:.1f}% to {new_p:.1f}% "
                        f"({abs_diff:+.1f} pp)"
                    )

        # Domain distribution drift component
        domain_drift = self._compute_domain_drift(old_analysis, new_analysis)

        # Overall drift: mean of cluster percentage-point changes (normalized)
        # plus a smaller domain component.  Capped at 1.0.
        # The total_abs_diff sums absolute pp changes; dividing by 200 normalizes
        # because the maximum sum-of-absolute-diffs for two distributions that
        # sum to 100% is 200 percentage points (one at 100%, the other at 0%).
        cluster_drift = min(total_abs_diff / 200.0, 1.0) if all_ids else 0.0

        # Blend: 80% cluster drift, 20% domain drift
        overall = min(0.8 * cluster_drift + 0.2 * domain_drift, 1.0)

        # Add domain-level significant changes
        if domain_drift >= self.config.drift_threshold:
            significant_changes.append(
                f"Domain distribution shifted (drift component: {domain_drift:.3f})"
            )

        logger.debug(
            "Drift analysis: cluster_drift=%.4f, domain_drift=%.4f, overall=%.4f, significant=%d",
            cluster_drift,
            domain_drift,
            overall,
            len(significant_changes),
        )

        return DriftReport(
            overall_drift_score=round(overall, 6),
            per_cluster_drift=per_cluster_drift,
            significant_changes=significant_changes,
        )

    # ------------------------------------------------------------------
    # detect_volume_anomaly
    # ------------------------------------------------------------------

    def detect_volume_anomaly(
        self,
        corpus: Corpus,
        window_days: int = 30,
    ) -> list[VolumeAnomaly]:
        """Find days with unusual volume spikes or dips.

        Computes daily email counts over the most recent *window_days*
        and flags any day whose count deviates from the mean by more
        than ``config.volume_anomaly_stddev`` standard deviations.

        Args:
            corpus: Email corpus to analyze.
            window_days: Number of recent days to consider.

        Returns:
            List of VolumeAnomaly objects, one per anomalous day.
        """
        if not corpus.emails:
            return []

        # Determine the date window
        dates = [e.received_date for e in corpus.emails]
        max_date = max(dates).date()
        min_date = max_date - timedelta(days=window_days - 1)

        # Count emails per day within the window
        daily_counts: Counter[datetime] = Counter()
        for email in corpus.emails:
            d = email.received_date.date()
            if d >= min_date:
                daily_counts[d] += 1

        # Fill in zero-count days
        all_days = []
        current = min_date
        while current <= max_date:
            all_days.append(current)
            current += timedelta(days=1)

        if len(all_days) < 2:
            # Not enough data for statistical analysis
            return []

        counts = [daily_counts.get(d, 0) for d in all_days]

        # Compute mean and standard deviation
        n = len(counts)
        mean_vol = sum(counts) / n
        variance = sum((c - mean_vol) ** 2 for c in counts) / n
        stddev = math.sqrt(variance)

        if stddev == 0.0:
            # All days identical — no anomalies possible
            return []

        threshold = self.config.volume_anomaly_stddev
        anomalies: list[VolumeAnomaly] = []

        for day, count in zip(all_days, counts, strict=True):
            z = (count - mean_vol) / stddev
            if abs(z) >= threshold:
                day_str = day.isoformat()
                anomalies.append(
                    VolumeAnomaly(
                        date_range=(day_str, day_str),
                        expected_volume=round(mean_vol, 2),
                        actual_volume=count,
                        z_score=round(z, 4),
                    )
                )

        logger.debug(
            "Volume anomaly analysis: window=%d days, mean=%.2f, stddev=%.2f, anomalies=%d",
            window_days,
            mean_vol,
            stddev,
            len(anomalies),
        )

        return anomalies

    # ------------------------------------------------------------------
    # detect_emerging_topics
    # ------------------------------------------------------------------

    def detect_emerging_topics(
        self,
        old_analysis: AnalysisResults,
        new_analysis: AnalysisResults,
    ) -> list[EmergingTopic]:
        """Find new patterns in new_analysis not present in old clusters.

        A cluster is considered "emerging" if it contains mostly email IDs
        that did not appear in any old cluster, and its size meets the
        ``config.new_cluster_threshold``.

        Args:
            old_analysis: Previous AnalysisResults snapshot.
            new_analysis: Current AnalysisResults snapshot.

        Returns:
            List of EmergingTopic objects describing newly identified topics.
        """
        old_email_ids: set[str] = set()
        for cluster in old_analysis.content_clusters:
            old_email_ids.update(cluster.email_ids)

        threshold = self.config.new_cluster_threshold
        emerging: list[EmergingTopic] = []

        for cluster in new_analysis.content_clusters:
            # Count how many email IDs in this cluster are genuinely new
            new_ids = [eid for eid in cluster.email_ids if eid not in old_email_ids]
            new_ratio = len(new_ids) / len(cluster.email_ids) if cluster.email_ids else 0.0

            # Consider a cluster "emerging" if >50% of its emails are new
            # AND the count of new emails meets the threshold
            if len(new_ids) >= threshold and new_ratio > 0.5:
                keywords = self._extract_keywords_from_cluster(cluster)
                suggested = self._suggest_category_name(keywords)

                emerging.append(
                    EmergingTopic(
                        topic_keywords=keywords,
                        email_count=len(new_ids),
                        first_seen=datetime.now().date().isoformat(),
                        suggested_category=suggested,
                    )
                )

        logger.debug(
            "Emerging topics: %d new topics detected (threshold=%d)",
            len(emerging),
            threshold,
        )

        return emerging

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _compute_domain_drift(
        self,
        old_analysis: AnalysisResults,
        new_analysis: AnalysisResults,
    ) -> float:
        """Compute drift in domain distribution between two analyses.

        Uses total-variation distance: half the sum of absolute differences
        between the normalized domain count distributions.

        Returns:
            Float in [0, 1] representing domain distribution divergence.
        """
        old_domains = {d.domain: d.count for d in old_analysis.sender_analysis.top_domains}
        new_domains = {d.domain: d.count for d in new_analysis.sender_analysis.top_domains}

        all_domains = set(old_domains.keys()) | set(new_domains.keys())
        if not all_domains:
            return 0.0

        old_total = sum(old_domains.values()) or 1
        new_total = sum(new_domains.values()) or 1

        total_diff = 0.0
        for domain in all_domains:
            old_frac = old_domains.get(domain, 0) / old_total
            new_frac = new_domains.get(domain, 0) / new_total
            total_diff += abs(old_frac - new_frac)

        # Total-variation distance: half the L1 distance between distributions
        return min(total_diff / 2.0, 1.0)

    def _extract_keywords_from_cluster(
        self,
        cluster: ContentCluster,
    ) -> list[str]:
        """Extract keywords from a cluster's representative samples.

        Tokenizes subjects and body previews, filters stop words and short
        tokens, and returns the most frequent terms.

        Args:
            cluster: ContentCluster to extract keywords from.

        Returns:
            List of keyword strings (up to 5).
        """
        # Common stop words to filter out
        stop_words = {
            "the",
            "a",
            "an",
            "is",
            "are",
            "was",
            "were",
            "be",
            "been",
            "being",
            "have",
            "has",
            "had",
            "do",
            "does",
            "did",
            "will",
            "would",
            "could",
            "should",
            "may",
            "might",
            "shall",
            "can",
            "to",
            "of",
            "in",
            "for",
            "on",
            "with",
            "at",
            "by",
            "from",
            "as",
            "into",
            "through",
            "during",
            "before",
            "after",
            "above",
            "below",
            "between",
            "out",
            "off",
            "over",
            "under",
            "again",
            "further",
            "then",
            "once",
            "here",
            "there",
            "when",
            "where",
            "why",
            "how",
            "all",
            "each",
            "every",
            "both",
            "few",
            "more",
            "most",
            "other",
            "some",
            "such",
            "no",
            "nor",
            "not",
            "only",
            "own",
            "same",
            "so",
            "than",
            "too",
            "very",
            "just",
            "because",
            "but",
            "and",
            "or",
            "if",
            "while",
            "about",
            "up",
            "it",
            "its",
            "this",
            "that",
            "these",
            "those",
            "i",
            "me",
            "my",
            "we",
            "our",
            "you",
            "your",
            "he",
            "him",
            "his",
            "she",
            "her",
            "they",
            "them",
            "their",
            "what",
            "which",
            "who",
            "whom",
            "re",
            "fwd",
        }

        word_counts: Counter[str] = Counter()
        for sample in cluster.representative_samples:
            text = f"{sample.subject} {sample.body_preview}".lower()
            # Simple tokenization: split on non-alpha characters
            tokens = [t for t in text.split() if t.isalpha() and len(t) > 2]
            for token in tokens:
                if token not in stop_words:
                    word_counts[token] += 1

        # Also include domain names from common_domains as potential keywords
        for domain, _count in cluster.common_domains:
            # Extract the main part of the domain (e.g., "devops" from "devops.com")
            parts = domain.split(".")
            if parts and len(parts[0]) > 2:
                word_counts[parts[0]] += 1

        # Return top 5 keywords
        return [word for word, _ in word_counts.most_common(5)]

    def _suggest_category_name(self, keywords: list[str]) -> str | None:
        """Generate a suggested category name from keywords.

        Takes the top 2-3 keywords and joins them with title case.

        Args:
            keywords: List of keyword strings.

        Returns:
            Suggested category name, or None if no keywords.
        """
        if not keywords:
            return None

        # Use top 2-3 keywords, title-cased
        name_words = keywords[: min(3, len(keywords))]
        return " ".join(w.title() for w in name_words)


__all__ = [
    "ChangeDetector",
    "DriftReport",
    "EmergingTopic",
    "VolumeAnomaly",
]
