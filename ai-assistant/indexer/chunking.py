from __future__ import annotations

from pathlib import Path
from typing import Callable

from indexer.types import ParsedChunk
from indexer.parsers.python_parser import parse_python_file
from indexer.parsers.react_parser import parse_react_file
from indexer.parsers.next_parser import parse_next_file
from indexer.parsers.sql_parser import parse_sql_file
from indexer.parsers.docker_parser import parse_docker_file
from indexer.parsers.env_parser import parse_env_file
from indexer.parsers.markdown_parser import parse_markdown_file


ParserFn = Callable[[str, str], list[ParsedChunk]]


EXTENSION_PARSERS: dict[str, ParserFn] = {
    ".py": parse_python_file,
    ".js": parse_react_file,
    ".jsx": parse_react_file,
    ".ts": parse_react_file,
    ".tsx": parse_react_file,
    ".sql": parse_sql_file,
    ".md": parse_markdown_file,
    ".yml": parse_docker_file,
    ".yaml": parse_docker_file,
    ".env": parse_env_file,
}


def split_with_overlap(text: str, chunk_size: int, overlap: int) -> list[str]:
    chunks = []
    start = 0
    text_length = len(text)

    while start < text_length:
        end = min(start + chunk_size, text_length)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= text_length:
            break
        start = max(end - overlap, start + 1)

    return chunks


def parse_file(path: str, text: str, chunk_size: int, overlap: int) -> list[ParsedChunk]:
    path_obj = Path(path)
    normalized = path_obj.as_posix().lower()
    lower_path = path_obj.name.lower()
    suffix = path_obj.suffix.lower()

    if lower_path == "dockerfile":
        suffix = "dockerfile"
    elif lower_path == ".env":
        suffix = ".env"
    elif ("frontend/app" in normalized or "frontend/pages" in normalized) and suffix in {".ts", ".tsx", ".js", ".jsx"}:
        chunks = parse_next_file(path, text)
        if chunks:
            return chunks

    parser = EXTENSION_PARSERS.get(suffix)
    if parser:
        chunks = parser(path, text)
        if chunks:
            return chunks

    return [ParsedChunk(text=chunk, chunk_type="text") for chunk in split_with_overlap(text, chunk_size, overlap)]