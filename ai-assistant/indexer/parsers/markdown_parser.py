from __future__ import annotations

import re

from indexer.types import ParsedChunk


HEADING_PATTERN = re.compile(r"(?=^#{1,6}\s+)", re.MULTILINE)


def parse_markdown_file(path: str, text: str) -> list[ParsedChunk]:
    parts = HEADING_PATTERN.split(text)
    chunks = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        chunks.append(
            ParsedChunk(
                text=part,
                chunk_type="section",
                framework="markdown",
            )
        )
    if not chunks:
        chunks.append(ParsedChunk(text=text.strip(), chunk_type="document", framework="markdown"))
    return chunks