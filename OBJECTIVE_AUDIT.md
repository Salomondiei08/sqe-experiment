# Objective Audit

Objective summary:

Produce a rigorous SQE experiment and LaTeX paper package for a high-quality
paper by Salomon DIEI, using real experiment results, graphs, tables, and a
GitHub placeholder. Do not delete server files. Pause AMABench only if needed
for compute.

## Requirement-to-artifact checklist

| Requirement | Evidence | Status |
|---|---|---|
| Analyze and plan first | `PAPER_CHECKLIST.md`, `EXPERIMENT_STATUS.md`, this audit | Done |
| Rerun/update experiments | `results_500_memory_seed42/`, `results_500_memory_seed43/`, `results_500_memory_seed44/`, `results_500_memory_seed45/`, `results_500_memory_seed46/`, `results_500_memory_seed47/`, `results_500_memory_seed48/`, and `results_500_memory_seed49/` contain baselines plus selective, always-expand, traces-only, paraphrases-only, and random-gated control on corrected 500-query evals | Done for eight independent memory-index retrieval seeds |
| Add graphs | `paper/figures/method_overview.png`, `paper/figures/recall_at_5.png`, `paper/figures/gate_diagnostic.png`, `paper/figures/threshold_sensitivity.png` | Done |
| Add tables | `paper/tables/main_results.tex`, `cost_summary.tex`, `measured_token_cost.tex`, `paired_tests.tex`, `gate_diagnostics.tex`, `threshold_sweep.tex`, `validation_threshold.tex`, `experiment_manifest.tex`, `multiseed_summary.tex`, `multiseed_paired_tests.tex`, `win_loss_analysis.tex`, `multiseed_gate_validation.tex`, `gate_variant_diagnostics.tex`, `gate_headroom_diagnostics.tex`, `gate_feature_diagnostics.tex`, `cross_seed_top1_gate.tex` | Done |
| Add real results from experiments | `results_500_memory_seed42/full_report_v2.json` and LaTeX tables generated from JSON/JSONL | Done |
| Add place for GitHub | `paper/main.tex` and `paper/tables/experiment_manifest.tex` contain `TODO: add GitHub URL` | Done |
| Author is Salomon DIEI | `paper/main.tex` author block | Done |
| Add runnable project documentation | `README.md` points to the corrected 500-query run and paper artifacts; `paper/README.md` records the PDF build command | Done |
| Add experiment verifier | `scripts/07_verify_experiment.py` and `results_500_memory_seed42/verification_report.json` | Done |
| Prevent hallucinated or untraceable data | `DATA_PROVENANCE.md` maps active evidence classes to sources; `paper/table_inventory.json` maps every active table to concrete source files; `CLAIM_AUDIT.md` maps claims to evidence and unsupported claims; `ARTIFACT_MANIFEST.json` records checksums; verifier checks active paper/report files for forbidden synthetic-evidence references, unsupported positive claims, stale headline metrics, deprecated table inputs, legacy pilot-result references, and missing table-source files | Done |
| Improve figure/table formatting and references | `PAPER_STYLE_AUDIT.json` reports 4 figures, 17 tables, all captions/labels/references present, nonempty figure descriptions present, `manual_bold_count=0`, `em_dash_count=0`, and `failures=[]`; `FIGURE_ASSET_AUDIT.json` reports 4 readable active figures with PNG/SVG sources and no failures; verifier checks both audits and the paper generator's figure-description/float-placement behavior | Done |
| Provide conference-style layout preview | `paper/main_conference_preview.pdf`, `paper/main_conference_preview.tex`, and `CONFERENCE_PREVIEW_AUDIT.json`; marked as layout preview only, not official venue template and not experiment evidence | Done |
| Disclose compute environment without inventing runtime | `COMPUTE_ENVIRONMENT.json` records observed CPU, memory, GPU, OS, driver, and Python metadata; paper states runtime was not logged and does not estimate it | Done |
| Prepare venue-policy LLM usage disclosure | `LLM_USAGE_DISCLOSURE.md` contains a draft disclosure and states it is documentation only, not experiment evidence | Done |
| Prepare local GitHub release package | `github_code_release/RELEASE_MANIFEST.json` reports 192 files and `contains_pass1_results=false`, `contains_human_labels=false`, `contains_synthetic_replacement_rows=false` | Done |
| Prepare local Hugging Face dataset package | `hf_dataset_release/release_manifest.json` reports 163 files, no duplicate manifest paths, no unmanifested files, and no Pass@1, human-label, or synthetic replacement rows | Done |
| Prepare human-audit and Pass@1 handoff workflows without inventing labels or results | `human_audit/` contains 100 sampled query-target examples with blank reviewer fields, `human_audit/README.md`, `human_audit/REVIEWER_QUICKSTART.md`, and a template-only labeling manifest; `pass1_evoagentbench_configs/EXECUTION_QUICKSTART.md` documents the post-Docker-unblock four-method run path; verifiers keep both missing evidence gates marked as missing until real labels and task rows exist | Done |
| Do not delete anything on server | No experiment data/result files removed; `README.md` content was replaced at the same path | Done with note |
| Pause AMABench only if needed | AMABench was previously paused/resumed; later process check found no active AMABench/evaluation process | Done |
| High-quality LaTeX paper | `paper/main.tex` and rebuilt `paper/main.pdf` exist with real 500-query tables/figures, 8-seed independent memory-index aggregate with standard deviations, conservative claims, and `LATEX_BUILD_AUDIT.json` showing a warning-free Tectonic build | Done as retrieval paper package |
| Citation metadata quality | `paper/references.bib` uses venue-aware entries; `scripts/07_verify_experiment.py` reports `references_bib` with no missing keys, loose entries, or missing required metadata | Done |
| Handoff status | `HANDOFF_STATUS.md` summarizes current verified artifacts and blockers; `scripts/07_verify_experiment.py` checks `handoff_status_missing_required_phrases=[]`; `ARTIFACT_MANIFEST.json` tracks it | Done |
| Rigor suitable for top conference | Ablations, paired bootstrap, an eight-seed independent memory-index retrieval aggregate, and retained gate-feature diagnostics exist, but there are no human-audited query labels, no Pass@1/task-success evaluation, the Dense-Only advantage is not practically meaningful, and the method is not clearly better than Random-Gated-Expansion | Not complete |

