"""Python symbol/import/route/model extraction (spec Phase 3).

Symbol ranges start at the `def`/`class` line (decorators are recorded
separately), so the first line of a symbol's text is always its signature
line. Router prefixes join within the same file; cross-file router wiring
(dynamic app prefixes like `settings.API_V1_STR`) is reported as notes by
the CLI pass, never guessed.
"""
from __future__ import annotations

from pathlib import Path

from mentor.parse import treesitter as T

ROUTE_METHODS = {"get", "post", "put", "patch", "delete"}


def _text(node, data: bytes) -> str:
    return T.text_of(node, data)


def _dotted(node, data: bytes) -> str:
    parts = [c for c in node.children if c.type == "identifier"]
    return ".".join(_text(c, data) for c in parts)


def _string_value(node, data: bytes) -> str | None:
    """Unquoted value of a string literal, else None."""
    if node.type != "string":
        return None
    content = T.first_named(node, "string_content")
    if content is not None:
        return _text(content, data)
    raw = _text(node, data)
    if len(raw) >= 2 and raw[0] in "\"'" and raw[-1] == raw[0]:
        return raw[1:-1]
    return raw


def _call_args(call, data: bytes):
    arglist = T.first_named(call, "argument_list")
    if arglist is None:
        return []
    return [c for c in arglist.children if c.type not in ("(", ")", ",")]


def resolve_py(module: str, level: int, importer: Path, repo_root: Path) -> str | None:
    """Resolve an import to a repo-relative .py path if the target exists."""
    parts = module.split(".") if module else []
    candidates: list[Path] = []
    if level > 0:
        base = importer.parent
        for _ in range(level - 1):
            base = base.parent
        if parts:
            candidates.append(base.joinpath(*parts).with_suffix(".py"))
            candidates.append(base.joinpath(*parts, "__init__.py"))
        else:
            candidates.append(base.with_suffix(".py"))
            candidates.append(base / "__init__.py")
    else:
        for root in (repo_root / "backend", repo_root):
            if parts:
                candidates.append(root.joinpath(*parts).with_suffix(".py"))
                candidates.append(root.joinpath(*parts, "__init__.py"))
    for cand in candidates:
        try:
            if cand.is_file():
                return cand.relative_to(repo_root).as_posix()
        except (OSError, ValueError):
            continue
    return None


def _parse_imports(node, data: bytes, importer: Path, repo_root: Path) -> dict | None:
    line = T.line_of(node.start_point)
    if node.type == "import_statement":
        for child in node.children:
            if child.type == "dotted_name":
                module = _dotted(child, data)
                return {"module": module, "names": [{"name": module, "alias": None}],
                        "line": line, "level": 0,
                        "resolved": resolve_py(module, 0, importer, repo_root)}
            if child.type == "aliased_import":
                mod = _dotted(T.first_named(child, "dotted_name"), data)
                alias = _text(T.named_children(child, "identifier")[-1], data)
                return {"module": mod, "names": [{"name": mod, "alias": alias}],
                        "line": line, "level": 0,
                        "resolved": resolve_py(mod, 0, importer, repo_root)}
        return None
    if node.type == "import_from_statement":
        level = 0
        module = ""
        for child in node.children:
            if child.type == "relative_import":
                prefix = T.first_named(child, "import_prefix")
                dots = _text(prefix, data) if prefix is not None else ""
                level = dots.count(".")
                dotted = T.first_named(child, "dotted_name")
                module = _dotted(dotted, data) if dotted is not None else ""
            elif child.type == "dotted_name" and module == "" and level == 0:
                module = _dotted(child, data)
        names: list[dict] = []
        seen_import_kw = False
        for child in node.children:
            if child.type == "import":
                seen_import_kw = True
                continue
            if not seen_import_kw:
                continue
            if child.type == "wildcard_import":
                names.append({"name": "*", "alias": None})
            elif child.type == "dotted_name":
                names.append({"name": _dotted(child, data), "alias": None})
            elif child.type == "identifier":
                names.append({"name": _text(child, data), "alias": None})
            elif child.type == "aliased_import":
                inner = child.children[0]
                nm = _dotted(inner, data) if inner.type == "dotted_name" else _text(inner, data)
                alias = _text(T.named_children(child, "identifier")[-1], data)
                names.append({"name": nm, "alias": alias})
        return {"module": module, "names": names, "line": line, "level": level,
                "resolved": resolve_py(module, level, importer, repo_root)}
    return None


def _docstring(body, data: bytes) -> str | None:
    if body is None or not body.children:
        return None
    first = body.children[0]
    if first.type == "expression_statement":
        s = T.first_named(first, "string")
        if s is not None:
            return _text(s, data)
    return None


