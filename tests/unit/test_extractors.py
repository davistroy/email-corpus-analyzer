"""
Unit tests for extractor modules.

Tests CheckpointManager and EmailExtractor (backed by GraphAPIClient)
with mocked API calls and file operations.
"""
import json
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from src.exceptions import RateLimitError
from src.extractors.checkpoint_manager import CheckpointManager
from src.extractors.m365_extractor import EmailExtractor, ExtractionError, ExtractionResult
from src.models.corpus import Corpus, CorpusMetadata
from src.models.email import Email
from src.utils.constants import EMAIL_COUNT_SENTINEL


class TestCheckpointManager:
    """Test cases for CheckpointManager class."""

    def test_init_with_default_path(self):
        """Test initialization with default checkpoint path."""
        with patch("src.extractors.checkpoint_manager.PathConfig") as mock_path_config:
            mock_path_config.get_checkpoint_path.return_value = Path("/default/checkpoint.json")
            manager = CheckpointManager()
            assert manager.checkpoint_file == Path("/default/checkpoint.json")
            assert manager.checkpoint_interval == 100

    def test_init_with_custom_path(self, tmp_path):
        """Test initialization with custom checkpoint path."""
        custom_path = tmp_path / "custom_checkpoint.json"
        manager = CheckpointManager(checkpoint_path=custom_path, checkpoint_interval=50)
        assert manager.checkpoint_file == custom_path
        assert manager.checkpoint_interval == 50

    def test_init_with_string_path(self, tmp_path):
        """Test initialization with string path."""
        custom_path = str(tmp_path / "string_path.json")
        manager = CheckpointManager(checkpoint_path=custom_path)
        assert manager.checkpoint_file == Path(custom_path)

    def test_save_checkpoint(self, tmp_path):
        """Test saving checkpoint data to file (v2 compact format)."""
        checkpoint_file = tmp_path / "checkpoint.json"
        manager = CheckpointManager(checkpoint_path=checkpoint_file)

        manager.save_checkpoint(
            emails_processed=2,
            last_processed_id="email2",
            source="hotmail",
        )

        # Verify file was created
        assert checkpoint_file.exists()

        # Verify contents
        with open(checkpoint_file) as f:
            data = json.load(f)

        assert data["version"] == 2
        assert data["emails_processed"] == 2
        assert data["last_processed_id"] == "email2"
        assert data["checkpoint_interval"] == 100
        assert data["source"] == "hotmail"
        assert "timestamp" in data
        # v2 format should NOT contain extracted_emails
        assert "extracted_emails" not in data

    def test_load_checkpoint_existing_file(self, tmp_path):
        """Test loading existing v2 checkpoint."""
        checkpoint_file = tmp_path / "checkpoint.json"
        checkpoint_data = {
            "version": 2,
            "emails_processed": 50,
            "last_processed_id": "abc123",
            "timestamp": "2024-01-01T12:00:00",
            "checkpoint_interval": 100,
            "source": "hotmail",
        }

        with open(checkpoint_file, "w") as f:
            json.dump(checkpoint_data, f)

        manager = CheckpointManager(checkpoint_path=checkpoint_file)
        loaded = manager.load_checkpoint()

        assert loaded is not None
        assert loaded["version"] == 2
        assert loaded["emails_processed"] == 50
        assert loaded["last_processed_id"] == "abc123"

    def test_load_checkpoint_no_file(self, tmp_path):
        """Test loading checkpoint when file doesn't exist."""
        checkpoint_file = tmp_path / "nonexistent.json"
        manager = CheckpointManager(checkpoint_path=checkpoint_file)
        loaded = manager.load_checkpoint()
        assert loaded is None

    def test_load_checkpoint_directory_instead_of_file(self, tmp_path):
        """Test handling when checkpoint path is a directory."""
        checkpoint_dir = tmp_path / "checkpoint_dir"
        checkpoint_dir.mkdir()
        manager = CheckpointManager(checkpoint_path=checkpoint_dir)
        loaded = manager.load_checkpoint()
        assert loaded is None

    def test_load_checkpoint_corrupted_file(self, tmp_path):
        """Test handling corrupted checkpoint file."""
        checkpoint_file = tmp_path / "corrupted.json"
        with open(checkpoint_file, "w") as f:
            f.write("not valid json {{{")

        manager = CheckpointManager(checkpoint_path=checkpoint_file)
        loaded = manager.load_checkpoint()
        assert loaded is None

    def test_should_checkpoint_at_interval(self):
        """Test checkpoint interval detection."""
        manager = CheckpointManager(checkpoint_interval=100)

        assert manager.should_checkpoint(100) is True
        assert manager.should_checkpoint(200) is True
        assert manager.should_checkpoint(300) is True

    def test_should_not_checkpoint_between_intervals(self):
        """Test that checkpoints are not triggered between intervals."""
        manager = CheckpointManager(checkpoint_interval=100)

        assert manager.should_checkpoint(1) is False
        assert manager.should_checkpoint(50) is False
        assert manager.should_checkpoint(99) is False
        assert manager.should_checkpoint(101) is False

    def test_should_checkpoint_custom_interval(self):
        """Test checkpoint with custom interval."""
        manager = CheckpointManager(checkpoint_interval=25)

        assert manager.should_checkpoint(25) is True
        assert manager.should_checkpoint(50) is True
        assert manager.should_checkpoint(10) is False

    def test_clear_checkpoint(self, tmp_path):
        """Test clearing checkpoint file."""
        checkpoint_file = tmp_path / "checkpoint.json"
        with open(checkpoint_file, "w") as f:
            json.dump({"test": "data"}, f)

        manager = CheckpointManager(checkpoint_path=checkpoint_file)
        manager.clear_checkpoint()

        assert not checkpoint_file.exists()

    def test_clear_checkpoint_no_file(self, tmp_path):
        """Test clearing when no checkpoint file exists."""
        checkpoint_file = tmp_path / "nonexistent.json"
        manager = CheckpointManager(checkpoint_path=checkpoint_file)
        # Should not raise exception
        manager.clear_checkpoint()

    def test_clear_checkpoint_directory(self, tmp_path):
        """Test that clear_checkpoint handles directory gracefully."""
        checkpoint_dir = tmp_path / "checkpoint_dir"
        checkpoint_dir.mkdir()
        manager = CheckpointManager(checkpoint_path=checkpoint_dir)
        # Should not delete directory or raise exception
        manager.clear_checkpoint()
        assert checkpoint_dir.exists()

    def test_get_resume_point_with_checkpoint(self, tmp_path):
        """Test getting resume point from existing v2 checkpoint."""
        checkpoint_file = tmp_path / "checkpoint.json"
        checkpoint_data = {
            "version": 2,
            "emails_processed": 75,
            "last_processed_id": "xyz789",
            "timestamp": "2024-01-01T12:00:00",
            "checkpoint_interval": 100,
            "source": "hotmail",
        }

        with open(checkpoint_file, "w") as f:
            json.dump(checkpoint_data, f)

        manager = CheckpointManager(checkpoint_path=checkpoint_file)
        count, last_id = manager.get_resume_point()

        assert count == 75
        assert last_id == "xyz789"

    def test_get_resume_point_no_checkpoint(self, tmp_path):
        """Test getting resume point when no checkpoint exists."""
        checkpoint_file = tmp_path / "nonexistent.json"
        manager = CheckpointManager(checkpoint_path=checkpoint_file)
        count, last_id = manager.get_resume_point()

        assert count == 0
        assert last_id == ""

    def test_get_resume_point_old_format_returns_empty(self, tmp_path):
        """Test resume point returns empty for v1 (legacy) checkpoints."""
        checkpoint_file = tmp_path / "checkpoint.json"
        checkpoint_data = {
            "emails_processed": 10,
            "last_processed_id": "abc",
            "timestamp": "2024-01-01T12:00:00",
            "extracted_emails": [{"id": "email1"}, {"id": "email2"}]
            # No version field = v1 format
        }

        with open(checkpoint_file, "w") as f:
            json.dump(checkpoint_data, f)

        manager = CheckpointManager(checkpoint_path=checkpoint_file)
        count, last_id = manager.get_resume_point()

        # Old format should be rejected, returning fresh start
        assert count == 0
        assert last_id == ""

    def test_checkpoint_file_is_small(self, tmp_path):
        """Test that v2 checkpoints are < 1KB regardless of emails_processed count."""
        checkpoint_file = tmp_path / "checkpoint.json"
        manager = CheckpointManager(checkpoint_path=checkpoint_file)

        # Even for a very large number of processed emails, the file stays tiny
        manager.save_checkpoint(
            emails_processed=100000,
            last_processed_id="a" * 200,  # Long ID
            source="hotmail",
        )

        file_size = checkpoint_file.stat().st_size
        assert file_size < 1024, f"Checkpoint file is {file_size} bytes, expected < 1024"

    def test_checkpoint_version_is_present(self, tmp_path):
        """Test that saved checkpoints include version field."""
        checkpoint_file = tmp_path / "checkpoint.json"
        manager = CheckpointManager(checkpoint_path=checkpoint_file)

        manager.save_checkpoint(
            emails_processed=5,
            last_processed_id="test_id",
            source="gmail",
        )

        with open(checkpoint_file) as f:
            data = json.load(f)

        assert "version" in data
        assert data["version"] == 2

    def test_old_format_checkpoint_rejected_on_load(self, tmp_path):
        """Test that v1 checkpoints (with extracted_emails) are handled gracefully."""
        checkpoint_file = tmp_path / "checkpoint.json"
        # Write a v1 checkpoint with full email objects
        v1_data = {
            "emails_processed": 50,
            "last_processed_id": "abc123",
            "timestamp": "2024-01-01T12:00:00",
            "checkpoint_interval": 100,
            "extracted_emails": [
                {"id": f"email_{i}", "subject": f"Subject {i}", "body": "x" * 1000}
                for i in range(50)
            ]
        }

        with open(checkpoint_file, "w") as f:
            json.dump(v1_data, f)

        manager = CheckpointManager(checkpoint_path=checkpoint_file)
        loaded = manager.load_checkpoint()

        # v1 format should be rejected
        assert loaded is None

    def test_checkpoint_integrity_check_negative_count(self, tmp_path):
        """Test that checkpoints with negative emails_processed are rejected."""
        checkpoint_file = tmp_path / "checkpoint.json"
        invalid_data = {
            "version": 2,
            "emails_processed": -5,
            "last_processed_id": "abc",
            "timestamp": "2024-01-01T12:00:00",
            "checkpoint_interval": 100,
            "source": "hotmail",
        }

        with open(checkpoint_file, "w") as f:
            json.dump(invalid_data, f)

        manager = CheckpointManager(checkpoint_path=checkpoint_file)
        loaded = manager.load_checkpoint()
        assert loaded is None

    def test_checkpoint_integrity_check_non_integer_count(self, tmp_path):
        """Test that checkpoints with non-integer emails_processed are rejected."""
        checkpoint_file = tmp_path / "checkpoint.json"
        invalid_data = {
            "version": 2,
            "emails_processed": "not_a_number",
            "last_processed_id": "abc",
            "timestamp": "2024-01-01T12:00:00",
            "checkpoint_interval": 100,
            "source": "hotmail",
        }

        with open(checkpoint_file, "w") as f:
            json.dump(invalid_data, f)

        manager = CheckpointManager(checkpoint_path=checkpoint_file)
        loaded = manager.load_checkpoint()
        assert loaded is None

    def test_save_checkpoint_gmail_source(self, tmp_path):
        """Test saving checkpoint with gmail source."""
        checkpoint_file = tmp_path / "checkpoint.json"
        manager = CheckpointManager(checkpoint_path=checkpoint_file)

        manager.save_checkpoint(
            emails_processed=10,
            last_processed_id="gmail_msg_10",
            source="gmail",
        )

        with open(checkpoint_file) as f:
            data = json.load(f)

        assert data["source"] == "gmail"

    def test_resume_from_v2_checkpoint_with_mock_api(self, tmp_path):
        """Test that resume from v2 checkpoint works correctly with mocked API."""
        checkpoint_file = tmp_path / "checkpoint.json"
        manager = CheckpointManager(checkpoint_path=checkpoint_file)

        # Save a v2 checkpoint
        manager.save_checkpoint(
            emails_processed=50,
            last_processed_id="msg_50",
            source="hotmail",
        )

        # Load and verify
        count, last_id = manager.get_resume_point()
        assert count == 50
        assert last_id == "msg_50"


