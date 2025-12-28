export interface Reading {
  co2_ppm: number | null;
  temperature_celsius: number | null;
  timestamp: string | null;
}

export interface HistoryEntry {
  timestamp: string;
  co2_ppm: number;
  temperature_celsius: number;
}

export interface HourlyEntry {
  timestamp: string;
  co2_min: number;
  co2_max: number;
  co2_avg: number;
  temp_avg: number;
  count: number;
}

export interface MinuteEntry {
  timestamp: string;
  co2_min: number;
  co2_max: number;
  co2_avg: number;
  temp_avg: number;
  count: number;
}

export interface DailyEntry {
  date: string;
  co2_min: number;
  co2_max: number;
  co2_avg: number;
  co2_day_avg: number | null;
  co2_night_avg: number | null;
  temp_avg: number;
  count: number;
  is_weekend: boolean;
}

export type Resolution = 'raw' | '5min' | '10min' | '15min' | 'hourly' | 'daily' | 'auto';

export interface HistoryResponse {
  resolution: 'raw' | '5min' | '10min' | '15min' | 'hourly' | 'daily';
  data: HistoryEntry[] | MinuteEntry[] | HourlyEntry[] | DailyEntry[];
}

export interface Statistics {
  count: number;
  co2: {
    min: number | null;
    max: number | null;
    avg: number | null;
  };
  temperature: {
    min: number | null;
    max: number | null;
    avg: number | null;
  };
}

export interface DeviceInfo {
  connected: boolean;
  devices: {
    product: string;
    vendor_id: string;
    product_id: string;
  }[];
}

export interface HourlyPattern {
  hour: number;
  co2_avg: number | null;
  temp_avg: number | null;
  sample_count: number;
}

export interface WeeklyPattern {
  day: string;
  day_num: number;
  co2_avg: number | null;
  temp_avg: number | null;
  sample_count: number;
}

export interface DayNightComparison {
  day: {
    co2_avg: number | null;
    temp_avg: number | null;
    sample_count: number;
    hours: string;
  };
  night: {
    co2_avg: number | null;
    temp_avg: number | null;
    sample_count: number;
    hours: string;
  };
}

export interface WorkWeekendComparison {
  workday: {
    co2_avg: number | null;
    temp_avg: number | null;
    sample_count: number;
    description: string;
  };
  weekend: {
    co2_avg: number | null;
    temp_avg: number | null;
    sample_count: number;
    description: string;
  };
}

export interface Summary {
  last_24h: Statistics;
  last_7d: Statistics;
  last_30d: Statistics;
  patterns: {
    day_night: DayNightComparison;
    work_weekend: WorkWeekendComparison;
  };
  total_measurements: number;
}

export type TimeRange = '24h' | '7d' | '30d' | '90d' | '1y' | 'all';
