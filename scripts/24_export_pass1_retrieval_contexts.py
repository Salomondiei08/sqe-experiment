"""
Export method-specific retrieved-memory contexts for downstream Pass@1 runs.

This script does not run agents, does not verify patches, and does not create
Pass@1 results. It prepares auditable context packets that a SWE-bench runner
can inject into prompts before running real task-success evaluations.
"""

import argparse
import csv
import importlib.util
import json
import sys
from pathlib import Path

from openai import OpenAI

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[0]
sys.path.insert(0, str(SCRIPT_DIR))

from retrieval_engine import RetrievalEngine  # noqa: E402


def load_proposed_module():
    path = SCRIPT_DIR / "04_run_proposed_method.py"
    spec = importlib.util.spec_from_file_location("sqe_proposed_method", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load proposed-method module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_json(path):
    with open(path) as f:
        return json.load(f)


def read_jsonl(path):
    rows = []
    with open(path) as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def count_jsonl_rows(path):
    if not path.exists():
        return 0
    n_rows = 0
    with open(path) as f:
        for line in f:
            if line.strip():
                n_rows += 1
    return n_rows


def existing_task_ids(path, method):
    if not path.exists():
        return set()
    return {
        row["task_id"]
        for row in read_jsonl(path)
        if row.get("method") == method and row.get("task_id")
    }


def write_cache(cache_path, cache):
    if not cache_path:
        return
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(cache, indent=2, sort_keys=True) + "\n")


def load_memory(memory_path):
    memory = {}
    for row in read_jsonl(memory_path):
        episode_id = row.get("episode_id")
        if episode_id:
            memory[episode_id] = row
    return memory


def load_tasks(path):
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".jsonl":
        rows = read_jsonl(path)
    elif suffix == ".json":
        data = read_json(path)
        rows = data if isinstance(data, list) else data.get("tasks", [])
    elif suffix == ".csv":
        with open(path, newline="") as f:
            rows = list(csv.DictReader(f))
    elif suffix == ".parquet":
        try:
            import pandas as pd
        except ImportError as exc:
            raise SystemExit("pandas is required to read parquet task files") from exc
        rows = pd.read_parquet(path).to_dict("records")
    else:
        raise SystemExit(f"unsupported task file extension: {path}")

    tasks = []
    for i, row in enumerate(rows):
        task_id = (
            row.get("task_id")
            or row.get("instance_id")
            or row.get("name")
            or row.get("id")
            or f"task_{i:04d}"
        )
        problem = (
            row.get("problem_statement")
            or row.get("problem")
            or row.get("query")
            or row.get("description")
            or ""
        )
        repo = row.get("repo", "")
        if not str(problem).strip():
            continue
        tasks.append(
            {
                "task_id": str(task_id),
                "repo": str(repo) if repo is not None else "",
                "problem_statement": str(problem),
            }
        )
    return tasks


def method_label(mode):
    return {
        "dense_only": "Dense-Only",
        "selective": "Selective-QE",
        "always_expand": "Always-Expand",
        "traces_only": "HyDE-Traces-Only",
        "paraphrases_only": "Paraphrases-Only",
        "random_budget": "Random-Gated-Expansion",
    }[mode]


def make_query(task, query_template):
    return query_template.format(
        task_id=task["task_id"],
        repo=task.get("repo", ""),
        problem_statement=task["problem_statement"],
    )


def context_text(task, memories):
    lines = [
        "## Retrieved Prior Agent Memories",
        "",
        "The following entries are retrieved from prior software-agent memory logs.",
        "Use them only when they are relevant to the current bug.",
        "",
    ]
    for i, item in enumerate(memories, start=1):
        lines.extend(
            [
                f"### Memory {i}: {item['episode_id']}",
                f"Task ID: {item.get('task_id', '')}",
                item.get("formatted_text", ""),
                "",
            ]
        )
    return "\n".join(lines).strip()


def verify_embedding_dimension(engine, query):
    embedding = engine.embed([query])
    embed_dim = int(embedding.shape[1])
    index_dim = int(engine.faiss_index.d)
    if embed_dim != index_dim:
        raise SystemExit(
            "embedding model dimension does not match FAISS index: "
            f"model_dim={embed_dim}, index_dim={index_dim}. "
            "Use the same embedding model that built the index."
        )


