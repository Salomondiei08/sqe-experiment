# Pass@1 Result Schema

This is a schema note, not a result source. Do not report Pass@1 until real
downstream task rows exist and `scripts/17_verify_pass1_results.py` passes.

## Required Files

- `results_pass1/manifest.json`
- `results_pass1/*_detailed.jsonl`
- `results_pass1/pass1_summary.json`

## Required Detailed Row Fields

Each attempted task/method pair must have exactly one JSONL row:

```json
{
  "task_id": "repo_or_benchmark_task_id",
  "method": "Dense-Only",
  "success": false,
  "runtime_seconds": 0.0,
  "failure_reason": "required when success is false"
}
```

Allowed method names should match the retrieval paper where possible:

- `Dense-Only`
- `Always-Expand`
- `Random-Gated-Expansion`
- `Selective-QE`

The verifier requires these four methods by default and checks that they cover
the same task set. Additional methods may be included, but every method in
detailed rows must be present in `pass1_summary.json`.
The EvoAgentBench importer accepts only these four method names by default; use
`--allow_unlisted_method` only for exploratory non-paper methods.

## Summary Command

Before running agents, verify the prepared method-specific retrieval context
packets:

```bash
python scripts/25_verify_pass1_contexts.py --context_dir pass1_contexts
```

The current package includes verified Dense-Only, Always-Expand,
Random-Gated-Expansion, and Selective-QE context packets for 500 SWE-bench
Verified task descriptions. These context packets are prompt inputs only. They
are not Pass@1 evidence.
Verify any generated context packet with:

```bash
python scripts/25_verify_pass1_contexts.py --context_dir pass1_contexts
```

This verifier checks context schema and confirms that the packet is explicitly
marked as non-result data.

After real detailed task rows exist, either from a custom task runner or from
imported EvoAgentBench job outputs:

The concise execution handoff is
`pass1_evoagentbench_configs/EXECUTION_QUICKSTART.md`; the longer operational
runbook is `pass1_evoagentbench_configs/RUNBOOK.md`. Both are documentation
only and are not Pass@1 evidence.
After Docker access is fixed, the guarded runner can execute the four-method
smoke or full paired run:

```bash
scripts/42_run_pass1_after_preflight.sh smoke
scripts/42_run_pass1_after_preflight.sh full
```

It reruns preflight, refuses to continue unless `ready_to_run_pass1=true`, and
does not overwrite imported rows unless `PASS1_OVERWRITE=1` is explicitly set.
Smoke mode writes to `results_pass1_smoke/` and lowers the verifier threshold
explicitly for operational checking. Full mode writes to `results_pass1/`; the
default summary and verifier require at least 500 paired task IDs for paper
evidence.

```bash
python scripts/23_import_evoagentbench_pass1.py \
  --job_dir /path/to/evoagentbench/jobs/<job_name> \
  --method Selective-QE
```

Then recompute and verify the summary:

```bash
python scripts/21_summarize_pass1_results.py --results_dir results_pass1
python scripts/17_verify_pass1_results.py --results_dir results_pass1
```

The summary command recomputes `attempted`, `solved`, and `pass@1` from detailed
rows. By default it refuses to write `pass1_summary.json` unless Dense-Only,
Always-Expand, Random-Gated-Expansion, and Selective-QE rows are all present
over the same task set with at least 500 paired task IDs. It does not run
agents and does not create task outcomes.
The EvoAgentBench importer also does not run agents; it only converts existing
`result.json` files that already contain verifier rewards.
