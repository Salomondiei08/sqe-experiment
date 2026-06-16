"""
Generate paper artifacts from completed SQE experiment results.

This script is intentionally dependency-light. It uses only the Python standard
library so it can run even when plotting libraries are unavailable. It writes:
  - paper/tables/*.tex
  - paper/figures/*.svg
  - paper/references.bib
  - paper/main.tex
  - results_500_memory_seed42/full_report_v2.json by default, or the selected
    --results_dir/full_report_v2.json

It does not overwrite raw experiment data or detailed result files.
"""

import argparse
import json
import random
import re
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results_500_memory_seed42"
PAPER = ROOT / "paper"
TABLES = PAPER / "tables"
FIGURES = PAPER / "figures"


def read_json(path):
    with open(path) as f:
        return json.load(f)


def canonical_method_name(method):
    return method


def read_jsonl(path):
    if not path.exists():
        return []
    rows = []
    with open(path) as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def pct(x):
    if x is None:
        return "--"
    return f"{100.0 * x:.1f}"


def latex_escape(text):
    text = str(text)
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(replacements.get(ch, ch) for ch in text)


def truncate_text(text, max_chars=82):
    text = re.sub(r"\s+", " ", str(text)).strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."


def method_slug(name):
    return name.lower().replace("-", "_").replace("+", "_").replace(" ", "_")


def load_summaries():
    summaries = []
    baseline_path = RESULTS / "baselines_summary.json"
    if baseline_path.exists():
        for item in read_json(baseline_path):
            item["method"] = canonical_method_name(item["method"])
            summaries.append(item)

    for path in sorted(RESULTS.glob("*_summary.json")):
        if path.name == "baselines_summary.json":
            continue
        item = read_json(path)
        item["method"] = canonical_method_name(item["method"])
        item["_summary_file"] = path.name
        summaries.append(item)

    # Deduplicate by method, keeping the last file in lexical order.
    by_method = {}
    for item in summaries:
        by_method[item["method"]] = item
    return list(by_method.values())


def detailed_path_for_method(method):
    mapping = {
        "Dense-Only": "dense_only_detailed.jsonl",
        "BM25-Only": "bm25_only_detailed.jsonl",
        "Hybrid-RRF": "hybrid_rrf_detailed.jsonl",
        "Selective-QE": "proposed_detailed.jsonl",
        "Always-Expand": "always_expand_detailed.jsonl",
        "HyDE-Traces-Only": "traces_only_detailed.jsonl",
        "Paraphrases-Only": "paraphrases_only_detailed.jsonl",
        "Dense-Only-Runner": "dense_only_detailed.jsonl",
        "Random-Gated-Expansion": "random_budget_detailed.jsonl",
    }
    return RESULTS / mapping.get(method, f"{method_slug(method)}_detailed.jsonl")


def enrich_summary(summary, top_ks=(1, 5, 10)):
    rows = read_jsonl(detailed_path_for_method(summary["method"]))
    if not rows:
        return summary

    n = len(rows)
    target_key = "target_id"
    recalls = {}
    rr_total = 0.0
    max_depth = 0
    for row in rows:
        target = row.get(target_key) or row.get("target_episode_id")
        retrieved = row.get("retrieved_ids", [])
        max_depth = max(max_depth, len(retrieved))
        for k in top_ks:
            recalls[f"recall@{k}"] = recalls.get(f"recall@{k}", 0) + int(target in retrieved[:k])
        if target in retrieved:
            rr_total += 1.0 / (retrieved.index(target) + 1)

    for k in top_ks:
        summary[f"recall@{k}"] = recalls[f"recall@{k}"] / n
    summary["mrr"] = rr_total / n
    summary["n_queries"] = n
    summary["max_retrieved_depth"] = max_depth
    return summary


def row_hit_at(row, top_k):
    target = row.get("target_id") or row.get("target_episode_id")
    retrieved = row.get("retrieved_ids", [])
    return bool(target in retrieved[:top_k])


def target_rank(row):
    target = row.get("target_id") or row.get("target_episode_id")
    retrieved = row.get("retrieved_ids", [])
    if target in retrieved:
        return str(retrieved.index(target) + 1)
    return ">10"


def bootstrap_ci(rows, top_k=5, n_boot=2000, seed=42):
    if not rows:
        return None
    rng = random.Random(seed)
    vals = [1.0 if row_hit_at(row, top_k) else 0.0 for row in rows]
    n = len(vals)
    samples = []
    for _ in range(n_boot):
        samples.append(sum(vals[rng.randrange(n)] for _ in range(n)) / n)
    samples.sort()
    lo = samples[int(0.025 * n_boot)]
    hi = samples[int(0.975 * n_boot)]
    return lo, hi


def method_rows(method):
    return read_jsonl(detailed_path_for_method(method))


def paired_bootstrap_delta(method_a, method_b, top_k=5, n_boot=5000, seed=42):
    """Bootstrap the paired recall delta method_a - method_b by query_id."""
    rows_a = {r.get("query_id"): r for r in method_rows(method_a)}
    rows_b = {r.get("query_id"): r for r in method_rows(method_b)}
    ids = sorted(set(rows_a) & set(rows_b))
    if not ids:
        return None

    diffs = [
        (1.0 if row_hit_at(rows_a[qid], top_k) else 0.0)
        - (1.0 if row_hit_at(rows_b[qid], top_k) else 0.0)
        for qid in ids
    ]
    observed = sum(diffs) / len(diffs)

    rng = random.Random(seed)
    samples = []
    n = len(diffs)
    for _ in range(n_boot):
        samples.append(sum(diffs[rng.randrange(n)] for _ in range(n)) / n)
    samples.sort()
    lo = samples[int(0.025 * n_boot)]
    hi = samples[int(0.975 * n_boot)]
    # Two-sided sign-style bootstrap p-value around zero.
    p = 2 * min(
        sum(1 for x in samples if x <= 0) / n_boot,
        sum(1 for x in samples if x >= 0) / n_boot,
    )
    return {"delta": observed, "ci95": [lo, hi], "p_bootstrap": min(1.0, p), "n": n}


def estimated_calls_from_row(row):
    meta = row.get("meta", {})
    if "estimated_llm_calls" in meta:
        return meta["estimated_llm_calls"]
    traces = meta.get("n_hypothetical_traces_generated", 0)
    paraphrase_call = 1 if meta.get("n_paraphrases_generated", 0) else 0
    return traces + paraphrase_call


def add_cost_summary(summary):
    rows = read_jsonl(detailed_path_for_method(summary["method"]))
    if not rows:
        summary.setdefault("avg_estimated_llm_calls_per_query", 0.0)
        summary.setdefault("avg_total_tokens_per_query", 0.0)
        return summary
    summary["avg_estimated_llm_calls_per_query"] = (
        sum(estimated_calls_from_row(r) for r in rows) / len(rows)
    )
    summary["avg_actual_llm_calls_per_query"] = (
        sum(r.get("meta", {}).get("llm_calls", 0) for r in rows) / len(rows)
    )
    summary["avg_prompt_tokens_per_query"] = (
        sum(r.get("meta", {}).get("prompt_tokens", 0) for r in rows) / len(rows)
    )
    summary["avg_completion_tokens_per_query"] = (
        sum(r.get("meta", {}).get("completion_tokens", 0) for r in rows) / len(rows)
    )
    summary["avg_total_tokens_per_query"] = (
        sum(r.get("meta", {}).get("total_tokens", 0) for r in rows) / len(rows)
    )
    if any("elapsed_seconds" in r.get("meta", {}) for r in rows):
        summary["avg_latency_seconds_per_query"] = (
            sum(r.get("meta", {}).get("elapsed_seconds", 0.0) for r in rows)
            / len(rows)
        )
    return summary


def write_main_results_table(summaries):
    TABLES.mkdir(parents=True, exist_ok=True)
    include_r10 = any(s.get("max_retrieved_depth", 0) >= 10 for s in summaries)
    lines = [
        r"\begin{tabular}{l" + ("rrrrr" if include_r10 else "rrrr") + "}",
        r"\toprule",
        (
            r"Method & Recall@1 & Recall@5 & Recall@10 & MRR & Expansion \%"
            if include_r10
            else r"Method & Recall@1 & Recall@5 & MRR & Expansion \%"
        ),
        r"\\",
        r"\midrule",
    ]
    order = [
        "Dense-Only",
        "BM25-Only",
        "Hybrid-RRF",
        "Paraphrases-Only",
        "HyDE-Traces-Only",
        "Always-Expand",
        "Random-Gated-Expansion",
        "Selective-QE",
    ]
    ordered = sorted(summaries, key=lambda s: order.index(s["method"]) if s["method"] in order else 99)
    for s in ordered:
        exp = s.get("expansion_trigger_rate")
        if include_r10:
            lines.append(
                f"{s['method']} & {pct(s.get('recall@1'))} & {pct(s.get('recall@5'))} "
                f"& {pct(s.get('recall@10'))} & {pct(s.get('mrr'))} & {pct(exp)} \\\\"
            )
        else:
            lines.append(
                f"{s['method']} & {pct(s.get('recall@1'))} & {pct(s.get('recall@5'))} "
                f"& {pct(s.get('mrr'))} & {pct(exp)} \\\\"
            )
    lines.extend([r"\bottomrule", r"\end{tabular}", ""])
    (TABLES / "main_results.tex").write_text("\n".join(lines))


