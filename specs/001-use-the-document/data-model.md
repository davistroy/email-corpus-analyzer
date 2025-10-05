# Data Model: Email Corpus Extraction and Analysis System

**Date**: 2025-10-05
**Phase**: Phase 1 - Design & Contracts
**Source**: Extracted from spec.md Key Entities section + functional requirements

---

## Entity Relationship Diagram

```
Corpus (1) ─────< (many) Email
  │                       │
  │                       └─────> (1) Sender
  │
  ├─────> (1) AnalysisResults
  │              │
  │              ├─────> SenderAnalysis
  │              ├─────> SubjectPatterns
  │              ├─────> TemporalPatterns
  │              ├─────> VolumeStats
  │              └─────> (many) ContentCluster
  │
  └─────> (many) Category
                   │
                   └─────< (optional) ContentCluster
```

---

## 1. Email

**Purpose**: Individual email message with complete metadata and content

**File**: `src/models/email.py`

### Attributes

| Field | Type | Required | Validation | Description |
|-------|------|----------|------------|-------------|
| `id` | str | Yes | Non-empty | Unique identifier from M365 API |
| `sender_email` | str | Yes | Email format | Sender's email address |
| `sender_name` | str | No | - | Sender's display name |
| `sender_domain` | str | Yes | Domain format | Extracted from sender_email |
| `recipient_email` | str | No | Email format | Primary recipient email |
| `recipient_name` | str | No | - | Recipient display name |
| `subject` | str | Yes | - | Email subject line (may be empty string) |
| `body_text` | str | Yes | - | Plain text body (HTML converted) |
| `received_date` | datetime | Yes | ISO 8601 | When email was received |
| `has_attachments` | bool | Yes | - | Whether email has attachments |

### Example (JSON)

```json
{
  "id": "AAMkAGI2T...",
  "sender_email": "john@example.com",
  "sender_name": "John Doe",
  "sender_domain": "example.com",
  "recipient_email": "user@hotmail.com",
  "recipient_name": "User Name",
  "subject": "Q3 Project Update",
  "body_text": "Hi team, here's the update on our Q3 progress...",
  "received_date": "2025-09-15T10:30:00Z",
  "has_attachments": false
}
```

### Pydantic Model

```python
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime

class Email(BaseModel):
    id: str = Field(..., min_length=1, description="Unique M365 message ID")
    sender_email: EmailStr
    sender_name: str = ""
    sender_domain: str = Field(..., min_length=1)
    recipient_email: EmailStr | None = None
    recipient_name: str = ""
    subject: str
    body_text: str
    received_date: datetime
    has_attachments: bool

    @property
    def combined_text(self) -> str:
        """Combined subject + body for embeddings."""
        return f"{self.subject} {self.body_text[:500]}"
```

---

## 2. Corpus

**Purpose**: Complete collection of extracted emails with metadata

**File**: `src/models/corpus.py`

### Attributes

| Field | Type | Required | Validation | Description |
|-------|------|----------|------------|-------------|
| `extraction_date` | datetime | Yes | ISO 8601 | When corpus was extracted |
| `total_emails` | int | Yes | >= 0 | Total number of emails |
| `source` | str | Yes | - | Source system (e.g., "Hotmail/M365") |
| `user_email` | str | Yes | Email format | User's email address |
| `emails` | List[Email] | Yes | - | List of all extracted emails |

### Example (JSON)

```json
{
  "extraction_metadata": {
    "extraction_date": "2025-10-05T14:30:00Z",
    "total_emails": 1523,
    "source": "Hotmail/M365",
    "user_email": "user@hotmail.com"
  },
  "emails": [...]
}
```

### Pydantic Model

```python
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import List

class CorpusMetadata(BaseModel):
    extraction_date: datetime
    total_emails: int = Field(..., ge=0)
    source: str
    user_email: EmailStr

class Corpus(BaseModel):
    extraction_metadata: CorpusMetadata
    emails: List[Email] = Field(default_factory=list)

    @property
    def date_range(self) -> tuple[datetime, datetime]:
        """Get oldest and newest email dates."""
        if not self.emails:
            return (self.extraction_metadata.extraction_date,
                    self.extraction_metadata.extraction_date)
        dates = [e.received_date for e in self.emails]
        return (min(dates), max(dates))
```

---

## 3. Sender

**Purpose**: Aggregated sender information with classification

**File**: `src/models/sender.py`

### Attributes

| Field | Type | Required | Validation | Description |
|-------|------|----------|------------|-------------|
| `email` | str | Yes | Email format | Sender's email address |
| `name` | str | No | - | Display name |
| `domain` | str | Yes | Domain format | Email domain |
| `type` | SenderType | Yes | Enum | personal/service/marketing/work |
| `frequency_count` | int | Yes | >= 1 | Total emails from this sender |
| `sample_subjects` | List[str] | No | Max 5 | Sample subject lines |
| `email_ids` | List[str] | Yes | - | IDs of emails from this sender |

