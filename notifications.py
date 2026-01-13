#!/usr/bin/env python3
"""
System Notifications
Handles sending system notifications for CO2 alarms.
"""

import subprocess
import platform
from datetime import datetime, timedelta
from typing import Optional


class NotificationManager:
    """Manages system notifications with cooldown."""

    def __init__(self):
        self.last_notification: Optional[datetime] = None

    def send_notification(self, title: str, message: str, sound: bool = True) -> bool:
        """
        Send a system notification.

        Args:
            title: Notification title
            message: Notification message
            sound: Play system sound

        Returns:
            True if notification was sent successfully
        """
        system = platform.system()

        try:
            if system == "Darwin":  # macOS
                return self._send_macos_notification(title, message, sound)
            elif system == "Linux":
                return self._send_linux_notification(title, message, sound)
            else:
                print(f"Notifications not supported on {system}")
                return False
        except Exception as e:
            print(f"Failed to send notification: {e}")
            return False

    def _send_macos_notification(self, title: str, message: str, sound: bool) -> bool:
        """Send notification on macOS using osascript."""
        sound_param = ' sound name "Glass"' if sound else ''
        script = f'display notification "{message}" with title "{title}"{sound_param}'

        result = subprocess.run(
            ['osascript', '-e', script],
            capture_output=True,
            text=True
        )
        return result.returncode == 0

    def _send_linux_notification(self, title: str, message: str, sound: bool) -> bool:
        """Send notification on Linux using notify-send."""
        cmd = ['notify-send', title, message]
        if sound:
            cmd.extend(['-u', 'critical'])

        result = subprocess.run(cmd, capture_output=True)
        return result.returncode == 0

    def should_notify(self, cooldown_minutes: int) -> bool:
        """
        Check if enough time has passed since last notification.

        Args:
            cooldown_minutes: Minimum minutes between notifications

        Returns:
            True if notification should be sent
        """
        if self.last_notification is None:
            return True

        cooldown_period = timedelta(minutes=cooldown_minutes)
        return datetime.now() - self.last_notification > cooldown_period

    def mark_notified(self) -> None:
        """Record that a notification was just sent."""
        self.last_notification = datetime.now()

    def send_co2_alarm(self, co2_ppm: int, threshold: int, cooldown_minutes: int) -> bool:
        """
        Send a CO2 alarm notification if cooldown period has passed.

        Args:
            co2_ppm: Current CO2 level
            threshold: Alarm threshold
            cooldown_minutes: Cooldown period

        Returns:
            True if notification was sent
        """
        if not self.should_notify(cooldown_minutes):
            return False

        title = "⚠️ High CO2 Level!"
        message = f"CO2 is at {co2_ppm} ppm (threshold: {threshold} ppm). Consider opening a window."

        success = self.send_notification(title, message, sound=True)
        if success:
            self.mark_notified()
            print(f"Sent CO2 alarm notification: {co2_ppm} ppm")

        return success
