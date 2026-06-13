from __future__ import annotations

from pathlib import Path
import subprocess
import sys

from scripts import capture_next_handoff_qa as qa


def test_next_handoff_qa_maps_current_next_screens_to_c_handoff_refs():
    assert qa.NEXT_SCREEN_REFERENCE_MAP == {
        "overview": "C1-pillarstack-heatmap.png",
        "deepdive": "C2-pillarstack-waterfall.png",
        "rotation": "C3-pillarstack-rotation.png",
    }
    assert qa.QA_PROFILES["c"]["buttons"]["overview"] == "Heatmap"
    assert qa.QA_PROFILES["c"]["buttons"]["deepdive"] == "Deep dive"
    assert qa.NEXT_SCREEN_BUTTONS["rotation"] == "Rotation"


def test_next_handoff_qa_profiles_cover_a_b_and_c_references():
    assert qa.QA_PROFILES["a"]["reference_map"] == {
        "overview": "A1-terminal-overview.png",
        "deepdive": "A2-terminal-deepdive.png",
        "rotation": "A3-terminal-rotation.png",
    }
    assert qa.QA_PROFILES["b"]["reference_map"] == {
        "overview": "B1-editorial-brief.png",
        "deepdive": "B2-editorial-article.png",
        "rotation": "B3-editorial-rotation.png",
    }
    assert qa.QA_PROFILES["a"]["default_url"] == "http://127.0.0.1:3000/?presentation=a"
    assert qa.QA_PROFILES["b"]["default_url"] == "http://127.0.0.1:3000/?presentation=b"
    assert qa.QA_PROFILES["c"]["default_url"] == "http://127.0.0.1:3000/?presentation=c"


def test_next_handoff_qa_required_text_covers_new_chart_primitives():
    required = qa.NEXT_SCREEN_REQUIRED_TEXT

    assert "The composite, dissected" in required["overview"]
    assert "The composite, built pillar by pillar" in required["deepdive"]
    assert "The rotation map" in required["rotation"]
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
    assert "--profile" in result.stdout
    assert qa.parse_args([]).profile == "c"
    assert qa.parse_args(["--profile", "a"]).profile == "a"
    assert qa.parse_args([]).url is None


def test_next_handoff_qa_hides_development_overlay_before_capture():
    source = Path("scripts/capture_next_handoff_qa.py").read_text(encoding="utf-8")

    assert "page.add_style_tag(" in source
    assert "nextjs-portal" in source
    assert "[data-next-badge-root]" in source


def test_next_handoff_qa_is_not_imported_by_production_app():
    root = Path(__file__).resolve().parent.parent
    app_source = (root / "app.py").read_text(encoding="utf-8")
    page_source = (root / "web" / "app" / "page.tsx").read_text(encoding="utf-8")

    assert "capture_next_handoff_qa" not in app_source
    assert "capture_next_handoff_qa" not in page_source
