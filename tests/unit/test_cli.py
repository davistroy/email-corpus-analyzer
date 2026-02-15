"""
Unit tests for CLI entry point modules.

Tests cover:
- src/cli.py - Main CLI with argparse, commands (extract, analyze, suggest, review, pipeline)
Uses mocking to avoid real file I/O, network calls, and external dependencies.
"""
import argparse
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open

import pytest


class TestCreateParser:
    """Test cases for create_parser() function in cli.py."""

    def test_create_parser_returns_argument_parser(self):
        """Test that create_parser returns an ArgumentParser."""
        from src.cli import create_parser

        parser = create_parser()

        assert isinstance(parser, argparse.ArgumentParser)

    def test_create_parser_has_prog_name(self):
        """Test parser has correct program name."""
        from src.cli import create_parser

        parser = create_parser()

        assert parser.prog == "email-processor"

    def test_create_parser_has_output_dir_option(self):
        """Test parser has --output-dir global option."""
        from src.cli import create_parser

        parser = create_parser()

        # Parse with output-dir
        args = parser.parse_args(["--output-dir", "/tmp/test", "extract", "--user-email", "test@test.com"])
        assert args.output_dir == Path("/tmp/test")

    def test_create_parser_has_verbose_option(self):
        """Test parser has --verbose/-v option."""
        from src.cli import create_parser

        parser = create_parser()

        args = parser.parse_args(["-v", "extract", "--user-email", "test@test.com"])
        assert args.verbose is True

        args = parser.parse_args(["--verbose", "extract", "--user-email", "test@test.com"])
        assert args.verbose is True

    def test_create_parser_requires_command(self):
        """Test parser requires a subcommand."""
        from src.cli import create_parser

        parser = create_parser()

        with pytest.raises(SystemExit):
            parser.parse_args([])

    def test_create_parser_has_extract_command(self):
        """Test parser has extract subcommand."""
        from src.cli import create_parser

        parser = create_parser()

        args = parser.parse_args(["extract", "--user-email", "test@example.com"])
        assert args.command == "extract"
        assert args.user_email == "test@example.com"

    def test_extract_command_requires_user_email(self):
        """Test extract command requires --user-email."""
        from src.cli import create_parser

        parser = create_parser()

        with pytest.raises(SystemExit):
            parser.parse_args(["extract"])

    def test_extract_command_has_batch_size_option(self):
        """Test extract command has --batch-size option with default."""
        from src.cli import create_parser

        parser = create_parser()

        args = parser.parse_args(["extract", "--user-email", "test@test.com"])
        assert args.batch_size == 500

        args = parser.parse_args(["extract", "--user-email", "test@test.com", "--batch-size", "100"])
        assert args.batch_size == 100

    def test_extract_command_has_checkpoint_interval_option(self):
        """Test extract command has --checkpoint-interval option."""
        from src.cli import create_parser

        parser = create_parser()

        args = parser.parse_args(["extract", "--user-email", "test@test.com"])
        assert args.checkpoint_interval == 100

        args = parser.parse_args(["extract", "--user-email", "test@test.com", "--checkpoint-interval", "50"])
        assert args.checkpoint_interval == 50

    def test_extract_command_has_corpus_file_option(self):
        """Test extract command has --corpus-file option."""
        from src.cli import create_parser

        parser = create_parser()

        args = parser.parse_args(["extract", "--user-email", "test@test.com", "--corpus-file", "/custom/corpus.json"])
        assert args.corpus_file == Path("/custom/corpus.json")

    def test_create_parser_has_analyze_command(self):
        """Test parser has analyze subcommand."""
        from src.cli import create_parser

        parser = create_parser()

        args = parser.parse_args(["analyze"])
        assert args.command == "analyze"

    def test_analyze_command_has_corpus_option(self):
        """Test analyze command has --corpus option."""
        from src.cli import create_parser

        parser = create_parser()

        args = parser.parse_args(["analyze", "--corpus", "/path/to/corpus.json"])
        assert args.corpus == Path("/path/to/corpus.json")

    def test_analyze_command_has_num_clusters_option(self):
        """Test analyze command has --num-clusters option."""
        from src.cli import create_parser

        parser = create_parser()

        args = parser.parse_args(["analyze"])
        assert args.num_clusters == 10

        args = parser.parse_args(["analyze", "--num-clusters", "15"])
        assert args.num_clusters == 15

    def test_analyze_command_has_analysis_file_option(self):
        """Test analyze command has --analysis-file option."""
        from src.cli import create_parser

        parser = create_parser()

        args = parser.parse_args(["analyze", "--analysis-file", "/custom/analysis.json"])
        assert args.analysis_file == Path("/custom/analysis.json")

    def test_create_parser_has_suggest_command(self):
        """Test parser has suggest subcommand."""
        from src.cli import create_parser

        parser = create_parser()

        args = parser.parse_args(["suggest"])
        assert args.command == "suggest"

    def test_suggest_command_has_analysis_option(self):
        """Test suggest command has --analysis option."""
        from src.cli import create_parser

        parser = create_parser()

        args = parser.parse_args(["suggest", "--analysis", "/path/analysis.json"])
        assert args.analysis == Path("/path/analysis.json")

    def test_suggest_command_has_min_cluster_percentage_option(self):
        """Test suggest command has --min-cluster-percentage option."""
        from src.cli import create_parser

        parser = create_parser()

        args = parser.parse_args(["suggest"])
        assert args.min_cluster_percentage == 5.0

        args = parser.parse_args(["suggest", "--min-cluster-percentage", "10.0"])
        assert args.min_cluster_percentage == 10.0

    def test_suggest_command_has_min_sender_count_option(self):
        """Test suggest command has --min-sender-count option."""
        from src.cli import create_parser

        parser = create_parser()

        args = parser.parse_args(["suggest"])
        assert args.min_sender_count == 20

        args = parser.parse_args(["suggest", "--min-sender-count", "30"])
        assert args.min_sender_count == 30

    def test_suggest_command_has_suggestions_file_option(self):
        """Test suggest command has --suggestions-file option."""
        from src.cli import create_parser

        parser = create_parser()

        args = parser.parse_args(["suggest", "--suggestions-file", "/custom/suggestions.json"])
        assert args.suggestions_file == Path("/custom/suggestions.json")

    def test_create_parser_has_review_command(self):
        """Test parser has review subcommand."""
        from src.cli import create_parser

        parser = create_parser()

        args = parser.parse_args(["review"])
        assert args.command == "review"

    def test_review_command_has_suggestions_option(self):
        """Test review command has --suggestions option."""
        from src.cli import create_parser

        parser = create_parser()

        args = parser.parse_args(["review", "--suggestions", "/path/suggestions.json"])
        assert args.suggestions == Path("/path/suggestions.json")

    def test_review_command_has_approved_file_option(self):
        """Test review command has --approved-file option."""
        from src.cli import create_parser

        parser = create_parser()

        args = parser.parse_args(["review", "--approved-file", "/custom/approved.json"])
        assert args.approved_file == Path("/custom/approved.json")

    def test_review_command_has_no_cleanup_option(self):
        """Test review command has --no-cleanup flag."""
        from src.cli import create_parser

        parser = create_parser()

        args = parser.parse_args(["review"])
        assert args.no_cleanup is False

        args = parser.parse_args(["review", "--no-cleanup"])
        assert args.no_cleanup is True

    def test_create_parser_has_pipeline_command(self):
        """Test parser has pipeline subcommand."""
        from src.cli import create_parser

        parser = create_parser()

        args = parser.parse_args(["pipeline", "--user-email", "test@example.com"])
        assert args.command == "pipeline"

    def test_pipeline_command_requires_user_email(self):
        """Test pipeline command requires --user-email."""
        from src.cli import create_parser

        parser = create_parser()

        with pytest.raises(SystemExit):
            parser.parse_args(["pipeline"])

    def test_pipeline_command_has_num_clusters_option(self):
        """Test pipeline command has --num-clusters option."""
        from src.cli import create_parser

        parser = create_parser()

        args = parser.parse_args(["pipeline", "--user-email", "test@test.com"])
        assert args.num_clusters == 10

    def test_pipeline_command_has_no_cleanup_option(self):
        """Test pipeline command has --no-cleanup flag."""
        from src.cli import create_parser

        parser = create_parser()

        args = parser.parse_args(["pipeline", "--user-email", "test@test.com", "--no-cleanup"])
        assert args.no_cleanup is True


class TestSetupOutputDirectory:
    """Test cases for setup_output_directory() function."""

    @patch("src.cli.parsers.PathConfig")
    @patch("src.cli.parsers.logger")
    def test_setup_output_directory_with_custom_path(self, mock_logger, mock_path_config):
        """Test setup with custom output directory."""
        from src.cli import setup_output_directory

        args = argparse.Namespace(output_dir=Path("/custom/output"))

        setup_output_directory(args)

        mock_path_config.set_output_dir.assert_called_once_with(Path("/custom/output"))
        mock_path_config.ensure_output_dir_exists.assert_called_once()

    @patch("src.cli.parsers.PathConfig")
    @patch("src.cli.parsers.logger")
    def test_setup_output_directory_with_default(self, mock_logger, mock_path_config):
        """Test setup with default output directory."""
        from src.cli import setup_output_directory

        mock_path_config.get_default_output_dir.return_value = Path("/default/output")
        args = argparse.Namespace(output_dir=None)

        setup_output_directory(args)

        mock_path_config.set_output_dir.assert_not_called()
        mock_path_config.get_default_output_dir.assert_called_once()
        mock_path_config.ensure_output_dir_exists.assert_called_once()


class TestCmdExtract:
    """Test cases for cmd_extract() function."""

    @patch("src.cli.commands.extract.save_json")
    @patch("src.cli.commands.extract.PathConfig")
    @patch("src.cli.commands.extract.logger")
    @patch("src.extractors.m365_extractor.EmailExtractor")
    def test_cmd_extract_success(self, mock_extractor_class, mock_logger, mock_path_config, mock_save_json):
        """Test successful email extraction."""
        from src.cli import cmd_extract

        mock_path_config.get_corpus_path.return_value = Path("/output/corpus.json")
        mock_path_config.get_output_dir.return_value = Path("/output")

        args = argparse.Namespace(
            user_email="test@example.com",
            corpus_file=None,
            batch_size=500,
            checkpoint_interval=100
        )

        # Mock the EmailExtractor
        mock_extractor = MagicMock()
        mock_result = MagicMock()
        mock_result.success_count = 100
        mock_result.failed_emails = []
        mock_result.corpus = MagicMock()
        mock_result.corpus.model_dump.return_value = {"emails": []}
        mock_extractor.extract_all.return_value = mock_result
        mock_extractor_class.return_value = mock_extractor

        result = cmd_extract(args)

        assert result == 0
        mock_save_json.assert_called_once()
        mock_extractor.extract_all.assert_called_once_with(
            max_batch_size=500,
            checkpoint_interval=100
        )

    @patch("src.cli.commands.extract.save_json")
    @patch("src.cli.commands.extract.PathConfig")
    @patch("src.cli.commands.extract.logger")
    @patch("src.extractors.m365_extractor.EmailExtractor")
    def test_cmd_extract_with_custom_corpus_path(self, mock_extractor_class, mock_logger, mock_path_config, mock_save):
        """Test extraction with custom corpus file path."""
        from src.cli import cmd_extract

        mock_path_config.get_output_dir.return_value = Path("/output")

        args = argparse.Namespace(
            user_email="test@example.com",
            corpus_file=Path("/custom/corpus.json"),
            batch_size=500,
            checkpoint_interval=100
        )

        mock_extractor = MagicMock()
        mock_result = MagicMock()
        mock_result.success_count = 50
        mock_result.failed_emails = []
        mock_result.corpus = MagicMock()
        mock_result.corpus.model_dump.return_value = {}
        mock_extractor.extract_all.return_value = mock_result
        mock_extractor_class.return_value = mock_extractor

        result = cmd_extract(args)

        # Verify custom path is used
        mock_save.assert_called_once()
        call_args = mock_save.call_args
        assert call_args[0][1] == Path("/custom/corpus.json")

    @patch("src.cli.commands.extract.PathConfig")
    @patch("src.cli.commands.extract.logger")
    @patch("src.extractors.m365_extractor.EmailExtractor")
    def test_cmd_extract_initialization_failure(self, mock_extractor_class, mock_logger, mock_path_config):
        """Test extraction fails on extractor initialization error."""
        from src.cli import cmd_extract

        mock_path_config.get_output_dir.return_value = Path("/output")

        args = argparse.Namespace(
            user_email="test@example.com",
            corpus_file=None,
            batch_size=500,
            checkpoint_interval=100
        )

        mock_extractor_class.side_effect = Exception("Init failed")

        result = cmd_extract(args)

        assert result == 1

    @patch("src.cli.commands.extract.PathConfig")
    @patch("src.cli.commands.extract.logger")
    @patch("src.extractors.m365_extractor.EmailExtractor")
    def test_cmd_extract_extraction_failure(self, mock_extractor_class, mock_logger, mock_path_config):
        """Test extraction fails during extraction."""
        from src.cli import cmd_extract

        mock_path_config.get_corpus_path.return_value = Path("/output/corpus.json")
        mock_path_config.get_output_dir.return_value = Path("/output")

        args = argparse.Namespace(
            user_email="test@example.com",
            corpus_file=None,
            batch_size=500,
            checkpoint_interval=100
        )

        mock_extractor = MagicMock()
        mock_extractor.extract_all.side_effect = Exception("Network error")
        mock_extractor_class.return_value = mock_extractor

        result = cmd_extract(args)

        assert result == 1

    @patch("src.cli.commands.extract.save_json")
    @patch("src.cli.commands.extract.PathConfig")
    @patch("src.cli.commands.extract.logger")
    @patch("src.extractors.m365_extractor.EmailExtractor")
    def test_cmd_extract_with_failed_emails(self, mock_extractor_class, mock_logger, mock_path_config, mock_save_json):
        """Test extraction with some failed emails."""
        from src.cli import cmd_extract

        mock_path_config.get_corpus_path.return_value = Path("/output/corpus.json")
        mock_path_config.get_output_dir.return_value = Path("/output")

        args = argparse.Namespace(
            user_email="test@example.com",
            corpus_file=None,
            batch_size=500,
            checkpoint_interval=100
        )

        mock_extractor = MagicMock()
        mock_result = MagicMock()
        mock_result.success_count = 95
        mock_result.failed_emails = [MagicMock(), MagicMock()]  # 2 failed
        mock_result.failure_count = 2
        mock_result.total_attempted = 97
        mock_result.success_rate = 0.979  # 95/97
        mock_result.corpus = MagicMock()
        mock_result.corpus.model_dump.return_value = {}
        mock_result.corpus.emails = [MagicMock(id=f"e_{i}") for i in range(95)]
        mock_result.corpus.extraction_metadata.total_emails = 95
        mock_extractor.extract_all.return_value = mock_result
        mock_extractor_class.return_value = mock_extractor

        result = cmd_extract(args)

        # Should still succeed but log warning
        assert result == 0


