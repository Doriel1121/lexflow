from __future__ import annotations

import pickle
from dataclasses import asdict
from pathlib import Path
from typing import Iterable

import faiss
import numpy as np

from config import DEFAULT_CONFIG, AppConfig
from indexer.cache import CachedFileRecord, IndexCache, file_signature
from indexer.chunking import parse_file
from indexer.embeddings import EmbeddingEngine
from indexer.graph_builder import DependencyGraphBuilder
from indexer.metadata import SourceChunkMetadata, build_metadata, hash_text


def iter_project_files(config: AppConfig) -> Iterable[Path]:
    for path in config.project_path.rglob("*"):
        if not path.is_file():
            continue
        parts = set(path.parts)
        if any(banned in parts for banned in config.banned_dirs):
            continue
        name = path.name.lower()
        suffix = path.suffix.lower()
        if name in {"dockerfile", ".env"} or suffix in config.allowed_extensions:
            yield path


def process_file(path: Path, config: AppConfig, embedder: EmbeddingEngine) -> tuple[list[str], list[dict], np.ndarray]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    parsed_chunks = parse_file(str(path), text, config.chunk_size, config.chunk_overlap)
    file_hash = hash_text(text)
    documents = [chunk.text for chunk in parsed_chunks]
    metadata = [build_metadata(str(path), chunk, text, file_hash).to_dict() for chunk in parsed_chunks]
    embeddings = embedder.encode(documents)
    return documents, metadata, embeddings


def index_project(config: AppConfig = DEFAULT_CONFIG) -> None:
    cache = IndexCache(config.cache_path)
    cache.load()
    embedder = EmbeddingEngine(config.embedding_model, config.batch_size)

    all_documents: list[str] = []
    all_metadata: list[dict] = []
    all_embeddings: list[np.ndarray] = []
    present_paths: set[str] = set()

    print(f"Scanning project files under: {config.project_path}")
    for path in iter_project_files(config):
        path_string = str(path)
        present_paths.add(path_string)
        try:
            signature = file_signature(path)
        except OSError:
            continue

        cached = cache.get(path_string, signature)
        if cached:
            print(f"Cache hit: {path_string}")
            documents = cached.get("chunks", [])
            metadata = cached.get("metadata", [])
            embeddings = np.array(cached.get("embeddings", []), dtype=np.float32)
        else:
            print(f"Processing: {path_string}")
            try:
                documents, metadata, embeddings = process_file(path, config, embedder)
            except Exception as exc:
                print(f"Skipped {path_string}: {exc}")
                continue
            cache.set(
                path_string,
                CachedFileRecord(
                    signature=signature,
                    chunks=documents,
                    metadata=metadata,
                    embeddings=embeddings.tolist(),
                ),
            )

        all_documents.extend(documents)
        all_metadata.extend(metadata)
        if embeddings.size:
            all_embeddings.append(embeddings)

    if all_embeddings:
        matrix = np.vstack(all_embeddings).astype(np.float32)
    else:
        matrix = np.empty((0, embedder.model.get_sentence_embedding_dimension()), dtype=np.float32)

    index = embedder.build_index(matrix)
    config.index_path.parent.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(config.index_path))

    with config.metadata_path.open("wb") as meta_file:
        pickle.dump((all_documents, all_metadata), meta_file)

    graph_builder = DependencyGraphBuilder()
    graph_builder.extend(SourceChunkMetadata(**item) for item in all_metadata)
    graph_builder.serialize(config.graph_path)

    cache.prune_missing(present_paths)
    cache.save()

    print(f"Indexed {len(all_documents)} chunks from {len(present_paths)} files")
    print(f"Wrote {config.index_path}")
    print(f"Wrote {config.metadata_path}")
    print(f"Wrote {config.graph_path}")


if __name__ == "__main__":
    index_project()