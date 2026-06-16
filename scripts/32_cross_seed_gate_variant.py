"""
Cross-seed validation for simple score/BM25 expansion gates.

This diagnostic does not run retrieval, does not call an LLM, and does not
create task-success evidence. It recombines already executed Dense-Only and
Always-Expand rows, using BM25-Only rows only to compute a gate feature.
"""

import argparse
import json
import random
from pathlib import Path


THRESHOLDS = [round(value / 100.0, 2) for value in range(45, 81)]
POLICIES = [
    "score_only",
    "score_and_no_bm25_agreement",
    "score_or_no_bm25_agreement",
]


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


def top1_score(row):
    score = row.get("meta", {}).get("top1_score_before_expansion")
    if score is None:
        raise ValueError(f"missing top1 score for {row.get('query_id')}")
    return float(score)


def load_seed_rows(root, seed):
    results_dir = root / f"results_500_memory_seed{seed}"
    dense = read_jsonl(results_dir / "dense_only_detailed.jsonl")
    expanded = read_jsonl(results_dir / "always_expand_detailed.jsonl")
    bm25 = read_jsonl(results_dir / "bm25_only_detailed.jsonl")
    if not (len(dense) == len(expanded) == len(bm25)):
        raise ValueError(f"length mismatch in {results_dir}")
    rows = []
    for index, (dense_row, expanded_row, bm25_row) in enumerate(zip(dense, expanded, bm25)):
        qid = dense_row.get("query_id")
        if qid != expanded_row.get("query_id") or qid != bm25_row.get("query_id"):
            raise ValueError(f"query mismatch in {results_dir} row {index}")
        dense_ids = dense_row.get("retrieved_ids", [])
        bm25_ids = bm25_row.get("retrieved_ids", [])
        dense_top_id = dense_ids[0] if dense_ids else None
        rows.append(
            {
                "seed": seed,
                "query_id": qid,
                "top1": top1_score(expanded_row),
                "bm25_agrees_top10": dense_top_id in bm25_ids[:10],
                "dense_row": dense_row,
                "expanded_row": expanded_row,
            }
        )
    return sorted(rows, key=lambda row: row["query_id"])


def should_expand(row, policy, threshold):
    score_low = row["top1"] < threshold
    no_bm25_agreement = not row["bm25_agrees_top10"]
    if policy == "score_only":
        return score_low
    if policy == "score_and_no_bm25_agreement":
        return score_low and no_bm25_agreement
    if policy == "score_or_no_bm25_agreement":
        return score_low or no_bm25_agreement
    raise ValueError(f"unknown policy: {policy}")


def evaluate(rows, policy, threshold, k):
    dense_hits = 0
    always_hits = 0
    gate_hits = 0
    expanded = 0
    deltas = []
    for row in rows:
        dense_hit = int(hit_at(row["dense_row"], k))
        always_hit = int(hit_at(row["expanded_row"], k))
        expand = should_expand(row, policy, threshold)
        gate_hit = always_hit if expand else dense_hit
        dense_hits += dense_hit
        always_hits += always_hit
        gate_hits += gate_hit
        expanded += int(expand)
        deltas.append(gate_hit - dense_hit)
    n = len(rows)
    return {
        "n_queries": n,
        "gate_recall": gate_hits / n,
        "dense_recall": dense_hits / n,
        "always_recall": always_hits / n,
        "delta_vs_dense": sum(deltas) / n,
        "expansion_rate": expanded / n,
        "deltas": deltas,
    }


def select_gate(train_rows, k, max_expansion_rate):
    candidates = []
    for policy in POLICIES:
        for threshold in THRESHOLDS:
            metrics = evaluate(train_rows, policy, threshold, k)
            candidates.append(
                {
                    "policy": policy,
                    "threshold": threshold,
                    "train_recall": metrics["gate_recall"],
                    "dense_train_recall": metrics["dense_recall"],
                    "always_train_recall": metrics["always_recall"],
                    "train_delta_vs_dense": metrics["delta_vs_dense"],
                    "train_expansion_rate": metrics["expansion_rate"],
                    "within_budget": metrics["expansion_rate"] <= max_expansion_rate,
                }
            )
    pool = [row for row in candidates if row["within_budget"]] or candidates
    pool.sort(
        key=lambda row: (
            -row["train_recall"],
            row["train_expansion_rate"],
            row["policy"],
            row["threshold"],
        )
    )
    return pool[0], candidates


def percentile(values, pct):
    ordered = sorted(values)
    index = (len(ordered) - 1) * pct
    lo = int(index)
    hi = min(lo + 1, len(ordered) - 1)
    frac = index - lo
    return ordered[lo] * (1 - frac) + ordered[hi] * frac


def bootstrap_ci(deltas, n_bootstrap, seed):
    rng = random.Random(seed)
    n = len(deltas)
    samples = []
    for _ in range(n_bootstrap):
        samples.append(sum(deltas[rng.randrange(n)] for _ in range(n)) / n)
    return {
        "ci_low": percentile(samples, 0.025),
        "ci_high": percentile(samples, 0.975),
        "n_bootstrap": n_bootstrap,
        "bootstrap_seed": seed,
    }


def sign_flip_p(deltas, n_randomizations, seed):
    observed = abs(sum(deltas) / len(deltas))
    rng = random.Random(seed)
    count = 0
    for _ in range(n_randomizations):
        value = sum(delta if rng.random() < 0.5 else -delta for delta in deltas) / len(deltas)
        if abs(value) >= observed - 1e-15:
            count += 1
    return (count + 1) / (n_randomizations + 1)


