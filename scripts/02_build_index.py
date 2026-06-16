"""
Step 2: Build the Memory Index
================================
Builds two indices over the memory store:
  1. Dense FAISS index using BGE-M3 embeddings
  2. Sparse BM25 index using rank-bm25

Both indices use the exact same formatted_text from the memory store.
This is the frozen, shared index that ALL retrieval methods will use.

Usage:
    python scripts/02_build_index.py \
        --memory_path data/memory_store.jsonl \
        --index_dir index/ \
        --embedding_model BAAI/bge-m3 \
        --device cuda \
        --batch_size 64
"""

import argparse
import pickle
from pathlib import Path

import faiss
import jsonlines
import numpy as np
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer
from tqdm import tqdm
from rich.console import Console
from rich.panel import Panel

console = Console()


def load_memory_store(path: str) -> tuple[list[str], list[str]]:
    """Returns (episode_ids, formatted_texts)."""
    ids, texts = [], []
    with jsonlines.open(path) as reader:
        for ep in reader:
            ids.append(ep["episode_id"])
            texts.append(ep["formatted_text"])
    return ids, texts


def build_dense_index(
    texts: list[str],
    model_name: str,
    device: str,
    batch_size: int,
    index_dir: Path,
) -> None:
    """Embed all texts with BGE-M3 and save a FAISS flat L2 index."""
    console.print(Panel(f"Building Dense Index with {model_name}", style="bold green"))

    model = SentenceTransformer(model_name, device=device)
    model.max_seq_length = 512

    console.print(f"Embedding {len(texts)} texts in batches of {batch_size}...")
    embeddings = model.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=True,
        normalize_embeddings=True,  # Cosine similarity via inner product
        convert_to_numpy=True,
    )

    dim = embeddings.shape[1]
    console.print(f"Embedding dimension: {dim}")

    # Build FAISS index (Inner Product = Cosine after normalization)
    index = faiss.IndexFlatIP(dim)
    index.add(embeddings.astype(np.float32))
    console.print(f"[green]FAISS index built: {index.ntotal} vectors[/green]")

    # Save index and embeddings
    faiss.write_index(index, str(index_dir / "dense.faiss"))
    np.save(str(index_dir / "dense_embeddings.npy"), embeddings)
    console.print(f"[green]Dense index saved to {index_dir / 'dense.faiss'}[/green]")

    return model  # Return model for reuse during retrieval


def build_bm25_index(
    texts: list[str],
    index_dir: Path,
) -> None:
    """Tokenize texts and build a BM25Okapi index."""
    console.print(Panel("Building Sparse BM25 Index", style="bold green"))

    # Simple whitespace tokenizer — good enough for code/bash text
    tokenized = [text.lower().split() for text in tqdm(texts, desc="Tokenizing")]

    bm25 = BM25Okapi(tokenized)
    console.print(f"[green]BM25 index built over {len(tokenized)} documents[/green]")

    with open(index_dir / "bm25.pkl", "wb") as f:
        pickle.dump({"bm25": bm25, "tokenized_corpus": tokenized}, f)
    console.print(f"[green]BM25 index saved to {index_dir / 'bm25.pkl'}[/green]")


def main(args):
    index_dir = Path(args.index_dir)
    index_dir.mkdir(parents=True, exist_ok=True)

    console.print(Panel("Loading memory store", style="bold blue"))
    ids, texts = load_memory_store(args.memory_path)
    console.print(f"Loaded {len(texts)} episodes")

    # Save the ID mapping so retrieval can map index positions back to episode IDs
    import json
    with open(index_dir / "id_map.json", "w") as f:
        json.dump(ids, f)
    console.print(f"[green]ID map saved ({len(ids)} entries)[/green]")

    # Build both indices
    build_dense_index(texts, args.embedding_model, args.device, args.batch_size, index_dir)
    build_bm25_index(texts, index_dir)

    console.print(Panel("[bold green]All indices built successfully![/bold green]"))
    console.print(
        f"\nIndex directory contents:\n"
        f"  dense.faiss       — FAISS inner-product index\n"
        f"  dense_embeddings.npy — Raw embeddings (for debugging)\n"
        f"  bm25.pkl          — BM25Okapi index\n"
        f"  id_map.json       — Maps FAISS position → episode_id\n"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--memory_path", type=str, default="data/memory_store.jsonl")
    parser.add_argument("--index_dir", type=str, default="index/")
    parser.add_argument("--embedding_model", type=str, default="BAAI/bge-m3")
    parser.add_argument("--device", type=str, default="cuda")
    parser.add_argument("--batch_size", type=int, default=64)
    args = parser.parse_args()
    main(args)