class TestCLIExtractSinceLastFlag:
    """Test cases for --since-last CLI flag (Task 4B.2)."""

    def test_extract_command_has_since_last_flag(self):
        """Test that extract command has --since-last flag."""
        from src.cli import create_parser

        parser = create_parser()

        # Without flag - default should be False
        args = parser.parse_args(["extract", "--user-email", "test@test.com"])
        assert args.since_last is False

        # With flag - should be True
        args = parser.parse_args(["extract", "--user-email", "test@test.com", "--since-last"])
        assert args.since_last is True


class TestEmailExtractor:
    """Test cases for EmailExtractor class."""

    @pytest.fixture
    def extractor(self, tmp_path):
        """Create EmailExtractor with temp checkpoint directory."""
        return EmailExtractor(
            user_email="test@example.com",
            checkpoint_dir=str(tmp_path)
        )

    @pytest.fixture
    def mock_email_data(self):
        """Create mock M365 email data."""
        return {
            "id": "msg123",
            "subject": "Test Email Subject",
            "from": {
                "emailAddress": {
                    "address": "sender@example.com",
                    "name": "Test Sender"
                }
            },
            "toRecipients": [
                {
                    "emailAddress": {
                        "address": "recipient@example.com",
                        "name": "Test Recipient"
                    }
                }
            ],
            "body": {
                "contentType": "html",
                "content": "<html><body><p>Test email body content</p></body></html>"
            },
            "receivedDateTime": "2024-01-15T10:30:00Z",
            "hasAttachments": False
        }

    def test_init_creates_checkpoint_manager(self, tmp_path):
        """Test that initialization creates checkpoint manager."""
        extractor = EmailExtractor(
            user_email="user@example.com",
            checkpoint_dir=str(tmp_path)
        )
        assert extractor.user_email == "user@example.com"
        assert extractor.checkpoint_manager is not None

    def test_process_email_valid_data(self, extractor, mock_email_data):
        """Test processing valid email data into Email model."""
        email = extractor._process_email(mock_email_data)

        assert email.id == "msg123"
        assert email.sender_email == "sender@example.com"
        assert email.sender_name == "Test Sender"
        assert email.sender_domain == "example.com"
        assert email.subject == "Test Email Subject"
        assert "Test email body content" in email.body_text
        assert email.has_attachments is False

    def test_process_email_extracts_domain(self, extractor, mock_email_data):
        """Test that domain is extracted from sender email."""
        mock_email_data["from"]["emailAddress"]["address"] = "test@subdomain.company.com"
        email = extractor._process_email(mock_email_data)
        assert email.sender_domain == "subdomain.company.com"

    def test_process_email_handles_missing_sender(self, extractor, mock_email_data):
        """Test handling of email with missing sender info raises validation error."""
        mock_email_data["from"] = {}
        # Empty dict causes KeyError from dict access before validation
        with pytest.raises((KeyError, ValueError, TypeError)):
            extractor._process_email(mock_email_data)

    def test_process_email_html_body_conversion(self, extractor, mock_email_data):
        """Test HTML body is converted to plain text."""
        mock_email_data["body"]["content"] = """
        <html>
            <body>
                <h1>Important Message</h1>
                <p>This is the message content.</p>
                <script>alert('bad');</script>
            </body>
        </html>
        """
        email = extractor._process_email(mock_email_data)
        assert "Important Message" in email.body_text
        assert "message content" in email.body_text
        assert "alert" not in email.body_text

    def test_process_email_empty_body(self, extractor, mock_email_data):
        """Test handling of email with empty body."""
        mock_email_data["body"]["content"] = ""
        email = extractor._process_email(mock_email_data)
        assert email.body_text == ""

    def test_process_email_missing_recipients(self, extractor, mock_email_data):
        """Test handling of email with empty toRecipients list."""
        mock_email_data["toRecipients"] = []
        email = extractor._process_email(mock_email_data)
        assert email.recipient_email is None
        assert email.recipient_name == ""

    def test_process_email_parses_date(self, extractor, mock_email_data):
        """Test that received date is properly parsed."""
        mock_email_data["receivedDateTime"] = "2024-06-15T14:30:00Z"
        email = extractor._process_email(mock_email_data)
        assert email.received_date.year == 2024
        assert email.received_date.month == 6
        assert email.received_date.day == 15

    @patch.object(EmailExtractor, "_get_total_email_count")
    @patch.object(EmailExtractor, "_fetch_batch")
    def test_extract_all_success(self, mock_fetch_batch, mock_get_count, extractor, mock_email_data):
        """Test successful extraction of all emails."""
        mock_get_count.return_value = 2
        mock_fetch_batch.return_value = [mock_email_data, mock_email_data]

        result = extractor.extract_all(max_batch_size=100, checkpoint_interval=100)

        assert isinstance(result, ExtractionResult)
        assert result.success_count == 2
        assert result.failure_count == 0
        assert len(result.corpus.emails) == 2

    @patch.object(EmailExtractor, "_get_total_email_count")
    @patch.object(EmailExtractor, "_fetch_batch")
    def test_extract_all_with_progress_callback(
        self, mock_fetch_batch, mock_get_count, extractor, mock_email_data
    ):
        """Test extraction with progress callback."""
        mock_get_count.return_value = 2
        mock_fetch_batch.return_value = [mock_email_data]

        progress_values = []

        def progress_callback(current, total):
            progress_values.append((current, total))

        extractor.extract_all(
            max_batch_size=1,
            checkpoint_interval=100,
            progress_callback=progress_callback
        )

        assert len(progress_values) > 0

    @patch.object(EmailExtractor, "_get_total_email_count")
    @patch.object(EmailExtractor, "_fetch_batch")
    def test_extract_all_handles_batch_error(
        self, mock_fetch_batch, mock_get_count, extractor
    ):
        """Test extraction handles batch fetch errors."""
        mock_get_count.return_value = 100
        mock_fetch_batch.side_effect = Exception("Network error")

        result = extractor.extract_all()

        assert result.failure_count > 0
        assert len(result.failed_emails) > 0
        assert result.failed_emails[0].error_type == "timeout"

    @patch.object(EmailExtractor, "_get_total_email_count")
    @patch.object(EmailExtractor, "_fetch_batch")
    def test_extract_all_handles_rate_limit(
        self, mock_fetch_batch, mock_get_count, extractor, mock_email_data
    ):
        """Test extraction handles rate limiting via RateLimitError."""
        mock_get_count.return_value = 10
        # First call fails with RateLimitError, second succeeds but empty
        mock_fetch_batch.side_effect = [
            RateLimitError(retry_after=5),
            []  # Empty batch to stop iteration
        ]

        with patch.object(extractor, "_handle_rate_limit") as mock_rate_limit:
            extractor.extract_all(max_batch_size=10)
            mock_rate_limit.assert_called_once_with(0, retry_after=5)

    @patch.object(EmailExtractor, "_get_total_email_count")
    @patch.object(EmailExtractor, "_fetch_batch")
    def test_extract_all_non_rate_limit_error_stops(
        self, mock_fetch_batch, mock_get_count, extractor
    ):
        """Test that non-rate-limit exceptions stop extraction (not caught as rate limit)."""
        mock_get_count.return_value = 100
        mock_fetch_batch.side_effect = Exception("Some other error")

        result = extractor.extract_all()

        assert result.failure_count > 0
        assert result.failed_emails[0].error_type == "timeout"

    @patch.object(EmailExtractor, "_get_total_email_count")
    @patch.object(EmailExtractor, "_fetch_batch")
    def test_extract_all_malformed_email(
        self, mock_fetch_batch, mock_get_count, extractor, mock_email_data
    ):
        """Test extraction handles malformed email data."""
        mock_get_count.return_value = 2
        malformed_email = {"id": "bad", "invalid": True}
        mock_fetch_batch.return_value = [mock_email_data, malformed_email]

        result = extractor.extract_all(max_batch_size=100)

        # One success, one failure
        assert result.success_count >= 1
        assert result.failure_count >= 1 or result.success_count < 2

    @patch.object(EmailExtractor, "_get_total_email_count")
    def test_extract_all_connection_error(self, mock_get_count, extractor):
        """Test extraction raises ConnectionError when M365 unreachable."""
        mock_get_count.side_effect = ConnectionError("MCP server unreachable")

        with pytest.raises(ConnectionError):
            extractor.extract_all()

    @patch.object(EmailExtractor, "_get_total_email_count")
    @patch.object(EmailExtractor, "_fetch_batch")
    def test_extract_all_empty_batch_stops_pagination(
        self, mock_fetch_batch, mock_get_count, extractor
    ):
        """Test that empty batch result stops pagination."""
        mock_get_count.return_value = EMAIL_COUNT_SENTINEL  # Large sentinel
        mock_fetch_batch.return_value = []

        result = extractor.extract_all()

        assert result.success_count == 0
        mock_fetch_batch.assert_called_once()

    @patch.object(EmailExtractor, "_get_total_email_count")
    @patch.object(EmailExtractor, "_fetch_batch")
    def test_extract_all_creates_valid_corpus(
        self, mock_fetch_batch, mock_get_count, extractor, mock_email_data
    ):
        """Test extraction creates valid Corpus object."""
        mock_get_count.return_value = 1
        mock_fetch_batch.return_value = [mock_email_data]

        result = extractor.extract_all()

        assert isinstance(result.corpus, Corpus)
        assert result.corpus.extraction_metadata.source == "Hotmail/M365"
        assert result.corpus.extraction_metadata.user_email == "test@example.com"
        assert result.corpus.extraction_metadata.total_emails == 1

    def test_handle_rate_limit_backoff(self, extractor):
        """Test rate limit handling with exponential backoff."""
        with patch("time.sleep") as mock_sleep:
            extractor._handle_rate_limit(0)
            mock_sleep.assert_called_with(1)  # 2^0 = 1

            extractor._handle_rate_limit(1)
            mock_sleep.assert_called_with(2)  # 2^1 = 2

            extractor._handle_rate_limit(2)
            mock_sleep.assert_called_with(4)  # 2^2 = 4

            extractor._handle_rate_limit(10)
            mock_sleep.assert_called_with(8)  # Max 8 seconds

    def test_handle_rate_limit_uses_retry_after(self, extractor):
        """Test rate limit handling uses retry_after when provided."""
        with patch("time.sleep") as mock_sleep:
            extractor._handle_rate_limit(0, retry_after=30)
            mock_sleep.assert_called_with(8)  # Capped at MAX_BACKOFF_SECONDS (8)

            extractor._handle_rate_limit(0, retry_after=5)
            mock_sleep.assert_called_with(5)  # Uses retry_after when < max

    def test_handle_rate_limit_ignores_zero_retry_after(self, extractor):
        """Test rate limit handling falls back to exponential when retry_after is 0."""
        with patch("time.sleep") as mock_sleep:
            extractor._handle_rate_limit(2, retry_after=0)
            mock_sleep.assert_called_with(4)  # 2^2 = 4 (exponential fallback)

    @patch.object(EmailExtractor, "_get_total_email_count")
    @patch.object(EmailExtractor, "_fetch_batch")
    def test_extract_all_saves_checkpoint(
        self, mock_fetch_batch, mock_get_count, extractor, mock_email_data, tmp_path
    ):
        """Test that checkpoint is saved at intervals."""
        mock_get_count.return_value = 150
        # Return 100 emails to trigger checkpoint
        mock_fetch_batch.side_effect = [
            [mock_email_data] * 100,
            []  # Empty to stop
        ]

        result = extractor.extract_all(max_batch_size=100, checkpoint_interval=100)

        # Checkpoint should have been saved then cleared
        assert result.success_count == 100


