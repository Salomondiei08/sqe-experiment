"""
Generate a static HTML form for human audit labeling.

The generated form is a reviewer convenience only. It does not create labels by
itself, does not validate reviewer identity, and is not paper evidence. The
exported CSV must still be saved as labeled_human_audit_queries.csv, accompanied
by a real labeling manifest, summarized, and verified before any human-audit
numbers can be reported.
"""

import argparse
import html
import json
from pathlib import Path


LABELS = ["", "yes", "no", "uncertain"]
LABEL_FIELDS = [
    "is_query_clear",
    "does_target_answer_query",
    "is_query_too_specific_or_copied",
]


def read_jsonl(path):
    rows = []
    with open(path) as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def html_escape_json(rows):
    return html.escape(json.dumps(rows, sort_keys=True), quote=False)


def build_html(rows):
    rows_json = html_escape_json(rows)
    labels_json = json.dumps(LABELS)
    label_fields_json = json.dumps(LABEL_FIELDS)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>SQE Human Audit Labeling Form</title>
  <style>
    body {{
      margin: 0;
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: #1d2329;
      background: #f7f8f9;
    }}
    header {{
      position: sticky;
      top: 0;
      z-index: 10;
      background: #ffffff;
      border-bottom: 1px solid #d9dee3;
      padding: 14px 20px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
    }}
    h1 {{
      margin: 0;
      font-size: 18px;
      font-weight: 650;
    }}
    main {{
      max-width: 1180px;
      margin: 0 auto;
      padding: 18px 20px 40px;
    }}
    .status {{
      font-size: 14px;
      color: #40505f;
    }}
    .toolbar {{
      display: flex;
      gap: 8px;
      align-items: center;
      flex-wrap: wrap;
    }}
    button {{
      border: 1px solid #aeb8c2;
      background: #ffffff;
      color: #17202a;
      border-radius: 6px;
      padding: 8px 10px;
      font-size: 14px;
      cursor: pointer;
    }}
    button.primary {{
      background: #0f766e;
      color: white;
      border-color: #0f766e;
    }}
    .notice {{
      border: 1px solid #d0d7de;
      background: #ffffff;
      border-radius: 8px;
      padding: 12px 14px;
      margin-bottom: 14px;
      font-size: 14px;
      line-height: 1.45;
    }}
    .query {{
      background: #ffffff;
      border: 1px solid #d9dee3;
      border-radius: 8px;
      margin: 12px 0;
      padding: 14px;
    }}
    .query h2 {{
      font-size: 15px;
      margin: 0 0 8px;
    }}
    .grid {{
      display: grid;
      grid-template-columns: minmax(220px, 1fr) minmax(260px, 1.2fr);
      gap: 12px;
    }}
    .textblock {{
      white-space: pre-wrap;
      line-height: 1.4;
      font-size: 14px;
    }}
    .excerpt {{
      max-height: 260px;
      overflow: auto;
      border-left: 3px solid #ccd6dd;
      padding-left: 10px;
    }}
    .labels {{
      display: grid;
      grid-template-columns: repeat(3, minmax(180px, 1fr));
      gap: 10px;
      margin-top: 12px;
    }}
    label {{
      display: grid;
      gap: 4px;
      font-size: 13px;
      color: #34414d;
    }}
    select, textarea, input {{
      border: 1px solid #bec8d2;
      border-radius: 6px;
      padding: 7px 8px;
      font: inherit;
      background: #ffffff;
    }}
    textarea {{
      margin-top: 10px;
      width: 100%;
      box-sizing: border-box;
      min-height: 54px;
      resize: vertical;
    }}
    @media (max-width: 820px) {{
      header, .toolbar {{
        align-items: stretch;
        flex-direction: column;
      }}
      .grid, .labels {{
        grid-template-columns: 1fr;
      }}
    }}
  </style>
