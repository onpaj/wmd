# DAK Raspberry Pi OS / Wayland Setup — Design Spec

**Date:** 2026-04-08
**Status:** Approved

---

## Overview

Deploy DAK dashboard to a wall-mounted display running Raspberry Pi OS (Debian Trixie) with Wayland/labwc compositor. The screen is physically rotated 90° clockwise and must be configured in software. Chromium runs in kiosk mode under Wayland via labwc autostart.

---

## Target Environment

| Property | Value |
|----------|-------|
| OS | Raspberry Pi OS (Debian Trixie / 13) |
| Kernel | 6.12 aarch64 (RPi firmware) |
| Display server | Wayland (labwc compositor) |
| Session manager | LightDM (`rpd-labwc` session) |
| Auto-login user | `rem` (already configured) |
| Chromium binary | `/usr/bin/chromium` |
| Node.js | v20 (available via apt, not yet installed) |
| Python | 3.13.5 (system) |
| Git repo | `https://github.com/onpaj/wmd.git` (branch: `master`) |
| SSH | `ssh -i ~/.ssh/id_ed25519_rpi rem@192.168.10.66` |

---

## Architecture

```
Boot
 └─ LightDM (autologin=rem, session=rpd-labwc — already configured)
     └─ labwc (Wayland compositor)
         └─ ~/.config/labwc/autostart
             ├─ wlr-randr: detect first output → --transform 90 (clockwise)
             └─ loop: chromium --kiosk --ozone-platform=wayland :3000
                       (auto-restarts on crash)

systemd (system service)
 └─ dak-server: uvicorn on :3000, Restart=always, starts at boot
```

---

## Components

### 1. deploy.sh (updated)

Single-file idempotent script piped over SSH. Changes from current version:

- **Chromium binary**: detect `chromium` (not `chromium-browser`)
- **Node.js**: install via `apt-get install nodejs npm` (v20 in Debian Trixie repos — no external NodeSource repo needed)
- **LightDM block**: skipped entirely (already configured on target)
- **openbox autostart**: removed — replaced by labwc autostart
- **dak-browser.service**: not installed — browser managed by labwc autostart instead
- **labwc autostart**: written to `~/.config/labwc/autostart`
- **labwc rc.xml**: idle monitor timeout set to 0 (no screen blanking)

### 2. labwc autostart (`~/.config/labwc/autostart`)

```bash
# Screen rotation: detect first connected output, rotate 90° clockwise
wlr-randr --output "$(wlr-randr | head -1 | awk '{print $1}')" --transform 90 &

# Wait for dak-server backend to be ready
sleep 5

# Chromium kiosk — auto-restarts on crash
while true; do
  /usr/bin/chromium \
    --kiosk --noerrdialogs --disable-infobars --no-first-run \
    --ozone-platform=wayland \
    --check-for-update-interval=31536000 \
    --disable-translate --disable-features=Translate \
    http://localhost:3000
  sleep 2
done &
```

**Why dynamic output detection:** The monitor will be replaced; `wlr-randr | head -1 | awk '{print $1}'` always picks the first connected output regardless of its name.

### 3. Screen blanking prevention

`~/.config/labwc/rc.xml` — set idle monitor timeout to 0:
```xml
<idle>
  <monitor timeout="0"/>
</idle>
```

If `rc.xml` doesn't exist, create it with minimal valid content. If it does exist, patch only the `<idle>` section.

### 4. dak-server.service

Generated dynamically from deploy.sh with correct user and paths. No static file needed in the repo for this (deploy.sh writes it). Identical to current logic — `Restart=always`, `RestartSec=5`, `WantedBy=multi-user.target`.

### 5. deploy-to-pi.sh

No changes required. Usage:

```bash
./deploy-to-pi.sh rem@192.168.10.66 https://github.com/onpaj/wmd.git config.json
```

---

## Deployment Flow

1. Local: `./deploy-to-pi.sh rem@192.168.10.66 https://github.com/onpaj/wmd.git config.json`
2. deploy.sh runs on Pi as `rem`:
   - `apt-get install nodejs npm` (+ other deps if missing)
   - `git clone --branch master https://github.com/onpaj/wmd.git ~/dak`
     (or `git fetch && reset --hard` if already cloned)
   - Write `config.json` from base64 arg
   - `python3 -m venv .venv && pip install -r requirements.txt`
   - `npm ci && npm run build`
   - Write `~/.config/labwc/autostart` (rotation + kiosk loop)
   - Patch `~/.config/labwc/rc.xml` (idle timeout = 0)
   - Install + enable `dak-server.service`
   - Start `dak-server`
3. Reboot (or `sudo systemctl restart lightdm`) to launch the Wayland session with autostart

---

## Update Flow

```bash
./deploy-to-pi.sh rem@192.168.10.66 https://github.com/onpaj/wmd.git
# (omit config.json to keep existing config)
```

Script is idempotent — safe to re-run.

---

## Out of Scope

- Wayland screen recording / mirroring
- Multi-monitor support
- Touch input configuration
- Any changes to DAK application logic
