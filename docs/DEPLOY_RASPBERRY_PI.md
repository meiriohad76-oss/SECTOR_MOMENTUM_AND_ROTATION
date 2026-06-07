# Deploying the dashboard on a Raspberry Pi (24/7)

This guide covers a clean install on a fresh Raspberry Pi, configured to auto-start the dashboard on boot and keep it running. For exposing it to the internet via your own domain, follow up with [`DEPLOY_CLOUDFLARE_TUNNEL.md`](DEPLOY_CLOUDFLARE_TUNNEL.md).

## Hardware

- **Raspberry Pi 4 (4 GB or 8 GB)** or **Pi 5** — anything older struggles with pandas + yfinance simultaneously.
- microSD card (32 GB+), or better: an SSD via USB-3 (boots noticeably faster).
- Ethernet recommended for stability; Wi-Fi works.
- Power supply (official one — undervoltage warnings tank performance).

## OS install

1. Download **Raspberry Pi Imager**: https://www.raspberrypi.com/software/.
2. Flash **Raspberry Pi OS Lite (64-bit)** — Bookworm or newer. The Lite (no GUI) image is plenty.
3. Before clicking Write, press `Ctrl+Shift+X` to open advanced options:
   - Set hostname: `sector-pi`
   - Enable SSH (with public-key auth ideally, or password)
   - Set username (e.g. `meiri`) and password
   - Configure Wi-Fi if not using Ethernet
4. Boot the Pi. Find its IP from your router or with `arp -a` from another machine.
5. SSH in: `ssh meiri@<pi-ip>` (or `ssh meiri@sector-pi.local` on most home networks).

## System packages

```bash
sudo apt update && sudo apt full-upgrade -y
sudo apt install -y python3-venv python3-pip git curl
python3 --version    # should be 3.11.x on Bookworm
```

## Clone the repo and create the venv

Assuming your GitHub repo is at `https://github.com/<you>/sector-rotation-dashboard`:

```bash
cd ~
git clone https://github.com/<you>/sector-rotation-dashboard.git
cd sector-rotation-dashboard

python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Test it manually first:

```bash
streamlit run app.py --server.address 0.0.0.0 --server.port 8501 --server.headless true
```

From another machine on your LAN, open `http://<pi-ip>:8501`. You should see the dashboard.

`Ctrl+C` to stop. Now we install it as a service so it runs on boot.

## Configure local secrets

Provider keys are intentionally not committed. Put Pi-local secrets in `.streamlit/secrets.toml` under the repo root and keep the file readable only by the service user:

```bash
cd "$PI_REPO_PATH"
mkdir -p .streamlit
chmod 700 .streamlit
nano .streamlit/secrets.toml
chmod 600 .streamlit/secrets.toml
```

For Massive OHLCV validation, set:

```toml
MASSIVE_API_KEY = "..."
```

For FRED macro validation, set:

```toml
FRED_API_KEY = "..."
```

Validate without writing backtest artifacts:

```bash
OHLCV_PROVIDER=massive ./.venv/bin/python scripts/run_backtest.py --live-smoke --smoke-period 2mo
```

Expected success:

```text
Live backtest smoke passed for 14 tickers with provider=massive period=2mo; artifacts were not written.
```

## Auto-start with systemd

The repo ships a service unit at `systemd/sector-dashboard.service`. Install it:

```bash
# Adjust the User= line and ExecStart paths if your username/path differ
sudo cp systemd/sector-dashboard.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable sector-dashboard
sudo systemctl start  sector-dashboard

# Verify
sudo systemctl status sector-dashboard
```

You should see `active (running)`. The dashboard is now reachable at `http://<pi-ip>:8501` and will restart on boot or after a crash.

### Optional public methodology landing service

B-152 ships a static public landing page under `public/`. To serve it from the same Pi, install `systemd/methodology-landing.service`, adjust the user/path, and bind it to localhost port 8500:

```bash
sudo cp systemd/methodology-landing.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now methodology-landing
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8500/
```

