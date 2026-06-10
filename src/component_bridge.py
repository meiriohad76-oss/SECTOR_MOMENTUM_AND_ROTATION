"""Small Streamlit component bridges for dashboard controls, clicks, and tooltips."""
from __future__ import annotations

from collections.abc import Callable, MutableMapping
from dataclasses import dataclass
from html import escape
import re
from typing import Any

from .preferences import BLUF_MODES, DENSITY_MODES, PALETTE_OPTIONS, SPARKLINE_STYLES


BRIDGE_ACTION_PARAM = "bridge_action"
BRIDGE_BLUF_PARAM = "bridge_bluf_mode"
BRIDGE_DENSITY_PARAM = "bridge_density"
BRIDGE_SPARKLINE_PARAM = "bridge_sparkline"
BRIDGE_PALETTE_PARAM = "bridge_palette"
CONTROL_BRIDGE_PARAMS = (
    BRIDGE_ACTION_PARAM,
    BRIDGE_BLUF_PARAM,
    BRIDGE_DENSITY_PARAM,
    BRIDGE_SPARKLINE_PARAM,
    BRIDGE_PALETTE_PARAM,
)


@dataclass(frozen=True)
class BridgeActionResult:
    consumed: bool
    changed: bool
    should_rerun: bool
    refreshed: bool = False
    changed_keys: tuple[str, ...] = ()


def normalize_bridge_ticker(value: Any) -> str:
    """Return a safe uppercase token for ticker bridge attributes."""
    text = str(value or "").upper()
    return re.sub(r"[^A-Z0-9.^_-]", "", text)[:24]


def drill_bridge_attrs(ticker: Any, *, label: str | None = None) -> str:
    """Return accessible HTML attributes that the drill click bridge can consume."""
    safe_ticker = normalize_bridge_ticker(ticker)
    if not safe_ticker:
        return ""
    suffix = f" for {label}" if label else ""
    aria = escape(f"Open {safe_ticker} drill-down{suffix}", quote=True)
    return (
        f'data-drill-ticker="{escape(safe_ticker, quote=True)}" '
        f'role="button" tabindex="0" aria-label="{aria}"'
    )


def drill_click_bridge_html() -> str:
    """Return a hidden component payload that turns data-drill-ticker nodes into URL updates."""
    return """
<script>
(function () {
  const parentWindow = window.parent || window;
  let doc;
  try {
    doc = parentWindow.document;
  } catch (error) {
    return;
  }
  if (parentWindow.__sectorDrillBridgeInstalled) {
    return;
  }
  parentWindow.__sectorDrillBridgeInstalled = true;

  function cleanTicker(value) {
    return String(value || '').toUpperCase().replace(/[^A-Z0-9.^_-]/g, '').slice(0, 24);
  }

  function setTicker(ticker) {
    ticker = cleanTicker(ticker);
    if (!ticker) {
      return;
    }
    const url = new URL(parentWindow.location.href);
    url.searchParams.set('ticker', ticker);
    url.hash = 'drill';
    parentWindow.location.assign(url.toString());
  }

  function targetFromEvent(event) {
    const target = event.target;
    if (!target || typeof target.closest !== 'function') {
      return null;
    }
    return target.closest('[data-drill-ticker]');
  }

  doc.addEventListener('click', function (event) {
    const node = targetFromEvent(event);
    if (!node) {
      return;
    }
    event.preventDefault();
    setTicker(node.getAttribute('data-drill-ticker'));
  }, true);

  doc.addEventListener('keydown', function (event) {
    if (event.key !== 'Enter' && event.key !== ' ') {
      return;
    }
    const node = targetFromEvent(event);
    if (!node) {
      return;
    }
    event.preventDefault();
    setTicker(node.getAttribute('data-drill-ticker'));
  }, true);
})();
</script>
"""


