"""
Step 3: Run Baseline Retrieval Methods
========================================
Evaluates three baselines on the eval_pairs dataset:
  1. Dense-only (BGE-M3 cosine similarity)
  2. BM25-only (sparse keyword retrieval)
  3. Hybrid (Dense + BM25 fused with RRF, no query expansion)

All three methods use the exact same frozen memory index.

Usage:
    python scripts/03_run_baselines.py \
        --eval_path data/eval_pairs.jsonl \
        --index_dir index/ \
        --embedding_model BAAI/bge-m3 \
        --device cuda \
        --top_k 5 \
        --results_dir results/
"""

import argparse
import json
from pathlib import Path

import jsonlines
from tqdm import tqdm
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from retrieval_engine import RetrievalEngine

console = Console()


def recall_at_k(retrieved_ids: list[str], target_id: str) -> bool:
    """Returns True if target_id is in the retrieved list."""
    return target_id in retrieved_ids


def run_method(
    method_name: str,
    eval_pairs: list[dict],
    engine: RetrievalEngine,
    top_k: int,
    retrieve_fn,
) -> dict:
    """Generic runner for any retrieval method."""
    hits_1, hits_5 = 0, 0
    detailed = []

    for pair in tqdm(eval_pairs, desc=method_name):
        query = pair["query"]
        target_id = pair["target_episode_id"]

        results = retrieve_fn(query, top_k)
        retrieved_ids = [ep_id for ep_id, _ in results]

        h1 = recall_at_k(retrieved_ids[:1], target_id)
        h5 = recall_at_k(retrieved_ids[:top_k], target_id)
        hits_1 += int(h1)
        hits_5 += int(h5)

        detailed.append(
            {
                "query_id": pair["query_id"],
                "query": query,
                "target_id": target_id,
                "retrieved_ids": retrieved_ids,
                "hit@1": h1,
                f"hit@{top_k}": h5,
            }
        )

    n = len(eval_pairs)
    return {
        "method": method_name,
        "recall@1": hits_1 / n,
        f"recall@{top_k}": hits_5 / n,
        "n_queries": n,
        "detailed": detailed,
    }


def main(args):
    results_dir = Path(args.results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)

    console.print(Panel("Loading eval pairs and index", style="bold blue"))
    eval_pairs = []
    with jsonlines.open(args.eval_path) as reader:
        eval_pairs = list(reader)
    console.print(f"Loaded {len(eval_pairs)} eval pairs")

    engine = RetrievalEngine(
        index_dir=args.index_dir,
        embedding_model=args.embedding_model,
        device=args.device,
    )
    console.print("[green]Retrieval engine loaded[/green]")

    all_results = []

    # -----------------------------------------------------------------------
    # Baseline 1: Dense-only
    # -----------------------------------------------------------------------
    console.print(Panel("Baseline 1: Dense Retrieval (BGE-M3)", style="bold yellow"))
    dense_results = run_method(
        method_name="Dense-Only",
        eval_pairs=eval_pairs,
        engine=engine,
        top_k=args.top_k,
        retrieve_fn=lambda q, k: engine.dense_search(q, top_k=k),
    )
    all_results.append(dense_results)

    # -----------------------------------------------------------------------
    # Baseline 2: BM25-only
    # -----------------------------------------------------------------------
    console.print(Panel("Baseline 2: BM25 Sparse Retrieval", style="bold yellow"))
    bm25_results = run_method(
        method_name="BM25-Only",
        eval_pairs=eval_pairs,
        engine=engine,
        top_k=args.top_k,
        retrieve_fn=lambda q, k: engine.bm25_search(q, top_k=k),
    )
    all_results.append(bm25_results)

    # -----------------------------------------------------------------------
    # Baseline 3: Hybrid (Dense + BM25 with RRF, NO expansion)
    # -----------------------------------------------------------------------
    console.print(Panel("Baseline 3: Hybrid Dense+BM25 with RRF", style="bold yellow"))

    def hybrid_retrieve(query: str, top_k: int) -> list[tuple[str, float]]:
        dense = engine.dense_search(query, top_k=top_k * 2)
        sparse = engine.bm25_search(query, top_k=top_k * 2)
        return engine.rrf_fusion([dense, sparse], top_k=top_k)

    hybrid_results = run_method(
        method_name="Hybrid-RRF",
        eval_pairs=eval_pairs,
        engine=engine,
        top_k=args.top_k,
        retrieve_fn=hybrid_retrieve,
    )
    all_results.append(hybrid_results)

    # -----------------------------------------------------------------------
    # Print results table
    # -----------------------------------------------------------------------
    table = Table(title="Baseline Results", show_header=True)
    table.add_column("Method", style="bold")
    table.add_column("Recall@1", justify="right")
    table.add_column(f"Recall@{args.top_k}", justify="right")

    for r in all_results:
        table.add_row(
            r["method"],
            f"{r['recall@1']:.3f}",
            f"{r[f'recall@{args.top_k}']:.3f}",
        )
    console.print(table)

    # Save results
    summary = [
        {
            "method": r["method"],
            "recall@1": r["recall@1"],
            f"recall@{args.top_k}": r[f"recall@{args.top_k}"],
            "n_queries": r["n_queries"],
        }
        for r in all_results
    ]
    with open(results_dir / "baselines_summary.json", "w") as f:
        json.dump(summary, f, indent=2)

    for r in all_results:
        method_slug = r["method"].lower().replace("-", "_").replace("+", "_")
        with jsonlines.open(results_dir / f"{method_slug}_detailed.jsonl", "w") as w:
            w.write_all(r["detailed"])

    console.print(f"[green]Results saved to {results_dir}[/green]")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--eval_path", type=str, default="data/eval_pairs.jsonl")
    parser.add_argument("--index_dir", type=str, default="index/")
    parser.add_argument("--embedding_model", type=str, default="BAAI/bge-m3")
    parser.add_argument("--device", type=str, default="cuda")
    parser.add_argument("--top_k", type=int, default=5)
    parser.add_argument("--results_dir", type=str, default="results/")
    args = parser.parse_args()
    main(args)