def _collect_calls(fn_node, data: bytes) -> list[dict]:
    # Nested function bodies belong to the inner symbol: their calls are
    # recorded on the inner function only, not re-attributed to every
    # enclosing function (which produced spurious `likely` edges). Lambdas
    # have no symbol record, so their calls stay with the enclosing
    # function; decorator/default-arg edge cases are documented in the
    # perf-07 commit (negligible vs the removed double-attribution).
    nested = [(n.start_byte, n.end_byte) for n in T.walk(fn_node)
              if n.type == "function_definition" and n is not fn_node]
    calls = []
    for node in T.walk(fn_node):
        if node.type != "call":
            continue
        s, e = node.start_byte, node.end_byte
        if any(a <= s and e <= b for (a, b) in nested):
            continue
        fn = node.children[0] if node.children else None
        if fn is None:
            continue
        if fn.type == "identifier":
            calls.append({"name": _text(fn, data), "line": T.line_of(fn.start_point)})
        elif fn.type == "attribute":
            obj = T.first_named(fn, "identifier")
            attr = [c for c in fn.children if c.type == "identifier"]
            if obj is not None and len(attr) >= 2:
                calls.append({"name": f"{_text(attr[0], data)}.{_text(attr[-1], data)}",
                              "line": T.line_of(fn.start_point)})
    return calls


def _header_bases_and_kwargs(def_node, data: bytes):
    arglist = T.first_named(def_node, "argument_list")
    bases: list[str] = []
    kwargs: dict[str, str] = {}
    if arglist is None:
        return bases, kwargs
    for child in arglist.children:
        if child.type == "identifier":
            bases.append(_text(child, data))
        elif child.type == "dotted_name":
            bases.append(_dotted(child, data))
        elif child.type == "keyword_argument":
            kids = [c for c in child.children if c.type not in ("=", ":", ",")]
            if len(kids) >= 2 and kids[0].type == "identifier":
                kwargs[_text(kids[0], data)] = _text(kids[1], data)
    return bases, kwargs


def extract_py(path: Path, data: bytes, repo_root: Path) -> dict:
    tree = T.parse_bytes("python", data)
    root = tree.root_node
    rel = path.relative_to(repo_root).as_posix()
    importer = path
    symbols: list[dict] = []
    imports: list[dict] = []
    routes: list[dict] = []
    router_defs: list[dict] = []
    include_routers: list[dict] = []
    models: list[dict] = []
    file_lines = len(T.lines_of(data))

    def router_prefix_for(var: str | None):
        if var is None:
            return None, True
        for rd in router_defs:
            if rd["var"] == var:
                return rd["prefix"], not rd["prefix_known"]
        return None, True

    def record(node, stack: list[str], decorators: list[dict]):
        ctype = node.type
        name_node = inner_name(node)
        if name_node is None:
            return
        name = _text(name_node, data)
        kind = "class" if ctype == "class_definition" else ("method" if stack else "function")
        qual = ".".join([*stack, name])
        start = T.line_of(node.start_point)
        end = T.line_of(node.end_point)
        body = T.first_named(node, "block")
        doc = _docstring(body, data) if ctype == "function_definition" else None
        params = None
        if ctype == "function_definition":
            pnode = T.first_named(node, "parameters")
            params = _text(pnode, data) if pnode is not None else None
        bases = None
        if ctype == "class_definition":
            bases, _ = _header_bases_and_kwargs(node, data)
        symbols.append({
            "kind": kind, "name": name, "qualname": qual,
            "parent": stack[-1] if stack else None,
            "start_line": start, "end_line": end, "signature_line": start,
            "docstring": doc, "params": params, "bases": bases,
            "decorators": decorators,
            "calls": _collect_calls(node, data) if ctype == "function_definition" else [],
        })
        for dec in decorators:
            route = _decorator_route(dec, name, qual, start, end, data)
            if route is not None:
                prefix, unknown = router_prefix_for(route["router_var"])
                route.update({"file": rel, "router_prefix": prefix,
                              "prefix_unknown": unknown})
                routes.append(route)
        if ctype == "class_definition":
            model = _class_model(node, name, qual, start, end, data)
            if model is not None:
                model["file"] = rel
                models.append(model)
            visit(T.first_named(node, "block") or node, [*stack, name])

    def visit(node, stack: list[str], decorators: list[dict] | None = None):
        nonlocal symbols, imports, routes, router_defs, include_routers, models
        decorators = decorators or []
        for child in node.children:
            ctype = child.type
            if ctype in ("import_statement", "import_from_statement"):
                imp = _parse_imports(child, data, importer, repo_root)
                if imp is not None:
                    imports.append(imp)
            elif ctype == "decorated_definition":
                decs = []
                inner = None
                for part in child.children:
                    if part.type == "decorator":
                        decs.append({"text": _text(part, data),
                                     "line": T.line_of(part.start_point)})
                    elif part.type in ("function_definition", "class_definition"):
                        inner = part
                if inner is not None:
                    record(inner, stack, decs)
            elif ctype in ("function_definition", "class_definition"):
                record(child, stack, decorators)
            elif ctype == "expression_statement":
                _find_assignments(child, router_defs, include_routers, data)
                for sub in child.children:
                    if sub.type in ("function_definition", "class_definition",
                                    "decorated_definition", "block"):
                        visit(sub, stack)
            elif ctype == "block":
                visit(child, stack)
            elif ctype not in ("string",):
                # Recurse into anything else (if/for/try bodies etc.).
                if child.children:
                    visit(child, stack)

    visit(root, [])
    for node in T.walk(root):
        if node.type == "call":
            _maybe_include_router(node, data, include_routers)
    # Router prefixes may be defined after use; join afterwards.
    for route in routes:
        if route["prefix_unknown"]:
            prefix, unknown = router_prefix_for(route["router_var"])
            route.update({"router_prefix": prefix, "prefix_unknown": unknown})
    return {"path": rel, "language": "python", "status": "parsed",
            "file_lines": file_lines, "has_error": root.has_error,
            "symbols": symbols, "imports": imports, "routes": routes,
            "router_defs": router_defs, "include_routers": include_routers,
            "models": models}


