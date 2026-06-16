# Pass@1 Harness Audit

This audit records whether the current workspace contains a real downstream
software-agent task-success harness that can be used to produce Pass@1 evidence
for the SQE paper.

## Search Performed

Searched for harness and task-success related files under:

- `/home/nlp-07/evermemos`
- `/home/nlp-07/sqe_experiment`

Search terms included:

- `*swe*bench*`
- `*pass*1*`
- `*agent*run*`
- `*harness*`
- `*evaluate*`
- `*eval*`
- `Pass@1`
- `SWE-bench`
- `swebench`
- `task-success`
- `agent run`

Additional current-state search:

- `find /home/nlp-07/evermemos/EverOS/benchmarks/EvoAgentBench -maxdepth 5 -iname 'result.json'`
- `find /home/nlp-07/sqe_experiment -maxdepth 4 \( -path '*/results_pass1*' -o -iname '*pass1*' -o -iname '*evoagent*' \)`
- `find /home/nlp-07/evermemos/EverOS/benchmarks/EvoAgentBench -maxdepth 8 -iname 'result.json'`
- `find /home/nlp-07 -maxdepth 5 -path '*results_pass1*'`
- Direct inspection of `EvoAgentBench/src/domains/software_engineering/swebench.py`
  and `EvoAgentBench/src/domains/software_engineering/prompt.md`.

## Relevant Files Found

| File | Finding |
|---|---|
| `scripts/17_verify_pass1_results.py` | Verifies future Pass@1 artifacts, but does not run agent tasks. |
| `scripts/23_import_evoagentbench_pass1.py` | Converts existing EvoAgentBench job `result.json` files into the strict `results_pass1/*_detailed.jsonl` schema; it does not run agents or create task outcomes. |
| `scripts/24_export_pass1_retrieval_contexts.py` | Exports method-specific retrieved-memory context packets for downstream task prompts. It does not run agents, verify patches, or create Pass@1 evidence. |
| `scripts/25_verify_pass1_contexts.py` | Verifies future retrieval-context packets and fails if they are missing, malformed, or marked as result evidence. |
| `EverOS/methods/HyperMem/scripts/run_eval.sh` | Runs a HyperMem memory-evaluation pipeline via `hypermem/main/eval.py`; not an SQE SWE-bench task-success harness. |
| `scripts/03_run_longmemeval.sh` | Runs LongMemEval-S through EverMemOS evaluation; this is memory QA evaluation, not downstream software-agent Pass@1. |
| `scripts/05_evaluate_and_report.py` | Evaluates retrieval rows for Recall@K/MRR; not task success. |
| `EverOS/benchmarks/EvoAgentBench/src/run.py` | Real multi-domain agent evaluation entry point. |
| `EverOS/benchmarks/EvoAgentBench/src/domains/software_engineering/swebench.py` | Docker-based SWE-bench adapter that verifies generated patches with the SWE-bench harness. This is a plausible downstream task-success runner; SQE method configs now exist, but completed task-success job outputs are still missing. |
| `EverOS/benchmarks/EvoAgentBench/src/domains/software_engineering/prompt.md` | The local prompt template now supports an optional retrieved-memory context section when `retrieval_context_file` is configured. This enables method-specific prompt construction, but it is not task-success evidence. |

No completed EvoAgentBench `result.json` job outputs were found under the local
EvoAgentBench tree during searches to depth 8. No `results_pass1/` directory was
found under `/home/nlp-07` to depth 5. Therefore
`scripts/23_import_evoagentbench_pass1.py` has no real job directory to import
at this time.

No runnable SWE-bench-style software-agent harness was found inside the SQE
experiment directory itself. A real SWE-bench-capable harness exists nearby in
EvoAgentBench. The local integration now supports method-specific retrieval
context for Dense-Only, Always-Expand, Random-Gated-Expansion, and Selective-QE,
but no completed task-success jobs have been run.

The remaining evidence gap is not prompt construction. To produce
method-comparison Pass@1 evidence, the runner must execute the same SWE-bench
tasks under each retrieval method, verify generated patches, and record the
method name in the resulting job directory before importing completed
`result.json` files.

An optional prompt-context hook has now been added to the local EvoAgentBench
SWE-bench adapter:

