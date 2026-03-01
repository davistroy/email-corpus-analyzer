"""
Scheduler for automated email processing (Phase 6, Item 6.3).

Sets up automated extraction, analysis, categorization, and email-moving
using platform-native scheduling:
- Windows: Task Scheduler XML + schtasks registration
- Linux/macOS: crontab entry generation

Provides:
- ScheduleStatus model: enabled, interval_hours, next_run, last_run, last_result
- Scheduler class: setup(), run(), get_status(), disable()
- State persistence at ~/.email-analyzer/scheduler_state.json
"""

from __future__ import annotations

import contextlib
import json
import subprocess
import sys
import textwrap
from datetime import datetime, timedelta
from pathlib import Path

from pydantic import BaseModel, Field

from src.automation.incremental import IncrementalProcessor, IncrementalResult
from src.config.models import SchedulerConfig
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Task name used for OS scheduler registration
TASK_NAME = "EmailCorpusAnalyzer-ScheduledRun"

# Marker comment appended to cron entries for identification
_CRON_MARKER = "# email-corpus-analyzer"


# =============================================================================
# ScheduleStatus Model
# =============================================================================


class ScheduleStatus(BaseModel):
    """Status of the scheduler, persisted as JSON.

    Tracks whether the scheduler is enabled, the configured interval,
    next/last run timestamps, and the result of the last run.
    """

    enabled: bool = Field(default=False, description="Whether scheduling is active")
    interval_hours: int = Field(
        default=24, ge=1, le=168, description="Hours between scheduled runs"
    )
    next_run: datetime | None = Field(default=None, description="Estimated next run time")
    last_run: datetime | None = Field(default=None, description="Timestamp of last completed run")
    last_result: str | None = Field(
        default=None,
        description="Result of last run: 'success' or 'error: <message>'",
    )


# =============================================================================
# Scheduler
# =============================================================================