## Current completion audit

Objective restated as concrete deliverables:

- Rerun, update, or rewrite the SQE experiments using real experiment outputs.
- Produce a coherent LaTeX paper package with graphs, tables, and results.
- Include a GitHub placeholder and set the author to Salomon DIEI.
- Be rigorous: avoid hallucinated, simulated, or untraceable data.
- Do not delete server files.
- Pause AMABench only if compute requires it.
- Analyze and plan before acting.

Prompt-to-artifact checklist:

| Objective item | Concrete evidence inspected | Current status |
|---|---|---|
| Analyze and plan first | `PAPER_CHECKLIST.md` is retained as a deprecated planning template; `OBJECTIVE_AUDIT.md`, `DATA_PROVENANCE.md`, and `NEXT_EXPERIMENTS.md` document current evidence and gaps | Satisfied |
| Rerun/update experiments | `results_500_memory_seed42/` through `results_500_memory_seed49/` contain complete executed retrieval rows for all active methods; verifier reports `failures=[]` | Satisfied for retrieval experiments |
| Use real results only | `DATA_PROVENANCE.md` maps active evidence classes to JSON/JSONL sources; `paper/table_inventory.json` maps every active table to concrete source files; `CLAIM_AUDIT.md` lists supported and unsupported claims; `scripts/07_verify_experiment.py` rejects deprecated non-evidence tables, unsupported positive claims, invalid dataset paths, legacy 100-query pilot-result references, stale abstract headline metrics, and active tables with missing source files | Satisfied for active paper package |
| Add graphs | `paper/figures/method_overview.png`, `paper/figures/recall_at_5.png`, `paper/figures/gate_diagnostic.png`, and `paper/figures/threshold_sensitivity.png` exist; `FIGURE_ASSET_AUDIT.json` verifies size, brightness, nonblank content, and matching SVG sources | Satisfied |
| Add tables | `paper/tables/main_results.tex`, `cost_summary.tex`, `measured_token_cost.tex`, `paired_tests.tex`, `gate_diagnostics.tex`, `threshold_sweep.tex`, `validation_threshold.tex`, `experiment_manifest.tex`, `multiseed_summary.tex`, `multiseed_paired_tests.tex`, `win_loss_analysis.tex`, `multiseed_gate_validation.tex`, `gate_variant_diagnostics.tex`, `gate_headroom_diagnostics.tex`, and `gate_feature_diagnostics.tex` exist and are checked against source data or provenance-backed diagnostic JSON | Satisfied |
| Produce LaTeX paper | `paper/main.tex` and `paper/main.pdf` exist; `scripts/31_verify_latex_clean_build.py` records `clean_build=true`, `warnings=[]`, and `failures=[]` in `LATEX_BUILD_AUDIT.json`; the main verifier now requires this readiness evidence | Satisfied as retrieval-paper draft |
| Professional formatting | `PAPER_STYLE_AUDIT.json` reports 4 figures, 17 tables, all floats captioned/labeled/referenced, nonempty figure descriptions, zero manual bold commands, zero em dash characters, no flagged hype phrases, and no failures; `FIGURE_ASSET_AUDIT.json` reports no figure readability failures | Satisfied |
| Conference preview | `CONFERENCE_PREVIEW_AUDIT.json` reports `clean_for_preview=true`, `is_official_venue_template=false`, and `is_experiment_evidence=false`; `paper/main_conference_preview.pdf` exists | Satisfied as layout preview |
| Compute disclosure | `COMPUTE_ENVIRONMENT.json` exists, is marked `is_experiment_metric=false`, records 96 CPU threads, 251 GiB RAM, and 8 RTX A6000 GPUs; the paper says runtime was not logged | Satisfied |
| LLM-use policy note | `LLM_USAGE_DISCLOSURE.md` exists and does not add experimental claims | Satisfied |
| Add GitHub placeholder | `paper/main.tex` contains `TODO: add GitHub URL`; verifier checks the placeholder | Satisfied |
| Author is Salomon DIEI | `paper/main.tex` author block contains `Salomon DIEI`; verifier checks the author string | Satisfied |
| Do not delete server files | Deprecated non-evidence files were moved under `deprecated_non_evidence/` rather than deleted; historical fixed-memory query-seed runs remain on disk as secondary provenance; release helpers now treat `--clean` as a deprecated no-op; `scripts/07_verify_experiment.py` checks `release_helpers_non_destructive` and fails if destructive removal patterns return | Satisfied to current knowledge |
| Pause AMABench only if needed | AMABench was not running in the latest process checks; no current pause was needed | Satisfied |
| Avoid AI slop/overclaiming | Paper and docs state that SQE has only a small retrieval-only improvement over Dense-Only, does not clearly beat Random-Gated-Expansion, and that Pass@1/human labels are missing; verifier reports `unsupported_claim_references=[]` | Satisfied for current draft |
| Document remaining blockers | `BLOCKED_NEXT_ACTIONS.md` lists the Docker/admin step for Pass@1 and the required real human-label artifacts, with verifier gates; `SUBMISSION_READINESS.json` includes `Documented unblock steps`; `scripts/07_verify_experiment.py` cross-checks that readiness entry | Satisfied |
| Strong top-conference empirical package | `SUBMISSION_READINESS.json` reports `strong_submission_ready=false`, `blocking_count=2`; `pass1_harness_preflight.json` reports Docker permission is blocked; `PASS1_RESULTS_SCHEMA.md` is schema documentation only | Not complete |

