"""
Verify human-audit label artifacts for the SQE retrieval benchmark.

This script validates labels supplied by reviewers. It does not create labels.
It recomputes summary rates from labeled_human_audit_queries.csv and compares
them against human_audit_summary.json.
"""

import argparse
import csv
import json
from datetime import datetime
from pathlib import Path


ALLOWED_LABELS = {"yes", "no", "uncertain"}
REQUIRED_LABEL_FIELDS = [
    "is_query_clear",
    "does_target_answer_query",
    "is_query_too_specific_or_copied",
]
REQUIRED_BASE_FIELDS = ["query_id", "query", "target_episode_id", "target_excerpt"]
REQUIRED_MANIFEST_FIELDS = [
    "reviewers",
    "label_set",
    "labeling_date",
    "n_labeled_rows",
    "source_csv",
    "labeled_csv",
    "protocol_notes",
    "adjudication_notes",
]


def read_json(path):
    with open(path) as f:
        return json.load(f)


def read_jsonl(path):
    rows = []
    with open(path) as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def read_csv(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def is_yyyy_mm_dd(value):
    text = str(value or "").strip()
    if len(text) != 10:
        return False
    try:
        parsed = datetime.strptime(text, "%Y-%m-%d")
    except ValueError:
        return False
    return parsed.strftime("%Y-%m-%d") == text


def label_counts(rows, field):
    counts = {label: 0 for label in sorted(ALLOWED_LABELS)}
    for row in rows:
        counts[row[field].strip().lower()] += 1
    total = len(rows)
    rates = {label: counts[label] / total if total else 0.0 for label in counts}
    return {"counts": counts, "rates": rates}


def recompute_summary(rows):
    return {
        "n_rows": len(rows),
        "is_query_clear": label_counts(rows, "is_query_clear"),
        "does_target_answer_query": label_counts(rows, "does_target_answer_query"),
        "is_query_too_specific_or_copied": label_counts(
            rows, "is_query_too_specific_or_copied"
        ),
    }


def compare_summary(expected, actual, failures):
    if actual.get("n_rows") != expected["n_rows"]:
        failures.append(
            f"summary n_rows={actual.get('n_rows')} does not match "
            f"recomputed {expected['n_rows']}"
        )
    for field in REQUIRED_LABEL_FIELDS:
        actual_field = actual.get(field, {})
        for label, count in expected[field]["counts"].items():
            actual_count = actual_field.get("counts", {}).get(label)
            if actual_count != count:
                failures.append(
                    f"summary {field}.counts.{label}={actual_count} "
                    f"does not match recomputed {count}"
                )
        for label, rate in expected[field]["rates"].items():
            actual_rate = actual_field.get("rates", {}).get(label)
            try:
                actual_rate = float(actual_rate)
            except (TypeError, ValueError):
                failures.append(f"summary {field}.rates.{label} is not numeric")
                continue
            if abs(actual_rate - rate) > 1e-12:
                failures.append(
                    f"summary {field}.rates.{label}={actual_rate} "
                    f"does not match recomputed {rate}"
                )


def verify_human_audit(audit_dir):
    audit_dir = Path(audit_dir).resolve()
    failures = []
    warnings = []

    unlabeled_jsonl = audit_dir / "human_audit_queries.jsonl"
    labeled_csv = audit_dir / "labeled_human_audit_queries.csv"
    labeling_manifest = audit_dir / "human_audit_labeling_manifest.json"
    summary_path = audit_dir / "human_audit_summary.json"

    for path, description in [
        (unlabeled_jsonl, "source unlabeled JSONL"),
        (labeled_csv, "labeled CSV"),
        (labeling_manifest, "labeling manifest"),
        (summary_path, "human-audit summary"),
    ]:
        if not path.exists():
            failures.append(f"missing {description}: {path}")

    source_rows = read_jsonl(unlabeled_jsonl) if unlabeled_jsonl.exists() else []
    labeled_rows = read_csv(labeled_csv) if labeled_csv.exists() else []
    manifest = read_json(labeling_manifest) if labeling_manifest.exists() else {}
    summary = read_json(summary_path) if summary_path.exists() else {}

    source_by_id = {row.get("query_id"): row for row in source_rows}
    if len(source_by_id) != len(source_rows):
        failures.append("source human_audit_queries.jsonl contains duplicate query_id values")

    labeled_ids = [row.get("query_id") for row in labeled_rows]
    if len(labeled_ids) != len(set(labeled_ids)):
        failures.append("labeled_human_audit_queries.csv contains duplicate query_id values")
    missing_from_source = sorted(qid for qid in labeled_ids if qid not in source_by_id)
    if missing_from_source:
        failures.append(
            "labeled rows not present in source audit packet: "
            f"{missing_from_source[:10]}"
        )
    missing_labels = sorted(set(source_by_id) - set(labeled_ids))
    if missing_labels:
        failures.append(
            "source audit rows missing from labeled CSV: "
            f"{missing_labels[:10]}"
        )

    row_field_failures = []
    invalid_label_rows = []
    changed_source_rows = []
    for index, row in enumerate(labeled_rows, start=2):
        missing_fields = sorted(
            set(REQUIRED_BASE_FIELDS + REQUIRED_LABEL_FIELDS) - set(row)
        )
        if missing_fields:
            row_field_failures.append({"csv_line": index, "missing": missing_fields})
            continue
        for field in REQUIRED_LABEL_FIELDS:
            value = row.get(field, "").strip().lower()
            if value not in ALLOWED_LABELS:
                invalid_label_rows.append(
                    {
                        "csv_line": index,
                        "query_id": row.get("query_id"),
                        "field": field,
                        "value": row.get(field),
                    }
                )
        source = source_by_id.get(row.get("query_id"))
        if source:
            for field in REQUIRED_BASE_FIELDS:
                if str(row.get(field, "")) != str(source.get(field, "")):
                    changed_source_rows.append(
                        {
                            "csv_line": index,
                            "query_id": row.get("query_id"),
                            "field": field,
                        }
                    )

    if row_field_failures:
        failures.append(f"labeled rows missing required fields: {row_field_failures[:10]}")
    if invalid_label_rows:
        failures.append(f"invalid label values: {invalid_label_rows[:10]}")
    if changed_source_rows:
        failures.append(
            "labeled CSV changed source query/target fields: "
            f"{changed_source_rows[:10]}"
        )

    missing_manifest_fields = [
        field for field in REQUIRED_MANIFEST_FIELDS if field not in manifest
    ]
    if missing_manifest_fields:
        failures.append(
            "human_audit_labeling_manifest.json missing required fields: "
            f"{missing_manifest_fields}"
        )

    reviewers = manifest.get("reviewers")
    if not isinstance(reviewers, list) or not reviewers:
        failures.append("human_audit_labeling_manifest.json must list reviewers")
    elif len(reviewers) < 2:
        failures.append("human_audit_labeling_manifest.json must list at least two reviewers")
    elif any("TODO" in str(value) or not str(value).strip() for value in reviewers):
        failures.append("human_audit_labeling_manifest.json reviewers contains TODO/blank values")

    if not manifest.get("label_set"):
        failures.append("human_audit_labeling_manifest.json must document label_set")
    elif sorted(manifest.get("label_set")) != sorted(ALLOWED_LABELS):
        failures.append(
            "human_audit_labeling_manifest.json label_set must be "
            f"{sorted(ALLOWED_LABELS)}"
        )

    labeling_date = str(manifest.get("labeling_date", "")).strip()
    if not labeling_date or "TODO" in labeling_date:
        failures.append("human_audit_labeling_manifest.json must record labeling_date")
    elif not is_yyyy_mm_dd(labeling_date):
        failures.append(
            "human_audit_labeling_manifest.json labeling_date must use YYYY-MM-DD"
        )
    if manifest.get("source_csv") != "human_audit_queries.csv":
        failures.append(
            "human_audit_labeling_manifest.json source_csv must be "
            "human_audit_queries.csv"
        )
    if manifest.get("labeled_csv") != "labeled_human_audit_queries.csv":
        failures.append(
            "human_audit_labeling_manifest.json labeled_csv must be "
            "labeled_human_audit_queries.csv"
        )
    protocol_notes = manifest.get("protocol_notes")
    if not isinstance(protocol_notes, list) or not protocol_notes:
        failures.append("human_audit_labeling_manifest.json must document protocol_notes")
    elif any("TODO" in str(value) or not str(value).strip() for value in protocol_notes):
        failures.append(
            "human_audit_labeling_manifest.json protocol_notes contains TODO/blank values"
        )
    adjudication_notes = manifest.get("adjudication_notes")
    if not isinstance(adjudication_notes, list) or not adjudication_notes:
        failures.append("human_audit_labeling_manifest.json must document adjudication_notes")
    elif any("TODO" in str(value) or not str(value).strip() for value in adjudication_notes):
        failures.append(
            "human_audit_labeling_manifest.json adjudication_notes contains TODO/blank values"
        )
    if manifest.get("n_labeled_rows") != len(labeled_rows):
        failures.append(
            "human_audit_labeling_manifest.json n_labeled_rows does not match "
            f"CSV rows: {manifest.get('n_labeled_rows')} vs {len(labeled_rows)}"
        )

    recomputed = recompute_summary(labeled_rows) if labeled_rows else {
        "n_rows": 0,
        "is_query_clear": {"counts": {}, "rates": {}},
        "does_target_answer_query": {"counts": {}, "rates": {}},
        "is_query_too_specific_or_copied": {"counts": {}, "rates": {}},
    }
    if summary_path.exists():
        if summary.get("artifact_type") != "human_audit_summary":
            failures.append("human_audit_summary.json artifact_type must be human_audit_summary")
        if summary.get("is_experiment_evidence") is not True:
            failures.append("human_audit_summary.json must be marked as experiment evidence")
        if summary.get("source_csv") != "human_audit_queries.csv":
            failures.append("human_audit_summary.json source_csv must be human_audit_queries.csv")
        if summary.get("labeled_csv") != "labeled_human_audit_queries.csv":
            failures.append(
                "human_audit_summary.json labeled_csv must be labeled_human_audit_queries.csv"
            )
        if summary.get("labeling_manifest") != "human_audit_labeling_manifest.json":
            failures.append(
                "human_audit_summary.json labeling_manifest must be "
                "human_audit_labeling_manifest.json"
            )
        compare_summary(recomputed, summary, failures)

    report = {
        "audit_dir": str(audit_dir),
        "source_jsonl": str(unlabeled_jsonl),
        "labeled_csv": str(labeled_csv),
        "labeling_manifest": str(labeling_manifest),
        "summary_path": str(summary_path),
        "n_source_rows": len(source_rows),
        "n_labeled_rows": len(labeled_rows),
        "recomputed_summary": recomputed,
        "warnings": warnings,
        "failures": failures,
    }
    return report


def main(args):
    report = verify_human_audit(args.audit_dir)
    text = json.dumps(report, indent=2) + "\n"
    if args.output:
        Path(args.output).resolve().write_text(text)
    print(text, end="")
    return 1 if report["failures"] else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit_dir", default="/home/nlp-07/sqe_experiment/human_audit")
    parser.add_argument("--output", default="")
    raise SystemExit(main(parser.parse_args()))