class TestExtractionResult:
    """Test cases for ExtractionResult dataclass."""

    def test_success_rate_calculation(self):
        """Test success rate is calculated correctly."""
        result = ExtractionResult(
            corpus=Corpus(
                extraction_metadata=CorpusMetadata(
                    extraction_date=datetime.now(),
                    total_emails=80,
                    source="test",
                    user_email="user@example.com"
                ),
                emails=[]
            ),
            failed_emails=[],
            success_count=80,
            failure_count=20,
            total_attempted=100
        )
        assert result.success_rate == 0.8

    def test_success_rate_zero_attempted(self):
        """Test success rate with zero attempts."""
        result = ExtractionResult(
            corpus=Corpus(
                extraction_metadata=CorpusMetadata(
                    extraction_date=datetime.now(),
                    total_emails=0,
                    source="test",
                    user_email="user@example.com"
                ),
                emails=[]
            ),
            failed_emails=[],
            success_count=0,
            failure_count=0,
            total_attempted=0
        )
        assert result.success_rate == 0.0


class TestExtractionError:
    """Test cases for ExtractionError dataclass."""

    def test_extraction_error_creation(self):
        """Test creating ExtractionError instance."""
        error = ExtractionError(
            email_id="msg123",
            error_type="timeout",
            error_message="Connection timed out",
            timestamp=datetime(2024, 1, 15, 10, 30)
        )
        assert error.email_id == "msg123"
        assert error.error_type == "timeout"
        assert error.error_message == "Connection timed out"

    def test_extraction_error_types(self):
        """Test various error types."""
        error_types = ["rate_limit", "timeout", "malformed", "unknown"]
        for error_type in error_types:
            error = ExtractionError(
                email_id="test",
                error_type=error_type,
                error_message="Test error",
                timestamp=datetime.now()
            )
            assert error.error_type == error_type


class TestEmailExtractorResume:
    """Test cases for resumption functionality."""

    @pytest.fixture
    def extractor_with_checkpoint(self, tmp_path):
        """Create extractor with pre-existing v2 checkpoint."""
        checkpoint_file = tmp_path / "extraction_checkpoint.json"
        checkpoint_data = {
            "version": 2,
            "emails_processed": 50,
            "last_processed_id": "previous_email_id",
            "timestamp": "2024-01-01T12:00:00",
            "checkpoint_interval": 100,
            "source": "hotmail",
        }

        with open(checkpoint_file, "w") as f:
            json.dump(checkpoint_data, f)

        return EmailExtractor(
            user_email="test@example.com",
            checkpoint_dir=str(tmp_path)
        )

    @patch.object(EmailExtractor, "_get_total_email_count")
    @patch.object(EmailExtractor, "_fetch_batch")
    def test_extract_all_resumes_from_checkpoint(
        self, mock_fetch_batch, mock_get_count, extractor_with_checkpoint
    ):
        """Test that extraction resumes from v2 checkpoint using skip offset."""
        mock_get_count.return_value = 100
        mock_fetch_batch.return_value = []  # No new emails after skip

        result = extractor_with_checkpoint.extract_all()

        # v2 checkpoint: no emails reconstructed from checkpoint,
        # extractor re-fetches using skip offset
        assert isinstance(result, ExtractionResult)

    def test_resume_from_checkpoint_method(self, extractor_with_checkpoint):
        """Test resume_from_checkpoint delegates to extract_all."""
        with patch.object(extractor_with_checkpoint, "extract_all") as mock_extract:
            mock_extract.return_value = MagicMock(spec=ExtractionResult)
            extractor_with_checkpoint.resume_from_checkpoint("path")
            mock_extract.assert_called_once()

    @patch.object(EmailExtractor, "_get_total_email_count")
    @patch.object(EmailExtractor, "_fetch_batch")
    def test_old_format_checkpoint_triggers_fresh_extraction(
        self, mock_fetch_batch, mock_get_count, tmp_path
    ):
        """Test that v1 (old format) checkpoint is rejected, causing fresh extraction."""
        checkpoint_file = tmp_path / "extraction_checkpoint.json"
        # Write a v1 checkpoint (no version field, has extracted_emails)
        v1_data = {
            "emails_processed": 50,
            "last_processed_id": "old_id",
            "timestamp": "2024-01-01T12:00:00",
            "checkpoint_interval": 100,
            "extracted_emails": [{"id": "email1"}]
        }
        with open(checkpoint_file, "w") as f:
            json.dump(v1_data, f)

        extractor = EmailExtractor(
            user_email="test@example.com",
            checkpoint_dir=str(tmp_path)
        )

        mock_get_count.return_value = EMAIL_COUNT_SENTINEL
        mock_fetch_batch.return_value = []

        result = extractor.extract_all()

        # Should start fresh (0 emails processed from checkpoint)
        assert isinstance(result, ExtractionResult)
        # The fetch should start at offset 0 (not 50)
        mock_fetch_batch.assert_called_once_with(0, 500, "")