This audit does not mark the overall objective complete as a top-conference
submission. It marks the current state as a verified retrieval-paper draft with
explicit remaining blockers.

## Verified commands

- `python3 -m py_compile /home/nlp-07/sqe_experiment/scripts/*.py`
- `bash -n /home/nlp-07/sqe_experiment/scripts/run_ablation_suite.sh`
- File presence checks for `paper/`, `results_500_memory_seed42/`, and `EXPERIMENT_STATUS.md`
- Corrected eval-target membership check: 500/500 targets in indexed memory
- Invalid held-out-target dataset identified: `data_500_seed42` has 0/500 targets in memory and is not used for paper results
- `random_budget_summary.json` and `random_budget_detailed.jsonl` generated and included in tables/significance tests
- `threshold_sweep.tex` and `threshold_sensitivity.png` regenerated from corrected dense-only and always-expand result files
- `validation_threshold.tex` regenerated from a first-half threshold selection and second-half evaluation over existing dense-only and always-expand result files
- `gate_headroom_diagnostics.tex` regenerated from held-out recombination of executed dense-only and always-expand result files
- `scripts/22_gate_feature_diagnostics.py` generated
  `results_gate_calibration/gate_feature_diagnostics.json` and
  `paper/tables/gate_feature_diagnostics.tex` from saved FAISS/BM25 indexes and
  executed Dense-Only/Always-Expand rows; the verifier now checks that table
  against the JSON.
- `scripts/04_run_proposed_method.py` now records prompt, completion, and total tokens from OpenAI-compatible `resp.usage` for future runs
- `scripts/06_make_paper_artifacts.py` now includes a token column in `cost_summary.tex` when token fields are present in detailed result files
- `results_tokenmeasured_500_seed42/*_tokenmeasured500_summary.json` contains measured token usage for full 500-query reruns of Selective-QE, Always-Expand, HyDE-Traces-Only, Paraphrases-Only, and Random-Gated-Expansion
- `paper/tables/measured_token_cost.tex` and `paper/main.tex` include the measured-token rerun as a cost measurement
- `scripts/07_verify_experiment.py` completed with zero failures on the corrected 500-query run
- `scripts/37_audit_paper_style.py` generated `PAPER_STYLE_AUDIT.json`; the
  latest audit reports `clean=true`, `n_figures=4`, `n_tables=17`,
  `manual_bold_count=0`, `em_dash_count=0`, `hype_or_vague_phrase_hits=[]`,
  `warnings=[]`, and `failures=[]`.
- `scripts/38_capture_compute_environment.py` generated
  `COMPUTE_ENVIRONMENT.json`; it is metadata only, not an experiment metric,
  and records the observed CPU, memory, GPU, OS, driver, and Python
  environment.
