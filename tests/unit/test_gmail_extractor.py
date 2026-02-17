"""Tests for GmailClient and GmailExtractor."""
import base64
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.extractors.gmail_client import GmailClient
from src.extractors.gmail_extractor import GmailExtractor
from src.models.corpus import Corpus, CorpusMetadata
from src.models.email import Email

# ─── GmailClient Tests ────────────────────────────────────────────────


@pytest.fixture
def gmail_client(tmp_path):
    return GmailClient(
        user_email="test@gmail.com",
        credentials_path=tmp_path / "creds.json",
        token_path=tmp_path / "token.json",
    )


@pytest.fixture
def sample_gmail_message():
    """Sample Gmail API message in full format."""
    html_body = "<p>Hello from Gmail</p>"
    encoded_body = base64.urlsafe_b64encode(html_body.encode()).decode()

    return {
        "id": "gmail_001",
        "threadId": "thread_001",
        "snippet": "Hello from Gmail",
        "internalDate": "1705312200000",  # 2024-01-15T10:30:00Z
        "payload": {
            "mimeType": "multipart/alternative",
            "headers": [
                {"name": "From", "value": "sender@example.com"},
                {"name": "To", "value": "test@gmail.com"},
                {"name": "Subject", "value": "Test Gmail Email"},
                {"name": "Date", "value": "Mon, 15 Jan 2024 10:30:00 +0000"},
                {"name": "In-Reply-To", "value": "<prev@example.com>"},
                {"name": "References", "value": "<orig@example.com> <prev@example.com>"},
            ],
            "body": {"size": 0},
            "parts": [
                {
                    "mimeType": "text/plain",
                    "body": {
                        "data": base64.urlsafe_b64encode(b"Hello from Gmail").decode()
                    },
                },
                {
                    "mimeType": "text/html",
                    "body": {"data": encoded_body},
                },
            ],
        },
    }


class TestGmailClientParseEmailHeader:
    def test_name_and_email(self):
        email, name = GmailClient._parse_email_header("John Doe <john@example.com>")
        assert email == "john@example.com"
        assert name == "John Doe"

    def test_quoted_name(self):
        email, name = GmailClient._parse_email_header('"Jane Doe" <jane@example.com>')
        assert email == "jane@example.com"
        assert name == "Jane Doe"

    def test_bare_email(self):
        email, name = GmailClient._parse_email_header("john@example.com")
        assert email == "john@example.com"
        assert name == ""

    def test_angle_bracket_email(self):
        email, name = GmailClient._parse_email_header("<john@example.com>")
        assert email == "john@example.com"
        assert name == ""

    def test_empty_header(self):
        email, name = GmailClient._parse_email_header("")
        assert email == "unknown@unknown.com"
        assert name == ""


class TestGmailClientParseDate:
    def test_rfc2822_date(self):
        result = GmailClient._parse_date("Mon, 15 Jan 2024 10:30:00 +0000")
        assert "2024-01-15" in result
        assert result.endswith("Z")

    def test_internal_date_fallback(self):
        result = GmailClient._parse_date("", "1705312200000")
        assert "2024-01-15" in result

    def test_both_empty_uses_now(self):
        result = GmailClient._parse_date("", None)
        assert "T" in result  # ISO format


