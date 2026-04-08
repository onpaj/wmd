# RPi OS Wayland Setup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Update `deploy.sh` to deploy DAK dashboard on Raspberry Pi OS (Debian Trixie / Wayland / labwc) with 90° clockwise screen rotation, then deploy to the Pi at `rem@192.168.10.66`.

**Architecture:** Browser (Chromium) is launched from labwc autostart with `--ozone-platform=wayland` and a restart loop. Screen rotation is applied via `wlr-randr` at session start. The backend (`dak-server`) stays as a systemd system service. `deploy.sh` is piped over SSH so changes take effect without pushing the script itself to the Pi.

**Tech Stack:** Bash (deploy.sh), Python 3.13 (XML patching), wlr-randr (Wayland output rotation), labwc (compositor autostart), systemd (backend service), Chromium (kiosk browser)

---

## File Map

| File | Action | What changes |
|------|--------|--------------|
| `deploy.sh` | Modify | Package list, chromium detection, LightDM block, openbox→labwc autostart, rc.xml idle config, remove dak-browser.service |
| `DEPLOY.md` | Modify | Rewrite for RPi OS Wayland, update all step references |

---

### Task 1: Simplify package install and chromium detection in deploy.sh

**Files:**
- Modify: `deploy.sh` (lines ~43-79)

The current script tries `chromium-browser` then falls back to `chromium`, and installs X11 packages not needed on RPi OS Wayland. Remove the `detect_chromium_bin` function, simplify the package list, and add a direct existence check.

- [ ] **Step 1: Remove `detect_chromium_bin` function**

In `deploy.sh`, delete lines 43–50 (the full `detect_chromium_bin` function):

```bash
detect_chromium_bin() {
  if command -v chromium-browser &>/dev/null; then
    echo "chromium-browser"
  elif command -v chromium &>/dev/null; then
    echo "chromium"
  else
    echo ""
  fi
}
```

- [ ] **Step 2: Replace the package install block**

Replace the entire `# ── 1. System packages` block (lines ~60–75) with:

```bash
# ── 1. System packages ────────────────────────────────────────────────────────
info "Installing system packages..."
sudo apt-get update -qq
sudo apt-get install -y \
  python3 python3-pip python3-venv \
  nodejs npm \
  chromium \
  git curl
```

- [ ] **Step 3: Replace chromium verification (lines ~77–79)**

Replace:
```bash
CHROMIUM_BIN="$(detect_chromium_bin)"
[[ -z "$CHROMIUM_BIN" ]] && error "Could not find chromium or chromium-browser after install. Install manually and re-run."
info "Chromium binary: $(command -v "$CHROMIUM_BIN")"
```

With:
```bash
command -v chromium &>/dev/null || error "chromium not found after install. Run: sudo apt-get install chromium"
info "Chromium binary: $(command -v chromium)"
```

- [ ] **Step 4: Verify no remaining references to `CHROMIUM_BIN` or `detect_chromium_bin`**

Run:
```bash
grep -n "CHROMIUM_BIN\|detect_chromium_bin\|chromium-browser" deploy.sh
```

Expected: no output.

---

### Task 2: Replace LightDM config block in deploy.sh

**Files:**
- Modify: `deploy.sh` (step 6, lines ~129–156)

LightDM is already configured on the target Pi (`autologin-user=rem`, `autologin-session=rpd-labwc`). Skip the config block entirely; only keep the `graphical.target` line.

- [ ] **Step 1: Replace the entire `# ── 6. LightDM auto-login` block**

Delete everything from `# ── 6. LightDM auto-login` through `sudo systemctl set-default graphical.target` and replace with:

```bash
# ── 6. LightDM auto-login ────────────────────────────────────────────────────
info "Skipping LightDM configuration (already configured on Raspberry Pi OS)..."
sudo systemctl set-default graphical.target
```

---

### Task 3: Replace openbox autostart with labwc autostart + rc.xml

