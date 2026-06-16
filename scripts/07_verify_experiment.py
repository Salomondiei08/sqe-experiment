"""
Verify the corrected SQE retrieval experiment.

This script checks the failure modes that matter for the paper:
  - evaluation targets are present in the memory store and index;
  - result rows have the expected query count;
  - summary metrics match the detailed JSONL files;
  - generated paper artifacts exist.

It uses only the Python standard library.
"""

import argparse
import struct
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path


METHOD_DETAIL_FILES = {
    "Dense-Only": "dense_only_detailed.jsonl",
    "BM25-Only": "bm25_only_detailed.jsonl",
    "Hybrid-RRF": "hybrid_rrf_detailed.jsonl",
    "Paraphrases-Only": "paraphrases_only_detailed.jsonl",
    "HyDE-Traces-Only": "traces_only_detailed.jsonl",
    "Always-Expand": "always_expand_detailed.jsonl",
    "Random-Gated-Expansion": "random_budget_detailed.jsonl",
    "Selective-QE": "proposed_detailed.jsonl",
}

ALLOWED_TABLE_INPUTS = {
    "experiment_manifest",
    "case_analysis",
    "main_results",
    "cost_summary",
    "measured_token_cost",
    "paired_tests",
    "gate_diagnostics",
    "threshold_sweep",
    "validation_threshold",
    "multiseed_summary",
    "multiseed_paired_tests",
    "multiseed_gate_validation",
    "gate_validation_paired_tests",
    "cross_seed_top1_gate",
    "gate_variant_diagnostics",
    "gate_headroom_diagnostics",
    "win_loss_analysis",
}

DEPRECATED_TABLE_INPUTS = {
    "random_budget_" + "simulation",
    "measured_token_pilot",
}

EXPECTED_MULTI_SEEDS = [42, 43, 44, 45, 46, 47, 48, 49]
EXPECTED_PAIRED_BASELINES = {
    "Dense-Only",
    "Hybrid-RRF",
    "Always-Expand",
    "Random-Gated-Expansion",
    "Paraphrases-Only",
    "HyDE-Traces-Only",
}


def read_json(path):
    with open(path) as f:
        return json.load(f)


def canonical_method_name(method):
    return method


def read_jsonl(path):
    rows = []
    with open(path) as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def png_dimensions(path):
    with open(path, "rb") as f:
        header = f.read(24)
    if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    width, height = struct.unpack(">II", header[16:24])
    return width, height


def verify_human_audit(root, eval_rows, failures, warnings, report):
    audit_dir = root / "human_audit"
    manifest_path = audit_dir / "human_audit_manifest.json"
    jsonl_path = audit_dir / "human_audit_queries.jsonl"
    csv_path = audit_dir / "human_audit_queries.csv"
    readme_path = audit_dir / "README.md"
    report["checks"]["human_audit"] = {}

    missing = [
        str(p)
        for p in [manifest_path, jsonl_path, csv_path, readme_path]
        if not p.exists()
    ]
    if missing:
        warnings.append(f"Human audit packet is incomplete: {missing}")
        report["checks"]["human_audit"]["present"] = False
        return

    manifest = read_json(manifest_path)
    rows = read_jsonl(jsonl_path)
    report["checks"]["human_audit"] = {
        "present": True,
        "manifest": manifest,
        "n_rows": len(rows),
    }

    if manifest.get("n_audit_queries") != len(rows):
        failures.append("human_audit_manifest.json n_audit_queries does not match JSONL rows")
    if manifest.get("n_source_queries") != len(eval_rows):
        failures.append("human_audit_manifest.json n_source_queries does not match eval_pairs")

    eval_ids = {r["query_id"] for r in eval_rows}
    audit_ids = [r.get("query_id") for r in rows]
    if len(audit_ids) != len(set(audit_ids)):
        failures.append("human audit packet contains duplicate query_id values")
    absent = sorted(qid for qid in audit_ids if qid not in eval_ids)
    if absent:
        failures.append(f"human audit packet query IDs not found in eval_pairs: {absent[:5]}")

    reviewer_fields = [
        "is_query_clear",
        "does_target_answer_query",
        "is_query_too_specific_or_copied",
        "reviewer_notes",
    ]
    filled = [
        r.get("query_id", "")
        for r in rows
        if any(str(r.get(field, "")).strip() for field in reviewer_fields)
    ]
    report["checks"]["human_audit"]["filled_reviewer_rows"] = len(filled)
    if filled:
        failures.append(
            "human audit reviewer fields are no longer blank; do not treat them as "
            f"unlabeled data without documenting the labeling process: {filled[:5]}"
        )


def verify_multiseed_artifacts(root, failures, report):
    results_dir = root / "results_multiseed"
    summary_path = results_dir / "multiseed_report.json"
    paired_path = results_dir / "multiseed_paired_tests.json"
    gate_path = results_dir / "multiseed_gate_validation.json"
    report["checks"]["multiseed_artifacts"] = {}

    missing = [str(p) for p in [summary_path, paired_path, gate_path] if not p.exists()]
    if missing:
        failures.append(f"Missing multiseed result files: {missing}")
        report["checks"]["multiseed_artifacts"]["present"] = False
        return

    summary = read_json(summary_path)
    paired = read_json(paired_path)
    gate = read_json(gate_path)
    report["checks"]["multiseed_artifacts"] = {
        "present": True,
        "summary_path": str(summary_path),
        "paired_path": str(paired_path),
        "gate_path": str(gate_path),
        "summary_seed_family": summary.get("seed_family"),
        "paired_seed_family": paired.get("seed_family"),
        "gate_seed_family": gate.get("seed_family"),
    }

    for name, artifact in [
        ("multiseed_report.json", summary),
        ("multiseed_paired_tests.json", paired),
        ("multiseed_gate_validation.json", gate),
    ]:
        if artifact.get("seed_family") != "independent_memory":
            failures.append(
                f"{name} seed_family is {artifact.get('seed_family')}, "
                "expected independent_memory for active paper artifacts"
            )

    if summary.get("requested_seeds") != EXPECTED_MULTI_SEEDS:
        failures.append(
            "multiseed_report.json requested_seeds changed from "
            f"{EXPECTED_MULTI_SEEDS}: {summary.get('requested_seeds')}"
        )
    if summary.get("n_complete_seeds") != len(EXPECTED_MULTI_SEEDS):
        failures.append(
            "multiseed_report.json does not contain the expected completed seeds: "
            f"{summary.get('n_complete_seeds')}"
        )
    seed_reports = summary.get("seed_reports", [])
    if len(seed_reports) != len(EXPECTED_MULTI_SEEDS):
        failures.append(f"multiseed_report.json has {len(seed_reports)} seed reports")
    for seed_report in seed_reports:
        seed = seed_report.get("seed")
        expected_dir = root / f"results_500_memory_seed{seed}"
        if seed not in EXPECTED_MULTI_SEEDS:
            failures.append(f"Unexpected seed in multiseed_report.json: {seed}")
        if seed in EXPECTED_MULTI_SEEDS and seed_report.get("results_dir") != str(expected_dir):
            failures.append(
                f"Seed {seed} result directory in multiseed_report.json is "
                f"{seed_report.get('results_dir')}, expected {expected_dir}"
            )
        if seed_report.get("status") != "complete":
            failures.append(f"Seed {seed} is not complete in multiseed_report.json")
        methods = seed_report.get("methods", {})
        missing_methods = sorted(set(METHOD_DETAIL_FILES) - set(methods))
        if missing_methods:
            failures.append(f"Seed {seed} missing methods in multiseed_report.json: {missing_methods}")
        for method, metrics in methods.items():
            if metrics.get("n_queries") != 500:
                failures.append(
                    f"Seed {seed} {method} has n_queries={metrics.get('n_queries')}, expected 500"
                )

    if paired.get("seeds") != EXPECTED_MULTI_SEEDS:
        failures.append(
            "multiseed_paired_tests.json seeds changed from "
            f"{EXPECTED_MULTI_SEEDS}: {paired.get('seeds')}"
        )
    if paired.get("metric") != "Recall@5":
        failures.append(f"multiseed_paired_tests.json metric is {paired.get('metric')}")
    paired_rows = paired.get("rows", [])
    paired_baselines = {row.get("baseline") for row in paired_rows}
    missing_baselines = sorted(EXPECTED_PAIRED_BASELINES - paired_baselines)
    if missing_baselines:
        failures.append(f"Missing paired-test baselines: {missing_baselines}")
    for row in paired_rows:
        expected_queries = 500 * len(EXPECTED_MULTI_SEEDS)
        if row.get("n_queries") != expected_queries:
            failures.append(
                f"Paired test {row.get('baseline')} has n_queries={row.get('n_queries')}, "
                f"expected {expected_queries}"
            )

    if gate.get("seeds") != EXPECTED_MULTI_SEEDS:
        failures.append(
            "multiseed_gate_validation.json seeds changed from "
            f"{EXPECTED_MULTI_SEEDS}: {gate.get('seeds')}"
        )
    if gate.get("metric") != "Recall@5":
        failures.append(f"multiseed_gate_validation.json metric is {gate.get('metric')}")
    gate_rows = gate.get("seed_reports", [])
    if len(gate_rows) != len(EXPECTED_MULTI_SEEDS):
        failures.append(f"multiseed_gate_validation.json has {len(gate_rows)} seed reports")
    for row in gate_rows:
        seed = row.get("seed")
        expected_dir = root / f"results_500_memory_seed{seed}"
        if seed not in EXPECTED_MULTI_SEEDS:
            failures.append(f"Unexpected seed in multiseed_gate_validation.json: {seed}")
        if seed in EXPECTED_MULTI_SEEDS and row.get("results_dir") != str(expected_dir):
            failures.append(
                f"Seed {seed} result directory in multiseed_gate_validation.json is "
                f"{row.get('results_dir')}, expected {expected_dir}"
            )
        if row.get("n_train") != 250 or row.get("n_test") != 250:
            failures.append(
                f"Gate validation seed {seed} has train/test "
                f"{row.get('n_train')}/{row.get('n_test')}, expected 250/250"
            )
    if gate.get("aggregate", {}).get("n_seeds") != len(EXPECTED_MULTI_SEEDS):
        failures.append("multiseed_gate_validation.json aggregate does not cover the expected seeds")


def verify_random_gated_execution(root, failures, report):
    """Verify that the random-gated baseline is backed by executed row files."""
    checks = {}
    for seed in EXPECTED_MULTI_SEEDS:
        results_dir = root / f"results_500_memory_seed{seed}"
        detail_path = results_dir / "random_budget_detailed.jsonl"
        summary_path = results_dir / "random_budget_summary.json"
        seed_check = {
            "detail_path": str(detail_path),
            "summary_path": str(summary_path),
            "detail_present": detail_path.exists(),
            "summary_present": summary_path.exists(),
        }
        checks[str(seed)] = seed_check

        if not detail_path.exists():
            failures.append(f"Missing executed Random-Gated-Expansion rows: {detail_path}")
            continue
        rows = read_jsonl(detail_path)
        seed_check["n_rows"] = len(rows)
        if len(rows) != 500:
            failures.append(
                f"{detail_path} has {len(rows)} rows, expected 500 executed query rows"
            )

        bad_modes = [
            row.get("query_id", f"row_{idx}")
            for idx, row in enumerate(rows)
            if row.get("meta", {}).get("mode") != "random_budget"
        ]
        seed_check["bad_mode_rows"] = bad_modes[:10]
        if bad_modes:
            failures.append(
                f"{detail_path} contains rows without meta.mode=random_budget: {bad_modes[:5]}"
            )

        expanded_rows = [row for row in rows if row.get("meta", {}).get("expanded")]
        nonexpanded_rows = [row for row in rows if not row.get("meta", {}).get("expanded")]
        seed_check["n_expanded"] = len(expanded_rows)
        seed_check["n_nonexpanded"] = len(nonexpanded_rows)
        if not expanded_rows or not nonexpanded_rows:
            failures.append(
                f"{detail_path} does not contain both expanded and non-expanded executed rows"
            )

        bad_expanded = []
        for row in expanded_rows:
            meta = row.get("meta", {})
            if (
                meta.get("n_hypothetical_traces_generated", 0) < 1
                or meta.get("n_paraphrases_generated", 0) < 1
                or meta.get("n_ranked_lists_fused", 0) <= 1
                or meta.get("estimated_llm_calls", 0) < 1
            ):
                bad_expanded.append(row.get("query_id", ""))
        seed_check["bad_expanded_rows"] = bad_expanded[:10]
        if bad_expanded:
            failures.append(
                f"{detail_path} has expanded random-gated rows without executed "
                f"expansion metadata: {bad_expanded[:5]}"
            )

        bad_nonexpanded = []
        for row in nonexpanded_rows:
            meta = row.get("meta", {})
            if (
                meta.get("n_hypothetical_traces_generated", 0) != 0
                or meta.get("n_paraphrases_generated", 0) != 0
                or meta.get("estimated_llm_calls", 0) != 0
            ):
                bad_nonexpanded.append(row.get("query_id", ""))
        seed_check["bad_nonexpanded_rows"] = bad_nonexpanded[:10]
        if bad_nonexpanded:
            failures.append(
                f"{detail_path} has non-expanded random-gated rows with expansion "
                f"metadata: {bad_nonexpanded[:5]}"
            )

        if not summary_path.exists():
            failures.append(f"Missing Random-Gated-Expansion summary: {summary_path}")
            continue
        summary = read_json(summary_path)
        seed_check["summary_method"] = summary.get("method")
        seed_check["summary_mode"] = summary.get("config", {}).get("mode")
        if summary.get("method") != "Random-Gated-Expansion":
            failures.append(
                f"{summary_path} method is {summary.get('method')}, "
                "expected Random-Gated-Expansion"
            )
        if summary.get("config", {}).get("mode") != "random_budget":
            failures.append(
                f"{summary_path} config.mode is {summary.get('config', {}).get('mode')}, "
                "expected random_budget"
            )
        if summary.get("n_queries") != len(rows):
            failures.append(
                f"{summary_path} n_queries={summary.get('n_queries')} does not "
                f"match {len(rows)} detailed rows"
            )
        if summary.get("n_expanded") != len(expanded_rows):
            failures.append(
                f"{summary_path} n_expanded={summary.get('n_expanded')} does not "
                f"match {len(expanded_rows)} detailed rows"
            )

    report["checks"]["random_gated_execution"] = checks


def load_summaries(results_dir):
    summaries = {}
    baseline_path = results_dir / "baselines_summary.json"
    if baseline_path.exists():
        for item in read_json(baseline_path):
            item["method"] = canonical_method_name(item["method"])
            summaries[item["method"]] = item
    for path in sorted(results_dir.glob("*_summary.json")):
        if path.name == "baselines_summary.json":
            continue
        item = read_json(path)
        item["method"] = canonical_method_name(item["method"])
        summaries[item["method"]] = item
    return summaries


def row_target(row):
    return row.get("target_id") or row.get("target_episode_id")


def row_hit_at(row, top_k):
    return row_target(row) in row.get("retrieved_ids", [])[:top_k]


def target_rank(row):
    target = row_target(row)
    retrieved = row.get("retrieved_ids", [])
    if target in retrieved:
        return str(retrieved.index(target) + 1)
    return ">10"


def latex_text(text):
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


def compute_metrics(rows):
    n = len(rows)
    out = {"n_queries": n}
    if not rows:
        return out
    max_depth = max(len(r.get("retrieved_ids", [])) for r in rows)
    for k in [1, 5, 10]:
        if max_depth >= k:
            out[f"recall@{k}"] = (
                sum(row_target(r) in r.get("retrieved_ids", [])[:k] for r in rows) / n
            )
    rr = 0.0
    for row in rows:
        target = row_target(row)
        retrieved = row.get("retrieved_ids", [])
        if target in retrieved:
            rr += 1.0 / (retrieved.index(target) + 1)
    out["mrr"] = rr / n
    out["max_retrieved_depth"] = max_depth
    if any("meta" in row for row in rows):
        out["expansion_rate"] = sum(
            1 for row in rows if row.get("meta", {}).get("expanded")
        ) / n
    return out


