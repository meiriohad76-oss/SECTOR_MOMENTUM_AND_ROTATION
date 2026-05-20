# B-025 View Preferences Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add native Streamlit view preferences for BLUF mode, layout density, and pick-card sparkline style.

**Architecture:** Put preference validation and display helpers in `src/preferences.py`, extend `src/visuals.svg_sparkline()` with a style argument, and keep Streamlit wiring in `app.py`. CSS uses a density class on the existing `.app` shell.

**Tech Stack:** Python, Streamlit native widgets, CSS, pytest.

---

## File Structure

- Create `src/preferences.py`: constants and pure helpers for defaults, normalization, and CSS mode decisions.
- Create `tests/test_preferences.py`: deterministic tests for helper behavior.
- Create or modify `tests/test_visuals.py`: tests for sparkline modes.
- Create `tests/test_view_preferences_static.py`: static app/CSS wiring checks.
- Modify `src/visuals.py`: add `style` parameter to `svg_sparkline()`.
- Modify `app.py`: initialize preferences, add `render_view_preferences()`, apply BLUF/density/sparkline modes.
- Modify `static/style.css`: add compact BLUF and density rules.
- Modify `docs/BACKLOG.md`: mark B-025 implemented and document deferred custom panel work.

---

### Task 1: Preference Helpers

**Files:**
- Create: `tests/test_preferences.py`
- Create: `src/preferences.py`

- [ ] **Step 1: Write failing tests**

```python
from __future__ import annotations

from src import preferences


def test_initialize_preferences_sets_defaults():
    session = {}

    preferences.initialize_preferences(session)

    assert session["bluf_mode"] == "Verdict"
    assert session["view_density"] == "Comfortable"
    assert session["sparkline_style"] == "Filled"


def test_initialize_preferences_normalizes_invalid_values():
    session = {
        "bluf_mode": "NOPE",
        "view_density": "Dense",
        "sparkline_style": "Bars",
    }

    preferences.initialize_preferences(session)

    assert session["bluf_mode"] == "Verdict"
    assert session["view_density"] == "Comfortable"
    assert session["sparkline_style"] == "Filled"


def test_density_class_only_marks_compact_density():
    assert preferences.density_class("Compact") == "density-compact"
    assert preferences.density_class("Comfortable") == "density-comfortable"


def test_bluf_helpers_report_modes():
    assert preferences.should_render_bluf("Hidden") is False
    assert preferences.should_render_bluf("Compact") is True
    assert preferences.is_compact_bluf("Compact") is True
    assert preferences.is_compact_bluf("Verdict") is False


def test_sparkline_mode_lowercases_valid_style():
    assert preferences.sparkline_mode("Line") == "line"
    assert preferences.sparkline_mode("Off") == "off"
    assert preferences.sparkline_mode("unknown") == "filled"
```

- [ ] **Step 2: Run RED**

Run: `python -m pytest tests/test_preferences.py -q`

Expected: import failure because `src/preferences.py` does not exist.

- [ ] **Step 3: Implement helpers**

```python
from __future__ import annotations

from collections.abc import MutableMapping

BLUF_MODES = ("Verdict", "Compact", "Hidden")
DENSITY_MODES = ("Comfortable", "Compact")
SPARKLINE_STYLES = ("Filled", "Line", "Off")

DEFAULT_BLUF_MODE = "Verdict"
DEFAULT_DENSITY = "Comfortable"
DEFAULT_SPARKLINE_STYLE = "Filled"


def _normalize(value, allowed: tuple[str, ...], default: str) -> str:
    text = str(value).strip() if value is not None else ""
    for option in allowed:
        if text.lower() == option.lower():
            return option
    return default


def initialize_preferences(session_state: MutableMapping) -> None:
    session_state["bluf_mode"] = _normalize(session_state.get("bluf_mode"), BLUF_MODES, DEFAULT_BLUF_MODE)
    session_state["view_density"] = _normalize(session_state.get("view_density"), DENSITY_MODES, DEFAULT_DENSITY)
    session_state["sparkline_style"] = _normalize(
        session_state.get("sparkline_style"),
        SPARKLINE_STYLES,
        DEFAULT_SPARKLINE_STYLE,
    )


def density_class(value: str) -> str:
    density = _normalize(value, DENSITY_MODES, DEFAULT_DENSITY)
    return f"density-{density.lower()}"


def should_render_bluf(value: str) -> bool:
    return _normalize(value, BLUF_MODES, DEFAULT_BLUF_MODE) != "Hidden"


def is_compact_bluf(value: str) -> bool:
    return _normalize(value, BLUF_MODES, DEFAULT_BLUF_MODE) == "Compact"


def sparkline_mode(value: str) -> str:
    return _normalize(value, SPARKLINE_STYLES, DEFAULT_SPARKLINE_STYLE).lower()
```

- [ ] **Step 4: Run GREEN**

Run: `python -m pytest tests/test_preferences.py -q`

Expected: tests pass.

- [ ] **Step 5: Commit helper**

```bash
git add src/preferences.py tests/test_preferences.py
git commit -m "feat: add view preference helpers"
```

---

### Task 2: Sparkline Modes

**Files:**
- Modify: `src/visuals.py`
- Create or modify: `tests/test_visuals.py`

- [ ] **Step 1: Write failing tests**

