# Integration tests across team boundaries, without a shared staging environment

This codebase is a replica setup of what's experimented at Orbem. The concept was presented as [a lightning talk at NixCon'26](https://talks.nixcon.org/nixcon-2026/talk/YP8SH3/).

For simplicity, they don't use the uv2nix/pyproject-nix machinery, the services are minimal.

> [!CAUTION]  
> Most of this codebase was LLM generated, although reviewed by me to make sure it represents reality of our internal efforts @ Orbem.

There are 4 services, each potentially owned by a different team, and packaged by the `flake.nix`
next to its own source. One command starts all of them plus their sidecars,
runs the cross-service assertions, and tears the stack down:


```sh
cd integration-test
just test
just test-pinned
```

## Layout

```
sensor-service/       flake.nix + main.py    GET /reading            :8001
actuator-service/     flake.nix + main.py    GET /state, POST /set   :8002
controller-service/   flake.nix + main.py    GET /status             :8003
telemetry-service/    flake.nix + main.py    GET /status             :8004
integration-test/
  flake.nix           consumes all four as inputs, exposes apps.test
  process-compose.nix the topology: bus mock, 4 services, prometheus, test
  tests/              the cross-service assertions
  bench/              times the nix leg against the docker leg
docker-compose.yml    the benchmark baseline
```

### Flake per service

Each service directory is an
independent flake, consumed by `integration-test/flake.nix` the same way any
other repo would be:

```nix
sensor-service.url = "github:shivashispadhi-orbem/nixcon26-lightning-talk?dir=sensor-service";
```

`?dir=` addresses a subdirectory. Moving `sensor-service/` into its own
repository means dropping `?dir=` from that line. Monorepo or separate repos is
not a concern for this toolkit.

## The test

```
      POST /register/temperature = 38°C
                 |
         hardware-bus-mock  (stands in for the fieldbus/PLC)
                 |
          sensor-service  GET /reading
                 |
        controller-service  38°C is above the band -> COOLING
                 |
          actuator-service  POST /set
                 |
         hardware-bus-mock  actuator_state = COOLING
                 |
      GET /register/actuator_state  =>  "COOLING"     <-- the assertion
                 |
         telemetry-service  aggregates all three
```

On real hardware the sensor MCU writes the temperature register and the
actuator MCU writes back the state it reached; here `actuator-service` writes
both, so this covers service composition rather than the physical layer.

## Running it

Needs Nix with flakes enabled (`experimental-features = nix-command flakes`).

```sh
cd integration-test
just test
```

Expected output:

```
[test] PASS sensor reads through to the bus
[test] PASS controller closes the loop through the actuator
[test] PASS telemetry aggregates all three
[test] 3 passed
```

`nix run .#test` is the entry point; `just test` adds
`--override-input ... path:../<service>` so local edits are picked up without a
push. `just test-pinned` drops them and takes every service from `flake.lock`,
which is what CI runs.

To drive the stack by hand instead:

```sh
nix develop
curl localhost:8001/reading
curl localhost:9090/api/v1/targets
```

### The docker-compose baseline

Note that the project doesn't use the `buildLayeredImage` to show a real-world workflow where people build with docker / podman, etc.

```sh
cd integration-test
just test-docker
```

## The benchmark

```sh
cd integration-test
just bench
just bench-manifest
```

| leg | dependencies come from | |
|---|---|---|
| `nix-hot` | `cache.nixos.org`, store already warm | `nix run .#test` |
| `docker-hot` | Docker Hub, layer cache already warm | `docker compose up --build` |

On an M3 Pro:

| leg | mean | n | |
|---|---|---|---|
| `nix-hot` | 6.51s ± 0.97s | 10 | |
| `docker-hot` | 69.72s ± 0.58s | 10 | 10.7× |

Even for cold-uses in a new machine, with a binary cache the nix runtime will behave better than an OCI container based one, because of better caching, although build times may be more in Nix.

Raw hyperfine JSON and the machine it ran on are in
`integration-test/bench/results/`.