def almost_equal(a, b, tol=1e-9):
    return abs(float(a) - float(b)) <= tol


def pct(value):
    return f"{100.0 * value:.1f}"


def signed_pct(value):
    return f"{100.0 * value:+.1f}"


def pct_pm(mean_value, std_value):
    return f"{pct(mean_value)} $\\pm$ {pct(std_value)}"


def verify_main_results_table(paper_dir, method_metrics, failures, report):
    table_path = paper_dir / "tables" / "main_results.tex"
    if not table_path.exists():
        return
    text = table_path.read_text(errors="replace")
    missing_rows = []
    for method, metrics in method_metrics.items():
        expansion = (
            pct(metrics["expansion_rate"])
            if "expansion_rate" in metrics
            else "--"
        )
        expected = (
            f"{method} & {pct(metrics['recall@1'])} & {pct(metrics['recall@5'])} "
            f"& {pct(metrics['recall@10'])} & {pct(metrics['mrr'])} & {expansion}"
        )
        if expected not in text:
            missing_rows.append(expected)
    report["checks"]["main_results_table_missing_expected_rows"] = missing_rows
    if missing_rows:
        failures.append(
            "paper/tables/main_results.tex does not match recomputed metrics: "
            f"{missing_rows[:3]}"
        )


def verify_main_tex_headline_metrics(paper_dir, method_metrics, n_eval, failures, report):
    main_path = paper_dir / "main.tex"
    if not main_path.exists():
        return
    text = main_path.read_text(errors="replace")
    normalized = re.sub(r"\s+", " ", text)
    dense = method_metrics.get("Dense-Only", {})
    hybrid = method_metrics.get("Hybrid-RRF", {})
    selective = method_metrics.get("Selective-QE", {})
    expected_snippets = [
        f"with {n_eval} query-memory pairs",
        (
            f"SQE obtains {pct(selective.get('recall@5'))}\\% Recall@5, "
            f"compared with {pct(dense.get('recall@5'))}\\% for dense retrieval "
            f"and {pct(hybrid.get('recall@5'))}\\% for hybrid RRF"
        ),
        "Random-Gated-Expansion is an executed control",
    ]
    missing = [snippet for snippet in expected_snippets if snippet not in normalized]
    stale_patterns = [
        "with 100 query-memory pairs",
        "SQE changes Recall@5 from 67.0\\%",
    ]
    stale_hits = [pattern for pattern in stale_patterns if pattern in normalized]
    report["checks"]["main_tex_missing_headline_metric_snippets"] = missing
    report["checks"]["main_tex_stale_headline_metric_snippets"] = stale_hits
    if missing:
        failures.append(
            "paper/main.tex headline metrics do not match active result files: "
            f"{missing}"
        )
    if stale_hits:
        failures.append(
            "paper/main.tex contains stale headline metrics from deprecated runs: "
            f"{stale_hits}"
        )


def verify_multiseed_summary_table(root, paper_dir, failures, report):
    report_path = root / "results_multiseed" / "multiseed_report.json"
    table_path = paper_dir / "tables" / "multiseed_summary.tex"
    if not report_path.exists() or not table_path.exists():
        return
    multiseed = read_json(report_path)
    aggregate = multiseed.get("aggregate", {})
    text = table_path.read_text(errors="replace")
    methods = [
        "Dense-Only",
        "Hybrid-RRF",
        "Always-Expand",
        "Random-Gated-Expansion",
        "Selective-QE",
    ]
    missing_rows = []
    for method in methods:
        item = aggregate.get(method, {})
        if not item:
            missing_rows.append(f"{method}: missing aggregate")
            continue
        expected = (
            f"{method} & {item.get('n_seeds', 0)} "
            f"& {pct_pm(item['recall@1_mean'], item['recall@1_std'])} "
            f"& {pct_pm(item['recall@5_mean'], item['recall@5_std'])} "
            f"& {pct_pm(item['recall@10_mean'], item['recall@10_std'])}"
        )
        if expected not in text:
            missing_rows.append(expected)
    report["checks"]["multiseed_summary_table_missing_expected_rows"] = missing_rows
    if missing_rows:
        failures.append(
            "paper/tables/multiseed_summary.tex does not match multiseed_report.json: "
            f"{missing_rows[:3]}"
        )


def fmt_signed_pct(value):
    prefix = "+" if value >= 0 else ""
    return f"{prefix}{100.0 * value:.1f}"


def verify_multiseed_paired_table(root, paper_dir, failures, report):
    report_path = root / "results_multiseed" / "multiseed_paired_tests.json"
    table_path = paper_dir / "tables" / "multiseed_paired_tests.tex"
    if not report_path.exists() or not table_path.exists():
        return
    paired = read_json(report_path)
    text = table_path.read_text(errors="replace")
    missing_rows = []
    for row in paired.get("rows", []):
        expected = (
            f"{row['baseline']} & {row['n_queries']} & "
            f"{fmt_signed_pct(row['delta'])} & "
            f"[{fmt_signed_pct(row['ci_low'])}, {fmt_signed_pct(row['ci_high'])}] & "
            f"{row['p_value']:.3f}"
        )
        if expected not in text:
            missing_rows.append(expected)
    report["checks"]["multiseed_paired_table_missing_expected_rows"] = missing_rows
    if missing_rows:
        failures.append(
            "paper/tables/multiseed_paired_tests.tex does not match "
            f"multiseed_paired_tests.json: {missing_rows[:3]}"
        )


def verify_multiseed_gate_table(root, paper_dir, failures, report):
    report_path = root / "results_multiseed" / "multiseed_gate_validation.json"
    table_path = paper_dir / "tables" / "multiseed_gate_validation.tex"
    if not report_path.exists() or not table_path.exists():
        return
    gate = read_json(report_path)
    text = table_path.read_text(errors="replace")
    missing_rows = []
    for row in gate.get("seed_reports", []):
        expected = (
            f"{row['seed']} & {row['threshold']:.2f} & "
            f"{pct(row['train_recall'])} & "
            f"{pct(row['test_recall'])} & "
            f"{pct(row['dense_test_recall'])} & "
            f"{pct(row['test_expansion_rate'])}"
        )
        if expected not in text:
            missing_rows.append(expected)
    aggregate = gate.get("aggregate", {})
    if aggregate:
        expected = (
            "Mean & -- & "
            f"{pct(aggregate['train_recall_mean'])} & "
            f"{pct(aggregate['test_recall_mean'])} & "
            f"{pct(aggregate['dense_test_recall_mean'])} & "
            f"{pct(aggregate['test_expansion_rate_mean'])}"
        )
        if expected not in text:
            missing_rows.append(expected)
    report["checks"]["multiseed_gate_table_missing_expected_rows"] = missing_rows
    if missing_rows:
        failures.append(
            "paper/tables/multiseed_gate_validation.tex does not match "
            f"multiseed_gate_validation.json: {missing_rows[:3]}"
        )


def verify_gate_variant_table(root, paper_dir, failures, report):
    report_path = root / "results_gate_calibration" / "gate_variant_diagnostics.json"
    table_path = paper_dir / "tables" / "gate_variant_diagnostics.tex"
    if not report_path.exists() or not table_path.exists():
        return
    gate = read_json(report_path)
    text = table_path.read_text(errors="replace")
    missing_rows = []
    for row in gate.get("seed_reports", []):
        expected = (
            f"{row['seed']} & {latex_text(row['policy'])} & {row['threshold']:.2f} & "
            f"{pct(row['test_recall'])} & "
            f"{pct(row['dense_test_recall'])} & "
            f"{pct(row['test_expansion_rate'])}"
        )
        if expected not in text:
            missing_rows.append(expected)
    aggregate = gate.get("aggregate", {})
    if aggregate:
        expected = (
            "Mean & -- & -- & "
            f"{pct(aggregate['test_recall_mean'])} & "
            f"{pct(aggregate['dense_test_recall_mean'])} & "
            f"{pct(aggregate['test_expansion_rate_mean'])}"
        )
        if expected not in text:
            missing_rows.append(expected)
    report["checks"]["gate_variant_table_missing_expected_rows"] = missing_rows
    if missing_rows:
        failures.append(
            "paper/tables/gate_variant_diagnostics.tex does not match "
            f"gate_variant_diagnostics.json: {missing_rows[:3]}"
        )


def verify_gate_headroom_table(root, paper_dir, failures, report):
    report_path = root / "results_gate_calibration" / "gate_headroom_diagnostics.json"
    table_path = paper_dir / "tables" / "gate_headroom_diagnostics.tex"
    if not report_path.exists() or not table_path.exists():
        return
    headroom = read_json(report_path)
    text = table_path.read_text(errors="replace")
    missing_rows = []
    for row in headroom.get("seed_reports", []):
        expected = (
            f"{row['seed']} & "
            f"{pct(row['dense_recall'])} & "
            f"{pct(row['always_expand_recall'])} & "
            f"{pct(row['oracle_recall'])} & "
            f"{pct(row['helpful_rate'])} & "
            f"{pct(row['harmful_rate'])}"
        )
        if expected not in text:
            missing_rows.append(expected)
    aggregate = headroom.get("aggregate", {})
    if aggregate:
        expected = (
            "Mean & "
            f"{pct(aggregate['dense_recall_mean'])} & "
            f"{pct(aggregate['always_expand_recall_mean'])} & "
            f"{pct(aggregate['oracle_recall_mean'])} & "
            f"{pct(aggregate['helpful_rate_mean'])} & "
            f"{pct(aggregate['harmful_rate_mean'])}"
        )
        if expected not in text:
            missing_rows.append(expected)
    report["checks"]["gate_headroom_table_missing_expected_rows"] = missing_rows
    if missing_rows:
        failures.append(
            "paper/tables/gate_headroom_diagnostics.tex does not match "
            f"gate_headroom_diagnostics.json: {missing_rows[:3]}"
        )


def verify_gate_feature_table(root, paper_dir, failures, report):
    report_path = root / "results_gate_calibration" / "gate_feature_diagnostics.json"
    table_path = paper_dir / "tables" / "gate_feature_diagnostics.tex"
    if not report_path.exists() or not table_path.exists():
        return
    gate = read_json(report_path)
    text = table_path.read_text(errors="replace")
    missing_rows = []
    for row in gate.get("seed_reports", []):
        expected = (
            f"{row['seed']} & {latex_text(row['policy'])} & {row['threshold']:.3f} & "
            f"{pct(row['test_recall'])} & "
            f"{pct(row['dense_test_recall'])} & "
            f"{pct(row['test_expansion_rate'])}"
        )
        if expected not in text:
            missing_rows.append(expected)
    aggregate = gate.get("aggregate", {})
    if aggregate:
        expected = (
            "Mean & -- & -- & "
            f"{pct(aggregate['test_recall_mean'])} & "
            f"{pct(aggregate['dense_test_recall_mean'])} & "
            f"{pct(aggregate['test_expansion_rate_mean'])}"
        )
        if expected not in text:
            missing_rows.append(expected)
    report["checks"]["gate_feature_table_missing_expected_rows"] = missing_rows
    if missing_rows:
        failures.append(
            "paper/tables/gate_feature_diagnostics.tex does not match "
            f"gate_feature_diagnostics.json: {missing_rows[:3]}"
        )


def verify_cross_seed_top1_gate_table(root, paper_dir, failures, report):
    report_path = root / "results_gate_calibration" / "cross_seed_top1_gate.json"
    table_path = paper_dir / "tables" / "cross_seed_top1_gate.tex"
    if not report_path.exists() or not table_path.exists():
        return
    gate = read_json(report_path)
    text = table_path.read_text(errors="replace")
    missing_rows = []
    for row in gate.get("seed_reports", []):
        train_seeds = ",".join(str(seed) for seed in row["train_seeds"])
        expected = (
            f"{row['test_seed']} & {train_seeds} & {row['threshold']:.2f} & "
            f"{pct(row['gate_recall'])} & "
            f"{pct(row['dense_recall'])} & "
            f"{signed_pct(row['delta_vs_dense'])} & "
            f"{pct(row['expansion_rate'])}"
        )
        if expected not in text:
            missing_rows.append(expected)
    aggregate = gate.get("aggregate", {})
    if aggregate:
        expected = (
            "All & -- & -- & "
            f"{pct(aggregate['gate_recall'])} & "
            f"{pct(aggregate['dense_recall'])} & "
            f"{signed_pct(aggregate['delta_vs_dense'])} & "
            f"{pct(aggregate['expansion_rate'])}"
        )
        if expected not in text:
            missing_rows.append(expected)
    report["checks"]["cross_seed_top1_gate_table_missing_expected_rows"] = missing_rows
    if missing_rows:
        failures.append(
            "paper/tables/cross_seed_top1_gate.tex does not match "
            f"cross_seed_top1_gate.json: {missing_rows[:3]}"
        )


def verify_win_loss_table(root, paper_dir, failures, report):
    report_path = root / "results_multiseed" / "win_loss_analysis.json"
    table_path = paper_dir / "tables" / "win_loss_analysis.tex"
    if not report_path.exists() or not table_path.exists():
        return
    win_loss = read_json(report_path)
    text = table_path.read_text(errors="replace")
    missing_rows = []
    for row in win_loss.get("rows", []):
        expected = (
            f"seed {row['seed']} & {row['n_queries']} & {row['both_hit']} & "
            f"{row['selective_win']} & {row['selective_loss']} & "
            f"{row['both_miss']} & {row['net_wins']}"
        )
        if expected not in text:
            missing_rows.append(expected)
    aggregate = win_loss.get("aggregate", {})
    if aggregate:
        expected = (
            f"All & {aggregate['n_queries']} & {aggregate['both_hit']} & "
            f"{aggregate['selective_win']} & {aggregate['selective_loss']} & "
            f"{aggregate['both_miss']} & {aggregate['net_wins']}"
        )
        if expected not in text:
            missing_rows.append(expected)
    report["checks"]["win_loss_table_missing_expected_rows"] = missing_rows
    if missing_rows:
        failures.append(
            "paper/tables/win_loss_analysis.tex does not match "
            f"win_loss_analysis.json: {missing_rows[:3]}"
        )


def verify_measured_token_table(root, paper_dir, failures, report):
    measured_dir = root / "results_tokenmeasured_500_seed42"
    table_path = paper_dir / "tables" / "measured_token_cost.tex"
    summary_paths = sorted(measured_dir.glob("*_tokenmeasured500_summary.json"))
    if not summary_paths:
        pilot = root / "results_tokenpilot_50_seed42" / "selective_tokenpilot50_summary.json"
        summary_paths = [pilot] if pilot.exists() else []
    if not summary_paths or not table_path.exists():
        return
    text = table_path.read_text(errors="replace")
    expected_rows = []
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

    for summary_path in summary_paths:
        summary = read_json(summary_path)
        expected_rows.append(
            f"{measured_label(summary)} & "
            f"{pct(summary.get('expansion_trigger_rate', 0.0))} & "
            f"{summary.get('avg_actual_llm_calls_per_query', 0.0):.2f} & "
            f"{summary.get('avg_prompt_tokens_per_query', 0.0):.1f} & "
            f"{summary.get('avg_total_tokens_per_query', 0.0):.1f} & "
            f"{summary.get('avg_latency_seconds_per_query', 0.0):.2f}"
        )
    missing_rows = [row for row in expected_rows if row not in text]
    report["checks"]["measured_token_table_missing_expected_rows"] = missing_rows
    if missing_rows:
        failures.append(
            "paper/tables/measured_token_cost.tex does not match "
            f"measured token summaries: {missing_rows[:3]}"
        )


