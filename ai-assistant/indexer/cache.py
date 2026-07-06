from __future__ import annotations

import os
import pickle
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any


CACHE_VERSION = 2


@dataclass
class CachedFileRecord:
    signature: tuple[int, int]
    chunks: list[dict[str, Any]]
    embeddings: list[list[float]]
    metadata: list[dict[str, Any]]


class IndexCache:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.data: dict[str, Any] = {"version": CACHE_VERSION, "files": {}}

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            self.data = {"version": CACHE_VERSION, "files": {}}
            return self.data

        try:
            with self.path.open("rb") as cache_file:
                data = pickle.load(cache_file)
            if data.get("version") != CACHE_VERSION or not isinstance(data.get("files"), dict):
                self.data = {"version": CACHE_VERSION, "files": {}}
            else:
                self.data = data
        except Exception:
            self.data = {"version": CACHE_VERSION, "files": {}}
        return self.data

    def get(self, path: str, signature: tuple[int, int]) -> dict[str, Any] | None:
        record = self.data.get("files", {}).get(path)
        if record and tuple(record.get("signature", ())) == tuple(signature):
            return record
        return None

    def set(self, path: str, record: CachedFileRecord) -> None:
        self.data.setdefault("files", {})[path] = asdict(record)

    def prune_missing(self, present_paths: set[str]) -> None:
        files = self.data.setdefault("files", {})
        for path in list(files.keys()):
            if path not in present_paths:
                del files[path]

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("wb") as cache_file:
            pickle.dump(self.data, cache_file)


def file_signature(path: str | Path) -> tuple[int, int]:
    stat_result = os.stat(path)
    return stat_result.st_mtime_ns, stat_result.st_size