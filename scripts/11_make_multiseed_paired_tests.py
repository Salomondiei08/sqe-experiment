"""
Paired bootstrap tests over completed fixed-memory SQE retrieval seeds.

The script reads executed detailed JSONL files only. It aligns methods within
each completed seed by row order and computes paired Recall@5 deltas for
Selective-QE against selected baselines. It does not generate or impute any
missing run.
"""

import argparse
import json
import random
from pathlib import Path


BASELINES = {
    "Dense-Only": "dense_only_detailed.jsonl",
    "Hybrid-RRF": "hybrid_rrf_detailed.jsonl",
    "Always-Expand": "always_expand_detailed.jsonl",
    "Random-Gated-Expansion": "random_budget_detailed.jsonl",
    "Paraphrases-Only": "paraphrases_only_detailed.jsonl",
    "HyDE-Traces-Only": "traces_only_detailed.jsonl",
}


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
    return 1.0 if target in row.get("retrieved_ids", [])[:k] else 0.0


def mean(values):
    values = list(values)
    return sum(values) / len(values)


def percentile(sorted_values, q):
    if not sorted_values:
        return None
    pos = q * (len(sorted_values) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(sorted_values) - 1)
    frac = pos - lo
    return sorted_values[lo] * (1.0 - frac) + sorted_values[hi] * frac


def paired_bootstrap(deltas, n_samples, seed):
    rng = random.Random(seed)
    n = len(deltas)
    observed = mean(deltas)
    samples = []
    for _ in range(n_samples):
        samples.append(mean(deltas[rng.randrange(n)] for _ in range(n)))
    samples.sort()
    ci_low = percentile(samples, 0.025)
    ci_high = percentile(samples, 0.975)
    if observed >= 0:
        p = sum(1 for x in samples if x <= 0.0) / n_samples
    else:
        p = sum(1 for x in samples if x >= 0.0) / n_samples
    return observed, ci_low, ci_high, p


def fmt_pct(value, signed=False):
    prefix = "+" if signed and value >= 0 else ""
    return f"{prefix}{100.0 * value:.1f}"


def collect_pairs(root, seeds, baseline_file, seed_family):
    pairs = []
    for seed in seeds:
        results_dir = discover_seed_dir(root, seed, seed_family)
        if not results_dir:
            continue
        selective_path = results_dir / "proposed_detailed.jsonl"
        baseline_path = results_dir / baseline_file
        if not selective_path.exists() or not baseline_path.exists():
            continue
        selective = read_jsonl(selective_path)
        baseline = read_jsonl(baseline_path)
        if len(selective) != len(baseline):
            raise ValueError(
                f"Length mismatch for seed {seed}: "
                f"{selective_path.name}={len(selective)}, "
                f"{baseline_path.name}={len(baseline)}"
            )
        for idx, (sel_row, base_row) in enumerate(zip(selective, baseline)):
            sel_qid = sel_row.get("query_id")
            base_qid = base_row.get("query_id")
            if sel_qid != base_qid:
                raise ValueError(
                    f"Query mismatch for seed {seed} row {idx}: "
                    f"{sel_qid} vs {base_qid}"
                )
            pairs.append((seed, idx, sel_row, base_row))
    return pairs


def write_latex(path, rows):
    lines = [
        r"\begin{tabular}{lrrrr}",
        r"\toprule",
        r"Baseline & Queries & $\Delta$R@5 & 95\% CI & Bootstrap $p$ \\",
        r"\midrule",
    ]
    for row in rows:
        lines.append(
            f"{row['baseline']} & {row['n_queries']} & "
            f"{fmt_pct(row['delta'], signed=True)} & "
            f"[{fmt_pct(row['ci_low'], signed=True)}, {fmt_pct(row['ci_high'], signed=True)}] & "
            f"{row['p_value']:.3f} \\\\"
        )
    lines.extend([r"\bottomrule", r"\end{tabular}", ""])
    path.write_text("\n".join(lines))


def main(args):
    root = Path(args.root)
    seeds = [int(s) for s in args.seeds.split(",") if s.strip()]
    rows = []
    for baseline, filename in BASELINES.items():
        pairs = collect_pairs(root, seeds, filename, args.seed_family)
        deltas = [
            hit_at(sel_row, args.k) - hit_at(base_row, args.k)
            for _, _, sel_row, base_row in pairs
        ]
        if not deltas:
            continue
        delta, ci_low, ci_high, p_value = paired_bootstrap(
            deltas, args.bootstrap_samples, args.seed
        )
        rows.append(
            {
                "baseline": baseline,
                "n_queries": len(deltas),
                "delta": delta,
                "ci_low": ci_low,
                "ci_high": ci_high,
                "p_value": p_value,
            }
        )

    report = {
        "seeds": seeds,
        "seed_family": args.seed_family,
        "metric": f"Recall@{args.k}",
        "method": "Selective-QE",
        "bootstrap_samples": args.bootstrap_samples,
        "bootstrap_seed": args.seed,
        "rows": rows,
    }
    report_path = root / args.output
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2))

    table_path = root / args.table_output
    table_path.parent.mkdir(parents=True, exist_ok=True)
    write_latex(table_path, rows)
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
    parser.add_argument("--bootstrap_samples", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--output", default="results_multiseed/multiseed_paired_tests.json"
    )
    parser.add_argument(
        "--table_output", default="paper/tables/multiseed_paired_tests.tex"
    )
    main(parser.parse_args())
