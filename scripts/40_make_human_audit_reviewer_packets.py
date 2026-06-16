"""
Create reviewer-specific human-audit packets without creating labels.

The generated files are handoff aids only. They copy the source audit rows and
leave all reviewer label fields blank. They must not be reported as
human-audit evidence until reviewers fill labels, an adjudicated labeled CSV is
created, and scripts/18_verify_human_audit_labels.py passes.
"""

import argparse
import csv
import json
from pathlib import Path


REVIEWER_FIELDS = [
    "is_query_clear",
    "does_target_answer_query",
    "is_query_too_specific_or_copied",
    "reviewer_notes",
]


def read_csv(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path, rows, fieldnames):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def blank_reviewer_fields(row):
    out = dict(row)
    for field in REVIEWER_FIELDS:
        out[field] = ""
    return out


def reviewer_rows(rows, mode, reviewer_index, n_reviewers):
    if mode == "full":
        return [blank_reviewer_fields(row) for row in rows]
    if mode == "split":
        return [
            blank_reviewer_fields(row)
            for index, row in enumerate(rows)
            if index % n_reviewers == reviewer_index
        ]
    raise ValueError(f"unknown assignment mode: {mode}")


def main(args):
    audit_dir = Path(args.audit_dir).resolve()
    source_csv = audit_dir / "human_audit_queries.csv"
    output_dir = Path(args.output_dir).resolve() if args.output_dir else audit_dir / "reviewer_packets"
    reviewers = [name.strip() for name in args.reviewers.split(",") if name.strip()]
    if not reviewers:
        raise SystemExit("at least one reviewer ID is required")
    if args.mode not in {"full", "split"}:
        raise SystemExit("--mode must be 'full' or 'split'")
    if not source_csv.exists():
        raise SystemExit(f"missing source audit CSV: {source_csv}")

    rows = read_csv(source_csv)
    if not rows:
        raise SystemExit(f"source audit CSV has no rows: {source_csv}")
    fieldnames = list(rows[0].keys())
    for field in REVIEWER_FIELDS:
        if field not in fieldnames:
            fieldnames.append(field)

    packet_rows = []
    for reviewer_index, reviewer in enumerate(reviewers):
        out_rows = reviewer_rows(rows, args.mode, reviewer_index, len(reviewers))
        packet_name = f"{reviewer}.csv"
        packet_path = output_dir / packet_name
        write_csv(packet_path, out_rows, fieldnames)
        packet_rows.append(
            {
                "reviewer": reviewer,
                "path": str(packet_path.relative_to(audit_dir)),
                "n_rows": len(out_rows),
                "contains_labels": False,
            }
        )

    manifest = {
        "artifact_type": "human_audit_reviewer_packets",
        "is_experiment_evidence": False,
        "source_csv": "human_audit_queries.csv",
        "assignment_mode": args.mode,
        "reviewer_packets": packet_rows,
        "required_final_outputs": [
            "labeled_human_audit_queries.csv",
            "human_audit_labeling_manifest.json",
            "human_audit_summary.json",
        ],
        "note": (
            "Reviewer packets are unlabeled handoff files. They do not satisfy "
            "the human-audit evidence requirement."
        ),
    }
    manifest_path = output_dir / "assignment_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")

    readme = output_dir / "README.md"
    readme.write_text(
        "# Human Audit Reviewer Packets\n\n"
        "These files are documentation-only handoff packets. They copy source "
        "audit rows and leave reviewer label fields blank.\n\n"
        "Do not cite these files as human-audit evidence. Human-audit numbers "
        "can be reported only after `labeled_human_audit_queries.csv`, "
        "`human_audit_labeling_manifest.json`, and `human_audit_summary.json` "
        "exist and `scripts/18_verify_human_audit_labels.py` reports no "
        "failures.\n",
    )

    print(
        json.dumps(
            {
                "output_dir": str(output_dir),
                "assignment_mode": args.mode,
                "n_reviewers": len(reviewers),
                "n_source_rows": len(rows),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit_dir", default="/home/nlp-07/sqe_experiment/human_audit")
    parser.add_argument("--output_dir", default="")
    parser.add_argument("--reviewers", default="reviewer_a,reviewer_b")
    parser.add_argument(
        "--mode",
        default="full",
        help="'full' gives every reviewer all rows; 'split' partitions rows by reviewer.",
    )
    raise SystemExit(main(parser.parse_args()))
