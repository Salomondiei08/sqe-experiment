"""
Create pass1_summary.json from real downstream task-attempt rows.

This script does not run agents and does not invent task outcomes. It only
summarizes existing results_pass1/*_detailed.jsonl files. The stricter verifier
in scripts/17_verify_pass1_results.py must still pass before any Pass@1 numbers
are used in the paper.
"""

import argparse
import json
from pathlib import Path


REQUIRED_ROW_FIELDS = {"task_id", "method", "success", "runtime_seconds"}
DEFAULT_EXPECTED_METHODS = [
    "Dense-Only",
    "Always-Expand",
    "Random-Gated-Expansion",
    "Selective-QE",
]
DEFAULT_MIN_TASK_COUNT = 500


def read_jsonl(path):
    rows = []
    with open(path) as f:
        for line_number, line in enumerate(f, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            row["_source_file"] = str(path)
            row["_source_line"] = line_number
            rows.append(row)
    return rows


def validate_rows(rows, expected_methods=None, min_task_count=DEFAULT_MIN_TASK_COUNT):
    failures = []
    seen = set()
    for row in rows:
        source = f"{row.get('_source_file')}:{row.get('_source_line')}"
        missing = sorted(REQUIRED_ROW_FIELDS - set(row))
        if missing:
            failures.append(f"{source}: missing fields {missing}")
            continue
        pair = (row.get("task_id"), row.get("method"))
        if pair in seen:
            failures.append(f"{source}: duplicate task/method pair {pair}")
        seen.add(pair)
        if not isinstance(row.get("success"), bool):
            failures.append(f"{source}: success must be boolean")
        runtime = row.get("runtime_seconds")
        if not isinstance(runtime, (int, float)) or runtime < 0:
            failures.append(f"{source}: runtime_seconds must be non-negative number")
        if row.get("success") is False and not str(row.get("failure_reason", "")).strip():
            failures.append(f"{source}: failed row missing failure_reason")

    expected_methods = list(expected_methods or [])
    if expected_methods:
        observed_methods = {row.get("method") for row in rows}
        missing_methods = sorted(set(expected_methods) - observed_methods)
        if missing_methods:
            failures.append(f"missing expected Pass@1 methods: {missing_methods}")

        expected_task_ids = {
            row.get("task_id")
            for row in rows
            if row.get("task_id") and row.get("method") in expected_methods
        }
        if not expected_task_ids:
            failures.append("no task rows found for expected Pass@1 methods")
        if min_task_count and len(expected_task_ids) < min_task_count:
            failures.append(
                "task set is too small for paper Pass@1 evidence: "
                f"observed={len(expected_task_ids)} required_minimum={min_task_count}"
            )

        for method in expected_methods:
            method_task_ids = {
                row.get("task_id")
                for row in rows
                if row.get("method") == method and row.get("task_id")
            }
            missing_tasks = sorted(expected_task_ids - method_task_ids)
            extra_tasks = sorted(method_task_ids - expected_task_ids)
            if missing_tasks:
                failures.append(
                    f"method {method} missing task rows for expected task set: "
                    f"{missing_tasks[:10]}"
                )
            if extra_tasks:
                failures.append(
                    f"method {method} has task rows outside expected task set: "
                    f"{extra_tasks[:10]}"
                )
    return failures


def summarize(rows, expected_methods=None, min_task_count=DEFAULT_MIN_TASK_COUNT):
    methods = {}
    for row in rows:
        method = row["method"]
        entry = methods.setdefault(method, {"attempted": 0, "solved": 0})
        entry["attempted"] += 1
        if row["success"] is True:
            entry["solved"] += 1
    for entry in methods.values():
        attempted = entry["attempted"]
        entry["pass@1"] = entry["solved"] / attempted if attempted else 0.0
    task_ids = sorted({row["task_id"] for row in rows if row.get("task_id")})
    return {
        "methods": methods,
        "expected_methods": list(expected_methods or []),
        "task_set_size": len(task_ids),
        "minimum_task_count": min_task_count,
    }


def main(args):
    results_dir = Path(args.results_dir).resolve()
    output = Path(args.output).resolve() if args.output else results_dir / "pass1_summary.json"
    detailed_paths = sorted(results_dir.glob("*_detailed.jsonl"))
    if not detailed_paths:
        raise SystemExit(
            f"missing *_detailed.jsonl files under {results_dir}\n"
            "Run real downstream task attempts before creating a Pass@1 summary."
        )

    rows = []
    for path in detailed_paths:
        rows.extend(read_jsonl(path))
    if not rows:
        raise SystemExit(f"no task-attempt rows found under {results_dir}")

    expected_methods = args.expected_method or []
    if args.require_default_methods:
        expected_methods = DEFAULT_EXPECTED_METHODS

    failures = validate_rows(
        rows,
        expected_methods=expected_methods,
        min_task_count=args.min_task_count,
    )
    if failures:
        raise SystemExit("cannot summarize invalid Pass@1 rows:\n" + "\n".join(failures[:20]))

    summary = summarize(
        rows,
        expected_methods=expected_methods,
        min_task_count=args.min_task_count,
    )
    output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "output": str(output),
                "n_rows": len(rows),
                "expected_methods": expected_methods,
                "task_set_size": summary["task_set_size"],
                "minimum_task_count": args.min_task_count,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--results_dir", default="/home/nlp-07/sqe_experiment/results_pass1")
    parser.add_argument("--output", default="")
    parser.add_argument(
        "--expected_method",
        action="append",
        default=[],
        help="Require this method in detailed rows. Can be repeated.",
    )
    parser.add_argument(
        "--require_default_methods",
        action="store_true",
        default=True,
        help="Require Dense-Only, Always-Expand, Random-Gated-Expansion, and Selective-QE.",
    )
    parser.add_argument(
        "--no_require_default_methods",
        dest="require_default_methods",
        action="store_false",
        help="Only summarize methods present in the detailed rows.",
    )
    parser.add_argument(
        "--min_task_count",
        type=int,
        default=DEFAULT_MIN_TASK_COUNT,
        help=(
            "Minimum number of paired task IDs required before producing a "
            "Pass@1 summary. The default is the full SWE-bench Verified size "
            "used for paper evidence; smoke runs must lower this explicitly."
        ),
    )
    raise SystemExit(main(parser.parse_args()))
