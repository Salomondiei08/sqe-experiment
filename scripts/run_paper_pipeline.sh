#!/usr/bin/env bash
set -euo pipefail

# Regenerate and verify the current SQE paper package from existing executed
# results. This script is non-destructive: it does not delete server files and
# does not rerun retrieval or generate new expansion data.

ROOT="/home/nlp-07/sqe_experiment"
PY="/home/nlp-07/evermemos/EverOS/methods/evermemos/.venv/bin/python"
TECTONIC="/home/nlp-07/.local/bin/tectonic-musl"

verify_seed() {
  local data_dir="$1"
  local index_dir="$2"
  local results_dir="$3"
  local report_path="${4:-${results_dir}/verification_report.json}"
  local manifest_flag="${5:-}"
  "${PY}" "${ROOT}/scripts/07_verify_experiment.py" \
    --data_dir "${data_dir}" \
    --index_dir "${index_dir}" \
    --results_dir "${results_dir}" \
    --paper_dir "${ROOT}/paper" \
    --report_path "${report_path}" \
    ${manifest_flag}
}

"${PY}" "${ROOT}/scripts/19_win_loss_analysis.py" \
  --root "${ROOT}" \
  --seeds "42,43,44,45,46,47,48,49" \
  --k 5 \
  --output "results_multiseed/win_loss_analysis.json" \
  --table_output "paper/tables/win_loss_analysis.tex"

bash "${ROOT}/scripts/run_multiseed_artifacts.sh"

"${PY}" "${ROOT}/scripts/15_gate_variant_diagnostics.py" \
  --root "${ROOT}" \
  --seeds "42,43,44,45,46,47,48,49" \
  --output "results_gate_calibration/gate_variant_diagnostics.json" \
  --table_output "paper/tables/gate_variant_diagnostics.tex"

"${PY}" "${ROOT}/scripts/16_gate_headroom_diagnostics.py" \
  --root "${ROOT}" \
  --seeds "42,43,44,45,46,47,48,49" \
  --output "results_gate_calibration/gate_headroom_diagnostics.json" \
  --table_output "paper/tables/gate_headroom_diagnostics.tex"

"${PY}" "${ROOT}/scripts/22_gate_feature_diagnostics.py" \
  --root "${ROOT}" \
  --seeds "42,43,44,45,46,47,48,49" \
  --device cpu \
  --output "results_gate_calibration/gate_feature_diagnostics.json" \
  --table_output "paper/tables/gate_feature_diagnostics.tex"

"${PY}" "${ROOT}/scripts/28_gate_validation_paired_tests.py" \
  --root "${ROOT}" \
  --output "results_gate_calibration/gate_validation_paired_tests.json" \
  --table_output "paper/tables/gate_validation_paired_tests.tex"

"${PY}" "${ROOT}/scripts/29_cross_seed_top1_gate.py" \
  --root "${ROOT}" \
  --seeds "42,43,44,45,46,47,48,49" \
  --output "results_gate_calibration/cross_seed_top1_gate.json" \
  --table_output "paper/tables/cross_seed_top1_gate.tex"

"${PY}" "${ROOT}/scripts/32_cross_seed_gate_variant.py" \
  --root "${ROOT}" \
  --output "results_gate_calibration/cross_seed_gate_variant.json" \
  --table_output "paper/tables/cross_seed_gate_variant.tex"

"${PY}" "${ROOT}/scripts/06_make_paper_artifacts.py" \
  --results_dir "${ROOT}/results_500_memory_seed42" \
  --paper_dir "${ROOT}/paper" \
  --data_dir "${ROOT}/data_500_memory_seed42"

"${PY}" "${ROOT}/scripts/31_verify_latex_clean_build.py" \
  --root "${ROOT}" \
  --paper_dir "paper" \
  --tex "main.tex" \
  --tectonic "${TECTONIC}" \
  --output "LATEX_BUILD_AUDIT.json"

"${PY}" "${ROOT}/scripts/36_make_conference_preview.py" \
  --tectonic "${TECTONIC}" \
  --output "paper/main_conference_preview.tex" \
  --audit "CONFERENCE_PREVIEW_AUDIT.json"

"${PY}" "${ROOT}/scripts/38_capture_compute_environment.py" \
  --root "${ROOT}" \
  --output "COMPUTE_ENVIRONMENT.json"

"${PY}" "${ROOT}/scripts/37_audit_paper_style.py" \
  --root "${ROOT}" \
  --output "PAPER_STYLE_AUDIT.json"

