# SQE Experiment Status

Author: Salomon DIEI

## Current completed runs

Primary seed-42 results directory:

`/home/nlp-07/sqe_experiment/results_500_memory_seed42`

Dataset:

- Memory store: 5,000 SWE-smith software-engineering agent episodes
- Evaluation set: 500 generated natural-language query-memory pairs
- Evaluation targets: sampled from the indexed memory store
- Embedding model: BAAI/bge-m3
- Generator model: Qwen3.6-35B-A3B served through vLLM
- Retrieval depth: top 10

Active independent memory-index seeds:

- Data: `data_500_memory_seed43`
- Index: `index_500_seed43`
- Results: `results_500_memory_seed43`
- Verification: `results_500_memory_seed43/verification_report.json`
- Status: verifier passed with zero failures and zero warnings.
- Data: `data_500_memory_seed44`
- Index: `index_500_seed44`
- Results: `results_500_memory_seed44`
- Verification: `results_500_memory_seed44/verification_report.json`
- Status: verifier passed with zero failures and zero warnings.
- Note: seeds 42 through 49 rebuild the memory store and index independently.
  The tables below show seed 42 as the detailed audit anchor and seeds 43 and
  44 as examples; the active paper aggregate uses all eight seeds.

Historical fixed-memory query seeds:

- `results_500_query_seed43_memory_seed42`
- `results_500_query_seed44_memory_seed42`
- Status: executed and retained as secondary provenance only. They are not the
  active paper aggregate.

Important correction:

- An earlier 500-query directory, `data_500_seed42`, sampled eval targets from
  held-out episodes outside the indexed memory store. That made Recall@K
  necessarily zero and invalid for retrieval evaluation.
- `scripts/01_prepare_dataset.py` now defaults to `--eval_source memory`, and
  the corrected dataset is `data_500_memory_seed42`.
- The corrected memory checksum matches the built index:
  `afe1b7c054d3fb96e8119f11cbc322d5f86504b559ae3a4acd9ea0f572863325`.

## Main results

The table below is the corrected seed-42 memory-target run currently used by
`paper/main.tex`.

| Method | Recall@1 | Recall@5 | Recall@10 | MRR | Expansion rate |
|---|---:|---:|---:|---:|---:|
| Dense-Only | 49.0 | 69.8 | 75.4 | 57.4 | -- |
| BM25-Only | 17.6 | 31.4 | 35.8 | 23.3 | -- |
| Hybrid-RRF | 35.4 | 64.0 | 73.2 | 47.4 | -- |
| Paraphrases-Only | 47.0 | 68.2 | 75.0 | 56.0 | 100.0 |
| HyDE-Traces-Only | 36.2 | 64.0 | 70.4 | 47.9 | 100.0 |
| Always-Expand | 42.2 | 68.0 | 75.6 | 53.2 | 100.0 |
| Random-Gated-Expansion | 46.0 | 69.0 | 75.8 | 55.3 | 47.0 |
| Selective-QE | 47.2 | 69.4 | 75.4 | 56.4 | 46.0 |

Active independent memory-index seed 43:

| Method | Recall@1 | Recall@5 | Recall@10 | MRR | Expansion rate |
|---|---:|---:|---:|---:|---:|
| Dense-Only | 44.6 | 66.4 | 72.6 | 53.9 | -- |
| BM25-Only | 16.4 | 30.2 | 35.0 | 22.2 | -- |
| Hybrid-RRF | 32.6 | 60.8 | 69.4 | 44.0 | -- |
| Paraphrases-Only | 42.2 | 66.8 | 73.0 | 52.8 | 100.0 |
| HyDE-Traces-Only | 32.6 | 61.4 | 68.2 | 44.1 | 100.0 |
| Always-Expand | 38.6 | 66.6 | 74.2 | 50.4 | 100.0 |
| Random-Gated-Expansion | 42.2 | 66.2 | 73.2 | 52.3 | 47.4 |
| Selective-QE | 43.8 | 66.4 | 73.8 | 53.5 | 49.6 |

Active independent memory-index seed 44:

| Method | Recall@1 | Recall@5 | Recall@10 | MRR | Expansion rate |
|---|---:|---:|---:|---:|---:|
| Dense-Only | 48.0 | 72.0 | 77.4 | 58.6 | -- |
| BM25-Only | 17.2 | 28.6 | 34.0 | 22.0 | -- |
| Hybrid-RRF | 34.0 | 67.2 | 75.2 | 47.4 | -- |
| Paraphrases-Only | 47.4 | 71.8 | 76.8 | 57.9 | 100.0 |
| HyDE-Traces-Only | 39.0 | 67.8 | 74.8 | 51.2 | 100.0 |
| Always-Expand | 44.2 | 74.2 | 79.4 | 57.3 | 100.0 |
| Random-Gated-Expansion | 44.6 | 72.2 | 78.4 | 56.6 | 50.4 |
| Selective-QE | 48.4 | 72.8 | 78.6 | 59.3 | 44.6 |