```text
/home/nlp-07/evermemos/EverOS/benchmarks/EvoAgentBench/src/domains/software_engineering/swebench.py
/home/nlp-07/evermemos/EverOS/benchmarks/EvoAgentBench/src/domains/software_engineering/prompt.md
/home/nlp-07/evermemos/EverOS/benchmarks/EvoAgentBench/src/domains/software_engineering/software_engineering.yaml
```

When `retrieval_context_file` is configured, `SWEBenchAdapter.build_prompt()`
loads the matching JSONL row by task ID and inserts its `context_text` under an
`Optional Retrieved Memory Context` prompt section. If the config key is absent,
the SWE-bench prompt is unchanged. This is still only a harness integration; no
agent task has been run and no patch has been verified.

The integration smoke test used stubbed Docker/SWE-bench imports to avoid
running containers, loaded 500 Dense-Only contexts from
`pass1_contexts/dense_only_contexts.jsonl`, and confirmed that the generated
prompt contains both `Optional Retrieved Memory Context (Dense-Only)` and
`Retrieved Prior Agent Memories`.

The local EvoAgentBench SWE-bench task metadata was also prepared from
`princeton-nlp/SWE-bench_Verified`, test split:

```text
/home/nlp-07/evermemos/EverOS/benchmarks/EvoAgentBench/data/swebench/test-00000-of-00001.parquet
/home/nlp-07/evermemos/EverOS/benchmarks/EvoAgentBench/data/swebench/task_split.json
/home/nlp-07/evermemos/EverOS/benchmarks/EvoAgentBench/data/swebench/sqe_prepared_manifest.json
```

These files are task metadata only and are explicitly not Pass@1 evidence.

`scripts/26_check_pass1_harness_readiness.py` was added as a preflight checker
for the real EvoAgentBench execution environment. The latest report is:

```text
pass1_harness_preflight.json
```

It confirms that the Python dependencies `docker` and `swebench` are installed,
the SWE-bench parquet and split file exist, and all four retrieval-context
packets verify. The remaining blocker is OS-level Docker access:
`nlp-07` is not in the Docker socket group and `sudo -n docker ps` requires a
password. Therefore real SWE-bench Pass@1 runs cannot be executed from the
current session.

Additional Docker checks on 2026-05-15 confirmed this is an OS permission
blocker rather than an incomplete SQE setup: an escalated `docker ps` still
returned socket permission denied, `sudo -n docker ps` required a password,
`id` showed `nlp-07` belongs only to group `nlp-07`, and
`/var/run/docker.sock` is owned by `root:docker`. The fresh preflight also
records that the Docker socket group is `docker`, the current effective user
groups are `["nlp-07"]`, and `nlp-07` is not listed in the Docker group in
`/etc/group`, so `newgrp docker`/`sg docker` cannot unblock this session.

Because `nanobot` and `openclaw` CLIs were not installed on this host, a small
Codex CLI agent adapter was added to the local EvoAgentBench tree:

```text
/home/nlp-07/evermemos/EverOS/benchmarks/EvoAgentBench/src/agents/codex/codex.py
/home/nlp-07/evermemos/EverOS/benchmarks/EvoAgentBench/src/agents/codex/__init__.py
/home/nlp-07/evermemos/EverOS/benchmarks/EvoAgentBench/src/agents/codex/codex.yaml.example
```

The SQE package includes method-specific EvoAgentBench configs under:

```text
pass1_evoagentbench_configs/
```

A non-Docker smoke test loaded the Codex configs, imported the SWE-bench domain,
selected `astropy__astropy-12907`, and confirmed the expected
retrieval-context method for each checked condition. This is configuration
validation only, not a task run.

`scripts/24_export_pass1_retrieval_contexts.py` now provides the retrieval half
of that bridge. It reads task descriptions from JSONL/JSON/CSV/parquet, retrieves
real memory rows from the saved SQE index under a selected paper method, and
writes `*_contexts.jsonl` plus a manifest. These context packets are inputs to a
future task run only; they are not Pass@1 results.

The workspace now contains verified four-method context packets for SWE-bench
Verified task metadata:

```text
pass1_tasks/swebench_verified_tasks.jsonl
pass1_tasks/swebench_verified_tasks_manifest.json
pass1_contexts/always_expand_contexts.jsonl
pass1_contexts/always_expand_manifest.json
pass1_contexts/dense_only_contexts.jsonl
pass1_contexts/dense_only_manifest.json
pass1_contexts/random_gated_expansion_contexts.jsonl
pass1_contexts/random_gated_expansion_manifest.json
pass1_contexts/selective_qe_contexts.jsonl
pass1_contexts/selective_qe_manifest.json
pass1_contexts/selective_expansion_cache.json
pass1_contexts/verification_report.json
```

