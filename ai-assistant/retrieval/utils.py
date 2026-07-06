from __future__ import annotations

from pathlib import Path
from typing import Any


def normalize_metadata(metadata: Any) -> dict[str, Any]:
    if isinstance(metadata, dict):
        return metadata
    if isinstance(metadata, str):
        return {
            "path": metadata,
            "layer": "unknown",
            "language": Path(metadata).suffix.lstrip("."),
            "symbols": [],
            "imports": [],
            "exports": [],
            "route": "",
            "chunk_type": "legacy_text",
            "framework": "",
        }
    return {
        "path": "",
        "layer": "unknown",
        "language": "",
        "symbols": [],
        "imports": [],
        "exports": [],
        "route": "",
        "chunk_type": "unknown",
        "framework": "",
    }