"""
Check whether the SQE paper package has the evidence needed for a strong
submission.

This script is intentionally conservative. It does not generate metrics. It
reads existing artifacts and reports which submission-readiness criteria are
met, weak, or missing.
"""

import argparse
import csv
import importlib.util
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_PASS1_METHODS = [
    "Dense-Only",
    "Always-Expand",
    "Random-Gated-Expansion",
    "Selective-QE",
]
DEFAULT_PASS1_MIN_TASK_COUNT = 500


def read_json(path):
    with open(path) as f:
        return json.load(f)


def read_jsonl(path):
    rows = []
    if not path.exists():
        return rows
    with open(path) as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def read_csv(path):
    if not path.exists():
        return []
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def independent_memory_seed_dirs(root):
    out = []
    for path in sorted(root.glob("results_500_memory_seed*")):
        seed_text = path.name.replace("results_500_memory_seed", "")
        if not seed_text.isdigit():
            continue
        verifier = path / "verification_report.json"
        if not verifier.exists():
            out.append({"seed": int(seed_text), "path": str(path), "status": "unverified"})
            continue
        report = read_json(verifier)
        status = "complete" if not report.get("failures") else "failed"
        out.append({"seed": int(seed_text), "path": str(path), "status": status})
    return out


def human_audit_status(root):
    audit_dir = root / "human_audit"
    source_rows = read_jsonl(audit_dir / "human_audit_queries.jsonl")
    labeled_csv = audit_dir / "labeled_human_audit_queries.csv"
    labeling_manifest = audit_dir / "human_audit_labeling_manifest.json"
    labeling_manifest_template = audit_dir / "human_audit_labeling_manifest.template.json"
    labeling_form = audit_dir / "labeling_form.html"
    labeling_form_manifest = audit_dir / "labeling_form_manifest.json"
    labeling_protocol = audit_dir / "LABELING_PROTOCOL.md"
    reviewer_quickstart = audit_dir / "REVIEWER_QUICKSTART.md"
    reviewer_packet_dir = audit_dir / "reviewer_packets"
    reviewer_packet_manifest = reviewer_packet_dir / "assignment_manifest.json"
    reviewer_packet_verification = audit_dir / "reviewer_packets_verification.json"
    summary_path = audit_dir / "human_audit_summary.json"
    verification_report_path = audit_dir / "verification_report.json"
    labeled_rows = read_csv(labeled_csv)
    labeling_manifest_data = read_json(labeling_manifest) if labeling_manifest.exists() else {}
    summary_data = read_json(summary_path) if summary_path.exists() else {}
    source_packet_paths = [
        audit_dir / "human_audit_queries.csv",
        audit_dir / "human_audit_queries.jsonl",
        audit_dir / "human_audit_manifest.json",
        audit_dir / "README.md",
        labeling_protocol,
        reviewer_quickstart,
    ]
    label_fields = [
        "is_query_clear",
        "does_target_answer_query",
        "is_query_too_specific_or_copied",
    ]
    allowed = {"yes", "no", "uncertain"}
    invalid_labels = []
    complete_label_rows = 0
    for row in labeled_rows:
        row_complete = True
        for field in label_fields:
            value = str(row.get(field, "")).strip().lower()
            if value not in allowed:
                invalid_labels.append(
                    {
                        "query_id": row.get("query_id"),
                        "field": field,
                        "value": row.get(field),
                    }
                )
                row_complete = False
        if row_complete:
            complete_label_rows += 1
    verification_report = {}
    verification_report_failures = []
    if verification_report_path.exists():
        verification_report = read_json(verification_report_path)
        verification_report_failures = verification_report.get("failures", [])
    reviewer_packet_verification_report = {}
    if reviewer_packet_verification.exists():
        reviewer_packet_verification_report = read_json(reviewer_packet_verification)
    reviewers = labeling_manifest_data.get("reviewers")
    reviewer_count = len(reviewers) if isinstance(reviewers, list) else 0
    adjudication_notes = labeling_manifest_data.get("adjudication_notes")
    protocol_notes = labeling_manifest_data.get("protocol_notes")
    summary_provenance_valid = (
        summary_data.get("artifact_type") == "human_audit_summary"
        and summary_data.get("is_experiment_evidence") is True
        and summary_data.get("source_csv") == "human_audit_queries.csv"
        and summary_data.get("labeled_csv") == "labeled_human_audit_queries.csv"
        and summary_data.get("labeling_manifest") == "human_audit_labeling_manifest.json"
    )
    manifest_guard_valid = (
        reviewer_count >= 2
        and isinstance(adjudication_notes, list)
        and bool(adjudication_notes)
        and all(str(value).strip() and "TODO" not in str(value) for value in adjudication_notes)
        and isinstance(protocol_notes, list)
        and bool(protocol_notes)
        and all(str(value).strip() and "TODO" not in str(value) for value in protocol_notes)
        and labeling_manifest_data.get("source_csv") == "human_audit_queries.csv"
        and labeling_manifest_data.get("labeled_csv") == "labeled_human_audit_queries.csv"
    )

    return {
        "source_rows": len(source_rows),
        "labeled_rows": len(labeled_rows),
        "complete_label_rows": complete_label_rows,
        "invalid_label_count": len(invalid_labels),
        "missing_files": [
            str(path)
            for path in [labeled_csv, labeling_manifest, summary_path]
            if not path.exists()
        ],
        "documentation_only_templates": [
            str(path)
            for path in [
                labeling_manifest_template,
                labeling_form,
                labeling_form_manifest,
                labeling_protocol,
                reviewer_quickstart,
                reviewer_packet_manifest,
            ]
            if path.exists()
        ],
        "source_packet_paths": [str(path) for path in source_packet_paths if path.exists()],
        "source_packet_is_evidence": False,
        "labeling_template_is_evidence": False,
        "labeling_form_is_evidence": False,
        "labeling_protocol_present": labeling_protocol.exists(),
        "labeling_protocol_is_evidence": False,
        "reviewer_quickstart_present": reviewer_quickstart.exists(),
        "reviewer_quickstart_is_evidence": False,
        "reviewer_packet_manifest_present": reviewer_packet_manifest.exists(),
        "reviewer_packet_manifest_is_evidence": False,
        "reviewer_packet_verification_present": reviewer_packet_verification.exists(),
        "reviewer_packet_verification_failures": reviewer_packet_verification_report.get(
            "failures", []
        ),
        "reviewer_packet_verification_is_evidence": False,
        "labeling_manifest_reviewer_count": reviewer_count,
        "labeling_manifest_has_two_reviewers": reviewer_count >= 2,
        "labeling_manifest_has_adjudication_notes": (
            isinstance(adjudication_notes, list)
            and bool(adjudication_notes)
            and all(str(value).strip() and "TODO" not in str(value) for value in adjudication_notes)
        ),
        "labeling_manifest_guard_valid": manifest_guard_valid,
        "summary_provenance_valid": summary_provenance_valid,
        "verification_report": str(verification_report_path),
        "verification_report_present": verification_report_path.exists(),
        "verification_report_failures": verification_report_failures,
        "valid": (
            bool(source_rows)
            and len(labeled_rows) == len(source_rows)
            and complete_label_rows == len(source_rows)
            and not invalid_labels
            and labeled_csv.exists()
            and labeling_manifest.exists()
            and summary_path.exists()
            and manifest_guard_valid
            and summary_provenance_valid
            and verification_report_path.exists()
            and not verification_report_failures
        ),
    }


