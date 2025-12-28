#!/usr/bin/env python3
"""
CO2 Tracker - Main Application

Continuously reads CO2 and temperature from the TFA Dostmann AirControl Mini
and stores measurements in a SQLite database.
"""

import argparse
import signal
import sys
import time
from datetime import datetime

from co2_reader import CO2Reader, list_devices
from database import CO2Database


class CO2Tracker:
    """Main tracker application."""

    def __init__(self, db_path: str = "data/co2_data.db", interval: int = 60):
        """
        Initialize the tracker.

        Args:
            db_path: Path to SQLite database
            interval: Reading interval in seconds
        """
        self.db = CO2Database(db_path)
        self.reader = CO2Reader()
        self.interval = interval
        self.running = False

    def start(self):
        """Start tracking CO2 levels."""
        print("=" * 50)
        print("CO2 Monitor Tracker")
        print("=" * 50)

        # Check for device
        devices = list_devices()
        if not devices:
            print("ERROR: No CO2 monitor found!")
            print("Make sure the device is connected via USB.")
            return False

        print(f"Found CO2 monitor: {devices[0].get('product_string', 'Unknown')}")

        # Connect to device
        if not self.reader.connect():
            print("ERROR: Failed to connect to device!")
            return False

        print(f"Connected successfully!")
        print(f"Reading interval: {self.interval} seconds")
        print(f"Database: {self.db.db_path}")
        print("-" * 50)

        self.running = True
        self._run_loop()
        return True

    def stop(self):
        """Stop tracking."""
        self.running = False
        self.reader.disconnect()
        print("\nTracker stopped.")

    def _run_loop(self):
        """Main tracking loop."""
        consecutive_errors = 0
        max_errors = 5

        while self.running:
            try:
                # Read from device
                reading = self.reader.read(timeout_seconds=10)

                if reading.co2_ppm is not None:
                    # Store in database
                    self.db.insert(
                        co2_ppm=reading.co2_ppm,
                        temperature_celsius=reading.temperature_celsius
                    )

                    # Display current reading
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    co2_status = self._get_co2_status(reading.co2_ppm)
                    temp_str = f"{reading.temperature_celsius}°C" if reading.temperature_celsius else "N/A"

                    print(f"[{timestamp}] CO2: {reading.co2_ppm:4d} ppm {co2_status} | Temp: {temp_str}")

                    consecutive_errors = 0
                else:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] Warning: No CO2 reading received")
                    consecutive_errors += 1

            except IOError as e:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Error reading device: {e}")
                consecutive_errors += 1

                # Try to reconnect
                if consecutive_errors < max_errors:
                    print("Attempting to reconnect...")
                    time.sleep(2)
                    self.reader.disconnect()
                    if self.reader.connect():
                        print("Reconnected!")
                    else:
                        print("Reconnection failed")

            except Exception as e:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Unexpected error: {e}")
                consecutive_errors += 1

            # Check for too many consecutive errors
            if consecutive_errors >= max_errors:
                print(f"\nToo many consecutive errors ({max_errors}). Stopping.")
                self.running = False
                break

            # Wait for next reading
            if self.running:
                time.sleep(self.interval)

    def _get_co2_status(self, co2_ppm: int) -> str:
        """Get a status indicator for CO2 level."""
        if co2_ppm < 800:
            return "[Good]"
        elif co2_ppm < 1000:
            return "[OK]"
        elif co2_ppm < 1500:
            return "[Poor]"
        else:
            return "[Bad!]"

    def show_statistics(self):
        """Display statistics from the database."""
        print("\n" + "=" * 50)
        print("Statistics (Last 24 Hours)")
        print("=" * 50)

        stats = self.db.get_statistics(hours=24)

        if stats['count'] == 0:
            print("No data available.")
            return

        print(f"Measurements: {stats['count']}")
        print()
        print("CO2 (ppm):")
        print(f"  Min: {stats['co2']['min']}")
        print(f"  Max: {stats['co2']['max']}")
        print(f"  Avg: {stats['co2']['avg']}")
        print()
        print("Temperature (°C):")
        print(f"  Min: {stats['temperature']['min']}")
        print(f"  Max: {stats['temperature']['max']}")
        print(f"  Avg: {stats['temperature']['avg']}")
        print("=" * 50)


def main():
    parser = argparse.ArgumentParser(
        description="Track CO2 levels from TFA Dostmann AirControl Mini"
    )
    parser.add_argument(
        "-i", "--interval",
        type=int,
        default=60,
        help="Reading interval in seconds (default: 60)"
    )
    parser.add_argument(
        "-d", "--database",
        type=str,
        default="data/co2_data.db",
        help="Path to SQLite database (default: data/co2_data.db)"
    )
    parser.add_argument(
        "-s", "--stats",
        action="store_true",
        help="Show statistics and exit"
    )
    parser.add_argument(
        "-l", "--list",
        action="store_true",
        help="List connected devices and exit"
    )

    args = parser.parse_args()

    # List devices
    if args.list:
        devices = list_devices()
        if devices:
            print("Found devices:")
            for d in devices:
                print(f"  - {d.get('product_string', 'Unknown')} "
                      f"(VID: 0x{d['vendor_id']:04X}, PID: 0x{d['product_id']:04X})")
        else:
            print("No CO2 monitor devices found.")
        return

    tracker = CO2Tracker(db_path=args.database, interval=args.interval)

    # Show statistics only
    if args.stats:
        tracker.show_statistics()
        return

    # Setup signal handlers for graceful shutdown
    def signal_handler(signum, frame):
        print("\nReceived interrupt signal...")
        tracker.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Start tracking
    if not tracker.start():
        sys.exit(1)


if __name__ == "__main__":
    main()
