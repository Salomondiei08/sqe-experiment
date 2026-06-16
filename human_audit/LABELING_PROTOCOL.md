# Human Audit Labeling Protocol

This protocol is documentation only. It is not experiment evidence and does not
contain labels.

## Goal

Label whether the generated retrieval queries are understandable and whether
their paired target memory excerpts actually support the query. These labels are
intended to audit query quality, not to change retrieval metrics.

## Files

- Source packet: `human_audit_queries.csv`
- Expected labeled output: `labeled_human_audit_queries.csv`
- Expected manifest: `human_audit_labeling_manifest.json`
- Expected summary: `human_audit_summary.json`

Do not edit `query_id`, `query`, `target_episode_id`, or `target_excerpt` in the
labeled CSV. The verifier treats changes to those fields as failures.

## Labels

Use only these values for each required label field:

- `yes`
- `no`
- `uncertain`

Required label fields:

- `is_query_clear`
- `does_target_answer_query`
- `is_query_too_specific_or_copied`

`reviewer_notes` is optional free text.

## Decisions

Mark `is_query_clear=yes` only if the query is understandable without reading
the target excerpt. Use `uncertain` when the query depends on hidden context.

Mark `does_target_answer_query=yes` only if the target excerpt contains enough
information to answer the query. Use `no` when the excerpt is related but does
not answer the query. Use `uncertain` when the excerpt is truncated or ambiguous.

Mark `is_query_too_specific_or_copied=yes` when the query appears to copy
unusual identifiers, filenames, exact phrases, or implementation details from
the target in a way that could make retrieval artificially easy.

## Required Manifest

After real labels are collected, create `human_audit_labeling_manifest.json`
with:

- `reviewers`: at least two reviewer names or IDs
- `label_set`: exactly `["no", "uncertain", "yes"]`
- `labeling_date`: actual review date in `YYYY-MM-DD` form
- `n_labeled_rows`: number of rows in `labeled_human_audit_queries.csv`
- `source_csv`: `human_audit_queries.csv`
- `labeled_csv`: `labeled_human_audit_queries.csv`
- `protocol_notes`: nonempty list describing how labeling was performed
- `adjudication_notes`: nonempty list describing how disagreements were
  reconciled before writing `labeled_human_audit_queries.csv`

Do not use template or TODO values in the real manifest.

## Verification

After real labels exist, run:

```bash
python scripts/20_summarize_human_audit_labels.py --audit_dir human_audit
python scripts/18_verify_human_audit_labels.py \
  --audit_dir human_audit \
  --output human_audit/verification_report.json
```

Human-audit numbers may be reported only after the verifier has `failures: []`.
