# Pass@1 Execution Quickstart

This file is documentation only. It is not Pass@1 evidence and does not contain
task outcomes.

## Current Blocker

The current user cannot access the Docker daemon. An administrator must run:

```bash
sudo usermod -aG docker nlp-07
```

Then start a new login session for `nlp-07` and rerun the preflight:

```bash
cd /home/nlp-07/sqe_experiment
python3 scripts/26_check_pass1_harness_readiness.py \
  --sqe_root . \
  --output pass1_harness_preflight.json
```

Continue only if `ready_to_run_pass1` is `true`.

`nerdctl` is present on this machine, but it is not a valid substitute for the
current SWE-bench run path: rootless containerd is not running, and
EvoAgentBench's SWE-bench adapter uses Docker SDK/socket operations directly.

## Guarded Runner

After preflight is green, the SQE package provides a guarded four-method runner:

```bash
cd /home/nlp-07/sqe_experiment
scripts/42_run_pass1_after_preflight.sh smoke
scripts/42_run_pass1_after_preflight.sh full
```

The script reruns preflight before launching jobs, runs Dense-Only,
Always-Expand, Random-Gated-Expansion, and Selective-QE over the same task set,
imports all four methods, summarizes, and verifies. It does not overwrite
existing imported rows unless `PASS1_OVERWRITE=1` is explicitly set.
Smoke mode writes to `results_pass1_smoke/` and is not paper evidence. Full
mode writes to `results_pass1/` and must pass the default 500-task verifier
threshold before any Pass@1 number is citable.

## Smoke Test

Run the same task under all four paper methods:

```bash
cd /home/nlp-07/evermemos/EverOS/benchmarks/EvoAgentBench
PY=/home/nlp-07/evermemos/EverOS/methods/evermemos/.venv/bin/python
ROOT=/home/nlp-07/sqe_experiment/pass1_evoagentbench_configs

$PY src/run.py --config $ROOT/config_dense_codex.yaml \
  --task astropy__astropy-12907 --job sqe_dense_codex_smoke
$PY src/run.py --config $ROOT/config_always_expand_codex.yaml \
  --task astropy__astropy-12907 --job sqe_always_expand_codex_smoke
$PY src/run.py --config $ROOT/config_random_gated_codex.yaml \
  --task astropy__astropy-12907 --job sqe_random_gated_codex_smoke
$PY src/run.py --config $ROOT/config_selective_codex.yaml \
  --task astropy__astropy-12907 --job sqe_selective_codex_smoke
```

The smoke jobs are operational checks. Do not cite them as paper evidence.
The guarded runner verifies smoke output with `--min_task_count 1` only to catch
execution or import failures.

## Full Paired Run

Use the same split and task set for all methods:

```bash
cd /home/nlp-07/evermemos/EverOS/benchmarks/EvoAgentBench
PY=/home/nlp-07/evermemos/EverOS/methods/evermemos/.venv/bin/python
ROOT=/home/nlp-07/sqe_experiment/pass1_evoagentbench_configs

$PY src/run.py --config $ROOT/config_dense_codex.yaml \
  --split test --parallel 1 --job sqe_dense_codex_test
$PY src/run.py --config $ROOT/config_always_expand_codex.yaml \
  --split test --parallel 1 --job sqe_always_expand_codex_test
$PY src/run.py --config $ROOT/config_random_gated_codex.yaml \
  --split test --parallel 1 --job sqe_random_gated_codex_test
$PY src/run.py --config $ROOT/config_selective_codex.yaml \
  --split test --parallel 1 --job sqe_selective_codex_test
```

Increase `--parallel` only after confirming Docker capacity.

## Import And Verify

After completed job directories contain real `result.json` files:

```bash
cd /home/nlp-07/sqe_experiment
PY=/home/nlp-07/evermemos/EverOS/methods/evermemos/.venv/bin/python
JOBS=/home/nlp-07/evermemos/EverOS/benchmarks/EvoAgentBench/jobs

$PY scripts/23_import_evoagentbench_pass1.py \
  --job_dir $JOBS/sqe_dense_codex_test --method Dense-Only --overwrite
$PY scripts/23_import_evoagentbench_pass1.py \
  --job_dir $JOBS/sqe_always_expand_codex_test --method Always-Expand --overwrite
$PY scripts/23_import_evoagentbench_pass1.py \
  --job_dir $JOBS/sqe_random_gated_codex_test \
  --method Random-Gated-Expansion --overwrite
$PY scripts/23_import_evoagentbench_pass1.py \
  --job_dir $JOBS/sqe_selective_codex_test --method Selective-QE --overwrite

$PY scripts/21_summarize_pass1_results.py --results_dir results_pass1
$PY scripts/17_verify_pass1_results.py --results_dir results_pass1
$PY scripts/14_submission_readiness_check.py --root . --output SUBMISSION_READINESS.json
```

Pass@1 numbers can be used in the paper only after
`scripts/17_verify_pass1_results.py` reports no failures over the four-method
paired task set. The default verifier requires at least 500 paired task IDs.
