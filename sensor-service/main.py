#!/usr/bin/env python3
"""sensor-service (Sensing team): serves hardware bus readings over HTTP."""
import json
import os
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(os.environ.get("SENSOR_PORT", "8001"))
BUS_URL = os.environ.get("HARDWARE_BUS_URL", "http://localhost:9000")

_requests = 0


def _read_register(name):
    with urllib.request.urlopen(f"{BUS_URL}/register/{name}", timeout=2) as resp:
        return json.load(resp)["value"]


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
        global _requests
        if self.path == "/healthz":
            return self._send(200, {"status": "ok"})
        if self.path == "/reading":
            _requests += 1
            try:
                return self._send(200, {
                    "temperature_c": _read_register("temperature"),
                    "vibration_mm_s": _read_register("vibration"),
                    "timestamp": time.time(),
                })
            except (urllib.error.URLError, TimeoutError) as exc:
                return self._send(503, {"error": f"hardware bus unreachable: {exc}"})
        if self.path == "/metrics":
            return self._send(200, (
                "# TYPE sensor_requests_total counter\n"
                f"sensor_requests_total {_requests}\n"
            ), "text/plain; version=0.0.4")
        self._send(404, {"error": "not found"})


if __name__ == "__main__":
    print(f"sensor-service listening on :{PORT}, bus at {BUS_URL}")
    ThreadingHTTPServer((os.environ.get("SENSOR_HOST", "0.0.0.0"), PORT), Handler).serve_forever()
