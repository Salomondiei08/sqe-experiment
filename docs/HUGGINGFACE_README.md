---
pretty_name: "SQE: Selective Query-Side Expansion for Agent Memory"
language:
  - en
task_categories:
  - text-retrieval
tags:
  - agent-memory
  - query-expansion
  - retrieval
  - software-engineering-agents
  - swe-smith
  - negative-results
size_categories:
  - 1K<n<10K
---

# SQE: When Does Query Expansion Help Agent Memory?

[Project page](https://salomondiei08.github.io/sqe-experiment/) ·
[Paper (PDF)](https://salomondiei08.github.io/sqe-experiment/assets/sqe-paper.pdf) ·
[Code](https://github.com/Salomondiei08/sqe-experiment) ·
[Contact](mailto:salomon@koreatech.ac.kr)

This dataset accompanies **When Does Query Expansion Help Agent Memory? A
Multi-Seed Study of Selective Expansion and Gate Reliability** (Salomon Diei,
KOREATECH, 2026). It contains the memory stores, evaluation queries, and result
files behind every number in the paper.

> **TL;DR** Expanding only low-confidence queries halves the cost of LLM query
> expansion for agent memory with no loss in Recall@5, but the confidence gate
> picks queries no better than chance.

## Dataset summary

Long-horizon software agents store execution traces and later retrieve them with
natural-language questions. Each memory item here is a single agent step
(thought, action, observation) from the `tool` split of
[SWE-bench/SWE-smith-trajectories](https://huggingface.co/datasets/SWE-bench/SWE-smith-trajectories).
For each of 8 seeds (42–49), a store of 5,000 steps was resampled from a shared
pool of about 16,500 steps, and 500 evaluation targets were sampled from that store.
Each target has one natural-language question, written by an LLM
(Qwen3.6-35B-A3B) that saw the step and was told not to copy identifiers.

## Structure

```
data/
  memory_seed{42..49}/
    memory_store.jsonl      # 5,000 agent steps (the retrieval corpus)
    eval_pairs.jsonl        # 500 query → target pairs
    dataset_manifest.json   # seed, source dataset and split, generator
results/
  results_500_memory_seed{42..49}/   # per-method summaries and per-query rows
  results_multiseed/                 # multi-seed report, paired tests, win/loss
  results_gate_calibration/          # gate threshold diagnostics
human_audit/                         # 100-query audit packet (unlabeled)
```

`eval_pairs.jsonl` fields:

| Field | Description |
| --- | --- |
| `query_id` | Query identifier within the seed |
| `query` | Natural-language question used for retrieval |
| `target_episode_id` | ID of the one relevant memory step in `memory_store.jsonl` |
| `target_text` | Text of the target step |

## Headline results

Mean over 8 seeds, % (full tables in the paper and `results/results_multiseed/`).

| Method | Recall@1 | Recall@5 | Recall@10 | Expanded |
| --- | ---: | ---: | ---: | ---: |
| Dense-Only | 45.5 | 68.5 | 74.2 | 0 |
| Hybrid-RRF | 32.5 | 63.5 | 71.8 | 0 |
| Always-Expand | 39.8 | 69.2 | 75.9 | 100 |
| Random-Gated-Expansion | 42.6 | 68.9 | 75.0 | 45.9 |
| SQE | 44.5 | 69.4 | 75.3 | 48.2 |

SQE is +0.9 Recall@5 points over dense retrieval (95% CI [+0.1, +1.7]) and is
statistically indistinguishable from a random gate at the same budget.

## Intended use and limitations

Intended for reproducing and auditing the paper's retrieval results, and as a
benchmark for gating or query-expansion methods over agent-trace memory.

- Queries are LLM-generated from the target step and can leak its wording.
- Exactly one step is relevant per query; sibling steps from the same trajectory
  count as misses, so Recall@k may understate all methods.
- Stores across seeds share about 30% of their steps; the 4,000 targets contain
  3,527 distinct steps.
- These are retrieval metrics only; downstream agent task success is not included.

See [`DATA_PROVENANCE.md`](DATA_PROVENANCE.md) and
[`NO_HALLUCINATED_DATA.md`](NO_HALLUCINATED_DATA.md) for where every number comes
from. Memory steps are derived from SWE-smith trajectories; please also follow the
upstream dataset's terms.

## Citation

```bibtex
@misc{diei2026sqe,
  title  = {When Does Query Expansion Help Agent Memory? A Multi-Seed Study of Selective Expansion and Gate Reliability},
  author = {Diei, Salomon},
  year   = {2026},
  note   = {Preprint},
  url    = {https://github.com/Salomondiei08/sqe-experiment}
}
```
