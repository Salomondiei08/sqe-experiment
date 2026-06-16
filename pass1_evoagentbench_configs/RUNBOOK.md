# EvoAgentBench Pass@1 Runbook

These configs prepare real downstream SWE-bench runs for the SQE paper. They do
not contain results and must not be cited as Pass@1 evidence.

## Preflight

```bash
cd /home/nlp-07/sqe_experiment
/home/nlp-07/evermemos/EverOS/methods/evermemos/.venv/bin/python \
  scripts/26_check_pass1_harness_readiness.py \
  --output pass1_harness_preflight.json
```

The current blocker is Docker daemon permission for user `nlp-07`.

Current observed state on 2026-05-15:

- `nlp-07` belongs only to group `nlp-07`.
- `/var/run/docker.sock` is owned by `root:docker`.
- `docker ps` fails with socket permission denied.
- `nerdctl` is installed, but `nerdctl ps` reports that rootless containerd is
  not running. It is also not a drop-in replacement for this SWE-bench harness,
  because the adapter calls the Docker SDK and Docker socket API directly.
- An escalated `docker ps` check still failed with the same socket permission
  error.
- `sudo -n docker ps` fails because a password is required.

An administrator can resolve this with:

```bash
sudo usermod -aG docker nlp-07
```

Then start a new login/session for the group change to apply and rerun the
preflight command above. Do not treat a fixed preflight as Pass@1 evidence; it
only means the real SWE-bench task runs can start.

## Guarded Runner

The preferred post-unblock path is:

```bash
cd /home/nlp-07/sqe_experiment
scripts/42_run_pass1_after_preflight.sh smoke
scripts/42_run_pass1_after_preflight.sh full
```

The helper reruns preflight, refuses to launch jobs unless
`ready_to_run_pass1=true`, runs the same task set under Dense-Only,
Always-Expand, Random-Gated-Expansion, and Selective-QE, imports all four
methods, summarizes, and verifies the result package. It refuses to overwrite
existing imported rows unless `PASS1_OVERWRITE=1` is explicitly set.

## Context Packets

The active retrieval paper uses four methods for downstream task-success
comparison: Dense-Only, Always-Expand, Random-Gated-Expansion, and Selective-QE.
All four context packets are already prepared and verified under
`/home/nlp-07/sqe_experiment/pass1_contexts/`. To regenerate them, use the same
task file, memory store, index, embedding model, and top-k:

```bash
cd /home/nlp-07/sqe_experiment
/home/nlp-07/evermemos/EverOS/methods/evermemos/.venv/bin/python \
  scripts/24_export_pass1_retrieval_contexts.py \
  --task_file pass1_tasks/swebench_verified_tasks.jsonl \
  --mode dense_only \
  --embedding_model BAAI/bge-m3 \
  --top_k 5 \
  --output_dir pass1_contexts

/home/nlp-07/evermemos/EverOS/methods/evermemos/.venv/bin/python \
  scripts/24_export_pass1_retrieval_contexts.py \
  --task_file pass1_tasks/swebench_verified_tasks.jsonl \
  --mode selective \
  --embedding_model BAAI/bge-m3 \
  --top_k 5 \
  --confidence_threshold 0.65 \
  --n_hypothetical_traces 2 \
  --n_paraphrases 2 \
  --llm_base_url http://localhost:8000/v1 \
  --llm_api_key EMPTY \
  --llm_model Qwen3.6-35B-A3B \
  --expansion_cache pass1_contexts/selective_expansion_cache.json \
  --cache_flush_every 1 \
  --resume \
  --output_dir pass1_contexts

/home/nlp-07/evermemos/EverOS/methods/evermemos/.venv/bin/python \
  scripts/24_export_pass1_retrieval_contexts.py \
  --task_file pass1_tasks/swebench_verified_tasks.jsonl \
  --mode always_expand \
  --embedding_model BAAI/bge-m3 \
  --top_k 5 \
  --expansion_cache pass1_contexts/pass1_expansion_cache.json \
  --cache_flush_every 1 \
  --resume \
  --output_dir pass1_contexts

/home/nlp-07/evermemos/EverOS/methods/evermemos/.venv/bin/python \
  scripts/24_export_pass1_retrieval_contexts.py \
  --task_file pass1_tasks/swebench_verified_tasks.jsonl \
  --mode random_budget \
  --random_expand_rate 0.48225 \
  --seed 42 \
  --embedding_model BAAI/bge-m3 \
  --top_k 5 \
  --expansion_cache pass1_contexts/pass1_expansion_cache.json \
  --cache_flush_every 1 \
  --resume \
  --output_dir pass1_contexts

/home/nlp-07/evermemos/EverOS/methods/evermemos/.venv/bin/python \
  scripts/25_verify_pass1_contexts.py --context_dir pass1_contexts
```

