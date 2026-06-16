"""
Prepare a local GitHub code-release directory for the SQE paper package.

The script copies code, paper source, lightweight paper artifacts, configs, and
documentation into a reviewable directory. It does not create a git repository,
push to GitHub, upload data, or synthesize missing evidence.
"""

import argparse
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_INCLUDE_PATTERNS = [
    "README.md",
    "Makefile",
    "DATA_PROVENANCE.md",
    "NO_HALLUCINATED_DATA.md",
    "LLM_USAGE_DISCLOSURE.md",
    "CLAIM_AUDIT.md",
    "PASS1_HARNESS_AUDIT.md",
    "PASS1_RESULTS_SCHEMA.md",
    "BLOCKED_NEXT_ACTIONS.md",
    "HANDOFF_STATUS.md",
    "NEXT_EXPERIMENTS.md",
    "EXPERIMENT_STATUS.md",
    "OBJECTIVE_AUDIT.md",
    "OBJECTIVE_COMPLETION_AUDIT.md",
    "SUBMISSION_READINESS.json",
    "LATEX_BUILD_AUDIT.json",
    "CONFERENCE_PREVIEW_AUDIT.json",
    "PAPER_STYLE_AUDIT.json",
    "FIGURE_ASSET_AUDIT.json",
    "PAPER_EVIDENCE_CLAIM_AUDIT.json",
    "COMPUTE_ENVIRONMENT.json",
    "ARTIFACT_MANIFEST.json",
    "scripts/*.py",
    "scripts/*.sh",
    "paper/README.md",
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
    "pass1_evoagentbench_configs/*.yaml",
    "pass1_evoagentbench_configs/*.md",
    "human_audit/README.md",
    "human_audit/LABELING_PROTOCOL.md",
    "human_audit/REVIEWER_QUICKSTART.md",
    "human_audit/human_audit_manifest.json",
    "human_audit/human_audit_labeling_manifest.template.json",
    "human_audit/labeling_form_manifest.json",
    "human_audit/reviewer_packets/README.md",
    "human_audit/reviewer_packets/assignment_manifest.json",
    "human_audit/reviewer_packets/*.csv",
    "human_audit/reviewer_packets_verification.json",
]

OPTIONAL_SUMMARY_PATTERNS = [
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
    "results_multiseed/*.json",
    "results_gate_calibration/*.json",
    "results_tokenmeasured_500_seed42/*_summary.json",
]

FORBIDDEN_PARTS = {
    "__pycache__",
    ".git",
    "hf_dataset_release",
    "github_code_release",
}

FORBIDDEN_SUFFIXES = {
    ".pyc",
}


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
    out = []
    for path in sorted(set(paths)):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if any(part in FORBIDDEN_PARTS for part in rel.parts):
            continue
        if path.suffix in FORBIDDEN_SUFFIXES:
            continue
        out.append(path)
    return out


def copy_paths(root, output, paths):
    files = []
    for src in paths:
        rel = src.relative_to(root)
        dst = output / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        files.append(
            {
                "path": str(rel),
                "bytes": dst.stat().st_size,
                "sha256": sha256_file(dst),
                "source_path": str(src),
            }
        )
    return files


def write_release_readme(path, include_result_summaries):
    summaries = (
        "Lightweight result summaries and verification reports are included."
        if include_result_summaries
        else "Result summaries are not included; use the Hugging Face release package for data artifacts."
    )
    path.write_text(
        "\n".join(
            [
                "# SQE Paper Code Release",
                "",
                "This local directory is prepared for creating a public GitHub repository.",
                "It contains code, paper source, configuration files, and documentation.",
                "It also includes the optional two-column layout preview PDF and audit.",
                "",
                "It does not contain raw memory stores, detailed per-query JSONL result rows,",
                "human labels, or downstream Pass@1 results.",
                "",
                summaries,
                "",
                "Public repository URL placeholder: TODO: add GitHub URL.",
                "Hugging Face dataset URL placeholder: TODO: add Hugging Face dataset URL.",
                "",
                "Before publishing, inspect RELEASE_MANIFEST.json and replace the placeholders",
                "in the paper and documentation with the final public URLs.",
                "",
            ]
        )
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--output_dir", default=str(ROOT / "github_code_release"))
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Deprecated no-op retained for compatibility; never deletes output files.",
    )
    parser.add_argument("--include_result_summaries", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    output = Path(args.output_dir).resolve()
    if output == root:
        raise SystemExit("Refusing to use the project root as output_dir")
    if args.clean:
        print(
            "warning: --clean is deprecated and ignored; release packaging is non-destructive",
            file=sys.stderr,
        )
    output.mkdir(parents=True, exist_ok=True)

    patterns = list(DEFAULT_INCLUDE_PATTERNS)
    if args.include_result_summaries:
        patterns.extend(OPTIONAL_SUMMARY_PATTERNS)
    paths = collect_paths(root, patterns)
    files = copy_paths(root, output, paths)
    write_release_readme(output / "README.md", args.include_result_summaries)
    files.append(
        {
            "path": "README.md",
            "bytes": (output / "README.md").stat().st_size,
            "sha256": sha256_file(output / "README.md"),
            "source_path": "generated by scripts/34_prepare_github_code_release.py",
        }
    )
    manifest = {
        "artifact_type": "github_code_release",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "root": str(root),
        "output_dir": str(output),
        "include_result_summaries": bool(args.include_result_summaries),
        "contains_raw_memory_stores": False,
        "contains_detailed_query_rows": False,
        "contains_pass1_results": False,
        "contains_human_labels": False,
        "contains_synthetic_replacement_rows": False,
        "n_files": len(files),
        "files": sorted(files, key=lambda row: row["path"]),
    }
    (output / "RELEASE_MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    )
    print(json.dumps({"output_dir": str(output), "n_files": len(files)}, indent=2))


if __name__ == "__main__":
    main()
