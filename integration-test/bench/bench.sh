#!/usr/bin/env bash
# Times `nix run .#test` against `docker compose up --build`, both warm, from
# "I want to test this" to "the assertions exited 0". Same tests, services, ports.
set -euo pipefail

cd "$(dirname "$0")/.."
ROOT="$(cd .. && pwd)"
RESULTS="bench/results"
mkdir -p "$RESULTS"

RUNS="${BENCH_RUNS:-10}"

# `type -P` and not `command -v`: the latter would find this function.
if type -P hyperfine >/dev/null; then
  hyperfine() { command hyperfine "$@"; }
else
  hyperfine() { nix run nixpkgs#hyperfine -- "$@"; }
fi

# From the working tree, not the pinned revisions: otherwise the nix leg is charged
# for a fetch the docker leg does not make.
LOCAL_INPUTS=(
  --override-input sensor-service "path:$ROOT/sensor-service"
  --override-input actuator-service "path:$ROOT/actuator-service"
  --override-input controller-service "path:$ROOT/controller-service"
  --override-input telemetry-service "path:$ROOT/telemetry-service"
)

COMPOSE="docker compose -f $ROOT/docker-compose.yml --project-directory $ROOT"

case "${1:-}" in
  nix-hot)
    # Warm the store first so the timed runs measure the run, not the build.
    nix build .#default "${LOCAL_INPUTS[@]}" --no-link
    hyperfine --warmup 1 --runs "$RUNS" \
      --prepare 'rm -rf .data' \
      --export-json "$RESULTS/nix-hot.json" \
      --command-name 'nix run .#test (warm store)' \
      "nix run .#test ${LOCAL_INPUTS[*]}"
    ;;

  docker-hot)
    $COMPOSE build >/dev/null
    hyperfine --warmup 1 --runs "$RUNS" \
      --prepare "$COMPOSE down -v --remove-orphans" \
      --export-json "$RESULTS/docker-hot.json" \
      --command-name 'docker compose up --build (warm layer cache)' \
      "$COMPOSE up --build --abort-on-container-exit --exit-code-from test"
    $COMPOSE down -v --remove-orphans >/dev/null 2>&1 || true
    ;;

  summary)
    exec "$(dirname "$0")/summary.sh"
    ;;

  *)
    cat >&2 <<USAGE
usage: bench/bench.sh <nix-hot|docker-hot|summary>

  nix-hot       nix run .#test, warm store, deps from cache.nixos.org
  docker-hot    docker compose up --build, warm layer cache
  summary       print a table from whatever is in bench/results/

  BENCH_RUNS=N  override the sample count.
USAGE
    exit 2
    ;;
esac