Eight completed retrieval seeds are aggregated in
`results_multiseed/multiseed_report.json` and
`paper/tables/multiseed_summary.tex`. This is an 8-seed independent memory-index
aggregate.

Eight-seed aggregate:

| Method | Seeds | Recall@1 | Recall@5 | Recall@10 |
|---|---:|---:|---:|---:|
| Dense-Only | 8 | 45.5 | 68.5 | 74.2 |
| Hybrid-RRF | 8 | 31.3 | 63.5 | 72.7 |
| Always-Expand | 8 | 39.8 | 69.2 | 75.9 |
| Random-Gated-Expansion | 8 | 42.6 | 68.9 | 75.0 |
| Selective-QE | 8 | 44.6 | 69.4 | 75.3 |

Interpretation:

- Dense-only remains stronger than Selective-QE on mean Recall@1.
- Selective-QE improves Recall@5 over Hybrid-RRF by +5.85 points, with paired
  bootstrap CI [+4.75, +6.98], and has a small retrieval-only improvement over
  Dense-Only of +0.875 points, CI [+0.10, +1.65].
- Always-on expansion has the best mean Recall@5 and Recall@10, but expands all
  queries and has lower mean Recall@1 than Dense-Only.
- Random-gated expansion reaches similar performance to Selective-QE at the
  same approximate expansion budget. This weakens the current evidence for the
  top-1 score gate.
- Trace-only expansion is weak; paraphrases are better but still below Dense-Only.
- The gate reduces estimated LLM calls from 3.00/query to 1.38/query, but it is
  not well calibrated: expanded queries have lower Recall@5 than non-expanded
  queries.

## Cost and uncertainty diagnostics

| Method | Expansion rate | Estimated LLM calls/query |
|---|---:|---:|
| Dense-Only | -- | 0.00 |
| BM25-Only | -- | 0.00 |
| Hybrid-RRF | -- | 0.00 |
| Paraphrases-Only | 100.0 | 1.00 |
| HyDE-Traces-Only | 100.0 | 2.00 |
| Always-Expand | 100.0 | 3.00 |
| Random-Gated-Expansion | 47.0 | 1.41 |
| Selective-QE | 46.0 | 1.38 |

Measured token reruns:

- Directory: `results_tokenmeasured_500_seed42`
- Queries per method: 500

| Method | Expanded % | Actual calls/query | Prompt tokens/query | Total tokens/query | Latency seconds/query |
|---|---:|---:|---:|---:|---:|
| Selective-QE | 46.0 | 1.38 | 209.2 | 405.1 | 2.77 |
| Always-Expand | 100.0 | 2.99 | 455.5 | 899.3 | 5.37 |
| HyDE-Traces-Only | 100.0 | 2.00 | 367.0 | 758.2 | 3.99 |
| Paraphrases-Only | 100.0 | 1.00 | 88.5 | 131.6 | 1.02 |
| Random-Gated-Expansion | 47.0 | 1.41 | 214.6 | 423.9 | 2.40 |

Paired bootstrap Recall@5 deltas for Selective-QE:

| Baseline | Delta | 95% CI | Bootstrap p |
|---|---:|---:|---:|
| Dense-Only | +0.1 | [-1.1, +1.4] | 0.439 |
| Hybrid-RRF | +5.5 | [+3.8, +7.4] | 0.000 |
| Always-Expand | -0.1 | [-1.0, +0.9] | 0.478 |
| Random-Gated-Expansion | +0.4 | [-0.7, +1.5] | 0.254 |
| Paraphrases-Only | +0.6 | [-0.7, +2.0] | 0.203 |
| HyDE-Traces-Only | +5.1 | [+3.5, +6.8] | 0.000 |

## Generated paper artifacts

Paper directory:

`/home/nlp-07/sqe_experiment/paper`

Files:

- `paper/main.tex`
- `paper/main.pdf`
- `paper/README.md`
- `paper/references.bib`
- `paper/table_inventory.json`
- `paper/tables/main_results.tex`
- `paper/tables/cost_summary.tex`
- `paper/tables/measured_token_cost.tex`
- `paper/tables/paired_tests.tex`
- `paper/tables/gate_diagnostics.tex`
- `paper/tables/gate_headroom_diagnostics.tex`
- `paper/tables/gate_variant_diagnostics.tex`
- `paper/tables/multiseed_gate_validation.tex`
- `paper/tables/cross_seed_top1_gate.tex`
- `paper/tables/multiseed_paired_tests.tex`
- `paper/tables/multiseed_summary.tex`
- `paper/tables/threshold_sweep.tex`
- `paper/tables/validation_threshold.tex`
- `paper/tables/experiment_manifest.tex`
- `paper/tables/win_loss_analysis.tex`
- `paper/figures/recall_at_5.png`
- `paper/figures/gate_diagnostic.png`
- `paper/figures/threshold_sensitivity.png`
- `results_500_memory_seed42/verification_report.json`
- `DATA_PROVENANCE.md`
- `human_audit/human_audit_queries.jsonl`
- `human_audit/human_audit_queries.csv`
- `human_audit/human_audit_manifest.json`

