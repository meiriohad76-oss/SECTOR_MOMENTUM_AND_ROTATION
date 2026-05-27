from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_full_matrix_uses_explicit_sort_controls_and_active_headers():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")

    assert "from src.table_sort import (" in app_source
    assert "FULL_TABLE_SORT_FIELDS" in app_source
    assert "FULL_TABLE_SORT_DIRECTIONS" in app_source
    assert "normalize_full_table_sort" in app_source
    assert "sort_full_table_frame(" in app_source
    assert 'st.selectbox("Sort field"' in app_source
    assert 'st.segmented_control("Direction"' in app_source
    assert "table_sort_field_choice" in app_source
    assert "table_sort_direction_choice" in app_source
    assert "matrix-sort-summary" in app_source
    assert "sort-active" in app_source


def test_sort_direction_control_does_not_duplicate_session_state_default():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    start = app_source.index('selected_direction = st.segmented_control("Direction"')
    end = app_source.index("selected_field, selected_direction = normalize_full_table_sort", start)
    control_source = app_source[start:end]

    assert 'key="table_sort_direction_choice"' in control_source
    assert "default=" not in control_source


def test_sort_controls_are_visual_only_and_do_not_force_data_recompute():
    perf_source = (ROOT / "src" / "performance_audit.py").read_text(encoding="utf-8")

    assert '"table_sort",' in perf_source
    assert '"table_sort_field",' in perf_source
    assert '"table_sort_direction",' in perf_source
    assert '"table_sort_field_choice",' in perf_source
    assert '"table_sort_direction_choice",' in perf_source
    visual_block = perf_source[
        perf_source.index("VISUAL_STATE_KEYS = (") : perf_source.index("COMPUTE_SNAPSHOT_KEYS")
    ]
    assert '"table_sort_field_choice",' in visual_block
    assert '"table_sort_direction_choice",' in visual_block
