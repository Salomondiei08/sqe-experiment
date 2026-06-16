#!/usr/bin/env bash
set -euo pipefail

# Reproduce the current SQE retrieval ablation suite on the corrected 500-query
# memory-target dataset.
#
# Assumptions:
# - Run from /home/nlp-07/sqe_experiment or pass absolute paths as below.
# - The vLLM OpenAI-compatible server is available at http://localhost:8000/v1.
# - The model name exposed by vLLM is Qwen3.6-35B-A3B.
# - The EverMemOS venv contains the required SQE dependencies.

ROOT="/home/nlp-07/sqe_experiment"
PY="/home/nlp-07/evermemos/EverOS/methods/evermemos/.venv/bin/python"
DATA_DIR="${ROOT}/data_500_memory_seed42"
INDEX_DIR="${ROOT}/index_500_seed42"
RESULTS="${ROOT}/results_ablation_500_$(date +%Y%m%d_%H%M%S)"
CACHE="${RESULTS}/expansion_cache.json"
TOKEN_RESULTS="${ROOT}/results_tokenmeasured_500_seed42"

mkdir -p "${RESULTS}"

"${PY}" "${ROOT}/scripts/03_run_baselines.py" \
  --eval_path "${DATA_DIR}/eval_pairs.jsonl" \
  --index_dir "${INDEX_DIR}" \
  --embedding_model BAAI/bge-m3 \
  --device cpu \
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
    --device cpu \
    --llm_base_url http://localhost:8000/v1 \
    --llm_model Qwen3.6-35B-A3B \
    --confidence_threshold 0.65 \
    --n_hypothetical_traces 2 \
    --n_paraphrases 2 \
    --top_k 10 \
    --results_dir "${RESULTS}" \
    --mode "${MODE}" \
    --seed 42 \
    --expansion_cache "${CACHE}" \
    "${EXTRA_ARGS[@]}"
done

# Optional: rerun expansion methods without the expansion cache to capture
# measured token usage. This is slow because it regenerates expansions.
# Set RUN_TOKEN_MEASURED=1 for Selective-QE only, or RUN_TOKEN_MEASURED=all for
# all expansion ablations.
if [[ "${RUN_TOKEN_MEASURED:-0}" == "1" ]]; then
  mkdir -p "${TOKEN_RESULTS}"
  "${PY}" "${ROOT}/scripts/04_run_proposed_method.py" \
    --eval_path "${DATA_DIR}/eval_pairs.jsonl" \
    --index_dir "${INDEX_DIR}" \
    --embedding_model BAAI/bge-m3 \
    --device cpu \
    --llm_base_url http://localhost:8000/v1 \
    --llm_model Qwen3.6-35B-A3B \
    --confidence_threshold 0.65 \
    --n_hypothetical_traces 2 \
    --n_paraphrases 2 \
    --top_k 10 \
    --results_dir "${TOKEN_RESULTS}" \
    --mode selective \
    --seed 42 \
    --output_tag selective_tokenmeasured500
elif [[ "${RUN_TOKEN_MEASURED:-0}" == "all" ]]; then
  mkdir -p "${TOKEN_RESULTS}"
  for MODE in selective always_expand traces_only paraphrases_only random_budget; do
    EXTRA_ARGS=()
    if [[ "${MODE}" == "random_budget" ]]; then
      EXTRA_ARGS+=(--random_expand_rate 0.46)
    fi
    "${PY}" "${ROOT}/scripts/04_run_proposed_method.py" \
      --eval_path "${DATA_DIR}/eval_pairs.jsonl" \
      --index_dir "${INDEX_DIR}" \
      --embedding_model BAAI/bge-m3 \
      --device cpu \
      --llm_base_url http://localhost:8000/v1 \
      --llm_model Qwen3.6-35B-A3B \
      --confidence_threshold 0.65 \
      --n_hypothetical_traces 2 \
      --n_paraphrases 2 \
      --top_k 10 \
      --results_dir "${TOKEN_RESULTS}" \
      --mode "${MODE}" \
      --seed 42 \
      --output_tag "${MODE}_tokenmeasured500" \
      "${EXTRA_ARGS[@]}"
  done
fi

"${PY}" "${ROOT}/scripts/06_make_paper_artifacts.py" \
  --results_dir "${RESULTS}" \
  --paper_dir "${ROOT}/paper" \
  --data_dir "${DATA_DIR}"

"${PY}" "${ROOT}/scripts/07_verify_experiment.py" \
  --data_dir "${DATA_DIR}" \
  --index_dir "${INDEX_DIR}" \
  --results_dir "${RESULTS}" \
  --paper_dir "${ROOT}/paper" \
  --report_path "${RESULTS}/verification_report.json"

echo "Results written to ${RESULTS}"
