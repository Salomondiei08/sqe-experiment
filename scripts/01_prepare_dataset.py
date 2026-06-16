"""
Step 1: Dataset Preparation
============================
Downloads SWE-smith trajectories from HuggingFace, extracts agent
episodes (Thought + Action + Observation), formats them into the
memory store, and generates natural language queries using the LLM.

Usage:
    python scripts/01_prepare_dataset.py \
        --n_memory 5000 \
        --n_eval 100 \
        --llm_base_url http://localhost:8000/v1 \
        --llm_model Qwen/Qwen3-32B \
        --output_dir data/
"""

import argparse
import json
import random
import re
import time
from pathlib import Path

import jsonlines
from datasets import load_dataset
from openai import OpenAI
from tqdm import tqdm
from rich.console import Console
from rich.panel import Panel

console = Console()

# ---------------------------------------------------------------------------
# Prompt for generating natural language queries from execution traces
# ---------------------------------------------------------------------------
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
   Use high-level descriptions instead (e.g., say "database error" not "psycopg2.OperationalError").
3. Be specific enough that only this trace (or a very similar one) would answer it.
4. Be a single sentence ending with a question mark.

Output ONLY the question, nothing else.
"""


def format_episode(step: dict) -> str:
    """
    Convert a raw trajectory step into the canonical memory format:
      [THOUGHT] ...
      [ACTION] tool_name: command
      [OBSERVATION] output (head + tail truncated)
    """
    parts = []

    thought = step.get("thought", "").strip()
    if thought:
        parts.append(f"[THOUGHT] {thought}")

    tool = step.get("tool", step.get("action", "")).strip()
    command = step.get("command", step.get("tool_input", "")).strip()
    if tool or command:
        parts.append(f"[ACTION] {tool}: {command}" if tool else f"[ACTION] {command}")

    observation = step.get("observation", step.get("output", "")).strip()
    if observation:
        # Head-tail truncation: keep first 300 chars and last 300 chars
        if len(observation) > 700:
            head = observation[:300]
            tail = observation[-300:]
            observation = head + "\n... [truncated] ...\n" + tail
        parts.append(f"[OBSERVATION] {observation}")

    return "\n".join(parts)


def extract_steps_from_trajectory(traj: dict) -> list[dict]:
    """
    Parse a SWE-smith trajectory dict (tool split) into a list of episode steps.
    The 'messages' field is a JSON string with dicts containing:
      role, content, thought, action, tool_calls, message_type
    """
    steps = []
    raw_messages = traj.get("messages", "[]")
    try:
        history = json.loads(raw_messages) if isinstance(raw_messages, str) else raw_messages
    except (json.JSONDecodeError, TypeError):
        return steps

    for i, turn in enumerate(history):
        role = turn.get("role", "")
        if role != "assistant":
            continue

        # thought is a top-level field in this format
        thought = str(turn.get("thought") or "").strip()[:300]

        # tool name + command from tool_calls list
        tool_name = ""
        command = ""
        tool_calls = turn.get("tool_calls") or []
        if tool_calls:
            tc = tool_calls[0]
            fn = tc.get("function", {})
            tool_name = fn.get("name", "")
            try:
                args = json.loads(fn.get("arguments", "{}"))
            except (json.JSONDecodeError, TypeError):
                args = {}
            command = args.get("command", args.get("path", str(args)))

        # observation from the next tool turn
        observation = ""
        if i + 1 < len(history):
            next_turn = history[i + 1]
            if next_turn.get("role") == "tool":
                obs_content = next_turn.get("content", "")
                if isinstance(obs_content, list):
                    obs_content = " ".join(
                        c.get("text", "") for c in obs_content if isinstance(c, dict)
                    )
                observation = str(obs_content)

        if tool_name or command:
            steps.append(
                {
                    "thought": thought,
                    "tool": tool_name,
                    "command": command,
                    "observation": observation,
                }
            )

    return steps


def generate_nl_query(client: OpenAI, model: str, trace: str) -> str:
    """Call the LLM to generate a natural language query for a given trace."""
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
    except Exception as e:
        console.print(f"[red]LLM call failed: {e}[/red]")
        return ""


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with jsonlines.open(path) as reader:
        return list(reader)


def write_jsonl(path: Path, rows: list[dict]) -> None:
    with jsonlines.open(path, "w") as writer:
        writer.write_all(rows)


def main(args):
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    memory_path = output_dir / "memory_store.jsonl"
    eval_path = output_dir / "eval_pairs.jsonl"
    candidates_path = output_dir / "eval_candidates.jsonl"
    manifest_path = output_dir / "dataset_manifest.json"

    if not args.overwrite and memory_path.exists() and candidates_path.exists():
        console.print(Panel("Step 1: Reusing existing sampled dataset", style="bold blue"))
        memory_store = load_jsonl(memory_path)
        eval_candidates = load_jsonl(candidates_path)
        console.print(
            f"Memory store: {len(memory_store)} episodes | "
            f"Eval candidates: {len(eval_candidates)} episodes"
        )
    else:
        if not args.overwrite and (memory_path.exists() or eval_path.exists()):
            raise FileExistsError(
                f"{output_dir} already contains dataset files. Use --overwrite "
                "or choose a new --output_dir."
            )

        console.print(Panel("Step 1: Loading SWE-smith trajectories", style="bold blue"))

        # Load dataset — streaming to avoid downloading everything
        dataset = load_dataset(
            "SWE-bench/SWE-smith-trajectories",
            split=args.dataset_split,
            streaming=True,
        )

        # Collect all episodes from trajectories
        all_episodes = []
        console.print("Extracting episodes from trajectories...")
        required = args.n_memory + args.n_eval
        collect_target = max(required, int(required * args.collection_multiplier))
        for traj in tqdm(dataset, desc="Trajectories"):
            steps = extract_steps_from_trajectory(traj)
            for step in steps:
                formatted = format_episode(step)
                if len(formatted) > 100:  # Skip trivially short episodes
                    all_episodes.append(
                        {
                            "episode_id": f"ep_{len(all_episodes):06d}",
                            "task_id": traj.get("instance_id", "unknown"),
                            "formatted_text": formatted,
                            "raw": step,
                        }
                    )
            if len(all_episodes) >= collect_target:
                break

        if len(all_episodes) < required:
            raise RuntimeError(
                f"Only collected {len(all_episodes)} episodes, need {required}."
            )

        console.print(f"[green]Collected {len(all_episodes)} raw episodes[/green]")

        # Sample the memory store. Evaluation targets must be retrievable, so
        # by default they are drawn from the indexed memory store rather than
        # from held-out episodes.
        random.seed(args.seed)
        random.shuffle(all_episodes)
        memory_store = all_episodes[: args.n_memory]
        if args.eval_source == "memory":
            eval_candidates = random.sample(memory_store, args.n_eval)
        else:
            eval_candidates = all_episodes[args.n_memory : args.n_memory + args.n_eval]

        console.print(
            f"Memory store: {len(memory_store)} episodes | "
            f"Eval candidates: {len(eval_candidates)} episodes"
        )

        write_jsonl(memory_path, memory_store)
        write_jsonl(candidates_path, eval_candidates)
        console.print(f"[green]Memory store saved to {memory_path}[/green]")
        console.print(f"[green]Eval candidates saved to {candidates_path}[/green]")

    # Generate NL queries for evaluation set
    console.print(
        Panel("Step 2: Generating NL queries with LLM", style="bold blue")
    )
    client = OpenAI(base_url=args.llm_base_url, api_key="EMPTY")

    eval_pairs = load_jsonl(eval_path) if args.resume else []
    completed_targets = {p.get("target_episode_id") for p in eval_pairs}
    failed = 0
    for ep in tqdm(eval_candidates, desc="Generating queries"):
        if len(eval_pairs) >= args.n_eval:
            break
        if ep["episode_id"] in completed_targets:
            continue
        query = generate_nl_query(client, args.llm_model, ep["formatted_text"])
        if not query:
            failed += 1
            continue
        eval_pairs.append(
            {
                "query_id": f"q_{len(eval_pairs):04d}",
                "query": query,
                "target_episode_id": ep["episode_id"],
                "target_text": ep["formatted_text"],
            }
        )
        completed_targets.add(ep["episode_id"])
        if args.checkpoint_every and len(eval_pairs) % args.checkpoint_every == 0:
            write_jsonl(eval_path, eval_pairs)
        time.sleep(0.05)  # Small delay to avoid overwhelming the server

    console.print(
        f"[green]Generated {len(eval_pairs)} query pairs "
        f"({failed} failed)[/green]"
    )

    write_jsonl(eval_path, eval_pairs)
    console.print(f"[green]Eval pairs saved to {eval_path}[/green]")

    manifest = {
        "n_memory": len(memory_store),
        "n_eval_requested": args.n_eval,
        "n_eval_generated": len(eval_pairs),
        "seed": args.seed,
        "dataset": "SWE-bench/SWE-smith-trajectories",
        "dataset_split": args.dataset_split,
        "eval_source": args.eval_source,
        "llm_base_url": args.llm_base_url,
        "llm_model": args.llm_model,
        "memory_path": str(memory_path),
        "eval_candidates_path": str(candidates_path),
        "eval_path": str(eval_path),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2))
    console.print(f"[green]Manifest saved to {manifest_path}[/green]")

    # Print a sample to verify quality
    if eval_pairs:
        console.print("\n[bold]Sample eval pair:[/bold]")
        sample = eval_pairs[0]
        console.print(f"  Query: [yellow]{sample['query']}[/yellow]")
        console.print(f"  Target trace (first 200 chars):\n  {sample['target_text'][:200]}")
    else:
        console.print("[red]No eval pairs generated — check LLM connectivity and episode extraction.[/red]")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--n_memory", type=int, default=5000,
                        help="Number of episodes in the memory store")
    parser.add_argument("--n_eval", type=int, default=100,
                        help="Number of evaluation query pairs")
    parser.add_argument("--llm_base_url", type=str,
                        default="http://localhost:8000/v1",
                        help="vLLM server base URL")
    parser.add_argument("--llm_model", type=str,
                        default="Qwen/Qwen3-32B",
                        help="LLM model name served by vLLM")
    parser.add_argument("--output_dir", type=str, default="data/")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed for memory/eval sampling")
    parser.add_argument("--dataset_split", type=str, default="tool")
    parser.add_argument("--eval_source", choices=["memory", "heldout"], default="memory",
                        help="Sample eval targets from indexed memory or held-out episodes")
    parser.add_argument("--collection_multiplier", type=float, default=3.0,
                        help="Collect this multiple of n_memory+n_eval before sampling")
    parser.add_argument("--resume", action="store_true",
                        help="Resume query generation from existing eval_pairs.jsonl")
    parser.add_argument("--overwrite", action="store_true",
                        help="Overwrite existing dataset files in output_dir")
    parser.add_argument("--checkpoint_every", type=int, default=25,
                        help="Save eval_pairs every N generated queries; 0 disables checkpoints")
    args = parser.parse_args()
    main(args)