"${PY}" "${ROOT}/scripts/39_audit_figure_assets.py" \
  --root "${ROOT}" \
  --output "FIGURE_ASSET_AUDIT.json"

"${PY}" "${ROOT}/scripts/43_audit_paper_evidence_claims.py" \
  --root "${ROOT}" \
  --output "PAPER_EVIDENCE_CLAIM_AUDIT.json"

verify_seed \
  "${ROOT}/data_500_memory_seed42" \
  "${ROOT}/index_500_seed42" \
  "${ROOT}/results_500_memory_seed42" \
  "${ROOT}/results_500_memory_seed42/verification_report.json" \
  "--skip_manifest_freshness"
verify_seed \
  "${ROOT}/data_500_memory_seed43" \
  "${ROOT}/index_500_seed43" \
  "${ROOT}/results_500_memory_seed43" \
  "${ROOT}/results_500_memory_seed43/verification_report.json" \
  "--skip_manifest_freshness"
verify_seed \
  "${ROOT}/data_500_memory_seed44" \
  "${ROOT}/index_500_seed44" \
  "${ROOT}/results_500_memory_seed44" \
  "${ROOT}/results_500_memory_seed44/verification_report.json" \
  "--skip_manifest_freshness"
verify_seed \
  "${ROOT}/data_500_memory_seed45" \
  "${ROOT}/index_500_seed45" \
  "${ROOT}/results_500_memory_seed45" \
  "${ROOT}/results_500_memory_seed45/verification_report.json" \
  "--skip_manifest_freshness"
verify_seed \
  "${ROOT}/data_500_memory_seed46" \
  "${ROOT}/index_500_seed46" \
  "${ROOT}/results_500_memory_seed46" \
  "${ROOT}/results_500_memory_seed46/verification_report.json" \
  "--skip_manifest_freshness"
verify_seed \
  "${ROOT}/data_500_memory_seed47" \
  "${ROOT}/index_500_seed47" \
  "${ROOT}/results_500_memory_seed47" \
  "${ROOT}/results_500_memory_seed47/verification_report.json" \
  "--skip_manifest_freshness"
verify_seed \
  "${ROOT}/data_500_memory_seed48" \
  "${ROOT}/index_500_seed48" \
  "${ROOT}/results_500_memory_seed48" \
  "${ROOT}/results_500_memory_seed48/verification_report.json" \
  "--skip_manifest_freshness"
verify_seed \
  "${ROOT}/data_500_memory_seed49" \
  "${ROOT}/index_500_seed49" \
  "${ROOT}/results_500_memory_seed49" \
  "${ROOT}/results_500_memory_seed49/verification_report.json" \
  "--skip_manifest_freshness"

"${PY}" "${ROOT}/scripts/26_check_pass1_harness_readiness.py" \
  --sqe_root "${ROOT}" \
  --output "${ROOT}/pass1_harness_preflight.json"

# Refresh the human-label verification report. Missing labels are an expected
# non-fatal blocker for the current retrieval-paper draft and are surfaced by
# SUBMISSION_READINESS.json.
if ! "${PY}" "${ROOT}/scripts/18_verify_human_audit_labels.py" \
  --audit_dir "${ROOT}/human_audit" \
  --output "${ROOT}/human_audit/verification_report.json"; then
  :
fi

"${PY}" "${ROOT}/scripts/14_submission_readiness_check.py" \
  --root "${ROOT}" \
  --output "SUBMISSION_READINESS.json"

"${PY}" "${ROOT}/scripts/43_audit_paper_evidence_claims.py" \
  --root "${ROOT}" \
  --output "PAPER_EVIDENCE_CLAIM_AUDIT.json"

"${PY}" "${ROOT}/scripts/35_write_missing_evidence_blockers.py" \
  --root "${ROOT}" \
  --output "MISSING_EVIDENCE_BLOCKERS.json"

"${PY}" "${ROOT}/scripts/33_prepare_hf_dataset_release.py" \
  --root "${ROOT}" \
  --output_dir "${ROOT}/hf_dataset_release" \
  --include_detailed_results

"${PY}" "${ROOT}/scripts/34_prepare_github_code_release.py" \
  --root "${ROOT}" \
  --output_dir "${ROOT}/github_code_release" \
  --include_result_summaries

