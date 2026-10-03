"""Build the two-column preprint data figures from executed result JSON only.

Every number plotted here is read from files under results/. Nothing is typed
in by hand, so the figures cannot drift from the tables. The method-overview
diagram is a separate, non-data illustration (see README.md in this folder).

Usage: python paper/preprint/make_figures.py   (needs matplotlib)
"""

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "results"
OUT = Path(__file__).resolve().parent / "figures"
OUT.mkdir(exist_ok=True)

# Two-column layout: one column is 3.25in wide; full width is 6.75in.
COL_W = 3.25
plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
    "mathtext.fontset": "stix",
    "font.size": 8,
    "axes.labelsize": 8,
    "axes.titlesize": 8,
    "xtick.labelsize": 7,
    "ytick.labelsize": 7,
    "legend.fontsize": 7,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.linewidth": 0.6,
    "xtick.major.width": 0.6,
    "ytick.major.width": 0.6,
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.02,
})

# Muted, colour-blind-safe palette; SQE is the only saturated colour.
SQE_COLOR = "#D55E00"
BASE_COLOR = "#4C6A92"
LIGHT = "#A9B8CC"
GRAY = "#7F7F7F"

METHODS = [
    "Hybrid-RRF",
    "HyDE-Traces-Only",
    "Paraphrases-Only",
    "Dense-Only",
    "Always-Expand",
    "Random-Gated-Expansion",
    "Selective-QE",
]
SHORT = {
    "Hybrid-RRF": "Hybrid-RRF",
    "HyDE-Traces-Only": "Traces only",
    "Paraphrases-Only": "Paraphrases only",
    "Dense-Only": "Dense only",
    "Always-Expand": "Always expand",
    "Random-Gated-Expansion": "Random gate",
    "Selective-QE": "SQE (ours)",
}


def load(rel):
    return json.loads((RESULTS / rel).read_text())


def save(fig, stem):
    fig.savefig(OUT / f"{stem}.pdf")
    fig.savefig(OUT / f"{stem}.png", dpi=300)
    plt.close(fig)


def per_seed_recall5():
    """Recall@5 per method per seed, as percentages."""
    report = load("multiseed/multiseed_report.json")
    table = {m: [] for m in METHODS}
    for seed in report["seed_reports"]:
        for m in METHODS:
            table[m].append(100 * seed["methods"][m]["recall@5"])
    return table


def fig_multiseed(table):
    """Dot plot: each seed as a faint dot, mean as a bold tick."""
    fig, ax = plt.subplots(figsize=(COL_W, 2.1))
    dense_mean = sum(table["Dense-Only"]) / len(table["Dense-Only"])
    ax.axvline(dense_mean, color=GRAY, lw=0.6, ls="--", zorder=0)
    for y, m in enumerate(METHODS):
        vals = table[m]
        mean = sum(vals) / len(vals)
        color = SQE_COLOR if m == "Selective-QE" else BASE_COLOR
        ax.scatter(vals, [y] * len(vals), s=9, color=color, alpha=0.35, lw=0)
        ax.plot([mean, mean], [y - 0.32, y + 0.32], color=color, lw=2)
        ax.text(77.2, y, f"{mean:.1f}", va="center", ha="left", fontsize=7, color=color)
    ax.set_yticks(range(len(METHODS)))
    ax.set_yticklabels([SHORT[m] for m in METHODS])
    ax.get_yticklabels()[-1].set_color(SQE_COLOR)
    ax.set_xlim(58, 77)
    ax.set_xlabel("Recall@5 (%)")
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_visible(False)
    save(fig, "multiseed_recall5")