def paired_dense_status(root):
    path = root / "results_multiseed" / "multiseed_paired_tests.json"
    if not path.exists():
        return {"present": False}
    report = read_json(path)
    dense = next(
        (row for row in report.get("rows", []) if row.get("baseline") == "Dense-Only"),
        {},
    )
    if not dense:
        return {"present": True, "dense_row_present": False}
    excludes_zero = dense.get("ci_low", 0) > 0 or dense.get("ci_high", 0) < 0
    return {
        "present": True,
        "dense_row_present": True,
        "delta": dense.get("delta"),
        "ci_low": dense.get("ci_low"),
        "ci_high": dense.get("ci_high"),
        "excludes_zero": excludes_zero,
    }


def gate_validation_paired_status(root):
    path = root / "results_gate_calibration" / "gate_validation_paired_tests.json"
    evidence = {
        "path": str(path),
        "present": path.exists(),
        "is_pass1_result": False,
    }
    if not path.exists():
        return evidence
    report = read_json(path)
    aggregate = report.get("aggregate", {})
    evidence.update(
        {
            "metric": report.get("metric"),
            "n_queries": aggregate.get("n_queries"),
            "delta": aggregate.get("delta"),
            "ci_low": aggregate.get("ci_low"),
            "ci_high": aggregate.get("ci_high"),
            "sign_flip_p": aggregate.get("sign_flip_p"),
            "excludes_zero": (
                aggregate.get("ci_low", 0) > 0 or aggregate.get("ci_high", 0) < 0
            ),
        }
    )
    return evidence


def cross_seed_top1_gate_status(root):
    path = root / "results_gate_calibration" / "cross_seed_top1_gate.json"
    table_path = root / "paper" / "tables" / "cross_seed_top1_gate.tex"
    script_path = root / "scripts" / "29_cross_seed_top1_gate.py"
    evidence = {
        "path": str(path),
        "table": str(table_path),
        "script": str(script_path),
        "present": path.exists(),
        "table_present": table_path.exists(),
        "script_present": script_path.exists(),
        "is_pass1_result": False,
    }
    if not path.exists():
        return evidence
    report = read_json(path)
    aggregate = report.get("aggregate", {})
    evidence.update(
        {
            "metric": report.get("metric"),
            "n_queries": aggregate.get("n_queries"),
            "gate_recall": aggregate.get("gate_recall"),
            "dense_recall": aggregate.get("dense_recall"),
            "delta_vs_dense": aggregate.get("delta_vs_dense"),
            "ci_low": aggregate.get("ci_low"),
            "ci_high": aggregate.get("ci_high"),
            "sign_flip_p": aggregate.get("sign_flip_p"),
            "expansion_rate": aggregate.get("expansion_rate"),
            "excludes_zero": (
                aggregate.get("ci_low", 0) > 0 or aggregate.get("ci_high", 0) < 0
            ),
        }
    )
    return evidence


