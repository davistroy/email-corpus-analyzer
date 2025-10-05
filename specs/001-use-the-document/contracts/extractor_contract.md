# Contract: Email Extractor

**Module**: `src/extractors/m365_extractor.py`
**Purpose**: Extract emails from M365 MCP server and convert to Email objects
**Constitution Compliance**: Modular, testable (Principle V), Error resilient (Principle VI)

---

## Interface

```python
class EmailExtractor(Protocol):
    """Contract for email extraction from M365."""

    def extract_all(
        self,
        max_batch_size: int = 500,
        checkpoint_interval: int = 100,
        progress_callback: Callable[[int, int], None] | None = None
    ) -> ExtractionResult:
        """
        Extract all emails from connected M365 inbox.

        Args:
            max_batch_size: Maximum emails per API request (default 500)
            checkpoint_interval: Save checkpoint every N emails (default 100)
            progress_callback: Optional callback(current, total) for progress tracking

        Returns:
            ExtractionResult with corpus and error summary

        Raises:
            ConnectionError: If M365 MCP server unreachable
            AuthenticationError: If M365 authentication fails
        """
        ...

    def resume_from_checkpoint(
        self,
        checkpoint_path: str
    ) -> ExtractionResult:
        """
        Resume interrupted extraction from checkpoint.

        Args:
            checkpoint_path: Path to checkpoint file

        Returns:
            ExtractionResult continuing from checkpoint

        Raises:
            FileNotFoundError: If checkpoint doesn't exist
            ValueError: If checkpoint corrupted
        """
        ...
```

---

## Data Structures

```python
from dataclasses import dataclass
from typing import List
from models.email import Email
from models.corpus import Corpus

@dataclass
class ExtractionError:
    email_id: str
    error_type: str  # "rate_limit", "timeout", "malformed", "unknown"
    error_message: str
    timestamp: datetime

@dataclass
class ExtractionResult:
    corpus: Corpus
    failed_emails: List[ExtractionError]
    success_count: int
    failure_count: int
    total_attempted: int

    @property
    def success_rate(self) -> float:
        return self.success_count / self.total_attempted if self.total_attempted > 0 else 0.0
```

---

## Behavioral Requirements

### FR-001: M365 Connection
- **MUST** connect to M365 MCP server via MCP protocol
- **MUST** validate connection before extraction starts
- **MUST** raise ConnectionError if server unreachable

### FR-002: Pagination
- **MUST** use pagination with configurable batch size
- **MUST** default to max_batch_size=500
- **MUST** handle `@odata.nextLink` tokens from M365 responses

### FR-005: Error Handling
- **MUST** log errors without halting process
- **MUST** continue to next email on individual failure
- **MUST** collect all errors in ExtractionResult.failed_emails

### FR-006: Retry Logic
- **MUST** implement exponential backoff for rate limits (1s, 2s, 4s)
- **MUST** retry up to 3 times per email
- **MUST** raise after max retries only for critical errors

### FR-009: Progress Tracking
- **MUST** call progress_callback(current, total) if provided
- **MUST** update after each batch processed
- **MUST** show percentage complete

### FR-010: Checkpointing
- **MUST** save checkpoint every checkpoint_interval emails
- **MUST** include: emails_processed, last_processed_id, timestamp
- **MUST** allow resumption from checkpoint

---

## Test Cases (Contract Tests)

### Test 1: Successful Full Extraction
```python
def test_extract_all_success():
    """GIVEN M365 connection with 100 emails
       WHEN extract_all() called
       THEN all 100 emails extracted
       AND result.success_count == 100
       AND result.failure_count == 0
    """
```

### Test 2: Handle Rate Limit
```python
def test_extract_handles_rate_limit():
    """GIVEN M365 returns rate limit error on email 50
       WHEN extract_all() called
       THEN extractor retries with exponential backoff
       AND continues after backoff
       AND extracts remaining emails
    """
```

### Test 3: Resume from Checkpoint
```python
def test_resume_from_checkpoint():
    """GIVEN checkpoint saved at email 100 of 200
       WHEN resume_from_checkpoint() called
       THEN extraction starts from email 101
       AND completes emails 101-200
       AND does not re-extract emails 1-100
    """
```

### Test 4: Continue on Individual Failure
```python
def test_continue_on_malformed_email():
    """GIVEN email 50 is malformed
       WHEN extract_all() called
       THEN email 50 added to failed_emails
       AND extraction continues with email 51
       AND success_count == 99
       AND failure_count == 1
    """
```

### Test 5: Progress Callback
```python
def test_progress_callback_invoked():
    """GIVEN progress_callback provided
       WHEN extract_all() called with 100 emails
       THEN callback invoked after each batch
       AND final call is callback(100, 100)
    """
```

---

## Performance Requirements

- **Throughput**: Best-effort (per Clarification Q4), target 50-100 emails/min
- **Memory**: Use streaming, don't load all emails in memory at once
- **Checkpoint frequency**: Default 100 emails, configurable
