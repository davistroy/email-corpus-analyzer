"""
Unit tests for Scheduler (Phase 6, Item 6.3).

Tests the scheduler system that sets up automated processing:
- ScheduleStatus model with enabled, interval_hours, next_run, last_run, last_result
- Scheduler class with setup/run/status/disable
- Windows Task Scheduler XML generation and schtasks registration
- Linux/macOS crontab entry generation
- CLI integration: scheduler subcommand with setup/run/status/disable sub-actions
- Uses SchedulerConfig from config

TDD: These tests are written first, implementation follows.
"""

import json
from datetime import datetime, timedelta
from unittest.mock import MagicMock, mock_open, patch

from src.config.models import SchedulerConfig

# =============================================================================
# ScheduleStatus Model Tests
# =============================================================================


class TestScheduleStatusModel:
    """Tests for the ScheduleStatus pydantic model."""

    def test_schedule_status_default_values(self):
        """ScheduleStatus can be created with all defaults."""
        from src.automation.scheduler import ScheduleStatus

        status = ScheduleStatus()
        assert status.enabled is False
        assert status.interval_hours == 24
        assert status.next_run is None
        assert status.last_run is None
        assert status.last_result is None

    def test_schedule_status_full_values(self):
        """ScheduleStatus can be created with all fields set."""
        from src.automation.scheduler import ScheduleStatus

        now = datetime(2026, 2, 28, 14, 0, 0)
        status = ScheduleStatus(
            enabled=True,
            interval_hours=12,
            next_run=now + timedelta(hours=12),
            last_run=now,
            last_result="success",
        )
        assert status.enabled is True
        assert status.interval_hours == 12
        assert status.next_run == now + timedelta(hours=12)
        assert status.last_run == now
        assert status.last_result == "success"

    def test_schedule_status_serialization(self):
        """ScheduleStatus round-trips through JSON serialization."""
        from src.automation.scheduler import ScheduleStatus

        now = datetime(2026, 2, 28, 14, 0, 0)
        status = ScheduleStatus(
            enabled=True,
            interval_hours=6,
            next_run=now,
            last_run=now - timedelta(hours=6),
            last_result="success",
        )
        data = status.model_dump(mode="json")
        restored = ScheduleStatus(**data)
        assert restored.enabled == status.enabled
        assert restored.interval_hours == status.interval_hours
        assert restored.last_result == status.last_result

    def test_schedule_status_last_result_values(self):
        """ScheduleStatus last_result accepts various string values."""
        from src.automation.scheduler import ScheduleStatus

        for result in ["success", "error: timeout", "error: auth failed", None]:
            status = ScheduleStatus(last_result=result)
            assert status.last_result == result


# =============================================================================
# Scheduler Class Tests
# =============================================================================