def pass1_status(root):
    candidates = [
        root / "results_pass1",
        root / "pass1_results",
        root / "results_swebench_pass1",
    ]
    present = [path for path in candidates if path.exists()]
    schema_path = root / "PASS1_RESULTS_SCHEMA.md"
    importer_path = root / "scripts" / "23_import_evoagentbench_pass1.py"
    harness_audit_path = root / "PASS1_HARNESS_AUDIT.md"
    schema_note = {
        "schema_documentation": str(schema_path),
        "schema_documentation_present": schema_path.exists(),
        "schema_is_evidence": False,
        "evoagentbench_importer": str(importer_path),
        "evoagentbench_importer_present": importer_path.exists(),
        "importer_is_evidence": False,
        "harness_audit": str(harness_audit_path),
        "harness_audit_present": harness_audit_path.exists(),
    }
    if not present:
        return {"present_paths": [], "has_pass1_results": False, **schema_note}

    attempts = []
    for pass1_dir in present:
        manifest_path = pass1_dir / "manifest.json"
        summary_path = pass1_dir / "pass1_summary.json"
        detailed_paths = sorted(pass1_dir.glob("*_detailed.jsonl"))
        evidence = {
            "path": str(pass1_dir),
            "manifest": str(manifest_path),
            "summary": str(summary_path),
            "detailed_files": [str(path) for path in detailed_paths],
            "valid": False,
            "problems": [],
        }
        if not manifest_path.exists():
            evidence["problems"].append("missing manifest.json")
        if not summary_path.exists():
            evidence["problems"].append("missing pass1_summary.json")
        if not detailed_paths:
            evidence["problems"].append("missing *_detailed.jsonl files")

        rows = []
        for path in detailed_paths:
            rows.extend(read_jsonl(path))
        if not rows:
            evidence["problems"].append("no detailed rows")

        required_fields = {"task_id", "method", "success", "runtime_seconds"}
        missing_field_rows = []
        missing_failure_reason_rows = []
        for idx, row in enumerate(rows):
            missing_fields = sorted(required_fields - set(row))
            if missing_fields:
                missing_field_rows.append({"row_index": idx, "missing": missing_fields})
            if row.get("success") is False and not str(row.get("failure_reason", "")).strip():
                missing_failure_reason_rows.append(idx)
        if missing_field_rows:
            evidence["problems"].append(
                f"rows missing required fields: {missing_field_rows[:5]}"
            )
        if missing_failure_reason_rows:
            evidence["problems"].append(
                "unsuccessful rows missing failure_reason: "
                f"{missing_failure_reason_rows[:5]}"
            )

        recomputed = {}
        task_ids_by_method = {}
        for row in rows:
            method = row.get("method")
            if not method:
                continue
            entry = recomputed.setdefault(method, {"attempted": 0, "solved": 0})
            entry["attempted"] += 1
            if row.get("success") is True:
                entry["solved"] += 1
            task_id = row.get("task_id")
            if task_id:
                task_ids_by_method.setdefault(method, set()).add(task_id)
        for entry in recomputed.values():
            attempted = entry["attempted"]
            entry["pass@1"] = entry["solved"] / attempted if attempted else 0.0
        evidence["recomputed"] = recomputed
        evidence["expected_methods"] = EXPECTED_PASS1_METHODS

        missing_methods = sorted(set(EXPECTED_PASS1_METHODS) - set(recomputed))
        if missing_methods:
            evidence["problems"].append(
                f"missing expected Pass@1 methods: {missing_methods}"
            )
        expected_task_ids = set()
        for method in EXPECTED_PASS1_METHODS:
            expected_task_ids.update(task_ids_by_method.get(method, set()))
        evidence["task_set_size"] = len(expected_task_ids)
        evidence["minimum_task_count"] = DEFAULT_PASS1_MIN_TASK_COUNT
        if len(expected_task_ids) < DEFAULT_PASS1_MIN_TASK_COUNT:
            evidence["problems"].append(
                "task set is too small for paper Pass@1 evidence: "
                f"observed={len(expected_task_ids)} "
                f"required_minimum={DEFAULT_PASS1_MIN_TASK_COUNT}"
            )
        for method in EXPECTED_PASS1_METHODS:
            method_task_ids = task_ids_by_method.get(method, set())
            missing_tasks = sorted(expected_task_ids - method_task_ids)
            if missing_tasks:
                evidence["problems"].append(
                    f"method {method} missing task rows for expected task set: "
                    f"{missing_tasks[:10]}"
                )

        if summary_path.exists():
            summary = read_json(summary_path)
            summary_methods = summary.get("methods", {})
            if not isinstance(summary_methods, dict):
                evidence["problems"].append("pass1_summary.json methods is not an object")
                summary_methods = {}
            summary_task_set_size = summary.get("task_set_size")
            if summary_task_set_size != len(expected_task_ids):
                evidence["problems"].append(
                    "pass1_summary.json task_set_size does not match detailed rows: "
                    f"summary={summary_task_set_size} recomputed={len(expected_task_ids)}"
                )
            summary_min_task_count = summary.get("minimum_task_count")
            if summary_min_task_count != DEFAULT_PASS1_MIN_TASK_COUNT:
                evidence["problems"].append(
                    "pass1_summary.json must record the paper evidence minimum "
                    f"task count {DEFAULT_PASS1_MIN_TASK_COUNT}; "
                    f"observed={summary_min_task_count}"
                )
            for method, values in recomputed.items():
                summary_row = summary_methods.get(method)
                if not summary_row:
                    evidence["problems"].append(f"summary missing method {method}")
                    continue
                for key in ["attempted", "solved"]:
                    if summary_row.get(key) != values[key]:
                        evidence["problems"].append(
                            f"summary {method} {key}={summary_row.get(key)} "
                            f"does not match recomputed {values[key]}"
                        )
                if abs(float(summary_row.get("pass@1", -1)) - values["pass@1"]) > 1e-12:
                    evidence["problems"].append(
                        f"summary {method} pass@1={summary_row.get('pass@1')} "
                        f"does not match recomputed {values['pass@1']}"
                    )

        evidence["valid"] = not evidence["problems"]
        attempts.append(evidence)

    return {
        "present_paths": [str(path) for path in present],
        "has_pass1_results": any(item["valid"] for item in attempts),
        "attempts": attempts,
        **schema_note,
    }


def pass1_context_status(root):
    context_dir = root / "pass1_contexts"
    exporter_path = root / "scripts" / "24_export_pass1_retrieval_contexts.py"
    verifier_path = root / "scripts" / "25_verify_pass1_contexts.py"
    evidence = {
        "context_dir": str(context_dir),
        "exporter": str(exporter_path),
        "exporter_present": exporter_path.exists(),
        "verifier": str(verifier_path),
        "verifier_present": verifier_path.exists(),
        "is_pass1_result": False,
        "has_valid_contexts": False,
    }
    if not context_dir.exists():
        evidence["problems"] = [f"context directory does not exist: {context_dir}"]
        return evidence
    if not verifier_path.exists():
        evidence["problems"] = [f"context verifier missing: {verifier_path}"]
        return evidence

    spec = importlib.util.spec_from_file_location("pass1_context_verifier", verifier_path)
    if spec is None or spec.loader is None:
        evidence["problems"] = [f"cannot load context verifier: {verifier_path}"]
        return evidence
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    expected_methods = getattr(module, "DEFAULT_EXPECTED_METHODS", [])
    report = module.verify_contexts(context_dir, expected_methods=expected_methods)
    evidence["verification_report"] = report
    evidence["has_valid_contexts"] = not report.get("failures")
    evidence["expected_methods"] = expected_methods
    evidence["problems"] = report.get("failures", [])
    return evidence


