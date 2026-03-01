"""
Tests for src/cli/commands/notifications.py — Notification CLI commands (Phase 6, Item 6.4).

TDD: Tests written first, implementation follows.
"""

import argparse
from unittest.mock import patch

from src.automation.notifications import Alert, NotificationHistory, Severity
from src.cli.commands.notifications import (
    build_notifications_parser,
    cmd_notifications,
    cmd_notifications_clear,
    cmd_notifications_show,
    cmd_notifications_test,
)

# =============================================================================
# Parser tests
# =============================================================================


class TestBuildNotificationsParser:
    """Test that the notifications parser is properly constructed."""

    def test_parser_created(self):
        parent = argparse.ArgumentParser()
        subparsers = parent.add_subparsers(dest="command")
        parser = build_notifications_parser(subparsers)
        assert parser is not None

    def test_show_subcommand(self):
        parent = argparse.ArgumentParser()
        subparsers = parent.add_subparsers(dest="command")
        build_notifications_parser(subparsers)
        args = parent.parse_args(["notifications", "show"])
        assert args.command == "notifications"
        assert args.notifications_action == "show"

    def test_clear_subcommand(self):
        parent = argparse.ArgumentParser()
        subparsers = parent.add_subparsers(dest="command")
        build_notifications_parser(subparsers)
        args = parent.parse_args(["notifications", "clear"])
        assert args.command == "notifications"
        assert args.notifications_action == "clear"

    def test_test_subcommand(self):
        parent = argparse.ArgumentParser()
        subparsers = parent.add_subparsers(dest="command")
        build_notifications_parser(subparsers)
        args = parent.parse_args(["notifications", "test"])
        assert args.command == "notifications"
        assert args.notifications_action == "test"

    def test_show_with_severity_filter(self):
        parent = argparse.ArgumentParser()
        subparsers = parent.add_subparsers(dest="command")
        build_notifications_parser(subparsers)
        args = parent.parse_args(["notifications", "show", "--severity", "warning"])
        assert args.severity == "warning"

    def test_show_default_no_severity_filter(self):
        parent = argparse.ArgumentParser()
        subparsers = parent.add_subparsers(dest="command")
        build_notifications_parser(subparsers)
        args = parent.parse_args(["notifications", "show"])
        assert args.severity is None


# =============================================================================
# cmd_notifications_show tests
# =============================================================================


class TestCmdNotificationsShow:
    """Test the show subcommand."""

    def test_show_no_notifications(self, tmp_path, capsys):
        args = argparse.Namespace(
            json=False,
            severity=None,
            config=None,
        )
        with patch(
            "src.cli.commands.notifications.get_default_notifications_path",
            return_value=tmp_path / "notifications.jsonl",
        ):
            exit_code = cmd_notifications_show(args)
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "No notifications" in captured.out

    def test_show_with_notifications(self, tmp_path, capsys):
        path = tmp_path / "notifications.jsonl"
        history = NotificationHistory(path)
        history.add(
            Alert(
                title="Test Alert",
                message="Something happened",
                severity=Severity.WARNING,
                source="drift",
            )
        )

        args = argparse.Namespace(json=False, severity=None, config=None)
        with patch(
            "src.cli.commands.notifications.get_default_notifications_path",
            return_value=path,
        ):
            exit_code = cmd_notifications_show(args)
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "Test Alert" in captured.out
        assert "Something happened" in captured.out

    def test_show_json_output(self, tmp_path, capsys):
        path = tmp_path / "notifications.jsonl"
        history = NotificationHistory(path)
        history.add(
            Alert(
                title="JSON Test",
                message="Check format",
                severity=Severity.INFO,
                source="test",
            )
        )

        args = argparse.Namespace(json=True, severity=None, config=None)
        with patch(
            "src.cli.commands.notifications.get_default_notifications_path",
            return_value=path,
        ):
            exit_code = cmd_notifications_show(args)
        assert exit_code == 0
        captured = capsys.readouterr()
        import json

        data = json.loads(captured.out)
        assert data["command"] == "notifications show"
        assert len(data["notifications"]) == 1

    def test_show_filter_by_severity(self, tmp_path, capsys):
        path = tmp_path / "notifications.jsonl"
        history = NotificationHistory(path)
        history.add(Alert(title="Info One", message="M", severity=Severity.INFO, source="test"))
        history.add(
            Alert(title="Critical One", message="M", severity=Severity.CRITICAL, source="test")
        )

        args = argparse.Namespace(json=False, severity="critical", config=None)
        with patch(
            "src.cli.commands.notifications.get_default_notifications_path",
            return_value=path,
        ):
            exit_code = cmd_notifications_show(args)
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "Critical One" in captured.out
        assert "Info One" not in captured.out


# =============================================================================
# cmd_notifications_clear tests
# =============================================================================


