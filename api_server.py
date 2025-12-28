#!/usr/bin/env python3
"""
API Server for CO2 Monitor Dashboard

Provides REST API endpoints for CO2 data and real-time readings.
"""

import asyncio
import json
import threading
import time
from datetime import datetime, timedelta, date
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import uvicorn

from database import CO2Database
from co2_reader import CO2Reader, list_devices
from aggregator import Aggregator


# Global state
db = CO2Database()
reader = CO2Reader()
aggregator = Aggregator()
current_reading = {"co2_ppm": None, "temperature_celsius": None, "timestamp": None}
websocket_clients: list[WebSocket] = []
reader_thread = None
aggregator_thread = None
stop_reader = threading.Event()
stop_aggregator = threading.Event()


def reading_loop():
    """Background thread that continuously reads from CO2 sensor."""
    global current_reading

    if not reader.connect():
        print("Failed to connect to CO2 sensor")
        return

    print("CO2 reader connected")

    while not stop_reader.is_set():
        try:
            reading = reader.read(timeout_seconds=5)
            if reading.co2_ppm is not None:
                current_reading = {
                    "co2_ppm": reading.co2_ppm,
                    "temperature_celsius": reading.temperature_celsius,
                    "timestamp": datetime.now().isoformat()
                }
                # Store in database
                db.insert(reading.co2_ppm, reading.temperature_celsius)
        except Exception as e:
            print(f"Reading error: {e}")

        # Wait before next reading
        for _ in range(50):  # 5 seconds in 0.1s increments
            if stop_reader.is_set():
                break
            time.sleep(0.1)

    reader.disconnect()
    print("CO2 reader disconnected")


def aggregation_loop():
    """Background thread that periodically aggregates data."""
    print("Aggregator started")

    while not stop_aggregator.is_set():
        try:
            aggregator.run_incremental()
        except Exception as e:
            print(f"Aggregation error: {e}")

        # Run every 5 minutes
        for _ in range(300):  # 5 minutes in 1s increments
            if stop_aggregator.is_set():
                break
            time.sleep(1)

    print("Aggregator stopped")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    global reader_thread, aggregator_thread

    # Start reader thread
    stop_reader.clear()
    reader_thread = threading.Thread(target=reading_loop, daemon=True)
    reader_thread.start()

    # Start aggregator thread
    stop_aggregator.clear()
    aggregator_thread = threading.Thread(target=aggregation_loop, daemon=True)
    aggregator_thread.start()

    # Start WebSocket broadcaster
    asyncio.create_task(broadcast_readings())

    yield

    # Shutdown
    stop_reader.set()
    stop_aggregator.set()
    if reader_thread:
        reader_thread.join(timeout=2)
    if aggregator_thread:
        aggregator_thread.join(timeout=2)


app = FastAPI(title="CO2 Monitor API", lifespan=lifespan)

# CORS for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def broadcast_readings():
    """Broadcast current readings to all WebSocket clients."""
    while True:
        if websocket_clients and current_reading["co2_ppm"] is not None:
            message = json.dumps(current_reading)
            disconnected = []
            for ws in websocket_clients:
                try:
                    await ws.send_text(message)
                except Exception:
                    disconnected.append(ws)
            for ws in disconnected:
                websocket_clients.remove(ws)
        await asyncio.sleep(2)


# ==================== Core Endpoints ====================

@app.get("/api/current")
async def get_current():
    """Get current CO2 reading."""
    return current_reading


@app.get("/api/device")
async def get_device():
    """Get device information."""
    devices = list_devices()
    return {
        "connected": len(devices) > 0,
        "devices": [
            {
                "product": d.get("product_string", "Unknown"),
                "vendor_id": f"0x{d['vendor_id']:04X}",
                "product_id": f"0x{d['product_id']:04X}"
            }
            for d in devices
        ]
    }


@app.get("/api/statistics")
async def get_statistics(hours: int = 24):
    """Get statistics for the given time period."""
    return db.get_statistics(hours)


# ==================== History Endpoints ====================

