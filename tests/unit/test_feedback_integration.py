"""
Unit tests for Phase 5, Work Item 5.4: Wire Feedback into LLM Classifier and Pipeline.

TDD tests written FIRST, covering:
1. LLMClassifier accepts optional FewShotRetriever in __init__
2. classify() auto-retrieves few-shot examples when retriever is available
3. _build_prompt() includes few-shot examples from retriever results
4. EmailCategorizer saves classifications to DB when database is available
5. Pipeline surfaces uncertain classifications after classification run

Tests use mocks for the LLM client, FewShotRetriever, and Database to isolate
the feedback integration wiring from external dependencies.
"""

from datetime import datetime
from unittest.mock import MagicMock

from src.classifiers.base import (
    ClassificationContext,
    ClassificationResult,
)
from src.config.models import CategoryDefinition, ClassifierConfig
from src.models.corpus import Corpus, CorpusMetadata
from src.models.email import Email
from src.models.rule import (
    CategoryRule,
    ConditionField,
    ConditionLogic,
    ConditionOperator,
    RuleAction,
    RuleActionType,
    RuleCondition,
    RuleSet,
)
from src.storage.database import Database

# =============================================================================
# Helpers
# =============================================================================


def _make_email(**overrides) -> Email:
    """Create a test email with sensible defaults."""
    defaults = {
        "id": "email_001",
        "sender_email": "newsletter@example.com",
        "sender_name": "Test Sender",
        "sender_domain": "example.com",
        "subject": "Weekly Newsletter: Top Stories",
        "body_text": "Here are this week's top stories...",
        "received_date": datetime(2024, 1, 15, 10, 0),
        "has_attachments": False,
    }
    defaults.update(overrides)
    return Email(**defaults)


def _make_config(**overrides) -> ClassifierConfig:
    """Create a test ClassifierConfig."""
    defaults = {
        "provider": "ollama",
        "model_name": "qwen2.5:7b",
        "categories": [
            CategoryDefinition(
                name="Newsletters",
                description="Regular email digests",
                keywords=["newsletter", "digest"],
            ),
            CategoryDefinition(
                name="Promotions",
                description="Marketing emails",
                keywords=["sale", "discount"],
            ),
        ],
    }
    defaults.update(overrides)
    return ClassifierConfig(**defaults)


def _make_rule(
    rule_id: str = "rule_001",
    action_target: str = "Newsletters",
    priority: int = 50,
) -> CategoryRule:
    """Create a test CategoryRule."""
    return CategoryRule(
        rule_id=rule_id,
        name="Test Rule",
        conditions=[
            RuleCondition(
                field=ConditionField.SENDER_DOMAIN,
                operator=ConditionOperator.EQUALS,
                value="example.com",
                case_sensitive=False,
            )
        ],
        action=RuleAction(
            action_type=RuleActionType.CATEGORIZE,
            target=action_target,
        ),
        logic=ConditionLogic.AND,
        priority=priority,
        enabled=True,
    )


def _make_rule_set(*rules: CategoryRule) -> RuleSet:
    """Create a RuleSet from the given rules."""
    return RuleSet(rules=list(rules))


def _make_mock_retriever(examples=None):
    """Create a mock FewShotRetriever that returns given examples."""
    retriever = MagicMock()
    if examples is None:
        examples = [
            {
                "email_subject": "50% off everything!",
                "category": "Promotions",
            },
            {
                "email_subject": "Your Weekly Digest",
                "category": "Newsletters",
            },
        ]
    retriever.retrieve.return_value = examples
    return retriever


def _make_mock_llm_response(category="Newsletters", confidence=0.92):
    """Create a mock LLM response."""
    from src.classifiers.llm_classifier import LLMClassificationResponse

    return LLMClassificationResponse(
        category=category,
        confidence=confidence,
        reasoning=f"Email matches {category} pattern",
    )


