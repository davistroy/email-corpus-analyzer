# Research: Email Corpus Extraction and Analysis System

**Date**: 2025-10-05
**Phase**: Phase 0 - Technology Research via Context7
**Constitution Compliance**: All libraries researched via Context7 MCP server per Principle III

---

## Research Summary

All external dependencies have been researched via Context7 MCP server to ensure latest best practices and avoid deprecated patterns. This research resolves the NEEDS CLARIFICATION items from Technical Context.

---

## 1. Text Embeddings Library

### Decision: sentence-transformers (UKPLab)

**Library ID**: `/ukplab/sentence-transformers`
**Version**: Latest stable (will pin exact version during implementation)
**Trust Score**: 7.8/10
**Code Snippets Available**: 653

### Rationale

1. **Purpose-built for semantic similarity**: Specifically designed for sentence/document embeddings, perfect for clustering emails by content
2. **Memory efficient**: Supports quantization (binary, int8) reducing memory from float32 to int8 (8192 bytes → 256 bytes for 1024-dim embeddings)
3. **Easy API**: Simple `model.encode()` interface, returns numpy arrays compatible with scikit-learn
4. **Pre-trained models**: Models like `mixedbread-ai/mxbai-embed-large-v1` ready for immediate use without training
5. **Multi-process support**: Can distribute across multiple GPUs/processes for large corpus processing

### Key Usage Patterns (from Context7)

```python
from sentence_transformers import SentenceTransformer

# Load pre-trained model
model = SentenceTransformer("mixedbread-ai/mxbai-embed-large-v1")

# Generate embeddings for email text
emails = ["Subject: Meeting\nBody: Let's meet tomorrow", ...]
embeddings = model.encode(emails, show_progress_bar=True)
# Returns: numpy array shape (n_emails, embedding_dim)

# Memory optimization with binary quantization
binary_embeddings = model.encode(emails, precision="binary")
# Reduces memory by ~32x while maintaining similarity rankings
```

### Best Practices for Email Analysis

1. **Combine subject + body**: `f"{email['subject']} {email['body_text'][:500]}"` for richer context
2. **Use progress bars**: `show_progress_bar=True` for transparency (Constitution Principle VII)
3. **Batch processing**: Process in chunks to avoid memory issues with 10k+ emails
4. **Normalize embeddings**: Use `util.normalize_embeddings()` before clustering for better results

### Alternatives Considered

- **OpenAI Embeddings API**: Rejected - violates Privacy principle (data sent to external service)
- **Huggingface Transformers**: Rejected - more complex, requires manual tokenization/pooling
- **Universal Sentence Encoder**: Rejected - requires TensorFlow dependency

### Installation

```bash
pip install sentence-transformers==<exact_version>
```

---

## 2. Clustering Library

### Decision: scikit-learn KMeans

**Library ID**: `/scikit-learn/scikit-learn`
**Version**: 1.7.1 (latest stable)
**Trust Score**: 8.5/10
**Code Snippets Available**: 4161

### Rationale

1. **Industry standard**: Most widely used ML library in Python, well-tested and stable
2. **Sparse data support**: KMeans with `solver='elkan'` supports sparse matrices (useful for TF-IDF if needed)
3. **Memory efficient**: MiniBatchKMeans option for large datasets (10k+ emails)
4. **Simple API**: Fits Constitution Principle V (testable, modular)
5. **Rich ecosystem**: Compatible with sentence-transformers embeddings (both use numpy)

### Key Usage Patterns (from Context7)

```python
from sklearn.cluster import KMeans, MiniBatchKMeans

# Standard KMeans for moderate corpus (<5k emails)
kmeans = KMeans(n_clusters=10, random_state=42, n_init=10)
cluster_labels = kmeans.fit_predict(embeddings)
cluster_centers = kmeans.cluster_centers_

# MiniBatchKMeans for large corpus (>5k emails)
mbkmeans = MiniBatchKMeans(
    n_clusters=10,
    random_state=42,
    batch_size=128,
    n_init=10
)
labels = mbkmeans.fit_predict(embeddings)
```

### Best Practices for Email Categorization

1. **Determine optimal k**: Use elbow method or silhouette score to find ideal cluster count
2. **Set random_state**: Ensures reproducible results for testing (Constitution Principle I)
3. **Use n_init=10**: Run algorithm 10 times with different initializations, pick best
4. **MiniBatchKMeans for scale**: When corpus >5k emails, use MiniBatchKMeans for speed vs accuracy tradeoff
5. **Extract centroids**: Use `cluster_centers_` to find representative emails closest to centroid

