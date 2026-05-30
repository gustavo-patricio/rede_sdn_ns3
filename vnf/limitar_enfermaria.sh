#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

require_command tc

WAN_IFACE="$(iface_for_server)"
remove_enfermaria_limit "$WAN_IFACE"
tc qdisc add dev "$WAN_IFACE" root tbf \
    rate "$LIMIT_RATE" \
    burst "$LIMIT_BURST" \
    latency "$LIMIT_LATENCY"

echo "Limitacao aplicada na enfermaria: iface=$WAN_IFACE rate=$LIMIT_RATE burst=$LIMIT_BURST latency=$LIMIT_LATENCY"
