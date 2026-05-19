#!/usr/bin/env bash
# Deploy ADSB Nearby custom integration to Home Assistant via rsync
# Usage: ./deploy.sh root@YOUR_HA_IP:/config/
#   or:  ./deploy.sh homeassistant@192.168.1.100:/home/homeassistant/.homeassistant/

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="${SCRIPT_DIR}/custom_components/adsb_nearby/"

if [ $# -eq 0 ]; then
    echo "Usage: $0 <user>@<host>:<ha-config-path>"
    echo ""
    echo "Examples:"
    echo "  $0 root@192.168.1.100:/config/"
    echo "  $0 homeassistant@192.168.1.100:/home/homeassistant/.homeassistant/"
    exit 1
fi

DEST="$1"

echo "Deploying ADSB Nearby integration..."
echo "  Source: ${SRC}"
echo "  Dest:   ${DEST}custom_components/adsb_nearby/"
echo ""

rsync -av --delete \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.DS_Store' \
    --exclude='*.egg-info' \
    "${SRC}" \
    "${DEST}custom_components/adsb_nearby/"

echo ""
echo "Done. Restart Home Assistant to load the updated integration."
