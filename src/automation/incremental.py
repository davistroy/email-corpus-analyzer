"""
Incremental processing engine for Phase 6, Item 6.1.

Processes only new emails since the last run:
- extract_new(): Get only emails since last extraction using checkpoint data
- merge_into_corpus(): Merge new emails into existing corpus without duplicates
- reassign_to_clusters(): Assign new emails to existing clusters via nearest-centroid
- categorize_new(): Categorize new emails using existing rules
- run(): Full incremental pipeline orchestrating all steps

IncrementalResult model provides processing metrics (new_email_count,
merged_corpus_size, new_categorizations, processing_time).
"""

from __future__ import annotations

import hashlib
import logging
import time
from collections.abc import Callable
from datetime import datetime
from typing import TYPE_CHECKING

import numpy as np
from pydantic import BaseModel, Field

from src.models.analysis_results import AnalysisResults
from src.models.categorization import EmailCategorization
from src.models.content_cluster import ContentCluster
from src.models.corpus import Corpus, CorpusMetadata
from src.models.email import Email
from src.models.rule import RuleSet
from src.rules.engine import RuleEngine

if TYPE_CHECKING:
    from src.services.extraction_service import ExtractionService

logger = logging.getLogger(__name__)


# =============================================================================
# Result Model
# =============================================================================


class IncrementalResult(BaseModel):
    """Result of an incremental processing run.

    Captures all metrics from an incremental pipeline execution:
    how many new emails were found, the final corpus size, categorization
    results for the new emails, and wall-clock processing time.
    """

    new_email_count: int = Field(
        ..., ge=0, description="Number of new emails extracted in this run"
    )
    merged_corpus_size: int = Field(
        ..., ge=0, description="Total emails in the merged corpus after this run"
    )
    new_categorizations: list[EmailCategorization] = Field(
        default_factory=list,
        description="Categorization results for the new emails",
    )
    processing_time: float = Field(..., ge=0.0, description="Wall-clock processing time in seconds")


# =============================================================================
# Processor
# =============================================================================