# Refresh the tracked official reports after readiness is current, so their
# embedded readiness snapshot matches the final package state.
verify_seed \
  "${ROOT}/data_500_memory_seed42" \
  "${ROOT}/index_500_seed42" \
  "${ROOT}/results_500_memory_seed42" \
  "${ROOT}/results_500_memory_seed42/verification_report.json" \
  "--skip_manifest_freshness"
verify_seed \
  "${ROOT}/data_500_memory_seed43" \
  "${ROOT}/index_500_seed43" \
  "${ROOT}/results_500_memory_seed43" \
  "${ROOT}/results_500_memory_seed43/verification_report.json" \
  "--skip_manifest_freshness"
verify_seed \
  "${ROOT}/data_500_memory_seed44" \
  "${ROOT}/index_500_seed44" \
  "${ROOT}/results_500_memory_seed44" \
  "${ROOT}/results_500_memory_seed44/verification_report.json" \
  "--skip_manifest_freshness"
verify_seed \
  "${ROOT}/data_500_memory_seed45" \
  "${ROOT}/index_500_seed45" \
  "${ROOT}/results_500_memory_seed45" \
  "${ROOT}/results_500_memory_seed45/verification_report.json" \
  "--skip_manifest_freshness"
verify_seed \
  "${ROOT}/data_500_memory_seed46" \
  "${ROOT}/index_500_seed46" \
  "${ROOT}/results_500_memory_seed46" \
  "${ROOT}/results_500_memory_seed46/verification_report.json" \
  "--skip_manifest_freshness"
verify_seed \
  "${ROOT}/data_500_memory_seed47" \
  "${ROOT}/index_500_seed47" \
  "${ROOT}/results_500_memory_seed47" \
  "${ROOT}/results_500_memory_seed47/verification_report.json" \
  "--skip_manifest_freshness"
verify_seed \
  "${ROOT}/data_500_memory_seed48" \
  "${ROOT}/index_500_seed48" \
  "${ROOT}/results_500_memory_seed48" \
  "${ROOT}/results_500_memory_seed48/verification_report.json" \
  "--skip_manifest_freshness"
verify_seed \
  "${ROOT}/data_500_memory_seed49" \
  "${ROOT}/index_500_seed49" \
  "${ROOT}/results_500_memory_seed49" \
  "${ROOT}/results_500_memory_seed49/verification_report.json" \
  "--skip_manifest_freshness"

"${PY}" "${ROOT}/scripts/13_make_artifact_manifest.py" \
  --root "${ROOT}" \
  --output "ARTIFACT_MANIFEST.json"

# Final verification writes reports outside the artifact tree so it cannot make
# ARTIFACT_MANIFEST.json stale while proving the manifest is fresh.
verify_seed \
  "${ROOT}/data_500_memory_seed42" \
  "${ROOT}/index_500_seed42" \
  "${ROOT}/results_500_memory_seed42" \
  "/tmp/sqe_verify_seed42.json"
verify_seed \
  "${ROOT}/data_500_memory_seed43" \
  "${ROOT}/index_500_seed43" \
  "${ROOT}/results_500_memory_seed43" \
  "/tmp/sqe_verify_seed43.json"
verify_seed \
  "${ROOT}/data_500_memory_seed44" \
  "${ROOT}/index_500_seed44" \
  "${ROOT}/results_500_memory_seed44" \
  "/tmp/sqe_verify_seed44.json"
verify_seed \
  "${ROOT}/data_500_memory_seed45" \
  "${ROOT}/index_500_seed45" \
  "${ROOT}/results_500_memory_seed45" \
  "/tmp/sqe_verify_seed45.json"
verify_seed \
  "${ROOT}/data_500_memory_seed46" \
  "${ROOT}/index_500_seed46" \
  "${ROOT}/results_500_memory_seed46" \
  "/tmp/sqe_verify_seed46.json"
verify_seed \
  "${ROOT}/data_500_memory_seed47" \
  "${ROOT}/index_500_seed47" \
  "${ROOT}/results_500_memory_seed47" \
  "/tmp/sqe_verify_seed47.json"
verify_seed \
  "${ROOT}/data_500_memory_seed48" \
  "${ROOT}/index_500_seed48" \
  "${ROOT}/results_500_memory_seed48" \
  "/tmp/sqe_verify_seed48.json"
verify_seed \
  "${ROOT}/data_500_memory_seed49" \
  "${ROOT}/index_500_seed49" \
  "${ROOT}/results_500_memory_seed49" \
  "/tmp/sqe_verify_seed49.json"

echo "Paper package regenerated and verified for independent memory-index seeds 42, 43, 44, 45, 46, 47, 48, and 49."
