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
./.venv/bin/python -m pytest -q
```

If tests pass, it terminates the current Streamlit service `MainPID` so systemd restarts the dashboard, then polls `http://127.0.0.1:8501/?ticker=XLK` until the service is active and HTTP returns `200`.

## Pi Requirements

- The repo self-hosted runner is online with the `sector-pi` label.
- The Pi checkout already exists at `PI_REPO_PATH`.
- The Pi repo can pull from GitHub without an interactive prompt.
- The `.venv` exists and has `requirements.txt` installed.
- The SSH user can read the repo and terminate the Streamlit service process.
- The runner can reach `PI_HOST` over SSH. With a runner on the same Pi or LAN, a private LAN hostname/IP is usually sufficient.

If you later remove the self-hosted runner and switch back to GitHub-hosted runners, `PI_HOST` must become a GitHub-reachable SSH endpoint through a secure tunnel or VPN. Do not open raw SSH to the internet without firewall and key-only hardening.
