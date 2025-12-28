/**
 * CO2 Monitor API Server
 *
 * Provides REST API endpoints and WebSocket for real-time CO2 data.
 */

import { createServer, IncomingMessage, ServerResponse } from 'http';
import { readFileSync, existsSync, statSync } from 'fs';
import { join, extname } from 'path';
import { WebSocketServer, WebSocket } from 'ws';
import { CO2Database, Measurement } from './database.js';
import { CO2Reader, listDevices, CO2Reading } from './co2Reader.js';

const PORT = 8080;
const FRONTEND_DIR = join(process.cwd(), '..', 'frontend', 'dist');

// Global state
const db = new CO2Database(join(process.cwd(), '..', 'data', 'co2_data.db'));
const reader = new CO2Reader();
const wsClients: Set<WebSocket> = new Set();

let currentReading: {
  co2_ppm: number | null;
  temperature_celsius: number | null;
  timestamp: string | null;
} = {
  co2_ppm: null,
  temperature_celsius: null,
  timestamp: null
};

let stopReading = false;
let stopAggregator = false;

// ==================== MIME Types ====================

const MIME_TYPES: Record<string, string> = {
  '.html': 'text/html',
  '.js': 'application/javascript',
  '.css': 'text/css',
  '.json': 'application/json',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon',
  '.woff': 'font/woff',
  '.woff2': 'font/woff2'
};

// ==================== Utility Functions ====================

function sendJson(res: ServerResponse, data: unknown, status = 200): void {
  res.writeHead(status, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify(data));
}

function sendError(res: ServerResponse, message: string, status = 400): void {
  sendJson(res, { error: message }, status);
}

function parseQuery(url: string): URLSearchParams {
  const idx = url.indexOf('?');
  return new URLSearchParams(idx >= 0 ? url.slice(idx + 1) : '');
}

function getPath(url: string): string {
  const idx = url.indexOf('?');
  return idx >= 0 ? url.slice(0, idx) : url;
}

function serveStatic(res: ServerResponse, filePath: string): boolean {
  const fullPath = join(FRONTEND_DIR, filePath);
  if (!existsSync(fullPath)) return false;

  const stat = statSync(fullPath);
  if (!stat.isFile()) return false;

  const ext = extname(fullPath);
  const contentType = MIME_TYPES[ext] || 'application/octet-stream';

  res.writeHead(200, { 'Content-Type': contentType });
  res.end(readFileSync(fullPath));
  return true;
}

// ==================== API Handlers ====================

function handleCurrent(res: ServerResponse): void {
  sendJson(res, currentReading);
}

function handleDevice(res: ServerResponse): void {
  const devices = listDevices();
  sendJson(res, {
    connected: devices.length > 0,
    devices: devices.map(d => ({
      product: d.product,
      vendor_id: d.vendorId,
      product_id: d.productId
    }))
  });
}

function handleStatistics(res: ServerResponse, query: URLSearchParams): void {
  const hours = parseInt(query.get('hours') || '24', 10);
  sendJson(res, db.getStatistics(hours));
}