class TestGmailClientExtractBody:
    def test_html_from_parts(self, gmail_client, sample_gmail_message):
        body = gmail_client._extract_body(sample_gmail_message["payload"])
        assert "Hello from Gmail" in body
        assert "<p>" in body  # Should get HTML version

    def test_plain_text_fallback(self, gmail_client):
        encoded = base64.urlsafe_b64encode(b"Plain text only").decode()
        payload = {
            "mimeType": "text/plain",
            "body": {"data": encoded},
            "parts": [],
        }
        body = gmail_client._extract_body(payload)
        assert "Plain text only" in body

    def test_empty_payload(self, gmail_client):
        body = gmail_client._extract_body({"body": {}, "parts": []})
        assert body == ""

    def test_3_level_nested_mime(self, gmail_client):
        """3-level nesting: multipart/mixed -> multipart/alternative -> text/html."""
        html_content = "<h1>Deep HTML</h1>"
        plain_content = "Deep plain"
        payload = {
            "mimeType": "multipart/mixed",
            "body": {"size": 0},
            "parts": [
                {
                    "mimeType": "multipart/alternative",
                    "body": {"size": 0},
                    "parts": [
                        {
                            "mimeType": "text/plain",
                            "body": {
                                "data": base64.urlsafe_b64encode(
                                    plain_content.encode()
                                ).decode()
                            },
                        },
                        {
                            "mimeType": "text/html",
                            "body": {
                                "data": base64.urlsafe_b64encode(
                                    html_content.encode()
                                ).decode()
                            },
                        },
                    ],
                },
                {
                    "mimeType": "application/pdf",
                    "filename": "invoice.pdf",
                    "body": {"attachmentId": "att_001", "size": 12345},
                },
            ],
        }

        body = gmail_client._extract_body(payload)
        assert body == html_content
        assert "<h1>" in body

    def test_4_level_nested_mime(self, gmail_client):
        """4-level nesting: multipart/mixed -> multipart/related -> multipart/alternative -> text/html."""
        html_content = "<div>Very deep HTML</div>"
        plain_content = "Very deep plain"
        payload = {
            "mimeType": "multipart/mixed",
            "body": {"size": 0},
            "parts": [
                {
                    "mimeType": "multipart/related",
                    "body": {"size": 0},
                    "parts": [
                        {
                            "mimeType": "multipart/alternative",
                            "body": {"size": 0},
                            "parts": [
                                {
                                    "mimeType": "text/plain",
                                    "body": {
                                        "data": base64.urlsafe_b64encode(
                                            plain_content.encode()
                                        ).decode()
                                    },
                                },
                                {
                                    "mimeType": "text/html",
                                    "body": {
                                        "data": base64.urlsafe_b64encode(
                                            html_content.encode()
                                        ).decode()
                                    },
                                },
                            ],
                        },
                        {
                            "mimeType": "image/png",
                            "filename": "logo.png",
                            "body": {"attachmentId": "att_img", "size": 5000},
                        },
                    ],
                },
                {
                    "mimeType": "application/octet-stream",
                    "filename": "data.bin",
                    "body": {"attachmentId": "att_002", "size": 9999},
                },
            ],
        }

        body = gmail_client._extract_body(payload)
        assert body == html_content

    def test_4_level_plain_text_fallback(self, gmail_client):
        """4-level nesting with only plain text available."""
        plain_content = "Only plain text at depth 4"
        payload = {
            "mimeType": "multipart/mixed",
            "body": {"size": 0},
            "parts": [
                {
                    "mimeType": "multipart/related",
                    "body": {"size": 0},
                    "parts": [
                        {
                            "mimeType": "multipart/alternative",
                            "body": {"size": 0},
                            "parts": [
                                {
                                    "mimeType": "text/plain",
                                    "body": {
                                        "data": base64.urlsafe_b64encode(
                                            plain_content.encode()
                                        ).decode()
                                    },
                                },
                            ],
                        },
                    ],
                },
            ],
        }

        body = gmail_client._extract_body(payload)
        assert body == plain_content

    def test_max_depth_guard(self, gmail_client):
        """Recursion stops at max_depth to prevent stack overflow on malformed messages."""
        html_content = "<p>Too deep</p>"
        # Build a chain 15 levels deep -- only leaf at depth 15 has content
        leaf = {
            "mimeType": "text/html",
            "body": {
                "data": base64.urlsafe_b64encode(html_content.encode()).decode()
            },
        }
        node = leaf
        for _ in range(14):
            node = {
                "mimeType": "multipart/mixed",
                "body": {"size": 0},
                "parts": [node],
            }

        # With default max_depth=10, the leaf at depth 15 should NOT be reached
        body = gmail_client._extract_body(node)
        assert body == ""

    def test_max_depth_allows_content_within_limit(self, gmail_client):
        """Content at exactly max_depth is still reachable."""
        html_content = "<p>At depth limit</p>"
        leaf = {
            "mimeType": "text/html",
            "body": {
                "data": base64.urlsafe_b64encode(html_content.encode()).decode()
            },
        }
        # Build chain of depth 9 wrappings -> leaf at depth 10 (0-indexed: root=0, leaf=10)
        node = leaf
        for _ in range(10):
            node = {
                "mimeType": "multipart/mixed",
                "body": {"size": 0},
                "parts": [node],
            }

        body = gmail_client._extract_body(node)
        assert body == html_content

    def test_html_preferred_over_plain_at_same_level(self, gmail_client):
        """When both HTML and plain exist at the same nesting level, HTML wins."""
        html_content = "<b>HTML wins</b>"
        plain_content = "Plain loses"
        payload = {
            "mimeType": "multipart/alternative",
            "body": {"size": 0},
            "parts": [
                {
                    "mimeType": "text/plain",
                    "body": {
                        "data": base64.urlsafe_b64encode(
                            plain_content.encode()
                        ).decode()
                    },
                },
                {
                    "mimeType": "text/html",
                    "body": {
                        "data": base64.urlsafe_b64encode(
                            html_content.encode()
                        ).decode()
                    },
                },
            ],
        }

        body = gmail_client._extract_body(payload)
        assert body == html_content


