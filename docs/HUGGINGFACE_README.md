# Selective Query-Side Expansion (SQE)

<p>
  <a href="https://salomondiei08.github.io/sqe-experiment/">🌐 Interactive results</a> ·
  <a href="https://github.com/Salomondiei08/sqe-experiment">💻 Code</a> ·
  <a href="https://sites.google.com/view/nafsik?pli=1&authuser=0">🎤 NAFSIK 2026</a> ·
  <a href="mailto:salomon@koreatech.ac.kr">✉️ Contact</a>
</p>

Presented at [NAFSIK 2026](https://sites.google.com/view/nafsik?pli=1&authuser=0).

This dataset accompanies **Selective Query-Side Expansion for Long-Horizon
Agent Memory Retrieval**, a retrieval-time study of confidence-gated query
expansion for software-agent memory.

The release supports reproducible retrieval analysis over eight independently
rebuilt memory-index seeds. The companion code repository contains the
preparation scripts, verification tools, paper source, result summaries, and
the interactive evidence page.

## Headline evidence

Selective-QE reaches **69.4 mean Recall@5** across eight seeds while expanding
**46% of queries**. It is ahead of Hybrid-RRF, close to Dense-Only, and
statistically tied with the executed random-gating budget control. These are
retrieval metrics, not downstream agent success claims.

## Links

- [Interactive results](https://salomondiei08.github.io/sqe-experiment/)
- [Code and paper](https://github.com/Salomondiei08/sqe-experiment)
- [Paper PDF](https://github.com/Salomondiei08/sqe-experiment/blob/main/paper/main.pdf)

## Scope and limitations

The queries are generated retrieval probes paired with target memories from
the indexed store. Human query-quality labels and downstream SWE-bench-style
Pass@1 outcomes are not included in this dataset release. See the repository's
`docs/audits/DATA_PROVENANCE.md`, `docs/audits/CLAIM_AUDIT.md`, and `docs/audits/NO_HALLUCINATED_DATA.md` for the
full evidence boundary.

## Citation

```bibtex
@article{diei2026sqe,
  title  = {Selective Query-Side Expansion for Long-Horizon Agent Memory Retrieval},
  author = {DIEI, Salomon},
  year   = {2026},
  url    = {https://github.com/Salomondiei08/sqe-experiment}
}
```
