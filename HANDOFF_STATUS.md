# SQE Paper Package Handoff Status

This file is documentation only. It is not experiment evidence.

## Current State

- The retrieval-paper package is regenerated and verifier-clean.
- The compiled paper is `paper/main.pdf`.
- The latest clean build audit reports `pdf_pages=11` and
  `pdf_bytes=473040`.
- The source manuscript is `paper/main.tex`.
- Common non-destructive maintenance commands are available through
  `Makefile`; use `make verify`, `make release`, `make manifest`, or the
  guarded `make external-evidence-resume` target after real Pass@1 rows and
  human labels exist.
- A two-column layout preview is available at
  `paper/main_conference_preview.pdf`. It is not an official venue template and
  is not experiment evidence.
- A browser-based conference presentation is available at
  `presentation/sqe_conference_slides.html`, with speaker notes in
  `presentation/sqe_conference_speaker_notes.md`. It uses the verified
  retrieval results only and explicitly avoids Pass@1 or human-label claims.
- The author in the manuscript is Salomon DIEI.
- The public repository placeholder is `TODO: add GitHub URL`.
- The local GitHub code-release helper is
  `scripts/34_prepare_github_code_release.py`.
- The Hugging Face dataset placeholder is
  `TODO: add Hugging Face dataset URL`.
- The local Hugging Face release helper is
  `scripts/33_prepare_hf_dataset_release.py`.
- After real Pass@1 results and human labels exist, the guarded resume helper
  is `scripts/44_resume_after_external_evidence.sh`. It does not create labels
  or task outcomes; it summarizes/verifies existing evidence, refreshes
  readiness files, release bundles, the manifest, and the final verifier report.
- The release helpers are non-destructive. Their deprecated `--clean` flag is
  retained only for command compatibility and is ignored if supplied.
- `scripts/07_verify_experiment.py` enforces this with the
  `release_helpers_non_destructive` check; it fails if destructive removal
  patterns return to the release helpers or if the no-op `--clean` guard is
  missing.
- The paper style audit is `PAPER_STYLE_AUDIT.json`; it now guards figure/table
  references, nonempty figure descriptions, excessive manual bolding,
  dash/curly-quote characters, and a small list of hype or vague phrases.
- The figure asset audit is `FIGURE_ASSET_AUDIT.json`; it checks the active
  paper figures for PNG/SVG presence, minimum rendered size, brightness,
  nonblank content, and SVG text elements.
- The evidence-claim audit is `PAPER_EVIDENCE_CLAIM_AUDIT.json`; it blocks
  positive Pass@1, task-success, or human-validation claims while those
  readiness gates are missing. `SUBMISSION_READINESS.json` reports it as
  `Paper evidence-claim audit`.
- The compute-environment metadata is `COMPUTE_ENVIRONMENT.json`; it is not an
  experiment metric and does not invent wall-clock runtime.
- `LLM_USAGE_DISCLOSURE.md` is a draft disclosure for venues that require
  reporting substantial LLM assistance. It is documentation only and not
  experiment evidence.
- Active retrieval evidence uses 8 independently rebuilt memory-index seeds:
  `results_500_memory_seed42/` through `results_500_memory_seed49/`.
- The primary aggregate is `results_multiseed/multiseed_report.json`.
- The paired aggregate is `results_multiseed/multiseed_paired_tests.json`.
- `Random-Gated-Expansion` is an executed control backed by
  `results_500_memory_seed*/random_budget_detailed.jsonl`.

## Latest Verification Commands

Run these from `/home/nlp-07/sqe_experiment`:

```bash
python3 scripts/31_verify_latex_clean_build.py
python3 scripts/14_submission_readiness_check.py
python3 scripts/13_make_artifact_manifest.py
python3 scripts/07_verify_experiment.py \
  --data_dir data_500_memory_seed42 \
  --index_dir index_500_seed42 \
  --results_dir results_500_memory_seed42 \
  --paper_dir paper \
  --report_path /tmp/sqe_verify_latest.json
```

