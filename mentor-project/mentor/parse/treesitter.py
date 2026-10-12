"""Tree-sitter grammar loading and shared node helpers (spec Phase 3, D3.1)."""
from __future__ import annotations

from functools import lru_cache

import tree_sitter
import tree_sitter_python as _py
import tree_sitter_typescript as _ts

LANGUAGE_FOR_EXT = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "tsx",
    # No plain-JS grammar in scope (A2: Py+TS first); the tsx grammar is used
    # for .js/.jsx and the grammar actually used is recorded per file.
    ".js": "tsx",
    ".jsx": "tsx",
}


@lru_cache(maxsize=None)
def get_language(name: str) -> tree_sitter.Language:
    if name == "python":
        return tree_sitter.Language(_py.language())
    if name == "typescript":
        return tree_sitter.Language(_ts.language_typescript())
    if name == "tsx":
        return tree_sitter.Language(_ts.language_tsx())
    raise ValueError(f"unknown language: {name}")


def get_parser(name: str) -> tree_sitter.Parser:
    return tree_sitter.Parser(get_language(name))


def parse_bytes(name: str, data: bytes) -> tree_sitter.Tree:
    return get_parser(name).parse(data)


def line_of(point) -> int:
    """0-based tree-sitter row -> 1-based line number."""
    return point.row + 1


def text_of(node, data: bytes) -> str:
    start, end = node.start_byte, node.end_byte
    return data[start:end].decode("utf-8", errors="replace")


def lines_of(data: bytes) -> list[str]:
    return data.decode("utf-8", errors="replace").splitlines()


def named_children(node, *types: str):
    return [c for c in node.children if c.type in types]


def first_named(node, *types: str):
    for c in node.children:
        if c.type in types:
            return c
    return None


def walk(node):
    """Yield node and all descendants depth-first."""
    stack = [node]
    while stack:
        current = stack.pop()
        yield current
        stack.extend(reversed(current.children))
