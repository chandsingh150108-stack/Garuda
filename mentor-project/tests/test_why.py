"""Phase 14 gate: history collection, H-blocks, why-path, gh-offline."""
from pathlib import Path

from mentor.answer import qa as QA
from mentor.features import why as W
from tests.socket_guard import SocketGuard

REPO = Path("data/repos/fst")
DB = Path("data/indexes/fst.sqlite")
SHA = "7257e606cb94eada1dca40173e2b7f99dd549bc6"


class ScriptAdapter:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = 0

    def complete(self, messages, schema, options, timeout_s):
        self.calls += 1
        return self.outcomes[min(self.calls - 1, len(self.outcomes) - 1)]


def test_blame_range_returns_sha_author_date():
    blame = W.blame_range(REPO, "backend/app/api/routes/users.py", 147, 147)
    assert blame, "blame must attribute the handler def line"
    first = blame[0]
    assert len(first["sha"]) == 40 and first["author"] and first["date"]
    assert first["lines"] == [147]  # final (pinned) line numbers
    assert all("author" in b and "subject" in b for b in blame)


def test_log_follow_returns_recent_commits():
    commits = W.log_follow(REPO, "backend/app/api/routes/users.py", n=3)
    assert len(commits) == 3
    assert all(len(c["sha"]) == 40 and c["date"] for c in commits)


def test_history_blocks_state_records_not_truth():
    history = W.history_for_symbol(REPO, "backend/app/api/routes/users.py",
                                   147, 159)
    blocks = W.history_blocks(history, "backend/app/api/routes/users.py")
    assert blocks and all(b["id"].startswith("H") for b in blocks)
    assert all("records:" in b["text"] for b in blocks)
    assert all(len(b["sha"]) == 40 for b in blocks)


def test_why_path_attaches_history_without_model():
    adapter = ScriptAdapter(['{"status": "abstain", "segments": [],'
                             ' "missing": ["no recorded rationale found"]}'])
    out = QA.ask(DB, SHA, "Why is registration open?", k=5, adapter=adapter,
                 why=True, repo_path=REPO,
                 tau_score=0.0, tau_cov=0.0)
    assert out["status"] == "abstain"
    assert adapter.calls == 1
    assert out["evidence_tokens"] >= 0
    h_refs = [e for e in out.get("evidence", []) if e["id"].startswith("H")]
    assert h_refs, "why-path must attach history refs even on abstention"
    assert all("sha" not in e for e in h_refs)  # refs carry id/path/lines only


def test_why_without_repo_path_attaches_nothing():
    adapter = ScriptAdapter(['{"status": "abstain", "segments": [],'
                             ' "missing": ["x"]}'])
    out = QA.ask(DB, SHA, "Why is registration open?", k=5, adapter=adapter,
                 why=True, repo_path=None, tau_score=0.0, tau_cov=0.0)
    assert out["status"] == "abstain"
    assert all(not e["id"].startswith("H") for e in out.get("evidence", []))


def test_gh_disabled_makes_no_network_call():
    assert W.gh_pr(1274, enabled=False) is None
    with SocketGuard(enforce=True) as guard:
        assert W.gh_pr(1274, enabled=False) is None
    assert guard.non_loopback == []


def test_provenance_derived_from_pointers_not_labels():
    import json
    mixed = json.dumps({"status": "answer", "segments": [
        {"text": "`authenticate` checks credentials", "kind": "fact",
         "evidence_ids": ["E1"]},
        {"text": "likely added to prevent abuse", "kind": "inference",
         "evidence_ids": ["E1"]}], "missing": []})
    adapter = ScriptAdapter([mixed])
    out = QA.ask(DB, SHA, "Why does `authenticate` exist?", k=5,
                 adapter=adapter, why=True, repo_path=REPO,
                 tau_score=0.0, tau_cov=0.0)
    assert out["status"] == "answer"
    by_kind = {s["kind"]: s["provenance"] for s in out["segments"]}
    # Inferred guesses never surface as facts: separate section by kind.
    assert by_kind == {"fact": "proven", "inference": "inferred"}
    assert all(s["kind"] != "fact" or s["provenance"] in ("proven", "history")
               for s in out["segments"])