These commands prepare prompt inputs only. They do not run agents, verify
patches, or create Pass@1 evidence.

## Smoke Runs

Run one task per method after Docker access is available:

```bash
cd /home/nlp-07/evermemos/EverOS/benchmarks/EvoAgentBench
/home/nlp-07/evermemos/EverOS/methods/evermemos/.venv/bin/python \
  src/run.py \
  --config /home/nlp-07/sqe_experiment/pass1_evoagentbench_configs/config_dense_codex.yaml \
  --task astropy__astropy-12907 \
  --job sqe_dense_codex_smoke

/home/nlp-07/evermemos/EverOS/methods/evermemos/.venv/bin/python \
  src/run.py \
  --config /home/nlp-07/sqe_experiment/pass1_evoagentbench_configs/config_selective_codex.yaml \
  --task astropy__astropy-12907 \
  --job sqe_selective_codex_smoke

/home/nlp-07/evermemos/EverOS/methods/evermemos/.venv/bin/python \
  src/run.py \
  --config /home/nlp-07/sqe_experiment/pass1_evoagentbench_configs/config_always_expand_codex.yaml \
  --task astropy__astropy-12907 \
  --job sqe_always_expand_codex_smoke

/home/nlp-07/evermemos/EverOS/methods/evermemos/.venv/bin/python \
  src/run.py \
  --config /home/nlp-07/sqe_experiment/pass1_evoagentbench_configs/config_random_gated_codex.yaml \
  --task astropy__astropy-12907 \
  --job sqe_random_gated_codex_smoke
```

All active domain configs explicitly set `split: test`. Keep the same task ID
for all methods so the smoke comparison is paired.

## Full Paired Run

After all four smoke jobs finish and import cleanly, run the paired test split.
Start with `parallel 1` unless there is enough Docker capacity for more
concurrent SWE-bench containers.

```bash
cd /home/nlp-07/evermemos/EverOS/benchmarks/EvoAgentBench
/home/nlp-07/evermemos/EverOS/methods/evermemos/.venv/bin/python \
  src/run.py \
  --config /home/nlp-07/sqe_experiment/pass1_evoagentbench_configs/config_dense_codex.yaml \
  --split test \
  --parallel 1 \
  --job sqe_dense_codex_test

/home/nlp-07/evermemos/EverOS/methods/evermemos/.venv/bin/python \
  src/run.py \
  --config /home/nlp-07/sqe_experiment/pass1_evoagentbench_configs/config_selective_codex.yaml \
  --split test \
  --parallel 1 \
  --job sqe_selective_codex_test

/home/nlp-07/evermemos/EverOS/methods/evermemos/.venv/bin/python \
  src/run.py \
  --config /home/nlp-07/sqe_experiment/pass1_evoagentbench_configs/config_always_expand_codex.yaml \
  --split test \
  --parallel 1 \
  --job sqe_always_expand_codex_test

/home/nlp-07/evermemos/EverOS/methods/evermemos/.venv/bin/python \
  src/run.py \
  --config /home/nlp-07/sqe_experiment/pass1_evoagentbench_configs/config_random_gated_codex.yaml \
  --split test \
  --parallel 1 \
  --job sqe_random_gated_codex_test
```