def pass1_harness_preflight_status(root):
    path = root / "pass1_harness_preflight.json"
    checker_path = root / "scripts" / "26_check_pass1_harness_readiness.py"
    guarded_runner_path = root / "scripts" / "42_run_pass1_after_preflight.sh"
    execution_quickstart_path = (
        root / "pass1_evoagentbench_configs" / "EXECUTION_QUICKSTART.md"
    )
    guarded_runner_text = (
        guarded_runner_path.read_text(errors="replace")
        if guarded_runner_path.exists()
        else ""
    )
    evidence = {
        "preflight_report": str(path),
        "preflight_report_present": path.exists(),
        "checker": str(checker_path),
        "checker_present": checker_path.exists(),
        "guarded_runner": str(guarded_runner_path),
        "guarded_runner_present": guarded_runner_path.exists(),
        "guarded_runner_is_evidence": False,
        "guarded_runner_requires_ready_preflight": (
            "ready_to_run_pass1" in guarded_runner_text
            and "Pass@1 preflight is not ready" in guarded_runner_text
        ),
        "guarded_runner_default_no_overwrite": (
            "PASS1_OVERWRITE:-0" in guarded_runner_text
            and "IMPORT_ARGS+=(--overwrite)" in guarded_runner_text
        ),
        "guarded_runner_smoke_output_separate": (
            'RESULTS_DIR="$SQE_ROOT/results_pass1_smoke"' in guarded_runner_text
        ),
        "guarded_runner_full_min_task_count": (
            "MIN_TASK_COUNT=500" in guarded_runner_text
            and '--min_task_count "$MIN_TASK_COUNT"' in guarded_runner_text
        ),
        "guarded_runner_smoke_min_task_count_explicit": (
            "MIN_TASK_COUNT=1" in guarded_runner_text
            and 'if [[ "$MODE" == "smoke" ]]' in guarded_runner_text
        ),
        "execution_quickstart": str(execution_quickstart_path),
        "execution_quickstart_present": execution_quickstart_path.exists(),
        "execution_quickstart_is_evidence": False,
        "is_pass1_result": False,
    }
    if not path.exists():
        evidence["ready_to_run_pass1"] = False
        evidence["blockers"] = [f"missing preflight report: {path}"]
        return evidence
    report = read_json(path)
    evidence["checked_at_utc"] = report.get("checked_at_utc")
    evidence["ready_to_run_pass1"] = bool(report.get("ready_to_run_pass1"))
    evidence["blockers"] = report.get("blockers", [])
    evidence["python_missing"] = report.get("python_imports", {}).get("missing", [])
    docker = report.get("docker", {})
    evidence["docker_can_run"] = docker.get("can_run_docker_ps")
    evidence["docker_socket_group"] = docker.get("socket_group_name")
    evidence["docker_socket_group_members"] = docker.get("socket_group_members")
    evidence["docker_user_group_names"] = docker.get("user_group_names")
    evidence["docker_user_in_socket_group"] = docker.get("user_in_socket_group")
    evidence["docker_user_listed_in_socket_group"] = docker.get(
        "user_listed_in_socket_group"
    )
    alternate_runtimes = report.get("alternate_container_runtimes", {})
    evidence["alternate_container_runtime_note"] = alternate_runtimes.get("note")
    evidence["alternate_container_runtimes"] = {
        name: {
            "present": row.get("present"),
            "can_list_containers": row.get("can_list_containers"),
            "is_drop_in_for_evoagentbench_swebench": row.get(
                "is_drop_in_for_evoagentbench_swebench"
            ),
        }
        for name, row in alternate_runtimes.get("runtimes", {}).items()
    }
    evidence["parquet_exists"] = report.get("evoagentbench_data", {}).get("parquet_exists")
    evidence["split_file_exists"] = report.get("evoagentbench_data", {}).get("split_file_exists")
    evidence["context_packets_valid"] = report.get("context_packets", {}).get("valid")
    evidence["run_configs_valid"] = report.get("run_configs", {}).get("valid")
    evidence["codex_cli"] = report.get("run_configs", {}).get("codex_cli")
    return evidence


def external_evidence_resume_helper_status(root):
    script_path = root / "scripts" / "44_resume_after_external_evidence.sh"
    text = script_path.read_text(errors="replace") if script_path.exists() else ""
    required_snippets = [
        "missing Pass@1 result directory",
        "missing real human labels",
        "scripts/21_summarize_pass1_results.py",
        "scripts/17_verify_pass1_results.py",
        "scripts/20_summarize_human_audit_labels.py",
        "scripts/18_verify_human_audit_labels.py",
        "scripts/14_submission_readiness_check.py",
        "scripts/07_verify_experiment.py",
    ]
    forbidden_snippets = [
        "labeled_human_audit_queries.csv <<",
        "pass1_summary.json <<",
        "success\": true",
        "rm -rf",
    ]
    missing_required = [s for s in required_snippets if s not in text]
    forbidden_present = [s for s in forbidden_snippets if s in text]
    return {
        "script": str(script_path),
        "present": script_path.exists(),
        "is_experiment_evidence": False,
        "creates_labels_or_task_outcomes": False,
        "missing_required_snippets": missing_required,
        "forbidden_snippets_present": forbidden_present,
        "valid": script_path.exists() and not missing_required and not forbidden_present,
    }


def measured_token_status(root):
    token_summary = (
        root
        / "results_tokenmeasured_500_seed42"
        / "selective_tokenmeasured500_summary.json"
    )
    expansion_methods = [
        "always_expand",
        "traces_only",
        "paraphrases_only",
        "random_budget",
    ]
    measured_expansion = []
    for method in expansion_methods:
        candidates = list((root / "results_tokenmeasured_500_seed42").glob(f"*{method}*summary.json"))
        if candidates:
            measured_expansion.append(method)
    return {
        "selective_measured": token_summary.exists(),
        "other_measured_expansion_methods": measured_expansion,
    }


