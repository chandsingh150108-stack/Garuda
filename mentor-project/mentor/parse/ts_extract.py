"""TypeScript/TSX symbol, import, and client-call extraction (spec Phase 3).

Functions, classes (+methods), exported constants, imports with resolved
targets, and HTTP client call sites (`fetch(`/`axios.` with a string path).
Client calls are recorded as client-side calls, never routes.
"""
from __future__ import annotations

import re
from pathlib import Path

from mentor.parse import treesitter as T

IDENT_LIKE = ("identifier", "type_identifier", "property_identifier",
              "private_property_identifier", "shorthand_property_identifier")


def _text(node, data: bytes) -> str:
    return T.text_of(node, data)


def _first_name(node, data: bytes) -> str | None:
    for c in node.children:
        if c.type in IDENT_LIKE:
            return _text(c, data)
    return None


def _unquote(node, data: bytes) -> str | None:
    if node.type != "string":
        return None
    frag = T.first_named(node, "string_fragment")
    if frag is not None:
        return _text(frag, data)
    raw = _text(node, data)
    if len(raw) >= 2 and raw[0] in "\"'`" and raw[-1] == raw[0]:
        return raw[1:-1]
    return raw


def resolve_ts(source: str, importer: Path, repo_root: Path) -> str | None:
    """Resolve an import source to a repo-relative file if it exists."""
    if source.startswith("@/"):
        bases = [repo_root / "frontend" / "src" / source[2:]]
    elif source.startswith("."):
        bases = [(importer.parent / source)]
    else:
        return None  # bare package import: external, never resolved
    for base in bases:
        cands = [base.with_suffix(s) for s in (".ts", ".tsx", ".js")]
        cands += [base / ("index" + s) for s in (".ts", ".tsx", ".js")]
        cands.append(base)  # exact path as written
        for cand in cands:
            try:
                if cand.is_file():
                    return cand.relative_to(repo_root).as_posix()
            except (OSError, ValueError):
                continue
    return None


def _import_names(clause, data: bytes) -> list[dict]:
    names: list[dict] = []
    if clause is None:
        return names
    for child in clause.children:
        if child.type == "identifier":
            names.append({"name": _text(child, data), "alias": None})
        elif child.type == "named_imports":
            for spec in child.children:
                if spec.type != "import_specifier":
                    continue
                parts = [c for c in spec.children if c.type in IDENT_LIKE]
                if len(parts) == 1:
                    names.append({"name": _text(parts[0], data), "alias": None})
                elif len(parts) >= 2:
                    names.append({"name": _text(parts[0], data),
                                  "alias": _text(parts[-1], data)})
        elif child.type == "namespace_import":
            ident = T.first_named(child, "identifier")
            if ident is not None:
                names.append({"name": "*", "alias": _text(ident, data)})
    return names


def _collect_ts_calls(fn_node, data: bytes) -> list[dict]:
    calls = []
    for node in T.walk(fn_node):
        if node.type != "call_expression":
            continue
        callee = node.children[0] if node.children else None
        if callee is None:
            continue
        if callee.type == "identifier":
            calls.append({"name": _text(callee, data),
                          "line": T.line_of(callee.start_point)})
        elif callee.type == "member_expression":
            parts = [c for c in callee.children if c.type in IDENT_LIKE]
            if len(parts) >= 2:
                calls.append({"name": f"{_text(parts[0], data)}.{_text(parts[-1], data)}",
                              "line": T.line_of(callee.start_point)})
    return calls


def _client_call(call_node, data: bytes) -> dict | None:
    """fetch("...") or axios.<m>("...") with a string path argument."""
    callee = call_node.children[0] if call_node.children else None
    if callee is None:
        return None
    label = None
    if callee.type == "identifier" and _text(callee, data) == "fetch":
        label = "fetch"
    elif callee.type == "member_expression":
        parts = [c for c in callee.children if c.type in IDENT_LIKE]
        if len(parts) >= 2 and _text(parts[0], data) == "axios":
            label = f"axios.{_text(parts[-1], data)}"
    if label is None:
        return None
    args = T.first_named(call_node, "arguments")
    if args is None:
        return None
    for arg in args.children:
        if arg.type == "string":
            val = _unquote(arg, data)
            if val is not None:
                return {"callee": label, "path": val,
                        "line": T.line_of(call_node.start_point)}
            return None
        if arg.type not in ("(", ")", ","):
            return None  # first arg is not a string literal
    return None