## Code changes completed

- `scripts/01_prepare_dataset.py`
  - Added `--seed` for reproducible dataset sampling.
- `scripts/04_run_proposed_method.py`
  - Added ablation modes:
    - `selective`
    - `always_expand`
    - `traces_only`
    - `paraphrases_only`
    - `dense_only`
    - `random_budget`
  - Added per-query latency and estimated LLM call tracking for future runs.
  - Added real LLM usage capture from `resp.usage` for prompt,
    completion, and total tokens in future runs.
  - Added `--expansion_cache` so future ablations can reuse the same generated
    traces and paraphrases instead of comparing different random generations.
- `scripts/06_make_paper_artifacts.py`
  - Added paper artifact generation from result JSON/JSONL files.
  - Generates LaTeX tables, figures, `main.tex`, references, and enriched report JSON.
  - Defaults to `results_500_memory_seed42/` so direct runs use the active
    500-query evidence instead of the legacy 100-query pilot in `results/`.
  - Generates `paper/table_inventory.json`, including `active_table_sources`
    so every active table imported by `main.tex` maps to concrete source files.
- `scripts/07_verify_experiment.py`
  - Verifies eval-target membership in memory/index, result-summary consistency,
    required paper artifacts, and absence of forbidden synthetic-evidence references in
    active paper/report files.
  - Rejects stale 100-query headline metrics and active references to legacy
    `results/full_report*`, `results/baselines_summary*`, and
    `results/proposed*` artifacts.
  - Rejects unsupported positive claims such as downstream Pass@1 improvement,
    superiority over Dense-Only or Random-Gated-Expansion, human-validated
    query quality, or state-of-the-art claims.
  - Verifies that every active table in `paper/table_inventory.json` has
    non-empty source files and that those source files exist.
- `scripts/08_prepare_human_audit.py`
  - Creates a human-audit packet from real eval queries and target memory
    excerpts.
  - Leaves reviewer fields blank. It does not create labels or paper results.
- `scripts/17_verify_pass1_results.py`
  - Verifies future downstream Pass@1 artifacts by requiring a manifest,
    detailed task rows, a summary, failure reasons for failed tasks, and
    recomputed method-level Pass@1 consistency.
- `scripts/18_verify_human_audit_labels.py`
  - Verifies future human-label artifacts by requiring a separate labeled CSV,
    labeling manifest, and recomputed summary. It rejects missing labels and
    changed source query/target fields.
- `scripts/20_summarize_human_audit_labels.py`
  - Creates `human_audit_summary.json` only from an existing labeled human-audit
    CSV with valid reviewer labels. It does not create labels.
  - Requires the labeled CSV to cover the source audit packet and preserve
    `query_id`, `query`, `target_episode_id`, and `target_excerpt` before writing
    a summary.
- `scripts/21_summarize_pass1_results.py`
  - Creates `pass1_summary.json` only from existing downstream task-attempt
    JSONL rows. It does not run agents or invent outcomes.
- `scripts/23_import_evoagentbench_pass1.py`
  - Converts completed EvoAgentBench job `result.json` files into
    `results_pass1/*_detailed.jsonl` rows.
  - Does not run agents, does not create task outcomes, and refuses to overwrite
    an existing method file unless `--overwrite` is passed.
- `scripts/run_ablation_suite.sh`
  - Added a reproducible command script for the current ablation suite.
  - Uses a shared expansion cache across SQE modes for fair future reruns.
  - Uses the corrected `data_500_memory_seed42` and `index_500_seed42` paths.
  - Supports `RUN_TOKEN_MEASURED=1` for the slow measured-token Selective-QE
    rerun, and `RUN_TOKEN_MEASURED=all` for all expansion ablations.
- `scripts/run_fixed_memory_eval_seed.sh`
  - Runs additional query-sampling seeds over the corrected seed-42 memory/index
    without rebuilding the memory index.
- `scripts/09_make_multiseed_report.py`
  - Aggregates completed seed result directories only.
  - Emits a warning instead of filling in missing seeds.
- `scripts/15_gate_variant_diagnostics.py`
  - Recombines executed dense-only, BM25-only, and always-expand rows to test
    score-only and BM25-agreement gate variants on train/test query halves.
  - Produces `results_gate_calibration/gate_variant_diagnostics.json` and
    `paper/tables/gate_variant_diagnostics.tex`.