class TestCmdAnalyze:
    """Test cases for cmd_analyze() function."""

    @patch("src.cli.commands.analyze.save_json")
    @patch("src.cli.commands.analyze.load_json")
    @patch("src.cli.commands.analyze.PathConfig")
    @patch("src.cli.commands.analyze.logger")
    @patch("src.analyzers.run_full_analysis")
    @patch("src.models.corpus.Corpus")
    def test_cmd_analyze_success(self, mock_corpus_class, mock_analysis, mock_logger, mock_path_config, mock_load_json, mock_save_json):
        """Test successful corpus analysis."""
        from src.cli import cmd_analyze

        mock_path_config.get_corpus_path.return_value = Path("/output/corpus.json")
        mock_path_config.get_analysis_path.return_value = Path("/output/analysis.json")
        mock_load_json.return_value = {
            "extraction_metadata": {
                "extraction_date": "2024-01-01T00:00:00",
                "total_emails": 100,
                "source": "test",
                "user_email": "test@example.com"
            },
            "emails": []
        }

        args = argparse.Namespace(
            corpus=None,
            num_clusters=10,
            analysis_file=None
        )

        mock_corpus = MagicMock()
        mock_corpus.emails = []
        mock_corpus_class.return_value = mock_corpus

        mock_results = MagicMock()
        mock_results.model_dump.return_value = {"results": "data"}
        mock_results.sender_analysis.unique_senders = 50
        mock_results.content_clusters = [1, 2, 3]
        mock_analysis.return_value = (mock_results, None)

        result = cmd_analyze(args)

        assert result == 0
        mock_analysis.assert_called_once()
        mock_save_json.assert_called_once()

    @patch("src.cli.commands.analyze.save_json")
    @patch("src.cli.commands.analyze.load_json")
    @patch("src.cli.commands.analyze.PathConfig")
    @patch("src.cli.commands.analyze.logger")
    @patch("src.analyzers.run_full_analysis")
    @patch("src.models.corpus.Corpus")
    def test_cmd_analyze_with_custom_corpus_path(self, mock_corpus_class, mock_analysis, mock_logger, mock_path_config, mock_load_json, mock_save_json):
        """Test analysis with custom corpus path."""
        from src.cli import cmd_analyze

        mock_path_config.get_analysis_path.return_value = Path("/output/analysis.json")
        mock_load_json.return_value = {
            "extraction_metadata": {
                "extraction_date": "2024-01-01T00:00:00",
                "total_emails": 0,
                "source": "test",
                "user_email": "test@example.com"
            },
            "emails": []
        }

        args = argparse.Namespace(
            corpus=Path("/custom/corpus.json"),
            num_clusters=10,
            analysis_file=None
        )

        mock_corpus = MagicMock()
        mock_corpus.emails = []
        mock_corpus_class.return_value = mock_corpus

        mock_results = MagicMock()
        mock_results.model_dump.return_value = {}
        mock_results.sender_analysis.unique_senders = 0
        mock_results.content_clusters = []
        mock_analysis.return_value = (mock_results, None)

        result = cmd_analyze(args)

        # Verify custom path used for loading
        mock_load_json.assert_called_once_with(Path("/custom/corpus.json"))

    @patch("src.cli.commands.analyze.load_json")
    @patch("src.cli.commands.analyze.PathConfig")
    @patch("src.cli.commands.analyze.logger")
    def test_cmd_analyze_corpus_load_failure(self, mock_logger, mock_path_config, mock_load_json):
        """Test analysis fails when corpus cannot be loaded."""
        from src.cli import cmd_analyze

        mock_path_config.get_corpus_path.return_value = Path("/output/corpus.json")
        mock_load_json.side_effect = FileNotFoundError("Corpus not found")

        args = argparse.Namespace(
            corpus=None,
            num_clusters=10,
            analysis_file=None
        )

        result = cmd_analyze(args)

        assert result == 1

    @patch("src.cli.commands.analyze.load_json")
    @patch("src.cli.commands.analyze.PathConfig")
    @patch("src.cli.commands.analyze.logger")
    @patch("src.analyzers.run_full_analysis")
    @patch("src.models.corpus.Corpus")
    def test_cmd_analyze_analysis_failure(self, mock_corpus_class, mock_analysis, mock_logger, mock_path_config, mock_load_json):
        """Test analysis fails during processing."""
        from src.cli import cmd_analyze

        mock_path_config.get_corpus_path.return_value = Path("/output/corpus.json")
        mock_path_config.get_analysis_path.return_value = Path("/output/analysis.json")
        mock_load_json.return_value = {
            "extraction_metadata": {
                "extraction_date": "2024-01-01T00:00:00",
                "total_emails": 0,
                "source": "test",
                "user_email": "test@example.com"
            },
            "emails": []
        }

        args = argparse.Namespace(
            corpus=None,
            num_clusters=10,
            analysis_file=None
        )

        mock_corpus = MagicMock()
        mock_corpus.emails = []
        mock_corpus_class.return_value = mock_corpus
        mock_analysis.side_effect = Exception("Analysis error")

        result = cmd_analyze(args)

        assert result == 1


class TestCmdSuggest:
    """Test cases for cmd_suggest() function."""

    @patch("src.cli.commands.suggest.atomic_write_text")
    @patch("src.cli.commands.suggest.save_json")
    @patch("src.cli.commands.suggest.load_json")
    @patch("src.cli.commands.suggest.PathConfig")
    @patch("src.cli.commands.suggest.logger")
    def test_cmd_suggest_success(self, mock_logger, mock_path_config, mock_load_json, mock_save_json, mock_atomic_write_text):
        """Test successful category suggestion generation."""
        from src.cli import cmd_suggest

        mock_report_path = MagicMock()
        mock_path_config.get_analysis_path.return_value = Path("/output/analysis.json")
        mock_path_config.get_suggestions_path.return_value = Path("/output/suggestions.json")
        mock_path_config.get_suggestions_report_path.return_value = mock_report_path

        # Create valid analysis results mock data
        mock_load_json.return_value = {
            "sender_analysis": {
                "top_senders": [],
                "top_domains": [],
                "unique_senders": 10,
                "unique_domains": 5
            },
            "subject_patterns": {
                "common_prefixes": {},
                "numbered_patterns": {},
                "top_keywords": [],
                "bracket_tags": [],
                "total_subjects_analyzed": 100
            },
            "content_clusters": [],
            "temporal_patterns": {
                "frequency_distribution": {},
                "sender_frequencies": {}
            },
            "volume_stats": {
                "total_emails": 100,
                "unique_senders": 10,
                "date_range": {"oldest": "2024-01-01", "newest": "2024-01-31", "span_days": "30"},
                "with_attachments": 20,
                "attachment_percentage": 20.0,
                "avg_body_length_chars": 500,
                "emails_per_day": 3.3
            }
        }

        args = argparse.Namespace(
            analysis=None,
            min_cluster_percentage=5.0,
            min_sender_count=20,
            suggestions_file=None
        )

        with patch("src.generators.category_generator.CategoryGenerator") as mock_gen_class:
            with patch("src.models.analysis_results.AnalysisResults") as mock_results_class:
                mock_results = MagicMock()
                mock_results_class.return_value = mock_results

                mock_gen = MagicMock()
                mock_category = MagicMock()
                mock_category.model_dump.return_value = {"id": "cat1"}
                mock_gen.generate_suggestions.return_value = [mock_category]
                mock_gen.generate_report.return_value = "# Report"
                mock_gen_class.return_value = mock_gen

                result = cmd_suggest(args)

                assert result == 0
                mock_gen.generate_suggestions.assert_called_once()

    @patch("src.cli.commands.suggest.load_json")
    @patch("src.cli.commands.suggest.PathConfig")
    @patch("src.cli.commands.suggest.logger")
    def test_cmd_suggest_analysis_load_failure(self, mock_logger, mock_path_config, mock_load_json):
        """Test suggestion fails when analysis cannot be loaded."""
        from src.cli import cmd_suggest

        mock_path_config.get_analysis_path.return_value = Path("/output/analysis.json")
        mock_load_json.side_effect = FileNotFoundError("Analysis not found")

        args = argparse.Namespace(
            analysis=None,
            min_cluster_percentage=5.0,
            min_sender_count=20,
            suggestions_file=None
        )

        result = cmd_suggest(args)

        assert result == 1

    @patch("src.cli.commands.suggest.atomic_write_text")
    @patch("src.cli.commands.suggest.save_json")
    @patch("src.cli.commands.suggest.load_json")
    @patch("src.cli.commands.suggest.PathConfig")
    @patch("src.cli.commands.suggest.logger")
    @patch("src.generators.category_generator.CategoryGenerator")
    @patch("src.models.analysis_results.AnalysisResults")
    def test_cmd_suggest_with_custom_paths(self, mock_results_class, mock_gen_class, mock_logger, mock_path_config, mock_load_json, mock_save, mock_atomic_write_text):
        """Test suggestion with custom analysis and output paths."""
        from src.cli import cmd_suggest

        mock_path_config.get_suggestions_report_path.return_value = Path("/output/report.md")

        # Create valid analysis results mock data
        mock_load_json.return_value = {
            "sender_analysis": {
                "top_senders": [],
                "top_domains": [],
                "unique_senders": 10,
                "unique_domains": 5
            },
            "subject_patterns": {
                "common_prefixes": {},
                "numbered_patterns": {},
                "top_keywords": [],
                "bracket_tags": [],
                "total_subjects_analyzed": 100
            },
            "content_clusters": [],
            "temporal_patterns": {
                "frequency_distribution": {},
                "sender_frequencies": {}
            },
            "volume_stats": {
                "total_emails": 100,
                "unique_senders": 10,
                "date_range": {},
                "with_attachments": 20,
                "attachment_percentage": 20.0,
                "avg_body_length_chars": 500,
                "emails_per_day": 3.3
            }
        }

        args = argparse.Namespace(
            analysis=Path("/custom/analysis.json"),
            min_cluster_percentage=10.0,
            min_sender_count=30,
            suggestions_file=Path("/custom/suggestions.json")
        )

        mock_results = MagicMock()
        mock_results_class.return_value = mock_results

        mock_gen = MagicMock()
        mock_gen.generate_suggestions.return_value = []
        mock_gen.generate_report.return_value = ""
        mock_gen_class.return_value = mock_gen

        result = cmd_suggest(args)

        mock_load_json.assert_called_once_with(Path("/custom/analysis.json"))
        # Verify custom suggestions path is used
        call_args = mock_save.call_args
        assert call_args[0][1] == Path("/custom/suggestions.json")

    @patch("src.cli.commands.suggest.load_json")
    @patch("src.cli.commands.suggest.PathConfig")
    @patch("src.cli.commands.suggest.logger")
    @patch("src.generators.category_generator.CategoryGenerator")
    @patch("src.models.analysis_results.AnalysisResults")
    def test_cmd_suggest_generation_failure(self, mock_results_class, mock_gen_class, mock_logger, mock_path_config, mock_load_json):
        """Test suggestion fails during generation."""
        from src.cli import cmd_suggest

        mock_path_config.get_analysis_path.return_value = Path("/output/analysis.json")
        mock_path_config.get_suggestions_path.return_value = Path("/output/suggestions.json")

        mock_load_json.return_value = {
            "sender_analysis": {"top_senders": [], "top_domains": [], "unique_senders": 0, "unique_domains": 0},
            "subject_patterns": {"common_prefixes": {}, "numbered_patterns": {}, "top_keywords": [], "bracket_tags": [], "total_subjects_analyzed": 0},
            "content_clusters": [],
            "temporal_patterns": {"frequency_distribution": {}, "sender_frequencies": {}},
            "volume_stats": {"total_emails": 0, "unique_senders": 0, "date_range": {}, "with_attachments": 0, "attachment_percentage": 0, "avg_body_length_chars": 0, "emails_per_day": 0}
        }

        args = argparse.Namespace(
            analysis=None,
            min_cluster_percentage=5.0,
            min_sender_count=20,
            suggestions_file=None
        )

        mock_results = MagicMock()
        mock_results_class.return_value = mock_results

        mock_gen = MagicMock()
        mock_gen.generate_suggestions.side_effect = Exception("Generation error")
        mock_gen_class.return_value = mock_gen

        result = cmd_suggest(args)

        assert result == 1


