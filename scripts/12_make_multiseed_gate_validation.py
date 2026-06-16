"""
Multi-seed split validation for SQE threshold gates.

This script reads executed dense-only and always-expand result files. For each
completed seed, it selects the best top-1-score expansion threshold on the first
half of query IDs and evaluates that threshold on the second half. It does not
generate new retrieval outputs or fabricate missing seeds.
"""

import argparse
import json
from pathlib import Path


THRESHOLDS = [round(x / 100.0, 2) for x in range(45, 81, 5)]


def read_jsonl(path):
    rows = []
    with open(path) as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


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


def hit_at(row, k):
    target = row.get("target_id") or row.get("target_episode_id")
    return target in row.get("retrieved_ids", [])[:k]


def score(row):
    return row.get("meta", {}).get("top1_score_before_expansion")


def combined_hit(dense_row, expanded_row, threshold, k):
    top1_score = score(expanded_row)
    if top1_score is None:
        raise ValueError(f"Missing top1_score_before_expansion for {expanded_row.get('query_id')}")
    row = expanded_row if top1_score < threshold else dense_row
    return hit_at(row, k)


def evaluate(pairs, threshold, k):
    if not pairs:
        return None
    return sum(combined_hit(dense, expanded, threshold, k) for dense, expanded in pairs) / len(pairs)


def mean(values):
    values = list(values)
    return sum(values) / len(values)


def fmt_pct(value, signed=False):
    prefix = "+" if signed and value >= 0 else ""
    return f"{prefix}{100.0 * value:.1f}"


def seed_pairs(results_dir):
    dense = read_jsonl(results_dir / "dense_only_detailed.jsonl")
    expanded = read_jsonl(results_dir / "always_expand_detailed.jsonl")
    if len(dense) != len(expanded):
        raise ValueError(f"Length mismatch in {results_dir}")
    pairs = []
    for idx, (dense_row, expanded_row) in enumerate(zip(dense, expanded)):
        if dense_row.get("query_id") != expanded_row.get("query_id"):
            raise ValueError(
                f"Query mismatch in {results_dir} row {idx}: "
                f"{dense_row.get('query_id')} vs {expanded_row.get('query_id')}"
            )
        pairs.append((dense_row, expanded_row))
    return pairs


def split_pairs(pairs):
    ordered = sorted(pairs, key=lambda pair: pair[0].get("query_id", ""))
    midpoint = len(ordered) // 2
    return ordered[:midpoint], ordered[midpoint:]


def select_threshold(train_pairs, k):
    candidates = []
    for threshold in THRESHOLDS:
        candidates.append((evaluate(train_pairs, threshold, k), threshold))
    # Deterministic tie-break: prefer the lower expansion threshold.
    candidates.sort(key=lambda item: (-item[0], item[1]))
    return candidates[0][1], candidates[0][0]


def expansion_rate(pairs, threshold):
    expanded = sum(score(expanded_row) < threshold for _, expanded_row in pairs)
    return expanded / len(pairs) if pairs else None


def write_latex(path, seed_reports, aggregate):
    lines = [
        r"\begin{tabular}{lrrrrr}",
        r"\toprule",
        r"Seed & Threshold & Train R@5 & Test R@5 & Dense Test R@5 & Expansion \\",
        r"\midrule",
    ]
    for row in seed_reports:
        lines.append(
            f"{row['seed']} & {row['threshold']:.2f} & "
            f"{fmt_pct(row['train_recall'])} & "
            f"{fmt_pct(row['test_recall'])} & "
            f"{fmt_pct(row['dense_test_recall'])} & "
            f"{fmt_pct(row['test_expansion_rate'])} \\\\"
        )
    lines.append(r"\midrule")
    lines.append(
        "Mean & -- & "
        f"{fmt_pct(aggregate['train_recall_mean'])} & "
        f"{fmt_pct(aggregate['test_recall_mean'])} & "
        f"{fmt_pct(aggregate['dense_test_recall_mean'])} & "
        f"{fmt_pct(aggregate['test_expansion_rate_mean'])} \\\\"
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
            continue
        pairs = seed_pairs(results_dir)
        train_pairs, test_pairs = split_pairs(pairs)
        threshold, train_recall = select_threshold(train_pairs, args.k)
        test_recall = evaluate(test_pairs, threshold, args.k)
        dense_test_recall = sum(hit_at(dense, args.k) for dense, _ in test_pairs) / len(test_pairs)
        seed_reports.append(
            {
                "seed": seed,
                "results_dir": str(results_dir),
                "n_train": len(train_pairs),
                "n_test": len(test_pairs),
                "threshold": threshold,
                "train_recall": train_recall,
                "test_recall": test_recall,
                "dense_test_recall": dense_test_recall,
                "test_delta_vs_dense": test_recall - dense_test_recall,
                "test_expansion_rate": expansion_rate(test_pairs, threshold),
                "threshold_grid": THRESHOLDS,
            }
        )

    if not seed_reports:
        raise SystemExit("No completed seed directories found")

    aggregate = {
        "n_seeds": len(seed_reports),
        "train_recall_mean": mean(row["train_recall"] for row in seed_reports),
        "test_recall_mean": mean(row["test_recall"] for row in seed_reports),
        "dense_test_recall_mean": mean(row["dense_test_recall"] for row in seed_reports),
        "test_delta_vs_dense_mean": mean(row["test_delta_vs_dense"] for row in seed_reports),
        "test_expansion_rate_mean": mean(row["test_expansion_rate"] for row in seed_reports),
    }
    report = {
        "seeds": seeds,
        "seed_family": args.seed_family,
        "metric": f"Recall@{args.k}",
        "procedure": (
            "For each seed, select the best top-1-score threshold on the first "
            "half of sorted query IDs, then evaluate on the second half using "
            "executed dense-only rows when score >= threshold and executed "
            "always-expand rows when score < threshold."
        ),
        "seed_reports": seed_reports,
        "aggregate": aggregate,
    }

    output_path = root / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2))

    table_path = root / args.table_output
    table_path.parent.mkdir(parents=True, exist_ok=True)
    write_latex(table_path, seed_reports, aggregate)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default="/home/nlp-07/sqe_experiment")
    parser.add_argument("--seeds", default="42,43,44,45")
    parser.add_argument(
        "--seed_family",
        choices=["fixed_memory_query", "independent_memory", "auto"],
        default="fixed_memory_query",
    )
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument(
        "--output", default="results_multiseed/multiseed_gate_validation.json"
    )
    parser.add_argument(
        "--table_output", default="paper/tables/multiseed_gate_validation.tex"
    )
    main(parser.parse_args())