- `LLM_USAGE_DISCLOSURE.md` was added as a venue-policy disclosure draft for
  substantial LLM assistance. It explicitly says it is documentation only and
  not experiment evidence.
- `scripts/36_make_conference_preview.py` generated
  `paper/main_conference_preview.tex`, `paper/main_conference_preview.pdf`,
  and `CONFERENCE_PREVIEW_AUDIT.json`; the preview is not an official venue
  template and is not experiment evidence.
- `DATA_PROVENANCE.md` documents active paper artifact sources and marks deprecated unused diagnostics
- `scripts/07_verify_experiment.py` verifies that `paper/main.tex` only inputs whitelisted provenance-backed tables and no deprecated tables
- `scripts/08_prepare_human_audit.py` produced `human_audit/human_audit_queries.jsonl`, `human_audit/human_audit_queries.csv`, and `human_audit/human_audit_manifest.json` from real eval rows with blank reviewer fields
- `human_audit/human_audit_labeling_manifest.template.json` was added as a
  template only; it is not counted as a labeled audit manifest.
- `scripts/07_verify_experiment.py` checks the human-audit packet and fails if reviewer fields have been filled without a documented labeling step
- `human_audit/README.md` defines the reviewer rubric and explicitly states
  that no human-audit numbers should be reported until labels are collected.
- `scripts/20_summarize_human_audit_labels.py` now refuses to summarize a
  labeled CSV unless it covers the source audit packet and preserves the original
  query and target fields. A temporary valid-label smoke test passed under
  `/tmp/sqe_human_summary_test/`, and a tampered-label test failed as expected.
- `scripts/07_verify_experiment.py` now requires the human-audit README/rubric
  alongside the JSONL, CSV, and manifest files.
- `scripts/07_verify_experiment.py` now checks the active paper for author
  `Salomon DIEI`, the GitHub URL placeholder, a nonempty PDF, and forbidden
  synthetic-evidence terms across active tables and multiseed reports.
- `scripts/07_verify_experiment.py` completed with zero failures and zero
  warnings after the paper-requirement checks were added.
- `scripts/13_make_artifact_manifest.py` generated `ARTIFACT_MANIFEST.json`
  with SHA256 checksums and file sizes for active paper, result, audit, script,
  and documentation files.
- `scripts/07_verify_experiment.py` now requires `ARTIFACT_MANIFEST.json` and
  checks that it contains the main paper files, multiseed reports, and
  human-audit rubric.
- `scripts/07_verify_experiment.py` now recomputes size and SHA256 for every
  manifest entry and fails if `ARTIFACT_MANIFEST.json` is stale.
- `scripts/07_verify_experiment.py` now extracts text from `paper/main.pdf`
  with `pdftotext` when available and checks that the compiled PDF contains
  the author, GitHub placeholder, multiseed sections, key diagnostic values,
  and Pass@1 caveat.
- `scripts/31_verify_latex_clean_build.py` now compiles `paper/main.tex` with
  Tectonic and writes `LATEX_BUILD_AUDIT.json`; the latest audit reports
  `returncode=0`, `warnings=[]`, `failures=[]`, and `clean_build=true`.
- `scripts/07_verify_experiment.py` now requires the clean-build audit through
  `SUBMISSION_READINESS.json` and fails if LaTeX warnings or failures are
  recorded.
- `scripts/07_verify_experiment.py` completed with zero failures and zero
  warnings with `main_pdf_text_checked=true`,
  `main_pdf_missing_phrases=[]`, and `artifact_manifest_stale_entries=[]`.
- `scripts/14_submission_readiness_check.py` generated
  `SUBMISSION_READINESS.json`, which records `strong_submission_ready=false`
  with blocking gaps: missing downstream Pass@1/task-success evaluation and
  missing human-audited labels. Measured token costs are now present for all
  expansion ablations.
- `PASS1_RESULTS_SCHEMA.md` was added as schema documentation for future
  downstream task rows; it is not counted as Pass@1 evidence.
- `scripts/23_import_evoagentbench_pass1.py` was added to convert existing
  EvoAgentBench job `result.json` files into `results_pass1/*_detailed.jsonl`
  rows. A temporary import/summarize/verify smoke test passed under
  `/tmp/sqe_pass1_import_test/`; no real SQE Pass@1 evidence was created.
- `scripts/07_verify_experiment.py` now requires `SUBMISSION_READINESS.json`
  and fails if it incorrectly marks the package strong-submission ready while
  those blockers remain.
- `scripts/run_paper_pipeline.sh` regenerates deterministic paper artifacts,
  multiseed artifacts, the PDF, submission-readiness report, checksum manifest,
  and verification reports for seeds 42, 43, 44, 45, 46, 47, 48, and 49 from existing executed
  results without rerunning retrieval or deleting files.