def no_hallucinated_data_status(root):
    policy_path = root / "NO_HALLUCINATED_DATA.md"
    required_phrases = [
        "invented, placeholder, or simulated",
        "executed random-gating budget control",
        "is not evidence",
    ]
    problems = []
    if not policy_path.exists():
        problems.append("missing NO_HALLUCINATED_DATA.md")
        policy_text = ""
    else:
        policy_text = policy_path.read_text(errors="replace")
        for phrase in required_phrases:
            if phrase not in policy_text:
                problems.append(f"policy missing required phrase: {phrase}")

    verifier_reports = sorted(root.glob("results_500_memory_seed*/verification_report.json"))
    report_checks = []
    for path in verifier_reports:
        report = read_json(path)
        checks = report.get("checks", {})
        report_status = {
            "path": str(path),
            "failures": report.get("failures", []),
            "forbidden_synthetic_evidence_references": checks.get(
                "forbidden_synthetic_evidence_references", []
            ),
            "invalid_or_deprecated_artifact_references": checks.get(
                "invalid_or_deprecated_artifact_references", []
            ),
            "unsupported_claim_references": checks.get("unsupported_claim_references", []),
            "legacy_random_budget_doc_references": checks.get(
                "legacy_random_budget_doc_references", []
            ),
            "stale_seed_provenance_doc_references": checks.get(
                "stale_seed_provenance_doc_references", []
            ),
            "stale_gate_variant_ci_doc_references": checks.get(
                "stale_gate_variant_ci_doc_references", []
            ),
            "checklist_missing_quarantine_phrases": checks.get(
                "checklist_missing_quarantine_phrases", []
            ),
            "checklist_forbidden_placeholder_claims": checks.get(
                "checklist_forbidden_placeholder_claims", []
            ),
            "no_hallucinated_data_missing_required_phrases": checks.get(
                "no_hallucinated_data_missing_required_phrases", []
            ),
        }
        report_checks.append(report_status)
        for key, value in report_status.items():
            if key == "path":
                continue
            if value:
                problems.append(f"{path}: {key}={value}")

    if not verifier_reports:
        problems.append("missing results_500_memory_seed*/verification_report.json")

    return {
        "policy": str(policy_path),
        "required_phrases": required_phrases,
        "verification_reports_checked": report_checks,
        "valid": not problems,
        "problems": problems,
    }


def latex_build_status(root):
    audit_path = root / "LATEX_BUILD_AUDIT.json"
    script_path = root / "scripts" / "31_verify_latex_clean_build.py"
    pdf_path = root / "paper" / "main.pdf"
    evidence = {
        "audit": str(audit_path),
        "audit_present": audit_path.exists(),
        "script": str(script_path),
        "script_present": script_path.exists(),
        "pdf": str(pdf_path),
        "pdf_present": pdf_path.exists(),
        "clean_build": False,
    }
    if not audit_path.exists():
        evidence["problems"] = [f"missing LaTeX build audit: {audit_path}"]
        return evidence
    audit = read_json(audit_path)
    evidence.update(
        {
            "clean_build": bool(audit.get("clean_build")),
            "returncode": audit.get("returncode"),
            "warnings": audit.get("warnings", []),
            "failures": audit.get("failures", []),
            "pdf_bytes": audit.get("pdf_bytes"),
            "pdf_pages": audit.get("pdf_pages"),
            "tectonic": audit.get("tectonic"),
        }
    )
    evidence["problems"] = audit.get("failures", [])
    return evidence


def conference_preview_status(root):
    audit_path = root / "CONFERENCE_PREVIEW_AUDIT.json"
    script_path = root / "scripts" / "36_make_conference_preview.py"
    tex_path = root / "paper" / "main_conference_preview.tex"
    pdf_path = root / "paper" / "main_conference_preview.pdf"
    evidence = {
        "audit": str(audit_path),
        "audit_present": audit_path.exists(),
        "script": str(script_path),
        "script_present": script_path.exists(),
        "tex": str(tex_path),
        "tex_present": tex_path.exists(),
        "pdf": str(pdf_path),
        "pdf_present": pdf_path.exists(),
        "is_experiment_evidence": False,
        "is_official_venue_template": False,
        "clean_for_preview": False,
        "problems": [],
    }
    problems = []
    for path, label in [
        (audit_path, "conference preview audit"),
        (script_path, "conference preview generator"),
        (tex_path, "conference preview TeX"),
        (pdf_path, "conference preview PDF"),
    ]:
        if not path.exists():
            problems.append(f"missing {label}: {path}")

    if audit_path.exists():
        audit = read_json(audit_path)
        evidence.update(
            {
                "clean_for_preview": bool(audit.get("clean_for_preview")),
                "warnings": audit.get("warnings", []),
                "failures": audit.get("failures", []),
                "pdf_bytes": audit.get("pdf_bytes"),
                "pdf_pages": audit.get("pdf_pages"),
                "is_experiment_evidence": audit.get("is_experiment_evidence"),
                "is_official_venue_template": audit.get("is_official_venue_template"),
            }
        )
        problems.extend(audit.get("failures", []))
        if audit.get("clean_for_preview") is not True:
            problems.append("CONFERENCE_PREVIEW_AUDIT.json is not clean_for_preview")
        if audit.get("is_experiment_evidence") is not False:
            problems.append("conference preview must be marked as non-evidence")
        if audit.get("is_official_venue_template") is not False:
            problems.append("conference preview must not claim official venue-template status")
        if pdf_path.exists() and audit.get("pdf_bytes") != pdf_path.stat().st_size:
            problems.append("conference preview audit pdf_bytes does not match current PDF")

    evidence["problems"] = problems
    evidence["valid"] = not problems
    return evidence


