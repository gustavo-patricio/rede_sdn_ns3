#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

require_command iptables

iptables -C FORWARD -s "$TRIAGEM_NET" -d "$SERVER_IP" -j DROP 2>/dev/null || \
    iptables -I FORWARD -s "$TRIAGEM_NET" -d "$SERVER_IP" -j DROP

echo "Bloqueio aplicado na triagem: $TRIAGEM_NET -> $SERVER_IP"
