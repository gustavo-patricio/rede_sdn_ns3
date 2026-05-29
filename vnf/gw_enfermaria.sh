#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

require_command iptables

enable_forwarding
ensure_log_rule "$ENFERMARIA_NET" "GW_ENFERMARIA_TRAFEGO: "
ensure_forward_accept "$ENFERMARIA_NET"

echo "Gateway enfermaria configurado: $ENFERMARIA_NET -> $SERVER_IP"
