from __future__ import annotations

import re

from indexer.types import ParsedChunk


IMPORT_PATTERN = re.compile(r"^\s*import\s+.*$|^\s*from\s+.*\s+import\s+.*$", re.MULTILINE)
EXPORT_PATTERN = re.compile(r"^\s*export\s+.*$", re.MULTILINE)
COMPONENT_PATTERN = re.compile(r"(?m)^\s*(?:export\s+)?(?:const|function)\s+([A-Z][A-Za-z0-9_]*)\s*(?:=\s*\(|\()")
HOOK_PATTERN = re.compile(r"(?m)^\s*const\s+(use[A-Z][A-Za-z0-9_]*)\s*=\s*\(")
INTERFACE_PATTERN = re.compile(r"(?m)^\s*(?:export\s+)?interface\s+([A-Z][A-Za-z0-9_]*)\b")
TYPE_PATTERN = re.compile(r"(?m)^\s*(?:export\s+)?type\s+([A-Z][A-Za-z0-9_]*)\b")
CONTEXT_PATTERN = re.compile(r"createContext\(|useContext\(")
ROUTE_PATTERN = re.compile(r"(?:app|router|useRouter|params|searchParams|pathname)")


def _block_from_match(text: str, start: int, next_start: int | None) -> str:
    end = next_start if next_start is not None else len(text)
    return text[start:end].strip()


def _next_start(starts: list[int], start: int) -> int | None:
    for candidate in starts:
        if candidate > start:
            return candidate
    return None


def parse_react_file(path: str, text: str) -> list[ParsedChunk]:
    chunks: list[ParsedChunk] = []
    imports = [match.group(0).strip() for match in IMPORT_PATTERN.finditer(text)]
    exports = [match.group(0).strip() for match in EXPORT_PATTERN.finditer(text)]
    symbols = []

    component_matches = list(COMPONENT_PATTERN.finditer(text))
    hook_matches = list(HOOK_PATTERN.finditer(text))
    interface_matches = list(INTERFACE_PATTERN.finditer(text))
    type_matches = list(TYPE_PATTERN.finditer(text))
    declaration_starts = sorted(
        match.start()
        for match in [*interface_matches, *type_matches, *component_matches, *hook_matches]
    )

    for match in interface_matches:
        start = match.start()
        chunk_text = _block_from_match(text, start, _next_start(declaration_starts, start))
        name = match.group(1)
        symbols.append(name)
        chunks.append(
            ParsedChunk(
                text=chunk_text,
                chunk_type="interface",
                symbols=[name],
                imports=imports,
                exports=exports,
                route=path,
                framework="react",
            )
        )

    for match in type_matches:
        start = match.start()
        chunk_text = _block_from_match(text, start, _next_start(declaration_starts, start))
        name = match.group(1)
        symbols.append(name)
        chunks.append(
            ParsedChunk(
                text=chunk_text,
                chunk_type="type",
                symbols=[name],
                imports=imports,
                exports=exports,
                route=path,
                framework="react",
            )
        )

    for match in component_matches:
        start = match.start()
        chunk_text = _block_from_match(text, start, _next_start(declaration_starts, start))
        name = match.group(1)
        symbols.append(name)
        chunks.append(
            ParsedChunk(
                text=chunk_text,
                chunk_type="component",
                symbols=[name],
                imports=imports,
                exports=exports,
                route=path,
                framework="react",
                extra={"context_used": bool(CONTEXT_PATTERN.search(chunk_text)), "route_usage": bool(ROUTE_PATTERN.search(chunk_text))},
            )
        )

    for match in hook_matches:
        start = match.start()
        chunk_text = _block_from_match(text, start, _next_start(declaration_starts, start))
        name = match.group(1)
        symbols.append(name)
        chunks.append(
            ParsedChunk(
                text=chunk_text,
                chunk_type="hook",
                symbols=[name],
                imports=imports,
                exports=exports,
                route=path,
                framework="react",
            )
        )

    if not chunks:
        chunks.append(
            ParsedChunk(
                text=text.strip(),
                chunk_type="module",
                symbols=symbols,
                imports=imports,
                exports=exports,
                route=path,
                framework="react",
                extra={"context_used": bool(CONTEXT_PATTERN.search(text)), "route_usage": bool(ROUTE_PATTERN.search(text))},
            )
        )

    return chunks
