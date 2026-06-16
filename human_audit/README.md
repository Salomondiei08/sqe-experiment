# Human Audit Packet

This directory contains an unlabeled 100-query audit sample for the SQE
retrieval paper. It is not a result source yet.

## Files

- `human_audit_queries.csv`: spreadsheet-friendly review file.
- `human_audit_queries.jsonl`: same rows in JSONL form.
- `human_audit_manifest.json`: source path, sample size, seed, and excerpt
  length.
- `LABELING_PROTOCOL.md`: reviewer protocol for producing real labels.
- `REVIEWER_QUICKSTART.md`: short reviewer handoff with required outputs and
  verification commands.
- `labeling_form.html`: optional browser-based labeling helper.
- `labeling_form_manifest.json`: provenance for the helper form.
- `reviewer_packets/`: optional reviewer-specific handoff CSVs generated from
  the source rows with blank label fields.
- `reviewer_packets_verification.json`: verification report showing the
  reviewer packets are blank non-evidence handoff files.
- `verification_report.json`: latest verifier report. This is expected to
  contain failures until real labels, a real labeling manifest, and a recomputed
  summary are added.

The labeling form is not evidence. It only helps reviewers export a CSV with
the expected columns.
`LABELING_PROTOCOL.md` is also not evidence; it documents the protocol that
future reviewers should follow before creating labeled artifacts.

## Reviewer Fields

Each row contains a generated retrieval query, the target memory ID, and a short
target-memory excerpt. Reviewers should fill only these fields:

- `is_query_clear`: `yes`, `no`, or `uncertain`.
- `does_target_answer_query`: `yes`, `no`, or `uncertain`.
- `is_query_too_specific_or_copied`: `yes`, `no`, or `uncertain`.
- `reviewer_notes`: optional short note.

## Labeling Rules

- Mark `is_query_clear=yes` only when the query is understandable without
  reading the target.
- Mark `does_target_answer_query=yes` only when the target excerpt contains
  enough information to answer the query.
- Mark `is_query_too_specific_or_copied=yes` when the query appears to copy
  unusual phrasing, filenames, or identifiers directly from the target in a way
  that makes retrieval artificially easy.
- Use `uncertain` instead of guessing.

## Current Status

The packet is intentionally unlabeled. The verifier fails if reviewer fields are
filled without a separate documented labeling step. Do not report human-audit
numbers in the paper until reviewed labels and a labeling protocol are added.

## Required Labeled Artifacts

Before reporting human-audit numbers, add these separate files:

- `labeled_human_audit_queries.csv`: same source rows as
  `human_audit_queries.csv`, with reviewer labels filled.
- `human_audit_labeling_manifest.json`: reviewer IDs or names, label set,
  labeling date, protocol notes, and `n_labeled_rows`. The protocol notes
  should cite or summarize `LABELING_PROTOCOL.md`.
- `human_audit_summary.json`: label counts and rates recomputed from the labeled
  CSV. The summary must declare `artifact_type=human_audit_summary`,
  `is_experiment_evidence=true`, `source_csv=human_audit_queries.csv`,
  `labeled_csv=labeled_human_audit_queries.csv`, and
  `labeling_manifest=human_audit_labeling_manifest.json`.

The real labeling manifest must not contain template/TODO values. It must list:
at least two `reviewers`, `label_set`, `labeling_date`, `n_labeled_rows`,
`source_csv`, `labeled_csv`, `protocol_notes`, and `adjudication_notes`.
The verifier requires `labeling_date` to use exact `YYYY-MM-DD` format.

The optional `human_audit_labeling_manifest.template.json` file is a template
only. It is not evidence and must not be renamed until real labels exist.

The optional `labeling_form.html` can be opened in a browser. It stores draft
labels in browser local storage and exports a CSV. That exported file still
needs to be reviewed, saved as `labeled_human_audit_queries.csv`, paired with a
real labeling manifest, summarized, and verified.

Regenerate the form with:

```bash
python scripts/27_make_human_audit_labeling_form.py
```

Generate reviewer-specific blank packets with:

```bash
python scripts/40_make_human_audit_reviewer_packets.py
```

The reviewer packets are not evidence. They only help assign source rows to
reviewers.

After real labels are entered, generate the summary with:

```bash
python scripts/20_summarize_human_audit_labels.py --audit_dir human_audit
```

Run:

```bash
python scripts/18_verify_human_audit_labels.py \
  --audit_dir human_audit \
  --output human_audit/verification_report.json
```

This command must pass before labels can be used in the paper.
