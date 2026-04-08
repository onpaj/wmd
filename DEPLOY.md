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

1. **System packages** — installs `nodejs npm chromium labwc wlr-randr git curl python3-venv` via apt; removes `gnome-keyring` (causes a "change password for new keyring" dialog on first boot)
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

Use `update.sh` after every commit. The first argument selects the update level:

| Level | What it does |
|-------|-------------|
| `frontend` | git pull → rebuild JS → clear Chromium cache & restart |
| `backend` | git pull → restart `wmd-server` |
| `app` *(default)* | git pull → rebuild JS + restart `wmd-server` + clear Chromium cache |
| `system` | `app` + `npm ci`, `pip install`, apt packages, labwc config |

```bash
# Most common — code change, no dependency changes
git push && ./update.sh

# Frontend-only change (e.g. CSS, layout tweak)
git push && ./update.sh frontend

# Backend-only change (e.g. Python logic, no new deps)
git push && ./update.sh backend

# Added new npm/pip packages or changed system config
git push && ./update.sh system

# Custom host (second arg)
./update.sh app rem@192.168.10.66
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

**"Change password for new keyring" dialog on boot**
- `gnome-keyring` is installed by default on RPi OS and triggers this dialog on first login
- deploy.sh removes it automatically; to fix manually: `sudo apt-get remove gnome-keyring`
- **Side effect:** removing `gnome-keyring` also removes `rpd-wayland-core`, which provides the `rpd-labwc` session and `pi-greeter-labwc` greeter — causing LightDM to crash on next boot
- deploy.sh patches `/etc/lightdm/lightdm.conf` to use `labwc` + `lightdm-gtk-greeter` instead; to fix manually: `sudo sed -i "s/pi-greeter-labwc/lightdm-gtk-greeter/; s/rpd-labwc/labwc/" /etc/lightdm/lightdm.conf`
- **Do not run `sudo apt autoremove` after removing gnome-keyring** — it will also pull out `labwc` and its Wayland libs. If that happens: `sudo apt-get install labwc wlr-randr`

**"English" overlay / on-screen keyboard visible**
- `squeekboard` (RPi OS on-screen keyboard) autostarts and shows a language indicator
- deploy.sh masks it via `~/.config/autostart/squeekboard.desktop` with `Hidden=true`
- To fix manually: `mkdir -p ~/.config/autostart && echo -e '[Desktop Entry]\nHidden=true' > ~/.config/autostart/squeekboard.desktop`

**Mouse cursor visible on screen**
- `unclutter-xfixes` does not work on Wayland; cursor is hidden two ways instead:
  1. CSS `cursor: none` on `html, body` in `static/css/base.css` — hides it inside the dashboard
  2. labwc `<core><cursor><hideTimeout>1000</hideTimeout></cursor></core>` in `rc.xml` — hides it 1s after last movement (covers boot period before Chromium starts)

**Photos not loading** — verify `icloud.shareToken` in `config.json`

**Calendar events missing** — confirm ICS URL is reachable from the Pi: `curl "<ics-url>"`
