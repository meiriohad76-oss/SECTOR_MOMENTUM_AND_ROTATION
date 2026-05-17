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

### Useful commands

```bash
sudo systemctl restart sector-dashboard   # apply code changes / refresh
sudo systemctl stop sector-dashboard
sudo systemctl status sector-dashboard
journalctl -u sector-dashboard -f         # live logs (Ctrl+C to exit)
journalctl -u sector-dashboard --since "1 hour ago"
```

## Updating the dashboard later

```bash
cd ~/sector-rotation-dashboard
git pull
source .venv/bin/activate
pip install -r requirements.txt           # if dependencies changed
sudo systemctl restart sector-dashboard
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

## Resource notes

On a Pi 4 with 4 GB RAM and the full 67-ticker universe:
- First data fetch: ~60 seconds (cold cache from Yahoo)
- Memory footprint: ~600 MB resident
- CPU: spikes during indicator computation, idle while idle (Streamlit caches everything)
- Disk: <100 MB total (the venv is ~250 MB)

If you see memory pressure, edit `src/universe.py` to trim the universe (e.g. drop the country ETFs or factor ETFs).

## Next: expose it publicly

Right now the dashboard is only reachable from your home LAN. To expose it on `dashboard.yourdomain.com` securely without port-forwarding, see [`DEPLOY_CLOUDFLARE_TUNNEL.md`](DEPLOY_CLOUDFLARE_TUNNEL.md).