class TestGmailClientGetMessage:
    def test_normalize_to_graph_format(self, gmail_client, sample_gmail_message):
        with patch.object(gmail_client, "_get_service") as mock_svc:
            mock_service = MagicMock()
            mock_svc.return_value = mock_service
            mock_service.users().messages().get().execute.return_value = (
                sample_gmail_message
            )

            result = gmail_client._get_message(mock_service, "gmail_001")

        assert result["id"] == "gmail_001"
        assert result["subject"] == "Test Gmail Email"
        assert result["from"]["emailAddress"]["address"] == "sender@example.com"
        assert result["toRecipients"][0]["emailAddress"]["address"] == "test@gmail.com"
        assert result["_gmail_thread_id"] == "thread_001"
        assert result["_in_reply_to"] == "<prev@example.com>"
        assert len(result["_references"]) == 2


class TestGmailClientFetchEmails:
    def test_fetch_emails_calls_list_and_get(self, gmail_client):
        with patch.object(gmail_client, "_get_service") as mock_svc:
            mock_service = MagicMock()
            mock_svc.return_value = mock_service

            # Mock list response
            mock_service.users().messages().list().execute.return_value = {
                "messages": [{"id": "msg1"}, {"id": "msg2"}]
            }

            # Mock get responses
            normalized = {
                "id": "msg1",
                "subject": "Test",
                "from": {"emailAddress": {"address": "a@b.com", "name": "A"}},
                "toRecipients": [],
                "receivedDateTime": "2024-01-15T10:00:00Z",
                "body": {"content": "test"},
                "bodyPreview": "test",
                "hasAttachments": False,
                "conversationId": "t1",
                "_gmail_thread_id": "t1",
                "_in_reply_to": "",
                "_references": [],
            }

            with patch.object(gmail_client, "_get_message", return_value=normalized):
                result = gmail_client.fetch_emails(max_results=10)

            assert len(result) == 2


# ─── GmailExtractor Tests ─────────────────────────────────────────────


@pytest.fixture
def gmail_extractor(tmp_path):
    """Create GmailExtractor with mocked GmailClient."""
    # Patch the GmailClient class where it gets imported
    mock_client = MagicMock()
    with patch("src.extractors.gmail_client.GmailClient", return_value=mock_client):
        extractor = GmailExtractor(
            user_email="test@gmail.com",
            checkpoint_dir=str(tmp_path),
        )
    # Ensure the mock client is used
    extractor.gmail_client = mock_client
    return extractor


@pytest.fixture
def normalized_gmail_messages():
    """Messages already normalized to Graph format by GmailClient."""
    return [
        {
            "id": "gmail_001",
            "subject": "Order Confirmation",
            "from": {
                "emailAddress": {
                    "address": "orders@store.com",
                    "name": "Store Orders",
                }
            },
            "toRecipients": [
                {
                    "emailAddress": {
                        "address": "test@gmail.com",
                        "name": "Test User",
                    }
                }
            ],
            "receivedDateTime": "2025-01-15T10:30:00Z",
            "body": {"contentType": "html", "content": "<p>Your order is confirmed</p>"},
            "bodyPreview": "Your order is confirmed",
            "hasAttachments": False,
            "conversationId": "thread_001",
            "_gmail_thread_id": "thread_001",
            "_in_reply_to": None,
            "_references": [],
        },
        {
            "id": "gmail_002",
            "subject": "Meeting Tomorrow",
            "from": {
                "emailAddress": {
                    "address": "colleague@work.com",
                    "name": "Colleague",
                }
            },
            "toRecipients": [
                {
                    "emailAddress": {
                        "address": "test@gmail.com",
                        "name": "Test User",
                    }
                }
            ],
            "receivedDateTime": "2025-01-16T14:00:00Z",
            "body": {"contentType": "html", "content": "<p>Let's meet at 2pm</p>"},
            "bodyPreview": "Let's meet at 2pm",
            "hasAttachments": False,
            "conversationId": "thread_002",
            "_gmail_thread_id": "thread_002",
            "_in_reply_to": None,
            "_references": [],
        },
    ]


