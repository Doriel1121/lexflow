from __future__ import annotations

import pickle
import re
from pathlib import Path
from typing import Any

from config import DEFAULT_CONFIG
from retrieval.utils import normalize_metadata

_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_STOPWORDS = {
    "what",
    "where",
    "when",
    "which",
    "about",
    "with",
    "from",
    "that",
    "this",
    "the",
    "and",
    "for",
    "are",
    "is",
    "in",
    "of",
    "to",
}


def query_tokens(query: str) -> list[str]:
    tokens = []
    for token in _TOKEN_RE.findall(query):
        normalized = token.lower()
        if len(normalized) < 3 or normalized in _STOPWORDS:
            continue
        tokens.append(normalized)
    return tokens


class SymbolSearch:
    def __init__(self, config=DEFAULT_CONFIG) -> None:
        self.config = config
        with Path(config.metadata_path).open("rb") as meta_file:
            self.documents, raw_metadata = pickle.load(meta_file)
        self.metadata = [normalize_metadata(item) for item in raw_metadata]
        self.index = self._build_index()

    def _build_index(self) -> dict[str, list[int]]:
        symbol_index: dict[str, list[int]] = {}
        for idx, metadata in enumerate(self.metadata):
            for symbol in metadata.get("symbols", []):
                symbol_index.setdefault(str(symbol).lower(), []).append(idx)
        return symbol_index

    def lookup_symbol(self, symbol: str) -> list[dict[str, Any]]:
        matches = self.index.get(symbol.lower(), [])
        return [
            {
                "text": self.documents[index],
                "metadata": self.metadata[index],
                "source": "symbol",
                "score": 100.0,
            }
            for index in matches
        ]

    def fuzzy_lookup(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        tokens = query_tokens(query)
        if not tokens:
            return []

        ranked_matches: list[tuple[int, int]] = []
        for symbol, indices in self.index.items():
            score = self._symbol_score(symbol, tokens)
            if score <= 0:
                continue
            for index in indices:
                ranked_matches.append((score, index))

        return self._results_from_ranked_matches(ranked_matches, limit, "symbol")

    def lexical_lookup(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        tokens = query_tokens(query)
        if not tokens:
            return []

        ranked_matches: list[tuple[int, int]] = []
        for index, (text, metadata) in enumerate(zip(self.documents, self.metadata)):
            score = self._lexical_score(str(text), metadata, tokens)
            if score > 0:
                ranked_matches.append((score, index))

        return self._results_from_ranked_matches(ranked_matches, limit, "lexical")

    def _results_from_ranked_matches(self, ranked_matches: list[tuple[int, int]], limit: int, source: str) -> list[dict[str, Any]]:
        ranked_matches.sort(key=lambda item: item[0], reverse=True)
        results = []
        seen = set()
        for score, index in ranked_matches:
            if index in seen:
                continue
            seen.add(index)
            results.append(
                {
                    "score": float(score),
                    "text": self.documents[index],
                    "metadata": self.metadata[index],
                    "source": source,
                }
            )
            if len(results) >= limit:
                break
        return results

    def _symbol_score(self, symbol: str, tokens: list[str]) -> int:
        symbol_parts = set(query_tokens(symbol))
        score = 0
        for token in tokens:
            if symbol == token:
                score += 100
            elif token in symbol_parts:
                score += 75
            elif symbol.startswith(token):
                score += 40
            elif token in symbol:
                score += 15
        return score

    def _lexical_score(self, text: str, metadata: dict[str, Any], tokens: list[str]) -> int:
        text_lower = text.lower()
        path = str(metadata.get("path", "")).replace("\\", "/").lower()
        layer = str(metadata.get("layer", "")).lower()
        language = str(metadata.get("language", "")).lower()
        chunk_type = str(metadata.get("chunk_type", "")).lower()
        symbols = {str(symbol).lower() for symbol in metadata.get("symbols", [])}
        token_set = set(tokens)

        score = 0
        for token in token_set:
            if token in symbols:
                score += 90
            if token in path:
                score += 35
            if token in text_lower[:1500]:
                score += 20

        if {"interface", "user"}.issubset(token_set) and "interface user" in text_lower:
            score += 240
        if {"interface", "user"}.issubset(token_set) and "export interface user" in text_lower:
            score += 280
        if "frontend" in token_set and (layer == "frontend" or "/frontend/" in path):
            score += 90
        if "backend" in token_set and (layer == "backend" or "/backend/" in path):
            score += 90
        if "interface" in token_set and language in {"typescript", "tsx", "ts"}:
            score += 60
        if "interface" in token_set and chunk_type == "component":
            score -= 80
        if path.endswith("/.env") or "/.env" in path or chunk_type == "env_key":
            score -= 180
        if "/tests/" in path and "test" not in token_set:
            score -= 40
        return score
