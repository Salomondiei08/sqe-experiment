"""
Verify human-audit reviewer packets are non-evidence handoff files.

Reviewer packets should copy source audit rows and leave reviewer label fields
blank. This script fails if packet rows alter source fields or contain labels.
It does not validate final human labels; use scripts/18_verify_human_audit_labels.py
for that after real review is complete.
"""

import argparse
import csv
import json
from pathlib import Path


BASE_FIELDS = ["query_id", "query", "target_episode_id", "target_excerpt"]
LABEL_FIELDS = [
    "is_query_clear",
    "does_target_answer_query",
    "is_query_too_specific_or_copied",
]


def read_csv(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def read_json(path):
    with open(path) as f:
        return json.load(f)


def verify_packets(audit_dir):
    audit_dir = Path(audit_dir).resolve()
    source_csv = audit_dir / "human_audit_queries.csv"
    packet_dir = audit_dir / "reviewer_packets"
    manifest_path = packet_dir / "assignment_manifest.json"
    failures = []
    warnings = []

    if not source_csv.exists():
        failures.append(f"missing source audit CSV: {source_csv}")
        source_rows = []
    else:
        source_rows = read_csv(source_csv)
    source_by_id = {row.get("query_id"): row for row in source_rows}

    if not packet_dir.exists():
        failures.append(f"missing reviewer packet directory: {packet_dir}")
    if not manifest_path.exists():
        failures.append(f"missing reviewer packet manifest: {manifest_path}")
        manifest = {}
    else:
        manifest = read_json(manifest_path)

    if manifest.get("is_experiment_evidence") is not False:
        failures.append("reviewer packet manifest must set is_experiment_evidence=false")

    packets = manifest.get("reviewer_packets", [])
    if not isinstance(packets, list) or not packets:
        failures.append("reviewer packet manifest must list reviewer_packets")
        packets = []

    packet_reports = []
    for packet in packets:
        rel_path = packet.get("path")
        if not rel_path:
            failures.append(f"reviewer packet entry missing path: {packet}")
            continue
        path = audit_dir / rel_path
        if not path.exists():
            failures.append(f"reviewer packet CSV missing: {path}")
            continue
        rows = read_csv(path)
        changed_source_rows = []
        filled_label_rows = []
        unknown_ids = []
        for line_number, row in enumerate(rows, start=2):
            source = source_by_id.get(row.get("query_id"))
            if source is None:
                unknown_ids.append(row.get("query_id"))
                continue
            for field in BASE_FIELDS:
                if str(row.get(field, "")) != str(source.get(field, "")):
                    changed_source_rows.append(
                        {
                            "csv_line": line_number,
                            "query_id": row.get("query_id"),
                            "field": field,
                        }
                    )
            filled = [
                field
                for field in LABEL_FIELDS
                if str(row.get(field, "")).strip()
            ]
            if filled:
                filled_label_rows.append(
                    {
                        "csv_line": line_number,
                        "query_id": row.get("query_id"),
                        "fields": filled,
                    }
                )
        if unknown_ids:
            failures.append(
                f"{path.name} contains query IDs not in source packet: {unknown_ids[:10]}"
            )
        if changed_source_rows:
            failures.append(
                f"{path.name} changed source fields: {changed_source_rows[:10]}"
            )
        if filled_label_rows:
            failures.append(
                f"{path.name} contains filled label fields and is no longer a blank packet: "
                f"{filled_label_rows[:10]}"
            )
        if packet.get("contains_labels") is not False:
            failures.append(f"{path.name} manifest entry must set contains_labels=false")
        if packet.get("n_rows") != len(rows):
            failures.append(
                f"{path.name} manifest n_rows={packet.get('n_rows')} does not match CSV rows {len(rows)}"
            )
        packet_reports.append(
            {
                "path": str(path),
                "n_rows": len(rows),
                "contains_filled_labels": bool(filled_label_rows),
            }
        )

    report = {
        "audit_dir": str(audit_dir),
        "source_csv": str(source_csv),
        "packet_dir": str(packet_dir),
        "manifest": str(manifest_path),
        "is_experiment_evidence": False,
        "packet_reports": packet_reports,
        "warnings": warnings,
        "failures": failures,
    }
    return report


def main(args):
    report = verify_packets(args.audit_dir)
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text)
    print(text, end="")
    return 1 if report["failures"] else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit_dir", default="/home/nlp-07/sqe_experiment/human_audit")
    parser.add_argument("--output", default="")
    raise SystemExit(main(parser.parse_args()))