class TestScheduler:
    """Tests for the Scheduler class."""

    def test_scheduler_init_with_defaults(self):
        """Scheduler initializes with default SchedulerConfig."""
        from src.automation.scheduler import Scheduler

        scheduler = Scheduler()
        assert scheduler.config is not None
        assert isinstance(scheduler.config, SchedulerConfig)

    def test_scheduler_init_with_custom_config(self):
        """Scheduler initializes with custom SchedulerConfig."""
        from src.automation.scheduler import Scheduler

        config = SchedulerConfig(
            enabled=True,
            interval_hours=6,
            run_at="03:00",
            tasks=["extract", "analyze"],
        )
        scheduler = Scheduler(config=config)
        assert scheduler.config.interval_hours == 6
        assert scheduler.config.run_at == "03:00"

    def test_get_status_no_state_file(self):
        """get_status returns disabled status when no state file exists."""
        from src.automation.scheduler import Scheduler

        scheduler = Scheduler()
        with patch.object(scheduler, "_load_state", return_value=None):
            status = scheduler.get_status()
        assert status.enabled is False
        assert status.last_run is None
        assert status.next_run is None

    def test_get_status_with_state_file(self):
        """get_status returns status from saved state."""
        from src.automation.scheduler import Scheduler, ScheduleStatus

        scheduler = Scheduler()
        now = datetime(2026, 2, 28, 14, 0, 0)
        saved_status = ScheduleStatus(
            enabled=True,
            interval_hours=24,
            next_run=now + timedelta(hours=24),
            last_run=now,
            last_result="success",
        )
        with patch.object(scheduler, "_load_state", return_value=saved_status):
            status = scheduler.get_status()
        assert status.enabled is True
        assert status.last_result == "success"

    def test_disable_updates_state(self):
        """disable() sets enabled=False and saves state."""
        from src.automation.scheduler import Scheduler, ScheduleStatus

        scheduler = Scheduler()
        now = datetime(2026, 2, 28, 14, 0, 0)
        current_status = ScheduleStatus(
            enabled=True,
            interval_hours=24,
            next_run=now + timedelta(hours=24),
            last_run=now,
            last_result="success",
        )
        with (
            patch.object(scheduler, "_load_state", return_value=current_status),
            patch.object(scheduler, "_save_state") as mock_save,
        ):
            result = scheduler.disable()
        assert result.enabled is False
        mock_save.assert_called_once()
        saved_status = mock_save.call_args[0][0]
        assert saved_status.enabled is False

    def test_disable_when_already_disabled(self):
        """disable() is idempotent - works even if already disabled."""
        from src.automation.scheduler import Scheduler

        scheduler = Scheduler()
        with (
            patch.object(scheduler, "_load_state", return_value=None),
            patch.object(scheduler, "_save_state") as mock_save,
        ):
            result = scheduler.disable()
        assert result.enabled is False
        mock_save.assert_called_once()

    @patch("src.automation.scheduler.sys")
    def test_setup_detects_windows(self, mock_sys):
        """setup() detects Windows platform and calls Windows setup."""
        from src.automation.scheduler import Scheduler

        mock_sys.platform = "win32"
        scheduler = Scheduler()
        with (
            patch.object(scheduler, "_setup_windows", return_value=True) as mock_win,
            patch.object(scheduler, "_save_state"),
        ):
            result = scheduler.setup()
        mock_win.assert_called_once()
        assert result.enabled is True

    @patch("src.automation.scheduler.sys")
    def test_setup_detects_linux(self, mock_sys):
        """setup() detects Linux platform and calls crontab setup."""
        from src.automation.scheduler import Scheduler

        mock_sys.platform = "linux"
        scheduler = Scheduler()
        with (
            patch.object(scheduler, "_setup_cron", return_value=True) as mock_cron,
            patch.object(scheduler, "_save_state"),
        ):
            result = scheduler.setup()
        mock_cron.assert_called_once()
        assert result.enabled is True

    @patch("src.automation.scheduler.sys")
    def test_setup_detects_macos(self, mock_sys):
        """setup() detects macOS platform and calls crontab setup."""
        from src.automation.scheduler import Scheduler

        mock_sys.platform = "darwin"
        scheduler = Scheduler()
        with (
            patch.object(scheduler, "_setup_cron", return_value=True) as mock_cron,
            patch.object(scheduler, "_save_state"),
        ):
            result = scheduler.setup()
        mock_cron.assert_called_once()
        assert result.enabled is True

    @patch("src.automation.scheduler.sys")
    def test_setup_returns_disabled_on_failure(self, mock_sys):
        """setup() returns disabled status if platform setup fails."""
        from src.automation.scheduler import Scheduler

        mock_sys.platform = "win32"
        scheduler = Scheduler()
        with (
            patch.object(scheduler, "_setup_windows", return_value=False),
            patch.object(scheduler, "_save_state") as mock_save,
        ):
            result = scheduler.setup()
        assert result.enabled is False
        # State should still be saved (recording the failure)
        mock_save.assert_called_once()


# =============================================================================
# Windows Task Scheduler Tests
# =============================================================================


