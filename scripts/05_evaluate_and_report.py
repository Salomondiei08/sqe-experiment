"""
Step 5: Evaluate All Methods and Generate Report
==================================================
Loads all results from baselines and the proposed method,
computes final metrics, runs ablation analysis, and generates:
  - A summary table (printed to console)
  - A bar chart comparing Recall@K across all methods
  - A threshold sensitivity plot for the confidence gate
  - A JSON report for the paper

Usage:
    python scripts/05_evaluate_and_report.py \
        --results_dir results/ \
        --top_k 5
"""

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import jsonlines
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()


def load_summary(results_dir: Path) -> list[dict]:
    """Load all method summaries into a unified list."""
    summaries = []

    # Baselines
    baseline_path = results_dir / "baselines_summary.json"
    if baseline_path.exists():
        with open(baseline_path) as f:
            summaries.extend(json.load(f))

    # Proposed method
    proposed_path = results_dir / "proposed_summary.json"
    if proposed_path.exists():
        with open(proposed_path) as f:
            summaries.append(json.load(f))

    return summaries


def load_detailed(results_dir: Path, filename: str) -> list[dict]:
    path = results_dir / filename
    if not path.exists():
        return []
    with jsonlines.open(path) as r:
        return list(r)


def plot_recall_comparison(summaries: list[dict], top_k: int, output_path: Path):
    """Bar chart comparing Recall@1 and Recall@K across all methods."""
    methods = [s["method"] for s in summaries]
    recall1 = [s.get("recall@1", 0) for s in summaries]
    recallk = [s.get(f"recall@{top_k}", 0) for s in summaries]

    x = np.arange(len(methods))
    width = 0.35

    fig, ax = plt.subplots(figsize=(10, 6))
    bars1 = ax.bar(x - width / 2, recall1, width, label="Recall@1",
                   color="#4C72B0", alpha=0.85, edgecolor="white")
    bars2 = ax.bar(x + width / 2, recallk, width, label=f"Recall@{top_k}",
                   color="#DD8452", alpha=0.85, edgecolor="white")

    # Value labels on bars
    for bar in bars1:
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.005,
                f"{bar.get_height():.2f}", ha="center", va="bottom", fontsize=9)
    for bar in bars2:
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.005,
                f"{bar.get_height():.2f}", ha="center", va="bottom", fontsize=9)

    ax.set_xlabel("Retrieval Method", fontsize=12)
    ax.set_ylabel("Recall Score", fontsize=12)
    ax.set_title(
        "Retrieval Recall Comparison: Baselines vs. Selective Query Expansion",
        fontsize=13, fontweight="bold"
    )
    ax.set_xticks(x)
    ax.set_xticklabels(methods, fontsize=10)
    ax.set_ylim(0, 1.1)
    ax.legend(fontsize=11)
    ax.yaxis.grid(True, linestyle="--", alpha=0.7)
    ax.set_axisbelow(True)

    # Highlight the proposed method bar
    proposed_idx = next(
        (i for i, s in enumerate(summaries) if "Selective" in s["method"]), None
    )
    if proposed_idx is not None:
        ax.get_xticklabels()[proposed_idx].set_color("#c0392b")
        ax.get_xticklabels()[proposed_idx].set_fontweight("bold")

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()
    console.print(f"[green]Recall comparison chart saved to {output_path}[/green]")


def plot_threshold_sensitivity(detailed_proposed: list[dict], top_k: int, output_path: Path):
    """
    Simulate different confidence thresholds on the proposed method results
    to show the trade-off between expansion rate and recall.
    """
    if not detailed_proposed:
        console.print("[yellow]No proposed method details found, skipping threshold plot[/yellow]")
        return

    thresholds = np.arange(0.3, 1.0, 0.05)
    recall_k_vals = []
    expansion_rates = []

    for tau in thresholds:
        hits = 0
        expanded = 0
        for item in detailed_proposed:
            meta = item.get("meta", {})
            top1_score = meta.get("top1_score_before_expansion", 0.0)
            target_id = item["target_id"]
            retrieved_ids = item["retrieved_ids"]

            # Simulate: if score < tau, we use the expanded results (already computed)
            # if score >= tau, we use only the first retrieved ID (dense-only)
            if top1_score < tau:
                expanded += 1
                hit = target_id in retrieved_ids[:top_k]
            else:
                # Simulate dense-only: use the first retrieved_id
                hit = target_id == retrieved_ids[0] if retrieved_ids else False

            hits += int(hit)

        recall_k_vals.append(hits / len(detailed_proposed))
        expansion_rates.append(expanded / len(detailed_proposed))

    fig, ax1 = plt.subplots(figsize=(9, 5))
    color1 = "#2ecc71"
    color2 = "#e74c3c"

    ax1.plot(thresholds, recall_k_vals, color=color1, marker="o", linewidth=2,
             label=f"Recall@{top_k}")
    ax1.set_xlabel("Confidence Threshold (τ)", fontsize=12)
    ax1.set_ylabel(f"Recall@{top_k}", color=color1, fontsize=12)
    ax1.tick_params(axis="y", labelcolor=color1)
    ax1.set_ylim(0, 1.05)

    ax2 = ax1.twinx()
    ax2.plot(thresholds, expansion_rates, color=color2, marker="s",
             linewidth=2, linestyle="--", label="Expansion Rate")
    ax2.set_ylabel("Expansion Trigger Rate", color=color2, fontsize=12)
    ax2.tick_params(axis="y", labelcolor=color2)
    ax2.set_ylim(0, 1.05)

    patch1 = mpatches.Patch(color=color1, label=f"Recall@{top_k}")
    patch2 = mpatches.Patch(color=color2, label="Expansion Rate")
    ax1.legend(handles=[patch1, patch2], loc="center right", fontsize=10)

    plt.title(
        "Threshold Sensitivity: Recall vs. Expansion Rate",
        fontsize=13, fontweight="bold"
    )
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()
    console.print(f"[green]Threshold sensitivity chart saved to {output_path}[/green]")