function handleHistory(res: ServerResponse, query: URLSearchParams): void {
  let resolution = query.get('resolution') || 'auto';
  const hours = query.get('hours');
  const days = query.get('days');
  const start = query.get('start');
  const end = query.get('end');

  // Determine time range
  let startDt: Date;
  let endDt: Date;

  if (start && end) {
    startDt = new Date(start);
    endDt = new Date(end);
  } else if (days) {
    endDt = new Date();
    startDt = new Date(endDt.getTime() - parseInt(days, 10) * 24 * 60 * 60 * 1000);
  } else if (hours) {
    endDt = new Date();
    startDt = new Date(endDt.getTime() - parseInt(hours, 10) * 60 * 60 * 1000);
  } else {
    endDt = new Date();
    startDt = new Date(endDt.getTime() - 24 * 60 * 60 * 1000);
  }

  // Auto-select resolution based on time range
  if (resolution === 'auto') {
    const rangeHours = (endDt.getTime() - startDt.getTime()) / (1000 * 60 * 60);
    if (rangeHours <= 6) {
      resolution = 'raw';
    } else if (rangeHours <= 24) {
      resolution = '5min';
    } else if (rangeHours <= 48) {
      resolution = '15min';
    } else if (rangeHours <= 24 * 7) {
      resolution = 'hourly';
    } else {
      resolution = 'daily';
    }
  }

  // Fetch data based on resolution
  if (resolution === 'raw') {
    const measurements = db.getRange(startDt, endDt);
    sendJson(res, {
      resolution: 'raw',
      data: measurements.map(m => ({
        timestamp: m.timestamp.toISOString(),
        co2_ppm: m.co2Ppm,
        temperature_celsius: m.temperatureCelsius
      }))
    });
  } else if (['5min', '10min', '15min'].includes(resolution)) {
    const interval = parseInt(resolution.replace('min', ''), 10);
    const stats = db.getMinuteStats(startDt, endDt, interval);
    sendJson(res, {
      resolution,
      data: stats.map(s => ({
        timestamp: s.intervalStart.toISOString(),
        co2_min: s.co2Min,
        co2_max: s.co2Max,
        co2_avg: s.co2Avg,
        temp_avg: s.tempAvg,
        count: s.co2Count
      }))
    });
  } else if (resolution === 'hourly') {
    const stats = db.getHourlyStats(startDt, endDt);
    sendJson(res, {
      resolution: 'hourly',
      data: stats.map(s => ({
        timestamp: s.hourStart.toISOString(),
        co2_min: s.co2Min,
        co2_max: s.co2Max,
        co2_avg: s.co2Avg,
        temp_avg: s.tempAvg,
        count: s.co2Count
      }))
    });
  } else {
    // daily
    const startDate = startDt.toISOString().slice(0, 10);
    const endDate = endDt.toISOString().slice(0, 10);
    const stats = db.getDailyStats(startDate, endDate);
    sendJson(res, {
      resolution: 'daily',
      data: stats.map(s => ({
        date: s.date,
        co2_min: s.co2Min,
        co2_max: s.co2Max,
        co2_avg: s.co2Avg,
        co2_day_avg: s.co2DayAvg,
        co2_night_avg: s.co2NightAvg,
        temp_avg: s.tempAvg,
        count: s.measurementCount,
        is_weekend: s.isWeekend
      }))
    });
  }
}

function handleHourlyPattern(res: ServerResponse): void {
  sendJson(res, db.getHourlyPattern());
}

function handleWeeklyPattern(res: ServerResponse): void {
  sendJson(res, db.getWeeklyPattern());
}

function handleDayNight(res: ServerResponse): void {
  sendJson(res, db.getDayNightComparison());
}

function handleWorkWeekend(res: ServerResponse): void {
  sendJson(res, db.getWorkdayWeekendComparison());
}

function handleSummary(res: ServerResponse): void {
  sendJson(res, {
    last_24h: db.getStatistics(24),
    last_7d: db.getStatistics(24 * 7),
    last_30d: db.getStatistics(24 * 30),
    patterns: {
      day_night: db.getDayNightComparison(),
      work_weekend: db.getWorkdayWeekendComparison()
    },
    total_measurements: db.count()
  });
}

function handleHealth(res: ServerResponse): void {
  const devices = listDevices();
  sendJson(res, {
    status: 'healthy',
    device_connected: devices.length > 0,
    database_measurements: db.count(),
    current_reading: currentReading,
    timestamp: new Date().toISOString()
  });
}

// ==================== HTTP Server ====================

const server = createServer((req: IncomingMessage, res: ServerResponse) => {
  const url = req.url || '/';
  const path = getPath(url);
  const query = parseQuery(url);

  // CORS headers
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') {
    res.writeHead(204);
    res.end();
    return;
  }

  // API routes
  if (path.startsWith('/api/')) {
    switch (path) {
      case '/api/current':
        return handleCurrent(res);
      case '/api/device':
        return handleDevice(res);
      case '/api/statistics':
        return handleStatistics(res, query);
      case '/api/history':
        return handleHistory(res, query);
      case '/api/patterns/hourly':
        return handleHourlyPattern(res);
      case '/api/patterns/weekly':
        return handleWeeklyPattern(res);
      case '/api/patterns/day-night':
        return handleDayNight(res);
      case '/api/patterns/work-weekend':
        return handleWorkWeekend(res);
      case '/api/stats/summary':
        return handleSummary(res);
      case '/api/health':
        return handleHealth(res);
      default:
        return sendError(res, 'Not found', 404);
    }
  }

  // Static files
  if (path.startsWith('/assets/')) {
    if (serveStatic(res, path)) return;
  }

  // Serve index.html for root and SPA routes
  if (path === '/' || !path.includes('.')) {
    if (serveStatic(res, 'index.html')) return;
  }

  // Fallback: try to serve exact path
  if (serveStatic(res, path)) return;

  sendError(res, 'Not found', 404);
});

// ==================== WebSocket Server ====================

const wss = new WebSocketServer({ server });

