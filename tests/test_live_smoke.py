from __future__ import annotations

from src.live_smoke import classify_local_dashboard_response, classify_protected_dashboard_response


def test_classifies_cloudflare_access_challenge_as_healthy_protected_route():
    result = classify_protected_dashboard_response(
        status_code=302,
        headers={
            "Location": "https://ahadahad.cloudflareaccess.com/cdn-cgi/access/login/sentimentdashboard",
            "Www-Authenticate": "Cloudflare-Access",
        },
        text="",
    )

    assert result.ok is True
    assert result.state == "cloudflare_access_challenge"


def test_classifies_authenticated_dashboard_as_healthy_route():
    result = classify_protected_dashboard_response(
        status_code=200,
        headers={},
        text="<html><body>SENTIMENT BOARD <section>Data and dashboard health</section></body></html>",
    )

    assert result.ok is True
    assert result.state == "authenticated_dashboard"


def test_classifies_followed_cloudflare_access_page_as_healthy_challenge():
    result = classify_protected_dashboard_response(
        status_code=200,
        headers={},
        text="<html><title>Sign in - Cloudflare Access</title><body>Cloudflare Access</body></html>",
    )

    assert result.ok is True
    assert result.state == "cloudflare_access_challenge"


def test_rejects_ambiguous_public_200_without_dashboard_or_access_markers():
    result = classify_protected_dashboard_response(
        status_code=200,
        headers={},
        text="<html><body>Welcome</body></html>",
    )

    assert result.ok is False
    assert result.state == "unexpected_response"


def test_classifies_local_streamlit_shell_as_healthy_smoke():
    result = classify_local_dashboard_response(
        status_code=200,
        text="<html><head><title>Streamlit</title></head><script src='./static/js/index.js'></script></html>",
    )

    assert result.ok is True
    assert result.state == "streamlit_shell"


def test_classifies_local_nextjs_shell_as_healthy_smoke():
    """Next.js app router responses contain __NEXT_DATA__ — accept them as a valid shell."""
    nextjs_body = (
        '<html><head></head><body>'
        '<script id="__NEXT_DATA__" type="application/json">{"page":"/"}</script>'
        '<script src="/_next/static/chunks/main.js"></script>'
        '</body></html>'
    )
    result = classify_local_dashboard_response(status_code=200, text=nextjs_body)

    assert result.ok is True
    assert result.state == "nextjs_shell"


def test_strict_local_dashboard_smoke_rejects_streamlit_shell_without_dashboard_markers():
    result = classify_local_dashboard_response(
        status_code=200,
        text="<html><head><title>Streamlit</title></head><script src='./static/js/index.js'></script></html>",
        require_dashboard_markers=True,
    )

    assert result.ok is False
    assert result.state == "missing_dashboard_markers"
    assert "sentiment board" in result.detail


def test_strict_local_dashboard_smoke_requires_all_core_markers():
    result = classify_local_dashboard_response(
        status_code=200,
        text="<html><body>SENTIMENT BOARD BLUF Data and dashboard health</body></html>",
        require_dashboard_markers=True,
    )

    assert result.ok is True
    assert result.state == "dashboard_content"


def test_rejects_upstream_cloudflare_errors():
    result = classify_protected_dashboard_response(
        status_code=530,
        headers={},
        text="origin unavailable",
    )

    assert result.ok is False
    assert result.state == "upstream_error"
