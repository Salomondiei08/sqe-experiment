# Version history

## Unreleased

- Added the two-column preprint of the paper (`paper/preprint/`) with figures
  rebuilt from the released JSON, corrected method and data claims after a fact
  check, and fixed author lists and venues in the references.
- Updated the project page to the preprint: new title and abstract, key findings,
  paired-test table, gate analysis, limitations, BibTeX, talk slides, Google
  Scholar and social-preview metadata; redesigned the layout.
- Rewrote the GitHub README and the Hugging Face dataset card to match the
  preprint, including corrected Hybrid-RRF Recall@1 (32.5) and mean expansion
  rates (SQE 48.2%, random gate 45.9%).

- Reframed the paper as a multi-seed retrieval study with a negative gate-
  reliability result; expanded related work, disclosed statistical and dataset
  limitations, corrected the cross-seed protocol description, and added an AI-
  assistance disclosure.
- Added explicit Hugging Face revision pinning for future dataset preparation
  and made local Makefile targets portable.
- Replaced paper placeholders with public GitHub and Hugging Face links,
  documented the NAFSIK 2026 presentation, and rebuilt the paper PDFs.
- Added a responsive, dependency-free interactive research page under `site/`
  with live rendering of the released multiseed result summaries.
- Added a public-facing README with GitHub, Hugging Face, paper, dataset, and
  interactive-page links plus a clear evidence-status statement.
