"""
Write checksums for active SQE paper artifacts.

The manifest is a reproducibility aid. It records file size and SHA256 for the
paper source, generated tables/figures, verification reports, and active result
summaries. It does not read or generate experimental metrics.
"""

import argparse
import hashlib
import json
from pathlib import Path


DEFAULT_PATTERNS = [
    "paper/main.tex",
    "paper/main.pdf",
    "paper/main_conference_preview.tex",
    "paper/main_conference_preview.pdf",
    "paper/references.bib",
    "paper/table_inventory.json",
    "paper/tables/*.tex",
    "paper/figures/*.png",
    "presentation/*.html",
    "presentation/*.md",
    "results_500_memory_seed42/*_summary.json",
    "results_500_memory_seed42/baselines_summary.json",
    "results_500_memory_seed42/full_report_v2.json",
    "results_500_memory_seed42/verification_report.json",
    "results_500_memory_seed43/*_summary.json",
    "results_500_memory_seed43/baselines_summary.json",
    "results_500_memory_seed43/verification_report.json",
    "results_500_memory_seed44/*_summary.json",
    "results_500_memory_seed44/baselines_summary.json",
    "results_500_memory_seed44/verification_report.json",
    "results_500_memory_seed45/*_summary.json",
    "results_500_memory_seed45/baselines_summary.json",
    "results_500_memory_seed45/verification_report.json",
    "results_500_memory_seed46/*_summary.json",
    "results_500_memory_seed46/baselines_summary.json",
    "results_500_memory_seed46/verification_report.json",
    "results_500_memory_seed47/*_summary.json",
    "results_500_memory_seed47/baselines_summary.json",
    "results_500_memory_seed47/verification_report.json",
    "results_500_memory_seed48/*_summary.json",
    "results_500_memory_seed48/baselines_summary.json",
    "results_500_memory_seed48/verification_report.json",
    "results_500_memory_seed49/*_summary.json",
    "results_500_memory_seed49/baselines_summary.json",
    "results_500_memory_seed49/verification_report.json",
    "results_500_query_seed43_memory_seed42/*_summary.json",
    "results_500_query_seed43_memory_seed42/baselines_summary.json",
    "results_500_query_seed43_memory_seed42/verification_report.json",
    "results_500_query_seed44_memory_seed42/*_summary.json",
    "results_500_query_seed44_memory_seed42/baselines_summary.json",
    "results_500_query_seed44_memory_seed42/verification_report.json",
    "results_multiseed/*.json",
    "results_gate_calibration/*.json",
    "results_tokenmeasured_500_seed42/*_summary.json",
    "SUBMISSION_READINESS.json",
    "LATEX_BUILD_AUDIT.json",
    "CONFERENCE_PREVIEW_AUDIT.json",
    "PAPER_STYLE_AUDIT.json",
    "FIGURE_ASSET_AUDIT.json",
    "PAPER_EVIDENCE_CLAIM_AUDIT.json",
    "COMPUTE_ENVIRONMENT.json",
    "BLOCKED_NEXT_ACTIONS.md",
    "MISSING_EVIDENCE_BLOCKERS.json",
    "HANDOFF_STATUS.md",
    "NEXT_EXPERIMENTS.md",
    "CLAIM_AUDIT.md",
    "NO_HALLUCINATED_DATA.md",
    "LLM_USAGE_DISCLOSURE.md",
    "PASS1_HARNESS_AUDIT.md",
    "PASS1_RESULTS_SCHEMA.md",
    "pass1_harness_preflight.json",
    "pass1_evoagentbench_configs/*.yaml",
    "pass1_evoagentbench_configs/*.md",
    "pass1_tasks/*.jsonl",
    "pass1_tasks/*.json",
    "pass1_contexts/*_contexts.jsonl",
    "pass1_contexts/*_manifest.json",
    "pass1_contexts/*_cache.json",
    "pass1_contexts/verification_report.json",
    "human_audit/*.md",
    "human_audit/human_audit_manifest.json",
    "human_audit/*.template.json",
    "human_audit/labeling_form.html",
    "human_audit/labeling_form_manifest.json",
    "human_audit/reviewer_packets/*.md",
    "human_audit/reviewer_packets/*.json",
    "human_audit/reviewer_packets/*.csv",
    "human_audit/reviewer_packets_verification.json",
    "scripts/*.py",
    "scripts/*.sh",
    "hf_dataset_release/README.md",
    "hf_dataset_release/release_manifest.json",
    "github_code_release/README.md",
    "github_code_release/RELEASE_MANIFEST.json",
    "README.md",
    "Makefile",
    "DATA_PROVENANCE.md",
    "EXPERIMENT_STATUS.md",
    "OBJECTIVE_AUDIT.md",
    "OBJECTIVE_COMPLETION_AUDIT.md",
    "PAPER_CHECKLIST.md",
]


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def collect_paths(root, patterns):
    paths = []
    for pattern in patterns:
        paths.extend(root.glob(pattern))
    return sorted({path for path in paths if path.is_file()})


def main(args):
    root = Path(args.root).resolve()
    output = root / args.output
    paths = collect_paths(root, DEFAULT_PATTERNS)
    files = []
    for path in paths:
        stat = path.stat()
        files.append(
            {
                "path": str(path.relative_to(root)),
                "bytes": stat.st_size,
                "sha256": sha256_file(path),
            }
        )
    manifest = {
        "root": str(root),
        "n_files": len(files),
        "note": (
            "Checksums for active paper artifacts and result summaries. This "
            "manifest is not a source of metrics."
        ),
        "files": files,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"output": str(output), "n_files": len(files)}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default="/home/nlp-07/sqe_experiment")
    parser.add_argument("--output", default="ARTIFACT_MANIFEST.json")
    main(parser.parse_args())
