#!/usr/bin/env python3
"""Cross-service assertions for the control loop.

The loop only closes when sensor-service, actuator-service and
controller-service run against the same hardware bus, so no per-service suite
covers it. Temperature goes in at the bus; the actuator state comes back out at
the bus, not out of controller-service's own status.

The bus mock stands in for a fieldbus/PLC. On real hardware the sensor MCU
writes the temperature register and the actuator MCU writes back the state it
reached; here actuator-service writes both, so this covers service composition
rather than the physical layer.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

# Defaults are the process-compose layout. The docker leg runs this same file in
# a container, where each service is a DNS name.
BUS = os.environ.get("HARDWARE_BUS_URL", "http://localhost:9000")
SENSOR = os.environ.get("SENSOR_SERVICE_URL", "http://localhost:8001")
ACTUATOR = os.environ.get("ACTUATOR_SERVICE_URL", "http://localhost:8002")
CONTROLLER = os.environ.get("CONTROLLER_SERVICE_URL", "http://localhost:8003")
TELEMETRY = os.environ.get("TELEMETRY_SERVICE_URL", "http://localhost:8004")
TARGET_HIGH_C = float(os.environ.get("CONTROLLER_TARGET_HIGH_C", "23.0"))


def get(url):
    with urllib.request.urlopen(url, timeout=5) as resp:
        return json.load(resp)


def post(url, payload):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), method="POST")
    req.add_header("Content-Type", "application/json")
    urllib.request.urlopen(req, timeout=5).close()


def until(predicate, what, timeout=30.0, interval=0.5):
    """Poll until predicate returns a truthy value, or fail the test."""
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        try:
            last = predicate()
            if last:
                return last
        except (urllib.error.URLError, TimeoutError, KeyError, TypeError) as exc:
            last = exc
        time.sleep(interval)
    raise AssertionError(f"timed out after {timeout}s waiting for {what} (last: {last!r})")


def test_sensor_reads_through_to_the_bus():
    post(f"{BUS}/register/temperature", {"value": 42.5})
    reading = until(
        lambda: get(f"{SENSOR}/reading") if get(f"{SENSOR}/reading")["temperature_c"] > 40 else None,
        "sensor-service to report the temperature written to the bus",
    )
    assert "vibration_mm_s" in reading, reading


def test_controller_closes_the_loop_through_the_actuator():
    post(f"{BUS}/register/actuator_state", {"value": "IDLE"})
    post(f"{BUS}/register/temperature", {"value": TARGET_HIGH_C + 15})

    until(
        lambda: get(f"{BUS}/register/actuator_state")["value"] == "COOLING",
        "controller-service to drive the actuator to COOLING via the bus",
    )
    assert get(f"{ACTUATOR}/state")["state"] == "COOLING", get(f"{ACTUATOR}/state")

    status = get(f"{CONTROLLER}/status")
    assert status["last_decision"] == "COOLING", status
    assert status["cycles"] > 0, status


def _telemetry_saw_cooling():
    agg = get(f"{TELEMETRY}/status")
    if not all(agg[k] for k in ("sensor", "actuator", "controller")):
        return None
    return agg if agg["controller"]["last_decision"] == "COOLING" else None


def test_telemetry_aggregates_all_three():
    # telemetry polls on its own clock, so wait for its view to catch up.
    agg = until(_telemetry_saw_cooling, "telemetry-service to observe the COOLING decision")
    assert agg["actuator"]["state"] == "COOLING", agg
    assert agg["controller"]["cycles"] > 0, agg
    assert agg["sensor"]["temperature_c"] > TARGET_HIGH_C, agg


TESTS = [
    ("sensor reads through to the bus", test_sensor_reads_through_to_the_bus),
    ("controller closes the loop through the actuator", test_controller_closes_the_loop_through_the_actuator),
    ("telemetry aggregates all three", test_telemetry_aggregates_all_three),
]

if __name__ == "__main__":
    for name, fn in TESTS:
        print(f"... {name}", flush=True)
        try:
            fn()
        except AssertionError as exc:
            print(f"FAIL {name}: {exc}", flush=True)
            sys.exit(1)
        print(f"PASS {name}", flush=True)
    print(f"\n{len(TESTS)} passed", flush=True)
