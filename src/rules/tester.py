"""
Rule tester for dry-running rules against a corpus (Phase 3, Item 3.4).

Provides:
- RuleTester: Evaluate a RuleSet against every email in a Corpus
- TestReport: Per-rule match counts, coverage stats, conflicts, confusion matrix
- ConfusionMatrix: Pairwise overlap between rules
"""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Callable

from pydantic import BaseModel, Field, computed_field

from src.models.corpus import Corpus
from src.models.rule import RuleSet
from src.rules.engine import RuleEngine

logger = logging.getLogger(__name__)

# Maximum number of example subjects/senders to store per rule match detail
_MAX_EXAMPLES = 5


# =============================================================================
# Data models
# =============================================================================


class RuleMatchDetail(BaseModel):
    """Per-rule match statistics from a test run."""

    rule_id: str = Field(..., description="ID of the rule")
    rule_name: str = Field(..., description="Human-readable rule name")
    match_count: int = Field(default=0, ge=0, description="Number of emails matched")
    matched_email_ids: list[str] = Field(
        default_factory=list, description="IDs of all matched emails"
    )
    example_subjects: list[str] = Field(
        default_factory=list, description=f"Up to {_MAX_EXAMPLES} example subjects"
    )
    example_senders: list[str] = Field(
        default_factory=list, description=f"Up to {_MAX_EXAMPLES} example senders"
    )
    match_percentage: float = Field(
        default=0.0, ge=0.0, description="Percentage of corpus matched by this rule"
    )


class ConflictEntry(BaseModel):
    """An email matched by multiple rules with different categories."""

    email_id: str = Field(..., description="ID of the conflicting email")
    matching_rule_ids: list[str] = Field(
        ..., description="IDs of all rules that matched this email"
    )
    matching_rule_names: list[str] = Field(
        ..., description="Names of all rules that matched this email"
    )


class ConfusionCell(BaseModel):
    """A single cell in the confusion matrix."""

    row_rule_id: str = Field(..., description="Row rule ID")
    col_rule_id: str = Field(..., description="Column rule ID")
    count: int = Field(default=0, ge=0, description="Number of overlapping emails")


class ConfusionMatrix(BaseModel):
    """Pairwise overlap matrix between rules.

    Each cell (i, j) counts how many emails are matched by both rule i and rule j.
    Diagonal cells count how many emails each rule matches on its own.
    """

    rule_ids: list[str] = Field(..., description="Ordered list of rule IDs (row/column labels)")
    rule_names: dict[str, str] = Field(
        default_factory=dict, description="Mapping of rule_id -> rule_name"
    )
    cells: list[ConfusionCell] = Field(default_factory=list, description="All cells in the matrix")

    def get_cell(self, row_rule_id: str, col_rule_id: str) -> ConfusionCell | None:
        """Look up a cell by row and column rule IDs.

        Returns None if either rule ID is not in the matrix.
        """
        if row_rule_id not in self.rule_ids or col_rule_id not in self.rule_ids:
            return None
        for cell in self.cells:
            if cell.row_rule_id == row_rule_id and cell.col_rule_id == col_rule_id:
                return cell
        return None


