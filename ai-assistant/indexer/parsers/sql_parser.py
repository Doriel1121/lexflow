from __future__ import annotations

import re

from indexer.types import ParsedChunk


CREATE_TABLE_PATTERN = re.compile(r"(?is)create\s+table\s+[^;]+;")
CREATE_INDEX_PATTERN = re.compile(r"(?is)create\s+(?:unique\s+)?index\s+[^;]+;")
FOREIGN_KEY_PATTERN = re.compile(r"foreign\s+key\s*\(([^)]+)\)\s*references\s+([^(\s]+)", re.IGNORECASE)
PRIMARY_KEY_PATTERN = re.compile(r"primary\s+key\s*\(([^)]+)\)", re.IGNORECASE)
COLUMN_PATTERN = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s+([A-Za-z0-9_()]+)", re.MULTILINE)


def _table_name(statement: str) -> str:
    match = re.search(r"create\s+table\s+(?:if\s+not\s+exists\s+)?([A-Za-z0-9_\.\"]+)", statement, re.IGNORECASE)
    if match:
        return match.group(1).strip('"')
    return "table"


def _parse_columns(statement: str) -> list[str]:
    columns = []
    body_match = re.search(r"\((.*)\)", statement, re.DOTALL)
    if not body_match:
        return columns
    body = body_match.group(1)
    for column_match in COLUMN_PATTERN.finditer(body):
        column_name = column_match.group(1)
        columns.append(column_name)
    return columns


def parse_sql_file(path: str, text: str) -> list[ParsedChunk]:
    chunks: list[ParsedChunk] = []

    for statement in CREATE_TABLE_PATTERN.findall(text):
        table = _table_name(statement)
        columns = _parse_columns(statement)
        primary_keys = [match.group(1) for match in PRIMARY_KEY_PATTERN.finditer(statement)]
        foreign_keys = [f"{match.group(1)}->{match.group(2)}" for match in FOREIGN_KEY_PATTERN.finditer(statement)]
        chunks.append(
            ParsedChunk(
                text=statement.strip(),
                chunk_type="table",
                symbols=[table, *columns],
                framework="sql",
                extra={"table": table, "columns": columns, "primary_keys": primary_keys, "foreign_keys": foreign_keys},
            )
        )

    for statement in CREATE_INDEX_PATTERN.findall(text):
        index_name = re.search(r"create\s+(?:unique\s+)?index\s+([A-Za-z0-9_\.\"]+)", statement, re.IGNORECASE)
        chunks.append(
            ParsedChunk(
                text=statement.strip(),
                chunk_type="index",
                symbols=[index_name.group(1).strip('"')] if index_name else [],
                framework="sql",
            )
        )

    if not chunks:
        chunks.append(ParsedChunk(text=text.strip(), chunk_type="sql", framework="sql"))

    return chunks