class TestSchedulerWindowsIntegration:
    """Tests for Windows Task Scheduler XML generation and registration."""

    def test_generate_task_xml_contains_required_elements(self):
        """Generated XML contains all required Task Scheduler elements."""
        from src.automation.scheduler import Scheduler

        config = SchedulerConfig(run_at="03:30", interval_hours=24)
        scheduler = Scheduler(config=config)
        xml_content = scheduler._generate_task_xml()

        # Must be valid XML with Task namespace
        assert '<?xml version="1.0"' in xml_content
        assert "http://schemas.microsoft.com/windows/2004/02/mit/task" in xml_content

        # Must contain a trigger with the configured time
        assert "03:30:00" in xml_content

        # Must contain python execution command
        assert "python" in xml_content.lower() or "Python" in xml_content
        assert "scheduler" in xml_content.lower() or "run" in xml_content.lower()

    def test_generate_task_xml_respects_interval(self):
        """Generated XML includes repetition interval for non-daily schedules."""
        from src.automation.scheduler import Scheduler

        config = SchedulerConfig(run_at="02:00", interval_hours=6)
        scheduler = Scheduler(config=config)
        xml_content = scheduler._generate_task_xml()

        # Should include repetition for 6-hour interval
        assert "PT6H" in xml_content

    def test_generate_task_xml_daily_schedule(self):
        """Generated XML uses daily trigger for 24-hour interval."""
        from src.automation.scheduler import Scheduler

        config = SchedulerConfig(run_at="02:00", interval_hours=24)
        scheduler = Scheduler(config=config)
        xml_content = scheduler._generate_task_xml()

        # Should have a calendar/daily trigger
        assert "02:00:00" in xml_content

    @patch("subprocess.run")
    def test_setup_windows_calls_schtasks(self, mock_run):
        """_setup_windows registers task via schtasks /Create."""
        from src.automation.scheduler import Scheduler

        mock_run.return_value = MagicMock(returncode=0, stdout="SUCCESS")
        scheduler = Scheduler()

        with (
            patch.object(scheduler, "_generate_task_xml", return_value="<Task/>"),
            patch("builtins.open", mock_open()),
            patch("pathlib.Path.unlink"),
        ):
            result = scheduler._setup_windows()

        assert result is True
        mock_run.assert_called_once()
        call_args = mock_run.call_args
        cmd = call_args[0][0] if call_args[0] else call_args[1].get("args", [])
        # Should use schtasks command
        assert "schtasks" in cmd[0].lower() or "schtasks" in str(cmd).lower()

    @patch("subprocess.run")
    def test_setup_windows_handles_schtasks_failure(self, mock_run):
        """_setup_windows returns False when schtasks fails."""
        from src.automation.scheduler import Scheduler

        mock_run.return_value = MagicMock(returncode=1, stderr="Access denied")
        scheduler = Scheduler()

        with (
            patch.object(scheduler, "_generate_task_xml", return_value="<Task/>"),
            patch("builtins.open", mock_open()),
            patch("pathlib.Path.unlink"),
        ):
            result = scheduler._setup_windows()

        assert result is False

    @patch("subprocess.run")
    def test_disable_windows_calls_schtasks_delete(self, mock_run):
        """_disable_windows removes task via schtasks /Delete."""
        from src.automation.scheduler import Scheduler

        mock_run.return_value = MagicMock(returncode=0)
        scheduler = Scheduler()
        result = scheduler._disable_windows()

        assert result is True
        call_args = mock_run.call_args
        cmd = call_args[0][0] if call_args[0] else call_args[1].get("args", [])
        assert "/Delete" in str(cmd) or "/delete" in str(cmd).lower()


# =============================================================================
# Cron (Linux/macOS) Tests
# =============================================================================


