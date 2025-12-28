/**
 * Database Module for CO2 Monitor
 *
 * Handles SQLite storage for CO2 and temperature measurements with aggregation support.
 */

import Database from 'better-sqlite3';
import { mkdirSync, existsSync, statSync } from 'fs';
import { dirname } from 'path';

// Time definitions
export const DAYTIME_START = 6;  // 06:00
export const DAYTIME_END = 22;   // 22:00
export const WORKDAY_START = 8;  // 08:00
export const WORKDAY_END = 18;   // 18:00

const SCHEMA_VERSION = 3;

export interface Measurement {
  id: number;
  timestamp: Date;
  co2Ppm: number;
  temperatureCelsius: number | null;
}

export interface MinuteStats {
  id: number;
  intervalStart: Date;
  intervalMinutes: number;
  co2Min: number;
  co2Max: number;
  co2Avg: number;
  co2Count: number;
  tempMin: number | null;
  tempMax: number | null;
  tempAvg: number | null;
}

export interface HourlyStats {
  id: number;
  hourStart: Date;
  co2Min: number;
  co2Max: number;
  co2Avg: number;
  co2Count: number;
  tempMin: number | null;
  tempMax: number | null;
  tempAvg: number | null;
  isWorkday: boolean;
  isDaytime: boolean;
  hourOfDay: number;
  dayOfWeek: number;
}

export interface DailyStats {
  id: number;
  date: string;
  co2Min: number;
  co2Max: number;
  co2Avg: number;
  co2DayAvg: number | null;
  co2NightAvg: number | null;
  tempMin: number | null;
  tempMax: number | null;
  tempAvg: number | null;
  measurementCount: number;
  isWeekend: boolean;
}

export interface Statistics {
  count: number;
  co2: { min: number | null; max: number | null; avg: number | null };
  temperature: { min: number | null; max: number | null; avg: number | null };
}

export interface HourlyPattern {
  hour: number;
  co2Avg: number | null;
  tempAvg: number | null;
  sampleCount: number;
}

export interface WeeklyPattern {
  day: string;
  dayNum: number;
  co2Avg: number | null;
  tempAvg: number | null;
  sampleCount: number;
}

export interface DayNightComparison {
  day: { co2Avg: number | null; tempAvg: number | null; sampleCount: number; hours: string };
  night: { co2Avg: number | null; tempAvg: number | null; sampleCount: number; hours: string };
}

export interface WorkWeekendComparison {
  workday: { co2Avg: number | null; tempAvg: number | null; sampleCount: number; description: string };
  weekend: { co2Avg: number | null; tempAvg: number | null; sampleCount: number; description: string };
}

function formatDate(date: Date): string {
  return date.toISOString().replace('T', ' ').slice(0, 19);
}

function parseDate(str: string): Date {
  return new Date(str.replace(' ', 'T') + 'Z');
}

export class CO2Database {
  private db: Database.Database;
  private dbPath: string;

  constructor(dbPath: string = 'data/co2_data.db') {
    this.dbPath = dbPath;

    // Ensure directory exists
    const dir = dirname(dbPath);
    if (!existsSync(dir)) {
      mkdirSync(dir, { recursive: true });
    }

    this.db = new Database(dbPath);
    this.db.pragma('journal_mode = WAL');
    this.initDb();
  }

