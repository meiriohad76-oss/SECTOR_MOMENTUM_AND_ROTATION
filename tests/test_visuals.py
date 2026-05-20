from __future__ import annotations

import pandas as pd

from src.visuals import svg_sparkline


def _price_frame():
    return pd.DataFrame({"close": [10, 11, 12, 11, 13, 14]})


def test_svg_sparkline_off_returns_empty_markup():
    assert svg_sparkline(_price_frame(), "#26d65b", style="off") == ""


def test_svg_sparkline_line_style_omits_area_fill():
    html = svg_sparkline(_price_frame(), "#26d65b", style="line")

    assert "<svg" in html
    assert 'fill="url(#' not in html
    assert 'stroke="#26d65b"' in html


def test_svg_sparkline_filled_style_keeps_area_fill():
    html = svg_sparkline(_price_frame(), "#26d65b", style="filled")

    assert 'fill="url(#' in html
    assert 'stroke="#26d65b"' in html