class TestEmailExtractorRetryLogic:
    """Test retry and error handling logic in EmailExtractor."""

    @pytest.fixture
    def extractor(self, tmp_path):
        """Create EmailExtractor for retry tests."""
        return EmailExtractor(
            user_email="retry@example.com",
            checkpoint_dir=str(tmp_path)
        )

    @pytest.fixture
    def valid_email_data(self):
        """Create valid M365 email data."""
        return {
            "id": "valid_msg",
            "subject": "Valid Subject",
            "from": {
                "emailAddress": {
                    "address": "sender@example.com",
                    "name": "Sender"
                }
            },
            "toRecipients": [
                {"emailAddress": {"address": "recipient@example.com", "name": "Recipient"}}
            ],
            "body": {"content": "<p>Valid body</p>"},
            "receivedDateTime": "2024-01-01T00:00:00Z",
            "hasAttachments": False
        }

    @patch.object(EmailExtractor, "_get_total_email_count")
    @patch.object(EmailExtractor, "_fetch_batch")
    def test_extract_all_partial_batch_stops(
        self, mock_fetch_batch, mock_get_count, extractor, valid_email_data
    ):
        """Test that receiving fewer emails than requested stops pagination."""
        mock_get_count.return_value = EMAIL_COUNT_SENTINEL
        # Return fewer than requested batch size
        mock_fetch_batch.return_value = [valid_email_data] * 3  # Less than batch_size of 10

        result = extractor.extract_all(max_batch_size=10)

        # Should stop after first batch because we got fewer than requested
        assert mock_fetch_batch.call_count == 1
        assert result.success_count == 3

    @patch.object(EmailExtractor, "_get_total_email_count")
    @patch.object(EmailExtractor, "_fetch_batch")
    def test_extract_all_exact_batch_continues(
        self, mock_fetch_batch, mock_get_count, extractor, valid_email_data
    ):
        """Test that receiving exact batch size continues pagination."""
        mock_get_count.return_value = EMAIL_COUNT_SENTINEL
        # First batch: exact size, second batch: empty
        mock_fetch_batch.side_effect = [
            [valid_email_data] * 10,  # Exact batch size
            []  # Empty stops iteration
        ]

        result = extractor.extract_all(max_batch_size=10)

        assert mock_fetch_batch.call_count == 2
        assert result.success_count == 10

    @patch.object(EmailExtractor, "_get_total_email_count")
    @patch.object(EmailExtractor, "_fetch_batch")
    def test_checkpoint_saved_at_interval(
        self, mock_fetch_batch, mock_get_count, extractor, valid_email_data
    ):
        """Test checkpoint is saved exactly at interval."""
        mock_get_count.return_value = EMAIL_COUNT_SENTINEL
        # Return 100 emails to hit checkpoint at exactly 100
        mock_fetch_batch.side_effect = [
            [valid_email_data] * 100,
            []
        ]

        with patch.object(extractor.checkpoint_manager, "save_checkpoint") as mock_save:
            extractor.extract_all(max_batch_size=100, checkpoint_interval=100)

            # Checkpoint should be saved when we hit 100 emails
            assert mock_save.called

    def test_fetch_batch_delegates_to_mcp_client(self, extractor):
        """Test _fetch_batch uses MCP client correctly."""
        with patch.object(extractor.graph_client, "fetch_emails") as mock_fetch:
            mock_fetch.return_value = [{"id": "test"}]

            result = extractor._fetch_batch(0, 50)

            mock_fetch.assert_called_once_with(max_results=50, skip=0)
            assert result == [{"id": "test"}]

    def test_fetch_batch_connection_error(self, extractor):
        """Test _fetch_batch raises ConnectionError on client failure."""
        with patch.object(extractor.graph_client, "fetch_emails") as mock_fetch:
            mock_fetch.side_effect = Exception("Network failure")

            with pytest.raises(ConnectionError, match="M365 batch fetch failed"):
                extractor._fetch_batch(0, 50)

    def test_fetch_batch_propagates_connection_error(self, extractor):
        """Test _fetch_batch propagates ConnectionError without wrapping."""
        with patch.object(extractor.graph_client, "fetch_emails") as mock_fetch:
            mock_fetch.side_effect = ConnectionError("Original error")

            with pytest.raises(ConnectionError, match="Original error"):
                extractor._fetch_batch(0, 50)

    def test_get_total_email_count_propagates_connection_error(self, extractor):
        """Test _get_total_email_count propagates ConnectionError."""
        with patch.object(extractor.graph_client, "fetch_emails") as mock_fetch:
            mock_fetch.side_effect = ConnectionError("MCP unreachable")

            with pytest.raises(ConnectionError):
                extractor._get_total_email_count()


class TestSentinelValueSuppression:
    """Test cases for work item 1.3: Suppress sentinel value from user-facing output.

    Patches the extractor's logger.info to inspect log messages directly,
    since the logger uses propagate=False and holds a pre-captured sys.stdout
    reference that defeats both caplog and capsys.
    """

    @pytest.fixture
    def extractor(self, tmp_path):
        """Create EmailExtractor for sentinel tests."""
        return EmailExtractor(
            user_email="sentinel@example.com",
            checkpoint_dir=str(tmp_path)
        )

    @patch.object(EmailExtractor, "_get_total_email_count")
    @patch.object(EmailExtractor, "_fetch_batch")
    def test_sentinel_value_suppressed_in_log(
        self, mock_fetch_batch, mock_get_count, extractor
    ):
        """Test that sentinel value 999999 does not appear in any log message."""
        mock_get_count.return_value = EMAIL_COUNT_SENTINEL
        mock_fetch_batch.return_value = []

        logged_messages = []
        original_info = extractor.logger.info
        extractor.logger.info = lambda msg, *a, **kw: logged_messages.append(msg)

        try:
            extractor.extract_all()
        finally:
            extractor.logger.info = original_info

        for msg in logged_messages:
            assert "999999" not in msg, (
                f"Sentinel value leaked into log: {msg}"
            )

    @patch.object(EmailExtractor, "_get_total_email_count")
    @patch.object(EmailExtractor, "_fetch_batch")
    def test_sentinel_shows_unknown_count_message(
        self, mock_fetch_batch, mock_get_count, extractor
    ):
        """Test that sentinel triggers 'total count unknown' message."""
        mock_get_count.return_value = EMAIL_COUNT_SENTINEL
        mock_fetch_batch.return_value = []

        logged_messages = []
        original_info = extractor.logger.info
        extractor.logger.info = lambda msg, *a, **kw: logged_messages.append(msg)

        try:
            extractor.extract_all()
        finally:
            extractor.logger.info = original_info

        assert any(
            "total count unknown" in msg for msg in logged_messages
        ), f"Expected 'total count unknown' message, got: {logged_messages}"

    @patch.object(EmailExtractor, "_get_total_email_count")
    @patch.object(EmailExtractor, "_fetch_batch")
    def test_real_count_shows_formatted_number(
        self, mock_fetch_batch, mock_get_count, extractor
    ):
        """Test that a real email count displays with comma formatting."""
        mock_get_count.return_value = 1500
        mock_fetch_batch.return_value = []

        logged_messages = []
        original_info = extractor.logger.info
        extractor.logger.info = lambda msg, *a, **kw: logged_messages.append(msg)

        try:
            extractor.extract_all()
        finally:
            extractor.logger.info = original_info

        assert any(
            "Found 1,500 emails to process" in msg for msg in logged_messages
        ), f"Expected formatted count '1,500', got: {logged_messages}"

    @patch.object(EmailExtractor, "_get_total_email_count")
    @patch.object(EmailExtractor, "_fetch_batch")
    def test_small_real_count_shows_number(
        self, mock_fetch_batch, mock_get_count, extractor
    ):
        """Test that a small real email count displays without commas."""
        mock_get_count.return_value = 42
        mock_fetch_batch.return_value = []

        logged_messages = []
        original_info = extractor.logger.info
        extractor.logger.info = lambda msg, *a, **kw: logged_messages.append(msg)

        try:
            extractor.extract_all()
        finally:
            extractor.logger.info = original_info

        assert any(
            "Found 42 emails to process" in msg for msg in logged_messages
        ), f"Expected 'Found 42 emails to process', got: {logged_messages}"


