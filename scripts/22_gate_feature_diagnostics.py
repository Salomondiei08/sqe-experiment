"""
Diagnostics for score-feature SQE gates using saved retrieval indexes.

This script does not run query expansion and does not generate LLM outputs. It
computes dense/BM25 gate features from saved indexes, then recombines already
executed Dense-Only and Always-Expand rows on a train/test query split.
"""

import argparse
import json
import math
from pathlib import Path

from retrieval_engine import RetrievalEngine


TOP1_THRESHOLDS = [round(x / 100.0, 2) for x in range(45, 81, 5)]
MARGIN_THRESHOLDS = [round(x / 1000.0, 3) for x in range(5, 101, 5)]
CONCENTRATION_THRESHOLDS = [round(x / 1000.0, 3) for x in range(200, 701, 50)]


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


def softmax(values):
    if not values:
        return []
    max_value = max(values)
    exps = [math.exp(value - max_value) for value in values]
    total = sum(exps)
    return [value / total for value in exps]


def normalized_entropy(values):
    probs = softmax(values)
    if len(probs) <= 1:
        return 0.0
    entropy = -sum(prob * math.log(prob) for prob in probs if prob > 0)
    return entropy / math.log(len(probs))


def dense_concentration(values):
    return 1.0 - normalized_entropy(values)


def load_pairs(results_dir):
    dense = read_jsonl(results_dir / "dense_only_detailed.jsonl")
    expanded = read_jsonl(results_dir / "always_expand_detailed.jsonl")
    if len(dense) != len(expanded):
        raise ValueError(f"Length mismatch in {results_dir}")
    pairs = []
    for index, (dense_row, expanded_row) in enumerate(zip(dense, expanded)):
        if dense_row.get("query_id") != expanded_row.get("query_id"):
            raise ValueError(f"Query mismatch in {results_dir} row {index}")
        pairs.append((dense_row, expanded_row))
    return sorted(pairs, key=lambda rows: rows[0].get("query_id", ""))


def compute_features(engine, pairs, dense_top_k, bm25_top_k):
    feature_rows = []
    for dense_row, expanded_row in pairs:
        query = dense_row["query"]
        dense_results = engine.dense_search(query, top_k=dense_top_k)
        bm25_results = engine.bm25_search(query, top_k=bm25_top_k)
        scores = [score for _, score in dense_results]
        top1 = scores[0] if scores else 0.0
        top2 = scores[1] if len(scores) > 1 else top1
        margin = top1 - top2
        concentration = dense_concentration(scores[: min(5, len(scores))])
        dense_top_id = dense_results[0][0] if dense_results else None
        bm25_ids = [episode_id for episode_id, _ in bm25_results]
        feature_rows.append(
            {
                "query_id": dense_row["query_id"],
                "top1": top1,
                "margin": margin,
                "concentration": concentration,
                "bm25_agrees_top10": dense_top_id in bm25_ids[:10],
                "dense_row": dense_row,
                "expanded_row": expanded_row,
            }
        )
    return feature_rows


def should_expand(policy, threshold, row):
    if policy == "top1_low":
        return row["top1"] < threshold
    if policy == "margin_low":
        return row["margin"] < threshold
    if policy == "concentration_low":
        return row["concentration"] < threshold
    if policy == "top1_low_or_no_bm25_agreement":
        return row["top1"] < threshold or not row["bm25_agrees_top10"]
    if policy == "margin_low_or_no_bm25_agreement":
        return row["margin"] < threshold or not row["bm25_agrees_top10"]
    raise ValueError(f"unknown policy: {policy}")


def policy_thresholds(policy):
    if policy in {"top1_low", "top1_low_or_no_bm25_agreement"}:
        return TOP1_THRESHOLDS
    if policy in {"margin_low", "margin_low_or_no_bm25_agreement"}:
        return MARGIN_THRESHOLDS
    if policy == "concentration_low":
        return CONCENTRATION_THRESHOLDS
    raise ValueError(f"unknown policy: {policy}")


def evaluate(rows, policy, threshold, k):
    hits = 0
    expanded = 0
    for row in rows:
        use_expanded = should_expand(policy, threshold, row)
        selected = row["expanded_row"] if use_expanded else row["dense_row"]
        hits += int(hit_at(selected, k))
        expanded += int(use_expanded)
    return {"recall": hits / len(rows), "expansion_rate": expanded / len(rows)}


def select_policy(train_rows, policies, k, max_expansion_rate):
    candidates = []
    for policy in policies:
        for threshold in policy_thresholds(policy):
            metrics = evaluate(train_rows, policy, threshold, k)
            candidates.append(
                {
                    "policy": policy,
                    "threshold": threshold,
                    "train_recall": metrics["recall"],
                    "train_expansion_rate": metrics["expansion_rate"],
                    "within_budget": metrics["expansion_rate"] <= max_expansion_rate,
                }
            )
    budgeted = [row for row in candidates if row["within_budget"]]
    selection_pool = budgeted if budgeted else candidates
    selection_pool.sort(
        key=lambda row: (
            -row["train_recall"],
            row["train_expansion_rate"],
            row["policy"],
            row["threshold"],
        )
    )
    return selection_pool[0], candidates


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
            f"{row['seed']} & {latex_text(row['policy'])} & {row['threshold']:.3f} & "
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
        "top1_low",
        "margin_low",
        "concentration_low",
        "top1_low_or_no_bm25_agreement",
        "margin_low_or_no_bm25_agreement",
    ]
    seed_reports = []
    for seed in seeds:
        results_dir = root / f"results_500_memory_seed{seed}"
        index_dir = root / f"index_500_seed{seed}"
        if not results_dir.exists() or not index_dir.exists():
            continue
        pairs = load_pairs(results_dir)
        engine = RetrievalEngine(
            str(index_dir),
            embedding_model=args.embedding_model,
            device=args.device,
        )
        rows = compute_features(engine, pairs, args.dense_top_k, args.bm25_top_k)
        midpoint = len(rows) // 2
        train_rows = rows[:midpoint]
        test_rows = rows[midpoint:]
        selected, candidates = select_policy(
            train_rows, policies, args.k, args.max_expansion_rate
        )
        test_metrics = evaluate(test_rows, selected["policy"], selected["threshold"], args.k)
        dense_recall = sum(hit_at(row["dense_row"], args.k) for row in test_rows) / len(test_rows)
        seed_reports.append(
            {
                "seed": seed,
                "results_dir": str(results_dir),
                "index_dir": str(index_dir),
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
        raise SystemExit("No completed seed/index directories found")

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
        "procedure": (
            "For each independent memory seed, compute dense top-k score features "
            "from the saved FAISS index and BM25 agreement from the saved BM25 "
            "index. Select a gate on the first half of sorted query IDs, then "
            "evaluate on the second half by recombining executed Dense-Only and "
            "Always-Expand result rows."
        ),
        "policies": policies,
        "max_expansion_rate": args.max_expansion_rate,
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
    parser.add_argument("--dense_top_k", type=int, default=10)
    parser.add_argument("--bm25_top_k", type=int, default=10)
    parser.add_argument("--max_expansion_rate", type=float, default=0.55)
    parser.add_argument("--embedding_model", default="BAAI/bge-m3")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--output", default="results_gate_calibration/gate_feature_diagnostics.json")
    parser.add_argument("--table_output", default="paper/tables/gate_feature_diagnostics.tex")
    main(parser.parse_args())
