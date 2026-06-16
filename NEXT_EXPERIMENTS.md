# Next Experiments for a Strong Submission

The current package is a verified retrieval-paper draft. It is not yet a strong
top-conference empirical submission. `SUBMISSION_READINESS.json` lists the
blocking gaps. This file turns those gaps into concrete work items.

## 1. Downstream Pass@1 or Task-Success Evaluation

Goal: test whether retrieval gains improve software-agent task success.

Minimum design:

- Use the same agent scaffold and task set for all retrieval modes.
- Compare at least Dense-Only, Always-Expand, Random-Gated-Expansion, and
  Selective-QE.
- Keep model, budget, timeout, and tool permissions identical across modes.
- Report solved tasks / attempted tasks, Pass@1, cost, and timeout/error rates.

Expected evidence:

- `results_pass1/manifest.json`
- `results_pass1/*_detailed.jsonl`
- `results_pass1/pass1_summary.json`

If using EvoAgentBench as the SWE-bench runner, first run completed jobs for each
retrieval method with method-specific retrieval context injected. Then import each
completed job:

The method-specific retrieved-memory context packets are already prepared under
`pass1_contexts/`. Verify them before launching the agent run:

```bash
python scripts/25_verify_pass1_contexts.py --context_dir pass1_contexts
```

These context packets are prompt inputs only. They are not Pass@1 evidence and
must not be reported as task-success results.

To inject a verified packet into the local EvoAgentBench SWE-bench adapter, use
the method-specific domain configs under `pass1_evoagentbench_configs/`:

```yaml
retrieval_context_file: /home/nlp-07/sqe_experiment/pass1_contexts/dense_only_contexts.jsonl
retrieval_context_method: Dense-Only
```

Analogous configs are present for Always-Expand, Random-Gated-Expansion, and
Selective-QE.

Run separate jobs for each retrieval method and use distinct job names. Only
completed `result.json` files with objective verifier rewards can be imported as
Pass@1 evidence.

Before launching jobs, run the preflight:

```bash
python scripts/26_check_pass1_harness_readiness.py \
  --output pass1_harness_preflight.json
```

The current preflight blocker is Docker daemon permission for user `nlp-07`.
Python dependencies, SWE-bench task metadata, retrieval-context packets, and
four-method Codex configs are prepared under `pass1_evoagentbench_configs/`.

## Retrieval Evidence Gap

The held-out threshold-gate diagnostic was paired-tested against Dense-Only over
2,000 held-out query/seed pairs:

```bash
python scripts/28_gate_validation_paired_tests.py
```

Current result: +1.1 Recall@5 points, 95% CI [+0.1, +2.1], sign-flip
p=0.0366. This is a diagnostic over recombined executed retrieval rows, not
Pass@1 evidence and not direct evidence that SQE improves downstream agents.

```bash
python scripts/23_import_evoagentbench_pass1.py \
  --job_dir /path/to/evoagentbench/jobs/<job_name> \
  --method Selective-QE
```

Summary command:

```bash
python scripts/21_summarize_pass1_results.py --results_dir results_pass1
python scripts/17_verify_pass1_results.py --results_dir results_pass1
```

Acceptance bar:

- Every attempted task has a task ID, method, success flag, runtime, and failure
  reason if unsuccessful.
- Required detailed-row fields: `task_id`, `method`, `success`, and
  `runtime_seconds`; failed rows must include a non-empty `failure_reason`.
- `pass1_summary.json` must contain a `methods` object with `attempted`,
  `solved`, and `pass@1` values for each method.
- `scripts/21_summarize_pass1_results.py --results_dir results_pass1` refuses
  to write a summary by default unless Dense-Only, Always-Expand,
  Random-Gated-Expansion, and Selective-QE rows are all present over the same
  task set.
- The paper reports only completed runs, not partial task queues.
- `scripts/14_submission_readiness_check.py` recomputes the summary values from
  the detailed JSONL rows before accepting the Pass@1 evidence.
- `scripts/17_verify_pass1_results.py --results_dir results_pass1` must pass
  before any Pass@1 numbers are moved into the paper. By default it requires
  Dense-Only, Always-Expand, Random-Gated-Expansion, and Selective-QE rows over
  the same task set.

## 2. Human-Audited Query Quality Labels

Goal: establish whether generated queries and target memories are valid
retrieval examples.

Current unlabeled packet:

- `human_audit/human_audit_queries.csv`
- `human_audit/human_audit_queries.jsonl`
- `human_audit/README.md`

Labeling protocol:

