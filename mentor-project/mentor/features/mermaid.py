"""Deterministic Mermaid flowchart renderer (spec Phase 12, C8).

The LLM NEVER writes Mermaid: node IDs are generated (N1..), labels are
escaped by code, shapes come from component kinds. `check()` is the manual
parse validation until the Phase 16 browser check: header, balanced quotes,
known edge endpoints, no raw syntax characters inside labels.

Escaping rules (Mermaid flowchart docs [OFFICIAL]): quoted labels for
troublesome text; entity codes for reserved chars. We additionally forbid the
bare word `end` and leading o/x link-target confusion BY CONSTRUCTION
(generated IDs match ^N[0-9]+$).
"""
from __future__ import annotations

import re

SHAPES = {
    "entrypoint": ("([", "])"),       # stadium
    "api-layer": ("[", "]"),
    "model-layer": ("[", "]"),
    "service-layer": ("[", "]"),
    "frontend": ("[", "]"),
    "test": ("[", "]"),
    "configuration": ("[", "]"),
    "external-database": ("[(", ")]"),  # cylinder
}


def escape_label(text: str) -> str:
    """Replace every Mermaid-significant character with safe text."""
    out = []
    for ch in text:
        out.append({
            '"': "#quot;",
            "#": "#35;",
            "<": "#lt;",
            ">": "#gt;",
            "`": "'",
            "[": "(",
            "]": ")",
            "{": "(",
            "}": ")",
            "|": "/",
            ";": ",",
        }.get(ch, ch))
    return "".join(out).strip()


def render(model: dict, direction: str = "LR") -> str:
    """Render the component model. Output depends only on the model."""
    lines = [f"flowchart {direction}"]
    for node in model["nodes"]:
        left, right = SHAPES.get(node["kind"], ("[", "]"))
        lines.append(f'    {node["id"]}{left}"{escape_label(node["label"])}"{right}')
    for edge in model["edges"]:
        lines.append(f'    {edge["from"]} -->|{escape_label(edge["kind"])}| {edge["to"]}')
    return "\n".join(lines) + "\n"


def check(text: str) -> list[str]:
    """Structural validation. Empty list = parses (manually)."""
    problems: list[str] = []
    lines = text.splitlines()
    if not lines or not re.fullmatch(r"flowchart (TD|TB|BT|RL|LR)", lines[0].strip()):
        problems.append("missing/invalid flowchart header")
        return problems
    defined: set[str] = set()
    for lineno, line in enumerate(lines[1:], start=2):
        s = line.strip()
        if not s:
            continue
        m = re.fullmatch(r"(N[0-9]+)(\(\[|\[\(|\[).*", s)
        edge = re.fullmatch(r"(N[0-9]+)\s*-->\|([^|]*)\|\s*(N[0-9]+)", s)
        if m:
            defined.add(m.group(1))
            label = s.split('"')
            if len(label) < 3 or any(c in label[1] for c in '[]{}|"'):
                problems.append(f"line {lineno}: bad label quoting")
        elif edge:
            for endpoint in (edge.group(1), edge.group(3)):
                if endpoint not in defined:
                    problems.append(f"line {lineno}: unknown endpoint {endpoint}")
            if re.search(r"[\"#<>`]", edge.group(2)):
                problems.append(f"line {lineno}: raw char in edge label")
        else:
            problems.append(f"line {lineno}: unrecognized statement")
    return problems