The task metadata was derived from `princeton-nlp/SWE-bench_Verified`, test
split, and contains 500 task descriptions. The manifest explicitly marks it as
`is_pass1_result: false`.

The Dense-Only context export command was:

```bash
/home/nlp-07/evermemos/EverOS/methods/evermemos/.venv/bin/python \
  scripts/24_export_pass1_retrieval_contexts.py \
  --task_file pass1_tasks/swebench_verified_tasks.jsonl \
  --mode dense_only \
  --embedding_model BAAI/bge-m3 \
  --device cpu \
  --top_k 5 \
  --output_dir pass1_contexts
```

The Selective-QE context export command was:

```bash
/home/nlp-07/evermemos/EverOS/methods/evermemos/.venv/bin/python \
  scripts/24_export_pass1_retrieval_contexts.py \
  --task_file pass1_tasks/swebench_verified_tasks.jsonl \
  --mode selective \
  --embedding_model BAAI/bge-m3 \
  --device cpu \
  --top_k 5 \
  --confidence_threshold 0.65 \
  --n_hypothetical_traces 2 \
  --n_paraphrases 2 \
  --llm_base_url http://localhost:8000/v1 \
  --llm_api_key EMPTY \
  --llm_model Qwen3.6-35B-A3B \
  --expansion_cache pass1_contexts/selective_expansion_cache.json \
  --output_dir pass1_contexts
```

The verifier passed on all four packets with 500 rows per method and zero
failures:

```bash
/home/nlp-07/evermemos/EverOS/methods/evermemos/.venv/bin/python \
  scripts/25_verify_pass1_contexts.py \
  --context_dir pass1_contexts \
  --output pass1_contexts/verification_report.json
```

A smoke test was run with dense retrieval on two existing audit queries and
wrote temporary artifacts under `/tmp/sqe_context_export_smoke/`:

```bash
/home/nlp-07/evermemos/EverOS/methods/evermemos/.venv/bin/python \
  scripts/24_export_pass1_retrieval_contexts.py \
  --task_file human_audit/human_audit_queries.jsonl \
  --mode dense_only \
  --max_tasks 2 \
  --top_k 3 \
  --device cpu \
  --embedding_model BAAI/bge-m3 \
  --output_dir /tmp/sqe_context_export_smoke
```

The smoke test produced:

```text
n_tasks: 2
output: /tmp/sqe_context_export_smoke/dense_only_contexts.jsonl
manifest: /tmp/sqe_context_export_smoke/dense_only_manifest.json
```

The context verifier passed on that temporary packet:

```bash
/home/nlp-07/evermemos/EverOS/methods/evermemos/.venv/bin/python \
  scripts/25_verify_pass1_contexts.py \
  --context_dir /tmp/sqe_context_export_smoke
```

The default `pass1_contexts/` directory now verifies successfully for
Dense-Only, Always-Expand, Random-Gated-Expansion, and Selective-QE. This
changes only the prompt-input preparation state; it does not create or imply
task-success results.

An attempted smoke test with `Qwen/Qwen3-Embedding-4B` failed because the saved
FAISS index has dimension 1024 and must be queried with the original
`BAAI/bge-m3` embedding model. The exporter now checks this dimension match
explicitly before writing context artifacts.

## Current Conclusion

The current package cannot honestly report downstream Pass@1 or task-success
numbers. Adding such numbers requires real task runs that:

- executes software-engineering tasks with retrieval context injected per method,
- records one row per attempted task and method,
- records success/failure from an objective task checker,
- stores runtime and failure reasons,
- writes artifacts accepted by `scripts/17_verify_pass1_results.py`.

If EvoAgentBench is used for those runs, import completed job directories with:

```bash
python scripts/23_import_evoagentbench_pass1.py \
  --job_dir /path/to/evoagentbench/jobs/<job_name> \
  --method Selective-QE
```

After real detailed task rows exist, generate `pass1_summary.json` with:

```bash
python scripts/21_summarize_pass1_results.py --results_dir results_pass1
python scripts/17_verify_pass1_results.py --results_dir results_pass1
```

Until those artifacts exist and pass verification, Pass@1 must remain a stated
missing blocker rather than a paper result.

See `PASS1_RESULTS_SCHEMA.md` for the exact row and summary schema expected by
the verifier.