Use Cloudflare Tunnel to expose `http://127.0.0.1:8500` on the public root while keeping the Streamlit dashboard on `http://127.0.0.1:8501`.

### Useful commands

```bash
./.venv/bin/python scripts/restart_sector_dashboard.py --service sector-dashboard
sudo systemctl stop sector-dashboard
sudo systemctl status sector-dashboard
journalctl -u sector-dashboard -f         # live logs (Ctrl+C to exit)
journalctl -u sector-dashboard --since "1 hour ago"
```

The restart helper is the preferred non-interactive deploy path over SSH. It reads the
systemd `MainPID`, sends `SIGTERM` to the running Streamlit process, lets the
`Restart=always` service policy start a fresh process, and polls
`http://127.0.0.1:8501/?ticker=XLK` until it returns HTTP 200. It does not call
`sudo`, so it works with `ssh -o BatchMode=yes`.

## Updating the dashboard later

```bash
cd "$PI_REPO_PATH"
git pull
source .venv/bin/activate
pip install -r requirements.txt           # if dependencies changed
./.venv/bin/python scripts/restart_sector_dashboard.py --service sector-dashboard
```

## Optional: schedule a nightly state-refresh

The state machine advances every page-load. If you want it to advance even when nobody opens the page (so the alert log captures changes overnight), add a cron entry:

```bash
crontab -e
```

Append:
```
0 22 * * * curl -s http://localhost:8501/?refresh=1 > /dev/null 2>&1
```

This hits the dashboard at 22:00 daily, which forces a state-machine pass.

## Verify durable state persistence

The Pi should keep dashboard memory under the checkout's `data/` directory, not
only in repo-root `state.json`. The service template sets:

```ini
Environment=STATE_FILE=/home/<pi-user>/<repo-dir>/data/state.json
Environment=STATE_TRANSITION_JOURNAL=/home/<pi-user>/<repo-dir>/data/state_transitions.jsonl
```

After deploy/restart, verify the paths and counts:

```bash
cd "$PI_REPO_PATH"
./.venv/bin/python - <<'PY'
from src.scoring import state_storage_health
print(state_storage_health())
PY
ls -lah data/state.json data/state_transitions.jsonl data/state_backups 2>/dev/null || true
```

If a legacy repo-root `state.json` exists and `data/state.json` does not, the app
migrates it into `data/state.json` on the next state read/write. The transition
journal is append-only, so losing or truncating the snapshot should not erase the
Recent transitions panel.

## Optional: schedule the 08:00 ET email digest

B-120 ships a LOW-severity digest script and a systemd timer template. Before enabling the timer, configure the SMTP values in `.streamlit/secrets.toml`, then run a no-send diagnostic:

```bash
cd "$PI_REPO_PATH"
./.venv/bin/python scripts/send_email_digest.py --dry-run
```

Install the timer without sudo as a user service:

```bash
cd "$PI_REPO_PATH"
mkdir -p ~/.config/systemd/user
cp systemd/user/sector-email-digest.service ~/.config/systemd/user/
cp systemd/user/sector-email-digest.timer ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now sector-email-digest.timer
systemctl --user list-timers sector-email-digest.timer
```

The user unit assumes the checkout path configured in the copied service. If your checkout path differs, edit `WorkingDirectory=` and `ExecStart=` in `~/.config/systemd/user/sector-email-digest.service`.

Alternatively, install the root-level system timer:

```bash
sudo cp systemd/sector-email-digest.service /etc/systemd/system/
sudo cp systemd/sector-email-digest.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now sector-email-digest.timer
systemctl list-timers sector-email-digest.timer
```

Adjust the `User=`, `Group=`, and `WorkingDirectory=` values in `/etc/systemd/system/sector-email-digest.service` if your Pi user or checkout path differs. The timer runs at `08:00 America/New_York`; without SMTP secrets or eligible LOW-severity transitions, the job exits cleanly with `email_digest=skipped`.

## Optional: publish transition RSS and iCal feeds

