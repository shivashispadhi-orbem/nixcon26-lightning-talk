# bench/

```sh
just bench           # nix-hot + docker-hot, then the table
just bench-manifest  # machine, toolchain, closure size, locked revs
```

## What is being compared

Both legs run the same `tests/test_control_loop.py` against the same four
services on the same ports; the docker leg only overrides the service URLs from
`localhost` to container DNS names. Both are timed from *"I want to test this"*
to *"the assertions exited 0"*, not to "the command returned".

| leg | dependencies from | local state |
|---|---|---|
| `nix-hot` | `cache.nixos.org` | store warm |
| `docker-hot` | Docker Hub | layer cache warm, base images present |

## Measured

| leg | mean | n | |
|---|---|---|---|
| `nix-hot` | 6.51s ± 0.97s | 10 | |
| `docker-hot` | 69.72s ± 0.58s | 10 | 10.7× |

M3 Pro, 11 cores, 18 GB. `results/manifest.json` records the machine, toolchain
and closure size; `on_ac_power` is in there because it moves the number.

The nix leg resolves the four services from the working tree
(`--override-input`) rather than the pinned revisions, so it is not charged for
a fetch the docker leg does not make.

## Files

| | |
|---|---|
| `bench.sh` | the two legs, plus `summary` |
| `summary.sh` | table from whatever JSON is in `results/` |
| `manifest.sh` | machine, toolchain, closure size, every locked revision |
| `results/` | hyperfine JSON + the manifest |
