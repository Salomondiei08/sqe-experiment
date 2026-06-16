"""
Step 4: Run the Proposed Method — Selective Query-Side Expansion
=================================================================
Implements the core contribution of the paper:

  1. Run Dense retrieval on the original query.
  2. If top-1 cosine score < confidence_threshold → trigger expansion.
  3. Generate K hypothetical execution traces via LLM (HyDE for code).
  4. Generate M paraphrased queries via LLM.
  5. Retrieve with Dense for each expanded query.
  6. Fuse ALL ranked lists (original + expansions) with RRF.
  7. Return top-K results.

The script also supports ablation modes used for paper experiments:
  - selective: confidence-gated trace + paraphrase expansion
  - always_expand: trace + paraphrase expansion for every query
  - traces_only: trace expansion only
  - paraphrases_only: paraphrase expansion only
  - dense_only: dense retrieval through the same runner

Usage:
    python scripts/04_run_proposed_method.py \
        --eval_path data/eval_pairs.jsonl \
        --index_dir index/ \
        --embedding_model BAAI/bge-m3 \
        --device cuda \
        --llm_base_url http://localhost:8000/v1 \
        --llm_model Qwen/Qwen3-32B \
        --confidence_threshold 0.65 \
        --n_hypothetical_traces 2 \
        --n_paraphrases 2 \
        --top_k 5 \
        --results_dir results/
"""

import argparse
import json
import random
import time
from pathlib import Path

import jsonlines
from openai import OpenAI
from tqdm import tqdm
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from retrieval_engine import RetrievalEngine

console = Console()

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

HYPOTHETICAL_TRACE_PROMPT = """\
You are an AI software engineering agent. You are searching your memory for a \
past action that relates to the following question:

"{query}"

Generate a realistic hypothetical execution trace (bash command + output, or \
Python error + traceback) that would be stored in the agent's memory if it had \
already performed the action this question is asking about.

Format your response exactly like this:
[THOUGHT] <brief agent thought>
[ACTION] <tool_name>: <command or code>
[OBSERVATION] <realistic terminal output, error message, or result>

Be specific and realistic. Use exact technical terms, error codes, and file \
paths that would appear in a real software engineering session.
Output ONLY the trace, nothing else.
"""

PARAPHRASE_PROMPT = """\
Rephrase the following question in {n} different ways. Each rephrasing should \
preserve the meaning but use different words and phrasing styles.

Original question: "{query}"

Output ONLY the {n} rephrased questions, one per line, numbered 1. 2. etc.
"""


