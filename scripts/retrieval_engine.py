"""
Retrieval Engine
=================
Shared retrieval utilities used by all methods (baselines and proposed).
Loads the frozen FAISS and BM25 indices once and exposes simple search APIs.
"""

import json
import pickle
from pathlib import Path
from typing import Optional

import faiss
import numpy as np
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer


class RetrievalEngine:
    """
    Loads the pre-built Dense and Sparse indices and provides
    search methods for all retrieval pipelines.
    """

    def __init__(self, index_dir: str, embedding_model: str, device: str = "cuda"):
        index_dir = Path(index_dir)

        # Load ID map
        with open(index_dir / "id_map.json") as f:
            self.id_map: list[str] = json.load(f)

        # Load Dense index
        self.faiss_index = faiss.read_index(str(index_dir / "dense.faiss"))

        # Load BM25 index
        with open(index_dir / "bm25.pkl", "rb") as f:
            bm25_data = pickle.load(f)
        self.bm25: BM25Okapi = bm25_data["bm25"]

        # Load embedding model
        self.embed_model = SentenceTransformer(embedding_model, device=device)
        self.embed_model.max_seq_length = 512

    def embed(self, texts: list[str]) -> np.ndarray:
        """Embed a list of texts and return normalized numpy array."""
        return self.embed_model.encode(
            texts,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        ).astype(np.float32)

    def dense_search(self, query: str, top_k: int = 10) -> list[tuple[str, float]]:
        """
        Returns list of (episode_id, score) sorted by descending cosine similarity.
        """
        q_emb = self.embed([query])
        scores, indices = self.faiss_index.search(q_emb, top_k)
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx >= 0:
                results.append((self.id_map[idx], float(score)))
        return results

    def bm25_search(self, query: str, top_k: int = 10) -> list[tuple[str, float]]:
        """
        Returns list of (episode_id, score) sorted by descending BM25 score.
        """
        tokenized_query = query.lower().split()
        scores = self.bm25.get_scores(tokenized_query)
        top_indices = np.argsort(scores)[::-1][:top_k]
        return [(self.id_map[i], float(scores[i])) for i in top_indices]

    def rrf_fusion(
        self,
        ranked_lists: list[list[tuple[str, float]]],
        k: int = 60,
        top_k: int = 10,
    ) -> list[tuple[str, float]]:
        """
        Reciprocal Rank Fusion over multiple ranked lists.
        RRF score = sum(1 / (k + rank_i)) for each list.
        Returns list of (episode_id, rrf_score) sorted descending.
        """
        rrf_scores: dict[str, float] = {}
        for ranked_list in ranked_lists:
            for rank, (ep_id, _) in enumerate(ranked_list, start=1):
                rrf_scores[ep_id] = rrf_scores.get(ep_id, 0.0) + 1.0 / (k + rank)
        sorted_results = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
        return sorted_results[:top_k]

    def get_top_dense_score(self, query: str) -> float:
        """Returns the top cosine similarity score for a query (used for confidence gating)."""
        results = self.dense_search(query, top_k=1)
        return results[0][1] if results else 0.0