- At least one reviewer labels all 100 rows.
- Prefer two reviewers plus adjudication for top-conference submission.
- Allowed labels are `yes`, `no`, and `uncertain`.
- Do not edit target excerpts or query text during labeling.

Expected evidence:

- `human_audit/labeled_human_audit_queries.csv`
- `human_audit/human_audit_labeling_manifest.json`
- `human_audit/human_audit_summary.json`

Summary command:

```bash
python scripts/20_summarize_human_audit_labels.py --audit_dir human_audit
```

Acceptance bar:

- Report query clarity rate.
- Report target-answerability rate.
- Report copied/specific-query rate.
- Exclude or separately analyze invalid rows before making retrieval claims.
- `scripts/18_verify_human_audit_labels.py --audit_dir human_audit` must pass
  before any human-audit rates are moved into the paper.

## 3. Stronger Gate Calibration

Goal: replace the weak top-1-score-only selector.

Candidate gate features:

- Dense top-1 score.
- Dense top-1/top-2 margin.
- Dense score entropy or concentration across top-k.
- Dense/BM25 agreement on top-k IDs.
- Whether BM25 retrieves the same top candidate as dense retrieval.

Completed diagnostic:

- `results_gate_calibration/gate_variant_diagnostics.json`
- `paper/tables/gate_variant_diagnostics.tex`
- `results_gate_calibration/gate_feature_diagnostics.json`
- `paper/tables/gate_feature_diagnostics.tex`
- `results_gate_calibration/cross_seed_top1_gate.json`
- `paper/tables/cross_seed_top1_gate.tex`

These diagnostics use executed dense-only, BM25-only, and always-expand rows
plus saved FAISS/BM25 indexes for the independent memory-index seeds. They do
not remove the gate-calibration blocker. The current gate-feature diagnostic
obtains mean held-out Recall@5 69.15 versus dense 68.15 at 29.85% expansion.
The leave-one-seed-out top-1 diagnostic obtains 69.35% Recall@5 versus 69.30%
for Dense-Only at 38.6% expansion, and its confidence interval crosses zero.

Protocol:

- Select gate settings on a validation split only.
- Evaluate on held-out queries and across seeds.
- Keep the expansion budget comparable to Selective-QE and Random-Gated-Expansion.

Expected evidence:

- `results_gate_calibration/learned_gate_validation.json`
- `results_gate_calibration/learned_gate_detailed.jsonl`
- `paper/tables/learned_gate_validation.tex`

These files remain future work for a learned or externally validated gate, not
the already completed deterministic diagnostics.

Acceptance bar:

- Improvement over dense has a confidence interval that does not cross zero, or
  the paper explicitly frames the gate as cost control rather than quality gain.

## 4. Measured Token Costs for All Expansion Ablations

Goal: avoid mixing measured Selective-QE cost with estimated costs for other
expansion methods.

Current status: done for the active paper package.

Verified methods:

- Always-Expand
- HyDE-Traces-Only
- Paraphrases-Only
- Random-Gated-Expansion
- Selective-QE

Evidence:

- `results_tokenmeasured_500_seed42/*_summary.json`
- `paper/tables/measured_token_cost.tex`
- `SUBMISSION_READINESS.json`, check
  `Measured token costs for all expansion ablations`

Acceptance bar:

- Every expansion method reports actual calls/query, prompt tokens/query,
  completion tokens/query, total tokens/query, and latency/query.

## Evidence Promotion Checklist

Before any new result is moved into `paper/main.tex`:

- Add the underlying JSON or JSONL files first.
- Generate tables from those files, not by editing LaTeX numbers manually.
- Ensure `paper/table_inventory.json` lists every active table and that
  `active_table_sources` points to existing source files.
- Regenerate the paper package with:

```bash
bash scripts/run_paper_pipeline.sh
```

- Run the dedicated verifier for the evidence type, for example
  `scripts/17_verify_pass1_results.py` or
  `scripts/18_verify_human_audit_labels.py`.
- Do not claim Pass@1, human-label rates, or stronger gate performance until
  the corresponding verifier passes and `SUBMISSION_READINESS.json` reflects
  the new evidence.

## Recommended Order

1. Human-audit labels, because they validate the benchmark itself.
2. Downstream Pass@1, because it is the strongest paper claim.
3. Gate calibration, because it determines whether SQE can make a stronger
   quality claim than cost control.
4. Additional independent memory-index seeds only if the paper needs narrower
   confidence intervals than the current verified seeds 42, 43, and 44 provide.
