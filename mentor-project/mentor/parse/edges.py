"""Edge building: resolved import edges + likely call edges (spec Phase 3, D3.3).

Labels: `resolved` only when the import target file exists in the repo
(join on the extractor's `resolved` field). Name-based call edges are
always `likely`. No other label is permitted.
"""
from __future__ import annotations


def build_import_edges(files: dict[str, dict]) -> list[dict]:
    edges = []
    for path in sorted(files):
        parsed = files[path]
        if parsed.get("status") != "parsed":
            continue
        for imp in parsed.get("imports", []):
            target = imp.get("resolved")
            edges.append({"kind": "import", "label": "resolved" if target else "unresolved",
                          "from": path, "to": target,
                          "module": imp.get("module"), "line": imp.get("line")})
    return edges


def build_call_edges(files: dict[str, dict]) -> list[dict]:
    """Name-based call edges: a call resolves (likely) to a same-file symbol
    or to a name explicitly imported in the same file."""
    edges = []
    for path in sorted(files):
        parsed = files[path]
        if parsed.get("status") != "parsed":
            continue
        defined = {}
        for sym in parsed.get("symbols", []):
            defined.setdefault(sym["name"], sym)
        imported = {}
        for imp in parsed.get("imports", []):
            for item in imp.get("names", []):
                key = item.get("alias") or item.get("name")
                if key and key != "*":
                    imported[key] = imp
        for sym in parsed.get("symbols", []):
            if sym.get("kind") not in ("function", "method", "const"):
                continue
            for call in sym.get("calls", []) or []:
                callee = call.get("name", "")
                base = callee.split(".")[0]
                if base in defined:
                    target = defined[base]
                    edges.append({"kind": "call", "label": "likely",
                                  "from": sym["qualname"], "from_file": path,
                                  "from_line": call.get("line"), "to": target["qualname"],
                                  "to_file": path,
                                  "to_lines": [target["start_line"], target["end_line"]]})
                elif base in imported:
                    edges.append({"kind": "call", "label": "likely",
                                  "from": sym["qualname"], "from_file": path,
                                  "from_line": call.get("line"), "to": base,
                                  "to_file": imported[base].get("resolved"),
                                  "to_lines": None})
    return edges


def build_edges(files: dict[str, dict]) -> dict:
    imports = build_import_edges(files)
    calls = build_call_edges(files)
    return {"imports": imports, "calls": calls,
            "counts": {"import": len(imports), "call": len(calls)}}
