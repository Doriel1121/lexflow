from __future__ import annotations

import pickle
from pathlib import Path
from typing import Any

import faiss

from config import DEFAULT_CONFIG
from indexer.embeddings import EmbeddingEngine
from retrieval.utils import normalize_metadata


class SemanticSearch:
    def __init__(self, config=DEFAULT_CONFIG) -> None:
        self.config = config
        self.embedder = EmbeddingEngine(config.embedding_model, config.batch_size)
        self.index = faiss.read_index(str(config.index_path))
        with Path(config.metadata_path).open("rb") as meta_file:
            self.documents, raw_metadata = pickle.load(meta_file)
        self.metadata = [normalize_metadata(item) for item in raw_metadata]

    def search(self, query: str, k: int = 5) -> list[dict[str, Any]]:
        query_vector = self.embedder.query(query)
        distances, indices = self.index.search(query_vector, k)
        results = []
        for distance, index in zip(distances[0], indices[0]):
            if index < 0 or index >= len(self.documents):
                continue
            results.append(
                {
                    "score": float(distance),
                    "text": self.documents[index],
                    "metadata": self.metadata[index],
                    "source": "semantic",
                }
            )
        return results