**Files:**
- Modify: `deploy.sh` (step 7, lines ~158–173)

Replace the openbox/xset/unclutter block with: (a) labwc autostart that rotates the display and launches Chromium in a restart loop, (b) labwc rc.xml patched to disable screen blanking.

- [ ] **Step 1: Replace the entire `# ── 7. Kiosk hardening` block**

Delete from `# ── 7. Kiosk hardening` to the closing `fi` and replace with:

```bash
# ── 7. labwc autostart: screen rotation + kiosk browser ──────────────────────
info "Configuring labwc autostart (rotation + kiosk)..."
LABWC_DIR="/home/${DAK_USER}/.config/labwc"
mkdir -p "$LABWC_DIR"

cat > "${LABWC_DIR}/autostart" << 'EOF'
# Screen rotation: detect first connected output, rotate 90° clockwise
wlr-randr --output "$(wlr-randr | head -1 | awk '{print $1}')" --transform 90

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
EOF
info "labwc autostart written."

# ── 7b. Disable screen blanking via labwc rc.xml ─────────────────────────────
info "Disabling screen blanking (labwc rc.xml)..."
RC_XML="${LABWC_DIR}/rc.xml"
python3 << PYEOF
import os, xml.etree.ElementTree as ET

rc_xml = "${RC_XML}"
if os.path.exists(rc_xml):
    tree = ET.parse(rc_xml)
    root = tree.getroot()
    idle = root.find('idle')
    if idle is None:
        idle = ET.SubElement(root, 'idle')
    monitor = idle.find('monitor')
    if monitor is None:
        monitor = ET.SubElement(idle, 'monitor')
    monitor.set('timeout', '0')
    tree.write(rc_xml, xml_declaration=True, encoding='UTF-8')
else:
    with open(rc_xml, 'w') as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n<labwc_config>\n  <idle>\n    <monitor timeout="0"/>\n  </idle>\n</labwc_config>\n')
print("idle monitor timeout set to 0")
PYEOF
info "Screen blanking disabled."
```

---

### Task 4: Remove dak-browser.service from deploy.sh

**Files:**
- Modify: `deploy.sh` (step 8, lines ~175–219)

The browser is now managed by labwc autostart, not systemd. Remove the `dak-browser.service` tee block and update the enable/start commands and done message.

- [ ] **Step 1: Remove the dak-browser.service tee block**

Delete the `# Generate dak-browser.service` block (the `sudo tee /etc/systemd/system/dak-browser.service` heredoc and surrounding lines).

- [ ] **Step 2: Update the systemctl enable line**

Replace:
```bash
sudo systemctl enable dak-server dak-browser
```
With:
```bash
sudo systemctl enable dak-server
```

- [ ] **Step 3: Update the done message**

In the done/summary block at the bottom, remove any reference to `dak-browser` and update the "Next steps" section:

```bash
echo -e "${GREEN}╔══════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║          DAK Dashboard deployment complete           ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════╝${NC}"
echo ""
echo "  Install dir : ${INSTALL_DIR}"
echo "  Config file : ${INSTALL_DIR}/config.json"
echo "  Backend     : http://localhost:3000"
echo ""
echo "  Next steps:"
echo "    1. Edit config:  nano ${INSTALL_DIR}/config.json"
echo "    2. Restart:      sudo systemctl restart dak-server"
echo "    3. View logs:    journalctl -u dak-server -f"
echo "    4. Reboot to start Chromium kiosk via labwc autostart."
echo ""
echo "  Quick verify:"
echo "    systemctl status dak-server"
echo "    curl http://localhost:3000/api/data | python3 -m json.tool"
```

---

### Task 5: Syntax-check, commit, and push deploy.sh

**Files:**
- `deploy.sh`

- [ ] **Step 1: Run bash syntax check**

```bash
bash -n deploy.sh
```

Expected: no output (exit code 0).

- [ ] **Step 2: Verify no stale references remain**