def verify_case_analysis_table(data_dir, results_dir, paper_dir, failures, report):
    table_path = paper_dir / "tables" / "case_analysis.tex"
    if not table_path.exists():
        return
    eval_rows = {r.get("query_id"): r for r in read_jsonl(data_dir / "eval_pairs.jsonl")}
    dense_rows = {r.get("query_id"): r for r in read_jsonl(results_dir / "dense_only_detailed.jsonl")}
    sqe_rows = {r.get("query_id"): r for r in read_jsonl(results_dir / "proposed_detailed.jsonl")}
    differing = []
    for query_id in sorted(set(dense_rows) & set(sqe_rows)):
        dense_hit = row_hit_at(dense_rows[query_id], 5)
        sqe_hit = row_hit_at(sqe_rows[query_id], 5)
        if dense_hit == sqe_hit:
            continue
        label = "SQE gain" if sqe_hit else "SQE loss"
        differing.append((label, query_id, dense_rows[query_id], sqe_rows[query_id]))

    selected = []
    for label in ["SQE gain", "SQE loss"]:
        selected.extend([row for row in differing if row[0] == label][:2])

    text = table_path.read_text(errors="replace")
    expected_rows = []
    for label, query_id, dense_row, sqe_row in selected:
        query = eval_rows.get(query_id, {}).get("query") or sqe_row.get("query") or dense_row.get("query", "")
        expanded = "yes" if sqe_row.get("meta", {}).get("expanded") else "no"
        expected_rows.append(
            f"{latex_text(label)} & {latex_text(query_id)} & "
            f"{latex_text(target_rank(dense_row))} & {latex_text(target_rank(sqe_row))} & "
            f"{expanded} & {latex_text(truncate_text(query))}"
        )
    missing_rows = [row for row in expected_rows if row not in text]
    report["checks"]["case_analysis_table_missing_expected_rows"] = missing_rows
    report["checks"]["case_analysis_expected_rows"] = expected_rows
    if missing_rows:
        failures.append(
            "paper/tables/case_analysis.tex does not match seed-42 detailed rows: "
            f"{missing_rows[:3]}"
        )


