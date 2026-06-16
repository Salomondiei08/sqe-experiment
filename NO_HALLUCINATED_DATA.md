# No Hallucinated Data Policy

This experiment package must not contain invented, placeholder, or simulated
numbers presented as empirical evidence.

Allowed evidence:

- Executed result files with per-query rows, such as `*_detailed.jsonl`.
- Deterministic summaries recomputed from executed result files.
- Deterministic tables and figures generated from those summaries.
- Active paper tables listed in `paper/table_inventory.json` with non-empty
  `active_table_sources` entries that point to existing source files.
- Diagnostic documents that clearly state when evidence is missing.

Not allowed as paper evidence:

- Hallucinated metrics.
- Placeholder metrics.
- Simulated metrics.
- Any number introduced to fill a missing experiment, missing label, failed run,
  incomplete run, or reviewer-facing gap.
- Example numbers copied from planning documents.
- Schema files, manifest templates, or unlabeled audit packets presented as if
  they were completed results.
- Results from deprecated pilot artifacts unless explicitly labeled historical
  and excluded from active paper claims.

Specific measured-token rule:

- `results_tokenmeasured_500_seed42/` contains executed cost measurements for
  expansion ablations. These files may support calls/query, tokens/query, and
  latency/query claims.
- Measured-token reruns are not a replacement for the active retrieval-
  effectiveness comparison over independent memory-index seeds.

Specific missing-evidence rule:

- `PASS1_RESULTS_SCHEMA.md` is documentation only; it is not Pass@1 evidence.
- `human_audit/human_audit_labeling_manifest.template.json` is a template only;
  it is not a human-labeling manifest.
- `human_audit/human_audit_queries.csv` and `.jsonl` are unlabeled packets until
  separate labeled files, a labeling manifest, and a recomputed summary exist.

Specific random-gated rule:

- `Random-Gated-Expansion` means the executed random-gating budget control
  stored in `results_500_memory_seed*/random_budget_detailed.jsonl`.
- Any deprecated random-gated table artifact is not evidence and must not be
  imported, cited, or summarized in the active paper.

Specific query-expansion rule:

- `expansion_cache.json` files and generated hypothetical traces are method
  inputs for retrieval only. They are not factual execution logs, task-success
  evidence, human labels, or standalone empirical evidence.
- The paper may describe generated hypothetical traces as retrieval probes, but
  must not present their contents as real historical actions or observed
  software executions.
