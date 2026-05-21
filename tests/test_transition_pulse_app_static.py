from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_transition_pulse_is_wired_to_alerts_and_picks():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")

    assert "from src.transition_pulse import transition_pulse_class, transition_row_pulse_class" in app_source
    assert "pulse_class = transition_row_pulse_class(r)" in app_source
    assert "pulse_class = transition_pulse_class(tkr, transitions)" in app_source
    assert '<div class="alert-row {new_state} {pulse_class}">' in app_source
    assert '<div class="pick {state} {pulse_class}">' in app_source


def test_transition_pulse_css_animation_and_reduced_motion_guard():
    css_source = (ROOT / "static" / "style.css").read_text(encoding="utf-8")

    assert "@keyframes state-pulse" in css_source
    assert "@keyframes alert-state-pulse" in css_source
    assert ".pulse-transition {" in css_source
    assert ".pick.pulse-transition" in css_source
    assert ".alert-row.pulse-transition" in css_source
    assert "background: transparent;" in css_source
    assert "@media (prefers-reduced-motion: reduce)" in css_source
    assert ".pulse-transition { animation: none; }" in css_source
