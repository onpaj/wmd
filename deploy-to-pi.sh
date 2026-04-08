#!/usr/bin/env bash
# Local wrapper — deploys WMD to a remote machine over SSH in one command.
#
# Usage:
#   ./deploy-to-pi.sh <user@host> [repo-url] [config-file]
#
# Examples:
#   ./deploy-to-pi.sh ubuntu@192.168.1.50
#   ./deploy-to-pi.sh ubuntu@192.168.1.50 https://github.com/you/wmd.git
#   ./deploy-to-pi.sh ubuntu@192.168.1.50 https://github.com/you/wmd.git config.json
#   ./deploy-to-pi.sh pi@raspberrypi.local "" config.json   # no git URL, just config

set -euo pipefail

SSH_TARGET="${1:-}"
REPO_URL="${2:-}"
CONFIG_FILE="${3:-}"

[[ -z "$SSH_TARGET" ]] && { echo "Usage: $0 <user@host> [repo-url] [config-file]"; exit 1; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

CONFIG_B64=""
if [[ -n "$CONFIG_FILE" ]]; then
  [[ ! -f "$CONFIG_FILE" ]] && { echo "Config file not found: $CONFIG_FILE"; exit 1; }
  CONFIG_B64="$(base64 < "$CONFIG_FILE")"
  echo "[local] Config file: $CONFIG_FILE ($(wc -c < "$CONFIG_FILE") bytes)"
fi

echo "[local] Deploying to ${SSH_TARGET}..."
echo "[local] Repo URL: ${REPO_URL:-'(none — use existing code)'}"
echo "[local] Config:   ${CONFIG_FILE:-'(none — keep existing or create from example)'}"
echo ""

# shellcheck disable=SC2087
ssh "$SSH_TARGET" 'bash -s' -- "$REPO_URL" "$CONFIG_B64" < "$SCRIPT_DIR/deploy.sh"
