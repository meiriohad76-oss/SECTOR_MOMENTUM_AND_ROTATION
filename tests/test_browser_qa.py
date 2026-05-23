from __future__ import annotations

from src.browser_qa import (
    BROWSER_QA_TICKETS,
    BrowserQaResult,
    build_browser_qa_report,
    browser_qa_targets,
    missing_text_checks,
)


def test_browser_qa_targets_cover_visual_residual_risks():
    tickets = {ticket for target in browser_qa_targets() for ticket in target.tickets}

    assert BROWSER_QA_TICKETS == (
        "B-110",
        "B-111",
        "B-112",
        "B-113",
        "B-114",
        "B-115",
        "B-116",
        "B-117",
        "B-146",
        "B-147",
    )
    assert tickets == set(BROWSER_QA_TICKETS)
    targets = browser_qa_targets()
    assert {target.viewport for target in targets} == {"desktop", "tablet", "mobile"}
    assert all(target.focus_text for target in targets)
    by_id = {target.target_id: target for target in targets}
    assert by_id["desktop-palette-view-options"].tickets == ("B-117",)
    assert by_id["desktop-palette-view-options"].path == "/?ticker=XLK&browser_qa_palette=Solarized"
    assert "expand:VIEW OPTIONS" in by_id["desktop-palette-view-options"].setup_actions
    assert "expect-radio-checked:Solarized" in by_id["desktop-palette-view-options"].setup_actions
    assert by_id["desktop-transition-pulse"].tickets == ("B-114",)
    assert "expect-visible:.alert-row.pulse-transition" in by_id["desktop-transition-pulse"].actions
    assert by_id["desktop-provider-status-banner"].tickets == ("B-146",)
    assert "expect-visible:.provider-status-banner" in by_id["desktop-provider-status-banner"].actions
    assert by_id["desktop-comparison-view"].focus_text == "COMPARE TICKERS"
    assert by_id["desktop-full-matrix-table"].focus_text == "FULL 7"
    assert "hover:first-full-table-row" in by_id["desktop-full-matrix-table"].actions
    assert "expect-visible:.full-table tbody tr:first-child .row-preview" in by_id["desktop-full-matrix-table"].actions


def test_browser_qa_report_is_secret_safe_and_actionable():
    results = [
        BrowserQaResult(
            target_id="desktop-dashboard",
            viewport="desktop",
            tickets=("B-111", "B-115", "B-146", "B-147"),
            url="http://127.0.0.1:8501/?ticker=XLK",
            screenshot="docs/browser-qa/latest/desktop-dashboard.png",
            checks=("text:SENTIMENT BOARD", "text:COMPARE TICKERS"),
            ok=True,
            notes=("nonblank screenshot",),
        ),
        BrowserQaResult(
            target_id="mobile-dashboard",
            viewport="mobile",
            tickets=("B-110",),
            url="http://127.0.0.1:8501/?ticker=XLK",
            screenshot="docs/browser-qa/latest/mobile-dashboard.png",
            checks=("text:SENTIMENT BOARD",),
            ok=False,
            notes=("missing text:FULL 7-PILLAR MATRIX",),
        ),
    ]

    report = build_browser_qa_report(results, generated_at="2026-05-23T03:00:00Z")

    assert "Browser QA Evidence" in report
    assert "2026-05-23T03:00:00Z" in report
    assert "B-111, B-115, B-146, B-147" in report
    assert "FAIL" in report
    assert "docs/browser-qa/latest/mobile-dashboard.png" in report
    assert "token" not in report.lower()
    assert "secret" not in report.lower()


def test_missing_text_checks_uses_normalized_body_text():
    body_text = """
        Sentiment Board
        Full   7-pillar   matrix
        Compare tickers
        Risk Regime
    """

    assert missing_text_checks(body_text, ("text:SENTIMENT BOARD", "text:FULL 7-pillar matrix")) == ()
    assert missing_text_checks(body_text, ("text:DRILL", "role:button")) == ("text:DRILL",)
