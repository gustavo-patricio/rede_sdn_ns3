#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

require_command iptables

enable_forwarding
ensure_log_rule "$TRIAGEM_NET" "GW_TRIAGEM_TRAFEGO: "
ensure_forward_accept "$TRIAGEM_NET"

echo "Gateway triagem configurado: $TRIAGEM_NET -> $SERVER_IP"
