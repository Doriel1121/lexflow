from __future__ import annotations

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer


class EmbeddingEngine:
    def __init__(self, model_name: str, batch_size: int = 64) -> None:
        self.model = SentenceTransformer(model_name)
        self.batch_size = batch_size

    def encode(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.empty((0, self.model.get_sentence_embedding_dimension()), dtype=np.float32)

        vectors = []
        for start in range(0, len(texts), self.batch_size):
            end = min(start + self.batch_size, len(texts))
            batch = texts[start:end]
            batch_vectors = self.model.encode(batch, convert_to_numpy=True, show_progress_bar=False)
            vectors.append(batch_vectors.astype(np.float32))

        return np.vstack(vectors).astype(np.float32)

    def build_index(self, embeddings: np.ndarray) -> faiss.IndexFlatL2:
        if embeddings.size == 0:
            embeddings = np.empty((0, self.model.get_sentence_embedding_dimension()), dtype=np.float32)
        index = faiss.IndexFlatL2(embeddings.shape[1])
        index.add(embeddings)
        return index

    def query(self, text: str) -> np.ndarray:
        vector = self.model.encode([text], convert_to_numpy=True, show_progress_bar=False)
        return vector.astype(np.float32)