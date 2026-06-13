from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
TUTORIAL_PATH = ROOT / "docs" / "how-to-add-sector-indicator-pillar.md"


def test_tutorial_exists_and_covers_three_extension_paths():
    text = TUTORIAL_PATH.read_text(encoding="utf-8")

    assert "# How To Add A Sector, Indicator, Or Pillar" in text
    assert "## Add A Sector Or Universe Class" in text
    assert "## Add An Indicator" in text
    assert "## Add Or Change A Pillar" in text
    assert "src/universe.py" in text
    assert "src/indicators.py" in text
    assert "src/flow.py" in text
    assert "src/macro.py" in text
    assert "src/scoring.py" in text
    assert "src/component_docs.py" in text


def test_tutorial_preserves_methodology_and_provider_safety_rules():
    text = TUTORIAL_PATH.read_text(encoding="utf-8")

    assert "docs/sector-rotation-methodology.md" in text
    assert "docs/PRODUCT_DESIGN.md" in text
    assert "tests/test_universe.py" in text
    assert "short-history inputs return neutral or missing values" in text
    assert "do not fetch provider data from scoring helpers" in text
    assert "do not write state.json from tests or backtests" in text
    assert "keep provider-backed signals opt-in and fail-closed" in text


def test_tutorial_includes_verification_recipe():
    text = TUTORIAL_PATH.read_text(encoding="utf-8")

    assert "python -m pytest tests/test_universe.py -q" in text
    assert "python -m pytest tests/test_indicators.py tests/test_flow.py tests/test_scoring.py -q" in text
    assert "python -m pytest -q" in text
    assert "python -m compileall app.py src scripts" in text
    assert "git diff --check" in text


def test_readme_and_backlog_link_tutorial():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    backlog = (ROOT / "docs" / "BACKLOG.md").read_text(encoding="utf-8")

    assert "docs/how-to-add-sector-indicator-pillar.md" in readme
    assert "B-151" in backlog
    assert "docs/how-to-add-sector-indicator-pillar.md" in backlog
    assert "IMPLEMENTED" in backlog