def paper_style_status(root):
    audit_path = root / "PAPER_STYLE_AUDIT.json"
    script_path = root / "scripts" / "37_audit_paper_style.py"
    evidence = {
        "audit": str(audit_path),
        "audit_present": audit_path.exists(),
        "script": str(script_path),
        "script_present": script_path.exists(),
        "clean": False,
        "is_experiment_evidence": False,
        "problems": [],
    }
    problems = []
    if not script_path.exists():
        problems.append(f"missing paper style audit script: {script_path}")
    if not audit_path.exists():
        problems.append(f"missing paper style audit: {audit_path}")
    else:
        audit = read_json(audit_path)
        evidence.update(
            {
                "clean": bool(audit.get("clean")),
                "n_figures": audit.get("n_figures"),
                "n_tables": audit.get("n_tables"),
                "manual_bold_count": audit.get("manual_bold_count"),
                "em_dash_count": audit.get("em_dash_count"),
                "forbidden_unicode_punctuation_counts": audit.get(
                    "forbidden_unicode_punctuation_counts", {}
                ),
                "guarded_phrases": audit.get("guarded_phrases", []),
                "hype_or_vague_phrase_hits": audit.get("hype_or_vague_phrase_hits", []),
                "required_layout_controls": audit.get("required_layout_controls", []),
                "missing_layout_controls": audit.get("missing_layout_controls", []),
                "warnings": audit.get("warnings", []),
                "failures": audit.get("failures", []),
            }
        )
        required_guarded_phrases = {"extense", "extensive", "extensively", "robust"}
        guarded_phrases = set(audit.get("guarded_phrases", []))
        missing_guarded_phrases = sorted(required_guarded_phrases - guarded_phrases)
        evidence["missing_required_guarded_phrases"] = missing_guarded_phrases
        if missing_guarded_phrases:
            problems.append(
                "paper style audit does not guard required wording: "
                f"{missing_guarded_phrases}"
            )
        required_layout_controls = {
            r"\captionsetup{font=small,labelfont=bf,skip=6pt}",
            r"\captionsetup[table]{position=top,aboveskip=7pt,belowskip=9pt}",
            r"\captionsetup[figure]{position=bottom,aboveskip=7pt,belowskip=9pt}",
            r"\setlength{\textfloatsep}{20pt plus 3pt minus 2pt}",
            r"\setlength{\floatsep}{18pt plus 3pt minus 2pt}",
            r"\setlength{\intextsep}{18pt plus 3pt minus 2pt}",
            r"\setlength{\tabcolsep}{5pt}",
            r"\renewcommand{\arraystretch}{1.08}",
            r"\emergencystretch=1em",
        }
        layout_controls = set(audit.get("required_layout_controls", []))
        missing_required_layout_controls = sorted(
            required_layout_controls - layout_controls
        )
        evidence["missing_required_layout_controls"] = (
            missing_required_layout_controls
        )
        if missing_required_layout_controls:
            problems.append(
                "paper style audit does not require layout controls: "
                f"{missing_required_layout_controls}"
            )
        if audit.get("missing_layout_controls"):
            problems.append(
                "paper style audit reports missing layout controls: "
                f"{audit.get('missing_layout_controls')}"
            )
        problems.extend(audit.get("failures", []))
        if audit.get("clean") is not True:
            problems.append("PAPER_STYLE_AUDIT.json is not clean")
        if audit.get("em_dash_count") != 0:
            problems.append("paper style audit reports em dash characters")
        if audit.get("forbidden_unicode_punctuation_counts"):
            problems.append(
                "paper style audit reports forbidden unicode punctuation: "
                f"{audit.get('forbidden_unicode_punctuation_counts')}"
            )
        if audit.get("hype_or_vague_phrase_hits"):
            problems.append(
                "paper style audit reports hype or vague wording: "
                f"{audit.get('hype_or_vague_phrase_hits')}"
            )
    evidence["problems"] = problems
    evidence["valid"] = not problems
    return evidence


def figure_asset_status(root):
    audit_path = root / "FIGURE_ASSET_AUDIT.json"
    script_path = root / "scripts" / "39_audit_figure_assets.py"
    evidence = {
        "audit": str(audit_path),
        "audit_present": audit_path.exists(),
        "script": str(script_path),
        "script_present": script_path.exists(),
        "clean": False,
        "is_experiment_evidence": False,
        "problems": [],
    }
    problems = []
    if not script_path.exists():
        problems.append(f"missing figure asset audit script: {script_path}")
    if not audit_path.exists():
        problems.append(f"missing figure asset audit: {audit_path}")
    else:
        audit = read_json(audit_path)
        evidence.update(
            {
                "clean": bool(audit.get("clean")),
                "n_active_figures": audit.get("n_active_figures"),
                "warnings": audit.get("warnings", []),
                "failures": audit.get("failures", []),
                "figures": audit.get("figures", []),
            }
        )
        problems.extend(audit.get("failures", []))
        if audit.get("clean") is not True:
            problems.append("FIGURE_ASSET_AUDIT.json is not clean")
        if audit.get("n_active_figures", 0) < 4:
            problems.append("figure asset audit reports fewer than 4 active figures")
    evidence["problems"] = problems
    evidence["valid"] = not problems
    return evidence


def paper_evidence_claim_status(root):
    audit_path = root / "PAPER_EVIDENCE_CLAIM_AUDIT.json"
    script_path = root / "scripts" / "43_audit_paper_evidence_claims.py"
    evidence = {
        "audit": str(audit_path),
        "audit_present": audit_path.exists(),
        "script": str(script_path),
        "script_present": script_path.exists(),
        "clean": False,
        "is_experiment_evidence": False,
        "problems": [],
    }
    problems = []
    if not script_path.exists():
        problems.append(f"missing paper evidence-claim audit script: {script_path}")
    if not audit_path.exists():
        problems.append(f"missing paper evidence-claim audit: {audit_path}")
    else:
        audit = read_json(audit_path)
        evidence.update(
            {
                "clean": bool(audit.get("clean")),
                "matches": audit.get("matches", []),
                "missing_required_limitations": audit.get(
                    "missing_required_limitations", []
                ),
                "warnings": audit.get("warnings", []),
                "failures": audit.get("failures", []),
                "strong_submission_ready": audit.get("strong_submission_ready"),
                "blocking_count": audit.get("blocking_count"),
            }
        )
        problems.extend(audit.get("failures", []))
        if audit.get("clean") is not True:
            problems.append("PAPER_EVIDENCE_CLAIM_AUDIT.json is not clean")
        if audit.get("matches"):
            problems.append(
                "paper evidence-claim audit reports unsupported positive claims: "
                f"{audit.get('matches')}"
            )
        if audit.get("missing_required_limitations"):
            problems.append(
                "paper evidence-claim audit reports missing limitation phrases: "
                f"{audit.get('missing_required_limitations')}"
            )
    evidence["problems"] = problems
    evidence["valid"] = not problems
    return evidence


def compute_environment_status(root):
    path = root / "COMPUTE_ENVIRONMENT.json"
    script_path = root / "scripts" / "38_capture_compute_environment.py"
    evidence = {
        "path": str(path),
        "present": path.exists(),
        "script": str(script_path),
        "script_present": script_path.exists(),
        "is_experiment_metric": False,
        "runtime_measurements_available": False,
        "problems": [],
    }
    problems = []
    if not script_path.exists():
        problems.append(f"missing compute capture script: {script_path}")
    if not path.exists():
        problems.append(f"missing compute environment metadata: {path}")
    else:
        report = read_json(path)
        cpu = report.get("cpu", {})
        gpus = report.get("gpus", [])
        memory = report.get("memory", {})
        evidence.update(
            {
                "checked_at_utc": report.get("checked_at_utc"),
                "is_experiment_metric": report.get("is_experiment_metric"),
                "runtime_measurements_available": report.get(
                    "runtime_measurements_available"
                ),
                "cpu_model": cpu.get("cpu_model"),
                "cpu_threads": cpu.get("cpu_threads"),
                "memory_total": memory.get("total"),
                "gpu_count": len(gpus),
                "gpu_names": sorted({gpu.get("name") for gpu in gpus if gpu.get("name")}),
            }
        )
        if report.get("is_experiment_metric") is not False:
            problems.append("compute metadata must not be marked as an experiment metric")
        if not cpu.get("cpu_model") or not cpu.get("cpu_threads"):
            problems.append("compute metadata is missing CPU model or thread count")
        if not memory.get("total"):
            problems.append("compute metadata is missing memory total")
    evidence["problems"] = problems
    evidence["valid"] = not problems
    return evidence