def fig_cost_quality(table):
    """Measured tokens/query (seed 42) against 8-seed mean Recall@5."""
    runs = load("seed42/full_report_v2.json")["measured_token_runs"]
    tokens = {"Dense-Only": 0.0}
    for run in runs:
        name = run["method"].split(" (")[0]
        tokens[name] = run["avg_total_tokens_per_query"]
    fig, ax = plt.subplots(figsize=(COL_W, 2.0))
    offsets = {
        "Dense-Only": (5, 5),
        "Selective-QE": (-6, 5),
        "Random-Gated-Expansion": (6, -9),
        "Always-Expand": (-6, -11),
        "Paraphrases-Only": (5, -11),
        "HyDE-Traces-Only": (-8, 5),
    }
    for m, (dx, dy) in offsets.items():
        x = tokens[m]
        y = sum(table[m]) / len(table[m])
        color = SQE_COLOR if m == "Selective-QE" else BASE_COLOR
        ax.scatter([x], [y], s=22, color=color, zorder=3, edgecolor="white", lw=0.5)
        ax.annotate(SHORT[m], (x, y), xytext=(dx, dy), textcoords="offset points",
                    fontsize=6.5, color=color, ha="right" if dx < 0 else "left")
    ax.set_xlabel("LLM tokens per query (measured)")
    ax.set_ylabel("Recall@5 (%)")
    ax.set_xlim(-60, 980)
    ax.set_ylim(63.5, 70.5)
    ax.grid(axis="y", lw=0.3, color="#dddddd")
    save(fig, "cost_quality")


def fig_threshold():
    """Seed-42 post-hoc sweep: Recall@5 and expansion rate vs threshold."""
    rows = load("seed42/full_report_v2.json")["threshold_sweep"]
    xs = [r["threshold"] for r in rows]
    r5 = [100 * r["recall@5"] for r in rows]
    exp = [100 * r["expanded"] / r["n"] for r in rows]
    fig, ax = plt.subplots(figsize=(COL_W, 1.9))
    ax.plot(xs, r5, color=BASE_COLOR, marker="o", ms=2.5, lw=1, label="Recall@5")
    ax.axvline(0.65, color=SQE_COLOR, lw=0.8, ls="--")
    ax.text(0.652, 70.35, r"$\tau=0.65$", color=SQE_COLOR, fontsize=7)
    ax.set_xlabel(r"Expansion threshold $\tau$")
    ax.set_ylabel("Recall@5 (%)", color=BASE_COLOR)
    ax.set_ylim(67.5, 70.6)
    ax2 = ax.twinx()
    ax2.spines["right"].set_visible(True)
    ax2.fill_between(xs, exp, color=LIGHT, alpha=0.35, lw=0, label="Queries expanded")
    ax2.set_ylabel("Queries expanded (%)", color=GRAY)
    ax2.set_ylim(0, 105)
    ax.set_zorder(ax2.get_zorder() + 1)
    ax.patch.set_visible(False)
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, loc="lower left", frameon=False)
    save(fig, "threshold_sweep")


def fig_headroom():
    """Held-out half of each seed: dense, always-expand, and oracle gate."""
    seeds = load("gate_calibration/gate_headroom_diagnostics.json")["seed_reports"]
    labels = [str(s["seed"]) for s in seeds]
    series = [
        ("Dense only", "dense_recall", LIGHT),
        ("Always expand", "always_expand_recall", BASE_COLOR),
        ("Oracle gate", "oracle_recall", SQE_COLOR),
    ]
    fig, ax = plt.subplots(figsize=(COL_W, 1.9))
    width = 0.26
    for i, (name, key, color) in enumerate(series):
        xs = [j + (i - 1) * width for j in range(len(seeds))]
        ax.bar(xs, [100 * s[key] for s in seeds], width, color=color, label=name, lw=0)
    ax.set_xticks(range(len(seeds)))
    ax.set_xticklabels(labels)
    ax.set_xlabel("Memory-index seed (held-out half)")
    ax.set_ylabel("Recall@5 (%)")
    ax.set_ylim(60, 79)
    ax.legend(ncol=3, loc="upper center", frameon=False, bbox_to_anchor=(0.5, 1.15))
    save(fig, "gate_headroom")


if __name__ == "__main__":
    recall_table = per_seed_recall5()
    fig_multiseed(recall_table)
    fig_cost_quality(recall_table)
    fig_threshold()
    fig_headroom()
    print("wrote", sorted(p.name for p in OUT.glob("*.pdf")))
