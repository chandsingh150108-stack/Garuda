"""T7: secrets in the repository. Boundary: ingest. Controls: regex
scanner + filename exclusions, secret-bearing files excluded from the index,
hash-only audit, redaction before any cloud call (Phase 11). Tests: every
secret format is caught; the value never lands in manifest/index/payload.
"""
import json

from mentor.ingest import manifest as M
from mentor.ingest import secrets as S
from mentor.llm import redact as RD

CASES = {
    "aws": 'KEY = "AKIAIOSFODNN7EXAMPLE"\n',
    "pem": "-----BEGIN RSA PRIVATE KEY-----\nabc\n",
    "jwt": "t = eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c\n",
    "quoted": 'password = "hunter2hunter2"\n',
}


def test_scanner_catches_every_format(tmp_path):
    for name, body in CASES.items():
        target = tmp_path / f"{name}.py"
        target.write_text(body, encoding="utf-8")
        assert S.scan_file(target), name


def test_manifest_and_redaction_keep_values_out(tmp_path):
    secret = tmp_path / "s.py"
    secret.write_text(CASES["aws"], encoding="utf-8")
    manifest = M.build_manifest(tmp_path, "t7")
    entry = next(e for e in manifest["files"] if e["path"] == "s.py")
    assert entry["skipped"] == "secret"
    assert "AKIAIOSFODNN7EXAMPLE" not in json.dumps(entry)
    blocks = [{"id": "E1", "path": "s.py", "start_line": 1, "end_line": 1,
               "header": "s", "text": CASES["aws"]}]
    redacted, report = RD.redact_blocks(blocks)
    assert "AKIAIOSFODNN7EXAMPLE" not in json.dumps(redacted)
    assert "AKIAIOSFODNN7EXAMPLE" not in json.dumps(report)
