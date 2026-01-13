#!/usr/bin/env python3
"""
Alarm Settings Manager
Handles storage and retrieval of CO2 alarm settings.
"""

import json
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class AlarmSettings:
    """CO2 alarm configuration."""
    enabled: bool = False
    threshold: int = 1000  # CO2 ppm threshold
    cooldown_minutes: int = 30  # Don't notify again within this period

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> 'AlarmSettings':
        return cls(
            enabled=data.get('enabled', False),
            threshold=data.get('threshold', 1000),
            cooldown_minutes=data.get('cooldown_minutes', 30)
        )


class AlarmSettingsManager:
    """Manages alarm settings persistence."""

    def __init__(self, settings_file: str = "data/alarm_settings.json"):
        self.settings_file = Path(settings_file)
        self.settings_file.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> AlarmSettings:
        """Load alarm settings from file."""
        if not self.settings_file.exists():
            return AlarmSettings()

        try:
            with open(self.settings_file, 'r') as f:
                data = json.load(f)
                return AlarmSettings.from_dict(data)
        except (json.JSONDecodeError, IOError):
            return AlarmSettings()

    def save(self, settings: AlarmSettings) -> None:
        """Save alarm settings to file."""
        with open(self.settings_file, 'w') as f:
            json.dump(settings.to_dict(), f, indent=2)
