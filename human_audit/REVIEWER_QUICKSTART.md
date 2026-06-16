# Human Audit Reviewer Quickstart

This file is documentation only. It is not experiment evidence and does not
contain labels.

## Inputs

- `human_audit_queries.csv`: source spreadsheet to label.
- `reviewer_packets/*.csv`: optional reviewer-specific copies of the same
  source rows with blank label fields.
- `LABELING_PROTOCOL.md`: labeling rules.
- `labeling_form.html`: optional local browser helper.

Do not edit `query_id`, `query`, `target_episode_id`, or `target_excerpt`.
Reviewer packets are assignment aids only. They are not evidence.

## Labels

Fill these fields for every row with only `yes`, `no`, or `uncertain`:

- `is_query_clear`
- `does_target_answer_query`
- `is_query_too_specific_or_copied`

`reviewer_notes` is optional free text. Use `uncertain` instead of guessing.

## Required Outputs

After real review, the audit directory must contain:

- `labeled_human_audit_queries.csv`
- `human_audit_labeling_manifest.json`
- `human_audit_summary.json`

The manifest must use an actual `YYYY-MM-DD` `labeling_date`, at least two
reviewers, `label_set` equal to `["no", "uncertain", "yes"]`,
`source_csv` equal to `human_audit_queries.csv`, and `labeled_csv` equal to
`labeled_human_audit_queries.csv`. It must also document `adjudication_notes`
for how reviewer disagreements were reconciled.

## Verification

Run these commands from the project root after real labels exist:

```bash
python3 scripts/20_summarize_human_audit_labels.py --audit_dir human_audit
python3 scripts/18_verify_human_audit_labels.py \
  --audit_dir human_audit \
  --output human_audit/verification_report.json
python3 scripts/14_submission_readiness_check.py --root . --output SUBMISSION_READINESS.json
```

Human-audit numbers can be used in the paper only after the verifier reports
`failures: []`.
