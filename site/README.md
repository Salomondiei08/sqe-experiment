# SQE interactive research page

This is a dependency-free static site. `index.html` loads the committed
`data/multiseed_report.json` file and renders the released experiment without
inventing or fetching metrics at runtime.

## Local preview

From the repository root:

```bash
python3 -m http.server 4173 --directory site
```

Open <http://localhost:4173> in a browser. A local HTTP server is required
because browsers block `fetch()` from `file://` pages.

The page is designed to be deployable through GitHub Pages. It uses the
repository's GitHub and Hugging Face URLs for external artifact links.
