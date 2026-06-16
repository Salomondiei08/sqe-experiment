# EvoAgentBench Pass@1 Configs

These configs prepare future real SWE-bench task-success runs. They do not run
agents and are not Pass@1 evidence.

Preflight first:

```bash
cd /home/nlp-07/sqe_experiment
/home/nlp-07/evermemos/EverOS/methods/evermemos/.venv/bin/python \
  scripts/26_check_pass1_harness_readiness.py \
  --output pass1_harness_preflight.json
```

Current blocker: user `nlp-07` cannot access `/var/run/docker.sock`.

When Docker access is available, run small pilots first:

```bash
cd /home/nlp-07/evermemos/EverOS/benchmarks/EvoAgentBench
/home/nlp-07/evermemos/EverOS/methods/evermemos/.venv/bin/python src/run.py \
  --config /home/nlp-07/sqe_experiment/pass1_evoagentbench_configs/dense_only_config.yaml \
  --job sqe_dense_only_pilot \
  --task astropy__astropy-12907

/home/nlp-07/evermemos/EverOS/methods/evermemos/.venv/bin/python src/run.py \
  --config /home/nlp-07/sqe_experiment/pass1_evoagentbench_configs/selective_qe_config.yaml \
  --job sqe_selective_qe_pilot \
  --task astropy__astropy-12907
```

For the full paper comparison, use the four-method configs documented in
`EXECUTION_QUICKSTART.md` and `RUNBOOK.md`: Dense-Only, Always-Expand,
Random-Gated-Expansion, and Selective-QE. The four matching context packets are present under
`/home/nlp-07/sqe_experiment/pass1_contexts/`; they are prompt inputs only, not
Pass@1 evidence.

Only completed job directories containing real `result.json` files and verifier
rewards can be imported:

```bash
cd /home/nlp-07/sqe_experiment
python scripts/23_import_evoagentbench_pass1.py \
  --job_dir /home/nlp-07/evermemos/EverOS/benchmarks/EvoAgentBench/jobs/sqe_dense_only_pilot \
  --method Dense-Only

python scripts/23_import_evoagentbench_pass1.py \
  --job_dir /home/nlp-07/evermemos/EverOS/benchmarks/EvoAgentBench/jobs/sqe_selective_qe_pilot \
  --method Selective-QE
```
