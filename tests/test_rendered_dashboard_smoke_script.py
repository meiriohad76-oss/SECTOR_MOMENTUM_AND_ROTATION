from __future__ import annotations

import json
from pathlib import Path

from scripts import rendered_dashboard_smoke


ROOT = Path(__file__).resolve().parent.parent


def test_rendered_smoke_text_classifier_accepts_dashboard_markers():
    ok, state, missing = rendered_dashboard_smoke._target_state_from_text(
        "SENTIMENT BOARD\nBLUF\nData and dashboard health",
        rendered_dashboard_smoke.DEFAULT_EXPECTED_TEXT,
    )

    assert ok is True
    assert state == "rendered_dashboard"
    assert missing == ()


def test_rendered_smoke_text_classifier_rejects_cloudflare_access_wall():
    ok, state, missing = rendered_dashboard_smoke._target_state_from_text(
        "<title>Sign in - Cloudflare Access</title><body>Cloudflare Access</body>",
        rendered_dashboard_smoke.DEFAULT_EXPECTED_TEXT,
    )

    assert ok is False
    assert state == "cloudflare_access_wall"
    assert missing == rendered_dashboard_smoke.DEFAULT_EXPECTED_TEXT


def test_rendered_smoke_text_classifier_reports_missing_text():
    ok, state, missing = rendered_dashboard_smoke._target_state_from_text(
        "SENTIMENT BOARD only",
        rendered_dashboard_smoke.DEFAULT_EXPECTED_TEXT,
    )

    assert ok is False
    assert state == "missing_rendered_text"
    assert "text:BLUF" in missing
    assert "text:Data and dashboard health" in missing


def test_rendered_smoke_allow_unavailable_exits_zero_for_browser_setup_errors(monkeypatch, capsys):
    monkeypatch.setattr(
        rendered_dashboard_smoke,
        "_run_rendered_smoke",
        lambda **kwargs: {"ok": False, "state": "browser_error", "detail": "no browser"},
    )

    exit_code = rendered_dashboard_smoke.main(["--allow-unavailable"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "rendered_dashboard_smoke ok=false state=browser_error" in output
    assert json.loads(output.splitlines()[-1])["detail"] == "no browser"


def test_rendered_smoke_fails_for_rendered_content_errors_even_with_allow_unavailable(monkeypatch, capsys):
    monkeypatch.setattr(
        rendered_dashboard_smoke,
        "_run_rendered_smoke",
        lambda **kwargs: {
            "ok": False,
            "state": "missing_rendered_text",
            "detail": "render timeout",
            "missing": ["text:BLUF"],
        },
    )

    exit_code = rendered_dashboard_smoke.main(["--allow-unavailable"])

    output = capsys.readouterr().out
    assert exit_code == 1
    assert "rendered_dashboard_smoke ok=false state=missing_rendered_text" in output


def test_rendered_smoke_script_is_not_core_deploy_gate_yet():
    workflow = (ROOT / ".github" / "workflows" / "deploy-pi.yml").read_text(encoding="utf-8")

    assert "scripts/rendered_dashboard_smoke.py" not in workflow


def test_readme_documents_rendered_dashboard_smoke_commands():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "scripts/rendered_dashboard_smoke.py --url http://127.0.0.1:8501/?ticker=XLK" in readme
    assert "scripts/rendered_dashboard_smoke.py --url https://sentimentdashboard.ahaddashboards.uk/?ticker=XLK" in readme
    assert "--allow-unavailable" in readme
    assert "SENTIMENT BOARD" in readme
    assert "Data and dashboard health" in readme
