#!/usr/bin/env bash
# What the numbers in results/ were measured on.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p bench/results

# Same overrides bench.sh times, so the closure matches the numbers.
ROOT="$(cd .. && pwd)"
LOCAL_INPUTS=(
  --override-input sensor-service "path:$ROOT/sensor-service"
  --override-input actuator-service "path:$ROOT/actuator-service"
  --override-input controller-service "path:$ROOT/controller-service"
  --override-input telemetry-service "path:$ROOT/telemetry-service"
)
closure_mb=$(nix path-info -S .#default "${LOCAL_INPUTS[@]}" 2>/dev/null | awk '{printf "%.0f", $2/1024/1024}')
closure_paths=$(nix path-info -r .#default "${LOCAL_INPUTS[@]}" 2>/dev/null | wc -l | tr -d ' ')
: "${closure_mb:=null}" "${closure_paths:=null}"

python3 - > bench/results/manifest.json <<PY
import json, platform, subprocess

def sh(*cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=30).stdout.strip()
    except Exception:
        return None

print(json.dumps({
    "recorded_utc": sh("date", "-u", "+%Y-%m-%dT%H:%M:%SZ"),
    "machine": {
        "os": f"{platform.system()} {platform.release()}",
        "arch": platform.machine(),
        "cpu": sh("sysctl", "-n", "machdep.cpu.brand_string"),
        "cores": sh("sysctl", "-n", "hw.ncpu"),
        "ram_gb": round(int(sh("sysctl", "-n", "hw.memsize") or 0) / 1024**3),
        "on_ac_power": "AC Power" in (sh("pmset", "-g", "batt") or ""),
    },
    "toolchain": {
        "nix": sh("nix", "--version"),
        "docker": sh("docker", "version", "--format", "{{.Server.Version}}"),
        "compose": sh("docker", "compose", "version", "--short"),
    },
    "nix_closure": {"size_mb": $closure_mb, "store_paths": $closure_paths},
    # The services are timed from the working tree, so the revs below are what CI
    # pins, not what was timed. nixpkgs and process-compose-flake are the same either way.
    "services_from": "working tree (--override-input), not the locked revs",
    "locked_inputs": {
        name: node.get("locked", {}).get("rev") or node.get("locked", {}).get("narHash")
        for name, node in json.load(open("flake.lock"))["nodes"].items()
        if name != "root"
    },
    "docker_images": {
        "base": "python:3.11-slim",
        "prometheus": "prom/prometheus:v2.55.1",
        "registry": "docker.io",
    },
}, indent=2))
PY
echo "wrote bench/results/manifest.json"
