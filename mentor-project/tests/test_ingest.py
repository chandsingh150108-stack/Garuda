"""Phase 2 gate: sandboxed ingest fixture tests (spec Phase 2)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from mentor.ingest import filters as F
from mentor.ingest import secrets as S
from mentor.ingest.acquire import check_repo
from mentor.ingest.manifest import build_manifest

CANARY = "AKIAIOSFODNN7EXAMPLE"  # AWS docs example; fake, well-known
OUTSIDE_MARKER = "OUTSIDE-TARGET-MARKER-9f8b7a"


def make_repo(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "app.py").write_text("def hello():\n    return 'hi'\n", encoding="utf-8")
    return root


def _make_outside_link(repo: Path, tmp_path: Path):
    """Create a symlink to an outside file; fall back to a dir junction
    (no privilege needed on Windows). Returns (link_path, is_dir_link)."""
    outside_file = tmp_path / "outside.txt"
    outside_file.write_text(OUTSIDE_MARKER + "\nsecret-detail\n", encoding="utf-8")
    link = repo / "evil_link.py"
    try:
        os.symlink(str(outside_file), str(link))
        return link, False
    except OSError:
        pass  # WinError 1314 without privilege: use a junction instead
    outside_dir = tmp_path / "outside_dir"
    outside_dir.mkdir(exist_ok=True)
    (outside_dir / "payload.py").write_text(OUTSIDE_MARKER + "\n", encoding="utf-8")
    link_dir = repo / "evil_dir"
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         f"New-Item -ItemType Junction -Path '{link_dir}' -Target '{outside_dir}'"],
        capture_output=True, text=True, timeout=30,
    )
    if proc.returncode != 0:
        pytest.skip(f"cannot create symlink or junction: {proc.stderr.strip()}")
    return link_dir, True


def test_symlink_skipped_and_target_never_read(tmp_path: Path):
    repo = make_repo(tmp_path / "repo")
    link, is_dir = _make_outside_link(repo, tmp_path)
    try:
        decision = F.decide_file(link, repo)
        assert decision.include is False and decision.reason == "symlink"
        manifest = build_manifest(repo, "abc123")
        blob = json.dumps(manifest)
        assert OUTSIDE_MARKER not in blob
        assert "secret-detail" not in blob
        rows = {f["path"]: f for f in manifest["files"]}
        key = link.name
        assert rows[key]["skipped"] == "symlink"
        if is_dir:
            assert f"{key}/payload.py" not in rows  # never descended
    finally:
        if is_dir:
            try:
                os.rmdir(link)  # removes junction only, never the target
            except OSError:
                pass


def test_path_traversal_rejected(tmp_path: Path):
    repo = make_repo(tmp_path / "repo")
    with pytest.raises(ValueError):
        F.safe_join(repo, "../outside.py")
    with pytest.raises(ValueError):
        F.safe_join(repo, "sub/../../etc/passwd")
    with pytest.raises(ValueError):
        F.safe_join(repo, "C:/Windows/win.ini" if os.name == "nt" else "/etc/passwd")


def test_canary_secret_excluded_hash_only(tmp_path: Path):
    repo = make_repo(tmp_path / "repo")
    planted = repo / "settings.py"
    planted.write_text(f"aws_access_key_id = {CANARY}\n", encoding="utf-8")
    findings = S.scan_file(planted)
    assert findings and findings[0].category == "aws_access_key"
    manifest = build_manifest(repo, "abc123")
    blob = json.dumps(manifest)
    assert CANARY not in blob  # value never stored
    rows = {f["path"]: f for f in manifest["files"]}
    assert rows["settings.py"]["skipped"] == "secret"
    assert rows["settings.py"]["secret_line_hashes"]
    assert all(len(h) == 64 for h in rows["settings.py"]["secret_line_hashes"])


def test_password_kwarg_passing_is_not_a_secret(tmp_path: Path):
    # Regression: kwarg passing / variable refs must not exclude source files.
    assert S.scan_text("user = crud.create_user(password=user_in.password)\n") == []
    assert S.scan_text('hashed = data["password"]\n') == []
    assert S.scan_text("const password = randomPassword()\n") == []
    assert S.scan_text('password = "s3cr3t-value"\n') != []
    assert S.scan_text("api_key: 'abcdef123456'\n") != []


def test_oversized_skipped(tmp_path: Path):
    repo = make_repo(tmp_path / "repo")
    big = repo / "big.py"
    big.write_bytes(b"# padding\n" + b"x" * (1_000_000 + 1))
    decision = F.decide_file(big, repo)
    assert decision.include is False and decision.reason == "size"


def test_submodule_skipped(tmp_path: Path):
    repo = make_repo(tmp_path / "repo")
    vendor = repo / "vendor"
    vendor.mkdir()
    (vendor / ".git").write_text("gitdir: ../../elsewhere.git\n", encoding="utf-8")
    (vendor / "lib.py").write_text("X = 1\n", encoding="utf-8")
    assert F.is_submodule(vendor, repo) is True
    manifest = build_manifest(repo, "abc123")
    rows = {f["path"]: f for f in manifest["files"]}
    assert rows["vendor"]["skipped"] == "submodule"
    assert "vendor/lib.py" not in rows  # never descended


def test_counterfactual_map_consistent(tmp_path: Path):
    from scripts.make_counterfactual import apply_counterfactual

    src = tmp_path / "src"
    (src / "backend" / "app" / "api" / "routes").mkdir(parents=True)
    (src / "backend" / "app" / "core").mkdir(parents=True)
    # 22 functions each referenced 3+ times.
    body = "".join(f"def func{i:02d}():\n    return {i}\n" for i in range(22))
    body += "".join(f"CALL_{i} = func{i:02d}() or func{i:02d}() or func{i:02d}()\n" for i in range(22))
    routes = "".join(f'@router.get("/route{i:02d}")\ndef h{i}(): ...\n' for i in range(6))
    (src / "mod.py").write_text(body + routes, encoding="utf-8")
    (src / "backend" / "app" / "api" / "routes" / "users.py").write_text(
        '@router.post("/signup")\ndef register_user(): ...\n'
        '@router.post("/login")\ndef login_user(): ...\n'
        '@router.get("/items")\ndef list_items(): ...\n'
        '@router.get("/users")\ndef list_users(): ...\n'
        '@router.post("/token")\ndef make_token(): ...\n'
        '@router.get("/extra")\ndef extra(): ...\n',
        encoding="utf-8",
    )
    (src / "backend" / "app" / "core" / "config.py").write_text(
        'PROJECT_NAME = "demo"\nAPI_V1_STR = "/api/v1"\nSECRET_NAME = "s3cr3t"\n',
        encoding="utf-8",
    )
    rename_map = apply_counterfactual(src, tmp_path / "dst")
    assert len(rename_map["identifiers"]) == 20
    assert len(rename_map["routes"]) == 5
    assert len(rename_map["config"]) == 3
    # Old identifiers absent outside string literals (we replace everywhere).
    import re

    for path in (tmp_path / "dst").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for old in rename_map["identifiers"]:
            assert not re.search(rf"\b{re.escape(old)}\b", text), (old, path)


def test_manifest_sha_and_count(tmp_path: Path):
    repo = make_repo(tmp_path / "repo")
    (repo / "b.ts").write_text("export const x = 1;\n", encoding="utf-8")
    manifest = build_manifest(repo, "deadbeef")
    assert manifest["sha"] == "deadbeef"
    # Count matches a filesystem walk excluding pruned dirs.
    assert manifest["count"] == len(manifest["files"])
    assert manifest["count"] >= 2


def test_acquire_verifies_sha_and_dirty(tmp_path: Path):
    repo = tmp_path / "repo"
    subprocess.run(["git", "init", str(repo)], check=True,
                   capture_output=True, timeout=30)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "t@t.t"],
                   check=True, capture_output=True, timeout=30)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "t"],
                   check=True, capture_output=True, timeout=30)
    (repo / "a.py").write_text("x=1\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "."],
                   check=True, capture_output=True, timeout=30)
    subprocess.run(["git", "-C", str(repo), "commit", "-m", "init"],
                   check=True, capture_output=True, timeout=30)
    sha = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                         capture_output=True, text=True, check=True,
                         timeout=30).stdout.strip()
    info = check_repo(repo, sha)
    assert info.head_sha == sha and info.dirty is False
    (repo / "a.py").write_text("x=2\n", encoding="utf-8")
    with pytest.raises(Exception):
        check_repo(repo, sha)
    info2 = check_repo(repo, sha, allow_dirty=True)
    assert info2.dirty is True
    with pytest.raises(Exception):
        check_repo(repo, "0" * 40)
