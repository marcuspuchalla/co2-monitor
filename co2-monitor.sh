#!/bin/bash
#
# CO2 Monitor Service Script
# Starts the CO2 monitor API server with automatic restart on failure.
#

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Configuration
VENV_PATH="$SCRIPT_DIR/venv"
LOG_DIR="$SCRIPT_DIR/logs"
PID_FILE="$SCRIPT_DIR/co2-monitor.pid"
LOG_FILE="$LOG_DIR/co2-monitor.log"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Create log directory
mkdir -p "$LOG_DIR"

log() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1" >&2
}

warn() {
    echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] WARNING:${NC} $1"
}

check_venv() {
    if [ ! -d "$VENV_PATH" ]; then
        error "Virtual environment not found at $VENV_PATH"
        error "Run: python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
        exit 1
    fi
}

start() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if kill -0 "$PID" 2>/dev/null; then
            warn "CO2 Monitor is already running (PID: $PID)"
            return 0
        else
            rm -f "$PID_FILE"
        fi
    fi

    check_venv
    log "Starting CO2 Monitor..."

    # Activate virtual environment and start server
    source "$VENV_PATH/bin/activate"

    nohup python api_server.py >> "$LOG_FILE" 2>&1 &
    PID=$!
    echo $PID > "$PID_FILE"

    sleep 2

    if kill -0 "$PID" 2>/dev/null; then
        log "CO2 Monitor started (PID: $PID)"
        log "Logs: $LOG_FILE"
        log "Web UI: http://localhost:8080"
    else
        error "Failed to start CO2 Monitor"
        rm -f "$PID_FILE"
        exit 1
    fi
}

stop() {
    if [ ! -f "$PID_FILE" ]; then
        warn "CO2 Monitor is not running (no PID file)"
        return 0
    fi

    PID=$(cat "$PID_FILE")

    if kill -0 "$PID" 2>/dev/null; then
        log "Stopping CO2 Monitor (PID: $PID)..."
        kill "$PID"

        # Wait for graceful shutdown
        for i in {1..10}; do
            if ! kill -0 "$PID" 2>/dev/null; then
                break
            fi
            sleep 1
        done

        # Force kill if still running
        if kill -0 "$PID" 2>/dev/null; then
            warn "Force killing CO2 Monitor..."
            kill -9 "$PID"
        fi

        log "CO2 Monitor stopped"
    else
        warn "CO2 Monitor process not found (stale PID file)"
    fi

    rm -f "$PID_FILE"
}

restart() {
    log "Restarting CO2 Monitor..."
    stop
    sleep 2
    start
}

status() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if kill -0 "$PID" 2>/dev/null; then
            log "CO2 Monitor is running (PID: $PID)"

            # Check health endpoint
            if command -v curl &> /dev/null; then
                HEALTH=$(curl -s http://localhost:8080/api/health 2>/dev/null || echo "")
                if [ -n "$HEALTH" ]; then
                    echo "$HEALTH" | python3 -m json.tool 2>/dev/null || echo "$HEALTH"
                fi
            fi
            return 0
        else
            warn "CO2 Monitor is not running (stale PID file)"
            return 1
        fi
    else
        warn "CO2 Monitor is not running"
        return 1
    fi
}

logs() {
    if [ -f "$LOG_FILE" ]; then
        tail -f "$LOG_FILE"
    else
        error "Log file not found: $LOG_FILE"
        exit 1
    fi
}

health() {
    if command -v curl &> /dev/null; then
        RESPONSE=$(curl -s -w "\n%{http_code}" http://localhost:8080/api/health 2>/dev/null)
        HTTP_CODE=$(echo "$RESPONSE" | tail -1)
        BODY=$(echo "$RESPONSE" | sed '$d')

        if [ "$HTTP_CODE" = "200" ]; then
            log "Health check: OK"
            echo "$BODY" | python3 -m json.tool 2>/dev/null || echo "$BODY"
            return 0
        else
            error "Health check failed (HTTP $HTTP_CODE)"
            return 1
        fi
    else
        error "curl is required for health check"
        exit 1
    fi
}

case "$1" in
    start)
        start
        ;;
    stop)
        stop
        ;;
    restart)
        restart
        ;;
    status)
        status
        ;;
    logs)
        logs
        ;;
    health)
        health
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|logs|health}"
        echo ""
        echo "Commands:"
        echo "  start   - Start the CO2 Monitor service"
        echo "  stop    - Stop the CO2 Monitor service"
        echo "  restart - Restart the CO2 Monitor service"
        echo "  status  - Check if the service is running"
        echo "  logs    - Follow the log file"
        echo "  health  - Check the health endpoint"
        exit 1
        ;;
esac