</head>
<body>
  <header>
    <div>
      <h1>SQE Human Audit Labeling Form</h1>
      <div class="status" id="status"></div>
    </div>
    <div class="toolbar">
      <input id="reviewer" placeholder="reviewer id">
      <button id="export" class="primary">Export CSV</button>
      <button id="clear">Clear Local Labels</button>
    </div>
  </header>
  <main>
    <section class="notice">
      This form is a convenience tool only. It is not evidence. Exported labels
      must be saved as <code>human_audit/labeled_human_audit_queries.csv</code>,
      accompanied by a real <code>human_audit_labeling_manifest.json</code>,
      summarized, and verified before use in the paper.
    </section>
    <div id="rows"></div>
  </main>
  <script id="rows-data" type="application/json">{rows_json}</script>
  <script>
    const rows = JSON.parse(document.getElementById("rows-data").textContent);
    const labels = {labels_json};
    const labelFields = {label_fields_json};
    const storageKey = "sqe-human-audit-labels-v1";
    const state = JSON.parse(localStorage.getItem(storageKey) || "{{}}");

    function esc(value) {{
      return String(value ?? "").replace(/[&<>"']/g, ch => ({{
        "&": "&amp;", "<": "&lt;", ">": "&gt;", "\\"": "&quot;", "'": "&#39;"
      }}[ch]));
    }}

    function csvCell(value) {{
      const s = String(value ?? "");
      return '"' + s.replace(/"/g, '""') + '"';
    }}

    function persist() {{
      localStorage.setItem(storageKey, JSON.stringify(state));
      renderStatus();
    }}

    function renderStatus() {{
      const done = rows.filter(row => {{
        const item = state[row.query_id] || {{}};
        return labelFields.every(field => ["yes", "no", "uncertain"].includes(item[field]));
      }}).length;
      document.getElementById("status").textContent = `${{done}} / ${{rows.length}} complete`;
    }}

    function makeSelect(row, field) {{
      const current = (state[row.query_id] || {{}})[field] || "";
      const options = labels.map(label => {{
        const text = label || "unlabeled";
        return `<option value="${{esc(label)}}" ${{label === current ? "selected" : ""}}>${{esc(text)}}</option>`;
      }}).join("");
      return `<label>${{esc(field)}}<select data-query="${{esc(row.query_id)}}" data-field="${{esc(field)}}">${{options}}</select></label>`;
    }}

    function renderRows() {{
      const root = document.getElementById("rows");
      root.innerHTML = rows.map(row => {{
        const saved = state[row.query_id] || {{}};
        return `<article class="query">
          <h2>${{esc(row.query_id)}} | ${{esc(row.target_episode_id)}}</h2>
          <div class="grid">
            <div>
              <strong>Query</strong>
              <div class="textblock">${{esc(row.query)}}</div>
            </div>
            <div>
              <strong>Target excerpt</strong>
              <div class="textblock excerpt">${{esc(row.target_excerpt)}}</div>
            </div>
          </div>
          <div class="labels">${{labelFields.map(field => makeSelect(row, field)).join("")}}</div>
          <textarea data-query="${{esc(row.query_id)}}" data-field="reviewer_notes" placeholder="reviewer notes">${{esc(saved.reviewer_notes || "")}}</textarea>
        </article>`;
      }}).join("");
      root.querySelectorAll("select, textarea").forEach(el => {{
        el.addEventListener("change", event => {{
          const qid = event.target.dataset.query;
          const field = event.target.dataset.field;
          state[qid] = state[qid] || {{}};
          state[qid][field] = event.target.value;
          persist();
        }});
      }});
      renderStatus();
    }}

    function exportCsv() {{
      const header = [
        "query_id", "query", "target_episode_id", "target_excerpt",
        "is_query_clear", "does_target_answer_query",
        "is_query_too_specific_or_copied", "reviewer_notes"
      ];
      const csvRows = [header.map(csvCell).join(",")];
      for (const row of rows) {{
        const item = state[row.query_id] || {{}};
        csvRows.push([
          row.query_id,
          row.query,
          row.target_episode_id,
          row.target_excerpt,
          item.is_query_clear || "",
          item.does_target_answer_query || "",
          item.is_query_too_specific_or_copied || "",
          item.reviewer_notes || ""
        ].map(csvCell).join(","));
      }}
      const blob = new Blob([csvRows.join("\\n") + "\\n"], {{type: "text/csv"}});
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      const reviewer = document.getElementById("reviewer").value.trim() || "reviewer";
      a.href = url;
      a.download = `labeled_human_audit_queries_${{reviewer}}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    }}

    document.getElementById("export").addEventListener("click", exportCsv);
    document.getElementById("clear").addEventListener("click", () => {{
      if (confirm("Clear locally stored labels in this browser?")) {{
        localStorage.removeItem(storageKey);
        location.reload();
      }}
    }});
    renderRows();
  </script>
</body>
</html>
"""


def main(args):
    source = Path(args.source).resolve()
    output = Path(args.output).resolve()
    manifest = Path(args.manifest).resolve()
    rows = read_jsonl(source)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(build_html(rows))
    manifest.write_text(
        json.dumps(
            {
                "artifact_type": "human_audit_labeling_form",
                "is_evidence": False,
                "source": str(source),
                "output": str(output),
                "n_rows": len(rows),
                "note": (
                    "Reviewer convenience artifact only. This is not a labeled "
                    "dataset and not paper evidence."
                ),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    print(json.dumps({"output": str(output), "manifest": str(manifest), "n_rows": len(rows)}, indent=2))
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default="/home/nlp-07/sqe_experiment/human_audit/human_audit_queries.jsonl")
    parser.add_argument("--output", default="/home/nlp-07/sqe_experiment/human_audit/labeling_form.html")
    parser.add_argument("--manifest", default="/home/nlp-07/sqe_experiment/human_audit/labeling_form_manifest.json")
    raise SystemExit(main(parser.parse_args()))