def compute_error_analysis(detailed_proposed: list[dict], top_k: int) -> dict:
    """Analyze failure modes in the proposed method."""
    total = len(detailed_proposed)
    if total == 0:
        return {}

    expanded_hits = 0
    expanded_misses = 0
    non_expanded_hits = 0
    non_expanded_misses = 0

    for item in detailed_proposed:
        meta = item.get("meta", {})
        was_expanded = meta.get("expanded", False)
        hit = item.get(f"hit@{top_k}", False)

        if was_expanded:
            if hit:
                expanded_hits += 1
            else:
                expanded_misses += 1
        else:
            if hit:
                non_expanded_hits += 1
            else:
                non_expanded_misses += 1

    return {
        "total_queries": total,
        "expanded": {
            "count": expanded_hits + expanded_misses,
            "hits": expanded_hits,
            "misses": expanded_misses,
            "recall": expanded_hits / max(1, expanded_hits + expanded_misses),
        },
        "not_expanded": {
            "count": non_expanded_hits + non_expanded_misses,
            "hits": non_expanded_hits,
            "misses": non_expanded_misses,
            "recall": non_expanded_hits / max(1, non_expanded_hits + non_expanded_misses),
        },
    }


def main(args):
    results_dir = Path(args.results_dir)
    top_k = args.top_k

    console.print(Panel("Loading all results", style="bold blue"))
    summaries = load_summary(results_dir)

    if not summaries:
        console.print("[red]No results found. Run the retrieval scripts first.[/red]")
        return

    # Print summary table
    table = Table(title="Full Results Summary", show_header=True, show_lines=True)
    table.add_column("Method", style="bold", min_width=20)
    table.add_column("Recall@1", justify="right")
    table.add_column(f"Recall@{top_k}", justify="right")
    table.add_column("Expansion Rate", justify="right")

    for s in summaries:
        exp_rate = f"{s.get('expansion_trigger_rate', 0):.1%}" if "expansion_trigger_rate" in s else "N/A"
        table.add_row(
            s["method"],
            f"{s.get('recall@1', 0):.3f}",
            f"{s.get(f'recall@{top_k}', 0):.3f}",
            exp_rate,
        )
    console.print(table)

    # Generate charts
    plot_recall_comparison(summaries, top_k, results_dir / "recall_comparison.png")

    detailed_proposed = load_detailed(results_dir, "proposed_detailed.jsonl")
    plot_threshold_sensitivity(detailed_proposed, top_k, results_dir / "threshold_sensitivity.png")

    # Error analysis
    error_analysis = compute_error_analysis(detailed_proposed, top_k)
    if error_analysis:
        console.print(Panel("Error Analysis (Proposed Method)", style="bold cyan"))
        ea = error_analysis
        console.print(
            f"  Expanded queries:     {ea['expanded']['count']} "
            f"| Recall@{top_k}: {ea['expanded']['recall']:.3f}"
        )
        console.print(
            f"  Non-expanded queries: {ea['not_expanded']['count']} "
            f"| Recall@{top_k}: {ea['not_expanded']['recall']:.3f}"
        )

    # Save full report
    report = {
        "summaries": summaries,
        "error_analysis": error_analysis,
        "config": {"top_k": top_k},
    }
    with open(results_dir / "full_report.json", "w") as f:
        json.dump(report, f, indent=2)
    console.print(f"[green]Full report saved to {results_dir / 'full_report.json'}[/green]")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--results_dir", type=str, default="results/")
    parser.add_argument("--top_k", type=int, default=5)
    args = parser.parse_args()
    main(args)