class TestSchedulerCronIntegration:
    """Tests for crontab entry generation for Linux/macOS."""

    def test_generate_cron_entry_daily(self):
        """Generate correct cron entry for daily (24h) schedule."""
        from src.automation.scheduler import Scheduler

        config = SchedulerConfig(run_at="02:00", interval_hours=24)
        scheduler = Scheduler(config=config)
        entry = scheduler._generate_cron_entry()

        # Daily at 02:00 -> "0 2 * * *"
        assert entry.startswith("0 2 * * *")
        assert "scheduler" in entry.lower() or "run" in entry.lower()

    def test_generate_cron_entry_every_6_hours(self):
        """Generate correct cron entry for 6-hour interval."""
        from src.automation.scheduler import Scheduler

        config = SchedulerConfig(run_at="02:00", interval_hours=6)
        scheduler = Scheduler(config=config)
        entry = scheduler._generate_cron_entry()

        # Every 6 hours -> "0 */6 * * *"
        assert "*/6" in entry

    def test_generate_cron_entry_every_12_hours(self):
        """Generate correct cron entry for 12-hour interval."""
        from src.automation.scheduler import Scheduler

        config = SchedulerConfig(run_at="02:00", interval_hours=12)
        scheduler = Scheduler(config=config)
        entry = scheduler._generate_cron_entry()

        assert "*/12" in entry

    def test_generate_cron_entry_contains_python_command(self):
        """Cron entry includes the python command to run the scheduler."""
        from src.automation.scheduler import Scheduler

        scheduler = Scheduler()
        entry = scheduler._generate_cron_entry()

        assert "python" in entry.lower()
        assert "src.cli" in entry

    def test_generate_cron_entry_has_marker_comment(self):
        """Cron entry includes a marker comment for identification."""
        from src.automation.scheduler import Scheduler

        scheduler = Scheduler()
        entry = scheduler._generate_cron_entry()

        # Should have a comment marker so we can find/replace it later
        assert "email-corpus-analyzer" in entry.lower() or "email_corpus_analyzer" in entry.lower()

    @patch("subprocess.run")
    def test_setup_cron_installs_entry(self, mock_run):
        """_setup_cron installs crontab entry."""
        from src.automation.scheduler import Scheduler

        # First call: crontab -l (list existing)
        # Second call: crontab - (install new)
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="# existing crontab\n"),
            MagicMock(returncode=0),
        ]
        scheduler = Scheduler()
        result = scheduler._setup_cron()

        assert result is True
        assert mock_run.call_count == 2

    @patch("subprocess.run")
    def test_setup_cron_handles_no_existing_crontab(self, mock_run):
        """_setup_cron works when there is no existing crontab."""
        from src.automation.scheduler import Scheduler

        mock_run.side_effect = [
            MagicMock(returncode=1, stderr="no crontab for user"),  # no existing
            MagicMock(returncode=0),  # install succeeds
        ]
        scheduler = Scheduler()
        result = scheduler._setup_cron()

        assert result is True

    @patch("subprocess.run")
    def test_setup_cron_replaces_existing_entry(self, mock_run):
        """_setup_cron replaces an existing email-corpus-analyzer entry."""
        from src.automation.scheduler import Scheduler

        existing_cron = (
            "# other job\n"
            "0 3 * * * /usr/bin/backup\n"
            "0 2 * * * python -m src.cli scheduler run  # email-corpus-analyzer\n"
        )
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=existing_cron),
            MagicMock(returncode=0),
        ]
        scheduler = Scheduler()
        result = scheduler._setup_cron()

        assert result is True
        # The second call should have the old entry removed and new one added
        install_call = mock_run.call_args_list[1]
        new_cron = install_call[1].get("input", "") if "input" in install_call[1] else ""
        # Old entry should be removed (only one email-corpus-analyzer line)
        matching = [
            line for line in new_cron.strip().split("\n") if "email-corpus-analyzer" in line.lower()
        ]
        assert len(matching) == 1

    @patch("subprocess.run")
    def test_disable_cron_removes_entry(self, mock_run):
        """_disable_cron removes the crontab entry."""
        from src.automation.scheduler import Scheduler

        existing_cron = (
            "# other job\n"
            "0 3 * * * /usr/bin/backup\n"
            "0 2 * * * python -m src.cli scheduler run  # email-corpus-analyzer\n"
        )
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=existing_cron),
            MagicMock(returncode=0),
        ]
        scheduler = Scheduler()
        result = scheduler._disable_cron()

        assert result is True


# =============================================================================
# Scheduler.run() Tests
# =============================================================================