class TestReport(BaseModel):
    """Complete report from dry-running a RuleSet against a Corpus."""

    total_emails: int = Field(..., ge=0, description="Total emails in the corpus")
    total_rules: int = Field(..., ge=0, description="Total rules in the rule set")
    rule_matches: list[RuleMatchDetail] = Field(
        default_factory=list, description="Per-rule match details, sorted by match_count desc"
    )
    covered_email_ids: set[str] = Field(
        default_factory=set, description="Email IDs matched by at least one rule"
    )
    uncovered_email_ids: set[str] = Field(
        default_factory=set, description="Email IDs not matched by any rule"
    )
    conflicts: list[ConflictEntry] = Field(
        default_factory=list, description="Emails matched by multiple rules (different categories)"
    )
    confusion_matrix: ConfusionMatrix | None = Field(
        default=None, description="Pairwise rule overlap matrix (None if < 2 enabled rules)"
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def coverage_percentage(self) -> float:
        """Percentage of emails covered by at least one rule."""
        if self.total_emails == 0:
            return 0.0
        return len(self.covered_email_ids) / self.total_emails * 100.0

    @computed_field  # type: ignore[prop-decorator]
    @property
    def conflict_count(self) -> int:
        """Number of emails with conflicting rule matches."""
        return len(self.conflicts)


# =============================================================================
# RuleTester
# =============================================================================


class RuleTester:
    """Dry-run a RuleSet against a Corpus and produce a TestReport.

    Uses the existing RuleEngine for individual email evaluation.
    Supports progress callbacks for large corpora.
    """

    def __init__(self) -> None:
        self._engine = RuleEngine()

    def test_rules(
        self,
        rule_set: RuleSet,
        corpus: Corpus,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> TestReport:
        """Evaluate every rule against every email and compile a TestReport.

        Args:
            rule_set: The set of rules to test.
            corpus: The email corpus to test against.
            progress_callback: Optional callback(current, total) invoked
                as each email is processed.

        Returns:
            A TestReport containing per-rule matches, coverage, conflicts,
            and confusion matrix.
        """
        total_emails = len(corpus.emails)
        all_rules = rule_set.rules
        enabled_rules = rule_set.enabled_rules
        total_rules = len(all_rules)

        # Per-rule accumulators (keyed by rule_id)
        rule_matched_ids: dict[str, list[str]] = {r.rule_id: [] for r in all_rules}
        rule_example_subjects: dict[str, list[str]] = {r.rule_id: [] for r in all_rules}
        rule_example_senders: dict[str, list[str]] = {r.rule_id: [] for r in all_rules}

        # Per-email: which rule IDs matched
        email_to_matching_rules: dict[str, list[str]] = defaultdict(list)

        # Evaluate every email against all enabled rules
        for idx, email in enumerate(corpus.emails):
            for rule in enabled_rules:
                if self._engine.evaluate_rule(rule, email):
                    rule_matched_ids[rule.rule_id].append(email.id)
                    email_to_matching_rules[email.id].append(rule.rule_id)

                    # Collect examples (capped)
                    subj_list = rule_example_subjects[rule.rule_id]
                    if len(subj_list) < _MAX_EXAMPLES:
                        subj_list.append(email.subject)

                    sender_list = rule_example_senders[rule.rule_id]
                    if len(sender_list) < _MAX_EXAMPLES:
                        sender_list.append(email.sender_email)

            if progress_callback is not None:
                progress_callback(idx + 1, total_emails)

        # Build per-rule match details
        rule_matches: list[RuleMatchDetail] = []
        for rule in all_rules:
            matched = rule_matched_ids[rule.rule_id]
            match_count = len(matched)
            pct = (match_count / total_emails * 100.0) if total_emails > 0 else 0.0
            rule_matches.append(
                RuleMatchDetail(
                    rule_id=rule.rule_id,
                    rule_name=rule.name,
                    match_count=match_count,
                    matched_email_ids=matched,
                    example_subjects=rule_example_subjects[rule.rule_id],
                    example_senders=rule_example_senders[rule.rule_id],
                    match_percentage=pct,
                )
            )

        # Sort by match count descending
        rule_matches.sort(key=lambda d: d.match_count, reverse=True)

        # Coverage
        all_email_ids = {e.id for e in corpus.emails}
        covered_ids = set(email_to_matching_rules.keys())
        uncovered_ids = all_email_ids - covered_ids

        # Conflicts: emails matched by rules from DIFFERENT categories
        # Build a rule_id -> category_id lookup
        rule_category: dict[str, str | None] = {r.rule_id: r.category_id for r in all_rules}
        rule_name_map: dict[str, str] = {r.rule_id: r.name for r in all_rules}

        conflicts: list[ConflictEntry] = []
        for email_id, matching_rule_ids in email_to_matching_rules.items():
            if len(matching_rule_ids) < 2:
                continue
            # Check if the matching rules span multiple categories
            categories_hit = {rule_category.get(rid) for rid in matching_rule_ids}
            # Filter out None to avoid false conflicts for rules without category_id
            categories_hit.discard(None)
            if len(categories_hit) > 1:
                conflicts.append(
                    ConflictEntry(
                        email_id=email_id,
                        matching_rule_ids=matching_rule_ids,
                        matching_rule_names=[
                            rule_name_map.get(rid, rid) for rid in matching_rule_ids
                        ],
                    )
                )

        # Confusion matrix: pairwise overlap between enabled rules
        confusion_matrix: ConfusionMatrix | None = None
        if len(enabled_rules) >= 2:
            # Build sets of matched email IDs per enabled rule
            enabled_matched_sets: dict[str, set[str]] = {
                r.rule_id: set(rule_matched_ids[r.rule_id]) for r in enabled_rules
            }
            enabled_rule_ids = [r.rule_id for r in enabled_rules]
            enabled_rule_names = {r.rule_id: r.name for r in enabled_rules}

            cells: list[ConfusionCell] = []
            for rid_row in enabled_rule_ids:
                for rid_col in enabled_rule_ids:
                    overlap = len(enabled_matched_sets[rid_row] & enabled_matched_sets[rid_col])
                    cells.append(
                        ConfusionCell(
                            row_rule_id=rid_row,
                            col_rule_id=rid_col,
                            count=overlap,
                        )
                    )

            confusion_matrix = ConfusionMatrix(
                rule_ids=enabled_rule_ids,
                rule_names=enabled_rule_names,
                cells=cells,
            )

        report = TestReport(
            total_emails=total_emails,
            total_rules=total_rules,
            rule_matches=rule_matches,
            covered_email_ids=covered_ids,
            uncovered_email_ids=uncovered_ids,
            conflicts=conflicts,
            confusion_matrix=confusion_matrix,
        )

        logger.info(
            f"Rule test complete: {total_emails} emails, {total_rules} rules, "
            f"{report.coverage_percentage:.1f}% coverage, {report.conflict_count} conflicts"
        )

        return report