def write_error_table(report):
    ea = report.get("error_analysis", {})
    lines = [
        r"\begin{tabular}{lrrrr}",
        r"\toprule",
        r"Subset & Count & Hits@5 & Misses@5 & Recall@5",
        r"\\",
        r"\midrule",
    ]
    for label, key in [("Expanded", "expanded"), ("Not expanded", "not_expanded")]:
        item = ea.get(key, {})
        lines.append(
            f"{label} & {item.get('count', 0)} & {item.get('hits', 0)} "
            f"& {item.get('misses', 0)} & {pct(item.get('recall'))} \\\\"
        )
    lines.extend([r"\bottomrule", r"\end{tabular}", ""])
    (TABLES / "gate_diagnostics.tex").write_text("\n".join(lines))


def write_cost_table(summaries):
    include_tokens = any(s.get("avg_total_tokens_per_query", 0.0) for s in summaries)
    lines = [
        r"\begin{tabular}{lrrr}" if include_tokens else r"\begin{tabular}{lrr}",
        r"\toprule",
        (
            r"Method & Expansion \% & Estimated calls/query & Tokens/query \\"
            if include_tokens
            else r"Method & Expansion \% & Estimated LLM calls/query \\"
        ),
        r"\midrule",
    ]
    order = [
        "Dense-Only",
        "BM25-Only",
        "Hybrid-RRF",
        "Paraphrases-Only",
        "HyDE-Traces-Only",
        "Always-Expand",
        "Random-Gated-Expansion",
        "Selective-QE",
    ]
    ordered = sorted(summaries, key=lambda s: order.index(s["method"]) if s["method"] in order else 99)
    for s in ordered:
        exp = s.get("expansion_trigger_rate")
        calls = s.get("avg_estimated_llm_calls_per_query", 0.0)
        if include_tokens:
            tokens = s.get("avg_total_tokens_per_query", 0.0)
            lines.append(f"{s['method']} & {pct(exp)} & {calls:.2f} & {tokens:.1f} \\\\")
        else:
            lines.append(f"{s['method']} & {pct(exp)} & {calls:.2f} \\\\")
    lines.extend([r"\bottomrule", r"\end{tabular}", ""])
    (TABLES / "cost_summary.tex").write_text("\n".join(lines))


def load_measured_token_runs():
    result_dir = ROOT / "results_tokenmeasured_500_seed42"
    runs = []
    if result_dir.exists():
        for path in sorted(result_dir.glob("*_tokenmeasured500_summary.json")):
            item = read_json(path)
            item["method"] = canonical_method_name(item.get("method", ""))
            item["_summary_file"] = str(path)
            runs.append(item)
    if runs:
        return runs
    pilot = ROOT / "results_tokenpilot_50_seed42" / "selective_tokenpilot50_summary.json"
    if pilot.exists():
        item = read_json(pilot)
        item["method"] = canonical_method_name(item.get("method", ""))
        item["_summary_file"] = str(pilot)
        return [item]
    return []


def write_measured_token_table(measured_runs):
    if not measured_runs:
        return
    lines = [
        r"\begin{tabular}{lrrrrr}",
        r"\toprule",
        r"Method & Expanded & Calls/q & Prompt tok/q & Total tok/q & Latency s/q \\",
        r"\midrule",
    ]
    order = [
        "Selective-QE",
        "Always-Expand",
        "HyDE-Traces-Only",
        "Paraphrases-Only",
        "Random-Gated-Expansion",
    ]
    def measured_label(item):
        mode = item.get("config", {}).get("mode")
        labels = {
            "selective": "Selective-QE",
            "always_expand": "Always-Expand",
            "traces_only": "HyDE-Traces-Only",
            "paraphrases_only": "Paraphrases-Only",
            "random_budget": "Random-Gated-Expansion",
        }
        return labels.get(mode, item.get("method", "Unknown"))

    measured_runs = sorted(
        measured_runs,
        key=lambda item: order.index(measured_label(item)) if measured_label(item) in order else 99,
    )
    for measured in measured_runs:
        lines.append(
            f"{measured_label(measured)} & "
            f"{pct(measured.get('expansion_trigger_rate'))} & "
            f"{measured.get('avg_actual_llm_calls_per_query', 0.0):.2f} & "
            f"{measured.get('avg_prompt_tokens_per_query', 0.0):.1f} & "
            f"{measured.get('avg_total_tokens_per_query', 0.0):.1f} & "
            f"{measured.get('avg_latency_seconds_per_query', 0.0):.2f} \\\\"
        )
    lines.extend([r"\bottomrule", r"\end{tabular}", ""])
    (TABLES / "measured_token_cost.tex").write_text("\n".join(lines))


def write_significance_table(stats):
    lines = [
        r"\begin{tabular}{lrrr}",
        r"\toprule",
        r"Comparison & $\Delta$ Recall@5 & 95\% CI & Bootstrap $p$ \\",
        r"\midrule",
    ]
    for baseline, item in stats.items():
        ci = item["ci95"]
        lines.append(
            f"Selective-QE $-$ {baseline} & {pct(item['delta'])} "
            f"& [{pct(ci[0])}, {pct(ci[1])}] & {item['p_bootstrap']:.3f} \\\\"
        )
    lines.extend([r"\bottomrule", r"\end{tabular}", ""])
    (TABLES / "paired_tests.tex").write_text("\n".join(lines))


def write_case_analysis_table(data_dir):
    eval_rows = {r.get("query_id"): r for r in read_jsonl(Path(data_dir) / "eval_pairs.jsonl")}
    dense_rows = {r.get("query_id"): r for r in read_jsonl(RESULTS / "dense_only_detailed.jsonl")}
    sqe_rows = {r.get("query_id"): r for r in read_jsonl(RESULTS / "proposed_detailed.jsonl")}
    rows = []
    for query_id in sorted(set(dense_rows) & set(sqe_rows)):
        dense_hit = row_hit_at(dense_rows[query_id], 5)
        sqe_hit = row_hit_at(sqe_rows[query_id], 5)
        if dense_hit == sqe_hit:
            continue
        label = "SQE gain" if sqe_hit else "SQE loss"
        rows.append((label, query_id, dense_rows[query_id], sqe_rows[query_id]))

    selected = []
    for label in ["SQE gain", "SQE loss"]:
        selected.extend([row for row in rows if row[0] == label][:2])

    lines = [
        r"\begin{tabular}{lllllp{0.45\linewidth}}",
        r"\toprule",
        r"Case & Query ID & Dense rank & SQE rank & Expanded & Query \\",
        r"\midrule",
    ]
    for label, query_id, dense_row, sqe_row in selected:
        query = eval_rows.get(query_id, {}).get("query") or sqe_row.get("query") or dense_row.get("query", "")
        expanded = "yes" if sqe_row.get("meta", {}).get("expanded") else "no"
        lines.append(
            f"{latex_escape(label)} & {latex_escape(query_id)} & "
            f"{latex_escape(target_rank(dense_row))} & {latex_escape(target_rank(sqe_row))} & "
            f"{expanded} & {latex_escape(truncate_text(query))} \\\\"
        )
    if not selected:
        lines.append(r"No differing top-5 cases found & -- & -- & -- & -- & -- \\")
    lines.extend([r"\bottomrule", r"\end{tabular}", ""])
    (TABLES / "case_analysis.tex").write_text("\n".join(lines))


def threshold_sweep():
    dense_rows = {r.get("query_id"): r for r in read_jsonl(RESULTS / "dense_only_detailed.jsonl")}
    expand_rows = {
        r.get("query_id"): r for r in read_jsonl(RESULTS / "always_expand_detailed.jsonl")
    }
    if not dense_rows or not expand_rows:
        return []
    thresholds = [0.45, 0.50, 0.55, 0.60, 0.62, 0.64, 0.65, 0.66, 0.68, 0.70, 0.75, 0.80]
    out = []
    for threshold in thresholds:
        selected = []
        expanded = 0
        for query_id, dense_row in dense_rows.items():
            expand_row = expand_rows.get(query_id)
            if not expand_row:
                continue
            score = expand_row.get("meta", {}).get("top1_score_before_expansion", 1.0)
            row = expand_row if score < threshold else dense_row
            expanded += int(score < threshold)
            selected.append(row)
        if not selected:
            continue
        item = {"threshold": threshold, "expanded": expanded, "n": len(selected)}
        for top_k in [1, 5, 10]:
            item[f"recall@{top_k}"] = sum(row_hit_at(r, top_k) for r in selected) / len(selected)
        out.append(item)
    return out


def apply_threshold(rows, threshold):
    selected = []
    expanded = 0
    for dense_row, expand_row in rows:
        score = expand_row.get("meta", {}).get("top1_score_before_expansion", 1.0)
        row = expand_row if score < threshold else dense_row
        expanded += int(score < threshold)
        selected.append(row)
    out = {"threshold": threshold, "expanded": expanded, "n": len(selected)}
    for top_k in [1, 5, 10]:
        out[f"recall@{top_k}"] = (
            sum(row_hit_at(r, top_k) for r in selected) / max(1, len(selected))
        )
    return out


def validation_threshold_check():
    dense_rows = {r.get("query_id"): r for r in read_jsonl(RESULTS / "dense_only_detailed.jsonl")}
    expand_rows = {
        r.get("query_id"): r for r in read_jsonl(RESULTS / "always_expand_detailed.jsonl")
    }
    paired = [
        (dense_rows[qid], expand_rows[qid])
        for qid in sorted(dense_rows)
        if qid in expand_rows
    ]
    if len(paired) < 2:
        return {}
    midpoint = len(paired) // 2
    validation = paired[:midpoint]
    test = paired[midpoint:]
    thresholds = [0.45, 0.50, 0.55, 0.60, 0.62, 0.64, 0.65, 0.66, 0.68, 0.70, 0.75, 0.80]
    validation_rows = [apply_threshold(validation, threshold) for threshold in thresholds]
    best = max(
        validation_rows,
        key=lambda r: (r.get("recall@5", 0.0), r.get("recall@10", 0.0), -r["expanded"]),
    )
    fixed = apply_threshold(test, 0.65)
    tuned = apply_threshold(test, best["threshold"])
    dense = apply_threshold(test, 0.45)
    return {
        "validation_n": len(validation),
        "test_n": len(test),
        "selected_threshold": best["threshold"],
        "validation_selected": best,
        "test_dense_proxy": dense,
        "test_fixed_0_65": fixed,
        "test_selected": tuned,
        "validation_rows": validation_rows,
    }