def fmt_pct(value, signed=False):
    prefix = "+" if signed and value >= 0 else ""
    return f"{prefix}{100.0 * value:.1f}"


def latex_text(value):
    return str(value).replace("_", r"\_")


def write_table(path, rows, aggregate):
    lines = [
        r"\begin{tabular}{llrrrrr}",
        r"\toprule",
        r"Test seed & Policy & Threshold & Gate R@5 & Dense R@5 & Delta & Expansion \\",
        r"\midrule",
    ]
    for row in rows:
        lines.append(
            f"{row['test_seed']} & {latex_text(row['policy'])} & "
            f"{row['threshold']:.2f} & {fmt_pct(row['gate_recall'])} & "
            f"{fmt_pct(row['dense_recall'])} & "
            f"{fmt_pct(row['delta_vs_dense'], signed=True)} & "
            f"{fmt_pct(row['expansion_rate'])} \\\\"
        )
    lines.append(r"\midrule")
    lines.append(
        f"All & -- & -- & {fmt_pct(aggregate['gate_recall'])} & "
        f"{fmt_pct(aggregate['dense_recall'])} & "
        f"{fmt_pct(aggregate['delta_vs_dense'], signed=True)} & "
        f"{fmt_pct(aggregate['expansion_rate'])} \\\\"
    )
    lines.extend([r"\bottomrule", r"\end{tabular}", ""])
    path.write_text("\n".join(lines))


def main(args):
    root = Path(args.root)
    seeds = [int(seed) for seed in args.seeds.split(",") if seed.strip()]
    seed_rows = {seed: load_seed_rows(root, seed) for seed in seeds}
    reports = []
    all_deltas = []
    total_gate_hits = 0
    total_dense_hits = 0
    total_always_hits = 0
    total_expanded = 0
    total_queries = 0
    for test_seed in seeds:
        train_seeds = [seed for seed in seeds if seed != test_seed]
        train_rows = [row for seed in train_seeds for row in seed_rows[seed]]
        test_rows = seed_rows[test_seed]
        selected, candidates = select_gate(train_rows, args.k, args.max_expansion_rate)
        metrics = evaluate(test_rows, selected["policy"], selected["threshold"], args.k)
        reports.append(
            {
                "test_seed": test_seed,
                "train_seeds": train_seeds,
                "n_train": len(train_rows),
                "n_test": len(test_rows),
                "policy": selected["policy"],
                "threshold": selected["threshold"],
                "train_recall": selected["train_recall"],
                "train_delta_vs_dense": selected["train_delta_vs_dense"],
                "train_expansion_rate": selected["train_expansion_rate"],
                "gate_recall": metrics["gate_recall"],
                "dense_recall": metrics["dense_recall"],
                "always_recall": metrics["always_recall"],
                "delta_vs_dense": metrics["delta_vs_dense"],
                "expansion_rate": metrics["expansion_rate"],
                "candidate_grid": candidates,
            }
        )
        all_deltas.extend(metrics["deltas"])
        total_queries += metrics["n_queries"]
        total_gate_hits += metrics["gate_recall"] * metrics["n_queries"]
        total_dense_hits += metrics["dense_recall"] * metrics["n_queries"]
        total_always_hits += metrics["always_recall"] * metrics["n_queries"]
        total_expanded += metrics["expansion_rate"] * metrics["n_queries"]

    aggregate = {
        "n_queries": total_queries,
        "gate_recall": total_gate_hits / total_queries,
        "dense_recall": total_dense_hits / total_queries,
        "always_recall": total_always_hits / total_queries,
        "delta_vs_dense": sum(all_deltas) / total_queries,
        "expansion_rate": total_expanded / total_queries,
        **bootstrap_ci(all_deltas, args.n_bootstrap, args.seed),
        "sign_flip_p": sign_flip_p(all_deltas, args.n_randomizations, args.seed),
        "n_randomizations": args.n_randomizations,
    }
    report = {
        "artifact_type": "cross_seed_gate_variant",
        "is_pass1_result": False,
        "metric": f"Recall@{args.k}",
        "seed_family": "independent_memory",
        "procedure": (
            "Leave one independent memory-index seed out. Select a score/BM25 "
            "gate on the other seeds under an expansion-rate budget, then "
            "evaluate by recombining executed Dense-Only and Always-Expand rows "
            "on the held-out seed."
        ),
        "max_expansion_rate": args.max_expansion_rate,
        "policies": POLICIES,
        "thresholds": THRESHOLDS,
        "seed_reports": reports,
        "aggregate": aggregate,
    }
    output = root / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    table = root / args.table_output
    table.parent.mkdir(parents=True, exist_ok=True)
    write_table(table, reports, aggregate)
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default="/home/nlp-07/sqe_experiment")
    parser.add_argument("--seeds", default="42,43,44,45,46,47,48,49")
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--max_expansion_rate", type=float, default=0.55)
    parser.add_argument("--n_bootstrap", type=int, default=10000)
    parser.add_argument("--n_randomizations", type=int, default=10000)
    parser.add_argument("--seed", type=int, default=20260514)
    parser.add_argument(
        "--output",
        default="results_gate_calibration/cross_seed_gate_variant.json",
    )
    parser.add_argument(
        "--table_output",
        default="paper/tables/cross_seed_gate_variant.tex",
    )
    raise SystemExit(main(parser.parse_args()))
