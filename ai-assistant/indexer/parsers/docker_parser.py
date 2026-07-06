from __future__ import annotations

import re

from indexer.types import ParsedChunk


SERVICE_PATTERN = re.compile(r"^\s{2,}([A-Za-z0-9_-]+):\s*$", re.MULTILINE)
PORT_PATTERN = re.compile(r"ports:\s*\n((?:\s*-\s*.+\n?)+)", re.MULTILINE)
VOLUME_PATTERN = re.compile(r"volumes:\s*\n((?:\s*-\s*.+\n?)+)", re.MULTILINE)
DEPENDS_PATTERN = re.compile(r"depends_on:\s*\n((?:\s*-\s*.+\n?)+)", re.MULTILINE)
ENV_PATTERN = re.compile(r"environment:\s*\n((?:\s*-\s*.+\n?|\s+[A-Za-z0-9_]+:\s*.+\n?)+)", re.MULTILINE)


def _block_for_service(text: str, service_name: str, next_service_start: int | None, current_start: int) -> str:
    end = next_service_start if next_service_start is not None else len(text)
    return text[current_start:end].strip()


def parse_docker_file(path: str, text: str) -> list[ParsedChunk]:
    chunks: list[ParsedChunk] = []
    service_matches = list(SERVICE_PATTERN.finditer(text))

    for index, match in enumerate(service_matches):
        service_name = match.group(1)
        next_start = service_matches[index + 1].start() if index + 1 < len(service_matches) else None
        block = _block_for_service(text, service_name, next_start, match.start())
        ports = PORT_PATTERN.findall(block)
        volumes = VOLUME_PATTERN.findall(block)
        depends_on = DEPENDS_PATTERN.findall(block)
        environment = ENV_PATTERN.findall(block)
        chunks.append(
            ParsedChunk(
                text=block,
                chunk_type="service",
                symbols=[service_name],
                framework="docker",
                extra={"ports": ports, "volumes": volumes, "depends_on": depends_on, "environment": environment},
            )
        )

    if not chunks:
        chunks.append(ParsedChunk(text=text.strip(), chunk_type="docker", framework="docker"))

    return chunks