"""
Summarize completed SQE seed directories.

This script only reads executed result files. It refuses to fabricate missing
seeds and writes a JSON report plus a LaTeX table with n/a when fewer than two
completed seeds are available.
"""

import argparse
import json
import math
from pathlib import Path


METHOD_FILES = {
    "Dense-Only": "dense_only_detailed.jsonl",
    "BM25-Only": "bm25_only_detailed.jsonl",
    "Hybrid-RRF": "hybrid_rrf_detailed.jsonl",
    "Paraphrases-Only": "paraphrases_only_detailed.jsonl",
    "HyDE-Traces-Only": "traces_only_detailed.jsonl",
    "Always-Expand": "always_expand_detailed.jsonl",
    "Random-Gated-Expansion": "random_budget_detailed.jsonl",
    "Selective-QE": "proposed_detailed.jsonl",
}


def read_jsonl(path):
    rows = []
    with open(path) as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def row_hit(row, k):
    target = row.get("target_id") or row.get("target_episode_id")
    return target in row.get("retrieved_ids", [])[:k]


def metrics(rows):
    n = len(rows)
    out = {"n_queries": n}
    if not rows:
        return out
    for k in [1, 5, 10]:
        out[f"recall@{k}"] = sum(row_hit(row, k) for row in rows) / n
    rr = 0.0
    for row in rows:
        target = row.get("target_id") or row.get("target_episode_id")
        retrieved = row.get("retrieved_ids", [])
        if target in retrieved:
            rr += 1.0 / (retrieved.index(target) + 1)
    out["mrr"] = rr / n
    expanded = sum(1 for row in rows if row.get("meta", {}).get("expanded"))
    if any("meta" in row for row in rows):
        out["expansion_rate"] = expanded / n
    return out


def mean(values):
    return sum(values) / len(values)


def sample_std(values):
    if len(values) < 2:
        return None
    mu = mean(values)
    return math.sqrt(sum((x - mu) ** 2 for x in values) / (len(values) - 1))


def pct(value):
    if value is None:
        return "--"
    return f"{100.0 * value:.1f}"


def pct_pm(mean_value, std_value):
    if mean_value is None:
        return "--"
    if std_value is None:
        return pct(mean_value)
    return f"{100.0 * mean_value:.1f} $\\pm$ {100.0 * std_value:.1f}"


def discover_seed_dir(root, seed, seed_family):
    if seed_family == "independent_memory":
        candidates = [root / f"results_500_memory_seed{seed}"]
    elif seed_family == "fixed_memory_query":
        candidates = (
            [root / "results_500_memory_seed42"]
            if seed == 42
            else [root / f"results_500_query_seed{seed}_memory_seed42"]
        )
    elif seed_family == "auto":
        candidates = [
            root / f"results_500_memory_seed{seed}",
            root / f"results_500_query_seed{seed}_memory_seed42",
        ]
    else:
        raise ValueError(f"Unknown seed_family: {seed_family}")
    for path in candidates:
        if path.exists():
            return path
    return None


def completed_methods(results_dir):
    return {
        method: results_dir / filename
        for method, filename in METHOD_FILES.items()
        if (results_dir / filename).exists()
    }


def write_latex_table(path, aggregate):
    methods = [
        "Dense-Only",
        "Hybrid-RRF",
        "Always-Expand",
        "Random-Gated-Expansion",
        "Selective-QE",
    ]
    lines = [
        r"\begin{tabular}{lrrrr}",
        r"\toprule",
        r"Method & Seeds & Recall@1 & Recall@5 & Recall@10 \\",
        r"\midrule",
    ]
    for method in methods:
        item = aggregate.get(method, {})
        n = item.get("n_seeds", 0)
        lines.append(
            f"{method} & {n} "
            f"& {pct_pm(item.get('recall@1_mean'), item.get('recall@1_std'))} "
            f"& {pct_pm(item.get('recall@5_mean'), item.get('recall@5_std'))} "
            f"& {pct_pm(item.get('recall@10_mean'), item.get('recall@10_std'))} \\\\"
        )
    lines.extend([r"\bottomrule", r"\end{tabular}", ""])
    path.write_text("\n".join(lines))


def main(args):
    root = Path(args.root)
    seeds = [int(s) for s in args.seeds.split(",") if s.strip()]
    seed_reports = []
    for seed in seeds:
        results_dir = discover_seed_dir(root, seed, args.seed_family)
        if not results_dir:
            seed_reports.append({"seed": seed, "status": "missing"})
            continue
        methods = {}
        for method, detail_path in completed_methods(results_dir).items():
            rows = read_jsonl(detail_path)
            methods[method] = metrics(rows)
        status = "complete" if set(METHOD_FILES) <= set(methods) else "partial"
        seed_reports.append(
            {
                "seed": seed,
                "status": status,
                "results_dir": str(results_dir),
                "methods": methods,
            }
        )

    aggregate = {}
    for method in METHOD_FILES:
        completed = [
            report["methods"][method]
            for report in seed_reports
            if report.get("status") in {"complete", "partial"}
            and method in report.get("methods", {})
        ]
        if not completed:
            continue
        item = {"n_seeds": len(completed)}
        for key in ["recall@1", "recall@5", "recall@10", "mrr", "expansion_rate"]:
            values = [m[key] for m in completed if key in m]
            if not values:
                continue
            item[f"{key}_mean"] = mean(values)
            item[f"{key}_std"] = sample_std(values)
        aggregate[method] = item

    report = {
        "requested_seeds": seeds,
        "seed_family": args.seed_family,
        "n_complete_seeds": sum(1 for r in seed_reports if r["status"] == "complete"),
        "seed_reports": seed_reports,
        "aggregate": aggregate,
        "warning": (
            "Do not report this as a multi-seed experiment until at least two "
            "completed seeds are present."
            if sum(1 for r in seed_reports if r["status"] == "complete") < 2
            else ""
        ),
    }
    output = root / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2))

    table_path = root / args.table_output
    table_path.parent.mkdir(parents=True, exist_ok=True)
    write_latex_table(table_path, aggregate)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default="/home/nlp-07/sqe_experiment")
    parser.add_argument("--seeds", default="42,43,44,45")
    parser.add_argument(
        "--seed_family",
        choices=["fixed_memory_query", "independent_memory", "auto"],
        default="fixed_memory_query",
        help=(
            "fixed_memory_query keeps seed42 memory fixed and varies query samples; "
            "independent_memory requires results_500_memory_seed* directories; "
            "auto preserves the historical discovery order and should be avoided "
            "for paper claims."
        ),
    )
    parser.add_argument("--output", default="results_multiseed/multiseed_report.json")
    parser.add_argument("--table_output", default="paper/tables/multiseed_summary.tex")
    main(parser.parse_args())