def viewport_tooltip_bridge_html() -> str:
    """Return a hidden component payload that clamps data-tip tooltips inside the viewport."""
    return """
<script>
(function () {
  const parentWindow = window.parent || window;
  let doc;
  try {
    doc = parentWindow.document;
  } catch (error) {
    return;
  }
  if (parentWindow.__sectorViewportTooltipBridgeInstalled) {
    return;
  }
  parentWindow.__sectorViewportTooltipBridgeInstalled = true;
  doc.documentElement.classList.add('sector-js-tooltips');

  const styleId = 'sector-dashboard-tooltip-style';
  if (!doc.getElementById(styleId)) {
    const style = doc.createElement('style');
    style.id = styleId;
    style.textContent = `
      #sector-dashboard-tooltip {
        position: fixed;
        left: 16px;
        top: 16px;
        z-index: 2147483647;
        box-sizing: border-box;
        max-width: calc(100vw - 32px);
        width: max-content;
        min-width: min(220px, calc(100vw - 32px));
        padding: 10px 12px;
        border: 1px solid var(--border-strong, #3f4b5d);
        border-radius: 6px;
        background: var(--panel, #111821);
        color: var(--fg, #f0f4fa);
        box-shadow: 0 10px 28px rgba(0,0,0,0.55);
        font: 400 0.92rem/1.55 var(--font-prose, system-ui, sans-serif);
        letter-spacing: 0;
        text-align: left;
        text-transform: none;
        white-space: normal;
        overflow-wrap: anywhere;
        word-break: normal;
        hyphens: auto;
        pointer-events: none;
        opacity: 0;
        visibility: hidden;
        transition: opacity 120ms ease, visibility 120ms ease;
      }
      #sector-dashboard-tooltip.is-visible {
        opacity: 1;
        visibility: visible;
      }
    `;
    doc.head.appendChild(style);
  }

  const tooltip = doc.createElement('div');
  tooltip.id = 'sector-dashboard-tooltip';
  tooltip.setAttribute('role', 'tooltip');
  doc.body.appendChild(tooltip);

  let activeNode = null;

  function clamp(value, min, max) {
    return Math.min(Math.max(value, min), Math.max(min, max));
  }

  function targetFromEvent(event) {
    const target = event && event.target;
    if (!target || typeof target.closest !== 'function') {
      return null;
    }
    return target.closest('[data-tip]');
  }

  function positionTooltip(target) {
    const rect = target.getBoundingClientRect();
    const margin = 16;
    const maxWidth = Math.max(180, parentWindow.innerWidth - margin * 2);
    tooltip.style.maxWidth = Math.min(420, maxWidth) + 'px';
    tooltip.style.left = '0px';
    tooltip.style.top = '0px';
    const tipRect = tooltip.getBoundingClientRect();
    const width = Math.min(tipRect.width || 240, maxWidth);
    const height = tipRect.height || 48;
    const centered = rect.left + rect.width / 2 - width / 2;
    const left = clamp(centered, margin, parentWindow.innerWidth - width - margin);
    const aboveTop = rect.top - height - 10;
    const belowTop = rect.bottom + 10;
    const top = aboveTop >= margin
      ? aboveTop
      : clamp(belowTop, margin, parentWindow.innerHeight - height - margin);
    tooltip.style.left = left + 'px';
    tooltip.style.top = top + 'px';
  }

  function show(event) {
    const target = targetFromEvent(event);
    if (!target) {
      return;
    }
    const text = String(target.getAttribute('data-tip') || '').trim();
    if (!text) {
      return;
    }
    if (activeNode && activeNode !== target) {
      activeNode.removeAttribute('data-tip-js-active');
    }
    activeNode = target;
    activeNode.setAttribute('data-tip-js-active', '1');
    tooltip.textContent = text;
    tooltip.classList.add('is-visible');
    positionTooltip(target);
  }

  function hide(event) {
    if (!activeNode) {
      return;
    }
    if (event && event.relatedTarget && activeNode.contains(event.relatedTarget)) {
      return;
    }
    activeNode.removeAttribute('data-tip-js-active');
    activeNode = null;
    tooltip.classList.remove('is-visible');
  }

  function reposition() {
    if (activeNode) {
      positionTooltip(activeNode);
    }
  }

  doc.addEventListener('mouseover', show, true);
  doc.addEventListener('focusin', show, true);
  doc.addEventListener('mouseout', hide, true);
  doc.addEventListener('focusout', hide, true);
  doc.addEventListener('scroll', reposition, true);
  parentWindow.addEventListener('resize', reposition, true);
})();
</script>
"""


