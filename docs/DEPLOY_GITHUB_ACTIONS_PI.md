# GitHub Actions Auto-Deploy To The Pi

This repo includes `.github/workflows/deploy-pi.yml` for automatic deployment to the Raspberry Pi whenever `backlog-stepwise-qa` is pushed, plus manual runs through GitHub Actions `workflow_dispatch`.

## Required GitHub Secrets

Set these repository secrets in GitHub:

| Secret | Example | Notes |
|---|---|---|
| `PI_HOST` | `10.100.102.18` | The Pi host reachable from the GitHub runner. Use a public/tunnel endpoint if GitHub cannot reach your LAN IP. |
| `PI_USER` | `ahad` | SSH user on the Pi. |
| `PI_SSH_KEY` | private key text | Private key for a deploy-only key whose public half is in `~/.ssh/authorized_keys` on the Pi. |
| `PI_KNOWN_HOSTS` | `10.100.102.18 ssh-ed25519 ...` | Pinned SSH host key line for the Pi. Generate from a trusted machine with `ssh-keyscan -H <pi-host>` and verify it before saving. |
| `PI_REPO_PATH` | `/home/ahad/SECTOR_MOMENTUM_AND_ROTATION` | Existing checkout on the Pi. |
| `PI_SERVICE_NAME` | `sector-dashboard` | Optional; defaults to `sector-dashboard` when unset. |

## What The Workflow Does

On push to `backlog-stepwise-qa`, the workflow SSHes to the Pi and runs:

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

- The Pi checkout already exists at `PI_REPO_PATH`.
- The Pi repo can pull from GitHub without an interactive prompt.
- The `.venv` exists and has `requirements.txt` installed.
- The SSH user can read the repo and terminate the Streamlit service process.
- GitHub Actions can reach `PI_HOST` over SSH.

If the Pi is only reachable on the home LAN, keep using manual SSH deploys until you expose SSH through a secure tunnel or self-hosted runner. Do not open raw SSH to the internet without firewall and key-only hardening.
