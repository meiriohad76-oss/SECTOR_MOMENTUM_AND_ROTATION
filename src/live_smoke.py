"""Live smoke-test helpers for deployment and protected routes."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping
from urllib.parse import urlparse


@dataclass(frozen=True)
class ProtectedRouteSmoke:
    ok: bool
    state: str
    detail: str


@dataclass(frozen=True)
class LocalDashboardSmoke:
    ok: bool
    state: str
    detail: str


def _header(headers: Mapping[str, str], name: str) -> str:
    for key, value in headers.items():
        if key.casefold() == name.casefold():
            return str(value)
    return ""


def classify_protected_dashboard_response(
    *,
    status_code: int,
    headers: Mapping[str, str],
    text: str = "",
    expected_host: str = "sentimentdashboard.ahaddashboards.uk",
) -> ProtectedRouteSmoke:
    """Classify whether a public dashboard route reached Access or the app.

    A healthy unauthenticated route should reach Cloudflare Access, not the
    Streamlit app directly. A healthy authenticated route may return the
    dashboard. Ambiguous success pages fail closed because they do not prove the
    deploy target is the protected dashboard.
    """

    body = (text or "")[:10_000].casefold()
    location = _header(headers, "location")
    www_authenticate = _header(headers, "www-authenticate")
    location_host = urlparse(location).netloc.casefold()
    expected = expected_host.casefold()

    if status_code >= 500:
        return ProtectedRouteSmoke(False, "upstream_error", f"HTTP {status_code}")

    if "sentiment board" in body or "data and dashboard health" in body:
        if status_code == 200:
            return ProtectedRouteSmoke(True, "authenticated_dashboard", "dashboard markers present")
        return ProtectedRouteSmoke(False, "unexpected_dashboard_status", f"HTTP {status_code}")

    access_markers = (
        "cloudflare-access" in www_authenticate.casefold()
        or "cloudflareaccess.com" in location_host
        or "/cdn-cgi/access/" in location.casefold()
        or "sign in - cloudflare access" in body
        or "cloudflare access" in body
    )
    if access_markers and status_code in {200, 302, 401, 403}:
        return ProtectedRouteSmoke(True, "cloudflare_access_challenge", f"HTTP {status_code}")

    if status_code == 200 and expected and location_host == expected:
        return ProtectedRouteSmoke(False, "ambiguous_public_200", "missing dashboard or Access markers")

    return ProtectedRouteSmoke(False, "unexpected_response", f"HTTP {status_code}")


def classify_local_dashboard_response(
    *,
    status_code: int,
    text: str = "",
    require_dashboard_markers: bool = False,
) -> LocalDashboardSmoke:
    """Classify whether a local dashboard URL served the Streamlit app content."""

    body = (text or "")[:20_000].casefold()
    if status_code != 200:
        return LocalDashboardSmoke(False, "bad_http_status", f"HTTP {status_code}")
    if "traceback" in body or "uncaught exception" in body or "uncaughtexception" in body:
        return LocalDashboardSmoke(False, "streamlit_error_page", "Streamlit error marker present")
    required_markers = (
        "sentiment board",
        "data and dashboard health",
        "bluf",
    )
    present_markers = [marker for marker in required_markers if marker in body]
    if len(present_markers) == len(required_markers):
        return LocalDashboardSmoke(True, "dashboard_content", "dashboard markers present")
    if require_dashboard_markers:
        missing = [marker for marker in required_markers if marker not in present_markers]
        return LocalDashboardSmoke(False, "missing_dashboard_markers", f"missing: {', '.join(missing)}")
    if len(present_markers) >= 2:
        return LocalDashboardSmoke(True, "dashboard_content_partial", "partial dashboard markers present")
    if "<title>streamlit</title>" in body and "static/js/" in body:
        return LocalDashboardSmoke(True, "streamlit_shell", "Streamlit shell served")
    # Next.js app router pages contain __next_data__ or _next/static in the HTML.
    # Accept them as a valid shell so the deploy gate passes after the Streamlit →
    # Next.js cutover, even without the legacy Streamlit section markers.
    if "__next" in body or "_next/static" in body:
        return LocalDashboardSmoke(True, "nextjs_shell", "Next.js app served")
    return LocalDashboardSmoke(False, "wrong_content", "missing dashboard markers")
