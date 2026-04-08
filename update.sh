#!/usr/bin/env bash
# WMD Dashboard — Remote update script
# Usage: ./update.sh [level] [user@host]
#   level: frontend | backend | app | system  (default: app)
#   host:  default rem@192.168.10.66
#
# Levels:
#   frontend  — git pull, rebuild JS, clear Chromium cache & restart
#   backend   — git pull, restart wmd-server
#   app       — git pull, rebuild JS + restart wmd-server + clear Chromium cache
#   system    — app + npm ci, pip install, apt packages, labwc config

set -euo pipefail

LEVEL="${1:-app}"
HOST="${2:-rem@192.168.10.66}"
SSH="ssh -i ~/.ssh/id_ed25519_rpi"

case "$LEVEL" in
  frontend|backend|app|system) ;;
  *)
    echo "Unknown level: $LEVEL"
    echo "Usage: ./update.sh [frontend|backend|app|system] [user@host]"
    exit 1
    ;;
esac

echo "Updating WMD on ${HOST} (level: ${LEVEL})..."

$SSH "$HOST" LEVEL="$LEVEL" 'bash -s' << 'REMOTE'
set -euo pipefail
cd ~/wmd

echo "→ Pulling latest code..."
git fetch origin
git reset --hard origin/master

# ── SYSTEM: install all dependencies ────────────────────────────────────────
if [ "$LEVEL" = "system" ]; then
  echo "→ Installing system packages..."
  sudo apt-get install -y -qq fonts-noto fonts-noto-color-emoji 2>/dev/null || true

  echo "→ Installing npm dependencies..."
  npm ci --silent

  echo "→ Updating Python dependencies..."
  .venv/bin/pip install --quiet -r requirements.txt

  echo "→ Applying labwc config (autostart + rc.xml)..."
  LABWC_DIR="$HOME/.config/labwc"
  mkdir -p "$LABWC_DIR"

  cat > "${LABWC_DIR}/autostart" << 'AUTOSTART'
# Screen rotation: detect first connected output, rotate 90° clockwise
wlr-randr --output "$(wlr-randr | head -1 | awk '{print $1}')" --transform 90

# Wait for wmd-server backend to be ready
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
AUTOSTART

  python3 << 'PYEOF'
import os, xml.etree.ElementTree as ET
rc_xml = os.path.expanduser("~/.config/labwc/rc.xml")
FRESH_XML = '<?xml version="1.0" encoding="UTF-8"?>\n<labwc_config>\n  <core>\n    <cursor>\n      <hideTimeout>1000</hideTimeout>\n    </cursor>\n  </core>\n  <idle>\n    <monitor timeout="0"/>\n  </idle>\n</labwc_config>\n'
if os.path.exists(rc_xml):
    try:
        tree = ET.parse(rc_xml)
        root = tree.getroot()
        idle = root.find('idle')
        if idle is None:
            idle = ET.SubElement(root, 'idle')
        monitor = idle.find('monitor')
        if monitor is None:
            monitor = ET.SubElement(idle, 'monitor')
        monitor.set('timeout', '0')
        core = root.find('core')
        if core is None:
            core = ET.SubElement(root, 'core')
        cursor = core.find('cursor')
        if cursor is None:
            cursor = ET.SubElement(core, 'cursor')
        hide_timeout = cursor.find('hideTimeout')
        if hide_timeout is None:
            hide_timeout = ET.SubElement(cursor, 'hideTimeout')
        hide_timeout.text = '1000'
        tree.write(rc_xml, xml_declaration=True, encoding='UTF-8')
    except ET.ParseError:
        with open(rc_xml, 'w') as f:
            f.write(FRESH_XML)
else:
    with open(rc_xml, 'w') as f:
        f.write(FRESH_XML)
print("labwc rc.xml updated")
PYEOF
fi

# ── FRONTEND: rebuild JS bundle ──────────────────────────────────────────────
if [ "$LEVEL" = "frontend" ] || [ "$LEVEL" = "app" ] || [ "$LEVEL" = "system" ]; then
  echo "→ Rebuilding frontend..."
  npm run build
fi

# ── BACKEND: restart wmd-server ──────────────────────────────────────────────
if [ "$LEVEL" = "backend" ] || [ "$LEVEL" = "app" ] || [ "$LEVEL" = "system" ]; then
  echo "→ Restarting wmd-server..."
  sudo systemctl restart wmd-server

  echo "→ Verifying (waiting up to 60s for startup)..."
  for i in $(seq 1 12); do
    if curl -sf --max-time 5 http://localhost:3000/api/data > /dev/null 2>&1; then
      echo "✓ wmd-server is responding"
      break
    fi
    if [ "$i" -eq 12 ]; then
      echo "✗ wmd-server not responding after 60s — check: journalctl -u wmd-server -f"
      exit 1
    fi
    echo "  waiting... (${i}/12)"
    sleep 5
  done
fi

# ── FRONTEND + APP + SYSTEM: reload Chromium ─────────────────────────────────
if [ "$LEVEL" = "frontend" ] || [ "$LEVEL" = "app" ] || [ "$LEVEL" = "system" ]; then
  echo "→ Reloading Chromium (clearing cache)..."
  pkill -f chromium || true
  sleep 1
  rm -rf ~/.cache/chromium/Default/Cache \
         ~/.cache/chromium/Default/"Code Cache" \
         ~/.cache/chromium/Default/GPUCache 2>/dev/null || true
  echo "✓ Chromium will restart automatically via labwc autostart"
fi

REMOTE

echo "Done (level: ${LEVEL})."