def write_threshold_table(rows):
    if not rows:
        return
    lines = [
        r"\begin{tabular}{rrrr}",
        r"\toprule",
        r"Threshold & Expanded & Recall@5 & Recall@10 \\",
        r"\midrule",
    ]
    for row in rows:
        lines.append(
            f"{row['threshold']:.2f} & {row['expanded']}/{row['n']} "
            f"& {pct(row.get('recall@5'))} & {pct(row.get('recall@10'))} \\\\"
        )
    lines.extend([r"\bottomrule", r"\end{tabular}", ""])
    (TABLES / "threshold_sweep.tex").write_text("\n".join(lines))


def write_validation_threshold_table(check):
    if not check:
        return
    lines = [
        r"\begin{tabular}{lrrrr}",
        r"\toprule",
        r"Policy & Threshold & Expanded & Recall@5 & Recall@10 \\",
        r"\midrule",
    ]
    rows = [
        ("Dense-only proxy", check["test_dense_proxy"]),
        ("Fixed gate", check["test_fixed_0_65"]),
        ("Validation-selected gate", check["test_selected"]),
    ]
    for label, row in rows:
        lines.append(
            f"{label} & {row['threshold']:.2f} & {row['expanded']}/{row['n']} "
            f"& {pct(row.get('recall@5'))} & {pct(row.get('recall@10'))} \\\\"
        )
    lines.extend([r"\bottomrule", r"\end{tabular}", ""])
    (TABLES / "validation_threshold.tex").write_text("\n".join(lines))


def compute_gate_error_analysis(rows, top_k=5):
    if not rows:
        return {}
    out = {
        "total_queries": len(rows),
        "expanded": {"count": 0, "hits": 0, "misses": 0, "recall": 0.0},
        "not_expanded": {"count": 0, "hits": 0, "misses": 0, "recall": 0.0},
    }
    for row in rows:
        bucket = "expanded" if row.get("meta", {}).get("expanded") else "not_expanded"
        hit = row_hit_at(row, top_k)
        out[bucket]["count"] += 1
        out[bucket]["hits" if hit else "misses"] += 1
    for bucket in ["expanded", "not_expanded"]:
        item = out[bucket]
        item["recall"] = item["hits"] / max(1, item["count"])
    return out


def get_n_queries(summaries):
    for summary in summaries:
        if summary.get("n_queries"):
            return int(summary["n_queries"])
    detailed = RESULTS / "dense_only_detailed.jsonl"
    if detailed.exists():
        return len(read_jsonl(detailed))
    return 0


def write_manifest_table(summaries, data_dir):
    data_dir = Path(data_dir)
    manifest_path = data_dir / "dataset_manifest.json"
    manifest = read_json(manifest_path) if manifest_path.exists() else {}
    memory_path = data_dir / "memory_store.jsonl"
    memory = manifest.get("n_memory")
    if memory is None and memory_path.exists():
        memory = sum(1 for _ in open(memory_path))
    eval_n = get_n_queries(summaries)
    lines = [
        r"\begin{tabular}{ll}",
        r"\toprule",
        r"Item & Value \\",
        r"\midrule",
        f"Memory episodes & {memory or '--'} \\\\",
        f"Evaluation queries & {eval_n} \\\\",
        f"Dataset split & {manifest.get('dataset_split', '--')} \\\\",
        f"Evaluation source & {manifest.get('eval_source', '--')} \\\\",
        f"Dataset seed & {manifest.get('seed', '--')} \\\\",
        r"Embedding model & BAAI/bge-m3 \\",
        r"Generator model & Qwen3.6-35B-A3B via vLLM \\",
        r"Index & FAISS dense + BM25 sparse \\",
        r"Fusion & Reciprocal Rank Fusion \\",
        r"GitHub URL & TODO: add public repository URL \\",
        r"Hugging Face dataset & TODO: add Hugging Face dataset URL \\",
        r"\bottomrule",
        r"\end{tabular}",
        "",
    ]
    (TABLES / "experiment_manifest.tex").write_text("\n".join(lines))


def bar_svg(summaries):
    FIGURES.mkdir(parents=True, exist_ok=True)
    order = [
        "Dense-Only",
        "BM25-Only",
        "Hybrid-RRF",
        "Always-Expand",
        "Random-Gated-Expansion",
        "Selective-QE",
        "Paraphrases-Only",
        "HyDE-Traces-Only",
    ]
    by_method = {s["method"]: s for s in summaries}
    methods = [m for m in order if m in by_method]
    values = [by_method[m].get("recall@5", 0.0) for m in methods]
    width, height = 820, 500
    left, right = 245, 755
    top = 86
    row_h = 42
    chart_w = right - left
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<text x="410" y="30" text-anchor="middle" font-family="Arial" font-size="17" fill="#222">Recall@5 by retrieval method</text>',
        '<text x="500" y="464" text-anchor="middle" font-family="Arial" font-size="12" fill="#333">Recall@5</text>',
        f'<line x1="{left}" y1="{top + len(values)*row_h + 4}" x2="{right}" y2="{top + len(values)*row_h + 4}" stroke="black"/>',
        f'<line x1="{left}" y1="{top - 12}" x2="{left}" y2="{top + len(values)*row_h + 4}" stroke="black"/>',
    ]
    for tick in [0, 0.25, 0.5, 0.75, 1.0]:
        x = left + tick * chart_w
        parts.append(f'<line x1="{x:.1f}" y1="{top + len(values)*row_h + 4}" x2="{x:.1f}" y2="{top + len(values)*row_h + 9}" stroke="black"/>')
        parts.append(f'<text x="{x:.1f}" y="{top + len(values)*row_h + 25}" text-anchor="middle" font-family="Arial" font-size="11">{tick:.2f}</text>')
        if tick:
            parts.append(f'<line x1="{x:.1f}" y1="{top - 10}" x2="{x:.1f}" y2="{top + len(values)*row_h + 4}" stroke="#e5e7eb"/>')
    for i, (m, v) in enumerate(zip(methods, values)):
        y = top + i * row_h
        x = left
        w = v * chart_w
        color = "#e4a176" if "Selective" in m else "#9fc3d8"
        parts.append(f'<text x="{left - 12}" y="{y + 22}" text-anchor="end" font-family="Arial" font-size="12" fill="#222">{m}</text>')
        parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="24" fill="{color}" stroke="#667085" stroke-width="0.5"/>')
        parts.append(f'<text x="{x + w + 8:.1f}" y="{y + 18}" font-family="Arial" font-size="12" fill="#222">{v:.2f}</text>')
    parts.append('<rect x="590" y="45" width="14" height="10" fill="#e4a176" stroke="#667085" stroke-width="0.5"/>')
    parts.append('<text x="612" y="55" font-family="Arial" font-size="12" fill="#444">Selective-QE</text>')
    parts.append('<rect x="590" y="64" width="14" height="10" fill="#9fc3d8" stroke="#667085" stroke-width="0.5"/>')
    parts.append('<text x="612" y="74" font-family="Arial" font-size="12" fill="#444">Baseline or ablation</text>')
    parts.append("</svg>")
    svg = "\n".join(parts).replace(
        'font-family="Arial"', 'font-family="DejaVu Sans" font-weight="400"'
    )
    (FIGURES / "recall_at_5.svg").write_text(svg)


def gate_svg(rows):
    if not rows:
        return
    bins = [(0.45, 0.55), (0.55, 0.60), (0.60, 0.65), (0.65, 0.70), (0.70, 0.80)]
    points = []
    for lo, hi in bins:
        group = [
            r for r in rows
            if lo <= r.get("meta", {}).get("top1_score_before_expansion", 0.0) < hi
        ]
        if group:
            hit = sum(1 for r in group if row_hit_at(r, 5)) / len(group)
            points.append((f"{lo:.2f}-{hi:.2f}", hit, len(group)))
    width, height = 820, 430
    left, bottom = 80, 340
    chart_w, chart_h = 680, 260
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<text x="410" y="30" text-anchor="middle" font-family="Arial" font-size="17" fill="#222">Gate diagnostic: top-1 score vs SQE Recall@5</text>',
        '<text x="82" y="66" font-family="Arial" font-size="12" fill="#444">SQE Recall@5</text>',
        '<text x="420" y="402" text-anchor="middle" font-family="Arial" font-size="12" fill="#333">Dense top-1 score bin</text>',
        f'<line x1="{left}" y1="{bottom}" x2="{left + chart_w}" y2="{bottom}" stroke="black"/>',
        f'<line x1="{left}" y1="{bottom}" x2="{left}" y2="{bottom - chart_h}" stroke="black"/>',
    ]
    gap = chart_w / max(1, len(points))
    for i, (label, hit, n) in enumerate(points):
        x = left + i * gap + gap * 0.5
        y = bottom - hit * chart_h
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="6" fill="#9fc3d8" stroke="#667085" stroke-width="1"/>')
        parts.append(f'<text x="{x:.1f}" y="{y-12:.1f}" text-anchor="middle" font-family="Arial" font-size="11">{hit:.2f}</text>')
        parts.append(f'<text x="{x:.1f}" y="{bottom + 18}" text-anchor="middle" font-family="Arial" font-size="10">{label}</text>')
        parts.append(f'<text x="{x:.1f}" y="{bottom + 34}" text-anchor="middle" font-family="Arial" font-size="10">n={n}</text>')
    parts.append('<circle cx="612" cy="58" r="5" fill="#9fc3d8" stroke="#667085" stroke-width="1"/>')
    parts.append('<text x="624" y="62" font-family="Arial" font-size="12" fill="#444">Score-bin recall</text>')
    parts.append("</svg>")
    svg = "\n".join(parts).replace(
        'font-family="Arial"', 'font-family="DejaVu Sans" font-weight="400"'
    )
    (FIGURES / "gate_diagnostic.svg").write_text(svg)