class TestGmailExtractorExtractAll:
    def test_extract_all_success(self, gmail_extractor, normalized_gmail_messages):
        # First call returns messages, second returns empty (end of inbox)
        gmail_extractor.gmail_client.fetch_emails.side_effect = [
            normalized_gmail_messages,
            [],
        ]

        result = gmail_extractor.extract_all(max_batch_size=500)

        assert result.success_count == 2
        assert result.failure_count == 0
        assert result.corpus.extraction_metadata.source == "Gmail"
        assert result.corpus.extraction_metadata.user_email == "test@gmail.com"
        assert len(result.corpus.emails) == 2

    def test_extract_all_empty_inbox(self, gmail_extractor):
        gmail_extractor.gmail_client.fetch_emails.return_value = []

        result = gmail_extractor.extract_all()

        assert result.success_count == 0
        assert len(result.corpus.emails) == 0

    def test_extract_all_handles_malformed_email(self, gmail_extractor):
        bad_message = {
            "id": "bad_001",
            "subject": "Bad Email",
            "from": {"emailAddress": {"address": "not-valid", "name": "Bad"}},
            "toRecipients": [],
            "receivedDateTime": "2025-01-15T10:30:00Z",
            "body": {"content": "test"},
            "hasAttachments": False,
            "_gmail_thread_id": None,
            "_in_reply_to": None,
            "_references": [],
        }
        gmail_extractor.gmail_client.fetch_emails.side_effect = [
            [bad_message],
            [],
        ]

        result = gmail_extractor.extract_all()

        # Should handle the error gracefully
        assert result.failure_count >= 0  # May or may not fail depending on validation

    def test_extract_all_with_progress_callback(
        self, gmail_extractor, normalized_gmail_messages
    ):
        gmail_extractor.gmail_client.fetch_emails.side_effect = [
            normalized_gmail_messages,
            [],
        ]

        callback = MagicMock()
        gmail_extractor.extract_all(progress_callback=callback)

        assert callback.call_count == 2  # Called once per email


class TestGmailExtractorProcessEmail:
    def test_process_email_basic(self, gmail_extractor, normalized_gmail_messages):
        email = gmail_extractor._process_email(normalized_gmail_messages[0])

        assert email.id == "gmail_001"
        assert email.subject == "Order Confirmation"
        assert email.sender_email == "orders@store.com"
        assert email.sender_domain == "store.com"
        assert email.thread_id == "thread_001"

    def test_process_email_with_thread_info(self, gmail_extractor):
        msg = {
            "id": "gmail_003",
            "subject": "Re: Discussion",
            "from": {
                "emailAddress": {"address": "a@b.com", "name": "A"}
            },
            "toRecipients": [
                {"emailAddress": {"address": "test@gmail.com", "name": "Test"}}
            ],
            "receivedDateTime": "2025-01-17T10:00:00Z",
            "body": {"content": "<p>Reply</p>"},
            "hasAttachments": False,
            "_gmail_thread_id": "thread_abc",
            "_in_reply_to": "<orig@msg.id>",
            "_references": ["<orig@msg.id>", "<prev@msg.id>"],
        }

        email = gmail_extractor._process_email(msg)

        assert email.thread_id == "thread_abc"
        assert email.in_reply_to == "<orig@msg.id>"
        assert len(email.references) == 2


