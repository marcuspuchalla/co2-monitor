# CO2 Monitor

A real-time CO2 monitoring solution for the TFA Dostmann AirControl Mini CO2 Meter (TFA 31.5006). Features a web dashboard with historical data, pattern analysis, and multi-resolution aggregation.

## Features

- **Real-time Monitoring**: Live CO2 and temperature readings via WebSocket
- **Historical Data**: Track CO2 levels over time with configurable time ranges
- **Multi-Resolution Aggregation**: View data at raw, 5-min, 10-min, 15-min, hourly, or daily resolution
- **CO2 Alarms**: System notifications when CO2 exceeds threshold (macOS/Linux)
  - Configurable threshold and cooldown period
  - Native OS notifications
- **Pattern Analysis**:
  - Hourly patterns (average by hour of day)
  - Weekly patterns (average by day of week)
  - Day vs Night comparison
  - Workday vs Weekend comparison
- **Web Dashboard**: Modern Vue.js dashboard with Tailwind CSS
- **Background Service**: Run as a daemon with automatic health monitoring

## Hardware Requirements

- TFA Dostmann AirControl Mini CO2 Meter (TFA 31.5006)
  - Vendor ID: 0x04D9
  - Product ID: 0xA052

## Screenshots

![Dashboard Overview](screenshots/dashboard.png)
*Main dashboard showing current CO2 level, temperature, and historical chart*

![Pattern Analysis](screenshots/patterns.png)
*Pattern analysis showing hourly, weekly, day/night, and work/weekend patterns*

The dashboard displays:
- Current CO2 level with color-coded status (Good/OK/Poor/Bad)
- Current temperature
- Historical chart with adjustable time range and resolution
- Pattern analysis cards
- Device connection status

## Installation

### Prerequisites

- Python 3.10+
- Node.js 20.19+ or 22.12+
- USB HID access (may require permissions on Linux)

### Setup

1. Clone the repository:
```bash
git clone https://github.com/YOUR_USERNAME/co2-monitor.git
cd co2-monitor
```

2. Create and activate virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install Python dependencies:
```bash
pip install -r requirements.txt
```

4. Build the frontend:
```bash
cd frontend
npm install
npm run build
cd ..
```

5. Run the server:
```bash
python api_server.py
```

6. Open http://localhost:8080 in your browser.

## Usage

### Running the Server

```bash
# Start the API server (includes sensor reading and aggregation)
python api_server.py

# Or use the service script
./co2-monitor.sh start
./co2-monitor.sh status
./co2-monitor.sh stop
```

### Service Management

The `co2-monitor.sh` script provides service management:

```bash
./co2-monitor.sh start    # Start the service
./co2-monitor.sh stop     # Stop the service
./co2-monitor.sh restart  # Restart the service
./co2-monitor.sh status   # Check status and current reading
./co2-monitor.sh logs     # Follow the log file
./co2-monitor.sh health   # Check health endpoint
```

### CO2 Alarm Configuration

Configure high CO2 notifications directly in the web interface:

1. Click the "Alarm" button in the top-right corner
2. Enable the alarm toggle
3. Set your CO2 threshold (default: 1000 ppm)
4. Configure cooldown period (default: 30 minutes)

When CO2 exceeds your threshold, you'll receive a system notification. The cooldown prevents repeated notifications.

**Supported platforms:**
- macOS: Native notification center alerts
- Linux: notify-send notifications

Settings are saved in `data/alarm_settings.json` and persist across restarts.

### macOS Auto-Start

To start automatically on login:

```bash
cp com.co2monitor.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.co2monitor.plist
```

### Data Aggregation

The system automatically aggregates data at multiple resolutions:
- **5-minute intervals**: For detailed short-term analysis
- **10-minute intervals**: Medium granularity
- **15-minute intervals**: Good balance of detail and storage
- **Hourly**: For multi-day views
- **Daily**: For long-term trends

To manually run aggregation:

```bash
# Run incremental aggregation
python aggregator.py

# Backfill all historical data
python aggregator.py --backfill

# Run as daemon (periodic aggregation)
python aggregator.py --daemon
```

### Data Retention