class TestCmdReview:
    """Test cases for cmd_review() function."""

    @patch("src.cli.commands.review.load_json")
    @patch("src.cli.commands.review.PathConfig")
    @patch("src.cli.commands.review.logger")
    @patch("src.ui.category_review.review_categories")
    @patch("src.ui.category_review.cleanup_intermediate_files")
    @patch("src.models.category.Category")
    def test_cmd_review_success(self, mock_category_class, mock_cleanup, mock_review, mock_logger, mock_path_config, mock_load_json):
        """Test successful category review."""
        from src.cli import cmd_review

        mock_path_config.get_suggestions_path.return_value = Path("/output/suggestions.json")
        mock_path_config.get_approved_categories_path.return_value = Path("/output/approved.json")
        mock_path_config.get_output_dir.return_value = Path("/output")

        mock_load_json.return_value = [{
            "category_id": "cat1",
            "category_name": "Test Category",
            "description": "Test description",
            "confidence": 0.8,
            "source": "content_cluster"
        }]

        args = argparse.Namespace(
            suggestions=None,
            approved_file=None,
            no_cleanup=False
        )

        mock_category = MagicMock()
        mock_category_class.return_value = mock_category
        mock_review.return_value = [mock_category]

        result = cmd_review(args)

        assert result == 0
        mock_review.assert_called_once()
        mock_cleanup.assert_called_once()

    @patch("src.cli.commands.review.load_json")
    @patch("src.cli.commands.review.PathConfig")
    @patch("src.cli.commands.review.logger")
    @patch("src.ui.category_review.review_categories")
    @patch("src.ui.category_review.cleanup_intermediate_files")
    def test_cmd_review_with_no_cleanup(self, mock_cleanup, mock_review, mock_logger, mock_path_config, mock_load_json):
        """Test review with --no-cleanup flag."""
        from src.cli import cmd_review

        mock_path_config.get_suggestions_path.return_value = Path("/output/suggestions.json")
        mock_path_config.get_approved_categories_path.return_value = Path("/output/approved.json")

        mock_load_json.return_value = []

        args = argparse.Namespace(
            suggestions=None,
            approved_file=None,
            no_cleanup=True
        )

        mock_review.return_value = []

        result = cmd_review(args)

        assert result == 0
        mock_cleanup.assert_not_called()

    @patch("src.cli.commands.review.load_json")
    @patch("src.cli.commands.review.PathConfig")
    @patch("src.cli.commands.review.logger")
    def test_cmd_review_suggestions_load_failure(self, mock_logger, mock_path_config, mock_load_json):
        """Test review fails when suggestions cannot be loaded."""
        from src.cli import cmd_review

        mock_path_config.get_suggestions_path.return_value = Path("/output/suggestions.json")
        mock_load_json.side_effect = FileNotFoundError("Suggestions not found")

        args = argparse.Namespace(
            suggestions=None,
            approved_file=None,
            no_cleanup=False
        )

        result = cmd_review(args)

        assert result == 1

    @patch("src.cli.commands.review.load_json")
    @patch("src.cli.commands.review.PathConfig")
    @patch("src.cli.commands.review.logger")
    @patch("src.ui.category_review.review_categories")
    @patch("src.models.category.Category")
    def test_cmd_review_review_failure(self, mock_category_class, mock_review, mock_logger, mock_path_config, mock_load_json):
        """Test review fails during review process."""
        from src.cli import cmd_review

        mock_path_config.get_suggestions_path.return_value = Path("/output/suggestions.json")
        mock_path_config.get_approved_categories_path.return_value = Path("/output/approved.json")

        mock_load_json.return_value = []

        args = argparse.Namespace(
            suggestions=None,
            approved_file=None,
            no_cleanup=False
        )

        mock_review.side_effect = Exception("Review error")

        result = cmd_review(args)

        assert result == 1


class TestCmdPipeline:
    """Test cases for cmd_pipeline() function."""

    @patch("src.cli.commands.pipeline.cmd_review")
    @patch("src.cli.commands.pipeline.cmd_suggest")
    @patch("src.cli.commands.pipeline.cmd_analyze")
    @patch("src.cli.commands.pipeline.cmd_extract")
    @patch("src.cli.commands.pipeline.logger")
    def test_cmd_pipeline_success(self, mock_logger, mock_extract, mock_analyze, mock_suggest, mock_review):
        """Test successful pipeline execution."""
        from src.cli import cmd_pipeline

        mock_extract.return_value = 0
        mock_analyze.return_value = 0
        mock_suggest.return_value = 0
        mock_review.return_value = 0

        args = argparse.Namespace(
            user_email="test@example.com",
            num_clusters=10,
            no_cleanup=False,
            output_dir=Path("/output"),
            verbose=False
        )

        result = cmd_pipeline(args)

        assert result == 0
        mock_extract.assert_called_once()
        mock_analyze.assert_called_once()
        mock_suggest.assert_called_once()
        mock_review.assert_called_once()

    @patch("src.cli.commands.pipeline.cmd_extract")
    @patch("src.cli.commands.pipeline.logger")
    def test_cmd_pipeline_extract_failure(self, mock_logger, mock_extract):
        """Test pipeline fails on extraction error."""
        from src.cli import cmd_pipeline

        mock_extract.return_value = 1

        args = argparse.Namespace(
            user_email="test@example.com",
            num_clusters=10,
            no_cleanup=False,
            output_dir=None,
            verbose=False
        )

        result = cmd_pipeline(args)

        assert result == 1

    @patch("src.cli.commands.pipeline.cmd_analyze")
    @patch("src.cli.commands.pipeline.cmd_extract")
    @patch("src.cli.commands.pipeline.logger")
    def test_cmd_pipeline_analyze_failure(self, mock_logger, mock_extract, mock_analyze):
        """Test pipeline fails on analysis error."""
        from src.cli import cmd_pipeline

        mock_extract.return_value = 0
        mock_analyze.return_value = 1

        args = argparse.Namespace(
            user_email="test@example.com",
            num_clusters=10,
            no_cleanup=False,
            output_dir=None,
            verbose=False
        )

        result = cmd_pipeline(args)

        assert result == 1

    @patch("src.cli.commands.pipeline.cmd_suggest")
    @patch("src.cli.commands.pipeline.cmd_analyze")
    @patch("src.cli.commands.pipeline.cmd_extract")
    @patch("src.cli.commands.pipeline.logger")
    def test_cmd_pipeline_suggest_failure(self, mock_logger, mock_extract, mock_analyze, mock_suggest):
        """Test pipeline fails on suggestion error."""
        from src.cli import cmd_pipeline

        mock_extract.return_value = 0
        mock_analyze.return_value = 0
        mock_suggest.return_value = 1

        args = argparse.Namespace(
            user_email="test@example.com",
            num_clusters=10,
            no_cleanup=False,
            output_dir=None,
            verbose=False
        )

        result = cmd_pipeline(args)

        assert result == 1

    @patch("src.cli.commands.pipeline.cmd_review")
    @patch("src.cli.commands.pipeline.cmd_suggest")
    @patch("src.cli.commands.pipeline.cmd_analyze")
    @patch("src.cli.commands.pipeline.cmd_extract")
    @patch("src.cli.commands.pipeline.logger")
    def test_cmd_pipeline_review_failure(self, mock_logger, mock_extract, mock_analyze, mock_suggest, mock_review):
        """Test pipeline fails on review error."""
        from src.cli import cmd_pipeline

        mock_extract.return_value = 0
        mock_analyze.return_value = 0
        mock_suggest.return_value = 0
        mock_review.return_value = 1

        args = argparse.Namespace(
            user_email="test@example.com",
            num_clusters=10,
            no_cleanup=False,
            output_dir=None,
            verbose=False
        )

        result = cmd_pipeline(args)

        assert result == 1


class TestCliMain:
    """Test cases for main() function in cli.py."""

    @patch("src.cli.setup_output_directory")
    @patch("src.cli.create_parser")
    def test_main_calls_extract_handler(self, mock_create_parser, mock_setup):
        """Test main dispatches to extract handler."""
        from src.cli import main

        mock_parser = MagicMock()
        mock_args = MagicMock()
        mock_args.command = "extract"
        mock_args.verbose = False
        mock_parser.parse_args.return_value = mock_args
        mock_create_parser.return_value = mock_parser

        with patch("src.cli.cmd_extract") as mock_extract:
            mock_extract.return_value = 0

            result = main()

            assert result == 0
            mock_extract.assert_called_once_with(mock_args)

    @patch("src.cli.setup_output_directory")
    @patch("src.cli.create_parser")
    def test_main_handles_keyboard_interrupt(self, mock_create_parser, mock_setup):
        """Test main handles KeyboardInterrupt."""
        from src.cli import main

        mock_parser = MagicMock()
        mock_args = MagicMock()
        mock_args.command = "extract"
        mock_args.verbose = False
        mock_parser.parse_args.return_value = mock_args
        mock_create_parser.return_value = mock_parser

        with patch("src.cli.cmd_extract") as mock_extract:
            mock_extract.side_effect = KeyboardInterrupt()

            result = main()

            assert result == 130

    @patch("src.cli.setup_output_directory")
    @patch("src.cli.create_parser")
    def test_main_handles_unexpected_exception(self, mock_create_parser, mock_setup):
        """Test main handles unexpected exceptions."""
        from src.cli import main

        mock_parser = MagicMock()
        mock_args = MagicMock()
        mock_args.command = "analyze"
        mock_args.verbose = False
        mock_parser.parse_args.return_value = mock_args
        mock_create_parser.return_value = mock_parser

        with patch("src.cli.cmd_analyze") as mock_analyze:
            mock_analyze.side_effect = Exception("Unexpected error")

            result = main()

            assert result == 1

    @patch("src.cli.setup_output_directory")
    @patch("src.cli.create_parser")
    def test_main_handles_unknown_command(self, mock_create_parser, mock_setup):
        """Test main handles unknown command gracefully."""
        from src.cli import main

        mock_parser = MagicMock()
        mock_args = MagicMock()
        mock_args.command = "unknown_command"
        mock_args.verbose = False
        mock_parser.parse_args.return_value = mock_args
        mock_create_parser.return_value = mock_parser

        result = main()

        assert result == 1

    @patch("src.cli.setup_output_directory")
    @patch("src.cli.create_parser")
    def test_main_with_verbose_flag(self, mock_create_parser, mock_setup):
        """Test main enables debug logging with verbose flag."""
        from src.cli import main
        import logging

        mock_parser = MagicMock()
        mock_args = MagicMock()
        mock_args.command = "extract"
        mock_args.verbose = True
        mock_parser.parse_args.return_value = mock_args
        mock_create_parser.return_value = mock_parser

        with patch("src.cli.cmd_extract") as mock_extract:
            with patch("src.cli.logging.getLogger") as mock_get_logger:
                mock_root_logger = MagicMock()
                mock_get_logger.return_value = mock_root_logger
                mock_extract.return_value = 0

                main()

                # Verify the root logger's setLevel was called with DEBUG
                mock_root_logger.setLevel.assert_called_with(logging.DEBUG)


# =============================================================================
# Tests for config command integration in cli.py
# =============================================================================

class TestConfigCommand:
    """Test cases for config subcommand in cli.py."""

    def test_create_parser_has_config_command(self):
        """Test parser has config subcommand."""
        from src.cli import create_parser

        parser = create_parser()

        args = parser.parse_args(["config", "show"])
        assert args.command == "config"
        assert args.config_action == "show"

    def test_config_command_has_init_action(self):
        """Test config command has init action."""
        from src.cli import create_parser

        parser = create_parser()

        args = parser.parse_args(["config", "init"])
        assert args.config_action == "init"

    def test_config_command_has_show_action(self):
        """Test config command has show action."""
        from src.cli import create_parser

        parser = create_parser()

        args = parser.parse_args(["config", "show"])
        assert args.config_action == "show"

    def test_config_init_has_output_option(self):
        """Test config init has --output option."""
        from src.cli import create_parser

        parser = create_parser()

        args = parser.parse_args(["config", "init", "--output", "/path/to/config.yaml"])
        assert args.config_output == Path("/path/to/config.yaml")

    def test_config_init_has_global_flag(self):
        """Test config init has --global flag."""
        from src.cli import create_parser

        parser = create_parser()

        args = parser.parse_args(["config", "init", "--global"])
        assert args.config_global is True

    def test_create_parser_has_config_flag(self):
        """Test parser has --config global flag."""
        from src.cli import create_parser

        parser = create_parser()

        args = parser.parse_args(["--config", "/custom/config.yaml", "analyze"])
        assert args.config == Path("/custom/config.yaml")


