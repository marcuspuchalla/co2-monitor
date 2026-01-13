"""
Database Module for CO2 Monitor

Handles SQLite storage for CO2 and temperature measurements with aggregation support.
"""

import sqlite3
from datetime import datetime, timedelta, date
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

# Time definitions
DAYTIME_START = 6   # 06:00
DAYTIME_END = 22    # 22:00
WORKDAY_START = 8   # 08:00
WORKDAY_END = 18    # 18:00


@dataclass
class Measurement:
    """A stored measurement from the database."""
    id: int
    timestamp: datetime
    co2_ppm: int
    temperature_celsius: float


@dataclass
class HourlyStats:
    """Hourly aggregated statistics."""
    id: int
    hour_start: datetime
    co2_min: int
    co2_max: int
    co2_avg: float
    co2_count: int
    temp_min: float
    temp_max: float
    temp_avg: float
    is_workday: bool
    is_daytime: bool
    hour_of_day: int
    day_of_week: int


@dataclass
class DailyStats:
    """Daily aggregated statistics."""
    id: int
    date: date
    co2_min: int
    co2_max: int
    co2_avg: float
    co2_day_avg: float
    co2_night_avg: float
    temp_min: float
    temp_max: float
    temp_avg: float
    measurement_count: int
    is_weekend: bool


@dataclass
class MinuteStats:
    """Minute-level aggregated statistics (5, 10, or 15 minute intervals)."""
    id: int
    interval_start: datetime
    interval_minutes: int  # 5, 10, or 15
    co2_min: int
    co2_max: int
    co2_avg: float
    co2_count: int
    temp_min: float
    temp_max: float
    temp_avg: float


