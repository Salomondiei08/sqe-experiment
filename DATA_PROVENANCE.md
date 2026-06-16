# Data Provenance Audit

This file records where each paper number comes from. The rule for the paper is:
use executed experiment outputs or deterministic recomputations from executed
outputs only. Do not present simulated or invented values as experiment results.

## Valid Executed Runs

Artifact checksum manifest:

- Output: `ARTIFACT_MANIFEST.json`
- Generator: `scripts/13_make_artifact_manifest.py`
- Status: records file sizes and SHA256 checksums for active paper artifacts,
  result summaries, verification reports, multiseed reports, measured-token
  summary, scripts, project documentation, and the human-audit rubric. It is a
  reproducibility aid, not a metric source.

Submission-readiness report:

- Output: `SUBMISSION_READINESS.json`
- Generator: `scripts/14_submission_readiness_check.py`
- Status: conservative checklist for strong-submission evidence. It currently
  marks the package as not strong-submission ready because downstream
  Pass@1/task-success results and human labels are missing, and the method is
  not clearly better than the executed random-gating budget control.

Next-experiments plan:

- Output: `NEXT_EXPERIMENTS.md`
- Status: concrete plan for the missing strong-submission evidence. It contains
  commands, expected evidence files, and acceptance bars. It is not a result
  source.

Corrected main run:

- Data: `data_500_memory_seed42/`
- Index: `index_500_seed42/`
- Results: `results_500_memory_seed42/`
- Verification: `results_500_memory_seed42/verification_report.json`

Completed active independent memory-index seeds:

- Data: `data_500_memory_seed43/`
- Index: `index_500_seed43/`
- Results: `results_500_memory_seed43/`
- Verification: `results_500_memory_seed43/verification_report.json`
- Data: `data_500_memory_seed44/`
- Index: `index_500_seed44/`
- Results: `results_500_memory_seed44/`
- Verification: `results_500_memory_seed44/verification_report.json`
- Data: `data_500_memory_seed45/` through `data_500_memory_seed49/`
- Index: `index_500_seed45/` through `index_500_seed49/`
- Results: `results_500_memory_seed45/` through `results_500_memory_seed49/`
- Verification: `results_500_memory_seed45/verification_report.json` through
  `results_500_memory_seed49/verification_report.json`
- Status: executed and verified. These rebuild the memory store and index for
  each seed and are the active multiseed evidence used by the paper.

Historical fixed-memory query seeds:

- Data: `data_500_query_seed43_memory_seed42/`
- Index: `index_500_seed42/`
- Results: `results_500_query_seed43_memory_seed42/`
- Verification: `results_500_query_seed43_memory_seed42/verification_report.json`
- Data: `data_500_query_seed44_memory_seed42/`
- Index: `index_500_seed42/`
- Results: `results_500_query_seed44_memory_seed42/`
- Verification: `results_500_query_seed44_memory_seed42/verification_report.json`
- Status: executed and verified, but retained as historical secondary evidence
  only. These reuse the corrected seed-42 memory store and index while sampling
  new query sets with seeds 43 and 44. They are not the active paper aggregate.

Measured-token reruns:

- Results: `results_tokenmeasured_500_seed42/`
- Summary: `results_tokenmeasured_500_seed42/selective_tokenmeasured500_summary.json`
- Detailed rows: `results_tokenmeasured_500_seed42/selective_tokenmeasured500_detailed.jsonl`
- Additional summaries:
  `always_expand_tokenmeasured500_summary.json`,
  `traces_only_tokenmeasured500_summary.json`,
  `paraphrases_only_tokenmeasured500_summary.json`, and
  `random_budget_tokenmeasured500_summary.json`
- Status: executed 500-query cost measurements for all expansion ablations.
  These files support measured calls, prompt tokens, completion tokens, total
  tokens, and latency. They are cost measurements, not the main retrieval-
  effectiveness comparison.

Expansion caches and hypothetical traces:

- Files: `results_500_memory_seed*/expansion_cache.json`
- Status: method-input caches for generated query variants. They can explain
  what text was submitted to retrieval during SQE runs, but their contents are
  not factual execution logs, task-success evidence, human labels, or standalone
  empirical evidence. Retrieval metrics must come from executed per-query result
  rows and deterministic summaries, not from treating generated trace text as
  observed software executions.

Human-audit packet:

- Source: `data_500_memory_seed42/eval_pairs.jsonl`
- Output: `human_audit/human_audit_queries.jsonl`
- Output: `human_audit/human_audit_queries.csv`
- Manifest: `human_audit/human_audit_manifest.json`
- Reviewer rubric: `human_audit/README.md`
- Status: unlabeled packet only. The reviewer fields are intentionally blank,
  and no human-evaluation result should be claimed from these files yet.

Required human-label evidence before reporting audit rates:

- `human_audit/labeled_human_audit_queries.csv`
- `human_audit/human_audit_labeling_manifest.json`
- `human_audit/human_audit_summary.json`
- Verifier: `scripts/18_verify_human_audit_labels.py`

Required downstream task-success evidence before reporting Pass@1:

- `results_pass1/manifest.json`
- `results_pass1/*_detailed.jsonl`
- `results_pass1/pass1_summary.json`
- Verifier: `scripts/17_verify_pass1_results.py`

Multiseed report:

- Output: `results_multiseed/multiseed_report.json`
- Table: `paper/tables/multiseed_summary.tex`
- Source: completed independent memory-index seed result directories only.
- Seed family: `independent_memory`
- Status: contains eight completed seeds, 42, 43, 44, 45, 46, 47, 48, and 49. It is referenced by
  `paper/main.tex` as the active independent memory-index retrieval aggregate.

Multiseed paired bootstrap:

- Output: `results_multiseed/multiseed_paired_tests.json`
- Table: `paper/tables/multiseed_paired_tests.tex`
- Source: completed independent memory-index detailed JSONL files for seeds
  42, 43, 44, 45, 46, 47, 48, and 49.
- Seed family: `independent_memory`
- Status: deterministic recomputation over executed retrieval rows. It aligns
  rows by query id within each seed and does not impute missing values.

Win/loss analysis:

- Output: `results_multiseed/win_loss_analysis.json`
- Table: `paper/tables/win_loss_analysis.tex`
- Source: completed independent memory-index Dense-Only and Selective-QE
  detailed JSONL files for seeds 42, 43, 44, 45, 46, 47, 48, and 49.
- Status: deterministic query-level diagnostic. It counts Selective-QE wins when
  SQE retrieves the target in the top 5 and Dense-Only does not, and losses when
  Dense-Only retrieves the target and SQE does not. It does not create new
  retrieval data.

Multiseed gate validation:

- Output: `results_multiseed/multiseed_gate_validation.json`
- Table: `paper/tables/multiseed_gate_validation.tex`
- Seed family: `independent_memory`
- Source: completed independent memory-index dense-only and always-expand
  detailed JSONL files for seeds 42, 43, 44, 45, 46, 47, 48, and 49.
- Status: deterministic split validation over executed retrieval rows. For each
  seed, it selects a top-1-score threshold on the first half of sorted query IDs
  and evaluates the recombined dense/always-expand rows on the second half.

Gate-variant diagnostics:

- Output: `results_gate_calibration/gate_variant_diagnostics.json`
- Table: `paper/tables/gate_variant_diagnostics.tex`
- Source: completed independent memory-index dense-only, BM25-only, and
  always-expand detailed JSONL files for seeds 42, 43, 44, 45, 46, 47, 48, and 49.
- Status: deterministic split diagnostic over executed retrieval rows. For each
  seed, it selects among score-only and BM25-agreement gate variants on the
  first half of sorted query IDs and evaluates the selected variant on the
  second half. It is not a new retrieval run and does not generate data.

Gate-feature diagnostics:

- Output: `results_gate_calibration/gate_feature_diagnostics.json`
- Table: `paper/tables/gate_feature_diagnostics.tex`
- Source: saved FAISS/BM25 indexes plus completed independent memory-index
  Dense-Only and Always-Expand detailed JSONL files for seeds 42, 43, 44, 45, 46, 47, 48, and 49.
- Status: deterministic split diagnostic. It computes dense top-k score
  features from saved indexes, selects a gate on the first half of sorted query
  IDs, and evaluates by recombining executed Dense-Only and Always-Expand rows
  on the second half. It does not run query expansion or generate LLM data.

Cross-seed top-1 gate diagnostic:

- Output: `results_gate_calibration/cross_seed_top1_gate.json`
- Table: `paper/tables/cross_seed_top1_gate.tex`
- Generator: `scripts/29_cross_seed_top1_gate.py`
- Source: completed independent memory-index Dense-Only and Always-Expand
  detailed JSONL files for seeds 42, 43, 44, 45, 46, 47, 48, and 49.