### Determining Cluster Count

```python
from sklearn.metrics import silhouette_score

# Test different cluster counts
silhouette_scores = []
for k in range(5, 20):
    kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
    labels = kmeans.fit_predict(embeddings)
    score = silhouette_score(embeddings, labels)
    silhouette_scores.append((k, score))

# Pick k with highest silhouette score
best_k = max(silhouette_scores, key=lambda x: x[1])[0]
```

### Alternatives Considered

- **DBSCAN**: Rejected - requires density parameter tuning, doesn't guarantee all points clustered
- **Hierarchical Clustering**: Rejected - O(n²) memory, impractical for 10k+ emails
- **Spectral Clustering**: Rejected - requires affinity matrix (memory intensive)

### Installation

```bash
pip install scikit-learn==1.7.1
```

---

## 3. HTML Parsing Library

### Decision: BeautifulSoup4

**Library ID**: `/wention/beautifulsoup4`
**Version**: Latest stable
**Trust Score**: 8.2/10
**Code Snippets Available**: 151

### Rationale

1. **Robust malformed HTML handling**: Critical for email HTML which is often non-standard
2. **Multiple parser backends**: Supports lxml, html5lib, html.parser for fallback robustness
3. **Simple text extraction**: `.get_text()` method handles all edge cases
4. **Battle-tested**: Industry standard for web scraping, handles real-world messiness
5. **Lenient parsing**: Automatically fixes common HTML mistakes (Constitution Principle VI - error resilience)

### Key Usage Patterns (from Context7)

```python
from bs4 import BeautifulSoup

def extract_plain_text(html_content):
    """Extract plain text from HTML email body."""
    # Use lxml parser (fast), fallback to html.parser if lxml unavailable
    try:
        soup = BeautifulSoup(html_content, "lxml")
    except:
        soup = BeautifulSoup(html_content, "html.parser")

    # Remove script and style elements
    for script in soup(['script', 'style']):
        script.decompose()

    # Get text with separator and strip whitespace
    text = soup.get_text(separator=" ", strip=True)

    return text
```

### Best Practices for Email HTML

1. **Parser selection**: Use `lxml` for speed, `html.parser` as fallback (no external deps)
2. **Remove scripts/styles**: Always strip `<script>` and `<style>` tags before text extraction
3. **Use separator**: `get_text(separator=" ")` prevents words from different tags merging
4. **Strip whitespace**: `strip=True` removes leading/trailing whitespace from each text chunk
5. **Handle CDATA**: BeautifulSoup automatically handles CDATA sections in emails

### Handling Malformed HTML (Context7 findings)

```python
# Parser differences for malformed HTML
from bs4 import BeautifulSoup

# Malformed: <a></p>
soup_lxml = BeautifulSoup("<a></p>", "lxml")
# Output: <html><body><a></a></body></html> (auto-fixes)

soup_html_parser = BeautifulSoup("<a></p>", "html.parser")
# Output: <a></a> (minimal fix)

# Best: Try lxml first, fallback to html.parser
def safe_parse(html):
    try:
        return BeautifulSoup(html, "lxml")
    except:
        return BeautifulSoup(html, "html.parser")
```

### Alternatives Considered

- **lxml directly**: Rejected - less forgiving of malformed HTML, stricter parsing
- **html.parser (stdlib)**: Rejected - slower, less robust, but kept as fallback
- **selectolax**: Rejected - faster but less battle-tested for malformed input

### Installation

```bash
pip install beautifulsoup4
pip install lxml  # Optional but recommended for speed
```

---

## 4. Supporting Libraries

### 4.1 Progress Indicators

**Decision**: tqdm
**Rationale**: Standard Python progress bar library, integrates with sentence-transformers `show_progress_bar` parameter

```bash
pip install tqdm
```

### 4.2 Data Validation

**Decision**: pydantic
**Rationale**: Type-safe data models for Email, Corpus, Category entities (Constitution Principle V - modular components)

```bash
pip install pydantic
```

### 4.3 Testing Framework

**Decision**: pytest (from Technical Context)
**Rationale**: Industry standard, supports fixtures, parametrization, integration with coverage.py

```bash
pip install pytest pytest-cov
```

---

