#!/usr/bin/env bash
set -euo pipefail

# Regenerate deterministic multi-seed paper artifacts from completed result
# directories. This script reads executed JSONL files only; it does not run
# retrieval, generate expansions, or fabricate missing seeds.

ROOT="/home/nlp-07/sqe_experiment"
PY="/home/nlp-07/evermemos/EverOS/methods/evermemos/.venv/bin/python"
SEEDS="${SEEDS:-42,43,44,45,46,47,48,49}"
SEED_FAMILY="${SEED_FAMILY:-independent_memory}"

"${PY}" "${ROOT}/scripts/09_make_multiseed_report.py" \
  --root "${ROOT}" \
  --seeds "${SEEDS}" \
  --seed_family "${SEED_FAMILY}" \
  --output "results_multiseed/multiseed_report.json" \
  --table_output "paper/tables/multiseed_summary.tex"

"${PY}" "${ROOT}/scripts/11_make_multiseed_paired_tests.py" \
  --root "${ROOT}" \
  --seeds "${SEEDS}" \
  --seed_family "${SEED_FAMILY}" \
  --output "results_multiseed/multiseed_paired_tests.json" \
  --table_output "paper/tables/multiseed_paired_tests.tex"

"${PY}" "${ROOT}/scripts/12_make_multiseed_gate_validation.py" \
  --root "${ROOT}" \
  --seeds "${SEEDS}" \
  --seed_family "${SEED_FAMILY}" \
  --output "results_multiseed/multiseed_gate_validation.json" \
  --table_output "paper/tables/multiseed_gate_validation.tex"

echo "Regenerated deterministic multi-seed artifacts for ${SEED_FAMILY} seeds ${SEEDS}"