def extract_ts(path: Path, data: bytes, repo_root: Path, grammar: str) -> dict:
    tree = T.parse_bytes(grammar, data)
    root = tree.root_node
    rel = path.relative_to(repo_root).as_posix()
    symbols: list[dict] = []
    imports: list[dict] = []
    client_calls: list[dict] = []
    file_lines = len(T.lines_of(data))

    def add_symbol(kind, name, node, parent, exported, extra=None):
        start = T.line_of(node.start_point)
        sym = {"kind": kind, "name": name,
               "qualname": f"{parent}.{name}" if parent else name,
               "parent": parent, "start_line": start,
               "end_line": T.line_of(node.end_point), "signature_line": start,
               "docstring": None, "exported": exported,
               "decorators": [], "params": None,
               "calls": _collect_ts_calls(node, data)}
        if extra:
            sym.update(extra)
        symbols.append(sym)
        return sym

    def visit(node, parent: str | None, exported: bool):
        for child in node.children:
            ctype = child.type
            if ctype == "import_statement":
                src_node = next((c for c in child.children if c.type == "string"), None)
                source = _unquote(src_node, data) if src_node is not None else ""
                clause = T.first_named(child, "import_clause")
                imports.append({"module": source or "",
                                "names": _import_names(clause, data),
                                "line": T.line_of(child.start_point), "level": 0,
                                "resolved": resolve_ts(source or "", path, repo_root)})
            elif ctype == "export_statement":
                visit(child, parent, True)
            elif ctype == "function_declaration":
                name = _first_name(child, data) or "<anonymous>"
                qual = f"{parent}.{name}" if parent else name
                add_symbol("function", name, child, parent, exported)
                body = T.first_named(child, "statement_block")
                if body is not None:
                    visit(body, qual, False)
            elif ctype in ("class_declaration", "abstract_class_declaration"):
                name = _first_name(child, data) or "<anonymous>"
                qual = f"{parent}.{name}" if parent else name
                add_symbol("class", name, child, parent, exported)
                body = T.first_named(child, "class_body")
                if body is not None:
                    for member in body.children:
                        if member.type == "method_definition":
                            mname = _first_name(member, data) or "<anonymous>"
                            add_symbol("method", mname, member, name, False)
                            mbody = T.first_named(member, "statement_block")
                            if mbody is not None:
                                visit(mbody, f"{qual}.{mname}", False)
                        elif member.type not in ("{", "}"):
                            visit(member, qual, False)
            elif ctype == "lexical_declaration":
                for decl in T.named_children(child, "variable_declarator"):
                    ident = T.first_named(decl, "identifier")
                    if ident is None:
                        continue
                    value = decl.children[-1] if len(decl.children) > 1 else None
                    extra = {"const_kind": "arrow" if value is not None and value.type == "arrow_function" else "value"}
                    cname = _text(ident, data)
                    cqual = f"{parent}.{cname}" if parent else cname
                    # Only top-level consts are symbols; nested ones are
                    # locals (noise), but their values are still scanned.
                    if parent is None:
                        add_symbol("const", cname, decl, parent, exported, extra)
                    if value is not None and value.children:
                        visit(value, cqual, False)
            elif ctype == "call_expression":
                cc = _client_call(child, data)
                if cc is not None:
                    cc["file"] = rel
                    client_calls.append(cc)
                for sub in child.children:
                    if sub.children:
                        visit(sub, parent, False)
            elif ctype in ("statement_block", "program", "export_statement",
                           "class_body", "if_statement", "try_statement",
                           "for_statement", "while_statement"):
                visit(child, parent, exported)
            elif child.children and ctype not in ("string", "template_string"):
                # Descend generically so nested calls/imports are not missed,
                # but never treat nested declarations as new top-level symbols
                # except through the explicit branches above.
                visit(child, parent, False)

    visit(root, None, False)
    return {"path": rel, "language": grammar, "status": "parsed",
            "file_lines": file_lines, "has_error": root.has_error,
            "symbols": symbols, "imports": imports, "routes": [],
            "models": [], "client_calls": client_calls}
