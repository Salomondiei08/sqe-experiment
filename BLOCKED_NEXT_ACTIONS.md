# Blocked Next Actions

This file lists the remaining actions required before the SQE package can make
strong downstream or human-validation claims. It is not experiment evidence.
`SUBMISSION_READINESS.json` tracks this document as `Documented unblock steps`
so missing unblock instructions are visible in the readiness report.

## 1. Downstream Pass@1 / Task Success

Current status: blocked by Docker daemon permissions for user `nlp-07`.

Evidence:

- `pass1_harness_preflight.json`: `ready_to_run_pass1=false`
- `pass1_harness_preflight.json`: `checked_at_utc=2026-05-15T07:41:49+00:00`
- blocker: `current user cannot access Docker daemon`
- `/var/run/docker.sock` exists but user `nlp-07` is not in the socket group
- Docker socket group: `docker`
- Current user groups: `["nlp-07"]`
- Current `getent group docker` output:
  `docker:x:998:dice,cv-00,cv-01,cv-02,cv-03,cv-04,cv-05,cv-06,cv-07,cv-08,cv-09,cv-10`
- `nlp-07` is not listed in the `docker` group in `/etc/group`; `newgrp docker`
  and `sg docker` are therefore not an unblock path from this session
- `nerdctl` is installed, but rootless containerd is not running and the
  SWE-bench adapter is Docker-SDK based
- verified retrieval-context packets exist for Dense-Only, Always-Expand,
  Random-Gated-Expansion, and Selective-QE

Required admin action:

```bash
sudo usermod -aG docker nlp-07
```

Latest attempted unblock check from the Codex session failed because
passwordless sudo is not available:

Latest approval-path `sudo usermod -aG docker nlp-07` attempt failed:

```text
sudo: a terminal is required to read the password; either use the -S option to read from standard input or configure an askpass helper
```

Latest non-interactive sudo check from this session still failed:

```text
sudo: a password is required
```

Latest direct Docker check from this session still failed:

```text
permission denied while trying to connect to the Docker daemon socket at unix:///var/run/docker.sock
```

The current user groups remain `uid=1015(nlp-07) gid=1015(nlp-07)
groups=1015(nlp-07)`, while `/var/run/docker.sock` is owned by `root:docker`.

Run the admin command from an interactive shell with sudo access, or have an
administrator add `nlp-07` to the `docker` group.

Then start a new login session and verify:

```bash
docker ps
python3 scripts/26_check_pass1_harness_readiness.py \
  --output pass1_harness_preflight.json
```

Only after preflight reports `ready_to_run_pass1=true` with a fresh
`checked_at_utc` timestamp, run completed paired EvoAgentBench/SWE-bench jobs
for all four paper methods over the same task set. The guarded helper is:

```bash
scripts/42_run_pass1_after_preflight.sh smoke
scripts/42_run_pass1_after_preflight.sh full
```

The helper reruns preflight first and refuses to continue unless it is green. It
also refuses to overwrite existing imported Pass@1 rows unless
`PASS1_OVERWRITE=1` is explicitly set. Smoke mode writes to
`results_pass1_smoke/` and is only an operational check. Full mode writes to
`results_pass1/`, and the default summary/verifier require at least 500 paired
task IDs before Pass@1 can be treated as paper evidence.

The required paper methods are:

- Dense-Only
- Always-Expand
- Random-Gated-Expansion
- Selective-QE

After jobs finish, import, summarize, and verify:

```bash
python3 scripts/23_import_evoagentbench_pass1.py \
  --job_dir /path/to/evoagentbench/jobs/<job_name> \
  --method <METHOD> \
  --overwrite

python3 scripts/21_summarize_pass1_results.py --results_dir results_pass1
python3 scripts/17_verify_pass1_results.py --results_dir results_pass1
python3 scripts/14_submission_readiness_check.py --output SUBMISSION_READINESS.json
```

After both Pass@1 results and human labels exist, the package can be refreshed
with the guarded resume helper:

```bash
scripts/44_resume_after_external_evidence.sh verify-only
scripts/44_resume_after_external_evidence.sh rebuild-paper
```

`verify-only` summarizes and verifies the real external evidence, refreshes
readiness files, release bundles, the manifest, and the final verifier report.
`rebuild-paper` additionally reruns the full paper pipeline. The helper refuses
to continue if `results_pass1/` or `human_audit/labeled_human_audit_queries.csv`
is missing.

Acceptance gate:

- `scripts/17_verify_pass1_results.py` exits with status 0.
- The verifier reports at least 500 paired task IDs for the four paper methods.
- `SUBMISSION_READINESS.json` no longer marks downstream Pass@1/task-success
  as missing.
- `results_pass1/` contains real `manifest.json`, `*_detailed.jsonl`, and
  `pass1_summary.json` files.

## 2. Human-Audited Query Quality Labels

Current status: missing real labels.

Evidence:

- `human_audit/verification_report.json` reports missing:
  - `human_audit/labeled_human_audit_queries.csv`
  - `human_audit/human_audit_labeling_manifest.json`
  - `human_audit/human_audit_summary.json`
- `human_audit/human_audit_queries.csv` is an unlabeled source packet only.

Required human action:

1. Complete `human_audit/labeled_human_audit_queries.csv` for all source
   query rows.
2. Create `human_audit/human_audit_labeling_manifest.json` with real reviewers,
   label set, labeling date, row count, source file, labeled file, and protocol
   notes.
3. Summarize and verify:

```bash
python3 scripts/20_summarize_human_audit_labels.py --audit_dir human_audit
python3 scripts/18_verify_human_audit_labels.py \
  --audit_dir human_audit \
  --output human_audit/verification_report.json
python3 scripts/14_submission_readiness_check.py --output SUBMISSION_READINESS.json
```

Acceptance gate:

- `scripts/18_verify_human_audit_labels.py` exits with status 0.
- `SUBMISSION_READINESS.json` no longer marks human-audited query quality
  labels as missing.
- The paper cites only rates recomputed from the verified labeled CSV.

## Non-Negotiable Evidence Rule

Do not create placeholder Pass@1 rows, placeholder human labels, fabricated
metrics, or example values to satisfy these gates. Missing evidence must remain marked as missing
until the real artifacts exist and the verifiers pass.