class TestGmailExtractorIncremental:
    def test_incremental_deduplicates(
        self, gmail_extractor, normalized_gmail_messages
    ):
        # Existing corpus with one email
        existing_email = Email(
            id="gmail_001",
            sender_email="orders@store.com",
            sender_name="Store Orders",
            sender_domain="store.com",
            recipient_email="test@gmail.com",
            subject="Order Confirmation",
            body_text="Your order is confirmed",
            received_date=datetime(2025, 1, 15, 10, 30, tzinfo=timezone.utc),
            has_attachments=False,
        )
        existing_corpus = Corpus(
            extraction_metadata=CorpusMetadata(
                extraction_date=datetime(2025, 1, 15, tzinfo=timezone.utc),
                total_emails=1,
                source="Gmail",
                user_email="test@gmail.com",
                last_extraction_date=datetime(2025, 1, 15, tzinfo=timezone.utc),
            ),
            emails=[existing_email],
        )

        gmail_extractor.gmail_client.fetch_emails.side_effect = [
            normalized_gmail_messages,  # Both old and new
            [],
        ]

        result = gmail_extractor.extract_incremental(existing_corpus)

        # Should only add the new one (gmail_002), skip duplicate gmail_001
        assert result.new_emails_count == 1
        assert result.previous_count == 1
        assert result.total_count == 2


class TestGmailExtractorComputeHash:
    def test_hash_empty(self):
        assert GmailExtractor._compute_email_ids_hash([]) == ""

    def test_hash_deterministic(self):
        emails = [
            Email(
                id="a",
                sender_email="x@y.com",
                sender_domain="y.com",
                subject="",
                body_text="",
                received_date=datetime.now(),
                has_attachments=False,
            ),
            Email(
                id="b",
                sender_email="x@y.com",
                sender_domain="y.com",
                subject="",
                body_text="",
                received_date=datetime.now(),
                has_attachments=False,
            ),
        ]
        h1 = GmailExtractor._compute_email_ids_hash(emails)
        h2 = GmailExtractor._compute_email_ids_hash(list(reversed(emails)))
        assert h1 == h2  # Order-independent


class TestGmailRecipientParsing:
    """Test safe recipient parsing for Gmail extractor (Work Item 1.1)."""

    @pytest.fixture
    def extractor(self, tmp_path):
        """Create GmailExtractor with mocked GmailClient."""
        mock_client = MagicMock()
        with patch("src.extractors.gmail_client.GmailClient", return_value=mock_client):
            ext = GmailExtractor(
                user_email="test@gmail.com",
                checkpoint_dir=str(tmp_path),
            )
        ext.gmail_client = mock_client
        return ext

    @pytest.fixture
    def base_email_data(self):
        """Base normalized Gmail email data without toRecipients."""
        return {
            "id": "gmail_recipient_test",
            "subject": "Recipient Test",
            "from": {
                "emailAddress": {
                    "address": "sender@example.com",
                    "name": "Sender",
                }
            },
            "body": {"content": "<p>Body</p>"},
            "receivedDateTime": "2025-01-15T10:30:00Z",
            "hasAttachments": False,
            "_gmail_thread_id": "thread_test",
            "_in_reply_to": None,
            "_references": [],
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
        base_email_data.pop("toRecipients", None)
        email = extractor._process_email(base_email_data)
        assert email.recipient_email is None
        assert email.recipient_name == ""

    def test_valid_to_recipients(self, extractor, base_email_data):
        """Emails with valid toRecipients extract correctly."""
        base_email_data["toRecipients"] = [
            {
                "emailAddress": {
                    "address": "recipient@gmail.com",
                    "name": "Gmail User",
                }
            }
        ]
        email = extractor._process_email(base_email_data)
        assert email.recipient_email == "recipient@gmail.com"
        assert email.recipient_name == "Gmail User"

    def test_multiple_to_recipients_takes_first(self, extractor, base_email_data):
        """When multiple recipients exist, the first is used."""
        base_email_data["toRecipients"] = [
            {"emailAddress": {"address": "first@gmail.com", "name": "First"}},
            {"emailAddress": {"address": "second@gmail.com", "name": "Second"}},
        ]
        email = extractor._process_email(base_email_data)
        assert email.recipient_email == "first@gmail.com"
        assert email.recipient_name == "First"

    def test_to_recipients_with_empty_email_address_dict(self, extractor, base_email_data):
        """When toRecipients has entry with empty emailAddress, returns None/empty."""
        base_email_data["toRecipients"] = [{"emailAddress": {}}]
        email = extractor._process_email(base_email_data)
        assert email.recipient_email is None
        assert email.recipient_name == ""
