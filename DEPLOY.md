# WMD Dashboard — Deployment Guide

Target platform: Raspberry Pi running Raspberry Pi OS (Debian Trixie, Wayland/labwc).

---

## Prerequisites

- Raspberry Pi OS (Debian Trixie or later) installed
- LightDM configured for auto-login (default on RPi OS — user `rem` or your username)
- HDMI display connected
- SSH access

---

## One-Command Deploy

From your local machine (where this repo lives):

```bash
./deploy-to-pi.sh rem@192.168.10.66 https://github.com/onpaj/wmd.git config.json
```

Replace `rem@192.168.10.66` with your Pi's user and IP. Omit `config.json` to keep the existing config on the Pi.

This pipes `deploy.sh` over SSH and runs it as your Pi user. The script is idempotent — safe to re-run.

---

## What deploy.sh Does

1. **System packages** — installs `nodejs npm chromium git curl python3-venv` via apt
2. **Code** — clones `https://github.com/onpaj/wmd.git` (or pulls if already present)
3. **Config** — writes `config.json` from the provided file (or keeps existing)
4. **Python env** — creates `.venv` and installs `requirements.txt`
5. **Frontend** — runs `npm ci && npm run build`
6. **labwc autostart** — writes `~/.config/labwc/autostart`:
   - Rotates display 90° clockwise via `wlr-randr` (detects output name dynamically)
   - Launches Chromium in Wayland kiosk mode, auto-restarts on crash
7. **Screen blanking** — disables idle monitor timeout in `~/.config/labwc/rc.xml`
8. **wmd-server** — installs and enables systemd service (backend on port 3000)

---

## Configuration

```bash
cp config.example.json config.json
nano config.json
```

Minimum required fields:

| Field | Description |
|-------|-------------|
| `icloud.shareToken` | Token from iCloud shared album URL (after `?token=`) |
| `calendars[].url` | ICS feed URL |
| `weather.latitude` / `longitude` | Location coordinates |
| `homeAssistant.url` / `token` | HA instance URL and long-lived access token |

See `CLAUDE.md` for the full config schema.

---

## Verify

```bash
# Backend running?
ssh rem@192.168.10.66 'systemctl status wmd-server'
ssh rem@192.168.10.66 'curl -s http://localhost:3000/api/data | python3 -m json.tool | head -20'

# Follow logs
ssh rem@192.168.10.66 'journalctl -u wmd-server -f'
```

Reboot the Pi to start the full kiosk session (labwc autostart launches Chromium):

```bash
ssh rem@192.168.10.66 'sudo reboot'
```

---

## Updating

```bash
# Pull latest code + rebuild (keeps existing config.json)
./deploy-to-pi.sh rem@192.168.10.66 https://github.com/onpaj/wmd.git

# Then restart backend
ssh rem@192.168.10.66 'sudo systemctl restart wmd-server'
```

---

## Troubleshooting

**Backend not responding**
- `ssh rem@192.168.10.66 'systemctl status wmd-server'`
- `ssh rem@192.168.10.66 'journalctl -u wmd-server -b'`

**Chromium not starting / wrong orientation**
- Check labwc autostart: `ssh rem@192.168.10.66 'cat ~/.config/labwc/autostart'`
- Run wlr-randr manually from SSH (requires `WAYLAND_DISPLAY`): reboot and check via the display

**Screen going blank**
- Check rc.xml: `ssh rem@192.168.10.66 'cat ~/.config/labwc/rc.xml'`
- Confirm `<monitor timeout="0"/>` is present under `<idle>`

**Node.js / npm not found after install**
- `ssh rem@192.168.10.66 'apt-cache policy nodejs'` — should show v20
- Re-run deploy.sh

**Photos not loading** — verify `icloud.shareToken` in `config.json`

**Calendar events missing** — confirm ICS URL is reachable from the Pi: `curl "<ics-url>"`