- Raw measurements: 30 days (configurable)
- Aggregated data: Kept indefinitely
- Maximum database size: 5GB (configurable)

## API Endpoints

### Core Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/current` | Current CO2/temperature reading |
| `GET /api/device` | Device information |
| `GET /api/health` | Health check |
| `WS /ws` | WebSocket for real-time updates |

### History Endpoints

| Endpoint | Parameters | Description |
|----------|------------|-------------|
| `GET /api/history` | `hours`, `days`, `resolution` | Historical readings |
| `GET /api/statistics` | `hours` | Statistics for time period |
| `GET /api/stats/summary` | - | Multi-period summary |

Resolution options: `raw`, `5min`, `10min`, `15min`, `hourly`, `daily`, `auto`

### Pattern Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/patterns/hourly` | Average by hour of day (0-23) |
| `GET /api/patterns/weekly` | Average by day of week |
| `GET /api/patterns/day-night` | Day vs night comparison |
| `GET /api/patterns/work-weekend` | Workday vs weekend comparison |

## Configuration

### Time Definitions

- **Daytime**: 06:00 - 22:00
- **Nighttime**: 22:00 - 06:00
- **Workday hours**: Mon-Fri 08:00 - 18:00

### Database

SQLite database stored at `data/co2_data.db` with schema versioning (current: v3).

Tables:
- `measurements`: Raw sensor readings
- `minute_stats`: 5/10/15-minute aggregations
- `hourly_stats`: Hourly aggregations with workday/daytime flags
- `daily_stats`: Daily aggregations with day/night averages
- `metadata`: Schema version tracking

## Project Structure

```
co2-monitor/
├── api_server.py        # FastAPI server with WebSocket support (Python)
├── co2_reader.py        # USB HID communication with sensor (Python)
├── database.py          # SQLite database operations (Python)
├── aggregator.py        # Data aggregation service (Python)
├── tracker.py           # CLI tool for testing
├── health_monitor.py    # Health check utility
├── co2-monitor.sh       # Service management script
├── com.co2monitor.plist # macOS LaunchAgent
├── requirements.txt     # Python dependencies
├── server/              # TypeScript backend (alternative)
│   ├── src/
│   │   ├── index.ts     # API server with WebSocket
│   │   ├── co2Reader.ts # USB HID communication
│   │   └── database.ts  # SQLite operations
│   ├── dist/            # Compiled JavaScript
│   ├── package.json
│   └── tsconfig.json
├── frontend/            # Vue.js frontend
│   ├── src/
│   │   ├── App.vue
│   │   ├── components/
│   │   │   └── CO2Chart.vue
│   │   ├── composables/
│   │   │   └── useCO2Data.ts
│   │   └── types.ts
│   └── dist/            # Built frontend
├── screenshots/         # Dashboard screenshots
└── data/
    └── co2_data.db      # SQLite database
```

## Development

### Frontend Development

```bash
cd frontend
npm run dev  # Start dev server with hot reload
```

The dev server proxies API requests to `http://localhost:8080`.

### TypeScript Backend (Alternative)

An alternative TypeScript/Node.js backend is available with minimal dependencies:

```bash
cd server
npm install
npm run build
npm start
```

For development with hot reload:
```bash
npm run dev
```

The TypeScript backend provides the same API and WebSocket endpoints as the Python version.

### Running Tests

```bash
# Test sensor connection
python co2_reader.py

# Test database
python database.py

# Health check
python health_monitor.py --json
```

## Troubleshooting

### Device Not Found

- Ensure the CO2 meter is connected via USB
- Check USB permissions (Linux may require udev rules)
- Run `python co2_reader.py` to test connection

### Port Already in Use

```bash
lsof -ti:8080 | xargs kill -9
```

### Database Issues

```bash
# Rebuild all aggregations
python aggregator.py --backfill
```

## License

MIT License

## Acknowledgments

- Based on USB HID protocol research from [JsBergbau/TFACO2AirCO2ntrol_CO2Meter](https://github.com/JsBergbau/TFACO2AirCO2ntrol_CO2Meter)
- TFA Dostmann for the AirControl Mini CO2 meter
