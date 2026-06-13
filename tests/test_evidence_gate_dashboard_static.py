from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_app_surfaces_evidence_gates_without_promoting_rules_or_running_cli():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    start = app_source.index("def render_evidence_gate_lab():")
    end = app_source.index("def render_debrief_lab():")
    section_source = app_source[start:end]

    assert (
        "from src.evidence_gates import "
        "evaluate_promotion_gate, promotion_gate_decisions_frame"
    ) in app_source
    assert (
        'FRED_VALIDATION_SUMMARY_PATH = APP_ROOT / "docs" / '
        '"fred_macro_validation_summary.csv"'
    ) in app_source
    assert (
        'MASSIVE_VALIDATION_SUMMARY_PATH = APP_ROOT / "docs" / '
        '"massive_provider_validation_summary.csv"'
    ) in app_source
    assert 'EVIDENCE_GATE_REPORT_PATH = APP_ROOT / "docs" / "evidence_gate_report.md"' in app_source
    assert "def render_evidence_gate_lab():" in app_source
    assert "Evidence gates" in section_source
    assert "Macro and provider research" in section_source
    assert "evaluate_promotion_gate(" in section_source
    assert "promotion_gate_decisions_frame(" in section_source
    assert 'gate_rows = gate_rows.rename(columns={"Ticket": "Gate"})' in section_source
    assert "EVIDENCE_GATE_REPORT_PATH.read_text" in section_source
    assert "live_promotion_allowed" in section_source
    assert "evaluate_evidence_gates.main(" not in app_source
    assert "fetch_ohlcv(" not in section_source
    assert "apply_state_machine(" not in section_source
    assert "send_" not in section_source
