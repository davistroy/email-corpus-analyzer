# Contract: Email Analyzers

**Modules**: `src/analyzers/*_analyzer.py`
**Purpose**: Analyze email corpus across multiple dimensions
**Constitution Compliance**: Modular (Principle V), Progress transparency (Principle VII)

---

## Base Analyzer Interface

```python
class Analyzer(Protocol):
    """Base contract for all analyzer modules."""

    def analyze(
        self,
        corpus: Corpus,
        progress_callback: Callable[[int, int], None] | None = None
    ) -> AnalysisResult:
        """
        Analyze email corpus.

        Args:
            corpus: Complete email corpus
            progress_callback: Optional callback(current, total)

        Returns:
            Analysis results specific to analyzer type

        Raises:
            ValueError: If corpus is empty or invalid
        """
        ...
```

---

## 1. Sender Analyzer Contract

**File**: `src/analyzers/sender_analyzer.py`

### Interface

```python
class SenderAnalyzer(Analyzer):
    def analyze(self, corpus: Corpus, progress_callback=None) -> SenderAnalysis:
        """
        Analyze sender patterns.

        Returns:
            SenderAnalysis with top_senders, top_domains, unique counts
        """
        ...

    def classify_sender_type(self, sender: Sender) -> SenderType:
        """
        Classify sender as personal/service/marketing/work.

        Args:
            sender: Sender object with domain, count, sample_subjects

        Returns:
            SenderType enum value
        """
        ...
```

### Behavioral Requirements (FR-012, FR-013)

- **MUST** count emails per sender
- **MUST** extract top 50 senders by frequency
- **MUST** extract top 30 domains by frequency
- **MUST** classify each sender using heuristics:
  - Service: domains contain "noreply", "no-reply", "notification"
  - Marketing: >10 emails + keywords "unsubscribe", "promotional", "offer"
  - Work: keywords "meeting", "project", "team", "re:", "fwd:"
  - Personal: default

### Test Cases

```python
def test_sender_analysis_counts():
    """GIVEN corpus with 100 emails from 10 unique senders
       WHEN analyze() called
       THEN unique_senders == 10
       AND top_senders contains all 10 senders sorted by count
    """

def test_classify_service_sender():
    """GIVEN sender with domain "noreply@service.com"
       WHEN classify_sender_type() called
       THEN returns SenderType.SERVICE
    """

def test_classify_marketing_sender():
    """GIVEN sender with 15 emails containing "unsubscribe"
       WHEN classify_sender_type() called
       THEN returns SenderType.MARKETING
    """
```

---

## 2. Subject Analyzer Contract

**File**: `src/analyzers/subject_analyzer.py`

### Interface

```python
class SubjectAnalyzer(Analyzer):
    def analyze(self, corpus: Corpus, progress_callback=None) -> SubjectPatterns:
        """
        Analyze subject line patterns.

        Returns:
            SubjectPatterns with prefixes, numbered patterns, keywords, tags
        """
        ...
```

### Behavioral Requirements (FR-014)

- **MUST** extract common prefixes: RE:, FWD:, Fwd:, Re: (case-insensitive)
- **MUST** extract numbered patterns: regex `(\w+)\s*[#№]\s*\d+`
- **MUST** extract top 50 keywords excluding stop words
- **MUST** extract bracket tags: regex `[\[\(]([^\]\)]+)[\]\)]`

### Test Cases

```python
def test_extract_prefixes():
    """GIVEN subjects ["RE: Meeting", "Fwd: Update", "Hello"]
       WHEN analyze() called
       THEN common_prefixes == {"RE:": 1, "FWD:": 1}
    """

def test_extract_numbered_patterns():
    """GIVEN subjects ["Invoice #12345", "Order #456"]
       WHEN analyze() called
       THEN numbered_patterns == {"Invoice": 1, "Order": 1}
    """

def test_filter_stop_words():
    """GIVEN subjects containing "the", "and", "a"
       WHEN analyze() called
       THEN top_keywords does not include stop words
    """
```

---

## 3. Semantic Analyzer Contract

**File**: `src/analyzers/semantic_analyzer.py`

### Interface

```python
class SemanticAnalyzer(Analyzer):
    def __init__(self, model_name: str = "mixedbread-ai/mxbai-embed-large-v1"):
        """
        Initialize with sentence transformer model.

        Args:
            model_name: Hugging Face model identifier
        """
        ...

    def analyze(
        self,
        corpus: Corpus,
        num_clusters: int = 10,
        progress_callback=None
    ) -> List[ContentCluster]:
        """
        Perform semantic clustering.

        Args:
            corpus: Email corpus
            num_clusters: Number of clusters (default 10)
            progress_callback: Progress tracking

        Returns:
            List of ContentCluster objects
        """
        ...
```

### Behavioral Requirements (FR-015, FR-016, FR-017)

