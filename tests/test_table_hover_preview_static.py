from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_full_table_wires_row_hover_preview_markup():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")

    assert "from src.table_preview import table_row_rrg_preview_html" in app_source
    assert "preview_html = table_row_rrg_preview_html(tkr, r)" in app_source
    assert "ticker_name = _ticker_identity_subtext(tkr)" in app_source
    assert '<td class="t table-ticker">{_esc(tkr)}<small>{_esc(ticker_name)}</small>{preview_html}</td>' in app_source


def test_full_table_hover_preview_css_is_present_and_mobile_safe():
    css_source = (ROOT / "static" / "style.css").read_text(encoding="utf-8")

    assert ".table-ticker {" in css_source
    assert ".row-preview {" in css_source
    assert ".mini-rrg {" in css_source
    assert ".mini-rrg-dot {" in css_source
    assert ".full-table tr:hover .row-preview" in css_source
    assert "@media (max-width: 760px)" in css_source
    assert ".row-preview { display: none; }" in css_source
    assert "@media (hover: none), (pointer: coarse)" in css_source
