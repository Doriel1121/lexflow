from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

from indexer.types import ParsedChunk


@dataclass
class _PythonSymbol:
    name: str
    kind: str
    start_line: int
    end_line: int
    decorators: list[str]
    bases: list[str]
    docstring: str = ""


def _source_lines(text: str) -> list[str]:
    return text.splitlines()


def _node_text(lines: list[str], start_line: int, end_line: int) -> str:
    return "\n".join(lines[start_line - 1:end_line]).strip()


def _decorator_names(node: ast.AST) -> list[str]:
    decorators = []
    for decorator in getattr(node, "decorator_list", []):
        if isinstance(decorator, ast.Name):
            decorators.append(decorator.id)
        elif isinstance(decorator, ast.Attribute):
            decorators.append(decorator.attr)
        else:
            decorators.append(ast.unparse(decorator) if hasattr(ast, "unparse") else "decorator")
    return decorators


def _base_names(node: ast.ClassDef) -> list[str]:
    bases = []
    for base in node.bases:
        if isinstance(base, ast.Name):
            bases.append(base.id)
        elif isinstance(base, ast.Attribute):
            bases.append(base.attr)
        else:
            bases.append(ast.unparse(base) if hasattr(ast, "unparse") else "base")
    return bases


def _function_signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
    return f"{prefix} {node.name}"


def _class_signature(node: ast.ClassDef) -> str:
    bases = f"({', '.join(_base_names(node))})" if node.bases else ""
    return f"class {node.name}{bases}"


def parse_python_file(path: str, text: str) -> list[ParsedChunk]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return [ParsedChunk(text=text.strip(), chunk_type="module", framework="fastapi")]

    lines = _source_lines(text)
    chunks: list[ParsedChunk] = []
    imports: list[str] = []
    module_docstring = ast.get_docstring(tree) or ""

    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module_name = node.module or ""
            for alias in node.names:
                imports.append(f"{module_name}.{alias.name}".strip("."))

    if imports:
        import_lines = []
        for node in tree.body:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                start = getattr(node, "lineno", 1)
                end = getattr(node, "end_lineno", start)
                import_lines.append(_node_text(lines, start, end))
        import_text = "\n".join(import_lines).strip()
        if import_text:
            chunks.append(
                ParsedChunk(
                    text=import_text,
                    chunk_type="imports",
                    imports=imports,
                    framework="fastapi" if "fastapi" in text.lower() else "",
                )
            )

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            start = getattr(node, "lineno", None)
            end = getattr(node, "end_lineno", None)
            if start is None or end is None:
                continue
            chunk_text = _node_text(lines, start, end)
            if not chunk_text:
                continue
            methods = [child.name for child in node.body if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))]
            route_names = []
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    for decorator in getattr(child, "decorator_list", []):
                        decorator_text = ast.unparse(decorator) if hasattr(ast, "unparse") else ""
                        if "router." in decorator_text or "app." in decorator_text:
                            route_names.append(child.name)
            chunk_type = "class"
            if route_names:
                chunk_type = "api_class"
            chunks.append(
                ParsedChunk(
                    text=chunk_text,
                    chunk_type=chunk_type,
                    symbols=[node.name, *methods],
                    imports=imports,
                    exports=[node.name],
                    framework="fastapi" if route_names or "fastapi" in text.lower() else "python",
                    start_line=start,
                    end_line=end,
                    extra={
                        "bases": _base_names(node),
                        "docstring": ast.get_docstring(node) or "",
                        "decorators": _decorator_names(node),
                        "signature": _class_signature(node),
                    },
                )
            )
            continue

        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            start = getattr(node, "lineno", None)
            end = getattr(node, "end_lineno", None)
            if start is None or end is None:
                continue
            chunk_text = _node_text(lines, start, end)
            if not chunk_text:
                continue
            decorators = _decorator_names(node)
            is_route = any("router." in item or "app." in item for item in decorators)
            chunk_type = "route" if is_route else ("async_function" if isinstance(node, ast.AsyncFunctionDef) else "function")
            route = ""
            for decorator in decorators:
                if any(prefix in decorator for prefix in ("router.get", "router.post", "router.put", "router.delete", "router.patch", "app.get", "app.post", "app.put", "app.delete", "app.patch")):
                    route = decorator
                    break
            chunks.append(
                ParsedChunk(
                    text=chunk_text,
                    chunk_type=chunk_type,
                    symbols=[node.name],
                    imports=imports,
                    exports=[node.name],
                    route=route,
                    framework="fastapi" if route else "python",
                    start_line=start,
                    end_line=end,
                    extra={
                        "docstring": ast.get_docstring(node) or "",
                        "decorators": decorators,
                        "signature": _function_signature(node),
                    },
                )
            )

    if module_docstring:
        chunks.insert(
            0,
            ParsedChunk(
                text=module_docstring,
                chunk_type="docstring",
                imports=imports,
                framework="python",
            ),
        )

    if not chunks:
        chunks.append(ParsedChunk(text=text.strip(), chunk_type="module", imports=imports, framework="python"))

    return chunks