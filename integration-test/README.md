# integration-test

Composes the four services, each packaged by its own `flake.nix` and consumed
here as a flake input, with a hardware-bus mock and Prometheus.

```sh
just test          # services from the working tree
just test-pinned   # services from flake.lock (what CI runs)
just bench         # times the nix leg against docker, see bench/README.md
```

See `../README.md` for what it asserts.

## Notes

`flake.nix` uses `evalModules` rather than `makeProcessCompose` to get
`outputs.testPackage`, which runs non-interactively and exits with the
assertions' status. The process named `test` in `process-compose.nix` creates
it.

`cli.preHook` wipes `.data` on every run, so each run is clean.