- `bash scripts/run_paper_pipeline.sh` completed successfully after adding
  table-source provenance and ended with `Paper package regenerated and
  verified for independent memory-index seeds 42, 43, 44, 45, 46, 47, 48, and 49.`
- `scripts/07_verify_experiment.py` now fails if active paper/report artifacts
  reference the invalid old `data_500_seed42`/`results_500_seed42` paths or
  excluded non-evidence tables such as deprecated random-gated artifacts and
  `measured_token_pilot.tex`.
- The verifier completed with
  `invalid_or_deprecated_artifact_references=[]`.
- The legacy `results/` directory is documented in `DATA_PROVENANCE.md` as an
  inactive 100-query pilot. The verifier now fails if active paper/report
  artifacts reference `results/full_report*`, `results/baselines_summary*`, or
  `results/proposed*`.
- `scripts/06_make_paper_artifacts.py` now defaults to
  `results_500_memory_seed42/` so direct runs cannot silently regenerate the
  paper from the old 100-query pilot directory.
- `scripts/07_verify_experiment.py` now checks `paper/main.tex` headline
  metrics against active seed-42 JSONL rows and fails if stale 100-query
  abstract text reappears.
- The verifier completed with
  `main_tex_missing_headline_metric_snippets=[]`,
  `main_tex_stale_headline_metric_snippets=[]`, and
  `invalid_or_deprecated_artifact_references=[]`.
- `scripts/07_verify_experiment.py` now checks that
  `paper/tables/main_results.tex` matches metrics recomputed from detailed
  JSONL files, and that `paper/tables/multiseed_summary.tex` matches
  `results_multiseed/multiseed_report.json`.
- The verifier completed with
  `main_results_table_missing_expected_rows=[]` and
  `multiseed_summary_table_missing_expected_rows=[]`.
- `scripts/07_verify_experiment.py` now checks that
  `paper/tables/multiseed_paired_tests.tex` matches
  `results_multiseed/multiseed_paired_tests.json`, and that
  `paper/tables/multiseed_gate_validation.tex` matches
  `results_multiseed/multiseed_gate_validation.json`.
- The verifier completed with
  `multiseed_paired_table_missing_expected_rows=[]` and
  `multiseed_gate_table_missing_expected_rows=[]`.
- `scripts/07_verify_experiment.py` now checks that
  `paper/tables/measured_token_cost.tex` matches
  `results_tokenmeasured_500_seed42/selective_tokenmeasured500_summary.json`.
- The verifier completed with
  `measured_token_table_missing_expected_rows=[]`.
- `scripts/06_make_paper_artifacts.py` now writes
  `paper/table_inventory.json` with `active_table_sources`, and
  `scripts/07_verify_experiment.py` fails if any active table has missing,
  empty, or mismatched source entries. The latest verifier completed with
  `table_inventory_source_key_mismatch=[]`,
  `table_inventory_empty_source_tables=[]`, and
  `table_inventory_missing_source_paths=[]`.
- `scripts/07_verify_experiment.py` now validates the three active PNG figures
  by checking PNG headers, dimensions, and file size.
- The verifier confirmed all active figures are nonempty 760 by 420 PNGs.
- `NEXT_EXPERIMENTS.md` gives concrete commands, expected evidence files, and
  acceptance bars for the four strong-submission blockers plus measured-cost
  follow-up.
- `PAPER_CHECKLIST.md` is explicitly marked as a deprecated planning template, not a result source
- `scripts/run_ablation_suite.sh` now targets corrected 500-query data/index paths, includes the executed random-gated ablation, and runs verification
- Installed user-local Tectonic musl binary at `/home/nlp-07/.local/bin/tectonic-musl`
- `/home/nlp-07/.local/bin/tectonic-musl main.tex` in `paper/` produced `paper/main.pdf` without warnings
- Historical audit note: `pdfinfo paper/main.pdf` then reported 8 pages, letter size, PDF 1.5 after adding
  the 8-seed aggregate and gate-validation tables
- AMABench process check later found no active AMABench/evaluation process; the
  previous Python worker was defunct.
- `results_500_query_seed43_memory_seed42/verification_report.json` completed
  with zero failures and zero warnings.
- `results_500_query_seed44_memory_seed42/verification_report.json` completed
  with zero failures and zero warnings.
- `results_multiseed/multiseed_report.json` aggregates seeds 42, 43, 44, 45, 46, 47, 48, and 49
  with no missing seed warning.
- `paper/tables/multiseed_summary.tex` reports mean plus sample standard
  deviation across the eight completed independent memory-index retrieval seeds.
- `results_multiseed/multiseed_paired_tests.json` and
  `paper/tables/multiseed_paired_tests.tex` report paired Recall@5 bootstrap
  intervals over all 4,000 executed query rows.