@app.get("/api/history")
async def get_history(
    resolution: str = Query("auto", pattern="^(raw|5min|10min|15min|hourly|daily|auto)$"),
    hours: Optional[int] = None,
    days: Optional[int] = None,
    start: Optional[str] = None,
    end: Optional[str] = None
):
    """
    Get historical readings with configurable resolution.

    - resolution: raw, 5min, 10min, 15min, hourly, daily, or auto
    - hours: Get last N hours (shorthand)
    - days: Get last N days (shorthand)
    - start/end: ISO datetime strings for custom range
    """
    # Determine time range
    if start and end:
        start_dt = datetime.fromisoformat(start)
        end_dt = datetime.fromisoformat(end)
    elif days:
        end_dt = datetime.now()
        start_dt = end_dt - timedelta(days=days)
    elif hours:
        end_dt = datetime.now()
        start_dt = end_dt - timedelta(hours=hours)
    else:
        # Default: last 24 hours
        end_dt = datetime.now()
        start_dt = end_dt - timedelta(hours=24)

    # Auto-select resolution based on time range
    if resolution == "auto":
        range_hours = (end_dt - start_dt).total_seconds() / 3600
        if range_hours <= 6:
            resolution = "raw"
        elif range_hours <= 24:
            resolution = "5min"
        elif range_hours <= 48:
            resolution = "15min"
        elif range_hours <= 24 * 7:
            resolution = "hourly"
        else:
            resolution = "daily"

    # Fetch data based on resolution
    if resolution == "raw":
        measurements = db.get_range(start_dt, end_dt)
        return {
            "resolution": "raw",
            "data": [
                {
                    "timestamp": m.timestamp.isoformat(),
                    "co2_ppm": m.co2_ppm,
                    "temperature_celsius": m.temperature_celsius
                }
                for m in measurements
            ]
        }
    elif resolution in ("5min", "10min", "15min"):
        interval = int(resolution.replace("min", ""))
        stats = db.get_minute_stats(start_dt, end_dt, interval)
        return {
            "resolution": resolution,
            "data": [
                {
                    "timestamp": s.interval_start.isoformat(),
                    "co2_min": s.co2_min,
                    "co2_max": s.co2_max,
                    "co2_avg": s.co2_avg,
                    "temp_avg": s.temp_avg,
                    "count": s.co2_count
                }
                for s in stats
            ]
        }
    elif resolution == "hourly":
        stats = db.get_hourly_stats(start_dt, end_dt)
        return {
            "resolution": "hourly",
            "data": [
                {
                    "timestamp": s.hour_start.isoformat(),
                    "co2_min": s.co2_min,
                    "co2_max": s.co2_max,
                    "co2_avg": s.co2_avg,
                    "temp_avg": s.temp_avg,
                    "count": s.co2_count
                }
                for s in stats
            ]
        }
    else:  # daily
        stats = db.get_daily_stats(start_dt.date(), end_dt.date())
        return {
            "resolution": "daily",
            "data": [
                {
                    "date": s.date.isoformat(),
                    "co2_min": s.co2_min,
                    "co2_max": s.co2_max,
                    "co2_avg": s.co2_avg,
                    "co2_day_avg": s.co2_day_avg,
                    "co2_night_avg": s.co2_night_avg,
                    "temp_avg": s.temp_avg,
                    "count": s.measurement_count,
                    "is_weekend": s.is_weekend
                }
                for s in stats
            ]
        }


# ==================== Pattern Endpoints ====================

@app.get("/api/patterns/hourly")
async def get_hourly_pattern():
    """Get average CO2/temperature by hour of day (0-23)."""
    return db.get_hourly_pattern()


@app.get("/api/patterns/weekly")
async def get_weekly_pattern():
    """Get average CO2/temperature by day of week."""
    return db.get_weekly_pattern()


@app.get("/api/patterns/day-night")
async def get_day_night():
    """Get day vs night comparison."""
    return db.get_day_night_comparison()


@app.get("/api/patterns/work-weekend")
async def get_work_weekend():
    """Get workday vs weekend comparison."""
    return db.get_workday_weekend_comparison()


# ==================== Stats Endpoints ====================

@app.get("/api/stats/range")
async def get_stats_range(
    start: str = Query(..., description="Start datetime (ISO format)"),
    end: str = Query(..., description="End datetime (ISO format)")
):
    """Get comprehensive statistics for a date range."""
    start_dt = datetime.fromisoformat(start)
    end_dt = datetime.fromisoformat(end)
    return db.get_stats_for_range(start_dt, end_dt)


@app.get("/api/stats/summary")
async def get_summary():
    """Get overall summary with multiple time ranges."""
    now = datetime.now()
    return {
        "last_24h": db.get_statistics(24),
        "last_7d": db.get_statistics(24 * 7),
        "last_30d": db.get_statistics(24 * 30),
        "patterns": {
            "day_night": db.get_day_night_comparison(),
            "work_weekend": db.get_workday_weekend_comparison()
        },
        "total_measurements": db.count()
    }


# ==================== Health Endpoint ====================

@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    devices = list_devices()
    return {
        "status": "healthy",
        "device_connected": len(devices) > 0,
        "database_measurements": db.count(),
        "current_reading": current_reading,
        "timestamp": datetime.now().isoformat()
    }


# ==================== WebSocket ====================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates."""
    await websocket.accept()
    websocket_clients.append(websocket)
    try:
        # Send current reading immediately
        if current_reading["co2_ppm"] is not None:
            await websocket.send_text(json.dumps(current_reading))
        # Keep connection alive
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        if websocket in websocket_clients:
            websocket_clients.remove(websocket)


# ==================== Static Files ====================

@app.get("/")
async def serve_index():
    """Serve the frontend."""
    return FileResponse("frontend/dist/index.html")


# Mount static files (after API routes)
try:
    app.mount("/assets", StaticFiles(directory="frontend/dist/assets"), name="assets")
except Exception:
    pass  # Frontend not built yet


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
