"""Phase 16 gate: built-page security — CSP present, no inline scripts,
no dangerouslySetInnerHTML anywhere (spec Phase 16)."""
import re
from pathlib import Path

DIST = Path("web/dist")
SRC = Path("web/src")


def _built_html() -> str:
    index = DIST / "index.html"
    assert index.is_file(), "web/dist missing: run `npm run build` in web/"
    return index.read_text(encoding="utf-8")


def test_csp_meta_present():
    html = _built_html()
    assert "Content-Security-Policy" in html
    for directive in ("default-src 'self'", "script-src 'self'",
                      "connect-src 'self'"):
        assert directive in html, f"CSP missing {directive}"


def test_no_inline_scripts_in_build():
    html = _built_html()
    for match in re.finditer(r"<script[^>]*>", html):
        assert "src=" in match.group(0), f"inline script: {match.group(0)}"


def test_no_dangerously_set_inner_html():
    hits = []
    for path in list(SRC.rglob("*.tsx")) + list(SRC.rglob("*.ts")):
        text = path.read_text(encoding="utf-8")
        if "dangerouslySetInnerHTML" in text:
            hits.append(str(path))
    assert hits == [], f"HTML injection vector: {hits}"
