"""
Create human_audit_summary.json from real labeled human-audit rows.

This script does not create labels and does not modify the source audit packet.
It is intended to run after reviewers fill human_audit/labeled_human_audit_queries.csv.
The stricter verifier in scripts/18_verify_human_audit_labels.py must still pass
before any human-audit numbers are used in the paper.
"""

import argparse
import csv
import json
from pathlib import Path


ALLOWED_LABELS = {"yes", "no", "uncertain"}
REQUIRED_LABEL_FIELDS = [
    "is_query_clear",
    "does_target_answer_query",
    "is_query_too_specific_or_copied",
]
REQUIRED_BASE_FIELDS = ["query_id", "query", "target_episode_id", "target_excerpt"]


def read_csv(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def read_jsonl(path):
    rows = []
    with open(path) as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def normalize_label(value):
    return str(value or "").strip().lower()


def validate_rows(rows, source_rows, labeled_csv):
    failures = []
    if not rows:
        failures.append(f"no labeled rows found in {labeled_csv}")
        return failures

    source_by_id = {row.get("query_id"): row for row in source_rows}
    if len(source_by_id) != len(source_rows):
        failures.append("source human_audit_queries.jsonl contains duplicate query_id values")
    labeled_ids = [row.get("query_id") for row in rows]
    if len(labeled_ids) != len(set(labeled_ids)):
        failures.append(f"{labeled_csv}: duplicate query_id values")
    missing_from_labeled = sorted(set(source_by_id) - set(labeled_ids))
    if missing_from_labeled:
        failures.append(
            "source audit rows missing from labeled CSV: "
            f"{missing_from_labeled[:10]}"
        )
    extra_labeled = sorted(qid for qid in labeled_ids if qid not in source_by_id)
    if extra_labeled:
        failures.append(
            "labeled CSV contains rows not present in source packet: "
            f"{extra_labeled[:10]}"
        )

    for line_number, row in enumerate(rows, start=2):
        missing = [
            field
            for field in REQUIRED_BASE_FIELDS + REQUIRED_LABEL_FIELDS
            if field not in row
        ]
        if missing:
            failures.append(f"{labeled_csv}:{line_number}: missing fields {missing}")
            continue
        for field in REQUIRED_LABEL_FIELDS:
            value = normalize_label(row.get(field))
            if value not in ALLOWED_LABELS:
                failures.append(
                    f"{labeled_csv}:{line_number}: invalid {field}={row.get(field)!r}"
                )
        source = source_by_id.get(row.get("query_id"))
        if source:
            for field in REQUIRED_BASE_FIELDS:
                if str(row.get(field, "")) != str(source.get(field, "")):
                    failures.append(
                        f"{labeled_csv}:{line_number}: changed source field {field}"
                    )
    return failures


def label_counts(rows, field):
    counts = {label: 0 for label in sorted(ALLOWED_LABELS)}
    for row in rows:
        counts[normalize_label(row[field])] += 1
    total = len(rows)
    rates = {label: counts[label] / total if total else 0.0 for label in counts}
    return {"counts": counts, "rates": rates}


def summarize(rows):
    return {
        "artifact_type": "human_audit_summary",
        "is_experiment_evidence": True,
        "source_csv": "human_audit_queries.csv",
        "labeled_csv": "labeled_human_audit_queries.csv",
        "labeling_manifest": "human_audit_labeling_manifest.json",
        "n_rows": len(rows),
        "is_query_clear": label_counts(rows, "is_query_clear"),
        "does_target_answer_query": label_counts(rows, "does_target_answer_query"),
        "is_query_too_specific_or_copied": label_counts(
            rows, "is_query_too_specific_or_copied"
        ),
    }


def main(args):
    audit_dir = Path(args.audit_dir).resolve()
    source_jsonl = audit_dir / "human_audit_queries.jsonl"
    labeled_csv = audit_dir / "labeled_human_audit_queries.csv"
    output = Path(args.output).resolve() if args.output else audit_dir / "human_audit_summary.json"

    if not source_jsonl.exists():
        raise SystemExit(f"missing source audit JSONL: {source_jsonl}")
    if not labeled_csv.exists():
        raise SystemExit(
            f"missing labeled CSV: {labeled_csv}\n"
            "Create this file from human_audit_queries.csv with real reviewer labels first."
        )

    source_rows = read_jsonl(source_jsonl)
    rows = read_csv(labeled_csv)
    failures = validate_rows(rows, source_rows, labeled_csv)
    if failures:
        raise SystemExit("cannot summarize invalid labels:\n" + "\n".join(failures[:20]))

    summary = summarize(rows)
    output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"output": str(output), "n_rows": len(rows)}, indent=2))
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit_dir", default="/home/nlp-07/sqe_experiment/human_audit")
    parser.add_argument("--output", default="")
    raise SystemExit(main(parser.parse_args()))