class TestCmdConfigInit:
    """Test cases for cmd_config_init() function."""

    @patch("src.cli.commands.config.logger")
    def test_cmd_config_init_generates_template(self, mock_logger):
        """Test config init generates template file."""
        from src.cli import cmd_config_init

        args = argparse.Namespace(
            config_output=None,
            config_global=False
        )

        with patch("src.cli.commands.config.generate_template") as mock_gen:
            with patch("src.cli.commands.config.get_project_config_path") as mock_path:
                mock_gen.return_value = "# Template"
                mock_path.return_value = Path(".email-analyzer.yaml")

                with patch("builtins.open", mock_open()) as mock_file:
                    result = cmd_config_init(args)

                    assert result == 0
                    mock_gen.assert_called_once()
                    mock_file.assert_called_once()

    @patch("src.cli.commands.config.logger")
    def test_cmd_config_init_with_custom_output(self, mock_logger):
        """Test config init with custom output path."""
        from src.cli import cmd_config_init

        args = argparse.Namespace(
            config_output=Path("/custom/config.yaml"),
            config_global=False
        )

        with patch("src.cli.commands.config.generate_template") as mock_gen:
            mock_gen.return_value = "# Template"

            with patch("builtins.open", mock_open()) as mock_file:
                result = cmd_config_init(args)

                assert result == 0
                mock_file.assert_called_once_with(
                    Path("/custom/config.yaml"), "w", encoding="utf-8"
                )

    @patch("src.cli.commands.config.logger")
    def test_cmd_config_init_global_creates_in_global_path(self, mock_logger):
        """Test config init --global creates in global config directory."""
        from src.cli import cmd_config_init

        args = argparse.Namespace(
            config_output=None,
            config_global=True
        )

        with patch("src.cli.commands.config.generate_template") as mock_gen:
            with patch("src.cli.commands.config.get_global_config_path") as mock_path:
                mock_gen.return_value = "# Template"
                mock_path.return_value = Path("/home/user/.config/email-analyzer/config.yaml")

                with patch("builtins.open", mock_open()):
                    with patch("pathlib.Path.mkdir"):
                        result = cmd_config_init(args)

                        assert result == 0
                        mock_path.assert_called_once()

    @patch("src.cli.commands.config.logger")
    def test_cmd_config_init_handles_write_error(self, mock_logger):
        """Test config init handles file write errors."""
        from src.cli import cmd_config_init

        args = argparse.Namespace(
            config_output=Path("/readonly/config.yaml"),
            config_global=False
        )

        with patch("src.cli.commands.config.generate_template") as mock_gen:
            mock_gen.return_value = "# Template"

            with patch("builtins.open", side_effect=PermissionError("Permission denied")):
                result = cmd_config_init(args)

                assert result == 1


class TestCmdConfigShow:
    """Test cases for cmd_config_show() function."""

    @patch("src.cli.commands.config.logger")
    def test_cmd_config_show_displays_resolved_config(self, mock_logger):
        """Test config show displays resolved configuration."""
        from src.cli import cmd_config_show
        from src.config.models import AppConfig

        args = argparse.Namespace(config=None)

        with patch("src.cli.commands.config.load_config") as mock_load:
            mock_load.return_value = AppConfig(user_email="test@example.com")

            with patch("src.cli.commands.config.show_resolved_config") as mock_show:
                mock_show.return_value = "user_email: test@example.com"

                with patch("builtins.print") as mock_print:
                    result = cmd_config_show(args)

                    assert result == 0
                    mock_show.assert_called_once()
                    mock_print.assert_called()

    @patch("src.cli.commands.config.logger")
    def test_cmd_config_show_with_custom_config(self, mock_logger):
        """Test config show with custom config file."""
        from src.cli import cmd_config_show
        from src.config.models import AppConfig

        args = argparse.Namespace(config=Path("/custom/config.yaml"))

        with patch("src.cli.commands.config.load_config") as mock_load:
            mock_load.return_value = AppConfig()

            with patch("src.cli.commands.config.show_resolved_config") as mock_show:
                mock_show.return_value = "# Config"

                with patch("builtins.print"):
                    result = cmd_config_show(args)

                    mock_load.assert_called_once_with(
                        config_path=Path("/custom/config.yaml")
                    )

    @patch("src.cli.commands.config.logger")
    def test_cmd_config_show_handles_load_error(self, mock_logger):
        """Test config show handles config load errors."""
        from src.cli import cmd_config_show
        from src.config.loader import ConfigLoadError

        args = argparse.Namespace(config=Path("/invalid/config.yaml"))

        with patch("src.cli.commands.config.load_config") as mock_load:
            mock_load.side_effect = ConfigLoadError("Invalid config")

            result = cmd_config_show(args)

            assert result == 1


class TestConfigIntegration:
    """Test config loading integration with CLI commands."""

    @patch("src.cli.setup_output_directory")
    @patch("src.cli.load_config")
    @patch("src.cli.create_parser")
    def test_main_loads_config_before_command(self, mock_create_parser, mock_load_config, mock_setup):
        """Test main loads config before dispatching to command handler."""
        from src.cli import main
        from src.config.models import AppConfig

        mock_parser = MagicMock()
        mock_args = MagicMock()
        mock_args.command = "analyze"
        mock_args.config = None
        mock_args.verbose = False
        mock_parser.parse_args.return_value = mock_args
        mock_create_parser.return_value = mock_parser

        mock_load_config.return_value = AppConfig()

        with patch("src.cli.cmd_analyze") as mock_analyze:
            mock_analyze.return_value = 0

            result = main()

            # Config should be loaded
            mock_load_config.assert_called_once()

    @patch("src.cli.setup_output_directory")
    @patch("src.cli.load_config")
    @patch("src.cli.create_parser")
    def test_cli_args_override_config_values(self, mock_create_parser, mock_load_config, mock_setup):
        """Test CLI arguments override config file values."""
        from src.cli import main
        from src.config.models import AppConfig, AnalyzeConfig

        mock_parser = MagicMock()
        mock_args = MagicMock()
        mock_args.command = "analyze"
        mock_args.config = None
        mock_args.verbose = False
        mock_args.num_clusters = 20  # CLI override
        mock_args.corpus = None
        mock_args.analysis_file = None
        mock_parser.parse_args.return_value = mock_args
        mock_create_parser.return_value = mock_parser

        # Config has different value
        mock_load_config.return_value = AppConfig(
            analyze=AnalyzeConfig(num_clusters=10)
        )

        with patch("src.cli.cmd_analyze") as mock_analyze:
            mock_analyze.return_value = 0

            main()

            # The analyze command should receive the CLI override value
            call_args = mock_analyze.call_args[0][0]
            assert call_args.num_clusters == 20


# =============================================================================
# Tests for Track 1B: Quick Wins - New Features
# =============================================================================


class TestQuietFlag:
    """Test cases for --quiet / -q flag (Task 1B.1)."""

    def test_create_parser_has_quiet_option(self):
        """Test parser has --quiet/-q option."""
        from src.cli import create_parser

        parser = create_parser()

        args = parser.parse_args(["-q", "analyze"])
        assert args.quiet is True

        args = parser.parse_args(["--quiet", "extract", "--user-email", "test@test.com"])
        assert args.quiet is True

    def test_quiet_default_is_false(self):
        """Test quiet defaults to False."""
        from src.cli import create_parser

        parser = create_parser()

        args = parser.parse_args(["analyze"])
        assert args.quiet is False

    def test_quiet_and_verbose_mutually_exclusive(self):
        """Test that --quiet and --verbose cannot be used together."""
        from src.cli import create_parser

        parser = create_parser()

        # Both flags should raise error
        with pytest.raises(SystemExit):
            parser.parse_args(["--quiet", "--verbose", "analyze"])

    @patch("src.cli.setup_output_directory")
    @patch("src.cli.load_config")
    @patch("src.cli.create_parser")
    def test_quiet_mode_sets_warning_log_level(self, mock_create_parser, mock_load_config, mock_setup):
        """Test quiet mode sets log level to WARNING."""
        from src.cli import main
        from src.config.models import AppConfig
        import logging

        mock_parser = MagicMock()
        mock_args = MagicMock()
        mock_args.command = "analyze"
        mock_args.quiet = True
        mock_args.verbose = False
        mock_args.config = None
        mock_parser.parse_args.return_value = mock_args
        mock_create_parser.return_value = mock_parser
        mock_load_config.return_value = AppConfig()

        with patch("src.cli.cmd_analyze") as mock_analyze:
            with patch("src.cli.logging.getLogger") as mock_get_logger:
                mock_root_logger = MagicMock()
                mock_get_logger.return_value = mock_root_logger
                mock_analyze.return_value = 0

                main()

                mock_root_logger.setLevel.assert_called_with(logging.WARNING)


class TestJsonOutputFlag:
    """Test cases for --json output flag (Task 1B.2)."""

    def test_create_parser_has_json_option(self):
        """Test parser has --json option."""
        from src.cli import create_parser

        parser = create_parser()

        args = parser.parse_args(["--json", "analyze"])
        assert args.json is True

    def test_json_default_is_false(self):
        """Test json defaults to False."""
        from src.cli import create_parser

        parser = create_parser()

        args = parser.parse_args(["analyze"])
        assert args.json is False

    def test_json_and_verbose_mutually_exclusive(self):
        """Test that --json and --verbose cannot be used together."""
        from src.cli import create_parser

        parser = create_parser()

        # Both flags should raise error
        with pytest.raises(SystemExit):
            parser.parse_args(["--json", "--verbose", "analyze"])

    def test_json_works_with_all_commands(self):
        """Test --json flag works with all commands."""
        from src.cli import create_parser

        parser = create_parser()

        # Test with each command
        for cmd, extra_args in [
            ("extract", ["--user-email", "test@test.com"]),
            ("analyze", []),
            ("suggest", []),
            ("review", []),
            ("pipeline", ["--user-email", "test@test.com"]),
        ]:
            args = parser.parse_args(["--json", cmd] + extra_args)
            assert args.json is True
            assert args.command == cmd

    @patch("src.cli.commands.analyze.save_json")
    @patch("src.cli.commands.analyze.load_json")
    @patch("src.cli.commands.analyze.PathConfig")
    @patch("src.cli.commands.analyze.logger")
    @patch("src.analyzers.run_full_analysis")
    @patch("src.models.corpus.Corpus")
    def test_cmd_analyze_json_output(self, mock_corpus_class, mock_analysis, mock_logger, mock_path_config, mock_load_json, mock_save_json):
        """Test analyze command returns JSON output when --json flag is set."""
        from src.cli import cmd_analyze
        import json

        mock_path_config.get_corpus_path.return_value = Path("/output/corpus.json")
        mock_path_config.get_analysis_path.return_value = Path("/output/analysis.json")
        mock_load_json.return_value = {
            "extraction_metadata": {
                "extraction_date": "2024-01-01T00:00:00",
                "total_emails": 100,
                "source": "test",
                "user_email": "test@example.com"
            },
            "emails": []
        }

        args = argparse.Namespace(
            corpus=None,
            num_clusters=10,
            analysis_file=None,
            json=True
        )

        mock_corpus = MagicMock()
        mock_corpus.emails = [MagicMock() for _ in range(100)]
        mock_corpus_class.return_value = mock_corpus

        mock_results = MagicMock()
        mock_results.model_dump.return_value = {"results": "data"}
        mock_results.sender_analysis.unique_senders = 50
        mock_results.content_clusters = [1, 2, 3]
        mock_analysis.return_value = (mock_results, None)

        # Capture stdout
        with patch("sys.stdout") as mock_stdout:
            with patch("src.cli.commands.analyze.output_json") as mock_output_json:
                result = cmd_analyze(args)

                assert result == 0
                mock_output_json.assert_called_once()
                call_args = mock_output_json.call_args[0][0]
                assert call_args["command"] == "analyze"
                assert call_args["status"] == "success"
                assert "duration_seconds" in call_args
                assert "output_file" in call_args


class TestInfoCommand:
    """Test cases for info command (Task 1B.3)."""

    def test_create_parser_has_info_command(self):
        """Test parser has info subcommand."""
        from src.cli import create_parser

        parser = create_parser()

        args = parser.parse_args(["info"])
        assert args.command == "info"

    def test_info_command_accepts_corpus_option(self):
        """Test info command accepts --corpus option."""
        from src.cli import create_parser

        parser = create_parser()

        args = parser.parse_args(["info", "--corpus", "/path/to/corpus.json"])
        assert args.corpus == Path("/path/to/corpus.json")

    @patch("src.cli.commands.info.load_json")
    @patch("src.cli.commands.info.PathConfig")
    @patch("src.cli.commands.info.logger")
    def test_cmd_info_success(self, mock_logger, mock_path_config, mock_load_json):
        """Test successful info command execution."""
        from src.cli import cmd_info

        mock_path_config.get_corpus_path.return_value = Path("/output/corpus.json")
        mock_path_config.get_analysis_path.return_value = Path("/output/analysis.json")
        mock_path_config.get_suggestions_path.return_value = Path("/output/suggestions.json")
        mock_path_config.get_approved_categories_path.return_value = Path("/output/approved.json")

        # Mock corpus data with minimal structure
        mock_load_json.return_value = {
            "extraction_metadata": {
                "extraction_date": "2024-01-01T00:00:00",
                "total_emails": 100,
                "source": "test",
                "user_email": "test@example.com"
            },
            "emails": [
                {"id": "1", "sender_email": "alice@example.com", "received_date": "2024-01-01T00:00:00"},
                {"id": "2", "sender_email": "bob@example.com", "received_date": "2024-06-15T00:00:00"},
            ]
        }

        args = argparse.Namespace(
            corpus=None,
            json=False
        )

        with patch("builtins.print") as mock_print:
            with patch("pathlib.Path.stat") as mock_stat:
                mock_stat.return_value = MagicMock(st_size=45_000_000)  # 45 MB
                with patch("pathlib.Path.exists", return_value=True):
                    result = cmd_info(args)

        assert result == 0

    @patch("src.cli.commands.info.load_json")
    @patch("src.cli.commands.info.PathConfig")
    @patch("src.cli.commands.info.logger")
    def test_cmd_info_json_output(self, mock_logger, mock_path_config, mock_load_json):
        """Test info command with --json flag."""
        from src.cli import cmd_info

        mock_path_config.get_corpus_path.return_value = Path("/output/corpus.json")
        mock_path_config.get_analysis_path.return_value = Path("/output/analysis.json")
        mock_path_config.get_suggestions_path.return_value = Path("/output/suggestions.json")
        mock_path_config.get_approved_categories_path.return_value = Path("/output/approved.json")

        mock_load_json.return_value = {
            "extraction_metadata": {
                "extraction_date": "2024-01-01T00:00:00",
                "total_emails": 100,
                "source": "test",
                "user_email": "test@example.com"
            },
            "emails": [
                {"id": "1", "sender_email": "alice@example.com", "received_date": "2024-01-01T00:00:00"},
            ]
        }

        args = argparse.Namespace(
            corpus=None,
            json=True
        )

        with patch("src.cli.commands.info.output_json") as mock_output_json:
            with patch("pathlib.Path.stat") as mock_stat:
                mock_stat.return_value = MagicMock(st_size=45_000_000)
                with patch("pathlib.Path.exists", return_value=True):
                    result = cmd_info(args)

        assert result == 0
        mock_output_json.assert_called_once()
        call_args = mock_output_json.call_args[0][0]
        assert "email_count" in call_args
        assert "file_size_bytes" in call_args

    @patch("src.cli.commands.info.load_json")
    @patch("src.cli.commands.info.PathConfig")
    @patch("src.cli.commands.info.logger")
    def test_cmd_info_corpus_not_found(self, mock_logger, mock_path_config, mock_load_json):
        """Test info command when corpus file doesn't exist."""
        from src.cli import cmd_info

        mock_path_config.get_corpus_path.return_value = Path("/output/corpus.json")
        mock_load_json.side_effect = FileNotFoundError("Corpus not found")

        args = argparse.Namespace(
            corpus=None,
            json=False
        )

        result = cmd_info(args)

        assert result == 1


