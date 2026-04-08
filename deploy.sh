#!/usr/bin/env bash
# WMD Dashboard — One-shot deployment script
# Usage:
#   On the target machine:
#     bash deploy.sh [REPO_URL] [CONFIG_BASE64]
#
#   Via SSH from local machine (recommended):
#     ssh user@host 'bash -s' -- \
#       "https://github.com/you/wmd.git" \
#       "$(base64 < config.json)" \
#       < deploy.sh
#
#   Without a git repo (code already on machine):
#     bash deploy.sh "" "$(base64 < config.json)"
#
# Re-running the script is safe (idempotent).

set -euo pipefail

# ── Configuration ────────────────────────────────────────────────────────────
REPO_URL="${1:-}"          # Optional: git repo URL
CONFIG_B64="${2:-}"        # Optional: base64-encoded config.json content
INSTALL_DIR="/home/$(whoami)/wmd"
WMD_USER="$(whoami)"
BRANCH="main"

# ── Helpers ──────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()  { echo -e "${GREEN}[WMD]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*" >&2; exit 1; }

require_root() {
  if [[ $EUID -eq 0 ]]; then
    error "Do not run this script as root. Run as your normal user (sudo access required)."
  fi
}

# ── Pre-flight ────────────────────────────────────────────────────────────────
require_root

info "WMD Dashboard deployment — user: ${WMD_USER}, target: ${INSTALL_DIR}"
info "Date: $(date)"

# ── 1. System packages ────────────────────────────────────────────────────────
info "Installing system packages..."
sudo apt-get update -qq
sudo apt-get install -y \
  python3 python3-pip python3-venv \
  nodejs npm \
  chromium \
  git curl

command -v chromium &>/dev/null || error "chromium not found after install. Run: sudo apt-get install chromium"
info "Chromium binary: $(command -v chromium)"

# ── 2. Clone or update repository ────────────────────────────────────────────
if [[ -d "$INSTALL_DIR/.git" ]]; then
  info "Repository already exists — pulling latest changes..."
  git -C "$INSTALL_DIR" fetch origin
  git -C "$INSTALL_DIR" reset --hard "origin/${BRANCH}"
elif [[ -d "$INSTALL_DIR" && -f "$INSTALL_DIR/main.py" ]]; then
  info "Code already present (no .git) — skipping clone."
elif [[ -n "$REPO_URL" ]]; then
  info "Cloning repository from ${REPO_URL}..."
  git clone --branch "$BRANCH" "$REPO_URL" "$INSTALL_DIR"
else
  error "No code found at ${INSTALL_DIR} and no REPO_URL provided.\n       Pass the git URL as first argument:  bash deploy.sh https://github.com/you/wmd.git\n       Or copy the project to ${INSTALL_DIR} first, then re-run."
fi

cd "$INSTALL_DIR"

# ── 3. config.json ────────────────────────────────────────────────────────────
if [[ -n "$CONFIG_B64" ]]; then
  info "Writing config.json from provided base64 content..."
  echo "$CONFIG_B64" | base64 --decode > "$INSTALL_DIR/config.json"
  info "config.json written."
elif [[ ! -f "$INSTALL_DIR/config.json" ]]; then
  info "Creating config.json from example — edit it before starting services."
  cp "$INSTALL_DIR/config.example.json" "$INSTALL_DIR/config.json"
  warn "config.json created. Fill in your values:"
  warn "  - icloud.shareToken"
  warn "  - calendars[].url"
  warn "  - weather.latitude / longitude"
  warn "  - homeAssistant.url / token"
  warn "  Edit: nano ${INSTALL_DIR}/config.json"
else
  info "config.json already present — skipping."
fi

# ── 4. Python virtual environment ────────────────────────────────────────────
if [[ ! -d "$INSTALL_DIR/.venv" ]]; then
  info "Creating Python virtual environment..."
  python3 -m venv "$INSTALL_DIR/.venv"
fi
info "Installing Python dependencies..."
"$INSTALL_DIR/.venv/bin/pip" install --quiet --upgrade pip
"$INSTALL_DIR/.venv/bin/pip" install --quiet -r "$INSTALL_DIR/requirements.txt"

# ── 5. Frontend build ─────────────────────────────────────────────────────────
info "Installing Node.js dependencies and building frontend..."
npm --prefix "$INSTALL_DIR" ci --silent
npm --prefix "$INSTALL_DIR" run build

# ── 6. LightDM auto-login ────────────────────────────────────────────────────
info "Skipping LightDM configuration (already configured on Raspberry Pi OS)..."
sudo systemctl set-default graphical.target

# ── 7. labwc autostart: screen rotation + kiosk browser ──────────────────────
info "Configuring labwc autostart (rotation + kiosk)..."
LABWC_DIR="/home/${WMD_USER}/.config/labwc"
mkdir -p "$LABWC_DIR"

cat > "${LABWC_DIR}/autostart" << 'EOF'
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
EOF
info "labwc autostart written."

# ── 7b. Disable screen blanking via labwc rc.xml ─────────────────────────────
info "Disabling screen blanking (labwc rc.xml)..."
RC_XML="${LABWC_DIR}/rc.xml"
python3 << PYEOF
import os, xml.etree.ElementTree as ET

rc_xml = "${RC_XML}"
FRESH_XML = '<?xml version="1.0" encoding="UTF-8"?>\n<labwc_config>\n  <idle>\n    <monitor timeout="0"/>\n  </idle>\n</labwc_config>\n'
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
        tree.write(rc_xml, xml_declaration=True, encoding='UTF-8')
    except ET.ParseError:
        with open(rc_xml, 'w') as f:
            f.write(FRESH_XML)
else:
    with open(rc_xml, 'w') as f:
        f.write(FRESH_XML)
print("idle monitor timeout set to 0")
PYEOF
info "Screen blanking disabled."

# ── 8. Systemd service files ──────────────────────────────────────────────────
info "Installing systemd service files..."

# Generate wmd-server.service
sudo tee /etc/systemd/system/wmd-server.service > /dev/null << EOF
[Unit]
Description=WMD Dashboard Server
After=network.target
Wants=network.target

[Service]
User=${WMD_USER}
WorkingDirectory=${INSTALL_DIR}
ExecStart=${INSTALL_DIR}/.venv/bin/uvicorn main:app --host 0.0.0.0 --port 3000
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable wmd-server
info "Services enabled."

# ── 9. Start services ─────────────────────────────────────────────────────────
info "Starting wmd-server..."
sudo systemctl restart wmd-server

# Give server a moment to start before verifying
sleep 3
if curl -sf http://localhost:3000/api/data > /dev/null; then
  info "wmd-server is responding at http://localhost:3000/api/data"
else
  warn "wmd-server did not respond yet. Check: journalctl -u wmd-server -f"
fi

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║          WMD Dashboard deployment complete           ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════╝${NC}"
echo ""
echo "  Install dir : ${INSTALL_DIR}"
echo "  Config file : ${INSTALL_DIR}/config.json"
echo "  Backend     : http://localhost:3000"
echo ""
echo "  Next steps:"
echo "    1. Edit config:  nano ${INSTALL_DIR}/config.json"
echo "    2. Restart:      sudo systemctl restart wmd-server"
echo "    3. View logs:    journalctl -u wmd-server -f"
echo "    4. Reboot to start Chromium kiosk via labwc autostart."
echo ""
echo "  Quick verify:"
echo "    systemctl status wmd-server"
echo "    curl http://localhost:3000/api/data | python3 -m json.tool"
