from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_browser_qa_script_imports_playwright_only_inside_runner():
    script = (ROOT / "scripts" / "capture_browser_qa.py").read_text(encoding="utf-8")

    assert "sys.path.insert(0, str(ROOT))" in script
    assert "from src.browser_qa import" in script
    assert "from PIL import Image" not in script.split("def _image_nonblank(")[0]
    assert "from playwright.sync_api import" in script
    assert script.index("def _run_playwright_capture(") < script.index("from playwright.sync_api import")
    assert "Install with: python -m pip install playwright && python -m playwright install chromium" in script


def test_browser_qa_script_writes_report_and_manifest():
    script = (ROOT / "scripts" / "capture_browser_qa.py").read_text(encoding="utf-8")

    assert "browser_qa_targets()" in script
    assert "--browser-channel" in script
    assert "--user-data-dir" in script
    assert "--headed" in script
    assert "launch_persistent_context" in script
    assert "channel=browser_channel" in script
    assert "build_browser_qa_report(" in script
    assert "browser_qa_manifest.json" in script
    assert "browser_qa_report.md" in script
    assert "--qa-mode" in script
    assert '"qa_mode": qa_mode' in script
    assert "qa_mode=qa_mode" in script
    assert "screenshot_path.unlink()" in script
    assert "missing_text_checks(" in script
    assert "_wait_for_dashboard_idle(" in script
    assert "COMPUTING INDICATORS" in script
    assert ".replace(\"\\xa0\", \" \")" in script
    assert "getBoundingClientRect()" in script
    assert "dashboard idle timeout after setup" in script
    assert "document.body" in script
    assert "locator(\"body\").inner_text" not in script
    assert "_scroll_to_focus_text(" in script
    assert "_run_target_actions(" in script
    assert "action.startswith(\"expand:\")" in script
    assert "action.startswith(\"radio:\")" in script
    assert "locator(\"label\").filter(has_text=value)" in script
    assert "action == \"hover:first-full-table-row\"" in script
    assert "expect-visible:" in script
    assert "click-drill:" in script
    assert "data-drill-ticker" in script
    assert "Per-ticker drill-down" in script
    assert "expect-scrollable:" in script
    assert "expect-no-document-overlap:" in script
    assert "element.scrollHeight > element.clientHeight" in script
    assert "documentTop" in script
    assert "expect-radio-checked:" in script
    assert "querySelector('input')?.checked" in script
    assert "section[data-testid=\"stMain\"]" in script
    assert "scrollTop" in script
    assert "target.focus_text" in script
    assert "dashboard ready" in script
    assert "min(timeout_ms, 15_000)" in script
    assert "focused text:" in script
    assert "visible=true" in script
    assert "target.wheel_steps" not in script
    assert "target.use_wheel_scan" not in script
    assert "wheel scan:" not in script
    assert "page.mouse.wheel" not in script
    assert ".scroll_into_view_if_needed(" not in script
    assert "--settle-ms" in script
    assert "full_page=False" in script
    assert "page.screenshot(path=str(screenshot_path), full_page=False, timeout=timeout_ms)" in script
    assert "Image.open(" in script


def test_browser_qa_readme_documents_qa_dependencies_and_secret_free_mode():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    requirements = (ROOT / "requirements-qa.txt").read_text(encoding="utf-8")

    assert "python -m pip install -r requirements-qa.txt" in readme
    assert "BROWSER_QA_MODE" in readme
    assert "MASSIVE_API_KEY" in readme
    assert "FRED_API_KEY" in readme
    assert "playwright" in requirements
    assert "pillow" in requirements.lower()