class IncrementalProcessor:
    """Process only new emails since the last run.

    Orchestrates incremental extraction, corpus merging, cluster
    reassignment (nearest-centroid without full re-clustering), and
    rule-based categorization of new emails.

    Args:
        extraction_service: ExtractionService instance for email extraction.
    """

    def __init__(self, extraction_service: ExtractionService) -> None:
        self._extraction_service = extraction_service
        self._engine = RuleEngine()
        self._merged_corpus: Corpus | None = None
        self._updated_analysis: AnalysisResults | None = None

    # ------------------------------------------------------------------
    # Public properties
    # ------------------------------------------------------------------

    @property
    def merged_corpus(self) -> Corpus | None:
        """Return the merged corpus from the last run(), or None if not yet run."""
        return self._merged_corpus

    @property
    def updated_analysis(self) -> AnalysisResults | None:
        """Return the updated analysis from the last run(), or None if not yet run."""
        return self._updated_analysis

    # ------------------------------------------------------------------
    # extract_new
    # ------------------------------------------------------------------

    def extract_new(
        self,
        existing_corpus: Corpus,
        progress_callback: Callable[[str], None] | None = None,
    ) -> list[Email]:
        """Extract only emails that arrived since the last extraction.

        Delegates to the ExtractionService with ``since_last=True`` so only
        emails newer than the existing corpus are fetched.

        Args:
            existing_corpus: The current corpus (used to determine the
                extraction boundary via its metadata).
            progress_callback: Optional ``callback(message)`` for status updates.

        Returns:
            List of newly extracted Email objects.

        Raises:
            ConnectionError: If the email server is unreachable.
            AuthenticationError: If authentication fails.
        """
        if progress_callback:
            progress_callback("Extracting new emails since last run...")

        result_corpus = self._extraction_service.run(
            since_last=True,
            existing_corpus=existing_corpus,
            progress_callback=progress_callback,
        )

        new_emails = list(result_corpus.emails)

        if progress_callback:
            progress_callback(f"Extracted {len(new_emails)} new email(s)")

        return new_emails

    # ------------------------------------------------------------------
    # merge_into_corpus
    # ------------------------------------------------------------------

    def merge_into_corpus(
        self,
        new_emails: list[Email],
        existing_corpus: Corpus,
    ) -> Corpus:
        """Merge new emails into the existing corpus without duplicates.

        Deduplicates by email ID — existing emails are preserved as-is,
        and only genuinely new IDs are appended.  Metadata (total count,
        last extraction date, email IDs hash) is updated.

        Args:
            new_emails: Newly extracted emails to merge in.
            existing_corpus: The current corpus.

        Returns:
            A new Corpus containing all unique emails.
        """
        existing_ids = {e.id for e in existing_corpus.emails}
        merged_emails = list(existing_corpus.emails)

        for email in new_emails:
            if email.id not in existing_ids:
                existing_ids.add(email.id)
                merged_emails.append(email)

        # Compute email IDs hash for change detection
        email_ids_hash = ""
        if merged_emails:
            sorted_ids = sorted(e.id for e in merged_emails)
            combined = "|".join(sorted_ids)
            email_ids_hash = hashlib.sha256(combined.encode()).hexdigest()

        metadata = CorpusMetadata(
            extraction_date=existing_corpus.extraction_metadata.extraction_date,
            total_emails=len(merged_emails),
            source=existing_corpus.extraction_metadata.source,
            user_email=existing_corpus.extraction_metadata.user_email,
            last_extraction_date=datetime.now(),
            email_ids_hash=email_ids_hash,
            extraction_params=existing_corpus.extraction_metadata.extraction_params,
        )

        return Corpus(extraction_metadata=metadata, emails=merged_emails)

    # ------------------------------------------------------------------
    # reassign_to_clusters
    # ------------------------------------------------------------------

    def reassign_to_clusters(
        self,
        new_emails: list[Email],
        existing_analysis: AnalysisResults,
        progress_callback: Callable[[str], None] | None = None,
    ) -> AnalysisResults:
        """Assign new emails to existing clusters using nearest-centroid.

        Instead of re-clustering the entire corpus, each new email's
        embedding is compared to every existing cluster centroid (computed
        from the cluster's email IDs in the existing analysis).  The email
        is assigned to the cluster with the smallest cosine distance.

        Cluster sizes and percentages are updated accordingly.

        Args:
            new_emails: Newly extracted emails to assign.
            existing_analysis: Existing AnalysisResults with content_clusters.
            progress_callback: Optional ``callback(message)`` for status updates.

        Returns:
            Updated AnalysisResults with new emails assigned to clusters.
        """
        if not new_emails:
            return existing_analysis

        if progress_callback:
            progress_callback(f"Reassigning {len(new_emails)} email(s) to existing clusters...")

        clusters = existing_analysis.content_clusters
        if not clusters:
            logger.warning("No existing clusters to assign emails to")
            return existing_analysis

        # Compute centroids for existing clusters
        centroids = self._compute_centroids(clusters)

        # Compute embeddings for new emails
        new_embeddings = self._compute_embeddings(new_emails)

        # Deep copy clusters for mutation
        updated_clusters: list[ContentCluster] = []
        for cluster in clusters:
            updated_clusters.append(
                ContentCluster(
                    cluster_id=cluster.cluster_id,
                    size=cluster.size,
                    percentage=cluster.percentage,
                    representative_samples=list(cluster.representative_samples),
                    common_domains=list(cluster.common_domains),
                    email_ids=list(cluster.email_ids),
                    silhouette_score=cluster.silhouette_score,
                    cohesion_score=cluster.cohesion_score,
                )
            )

        # Assign each new email to nearest centroid
        for idx, email in enumerate(new_emails):
            embedding = new_embeddings[idx].reshape(1, -1)
            # Cosine distance to each centroid
            distances = np.array(
                [
                    float(
                        np.dot(embedding.flatten(), centroid)
                        / (np.linalg.norm(embedding) * np.linalg.norm(centroid) + 1e-10)
                    )
                    for centroid in centroids
                ]
            )
            # Cosine similarity: higher is better -> pick argmax
            nearest_idx = int(np.argmax(distances))
            updated_clusters[nearest_idx].email_ids.append(email.id)
            updated_clusters[nearest_idx].size += 1

        # Recalculate percentages
        total_emails = sum(c.size for c in updated_clusters)
        for cluster in updated_clusters:
            cluster.percentage = (
                round((cluster.size / total_emails) * 100, 2) if total_emails > 0 else 0.0
            )

        if progress_callback:
            progress_callback("Cluster reassignment complete")

        return AnalysisResults(
            sender_analysis=existing_analysis.sender_analysis,
            subject_patterns=existing_analysis.subject_patterns,
            content_clusters=updated_clusters,
            temporal_patterns=existing_analysis.temporal_patterns,
            volume_stats=existing_analysis.volume_stats,
        )

    # ------------------------------------------------------------------
    # categorize_new
    # ------------------------------------------------------------------

    def categorize_new(
        self,
        new_emails: list[Email],
        rule_set: RuleSet,
        progress_callback: Callable[[str], None] | None = None,
    ) -> list[EmailCategorization]:
        """Categorize new emails using an existing rule set.

        Applies the rule engine to each new email and produces an
        EmailCategorization per email.

        Args:
            new_emails: Newly extracted emails to categorize.
            rule_set: The RuleSet to evaluate against each email.
            progress_callback: Optional ``callback(message)`` for status updates.

        Returns:
            List of EmailCategorization results, one per input email.
        """
        if not new_emails:
            return []

        if progress_callback:
            progress_callback(f"Categorizing {len(new_emails)} new email(s)...")

        from src.categorizer.categorizer import EmailCategorizer

        categorizer = EmailCategorizer()
        categorizations: list[EmailCategorization] = []

        for idx, email in enumerate(new_emails):
            result = categorizer.categorize_email(email, rule_set)
            categorizations.append(result)

            if progress_callback and (idx + 1) % 10 == 0:
                progress_callback(f"Categorized {idx + 1}/{len(new_emails)} emails")

        if progress_callback:
            progress_callback(f"Categorization complete: {len(categorizations)} email(s) processed")

        return categorizations

    # ------------------------------------------------------------------
    # run (full pipeline)
    # ------------------------------------------------------------------

    def run(
        self,
        existing_corpus: Corpus,
        existing_analysis: AnalysisResults | None = None,
        rule_set: RuleSet | None = None,
        progress_callback: Callable[[str], None] | None = None,
    ) -> IncrementalResult:
        """Run the full incremental processing pipeline.

        Steps:
        1. Extract new emails since last run
        2. Merge into existing corpus (dedup)
        3. Reassign new emails to existing clusters (if analysis provided)
        4. Categorize new emails using rules (if rule_set provided)

        Args:
            existing_corpus: The current email corpus.
            existing_analysis: Existing AnalysisResults (optional; skips
                cluster reassignment if None).
            rule_set: RuleSet for categorization (optional; skips
                categorization if None).
            progress_callback: Optional ``callback(message)`` for status updates.

        Returns:
            IncrementalResult with processing metrics.
        """
        start_time = time.monotonic()

        if progress_callback:
            progress_callback("Starting incremental processing...")

        # Step 1: Extract new emails
        new_emails = self.extract_new(
            existing_corpus=existing_corpus,
            progress_callback=progress_callback,
        )

        # Step 2: Merge into corpus
        merged = self.merge_into_corpus(new_emails, existing_corpus)
        self._merged_corpus = merged

        if progress_callback:
            progress_callback(f"Merged corpus: {len(merged.emails)} emails ({len(new_emails)} new)")

        # Step 3: Reassign to clusters (if analysis available and new emails exist)
        if existing_analysis is not None and new_emails:
            updated_analysis = self.reassign_to_clusters(
                new_emails, existing_analysis, progress_callback=progress_callback
            )
            self._updated_analysis = updated_analysis
        elif existing_analysis is not None:
            self._updated_analysis = existing_analysis
        else:
            self._updated_analysis = None

        # Step 4: Categorize new emails (if rules available and new emails exist)
        categorizations: list[EmailCategorization] = []
        if rule_set is not None and new_emails:
            categorizations = self.categorize_new(
                new_emails, rule_set, progress_callback=progress_callback
            )

        elapsed = time.monotonic() - start_time

        if progress_callback:
            progress_callback(
                f"Incremental processing complete: {len(new_emails)} new emails, "
                f"{elapsed:.1f}s elapsed"
            )

        return IncrementalResult(
            new_email_count=len(new_emails),
            merged_corpus_size=len(merged.emails),
            new_categorizations=categorizations,
            processing_time=round(elapsed, 3),
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _compute_embeddings(self, emails: list[Email]) -> np.ndarray:
        """Compute embeddings for a list of emails using sentence-transformers.

        Loads the model lazily on first call. Uses the same model and text
        preparation as the SemanticAnalyzer for consistency.

        Args:
            emails: Emails to embed.

        Returns:
            numpy array of shape (len(emails), embedding_dim).
        """
        from sentence_transformers import SentenceTransformer

        if not hasattr(self, "_embed_model") or self._embed_model is None:
            self._embed_model = SentenceTransformer("mixedbread-ai/mxbai-embed-large-v1")

        texts = [email.combined_text_with_limit(1500) for email in emails]
        embeddings: np.ndarray = self._embed_model.encode(
            texts, show_progress_bar=False, convert_to_numpy=True
        )
        return embeddings

    def _compute_centroids(self, clusters: list[ContentCluster]) -> np.ndarray:
        """Compute centroid vectors for existing clusters.

        Since we don't store per-email embeddings, this method computes a
        representative centroid by encoding the cluster's representative
        samples and averaging their embeddings.

        Args:
            clusters: List of ContentCluster objects.

        Returns:
            numpy array of shape (num_clusters, embedding_dim).
        """
        from sentence_transformers import SentenceTransformer

        if not hasattr(self, "_embed_model") or self._embed_model is None:
            self._embed_model = SentenceTransformer("mixedbread-ai/mxbai-embed-large-v1")

        centroids = []
        for cluster in clusters:
            # Use representative samples to approximate the centroid
            texts = [
                f"{sample.subject} {sample.body_preview}"
                for sample in cluster.representative_samples
            ]
            if not texts:
                # Fallback: use a zero vector (should not happen with valid clusters)
                centroids.append(np.zeros(self._embed_model.get_sentence_embedding_dimension()))
                continue

            sample_embeddings = self._embed_model.encode(
                texts, show_progress_bar=False, convert_to_numpy=True
            )
            centroid = np.mean(sample_embeddings, axis=0)
            centroids.append(centroid)

        return np.array(centroids)


__all__ = ["IncrementalProcessor", "IncrementalResult"]
