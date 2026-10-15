"""T6: malicious repository (huge files, symlinks, submodules, pathological
syntax). Boundary: ingest + parser. Controls: size caps, symlink/submodule
refusal, isolated parse workers with timeout. Thin regression over the
Phase 2/3 fixture properties on a hostile scratch tree.
"""
from mentor.ingest import filters as F
from mentor.ingest import manifest as M
from mentor.parse import parse_worker as W


def test_hostile_tree_never_followed_or_executed(tmp_path):
    root = tmp_path / "hostile"
    root.mkdir()
    (root / "big.py").write_bytes(b"x = 1\n" * 300000)  # >1 MB
    (root / "ok.py").write_text("def fine():\n    return 1\n",
                                encoding="utf-8")
    import os
    try:
        os.symlink(str(root / "ok.py"), str(root / "link.py"))
        have_link = True
    except OSError:
        have_link = False
    manifest = M.build_manifest(root, "hostile")
    by_path = {e["path"]: e for e in manifest["files"]}
    assert by_path["big.py"]["skipped"] == "size"
    if have_link:
        assert by_path["link.py"]["skipped"] == "symlink"
    res = W.parse_one(root, "ok.py", timeout_s=10.0)
    assert res.get("status") == "parsed"


def test_deep_nesting_does_not_hang(tmp_path):
    root = tmp_path / "nest"
    root.mkdir()
    (root / "n.py").write_text("x = [" * 3000 + "]" * 3000 + "\n",
                               encoding="utf-8")
    res = W.parse_one(root, "n.py", timeout_s=10.0)
    assert res.get("status") in ("parsed", "parse_failed")
    assert F.safe_join(root.resolve(), "n.py").is_file()
