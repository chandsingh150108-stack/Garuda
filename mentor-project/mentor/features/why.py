"""History provenance for "why" questions (spec Phase 14, D14.1).

Code proves what/how; only Git history can record intent — and even then, a
commit message records what someone WROTE, not necessarily the truth
(untrusted input per Global Rule 4). HISTORY citations therefore mean
"recorded rationale", displayed with SHA/author/date; anything else causal is
INFERRED (separate section) or UNKNOWN.

Reads ONLY via `git blame --porcelain -L` and `git log --follow` (read-only
subprocesses, shell=False, timeouts; repository code is never executed).
`gh` PR lookup exists but is OFF by default and never used in tests.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

GIT_TIMEOUT_S = 30


def _git(repo: Path, *args: str) -> str:
    # encoding=utf-8: commit summaries contain emoji; the Windows locale
    # codec (cp1252) cannot decode them.
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=GIT_TIMEOUT_S, shell=False)
    if proc.returncode != 0:
        raise OSError(f"git {' '.join(args)} failed: {proc.stderr[:200]}")
    return proc.stdout


def blame_range(repo: Path, path: str, start: int,
                end: int) -> list[dict]:
    """Per-commit attribution for lines start..end (porcelain).

    Returns [{sha, author, date, subject, lines:[...]}] in line order,
    consecutive same-commit lines merged. Dates are author-time ISO UTC.
    """
    import datetime
    out = _git(repo, "blame", "--porcelain", "-L", f"{start},{end}", "--", path)
    records: list[dict] = []
    current: dict | None = None
    headers: dict[str, dict] = {}  # sha -> last full header (porcelain
    # compresses repeats: later groups from one commit omit author lines)
    for line in out.splitlines():
        m = re.fullmatch(r"([0-9a-f]{40}) (\d+) (\d+)( \d+)?", line)
        if m:
            sha = m.group(1)
            if current is None or current["sha"] != sha:
                known = headers.get(sha, {})
                current = {"sha": sha, "author": known.get("author", ""),
                           "date": known.get("date", ""),
                           "subject": known.get("subject", ""), "lines": []}
                records.append(current)
            # THIRD field is the final (pinned-commit) line number.
            current["lines"].append(int(m.group(3)))
            continue
        if current is None:
            continue
        if line.startswith("author "):
            current["author"] = line[len("author "):]
        elif line.startswith("author-time "):
            try:
                ts = int(line[len("author-time "):])
                current["date"] = datetime.datetime.fromtimestamp(
                    ts, tz=datetime.timezone.utc).strftime("%Y-%m-%d")
            except ValueError:
                current["date"] = ""
        elif line.startswith("summary "):
            current["subject"] = line[len("summary "):]
        if current["author"] or current["date"] or current["subject"]:
            headers[current["sha"]] = {
                "author": current["author"], "date": current["date"],
                "subject": current["subject"]}
    return [r for r in records if not r["sha"].startswith("0" * 8)]


def log_follow(repo: Path, path: str, n: int = 3) -> list[dict]:
    """Top-n commits touching a file (follow renames)."""
    out = _git(repo, "log", "--follow", f"-n{n}", "--format=%H|%an|%ad|%s",
               "--date=short", "--", path)
    commits = []
    for line in out.splitlines():
        parts = line.split("|", 3)
        if len(parts) == 4:
            commits.append({"sha": parts[0], "author": parts[1],
                            "date": parts[2], "subject": parts[3]})
    return commits


def history_for_symbol(repo: Path, path: str, start: int,
                       end: int) -> dict:
    """Blame for the symbol range + top-3 file history. Never raises for
    missing history: returns empty lists (caller renders UNKNOWN)."""
    try:
        blame = blame_range(repo, path, start, end)
    except Exception:
        blame = []
    try:
        commits = log_follow(repo, path)
    except Exception:
        commits = []
    return {"blame": blame, "commits": commits}


def history_blocks(history: dict, path: str = "",
                   start_id: int = 1) -> list[dict]:
    """Server-numbered H-blocks: commit records with SHA/author/date.

    Text states the RECORD ("commit X by Y records: ..."), never asserts the
    rationale is true. One block per distinct commit (blame + log merged).
    """
    seen: dict[str, dict] = {}
    for entry in history.get("blame", []) + history.get("commits", []):
        sha = entry["sha"]
        if sha not in seen:
            seen[sha] = entry
    blocks = []
    for i, (sha, entry) in enumerate(seen.items(), start=start_id):
        lines = ",".join(str(n) for n in entry.get("lines", [])) or "-"
        blocks.append({
            "id": f"H{i}", "kind": "history",
            "path": entry.get("path", "") or path,
            "lines": lines,
            "text": (f"commit {sha[:12]} by {entry.get('author', '?')} "
                     f"on {entry.get('date', '?')} records: "
                     f"{entry.get('subject', '')}"),
            "sha": sha, "author": entry.get("author", ""),
            "date": entry.get("date", "")})
    return blocks


def gh_pr(pr_number: int, *, enabled: bool = False,
          timeout_s: float = 30.0) -> dict | None:
    """Optional PR lookup via `gh` (D14.3). OFF by default: returns None
    without attempting any network. When enabled, returns a HISTORY item
    {pr, url, title, author} or None on any failure."""
    if not enabled:
        return None
    try:
        proc = subprocess.run(
            ["gh", "pr", "view", str(pr_number),
             "--json", "number,title,author,url"],
            capture_output=True, text=True, timeout=timeout_s, shell=False)
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    import json
    try:
        body = json.loads(proc.stdout)
    except ValueError:
        return None
    author = body.get("author", {})
    return {"pr": body.get("number", pr_number), "url": body.get("url", ""),
            "title": body.get("title", ""),
            "author": author.get("login", "") if isinstance(author, dict)
            else str(author)}