def llm_usage_disclosure_status(root):
    path = root / "LLM_USAGE_DISCLOSURE.md"
    required_phrases = [
        "documentation only",
        "not experiment evidence",
        "author remains responsible",
        "not used as a source of experiment evidence",
        "Missing evidence must remain marked as missing",
    ]
    missing_phrases = []
    if not path.exists():
        missing_phrases = required_phrases
    else:
        text = path.read_text(errors="replace")
        missing_phrases = [phrase for phrase in required_phrases if phrase not in text]
    return {
        "path": str(path),
        "present": path.exists(),
        "is_experiment_evidence": False,
        "required_phrases": required_phrases,
        "missing_required_phrases": missing_phrases,
        "valid": path.exists() and not missing_phrases,
    }


def blocked_next_actions_status(root):
    path = root / "BLOCKED_NEXT_ACTIONS.md"
    required_phrases = [
        "It is not experiment evidence.",
        "current user cannot access Docker daemon",
        "sudo usermod -aG docker nlp-07",
        "Dense-Only",
        "Always-Expand",
        "Random-Gated-Expansion",
        "Selective-QE",
        "labeled_human_audit_queries.csv",
        "human_audit_labeling_manifest.json",
        "human_audit_summary.json",
        "Do not create placeholder Pass@1 rows",
        "Missing evidence must remain marked as missing",
    ]
    missing_phrases = []
    if not path.exists():
        missing_phrases = required_phrases
        text = ""
    else:
        text = path.read_text(errors="replace")
        missing_phrases = [phrase for phrase in required_phrases if phrase not in text]
    return {
        "path": str(path),
        "present": path.exists(),
        "is_evidence": False,
        "required_phrases": required_phrases,
        "missing_required_phrases": missing_phrases,
        "valid": path.exists() and not missing_phrases,
    }


def release_helper_non_destructive_status(root):
    helper_names = [
        "33_prepare_hf_dataset_release.py",
        "34_prepare_github_code_release.py",
    ]
    destructive_patterns = ["shutil.rmtree", ".unlink(", "os.remove(", "os.rmdir("]
    required_noop_phrases = [
        "--clean",
        "Deprecated no-op retained for compatibility",
        "deprecated and ignored",
        "non-destructive",
    ]
    checked_scripts = []
    destructive_hits = []
    missing_noop_clean_guard = []
    for helper_name in helper_names:
        path = root / "scripts" / helper_name
        if not path.exists():
            missing_noop_clean_guard.append(f"{helper_name}: missing script")
            continue
        checked_scripts.append(str(path))
        text = path.read_text(errors="replace")
        for pattern in destructive_patterns:
            if pattern in text:
                destructive_hits.append(f"{helper_name}: {pattern}")
        missing_phrases = [
            phrase for phrase in required_noop_phrases if phrase not in text
        ]
        if missing_phrases:
            missing_noop_clean_guard.append(f"{helper_name}: {missing_phrases}")
    return {
        "checked_scripts": checked_scripts,
        "destructive_patterns": destructive_hits,
        "missing_noop_clean_guard": missing_noop_clean_guard,
        "deprecated_clean_is_noop": not missing_noop_clean_guard,
        "valid": not destructive_hits and not missing_noop_clean_guard,
    }


def project_script_deletion_safety_status(root):
    scripts_dir = root / "scripts"
    destructive_patterns = [
        ("shutil.rmtree", r"shutil\.rmtree"),
        (".unlink(", r"\.unlink\("),
        ("os.remove(", r"os\.remove\("),
        ("os.rmdir(", r"os\.rmdir\("),
        ("git reset --hard", r"git\s+reset\s+--hard"),
        ("git checkout --", r"git\s+checkout\s+--"),
        ("rm command", r"(^|\n)\s*rm\s+"),
        ("subprocess rm command", r"subprocess\.[^(]+\([^)]*[\"']rm[\"']"),
    ]
    audit_scripts = {
        "07_verify_experiment.py",
        "14_submission_readiness_check.py",
    }
    destructive_hits = []
    checked_scripts = []
    if not scripts_dir.exists():
        return {
            "checked_scripts": [],
            "destructive_patterns": [f"missing scripts directory: {scripts_dir}"],
            "audit_scripts_excluded": sorted(audit_scripts),
            "valid": False,
        }
    for path in sorted(scripts_dir.glob("*")):
        if not path.is_file() or path.name in audit_scripts:
            continue
        checked_scripts.append(str(path))
        text = path.read_text(errors="replace")
        for label, pattern in destructive_patterns:
            if re.search(pattern, text):
                destructive_hits.append(f"{path.name}: {label}")
    return {
        "checked_scripts": checked_scripts,
        "destructive_patterns": destructive_hits,
        "audit_scripts_excluded": sorted(audit_scripts),
        "valid": not destructive_hits,
    }


def item(name, status, evidence, required_for_strong_submission=True):
    return {
        "name": name,
        "status": status,
        "required_for_strong_submission": required_for_strong_submission,
        "evidence": evidence,
    }


