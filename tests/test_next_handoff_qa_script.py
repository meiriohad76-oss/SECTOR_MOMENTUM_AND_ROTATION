from __future__ import annotations

import subprocess
import sys

from scripts import capture_next_handoff_qa as qa


def test_next_handoff_qa_maps_current_next_screens_to_c_handoff_refs():
    assert qa.NEXT_SCREEN_REFERENCE_MAP == {
        "overview": "C1-pillarstack-heatmap.png",
        "deepdive": "C2-pillarstack-waterfall.png",
        "rotation": "C3-pillarstack-rotation.png",
    }
    assert qa.NEXT_SCREEN_BUTTONS["overview"] == "A Overview"
    assert qa.NEXT_SCREEN_BUTTONS["deepdive"] == "B Deep Dive"
    assert qa.NEXT_SCREEN_BUTTONS["rotation"] == "C Rotation"


def test_next_handoff_qa_required_text_covers_new_chart_primitives():
    required = qa.NEXT_SCREEN_REQUIRED_TEXT

    assert "The composite, dissected" in required["overview"]
    assert "The composite, built pillar by pillar" in required["deepdive"]
    assert "Relative Rotation Graph" in required["rotation"]
    assert "The flow river" in required["rotation"]


def test_next_handoff_qa_missing_text_normalizes_nbsp():
    assert qa._missing_text("A\xa0B The flow river", ("A B", "The flow river")) == []
    assert qa._missing_text("Only one", ("Only one", "Missing")) == ["Missing"]


def test_next_handoff_qa_cli_exposes_similarity_gate_and_next_url():
    result = subprocess.run(
        [sys.executable, "scripts/capture_next_handoff_qa.py", "--help"],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "--min-similarity" in result.stdout
    assert qa.parse_args([]).url == "http://127.0.0.1:3000"


def test_next_handoff_qa_is_not_imported_by_production_app():
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    app_source = (root / "app.py").read_text(encoding="utf-8")
    page_source = (root / "web" / "app" / "page.tsx").read_text(encoding="utf-8")

    assert "capture_next_handoff_qa" not in app_source
    assert "capture_next_handoff_qa" not in page_source
