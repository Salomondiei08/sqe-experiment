"""
Derive Dense-Only vs Selective-QE win/loss diagnostics from executed rows.

The analysis is deterministic and uses only existing detailed retrieval JSONL
files. It reports how often Selective-QE recovers a target missed by Dense-Only
and how often it loses a target Dense-Only retrieved.
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
    target = row.get("target_id")
    return target in row.get("retrieved_ids", [])[:k]


def pct(value):
    return f"{100 * value:.1f}"


def analyze_seed(seed, results_dir, k):
    dense_rows = {row["query_id"]: row for row in read_jsonl(results_dir / "dense_only_detailed.jsonl")}
    selective_rows = {
        row["query_id"]: row for row in read_jsonl(results_dir / "proposed_detailed.jsonl")
    }
    common_ids = sorted(set(dense_rows) & set(selective_rows))
    missing_ids = sorted(set(dense_rows) ^ set(selective_rows))
    counts = {
        "both_hit": 0,
        "selective_win": 0,
        "selective_loss": 0,
        "both_miss": 0,
        "expanded_win": 0,
        "expanded_loss": 0,
        "not_expanded_win": 0,
        "not_expanded_loss": 0,
    }
    for query_id in common_ids:
        dense_hit = hit_at(dense_rows[query_id], k)
        selective_row = selective_rows[query_id]
        selective_hit = hit_at(selective_row, k)
        expanded = bool(selective_row.get("meta", {}).get("expanded"))
        if dense_hit and selective_hit:
            counts["both_hit"] += 1
        elif selective_hit and not dense_hit:
            counts["selective_win"] += 1
            counts["expanded_win" if expanded else "not_expanded_win"] += 1
        elif dense_hit and not selective_hit:
            counts["selective_loss"] += 1
            counts["expanded_loss" if expanded else "not_expanded_loss"] += 1
        else:
            counts["both_miss"] += 1
    n = len(common_ids)
    return {
        "seed": seed,
        "results_dir": str(results_dir),
        "k": k,
        "n_queries": n,
        "missing_query_ids": missing_ids,
        **counts,
        "net_wins": counts["selective_win"] - counts["selective_loss"],
        "selective_win_rate": counts["selective_win"] / n if n else 0.0,
        "selective_loss_rate": counts["selective_loss"] / n if n else 0.0,
    }


def write_table(path, rows, aggregate):
    lines = [
        "\\begin{tabular}{lrrrrrr}",
        "\\toprule",
        "Split & N & Both hit & SQE win & SQE loss & Both miss & Net \\\\",
        "\\midrule",
    ]
    for row in rows:
        lines.append(
            f"seed {row['seed']} & {row['n_queries']} & {row['both_hit']} & "
            f"{row['selective_win']} & {row['selective_loss']} & "
            f"{row['both_miss']} & {row['net_wins']} \\\\"
        )
    lines.extend(
        [
            "\\midrule",
            f"All & {aggregate['n_queries']} & {aggregate['both_hit']} & "
            f"{aggregate['selective_win']} & {aggregate['selective_loss']} & "
            f"{aggregate['both_miss']} & {aggregate['net_wins']} \\\\",
            "\\bottomrule",
            "\\end{tabular}",
        ]
    )
    path.write_text("\n".join(lines) + "\n")


def aggregate_rows(rows, k):
    keys = [
        "n_queries",
        "both_hit",
        "selective_win",
        "selective_loss",
        "both_miss",
        "expanded_win",
        "expanded_loss",
        "not_expanded_win",
        "not_expanded_loss",
    ]
    aggregate = {"seed": "all", "k": k, "missing_query_ids": []}
    for key in keys:
        aggregate[key] = sum(row[key] for row in rows)
    aggregate["net_wins"] = aggregate["selective_win"] - aggregate["selective_loss"]
    n = aggregate["n_queries"]
    aggregate["selective_win_rate"] = aggregate["selective_win"] / n if n else 0.0
    aggregate["selective_loss_rate"] = aggregate["selective_loss"] / n if n else 0.0
    return aggregate


def main(args):
    root = Path(args.root).resolve()
    seeds = [int(seed) for seed in args.seeds.split(",") if seed.strip()]
    rows = []
    failures = []
    for seed in seeds:
        results_dir = root / f"results_500_memory_seed{seed}"
        if not results_dir.exists():
            failures.append(f"missing results directory for seed {seed}: {results_dir}")
            continue
        row = analyze_seed(seed, results_dir, args.k)
        if row["missing_query_ids"]:
            failures.append(
                f"seed {seed} dense/selective query ID mismatch: "
                f"{row['missing_query_ids'][:10]}"
            )
        rows.append(row)
    aggregate = aggregate_rows(rows, args.k)
    report = {
        "k": args.k,
        "seeds": seeds,
        "rows": rows,
        "aggregate": aggregate,
        "interpretation": (
            "SQE win means Selective-QE retrieves the target in the top-k when "
            "Dense-Only does not. SQE loss means Dense-Only retrieves the target "
            "in the top-k when Selective-QE does not."
        ),
        "failures": failures,
    }

    output = root / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n")
    table_output = root / args.table_output
    table_output.parent.mkdir(parents=True, exist_ok=True)
    write_table(table_output, rows, aggregate)

    print(json.dumps(report, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default="/home/nlp-07/sqe_experiment")
    parser.add_argument("--seeds", default="42,43,44,45")
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--output", default="results_multiseed/win_loss_analysis.json")
    parser.add_argument("--table_output", default="paper/tables/win_loss_analysis.tex")
    raise SystemExit(main(parser.parse_args()))
