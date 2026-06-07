from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.visuals import rrg_chart_dark


ROOT = Path(__file__).resolve().parent.parent


def test_dashboard_ticker_labels_use_high_contrast_token():
    css = (ROOT / "static" / "style.css").read_text(encoding="utf-8")

    assert "--ticker-label:" in css
    assert "--ticker-label-shadow:" in css
    assert "color: var(--ticker-label);" in css
    assert "text-shadow: var(--ticker-label-shadow);" in css

    expected_selectors = [
        ".alert-row .t",
        ".action-list .t",
        ".pick-ticker",
        ".table-ticker",
        ".drill-title .t",
        ".comparison-ticker",
        ".quad-card .qtick",
        ".portfolio-actions .pa-row b",
        ".ticker-analysis-grid .tile-sub",
    ]
    for selector in expected_selectors:
        assert selector in css
    assert ".alert-row .t small {\n  color: var(--ticker-label);\n  white-space: nowrap;" in css
    assert "grid-template-columns: 24px minmax(154px, 210px) 120px minmax(0, 1fr) auto 30px;" in css


def test_dark_rrg_ticker_text_uses_readable_foreground():
    frame = pd.DataFrame(
        {
            "rs_ratio": [101.0, 99.0],
            "rs_momentum": [102.0, 98.0],
            "state": ["STAGE_2_BULLISH", "WARNING"],
        },
        index=["XLK", "XLF"],
    )

    fig = rrg_chart_dark(frame)
    point_trace = fig.data[0]

    assert point_trace.textfont.color == "#ffffff"
    assert point_trace.textfont.size >= 14

    annotation_text = " ".join(annotation.text for annotation in fig.layout.annotations)
    assert "LEADING - strong relative trend" in annotation_text
    assert "WEAKENING - leadership fading" in annotation_text
    assert "LAGGING - weak relative trend" in annotation_text
    assert "IMPROVING - early recovery" in annotation_text