def rrg_plotly_click_bridge_html(fig: Any, *, div_id: str = "rrg-plotly-bridge") -> str:
    """Render a Plotly figure with point clicks bridged into the ticker query param."""
    plot_html = fig.to_html(
        full_html=False,
        include_plotlyjs="cdn",
        div_id=div_id,
        config={"displayModeBar": False, "responsive": True},
    )
    safe_div_id = escape(div_id, quote=True)
    return f"""
<div class="rrg-plotly-bridge-wrap">
{plot_html}
</div>
<script>
(function () {{
  const parentWindow = window.parent || window;
  function cleanTicker(value) {{
    return String(value || '').toUpperCase().replace(/[^A-Z0-9.^_-]/g, '').slice(0, 24);
  }}
    function setTicker(ticker) {{
      ticker = cleanTicker(ticker);
      if (!ticker) {{
        return;
      }}
      const url = new URL(parentWindow.location.href);
      url.searchParams.set('ticker', ticker);
      url.hash = 'drill';
      parentWindow.location.assign(url.toString());
    }}
  function wire() {{
    const plot = document.getElementById('{safe_div_id}');
    if (!plot || typeof plot.on !== 'function') {{
      window.setTimeout(wire, 100);
      return;
    }}
    if (plot.__sectorRrgClickBridgeInstalled) {{
      return;
    }}
    plot.__sectorRrgClickBridgeInstalled = true;
    plot.on('plotly_click', function (event) {{
      const point = event && event.points && event.points[0];
      const ticker = point && (point.text || point.customdata);
      setTicker(ticker);
    }});
  }}
  wire();
}})();
</script>
"""


def floating_control_bridge_html(
    *,
    theme: str,
    bluf_mode: str,
    density: str,
    sparkline: str,
    palette: str,
) -> str:
    """Return a custom floating header/preference component payload."""
    payload = {
        "theme": _normalize_choice(theme, ("dark", "light"), "dark"),
        "bluf_mode": _normalize_choice(bluf_mode, BLUF_MODES, "Verdict"),
        "density": _normalize_choice(density, DENSITY_MODES, "Comfortable"),
        "sparkline": _normalize_choice(sparkline, SPARKLINE_STYLES, "Filled"),
        "palette": _normalize_choice(palette, PALETTE_OPTIONS, "Default"),
    }
    bluf_options = _js_options(BLUF_MODES, payload["bluf_mode"])
    density_options = _js_options(DENSITY_MODES, payload["density"])
    sparkline_options = _js_options(SPARKLINE_STYLES, payload["sparkline"])
    palette_options = _js_options(PALETTE_OPTIONS, payload["palette"])
    next_theme_label = "LIGHT" if payload["theme"] == "dark" else "DARK"
    return f"""
<script>
(function () {{
  const parentWindow = window.parent || window;
  let doc;
  try {{
    doc = parentWindow.document;
  }} catch (error) {{
    return;
  }}
  const existing = doc.getElementById('floating-preference-bridge');
  if (existing) {{
    existing.remove();
  }}
  const styleId = 'floating-preference-bridge-style';
  if (!doc.getElementById(styleId)) {{
    const style = doc.createElement('style');
    style.id = styleId;
    style.textContent = `
      #floating-preference-bridge {{
        position: fixed;
        top: 12px;
        right: 24px;
        z-index: 999999;
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 8px;
        border: 1px solid var(--border, #2f3946);
        border-radius: 8px;
        background: var(--panel, #111821);
        color: var(--fg, #f0f4fa);
        box-shadow: 0 14px 30px rgba(0,0,0,0.28);
        font: 700 12px/1.2 var(--font-prose, system-ui, sans-serif);
      }}
      #floating-preference-bridge label {{
        display: flex;
        align-items: center;
        gap: 4px;
        color: var(--fg-dim, #d7dde7);
        white-space: nowrap;
      }}
      #floating-preference-bridge select,
      #floating-preference-bridge button {{
        min-height: 34px;
        border: 1px solid var(--border, #2f3946);
        border-radius: 7px;
        background: var(--panel-2, #192231);
        color: var(--fg, #f0f4fa);
        font: 700 12px/1.2 var(--font-prose, system-ui, sans-serif);
      }}
      #floating-preference-bridge button {{
        padding: 0 10px;
        cursor: pointer;
      }}
      #floating-preference-bridge select {{
        max-width: 116px;
        padding: 0 24px 0 8px;
      }}
      @media (max-width: 900px) {{
        #floating-preference-bridge {{
          left: 12px;
          right: 12px;
          top: auto;
          bottom: 12px;
          overflow-x: auto;
        }}
      }}
    `;
    doc.head.appendChild(style);
  }}

  function setParam(key, value) {{
    const url = new URL(parentWindow.location.href);
    url.searchParams.set(key, value);
    parentWindow.location.assign(url.toString());
  }}

  const panel = doc.createElement('div');
  panel.id = 'floating-preference-bridge';
  panel.setAttribute('aria-label', 'Floating view preferences and header controls');
  panel.innerHTML = `
    <button type="button" data-bridge-action="refresh" title="Refresh market data">REFRESH</button>
    <button type="button" data-bridge-action="toggle_theme" title="Switch theme">{next_theme_label}</button>
    <label>VIEW<select data-bridge-param="{BRIDGE_BLUF_PARAM}">{bluf_options}</select></label>
    <label>DENSITY<select data-bridge-param="{BRIDGE_DENSITY_PARAM}">{density_options}</select></label>
    <label>SPARK<select data-bridge-param="{BRIDGE_SPARKLINE_PARAM}">{sparkline_options}</select></label>
    <label>PALETTE<select data-bridge-param="{BRIDGE_PALETTE_PARAM}">{palette_options}</select></label>
  `;
  panel.addEventListener('click', function (event) {{
    const button = event.target.closest('button[data-bridge-action]');
    if (!button) {{
      return;
    }}
    setParam('{BRIDGE_ACTION_PARAM}', button.getAttribute('data-bridge-action'));
  }});
  panel.addEventListener('change', function (event) {{
    const select = event.target.closest('select[data-bridge-param]');
    if (!select) {{
      return;
    }}
    setParam(select.getAttribute('data-bridge-param'), select.value);
  }});
  doc.body.appendChild(panel);
}})();
</script>
"""


