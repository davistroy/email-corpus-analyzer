"""
Notification system for Phase 6, Item 6.4.

Sends alerts when automated processing detects actionable changes:
- New category candidate detected (cluster of uncategorized emails)
- Existing category drifting (match rate dropping)
- New high-volume sender detected
- Rule coverage dropping below threshold

Supports multiple notification channels:
- desktop: system notifications (Windows toast, macOS osascript, Linux notify-send)
- log: write to a notification log file (~/.email-analyzer/notifications.log)
- console: print to stdout with severity formatting

Alert history stored in ~/.email-analyzer/notifications.jsonl for review.
"""

from __future__ import annotations

import json
import logging
import platform
import subprocess
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


# =============================================================================
# Severity enum
# =============================================================================


class Severity(str, Enum):
    """Alert severity levels with numeric ordering."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"

    @property
    def level(self) -> int:
        """Numeric level for ordering: INFO=0, WARNING=1, CRITICAL=2."""
        _levels = {"info": 0, "warning": 1, "critical": 2}
        return _levels[self.value]

    @property
    def label(self) -> str:
        """Uppercase label for display."""
        return self.value.upper()


# =============================================================================
# Alert model
# =============================================================================


class Alert:
    """
    A single notification alert.

    Attributes:
        title: Short alert title.
        message: Detailed alert message.
        severity: INFO, WARNING, or CRITICAL.
        source: What generated the alert (e.g., 'drift', 'volume', 'cluster').
        timestamp: When the alert was created (UTC).
    """

    def __init__(
        self,
        title: str,
        message: str,
        severity: Severity,
        source: str,
        timestamp: datetime | None = None,
    ) -> None:
        self.title = title
        self.message = message
        self.severity = severity
        self.source = source
        self.timestamp = timestamp or datetime.now(timezone.utc)

    def to_dict(self) -> dict:
        """Serialize to dictionary for JSON storage."""
        return {
            "title": self.title,
            "message": self.message,
            "severity": self.severity.value,
            "source": self.source,
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> Alert:
        """Deserialize from dictionary."""
        return cls(
            title=data["title"],
            message=data["message"],
            severity=Severity(data["severity"]),
            source=data["source"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
        )

    def __repr__(self) -> str:
        return (
            f"Alert(title={self.title!r}, severity={self.severity.value}, source={self.source!r})"
        )


# =============================================================================
# NotificationHistory — JSONL storage
# =============================================================================


def get_default_notifications_path() -> Path:
    """
    Get the default path for the notifications JSONL file.

    Returns:
        Path to ~/.email-analyzer/notifications.jsonl
    """
    return Path.home() / ".email-analyzer" / "notifications.jsonl"


def get_default_log_path() -> Path:
    """
    Get the default path for the notification log file.

    Returns:
        Path to ~/.email-analyzer/notifications.log
    """
    return Path.home() / ".email-analyzer" / "notifications.log"


class NotificationHistory:
    """
    Persistent storage for notification alerts in JSONL format.

    Each alert is one JSON object per line, appended on add().
    Supports get_all, get_by_severity, count, and clear operations.

    Args:
        path: Path to the JSONL file. Created on first write.
    """

    def __init__(self, path: Path) -> None:
        self._path = path

    @property
    def path(self) -> Path:
        """The file path for this history store."""
        return self._path

    def add(self, alert: Alert) -> None:
        """
        Append an alert to the history file.

        Creates the parent directory and file if they don't exist.

        Args:
            alert: Alert to persist.
        """
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._path, "a", encoding="utf-8") as f:
                f.write(json.dumps(alert.to_dict()) + "\n")
        except OSError:
            logger.warning("Failed to write notification to %s", self._path, exc_info=True)

    def get_all(self) -> list[Alert]:
        """
        Read all alerts from the history file.

        Corrupted lines are skipped with a warning.

        Returns:
            List of Alert objects, oldest first.
        """
        if not self._path.exists():
            return []

        alerts: list[Alert] = []
        try:
            with open(self._path, encoding="utf-8") as f:
                for line_no, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        alerts.append(Alert.from_dict(data))
                    except (json.JSONDecodeError, KeyError, ValueError):
                        logger.warning("Skipping corrupted line %d in %s", line_no, self._path)
        except OSError:
            logger.warning("Failed to read notifications from %s", self._path, exc_info=True)

        return alerts

    def get_by_severity(self, severity: Severity) -> list[Alert]:
        """
        Get alerts filtered by severity.

        Args:
            severity: Only return alerts with this severity level.

        Returns:
            Filtered list of Alert objects.
        """
        return [a for a in self.get_all() if a.severity == severity]

    def count(self) -> int:
        """Return the number of stored alerts."""
        return len(self.get_all())

    def clear(self) -> int:
        """
        Remove all alerts from history.

        Returns:
            Number of alerts that were cleared.
        """
        existing_count = self.count()
        if self._path.exists():
            try:
                self._path.unlink()
            except OSError:
                logger.warning("Failed to clear notifications at %s", self._path, exc_info=True)
        return existing_count


# =============================================================================
# NotificationManager — multi-channel dispatch
# =============================================================================


class NotificationManager:
    """
    Sends alerts via multiple notification channels.

    Supported channels:
    - ``console``: Formatted print to stdout.
    - ``log``: Append to a log file (notifications.log).
    - ``desktop``: OS-native notification (Windows toast, macOS, Linux).

    Args:
        channels: List of channel names to use for send_alert().
        history_path: Path for the JSONL notification history.
        log_path: Path for the log-channel output file.
    """

    def __init__(
        self,
        channels: list[str],
        history_path: Path | None = None,
        log_path: Path | None = None,
    ) -> None:
        self._channels = list(channels)
        self._history = NotificationHistory(history_path or get_default_notifications_path())
        self._log_path = log_path or get_default_log_path()

    @property
    def channels(self) -> list[str]:
        """Configured notification channels."""
        return list(self._channels)

    def get_history(self) -> NotificationHistory:
        """Return the underlying NotificationHistory instance."""
        return self._history

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def send_notification(
        self,
        title: str,
        message: str,
        severity: Severity,
        channel: str,
    ) -> bool:
        """
        Send a notification via a specific channel.

        Args:
            title: Notification title.
            message: Notification body.
            severity: Severity level.
            channel: Channel name ('console', 'log', or 'desktop').

        Returns:
            True if the notification was delivered successfully.
        """
        dispatchers = {
            "console": self._send_console,
            "log": self._send_log,
            "desktop": self._send_desktop,
        }
        handler = dispatchers.get(channel)
        if handler is None:
            logger.warning("Unknown notification channel: %s", channel)
            return False

        if channel == "desktop":
            return handler(title, message)
        return handler(title, message, severity)

    def send_alert(self, alert: Alert) -> list[bool]:
        """
        Send an alert via all configured channels and persist to history.

        Args:
            alert: The Alert to send.

        Returns:
            List of booleans, one per channel, indicating delivery success.
        """
        # Persist to history first
        self._history.add(alert)

        results: list[bool] = []
        for channel in self._channels:
            try:
                ok = self.send_notification(
                    title=alert.title,
                    message=alert.message,
                    severity=alert.severity,
                    channel=channel,
                )
                results.append(ok)
            except Exception:
                logger.warning("Failed to send alert via channel %s", channel, exc_info=True)
                results.append(False)

        return results

    # ------------------------------------------------------------------
    # Channel implementations
    # ------------------------------------------------------------------

    def _send_console(self, title: str, message: str, severity: Severity) -> bool:
        """Print formatted notification to stdout."""
        severity_markers = {
            Severity.INFO: "[INFO]",
            Severity.WARNING: "[WARNING]",
            Severity.CRITICAL: "[CRITICAL]",
        }
        marker = severity_markers.get(severity, "[INFO]")
        separator = "-" * 50
        print(f"\n{separator}")
        print(f"{marker} {title}")
        print(f"  {message}")
        print(separator)
        return True

    def _send_log(self, title: str, message: str, severity: Severity) -> bool:
        """Append formatted notification to the log file."""
        try:
            self._log_path.parent.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now(timezone.utc).isoformat()
            entry = f"[{timestamp}] [{severity.label}] {title}: {message}\n"
            with open(self._log_path, "a", encoding="utf-8") as f:
                f.write(entry)
            return True
        except OSError:
            logger.warning("Failed to write to notification log: %s", self._log_path, exc_info=True)
            return False

    def _send_desktop(self, title: str, message: str) -> bool:
        """
        Send a desktop notification using the platform's native API.

        Returns True if successful, False otherwise.
        """
        system = platform.system()
        try:
            if system == "Windows":
                return self._send_windows_toast(title, message)
            if system == "Darwin":
                return self._send_macos_notification(title, message)
            if system == "Linux":
                return self._send_linux_notification(title, message)
            logger.warning("Desktop notifications not supported on %s", system)
            return False
        except Exception:
            logger.warning("Desktop notification failed", exc_info=True)
            return False

    def _send_windows_toast(self, title: str, message: str) -> bool:
        """Send a Windows toast notification using PowerShell."""
        try:
            # Use PowerShell BurntToast or built-in WinRT toast
            ps_script = (
                "[Windows.UI.Notifications.ToastNotificationManager, "
                "Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null; "
                "[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, "
                "ContentType = WindowsRuntime] | Out-Null; "
                "$template = [Windows.UI.Notifications.ToastNotificationManager]::"
                "GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02); "
                "$text = $template.GetElementsByTagName('text'); "
                f"$text[0].AppendChild($template.CreateTextNode('{title}')) | Out-Null; "
                f"$text[1].AppendChild($template.CreateTextNode('{message}')) | Out-Null; "
                "$toast = [Windows.UI.Notifications.ToastNotification]::new($template); "
                "[Windows.UI.Notifications.ToastNotificationManager]::"
                "CreateToastNotifier('Email Analyzer').Show($toast)"
            )
            result = subprocess.run(
                ["powershell", "-Command", ps_script],
                capture_output=True,
                timeout=10,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            logger.warning("Windows toast notification failed", exc_info=True)
            return False

    def _send_macos_notification(self, title: str, message: str) -> bool:
        """Send a macOS notification using osascript."""
        try:
            script = (
                f'display notification "{message}" with title "{title}" subtitle "Email Analyzer"'
            )
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                timeout=10,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            logger.warning("macOS notification failed", exc_info=True)
            return False

    def _send_linux_notification(self, title: str, message: str) -> bool:
        """Send a Linux notification using notify-send."""
        try:
            result = subprocess.run(
                ["notify-send", title, message],
                capture_output=True,
                timeout=10,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            logger.warning("Linux notify-send failed", exc_info=True)
            return False


__all__ = [
    "Alert",
    "NotificationHistory",
    "NotificationManager",
    "Severity",
    "get_default_log_path",
    "get_default_notifications_path",
]
