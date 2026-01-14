"""
Unit tests for CLI entry point modules.

Tests cover:
- src/cli.py - Main CLI with argparse, commands (extract, analyze, suggest, review, pipeline)
- src/main.py - Alternative entry point with EmailProcessorCLI class

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

    @patch("src.cli.PathConfig")
    @patch("src.cli.logger")
    def test_setup_output_directory_with_custom_path(self, mock_logger, mock_path_config):
        """Test setup with custom output directory."""
        from src.cli import setup_output_directory

        args = argparse.Namespace(output_dir=Path("/custom/output"))

        setup_output_directory(args)

        mock_path_config.set_output_dir.assert_called_once_with(Path("/custom/output"))
        mock_path_config.ensure_output_dir_exists.assert_called_once()

    @patch("src.cli.PathConfig")
    @patch("src.cli.logger")
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

    @patch("src.cli.save_json")
    @patch("src.cli.PathConfig")
    @patch("src.cli.logger")
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

    @patch("src.cli.save_json")
    @patch("src.cli.PathConfig")
    @patch("src.cli.logger")
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

    @patch("src.cli.PathConfig")
    @patch("src.cli.logger")
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

    @patch("src.cli.PathConfig")
    @patch("src.cli.logger")
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

    @patch("src.cli.save_json")
    @patch("src.cli.PathConfig")
    @patch("src.cli.logger")
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
        mock_result.corpus = MagicMock()
        mock_result.corpus.model_dump.return_value = {}
        mock_extractor.extract_all.return_value = mock_result
        mock_extractor_class.return_value = mock_extractor

        result = cmd_extract(args)

        # Should still succeed but log warning
        assert result == 0
        mock_logger.warning.assert_called()


class TestCmdAnalyze:
    """Test cases for cmd_analyze() function."""

    @patch("src.cli.save_json")
    @patch("src.cli.load_json")
    @patch("src.cli.PathConfig")
    @patch("src.cli.logger")
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
        mock_analysis.return_value = mock_results

        result = cmd_analyze(args)

        assert result == 0
        mock_analysis.assert_called_once()
        mock_save_json.assert_called_once()

    @patch("src.cli.save_json")
    @patch("src.cli.load_json")
    @patch("src.cli.PathConfig")
    @patch("src.cli.logger")
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
        mock_analysis.return_value = mock_results

        result = cmd_analyze(args)

        # Verify custom path used for loading
        mock_load_json.assert_called_once_with(Path("/custom/corpus.json"))

    @patch("src.cli.load_json")
    @patch("src.cli.PathConfig")
    @patch("src.cli.logger")
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

    @patch("src.cli.load_json")
    @patch("src.cli.PathConfig")
    @patch("src.cli.logger")
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

    @patch("src.cli.save_json")
    @patch("src.cli.load_json")
    @patch("src.cli.PathConfig")
    @patch("src.cli.logger")
    def test_cmd_suggest_success(self, mock_logger, mock_path_config, mock_load_json, mock_save_json):
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

    @patch("src.cli.load_json")
    @patch("src.cli.PathConfig")
    @patch("src.cli.logger")
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

    @patch("src.cli.save_json")
    @patch("src.cli.load_json")
    @patch("src.cli.PathConfig")
    @patch("src.cli.logger")
    @patch("src.generators.category_generator.CategoryGenerator")
    @patch("src.models.analysis_results.AnalysisResults")
    def test_cmd_suggest_with_custom_paths(self, mock_results_class, mock_gen_class, mock_logger, mock_path_config, mock_load_json, mock_save):
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

        with patch("builtins.open", mock_open()):
            result = cmd_suggest(args)

            mock_load_json.assert_called_once_with(Path("/custom/analysis.json"))
            # Verify custom suggestions path is used
            call_args = mock_save.call_args
            assert call_args[0][1] == Path("/custom/suggestions.json")

    @patch("src.cli.load_json")
    @patch("src.cli.PathConfig")
    @patch("src.cli.logger")
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

    @patch("src.cli.load_json")
    @patch("src.cli.PathConfig")
    @patch("src.cli.logger")
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

    @patch("src.cli.load_json")
    @patch("src.cli.PathConfig")
    @patch("src.cli.logger")
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

    @patch("src.cli.load_json")
    @patch("src.cli.PathConfig")
    @patch("src.cli.logger")
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

    @patch("src.cli.load_json")
    @patch("src.cli.PathConfig")
    @patch("src.cli.logger")
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

    @patch("src.cli.cmd_review")
    @patch("src.cli.cmd_suggest")
    @patch("src.cli.cmd_analyze")
    @patch("src.cli.cmd_extract")
    @patch("src.cli.logger")
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

    @patch("src.cli.cmd_extract")
    @patch("src.cli.logger")
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

    @patch("src.cli.cmd_analyze")
    @patch("src.cli.cmd_extract")
    @patch("src.cli.logger")
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

    @patch("src.cli.cmd_suggest")
    @patch("src.cli.cmd_analyze")
    @patch("src.cli.cmd_extract")
    @patch("src.cli.logger")
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

    @patch("src.cli.cmd_review")
    @patch("src.cli.cmd_suggest")
    @patch("src.cli.cmd_analyze")
    @patch("src.cli.cmd_extract")
    @patch("src.cli.logger")
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
# Tests for main.py - EmailProcessorCLI class
# =============================================================================

class TestEmailProcessorCLIInit:
    """Test cases for EmailProcessorCLI.__init__() in main.py."""

    @patch("src.main.ensure_output_dir")
    @patch("src.main.logger")
    def test_init_creates_output_dir(self, mock_logger, mock_ensure):
        """Test initialization creates output directory."""
        from src.main import EmailProcessorCLI

        cli = EmailProcessorCLI(
            output_dir=Path("/output"),
            user_email="test@example.com"
        )

        assert cli.output_dir == Path("/output")
        assert cli.user_email == "test@example.com"
        mock_ensure.assert_called_once_with(Path("/output"))

    @patch("src.main.ensure_output_dir")
    @patch("src.main.logger")
    def test_init_logs_initialization(self, mock_logger, mock_ensure):
        """Test initialization logs info message."""
        from src.main import EmailProcessorCLI

        cli = EmailProcessorCLI(
            output_dir=Path("/output"),
            user_email="test@example.com"
        )

        mock_logger.info.assert_called()


class TestEmailProcessorCLIExtract:
    """Test cases for EmailProcessorCLI.extract() method."""

    @patch("src.main.save_json")
    @patch("src.main.ensure_output_dir")
    @patch("src.main.logger")
    def test_extract_success(self, mock_logger, mock_ensure, mock_save):
        """Test successful extraction."""
        from src.main import EmailProcessorCLI

        cli = EmailProcessorCLI(
            output_dir=Path("/output"),
            user_email="test@example.com"
        )

        with patch("src.main.EmailExtractor") as mock_extractor_class:
            mock_extractor = MagicMock()
            mock_result = MagicMock()
            mock_result.success_count = 100
            mock_result.failure_count = 0
            mock_result.corpus = MagicMock()
            mock_result.corpus.model_dump.return_value = {}
            mock_result.failed_emails = []
            mock_extractor.extract_all.return_value = mock_result
            mock_extractor_class.return_value = mock_extractor

            result = cli.extract(batch_size=500, checkpoint_interval=100)

            assert result is True
            mock_save.assert_called_once()

    @patch("src.main.save_json")
    @patch("src.main.ensure_output_dir")
    @patch("src.main.logger")
    def test_extract_writes_error_log(self, mock_logger, mock_ensure, mock_save):
        """Test extraction writes error log when failures occur."""
        from src.main import EmailProcessorCLI

        cli = EmailProcessorCLI(
            output_dir=Path("/output"),
            user_email="test@example.com"
        )

        with patch("src.main.EmailExtractor") as mock_extractor_class:
            mock_extractor = MagicMock()
            mock_result = MagicMock()
            mock_result.success_count = 95
            mock_result.failure_count = 5
            mock_result.corpus = MagicMock()
            mock_result.corpus.model_dump.return_value = {}

            mock_error = MagicMock()
            mock_error.timestamp = datetime.now()
            mock_error.error_type = "timeout"
            mock_error.email_id = "msg123"
            mock_error.error_message = "Connection timeout"
            mock_result.failed_emails = [mock_error]

            mock_extractor.extract_all.return_value = mock_result
            mock_extractor_class.return_value = mock_extractor

            with patch("builtins.open", mock_open()):
                result = cli.extract()

                assert result is True

    @patch("src.main.ensure_output_dir")
    @patch("src.main.logger")
    def test_extract_failure(self, mock_logger, mock_ensure):
        """Test extraction handles failure."""
        from src.main import EmailProcessorCLI

        cli = EmailProcessorCLI(
            output_dir=Path("/output"),
            user_email="test@example.com"
        )

        with patch("src.main.EmailExtractor") as mock_extractor_class:
            mock_extractor_class.side_effect = Exception("Connection failed")

            result = cli.extract()

            assert result is False


class TestEmailProcessorCLIAnalyze:
    """Test cases for EmailProcessorCLI.analyze() method."""

    @patch("src.main.save_json")
    @patch("src.main.load_json")
    @patch("src.main.ensure_output_dir")
    @patch("src.main.logger")
    def test_analyze_success(self, mock_logger, mock_ensure, mock_load, mock_save):
        """Test successful analysis."""
        from src.main import EmailProcessorCLI

        cli = EmailProcessorCLI(
            output_dir=Path("/output"),
            user_email="test@example.com"
        )

        mock_load.return_value = {
            "extraction_metadata": {
                "extraction_date": "2024-01-01T00:00:00",
                "total_emails": 100,
                "source": "test",
                "user_email": "test@example.com"
            },
            "emails": []
        }

        with patch("src.main.Corpus") as mock_corpus_class:
            with patch("src.main.run_full_analysis") as mock_analysis:
                mock_corpus = MagicMock()
                mock_corpus.emails = []
                mock_corpus_class.return_value = mock_corpus

                mock_results = MagicMock()
                mock_results.model_dump.return_value = {}
                mock_analysis.return_value = mock_results

                result = cli.analyze(num_clusters=10)

                assert result is True
                mock_save.assert_called_once()

    @patch("src.main.load_json")
    @patch("src.main.ensure_output_dir")
    @patch("src.main.logger")
    def test_analyze_file_not_found(self, mock_logger, mock_ensure, mock_load):
        """Test analysis handles missing corpus file."""
        from src.main import EmailProcessorCLI

        cli = EmailProcessorCLI(
            output_dir=Path("/output"),
            user_email="test@example.com"
        )

        mock_load.side_effect = FileNotFoundError("Corpus not found")

        result = cli.analyze()

        assert result is False

    @patch("src.main.load_json")
    @patch("src.main.ensure_output_dir")
    @patch("src.main.logger")
    def test_analyze_general_failure(self, mock_logger, mock_ensure, mock_load):
        """Test analysis handles general failure."""
        from src.main import EmailProcessorCLI

        cli = EmailProcessorCLI(
            output_dir=Path("/output"),
            user_email="test@example.com"
        )

        mock_load.side_effect = Exception("Unexpected error")

        result = cli.analyze()

        assert result is False


class TestEmailProcessorCLISuggest:
    """Test cases for EmailProcessorCLI.suggest() method."""

    @patch("src.main.save_json")
    @patch("src.main.load_json")
    @patch("src.main.ensure_output_dir")
    @patch("src.main.logger")
    def test_suggest_success(self, mock_logger, mock_ensure, mock_load, mock_save):
        """Test successful suggestion generation."""
        from src.main import EmailProcessorCLI

        cli = EmailProcessorCLI(
            output_dir=Path("/output"),
            user_email="test@example.com"
        )

        mock_load.return_value = {
            "sender_analysis": {"top_senders": [], "top_domains": [], "unique_senders": 0, "unique_domains": 0},
            "subject_patterns": {"common_prefixes": {}, "numbered_patterns": {}, "top_keywords": [], "bracket_tags": [], "total_subjects_analyzed": 0},
            "content_clusters": [],
            "temporal_patterns": {"frequency_distribution": {}, "sender_frequencies": {}},
            "volume_stats": {"total_emails": 0, "unique_senders": 0, "date_range": {}, "with_attachments": 0, "attachment_percentage": 0, "avg_body_length_chars": 0, "emails_per_day": 0}
        }

        with patch("src.main.AnalysisResults") as mock_results_class:
            with patch("src.main.CategoryGenerator") as mock_gen_class:
                mock_results = MagicMock()
                mock_results_class.return_value = mock_results

                mock_gen = MagicMock()
                mock_category = MagicMock()
                mock_category.source = MagicMock()
                mock_category.source.value = "content_cluster"
                mock_category.model_dump.return_value = {}
                mock_gen.generate_suggestions.return_value = [mock_category]
                mock_gen.generate_report.return_value = "# Report"
                mock_gen_class.return_value = mock_gen

                with patch("builtins.open", mock_open()):
                    result = cli.suggest()

                    assert result is True

    @patch("src.main.load_json")
    @patch("src.main.ensure_output_dir")
    @patch("src.main.logger")
    def test_suggest_file_not_found(self, mock_logger, mock_ensure, mock_load):
        """Test suggestion handles missing analysis file."""
        from src.main import EmailProcessorCLI

        cli = EmailProcessorCLI(
            output_dir=Path("/output"),
            user_email="test@example.com"
        )

        mock_load.side_effect = FileNotFoundError("Analysis not found")

        result = cli.suggest()

        assert result is False

    @patch("src.main.load_json")
    @patch("src.main.ensure_output_dir")
    @patch("src.main.logger")
    def test_suggest_general_failure(self, mock_logger, mock_ensure, mock_load):
        """Test suggestion handles general failure."""
        from src.main import EmailProcessorCLI

        cli = EmailProcessorCLI(
            output_dir=Path("/output"),
            user_email="test@example.com"
        )

        mock_load.side_effect = Exception("Unexpected error")

        result = cli.suggest()

        assert result is False


class TestEmailProcessorCLIReview:
    """Test cases for EmailProcessorCLI.review() method."""

    @patch("src.main.load_json")
    @patch("src.main.ensure_output_dir")
    @patch("src.main.logger")
    def test_review_success(self, mock_logger, mock_ensure, mock_load):
        """Test successful review."""
        from src.main import EmailProcessorCLI

        cli = EmailProcessorCLI(
            output_dir=Path("/output"),
            user_email="test@example.com"
        )

        mock_load.return_value = [{
            "category_id": "cat1",
            "category_name": "Test",
            "description": "Test desc",
            "confidence": 0.8,
            "source": "content_cluster"
        }]

        with patch("src.main.Category") as mock_category_class:
            with patch("src.main.review_categories") as mock_review:
                with patch("src.main.cleanup_intermediate_files") as mock_cleanup:
                    mock_category = MagicMock()
                    mock_category_class.return_value = mock_category
                    mock_review.return_value = [mock_category]

                    result = cli.review(enable_cleanup=True)

                    assert result is True
                    mock_cleanup.assert_called_once()

    @patch("src.main.load_json")
    @patch("src.main.ensure_output_dir")
    @patch("src.main.logger")
    def test_review_without_cleanup(self, mock_logger, mock_ensure, mock_load):
        """Test review without cleanup."""
        from src.main import EmailProcessorCLI

        cli = EmailProcessorCLI(
            output_dir=Path("/output"),
            user_email="test@example.com"
        )

        mock_load.return_value = []

        with patch("src.main.review_categories") as mock_review:
            with patch("src.main.cleanup_intermediate_files") as mock_cleanup:
                mock_review.return_value = []

                result = cli.review(enable_cleanup=False)

                assert result is True
                mock_cleanup.assert_not_called()

    @patch("src.main.load_json")
    @patch("src.main.ensure_output_dir")
    @patch("src.main.logger")
    def test_review_file_not_found(self, mock_logger, mock_ensure, mock_load):
        """Test review handles missing suggestions file."""
        from src.main import EmailProcessorCLI

        cli = EmailProcessorCLI(
            output_dir=Path("/output"),
            user_email="test@example.com"
        )

        mock_load.side_effect = FileNotFoundError("Suggestions not found")

        result = cli.review()

        assert result is False

    @patch("src.main.load_json")
    @patch("src.main.ensure_output_dir")
    @patch("src.main.logger")
    def test_review_general_failure(self, mock_logger, mock_ensure, mock_load):
        """Test review handles general failure."""
        from src.main import EmailProcessorCLI

        cli = EmailProcessorCLI(
            output_dir=Path("/output"),
            user_email="test@example.com"
        )

        mock_load.side_effect = Exception("Review error")

        result = cli.review()

        assert result is False


class TestEmailProcessorCLIPipeline:
    """Test cases for EmailProcessorCLI.pipeline() method."""

    @patch("src.main.ensure_output_dir")
    @patch("src.main.logger")
    def test_pipeline_success(self, mock_logger, mock_ensure):
        """Test successful pipeline execution."""
        from src.main import EmailProcessorCLI

        cli = EmailProcessorCLI(
            output_dir=Path("/output"),
            user_email="test@example.com"
        )

        with patch.object(cli, "extract") as mock_extract:
            with patch.object(cli, "analyze") as mock_analyze:
                with patch.object(cli, "suggest") as mock_suggest:
                    with patch.object(cli, "review") as mock_review:
                        mock_extract.return_value = True
                        mock_analyze.return_value = True
                        mock_suggest.return_value = True
                        mock_review.return_value = True

                        result = cli.pipeline()

                        assert result is True
                        mock_extract.assert_called_once()
                        mock_analyze.assert_called_once()
                        mock_suggest.assert_called_once()
                        mock_review.assert_called_once()

    @patch("src.main.ensure_output_dir")
    @patch("src.main.logger")
    def test_pipeline_extract_failure(self, mock_logger, mock_ensure):
        """Test pipeline fails on extract error."""
        from src.main import EmailProcessorCLI

        cli = EmailProcessorCLI(
            output_dir=Path("/output"),
            user_email="test@example.com"
        )

        with patch.object(cli, "extract") as mock_extract:
            mock_extract.return_value = False

            result = cli.pipeline()

            assert result is False

    @patch("src.main.ensure_output_dir")
    @patch("src.main.logger")
    def test_pipeline_analyze_failure(self, mock_logger, mock_ensure):
        """Test pipeline fails on analyze error."""
        from src.main import EmailProcessorCLI

        cli = EmailProcessorCLI(
            output_dir=Path("/output"),
            user_email="test@example.com"
        )

        with patch.object(cli, "extract") as mock_extract:
            with patch.object(cli, "analyze") as mock_analyze:
                mock_extract.return_value = True
                mock_analyze.return_value = False

                result = cli.pipeline()

                assert result is False

    @patch("src.main.ensure_output_dir")
    @patch("src.main.logger")
    def test_pipeline_keyboard_interrupt(self, mock_logger, mock_ensure):
        """Test pipeline handles KeyboardInterrupt."""
        from src.main import EmailProcessorCLI

        cli = EmailProcessorCLI(
            output_dir=Path("/output"),
            user_email="test@example.com"
        )

        with patch.object(cli, "extract") as mock_extract:
            mock_extract.side_effect = KeyboardInterrupt()

            result = cli.pipeline()

            assert result is False

    @patch("src.main.ensure_output_dir")
    @patch("src.main.logger")
    def test_pipeline_general_exception(self, mock_logger, mock_ensure):
        """Test pipeline handles general exception."""
        from src.main import EmailProcessorCLI

        cli = EmailProcessorCLI(
            output_dir=Path("/output"),
            user_email="test@example.com"
        )

        with patch.object(cli, "extract") as mock_extract:
            mock_extract.side_effect = Exception("Pipeline error")

            result = cli.pipeline()

            assert result is False


class TestMainPyMain:
    """Test cases for main() function in main.py."""

    @patch("src.main.EmailProcessorCLI")
    @patch("src.main.sys.exit")
    def test_main_extract_command(self, mock_exit, mock_cli_class):
        """Test main executes extract command."""
        from src.main import main

        mock_cli = MagicMock()
        mock_cli.extract.return_value = True
        mock_cli_class.return_value = mock_cli

        with patch("sys.argv", ["main.py", "extract"]):
            with patch("argparse.ArgumentParser.parse_args") as mock_parse:
                mock_args = MagicMock()
                mock_args.command = "extract"
                mock_args.output_dir = Path("/output")
                mock_args.user_email = "test@example.com"
                mock_args.batch_size = 500
                mock_args.checkpoint_interval = 100
                mock_parse.return_value = mock_args

                main()

                mock_cli.extract.assert_called_once()
                mock_exit.assert_called_with(0)

    @patch("src.main.EmailProcessorCLI")
    @patch("src.main.sys.exit")
    def test_main_analyze_command(self, mock_exit, mock_cli_class):
        """Test main executes analyze command."""
        from src.main import main

        mock_cli = MagicMock()
        mock_cli.analyze.return_value = True
        mock_cli_class.return_value = mock_cli

        with patch("sys.argv", ["main.py", "analyze"]):
            with patch("argparse.ArgumentParser.parse_args") as mock_parse:
                mock_args = MagicMock()
                mock_args.command = "analyze"
                mock_args.output_dir = Path("/output")
                mock_args.user_email = "test@example.com"
                mock_args.clusters = 10
                mock_parse.return_value = mock_args

                main()

                mock_cli.analyze.assert_called_once()

    @patch("src.main.EmailProcessorCLI")
    @patch("src.main.sys.exit")
    def test_main_suggest_command(self, mock_exit, mock_cli_class):
        """Test main executes suggest command."""
        from src.main import main

        mock_cli = MagicMock()
        mock_cli.suggest.return_value = True
        mock_cli_class.return_value = mock_cli

        with patch("sys.argv", ["main.py", "suggest"]):
            with patch("argparse.ArgumentParser.parse_args") as mock_parse:
                mock_args = MagicMock()
                mock_args.command = "suggest"
                mock_args.output_dir = Path("/output")
                mock_args.user_email = "test@example.com"
                mock_args.min_cluster_pct = 5.0
                mock_args.min_sender_count = 20
                mock_parse.return_value = mock_args

                main()

                mock_cli.suggest.assert_called_once()

    @patch("src.main.EmailProcessorCLI")
    @patch("src.main.sys.exit")
    def test_main_review_command(self, mock_exit, mock_cli_class):
        """Test main executes review command."""
        from src.main import main

        mock_cli = MagicMock()
        mock_cli.review.return_value = True
        mock_cli_class.return_value = mock_cli

        with patch("sys.argv", ["main.py", "review"]):
            with patch("argparse.ArgumentParser.parse_args") as mock_parse:
                mock_args = MagicMock()
                mock_args.command = "review"
                mock_args.output_dir = Path("/output")
                mock_args.user_email = "test@example.com"
                mock_args.no_cleanup = False
                mock_parse.return_value = mock_args

                main()

                mock_cli.review.assert_called_once()

    @patch("src.main.EmailProcessorCLI")
    @patch("src.main.sys.exit")
    def test_main_pipeline_command(self, mock_exit, mock_cli_class):
        """Test main executes pipeline command."""
        from src.main import main

        mock_cli = MagicMock()
        mock_cli.pipeline.return_value = True
        mock_cli_class.return_value = mock_cli

        with patch("sys.argv", ["main.py", "pipeline"]):
            with patch("argparse.ArgumentParser.parse_args") as mock_parse:
                mock_args = MagicMock()
                mock_args.command = "pipeline"
                mock_args.output_dir = Path("/output")
                mock_args.user_email = "test@example.com"
                mock_args.batch_size = 500
                mock_args.checkpoint_interval = 100
                mock_args.clusters = 10
                mock_args.min_cluster_pct = 5.0
                mock_args.min_sender_count = 20
                mock_parse.return_value = mock_args

                main()

                mock_cli.pipeline.assert_called_once()

    @patch("src.main.sys.exit")
    def test_main_no_command(self, mock_exit):
        """Test main shows help when no command provided."""
        from src.main import main

        with patch("argparse.ArgumentParser.parse_args") as mock_parse:
            mock_args = MagicMock()
            mock_args.command = None
            mock_parse.return_value = mock_args

            with patch("argparse.ArgumentParser.print_help"):
                main()

                mock_exit.assert_called_with(1)

    def test_main_keyboard_interrupt(self):
        """Test main handles KeyboardInterrupt."""
        from src.main import main

        with patch("argparse.ArgumentParser.parse_args") as mock_parse:
            mock_args = MagicMock()
            mock_args.command = "extract"
            mock_args.output_dir = Path("/output")
            mock_args.user_email = "test@example.com"
            mock_args.batch_size = 500
            mock_args.checkpoint_interval = 100
            mock_parse.return_value = mock_args

            with patch("src.main.EmailProcessorCLI") as mock_cli_class:
                mock_cli = MagicMock()
                mock_cli.extract.side_effect = KeyboardInterrupt()
                mock_cli_class.return_value = mock_cli

                with pytest.raises(SystemExit) as exc_info:
                    main()

                assert exc_info.value.code == 130

    @patch("src.main.EmailProcessorCLI")
    @patch("src.main.sys.exit")
    @patch("src.main.logger")
    def test_main_general_exception(self, mock_logger, mock_exit, mock_cli_class):
        """Test main handles general exception."""
        from src.main import main

        mock_cli = MagicMock()
        mock_cli.extract.side_effect = Exception("Unexpected error")
        mock_cli_class.return_value = mock_cli

        with patch("sys.argv", ["main.py", "extract"]):
            with patch("argparse.ArgumentParser.parse_args") as mock_parse:
                mock_args = MagicMock()
                mock_args.command = "extract"
                mock_args.output_dir = Path("/output")
                mock_args.user_email = "test@example.com"
                mock_args.batch_size = 500
                mock_args.checkpoint_interval = 100
                mock_parse.return_value = mock_args

                main()

                mock_exit.assert_called_with(1)

    @patch("src.main.EmailProcessorCLI")
    @patch("src.main.sys.exit")
    def test_main_command_failure_exits_with_1(self, mock_exit, mock_cli_class):
        """Test main exits with 1 when command fails."""
        from src.main import main

        mock_cli = MagicMock()
        mock_cli.extract.return_value = False
        mock_cli_class.return_value = mock_cli

        with patch("sys.argv", ["main.py", "extract"]):
            with patch("argparse.ArgumentParser.parse_args") as mock_parse:
                mock_args = MagicMock()
                mock_args.command = "extract"
                mock_args.output_dir = Path("/output")
                mock_args.user_email = "test@example.com"
                mock_args.batch_size = 500
                mock_args.checkpoint_interval = 100
                mock_parse.return_value = mock_args

                main()

                mock_exit.assert_called_with(1)