class SelectiveQueryExpander:
    """
    Implements the Selective Query-Side Expansion method.
    """

    def __init__(
        self,
        engine: RetrievalEngine,
        llm_client: OpenAI,
        llm_model: str,
        confidence_threshold: float = 0.65,
        n_hypothetical_traces: int = 2,
        n_paraphrases: int = 2,
        mode: str = "selective",
        random_expand_rate: float = 0.0,
        seed: int = 42,
        expansion_cache: dict | None = None,
    ):
        self.engine = engine
        self.client = llm_client
        self.model = llm_model
        self.threshold = confidence_threshold
        self.n_traces = n_hypothetical_traces
        self.n_paraphrases = n_paraphrases
        self.mode = mode
        self.random_expand_rate = random_expand_rate
        self.rng = random.Random(seed)
        self.cache = expansion_cache if expansion_cache is not None else {
            "traces": {},
            "paraphrases": {},
        }
        self._current_usage = {
            "llm_calls": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }

    @staticmethod
    def _cache_key(query: str) -> str:
        return query.strip()

    def _reset_usage(self) -> None:
        self._current_usage = {
            "llm_calls": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }

    def _record_usage(self, resp) -> None:
        self._current_usage["llm_calls"] += 1
        usage = getattr(resp, "usage", None)
        if not usage:
            return
        for field in ["prompt_tokens", "completion_tokens", "total_tokens"]:
            value = getattr(usage, field, None)
            if value is not None:
                self._current_usage[field] += int(value)

    def _generate_hypothetical_traces(self, query: str) -> list[str]:
        """Generate N hypothetical execution traces for the query."""
        key = self._cache_key(query)
        traces = list(self.cache.setdefault("traces", {}).get(key, []))
        while len(traces) < self.n_traces:
            try:
                resp = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "user",
                            "content": HYPOTHETICAL_TRACE_PROMPT.format(query=query),
                        }
                    ],
                    max_tokens=256,
                    temperature=0.8,
                    extra_body={"chat_template_kwargs": {"enable_thinking": False}},
                )
                self._record_usage(resp)
                trace = resp.choices[0].message.content.strip()
                if trace:
                    traces.append(trace)
            except Exception as e:
                console.print(f"[red]Trace generation failed: {e}[/red]")
                break
        self.cache["traces"][key] = traces
        return traces[: self.n_traces]

    def _generate_paraphrases(self, query: str) -> list[str]:
        """Generate M paraphrased versions of the query."""
        key = self._cache_key(query)
        cached = list(self.cache.setdefault("paraphrases", {}).get(key, []))
        if len(cached) >= self.n_paraphrases:
            return cached[: self.n_paraphrases]
        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": PARAPHRASE_PROMPT.format(
                            n=self.n_paraphrases, query=query
                        ),
                    }
                ],
                max_tokens=256,
                temperature=0.5,
                extra_body={"chat_template_kwargs": {"enable_thinking": False}},
            )
            self._record_usage(resp)
            raw = resp.choices[0].message.content.strip()
            # Parse numbered list
            lines = [
                line.split(". ", 1)[-1].strip()
                for line in raw.split("\n")
                if line.strip() and line[0].isdigit()
            ]
            merged = (cached + lines)[: self.n_paraphrases]
            self.cache["paraphrases"][key] = merged
            return merged
        except Exception as e:
            console.print(f"[red]Paraphrase generation failed: {e}[/red]")
            return cached[: self.n_paraphrases]

    def retrieve(
        self, query: str, top_k: int = 5
    ) -> tuple[list[tuple[str, float]], dict]:
        """
        Main retrieval method.
        Returns (results, metadata) where metadata contains diagnostics.
        """
        metadata = {
            "query": query,
            "mode": self.mode,
            "expanded": False,
            "top1_score_before_expansion": 0.0,
            "n_hypothetical_traces_generated": 0,
            "n_paraphrases_generated": 0,
            "n_ranked_lists_fused": 1,
            "llm_calls": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }
        self._reset_usage()

        # Step 1: Dense retrieval on original query
        original_dense = self.engine.dense_search(query, top_k=top_k * 2)
        top1_score = original_dense[0][1] if original_dense else 0.0
        metadata["top1_score_before_expansion"] = top1_score

        if self.mode == "dense_only":
            return original_dense[:top_k], metadata

        should_expand = False
        if self.mode == "selective":
            should_expand = top1_score < self.threshold
        elif self.mode in ("always_expand", "traces_only", "paraphrases_only"):
            should_expand = True
        elif self.mode == "random_budget":
            should_expand = self.rng.random() < self.random_expand_rate
        else:
            raise ValueError(f"Unknown mode: {self.mode}")

        # Step 2: Gate
        if not should_expand:
            # High confidence — return dense results directly (no expansion cost)
            metadata["expanded"] = False
            return original_dense[:top_k], metadata

        # Low confidence — trigger expansion
        metadata["expanded"] = True
        all_ranked_lists = [original_dense]

        # Step 3: Generate and retrieve hypothetical traces
        hyp_traces = []
        if self.mode != "paraphrases_only":
            hyp_traces = self._generate_hypothetical_traces(query)
        metadata["n_hypothetical_traces_generated"] = len(hyp_traces)

        for trace in hyp_traces:
            # Dense retrieval on hypothetical trace
            trace_dense = self.engine.dense_search(trace, top_k=top_k * 2)
            all_ranked_lists.append(trace_dense)
            # BM25 retrieval on hypothetical trace (key: exact term matching)
            trace_bm25 = self.engine.bm25_search(trace, top_k=top_k * 2)
            all_ranked_lists.append(trace_bm25)

        # Step 4: Generate and retrieve paraphrases
        paraphrases = []
        if self.mode != "traces_only":
            paraphrases = self._generate_paraphrases(query)
        metadata["n_paraphrases_generated"] = len(paraphrases)

        for para in paraphrases:
            para_dense = self.engine.dense_search(para, top_k=top_k * 2)
            all_ranked_lists.append(para_dense)

        metadata["n_ranked_lists_fused"] = len(all_ranked_lists)
        metadata.update(self._current_usage)

        # Step 5: RRF fusion
        fused = self.engine.rrf_fusion(all_ranked_lists, top_k=top_k)
        return fused, metadata


