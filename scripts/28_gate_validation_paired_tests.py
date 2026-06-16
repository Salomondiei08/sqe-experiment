"""
Paired test for the held-out threshold-gate diagnostic.

This script does not run retrieval and does not generate expansions. It uses
the thresholds selected by scripts/12_make_multiseed_gate_validation.py and
recomputes paired per-query Recall@K differences against Dense-Only on the
held-out half of each independent memory seed.
"""

import argparse
import json
import random
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


def top1_score(expanded_row):
    score = expanded_row.get("meta", {}).get("top1_score_before_expansion")
    if score is None:
        raise ValueError(f"missing top1_score_before_expansion for {expanded_row.get('query_id')}")
    return score


def load_pairs(results_dir):
    dense = read_jsonl(results_dir / "dense_only_detailed.jsonl")
    expanded = read_jsonl(results_dir / "always_expand_detailed.jsonl")
    if len(dense) != len(expanded):
        raise ValueError(f"length mismatch in {results_dir}")
    pairs = []
    for index, (dense_row, expanded_row) in enumerate(zip(dense, expanded)):
        if dense_row.get("query_id") != expanded_row.get("query_id"):
            raise ValueError(
                f"query mismatch in {results_dir} row {index}: "
                f"{dense_row.get('query_id')} vs {expanded_row.get('query_id')}"
            )
        pairs.append((dense_row, expanded_row))
    return sorted(pairs, key=lambda pair: pair[0].get("query_id", ""))


def percentile(values, pct):
    if not values:
        return None
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


def two_sided_sign_flip_p(deltas, n_randomizations, seed):
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


def write_table(path, rows, aggregate):
    lines = [
        r"\begin{tabular}{lrrrrr}",
        r"\toprule",
        r"Scope & Queries & Gate R@5 & Dense R@5 & Delta & 95\% CI \\",
        r"\midrule",
    ]
    for row in rows:
        lines.append(
            f"{row['seed']} & {row['n_queries']} & "
            f"{fmt_pct(row['gate_recall'])} & {fmt_pct(row['dense_recall'])} & "
            f"{fmt_pct(row['delta'], signed=True)} & "
            f"[{fmt_pct(row['ci_low'], signed=True)}, {fmt_pct(row['ci_high'], signed=True)}] \\\\"
        )
    lines.append(r"\midrule")
    lines.append(
        f"All & {aggregate['n_queries']} & "
        f"{fmt_pct(aggregate['gate_recall'])} & {fmt_pct(aggregate['dense_recall'])} & "
        f"{fmt_pct(aggregate['delta'], signed=True)} & "
        f"[{fmt_pct(aggregate['ci_low'], signed=True)}, {fmt_pct(aggregate['ci_high'], signed=True)}] \\\\"
    )
    lines.extend([r"\bottomrule", r"\end{tabular}", ""])
    path.write_text("\n".join(lines))


def main(args):
    root = Path(args.root)
    gate_path = root / args.gate_validation
    gate_report = json.load(open(gate_path))
    seed_thresholds = {
        int(row["seed"]): row["threshold"]
        for row in gate_report.get("seed_reports", [])
    }
    if not seed_thresholds:
        raise SystemExit(f"no seed thresholds found in {gate_path}")

    rows = []
    all_deltas = []
    for seed in sorted(seed_thresholds):
        results_dir = root / f"results_500_memory_seed{seed}"
        threshold = seed_thresholds[seed]
        pairs = load_pairs(results_dir)
        test_pairs = pairs[len(pairs) // 2 :]
        deltas = []
        gate_hits = 0
        dense_hits = 0
        expanded_count = 0
        for dense_row, expanded_row in test_pairs:
            dense_hit = int(hit_at(dense_row, args.k))
            expand = top1_score(expanded_row) < threshold
            selected_row = expanded_row if expand else dense_row
            gate_hit = int(hit_at(selected_row, args.k))
            dense_hits += dense_hit
            gate_hits += gate_hit
            expanded_count += int(expand)
            deltas.append(gate_hit - dense_hit)
        ci = bootstrap_ci(deltas, args.n_bootstrap, args.seed + seed)
        rows.append(
            {
                "seed": seed,
                "threshold": threshold,
                "n_queries": len(deltas),
                "dense_recall": dense_hits / len(deltas),
                "gate_recall": gate_hits / len(deltas),
                "delta": sum(deltas) / len(deltas),
                "expansion_rate": expanded_count / len(deltas),
                **ci,
            }
        )
        all_deltas.extend(deltas)

    aggregate_ci = bootstrap_ci(all_deltas, args.n_bootstrap, args.seed)
    aggregate = {
        "n_queries": len(all_deltas),
        "dense_recall": sum(row["dense_recall"] * row["n_queries"] for row in rows) / len(all_deltas),
        "gate_recall": sum(row["gate_recall"] * row["n_queries"] for row in rows) / len(all_deltas),
        "delta": sum(all_deltas) / len(all_deltas),
        "ci_low": aggregate_ci["ci_low"],
        "ci_high": aggregate_ci["ci_high"],
        "n_bootstrap": args.n_bootstrap,
        "bootstrap_seed": args.seed,
        "sign_flip_p": two_sided_sign_flip_p(all_deltas, args.n_randomizations, args.seed),
        "n_randomizations": args.n_randomizations,
    }
    report = {
        "artifact_type": "gate_validation_paired_tests",
        "is_pass1_result": False,
        "metric": f"Recall@{args.k}",
        "gate_validation_source": str(gate_path),
        "procedure": (
            "Use thresholds selected on the first half of each seed by the "
            "existing gate-validation diagnostic. On the held-out half, compare "
            "the resulting gate decision against Dense-Only per query."
        ),
        "seed_reports": rows,
        "aggregate": aggregate,
    }
    output = root / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    table = root / args.table_output
    table.parent.mkdir(parents=True, exist_ok=True)
    write_table(table, rows, aggregate)
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default="/home/nlp-07/sqe_experiment")
    parser.add_argument("--gate_validation", default="results_multiseed/multiseed_gate_validation.json")
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--n_bootstrap", type=int, default=10000)
    parser.add_argument("--n_randomizations", type=int, default=10000)
    parser.add_argument("--seed", type=int, default=20260514)
    parser.add_argument("--output", default="results_gate_calibration/gate_validation_paired_tests.json")
    parser.add_argument("--table_output", default="paper/tables/gate_validation_paired_tests.tex")
    raise SystemExit(main(parser.parse_args()))