### SenderType Enum

```python
from enum import Enum

class SenderType(str, Enum):
    PERSONAL = "personal"
    SERVICE = "service"
    MARKETING = "marketing"
    WORK = "work"
```

### Pydantic Model

```python
from pydantic import BaseModel, EmailStr, Field
from typing import List
from enum import Enum

class SenderType(str, Enum):
    PERSONAL = "personal"
    SERVICE = "service"
    MARKETING = "marketing"
    WORK = "work"

class Sender(BaseModel):
    email: EmailStr
    name: str = ""
    domain: str
    type: SenderType
    frequency_count: int = Field(..., ge=1)
    sample_subjects: List[str] = Field(default_factory=list, max_length=5)
    email_ids: List[str] = Field(default_factory=list)
```

---

## 4. AnalysisResults

**Purpose**: Complete analysis output container

**File**: `src/models/analysis_results.py`

### Structure

```python
from pydantic import BaseModel
from typing import List, Dict

class SenderAnalysis(BaseModel):
    top_senders: List[Sender]
    top_domains: List[Dict[str, int]]  # [{"domain": "example.com", "count": 45}]
    unique_senders: int
    unique_domains: int

class SubjectPatterns(BaseModel):
    common_prefixes: Dict[str, int]  # {"RE:": 45, "FWD:": 23}
    numbered_patterns: Dict[str, int]  # {"Invoice": 12, "Order": 34}
    top_keywords: List[tuple[str, int]]  # [("meeting", 45), ("update", 38)]
    bracket_tags: List[tuple[str, int]]  # [("URGENT", 12), ("Team", 8)]
    total_subjects_analyzed: int

class TemporalPatterns(BaseModel):
    frequency_distribution: Dict[str, int]  # {"daily": 50, "weekly": 30, ...}
    sender_frequencies: Dict[str, Dict]  # {sender_email: {type, count, first, last}}

class VolumeStats(BaseModel):
    total_emails: int
    unique_senders: int
    date_range: Dict[str, str]  # {oldest, newest, span_days}
    with_attachments: int
    attachment_percentage: float
    avg_body_length_chars: int
    emails_per_day: float

class AnalysisResults(BaseModel):
    sender_analysis: SenderAnalysis
    subject_patterns: SubjectPatterns
    content_clusters: List['ContentCluster']
    temporal_patterns: TemporalPatterns
    volume_stats: VolumeStats
```

---

## 5. ContentCluster

**Purpose**: Thematic grouping from semantic analysis

**File**: `src/models/content_cluster.py`

### Attributes

| Field | Type | Required | Validation | Description |
|-------|------|----------|------------|-------------|
| `cluster_id` | int | Yes | >= 0 | Cluster index |
| `size` | int | Yes | >= 1 | Number of emails in cluster |
| `percentage` | float | Yes | 0-100 | Percentage of total corpus |
| `representative_samples` | List[Dict] | Yes | Max 5 | Sample emails closest to centroid |
| `common_domains` | List[tuple] | No | - | Most frequent sender domains |
| `email_ids` | List[str] | Yes | - | All email IDs in this cluster |

### Pydantic Model

```python
from pydantic import BaseModel, Field
from typing import List, Dict, Tuple

class RepresentativeSample(BaseModel):
    subject: str
    sender: str
    body_preview: str = Field(..., max_length=200)

class ContentCluster(BaseModel):
    cluster_id: int = Field(..., ge=0)
    size: int = Field(..., ge=1)
    percentage: float = Field(..., ge=0, le=100)
    representative_samples: List[RepresentativeSample] = Field(..., max_length=5)
    common_domains: List[Tuple[str, int]] = Field(default_factory=list)
    email_ids: List[str] = Field(default_factory=list)
```

---

## 6. Category

**Purpose**: Suggested or approved email classification

**File**: `src/models/category.py`

### Attributes

| Field | Type | Required | Validation | Description |
|-------|------|----------|------------|-------------|
| `category_id` | str | Yes | Non-empty | Unique identifier (e.g., "cat_001") |
| `category_name` | str | Yes | Non-empty | User-facing category name |
| `description` | str | Yes | - | Category description |
| `confidence` | float | Yes | 0-1 | Confidence score |
| `email_count` | int | No | >= 0 | Estimated emails in category |
| `percentage` | float | No | 0-100 | Percentage of corpus |
| `source` | CategorySource | Yes | Enum | Origin: cluster/sender/template/custom |
| `source_id` | str | No | - | ID of source (cluster_id, sender, etc.) |
| `user_modified` | bool | Yes | - | Whether user edited this category |
| `distinguishing_features` | List[str] | No | - | Key characteristics |
| `example_email_ids` | List[str] | No | Max 10 | Sample email IDs |

### CategorySource Enum

```python
from enum import Enum

class CategorySource(str, Enum):
    CONTENT_CLUSTER = "content_cluster"
    SENDER = "sender"
    TEMPLATE = "template"
    CUSTOM = "custom"
```

### Pydantic Model

