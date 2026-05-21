from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"
INDEX = PUBLIC / "index.html"
CSS = PUBLIC / "assets" / "methodology.css"
PREVIEW = PUBLIC / "assets" / "methodology-preview.png"


def test_public_landing_files_exist_and_use_bitmap_asset():
    assert INDEX.exists()
    assert CSS.exists()
    assert PREVIEW.exists()
    assert PREVIEW.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


def test_public_landing_explains_methodology_without_live_data():
    html = INDEX.read_text(encoding="utf-8")

    assert "<title>Sector Rotation Methodology</title>" in html
    assert "<h1>Sector Rotation Methodology</h1>" in html
    assert "assets/methodology-preview.png" in html
    assert "Cross-sectional momentum" in html
    assert "Faber 10-month SMA" in html
    assert "Weinstein Stage 2" in html
    assert "Antonacci dual momentum" in html
    assert "Relative Rotation Graphs" in html
    assert "Business-cycle overlay" in html
    assert "Institutional flow" in html
    assert "educational and research purposes only" in html
    assert "not investment advice" in html


def test_public_landing_keeps_dashboard_separate_and_protected():
    html = INDEX.read_text(encoding="utf-8")
    lower_html = html.lower()

    assert "https://dashboard.ahaddashboards.uk/?ticker=XLK" in html
    assert "Cloudflare Access" in html
    assert "live picks" not in html.lower()
    assert "current holdings" not in html.lower()
    assert "run_journal" not in html
    assert "state.json" not in html
    assert ".streamlit" not in html
    assert "streamlit" not in html.lower()
    assert "websocket" not in html.lower()
    assert "api_key" not in html.lower()
    assert "account" not in lower_html
    assert "private dashboard state" not in lower_html
    assert "dashboard state" not in lower_html
    assert "journal" not in lower_html
    assert "api key" not in lower_html


def test_public_landing_css_uses_no_external_or_script_dependencies():
    html = INDEX.read_text(encoding="utf-8")
    css = CSS.read_text(encoding="utf-8")

    assert '<link rel="stylesheet" href="assets/methodology.css">' in html
    assert "<script" not in html.lower()
    assert "http://" not in css
    assert "https://" not in css
    assert "orb" not in css.lower()
    assert "bokeh" not in css.lower()


def test_public_landing_internal_links_exist_under_public_root():
    html = INDEX.read_text(encoding="utf-8")

    assert "docs/sector-rotation-methodology.md" not in html
    for relative_path in ("methodology.html", "sitemap.xml"):
        assert (PUBLIC / relative_path).exists()