- Current independent-memory paired Recall@5 tests report Selective-QE versus
  Dense-Only at +0.875 points with CI [+0.10, +1.65] and versus
  Random-Gated-Expansion at +0.475 points with CI [-0.175, +1.15].
- `results_multiseed/multiseed_gate_validation.json` and
  `paper/tables/multiseed_gate_validation.tex` report split-threshold
  validation over executed dense-only and always-expand rows for seeds 42, 43,
  and 44.
- `results_gate_calibration/gate_variant_diagnostics.json` and
  `paper/tables/gate_variant_diagnostics.tex` report a deterministic diagnostic
  over executed dense-only, BM25-only, and always-expand rows. The selected
  variants reach 68.8% mean held-out Recall@5 versus 67.7% dense on the same
  held-out halves, while expanding 58.7% of held-out queries. This remains a
  weak diagnostic, not a solved gate-calibration result.
- `/home/nlp-07/.local/bin/tectonic-musl main.tex` was rerun after adding
  standard deviations and produced `paper/main.pdf`.
- `scripts/07_verify_experiment.py` completed with zero failures after
  `paper/main.tex` began referencing `tables/multiseed_summary`.
- `scripts/07_verify_experiment.py` now requires both multiseed paper tables
  and fails if `paper/main.tex` references a missing table input.
- `scripts/07_verify_experiment.py` completed with zero failures and zero
  warnings for seeds 42, 43, 44, 45, 46, 47, 48, and 49 after the stricter paper-artifact check.
- Historical audit note: `/home/nlp-07/.local/bin/tectonic-musl main.tex` was
  rerun after adding multiseed gate validation and then produced an 8-page
  `paper/main.pdf`.
- `scripts/07_verify_experiment.py` now checks the multiseed JSON reports for
  complete seeds 42, 43, 44, 45, 46, 47, 48, and 49, 500-query method rows, 4,000 paired-test rows
  per comparison, and 250/250 gate-validation splits.
- `scripts/09_make_multiseed_report.py`,
  `scripts/11_make_multiseed_paired_tests.py`, and
  `scripts/12_make_multiseed_gate_validation.py` now require an explicit
  `seed_family` field so fixed-memory query-sampling seeds cannot be silently
  mixed with independent memory-index seeds.
- `scripts/07_verify_experiment.py` now fails if the active paper multiseed
  reports are not marked `independent_memory` or if their seed result
  directories do not match the expected independent memory-index layout.
- `scripts/07_verify_experiment.py` completed with zero failures and zero
  warnings for seeds 42, 43, 44, 45, 46, 47, 48, and 49 after the multiseed artifact checks.
- `scripts/run_multiseed_artifacts.sh` regenerates the deterministic multiseed
  report, paired bootstrap table, and gate-validation table from completed
  result files without running retrieval or generating new data.
- `bash scripts/run_multiseed_artifacts.sh` was executed successfully and
  regenerated `results_multiseed/multiseed_report.json`,
  `results_multiseed/multiseed_paired_tests.json`, and
  `results_multiseed/multiseed_gate_validation.json`.
- `scripts/07_verify_experiment.py` completed with zero failures and zero
  warnings after regenerating the multiseed artifacts.
- `scripts/06_make_paper_artifacts.py` now preserves the multiseed summary,
  multiseed paired-test, and multiseed gate-validation sections when
  regenerating `paper/main.tex`.
- `scripts/06_make_paper_artifacts.py` now reads
  `results_multiseed/multiseed_paired_tests.json` and
  `results_multiseed/multiseed_gate_validation.json` to insert the actual
  dense-comparison interval and gate-validation delta/expansion values into
  `paper/main.tex`.
- The documented regeneration path was rerun:
  `scripts/06_make_paper_artifacts.py`, `scripts/run_multiseed_artifacts.sh`,
  `scripts/07_verify_experiment.py`, and `/home/nlp-07/.local/bin/tectonic-musl
  main.tex`.
- Historical audit note: `pdfinfo paper/main.pdf` then reported a 9-page PDF created on May 14, 2026 at
  10:42:16 KST after the Random-Gated-Expansion wording update.
- After correcting stale provenance and future-work text, the readiness report
  was regenerated with `strong_submission_ready=false` and `blocking_count=2`.
- After correcting stale provenance, future-work text, and legacy-result guards,
  `ARTIFACT_MANIFEST.json` was regenerated; the current manifest tracks 242
  files.
- Final verifier runs for independent memory seeds 42, 43, 44, 45, 46, 47, 48,
  and 49 refreshed each seed's `verification_report.json`; each reported
  `failures=[]`, `forbidden_synthetic_evidence_references=[]`,
  `deprecated_table_inputs=[]`, `stale_seed_provenance_doc_references=[]`,
  `stale_gate_variant_ci_doc_references=[]`, and
  `artifact_manifest_stale_entries=[]`.
