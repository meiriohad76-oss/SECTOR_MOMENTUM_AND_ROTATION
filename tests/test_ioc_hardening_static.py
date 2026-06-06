from __future__ import annotations

import re
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_ioc_audit_file_is_redacted_if_present():
    audit_path = ROOT / "docs" / "IOC_AUDIT_2026-05-27.md"
    if not audit_path.exists():
        return

    text = audit_path.read_text(encoding="utf-8")

    assert "MASSIVE_VERIFY_SSL = \"false\"" not in text
    assert not re.search(r'MASSIVE_API_KEY\s*=\s*"(?!\[REDACTED|""|your-)[^"]{12,}"', text)
    assert not re.search(r"Bearer\s+(?!\[REDACTED)[A-Za-z0-9_.\-]{20,}", text)


def test_streamlit_config_sets_safe_server_defaults():
    config_path = ROOT / ".streamlit" / "config.toml"

    config = tomllib.loads(config_path.read_text(encoding="utf-8"))

    assert config["server"]["headless"] is True
    assert config["server"]["address"] == "127.0.0.1"
    assert config["server"]["port"] == 8501
    assert config["server"]["fileWatcherType"] == "none"
    assert config["server"]["maxUploadSize"] == 5
    assert config["browser"]["gatherUsageStats"] is False
    assert config["theme"]["base"] == "dark"


def test_streamlit_secret_template_keeps_tls_on_and_free_finra_live():
    template = (ROOT / ".streamlit" / "secrets.toml.example").read_text(encoding="utf-8")
    parsed = tomllib.loads(template)

    assert parsed["MASSIVE_VERIFY_SSL"] == "true"
    assert parsed["FINRA_ATS_STUB_MODE"] == "false"
    assert parsed["FINRA_SHORT_INTEREST_STUB_MODE"] == "false"
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert ".streamlit/secrets.toml" in gitignore
    assert "docs/IOC_AUDIT_*.md" in gitignore


def test_systemd_template_targets_current_ahadpi5_checkout():
    unit = (ROOT / "systemd" / "sector-dashboard.service").read_text(encoding="utf-8")

    assert "User=ahad" in unit
    assert "Group=ahad" in unit
    assert "WorkingDirectory=/home/ahad/SECTOR_MOMENTUM_AND_ROTATION" in unit
    assert "Environment=STATE_FILE=/home/ahad/SECTOR_MOMENTUM_AND_ROTATION/data/state.json" in unit
    assert (
        "Environment=STATE_TRANSITION_JOURNAL=/home/ahad/SECTOR_MOMENTUM_AND_ROTATION/data/state_transitions.jsonl"
        in unit
    )
    assert "/home/ahad/SECTOR_MOMENTUM_AND_ROTATION/.venv/bin/streamlit run app.py" in unit
    assert "/home/meiri/sector-rotation-dashboard" not in unit


def test_production_dashboard_hides_internal_ticket_and_debug_labels():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")

    removed_labels = [
        "COMPONENT DOCS",
        "B-111",
        "B-115",
        "B-130",
        "B-105",
        "B-163",
        "B-158 / B-160",
        "B-011",
        "B-132",
        "B-153",
        "B-131",
        "+2 24H",
        "FLOW FEEDS STUBBED",
        "MEIRI / READ-ONLY",
    ]
    ui_region_start = app_source.index("def render_explainer():")
    ui_region = app_source[ui_region_start:]

    for label in removed_labels:
        assert label not in ui_region

    assert "_operator_mode_enabled()" in app_source
    assert "Component inventory" in app_source
