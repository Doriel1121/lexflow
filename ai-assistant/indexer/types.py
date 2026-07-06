from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ParsedChunk:
    text: str
    chunk_type: str
    symbols: list[str] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)
    exports: list[str] = field(default_factory=list)
    route: str = ""
    framework: str = ""
    start_line: int | None = None
    end_line: int | None = None
    extra: dict[str, Any] = field(default_factory=dict)