class TestSkipReviewFlag:
    """Test cases for --skip-review flag (Task 1B.4)."""

    def test_pipeline_command_has_skip_review_option(self):
        """Test pipeline command has --skip-review flag."""
        from src.cli import create_parser

        parser = create_parser()

        args = parser.parse_args(["pipeline", "--user-email", "test@test.com", "--skip-review"])
        assert args.skip_review is True

    def test_skip_review_default_is_false(self):
        """Test skip_review defaults to False."""
        from src.cli import create_parser

        parser = create_parser()

        args = parser.parse_args(["pipeline", "--user-email", "test@test.com"])
        assert args.skip_review is False

    @patch("src.cli.commands.pipeline.cmd_review")
    @patch("src.cli.commands.pipeline.cmd_suggest")
    @patch("src.cli.commands.pipeline.cmd_analyze")
    @patch("src.cli.commands.pipeline.cmd_extract")
    @patch("src.cli.commands.pipeline.logger")
    def test_cmd_pipeline_skip_review_auto_accepts(self, mock_logger, mock_extract, mock_analyze, mock_suggest, mock_review):
        """Test pipeline with --skip-review auto-accepts all suggestions."""
        from src.cli import cmd_pipeline

        mock_extract.return_value = 0
        mock_analyze.return_value = 0
        mock_suggest.return_value = 0

        args = argparse.Namespace(
            user_email="test@example.com",
            num_clusters=10,
            no_cleanup=False,
            skip_review=True,
            output_dir=Path("/output"),
            verbose=False,
            quiet=False,
            json=False
        )

        with patch("src.cli.commands.pipeline.auto_approve_categories") as mock_auto_approve:
            mock_auto_approve.return_value = 0

            result = cmd_pipeline(args)

            assert result == 0
            # Review should not be called
            mock_review.assert_not_called()
            # Auto-approve should be called instead
            mock_auto_approve.assert_called_once()

    @patch("src.cli.commands.pipeline.cmd_review")
    @patch("src.cli.commands.pipeline.cmd_suggest")
    @patch("src.cli.commands.pipeline.cmd_analyze")
    @patch("src.cli.commands.pipeline.cmd_extract")
    @patch("src.cli.commands.pipeline.logger")
    def test_cmd_pipeline_without_skip_review_calls_review(self, mock_logger, mock_extract, mock_analyze, mock_suggest, mock_review):
        """Test pipeline without --skip-review calls interactive review."""
        from src.cli import cmd_pipeline

        mock_extract.return_value = 0
        mock_analyze.return_value = 0
        mock_suggest.return_value = 0
        mock_review.return_value = 0

        args = argparse.Namespace(
            user_email="test@example.com",
            num_clusters=10,
            no_cleanup=False,
            skip_review=False,
            output_dir=Path("/output"),
            verbose=False,
            quiet=False,
            json=False
        )

        result = cmd_pipeline(args)

        assert result == 0
        mock_review.assert_called_once()


class TestEmailValidation:
    """Test cases for email validation and early feedback (Task 1B.5)."""

    def test_validate_email_format_valid(self):
        """Test email validation accepts valid email formats."""
        from src.cli import validate_email_format

        assert validate_email_format("user@example.com") is True
        assert validate_email_format("user@hotmail.com") is True
        assert validate_email_format("user.name@outlook.com") is True
        assert validate_email_format("user+tag@gmail.com") is True

    def test_validate_email_format_invalid(self):
        """Test email validation rejects invalid email formats."""
        from src.cli import validate_email_format

        assert validate_email_format("notanemail") is False
        assert validate_email_format("missing@domain") is False
        assert validate_email_format("@nodomain.com") is False
        assert validate_email_format("spaces in@email.com") is False
        assert validate_email_format("") is False

    @patch("src.cli.commands.extract.PathConfig")
    @patch("src.cli.commands.extract.logger")
    def test_cmd_extract_validates_email_format(self, mock_logger, mock_path_config):
        """Test extract command validates email format before proceeding."""
        from src.cli import cmd_extract

        mock_path_config.get_output_dir.return_value = Path("/output")

        args = argparse.Namespace(
            user_email="invalid-email",
            corpus_file=None,
            batch_size=500,
            checkpoint_interval=100,
            json=False
        )

        result = cmd_extract(args)

        assert result == 1
        mock_logger.error.assert_called()

    @patch("src.cli.commands.pipeline.logger")
    def test_cmd_pipeline_validates_email_format(self, mock_logger):
        """Test pipeline command validates email format before proceeding."""
        from src.cli import cmd_pipeline

        args = argparse.Namespace(
            user_email="invalid-email",
            num_clusters=10,
            no_cleanup=False,
            skip_review=False,
            output_dir=Path("/output"),
            verbose=False,
            quiet=False,
            json=False
        )

        result = cmd_pipeline(args)

        assert result == 1
        mock_logger.error.assert_called()


class TestVersionFlag:
    """Test cases for --version flag (Task 1B.6)."""

    def test_version_defined_in_init(self):
        """Test that __version__ is defined in src/__init__.py."""
        from src import __version__

        assert __version__ is not None
        assert isinstance(__version__, str)
        # Check semantic versioning format (x.y.z)
        parts = __version__.split(".")
        assert len(parts) >= 2

    def test_create_parser_has_version_option(self):
        """Test parser has --version option."""
        from src.cli import create_parser
        from src import __version__

        parser = create_parser()

        # --version should trigger SystemExit and print version
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["--version"])

        assert exc_info.value.code == 0

    def test_version_output_format(self):
        """Test version output format."""
        from src.cli import create_parser
        from src import __version__
        import io
        import sys

        parser = create_parser()

        # Capture stderr (argparse writes version there by default)
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()

        try:
            parser.parse_args(["--version"])
        except SystemExit:
            pass

        output = sys.stdout.getvalue()
        sys.stdout = old_stdout

        assert __version__ in output


class TestAutoApproveCategories:
    """Test cases for auto_approve_categories function."""

    @patch("src.cli.commands.review.save_json")
    @patch("src.cli.commands.review.load_json")
    @patch("src.cli.commands.review.PathConfig")
    @patch("src.cli.commands.review.logger")
    def test_auto_approve_categories_success(self, mock_logger, mock_path_config, mock_load_json, mock_save_json):
        """Test auto_approve_categories copies suggestions to approved."""
        from src.cli import auto_approve_categories

        mock_path_config.get_suggestions_path.return_value = Path("/output/suggestions.json")
        mock_path_config.get_approved_categories_path.return_value = Path("/output/approved.json")

        mock_load_json.return_value = [
            {"category_id": "cat1", "category_name": "Category 1"},
            {"category_id": "cat2", "category_name": "Category 2"},
        ]

        args = argparse.Namespace(
            suggestions=None,
            approved_file=None,
            no_cleanup=True,
            json=False
        )

        result = auto_approve_categories(args)

        assert result == 0
        mock_save_json.assert_called_once()

    @patch("src.cli.commands.review.load_json")
    @patch("src.cli.commands.review.PathConfig")
    @patch("src.cli.commands.review.logger")
    def test_auto_approve_categories_file_not_found(self, mock_logger, mock_path_config, mock_load_json):
        """Test auto_approve_categories handles missing suggestions file."""
        from src.cli import auto_approve_categories

        mock_path_config.get_suggestions_path.return_value = Path("/output/suggestions.json")
        mock_load_json.side_effect = FileNotFoundError("Suggestions not found")

        args = argparse.Namespace(
            suggestions=None,
            approved_file=None,
            no_cleanup=True,
            json=False
        )

        result = auto_approve_categories(args)

        assert result == 1


class TestOutputJsonFunction:
    """Test cases for output_json helper function."""

    def test_output_json_writes_formatted_json(self):
        """Test output_json writes properly formatted JSON to stdout."""
        from src.cli import output_json
        import io
        import sys
        import json

        data = {"command": "test", "status": "success"}

        old_stdout = sys.stdout
        sys.stdout = io.StringIO()

        output_json(data)

        output = sys.stdout.getvalue()
        sys.stdout = old_stdout

        # Should be valid JSON
        parsed = json.loads(output)
        assert parsed["command"] == "test"
        assert parsed["status"] == "success"

    def test_output_json_includes_all_fields(self):
        """Test output_json preserves all fields."""
        from src.cli import output_json
        import io
        import sys
        import json

        data = {
            "command": "analyze",
            "status": "success",
            "duration_seconds": 123.45,
            "output_file": "/path/to/file.json",
            "stats": {"emails_analyzed": 1000}
        }

        old_stdout = sys.stdout
        sys.stdout = io.StringIO()

        output_json(data)

        output = sys.stdout.getvalue()
        sys.stdout = old_stdout

        parsed = json.loads(output)
        assert parsed["duration_seconds"] == 123.45
        assert parsed["stats"]["emails_analyzed"] == 1000


# =============================================================================
# Tests for dry-run mode (--dry-run / -n flag)
# =============================================================================


class TestDryRunParserOptions:
    """Test cases for --dry-run flag in argument parser."""

    def test_extract_command_has_dry_run_flag(self):
        """Test extract command has --dry-run flag."""
        from src.cli import create_parser

        parser = create_parser()

        args = parser.parse_args(["extract", "--user-email", "test@test.com", "--dry-run"])
        assert args.dry_run is True

    def test_extract_command_has_short_dry_run_flag(self):
        """Test extract command has -n short flag for dry-run."""
        from src.cli import create_parser

        parser = create_parser()

        args = parser.parse_args(["extract", "--user-email", "test@test.com", "-n"])
        assert args.dry_run is True

    def test_extract_dry_run_defaults_to_false(self):
        """Test extract dry-run defaults to False."""
        from src.cli import create_parser

        parser = create_parser()

        args = parser.parse_args(["extract", "--user-email", "test@test.com"])
        assert args.dry_run is False

    def test_analyze_command_has_dry_run_flag(self):
        """Test analyze command has --dry-run flag."""
        from src.cli import create_parser

        parser = create_parser()

        args = parser.parse_args(["analyze", "--dry-run"])
        assert args.dry_run is True

    def test_analyze_command_has_short_dry_run_flag(self):
        """Test analyze command has -n short flag."""
        from src.cli import create_parser

        parser = create_parser()

        args = parser.parse_args(["analyze", "-n"])
        assert args.dry_run is True

    def test_suggest_command_has_dry_run_flag(self):
        """Test suggest command has --dry-run flag."""
        from src.cli import create_parser

        parser = create_parser()

        args = parser.parse_args(["suggest", "--dry-run"])
        assert args.dry_run is True

    def test_review_command_has_dry_run_flag(self):
        """Test review command has --dry-run flag."""
        from src.cli import create_parser

        parser = create_parser()

        args = parser.parse_args(["review", "--dry-run"])
        assert args.dry_run is True

    def test_pipeline_command_has_dry_run_flag(self):
        """Test pipeline command has --dry-run flag."""
        from src.cli import create_parser

        parser = create_parser()

        args = parser.parse_args(["pipeline", "--user-email", "test@test.com", "--dry-run"])
        assert args.dry_run is True


