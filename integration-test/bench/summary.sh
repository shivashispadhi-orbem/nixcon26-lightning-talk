#!/usr/bin/env bash
# Print a table from whatever hyperfine JSON is in bench/results/.
set -euo pipefail
cd "$(dirname "$0")"

python3 - results/*.json <<'PY'
import json, statistics, sys

rows = []
for path in sys.argv[1:]:
    try:
        blob = json.load(open(path))
    except json.JSONDecodeError:  # a leg still running writes its file empty.
        continue
    for r in blob.get("results", []):  # manifest.json has none.
        t = r["times"]
        rows.append((
            path.split("/")[-1].removesuffix(".json"),
            len(t), statistics.mean(t), statistics.stdev(t) if len(t) > 1 else 0.0,
            statistics.median(t),
        ))

if not rows:
    sys.exit("no results in bench/results/ -- run bench.sh first")

rows.sort(key=lambda r: r[2])
width = max(len(r[0]) for r in rows)
print(f"{'leg':<{width}}  {'n':>3}  {'mean':>8}  {'sd':>7}  {'median':>8}")
for leg, n, mean, sd, med in rows:
    print(f"{leg:<{width}}  {n:>3}  {mean:>7.2f}s  {sd:>6.2f}s  {med:>7.2f}s")

print()
for leg, _, mean, _, _ in rows[1:]:
    print(f"{leg} is {mean / rows[0][2]:.1f}x {rows[0][0]}")
PY