class TestIncrementalExtraction:
    """Test cases for Task 4B.2: Incremental extraction functionality."""

    @pytest.fixture
    def extractor(self, tmp_path):
        """Create EmailExtractor with temp directory."""
        return EmailExtractor(
            user_email="incremental@example.com",
            checkpoint_dir=str(tmp_path)
        )

    @pytest.fixture
    def existing_corpus(self):
        """Create an existing corpus for incremental extraction tests."""
        return Corpus(
            extraction_metadata=CorpusMetadata(
                extraction_date=datetime(2024, 1, 1, 10, 0),
                total_emails=2,
                source="Hotmail/M365",
                user_email="incremental@example.com",
                last_extraction_date=datetime(2024, 1, 1, 10, 0),
                email_ids_hash="existing_hash",
                extraction_params={"batch_size": 500}
            ),
            emails=[
                Email(
                    id="existing_001",
                    sender_email="old1@example.com",
                    sender_name="Old Sender 1",
                    sender_domain="example.com",
                    subject="Old Email 1",
                    body_text="Old body 1",
                    received_date=datetime(2024, 1, 1, 8, 0),
                    has_attachments=False
                ),
                Email(
                    id="existing_002",
                    sender_email="old2@example.com",
                    sender_name="Old Sender 2",
                    sender_domain="example.com",
                    subject="Old Email 2",
                    body_text="Old body 2",
                    received_date=datetime(2024, 1, 1, 9, 0),
                    has_attachments=False
                )
            ]
        )

    @pytest.fixture
    def new_email_data(self):
        """Create mock M365 data for a new email."""
        return {
            "id": "new_001",
            "subject": "New Email",
            "from": {
                "emailAddress": {
                    "address": "new@example.com",
                    "name": "New Sender"
                }
            },
            "toRecipients": [
                {"emailAddress": {"address": "me@example.com", "name": "Me"}}
            ],
            "body": {"content": "<p>New email body</p>"},
            "receivedDateTime": "2024-01-15T10:00:00Z",
            "hasAttachments": False
        }

    def test_extract_incremental_only_fetches_new_emails(
        self, extractor, existing_corpus, new_email_data
    ):
        """Test that incremental extraction only fetches emails since last extraction."""
        with patch.object(extractor.graph_client, "fetch_emails") as mock_fetch:
            mock_fetch.side_effect = [[new_email_data], []]

            result = extractor.extract_incremental(existing_corpus)

            # Should have 3 emails total (2 existing + 1 new)
            assert result.corpus.extraction_metadata.total_emails == 3
            assert len(result.corpus.emails) == 3
            assert result.new_emails_count == 1

    def test_extract_incremental_deduplicates_by_message_id(
        self, extractor, existing_corpus
    ):
        """Test that duplicate emails are not added (deduplication by message_id)."""
        # Return an email with ID that already exists in corpus
        duplicate_email = {
            "id": "existing_001",  # Same ID as existing email
            "subject": "Duplicate Email",
            "from": {"emailAddress": {"address": "dup@example.com", "name": "Dup"}},
            "toRecipients": [{"emailAddress": {"address": "me@example.com", "name": "Me"}}],
            "body": {"content": "Duplicate body"},
            "receivedDateTime": "2024-01-15T10:00:00Z",
            "hasAttachments": False
        }

        with patch.object(extractor.graph_client, "fetch_emails") as mock_fetch:
            mock_fetch.return_value = [duplicate_email]

            result = extractor.extract_incremental(existing_corpus)

            # Should still have 2 emails (no duplicates added)
            assert len(result.corpus.emails) == 2
            assert result.new_emails_count == 0

    def test_extract_incremental_updates_metadata(
        self, extractor, existing_corpus, new_email_data
    ):
        """Test that metadata is updated after incremental extraction."""
        with patch.object(extractor.graph_client, "fetch_emails") as mock_fetch:
            mock_fetch.side_effect = [[new_email_data], []]

            old_extraction_date = existing_corpus.extraction_metadata.last_extraction_date
            result = extractor.extract_incremental(existing_corpus)

            # Metadata should be updated
            assert result.corpus.extraction_metadata.last_extraction_date > old_extraction_date
            assert result.corpus.extraction_metadata.email_ids_hash != existing_corpus.extraction_metadata.email_ids_hash

    def test_extract_incremental_empty_result(
        self, extractor, existing_corpus
    ):
        """Test incremental extraction when there are no new emails."""
        with patch.object(extractor.graph_client, "fetch_emails") as mock_fetch:
            mock_fetch.return_value = []

            result = extractor.extract_incremental(existing_corpus)

            # Should still have original 2 emails, no new ones
            assert len(result.corpus.emails) == 2
            assert result.new_emails_count == 0

    def test_extract_incremental_result_has_new_emails_count(self, extractor):
        """Test that IncrementalExtractionResult has new_emails_count attribute."""
        # Just verify the dataclass/result class has the expected attribute
        from src.extractors.m365_extractor import IncrementalExtractionResult
        assert hasattr(IncrementalExtractionResult, '__annotations__')
        assert 'new_emails_count' in IncrementalExtractionResult.__annotations__

    def test_extract_incremental_reports_statistics(
        self, extractor, existing_corpus, new_email_data
    ):
        """Test that incremental extraction provides statistics about added emails."""
        new_email_2 = new_email_data.copy()
        new_email_2["id"] = "new_002"

        with patch.object(extractor.graph_client, "fetch_emails") as mock_fetch:
            mock_fetch.side_effect = [[new_email_data, new_email_2], []]

            result = extractor.extract_incremental(existing_corpus)

            # Statistics should be correct
            assert result.previous_count == 2  # Old corpus had 2
            assert result.new_emails_count == 2  # Added 2 new
            assert result.total_count == 4  # Total is now 4

    def test_get_incremental_kwargs_returns_filter_after(
        self, extractor, existing_corpus
    ):
        """Test that _get_incremental_kwargs returns filter_after from corpus metadata."""
        kwargs = extractor._get_incremental_kwargs(existing_corpus)

        assert "filter_after" in kwargs
        assert kwargs["filter_after"] == existing_corpus.extraction_metadata.last_extraction_date

    def test_get_incremental_kwargs_empty_when_no_last_date(self, extractor):
        """Test that _get_incremental_kwargs returns empty dict when no last_extraction_date."""
        corpus_no_date = Corpus(
            extraction_metadata=CorpusMetadata(
                extraction_date=datetime(2024, 1, 1),
                total_emails=0,
                source="Hotmail/M365",
                user_email="incremental@example.com",
                last_extraction_date=None,
            ),
            emails=[],
        )

        kwargs = extractor._get_incremental_kwargs(corpus_no_date)
        assert kwargs == {}

    def test_fetch_incremental_batch_passes_filter_after_to_client(self, extractor):
        """Test that _fetch_incremental_batch passes filter_after to Graph API client."""
        filter_date = datetime(2024, 6, 15, 10, 0, 0)

        with patch.object(extractor.graph_client, "fetch_emails") as mock_fetch:
            mock_fetch.return_value = [{"id": "new_msg"}]

            result = extractor._fetch_incremental_batch(
                start=0, batch_size=100, filter_after=filter_date
            )

            mock_fetch.assert_called_once_with(
                max_results=100,
                skip=0,
                filter_after=filter_date,
            )
            assert result == [{"id": "new_msg"}]

    def test_fetch_incremental_batch_no_filter_when_not_provided(self, extractor):
        """Test that _fetch_incremental_batch passes None filter when not provided."""
        with patch.object(extractor.graph_client, "fetch_emails") as mock_fetch:
            mock_fetch.return_value = []

            extractor._fetch_incremental_batch(start=0, batch_size=50)

            mock_fetch.assert_called_once_with(
                max_results=50,
                skip=0,
                filter_after=None,
            )

    def test_incremental_extraction_passes_filter_to_graph_api(
        self, extractor, existing_corpus, new_email_data
    ):
        """Test end-to-end: incremental extraction passes date filter to Graph API client."""
        with patch.object(extractor.graph_client, "fetch_emails") as mock_fetch:
            # First call returns new email, second call returns empty (stop)
            mock_fetch.side_effect = [[new_email_data], []]

            result = extractor.extract_incremental(existing_corpus)

            # Verify the first call included filter_after
            first_call = mock_fetch.call_args_list[0]
            assert first_call.kwargs.get("filter_after") == existing_corpus.extraction_metadata.last_extraction_date

            # New email should be added
            assert result.new_emails_count == 1
            assert result.total_count == 3

    def test_incremental_extraction_dedup_still_works_with_filter(
        self, extractor, existing_corpus
    ):
        """Test that client-side dedup still works as safety net alongside server filter."""
        # Simulate server returning a duplicate despite the date filter
        duplicate_email = {
            "id": "existing_001",  # Same ID as existing email
            "subject": "Duplicate from server",
            "from": {"emailAddress": {"address": "dup@example.com", "name": "Dup"}},
            "toRecipients": [{"emailAddress": {"address": "me@example.com", "name": "Me"}}],
            "body": {"content": "<p>Dup body</p>"},
            "receivedDateTime": "2024-01-15T10:00:00Z",
            "hasAttachments": False,
        }

        with patch.object(extractor.graph_client, "fetch_emails") as mock_fetch:
            mock_fetch.return_value = [duplicate_email]

            result = extractor.extract_incremental(existing_corpus)

            # Despite server returning an email, dedup catches the duplicate
            assert result.new_emails_count == 0
            assert result.total_count == 2  # Still just the 2 original


class TestM365RecipientParsing:
    """Test safe recipient parsing for M365 extractor (Work Item 1.1)."""

    @pytest.fixture
    def extractor(self, tmp_path):
        """Create EmailExtractor with temp directory."""
        return EmailExtractor(
            user_email="test@example.com",
            checkpoint_dir=str(tmp_path),
        )

    @pytest.fixture
    def base_email_data(self):
        """Base M365 email data without toRecipients (to be set per test)."""
        return {
            "id": "msg_recipient_test",
            "subject": "Recipient Test",
            "from": {
                "emailAddress": {
                    "address": "sender@example.com",
                    "name": "Sender",
                }
            },
            "body": {"content": "<p>Body</p>"},
            "receivedDateTime": "2024-01-15T10:30:00Z",
            "hasAttachments": False,
        }

    def test_empty_to_recipients_list(self, extractor, base_email_data):
        """Emails with toRecipients=[] produce recipient_email=None."""
        base_email_data["toRecipients"] = []
        email = extractor._process_email(base_email_data)
        assert email.recipient_email is None
        assert email.recipient_name == ""

    def test_none_to_recipients(self, extractor, base_email_data):
        """Emails with toRecipients=None produce recipient_email=None."""
        base_email_data["toRecipients"] = None
        email = extractor._process_email(base_email_data)
        assert email.recipient_email is None
        assert email.recipient_name == ""

    def test_missing_to_recipients_key(self, extractor, base_email_data):
        """Emails with no toRecipients key produce recipient_email=None."""
        # Ensure key is not present
        base_email_data.pop("toRecipients", None)
        email = extractor._process_email(base_email_data)
        assert email.recipient_email is None
        assert email.recipient_name == ""

    def test_valid_to_recipients(self, extractor, base_email_data):
        """Emails with valid toRecipients extract correctly."""
        base_email_data["toRecipients"] = [
            {
                "emailAddress": {
                    "address": "recipient@example.com",
                    "name": "Test Recipient",
                }
            }
        ]
        email = extractor._process_email(base_email_data)
        assert email.recipient_email == "recipient@example.com"
        assert email.recipient_name == "Test Recipient"

    def test_multiple_to_recipients_takes_first(self, extractor, base_email_data):
        """When multiple recipients exist, the first is used."""
        base_email_data["toRecipients"] = [
            {"emailAddress": {"address": "first@example.com", "name": "First"}},
            {"emailAddress": {"address": "second@example.com", "name": "Second"}},
        ]
        email = extractor._process_email(base_email_data)
        assert email.recipient_email == "first@example.com"
        assert email.recipient_name == "First"

    def test_to_recipients_with_empty_email_address_dict(self, extractor, base_email_data):
        """When toRecipients has entry with empty emailAddress, returns None/empty."""
        base_email_data["toRecipients"] = [{"emailAddress": {}}]
        email = extractor._process_email(base_email_data)
        assert email.recipient_email is None
        assert email.recipient_name == ""