  private initDb(): void {
    // Check schema version
    let currentVersion = 1;
    try {
      const row = this.db.prepare(
        "SELECT value FROM metadata WHERE key = 'schema_version'"
      ).get() as { value: string } | undefined;
      if (row) {
        currentVersion = parseInt(row.value, 10);
      }
    } catch {
      currentVersion = 1;
    }

    // Create measurements table
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS measurements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        co2_ppm INTEGER NOT NULL,
        temperature_celsius REAL
      )
    `);
    this.db.exec(`
      CREATE INDEX IF NOT EXISTS idx_measurements_timestamp
      ON measurements(timestamp)
    `);

    // Migrate to v2 if needed
    if (currentVersion < 2) {
      this.migrateToV2();
    }

    // Migrate to v3 if needed
    if (currentVersion < 3) {
      this.migrateToV3();
    }
  }

  private migrateToV2(): void {
    console.log('Migrating database to schema v2...');

    this.db.exec(`
      CREATE TABLE IF NOT EXISTS metadata (
        key TEXT PRIMARY KEY,
        value TEXT
      )
    `);

    this.db.exec(`
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
    `);
    this.db.exec(`CREATE INDEX IF NOT EXISTS idx_hourly_hour_start ON hourly_stats(hour_start)`);
    this.db.exec(`CREATE INDEX IF NOT EXISTS idx_hourly_hour_of_day ON hourly_stats(hour_of_day)`);
    this.db.exec(`CREATE INDEX IF NOT EXISTS idx_hourly_day_of_week ON hourly_stats(day_of_week)`);

    this.db.exec(`
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
    `);
    this.db.exec(`CREATE INDEX IF NOT EXISTS idx_daily_date ON daily_stats(date)`);

    this.db.exec(`
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
    `);

    this.db.prepare(
      "INSERT OR REPLACE INTO metadata (key, value) VALUES ('schema_version', '2')"
    ).run();

    console.log('Migration to v2 complete.');
  }

  private migrateToV3(): void {
    console.log('Migrating database to schema v3...');

    this.db.exec(`
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
    `);
    this.db.exec(`CREATE INDEX IF NOT EXISTS idx_minute_interval_start ON minute_stats(interval_start)`);
    this.db.exec(`CREATE INDEX IF NOT EXISTS idx_minute_interval_minutes ON minute_stats(interval_minutes)`);

    this.db.prepare(
      "INSERT OR REPLACE INTO metadata (key, value) VALUES ('schema_version', '3')"
    ).run();

    console.log('Migration to v3 complete.');
  }

  // ==================== Raw Measurements ====================

  insert(co2Ppm: number, temperatureCelsius: number | null): number {
    const stmt = this.db.prepare(
      'INSERT INTO measurements (co2_ppm, temperature_celsius) VALUES (?, ?)'
    );
    const result = stmt.run(co2Ppm, temperatureCelsius);
    return result.lastInsertRowid as number;
  }

  getLatest(): Measurement | null {
    const row = this.db.prepare(
      'SELECT * FROM measurements ORDER BY timestamp DESC LIMIT 1'
    ).get() as any;

    if (!row) return null;

    return {
      id: row.id,
      timestamp: parseDate(row.timestamp),
      co2Ppm: row.co2_ppm,
      temperatureCelsius: row.temperature_celsius
    };
  }

  getRange(start: Date, end: Date): Measurement[] {
    const rows = this.db.prepare(`
      SELECT * FROM measurements
      WHERE timestamp BETWEEN ? AND ?
      ORDER BY timestamp
    `).all(formatDate(start), formatDate(end)) as any[];

    return rows.map(row => ({
      id: row.id,
      timestamp: parseDate(row.timestamp),
      co2Ppm: row.co2_ppm,
      temperatureCelsius: row.temperature_celsius
    }));
  }

  getStatistics(hours: number = 24): Statistics {
    const start = new Date(Date.now() - hours * 60 * 60 * 1000);
    const row = this.db.prepare(`
      SELECT
        COUNT(*) as count,
        MIN(co2_ppm) as min_co2,
        MAX(co2_ppm) as max_co2,
        AVG(co2_ppm) as avg_co2,
        MIN(temperature_celsius) as min_temp,
        MAX(temperature_celsius) as max_temp,
        AVG(temperature_celsius) as avg_temp
      FROM measurements
      WHERE timestamp >= ?
    `).get(formatDate(start)) as any;

    return {
      count: row.count,
      co2: {
        min: row.min_co2,
        max: row.max_co2,
        avg: row.avg_co2 ? Math.round(row.avg_co2 * 10) / 10 : null
      },
      temperature: {
        min: row.min_temp,
        max: row.max_temp,
        avg: row.avg_temp ? Math.round(row.avg_temp * 10) / 10 : null
      }
    };
  }

  count(): number {
    const row = this.db.prepare('SELECT COUNT(*) as count FROM measurements').get() as any;
    return row.count;
  }

  deleteOlderThan(days: number): number {
    const cutoff = new Date(Date.now() - days * 24 * 60 * 60 * 1000);
    const result = this.db.prepare(
      'DELETE FROM measurements WHERE timestamp < ?'
    ).run(formatDate(cutoff));
    return result.changes;
  }

  getDatabaseSizeMb(): number {
    try {
      const stats = statSync(this.dbPath);
      return stats.size / (1024 * 1024);
    } catch {
      return 0;
    }
  }

  cleanupIfSizeExceeded(maxSizeGb: number = 5.0, daysToKeep: number = 30): number {
    let totalDeleted = 0;
    const maxSizeMb = maxSizeGb * 1024;

    // First, enforce the standard retention period
    totalDeleted += this.deleteOlderThan(daysToKeep);

    // Check if we're still over the size limit
    let currentSize = this.getDatabaseSizeMb();
    if (currentSize <= maxSizeMb) {
      return totalDeleted;
    }

    // Progressively delete older data until under limit
    let daysToDelete = daysToKeep - 1;
    while (currentSize > maxSizeMb && daysToDelete > 1) {
      totalDeleted += this.deleteOlderThan(daysToDelete);
      this.db.exec('VACUUM');
      currentSize = this.getDatabaseSizeMb();
      daysToDelete--;
    }

    return totalDeleted;
  }

  // ==================== Minute Stats ====================

  getMinuteStats(start: Date, end: Date, intervalMinutes: number = 15): MinuteStats[] {
    const rows = this.db.prepare(`
      SELECT * FROM minute_stats
      WHERE interval_start BETWEEN ? AND ?
      AND interval_minutes = ?
      ORDER BY interval_start
    `).all(formatDate(start), formatDate(end), intervalMinutes) as any[];

    return rows.map(row => ({
      id: row.id,
      intervalStart: parseDate(row.interval_start),
      intervalMinutes: row.interval_minutes,
      co2Min: row.co2_min,
      co2Max: row.co2_max,
      co2Avg: row.co2_avg,
      co2Count: row.co2_count,
      tempMin: row.temp_min,
      tempMax: row.temp_max,
      tempAvg: row.temp_avg
    }));
  }

  insertMinuteStats(
    intervalStart: Date, intervalMinutes: number,
    co2Min: number, co2Max: number, co2Avg: number, co2Count: number,
    tempMin: number | null, tempMax: number | null, tempAvg: number | null
  ): void {
    this.db.prepare(`
      INSERT OR REPLACE INTO minute_stats
      (interval_start, interval_minutes, co2_min, co2_max, co2_avg, co2_count,
       temp_min, temp_max, temp_avg)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    `).run(
      formatDate(intervalStart), intervalMinutes,
      co2Min, co2Max, co2Avg, co2Count,
      tempMin, tempMax, tempAvg
    );
  }

  // ==================== Hourly Stats ====================

  getHourlyStats(start: Date, end: Date): HourlyStats[] {
    const rows = this.db.prepare(`
      SELECT * FROM hourly_stats
      WHERE hour_start BETWEEN ? AND ?
      ORDER BY hour_start
    `).all(formatDate(start), formatDate(end)) as any[];

    return rows.map(row => ({
      id: row.id,
      hourStart: parseDate(row.hour_start),
      co2Min: row.co2_min,
      co2Max: row.co2_max,
      co2Avg: row.co2_avg,
      co2Count: row.co2_count,
      tempMin: row.temp_min,
      tempMax: row.temp_max,
      tempAvg: row.temp_avg,
      isWorkday: Boolean(row.is_workday),
      isDaytime: Boolean(row.is_daytime),
      hourOfDay: row.hour_of_day,
      dayOfWeek: row.day_of_week
    }));
  }

  insertHourlyStats(
    hourStart: Date, co2Min: number, co2Max: number, co2Avg: number, co2Count: number,
    tempMin: number | null, tempMax: number | null, tempAvg: number | null
  ): void {
    const hourOfDay = hourStart.getHours();
    const dayOfWeek = hourStart.getDay();
    const isDaytime = hourOfDay >= DAYTIME_START && hourOfDay < DAYTIME_END;
    const isWorkday = dayOfWeek >= 1 && dayOfWeek <= 5 &&
                      hourOfDay >= WORKDAY_START && hourOfDay < WORKDAY_END;

    this.db.prepare(`
      INSERT OR REPLACE INTO hourly_stats
      (hour_start, co2_min, co2_max, co2_avg, co2_count,
       temp_min, temp_max, temp_avg, is_workday, is_daytime,
       hour_of_day, day_of_week)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `).run(
      formatDate(hourStart), co2Min, co2Max, co2Avg, co2Count,
      tempMin, tempMax, tempAvg, isWorkday ? 1 : 0, isDaytime ? 1 : 0,
      hourOfDay, dayOfWeek
    );
  }

  // ==================== Daily Stats ====================

  getDailyStats(startDate: string, endDate: string): DailyStats[] {
    const rows = this.db.prepare(`
      SELECT * FROM daily_stats
      WHERE date BETWEEN ? AND ?
      ORDER BY date
    `).all(startDate, endDate) as any[];

    return rows.map(row => ({
      id: row.id,
      date: row.date,
      co2Min: row.co2_min,
      co2Max: row.co2_max,
      co2Avg: row.co2_avg,
      co2DayAvg: row.co2_day_avg,
      co2NightAvg: row.co2_night_avg,
      tempMin: row.temp_min,
      tempMax: row.temp_max,
      tempAvg: row.temp_avg,
      measurementCount: row.measurement_count,
      isWeekend: Boolean(row.is_weekend)
    }));
  }

  insertDailyStats(
    date: string, co2Min: number, co2Max: number, co2Avg: number,
    co2DayAvg: number | null, co2NightAvg: number | null,
    tempMin: number | null, tempMax: number | null, tempAvg: number | null,
    measurementCount: number
  ): void {
    const dateObj = new Date(date);
    const isWeekend = dateObj.getDay() === 0 || dateObj.getDay() === 6;

    this.db.prepare(`
      INSERT OR REPLACE INTO daily_stats
      (date, co2_min, co2_max, co2_avg, co2_day_avg, co2_night_avg,
       temp_min, temp_max, temp_avg, measurement_count, is_weekend)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `).run(
      date, co2Min, co2Max, co2Avg, co2DayAvg, co2NightAvg,
      tempMin, tempMax, tempAvg, measurementCount, isWeekend ? 1 : 0
    );
  }

  // ==================== Analytics Queries ====================

  getHourlyPattern(): HourlyPattern[] {
    const rows = this.db.prepare(`
      SELECT
        hour_of_day,
        AVG(co2_avg) as co2_avg,
        AVG(temp_avg) as temp_avg,
        SUM(co2_count) as sample_count
      FROM hourly_stats
      GROUP BY hour_of_day
      ORDER BY hour_of_day
    `).all() as any[];

    return rows.map(row => ({
      hour: row.hour_of_day,
      co2Avg: row.co2_avg ? Math.round(row.co2_avg * 10) / 10 : null,
      tempAvg: row.temp_avg ? Math.round(row.temp_avg * 10) / 10 : null,
      sampleCount: row.sample_count
    }));
  }

  getWeeklyPattern(): WeeklyPattern[] {
    const dayNames = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
    const rows = this.db.prepare(`
      SELECT
        day_of_week,
        AVG(co2_avg) as co2_avg,
        AVG(temp_avg) as temp_avg,
        SUM(co2_count) as sample_count
      FROM hourly_stats
      GROUP BY day_of_week
      ORDER BY day_of_week
    `).all() as any[];

    return rows.map(row => ({
      day: dayNames[row.day_of_week],
      dayNum: row.day_of_week,
      co2Avg: row.co2_avg ? Math.round(row.co2_avg * 10) / 10 : null,
      tempAvg: row.temp_avg ? Math.round(row.temp_avg * 10) / 10 : null,
      sampleCount: row.sample_count
    }));
  }

  getDayNightComparison(): DayNightComparison {
    const dayRow = this.db.prepare(`
      SELECT
        AVG(co2_avg) as co2_avg,
        AVG(temp_avg) as temp_avg,
        SUM(co2_count) as sample_count
      FROM hourly_stats
      WHERE is_daytime = 1
    `).get() as any;

    const nightRow = this.db.prepare(`
      SELECT
        AVG(co2_avg) as co2_avg,
        AVG(temp_avg) as temp_avg,
        SUM(co2_count) as sample_count
      FROM hourly_stats
      WHERE is_daytime = 0
    `).get() as any;

    return {
      day: {
        co2Avg: dayRow?.co2_avg ? Math.round(dayRow.co2_avg * 10) / 10 : null,
        tempAvg: dayRow?.temp_avg ? Math.round(dayRow.temp_avg * 10) / 10 : null,
        sampleCount: dayRow?.sample_count || 0,
        hours: `${DAYTIME_START.toString().padStart(2, '0')}:00 - ${DAYTIME_END.toString().padStart(2, '0')}:00`
      },
      night: {
        co2Avg: nightRow?.co2_avg ? Math.round(nightRow.co2_avg * 10) / 10 : null,
        tempAvg: nightRow?.temp_avg ? Math.round(nightRow.temp_avg * 10) / 10 : null,
        sampleCount: nightRow?.sample_count || 0,
        hours: `${DAYTIME_END.toString().padStart(2, '0')}:00 - ${DAYTIME_START.toString().padStart(2, '0')}:00`
      }
    };
  }

  getWorkdayWeekendComparison(): WorkWeekendComparison {
    const workdayRow = this.db.prepare(`
      SELECT
        AVG(co2_avg) as co2_avg,
        AVG(temp_avg) as temp_avg,
        SUM(co2_count) as sample_count
      FROM hourly_stats
      WHERE is_workday = 1
    `).get() as any;

    const weekendRow = this.db.prepare(`
      SELECT
        AVG(co2_avg) as co2_avg,
        AVG(temp_avg) as temp_avg,
        SUM(co2_count) as sample_count
      FROM hourly_stats
      WHERE day_of_week IN (0, 6)
    `).get() as any;

    return {
      workday: {
        co2Avg: workdayRow?.co2_avg ? Math.round(workdayRow.co2_avg * 10) / 10 : null,
        tempAvg: workdayRow?.temp_avg ? Math.round(workdayRow.temp_avg * 10) / 10 : null,
        sampleCount: workdayRow?.sample_count || 0,
        description: `Mon-Fri ${WORKDAY_START.toString().padStart(2, '0')}:00-${WORKDAY_END.toString().padStart(2, '0')}:00`
      },
      weekend: {
        co2Avg: weekendRow?.co2_avg ? Math.round(weekendRow.co2_avg * 10) / 10 : null,
        tempAvg: weekendRow?.temp_avg ? Math.round(weekendRow.temp_avg * 10) / 10 : null,
        sampleCount: weekendRow?.sample_count || 0,
        description: 'Sat-Sun all day'
      }
    };
  }

  close(): void {
    this.db.close();
  }
}
