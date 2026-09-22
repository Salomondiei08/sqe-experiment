# arXiv submission notes

Build the active manuscript and prepare a minimal upload archive:

```bash
python3 scripts/06_make_paper_artifacts.py \
  --results_dir results/seed42 \
  --paper_dir paper \
  --data_dir data_500_memory_seed42
python3 scripts/46_prepare_arxiv_submission.py
```

The second command compiles the isolated source tree before creating
`/tmp/sqe_arxiv_submission.zip`. The archive contains only `main.tex`, the
bibliography, and the tables and figures referenced by the manuscript. It does
not include generated PDFs, logs, unused diagnostics, or result data.

Before submission, review the arXiv-generated preview and metadata manually.
Select an appropriate category and license; those choices are author decisions
and are intentionally not automated by this repository.
