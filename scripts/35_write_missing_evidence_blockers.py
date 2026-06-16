"""
Write a machine-readable summary of missing evidence blockers.

This file is documentation support only. It records what real artifacts must
exist before the paper can make downstream task-success or human-validation
claims.
"""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_json(path):
    with open(path) as f:
        return json.load(f)


def readiness_evidence(readiness, check_name):
    for check in readiness.get("checks", []):
        if check.get("name") == check_name:
            return check.get("evidence", {})
    return {}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--output", default="MISSING_EVIDENCE_BLOCKERS.json")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    readiness_path = root / "SUBMISSION_READINESS.json"
    preflight_path = root / "pass1_harness_preflight.json"
    human_report_path = root / "human_audit" / "verification_report.json"

    readiness = read_json(readiness_path) if readiness_path.exists() else {}
    preflight = read_json(preflight_path) if preflight_path.exists() else {}
    human_report = read_json(human_report_path) if human_report_path.exists() else {}
    pass1_preflight_readiness = readiness_evidence(readiness, "Pass@1 harness execution preflight")

    blockers = {
        "artifact_type": "missing_evidence_blockers",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "is_experiment_evidence": False,
        "strong_submission_ready": readiness.get("strong_submission_ready", False),
        "blocking_count": readiness.get("blocking_count"),
        "blockers": [
            {
                "name": "Downstream Pass@1 or task-success evaluation",
                "status": "missing",
                "reason": "No verified results_pass1 manifest, detailed rows, or summary exist.",
                "current_preflight": {
                    "path": str(preflight_path),
                    "checked_at_utc": preflight.get("checked_at_utc"),
                    "ready_to_run_pass1": preflight.get("ready_to_run_pass1"),
                    "blockers": preflight.get("blockers", []),
                    "docker_socket_group": pass1_preflight_readiness.get("docker_socket_group"),
                    "docker_user_group_names": pass1_preflight_readiness.get("docker_user_group_names", []),
                    "docker_user_in_socket_group": pass1_preflight_readiness.get("docker_user_in_socket_group"),
                    "docker_user_listed_in_socket_group": pass1_preflight_readiness.get(
                        "docker_user_listed_in_socket_group"
                    ),
                },
                "admin_unblock_command": "sudo usermod -aG docker nlp-07",
                "post_admin_checks": [
                    "start a new login session",
                    "docker ps",
                    "python3 scripts/26_check_pass1_harness_readiness.py --output pass1_harness_preflight.json",
                ],
                "must_create_real_files": [
                    "results_pass1/manifest.json",
                    "results_pass1/pass1_summary.json",
                    "results_pass1/*_detailed.jsonl",
                ],
                "minimum_methods": [
                    "Dense-Only",
                    "Always-Expand",
                    "Random-Gated-Expansion",
                    "Selective-QE",
                ],
                "verification_commands": [
                    "python3 scripts/21_summarize_pass1_results.py --results_dir results_pass1",
                    "python3 scripts/17_verify_pass1_results.py --results_dir results_pass1",
                    "python3 scripts/14_submission_readiness_check.py --output SUBMISSION_READINESS.json",
                ],
                "do_not_use_as_evidence": [
                    "pass1_harness_preflight.json",
                    "PASS1_RESULTS_SCHEMA.md",
                    "pass1_contexts/*.jsonl",
                    "pass1_evoagentbench_configs/*.yaml",
                ],
            },
            {
                "name": "Human-audited query quality labels",
                "status": "missing",
                "reason": "The audit packet exists, but no completed reviewer labels exist.",
                "current_verification": {
                    "path": str(human_report_path),
                    "n_labeled_rows": human_report.get("n_labeled_rows", 0),
                    "failures": human_report.get("failures", []),
                },
                "must_create_real_files": [
                    "human_audit/labeled_human_audit_queries.csv",
                    "human_audit/human_audit_labeling_manifest.json",
                    "human_audit/human_audit_summary.json",
                ],
                "verification_commands": [
                    "python3 scripts/20_summarize_human_audit_labels.py --audit_dir human_audit",
                    "python3 scripts/18_verify_human_audit_labels.py --audit_dir human_audit --output human_audit/verification_report.json",
                    "python3 scripts/14_submission_readiness_check.py --output SUBMISSION_READINESS.json",
                ],
                "do_not_use_as_evidence": [
                    "human_audit/human_audit_queries.csv",
                    "human_audit/human_audit_queries.jsonl",
                    "human_audit/human_audit_labeling_manifest.template.json",
                    "human_audit/labeling_form.html",
                ],
            },
        ],
        "non_negotiable_rule": (
            "Do not create placeholder Pass@1 rows, placeholder labels, fabricated "
            "metrics, or simulated results. Missing evidence must remain marked "
            "as missing until real artifacts exist and verifiers pass."
        ),
    }

    output = root / args.output
    output.write_text(json.dumps(blockers, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"output": str(output), "blocking_count": len(blockers["blockers"])}, indent=2))


if __name__ == "__main__":
    main()
