"""Gold-set loading + validation (spec Phase 6, D6.1-D6.3).

Every gold range must exist in a real file at the pinned commit; composition
(8/6/6/4/6) is enforced. Unanswerable items carry empty gold with recorded
absence evidence in reviewer_notes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

COMPOSITION = {"where_how": 8, "arch": 6, "flow": 6, "why": 4, "unanswerable": 6}
STATUSES = {"answer", "abstain"}


@dataclass
class GoldRange:
    path: str
    start_line: int
    end_line: int


@dataclass
class GoldItem:
    id: str
    category: str
    question: str
    expected_status: str
    gold: list[GoldRange] = field(default_factory=list)
    must_include: list[str] = field(default_factory=list)
    reviewer_notes: str = ""


@dataclass
class GoldSet:
    version: int
    items: list[GoldItem]


def load(path: Path) -> GoldSet:
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    items = [GoldItem(
        id=i["id"], category=i["category"], question=i["question"],
        expected_status=i["expected_status"],
        gold=[GoldRange(**g) for g in i.get("gold", [])],
        must_include=list(i.get("must_include", [])),
        reviewer_notes=i.get("reviewer_notes", "")) for i in doc["items"]]
    return GoldSet(version=doc.get("version", 0), items=items)


def validate(gold: GoldSet, repo_root: Path) -> list[str]:
    """Return violation strings (empty = valid)."""
    problems: list[str] = []
    counts: dict[str, int] = {}
    seen_ids: set[str] = set()
    for item in gold.items:
        if item.id in seen_ids:
            problems.append(f"{item.id}: duplicate id")
        seen_ids.add(item.id)
        if item.category not in COMPOSITION:
            problems.append(f"{item.id}: unknown category {item.category}")
        else:
            counts[item.category] = counts.get(item.category, 0) + 1
        if item.expected_status not in STATUSES:
            problems.append(f"{item.id}: bad status {item.expected_status}")
        if item.expected_status == "answer" and not item.gold:
            problems.append(f"{item.id}: answerable item has empty gold")
        for g in item.gold:
            target = repo_root / g.path
            if not target.is_file() or target.is_symlink():
                problems.append(f"{item.id}: missing path {g.path}")
                continue
            total = len(target.read_bytes().decode("utf-8", errors="replace").splitlines())
            if not (1 <= g.start_line <= g.end_line <= total):
                problems.append(f"{item.id}: range [{g.start_line},{g.end_line}]"
                                f" outside 1..{total} in {g.path}")
    for category, want in COMPOSITION.items():
        got = counts.get(category, 0)
        if got != want:
            problems.append(f"composition {category}: want {want}, got {got}")
    return problems


def answerable(gold: GoldSet) -> list[GoldItem]:
    return [i for i in gold.items if i.expected_status == "answer"]
