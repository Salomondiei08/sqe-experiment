"""
Verify downstream Pass@1/task-success result artifacts.

This script is intentionally read-only with respect to experiment evidence. It
does not run agents and does not invent missing values. It checks that detailed
task rows exist, recomputes method-level Pass@1 from those rows, and compares the
recomputed values against pass1_summary.json.
"""

import argparse
import json
from pathlib import Path


REQUIRED_ROW_FIELDS = {"task_id", "method", "success", "runtime_seconds"}
REQUIRED_SUMMARY_FIELDS = {"attempted", "solved", "pass@1"}
DEFAULT_EXPECTED_METHODS = [
    "Dense-Only",
    "Always-Expand",
    "Random-Gated-Expansion",
    "Selective-QE",
]
DEFAULT_MIN_TASK_COUNT = 500


def read_json(path):
    with open(path) as f:
        return json.load(f)


def read_jsonl(path):
    rows = []
    with open(path) as f:
        for line_number, line in enumerate(f, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: invalid JSON: {exc}") from exc
            row["_source_file"] = str(path)
            row["_source_line"] = line_number
            rows.append(row)
    return rows


def recompute_methods(rows):
    methods = {}
    task_method_pairs = set()
    duplicate_pairs = []
    for row in rows:
        method = row.get("method")
        task_id = row.get("task_id")
        pair = (task_id, method)
        if pair in task_method_pairs:
            duplicate_pairs.append(
                {
                    "task_id": task_id,
                    "method": method,
                    "source_file": row.get("_source_file"),
                    "source_line": row.get("_source_line"),
                }
            )
        task_method_pairs.add(pair)
        entry = methods.setdefault(method, {"attempted": 0, "solved": 0})
        entry["attempted"] += 1
        if row.get("success") is True:
            entry["solved"] += 1
    for entry in methods.values():
        attempted = entry["attempted"]
        entry["pass@1"] = entry["solved"] / attempted if attempted else 0.0
    return methods, duplicate_pairs


def verify_pass1(results_dir, expected_methods=None, min_task_count=DEFAULT_MIN_TASK_COUNT):
    results_dir = Path(results_dir).resolve()
    failures = []
    warnings = []
    expected_methods = list(expected_methods or [])

    manifest_path = results_dir / "manifest.json"
    summary_path = results_dir / "pass1_summary.json"
    detailed_paths = sorted(results_dir.glob("*_detailed.jsonl"))

    if not results_dir.exists():
        failures.append(f"results directory does not exist: {results_dir}")
    if not manifest_path.exists():
        failures.append(f"missing manifest.json: {manifest_path}")
    if not summary_path.exists():
        failures.append(f"missing pass1_summary.json: {summary_path}")
    if not detailed_paths:
        failures.append(f"missing *_detailed.jsonl files under {results_dir}")

    manifest = read_json(manifest_path) if manifest_path.exists() else {}
    summary = read_json(summary_path) if summary_path.exists() else {}

    rows = []
    for path in detailed_paths:
        try:
            rows.extend(read_jsonl(path))
        except ValueError as exc:
            failures.append(str(exc))
    if not rows:
        failures.append("no detailed task rows found")

    missing_field_rows = []
    invalid_success_rows = []
    invalid_runtime_rows = []
    missing_failure_reason_rows = []
    for row in rows:
        missing = sorted(REQUIRED_ROW_FIELDS - set(row))
        if missing:
            missing_field_rows.append(
                {
                    "source_file": row.get("_source_file"),
                    "source_line": row.get("_source_line"),
                    "missing": missing,
                }
            )
        if "success" in row and not isinstance(row.get("success"), bool):
            invalid_success_rows.append(
                {
                    "source_file": row.get("_source_file"),
                    "source_line": row.get("_source_line"),
                    "success": row.get("success"),
                }
            )
        if "runtime_seconds" in row:
            runtime = row.get("runtime_seconds")
            if not isinstance(runtime, (int, float)) or runtime < 0:
                invalid_runtime_rows.append(
                    {
                        "source_file": row.get("_source_file"),
                        "source_line": row.get("_source_line"),
                        "runtime_seconds": runtime,
                    }
                )
        if row.get("success") is False and not str(row.get("failure_reason", "")).strip():
            missing_failure_reason_rows.append(
                {
                    "source_file": row.get("_source_file"),
                    "source_line": row.get("_source_line"),
                    "task_id": row.get("task_id"),
                    "method": row.get("method"),
                }
            )

    if missing_field_rows:
        failures.append(f"rows missing required fields: {missing_field_rows[:10]}")
    if invalid_success_rows:
        failures.append(f"rows have non-boolean success values: {invalid_success_rows[:10]}")
    if invalid_runtime_rows:
        failures.append(f"rows have invalid runtime_seconds values: {invalid_runtime_rows[:10]}")
    if missing_failure_reason_rows:
        failures.append(
            "unsuccessful rows missing failure_reason: "
            f"{missing_failure_reason_rows[:10]}"
        )

    recomputed, duplicate_pairs = recompute_methods(rows)
    if duplicate_pairs:
        failures.append(f"duplicate task_id/method rows: {duplicate_pairs[:10]}")

    if expected_methods:
        observed_methods = set(recomputed)
        missing_methods = sorted(set(expected_methods) - observed_methods)
        if missing_methods:
            failures.append(f"missing expected Pass@1 methods: {missing_methods}")
        observed_task_ids = {
            row.get("task_id")
            for row in rows
            if row.get("task_id") and row.get("method") in expected_methods
        }
        if min_task_count and len(observed_task_ids) < min_task_count:
            failures.append(
                "task set is too small for paper Pass@1 evidence: "
                f"observed={len(observed_task_ids)} required_minimum={min_task_count}"
            )
        for method in expected_methods:
            method_task_ids = {
                row.get("task_id")
                for row in rows
                if row.get("method") == method and row.get("task_id")
            }
            missing_tasks = sorted(observed_task_ids - method_task_ids)
            extra_tasks = sorted(method_task_ids - observed_task_ids)
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

    summary_methods = summary.get("methods", {})
    if summary_path.exists() and not isinstance(summary_methods, dict):
        failures.append("pass1_summary.json must contain an object field named methods")
        summary_methods = {}

    for method, values in recomputed.items():
        summary_row = summary_methods.get(method)
        if not summary_row:
            failures.append(f"pass1_summary.json missing method: {method}")
            continue
        missing_summary_fields = sorted(REQUIRED_SUMMARY_FIELDS - set(summary_row))
        if missing_summary_fields:
            failures.append(
                f"pass1_summary.json method {method} missing fields: "
                f"{missing_summary_fields}"
            )
            continue
        for key in ["attempted", "solved"]:
            if summary_row.get(key) != values[key]:
                failures.append(
                    f"summary mismatch for {method} {key}: "
                    f"summary={summary_row.get(key)} recomputed={values[key]}"
                )
        try:
            summary_pass1 = float(summary_row.get("pass@1"))
        except (TypeError, ValueError):
            failures.append(f"summary pass@1 for {method} is not numeric")
            continue
        if abs(summary_pass1 - values["pass@1"]) > 1e-12:
            failures.append(
                f"summary mismatch for {method} pass@1: "
                f"summary={summary_pass1} recomputed={values['pass@1']}"
            )

    extra_summary_methods = sorted(set(summary_methods) - set(recomputed))
    if extra_summary_methods:
        warnings.append(
            "pass1_summary.json contains methods with no detailed rows: "
            f"{extra_summary_methods}"
        )

    report = {
        "results_dir": str(results_dir),
        "manifest_path": str(manifest_path),
        "summary_path": str(summary_path),
        "detailed_files": [str(path) for path in detailed_paths],
        "manifest": manifest,
        "expected_methods": expected_methods,
        "minimum_task_count": min_task_count,
        "task_set_size": len(
            {
                row.get("task_id")
                for row in rows
                if row.get("task_id")
                and (not expected_methods or row.get("method") in expected_methods)
            }
        ),
        "n_rows": len(rows),
        "recomputed_methods": recomputed,
        "warnings": warnings,
        "failures": failures,
    }
    return report


def main(args):
    expected_methods = args.expected_method or []
    if args.require_default_methods:
        expected_methods = DEFAULT_EXPECTED_METHODS
    report = verify_pass1(
        args.results_dir,
        expected_methods=expected_methods,
        min_task_count=args.min_task_count,
    )
    output = Path(args.output).resolve() if args.output else None
    text = json.dumps(report, indent=2) + "\n"
    if output:
        output.write_text(text)
    print(text, end="")
    return 1 if report["failures"] else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--results_dir", default="/home/nlp-07/sqe_experiment/results_pass1")
    parser.add_argument("--output", default="")
    parser.add_argument(
        "--expected_method",
        action="append",
        default=[],
        help="Require this method in detailed rows and pass1_summary.json. Can be repeated.",
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
        help="Only validate methods present in the result rows.",
    )
    parser.add_argument(
        "--min_task_count",
        type=int,
        default=DEFAULT_MIN_TASK_COUNT,
        help=(
            "Minimum number of paired task IDs required for valid Pass@1 "
            "evidence. The default protects paper results; smoke runs must "
            "lower this explicitly."
        ),
    )
    raise SystemExit(main(parser.parse_args()))
