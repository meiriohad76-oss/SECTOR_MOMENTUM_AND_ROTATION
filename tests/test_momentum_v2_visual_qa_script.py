from scripts import momentum_v2_visual_qa as qa


def test_visual_qa_maps_all_handoff_pngs():
    assert len(qa.REFERENCE_MAP) == 9
    assert qa.REFERENCE_MAP[("A", "overview")] == "A1-terminal-overview.png"
    assert qa.REFERENCE_MAP[("B", "deepdive")] == "B2-editorial-article.png"
    assert qa.REFERENCE_MAP[("C", "rotation")] == "C3-pillarstack-rotation.png"


def test_visual_qa_targets_all_display_screen_combinations():
    targets = qa._iter_targets(["A", "B", "C"], ["overview", "deepdive", "rotation"])

    assert len(targets) == 9
    assert ("C", "deepdive") in targets


def test_visual_qa_static_html_contains_mv2_shell():
    html = qa._static_html("C", "deepdive")

    assert "mv2-shell" in html
    assert "momentum-v2-c-deepdive" in html
    assert "waterfall" in html


def test_visual_qa_cli_exposes_similarity_release_gate():
    import subprocess
    import sys

    result = subprocess.run(
        [
            sys.executable,
            "scripts/momentum_v2_visual_qa.py",
            "--help",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "--min-similarity" in result.stdout