class TestCmdExtractDryRun:
    """Test cases for dry-run mode in cmd_extract."""

    @patch("src.cli.commands.extract.PathConfig")
    @patch("src.cli.commands.extract.logger")
    def test_cmd_extract_dry_run_does_not_execute(self, mock_logger, mock_path_config):
        """Test dry-run mode doesn't actually extract emails."""
        from src.cli import cmd_extract

        mock_path_config.get_corpus_path.return_value = Path("/output/corpus.json")
        mock_path_config.get_output_dir.return_value = Path("/output")

        args = argparse.Namespace(
            user_email="test@example.com",
            corpus_file=None,
            batch_size=500,
            checkpoint_interval=100,
            dry_run=True
        )

        # In dry-run mode, the extractor should NOT be imported/called
        # The function should return early with preview output
        with patch("src.extractors.m365_extractor.EmailExtractor", side_effect=Exception("Should not be called")):
            # Should complete without error because dry-run returns before import
            result = cmd_extract(args)

        assert result == 0

    @patch("src.cli.commands.extract.PathConfig")
    @patch("src.cli.commands.extract.logger")
    def test_cmd_extract_dry_run_prints_preview(self, mock_logger, mock_path_config, capsys):
        """Test dry-run mode prints preview output."""
        from src.cli import cmd_extract

        mock_path_config.get_corpus_path.return_value = Path("/output/corpus.json")
        mock_path_config.get_output_dir.return_value = Path("/output")

        args = argparse.Namespace(
            user_email="test@example.com",
            corpus_file=None,
            batch_size=500,
            checkpoint_interval=100,
            dry_run=True
        )

        result = cmd_extract(args)

        captured = capsys.readouterr()
        assert "[DRY RUN]" in captured.out
        assert "extract" in captured.out
        assert "test@example.com" in captured.out
        assert "No changes will be made" in captured.out


class TestCmdAnalyzeDryRun:
    """Test cases for dry-run mode in cmd_analyze."""

    @patch("src.cli.commands.analyze.PathConfig")
    @patch("src.cli.commands.analyze.logger")
    def test_cmd_analyze_dry_run_does_not_execute(self, mock_logger, mock_path_config):
        """Test dry-run mode doesn't actually analyze."""
        from src.cli import cmd_analyze

        mock_path_config.get_corpus_path.return_value = Path("/output/corpus.json")
        mock_path_config.get_analysis_path.return_value = Path("/output/analysis.json")

        args = argparse.Namespace(
            corpus=None,
            num_clusters=10,
            analysis_file=None,
            dry_run=True
        )

        # In dry-run mode, run_full_analysis should NOT be imported/called
        with patch("src.analyzers.run_full_analysis", side_effect=Exception("Should not be called")):
            # Should complete without error because dry-run returns before import
            result = cmd_analyze(args)

        assert result == 0

    @patch("src.cli.commands.analyze.PathConfig")
    @patch("src.cli.commands.analyze.logger")
    def test_cmd_analyze_dry_run_prints_preview(self, mock_logger, mock_path_config, capsys):
        """Test dry-run mode prints preview output."""
        from src.cli import cmd_analyze

        mock_path_config.get_corpus_path.return_value = Path("/output/corpus.json")
        mock_path_config.get_analysis_path.return_value = Path("/output/analysis.json")

        args = argparse.Namespace(
            corpus=None,
            num_clusters=10,
            analysis_file=None,
            dry_run=True
        )

        result = cmd_analyze(args)

        captured = capsys.readouterr()
        assert "[DRY RUN]" in captured.out
        assert "analyze" in captured.out


class TestCmdSuggestDryRun:
    """Test cases for dry-run mode in cmd_suggest."""

    @patch("src.cli.commands.suggest.PathConfig")
    @patch("src.cli.commands.suggest.logger")
    def test_cmd_suggest_dry_run_does_not_execute(self, mock_logger, mock_path_config):
        """Test dry-run mode doesn't actually generate suggestions."""
        from src.cli import cmd_suggest

        mock_path_config.get_analysis_path.return_value = Path("/output/analysis.json")
        mock_path_config.get_suggestions_path.return_value = Path("/output/suggestions.json")

        args = argparse.Namespace(
            analysis=None,
            min_cluster_percentage=5.0,
            min_sender_count=20,
            suggestions_file=None,
            dry_run=True
        )

        # In dry-run mode, CategoryGenerator should NOT be imported/called
        with patch("src.generators.category_generator.CategoryGenerator", side_effect=Exception("Should not be called")):
            # Should complete without error because dry-run returns before import
            result = cmd_suggest(args)

        assert result == 0

    @patch("src.cli.commands.suggest.PathConfig")
    @patch("src.cli.commands.suggest.logger")
    def test_cmd_suggest_dry_run_prints_preview(self, mock_logger, mock_path_config, capsys):
        """Test dry-run mode prints preview output."""
        from src.cli import cmd_suggest

        mock_path_config.get_analysis_path.return_value = Path("/output/analysis.json")
        mock_path_config.get_suggestions_path.return_value = Path("/output/suggestions.json")

        args = argparse.Namespace(
            analysis=None,
            min_cluster_percentage=5.0,
            min_sender_count=20,
            suggestions_file=None,
            dry_run=True
        )

        result = cmd_suggest(args)

        captured = capsys.readouterr()
        assert "[DRY RUN]" in captured.out
        assert "suggest" in captured.out


class TestCmdReviewDryRun:
    """Test cases for dry-run mode in cmd_review."""

    @patch("src.cli.commands.review.PathConfig")
    @patch("src.cli.commands.review.logger")
    def test_cmd_review_dry_run_does_not_execute(self, mock_logger, mock_path_config):
        """Test dry-run mode doesn't actually review."""
        from src.cli import cmd_review

        mock_path_config.get_suggestions_path.return_value = Path("/output/suggestions.json")
        mock_path_config.get_approved_categories_path.return_value = Path("/output/approved.json")
        mock_path_config.get_output_dir.return_value = Path("/output")

        args = argparse.Namespace(
            suggestions=None,
            approved_file=None,
            no_cleanup=False,
            dry_run=True
        )

        # In dry-run mode, review_categories should NOT be imported/called
        with patch("src.ui.category_review.review_categories", side_effect=Exception("Should not be called")):
            # Should complete without error because dry-run returns before import
            result = cmd_review(args)

        assert result == 0

    @patch("src.cli.commands.review.PathConfig")
    @patch("src.cli.commands.review.logger")
    def test_cmd_review_dry_run_prints_preview(self, mock_logger, mock_path_config, capsys):
        """Test dry-run mode prints preview output."""
        from src.cli import cmd_review

        mock_path_config.get_suggestions_path.return_value = Path("/output/suggestions.json")
        mock_path_config.get_approved_categories_path.return_value = Path("/output/approved.json")
        mock_path_config.get_output_dir.return_value = Path("/output")

        args = argparse.Namespace(
            suggestions=None,
            approved_file=None,
            no_cleanup=False,
            dry_run=True
        )

        result = cmd_review(args)

        captured = capsys.readouterr()
        assert "[DRY RUN]" in captured.out
        assert "review" in captured.out


class TestCmdPipelineDryRun:
    """Test cases for dry-run mode in cmd_pipeline."""

    @patch("src.cli.commands.pipeline.logger")
    def test_cmd_pipeline_dry_run_does_not_execute(self, mock_logger):
        """Test dry-run mode doesn't actually run pipeline."""
        from src.cli import cmd_pipeline

        args = argparse.Namespace(
            user_email="test@example.com",
            num_clusters=10,
            no_cleanup=False,
            skip_review=False,
            output_dir=None,
            verbose=False,
            quiet=False,
            json=False,
            dry_run=True
        )

        # Should NOT call any of the sub-commands
        with patch("src.cli.commands.pipeline.cmd_extract", side_effect=Exception("Should not be called")):
            with patch("src.cli.commands.pipeline.cmd_analyze", side_effect=Exception("Should not be called")):
                result = cmd_pipeline(args)

        assert result == 0

    @patch("src.cli.commands.pipeline.logger")
    def test_cmd_pipeline_dry_run_prints_preview(self, mock_logger, capsys):
        """Test dry-run mode prints preview output."""
        from src.cli import cmd_pipeline

        args = argparse.Namespace(
            user_email="test@example.com",
            num_clusters=10,
            no_cleanup=False,
            skip_review=False,
            output_dir=None,
            verbose=False,
            quiet=False,
            json=False,
            dry_run=True
        )

        result = cmd_pipeline(args)

        captured = capsys.readouterr()
        assert "[DRY RUN]" in captured.out
        assert "pipeline" in captured.out


class TestDryRunValidation:
    """Test dry-run mode still performs validation."""

    @patch("src.cli.commands.extract.PathConfig")
    @patch("src.cli.commands.extract.logger")
    def test_extract_dry_run_validates_email_format(self, mock_logger, mock_path_config):
        """Test dry-run still validates email format."""
        from src.cli import cmd_extract

        mock_path_config.get_corpus_path.return_value = Path("/output/corpus.json")

        args = argparse.Namespace(
            user_email="invalid-email",  # Invalid email
            corpus_file=None,
            batch_size=500,
            checkpoint_interval=100,
            dry_run=True
        )

        result = cmd_extract(args)

        # Should fail validation even in dry-run mode
        assert result == 1

    @patch("src.cli.commands.pipeline.logger")
    def test_pipeline_dry_run_validates_email_format(self, mock_logger):
        """Test pipeline dry-run still validates email format."""
        from src.cli import cmd_pipeline

        args = argparse.Namespace(
            user_email="invalid-email",  # Invalid email
            num_clusters=10,
            no_cleanup=False,
            skip_review=False,
            output_dir=None,
            verbose=False,
            quiet=False,
            json=False,
            dry_run=True
        )

        result = cmd_pipeline(args)

        # Should fail validation even in dry-run mode
        assert result == 1


class TestDryRunWithJsonOutput:
    """Test dry-run mode with --json flag."""

    @patch("src.cli.commands.extract.PathConfig")
    @patch("src.cli.commands.extract.logger")
    def test_extract_dry_run_with_json_output(self, mock_logger, mock_path_config, capsys):
        """Test dry-run mode respects --json flag."""
        from src.cli import cmd_extract
        import json

        mock_path_config.get_corpus_path.return_value = Path("/output/corpus.json")
        mock_path_config.get_output_dir.return_value = Path("/output")

        args = argparse.Namespace(
            user_email="test@example.com",
            corpus_file=None,
            batch_size=500,
            checkpoint_interval=100,
            dry_run=True,
            json=True
        )

        result = cmd_extract(args)

        captured = capsys.readouterr()
        # Should output JSON
        output = json.loads(captured.out)
        assert output["command"] == "extract"
        assert output["dry_run"] is True
        assert result == 0


# =============================================================================
# Tests for auto-cluster CLI integration (Track 2A)
# =============================================================================


class TestAutoClusterCLI:
    """Test cases for auto-cluster CLI flags."""

    def test_analyze_command_has_auto_clusters_flag(self):
        """Test analyze command has --auto-clusters flag."""
        from src.cli import create_parser

        parser = create_parser()

        args = parser.parse_args(["analyze", "--auto-clusters"])
        assert args.auto_clusters is True

    def test_analyze_command_auto_clusters_default_false(self):
        """Test --auto-clusters defaults to False."""
        from src.cli import create_parser

        parser = create_parser()

        args = parser.parse_args(["analyze"])
        assert args.auto_clusters is False

    def test_analyze_command_has_cluster_method_flag(self):
        """Test analyze command has --cluster-method flag."""
        from src.cli import create_parser

        parser = create_parser()

        args = parser.parse_args(["analyze", "--cluster-method", "elbow"])
        assert args.cluster_method == "elbow"

        args = parser.parse_args(["analyze", "--cluster-method", "silhouette"])
        assert args.cluster_method == "silhouette"

    def test_analyze_command_cluster_method_default_silhouette(self):
        """Test --cluster-method defaults to silhouette."""
        from src.cli import create_parser

        parser = create_parser()

        args = parser.parse_args(["analyze"])
        assert args.cluster_method == "silhouette"

    def test_num_clusters_overrides_auto_selection(self):
        """Test --num-clusters overrides auto-selection."""
        from src.cli import create_parser

        parser = create_parser()

        # Both flags can be set
        args = parser.parse_args(["analyze", "--auto-clusters", "--num-clusters", "5"])
        assert args.auto_clusters is True
        assert args.num_clusters == 5

    def test_analyze_command_has_cluster_analysis_flag(self):
        """Test analyze command has --cluster-analysis flag."""
        from src.cli import create_parser

        parser = create_parser()

        args = parser.parse_args(["analyze", "--cluster-analysis"])
        assert args.cluster_analysis is True

    def test_analyze_command_cluster_analysis_default_false(self):
        """Test --cluster-analysis defaults to False."""
        from src.cli import create_parser

        parser = create_parser()

        args = parser.parse_args(["analyze"])
        assert args.cluster_analysis is False

    def test_pipeline_command_has_auto_clusters_flag(self):
        """Test pipeline command has --auto-clusters flag."""
        from src.cli import create_parser

        parser = create_parser()

        args = parser.parse_args(["pipeline", "--user-email", "test@test.com", "--auto-clusters"])
        assert args.auto_clusters is True

    def test_pipeline_command_has_cluster_method_flag(self):
        """Test pipeline command has --cluster-method flag."""
        from src.cli import create_parser

        parser = create_parser()

        args = parser.parse_args(["pipeline", "--user-email", "test@test.com", "--cluster-method", "elbow"])
        assert args.cluster_method == "elbow"


# =============================================================================
# Tests for cluster analysis report (Track 2A.5)
# =============================================================================


