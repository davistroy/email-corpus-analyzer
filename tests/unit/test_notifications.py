"""
Tests for src/automation/notifications.py — Notification system (Phase 6, Item 6.4).

TDD: Tests written first, implementation follows.
"""

import json
from datetime import datetime, timezone
from unittest.mock import patch

from src.automation.notifications import (
    Alert,
    NotificationHistory,
    NotificationManager,
    Severity,
    get_default_notifications_path,
)

# =============================================================================
# Alert model tests
# =============================================================================


class TestSeverity:
    """Test Severity enum."""

    def test_severity_values(self):
        assert Severity.INFO == "info"
        assert Severity.WARNING == "warning"
        assert Severity.CRITICAL == "critical"

    def test_severity_ordering(self):
        """Info < Warning < Critical for comparison."""
        assert Severity.INFO.level < Severity.WARNING.level
        assert Severity.WARNING.level < Severity.CRITICAL.level


class TestAlert:
    """Test Alert model."""

    def test_create_alert_minimal(self):
        alert = Alert(
            title="Test Alert",
            message="Something happened",
            severity=Severity.INFO,
            source="test",
        )
        assert alert.title == "Test Alert"
        assert alert.message == "Something happened"
        assert alert.severity == Severity.INFO
        assert alert.source == "test"
        assert isinstance(alert.timestamp, datetime)

    def test_create_alert_with_timestamp(self):
        ts = datetime(2026, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        alert = Alert(
            title="Custom Time",
            message="Custom timestamp",
            severity=Severity.WARNING,
            source="monitor",
            timestamp=ts,
        )
        assert alert.timestamp == ts

    def test_alert_to_dict(self):
        alert = Alert(
            title="Test",
            message="Msg",
            severity=Severity.CRITICAL,
            source="drift",
        )
        d = alert.to_dict()
        assert d["title"] == "Test"
        assert d["message"] == "Msg"
        assert d["severity"] == "critical"
        assert d["source"] == "drift"
        assert "timestamp" in d

    def test_alert_from_dict(self):
        data = {
            "title": "Roundtrip",
            "message": "Works",
            "severity": "warning",
            "source": "volume",
            "timestamp": "2026-01-15T10:30:00+00:00",
        }
        alert = Alert.from_dict(data)
        assert alert.title == "Roundtrip"
        assert alert.severity == Severity.WARNING
        assert alert.source == "volume"

    def test_alert_roundtrip(self):
        """to_dict -> from_dict preserves data."""
        original = Alert(
            title="Roundtrip Test",
            message="Full cycle",
            severity=Severity.CRITICAL,
            source="test",
        )
        restored = Alert.from_dict(original.to_dict())
        assert restored.title == original.title
        assert restored.message == original.message
        assert restored.severity == original.severity
        assert restored.source == original.source


# =============================================================================
# NotificationHistory tests
# =============================================================================


class TestNotificationHistory:
    """Test NotificationHistory JSONL storage."""

    def test_default_path(self):
        path = get_default_notifications_path()
        assert path.name == "notifications.jsonl"
        assert ".email-analyzer" in str(path)

    def test_add_and_get_all(self, tmp_path):
        history = NotificationHistory(tmp_path / "notifications.jsonl")
        alert = Alert(
            title="Test",
            message="Added",
            severity=Severity.INFO,
            source="test",
        )
        history.add(alert)

        alerts = history.get_all()
        assert len(alerts) == 1
        assert alerts[0].title == "Test"

    def test_add_multiple(self, tmp_path):
        history = NotificationHistory(tmp_path / "notifications.jsonl")
        for i in range(3):
            history.add(
                Alert(
                    title=f"Alert {i}",
                    message=f"Message {i}",
                    severity=Severity.INFO,
                    source="test",
                )
            )
        assert len(history.get_all()) == 3

    def test_get_all_empty(self, tmp_path):
        history = NotificationHistory(tmp_path / "notifications.jsonl")
        assert history.get_all() == []

    def test_get_all_missing_file(self, tmp_path):
        history = NotificationHistory(tmp_path / "nonexistent" / "notifications.jsonl")
        assert history.get_all() == []

    def test_clear(self, tmp_path):
        history = NotificationHistory(tmp_path / "notifications.jsonl")
        history.add(Alert(title="To Clear", message="Gone", severity=Severity.INFO, source="test"))
        assert len(history.get_all()) == 1
        count = history.clear()
        assert count == 1
        assert history.get_all() == []

    def test_clear_empty(self, tmp_path):
        history = NotificationHistory(tmp_path / "notifications.jsonl")
        count = history.clear()
        assert count == 0

    def test_count(self, tmp_path):
        history = NotificationHistory(tmp_path / "notifications.jsonl")
        assert history.count() == 0
        history.add(Alert(title="A", message="B", severity=Severity.INFO, source="test"))
        assert history.count() == 1

    def test_get_unread(self, tmp_path):
        """Unread = all alerts since last clear."""
        history = NotificationHistory(tmp_path / "notifications.jsonl")
        history.add(Alert(title="First", message="M", severity=Severity.INFO, source="test"))
        alerts = history.get_all()
        assert len(alerts) == 1

    def test_persistence_across_instances(self, tmp_path):
        """JSONL file persists across NotificationHistory instances."""
        path = tmp_path / "notifications.jsonl"
        h1 = NotificationHistory(path)
        h1.add(Alert(title="Persist", message="M", severity=Severity.INFO, source="test"))

        h2 = NotificationHistory(path)
        assert len(h2.get_all()) == 1
        assert h2.get_all()[0].title == "Persist"

    def test_corrupted_line_skipped(self, tmp_path):
        """Corrupted JSONL lines are skipped gracefully."""
        path = tmp_path / "notifications.jsonl"
        # Write a valid line then a corrupt one
        valid_alert = Alert(title="Valid", message="M", severity=Severity.INFO, source="test")
        with open(path, "w", encoding="utf-8") as f:
            f.write(json.dumps(valid_alert.to_dict()) + "\n")
            f.write("THIS IS NOT JSON\n")
        history = NotificationHistory(path)
        alerts = history.get_all()
        assert len(alerts) == 1
        assert alerts[0].title == "Valid"

    def test_get_by_severity(self, tmp_path):
        history = NotificationHistory(tmp_path / "notifications.jsonl")
        history.add(Alert(title="Info", message="M", severity=Severity.INFO, source="test"))
        history.add(Alert(title="Warning", message="M", severity=Severity.WARNING, source="test"))
        history.add(Alert(title="Critical", message="M", severity=Severity.CRITICAL, source="test"))
        warnings = history.get_by_severity(Severity.WARNING)
        assert len(warnings) == 1
        assert warnings[0].title == "Warning"


# =============================================================================
# NotificationManager tests
# =============================================================================


class TestNotificationManager:
    """Test NotificationManager channel dispatch."""

    def test_init_default_channels(self, tmp_path):
        mgr = NotificationManager(
            channels=["log"],
            history_path=tmp_path / "notifications.jsonl",
        )
        assert "log" in mgr.channels

    def test_init_multiple_channels(self, tmp_path):
        mgr = NotificationManager(
            channels=["log", "console", "desktop"],
            history_path=tmp_path / "notifications.jsonl",
        )
        assert set(mgr.channels) == {"log", "console", "desktop"}

    def test_send_notification_console(self, tmp_path, capsys):
        mgr = NotificationManager(
            channels=["console"],
            history_path=tmp_path / "notifications.jsonl",
        )
        result = mgr.send_notification(
            title="Console Test",
            message="Hello stdout",
            severity=Severity.INFO,
            channel="console",
        )
        assert result is True
        captured = capsys.readouterr()
        assert "Console Test" in captured.out
        assert "Hello stdout" in captured.out

    def test_send_notification_log(self, tmp_path):
        log_path = tmp_path / "notifications.log"
        mgr = NotificationManager(
            channels=["log"],
            history_path=tmp_path / "notifications.jsonl",
            log_path=log_path,
        )
        result = mgr.send_notification(
            title="Log Test",
            message="Hello log",
            severity=Severity.WARNING,
            channel="log",
        )
        assert result is True
        assert log_path.exists()
        content = log_path.read_text(encoding="utf-8")
        assert "Log Test" in content
        assert "Hello log" in content
        assert "WARNING" in content

    def test_send_notification_desktop_mocked(self, tmp_path):
        """Desktop notification succeeds when platform API works."""
        mgr = NotificationManager(
            channels=["desktop"],
            history_path=tmp_path / "notifications.jsonl",
        )
        with patch.object(mgr, "_send_desktop", return_value=True):
            result = mgr.send_notification(
                title="Desktop Test",
                message="Hello desktop",
                severity=Severity.CRITICAL,
                channel="desktop",
            )
            assert result is True

    def test_send_notification_desktop_failure_graceful(self, tmp_path):
        """Desktop notification failure returns False, doesn't raise."""
        mgr = NotificationManager(
            channels=["desktop"],
            history_path=tmp_path / "notifications.jsonl",
        )
        with patch.object(mgr, "_send_desktop", return_value=False):
            result = mgr.send_notification(
                title="Fail Test",
                message="Should not crash",
                severity=Severity.CRITICAL,
                channel="desktop",
            )
            assert result is False

    def test_send_notification_unknown_channel(self, tmp_path):
        mgr = NotificationManager(
            channels=["log"],
            history_path=tmp_path / "notifications.jsonl",
        )
        result = mgr.send_notification(
            title="Unknown",
            message="Bad channel",
            severity=Severity.INFO,
            channel="carrier_pigeon",
        )
        assert result is False

    def test_send_alert_all_channels(self, tmp_path):
        """send_alert dispatches to all configured channels."""
        log_path = tmp_path / "notifications.log"
        mgr = NotificationManager(
            channels=["log", "console"],
            history_path=tmp_path / "notifications.jsonl",
            log_path=log_path,
        )
        alert = Alert(
            title="Multi",
            message="Both channels",
            severity=Severity.INFO,
            source="test",
        )
        results = mgr.send_alert(alert)
        assert len(results) == 2
        assert all(r is True for r in results)

    def test_send_alert_stores_in_history(self, tmp_path):
        """send_alert persists alert to history."""
        mgr = NotificationManager(
            channels=["console"],
            history_path=tmp_path / "notifications.jsonl",
        )
        alert = Alert(
            title="Persist Alert",
            message="Should be stored",
            severity=Severity.WARNING,
            source="test",
        )
        mgr.send_alert(alert)
        history = mgr.get_history()
        alerts = history.get_all()
        assert len(alerts) == 1
        assert alerts[0].title == "Persist Alert"

    def test_send_alert_partial_failure(self, tmp_path):
        """If one channel fails, others still execute."""
        mgr = NotificationManager(
            channels=["console", "desktop"],
            history_path=tmp_path / "notifications.jsonl",
        )
        with patch.object(mgr, "_send_desktop", return_value=False):
            alert = Alert(
                title="Partial",
                message="One fails",
                severity=Severity.INFO,
                source="test",
            )
            results = mgr.send_alert(alert)
            assert len(results) == 2
            # console should succeed, desktop should fail
            assert True in results
            assert False in results

    def test_log_channel_appends(self, tmp_path):
        """Multiple log notifications append, not overwrite."""
        log_path = tmp_path / "notifications.log"
        mgr = NotificationManager(
            channels=["log"],
            history_path=tmp_path / "notifications.jsonl",
            log_path=log_path,
        )
        mgr.send_notification("First", "1", Severity.INFO, "log")
        mgr.send_notification("Second", "2", Severity.INFO, "log")
        content = log_path.read_text(encoding="utf-8")
        assert "First" in content
        assert "Second" in content

    def test_console_severity_formatting(self, tmp_path, capsys):
        """Console output includes severity indicator."""
        mgr = NotificationManager(
            channels=["console"],
            history_path=tmp_path / "notifications.jsonl",
        )
        mgr.send_notification("Crit", "Bad", Severity.CRITICAL, "console")
        captured = capsys.readouterr()
        assert "CRITICAL" in captured.out

    def test_console_info_formatting(self, tmp_path, capsys):
        mgr = NotificationManager(
            channels=["console"],
            history_path=tmp_path / "notifications.jsonl",
        )
        mgr.send_notification("Info", "Good", Severity.INFO, "console")
        captured = capsys.readouterr()
        assert "INFO" in captured.out

    def test_get_history_returns_history_instance(self, tmp_path):
        mgr = NotificationManager(
            channels=["log"],
            history_path=tmp_path / "notifications.jsonl",
        )
        history = mgr.get_history()
        assert isinstance(history, NotificationHistory)


class TestDesktopNotification:
    """Tests for desktop notification platform logic."""

    def test_send_desktop_windows(self, tmp_path):
        """On Windows, _send_desktop attempts Windows toast."""
        mgr = NotificationManager(
            channels=["desktop"],
            history_path=tmp_path / "notifications.jsonl",
        )
        with (
            patch("platform.system", return_value="Windows"),
            patch.object(mgr, "_send_windows_toast", return_value=True) as mock_toast,
        ):
            result = mgr._send_desktop("Title", "Message")
            assert result is True
            mock_toast.assert_called_once_with("Title", "Message")

    def test_send_desktop_macos(self, tmp_path):
        """On macOS, _send_desktop attempts osascript."""
        mgr = NotificationManager(
            channels=["desktop"],
            history_path=tmp_path / "notifications.jsonl",
        )
        with (
            patch("platform.system", return_value="Darwin"),
            patch.object(mgr, "_send_macos_notification", return_value=True) as mock_mac,
        ):
            result = mgr._send_desktop("Title", "Message")
            assert result is True
            mock_mac.assert_called_once_with("Title", "Message")

    def test_send_desktop_linux(self, tmp_path):
        """On Linux, _send_desktop attempts notify-send."""
        mgr = NotificationManager(
            channels=["desktop"],
            history_path=tmp_path / "notifications.jsonl",
        )
        with (
            patch("platform.system", return_value="Linux"),
            patch.object(mgr, "_send_linux_notification", return_value=True) as mock_linux,
        ):
            result = mgr._send_desktop("Title", "Message")
            assert result is True
            mock_linux.assert_called_once_with("Title", "Message")

    def test_send_desktop_unsupported_platform(self, tmp_path):
        """Unsupported platform returns False."""
        mgr = NotificationManager(
            channels=["desktop"],
            history_path=tmp_path / "notifications.jsonl",
        )
        with patch("platform.system", return_value="FreeBSD"):
            result = mgr._send_desktop("Title", "Message")
            assert result is False

    def test_send_desktop_exception_handled(self, tmp_path):
        """Exceptions during desktop send are caught gracefully."""
        mgr = NotificationManager(
            channels=["desktop"],
            history_path=tmp_path / "notifications.jsonl",
        )
        with (
            patch("platform.system", return_value="Windows"),
            patch.object(mgr, "_send_windows_toast", side_effect=Exception("Toast failed")),
        ):
            result = mgr._send_desktop("Title", "Message")
            assert result is False
