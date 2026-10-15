"""Guided tours: BFS flow traces with validated steps (spec Phase 13).

Traversal (D13.2): breadth-first from the route handler over resolved edges
first, then `likely` edges, depth ≤ 3, fan-out ≤ 8 per node. A hop is
`calls` only for import-resolved definitions (C9/D3.3); otherwise
"likely calls, by name" (D13.4). A step is kept only with validator-accepted
citation evidence (D13.3); drops are logged in the tour record.

Tours are precomputed, cached with dependency hashes (Phase 17 model), and
served by the API. Narration uses the Phase 9 path per step with a
deterministic fallback (signature + docstring facts), so structure never
depends on the model.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from pathlib import Path

import yaml

from mentor.features import mermaid as M

MAX_DEPTH = 3
MAX_FAN = 8


def load_definition(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _chunk_evidence(con, sha: str, path: str, start: int,
                    end: int) -> list[dict]:
    rows = con.execute(
        "SELECT chunk_id, start_line, end_line FROM chunks"
        " WHERE snapshot_sha = ? AND path = ?"
        " AND NOT (end_line < ? OR start_line > ?) ORDER BY start_line",
        (sha, path, start, end)).fetchall()
    return [{"chunk_id": c, "path": path, "lines": f"{s}-{e}"}
            for c, s, e in rows]


def find_seed(con, sha: str, definition: dict) -> dict | None:
    """Resolve the seed route+handler to a step-0 candidate from the index."""
    row = con.execute(
        "SELECT file, handler_start, handler_end FROM routes"
        " WHERE snapshot_sha = ? AND method = ? AND handler = ?"
        " AND instr(path, ?) > 0",
        (sha, definition["method"], definition["handler"],
         definition["route"])).fetchone()
    if row is None:
        row = con.execute(
            "SELECT file, handler_start, handler_end FROM routes"
            " WHERE snapshot_sha = ? AND handler = ?",
            (sha, definition["handler"])).fetchone()
    if row is None:
        return None
    file, start, end = row
    ev = _chunk_evidence(con, sha, file, start, end)
    if not ev:
        return None
    return {"symbol": definition["handler"], "file": file,
            "start": start, "end": end, "hop": "route",
            "hop_detail": f"{definition['method'].upper()} {definition['route']}",
            "evidence": ev}


def _import_rows(con, sha: str, caller_file: str) -> list:
    """Import rows with names normalized to {module, names, target}; entries
    are {name, alias} dicts (Phase 3 stores both)."""
    out = []
    for module, names_json, target in con.execute(
            "SELECT module, names_json, resolved FROM imports"
            " WHERE snapshot_sha = ? AND path = ?", (sha, caller_file)):
        try:
            imported = json.loads(names_json)
        except ValueError:
            continue
        names = []
        if isinstance(imported, list):
            for entry in imported:
                if isinstance(entry, dict):
                    names.append((entry.get("name", ""),
                                  entry.get("alias") or entry.get("name", "")))
                elif isinstance(entry, str):
                    names.append((entry, entry))
        out.append({"module": module or "", "names": names, "target": target})
    return out


def _submodule_fallback(target: str | None, callee: str) -> str | None:
    """`from package import submodule` resolves to the package __init__
    (ours are empty re-export shims); the definition lives in the sibling
    submodule file."""
    if target and target.endswith("__init__.py"):
        import os
        sibling = os.path.join(os.path.dirname(target), callee + ".py")
        return sibling.replace("\\", "/")
    return target


def _symbol_in(con, sha: str, path: str, name: str):
    return con.execute(
        "SELECT path, start_line, end_line FROM symbols"
        " WHERE snapshot_sha = ? AND path = ? AND name = ?"
        " ORDER BY start_line LIMIT 1", (sha, path, name)).fetchone()


BUILTINS = frozenset({
    "len", "str", "int", "float", "bool", "dict", "list", "set", "tuple",
    "print", "range", "isinstance", "issubclass", "hasattr", "getattr",
    "super", "enumerate", "zip", "map", "filter", "sorted", "reversed",
    "min", "max", "sum", "any", "all", "abs", "round", "repr", "type",
})


def _caller_params(con, sha: str, caller_file: str, symbol: str) -> set[str]:
    row = con.execute("SELECT params FROM symbols WHERE snapshot_sha = ?"
                      " AND path = ? AND qualname = ?",
                      (sha, caller_file, symbol)).fetchone()
    if not row or not row[0]:
        return set()
    return set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", row[0]))


def _line_text(con, sha: str, path: str, line: int) -> str:
    row = con.execute("SELECT text, start_line FROM chunks"
                      " WHERE snapshot_sha = ? AND path = ?"
                      " AND start_line <= ? AND end_line >= ?"
                      " ORDER BY start_line LIMIT 1",
                      (sha, path, line, line)).fetchone()
    if row is None:
        return ""
    lines = row[0].splitlines()
    idx = line - row[1]
    return lines[idx] if 0 <= idx < len(lines) else ""


def _resolve_callee(con, sha: str, caller_file: str,
                    callee: str) -> tuple | None:
    """Import-resolved definition (C9): the caller file imports `callee` and
    a symbol with that name is defined in the resolved target file
    (with submodule fallback for package __init__ targets)."""
    for row in _import_rows(con, sha, caller_file):
        if not any(n == callee or a == callee for n, a in row["names"]):
            continue
        target = _submodule_fallback(row["target"], callee)
        if not target:
            continue
        sym = _symbol_in(con, sha, target, callee)
        if sym:
            return sym
    # Same-module definition (a definition next to the caller resolves too).
    return _symbol_in(con, sha, caller_file, callee)


def _outgoing(con, sha: str, symbol: str,
              caller_file: str) -> tuple[list, list, list]:
    """(resolved, likely, drops) outgoing hops for a caller symbol.

    `module.attr(...)` call sites resolve the ATTRIBUTE in the module's file
    (e.g. `crud.create_user` -> create_user in backend/app/crud.py). External
    imports, builtins, and caller parameters are dropped with reasons — tours
    trace first-party flow, not frameworks.
    """
    rows = con.execute(
        "SELECT to_ref, detail_json FROM edges WHERE snapshot_sha = ?"
        " AND kind = 'call' AND label = 'likely' AND from_ref = ?",
        (sha, symbol)).fetchall()
    params = _caller_params(con, sha, caller_file, symbol)
    imports = _import_rows(con, sha, caller_file)
    resolved, likely, drops = [], [], []
    seen: set[str] = set()
    ordered = sorted(rows, key=lambda r: _line_of(r[1]))
    for callee, detail in ordered:
        try:
            info = json.loads(detail)
        except ValueError:
            info = {}
        # Same-named symbols in different files share from_ref: only edges
        # really emitted from the caller's file apply (C9 precision).
        if (info.get("from_file") or "").replace("\\", "/") != caller_file:
            continue
        line = info.get("from_line") or 0
        site = _line_text(con, sha, caller_file, line)
        attrs = re.findall(rf"\b{re.escape(callee)}\.([A-Za-z_][A-Za-z0-9_]*)",
                           site)
        # Bare callee hop only when it resolves to a definition; otherwise
        # the attribute hops below carry the meaning (e.g. `crud` alone is
        # noise next to resolved `crud.create_user`).
        bare_target = _resolve_callee(con, sha, caller_file, callee)
        play_bare = bare_target is not None or not attrs
        candidates = ([None] if play_bare else []) + attrs
        for attr in candidates:
            key = f"{callee}.{attr}" if attr else callee
            if key in seen:
                continue
            seen.add(key)
            name = attr or callee
            if not attr and name in params:
                drops.append({"callee": key, "reason": "caller parameter"})
                continue
            if not attr and name in BUILTINS:
                drops.append({"callee": key, "reason": "builtin"})
                continue
            mentioned = [r for r in imports
                         if any(n == callee or a == callee
                                for n, a in r["names"])]
            external = (bool(mentioned) and
                        all(r["target"] is None for r in mentioned))
            if external and not _symbol_in(con, sha, caller_file, name):
                drops.append({"callee": key, "reason": "external import"})
                continue
            target = None
            if attr:
                for r in mentioned:
                    for tfile in (_submodule_fallback(r["target"], callee),
                                  r["target"]):
                        if tfile and _symbol_in(con, sha, tfile, attr):
                            target = _symbol_in(con, sha, tfile, attr)
                            break
                    if target:
                        break
            else:
                target = bare_target
            hop = {"callee": key, "next_symbol": name, "line": line,
                   "target": target}
            (resolved if target else likely).append(hop)
    return resolved, likely, drops


def _line_of(detail: str) -> int:
    try:
        return json.loads(detail).get("from_line") or 0
    except ValueError:
        return 0


def traverse(db: Path, sha: str, seed: dict) -> tuple[list[dict], list[dict]]:
    """BFS over call hops. Returns (steps, drops). Deterministic."""
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        steps = [{"n": 0, "symbol": seed["symbol"], "file": seed["file"],
                  "start": seed["start"], "end": seed["end"], "hop": "route",
                  "from": None,
                  "hop_detail": seed["hop_detail"], "evidence": seed["evidence"]}]
        drops: list[dict] = []
        visited = {(seed["file"], seed["symbol"])}
        frontier = [(seed["symbol"], seed["file"], 0)]
        while frontier:
            symbol, caller_file, depth = frontier.pop(0)
            if depth >= MAX_DEPTH:
                continue
            resolved, likely, outgoing_drops = _outgoing(
                con, sha, symbol, caller_file)
            drops.extend({**d, "at": symbol} for d in outgoing_drops)
            for hop in (resolved + likely)[:MAX_FAN]:
                target = hop["target"]
                if target is not None:
                    tfile, tstart, tend = target
                    key = (tfile, hop["callee"])
                    ev = _chunk_evidence(con, sha, tfile, tstart, tend)
                    # The hop claim spans two places: cite the definition AND
                    # the call site, so the validator can check both names.
                    site = _chunk_evidence(con, sha, caller_file,
                                           hop["line"], hop["line"])
                    ev = ev + [c for c in site
                               if c["chunk_id"] not in {e["chunk_id"] for e in ev}]
                    hop_label, detail = "calls", hop["callee"]
                    loc = (tfile, tstart, tend, hop["callee"])
                else:
                    # Likely hop: evidence is the call-site chunk itself.
                    ev = _chunk_evidence(con, sha, caller_file,
                                         hop["line"], hop["line"])
                    hop_label = "likely calls, by name"
                    detail = hop["callee"]
                    loc = (caller_file, hop["line"], hop["line"],
                           hop["callee"])
                    key = (caller_file, hop["callee"], hop["line"])
                if not ev:
                    drops.append({"at": symbol, "callee": hop["callee"],
                                  "reason": "no evidence chunk"})
                    continue
                if key in visited:
                    continue
                visited.add(key)
                steps.append({"n": len(steps), "symbol": loc[3],
                              "file": loc[0], "start": loc[1], "end": loc[2],
                              "hop": hop_label, "from": symbol,
                              "hop_detail": detail,
                              "evidence": ev})
                if target is not None:
                    frontier.append((hop["next_symbol"], tfile, depth + 1))
        return steps, drops
    finally:
        con.close()


def _bare(dotted: str) -> str:
    return dotted.split(".")[-1]


def deterministic_narration(step: dict, docstring: str = "") -> tuple[str, str]:
    """Fallback narration from code facts only (no model). Bare identifiers,
    no paths/URLs — shaped to pass the same validator as LLM text."""
    if step["hop"] == "route":
        title = f"Enter at `{step['symbol']}`"
        text = (f"`{step['symbol']}` handles {step['hop_detail']}."
                + (f" {docstring}" if docstring else ""))
    elif step["hop"] == "calls":
        title = f"Call `{_bare(step['hop_detail'])}`"
        text = (f"`{step.get('from') or '???'}` calls "
                f"`{_bare(step['hop_detail'])}`.")
    else:
        title = f"Likely call `{_bare(step['hop_detail'])}`"
        text = (f"`{step.get('from') or '???'}` likely calls "
                f"`{_bare(step['hop_detail'])}`, by name.")
    return title, text


def narrate(db: Path, sha: str, step: dict, adapter=None) -> dict:
    """Per-step title+explanation through the Phase 9 path with validation.
    Falls back to deterministic narration; failures are reported, never
    raised. Returns the step with title/explanation/narrated_by."""
    from mentor.answer import validator as V
    from mentor.features import summaries as SU
    title, text = deterministic_narration(step)
    narrated_by = "deterministic"
    if adapter is not None:
        from mentor import config as CFG
        from mentor.llm import gateway as GW
        suffix = f" {CFG.LLM_SYSTEM_SUFFIX}" if CFG.LLM_SYSTEM_SUFFIX else ""
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        try:
            rows = con.execute(
                f"SELECT chunk_id, text FROM chunks WHERE chunk_id IN "
                f"({','.join('?' for _ in step['evidence'])})",
                tuple(e["chunk_id"] for e in step["evidence"])).fetchall()
        finally:
            con.close()
        texts = {c: t for c, t in rows}
        ev_ids = [f"E{i + 1}" for i in range(len(step["evidence"]))]
        blocks = [{"id": eid, "text": texts.get(e["chunk_id"], "")}
                  for e, eid in zip(step["evidence"], ev_ids)]
        prompt = (
            "Describe this code step in one short title and one paragraph "
            "for a newcomer. Respond with JSON "
            '{"title": "...", "text": "..."}. Put backticks ONLY around '
            "BARE function, class, and variable names that appear verbatim "
            "in the evidence — never module prefixes (`crud.x` is forbidden, "
            "write `x`), never file names, paths, or anything else."
            + suffix + " Evidence:\n" +
            "\n".join(f"[{eid}] {step['file']}:{e['lines']}\n{t}"
                      for e, eid, t in zip(step["evidence"], ev_ids,
                                           [texts.get(e["chunk_id"], "")
                                            for e in step["evidence"]])))
        try:
            parsed = GW.generate(
                adapter,
                [{"role": "system", "content": prompt},
                 {"role": "user", "content": f"Step: {step['hop']} "
                                            f"{step['hop_detail']} in "
                                            f"{step['file']}"}],
                {"type": "object"}, {"max_tokens": 256}, timeout_s=120.0)
        except GW.GatewayError:
            parsed = None
        if isinstance(parsed, dict) and parsed.get("title") and parsed.get("text"):
            # Module prefixes (`crud.x`) name the call site, not the
            # definition chunk: normalize to the bare identifier before
            # validating AND serving, so V4 checks what is displayed.
            norm = re.sub(r"`([A-Za-z_][A-Za-z0-9_]*)\.([A-Za-z_][A-Za-z0-9_]*)`",
                          r"`\2`", str(parsed["text"])[:600])
            probe = {"status": "answer",
                     "segments": [{"text": norm,
                                   "kind": "fact",
                                   "evidence_ids": ev_ids[:3] or ev_ids}],
                     "missing": []}
            evidence_text = "\n".join(texts.values())
            if not V.validate(probe, blocks) and SU.accept_title(
                    str(parsed["title"])[:80], evidence_text):
                title = str(parsed["title"])[:80]
                text = norm
                narrated_by = "llm"
    # D13.3: deterministic narration passes through the same validator;
    # a step whose own narration is rejected is dropped by the caller.
    if narrated_by == "deterministic":
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        try:
            rows = con.execute(
                f"SELECT chunk_id, text FROM chunks WHERE chunk_id IN "
                f"({','.join('?' for _ in step['evidence'])})",
                tuple(e["chunk_id"] for e in step["evidence"])).fetchall()
        finally:
            con.close()
        texts = {c: t for c, t in rows}
        ev_ids = [f"E{i + 1}" for i in range(len(step["evidence"]))]
        blocks = [{"id": eid, "text": texts.get(e["chunk_id"], "")}
                  for e, eid in zip(step["evidence"], ev_ids)]
        probe = {"status": "answer",
                 "segments": [{"text": text, "kind": "fact",
                               "evidence_ids": ev_ids[:3] or ev_ids}],
                 "missing": []}
        if V.validate(probe, blocks):
            return None
    return {**step, "title": title, "explanation": text,
            "narrated_by": narrated_by}


def _short(path: str) -> str:
    return path.rsplit("/", 1)[-1].rsplit(".", 1)[0]


def sequence_mermaid(tour: dict) -> str:
    """Deterministic sequenceDiagram: participants from paths, messages from
    hop labels. IDs are positional (P0..); labels escaped by code."""
    parts: list[str] = []
    seen: dict[str, str] = {}

    def pid(path: str) -> str:
        if path not in seen:
            seen[path] = f"P{len(seen)}"
        return seen[path]

    lines = ["sequenceDiagram"]
    for step in tour["steps"]:
        pid(step["file"])
    for path, ident in seen.items():
        lines.append(f"    participant {ident} as {M.escape_label(_short(path))}")
    prev = None
    for step in tour["steps"]:
        cur = seen[step["file"]]
        if prev is None:
            lines.append(f"    Note over {cur}: {M.escape_label(step['title'])}")
        elif cur == prev:
            lines.append(f"    Note over {cur}: {M.escape_label(step['title'])}")
        else:
            msg = (f"{step['hop']} {step['hop_detail']}"
                   if step["hop"] != "route" else step["hop_detail"])
            lines.append(f"    {prev}->>{cur}: {M.escape_label(msg)}")
        prev = cur
    return "\n".join(lines) + "\n"


def check_sequence(text: str) -> list[str]:
    """Structural check for our sequence diagrams."""
    problems: list[str] = []
    lines = text.splitlines()
    if not lines or lines[0].strip() != "sequenceDiagram":
        return ["missing sequenceDiagram header"]
    participants: set[str] = set()
    for lineno, line in enumerate(lines[1:], start=2):
        s = line.strip()
        m = re.fullmatch(r"participant (P[0-9]+) as (.+)", s)
        if m:
            participants.add(m.group(1))
            continue
        m = re.fullmatch(r"(P[0-9]+)->>(P[0-9]+): (.+)", s)
        if m:
            if m.group(1) not in participants or m.group(2) not in participants:
                problems.append(f"line {lineno}: unknown participant")
            continue
        m = re.fullmatch(r"Note over (P[0-9]+): (.+)", s)
        if m:
            if m.group(1) not in participants:
                problems.append(f"line {lineno}: unknown participant")
            continue
        problems.append(f"line {lineno}: unrecognized statement")
    return problems


def dep_hashes(db: Path, sha: str, tour: dict) -> dict:
    """Content hashes of every file the tour depends on (Phase 17 model)."""
    import sqlite3 as lite
    paths = sorted({s["file"] for s in tour["steps"]})
    con = lite.connect(f"file:{db}?mode=ro", uri=True)
    try:
        out = {}
        for path in paths:
            row = con.execute("SELECT sha256 FROM files"
                              " WHERE snapshot_sha = ? AND path = ?",
                              (sha, path)).fetchone()
            # files table may lack hashes for skipped rows; fall back to chunks.
            out[path] = row[0] if row and row[0] else _chunks_hash(con, sha, path)
        return out
    finally:
        con.close()


def _chunks_hash(con, sha: str, path: str) -> str:
    import hashlib
    rows = con.execute("SELECT content_hash FROM chunks"
                       " WHERE snapshot_sha = ? AND path = ? ORDER BY start_line",
                       (sha, path)).fetchall()
    return hashlib.sha256("\n".join(r[0] for r in rows).encode()).hexdigest()


def build(db: Path, sha: str, definition: dict, adapter=None) -> dict:
    """Full tour: seed -> traverse -> narrate -> diagrams -> hashes."""
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        seed = find_seed(con, sha, definition)
    finally:
        con.close()
    if seed is None:
        raise ValueError(f"seed not found: {definition['name']}")
    steps, drops = traverse(db, sha, seed)
    tour = {"name": definition["name"], "question": definition["question"],
            "sha": sha, "seed": seed, "steps": [], "drops": drops}
    for step in steps:
        narrated = narrate(db, sha, step, adapter)
        if narrated is None:
            tour["drops"].append({"at": step["symbol"], "callee": "",
                                  "reason": "narration rejected by validator"})
            continue
        narrated["n"] = len(tour["steps"])
        tour["steps"].append(narrated)
    tour["sequence"] = sequence_mermaid(tour)
    tour["sequence_problems"] = check_sequence(tour["sequence"])
    tour["dep_hashes"] = dep_hashes(db, sha, tour)
    return tour


def save(path: Path, tour: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(tour, indent=1, sort_keys=True), encoding="utf-8")


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def is_stale(db: Path, sha: str, tour: dict) -> bool:
    """True when any dependency hash changed (Phase 17 freshness input)."""
    return dep_hashes(db, sha, tour) != tour.get("dep_hashes", {})
