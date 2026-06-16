#!/usr/bin/env bash
set -euo pipefail

# Resume the SQE paper package after real external evidence has been added.
# This script does not create labels, task outcomes, or synthetic evidence.
# It summarizes and verifies existing real artifacts, then refreshes readiness,
# release bundles, the artifact manifest, and the final verifier report.

MODE="${1:-verify-only}"
SQE_ROOT="${SQE_ROOT:-/home/nlp-07/sqe_experiment}"
PY="${PY:-python3}"
PASS1_RESULTS_DIR="${PASS1_RESULTS_DIR:-$SQE_ROOT/results_pass1}"
HUMAN_AUDIT_DIR="${HUMAN_AUDIT_DIR:-$SQE_ROOT/human_audit}"
VERIFY_REPORT="${VERIFY_REPORT:-/tmp/sqe_verify_after_external_evidence.json}"

case "$MODE" in
  verify-only|rebuild-paper) ;;
  *)
    echo "usage: $0 [verify-only|rebuild-paper]" >&2
    exit 2
    ;;
esac

cd "$SQE_ROOT"

if [[ ! -d "$PASS1_RESULTS_DIR" ]]; then
  echo "missing Pass@1 result directory: $PASS1_RESULTS_DIR" >&2
  echo "Run scripts/42_run_pass1_after_preflight.sh full after Docker preflight is green." >&2
  exit 1
fi

if [[ ! -f "$HUMAN_AUDIT_DIR/labeled_human_audit_queries.csv" ]]; then
  echo "missing real human labels: $HUMAN_AUDIT_DIR/labeled_human_audit_queries.csv" >&2
  echo "Complete the human-audit labeling packet before resuming." >&2
  exit 1
fi

"$PY" scripts/21_summarize_pass1_results.py \
  --results_dir "$PASS1_RESULTS_DIR"
"$PY" scripts/17_verify_pass1_results.py \
  --results_dir "$PASS1_RESULTS_DIR"

"$PY" scripts/20_summarize_human_audit_labels.py \
  --audit_dir "$HUMAN_AUDIT_DIR"
"$PY" scripts/18_verify_human_audit_labels.py \
  --audit_dir "$HUMAN_AUDIT_DIR" \
  --output "$HUMAN_AUDIT_DIR/verification_report.json"

"$PY" scripts/14_submission_readiness_check.py \
  --root "$SQE_ROOT" \
  --output "$SQE_ROOT/SUBMISSION_READINESS.json"
"$PY" scripts/35_write_missing_evidence_blockers.py \
  --root "$SQE_ROOT" \
  --output "$SQE_ROOT/MISSING_EVIDENCE_BLOCKERS.json"

if [[ "$MODE" == "rebuild-paper" ]]; then
  bash scripts/run_paper_pipeline.sh
fi

"$PY" scripts/33_prepare_hf_dataset_release.py \
  --root "$SQE_ROOT" \
  --output_dir "$SQE_ROOT/hf_dataset_release" \
  --include_detailed_results
"$PY" scripts/34_prepare_github_code_release.py \
  --root "$SQE_ROOT" \
  --output_dir "$SQE_ROOT/github_code_release" \
  --include_result_summaries
"$PY" scripts/13_make_artifact_manifest.py \
  --root "$SQE_ROOT" \
  --output "$SQE_ROOT/ARTIFACT_MANIFEST.json"
"$PY" scripts/07_verify_experiment.py \
  --data_dir data_500_memory_seed42 \
  --index_dir index_500_seed42 \
  --results_dir results_500_memory_seed42 \
  --paper_dir paper \
  --report_path "$VERIFY_REPORT"

echo "External evidence verified and package refreshed."
echo "Final verifier report: $VERIFY_REPORT"
