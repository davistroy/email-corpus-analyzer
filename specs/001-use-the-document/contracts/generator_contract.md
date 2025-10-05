# Contract: Category Generator

**Module**: `src/generators/category_generator.py`
**Purpose**: Generate category suggestions from analysis results
**Functional Requirements**: FR-022 through FR-030

---

## Interface

```python
class CategoryGenerator(Protocol):
    def generate_suggestions(
        self,
        analysis_results: AnalysisResults,
        min_cluster_percentage: float = 5.0,
        min_sender_count: int = 20
    ) -> List[Category]:
        """
        Generate category suggestions from analysis.

        Args:
            analysis_results: Complete analysis results
            min_cluster_percentage: Minimum cluster size % to suggest (default 5%)
            min_sender_count: Minimum emails from sender to suggest category (default 20)

        Returns:
            List of Category objects sorted by confidence (highest first)
        """
        ...

    def apply_templates(
        self,
        analysis_results: AnalysisResults
    ) -> List[Category]:
        """
        Apply predefined category templates.

        Args:
            analysis_results: Complete analysis results

        Returns:
            List of Category objects from template matching
        """
        ...

    def score_confidence(
        self,
        category: Category,
        total_emails: int
    ) -> float:
        """
        Calculate confidence score for category.

        Args:
            category: Category to score
            total_emails: Total emails in corpus

        Returns:
            Confidence score 0.0-1.0
        """
        ...
```

---

## Behavioral Requirements

### FR-022: Cluster-based Categories
- **MUST** generate categories from ContentClusters where percentage > min_cluster_percentage
- **MUST** use LLM or heuristics to generate category name from cluster samples
- **MUST** set category.source = CategorySource.CONTENT_CLUSTER

### FR-023: Sender-based Categories
- **MUST** generate categories from Senders where frequency_count > min_sender_count
- **MUST** use sender domain + sample subjects for category naming
- **MUST** set category.source = CategorySource.SENDER

### FR-024: Template Application
- **MUST** apply all 6 predefined templates (Financial, Shopping, Social, Newsletters, Travel, Security)
- **MUST** match keywords in subject/body AND/OR domains
- **MUST** set category.source = CategorySource.TEMPLATE

### FR-025: Confidence Scoring
- **MUST** base confidence on: email_count, source_type, percentage_of_corpus
- **MUST** use formula: confidence = avg(volume_score, source_score, percentage_score)
- **MUST** ensure confidence in range [0, 1]

### FR-027: Merge Similar Categories
- **MUST** detect similar category names (Levenshtein distance < 3)
- **MUST** combine categories with >70% overlapping email_ids
- **MUST** keep higher confidence category name

### FR-028: Sort by Confidence
- **MUST** sort final category list by confidence descending
- **MUST** return highest confidence categories first

---

## Test Cases

```python
def test_generate_from_large_cluster():
    """GIVEN cluster with 15% of corpus
       WHEN generate_suggestions() called with min_cluster_percentage=5
       THEN category generated from this cluster
       AND category.source == CategorySource.CONTENT_CLUSTER
    """

def test_skip_small_cluster():
    """GIVEN cluster with 3% of corpus
       WHEN generate_suggestions() called with min_cluster_percentage=5
       THEN no category generated from this cluster
    """

def test_apply_financial_template():
    """GIVEN emails with subjects containing "invoice", "payment"
       WHEN apply_templates() called
       THEN "Financial & Banking" category generated
       AND confidence > 0.5
    """

def test_confidence_scoring():
    """GIVEN category with 200 emails (20% of corpus) from template
       WHEN score_confidence() called
       THEN confidence == avg(volume_score, source_score, percentage_score)
       AND confidence in range [0, 1]
    """

def test_merge_similar_categories():
    """GIVEN categories ["Shopping", "Shop"] with 80% overlap
       WHEN merge step executes
       THEN only one category remains
       AND higher confidence name kept
    """

def test_sort_by_confidence():
    """GIVEN 5 categories with confidences [0.9, 0.3, 0.7, 0.5, 0.8]
       WHEN generate_suggestions() returns
       THEN categories sorted [0.9, 0.8, 0.7, 0.5, 0.3]
    """
```
