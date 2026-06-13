from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
NOTEBOOK_PATH = ROOT / "notebooks" / "backtest_methodology_report.ipynb"


def _notebook_text() -> str:
    return NOTEBOOK_PATH.read_text(encoding="utf-8")


def test_backtest_methodology_notebook_is_valid_json_notebook():
    notebook = json.loads(_notebook_text())

    assert notebook["nbformat"] == 4
    assert isinstance(notebook["cells"], list)
    assert len(notebook["cells"]) >= 4


def test_backtest_methodology_notebook_references_artifacts_without_secrets():
    text = _notebook_text()

    assert "docs/backtest_report.md" in text
    assert "docs/backtest_methodology_report.md" in text
    assert "docs/backtest_equity.csv" in text
    assert "docs/backtest_metadata.json" in text
    assert "python scripts/run_backtest.py --live-smoke" in text
    assert "MASSIVE_API_KEY" not in text
