from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any

from indexer.types import ParsedChunk


@dataclass
class SourceChunkMetadata:
    path: str
    layer: str
    language: str
    symbols: list[str] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)
    exports: list[str] = field(default_factory=list)
    route: str = ""
    chunk_type: str = ""
    framework: str = ""
    last_modified: str = ""
    hash: str = ""
    start_line: int | None = None
    end_line: int | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class IndexedChunk:
    text: str
    metadata: SourceChunkMetadata
    embedding: list[float] | None = None


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def hash_text(text: str) -> str:
    return sha256(text.encode("utf-8", errors="ignore")).hexdigest()


def infer_layer(path: str) -> str:
    normalized = Path(path).as_posix().lower()
    if "/frontend/" in normalized:
        return "frontend"
    if "/backend/" in normalized:
        return "backend"
    if "/database/" in normalized or normalized.endswith((".sql",)):
        return "database"
    if normalized.endswith((".env",)):
        return "config"
    if normalized.endswith(("dockerfile", ".yml", ".yaml")):
        return "config"
    return "shared"


def infer_language(path: str) -> str:
    name = Path(path).name.lower()
    suffix = Path(path).suffix.lower()
    if name == "dockerfile":
        return "docker"
    if suffix in {".ts", ".tsx"}:
        return "typescript"
    if suffix in {".js", ".jsx"}:
        return "javascript"
    if suffix == ".py":
        return "python"
    if suffix == ".sql":
        return "sql"
    if suffix == ".md":
        return "markdown"
    if suffix in {".yml", ".yaml"}:
        return "yaml"
    if suffix == ".env":
        return "env"
    return suffix.lstrip(".") or "text"


def infer_framework(path: str, content: str = "") -> str:
    normalized = Path(path).as_posix().lower()
    if "/frontend/" in normalized or normalized.endswith((".tsx", ".jsx")):
        if "next" in normalized:
            return "nextjs"
        return "react"
    if "/backend/" in normalized or "fastapi" in content.lower() or "from fastapi" in content.lower():
        return "fastapi"
    if normalized.endswith(("dockerfile",)) or "services:" in content.lower():
        return "docker"
    return ""


def build_metadata(path: str, chunk: ParsedChunk, source_text: str, file_hash: str) -> SourceChunkMetadata:
    return SourceChunkMetadata(
        path=path,
        layer=infer_layer(path),
        language=infer_language(path),
        symbols=chunk.symbols,
        imports=chunk.imports,
        exports=chunk.exports,
        route=chunk.route,
        chunk_type=chunk.chunk_type,
        framework=chunk.framework or infer_framework(path, source_text),
        last_modified=now_iso(),
        hash=file_hash,
        start_line=chunk.start_line,
        end_line=chunk.end_line,
        extra={**chunk.extra},
    )