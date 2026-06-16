"""
Generate an additional query-sampling seed over an existing memory store.

This keeps the memory index fixed and samples new evaluation targets from the
already indexed memory. It is useful for robustness checks that do not require
rebuilding a 5,000-document embedding index.
"""

import argparse
import json
import random
import shutil
import time
from pathlib import Path

import jsonlines
from openai import OpenAI
from rich.console import Console
from rich.panel import Panel
from tqdm import tqdm


console = Console()

QUERY_GENERATION_PROMPT = """\
You are simulating an AI software engineering agent that has been working on a \
coding task for a long time and needs to recall a past action from its memory.

Below is a raw execution trace from earlier in the agent's trajectory:

--- TRACE ---
{trace}
--- END TRACE ---

Your task: Write ONE natural language question that this agent might ask later \
to retrieve this memory. The question must:
1. Be phrased in plain English, as if the agent is thinking out loud.
2. NOT copy exact technical terms, variable names, or error codes from the trace. \
   Use high-level descriptions instead.
3. Be specific enough that only this trace, or a very similar one, would answer it.
4. Be a single sentence ending with a question mark.

Output ONLY the question, nothing else.
"""


def read_jsonl(path):
    rows = []
    with jsonlines.open(path) as reader:
        rows = list(reader)
    return rows


def write_jsonl(path, rows):
    with jsonlines.open(path, "w") as writer:
        writer.write_all(rows)


def generate_query(client, model, trace):
    prompt = QUERY_GENERATION_PROMPT.format(trace=trace)
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=128,
            temperature=0.7,
            extra_body={"chat_template_kwargs": {"enable_thinking": False}},
        )
        return response.choices[0].message.content.strip()
    except Exception as exc:
        console.print(f"[red]LLM call failed: {exc}[/red]")
        return ""


def main(args):
    source_memory = Path(args.source_memory)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    memory_path = output_dir / "memory_store.jsonl"
    candidates_path = output_dir / "eval_candidates.jsonl"
    eval_path = output_dir / "eval_pairs.jsonl"
    manifest_path = output_dir / "dataset_manifest.json"

    if not source_memory.exists():
        raise FileNotFoundError(source_memory)
    existing_outputs = [
        path for path in [candidates_path, eval_path, manifest_path] if path.exists()
    ]
    if eval_path.exists() and not args.resume:
        raise FileExistsError(f"{eval_path} exists; use --resume or a new output_dir")
    if args.overwrite:
        if existing_outputs:
            raise FileExistsError(
                "--overwrite is disabled for server safety; use a new output_dir "
                f"or --resume. Existing files: {[str(path) for path in existing_outputs]}"
            )
        console.print(
            "[yellow]--overwrite is deprecated and did not delete files.[/yellow]"
        )

    console.print(Panel("Preparing fixed-memory eval seed", style="bold blue"))
    if not memory_path.exists():
        shutil.copy2(source_memory, memory_path)
    memory_rows = read_jsonl(memory_path)
    if len(memory_rows) < args.n_eval:
        raise RuntimeError(f"Need {args.n_eval} memory rows, found {len(memory_rows)}")

    if candidates_path.exists() and not args.overwrite:
        candidates = read_jsonl(candidates_path)
    else:
        rng = random.Random(args.seed)
        candidates = rng.sample(memory_rows, args.n_eval)
        write_jsonl(candidates_path, candidates)

    client = OpenAI(base_url=args.llm_base_url, api_key="EMPTY")
    eval_pairs = read_jsonl(eval_path) if args.resume and eval_path.exists() else []
    completed = {row.get("target_episode_id") for row in eval_pairs}
    failed = 0
    for candidate in tqdm(candidates, desc="Generating queries"):
        if len(eval_pairs) >= args.n_eval:
            break
        if candidate["episode_id"] in completed:
            continue
        query = generate_query(client, args.llm_model, candidate["formatted_text"])
        if not query:
            failed += 1
            continue
        eval_pairs.append(
            {
                "query_id": f"q_{len(eval_pairs):04d}",
                "query": query,
                "target_episode_id": candidate["episode_id"],
                "target_text": candidate["formatted_text"],
            }
        )
        completed.add(candidate["episode_id"])
        if args.checkpoint_every and len(eval_pairs) % args.checkpoint_every == 0:
            write_jsonl(eval_path, eval_pairs)
        time.sleep(0.05)

    write_jsonl(eval_path, eval_pairs)
    manifest = {
        "n_memory": len(memory_rows),
        "n_eval_requested": args.n_eval,
        "n_eval_generated": len(eval_pairs),
        "seed": args.seed,
        "dataset": "SWE-bench/SWE-smith-trajectories",
        "dataset_split": args.dataset_split,
        "eval_source": "memory",
        "memory_source_path": str(source_memory.resolve()),
        "memory_path": str(memory_path.resolve()),
        "eval_candidates_path": str(candidates_path.resolve()),
        "eval_path": str(eval_path.resolve()),
        "llm_base_url": args.llm_base_url,
        "llm_model": args.llm_model,
        "note": "Fixed-memory query-sampling seed; uses the existing indexed memory store.",
    }
    manifest_path.write_text(json.dumps(manifest, indent=2))
    console.print(
        f"[green]Generated {len(eval_pairs)} query pairs ({failed} failed)[/green]"
    )
    console.print(f"[green]Wrote {manifest_path}[/green]")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source_memory", required=True)
    parser.add_argument("--output_dir", required=True)
    parser.add_argument("--n_eval", type=int, default=500)
    parser.add_argument("--seed", type=int, default=43)
    parser.add_argument("--dataset_split", default="tool")
    parser.add_argument("--llm_base_url", default="http://localhost:8000/v1")
    parser.add_argument("--llm_model", default="Qwen3.6-35B-A3B")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--checkpoint_every", type=int, default=25)
    main(parser.parse_args())
