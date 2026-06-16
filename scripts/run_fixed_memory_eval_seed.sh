#!/usr/bin/env bash
set -euo pipefail

# Run a query-sampling seed over the corrected seed-42 memory/index.
# This avoids rebuilding the memory index and keeps all targets retrievable.

ROOT="/home/nlp-07/sqe_experiment"
PY="/home/nlp-07/evermemos/EverOS/methods/evermemos/.venv/bin/python"

SEED="${1:-43}"
N_EVAL="${N_EVAL:-500}"
SOURCE_DATA="${ROOT}/data_500_memory_seed42"
INDEX_DIR="${ROOT}/index_500_seed42"
DATA_DIR="${ROOT}/data_500_query_seed${SEED}_memory_seed42"
RESULTS="${ROOT}/results_500_query_seed${SEED}_memory_seed42"
CACHE="${RESULTS}/expansion_cache.json"
DEVICE="${DEVICE:-cpu}"

if [[ -e "${RESULTS}" && "${ALLOW_OVERWRITE:-0}" != "1" ]]; then
  echo "Refusing to overwrite existing results directory: ${RESULTS}" >&2
  echo "Set ALLOW_OVERWRITE=1 only if you intentionally want to rerun this seed." >&2
  exit 1
fi

"${PY}" "${ROOT}/scripts/10_prepare_eval_from_memory.py" \
  --source_memory "${SOURCE_DATA}/memory_store.jsonl" \
  --output_dir "${DATA_DIR}" \
  --n_eval "${N_EVAL}" \
  --seed "${SEED}" \
  --resume \
  --llm_base_url http://localhost:8000/v1 \
  --llm_model Qwen3.6-35B-A3B

mkdir -p "${RESULTS}"

"${PY}" "${ROOT}/scripts/03_run_baselines.py" \
  --eval_path "${DATA_DIR}/eval_pairs.jsonl" \
  --index_dir "${INDEX_DIR}" \
  --embedding_model BAAI/bge-m3 \
  --device "${DEVICE}" \
  --top_k 10 \
  --results_dir "${RESULTS}"

for MODE in selective always_expand traces_only paraphrases_only random_budget; do
  EXTRA_ARGS=()
  if [[ "${MODE}" == "random_budget" ]]; then
    EXTRA_ARGS+=(--random_expand_rate 0.46)
  fi
  "${PY}" "${ROOT}/scripts/04_run_proposed_method.py" \
    --eval_path "${DATA_DIR}/eval_pairs.jsonl" \
    --index_dir "${INDEX_DIR}" \
    --embedding_model BAAI/bge-m3 \
    --device "${DEVICE}" \
    --llm_base_url http://localhost:8000/v1 \
    --llm_model Qwen3.6-35B-A3B \
    --confidence_threshold 0.65 \
    --n_hypothetical_traces 2 \
    --n_paraphrases 2 \
    --top_k 10 \
    --results_dir "${RESULTS}" \
    --mode "${MODE}" \
    --seed "${SEED}" \
    --expansion_cache "${CACHE}" \
    "${EXTRA_ARGS[@]}"
done

"${PY}" "${ROOT}/scripts/07_verify_experiment.py" \
  --data_dir "${DATA_DIR}" \
  --index_dir "${INDEX_DIR}" \
  --results_dir "${RESULTS}" \
  --paper_dir "${ROOT}/paper" \
  --report_path "${RESULTS}/verification_report.json"

echo "Completed fixed-memory eval seed ${SEED}: ${RESULTS}"