def inner_name(def_node):
    for c in def_node.children:
        if c.type == "identifier":
            return c
    return None


def _decorator_route(dec: dict, func_name: str, qual: str, start: int, end: int, data: bytes) -> dict | None:
    import re
    match = re.match(r"@([A-Za-z_][A-Za-z0-9_]*)\.(get|post|put|patch|delete)\b", dec["text"])
    if not match:
        return None
    var, method = match.group(1), match.group(2)
    # First positional string literal in the decorator call.
    path = None
    str_match = re.search(r"""\(\s*["']([^"']+)["']""", dec["text"])
    if str_match:
        path = str_match.group(1)
    return {"method": method, "path": path, "handler": qual,
            "handler_lines": [start, end], "decorator_line": dec["line"],
            "router_var": var}


def _maybe_include_router(call, data: bytes, include_routers: list):
    fn = call.children[0] if call.children else None
    if fn is None or fn.type != "attribute":
        return
    idents = [c for c in fn.children if c.type == "identifier"]
    if len(idents) < 2 or T.text_of(idents[-1], data) != "include_router":
        return
    obj = T.text_of(idents[0], data)
    router_arg, prefix, known = None, None, False
    for arg in _call_args(call, data):
        if arg.type == "keyword_argument":
            parts = [c for c in arg.children if c.type not in ("=", ":", ",")]
            if len(parts) >= 2 and T.text_of(parts[0], data) == "prefix":
                lit = _string_value(parts[1], data)
                prefix, known = (lit, True) if lit is not None else (None, False)
        elif router_arg is None and arg.type == "identifier":
            router_arg = T.text_of(arg, data)
    include_routers.append({"object": obj, "router": router_arg, "prefix": prefix,
                            "prefix_known": known,
                            "line": T.line_of(call.start_point)})


def _find_assignments(node, router_defs: list, include_routers: list, data: bytes):
    for sub in T.walk(node):
        if sub.type != "assignment":
            continue
        kids = [c for c in sub.children if c.type == "identifier"]
        if not kids:
            continue
        var = T.text_of(kids[0], data)
        value = sub.children[-1]
        if value.type != "call":
            continue
        callee = value.children[0] if value.children else None
        if callee is None or callee.type != "identifier":
            continue
        callee_name = T.text_of(callee, data)
        args = _call_args(value, data)
        if callee_name in ("APIRouter", "FastAPI"):
            prefix, known = "", True
            for arg in args:
                if arg.type == "keyword_argument":
                    parts = [c for c in arg.children if c.type not in ("=", ":", ",")]
                    if len(parts) >= 2 and T.text_of(parts[0], data) == "prefix":
                        lit = _string_value(parts[1], data)
                        if lit is not None:
                            prefix, known = lit, True
                        else:
                            prefix, known = None, False
            router_defs.append({"var": var, "prefix": prefix, "prefix_known": known,
                                "line": T.line_of(sub.start_point)})


def _class_model(class_node, name: str, qual: str, start: int, end: int, data: bytes) -> dict | None:
    bases, kwargs = _header_bases_and_kwargs(class_node, data)
    if kwargs.get("table") != "True":
        return None
    body = T.first_named(class_node, "block")
    fields: list[dict] = []
    table = name.lower()
    table_inferred = True
    if body is not None:
        for stmt in body.children:
            if stmt.type != "expression_statement":
                continue
            for sub in stmt.children:
                if sub.type != "assignment":
                    continue
                kids = sub.children
                ident = next((c for c in kids if c.type == "identifier"), None)
                typ = next((c for c in kids if c.type == "type"), None)
                if ident is None:
                    continue
                fname = T.text_of(ident, data)
                if fname == "__tablename__":
                    val = kids[-1]
                    lit = _string_value(val, data)
                    if lit is not None:
                        table, table_inferred = lit, False
                elif typ is not None:
                    fields.append({"name": fname, "type": T.text_of(typ, data),
                                   "line": T.line_of(ident.start_point)})
    return {"class": name, "qualname": qual, "lines": [start, end],
            "table": table, "table_inferred": table_inferred,
            "bases": bases, "fields": fields}