The latest verifier status after the blocker refresh and release sync was:

- `failures: []`
- `artifact_manifest_stale_entries: []`
- `unsupported_claim_references: []`
- `legacy_random_budget_doc_references: []`
- `no_hallucinated_data_missing_required_phrases: []`
- `references_bib.missing_required_keys: []`
- `references_bib.forbidden_loose_entries: []`
- `references_bib.missing_required_metadata: []`
- `stale_seed_provenance_doc_references: []`
- `stale_gate_variant_ci_doc_references: []`
- `readiness_missing_guard_fields: []`
- `readiness_nonempty_guard_fields: []`
- `readiness_latex_pdf_pages: 11`
- `main_pdf_pages: 11`
- `readiness_pass1_preflight_checked_at_utc: 2026-05-15T06:50:02+00:00`
- `readiness_pass1_preflight_ready: false`
- `readiness_pass1_docker_socket_group: docker`
- `readiness_pass1_docker_user_group_names: ["nlp-07"]`
- `readiness_pass1_docker_user_in_socket_group: false`
- `readiness_pass1_docker_user_listed_in_socket_group: false`
- `ARTIFACT_MANIFEST.json`: `n_files=242`
- `github_code_release/RELEASE_MANIFEST.json`: `n_files=210`

The official `results_500_memory_seed42/verification_report.json` through
`results_500_memory_seed49/verification_report.json` files have also been
refreshed with the current verifier schema, including the bibliography,
handoff-status, stale seed-provenance, stale gate-variant CI wording, and
readiness anti-hallucination, timestamped Pass@1 preflight summary checks, and
the generated-trace-as-retrieval-probe guardrails, plus the PDF page-count
cross-check. They also include the `readiness_release_helpers_status=pass`
snapshot and the `release_helpers_non_destructive` check, which reports no
destructive release-helper patterns and no missing no-op `--clean` guards.
The current paper package includes four numbered figures:
`method_overview.png`, `recall_at_5.png`, `gate_diagnostic.png`, and
`threshold_sensitivity.png`.
The paper pipeline intentionally refreshes those tracked reports again after
`SUBMISSION_READINESS.json` is current, then rebuilds `ARTIFACT_MANIFEST.json`.
Do not remove that second refresh as duplicate work; it prevents stale embedded
readiness timestamps in the official reports.
The verifier also checks `paper_generator_professional_formatting`; this guard
requires the paper generator to emit figure descriptions and rejects forced
`[H]` figure placement.

## Strong-Submission Blockers

`SUBMISSION_READINESS.json` currently reports:

- `strong_submission_ready=false`
- `blocking_count=2`

The two blockers are:

1. Real downstream Pass@1/task-success results are missing.
2. Real human-audited query-quality labels are missing.

The Pass@1 harness preflight is blocked because user `nlp-07` cannot access the
Docker daemon. The attempted command

```bash
sudo usermod -aG docker nlp-07
```

failed from this session because sudo requires an interactive password prompt.
The latest approval-path attempt also failed with:

```text
sudo: a terminal is required to read the password; either use the -S option to read from standard input or configure an askpass helper
```

The non-interactive check `sudo -n true` currently fails with
`sudo: a password is required`, so Codex cannot make this group change from the
current session. The Docker group is currently
`docker:x:998:dice,cv-00,cv-01,cv-02,cv-03,cv-04,cv-05,cv-06,cv-07,cv-08,cv-09,cv-10`;
`nlp-07` is not listed. Run the admin command from an interactive shell with
sudo access, then start a new login session and rerun
`scripts/26_check_pass1_harness_readiness.py`.

Human audit source packets exist under `human_audit/`, but the labeled CSV,
labeling manifest, and summary are intentionally absent until real reviewers
label the rows.

## Non-Negotiable Rule

Do not create placeholder Pass@1 rows, placeholder labels, fabricated metrics,
or simulated results to satisfy the missing gates. Missing evidence must remain
marked as missing until real artifacts exist and the verifiers pass.