def apply_control_bridge_query_actions(
    session_state: MutableMapping[str, Any],
    query_params: MutableMapping[str, Any],
    *,
    refresh_callback: Callable[[], Any] | None = None,
) -> BridgeActionResult:
    """Apply and consume query params emitted by the floating control bridge."""
    consumed_keys = tuple(key for key in CONTROL_BRIDGE_PARAMS if _query_value(query_params, key))
    changed_keys: list[str] = []
    refreshed = False

    action = _query_value(query_params, BRIDGE_ACTION_PARAM)
    if action == "toggle_theme":
        current = str(session_state.get("theme", "dark")).strip().lower()
        next_theme = "light" if current == "dark" else "dark"
        if session_state.get("theme") != next_theme:
            session_state["theme"] = next_theme
            changed_keys.append("theme")
    elif action == "refresh":
        if refresh_callback is not None:
            refresh_callback()
        session_state.pop("dashboard_compute_snapshot", None)
        refreshed = True

    _apply_choice(session_state, "bluf_mode", _query_value(query_params, BRIDGE_BLUF_PARAM), BLUF_MODES, changed_keys)
    _apply_choice(
        session_state,
        "view_density",
        _query_value(query_params, BRIDGE_DENSITY_PARAM),
        DENSITY_MODES,
        changed_keys,
    )
    _apply_choice(
        session_state,
        "sparkline_style",
        _query_value(query_params, BRIDGE_SPARKLINE_PARAM),
        SPARKLINE_STYLES,
        changed_keys,
    )
    _apply_choice(
        session_state,
        "color_palette",
        _query_value(query_params, BRIDGE_PALETTE_PARAM),
        PALETTE_OPTIONS,
        changed_keys,
    )

    for key in consumed_keys:
        _delete_query_param(query_params, key)
    changed = bool(changed_keys or refreshed)
    return BridgeActionResult(
        consumed=bool(consumed_keys),
        changed=changed,
        should_rerun=bool(consumed_keys),
        refreshed=refreshed,
        changed_keys=tuple(changed_keys),
    )


def _apply_choice(
    session_state: MutableMapping[str, Any],
    key: str,
    raw_value: str,
    allowed: tuple[str, ...],
    changed_keys: list[str],
) -> None:
    if not raw_value:
        return
    value = _normalize_choice(raw_value, allowed, "")
    if not value:
        return
    if session_state.get(key) != value:
        session_state[key] = value
        changed_keys.append(key)


def _normalize_choice(value: Any, allowed: tuple[str, ...], default: str) -> str:
    text = str(value or "").strip()
    for option in allowed:
        if text.lower() == option.lower():
            return option
    return default


def _query_value(query_params: MutableMapping[str, Any], key: str) -> str:
    raw = query_params.get(key)
    if isinstance(raw, (list, tuple)):
        raw = raw[0] if raw else ""
    return str(raw or "").strip()


def _delete_query_param(query_params: MutableMapping[str, Any], key: str) -> None:
    try:
        del query_params[key]
    except KeyError:
        pass


def _js_options(options: tuple[str, ...], selected: str) -> str:
    return "".join(
        f'<option value="{escape(option, quote=True)}"{" selected" if option == selected else ""}>'
        f"{escape(option)}</option>"
        for option in options
    )
