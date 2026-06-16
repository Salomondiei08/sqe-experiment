"""
Verify retrieval-context packets prepared for future Pass@1 runs.

This checker confirms that context packets are well formed and explicitly marked
as non-results. It does not run agents and does not validate task success.
"""

import argparse
import json
from pathlib import Path


REQUIRED_ROW_FIELDS = {
    "task_id",
    "method",
    "query",
    "retrieved_memories",
    "context_text",
    "retrieval_meta",
}
FORBIDDEN_RESULT_FIELDS = {"success", "runtime_seconds", "pass@1", "solved", "reward"}
REQUIRED_MEMORY_FIELDS = {"episode_id", "score", "task_id", "formatted_text"}
DEFAULT_EXPECTED_METHODS = [
    "Dense-Only",
    "Always-Expand",
    "Random-Gated-Expansion",
    "Selective-QE",
]


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


def verify_manifest(manifest_path):
    failures = []
    manifest = read_json(manifest_path)
    if manifest.get("artifact_type") != "pass1_retrieval_contexts":
        failures.append(f"{manifest_path}: artifact_type must be pass1_retrieval_contexts")
    if manifest.get("is_pass1_result") is not False:
        failures.append(f"{manifest_path}: is_pass1_result must be false")
    if "Pass@1 claim" not in manifest.get("note", ""):
        failures.append(f"{manifest_path}: note must state that this is not Pass@1 evidence")
    output_path = Path(manifest.get("output_path", ""))
    if not output_path.exists():
        failures.append(f"{manifest_path}: output_path does not exist: {output_path}")
    return manifest, output_path, failures


def verify_rows(path, manifest):
    failures = []
    try:
        rows = read_jsonl(path)
    except ValueError as exc:
        return [], [str(exc)]
    if not rows:
        failures.append(f"{path}: no context rows found")
        return rows, failures

    expected_n = manifest.get("n_tasks")
    if expected_n is not None and expected_n != len(rows):
        failures.append(f"{path}: manifest n_tasks={expected_n}, rows={len(rows)}")

    expected_method = manifest.get("method")
    seen_pairs = set()
    for row in rows:
        source = f"{row.get('_source_file')}:{row.get('_source_line')}"
        missing = sorted(REQUIRED_ROW_FIELDS - set(row))
        if missing:
            failures.append(f"{source}: missing required fields {missing}")
        forbidden = sorted(FORBIDDEN_RESULT_FIELDS & set(row))
        if forbidden:
            failures.append(f"{source}: context row contains result fields {forbidden}")
        if expected_method and row.get("method") != expected_method:
            failures.append(
                f"{source}: method={row.get('method')!r}, expected {expected_method!r}"
            )
        pair = (row.get("task_id"), row.get("method"))
        if pair in seen_pairs:
            failures.append(f"{source}: duplicate task/method pair {pair}")
        seen_pairs.add(pair)

        memories = row.get("retrieved_memories")
        if not isinstance(memories, list):
            failures.append(f"{source}: retrieved_memories must be a list")
            continue
        if not memories:
            failures.append(f"{source}: retrieved_memories is empty")
        for i, memory in enumerate(memories, start=1):
            missing_memory = sorted(REQUIRED_MEMORY_FIELDS - set(memory))
            if missing_memory:
                failures.append(
                    f"{source}: memory {i} missing fields {missing_memory}"
                )
            if not isinstance(memory.get("score"), (int, float)):
                failures.append(f"{source}: memory {i} score must be numeric")
        context_text = row.get("context_text", "")
        if not isinstance(context_text, str) or "Retrieved Prior Agent Memories" not in context_text:
            failures.append(f"{source}: context_text missing expected heading")
        meta = row.get("retrieval_meta", {})
        if not isinstance(meta, dict) or "mode" not in meta:
            failures.append(f"{source}: retrieval_meta must include mode")
    return rows, failures


def verify_contexts(context_dir, expected_methods=None):
    context_dir = Path(context_dir).resolve()
    failures = []
    warnings = []
    reports = []
    expected_methods = list(expected_methods or [])

    manifest_paths = sorted(context_dir.glob("*_manifest.json"))
    if not context_dir.exists():
        failures.append(f"context directory does not exist: {context_dir}")
    if not manifest_paths:
        failures.append(f"missing *_manifest.json files under {context_dir}")

    for manifest_path in manifest_paths:
        manifest, output_path, manifest_failures = verify_manifest(manifest_path)
        failures.extend(manifest_failures)
        rows = []
        row_failures = []
        if output_path.exists():
            rows, row_failures = verify_rows(output_path, manifest)
            failures.extend(row_failures)
        reports.append(
            {
                "manifest_path": str(manifest_path),
                "output_path": str(output_path),
                "method": manifest.get("method"),
                "n_rows": len(rows),
                "failures": manifest_failures + row_failures,
            }
        )

    if expected_methods:
        by_method = {row.get("method"): row for row in reports}
        for method in expected_methods:
            report = by_method.get(method)
            if report is None:
                failures.append(f"missing context packet for expected method: {method}")
                continue
            if report.get("n_rows", 0) == 0:
                failures.append(f"context packet has zero rows for expected method: {method}")

    return {
        "context_dir": str(context_dir),
        "expected_methods": expected_methods,
        "reports": reports,
        "warnings": warnings,
        "failures": failures,
    }


def main(args):
    expected_methods = args.expected_method or []
    if args.require_default_methods:
        expected_methods = DEFAULT_EXPECTED_METHODS
    report = verify_contexts(args.context_dir, expected_methods=expected_methods)
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        Path(args.output).write_text(text)
    print(text, end="")
    return 1 if report["failures"] else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--context_dir", default="/home/nlp-07/sqe_experiment/pass1_contexts")
    parser.add_argument("--output", default="")
    parser.add_argument(
        "--expected_method",
        action="append",
        default=[],
        help="Require a valid packet for this method label. Can be repeated.",
    )
    parser.add_argument(
        "--require_default_methods",
        action="store_true",
        default=True,
        help="Require Dense-Only, Always-Expand, Random-Gated-Expansion, and Selective-QE packets.",
    )
    parser.add_argument(
        "--no_require_default_methods",
        dest="require_default_methods",
        action="store_false",
        help="Only validate packets that are present.",
    )
    raise SystemExit(main(parser.parse_args()))
