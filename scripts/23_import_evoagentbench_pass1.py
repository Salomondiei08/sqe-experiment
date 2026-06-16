"""
Import real EvoAgentBench SWE-bench job outputs into the Pass@1 schema.

This script does not run agents and does not create task outcomes. It converts
existing EvoAgentBench trial result.json files into results_pass1/*_detailed.jsonl
rows that can then be summarized and verified by scripts/21_summarize_pass1_results.py
and scripts/17_verify_pass1_results.py.
"""

import argparse
import json
import re
from datetime import datetime
from pathlib import Path


ALLOWED_METHODS = {
    "Dense-Only",
    "Always-Expand",
    "Random-Gated-Expansion",
    "Selective-QE",
}


def read_json(path):
    with open(path) as f:
        return json.load(f)


def parse_time(value):
    if not value:
        return None
    text = str(value)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def method_slug(method):
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "_", method.strip()).strip("_")
    if not slug:
        raise ValueError("method name produces empty file slug")
    return slug


def reward_from_result(result):
    verifier = result.get("verifier_result", {})
    nested = verifier.get("rewards", {}).get("reward")
    reward = nested if nested is not None else verifier.get("reward", 0.0)
    try:
        return float(reward)
    except (TypeError, ValueError):
        return 0.0


def runtime_from_result(result):
    elapsed = result.get("agent_result", {}).get("elapsed_sec")
    if isinstance(elapsed, (int, float)) and elapsed >= 0:
        return float(elapsed)
    started = parse_time(result.get("started_at"))
    ended = parse_time(result.get("ended_at"))
    if started and ended and ended >= started:
        return (ended - started).total_seconds()
    return 0.0


def failure_reason_from_result(result, reward):
    exception_info = result.get("exception_info")
    if exception_info:
        kind = exception_info.get("type", "Exception")
        message = exception_info.get("message", "")
        return f"{kind}: {message}".strip()
    verifier = result.get("verifier_result", {})
    if verifier.get("error"):
        return str(verifier["error"])
    if reward <= 0:
        return "task not resolved by verifier"
    return ""


def collect_rows(job_dir, method, threshold):
    rows = []
    skipped_retry_dirs = []
    for result_path in sorted(Path(job_dir).glob("*/result.json")):
        if "_retry" in result_path.parent.name:
            skipped_retry_dirs.append(str(result_path.parent))
            continue
        result = read_json(result_path)
        task_id = result.get("task_name") or result_path.parent.name.split("__trial_")[0]
        reward = reward_from_result(result)
        success = reward > threshold
        row = {
            "task_id": task_id,
            "method": method,
            "success": success,
            "runtime_seconds": runtime_from_result(result),
            "source_job_dir": str(Path(job_dir).resolve()),
            "source_result_json": str(result_path.resolve()),
            "reward": reward,
            "agent": result.get("agent"),
            "trial": result.get("trial", 1),
        }
        if not success:
            row["failure_reason"] = failure_reason_from_result(result, reward)
        rows.append(row)
    return rows, skipped_retry_dirs


def update_manifest(output_dir, method, job_dir, output_path, rows, threshold, skipped_retry_dirs):
    manifest_path = output_dir / "manifest.json"
    manifest = {}
    if manifest_path.exists():
        manifest = read_json(manifest_path)
    imports = manifest.setdefault("imports", [])
    imports = [
        entry for entry in imports
        if entry.get("method") != method or entry.get("output_path") != str(output_path)
    ]
    imports.append(
        {
            "method": method,
            "source": "EvoAgentBench",
            "source_job_dir": str(Path(job_dir).resolve()),
            "output_path": str(output_path),
            "n_rows": len(rows),
            "success_threshold": threshold,
            "skipped_retry_dirs": skipped_retry_dirs,
            "note": "Imported from existing result.json files; no agent tasks were run by this importer.",
        }
    )
    manifest["imports"] = imports
    manifest.setdefault(
        "schema_note",
        "Detailed rows must be summarized by scripts/21_summarize_pass1_results.py and verified by scripts/17_verify_pass1_results.py before paper use.",
    )
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return manifest_path


def main(args):
    job_dir = Path(args.job_dir).resolve()
    output_dir = Path(args.output_dir).resolve()
    if args.method not in ALLOWED_METHODS and not args.allow_unlisted_method:
        raise SystemExit(
            f"method {args.method!r} is not one of {sorted(ALLOWED_METHODS)}. "
            "Use --allow_unlisted_method only for exploratory non-paper methods."
        )
    if not job_dir.exists():
        raise SystemExit(f"job_dir does not exist: {job_dir}")
    rows, skipped_retry_dirs = collect_rows(job_dir, args.method, args.success_threshold)
    if not rows:
        raise SystemExit(f"no non-retry result.json files found under {job_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{method_slug(args.method)}_detailed.jsonl"
    if output_path.exists() and not args.overwrite:
        raise SystemExit(f"refusing to overwrite existing file without --overwrite: {output_path}")
    with open(output_path, "w") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")

    manifest_path = update_manifest(
        output_dir,
        args.method,
        job_dir,
        output_path,
        rows,
        args.success_threshold,
        skipped_retry_dirs,
    )
    print(
        json.dumps(
            {
                "output_path": str(output_path),
                "manifest_path": str(manifest_path),
                "n_rows": len(rows),
                "n_success": sum(1 for row in rows if row["success"]),
                "skipped_retry_dirs": skipped_retry_dirs,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--job_dir", required=True, help="EvoAgentBench job directory")
    parser.add_argument("--method", required=True, help="Paper method name for imported rows")
    parser.add_argument("--output_dir", default="/home/nlp-07/sqe_experiment/results_pass1")
    parser.add_argument(
        "--success_threshold",
        type=float,
        default=0.0,
        help="A task is successful when verifier reward is greater than this threshold.",
    )
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument(
        "--allow_unlisted_method",
        action="store_true",
        help="Allow importing a non-paper method name. Do not use for main paper Pass@1 evidence.",
    )
    raise SystemExit(main(parser.parse_args()))
