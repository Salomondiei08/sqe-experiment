# Selective Query-Side Expansion (SQE)

**Confidence-gated retrieval augmentation for long-horizon agent memory.**

<p>
  <a href="https://salomondiei08.github.io/sqe-experiment/">🌐 Interactive results</a> ·
  <a href="https://huggingface.co/datasets/TheReinventGuy/sqe-experiment">🤗 Dataset</a> ·
  <a href="paper/main.pdf">📄 Paper</a> ·
  <a href="https://sites.google.com/view/nafsik?pli=1&authuser=0">🎤 NAFSIK 2026</a> ·
  <a href="mailto:salomon@koreatech.ac.kr">✉️ Contact</a>
</p>

Presented at [NAFSIK 2026](https://sites.google.com/view/nafsik?pli=1&authuser=0).

SQE studies when a memory-retrieval query should be expanded rather than
expanded unconditionally. The method keeps the memory store and indexes fixed,
uses an initial retrieval pass as a confidence signal, and selectively adds
hypothetical execution traces and paraphrases before Reciprocal Rank Fusion.

> **Evidence status.** This release supports a retrieval-only, cost-aware
> result. On eight independently rebuilt memory-index seeds, Selective-QE
> reaches **69.4% mean Recall@5** at a **46% expansion rate**. It is clearly
> above Hybrid-RRF, but remains close to Dense-Only and statistically tied with
> the executed random-gating budget control. We do not claim downstream
> SWE-bench success or human-validated query quality here.

## Explore the release

The [interactive research page](https://salomondiei08.github.io/sqe-experiment/)
turns the released JSON summaries into a browsable evidence view: method
comparison, per-seed inspection, cost/quality plot, pipeline explanation, and
artifact links.

## Repository map

The root contains only the entry points. Supporting material is grouped in
[`docs/`](docs/), result artifacts in [`results/`](results/), executable
pipelines in [`scripts/`](scripts/), and paper assets in [`paper/`](paper/).
The [documentation map](docs/README.md) explains the audit and release folders.

| Resource | What it contains |
| --- | --- |
| [Paper](paper/main.pdf) | LaTeX source, PDF, figures, tables, and references |
| [Dataset 🤗](https://huggingface.co/datasets/TheReinventGuy/sqe-experiment) | Companion Hugging Face dataset |
| [`results/`](results) | Independent seeds 42–49, paired tests, gate diagnostics, and token measurements |
| [`scripts/`](scripts) | Dataset preparation, retrieval, verification, and report generation |
| [`paper/`](paper) | Main paper, figures, tables, and source inventory |
| [`human_audit/`](human_audit) | Query audit packet and labeling protocol; labels remain separate |

## Headline results

Eight independent memory-index seeds, 500 queries per seed:

| Method | Recall@1 | Recall@5 | Recall@10 | Expansion |
| --- | ---: | ---: | ---: | ---: |
| Dense-Only | 45.5 | 68.5 | 74.2 | — |
| Hybrid-RRF | 31.3 | 63.5 | 72.7 | — |
| Always-Expand | 39.8 | **69.2** | **75.9** | 100% |
| Random-Gated-Expansion | 42.6 | 68.9 | 75.0 | 47% |
| **Selective-QE** | **44.6** | **69.4** | 75.3 | **46%** |

Selective-QE improves Recall@5 over Dense-Only by a small retrieval-only
margin, improves over Hybrid-RRF by 5.9 points, and uses roughly half the
expansion budget of Always-Expand. The random-gated control is intentionally
included because matching cost alone is a demanding baseline for the gate.

## Method

1. Run dense retrieval over the unchanged memory index.
2. Use the top-1 dense score as the released experiment's gate.
3. For low-confidence queries, generate two hypothetical trace probes and two
   paraphrases.
4. Retrieve each variant against the same index and fuse the ranked lists with
   RRF.

The newer paper draft studies a pre-decoding Yes/No logit gate. That gate is a
research direction in the paper and should not be confused with the released
top-1-score implementation used for the tables above.

## Reproduce or audit

```bash
python scripts/07_verify_experiment.py
python scripts/09_make_multiseed_report.py
python scripts/14_submission_readiness_check.py
```

The release is deliberately explicit about what is and is not present. Raw
memory stores, detailed per-query JSONL rows, human labels, and downstream
Pass@1 outcomes are not bundled into this public code release.

## Citation

```bibtex
@article{diei2026sqe,
  title  = {Selective Query-Side Expansion for Agent Memory Retrieval: A Multi-Seed Study of Cost and Gate Reliability},
  author = {DIEI, Salomon},
  year   = {2026},
  url    = {https://github.com/Salomondiei08/sqe-experiment}
}
```

## License and contact

See the repository files and dataset card for the applicable release terms.
For questions or collaboration, contact
[Salomon DIEI](mailto:salomon@koreatech.ac.kr).
