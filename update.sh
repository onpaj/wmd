#!/usr/bin/env bash
# WMD Dashboard — Remote update script
# Usage: ./update.sh [user@host]
# Default host: rem@192.168.10.66

set -euo pipefail

HOST="${1:-rem@192.168.10.66}"
SSH="ssh -i ~/.ssh/id_ed25519_rpi"

echo "Updating WMD on ${HOST}..."

$SSH "$HOST" 'bash -s' << 'REMOTE'
set -euo pipefail
cd ~/wmd

echo "→ Pulling latest code..."
git fetch origin
git reset --hard origin/master

echo "→ Rebuilding frontend..."
npm ci --silent
npm run build

echo "→ Updating Python dependencies..."
.venv/bin/pip install --quiet -r requirements.txt

echo "→ Restarting wmd-server..."
sudo systemctl restart wmd-server

echo "→ Verifying..."
sleep 3
if curl -sf http://localhost:3000/api/data > /dev/null; then
  echo "✓ wmd-server is responding"
else
  echo "✗ wmd-server not responding — check: journalctl -u wmd-server -f"
  exit 1
fi

echo "→ Reloading Chromium..."
pkill -f chromium || true
REMOTE

echo "Update complete."
