"""
Aggregation Service for CO2 Monitor

Computes hourly and daily statistics from raw measurements.
Runs periodically to keep aggregates up-to-date.
"""

import sqlite3
from datetime import datetime, timedelta, date
from pathlib import Path
import time
import signal
import sys

from database import CO2Database, DAYTIME_START, DAYTIME_END


class Aggregator:
    """Aggregates raw measurements into minute, hourly, and daily statistics."""

    # Supported minute intervals
    MINUTE_INTERVALS = [5, 10, 15]

    def __init__(self, db_path: str = "data/co2_data.db"):
        self.db = CO2Database(db_path)
        self.db_path = Path(db_path)
        self.running = False

    def aggregate_minute_interval(self, interval_start: datetime,
                                   interval_minutes: int = 15) -> bool:
        """
        Aggregate measurements for a specific minute interval.

        Args:
            interval_start: The start of the interval (e.g., 2025-12-28 14:15:00)
            interval_minutes: The interval size in minutes (5, 10, or 15)

        Returns:
            True if data was aggregated, False if no data for that interval
        """
        interval_end = interval_start + timedelta(minutes=interval_minutes)

        with sqlite3.connect(self.db_path) as conn:
            start_str = interval_start.strftime('%Y-%m-%d %H:%M:%S')
            end_str = interval_end.strftime('%Y-%m-%d %H:%M:%S')

            row = conn.execute("""
                SELECT
                    MIN(co2_ppm) as co2_min,
                    MAX(co2_ppm) as co2_max,
                    AVG(co2_ppm) as co2_avg,
                    COUNT(*) as co2_count,
                    MIN(temperature_celsius) as temp_min,
                    MAX(temperature_celsius) as temp_max,
                    AVG(temperature_celsius) as temp_avg
                FROM measurements
                WHERE timestamp >= ? AND timestamp < ?
            """, (start_str, end_str)).fetchone()

            if row[3] == 0:  # No measurements
                return False

            self.db.insert_minute_stats(
                interval_start=interval_start,
                interval_minutes=interval_minutes,
                co2_min=row[0],
                co2_max=row[1],
                co2_avg=round(row[2], 1),
                co2_count=row[3],
                temp_min=row[4],
                temp_max=row[5],
                temp_avg=round(row[6], 1) if row[6] else None
            )
            return True

    def aggregate_hour(self, hour_start: datetime) -> bool:
        """
        Aggregate measurements for a specific hour.

        Args:
            hour_start: The start of the hour to aggregate (e.g., 2025-12-28 14:00:00)

        Returns:
            True if data was aggregated, False if no data for that hour
        """
        hour_end = hour_start + timedelta(hours=1)

        with sqlite3.connect(self.db_path) as conn:
            # Use space-separated format to match database storage
            start_str = hour_start.strftime('%Y-%m-%d %H:%M:%S')
            end_str = hour_end.strftime('%Y-%m-%d %H:%M:%S')

            row = conn.execute("""
                SELECT
                    MIN(co2_ppm) as co2_min,
                    MAX(co2_ppm) as co2_max,
                    AVG(co2_ppm) as co2_avg,
                    COUNT(*) as co2_count,
                    MIN(temperature_celsius) as temp_min,
                    MAX(temperature_celsius) as temp_max,
                    AVG(temperature_celsius) as temp_avg
                FROM measurements
                WHERE timestamp >= ? AND timestamp < ?
            """, (start_str, end_str)).fetchone()

            if row[3] == 0:  # No measurements
                return False

            self.db.insert_hourly_stats(
                hour_start=hour_start,
                co2_min=row[0],
                co2_max=row[1],
                co2_avg=round(row[2], 1),
                co2_count=row[3],
                temp_min=row[4],
                temp_max=row[5],
                temp_avg=round(row[6], 1) if row[6] else None
            )
            return True

    def aggregate_day(self, stat_date: date) -> bool:
        """
        Aggregate measurements for a specific day.

        Args:
            stat_date: The date to aggregate

        Returns:
            True if data was aggregated, False if no data for that day
        """
        day_start = datetime.combine(stat_date, datetime.min.time())
        day_end = day_start + timedelta(days=1)

        # Use space-separated format to match database storage
        start_str = day_start.strftime('%Y-%m-%d %H:%M:%S')
        end_str = day_end.strftime('%Y-%m-%d %H:%M:%S')

        with sqlite3.connect(self.db_path) as conn:
            # Overall stats
            row = conn.execute("""
                SELECT
                    MIN(co2_ppm) as co2_min,
                    MAX(co2_ppm) as co2_max,
                    AVG(co2_ppm) as co2_avg,
                    COUNT(*) as count,
                    MIN(temperature_celsius) as temp_min,
                    MAX(temperature_celsius) as temp_max,
                    AVG(temperature_celsius) as temp_avg
                FROM measurements
                WHERE timestamp >= ? AND timestamp < ?
            """, (start_str, end_str)).fetchone()

            if row[3] == 0:  # No measurements
                return False

            # Day average (06:00 - 22:00)
            day_avg_row = conn.execute("""
                SELECT AVG(co2_ppm)
                FROM measurements
                WHERE timestamp >= ? AND timestamp < ?
                AND CAST(strftime('%H', timestamp) AS INTEGER) >= ?
                AND CAST(strftime('%H', timestamp) AS INTEGER) < ?
            """, (start_str, end_str, DAYTIME_START, DAYTIME_END)).fetchone()

            # Night average (22:00 - 06:00)
            night_avg_row = conn.execute("""
                SELECT AVG(co2_ppm)
                FROM measurements
                WHERE timestamp >= ? AND timestamp < ?
                AND (CAST(strftime('%H', timestamp) AS INTEGER) >= ?
                     OR CAST(strftime('%H', timestamp) AS INTEGER) < ?)
            """, (start_str, end_str, DAYTIME_END, DAYTIME_START)).fetchone()

            self.db.insert_daily_stats(
                stat_date=stat_date,
                co2_min=row[0],
                co2_max=row[1],
                co2_avg=round(row[2], 1),
                co2_day_avg=round(day_avg_row[0], 1) if day_avg_row[0] else None,
                co2_night_avg=round(night_avg_row[0], 1) if night_avg_row[0] else None,
                temp_min=row[4],
                temp_max=row[5],
                temp_avg=round(row[6], 1) if row[6] else None,
                measurement_count=row[3]
            )
            return True

    def backfill_all(self):
        """
        Backfill all historical aggregates from existing measurements.
        Call this after migration or to rebuild aggregates.
        """
        print("Starting backfill of historical aggregates...")

        with sqlite3.connect(self.db_path) as conn:
            # Get the date range of measurements
            row = conn.execute("""
                SELECT MIN(timestamp), MAX(timestamp)
                FROM measurements
            """).fetchone()

            if not row[0]:
                print("No measurements to aggregate.")
                return

            start = datetime.fromisoformat(row[0])
            end = datetime.fromisoformat(row[1])

        # Aggregate by minute intervals (5, 10, 15)
        for interval in self.MINUTE_INTERVALS:
            print(f"Aggregating {interval}-minute stats from {start} to {end}...")
            # Round start down to nearest interval boundary
            current = start.replace(
                minute=(start.minute // interval) * interval,
                second=0, microsecond=0
            )
            intervals_aggregated = 0

            while current <= end:
                if self.aggregate_minute_interval(current, interval):
                    intervals_aggregated += 1
                current += timedelta(minutes=interval)

            print(f"Aggregated {intervals_aggregated} {interval}-minute intervals.")

        # Aggregate by hour
        print(f"Aggregating hourly stats from {start} to {end}...")
        current_hour = start.replace(minute=0, second=0, microsecond=0)
        hours_aggregated = 0

        while current_hour <= end:
            if self.aggregate_hour(current_hour):
                hours_aggregated += 1
            current_hour += timedelta(hours=1)

        print(f"Aggregated {hours_aggregated} hours.")

        # Aggregate by day
        print("Aggregating daily stats...")
        current_date = start.date()
        days_aggregated = 0

        while current_date <= end.date():
            if self.aggregate_day(current_date):
                days_aggregated += 1
            current_date += timedelta(days=1)

        print(f"Aggregated {days_aggregated} days.")
        print("Backfill complete!")

    def run_incremental(self):
        """
        Run incremental aggregation for current and recent time periods.
        Call this periodically (e.g., every 5 minutes).
        """
        now = datetime.now()

        # Aggregate minute intervals for current and previous periods
        for interval in self.MINUTE_INTERVALS:
            # Current interval
            current_interval = now.replace(
                minute=(now.minute // interval) * interval,
                second=0, microsecond=0
            )
            self.aggregate_minute_interval(current_interval, interval)

            # Previous interval
            prev_interval = current_interval - timedelta(minutes=interval)
            self.aggregate_minute_interval(prev_interval, interval)

        # Aggregate current hour
        current_hour = now.replace(minute=0, second=0, microsecond=0)
        self.aggregate_hour(current_hour)

        # Also aggregate previous hour (in case it wasn't complete)
        previous_hour = current_hour - timedelta(hours=1)
        self.aggregate_hour(previous_hour)

        # Aggregate today
        self.aggregate_day(now.date())

        # Also aggregate yesterday (in case of late data)
        yesterday = now.date() - timedelta(days=1)
        self.aggregate_day(yesterday)

    def cleanup_old_raw_data(self, days_to_keep: int = 30, max_size_gb: float = 5.0):
        """
        Delete raw measurements older than N days or if database exceeds size limit.
        Aggregates are kept forever.
        """
        deleted = self.db.cleanup_if_size_exceeded(max_size_gb, days_to_keep)
        if deleted > 0:
            size_mb = self.db.get_database_size_mb()
            print(f"Cleaned up {deleted} old measurements (keeping {days_to_keep} days, "
                  f"max {max_size_gb}GB). Current size: {size_mb:.1f}MB")
        return deleted

    def run_daemon(self, interval_minutes: int = 5):
        """
        Run as a daemon, aggregating periodically.

        Args:
            interval_minutes: How often to run aggregation
        """
        self.running = True

        def signal_handler(signum, frame):
            print("\nStopping aggregator...")
            self.running = False

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        print(f"Aggregator daemon started. Running every {interval_minutes} minutes.")
        print("Press Ctrl+C to stop.")

        # Initial backfill
        self.backfill_all()

        while self.running:
            try:
                self.run_incremental()

                # Cleanup once per hour
                if datetime.now().minute < interval_minutes:
                    self.cleanup_old_raw_data()

            except Exception as e:
                print(f"Aggregation error: {e}")

            # Sleep in small increments to respond to signals
            for _ in range(interval_minutes * 60 // 5):
                if not self.running:
                    break
                time.sleep(5)

        print("Aggregator stopped.")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="CO2 Monitor Aggregation Service")
    parser.add_argument(
        "--backfill", action="store_true",
        help="Backfill all historical aggregates and exit"
    )
    parser.add_argument(
        "--daemon", action="store_true",
        help="Run as daemon (periodic aggregation)"
    )
    parser.add_argument(
        "--interval", type=int, default=5,
        help="Aggregation interval in minutes (default: 5)"
    )
    parser.add_argument(
        "--cleanup", type=int, metavar="DAYS", default=30,
        nargs='?', const=30,
        help="Clean up raw data older than N days (default: 30, max 5GB)"
    )
    parser.add_argument(
        "--max-size", type=float, default=5.0,
        help="Maximum database size in GB before cleanup (default: 5.0)"
    )
    parser.add_argument(
        "-d", "--database", type=str, default="data/co2_data.db",
        help="Path to SQLite database"
    )

    args = parser.parse_args()

    aggregator = Aggregator(args.database)

    if args.backfill:
        aggregator.backfill_all()
    elif args.daemon:
        aggregator.run_daemon(args.interval)
    elif '--cleanup' in sys.argv:
        aggregator.cleanup_old_raw_data(args.cleanup, args.max_size)
    else:
        # Default: run once
        print("Running incremental aggregation...")
        aggregator.run_incremental()
        print("Done.")


if __name__ == "__main__":
    main()
