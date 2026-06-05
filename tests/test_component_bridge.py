from __future__ import annotations

from types import SimpleNamespace

from src import component_bridge


def test_drill_bridge_attributes_escape_ticker_and_label_values():
    attrs = component_bridge.drill_bridge_attrs('xlk" onclick="bad', label='Tech <sector>')

    assert 'data-drill-ticker="XLKONCLICKBAD"' in attrs
    assert 'role="button"' in attrs
    assert 'tabindex="0"' in attrs
    assert 'aria-label="Open XLKONCLICKBAD drill-down for Tech &lt;sector&gt;"' in attrs
    assert " onclick=" not in attrs.lower()


def test_drill_click_bridge_preserves_query_params_and_sets_ticker():
    html = component_bridge.drill_click_bridge_html()

    assert "data-drill-ticker" in html
    assert "new URL(parentWindow.location.href)" in html
    assert "url.searchParams.set('ticker', ticker)" in html
    assert "url.hash = 'drill'" in html
    assert "parentWindow.location.assign(url.toString())" in html
    assert "keydown" in html
    assert "Enter" in html
    assert " " in html


def test_rrg_plotly_click_bridge_uses_point_text_as_drill_ticker():
    fig = SimpleNamespace(to_html=lambda **kwargs: '<div id="rrg-test"></div><script>Plotly.newPlot()</script>')

    html = component_bridge.rrg_plotly_click_bridge_html(fig, div_id="rrg-test")

    assert 'id="rrg-test"' in html
    assert "plotly_click" in html
    assert "point.text" in html
    assert "setTicker(ticker)" in html


def test_control_bridge_applies_query_actions_and_clears_consumed_params():
    session = {
        "theme": "dark",
        "bluf_mode": "Verdict",
        "view_density": "Comfortable",
        "sparkline_style": "Filled",
        "color_palette": "Default",
    }
    query = {
        "bridge_action": ["toggle_theme"],
        "bridge_bluf_mode": "Hidden",
        "bridge_density": "Compact",
        "bridge_sparkline": "Line",
        "bridge_palette": "Nord",
        "ticker": "XLK",
    }

    result = component_bridge.apply_control_bridge_query_actions(session, query)

    assert result.consumed is True
    assert result.changed is True
    assert result.should_rerun is True
    assert result.refreshed is False
    assert session == {
        "theme": "light",
        "bluf_mode": "Hidden",
        "view_density": "Compact",
        "sparkline_style": "Line",
        "color_palette": "Nord",
    }
    assert query == {"ticker": "XLK"}
    assert result.changed_keys == (
        "theme",
        "bluf_mode",
        "view_density",
        "sparkline_style",
        "color_palette",
    )


def test_control_bridge_refresh_calls_cache_clear_without_secret_payloads():
    calls = []
    session = {"theme": "dark", "dashboard_compute_snapshot": object()}
    query = {"bridge_action": "refresh", "bridge_palette": "Bearer SECRET"}

    result = component_bridge.apply_control_bridge_query_actions(
        session,
        query,
        refresh_callback=lambda: calls.append("cleared"),
    )

    assert calls == ["cleared"]
    assert "dashboard_compute_snapshot" not in session
    assert query == {}
    assert result.refreshed is True
    assert result.changed is True
    assert "SECRET" not in repr(result)


def test_floating_control_bridge_html_is_custom_component_payload():
    html = component_bridge.floating_control_bridge_html(
        theme="dark",
        bluf_mode="Verdict",
        density="Comfortable",
        sparkline="Filled",
        palette="Default",
    )

    assert "floating-preference-bridge" in html
    assert "bridge_action" in html
    assert "toggle_theme" in html
    assert "bridge_bluf_mode" in html
    assert "bridge_density" in html
    assert "bridge_sparkline" in html
    assert "bridge_palette" in html
    assert "VIEW" in html
