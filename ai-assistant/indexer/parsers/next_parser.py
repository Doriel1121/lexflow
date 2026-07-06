from __future__ import annotations

from pathlib import Path

from indexer.parsers.react_parser import parse_react_file
from indexer.types import ParsedChunk


def parse_next_file(path: str, text: str) -> list[ParsedChunk]:
    chunks = parse_react_file(path, text)
    normalized = Path(path).as_posix().lower()
    route = normalized.split("/frontend/")[-1] if "/frontend/" in normalized else normalized
    for chunk in chunks:
        chunk.framework = "nextjs"
        chunk.route = route
    return chunks