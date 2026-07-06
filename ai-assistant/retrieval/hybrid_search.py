from __future__ import annotations

from typing import Any

from config import DEFAULT_CONFIG
from retrieval.semantic_search import SemanticSearch
from retrieval.symbol_search import SymbolSearch, query_tokens


class HybridSearch:
    def __init__(self, config=DEFAULT_CONFIG) -> None:
        self.semantic = SemanticSearch(config)
        self.symbol = SymbolSearch(config)

    def search(self, query: str, k: int = 8) -> list[dict[str, Any]]:
        limit = max(k * 3, 12)
        semantic_results = self.semantic.search(query, k=limit)
        symbol_results = self.symbol.fuzzy_lookup(query, limit=limit)
        lexical_results = self.symbol.lexical_lookup(query, limit=limit)
        combined = []
        seen = set()
        for result in [*symbol_results, *lexical_results, *semantic_results]:
            metadata = result["metadata"]
            key = (metadata.get("path"), result["text"][:120])
            if key in seen:
                continue
            seen.add(key)
            ranked_result = dict(result)
            ranked_result["rank_score"] = self._rank_result(query, ranked_result)
            combined.append(ranked_result)

        combined.sort(key=lambda result: result.get("rank_score", 0.0), reverse=True)
        return combined[:k]

    def lookup_symbol(self, symbol: str) -> list[dict[str, Any]]:
        return self.symbol.lookup_symbol(symbol)

    def retrieve_context(self, query: str, k: int = 8) -> str:
        results = self.search(query, k=k)
        context_parts = []
        for result in results:
            metadata = result["metadata"]
            path = metadata.get("path", "")
            chunk_type = metadata.get("chunk_type", "")
            symbols = ", ".join(metadata.get("symbols", []))
            context_parts.append(f"FILE: {path}\nTYPE: {chunk_type}\nSYMBOLS: {symbols}\n{result['text']}")
        return "\n---\n".join(context_parts)

    def _rank_result(self, query: str, result: dict[str, Any]) -> float:
        tokens = set(query_tokens(query))
        metadata = result.get("metadata", {})
        path = str(metadata.get("path", "")).replace("\\", "/").lower()
        layer = str(metadata.get("layer", "")).lower()
        language = str(metadata.get("language", "")).lower()
        chunk_type = str(metadata.get("chunk_type", "")).lower()
        symbols = {str(symbol).lower() for symbol in metadata.get("symbols", [])}
        text = str(result.get("text", "")).lower()

        score = 0.0
        if result.get("source") == "symbol":
            score += 100.0
        if result.get("source") == "lexical":
            score += 80.0
        score += float(result.get("score") or 0.0)

        for token in tokens:
            if token in symbols:
                score += 90.0
            elif any(symbol.startswith(token) for symbol in symbols):
                score += 35.0
            elif token in path:
                score += 18.0
            elif token in text[:1000]:
                score += 5.0

        if "frontend" in tokens and (layer == "frontend" or "/frontend/" in path):
            score += 80.0
        if "backend" in tokens and (layer == "backend" or "/backend/" in path):
            score += 80.0
        if "interface" in tokens and language in {"typescript", "tsx", "ts"}:
            score += 45.0
        if "interface" in tokens and ("interface" in chunk_type or "interface " in text[:400]):
            score += 45.0
        if {"interface", "user"}.issubset(tokens) and "export interface user" in text[:600]:
            score += 200.0
        elif {"interface", "user"}.issubset(tokens) and "interface user" in text[:600]:
            score += 160.0

        if "interface" in tokens and chunk_type == "component":
            score -= 75.0
        if path.endswith("/.env") or "/.env" in path or chunk_type == "env_key":
            score -= 120.0
        if "/node_modules/" in path or "/.venv/" in path:
            score -= 200.0
        if "/tests/" in path and "test" not in tokens:
            score -= 35.0
        if path.endswith("docker-compose.yml") and not ({"docker", "compose", "service"} & tokens):
            score -= 70.0

        return score