- Status: deterministic diagnostic over executed retrieval rows. For each fold,
  it selects a top-1-score threshold on two independent memory-index seeds and
  evaluates the recombined dense/always-expand rows on the held-out seed. It
  does not run query expansion, generate LLM data, or support a clear
  effectiveness claim because its confidence interval crosses zero.

Cross-seed score/BM25 gate-variant diagnostic:

- Output: `results_gate_calibration/cross_seed_gate_variant.json`
- Table: `paper/tables/cross_seed_gate_variant.tex`
- Generator: `scripts/32_cross_seed_gate_variant.py`
- Source: completed independent memory-index Dense-Only, BM25-Only, and
  Always-Expand detailed JSONL files for seeds 42, 43, 44, 45, 46, 47, 48, and 49.
- Status: retained deterministic diagnostic over executed retrieval rows. For
  each fold, it selects a score/BM25 gate on seven held-in independent
  memory-index seeds and evaluates the recombined dense/always-expand rows on
  the held-out seed.
  It does not run query expansion, generate LLM data, or support a clear SQE
  effectiveness claim because it is a separate score/BM25 gate diagnostic
  rather than the proposed SQE method or downstream Pass@1 evidence.

## Paper Tables

Machine-readable active-table provenance:

- Inventory: `paper/table_inventory.json`
- Field: `active_table_sources`
- Status: generated from `paper/main.tex` by
  `scripts/06_make_paper_artifacts.py`. Each active table imported by the paper
  has a non-empty list of concrete source files. The verifier fails if the
  inventory omits an active table, lists an empty source list, or references a
  missing source file.

| Paper artifact | Source | Type |
|---|---|---|
| `paper/tables/main_results.tex` | `results_500_memory_seed42/*_detailed.jsonl` and `*_summary.json` | Executed retrieval runs |
| `paper/tables/cost_summary.tex` | `results_500_memory_seed42/*_detailed.jsonl` metadata | Executed retrieval runs, estimated calls |
| `paper/tables/measured_token_cost.tex` | `results_tokenmeasured_500_seed42/*_tokenmeasured500_summary.json` | Executed token-measured reruns |
| `paper/tables/paired_tests.tex` | Paired bootstrap over `results_500_memory_seed42/*_detailed.jsonl` | Deterministic statistical recomputation |
| `paper/tables/gate_diagnostics.tex` | `results_500_memory_seed42/proposed_detailed.jsonl` | Deterministic aggregation |
| `paper/tables/threshold_sweep.tex` | `dense_only_detailed.jsonl` plus `always_expand_detailed.jsonl` | Deterministic post-hoc diagnostic |
| `paper/tables/validation_threshold.tex` | `dense_only_detailed.jsonl` plus `always_expand_detailed.jsonl` | Deterministic split diagnostic |
| `paper/tables/experiment_manifest.tex` | `data_500_memory_seed42/dataset_manifest.json` and fixed run config | Manifest metadata |
| `paper/tables/multiseed_summary.tex` | `results_multiseed/multiseed_report.json` from completed seeds 42, 43, 44, 45, 46, 47, 48, and 49 | Deterministic aggregation of executed retrieval runs |
| `paper/tables/multiseed_paired_tests.tex` | `results_multiseed/multiseed_paired_tests.json` from completed seeds 42, 43, 44, 45, 46, 47, 48, and 49 | Deterministic paired bootstrap over executed retrieval rows |
| `paper/tables/win_loss_analysis.tex` | `results_multiseed/win_loss_analysis.json` from completed seeds 42, 43, 44, 45, 46, 47, 48, and 49 | Deterministic query-level comparison over executed retrieval rows |
| `paper/tables/multiseed_gate_validation.tex` | `results_multiseed/multiseed_gate_validation.json` from completed seeds 42, 43, 44, 45, 46, 47, 48, and 49 | Deterministic split validation over executed retrieval rows |
| `paper/tables/gate_variant_diagnostics.tex` | `results_gate_calibration/gate_variant_diagnostics.json` from completed seeds 42, 43, 44, 45, 46, 47, 48, and 49 | Deterministic split diagnostic over executed retrieval rows |
| `paper/tables/gate_headroom_diagnostics.tex` | `results_gate_calibration/gate_headroom_diagnostics.json` from completed seeds 42, 43, 44, 45, 46, 47, 48, and 49 | Deterministic held-out headroom diagnostic over executed retrieval rows |
| `paper/tables/gate_feature_diagnostics.tex` | `results_gate_calibration/gate_feature_diagnostics.json` from saved indexes and completed seeds 42, 43, 44, 45, 46, 47, 48, and 49 | Retained deterministic score-feature diagnostic; not imported by `paper/main.tex` |
| `paper/tables/cross_seed_gate_variant.tex` | `results_gate_calibration/cross_seed_gate_variant.json` from completed seeds 42, 43, 44, 45, 46, 47, 48, and 49 | Retained deterministic cross-seed score/BM25 diagnostic; not imported by `paper/main.tex` |