```python
from pydantic import BaseModel, Field
from typing import List
from enum import Enum

class CategorySource(str, Enum):
    CONTENT_CLUSTER = "content_cluster"
    SENDER = "sender"
    TEMPLATE = "template"
    CUSTOM = "custom"

class Category(BaseModel):
    category_id: str = Field(..., min_length=1)
    category_name: str = Field(..., min_length=1)
    description: str
    confidence: float = Field(..., ge=0, le=1)
    email_count: int | None = Field(None, ge=0)
    percentage: float | None = Field(None, ge=0, le=100)
    source: CategorySource
    source_id: str | None = None
    user_modified: bool = False
    distinguishing_features: List[str] = Field(default_factory=list)
    example_email_ids: List[str] = Field(default_factory=list, max_length=10)
```

---

## 7. CategoryTemplate

**Purpose**: Predefined category pattern for matching

**File**: `src/models/category_template.py`

### Attributes

| Field | Type | Required | Validation | Description |
|-------|------|----------|------------|-------------|
| `name` | str | Yes | Non-empty | Template category name |
| `keywords` | List[str] | Yes | Non-empty | Keywords to match in subject/body |
| `domains` | List[str] | No | - | Sender domains to match |
| `description` | str | Yes | - | Template description |

### Predefined Templates (from spec FR-024)

1. Financial & Banking
2. Shopping & E-commerce
3. Social Media
4. Newsletters & Marketing
5. Travel & Transportation
6. Account & Security

### Pydantic Model

```python
from pydantic import BaseModel, Field
from typing import List

class CategoryTemplate(BaseModel):
    name: str = Field(..., min_length=1)
    keywords: List[str] = Field(..., min_length=1)
    domains: List[str] = Field(default_factory=list)
    description: str

# Predefined templates constant
PREDEFINED_TEMPLATES = [
    CategoryTemplate(
        name="Financial & Banking",
        keywords=["invoice", "payment", "bank", "statement", "bill", "credit"],
        domains=["paypal.com", "chase.com", "bankofamerica.com", "stripe.com"],
        description="Financial transactions, banking, and billing"
    ),
    CategoryTemplate(
        name="Shopping & E-commerce",
        keywords=["order", "shipped", "delivery", "purchase", "receipt"],
        domains=["amazon.com", "ebay.com", "etsy.com", "shopify.com"],
        description="Online shopping confirmations and shipping updates"
    ),
    # ... (other 4 templates)
]
```

---

## Validation Rules

### Cross-Entity Constraints

1. **Corpus.total_emails == len(Corpus.emails)**
2. **All Email.id values must be unique within Corpus**
3. **Sender.email_ids must reference valid Email.id values**
4. **ContentCluster.email_ids must reference valid Email.id values**
5. **Category.example_email_ids must reference valid Email.id values**
6. **Sum of all ContentCluster.percentage values should ≈ 100% (within rounding)**

### File Output Constraints

1. **All datetime fields**: ISO 8601 format with 'Z' suffix
2. **All JSON files**: UTF-8 encoding, pretty-printed with indent=2
3. **File permissions**: 0600 (user read/write only) per Constitution Principle IV
4. **Output directory**: `/mnt/user-data/outputs/` (per spec FR-007)

---

## State Transitions

### Email Processing States

```
[Raw M365 Data]
    → (extract) →
[Email object with HTML body]
    → (parse HTML) →
[Email object with plain text body]
    → (save to corpus) →
[Persisted in email_corpus.json]
```

### Category Lifecycle

```
[ContentCluster]
    → (generate suggestion) →
[Category (source=content_cluster, user_modified=false)]
    → (user reviews) →
[Category (user_modified=true)] OR [Deleted] OR [Merged with another]
    → (user approves) →
[Saved in approved_categories.json]
```

### Corpus Overwrite Behavior (per Clarification Q3)

```
[Existing email_corpus.json]
    + (re-run extraction) →
[Completely overwritten with new extraction]
```

---

## Memory Considerations

### For 10,000 Emails

- **Email objects**: ~5KB each = 50MB
- **Text embeddings** (384-dim float32): 384 * 4 bytes * 10k = ~15MB
- **Binary quantized embeddings**: 384 / 8 bytes * 10k = ~0.5MB
- **Total in-memory peak**: ~100-150MB (manageable)

### Optimization Strategies

1. Use generators when loading corpus (don't load all emails at once)
2. Use binary quantization for embeddings (32x memory reduction)
3. Process analysis in batches (Constitution Principle VII - streaming)
4. Delete intermediate results after each phase (per Clarification Q1 - optional cleanup)

---

## Next Steps (Contract Generation)

Based on these data models, generate contracts for:

1. **ExtractorContract**: Email extraction from M365
2. **AnalyzerContract**: Each analyzer module (sender, subject, semantic, temporal, volume)
3. **GeneratorContract**: Category generation
4. **ReviewContract**: Interactive category review

See `contracts/` directory for OpenAPI-style contracts.