def main(args):
    tasks = load_tasks(args.task_file)
    if args.max_tasks:
        tasks = tasks[: args.max_tasks]
    if not tasks:
        raise SystemExit("no tasks with problem statements found")

    memory = load_memory(args.memory_path)
    if not memory:
        raise SystemExit(f"no memory rows found: {args.memory_path}")

    engine = RetrievalEngine(
        index_dir=args.index_dir,
        embedding_model=args.embedding_model,
        device=args.device,
    )
    verify_embedding_dimension(
        engine,
        make_query(tasks[0], args.query_template),
    )
    proposed = load_proposed_module()
    cache_path = Path(args.expansion_cache) if args.expansion_cache else None
    expansion_cache = {"traces": {}, "paraphrases": {}}
    if cache_path and cache_path.exists():
        expansion_cache = read_json(cache_path)

    llm_client = OpenAI(base_url=args.llm_base_url, api_key=args.llm_api_key)
    expander = proposed.SelectiveQueryExpander(
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

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    label = method_label(args.mode)
    slug = label.lower().replace("-", "_").replace("@", "at").replace(" ", "_")
    output_path = output_dir / f"{slug}_contexts.jsonl"
    manifest_path = output_dir / f"{slug}_manifest.json"

    seen_task_ids = existing_task_ids(output_path, label) if args.resume else set()
    write_mode = "a" if args.resume and output_path.exists() else "w"
    processed = 0
    skipped = 0
    cache_every = max(args.cache_flush_every, 1)

    output_f = open(output_path, write_mode)
    for task in tasks:
        if task["task_id"] in seen_task_ids:
            skipped += 1
            continue
        query = make_query(task, args.query_template)
        results, meta = expander.retrieve(query, top_k=args.top_k)
        memories = []
        missing_ids = []
        for episode_id, score in results:
            source = memory.get(episode_id)
            if not source:
                missing_ids.append(episode_id)
                continue
            memories.append(
                {
                    "episode_id": episode_id,
                    "score": score,
                    "task_id": source.get("task_id", ""),
                    "formatted_text": source.get("formatted_text", ""),
                }
            )
        row = {
            "task_id": task["task_id"],
            "repo": task.get("repo", ""),
            "method": label,
            "query": query,
            "retrieved_memories": memories,
            "missing_retrieved_ids": missing_ids,
            "context_text": context_text(task, memories),
            "retrieval_meta": meta,
        }
        output_f.write(json.dumps(row, sort_keys=True) + "\n")
        output_f.flush()
        processed += 1
        if processed % cache_every == 0:
            write_cache(cache_path, expander.cache)

    output_f.close()
    write_cache(cache_path, expander.cache)
    n_output_rows = count_jsonl_rows(output_path)

    manifest = {
        "artifact_type": "pass1_retrieval_contexts",
        "is_pass1_result": False,
        "note": (
            "Context packet only. It must be injected into a real downstream "
            "agent run and verified before any Pass@1 claim is made."
        ),
        "method": label,
        "mode": args.mode,
        "task_file": str(Path(args.task_file).resolve()),
        "memory_path": str(Path(args.memory_path).resolve()),
        "index_dir": str(Path(args.index_dir).resolve()),
        "output_path": str(output_path.resolve()),
        "n_tasks": n_output_rows,
        "top_k": args.top_k,
        "config": {
            "embedding_model": args.embedding_model,
            "device": args.device,
            "confidence_threshold": args.confidence_threshold,
            "n_hypothetical_traces": args.n_hypothetical_traces,
            "n_paraphrases": args.n_paraphrases,
            "random_expand_rate": args.random_expand_rate,
            "seed": args.seed,
            "query_template": args.query_template,
        },
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "output": str(output_path),
                "manifest": str(manifest_path),
                "n_tasks": n_output_rows,
                "processed": processed,
                "skipped_existing": skipped,
                "resume": args.resume,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--task_file", required=True)
    parser.add_argument("--memory_path", default="/home/nlp-07/sqe_experiment/data_500_memory_seed42/memory_store.jsonl")
    parser.add_argument("--index_dir", default="/home/nlp-07/sqe_experiment/index_500_seed42")
    parser.add_argument("--embedding_model", default="BAAI/bge-m3")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--llm_base_url", default="http://localhost:8000/v1")
    parser.add_argument("--llm_api_key", default="EMPTY")
    parser.add_argument("--llm_model", default="Qwen3.6-35B-A3B")
    parser.add_argument("--confidence_threshold", type=float, default=0.65)
    parser.add_argument("--n_hypothetical_traces", type=int, default=2)
    parser.add_argument("--n_paraphrases", type=int, default=2)
    parser.add_argument(
        "--mode",
        default="dense_only",
        choices=[
            "dense_only",
            "selective",
            "always_expand",
            "traces_only",
            "paraphrases_only",
            "random_budget",
        ],
    )
    parser.add_argument("--random_expand_rate", type=float, default=0.0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--top_k", type=int, default=5)
    parser.add_argument("--max_tasks", type=int, default=0)
    parser.add_argument("--expansion_cache", default="")
    parser.add_argument("--cache_flush_every", type=int, default=10)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--output_dir", default="/home/nlp-07/sqe_experiment/pass1_contexts")
    parser.add_argument(
        "--query_template",
        default="{repo}\n\n{problem_statement}",
        help="Python format string using task_id, repo, and problem_statement.",
    )
    raise SystemExit(main(parser.parse_args()))
