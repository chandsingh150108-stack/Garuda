"""T13: cross-site scripting in the interface. Boundary: browser.
Controls: plain-text answer rendering (D16.2), no `dangerouslySetInnerHTML`
anywhere, strict CSP meta in source AND built output. Mirrors the Phase 16
build gate at the threat-model level.
"""
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent.parent / "web" / "src"
DIST = Path(__file__).resolve().parent.parent.parent / "web" / "dist"


def test_no_raw_html_rendering_api():
    hits = [str(p) for p in list(SRC.rglob("*.tsx")) + list(SRC.rglob("*.ts"))
            if "dangerouslySetInnerHTML" in p.read_text(encoding="utf-8")]
    assert hits == [], f"HTML injection vector: {hits}"


def test_built_page_has_csp_and_no_inline_scripts():
    index = DIST / "index.html"
    assert index.is_file(), "run `npm run build` in web/"
    html = index.read_text(encoding="utf-8")
    assert "Content-Security-Policy" in html
    for directive in ("default-src 'self'", "script-src 'self'",
                      "connect-src 'self'"):
        assert directive in html, f"CSP missing {directive}"
    import re
    for match in re.finditer(r"<script[^>]*>", html):
        assert "src=" in match.group(0), f"inline script: {match.group(0)}"