```python
from __future__ import annotations

import pandas as pd

from src.visuals import svg_sparkline


def _price_frame():
    return pd.DataFrame({"close": [10, 11, 12, 11, 13, 14]})


def test_svg_sparkline_off_returns_empty_markup():
    assert svg_sparkline(_price_frame(), "#26d65b", style="off") == ""


def test_svg_sparkline_line_style_omits_area_fill():
    html = svg_sparkline(_price_frame(), "#26d65b", style="line")

    assert "<svg" in html
    assert "fill=\"url(#" not in html
    assert "stroke=\"#26d65b\"" in html


def test_svg_sparkline_filled_style_keeps_area_fill():
    html = svg_sparkline(_price_frame(), "#26d65b", style="filled")

    assert "fill=\"url(#" in html
    assert "stroke=\"#26d65b\"" in html
```

- [ ] **Step 2: Run RED**

Run: `python -m pytest tests/test_visuals.py -q`

Expected: fails because `svg_sparkline()` does not accept `style`.

- [ ] **Step 3: Implement modes**

Change `svg_sparkline()` signature to:

```python
def svg_sparkline(df_daily, color: str, width: int = 240, height: int = 50, style: str = "filled") -> str:
```

Return `""` when `style == "off"`. Only include the gradient and area path when normalized style is `"filled"`.

- [ ] **Step 4: Run GREEN**

Run: `python -m pytest tests/test_visuals.py -q`

Expected: tests pass.

---

### Task 3: App Wiring and CSS

**Files:**
- Modify: `app.py`
- Modify: `static/style.css`
- Create: `tests/test_view_preferences_static.py`

- [ ] **Step 1: Add static wiring tests**

```python
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_view_preferences_are_initialized_and_rendered_near_header():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")

    assert "initialize_preferences(st.session_state)" in app_source
    assert "render_header_controls()\nrender_view_preferences()" in app_source
    assert "render_bluf()" in app_source


def test_app_uses_preferences_for_bluf_density_and_sparklines():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")

    assert "density_class(st.session_state.view_density)" in app_source
    assert "should_render_bluf(st.session_state.bluf_mode)" in app_source
    assert "is_compact_bluf(st.session_state.bluf_mode)" in app_source
    assert "sparkline_mode(st.session_state.sparkline_style)" in app_source


def test_css_contains_compact_density_rules():
    css = (ROOT / "static" / "style.css").read_text(encoding="utf-8")

    assert ".app.density-compact .section" in css
    assert ".bluf.compact" in css
    assert ".app.density-compact .pick-spark" in css
```

- [ ] **Step 2: Run RED**

Run: `python -m pytest tests/test_view_preferences_static.py -q`

Expected: fails because app/CSS do not yet contain preference wiring.

- [ ] **Step 3: Wire app**

Import preference helpers. Initialize preferences near other session defaults. Add `render_view_preferences()` with an expander and three native radio controls. Add density class to `<div class="app ...">`. Update `render_bluf()` to skip hidden mode and render compact mode. Pass `style=sparkline_mode(st.session_state.sparkline_style)` to `svg_sparkline()`.

- [ ] **Step 4: Add CSS**

Add compact BLUF and density rules:

```css
.bluf.compact { padding: 14px 18px 16px; }
.bluf.compact .bluf-head { margin-bottom: 6px; }
.bluf.compact .bluf-headline { font-size: 1.25rem; margin: 4px 0; }
.bluf.compact .bluf-sub { margin-bottom: 0; font-size: 0.86rem; }
.app.density-compact .section { margin-top: 20px; }
.app.density-compact .status-row,
.app.density-compact .picks-grid { gap: 10px; }
.app.density-compact .tile,
.app.density-compact .pick,
.app.density-compact .action-card { padding: 10px 12px; }
.app.density-compact .pick { gap: 8px; }
.app.density-compact .pick-spark { height: 38px; }
```

- [ ] **Step 5: Run focused tests**

Run:

```bash
python -m pytest tests/test_preferences.py tests/test_visuals.py tests/test_view_preferences_static.py -q
```

Expected: tests pass.

---

### Task 4: Docs, QA, Review, Commit

**Files:**
- Modify: `docs/BACKLOG.md`

- [ ] **Step 1: Update backlog**

Replace B-025 with implemented status and deferred custom panel work.

- [ ] **Step 2: Run verification**

Run:

```bash
python -m pytest tests/test_preferences.py tests/test_visuals.py tests/test_view_preferences_static.py -q
python -m pytest -q
python -m compileall app.py src scripts
git diff --check
```

Expected:

- focused tests pass
- full suite passes
- compileall exits 0
- diff check exits 0, allowing existing CRLF warnings

- [ ] **Step 3: Request review**

Ask a reviewer to inspect preference state, app wiring, visual output changes, CSS blast radius, and tests.

- [ ] **Step 4: Smoke local app**

Verify local Streamlit HTTP 200 on the existing server or start one if needed.

- [ ] **Step 5: Commit implementation**

```bash
git add app.py src/preferences.py src/visuals.py static/style.css tests/test_preferences.py tests/test_visuals.py tests/test_view_preferences_static.py docs/BACKLOG.md docs/superpowers/specs/2026-05-20-b025-view-preferences-design.md docs/superpowers/plans/2026-05-20-b025-view-preferences.md
git commit -m "feat: add view preferences panel"
```