class TestSchedulerRun:
    """Tests for Scheduler.run() - manual trigger of incremental processing."""

    @patch("src.automation.scheduler.IncrementalProcessor")
    def test_run_calls_incremental_processor(self, mock_processor_cls):
        """run() creates and executes an IncrementalProcessor."""
        from src.automation.incremental import IncrementalResult
        from src.automation.scheduler import Scheduler

        mock_processor = MagicMock()
        mock_processor.run.return_value = IncrementalResult(
            new_email_count=5,
            merged_corpus_size=100,
            new_categorizations=[],
            processing_time=2.5,
        )
        mock_processor_cls.return_value = mock_processor

        scheduler = Scheduler()
        with (
            patch.object(scheduler, "_load_corpus", return_value=MagicMock()),
            patch.object(scheduler, "_load_analysis", return_value=None),
            patch.object(scheduler, "_load_rules", return_value=None),
            patch.object(scheduler, "_create_extraction_service", return_value=MagicMock()),
            patch.object(scheduler, "_save_state"),
            patch.object(scheduler, "_save_corpus"),
        ):
            result = scheduler.run()

        assert result is not None
        assert result.new_email_count == 5
        mock_processor.run.assert_called_once()

    @patch("src.automation.scheduler.IncrementalProcessor")
    def test_run_updates_state_on_success(self, mock_processor_cls):
        """run() updates state with success result and last_run timestamp."""
        from src.automation.incremental import IncrementalResult
        from src.automation.scheduler import Scheduler

        mock_processor = MagicMock()
        mock_processor.run.return_value = IncrementalResult(
            new_email_count=3,
            merged_corpus_size=50,
            new_categorizations=[],
            processing_time=1.0,
        )
        mock_processor.merged_corpus = MagicMock()
        mock_processor_cls.return_value = mock_processor

        scheduler = Scheduler()
        with (
            patch.object(scheduler, "_load_corpus", return_value=MagicMock()),
            patch.object(scheduler, "_load_analysis", return_value=None),
            patch.object(scheduler, "_load_rules", return_value=None),
            patch.object(scheduler, "_create_extraction_service", return_value=MagicMock()),
            patch.object(scheduler, "_save_state") as mock_save,
            patch.object(scheduler, "_save_corpus"),
        ):
            scheduler.run()

        mock_save.assert_called_once()
        saved_status = mock_save.call_args[0][0]
        assert saved_status.last_result == "success"
        assert saved_status.last_run is not None

    @patch("src.automation.scheduler.IncrementalProcessor")
    def test_run_updates_state_on_error(self, mock_processor_cls):
        """run() updates state with error result when processing fails."""
        from src.automation.scheduler import Scheduler

        mock_processor = MagicMock()
        mock_processor.run.side_effect = RuntimeError("Connection failed")
        mock_processor_cls.return_value = mock_processor

        scheduler = Scheduler()
        with (
            patch.object(scheduler, "_load_corpus", return_value=MagicMock()),
            patch.object(scheduler, "_load_analysis", return_value=None),
            patch.object(scheduler, "_load_rules", return_value=None),
            patch.object(scheduler, "_create_extraction_service", return_value=MagicMock()),
            patch.object(scheduler, "_save_state") as mock_save,
        ):
            result = scheduler.run()

        assert result is None
        mock_save.assert_called_once()
        saved_status = mock_save.call_args[0][0]
        assert "error" in saved_status.last_result.lower()

    def test_run_handles_missing_corpus(self):
        """run() returns None when corpus file is not found."""
        from src.automation.scheduler import Scheduler

        scheduler = Scheduler()
        with patch.object(scheduler, "_load_corpus", return_value=None):
            result = scheduler.run()

        assert result is None


# =============================================================================
# State Persistence Tests
# =============================================================================


class TestSchedulerStatePersistence:
    """Tests for scheduler state file persistence."""

    def test_state_file_path(self):
        """State file is stored at ~/.email-analyzer/scheduler_state.json."""
        from src.automation.scheduler import Scheduler

        scheduler = Scheduler()
        state_path = scheduler._get_state_path()
        assert state_path.name == "scheduler_state.json"
        assert ".email-analyzer" in str(state_path)

    def test_save_and_load_state_roundtrip(self, tmp_path):
        """State can be saved and loaded back."""
        from src.automation.scheduler import Scheduler, ScheduleStatus

        scheduler = Scheduler()
        state_path = tmp_path / "scheduler_state.json"

        with patch.object(scheduler, "_get_state_path", return_value=state_path):
            status = ScheduleStatus(
                enabled=True,
                interval_hours=12,
                last_result="success",
            )
            scheduler._save_state(status)

            loaded = scheduler._load_state()

        assert loaded is not None
        assert loaded.enabled is True
        assert loaded.interval_hours == 12
        assert loaded.last_result == "success"

    def test_load_state_returns_none_for_missing_file(self, tmp_path):
        """_load_state returns None when state file doesn't exist."""
        from src.automation.scheduler import Scheduler

        scheduler = Scheduler()
        state_path = tmp_path / "nonexistent.json"
        with patch.object(scheduler, "_get_state_path", return_value=state_path):
            loaded = scheduler._load_state()
        assert loaded is None

    def test_load_state_returns_none_for_corrupted_file(self, tmp_path):
        """_load_state returns None when state file is corrupted."""
        from src.automation.scheduler import Scheduler

        scheduler = Scheduler()
        state_path = tmp_path / "scheduler_state.json"
        state_path.write_text("not valid json{{{")

        with patch.object(scheduler, "_get_state_path", return_value=state_path):
            loaded = scheduler._load_state()
        assert loaded is None