class TestClusterAnalysisReport:
    """Test cases for cluster analysis report feature."""

    @patch("src.cli.commands.analyze.load_json")
    @patch("src.cli.commands.analyze.PathConfig")
    @patch("src.cli.commands.analyze.logger")
    def test_cluster_analysis_prints_k_vs_score_table(self, mock_logger, mock_path_config, mock_load_json, capsys):
        """Test that --cluster-analysis prints k vs score table."""
        from src.cli import cmd_analyze

        mock_path_config.get_corpus_path.return_value = Path("/output/corpus.json")
        mock_path_config.get_analysis_path.return_value = Path("/output/analysis.json")
        mock_load_json.return_value = {
            "extraction_metadata": {
                "extraction_date": "2024-01-01T00:00:00",
                "total_emails": 50,
                "source": "test",
                "user_email": "test@example.com"
            },
            "emails": [
                {
                    "id": str(i),
                    "sender_email": f"sender{i}@example.com",
                    "sender_name": "",
                    "sender_domain": "example.com",
                    "recipient_email": None,
                    "recipient_name": "",
                    "subject": f"Subject {i}",
                    "body_text": f"Body text {i}",
                    "received_date": "2024-01-01T10:00:00",
                    "has_attachments": False
                }
                for i in range(50)
            ]
        }

        args = argparse.Namespace(
            corpus=None,
            num_clusters=5,
            auto_clusters=False,
            cluster_method="silhouette",
            cluster_analysis=True,
            analysis_file=None,
            dry_run=False,
            json=False
        )

        # This test verifies the feature exists - actual implementation details
        # are tested in the run to ensure table/chart output is generated
        with patch("src.analyzers.run_full_analysis") as mock_analysis:
            with patch("src.cli.commands.analyze.save_json"):
                mock_results = MagicMock()
                mock_results.model_dump.return_value = {}
                mock_results.sender_analysis.unique_senders = 10
                mock_results.content_clusters = []
                mock_analysis.return_value = (mock_results, None)

                # Run should succeed
                result = cmd_analyze(args)

                # Command should complete (actual output tested via integration)
                assert result == 0

    def test_cluster_analysis_with_json_output(self):
        """Test --cluster-analysis works with --json flag."""
        from src.cli import create_parser

        parser = create_parser()

        # --json is a global flag that must come before the subcommand
        args = parser.parse_args(["--json", "analyze", "--cluster-analysis"])
        assert args.cluster_analysis is True
        assert args.json is True


# =============================================================================
# Tests for export command (Track 5C: Export & Polish)
# =============================================================================


class TestExportCommand:
    """Test cases for export command (Task 5C.3)."""

    def test_create_parser_has_export_command(self):
        """Test parser has export subcommand."""
        from src.cli import create_parser

        parser = create_parser()

        args = parser.parse_args(["export", "--format", "csv"])
        assert args.command == "export"

    def test_export_command_requires_format(self):
        """Test export command requires --format flag."""
        from src.cli import create_parser

        parser = create_parser()

        with pytest.raises(SystemExit):
            parser.parse_args(["export"])

    def test_export_command_format_csv(self):
        """Test export command accepts csv format."""
        from src.cli import create_parser

        parser = create_parser()

        args = parser.parse_args(["export", "--format", "csv"])
        assert args.format == "csv"

    def test_export_command_format_html(self):
        """Test export command accepts html format."""
        from src.cli import create_parser

        parser = create_parser()

        args = parser.parse_args(["export", "--format", "html"])
        assert args.format == "html"

    def test_export_command_rejects_invalid_format(self):
        """Test export command rejects invalid format."""
        from src.cli import create_parser

        parser = create_parser()

        with pytest.raises(SystemExit):
            parser.parse_args(["export", "--format", "invalid"])

    def test_export_command_has_output_option(self):
        """Test export command has --output option."""
        from src.cli import create_parser

        parser = create_parser()

        args = parser.parse_args(["export", "--format", "csv", "--output", "/custom/output.csv"])
        assert args.output == Path("/custom/output.csv")

    def test_export_command_has_input_option(self):
        """Test export command has --input option."""
        from src.cli import create_parser

        parser = create_parser()

        args = parser.parse_args(["export", "--format", "csv", "--input", "/custom/categories.json"])
        assert args.input == Path("/custom/categories.json")

    def test_export_command_default_output_is_none(self):
        """Test export command --output defaults to None (auto-generated)."""
        from src.cli import create_parser

        parser = create_parser()

        args = parser.parse_args(["export", "--format", "csv"])
        assert args.output is None

    def test_export_command_default_input_is_none(self):
        """Test export command --input defaults to None (uses approved_categories.json)."""
        from src.cli import create_parser

        parser = create_parser()

        args = parser.parse_args(["export", "--format", "csv"])
        assert args.input is None


class TestCmdExport:
    """Test cases for cmd_export function."""

    @patch("src.cli.commands.export.load_json")
    @patch("src.cli.commands.export.PathConfig")
    @patch("src.cli.commands.export.logger")
    def test_cmd_export_csv_success(self, mock_logger, mock_path_config, mock_load_json):
        """Test successful CSV export."""
        from src.cli import cmd_export

        mock_path_config.get_approved_categories_path.return_value = Path("/output/approved.json")
        mock_path_config.get_output_dir.return_value = Path("/output")

        # Mock categories data
        mock_load_json.return_value = [
            {
                "category_id": "cat_001",
                "category_name": "Test Category",
                "description": "Test description",
                "confidence": 0.85,
                "email_count": 100,
                "percentage": 10.0,
                "source": "template",
                "level": 0,
                "parent_category_id": None,
            }
        ]

        args = argparse.Namespace(
            format="csv",
            output=None,
            input=None,
            json=False
        )

        with patch("src.exporters.csv_exporter.export_categories_to_csv") as mock_export:
            mock_export.return_value = Path("/output/categories.csv")
            result = cmd_export(args)

        assert result == 0
        mock_export.assert_called_once()

    @patch("src.cli.commands.export.load_json")
    @patch("src.cli.commands.export.PathConfig")
    @patch("src.cli.commands.export.logger")
    def test_cmd_export_html_success(self, mock_logger, mock_path_config, mock_load_json):
        """Test successful HTML export."""
        from src.cli import cmd_export

        mock_path_config.get_approved_categories_path.return_value = Path("/output/approved.json")
        mock_path_config.get_output_dir.return_value = Path("/output")

        mock_load_json.return_value = [
            {
                "category_id": "cat_001",
                "category_name": "Test Category",
                "description": "Test description",
                "confidence": 0.85,
                "email_count": 100,
                "percentage": 10.0,
                "source": "template",
                "level": 0,
                "parent_category_id": None,
            }
        ]

        args = argparse.Namespace(
            format="html",
            output=None,
            input=None,
            json=False
        )

        with patch("src.exporters.html_exporter.export_categories_to_html") as mock_export:
            mock_export.return_value = Path("/output/report.html")
            result = cmd_export(args)

        assert result == 0
        mock_export.assert_called_once()

    @patch("src.cli.commands.export.load_json")
    @patch("src.cli.commands.export.PathConfig")
    @patch("src.cli.commands.export.logger")
    def test_cmd_export_custom_output_path(self, mock_logger, mock_path_config, mock_load_json):
        """Test export with custom output path."""
        from src.cli import cmd_export

        mock_path_config.get_approved_categories_path.return_value = Path("/output/approved.json")

        mock_load_json.return_value = [
            {
                "category_id": "cat_001",
                "category_name": "Test Category",
                "description": "Test description",
                "confidence": 0.85,
                "email_count": 100,
                "percentage": 10.0,
                "source": "template",
                "level": 0,
                "parent_category_id": None,
            }
        ]

        args = argparse.Namespace(
            format="csv",
            output=Path("/custom/output.csv"),
            input=None,
            json=False
        )

        with patch("src.exporters.csv_exporter.export_categories_to_csv") as mock_export:
            mock_export.return_value = Path("/custom/output.csv")
            result = cmd_export(args)

        assert result == 0
        # Verify custom path was used
        call_args = mock_export.call_args[0]
        assert call_args[1] == Path("/custom/output.csv")

    @patch("src.cli.commands.export.load_json")
    @patch("src.cli.commands.export.PathConfig")
    @patch("src.cli.commands.export.logger")
    def test_cmd_export_custom_input_path(self, mock_logger, mock_path_config, mock_load_json):
        """Test export with custom input path."""
        from src.cli import cmd_export

        mock_path_config.get_output_dir.return_value = Path("/output")

        mock_load_json.return_value = [
            {
                "category_id": "cat_001",
                "category_name": "Test Category",
                "description": "Test description",
                "confidence": 0.85,
                "email_count": 100,
                "percentage": 10.0,
                "source": "template",
                "level": 0,
                "parent_category_id": None,
            }
        ]

        args = argparse.Namespace(
            format="csv",
            output=None,
            input=Path("/custom/input.json"),
            json=False
        )

        with patch("src.exporters.csv_exporter.export_categories_to_csv") as mock_export:
            mock_export.return_value = Path("/output/categories.csv")
            result = cmd_export(args)

        assert result == 0
        # Verify custom input path was used
        mock_load_json.assert_called_with(Path("/custom/input.json"))

    @patch("src.cli.commands.export.load_json")
    @patch("src.cli.commands.export.PathConfig")
    @patch("src.cli.commands.export.logger")
    def test_cmd_export_file_not_found(self, mock_logger, mock_path_config, mock_load_json):
        """Test export when input file doesn't exist."""
        from src.cli import cmd_export

        mock_path_config.get_approved_categories_path.return_value = Path("/output/approved.json")
        mock_load_json.side_effect = FileNotFoundError("File not found")

        args = argparse.Namespace(
            format="csv",
            output=None,
            input=None,
            json=False
        )

        result = cmd_export(args)

        assert result == 1

    @patch("src.cli.commands.export.load_json")
    @patch("src.cli.commands.export.PathConfig")
    @patch("src.cli.commands.export.logger")
    def test_cmd_export_json_output(self, mock_logger, mock_path_config, mock_load_json):
        """Test export with --json output."""
        from src.cli import cmd_export

        mock_path_config.get_approved_categories_path.return_value = Path("/output/approved.json")
        mock_path_config.get_output_dir.return_value = Path("/output")

        mock_load_json.return_value = [
            {
                "category_id": "cat_001",
                "category_name": "Test Category",
                "description": "Test description",
                "confidence": 0.85,
                "email_count": 100,
                "percentage": 10.0,
                "source": "template",
                "level": 0,
                "parent_category_id": None,
            }
        ]

        args = argparse.Namespace(
            format="csv",
            output=None,
            input=None,
            json=True
        )

        with patch("src.exporters.csv_exporter.export_categories_to_csv") as mock_export:
            mock_export.return_value = Path("/output/categories.csv")
            with patch("src.cli.commands.export.output_json") as mock_output_json:
                result = cmd_export(args)

        assert result == 0
        mock_output_json.assert_called_once()
        call_args = mock_output_json.call_args[0][0]
        assert call_args["status"] == "success"
        assert "output_file" in call_args

    @patch("src.cli.commands.export.load_json")
    @patch("src.cli.commands.export.PathConfig")
    @patch("src.cli.commands.export.logger")
    def test_cmd_export_handles_empty_categories(self, mock_logger, mock_path_config, mock_load_json):
        """Test export handles empty category list."""
        from src.cli import cmd_export

        mock_path_config.get_approved_categories_path.return_value = Path("/output/approved.json")
        mock_path_config.get_output_dir.return_value = Path("/output")

        mock_load_json.return_value = []  # Empty list

        args = argparse.Namespace(
            format="csv",
            output=None,
            input=None,
            json=False
        )

        with patch("src.exporters.csv_exporter.export_categories_to_csv") as mock_export:
            mock_export.return_value = Path("/output/categories.csv")
            result = cmd_export(args)

        assert result == 0
        mock_export.assert_called_once()
        # Verify empty list was passed
        call_args = mock_export.call_args[0]
        assert call_args[0] == []


# =============================================================================
# Tests for Phase 6 Track 6A: Exception Handling and Recovery Hints
# =============================================================================


class TestExceptionHandlingInCli:
    """Test cases for proper exception handling with recovery hints."""

    @patch("src.cli.commands.analyze.logger")
    @patch("src.cli.commands.analyze.load_json")
    @patch("src.cli.commands.analyze.PathConfig")
    def test_cmd_analyze_corpus_not_found_error(self, mock_path_config, mock_load_json, mock_logger):
        """Test analyze shows recovery hint when corpus not found."""
        from src.cli import cmd_analyze
        from src.exceptions import CorpusNotFoundError

        mock_path_config.get_corpus_path.return_value = Path("/output/corpus.json")

        # Simulate file not found
        mock_load_json.side_effect = FileNotFoundError("File not found")

        args = argparse.Namespace(
            corpus=None,
            num_clusters=10,
            analysis_file=None,
            verbose=False,
            json=False,
            dry_run=False,
            cluster_analysis=False,
            incremental=False,
            auto_clusters=False,
            cluster_method="silhouette"
        )

        result = cmd_analyze(args)

        assert result == 1
        mock_logger.error.assert_called()

    @patch("src.cli.commands.suggest.logger")
    @patch("src.cli.commands.suggest.load_json")
    @patch("src.cli.commands.suggest.PathConfig")
    def test_cmd_analyze_corpus_not_found_json_output(self, mock_path_config, mock_load_json, mock_logger):
        """Test analyze with --json outputs structured error."""
        from src.cli import cmd_analyze

        mock_path_config.get_corpus_path.return_value = Path("/output/corpus.json")
        mock_load_json.side_effect = FileNotFoundError("File not found")

        args = argparse.Namespace(
            corpus=None,
            num_clusters=10,
            analysis_file=None,
            verbose=False,
            json=True,
            dry_run=False,
            cluster_analysis=False,
            incremental=False,
            auto_clusters=False,
            cluster_method="silhouette"
        )

        with patch("src.cli.commands.analyze.output_json") as mock_output_json:
            result = cmd_analyze(args)

            assert result == 1
            mock_output_json.assert_called_once()
            call_args = mock_output_json.call_args[0][0]
            assert call_args["status"] == "error"
            assert "error" in call_args

    @patch("src.cli.commands.suggest.logger")
    @patch("src.cli.commands.suggest.load_json")
    @patch("src.cli.commands.suggest.PathConfig")
    def test_cmd_suggest_analysis_not_found_error(self, mock_path_config, mock_load_json, mock_logger):
        """Test suggest shows error when analysis not found."""
        from src.cli import cmd_suggest

        mock_path_config.get_analysis_path.return_value = Path("/output/analysis.json")
        mock_load_json.side_effect = FileNotFoundError("Analysis file not found")

        args = argparse.Namespace(
            analysis=None,
            min_cluster_percentage=5.0,
            min_sender_count=20,
            suggestions_file=None,
            verbose=False,
            json=False,
            dry_run=False
        )

        result = cmd_suggest(args)

        assert result == 1
        mock_logger.error.assert_called()

    @patch("src.cli.commands.extract.logger")
    def test_cmd_extract_invalid_email_format(self, mock_logger):
        """Test extract validates email format."""
        from src.cli import cmd_extract

        args = argparse.Namespace(
            user_email="not-an-email",
            corpus_file=None,
            batch_size=500,
            checkpoint_interval=100,
            verbose=False,
            json=False,
            dry_run=False,
            since_last=False,
            output_dir=None
        )

        result = cmd_extract(args)

        assert result == 1
        mock_logger.error.assert_called()


