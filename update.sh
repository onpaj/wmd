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

echo "→ Reloading Chromium..."
pkill -f chromium || true
REMOTE

echo "Update complete."
