# Experiment results

Result artifacts are grouped by purpose instead of being spread across the
repository root.

## Independent memory-index runs

- `seed42/` through `seed49/` - one independently rebuilt memory store and
  index per seed.

## Aggregated analysis

- `multiseed/` - eight-seed reports, paired tests, and win/loss analysis.
- `gate_calibration/` - gate diagnostics and held-out threshold checks.
- `tokenmeasured_seed42/` - measured token and latency reruns.

The scripts accept the same grouped paths and the paper links to these
directories directly. Detailed raw memory stores are intentionally not part of
this public code release.
