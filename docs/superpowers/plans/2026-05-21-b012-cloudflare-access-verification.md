# B-012 Cloudflare Access Verification Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:verification-before-completion before marking this ticket complete. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Confirm the public dashboard URL is protected by Cloudflare Access before treating the tunnel as production-safe.

**Architecture:** No app code changes. Verification is performed from unauthenticated HTTP clients and recorded in docs so later agents do not have to infer policy state from screenshots.

**Tech Stack:** Cloudflare Access, curl, existing Streamlit/Pi deployment.

---

## Verification Steps

- [x] **Step 1: Check unauthenticated public headers from Windows**

Run:

```powershell
curl.exe --ssl-no-revoke -I -L --max-time 20 https://sentimentdashboard.ahaddashboards.uk
```

Observed on 2026-05-21:

- Initial response: `HTTP/1.1 302 Found`
- `Www-Authenticate: Cloudflare-Access ...`
- `Location: https://ahadahad.cloudflareaccess.com/cdn-cgi/access/login/...`
- Final response: `HTTP/1.1 200 OK`
- `CF-Access-Domain: sentimentdashboard.ahaddashboards.uk`

- [x] **Step 2: Check unauthenticated public HTML from Windows**

Run:

```powershell
curl.exe --ssl-no-revoke -s -L --max-time 20 https://sentimentdashboard.ahaddashboards.uk
```

Observed on 2026-05-21:

- HTML title: `Sign in - Cloudflare Access`
- Access login page content returned instead of Streamlit dashboard HTML.

- [x] **Step 3: Check unauthenticated public headers from the Pi**

Run:

```powershell
ssh -i "$env:USERPROFILE\.ssh\codex_ahadpi_ed25519" -o BatchMode=yes -o ConnectTimeout=8 ahad@10.100.102.18 "curl -I -L --max-time 20 https://sentimentdashboard.ahaddashboards.uk || true"
```

Observed on 2026-05-21:

- Initial response: `HTTP/2 302`
- `www-authenticate: Cloudflare-Access ...`
- Final response: `HTTP/2 200`
- `cf-access-domain: sentimentdashboard.ahaddashboards.uk`

## Result

B-012 is verified. Unauthenticated public requests reach the Cloudflare Access sign-in flow, not the dashboard.

## Residual Risk

This check proves the public unauthenticated path is locked down at verification time. It does not prove every allowed email policy member is correct, and it should be rerun after Cloudflare Access policy edits.