```bash
grep -n "openbox\|unclutter\|xset\|CHROMIUM_BIN\|detect_chromium_bin\|chromium-browser\|dak-browser\|autologin-user\|lightdm.conf" deploy.sh
```

Expected: no output.

- [ ] **Step 3: Commit and push**

```bash
git add deploy.sh
git commit -m "feat: update deploy.sh for Raspberry Pi OS Wayland/labwc

- Replace X11/openbox kiosk with labwc autostart
- Screen rotation via wlr-randr (90° clockwise, dynamic output detection)
- Chromium kiosk with --ozone-platform=wayland and restart loop
- Disable screen blanking via labwc rc.xml idle config
- Remove dak-browser.service (browser managed by labwc autostart)
- Simplify package list: drop xorg/lightdm/openbox/unclutter
- Skip LightDM config block (already configured on RPi OS)

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
git push origin master
```

---

### Task 6: Update DEPLOY.md for Raspberry Pi OS Wayland

**Files:**
- Modify: `DEPLOY.md`

Rewrite to reflect the RPi OS Wayland setup. Keep the structure but replace Ubuntu-centric instructions.

- [ ] **Step 1: Replace DEPLOY.md content**

Overwrite `DEPLOY.md` with:

```markdown
# DAK Dashboard — Deployment Guide

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
8. **dak-server** — installs and enables systemd service (backend on port 3000)

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
ssh rem@192.168.10.66 'systemctl status dak-server'
ssh rem@192.168.10.66 'curl -s http://localhost:3000/api/data | python3 -m json.tool | head -20'

# Follow logs
ssh rem@192.168.10.66 'journalctl -u dak-server -f'
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
ssh rem@192.168.10.66 'sudo systemctl restart dak-server'
```

---

## Troubleshooting

**Backend not responding**
- `ssh rem@192.168.10.66 'systemctl status dak-server'`
- `ssh rem@192.168.10.66 'journalctl -u dak-server -b'`

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
```

- [ ] **Step 2: Commit and push**

```bash
git add DEPLOY.md
git commit -m "docs: rewrite DEPLOY.md for Raspberry Pi OS Wayland/labwc

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
git push origin master
```

---

### Task 7: Deploy to Pi and verify

- [ ] **Step 1: Run deploy**

```bash
./deploy-to-pi.sh rem@192.168.10.66 https://github.com/onpaj/wmd.git config.json
```

Expected: script runs to completion, ends with the green summary box. Watch for any `[ERROR]` lines.

- [ ] **Step 2: Verify dak-server is up**

```bash
ssh -i ~/.ssh/id_ed25519_rpi rem@192.168.10.66 'curl -s http://localhost:3000/api/data | python3 -m json.tool | head -5'
```

Expected: JSON output with top-level keys (photos, calendar, weather, etc.).

- [ ] **Step 3: Verify labwc autostart was written**

```bash
ssh -i ~/.ssh/id_ed25519_rpi rem@192.168.10.66 'cat ~/.config/labwc/autostart'
```

Expected: file contains `wlr-randr` rotation line and chromium kiosk loop.

- [ ] **Step 4: Verify rc.xml has idle timeout 0**

```bash
ssh -i ~/.ssh/id_ed25519_rpi rem@192.168.10.66 'cat ~/.config/labwc/rc.xml'
```

Expected: contains `<monitor timeout="0"/>` inside `<idle>`.

- [ ] **Step 5: Reboot and confirm kiosk starts**

```bash
ssh -i ~/.ssh/id_ed25519_rpi rem@192.168.10.66 'sudo reboot'
```

After ~30 seconds, the display should show the DAK dashboard in portrait mode (90° CW rotation). Verify remotely that the backend is still running:

```bash
sleep 35 && ssh -i ~/.ssh/id_ed25519_rpi rem@192.168.10.66 'systemctl status dak-server --no-pager'
```

Expected: `active (running)`.
