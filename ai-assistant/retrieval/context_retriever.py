from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from config import DEFAULT_CONFIG, AppConfig
from retrieval.hybrid_search import HybridSearch
from retrieval.utils import normalize_metadata


class ContextRetriever:
    def __init__(self, config: AppConfig = DEFAULT_CONFIG) -> None:
        self.config = config
        self.searcher = HybridSearch(config)
        self.graph = self._load_graph(config.graph_path)

    def retrieve(self, query: str, top_k: int | None = None) -> list[dict[str, Any]]:
        limit = top_k or self.config.top_k
        results = self.searcher.search(query, k=limit)
        normalized = []
        for result in results:
            metadata = normalize_metadata(result.get("metadata"))
            item = {
                "text": result.get("text", ""),
                "metadata": metadata,
                "source": result.get("source", "unknown"),
                "score": result.get("score"),
                "rank_score": result.get("rank_score"),
                "related": self._related_context(metadata),
            }
            normalized.append(item)
        return normalized

    def retrieve_context(self, query: str, top_k: int | None = None) -> str:
        parts = []
        for result in self.retrieve(query, top_k):
            metadata = result["metadata"]
            symbols = ", ".join(str(symbol) for symbol in metadata.get("symbols", []))
            parts.append(
                f"FILE: {metadata.get('path', '')}\n"
                f"TYPE: {metadata.get('chunk_type', '')}\n"
                f"SYMBOLS: {symbols}\n"
                f"{result.get('text', '')}"
            )
        return "\n---\n".join(parts)

    def _load_graph(self, graph_path: Path) -> dict[str, Any]:
        if not graph_path.exists():
            return {}
        try:
            return json.loads(graph_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def _related_context(self, metadata: dict[str, Any]) -> list[dict[str, str]]:
        symbols = {str(symbol) for symbol in metadata.get("symbols", [])}
        path = str(metadata.get("path", ""))
        if not self.graph:
            return []

        relationships = self.graph.get("relationships", []) or self.graph.get("edges", []) or []
        related: list[dict[str, str]] = []
        for relationship in relationships:
            source = str(relationship.get("source", relationship.get("from", "")))
            target = str(relationship.get("target", relationship.get("to", "")))
            relation = str(relationship.get("relation", relationship.get("type", "related")))
            if path and (path in source or path in target):
                related.append({"source": source, "relation": relation, "target": target})
            elif symbols and (source in symbols or target in symbols):
                related.append({"source": source, "relation": relation, "target": target})
            if len(related) >= 8:
                break
        return related
