#!/usr/bin/env bash
set -euo pipefail

# Run real EvoAgentBench SWE-bench jobs for the SQE paper after preflight is green.
# This script creates Pass@1 result evidence only when the real harness runs and
# the import/summarize/verify steps all succeed. It never fabricates rows.

MODE="${1:-smoke}"
PARALLEL="${PARALLEL:-1}"
SMOKE_TASK="${SMOKE_TASK:-astropy__astropy-12907}"
SQE_ROOT="${SQE_ROOT:-/home/nlp-07/sqe_experiment}"
EVO_ROOT="${EVO_ROOT:-/home/nlp-07/evermemos/EverOS/benchmarks/EvoAgentBench}"
PY="${PY:-/home/nlp-07/evermemos/EverOS/methods/evermemos/.venv/bin/python}"
CONFIG_ROOT="$SQE_ROOT/pass1_evoagentbench_configs"
PREFLIGHT="$SQE_ROOT/pass1_harness_preflight.json"
RESULTS_DIR="$SQE_ROOT/results_pass1"
MIN_TASK_COUNT=500
IMPORT_ARGS=()
if [[ "${PASS1_OVERWRITE:-0}" == "1" ]]; then
  IMPORT_ARGS+=(--overwrite)
fi

case "$MODE" in
  smoke|full) ;;
  *)
    echo "usage: $0 [smoke|full]" >&2
    exit 2
    ;;
esac

cd "$SQE_ROOT"
"$PY" scripts/26_check_pass1_harness_readiness.py \
  --sqe_root "$SQE_ROOT" \
  --evo_root "$EVO_ROOT" \
  --output "$PREFLIGHT" >/tmp/sqe_pass1_preflight.json

"$PY" - "$PREFLIGHT" <<'PY'
import json, sys
path = sys.argv[1]
report = json.load(open(path))
if report.get("ready_to_run_pass1") is not True:
    print("Pass@1 preflight is not ready. Blockers:", report.get("blockers"), file=sys.stderr)
    raise SystemExit(1)
PY

cd "$EVO_ROOT"

if [[ "$MODE" == "smoke" ]]; then
  TASK_ARGS=(--task "$SMOKE_TASK")
  JOB_SUFFIX="smoke"
  RESULTS_DIR="$SQE_ROOT/results_pass1_smoke"
  MIN_TASK_COUNT=1
else
  TASK_ARGS=(--split test)
  JOB_SUFFIX="test"
fi

"$PY" src/run.py --config "$CONFIG_ROOT/config_dense_codex.yaml" \
  "${TASK_ARGS[@]}" --parallel "$PARALLEL" --job "sqe_dense_codex_${JOB_SUFFIX}"
"$PY" src/run.py --config "$CONFIG_ROOT/config_always_expand_codex.yaml" \
  "${TASK_ARGS[@]}" --parallel "$PARALLEL" --job "sqe_always_expand_codex_${JOB_SUFFIX}"
"$PY" src/run.py --config "$CONFIG_ROOT/config_random_gated_codex.yaml" \
  "${TASK_ARGS[@]}" --parallel "$PARALLEL" --job "sqe_random_gated_codex_${JOB_SUFFIX}"
"$PY" src/run.py --config "$CONFIG_ROOT/config_selective_codex.yaml" \
  "${TASK_ARGS[@]}" --parallel "$PARALLEL" --job "sqe_selective_codex_${JOB_SUFFIX}"

cd "$SQE_ROOT"

"$PY" scripts/23_import_evoagentbench_pass1.py \
  --job_dir "$EVO_ROOT/jobs/sqe_dense_codex_${JOB_SUFFIX}" \
  --method Dense-Only \
  --output_dir "$RESULTS_DIR" \
  "${IMPORT_ARGS[@]}"
"$PY" scripts/23_import_evoagentbench_pass1.py \
  --job_dir "$EVO_ROOT/jobs/sqe_always_expand_codex_${JOB_SUFFIX}" \
  --method Always-Expand \
  --output_dir "$RESULTS_DIR" \
  "${IMPORT_ARGS[@]}"
"$PY" scripts/23_import_evoagentbench_pass1.py \
  --job_dir "$EVO_ROOT/jobs/sqe_random_gated_codex_${JOB_SUFFIX}" \
  --method Random-Gated-Expansion \
  --output_dir "$RESULTS_DIR" \
  "${IMPORT_ARGS[@]}"
"$PY" scripts/23_import_evoagentbench_pass1.py \
  --job_dir "$EVO_ROOT/jobs/sqe_selective_codex_${JOB_SUFFIX}" \
  --method Selective-QE \
  --output_dir "$RESULTS_DIR" \
  "${IMPORT_ARGS[@]}"

"$PY" scripts/21_summarize_pass1_results.py \
  --results_dir "$RESULTS_DIR" \
  --min_task_count "$MIN_TASK_COUNT"
"$PY" scripts/17_verify_pass1_results.py \
  --results_dir "$RESULTS_DIR" \
  --min_task_count "$MIN_TASK_COUNT"
"$PY" scripts/14_submission_readiness_check.py \
  --root "$SQE_ROOT" \
  --output "$SQE_ROOT/SUBMISSION_READINESS.json"

echo "Pass@1 ${MODE} run imported, summarized, and verified under $RESULTS_DIR"