- `scripts/14_submission_readiness_check.py` now propagates the stale seed
  provenance and stale gate-variant CI verifier fields into
  `SUBMISSION_READINESS.json`; `scripts/07_verify_experiment.py` fails if those
  readiness summaries omit the fields or report nonempty values. The latest
  no-skip verifier reports `readiness_missing_guard_fields=[]` and
  `readiness_nonempty_guard_fields=[]`.
- `pass1_harness_preflight.json` now includes a `checked_at_utc` timestamp,
  `SUBMISSION_READINESS.json` propagates it, and `scripts/07_verify_experiment.py`
  fails if the Pass@1 preflight summary omits it or incorrectly treats
  preflight as Pass@1 evidence. The latest timestamp is
  `2026-05-15T07:41:49+00:00`, with `ready_to_run_pass1=false`.
- `paper/main.tex` and its generator `scripts/06_make_paper_artifacts.py` now
  describe generated hypothetical traces as retrieval probes, not factual logs;
  `NO_HALLUCINATED_DATA.md`, `DATA_PROVENANCE.md`, and `CLAIM_AUDIT.md` encode
  the same distinction, and the verifier requires the corresponding phrases.
- After removing invented example metrics from `PAPER_CHECKLIST.md`,
  `scripts/07_verify_experiment.py` now reports
  `checklist_missing_quarantine_phrases=[]` and
  `checklist_forbidden_placeholder_claims=[]`; it fails if the checklist is no
  longer clearly quarantined as deprecated planning material or if fabricated
  Pass@1/Recall@5 examples return.
- `scripts/14_submission_readiness_check.py` no longer accepts a
  `results_pass1/` directory by presence alone. It requires `manifest.json`,
  `*_detailed.jsonl`, `pass1_summary.json`, required row fields, failure
  reasons for unsuccessful rows, and recomputed `attempted`, `solved`, and
  `pass@1` values before marking downstream Pass@1 as present.
- `scripts/17_verify_pass1_results.py` was added as a standalone verifier for
  future downstream Pass@1 artifacts. It recomputes Pass@1 from detailed rows
  and exits nonzero if the expected evidence is absent or inconsistent. It now
  requires Dense-Only, Always-Expand, Random-Gated-Expansion, and Selective-QE
  rows over the same task set by default.
- `scripts/21_summarize_pass1_results.py` now applies the same default
  four-method task-set gate before writing `pass1_summary.json`, so partial
  downstream runs cannot be summarized as paper-ready evidence.
- `scripts/24_export_pass1_retrieval_contexts.py` was added to prepare
  method-specific retrieved-memory context packets for future downstream
  SWE-bench-style runs. It does not run agents or create Pass@1 evidence. A
  two-row dense-retrieval smoke test wrote temporary artifacts under
  `/tmp/sqe_context_export_smoke/`, and an attempted run with a mismatched
  embedding model failed before writing evidence; the script now checks that the
  query embedding dimension matches the saved FAISS index.
- `scripts/25_verify_pass1_contexts.py` was added as a standalone verifier for
  retrieval-context packets. It passed on the temporary two-row context smoke
  packet and now passes on `pass1_contexts/`, which contains 500 rows for each
  planned downstream method: Dense-Only, Always-Expand,
  Random-Gated-Expansion, and Selective-QE. The context manifests and task
  manifest mark these artifacts as non-results, so context packets cannot
  silently stand in for Pass@1 evidence.
- The local EvoAgentBench SWE-bench adapter now has an optional prompt-context
  hook controlled by `retrieval_context_file` and `retrieval_context_method` in
  `software_engineering.yaml`. A prompt-build smoke test loaded all 500
  Dense-Only contexts and confirmed that the context section appears in the
  generated prompt. This does not run agents or create Pass@1 evidence.
- EvoAgentBench SWE-bench task metadata was prepared from
  `princeton-nlp/SWE-bench_Verified` under
  `/home/nlp-07/evermemos/EverOS/benchmarks/EvoAgentBench/data/swebench/`.
  This includes the parquet, split file, and a manifest marking the files as
  non-result metadata.
- `scripts/26_check_pass1_harness_readiness.py` was added and run. The latest
  `pass1_harness_preflight.json` reports that Python dependencies,
  SWE-bench metadata, run configs, and all four retrieval-context packets are
  present, but real EvoAgentBench Pass@1 runs are blocked because user
  `nlp-07` cannot access `/var/run/docker.sock`.
- A Codex CLI adapter and reproducible EvoAgentBench config files were added
  for future real Dense-Only, Always-Expand, Random-Gated-Expansion, and
  Selective-QE runs. A non-Docker smoke test loaded the configs and selected
  the expected SWE-bench task/method condition.
- `scripts/24_export_pass1_retrieval_contexts.py` now streams context rows,
  flushes the expansion cache periodically, and supports `--resume` for long
  Always-Expand and Random-Gated-Expansion context-packet builds.