## Paper Figures

| Paper artifact | Source | Type |
|---|---|---|
| `paper/figures/recall_at_5.png` | `results_500_memory_seed42/*_detailed.jsonl` | Executed retrieval runs |
| `paper/figures/gate_diagnostic.png` | `results_500_memory_seed42/proposed_detailed.jsonl` | Deterministic aggregation |
| `paper/figures/threshold_sensitivity.png` | `dense_only_detailed.jsonl` plus `always_expand_detailed.jsonl` | Deterministic post-hoc diagnostic |

## Excluded Non-Evidence Files

These files are intentionally not referenced by `paper/main.tex` and are kept
only because server files should not be deleted. They are not evidence for any
claim in the paper:

- Deprecated random-gated table artifacts under `deprecated_non_evidence/`
- `deprecated_non_evidence/measured_token_pilot.tex`

The legacy `results/` directory is also inactive. It contains an older
100-query pilot run and must not be used for paper claims. Active effectiveness
artifacts are under `results_500_memory_seed42/`,
`results_500_memory_seed43/`, `results_500_memory_seed44/`,
`results_500_memory_seed45/`, `results_500_memory_seed46/`,
`results_500_memory_seed47/`, `results_500_memory_seed48/`,
`results_500_memory_seed49/`, and
`results_multiseed/`.

The paper may use `Random-Gated-Expansion` only because it is backed by
executed JSONL rows. This baseline runs the same
expansion-and-retrieval code path as SQE, but replaces SQE's confidence gate
with random expansion decisions at a comparable expansion rate.

- `results_500_memory_seed42/random_budget_summary.json`
- `results_500_memory_seed42/random_budget_detailed.jsonl`
- `results_500_memory_seed43/random_budget_summary.json`
- `results_500_memory_seed43/random_budget_detailed.jsonl`
- `results_500_memory_seed44/random_budget_summary.json`
- `results_500_memory_seed44/random_budget_detailed.jsonl`
- `results_500_memory_seed45/random_budget_summary.json`
- `results_500_memory_seed45/random_budget_detailed.jsonl`
- `results_500_memory_seed46/random_budget_summary.json`
- `results_500_memory_seed46/random_budget_detailed.jsonl`
- `results_500_memory_seed47/random_budget_summary.json`
- `results_500_memory_seed47/random_budget_detailed.jsonl`
- `results_500_memory_seed48/random_budget_summary.json`
- `results_500_memory_seed48/random_budget_detailed.jsonl`
- `results_500_memory_seed49/random_budget_summary.json`
- `results_500_memory_seed49/random_budget_detailed.jsonl`

Do not use deprecated random-gated table artifacts, Monte Carlo random-gated
values, or any other unexecuted numbers as experimental evidence.

`scripts/07_verify_experiment.py` enforces this by checking the active
`paper/main.tex` table inputs against a whitelist and failing if deprecated
tables are referenced, if an active table input is missing from disk, or if
`paper/table_inventory.json` lacks valid source-file provenance for an active
table. It also checks that the multiseed JSON reports cover seeds 42, 43, 44, 45, 46, 47, 48, and 49 with complete
500-query method rows, 4,000 paired-test rows per comparison, and 250/250
train-test splits for gate validation. The verifier also rejects active
paper/report references to legacy `results/full_report*`,
`results/baselines_summary*`, and `results/proposed*` artifacts. It also rejects
unsupported positive claims in active paper/report files, including downstream
Pass@1 improvement, superiority over Dense-Only or Random-Gated-Expansion,
human-validated query quality, and state-of-the-art claims.

The verifier also checks that the human-audit packet is present, sampled from
the current eval set, and still unlabeled. Separate human-label and Pass@1
verifiers reject missing or inconsistent result files before those values can
support paper claims.
