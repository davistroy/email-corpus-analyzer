"""Notifications command: view, clear, and test notification alerts."""

import argparse
from pathlib import Path

from src.automation.notifications import (
    Alert,
    NotificationHistory,
    NotificationManager,
    Severity,
    get_default_log_path,
    get_default_notifications_path,
)
from src.cli.formatters import output_json
from src.config.loader import ConfigLoadError, load_config
from src.utils.logger import get_logger

logger = get_logger(__name__)


# =============================================================================
# Helpers
# =============================================================================


def _get_alert_channels(args: argparse.Namespace) -> list[str]:
    """Resolve alert channels from config, defaulting to ['console']."""
    try:
        config = load_config(config_path=getattr(args, "config", None))
        return list(config.monitoring.alert_channels)
    except (ConfigLoadError, Exception):
        return ["console"]


def _get_log_path(args: argparse.Namespace) -> Path:
    """Resolve notification log path."""
    return get_default_log_path()


# =============================================================================
# Parser
# =============================================================================


def build_notifications_parser(subparsers) -> argparse.ArgumentParser:
    """Add notifications subparser to the CLI and return it."""
    notif_parser = subparsers.add_parser(
        "notifications",
        help="Manage notification alerts",
        description="View, clear, or test notification alerts from automated processing.",
    )
    notif_subparsers = notif_parser.add_subparsers(
        dest="notifications_action",
        required=True,
        help="Notifications action to perform",
    )

    # notifications show
    show_parser = notif_subparsers.add_parser(
        "show",
        help="Display pending notifications",
        description="Show all notification alerts, optionally filtered by severity.",
    )
    show_parser.add_argument(
        "--severity",
        choices=["info", "warning", "critical"],
        default=None,
        help="Filter notifications by severity level",
    )

    # notifications clear
    notif_subparsers.add_parser(
        "clear",
        help="Clear all notifications",
        description="Mark all notifications as read by removing them from the history.",
    )

    # notifications test
    notif_subparsers.add_parser(
        "test",
        help="Send a test notification",
        description="Send a test notification through all configured channels.",
    )

    return notif_parser  # type: ignore[no-any-return]


# =============================================================================
# Subcommand handlers
# =============================================================================


def cmd_notifications_show(args: argparse.Namespace) -> int:
    """
    Show pending notifications, optionally filtered by severity.

    Args:
        args: Parsed CLI arguments (json, severity).

    Returns:
        Exit code (0 = success).
    """
    history = NotificationHistory(get_default_notifications_path())

    severity_filter = getattr(args, "severity", None)
    if severity_filter:
        alerts = history.get_by_severity(Severity(severity_filter))
    else:
        alerts = history.get_all()

    if getattr(args, "json", False):
        output_json(
            {
                "command": "notifications show",
                "count": len(alerts),
                "notifications": [a.to_dict() for a in alerts],
            }
        )
        return 0

    if not alerts:
        print("No notifications.")
        return 0

    print(f"\nNotifications ({len(alerts)}):")
    print("=" * 60)
    for alert in alerts:
        severity_markers = {
            Severity.INFO: "[INFO]",
            Severity.WARNING: "[WARNING]",
            Severity.CRITICAL: "[CRITICAL]",
        }
        marker = severity_markers.get(alert.severity, "[INFO]")
        ts = alert.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n  {marker} {alert.title}")
        print(f"  {alert.message}")
        print(f"  Source: {alert.source}  |  Time: {ts}")
    print("\n" + "=" * 60)

    return 0


def cmd_notifications_clear(args: argparse.Namespace) -> int:
    """
    Clear all notification history.

    Args:
        args: Parsed CLI arguments (json).

    Returns:
        Exit code (0 = success).
    """
    history = NotificationHistory(get_default_notifications_path())
    count = history.clear()

    if getattr(args, "json", False):
        output_json(
            {
                "command": "notifications clear",
                "cleared_count": count,
            }
        )
        return 0

    if count == 0:
        print("No notifications to clear.")
    else:
        print(f"Cleared {count} notification(s).")
    return 0


def cmd_notifications_test(args: argparse.Namespace) -> int:
    """
    Send a test notification through all configured channels.

    Args:
        args: Parsed CLI arguments (json).

    Returns:
        Exit code (0 = success, 1 = all channels failed).
    """
    channels = _get_alert_channels(args)
    log_path = _get_log_path(args)
    history_path = get_default_notifications_path()

    mgr = NotificationManager(
        channels=channels,
        history_path=history_path,
        log_path=log_path,
    )

    alert = Alert(
        title="Test Notification",
        message="This is a test notification from Email Analyzer.",
        severity=Severity.INFO,
        source="test",
    )

    results = mgr.send_alert(alert)

    if getattr(args, "json", False):
        output_json(
            {
                "command": "notifications test",
                "channels": channels,
                "results": dict(zip(channels, results, strict=True)),
            }
        )
    else:
        print("Test notification sent via configured channels:")
        for channel, ok in zip(channels, results, strict=True):
            status = "OK" if ok else "FAILED"
            print(f"  {channel}: {status}")

    return 0 if any(results) else 1


# =============================================================================
# Dispatcher
# =============================================================================


def cmd_notifications(args: argparse.Namespace) -> int:
    """
    Dispatch to the appropriate notifications subcommand.

    Args:
        args: Parsed CLI arguments with notifications_action.

    Returns:
        Exit code (0 = success, 1 = error).
    """
    action = getattr(args, "notifications_action", None)
    if action == "show":
        return cmd_notifications_show(args)
    if action == "clear":
        return cmd_notifications_clear(args)
    if action == "test":
        return cmd_notifications_test(args)

    logger.error("Unknown notifications action: %s", action)
    return 1