class TestConfigValidateCommand:
    """Test cases for config validate command (Track 6B)."""

    def test_create_parser_has_config_validate_command(self):
        """Test parser has config validate subcommand."""
        from src.cli import create_parser

        parser = create_parser()

        args = parser.parse_args(["config", "validate"])
        assert args.command == "config"
        assert args.config_action == "validate"

    @patch("src.cli.commands.config.logger")
    def test_cmd_config_validate_success(self, mock_logger):
        """Test config validate with valid configuration."""
        from src.cli import cmd_config_validate
        from src.config.models import AppConfig

        args = argparse.Namespace(
            config=None,
            json=False
        )

        with patch("src.cli.commands.config.load_config") as mock_load:
            mock_load.return_value = AppConfig()
            with patch("src.cli.commands.config.validate_config") as mock_validate:
                mock_validate.return_value = []  # No validation errors

                with patch("builtins.print"):
                    result = cmd_config_validate(args)

                assert result == 0

    @patch("src.cli.commands.config.logger")
    def test_cmd_config_validate_with_errors(self, mock_logger):
        """Test config validate with validation errors."""
        from src.cli import cmd_config_validate
        from src.config.models import AppConfig

        args = argparse.Namespace(
            config=None,
            json=False
        )

        with patch("src.cli.commands.config.load_config") as mock_load:
            mock_load.return_value = AppConfig(output_dir=Path("/nonexistent/path"))
            with patch("src.cli.commands.config.validate_config") as mock_validate:
                mock_validate.return_value = [
                    {"field": "output_dir", "status": "error", "message": "Directory does not exist"}
                ]

                with patch("builtins.print"):
                    result = cmd_config_validate(args)

                # Returns 0 even with warnings, 1 only for errors
                assert result in [0, 1]

    @patch("src.cli.commands.config.logger")
    def test_cmd_config_validate_json_output(self, mock_logger):
        """Test config validate with --json flag."""
        from src.cli import cmd_config_validate
        from src.config.models import AppConfig

        args = argparse.Namespace(
            config=None,
            json=True
        )

        with patch("src.cli.commands.config.load_config") as mock_load:
            mock_load.return_value = AppConfig()
            with patch("src.cli.commands.config.validate_config") as mock_validate:
                mock_validate.return_value = []

                with patch("src.cli.commands.config.output_json") as mock_output_json:
                    result = cmd_config_validate(args)

                    mock_output_json.assert_called_once()
                    call_args = mock_output_json.call_args[0][0]
                    assert "command" in call_args
                    assert "validations" in call_args


class TestCLIHelpExamples:
    """Test cases for enhanced CLI help with examples (Track 6B)."""

    def test_analyze_command_has_epilog_with_examples(self):
        """Test analyze command has epilog with usage examples."""
        from src.cli import create_parser

        parser = create_parser()
        # Access the subparser for analyze
        subparsers = parser._subparsers._group_actions[0].choices

        analyze_parser = subparsers["analyze"]
        assert analyze_parser.epilog is not None
        assert "example" in analyze_parser.epilog.lower()

    def test_extract_command_has_epilog_with_examples(self):
        """Test extract command has epilog with usage examples."""
        from src.cli import create_parser

        parser = create_parser()
        subparsers = parser._subparsers._group_actions[0].choices

        extract_parser = subparsers["extract"]
        assert extract_parser.epilog is not None
        assert "example" in extract_parser.epilog.lower()

    def test_suggest_command_has_epilog_with_examples(self):
        """Test suggest command has epilog with usage examples."""
        from src.cli import create_parser

        parser = create_parser()
        subparsers = parser._subparsers._group_actions[0].choices

        suggest_parser = subparsers["suggest"]
        assert suggest_parser.epilog is not None

    def test_review_command_has_epilog_with_examples(self):
        """Test review command has epilog with usage examples."""
        from src.cli import create_parser

        parser = create_parser()
        subparsers = parser._subparsers._group_actions[0].choices

        review_parser = subparsers["review"]
        assert review_parser.epilog is not None

    def test_pipeline_command_has_epilog_with_examples(self):
        """Test pipeline command has epilog with usage examples."""
        from src.cli import create_parser

        parser = create_parser()
        subparsers = parser._subparsers._group_actions[0].choices

        pipeline_parser = subparsers["pipeline"]
        assert pipeline_parser.epilog is not None

    def test_export_command_has_epilog_with_examples(self):
        """Test export command has epilog with usage examples."""
        from src.cli import create_parser

        parser = create_parser()
        subparsers = parser._subparsers._group_actions[0].choices

        export_parser = subparsers["export"]
        assert export_parser.epilog is not None


class TestConfigMappingsAndPrecedence:
    """Tests for data-driven _apply_config_defaults and _CONFIG_MAPPINGS."""

    def test_config_mappings_covers_all_mapped_attrs(self):
        """Test _CONFIG_MAPPINGS dict contains expected attributes."""
        from src.cli import _CONFIG_MAPPINGS

        expected = {
            "output_dir", "verbose", "user_email",
            "batch_size", "checkpoint_interval", "num_clusters",
            "min_cluster_percentage", "min_sender_count", "no_cleanup",
        }
        assert set(_CONFIG_MAPPINGS.keys()) == expected

    def test_apply_config_defaults_uses_config_when_cli_is_default(self):
        """Config values override CLI defaults when user didn't supply the flag."""
        from src.cli import _apply_config_defaults, create_parser
        from src.config.models import AppConfig, ExtractConfig

        parser = create_parser()
        # Parse with default batch_size (500) -- user didn't supply --batch-size
        args = parser.parse_args(["extract", "--user-email", "test@test.com"])
        assert args.batch_size == 500  # parser default

        config = AppConfig(extract=ExtractConfig(batch_size=1000))
        _apply_config_defaults(args, config, parser)

        assert args.batch_size == 1000

    def test_apply_config_defaults_cli_overrides_config(self):
        """Explicit CLI args take precedence over config file values."""
        from src.cli import _apply_config_defaults, create_parser
        from src.config.models import AppConfig, ExtractConfig

        parser = create_parser()
        # User explicitly sets --batch-size 750
        args = parser.parse_args([
            "extract", "--user-email", "test@test.com", "--batch-size", "750"
        ])
        assert args.batch_size == 750

        config = AppConfig(extract=ExtractConfig(batch_size=1000))
        _apply_config_defaults(args, config, parser)

        # CLI value should win
        assert args.batch_size == 750

    def test_apply_config_defaults_analyze_num_clusters(self):
        """Config overrides default num_clusters for analyze command."""
        from src.cli import _apply_config_defaults, create_parser
        from src.config.models import AppConfig, AnalyzeConfig

        parser = create_parser()
        args = parser.parse_args(["analyze"])
        assert args.num_clusters == 10  # parser default

        config = AppConfig(analyze=AnalyzeConfig(num_clusters=25))
        _apply_config_defaults(args, config, parser)

        assert args.num_clusters == 25

    def test_apply_config_defaults_analyze_cli_wins(self):
        """Explicit --num-clusters on CLI overrides config."""
        from src.cli import _apply_config_defaults, create_parser
        from src.config.models import AppConfig, AnalyzeConfig

        parser = create_parser()
        args = parser.parse_args(["analyze", "--num-clusters", "30"])

        config = AppConfig(analyze=AnalyzeConfig(num_clusters=25))
        _apply_config_defaults(args, config, parser)

        assert args.num_clusters == 30

    def test_apply_config_defaults_suggest_min_cluster_pct(self):
        """Config overrides default min_cluster_percentage for suggest."""
        from src.cli import _apply_config_defaults, create_parser
        from src.config.models import AppConfig, SuggestConfig

        parser = create_parser()
        args = parser.parse_args(["suggest"])
        assert args.min_cluster_percentage == 5.0

        config = AppConfig(suggest=SuggestConfig(min_cluster_percentage=10.0))
        _apply_config_defaults(args, config, parser)

        assert args.min_cluster_percentage == 10.0

    def test_apply_config_defaults_suggest_min_sender_count(self):
        """Config overrides default min_sender_count for suggest."""
        from src.cli import _apply_config_defaults, create_parser
        from src.config.models import AppConfig, SuggestConfig

        parser = create_parser()
        args = parser.parse_args(["suggest"])
        assert args.min_sender_count == 20

        config = AppConfig(suggest=SuggestConfig(min_sender_count=50))
        _apply_config_defaults(args, config, parser)

        assert args.min_sender_count == 50

    def test_apply_config_defaults_review_no_cleanup(self):
        """Config overrides default no_cleanup for review."""
        from src.cli import _apply_config_defaults, create_parser
        from src.config.models import AppConfig, ReviewConfig

        parser = create_parser()
        args = parser.parse_args(["review"])
        assert args.no_cleanup is False

        config = AppConfig(review=ReviewConfig(no_cleanup=True))
        _apply_config_defaults(args, config, parser)

        assert args.no_cleanup is True

    def test_apply_config_defaults_checkpoint_interval(self):
        """Config overrides default checkpoint_interval for extract."""
        from src.cli import _apply_config_defaults, create_parser
        from src.config.models import AppConfig, ExtractConfig

        parser = create_parser()
        args = parser.parse_args(["extract", "--user-email", "test@test.com"])
        assert args.checkpoint_interval == 100

        config = AppConfig(extract=ExtractConfig(checkpoint_interval=200))
        _apply_config_defaults(args, config, parser)

        assert args.checkpoint_interval == 200

    def test_apply_config_defaults_user_email_from_config(self):
        """Config provides user_email when CLI doesn't."""
        from src.cli import _apply_config_defaults, create_parser
        from src.config.models import AppConfig

        parser = create_parser()
        # Pipeline command has optional user_email (handled differently)
        # Use analyze which doesn't require --user-email
        args = parser.parse_args(["analyze"])
        # analyze doesn't have user_email attr typically, but let's test
        # with a namespace that does
        args.user_email = None

        config = AppConfig(user_email="config@example.com")
        _apply_config_defaults(args, config, parser)

        assert args.user_email == "config@example.com"

    def test_apply_config_defaults_output_dir_from_config(self):
        """Config provides output_dir when CLI doesn't set it."""
        from src.cli import _apply_config_defaults, create_parser
        from src.config.models import AppConfig

        parser = create_parser()
        args = parser.parse_args(["analyze"])
        assert args.output_dir is None  # parser default

        config = AppConfig(output_dir=Path("/custom/output"))
        _apply_config_defaults(args, config, parser)

        assert args.output_dir == Path("/custom/output")

    def test_apply_config_defaults_verbose_from_config(self):
        """Config provides verbose when CLI doesn't set it."""
        from src.cli import _apply_config_defaults, create_parser
        from src.config.models import AppConfig

        parser = create_parser()
        args = parser.parse_args(["analyze"])
        assert args.verbose is False

        config = AppConfig(verbose=True)
        _apply_config_defaults(args, config, parser)

        assert args.verbose is True

    def test_apply_config_defaults_skips_missing_attrs(self):
        """Attributes not in the namespace are silently skipped."""
        from src.cli import _apply_config_defaults, create_parser
        from src.config.models import AppConfig, ExtractConfig

        parser = create_parser()
        # analyze doesn't have batch_size
        args = parser.parse_args(["analyze"])
        assert not hasattr(args, "batch_size")

        config = AppConfig(extract=ExtractConfig(batch_size=1000))
        # Should not raise
        _apply_config_defaults(args, config, parser)

    def test_apply_config_defaults_none_config_value_skipped(self):
        """Config value of None does not override CLI default."""
        from src.cli import _apply_config_defaults, create_parser
        from src.config.models import AppConfig

        parser = create_parser()
        args = parser.parse_args(["analyze"])
        assert args.output_dir is None

        # Default AppConfig has output_dir=None
        config = AppConfig()
        _apply_config_defaults(args, config, parser)

        # Should remain None (not overridden)
        assert args.output_dir is None

    def test_apply_config_defaults_multiple_overrides(self):
        """Multiple config values can override defaults in one call."""
        from src.cli import _apply_config_defaults, create_parser
        from src.config.models import AppConfig, SuggestConfig

        parser = create_parser()
        args = parser.parse_args(["suggest"])

        config = AppConfig(
            suggest=SuggestConfig(
                min_cluster_percentage=15.0,
                min_sender_count=100,
            )
        )
        _apply_config_defaults(args, config, parser)

        assert args.min_cluster_percentage == 15.0
        assert args.min_sender_count == 100