wss.on('connection', (ws: WebSocket) => {
  wsClients.add(ws);
  console.log('WebSocket client connected');

  // Send current reading immediately
  if (currentReading.co2_ppm !== null) {
    ws.send(JSON.stringify(currentReading));
  }

  ws.on('close', () => {
    wsClients.delete(ws);
    console.log('WebSocket client disconnected');
  });

  ws.on('error', (err) => {
    console.error('WebSocket error:', err);
    wsClients.delete(ws);
  });
});

function broadcastReading(): void {
  if (wsClients.size === 0 || currentReading.co2_ppm === null) return;

  const message = JSON.stringify(currentReading);
  for (const ws of wsClients) {
    if (ws.readyState === WebSocket.OPEN) {
      ws.send(message);
    }
  }
}

// ==================== CO2 Reader Loop ====================

async function readerLoop(): Promise<void> {
  if (!reader.connect()) {
    console.error('Failed to connect to CO2 sensor');
    return;
  }

  console.log('CO2 reader connected');

  while (!stopReading) {
    try {
      const reading = reader.read(5000);
      if (reading.co2Ppm !== null) {
        currentReading = {
          co2_ppm: reading.co2Ppm,
          temperature_celsius: reading.temperatureCelsius,
          timestamp: new Date().toISOString()
        };

        // Store in database
        db.insert(reading.co2Ppm, reading.temperatureCelsius);

        // Broadcast to WebSocket clients
        broadcastReading();
      }
    } catch (error) {
      console.error('Reading error:', error);
    }

    // Wait 5 seconds before next reading
    await new Promise(resolve => setTimeout(resolve, 5000));
  }

  reader.disconnect();
  console.log('CO2 reader disconnected');
}

// ==================== Aggregator Loop ====================

async function aggregatorLoop(): Promise<void> {
  console.log('Aggregator started');

  while (!stopAggregator) {
    try {
      runAggregation();
    } catch (error) {
      console.error('Aggregation error:', error);
    }

    // Run every 5 minutes
    await new Promise(resolve => setTimeout(resolve, 5 * 60 * 1000));
  }

  console.log('Aggregator stopped');
}

function runAggregation(): void {
  const now = new Date();

  // Aggregate minute stats for 5min, 10min, 15min intervals
  for (const interval of [5, 10, 15]) {
    aggregateMinuteStats(interval, now);
  }

  // Aggregate hourly stats
  aggregateHourlyStats(now);

  // Aggregate daily stats
  aggregateDailyStats(now);

  // Cleanup old data
  db.cleanupIfSizeExceeded(5.0, 30);
}

function aggregateMinuteStats(intervalMinutes: number, now: Date): void {
  // Get the last 2 hours of raw data for aggregation
  const start = new Date(now.getTime() - 2 * 60 * 60 * 1000);
  const measurements = db.getRange(start, now);

  if (measurements.length === 0) return;

  // Group by interval
  const groups = new Map<string, Measurement[]>();

  for (const m of measurements) {
    const intervalStart = new Date(
      Math.floor(m.timestamp.getTime() / (intervalMinutes * 60 * 1000)) * intervalMinutes * 60 * 1000
    );
    const key = intervalStart.toISOString();
    if (!groups.has(key)) {
      groups.set(key, []);
    }
    groups.get(key)!.push(m);
  }

  // Insert aggregated stats
  for (const [key, ms] of groups) {
    if (ms.length === 0) continue;

    const co2Values = ms.map(m => m.co2Ppm);
    const tempValues = ms.filter(m => m.temperatureCelsius !== null).map(m => m.temperatureCelsius!);

    const co2Min = Math.min(...co2Values);
    const co2Max = Math.max(...co2Values);
    const co2Avg = Math.round(co2Values.reduce((a, b) => a + b, 0) / co2Values.length * 10) / 10;

    const tempMin = tempValues.length > 0 ? Math.min(...tempValues) : null;
    const tempMax = tempValues.length > 0 ? Math.max(...tempValues) : null;
    const tempAvg = tempValues.length > 0
      ? Math.round(tempValues.reduce((a, b) => a + b, 0) / tempValues.length * 10) / 10
      : null;

    db.insertMinuteStats(
      new Date(key), intervalMinutes,
      co2Min, co2Max, co2Avg, ms.length,
      tempMin, tempMax, tempAvg
    );
  }
}