B-122 can write local feed artifacts and optional static copies under `public/feeds/`, which are served by the public methodology landing service when that service is enabled:

```bash
cd "$PI_REPO_PATH"
./.venv/bin/python scripts/export_transition_feeds.py \
  --publish-dir public/feeds \
  --public-base-url https://www.ahaddashboards.uk/feeds/
```

This writes `data/feeds/transitions.rss`, `data/feeds/transitions.ics`, `public/feeds/transitions.rss`, and `public/feeds/transitions.ics`. The generated files are ignored by git and Docker packaging. If you do not expose the public landing service, omit `--publish-dir` and sync `data/feeds/` with your preferred hosting target instead.

To keep the artifacts fresh without sudo, install the user timer:

```bash
cd "$PI_REPO_PATH"
mkdir -p ~/.config/systemd/user
cp systemd/user/sector-transition-feeds.service ~/.config/systemd/user/
cp systemd/user/sector-transition-feeds.timer ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now sector-transition-feeds.timer
systemctl --user list-timers sector-transition-feeds.timer
```

The transition-feed timer exports every 15 minutes into `data/feeds/` and `public/feeds/`. Public validation is complete only when the external route serves RSS XML from `/feeds/transitions.rss` and iCal text from `/feeds/transitions.ics`.

## Optional: schedule Massive provider snapshots

B-161 can persist Massive `/v3/trades` provider snapshots into
`data/provider_snapshots/provider_snapshots.sqlite` for later as-of replay,
calibration, and provider-flow backtesting. The script is storage-only: it does
not change live scoring, vetoes, alerts, or recommendations.

Run a manual capture after `MASSIVE_API_KEY` is configured in
`.streamlit/secrets.toml`:

```bash
cd "$PI_REPO_PATH"
./.venv/bin/python scripts/capture_massive_provider_snapshots.py \
  --universe scored \
  --limit 5000 \
  --timeout 20
```

The `scored` universe captures the dashboard matrix and defensive instruments.
Use repeated `--ticker XLK` arguments for a narrow smoke test, or `--universe
all` if you also want benchmark tickers.

Install the post-market user timer without sudo:

```bash
cd "$PI_REPO_PATH"
mkdir -p ~/.config/systemd/user
cp systemd/user/sector-massive-provider-snapshots.service ~/.config/systemd/user/
cp systemd/user/sector-massive-provider-snapshots.timer ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now sector-massive-provider-snapshots.timer
systemctl --user list-timers sector-massive-provider-snapshots.timer
```

The timer runs Monday-Friday at `18:45 America/New_York`, after the regular US
market close. Verify storage health with:

```bash
sqlite3 data/provider_snapshots/provider_snapshots.sqlite \
  "pragma integrity_check; select count(*) from provider_snapshots;"
```

The capture job is ticker-isolated: one failed ticker does not stop the rest of
the universe from being saved. The script prints a final
`massive_provider_snapshot_summary requested=N saved=N failed=N` line. Exit code
`0` means every requested ticker was saved, `1` means partial success, and `2`
means nothing was saved or the job could not start. The consolidated readiness
check also reports the snapshot DB row count and whether the user timer is
installed, enabled, and active:

```bash
./.venv/bin/python scripts/check_ops_readiness.py
```

## Resource notes

On a Pi 4 with 4 GB RAM and the full 67-ticker universe:
- First data fetch: ~60 seconds (cold cache from Yahoo)
- Memory footprint: ~600 MB resident
- CPU: spikes during indicator computation, idle while idle (Streamlit caches everything)
- Disk: <100 MB total (the venv is ~250 MB)

If you see memory pressure, edit `src/universe.py` to trim the universe (e.g. drop the country ETFs or factor ETFs).

## Next: expose it publicly

Right now the dashboard is only reachable from your home LAN. To expose the public methodology root and protected dashboard securely without port-forwarding, see [`DEPLOY_CLOUDFLARE_TUNNEL.md`](DEPLOY_CLOUDFLARE_TUNNEL.md).
