#!/usr/bin/env python3
"""
Health Monitor for CO2 Monitor Service

Checks the health of the CO2 monitor API and outputs status.
Can be used with cron for periodic monitoring.
"""

import argparse
import json
import sys
from datetime import datetime
from urllib.request import urlopen
from urllib.error import URLError
from pathlib import Path


def check_health(base_url: str = "http://localhost:8080", timeout: int = 10) -> dict:
    """Check the health endpoint and return status."""
    try:
        with urlopen(f"{base_url}/api/health", timeout=timeout) as response:
            data = json.loads(response.read().decode())
            return {
                "status": "healthy",
                "data": data,
                "timestamp": datetime.now().isoformat()
            }
    except URLError as e:
        return {
            "status": "unhealthy",
            "error": str(e.reason),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


def check_sensor_reading(base_url: str = "http://localhost:8080", timeout: int = 10) -> dict:
    """Check if we're getting sensor readings."""
    try:
        with urlopen(f"{base_url}/api/current", timeout=timeout) as response:
            data = json.loads(response.read().decode())

            if data.get("co2_ppm") is None:
                return {
                    "status": "warning",
                    "message": "No CO2 reading available",
                    "data": data,
                    "timestamp": datetime.now().isoformat()
                }

            return {
                "status": "ok",
                "co2_ppm": data.get("co2_ppm"),
                "temperature": data.get("temperature_celsius"),
                "timestamp": datetime.now().isoformat()
            }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


def check_database(base_url: str = "http://localhost:8080", timeout: int = 10) -> dict:
    """Check database statistics."""
    try:
        with urlopen(f"{base_url}/api/statistics?hours=1", timeout=timeout) as response:
            data = json.loads(response.read().decode())

            if data.get("count", 0) == 0:
                return {
                    "status": "warning",
                    "message": "No measurements in last hour",
                    "data": data,
                    "timestamp": datetime.now().isoformat()
                }

            return {
                "status": "ok",
                "measurements_last_hour": data.get("count"),
                "co2_avg": data.get("co2", {}).get("avg"),
                "timestamp": datetime.now().isoformat()
            }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


def main():
    parser = argparse.ArgumentParser(description="CO2 Monitor Health Check")
    parser.add_argument(
        "--url", default="http://localhost:8080",
        help="Base URL of the CO2 monitor API"
    )
    parser.add_argument(
        "--timeout", type=int, default=10,
        help="Request timeout in seconds"
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Output as JSON"
    )
    parser.add_argument(
        "--quiet", action="store_true",
        help="Only output on errors"
    )

    args = parser.parse_args()

    # Run all checks
    results = {
        "api_health": check_health(args.url, args.timeout),
        "sensor": check_sensor_reading(args.url, args.timeout),
        "database": check_database(args.url, args.timeout)
    }

    # Determine overall status
    statuses = [r.get("status") for r in results.values()]
    if "error" in statuses or "unhealthy" in statuses:
        overall = "unhealthy"
        exit_code = 2
    elif "warning" in statuses:
        overall = "warning"
        exit_code = 1
    else:
        overall = "healthy"
        exit_code = 0

    results["overall"] = overall
    results["timestamp"] = datetime.now().isoformat()

    # Output
    if args.quiet and exit_code == 0:
        sys.exit(0)

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print(f"CO2 Monitor Health Check - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 50)

        for check, result in results.items():
            if check in ["overall", "timestamp"]:
                continue

            status = result.get("status", "unknown")
            status_symbol = {
                "ok": "[OK]",
                "healthy": "[OK]",
                "warning": "[WARN]",
                "unhealthy": "[FAIL]",
                "error": "[ERROR]"
            }.get(status, "[???]")

            print(f"\n{check}: {status_symbol}")

            if status in ["ok", "healthy"]:
                if "co2_ppm" in result:
                    print(f"  CO2: {result['co2_ppm']} ppm")
                if "temperature" in result:
                    print(f"  Temperature: {result['temperature']}°C")
                if "measurements_last_hour" in result:
                    print(f"  Measurements (1h): {result['measurements_last_hour']}")
                if "data" in result and "device_connected" in result["data"]:
                    print(f"  Device: {'Connected' if result['data']['device_connected'] else 'Disconnected'}")
            else:
                if "error" in result:
                    print(f"  Error: {result['error']}")
                if "message" in result:
                    print(f"  Message: {result['message']}")

        print(f"\n{'=' * 50}")
        print(f"Overall: {overall.upper()}")

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
