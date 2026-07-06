from __future__ import annotations

import re

from indexer.types import ParsedChunk


KEY_PATTERN = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=.*$", re.MULTILINE)


def parse_env_file(path: str, text: str) -> list[ParsedChunk]:
    keys = [match.group(1) for match in KEY_PATTERN.finditer(text) if not match.group(1).startswith("#")]
    if not keys:
        return [ParsedChunk(text="", chunk_type="env", framework="config")]

    chunks = []
    for key in keys:
        chunks.append(
            ParsedChunk(
                text=f"{key}=<redacted>",
                chunk_type="env_key",
                symbols=[key],
                framework="config",
            )
        )
    return chunks