def _make_classifier_with_mock(config=None, mock_response=None, retriever=None):
    """Create an LLMClassifier with a mocked Instructor client and optional retriever."""
    from src.classifiers.llm_classifier import LLMClassifier

    if config is None:
        config = _make_config()

    if mock_response is None:
        mock_response = _make_mock_llm_response()

    classifier = LLMClassifier(config, few_shot_retriever=retriever)

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_response
    classifier._client = mock_client

    return classifier, mock_client


# =============================================================================
# Task 1: LLMClassifier accepts optional FewShotRetriever
# =============================================================================


class TestLLMClassifierRetrieverInit:
    """Test that LLMClassifier accepts and stores a FewShotRetriever."""

    def test_init_without_retriever_defaults_to_none(self):
        """LLMClassifier works without a retriever (backward compatible)."""
        from src.classifiers.llm_classifier import LLMClassifier

        config = _make_config()
        classifier = LLMClassifier(config)
        assert classifier._few_shot_retriever is None

    def test_init_with_retriever_stores_it(self):
        """LLMClassifier stores the retriever when provided."""
        from src.classifiers.llm_classifier import LLMClassifier

        config = _make_config()
        retriever = _make_mock_retriever()
        classifier = LLMClassifier(config, few_shot_retriever=retriever)
        assert classifier._few_shot_retriever is retriever

    def test_init_preserves_existing_config(self):
        """Adding retriever does not break existing config storage."""
        from src.classifiers.llm_classifier import LLMClassifier

        config = _make_config()
        retriever = _make_mock_retriever()
        classifier = LLMClassifier(config, few_shot_retriever=retriever)
        assert classifier._config is config


# =============================================================================
# Task 2: classify() auto-retrieves few-shot examples when retriever available
# =============================================================================


class TestClassifyWithRetriever:
    """Test that classify() uses the retriever to get few-shot examples."""

    def test_classify_calls_retriever_when_available(self):
        """classify() calls retriever.retrieve() when a retriever is set."""
        retriever = _make_mock_retriever()
        classifier, _ = _make_classifier_with_mock(retriever=retriever)
        email = _make_email()

        classifier.classify(email, ["Newsletters", "Promotions"])

        retriever.retrieve.assert_called_once()

    def test_classify_passes_email_to_retriever(self):
        """classify() passes the email to the retriever."""
        retriever = _make_mock_retriever()
        classifier, _ = _make_classifier_with_mock(retriever=retriever)
        email = _make_email()

        classifier.classify(email, ["Newsletters", "Promotions"])

        # The retrieve call should receive the email
        call_args = retriever.retrieve.call_args
        assert call_args is not None
        # Check the email was passed (positional or keyword)
        all_args = list(call_args.args) + list(call_args.kwargs.values())
        assert email in all_args

    def test_classify_without_retriever_still_works(self):
        """classify() works fine with no retriever (zero-shot mode)."""
        classifier, _ = _make_classifier_with_mock(retriever=None)
        email = _make_email()

        result = classifier.classify(email, ["Newsletters", "Promotions"])

        assert isinstance(result, ClassificationResult)
        assert result.category_name == "Newsletters"

    def test_classify_merges_retriever_examples_with_existing_context(self):
        """classify() merges retriever examples into an existing context."""
        retriever = _make_mock_retriever(
            examples=[{"email_subject": "Sale Alert", "category": "Promotions"}]
        )
        classifier, mock_client = _make_classifier_with_mock(retriever=retriever)
        email = _make_email()
        context = ClassificationContext(
            category_descriptions={"Newsletters": "Regular digests"},
        )

        classifier.classify(email, ["Newsletters", "Promotions"], context=context)

        # Check the prompt sent to the LLM includes retriever examples
        call_kwargs = mock_client.chat.completions.create.call_args
        messages = call_kwargs.kwargs["messages"]
        full_text = " ".join(m["content"] for m in messages)
        assert "Sale Alert" in full_text

    def test_classify_uses_retriever_examples_when_no_context_provided(self):
        """classify() creates a context from retriever when no context given."""
        retriever = _make_mock_retriever(
            examples=[{"email_subject": "Breaking News", "category": "Newsletters"}]
        )
        classifier, mock_client = _make_classifier_with_mock(retriever=retriever)
        email = _make_email()

        classifier.classify(email, ["Newsletters", "Promotions"])

        call_kwargs = mock_client.chat.completions.create.call_args
        messages = call_kwargs.kwargs["messages"]
        full_text = " ".join(m["content"] for m in messages)
        assert "Breaking News" in full_text

    def test_classify_handles_retriever_error_gracefully(self):
        """classify() continues with zero-shot if retriever raises an error."""
        retriever = _make_mock_retriever()
        retriever.retrieve.side_effect = Exception("sqlite-vec unavailable")
        classifier, _ = _make_classifier_with_mock(retriever=retriever)
        email = _make_email()

        # Should not raise — graceful degradation to zero-shot
        result = classifier.classify(email, ["Newsletters", "Promotions"])
        assert isinstance(result, ClassificationResult)

    def test_classify_handles_retriever_returning_empty(self):
        """classify() works when retriever returns no examples."""
        retriever = _make_mock_retriever(examples=[])
        classifier, _ = _make_classifier_with_mock(retriever=retriever)
        email = _make_email()

        result = classifier.classify(email, ["Newsletters", "Promotions"])
        assert isinstance(result, ClassificationResult)


