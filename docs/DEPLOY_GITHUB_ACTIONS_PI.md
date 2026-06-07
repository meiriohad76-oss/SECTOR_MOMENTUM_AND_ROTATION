# GitHub Actions Auto-Deploy To The Pi

This repo includes `.github/workflows/deploy-pi.yml` for automatic deployment to the Raspberry Pi whenever `backlog-stepwise-qa` is pushed, plus manual runs through GitHub Actions `workflow_dispatch`. The workflow targets the repo self-hosted runner labeled `sector-pi` on the Pi so the deploy does not require exposing raw SSH to the public internet.

## Required GitHub Secrets

Set these repository secrets in GitHub:

| Secret | Example | Notes |
|---|---|---|
| `PI_HOST` | `<pi-host-or-lan-ip>` | The Pi host reachable from the GitHub runner. Use a public/tunnel endpoint if GitHub cannot reach your LAN IP. |
| `PI_USER` | `<pi-ssh-user>` | SSH user on the Pi. |
| `PI_SSH_KEY` | private key text | Private key for a deploy-only key whose public half is in `~/.ssh/authorized_keys` on the Pi. |
| `PI_KNOWN_HOSTS` | `<pi-host> ssh-ed25519 ...` | Pinned SSH host key line for the Pi. Generate from a trusted machine with `ssh-keyscan -H <pi-host>` and verify it before saving. |
| `PI_REPO_PATH` | `/home/<pi-user>/<repo-dir>` | Existing checkout on the Pi. |
| `PI_SERVICE_NAME` | `sector-dashboard` | Optional; defaults to `sector-dashboard` when unset. |

Before saving values in GitHub, you can export the same names locally and run a no-secret-output preflight:

```bash
python scripts/check_pi_deploy_config.py
```

The preflight prints only configured/missing secret names. It does not print the private key, known-hosts line, host value, or repo path.

## What The Workflow Does

On push to `backlog-stepwise-qa`, the self-hosted `sector-pi` runner SSHes to the Pi and runs:

```bash
cd "$PI_REPO_PATH"
git fetch origin backlog-stepwise-qa
git checkout backlog-stepwise-qa
git pull --ff-only origin backlog-stepwise-qa
./.venv/bin/python -m pip install -r requirements.txt
./.venv/bin/python -m playwright install chromium
./.venv/bin/python -m pytest -q
./.venv/bin/python scripts/enforce_safe_config.py --secrets-path "$PI_REPO_PATH/.streamlit/secrets.toml"
./.venv/bin/python scripts/install_user_timers.py --repo-root "$PI_REPO_PATH"
./.venv/bin/python scripts/smoke_provider_flow_lanes.py --ticker SPY --limit 25 --timeout 20 --require-massive
./.venv/bin/python scripts/warm_provider_flow_cache.py --universe us-sectors --timeout 20
./.venv/bin/python scripts/refresh_dashboard_state.py --period 3y --provider-flow-mode cache-only
./.venv/bin/python scripts/check_ops_readiness.py --strict-production
./.venv/bin/python scripts/restart_sector_dashboard.py --service "$PI_SERVICE_NAME" --url "http://127.0.0.1:8501/?ticker=XLK" --timeout-seconds 60
./.venv/bin/python scripts/rendered_dashboard_smoke.py --url "http://127.0.0.1:8501/?ticker=XLK" --timeout-ms 120000 --output-json "$PI_REPO_PATH/data/rendered_dashboard_smoke/latest.json"
systemctl --user reset-failed sector-rendered-dashboard-smoke.service || true
systemctl --user start sector-rendered-dashboard-smoke.service
./.venv/bin/python scripts/check_ops_readiness.py --strict-production --require-rendered-smoke
./.venv/bin/python scripts/smoke_deploy_gate.py \
  --local-dashboard-url "http://127.0.0.1:8501/?ticker=XLK" \
  --state-file "$PI_REPO_PATH/data/state.json" \
  --min-state-tickers 80 \
  --max-state-age-seconds 300 \
  --public-dashboard-url "https://sentimentdashboard.ahaddashboards.uk/?ticker=XLK" \
  --expect-cloudflare-access
```

If tests pass, it enforces `MASSIVE_VERIFY_SSL = "true"` and enables the cached Massive/FINRA provider-flow lanes in the Pi-local Streamlit secrets file without printing or changing API keys, installs/refreshes the non-sudo user timers for transition-feed exports, Massive provider snapshot capture, provider-flow cache warming, and headless state refresh, runs a narrow secret-safe Massive/FINRA provider-flow smoke for `SPY`, warms the US-sector provider-flow cache, refreshes the dashboard state/run journal headlessly, runs strict secret-safe ops-readiness gates, terminates the current Streamlit service `MainPID` so systemd restarts the dashboard, then polls `http://127.0.0.1:8501/?ticker=XLK` until the service is active and HTTP returns `200`.
After restart, it runs a mandatory rendered Playwright smoke against the local Streamlit URL and records `data/rendered_dashboard_smoke/latest.json`. It then starts the installed `sector-rendered-dashboard-smoke.service` once, proving the scheduled user-service command itself works and refreshing its `last_service_state`; a second strict readiness pass requires the fresh browser evidence before the final public/Cloudflare deploy smoke.

## Pi Requirements

- The repo self-hosted runner is online with the `sector-pi` label.
- The Pi checkout already exists at `PI_REPO_PATH`.
- The Pi repo can pull from GitHub without an interactive prompt.
- The `.venv` exists and has `requirements.txt` installed.
- The SSH user can read the repo and terminate the Streamlit service process.
- The runner can reach `PI_HOST` over SSH. With a runner on the same Pi or LAN, a private LAN hostname/IP is usually sufficient.

If you later remove the self-hosted runner and switch back to GitHub-hosted runners, `PI_HOST` must become a GitHub-reachable SSH endpoint through a secure tunnel or VPN. Do not open raw SSH to the internet without firewall and key-only hardening.