def threshold_svg(rows):
    if not rows:
        return
    width, height = 820, 430
    left, bottom = 80, 340
    chart_w, chart_h = 680, 260
    min_t = min(r["threshold"] for r in rows)
    max_t = max(r["threshold"] for r in rows)
    min_y = 0.65
    max_y = 0.77
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<text x="410" y="30" text-anchor="middle" font-family="Arial" font-size="17" fill="#222">Post-hoc threshold sweep</text>',
        '<text x="82" y="66" font-family="Arial" font-size="12" fill="#444">Recall@5</text>',
        '<text x="420" y="402" text-anchor="middle" font-family="Arial" font-size="12" fill="#333">Expansion threshold</text>',
        f'<line x1="{left}" y1="{bottom}" x2="{left + chart_w}" y2="{bottom}" stroke="black"/>',
        f'<line x1="{left}" y1="{bottom}" x2="{left}" y2="{bottom - chart_h}" stroke="black"/>',
    ]
    for tick in [0.66, 0.69, 0.72, 0.75]:
        y = bottom - (tick - min_y) / (max_y - min_y) * chart_h
        parts.append(f'<line x1="{left-5}" y1="{y:.1f}" x2="{left}" y2="{y:.1f}" stroke="black"/>')
        parts.append(f'<text x="{left-10}" y="{y+4:.1f}" text-anchor="end" font-family="Arial" font-size="11">{tick:.2f}</text>')
    prev = None
    for row in rows:
        x = left + (row["threshold"] - min_t) / max(1e-9, max_t - min_t) * chart_w
        y = bottom - (row["recall@5"] - min_y) / (max_y - min_y) * chart_h
        if prev:
            parts.append(f'<line x1="{prev[0]:.1f}" y1="{prev[1]:.1f}" x2="{x:.1f}" y2="{y:.1f}" stroke="#6b9fbd" stroke-width="2"/>')
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="#e4a176" stroke="#667085" stroke-width="1"/>')
        if row["threshold"] in {0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80}:
            parts.append(f'<text x="{x:.1f}" y="{bottom + 18}" text-anchor="middle" font-family="Arial" font-size="10">{row["threshold"]:.2f}</text>')
        prev = (x, y)
    parts.append('<line x1="600" y1="58" x2="630" y2="58" stroke="#6b9fbd" stroke-width="2"/>')
    parts.append('<circle cx="615" cy="58" r="5" fill="#e4a176" stroke="#667085" stroke-width="1"/>')
    parts.append('<text x="639" y="62" font-family="Arial" font-size="12" fill="#444">Recall@5</text>')
    parts.append("</svg>")
    svg = "\n".join(parts).replace(
        'font-family="Arial"', 'font-family="DejaVu Sans" font-weight="400"'
    )
    (FIGURES / "threshold_sensitivity.svg").write_text(svg)


def method_overview_svg():
    FIGURES.mkdir(parents=True, exist_ok=True)
    width, height = 1100, 430
    boxes = [
        (40, 160, 160, 76, "Memory request", "natural language query"),
        (245, 160, 165, 76, "Initial dense retrieval", "ranked list and score"),
        (460, 85, 170, 76, "High confidence", "use dense ranking"),
        (460, 245, 170, 76, "Low confidence", "generate query variants"),
        (690, 215, 165, 76, "Expansion probes", "traces and paraphrases"),
        (905, 160, 150, 76, "RRF fusion", "final ranking"),
    ]
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<text x="550" y="30" text-anchor="middle" font-family="Arial" font-size="18" fill="#222">Selective query-side expansion retrieval flow</text>',
        '<text x="550" y="55" text-anchor="middle" font-family="Arial" font-size="13" fill="#555">Expansion is applied only when the initial retrieval score is below the threshold.</text>',
    ]
    for x, y, w, h, title, subtitle in boxes:
        fill = "#f8fafc"
        stroke = "#94a3b8"
        if "Low" in title or "Trace" in title:
            fill = "#fff8f1"
            stroke = "#d28a57"
        if "RRF" in title:
            fill = "#f1f8f4"
            stroke = "#6fa982"
        parts.extend(
            [
                f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="{fill}" stroke="{stroke}" stroke-width="1.2"/>',
                f'<text x="{x + w/2}" y="{y + 31}" text-anchor="middle" font-family="Arial" font-size="14" fill="#222">{title}</text>',
                f'<text x="{x + w/2}" y="{y + 54}" text-anchor="middle" font-family="Arial" font-size="11" fill="#555">{subtitle}</text>',
            ]
        )
    arrows = [
        (200, 198, 245, 198, ""),
        (410, 198, 460, 123, "s1 >= tau"),
        (410, 198, 460, 283, "s1 < tau"),
        (630, 283, 690, 253, ""),
        (855, 253, 905, 198, ""),
        (630, 123, 905, 198, ""),
    ]
    for x1, y1, x2, y2, label in arrows:
        parts.append(
            f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#667085" stroke-width="1.4" marker-end="url(#arrow)"/>'
        )
        if label:
            safe_label = label.replace("<", "&lt;").replace(">", "&gt;")
            parts.append(
                f'<text x="{(x1+x2)/2}" y="{(y1+y2)/2 - 8}" text-anchor="middle" font-family="Arial" font-size="12" fill="#444">{safe_label}</text>'
            )
    parts.insert(
        1,
        '<defs><marker id="arrow" markerWidth="9" markerHeight="9" refX="8" refY="3" orient="auto" markerUnits="strokeWidth"><path d="M0,0 L0,6 L8,3 z" fill="#667085"/></marker></defs>',
    )
    parts.extend(
        [
            '<rect x="42" y="360" width="14" height="10" fill="#fff8f1" stroke="#d28a57"/>',
            '<text x="64" y="370" font-family="Arial" font-size="12" fill="#444">LLM expansion path</text>',
            '<rect x="220" y="360" width="14" height="10" fill="#f1f8f4" stroke="#6fa982"/>',
            '<text x="242" y="370" font-family="Arial" font-size="12" fill="#444">Rank fusion output</text>',
            '<rect x="405" y="360" width="14" height="10" fill="#f8fafc" stroke="#94a3b8"/>',
            '<text x="427" y="370" font-family="Arial" font-size="12" fill="#444">Existing retrieval index unchanged</text>',
            "</svg>",
        ]
    )
    svg = "\n".join(parts).replace(
        'font-family="Arial"', 'font-family="DejaVu Sans" font-weight="400"'
    )
    (FIGURES / "method_overview.svg").write_text(svg)


def convert_figures_to_png():
    method_overview_svg()
    for stem in ["method_overview", "recall_at_5", "gate_diagnostic", "threshold_sensitivity"]:
        svg = FIGURES / f"{stem}.svg"
        png = FIGURES / f"{stem}.png"
        try:
            subprocess.run(
                [
                    "convert",
                    "-density",
                    "220",
                    str(svg),
                    "-background",
                    "white",
                    "-alpha",
                    "remove",
                    "-alpha",
                    "off",
                    "-depth",
                    "8",
                    str(png),
                ],
                check=True,
            )
        except Exception:
            # Keep the SVG as a source artifact. The LaTeX paper can still use
            # the original PNGs generated by the experiment runner.
            pass
    for name in ["recall_comparison.png", "threshold_sensitivity.png"]:
        src = RESULTS / name
        if src.exists():
            shutil.copy2(src, FIGURES / name)


def write_references():
    refs = r"""@inproceedings{gao2023hyde,
  title={Precise Zero-Shot Dense Retrieval without Relevance Labels},
  author={Gao, Luyu and Ma, Xueguang and Lin, Jimmy and Callan, Jamie},
  booktitle={Proceedings of the 61st Annual Meeting of the Association for Computational Linguistics (Volume 1: Long Papers)},
  pages={1762--1777},
  year={2023},
  address={Toronto, Canada},
  publisher={Association for Computational Linguistics},
  doi={10.18653/v1/2023.acl-long.99},
  url={https://aclanthology.org/2023.acl-long.99/}
}

@inproceedings{cormack2009rrf,
  title={Reciprocal Rank Fusion Outperforms Condorcet and Individual Rank Learning Methods},
  author={Cormack, Gordon V. and Clarke, Charles L. A. and Buettcher, Stefan},
  booktitle={Proceedings of the 32nd International ACM SIGIR Conference on Research and Development in Information Retrieval},
  pages={758--759},
  year={2009},
  publisher={ACM},
  address={New York, NY, USA}
}

@inproceedings{jimenez2024swebench,
  title={SWE-bench: Can Language Models Resolve Real-World GitHub Issues?},
  author={Jimenez, Carlos E. and Yang, John and Wettig, Alexander and Yao, Shunyu and Pei, Kexin and Press, Ofir and Narasimhan, Karthik},
  booktitle={International Conference on Learning Representations},
  year={2024},
  url={https://openreview.net/forum?id=VTF8yNQM66}
}

@inproceedings{karpukhin2020dpr,
  title={Dense Passage Retrieval for Open-Domain Question Answering},
  author={Karpukhin, Vladimir and Oguz, Barlas and Min, Sewon and Lewis, Patrick and Wu, Ledell and Edunov, Sergey and Chen, Danqi and Yih, Wen-tau},
  booktitle={Proceedings of the 2020 Conference on Empirical Methods in Natural Language Processing (EMNLP)},
  pages={6769--6781},
  year={2020},
  address={Online},
  publisher={Association for Computational Linguistics},
  doi={10.18653/v1/2020.emnlp-main.550},
  url={https://aclanthology.org/2020.emnlp-main.550/}
}

@article{robertson2009bm25,
  title={The Probabilistic Relevance Framework: BM25 and Beyond},
  author={Robertson, Stephen and Zaragoza, Hugo},
  journal={Foundations and Trends in Information Retrieval},
  volume={3},
  number={4},
  pages={333--389},
  year={2009},
  doi={10.1561/1500000019}
}
"""
    (PAPER / "references.bib").write_text(refs)


