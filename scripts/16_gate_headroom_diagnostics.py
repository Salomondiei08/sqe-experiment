"""
Held-out headroom diagnostic for expansion gating.

This script does not run retrieval and does not generate expansions. It
recombines already executed dense-only and always-expand rows to measure how
often expansion could help or hurt if a perfect gate existed.
"""

import argparse
import json
from pathlib import Path


def read_jsonl(path):
    rows = []
    with open(path) as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def hit_at(row, k):
    target = row.get("target_id") or row.get("target_episode_id")
    return target in row.get("retrieved_ids", [])[:k]


def load_pairs(results_dir):
    dense = read_jsonl(results_dir / "dense_only_detailed.jsonl")
    expanded = read_jsonl(results_dir / "always_expand_detailed.jsonl")
    if len(dense) != len(expanded):
        raise ValueError(f"Length mismatch in {results_dir}")
    pairs = []
    for idx, rows in enumerate(zip(dense, expanded)):
        qids = {row.get("query_id") for row in rows}
        if len(qids) != 1:
            raise ValueError(f"Query mismatch in {results_dir} row {idx}: {qids}")
        pairs.append(rows)
    return sorted(pairs, key=lambda rows: rows[0].get("query_id", ""))


def discover_seed_dir(root, seed):
    path = root / f"results_500_memory_seed{seed}"
    return path if path.exists() else None


def mean(values):
    values = list(values)
    return sum(values) / len(values)


def evaluate(rows, k):
    dense_hits = []
    expanded_hits = []
    for dense_row, expanded_row in rows:
        dense_hits.append(hit_at(dense_row, k))
        expanded_hits.append(hit_at(expanded_row, k))
    n = len(rows)
    helpful = sum((not d) and e for d, e in zip(dense_hits, expanded_hits))
    harmful = sum(d and (not e) for d, e in zip(dense_hits, expanded_hits))
    both_hit = sum(d and e for d, e in zip(dense_hits, expanded_hits))
    both_miss = sum((not d) and (not e) for d, e in zip(dense_hits, expanded_hits))
    dense_recall = sum(dense_hits) / n
    expanded_recall = sum(expanded_hits) / n
    oracle_recall = sum(d or e for d, e in zip(dense_hits, expanded_hits)) / n
    # Minimal oracle expansion expands only when dense misses and expansion hits.
    oracle_expansion_rate = helpful / n
    return {
        "n": n,
        "dense_recall": dense_recall,
        "always_expand_recall": expanded_recall,
        "oracle_recall": oracle_recall,
        "oracle_gain_vs_dense": oracle_recall - dense_recall,
        "always_expand_delta_vs_dense": expanded_recall - dense_recall,
        "helpful_rate": helpful / n,
        "harmful_rate": harmful / n,
        "both_hit_rate": both_hit / n,
        "both_miss_rate": both_miss / n,
        "oracle_expansion_rate": oracle_expansion_rate,
    }


def fmt_pct(value, signed=False):
    prefix = "+" if signed and value >= 0 else ""
    return f"{prefix}{100.0 * value:.1f}"


def write_latex(path, seed_reports, aggregate):
    lines = [
        r"\begin{tabular}{lrrrrr}",
        r"\toprule",
        r"Seed & Dense R@5 & Always R@5 & Oracle R@5 & Helpful & Harmful \\",
        r"\midrule",
    ]
    for row in seed_reports:
        lines.append(
            f"{row['seed']} & "
            f"{fmt_pct(row['dense_recall'])} & "
            f"{fmt_pct(row['always_expand_recall'])} & "
            f"{fmt_pct(row['oracle_recall'])} & "
            f"{fmt_pct(row['helpful_rate'])} & "
            f"{fmt_pct(row['harmful_rate'])} \\\\"
        )
    lines.append(r"\midrule")
    lines.append(
        "Mean & "
        f"{fmt_pct(aggregate['dense_recall_mean'])} & "
        f"{fmt_pct(aggregate['always_expand_recall_mean'])} & "
        f"{fmt_pct(aggregate['oracle_recall_mean'])} & "
        f"{fmt_pct(aggregate['helpful_rate_mean'])} & "
        f"{fmt_pct(aggregate['harmful_rate_mean'])} \\\\"
    )
    lines.extend([r"\bottomrule", r"\end{tabular}", ""])
    path.write_text("\n".join(lines))


def main(args):
    root = Path(args.root)
    seeds = [int(seed) for seed in args.seeds.split(",") if seed.strip()]
    seed_reports = []
    for seed in seeds:
        results_dir = discover_seed_dir(root, seed)
        if results_dir is None:
            continue
        pairs = load_pairs(results_dir)
        midpoint = len(pairs) // 2
        test_rows = pairs[midpoint:]
        metrics = evaluate(test_rows, args.k)
        seed_reports.append(
            {
                "seed": seed,
                "results_dir": str(results_dir),
                "n_test": len(test_rows),
                **metrics,
            }
        )
    if not seed_reports:
        raise SystemExit("No completed independent memory seed directories found")

    aggregate = {
        "n_seeds": len(seed_reports),
        "dense_recall_mean": mean(row["dense_recall"] for row in seed_reports),
        "always_expand_recall_mean": mean(row["always_expand_recall"] for row in seed_reports),
        "oracle_recall_mean": mean(row["oracle_recall"] for row in seed_reports),
        "oracle_gain_vs_dense_mean": mean(row["oracle_gain_vs_dense"] for row in seed_reports),
        "always_expand_delta_vs_dense_mean": mean(
            row["always_expand_delta_vs_dense"] for row in seed_reports
        ),
        "helpful_rate_mean": mean(row["helpful_rate"] for row in seed_reports),
        "harmful_rate_mean": mean(row["harmful_rate"] for row in seed_reports),
        "both_hit_rate_mean": mean(row["both_hit_rate"] for row in seed_reports),
        "both_miss_rate_mean": mean(row["both_miss_rate"] for row in seed_reports),
        "oracle_expansion_rate_mean": mean(row["oracle_expansion_rate"] for row in seed_reports),
    }
    report = {
        "seeds": seeds,
        "seed_family": "independent_memory",
        "metric": f"Recall@{args.k}",
        "procedure": (
            "For each independent memory seed, evaluate the second half of sorted "
            "query IDs by recombining executed dense-only and always-expand rows. "
            "The oracle row is a diagnostic upper bound that counts a query as "
            "retrieved if either executed method retrieved the target."
        ),
        "seed_reports": seed_reports,
        "aggregate": aggregate,
    }
    output = root / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n")
    table = root / args.table_output
    table.parent.mkdir(parents=True, exist_ok=True)
    write_latex(table, seed_reports, aggregate)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default="/home/nlp-07/sqe_experiment")
    parser.add_argument("--seeds", default="42,43,44,45")
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--output", default="results_gate_calibration/gate_headroom_diagnostics.json")
    parser.add_argument("--table_output", default="paper/tables/gate_headroom_diagnostics.tex")
    main(parser.parse_args())
