# Claim Audit

This file records which claims the current paper package may make and which
claims are not supported by the executed evidence. It is a guard against
accidentally turning diagnostics, pilots, or future-work targets into paper
results.

## Supported Claims

| Claim | Evidence | Allowed wording |
|---|---|---|
| SQE was evaluated on corrected 500-query memory-target retrieval runs | `data_500_memory_seed42/`, `data_500_memory_seed43/`, `data_500_memory_seed44/`, `data_500_memory_seed45/`, `data_500_memory_seed46/`, `data_500_memory_seed47/`, `data_500_memory_seed48/`, `data_500_memory_seed49/`; verifier checks 500/500 targets in memory and index | "500 query-memory pairs" and "8 independently rebuilt memory-index seeds" |
| SQE has only a small retrieval-only Recall@5 improvement over Dense-Only | `results_multiseed/multiseed_paired_tests.json`: Recall@5 delta +0.875 points, CI [+0.10, +1.65], p=0.0154; `paper/tables/multiseed_summary.tex` | "small retrieval-only Recall@5 improvement" |
| SQE is not clearly better than Random-Gated-Expansion | `results_multiseed/multiseed_paired_tests.json`: Recall@5 delta +0.475 points, CI [-0.175, +1.15], p=0.085 | "not clearly better than the executed random-gating budget control" |
| SQE is higher than Hybrid-RRF on Recall@5 in the 8-seed aggregate | `results_multiseed/multiseed_paired_tests.json`: Recall@5 delta +5.85 points, CI [+4.75, +6.975], p=0.000 | "higher Recall@5 than Hybrid-RRF" |
| Random-Gated-Expansion is backed by executed JSONL evidence | `results_500_memory_seed42/random_budget_detailed.jsonl`, `results_500_memory_seed43/random_budget_detailed.jsonl`, `results_500_memory_seed44/random_budget_detailed.jsonl`, `results_500_memory_seed45/random_budget_detailed.jsonl`, `results_500_memory_seed46/random_budget_detailed.jsonl`, `results_500_memory_seed47/random_budget_detailed.jsonl`, `results_500_memory_seed48/random_budget_detailed.jsonl`, `results_500_memory_seed49/random_budget_detailed.jsonl`; `DATA_PROVENANCE.md` | "executed random-gating budget control" |
| Measured token costs exist for all expansion ablations | `results_tokenmeasured_500_seed42/*_tokenmeasured500_summary.json`; `paper/tables/measured_token_cost.tex` | "measured-token reruns are cost measurements" |
| Measured-token reruns support cost claims only | `results_tokenmeasured_500_seed42/*_tokenmeasured500_summary.json`; `paper/tables/measured_token_cost.tex`; `NO_HALLUCINATED_DATA.md` | "reported as cost measurements" |
| Active paper tables have declared source provenance | `paper/table_inventory.json` field `active_table_sources`; verifier fields `table_inventory_source_key_mismatch=[]`, `table_inventory_empty_source_tables=[]`, and `table_inventory_missing_source_paths=[]` | "active tables are backed by declared source files" |
| Generated hypothetical traces are retrieval probes, not factual logs | `results_500_memory_seed*/expansion_cache.json`; `NO_HALLUCINATED_DATA.md`; `DATA_PROVENANCE.md` | "retrieval probes rather than claims that those executions actually occurred" |
| The current gate is weakly calibrated | `paper/tables/gate_diagnostics.tex`, `paper/tables/multiseed_gate_validation.tex`, `paper/tables/gate_variant_diagnostics.tex`, `paper/tables/gate_headroom_diagnostics.tex` | "diagnostic" and "not enough evidence to remove the gate calibration limitation" |
| Cross-seed top-1 gate diagnostic remains weak | `results_gate_calibration/cross_seed_top1_gate.json`: Recall@5 delta +0.1 points, CI [-1.0, +1.1]; `paper/tables/cross_seed_top1_gate.tex` | "diagnostic" and "not support for a strong effectiveness claim" |

## Unsupported Claims

Do not claim any of the following until new executed evidence is added and the
corresponding verifier passes:

- SQE improves downstream software-agent Pass@1 or task success.
- SQE has a large or end-to-end improvement over Dense-Only.
- SQE is statistically or practically better than Random-Gated-Expansion.
- Human reviewers validated the generated retrieval queries.
- The random-gated baseline has any status beyond the executed JSONL rows listed
  in `DATA_PROVENANCE.md`.
- The cross-seed top-1 gate diagnostic establishes a clear improvement over
  Dense-Only.
- Measured-token reruns establish retrieval-effectiveness improvements.
- Contents of generated hypothetical traces are real historical actions or
  observed software executions.
- A table is paper evidence if it exists on disk but is not imported by
  `paper/main.tex` or lacks `paper/table_inventory.json` source provenance.
- Results from the legacy `results/` 100-query pilot are active paper evidence.

## Required Verification

Before submission or public release, run:

```bash
bash scripts/run_paper_pipeline.sh
/home/nlp-07/evermemos/EverOS/methods/evermemos/.venv/bin/python \
  scripts/17_verify_pass1_results.py --results_dir results_pass1
/home/nlp-07/evermemos/EverOS/methods/evermemos/.venv/bin/python \
  scripts/18_verify_human_audit_labels.py --audit_dir human_audit
```

The last two commands are expected to fail in the current package because real
Pass@1 results and human labels have not been collected.
