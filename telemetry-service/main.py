#!/usr/bin/env python3
"""telemetry-service (Platform team, own repo): aggregates the other three."""
import json
import os
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(os.environ.get("TELEMETRY_PORT", "8004"))
POLL_SECONDS = float(os.environ.get("TELEMETRY_POLL_INTERVAL_SECONDS", "2.0"))
SOURCES = (
    ("sensor", os.environ.get("SENSOR_SERVICE_URL", "http://localhost:8001") + "/reading"),
    ("actuator", os.environ.get("ACTUATOR_SERVICE_URL", "http://localhost:8002") + "/state"),
    ("controller", os.environ.get("CONTROLLER_SERVICE_URL", "http://localhost:8003") + "/status"),
)

_lock = threading.Lock()
_aggregate = {"sensor": None, "actuator": None, "controller": None, "updated_at": None}
_errors = 0


def _aggregate_loop():
    global _errors
    while True:
        snapshot, had_error = {}, False
        for key, url in SOURCES:
            try:
                with urllib.request.urlopen(url, timeout=2) as resp:
                    snapshot[key] = json.load(resp)
            except (urllib.error.URLError, TimeoutError) as exc:
                snapshot[key] = None
                had_error = True
                print(f"telemetry poll error for {key}: {exc}")
        with _lock:
            _aggregate.update(snapshot, updated_at=time.time())
            _errors += had_error
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
            snapshot, errors = dict(_aggregate), _errors
        if self.path == "/status":
            return self._send(200, snapshot)
        if self.path == "/metrics":
            return self._send(200, (
                "# TYPE telemetry_poll_errors_total counter\n"
                f"telemetry_poll_errors_total {errors}\n"
            ), "text/plain; version=0.0.4")
        self._send(404, {"error": "not found"})


if __name__ == "__main__":
    threading.Thread(target=_aggregate_loop, daemon=True).start()
    print(f"telemetry-service listening on :{PORT}")
    ThreadingHTTPServer((os.environ.get("TELEMETRY_HOST", "0.0.0.0"), PORT), Handler).serve_forever()
