// Renders the released multi-seed report (data/multiseed_report.json).
// Every number shown by this script is read from that file at load time.
const state = { report: null, metric: "recall@5", seed: "all" };

const methods = ["Dense-Only", "BM25-Only", "Hybrid-RRF", "Paraphrases-Only", "HyDE-Traces-Only", "Always-Expand", "Random-Gated-Expansion", "Selective-QE"];
const names = { "Dense-Only": "Dense-Only", "BM25-Only": "BM25-Only", "Hybrid-RRF": "Hybrid-RRF", "Paraphrases-Only": "Paraphrases", "HyDE-Traces-Only": "HyDE-Traces", "Always-Expand": "Always-Expand", "Random-Gated-Expansion": "Random gate", "Selective-QE": "SQE" };

async function loadData() {
  const response = await fetch("./data/multiseed_report.json");
  if (!response.ok) throw Error("Could not load released report");
  state.report = await response.json();
  renderAll();
}

/** Mean of a metric over all seeds (or one seed). */
function mean(method, metric, seed = "all") {
  const rows = state.report.seed_reports.filter((x) => seed === "all" || String(x.seed) === seed);
  return rows.reduce((sum, x) => sum + (x.methods[method]?.[metric] || 0), 0) / rows.length;
}

const pct = (value) => `${(value * 100).toFixed(1)}%`;

function renderChart() {
  const el = document.querySelector("#method-chart");
  const values = methods.map((method) => ({ method, value: mean(method, state.metric) }));
  const max = Math.max(...values.map((x) => x.value), 0.01);
  el.innerHTML = values
    .map((x) => {
      const highlight = x.method === "Selective-QE" ? "highlight" : x.method === "Random-Gated-Expansion" ? "control" : "";
      return `<div class="bar-row"><span class="bar-label">${names[x.method]}</span><span class="bar-track"><span class="bar ${highlight}" style="width:${Math.max(3, (x.value / max) * 100)}%"></span></span><span class="bar-value">${pct(x.value)}</span></div>`;
    })
    .join("");
}

function renderTable() {
  const el = document.querySelector("#seed-table");
  const rows = state.report.seed_reports.filter((x) => state.seed === "all" || String(x.seed) === state.seed);
  el.innerHTML =
    `<div class="seed-row head"><span>Seed</span><span>Dense</span><span>SQE</span><span>Δ</span></div>` +
    rows
      .map((x) => {
        const dense = x.methods["Dense-Only"]["recall@5"];
        const sqe = x.methods["Selective-QE"]["recall@5"];
        const delta = (sqe - dense) * 100;
        return `<div class="seed-row"><strong>${x.seed}</strong><span>${pct(dense)}</span><span>${pct(sqe)}</span><span class="metric-delta ${delta >= 0 ? "up" : "down"}">${delta >= 0 ? "+" : ""}${delta.toFixed(1)}</span></div>`;
      })
      .join("");
}

function renderAll() {
  renderChart();
  renderTable();
}

document.querySelector("#metric-select").addEventListener("change", (event) => {
  state.metric = event.target.value;
  renderChart();
});
document.querySelector("#seed-select").addEventListener("change", (event) => {
  state.seed = event.target.value;
  renderTable();
});
document.querySelector("#copy-citation").addEventListener("click", async () => {
  const status = document.querySelector("#copy-status");
  try {
    await navigator.clipboard.writeText(document.querySelector("#citation").textContent);
    status.textContent = "Copied";
  } catch {
    status.textContent = "Select the text to copy";
  }
  setTimeout(() => (status.textContent = ""), 2200);
});

loadData().catch((error) => {
  document.querySelector("#method-chart").innerHTML =
    '<p class="data-note">The released result file could not be loaded in this preview. Use the repository links below to inspect the source JSON.</p>';
  console.error(error);
});
