"""
Prepare a human-audit packet for SQE evaluation queries.

The output contains real generated queries and their target memory excerpts, plus
empty reviewer fields. It does not create labels or paper results.
"""

import argparse
import csv
import json
import random
from pathlib import Path


def read_jsonl(path):
    rows = []
    with open(path) as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def main(args):
    eval_rows = read_jsonl(Path(args.eval_path))
    rng = random.Random(args.seed)
    sample = list(eval_rows)
    rng.shuffle(sample)
    sample = sample[: args.n]

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = out_dir / "human_audit_queries.jsonl"
    csv_path = out_dir / "human_audit_queries.csv"

    audit_rows = []
    for row in sample:
        target_text = row.get("target_text", "")
        audit_rows.append(
            {
                "query_id": row.get("query_id", ""),
                "query": row.get("query", ""),
                "target_episode_id": row.get("target_episode_id", ""),
                "target_excerpt": target_text[: args.excerpt_chars],
                "is_query_clear": "",
                "does_target_answer_query": "",
                "is_query_too_specific_or_copied": "",
                "reviewer_notes": "",
            }
        )

    with open(jsonl_path, "w") as f:
        for row in audit_rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    fieldnames = list(audit_rows[0]) if audit_rows else [
        "query_id",
        "query",
        "target_episode_id",
        "target_excerpt",
        "is_query_clear",
        "does_target_answer_query",
        "is_query_too_specific_or_copied",
        "reviewer_notes",
    ]
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(audit_rows)

    manifest = {
        "source_eval_path": str(Path(args.eval_path).resolve()),
        "n_source_queries": len(eval_rows),
        "n_audit_queries": len(audit_rows),
        "seed": args.seed,
        "excerpt_chars": args.excerpt_chars,
        "jsonl_path": str(jsonl_path.resolve()),
        "csv_path": str(csv_path.resolve()),
        "note": "Reviewer fields are intentionally blank; no human labels have been added.",
    }
    (out_dir / "human_audit_manifest.json").write_text(json.dumps(manifest, indent=2))
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--eval_path", default="data_500_memory_seed42/eval_pairs.jsonl")
    parser.add_argument("--output_dir", default="human_audit")
    parser.add_argument("--n", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--excerpt_chars", type=int, default=700)
    main(parser.parse_args())