def main(args):
    results_dir = Path(args.results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)

    console.print(Panel("Loading eval pairs and index", style="bold blue"))
    eval_pairs = []
    with jsonlines.open(args.eval_path) as reader:
        eval_pairs = list(reader)
    console.print(f"Loaded {len(eval_pairs)} eval pairs")
    if args.max_queries:
        eval_pairs = eval_pairs[: args.max_queries]
        console.print(f"Using first {len(eval_pairs)} eval pairs due to --max_queries")

    engine = RetrievalEngine(
        index_dir=args.index_dir,
        embedding_model=args.embedding_model,
        device=args.device,
    )
    llm_client = OpenAI(base_url=args.llm_base_url, api_key="EMPTY")
    expansion_cache = {"traces": {}, "paraphrases": {}}
    cache_path = Path(args.expansion_cache) if args.expansion_cache else None
    if cache_path and cache_path.exists():
        with open(cache_path) as f:
            expansion_cache = json.load(f)

    expander = SelectiveQueryExpander(
        engine=engine,
        llm_client=llm_client,
        llm_model=args.llm_model,
        confidence_threshold=args.confidence_threshold,
        n_hypothetical_traces=args.n_hypothetical_traces,
        n_paraphrases=args.n_paraphrases,
        mode=args.mode,
        random_expand_rate=args.random_expand_rate,
        seed=args.seed,
        expansion_cache=expansion_cache,
    )

    console.print(
        Panel(
            f"Running Selective Query-Side Expansion\n"
            f"  Mode: {args.mode}\n"
            f"  Confidence threshold: {args.confidence_threshold}\n"
            f"  Hypothetical traces per query: {args.n_hypothetical_traces}\n"
            f"  Paraphrases per query: {args.n_paraphrases}",
            style="bold magenta",
        )
    )

    hits_1, hits_k = 0, 0
    n_expanded = 0
    detailed = []

    for pair in tqdm(eval_pairs, desc="SQE Method"):
        query = pair["query"]
        target_id = pair["target_episode_id"]

        started = time.perf_counter()
        results, meta = expander.retrieve(query, top_k=args.top_k)
        meta["elapsed_seconds"] = time.perf_counter() - started
        meta["estimated_llm_calls"] = (
            meta.get("n_hypothetical_traces_generated", 0)
            + (1 if meta.get("n_paraphrases_generated", 0) else 0)
        )
        retrieved_ids = [ep_id for ep_id, _ in results]

        h1 = target_id in retrieved_ids[:1]
        hk = target_id in retrieved_ids
        hits_1 += int(h1)
        hits_k += int(hk)
        if meta["expanded"]:
            n_expanded += 1

        detailed.append(
            {
                "query_id": pair["query_id"],
                "query": query,
                "target_id": target_id,
                "retrieved_ids": retrieved_ids,
                "hit@1": h1,
                f"hit@{args.top_k}": hk,
                "meta": meta,
            }
        )
        time.sleep(0.02)

    n = len(eval_pairs)
    recall_1 = hits_1 / n
    recall_k = hits_k / n
    expansion_rate = n_expanded / n
    avg_latency = sum(d["meta"].get("elapsed_seconds", 0.0) for d in detailed) / n
    avg_llm_calls = sum(d["meta"].get("estimated_llm_calls", 0) for d in detailed) / n
    avg_actual_llm_calls = sum(d["meta"].get("llm_calls", 0) for d in detailed) / n
    avg_prompt_tokens = sum(d["meta"].get("prompt_tokens", 0) for d in detailed) / n
    avg_completion_tokens = sum(d["meta"].get("completion_tokens", 0) for d in detailed) / n
    avg_total_tokens = sum(d["meta"].get("total_tokens", 0) for d in detailed) / n

    # Print results
    table = Table(title="Proposed Method Results", show_header=True)
    table.add_column("Metric", style="bold")
    table.add_column("Value", justify="right")
    table.add_row("Recall@1", f"{recall_1:.3f}")
    table.add_row(f"Recall@{args.top_k}", f"{recall_k:.3f}")
    table.add_row("Expansion Trigger Rate", f"{expansion_rate:.1%}")
    table.add_row("Queries Expanded", f"{n_expanded}/{n}")
    table.add_row("Avg Latency (s/query)", f"{avg_latency:.2f}")
    table.add_row("Avg LLM Calls/query", f"{avg_llm_calls:.2f}")
    if avg_actual_llm_calls or avg_total_tokens:
        table.add_row("Avg Actual LLM Calls/query", f"{avg_actual_llm_calls:.2f}")
        table.add_row("Avg Prompt Tokens/query", f"{avg_prompt_tokens:.1f}")
        table.add_row("Avg Completion Tokens/query", f"{avg_completion_tokens:.1f}")
        table.add_row("Avg Total Tokens/query", f"{avg_total_tokens:.1f}")
    console.print(table)

    # Save results
    method_names = {
        "selective": "Selective-QE",
        "always_expand": "Always-Expand",
        "traces_only": "HyDE-Traces-Only",
        "paraphrases_only": "Paraphrases-Only",
        "dense_only": "Dense-Only-Runner",
        "random_budget": "Random-Gated-Expansion",
    }
    summary = {
        "method": method_names.get(args.mode, args.mode),
        "recall@1": recall_1,
        f"recall@{args.top_k}": recall_k,
        "expansion_trigger_rate": expansion_rate,
        "n_expanded": n_expanded,
        "n_queries": n,
        "avg_latency_seconds_per_query": avg_latency,
        "avg_estimated_llm_calls_per_query": avg_llm_calls,
        "avg_actual_llm_calls_per_query": avg_actual_llm_calls,
        "avg_prompt_tokens_per_query": avg_prompt_tokens,
        "avg_completion_tokens_per_query": avg_completion_tokens,
        "avg_total_tokens_per_query": avg_total_tokens,
        "config": {
            "confidence_threshold": args.confidence_threshold,
            "n_hypothetical_traces": args.n_hypothetical_traces,
            "n_paraphrases": args.n_paraphrases,
            "mode": args.mode,
            "random_expand_rate": args.random_expand_rate,
            "seed": args.seed,
        },
    }
    if args.output_tag:
        summary_name = f"{args.output_tag}_summary.json"
        detail_name = f"{args.output_tag}_detailed.jsonl"
        summary["method"] = f"{summary['method']} ({args.output_tag})"
    else:
        summary_name = "proposed_summary.json" if args.mode == "selective" else f"{args.mode}_summary.json"
        detail_name = "proposed_detailed.jsonl" if args.mode == "selective" else f"{args.mode}_detailed.jsonl"
    with open(results_dir / summary_name, "w") as f:
        json.dump(summary, f, indent=2)

    with jsonlines.open(results_dir / detail_name, "w") as w:
        w.write_all(detailed)

    if cache_path:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_path, "w") as f:
            json.dump(expander.cache, f, indent=2)

    console.print(f"[green]Results saved to {results_dir}[/green]")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--eval_path", type=str, default="data/eval_pairs.jsonl")
    parser.add_argument("--index_dir", type=str, default="index/")
    parser.add_argument("--embedding_model", type=str, default="BAAI/bge-m3")
    parser.add_argument("--device", type=str, default="cuda")
    parser.add_argument("--llm_base_url", type=str, default="http://localhost:8000/v1")
    parser.add_argument("--llm_model", type=str, default="Qwen/Qwen3-32B")
    parser.add_argument("--confidence_threshold", type=float, default=0.65)
    parser.add_argument("--n_hypothetical_traces", type=int, default=2)
    parser.add_argument("--n_paraphrases", type=int, default=2)
    parser.add_argument("--mode", type=str, default="selective",
                        choices=[
                            "selective",
                            "always_expand",
                            "traces_only",
                            "paraphrases_only",
                            "dense_only",
                            "random_budget",
                        ])
    parser.add_argument("--random_expand_rate", type=float, default=0.0,
                        help="Expansion probability for random_budget mode")
    parser.add_argument("--expansion_cache", type=str, default="",
                        help="Optional JSON cache for generated traces and paraphrases")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max_queries", type=int, default=0,
                        help="Optional limit for pilot runs; 0 uses all eval pairs")
    parser.add_argument("--output_tag", type=str, default="",
                        help="Optional output tag to avoid overwriting main results")
    parser.add_argument("--top_k", type=int, default=5)
    parser.add_argument("--results_dir", type=str, default="results/")
    args = parser.parse_args()
    main(args)
