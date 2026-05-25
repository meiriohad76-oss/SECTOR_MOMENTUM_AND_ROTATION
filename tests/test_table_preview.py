from __future__ import annotations

from src.table_preview import rrg_preview_position, table_row_rrg_preview_html


def test_rrg_preview_position_centers_and_clamps_values():
    assert rrg_preview_position(100, 100) == (50.0, 50.0)
    assert rrg_preview_position(140, 60) == (100.0, 0.0)


def test_table_row_rrg_preview_html_escapes_text_and_includes_metrics():
    row = {
        "state": "STAGE_2_BULLISH",
        "rrg_quadrant": "Leading",
        "rs_ratio": 104.25,
        "rs_momentum": 97.5,
        "S_score": 1.234,
        "F_score": -0.25,
    }

    html = table_row_rrg_preview_html('XLK"<', row)

    assert "XLK&quot;&lt;" in html
    assert 'class="row-preview"' in html
    assert 'class="mini-rrg"' in html
    assert "--rrg-x:60.6%;" in html
    assert "--rrg-y:43.8%;" in html
    assert "RS 104.2" in html
    assert "MOM 97.5" in html
    assert "S +1.23" in html
    assert "F -0.25" in html
