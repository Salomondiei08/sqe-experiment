"""
Deterministic diagnostics for simple SQE gate variants.

This script does not run retrieval and does not generate new expansions. It
recombines already executed dense-only and always-expand result rows to compare
simple expansion gates on a train/test query split.
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


def hit_at(row, k):
    target = row.get("target_id") or row.get("target_episode_id")
    return target in row.get("retrieved_ids", [])[:k]


def top1_score(expanded_row):
    score = expanded_row.get("meta", {}).get("top1_score_before_expansion")
    if score is None:
        raise ValueError(f"Missing top1_score_before_expansion for {expanded_row.get('query_id')}")
    return score


def load_pairs(results_dir):
    dense = read_jsonl(results_dir / "dense_only_detailed.jsonl")
    bm25 = read_jsonl(results_dir / "bm25_only_detailed.jsonl")
    expanded = read_jsonl(results_dir / "always_expand_detailed.jsonl")
    if not (len(dense) == len(bm25) == len(expanded)):
        raise ValueError(f"Length mismatch in {results_dir}")
    pairs = []
    for idx, rows in enumerate(zip(dense, bm25, expanded)):
        qids = {row.get("query_id") for row in rows}
        if len(qids) != 1:
            raise ValueError(f"Query mismatch in {results_dir} row {idx}: {qids}")
        pairs.append(rows)
    return sorted(pairs, key=lambda rows: rows[0].get("query_id", ""))


def discover_seed_dir(root, seed):
    path = root / f"results_500_memory_seed{seed}"
    return path if path.exists() else None


def bm25_agrees(dense_row, bm25_row, bm25_k):
    dense_top1 = dense_row.get("retrieved_ids", [None])[0]
    return dense_top1 in bm25_row.get("retrieved_ids", [])[:bm25_k]


def should_expand(policy, threshold, dense_row, bm25_row, expanded_row, bm25_k):
    score_low = top1_score(expanded_row) < threshold
    agrees = bm25_agrees(dense_row, bm25_row, bm25_k)
    if policy == "score_only":
        return score_low
    if policy == "score_and_no_bm25_agreement":
        return score_low and not agrees
    if policy == "score_or_no_bm25_agreement":
        return score_low or not agrees
    raise ValueError(f"Unknown policy: {policy}")


def evaluate(rows, policy, threshold, k, bm25_k):
    hits = 0
    expanded_count = 0
    for dense_row, bm25_row, expanded_row in rows:
        expand = should_expand(policy, threshold, dense_row, bm25_row, expanded_row, bm25_k)
        selected = expanded_row if expand else dense_row
        hits += hit_at(selected, k)
        expanded_count += int(expand)
    return {
        "recall": hits / len(rows),
        "expansion_rate": expanded_count / len(rows),
    }


def select_policy(train_rows, policies, k, bm25_k):
    candidates = []
    for policy in policies:
        for threshold in THRESHOLDS:
            metrics = evaluate(train_rows, policy, threshold, k, bm25_k)
            candidates.append(
                {
                    "policy": policy,
                    "threshold": threshold,
                    "train_recall": metrics["recall"],
                    "train_expansion_rate": metrics["expansion_rate"],
                }
            )
    # Primary: train recall. Tie-breakers: lower expansion rate, then stable name/threshold.
    candidates.sort(
        key=lambda row: (
            -row["train_recall"],
            row["train_expansion_rate"],
            row["policy"],
            row["threshold"],
        )
    )
    return candidates[0], candidates


def mean(values):
    values = list(values)
    return sum(values) / len(values)


def fmt_pct(value, signed=False):
    prefix = "+" if signed and value >= 0 else ""
    return f"{prefix}{100.0 * value:.1f}"


def latex_text(value):
    return str(value).replace("_", r"\_")


def write_latex(path, seed_reports, aggregate):
    lines = [
        r"\begin{tabular}{llrrrr}",
        r"\toprule",
        r"Seed & Policy & Threshold & Test R@5 & Dense Test R@5 & Expansion \\",
        r"\midrule",
    ]
    for row in seed_reports:
        lines.append(
            f"{row['seed']} & {latex_text(row['policy'])} & {row['threshold']:.2f} & "
            f"{fmt_pct(row['test_recall'])} & "
            f"{fmt_pct(row['dense_test_recall'])} & "
            f"{fmt_pct(row['test_expansion_rate'])} \\\\"
        )
    lines.append(r"\midrule")
    lines.append(
        "Mean & -- & -- & "
        f"{fmt_pct(aggregate['test_recall_mean'])} & "
        f"{fmt_pct(aggregate['dense_test_recall_mean'])} & "
        f"{fmt_pct(aggregate['test_expansion_rate_mean'])} \\\\"
    )
    lines.extend([r"\bottomrule", r"\end{tabular}", ""])
    path.write_text("\n".join(lines))


def main(args):
    root = Path(args.root)
    seeds = [int(seed) for seed in args.seeds.split(",") if seed.strip()]
    policies = [
        "score_only",
        "score_and_no_bm25_agreement",
        "score_or_no_bm25_agreement",
    ]
    seed_reports = []
    for seed in seeds:
        results_dir = discover_seed_dir(root, seed)
        if results_dir is None:
            continue
        pairs = load_pairs(results_dir)
        midpoint = len(pairs) // 2
        train_rows = pairs[:midpoint]
        test_rows = pairs[midpoint:]
        selected, candidates = select_policy(train_rows, policies, args.k, args.bm25_k)
        test_metrics = evaluate(
            test_rows, selected["policy"], selected["threshold"], args.k, args.bm25_k
        )
        dense_recall = sum(hit_at(dense_row, args.k) for dense_row, _, _ in test_rows) / len(test_rows)
        seed_reports.append(
            {
                "seed": seed,
                "results_dir": str(results_dir),
                "n_train": len(train_rows),
                "n_test": len(test_rows),
                "policy": selected["policy"],
                "threshold": selected["threshold"],
                "train_recall": selected["train_recall"],
                "train_expansion_rate": selected["train_expansion_rate"],
                "test_recall": test_metrics["recall"],
                "dense_test_recall": dense_recall,
                "test_delta_vs_dense": test_metrics["recall"] - dense_recall,
                "test_expansion_rate": test_metrics["expansion_rate"],
                "candidate_grid": candidates,
            }
        )
    if not seed_reports:
        raise SystemExit("No completed independent memory seed directories found")

    aggregate = {
        "n_seeds": len(seed_reports),
        "test_recall_mean": mean(row["test_recall"] for row in seed_reports),
        "dense_test_recall_mean": mean(row["dense_test_recall"] for row in seed_reports),
        "test_delta_vs_dense_mean": mean(row["test_delta_vs_dense"] for row in seed_reports),
        "test_expansion_rate_mean": mean(row["test_expansion_rate"] for row in seed_reports),
    }
    report = {
        "seeds": seeds,
        "seed_family": "independent_memory",
        "metric": f"Recall@{args.k}",
        "bm25_agreement_k": args.bm25_k,
        "procedure": (
            "For each independent memory seed, select a policy and threshold on "
            "the first half of sorted query IDs, then evaluate on the second half "
            "by recombining executed dense-only rows with executed always-expand "
            "rows. BM25 agreement is computed from executed BM25-only rows."
        ),
        "policies": policies,
        "threshold_grid": THRESHOLDS,
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
    parser.add_argument("--bm25_k", type=int, default=10)
    parser.add_argument("--output", default="results_gate_calibration/gate_variant_diagnostics.json")
    parser.add_argument("--table_output", default="paper/tables/gate_variant_diagnostics.tex")
    main(parser.parse_args())
