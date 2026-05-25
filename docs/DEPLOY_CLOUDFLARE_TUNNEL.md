# Exposing the dashboard via Cloudflare Tunnel

## Public methodology landing page

B-152 keeps the public root separate from the dashboard:

- Public root: `https://ahaddashboards.uk` and `https://www.ahaddashboards.uk` -> `http://localhost:8500`
- Protected dashboard: `https://sentimentdashboard.ahaddashboards.uk` -> `http://localhost:8501`

Serve the static `public/` directory with `systemd/methodology-landing.service` or the non-sudo `systemd/user/methodology-landing.service`, then route the root hostnames to that static service. Keep Cloudflare Access on the dashboard hostname so the live Streamlit app stays private while the methodology overview is public.

This gives you a public URL like `https://dashboard.yourdomain.com` that:
- Routes traffic securely through Cloudflare (no inbound port-forward on your router)
- Auto-issues a valid TLS certificate
- Survives your home IP changing
- Optionally puts the dashboard behind Cloudflare Access (Google/email login) so it isn't public-public

## Prerequisites

- A domain managed by Cloudflare (free plan is fine). If your domain is registered elsewhere, change its nameservers to Cloudflare first — Cloudflare's onboarding walks you through it.
- The public methodology landing page running on your Pi at `http://127.0.0.1:8500` when serving from the Pi.
- The dashboard running on your Pi at `http://127.0.0.1:8501` (per [`DEPLOY_RASPBERRY_PI.md`](DEPLOY_RASPBERRY_PI.md)).
- A free Cloudflare account.

## 1. Install cloudflared on the Pi

```bash
# 64-bit Pi OS (Bookworm) — use arm64
curl -L --output cloudflared.deb \
  https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64.deb
sudo dpkg -i cloudflared.deb
cloudflared --version
```

(For 32-bit Pi OS use `cloudflared-linux-arm.deb` instead.)

## 2. Authenticate

```bash
cloudflared tunnel login
```

This prints a URL. Open it on any browser, log in to Cloudflare, and **select the domain** you'll use. cloudflared saves the credential to `~/.cloudflared/cert.pem`.

## 3. Create the tunnel

```bash
cloudflared tunnel create sector-dashboard
```

Note the **tunnel UUID** it prints — you'll need it in the next step. The credential file is saved at `~/.cloudflared/<UUID>.json`.

## 4. Point a DNS record at the tunnel

Pick the root and dashboard hostnames:

```bash
cloudflared tunnel route dns sector-dashboard ahaddashboards.uk
cloudflared tunnel route dns sector-dashboard www.ahaddashboards.uk
cloudflared tunnel route dns sector-dashboard sentimentdashboard.ahaddashboards.uk
```

This adds a `CNAME` to your Cloudflare DNS pointing at the tunnel. Repeat for additional subdomains if needed.

## 5. Write the config file

```bash
mkdir -p ~/.cloudflared
nano ~/.cloudflared/config.yml
```

Paste (replace the UUID, paths, and hostname):

```yaml
tunnel: <YOUR-TUNNEL-UUID>
credentials-file: /home/meiri/.cloudflared/<YOUR-TUNNEL-UUID>.json

ingress:
  - hostname: ahaddashboards.uk
    service: http://localhost:8500
  - hostname: www.ahaddashboards.uk
    service: http://localhost:8500
  - hostname: sentimentdashboard.ahaddashboards.uk
    service: http://localhost:8501
    originRequest:
      # Streamlit uses WebSocket for live updates
      noTLSVerify: true
      connectTimeout: 30s
  - service: http_status:404
```

A copy of this template is in [`../config/cloudflared-config.yml.example`](../config/cloudflared-config.yml.example).

## 6. Test the tunnel manually

```bash
cloudflared tunnel run sector-dashboard
```

Open `https://ahaddashboards.uk` in your browser to see the public methodology page. Open `https://sentimentdashboard.ahaddashboards.uk` to verify the dashboard route. `Ctrl+C` to stop.

## 7. Install as a service (auto-start on boot)

```bash
sudo cloudflared service install
sudo systemctl enable cloudflared
sudo systemctl start  cloudflared
sudo systemctl status cloudflared
```

The tunnel now starts on boot, restarts on crash, and stays up through your home's WAN-IP changes.

### Useful commands

```bash
sudo systemctl restart cloudflared           # apply config changes
journalctl -u cloudflared -f                 # live logs
cloudflared tunnel info sector-dashboard     # tunnel health
cloudflared tunnel list
```

## Lock the dashboard behind login — Cloudflare Access

Do not put the public root behind Access unless the methodology page should be private. The dashboard route should stay behind login:

1. In Cloudflare dashboard, go to **Zero Trust → Access → Applications → Add an application → Self-hosted.**
2. Application name: `Sector Dashboard.` Subdomain: `dashboard`. Domain: `yourdomain.com`.
3. Session duration: 24 hours (or whatever).
4. Click "Next" → create a **policy**:
   - Action: **Allow**
   - Include: **Emails** → enter `your-email@gmail.com` (and any teammates).
5. Save.

Now visitors get a Cloudflare-hosted login screen and have to receive a one-time-code on email before they can reach the dashboard. Free plan supports up to 50 users.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Browser shows "Error 1033" | Tunnel isn't running — `sudo systemctl status cloudflared` |
| Browser shows "Error 502" | Streamlit isn't running — `sudo systemctl status sector-dashboard` |
| "WebSocket connection failed" warning in browser console, charts don't update | Cloudflare WebSocket might be off. In the dashboard, **Network → WebSockets** must be enabled (it is by default on free plan). |
| Login loop with Cloudflare Access | Your email isn't in the policy's allow list, or you're using a different account than the one you whitelisted. |
| `cloudflared` complains it can't find credentials | The credentials file path in `config.yml` is wrong. Run `ls ~/.cloudflared/` and update. |
| Dashboard works on LAN but not via tunnel | Make sure Streamlit was started with `--server.address 127.0.0.1` (or `0.0.0.0`) and `--server.headless true`. |

## Lower-cost alternative: Cloudflare Quick Tunnel (temporary, no domain needed)

For testing only — gives you a random `*.trycloudflare.com` URL:

```bash
cloudflared tunnel --url http://localhost:8501
```

URL changes every time you restart, no auth. Useful for sharing with one person briefly.