# =============================================================================
# CLI Integration Tests
# =============================================================================


class TestSchedulerCLI:
    """Tests for the scheduler CLI subcommand."""

    def test_build_scheduler_parser_has_subactions(self):
        """build_scheduler_parser creates setup/run/status/disable sub-actions."""
        import argparse

        from src.cli.commands.scheduler import build_scheduler_parser

        parent_parser = argparse.ArgumentParser()
        subparsers = parent_parser.add_subparsers()
        scheduler_parser = build_scheduler_parser(subparsers)

        assert scheduler_parser is not None

    def test_cmd_scheduler_dispatches_setup(self):
        """cmd_scheduler dispatches to setup handler."""
        import argparse

        from src.cli.commands.scheduler import cmd_scheduler

        args = argparse.Namespace(
            scheduler_action="setup",
            json=False,
            verbose=False,
            output_dir=None,
            config=None,
        )
        with patch("src.cli.commands.scheduler._cmd_scheduler_setup", return_value=0) as mock:
            result = cmd_scheduler(args)
        assert result == 0
        mock.assert_called_once_with(args)

    def test_cmd_scheduler_dispatches_run(self):
        """cmd_scheduler dispatches to run handler."""
        import argparse

        from src.cli.commands.scheduler import cmd_scheduler

        args = argparse.Namespace(
            scheduler_action="run",
            json=False,
            verbose=False,
            output_dir=None,
            config=None,
        )
        with patch("src.cli.commands.scheduler._cmd_scheduler_run", return_value=0) as mock:
            result = cmd_scheduler(args)
        assert result == 0
        mock.assert_called_once_with(args)

    def test_cmd_scheduler_dispatches_status(self):
        """cmd_scheduler dispatches to status handler."""
        import argparse

        from src.cli.commands.scheduler import cmd_scheduler

        args = argparse.Namespace(
            scheduler_action="status",
            json=False,
            verbose=False,
            output_dir=None,
            config=None,
        )
        with patch("src.cli.commands.scheduler._cmd_scheduler_status", return_value=0) as mock:
            result = cmd_scheduler(args)
        assert result == 0
        mock.assert_called_once_with(args)

    def test_cmd_scheduler_dispatches_disable(self):
        """cmd_scheduler dispatches to disable handler."""
        import argparse

        from src.cli.commands.scheduler import cmd_scheduler

        args = argparse.Namespace(
            scheduler_action="disable",
            json=False,
            verbose=False,
            output_dir=None,
            config=None,
        )
        with patch("src.cli.commands.scheduler._cmd_scheduler_disable", return_value=0) as mock:
            result = cmd_scheduler(args)
        assert result == 0
        mock.assert_called_once_with(args)

    def test_cmd_scheduler_unknown_action(self):
        """cmd_scheduler returns 1 for unknown action."""
        import argparse

        from src.cli.commands.scheduler import cmd_scheduler

        args = argparse.Namespace(
            scheduler_action="bogus",
            json=False,
            verbose=False,
            output_dir=None,
            config=None,
        )
        result = cmd_scheduler(args)
        assert result == 1

    def test_cmd_scheduler_setup_returns_zero_on_success(self):
        """_cmd_scheduler_setup returns 0 on success."""
        import argparse

        from src.automation.scheduler import ScheduleStatus
        from src.cli.commands.scheduler import _cmd_scheduler_setup

        args = argparse.Namespace(
            json=False,
            verbose=False,
            output_dir=None,
            config=None,
        )
        with patch("src.automation.scheduler.Scheduler") as mock_cls:
            mock_scheduler = MagicMock()
            mock_cls.return_value = mock_scheduler
            mock_scheduler.setup.return_value = ScheduleStatus(enabled=True, interval_hours=24)
            result = _cmd_scheduler_setup(args)

        assert result == 0

    def test_cmd_scheduler_setup_returns_one_on_failure(self):
        """_cmd_scheduler_setup returns 1 when setup fails."""
        import argparse

        from src.automation.scheduler import ScheduleStatus
        from src.cli.commands.scheduler import _cmd_scheduler_setup

        args = argparse.Namespace(
            json=False,
            verbose=False,
            output_dir=None,
            config=None,
        )
        with patch("src.automation.scheduler.Scheduler") as mock_cls:
            mock_scheduler = MagicMock()
            mock_cls.return_value = mock_scheduler
            mock_scheduler.setup.return_value = ScheduleStatus(enabled=False)
            result = _cmd_scheduler_setup(args)

        assert result == 1

    def test_cmd_scheduler_run_returns_zero_on_success(self):
        """_cmd_scheduler_run returns 0 when run succeeds."""
        import argparse

        from src.automation.incremental import IncrementalResult
        from src.cli.commands.scheduler import _cmd_scheduler_run

        args = argparse.Namespace(
            json=False,
            verbose=False,
            output_dir=None,
            config=None,
        )

        mock_result = IncrementalResult(
            new_email_count=3,
            merged_corpus_size=50,
            new_categorizations=[],
            processing_time=1.0,
        )

        with patch("src.automation.scheduler.Scheduler") as mock_cls:
            mock_scheduler = MagicMock()
            mock_cls.return_value = mock_scheduler
            mock_scheduler.run.return_value = mock_result
            result = _cmd_scheduler_run(args)

        assert result == 0

    def test_cmd_scheduler_run_returns_one_on_failure(self):
        """_cmd_scheduler_run returns 1 when run fails."""
        import argparse

        from src.cli.commands.scheduler import _cmd_scheduler_run

        args = argparse.Namespace(
            json=False,
            verbose=False,
            output_dir=None,
            config=None,
        )

        with patch("src.automation.scheduler.Scheduler") as mock_cls:
            mock_scheduler = MagicMock()
            mock_cls.return_value = mock_scheduler
            mock_scheduler.run.return_value = None
            result = _cmd_scheduler_run(args)

        assert result == 1

    def test_cmd_scheduler_status_returns_zero(self):
        """_cmd_scheduler_status returns 0."""
        import argparse

        from src.automation.scheduler import ScheduleStatus
        from src.cli.commands.scheduler import _cmd_scheduler_status

        args = argparse.Namespace(
            json=False,
            verbose=False,
            output_dir=None,
            config=None,
        )
        with patch("src.automation.scheduler.Scheduler") as mock_cls:
            mock_scheduler = MagicMock()
            mock_cls.return_value = mock_scheduler
            mock_scheduler.get_status.return_value = ScheduleStatus(enabled=True)
            result = _cmd_scheduler_status(args)

        assert result == 0

    def test_cmd_scheduler_status_json_output(self, capsys):
        """_cmd_scheduler_status outputs JSON when --json flag set."""
        import argparse

        from src.automation.scheduler import ScheduleStatus
        from src.cli.commands.scheduler import _cmd_scheduler_status

        args = argparse.Namespace(
            json=True,
            verbose=False,
            output_dir=None,
            config=None,
        )

        now = datetime(2026, 2, 28, 14, 0, 0)

        with patch("src.automation.scheduler.Scheduler") as mock_cls:
            mock_scheduler = MagicMock()
            mock_cls.return_value = mock_scheduler
            mock_scheduler.get_status.return_value = ScheduleStatus(
                enabled=True,
                interval_hours=24,
                last_run=now,
                last_result="success",
            )
            result = _cmd_scheduler_status(args)

        assert result == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["command"] == "scheduler status"
        assert data["status"] == "success"
        assert data["schedule"]["enabled"] is True

    def test_cmd_scheduler_disable_returns_zero(self):
        """_cmd_scheduler_disable returns 0."""
        import argparse

        from src.automation.scheduler import ScheduleStatus
        from src.cli.commands.scheduler import _cmd_scheduler_disable

        args = argparse.Namespace(
            json=False,
            verbose=False,
            output_dir=None,
            config=None,
        )
        with patch("src.automation.scheduler.Scheduler") as mock_cls:
            mock_scheduler = MagicMock()
            mock_cls.return_value = mock_scheduler
            mock_scheduler.disable.return_value = ScheduleStatus(enabled=False)
            result = _cmd_scheduler_disable(args)

        assert result == 0


# =============================================================================
# Task Name Constants
# =============================================================================


class TestSchedulerTaskName:
    """Tests for task name constant used in OS scheduler registration."""

    def test_task_name_constant(self):
        """TASK_NAME constant is defined and non-empty."""
        from src.automation.scheduler import TASK_NAME

        assert isinstance(TASK_NAME, str)
        assert len(TASK_NAME) > 0
        assert "email" in TASK_NAME.lower()
