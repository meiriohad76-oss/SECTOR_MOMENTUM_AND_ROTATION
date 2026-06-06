from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_dashboard_copy_frames_outputs_as_decision_support_not_certainty():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    production_copy = app_source[
        app_source.index("INDICATOR_TIPS = {") : app_source.index("# =============================== data load")
    ]

    forbidden = (
        "Sell on Monday open",
        "sell now",
        "active buy",
        "predicted outperformance",
        "predicted underperformance",
        "10-30% drawdown",
        "median outcome",
        "positions safe",
        "guaranteed forecast",
    )
    for phrase in forbidden:
        assert phrase not in production_copy

    assert "decision-support signals" in production_copy
    assert "not guaranteed predictions or financial advice" in production_copy
    assert "MODEL SIGNAL" in production_copy