class Scheduler:
    """Orchestrates scheduled automated processing.

    Generates platform-specific scheduler configuration (Windows Task
    Scheduler XML or crontab entry) and provides manual run/status/disable
    operations.

    Args:
        config: SchedulerConfig instance. Uses defaults if not provided.
    """

    def __init__(self, config: SchedulerConfig | None = None) -> None:
        self.config = config or SchedulerConfig()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def setup(self) -> ScheduleStatus:
        """Register the scheduled task with the OS scheduler.

        Detects the platform and calls the appropriate setup method:
        - Windows: _setup_windows() (Task Scheduler via schtasks)
        - Linux/macOS: _setup_cron() (crontab entry)

        Returns:
            ScheduleStatus with enabled=True on success, enabled=False on failure.
        """
        platform = sys.platform

        if platform == "win32":
            success = self._setup_windows()
        elif platform in ("linux", "darwin"):
            success = self._setup_cron()
        else:
            logger.error(f"Unsupported platform for scheduling: {platform}")
            success = False

        now = datetime.now()
        next_run = now + timedelta(hours=self.config.interval_hours) if success else None

        status = ScheduleStatus(
            enabled=success,
            interval_hours=self.config.interval_hours,
            next_run=next_run,
            last_run=None,
            last_result=None,
        )
        self._save_state(status)
        return status

    def run(self, progress_callback=None) -> IncrementalResult | None:
        """Manually trigger a scheduled run.

        Loads the existing corpus, analysis, and rules, then delegates
        to IncrementalProcessor.run(). Updates state with the result.

        Args:
            progress_callback: Optional callback(message) for status updates.

        Returns:
            IncrementalResult on success, None on failure.
        """
        corpus = self._load_corpus()
        if corpus is None:
            logger.error("Cannot run scheduler: corpus file not found")
            return None

        analysis = self._load_analysis()
        rules = self._load_rules()
        extraction_service = self._create_extraction_service()

        now = datetime.now()
        try:
            processor = IncrementalProcessor(extraction_service=extraction_service)
            result = processor.run(
                existing_corpus=corpus,
                existing_analysis=analysis,
                rule_set=rules,
                progress_callback=progress_callback,
            )

            # Save merged corpus if available
            if processor.merged_corpus is not None:
                self._save_corpus(processor.merged_corpus)

            status = ScheduleStatus(
                enabled=True,
                interval_hours=self.config.interval_hours,
                next_run=now + timedelta(hours=self.config.interval_hours),
                last_run=now,
                last_result="success",
            )
            self._save_state(status)
            return result

        except Exception as e:
            logger.error(f"Scheduled run failed: {e}", exc_info=True)
            status = ScheduleStatus(
                enabled=True,
                interval_hours=self.config.interval_hours,
                next_run=now + timedelta(hours=self.config.interval_hours),
                last_run=now,
                last_result=f"error: {e}",
            )
            self._save_state(status)
            return None

    def get_status(self) -> ScheduleStatus:
        """Return the current scheduler status.

        Reads the persisted state file and returns a ScheduleStatus.
        Returns a disabled status if no state file exists.

        Returns:
            ScheduleStatus reflecting current scheduler state.
        """
        state = self._load_state()
        if state is None:
            return ScheduleStatus()
        return state

    def disable(self) -> ScheduleStatus:
        """Disable scheduled processing.

        Removes the OS scheduler task and updates the state file.

        Returns:
            ScheduleStatus with enabled=False.
        """
        state = self._load_state()
        platform = sys.platform

        if platform == "win32":
            self._disable_windows()
        elif platform in ("linux", "darwin"):
            self._disable_cron()

        if state is not None:
            state.enabled = False
            state.next_run = None
        else:
            state = ScheduleStatus(enabled=False)

        self._save_state(state)
        return state

    # ------------------------------------------------------------------
    # Windows Task Scheduler
    # ------------------------------------------------------------------

    def _generate_task_xml(self) -> str:
        """Generate Windows Task Scheduler XML definition.

        Creates an XML document conforming to the Task Scheduler schema
        that will execute `python -m src.cli scheduler run` at the
        configured interval.

        Returns:
            XML string for Task Scheduler import.
        """
        hour, minute = self.config.run_at.split(":")
        start_time = f"{hour}:{minute}:00"

        # Build repetition element for sub-daily intervals
        repetition_xml = ""
        if self.config.interval_hours < 24:
            repetition_xml = textwrap.dedent(f"""\
                <Repetition>
                  <Interval>PT{self.config.interval_hours}H</Interval>
                  <Duration>P1D</Duration>
                  <StopAtDurationEnd>false</StopAtDurationEnd>
                </Repetition>""")

        # Use sys.executable to get the current Python interpreter
        python_exe = sys.executable or "python"

        return textwrap.dedent(f"""\
            <?xml version="1.0" encoding="UTF-16"?>
            <Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
              <RegistrationInfo>
                <Description>Email Corpus Analyzer - Scheduled Processing</Description>
                <URI>\\{TASK_NAME}</URI>
              </RegistrationInfo>
              <Triggers>
                <CalendarTrigger>
                  <StartBoundary>2026-01-01T{start_time}</StartBoundary>
                  <Enabled>true</Enabled>
                  {repetition_xml}
                  <ScheduleByDay>
                    <DaysInterval>1</DaysInterval>
                  </ScheduleByDay>
                </CalendarTrigger>
              </Triggers>
              <Principals>
                <Principal id="Author">
                  <LogonType>InteractiveToken</LogonType>
                  <RunLevel>LeastPrivilege</RunLevel>
                </Principal>
              </Principals>
              <Settings>
                <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
                <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
                <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
                <AllowHardTerminate>true</AllowHardTerminate>
                <StartWhenAvailable>true</StartWhenAvailable>
                <RunOnlyIfNetworkAvailable>true</RunOnlyIfNetworkAvailable>
                <AllowStartOnDemand>true</AllowStartOnDemand>
                <Enabled>true</Enabled>
                <Hidden>false</Hidden>
                <ExecutionTimeLimit>PT4H</ExecutionTimeLimit>
              </Settings>
              <Actions Context="Author">
                <Exec>
                  <Command>{python_exe}</Command>
                  <Arguments>-m src.cli scheduler run</Arguments>
                </Exec>
              </Actions>
            </Task>""")

    def _setup_windows(self) -> bool:
        """Register the task with Windows Task Scheduler via schtasks.

        Writes the XML to a temp file, then calls:
          schtasks /Create /TN <name> /XML <path> /F

        Returns:
            True if registration succeeded, False otherwise.
        """
        xml_content = self._generate_task_xml()
        xml_path = Path.home() / ".email-analyzer" / f"{TASK_NAME}.xml"
        xml_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(xml_path, "w", encoding="utf-16") as f:
                f.write(xml_content)

            result = subprocess.run(
                ["schtasks", "/Create", "/TN", TASK_NAME, "/XML", str(xml_path), "/F"],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0:
                logger.info(f"Windows Task Scheduler task '{TASK_NAME}' created successfully")
                return True
            logger.error(f"schtasks failed (rc={result.returncode}): {result.stderr}")
            return False

        except Exception as e:
            logger.error(f"Failed to register Windows scheduled task: {e}")
            return False
        finally:
            with contextlib.suppress(OSError):
                xml_path.unlink(missing_ok=True)

    def _disable_windows(self) -> bool:
        """Remove the Windows Task Scheduler task.

        Returns:
            True if removal succeeded (or task didn't exist), False otherwise.
        """
        try:
            result = subprocess.run(
                ["schtasks", "/Delete", "/TN", TASK_NAME, "/F"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                logger.info(f"Windows Task Scheduler task '{TASK_NAME}' deleted")
                return True
            logger.warning(f"schtasks /Delete returned {result.returncode}: {result.stderr}")
            return True  # Task may not exist, which is fine
        except Exception as e:
            logger.error(f"Failed to remove Windows scheduled task: {e}")
            return False

    # ------------------------------------------------------------------
    # Cron (Linux / macOS)
    # ------------------------------------------------------------------

    def _generate_cron_entry(self) -> str:
        """Generate a crontab entry for the scheduled run.

        Returns:
            Cron line with schedule, command, and marker comment.
        """
        hour, minute = self.config.run_at.split(":")
        python_exe = sys.executable or "python"
        command = f"{python_exe} -m src.cli scheduler run"

        if self.config.interval_hours == 24:
            # Daily at the configured time
            cron_schedule = f"{int(minute)} {int(hour)} * * *"
        elif self.config.interval_hours < 24:
            # Every N hours
            cron_schedule = f"0 */{self.config.interval_hours} * * *"
        else:
            # Multi-day intervals: use daily and let the run logic handle skipping
            cron_schedule = f"{int(minute)} {int(hour)} * * *"

        return f"{cron_schedule} {command}  {_CRON_MARKER}"

    def _setup_cron(self) -> bool:
        """Install the crontab entry, replacing any existing one.

        Returns:
            True if installation succeeded, False otherwise.
        """
        try:
            # Read existing crontab
            existing = self._read_crontab()

            # Remove any existing email-corpus-analyzer lines
            filtered = [
                line for line in existing.splitlines() if _CRON_MARKER.lower() not in line.lower()
            ]

            # Add the new entry
            new_entry = self._generate_cron_entry()
            filtered.append(new_entry)

            # Ensure trailing newline
            new_crontab = "\n".join(filtered).strip() + "\n"

            # Install the new crontab
            result = subprocess.run(
                ["crontab", "-"],
                input=new_crontab,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0:
                logger.info("Crontab entry installed successfully")
                return True
            logger.error(f"crontab install failed: {result.stderr}")
            return False

        except Exception as e:
            logger.error(f"Failed to set up cron: {e}")
            return False

    def _disable_cron(self) -> bool:
        """Remove the email-corpus-analyzer entry from crontab.

        Returns:
            True if removal succeeded, False otherwise.
        """
        try:
            existing = self._read_crontab()
            filtered = [
                line for line in existing.splitlines() if _CRON_MARKER.lower() not in line.lower()
            ]

            new_crontab = "\n".join(filtered).strip() + "\n"

            result = subprocess.run(
                ["crontab", "-"],
                input=new_crontab,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0:
                logger.info("Crontab entry removed successfully")
                return True
            logger.error(f"crontab removal failed: {result.stderr}")
            return False

        except Exception as e:
            logger.error(f"Failed to remove cron entry: {e}")
            return False

    def _read_crontab(self) -> str:
        """Read the current user's crontab.

        Returns:
            Existing crontab content, or empty string if none exists.
        """
        result = subprocess.run(
            ["crontab", "-l"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            return result.stdout
        return ""

    # ------------------------------------------------------------------
    # State persistence
    # ------------------------------------------------------------------

    def _get_state_path(self) -> Path:
        """Return the path to the scheduler state file."""
        return Path.home() / ".email-analyzer" / "scheduler_state.json"

    def _save_state(self, status: ScheduleStatus) -> None:
        """Save scheduler status to the state file.

        Args:
            status: ScheduleStatus to persist.
        """
        state_path = self._get_state_path()
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(
            json.dumps(status.model_dump(mode="json"), indent=2, default=str),
            encoding="utf-8",
        )
        logger.debug(f"Scheduler state saved to {state_path}")

    def _load_state(self) -> ScheduleStatus | None:
        """Load scheduler status from the state file.

        Returns:
            ScheduleStatus if file exists and is valid, None otherwise.
        """
        state_path = self._get_state_path()
        if not state_path.exists():
            return None
        try:
            data = json.loads(state_path.read_text(encoding="utf-8"))
            return ScheduleStatus(**data)
        except Exception as e:
            logger.warning(f"Failed to load scheduler state: {e}")
            return None

    # ------------------------------------------------------------------
    # Data loading helpers (for run())
    # ------------------------------------------------------------------

    def _load_corpus(self):
        """Load the existing email corpus from the output directory.

        Returns:
            Corpus instance or None if not found.
        """
        from src.models.corpus import Corpus
        from src.utils.file_manager import load_json
        from src.utils.paths import PathConfig

        corpus_path = PathConfig.get_corpus_path()
        try:
            data = load_json(corpus_path)
            return Corpus(**data)
        except FileNotFoundError:
            logger.error(f"Corpus file not found: {corpus_path}")
            return None
        except Exception as e:
            logger.error(f"Failed to load corpus: {e}")
            return None

    def _load_analysis(self):
        """Load existing analysis results.

        Returns:
            AnalysisResults instance or None.
        """
        from src.models.analysis_results import AnalysisResults
        from src.utils.file_manager import load_json
        from src.utils.paths import PathConfig

        analysis_path = PathConfig.get_analysis_path()
        try:
            data = load_json(analysis_path)
            return AnalysisResults(**data)
        except Exception:
            logger.debug("Analysis results not available for incremental run")
            return None

    def _load_rules(self):
        """Load existing rule set.

        Returns:
            RuleSet instance or None.
        """
        from src.models.rule import RuleSet
        from src.utils.file_manager import load_json
        from src.utils.paths import PathConfig

        rules_path = PathConfig.get_rules_path()
        try:
            data = load_json(rules_path)
            return RuleSet(**data)
        except Exception:
            logger.debug("Rules not available for incremental run")
            return None

    def _create_extraction_service(self):
        """Create an ExtractionService for incremental extraction.

        Returns:
            ExtractionService instance.
        """
        from src.services.extraction_service import ExtractionService

        return ExtractionService()

    def _save_corpus(self, corpus) -> None:
        """Save the merged corpus back to disk.

        Args:
            corpus: Corpus instance to save.
        """
        from src.utils.file_manager import save_json
        from src.utils.paths import PathConfig

        corpus_path = PathConfig.get_corpus_path()
        save_json(corpus.model_dump(mode="json"), corpus_path)
        logger.info(f"Updated corpus saved to {corpus_path}")


__all__ = ["TASK_NAME", "ScheduleStatus", "Scheduler"]
