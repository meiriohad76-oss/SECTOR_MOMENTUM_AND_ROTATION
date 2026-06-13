# Public Methodology Landing Page

B-152 adds a static public landing page under `public/`. It is separate from the Streamlit dashboard and contains no live signals, account data, run journal content, state-machine data, or API-key references.

## Files

- `public/index.html` is the public root page.
- `public/methodology.html` is the public formula reference linked from the root page.
- `public/assets/methodology.css` is the page stylesheet.
- `public/assets/methodology-preview.png` is a static visual preview.
- `public/robots.txt`, `public/sitemap.xml`, and `public/_headers` are static-hosting support files.
- `systemd/methodology-landing.service` serves `public/` on `127.0.0.1:8500` when hosting from the Pi with root systemd.
- `systemd/user/methodology-landing.service` serves the same directory without sudo under the current Pi user.

## Route Split

Use separate hostnames or Cloudflare applications:

- Public root: `https://ahaddashboards.uk` and `https://www.ahaddashboards.uk` -> `http://localhost:8500`
- Protected dashboard: `https://sentimentdashboard.ahaddashboards.uk` -> `http://localhost:8501`

Keep Cloudflare Access enabled on the dashboard host. Do not put Cloudflare Access on the public methodology root unless you want the methodology page private too.

## Pi Service

```bash
cd /home/ahad/SECTOR_MOMENTUM_AND_ROTATION
sudo cp systemd/methodology-landing.service /etc/systemd/system/
sudo sed -i 's/User=meiri/User=ahad/' /etc/systemd/system/methodology-landing.service
sudo sed -i 's/Group=meiri/Group=ahad/' /etc/systemd/system/methodology-landing.service
sudo sed -i 's#/home/meiri/sector-rotation-dashboard#/home/ahad/SECTOR_MOMENTUM_AND_ROTATION#' /etc/systemd/system/methodology-landing.service
sudo systemctl daemon-reload
sudo systemctl enable --now methodology-landing
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8500/
```

Expected: `200`.

For AHADPI5-style non-sudo user services:

```bash
cd /home/ahad/SECTOR_MOMENTUM_AND_ROTATION
mkdir -p ~/.config/systemd/user
cp systemd/user/methodology-landing.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now methodology-landing.service
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8500/feeds/transitions.rss
```

Expected: `200` with RSS XML content after B-122 feed artifacts have been generated.

## Cloudflare Validation

After updating DNS/Cloudflare Tunnel or Cloudflare Pages, verify both surfaces:

```bash
curl -I https://ahaddashboards.uk/
curl -I https://www.ahaddashboards.uk/
curl -I https://sentimentdashboard.ahaddashboards.uk/?ticker=XLK
```

Expected:

- The public root returns `200`.
- The dashboard host remains protected or otherwise restricted according to the Cloudflare Access policy.