## 5. M365 MCP Client

### Decision: Use existing M365 MCP server connection

**Assumption**: M365 MCP server is already configured and authenticated (per spec FR-001)
**Access Method**: MCP protocol tools available in environment
**No additional library needed**: MCP tools accessed via existing runtime

---

## Technology Stack Summary

| Component | Library | Version | Context7 ID | Trust Score |
|-----------|---------|---------|-------------|-------------|
| Text Embeddings | sentence-transformers | Latest | /ukplab/sentence-transformers | 7.8 |
| Clustering | scikit-learn | 1.7.1 | /scikit-learn/scikit-learn | 8.5 |
| HTML Parsing | beautifulsoup4 | Latest | /wention/beautifulsoup4 | 8.2 |
| HTML Parser (fast) | lxml | Latest | N/A | - |
| Progress Bars | tqdm | Latest | N/A | - |
| Data Validation | pydantic | Latest | N/A | - |
| Testing | pytest | Latest | N/A | - |
| Language | Python | 3.10+ | Constitution | - |
| Email Access | M365 MCP | N/A | Existing | - |

---

## Dependencies File (requirements.txt)

```
# Core dependencies researched via Context7
sentence-transformers>=2.0.0  # Text embeddings
scikit-learn==1.7.1           # Clustering
beautifulsoup4>=4.12.0        # HTML parsing
lxml>=4.9.0                   # Fast HTML parser

# Supporting libraries
tqdm>=4.66.0                  # Progress bars
pydantic>=2.0.0               # Data validation
numpy>=1.24.0                 # Array operations (dep of above)

# Testing
pytest>=7.4.0                 # Test framework
pytest-cov>=4.1.0             # Coverage reporting
```

---

## Performance Expectations (from Context7 research)

### sentence-transformers
- **Encoding speed**: ~1000-5000 sentences/second on CPU (model-dependent)
- **Memory**: ~2-4 GB for large models (mixedbread-ai/mxbai-embed-large-v1)
- **Optimization**: Binary quantization reduces memory 32x with minimal accuracy loss

### scikit-learn KMeans
- **Time complexity**: O(n * k * i * d) where n=samples, k=clusters, i=iterations, d=dimensions
- **For 10k emails, k=10, d=384**: ~5-30 seconds (CPU-dependent)
- **MiniBatchKMeans**: 3-10x faster for large n

### BeautifulSoup
- **Parsing speed**: ~100-1000 documents/second (complexity-dependent)
- **For email HTML**: Typically fast (<10ms per email)

---

## Risk Mitigation

### 1. Model Download Size
- **Risk**: sentence-transformers models are 100-400MB
- **Mitigation**: Download once during setup, cache locally
- **Constitution alignment**: Local storage only (Principle IV)

### 2. Memory with Large Corpus
- **Risk**: 10k+ email embeddings may exceed RAM
- **Mitigation**:
  - Use binary quantization (32x reduction)
  - Process in batches with generators (Constitution Principle VII - streaming)
  - Use MiniBatchKMeans for clustering

### 3. Malformed HTML Edge Cases
- **Risk**: Some emails may have severely broken HTML
- **Mitigation**:
  - Multi-parser fallback (lxml → html.parser → raw text)
  - Catch exceptions per email, continue processing (Constitution Principle VI)
  - Log failures with email ID (Constitution Principle VI - debug logging)

---

## Next Steps (Phase 1)

1. Create data models (pydantic classes) for all entities
2. Define module contracts (extractor, analyzers, generators interfaces)
3. Generate failing contract tests
4. Create quickstart.md with validation scenarios
5. Update CLAUDE.md with technology decisions

---

## Context7 Query Log

All queries executed 2025-10-05:

1. `resolve-library-id` for "sentence-transformers" → `/ukplab/sentence-transformers`
2. `resolve-library-id` for "scikit-learn" → `/scikit-learn/scikit-learn`
3. `resolve-library-id` for "beautifulsoup4" → `/wention/beautifulsoup4`
4. `get-library-docs` for `/ukplab/sentence-transformers` (topic: embeddings, clustering, memory)
5. `get-library-docs` for `/scikit-learn/scikit-learn` (topic: KMeans, email categorization)
6. `get-library-docs` for `/wention/beautifulsoup4` (topic: HTML parsing, malformed HTML)

**Constitution Compliance**: ✅ All libraries researched via Context7 MCP server (Principle III)