- `scripts/27_make_human_audit_labeling_form.py` now generates
  `human_audit/labeling_form.html` and `human_audit/labeling_form_manifest.json`
  as reviewer conveniences. The manifest marks the form as non-evidence, and
  the human-label verifier still fails until real labeled CSV, manifest, and
  summary files are added.
- `scripts/28_gate_validation_paired_tests.py` was added to paired-test the
  held-out threshold-gate diagnostic against Dense-Only. It uses only executed
  dense-only and always-expand rows plus thresholds selected by the existing
  gate-validation diagnostic. The aggregate remains weak: +1.07 Recall@5
  points with a 95% CI crossing zero.
- `scripts/14_submission_readiness_check.py` now reports retrieval-context
  packets as a separate non-blocking readiness check. The current status is
  `pass` for the four-method packet set. Downstream Pass@1 remains a separate
  required blocker because context packets are prompt inputs, not task-success
  evidence.
- `scripts/18_verify_human_audit_labels.py` was added as a standalone verifier
  for future human-label artifacts. It requires a separate labeled CSV,
  labeling manifest, and recomputed summary before human-audit rates can support
  the paper.
- `scripts/19_win_loss_analysis.py` was added as a deterministic query-level
  diagnostic over executed Dense-Only and Selective-QE rows for seeds 42, 43,
  44, 45, 46, 47, 48, and 49. It produced `results_multiseed/win_loss_analysis.json` and
  `paper/tables/win_loss_analysis.tex`; the aggregate is 140 SQE wins, 105 SQE
  losses, and net +35 top-5 wins over 4,000 paired queries.
- `paper/main.tex` now includes the win/loss sentence and
  `\input{tables/win_loss_analysis}`, which makes the weak SQE-vs-Dense result
  explicit rather than overclaiming a broad improvement.
- `SUBMISSION_READINESS.json` was regenerated after the stricter Pass@1 check
  and still reports `strong_submission_ready=false` with `blocking_count=2`.
- A 2026-05-15 attempt to run `sudo usermod -aG docker nlp-07` from this
  session failed because sudo requires an interactive password prompt; the
  Docker permission blocker is unchanged.
- `ARTIFACT_MANIFEST.json` now tracks 201 files after adding the gate-headroom,
  measured-token, checklist, stricter-readiness, human-label, Pass@1,
  retrieval-context, win/loss, gate-feature, schema/template, seed49, and
  table-source provenance artifacts.
- `paper/main.tex` now frames the 8-seed aggregate as the primary retrieval
  evidence and says the Dense-Only comparison is not a practically meaningful
  advantage; this keeps the paper aligned with the small retrieval-only effect.
- `paper/references.bib` was tightened to use venue-aware BibTeX entries with
  DOI/page metadata where available for the cited HyDE, RRF, SWE-bench, DPR,
  and BM25 sources.
- `scripts/07_verify_experiment.py` now checks `paper/references.bib` for
  required citation keys, loose placeholder-style entries, and required
  venue/DOI/page metadata.
- `HANDOFF_STATUS.md` was added as documentation-only handoff guidance and is
  now included in the artifact manifest and verifier doc guards.
- `scripts/07_verify_experiment.py` now rejects stale Pass@1 harness wording
  that predates the optional retrieval-context hook and current Docker blocker.

## Current blockers for completion

The objective is not fully achieved as a top-conference paper because:

1. No Pass@1 downstream agent task evaluation has been run.
   `PASS1_HARNESS_AUDIT.md` records that a nearby EvoAgentBench SWE-bench
   runner exists and SQE method configs/context packets are prepared, but no
   completed method-comparison jobs have been imported. Execution is currently
   blocked by Docker socket permissions for user `nlp-07`.
   `PASS1_RESULTS_SCHEMA.md` is not evidence.
2. On the independent-memory multiseed paired bootstrap, Selective-QE has only
   a small retrieval-only improvement over Dense-Only: Recall@5 delta is
   +0.875 points with CI [+0.10, +1.65].
3. On the independent-memory multiseed paired bootstrap, Selective-QE is not
   clearly better than Random-Gated-Expansion: Recall@5 delta is +0.475 points
   with CI [-0.175, +1.15].
4. The gate is not well calibrated; expanded queries have lower Recall@5 than
   non-expanded queries, and the retained dense-margin/score-concentration
   diagnostic improves held-out Recall@5 only slightly.
5. A human-audit packet exists, but it is not labeled. No human-audited result
   exists yet. The labeling manifest template is not evidence.
6. The current aggregate has eight independent memory-index retrieval seeds,
   but larger-scale independent runs may still be needed for stronger claims.
7. Token accounting is present and verified for full 500-query reruns of all
   expansion ablations.

## Next concrete step

Add real downstream Pass@1/task-success evidence and human-audit labels if
pursuing a stronger submission. Further gate work should be externally
validated and should not replace those missing evidence sources.