def write_main_tex(summaries, error_analysis, measured_token_runs):
    selective = next((s for s in summaries if s["method"] == "Selective-QE"), {})
    dense = next((s for s in summaries if s["method"] == "Dense-Only"), {})
    hybrid = next((s for s in summaries if s["method"] == "Hybrid-RRF"), {})
    always = next((s for s in summaries if s["method"] == "Always-Expand"), {})
    random_budget = next(
        (s for s in summaries if s["method"] == "Random-Gated-Expansion"), {}
    )
    multiseed_path = ROOT / "results_multiseed" / "multiseed_report.json"
    multiseed = read_json(multiseed_path) if multiseed_path.exists() else {}
    multiseed_aggregate = multiseed.get("aggregate", {})
    multiseed_selective = multiseed_aggregate.get("Selective-QE", {})
    multiseed_dense = multiseed_aggregate.get("Dense-Only", {})
    multiseed_always = multiseed_aggregate.get("Always-Expand", {})
    multiseed_random = multiseed_aggregate.get("Random-Gated-Expansion", {})
    paired_path = ROOT / "results_multiseed" / "multiseed_paired_tests.json"
    paired_report = read_json(paired_path) if paired_path.exists() else {}
    paired_dense = next(
        (
            row
            for row in paired_report.get("rows", [])
            if row.get("baseline") == "Dense-Only"
        ),
        {},
    )
    paired_query_count = paired_dense.get("n_queries") or (
        500 * multiseed_count if multiseed_count else 0
    )
    gate_path = ROOT / "results_multiseed" / "multiseed_gate_validation.json"
    gate_report = read_json(gate_path) if gate_path.exists() else {}
    gate_aggregate = gate_report.get("aggregate", {})
    gate_paired_path = ROOT / "results_gate_calibration" / "gate_validation_paired_tests.json"
    gate_paired_report = read_json(gate_paired_path) if gate_paired_path.exists() else {}
    gate_paired_aggregate = gate_paired_report.get("aggregate", {})
    cross_seed_gate_path = ROOT / "results_gate_calibration" / "cross_seed_top1_gate.json"
    cross_seed_gate_report = read_json(cross_seed_gate_path) if cross_seed_gate_path.exists() else {}
    cross_seed_gate_aggregate = cross_seed_gate_report.get("aggregate", {})
    win_loss_path = ROOT / "results_multiseed" / "win_loss_analysis.json"
    win_loss_report = read_json(win_loss_path) if win_loss_path.exists() else {}
    win_loss_aggregate = win_loss_report.get("aggregate", {})
    multiseed_count = len(multiseed.get("requested_seeds", [])) or multiseed_selective.get("n_seeds")
    multiseed_phrase = f"{multiseed_count} independently rebuilt memory-index seeds"
    multiseed_sentence = ""
    if multiseed_selective and multiseed_dense:
        multiseed_sentence = (
            f" Across {multiseed_phrase}, SQE averages "
            f"{pct(multiseed_selective.get('recall@5_mean'))}\\% "
            f"Recall@5, compared with {pct(multiseed_dense.get('recall@5_mean'))}\\% "
            f"for dense retrieval, {pct(multiseed_always.get('recall@5_mean'))}\\% "
            f"for always-on expansion, and {pct(multiseed_random.get('recall@5_mean'))}\\% "
            f"for the executed random-gating budget control."
        )
    paired_dense_sentence = "the 95\\% interval crosses zero"
    if paired_dense:
        paired_dense_sentence = (
            f"the Recall@5 difference against dense retrieval is "
            f"{pct(paired_dense.get('delta'))} points with a 95\\% interval of "
            f"[{pct(paired_dense.get('ci_low'))}, {pct(paired_dense.get('ci_high'))}]"
        )
    win_loss_sentence = ""
    if win_loss_aggregate:
        win_loss_sentence = (
            f"At the query level, SQE recovers {win_loss_aggregate.get('selective_win')} "
            f"top-5 targets missed by Dense-Only, but loses "
            f"{win_loss_aggregate.get('selective_loss')} targets that Dense-Only retrieved, "
            f"for a net change of {win_loss_aggregate.get('net_wins')} over "
            f"{win_loss_aggregate.get('n_queries'):,} paired queries."
        )
    gate_validation_sentence = (
        "The selected thresholds improve mean test Recall@5 modestly over dense "
        "retrieval on the held-out halves"
    )
    if gate_aggregate:
        gate_validation_sentence = (
            f"The selected thresholds change mean test Recall@5 from "
            f"{pct(gate_aggregate.get('dense_test_recall_mean'))}\\% for dense "
            f"retrieval to {pct(gate_aggregate.get('test_recall_mean'))}\\%, "
            f"while expanding {pct(gate_aggregate.get('test_expansion_rate_mean'))}\\% "
            f"of held-out queries"
        )
    gate_paired_sentence = (
        "A paired held-out test still has an interval crossing zero."
    )
    if gate_paired_aggregate:
        gate_paired_sentence = (
            f"A paired held-out test over {gate_paired_aggregate.get('n_queries')} "
            f"query/seed pairs estimates a {pct(gate_paired_aggregate.get('delta'))} "
            f"point Recall@5 difference with a 95\\% interval of "
            f"[{pct(gate_paired_aggregate.get('ci_low'))}, "
            f"{pct(gate_paired_aggregate.get('ci_high'))}] and sign-flip "
            f"$p={gate_paired_aggregate.get('sign_flip_p'):.3f}$"
        )
    cross_seed_gate_sentence = "Cross-seed top-1-threshold validation is not available"
    if cross_seed_gate_aggregate:
        cross_seed_gate_sentence = (
            f"Leave-one-seed-out top-1 threshold selection obtains "
            f"{pct(cross_seed_gate_aggregate.get('gate_recall'))}\\% Recall@5 "
            f"versus {pct(cross_seed_gate_aggregate.get('dense_recall'))}\\% for "
            f"dense retrieval while expanding "
            f"{pct(cross_seed_gate_aggregate.get('expansion_rate'))}\\% of queries. "
            f"The paired difference is "
            f"{pct(cross_seed_gate_aggregate.get('delta_vs_dense'))} points with a "
            f"95\\% interval of [{pct(cross_seed_gate_aggregate.get('ci_low'))}, "
            f"{pct(cross_seed_gate_aggregate.get('ci_high'))}]"
        )
    if len(measured_token_runs) >= 5:
        measured_token_sentence = (
            "The measured-token reruns below provide provider-reported token usage "
            "for all expansion ablations."
        )
        measured_token_followup = (
            "These reruns execute the expansion methods without the expansion cache "
            "after adding usage logging for the OpenAI-compatible API. They are "
            "reported as cost measurements; the 500-query retrieval results above "
            "remain the main effectiveness comparison."
        )
    else:
        measured_token_sentence = (
            "The measured-token rerun below provides provider-reported token usage "
            "for Selective-QE only; the remaining expansion ablations still use "
            "estimated calls."
        )
        measured_token_followup = (
            "This rerun executes Selective-QE without the expansion cache after "
            "adding usage logging for the OpenAI-compatible API. It is reported "
            "as a cost measurement; the 500-query retrieval results above remain "
            "the main effectiveness comparison."
        )
    n_queries = get_n_queries(summaries)
    expansion_rate = selective.get(
        "expansion_trigger_rate", selective.get("expansion_rate", 0.0)
    )
    expansion_pct = pct(expansion_rate)
    expanded_count = int(round(expansion_rate * n_queries)) if n_queries else 0
    delta_dense = selective.get("recall@5", 0) - dense.get("recall@5", 0)
    delta_hybrid = selective.get("recall@5", 0) - hybrid.get("recall@5", 0)
    tex = rf"""\documentclass[10pt]{{article}}
\usepackage[letterpaper,margin=1in]{{geometry}}
\usepackage{{times}}
\usepackage{{microtype}}
\usepackage{{booktabs}}
\usepackage{{graphicx}}
\usepackage{{caption}}
\usepackage{{float}}
\usepackage[section]{{placeins}}
\usepackage[hidelinks]{{hyperref}}
\usepackage{{amsmath}}
\providecommand{{\Description}}[2][]{{}}
\captionsetup{{font=small,labelfont=bf,skip=6pt}}
\captionsetup[table]{{position=top,aboveskip=7pt,belowskip=9pt}}
\captionsetup[figure]{{position=bottom,aboveskip=7pt,belowskip=9pt}}
\setlength{{\textfloatsep}}{{20pt plus 3pt minus 2pt}}
\setlength{{\floatsep}}{{18pt plus 3pt minus 2pt}}
\setlength{{\intextsep}}{{18pt plus 3pt minus 2pt}}
\setlength{{\tabcolsep}}{{5pt}}
\renewcommand{{\arraystretch}}{{1.08}}
\emergencystretch=1em

\title{{Selective Query-Side Expansion for Long-Horizon Agent Memory Retrieval}}
\author{{Salomon DIEI\\School of Computer Science and Engineering, KOREATECH\\\texttt{{salomon@koreatech.ac.kr}}}}
\date{{}}

\begin{{document}}
\maketitle

\begin{{abstract}}
Long-horizon software-engineering agents store prior experience as execution traces,
tool calls, terminal outputs, and error messages, while later retrieval requests are
often phrased as natural-language questions. This representational mismatch can
prevent relevant memories from appearing in the retrieved context. We study
Selective Query-Side Expansion (SQE), a retrieval-time method that expands only
low-confidence queries into hypothetical execution traces and paraphrases, retrieves
each variant against the unchanged memory index, and combines ranked lists with
Reciprocal Rank Fusion. On a 5,000-episode SWE-smith memory store with {n_queries}
query-memory pairs, SQE obtains {pct(selective.get('recall@5'))}\% Recall@5,
compared with {pct(dense.get('recall@5'))}\% for dense retrieval and
{pct(hybrid.get('recall@5'))}\% for hybrid RRF.{multiseed_sentence} The current evidence supports SQE as a
cost-aware retrieval variant and shows higher Recall@5 than hybrid RRF, but it
does not establish a practically meaningful advantage over dense retrieval or a
clear advantage over the executed random-gating budget control. Downstream Pass@1 evaluation and human-audited query labels remain
necessary before making end-to-end agent-performance claims.
\end{{abstract}}

\section{{Introduction}}
Software-engineering agents accumulate long trajectories of observations,
commands, file edits, tests, and error traces. These records are useful only if
future agents can retrieve the relevant fragment when facing a related problem.
The retrieval problem is difficult because the memory and query distributions are
not written in the same style: a stored memory may contain a traceback or a patch
diff, while the future query may ask how an off-by-one line-number bug was fixed.

We study SQE as a retrieval-time intervention. The memory-writing
pipeline remains unchanged. At retrieval time, the method first runs dense
retrieval~\cite{{karpukhin2020dpr}} and treats the top-1 score as a confidence
signal. If the score is below a threshold, SQE generates execution-style hypothetical traces and paraphrased
queries, retrieves with these variants, and fuses the resulting rankings with
Reciprocal Rank Fusion~\cite{{cormack2009rrf}}. The method is related to
HyDE~\cite{{gao2023hyde}}, but is specialized to software-agent traces and is
applied selectively to bound generation cost.

\paragraph{{Contributions.}}
First, we formulate the trace-query mismatch problem for long-horizon software
agent memory. Second, we implement a selective expansion pipeline that combines
hypothetical traces, paraphrases, dense retrieval, sparse retrieval, and RRF.
Third, we provide a verified retrieval study on SWE-smith trajectories with
{multiseed_phrase}. Fourth, we identify the current
limitations: the confidence gate is weakly calibrated, the evaluation uses
generated retrieval queries, and downstream Pass@1 has not yet been measured.

\section{{Related Work}}
SQE builds on standard dense and sparse retrieval methods. Dense passage
retrieval maps queries and documents into a shared embedding space, while BM25
uses lexical term matching and remains a useful sparse baseline
~\cite{{karpukhin2020dpr,robertson2009bm25}}. The SQE experiments keep both
indexes fixed and modify only the query side, so the method can be evaluated as
a retrieval-time intervention rather than a memory-writing change.

Query expansion methods address vocabulary mismatch by rewriting or augmenting
the query before retrieval. HyDE generates a hypothetical document and embeds it
for zero-shot dense retrieval~\cite{{gao2023hyde}}. SQE uses the same broad idea
of hypothetical query-side expansion, but changes the unit of expansion to
software-agent execution traces and applies expansion only when the initial
retrieval score is low. The generated traces are retrieval probes rather than
claims that those executions actually occurred. Reciprocal Rank Fusion provides
a simple way to combine ranked lists from
the original query, generated traces, paraphrases, and sparse retrieval without
training a ranker~\cite{{cormack2009rrf}}.

For software-engineering agents, retrieval quality is only an intermediate
signal. SWE-bench-style evaluation measures whether an agent can produce a
patch that resolves a real issue~\cite{{jimenez2024swebench}}. The present paper
therefore reports retrieval metrics as a controlled diagnostic and treats
Pass@1 task success as required future evidence, not as an implied result.

\section{{Method}}
Let $M = \{{m_i\}}_{{i=1}}^N$ be a memory store of execution traces. Given a
query $q$, dense retrieval returns a ranked list $R_d(q)$ and a top-1 similarity
score $s_1(q)$. SQE expands the query if $s_1(q) < \tau$. For expanded queries,
an LLM generates $K$ hypothetical traces and $P$ paraphrases. Each variant is
retrieved against the same dense and BM25 sparse indexes~\cite{{robertson2009bm25}}. The ranked lists are fused
using RRF:
\[
  \mathrm{{score}}(m) = \sum_j \frac{{1}}{{k + \mathrm{{rank}}_j(m)}}.
\]
The current implementation uses $\tau=0.65$, $K=2$, $P=2$, and $k=60$.

Figure~\ref{{fig:method-overview}} shows the retrieval path. The high-confidence
branch uses the initial dense list. The low-confidence branch generates trace
probes and paraphrases, retrieves each query variant, and sends all ranked lists
to RRF.

\begin{{figure}}[!tbp]
\centering
\includegraphics[width=0.92\linewidth]{{figures/method_overview.png}}
\caption{{SQE retrieval flow. The method changes only the query side at retrieval time; the memory store and index are left unchanged.}}
\Description{{Flow diagram showing dense retrieval, a confidence gate, query-side trace and paraphrase expansion for low-confidence queries, parallel retrieval, and Reciprocal Rank Fusion.}}
\label{{fig:method-overview}}
\end{{figure}}

\section{{Experimental Setup}}
\begin{{table}}[!tbp]
\caption{{Experiment configuration and release placeholders.}}
\label{{tab:setup}}
\centering
\small
\input{{tables/experiment_manifest}}
\end{{table}}

Table~\ref{{tab:setup}} summarizes the current retrieval benchmark. The
experiment uses generated natural-language queries paired with
target memories. This setup isolates retrieval, but it does not yet establish
downstream task success. A complete evaluation requires verified human-audit
labels and agent Pass@1 evaluation on SWE-bench-style tasks~\cite{{jimenez2024swebench}}.
Random-Gated-Expansion is an executed control: it runs the same
expansion-and-retrieval code as SQE, but replaces the confidence gate with seeded
random expansion decisions at a comparable expansion rate and stores the
resulting per-query rows in JSONL.

\section{{Results}}
We treat the 8-seed aggregate in Table~\ref{{tab:multiseed}} as the primary
retrieval evidence. Table~\ref{{tab:seed42}} is retained as a detailed audit
anchor because its per-query rows, cost traces, figures, and case analyses are
all regenerated by the artifact pipeline.

\begin{{table}}[!tbp]
\caption{{Seed-42 retrieval results used as the detailed audit anchor.}}
\label{{tab:seed42}}
\centering
\small
\input{{tables/main_results}}
\end{{table}}

In the seed-42 run, SQE changes Recall@5 by {100*delta_dense:.1f} percentage points relative to dense-only
retrieval and {100*delta_hybrid:+.1f} percentage points relative to hybrid RRF
in the current run. Recall@1 is lower than dense retrieval. This indicates that
the current SQE configuration has higher Recall@5 than hybrid RRF,
but does not improve the strongest dense baseline. The always-on ablation shows
that expanding every query can hurt Recall@1, so selectivity is mainly a
cost-control mechanism in this run.

\subsection{{Multi-seed retrieval aggregate}}
\begin{{table}}[!tbp]
\caption{{Aggregate retrieval results over independent memory-index seeds.}}
\label{{tab:multiseed}}
\centering
\small
\input{{tables/multiseed_summary}}
\end{{table}}

The aggregate uses {multiseed_count} independently sampled memory stores of 5,000 episodes each and rebuilt
indices. SQE has slightly higher mean Recall@5 than dense retrieval, but the
paired effect against dense retrieval is small and Recall@1 remains below dense
retrieval. The result is therefore evidence for a modest retrieval-only
candidate-set difference under this setup, not strong evidence of an end-to-end
agent improvement. Figure~\ref{{fig:recall}} reports the
seed-42 method comparison, while Table~\ref{{tab:paired-multiseed}} reports the
paired aggregate uncertainty.

\begin{{table}}[!tbp]
\caption{{Paired bootstrap tests over all independent memory-index seeds.}}
\label{{tab:paired-multiseed}}
\centering
\scriptsize
\input{{tables/multiseed_paired_tests}}
\end{{table}}

The paired bootstrap over all {paired_query_count:,} query rows estimates a
small Recall@5 improvement over dense retrieval: {paired_dense_sentence}. The
same test shows larger gains over hybrid RRF and trace-only expansion, but not
a clear advantage over the executed random-gating budget control.
{win_loss_sentence} Table~\ref{{tab:win-loss}} reports the corresponding
win/loss counts.

\begin{{table}}[!tbp]
\caption{{Query-level top-5 wins and losses for SQE against Dense-Only.}}
\label{{tab:win-loss}}
\centering
\small
\input{{tables/win_loss_analysis}}
\end{{table}}

Table~\ref{{tab:cases}} lists deterministic examples from the seed-42 retrieval
rows. They are illustrative only and are not additional aggregate metrics.

\begin{{table}}[!tbp]
\caption{{Seed-42 examples where SQE and Dense-Only differ at top-5.}}
\label{{tab:cases}}
\centering
\scriptsize
\resizebox{{\linewidth}}{{!}}{{\input{{tables/case_analysis}}}}
\end{{table}}

\subsection{{Expansion cost}}
\begin{{table}}[!tbp]
\caption{{Estimated expansion cost for each retrieval method.}}
\label{{tab:cost}}
\centering
\small
\input{{tables/cost_summary}}
\end{{table}}

The completed ablations estimate generation cost by counting LLM calls rather
than provider-reported tokens. Selective-QE uses fewer expansion calls than
always-on expansion because it expands {expansion_pct}\% of queries.
{measured_token_sentence} Table~\ref{{tab:cost}} reports estimated calls, and
Table~\ref{{tab:tokens}} reports the measured-token reruns.

\subsection{{Measured token cost}}
\begin{{table}}[!tbp]
\caption{{Provider-reported token usage for measured-token reruns.}}
\label{{tab:tokens}}
\centering
\scriptsize
\input{{tables/measured_token_cost}}
\end{{table}}

{measured_token_followup}

\subsection{{Paired uncertainty}}
\begin{{table}}[!tbp]
\caption{{Seed-42 paired bootstrap uncertainty.}}
\label{{tab:paired-seed42}}
\centering
\scriptsize
\input{{tables/paired_tests}}
\end{{table}}

The confidence intervals in Table~\ref{{tab:paired-seed42}} are paired bootstrap intervals over the {n_queries} current
queries. They should be treated as diagnostics, not final statistical evidence,
because the evaluation set is small and generated from the same trace corpus.

\begin{{figure}}[!tbp]
\centering
\includegraphics[width=0.95\linewidth]{{figures/recall_at_5.png}}
\caption{{Recall@5 comparison across completed retrieval methods for seed 42. SQE is highlighted; the other bars are baselines or ablations.}}
\Description{{Bar chart comparing seed-42 Recall at 5 for dense retrieval, BM25, Hybrid-RRF, paraphrases, HyDE traces, always-expand, random-gated expansion, and SQE.}}
\label{{fig:recall}}
\end{{figure}}

\section{{Gate Diagnostics}}
\begin{{table}}[!tbp]
\caption{{Seed-42 gate diagnostic split by expansion decision.}}
\label{{tab:gate}}
\centering
\small
\input{{tables/gate_diagnostics}}
\end{{table}}

Table~\ref{{tab:gate}} shows that the gate expands {expanded_count} of
{n_queries} queries. In the current run, expanded queries do not
outperform non-expanded queries at Recall@5, so top-1 dense score is not yet a
well-calibrated selector. This is a central weakness for the current method claim.
Stronger gates should include
top-1/top-2 margin, dense-sparse agreement, score concentration, or a learned
policy.

\subsection{{Post-hoc threshold sweep}}
\begin{{table}}[!tbp]
\caption{{Seed-42 post-hoc threshold sweep.}}
\label{{tab:threshold-sweep}}
\centering
\small
\input{{tables/threshold_sweep}}
\end{{table}}

Table~\ref{{tab:threshold-sweep}} and Figure~\ref{{fig:threshold}} reuse the
completed dense-only and always-expand result files, so the sweep is
diagnostic rather than a tuned validation result. It indicates that the fixed
0.65 threshold is not optimal on this split, and threshold selection needs a
separate validation protocol.

\subsection{{Split validation check}}
\begin{{table}}[!tbp]
\caption{{Seed-42 split validation check for threshold selection.}}
\label{{tab:validation-threshold}}
\centering
\scriptsize
\input{{tables/validation_threshold}}
\end{{table}}

Table~\ref{{tab:validation-threshold}} reports a minimal guard against all-query
tuning: we select a threshold on the first half of the query IDs and report it on the second half. This split is small and
should not be treated as final evidence, but it makes the calibration weakness
explicit.

\subsection{{Multi-seed gate validation}}
\begin{{table}}[!tbp]
\caption{{Held-out gate validation over independent memory-index seeds.}}
\label{{tab:multiseed-gate}}
\centering
\scriptsize
\input{{tables/multiseed_gate_validation}}
\end{{table}}

Table~\ref{{tab:multiseed-gate}} repeats the split-threshold procedure for each completed
independent memory-index seed. It recombines only executed dense-only and
always-expand rows. {gate_validation_sentence}, but the result is still too
small to support a strong gate-calibration claim. {gate_paired_sentence}.
Table~\ref{{tab:gate-paired}} reports the paired test.

\begin{{table}}[!tbp]
\caption{{Paired uncertainty for held-out gate validation.}}
\label{{tab:gate-paired}}
\centering
\scriptsize
\input{{tables/gate_validation_paired_tests}}
\end{{table}}

\subsection{{Cross-seed top-1 gate}}
\begin{{table}}[!tbp]
\caption{{Leave-one-seed-out top-1 gate validation.}}
\label{{tab:cross-seed-gate}}
\centering
\scriptsize
\input{{tables/cross_seed_top1_gate}}
\end{{table}}

Table~\ref{{tab:cross-seed-gate}} selects a top-1-score threshold on two independent memory-index
seeds and evaluates it on the held-out seed. It recombines only executed
dense-only and always-expand rows. {cross_seed_gate_sentence}. The interval
still crosses zero, so this result is useful as a calibration diagnostic rather
than a strong effectiveness claim.

\subsection{{BM25-agreement gate variants}}
\begin{{table}}[!tbp]
\caption{{Held-out BM25-agreement gate variants.}}
\label{{tab:gate-variants}}
\centering
\scriptsize
\input{{tables/gate_variant_diagnostics}}
\end{{table}}

Table~\ref{{tab:gate-variants}} selects among score-only and BM25-agreement gate variants on
the first half of each seed and evaluates on the second half. It uses only
executed dense-only, BM25-only, and always-expand rows. The result is diagnostic:
the selected variants do not provide enough evidence to remove the gate
calibration limitation. Figure~\ref{{fig:gate-diagnostic}} shows why the
top-1 score is a weak selector in the current experiment.

\subsection{{Gate headroom}}
\begin{{table}}[!tbp]
\caption{{Held-out oracle headroom for a perfect expansion gate.}}
\label{{tab:gate-headroom}}
\centering
\scriptsize
\input{{tables/gate_headroom_diagnostics}}
\end{{table}}

Table~\ref{{tab:gate-headroom}} recombines executed dense-only and always-expand rows
on the second half of each independent memory seed. The oracle column is not an
implementable method; it shows the maximum possible Recall@5 if a perfect gate
could expand exactly the queries helped by always-on expansion. The small gap
between helpful and harmful expansion cases explains why the current confidence
gate is difficult to calibrate.

\begin{{figure}}[!tbp]
\centering
\includegraphics[width=0.95\linewidth]{{figures/gate_diagnostic.png}}
\caption{{Diagnostic relationship between dense top-1 score bins and final SQE Recall@5. The bins do not separate easy and hard cases cleanly enough for a strong gate claim.}}
\Description{{Line and bar diagnostic showing that dense top-1 score bins do not provide a clean monotonic separation between higher and lower Recall at 5 outcomes.}}
\label{{fig:gate-diagnostic}}
\end{{figure}}

\begin{{figure}}[!tbp]
\centering
\includegraphics[width=0.95\linewidth]{{figures/threshold_sensitivity.png}}
\caption{{Post-hoc Recall@5 under different expansion thresholds for seed 42. The figure is diagnostic because the threshold is evaluated on completed result rows.}}
\Description{{Threshold sweep chart showing post-hoc Recall at 5 as the expansion threshold changes for seed 42, with the fixed operating threshold marked for comparison.}}
\label{{fig:threshold}}
\end{{figure}}

\section{{Limitations and Next Experiments}}
The current evidence is preliminary. The retrieval experiment now includes
{multiseed_phrase}, but the improvement over dense
retrieval is small and there is no downstream Pass@1 measurement. Simple
held-out gate diagnostics using top-1 score, dense margin, score concentration,
and BM25 agreement have not removed the calibration weakness. A stronger
submission needs externally validated gate calibration, human-audited query
labels, and end-to-end agent success measurements.

\section{{Threats to Validity}}
\paragraph{{Construct validity.}}
Recall@K measures whether the target memory appears in the retrieved set, not
whether an agent can use that memory to fix a software task. The current
retrieval metrics are therefore intermediate evidence. Pass@1 task success and
human query-quality labels are required before claiming agent-level gains.

\paragraph{{Data validity.}}
The evaluation queries are generated from the same memory corpus used to define
target memories. This gives a controlled retrieval benchmark, but it may not
match how users or agents phrase future memory requests. The human-audit packet
is prepared, but no reviewer labels have been collected yet.

\paragraph{{Method validity.}}
The selective gate uses top-1 dense score, which is weakly calibrated in the
current experiments. Several held-out diagnostics test alternative gates, but
their intervals still cross zero. The current results should be read as a
cost-controlled retrieval study rather than evidence that the gate is solved.

\paragraph{{External validity.}}
The experiments use SWE-smith software-engineering traces, BAAI/bge-m3
embeddings, and Qwen3.6-35B-A3B for expansion. Results may change with other
agent logs, embedding models, generators, memory-writing policies, or task
domains.

\section{{Reproducibility}}
The intended public repository URL is: \texttt{{TODO: add GitHub URL}}.
The intended Hugging Face dataset URL is:
\texttt{{TODO: add Hugging Face dataset URL}}.
All scripts used for the current retrieval experiment are in the project
directory. Raw seed-42 results are stored under \nolinkurl{{{RESULTS.name}/}},
and generated paper artifacts are stored under \texttt{{paper/}}. Independent
memory-index seed results are stored under the
\nolinkurl{{results_500_memory_seed42/}} through
\nolinkurl{{results_500_memory_seed49/}} directories.
The verifier \nolinkurl{{scripts/07_verify_experiment.py}} checks that evaluation
targets are present in both the memory store and the index, recomputes retrieval
metrics from detailed JSONL files, and verifies required paper artifacts.
The dataset-release helper \nolinkurl{{scripts/33_prepare_hf_dataset_release.py}}
packages existing memory stores, evaluation pairs, retrieval summaries,
diagnostics, and the unlabeled human-audit packet into a local Hugging
Face-ready directory. It does not create human labels, downstream Pass@1 rows,
or synthetic replacement data.
The code-release helper \nolinkurl{{scripts/34_prepare_github_code_release.py}}
prepares a local GitHub-ready code package with scripts, paper source, configs,
documentation, and optional lightweight summaries. It does not upload to
GitHub and does not package raw memory stores, detailed query rows, downstream
task-outcome rows, or human labels.
The table inventory \nolinkurl{{paper/table_inventory.json}} records the source
files for each active table; deprecated diagnostic tables are excluded from the
paper claims.

\section{{Conclusion}}
SQE is a retrieval-time query-expansion method for long-horizon software-agent
memory. In the current experiments, it reduces expansion calls relative to
always-on expansion and improves Recall@5 over Hybrid-RRF and trace-only
expansion, but it remains essentially tied with dense retrieval and the executed
random-gating budget control. The present evidence is best read as a
verified retrieval study and a negative calibration result for the
current top-1-score gate. A stronger paper requires human-audited query labels
and downstream Pass@1 task-success measurements before making agent-level
performance claims.

\bibliographystyle{{plain}}
\bibliography{{references}}
\end{{document}}
"""
    tex = tex.replace(r"\begin{table}[t]", r"\begin{table}[!tbp]")
    tex = tex.replace(r"\begin{figure}[t]", r"\begin{figure}[!tbp]")
    (PAPER / "main.tex").write_text(tex)
    table_inputs = sorted(set(re.findall(r"\\input\{tables/([^}]+)\}", tex)))
    figure_inputs = sorted(
        set(re.findall(r"\\includegraphics\[[^\]]+\]\{figures/([^}]+)\}", tex))
    )
    all_tables = sorted(path.stem for path in TABLES.glob("*.tex"))
    active_table_sources = {
        "cost_summary": [
            "results_500_memory_seed42/dense_only_detailed.jsonl",
            "results_500_memory_seed42/always_expand_detailed.jsonl",
            "results_500_memory_seed42/proposed_detailed.jsonl",
            "results_500_memory_seed42/random_budget_detailed.jsonl",
        ],
        "case_analysis": [
            "data_500_memory_seed42/eval_pairs.jsonl",
            "results_500_memory_seed42/dense_only_detailed.jsonl",
            "results_500_memory_seed42/proposed_detailed.jsonl",
        ],
        "experiment_manifest": [
            "data_500_memory_seed42/dataset_manifest.json",
        ],
        "gate_diagnostics": [
            "results_500_memory_seed42/proposed_detailed.jsonl",
            "results_500_memory_seed42/full_report_v2.json",
        ],
        "gate_headroom_diagnostics": [
            "results_gate_calibration/gate_headroom_diagnostics.json",
        ],
        "gate_variant_diagnostics": [
            "results_gate_calibration/gate_variant_diagnostics.json",
        ],
        "main_results": [
            "results_500_memory_seed42/baselines_summary.json",
            "results_500_memory_seed42/dense_only_detailed.jsonl",
            "results_500_memory_seed42/bm25_only_detailed.jsonl",
            "results_500_memory_seed42/hybrid_rrf_detailed.jsonl",
            "results_500_memory_seed42/paraphrases_only_detailed.jsonl",
            "results_500_memory_seed42/traces_only_detailed.jsonl",
            "results_500_memory_seed42/always_expand_detailed.jsonl",
            "results_500_memory_seed42/random_budget_detailed.jsonl",
            "results_500_memory_seed42/proposed_detailed.jsonl",
        ],
        "measured_token_cost": [
            "results_tokenmeasured_500_seed42/always_expand_tokenmeasured500_summary.json",
            "results_tokenmeasured_500_seed42/paraphrases_only_tokenmeasured500_summary.json",
            "results_tokenmeasured_500_seed42/random_budget_tokenmeasured500_summary.json",
            "results_tokenmeasured_500_seed42/selective_tokenmeasured500_summary.json",
            "results_tokenmeasured_500_seed42/traces_only_tokenmeasured500_summary.json",
        ],
        "multiseed_gate_validation": [
            "results_multiseed/multiseed_gate_validation.json",
        ],
        "gate_validation_paired_tests": [
            "results_gate_calibration/gate_validation_paired_tests.json",
        ],
        "cross_seed_top1_gate": [
            "results_gate_calibration/cross_seed_top1_gate.json",
        ],
        "multiseed_paired_tests": [
            "results_multiseed/multiseed_paired_tests.json",
        ],
        "multiseed_summary": [
            "results_multiseed/multiseed_report.json",
        ],
        "paired_tests": [
            "results_500_memory_seed42/dense_only_detailed.jsonl",
            "results_500_memory_seed42/hybrid_rrf_detailed.jsonl",
            "results_500_memory_seed42/always_expand_detailed.jsonl",
            "results_500_memory_seed42/random_budget_detailed.jsonl",
            "results_500_memory_seed42/proposed_detailed.jsonl",
        ],
        "threshold_sweep": [
            "results_500_memory_seed42/dense_only_detailed.jsonl",
            "results_500_memory_seed42/always_expand_detailed.jsonl",
        ],
        "validation_threshold": [
            "results_500_memory_seed42/dense_only_detailed.jsonl",
            "results_500_memory_seed42/always_expand_detailed.jsonl",
        ],
        "win_loss_analysis": [
            "results_multiseed/win_loss_analysis.json",
        ],
    }
    inventory = {
        "note": (
            "Generated from paper/main.tex. Active tables are imported by the "
            "paper. Retained tables are present on disk but not imported and "
            "should not be cited as active paper evidence unless provenance is "
            "updated."
        ),
        "active_tables": table_inputs,
        "active_table_sources": {
            name: active_table_sources.get(name, []) for name in table_inputs
        },
        "retained_tables": sorted(name for name in all_tables if name not in table_inputs),
        "missing_active_tables": sorted(name for name in table_inputs if name not in all_tables),
        "active_figures": figure_inputs,
    }
    (PAPER / "table_inventory.json").write_text(json.dumps(inventory, indent=2) + "\n")