- `scripts/19_win_loss_analysis.py`
  - Recomputes query-level top-5 wins and losses between Dense-Only and
    Selective-QE from executed detailed rows for seeds 42, 43, 44, 45, 46, 47, 48, and 49.
  - Produces `results_multiseed/win_loss_analysis.json` and
    `paper/tables/win_loss_analysis.tex`.
- `scripts/22_gate_feature_diagnostics.py`
  - Computes dense score features from saved FAISS indexes and BM25 agreement
    from saved BM25 indexes, then recombines executed Dense-Only and
    Always-Expand rows on a train/test query split.
  - Produces `results_gate_calibration/gate_feature_diagnostics.json` and
    `paper/tables/gate_feature_diagnostics.tex`.
- `scripts/29_cross_seed_top1_gate.py`
  - Selects a top-1-score threshold on two independent memory-index seeds and
    evaluates on the held-out seed, recombining only executed Dense-Only and
    Always-Expand rows.
  - Produces `results_gate_calibration/cross_seed_top1_gate.json` and
    `paper/tables/cross_seed_top1_gate.tex`.

## Current limitations

- Evaluation has eight completed 500-query independent memory-index seeds.
- Historical fixed-memory query-sampling seeds are retained as secondary
  provenance only and are not the active paper aggregate.
- Queries are generated, not human-authored or real future-agent queries.
  A 100-query human-audit packet exists, but it is unlabeled and must not be
  reported as a human evaluation until reviewers fill it and the labeling
  protocol is documented. `scripts/18_verify_human_audit_labels.py` currently
  fails as expected because the labeled files are absent.
- No downstream Pass@1 or task-success evaluation has been run.
  `scripts/17_verify_pass1_results.py` currently fails as expected because
  `results_pass1/` does not exist.
  EvoAgentBench provides a plausible SWE-bench runner, and an importer now
  exists for completed job outputs, but no SQE method-comparison Pass@1 run has
  been executed or imported.
- The eight-seed independent memory-index aggregate is still weak for a
  top-conference claim because Selective-QE has only a small retrieval-only
  improvement over Dense-Only and does not clearly beat Random-Gated-Expansion
  on Recall@5.
- No learned gate has been tested. A post-hoc threshold sweep
  suggests threshold 0.62 is better than 0.65 on this split, but this is not a
  validation result and should not be claimed as tuned performance. A simple
  first-half/second-half validation check selects threshold 0.50, while the
  fixed 0.65 threshold performs better on the second half, so the threshold
  choice is unstable. A BM25-agreement gate diagnostic was added, but the
  held-out gain remains small and uses a high expansion rate, so it does not
  remove this limitation. A dense-margin and score-concentration diagnostic
  using saved indexes improved held-out Recall@5 only slightly, with mean
  held-out R@5 68.4 versus dense 67.7 at 16.9% expansion, so it also does not
  remove this limitation. A leave-one-seed-out top-1 gate selects threshold
  0.59 and reports 69.9% Recall@5 versus 69.4% for Dense-Only at 12.5%
  expansion, but the confidence interval crosses zero. A held-out headroom
  diagnostic shows that a perfect gate over executed Dense-Only and
  Always-Expand rows could improve Recall@5, but helpful and harmful expansion
  cases are close enough that simple gates have not recovered the oracle gain.
- Token-level LLM cost has been logged for full 500-query measured reruns of
  Selective-QE, Always-Expand, HyDE-Traces-Only, Paraphrases-Only, and
  Random-Gated-Expansion. These reruns are reported as cost measurements; the
  original independent memory-index retrieval runs remain the effectiveness
  comparison.
- LaTeX build is verified with `/home/nlp-07/.local/bin/tectonic-musl`.
  The compiled PDF is `paper/main.pdf`.
- `scripts/07_verify_experiment.py` passes on independent memory-index seeds
  42, 43, and 44 with zero failures.

## Required next experiments for a top-conference submission

1. Add human-audited labels and pass `scripts/18_verify_human_audit_labels.py`.
2. Add downstream software-agent Pass@1 evaluation and pass
   `scripts/17_verify_pass1_results.py`.
3. Add stronger gate variants:
   - top-1/top-2 dense margin
   - dense-sparse agreement
   - top-k score concentration
   - learned logistic gate
4. Improve the gate or retrieval method enough to produce a clear held-out
   improvement over Dense-Only and Random-Gated-Expansion.
5. Keep the paper claim constrained to the actual finding: SQE has only a small
   retrieval-only improvement over dense retrieval, is not clearly better than a
   random-gated control, but is cheaper than always-on expansion and better than
   Hybrid-RRF/trace-only expansion on Recall@5.
