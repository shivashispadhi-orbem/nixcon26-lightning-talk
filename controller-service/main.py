#!/usr/bin/env python3
"""controller-service (Controls team, own repo): keeps temperature in band.

Polls sensor-service and drives actuator-service; no direct bus access.
"""
import json
import os
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(os.environ.get("CONTROLLER_PORT", "8003"))
SENSOR_URL = os.environ.get("SENSOR_SERVICE_URL", "http://localhost:8001")
ACTUATOR_URL = os.environ.get("ACTUATOR_SERVICE_URL", "http://localhost:8002")
POLL_SECONDS = float(os.environ.get("CONTROLLER_POLL_INTERVAL_SECONDS", "2.0"))
TARGET_LOW_C = float(os.environ.get("CONTROLLER_TARGET_LOW_C", "20.0"))
TARGET_HIGH_C = float(os.environ.get("CONTROLLER_TARGET_HIGH_C", "23.0"))

_lock = threading.Lock()
_status = {"last_reading": None, "last_decision": None, "cycles": 0, "errors": 0}


def _get_json(url):
    with urllib.request.urlopen(url, timeout=2) as resp:
        return json.load(resp)


def _decide(temperature_c):
    if temperature_c > TARGET_HIGH_C:
        return "COOLING"
    if temperature_c < TARGET_LOW_C:
        return "HEATING"
    return "IDLE"


def _control_loop():
    while True:
        try:
            reading = _get_json(f"{SENSOR_URL}/reading")
            decision = _decide(reading["temperature_c"])
            req = urllib.request.Request(
                f"{ACTUATOR_URL}/set", data=json.dumps({"state": decision}).encode(), method="POST"
            )
            req.add_header("Content-Type", "application/json")
            urllib.request.urlopen(req, timeout=2).close()
            with _lock:
                _status.update(last_reading=reading, last_decision=decision, cycles=_status["cycles"] + 1)
        except (urllib.error.URLError, TimeoutError, KeyError) as exc:
            with _lock:
                _status["errors"] += 1
            print(f"control loop error: {exc}")
        time.sleep(POLL_SECONDS)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _send(self, status, body, content_type="application/json"):
        body = body.encode() if isinstance(body, str) else json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/healthz":
            return self._send(200, {"status": "ok"})
        with _lock:
            snapshot = dict(_status)
        if self.path == "/status":
            return self._send(200, snapshot)
        if self.path == "/metrics":
            return self._send(200, (
                "# TYPE controller_cycles_total counter\n"
                f"controller_cycles_total {snapshot['cycles']}\n"
                "# TYPE controller_errors_total counter\n"
                f"controller_errors_total {snapshot['errors']}\n"
            ), "text/plain; version=0.0.4")
        self._send(404, {"error": "not found"})


if __name__ == "__main__":
    threading.Thread(target=_control_loop, daemon=True).start()
    print(f"controller-service listening on :{PORT}")
    ThreadingHTTPServer((os.environ.get("CONTROLLER_HOST", "0.0.0.0"), PORT), Handler).serve_forever()