class CO2Database:
    """SQLite database for storing CO2 measurements with aggregation support."""

    SCHEMA_VERSION = 3

    def __init__(self, db_path: str = "data/co2_data.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Initialize the database schema."""
        with sqlite3.connect(self.db_path) as conn:
            # Check schema version
            try:
                version = conn.execute(
                    "SELECT value FROM metadata WHERE key = 'schema_version'"
                ).fetchone()
                current_version = int(version[0]) if version else 1
            except sqlite3.OperationalError:
                current_version = 1

            # Original measurements table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS measurements (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    co2_ppm INTEGER NOT NULL,
                    temperature_celsius REAL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_measurements_timestamp
                ON measurements(timestamp)
            """)

            # Migrate to v2 if needed
            if current_version < 2:
                self._migrate_to_v2(conn)

            # Migrate to v3 if needed
            if current_version < 3:
                self._migrate_to_v3(conn)

            conn.commit()

    def _migrate_to_v2(self, conn):
        """Migrate database to schema version 2."""
        print("Migrating database to schema v2...")

        # Metadata table for schema versioning
        conn.execute("""
            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)

        # Hourly aggregates table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS hourly_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hour_start DATETIME NOT NULL UNIQUE,
                co2_min INTEGER,
                co2_max INTEGER,
                co2_avg REAL,
                co2_count INTEGER,
                temp_min REAL,
                temp_max REAL,
                temp_avg REAL,
                is_workday BOOLEAN,
                is_daytime BOOLEAN,
                hour_of_day INTEGER,
                day_of_week INTEGER
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_hourly_hour_start
            ON hourly_stats(hour_start)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_hourly_hour_of_day
            ON hourly_stats(hour_of_day)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_hourly_day_of_week
            ON hourly_stats(day_of_week)
        """)

        # Daily aggregates table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS daily_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date DATE NOT NULL UNIQUE,
                co2_min INTEGER,
                co2_max INTEGER,
                co2_avg REAL,
                co2_day_avg REAL,
                co2_night_avg REAL,
                temp_min REAL,
                temp_max REAL,
                temp_avg REAL,
                measurement_count INTEGER,
                is_weekend BOOLEAN
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_daily_date
            ON daily_stats(date)
        """)

        # Pattern averages table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS pattern_averages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pattern_type TEXT NOT NULL,
                pattern_key TEXT NOT NULL,
                co2_avg REAL,
                temp_avg REAL,
                sample_count INTEGER,
                last_updated DATETIME,
                UNIQUE(pattern_type, pattern_key)
            )
        """)

        # Update schema version
        conn.execute("""
            INSERT OR REPLACE INTO metadata (key, value) VALUES ('schema_version', '2')
        """)

        print("Migration to v2 complete.")

    def _migrate_to_v3(self, conn):
        """Migrate database to schema version 3 - add minute-level aggregates."""
        print("Migrating database to schema v3...")

        # Minute-level aggregates table (supports 5, 10, 15 minute intervals)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS minute_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                interval_start DATETIME NOT NULL,
                interval_minutes INTEGER NOT NULL,
                co2_min INTEGER,
                co2_max INTEGER,
                co2_avg REAL,
                co2_count INTEGER,
                temp_min REAL,
                temp_max REAL,
                temp_avg REAL,
                UNIQUE(interval_start, interval_minutes)
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_minute_interval_start
            ON minute_stats(interval_start)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_minute_interval_minutes
            ON minute_stats(interval_minutes)
        """)

        # Update schema version
        conn.execute("""
            INSERT OR REPLACE INTO metadata (key, value) VALUES ('schema_version', '3')
        """)

        print("Migration to v3 complete.")

    # ==================== Raw Measurements ====================

    def insert(self, co2_ppm: int, temperature_celsius: Optional[float] = None) -> int:
        """Insert a new measurement."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "INSERT INTO measurements (co2_ppm, temperature_celsius) VALUES (?, ?)",
                (co2_ppm, temperature_celsius)
            )
            conn.commit()
            return cursor.lastrowid

    def get_latest(self) -> Optional[Measurement]:
        """Get the most recent measurement."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM measurements ORDER BY timestamp DESC LIMIT 1"
            ).fetchone()

            if row:
                return Measurement(
                    id=row['id'],
                    timestamp=datetime.fromisoformat(row['timestamp']),
                    co2_ppm=row['co2_ppm'],
                    temperature_celsius=row['temperature_celsius']
                )
            return None

    def get_range(self, start: datetime, end: datetime) -> list[Measurement]:
        """Get measurements within a time range."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """SELECT * FROM measurements
                   WHERE timestamp BETWEEN ? AND ?
                   ORDER BY timestamp""",
                (start.strftime('%Y-%m-%d %H:%M:%S'), end.strftime('%Y-%m-%d %H:%M:%S'))
            ).fetchall()

            return [
                Measurement(
                    id=row['id'],
                    timestamp=datetime.fromisoformat(row['timestamp']),
                    co2_ppm=row['co2_ppm'],
                    temperature_celsius=row['temperature_celsius']
                )
                for row in rows
            ]

    def get_last_hours(self, hours: int = 24) -> list[Measurement]:
        """Get measurements from the last N hours."""
        end = datetime.now()
        start = end - timedelta(hours=hours)
        return self.get_range(start, end)

    def get_statistics(self, hours: int = 24) -> dict:
        """Get statistics for the last N hours."""
        start = (datetime.now() - timedelta(hours=hours)).strftime('%Y-%m-%d %H:%M:%S')

        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                """SELECT
                    COUNT(*) as count,
                    MIN(co2_ppm) as min_co2,
                    MAX(co2_ppm) as max_co2,
                    AVG(co2_ppm) as avg_co2,
                    MIN(temperature_celsius) as min_temp,
                    MAX(temperature_celsius) as max_temp,
                    AVG(temperature_celsius) as avg_temp
                   FROM measurements
                   WHERE timestamp >= ?""",
                (start,)
            ).fetchone()

            return {
                'count': row[0],
                'co2': {
                    'min': row[1],
                    'max': row[2],
                    'avg': round(row[3], 1) if row[3] else None
                },
                'temperature': {
                    'min': row[4],
                    'max': row[5],
                    'avg': round(row[6], 1) if row[6] else None
                }
            }

    def count(self) -> int:
        """Get total number of measurements."""
        with sqlite3.connect(self.db_path) as conn:
            return conn.execute("SELECT COUNT(*) FROM measurements").fetchone()[0]

    def delete_older_than(self, days: int) -> int:
        """Delete measurements older than N days."""
        cutoff = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM measurements WHERE timestamp < ?",
                (cutoff,)
            )
            conn.commit()
            return cursor.rowcount

    def get_database_size_mb(self) -> float:
        """Get database file size in megabytes."""
        if self.db_path.exists():
            return self.db_path.stat().st_size / (1024 * 1024)
        return 0.0

    def cleanup_if_size_exceeded(self, max_size_gb: float = 5.0, days_to_keep: int = 30) -> int:
        """
        Delete old measurements if database exceeds size limit.
        First tries to enforce the days_to_keep limit.
        If still over limit, progressively deletes older data.

        Returns number of deleted measurements.
        """
        total_deleted = 0
        max_size_mb = max_size_gb * 1024

        # First, enforce the standard retention period
        deleted = self.delete_older_than(days_to_keep)
        total_deleted += deleted

        # Check if we're still over the size limit
        current_size = self.get_database_size_mb()
        if current_size <= max_size_mb:
            return total_deleted

        # Progressively delete older data until under limit
        days_to_delete = days_to_keep - 1
        while current_size > max_size_mb and days_to_delete > 1:
            deleted = self.delete_older_than(days_to_delete)
            total_deleted += deleted

            # Run VACUUM to reclaim space
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("VACUUM")

            current_size = self.get_database_size_mb()
            days_to_delete -= 1

        return total_deleted

    # ==================== Hourly Stats ====================

    def get_hourly_stats(self, start: datetime, end: datetime) -> list[HourlyStats]:
        """Get hourly stats within a time range."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """SELECT * FROM hourly_stats
                   WHERE hour_start BETWEEN ? AND ?
                   ORDER BY hour_start""",
                (start.strftime('%Y-%m-%d %H:%M:%S'), end.strftime('%Y-%m-%d %H:%M:%S'))
            ).fetchall()

            return [
                HourlyStats(
                    id=row['id'],
                    hour_start=datetime.fromisoformat(row['hour_start']),
                    co2_min=row['co2_min'],
                    co2_max=row['co2_max'],
                    co2_avg=row['co2_avg'],
                    co2_count=row['co2_count'],
                    temp_min=row['temp_min'],
                    temp_max=row['temp_max'],
                    temp_avg=row['temp_avg'],
                    is_workday=bool(row['is_workday']),
                    is_daytime=bool(row['is_daytime']),
                    hour_of_day=row['hour_of_day'],
                    day_of_week=row['day_of_week']
                )
                for row in rows
            ]

    def get_hourly_stats_last_days(self, days: int = 7) -> list[HourlyStats]:
        """Get hourly stats from the last N days."""
        end = datetime.now()
        start = end - timedelta(days=days)
        return self.get_hourly_stats(start, end)

    def insert_hourly_stats(self, hour_start: datetime, co2_min: int, co2_max: int,
                            co2_avg: float, co2_count: int, temp_min: float,
                            temp_max: float, temp_avg: float):
        """Insert or update hourly stats."""
        hour_of_day = hour_start.hour
        day_of_week = hour_start.weekday()
        is_daytime = DAYTIME_START <= hour_of_day < DAYTIME_END
        is_workday = day_of_week < 5 and WORKDAY_START <= hour_of_day < WORKDAY_END

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO hourly_stats
                (hour_start, co2_min, co2_max, co2_avg, co2_count,
                 temp_min, temp_max, temp_avg, is_workday, is_daytime,
                 hour_of_day, day_of_week)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (hour_start.strftime('%Y-%m-%d %H:%M:%S'), co2_min, co2_max, co2_avg, co2_count,
                  temp_min, temp_max, temp_avg, is_workday, is_daytime,
                  hour_of_day, day_of_week))
            conn.commit()

    # ==================== Minute Stats ====================

    def get_minute_stats(self, start: datetime, end: datetime,
                         interval_minutes: int = 15) -> list[MinuteStats]:
        """Get minute-level stats within a time range for a specific interval."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """SELECT * FROM minute_stats
                   WHERE interval_start BETWEEN ? AND ?
                   AND interval_minutes = ?
                   ORDER BY interval_start""",
                (start.strftime('%Y-%m-%d %H:%M:%S'), end.strftime('%Y-%m-%d %H:%M:%S'), interval_minutes)
            ).fetchall()

            return [
                MinuteStats(
                    id=row['id'],
                    interval_start=datetime.fromisoformat(row['interval_start']),
                    interval_minutes=row['interval_minutes'],
                    co2_min=row['co2_min'],
                    co2_max=row['co2_max'],
                    co2_avg=row['co2_avg'],
                    co2_count=row['co2_count'],
                    temp_min=row['temp_min'],
                    temp_max=row['temp_max'],
                    temp_avg=row['temp_avg']
                )
                for row in rows
            ]

    def get_minute_stats_last_hours(self, hours: int = 24,
                                    interval_minutes: int = 15) -> list[MinuteStats]:
        """Get minute-level stats from the last N hours."""
        end = datetime.now()
        start = end - timedelta(hours=hours)
        return self.get_minute_stats(start, end, interval_minutes)

    def insert_minute_stats(self, interval_start: datetime, interval_minutes: int,
                            co2_min: int, co2_max: int, co2_avg: float, co2_count: int,
                            temp_min: float, temp_max: float, temp_avg: float):
        """Insert or update minute-level stats."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO minute_stats
                (interval_start, interval_minutes, co2_min, co2_max, co2_avg, co2_count,
                 temp_min, temp_max, temp_avg)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (interval_start.strftime('%Y-%m-%d %H:%M:%S'), interval_minutes, co2_min, co2_max,
                  co2_avg, co2_count, temp_min, temp_max, temp_avg))
            conn.commit()

    # ==================== Daily Stats ====================

    def get_daily_stats(self, start_date: date, end_date: date) -> list[DailyStats]:
        """Get daily stats within a date range."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """SELECT * FROM daily_stats
                   WHERE date BETWEEN ? AND ?
                   ORDER BY date""",
                (start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))
            ).fetchall()

            return [
                DailyStats(
                    id=row['id'],
                    date=date.fromisoformat(row['date']),
                    co2_min=row['co2_min'],
                    co2_max=row['co2_max'],
                    co2_avg=row['co2_avg'],
                    co2_day_avg=row['co2_day_avg'],
                    co2_night_avg=row['co2_night_avg'],
                    temp_min=row['temp_min'],
                    temp_max=row['temp_max'],
                    temp_avg=row['temp_avg'],
                    measurement_count=row['measurement_count'],
                    is_weekend=bool(row['is_weekend'])
                )
                for row in rows
            ]

    def get_daily_stats_last_days(self, days: int = 30) -> list[DailyStats]:
        """Get daily stats from the last N days."""
        end = date.today()
        start = end - timedelta(days=days)
        return self.get_daily_stats(start, end)

    def insert_daily_stats(self, stat_date: date, co2_min: int, co2_max: int,
                           co2_avg: float, co2_day_avg: float, co2_night_avg: float,
                           temp_min: float, temp_max: float, temp_avg: float,
                           measurement_count: int):
        """Insert or update daily stats."""
        is_weekend = stat_date.weekday() >= 5

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO daily_stats
                (date, co2_min, co2_max, co2_avg, co2_day_avg, co2_night_avg,
                 temp_min, temp_max, temp_avg, measurement_count, is_weekend)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (stat_date.strftime('%Y-%m-%d'), co2_min, co2_max, co2_avg,
                  co2_day_avg, co2_night_avg, temp_min, temp_max, temp_avg,
                  measurement_count, is_weekend))
            conn.commit()

    # ==================== Pattern Averages ====================

    def get_pattern_averages(self, pattern_type: str) -> list[dict]:
        """Get all averages for a pattern type."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """SELECT pattern_key, co2_avg, temp_avg, sample_count
                   FROM pattern_averages
                   WHERE pattern_type = ?
                   ORDER BY pattern_key""",
                (pattern_type,)
            ).fetchall()

            return [dict(row) for row in rows]

    def update_pattern_average(self, pattern_type: str, pattern_key: str,
                               co2_avg: float, temp_avg: float, sample_count: int):
        """Update a pattern average."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO pattern_averages
                (pattern_type, pattern_key, co2_avg, temp_avg, sample_count, last_updated)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (pattern_type, pattern_key, co2_avg, temp_avg, sample_count,
                  datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            conn.commit()

    # ==================== Analytics Queries ====================

    def get_hourly_pattern(self) -> list[dict]:
        """Get average CO2/temp by hour of day."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute("""
                SELECT
                    hour_of_day,
                    AVG(co2_avg) as co2_avg,
                    AVG(temp_avg) as temp_avg,
                    SUM(co2_count) as sample_count
                FROM hourly_stats
                GROUP BY hour_of_day
                ORDER BY hour_of_day
            """).fetchall()

            return [
                {
                    'hour': row[0],
                    'co2_avg': round(row[1], 1) if row[1] else None,
                    'temp_avg': round(row[2], 1) if row[2] else None,
                    'sample_count': row[3]
                }
                for row in rows
            ]

    def get_weekly_pattern(self) -> list[dict]:
        """Get average CO2/temp by day of week."""
        day_names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute("""
                SELECT
                    day_of_week,
                    AVG(co2_avg) as co2_avg,
                    AVG(temp_avg) as temp_avg,
                    SUM(co2_count) as sample_count
                FROM hourly_stats
                GROUP BY day_of_week
                ORDER BY day_of_week
            """).fetchall()

            return [
                {
                    'day': day_names[row[0]],
                    'day_num': row[0],
                    'co2_avg': round(row[1], 1) if row[1] else None,
                    'temp_avg': round(row[2], 1) if row[2] else None,
                    'sample_count': row[3]
                }
                for row in rows
            ]

    def get_day_night_comparison(self) -> dict:
        """Get average CO2/temp for day vs night."""
        with sqlite3.connect(self.db_path) as conn:
            # Day averages (06:00 - 22:00)
            day_row = conn.execute("""
                SELECT
                    AVG(co2_avg) as co2_avg,
                    AVG(temp_avg) as temp_avg,
                    SUM(co2_count) as sample_count
                FROM hourly_stats
                WHERE is_daytime = 1
            """).fetchone()

            # Night averages (22:00 - 06:00)
            night_row = conn.execute("""
                SELECT
                    AVG(co2_avg) as co2_avg,
                    AVG(temp_avg) as temp_avg,
                    SUM(co2_count) as sample_count
                FROM hourly_stats
                WHERE is_daytime = 0
            """).fetchone()

            return {
                'day': {
                    'co2_avg': round(day_row[0], 1) if day_row[0] else None,
                    'temp_avg': round(day_row[1], 1) if day_row[1] else None,
                    'sample_count': day_row[2] or 0,
                    'hours': f"{DAYTIME_START:02d}:00 - {DAYTIME_END:02d}:00"
                },
                'night': {
                    'co2_avg': round(night_row[0], 1) if night_row[0] else None,
                    'temp_avg': round(night_row[1], 1) if night_row[1] else None,
                    'sample_count': night_row[2] or 0,
                    'hours': f"{DAYTIME_END:02d}:00 - {DAYTIME_START:02d}:00"
                }
            }

    def get_workday_weekend_comparison(self) -> dict:
        """Get average CO2/temp for workday hours vs weekend."""
        with sqlite3.connect(self.db_path) as conn:
            # Workday averages (Mon-Fri 08:00-18:00)
            workday_row = conn.execute("""
                SELECT
                    AVG(co2_avg) as co2_avg,
                    AVG(temp_avg) as temp_avg,
                    SUM(co2_count) as sample_count
                FROM hourly_stats
                WHERE is_workday = 1
            """).fetchone()

            # Weekend averages
            weekend_row = conn.execute("""
                SELECT
                    AVG(co2_avg) as co2_avg,
                    AVG(temp_avg) as temp_avg,
                    SUM(co2_count) as sample_count
                FROM hourly_stats
                WHERE day_of_week >= 5
            """).fetchone()

            return {
                'workday': {
                    'co2_avg': round(workday_row[0], 1) if workday_row[0] else None,
                    'temp_avg': round(workday_row[1], 1) if workday_row[1] else None,
                    'sample_count': workday_row[2] or 0,
                    'description': f"Mon-Fri {WORKDAY_START:02d}:00-{WORKDAY_END:02d}:00"
                },
                'weekend': {
                    'co2_avg': round(weekend_row[0], 1) if weekend_row[0] else None,
                    'temp_avg': round(weekend_row[1], 1) if weekend_row[1] else None,
                    'sample_count': weekend_row[2] or 0,
                    'description': "Sat-Sun all day"
                }
            }

    def get_stats_for_range(self, start: datetime, end: datetime) -> dict:
        """Get comprehensive stats for a date range."""
        with sqlite3.connect(self.db_path) as conn:
            # Overall stats from raw measurements
            row = conn.execute("""
                SELECT
                    COUNT(*) as count,
                    MIN(co2_ppm) as co2_min,
                    MAX(co2_ppm) as co2_max,
                    AVG(co2_ppm) as co2_avg,
                    MIN(temperature_celsius) as temp_min,
                    MAX(temperature_celsius) as temp_max,
                    AVG(temperature_celsius) as temp_avg
                FROM measurements
                WHERE timestamp BETWEEN ? AND ?
            """, (start.strftime('%Y-%m-%d %H:%M:%S'), end.strftime('%Y-%m-%d %H:%M:%S'))).fetchone()

            # Day/night from hourly stats
            day_night = conn.execute("""
                SELECT
                    is_daytime,
                    AVG(co2_avg) as co2_avg,
                    AVG(temp_avg) as temp_avg
                FROM hourly_stats
                WHERE hour_start BETWEEN ? AND ?
                GROUP BY is_daytime
            """, (start.strftime('%Y-%m-%d %H:%M:%S'), end.strftime('%Y-%m-%d %H:%M:%S'))).fetchall()

            day_stats = next((r for r in day_night if r[0] == 1), None)
            night_stats = next((r for r in day_night if r[0] == 0), None)

            return {
                'period': {
                    'start': start.isoformat(),
                    'end': end.isoformat()
                },
                'count': row[0],
                'co2': {
                    'min': row[1],
                    'max': row[2],
                    'avg': round(row[3], 1) if row[3] else None,
                    'day_avg': round(day_stats[1], 1) if day_stats and day_stats[1] else None,
                    'night_avg': round(night_stats[1], 1) if night_stats and night_stats[1] else None
                },
                'temperature': {
                    'min': row[4],
                    'max': row[5],
                    'avg': round(row[6], 1) if row[6] else None
                }
            }


if __name__ == "__main__":
    # Test database operations
    db = CO2Database()
    print(f"Database initialized at {db.db_path}")
    print(f"Total measurements: {db.count()}")

    # Test new analytics
    print("\nHourly pattern:", db.get_hourly_pattern()[:3], "...")
    print("Weekly pattern:", db.get_weekly_pattern())
    print("Day/Night:", db.get_day_night_comparison())
    print("Workday/Weekend:", db.get_workday_weekend_comparison())