def extract_pdf_text(pdf_path):
    if not pdf_path.exists() or not shutil.which("pdftotext"):
        return ""
    try:
        result = subprocess.run(
            ["pdftotext", str(pdf_path), "-"],
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception:
        return ""
    return result.stdout


def get_pdf_pages(pdf_path):
    if not pdf_path.exists() or not shutil.which("pdfinfo"):
        return None
    try:
        result = subprocess.run(
            ["pdfinfo", str(pdf_path)],
            check=False,
            capture_output=True,
            text=True,
        )
    except Exception:
        return None
    if result.returncode != 0:
        return None
    for line in result.stdout.splitlines():
        if line.startswith("Pages:"):
            try:
                return int(line.split(":", 1)[1].strip())
            except ValueError:
                return None
    return None


def main(args):
    root = Path(__file__).resolve().parents[1]
    data_dir = Path(args.data_dir)
    index_dir = Path(args.index_dir)
    results_dir = Path(args.results_dir)
    paper_dir = Path(args.paper_dir)

    failures = []
    warnings = []
    report = {
        "data_dir": str(data_dir),
        "index_dir": str(index_dir),
        "results_dir": str(results_dir),
        "paper_dir": str(paper_dir),
        "checks": {},
    }

    required_data = ["memory_store.jsonl", "eval_pairs.jsonl", "dataset_manifest.json"]
    for name in required_data:
        if not (data_dir / name).exists():
            failures.append(f"Missing data file: {data_dir / name}")

    required_index = ["id_map.json", "dense.faiss", "dense_embeddings.npy", "bm25.pkl"]
    for name in required_index:
        if not (index_dir / name).exists():
            failures.append(f"Missing index file: {index_dir / name}")

    if failures:
        report["failures"] = failures
        print(json.dumps(report, indent=2))
        return 1

    manifest = read_json(data_dir / "dataset_manifest.json")
    memory_rows = read_jsonl(data_dir / "memory_store.jsonl")
    eval_rows = read_jsonl(data_dir / "eval_pairs.jsonl")
    memory_ids = {r["episode_id"] for r in memory_rows}
    index_ids = set(read_json(index_dir / "id_map.json"))
    eval_targets = [r["target_episode_id"] for r in eval_rows]

    report["checks"]["manifest"] = manifest
    report["checks"]["memory_sha256"] = sha256_file(data_dir / "memory_store.jsonl")
    report["checks"]["n_memory"] = len(memory_rows)
    report["checks"]["n_eval"] = len(eval_rows)
    report["checks"]["n_index_ids"] = len(index_ids)
    report["checks"]["eval_targets_in_memory"] = sum(t in memory_ids for t in eval_targets)
    report["checks"]["eval_targets_in_index"] = sum(t in index_ids for t in eval_targets)

    if manifest.get("eval_source") != "memory":
        failures.append(f"Expected eval_source=memory, found {manifest.get('eval_source')}")
    if len(memory_rows) != manifest.get("n_memory"):
        failures.append("memory_store count does not match dataset_manifest.json")
    if len(eval_rows) != manifest.get("n_eval_generated"):
        failures.append("eval_pairs count does not match dataset_manifest.json")
    if report["checks"]["eval_targets_in_memory"] != len(eval_rows):
        failures.append("Some eval targets are absent from memory_store.jsonl")
    if report["checks"]["eval_targets_in_index"] != len(eval_rows):
        failures.append("Some eval targets are absent from index id_map.json")

    summaries = load_summaries(results_dir)
    report["checks"]["methods"] = {}
    for method, filename in METHOD_DETAIL_FILES.items():
        path = results_dir / filename
        if not path.exists():
            failures.append(f"Missing detailed result for {method}: {path}")
            continue
        rows = read_jsonl(path)
        metrics = compute_metrics(rows)
        report["checks"]["methods"][method] = metrics
        if metrics["n_queries"] != len(eval_rows):
            failures.append(f"{method} has {metrics['n_queries']} rows, expected {len(eval_rows)}")
        summary = summaries.get(method)
        if not summary:
            failures.append(f"Missing summary for {method}")
            continue
        for key, value in summary.items():
            if key.startswith("recall@") and key in metrics and not almost_equal(value, metrics[key]):
                failures.append(f"{method} {key} summary={value} detailed={metrics[key]}")
        if "n_queries" in summary and summary["n_queries"] != metrics["n_queries"]:
            failures.append(f"{method} n_queries summary mismatch")
        if "n_expanded" in summary:
            expanded = sum(1 for r in rows if r.get("meta", {}).get("expanded"))
            if summary["n_expanded"] != expanded:
                failures.append(f"{method} n_expanded summary={summary['n_expanded']} detailed={expanded}")

    if results_dir.name == "results_500_memory_seed42":
        verify_main_results_table(paper_dir, report["checks"]["methods"], failures, report)
        verify_main_tex_headline_metrics(
            paper_dir,
            report["checks"]["methods"],
            len(eval_rows),
            failures,
            report,
        )
        verify_multiseed_summary_table(root, paper_dir, failures, report)
        verify_multiseed_paired_table(root, paper_dir, failures, report)
        verify_multiseed_gate_table(root, paper_dir, failures, report)
        verify_gate_variant_table(root, paper_dir, failures, report)
        verify_gate_headroom_table(root, paper_dir, failures, report)
        verify_gate_feature_table(root, paper_dir, failures, report)
        verify_cross_seed_top1_gate_table(root, paper_dir, failures, report)
        verify_win_loss_table(root, paper_dir, failures, report)
        verify_measured_token_table(root, paper_dir, failures, report)
        verify_case_analysis_table(data_dir, results_dir, paper_dir, failures, report)
    else:
        report["checks"]["paper_table_consistency_scope"] = (
            "skipped for non-paper-source seed results"
        )

    paper_files = [
        "main.tex",
        "main.pdf",
        "main_conference_preview.tex",
        "main_conference_preview.pdf",
        "references.bib",
        "tables/main_results.tex",
        "tables/cost_summary.tex",
        "tables/measured_token_cost.tex",
        "tables/paired_tests.tex",
        "tables/gate_diagnostics.tex",
        "tables/threshold_sweep.tex",
        "tables/validation_threshold.tex",
        "tables/experiment_manifest.tex",
        "tables/case_analysis.tex",
        "tables/multiseed_summary.tex",
        "tables/multiseed_paired_tests.tex",
        "tables/multiseed_gate_validation.tex",
        "tables/gate_variant_diagnostics.tex",
        "tables/gate_headroom_diagnostics.tex",
        "tables/gate_feature_diagnostics.tex",
        "tables/cross_seed_top1_gate.tex",
        "tables/win_loss_analysis.tex",
        "figures/method_overview.png",
        "figures/recall_at_5.png",
        "figures/gate_diagnostic.png",
        "figures/threshold_sensitivity.png",
    ]
    missing_paper = [name for name in paper_files if not (paper_dir / name).exists()]
    report["checks"]["paper_files_present"] = len(paper_files) - len(missing_paper)
    if missing_paper:
        failures.append(f"Missing paper artifacts: {missing_paper}")

    figure_checks = {}
    for name in [
        "figures/method_overview.png",
        "figures/recall_at_5.png",
        "figures/gate_diagnostic.png",
        "figures/threshold_sensitivity.png",
    ]:
        path = paper_dir / name
        if not path.exists():
            continue
        dims = png_dimensions(path)
        figure_checks[name] = {
            "bytes": path.stat().st_size,
            "dimensions": list(dims) if dims else None,
        }
        if not dims:
            failures.append(f"Figure is not a valid PNG: {path}")
        elif dims[0] < 100 or dims[1] < 100 or path.stat().st_size < 1000:
            failures.append(f"Figure appears too small or empty: {path} {figure_checks[name]}")
    report["checks"]["figure_pngs"] = figure_checks

    conference_preview_audit_path = root / "CONFERENCE_PREVIEW_AUDIT.json"
    conference_preview_checks = {
        "present": conference_preview_audit_path.exists(),
        "clean_for_preview": False,
        "is_official_venue_template": None,
        "is_experiment_evidence": None,
        "failures": [],
        "pdf_pages": None,
        "pdf_bytes": None,
    }
    if conference_preview_audit_path.exists():
        conference_preview = read_json(conference_preview_audit_path)
        conference_preview_checks.update(
            {
                "clean_for_preview": conference_preview.get("clean_for_preview"),
                "is_official_venue_template": conference_preview.get(
                    "is_official_venue_template"
                ),
                "is_experiment_evidence": conference_preview.get("is_experiment_evidence"),
                "failures": conference_preview.get("failures", []),
                "pdf_pages": conference_preview.get("pdf_pages"),
                "pdf_bytes": conference_preview.get("pdf_bytes"),
            }
        )
        preview_pdf = paper_dir / "main_conference_preview.pdf"
        if not preview_pdf.exists():
            failures.append("paper/main_conference_preview.pdf is missing")
        elif preview_pdf.stat().st_size != conference_preview.get("pdf_bytes"):
            failures.append(
                "CONFERENCE_PREVIEW_AUDIT.json pdf_bytes does not match "
                "paper/main_conference_preview.pdf"
            )
        if conference_preview.get("clean_for_preview") is not True:
            failures.append("Conference preview audit is not clean for preview")
        if conference_preview.get("is_official_venue_template") is not False:
            failures.append("Conference preview must not claim official venue-template status")
        if conference_preview.get("is_experiment_evidence") is not False:
            failures.append("Conference preview must be marked as non-evidence")
        if conference_preview.get("failures"):
            failures.append(
                "Conference preview audit contains failures: "
                f"{conference_preview.get('failures')}"
            )
    else:
        failures.append("Missing CONFERENCE_PREVIEW_AUDIT.json")
    report["checks"]["conference_preview"] = conference_preview_checks

    paper_style_audit_path = root / "PAPER_STYLE_AUDIT.json"
    paper_style_checks = {
        "present": paper_style_audit_path.exists(),
        "clean": False,
        "failures": [],
        "warnings": [],
        "n_figures": None,
        "n_tables": None,
        "em_dash_count": None,
        "forbidden_unicode_punctuation_counts": {},
        "hype_or_vague_phrase_hits": [],
        "manual_bold_count": None,
    }
    if paper_style_audit_path.exists():
        paper_style = read_json(paper_style_audit_path)
        paper_style_checks.update(
            {
                "clean": paper_style.get("clean"),
                "failures": paper_style.get("failures", []),
                "warnings": paper_style.get("warnings", []),
                "n_figures": paper_style.get("n_figures"),
                "n_tables": paper_style.get("n_tables"),
                "em_dash_count": paper_style.get("em_dash_count"),
                "forbidden_unicode_punctuation_counts": paper_style.get(
                    "forbidden_unicode_punctuation_counts", {}
                ),
                "hype_or_vague_phrase_hits": paper_style.get(
                    "hype_or_vague_phrase_hits", []
                ),
                "guarded_phrases": paper_style.get("guarded_phrases", []),
                "missing_required_guarded_phrases": [],
                "required_layout_controls": paper_style.get(
                    "required_layout_controls", []
                ),
                "missing_layout_controls": paper_style.get(
                    "missing_layout_controls", []
                ),
                "manual_bold_count": paper_style.get("manual_bold_count"),
            }
        )
        required_guarded_phrases = {"extense", "extensive", "extensively", "robust"}
        guarded_phrases = set(paper_style.get("guarded_phrases", []))
        missing_guarded_phrases = sorted(required_guarded_phrases - guarded_phrases)
        paper_style_checks["missing_required_guarded_phrases"] = (
            missing_guarded_phrases
        )
        if missing_guarded_phrases:
            failures.append(
                "PAPER_STYLE_AUDIT.json missing required guarded phrases: "
                f"{missing_guarded_phrases}"
            )
        required_layout_controls = {
            r"\captionsetup{font=small,labelfont=bf,skip=6pt}",
            r"\captionsetup[table]{position=top,aboveskip=7pt,belowskip=9pt}",
            r"\captionsetup[figure]{position=bottom,aboveskip=7pt,belowskip=9pt}",
            r"\setlength{\textfloatsep}{20pt plus 3pt minus 2pt}",
            r"\setlength{\floatsep}{18pt plus 3pt minus 2pt}",
            r"\setlength{\intextsep}{18pt plus 3pt minus 2pt}",
            r"\setlength{\tabcolsep}{5pt}",
            r"\renewcommand{\arraystretch}{1.08}",
            r"\emergencystretch=1em",
        }
        layout_controls = set(paper_style.get("required_layout_controls", []))
        missing_required_layout_controls = sorted(
            required_layout_controls - layout_controls
        )
        paper_style_checks["missing_required_layout_controls"] = (
            missing_required_layout_controls
        )
        if missing_required_layout_controls:
            failures.append(
                "PAPER_STYLE_AUDIT.json missing required layout controls: "
                f"{missing_required_layout_controls}"
            )
        if paper_style.get("missing_layout_controls"):
            failures.append(
                "PAPER_STYLE_AUDIT.json reports missing layout controls: "
                f"{paper_style.get('missing_layout_controls')}"
            )
        if paper_style.get("clean") is not True:
            failures.append("PAPER_STYLE_AUDIT.json is not clean")
        if paper_style.get("failures"):
            failures.append(
                "PAPER_STYLE_AUDIT.json contains failures: "
                f"{paper_style.get('failures')}"
            )
        if paper_style.get("em_dash_count") != 0:
            failures.append("PAPER_STYLE_AUDIT.json reports em dash characters")
        if paper_style.get("forbidden_unicode_punctuation_counts"):
            failures.append(
                "PAPER_STYLE_AUDIT.json reports forbidden unicode punctuation: "
                f"{paper_style.get('forbidden_unicode_punctuation_counts')}"
            )
        if paper_style.get("hype_or_vague_phrase_hits"):
            failures.append(
                "PAPER_STYLE_AUDIT.json reports hype or vague wording: "
                f"{paper_style.get('hype_or_vague_phrase_hits')}"
            )
        if paper_style.get("n_figures", 0) < 4:
            failures.append("PAPER_STYLE_AUDIT.json reports fewer than 4 figures")
        if paper_style.get("n_tables", 0) < 10:
            failures.append("PAPER_STYLE_AUDIT.json reports too few active tables")
    else:
        failures.append("Missing PAPER_STYLE_AUDIT.json")
    report["checks"]["paper_style"] = paper_style_checks

    paper_generator_path = root / "scripts" / "06_make_paper_artifacts.py"
    paper_generator_checks = {
        "present": paper_generator_path.exists(),
        "description_count": 0,
        "has_description_command": False,
        "forced_here_float_patterns": [],
        "missing_required_phrases": [],
    }
    if not paper_generator_path.exists():
        failures.append("Missing scripts/06_make_paper_artifacts.py")
    else:
        generator_text = paper_generator_path.read_text(errors="replace")
        paper_generator_checks["description_count"] = generator_text.count(
            "\\Description"
        )
        paper_generator_checks["has_description_command"] = (
            "\\providecommand{{\\Description}}" in generator_text
            or "\\providecommand{\\Description}" in generator_text
        )
        for pattern in [r"\begin{{figure}}[H]", r"\begin{figure}[H]"]:
            if pattern in generator_text:
                paper_generator_checks["forced_here_float_patterns"].append(pattern)
        required_generator_phrases = [
            "method_overview.png",
            "recall_at_5.png",
            "gate_diagnostic.png",
            "threshold_sensitivity.png",
            "Flow diagram showing dense retrieval",
            "Bar chart comparing seed-42 Recall at 5",
            "Threshold sweep chart showing post-hoc Recall at 5",
        ]
        paper_generator_checks["missing_required_phrases"] = [
            phrase for phrase in required_generator_phrases if phrase not in generator_text
        ]
        if paper_generator_checks["description_count"] < 4:
            failures.append(
                "scripts/06_make_paper_artifacts.py does not emit descriptions for all figures"
            )
        if not paper_generator_checks["has_description_command"]:
            failures.append(
                "scripts/06_make_paper_artifacts.py is missing the LaTeX Description command shim"
            )
        if paper_generator_checks["forced_here_float_patterns"]:
            failures.append(
                "scripts/06_make_paper_artifacts.py uses forced [H] figure placement: "
                f"{paper_generator_checks['forced_here_float_patterns']}"
            )
        if paper_generator_checks["missing_required_phrases"]:
            failures.append(
                "scripts/06_make_paper_artifacts.py is missing required generated figure text: "
                f"{paper_generator_checks['missing_required_phrases']}"
            )
    report["checks"]["paper_generator_professional_formatting"] = (
        paper_generator_checks
    )

    figure_asset_audit_path = root / "FIGURE_ASSET_AUDIT.json"
    figure_asset_checks = {
        "present": figure_asset_audit_path.exists(),
        "clean": False,
        "failures": [],
        "warnings": [],
        "n_active_figures": None,
        "figures": [],
    }
    if figure_asset_audit_path.exists():
        figure_asset = read_json(figure_asset_audit_path)
        figure_asset_checks.update(
            {
                "clean": figure_asset.get("clean"),
                "failures": figure_asset.get("failures", []),
                "warnings": figure_asset.get("warnings", []),
                "n_active_figures": figure_asset.get("n_active_figures"),
                "figures": figure_asset.get("figures", []),
            }
        )
        if figure_asset.get("clean") is not True:
            failures.append("FIGURE_ASSET_AUDIT.json is not clean")
        if figure_asset.get("failures"):
            failures.append(
                "FIGURE_ASSET_AUDIT.json contains failures: "
                f"{figure_asset.get('failures')}"
            )
        if figure_asset.get("n_active_figures", 0) < 4:
            failures.append("FIGURE_ASSET_AUDIT.json reports fewer than 4 active figures")
    else:
        failures.append("Missing FIGURE_ASSET_AUDIT.json")
    report["checks"]["figure_assets"] = figure_asset_checks

    evidence_claim_audit_path = root / "PAPER_EVIDENCE_CLAIM_AUDIT.json"
    evidence_claim_checks = {
        "present": evidence_claim_audit_path.exists(),
        "clean": False,
        "failures": [],
        "warnings": [],
        "matches": [],
        "missing_required_limitations": [],
    }
    if evidence_claim_audit_path.exists():
        evidence_claim_audit = read_json(evidence_claim_audit_path)
        evidence_claim_checks.update(
            {
                "clean": evidence_claim_audit.get("clean"),
                "failures": evidence_claim_audit.get("failures", []),
                "warnings": evidence_claim_audit.get("warnings", []),
                "matches": evidence_claim_audit.get("matches", []),
                "missing_required_limitations": evidence_claim_audit.get(
                    "missing_required_limitations", []
                ),
            }
        )
        if evidence_claim_audit.get("clean") is not True:
            failures.append("PAPER_EVIDENCE_CLAIM_AUDIT.json is not clean")
        if evidence_claim_audit.get("matches"):
            failures.append(
                "PAPER_EVIDENCE_CLAIM_AUDIT.json contains unsupported claim matches: "
                f"{evidence_claim_audit.get('matches')}"
            )
        if evidence_claim_audit.get("missing_required_limitations"):
            failures.append(
                "PAPER_EVIDENCE_CLAIM_AUDIT.json is missing limitation phrases: "
                f"{evidence_claim_audit.get('missing_required_limitations')}"
            )
    else:
        failures.append("Missing PAPER_EVIDENCE_CLAIM_AUDIT.json")
    report["checks"]["paper_evidence_claim_audit"] = evidence_claim_checks

    compute_env_path = root / "COMPUTE_ENVIRONMENT.json"
    compute_env_checks = {
        "present": compute_env_path.exists(),
        "is_experiment_metric": None,
        "runtime_measurements_available": None,
        "cpu_threads": None,
        "gpu_count": None,
        "memory_total": None,
    }
    if compute_env_path.exists():
        compute_env = read_json(compute_env_path)
        cpu = compute_env.get("cpu", {})
        gpus = compute_env.get("gpus", [])
        memory = compute_env.get("memory", {})
        compute_env_checks.update(
            {
                "is_experiment_metric": compute_env.get("is_experiment_metric"),
                "runtime_measurements_available": compute_env.get(
                    "runtime_measurements_available"
                ),
                "cpu_threads": cpu.get("cpu_threads"),
                "gpu_count": len(gpus),
                "memory_total": memory.get("total"),
            }
        )
        if compute_env.get("is_experiment_metric") is not False:
            failures.append("COMPUTE_ENVIRONMENT.json must be marked as non-metric metadata")
        if not cpu.get("cpu_threads") or not memory.get("total"):
            failures.append("COMPUTE_ENVIRONMENT.json is missing CPU or memory metadata")
    else:
        failures.append("Missing COMPUTE_ENVIRONMENT.json")
    report["checks"]["compute_environment"] = compute_env_checks

    artifact_manifest_path = root / "ARTIFACT_MANIFEST.json"
    report["checks"]["artifact_manifest"] = str(artifact_manifest_path) if artifact_manifest_path.exists() else ""
    report["checks"]["artifact_manifest_freshness_skipped"] = bool(args.skip_manifest_freshness)
    if args.skip_manifest_freshness:
        report["checks"]["artifact_manifest_stale_entries"] = []
    elif not artifact_manifest_path.exists():
        failures.append("Missing ARTIFACT_MANIFEST.json")
    else:
        artifact_manifest = read_json(artifact_manifest_path)
        if artifact_manifest.get("n_files", 0) < 60:
            failures.append(
                "ARTIFACT_MANIFEST.json contains too few files: "
                f"{artifact_manifest.get('n_files')}"
            )
        manifest_paths = {item.get("path") for item in artifact_manifest.get("files", [])}
        for required in [
            "paper/main.tex",
            "paper/main.pdf",
            "paper/main_conference_preview.tex",
            "paper/main_conference_preview.pdf",
            "LATEX_BUILD_AUDIT.json",
            "CONFERENCE_PREVIEW_AUDIT.json",
            "PAPER_STYLE_AUDIT.json",
            "FIGURE_ASSET_AUDIT.json",
            "PAPER_EVIDENCE_CLAIM_AUDIT.json",
            "COMPUTE_ENVIRONMENT.json",
            "results_multiseed/multiseed_report.json",
            "results_multiseed/multiseed_paired_tests.json",
            "results_multiseed/multiseed_gate_validation.json",
            "results_multiseed/win_loss_analysis.json",
            "results_gate_calibration/gate_variant_diagnostics.json",
            "results_gate_calibration/gate_headroom_diagnostics.json",
            "results_gate_calibration/cross_seed_top1_gate.json",
            "results_500_memory_seed43/verification_report.json",
            "results_500_memory_seed44/verification_report.json",
            "human_audit/README.md",
            "human_audit/REVIEWER_QUICKSTART.md",
            "pass1_evoagentbench_configs/EXECUTION_QUICKSTART.md",
            "scripts/07_verify_experiment.py",
            "scripts/13_make_artifact_manifest.py",
            "scripts/31_verify_latex_clean_build.py",
            "scripts/36_make_conference_preview.py",
            "scripts/37_audit_paper_style.py",
            "scripts/38_capture_compute_environment.py",
            "scripts/39_audit_figure_assets.py",
            "scripts/43_audit_paper_evidence_claims.py",
            "scripts/17_verify_pass1_results.py",
            "scripts/18_verify_human_audit_labels.py",
            "scripts/19_win_loss_analysis.py",
            "scripts/29_cross_seed_top1_gate.py",
            "DATA_PROVENANCE.md",
            "EXPERIMENT_STATUS.md",
            "OBJECTIVE_AUDIT.md",
            "OBJECTIVE_COMPLETION_AUDIT.md",
            "CLAIM_AUDIT.md",
            "NO_HALLUCINATED_DATA.md",
            "LLM_USAGE_DISCLOSURE.md",
            "BLOCKED_NEXT_ACTIONS.md",
            "HANDOFF_STATUS.md",
            "PASS1_HARNESS_AUDIT.md",
            "PAPER_CHECKLIST.md",
        ]:
            if required not in manifest_paths:
                failures.append(f"ARTIFACT_MANIFEST.json missing required path: {required}")
        stale = []
        for item in artifact_manifest.get("files", []):
            rel_path = item.get("path")
            path = root / rel_path if rel_path else None
            if not path or not path.exists():
                stale.append(f"{rel_path}: missing")
                continue
            actual_size = path.stat().st_size
            actual_sha = sha256_file(path)
            if actual_size != item.get("bytes") or actual_sha != item.get("sha256"):
                stale.append(f"{rel_path}: checksum_or_size_mismatch")
        report["checks"]["artifact_manifest_stale_entries"] = stale[:20]
        if stale:
            failures.append(
                "ARTIFACT_MANIFEST.json is stale; regenerate it with "
                f"scripts/13_make_artifact_manifest.py. First mismatches: {stale[:5]}"
            )

    readiness_path = root / "SUBMISSION_READINESS.json"
    report["checks"]["submission_readiness"] = str(readiness_path) if readiness_path.exists() else ""
    if not readiness_path.exists():
        failures.append("Missing SUBMISSION_READINESS.json")
    else:
        readiness = read_json(readiness_path)
        report["checks"]["strong_submission_ready"] = readiness.get("strong_submission_ready")
        report["checks"]["submission_blocking_count"] = readiness.get("blocking_count")
        readiness_checks = readiness.get("checks", [])
        readiness_check_names = [item.get("name") for item in readiness_checks]
        report["checks"]["readiness_check_names"] = readiness_check_names
        if "Clear multi-seed improvement over dense retrieval" in readiness_check_names:
            failures.append(
                "SUBMISSION_READINESS.json uses overstrong dense-comparison wording; "
                "use 'Small multi-seed Recall@5 improvement over dense retrieval'"
            )
        if (
            "Small multi-seed Recall@5 improvement over dense retrieval"
            not in readiness_check_names
        ):
            failures.append(
                "SUBMISSION_READINESS.json is missing the scoped dense-comparison "
                "readiness check name"
            )
        if "Non-destructive release helpers" not in readiness_check_names:
            failures.append(
                "SUBMISSION_READINESS.json is missing the non-destructive release "
                "helper readiness check"
            )
        if "Project script deletion safety" not in readiness_check_names:
            failures.append(
                "SUBMISSION_READINESS.json is missing the project script deletion "
                "safety readiness check"
            )
        if "Paper evidence-claim audit" not in readiness_check_names:
            failures.append(
                "SUBMISSION_READINESS.json is missing the paper evidence-claim "
                "audit readiness check"
            )
        if "External evidence resume helper" not in readiness_check_names:
            failures.append(
                "SUBMISSION_READINESS.json is missing the external-evidence "
                "resume-helper readiness check"
            )
        pass1_check = next(
            (
                item for item in readiness_checks
                if item.get("name") == "Downstream Pass@1 or task-success evaluation"
            ),
            {},
        )
        pass1_evidence = pass1_check.get("evidence", {}) if pass1_check else {}
        pass1_context_check = next(
            (
                item for item in readiness_checks
                if item.get("name") == "Pass@1 retrieval context packets"
            ),
            {},
        )
        pass1_context_evidence = (
            pass1_context_check.get("evidence", {}) if pass1_context_check else {}
        )
        human_label_check = next(
            (
                item for item in readiness_checks
                if item.get("name") == "Human-audited query quality labels"
            ),
            {},
        )
        human_label_evidence = (
            human_label_check.get("evidence", {}) if human_label_check else {}
        )
        blocked_next_actions_check = next(
            (
                item for item in readiness_checks
                if item.get("name") == "Documented unblock steps"
            ),
            {},
        )
        blocked_next_actions_evidence = (
            blocked_next_actions_check.get("evidence", {})
            if blocked_next_actions_check
            else {}
        )
        resume_helper_check = next(
            (
                item for item in readiness_checks
                if item.get("name") == "External evidence resume helper"
            ),
            {},
        )
        resume_helper_evidence = (
            resume_helper_check.get("evidence", {}) if resume_helper_check else {}
        )
        pass1_preflight_check = next(
            (
                item for item in readiness_checks
                if item.get("name") == "Pass@1 harness execution preflight"
            ),
            {},
        )
        pass1_preflight_evidence = (
            pass1_preflight_check.get("evidence", {})
            if pass1_preflight_check
            else {}
        )
        no_hallucinated_check = next(
            (
                item for item in readiness_checks
                if item.get("name") == "No hallucinated or simulated evidence in active paper package"
            ),
            {},
        )
        no_hallucinated_evidence = (
            no_hallucinated_check.get("evidence", {})
            if no_hallucinated_check
            else {}
        )
        paper_claim_check = next(
            (
                item for item in readiness_checks
                if item.get("name") == "Paper evidence-claim audit"
            ),
            {},
        )
        paper_claim_evidence = (
            paper_claim_check.get("evidence", {}) if paper_claim_check else {}
        )
        report["checks"]["readiness_pass1_status"] = pass1_check.get("status")
        report["checks"]["readiness_pass1_has_results"] = pass1_evidence.get("has_pass1_results")
        report["checks"]["readiness_pass1_importer_present"] = pass1_evidence.get(
            "evoagentbench_importer_present"
        )
        report["checks"]["readiness_pass1_importer_is_evidence"] = pass1_evidence.get(
            "importer_is_evidence"
        )
        report["checks"]["readiness_pass1_schema_is_evidence"] = pass1_evidence.get(
            "schema_is_evidence"
        )
        report["checks"]["readiness_pass1_context_status"] = pass1_context_check.get("status")
        report["checks"]["readiness_pass1_context_is_result"] = pass1_context_evidence.get(
            "is_pass1_result"
        )
        report["checks"]["readiness_pass1_context_has_valid_contexts"] = (
            pass1_context_evidence.get("has_valid_contexts")
        )
        report["checks"]["readiness_pass1_context_exporter_present"] = (
            pass1_context_evidence.get("exporter_present")
        )
        report["checks"]["readiness_pass1_context_verifier_present"] = (
            pass1_context_evidence.get("verifier_present")
        )
        report["checks"]["readiness_human_label_status"] = human_label_check.get("status")
        report["checks"]["readiness_human_label_valid"] = human_label_evidence.get("valid")
        report["checks"]["readiness_human_label_labeled_rows"] = human_label_evidence.get(
            "labeled_rows"
        )
        report["checks"]["readiness_human_label_complete_rows"] = human_label_evidence.get(
            "complete_label_rows"
        )
        report["checks"]["readiness_human_source_packet_is_evidence"] = (
            human_label_evidence.get("source_packet_is_evidence")
        )
        report["checks"]["readiness_human_template_is_evidence"] = (
            human_label_evidence.get("labeling_template_is_evidence")
        )
        report["checks"]["readiness_human_labeling_protocol_present"] = (
            human_label_evidence.get("labeling_protocol_present")
        )
        report["checks"]["readiness_human_labeling_protocol_is_evidence"] = (
            human_label_evidence.get("labeling_protocol_is_evidence")
        )
        report["checks"]["readiness_human_reviewer_quickstart_present"] = (
            human_label_evidence.get("reviewer_quickstart_present")
        )
        report["checks"]["readiness_human_reviewer_quickstart_is_evidence"] = (
            human_label_evidence.get("reviewer_quickstart_is_evidence")
        )
        report["checks"]["readiness_human_reviewer_packet_manifest_present"] = (
            human_label_evidence.get("reviewer_packet_manifest_present")
        )
        report["checks"]["readiness_human_reviewer_packet_manifest_is_evidence"] = (
            human_label_evidence.get("reviewer_packet_manifest_is_evidence")
        )
        report["checks"]["readiness_human_reviewer_packet_verification_present"] = (
            human_label_evidence.get("reviewer_packet_verification_present")
        )
        report["checks"]["readiness_human_reviewer_packet_verification_failures"] = (
            human_label_evidence.get("reviewer_packet_verification_failures")
        )
        report["checks"]["readiness_human_reviewer_packet_verification_is_evidence"] = (
            human_label_evidence.get("reviewer_packet_verification_is_evidence")
        )
        report["checks"]["readiness_human_labeling_manifest_reviewer_count"] = (
            human_label_evidence.get("labeling_manifest_reviewer_count")
        )
        report["checks"]["readiness_human_labeling_manifest_has_two_reviewers"] = (
            human_label_evidence.get("labeling_manifest_has_two_reviewers")
        )
        report["checks"]["readiness_human_labeling_manifest_has_adjudication_notes"] = (
            human_label_evidence.get("labeling_manifest_has_adjudication_notes")
        )
        report["checks"]["readiness_human_labeling_manifest_guard_valid"] = (
            human_label_evidence.get("labeling_manifest_guard_valid")
        )
        report["checks"]["readiness_human_summary_provenance_valid"] = (
            human_label_evidence.get("summary_provenance_valid")
        )
        report["checks"]["readiness_blocked_next_actions_status"] = (
            blocked_next_actions_check.get("status")
        )
        report["checks"]["readiness_blocked_next_actions_valid"] = (
            blocked_next_actions_evidence.get("valid")
        )
        report["checks"]["readiness_blocked_next_actions_is_evidence"] = (
            blocked_next_actions_evidence.get("is_evidence")
        )
        report["checks"]["readiness_blocked_next_actions_missing_phrases"] = (
            blocked_next_actions_evidence.get("missing_required_phrases")
        )
        report["checks"]["readiness_external_resume_helper_status"] = (
            resume_helper_check.get("status")
        )
        report["checks"]["readiness_external_resume_helper_valid"] = (
            resume_helper_evidence.get("valid")
        )
        report["checks"]["readiness_external_resume_helper_is_evidence"] = (
            resume_helper_evidence.get("is_experiment_evidence")
        )
        report["checks"]["readiness_external_resume_helper_missing_required_snippets"] = (
            resume_helper_evidence.get("missing_required_snippets")
        )
        report["checks"]["readiness_external_resume_helper_forbidden_snippets_present"] = (
            resume_helper_evidence.get("forbidden_snippets_present")
        )
        report["checks"]["readiness_pass1_preflight_status"] = (
            pass1_preflight_check.get("status")
        )
        report["checks"]["readiness_pass1_preflight_checked_at_utc"] = (
            pass1_preflight_evidence.get("checked_at_utc")
        )
        report["checks"]["readiness_pass1_preflight_is_result"] = (
            pass1_preflight_evidence.get("is_pass1_result")
        )
        report["checks"]["readiness_pass1_execution_quickstart_present"] = (
            pass1_preflight_evidence.get("execution_quickstart_present")
        )
        report["checks"]["readiness_pass1_execution_quickstart_is_evidence"] = (
            pass1_preflight_evidence.get("execution_quickstart_is_evidence")
        )
        report["checks"]["readiness_pass1_guarded_runner_present"] = (
            pass1_preflight_evidence.get("guarded_runner_present")
        )
        report["checks"]["readiness_pass1_guarded_runner_is_evidence"] = (
            pass1_preflight_evidence.get("guarded_runner_is_evidence")
        )
        report["checks"]["readiness_pass1_guarded_runner_requires_ready_preflight"] = (
            pass1_preflight_evidence.get("guarded_runner_requires_ready_preflight")
        )
        report["checks"]["readiness_pass1_guarded_runner_default_no_overwrite"] = (
            pass1_preflight_evidence.get("guarded_runner_default_no_overwrite")
        )
        report["checks"]["readiness_pass1_guarded_runner_smoke_output_separate"] = (
            pass1_preflight_evidence.get("guarded_runner_smoke_output_separate")
        )
        report["checks"]["readiness_pass1_guarded_runner_full_min_task_count"] = (
            pass1_preflight_evidence.get("guarded_runner_full_min_task_count")
        )
        report["checks"]["readiness_pass1_guarded_runner_smoke_min_task_count_explicit"] = (
            pass1_preflight_evidence.get("guarded_runner_smoke_min_task_count_explicit")
        )
        report["checks"]["readiness_pass1_preflight_ready"] = (
            pass1_preflight_evidence.get("ready_to_run_pass1")
        )
        report["checks"]["readiness_pass1_preflight_blockers"] = (
            pass1_preflight_evidence.get("blockers")
        )
        report["checks"]["readiness_pass1_docker_socket_group"] = (
            pass1_preflight_evidence.get("docker_socket_group")
        )
        report["checks"]["readiness_pass1_docker_user_group_names"] = (
            pass1_preflight_evidence.get("docker_user_group_names")
        )
        report["checks"]["readiness_pass1_docker_user_in_socket_group"] = (
            pass1_preflight_evidence.get("docker_user_in_socket_group")
        )
        report["checks"]["readiness_pass1_docker_user_listed_in_socket_group"] = (
            pass1_preflight_evidence.get("docker_user_listed_in_socket_group")
        )
        report["checks"]["readiness_no_hallucinated_status"] = (
            no_hallucinated_check.get("status")
        )
        report["checks"]["readiness_no_hallucinated_valid"] = (
            no_hallucinated_evidence.get("valid")
        )
        report["checks"]["readiness_paper_evidence_claim_status"] = (
            paper_claim_check.get("status")
        )
        report["checks"]["readiness_paper_evidence_claim_clean"] = (
            paper_claim_evidence.get("clean")
        )
        report["checks"]["readiness_paper_evidence_claim_matches"] = (
            paper_claim_evidence.get("matches")
        )
        report["checks"]["readiness_paper_evidence_claim_missing_limitations"] = (
            paper_claim_evidence.get("missing_required_limitations")
        )
        readiness_report_summaries = no_hallucinated_evidence.get(
            "verification_reports_checked", []
        )
        readiness_missing_guard_fields = []
        readiness_nonempty_guard_fields = []
        required_readiness_guard_fields = [
            "stale_seed_provenance_doc_references",
            "stale_gate_variant_ci_doc_references",
        ]
        for item in readiness_report_summaries:
            summary_path = item.get("path", "<unknown>")
            for key in required_readiness_guard_fields:
                if key not in item:
                    readiness_missing_guard_fields.append(f"{summary_path}: {key}")
                elif item.get(key):
                    readiness_nonempty_guard_fields.append(
                        f"{summary_path}: {key}={item.get(key)}"
                    )
        report["checks"]["readiness_missing_guard_fields"] = (
            readiness_missing_guard_fields
        )
        report["checks"]["readiness_nonempty_guard_fields"] = (
            readiness_nonempty_guard_fields
        )
        latex_check = next(
            (
                item for item in readiness_checks
                if item.get("name") == "Verified LaTeX paper package"
            ),
            {},
        )
        latex_evidence = latex_check.get("evidence", {}) if latex_check else {}
        style_check = next(
            (
                item for item in readiness_checks
                if item.get("name") == "Paper style and float-reference audit"
            ),
            {},
        )
        style_evidence = style_check.get("evidence", {}) if style_check else {}
        figure_check = next(
            (
                item for item in readiness_checks
                if item.get("name") == "Figure asset readability audit"
            ),
            {},
        )
        figure_evidence = figure_check.get("evidence", {}) if figure_check else {}
        compute_check = next(
            (
                item for item in readiness_checks
                if item.get("name") == "Compute environment disclosure"
            ),
            {},
        )
        compute_evidence = compute_check.get("evidence", {}) if compute_check else {}
        llm_usage_check = next(
            (
                item for item in readiness_checks
                if item.get("name") == "LLM usage disclosure draft"
            ),
            {},
        )
        llm_usage_evidence = (
            llm_usage_check.get("evidence", {}) if llm_usage_check else {}
        )
        release_helper_check = next(
            (
                item for item in readiness_checks
                if item.get("name") == "Non-destructive release helpers"
            ),
            {},
        )
        release_helper_evidence = (
            release_helper_check.get("evidence", {}) if release_helper_check else {}
        )
        project_deletion_check = next(
            (
                item for item in readiness_checks
                if item.get("name") == "Project script deletion safety"
            ),
            {},
        )
        project_deletion_evidence = (
            project_deletion_check.get("evidence", {}) if project_deletion_check else {}
        )
        report["checks"]["readiness_latex_status"] = latex_check.get("status")
        report["checks"]["readiness_latex_clean_build"] = latex_evidence.get("clean_build")
        report["checks"]["readiness_latex_warnings"] = latex_evidence.get("warnings")
        report["checks"]["readiness_latex_failures"] = latex_evidence.get("failures")
        report["checks"]["readiness_latex_pdf_pages"] = latex_evidence.get("pdf_pages")
        report["checks"]["readiness_paper_style_status"] = style_check.get("status")
        report["checks"]["readiness_paper_style_clean"] = style_evidence.get("clean")
        report["checks"]["readiness_paper_style_failures"] = style_evidence.get("failures")
        report["checks"]["readiness_paper_style_forbidden_unicode_punctuation_counts"] = (
            style_evidence.get("forbidden_unicode_punctuation_counts")
        )
        report["checks"]["readiness_paper_style_hype_or_vague_phrase_hits"] = (
            style_evidence.get("hype_or_vague_phrase_hits")
        )
        report["checks"]["readiness_paper_style_missing_required_guarded_phrases"] = (
            style_evidence.get("missing_required_guarded_phrases", [])
        )
        report["checks"]["readiness_paper_style_missing_required_layout_controls"] = (
            style_evidence.get("missing_required_layout_controls", [])
        )
        report["checks"]["readiness_paper_style_missing_layout_controls"] = (
            style_evidence.get("missing_layout_controls", [])
        )
        report["checks"]["readiness_figure_asset_status"] = figure_check.get("status")
        report["checks"]["readiness_figure_asset_clean"] = figure_evidence.get("clean")
        report["checks"]["readiness_figure_asset_failures"] = figure_evidence.get("failures")
        report["checks"]["readiness_figure_asset_n_active_figures"] = (
            figure_evidence.get("n_active_figures")
        )
        report["checks"]["readiness_compute_status"] = compute_check.get("status")
        report["checks"]["readiness_compute_valid"] = compute_evidence.get("valid")
        report["checks"]["readiness_compute_is_metric"] = compute_evidence.get(
            "is_experiment_metric"
        )
        report["checks"]["readiness_llm_usage_status"] = llm_usage_check.get("status")
        report["checks"]["readiness_llm_usage_valid"] = llm_usage_evidence.get("valid")
        report["checks"]["readiness_llm_usage_missing_phrases"] = (
            llm_usage_evidence.get("missing_required_phrases")
        )
        report["checks"]["readiness_release_helpers_status"] = (
            release_helper_check.get("status")
        )
        report["checks"]["readiness_release_helpers_destructive_patterns"] = (
            release_helper_evidence.get("destructive_patterns")
        )
        report["checks"]["readiness_release_helpers_missing_noop_clean_guard"] = (
            release_helper_evidence.get("missing_noop_clean_guard")
        )
        report["checks"]["readiness_project_deletion_safety_status"] = (
            project_deletion_check.get("status")
        )
        report["checks"]["readiness_project_deletion_safety_destructive_patterns"] = (
            project_deletion_evidence.get("destructive_patterns")
        )
        if readiness.get("strong_submission_ready") is True:
            failures.append(
                "SUBMISSION_READINESS.json unexpectedly marks the package as "
                "strong-submission ready; verify dense-retrieval comparison, "
                "Pass@1, and human labels before setting this true."
            )
        if readiness.get("blocking_count", 0) < 1:
            failures.append("SUBMISSION_READINESS.json does not report any blocking gaps")
        if not pass1_check:
            failures.append("SUBMISSION_READINESS.json is missing the Pass@1 readiness check")
        else:
            if pass1_evidence.get("schema_is_evidence") is not False:
                failures.append("SUBMISSION_READINESS.json must mark Pass@1 schema as non-evidence")
            if pass1_evidence.get("importer_is_evidence") is not False:
                failures.append("SUBMISSION_READINESS.json must mark Pass@1 importer as non-evidence")
            if pass1_evidence.get("evoagentbench_importer_present") is not True:
                failures.append("SUBMISSION_READINESS.json does not record the Pass@1 importer")
            if pass1_check.get("status") == "missing" and pass1_evidence.get("has_pass1_results"):
                failures.append("SUBMISSION_READINESS.json marks Pass@1 missing but has results")
            if pass1_check.get("status") != "missing" and not pass1_evidence.get("has_pass1_results"):
                failures.append("SUBMISSION_READINESS.json Pass@1 status is inconsistent with evidence")
        if not pass1_context_check:
            failures.append("SUBMISSION_READINESS.json is missing the Pass@1 context-packet check")
        else:
            if pass1_context_check.get("required_for_strong_submission") is not False:
                failures.append("Pass@1 context packets must not be required evidence")
            if pass1_context_evidence.get("is_pass1_result") is not False:
                failures.append("Pass@1 context packets must be marked as non-result data")
            if pass1_context_evidence.get("exporter_present") is not True:
                failures.append("SUBMISSION_READINESS.json does not record the context exporter")
            if pass1_context_evidence.get("verifier_present") is not True:
                failures.append("SUBMISSION_READINESS.json does not record the context verifier")
            if (
                pass1_context_check.get("status") == "missing"
                and pass1_context_evidence.get("has_valid_contexts")
            ):
                failures.append("SUBMISSION_READINESS.json marks contexts missing but valid")
            if (
                pass1_context_check.get("status") != "missing"
                and not pass1_context_evidence.get("has_valid_contexts")
            ):
                failures.append("SUBMISSION_READINESS.json context status is inconsistent with evidence")
        if not human_label_check:
            failures.append("SUBMISSION_READINESS.json is missing the human-label readiness check")
        else:
            if human_label_evidence.get("source_packet_is_evidence") is not False:
                failures.append("SUBMISSION_READINESS.json must mark human-audit source packet as non-evidence")
            if human_label_evidence.get("labeling_template_is_evidence") is not False:
                failures.append("SUBMISSION_READINESS.json must mark human-label template as non-evidence")
            if human_label_evidence.get("labeling_protocol_present") is not True:
                failures.append("SUBMISSION_READINESS.json must record the human-label protocol")
            if human_label_evidence.get("labeling_protocol_is_evidence") is not False:
                failures.append("SUBMISSION_READINESS.json must mark human-label protocol as non-evidence")
            if human_label_evidence.get("reviewer_quickstart_present") is not True:
                failures.append("SUBMISSION_READINESS.json must record the human-audit reviewer quickstart")
            if human_label_evidence.get("reviewer_quickstart_is_evidence") is not False:
                failures.append("SUBMISSION_READINESS.json must mark the human-audit reviewer quickstart as non-evidence")
            if human_label_evidence.get("reviewer_packet_manifest_present") is not True:
                failures.append("SUBMISSION_READINESS.json must record the human-audit reviewer packet manifest")
            if human_label_evidence.get("reviewer_packet_manifest_is_evidence") is not False:
                failures.append("SUBMISSION_READINESS.json must mark human-audit reviewer packets as non-evidence")
            if human_label_evidence.get("reviewer_packet_verification_present") is not True:
                failures.append("SUBMISSION_READINESS.json must record reviewer packet verification")
            if human_label_evidence.get("reviewer_packet_verification_failures"):
                failures.append("human-audit reviewer packet verification must have no failures")
            if human_label_evidence.get("reviewer_packet_verification_is_evidence") is not False:
                failures.append("SUBMISSION_READINESS.json must mark reviewer packet verification as non-evidence")
            if human_label_check.get("status") != "missing":
                if human_label_evidence.get("labeling_manifest_has_two_reviewers") is not True:
                    failures.append("Accepted human-audit evidence must list at least two reviewers")
                if human_label_evidence.get("labeling_manifest_has_adjudication_notes") is not True:
                    failures.append("Accepted human-audit evidence must document adjudication notes")
                if human_label_evidence.get("labeling_manifest_guard_valid") is not True:
                    failures.append("Accepted human-audit manifest does not satisfy reviewer/adjudication guards")
                if human_label_evidence.get("summary_provenance_valid") is not True:
                    failures.append("Accepted human-audit summary must carry provenance fields")
            if human_label_check.get("status") == "missing" and human_label_evidence.get("valid"):
                failures.append("SUBMISSION_READINESS.json marks human labels missing but valid")
            if human_label_check.get("status") != "missing" and not human_label_evidence.get("valid"):
                failures.append("SUBMISSION_READINESS.json human-label status is inconsistent with evidence")
        if not blocked_next_actions_check:
            failures.append(
                "SUBMISSION_READINESS.json is missing the documented-unblock-steps check"
            )
        else:
            if blocked_next_actions_check.get("required_for_strong_submission") is not False:
                failures.append("Documented unblock steps must not be required evidence")
            if blocked_next_actions_evidence.get("is_evidence") is not False:
                failures.append("Documented unblock steps must be marked as non-evidence")
            if blocked_next_actions_evidence.get("valid") is not True:
                failures.append(
                    "SUBMISSION_READINESS.json does not record valid unblock-step documentation"
                )
            if blocked_next_actions_evidence.get("missing_required_phrases"):
                failures.append(
                    "SUBMISSION_READINESS.json records missing unblock-step phrases: "
                    f"{blocked_next_actions_evidence.get('missing_required_phrases')}"
                )
        if not resume_helper_check:
            failures.append(
                "SUBMISSION_READINESS.json is missing the external-evidence "
                "resume-helper check"
            )
        else:
            if resume_helper_check.get("required_for_strong_submission") is not False:
                failures.append("External evidence resume helper must not be required evidence")
            if resume_helper_evidence.get("is_experiment_evidence") is not False:
                failures.append("External evidence resume helper must be marked as non-evidence")
            if resume_helper_evidence.get("valid") is not True:
                failures.append(
                    "SUBMISSION_READINESS.json does not record a valid external-evidence "
                    "resume helper"
                )
            if resume_helper_evidence.get("missing_required_snippets"):
                failures.append(
                    "External evidence resume helper missing required snippets: "
                    f"{resume_helper_evidence.get('missing_required_snippets')}"
                )
            if resume_helper_evidence.get("forbidden_snippets_present"):
                failures.append(
                    "External evidence resume helper contains forbidden snippets: "
                    f"{resume_helper_evidence.get('forbidden_snippets_present')}"
                )
        if not pass1_preflight_check:
            failures.append("SUBMISSION_READINESS.json is missing the Pass@1 preflight check")
        else:
            if pass1_preflight_check.get("required_for_strong_submission") is not False:
                failures.append("Pass@1 preflight must not be required evidence")
            if pass1_preflight_evidence.get("is_pass1_result") is not False:
                failures.append("Pass@1 preflight must be marked as non-result data")
            if pass1_preflight_evidence.get("execution_quickstart_present") is not True:
                failures.append("SUBMISSION_READINESS.json must record the Pass@1 execution quickstart")
            if pass1_preflight_evidence.get("execution_quickstart_is_evidence") is not False:
                failures.append("SUBMISSION_READINESS.json must mark the Pass@1 execution quickstart as non-evidence")
            if pass1_preflight_evidence.get("guarded_runner_present") is not True:
                failures.append("SUBMISSION_READINESS.json must record the guarded Pass@1 runner")
            if pass1_preflight_evidence.get("guarded_runner_is_evidence") is not False:
                failures.append("Guarded Pass@1 runner must be marked as non-evidence")
            if pass1_preflight_evidence.get("guarded_runner_requires_ready_preflight") is not True:
                failures.append("Guarded Pass@1 runner must require a green preflight before running jobs")
            if pass1_preflight_evidence.get("guarded_runner_default_no_overwrite") is not True:
                failures.append("Guarded Pass@1 runner must refuse overwrite by default")
            if pass1_preflight_evidence.get("guarded_runner_smoke_output_separate") is not True:
                failures.append("Guarded Pass@1 runner must keep smoke output outside results_pass1/")
            if pass1_preflight_evidence.get("guarded_runner_full_min_task_count") is not True:
                failures.append("Guarded Pass@1 runner must keep the full-run 500-task evidence guard")
            if pass1_preflight_evidence.get("guarded_runner_smoke_min_task_count_explicit") is not True:
                failures.append("Guarded Pass@1 runner must lower the smoke threshold explicitly")
            if not pass1_preflight_evidence.get("alternate_container_runtime_note"):
                failures.append("SUBMISSION_READINESS.json must record alternate container runtime diagnostics")
            alternate_runtimes = pass1_preflight_evidence.get("alternate_container_runtimes")
            if not isinstance(alternate_runtimes, dict):
                failures.append("SUBMISSION_READINESS.json alternate container runtime diagnostics must be a dict")
            else:
                for runtime_name in ["nerdctl", "podman", "apptainer", "singularity"]:
                    row = alternate_runtimes.get(runtime_name)
                    if not isinstance(row, dict):
                        failures.append(
                            f"SUBMISSION_READINESS.json is missing alternate runtime row: {runtime_name}"
                        )
                        continue
                    if row.get("is_drop_in_for_evoagentbench_swebench") is not False:
                        failures.append(
                            f"{runtime_name} must not be marked as a drop-in EvoAgentBench SWE-bench runtime"
                        )
            if not pass1_preflight_evidence.get("checked_at_utc"):
                failures.append("SUBMISSION_READINESS.json Pass@1 preflight is missing checked_at_utc")
            if (
                pass1_preflight_evidence.get("ready_to_run_pass1") is False
                and not pass1_preflight_evidence.get("blockers")
            ):
                failures.append("SUBMISSION_READINESS.json Pass@1 preflight is blocked without blockers")
            if (
                pass1_preflight_check.get("status") == "blocked"
                and pass1_preflight_evidence.get("ready_to_run_pass1") is not False
            ):
                failures.append("SUBMISSION_READINESS.json Pass@1 preflight status is inconsistent")
            if pass1_preflight_evidence.get("docker_socket_group") != "docker":
                failures.append("SUBMISSION_READINESS.json must record the Docker socket group")
            if not isinstance(pass1_preflight_evidence.get("docker_user_group_names"), list):
                failures.append("SUBMISSION_READINESS.json must record current user group names")
            if pass1_preflight_evidence.get("ready_to_run_pass1") is False:
                if pass1_preflight_evidence.get("docker_user_in_socket_group") is not False:
                    failures.append("Blocked Pass@1 preflight must record that the current user is not in the Docker socket group")
                if pass1_preflight_evidence.get("docker_user_listed_in_socket_group") is not False:
                    failures.append("Blocked Pass@1 preflight must record that the current user is not listed in the Docker socket group")
        if not no_hallucinated_check:
            failures.append(
                "SUBMISSION_READINESS.json is missing the no-hallucinated-evidence check"
            )
        else:
            if no_hallucinated_check.get("status") != "pass":
                failures.append(
                    "SUBMISSION_READINESS.json does not mark the no-hallucinated-evidence check as pass"
                )
            if no_hallucinated_evidence.get("valid") is not True:
                failures.append(
                    "SUBMISSION_READINESS.json does not record valid anti-hallucination evidence"
                )
            if readiness_missing_guard_fields:
                failures.append(
                    "SUBMISSION_READINESS.json anti-hallucination report summaries "
                    "are missing stale-provenance guard fields: "
                    f"{readiness_missing_guard_fields}"
                )
            if readiness_nonempty_guard_fields:
                failures.append(
                    "SUBMISSION_READINESS.json anti-hallucination report summaries "
                    "contain nonempty stale-provenance guard fields: "
                    f"{readiness_nonempty_guard_fields}"
                )
        if not paper_claim_check:
            failures.append("SUBMISSION_READINESS.json is missing the paper evidence-claim audit")
        else:
            if paper_claim_check.get("required_for_strong_submission") is not False:
                failures.append("Paper evidence-claim audit must not be required evidence")
            if paper_claim_evidence.get("is_experiment_evidence") is not False:
                failures.append("Paper evidence-claim audit must be marked as non-evidence")
            if paper_claim_evidence.get("script_present") is not True:
                failures.append("SUBMISSION_READINESS.json must record the evidence-claim audit script")
            if paper_claim_evidence.get("audit_present") is not True:
                failures.append("SUBMISSION_READINESS.json must record the evidence-claim audit file")
            if paper_claim_check.get("status") != "pass":
                failures.append("Paper evidence-claim audit readiness status must pass")
            if paper_claim_evidence.get("clean") is not True:
                failures.append("Paper evidence-claim audit readiness evidence must be clean")
            if paper_claim_evidence.get("matches"):
                failures.append(
                    "Paper evidence-claim audit readiness evidence has matches: "
                    f"{paper_claim_evidence.get('matches')}"
                )
            if paper_claim_evidence.get("missing_required_limitations"):
                failures.append(
                    "Paper evidence-claim audit readiness evidence is missing limitations: "
                    f"{paper_claim_evidence.get('missing_required_limitations')}"
                )
        if not latex_check:
            failures.append("SUBMISSION_READINESS.json is missing the LaTeX package readiness check")
        else:
            if latex_check.get("status") != "pass":
                failures.append("SUBMISSION_READINESS.json does not mark the LaTeX package verified")
            if latex_evidence.get("clean_build") is not True:
                failures.append("SUBMISSION_READINESS.json does not record a clean LaTeX build")
            if latex_evidence.get("warnings"):
                failures.append(
                    "SUBMISSION_READINESS.json records LaTeX build warnings: "
                    f"{latex_evidence.get('warnings')}"
                )
            if latex_evidence.get("failures"):
                failures.append(
                    "SUBMISSION_READINESS.json records LaTeX build failures: "
                    f"{latex_evidence.get('failures')}"
                )
        if not style_check:
            failures.append("SUBMISSION_READINESS.json is missing the paper style readiness check")
        else:
            if style_check.get("status") != "pass":
                failures.append("SUBMISSION_READINESS.json does not mark the paper style audit as pass")
            if style_evidence.get("clean") is not True:
                failures.append("SUBMISSION_READINESS.json does not record a clean paper style audit")
            if style_evidence.get("failures"):
                failures.append(
                    "SUBMISSION_READINESS.json records paper style failures: "
                    f"{style_evidence.get('failures')}"
                )
        if not compute_check:
            failures.append("SUBMISSION_READINESS.json is missing the compute readiness check")
        else:
            if compute_check.get("status") != "pass":
                failures.append("SUBMISSION_READINESS.json does not mark compute disclosure as pass")
            if compute_evidence.get("valid") is not True:
                failures.append("SUBMISSION_READINESS.json does not record valid compute metadata")
            if compute_evidence.get("is_experiment_metric") is not False:
                failures.append("SUBMISSION_READINESS.json marks compute metadata as experiment metric")
        if not llm_usage_check:
            failures.append("SUBMISSION_READINESS.json is missing the LLM usage disclosure check")
        else:
            if llm_usage_check.get("status") != "pass":
                failures.append("SUBMISSION_READINESS.json does not mark LLM usage disclosure as pass")
            if llm_usage_evidence.get("valid") is not True:
                failures.append("SUBMISSION_READINESS.json does not record valid LLM usage disclosure")
            if llm_usage_evidence.get("is_experiment_evidence") is not False:
                failures.append("SUBMISSION_READINESS.json marks LLM disclosure as experiment evidence")
        if not release_helper_check:
            failures.append("SUBMISSION_READINESS.json is missing the release helper safety check")
        else:
            if release_helper_check.get("status") != "pass":
                failures.append("SUBMISSION_READINESS.json does not mark release helper safety as pass")
            if release_helper_evidence.get("valid") is not True:
                failures.append("SUBMISSION_READINESS.json does not record valid release helper safety")
            if release_helper_evidence.get("destructive_patterns"):
                failures.append(
                    "SUBMISSION_READINESS.json reports destructive release helper patterns: "
                    f"{release_helper_evidence.get('destructive_patterns')}"
                )
            if release_helper_evidence.get("missing_noop_clean_guard"):
                failures.append(
                    "SUBMISSION_READINESS.json reports missing no-op --clean guards: "
                    f"{release_helper_evidence.get('missing_noop_clean_guard')}"
                )
            if project_deletion_check.get("status") != "pass":
                failures.append("SUBMISSION_READINESS.json does not mark project deletion safety as pass")
            if project_deletion_evidence.get("valid") is not True:
                failures.append("SUBMISSION_READINESS.json does not record valid project deletion safety")
            if project_deletion_evidence.get("destructive_patterns"):
                failures.append(
                    "SUBMISSION_READINESS.json reports destructive project script patterns: "
                    f"{project_deletion_evidence.get('destructive_patterns')}"
                )

    legacy_gated_artifact = "_".join(["random", "budget", "simulation"])
    legacy_gated_table = legacy_gated_artifact + ".tex"
    legacy_budget_phrase = " ".join(["random", "budget", "simulation"])
    legacy_budget_hyphen_phrase = "-".join(["random", "budget"]) + " simulation"
    legacy_budget_hyphen_title = "-".join(["Random", "budget"]) + " simulation"
    legacy_budget_title = " ".join(["Random", "budget", "simulation"])
    forbidden_patterns = [
        legacy_gated_artifact,
        "Random-Budget-Expansion",
        legacy_budget_title,
        legacy_budget_hyphen_phrase,
        legacy_budget_hyphen_title,
        "random-gated " + "simulation",
        "Random-gated mean",
        "not a simulation",
        "one fixed memory index",
        "one fixed-memory index",
        "fixed-memory retrieval aggregate",
        "fabricated",
        "fake",
        "hallucinated",
        "simulated metrics",
        "simulated result",
        "simulated values",
        "placeholder metrics",
        "hypothetical evidence",
    ]
    invalid_data_patterns = [
        "data_500_seed42",
        "results_500_seed42",
        "results/full_report",
        "results/baselines_summary",
        "results/proposed_summary",
        "results/proposed_detailed",
        legacy_gated_table,
        "measured_token_pilot.tex",
    ]
    unsupported_claim_patterns = [
        "SQE improves downstream software-agent Pass@1",
        "SQE improves downstream task success",
        "SQE is statistically better than Dense-Only",
        "SQE is practically better than Dense-Only",
        "SQE is statistically better than Random-Gated-Expansion",
        "SQE is practically better than Random-Gated-Expansion",
        "Human reviewers validated the generated retrieval queries",
        "human-validated query quality",
        "state-of-the-art",
        "significantly improves",
        "significant improvement",
        "clearly improves",
        "clear improvement",
        "substantially improves",
        "dramatically improves",
        "robust improvement",
        "end-to-end improvement",
    ]
    forbidden_table_filenames = [
        legacy_gated_table,
        "measured_token_pilot.tex",
    ]
    text_targets = [
        paper_dir / "main.tex",
        results_dir / "full_report_v2.json",
    ]
    text_targets.extend(sorted((paper_dir / "tables").glob("*.tex")))
    text_targets.extend(sorted((root / "results_multiseed").glob("*.json")))
    forbidden_hits = []
    main_text = (paper_dir / "main.tex").read_text(errors="replace") if (paper_dir / "main.tex").exists() else ""
    for path in text_targets:
        if not path.exists():
            continue
        text = path.read_text(errors="replace")
        for pattern in forbidden_patterns:
            if pattern in text:
                forbidden_hits.append(f"{path}: {pattern}")
    report["checks"]["forbidden_synthetic_evidence_references"] = forbidden_hits
    if forbidden_hits:
        failures.append(f"Forbidden synthetic-evidence references found: {forbidden_hits}")
    forbidden_table_files = [
        str(paper_dir / "tables" / name)
        for name in forbidden_table_filenames
        if (paper_dir / "tables" / name).exists()
    ]
    report["checks"]["forbidden_table_files"] = forbidden_table_files
    if forbidden_table_files:
        failures.append(
            "Deprecated non-evidence table files remain under active paper/tables: "
            f"{forbidden_table_files}"
        )
    invalid_data_hits = []
    for path in text_targets:
        if not path.exists():
            continue
        text = path.read_text(errors="replace")
        for pattern in invalid_data_patterns:
            if pattern in text:
                invalid_data_hits.append(f"{path}: {pattern}")
    report["checks"]["invalid_or_deprecated_artifact_references"] = invalid_data_hits
    if invalid_data_hits:
        failures.append(
            "Invalid dataset or deprecated artifact references found in active "
            f"paper/report files: {invalid_data_hits}"
        )
    unsupported_claim_hits = []
    for path in text_targets:
        if not path.exists():
            continue
        text = path.read_text(errors="replace")
        for pattern in unsupported_claim_patterns:
            if pattern in text:
                unsupported_claim_hits.append(f"{path}: {pattern}")
    report["checks"]["unsupported_claim_references"] = unsupported_claim_hits
    if unsupported_claim_hits:
        failures.append(
            "Unsupported positive claims found in active paper/report files: "
            f"{unsupported_claim_hits}"
        )

    doc_guard_paths = [
        root / "README.md",
        root / "PAPER_CHECKLIST.md",
        root / "DATA_PROVENANCE.md",
        root / "CLAIM_AUDIT.md",
        root / "NO_HALLUCINATED_DATA.md",
        root / "BLOCKED_NEXT_ACTIONS.md",
        root / "HANDOFF_STATUS.md",
        root / "EXPERIMENT_STATUS.md",
        root / "NEXT_EXPERIMENTS.md",
        root / "OBJECTIVE_AUDIT.md",
        root / "OBJECTIVE_COMPLETION_AUDIT.md",
        root / "PASS1_HARNESS_AUDIT.md",
        root / "PASS1_RESULTS_SCHEMA.md",
        root / "SUBMISSION_READINESS.json",
    ]
    legacy_gated_artifact = "_".join(["random", "budget", "simulation"])
    legacy_budget_phrase = " ".join(["random", "budget", "simulation"])
    legacy_budget_hyphen_phrase = "-".join(["random", "budget"]) + " simulation"
    legacy_budget_hyphen_title = "-".join(["Random", "budget"]) + " simulation"
    legacy_budget_title = " ".join(["Random", "budget", "simulation"])
    legacy_budget_patterns = [
        "Random-Budget-Expansion",
        legacy_budget_phrase,
        legacy_budget_title,
        legacy_budget_hyphen_phrase,
        legacy_budget_hyphen_title,
        "random-gated " + "simulation",
        legacy_gated_artifact,
        "not a simulation",
    ]
    legacy_budget_hits = []
    for path in doc_guard_paths:
        if not path.exists():
            continue
        text = path.read_text(errors="replace")
        for pattern in legacy_budget_patterns:
            if pattern in text:
                legacy_budget_hits.append(f"{path}: {pattern}")
    report["checks"]["legacy_random_budget_doc_references"] = legacy_budget_hits
    if legacy_budget_hits:
        failures.append(
            "Legacy random-budget/simulation wording found in paper-facing docs: "
            f"{legacy_budget_hits}"
        )

    stale_pass1_harness_patterns = [
        "no method-specific retrieved-memory/context slot",
        "needs method-specific retrieval-context injection",
        "no runnable SQE SWE-bench-style task-success harness is currently present",
    ]
    stale_pass1_harness_hits = []
    for path in doc_guard_paths:
        if not path.exists():
            continue
        text = path.read_text(errors="replace")
        for pattern in stale_pass1_harness_patterns:
            if pattern in text:
                stale_pass1_harness_hits.append(f"{path}: {pattern}")
    report["checks"]["stale_pass1_harness_doc_references"] = stale_pass1_harness_hits
    if stale_pass1_harness_hits:
        failures.append(
            "Stale Pass@1 harness wording found in paper-facing docs: "
            f"{stale_pass1_harness_hits}"
        )

    stale_seed_patterns = [
        "completed seeds 42, 43, 44, 45, 46, 47 |",
        "completed seeds 42, 43, 44, 45, 46, 47`",
        "completed seeds 42, 43, 44, 45, 46, 47\n",
    ]
    stale_seed_hits = []
    stale_gate_variant_ci_hits = []
    for path in doc_guard_paths:
        if not path.exists():
            continue
        text = path.read_text(errors="replace")
        for pattern in stale_seed_patterns:
            if pattern in text:
                stale_seed_hits.append(f"{path}: {pattern.strip()}")
        gate_variant_marker = "Cross-seed score/BM25 gate-variant diagnostic"
        section = ""
        if gate_variant_marker in text:
            section = text.split(gate_variant_marker, 1)[1]
            for boundary in ["\n## ", "\n# ", "\nCross-seed top-1 gate diagnostic"]:
                if boundary in section:
                    section = section.split(boundary, 1)[0]
        if "confidence interval crosses zero" in section:
            stale_gate_variant_ci_hits.append(
                f"{path}: gate-variant diagnostic described as CI crossing zero"
            )
    report["checks"]["stale_seed_provenance_doc_references"] = stale_seed_hits
    report["checks"]["stale_gate_variant_ci_doc_references"] = stale_gate_variant_ci_hits
    if stale_seed_hits:
        failures.append(
            "Stale completed-seed provenance found in paper-facing docs: "
            f"{stale_seed_hits}"
        )
    if stale_gate_variant_ci_hits:
        failures.append(
            "Stale gate-variant CI wording found in paper-facing docs: "
            f"{stale_gate_variant_ci_hits}"
        )

    checklist_path = root / "PAPER_CHECKLIST.md"
    checklist_required_quarantine_phrases = [
        "Deprecated Planning Template",
        "It is not a source of paper results",
        "Do not copy numbers from this checklist into the paper",
    ]
    checklist_forbidden_claim_patterns = [
        "Pass@1 | Tokens/Query | Latency (ms)",
        "| Dense-Only       | 0.45",
        "| SQE (",
        "\"pass@1\": 0.",
        "\"recall@5\": 0.71",
        "Improves Recall@5 by 6.0%",
        "Recall@5 0.71 vs 0.67",
        "p<0.05",
    ]
    checklist_claim_hits = []
    checklist_missing_quarantine_phrases = []
    if checklist_path.exists():
        checklist_text = checklist_path.read_text(errors="replace")
        checklist_missing_quarantine_phrases = [
            phrase
            for phrase in checklist_required_quarantine_phrases
            if phrase not in checklist_text
        ]
        for pattern in checklist_forbidden_claim_patterns:
            if pattern in checklist_text:
                checklist_claim_hits.append(f"{checklist_path}: {pattern}")
    else:
        checklist_missing_quarantine_phrases = checklist_required_quarantine_phrases
    report["checks"]["checklist_missing_quarantine_phrases"] = (
        checklist_missing_quarantine_phrases
    )
    if checklist_missing_quarantine_phrases:
        failures.append(
            "PAPER_CHECKLIST.md is not clearly quarantined as deprecated planning "
            f"material: {checklist_missing_quarantine_phrases}"
        )
    report["checks"]["checklist_forbidden_placeholder_claims"] = checklist_claim_hits
    if checklist_claim_hits:
        failures.append(
            "PAPER_CHECKLIST.md contains fabricated or placeholder numeric claims: "
            f"{checklist_claim_hits}"
        )

    claim_audit_path = root / "CLAIM_AUDIT.md"
    claim_audit_required_phrases = [
        "SQE has only a small retrieval-only Recall@5 improvement over Dense-Only",
        "SQE is not clearly better than Random-Gated-Expansion",
        "Random-Gated-Expansion is backed by executed JSONL evidence",
        "Measured-token reruns support cost claims only",
        "Active paper tables have declared source provenance",
        "Generated hypothetical traces are retrieval probes, not factual logs",
        "Cross-seed top-1 gate diagnostic remains weak",
        "SQE improves downstream software-agent Pass@1 or task success.",
        "Human reviewers validated the generated retrieval queries.",
        "The cross-seed top-1 gate diagnostic establishes a clear improvement over",
        "Measured-token reruns establish retrieval-effectiveness improvements.",
        "Contents of generated hypothetical traces are real historical actions",
        "Results from the legacy `results/` 100-query pilot are active paper evidence.",
    ]
    claim_audit_missing_phrases = []
    if not claim_audit_path.exists():
        claim_audit_missing_phrases = claim_audit_required_phrases
    else:
        claim_audit_text = claim_audit_path.read_text(errors="replace")
        claim_audit_missing_phrases = [
            phrase
            for phrase in claim_audit_required_phrases
            if phrase not in claim_audit_text
        ]
    report["checks"]["claim_audit_missing_required_phrases"] = claim_audit_missing_phrases
    if claim_audit_missing_phrases:
        failures.append(
            "CLAIM_AUDIT.md is missing required supported/unsupported claim "
            f"guardrails: {claim_audit_missing_phrases}"
        )

    no_hallucinated_data_path = root / "NO_HALLUCINATED_DATA.md"
    no_hallucinated_data_required_phrases = [
        "invented, placeholder, or simulated",
        "executed random-gating budget control",
        "is not evidence",
        "active_table_sources",
        "cost measurements",
        "PASS1_RESULTS_SCHEMA.md",
        "template only",
        "unlabeled packets",
        "generated hypothetical traces are method",
        "not factual execution logs",
        "retrieval probes",
    ]
    no_hallucinated_data_missing_phrases = []
    if not no_hallucinated_data_path.exists():
        no_hallucinated_data_missing_phrases = no_hallucinated_data_required_phrases
    else:
        no_hallucinated_data_text = no_hallucinated_data_path.read_text(errors="replace")
        no_hallucinated_data_missing_phrases = [
            phrase
            for phrase in no_hallucinated_data_required_phrases
            if phrase not in no_hallucinated_data_text
        ]
    report["checks"]["no_hallucinated_data_missing_required_phrases"] = (
        no_hallucinated_data_missing_phrases
    )
    if no_hallucinated_data_missing_phrases:
        failures.append(
            "NO_HALLUCINATED_DATA.md is missing required anti-hallucination "
            f"guardrails: {no_hallucinated_data_missing_phrases}"
        )

    llm_usage_path = root / "LLM_USAGE_DISCLOSURE.md"
    llm_usage_required_phrases = [
        "documentation only",
        "not experiment evidence",
        "author remains responsible",
        "not used as a source of experiment evidence",
        "Missing evidence must remain marked as missing",
    ]
    llm_usage_missing_phrases = []
    if not llm_usage_path.exists():
        llm_usage_missing_phrases = llm_usage_required_phrases
    else:
        llm_usage_text = llm_usage_path.read_text(errors="replace")
        llm_usage_missing_phrases = [
            phrase for phrase in llm_usage_required_phrases if phrase not in llm_usage_text
        ]
    report["checks"]["llm_usage_missing_required_phrases"] = llm_usage_missing_phrases
    if llm_usage_missing_phrases:
        failures.append(
            "LLM_USAGE_DISCLOSURE.md is missing required disclosure guardrails: "
            f"{llm_usage_missing_phrases}"
        )

    blocked_next_actions_path = root / "BLOCKED_NEXT_ACTIONS.md"
    blocked_next_actions_required_phrases = [
        "It is not experiment evidence.",
        "current user cannot access Docker daemon",
        "sudo usermod -aG docker nlp-07",
        "Dense-Only",
        "Always-Expand",
        "Random-Gated-Expansion",
        "Selective-QE",
        "labeled_human_audit_queries.csv",
        "human_audit_labeling_manifest.json",
        "human_audit_summary.json",
        "Do not create placeholder Pass@1 rows",
        "Missing evidence must remain marked as missing",
        "checked_at_utc",
    ]
    blocked_next_actions_missing_phrases = []
    if not blocked_next_actions_path.exists():
        blocked_next_actions_missing_phrases = blocked_next_actions_required_phrases
    else:
        blocked_next_actions_text = blocked_next_actions_path.read_text(errors="replace")
        blocked_next_actions_missing_phrases = [
            phrase
            for phrase in blocked_next_actions_required_phrases
            if phrase not in blocked_next_actions_text
        ]
    report["checks"]["blocked_next_actions_missing_required_phrases"] = (
        blocked_next_actions_missing_phrases
    )
    if blocked_next_actions_missing_phrases:
        failures.append(
            "BLOCKED_NEXT_ACTIONS.md is missing required unblock/evidence "
            f"guardrails: {blocked_next_actions_missing_phrases}"
        )

    missing_evidence_path = root / "MISSING_EVIDENCE_BLOCKERS.json"
    missing_evidence_checks = {
        "present": missing_evidence_path.exists(),
        "is_experiment_evidence": None,
        "blocking_count": None,
        "missing_blocker_names": [],
        "missing_required_fields": [],
    }
    required_blocker_names = {
        "Downstream Pass@1 or task-success evaluation",
        "Human-audited query quality labels",
    }
    if not missing_evidence_path.exists():
        missing_evidence_checks["missing_required_fields"].append(str(missing_evidence_path))
    else:
        missing_evidence = read_json(missing_evidence_path)
        missing_evidence_checks["is_experiment_evidence"] = missing_evidence.get(
            "is_experiment_evidence"
        )
        blockers = missing_evidence.get("blockers", [])
        missing_evidence_checks["blocking_count"] = len(blockers)
        names = {blocker.get("name") for blocker in blockers}
        missing_evidence_checks["missing_blocker_names"] = sorted(
            required_blocker_names - names
        )
        if missing_evidence.get("is_experiment_evidence") is not False:
            missing_evidence_checks["missing_required_fields"].append(
                "is_experiment_evidence must be false"
            )
        if len(blockers) != 2:
            missing_evidence_checks["missing_required_fields"].append(
                "expected exactly two missing-evidence blockers"
            )
        if "Do not create placeholder Pass@1 rows" not in missing_evidence.get(
            "non_negotiable_rule", ""
        ):
            missing_evidence_checks["missing_required_fields"].append(
                "non_negotiable_rule must forbid placeholder Pass@1 rows"
            )
        for blocker in blockers:
            if not blocker.get("must_create_real_files"):
                missing_evidence_checks["missing_required_fields"].append(
                    f"{blocker.get('name')}: missing must_create_real_files"
                )
            if not blocker.get("verification_commands"):
                missing_evidence_checks["missing_required_fields"].append(
                    f"{blocker.get('name')}: missing verification_commands"
                )
            if not blocker.get("do_not_use_as_evidence"):
                missing_evidence_checks["missing_required_fields"].append(
                    f"{blocker.get('name')}: missing do_not_use_as_evidence"
                )
    report["checks"]["missing_evidence_blockers"] = missing_evidence_checks
    if missing_evidence_checks["missing_blocker_names"] or missing_evidence_checks[
        "missing_required_fields"
    ]:
        failures.append(
            "MISSING_EVIDENCE_BLOCKERS.json is incomplete or unsafe: "
            f"{missing_evidence_checks}"
        )

    handoff_status_path = root / "HANDOFF_STATUS.md"
    handoff_status_required_phrases = [
        "This file is documentation only. It is not experiment evidence.",
        "paper/main.pdf",
        "paper/main.tex",
        "Salomon DIEI",
        "TODO: add GitHub URL",
        "strong_submission_ready=false",
        "blocking_count=2",
        "Real downstream Pass@1/task-success results are missing.",
        "Real human-audited query-quality labels are missing.",
        "sudo usermod -aG docker nlp-07",
        "Do not create placeholder Pass@1 rows",
        "readiness_pass1_preflight_checked_at_utc",
    ]
    handoff_status_missing_phrases = []
    if not handoff_status_path.exists():
        handoff_status_missing_phrases = handoff_status_required_phrases
    else:
        handoff_status_text = handoff_status_path.read_text(errors="replace")
        handoff_status_missing_phrases = [
            phrase
            for phrase in handoff_status_required_phrases
            if phrase not in handoff_status_text
        ]
    report["checks"]["handoff_status_missing_required_phrases"] = (
        handoff_status_missing_phrases
    )
    if handoff_status_missing_phrases:
        failures.append(
            "HANDOFF_STATUS.md is missing required current-state/blocker "
            f"phrases: {handoff_status_missing_phrases}"
        )

    references_path = paper_dir / "references.bib"
    references_checks = {
        "present": references_path.exists(),
        "missing_required_keys": [],
        "forbidden_loose_entries": [],
        "missing_required_metadata": [],
    }
    if not references_path.exists():
        failures.append("paper/references.bib is missing")
        references_checks["missing_required_keys"] = [
            "gao2023hyde",
            "cormack2009rrf",
            "jimenez2024swebench",
            "karpukhin2020dpr",
            "robertson2009bm25",
        ]
    else:
        references_text = references_path.read_text(errors="replace")
        required_reference_keys = [
            "gao2023hyde",
            "cormack2009rrf",
            "jimenez2024swebench",
            "karpukhin2020dpr",
            "robertson2009bm25",
        ]
        references_checks["missing_required_keys"] = [
            key for key in required_reference_keys if "{" + key + "," not in references_text
        ]
        loose_patterns = [
            "journal={Proceedings of ACL}",
            "journal={Proceedings of EMNLP}",
            "journal={arXiv preprint arXiv:2310.06770}",
            "booktitle={Proceedings of SIGIR}",
        ]
        references_checks["forbidden_loose_entries"] = [
            pattern for pattern in loose_patterns if pattern in references_text
        ]
        required_metadata = {
            "gao2023hyde": [
                "doi={10.18653/v1/2023.acl-long.99}",
                "pages={1762--1777}",
            ],
            "jimenez2024swebench": [
                "booktitle={International Conference on Learning Representations}",
                "url={https://openreview.net/forum?id=VTF8yNQM66}",
            ],
            "karpukhin2020dpr": [
                "doi={10.18653/v1/2020.emnlp-main.550}",
                "pages={6769--6781}",
            ],
            "robertson2009bm25": [
                "doi={10.1561/1500000019}",
                "pages={333--389}",
            ],
        }
        for key, snippets in required_metadata.items():
            for snippet in snippets:
                if snippet not in references_text:
                    references_checks["missing_required_metadata"].append(
                        f"{key}: {snippet}"
                    )
        if references_checks["missing_required_keys"]:
            failures.append(
                "paper/references.bib is missing required citation keys: "
                f"{references_checks['missing_required_keys']}"
            )
        if references_checks["forbidden_loose_entries"]:
            failures.append(
                "paper/references.bib contains loose placeholder-style entries: "
                f"{references_checks['forbidden_loose_entries']}"
            )
        if references_checks["missing_required_metadata"]:
            failures.append(
                "paper/references.bib is missing required venue/DOI/page metadata: "
                f"{references_checks['missing_required_metadata']}"
            )
    report["checks"]["references_bib"] = references_checks

    report["checks"]["paper_author_present"] = "Salomon DIEI" in main_text
    report["checks"]["github_placeholder_present"] = "TODO: add GitHub URL" in main_text
    report["checks"]["huggingface_placeholder_present"] = (
        "TODO: add Hugging Face dataset URL" in main_text
    )
    report["checks"]["hf_release_script_present"] = (
        root / "scripts" / "33_prepare_hf_dataset_release.py"
    ).exists()
    report["checks"]["github_release_script_present"] = (
        root / "scripts" / "34_prepare_github_code_release.py"
    ).exists()
    release_helper_checks = {
        "checked_scripts": [],
        "destructive_patterns": [],
        "missing_noop_clean_guard": [],
    }
    for helper_name in [
        "33_prepare_hf_dataset_release.py",
        "34_prepare_github_code_release.py",
    ]:
        helper_path = root / "scripts" / helper_name
        if not helper_path.exists():
            release_helper_checks["missing_noop_clean_guard"].append(
                f"{helper_name}: missing script"
            )
            continue
        helper_text = helper_path.read_text(errors="replace")
        release_helper_checks["checked_scripts"].append(str(helper_path))
        for pattern in ["shutil.rmtree", ".unlink(", "os.remove(", "os.rmdir("]:
            if pattern in helper_text:
                release_helper_checks["destructive_patterns"].append(
                    f"{helper_name}: {pattern}"
                )
        required_noop_phrases = [
            "--clean",
            "Deprecated no-op retained for compatibility",
            "deprecated and ignored",
            "non-destructive",
        ]
        missing_phrases = [
            phrase for phrase in required_noop_phrases if phrase not in helper_text
        ]
        if missing_phrases:
            release_helper_checks["missing_noop_clean_guard"].append(
                f"{helper_name}: {missing_phrases}"
            )
    report["checks"]["release_helpers_non_destructive"] = release_helper_checks
    if release_helper_checks["destructive_patterns"]:
        failures.append(
            "Release helper scripts contain destructive file-removal patterns: "
            f"{release_helper_checks['destructive_patterns']}"
        )
    if release_helper_checks["missing_noop_clean_guard"]:
        failures.append(
            "Release helper scripts are missing the deprecated no-op --clean guard: "
            f"{release_helper_checks['missing_noop_clean_guard']}"
        )
    github_release_manifest = root / "github_code_release" / "RELEASE_MANIFEST.json"
    github_release_checks = {
        "present": github_release_manifest.exists(),
        "forbidden_paths": [],
        "bad_containment_flags": [],
    }
    if github_release_manifest.exists():
        github_release = read_json(github_release_manifest)
        for key in [
            "contains_raw_memory_stores",
            "contains_detailed_query_rows",
            "contains_pass1_results",
            "contains_human_labels",
            "contains_synthetic_replacement_rows",
        ]:
            if github_release.get(key) is not False:
                github_release_checks["bad_containment_flags"].append(key)
        forbidden_patterns = [
            "memory_store.jsonl",
            "_detailed.jsonl",
            "results_pass1/",
            "labeled_human_audit_queries.csv",
            "human_audit_summary.json",
            "hf_dataset_release/",
            "github_code_release/",
        ]
        for item in github_release.get("files", []):
            path = item.get("path", "")
            if any(pattern in path for pattern in forbidden_patterns):
                github_release_checks["forbidden_paths"].append(path)
    report["checks"]["github_code_release"] = github_release_checks
    main_pdf = paper_dir / "main.pdf"
    report["checks"]["main_pdf_bytes"] = main_pdf.stat().st_size if main_pdf.exists() else 0
    main_pdf_pages = get_pdf_pages(main_pdf)
    report["checks"]["main_pdf_pages"] = main_pdf_pages
    latex_pdf_pages = report["checks"].get("readiness_latex_pdf_pages")
    if latex_pdf_pages is not None and main_pdf_pages != latex_pdf_pages:
        failures.append(
            "LATEX_BUILD_AUDIT.json pdf_pages does not match current paper/main.pdf: "
            f"audit={latex_pdf_pages}, current={main_pdf_pages}"
        )
    if "Salomon DIEI" not in main_text:
        failures.append("paper/main.tex does not contain author Salomon DIEI")
    if "TODO: add GitHub URL" not in main_text:
        failures.append("paper/main.tex does not contain the GitHub URL placeholder")
    if "TODO: add Hugging Face dataset URL" not in main_text:
        failures.append("paper/main.tex does not contain the Hugging Face dataset URL placeholder")
    if not (root / "scripts" / "33_prepare_hf_dataset_release.py").exists():
        failures.append("Hugging Face dataset release helper script is missing")
    if not (root / "scripts" / "34_prepare_github_code_release.py").exists():
        failures.append("GitHub code release helper script is missing")
    if github_release_checks["present"]:
        if github_release_checks["bad_containment_flags"]:
            failures.append(
                "GitHub code release manifest has unsafe containment flags: "
                f"{github_release_checks['bad_containment_flags']}"
            )
        if github_release_checks["forbidden_paths"]:
            failures.append(
                "GitHub code release contains files that belong in the dataset "
                f"or missing-evidence outputs: {github_release_checks['forbidden_paths'][:10]}"
            )
    if not main_pdf.exists() or main_pdf.stat().st_size < 10000:
        failures.append("paper/main.pdf is missing or unexpectedly small")
    pdf_text = extract_pdf_text(main_pdf)
    report["checks"]["main_pdf_text_checked"] = bool(pdf_text)
    if pdf_text:
        gate_pdf_phrase = ""
        gate_json_path = root / "results_multiseed" / "multiseed_gate_validation.json"
        if gate_json_path.exists():
            gate_json = read_json(gate_json_path)
            expansion_rate = gate_json.get("aggregate", {}).get("test_expansion_rate_mean")
            if expansion_rate is not None:
                gate_pdf_phrase = pct(expansion_rate)
        required_pdf_phrases = [
            "Salomon DIEI",
            "TODO: add GitHub URL",
            "TODO: add Hugging Face dataset URL",
            "Related Work",
            "Threats to Validity",
            "Conclusion",
            "Multi-seed retrieval aggregate",
            "Multi-seed gate validation",
            "Recall@5 difference",
            gate_pdf_phrase,
            "Pass@1",
        ]
        required_pdf_phrases = [phrase for phrase in required_pdf_phrases if phrase]
        missing_pdf_phrases = [
            phrase for phrase in required_pdf_phrases if phrase not in pdf_text
        ]
        report["checks"]["main_pdf_missing_phrases"] = missing_pdf_phrases
        if missing_pdf_phrases:
            failures.append(
                f"paper/main.pdf text is stale or incomplete; missing {missing_pdf_phrases}"
            )
        unresolved_pdf_markers = sorted(
            marker for marker in ["??", "[?]"] if marker in pdf_text
        )
        report["checks"]["main_pdf_unresolved_markers"] = unresolved_pdf_markers
        if unresolved_pdf_markers:
            failures.append(
                f"paper/main.pdf contains unresolved LaTeX markers: {unresolved_pdf_markers}"
            )

    table_inputs = set(re.findall(r"\\input\{tables/([^}]+)\}", main_text))
    unknown_table_inputs = sorted(table_inputs - ALLOWED_TABLE_INPUTS)
    deprecated_table_inputs = sorted(table_inputs & DEPRECATED_TABLE_INPUTS)
    report["checks"]["main_tex_table_inputs"] = sorted(table_inputs)
    report["checks"]["unknown_table_inputs"] = unknown_table_inputs
    report["checks"]["deprecated_table_inputs"] = deprecated_table_inputs
    if unknown_table_inputs:
        failures.append(f"Unknown table inputs in main.tex: {unknown_table_inputs}")
    if deprecated_table_inputs:
        failures.append(f"Deprecated table inputs in main.tex: {deprecated_table_inputs}")
    missing_input_tables = [
        name for name in table_inputs if not (paper_dir / "tables" / f"{name}.tex").exists()
    ]
    report["checks"]["missing_input_tables"] = sorted(missing_input_tables)
    if missing_input_tables:
        failures.append(f"main.tex references missing table files: {sorted(missing_input_tables)}")
    table_inventory_path = paper_dir / "table_inventory.json"
    if not table_inventory_path.exists():
        report["checks"]["table_inventory_present"] = False
        failures.append("Missing paper/table_inventory.json")
    else:
        table_inventory = read_json(table_inventory_path)
        inventory_active = set(table_inventory.get("active_tables", []))
        inventory_retained = set(table_inventory.get("retained_tables", []))
        inventory_sources = table_inventory.get("active_table_sources", {})
        all_table_files = {path.stem for path in (paper_dir / "tables").glob("*.tex")}
        inventory_missing_active = sorted(table_inventory.get("missing_active_tables", []))
        active_mismatch = sorted(table_inputs ^ inventory_active)
        retained_mismatch = sorted((all_table_files - table_inputs) ^ inventory_retained)
        source_key_mismatch = sorted(table_inputs ^ set(inventory_sources))
        missing_source_paths = []
        empty_source_tables = []
        for table_name in sorted(table_inputs):
            sources = inventory_sources.get(table_name, [])
            if not sources:
                empty_source_tables.append(table_name)
                continue
            for source in sources:
                if not (root / source).exists():
                    missing_source_paths.append(source)
        report["checks"]["table_inventory_present"] = True
        report["checks"]["table_inventory_active_mismatch"] = active_mismatch
        report["checks"]["table_inventory_missing_active"] = inventory_missing_active
        report["checks"]["table_inventory_retained_mismatch"] = retained_mismatch
        report["checks"]["table_inventory_source_key_mismatch"] = source_key_mismatch
        report["checks"]["table_inventory_empty_source_tables"] = empty_source_tables
        report["checks"]["table_inventory_missing_source_paths"] = sorted(missing_source_paths)
        if active_mismatch:
            failures.append(
                "paper/table_inventory.json active_tables do not match main.tex "
                f"inputs: {active_mismatch}"
            )
        if inventory_missing_active:
            failures.append(
                "paper/table_inventory.json reports missing active tables: "
                f"{inventory_missing_active}"
            )
        if retained_mismatch:
            failures.append(
                "paper/table_inventory.json retained_tables do not match table "
                f"files not imported by main.tex: {retained_mismatch}"
            )
        if source_key_mismatch:
            failures.append(
                "paper/table_inventory.json active_table_sources keys do not "
                f"match main.tex inputs: {source_key_mismatch}"
            )
        if empty_source_tables:
            failures.append(
                "paper/table_inventory.json active_table_sources has empty "
                f"source lists for: {empty_source_tables}"
            )
        if missing_source_paths:
            failures.append(
                "paper/table_inventory.json active_table_sources references "
                f"missing files: {sorted(missing_source_paths)}"
            )

    measured_token_path = (
        root / "results_tokenmeasured_500_seed42" / "selective_tokenmeasured500_summary.json"
    )
    measured_token_summary = read_json(measured_token_path) if measured_token_path.exists() else {}
    report["checks"]["measured_token_summary"] = str(measured_token_path) if measured_token_summary else ""
    if not any("avg_total_tokens_per_query" in s and s["avg_total_tokens_per_query"] for s in summaries.values()):
        if not measured_token_summary.get("avg_total_tokens_per_query"):
            warnings.append("No completed summary contains measured token counts")

    verify_multiseed_artifacts(root, failures, report)
    verify_random_gated_execution(root, failures, report)
    verify_human_audit(root, eval_rows, failures, warnings, report)

    report["warnings"] = warnings
    report["failures"] = failures
    output = json.dumps(report, indent=2)
    print(output)
    if args.report_path:
        Path(args.report_path).write_text(output + "\n")
    return 1 if failures else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data_dir", default="data_500_memory_seed42")
    parser.add_argument("--index_dir", default="index_500_seed42")
    parser.add_argument("--results_dir", default="results_500_memory_seed42")
    parser.add_argument("--paper_dir", default="paper")
    parser.add_argument("--report_path", default="")
    parser.add_argument(
        "--skip_manifest_freshness",
        action="store_true",
        help=(
            "Skip ARTIFACT_MANIFEST freshness checks. Intended only for pipeline "
            "stages that write verification reports before regenerating the final manifest."
        ),
    )
    raise SystemExit(main(parser.parse_args()))
