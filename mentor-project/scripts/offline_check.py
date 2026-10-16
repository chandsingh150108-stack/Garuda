"""Offline demonstration check (spec Phase 19, D19.2).

Runs the demo question set through the in-process API with an ENFORCING
loopback-only socket guard and reports every attempted non-loopback
connection (must be zero) plus per-question cache labels.

What this proves and does NOT prove: it proves the demo code path makes no
non-loopback connection ATTEMPTS in-process. It does not prove OS-level
isolation (a socket guard cannot see subprocesses or pre-opened handles) —
recorded as residual risk 4 in SECURITY_THREAT_MODEL.md. The venue-level
proof remains "unplug the network and run the same script".
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from mentor.api import app as APP  # noqa: E402
from mentor.api import routes as R  # noqa: E402
from tests.socket_guard import SocketGuard  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Offline demo check.")
    parser.add_argument("--index", default="data/indexes/fst.sqlite")
    parser.add_argument("--repo", default="data/repos/fst")
    parser.add_argument("--repo-id", default="fst")
    parser.add_argument("--sha",
                        default="7257e606cb94eada1dca40173e2b7f99dd549bc6")
    parser.add_argument("--cache", default="data/demo_cache")
    args = parser.parse_args(argv)
    manifest_path = Path(args.cache) / "precompute_manifest.json"
    if not manifest_path.is_file():
        print(f"no demo cache at {manifest_path} (run `mentor precompute`)")
        return 2
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("sha") != args.sha:
        print(f"demo cache SHA {manifest.get('sha')} != {args.sha}")
        return 2
    R.REGISTRY.clear()
    R.REGISTRY[args.repo_id] = {"id": args.repo_id,
                                "path": str(Path(args.repo).resolve()),
                                "sha": args.sha, "index": args.index}
    client = TestClient(APP.create_app())
    failures: list[str] = []
    served = cached = 0
    with SocketGuard(enforce=True) as guard:
        for name, fn in (("status", lambda: client.get(
                f"/api/repos/{args.repo_id}/status")),
                         ("architecture", lambda: client.get(
                f"/api/repos/{args.repo_id}/architecture")),
                         ("tours", lambda: client.get(
                f"/api/repos/{args.repo_id}/tours")),
                         ("tasks", lambda: client.get(
                f"/api/repos/{args.repo_id}/tasks?limit=5"))):
            r = fn()
            if r.status_code != 200:
                failures.append(f"{name}: HTTP {r.status_code}")
        for qid in manifest.get("questions", []):
            doc = json.loads((Path(args.cache) / f"answer_{args.repo_id}_{qid}.json")
                             .read_text(encoding="utf-8"))
            r = client.post(f"/api/repos/{args.repo_id}/ask",
                            json={"question": doc["question"], "k": 10})
            served += 1
            if r.status_code != 200:
                failures.append(f"{qid}: HTTP {r.status_code}")
                continue
            body = r.json()
            if not body.get("cached"):
                failures.append(f"{qid}: served live, not from cache")
            else:
                cached += 1
    R.REGISTRY.clear()
    print(f"demo questions: {cached}/{served} from cache (labelled)")
    print(f"non-loopback attempts: {len(guard.non_loopback)}")
    for host, port in guard.non_loopback:
        print(f"  LEAK: {host}:{port}")
        failures.append(f"non-loopback connection to {host}:{port}")
    if failures:
        print("OFFLINE CHECK FAILED:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("OFFLINE CHECK PASSED: zero non-loopback connections, "
          "all demo answers cache-labelled")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