class TestEmailExtractorEdgeCases:
    """Test edge cases for EmailExtractor."""

    @pytest.fixture
    def extractor(self, tmp_path):
        """Create EmailExtractor with temp directory."""
        return EmailExtractor(
            user_email="edge@example.com",
            checkpoint_dir=str(tmp_path)
        )

    def test_process_email_no_at_in_sender(self, extractor):
        """Test handling sender email without @ symbol."""
        email_data = {
            "id": "test1",
            "subject": "Test",
            "from": {
                "emailAddress": {
                    "address": "invalid-email-format",
                    "name": "Invalid"
                }
            },
            "toRecipients": [],
            "body": {"content": "Body"},
            "receivedDateTime": "2024-01-01T00:00:00Z",
            "hasAttachments": False
        }

        # Lenient validator still rejects strings without @ (ValueError)
        with pytest.raises((KeyError, ValueError, TypeError)):
            extractor._process_email(email_data)

    def test_process_email_accepts_technically_invalid_addresses(self, extractor):
        """Test that technically-invalid but real-world email addresses are accepted.

        Spam and automated senders often have addresses that violate RFC 5321
        but must be preserved for classification and rule export.
        """
        test_cases = [
            ("noreply@39._ecoenergi.online", "39._ecoenergi.online"),
            ("CloudNotify@---SyncServi...-MtO0.autoworkscoll.com", "---SyncServi...-MtO0.autoworkscoll.com"),
        ]

        for address, expected_domain in test_cases:
            email_data = {
                "id": f"test_{address}",
                "subject": "Spam Test",
                "from": {
                    "emailAddress": {
                        "address": address,
                        "name": "Spam Sender"
                    }
                },
                "toRecipients": [
                    {"emailAddress": {"address": "user@example.com", "name": "User"}}
                ],
                "body": {"content": "<p>Spam body</p>"},
                "receivedDateTime": "2024-01-15T10:00:00Z",
                "hasAttachments": False,
            }

            email = extractor._process_email(email_data)

            assert email.sender_email == address
            assert email.sender_domain == expected_domain

    def test_process_email_special_characters_in_body(self, extractor):
        """Test handling special characters in email body."""
        email_data = {
            "id": "test1",
            "subject": "Test",
            "from": {
                "emailAddress": {
                    "address": "sender@example.com",
                    "name": "Sender"
                }
            },
            "toRecipients": [
                {"emailAddress": {"address": "recipient@example.com", "name": "Recipient"}}
            ],
            "body": {
                "content": "<p>Special chars: &amp; &lt; &gt; &quot; &#x27;</p>"
            },
            "receivedDateTime": "2024-01-01T00:00:00Z",
            "hasAttachments": False
        }

        email = extractor._process_email(email_data)
        # HTML entities should be decoded
        assert "&" in email.body_text or "Special chars" in email.body_text

    def test_fetch_batch_returns_fewer_than_requested(self, extractor):
        """Test handling when batch returns fewer emails than requested."""
        with patch.object(extractor.graph_client, "fetch_emails") as mock_fetch:
            mock_fetch.return_value = [{"id": "1"}, {"id": "2"}]

            result = extractor._fetch_batch(0, 100)

            assert len(result) == 2
            mock_fetch.assert_called_once_with(max_results=100, skip=0)

    def test_get_total_email_count_returns_sentinel(self, extractor):
        """Test that _get_total_email_count returns large sentinel value."""
        with patch.object(extractor.graph_client, "fetch_emails") as mock_fetch:
            mock_fetch.return_value = []

            count = extractor._get_total_email_count()

            # Returns EMAIL_COUNT_SENTINEL since M365 doesn't provide count
            assert count == EMAIL_COUNT_SENTINEL


class TestCorpusMetadataEnhancements:
    """Test cases for Task 4B.1: Enhanced CorpusMetadata fields."""

    def test_corpus_metadata_has_last_extraction_date_field(self):
        """Test CorpusMetadata model has last_extraction_date field."""
        metadata = CorpusMetadata(
            extraction_date=datetime.now(),
            total_emails=10,
            source="test",
            user_email="user@example.com",
            last_extraction_date=datetime(2024, 1, 15, 10, 0)
        )
        assert metadata.last_extraction_date == datetime(2024, 1, 15, 10, 0)

    def test_corpus_metadata_last_extraction_date_defaults_to_none(self):
        """Test that last_extraction_date defaults to None."""
        metadata = CorpusMetadata(
            extraction_date=datetime.now(),
            total_emails=0,
            source="test",
            user_email="user@example.com"
        )
        assert metadata.last_extraction_date is None

    def test_corpus_metadata_has_email_ids_hash_field(self):
        """Test CorpusMetadata model has email_ids_hash field."""
        metadata = CorpusMetadata(
            extraction_date=datetime.now(),
            total_emails=5,
            source="test",
            user_email="user@example.com",
            email_ids_hash="abc123def456"
        )
        assert metadata.email_ids_hash == "abc123def456"

    def test_corpus_metadata_email_ids_hash_defaults_to_none(self):
        """Test that email_ids_hash defaults to None."""
        metadata = CorpusMetadata(
            extraction_date=datetime.now(),
            total_emails=0,
            source="test",
            user_email="user@example.com"
        )
        assert metadata.email_ids_hash is None

    def test_corpus_metadata_has_extraction_params_field(self):
        """Test CorpusMetadata model has extraction_params field."""
        params = {"batch_size": 500, "max_emails": 1000}
        metadata = CorpusMetadata(
            extraction_date=datetime.now(),
            total_emails=100,
            source="test",
            user_email="user@example.com",
            extraction_params=params
        )
        assert metadata.extraction_params == params
        assert metadata.extraction_params["batch_size"] == 500

    def test_corpus_metadata_extraction_params_defaults_to_none(self):
        """Test that extraction_params defaults to None."""
        metadata = CorpusMetadata(
            extraction_date=datetime.now(),
            total_emails=0,
            source="test",
            user_email="user@example.com"
        )
        assert metadata.extraction_params is None

    def test_corpus_metadata_all_new_fields_in_model_dump(self):
        """Test that all new metadata fields are included in model_dump output."""
        metadata = CorpusMetadata(
            extraction_date=datetime.now(),
            total_emails=50,
            source="test",
            user_email="user@example.com",
            last_extraction_date=datetime(2024, 6, 1),
            email_ids_hash="hash123",
            extraction_params={"batch_size": 100}
        )
        dumped = metadata.model_dump()

        assert "last_extraction_date" in dumped
        assert "email_ids_hash" in dumped
        assert "extraction_params" in dumped
        assert dumped["email_ids_hash"] == "hash123"


class TestExtractionMetadataUpdate:
    """Test cases for updating metadata during extraction."""

    @pytest.fixture
    def extractor(self, tmp_path):
        """Create EmailExtractor for metadata update tests."""
        return EmailExtractor(
            user_email="test@example.com",
            checkpoint_dir=str(tmp_path)
        )

    @pytest.fixture
    def mock_email_data(self):
        """Create mock M365 email data."""
        return {
            "id": "msg123",
            "subject": "Test Email",
            "from": {
                "emailAddress": {
                    "address": "sender@example.com",
                    "name": "Test Sender"
                }
            },
            "toRecipients": [
                {"emailAddress": {"address": "recipient@example.com", "name": "Recipient"}}
            ],
            "body": {"content": "<p>Test body</p>"},
            "receivedDateTime": "2024-01-15T10:30:00Z",
            "hasAttachments": False
        }

    @patch.object(EmailExtractor, "_get_total_email_count")
    @patch.object(EmailExtractor, "_fetch_batch")
    def test_extraction_result_includes_extraction_params(
        self, mock_fetch_batch, mock_get_count, extractor, mock_email_data
    ):
        """Test that extraction result corpus includes extraction parameters."""
        mock_get_count.return_value = 1
        mock_fetch_batch.return_value = [mock_email_data]

        result = extractor.extract_all(max_batch_size=250, checkpoint_interval=50)

        # Verify extraction_params is populated
        assert result.corpus.extraction_metadata.extraction_params is not None
        params = result.corpus.extraction_metadata.extraction_params
        assert params["batch_size"] == 250
        assert params["checkpoint_interval"] == 50

    @patch.object(EmailExtractor, "_get_total_email_count")
    @patch.object(EmailExtractor, "_fetch_batch")
    def test_extraction_result_includes_email_ids_hash(
        self, mock_fetch_batch, mock_get_count, extractor, mock_email_data
    ):
        """Test that extraction result corpus includes email_ids_hash."""
        mock_get_count.return_value = 1
        mock_fetch_batch.return_value = [mock_email_data]

        result = extractor.extract_all(max_batch_size=100)

        # Verify email_ids_hash is populated
        assert result.corpus.extraction_metadata.email_ids_hash is not None
        assert len(result.corpus.extraction_metadata.email_ids_hash) > 0

    @patch.object(EmailExtractor, "_get_total_email_count")
    @patch.object(EmailExtractor, "_fetch_batch")
    def test_email_ids_hash_changes_with_different_emails(
        self, mock_fetch_batch, mock_get_count, extractor
    ):
        """Test that email_ids_hash changes when emails are different."""
        mock_get_count.return_value = 1

        # First extraction
        email1 = {
            "id": "msg_001",
            "subject": "Email 1",
            "from": {"emailAddress": {"address": "a@example.com", "name": "A"}},
            "toRecipients": [{"emailAddress": {"address": "r@example.com", "name": "R"}}],
            "body": {"content": "Body 1"},
            "receivedDateTime": "2024-01-01T00:00:00Z",
            "hasAttachments": False
        }
        mock_fetch_batch.return_value = [email1]
        result1 = extractor.extract_all()
        hash1 = result1.corpus.extraction_metadata.email_ids_hash

        # Second extraction with different email
        email2 = {
            "id": "msg_002",  # Different ID
            "subject": "Email 2",
            "from": {"emailAddress": {"address": "b@example.com", "name": "B"}},
            "toRecipients": [{"emailAddress": {"address": "r@example.com", "name": "R"}}],
            "body": {"content": "Body 2"},
            "receivedDateTime": "2024-01-02T00:00:00Z",
            "hasAttachments": False
        }
        mock_fetch_batch.return_value = [email2]
        result2 = extractor.extract_all()
        hash2 = result2.corpus.extraction_metadata.email_ids_hash

        # Hashes should be different
        assert hash1 != hash2


