#!/usr/bin/env python3
"""actuator-service (Sensing team): relays setpoints to the hardware bus."""
import json
import os
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(os.environ.get("ACTUATOR_PORT", "8002"))
BUS_URL = os.environ.get("HARDWARE_BUS_URL", "http://localhost:9000")
VALID_STATES = {"IDLE", "COOLING", "HEATING"}

_setpoints = 0


def _read_register(name):
    with urllib.request.urlopen(f"{BUS_URL}/register/{name}", timeout=2) as resp:
        return json.load(resp)["value"]


def _write_register(name, value):
    req = urllib.request.Request(
        f"{BUS_URL}/register/{name}", data=json.dumps({"value": value}).encode(), method="POST"
    )
    req.add_header("Content-Type", "application/json")
    urllib.request.urlopen(req, timeout=2).close()


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
        if self.path == "/state":
            try:
                return self._send(200, {"state": _read_register("actuator_state")})
            except (urllib.error.URLError, TimeoutError) as exc:
                return self._send(503, {"error": f"hardware bus unreachable: {exc}"})
        if self.path == "/metrics":
            return self._send(200, (
                "# TYPE actuator_setpoints_total counter\n"
                f"actuator_setpoints_total {_setpoints}\n"
            ), "text/plain; version=0.0.4")
        self._send(404, {"error": "not found"})

    def do_POST(self):
        global _setpoints
        if self.path != "/set":
            return self._send(404, {"error": "not found"})
        length = int(self.headers.get("Content-Length", "0"))
        state = json.loads(self.rfile.read(length) or b"{}").get("state")
        if state not in VALID_STATES:
            return self._send(400, {"error": f"state must be one of {sorted(VALID_STATES)}"})
        try:
            # On real hardware the actuator MCU writes back the state it reached.
            _write_register("actuator_state", state)
            _write_register("actuator_setpoint", state)
        except (urllib.error.URLError, TimeoutError) as exc:
            return self._send(503, {"error": f"hardware bus unreachable: {exc}"})
        _setpoints += 1
        self._send(200, {"state": state})


if __name__ == "__main__":
    print(f"actuator-service listening on :{PORT}, bus at {BUS_URL}")
    ThreadingHTTPServer((os.environ.get("ACTUATOR_HOST", "0.0.0.0"), PORT), Handler).serve_forever()
