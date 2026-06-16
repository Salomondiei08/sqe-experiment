#!/usr/bin/env bash
set -euo pipefail

# Run one corrected SQE retrieval seed without modifying the active paper.
# This script writes to seed-specific directories and refuses to overwrite
# completed result directories unless ALLOW_OVERWRITE=1 is set.

ROOT="/home/nlp-07/sqe_experiment"
PY="/home/nlp-07/evermemos/EverOS/methods/evermemos/.venv/bin/python"

SEED="${1:-43}"
N_EVAL="${N_EVAL:-500}"
N_MEMORY="${N_MEMORY:-5000}"
DATA_DIR="${ROOT}/data_500_memory_seed${SEED}"
INDEX_DIR="${ROOT}/index_500_seed${SEED}"
RESULTS="${ROOT}/results_500_memory_seed${SEED}"
CACHE="${RESULTS}/expansion_cache.json"
DEVICE="${DEVICE:-cpu}"

if [[ -e "${RESULTS}" && "${ALLOW_OVERWRITE:-0}" != "1" ]]; then
  echo "Refusing to overwrite existing results directory: ${RESULTS}" >&2
  echo "Set ALLOW_OVERWRITE=1 only if you intentionally want to rerun this seed." >&2
  exit 1
fi

"${PY}" "${ROOT}/scripts/01_prepare_dataset.py" \
  --output_dir "${DATA_DIR}" \
  --n_memory "${N_MEMORY}" \
  --n_eval "${N_EVAL}" \
  --seed "${SEED}" \
  --eval_source memory \
  --resume \
  --llm_base_url http://localhost:8000/v1 \
  --llm_model Qwen3.6-35B-A3B

if [[ ! -e "${INDEX_DIR}/dense.faiss" ]]; then
  "${PY}" "${ROOT}/scripts/02_build_index.py" \
    --memory_path "${DATA_DIR}/memory_store.jsonl" \
    --index_dir "${INDEX_DIR}" \
    --embedding_model BAAI/bge-m3 \
    --device "${DEVICE}"
fi

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

echo "Completed seed ${SEED}: ${RESULTS}"