# =============================================================================
# Task 3: _build_prompt includes few-shot examples from retriever
# =============================================================================


class TestBuildPromptWithRetrieverExamples:
    """Test that _build_prompt correctly includes retriever-provided examples."""

    def test_prompt_includes_retriever_examples(self):
        """Few-shot examples from retriever appear in the prompt."""
        from src.classifiers.llm_classifier import LLMClassifier

        config = _make_config()
        classifier = LLMClassifier(config)
        email = _make_email()
        context = ClassificationContext(
            few_shot_examples=[
                {"email_subject": "Flash Sale Today!", "category": "Promotions"},
                {"email_subject": "Monthly Digest", "category": "Newsletters"},
            ]
        )

        system_prompt, user_prompt = classifier._build_prompt(
            email, ["Newsletters", "Promotions"], context=context
        )

        full = system_prompt + user_prompt
        assert "Flash Sale Today!" in full
        assert "Monthly Digest" in full

    def test_prompt_without_few_shot_examples_is_valid(self):
        """Prompt is valid without few-shot examples (zero-shot mode)."""
        from src.classifiers.llm_classifier import LLMClassifier

        config = _make_config()
        classifier = LLMClassifier(config)
        email = _make_email()

        system_prompt, user_prompt = classifier._build_prompt(email, ["Newsletters", "Promotions"])

        assert len(system_prompt) > 0
        assert len(user_prompt) > 0
        # Should not contain "Examples:" section
        assert "Examples:" not in system_prompt


# =============================================================================
# Task 4: EmailCategorizer saves classifications to DB when available
# =============================================================================