function aggregateHourlyStats(now: Date): void {
  // Get the last 3 hours of raw data
  const start = new Date(now.getTime() - 3 * 60 * 60 * 1000);
  const measurements = db.getRange(start, now);

  if (measurements.length === 0) return;

  // Group by hour
  const groups = new Map<string, Measurement[]>();

  for (const m of measurements) {
    const hourStart = new Date(m.timestamp);
    hourStart.setMinutes(0, 0, 0);
    const key = hourStart.toISOString();
    if (!groups.has(key)) {
      groups.set(key, []);
    }
    groups.get(key)!.push(m);
  }

  // Insert aggregated stats
  for (const [key, ms] of groups) {
    if (ms.length === 0) continue;

    const co2Values = ms.map(m => m.co2Ppm);
    const tempValues = ms.filter(m => m.temperatureCelsius !== null).map(m => m.temperatureCelsius!);

    const co2Min = Math.min(...co2Values);
    const co2Max = Math.max(...co2Values);
    const co2Avg = Math.round(co2Values.reduce((a, b) => a + b, 0) / co2Values.length * 10) / 10;

    const tempMin = tempValues.length > 0 ? Math.min(...tempValues) : null;
    const tempMax = tempValues.length > 0 ? Math.max(...tempValues) : null;
    const tempAvg = tempValues.length > 0
      ? Math.round(tempValues.reduce((a, b) => a + b, 0) / tempValues.length * 10) / 10
      : null;

    db.insertHourlyStats(
      new Date(key),
      co2Min, co2Max, co2Avg, ms.length,
      tempMin, tempMax, tempAvg
    );
  }
}

function aggregateDailyStats(now: Date): void {
  // Get yesterday's data
  const yesterday = new Date(now);
  yesterday.setDate(yesterday.getDate() - 1);
  const startOfYesterday = new Date(yesterday.toISOString().slice(0, 10));
  const endOfYesterday = new Date(startOfYesterday.getTime() + 24 * 60 * 60 * 1000 - 1);

  const measurements = db.getRange(startOfYesterday, endOfYesterday);

  if (measurements.length === 0) return;

  const co2Values = measurements.map(m => m.co2Ppm);
  const tempValues = measurements.filter(m => m.temperatureCelsius !== null).map(m => m.temperatureCelsius!);

  // Day measurements (6:00 - 22:00)
  const dayMeasurements = measurements.filter(m => {
    const hour = m.timestamp.getHours();
    return hour >= 6 && hour < 22;
  });

  // Night measurements
  const nightMeasurements = measurements.filter(m => {
    const hour = m.timestamp.getHours();
    return hour < 6 || hour >= 22;
  });

  const co2Min = Math.min(...co2Values);
  const co2Max = Math.max(...co2Values);
  const co2Avg = Math.round(co2Values.reduce((a, b) => a + b, 0) / co2Values.length * 10) / 10;

  const co2DayAvg = dayMeasurements.length > 0
    ? Math.round(dayMeasurements.map(m => m.co2Ppm).reduce((a, b) => a + b, 0) / dayMeasurements.length * 10) / 10
    : null;

  const co2NightAvg = nightMeasurements.length > 0
    ? Math.round(nightMeasurements.map(m => m.co2Ppm).reduce((a, b) => a + b, 0) / nightMeasurements.length * 10) / 10
    : null;

  const tempMin = tempValues.length > 0 ? Math.min(...tempValues) : null;
  const tempMax = tempValues.length > 0 ? Math.max(...tempValues) : null;
  const tempAvg = tempValues.length > 0
    ? Math.round(tempValues.reduce((a, b) => a + b, 0) / tempValues.length * 10) / 10
    : null;

  const dateStr = startOfYesterday.toISOString().slice(0, 10);

  db.insertDailyStats(
    dateStr, co2Min, co2Max, co2Avg,
    co2DayAvg, co2NightAvg,
    tempMin, tempMax, tempAvg,
    measurements.length
  );
}

// ==================== Startup ====================

console.log(`Starting CO2 Monitor server on port ${PORT}...`);

server.listen(PORT, () => {
  console.log(`Server running at http://localhost:${PORT}`);

  // Start background tasks
  readerLoop().catch(console.error);
  aggregatorLoop().catch(console.error);
});

// Graceful shutdown
process.on('SIGINT', () => {
  console.log('\nShutting down...');
  stopReading = true;
  stopAggregator = true;

  wss.close();
  server.close();
  db.close();

  process.exit(0);
});

process.on('SIGTERM', () => {
  console.log('Received SIGTERM, shutting down...');
  stopReading = true;
  stopAggregator = true;

  wss.close();
  server.close();
  db.close();

  process.exit(0);
});