def main(args):
    root = Path(args.root).resolve()
    checks = []

    multiseed_report = root / "results_multiseed" / "multiseed_report.json"
    multiseed = read_json(multiseed_report) if multiseed_report.exists() else {}
    n_multiseed_runs = multiseed.get("n_complete_seeds", 0)
    seed_family = multiseed.get("seed_family")
    checks.append(
        item(
            "Active multiseed retrieval runs",
            "pass" if n_multiseed_runs >= 3 else "missing",
            {
                "path": str(multiseed_report),
                "n_complete_seeds": n_multiseed_runs,
                "seed_family": seed_family,
            },
            required_for_strong_submission=False,
        )
    )

    independent = independent_memory_seed_dirs(root)
    complete_independent = [row for row in independent if row["status"] == "complete"]
    checks.append(
        item(
            "Independent memory-index seeds",
            "pass" if len(complete_independent) >= 3 else "missing",
            {
                "complete_count": len(complete_independent),
                "seed_dirs": independent,
                "note": "Fixed-memory query seeds do not satisfy this criterion.",
            },
        )
    )

    paired_dense = paired_dense_status(root)
    checks.append(
        item(
            "Small multi-seed Recall@5 improvement over dense retrieval",
            "pass" if paired_dense.get("excludes_zero") else "weak",
            paired_dense,
        )
    )

    gate_paired = gate_validation_paired_status(root)
    checks.append(
        item(
            "Held-out gate diagnostic paired improvement",
            "pass" if gate_paired.get("excludes_zero") else "weak",
            gate_paired,
            required_for_strong_submission=False,
        )
    )

    cross_seed_gate = cross_seed_top1_gate_status(root)
    checks.append(
        item(
            "Cross-seed top-1 gate diagnostic",
            "pass" if cross_seed_gate.get("excludes_zero") else "weak",
            cross_seed_gate,
            required_for_strong_submission=False,
        )
    )

    pass1 = pass1_status(root)
    checks.append(
        item(
            "Downstream Pass@1 or task-success evaluation",
            "pass" if pass1["has_pass1_results"] else "missing",
            pass1,
        )
    )

    pass1_context = pass1_context_status(root)
    checks.append(
        item(
            "Pass@1 retrieval context packets",
            "pass" if pass1_context["has_valid_contexts"] else "missing",
            pass1_context,
            required_for_strong_submission=False,
        )
    )

    harness_preflight = pass1_harness_preflight_status(root)
    checks.append(
        item(
            "Pass@1 harness execution preflight",
            "pass" if harness_preflight["ready_to_run_pass1"] else "blocked",
            harness_preflight,
            required_for_strong_submission=False,
        )
    )

    audit = human_audit_status(root)
    checks.append(
        item(
            "Human-audited query quality labels",
            "pass" if audit["valid"] else "missing",
            audit,
        )
    )

    blocked_next_actions = blocked_next_actions_status(root)
    checks.append(
        item(
            "Documented unblock steps",
            "pass" if blocked_next_actions["valid"] else "missing",
            blocked_next_actions,
            required_for_strong_submission=False,
        )
    )

    resume_helper = external_evidence_resume_helper_status(root)
    checks.append(
        item(
            "External evidence resume helper",
            "pass" if resume_helper["valid"] else "missing",
            resume_helper,
            required_for_strong_submission=False,
        )
    )

    release_helpers = release_helper_non_destructive_status(root)
    checks.append(
        item(
            "Non-destructive release helpers",
            "pass" if release_helpers["valid"] else "failed",
            release_helpers,
            required_for_strong_submission=False,
        )
    )

    project_deletion_safety = project_script_deletion_safety_status(root)
    checks.append(
        item(
            "Project script deletion safety",
            "pass" if project_deletion_safety["valid"] else "failed",
            project_deletion_safety,
            required_for_strong_submission=False,
        )
    )

    no_hallucinated_data = no_hallucinated_data_status(root)
    checks.append(
        item(
            "No hallucinated or simulated evidence in active paper package",
            "pass" if no_hallucinated_data["valid"] else "failed",
            no_hallucinated_data,
        )
    )

    token = measured_token_status(root)
    checks.append(
        item(
            "Measured token costs for all expansion ablations",
            "pass" if len(token["other_measured_expansion_methods"]) >= 4 else "weak",
            token,
            required_for_strong_submission=False,
        )
    )

    verification = root / "results_500_memory_seed42" / "verification_report.json"
    latex_build = latex_build_status(root)
    checks.append(
        item(
            "Verified LaTeX paper package",
            "pass"
            if latex_build["clean_build"] and verification.exists()
            else "missing",
            {**latex_build, "verification_report": str(verification)},
            required_for_strong_submission=False,
        )
    )

    conference_preview = conference_preview_status(root)
    checks.append(
        item(
            "Conference-style paper preview",
            "pass" if conference_preview["valid"] else "missing",
            conference_preview,
            required_for_strong_submission=False,
        )
    )

    paper_style = paper_style_status(root)
    checks.append(
        item(
            "Paper style and float-reference audit",
            "pass" if paper_style["valid"] else "missing",
            paper_style,
            required_for_strong_submission=False,
        )
    )

    figure_assets = figure_asset_status(root)
    checks.append(
        item(
            "Figure asset readability audit",
            "pass" if figure_assets["valid"] else "missing",
            figure_assets,
            required_for_strong_submission=False,
        )
    )

    paper_evidence_claims = paper_evidence_claim_status(root)
    checks.append(
        item(
            "Paper evidence-claim audit",
            "pass" if paper_evidence_claims["valid"] else "failed",
            paper_evidence_claims,
            required_for_strong_submission=False,
        )
    )

    compute_environment = compute_environment_status(root)
    checks.append(
        item(
            "Compute environment disclosure",
            "pass" if compute_environment["valid"] else "missing",
            compute_environment,
            required_for_strong_submission=False,
        )
    )

    llm_usage_disclosure = llm_usage_disclosure_status(root)
    checks.append(
        item(
            "LLM usage disclosure draft",
            "pass" if llm_usage_disclosure["valid"] else "missing",
            llm_usage_disclosure,
            required_for_strong_submission=False,
        )
    )

    blocking = [
        check
        for check in checks
        if check["required_for_strong_submission"] and check["status"] != "pass"
    ]
    report = {
        "strong_submission_ready": not blocking,
        "blocking_count": len(blocking),
        "checks": checks,
        "note": (
            "A false value means the current package may still be useful as a "
            "retrieval paper draft, but should not be presented as a complete "
            "top-conference empirical submission."
        ),
    }

    output = root / args.output
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--output", default="SUBMISSION_READINESS.json")
    raise SystemExit(main(parser.parse_args()))