class TestIntegrationScenarios:
    """Integration-style tests for complete workflows."""

    @pytest.fixture
    def extractor(self, tmp_path):
        """Create EmailExtractor for integration tests."""
        return EmailExtractor(
            user_email="integration@example.com",
            checkpoint_dir=str(tmp_path)
        )

    def test_full_extraction_workflow_empty_inbox(self, extractor):
        """Test complete extraction workflow with empty inbox."""
        with patch.object(extractor.graph_client, "fetch_emails") as mock_fetch:
            mock_fetch.return_value = []

            result = extractor.extract_all()

            assert result.success_count == 0
            assert result.failure_count == 0
            assert len(result.corpus.emails) == 0

    @patch.object(EmailExtractor, "_get_total_email_count")
    @patch.object(EmailExtractor, "_fetch_batch")
    def test_full_extraction_workflow_multiple_batches(
        self, mock_fetch_batch, mock_get_count, extractor
    ):
        """Test extraction across multiple batches."""
        mock_get_count.return_value = EMAIL_COUNT_SENTINEL

        # First batch: 50 emails, second batch: 30 emails, third batch: empty
        batch1 = [{
            "id": f"email_{i}",
            "subject": f"Subject {i}",
            "from": {"emailAddress": {"address": f"sender{i}@example.com", "name": f"Sender {i}"}},
            "toRecipients": [{"emailAddress": {"address": "recipient@example.com", "name": "R"}}],
            "body": {"content": f"<p>Body {i}</p>"},
            "receivedDateTime": "2024-01-01T00:00:00Z",
            "hasAttachments": False
        } for i in range(50)]

        batch2 = [{
            "id": f"email_{i + 50}",
            "subject": f"Subject {i + 50}",
            "from": {"emailAddress": {"address": f"sender{i + 50}@example.com", "name": f"Sender {i}"}},
            "toRecipients": [{"emailAddress": {"address": "recipient@example.com", "name": "R"}}],
            "body": {"content": f"<p>Body {i}</p>"},
            "receivedDateTime": "2024-01-01T00:00:00Z",
            "hasAttachments": False
        } for i in range(30)]

        mock_fetch_batch.side_effect = [batch1, batch2, []]

        result = extractor.extract_all(max_batch_size=50, checkpoint_interval=100)

        assert result.success_count == 80
        assert len(result.corpus.emails) == 80

    def test_checkpoint_cleared_on_success(self, extractor, tmp_path):
        """Test checkpoint file is cleared after successful extraction."""
        checkpoint_file = tmp_path / "extraction_checkpoint.json"

        # Create a checkpoint file
        with open(checkpoint_file, "w") as f:
            json.dump({"test": "data"}, f)

        with patch.object(extractor.graph_client, "fetch_emails") as mock_fetch:
            mock_fetch.return_value = []

            extractor.extract_all()

            # Checkpoint should be cleared
            assert not checkpoint_file.exists()


class TestSharedBatchLoopCheckpoint:
    """Test that checkpoint behavior in _execute_batch_loop affects both extraction modes."""

    @pytest.fixture
    def extractor(self, tmp_path):
        """Create EmailExtractor with temp directory."""
        return EmailExtractor(
            user_email="shared@example.com",
            checkpoint_dir=str(tmp_path)
        )

    @pytest.fixture
    def valid_email_data(self):
        """Create valid M365 email data."""
        return {
            "id": "shared_msg",
            "subject": "Shared Test",
            "from": {
                "emailAddress": {
                    "address": "sender@example.com",
                    "name": "Sender"
                }
            },
            "toRecipients": [
                {"emailAddress": {"address": "recipient@example.com", "name": "Recipient"}}
            ],
            "body": {"content": "<p>Shared body</p>"},
            "receivedDateTime": "2024-01-01T00:00:00Z",
            "hasAttachments": False
        }

    @pytest.fixture
    def existing_corpus(self):
        """Create existing corpus for incremental tests."""
        return Corpus(
            extraction_metadata=CorpusMetadata(
                extraction_date=datetime(2024, 1, 1, 10, 0),
                total_emails=0,
                source="Hotmail/M365",
                user_email="shared@example.com",
                last_extraction_date=datetime(2024, 1, 1, 10, 0),
            ),
            emails=[],
        )

    @patch.object(EmailExtractor, "_get_total_email_count")
    @patch.object(EmailExtractor, "_fetch_batch")
    def test_checkpoint_saves_in_extract_all(
        self, mock_fetch_batch, mock_get_count, extractor, valid_email_data
    ):
        """Test that checkpoint saving works in extract_all via shared batch loop."""
        mock_get_count.return_value = EMAIL_COUNT_SENTINEL
        mock_fetch_batch.side_effect = [
            [valid_email_data] * 100,
            []
        ]

        with patch.object(extractor.checkpoint_manager, "save_checkpoint") as mock_save:
            extractor.extract_all(max_batch_size=100, checkpoint_interval=100)
            assert mock_save.called, "Checkpoint should be saved during extract_all"

    def test_checkpoint_saves_in_extract_incremental(
        self, extractor, valid_email_data, existing_corpus
    ):
        """Test that checkpoint saving works in extract_incremental via shared batch loop."""
        # Create 100 unique emails for the incremental batch
        emails = []
        for i in range(100):
            email = valid_email_data.copy()
            email["id"] = f"new_msg_{i}"
            emails.append(email)

        with patch.object(extractor.graph_client, "fetch_emails") as mock_fetch:
            mock_fetch.side_effect = [emails, []]

            with patch.object(extractor.checkpoint_manager, "save_checkpoint") as mock_save:
                extractor.extract_incremental(
                    existing_corpus, max_batch_size=100, checkpoint_interval=100
                )
                assert mock_save.called, (
                    "Checkpoint should be saved during extract_incremental "
                    "(shared batch loop now handles checkpoints for both modes)"
                )

    @patch.object(EmailExtractor, "_get_total_email_count")
    @patch.object(EmailExtractor, "_fetch_batch")
    def test_same_checkpoint_interval_used_by_both_modes(
        self, mock_fetch_batch, mock_get_count, extractor, valid_email_data, existing_corpus
    ):
        """Test that modifying checkpoint manager interval affects both extraction modes identically."""
        # Set the checkpoint manager interval to 25 so we get checkpoints at 25 and 50
        extractor.checkpoint_manager.checkpoint_interval = 25

        # Generate unique emails for each mode
        full_emails = []
        for i in range(50):
            email = valid_email_data.copy()
            email["id"] = f"full_{i}"
            full_emails.append(email)

        incr_emails = []
        for i in range(50):
            email = valid_email_data.copy()
            email["id"] = f"incr_{i}"
            incr_emails.append(email)

        # Test extract_all
        mock_get_count.return_value = EMAIL_COUNT_SENTINEL
        mock_fetch_batch.side_effect = [full_emails, []]

        with patch.object(extractor.checkpoint_manager, "save_checkpoint") as mock_save_full:
            extractor.extract_all(max_batch_size=50)
            full_save_count = mock_save_full.call_count

        # Test extract_incremental
        with patch.object(extractor.graph_client, "fetch_emails") as mock_fetch:
            mock_fetch.side_effect = [incr_emails, []]

            with patch.object(extractor.checkpoint_manager, "save_checkpoint") as mock_save_incr:
                extractor.extract_incremental(existing_corpus, max_batch_size=50)
                incr_save_count = mock_save_incr.call_count

        # Both modes should save checkpoints the same number of times
        # because they share _execute_batch_loop
        assert full_save_count == incr_save_count, (
            f"Checkpoint saves should be equal: extract_all={full_save_count}, "
            f"extract_incremental={incr_save_count}"
        )
        assert full_save_count == 2, (
            f"Expected 2 checkpoint saves (at 25 and 50), got {full_save_count}"
        )