class TestCmdNotificationsClear:
    """Test the clear subcommand."""

    def test_clear_empty(self, tmp_path, capsys):
        args = argparse.Namespace(json=False, config=None)
        with patch(
            "src.cli.commands.notifications.get_default_notifications_path",
            return_value=tmp_path / "notifications.jsonl",
        ):
            exit_code = cmd_notifications_clear(args)
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "0" in captured.out or "No notifications" in captured.out

    def test_clear_with_notifications(self, tmp_path, capsys):
        path = tmp_path / "notifications.jsonl"
        history = NotificationHistory(path)
        history.add(Alert(title="A", message="M", severity=Severity.INFO, source="test"))
        history.add(Alert(title="B", message="M", severity=Severity.WARNING, source="test"))

        args = argparse.Namespace(json=False, config=None)
        with patch(
            "src.cli.commands.notifications.get_default_notifications_path",
            return_value=path,
        ):
            exit_code = cmd_notifications_clear(args)
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "2" in captured.out

        # Verify actually cleared
        assert history.count() == 0

    def test_clear_json_output(self, tmp_path, capsys):
        path = tmp_path / "notifications.jsonl"
        history = NotificationHistory(path)
        history.add(Alert(title="A", message="M", severity=Severity.INFO, source="test"))

        args = argparse.Namespace(json=True, config=None)
        with patch(
            "src.cli.commands.notifications.get_default_notifications_path",
            return_value=path,
        ):
            exit_code = cmd_notifications_clear(args)
        assert exit_code == 0
        import json

        data = json.loads(capsys.readouterr().out)
        assert data["command"] == "notifications clear"
        assert data["cleared_count"] == 1


# =============================================================================
# cmd_notifications_test tests
# =============================================================================


class TestCmdNotificationsTest:
    """Test the test subcommand."""

    def test_test_sends_notification(self, tmp_path, capsys):
        path = tmp_path / "notifications.jsonl"
        args = argparse.Namespace(json=False, config=None)
        with (
            patch(
                "src.cli.commands.notifications.get_default_notifications_path",
                return_value=path,
            ),
            patch(
                "src.cli.commands.notifications._get_alert_channels",
                return_value=["console"],
            ),
            patch(
                "src.cli.commands.notifications._get_log_path",
                return_value=tmp_path / "notifications.log",
            ),
        ):
            exit_code = cmd_notifications_test(args)
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "Test notification sent" in captured.out or "test" in captured.out.lower()

    def test_test_stores_in_history(self, tmp_path, capsys):
        path = tmp_path / "notifications.jsonl"
        args = argparse.Namespace(json=False, config=None)
        with (
            patch(
                "src.cli.commands.notifications.get_default_notifications_path",
                return_value=path,
            ),
            patch(
                "src.cli.commands.notifications._get_alert_channels",
                return_value=["console"],
            ),
            patch(
                "src.cli.commands.notifications._get_log_path",
                return_value=tmp_path / "notifications.log",
            ),
        ):
            cmd_notifications_test(args)
        history = NotificationHistory(path)
        assert history.count() >= 1


# =============================================================================
# cmd_notifications dispatcher tests
# =============================================================================


class TestCmdNotifications:
    """Test the top-level dispatcher."""

    def test_dispatch_show(self, tmp_path, capsys):
        args = argparse.Namespace(
            notifications_action="show",
            json=False,
            severity=None,
            config=None,
        )
        with patch(
            "src.cli.commands.notifications.get_default_notifications_path",
            return_value=tmp_path / "notifications.jsonl",
        ):
            exit_code = cmd_notifications(args)
        assert exit_code == 0

    def test_dispatch_clear(self, tmp_path, capsys):
        args = argparse.Namespace(
            notifications_action="clear",
            json=False,
            config=None,
        )
        with patch(
            "src.cli.commands.notifications.get_default_notifications_path",
            return_value=tmp_path / "notifications.jsonl",
        ):
            exit_code = cmd_notifications(args)
        assert exit_code == 0

    def test_dispatch_test(self, tmp_path, capsys):
        args = argparse.Namespace(
            notifications_action="test",
            json=False,
            config=None,
        )
        with (
            patch(
                "src.cli.commands.notifications.get_default_notifications_path",
                return_value=tmp_path / "notifications.jsonl",
            ),
            patch(
                "src.cli.commands.notifications._get_alert_channels",
                return_value=["console"],
            ),
            patch(
                "src.cli.commands.notifications._get_log_path",
                return_value=tmp_path / "notifications.log",
            ),
        ):
            exit_code = cmd_notifications(args)
        assert exit_code == 0

    def test_dispatch_unknown(self, tmp_path):
        args = argparse.Namespace(
            notifications_action="explode",
            json=False,
            config=None,
        )
        exit_code = cmd_notifications(args)
        assert exit_code == 1