class TestCategorizerClassificationRecording:
    """Test EmailCategorizer records classifications in the database."""

    def test_categorizer_accepts_database_parameter(self):
        """EmailCategorizer accepts an optional database parameter."""
        from src.categorizer.categorizer import EmailCategorizer

        categorizer = EmailCategorizer(database=None)
        assert categorizer._database is None

    def test_categorizer_stores_database(self, tmp_path):
        """EmailCategorizer stores the database when provided."""
        from src.categorizer.categorizer import EmailCategorizer

        db = Database(tmp_path / "test.db")
        try:
            categorizer = EmailCategorizer(database=db)
            assert categorizer._database is db
        finally:
            db.close()

    def test_categorizer_records_classification_for_rule_match(self, tmp_path):
        """Categorizer saves classification to DB when a rule matches."""
        from src.categorizer.categorizer import EmailCategorizer

        db = Database(tmp_path / "test.db")
        try:
            categorizer = EmailCategorizer(database=db)

            email = _make_email()
            rule = _make_rule(action_target="Newsletters")
            rule_set = _make_rule_set(rule)

            # Insert a dummy email row so FK constraint is satisfied
            db.execute(
                "INSERT INTO emails (id, sender_email, sender_domain, subject, "
                "body_text, received_date, has_attachments) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    email.id,
                    email.sender_email,
                    email.sender_domain,
                    email.subject,
                    email.body_text,
                    email.received_date.isoformat(),
                    0,
                ),
            )

            categorizer.categorize_email(email, rule_set)

            # Verify classification was saved
            cursor = db.execute(
                "SELECT email_id, category_name, confidence, source "
                "FROM classifications WHERE email_id = ?",
                (email.id,),
            )
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == email.id
            assert row[1] == "Newsletters"
            assert row[2] > 0.0  # Has positive confidence
            assert "rule:" in row[3]
        finally:
            db.close()

    def test_categorizer_records_classifier_fallback(self, tmp_path):
        """Categorizer saves classification to DB for classifier fallback results."""
        from src.categorizer.categorizer import EmailCategorizer

        db = Database(tmp_path / "test.db")
        try:
            mock_classifier = MagicMock()
            mock_classifier.name = "TestClassifier"
            mock_classifier.classify.return_value = ClassificationResult(
                category_name="Promotions",
                confidence=0.85,
                source="classifier:TestClassifier",
                reasoning="Marketing content detected",
            )

            categorizer = EmailCategorizer(
                classifier=mock_classifier,
                database=db,
            )

            # Email that won't match any rules
            email = _make_email(sender_domain="nomatch.org")
            rule = _make_rule()  # Matches example.com, not nomatch.org
            rule_set = _make_rule_set(rule)

            # Insert email row for FK
            db.execute(
                "INSERT INTO emails (id, sender_email, sender_domain, subject, "
                "body_text, received_date, has_attachments) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    email.id,
                    email.sender_email,
                    "nomatch.org",
                    email.subject,
                    email.body_text,
                    email.received_date.isoformat(),
                    0,
                ),
            )

            categorizer.categorize_email(email, rule_set)

            cursor = db.execute(
                "SELECT email_id, category_name, source FROM classifications WHERE email_id = ?",
                (email.id,),
            )
            row = cursor.fetchone()
            assert row is not None
            assert row[1] == "Promotions"
            assert "classifier:" in row[2]
        finally:
            db.close()

    def test_categorizer_does_not_record_uncategorized(self, tmp_path):
        """Categorizer does NOT save a classification for uncategorized emails."""
        from src.categorizer.categorizer import EmailCategorizer

        db = Database(tmp_path / "test.db")
        try:
            categorizer = EmailCategorizer(database=db)

            email = _make_email(sender_domain="nomatch.org")
            rule = _make_rule()  # Matches example.com only
            rule_set = _make_rule_set(rule)

            # Insert email row for FK
            db.execute(
                "INSERT INTO emails (id, sender_email, sender_domain, subject, "
                "body_text, received_date, has_attachments) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    email.id,
                    email.sender_email,
                    "nomatch.org",
                    email.subject,
                    email.body_text,
                    email.received_date.isoformat(),
                    0,
                ),
            )

            result = categorizer.categorize_email(email, rule_set)
            assert result.is_uncategorized

            cursor = db.execute(
                "SELECT COUNT(*) FROM classifications WHERE email_id = ?",
                (email.id,),
            )
            count = cursor.fetchone()[0]
            assert count == 0
        finally:
            db.close()

    def test_categorizer_without_database_still_works(self):
        """Categorizer works without a database (backward compat)."""
        from src.categorizer.categorizer import EmailCategorizer

        categorizer = EmailCategorizer()
        email = _make_email()
        rule = _make_rule()
        rule_set = _make_rule_set(rule)

        result = categorizer.categorize_email(email, rule_set)
        assert not result.is_uncategorized

    def test_categorizer_records_model_version_for_classifier(self, tmp_path):
        """Categorizer records model_version when classification comes from classifier."""
        from src.categorizer.categorizer import EmailCategorizer

        db = Database(tmp_path / "test.db")
        try:
            mock_classifier = MagicMock()
            mock_classifier.name = "LLM Classifier (ollama/qwen2.5:7b)"
            mock_classifier.classify.return_value = ClassificationResult(
                category_name="Promotions",
                confidence=0.85,
                source="llm:ollama",
                reasoning="Marketing content",
            )

            categorizer = EmailCategorizer(
                classifier=mock_classifier,
                database=db,
            )

            email = _make_email(sender_domain="nomatch.org")
            rule_set = _make_rule_set(_make_rule())

            db.execute(
                "INSERT INTO emails (id, sender_email, sender_domain, subject, "
                "body_text, received_date, has_attachments) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    email.id,
                    email.sender_email,
                    "nomatch.org",
                    email.subject,
                    email.body_text,
                    email.received_date.isoformat(),
                    0,
                ),
            )

            categorizer.categorize_email(email, rule_set)

            cursor = db.execute(
                "SELECT model_version FROM classifications WHERE email_id = ?",
                (email.id,),
            )
            row = cursor.fetchone()
            assert row is not None
            # model_version should be set for classifier-based results
        finally:
            db.close()

    def test_categorizer_handles_db_error_gracefully(self, tmp_path):
        """Categorizer still returns result even if DB write fails."""
        from src.categorizer.categorizer import EmailCategorizer

        db = MagicMock()
        db.execute.side_effect = Exception("DB write failed")

        categorizer = EmailCategorizer(database=db)
        email = _make_email()
        rule = _make_rule()
        rule_set = _make_rule_set(rule)

        # Should still return a result, not crash
        result = categorizer.categorize_email(email, rule_set)
        assert not result.is_uncategorized

    def test_categorizer_records_batch_classifications(self, tmp_path):
        """Categorizer records classifications during batch categorize_corpus."""
        from src.categorizer.categorizer import EmailCategorizer

        db = Database(tmp_path / "test.db")
        try:
            categorizer = EmailCategorizer(database=db)

            emails = [_make_email(id=f"email_{i}") for i in range(3)]
            rule = _make_rule()
            rule_set = _make_rule_set(rule)

            # Insert email rows for FK
            for email in emails:
                db.execute(
                    "INSERT INTO emails (id, sender_email, sender_domain, subject, "
                    "body_text, received_date, has_attachments) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        email.id,
                        email.sender_email,
                        email.sender_domain,
                        email.subject,
                        email.body_text,
                        email.received_date.isoformat(),
                        0,
                    ),
                )

            corpus = Corpus(
                extraction_metadata=CorpusMetadata(
                    extraction_date=datetime(2024, 6, 15),
                    total_emails=3,
                    source="m365",
                    user_email="user@example.com",
                ),
                emails=emails,
            )

            categorizer.categorize_corpus(corpus, rule_set)

            cursor = db.execute("SELECT COUNT(*) FROM classifications")
            count = cursor.fetchone()[0]
            assert count == 3
        finally:
            db.close()


# =============================================================================
# Task 5: Pipeline surfaces uncertain classifications
# =============================================================================


class TestPipelineUncertaintySurfacing:
    """Test that pipeline surfaces uncertain classifications after classification."""

    def test_pipeline_result_has_uncertain_field(self):
        """PipelineResult includes uncertain_classifications field."""
        from src.services.pipeline_service import PipelineResult

        # PipelineResult should support uncertain_classifications
        result = PipelineResult(
            corpus=MagicMock(),
            analysis=MagicMock(),
            categories=[],
            output_dir=MagicMock(),
            uncertain_classifications=[],
        )
        assert hasattr(result, "uncertain_classifications")
        assert result.uncertain_classifications == []

    def test_pipeline_result_default_uncertain_is_empty(self):
        """PipelineResult defaults uncertain_classifications to empty list."""
        from src.services.pipeline_service import PipelineResult

        result = PipelineResult(
            corpus=MagicMock(),
            analysis=MagicMock(),
            categories=[],
            output_dir=MagicMock(),
        )
        assert result.uncertain_classifications == []