def main():
    global RESULTS, PAPER, TABLES, FIGURES
    parser = argparse.ArgumentParser()
    parser.add_argument("--results_dir", type=str, default=str(RESULTS))
    parser.add_argument("--paper_dir", type=str, default=str(PAPER))
    parser.add_argument("--data_dir", type=str, default=str(ROOT / "data_500_memory_seed42"))
    args = parser.parse_args()
    RESULTS = Path(args.results_dir)
    PAPER = Path(args.paper_dir)
    TABLES = PAPER / "tables"
    FIGURES = PAPER / "figures"

    PAPER.mkdir(exist_ok=True)
    TABLES.mkdir(parents=True, exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)

    summaries = [add_cost_summary(enrich_summary(dict(s))) for s in load_summaries()]
    measured_token_runs = load_measured_token_runs()
    proposed_rows = read_jsonl(RESULTS / "proposed_detailed.jsonl")
    old_report = read_json(RESULTS / "full_report.json") if (RESULTS / "full_report.json").exists() else {}
    error_analysis = old_report.get("error_analysis") or compute_gate_error_analysis(proposed_rows, top_k=5)

    for s in summaries:
        rows = read_jsonl(detailed_path_for_method(s["method"]))
        ci = bootstrap_ci(rows, top_k=5) if rows else None
        if ci:
            s["recall@5_ci95"] = ci

    report = {
        "summaries": summaries,
        "error_analysis": error_analysis,
        "threshold_sweep": threshold_sweep(),
        "validation_threshold_check": validation_threshold_check(),
        "measured_token_runs": measured_token_runs,
        "paired_bootstrap_recall5": {
            baseline: paired_bootstrap_delta("Selective-QE", baseline, top_k=5)
            for baseline in [
                "Dense-Only",
                "Hybrid-RRF",
                "Always-Expand",
                "Random-Gated-Expansion",
                "Paraphrases-Only",
                "HyDE-Traces-Only",
            ]
            if paired_bootstrap_delta("Selective-QE", baseline, top_k=5) is not None
        },
        "caveats": [
            f"Current run has {get_n_queries(summaries)} generated queries from one seed.",
            "Pass@1 has not been measured.",
            "The top-1 score gate requires calibration on larger data.",
        ],
    }
    (RESULTS / "full_report_v2.json").write_text(json.dumps(report, indent=2))

    write_main_results_table(summaries)
    write_error_table(report)
    write_cost_table(summaries)
    write_measured_token_table(measured_token_runs)
    write_significance_table(report["paired_bootstrap_recall5"])
    write_case_analysis_table(args.data_dir)
    write_threshold_table(report["threshold_sweep"])
    write_validation_threshold_table(report["validation_threshold_check"])
    write_manifest_table(summaries, args.data_dir)
    bar_svg(summaries)
    gate_svg(proposed_rows)
    threshold_svg(report["threshold_sweep"])
    convert_figures_to_png()
    write_references()
    write_main_tex(summaries, error_analysis, measured_token_runs)

    print("Wrote paper artifacts to", PAPER)
    print("Wrote enriched report to", RESULTS / "full_report_v2.json")


if __name__ == "__main__":
    main()
