from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from knowledge.models import KnowledgeEdge, KnowledgeGraph, KnowledgeNode
from indexer.metadata import SourceChunkMetadata


class KnowledgeGraphBuilder:
    def __init__(self) -> None:
        self.graph = KnowledgeGraph()

    def add_metadata(self, metadata: SourceChunkMetadata) -> None:
        for symbol in metadata.symbols:
            node_id = f"{metadata.path}:{symbol}"
            self.graph.add_node(
                KnowledgeNode(
                    id=node_id,
                    name=symbol,
                    kind=metadata.chunk_type or "symbol",
                    path=metadata.path,
                    language=metadata.language,
                    framework=metadata.framework,
                    metadata={"route": metadata.route, "layer": metadata.layer},
                )
            )

        for import_name in metadata.imports:
            self.graph.add_edge(
                KnowledgeEdge(
                    source=metadata.path,
                    target=import_name,
                    relation="imports",
                )
            )

    def extend(self, metadata_items: Iterable[SourceChunkMetadata]) -> None:
        for item in metadata_items:
            self.add_metadata(item)

    def serialize(self, path: str | Path) -> None:
        output = Path(path)
        output.write_text(json.dumps(self.graph.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")