Do not mix different task subsets between methods. If a smaller pilot is needed,
pass the same comma-separated `--task` list to all four method commands and use
distinct job names that record the subset.

## Import Completed Jobs

Only import after `result.json` files exist and the verifier has written
objective rewards.

```bash
cd /home/nlp-07/sqe_experiment
/home/nlp-07/evermemos/EverOS/methods/evermemos/.venv/bin/python \
  scripts/23_import_evoagentbench_pass1.py \
  --job_dir /home/nlp-07/evermemos/EverOS/benchmarks/EvoAgentBench/jobs/sqe_dense_codex_smoke \
  --method Dense-Only

/home/nlp-07/evermemos/EverOS/methods/evermemos/.venv/bin/python \
  scripts/23_import_evoagentbench_pass1.py \
  --job_dir /home/nlp-07/evermemos/EverOS/benchmarks/EvoAgentBench/jobs/sqe_selective_codex_smoke \
  --method Selective-QE

/home/nlp-07/evermemos/EverOS/methods/evermemos/.venv/bin/python \
  scripts/23_import_evoagentbench_pass1.py \
  --job_dir /home/nlp-07/evermemos/EverOS/benchmarks/EvoAgentBench/jobs/sqe_always_expand_codex_smoke \
  --method Always-Expand

/home/nlp-07/evermemos/EverOS/methods/evermemos/.venv/bin/python \
  scripts/23_import_evoagentbench_pass1.py \
  --job_dir /home/nlp-07/evermemos/EverOS/benchmarks/EvoAgentBench/jobs/sqe_random_gated_codex_smoke \
  --method Random-Gated-Expansion
```

For the full paired test jobs, use:

```bash
/home/nlp-07/evermemos/EverOS/methods/evermemos/.venv/bin/python \
  scripts/23_import_evoagentbench_pass1.py \
  --job_dir /home/nlp-07/evermemos/EverOS/benchmarks/EvoAgentBench/jobs/sqe_dense_codex_test \
  --method Dense-Only \
  --overwrite

/home/nlp-07/evermemos/EverOS/methods/evermemos/.venv/bin/python \
  scripts/23_import_evoagentbench_pass1.py \
  --job_dir /home/nlp-07/evermemos/EverOS/benchmarks/EvoAgentBench/jobs/sqe_selective_codex_test \
  --method Selective-QE \
  --overwrite

/home/nlp-07/evermemos/EverOS/methods/evermemos/.venv/bin/python \
  scripts/23_import_evoagentbench_pass1.py \
  --job_dir /home/nlp-07/evermemos/EverOS/benchmarks/EvoAgentBench/jobs/sqe_always_expand_codex_test \
  --method Always-Expand \
  --overwrite

/home/nlp-07/evermemos/EverOS/methods/evermemos/.venv/bin/python \
  scripts/23_import_evoagentbench_pass1.py \
  --job_dir /home/nlp-07/evermemos/EverOS/benchmarks/EvoAgentBench/jobs/sqe_random_gated_codex_test \
  --method Random-Gated-Expansion \
  --overwrite
```

Then summarize and verify:

```bash
/home/nlp-07/evermemos/EverOS/methods/evermemos/.venv/bin/python \
  scripts/21_summarize_pass1_results.py --results_dir results_pass1

/home/nlp-07/evermemos/EverOS/methods/evermemos/.venv/bin/python \
  scripts/17_verify_pass1_results.py --results_dir results_pass1
```

The paper may cite Pass@1 only after the verifier passes on completed paired
jobs. Context packets, configs, smoke tests, and preflight checks are not
Pass@1 evidence. The summary and verifier commands require Dense-Only,
Always-Expand, Random-Gated-Expansion, and Selective-QE rows over the same task
set by default, with at least 500 paired task IDs. Smoke output belongs in
`results_pass1_smoke/` and can only be verified with an explicit lower
`--min_task_count` for operational checks. The importer also accepts only those
four method names by default; `--allow_unlisted_method` is reserved for
exploratory non-paper runs.