- **MUST** use sentence-transformers for embeddings
- **MUST** combine subject + first 500 chars of body for embedding
- **MUST** use scikit-learn KMeans for clustering
- **MUST** default to 10 clusters, configurable
- **MUST** identify 5 representative samples per cluster (closest to centroid)
- **MUST** show progress for operations >10 seconds

### Test Cases

```python
def test_semantic_clustering():
    """GIVEN corpus with 100 emails
       WHEN analyze(num_clusters=5) called
       THEN returns 5 ContentCluster objects
       AND sum of cluster sizes == 100
    """

def test_representative_samples():
    """GIVEN cluster with 20 emails
       WHEN representative samples extracted
       THEN returns 5 samples closest to cluster centroid
    """

def test_progress_callback_long_operation():
    """GIVEN large corpus (1000+ emails)
       WHEN analyze() called with progress_callback
       THEN callback invoked multiple times during embedding
       AND callback invoked during clustering
    """
```

---

## 4. Temporal Analyzer Contract

**File**: `src/analyzers/temporal_analyzer.py`

### Interface

```python
class TemporalAnalyzer(Analyzer):
    def analyze(self, corpus: Corpus, progress_callback=None) -> TemporalPatterns:
        """
        Analyze temporal email patterns.

        Returns:
            TemporalPatterns with frequency classifications
        """
        ...

    def classify_frequency(self, dates: List[datetime]) -> str:
        """
        Classify sender frequency.

        Args:
            dates: List of email received dates (sorted)

        Returns:
            "one-time" | "daily" | "weekly" | "monthly" | "occasional"
        """
        ...
```

### Behavioral Requirements (FR-018)

- **MUST** classify senders by frequency:
  - one-time: 1 email
  - daily: avg interval < 2 days (>=10 emails)
  - weekly: avg interval < 8 days (>=10 emails)
  - monthly: avg interval < 35 days (>=10 emails)
  - occasional: default

### Test Cases

```python
def test_classify_daily_sender():
    """GIVEN sender with 15 emails over 15 days
       WHEN classify_frequency() called
       THEN returns "daily"
    """

def test_classify_one_time_sender():
    """GIVEN sender with 1 email
       WHEN classify_frequency() called
       THEN returns "one-time"
    """
```

---

## 5. Volume Analyzer Contract

**File**: `src/analyzers/volume_analyzer.py`

### Interface

```python
class VolumeAnalyzer(Analyzer):
    def analyze(self, corpus: Corpus, progress_callback=None) -> VolumeStats:
        """
        Calculate corpus volume statistics.

        Returns:
            VolumeStats with counts, date ranges, averages
        """
        ...
```

### Behavioral Requirements (FR-019)

- **MUST** calculate: total_emails, unique_senders, date_range
- **MUST** calculate: with_attachments count and percentage
- **MUST** calculate: avg_body_length_chars
- **MUST** calculate: emails_per_day (total / span_days)

### Test Cases

```python
def test_volume_statistics():
    """GIVEN corpus with 100 emails over 10 days
       WHEN analyze() called
       THEN volume_stats.total_emails == 100
       AND volume_stats.emails_per_day == 10.0
    """
```

---

## Master Analyzer Orchestrator

**File**: `src/analyzers/__init__.py`

```python
def run_full_analysis(
    corpus: Corpus,
    num_clusters: int = 10,
    progress_callback: Callable[[str, int, int], None] | None = None
) -> AnalysisResults:
    """
    Run all analyzers and combine results.

    Args:
        corpus: Complete email corpus
        num_clusters: Number of semantic clusters
        progress_callback: Optional callback(analyzer_name, current, total)

    Returns:
        AnalysisResults with all analysis components
    """
    results = AnalysisResults()

    # FR-012: Sender analysis
    results.sender_analysis = SenderAnalyzer().analyze(corpus,
        lambda c, t: progress_callback("sender", c, t) if progress_callback else None)

    # FR-014: Subject analysis
    results.subject_patterns = SubjectAnalyzer().analyze(corpus,
        lambda c, t: progress_callback("subject", c, t) if progress_callback else None)

    # FR-015: Semantic analysis
    results.content_clusters = SemanticAnalyzer().analyze(corpus, num_clusters,
        lambda c, t: progress_callback("semantic", c, t) if progress_callback else None)

    # FR-018: Temporal analysis
    results.temporal_patterns = TemporalAnalyzer().analyze(corpus,
        lambda c, t: progress_callback("temporal", c, t) if progress_callback else None)

    # FR-019: Volume statistics
    results.volume_stats = VolumeAnalyzer().analyze(corpus,
        lambda c, t: progress_callback("volume", c, t) if progress_callback else None)

    return results
```

### Test Case

```python
def test_run_full_analysis():
    """GIVEN corpus with 100 emails
       WHEN run_full_analysis() called
       THEN returns AnalysisResults with all 5 components populated
       AND each component has valid data
    """
```
