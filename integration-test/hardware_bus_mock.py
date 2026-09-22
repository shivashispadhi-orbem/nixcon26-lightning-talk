#!/usr/bin/env python3
"""Mock hardware register bus, standing in for a real PLC/fieldbus.

Registers drift in a background thread the way a real sensor would, and are
read/written over HTTP so no service needs driver code.
"""
import json
import os
import random
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(os.environ.get("BUS_PORT", "9000"))
DRIFT_SECONDS = float(os.environ.get("BUS_DRIFT_INTERVAL_SECONDS", "1.0"))

_lock = threading.Lock()
_registers = {
    "temperature": 21.5,  # Celsius
    "vibration": 0.02,  # mm/s
    "actuator_state": "IDLE",
    "actuator_setpoint": "IDLE",
}


def _drift_loop():
    while True:
        time.sleep(DRIFT_SECONDS)
        with _lock:
            _registers["temperature"] += random.uniform(-0.3, 0.3)
            _registers["vibration"] = max(0.0, _registers["vibration"] + random.uniform(-0.01, 0.01))
            if _registers["actuator_state"] == "COOLING":
                _registers["temperature"] -= 0.5


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _send(self, status, payload):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/healthz":
            return self._send(200, {"status": "ok"})
        if not self.path.startswith("/register/"):
            return self._send(404, {"error": "not found"})
        name = self.path.removeprefix("/register/")
        with _lock:
            if name not in _registers:
                return self._send(404, {"error": f"unknown register {name!r}"})
            self._send(200, {"name": name, "value": _registers[name]})

    def do_POST(self):
        if not self.path.startswith("/register/"):
            return self._send(404, {"error": "not found"})
        name = self.path.removeprefix("/register/")
        length = int(self.headers.get("Content-Length", "0"))
        value = json.loads(self.rfile.read(length) or b"{}")["value"]
        with _lock:
            _registers[name] = value
        self._send(200, {"name": name, "value": value})


if __name__ == "__main__":
    threading.Thread(target=_drift_loop, daemon=True).start()
    print(f"hardware-bus-mock listening on :{PORT}")
    ThreadingHTTPServer((os.environ.get("BUS_HOST", "0.0.0.0"), PORT), Handler).serve_forever()