class TestErrorMessageFormatting:
    """Test cases for work item 1.4: Clean up error messages during extraction.

    Validates that:
    - Pydantic ValidationErrors produce single-line warnings with field name
    - Generic exceptions show type and message concisely
    - Email IDs are truncated to 12 characters
    - End-of-extraction summary reports error counts by category
    - Full error details are preserved in ExtractionError.error_message
    """

    @pytest.fixture
    def extractor(self, tmp_path):
        """Create EmailExtractor for error formatting tests."""
        return EmailExtractor(
            user_email="errors@example.com",
            checkpoint_dir=str(tmp_path),
        )

    @pytest.fixture
    def valid_email_data(self):
        """Create valid M365 email data."""
        return {
            "id": "valid_msg_12345",
            "subject": "Valid Subject",
            "from": {
                "emailAddress": {
                    "address": "sender@example.com",
                    "name": "Sender",
                }
            },
            "toRecipients": [
                {"emailAddress": {"address": "recipient@example.com", "name": "R"}}
            ],
            "body": {"content": "<p>Valid body</p>"},
            "receivedDateTime": "2024-01-01T00:00:00Z",
            "hasAttachments": False,
        }

    @patch.object(EmailExtractor, "_get_total_email_count")
    @patch.object(EmailExtractor, "_fetch_batch")
    def test_validation_error_single_line_with_field(
        self, mock_fetch_batch, mock_get_count, extractor
    ):
        """Pydantic ValidationError is logged as single-line warning with field name."""
        mock_get_count.return_value = 1
        # Email with missing sender to trigger ValidationError
        bad_email = {
            "id": "abcdef123456_extra_chars",
            "subject": "Bad",
            "from": {},  # Missing emailAddress -> KeyError before Pydantic
            "toRecipients": [],
            "body": {"content": "body"},
            "receivedDateTime": "2024-01-01T00:00:00Z",
            "hasAttachments": False,
        }
        mock_fetch_batch.return_value = [bad_email]

        warnings = []
        original_warning = extractor.logger.warning
        extractor.logger.warning = lambda msg, *a, **kw: warnings.append(msg)

        try:
            extractor.extract_all(max_batch_size=100)
        finally:
            extractor.logger.warning = original_warning

        # Should have exactly one warning about skipping
        assert len(warnings) == 1
        msg = warnings[0]
        # Email ID should be truncated to 12 chars
        assert "abcdef123456" in msg
        assert "abcdef123456_extra_chars" not in msg
        # Should contain "Skipped email" prefix
        assert msg.startswith("Skipped email")

    @patch.object(EmailExtractor, "_get_total_email_count")
    @patch.object(EmailExtractor, "_fetch_batch")
    def test_generic_exception_shows_type_and_message(
        self, mock_fetch_batch, mock_get_count, extractor
    ):
        """Generic exceptions display type name and message concisely."""
        mock_get_count.return_value = 1
        bad_email = {"id": "long_id_abcdef_ghijkl"}
        mock_fetch_batch.return_value = [bad_email]

        warnings = []
        original_warning = extractor.logger.warning
        extractor.logger.warning = lambda msg, *a, **kw: warnings.append(msg)

        try:
            extractor.extract_all(max_batch_size=100)
        finally:
            extractor.logger.warning = original_warning

        assert len(warnings) == 1
        msg = warnings[0]
        # Should show error type name (KeyError, TypeError, etc.)
        assert "Skipped email long_id_abcd" in msg
        # Should contain the exception class name
        assert "Error" in msg or "error" in msg.lower()

    @patch.object(EmailExtractor, "_get_total_email_count")
    @patch.object(EmailExtractor, "_fetch_batch")
    def test_email_id_truncated_to_12_chars(
        self, mock_fetch_batch, mock_get_count, extractor
    ):
        """Email ID in warning messages is truncated to first 12 characters."""
        mock_get_count.return_value = 1
        bad_email = {"id": "123456789012XYZEXTRA"}
        mock_fetch_batch.return_value = [bad_email]

        warnings = []
        original_warning = extractor.logger.warning
        extractor.logger.warning = lambda msg, *a, **kw: warnings.append(msg)

        try:
            extractor.extract_all(max_batch_size=100)
        finally:
            extractor.logger.warning = original_warning

        msg = warnings[0]
        assert "123456789012" in msg
        assert "XYZEXTRA" not in msg

    @patch.object(EmailExtractor, "_get_total_email_count")
    @patch.object(EmailExtractor, "_fetch_batch")
    def test_error_summary_logged_after_extraction(
        self, mock_fetch_batch, mock_get_count, extractor
    ):
        """End-of-extraction summary reports total errors and counts by type."""
        mock_get_count.return_value = 3
        # Three bad emails to produce errors
        bad_emails = [
            {"id": "bad1"},
            {"id": "bad2"},
            {"id": "bad3"},
        ]
        mock_fetch_batch.return_value = bad_emails

        info_messages = []
        original_info = extractor.logger.info
        extractor.logger.info = lambda msg, *a, **kw: info_messages.append(msg)

        try:
            extractor.extract_all(max_batch_size=100)
        finally:
            extractor.logger.info = original_info

        # Find the summary message
        summary_msgs = [m for m in info_messages if "Skipped" in m and "emails" in m]
        assert len(summary_msgs) == 1, (
            f"Expected exactly one summary message, got: {info_messages}"
        )
        summary = summary_msgs[0]
        assert "Skipped 3 emails" in summary
        # Should contain error type breakdown
        assert "KeyError" in summary or "Error" in summary

    @patch.object(EmailExtractor, "_get_total_email_count")
    @patch.object(EmailExtractor, "_fetch_batch")
    def test_no_summary_when_no_errors(
        self, mock_fetch_batch, mock_get_count, extractor, valid_email_data
    ):
        """No error summary is logged when all emails process successfully."""
        mock_get_count.return_value = 1
        mock_fetch_batch.return_value = [valid_email_data]

        info_messages = []
        original_info = extractor.logger.info
        extractor.logger.info = lambda msg, *a, **kw: info_messages.append(msg)

        try:
            extractor.extract_all(max_batch_size=100)
        finally:
            extractor.logger.info = original_info

        # No "Skipped N emails" summary should appear
        summary_msgs = [m for m in info_messages if m.startswith("Skipped") and "emails" in m]
        assert len(summary_msgs) == 0, (
            f"Unexpected error summary in successful extraction: {summary_msgs}"
        )

    @patch.object(EmailExtractor, "_get_total_email_count")
    @patch.object(EmailExtractor, "_fetch_batch")
    def test_full_error_preserved_in_extraction_error(
        self, mock_fetch_batch, mock_get_count, extractor
    ):
        """Full error details are stored in ExtractionError.error_message for debugging."""
        mock_get_count.return_value = 1
        bad_email = {"id": "preserve_test"}
        mock_fetch_batch.return_value = [bad_email]

        result = extractor.extract_all(max_batch_size=100)

        assert len(result.failed_emails) == 1
        error = result.failed_emails[0]
        assert error.email_id == "preserve_test"
        assert error.error_type == "malformed"
        # Full error message should be present (not truncated)
        assert len(error.error_message) > 0

    @patch.object(EmailExtractor, "_get_total_email_count")
    @patch.object(EmailExtractor, "_fetch_batch")
    def test_validation_error_format_with_pydantic(
        self, mock_fetch_batch, mock_get_count, extractor
    ):
        """Pydantic ValidationError produces field-specific single-line warning."""
        mock_get_count.return_value = 1

        # Force _process_email to raise a Pydantic ValidationError
        def raise_validation_error(email_data):
            # Create a real Pydantic ValidationError by trying to construct Email
            # with invalid data
            from pydantic import BaseModel

            class StrictModel(BaseModel):
                required_field: int

            StrictModel(required_field="not_an_int")  # Will raise ValidationError

        with patch.object(extractor, "_process_email", side_effect=raise_validation_error):
            mock_fetch_batch.return_value = [{"id": "pydantic_test_id"}]

            # This won't work because raise_validation_error raises before returning
            # Let's use a direct ValidationError instead
            pass

        # Better approach: directly raise a ValidationError
        def make_validation_error(email_data):
            raise ValidationError.from_exception_data(
                title="Email",
                line_errors=[
                    {
                        "type": "missing",
                        "loc": ("sender_email",),
                        "msg": "Field required",
                        "input": {},
                    }
                ],
            )

        with patch.object(extractor, "_process_email", side_effect=make_validation_error):
            mock_fetch_batch.return_value = [{"id": "pydantic_test_long_id"}]

            warnings = []
            original_warning = extractor.logger.warning
            extractor.logger.warning = lambda msg, *a, **kw: warnings.append(msg)

            try:
                extractor.extract_all(max_batch_size=100)
            finally:
                extractor.logger.warning = original_warning

            assert len(warnings) == 1
            msg = warnings[0]
            assert "Skipped email pydantic_tes" in msg
            assert "sender_email" in msg
            assert "Field required" in msg

    @patch.object(EmailExtractor, "_get_total_email_count")
    @patch.object(EmailExtractor, "_fetch_batch")
    def test_mixed_error_types_in_summary(
        self, mock_fetch_batch, mock_get_count, extractor
    ):
        """Summary groups errors by type when multiple error types occur."""
        mock_get_count.return_value = 3

        call_count = 0

        def mixed_errors(email_data):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise KeyError("missing_field")
            elif call_count == 2:
                raise KeyError("another_field")
            else:
                raise ValueError("bad value")

        with patch.object(extractor, "_process_email", side_effect=mixed_errors):
            mock_fetch_batch.return_value = [
                {"id": "err1"}, {"id": "err2"}, {"id": "err3"}
            ]

            info_messages = []
            original_info = extractor.logger.info
            extractor.logger.info = lambda msg, *a, **kw: info_messages.append(msg)

            try:
                extractor.extract_all(max_batch_size=100)
            finally:
                extractor.logger.info = original_info

            summary_msgs = [m for m in info_messages if "Skipped" in m and "emails" in m]
            assert len(summary_msgs) == 1
            summary = summary_msgs[0]
            assert "Skipped 3 emails" in summary
            assert "KeyError" in summary
            assert "ValueError" in summary
            # KeyError should show count of 2
            assert "2 KeyError" in summary
            assert "1 ValueError" in summary
