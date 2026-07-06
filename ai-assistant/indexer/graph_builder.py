from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Iterable

from indexer.metadata import SourceChunkMetadata
from knowledge.models import KnowledgeEdge, KnowledgeGraph, KnowledgeNode


class DependencyGraphBuilder:
    def __init__(self) -> None:
        self.graph = KnowledgeGraph()

    def add_metadata(self, metadata: SourceChunkMetadata) -> None:
        file_node_id = metadata.path
        self.graph.add_node(
            KnowledgeNode(
                id=file_node_id,
                name=Path(metadata.path).name,
                kind="file",
                path=metadata.path,
                language=metadata.language,
                framework=metadata.framework,
                metadata={"layer": metadata.layer, "chunk_type": metadata.chunk_type},
            )
        )

        for symbol in metadata.symbols:
            symbol_id = f"{metadata.path}::{symbol}"
            self.graph.add_node(
                KnowledgeNode(
                    id=symbol_id,
                    name=symbol,
                    kind=metadata.chunk_type or "symbol",
                    path=metadata.path,
                    language=metadata.language,
                    framework=metadata.framework,
                    metadata={"route": metadata.route},
                )
            )
            self.graph.add_edge(KnowledgeEdge(source=file_node_id, target=symbol_id, relation="defines"))

        for import_name in metadata.imports:
            self.graph.add_edge(KnowledgeEdge(source=file_node_id, target=import_name, relation="imports"))

        for export_name in metadata.exports:
            self.graph.add_edge(KnowledgeEdge(source=file_node_id, target=f"export::{export_name}", relation="exports"))

        if metadata.route:
            self.graph.add_edge(KnowledgeEdge(source=file_node_id, target=metadata.route, relation="route"))

    def extend(self, metadata_items: Iterable[SourceChunkMetadata]) -> None:
        for item in metadata_items:
            self.add_metadata(item)

    def serialize(self, path: str | Path) -> None:
        output = Path(path)
        output.write_text(__import__("json").dumps(self.graph.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")